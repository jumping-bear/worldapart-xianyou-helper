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
CACHE_SCHEMA = 3
TABLES = {
    "tbnpcbasecfg", "tbnpcbedroom", "tbscenepresentationinteraction",
    "tbscenepresentationaction", "tbspace", "tbnpctalent", "tbcultivaterealm",
    "tbitem", "tbsteal", "tbitemtype", "tbpillrecipe", "tbpillherb",
    "tbpillsecretportal", "tbpillfurnace", "tbpilllevel", "tbpillportal",
    "tbpilleffect", "tbpillexplorepoi", "tbattribute",
}
MODULE_TABLES = {
    "bedroom": {"tbnpcbasecfg", "tbnpcbedroom", "tbscenepresentationinteraction",
                "tbscenepresentationaction"},
    "talent": {"tbnpcbasecfg", "tbspace", "tbnpctalent", "tbcultivaterealm"},
    "items": {"tbnpcbasecfg", "tbspace", "tbcultivaterealm", "tbitem", "tbsteal", "tbitemtype"},
    "pill": {"tbitem", "tbpillrecipe", "tbpillherb", "tbpillsecretportal",
             "tbpillfurnace", "tbpilllevel", "tbcultivaterealm", "tbpillportal",
             "tbpilleffect", "tbpillexplorepoi", "tbattribute"},
}
MODULE_NAMES = {"bedroom": "十八摸", "talent": "NPC天赋", "items": "NPC物品", "pill": "炼丹"}


def resolve_table(name):
    """把资源表名映射到规范名；精确匹配优先，其次取最长前缀，兼容后续版本的表名后缀变化。"""
    name = str(name or "").lower()
    if name in TABLES:
        return name
    best = ""
    for known in TABLES:
        if name.startswith(known) and len(known) > len(best):
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
            if isinstance(raw, str):
                text = raw
            else:
                raw = bytes(raw)
                if not raw.lstrip()[:1] in (b"{", b"["):
                    continue
                text = raw.decode("utf-8-sig")
            if not text.lstrip()[:1] in ("{", "["):
                continue
            value = json.loads(text)
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
PILL_MAP_SCHEMA = 5


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
    for row in _rows(tables.get("tbpillportal") or []):
        if isinstance(row, dict):
            portals[str(_int(row.get("id")))] = [
                _text(row.get("name")), _int(row.get("element")),
                bool(row.get("two_way")), _plain(row.get("desc")),
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
        }
    realms = build_realms(tables)
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
        }
    if not items:
        raise ValueError("物品配置为空")
    return {"schema": SCHEMA, "items": items, "npcs": npcs,
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


BUILTIN_FILES = {
    "bedroom": "bedroom_meta.json", "talent": "talent_meta.json", "items": "items_meta.json",
    "pill": "pill_meta.json",
}
BUILDERS = {"bedroom": build_bedroom, "talent": build_talent, "items": build_items,
            "pill": build_pill}


def _builtin(directory, module):
    data = _read_json(os.path.join(directory, BUILTIN_FILES[module]))
    if module == "bedroom":
        valid = isinstance(data, list)
    elif module == "talent":
        valid = isinstance(data, dict) and isinstance(data.get("talents"), list)
    elif module == "pill":
        valid = isinstance(data, dict) and isinstance(data.get("recipes"), list)
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
