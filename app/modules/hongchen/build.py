# -*- coding: utf-8 -*-
"""红尘：配置表 -> 模块快照。

只依赖 meta_update 的公共解析函数；不 import 其它模块。
游戏新增红尘任务（type=5 数据行）后重新导出快照即可，不需要改代码。
"""
import re

from meta_update import (
    SCHEMA, _call_parts, _clip, _const_args, _expr_ints, _int,
    _plain, _rows, _text, build_realms, build_spaces,
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

# 条件调用「任务提交/任务持有」这类玩家看不懂的机器写法 -> 人话动词。
# 末尾数字不是数量，而是任务 id，必须翻成任务名，绝不能把 id 直接甩给玩家。
_QUEST_CALLS = {
    "任务提交": "已提交过", "任务已提交": "已提交过",
    "任务完成": "已完成", "任务已完成": "已完成",
    "任务持有": "已接取", "任务接取": "已接取", "任务领取": "已接取",
}


def _table_rows(table):
    """tbquest 在游戏包里是 {rows, overrides}，其它表多为纯 list。"""
    if isinstance(table, dict) and isinstance(table.get("rows"), list):
        return table["rows"]
    return _rows(table)


def _space_index(tables):
    """tbspace -> {spaceId: "父地点 / 子地点"}，供 scan 按存档实时位置查女主在哪。"""
    out = {}
    for space_id, info in build_spaces(tables).items():
        path = [part for part in (info.get("path") or []) if part]
        if path:
            out[str(space_id)] = " / ".join(path)
    return out


def _build_phase_names(tables):
    """阶段 id → 阶段名（33 → 结丹后期），供把修炼层数门槛翻译成人话。"""
    out = {}
    for row in _rows(tables.get("tbcultivatephase")):
        if isinstance(row, dict) and row.get("id") is not None:
            name = _text(row.get("phase_name")) or ""
            if name:
                out[str(_int(row["id"]))] = name
    return out


def _build_realm_phases(tables):
    """阶段 id → 境界 id（21 → 2），供把玩家修炼层数换算成境界。"""
    out = {}
    for row in _rows(tables.get("tbcultivaterealm")):
        if isinstance(row, dict) and row.get("id") is not None:
            realm_id = _int(row.get("id"))
            for phase in row.get("phases") or []:
                out[str(_int(phase))] = realm_id
    return out


def _build_layer_phases(tables):
    """层数 id → 阶段全称（10 → 炼气后期），供把「修炼层数 10」翻译成人话。"""
    realms = build_realms(tables)
    phase_names, phase_realms = {}, {}
    for row in _rows(tables.get("tbcultivatephase")):
        if isinstance(row, dict) and row.get("id") is not None:
            phase_id = str(_int(row["id"]))
            phase_names[phase_id] = _text(row.get("phase_name")) or ""
            phase_realms[phase_id] = _int(row.get("realm"))
    out = {}
    for row in _rows(tables.get("tbcultivatelayer")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        phase_id = str(_int(row.get("phase")))
        name = phase_names.get(phase_id) or realms.get(str(phase_realms.get(phase_id, 0))) or ""
        if name:
            out[str(_int(row["id"]))] = name
    return out


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


def _type_label(value):
    """tbquesttype 的 text 带方括号（如「[主线]」），去掉括号只留类别名。"""
    return re.sub(r"[\[\]【】\s]", "", str(value or ""))


def _quest_gate_text(verb, quest_id, quest_names, quest_types):
    """「任务提交 11363」 -> 「已提交过主线「天帷之破」」，查不到名字也不出现裸数字。"""
    name = (quest_names or {}).get(quest_id) or ""
    kind = _type_label((quest_types or {}).get(quest_id))
    if not name:
        return "%s某个任务" % verb
    if kind:
        return "%s%s「%s」" % (verb, kind, name)
    return "%s「%s」" % (verb, name)


def _expr_gate(node, npcs, quest_names=None, quest_types=None):
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
        parts = [_expr_gate(item, npcs, quest_names, quest_types) for item in args]
        parts = [p for p in parts if p]
        if not parts:
            return None
        joiner = " 或 " if name in ("或", "||") else " 且 "
        return {"kind": "", "need": 0, "text": joiner.join(p["text"] for p in parts),
                "parts": parts}
    if name in ("非", "!", "not") and args:
        inner = _expr_gate(args[0], npcs, quest_names, quest_types)
        return {"kind": "", "need": 0,
                "text": "非（%s）" % (inner["text"] if inner else "条件")}
    call = index if index in _QUEST_CALLS else (name if name in _QUEST_CALLS else "")
    if call and nums:
        # 「条件.任务提交(11363)」：数字是任务 id，翻成任务名 + 类别。
        quest_id = nums[0]
        return {"kind": "quest", "need": quest_id,
                "text": _quest_gate_text(_QUEST_CALLS[call], quest_id,
                                         quest_names, quest_types)}
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
        return {"kind": "", "need": need, "text": "属性≥%d" % need}
    if name == "NPC" and index == "好感度至少" and len(nums) >= 2:
        return {"kind": "favor", "npc": nums[0], "need": nums[1],
                "text": "%s好感≥%d" % (npcs.get(nums[0], "NPC %s" % nums[0]), nums[1])}
    if name in ("等于", "EQ", "==") and nums:
        return {"kind": "", "need": nums[-1], "text": "＝%d" % nums[-1]}
    text = index or name
    return {"kind": "", "need": nums[-1] if nums else 0,
            "text": str(text) + ((" " + "/".join(str(x) for x in nums)) if nums else "")}


def _gate_from_condition(cond_row, npcs, grey_text="", quest_names=None, cond_option=None,
                         quest_types=None, realms=None, layer_phases=None, phase_names=None):
    """把 optionCondition 引用的条件行翻译成人话门槛 + 可判定结构。

    quest_names / cond_option / quest_types 由配置表动态构建（见 build_hongchen）：
      * quest_names: 任务 id -> 人话任务名，用于把 SIDE_ZHUJI_80144 翻成「丹房门影」；
      * quest_types: 任务 id -> 类别（主线/红尘/委托…），让「任务提交 11363」能翻成主线；
      * cond_option: 条件 id -> 引用它的选项文本，用于把 _O1 翻成「言辞支开」。
    新增任务/选项只需重新导出快照即可，无需改代码。

    realms / layer_phases / phase_names 用于把「境界≥2」「修炼层数 10」这类门槛翻成
    玩家看得懂的境界名/阶段名，而不是裸数字或英文 token。
    """
    quest_names = quest_names or {}
    cond_option = cond_option or {}
    quest_types = quest_types or {}
    realms = realms or {}
    layer_phases = layer_phases or {}
    phase_names = phase_names or {}
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
        # 80144 / 选项 1 这类机器语言，翻成任务名 + 选项文本。
        quest_id = _int(m.group(1))
        quest_name = quest_names.get(quest_id) or str(quest_id)
        option_text = cond_option.get(_int(cond_row.get("id"))) or ("选项 %s" % m.group(2))
        text = "需完成「%s」并选择「%s」" % (quest_name, option_text)
        kind, need = "quest_option", quest_id
    elif (m := re.search(r"_AFTER_(\d+)\s*$", upper)):
        # 云嫣线 YUNYAN_INVITE_AFTER_11363 这类别名，条件树缺失时也能翻成人话。
        quest_id = _int(m.group(1))
        text = _quest_gate_text("已提交过", quest_id, quest_names, quest_types)
        kind, need = "quest", quest_id
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
            symbol = {"GE": "≥", "GT": ">", "LT": "＜", "EQ": "＝"}[op]
            if token == "REALM":
                # 境界门槛里的数字是境界 id（2 = 筑基期），不是属性值，不能写成「境界≥2」。
                realm_name = realms.get(str(digits)) or ("境界%d" % digits)
                text, kind, need = "境界 %s %s" % (symbol, realm_name), "realm", digits
            else:
                attr_name = _ATTR_TOKEN.get(token, "")
                # 认不出的属性词宁可写「属性」，也不要甩一个英文 token 给玩家。
                text, kind, need = "%s%s%d" % (attr_name or "属性", symbol, digits), "attr", digits
        elif (m := re.search(r"_LAYER_(\d+)\s*$", upper)):
            # 修炼层数门槛（SIDE_SHENTONGTONG_QI_LAYER_10）：数字是层数 id，翻成阶段名。
            layer_id = int(m.group(1))
            layer_name = (layer_phases.get(str(layer_id))
                          or phase_names.get(str(layer_id))
                          or ("第 %d 层" % layer_id))
            text, kind, need = "境界达到 %s" % layer_name, "layer", layer_id
        elif (m := re.search(r"_(GE|LT|EQ)_(\d+)\s*$", upper)):
            symbol = {"GE": "≥", "LT": "＜", "EQ": "＝"}[m.group(1)]
            text, need = "属性%s%d" % (symbol, int(m.group(2))), int(m.group(2))

    if not text:
        parsed = _expr_gate(cond_row.get("condition"), npcs, quest_names, quest_types)
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
    # 任务 id -> 人话名 / 类别。取全表（不只红尘），这样「任务提交 11363」这种
    # 指向主线的前置也能翻成「已提交过主线「天帷之破」」。
    quest_names, quest_types = {}, {}
    for row in all_rows:
        qid = _int(row["id"])
        quest_names[qid] = _plain(row.get("name")) or str(qid)
        quest_types[qid] = type_names.get(_int(row.get("type"))) or ""
    cond_option = {}
    for row in _rows(tables.get("tbdialogue")):
        if not isinstance(row, dict):
            continue
        for option in row.get("options") or []:
            if not isinstance(option, dict):
                continue
            cid = _int(option.get("optionCondition"))
            text = _text(option.get("optionText"))
            if cid and text and cid not in cond_option:
                cond_option[cid] = text
    attr_names = {}
    for row in _rows(tables.get("tbinteractattribute")):
        if isinstance(row, dict) and row.get("id") is not None:
            attr_names[str(_int(row["id"]))] = _text(row.get("name"))
    # 境界/阶段/层数映射：把「境界≥2」「修炼层数 10」翻成人话（2 → 筑基期，10 → 炼气后期）。
    realms = build_realms(tables)
    realm_phases = _build_realm_phases(tables)
    phase_names = _build_phase_names(tables)
    layer_phases = _build_layer_phases(tables)

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
                    _text(option.get("optionGreyText")), quest_names, cond_option,
                    quest_types, realms, layer_phases, phase_names)
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
                gate = _gate_from_condition(conds.get(_int(row["acqCondition"])), npcs,
                                            "", quest_names, cond_option, quest_types,
                                            realms, layer_phases, phase_names)
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
        "spaces": _space_index(tables),
        "realms": realms, "phases": realm_phases, "phase_names": phase_names,
        "layer_phases": layer_phases,
        "done_states": list(DONE_STATES), "doing_states": list(DOING_STATES),
    }


build = build_hongchen
