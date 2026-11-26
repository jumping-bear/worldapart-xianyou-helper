# -*- coding: utf-8 -*-
"""接取 / 开启条件的统一解析。

支线与奇遇共用：配置里同一类条件（境界、层数、任务提交、NPC 对话、随机事件标记）
永远输出同一句人话，避免各模块各写一套后出现“石中剑只写无门槛”这类漏读。
"""
import re

from meta_update import _call_parts, _const_args, _expr_ints, _int, _plain, _text

_OP_NAMES = {">=", ">", "<=", "<", "==", "!=",
             "大于等于", "大于", "小于等于", "小于", "等于"}
_LOGIC_AND = {"&&", "且", "and"}
_LOGIC_OR = {"||", "或", "or"}
_NOT = {"!", "非", "not"}
_SELF_STATES = {"任务提交", "任务持有", "任务接取", "任务进行中"}


def _unwrap(node):
    while isinstance(node, (list, tuple)) and len(node) == 2 and isinstance(node[1], dict):
        node = node[1]
    return node


def _left_key(node):
    """解析「玩家.境界」这类索引表达式，返回 (拥有者, 字段)。"""
    node = _unwrap(node)
    if not isinstance(node, dict):
        return "", ""
    owner = ""
    target = node.get("target")
    if isinstance(target, list) and len(target) > 1 and isinstance(target[1], dict):
        owner = str(target[1].get("name") or "")
    key = ""
    index = node.get("index")
    if isinstance(index, list) and len(index) > 1 and isinstance(index[1], dict):
        key = str(index[1].get("value") or "")
    return owner, key


def _layer_local(ctx, layer_id):
    """层数显示用“本境界第几层”，不暴露表里的全局 id（筑基 9 层，而不是第 29 层）。"""
    value = (ctx.get("layer_local") or {}).get(str(layer_id))
    return value or layer_id


def _layer_label(ctx, layer_id):
    name = (ctx.get("layer_phases") or {}).get(str(layer_id))
    if name:
        return "「%s」（第 %s 层）" % (name, _layer_local(ctx, layer_id))
    return "第 %s 层" % _layer_local(ctx, layer_id)


def _realm_label(ctx, realm_id):
    return "「%s」" % ((ctx.get("realms") or {}).get(str(realm_id)) or ("境界 %s" % realm_id))


_QUEST_STATE_LABELS = {1: "进行中", 2: "已完成", 3: "已提交", 5: "已放弃", 6: "待提交"}


def quest_state_label(state):
    """存档 questComponent.quests[id].state 的玩家可读状态。"""
    if state is None or _int(state, -1) < 0:
        return "未获得"
    return _QUEST_STATE_LABELS.get(_int(state), "状态 %s" % state)


def _quest_name(ctx, quest_id):
    names = ctx.get("quest_names") or {}
    return names.get(quest_id) or names.get(str(quest_id)) or ("任务 %s" % quest_id)


def _merge_quest_pending(parts):
    """把「已接取 X」+「X 不在进行中」合并成“目标已完成或待提交”。"""
    skip = set()
    for index, text in enumerate(parts):
        match = re.fullmatch(r"已接取「(.+?)」", text)
        if match and ("「%s」不在进行中" % match.group(1)) in parts:
            skip.add(parts.index("「%s」不在进行中" % match.group(1)))
    out = []
    for index, text in enumerate(parts):
        if index in skip:
            continue
        match = re.fullmatch(r"已接取「(.+?)」", text)
        if match and ("「%s」不在进行中" % match.group(1)) in parts:
            out.append("已接取「%s」，目标已完成或待提交" % match.group(1))
        else:
            out.append(text)
    return out


def _merge_quest_submit_or(parts):
    """「完成 X」与「已接取 X，目标已完成待提交」是同一件事的两种状态，合并展示。"""
    flags = {}
    for text in parts:
        match = re.fullmatch(r"完成「(.+?)」", text)
        if match:
            flags.setdefault(match.group(1), set()).add("submit")
        match = re.fullmatch(r"已接取「(.+?)」，目标已完成或待提交", text)
        if match:
            flags.setdefault(match.group(1), set()).add("pending")
    out = []
    for text in parts:
        match = re.fullmatch(r"完成「(.+?)」", text)
        if match and "pending" in flags.get(match.group(1), set()):
            out.append("完成「%s」（已提交或已完成）" % match.group(1))
            continue
        match = re.fullmatch(r"已接取「(.+?)」，目标已完成或待提交", text)
        if match and "submit" in flags.get(match.group(1), set()):
            continue
        out.append(text)
    return out


def _is_self(node, self_id):
    """任务目标未激活 / 非（已提交自身）是自检，不是给玩家的门槛。"""
    call, index, args = _call_parts(node)
    ids = {_int(value) for value in _expr_ints(args)}
    if not self_id or self_id not in ids:
        return False
    if call in _NOT or index in _NOT:
        inner = _call_parts(args[0]) if args else ("", "", [])
        if inner[1] in _SELF_STATES:
            return True
    return index in ("任务目标未激活", "任务目标激活中")


def _raw_call(node):
    """直接读 func 数组里的调用名与参数；指定年月日时辰这类条件不在 index 上。"""
    if isinstance(node, list) and len(node) > 1 and isinstance(node[1], dict):
        payload = node[1]
        if payload.get("name"):
            return str(payload.get("name") or ""), payload.get("arguments") or []
    if isinstance(node, dict) and node.get("name") and isinstance(node.get("arguments"), list):
        return str(node.get("name") or ""), node.get("arguments") or []
    func = node.get("func") if isinstance(node, dict) else None
    if isinstance(func, list) and len(func) > 1 and isinstance(func[1], dict):
        return str(func[1].get("name") or ""), func[1].get("arguments") or []
    return "", []


def cond_alias(node):
    """识别「条件.CW_MONTH_7_12」这种按别名引用的条件（兼容 list/dict 两种节点形态）。"""
    info = node
    if isinstance(node, list) and len(node) > 1 and isinstance(node[1], dict):
        info = node[1]
    elif isinstance(node, dict):
        func = node.get("func")
        if isinstance(func, list) and len(func) > 1 and isinstance(func[1], dict):
            info = func[1]
    if not isinstance(info, dict):
        return ""
    target = info.get("target")
    if not (isinstance(target, list) and len(target) > 1 and isinstance(target[1], dict)):
        return ""
    owner = str(target[1].get("name") or "")
    index = info.get("index")
    key = ""
    if isinstance(index, list) and len(index) > 1 and isinstance(index[1], dict):
        key = str(index[1].get("value") or "")
    return key if owner == "条件" else ""


def resolve_aliases(node, aliases, depth=0):
    """把「条件.别名」递归展开成真实表达式；游戏新增别名时自动跟随。"""
    if depth > 6 or not aliases:
        return node
    alias = cond_alias(node)
    if alias and alias in aliases:
        return resolve_aliases(aliases[alias], aliases, depth + 1)
    if isinstance(node, list):
        return [resolve_aliases(item, aliases, depth) for item in node]
    if isinstance(node, dict):
        return {key: resolve_aliases(value, aliases, depth)
                for key, value in node.items()}
    return node


def _norm_args(args):
    """部分逻辑节点的 arguments 会多包一层列表，展开后再递归。"""
    args = args or []
    while len(args) == 1 and isinstance(args[0], list) and args[0] \
            and all(isinstance(item, (list, dict)) for item in args[0]):
        args = args[0]
    return args


def _time_text(values):
    """指定年月日时辰：0 表示不限，只写真正限制的项。"""
    year, month, day, unit = (list(values) + [0, 0, 0, 0])[:4]
    parts = []
    if year:
        parts.append("%s 年" % year)
    if month:
        parts.append("%s 月" % month)
    if day:
        parts.append("%s 日" % day)
    if unit:
        parts.append("第 %s 时段" % unit)
    return ("仅在 " + " ".join(parts)) if parts else "在特定时辰"


def gate_text(node, ctx, self_id=0):
    """把开启/接取表达式转成玩家能读的一句话；纯自检自动忽略。"""
    node = _unwrap(node)
    if not isinstance(node, dict):
        return ""
    raw_name, raw_args = _raw_call(node)
    if raw_name == "指定年月日时辰":
        return _time_text(_const_args(raw_args))
    call, index, args = _call_parts(node)
    args = _norm_args(args)
    logic = call if call in (_LOGIC_AND | _LOGIC_OR) else (
        index if index in (_LOGIC_AND | _LOGIC_OR) else "")
    if logic:
        parts = []
        for arg in args:
            text = gate_text(arg, ctx, self_id)
            if text and text not in parts:
                parts.append(text)
        if logic in _LOGIC_OR:
            parts = _merge_quest_submit_or(parts)
            squashed = _squash_month_texts(parts)
            if squashed:
                return squashed
        else:
            parts = _merge_quest_pending(parts)
        return _join_logic(parts, logic)
    if _is_self(node, self_id):
        return ""
    if call in _NOT or index in _NOT:
        inner = args[0] if args else None
        inner_call, inner_index, inner_args = _call_parts(inner) if inner is not None else (None, None, [])
        inner_values = _const_args(inner_args)
        if (inner_call == "任务进行中" or inner_index == "任务进行中") and inner_values:
            return "「%s」不在进行中" % _quest_name(ctx, _int(inner_values[0]))
        text = gate_text(inner, ctx, self_id) if inner is not None else ""
        return ("不满足：%s" % text) if text else ""
    op = call if call in _OP_NAMES else (index if index in _OP_NAMES else "")
    values = _const_args(args)
    if op and len(args) >= 2:
        left = _left_key(args[0])
        value = values[-1] if values else None
        if left[0] == "玩家" and left[1] in ("境界", "修炼阶段") and value is not None:
            return "境界达到%s" % _realm_label(ctx, value)
        if left[0] == "玩家" and left[1] in ("达到修炼层数", "修炼层数") and value is not None:
            return "修为达到%s" % _layer_label(ctx, value)
        if left[0] == "玩家" and left[1] == "宗门" and value is not None:
            name = (ctx.get("sects") or {}).get(str(_int(value))) or value
            return "加入「%s」" % name
        if left[1] == "灵石" and value is not None:
            return "灵石 %s %s" % (op.replace(">=", "≥").replace("<=", "≤"), value)
        if not left[1]:
            return ""
    player_key = index if call == "玩家" else (call if index == "玩家" else "")
    if player_key and values:
        if player_key in ("达到修炼层数", "修炼层数"):
            return "修为达到%s" % _layer_label(ctx, values[-1])
        if player_key in ("修炼阶段", "境界"):
            return "境界达到%s" % _realm_label(ctx, values[-1])
    if call == "条件" and index in _SELF_STATES and values:
        quest_id = _int(values[0])
        # 同一奇遇/任务系列内的状态条件属于阶段路由，不是给玩家的外部门槛。
        if ctx.get("ignore_family") and self_id \
                and quest_id // 10000 == _int(self_id) // 10000:
            return ""
        return {"任务提交": "完成「%s」", "任务持有": "已接取「%s」",
                "任务接取": "曾接取「%s」", "任务进行中": "「%s」正在进行"}[index] \
            % _quest_name(ctx, quest_id)
    if call in _SELF_STATES and values:
        quest_id = _int(values[0])
        if ctx.get("ignore_family") and self_id \
                and quest_id // 10000 == _int(self_id) // 10000:
            return ""
        return {"任务提交": "完成「%s」", "任务持有": "已接取「%s」",
                "任务接取": "曾接取「%s」", "任务进行中": "「%s」正在进行"}[call] \
            % _quest_name(ctx, quest_id)
    if call == "随机事件" and index:
        return "需先触发剧情「%s」" % index
    text = index if isinstance(index, str) and index else ""
    if text in ("条件", "玩家", "非"):
        return ""
    text = _plain(text or "")
    if text == "指定年月日时辰":
        return "在特定时辰"
    return re.sub(r"指定年月日时辰", "在特定时辰", text)


def _squash_month_texts(parts):
    """把「仅在 7 月 或 8 月 … 或 12 月」压成「仅在 7-12 月」。"""
    months = []
    for text in parts:
        text = text.strip()
        while text.startswith("（") and text.endswith("）"):
            text = text[1:-1]
        for piece in text.split(" 或 "):
            match = re.fullmatch(r"仅在\s*(\d+)(?:\s*-\s*(\d+))?\s*月", piece.strip())
            if not match:
                return ""
            start = int(match.group(1))
            end = int(match.group(2) or start)
            months.extend(range(start, end + 1))
    if len(months) < 2:
        return ""
    months = sorted(set(months))
    if months != list(range(months[0], months[-1] + 1)):
        return "仅在 %s 月" % "、".join(str(m) for m in months)
    return "仅在 %s-%s 月" % (months[0], months[-1])


def _join_logic(parts, logic):
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    opposite = " 或 " if logic in _LOGIC_AND else " 且 "
    cleaned = []
    for text in parts:
        while text.startswith("（") and text.endswith("）"):
            text = text[1:-1]
        if opposite in text:
            text = "（%s）" % text
        cleaned.append(text)
    return (" 或 " if logic in _LOGIC_OR else " 且 ").join(cleaned)


def _split_top(text, sep=" 且 "):
    """按顶层分隔符拆句，括号内的「且」不拆。"""
    parts, depth, buf, index = [], 0, "", 0
    while index < len(text):
        char = text[index]
        if char in "（(":
            depth += 1
        elif char in "）)":
            depth = max(0, depth - 1)
        if depth == 0 and text.startswith(sep, index):
            parts.append(buf.strip())
            buf = ""
            index += len(sep)
            continue
        buf += char
        index += 1
    parts.append(buf.strip())
    return [part for part in parts if part]


def combine(*parts):
    """多来源门槛合并：按顶层「且」拆句去重，OR 子句补括号。"""
    out, seen = [], set()
    for part in parts:
        text = (part or "").strip()
        if not text:
            continue
        for clause in _split_top(text):
            if clause in ("条件", "非", "玩家 >= 1"):
                continue
            if " 或 " in clause and not (clause.startswith("（") and clause.endswith("）")):
                clause = "（%s）" % clause
            if clause in seen:
                continue
            seen.add(clause)
            out.append(clause)
    return " 且 ".join(out)


def collect(node, ctx, self_id=0):
    """把表达式收集成可判定的树；未知条件保留为 unknown，不强行判定。"""
    node = _unwrap(node)
    if not isinstance(node, dict):
        return None
    raw_name, raw_args = _raw_call(node)
    if raw_name == "指定年月日时辰":
        year, month, day, unit = (list(_const_args(raw_args)) + [0, 0, 0, 0])[:4]
        return {"kind": "time", "year": _int(year), "month": _int(month),
                "day": _int(day), "unit": _int(unit), "text": _time_text([year, month, day, unit])}
    call, index, args = _call_parts(node)
    args = _norm_args(args)
    logic = call if call in (_LOGIC_AND | _LOGIC_OR) else (
        index if index in (_LOGIC_AND | _LOGIC_OR) else "")
    if logic:
        parts = [collect(arg, ctx, self_id) for arg in args]
        parts = [part for part in parts if part]
        if not parts:
            return None
        return {"mode": "any" if logic in _LOGIC_OR else "all", "parts": parts}
    if _is_self(node, self_id):
        return None
    if call in _NOT or index in _NOT:
        inner = args[0] if args else None
        part = collect(inner, ctx, self_id) if inner is not None else None
        if not part:
            return None
        return {"kind": "not", "part": part}
    op = call if call in _OP_NAMES else (index if index in _OP_NAMES else "")
    values = _const_args(args)
    if op and len(args) >= 2:
        left = _left_key(args[0])
        value = values[-1] if values else None
        if left[0] == "玩家" and left[1] in ("境界", "修炼阶段") and value is not None:
            return {"kind": "realm", "need": _int(value)}
        if left[0] == "玩家" and left[1] in ("达到修炼层数", "修炼层数") and value is not None:
            return {"kind": "layer", "need": _int(value)}
        if left[0] == "玩家" and left[1] == "宗门" and value is not None:
            return {"kind": "sect", "need": _int(value)}
        if left[1] == "灵石" and value is not None:
            return {"kind": "money", "need": _int(value)}
        if left[1] == "当前场景Id" or left[0] == "当前场景":
            return None  # 地点，不是开启门槛
        if left[0] == "玩家" and not left[1]:
            return None
        text = gate_text(node, ctx, self_id)
        return {"kind": "unknown", "text": text} if text else None
    player_key = index if call == "玩家" else (call if index == "玩家" else "")
    if player_key and values:
        if player_key in ("达到修炼层数", "修炼层数"):
            return {"kind": "layer", "need": _int(values[-1])}
        if player_key in ("修炼阶段", "境界"):
            return {"kind": "realm", "need": _int(values[-1])}
    if call == "条件" and index in _SELF_STATES and values:
        quest_id = _int(values[0])
        if ctx.get("ignore_family") and self_id \
                and quest_id // 10000 == _int(self_id) // 10000:
            return None
        return {"kind": "quest", "quest": quest_id, "mode": index}
    if call in _SELF_STATES and values:
        quest_id = _int(values[0])
        if ctx.get("ignore_family") and self_id \
                and quest_id // 10000 == _int(self_id) // 10000:
            return None
        return {"kind": "quest", "quest": quest_id, "mode": call}
    if call == "随机事件" and index:
        return {"kind": "unknown", "text": gate_text(node, ctx, self_id)}
    text = gate_text(node, ctx, self_id)
    return {"kind": "unknown", "text": text} if text else None


def evaluate(tree, ctx):
    """返回 (pass/fail/unknown, 检查项列表)。"""
    if not tree:
        return "pass", []
    if tree.get("mode") in ("all", "any"):
        results = [evaluate(part, ctx) for part in tree.get("parts") or []]
        checks = [check for _, items in results for check in items]
        states = [state for state, _ in results]
        if tree["mode"] == "any":
            if "pass" in states:
                # OR 只要有一条成立，其它未走分支的失败项不能当成“为什么没触发”。
                passing = [items for state, items in results if state == "pass"]
                return "pass", [check for items in passing for check in items]
            return ("unknown" if "unknown" in states else "fail"), checks
        if "fail" in states:
            return "fail", checks
        return ("unknown" if "unknown" in states else "pass"), checks
    kind = tree.get("kind")
    if kind == "not":
        inner = tree.get("part") or {}
        if inner.get("kind") == "quest" and inner.get("mode") == "任务进行中":
            quest_id = _int(inner.get("quest"))
            quests = ctx.get("quests") or {}
            state = _int(quests.get(quest_id, quests.get(str(quest_id), -1)), -1)
            ok = state != 1
            return ("pass" if ok else "fail"), [{
                "text": "「%s」不在进行中" % _quest_name(ctx, quest_id),
                "cur": quest_state_label(state), "need": "非进行中", "ok": ok}]
        state, checks = evaluate(inner, ctx)
        flipped = {"pass": "fail", "fail": "pass", "unknown": "unknown"}[state]
        items = []
        for check in checks:
            item = dict(check)
            if item.get("ok") is not None:
                item["ok"] = not item["ok"]
            item["text"] = "不满足：%s" % (item.get("text") or "条件")
            items.append(item)
        return flipped, items

    if kind == "time":
        game = ctx.get("game_time") or {}
        if not game:
            return "unknown", [{"text": tree.get("text") or "特定时辰", "ok": None}]
        checks = [
            ("year", "year", "年"), ("month", "month", "月"),
            ("day", "day", "日"), ("unit", "unit", "时段"),
        ]
        ok, cur_parts = True, []
        for field, key, _label in checks:
            need = _int(tree.get(field))
            cur = _int(game.get(key))
            if field == "unit":
                cur_parts.append("第 %s 时段" % cur)
            else:
                cur_parts.append("%s %s" % (cur, _label))
            if need and cur != need:
                ok = False
        return ("pass" if ok else "fail"), [{
            "text": tree.get("text") or "特定时辰",
            "cur": " ".join(cur_parts), "need": tree.get("text") or "",
            "ok": ok}]
    if kind == "realm":
        need = _int(tree.get("need"))
        cur = _int(ctx.get("realm"))
        name = (ctx.get("realms") or {}).get(str(need)) or need
        cur_name = (ctx.get("realms") or {}).get(str(cur)) or ("境界 %s" % cur)
        return ("pass" if cur >= need else "fail"), [
            {"text": "境界达到「%s」" % name, "cur": cur, "cur_label": cur_name,
             "need": need, "ok": cur >= need}]
    if kind == "layer":
        need = _int(tree.get("need"))
        cur = _int(ctx.get("layer"))
        name = (ctx.get("layer_phases") or {}).get(str(need)) or ""
        local = _layer_local(ctx, need)
        label = ("「%s」（第 %s 层）" % (name, local)) if name else ("第 %s 层" % local)
        cur_name = (ctx.get("layer_phases") or {}).get(str(cur)) or ("第 %s 层" % _layer_local(ctx, cur))
        return ("pass" if cur >= need else "fail"), [
            {"text": "修为达到%s" % label,
             "cur": cur, "cur_label": cur_name, "need": need, "ok": cur >= need}]
    if kind == "sect":
        need = _int(tree.get("need"))
        cur = _int(ctx.get("sect_id"))
        name = (ctx.get("sects") or {}).get(str(need)) or need
        ok = cur == need
        return ("pass" if ok else "fail"), [
            {"text": "加入「%s」" % name, "cur": cur or "未加入宗门",
             "need": name, "ok": ok}]
    if kind == "money":
        need = _int(tree.get("need"))
        cur = _int(ctx.get("money"))
        return ("pass" if cur >= need else "fail"), [
            {"text": "灵石 ≥ %s" % need, "cur": cur, "need": need, "ok": cur >= need}]
    if kind == "quest":
        quest_id = _int(tree.get("quest"))
        quests = ctx.get("quests") or {}
        state = quests.get(quest_id, quests.get(str(quest_id), -1))
        state = _int(state, -1)
        mode = tree.get("mode")
        name = _quest_name(ctx, quest_id)
        if mode == "任务提交":
            ok, label, need = state == 3, "完成「%s」" % name, "已提交"
        elif mode == "任务持有":
            ok, label, need = state in (1, 2, 6), "已接取「%s」" % name, "已接取"
        elif mode == "任务进行中":
            ok, label, need = state == 1, "「%s」正在进行" % name, "进行中"
        elif mode == "任务接取":
            ok, label, need = state >= 0, "曾接取「%s」" % name, "接取过"
        else:
            ok, label, need = state in (2, 3), "完成「%s」" % name, "已完成"
        return ("pass" if ok else "fail"), [{
            "text": label, "cur": quest_state_label(state),
            "need": need, "ok": ok}]
    return "unknown", [{"text": tree.get("text") or "条件", "ok": None}]
