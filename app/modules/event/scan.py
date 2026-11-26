# -*- coding: utf-8 -*-
"""奇遇扫描：结算、选项条件、属性等级、历史达成与奖励推荐。"""
import os

from app import acquire
import time

import meta_update

from ...common import bag_entries


HISTORY_FILE = "event_history.json"

# 可重复奇遇的结算记录会被重置，但游戏在独立组件里保留了累计次数与最近一次结算。
# 目前只确认了血祭坛：own_blood_count / beast_count / round_number / round_reward。
REPEAT_STATES = {5120100: "blood_altar_event"}


def _repeat_state(player, quest_id):
    field = REPEAT_STATES.get(quest_id)
    data = player.get(field) if field else None
    if not isinstance(data, dict):
        return None
    own = _event_int(data.get("own_blood_count"))
    beast = _event_int(data.get("beast_count"))
    rounds = _event_int(data.get("round_number")) or (own + beast)
    reward = data.get("round_reward") if isinstance(data.get("round_reward"), dict) else {}
    if not rounds and not reward.get("completed"):
        return None
    return {"rounds": rounds, "own": own, "beast": beast,
            "ending": _event_int(reward.get("ending")),
            "completed": bool(reward.get("completed")),
            "label": "献祭 %d 轮" % rounds}


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


def _apply_branches(rows):
    """把子奇遇归到母奇遇下：任一分支达成即视为整条奇遇完成，其余分支不再计入未完成。"""
    by_id = {row.get("id"): row for row in rows}
    children = {}
    for row in rows:
        parent_id = row.get("parent")
        if parent_id and parent_id in by_id and parent_id != row.get("id"):
            children.setdefault(parent_id, []).append(row)
            row["branch"] = True
    for parent_id, branches in children.items():
        parent = by_id[parent_id]
        own_achieved = bool(parent.get("achieved"))
        achieved = own_achieved or any(branch.get("achieved") for branch in branches)
        # 只有历史记录达成、当前存档没有结算时，母奇遇仍标为“历史达成”。
        # 回忆已收录同样视为当前存档的达成，不降级成历史记录。
        memory = any(bool(member.get("memory_got")) for member in [parent] + branches)
        history_only = achieved and not memory and not any(
            member.get("achieved") and not member.get("history_only") and not member.get("memory_got")
            for member in [parent] + branches)
        parent["achieved"] = achieved
        parent["achieved_via_branch"] = achieved and not own_achieved
        parent["group_achieved"] = achieved
        parent["group_size"] = len(branches) + 1
        if memory:
            parent["memory_got"] = True
            parent["memory_only"] = bool(parent.get("memory_only")) or not own_achieved
        if achieved:
            parent["history_only"] = history_only
        for branch in branches:
            branch["branch_selected"] = bool(branch.get("achieved"))
            branch["branch_closed"] = achieved and not branch.get("achieved")
            branch["group_achieved"] = achieved
    return children


def scan_event(obj, meta):
    """整理奇遇进度，并标注选项条件是否满足当前角色。"""
    player = obj.get("playerModel") or {}
    settlements = ((player.get("random_event_settlements") or {}).get("quests") or {})
    choices = ((player.get("dialogue_choice") or {}).get("choices") or {})
    character_name = player.get("playerName") or "未命名"
    layer = (player.get("combat") or {}).get("cultivate_layer_id")
    # 境界 = 层 → 阶段 → 境界。phases 的键是阶段 id，不能直接当层号查。
    layer_realms = meta.get("layer_realms") or {}
    phase = meta.get("phases") or {}
    if layer is not None and str(layer) in layer_realms:
        realm_id = _event_int(layer_realms[str(layer)])
    else:
        realm_id = _event_int(phase.get(str(layer))) if layer is not None else 0
    realms = meta.get("realms") or {"0": "凡人"}
    layer_name = (meta.get("layer_phases") or {}).get(str(layer), "")
    layer_local = (meta.get("layer_numbers") or {}).get(str(layer))
    character = {
        "name": character_name, "layer": _event_int(layer), "layer_local": layer_local,
        "realm": realm_id, "realm_name": realms.get(str(realm_id)) or "",
        "layer_name": layer_name, "date": obj.get("currentGameTime") or {},
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

    memory = player.get("memoria") or {}
    unlocked = memory.get("unlocked") if isinstance(memory.get("unlocked"), dict) else {}

    # 可重复奇遇的结算会被重置，但任务状态/独立组件仍保留完成痕迹。
    saved_quests = (player.get("questComponent") or {}).get("quests") or {}
    quest_states = {}
    for key, value in saved_quests.items():
        quest_states[_event_int(key)] = _event_int((value or {}).get("state"), -1)

    events_meta = [event for event in meta.get("events") or []
                   if isinstance(event, dict) and event.get("id") is not None]
    event_ids = {event["id"] for event in events_meta}
    event_names = {event["id"]: event.get("name") or "" for event in events_meta}
    game_time = obj.get("currentGameTime") or {}
    # 快照里的 id 键会被 JSON 写成字符串；acquire 按 int 查名字，这里转回 int。
    quest_name_map = {_event_int(key): value
                      for key, value in (meta.get("quest_names") or {}).items()}
    open_ctx = {
        "realm": realm_id, "layer": character["layer"], "money": money,
        "quests": quest_states, "quest_names": quest_name_map or event_names,
        "realms": realms, "layer_phases": meta.get("layer_phases") or {},
        "layer_local": meta.get("layer_numbers") or {},
        "game_time": game_time,
        "sect_id": _event_int(player.get("current_sect_id")),
        "sects": meta.get("sect_names") or {},
    }
    # 存档结算可能挂在合成/重复键下（例如石中剑的结局记在 5045999），
    # 必须按 ending → 所属奇遇 归属，不能只查 settlements[event.id]。
    ending_owner = {}
    for event in events_meta:
        for ending in event.get("endings") or []:
            ending_id = ending.get("id")
            if ending_id:
                ending_owner[ending_id] = event["id"]
    settled = {}
    for key, record in settlements.items():
        if not isinstance(record, dict):
            continue
        ending_id = _event_int(record.get("ending"))
        key_id = _event_int(key)
        owner = ending_owner.get(ending_id) or (key_id if key_id in event_ids else None)
        if owner is None:
            continue
        settled.setdefault(owner, []).append(record)

    history = _load_history()
    history_events = ((history.get(character_name) or {}).get("events") or {})

    rows, index = [], {}
    for event in events_meta:
        quest_id = event["id"]
        records = settled.get(quest_id) or []
        got_endings = {_event_int(record.get("ending")) for record in records
                       if _event_int(record.get("ending"))}
        completed = any(bool(record.get("completed")) for record in records)
        grants, grant_seen = [], {}
        for record in records:
            for grant in record.get("grants") or []:
                if not isinstance(grant, dict) or grant.get("item") is None:
                    continue
                item_id = _event_int(grant.get("item"))
                count = _event_int(grant.get("count"), 1)
                slot = grant_seen.get(item_id)
                if slot:
                    slot["count"] = max(slot["count"], count)
                    slot["delivered"] = slot["delivered"] or bool(grant.get("delivered"))
                    continue
                slot = {"item": item_id, "count": count,
                        "delivered": bool(grant.get("delivered")),
                        "owned": owned.get(str(item_id), 0)}
                grant_seen[item_id] = slot
                grants.append(slot)
        endings = []
        for ending in event.get("endings") or []:
            rewards = [dict(reward, owned=owned.get(str(reward.get("item")), 0))
                       for reward in (ending.get("rewards") or [])]
            endings.append(dict(ending, rewards=rewards,
                                got=ending.get("id") in got_endings))
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
        memory_id = _event_int(event.get("memoria"))
        memory_got = bool(memory_id) and bool(unlocked.get(str(memory_id)) or unlocked.get(memory_id))
        quest_done = quest_states.get(quest_id) in (2, 3)
        repeat = _repeat_state(player, quest_id)
        repeat_done = bool(repeat) and (repeat["rounds"] > 0 or repeat["completed"])
        if repeat and repeat.get("ending"):
            repeat["ending_title"] = next(
                (ending.get("title") for ending in endings if ending.get("id") == repeat["ending"]), "")
        record = history_events.get(str(quest_id)) or {}
        history_endings = [value for value in record.get("endings") or [] if isinstance(value, int)]
        for ending in endings:
            if ending.get("id") in history_endings:
                ending["history_got"] = True
        # 历史账本只作旧存档展示，不能参与当前完成判定：玩家读回旧档后，
        # 旧时间线（或其他存档分支）的结局会一直留在这里，造成误判为已达成。
        achieved = bool(got_endings) or completed or memory_got or repeat_done \
            or quest_done
        known_endings = {ending.get("id") for ending in endings}
        location = event.get("location") or {}
        sect_id = _event_int(location.get("sect"))
        followups = []
        for followup in event.get("followups") or []:
            item = dict(followup)
            stage = quest_states.get(_event_int(item.get("stage_quest")), -1)
            outcome = quest_states.get(_event_int(item.get("outcome_quest")), -1)
            if outcome in (2, 3):
                label = "已领取"
            elif outcome in (1, 6):
                label = "可领取"
            elif stage in (1, 6):
                label = "等待中"
            elif stage in (2, 3):
                label = "可领取"
            else:
                label = "未接取"
            item["state_label"] = label
            item["got"] = outcome in (2, 3)
            followups.append(item)
        prereqs = []
        for item in (event.get("open") or {}).get("prereqs") or []:
            entry = dict(item)
            if entry.get("type") == "quest":
                quest_id = _event_int(entry.get("quest"))
                state = quest_states.get(quest_id, -1)
                entry["state"] = state
                entry["state_label"] = acquire.quest_state_label(state)
                entry["ok"] = state in (2, 3)
                entry["held"] = state in (1, 2, 6)
                entry["in_progress"] = state == 1
                other = []
                for alt in entry.get("alternatives") or []:
                    ids = alt.get("quests") or []
                    if any(quest_states.get(_event_int(other_id), -1) in (1, 2, 3, 6)
                           for other_id in ids):
                        text = alt.get("option") or ""
                        if text and text not in other:
                            other.append(text)
                entry["other_branch"] = other
            prereqs.append(entry)
        open_status, open_checks = acquire.evaluate(
            (event.get("open") or {}).get("checks"), open_ctx)
        row = {key: value for key, value in event.items() if key != "dialogue"}
        row.update({
            "endings": endings, "achieved": achieved,
            "followups": followups,
            "prereqs": prereqs,
            "sect": sect_id, "sect_name": location.get("sect_name") or "",
            "sect_ok": (not sect_id) or sect_id == open_ctx.get("sect_id"),
            "open_status": open_status,
            "open_checks": open_checks,
            "open_blockers": [check for check in open_checks if check.get("ok") is False],
            "history_only": bool(history_endings) and not (
                got_endings or completed or memory_got or repeat_done or quest_done),
            "memory_got": memory_got,
            "memory_only": memory_got and not (got_endings or completed or repeat_done),
            "quest_done": quest_done,
            "repeat": repeat,
            "completed": completed,
            "ending": (sorted(got_endings) or [0])[0],
            "ending_title": next((ending.get("title") for ending in endings if ending.get("got")), ""),
            "unknown_ending": bool(got_endings - known_endings),
            "got_endings": sorted(got_endings),
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
            if not row["achieved"]:
                continue
            record = events.setdefault(str(row["id"]), {"endings": [], "grants": {}, "last": 0})
            for ending_id in row.get("got_endings") or []:
                if ending_id and ending_id not in record["endings"]:
                    record["endings"].append(ending_id)
                    dirty = True
            if row.get("memory_got") and not record.get("memory"):
                record["memory"] = True
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

    children = _apply_branches(rows)
    rows.sort(key=lambda row: (row.get("realm") or 0, row.get("id") or 0))
    for slot in index.values():
        slot["score"], slot["reasons"] = _score_item(slot)
    catalog = sorted(index.values(), key=lambda row: (-(row.get("score") or 0), str(row.get("name"))))

    top_rows = [row for row in rows if not row.get("branch")]
    stats = {
        "events": len(top_rows),
        "achieved": sum(1 for row in top_rows if row["achieved"]),
        "history": sum(1 for row in top_rows if row.get("history_only")),
        "memory": sum(1 for row in top_rows if row.get("memory_got")),
        "branches": sum(len(items) for items in children.values()),
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
