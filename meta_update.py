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
    if name in TABLES:
        return name
    best = ""
    for known in TABLES:
        if not name.startswith(known) or len(known) <= len(best):
            continue
        rest = name[len(known):]
        if rest[:1] in "_-.0123456789":
            best = known
    return best
SLOT_LABELS = {
    "Face": "脸", "Waist": "腰", "Foot": "足", "Leg": "腿", "Armpit": "腋下",
    "Fan": "团扇", "Feather": "灵羽", "Gourd": "灵泉葫芦", "Grass": "草叶",
    "Stick": "短杖", "Bamboo": "竹枝", "Hug": "相拥",
}
# 游戏分类图标资源使用 combat/artisan/travel/wealth/rapport/personality。
CATEGORY_NAMES = {
    "1": "战斗", "2": "技艺", "3": "游历",
    "4": "财富", "5": "交情", "6": "性格",
}


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


# ---------------- 炼丹盘面（ACMP 二进制） ----------------
PILL_MAP_DIR = "Assets/GameAssets/RefiningPills/Map/"
PILL_MAP_PATH = PILL_MAP_DIR + "default.bytes"
PILL_MAP_NAME = "default"
PILL_MAP_VERSION = 4
# 拾取点 32 字节：id(4) type(1) element(1) tier(1) effect(4) recipe(4)
#              x(4) y(4) rewardCfg(4) rewardQuality(1) portalCfg(4)
# 轨迹段 32 字节：type(1) endX(4) endY(4) length(4) preset(1) curvature(2)
#              cp1X(4) cp1Y(4) cp2X(4) cp2Y(4)
POI_SIZE = 32
SEGMENT_SIZE = 32
FOG_MAGIC = 0x31534746  # "FGS1"
PILL_MAP_SCHEMA = 6


def _asset_bytes(item):
    """取 TextAsset 原始字节；UnityPy 以 str 返回时按 surrogateescape 无损还原。"""
    raw = getattr(item, "m_Script", b"")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return str(raw).encode("utf-8", "surrogateescape")


def extract_pill_maps(inspection):
    """从 DefaultPackage 中取出全部炼丹盘面（Map/ 目录下所有 ACMP 文本资源）。"""
    import UnityPy

    manifest = inspection["manifest"]
    bundles = {}
    for asset in manifest["AssetList"]:
        if not isinstance(asset, dict):
            continue
        if not str(asset.get("AssetPath") or "").startswith(PILL_MAP_DIR):
            continue
        try:
            bundles.setdefault(int(asset["BundleID"]), True)
        except (KeyError, TypeError, ValueError):
            continue
    if not bundles:
        raise ValueError("清单中没有炼丹盘面资源")
    maps = {}
    for bundle_id in bundles:
        bundle = manifest["BundleList"][bundle_id]
        path = os.path.join(inspection["root"], str(bundle["FileHash"]) + ".bundle")
        with open(path, "rb") as f:
            data = f.read()
        offset = data.find(b"UnityFS")
        env = UnityPy.load(data[offset:] if offset >= 0 else data)
        for obj in env.objects:
            if obj.type.name != "TextAsset":
                continue
            item = obj.read()
            raw = _asset_bytes(item)
            if raw[:4] == b"ACMP":
                maps[str(getattr(item, "m_Name", "") or "map")] = raw
    if not maps:
        raise ValueError("未找到炼丹盘面数据")
    return maps


def decode_pill_map(raw):
    """解析 ACMP v4：头 + 地形 RLE + 拾取点 + 药材轨迹 + 字符串池。"""
    if len(raw) < 26 or raw[:4] != b"ACMP":
        raise ValueError("炼丹盘面格式不符")
    version = struct.unpack_from("<H", raw, 4)[0]
    if version != PILL_MAP_VERSION:
        raise ValueError("炼丹盘面版本不支持：%s" % version)
    map_size, tile_size, cols, rows, rle_count = struct.unpack_from("<5i", raw, 6)
    if not (0 < cols <= 4096 and 0 < rows <= 4096) or rle_count <= 0:
        raise ValueError("炼丹盘面尺寸异常")
    total = cols * rows
    runs, filled, pos = [], 0, 26
    for _ in range(rle_count):
        if pos + 3 > len(raw):
            raise ValueError("炼丹盘面地形数据截断")
        value, count = raw[pos], raw[pos + 1] | (raw[pos + 2] << 8)
        pos += 3
        if filled + count > total:
            raise ValueError("炼丹盘面地形溢出")
        runs.append([value, count])
        filled += count
    if filled != total:
        raise ValueError("炼丹盘面地形不足")

    def i32(offset):
        if offset + 4 > len(raw):
            raise ValueError("炼丹盘面数据截断")
        return struct.unpack_from("<i", raw, offset)[0]

    poi_count = i32(pos)
    pos += 4
    if poi_count < 0 or pos + poi_count * POI_SIZE > len(raw):
        raise ValueError("炼丹盘面拾取点数量异常")
    pois = []
    for _ in range(poi_count):
        pois.append([
            i32(pos), raw[pos + 4], raw[pos + 5], raw[pos + 6], i32(pos + 7),
            i32(pos + 11), i32(pos + 15), i32(pos + 19), i32(pos + 23),
            raw[pos + 27], i32(pos + 28),
        ])
        pos += POI_SIZE

    traj_count = i32(pos)
    pos += 4
    if traj_count < 0 or traj_count > 100000:
        raise ValueError("炼丹盘面轨迹数量异常")
    trajectories = []
    for _ in range(traj_count):
        herb_id, mode, percent = i32(pos), raw[pos + 8], raw[pos + 9]
        segments = i32(pos + 10)
        pos += 14
        if segments < 0 or pos + segments * SEGMENT_SIZE > len(raw):
            raise ValueError("炼丹盘面轨迹段数量异常")
        segs = []
        for _ in range(segments):
            segs.append([
                raw[pos], i32(pos + 1), i32(pos + 5), i32(pos + 9), raw[pos + 13],
                struct.unpack_from("<h", raw, pos + 14)[0] / 1000.0,
                i32(pos + 16), i32(pos + 20), i32(pos + 24), i32(pos + 28),
            ])
            pos += 32
        trajectories.append([herb_id, mode, percent, segs])

    pool_count = i32(pos)
    pos += 4
    if pool_count < 0 or pool_count > 100000:
        raise ValueError("炼丹盘面字符串池异常")
    pool = []
    for _ in range(pool_count):
        length = i32(pos)
        pos += 4
        if length < 0 or pos + length > len(raw):
            raise ValueError("炼丹盘面字符串池截断")
        pool.append(raw[pos:pos + length].decode("utf-8", "replace"))
        pos += length
    if pos != len(raw):
        raise ValueError("炼丹盘面存在多余数据")
    main, comps, routes = _walk_components(runs, cols, rows, tile_size, pois)
    return {"schema": SCHEMA, "map_schema": PILL_MAP_SCHEMA, "version": version,
            "map_size": map_size, "tile_size": tile_size,
            "cols": cols, "rows": rows, "runs": runs, "pois": pois,
            "trajectories": trajectories, "pool": pool,
            "main": main, "comps": comps, "routes": routes}


def _walk_components(runs, cols, rows, tile_size, pois):
    """按地形把盘面切成连通块（山不可通行），并算出从中心出发要走的传送口。"""
    grid = bytearray()
    for value, count in runs:
        grid.extend(bytes([value]) * count)
    comps = [-1] * (cols * rows)
    total = 0
    for start in range(cols * rows):
        if comps[start] != -1 or grid[start] == 1:
            continue
        comps[start] = total
        queue = [start]
        head = 0
        while head < len(queue):
            index = queue[head]
            head += 1
            x, y = index % cols, index // cols
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < cols and 0 <= ny < rows:
                    near = ny * cols + nx
                    if comps[near] == -1 and grid[near] != 1:
                        comps[near] = total
                        queue.append(near)
        total += 1
    main = comps[(rows // 2) * cols + cols // 2]
    poi_comps = []
    for poi in pois:
        x, y = int(poi[6] // tile_size), int(poi[7] // tile_size)
        poi_comps.append(comps[y * cols + x] if 0 <= x < cols and 0 <= y < rows else -1)
    groups = {}
    for index, poi in enumerate(pois):
        if poi[1] in (5, 6):
            groups.setdefault(poi[10], []).append(index)
    graph = {}
    for members in groups.values():
        for a in (i for i in members if pois[i][1] == 5):
            for b in (i for i in members if pois[i][1] == 6):
                ca, cb = poi_comps[a], poi_comps[b]
                if ca < 0 or cb < 0 or ca == cb:
                    continue
                graph.setdefault(ca, []).append(
                    (cb, [pois[a][10], pois[a][6], pois[a][7], pois[b][6], pois[b][7]]))
                graph.setdefault(cb, []).append(
                    (ca, [pois[a][10], pois[b][6], pois[b][7], pois[a][6], pois[a][7]]))
    routes = {str(main): []}
    queue, head = [main], 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for target, step in graph.get(current, []):
            if str(target) in routes:
                continue
            routes[str(target)] = routes[str(current)] + [step]
            queue.append(target)
    return main, poi_comps, routes


def build_pill_map(tables, inspection):
    """解码全部盘面并附上拾取点对应的名称，供前端直接展示。"""
    blobs = extract_pill_maps(inspection)
    attributes = {str(_int(r.get("id"))): _text(r.get("name"))
                  for r in _rows(tables.get("tbattribute") or []) if isinstance(r, dict)}
    effects, rewards, portals, recipes = {}, {}, {}, {}
    for row in _rows(tables.get("tbpilleffect") or []):
        if isinstance(row, dict):
            stat = str(_int(row.get("stat_type")))
            effects[str(_int(row.get("id")))] = [
                _text(row.get("name")), _int(row.get("tier")), _int(row.get("element")),
                _plain(row.get("desc")), _int(row.get("collect_exp")),
                _int(row.get("stat_type")), row.get("balance_value") or 0,
                attributes.get(stat, ""),
            ]
    for row in _rows(tables.get("tbpillexplorepoi") or []):
        if isinstance(row, dict):
            rewards[str(_int(row.get("id")))] = [
                _text(row.get("name")), _int(row.get("reward_type")), _int(row.get("quality")),
                _plain(row.get("desc")), _int(row.get("value_min")), _int(row.get("value_max")),
            ]
    item_names = {str(_int(r.get("id"))): _text(r.get("itemName"))
                  for r in _rows(tables.get("tbitem") or []) if isinstance(r, dict)}
    for row in _rows(tables.get("tbpillportal") or []):
        if isinstance(row, dict):
            cost_id = _int(row.get("cost_item_id"))
            portals[str(_int(row.get("id")))] = [
                _text(row.get("name")), _int(row.get("element")),
                bool(row.get("two_way")), _plain(row.get("desc")),
                item_names.get(str(cost_id), "") if cost_id else "",
                _int(row.get("cost_count")) if cost_id else 0,
            ]
    for row in _rows(tables.get("tbpillrecipe") or []):
        if not isinstance(row, dict):
            continue
        values = []
        for effect in row.get("main_effects") or row.get("effects") or []:
            if isinstance(effect, dict):
                values.extend(effect.get("values") or [])
        recipes[str(_int(row.get("id")))] = {
            "n": _text(row.get("name")), "t": _int(row.get("tier")),
            "e": _int(row.get("element")), "d": _fill(_plain(row.get("desc")), values),
            "x": _int(row.get("toxin_max")),
            "g": [_int(row.get("fan_threshold")), _int(row.get("xian_threshold")),
                  _int(row.get("shen_threshold"))],
            "s": _int(row.get("spirit_progress")),
            "m": _int(row.get("max_craft_count") or row.get("max_craft")),
            "tm": _int(row.get("total_time") or row.get("time")),
        }
    shared = {"effects": effects, "rewards": rewards, "portals": portals, "recipes": recipes,
              "herbs": {str(_int(h.get("id"))): _text(h.get("name"))
                        for h in _rows(tables.get("tbpillherb") or []) if isinstance(h, dict)}}
    maps = []
    for name in sorted(blobs, key=lambda n: (n != PILL_MAP_NAME, n)):
        data = decode_pill_map(blobs[name])
        data["name"] = name
        data.update(shared)
        maps.append(data)
    return {"schema": SCHEMA, "map_schema": PILL_MAP_SCHEMA, "maps": maps}


def load_fog_strokes(save_path, map_id="default"):
    """读取同槽位目录 refiningPillsFog/<mapId>.strokes 的已探索笔迹。

    文件头 magic FGS1 + version + 记录数，每条 21 字节：
    是否线段(1) + 起点(2×float) + 终点(2×float) + 半径(float)。
    """
    path = save_path or ""
    base = ""
    for _ in range(4):
        path = os.path.dirname(path)
        if not path:
            break
        candidate = os.path.join(path, "refiningPillsFog")
        if os.path.isdir(candidate):
            base = candidate
            break
    if not base:
        return []
    try:
        with open(os.path.join(base, map_id + ".strokes"), "rb") as f:
            raw = f.read()
    except OSError:
        return []
    if len(raw) < 12:
        return []
    magic, _version, count = struct.unpack_from("<3i", raw, 0)
    if magic != FOG_MAGIC or count < 0 or 12 + count * 21 > len(raw):
        return []
    strokes = []
    pos = 12
    for _ in range(count):
        sx, sy, ex, ey, radius = struct.unpack_from("<5f", raw, pos + 1)
        strokes.append([raw[pos], round(sx, 1), round(sy, 1), round(ex, 1), round(ey, 1),
                        round(radius, 1)])
        pos += 21
    return strokes


def _usable_map(data):
    """盘面数据是否可用：结构完整且是当前版本的字段布局。"""
    maps = data.get("maps") if isinstance(data, dict) else None
    return (isinstance(data, dict) and data.get("map_schema") == PILL_MAP_SCHEMA
            and isinstance(maps, list) and maps
            and isinstance(maps[0].get("pois"), list) and maps[0]["pois"]
            and isinstance(maps[0].get("recipes"), dict))


def load_pill_map(game_dir, builtin_dir, cache_dir=None):
    """按 游戏当前配置 → 兼容缓存 → 内置快照 的顺序取盘面数据。"""
    cache_dir = cache_dir or cache_directory()
    cache_path = os.path.join(cache_dir, "pill_map_cache.json")
    cache = _read_json(cache_path, {}) or {}
    error = ""
    try:
        inspection = inspect_game(game_dir)
        fingerprint = inspection["fingerprint"]
        if (cache.get("schema") == CACHE_SCHEMA and cache.get("fingerprint") == fingerprint
                and _usable_map(cache.get("data"))):
            return cache["data"], {"source": "current", "label": "游戏当前配置"}
        data = build_pill_map(_extract_tables(inspection), inspection)
        try:
            _atomic_json(cache_path, {"schema": CACHE_SCHEMA, "fingerprint": fingerprint,
                                      "generated_at": int(time.time()), "data": data})
        except Exception:
            pass
        return data, {"source": "current", "label": "游戏当前配置"}
    except Exception as e:
        error = str(e)
    if _usable_map(cache.get("data")):
        return cache["data"], {"source": "cache", "label": "兼容缓存", "warning": error}
    data = _read_json(os.path.join(builtin_dir, "pill_map.json"))
    if _usable_map(data):
        return data, {"source": "builtin", "label": "内置快照", "warning": error}
    return ({"schema": SCHEMA, "maps": []},
            {"source": "missing", "label": "无可用配置", "warning": error})


def build_bedroom(tables):
    npcs = {r.get("id"): r for r in _rows(tables["tbnpcbasecfg"]) if isinstance(r, dict)}
    actions = {r.get("id"): r for r in _rows(tables["tbscenepresentationaction"]) if isinstance(r, dict)}
    interactions = {}
    for row in _rows(tables["tbscenepresentationinteraction"]):
        if isinstance(row, dict):
            interactions.setdefault(row.get("presentationId"), []).append(row)
    result = []
    for bed in _rows(tables["tbnpcbedroom"]):
        if not isinstance(bed, dict):
            continue
        npc_id = bed.get("npcId", bed.get("id"))
        actions_out = []
        seen_action_ids = set()
        rows = sorted(interactions.get(bed.get("presentationId"), []),
                      key=lambda r: (r.get("actionId") or 0, r.get("id") or 0))
        for interaction in rows:
            action_id = interaction.get("actionId")
            if action_id in seen_action_ids:
                continue
            seen_action_ids.add(action_id)
            action = actions.get(action_id) or {}
            slot = str(action.get("groupSlot") or "")
            actions_out.append({
                "id": action_id, "slot": slot,
                "label": SLOT_LABELS.get(slot) or slot or _text(interaction.get("label")) or str(action_id),
                "type": action.get("type"),
            })
        npc = npcs.get(npc_id) or {}
        result.append({
            "cfg": npc_id, "npcName": _text(npc.get("npcName")) or ("#%s" % npc_id),
            "bedroom": _text(bed.get("name")), "actions": actions_out,
        })
    if not result:
        raise ValueError("寝室配置为空")
    return result


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


def build_talent(tables):
    realms = build_realms(tables)
    spaces = build_spaces(tables)
    npcs = {}
    for row in _rows(tables["tbnpcbasecfg"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        slots = []
        for slot in row.get("talent_slots") or []:
            if not isinstance(slot, dict):
                continue
            conditions = []
            for condition in slot.get("unlock_conditions") or []:
                if isinstance(condition, dict):
                    desc = _text(condition.get("desc"))
                    if desc:
                        conditions.append(desc)
            slots.append({
                "slot_id": slot.get("slot_id"),
                "required_npc_realm_id": slot.get("required_npc_realm_id", 0),
                "unlock_conditions": conditions,
            })
        npcs[str(row["id"])] = {
            "name": _text(row.get("npcName")) or _text(row.get("npcTitle")) or ("#%s" % row["id"]),
            "title": _text(row.get("npcTitle")),
            "can_be_dao_companion": bool(row.get("can_be_dao_companion")),
            "slots": slots,
        }
    talents = []
    for row in _rows(tables["tbnpctalent"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        talents.append({
            "id": row["id"], "name": _text(row.get("name")) or ("天赋 %s" % row["id"]),
            "quality": row.get("quality"), "effect": _text(row.get("effect_desc")),
            "category": row.get("category"),
            "category_name": CATEGORY_NAMES.get(str(row.get("category")), ""),
            "realm_id": row.get("realm_id", 0),
            "hover": _text(row.get("ui_hover_desc")),
            "trigger": _text(row.get("ui_trigger_desc")),
            "preview_only": bool(row.get("preview_only", False)),
        })
    if not talents:
        raise ValueError("NPC 天赋配置为空")
    return {"schema": SCHEMA, "talents": talents, "npcs": npcs, "spaces": spaces, "realms": realms}


def build_items(tables):
    """物品只读元数据：名称、类型、品质、偷窃参数和持有者的可偷状态。"""
    item_types = {}
    for row in _rows(tables["tbitemtype"]):
        if isinstance(row, dict) and row.get("id") is not None:
            item_types[str(row["id"])] = _text(row.get("typeName"))
    steals = {str(r.get("id")): r for r in _rows(tables["tbsteal"]) if isinstance(r, dict)}
    items = {}
    for row in _rows(tables["tbitem"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        rule = steals.get(str(row.get("steal_id"))) if row.get("steal_id") else None
        steal = None
        if rule:
            steal = {
                "rate": int(round(float(rule.get("rate_base") or 0) * 100)),
                "count": rule.get("steal_count") or 1,
                "kill": bool(rule.get("trigger_kill")),
                "intimacy": rule.get("intimacy_delta_self") or 0,
                "alignment": rule.get("alignment_delta_success") or 0,
            }
        items[str(row["id"])] = {
            "name": _text(row.get("itemName")) or ("物品 %s" % row["id"]),
            "type": item_types.get(str(row.get("itemType")), "") or "未分类",
            "quality": row.get("quality"),
            "price": row.get("price"),
            "steal": steal,
            "demand": bool(row.get("canDemand")),
            "demand_cost": _int(row.get("intimacy_deduction")),
        }
    realms = build_realms(tables)
    # 索要：tbnpcbagrule 按 NPC 配置指向索要模板，模板里是该 NPC 可被索要的固定物品池。
    templates = {str(r.get("id")): r for r in _rows(tables["tbnpcitemdemandholdtemplate"])
                 if isinstance(r, dict) and r.get("id") is not None}
    demands = {}
    for rule in _rows(tables["tbnpcbagrule"]):
        if not isinstance(rule, dict) or rule.get("npcId") is None:
            continue
        template = templates.get(str(rule.get("demandTemplateId")))
        if not template:
            continue
        ids = []
        for entry in template.get("demandItemList") or []:
            if isinstance(entry, dict) and entry.get("itemId") is not None:
                ids.append(_int(entry.get("itemId")))
        if ids:
            demands[str(rule.get("npcId"))] = ids
    tiers = []
    for row in _rows(tables["tbnpcintimacy"]):
        if not isinstance(row, dict) or row.get("intimacyRequirement") is None:
            continue
        name = _text(row.get("intimacyName")).replace("\u200b", "").strip()
        if not name:
            continue
        tiers.append({"name": name, "need": _int(row.get("intimacyRequirement"))})
    tiers.sort(key=lambda t: t["need"])
    npc_rows = [r for r in _rows(tables["tbnpcbasecfg"]) if isinstance(r, dict)]
    # 若整张表都没有 can_steal 字段，视为该版本取消了这层限制，改由物品参数单独判定。
    has_flag = any("can_steal" in row for row in npc_rows)
    npcs = {}
    for row in npc_rows:
        if row.get("id") is None:
            continue
        layer = row.get("propLayerId")
        npcs[str(row["id"])] = {
            "name": _text(row.get("npcName")) or _text(row.get("npcTitle")) or ("#%s" % row["id"]),
            "realm": realms.get(str(layer or 0)) or _text(row.get("layerZeroShowText")) or "凡人",
            "can_steal": bool(row.get("can_steal", True)) if has_flag else True,
            "demand": demands.get(str(row["id"])) or [],
        }
    if not items:
        raise ValueError("物品配置为空")
    return {"schema": SCHEMA, "items": items, "npcs": npcs, "intimacy": tiers,
            "spaces": build_spaces(tables), "realms": realms}


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _num(value):
    """数值转文本：10.0 → 10，0.35 保留小数。"""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _fill(template, values):
    """把文案里的 {0} {1} 换成实际数值。"""
    text = template or ""
    for index, value in enumerate(values or []):
        text = text.replace("{%d}" % index, _num(value))
    return text


def build_pill(tables):
    """炼丹只读元数据：丹方、药材、丹炉、等级与秘境遁点。"""
    items = {str(r.get("id")): r for r in _rows(tables["tbitem"]) if isinstance(r, dict)}
    levels = {}
    for row in _rows(tables["tbpilllevel"]):
        if isinstance(row, dict) and row.get("level") is not None:
            levels[str(row["level"])] = {
                "exp": _int(row.get("required_exp")),
                "title": _text(row.get("title")),
            }
    furnaces = []
    for row in _rows(tables["tbpillfurnace"]):
        if isinstance(row, dict) and row.get("id") is not None:
            furnaces.append({"id": _int(row["id"]), "name": _text(row.get("name"))
                             or ("丹炉 %s" % row["id"])})
    herbs = []
    for row in _rows(tables["tbpillherb"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        herbs.append({
            "id": _int(row["id"]),
            "name": _text(row.get("name")) or ("药材 %s" % row["id"]),
            "tier": _int(row.get("tier")),
            "element": _int(row.get("element")),
            "item_id": _int(row.get("item_id")),
            "rare": bool(row.get("is_rare")),
            "desc": _text(row.get("desc")),
        })
    recipes = []
    for row in _rows(tables["tbpillrecipe"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        effects = []
        for eff in row.get("main_effects") or []:
            if isinstance(eff, dict):
                effects.append({"type": _int(eff.get("type")),
                                "values": [_int(v) for v in (eff.get("values") or [])]})
        recipes.append({
            "id": _int(row["id"]),
            "name": _text(row.get("name")) or ("丹方 %s" % row["id"]),
            "tier": _int(row.get("tier")),
            "element": _int(row.get("element")),
            "item_id": _int(row.get("item_id")),
            "toxin_max": _int(row.get("toxin_max")),
            "max_craft": _int(row.get("max_craft_count")),
            "desc": _text(row.get("desc")),
            "effects": effects,
            "thresholds": [_int(row.get("fan_threshold")), _int(row.get("xian_threshold")),
                           _int(row.get("shen_threshold"))],
            "spirit": _int(row.get("spirit_progress")),
            "time": _int(row.get("total_time")),
        })
    recipe_by_name = {str(r["name"]): r["id"] for r in recipes}
    herb_by_id = {h["id"]: h for h in herbs}
    portals = []
    for row in _rows(tables["tbpillsecretportal"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        desc = _text(row.get("description"))
        cost_id = _int(row.get("cost_herb_id"))
        herb = herb_by_id.get(cost_id)
        cost_item = items.get(str(herb["item_id"] if herb else cost_id)) or {}
        cost = None
        if cost_id:
            cost = {"id": cost_id,
                    "name": (herb or {}).get("name") or _text(cost_item.get("itemName"))
                    or ("物品 %s" % cost_id),
                    "count": _int(row.get("cost_count"))}
        portals.append({
            "id": _int(row["id"]),
            "name": _text(row.get("name")) or ("遁点 %s" % row["id"]),
            "key": str(row.get("key") or ""),
            "realm": _int(row.get("destination_realm")),
            "furnace": _int(row.get("min_furnace")),
            "desc": desc,
            "hint": _text(row.get("unlock_hint")),
            "cost": cost,
            "mentions": [{"name": name, "recipe_id": recipe_by_name.get(name)}
                         for name in re.findall(r"「(.+?)」", desc)],
        })
    if not recipes:
        raise ValueError("炼丹配置为空")
    phases = {}
    for row in _rows(tables["tbcultivaterealm"]):
        if not isinstance(row, dict):
            continue
        realm_id = _int(row.get("id"))
        for phase in row.get("phases") or []:
            phases[str(_int(phase))] = realm_id
    return {"schema": SCHEMA, "recipes": recipes, "herbs": herbs, "portals": portals,
            "furnaces": furnaces, "levels": levels, "realms": build_realms(tables),
            "phases": phases}


FORGE_QUALITY_NAMES = ["白", "绿", "蓝", "紫", "橙"]
FORGE_SLOT_NAMES = {"1": "攻击", "2": "防御", "3": "辅助", "4": "速度"}


def build_forge(tables):
    """炼器只读元数据：器胚、棋盘布局、器契门槛、五色精粹、词条池与洗练保底。"""
    items = {str(_int(r.get("id"))): r for r in _rows(tables["tbitem"]) if isinstance(r, dict)}
    attributes = {str(_int(r.get("id"))): _text(r.get("name"))
                  for r in _rows(tables["tbattribute"]) if isinstance(r, dict)}
    elements = {}
    for row in _rows(tables["tbelement"]):
        if isinstance(row, dict) and _int(row.get("id")):
            elements[str(_int(row.get("id")))] = _text(row.get("element_name"))
    layouts = {str(_int(r.get("id"))): r
               for r in _rows(tables["tbalchemylayout"]) if isinstance(r, dict)}
    materials = {}
    for row in _rows(tables["tbalchemymaterial"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        mid = str(_int(row.get("id")))
        item = items.get(mid) or {}
        materials[mid] = {
            "name": _text(item.get("itemName")) or ("材料 %s" % mid),
            "element": _int(row.get("element_type")),
            "spirit": _int(row.get("spirit_value")),
            "quality": _int(item.get("quality")),
            "realm": _int(item.get("cultivateRealm")),
        }
    levels = []
    for row in _rows(tables["tbalchemylevel"]):
        if not isinstance(row, dict) or row.get("level") is None:
            continue
        levels.append({
            "level": _int(row.get("level")), "title": _text(row.get("title")),
            "exp": _int(row.get("required_exp")), "true_fire": _int(row.get("true_fire_base")),
            "points": _int(row.get("talent_point_reward")),
            "unlock": [_int(x) for x in (row.get("unlock_talent_ids") or [])],
        })
    levels.sort(key=lambda r: r["level"])
    talents = []
    for row in _rows(tables["tbalchemytalent"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        talents.append({
            "id": _int(row.get("id")), "name": _text(row.get("name")) or ("天赋 %s" % row["id"]),
            "desc": _text(row.get("desc")), "level": _int(row.get("required_level")),
            "cost": _int(row.get("talent_point_cost")), "type": _int(row.get("talent_type")),
            "params": row.get("effect_params") or [],
        })
    talents.sort(key=lambda r: r["id"])
    score_tiers = []
    for row in _rows(tables["tbalchemyscoretier"]):
        if isinstance(row, dict) and row.get("id") is not None:
            score_tiers.append({"id": _int(row.get("id")), "name": _text(row.get("name"))})
    score_tiers.sort(key=lambda r: r["id"])
    pity = []
    for row in _rows(tables["tbalchemywashpity"]):
        if isinstance(row, dict):
            pity.append({"realm": _int(row.get("realm_id")),
                         "quality": _int(row.get("affix_quality_id")),
                         "count": _int(row.get("pity_count"))})
    affix_pool = {}
    for row in _rows(tables["tbalchemyartifactaffixpool"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        affix_pool[str(_int(row.get("id")))] = {
            "attr": _int(row.get("attribute_id")), "text": _plain(row.get("desc")),
            "quality": _int(row.get("quality_id")), "pool": _int(row.get("pool_id")),
            "min": row.get("min_value"), "max": row.get("max_value"),
        }
    prototypes = []
    for row in _rows(tables["tbalchemyprototype"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        pid = _int(row.get("id"))
        item = items.get(str(pid)) or {}
        layout = layouts.get(str(_int(row.get("board_layout_id")))) or {}
        effects = []
        for eff in row.get("effects") or []:
            if not isinstance(eff, dict):
                continue
            material_id = _int(eff.get("material_id"))
            effects.append({
                "e": _int(eff.get("element_type")), "energy": _int(eff.get("required_energy")),
                "mat": material_id,
                "mat_name": (materials.get(str(material_id)) or {}).get("name")
                or ("材料 %s" % material_id),
                "count": _int(eff.get("material_count"), 1), "sort": _int(eff.get("sort")),
            })
        effects.sort(key=lambda x: x["sort"])
        tiers = []
        for tier in row.get("score_tiers") or []:
            if not isinstance(tier, dict):
                continue
            output_id = _int(tier.get("output_item_id"))
            output_item = items.get(str(output_id)) or {}
            tiers.append({
                "t": _int(tier.get("tier_id")), "min": _int(tier.get("score_min")),
                "out": output_id, "out_name": _text(output_item.get("itemName")),
                "attrs": [[_int(a.get("type")), _int(a.get("value"))]
                          for a in (tier.get("attributes") or []) if isinstance(a, dict)],
            })
        tiers.sort(key=lambda x: x["t"])
        prototypes.append({
            "id": pid, "name": _text(item.get("itemName")) or ("器胚 %s" % pid),
            "realm": _int(item.get("cultivateRealm")),
            "req_cult": _int(item.get("required_cultivation")),
            "quality": _int(item.get("quality")), "slot": _int(row.get("slot_type")),
            "board": _int(row.get("board_size")),
            "blocked": [[_int(c.get("x")), _int(c.get("y"))]
                        for c in (layout.get("blocked_cells") or []) if isinstance(c, dict)],
            "bonus": [[_int(c.get("x")), _int(c.get("y")), _int(c.get("element_type"))]
                      for c in (layout.get("bonus_cells") or []) if isinstance(c, dict)],
            "need": [{"e": _int(r.get("type")), "v": _int(r.get("value"))}
                     for r in (row.get("material_requirements") or []) if isinstance(r, dict)],
            "rec": [{"e": _int(r.get("type")), "v": _int(r.get("value"))}
                    for r in (row.get("recommended_spirit") or []) if isinstance(r, dict)],
            "rec_total": _int(row.get("recommended_total_spirit")),
            "energy": _int(row.get("energy_cost")),
            "effects": effects, "tiers": tiers,
        })
    if not prototypes:
        raise ValueError("炼器配置为空")
    used = set(materials) | {str(p["id"]) for p in prototypes}
    for proto in prototypes:
        used |= {str(tier["out"]) for tier in proto["tiers"]}
    item_index = {}
    for key in used:
        item = items.get(key)
        if item:
            item_index[key] = [_text(item.get("itemName")), _int(item.get("quality")),
                               _int(item.get("cultivateRealm"))]
    return {"schema": SCHEMA, "levels": levels, "talents": talents,
            "score_tiers": score_tiers, "qualities": FORGE_QUALITY_NAMES,
            "slots": FORGE_SLOT_NAMES, "elements": elements, "attributes": attributes,
            "realms": build_realms(tables), "materials": materials,
            "affix_pool": affix_pool, "pity": pity, "items": item_index,
            "prototypes": prototypes}


EVENT_GRADE_NAMES = {1: "上品", 2: "中品", 3: "下品"}
EVENT_GRADE_HINT = "上品结局的平均奖励优于中品，中品优于下品；具体奖励见每条结局。"

_OP_NAMES = {
    ">=": ">=", "大于等于": ">=", ">": ">", "大于": ">",
    "<": "<", "小于": "<", "<=": "<=", "小于等于": "<=",
    "==": "==", "等于": "==", "!=": "!=",
}


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


def _lines(value):
    """把“善恶值 +10|好感度 -10”这类多段文案拆成列表。"""
    return [part.strip() for part in re.split(r"[|\n]", _text(value)) if part.strip()]


def _clip(text, limit):
    return text if len(text) <= limit else text[:limit] + "…"


def _designer_path(note):
    """从策划备注里取出结局达成路径（“路径：A > B > C”）。"""
    text = _text(note)
    match = re.search(r"路径[:：]\s*(.+)$", text, re.S)
    if not match:
        return []
    tail = re.split(r"[；;]", match.group(1))[0]
    steps = [part.strip(" 　。") for part in re.split(r"\s*[>＞]\s*", tail)]
    return [step for step in steps if step]


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
        if "·" in name:
            head = name.split("·", 1)[0].strip()
            parent = next((other for other, other_name in names.items()
                           if other != quest_id and other_name == head), 0)
        if not parent and quest_id - 5800 in events:
            parent = quest_id - 5800
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
        endings = []
        for row in sorted(rows, key=lambda r: (_int(r.get("grade")), _int(r.get("id")))):
            drop_id = _int(row.get("reward_drop_id"))
            rewards = ending_rewards(drop_id) if drop_id else []
            grade = _int(row.get("grade"))
            endings.append({
                "id": _int(row.get("id")), "title": _plain(row.get("title"))
                or ("结局 %s" % row.get("id")), "summary": _plain(row.get("summary")),
                "detail": _lines(row.get("detail_lines")), "grade": grade,
                "grade_name": EVENT_GRADE_NAMES.get(grade, "第%s档" % grade),
                "path": _designer_path(row.get("designer_note")),
                "rewards": rewards or [],
                "reward_ok": True if not drop_id else rewards is not None,
            })
        resolved[quest_id] = location
        tree = _build_tree(quest_id, dialogues, flows, attrs, quest_names)
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


BUILTIN_FILES = {
    "bedroom": "bedroom_meta.json", "talent": "talent_meta.json", "items": "items_meta.json",
    "pill": "pill_meta.json", "forge": "forge_meta.json", "event": "event_meta.json",
    "quest": "quest_meta.json",
}
BUILDERS = {"bedroom": build_bedroom, "talent": build_talent, "items": build_items,
            "pill": build_pill, "forge": build_forge, "event": build_event, "quest": build_quests}


def _builtin(directory, module):
    data = _read_json(os.path.join(directory, BUILTIN_FILES[module]))
    if module == "bedroom":
        valid = isinstance(data, list)
    elif module == "talent":
        valid = isinstance(data, dict) and isinstance(data.get("talents"), list)
    elif module == "pill":
        valid = isinstance(data, dict) and isinstance(data.get("recipes"), list)
    elif module == "forge":
        valid = isinstance(data, dict) and isinstance(data.get("prototypes"), list)
    elif module == "event":
        valid = isinstance(data, dict) and isinstance(data.get("events"), list)
    elif module == "quest":
        valid = isinstance(data, dict) and isinstance(data.get("quests"), list)
    else:
        valid = isinstance(data, dict) and isinstance(data.get("items"), dict)
    if not valid:
        raise ValueError("%s内置快照无效" % MODULE_NAMES.get(module, module))
    return data


def load_metadata(game_dir, builtin_dir, modules=("bedroom", "talent"), cache_dir=None):
    """返回 (数据, 来源报告)；任何更新失败都回退，不阻断存档查询。"""
    modules = tuple(dict.fromkeys(modules))
    cache_dir = cache_dir or cache_directory()
    cache_path = os.path.join(cache_dir, "game_meta_cache.json")
    state_path = os.path.join(cache_dir, "meta_update_state.json")
    cache = _read_json(cache_path, {}) or {}
    if cache.get("schema") != CACHE_SCHEMA or not isinstance(cache.get("modules"), dict):
        cache = {"schema": CACHE_SCHEMA, "modules": {}}
    state = _read_json(state_path, {}) or {}
    result, report = {}, {"modules": {}, "warnings": [], "fingerprint": ""}
    inspection = None
    inspect_error = ""
    try:
        inspection = inspect_game(game_dir)
        report["fingerprint"] = inspection["fingerprint"]
        report["package_version"] = inspection["source"]["package_version"]
    except Exception as e:
        inspect_error = str(e)

    unresolved = []
    for module in modules:
        entry = (cache.get("modules") or {}).get(module) or {}
        data = entry.get("data")
        if inspection and data is not None and entry.get("fingerprint") == inspection["fingerprint"]:
            result[module] = data
            report["modules"][module] = {"source": "current", "label": "游戏当前配置"}
        else:
            unresolved.append(module)

    failed = state.get("fingerprint") == report["fingerprint"] and inspection
    failed_modules = set(state.get("modules") or []) if failed else set()
    to_extract = [m for m in unresolved if m not in failed_modules] if inspection else []
    errors = {}
    if to_extract:
        try:
            tables = _extract_tables(inspection)
            for module in to_extract:
                try:
                    missing = MODULE_TABLES[module] - set(tables)
                    if missing:
                        raise ValueError("缺少配置表：%s" % ", ".join(sorted(missing)))
                    data = BUILDERS[module](tables)
                    result[module] = data
                    cache["modules"][module] = {
                        "fingerprint": inspection["fingerprint"], "generated_at": int(time.time()), "data": data,
                    }
                    report["modules"][module] = {"source": "current", "label": "游戏当前配置"}
                except Exception as e:
                    errors[module] = str(e)
        except Exception as e:
            for module in to_extract:
                errors[module] = str(e)
        try:
            _atomic_json(cache_path, cache)
        except Exception as e:
            report["warnings"].append("配置已读取，但缓存写入失败：%s" % e)
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
        entry = (cache.get("modules") or {}).get(module) or {}
        if entry.get("data") is not None:
            result[module] = entry["data"]
            report["modules"][module] = {"source": "cache", "label": "兼容缓存"}
        else:
            try:
                result[module] = _builtin(builtin_dir, module)
                report["modules"][module] = {"source": "builtin", "label": "内置快照"}
            except Exception as e:
                errors[module] = str(e)
                if module == "bedroom":
                    fallback = []
                elif module == "talent":
                    fallback = {"schema": SCHEMA, "talents": [], "npcs": {}, "spaces": {},
                                "realms": {"0": "凡人"}}
                elif module == "pill":
                    fallback = {"schema": SCHEMA, "recipes": [], "herbs": [], "portals": [],
                                "furnaces": [], "levels": {}, "realms": {"0": "凡人"}}
                elif module == "forge":
                    fallback = {"schema": SCHEMA, "prototypes": [], "materials": {},
                                "items": {}, "levels": [], "talents": [], "score_tiers": [],
                                "qualities": FORGE_QUALITY_NAMES, "slots": FORGE_SLOT_NAMES,
                                "elements": {}, "attributes": {}, "affix_pool": {},
                                "pity": [], "realms": {"0": "凡人"}}
                elif module == "event":
                    fallback = {"schema": SCHEMA, "events": [], "realms": {"0": "凡人"},
                                "grades": EVENT_GRADE_NAMES,
                                "stats": {"events": 0, "endings": 0}}
                elif module == "quest":
                    fallback = {"schema": SCHEMA, "quests": [], "groups": [],
                                "realms": {"0": "凡人"},
                                "states": {str(k): v for k, v in QUEST_STATE_NAMES.items()},
                                "types": {}, "stats": {"quests": 0, "with_rewards": 0}}
                else:
                    fallback = {"schema": SCHEMA, "items": {}, "npcs": {}, "spaces": {},
                                "realms": {"0": "凡人"}}
                result[module] = fallback
                report["modules"][module] = {"source": "missing", "label": "无可用配置"}
        if module in errors:
            report["modules"][module]["warning"] = errors[module]
    if inspect_error and unresolved:
        report["warnings"].append("未读取游戏当前配置：%s" % inspect_error)
    for module, message in errors.items():
        if module in modules:
            report["warnings"].append("%s 配置更新失败，已使用兜底数据：%s" % (
                MODULE_NAMES.get(module, module), message))
    return result, report


def export_snapshots(game_dir, output_dir):
    inspection = inspect_game(game_dir)
    tables = _extract_tables(inspection)
    _atomic_json(os.path.join(output_dir, "bedroom_meta.json"), build_bedroom(tables))
    _atomic_json(os.path.join(output_dir, "talent_meta.json"), build_talent(tables))
    _atomic_json(os.path.join(output_dir, "items_meta.json"), build_items(tables))
    _atomic_json(os.path.join(output_dir, "pill_meta.json"), build_pill(tables))
    _atomic_json(os.path.join(output_dir, "pill_map.json"), build_pill_map(tables, inspection))
    _atomic_json(os.path.join(output_dir, "forge_meta.json"), build_forge(tables))
    _atomic_json(os.path.join(output_dir, "event_meta.json"), build_event(tables))
    _atomic_json(os.path.join(output_dir, "quest_meta.json"), build_quests(tables))
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
