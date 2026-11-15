# -*- coding: utf-8 -*-
"""奇遇扫描。"""
from ..common import bag_entries

KEY = "event"
LABEL = "奇遇"


def _event_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def scan_event(obj, meta):
    """整理奇遇进度：结算结局、实际所得、对话选择，并合并配置里的结局与奖励。"""
    player = obj.get("playerModel") or {}
    settlements = ((player.get("random_event_settlements") or {}).get("quests") or {})
    choices = ((player.get("dialogue_choice") or {}).get("choices") or {})
    owned = {}
    for entry in bag_entries(player.get("bag")):
        item_id = entry.get("item_id")
        if item_id is None:
            continue
        owned[str(item_id)] = owned.get(str(item_id), 0) + _event_int(entry.get("count"), 1)
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
        row = {key: value for key, value in event.items() if key != "dialogue"}
        row.update({
            "endings": endings, "achieved": achieved,
            "completed": bool(saved.get("completed")),
            "ending": ending_id,
            "ending_title": next((ending.get("title") for ending in endings if ending.get("got")), ""),
            "unknown_ending": bool(ending_id) and not any(ending.get("got") for ending in endings),
            "grants": grants,
            "choices": [{"text": text, "count": count} for text, count in picked.items()],
        })
        rows.append(row)
        for ending in endings:
            for reward in ending.get("rewards") or []:
                key = str(reward.get("item"))
                slot = index.setdefault(key, {
                    "item": reward.get("item"), "name": reward.get("name"),
                    "quality": reward.get("quality"), "type": reward.get("type"),
                    "owned": reward.get("owned", 0), "sources": [],
                })
                slot["sources"].append({
                    "event": quest_id, "event_name": event.get("name"),
                    "ending": ending.get("id"), "ending_title": ending.get("title"),
                    "grade": ending.get("grade"), "chance": reward.get("chance"),
                    "min": reward.get("min"), "max": reward.get("max"),
                    "expected": reward.get("expected"), "got": ending.get("got"),
                })
    rows.sort(key=lambda row: (row.get("realm") or 0, row.get("id") or 0))
    stats = {
        "events": len(rows),
        "achieved": sum(1 for row in rows if row["achieved"]),
        "endings": sum(len(row["endings"]) for row in rows),
        "got_endings": sum(1 for row in rows for ending in row["endings"] if ending["got"]),
        "granted": sum(len(row["grants"]) for row in rows),
        "reward_items": len(index),
    }
    catalog = sorted(index.values(), key=lambda row: (row.get("quality") or 0, str(row.get("name"))))
    realms = meta.get("realms") or {"0": "凡人"}
    layer = (player.get("combat") or {}).get("cultivate_layer_id")
    current_realm = _event_int((meta.get("phases") or {}).get(str(layer))) if layer is not None else 0
    return {"rows": rows, "reward_index": catalog, "stats": stats,
            "realms": realms, "current_realm": current_realm,
            "current_realm_name": realms.get(str(current_realm)) or "",
            "meta_stats": meta.get("stats") or {}, "grades": meta.get("grades") or {}}


def meta(metadata):
    return metadata.get("event") or {"events": [], "realms": {"0": "凡人"},
                                     "grades": {}, "stats": {}}


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    return scan_event(obj, meta_obj)


def post(rows, state, original, path):
    return rows


def enrich(module, meta_obj, state=None):
    return module


def summary(module):
    stats = (module.get("rows") or {}).get("stats") or {}
    return "奇遇：%d 个奇遇，已达成 %d 个；结局 %d/%d，实际所得 %d 条" % (
        stats.get("events", 0), stats.get("achieved", 0),
        stats.get("got_endings", 0), stats.get("endings", 0),
        stats.get("granted", 0))
