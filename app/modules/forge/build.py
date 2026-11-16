# -*- coding: utf-8 -*-
"""炼器：配置表 → 模块快照（自 meta_update.py 原样搬入）。"""
from meta_update import (
    SCHEMA, _int, _plain, _rows, _text, build_realms,
)


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


# 插件统一入口
build = build_forge
