# -*- coding: utf-8 -*-
"""炼器扫描。"""
from ...common import bag_entries


def _forge_number(value):
    try:
        text = "%.2f" % float(value)
    except (TypeError, ValueError):
        return str(value)
    return text.rstrip("0").rstrip(".") or "0"


def scan_forge(obj, meta):
    """整理炼器进度：等级天赋、器胚与材料库存、法宝器契词条与洗练保底。"""
    player = obj.get("playerModel") or {}
    alchemy = player.get("alchemy") or {}
    prototypes = {str(p.get("id")): p for p in (meta.get("prototypes") or []) if isinstance(p, dict)}
    materials = meta.get("materials") or {}
    item_meta = meta.get("items") or {}
    attributes = meta.get("attributes") or {}
    elements = meta.get("elements") or {}
    slots = meta.get("slots") or {}
    realms = meta.get("realms") or {}
    qualities = meta.get("qualities") or []
    tier_names = {str(t.get("id")): t.get("name") for t in (meta.get("score_tiers") or [])}
    affix_pool = meta.get("affix_pool") or {}
    pity_limit, pity_done = {}, {}
    for row in meta.get("pity") or []:
        pity_limit[(int(row.get("realm") or 0), int(row.get("quality") or 0))] = int(row.get("count") or 0)
    for row in alchemy.get("alchemy_wash_pity_counters") or []:
        if isinstance(row, dict):
            pity_done[(int(row.get("realm_id") or 0),
                       int(row.get("artifact_quality_id") or 0))] = int(row.get("count") or 0)

    def item_info(item_id):
        info = item_meta.get(str(item_id)) or []
        name = info[0] if len(info) > 0 else ""
        quality = int(info[1] or 0) if len(info) > 1 else 0
        realm_id = int(info[2] or 0) if len(info) > 2 else 0
        return name or ("物品 %s" % item_id), quality, realm_id

    def realm_name(realm_id):
        return realms.get(str(realm_id)) or ("境界 %s" % realm_id)

    owned = {}
    for entry in bag_entries(player.get("bag")):
        item_id = entry.get("item_id")
        if item_id is None:
            continue
        owned[str(item_id)] = owned.get(str(item_id), 0) + int(entry.get("count") or 1)

    # 材料盘点：按五行汇总件数与灵性
    material_rows, element_totals = [], {}
    for material_id, info in materials.items():
        count = owned.get(material_id, 0)
        if not count:
            continue
        element = int(info.get("element") or 0)
        material_rows.append({
            "id": int(material_id), "name": info.get("name") or ("材料 %s" % material_id),
            "element": element, "spirit": int(info.get("spirit") or 0),
            "quality": int(info.get("quality") or 0), "realm": int(info.get("realm") or 0),
            "count": count,
        })
        bucket = element_totals.setdefault(str(element), {"count": 0, "spirit": 0})
        bucket["count"] += count
        bucket["spirit"] += count * int(info.get("spirit") or 0)
    material_rows.sort(key=lambda r: (r["element"], -r["spirit"], r["id"]))
    element_rows = sorted(
        ({"element": int(key), "name": elements.get(key, ""), "count": value["count"],
          "spirit": value["spirit"]} for key, value in element_totals.items()),
        key=lambda r: r["element"])

    # 我的器胚与五行缺口
    embryos = []
    for prototype_id, proto in prototypes.items():
        count = owned.get(prototype_id, 0)
        if not count:
            continue
        need = []
        for req in proto.get("need") or []:
            element = str(req.get("e"))
            have = (element_totals.get(element) or {}).get("count", 0)
            need.append({"e": int(req.get("e") or 0), "name": elements.get(element, ""),
                         "need": int(req.get("v") or 0), "have": have,
                         "gap": max(0, int(req.get("v") or 0) - have)})
        embryos.append({
            "id": int(prototype_id), "name": proto.get("name"), "count": count,
            "realm": int(proto.get("realm") or 0), "realm_name": realm_name(proto.get("realm") or 0),
            "slot": int(proto.get("slot") or 0), "slot_name": slots.get(str(proto.get("slot")), ""),
            "board": int(proto.get("board") or 0), "need": need,
            "rec_total": int(proto.get("rec_total") or 0),
            "effects": proto.get("effects") or [],
        })
    embryos.sort(key=lambda r: (r["realm"], r["slot"], r["id"]))

    # 已炼成的法宝
    artifacts = []
    for entry in bag_entries(player.get("bag")):
        if "alchemy_proto_item_id" not in entry:
            continue
        name, quality, item_realm = item_info(entry.get("item_id"))
        proto = prototypes.get(str(entry.get("alchemy_proto_item_id"))) or {}
        artifact_realm = int(proto.get("realm") or item_realm or 0)
        tier_id = int(entry.get("alchemy_tier_id") or 0)
        affixes = []
        for pending, saved in ((False, entry.get("alchemy_affixes") or []),
                               (True, entry.get("pending_alchemy_affixes") or [])):
            for affix in saved:
                if not isinstance(affix, dict):
                    continue
                config = affix_pool.get(str(affix.get("config_id"))) or {}
                text = config.get("text") or ("词条 %s" % affix.get("config_id"))
                affixes.append({"text": text.replace("{0}", _forge_number(affix.get("value"))),
                                "quality": int(config.get("quality") or 0), "pending": pending})
        artifact_pity = []
        for quality_id, label in ((3, qualities[3] if len(qualities) > 3 else "紫"),
                                  (4, qualities[4] if len(qualities) > 4 else "橙")):
            total = pity_limit.get((artifact_realm, quality_id)) or 0
            if total:
                artifact_pity.append({
                    "name": label, "count": pity_done.get((artifact_realm, quality_id), 0),
                    "total": total,
                })
        artifacts.append({
            "uid": entry.get("uid"), "item_id": entry.get("item_id"), "name": name,
            "quality": quality, "realm": artifact_realm, "realm_name": realm_name(artifact_realm),
            "slot": int(proto.get("slot") or 0), "slot_name": slots.get(str(proto.get("slot")), ""),
            "proto": int(entry.get("alchemy_proto_item_id") or 0),
            "proto_name": proto.get("name") or "", "crafted": bool(entry.get("alchemy_crafted")),
            "tier": tier_id, "tier_name": tier_names.get(str(tier_id), ""),
            "score": int(entry.get("alchemy_score") or 0),
            "equipped": bool(entry.get("is_equipped")),
            "attrs": [[attributes.get(str(int(attr[0])), str(attr[0])), int(attr[1])]
                      for attr in (entry.get("alchemy_attrs") or [])
                      if isinstance(attr, (list, tuple)) and len(attr) >= 2],
            "affixes": affixes,
            "wash": [{"e": int(effect.get("e") or 0), "name": elements.get(str(effect.get("e")), ""),
                      "material": effect.get("mat_name"), "count": int(effect.get("count") or 1)}
                     for effect in (proto.get("effects") or [])],
            "pity": artifact_pity,
        })
    artifacts.sort(key=lambda r: (not r["equipped"], -r["score"], r["name"]))

    level = int(alchemy.get("alchemy_level") or 0)
    level_info = {}
    for row in meta.get("levels") or []:
        if int(row.get("level") or 0) == level:
            level_info = row
    talent_names = {str(t.get("id")): t.get("name") for t in (meta.get("talents") or [])}
    best_tier = int(alchemy.get("alchemy_highest_crafted_tier_id") or 0)
    return {
        "level": level, "exp": int(alchemy.get("alchemy_exp") or 0),
        "exp_need": int(level_info.get("exp") or 0),
        "level_title": level_info.get("title") or "",
        "true_fire": int(level_info.get("true_fire") or 0),
        "talent_points": int(alchemy.get("alchemy_talent_points") or 0),
        "unlocked": [{"id": x, "name": talent_names.get(str(x), "")}
                     for x in (alchemy.get("alchemy_unlocked_talents") or []) if isinstance(x, int)],
        "learned": [{"id": x, "name": talent_names.get(str(x), "")}
                    for x in (alchemy.get("alchemy_learned_talents") or []) if isinstance(x, int)],
        "best_score": int(alchemy.get("alchemy_best_score") or 0),
        "best_tier": best_tier, "best_tier_name": tier_names.get(str(best_tier), ""),
        "embryos": embryos,
        "embryo_total": sum(row["count"] for row in embryos),
        "materials": material_rows, "elements": element_rows,
        "artifacts": artifacts,
        "pity": [{"realm": realm_id, "realm_name": realm_name(realm_id), "quality": quality_id,
                  "quality_name": qualities[quality_id] if quality_id < len(qualities) else str(quality_id),
                  "count": pity_done.get((realm_id, quality_id), 0), "total": total}
                 for (realm_id, quality_id), total in sorted(pity_limit.items())],
    }


def meta(metadata):
    return metadata.get("forge") or {
        "prototypes": [], "materials": {}, "items": {}, "levels": [], "talents": [],
        "score_tiers": [], "qualities": ["白", "绿", "蓝", "紫", "橙"],
        "slots": {"1": "攻击", "2": "防御", "3": "辅助", "4": "速度"},
        "elements": {}, "attributes": {}, "affix_pool": {}, "pity": [],
        "realms": {"0": "凡人"},
    }


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    return scan_forge(obj, meta_obj)


def post(rows, state, original, path):
    return rows


def enrich(module, meta_obj, state=None):
    module["catalog"] = meta_obj.get("prototypes") or []
    for key in ("levels", "talents", "score_tiers", "qualities", "slots", "elements",
                "attributes", "realms"):
        module[key] = meta_obj.get(key)
    return module


def summary(module):
    rows = module.get("rows") or {}
    return "炼器：Lv%s %s，器胚 %d 件，法宝 %d 件，最高器契 %s（%s）" % (
        rows.get("level", 0), rows.get("level_title") or "",
        rows.get("embryo_total", 0), len(rows.get("artifacts") or []),
        rows.get("best_score", 0), rows.get("best_tier_name") or "未定阶")
