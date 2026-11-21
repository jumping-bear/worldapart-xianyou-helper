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
from app import acquire


EVENT_GRADE_NAMES = {1: "上品", 2: "中品", 3: "下品"}
EVENT_GRADE_HINT = "上品结局的平均奖励优于中品，中品优于下品；具体奖励见每条结局。"

# 条件表达式里常出现「拥有物品数量(50000)」这类裸 id；构建时先把物品名/货币表准备好，
# 渲染成「拥有 灵石」而不是「拥有物品 50000 数量」。
_ITEM_NAMES = {}
_CURRENCY = set()


_OP_NAMES = {
    ">=": ">=", "大于等于": ">=", ">": ">", "大于": ">",
    "<": "<", "小于": "<", "<=": "<=", "小于等于": "<=",
    "==": "==", "等于": "==", "!=": "!=",
}


def _layer_maps(tables, realms):
    """层数 id → 阶段名 / 境界 id。

    境界只能由「层 → 阶段 → 境界」推出；直接拿阶段 id 当层号查会得到凡人。
    """
    phase_names, phase_realms = {}, {}
    for row in _rows(tables.get("tbcultivatephase")):
        if isinstance(row, dict) and row.get("id") is not None:
            phase_id = str(_int(row["id"]))
            phase_names[phase_id] = _text(row.get("phase_name")) or ""
            phase_realms[phase_id] = _int(row.get("realm"))
    names, layer_realms, layer_numbers = {}, {}, {}
    for row in _rows(tables.get("tbcultivatelayer")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        phase_id = str(_int(row.get("phase")))
        realm_id = phase_realms.get(phase_id, 0)
        name = phase_names.get(phase_id) or realms.get(str(realm_id)) or ""
        layer_id = str(_int(row["id"]))
        if name:
            names[layer_id] = name
        if realm_id:
            layer_realms[layer_id] = realm_id
        local = _int(row.get("layer"))
        if local:
            layer_numbers[layer_id] = local
    return names, layer_realms, layer_numbers


def _humanize_gate(text, realms, layer_phases):
    """把表达式里的阶段/层数阈值换成境界名和阶段名。"""
    if not text:
        return text
    text = re.sub(r"(?:修炼阶段|境界)\s*(?:>=|≥|达到)\s*(\d+)",
                  lambda m: "境界达到「%s」" % (realms.get(m.group(1)) or ("境界 %s" % m.group(1))),
                  text)
    text = re.sub(r"(?:(?:修炼)?层数|修为)\s*(?:>=|≥|达到)\s*(\d+)",
                  lambda m: "修为达到「%s」" % (layer_phases.get(m.group(1)) or ("第 %s 层" % m.group(1))),
                  text)
    text = text.replace("指定年月日时辰", "在特定时辰")
    return text


def _left_key(node):
    """解析「玩家.境界」这类索引表达式，返回 (拥有者, 字段)。"""
    node = node[1] if isinstance(node, (list, tuple)) and len(node) == 2 \
        and isinstance(node[1], dict) else node
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


def _self_check(node, self_id):
    """交互点的“任务目标未激活 / 非（已提交自身）”是自检，不是给玩家的开启条件。"""
    call, index, args = _call_parts(node)
    ids = {_int(value) for value in _expr_ints(args)}
    if not self_id or self_id not in ids:
        return False
    if call in ("!", "非") or index in ("!", "非"):
        inner = _call_parts(args[0]) if args else ("", "", [])
        if inner[1] in ("任务提交", "任务持有", "任务接取", "任务进行中"):
            return True
    return index in ("任务目标未激活", "任务目标激活中")


def _gate_text(node, attrs, quest_names, realms, layer_phases, layer_numbers, self_id=0):
    """统一走 acquire：奇遇与支线对同一表达式永远得到同一句人话。"""
    return acquire.gate_text(node, {
        "attrs": attrs, "quest_names": quest_names,
        "realms": realms, "layer_phases": layer_phases,
        "layer_local": layer_numbers,
    }, self_id)


def _internal_only_cond(cond):
    """选项条件是否只是奇遇自身的状态自检（不构成玩家门槛）。"""
    text = cond.get("text") or ""
    if cond.get("checks"):
        return False
    if not any(tag in text for tag in ("奇遇进行中", "已接取", "已提交",
                                       "任务进行中", "任务持有", "任务提交", "任务接取")):
        return False
    return not re.search(r"(等级|灵石|层|境界|时辰|声望|好感)\s*[><=≥≤]", text)


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
# 策划备注常把门槛写在句尾，如「帮少女说话　【医术1级 ✓】」；这类标注会随版本过期。
_BRACKET_RE = re.compile(r"\s*【([^】]*)】\s*$")
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
    # 策划备注常把选项缩写成「反问坐庄」，而真实选项是一整句话；
    # 按字符顺序包含关系给一个较高分，避免误挂「以实际选项为准」。
    if len(a) >= 3:
        cursor = 0
        for char in a:
            cursor = b.find(char, cursor)
            if cursor < 0:
                break
            cursor += 1
        else:
            return 0.8
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
    # 策划备注里的「【医术1级 ✓】」会随版本过期（实际选项可能已要求 4 级），
    # 先剥掉旧标注，再按真实选项条件重算，避免同一结局出现两个不同等级。
    bracket = _BRACKET_RE.search(step)
    if bracket:
        step = step[:bracket.start()].strip(" 　")
    match = _THRESHOLD_RE.match(step) or _LEVEL_RE.match(step)
    if match:
        core = match.group(1).strip()
    elif bracket:
        core = step
    else:
        return step
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
    if not match:
        return step
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
    if name == "玩家" and index in ("达到修炼层数", "修炼层数"):
        return {"text": "修为"}
    if name == "玩家" and index in ("修炼阶段", "境界"):
        return {"text": "境界"}
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
            item_id = _int(values[0])
            if item_id in _CURRENCY:
                return {"text": "灵石", "money": True}
            name = _ITEM_NAMES.get(item_id) or "物品"
            return {"text": "拥有 %s" % name, "item": item_id}
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
    if name == "玩家" and index in ("达到修炼层数", "修炼层数"):
        values = _const_args(args) or _expr_ints(args)
        if values:
            return {"text": "修为 >= %s" % _int(values[-1]), "checks": [], "exact": False}
    if name == "玩家" and index in ("修炼阶段", "境界"):
        values = _const_args(args) or _expr_ints(args)
        if values:
            return {"text": "境界 >= %s" % _int(values[-1]), "checks": [], "exact": False}
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
            if name == "流程" and index in ("播放剧情", "播放立绘AVG组"):
                values = _const_args(args) or _expr_ints(args)
                if values:
                    sink.append({"kind": "jump", "id": values[0], "sub": 0, "conds": conds})
                return
            if name == "执行流程":
                values = _const_args(args) or _expr_ints(args)
                if values:
                    resolve_flow(values[0], conds, depth + 1, set(seen), sink)
                return
            if name == "随机事件" and index in ("完整奖励结局", "随机事件结局"):
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


def _flow_actions(flow_id, flows, attrs, quest_names=None):
    """把某个流程当成选项动作来展开，复用 _option_actions 的流程跟随逻辑。"""
    expr = {"func": ["call", {"name": "执行流程",
                              "arguments": [["int", {"value": flow_id}]]}], "args": []}
    return _option_actions(expr, flows, attrs, quest_names)


def _flow_entries(quest_id, flows, attrs, quest_names=None):
    """随机事件入口对白常只有旁白，真正的选项在流程后续的对白里。

    找出“从播放 quest_id 开始”的流程链，按顺序返回对话 id 与直接结局 id。
    多个流程都能播这段剧情时，取对话链最长的一条，避免拿到回顾/摘要流程。
    """
    best = ([], [])
    matches = 0
    for flow_id in sorted(flows):
        if not isinstance(flows[flow_id], dict):
            continue
        actions = _flow_actions(flow_id, flows, attrs, quest_names)
        if not any(action.get("kind") == "jump" and _int(action.get("id")) == quest_id
                   for action in actions):
            continue
        matches += 1
        dialogues, endings, seen = [], [], set()

        def collect(action):
            if not isinstance(action, dict):
                return
            if action.get("kind") == "jump":
                dialogue_id = _int(action.get("id"))
                if dialogue_id and dialogue_id not in seen:
                    seen.add(dialogue_id)
                    dialogues.append(dialogue_id)
            elif action.get("kind") == "ending":
                ending_id = _int(action.get("id"))
                if ending_id and ending_id not in endings:
                    endings.append(ending_id)
            for tail in action.get("after") or []:
                collect(tail)

        for action in actions:
            collect(action)
        if len(dialogues) > len(best[0]):
            best = (dialogues, endings)
        if matches >= 6:
            break
    return best


def _compact_linear(nodes):
    """把“只有一条继续”的旁白节点合并进上一段，只保留真正的选项节点。"""
    def key_of(to):
        try:
            parts = str(to)[2:].split(":")
            return (_int(parts[0]), _int(parts[1]))
        except (IndexError, ValueError):
            return None

    changed = True
    while changed:
        changed = False
        inbound = {}
        for node in nodes.values():
            for option in node.get("options") or []:
                to = option.get("to") or ""
                if to.startswith("d:"):
                    target = key_of(to)
                    if target:
                        inbound[target] = inbound.get(target, 0) + 1
        for key, node in list(nodes.items()):
            options = node.get("options") or []
            if len(options) != 1:
                continue
            option = options[0]
            if option.get("t") or option.get("after"):
                continue
            to = option.get("to") or ""
            if not to.startswith("d:"):
                continue
            target = key_of(to)
            nxt = nodes.get(target)
            if not nxt or inbound.get(target) != 1:
                continue
            node["text"] = (node.get("text") or "") + "\n" + (nxt.get("text") or "")
            node["options"] = nxt.get("options") or []
            nodes.pop(target, None)
            changed = True
            break
    return nodes


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
    # 随机事件（如“新挂的招工牌”）：入口对白只有旁白，选项在流程后续对白里，
    # 先把整条流程链上的对白加入待处理队列，再在无选项的节点上补“继续”。
    flow_chain, flow_endings = _flow_entries(quest_id, flows, attrs, quest_names)
    flow_keys = {}
    flow_links = {}
    for dialogue_id in ([quest_id] + [cid for cid in flow_chain if cid != quest_id]):
        key = entry_key(dialogue_id, 0)
        flow_keys[dialogue_id] = key
        if key != root and key not in nodes:
            queue.append(key)
    while queue and len(nodes) < max_nodes:
        key = queue.pop(0)
        if key in nodes:
            continue
        row = dialogues.get(key)
        if not isinstance(row, dict):
            continue
        node = {"text": node_text(key[0], key), "options": []}

        def add(option_text, effects, actions):
            entries, seen_sigs = [], set()
            for action in actions:
                entry = {"t": option_text, "eff": effects, "conds": action.get("conds") or []}
                tail_ids, tail_endings = [], []

                def collect_tail(items):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        if item.get("kind") == "jump":
                            tail_ids.append(_int(item.get("id")))
                        elif item.get("kind") == "ending":
                            tail_endings.append(_int(item.get("id")))
                        collect_tail(item.get("after") or [])

                def linear_chain(items):
                    """随机事件流程把后续对白串在 after 里；只有单链时才逐段接“继续”。"""
                    out = []
                    while (isinstance(items, list) and len(items) == 1
                           and isinstance(items[0], dict) and items[0].get("kind") == "jump"):
                        item = items[0]
                        out.append(_int(item.get("id")))
                        items = item.get("after") or []
                    return out

                if action["kind"] == "jump":
                    target = entry_key(action["id"], action.get("sub") or 0)
                    entry["to"] = "d:%s:%s" % target
                    collect_tail(action.get("after") or [])
                    chain = linear_chain(action.get("after") or [])
                    for dialogue_id in dict.fromkeys(tail_ids):
                        if not dialogue_id:
                            continue
                        tail_key = entry_key(dialogue_id, 0)
                        if tail_key in dialogues and tail_key not in nodes:
                            queue.append(tail_key)
                    if tail_endings:
                        unique_endings = list(dict.fromkeys(tail_endings))
                        entry["after"] = ["e:%s" % eid for eid in unique_endings]
                        endings.update(unique_endings)
                    # 单链：动作目标 → 后续对白逐段续接，避免中间旁白变成孤立节点。
                    if chain:
                        previous = _int(action["id"])
                        for dialogue_id in chain:
                            if dialogue_id and previous != quest_id:
                                flow_links[previous] = dialogue_id
                            previous = dialogue_id
                    if target in dialogues and target not in nodes:
                        queue.append(target)
                elif action["kind"] == "ending":
                    entry["to"] = "e:%s" % action["id"]
                    endings.add(action["id"])
                else:
                    entry["to"] = ""
                signature = (entry.get("t"), entry.get("to"), tuple(entry.get("after") or []))
                if signature in seen_sigs:
                    continue
                seen_sigs.add(signature)
                entries.append(entry)
            # 同一选项的成功/失败、随机流程会解析成多条动作：文案相同就合成一条，
            # 结局取并集；目标不同则标记“结果随机”，避免树里出现多个一模一样的选项。
            if not option_text:
                node["options"].extend(entries)
                return
            merged, order = {}, []
            for entry in entries:
                key = entry.get("t")
                if key not in merged:
                    merged[key] = dict(entry)
                    order.append(key)
                    continue
                slot = merged[key]
                if not slot.get("after") and entry.get("after"):
                    slot["after"] = entry["after"]
                elif entry.get("after"):
                    slot["after"] = list(dict.fromkeys(
                        list(slot.get("after") or []) + list(entry["after"])))
                if entry.get("to") != slot.get("to"):
                    slot["multi"] = True
            node["options"].extend(merged[key] for key in order)

        for option in row.get("options") or []:
            if not isinstance(option, dict):
                continue
            label = _clip(_plain(option.get("optionText")), 80)
            # 配置里的「【医术4级 ✓】」是写死的旧标注，容易和实时条件冲突；
            # 去掉方括号后缀，统一由前端按真实门槛显示 ✓/✗。
            label = re.sub(r"\s*【[^】]*】\s*$", "", label).strip() or label
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
        # 只由「奇遇进行中 / 已接取 / 已提交」这类内部状态组成的条件，玩家在选项上看不到，
        # 也不影响能不能选；全部过滤掉，避免把自检当成门槛展示。
        for option in node["options"]:
            option["conds"] = [cond for cond in (option.get("conds") or [])
                               if not _internal_only_cond(cond)]
        # 同文案的“条件成功 / 条件不足”两段剧情，在游戏里始终只显示一个选项：
        # 条件只决定走哪段结果，不是“能不能选”。这里合成一条，条件改成结果提示。
        by_label = {}
        for entry in node["options"]:
            label = entry.get("t")
            if label:
                by_label.setdefault(label, []).append(entry)
        for label, group in by_label.items():
            if len(group) != 2:
                continue
            conditioned = [item for item in group if item.get("conds")]
            plain = [item for item in group if not item.get("conds")]
            if len(conditioned) != 1 or len(plain) != 1:
                continue
            main, alt = plain[0], conditioned[0]
            notes = []
            for cond in alt.get("conds") or []:
                for check in cond.get("checks") or []:
                    if check.get("t") != "attr":
                        continue
                    info = attrs.get(str(check.get("a"))) or {}
                    name = info.get("name") or ("属性 %s" % check.get("a"))
                    notes.append("%s %s %s" % (name, check.get("op"), check.get("v")))
            if notes:
                main["note"] = "满足 %s 时另有结果" % " 且 ".join(notes)
            else:
                texts = [cond.get("text") for cond in alt.get("conds") or [] if cond.get("text")]
                if texts:
                    main["note"] = "条件满足时另有结果"
            # 条件分支的目标不能丢：主选项走兜底结果，条件满足时的另一段挂在 alts 上。
            if alt.get("to") or alt.get("after"):
                main.setdefault("alts", []).append({
                    "conds": alt.get("conds") or [],
                    "to": alt.get("to") or "",
                    "after": alt.get("after") or []})
            node["options"] = [item for item in node["options"] if item is not alt]
        nodes[key] = node
    # 流程链补边：没有真实选项的旁白节点自动接到下一段对白；链尾接流程结局。
    ordered_ids = list(flow_keys)
    for index, dialogue_id in enumerate(ordered_ids):
        node = nodes.get(flow_keys[dialogue_id])
        if not node or node.get("options"):
            continue
        if index + 1 < len(ordered_ids):
            next_key = flow_keys[ordered_ids[index + 1]]
            node["options"].append({"t": "", "eff": [], "conds": [],
                                    "to": "d:%s:%s" % next_key})
        elif flow_endings:
            node["options"].append({"t": "", "eff": [], "conds": [], "to": "",
                                    "after": ["e:%s" % eid for eid in flow_endings]})
            endings.update(flow_endings)
    # 选项跳转后的单链对白：目标节点没有真实选项时补“继续”，走到链尾再结算结局。
    for source_id, next_id in flow_links.items():
        node = nodes.get(entry_key(source_id, 0))
        next_key = entry_key(next_id, 0)
        if not node or node.get("options") or next_key not in nodes:
            continue
        node["options"].append({"t": "", "eff": [], "conds": [],
                                "to": "d:%s:%s" % next_key})
    _compact_linear(nodes)
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


def _ending_requirements(tree):
    """反推每个结局的获取条件（只统计“所有走法都带条件”的硬门槛）。

    返回 {结局id: [[条件, ...], ...]}：外层每条是一种走法（或），内层是必须同时满足的条件（且）。
    """
    nodes = (tree or {}).get("nodes") or {}
    root = (tree or {}).get("root") or ""
    if not nodes or root not in nodes:
        return {}
    paths = {}

    def record(ending_id, conds):
        cleaned, seen = [], set()
        for cond in conds:
            key = json.dumps(cond, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(cond)
        paths.setdefault(str(ending_id), {})[tuple(sorted(seen))] = cleaned

    def walk(node_id, acc, seen, depth):
        if depth > 12 or node_id in seen:
            return
        node = nodes.get(node_id)
        if not isinstance(node, dict):
            return
        seen = seen | {node_id}
        for option in node.get("options") or []:
            base = list(acc) + list(option.get("conds") or [])
            branches = [(option.get("to") or "", option.get("after") or [], base)]
            for alt in option.get("alts") or []:
                branches.append((alt.get("to") or "", alt.get("after") or [],
                                 base + list(alt.get("conds") or [])))
            for target, after, conds in branches:
                target = str(target)
                if target.startswith("e:"):
                    record(target[2:], conds)
                elif target.startswith("d:"):
                    walk(target, conds, seen, depth + 1)
                for tail in after:
                    tail = str(tail)
                    if tail.startswith("e:"):
                        record(tail[2:], conds)

    walk(root, [], set(), 0)
    out = {}
    for ending_id, group in paths.items():
        if not group or not all(conds for conds in group.values()):
            continue
        # 同一结局可能有多条走法：短的排前面，最多留 4 条，够玩家判断。
        out[ending_id] = sorted(group.values(), key=lambda conds: len(conds))[:4]
    return out


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

    _ITEM_NAMES.clear()
    _ITEM_NAMES.update({_int(key): value.get("name") for key, value in items.items()})
    _CURRENCY.clear()
    _CURRENCY.update(currency)

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
    layer_phases, layer_realms, layer_numbers = _layer_maps(tables, realms)
    npc_names = {}
    for row in _rows(tables.get("tbnpcbasecfg")):
        if isinstance(row, dict) and row.get("id") is not None:
            npc_names[str(_int(row["id"]))] = _plain(row.get("npcName")) or ""
    npc_homes = {}
    for row in _rows(tables.get("tbinitialspacenpc")):
        if not isinstance(row, dict) or row.get("npcId") is None:
            continue
        info = spaces.get(str(_int(row.get("spaceId")))) or {}
        path = [part for part in (info.get("path") or []) if part]
        if path:
            npc_homes[str(_int(row["npcId"]))] = " / ".join(path)
    cond_rows, cond_aliases = {}, {}
    for row in _rows(tables.get("tbconditionexpr")):
        if isinstance(row, dict) and row.get("id") is not None:
            cond_rows[str(_int(row["id"]))] = row
            alias = _text(row.get("alias"))
            if alias and row.get("condition"):
                cond_aliases[alias] = row.get("condition")
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
    ui_unlock = {}
    for row in _rows(tables["tbspaceinteractui"]):
        if isinstance(row, dict):
            action_id = _int(row.get("interactActionId"))
            ui_by_action.setdefault(action_id, []).append(row)
            if row.get("unlockConditionExpr"):
                ui_unlock.setdefault(action_id, []).append(row.get("unlockConditionExpr"))
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

    # 场景交互点的开启条件（例：先完成某主线才出现），奇遇也从这里取，和支线同源。
    interact_open = {}
    interact_checks = {}
    for row in _rows(tables.get("tbinteractaction")):
        if not isinstance(row, dict):
            continue
        matched = {value for value in _expr_ints(row.get("interactExpr")) if value in candidates}
        if not matched:
            continue
        node = row.get("openConditionExpr") or {}
        action_id = _int(row.get("id"))
        for quest_id in matched:
            unlock_parts = []
            unlock_trees = []
            for unlock in ui_unlock.get(action_id, []):
                unlock = acquire.resolve_aliases(unlock, cond_aliases)
                text = _gate_text(unlock, attrs, quest_names, realms, layer_phases,
                                  layer_numbers, quest_id)
                if text:
                    unlock_parts.append(text)
                tree = acquire.collect(unlock, {"quest_names": quest_names, "realms": realms,
                                                "layer_phases": layer_phases,
                                                "layer_local": layer_numbers})
                if tree:
                    unlock_trees.append(tree)
            node = acquire.resolve_aliases(node, cond_aliases)
            action_text = _gate_text(node, attrs, quest_names, realms, layer_phases,
                                     layer_numbers, quest_id)
            text = acquire.combine(" 且 ".join(unlock_parts), action_text)
            if text:
                interact_open[quest_id] = acquire.combine(interact_open.get(quest_id), text)
            action_tree = acquire.collect(node, {"quest_names": quest_names,
                                                 "realms": realms, "layer_phases": layer_phases,
                                                 "layer_local": layer_numbers}, quest_id)
            trees = unlock_trees + ([action_tree] if action_tree else [])
            if trees:
                interact_checks[quest_id] = ({"mode": "all", "parts": trees}
                                             if len(trees) > 1 else trees[0])

    def event_open(quest_id, quest):
        """奇遇开启条件与支线共用同一套字段优先级：接取条件 > 触发表达式 > 对话选项 > 交互点。"""
        cond_row = cond_rows.get(str(_int(quest.get("acqCondition")))) or {}
        base_text, base_tree = "", None
        if cond_row:
            cond_expr = acquire.resolve_aliases(cond_row.get("condition"), cond_aliases)
            base_text = _gate_text(cond_expr, attrs, quest_names,
                                   realms, layer_phases, layer_numbers, quest_id)
            base_tree = acquire.collect(cond_expr,
                                        {"quest_names": quest_names,
                                         "realms": realms, "layer_phases": layer_phases,
                                         "layer_local": layer_numbers},
                                        quest_id)

        def _ret(kind, text, source, checks):
            """接取条件与地点/交互门槛同时成立才算开启，不能只取其中一个。"""
            if base_text and text.startswith("无额外开启条件"):
                text = ""
            return {"kind": kind, "text": acquire.combine(base_text, text), "source": source,
                    "checks": _merge_checks(base_tree, checks)}

        def _merge_checks(*trees):
            items = [tree for tree in trees if tree]
            if not items:
                return None
            return {"mode": "all", "parts": items} if len(items) > 1 else items[0]
        trigger = acquire.resolve_aliases(quest.get("triggerExpr") or {}, cond_aliases)
        _name, call, targs = _call_parts(trigger)
        nums = [value for value in _const_args(targs) if isinstance(value, (int, float))]
        if _name == "任务触发" and call == "进入场景" and nums:
            info = spaces.get(str(_int(nums[0]))) or {}
            place = " / ".join([part for part in (info.get("path") or []) if part]) \
                or info.get("name") or ("场景 %s" % _int(nums[0]))
            return _ret("enter_scene", "进入「%s」时自动触发" % place, "triggerExpr", None)
        if call == "任务提交" and nums:
            labels = [quest_names.get(_int(value)) or ("任务 %s" % _int(value)) for value in nums]
            return _ret("quest", "完成「%s」后出现" % "」或「".join(labels), "triggerExpr",
                        {"mode": "any", "parts": [
                            {"kind": "quest", "quest": _int(value), "mode": "任务提交"}
                            for value in nums]})
        if call in ("修炼阶段达到", "境界达到") and nums:
            realm_id = str(_int(nums[0]))
            return _ret("realm", "境界达到「%s」" % (realms.get(realm_id) or ("境界 %s" % realm_id)),
                        "triggerExpr", {"kind": "realm", "need": _int(nums[0])})
        if call == "修炼层数达到" and nums:
            layer_id = str(_int(nums[0]))
            level = _int(nums[0])
            return _ret("layer", "修为达到「%s」（第 %s 层）" % (
                layer_phases.get(layer_id) or ("第 %s 层" % (layer_numbers.get(layer_id) or level)),
                layer_numbers.get(layer_id) or level), "triggerExpr",
                {"kind": "layer", "need": level})
        # 其余「任务触发.XXX」统一翻成人话；没见过的写法也要露出来，不能静默当成无门槛。
        trigger_labels = {
            "进入任一场景": "进入任意场景时自动触发",
            "接取条件满足": "满足接取条件时自动触发",
            "首次加入宗门": "首次加入宗门时触发",
            "剧情组播放完毕": "剧情播放完后触发",
            "修炼层数修为已满": "当前层修为满后触发",
            "新手完成": "完成新手引导后触发",
        }
        if _name == "任务触发":
            if call in trigger_labels:
                return _ret("trigger", trigger_labels[call], "triggerExpr", None)
            if call == "NPC好感度达到" and nums:
                need = _int(nums[-1])
                return _ret("favor", "NPC 好感达到 %s 后触发" % need, "triggerExpr", None)
            if call and call not in ("任务提交", "修炼阶段达到", "修炼层数达到", "境界达到"):
                return _ret("unknown", "触发条件：%s" % call, "triggerExpr",
                            {"kind": "unknown", "text": "触发条件：%s" % call})
        option = _text(quest.get("acqOptionText"))
        npc_id = _int(quest.get("acqNpcID"))
        if option and npc_id:
            home = npc_homes.get(str(npc_id)) or ""
            return _ret("dialogue",
                        "%s与「%s」对话，选择「%s」接取" % (
                            ("在%s" % home) if home else "",
                            npc_names.get(str(npc_id)) or ("NPC %s" % npc_id), option),
                        "dialogue", None)
        if interact_open.get(quest_id):
            return _ret("interaction", interact_open[quest_id], "interaction",
                        interact_checks.get(quest_id))
        return _ret("none", "无额外开启条件，到地点即可触发", "auto", None)
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
        """解析掉落表：ALL 全部获得，ONE 按权重随机其一（见 RewardDropType）。"""
        drop = drops.get(str(drop_id))
        if not drop:
            return None, "all"
        out, seen, mode = [], set(), "all"
        for variant in drop.get("variants") or []:
            if not isinstance(variant, dict):
                continue
            # RewardDropType: ALL=1 / ONE=2 / EACH_REWARD=4 / ONE_REWARD=5
            drop_type = _int(variant.get("type"), 1)
            mode = "one" if drop_type in (2, 5) else "all"
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
                # 全部获得时权重没有概率含义，统一按 100% 展示。
                chance = 100.0 if mode == "all" else (
                    (weight * 100.0 / total) if total else 100.0)
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
        return out, mode

    result, stats = [], {"exact": 0, "inferred": 0, "unknown": 0}
    # 忆海「奇遇留影」条目 id：存档 memoria.unlocked 里有它，说明玩家回忆里已收录，
    # 可重复奇遇的结算记录被重置后仍然能据此判定达成。
    memoria_ids = {}
    for row in _rows(tables.get("tbmemoriaentry")):
        if not isinstance(row, dict) or _int(row.get("category")) != 3:
            continue
        quest_id = _int(row.get("event_quest_id"))
        if quest_id:
            memoria_ids[quest_id] = _int(row.get("id"))
    resolved = {}
    hidden_settlements = 0
    dialogue_ids = {key[0] for key in dialogues}
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
        ending_reqs = _ending_requirements(tree)
        # 委托类（type=3）且完全没有对话的条目是付款/领取后的记账记录，不作为奇遇展示。
        if not tree and quest_id not in dialogue_ids and _int(quest.get("type")) == 3:
            hidden_settlements += 1
            continue
        # 有旁白、但所有节点都没有选项：纯旁白事件，进入后直接结算。
        narration_only = bool(tree) and not any(
            node.get("options") for node in (tree or {}).get("nodes", {}).values())
        endings = []
        for row in sorted(rows, key=lambda r: (_int(r.get("grade")), _int(r.get("id")))):
            drop_id = _int(row.get("reward_drop_id"))
            rewards, reward_mode = ending_rewards(drop_id) if drop_id else (None, "all")
            grade = _int(row.get("grade"))
            path = _ending_path(row.get("id"), row.get("title"), row.get("designer_note"))
            path = _align_path(path, tree, attrs, items, currency)
            endings.append({
                "id": _int(row.get("id")), "title": _plain(row.get("title"))
                or ("结局 %s" % row.get("id")), "summary": _plain(row.get("summary")),
                "detail": _lines(row.get("detail_lines")), "grade": grade,
                "grade_name": EVENT_GRADE_NAMES.get(grade, "第%s档" % grade),
                "path": path,
                "reqs": ending_reqs.get(str(_int(row.get("id")))) or [],
                "rewards": rewards or [], "reward_mode": reward_mode,
                "reward_ok": True if not drop_id else rewards is not None,
            })
        resolved[quest_id] = location
        result.append({
            "id": quest_id, "name": names[quest_id], "desc": desc,
            "open": event_open(quest_id, quest),
            "one_off": bool(quest.get("oneOff")), "parent": parents[quest_id],
            "endings": endings, "dialogue": {str(key): value for key, value in dialogue_texts.items()
                                             if key // 100 == quest_id // 100},
            "tree": tree,
            "narration_only": narration_only,
            "memoria": memoria_ids.get(quest_id, 0),
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
        event["realm_name"] = realms.get(str(realm)) or ("境界%s" % realm if realm else "未知境界")
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
    stats["narration_only"] = sum(1 for event in result if event["narration_only"])
    stats["hidden_settlements"] = hidden_settlements
    phases = {}
    for row in _rows(tables["tbcultivaterealm"]):
        if isinstance(row, dict):
            realm_id = _int(row.get("id"))
            for phase in row.get("phases") or []:
                phases[str(_int(phase))] = realm_id
    return {"schema": SCHEMA, "events": result, "realms": realms, "attrs": attrs,
            "currency": sorted(currency), "phases": phases,
            "layer_phases": layer_phases, "layer_realms": layer_realms,
            "layer_numbers": layer_numbers,
            # 开启条件的判定明细要能叫出任务名，不能把「任务 11143」甩给玩家。
            "quest_names": {str(quest_id): _plain(row.get("name")) or ("任务 %s" % quest_id)
                            for quest_id, row in quests.items()},
            "grade_names": EVENT_GRADE_NAMES, "grade_hint": EVENT_GRADE_HINT,
            "stats": stats}


# 插件统一入口
build = build_event
