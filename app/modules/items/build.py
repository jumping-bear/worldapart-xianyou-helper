# -*- coding: utf-8 -*-
"""NPC物品：配置表 → 模块快照（自 meta_update.py 原样搬入）。"""
from meta_update import (
    SCHEMA, _int, _rows, _text, build_realms, build_spaces,
)


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


# 插件统一入口
build = build_items
