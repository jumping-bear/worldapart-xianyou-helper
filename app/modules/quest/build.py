# -*- coding: utf-8 -*-
"""支线：配置表 → 模块快照（自 meta_update.py 原样搬入）。"""
import json
import os
import re

from meta_update import (
    SCHEMA, _call_parts, _clip, _const_args, _expr_ints, _int, _plain, _rows,
    _text, build_realms, build_spaces,
)


QUEST_STATE_NAMES = {
    0: "可接取", 1: "进行中", 2: "已完成", 3: "已提交",
    4: "已失败", 5: "已放弃", 6: "待提交",
}

# 人工注解放在数据文件里（notes.json），游戏更新只改 JSON、不改代码：
# 每条按任务名（首选）或任务 id 关联，名称对不上就自动跳过，不会因为版本更新而报错。
NOTES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes.json")


def _load_notes():
    try:
        with open(NOTES_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("notes") or []
    return [note for note in data if isinstance(note, dict)]


EGG_NOTES = _load_notes()


def _dialogue_context(dialogue_id, sub_id, dialogue_index, npcs):
    """还原选项所在的对话情境：剧情线名、相关 NPC、前后台词、同段所有选项。"""
    subs = sorted((r for r in dialogue_index.get(dialogue_id, []) if isinstance(r, dict)),
                  key=lambda r: _int(r.get("subId")))
    lines = []
    for sub in subs:
        text = _plain(sub.get("text"))
        if text and len(lines) < 5:
            lines.append({"sub": _int(sub.get("subId")), "text": _clip(text, 160)})
    npc_id, npc_name = 0, ""
    for sub in subs:
        candidate = _int(sub.get("npcId"))
        if candidate > 0 and npcs.get(candidate):
            npc_id, npc_name = candidate, npcs[candidate]
            break
    siblings = []
    for sub in subs:
        if _int(sub.get("subId")) == sub_id:
            siblings = [_text(o.get("optionText")) for o in (sub.get("options") or [])
                        if isinstance(o, dict) and _text(o.get("optionText"))]
            break
    # 剧情线名优先用对话里出现的高亮人名（如 <color>云嫣</color>），其次用 NPC 名。
    story = npc_name
    if not story:
        for sub in subs:
            raw = _text(sub.get("text"))
            match = re.search(r"<color=[^>]+>(.*?)</color>", raw, re.S)
            if match:
                story = _plain(match.group(1))
                break
    if not story:
        story = "剧情对话 %s" % dialogue_id
    return {"story": story, "npc": npc_id, "npc_name": npc_name,
            "lines": lines, "siblings": siblings}


def _build_egg_notes(items, quests=None, edges=None):
    """把 notes.json 的注解挂到任务上：先按名字匹配，再按 id 匹配，都对不上就跳过。"""
    out = []
    pool = list((quests or {}).values())
    for note in EGG_NOTES:
        name = str(note.get("quest_name") or "").strip()
        quest_id = _int(note.get("quest_id") or note.get("quest"))
        owner = next((q for q in pool if name and q.get("name") == name), None)
        if owner is None and quest_id:
            owner = next((q for q in pool if _int(q.get("id")) == quest_id), None)
        if owner is None:
            continue
        entry = {key: value for key, value in note.items()
                 if key not in ("quest_name", "quest_id", "item_id")}
        item_id = _int(note.get("item_id") or note.get("item"))
        item = items.get(item_id) or {}
        entry["item_name"] = item.get("name") or (("物品 %s" % item_id) if item_id else "")
        entry["item_desc"] = item.get("desc") or ""
        entry["quest"] = owner["id"]
        entry["quest_name"] = owner["name"]
        entry["hidden"] = bool(owner.get("hidden"))
        entry["from"] = sorted({e["from"] for e in (edges or [])
                                if e.get("to") == entry.get("quest")})
        entry["to"] = sorted({e["to"] for e in (edges or [])
                              if e.get("from") == entry.get("quest")})
        out.append(entry)
    return out


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


OP_ALIAS = {
    ">=": "大于等于", ">": "大于", "<=": "小于等于", "<": "小于",
    "==": "等于", "!=": "不等于", "&&": "且", "||": "或",
    "!": "非", "and": "且", "or": "或", "not": "非",
}
CMP_SYMBOL = {"大于等于": "≥", "大于": ">", "小于等于": "≤",
              "小于": "<", "等于": "=", "不等于": "≠"}
LOGIC_NAMES = ("且", "或")
NEG_NAME = "非"
MISSING_QUEST_NAME = "未收录任务"


def _quest_condition(cond, npcs, quest_names=None, attr_names=None, realms=None,
                     self_id=0, exclusive=None):
    """把接取条件表达式转成可判定的结构：好感度、城镇声望、境界、修炼阶段等。"""
    if not isinstance(cond, dict):
        return None
    root = _cond_leaf(cond.get("condition"), npcs, quest_names, attr_names,
                      realms, self_id, exclusive)
    if not root:
        return None
    checks, modes = [], set()

    def flatten(part):
        if part.get("parts"):
            modes.add(part.get("mode") or "all")
            for child in part["parts"]:
                flatten(child)
        else:
            checks.append(part)

    flatten(root)
    if not checks:
        return None
    mode = "single"
    if len(checks) > 1:
        mode = "mixed" if len(modes) > 1 else (next(iter(modes)) if modes else "all")
    return {"id": _int(cond.get("id")), "mode": mode, "checks": checks,
            "text": root.get("text") or " 且 ".join(check.get("text") or "" for check in checks)}


def _left_subject(node, npcs, attr_names=None):
    """比较式左侧的主语：属性名 / 境界 / 好感度对象，去掉机器函数名。"""
    name, index, args = _call_parts(node)
    if not index and isinstance(node, dict) and node.get("index"):
        index = _expr_string(node["index"]) or index
    values = _const_args(args)
    if not values and isinstance(node, dict):
        # 指定NPC(100121).境界 这类写法：参数挂在 target 的 call 里。
        target = node.get("target")
        if isinstance(target, (list, tuple)) and len(target) == 2:
            _inner_name, _inner_index, inner_args = _call_parts(target)
            values = _const_args(inner_args)
    if name == "玩家" and index:
        if index in ("探索属性等级", "属性等级"):
            attr_id = _int(values[0]) if values else 0
            return {"label": (attr_names or {}).get(attr_id) or "属性",
                    "kind": "attr", "attr": attr_id}
        if index == "境界":
            return {"label": "你的境界", "kind": "realm"}
        if index == "修炼阶段":
            return {"label": "你的修炼阶段", "kind": "phase"}
        if index in ("达到修炼层数", "修炼层数"):
            return {"label": "你的修炼层数", "kind": "layer"}
        if index == "灵石":
            return {"label": "灵石", "kind": "money"}
        if index == "宗门声望":
            return {"label": "宗门声望", "kind": "sect_rep"}
        return {"label": index, "kind": ""}
    if name == "指定NPC" and index:
        npc_id = _int(values[0]) if values else 0
        label = (npcs or {}).get(npc_id) or "该角色"
        if index == "境界":
            return {"label": "%s的境界" % label, "kind": "npc_realm", "npc": npc_id}
        return {"label": "%s的%s" % (label, index), "kind": ""}
    return None


def _merge_negative_pair(parts, quest_names):
    """“未在进行 X 且 尚未完成 X”合并成一句，避免同一任务名出现两次。"""
    if len(parts) != 2:
        return None
    if not all(part.get("neg") and part.get("kind") in ("quest_active", "quest_hold",
                                                         "quest_done") for part in parts):
        return None
    quests = {_int(part.get("quest")) for part in parts}
    kinds = {part.get("kind") for part in parts}
    if len(quests) != 1 or "quest_done" not in kinds:
        return None
    if kinds - {"quest_active", "quest_hold", "quest_done"}:
        return None
    quest_id = next(iter(quests))
    label = (quest_names or {}).get(quest_id) or MISSING_QUEST_NAME
    text = "「%s」未在进行且未完成" % label
    return {"kind": "quest_none", "quest": quest_id, "need": 0,
            "text": text, "pos_text": text, "neg_text": text}


def _collapse_done_texts(texts):
    """“完成「A」 或 完成「B」”→“完成「A」 或 「B」”，少重复一次动词。"""
    if len(texts) > 1 and all(text.startswith("完成「") for text in texts):
        return [texts[0]] + [text[2:] for text in texts[1:]]
    return texts


def _join_cond(parts, mode, quest_names=None):
    """拼条件文本：不同层级的且/或要加括号，避免语义被读反。"""
    if mode == "all":
        merged = _merge_negative_pair(parts, quest_names)
        if merged:
            return merged["text"]
    joiner = " 且 " if mode == "all" else " 或 "
    out = []
    for part in parts:
        text = part.get("text") or ""
        if part.get("parts") and (part.get("mode") or "all") != mode:
            text = "（%s）" % text
        out.append(text)
    if mode == "any" and all(not part.get("parts") and (part.get("kind") or "") == "quest_done"
                             for part in parts):
        out = _collapse_done_texts(out)
    return joiner.join(out)


def _quest_refs(node):
    """收集条件里引用到的任务：[(id, kind)]。"""
    out = []
    if not isinstance(node, dict):
        return out
    kind = node.get("kind") or ""
    if kind in ("quest_done", "quest_hold", "quest_accepted", "quest_active", "quest_none"):
        out.append((_int(node.get("quest")), kind))
    for part in node.get("parts") or []:
        out.extend(_quest_refs(part))
    for child in node.get("children") or []:
        out.extend(_quest_refs(child.get("leaf") or child))
    return out


def _negate_leaf(leaf):
    """单个条件取反：保留可判定字段，文本切到反义说法。"""
    out = dict(leaf)
    neg = not leaf.get("neg", False)
    out["neg"] = neg
    if neg:
        out["text"] = leaf.get("neg_text") or ("不满足：%s" % (leaf.get("text") or "条件"))
    else:
        out["text"] = leaf.get("pos_text") or leaf.get("text") or "条件"
    return out


def _node_leaves(node):
    """把扁平 parts 或嵌套 children 统一取成叶子列表。"""
    if node.get("parts"):
        return list(node["parts"])
    out = []
    for child in node.get("children") or []:
        if child.get("op"):
            out.extend(_node_leaves(child))
        elif child.get("leaf"):
            out.append(child["leaf"])
    return out


def _negate_cond(inner, self_id, exclusive, quest_names):
    """对整组条件取反。支线里常见「非（持有一条任务或其已完成）」＝两选项互斥。"""
    parts = _node_leaves(inner)
    refs = _quest_refs(inner)
    same = {quest_id for quest_id, _kind in refs}
    if parts and len(same) == 1 and all(kind in ("quest_hold", "quest_done") for _q, kind in refs):
        quest_id = next(iter(same))
        label = (quest_names or {}).get(quest_id) or MISSING_QUEST_NAME
        if quest_id in ((exclusive or {}).get(self_id) or set()):
            text = "与「%s」二选一" % label
        else:
            text = "「%s」未在进行且未完成" % label
        return {"kind": "quest_none", "quest": quest_id, "need": 0, "text": text,
                "pos_text": text, "neg_text": text}
    if not parts:
        return _negate_leaf(inner)
    texts = [part.get("text") or "" for part in parts]
    if inner.get("mode") == "any" or inner.get("op") == "or":
        text = "%s 都不成立" % "、".join(texts)
    else:
        text = "并非同时满足：%s" % "、".join(texts)
    return {"kind": "", "need": 0, "text": text, "pos_text": text, "neg_text": text}


def _cond_leaf(node, npcs, quest_names=None, attr_names=None, realms=None,
               self_id=0, exclusive=None):
    """单个条件或“且/或”组合，输出可读文本与可判定字段。"""
    node = _unwrap_expr(node)
    name, index, args = _call_parts(node)
    name = OP_ALIAS.get(name, name)
    values = _const_args(args)
    names = quest_names or {}
    if not index and isinstance(node, dict) and node.get("index"):
        index = _expr_string(node["index"]) or index

    if name in LOGIC_NAMES and args:
        mode = "any" if name == "或" else "all"
        parts = [_cond_leaf(item, npcs, names, attr_names, realms, self_id, exclusive)
                 for item in args]
        parts = [item for item in parts if item]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return {"mode": mode, "parts": parts, "text": _join_cond(parts, mode, names)}

    if name == NEG_NAME and args:
        inner = _cond_leaf(args[0], npcs, names, attr_names, realms, self_id, exclusive)
        return _negate_cond(inner, self_id, exclusive, names) if inner else None

    if name == "条件" and isinstance(index, str) and values:
        quest_id = _int(values[0])
        if self_id and quest_id == self_id:
            return None
        label = names.get(quest_id) or MISSING_QUEST_NAME
        table = {
            "任务提交": ("quest_done", "完成「%s」", "尚未完成「%s」"),
            "任务持有": ("quest_hold", "正在进行「%s」", "未在进行「%s」"),
            "任务接取": ("quest_accepted", "已接取过「%s」", "尚未接取「%s」"),
            "任务目标激活中": ("quest_active", "「%s」正在进行", "「%s」未在进行"),
        }
        if index in table:
            kind, pos, neg = table[index]
            return {"kind": kind, "quest": quest_id, "need": 1,
                    "text": pos % label, "pos_text": pos % label, "neg_text": neg % label}
        return {"kind": "", "need": 0, "text": "「%s」%s" % (label, index),
                "pos_text": "「%s」%s" % (label, index),
                "neg_text": "「%s」不满足%s" % (label, index)}

    if name == "NPC" and index == "好感度至少" and len(values) >= 2:
        npc_id, need = _int(values[0]), _int(values[1])
        label = npcs.get(npc_id) or "该角色"
        text = "%s好感度 ≥ %d" % (label, need)
        return {"kind": "favor", "npc": npc_id, "need": need,
                "text": text, "pos_text": text, "neg_text": "不满足：%s" % text}

    if name == "玩家" and isinstance(index, str) and values:
        if index == "城镇声望至少" and len(values) >= 2:
            need = _int(values[1])
            text = "城镇声望 ≥ %d" % need
            return {"kind": "city_rep", "city": _int(values[0]), "need": need,
                    "text": text, "pos_text": text, "neg_text": "不满足：%s" % text}
        # 阈值直接写在参数里：玩家.达到修炼层数(7) / 玩家.境界(2)。
        need = _int(values[-1])
        if index in ("达到修炼层数", "修炼层数"):
            text = "修炼层数 ≥ %d" % need
            return {"kind": "layer", "need": need, "text": text,
                    "pos_text": text, "neg_text": "不满足：%s" % text}
        if index in ("修炼阶段", "境界"):
            kind = "phase" if index == "修炼阶段" else "realm"
            realm_name = (realms or {}).get(str(need))
            subject = "你的修炼阶段" if kind == "phase" else "你的境界"
            text = ("%s ≥ %s" % (subject, realm_name)) if realm_name else ("%s ≥ %d" % (subject, need))
            return {"kind": kind, "need": need, "text": text,
                    "pos_text": text, "neg_text": "不满足：%s" % text}
        if index == "灵石":
            text = "灵石 ≥ %d" % need
            return {"kind": "money", "need": need, "text": text,
                    "pos_text": text, "neg_text": "不满足：%s" % text}

    if name in CMP_SYMBOL and args:
        op = CMP_SYMBOL[name]
        need = _int(values[-1]) if values else 0
        left = _unwrap_expr(args[0])
        subject = _left_subject(left, npcs, attr_names)
        if not subject:
            left_name, left_index, _left_args = _call_parts(left)
            subject = {"label": str(left_index or left_name or "条件"), "kind": ""}
        text = "%s %s %d" % (subject["label"], op, need)
        if subject.get("kind") in ("realm", "phase", "npc_realm"):
            realm_name = (realms or {}).get(str(need))
            if realm_name:
                if subject.get("kind") == "npc_realm" and need == 0:
                    text = "%s仍是凡人（尚未开始修炼）" % subject["label"].replace("的境界", "")
                else:
                    text = "%s %s %s" % (subject["label"], op, realm_name)
        elif subject.get("kind") == "layer" and need == 0:
            text = "%s尚未开始修炼" % subject["label"].replace("的修炼层数", "")
        leaf = {"kind": subject.get("kind") or "", "need": need,
                "text": text, "pos_text": text, "neg_text": "不满足：%s" % text}
        for key in ("attr", "npc"):
            if key in subject:
                leaf[key] = subject[key]
        return leaf

    if name == "指定NPC" and isinstance(index, str) and values:
        npc_id = _int(values[0])
        text = "%s的%s" % (npcs.get(npc_id) or "该角色", index)
        return {"kind": "", "need": 0, "text": text, "pos_text": text,
                "neg_text": "不满足：%s" % text}

    # 兜底也要是人话：绝不出现裸比较、无主语数字或“任务 123”。
    label = index if isinstance(index, str) and index else (name or "条件")
    if values:
        label = "%s 达到 %s" % (label, " / ".join(str(value) for value in values
                                                  if isinstance(value, int)))
    return {"kind": "", "need": 0, "text": label, "pos_text": label,
            "neg_text": "不满足：%s" % label}


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


def _cond_tree(node, npcs, quest_names=None, attr_names=None, realms=None,
               self_id=0, exclusive=None):
    """保留条件表达式的完整嵌套树，供逐条勾叉判定；文本一律人话。"""
    node = _unwrap_expr(node)
    name, index, args = _call_parts(node)
    name = OP_ALIAS.get(name, name)
    names = quest_names or {}
    if not index and isinstance(node, dict) and node.get("index"):
        index = _expr_string(node["index"]) or index
    if name in LOGIC_NAMES and args:
        op = "and" if name == "且" else "or"
        children = []
        for arg in args:
            child = _cond_tree(arg, npcs, names, attr_names, realms, self_id, exclusive)
            if child:
                children.append(child)
        if not children:
            return None
        if len(children) == 1:
            return children[0]
        if op == "and" and all(not child.get("op") for child in children):
            merged = _merge_negative_pair([child.get("leaf") or {} for child in children], names)
            if merged:
                return {"op": "", "children": [], "leaf": merged, "text": merged["text"]}
        joiner = " 且 " if op == "and" else " 或 "
        texts = []
        for child in children:
            text = child.get("text") or ""
            if child.get("op") and child["op"] != op:
                text = "（%s）" % text
            texts.append(text)
        if op == "or" and all(not child.get("op")
                              and (child.get("leaf") or {}).get("kind") == "quest_done"
                              for child in children):
            texts = _collapse_done_texts(texts)
        return {"op": op, "children": children, "text": joiner.join(texts)}
    if name == NEG_NAME and args:
        child = _cond_tree(args[0], npcs, names, attr_names, realms, self_id, exclusive)
        if not child:
            return None
        if not child.get("op"):
            leaf = _negate_leaf(child.get("leaf") or {})
            return {"op": "", "children": [], "leaf": leaf, "text": leaf["text"]}
        leaf = _negate_cond(child, self_id, exclusive, names)
        return {"op": "", "children": [], "leaf": leaf, "text": leaf["text"]}
    leaf = _cond_leaf(node, npcs, names, attr_names, realms, self_id, exclusive)
    if not leaf:
        return None
    return {"op": "", "children": [], "leaf": leaf, "text": leaf.get("text") or "条件"}


def _trigger_phrase(tree, quest_names=None):
    """条件全是“完成某任务”时，给玩家一句“完成 A 或 B 后自动触发”。"""
    if not tree:
        return ""
    names = []

    def walk(node):
        if node.get("op"):
            return all(walk(child) for child in node.get("children") or [])
        leaf = node.get("leaf") or {}
        if leaf.get("kind") != "quest_done":
            return False
        quest_id = _int(leaf.get("quest"))
        names.append((quest_names or {}).get(quest_id) or MISSING_QUEST_NAME)
        return True

    if not walk(tree) or not names:
        return ""
    joiner = "或" if tree.get("op") == "or" else "、"
    return "完成%s后自动触发" % joiner.join("「%s」" % name for name in names)


def _cond_task_refs(tree):
    """从条件树提取任务引用：任务提交→triggered，任务持有/接取→conditional。"""
    out = []

    def walk(node):
        leaf = node.get("leaf") or {}
        kind = leaf.get("kind") or ""
        quest_id = _int(leaf.get("quest"))
        if quest_id and kind in ("quest_done", "quest_hold", "quest_accepted", "quest_active"):
            out.append({"quest": quest_id, "kind": kind, "text": leaf.get("text") or ""})
        for child in node.get("children") or []:
            walk(child)

    if tree:
        walk(tree)
    return out


def _tree_has_kind(tree, kind):
    if not tree:
        return False
    if tree.get("op"):
        return any(_tree_has_kind(child, kind) for child in tree.get("children") or [])
    return (tree.get("leaf") or {}).get("kind") == kind


def _quest_gate(node):
    """触发表达式：完整解析任务提交 / 进入场景 / 接取条件满足 / 好感 / 境界。

    返回兼容旧 gate 的字段，并附 trigger_detail；quests 不再用 >1000 启发式，
    由调用方按本模块任务集合过滤。
    """
    if isinstance(node, (list, tuple)) and len(node) == 2 and isinstance(node[1], dict):
        node = node[1]
    name, index, args = _call_parts(node)
    event = index or (name or "")
    values = _quest_call_args(node, "args")
    if not values:
        values = [_int(value) for value in _expr_ints(node)]

    detail = {"kind": "unknown", "event": event, "label": "", "quests": [],
              "space": 0, "npc": 0, "favor": 0, "layer": 0}
    if event == "任务提交":
        detail.update(kind="quest_submit", quests=[_int(value) for value in values])
        detail["label"] = "完成前置任务后自动触发"
    elif event == "进入场景":
        detail.update(kind="scene_enter", space=_int(values[0]) if values else 0)
        detail["label"] = "进入指定地点后触发"
    elif event == "接取条件满足":
        detail.update(kind="acq_satisfied")
        detail["label"] = "满足条件后自动触发"
    elif event == "NPC好感度达到":
        detail.update(kind="npc_favor", npc=_int(values[0]) if values else 0,
                      favor=_int(values[1]) if len(values) > 1 else 0)
        detail["label"] = "好感度达到要求后触发"
    elif event == "修炼阶段达到":
        detail.update(kind="realm", layer=_int(values[0]) if values else 0)
        detail["label"] = "修炼到指定阶段后触发"

    gate = {"event": event, "quests": detail["quests"], "space": detail["space"],
            "npc": detail["npc"], "favor": detail["favor"], "layer": detail["layer"],
            "trigger_detail": detail}
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


# 章节不写死：group 形如 `XX支线-地区-标题`，`支线` 前面的词就是章节（炼气/筑基/隐藏/以及未来新增的）。
_GROUP_CHAPTER_RE = re.compile(r"^(.{1,8}?)支线\s*[-－—]\s*(.+)$")


def _split_group_name(group, region_names=None):
    """group 名拆成（标题、章节、地区）：`炼气支线-临州-宝鉴不如一见` →（宝鉴不如一见, 炼气, 临州）。"""
    chapter, rest = "支线", group
    matched = _GROUP_CHAPTER_RE.match(group or "")
    if matched:
        chapter, rest = matched.group(1).strip(), matched.group(2)
    rest = rest.replace("—", "-").replace("－", "-")
    rest = re.sub(r"（([^）]+)）", r" · \1", rest)
    parts = [part.strip() for part in re.split(r"-", rest) if part.strip()]
    region = ""
    if len(parts) > 1 and parts[0] in (region_names or set()):
        region = parts[0]
        parts = parts[1:]
    title = " · ".join(parts) or rest or group
    return title, chapter, region


def _clean_chain_name(name):
    name = re.sub(r"（同名路线）$", "", name or "")
    name = re.sub(r"…+线?$", "", name)
    name = re.sub(r"线$", "", name)
    return name.strip() or "支线"


def _chapter_from_realms(ids, quests, realms):
    values = []
    for quest_id in ids:
        values.extend(value for value in quests[quest_id].get("realm_ids") or [] if value > 0)
    if not values:
        # 没配境界 id 的旧任务，用地点所在境界兜底（河望镇 → 炼气），否则同名任务只能标“支线”。
        for quest_id in ids:
            realm = _int((quests[quest_id].get("location") or {}).get("realm"))
            if realm > 0:
                values.append(realm)
    if not values:
        return "支线"
    realm_name = str(realms.get(str(min(values))) or "").replace("期", "").strip()
    return realm_name or "支线"


def _chapter_layout(realms):
    """按境界表顺序给章节排序与配色位，新增境界（如化神之后的版本）无需改代码。"""
    order, names = {}, []
    for key in sorted((realms or {}), key=_int):
        name = str(realms.get(key) or "").replace("期", "").strip()
        if name and name not in names:
            names.append(name)
    for index, name in enumerate(names, 1):
        order[name] = index
    for extra in ("隐藏", "支线"):
        if extra not in order:
            order[extra] = len(order) + 1
    tones = {name: index % 6 for index, name in enumerate(list(order), 0)}
    return order, tones


def _build_storylines(quests, edges, realms, region_names=None, chapter_order=None):
    """把 254 个支线聚成玩家可顺着走的剧情线；同 group 的多条 chain 必须合成一条。"""
    clusters = {}
    for quest_id, quest in quests.items():
        key = ("g:" + quest["group"]) if quest["group"] else ("c:" + quest["chain_id"])
        clusters.setdefault(key, []).append(quest_id)

    out = []
    for key, ids in clusters.items():
        members = set(ids)
        preds = {quest_id: set() for quest_id in ids}
        for quest_id in ids:
            prev = quests[quest_id]["prev"]
            if prev in members and prev != quest_id:
                preds[quest_id].add(prev)
        # 条件触发/提交触发算隐式前置，用于把 70266 接在 70264 之后。
        for edge in edges:
            src, dst = edge["from"], edge["to"]
            if src in members and dst in members and src != dst:
                if edge["kind"] in ("triggered", "conditional") and src != quests[dst]["prev"]:
                    preds[dst].add(src)

        depth = {quest_id: 1 for quest_id in ids}
        for _ in range(len(ids) + 2):
            changed = False
            for quest_id in ids:
                if preds[quest_id]:
                    value = max(depth[src] for src in preds[quest_id]) + 1
                    if value > depth[quest_id] and value <= len(ids) + 1:
                        depth[quest_id] = value
                        changed = True
            if not changed:
                break

        # 同一 group 里的“单环支线”（如再试行针）没有前置，放到主线之后，避免插在开头。
        roots = [quest_id for quest_id in ids if not preds[quest_id]]
        if len(roots) > 1:
            chain_size = {}
            for quest_id in ids:
                chain_id = quests[quest_id]["chain_id"]
                chain_size[chain_id] = chain_size.get(chain_id, 0) + 1
            main_root = max(roots, key=lambda qid: (chain_size[quests[qid]["chain_id"]],
                                                    -quests[qid]["id"]))
            tail = max(depth.values()) + 1
            for quest_id in roots:
                if quest_id != main_root and chain_size[quests[quest_id]["chain_id"]] < chain_size[quests[main_root]["chain_id"]]:
                    depth[quest_id] = tail

        order = sorted(ids, key=lambda qid: (depth[qid], quests[qid]["chain_index"], qid))
        group = quests[order[0]]["group"]
        region = ""
        if group:
            name, chapter, region = _split_group_name(group, region_names)
        else:
            name = _clean_chain_name(quests[order[0]]["chain_name"])
            chapter = _chapter_from_realms(order, quests, realms)
            location = quests[order[0]].get("location") or {}
            region = location.get("region") or ""
            if all(quests[quest_id]["hidden"] for quest_id in order):
                chapter = "隐藏"
        if region and region in name:
            region = ""
        npc_names = []
        for quest_id in order:
            giver = quests[quest_id].get("giver") or {}
            name_value = giver.get("name") or ""
            if name_value and name_value not in npc_names:
                npc_names.append(name_value)
        out.append({"id": key, "name": name, "chapter": chapter, "region": region,
                    "group": group, "quests": order,
                    "depths": {str(qid): depth[qid] for qid in order},
                    "npc": npc_names, "size": len(order), "first": order[0]})
    rank = chapter_order or {}
    out.sort(key=lambda line: (rank.get(line["chapter"], 99),
                               -line["size"], line["first"]))
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
    # 从 tbquesttype 动态识别“支线”类型；type=5 红尘由独立模块负责，显式排除。
    side_types = {_int(quest_type) for quest_type, label in type_names.items()
                  if "支线" in label and "红尘" not in label}
    if not side_types:
        side_types = {2}

    side = [row for row in all_rows if _int(row.get("type")) in side_types]
    if not side:
        raise ValueError("支线任务配置为空")
    # 全表任务名：条件里常引用委托/奇遇任务，翻译时必须能叫出名字，不能出现“任务 5215900”。
    full_quest_names = {}
    for row in all_rows:
        name = _plain(row.get("name"))
        if name:
            full_quest_names[_int(row["id"])] = name
    quest_names = {_int(row["id"]): (_plain(row.get("name")) or "未命名支线")
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
    attr_names = {}
    attr_levels = {}
    for row in _rows(tables.get("tbinteractattribute")):
        if isinstance(row, dict) and row.get("id") is not None:
            attr_id = _int(row["id"])
            attr_names[attr_id] = _text(row.get("name")) or ("属性 %s" % attr_id)
            thresholds = [_int(c.get("maxExp")) for c in (row.get("levelConfigs") or [])
                          if isinstance(c, dict) and isinstance(c.get("maxExp"), (int, float))
                          and _int(c.get("maxExp")) > 0]
            attr_levels[str(attr_id)] = thresholds

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

    # 对话上下文索引：把一个 dialogue 的所有 subId 收集起来，供选项门槛还原“完整对话情境”。
    dialogue_index = {}
    for row in _rows(tables.get("tbdialogue")):
        if isinstance(row, dict) and row.get("id") is not None:
            dialogue_index.setdefault(_int(row["id"]), []).append(row)

    def _raw_quest_refs(node):
        """从原始条件 AST 里取出引用到的任务 id（只用于判断互斥选项）。"""
        out = []

        def walk(value):
            if isinstance(value, dict):
                name, index, args = _call_parts(value)
                if name == "条件" and index in ("任务提交", "任务持有", "任务接取",
                                                 "任务目标激活中"):
                    values = _const_args(args)
                    if values:
                        out.append(_int(values[0]))
                for child in value.values():
                    walk(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    walk(child)

        walk(node)
        return out

    # 同一段对话里两个选项分别接取两个任务，且各自条件排除对方 → 玩家熟悉的“二选一”。
    side_ids = set(quest_names)
    exclusive = {}
    for row in _rows(tables.get("tbdialogue")):
        if not isinstance(row, dict):
            continue
        picked = []
        for option in row.get("options") or []:
            if not isinstance(option, dict):
                continue
            cond_id = _int(option.get("optionCondition"))
            if not cond_id:
                continue
            calls = []
            _quest_walk_calls(option.get("optionExpr"), calls)
            kids = [_int(args[0]) for name, args in calls
                    if name.rsplit(".", 1)[-1] == "接取任务" and args and _int(args[0]) in side_ids]
            if kids:
                picked.append((kids[0], cond_id))
        if len(picked) < 2:
            continue
        for child, cond_id in picked:
            refs = set(_raw_quest_refs((conds.get(cond_id) or {}).get("condition")))
            for other, _other_cond in picked:
                if other != child and other in refs:
                    exclusive.setdefault(child, set()).add(other)
                    exclusive.setdefault(other, set()).add(child)

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
        acq_cond = None
        trigger_text = ""
        if cond_row:
            acq_cond = _quest_condition(cond_row, npcs, full_quest_names, attr_names,
                                        realms, quest_id, exclusive)
            tree = _cond_tree(cond_row.get("condition"), npcs, full_quest_names,
                              attr_names, realms, quest_id, exclusive)
            if acq_cond:
                acq_cond["tree"] = tree
                acq_cond["readable"] = acq_cond["text"]
                acq_cond["mixed"] = bool(tree and tree.get("op") == "not")
                trigger_text = _trigger_phrase(tree, full_quest_names)
        gate = _quest_gate(row.get("triggerExpr"))
        if gate:
            valid_ids = set(quest_names)
            gate["quests"] = [value for value in gate["quests"]
                              if value in valid_ids and value != quest_id]
            gate["trigger_detail"]["quests"] = list(gate["quests"])
            if not (gate["quests"] or gate["space"] or gate["npc"] or gate["layer"]
                    or gate["event"] == "接取条件满足"):
                gate = None
        quests[quest_id] = {
            "id": quest_id,
            "name": _plain(row.get("name")) or "未命名支线",
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
            "trigger_detail": (gate or {}).get("trigger_detail"),
            "trigger_text": trigger_text,
            "option_gates": [],
            "acq_branch_of": 0,
            "acq_branch_siblings": [],
            "prev_options": [],
            "acq_dialogue": acq_dialogues.get(quest_id),
            "acq_flows": [],
        }

    # 对话选项门槛：只保留“选项会接取支线任务”的条目；奇遇/委托/红尘的门槛不进本模块。
    option_gates = {}
    for row in _rows(tables.get("tbdialogue")):
        if not isinstance(row, dict):
            continue
        dialogue_id, sub_id = _int(row.get("id")), _int(row.get("subId"))
        for option in row.get("options") or []:
            if not isinstance(option, dict):
                continue
            cond_id = _int(option.get("optionCondition"))
            if not cond_id:
                continue
            cond_row = conds.get(cond_id)
            if not cond_row:
                continue
            calls = []
            _quest_walk_calls(option.get("optionExpr"), calls)
            children = [_int(args[0]) for name, args in calls
                        if name.rsplit(".", 1)[-1] == "接取任务" and args and args[0]]
            side_children = [child_id for child_id in children if child_id in quests]
            if not side_children:
                continue
            leaf = _cond_leaf(cond_row.get("condition"), npcs, full_quest_names, attr_names,
                              realms, side_children[0], exclusive)
            text = _clip((leaf or {}).get("text") or "无额外条件", 120)
            hint = _text(option.get("optionGreyText"))
            opt_text = _text(option.get("optionText"))
            gate = {"cond": cond_id, "text": text,
                    "dialogue": dialogue_id, "sub": sub_id, "option": opt_text,
                    "hint": hint, "hint_missing": not bool(hint), "children": children,
                    "leaf": leaf or {}, "context": _dialogue_context(
                        dialogue_id, sub_id, dialogue_index, npcs)}
            option_gates[(dialogue_id, sub_id, cond_id, opt_text)] = gate
            for child_id in side_children:
                if gate not in quests[child_id]["option_gates"]:
                    quests[child_id]["option_gates"].append(gate)

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
            name = first["name"]
        elif first["group"]:
            name = first["group"]
        elif len(ids) == 1:
            name = first["name"]
        else:
            givers = {quests[quest_id]["giver"]["name"] for quest_id in ids
                      if quests[quest_id].get("giver") and quests[quest_id]["giver"].get("name")}
            if len(givers) == 1:
                name = next(iter(givers))
            else:
                name = first["name"]
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

    # 统一关系边：前端只用它排脊柱顺序与隐藏连线；节点详情直接从任务行读取。
    edges = []

    def add_edge(src, dst, kind, label="", **extra):
        if not src or not dst or src == dst or src not in quests or dst not in quests:
            return
        if any(e["from"] == _int(src) and e["to"] == _int(dst) for e in edges):
            return
        edge = {"from": _int(src), "to": _int(dst), "kind": kind, "label": label or ""}
        edge.update(extra)
        if edge not in edges:
            edges.append(edge)

    for quest_id, quest in quests.items():
        prev = quest["prev"]
        if not prev:
            continue
        gate_texts = [g["text"] for g in quest["option_gates"] if quest_id in g["children"]]
        if quest["branch_key"] and quest["branch_key"].startswith(("d:", "p:")):
            add_edge(prev, quest_id, "branch", "；".join(gate_texts) or "二选一",
                     branch_key=quest["branch_key"])
        elif gate_texts:
            add_edge(prev, quest_id, "conditional", gate_texts[0])
        else:
            add_edge(prev, quest_id, "sequential", "")

    # 接取条件/触发表达式引用的任务关系：完成→triggered，进行中→conditional。
    for quest_id, quest in quests.items():
        acq = quest.get("acq_cond") or {}
        tree = acq.get("tree")
        for ref in _cond_task_refs(tree):
            if ref["quest"] not in quests or ref["quest"] == quest_id:
                continue
            name = quests[ref["quest"]]["name"]
            if ref["kind"] == "quest_done":
                add_edge(ref["quest"], quest_id, "triggered",
                         "完成「%s」后自动触发" % name, hidden=bool(quest["hidden"]))
                continue
            add_edge(ref["quest"], quest_id, "conditional",
                     acq.get("text") or ref["text"], hidden=bool(quest["hidden"]),
                     egg=_tree_has_kind(tree, "npc_realm"))
        gate = quest.get("gate") or {}
        for prev_quest_id in gate.get("quests") or []:
            if prev_quest_id in quests:
                add_edge(prev_quest_id, quest_id, "triggered",
                         "完成「%s」后自动触发" % quests[prev_quest_id]["name"],
                         hidden=bool(quest["hidden"]))

    diagnostics = {"hidden_total": sum(1 for quest in quests.values() if quest["hidden"])}

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

    # 剧情线：优先按 taskGroup 合并（同一组的任务是一条线），无 group 的按 quest_chain 独立成线。
    region_names = {"临州", "白獠部", "河望镇"}
    for quest in quests.values():
        region = (quest.get("location") or {}).get("region") or ""
        if region:
            region_names.add(region)
    chapter_order, chapter_tones = _chapter_layout(realms)
    storylines = _build_storylines(quests, edges, realms, region_names, chapter_order)

    # 同名任务：不同章节/不同剧情链里可能各有一个「小蝶所托」这种同名任务，
    # 玩家容易把已完成的那条当成眼前这条的前置。这里按名字分组，全部来自配置，不写死。
    line_meta = {}
    for line in storylines:
        for quest_id in line.get("quests") or []:
            line_meta[quest_id] = line
    name_groups = {}
    for quest_id, quest in quests.items():
        name = quest["name"]
        if name:
            name_groups.setdefault(name, []).append(quest_id)
    dup_names, same_name_map = {}, {}
    for name, ids in name_groups.items():
        if len(ids) < 2:
            continue
        ids = sorted(ids)
        entries = []
        for quest_id in ids:
            quest = quests[quest_id]
            line = line_meta.get(quest_id) or {}
            entries.append({
                "id": quest_id,
                "chapter": line.get("chapter") or "",
                "line": line.get("name") or quest.get("chain_name") or "",
                "region": line.get("region") or (quest.get("location") or {}).get("region") or "",
                "giver": (quest.get("giver") or {}).get("name") or "",
            })
        dup_names[name] = entries
        for quest_id in ids:
            same_name_map[quest_id] = [other for other in ids if other != quest_id]
    for quest_id, quest in quests.items():
        quest["same_name"] = sorted(same_name_map.get(quest_id, []))

    stats = {
        "quests": len(result),
        "with_rewards": sum(1 for quest in result if quest["rewards"]),
        "stones": sum(quest["reward_stone"] for quest in result),
        "groups": len(groups),
        "chains": len([chain for chain in chains if chain["size"] > 1]),
        "branches": len([branch for branch in branches.values() if len(branch["quests"]) > 1]),
        "hidden": sum(1 for quest in result if quest["hidden"]),
        "branch": sum(1 for quest in result if quest["branch"]),
        "edges": len(edges),
        "storylines": len(storylines),
        "option_gates": sum(len(quest["option_gates"]) for quest in result),
    }
    # 全表任务索引：条件里会引用主线/红尘/委托/奇遇任务，前端要能显示“它叫什么、属于哪类、在哪个模块”。
    quest_index = {}
    for row in all_rows:
        qid = _int(row.get("id"))
        if not qid:
            continue
        qtype = _int(row.get("type"))
        quest_index[str(qid)] = {
            "name": _plain(row.get("name")) or "",
            "type": qtype,
            "type_name": (type_names.get(qtype) or "").strip("[]"),
            "side": qtype in side_types,
        }
    return {"schema": SCHEMA, "quests": result, "groups": sorted(groups.values(), key=lambda g: g["name"]),
            "chains": sorted(chains, key=lambda item: chain_order.get(item["id"], 0)),
            "storylines": storylines,
            "dup_names": dup_names,
            "chapter_order": chapter_order, "chapter_tones": chapter_tones,
            "quest_index": quest_index,
            "branches": sorted(branches.values(), key=lambda item: item["key"]),
            "flow_accepts": flow_accepts,
            "space_names": {str(space_id): (info.get("name") or "")
                            for space_id, info in spaces.items()},
            "npc_homes": npc_homes,
            "npc_names": {str(key): value for key, value in npcs.items()},
            "realms": realms, "phases": phases,
            "edges": edges, "diagnostics": diagnostics,
            "egg_notes": _build_egg_notes(items, quests, edges),
            "attr_names": {str(key): value for key, value in attr_names.items()},
            "attr_levels": attr_levels,
            "states": {str(k): v for k, v in QUEST_STATE_NAMES.items()},
            "types": {str(k): v for k, v in type_names.items()}, "stats": stats}


# 插件统一入口
build = build_quests
