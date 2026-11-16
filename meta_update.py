# -*- coding: utf-8 -*-
"""从游戏当前 YooAsset 清单更新查询元数据；标准库优先，UnityPy 延迟导入。"""
import hashlib
import json
import os
import re
import struct
import sys
import time

SCHEMA = 2
CACHE_SCHEMA = 21
TABLES = {
    "tbnpcbasecfg", "tbnpcbedroom", "tbscenepresentationinteraction",
    "tbscenepresentationaction", "tbspace", "tbnpctalent", "tbcultivaterealm",
    "tbitem", "tbsteal", "tbitemtype", "tbpillrecipe", "tbpillherb",
    "tbpillsecretportal", "tbpillfurnace", "tbpilllevel", "tbpillportal",
    "tbpilleffect", "tbpillexplorepoi", "tbattribute",
    "tbalchemyprototype", "tbalchemymaterial", "tbalchemylayout", "tbalchemylevel",
    "tbalchemytalent", "tbalchemyscoretier", "tbalchemyartifactaffixpool",
    "tbalchemywashpity", "tbelement",
    "tbpassiveskill", "tbskill",
    "tbnpcbagrule", "tbnpcitemdemandholdtemplate", "tbnpcintimacy",
    "tbrandomeventending", "tbrewarddrop", "tbquest", "tbquesttype",
    "tbrandomeventteleportentry", "tbspaceactiveevent",
    "tbinteractaction", "tbspaceinteractui", "tbdialogue",
    "tbgameactionflow", "tbinteractattribute",
    "tbpillherb", "tbpillrecipe", "tbalchemymaterial",
    "tbnpcitemdemandholdtemplate", "tbconditionexpr",
}
MODULE_TABLES = {
    "bedroom": {"tbnpcbasecfg", "tbnpcbedroom", "tbscenepresentationinteraction",
                "tbscenepresentationaction"},
    "talent": {"tbnpcbasecfg", "tbspace", "tbnpctalent", "tbcultivaterealm"},
    "items": {"tbnpcbasecfg", "tbspace", "tbcultivaterealm", "tbitem", "tbsteal",
              "tbitemtype", "tbnpcbagrule", "tbnpcitemdemandholdtemplate",
              "tbnpcintimacy"},
    "pill": {"tbitem", "tbpillrecipe", "tbpillherb", "tbpillsecretportal",
             "tbpillfurnace", "tbpilllevel", "tbcultivaterealm", "tbpillportal",
             "tbpilleffect", "tbpillexplorepoi", "tbattribute"},
    "forge": {"tbalchemyprototype", "tbalchemymaterial", "tbalchemylayout",
              "tbalchemylevel", "tbalchemytalent", "tbalchemyscoretier",
              "tbalchemyartifactaffixpool", "tbalchemywashpity",
              "tbitem", "tbattribute", "tbelement", "tbcultivaterealm"},
    "event": {"tbrandomeventending", "tbrewarddrop", "tbquest", "tbitem",
              "tbitemtype", "tbspace", "tbcultivaterealm",
              "tbrandomeventteleportentry", "tbspaceactiveevent",
              "tbinteractaction", "tbspaceinteractui", "tbdialogue",
              "tbgameactionflow", "tbinteractattribute", "tbconditionexpr",
              "tbpillherb", "tbpillrecipe", "tbalchemymaterial",
              "tbnpcitemdemandholdtemplate"},
    # tbquesttype 只用于识别“支线”文案，缺失时回退 type==2，因此不列为必需表。
    "quest": {"tbquest", "tbrewarddrop", "tbitem", "tbitemtype", "tbgameactionflow",
              "tbnpcbasecfg", "tbspace", "tbcultivaterealm", "tbconditionexpr"},
}
MODULE_NAMES = {"bedroom": "仙居楼互动", "talent": "NPC天赋", "items": "NPC物品",
                "pill": "炼丹", "forge": "炼器", "event": "奇遇", "quest": "支线"}


def _plugin_specs():
    """已发现的插件模块（app/modules/<key>）；加载失败时只返回成功的那部分。"""
    try:
        from app import modules as plugins
        return plugins.all()
    except Exception:
        return {}


def _known_tables():
    """配置表名全集：内建表 + 插件模块各自声明的 TABLES。"""
    extra = set()
    for spec in _plugin_specs().values():
        extra |= set(getattr(spec, "TABLES", ()) or ())
    return TABLES | extra if extra else TABLES


# ---------------- MessagePack 解码（最小实现） ----------------
class Ext:
    __slots__ = ("type", "data")

    def __init__(self, t, d):
        self.type, self.data = t, d


def _dec(b, i):
    c = b[i]
    i += 1
    if c <= 0x7F:
        return c, i
    if c >= 0xE0:
        return c - 0x100, i
    if 0x80 <= c <= 0x8F:
        return _map(b, i, c & 0x0F)
    if 0x90 <= c <= 0x9F:
        return _arr(b, i, c & 0x0F)
    if 0xA0 <= c <= 0xBF:
        n = c & 0x1F
        return b[i:i + n].decode("utf-8", "replace"), i + n
    if c == 0xC0:
        return None, i
    if c in (0xC2, 0xC3):
        return c == 0xC3, i
    if c in (0xC4, 0xD9):
        n = b[i]
        i += 1
        v = b[i:i + n] if c == 0xC4 else b[i:i + n].decode("utf-8", "replace")
        return v, i + n
    if c in (0xC5, 0xDA):
        n = struct.unpack_from(">H", b, i)[0]
        i += 2
        v = b[i:i + n] if c == 0xC5 else b[i:i + n].decode("utf-8", "replace")
        return v, i + n
    if c in (0xC6, 0xDB):
        n = struct.unpack_from(">I", b, i)[0]
        i += 4
        v = b[i:i + n] if c == 0xC6 else b[i:i + n].decode("utf-8", "replace")
        return v, i + n
    if c == 0xCA:
        return struct.unpack_from(">f", b, i)[0], i + 4
    if c == 0xCB:
        return struct.unpack_from(">d", b, i)[0], i + 8
    if c == 0xCC:
        return b[i], i + 1
    if c == 0xCD:
        return struct.unpack_from(">H", b, i)[0], i + 2
    if c == 0xCE:
        return struct.unpack_from(">I", b, i)[0], i + 4
    if c == 0xCF:
        return struct.unpack_from(">Q", b, i)[0], i + 8
    if c == 0xD0:
        return struct.unpack_from(">b", b, i)[0], i + 1
    if c == 0xD1:
        return struct.unpack_from(">h", b, i)[0], i + 2
    if c == 0xD2:
        return struct.unpack_from(">i", b, i)[0], i + 4
    if c == 0xD3:
        return struct.unpack_from(">q", b, i)[0], i + 8
    if c in (0xD4, 0xD5, 0xD6, 0xD7, 0xD8):
        n = {0xD4: 1, 0xD5: 2, 0xD6: 4, 0xD7: 8, 0xD8: 16}[c]
        return Ext(b[i], b[i + 1:i + 1 + n]), i + 1 + n
    if c in (0xC7, 0xC8, 0xC9):
        n = {0xC7: b[i], 0xC8: struct.unpack_from(">H", b, i)[0], 0xC9: struct.unpack_from(">I", b, i)[0]}[c]
        off = {0xC7: 1, 0xC8: 2, 0xC9: 4}[c]
        t = b[i + off]
        s = i + off + 1
        return Ext(t, b[s:s + n]), s + n
    if c == 0xDC:
        return _arr(b, i + 2, struct.unpack_from(">H", b, i)[0])
    if c == 0xDD:
        return _arr(b, i + 4, struct.unpack_from(">I", b, i)[0])
    if c == 0xDE:
        return _map(b, i + 2, struct.unpack_from(">H", b, i)[0])
    if c == 0xDF:
        return _map(b, i + 4, struct.unpack_from(">I", b, i)[0])
    raise ValueError("msgpack 0x%02x" % c)


def _arr(b, i, n):
    out = []
    for _ in range(n):
        v, i = _dec(b, i)
        out.append(v)
    return out, i


def _map(b, i, n):
    out = {}
    for _ in range(n):
        k, i = _dec(b, i)
        v, i = _dec(b, i)
        out[k] = v
    return out, i


def unpack(data):
    return _dec(data, 0)[0]


def resolve_table(name):
    """把资源表名映射到规范名；精确匹配优先，其次取带版本后缀的最长前缀。

    只接受数字或 _-./ 开头的剩余部分，避免 tbitemuseeffect 这类同前缀表被误认成 tbitem。
    """
    name = str(name or "").lower()
    known_tables = _known_tables()
    if name in known_tables:
        return name
    best = ""
    for known in known_tables:
        if not name.startswith(known) or len(known) <= len(best):
            continue
        rest = name[len(known):]
        if rest[:1] in "_-.0123456789":
            best = known
    return best


def cache_directory():
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        root = os.path.expanduser("~")
    return os.path.join(root, "WorldApartTouchProgress")


def game_dir_from_config(cfg, decrypted_dir=""):
    game = (cfg or {}).get("game_dir") or ""
    if game and os.path.isfile(os.path.join(game, "WorldApart.exe")):
        return os.path.normpath(game)
    if decrypted_dir:
        parent = os.path.dirname(os.path.normpath(decrypted_dir))
        if os.path.basename(parent).lower() == "bepinex":
            candidate = os.path.dirname(parent)
            if os.path.isfile(os.path.join(candidate, "WorldApart.exe")):
                return candidate
    return ""


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _atomic_json(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    tmp = os.path.join(directory, ".%s.%s.tmp" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _version_key(path, manifest):
    version = str(manifest.get("PackageVersion") or "")
    numbers = tuple(int(x) for x in re.findall(r"\d+", version))
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = 0
    return numbers, version, stamp


def inspect_game(game_dir):
    if not game_dir:
        raise ValueError("未记录游戏目录")
    root = os.path.join(game_dir, "WorldApart_Data", "StreamingAssets", "yoo", "DefaultPackage")
    candidates = []
    for name in os.listdir(root):
        if not (name.startswith("DefaultPackage_") and name.endswith(".json")):
            continue
        path = os.path.join(root, name)
        manifest = _read_json(path)
        if not isinstance(manifest, dict):
            continue
        if not isinstance(manifest.get("AssetList"), list) or not isinstance(manifest.get("BundleList"), list):
            continue
        candidates.append((path, manifest))
    if not candidates:
        raise ValueError("找不到有效的 DefaultPackage 配置清单")
    path, manifest = max(candidates, key=lambda x: _version_key(x[0], x[1]))
    bundle_ids = set()
    for asset in manifest["AssetList"]:
        if not isinstance(asset, dict):
            continue
        asset_path = str(asset.get("AssetPath") or "")
        table = resolve_table(os.path.basename(asset_path).split(".", 1)[0])
        if table and asset_path.lower().endswith(".json"):
            try:
                bundle_ids.add(int(asset["BundleID"]))
            except (KeyError, TypeError, ValueError):
                pass
    bundles = []
    for bundle_id in sorted(bundle_ids):
        try:
            bundle = manifest["BundleList"][bundle_id]
            file_hash = str(bundle["FileHash"])
            file_path = os.path.join(root, file_hash + ".bundle")
            item = {
                "id": bundle_id, "hash": file_hash,
                "size": int(bundle.get("FileSize") or 0),
                "crc": str(bundle.get("FileCRC") or ""),
            }
            if not os.path.isfile(file_path):
                raise FileNotFoundError("配置资源缺失：%s.bundle" % file_hash)
            actual_size = os.path.getsize(file_path)
            if item["size"] and actual_size != item["size"]:
                raise ValueError("配置资源大小与清单不符：%s.bundle" % file_hash)
            bundles.append(item)
        except (IndexError, KeyError, TypeError, ValueError) as e:
            raise ValueError("清单中的配置资源信息无效：%s" % e)
    if not bundles:
        raise ValueError("当前清单没有所需配置表")
    source = {
        "package_version": str(manifest.get("PackageVersion") or ""),
        "manifest": os.path.basename(path), "bundles": bundles,
    }
    fingerprint = hashlib.sha256(
        json.dumps(source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {"root": root, "manifest": manifest, "source": source, "fingerprint": fingerprint}


def _extract_tables(inspection):
    import UnityPy  # 仅在配置指纹变化时导入

    manifest = inspection["manifest"]
    wanted_bundles = {b["id"] for b in inspection["source"]["bundles"]}
    assets = {}
    for asset in manifest["AssetList"]:
        if not isinstance(asset, dict):
            continue
        path = str(asset.get("AssetPath") or "")
        key = resolve_table(os.path.basename(path).split(".", 1)[0])
        if key and path.lower().endswith(".json"):
            try:
                bid = int(asset["BundleID"])
            except (KeyError, TypeError, ValueError):
                continue
            if bid in wanted_bundles:
                assets[bid] = True
    tables = {}
    for bundle_id in sorted(assets):
        bundle = manifest["BundleList"][bundle_id]
        path = os.path.join(inspection["root"], str(bundle["FileHash"]) + ".bundle")
        with open(path, "rb") as f:
            data = f.read()
        offset = data.find(b"UnityFS")
        if offset < 0:
            raise ValueError("配置资源不是可识别的 Unity bundle：%s" % os.path.basename(path))
        env = UnityPy.load(data[offset:])
        for obj in env.objects:
            if obj.type.name != "TextAsset":
                continue
            item = obj.read()
            name = resolve_table(str(item.m_Name))
            if not name or name in tables:
                continue
            raw = item.m_Script
            try:
                if isinstance(raw, str) and raw.lstrip()[:1] in ("{", "["):
                    value = json.loads(raw)
                elif isinstance(raw, (bytes, bytearray)) and bytes(raw).lstrip()[:1] in (b"{", b"["):
                    value = json.loads(bytes(raw).decode("utf-8-sig"))
                else:
                    # 炼器配置表以 MessagePack 二进制存放，按 msgpack 解析。
                    if not isinstance(raw, (bytes, bytearray)):
                        raw = str(raw).encode("utf-8", "surrogateescape")
                    value = unpack(bytes(raw))
            except (ValueError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(value, (list, dict)):
                tables[name] = value
    return tables


def _rows(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def _text(value):
    if isinstance(value, dict):
        for key in ("zh-Hans", "zh-Hant", "en-US"):
            if value.get(key):
                return str(value[key])
        return ""
    return "" if value is None else str(value)


def _plain(value):
    """去掉富文本标签，供列表展示。"""
    return re.sub(r"<[^>]+>", "", _text(value)).strip()


def build_realms(tables):
    realms = {"0": "凡人"}
    for row in _rows(tables["tbcultivaterealm"]):
        if isinstance(row, dict) and row.get("id") is not None:
            realms[str(row["id"])] = _text(row.get("realm_name")) or ("境界 %s" % row["id"])
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


def _module_tables(module, specs=None):
    """模块需要的配置表：优先用模块自己声明的 TABLES，老调用回退集中表。"""
    spec = (specs if specs is not None else _plugin_specs()).get(module)
    declared = getattr(spec, "TABLES", None) if spec is not None else None
    return set(declared or MODULE_TABLES.get(module, ()))


def _module_builder(module, specs=None):
    spec = (specs if specs is not None else _plugin_specs()).get(module)
    return spec.build if spec is not None and getattr(spec, "HAS_BUILD", False) else None


def _module_schema(module, spec):
    """每个模块独立的缓存版本：插件默认 1，老模块沿用 CACHE_SCHEMA。"""
    if spec is None:
        return CACHE_SCHEMA
    try:
        value = int(getattr(spec, "SCHEMA", 1) or 1)
    except (TypeError, ValueError):
        return 1
    return value if value > 0 else 1


def _module_cache_path(cache_dir, module):
    return os.path.join(cache_dir, "modules", "%s.json" % module)


def _read_module_cache(cache_dir, module, schema):
    entry = _read_json(_module_cache_path(cache_dir, module), {}) or {}
    if not isinstance(entry, dict) or entry.get("schema") != schema or entry.get("data") is None:
        return {}
    return entry


def _module_label(module, spec):
    return getattr(spec, "LABEL", "") or MODULE_NAMES.get(module, module)


def _builtin(directory, module, spec=None):
    """内置快照：文件名与合法性都由模块自己声明。"""
    name = getattr(spec, "SNAPSHOT", "") if spec is not None else ""
    if not name:
        raise ValueError("%s未声明内置快照" % _module_label(module, spec))
    data = _read_json(os.path.join(directory, name))
    check = getattr(spec, "builtin_ok", None)
    if data is None or (callable(check) and not check(data)):
        raise ValueError("%s内置快照无效" % _module_label(module, spec))
    return data


def _empty_data(module, spec=None):
    """配置完全不可用时的最小结构，保证页面能渲染。"""
    make = getattr(spec, "empty", None)
    if callable(make):
        try:
            data = make()
            if isinstance(data, (dict, list)):
                return data
        except Exception:
            pass
    return {"schema": SCHEMA}


def load_metadata(game_dir, builtin_dir, modules=("bedroom", "talent"), cache_dir=None):
    """返回 (数据, 来源报告)；任何更新失败都回退，不阻断存档查询。

    缓存按模块拆分到 cache_dir/modules/<key>.json，单个模块重算不会牵动其它模块。
    旧版 game_meta_cache.json 仍会读取一次，命中后按新结构继续使用。
    """
    modules = tuple(dict.fromkeys(modules))
    cache_dir = cache_dir or cache_directory()
    legacy_path = os.path.join(cache_dir, "game_meta_cache.json")
    state_path = os.path.join(cache_dir, "meta_update_state.json")
    legacy = _read_json(legacy_path, {}) or {}
    if legacy.get("schema") != CACHE_SCHEMA or not isinstance(legacy.get("modules"), dict):
        legacy = {"modules": {}}
    state = _read_json(state_path, {}) or {}
    specs = _plugin_specs()
    result, report = {}, {"modules": {}, "warnings": [], "fingerprint": ""}
    inspection = None
    inspect_error = ""
    try:
        inspection = inspect_game(game_dir)
        report["fingerprint"] = inspection["fingerprint"]
        report["package_version"] = inspection["source"]["package_version"]
    except Exception as e:
        inspect_error = str(e)

    entries, unresolved = {}, []
    for module in modules:
        schema = _module_schema(module, specs.get(module))
        entry = _read_module_cache(cache_dir, module, schema)
        migrated = False
        if not entry:
            old = (legacy.get("modules") or {}).get(module) or {}
            if isinstance(old, dict) and old.get("data") is not None:
                entry = {"schema": schema, "fingerprint": old.get("fingerprint"),
                         "generated_at": old.get("generated_at"), "data": old.get("data")}
                migrated = True
        entries[module] = entry
        if migrated:
            try:
                _atomic_json(_module_cache_path(cache_dir, module), entry)
            except Exception:
                pass
        data = entry.get("data")
        if inspection and data is not None and entry.get("fingerprint") == inspection["fingerprint"]:
            result[module] = data
            report["modules"][module] = {"source": "current", "label": "游戏当前配置"}
        else:
            unresolved.append(module)

    failed = bool(inspection) and state.get("fingerprint") == report["fingerprint"]
    failed_modules = set(state.get("modules") or []) if failed else set()
    builders = {module: _module_builder(module, specs) for module in unresolved}
    to_extract = [m for m in unresolved if m not in failed_modules and builders.get(m)] if inspection else []
    errors = {}
    if to_extract:
        try:
            tables = _extract_tables(inspection)
            for module in to_extract:
                try:
                    missing = _module_tables(module, specs) - set(tables)
                    if missing:
                        raise ValueError("缺少配置表：%s" % ", ".join(sorted(missing)))
                    data = builders[module](tables)
                    result[module] = data
                    entries[module] = {
                        "schema": _module_schema(module, specs.get(module)),
                        "fingerprint": inspection["fingerprint"],
                        "generated_at": int(time.time()), "data": data,
                    }
                    try:
                        _atomic_json(_module_cache_path(cache_dir, module), entries[module])
                    except Exception as e:
                        report["warnings"].append("%s 配置缓存写入失败：%s" % (
                            MODULE_NAMES.get(module, module), e))
                    report["modules"][module] = {"source": "current", "label": "游戏当前配置"}
                except Exception as e:
                    errors[module] = str(e)
        except Exception as e:
            for module in to_extract:
                errors[module] = str(e)
        try:
            _atomic_json(state_path, {
                "fingerprint": inspection["fingerprint"], "modules": sorted(errors),
                "errors": errors, "time": int(time.time()),
            })
        except Exception:
            pass
    for module, message in (state.get("errors") or {}).items():
        if module in unresolved and module in failed_modules:
            errors[module] = str(message)

    for module in unresolved:
        if module in result:
            continue
        entry = entries.get(module) or {}
        if entry.get("data") is not None:
            result[module] = entry["data"]
            report["modules"][module] = {"source": "cache", "label": "兼容缓存"}
        else:
            try:
                result[module] = _builtin(builtin_dir, module, specs.get(module))
                report["modules"][module] = {"source": "builtin", "label": "内置快照"}
            except Exception as e:
                errors[module] = str(e)
                result[module] = _empty_data(module, specs.get(module))
                report["modules"][module] = {"source": "missing", "label": "无可用配置"}
        if module in errors:
            report["modules"][module]["warning"] = errors[module]
    if inspect_error and unresolved:
        report["warnings"].append("未读取游戏当前配置：%s" % inspect_error)
    for module, message in errors.items():
        if module in modules:
            name = MODULE_NAMES.get(module) or getattr(specs.get(module), "LABEL", module)
            report["warnings"].append("%s 配置更新失败，已使用兜底数据：%s" % (name, message))
    return result, report


def export_snapshots(game_dir, output_dir):
    """导出全部模块的内置快照：模块自带 build 与额外快照（如炼丹盘面）。"""
    inspection = inspect_game(game_dir)
    tables = _extract_tables(inspection)
    for key, spec in sorted(_plugin_specs().items(), key=lambda item: (item[1].ORDER, item[0])):
        if getattr(spec, "HAS_BUILD", False):
            name = spec.SNAPSHOT or ("%s_meta.json" % key)
            _atomic_json(os.path.join(output_dir, name), spec.build(tables))
        for name, make in (getattr(spec, "EXTRA_SNAPSHOTS", None) or {}).items():
            _atomic_json(os.path.join(output_dir, name), make(tables, inspection))
    print("已导出当前配置快照：%s" % output_dir)


if __name__ == "__main__":
    if "--export-snapshots" in sys.argv:
        index = sys.argv.index("--export-snapshots")
        export_snapshots(sys.argv[index + 1], sys.argv[index + 2])
    else:
        cfg = _read_json(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), {}) or {}
        data, info = load_metadata(game_dir_from_config(cfg, cfg.get("decrypted_dir", "")),
                                   os.path.dirname(os.path.abspath(__file__)))
        print(json.dumps(info, ensure_ascii=False, indent=2))
