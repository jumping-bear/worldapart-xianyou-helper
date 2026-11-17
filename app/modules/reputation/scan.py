# -*- coding: utf-8 -*-
"""城镇声望扫描：当前声望、称号、委托完成后的跨档预测与货架解锁。"""
import os


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _key_map(mapping):
    out = {}
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            out[_int(key)] = value
    return out


def _time_text(value):
    if not isinstance(value, dict):
        return ""
    year, month, day = _int(value.get("year")), _int(value.get("month")), _int(value.get("day"))
    if not (year or month or day):
        return ""
    return "%d年%d月%d日" % (year, month, day)


def _pick_title(titles, reputation):
    current = None
    for title in titles or []:
        if _int(title.get("min")) <= reputation <= _int(title.get("max")):
            current = title
        elif _int(title.get("min")) <= reputation:
            current = current or title
    return current


def _next_title(titles, reputation):
    for title in titles or []:
        if _int(title.get("min")) > reputation:
            return title
    return None


def _gate_label(town, threshold):
    parts = []
    if threshold in (town.get("shelf") or {}).get("gates", []):
        parts.append("货架 %d" % threshold)
    for title in town.get("titles") or []:
        if _int(title.get("min")) == threshold:
            parts.append("称号 %d · %s" % (threshold, title.get("name") or ""))
            break
    return " / ".join(parts) or ("门槛 %d" % threshold)


def _gates(town):
    values = set()
    for threshold in (town.get("shelf") or {}).get("gates") or []:
        values.add(_int(threshold))
    for title in town.get("titles") or []:
        if _int(title.get("min")) > 0:
            values.add(_int(title.get("min")))
    return sorted(values)


def meta(metadata):
    return metadata.get("reputation") or {
        "schema": 1, "towns": [], "active_count": 0, "shelf_count": 0, "warnings": [],
    }


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    player = (obj or {}).get("playerModel") or {}
    behavior = player.get("behavior_value") or {}
    city_reputes = _key_map(behavior.get("city_reputes"))
    seen = [_int(value) for value in behavior.get("seen_city_reputation_unlocks") or []]
    component = player.get("questComponent") or {}
    force_records = _key_map((component.get("commission_task_component") or {}).get("force_records"))
    warnings = []
    known_towns = {_int(town.get("id")) for town in meta_obj.get("towns") or []}
    for town_id, value in city_reputes.items():
        if town_id and town_id not in known_towns:
            warnings.append("存档城镇声望 %s 未在城镇表中找到" % town_id)

    rows = []
    for town in meta_obj.get("towns") or []:
        town_id = _int(town.get("id"))
        reputation = _int(city_reputes.get(town_id))
        force_id = _int(town.get("force"))
        record = force_records.get(force_id) or {}
        task_ids = [_int(value) for value in record.get("task_ids") or [] if _int(value)]
        accepted_ids = {_int(value) for value in record.get("accepted_task_ids") or [] if _int(value)}
        pool = {_int(task.get("id")): task for task in town.get("pool") or []}
        offers, missing = [], []
        for task_id in task_ids:
            task = pool.get(task_id)
            if not task:
                missing.append(task_id)
                continue
            entry = dict(task)
            entry["accepted"] = task_id in accepted_ids
            entry["state"] = "进行中" if entry["accepted"] else "可接取"
            offers.append(entry)
        if missing:
            warnings.append("%s 有 %d 条委托不在当前委托池中（%s）"
                            % (town.get("name") or town_id, len(missing),
                               "、".join(str(value) for value in missing[:4])))
        for task_id in accepted_ids:
            if task_id not in task_ids and task_id not in pool:
                warnings.append("%s 已接委托 %s 未在委托池中" % (town.get("name") or town_id, task_id))

        available = [entry for entry in offers if not entry["accepted"]]
        reputation_gain = sum(_int(entry.get("reputation")) for entry in offers)
        available_gain = sum(_int(entry.get("reputation")) for entry in available)
        stones_gain = sum(_int(entry.get("stones")) for entry in offers)
        available_stones = sum(_int(entry.get("stones")) for entry in available)
        after = reputation + reputation_gain
        gates = _gates(town)
        next_gate = next((value for value in gates if value > reputation), 0)
        crossed = [value for value in gates if reputation < value <= after]
        current_title = _pick_title(town.get("titles") or [], reputation)
        next_title = _next_title(town.get("titles") or [], reputation)

        tiers = []
        for tier in (town.get("shelf") or {}).get("tiers") or []:
            threshold = _int(tier.get("threshold"))
            tiers.append({
                "threshold": threshold,
                "unlocked": reputation >= threshold,
                "after": after >= threshold,
                "duplicate": bool(tier.get("duplicate")),
                "same_as": _int(tier.get("same_as")),
                "price": _int(tier.get("price")),
                "items": tier.get("items") or [],
            })

        rows.append({
            "id": town_id,
            "name": town.get("name") or "",
            "active": bool(town.get("active")),
            "reputation": reputation,
            "reputation_id": _int(town.get("reputation_id")),
            "title": (current_title or {}).get("name") or "尚无称号",
            "title_desc": (current_title or {}).get("desc") or "",
            "next_title": ({"min": _int(next_title.get("min")),
                            "name": next_title.get("name") or ""} if next_title else None),
            "force": force_id,
            "offers": offers,
            "available": len(available),
            "accepted": len(offers) - len(available),
            "reputation_gain": reputation_gain,
            "available_gain": available_gain,
            "stones_gain": stones_gain,
            "available_stones": available_stones,
            "after": after,
            "crossed": [{"rep": value, "label": _gate_label(town, value)} for value in crossed],
            "next_gate": ({"rep": next_gate, "label": _gate_label(town, next_gate)}
                          if next_gate else None),
            "tier_states": tiers,
            "seen": town_id in seen,
            "refresh": _time_text(record.get("refresh_time")),
            "state": ("未开放" if not town.get("active")
                      else ("本期未刷新" if not task_ids else "可接取")),
        })

    active = [row for row in rows if row["active"]]
    highest = max(active, key=lambda row: row["reputation"]) if active else None
    totals = {
        "towns": len(active),
        "total_reputation": sum(row["reputation"] for row in active),
        "available_gain": sum(row["available_gain"] for row in active),
        "available_stones": sum(row["available_stones"] for row in active),
        "available_tasks": sum(row["available"] for row in active),
        "accepted_tasks": sum(row["accepted"] for row in active),
        "unlocked_shelf": sum(1 for row in active
                              if any(tier["unlocked"] for tier in row["tier_states"])),
        "seen": len([value for value in seen if value in known_towns]),
        "highest": ({"name": highest["name"], "reputation": highest["reputation"]}
                    if highest else None),
    }
    return {"towns": rows, "totals": totals, "seen": seen, "warnings": warnings}


def post(rows, state, original, path):
    if isinstance(rows, dict):
        rows["src"] = os.path.basename(original) if original else os.path.basename(path or "")
    return rows


def enrich(module, meta_obj, state=None):
    module["config"] = meta_obj or {}
    module["config_warnings"] = (meta_obj or {}).get("warnings") or []
    return module


def summary(module):
    rows = module.get("rows") or {}
    totals = rows.get("totals") or {}
    highest = totals.get("highest") or {}
    return "声望：%d 个城镇，合计 %d，本期可获 %d 声望；最高 %s %d" % (
        _int(totals.get("towns")), _int(totals.get("total_reputation")),
        _int(totals.get("available_gain")), highest.get("name") or "-",
        _int(highest.get("reputation")))
