# -*- coding: utf-8 -*-
"""炼丹扫描。"""
import meta_update

from .. import common

KEY = "pill"
LABEL = "炼丹"


def _manual_field(entry, name):
    """丹方手记字段带 alchemy_recipe_manual_entry_ 前缀，兼容旧写法。"""
    return entry.get("alchemy_recipe_manual_entry_" + name, entry.get(name))


def scan_pill(obj, meta, mapdata):
    """整理炼丹进度：等级、炉子、丹方手册、已拾取点，并挂上盘面数据。"""
    player = obj.get("playerModel") or {}
    rp = player.get("refining_pills") or {}
    herbs = {str(h.get("id")): h for h in (meta.get("herbs") or []) if isinstance(h, dict)}
    recipes = {str(r.get("id")): r for r in (meta.get("recipes") or []) if isinstance(r, dict)}
    manual = []
    entries = (player.get("pill_recipe_manual") or {}).get("alchemy_recipe_manual_entries") or {}
    for entry in (entries.values() if isinstance(entries, dict) else entries):
        if not isinstance(entry, dict):
            continue
        recipe_id = _manual_field(entry, "recipe_id")
        info = recipes.get(str(recipe_id)) or {}
        stats = _manual_field(entry, "herb_stats") or {}
        manual.append({
            "id": recipe_id, "name": info.get("name") or ("丹方 %s" % recipe_id),
            "tier": info.get("tier") or 0, "element": info.get("element") or 0,
            "grade": _manual_field(entry, "best_grade") or 0,
            "craft": _manual_field(entry, "craft_count") or 0,
            "toxin": _manual_field(entry, "toxin") or 0,
            "effects": _manual_field(entry, "effect_ids") or [],
            "herbs": [[(herbs.get(str(k)) or {}).get("name") or str(k), v]
                      for k, v in sorted(stats.items(), key=lambda kv: str(kv[0]))],
        })
    manual.sort(key=lambda r: (r["tier"], str(r["name"])))
    history = player.get("refining_pills_craft_history") or {}
    realm_id = (meta.get("phases") or {}).get(str((player.get("combat") or {}).get("cultivate_layer_id")))
    return {
        "level": rp.get("rp_level") or 0, "exp": rp.get("rp_exp") or 0,
        "furnace": rp.get("rp_unlocked_furnace") or 0,
        "current_furnace": rp.get("rp_current_furnace") or 0,
        "realm": (meta.get("realms") or {}).get(str(realm_id)) or "",
        "manual": manual,
        "highest_grade": history.get("highest_crafted_grade") or 0,
        "consumed": sorted(int(x) for x in (rp.get("rp_consumed_once_poi_ids") or [])
                           if isinstance(x, int)),
        "map": mapdata, "fog": [],
    }


def meta(metadata):
    return metadata.get("pill") or {"recipes": [], "herbs": [], "realms": {"0": "凡人"},
                                    "phases": {}}


def prepare(game_dir):
    return meta_update.load_pill_map(game_dir, common.BUILTIN_DIR)


def scan(obj, meta_obj, state=None):
    mapdata = state[0] if state else {}
    return scan_pill(obj, meta_obj, mapdata)


def post(rows, state, original, path):
    mapdata = state[0] if state else {}
    rows["fog"] = {m.get("name") or "default":
                   meta_update.load_fog_strokes(original or path, m.get("name") or "default")
                   for m in (mapdata.get("maps") or [])}
    return rows


def enrich(module, meta_obj, state=None):
    mapdata, info = state if state else ({}, {})
    if not module["rows"].get("map"):
        module["rows"]["map"] = mapdata
    module["map_config"] = info.get("label", "未知")
    module["map_warning"] = info.get("warning", "")
    return module


def summary(module):
    rows = module.get("rows") or {}
    pill_map = rows.get("map") or {}
    maps = pill_map.get("maps") or []
    pois = maps[0].get("pois") or [] if maps else []
    return "炼丹：%s 级，%d 张丹方手记，盘面 %d 张 / %d 个拾取点（已拾取 %d）" % (
        rows.get("level", 0), len(rows.get("manual") or []), len(maps), len(pois),
        len(rows.get("consumed") or []))
