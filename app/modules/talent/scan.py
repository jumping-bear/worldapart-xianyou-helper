# -*- coding: utf-8 -*-
"""NPC 天赋扫描。"""


def scan_talent(obj, meta):
    talents = {str(r.get("id")): r for r in meta.get("talents", []) if isinstance(r, dict)}
    npc_meta = meta.get("npcs") or {}
    space_meta = meta.get("spaces") or {}
    spaces = obj.get("spaces") or {}
    player = obj.get("playerModel") or {}
    dao_ids = {str(x) for x in ((player.get("npc_dao_ally") or {}).get("npc_ids") or [])}
    rows = []
    for uid, npc in (obj.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        saved_slots = (npc.get("talent") or {}).get("slots") or []
        if not saved_slots:
            continue
        cfg = npc.get("npcCfgId")
        info = npc_meta.get(str(cfg)) or {}
        slot_info = {str(s.get("slot_id")): s for s in info.get("slots", []) if isinstance(s, dict)}
        slots = []
        for saved in saved_slots:
            if not isinstance(saved, dict):
                continue
            talent_id = saved.get("talent_id")
            extra = slot_info.get(str(saved.get("slot_id"))) or {}
            talent = talents.get(str(talent_id)) or {}
            slots.append({
                "slot_id": saved.get("slot_id"), "talent_id": talent_id,
                "unlocked": bool(saved.get("unlocked")),
                "required_realm": extra.get("required_npc_realm_id", 0),
                "conditions": extra.get("unlock_conditions") or [],
                "known": bool(talent),
            })
        space = spaces.get(npc.get("currentSpaceUuid")) or {}
        space_id = space.get("spaceId")
        space_info = space_meta.get(str(space_id)) or {}
        location = space_info.get("name") or "未知地点"
        path = space_info.get("path") or [location]
        rows.append({
            "uid": str(uid), "cfg": cfg, "who": info.get("name") or ("#%s" % cfg),
            "title": info.get("title") or "", "location": location,
            "region": space_info.get("region") or location,
            "location_path": " / ".join(path), "space_id": space_id,
            "dao": str(cfg) in dao_ids, "slots": slots,
        })
    rows.sort(key=lambda r: (str(r["who"]), str(r["uid"])))
    return rows


def meta(metadata):
    empty = {"items": {}, "npcs": {}, "spaces": {}, "realms": {"0": "凡人"}}
    return metadata.get("talent") or dict(empty, talents=[])


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    return scan_talent(obj, meta_obj)


def post(rows, state, original, path):
    return rows


def enrich(module, meta_obj, state=None):
    module["talents"] = meta_obj.get("talents") or []
    module["realms"] = meta_obj.get("realms") or {"0": "凡人"}
    return module


def summary(module):
    rows = module.get("rows") or []
    return "NPC天赋：%d 位 NPC，%d 个槽位，已解锁 %d 个" % (
        len(rows), sum(len(r["slots"]) for r in rows),
        sum(1 for r in rows for s in r["slots"] if s["unlocked"]))
