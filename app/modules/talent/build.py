# -*- coding: utf-8 -*-
"""NPC天赋：配置表 → 模块快照（自 meta_update.py 原样搬入）。"""
from meta_update import (
    SCHEMA, _rows, _text, build_realms, build_spaces,
)


# 游戏分类图标资源使用 combat/artisan/travel/wealth/rapport/personality。
CATEGORY_NAMES = {
    "1": "战斗", "2": "技艺", "3": "游历",
    "4": "财富", "5": "交情", "6": "性格",
}


def build_talent(tables):
    realms = build_realms(tables)
    spaces = build_spaces(tables)
    # 同道容量与境界层数映射：npc_dao_ally_capacity 是每个境界能同道的人数上限，
    # phases 把存档里的 cultivate_layer_id 映射回境界 id（用于提示玩家当前境界）。
    realm_capacity, phases = {}, {}
    for row in _rows(tables["tbcultivaterealm"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        realm_id = str(row["id"])
        try:
            capacity = int(row.get("npc_dao_ally_capacity") or 0)
        except (TypeError, ValueError):
            capacity = 0
        if capacity:
            realm_capacity[realm_id] = capacity
        for phase in row.get("phases") or []:
            try:
                phases[str(int(phase))] = realm_id
            except (TypeError, ValueError):
                pass
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
                # fixed_talent_id 固定天赋；random_pool_group_id 随机池。两者用于
                # 在 NPC 尚未出现在当前存档时，仍能从配置推断其固定天赋。
                "fixed_talent_id": slot.get("fixed_talent_id", 0),
                "random_pool_group_id": slot.get("random_pool_group_id", 0),
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
    return {"schema": SCHEMA, "talents": talents, "npcs": npcs, "spaces": spaces,
            "realms": realms, "realm_capacity": realm_capacity, "phases": phases}


# 插件统一入口
build = build_talent
