# -*- coding: utf-8 -*-
"""炼丹：配置表 → 模块快照（自 meta_update.py 原样搬入）。"""
import os
import re
import struct
import time

from meta_update import (
    CACHE_SCHEMA, SCHEMA, _atomic_json, _extract_tables, _int, _plain, _read_json, _rows,
    _text, build_realms, cache_directory, inspect_game,
)


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


# 插件统一入口
build = build_pill
