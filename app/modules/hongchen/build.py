# -*- coding: utf-8 -*-
"""红尘：配置表 -> 模块快照。

只依赖 meta_update 的公共解析函数；不 import 其它模块。
游戏新增红尘任务（type=5 数据行）后重新导出快照即可，不需要改代码。
"""
import re

from meta_update import (
    SCHEMA, _call_parts, _clip, _const_args, _expr_ints, _int,
    _plain, _rows, _text,
)


HONGCHEN_STATE_NAMES = {
    0: "可接取", 1: "进行中", 2: "已完成", 3: "已提交",
    4: "已失败", 5: "已放弃", 6: "待提交",
}
DONE_STATES = (2, 3)
DOING_STATES = (1, 6)

# 条件 alias 里的属性英文/pinyin 片段 -> 中文名；仅用于把语义标签翻译给玩家。
# 数值来自数据行（alias 后缀 / greyText / 表达式树），新增属性只需补一个词。
_ATTR_TOKEN = {
    "LINGJI": "灵机", "SHENSHI": "神识", "PHYSIQUE": "体魄", "TIPO": "体魄",
    "DEBATE": "辩道", "BIANDAO": "辩道", "YISHU": "医术", "YILIAO": "医术",
    "INTIMACY": "好感", "FAVOR": "好感", "QINGYI": "情义",
    "LINGSHI": "灵石", "MONEY": "灵石", "GOLD": "灵石",
    "REPUTE": "声望", "SECTREP": "宗门声望", "CITYREP": "城镇声望",
    "REALM": "境界", "LAYER": "修炼阶段", "POWER": "战力",
}


def _table_rows(table):
    """tbquest 在游戏包里是 {rows, overrides}，其它表多为纯 list。"""
    if isinstance(table, dict) and isinstance(table.get("rows"), list):
        return table["rows"]
    return _rows(table)


def _unwrap(node):
    while isinstance(node, (list, tuple)) and len(node) == 2 and isinstance(node[1], dict):
        node = node[1]
    return node


def _expr_string(node):
    node = _unwrap(node)
    if isinstance(node, dict):
        for key in ("value", "name"):
            if isinstance(node.get(key), str):
                return node[key]
    return node if isinstance(node, str) else ""


def _args_of(args):
    out = []
    for arg in args or []:
        if isinstance(arg, (list, tuple)) and len(arg) == 2 and isinstance(arg[0], str):
            if arg[0] == "int" and isinstance(arg[1], dict):
                out.append(_int(arg[1].get("value")))
            elif arg[0] == "list" and isinstance(arg[1], dict):
                for item in arg[1].get("elements") or []:
                    if isinstance(item, (list, tuple)) and len(item) == 2 and item[0] == "int":
                        out.append(_int(item[1].get("value")))
        elif isinstance(arg, int):
            out.append(arg)
    return out


def _call_label(node):
    """拼接“玩家.接取任务”这类完整调用名，便于按末段识别。"""
    name, index, _ = _call_parts(node)
    if index and name:
        return "%s.%s" % (name, index)
    return str(index or name or "")


def _walk_calls(node, out):
    """递归收集 Luban 调用：[(名字, [参数...])]，用于找“接取任务”。"""
    if isinstance(node, dict):
        if "target" in node and "arguments" in node:
            name = _call_label(node)
            if name:
                out.append((name, _args_of(node.get("arguments"))))
            for arg in node.get("arguments") or []:
                _walk_calls(arg, out)
        if isinstance(node.get("func"), list):
            name = _call_label(node)
            if name:
                out.append((name, _args_of(node.get("args"))))
        for value in node.values():
            _walk_calls(value, out)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _walk_calls(value, out)
    return out


def _accepts(node):
    out = []
    for name, args in _walk_calls(node, []):
        if name.rsplit(".", 1)[-1] == "接取任务" and args and args[0]:
            out.append(_int(args[0]))
    return out


def _expr_gate(node, npcs):
    """递归翻译条件表达式（alias 缺失或无法识别时兜底）。"""
    node = _unwrap(node)
    name, index, args = _call_parts(node)
    if not isinstance(index, str):
        index = _expr_string(node.get("index")) if isinstance(node, dict) else ""
    values = [v for v in _const_args(args) if isinstance(v, (int, float, str))]
    nums = [int(v) for v in values if isinstance(v, (int, float))]
    if not name:
        return None
    if name in ("且", "或", "&&", "||") and args:
        parts = [_expr_gate(item, npcs) for item in args]
        parts = [p for p in parts if p]
        if not parts:
            return None
        joiner = " 或 " if name in ("或", "||") else " 且 "
        return {"kind": "", "need": 0, "text": joiner.join(p["text"] for p in parts),
                "parts": parts}
    if name in ("非", "!", "not") and args:
        inner = _expr_gate(args[0], npcs)
        return {"kind": "", "need": 0,
                "text": "非（%s）" % (inner["text"] if inner else "条件")}
    if name in ("大于等于", "GE", ">=") and args and nums:
        left = _unwrap(args[0])
        lname, lindex, largs = _call_parts(left)
        if not isinstance(lindex, str):
            lindex = _expr_string(left.get("index")) if isinstance(left, dict) else ""
        need = nums[-1]
        if lname == "NPC" and lindex == "好感度至少" and len(nums) >= 2:
            npc_id = nums[0]
            return {"kind": "favor", "npc": npc_id, "need": nums[-1],
                    "text": "%s好感≥%d" % (npcs.get(npc_id, "NPC %s" % npc_id), nums[-1])}
        if lname == "玩家" and lindex == "灵石":
            return {"kind": "money", "need": need, "text": "灵石≥%d" % need}
        if lname == "玩家" and isinstance(lindex, str):
            return {"kind": "attr", "attr_name": lindex, "need": need,
                    "text": "%s≥%d" % (lindex, need)}
        if isinstance(lindex, str) and lindex:
            return {"kind": "", "need": need, "text": "%s≥%d" % (lindex, need)}
        return {"kind": "", "need": need, "text": "≥%d" % need}
    if name == "NPC" and index == "好感度至少" and len(nums) >= 2:
        return {"kind": "favor", "npc": nums[0], "need": nums[1],
                "text": "%s好感≥%d" % (npcs.get(nums[0], "NPC %s" % nums[0]), nums[1])}
    if name in ("等于", "EQ", "==") and nums:
        return {"kind": "", "need": nums[-1], "text": "＝%d" % nums[-1]}
    text = index or name
    return {"kind": "", "need": nums[-1] if nums else 0,
            "text": str(text) + ((" " + "/".join(str(x) for x in nums)) if nums else "")}


def _gate_from_condition(cond_row, npcs, grey_text=""):
    """把 optionCondition 引用的条件行翻译成人话门槛 + 可判定结构。"""
    gate = {"alias": "", "text": "", "alias_text": "", "kind": "", "need": 0,
            "npc": 0, "attr_name": "", "source": ""}
    if not isinstance(cond_row, dict):
        gate["text"] = _plain(grey_text) or "附加条件"
        return gate
    alias = str(cond_row.get("alias") or "")
    gate["alias"] = alias
    upper = alias.upper()
    text, kind, need, attr_name = "", "", 0, ""

    m = re.search(r"SIDE_ZHUJI_(\d+)_O(\d+)", upper)
    if m:
        text, kind, need = "需完成「%s」相关剧情（选项 %s）" % (m.group(1), m.group(2)), "quest_option", int(m.group(1))
    elif re.search(r"INTIMACY|FAVOR", upper) and (m := re.search(r"(\d+)\s*$", upper)):
        text, kind, need = "好感≥%s" % m.group(1), "favor", int(m.group(1))
    elif "COST" in upper and (m := re.search(r"(\d+)\s*$", upper)):
        text, kind, need = "花费灵石≥%s" % m.group(1), "money", int(m.group(1))
    elif "LINGSHI" in upper and (m := re.search(r"(\d+)\s*$", upper)):
        text, kind, need = "灵石≥%s" % m.group(1), "money", int(m.group(1))
    else:
        m = re.search(r"_([A-Z]+)_(GE|LT|EQ|GT)_(\d+)\s*$", upper)
        if m:
            token, op, digits = m.group(1), m.group(2), int(m.group(3))
            attr_name = _ATTR_TOKEN.get(token, token)
            symbol = {"GE": "≥", "GT": ">", "LT": "＜", "EQ": "＝"}[op]
            text, kind, need = "%s%s%d" % (attr_name, symbol, digits), "attr", digits
        elif (m := re.search(r"_(GE|LT|EQ)_(\d+)\s*$", upper)):
            symbol = {"GE": "≥", "LT": "＜", "EQ": "＝"}[m.group(1)]
            text, need = "%s%d" % (symbol, int(m.group(2))), int(m.group(2))

    if not text:
        parsed = _expr_gate(cond_row.get("condition"), npcs)
        if parsed:
            text = parsed.get("text") or ""
            kind, need = parsed.get("kind") or "", _int(parsed.get("need"))
            attr_name = parsed.get("attr_name") or ""
    grey = _plain(grey_text)
    display = grey if grey else text
    gate.update({"text": display or "附加条件", "alias_text": text, "kind": kind,
                 "need": need, "attr_name": attr_name})
    return gate


def _character_of_group(group):
    m = re.search(r"女主\s*[-－—~～]\s*(.+?)\s*支线", str(group or ""))
    if m:
        return m.group(1).strip()
    text = re.sub(r"^(女主|红线|情缘)\s*[-－—]?\s*", "", str(group or ""))
    return re.sub(r"支线\s*$", "", text).strip() or str(group or "未分组")


def _line_npc(group, quests, npcs):
    """按角色线数据推断女主 NPC：引用次数 + 名字匹配，避免写死 id。"""
    character = _character_of_group(group)
    refs = {}
    for quest in quests:
        ids = []
        if quest.get("acqNpcID"):
            ids.append(quest["acqNpcID"])
        exp = quest.get("experience") or {}
        if isinstance(exp, dict) and exp.get("npcId"):
            ids.append(exp["npcId"])
        for obj in quest.get("objectives") or []:
            if isinstance(obj, dict) and obj.get("submitNpcID"):
                ids.append(obj["submitNpcID"])
        for nid in set(ids):
            refs[nid] = refs.get(nid, 0) + 1
    best, best_score = 0, -1
    for nid, count in refs.items():
        name = npcs.get(nid, {}).get("name") or ""
        score = count + (100 if (character and character in name) else 0)
        if score > best_score:
            best, best_score = nid, score
    return best, character


def build_hongchen(tables):
    """红尘任务只读元数据：6 条角色线 + 任务树 + 选项门槛。"""
    all_rows = [r for r in _table_rows(tables.get("tbquest"))
                if isinstance(r, dict) and r.get("id") is not None]

    # 类型从 tbquesttype 动态识别“红尘”，不写死 type==5。
    type_names, hongchen_types = {}, set()
    for row in _rows(tables.get("tbquesttype")):
        if isinstance(row, dict) and row.get("id") is not None:
            label = _text(row.get("text")) or ("类型 %s" % row["id"])
            type_names[_int(row["id"])] = label
            if "红尘" in label:
                hongchen_types.add(_int(row["id"]))
    if not hongchen_types:
        hongchen_types = {5}
    rows = [r for r in all_rows if _int(r.get("type")) in hongchen_types]
    if not rows:
        raise ValueError("红尘任务配置为空")
    hc_ids = {_int(r["id"]) for r in rows}

    npcs = {}
    for row in _rows(tables.get("tbnpcbasecfg")):
        if isinstance(row, dict) and row.get("id") is not None:
            npcs[_int(row["id"])] = {
                "name": _text(row.get("npcName")) or _text(row.get("npcTitle")) or ("NPC %s" % row["id"]),
                "portrait": _text(row.get("portraitIcon")) or "",
            }
    conds = {}
    for row in _rows(tables.get("tbconditionexpr")):
        if isinstance(row, dict) and row.get("id") is not None:
            conds[_int(row["id"])] = row
    attr_names = {}
    for row in _rows(tables.get("tbinteractattribute")):
        if isinstance(row, dict) and row.get("id") is not None:
            attr_names[str(_int(row["id"]))] = _text(row.get("name"))

    # 对话按 id 汇总（同一段剧情分散在多个 subId 行）。
    options_by_dialogue, acq_gates, dialogue_targets = {}, {}, {}
    for row in _rows(tables.get("tbdialogue")):
        if not isinstance(row, dict):
            continue
        did = _int(row.get("id"))
        for option in row.get("options") or []:
            if not isinstance(option, dict):
                continue
            targets = [t for t in _accepts(option.get("optionExpr")) if t in hc_ids]
            gate = None
            if option.get("optionCondition"):
                gate = _gate_from_condition(
                    conds.get(_int(option["optionCondition"])), npcs,
                    _text(option.get("optionGreyText")))
                gate["source"] = "optionCondition"
            if did in hc_ids:
                options_by_dialogue.setdefault(did, []).append({
                    "text": _text(option.get("optionText")) or "选择",
                    "to": targets, "gate": gate,
                })
                slot = dialogue_targets.setdefault(did, [])
                for target in targets:
                    if target not in slot:
                        slot.append(target)
            for target in targets:
                if gate:
                    slot = acq_gates.setdefault(target, [])
                    if gate not in slot:
                        slot.append(gate)

    # 流水接取目标：分支汇合点（例：诚恳道谢/嘴硬反驳 -> 妖风突袭）。
    flow_targets = {}
    for row in _rows(tables.get("tbgameactionflow")):
        if isinstance(row, dict) and row.get("id") is not None:
            targets = [t for t in _accepts(row.get("action")) if t in hc_ids]
            if targets:
                flow_targets[_int(row["id"])] = targets

    grouped = {}
    for row in rows:
        grouped.setdefault(_text(row.get("taskGroup")) or "未分组", []).append(row)

    all_quests, lines = [], []
    line_colors = ["#c9866b", "#9a7bb0", "#b08a5a", "#6f9fa0", "#c2727f", "#7f95c0"]
    for group_index, (group, group_rows) in enumerate(sorted(grouped.items())):
        npc_id, character = _line_npc(group, group_rows, npcs)
        npc_info = npcs.get(npc_id) or {}
        raw_by_id = {_int(r["id"]): r for r in group_rows}
        line_quests = []
        for row in group_rows:
            qid = _int(row["id"])
            trigger = row.get("triggerExpr") or {}
            prev = 0
            if _call_parts(trigger)[1] == "任务提交":
                for value in _expr_ints(trigger):
                    if _int(value) in hc_ids and _int(value) != qid:
                        prev = _int(value)
                        break
            giver_id = _int(row.get("acqNpcID")) or _int((row.get("experience") or {}).get("npcId"))
            gates = list(acq_gates.get(qid) or [])
            if row.get("acqCondition"):
                gate = _gate_from_condition(conds.get(_int(row["acqCondition"])), npcs)
                gate["source"] = "acqCondition"
                if gate not in gates:
                    gates.append(gate)
            options = []
            for option in options_by_dialogue.get(qid) or []:
                options.append({
                    "text": option["text"],
                    "to": [t for t in option["to"] if t != qid and t in raw_by_id],
                    "gate": option["gate"],
                })
            line_quests.append({
                "id": qid,
                "name": _plain(row.get("name")) or ("红尘 %s" % qid),
                "desc": _clip(_plain(row.get("description")), 200),
                "group": group,
                "prev": prev, "next": [], "depth": 0,
                "branch": False, "branch_key": "", "branch_with": [],
                "hidden": bool(row.get("hidden")),
                "acq_source": _int(row.get("acqSource")),
                "giver": {"id": giver_id, "name": npcs.get(giver_id, {}).get("name", "")} if giver_id else None,
                "gates": gates, "options": options,
            })
        by_id = {q["id"]: q for q in line_quests}

        # 对话分支：同一段对话的多个选项各接取一个任务 => 互斥。
        branch_defs = []
        for did, targets in dialogue_targets.items():
            if did not in by_id or len(targets) < 2:
                continue
            members = [t for t in targets if t in by_id]
            if len(members) < 2:
                continue
            key = "d:%d" % did
            names = [by_id[m]["name"] for m in members]
            for qid in members:
                q = by_id[qid]
                q["branch"] = True
                q["branch_key"] = key
                q["branch_with"] = [n for n in names if n != q["name"]]
                if not q["prev"]:
                    q["prev"] = did
            branch_defs.append({"key": key, "parent": did, "members": sorted(members),
                                "names": names, "kind": "对话选项"})

        # 单目标选项也补全前置。
        for did, options in options_by_dialogue.items():
            if did not in by_id:
                continue
            for option in options:
                for target in option["to"]:
                    if target in by_id and not by_id[target]["prev"]:
                        by_id[target]["prev"] = did

        # 同一流水接取的多个任务也构成分支（对话未覆盖时）。
        flow_owners = {}
        for qid, raw in raw_by_id.items():
            for field in ("questSubmitFlowId", "questAcqFlowId"):
                fid = _int(raw.get(field))
                if fid:
                    flow_owners.setdefault(fid, []).append(qid)
        covered = {m for definition in branch_defs for m in definition["members"]}
        for fid, owners in flow_owners.items():
            if len(owners) < 2:
                continue
            if all(owner in covered for owner in owners):
                continue
            key = "f:%d" % fid
            names = [by_id[o]["name"] for o in owners if o in by_id]
            for qid in owners:
                q = by_id[qid]
                q["branch"] = True
                q["branch_key"] = key
                q["branch_with"] = [n for n in names if n != q["name"]]
            parent = next((q["prev"] for q in (by_id[o] for o in owners)
                           if q["prev"] in by_id), 0)
            branch_defs.append({"key": key, "parent": parent, "members": sorted(owners),
                                "names": names, "kind": "剧情分支"})

        # 分支汇合点：分支成员共享流水的“接取任务”目标。
        for definition in branch_defs:
            member_flows = set()
            for qid in definition["members"]:
                raw = raw_by_id.get(qid) or {}
                for field in ("questSubmitFlowId", "questAcqFlowId"):
                    fid = _int(raw.get(field))
                    if fid:
                        member_flows.add(fid)
            nexts = []
            for fid in sorted(member_flows):
                for target in flow_targets.get(fid, []):
                    if target in by_id and target not in definition["members"] and target not in nexts:
                        nexts.append(target)
            definition["next"] = sorted(nexts)

        # 深度（链上的环数），用于前端分列。
        for q in line_quests:
            depth, seen, cur = 1, {q["id"]}, q
            while cur["prev"] in by_id and cur["prev"] not in seen:
                seen.add(cur["id"])
                cur = by_id[cur["prev"]]
                depth += 1
            q["depth"] = depth
        line_quests.sort(key=lambda q: (q["depth"], q["id"]))

        edges = []
        for q in line_quests:
            if q["prev"] in by_id:
                edges.append({"from": q["prev"], "to": q["id"],
                              "kind": "branch" if q["branch"] else "sequential",
                              "condition": " / ".join(g["text"] for g in q["gates"]),
                              "label": "分支" if q["branch"] else "",
                              "gate": q["gates"][0] if q["gates"] else None})
            for option in q["options"]:
                for target in option["to"]:
                    if target in by_id:
                        edges.append({"from": q["id"], "to": target, "kind": "conditional",
                                      "condition": (option["gate"] or {}).get("text") or "",
                                      "label": option["text"], "gate": option["gate"]})
        for definition in branch_defs:
            for target in definition.get("next") or []:
                for member in definition["members"]:
                    edges.append({"from": member, "to": target, "kind": "merge",
                                  "condition": "", "label": "汇合", "gate": None})

        lines.append({
            "group": group, "name": character,
            "npc_id": npc_id, "portrait": npc_info.get("portrait") or "",
            "color": line_colors[group_index % len(line_colors)],
            "quests": line_quests,
            "roots": [q["id"] for q in line_quests if q["depth"] == 1],
            "edges": edges,
            "branches": [{"key": d["key"], "parent": d["parent"], "members": d["members"],
                          "names": d["names"], "next": d.get("next") or [], "kind": d["kind"]}
                         for d in branch_defs],
            "stats": {"total": len(line_quests),
                      "with_gates": sum(1 for q in line_quests if q["gates"] or q["options"])},
        })
        all_quests.extend(line_quests)

    stats = {
        "lines": len(lines), "quests": len(all_quests),
        "with_gates": sum(1 for q in all_quests if q["gates"] or q["options"]),
        "gates": sum(len(q["gates"]) + sum(1 for o in q["options"] if o["gate"])
                     for q in all_quests),
        "branches": sum(len(line["branches"]) for line in lines),
    }
    return {
        "schema": SCHEMA, "lines": lines, "quests": all_quests,
        "states": {str(k): v for k, v in HONGCHEN_STATE_NAMES.items()},
        "attr_names": attr_names, "stats": stats,
        "done_states": list(DONE_STATES), "doing_states": list(DOING_STATES),
    }


build = build_hongchen
