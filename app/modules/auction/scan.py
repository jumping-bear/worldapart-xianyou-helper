# -*- coding: utf-8 -*-
"""拍卖会：从存档快照里整理本场拍品与寄售记录。"""

MARGIN = 0.2  # 建议出价上限 = 参考价值 × (1 - MARGIN)


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _realm_of(phases, layer):
    current = 0
    for item in phases or []:
        if layer >= _int(item.get("start")):
            current = _int(item.get("realm"))
    return current


def _loan_for(loans, layer):
    best, value = -1, 0
    for raw, amount in (loans or {}).items():
        try:
            start = int(raw)
        except (TypeError, ValueError):
            continue
        if start <= layer and start > best:
            best, value = start, _int(amount)
    return value


def _cell(row, items, notes):
    item_id = row.get("item_id")
    info = items.get(str(item_id)) or {}
    if item_id and not info:
        notes["unknown_items"].add(str(item_id))
    return {
        "index": row.get("index"),
        "item_id": item_id,
        "name": info.get("name") or ("物品 %s" % item_id if item_id else "空"),
        "type": info.get("type") or "",
        "quality": info.get("quality"),
        "count": _int(row.get("item_count"), 1),
        "revealed": bool(row.get("revealed")),
    }


def _chest(raw, config_id, chests, items, notes):
    config = chests.get(str(config_id))
    if config is None:
        notes["unknown_chests"].add(str(config_id))
        config = {}
    if "cells" not in raw:
        notes["chest_no_cells"] += 1
    cells = [_cell(cell, items, notes) for cell in (raw.get("cells") or []) if isinstance(cell, dict)]
    return {
        "config_id": config_id,
        "name": config.get("name") or ("珍匣 %s" % config_id),
        "cells": _int(raw.get("total_cell_count")),
        "start_price": _int(raw.get("start_price")),
        "expected": _int(raw.get("expected_total_price")),
        "true_total": _int(raw.get("total_true_value")),
        "reveal_per_bid": _int(raw.get("reveal_per_bid")),
        "init_reveal": _int(raw.get("init_reveal_count")),
        "cap": _int(raw.get("reveal_cap_ratio")),
        "detail": cells,
    }


def _item(raw, meta, notes):
    items = meta.get("items") or {}
    chests = {str(c.get("id")): c for c in meta.get("chests") or [] if isinstance(c, dict)}
    item_id = raw.get("item_id")
    info = items.get(str(item_id)) or {}
    if item_id and not info:
        notes["unknown_items"].add(str(item_id))
    chest = _chest(raw.get("chest"), raw.get("chest_config_id"), chests, items, notes) \
        if isinstance(raw.get("chest"), dict) else None
    if "true_value" not in raw or "base_price" not in raw:
        notes["missing_value"] += 1
    true_value = _int(raw.get("true_value"))
    base_price = _int(raw.get("base_price"))
    return {
        "pool_entry_id": raw.get("pool_entry_id"),
        "item_id": item_id,
        "name": (chest or {}).get("name") or info.get("name") or ("物品 %s" % item_id),
        "type": "珍匣" if chest else (info.get("type") or "未分类"),
        "quality": info.get("quality"),
        "quantity": _int(raw.get("quantity"), 1),
        "value_known": "true_value" in raw and "base_price" in raw,
        "true_value": true_value,
        "base_price": base_price,
        "ratio": round(float(true_value) / base_price, 2) if base_price else 0,
        "suggest_max": int(true_value * (1 - MARGIN)),
        "gap": true_value - base_price,
        "rarity": raw.get("item_rarity"),
        "finale": bool(raw.get("is_finale")),
        "sort_hint": _int(raw.get("sort_hint")),
        "chest": chest,
    }


def _note(has_player, has_component):
    if not has_player:
        return "还没有可用存档。"
    if not has_component:
        return "此存档没有拍卖会数据，可能游戏版本较旧或该功能尚未开放。"
    return ""


def _issues(notes, has_player, has_component, last_settle, has_sessions):
    out = []
    if not has_player:
        return out
    if not has_component:
        out.append("未找到拍卖会数据字段，可能游戏版本较旧或该功能尚未开放。")
        return out
    if notes["unknown_venues"]:
        ids = "、".join(sorted(notes["unknown_venues"])[:3])
        out.append("有 %d 个未知拍卖行（%s），配置可能已更新。" % (len(notes["unknown_venues"]), ids))
    if notes["unknown_chests"]:
        ids = "、".join(sorted(notes["unknown_chests"])[:3])
        out.append("有 %d 个未知珍匣配置（%s），已显示原始编号。" % (len(notes["unknown_chests"]), ids))
    if notes["unknown_items"]:
        ids = "、".join(sorted(notes["unknown_items"])[:3])
        out.append("有 %d 个物品未在配置中找到（%s），名称显示为原始编号。"
                   % (len(notes["unknown_items"]), ids))
    if notes["missing_value"]:
        out.append("有 %d 件拍品缺少参考价值字段，未给出出价建议。" % notes["missing_value"])
    if notes["empty_sessions"]:
        out.append("有 %d 个场次没有拍品数据，存档结构可能已更新。" % notes["empty_sessions"])
    if has_sessions and not last_settle:
        out.append("存档缺少上次结算时间，本场/历史按已结束记录推断，可能不准。")
    return out


def scan_auction(obj, meta, state=None):
    pm = obj.get("playerModel") or {}
    has_player = bool(pm)
    has_component = isinstance(pm.get("auction_component"), dict)
    auction = pm.get("auction_component") or {}
    notes = {"unknown_venues": set(), "unknown_chests": set(), "unknown_items": set(),
             "missing_value": 0, "empty_sessions": 0}
    combat = pm.get("combat") or {}
    layer = _int(combat.get("cultivate_layer_id"))
    player_realm = _realm_of(meta.get("phases"), layer)
    venues = {str(v.get("id")): v for v in meta.get("venues") or [] if isinstance(v, dict)}
    last_settle = _int(auction.get("last_settlement_time_units"))
    finished = {str(v) for v in (auction.get("finished_by_group") or {}).values()}
    sessions, warnings = [], []
    for key, snap in sorted((auction.get("generated_session_snapshots") or {}).items()):
        if not isinstance(snap, dict):
            continue
        venue_id, _, occurrence = str(key).partition(":")
        try:
            venue_id, occurrence = int(venue_id), int(occurrence)
        except (TypeError, ValueError):
            warnings.append("无法识别拍卖场次 %s" % key)
            continue
        venue = venues.get(str(venue_id))
        if venue is None:
            notes["unknown_venues"].add(str(venue_id))
            venue = {}
        if last_settle and occurrence > last_settle:
            state = "current"
        elif str(occurrence) in finished or (last_settle and occurrence <= last_settle):
            state = "finished"
        else:
            state = "current" if not last_settle else "finished"
        level = _int(venue.get("realm_id"))
        raws = [raw for raw in (snap.get("items") or []) if isinstance(raw, dict)]
        if not raws:
            notes["empty_sessions"] += 1
        items = [_item(raw, meta, notes) for raw in raws]
        items.sort(key=lambda i: (i["sort_hint"], i["base_price"]))
        sessions.append({
            "key": str(key),
            "venue_id": venue_id,
            "venue_name": venue.get("name") or ("拍卖行 %s" % venue_id),
            "venue_realm": level,
            "occurrence": occurrence,
            "state": state,
            "attend": level <= player_realm if player_realm else True,
            "same_realm": level == player_realm,
            "items": items,
            "worth": sum(1 for i in items if i["ratio"] >= 1.2),
            "total_value": sum(i["true_value"] for i in items),
            "total_start": sum(i["base_price"] for i in items),
        })
    sessions.sort(key=lambda s: (s["state"] != "current", -s["occurrence"]))
    pending = auction.get("pending_consignments") or {}
    loans = meta.get("loans") or {}
    warnings.extend(_issues(notes, has_player, has_component, last_settle, bool(sessions)))
    return {
        "available": has_component,
        "note": _note(has_player, has_component),
        "character": {
            "name": pm.get("playerName") or "未命名",
            "layer": layer,
            "realm": player_realm,
            "realm_name": (meta.get("realms") or {}).get(str(player_realm)) or ("境界 %s" % player_realm),
        },
        "sessions": sessions,
        "current": [s for s in sessions if s["state"] == "current"],
        "history": [s for s in sessions if s["state"] == "finished"],
        "consign": {
            "earnings": _int(auction.get("last_consign_earnings")),
            "sold": _int(auction.get("last_consign_sold_count")),
            "unsold": _int(auction.get("last_consign_unsold_count")),
            "pending": len(pending) if isinstance(pending, dict) else 0,
            "last_settle": last_settle,
        },
        "loan": {"layer": layer, "max": _loan_for(loans, layer)},
        "warnings": warnings,
    }


scan = scan_auction


def meta(metadata):
    return metadata.get("auction") or {}


def enrich(module, meta_obj, state=None):
    module["venues"] = meta_obj.get("venues") or []
    module["chests"] = meta_obj.get("chests") or []
    module["tactics"] = meta_obj.get("tactics") or []
    module["hermits"] = meta_obj.get("hermits") or []
    module["loans"] = meta_obj.get("loans") or {}
    module["realms"] = meta_obj.get("realms") or {}
    module["phases"] = meta_obj.get("phases") or []
    module["pool"] = meta_obj.get("pool") or []
    return module


def summary(module):
    rows = module.get("rows") or {}
    if rows.get("available") is False:
        return "拍卖会：此存档暂无拍卖数据"
    current = rows.get("current") or []
    count = sum(len(s.get("items") or []) for s in current)
    worth = sum(s.get("worth") or 0 for s in current)
    return "拍卖会：本场 %d 场、%d 件拍品，值得跟 %d 件" % (len(current), count, worth)


def empty():
    return {
        "available": False,
        "note": "还没有可用存档。",
        "character": {"name": "未命名", "layer": 0, "realm": 0, "realm_name": "凡人"},
        "sessions": [], "current": [], "history": [],
        "consign": {"earnings": 0, "sold": 0, "unsold": 0, "pending": 0, "last_settle": 0},
        "loan": {"layer": 0, "max": 0}, "warnings": [],
    }


def builtin_ok(data):
    return (isinstance(data, dict) and isinstance(data.get("venues"), list)
            and isinstance(data.get("items"), dict))
