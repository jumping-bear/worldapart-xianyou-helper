# -*- coding: utf-8 -*-
"""配置表解析的公共纯函数层。

约定（并行开发必读）：
    * 只增不改：新增函数随意；修改既有函数签名或语义，必须由装配负责人执行，
      并在合并前做一次全模块快照的逐字节比对。
    * 本文件只允许依赖标准库，禁止 import app.common / app.modules / meta_update，
      避免环形依赖。
    * 只放多模块共用的解析逻辑；单模块专用逻辑留在自己的 build.py。
"""
import re

# 快照数据结构版本（写进每个快照 JSON 的 schema 字段）
SCHEMA = 2


def _rows(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


# 配置表文本列：游戏里同一字段会同时给出简中/繁中/英文，按玩家游戏内语言取用。
TEXT_LANGUAGES = ("zh-Hans", "zh-Hant", "en-US")
TEXT_LANGUAGE = "zh-Hans"
# 文本清洗逻辑变更时递增，让已缓存的模块快照重新构建（不必逐个模块改 SCHEMA）。
# 2：新增「配置自带对照表」兜底（见 set_text_glossary），英文快照需要重建。
TEXT_REVISION = 2
# 有些表本身没有语言列（例如 tbalignmenttitle 的 titleName 就是纯中文字符串），
# 但同一句话在别的表里有简中/英文两列。这里放一份「简中 → 英文」的对照，
# 由 meta_update 从配置里现算，_text 遇到纯字符串时用它兜底。
TEXT_GLOSSARY = {}


def set_text_language(code):
    """切换配置表取值语言；未知语言回退简中。"""
    global TEXT_LANGUAGE
    TEXT_LANGUAGE = code if code in TEXT_LANGUAGES else "zh-Hans"


def set_text_glossary(mapping):
    """设置配置自带的简中→英文对照表；空字典表示关闭兜底。"""
    global TEXT_GLOSSARY
    TEXT_GLOSSARY = mapping if isinstance(mapping, dict) else {}


def _text(value):
    if isinstance(value, dict):
        if TEXT_LANGUAGE != "zh-Hans" and value.get(TEXT_LANGUAGE):
            return str(value[TEXT_LANGUAGE])
        for key in ("zh-Hans", "zh-Hant", "en-US"):
            if value.get(key):
                return str(value[key])
        return ""
    text = "" if value is None else str(value)
    # 表里没有语言列时，借配置自带的对照表翻译（仅在非简中模式下生效）。
    if TEXT_LANGUAGE != "zh-Hans" and TEXT_GLOSSARY:
        hit = TEXT_GLOSSARY.get(text) or TEXT_GLOSSARY.get(text.strip())
        if hit:
            return hit
    return text


def _plain(value):
    """去掉富文本标签，供列表展示。"""
    text = re.sub(r"<[^>]+>", "", _text(value))
    return re.sub(r"\s{2,}", " ", text).strip()


def build_realms(tables):
    realms = {"0": "凡人"}
    for row in _rows(tables["tbcultivaterealm"]):
        if isinstance(row, dict) and row.get("id") is not None:
            realms[str(row["id"])] = _text(row.get("realm_name")) or ("境界%s" % row["id"])
    return realms


def build_spaces(tables):
    spaces = {}
    for row in _rows(tables["tbspace"]):
        if isinstance(row, dict) and row.get("id") is not None:
            father = row.get("fatherSpace")
            if isinstance(father, dict):
                father = father.get("id")
            spaces[str(row["id"])] = {
                "name": _text(row.get("spaceName")) or ("地点 %s" % row["id"]),
                "realm_id": row.get("realm_id"),
                "father_id": "" if father in (None, "", 0, "0") else str(father),
            }

    def space_path(space_id):
        path, seen, current = [], set(), space_id
        while current in spaces and current not in seen:
            seen.add(current)
            path.append(current)
            current = spaces[current]["father_id"]
        path.reverse()
        names = []
        for item in path:
            name = spaces[item]["name"]
            if not names or names[-1] != name:
                names.append(name)
        return names

    for space_id, space in spaces.items():
        path = space_path(space_id) or [space["name"]]
        space["region"] = path[0]
        space["path"] = path
    return spaces


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _expr_ints(node):
    """取表达式树里的整型字面量，用于识别交互点引用的任务 id。"""
    out = []

    def walk(value):
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, (list, tuple)):
            if len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], dict):
                item = value[1].get("value")
                if isinstance(item, int) and not isinstance(item, bool):
                    out.append(item)
                walk(value[1])
            else:
                for child in value:
                    walk(child)

    walk(node)
    return out


def _clip(text, limit):
    return text if len(text) <= limit else text[:limit] + "…"


def _callee_name(callee):
    """从变量/索引/调用描述里取出函数名与索引名。"""
    if isinstance(callee, dict):
        return callee.get("name"), None
    if isinstance(callee, (list, tuple)) and len(callee) == 2 and isinstance(callee[1], dict):
        tag, payload = callee
        if tag == "variable":
            return payload.get("name"), None
        if tag == "index":
            name, _ = _callee_name(payload.get("target"))
            index = payload.get("index")
            index_name = None
            if isinstance(index, (list, tuple)) and len(index) == 2 and isinstance(index[1], dict):
                index_name = index[1].get("value")
            return name, index_name
        if tag == "call":
            return _callee_name(payload)
    return None, None


def _call_parts(node):
    """拆出调用节点的 (名字, 索引名, 参数列表)。"""
    if isinstance(node, (list, tuple)) and len(node) == 2 and isinstance(node[0], str) and isinstance(node[1], dict):
        return _call_parts(node[1])
    if not isinstance(node, dict):
        return None, None, []
    args = []
    callee = None
    if isinstance(node.get("func"), (list, dict)):
        callee, args = node["func"], node.get("args") or []
        if not args:
            inner_name, inner_index, inner_args = _call_parts(callee)
            if inner_args:
                return inner_name, inner_index, inner_args
    elif isinstance(node.get("target"), (list, dict)):
        callee, args = node["target"], node.get("arguments") or []
    elif isinstance(node.get("name"), str):
        callee, args = node, node.get("arguments") or []
    name, index = _callee_name(callee)
    return name, index, args if isinstance(args, list) else []


def _const_value(node):
    """取字面量表达式（int/string/bool/float）的值。"""
    if isinstance(node, (list, tuple)) and len(node) == 2 and isinstance(node[0], str):
        if node[0] in ("int", "string", "bool", "float") and isinstance(node[1], dict):
            return node[1].get("value")
    if isinstance(node, (int, float, str, bool)):
        return node
    return None


def _const_args(args):
    """按顺序取参数里的直接字面量，避免被嵌套条件里的整数干扰。"""
    out = []
    for arg in args or []:
        if isinstance(arg, (list, tuple)) and len(arg) == 2 and isinstance(arg[0], str) and isinstance(arg[1], dict):
            if arg[0] in ("int", "string", "bool", "float"):
                out.append(arg[1].get("value"))
        elif isinstance(arg, (int, float, str, bool)):
            out.append(arg)
    return out
