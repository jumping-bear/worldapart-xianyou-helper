# -*- coding: utf-8 -*-
"""奇遇扫描：结算、选项条件、属性等级、历史达成与奖励推荐。"""
import os
import time

import meta_update

from ...common import bag_entries


HISTORY_FILE = "event_history.json"


def _event_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _history_path():
    return os.path.join(meta_update.cache_directory(), HISTORY_FILE)


def _load_history():
    data = meta_update._read_json(_history_path(), {})
    return data if isinstance(data, dict) else {}


def _attr_level(levels, exp):
    thresholds = [value for value in levels or [] if isinstance(value, int) and value > 0]
    if not thresholds:
        return 0, 0
    level = sum(1 for value in thresholds if exp > value) + 1
    next_exp = thresholds[level - 1] if level <= len(thresholds) else 0
    return level, next_exp


def _score_item(item):
    quality = item.get("quality") or 0
    price = min((item.get("price") or 0) / 200.0, 20.0)
    uses = len(item.get("use") or [])
    sources = len(item.get("sources") or [])
    owned = item.get("owned") or 0
    score = quality * 18 + price + uses * 10 + (15 if sources == 1 else 0) + (20 if owned == 0 else 0)
    reasons = []
    if quality >= 4:
        reasons.append("品质 %s" % quality)
    if item.get("price"):
        reasons.append("单价 %s" % item["price"])
    for tag in item.get("use") or []:
        reasons.append(tag)
    if sources == 1:
        reasons.append("仅 1 条结局产出")
    if not owned:
        reasons.append("未拥有")
    return round(score), reasons


def scan_event(obj, meta):
    """整理奇遇进度，并标注选项条件是否满足当前角色。"""
    player = obj.get("playerModel") or {}
    settlements = ((player.get("random_event_settlements") or {}).get("quests") or {})
    choices = ((player.get("dialogue_choice") or {}).get("choices") or {})
    character_name = player.get("playerName") or "未命名"
    layer = (player.get("combat") or {}).get("cultivate_layer_id")
    phase = meta.get("phases") or {}
    realm_id = _event_int(phase.get(str(layer))) if layer is not None else 0
    realms = meta.get("realms") or {"0": "凡人"}
    character = {
        "name": character_name, "layer": _event_int(layer),
        "realm": realm_id, "realm_name": realms.get(str(realm_id)) or "",
        "file": os.path.basename(obj.get("_source_path") or ""),
    }

    owned = {}
    for entry in bag_entries(player.get("bag")):
        item_id = entry.get("item_id")
        if item_id is None:
            continue
        owned[str(item_id)] = owned.get(str(item_id), 0) + _event_int(entry.get("count"), 1)

    raw_attrs = player.get("interact_attributes") or {}
    attrs = {}
    for attr_id, info in (meta.get("attrs") or {}).items():
        exp = _event_int(raw_attrs.get(attr_id) if isinstance(raw_attrs, dict) else 0)
        if not exp and isinstance(raw_attrs, dict):
            exp = _event_int(raw_attrs.get(_event_int(attr_id)))
        level, next_exp = _attr_level(info.get("levels") or [], exp)
        attrs[str(attr_id)] = {
            "name": info.get("name") or ("探索属性 %s" % attr_id),
            "exp": exp, "level": level, "next": next_exp,
            "desc": info.get("desc") or "",
        }
    money = sum(owned.get(str(item_id), 0) for item_id in meta.get("currency") or [])

    history = _load_history()
    history_events = ((history.get(character_name) or {}).get("events") or {})

    rows, index = [], {}
    for event in meta.get("events") or []:
        if not isinstance(event, dict) or event.get("id") is None:
            continue
        quest_id = event["id"]
        saved = settlements.get(quest_id)
        if not isinstance(saved, dict):
            saved = settlements.get(str(quest_id))
        saved = saved if isinstance(saved, dict) else {}
        ending_id = _event_int(saved.get("ending"))
        grants = []
        for grant in saved.get("grants") or []:
            if not isinstance(grant, dict) or grant.get("item") is None:
                continue
            item_id = _event_int(grant.get("item"))
            grants.append({"item": item_id, "count": _event_int(grant.get("count"), 1),
                           "delivered": bool(grant.get("delivered")),
                           "owned": owned.get(str(item_id), 0)})
        endings = []
        for ending in event.get("endings") or []:
            rewards = [dict(reward, owned=owned.get(str(reward.get("item")), 0))
                       for reward in (ending.get("rewards") or [])]
            endings.append(dict(ending, rewards=rewards,
                                got=bool(ending_id) and ending.get("id") == ending_id))
        picked = {}
        dialogue = event.get("dialogue") or {}
        for key, counter in choices.items():
            try:
                dialogue_id = int(key)
            except (TypeError, ValueError):
                continue
            texts = dialogue.get(str(dialogue_id))
            if not texts or not isinstance(counter, dict):
                continue
            for option, count in counter.items():
                try:
                    option_index = int(option)
                except (TypeError, ValueError):
                    continue
                if 0 <= option_index < len(texts):
                    text = texts[option_index]
                    picked[text] = picked.get(text, 0) + max(1, _event_int(count, 1))
        achieved = bool(ending_id) or bool(saved.get("completed"))
        record = history_events.get(str(quest_id)) or {}
        history_endings = [value for value in record.get("endings") or [] if isinstance(value, int)]
        for ending in endings:
            if ending.get("id") in history_endings:
                ending["history_got"] = True
        row = {key: value for key, value in event.items() if key != "dialogue"}
        row.update({
            "endings": endings, "achieved": achieved or bool(history_endings),
            "history_only": bool(history_endings) and not achieved,
            "completed": bool(saved.get("completed")),
            "ending": ending_id,
            "ending_title": next((ending.get("title") for ending in endings if ending.get("got")), ""),
            "unknown_ending": bool(ending_id) and not any(ending.get("got") for ending in endings),
            "history_endings": history_endings,
            "grants": grants,
            "choices": [{"text": text, "count": count} for text, count in picked.items()],
            "tree_endings": len((event.get("tree") or {}).get("endings") or []),
        })
        rows.append(row)

        for ending in endings:
            for reward in ending.get("rewards") or []:
                key = str(reward.get("item"))
                slot = index.setdefault(key, {
                    "item": reward.get("item"), "name": reward.get("name"),
                    "quality": reward.get("quality"), "type": reward.get("type"),
                    "price": reward.get("price") or 0, "use": reward.get("use") or [],
                    "desc": reward.get("desc") or "",
                    "owned": reward.get("owned", 0), "sources": [], "got": False,
                })
                slot["got"] = slot["got"] or ending.get("got")
                slot["sources"].append({
                    "event": quest_id, "event_name": event.get("name"),
                    "ending": ending.get("id"), "ending_title": ending.get("title"),
                    "grade": ending.get("grade"), "chance": reward.get("chance"),
                    "min": reward.get("min"), "max": reward.get("max"),
                    "expected": reward.get("expected"), "got": ending.get("got"),
                })

    # 把本世结算并入历史账本，突破或换角色后仍能看到曾经达成。
    if settlements:
        slot = history.setdefault(character_name, {"events": {}})
        events = slot.setdefault("events", {})
        dirty = False
        for row in rows:
            if not row["achieved"] or not row["ending"]:
                continue
            record = events.setdefault(str(row["id"]), {"endings": [], "grants": {}, "last": 0})
            if row["ending"] not in record["endings"]:
                record["endings"].append(row["ending"])
                dirty = True
            for grant in row["grants"]:
                key = str(grant["item"])
                if grant["count"] > record["grants"].get(key, 0):
                    record["grants"][key] = grant["count"]
                    dirty = True
            if dirty:
                record["last"] = int(time.time())
        if dirty:
            try:
                meta_update._atomic_json(_history_path(), history)
            except Exception:
                pass

    rows.sort(key=lambda row: (row.get("realm") or 0, row.get("id") or 0))
    for slot in index.values():
        slot["score"], slot["reasons"] = _score_item(slot)
    catalog = sorted(index.values(), key=lambda row: (-(row.get("score") or 0), str(row.get("name"))))

    stats = {
        "events": len(rows),
        "achieved": sum(1 for row in rows if row["achieved"]),
        "history": sum(1 for row in rows if row.get("history_only")),
        "endings": sum(len(row["endings"]) for row in rows),
        "got_endings": sum(1 for row in rows for ending in row["endings"]
                           if ending.get("got") or ending.get("history_got")),
        "granted": sum(len(row["grants"]) for row in rows),
        "reward_items": len(index),
    }
    return {"rows": rows, "reward_index": catalog, "stats": stats,
            "realms": realms, "current_realm": realm_id,
            "current_realm_name": realms.get(str(realm_id)) or "",
            "attrs": attrs, "money": money, "character": character,
            "meta_stats": meta.get("stats") or {},
            "grades": meta.get("grade_names") or meta.get("grades") or {},
            "grade_hint": meta.get("grade_hint") or ""}


def meta(metadata):
    return metadata.get("event") or {"events": [], "realms": {"0": "凡人"},
                                     "attrs": {}, "grades": {}, "stats": {}}


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    return scan_event(obj, meta_obj)


def post(rows, state, original, path):
    if isinstance(rows, dict):
        rows["character"]["file"] = os.path.basename(original) if original else os.path.basename(path or "")
        rows["character"]["source"] = path or ""
    return rows


def enrich(module, meta_obj, state=None):
    return module


def summary(module):
    stats = (module.get("rows") or {}).get("stats") or {}
    return "奇遇：%d 个奇遇，已达成 %d 个；结局 %d/%d，实际所得 %d 条" % (
        stats.get("events", 0), stats.get("achieved", 0),
        stats.get("got_endings", 0), stats.get("endings", 0),
        stats.get("granted", 0))
