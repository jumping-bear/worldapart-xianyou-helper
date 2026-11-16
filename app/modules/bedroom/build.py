# -*- coding: utf-8 -*-
"""仙居楼互动：配置表 → 模块快照（自 meta_update.py 原样搬入）。"""
from meta_update import (
    _rows, _text,
)


SLOT_LABELS = {
    "Face": "脸", "Waist": "腰", "Foot": "足", "Leg": "腿", "Armpit": "腋下",
    "Fan": "团扇", "Feather": "灵羽", "Gourd": "灵泉葫芦", "Grass": "草叶",
    "Stick": "短杖", "Bamboo": "竹枝", "Hug": "相拥",
}


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


# 插件统一入口
build = build_bedroom
