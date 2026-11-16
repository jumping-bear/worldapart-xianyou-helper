# -*- coding: utf-8 -*-
"""支线：配置表 → 模块快照（自 meta_update.py 原样搬入）。"""
import re

from meta_update import (
    SCHEMA, _call_parts, _clip, _const_args, _const_value, _expr_ints, _int, _plain, _rows,
    _text, build_realms, build_spaces,
)


QUEST_STATE_NAMES = {
    0: "可接取", 1: "进行中", 2: "已完成", 3: "已提交",
    4: "已失败", 5: "已放弃", 6: "待提交",
}


def _quest_call_name(spec):
    """从 Luban 调用/索引表达式里取 玩家.获得奖励 这类名字。"""
    target = spec.get("target")
    if not isinstance(target, list) or not target:
        return ""
    head = target
    if len(head) < 2 or not isinstance(head[1], dict):
        return ""
    node = head[1]
    if head[0] == "variable":
        return str(node.get("name") or "")
    if head[0] == "index":
        owner = node.get("target") or []
        owner_name = ""
        if isinstance(owner, list) and len(owner) > 1 and isinstance(owner[1], dict):
            owner_name = str(owner[1].get("name") or "")
        index = node.get("index") or []
        key = index[1].get("value") if isinstance(index, list) and len(index) > 1 else ""
        return ("%s.%s" % (owner_name, key)) if owner_name else str(key or "")
    return ""


def _quest_call_args(spec, key="arguments"):
    out = []
    for arg in spec.get(key) or []:
        if not isinstance(arg, list) or not arg:
            continue
        if arg[0] == "int":
            out.append(_int(arg[1].get("value")))
        elif arg[0] == "list":
            for element in arg[1].get("elements") or []:
                if isinstance(element, list) and element and element[0] == "int":
                    out.append(_int(element[1].get("value")))
    return out


def _quest_walk_calls(node, out):
    if isinstance(node, dict):
        if "target" in node and "arguments" in node:
            name = _quest_call_name(node)
            if name:
                out.append((name, _quest_call_args(node)))
            for arg in node.get("arguments") or []:
                _quest_walk_calls(arg, out)
        if isinstance(node.get("func"), list):
            head = node["func"]
            name = ""
            if len(head) > 1 and isinstance(head[1], dict):
                spec = head[1]
                if head[0] == "variable":
                    name = str(spec.get("name") or "")
                elif head[0] == "index":
                    owner = spec.get("target") or []
                    owner_name = owner[1].get("name") if isinstance(owner, list) and len(owner) > 1 and isinstance(owner[1], dict) else ""
                    index = spec.get("index") or []
                    key = index[1].get("value") if isinstance(index, list) and len(index) > 1 else ""
                    name = ("%s.%s" % (owner_name, key)) if owner_name else str(key or "")
            if name:
                out.append((name, _quest_call_args(node, "args")))
        for key, value in node.items():
            _quest_walk_calls(value, out)
    elif isinstance(node, list):
        for value in node:
            _quest_walk_calls(value, out)


def _quest_flow_effects(flows, start):
    """跟随流水 nextIds，取出 获得奖励 / 获取物品 / 获得好感度。"""
    seen, queue = set(), [int(start)]
    rewards, items_got, intimacy = [], [], []
    while queue and len(seen) < 80:
        flow_id = queue.pop(0)
        if flow_id in seen:
            continue
        seen.add(flow_id)
        flow = flows.get(flow_id) or {}
        calls = []
        _quest_walk_calls(flow.get("action"), calls)
        for name, args in calls:
            short = name.rsplit(".", 1)[-1]
            if short == "获得奖励" and args:
                rewards.append(args[0])
            elif short == "获取物品" and len(args) >= 2:
                items_got.append((args[0], args[1]))
            elif short == "获得好感度" and len(args) >= 2:
                intimacy.append((args[0], args[1]))
        for nxt in flow.get("nextIds") or []:
            queue.append(_int(nxt))
    return rewards, items_got, intimacy


def _quest_drop_items(drops, drop_id, depth=0):
    out = []
    drop = drops.get(str(_int(drop_id)))
    if not drop or depth > 3:
        return out
    for variant in drop.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        for entry in variant.get("dropList") or []:
            if not isinstance(entry, dict):
                continue
            item_id = _int(entry.get("itemId"))
            if not item_id:
                continue
            low = _int(entry.get("itemCountMin"), 1)
            high = _int(entry.get("itemCountMax"), low)
            out.append((item_id, low, high))
        for child in variant.get("rewardDropList") or []:
            if not isinstance(child, dict):
                continue
            child_id = _int(child.get("rewardDropId"))
            if child_id:
                out.extend(_quest_drop_items(drops, child_id, depth + 1))
    return out


def _quest_highlight(value):
    """取富文本里高亮的地点词，例如 <color=#FFD71E>河望镇·主街</color>。"""
    raw = _text(value)
    match = re.search(r"<color=[^>]+>(.*?)</color>", raw, re.S)
    return _plain(match.group(1)) if match else ""


def _quest_condition(cond, npcs, quest_names=None):
    """把接取条件表达式转成可判定的结构：好感度、城镇声望、境界、修炼阶段等。"""
    if not isinstance(cond, dict):
        return None
    root = _cond_leaf(cond.get("condition"), npcs, quest_names)
    if not root:
        return None
    mode = root.get("mode") or "all"
    checks = root.get("parts") or [root]
    clean = True

    def flatten(group):
        nonlocal clean
        out = []
        for part in group:
            if part.get("parts"):
                if (part.get("mode") or "all") != mode:
                    clean = False
                out.extend(flatten(part["parts"]))
            else:
                out.append(part)
        return out

    flat = flatten(checks) or [root]
    return {"id": _int(cond.get("id")), "alias": str(cond.get("alias") or ""),
            "mode": mode if clean else "unknown", "checks": flat,
            "text": root.get("text") or " 且 ".join(check.get("text") or "" for check in flat)}


def _cond_leaf(node, npcs, quest_names=None):
    """单个条件或“且/或”组合，输出可读文本与可判定字段。"""
    node = _unwrap_expr(node)
    name, index, args = _call_parts(node)
    values = _const_args(args)
    names = quest_names or {}
    if not index and isinstance(node, dict) and node.get("index"):
        value = _const_value(_unwrap_expr(node["index"]))
        if isinstance(value, str):
            index = value
    if not index and isinstance(node, dict) and node.get("index"):
        index = _expr_string(node["index"]) or index
    if name in ("且", "或", "&&", "||", "and", "or") and args:
        parts = [_cond_leaf(item, npcs, names) for item in args]
        parts = [item for item in parts if item]
        if parts:
            mode = "any" if name in ("或", "||", "or") else "all"
            return {"mode": mode, "parts": parts,
                    "text": (" 且 " if mode == "all" else " 或 ").join(item["text"] for item in parts)}
    if name in ("非", "!") and args:
        inner = _cond_leaf(args[0], npcs, names)
        return {"kind": "", "need": 0, "text": "非（%s）" % (inner.get("text") or "条件")}
    if name == "条件" and isinstance(index, str) and values:
        quest_id = _int(values[0])
        label = names.get(quest_id) or ("任务 %s" % quest_id)
        table = {"任务提交": ("quest_done", "完成任务「%s」"),
                 "任务持有": ("quest_hold", "持有任务「%s」"),
                 "任务接取": ("quest_accepted", "已接取「%s」"),
                 "任务目标激活中": ("quest_active", "任务「%s」目标激活中")}
        kind, fmt = table.get(index, ("", index + "「%s」"))
        return {"kind": kind, "quest": quest_id, "need": 1, "text": fmt % label}
    if name == "玩家" and isinstance(index, str) and values:
        if index == "城镇声望至少" and len(values) >= 2:
            return {"kind": "city_rep", "city": _int(values[0]), "need": _int(values[1]),
                    "text": "城镇声望（%s）≥ %d" % (_int(values[0]), _int(values[1]))}
        if index in ("修炼阶段", "境界") and len(values) >= 1:
            return {"kind": "phase" if index == "修炼阶段" else "realm",
                    "need": _int(values[0]), "text": "%s ≥ %d" % (index, _int(values[0]))}
        if index in ("达到修炼层数", "修炼层数") and len(values) >= 1:
            return {"kind": "layer", "need": _int(values[0]),
                    "text": "修炼层数 ≥ %d" % _int(values[0])}
    if name == "大于等于" and args:
        left = _unwrap_expr(args[0])
        left_name, left_index, left_args = _call_parts(left)
        if not left_index and isinstance(left, dict) and left.get("index"):
            left_index = _expr_string(left["index"]) or left_index
        need = _int(values[-1]) if values else 0
        if left_name == "NPC" and left_index == "好感度至少" and len(values) >= 2:
            npc_id = _int(values[0])
            return {"kind": "favor", "npc": npc_id, "need": _int(values[1]),
                    "text": "%s好感度 ≥ %d" % (npcs.get(npc_id) or ("NPC %s" % npc_id),
                                               _int(values[1]))}
        if left_name == "指定NPC" and isinstance(left_index, str):
            left_values = _const_args(left_args) or _expr_ints(left)
            npc_id = _int(left_values[0]) if left_values else 0
            return {"kind": "", "need": need,
                    "text": "%s的%s ≥ %d" % (npcs.get(npc_id) or ("NPC %s" % npc_id),
                                             left_index, need)}
        if left_name == "玩家" and left_index == "城镇声望至少" and len(values) >= 2:
            return {"kind": "city_rep", "city": _int(values[0]), "need": _int(values[1]),
                    "text": "城镇声望（%s）≥ %d" % (_int(values[0]), _int(values[1]))}
        if left_name == "玩家" and isinstance(left_index, str):
            extra = ""
            left_values = _const_args(left_args)
            attr_id = 0
            if left_values and left_index in ("探索属性等级", "属性等级"):
                attr_id = _int(left_values[0])
                extra = "（%s）" % attr_id
            kind = {"修炼阶段": "phase", "境界": "realm", "灵石": "money",
                    "宗门声望": "sect_rep"}.get(left_index, "")
            if attr_id:
                kind = "attr"
            return {"kind": kind, "need": need, "attr": attr_id,
                    "text": "%s%s ≥ %d" % (left_index, extra, need)}
    if name in ("等于", "不等于", "大于", "小于", "小于等于") and args:
        left = _unwrap_expr(args[0])
        left_name, left_index, left_args = _call_parts(left)
        if not left_index and isinstance(left, dict) and left.get("index"):
            left_index = _expr_string(left["index"]) or left_index
        need = _int(values[-1]) if values else 0
        if left_name == "指定NPC" and isinstance(left_index, str):
            left_values = _const_args(left_args) or _expr_ints(left)
            npc_id = _int(left_values[0]) if left_values else 0
            op = {"等于": "=", "不等于": "≠", "大于": ">", "小于": "<", "小于等于": "≤"}[name]
            return {"kind": "", "need": need,
                    "text": "%s的%s %s %d" % (npcs.get(npc_id) or ("NPC %s" % npc_id),
                                              left_index, op, need)}
    if name == "NPC" and index == "好感度至少" and len(values) >= 2:
        npc_id = _int(values[0])
        return {"kind": "favor", "npc": npc_id, "need": _int(values[1]),
                "text": "%s好感度 ≥ %d" % (npcs.get(npc_id) or ("NPC %s" % npc_id),
                                           _int(values[1]))}
    text = index if isinstance(index, str) and index else ""
    nums = [str(value) for value in values if isinstance(value, int)]
    if not text and name:
        text = name
    return {"kind": "", "need": _int(values[-1]) if values else 0,
            "text": (text or "条件") + (" " + " / ".join(nums) if nums else "")}


def _unwrap_expr(node):
    """Luban AST 的类型标签数组 ["int", {...}] → 内部节点。"""
    while isinstance(node, (list, tuple)) and len(node) == 2 and isinstance(node[1], dict):
        node = node[1]
    return node


def _expr_string(node):
    """从字符串/变量节点取名称。"""
    node = _unwrap_expr(node)
    if isinstance(node, dict):
        for key in ("value", "name"):
            if isinstance(node.get(key), str):
                return node[key]
    return node if isinstance(node, str) else ""


def _quest_gate(node):
    """触发表达式：任务提交 / 进入场景 / NPC 好感度 / 修炼阶段。"""
    if isinstance(node, (list, tuple)) and len(node) == 2 and isinstance(node[1], dict):
        node = node[1]
    name, index, args = _call_parts(node)
    event = index or ""
    values = [_int(value) for value in _expr_ints(node)]
    gate = {"event": event, "quests": [], "space": 0, "npc": 0, "favor": 0, "layer": 0}
    if event == "任务提交":
        gate["quests"] = [value for value in values if value > 1000]
    elif event == "进入场景":
        gate["space"] = values[0] if values else 0
    elif event == "NPC好感度达到":
        gate["npc"] = values[0] if values else 0
        gate["favor"] = values[1] if len(values) > 1 else 0
    elif event == "修炼阶段达到":
        gate["layer"] = values[0] if values else 0
    return gate


def _flow_accept_entries(node, require=0, out=None):
    """流水里按条件接取任务：返回 [{quest, require}]，require 是决定该分支的已提交任务。"""
    if out is None:
        out = []
    if isinstance(node, (list, tuple)):
        if len(node) == 2 and isinstance(node[0], str) and isinstance(node[1], dict):
            tag, payload = node
            if tag == "conditional":
                leaf = _cond_leaf(payload.get("condition"), {}, {})
                req = _int(leaf.get("quest")) if leaf and leaf.get("kind") == "quest_done" else 0
                for key, value in payload.items():
                    if key == "condition":
                        continue
                    _flow_accept_entries(value, req if key == "trueExpression" else require, out)
                return out
            return _flow_accept_entries(payload, require, out)
        for item in node:
            _flow_accept_entries(item, require, out)
        return out
    if not isinstance(node, dict):
        return out
    name = ""
    if "target" in node and "arguments" in node:
        name = _quest_call_name(node)
        args = _quest_call_args(node)
    elif isinstance(node.get("func"), list):
        head = node["func"]
        spec = head[1] if len(head) > 1 and isinstance(head[1], dict) else {}
        if head[0] == "variable":
            name = str(spec.get("name") or "")
        elif head[0] == "index":
            owner = spec.get("target") or []
            owner_name = (owner[1].get("name") if isinstance(owner, list) and len(owner) > 1
                          and isinstance(owner[1], dict) else "")
            index = spec.get("index") or []
            key = index[1].get("value") if isinstance(index, list) and len(index) > 1 else ""
            name = ("%s.%s" % (owner_name, key)) if owner_name else str(key or "")
        args = _quest_call_args(node, "args")
    else:
        args = []
    if name.rsplit(".", 1)[-1] == "接取任务" and args and args[0]:
        out.append({"quest": _int(args[0]), "require": require})
    for key, value in node.items():
        if key != "condition":
            _flow_accept_entries(value, require, out)
    return out


def build_quests(tables):
    """支线任务只读元数据：任务、奖励、前置链路、地点与互斥分支。"""
    quest_table = tables["tbquest"]
    quest_rows = quest_table.get("rows") if isinstance(quest_table, dict) else quest_table
    all_rows = [row for row in _rows(quest_rows) if isinstance(row, dict) and row.get("id") is not None]

    type_names = {}
    for row in _rows(tables.get("tbquesttype")):
        if isinstance(row, dict) and row.get("id") is not None:
            type_names[_int(row["id"])] = _text(row.get("text")) or ("类型 %s" % row["id"])

    side = []
    for row in all_rows:
        quest_type = _int(row.get("type"))
        label = type_names.get(quest_type) or ""
        if quest_type == 2 or "支线" in label:
            side.append(row)
    if not side:
        raise ValueError("支线任务配置为空")
    quest_names = {_int(row["id"]): (_plain(row.get("name")) or ("支线 %s" % row["id"]))
                   for row in side}

    drops = {str(_int(r.get("id"))): r for r in _rows(tables["tbrewarddrop"])
             if isinstance(r, dict) and r.get("id") is not None}
    flows = {_int(r.get("id")): r for r in _rows(tables["tbgameactionflow"])
             if isinstance(r, dict) and r.get("id") is not None}
    npcs = {}
    for row in _rows(tables["tbnpcbasecfg"]):
        if isinstance(row, dict) and row.get("id") is not None:
            npcs[_int(row["id"])] = (_text(row.get("npcName")) or
                                     _text(row.get("npcTitle")) or ("NPC %s" % row["id"]))
    items = {}
    item_types = {}
    for row in _rows(tables.get("tbitemtype")):
        if isinstance(row, dict) and row.get("id") is not None:
            item_types[str(_int(row["id"]))] = _text(row.get("typeName")) or _text(row.get("name")) or ""
    for row in _rows(tables["tbitem"]):
        if isinstance(row, dict) and row.get("id") is not None:
            items[_int(row["id"])] = {
                "name": _text(row.get("itemName")) or ("物品 %s" % row["id"]),
                "quality": _int(row.get("quality")),
                "type": item_types.get(str(_int(row.get("itemType"))), ""),
                "price": _int(row.get("price")),
                "desc": _plain(row.get("itemDesc")),
            }
    spaces = build_spaces(tables)
    realms = build_realms(tables)
    place_names = sorted(((info.get("name") or "", space_id) for space_id, info in spaces.items()
                          if len(info.get("name") or "") >= 2), key=lambda pair: -len(pair[0]))
    # 剧情型委托人不在存档场景列表里，用人物小传里的地名推断常驻地。
    npc_homes = {}
    for row in _rows(tables["tbnpcbasecfg"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        plot = _plain(row.get("propPlot"))
        if not plot:
            continue
        for name, space_id in place_names:
            if name in plot:
                npc_homes[str(_int(row["id"]))] = (spaces.get(str(space_id)) or {}).get("name") or name
                break

    conds = {}
    for row in _rows(tables.get("tbconditionexpr")):
        if isinstance(row, dict) and row.get("id") is not None:
            conds[_int(row["id"])] = row
    acq_dialogues = {}
    for row in _rows(tables.get("tbdialogue")):
        if not isinstance(row, dict):
            continue
        dialogue_id, dialogue_npc = _int(row.get("id")), _int(row.get("npcId"))
        for option in row.get("options") or []:
            if not isinstance(option, dict):
                continue
            calls = []
            _quest_walk_calls(option.get("optionExpr"), calls)
            for name, args in calls:
                if name.rsplit(".", 1)[-1] != "接取任务" or not args:
                    continue
                child_id = _int(args[0])
                if child_id:
                    acq_dialogues.setdefault(child_id, {"dialogue": dialogue_id,
                                                        "npc": dialogue_npc})

    quests = {}
    for row in side:
        quest_id = _int(row["id"])
        objectives = [o for o in (row.get("objectives") or []) if isinstance(o, dict)]
        reward_slots = {}

        def add_reward(item_id, name, quality, low, high, source):
            key = str(item_id) if item_id else ("n:" + name)
            slot = reward_slots.get(key)
            if slot is None:
                slot = {"item": item_id, "name": name, "quality": quality,
                        "min": 0, "max": 0, "sources": []}
                reward_slots[key] = slot
            slot["min"] += max(0, _int(low))
            slot["max"] += max(0, _int(high))
            if source not in slot["sources"]:
                slot["sources"].append(source)

        def add_drop(drop_id, source):
            for item_id, low, high in _quest_drop_items(drops, drop_id):
                info = items.get(item_id) or {}
                add_reward(item_id, info.get("name") or ("物品 %s" % item_id),
                           _int(info.get("quality")), low, high, source)

        if row.get("rewardId"):
            add_drop(row["rewardId"], "提交")
        for objective in objectives:
            if objective.get("rewardId"):
                add_drop(objective["rewardId"], "阶段")

        flow_rewards, flow_items, flow_intimacy = [], [], []
        for field in ("questSubmitFlowId", "questAcqFlowId"):
            if row.get(field) is None:
                continue
            found = _quest_flow_effects(flows, row[field])
            flow_rewards.extend(found[0])
            flow_items.extend(found[1])
            flow_intimacy.extend(found[2])
        for drop_id in flow_rewards:
            add_drop(drop_id, "剧情")
        for item_id, count in flow_items:
            info = items.get(item_id) or {}
            add_reward(item_id, info.get("name") or ("物品 %s" % item_id),
                       _int(info.get("quality")), count, count, "剧情")
        for npc_id, amount in flow_intimacy:
            if amount > 0:
                add_reward(0, "%s亲密度" % npcs.get(npc_id, "NPC %s" % npc_id),
                           1, amount, amount, "好感")

        rewards = list(reward_slots.values())
        rewards.sort(key=lambda x: (-_int(x.get("quality")), -_int(x.get("max")), x.get("name") or ""))
        for reward in rewards:
            info = items.get(_int(reward.get("item"))) or {}
            reward["type"] = info.get("type") or ""
            reward["price"] = _int(info.get("price"))
            reward["desc"] = info.get("desc") or ""

        prev_id = next((value for value in _expr_ints(row.get("triggerExpr")) if value), 0)
        giver_id = _int(row.get("acqNpcID"))
        if not giver_id:
            experience = row.get("experience") or {}
            if isinstance(experience, dict):
                giver_id = _int(experience.get("npcId"))

        desc = _plain(row.get("description"))
        objective_texts = [_plain(o.get("description")) for o in objectives if _plain(o.get("description"))]
        blob = "\n".join([desc] + objective_texts)
        location = None
        for name, space_id in place_names:
            if name and name in blob:
                info = spaces.get(str(space_id)) or {}
                location = {"space": _int(space_id), "name": info.get("name") or name,
                            "path": info.get("path") or [name], "region": info.get("region") or name,
                            "realm": _int(info.get("realm_id")), "via": "text", "conf": "inferred"}
                break
        spot = ""
        for source_text in objective_texts + [desc]:
            spot = _quest_highlight(source_text)
            if spot:
                break
        if location and spot and spot == location.get("name"):
            spot = ""

        track_ids = {_int(o.get("trackId")) for o in objectives if _int(o.get("trackId"))}
        cond_row = conds.get(_int(row.get("acqCondition")))
        acq_cond = _quest_condition(cond_row, npcs, quest_names) if cond_row else None
        gate = _quest_gate(row.get("triggerExpr"))
        if not (gate["quests"] or gate["space"] or gate["npc"] or gate["layer"]
                or gate["event"] == "接取条件满足"):
            gate = None
        quests[quest_id] = {
            "id": quest_id,
            "name": _plain(row.get("name")) or ("支线 %s" % quest_id),
            "desc": _clip(desc, 240),
            "group": _text(row.get("taskGroup")),
            "chain": _int(row.get("quest_chain_id")),
            "type": _int(row.get("type")),
            "type_name": type_names.get(_int(row.get("type"))) or "支线",
            "acq_source": _int(row.get("acqSource")),
            "hidden": bool(row.get("hidden")),
            "one_off": bool(row.get("oneOff")),
            "can_abandon": bool(row.get("canAbandon")),
            "priority": _int(row.get("priority")),
            "realm_ids": [_int(x) for x in (row.get("realm_id_list") or []) if _int(x)],
            "giver": {"id": giver_id, "name": npcs.get(giver_id, "")} if giver_id else None,
            "objectives": [{"text": _clip(_plain(o.get("description")), 180),
                            "npc": npcs.get(_int(o.get("submitNpcID")), "")}
                           for o in objectives if _plain(o.get("description"))][:8],
            "location": location,
            "spot": spot,
            "prev": prev_id,
            "next": [],
            "chain_id": "", "chain_name": "", "chain_index": 0,
            "branch_key": "",
            "track_ids": sorted(track_ids),
            "branch": False,
            "branch_with": [],
            "rewards": rewards,
            "reward_stone": sum(_int(x.get("max")) for x in rewards if _int(x.get("item")) == 50000),
            "acq_cond": acq_cond,
            "gate": gate,
            "acq_branch_of": 0,
            "acq_branch_siblings": [],
            "prev_options": [],
            "acq_dialogue": acq_dialogues.get(quest_id),
            "acq_flows": [],
        }

    # 只有指向本模块支线的前置才算数，避免把 NPC id 当成前置任务。
    for quest in quests.values():
        if quest["prev"] and quest["prev"] not in quests:
            quest["prev"] = 0

    # 提交流水里的“接取任务”补全后续环，例如选完配菜后自动接取下一段剧情。
    raw_by_id = {_int(row["id"]): row for row in side}
    for quest_id, quest in quests.items():
        flow_id = raw_by_id.get(quest_id, {}).get("questSubmitFlowId")
        if flow_id is None:
            continue
        calls = []
        _quest_walk_calls((flows.get(_int(flow_id)) or {}).get("action"), calls)
        for name, args in calls:
            if name.rsplit(".", 1)[-1] != "接取任务" or not args:
                continue
            child_id = _int(args[0])
            if child_id in quests and child_id != quest_id and not quests[child_id]["prev"]:
                quests[child_id]["prev"] = quest_id

    # 对话选项里的“接取任务”补全分支环，例如 70100 的选配菜、70110 的饮酒选择。
    for row in _rows(tables.get("tbdialogue")):
        if not isinstance(row, dict):
            continue
        parent_id = _int(row.get("id"))
        if parent_id not in quests:
            continue
        for option in row.get("options") or []:
            if not isinstance(option, dict):
                continue
            calls = []
            _quest_walk_calls(option.get("optionExpr"), calls)
            for name, args in calls:
                if name.rsplit(".", 1)[-1] != "接取任务" or not args:
                    continue
                child_id = _int(args[0])
                if child_id in quests and child_id != parent_id and not quests[child_id]["prev"]:
                    quests[child_id]["prev"] = parent_id

    # 流水里的条件接取：按已提交的剧情选项决定接哪一环，等价于剧情分支。
    flow_owner, flow_parents = {}, {}
    for row in side:
        for key in ("questAcqFlowId", "questSubmitFlowId"):
            flow_id = _int(row.get(key))
            if flow_id:
                flow_owner.setdefault(flow_id, _int(row["id"]))
    for flow_id, flow in flows.items():
        for next_id in flow.get("nextIds") or []:
            next_id = _int(next_id)
            if next_id:
                flow_parents.setdefault(next_id, [])
                if _int(flow_id) not in flow_parents[next_id]:
                    flow_parents[next_id].append(_int(flow_id))
    for flow_id, flow in flows.items():
        entries = [entry for entry in _flow_accept_entries(flow.get("action"))
                   if entry["quest"] in quests]
        group = []
        for entry in entries:
            if entry["quest"] not in group:
                group.append(entry["quest"])
        if not group:
            continue
        owners = []
        for parent_id in flow_parents.get(_int(flow_id)) or []:
            owner = flow_owner.get(parent_id) or (parent_id if parent_id in quests else 0)
            if owner and owner not in owners:
                owners.append(owner)
        fallback = owners[0] if owners else 0
        for entry in entries:
            child_id = entry["quest"]
            if len(group) > 1:
                quests[child_id]["acq_branch_siblings"] = [x for x in group if x != child_id]
            require = entry["require"]
            if require and require in quests:
                quests[child_id]["acq_branch_of"] = require
            target = fallback or (require if require in quests else 0)
            if target and not quests[child_id]["prev"]:
                quests[child_id]["prev"] = target
            if len(owners) > 1:
                quests[child_id]["prev_options"] = owners

    children = {}
    for quest_id, quest in quests.items():
        if quest["prev"]:
            children.setdefault(quest["prev"], []).append(quest_id)
    for quest_id, quest in quests.items():
        quest["next"] = sorted(children.get(quest_id, []))

    # 同名同文案的双版本任务：通常是两条主线路线各自的同一段剧情，只能走其中一条。
    variant_groups, variant_of = {}, {}
    for quest_id, quest in quests.items():
        if quest["desc"]:
            variant_groups.setdefault((quest["name"], quest["desc"]), []).append(quest_id)
    for (name, _), ids in variant_groups.items():
        if len(ids) > 1:
            for quest_id in ids:
                variant_of[quest_id] = name

    # 剧情链：优先 quest_chain_id，其次 taskGroup，最后沿前置回溯到链首。
    def chain_root(quest_id):
        seen, current = set(), quest_id
        while quests[current]["prev"] in quests and current not in seen:
            seen.add(current)
            current = quests[current]["prev"]
        return current

    for quest_id, quest in quests.items():
        if quest_id in variant_of:
            quest["chain_id"] = "v:%s" % variant_of[quest_id]
        elif quest["chain"]:
            quest["chain_id"] = "c%d" % quest["chain"]
        elif quest["group"]:
            quest["chain_id"] = "g:" + quest["group"]
        else:
            quest["chain_id"] = "r%d" % chain_root(quest_id)

    chain_members = {}
    for quest_id, quest in quests.items():
        chain_members.setdefault(quest["chain_id"], []).append(quest_id)

    chains = []
    for chain_id, ids in chain_members.items():
        members = set(ids)
        first = quests[min(ids)]
        if chain_id.startswith("v:"):
            name = "%s（同名路线）" % first["name"]
        elif first["group"]:
            name = first["group"]
        elif len(ids) == 1:
            name = first["name"]
        else:
            givers = {quests[quest_id]["giver"]["name"] for quest_id in ids
                      if quests[quest_id].get("giver") and quests[quest_id]["giver"].get("name")}
            if len(givers) == 1:
                name = "%s线" % next(iter(givers))
            else:
                name = "%s…线" % first["name"]
        depth, queue = {}, [quest_id for quest_id in ids if quests[quest_id]["prev"] not in members]
        if not queue:
            queue = [min(ids)]
        for quest_id in queue:
            depth[quest_id] = 1
        changed = True
        while changed:
            changed = False
            for quest_id in ids:
                prev_id = quests[quest_id]["prev"]
                if prev_id in members and prev_id in depth and quest_id not in depth:
                    depth[quest_id] = depth[prev_id] + 1
                    changed = True
        for quest_id in ids:
            quests[quest_id]["chain_index"] = 1 if chain_id.startswith("v:") else depth.get(quest_id, 1)
            quests[quest_id]["chain_name"] = name
        chains.append({"id": chain_id, "name": name, "size": len(ids),
                       "first": min(ids), "group": first["group"]})

    used_names = {}
    for chain in chains:
        name = chain["name"]
        if name in used_names:
            name = "%s·%s" % (name, quests[chain["first"]]["name"])
        used_names[name] = 1
        chain["name"] = name
        for quest_id in chain_members[chain["id"]]:
            quests[quest_id]["chain_name"] = name

    # 互斥分支：同一前置任务分出，或同一段对话的多个选项分别接取不同任务。
    branches = {}

    def mark_branch(quest_id, key, kind, prev_id=0):
        quest = quests.get(quest_id)
        if not quest:
            return
        quest["branch"] = True
        if not quest["branch_key"]:
            quest["branch_key"] = key
        slot = branches.setdefault(key, {"key": key, "kind": kind, "prev": _int(prev_id),
                                         "quests": [], "names": []})
        if quest_id not in slot["quests"]:
            slot["quests"].append(quest_id)
            slot["names"].append(quest["name"])

    prev_groups = {}
    for quest_id, quest in quests.items():
        if quest["prev"]:
            prev_groups.setdefault((quest["chain_id"], quest["prev"]), []).append(quest_id)
    for (chain_id, prev_id), ids in prev_groups.items():
        if len(ids) > 1:
            key = "p:%s:%d" % (chain_id, prev_id)
            for quest_id in ids:
                mark_branch(quest_id, key, "任务分支", prev_id)
    for row in _rows(tables.get("tbdialogue")):
        if not isinstance(row, dict):
            continue
        picked = []
        for option in row.get("options") or []:
            if not isinstance(option, dict):
                continue
            calls = []
            _quest_walk_calls(option.get("optionExpr"), calls)
            for name, args in calls:
                if name.rsplit(".", 1)[-1] == "接取任务" and args:
                    quest_id = _int(args[0])
                    if quest_id in quests and quest_id not in picked:
                        picked.append(quest_id)
        if len(picked) > 1:
            key = "d:%d:%d" % (_int(row.get("id")), _int(row.get("subId")))
            for quest_id in picked:
                mark_branch(quest_id, key, "对话分支")

    for (name, _), ids in variant_groups.items():
        if len(ids) > 1:
            key = "v:%s" % name
            for quest_id in ids:
                mark_branch(quest_id, key, "同名路线")

    for quest_id, quest in quests.items():
        if quest["branch_key"]:
            slot = branches.get(quest["branch_key"]) or {}
            quest["branch_with"] = sorted(name for name in slot.get("names") or []
                                          if name != quest["name"])

    phases = {}
    for row in _rows(tables["tbcultivaterealm"]):
        if isinstance(row, dict):
            realm_id = _int(row.get("id"))
            for phase in row.get("phases") or []:
                phases[str(_int(phase))] = realm_id

    # 链内按环数排序，链按首任务 id 排序，保证 UI 稳定。
    chain_order = {chain["id"]: index for index, chain in enumerate(
        sorted(chains, key=lambda item: item["first"]))}
    result = sorted(quests.values(), key=lambda q: (chain_order.get(q["chain_id"], 0),
                                                   q["chain_index"], q["id"]))
    groups = {}
    for quest in result:
        key = quest["group"] or "未分组"
        slot = groups.setdefault(key, {"name": key, "total": 0, "with_rewards": 0, "stones": 0})
        slot["total"] += 1
        if quest["rewards"]:
            slot["with_rewards"] += 1
        slot["stones"] += quest["reward_stone"]

    # 同一段剧情流程接取的多个任务：多半是同源分支，只有一个会真正进入任务栏。
    flow_accepts, quest_flows = {}, {}
    for flow_id, flow in flows.items():
        entries = _flow_accept_entries(flow.get("action"))
        picked = []
        for entry in entries:
            child_id = entry["quest"]
            if child_id in quests and child_id not in picked:
                picked.append(child_id)
        if not picked:
            continue
        quest_flows.setdefault(flow_id, picked)
        for child_id in picked:
            quests[child_id]["acq_flows"] = sorted(set(quests[child_id].get("acq_flows") or []) | {flow_id})
        # 带“已提交某任务”的条件接取已按分支处理，不再算是同源跳过。
        conditional = any(entry["require"] for entry in entries if entry["quest"] in quests)
        if len(picked) > 1 and not conditional:
            flow_accepts[str(flow_id)] = picked

    stats = {
        "quests": len(result),
        "with_rewards": sum(1 for quest in result if quest["rewards"]),
        "stones": sum(quest["reward_stone"] for quest in result),
        "groups": len(groups),
        "chains": len([chain for chain in chains if chain["size"] > 1]),
        "branches": len([branch for branch in branches.values() if len(branch["quests"]) > 1]),
        "hidden": sum(1 for quest in result if quest["hidden"]),
        "branch": sum(1 for quest in result if quest["branch"]),
    }
    return {"schema": SCHEMA, "quests": result, "groups": sorted(groups.values(), key=lambda g: g["name"]),
            "chains": sorted(chains, key=lambda item: chain_order.get(item["id"], 0)),
            "branches": sorted(branches.values(), key=lambda item: item["key"]),
            "flow_accepts": flow_accepts,
            "space_names": {str(space_id): (info.get("name") or "")
                            for space_id, info in spaces.items()},
            "npc_homes": npc_homes,
            "npc_names": {str(key): value for key, value in npcs.items()},
            "realms": realms, "phases": phases,
            "states": {str(k): v for k, v in QUEST_STATE_NAMES.items()},
            "types": {str(k): v for k, v in type_names.items()}, "stats": stats}


# 插件统一入口
build = build_quests
