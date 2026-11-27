# -*- coding: utf-8 -*-
"""红尘：配置表 -> 模块快照。

只依赖 meta_update 的公共解析函数；不 import 其它模块。
游戏新增红尘任务（type=5 数据行）后重新导出快照即可，不需要改代码。
"""
import json
import re

from meta_update import (
    SCHEMA, _call_parts, _clip, _const_args, _expr_ints, _int,
    _plain, _rows, _text, build_realms, build_spaces,
)
from app import tablekit
from app import acquire

# 层 id → 本境界内层数（29 → 筑基 9 层），避免页面上出现“第 29 层”。
_LAYER_NUMBERS = {}
# 条件别名（条件.XXX）→ 真实表达式；从 tbconditionexpr 自动构建。
_COND_ALIASES = {}
# 探索属性 id → 中文名；解析「探索属性等级(1004)」时不能把内部字段名直接给玩家。
_ATTR_NAMES = {}


def _is_zh():
    return str(getattr(tablekit, "TEXT_LANGUAGE", "zh-Hans")).startswith("zh")


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


def _drop_items(drops, drop_id, depth=0):
    """奖励包 -> [(物品, 最少, 最多)]。奖励包可以嵌套子奖励包，最多跟三层。"""
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
                out.extend(_drop_items(drops, child_id, depth + 1))
    return out


def _flow_rewards(flows, start):
    """顺着流水 nextIds 取出奖励包 / 物品 / 探索属性，认清「提交后到底给了什么」。"""
    drops, items_got, attrs = [], [], []
    seen, queue = set(), [_int(start)]
    while queue and len(seen) < 80:
        flow_id = queue.pop(0)
        if not flow_id or flow_id in seen:
            continue
        seen.add(flow_id)
        flow = flows.get(flow_id) or {}
        name, index, args = _call_parts(flow.get("action"))
        method = index or name or ""
        values = list(_const_args(args))
        if method == "获得奖励" and values:
            drops.append(_int(values[0]))
        elif method == "获取物品" and len(values) >= 2:
            items_got.append((_int(values[0]), _int(values[1], 1)))
        elif method == "增加玩家探索属性" and len(values) >= 2:
            attrs.append((_int(values[0]), _int(values[1])))
        for nxt in flow.get("nextIds") or []:
            queue.append(_int(nxt))
    return drops, items_got, attrs


def _quest_rewards(row, items, drops, flows):
    """一条红尘任务的产出：物品（提交/阶段/剧情）+ 探索属性经验。

    同一件物品可能同时来自奖励包和流水，按 id 合并数量，来源只记一次。
    """
    slots, order = {}, []

    def add(item_id, low, high, source):
        key = str(item_id)
        slot = slots.get(key)
        if slot is None:
            info = items.get(item_id) or {}
            slot = {"item": item_id, "name": info.get("name") or "未识别物品",
                    "quality": _int(info.get("quality")), "min": 0, "max": 0, "sources": []}
            slots[key] = slot
            order.append(slot)
        slot["min"] += max(0, _int(low))
        slot["max"] += max(0, _int(high if high not in (None, "") else low))
        if source not in slot["sources"]:
            slot["sources"].append(source)

    def add_drop(drop_id, source):
        for item_id, low, high in _drop_items(drops, drop_id):
            add(item_id, low, high, source)

    if _int(row.get("rewardId")):
        add_drop(row["rewardId"], "提交")
    for obj in row.get("objectives") or []:
        if isinstance(obj, dict) and _int(obj.get("rewardId")):
            add_drop(obj["rewardId"], "阶段")

    attrs = []
    for field in ("questSubmitFlowId", "questAcqFlowId"):
        flow_id = _int(row.get(field))
        if not flow_id:
            continue
        drop_ids, got_items, got_attrs = _flow_rewards(flows, flow_id)
        for drop_id in drop_ids:
            add_drop(drop_id, "剧情")
        for item_id, count in got_items:
            add(item_id, count, count, "剧情")
        attrs.extend(got_attrs)

    attr_gain = []
    for attr_id, value in attrs:
        name = _ATTR_NAMES.get(str(attr_id)) or ""
        if name and _int(value):
            attr_gain.append({"name": name, "value": _int(value)})
    return order, attr_gain


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
    global _LAYER_NUMBERS
    _LAYER_NUMBERS = {}
    for row in _rows(tables.get("tbcultivatelayer")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        phase_id = str(_int(row.get("phase")))
        name = phase_names.get(phase_id) or realms.get(str(phase_realms.get(phase_id, 0))) or ""
        layer_id = str(_int(row["id"]))
        if name:
            out[layer_id] = name
        local = _int(row.get("layer"))
        if local:
            _LAYER_NUMBERS[layer_id] = local
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


def _canonical_gate(kind, need, text, realms=None, layer_phases=None, phase_names=None):
    """红尘三种条件写法统一成同一句人话：境界/修为都带引号和本境界层数。"""
    if kind == "realm" and need:
        name = (realms or {}).get(str(need))
        if name:
            return "境界达到「%s」" % name
    if kind == "phase" and need:
        # 「修炼阶段达到(2)」的 2 是阶段 id（炼气中期），不是境界 id（筑基期）。
        name = (phase_names or {}).get(str(need))
        if name:
            return "修为达到「%s」" % name
    if kind == "layer" and need:
        name = (layer_phases or {}).get(str(need)) or (phase_names or {}).get(str(need)) or ""
        local = _LAYER_NUMBERS.get(str(need)) or need
        return ("修为达到「%s」（第 %s 层）" % (name, local)) if name \
            else ("修为达到第 %s 层" % local)
    return text


def _layer_text(layer_id, layer_phases=None, phase_names=None):
    lid = str(layer_id)
    local = _LAYER_NUMBERS.get(lid) or lid
    name = (layer_phases or {}).get(lid) or (phase_names or {}).get(lid)
    return ("%s（第 %s 层）" % (name, local)) if name else str(local)


def _humanize_gate(text, realms, layer_phases, phase_names=None):
    """把「修炼阶段达到 2」「层数 ≥ 10」换成境界名/阶段名，避免给玩家看裸数字。"""
    if not text:
        return text
    text = re.sub(r"修炼阶段达到\s*(\d+)",
                  lambda m: "修为达到「%s」" % ((phase_names or {}).get(m.group(1))
                                               or ("第 %s 阶" % m.group(1))),
                  text)
    text = re.sub(r"(?:修炼)?层数达到\s*(\d+)",
                  lambda m: "修为达到 %s" % _layer_text(m.group(1), layer_phases),
                  text)
    text = re.sub(r"境界\s*[≥＞>]\s*(\d+)",
                  lambda m: "境界达到 %s" % (realms.get(m.group(1)) or ("第 %s 阶" % m.group(1))),
                  text)
    text = re.sub(r"(?:修炼)?层数\s*[≥＞>]\s*(\d+)",
                  lambda m: "修为达到 %s" % _layer_text(m.group(1), layer_phases),
                  text)
    return text


def _line_open(group_rows, hc_ids, condition_gates, npcs, quest_names, quest_types, realms,
               layer_phases, phase_names, character):
    """整条线的开启条件：门槛任务 > 接取条件 > 根任务触发条件 > 对话接取 > 无前置。"""
    roots = []
    for row in group_rows:
        qid = _int(row.get("id"))
        trigger = acquire.resolve_aliases(row.get("triggerExpr") or {}, _COND_ALIASES)
        prev = 0
        if _call_parts(trigger)[1] == "任务提交":
            for value in _expr_ints(trigger):
                if _int(value) in hc_ids and _int(value) != qid:
                    prev = _int(value)
                    break
        if not prev:
            roots.append(row)
    # 策划常把真正的解锁层写成隐藏的「XX支线接取门槛」任务，排到最前面优先读它。
    roots.sort(key=lambda r: 0 if re.search(r"接取门槛|Acceptance Requirements",
                                            _plain(r.get("name")) or "") else 1)
    for row in roots:
        if not row.get("acqCondition"):
            continue
        for gate in condition_gates.get(_int(row.get("id"))) or []:
            text = gate.get("text") or ""
            if text:
                kind = gate.get("kind") or ""
                need = _int(gate.get("need"))
                return {"kind": kind, "need": need,
                        "quest": need if kind == "quest" else 0,
                        "text": _canonical_gate(kind, need,
                                                _humanize_gate(text, realms, layer_phases,
                                                               phase_names),
                                                realms, layer_phases, phase_names),
                        "source": gate.get("source") or "acqCondition"}
    # 触发表达式：游戏里所有「任务触发.XXX」写法统一翻成人话，未知写法也要露出来，不能静默丢掉。
    trigger_labels = {
        "进入场景": "进入指定地点后触发",
        "进入任一场景": "进入任意场景后触发",
        "接取条件满足": "满足接取条件后触发",
        "首次加入宗门": "首次加入宗门后触发",
        "剧情组播放完毕": "剧情播放完后触发",
        "修炼层数修为已满": "当前层修为满后触发",
        "新手完成": "完成新手引导后触发",
    }
    for row in roots:
        trigger = acquire.resolve_aliases(row.get("triggerExpr") or {}, _COND_ALIASES)
        call = _call_parts(trigger)[1]
        if call == "NPC好感度达到":
            values = [int(v) for v in _const_args(_call_parts(trigger)[2])
                      if isinstance(v, (int, float))]
            need = values[-1] if values else 0
            return {"kind": "favor", "need": need,
                    "text": ("与 NPC 好感达到 %d 后触发" % need) if need else "好感达到后触发",
                    "source": "triggerExpr"}
        if call in trigger_labels:
            return {"kind": call, "text": trigger_labels[call], "source": "triggerExpr"}
        if call and _call_parts(trigger)[0] == "任务触发" \
                and call not in ("任务提交", "修炼阶段达到", "修炼层数达到", "境界达到"):
            return {"kind": "unknown", "text": "触发条件：%s" % call, "source": "triggerExpr"}
    for row in roots:
        trigger = acquire.resolve_aliases(row.get("triggerExpr") or {}, _COND_ALIASES)
        if _call_parts(trigger)[1] not in ("任务提交", "修炼阶段达到", "修炼层数达到", "境界达到"):
            continue
        parsed = _expr_gate(trigger, npcs, quest_names, quest_types) or {}
        text = parsed.get("text") or ""
        if text:
            kind, need = parsed.get("kind") or "", _int(parsed.get("need"))
            call = _call_parts(trigger)[1]
            if call == "修炼阶段达到":
                # 参数是阶段 id（2 = 炼气中期），不能当境界 id（2 = 筑基期）。
                kind = "phase"
                nums = [int(v) for v in _const_args(_call_parts(trigger)[2])
                        if isinstance(v, (int, float))]
                need = nums[0] if nums else need
            elif call == "修炼层数达到":
                kind = "layer"
                nums = [int(v) for v in _const_args(_call_parts(trigger)[2])
                        if isinstance(v, (int, float))]
                need = nums[0] if nums else need
            return {"kind": kind, "need": need,
                    "quest": need if kind == "quest" else 0,
                    "text": _canonical_gate(kind, need,
                                            _humanize_gate(text, realms, layer_phases,
                                                           phase_names),
                                            realms, layer_phases, phase_names),
                    "source": "triggerExpr"}
    for row in roots:
        if _int(row.get("acqSource")) == 1:
            return {"kind": "dialogue", "text": "与「%s」对话接取" % character,
                    "source": "dialogue"}
    return {"kind": "none", "text": "无需前置（剧情自动出现）", "source": "auto"}


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
        if lname == "玩家" and lindex in ("探索属性等级", "检定探索属性等级"):
            # 属性 id 在左侧调用的参数里（1004 = 辩道），不能把「探索属性等级」当属性名。
            inner = [int(v) for v in _const_args(largs) if isinstance(v, (int, float))]
            attr_id = inner[0] if inner else 0
            name = _ATTR_NAMES.get(str(attr_id)) or "属性"
            return {"kind": "attr", "attr_name": name, "need": need,
                    "text": "%s≥%d" % (name, need)}
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


def _clean_quest_refs(text, names):
    """描述里的「任务800300」换成任务名，避免把内部编号直接展示给玩家。"""
    if not text:
        return text

    def repl(match):
        name = (names or {}).get(_int(match.group(1)))
        if not name:
            return "后续任务" if _is_zh() else "a later quest"
        return ("任务「%s」" if _is_zh() else "quest “%s”") % name

    text = re.sub(r"任务\s*(\d+)", repl, text)
    return re.sub(r"Quest\s*(\d+)", repl, text, flags=re.I)


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

    m = re.search(r"_AFTER_(\d+)\s*$", upper)
    if m:
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
            local = _LAYER_NUMBERS.get(str(layer_id)) or layer_id
            layer_name = (layer_phases.get(str(layer_id))
                          or phase_names.get(str(layer_id))
                          or "")
            text, kind, need = (("境界达到 %s（第 %d 层）" % (layer_name, local)) if layer_name
                                else ("修炼层数 ≥ %d" % local)), "layer", layer_id
        elif (m := re.search(r"_(GE|LT|EQ)_(\d+)\s*$", upper)):
            symbol = {"GE": "≥", "LT": "＜", "EQ": "＝"}[m.group(1)]
            text, need = "属性%s%d" % (symbol, int(m.group(2))), int(m.group(2))

    if not text:
        parsed = _expr_gate(acquire.resolve_aliases(cond_row.get("condition"), _COND_ALIASES),
                            npcs, quest_names, quest_types)
        if parsed:
            text = parsed.get("text") or ""
            kind, need = parsed.get("kind") or "", _int(parsed.get("need"))
            attr_name = parsed.get("attr_name") or ""
    # 兜底：条件树里偶尔会产出「境界≥9」这种裸 id，必须翻成玩家认识的境界名。
    if text:
        text = re.sub(
            r"境界\s*[≥＞>]\s*(\d+)",
            lambda m: "境界 ≥ %s" % (realms.get(m.group(1)) or ("第 %s 阶" % m.group(1))),
            text)
        text = re.sub(
            r"(?:修炼)?层数\s*[≥＞>]\s*(\d+)",
            lambda m: "修炼层数 ≥ %s" % _layer_text(m.group(1), layer_phases, phase_names),
            text)
    grey = _plain(grey_text)
    # 「玩家.探索属性等级(灵机) ≥ 10」比的是等级，不是原始属性值；
    # 标记出来，扫描时用等级换算，避免界面上出现「当前 784」这种裸经验值。
    expression = json.dumps(acquire.resolve_aliases(cond_row.get("condition"), _COND_ALIASES),
                            ensure_ascii=False)
    if kind == "attr" and "探索属性等级" in expression:
        gate["level"] = True
    text = _canonical_gate(kind, need, text, realms, layer_phases, phase_names)
    # 属性/灵石统一成「体魄 ≥ 5 级 / 灵石 ≥ 100」；游戏灰字有时把选项名混进来
    # （「强行撞门（体魄≥5级）」），不能直接当任务门槛展示。
    symbol = {"GE": "≥", "GT": ">", "LT": "<", "EQ": "="}.get(
        (re.search(r"_(GE|GT|LT|EQ)_(\d+)\s*$", upper) or [None, "GE"])[1], "≥")
    if kind == "attr" and attr_name and need:
        text = ("%s %s %d 级" if gate.get("level") else "%s %s %d") % (attr_name, symbol, need)
    elif kind == "money" and need:
        text = "灵石 %s %d" % (symbol, need)
    elif kind == "favor" and need:
        text = "好感 %s %d" % (symbol, need)
    display = text if text and text != "附加条件" else (grey or text or "附加条件")
    gate.update({"text": display, "alias_text": text, "kind": kind,
                 "need": need, "attr_name": attr_name})
    return gate


_FEMALE_LINE = re.compile(r"女主\s*[-－—~～]\s*(.+?)\s*支线")


def _character_of_group(group):
    m = _FEMALE_LINE.search(str(group or ""))
    if m:
        return m.group(1).strip()
    text = re.sub(r"^(女主|红线|情缘)\s*[-－—]?\s*", "", str(group or ""))
    return re.sub(r"支线\s*$", "", text).strip() or str(group or "未分组")


def _is_role_line(group, group_rows):
    """这组红尘任务该不该当成一条角色线。

    红尘类型里混着不带支线分组的隐藏引导任务（例：81011「乌茉来讯」，
    taskGroup 为空、hidden=true，只是请玩家路过客栈时去歇脚）。按分组硬建线
    会凭空长出一张只有 1 个隐藏节点的角色卡，把 NPC 当成女主展示。
    有正式支线分组名的照常保留；没分组名时，组内只要还有可见任务也保留，
    这样策划换命名方式或新增未分组的真实支线仍会自动出现。
    """
    if _FEMALE_LINE.search(str(group or "")):
        return True
    return any(not row.get("hidden") for row in group_rows)


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
    global _COND_ALIASES
    _COND_ALIASES = {}
    for row in _rows(tables.get("tbconditionexpr")):
        if isinstance(row, dict) and row.get("id") is not None:
            conds[_int(row["id"])] = row
            if row.get("alias") and row.get("condition"):
                _COND_ALIASES[str(row["alias"])] = row["condition"]
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
    global _ATTR_NAMES
    _ATTR_NAMES = attr_names
    # 境界/阶段/层数映射：把「境界≥2」「修炼层数 10」翻成人话（2 → 筑基期，10 → 炼气后期）。
    realms = build_realms(tables)
    realm_phases = _build_realm_phases(tables)
    phase_names = _build_phase_names(tables)
    layer_phases = _build_layer_phases(tables)

    # 奖励：任务提交后给什么，是玩家判断「值不值得走这条线」的关键信息。
    # 数据只在 tbrewarddrop / tbitem / tbgameactionflow 里，缺名称时降级「未识别物品」。
    drops = {str(_int(r.get("id"))): r for r in _rows(tables.get("tbrewarddrop"))
             if isinstance(r, dict) and r.get("id") is not None}
    flows = {_int(r.get("id")): r for r in _rows(tables.get("tbgameactionflow"))
             if isinstance(r, dict) and r.get("id") is not None}
    item_type_names = {}
    for row in _rows(tables.get("tbitemtype")):
        if isinstance(row, dict) and row.get("id") is not None:
            item_type_names[str(_int(row["id"]))] = _text(row.get("typeName")) or _text(row.get("name")) or ""
    items = {}
    for row in _rows(tables.get("tbitem")):
        if isinstance(row, dict) and row.get("id") is not None:
            items[_int(row["id"])] = {
                "name": _text(row.get("itemName")) or "未识别物品",
                "quality": _int(row.get("quality")),
                "type": item_type_names.get(str(_int(row.get("itemType"))), ""),
                "price": _int(row.get("price")),
            }

    # 对话按 id 汇总（同一段剧情分散在多个 subId 行）。
    options_by_dialogue, acq_gates, dialogue_targets = {}, {}, {}
    dialogue_ids = set()
    for row in _rows(tables.get("tbdialogue")):
        if not isinstance(row, dict):
            continue
        did = _int(row.get("id"))
        dialogue_ids.add(did)
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
            if targets:
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

    # 对话挂在哪个任务的 objective 流水上：慕云栖的分支对话 id 不等于任务 id，
    # 必须顺着 activeFlowId 找回所属任务，分支才能接回主线，而不是被当成独立故事线。
    dialogue_owner = {}
    for row in all_rows:
        for obj in row.get("objectives") or []:
            if not isinstance(obj, dict):
                continue
            for field in ("activeFlowId", "completeFlowId", "submitFlowId", "finishFlowId"):
                fid = _int(obj.get(field))
                if fid in dialogue_ids:
                    dialogue_owner.setdefault(fid, _int(row.get("id")))

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
    line_groups = [(group, group_rows) for group, group_rows in sorted(grouped.items())
                   if _is_role_line(group, group_rows)]
    for group_index, (group, group_rows) in enumerate(line_groups):
        npc_id, character = _line_npc(group, group_rows, npcs)
        npc_info = npcs.get(npc_id) or {}
        # 分组名是策划写的中文（如「慕云栖」），显示名优先用 NPC 表里的当前语言名。
        character = npc_info.get("name") or character
        raw_by_id = {_int(r["id"]): r for r in group_rows}
        line_quests = []
        for row in group_rows:
            qid = _int(row["id"])
            trigger = acquire.resolve_aliases(row.get("triggerExpr") or {}, _COND_ALIASES)
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
            # 隐藏的「接取门槛」只是配置里的解锁说明，不当成任务节点展示。
            qname = _plain(row.get("name")) or ""
            if row.get("hidden") and re.search(r"接取门槛|Acceptance Requirements", qname):
                continue
            rewards, attr_gain = _quest_rewards(row, items, drops, flows)
            line_quests.append({
                "id": qid,
                "name": _plain(row.get("name")) or ("红尘 %s" % qid),
                "desc": _clip(_clean_quest_refs(_plain(row.get("description")), quest_names), 200),
                "group": group,
                "prev": prev, "next": [], "depth": 0,
                "branch": False, "branch_key": "", "branch_with": [],
                "hidden": bool(row.get("hidden")),
                "acq_source": _int(row.get("acqSource")),
                "giver": {"id": giver_id, "name": npcs.get(giver_id, {}).get("name", "")} if giver_id else None,
                "gates": gates, "options": options,
                "rewards": rewards, "attr_gain": attr_gain,
            })
        by_id = {q["id"]: q for q in line_quests}

        condition_gates = {}
        for q in line_quests:
            for g in q["gates"]:
                if g.get("source") == "acqCondition":
                    condition_gates.setdefault(q["id"], []).append(g)
        open_info = _line_open(group_rows, hc_ids, condition_gates, npcs, quest_names,
                               quest_types, realms, layer_phases, phase_names, character)
        # 来自 triggerExpr 的线级门槛（如念乔的「修炼阶段达到 2」）也要参与状态判定，
        # 否则整条线会被误判成「可接取」。
        if open_info.get("source") == "triggerExpr" and open_info.get("kind") in (
                "realm", "phase", "layer", "quest", "favor", "money", "attr"):
            gate = {"alias": "", "alias_text": open_info["text"], "text": open_info["text"],
                    "kind": open_info["kind"], "need": open_info.get("need") or 0,
                    "npc": 0, "attr_name": "", "source": "lineOpen"}
            for q in line_quests:
                if all(g.get("text") != gate["text"] for g in q["gates"]):
                    q["gates"].append(gate)

        all_by_id = {_int(row["id"]): row for row in all_rows
                     if isinstance(row, dict) and row.get("id") is not None}

        def _raw_prev(qid, seen=None):
            seen = seen if seen is not None else set()
            row = all_by_id.get(qid)
            if not row or qid in seen:
                return 0
            seen.add(qid)
            trigger = acquire.resolve_aliases(row.get("triggerExpr") or {}, _COND_ALIASES)
            if _call_parts(trigger)[1] == "任务提交":
                for value in _expr_ints(trigger):
                    value = _int(value)
                    if value and value != qid:
                        return value
            return 0

        def _anchor(qid):
            """分支对话的所属任务可能不在本角色线里，沿着它的前置一路找到本线节点。"""
            seen = set()
            while qid and qid not in by_id and qid not in seen:
                seen.add(qid)
                qid = _raw_prev(qid)
            return qid if qid in by_id else 0

        def _similar_parent(qid):
            """实在找不到前置时，退回同编号段的最近节点，别把分支甩到单独的“对话分支”里。"""
            text = str(qid)
            best = 0
            for other in by_id:
                label = str(other)
                if other < qid and len(label) < len(text) and text.startswith(label):
                    best = max(best, other)
            return best

        # 对话分支：同一段对话的多个选项各接取一个任务 => 互斥。
        branch_defs = []
        for did, targets in dialogue_targets.items():
            parent = did if did in by_id else _anchor(_int(dialogue_owner.get(did)))
            if parent not in by_id:
                parent = _similar_parent(did)
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
                if not q["prev"] and parent in by_id:
                    q["prev"] = parent
            branch_defs.append({"key": key, "parent": parent if parent in by_id else 0,
                                "members": sorted(members),
                                "names": names, "kind": "对话选项"})

        # 单目标选项也补全前置。
        for did, options in options_by_dialogue.items():
            parent = did if did in by_id else _anchor(_int(dialogue_owner.get(did)))
            if parent not in by_id:
                parent = _similar_parent(did)
            if parent not in by_id:
                continue
            for option in options:
                for target in option["to"]:
                    if target in by_id and not by_id[target]["prev"]:
                        by_id[target]["prev"] = parent

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

        # 分支汇合点：按“每个成员自己的提交流水”解析后续。不能把同组不同成员的
        # 目标合并成并集——例如「当众驳斥/骤然相袭 → 焰下交锋」，
        # 「殿檐暗路 → 虚火侵脉」，合并后会错画成两条路线汇合。
        for definition in branch_defs:
            member_next = {}
            for qid in definition["members"]:
                raw = raw_by_id.get(qid) or {}
                targets = []
                for field in ("questSubmitFlowId", "questAcqFlowId"):
                    fid = _int(raw.get(field))
                    if not fid:
                        continue
                    for target in flow_targets.get(fid, []):
                        if (target in by_id and target not in definition["members"]
                                and target not in targets):
                            targets.append(target)
                member_next[qid] = sorted(targets)
            definition["member_next"] = member_next
            merged = []
            for targets in member_next.values():
                for target in targets:
                    if target not in merged:
                        merged.append(target)
            definition["next"] = sorted(merged)

        # 深度（链上的环数），用于前端分列。
        for q in line_quests:
            depth, seen, cur = 1, {q["id"]}, q
            while cur["prev"] in by_id and cur["prev"] not in seen:
                seen.add(cur["id"])
                cur = by_id[cur["prev"]]
                depth += 1
            q["depth"] = depth
        line_quests.sort(key=lambda q: (q["depth"], q["id"]))

        # 线级解锁门槛：引用本线之外任务（主线/支线）的 gate 是整条线的入口条件，
        # 例如云嫣线「已提交过主线·天帷之破」。这类 gate 只挂在入口任务上，但实际
        # 整条线都被它锁住——把它下发给线内所有任务，避免无前置的任务被误判「可接取」。
        line_entry_gates = []
        for q in line_quests:
            for g in q["gates"]:
                if g.get("kind") == "quest" and _int(g.get("need")) not in hc_ids \
                        and g not in line_entry_gates:
                    line_entry_gates.append(g)
        if line_entry_gates:
            for q in line_quests:
                for g in line_entry_gates:
                    if g not in q["gates"]:
                        q["gates"].append(g)

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
            member_next = definition.get("member_next") or {}
            if member_next:
                for member, targets in member_next.items():
                    for target in targets:
                        edges.append({"from": member, "to": target, "kind": "merge",
                                      "condition": "", "label": "汇合", "gate": None})
            else:
                for target in definition.get("next") or []:
                    for member in definition["members"]:
                        edges.append({"from": member, "to": target, "kind": "merge",
                                      "condition": "", "label": "汇合", "gate": None})

        lines.append({
            "group": group, "name": character,
            "npc_id": npc_id, "portrait": npc_info.get("portrait") or "",
            "color": line_colors[group_index % len(line_colors)],
            "quests": line_quests,
            "open": open_info,
            "roots": [q["id"] for q in line_quests if q["depth"] == 1],
            "edges": edges,
            "branches": [{"key": d["key"], "parent": d["parent"], "members": d["members"],
                          "names": d["names"], "next": d.get("next") or [],
                          "member_next": d.get("member_next") or {}, "kind": d["kind"]}
                         for d in branch_defs],
            "stats": {"total": len(line_quests),
                      "with_rewards": sum(1 for q in line_quests if q["rewards"] or q["attr_gain"]),
                      "with_gates": sum(1 for q in line_quests if q["gates"] or q["options"])},
        })
        all_quests.extend(line_quests)

    stats = {
        "lines": len(lines), "quests": len(all_quests),
        "with_rewards": sum(1 for q in all_quests if q["rewards"] or q["attr_gain"]),
        "with_gates": sum(1 for q in all_quests if q["gates"] or q["options"]),
        "gates": sum(len(q["gates"]) + sum(1 for o in q["options"] if o["gate"])
                     for q in all_quests),
        "branches": sum(len(line["branches"]) for line in lines),
    }
    # 属性值 → 等级换算表：门槛写「体魄≥5级」时要用等级比较，不能拿原始数值硬比。
    attr_levels = {}
    for row in _rows(tables.get("tbinteractattribute")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        caps = []
        for cfg in row.get("levelConfigs") or []:
            if isinstance(cfg, dict):
                caps.append(_int(cfg.get("maxExp")))
        attr_levels[str(row.get("id"))] = caps

    # 灵石 id 按「货币类型 + 名字」派生（同名机关道具不算钱），找不到时回退旧 id。
    item_types = {str(_int(row.get("id"))): (_text(row.get("typeName")) or _text(row.get("name")) or "")
                  for row in _rows(tables.get("tbitemtype"))
                  if isinstance(row, dict) and row.get("id") is not None}
    currency = sorted({
        _int(row.get("id")) for row in _rows(tables.get("tbitem"))
        if isinstance(row, dict) and row.get("id") is not None
        and _plain(row.get("itemName")) == "灵石"
        and (item_types.get(str(_int(row.get("itemType")))) in ("货币", "Currency"))
    }) or [50000]

    # 阶段 id → 阶段先后；层数 id → 阶段 id。
    # 「修炼阶段达到」的参数是阶段 id，必须按阶段先后比较，不能拿层号直接比大小。
    phase_order = {}
    for row in _rows(tables.get("tbcultivaterealm")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        realm_id = _int(row.get("id"))
        for order, phase in enumerate(row.get("phases") or []):
            phase_order[str(_int(phase))] = realm_id * 100 + order + 1
    layer_phase = {}
    for row in _rows(tables.get("tbcultivatelayer")):
        if isinstance(row, dict) and row.get("id") is not None:
            layer_phase[str(_int(row["id"]))] = str(_int(row.get("phase")))

    return {
        "schema": SCHEMA, "lines": lines, "quests": all_quests,
        "states": {str(k): v for k, v in HONGCHEN_STATE_NAMES.items()},
        "attr_names": attr_names, "stats": stats,
        "spaces": _space_index(tables),
        "realms": realms, "phases": realm_phases, "phase_names": phase_names,
        "layer_phases": layer_phases, "phase_order": phase_order, "layer_phase": layer_phase,
        "attr_levels": attr_levels,
        "currency": currency,
        "done_states": list(DONE_STATES), "doing_states": list(DOING_STATES),
    }


build = build_hongchen
