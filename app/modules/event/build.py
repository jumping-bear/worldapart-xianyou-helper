# -*- coding: utf-8 -*-
"""奇遇：配置表 → 模块快照（自 meta_update.py 原样搬入）。"""
import difflib
import json
import os
import re

from meta_update import (
    SCHEMA, _call_parts, _clip, _const_args, _const_value, _expr_ints, _int, _plain, _rows,
    _text, build_realms, build_spaces,
)


EVENT_GRADE_NAMES = {1: "上品", 2: "中品", 3: "下品"}
EVENT_GRADE_HINT = "上品结局的平均奖励优于中品，中品优于下品；具体奖励见每条结局。"


_OP_NAMES = {
    ">=": ">=", "大于等于": ">=", ">": ">", "大于": ">",
    "<": "<", "小于": "<", "<=": "<=", "小于等于": "<=",
    "==": "==", "等于": "==", "!=": "!=",
}


def _lines(value):
    """把“善恶值 +10|好感度 -10”这类多段文案拆成列表。"""
    return [part.strip() for part in re.split(r"[|\n]", _text(value)) if part.strip()]


_RETRY_NOTES = {
    "木桩已拔、不可逆，不走暂离": "木桩已被拔起，无法重来",
    "旗已毁不可逆，不做暂离": "旗已毁，无法重来",
    "战前已逆吸毁石，不做暂离": "石头已在战前被毁，无法重来",
    "战前已断脉取矿、不可逆，不走暂离": "矿脉已在战前被取走，无法重来",
}
_BATTLE_NODES = {"B1": "小火灵"}


def _retry_note(match):
    text = match.group(1)
    return "（%s）" % _RETRY_NOTES.get(text, "此战失败后无法重来")


def _battle_fail_note(match):
    note = match.group(2).replace("摊已拍散", "摊子已被拍散").replace("不可回访", "无法再来")
    return "与%s战斗失败或逃走（%s）" % (match.group(1), note)


def _polish_path_step(step):
    """把策划备注里的内部术语整理成玩家能看懂的路径。"""
    step = step.split("｜", 1)[0].strip()
    step = re.sub(r"（([^（）]*?)≥(\d+)，不足置灰）", r"（需\1≥\2）", step)
    step = re.sub(r"（([^（）]*?)≥(\d+)，不足置灰$", r"（需\1≥\2）", step)
    step = re.sub(r"（\s*([^（）]*?)\s*在选项上即改）", r"（\1）", step)
    step = step.replace("选项上已扣押注", "已扣押注")
    step = re.sub(r"（原案【[^】]*】= \d+）", "", step)
    step = step.replace("（原案带神识+/善恶+，保留为一次性结局）", "（一次性结局）")
    step = step.replace("（无门槛，一次性收口）", "（无门槛，一次性结局）")
    step = step.replace("（一次性收口，无奖励）", "（一次性结局，无奖励）")
    step = step.replace("（带奖惩的一次性收口）", "（带奖惩的一次性结局）")
    step = step.replace("（带灵机经验的一次性收口）", "（带灵机经验的一次性结局）")
    step = step.replace("（一次性收口）", "（一次性结局）")
    step = step.replace("神识检定成功（含第一轮赢局暂存）", "神识检定成功（第一轮赢下的押注也一并发放）")
    step = step.replace("神识检定成功（≥4）", "神识检定成功（需≥4）")
    step = step.replace("神识检定失败（≥4）", "神识检定失败（需≥4）")
    step = re.sub(r"神识检定成功（1003 要求 (\d+) 级，成功率按常量表 ATTR_CHECK_\*）",
                  r"神识检定成功（需神识 \1 级）", step)
    step = step.replace("战前扣生命 70%", "战前扣除当前生命的 70%")
    step = re.sub(r"战前 flow \d+ 扣当前生命 (\d+)%", r"战前扣除当前生命的 \1%", step)
    step = re.sub(r"灵机检定成功（押注赢局暂存 \d+，本结局一并发放）",
                  "灵机检定成功（赢下的押注会一并发放）", step)
    step = re.sub(r"（败/逃走暂离 [^）]*，回访直达 [^）]*）", "（失败或逃走会暂时离开，可回访再战）", step)
    step = re.sub(r"（败/逃走暂离 [^）]*，回访重播首屏）", "（失败或逃走会暂时离开，可回访再战）", step)
    step = re.sub(r"（败/逃走暂离 [^）]*）", "（失败或逃走会暂时离开，可回访再战）", step)
    step = re.sub(r"（([^（）]*(?:不可逆|不[做走]暂离)[^（）]*)）", _retry_note, step)
    step = step.replace("不可回访", "无法再来")
    step = step.replace("（不可逃，无暂离）", "（此战无法逃跑）")
    step = step.replace("（不可逃）", "（此战无法逃跑）")
    step = re.sub(r"（不可逃$", "（此战无法逃跑）", step)
    step = re.sub(r"（补写结局.*$", "", step)
    step = re.sub(r"（新增结局.*$", "", step)
    step = re.sub(r"^战斗·(.+?)\s+胜$", r"战胜\1", step)
    step = re.sub(r"^战斗·(.+?)\s+败/逃（([^）]*)）$", _battle_fail_note, step)
    step = re.sub(r"^B(\d+)\s*胜$",
                  lambda m: "战胜%s" % _BATTLE_NODES.get("B" + m.group(1), "对手"), step)
    step = re.sub(r"^B(\d+)\s*败或逃.*$",
                  lambda m: "与%s战斗失败或逃走" % _BATTLE_NODES.get("B" + m.group(1), "对手"), step)
    step = step.replace("战败/逃", "战斗失败或逃走")
    step = re.sub(r"(?<!战斗)战败", "战斗失败", step)
    step = step.replace("逃跑", "逃走")
    return step.strip()


# 达成路径的人工注解放在数据文件里（notes.json），游戏更新只改 JSON、不改代码：
# 每条按结局标题（首选）或结局 id 关联，都对不上就跳过、回退到策划备注里的「路径：」标注。
NOTES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes.json")


def _load_path_notes():
    try:
        with open(NOTES_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    notes = data.get("notes") if isinstance(data, dict) else data
    out = []
    for note in notes or []:
        if not isinstance(note, dict):
            continue
        title = _text(note.get("ending_title") or note.get("title")).strip()
        ending_id = _int(note.get("ending_id") or note.get("id"))
        path = note.get("path") or []
        if isinstance(path, str):
            path = [path]
        path = [str(step).strip() for step in path if str(step).strip()]
        if not title and not ending_id:
            continue
        out.append({"id": ending_id, "title": title, "path": path})
    return out


PATH_NOTES = _load_path_notes()


def _ending_path(ending_id, title, note):
    """结局达成路径：优先 notes.json 人工注解（标题优先、id 兜底），对不上回退策划备注。"""
    matched = next((item for item in PATH_NOTES
                    if item["title"] and _text(title).strip() == item["title"]), None)
    if matched is None:
        matched = next((item for item in PATH_NOTES
                        if item["id"] and _int(ending_id) == item["id"]), None)
    if matched:
        return list(matched["path"])
    return _designer_path(note)


def _designer_path(note):
    """从策划备注里取出结局达成路径（“路径：A > B > C”）。"""
    text = _text(note)
    match = re.search(r"路径[:：]\s*(.+)$", text, re.S)
    if not match:
        return []
    tail = re.split(r"[；;]", match.group(1))[0]
    steps = [part.strip(" 　。") for part in re.split(r"\s*[>＞]\s*", tail)]
    return [_polish_path_step(step) for step in steps if step]


# 达成路径里的“（需X≥N）”“（X≥N）”“（需X N 级）”阈值，策划备注是手写的、会过期，
# 必须对齐到对话树里选项的真实条件（tree.nodes.*.options[].conds[].checks）。下面这组函数负责对齐。
_THRESHOLD_RE = re.compile(r"^(.*?)（(需)?\s*([^（）]*?)\s*(≥|>)\s*(\d+)\s*）$")
_LEVEL_RE = re.compile(r"^(.*?)（(需)?\s*([^（）]*?)\s*(\d+)\s*级）$")
_VERDICT_RE = re.compile(r"^(神识|灵机|体魄|辩道|医术)检定(成功|失败)$")


def _norm_match(text):
    """去掉标点与空白，供选项文本与路径步骤做模糊匹配。"""
    return re.sub(r"[\s\u3000。，、！？；：\"'“”‘’「」『』（）()【】…—·~＞≥]", "", text or "")


def _match_score(a, b):
    """路径步骤与选项文本的相似度：子串匹配优先，否则按最长公共子序列。"""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b:
        return 0.85 + 0.15 * len(a) / len(b)
    if b in a:
        return 0.85 + 0.15 * len(b) / len(a)
    return difflib.SequenceMatcher(None, a, b).ratio()


def _positive_checks(checks):
    """只保留“可达正向门槛”的检查：属性 / 灵石 / 物品的 >= 或 >。"""
    out = []
    for check in checks or []:
        if not isinstance(check, dict) or check.get("op") not in (">=", ">"):
            continue
        kind = check.get("t")
        if kind == "attr":
            out.append(("attr", check.get("a"), check.get("op"), check.get("v")))
        elif kind == "money":
            out.append(("money", None, check.get("op"), check.get("v")))
        elif kind == "item":
            out.append(("item", check.get("i"), check.get("op"), check.get("v")))
    return out


def _render_need(checks, attrs, items, currency):
    """把正向检查渲染成“需体魄≥8 且 灵石≥50”（同一属性取最低门槛）。"""
    best = {}
    for kind, key, op, value in checks:
        if value is None:
            continue
        slot = (kind, key)
        if slot not in best or value < best[slot][1]:
            best[slot] = (op, value)
    parts = []
    for (kind, key), (op, value) in sorted(best.items(), key=lambda item: (item[0][0], str(item[0][1]))):
        symbol = "≥" if op == ">=" else ">"
        if kind == "attr":
            name = (attrs.get(str(key)) or {}).get("name") or ("属性%s" % key)
            parts.append("%s%s%s" % (name, symbol, value))
        elif kind == "money":
            parts.append("灵石%s%s" % (symbol, value))
        else:
            if key in currency:
                parts.append("灵石%s%s" % (symbol, value))
            else:
                name = (items.get(str(key)) or {}).get("name") or ("物品%s" % key)
                parts.append("%s%s%s" % (name, symbol, value))
    return "需" + " 且 ".join(parts) if parts else ""


def _tree_option_checks(tree):
    """从剧情树收集 (规范化选项文本, 原始检查列表)，供阈值对齐。"""
    records = []
    for node in (tree or {}).get("nodes", {}).values():
        for option in node.get("options") or []:
            text = option.get("t") or ""
            if not text:
                continue
            checks = []
            for cond in option.get("conds") or []:
                checks.extend(cond.get("checks") or [])
            records.append((_norm_match(text), checks))
    return records


def _attr_id_by_name(attrs, name):
    for attr_id, info in attrs.items():
        if (info or {}).get("name") == name:
            return _int(attr_id)
    return 0


def _min_attr_threshold(records, attr_id):
    values = []
    for _norm, checks in records:
        for check in checks or []:
            if (isinstance(check, dict) and check.get("t") == "attr"
                    and _int(check.get("a")) == attr_id and check.get("op") in (">=", ">")):
                value = check.get("v")
                if value is not None:
                    values.append(value)
    return min(values) if values else None


def _align_path_step(step, records, attrs, items, currency):
    """把单条路径步骤里的“（需X≥N）”“（X≥N）”“（需X N 级）”阈值对齐到剧情树的真实选项条件。"""
    match = _THRESHOLD_RE.match(step) or _LEVEL_RE.match(step)
    if not match:
        return step
    core = match.group(1).strip()
    core_norm = _norm_match(core)
    if not core_norm:
        return step
    scored = [(_match_score(core_norm, opt_norm), checks) for opt_norm, checks in records]
    best_score = max((score for score, _ in scored), default=0.0)
    if best_score >= 0.55:
        merged = []
        for score, checks in scored:
            if score >= best_score - 0.001:
                merged.extend(checks)
        need = _render_need(_positive_checks(merged), attrs, items, currency)
        if need:
            return "%s（%s）" % (core, need)
        return core
    # 流程型“神识检定成功/失败”等无法按选项文本匹配，改用属性名在树里找回真实门槛。
    verdict = _VERDICT_RE.match(core)
    if verdict:
        attr_id = _attr_id_by_name(attrs, verdict.group(1))
        threshold = _min_attr_threshold(records, attr_id) if attr_id else None
        if threshold:
            return "%s（需%s≥%s）" % (core, verdict.group(1), threshold)
    if "（以实际选项为准）" in step:
        return step
    return "%s（以实际选项为准）" % step


def _align_path(path, tree, attrs, items, currency):
    """把整条达成路径的阈值对齐到剧情树。"""
    records = _tree_option_checks(tree)
    if not records:
        return list(path)
    return [_align_path_step(step, records, attrs, items, currency) for step in (path or [])]


def _operand_text(node, attrs, quest_names=None):
    """把条件左/右值渲染成人话，并保留可用于判定的属性 id。"""
    name, index, args = _call_parts(node)
    names = quest_names or {}
    if name == "玩家" and index == "检定探索属性等级":
        values = _const_args(args) or _expr_ints(args)
        attr_id = values[0] if values else 0
        info = attrs.get(str(attr_id)) or {}
        return {"text": (info.get("name") or "探索属性") + "等级", "attr": attr_id,
                "need_level": values[1] if len(values) > 1 else None}
    if name == "玩家" and index == "探索属性等级":
        values = _expr_ints(args)
        attr_id = values[0] if values else 0
        info = attrs.get(str(attr_id)) or {}
        return {"text": (info.get("name") or "探索属性") + "等级", "attr": attr_id}
    if name == "条件" and index in ("任务持有", "任务提交"):
        values = _expr_ints(args)
        quest_id = values[0] if values else 0
        label = names.get(quest_id) or ("任务 %s" % quest_id)
        return {"text": ("已接取" if index == "任务持有" else "已提交") + "「%s」" % label}
    if index == "灵石" or name == "灵石":
        return {"text": "灵石", "money": True}
    if name == "拥有物品数量":
        values = _expr_ints(args)
        if values:
            return {"text": "拥有物品 %s 数量" % values[0], "item": values[0]}
    value = _const_value(node)
    if isinstance(value, bool):
        return {"text": "是" if value else "否", "value": value}
    if isinstance(value, (int, float, str)):
        return {"text": str(value), "value": value}
    if name in ("任务持有", "任务提交", "任务进行中"):
        values = _expr_ints(args)
        quest_id = values[0] if values else 0
        label = names.get(quest_id) or ("任务 %s" % quest_id)
        if name == "任务进行中":
            return {"text": "奇遇进行中「%s」" % label}
        return {"text": "%s%s" % (name, quest_id)}
    if name == "随机事件" and index:
        return {"text": "随机事件标记「%s」" % index}
    if name and index:
        return {"text": "%s·%s" % (name, index)}
    if name:
        return {"text": name}
    return {"text": "条件"}


def _condition(node, attrs, quest_names=None):
    """把条件表达式转成可读文本，并在可靠时附带可判定的检查项。"""
    name, index, args = _call_parts(node)
    if name in ("&&", "and", "||", "or"):
        parts = [_condition(arg, attrs, quest_names) for arg in args]
        checks, exact = [], True
        for part in parts:
            checks.extend(part.get("checks") or [])
            exact = exact and part.get("exact")
        if name in ("||", "or"):
            checks, exact = [], False
        joiner = " 且 " if name in ("&&", "and") else " 或 "
        return {"text": joiner.join(part.get("text") or "条件" for part in parts),
                "checks": checks, "exact": exact}
    if name in ("!", "not"):
        sub = _condition(args[0], attrs, quest_names) if args else {}
        checks = sub.get("checks") or []
        if len(checks) == 1:
            check = dict(checks[0])
            check["op"] = {">=": "<", ">": "<=", "<=": ">", "<": ">=", "==": "!=",
                           "!=": "=="}.get(check.get("op"), check.get("op"))
            return {"text": "非（%s）" % (sub.get("text") or "条件"),
                    "checks": [check], "exact": True}
        return {"text": "非（%s）" % (sub.get("text") or "条件"),
                "checks": [], "exact": False}
    if name in _OP_NAMES:
        left = _operand_text(args[0], attrs, quest_names) if args else {"text": "?"}
        right = _operand_text(args[1], attrs, quest_names) if len(args) > 1 else {"text": "?"}
        op = _OP_NAMES[name]
        checks, exact = [], False
        if left.get("attr") and right.get("value") is not None:
            checks = [{"t": "attr", "a": left["attr"], "op": op, "v": right["value"]}]
            exact = True
        elif left.get("money") and right.get("value") is not None:
            checks = [{"t": "money", "op": op, "v": right["value"]}]
            exact = True
        elif left.get("item") and right.get("value") is not None:
            checks = [{"t": "item", "i": left["item"], "op": op, "v": right["value"]}]
            exact = True
        return {"text": "%s %s %s" % (left.get("text"), op, right.get("text")),
                "checks": checks, "exact": exact}
    if name in ("随机事件", "玩家") and index in ("扣除灵石", "选项扣除灵石"):
        values = _const_args(args) or _expr_ints(args)
        amount = values[-1] if values else 0
        return {"text": "灵石 >= %s" % amount,
                "checks": [{"t": "money", "op": ">=", "v": amount}], "exact": True}
    if name == "玩家" and index == "检定探索属性等级":
        operand = _operand_text(node, attrs, quest_names)
        need = operand.get("need_level")
        if operand.get("attr") and isinstance(need, int):
            return {"text": "%s >= %s" % (operand.get("text"), need),
                    "checks": [{"t": "attr", "a": operand["attr"], "op": ">=", "v": need}],
                    "exact": True}
        return {"text": operand.get("text") or "属性检定", "checks": [], "exact": False}
    operand = _operand_text(node, attrs, quest_names)
    if operand.get("text") != "条件":
        return {"text": operand["text"], "checks": [], "exact": False}
    if name == "属性检定":
        return {"text": "属性检定", "checks": [], "exact": False}
    if name == "任务进行中":
        return {"text": "奇遇进行中", "checks": [], "exact": False}
    if name == "有标记":
        return {"text": "需要剧情标记", "checks": [], "exact": False}
    if name:
        return {"text": name, "checks": [], "exact": False}
    value = _const_value(node)
    if isinstance(value, bool):
        return {"text": "是" if value else "否", "checks": [], "exact": False}
    return {"text": "条件", "checks": [], "exact": False}


def _option_effects(expr, attrs):
    """提取选项带来的探索经验、灵石消耗、善恶/声望变化。"""
    out = []

    def walk(node):
        if isinstance(node, dict):
            name, index, args = _call_parts(node)
            if name == "随机事件" and index:
                values = _const_args(args) or _expr_ints(args)
                if index == "选项探索经验" and len(values) >= 4:
                    info = attrs.get(str(values[2])) or {}
                    out.append("+%s %s经验" % (values[3], info.get("name") or "探索属性"))
                elif index == "选项扣除灵石" and values:
                    out.append("消耗 %s 灵石" % values[-1])
                elif index == "选项改变善恶值" and values:
                    out.append("善恶 %+d" % values[-1])
                elif index == "选项改变城镇声望" and values:
                    out.append("声望 %+d" % values[-1])
            elif name == "玩家" and index:
                values = _const_args(args) or _expr_ints(args)
                if index == "扣除灵石" and values:
                    out.append("消耗 %s 灵石" % values[-1])
                elif index == "改变善恶值" and values:
                    out.append("善恶 %+d" % values[-1])
                elif index == "增加玩家探索属性" and len(values) >= 2:
                    info = attrs.get(str(values[0])) or {}
                    out.append("+%s %s经验" % (values[-1], info.get("name") or "探索属性"))
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(expr)
    return out


def _option_actions(expr, flows, attrs, quest_names=None):
    """把选项/流程解析成“跳到哪个对话 / 触发哪个结局”的分支列表。"""
    out = []

    def resolve_flow(flow_id, conds, depth, seen, sink=None):
        sink = out if sink is None else sink
        if depth > 12 or flow_id in seen:
            return
        seen.add(flow_id)
        flow = flows.get(flow_id)
        if not isinstance(flow, dict):
            return
        start = len(sink)
        resolve(flow.get("action"), conds, depth + 1, seen, sink)
        produced = sink[start:]
        tail = []
        for nxt in flow.get("nextIds") or []:
            if isinstance(nxt, int):
                resolve_flow(nxt, conds, depth + 1, seen, tail)
        if produced and tail:
            for action in produced:
                if action.get("kind") == "jump":
                    action.setdefault("after", []).extend(tail)
                else:
                    sink.extend(tail)
                    break
        else:
            sink.extend(tail)

    def resolve(node, conds, depth, seen, sink=None):
        sink = out if sink is None else sink
        if depth > 14:
            return
        if isinstance(node, (list, tuple)) and len(node) == 2 and isinstance(node[0], str) and isinstance(node[1], dict):
            tag, payload = node
            if tag == "conditional":
                condition = _condition(payload.get("condition"), attrs, quest_names)
                resolve(payload.get("trueExpression"), conds + [dict(condition, need=True)], depth + 1, seen, sink)
                resolve(payload.get("falseExpression"), conds + [dict(condition, need=False)], depth + 1, seen, sink)
                return
            resolve(payload, conds, depth + 1, seen, sink)
            return
        if isinstance(node, dict):
            name, index, args = _call_parts(node)
            if name == "跳转剧情":
                values = _const_args(args) or _expr_ints(args)
                if values:
                    sink.append({"kind": "jump", "id": values[0],
                                 "sub": values[1] if len(values) > 1 else 0, "conds": conds})
                return
            if name == "流程" and index == "播放立绘AVG组":
                values = _const_args(args) or _expr_ints(args)
                if values:
                    sink.append({"kind": "jump", "id": values[0], "sub": 0, "conds": conds})
                return
            if name == "执行流程":
                values = _const_args(args) or _expr_ints(args)
                if values:
                    resolve_flow(values[0], conds, depth + 1, set(seen), sink)
                return
            if name == "随机事件" and index == "完整奖励结局":
                values = _const_args(args) or _expr_ints(args)
                if values:
                    sink.append({"kind": "ending", "id": values[0], "conds": conds})
                return
            for child in args:
                resolve(child, conds, depth + 1, seen, sink)
            for key in ("func", "target", "trueExpression", "falseExpression"):
                if key in node:
                    resolve(node[key], conds, depth + 1, seen, sink)
            return
        if isinstance(node, list):
            for child in node:
                resolve(child, conds, depth + 1, seen, sink)

    resolve(expr, [], 0, set())
    return out


def _build_tree(quest_id, dialogues, flows, attrs, quest_names=None, max_nodes=160):
    """从奇遇入口对话展开选项树；结局作为叶节点。"""
    keys = sorted(key for key in dialogues if key[0] == quest_id)
    if not keys:
        return None
    by_id = {}
    for key in dialogues:
        by_id.setdefault(key[0], []).append(key)

    def entry_key(dialogue_id, sub):
        candidates = sorted(by_id.get(dialogue_id) or [])
        if not candidates:
            return (dialogue_id, sub or 0)
        target = (dialogue_id, sub or 0)
        if target in dialogues and dialogues[target].get("options"):
            return target
        for key in candidates:
            if dialogues[key].get("options"):
                return key
        return candidates[0]

    def node_text(dialogue_id, key):
        texts = []
        for item in sorted(by_id.get(dialogue_id) or []):
            if item[1] > key[1]:
                continue
            text = _plain(dialogues[item].get("text"))
            if text:
                texts.append(text)
        return _clip("\n".join(texts), 200)

    root = entry_key(quest_id, 0)
    nodes, endings, queue = {}, set(), [root]
    while queue and len(nodes) < max_nodes:
        key = queue.pop(0)
        if key in nodes:
            continue
        row = dialogues.get(key)
        if not isinstance(row, dict):
            continue
        node = {"text": node_text(key[0], key), "options": []}

        def add(option_text, effects, actions):
            for action in actions:
                entry = {"t": option_text, "eff": effects, "conds": action.get("conds") or []}
                if action["kind"] == "jump":
                    target = entry_key(action["id"], action.get("sub") or 0)
                    entry["to"] = "d:%s:%s" % target
                    if target in dialogues and target not in nodes:
                        queue.append(target)
                    after = []
                    for tail in action.get("after") or []:
                        if isinstance(tail, dict) and tail.get("kind") == "ending":
                            after.append("e:%s" % tail["id"])
                            endings.add(tail["id"])
                    if after:
                        entry["after"] = after
                elif action["kind"] == "ending":
                    entry["to"] = "e:%s" % action["id"]
                    endings.add(action["id"])
                else:
                    entry["to"] = ""
                node["options"].append(entry)

        for option in row.get("options") or []:
            if not isinstance(option, dict):
                continue
            label = _clip(_plain(option.get("optionText")), 80)
            effects = _option_effects(option.get("optionExpr"), attrs)
            actions = _option_actions(option.get("optionExpr"), flows, attrs, quest_names)
            if actions:
                add(label, effects, actions)
            else:
                node["options"].append({"t": label, "eff": effects, "conds": [], "to": ""})
        add("", [], _option_actions(row.get("actionOnEnd"), flows, attrs, quest_names))
        next_plot = _int(row.get("nextPlotId"))
        if next_plot:
            target = entry_key(next_plot, 0)
            node["options"].append({"t": "", "eff": [], "conds": [],
                                    "to": "d:%s:%s" % target})
            if target in dialogues and target not in nodes:
                queue.append(target)
        nodes[key] = node
    if not nodes:
        return None
    prefix_keys = [key for key in keys if key != root and (dialogues[key].get("text") or "")]
    intro = _clip(_plain(dialogues[prefix_keys[0]].get("text")), 120) if prefix_keys else ""
    return {
        "root": "d:%s:%s" % root,
        "intro": intro,
        "nodes": {"d:%s:%s" % key: value for key, value in nodes.items()},
        "endings": sorted(endings),
    }


def build_event(tables):
    """奇遇只读元数据：结局、奖励、地点、选项条件、探索属性与剧情路线树。"""
    ending_rows = [r for r in _rows(tables["tbrandomeventending"]) if isinstance(r, dict)]
    if not ending_rows:
        raise ValueError("奇遇结局配置为空")
    quest_table = tables["tbquest"]
    quest_rows = quest_table.get("rows") if isinstance(quest_table, dict) else quest_table
    quests = {}
    for row in _rows(quest_rows):
        if isinstance(row, dict) and row.get("id") is not None:
            quests[_int(row["id"])] = row

    type_names = {}
    for row in _rows(tables["tbitemtype"]):
        if isinstance(row, dict) and row.get("id") is not None:
            type_names[str(_int(row["id"]))] = _text(row.get("typeName"))

    usage = {}
    for row in _rows(tables["tbpillherb"]):
        if isinstance(row, dict) and _int(row.get("item_id")):
            usage.setdefault(str(_int(row.get("item_id"))), set()).add("炼丹药材")
    for row in _rows(tables["tbpillrecipe"]):
        if isinstance(row, dict) and _int(row.get("item_id")):
            usage.setdefault(str(_int(row.get("item_id"))), set()).add("炼丹成品")
    for row in _rows(tables["tbalchemymaterial"]):
        if isinstance(row, dict) and _int(row.get("id")):
            usage.setdefault(str(_int(row.get("id"))), set()).add("炼器材料")
    for row in _rows(tables["tbnpcitemdemandholdtemplate"]):
        if not isinstance(row, dict):
            continue
        for need in row.get("demandItemList") or []:
            if isinstance(need, dict) and _int(need.get("itemId")):
                usage.setdefault(str(_int(need.get("itemId"))), set()).add("NPC 求购")

    items, currency = {}, set()
    for row in _rows(tables["tbitem"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        item_id = _int(row["id"])
        name = _text(row.get("itemName")) or ("物品 %s" % item_id)
        if name == "灵石":
            currency.add(item_id)
        items[str(item_id)] = {
            "name": name, "quality": _int(row.get("quality")),
            "type": type_names.get(str(_int(row.get("itemType"))), ""),
            "price": _int(row.get("price")),
            "desc": _plain(row.get("itemDesc")),
            "required_cultivation": _int(row.get("required_cultivation")),
            "use": sorted(usage.get(str(item_id), [])),
        }

    attrs = {}
    for row in _rows(tables["tbinteractattribute"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        levels = []
        for config in row.get("levelConfigs") or []:
            if isinstance(config, dict) and isinstance(config.get("maxExp"), (int, float)):
                levels.append(_int(config["maxExp"]))
        attrs[str(_int(row["id"]))] = {
            "name": _text(row.get("name")) or ("探索属性 %s" % row["id"]),
            "desc": _text(row.get("desc")), "levels": levels,
        }

    drops = {str(_int(r.get("id"))): r for r in _rows(tables["tbrewarddrop"]) if isinstance(r, dict)}
    spaces = build_spaces(tables)
    realms = build_realms(tables)
    dialogues = {}
    for row in _rows(tables["tbdialogue"]):
        if isinstance(row, dict) and row.get("id") is not None:
            dialogues[(_int(row["id"]), _int(row.get("subId")))] = row
    flows = {}
    for row in _rows(tables["tbgameactionflow"]):
        if isinstance(row, dict) and row.get("id") is not None:
            flows[_int(row["id"])] = row

    events = {}
    for row in ending_rows:
        quest_id = _int(row.get("event_quest_id"))
        if quest_id:
            events.setdefault(quest_id, []).append(row)
    if not events:
        raise ValueError("奇遇事件配置为空")
    candidates = set(events)
    for rows in events.values():
        for row in rows:
            stage = _int(row.get("stage_quest_id"))
            if stage:
                candidates.add(stage)

    # 交互点：tbinteractaction 表达式里引用任务 id，再经 tbspaceinteractui 落到具体场景。
    ui_by_action = {}
    for row in _rows(tables["tbspaceinteractui"]):
        if isinstance(row, dict):
            ui_by_action.setdefault(_int(row.get("interactActionId")), []).append(row)
    interact_hits = {}
    for row in _rows(tables["tbinteractaction"]):
        if not isinstance(row, dict):
            continue
        matched = {value for value in _expr_ints(row.get("interactExpr")) if value in candidates}
        if not matched:
            continue
        spot = _plain(row.get("textInteract"))
        for ui in ui_by_action.get(_int(row.get("id")), []):
            space_id = _int(ui.get("spaceId"))
            if not space_id:
                continue
            for quest_id in matched:
                interact_hits.setdefault(quest_id, []).append(
                    (space_id, spot or _plain(ui.get("textName"))))

    teleport = {}
    for row in _rows(tables["tbrandomeventteleportentry"]):
        if isinstance(row, dict) and row.get("questId") is not None:
            teleport[_int(row.get("questId"))] = _int(row.get("activeEventId"))
    active_spaces = {}
    for row in _rows(tables["tbspaceactiveevent"]):
        if isinstance(row, dict) and row.get("id") is not None:
            active_spaces.setdefault(_int(row.get("id")), []).append(_int(row.get("spaceId")))

    place_names = sorted(
        ((info["name"], int(space_id)) for space_id, info in spaces.items()
         if len(info.get("name") or "") >= 2),
        key=lambda pair: -len(pair[0]))

    def make_location(space_id, spot, conf, via):
        info = spaces.get(str(space_id)) or {}
        if not info:
            return None
        return {
            "space": _int(space_id), "name": info.get("name") or "",
            "path": info.get("path") or [info.get("name") or ""],
            "region": info.get("region") or info.get("name") or "",
            "realm": _int(info.get("realm_id")), "spot": spot or "",
            "conf": conf, "via": via,
        }

    def direct_location(quest_id, stage_ids, text):
        hits = []
        for key in [quest_id] + stage_ids:
            hits.extend(interact_hits.get(key, []))
        if hits:
            space_id, spot = hits[0]
            location = make_location(space_id, spot, "exact", "interact")
            if location:
                return location
        active = teleport.get(quest_id)
        if active:
            for space_id in active_spaces.get(active) or []:
                location = make_location(space_id, "", "exact", "teleport")
                if location:
                    return location
        for key in [quest_id] + stage_ids:
            quest = quests.get(key) or {}
            for value in _expr_ints(quest.get("triggerExpr")):
                if str(value) in spaces:
                    location = make_location(value, "", "inferred", "trigger")
                    if location:
                        return location
        for name, space_id in place_names:
            if name in text:
                return make_location(space_id, "", "inferred", "text")
        return None

    names = {quest_id: _plain((quests.get(quest_id) or {}).get("name")) or ("奇遇 %s" % quest_id)
             for quest_id in events}
    quest_names = {quest_id: _plain((row or {}).get("name")) or ("任务 %s" % quest_id)
                   for quest_id, row in quests.items()}
    parents = {}
    for quest_id, name in names.items():
        parent = 0
        # 父子奇遇按 tbquest 名称的「母名·分支名」前缀归并；tbrandomeventending 没有显式
        # 父事件字段（stage_quest_id 多为空），不依赖 id 步长这类魔法数。
        if "·" in name:
            head = name.split("·", 1)[0].strip()
            parent = next((other for other, other_name in names.items()
                           if other != quest_id and other_name == head), 0)
        parents[quest_id] = parent

    prefixes = {quest_id // 100 for quest_id in events}
    dialogue_texts = {}
    for (dialogue_id, _sub), row in dialogues.items():
        if dialogue_id // 100 not in prefixes:
            continue
        texts = [_plain(option.get("optionText")) for option in (row.get("options") or [])
                 if isinstance(option, dict)]
        texts = [text for text in texts if text]
        if not texts:
            continue
        slot = dialogue_texts.setdefault(dialogue_id, [])
        for text in texts:
            if text not in slot:
                slot.append(text)

    def ending_rewards(drop_id):
        drop = drops.get(str(drop_id))
        if not drop:
            return None
        out, seen = [], set()
        for variant in drop.get("variants") or []:
            if not isinstance(variant, dict):
                continue
            entries = [entry for entry in (variant.get("dropList") or []) if isinstance(entry, dict)]
            weights = [max(0, _int(entry.get("dropWeight"), 1)) for entry in entries]
            total = sum(weights) or len(entries)
            for entry, weight in zip(entries, weights):
                item_id = _int(entry.get("itemId"))
                if not item_id or item_id in seen:
                    continue
                seen.add(item_id)
                low = _int(entry.get("itemCountMin"), 1)
                high = _int(entry.get("itemCountMax"), low)
                chance = (weight * 100.0 / total) if total else 100.0
                info = items.get(str(item_id)) or {}
                out.append({
                    "item": item_id, "name": info.get("name") or ("物品 %s" % item_id),
                    "quality": info.get("quality") or 0, "type": info.get("type") or "",
                    "price": info.get("price") or 0, "use": info.get("use") or [],
                    "desc": info.get("desc") or "",
                    "min": low, "max": high, "weight": weight,
                    "chance": round(chance, 1),
                    "expected": round(chance / 100.0 * (low + high) / 2.0, 2),
                })
        return out

    result, stats = [], {"exact": 0, "inferred": 0, "unknown": 0}
    resolved = {}
    for quest_id in sorted(events):
        rows = events[quest_id]
        quest = quests.get(quest_id) or {}
        stage_ids = sorted({_int(row.get("stage_quest_id")) for row in rows
                            if _int(row.get("stage_quest_id"))})
        desc = _plain(quest.get("description"))
        objective_text = "\n".join(_plain(obj.get("description")) for obj in (quest.get("objectives") or [])
                                   if isinstance(obj, dict))
        location = direct_location(quest_id, stage_ids, desc + "\n" + objective_text)
        tree = _build_tree(quest_id, dialogues, flows, attrs, quest_names)
        endings = []
        for row in sorted(rows, key=lambda r: (_int(r.get("grade")), _int(r.get("id")))):
            drop_id = _int(row.get("reward_drop_id"))
            rewards = ending_rewards(drop_id) if drop_id else []
            grade = _int(row.get("grade"))
            path = _ending_path(row.get("id"), row.get("title"), row.get("designer_note"))
            path = _align_path(path, tree, attrs, items, currency)
            endings.append({
                "id": _int(row.get("id")), "title": _plain(row.get("title"))
                or ("结局 %s" % row.get("id")), "summary": _plain(row.get("summary")),
                "detail": _lines(row.get("detail_lines")), "grade": grade,
                "grade_name": EVENT_GRADE_NAMES.get(grade, "第%s档" % grade),
                "path": path,
                "rewards": rewards or [],
                "reward_ok": True if not drop_id else rewards is not None,
            })
        resolved[quest_id] = location
        result.append({
            "id": quest_id, "name": names[quest_id], "desc": desc,
            "one_off": bool(quest.get("oneOff")), "parent": parents[quest_id],
            "endings": endings, "dialogue": {str(key): value for key, value in dialogue_texts.items()
                                             if key // 100 == quest_id // 100},
            "tree": tree,
            "has_conditions": bool(tree) and any(
                option.get("conds") for node in (tree or {}).get("nodes", {}).values()
                for option in node.get("options") or []),
        })

    by_id = {event["id"]: event for event in result}
    for event in result:
        location = resolved.get(event["id"])
        if location is None and event["parent"] in by_id:
            parent_event = by_id[event["parent"]]
            parent_location = resolved.get(parent_event["id"])
            if parent_location:
                location = dict(parent_location, conf="inferred", via="parent")
        event["location"] = location
        realm = _int(location.get("realm")) if location else 0
        event["realm"] = realm
        event["realm_name"] = realms.get(str(realm)) or ("境界 %s" % realm if realm else "未知境界")
        key = (location or {}).get("conf") or "unknown"
        stats[key] = stats.get(key, 0) + 1
    stats["events"] = len(result)
    stats["endings"] = sum(len(event["endings"]) for event in result)
    stats["endings_with_rewards"] = sum(
        1 for event in result for ending in event["endings"] if ending["rewards"])
    stats["endings_missing_rewards"] = sum(
        1 for event in result for ending in event["endings"] if not ending["reward_ok"])
    stats["with_conditions"] = sum(1 for event in result if event["has_conditions"])
    stats["endings_with_path"] = sum(
        1 for event in result for ending in event["endings"] if ending["path"])
    stats["tree_endings"] = sum(len((event.get("tree") or {}).get("endings") or []) for event in result)
    phases = {}
    for row in _rows(tables["tbcultivaterealm"]):
        if isinstance(row, dict):
            realm_id = _int(row.get("id"))
            for phase in row.get("phases") or []:
                phases[str(_int(phase))] = realm_id
    return {"schema": SCHEMA, "events": result, "realms": realms, "attrs": attrs,
            "currency": sorted(currency), "phases": phases,
            "grade_names": EVENT_GRADE_NAMES, "grade_hint": EVENT_GRADE_HINT,
            "stats": stats}


# 插件统一入口
build = build_event
