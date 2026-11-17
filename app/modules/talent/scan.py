# -*- coding: utf-8 -*-
"""NPC 天赋扫描。

数据口径：
- 配置（meta.npcs）里有天赋槽位的 NPC 才进入列表；
- 出现在存档 obj["npcs"] 里的 NPC 是"当前世界"的人（present）；
- worldStatus == 2 表示已退隐/寿元已尽，存档仍保留记录但世界里已找不到（gone）；
- 既不在存档、也没有实时位置的 NPC 标为"不在当前世界"（present=False, gone=False）。
"""


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _realm_for_layer(phases, layer):
    """把存档里的 cultivate_layer_id 映射回境界 id（同 sect 模块的口径）。"""
    best, realm = -1, 0
    for raw, realm_id in (phases or {}).items():
        phase = _int(raw)
        if phase <= _int(layer) and phase > best:
            best, realm = phase, _int(realm_id)
    return realm


def scan_talent(obj, meta):
    talents = {str(r.get("id")): r for r in meta.get("talents", []) if isinstance(r, dict)}
    npc_meta = meta.get("npcs") or {}
    space_meta = meta.get("spaces") or {}
    spaces = obj.get("spaces") or {}
    player = obj.get("playerModel") or {}
    dao_ids = {str(x) for x in ((player.get("npc_dao_ally") or {}).get("npc_ids") or [])}
    # 同道提示：从存档推导玩家当前境界，容量在 enrich 阶段再按境界配置查表。
    player_realm = _realm_for_layer(meta.get("phases") or {},
                                    (player.get("combat") or {}).get("cultivate_layer_id"))
    dao = {"realm_id": str(player_realm), "count": len(dao_ids)}

    # 存档实例按 npcCfgId 建索引；同一配置可能有多份记录，优先留在世的。
    save_by_cfg = {}
    for uid, npc in (obj.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        cfg = str(npc.get("npcCfgId"))
        if cfg in ("None", "") or not cfg:
            continue
        previous = save_by_cfg.get(cfg)
        if previous is None or (_int(previous.get("worldStatus")) == 2
                                and _int(npc.get("worldStatus")) != 2):
            save_by_cfg[cfg] = npc

    rows = []
    for cfg, info in npc_meta.items():
        if not isinstance(info, dict):
            continue
        cfg_slots = [s for s in (info.get("slots") or []) if isinstance(s, dict)]
        if not cfg_slots:
            continue
        record = save_by_cfg.get(cfg)
        present = record is not None
        gone = present and _int(record.get("worldStatus")) == 2

        location, region, path, space_id = "未知地点", "", [], None
        if record is not None:
            space = spaces.get(record.get("currentSpaceUuid")) or {}
            space_id = space.get("spaceId")
            space_info = space_meta.get(str(space_id)) or {}
            location = space_info.get("name") or "未知地点"
            path = space_info.get("path") or [location]
            region = space_info.get("region") or location

        slot_info = {str(s.get("slot_id")): s for s in cfg_slots}
        slots = []
        if record is not None:
            for saved in (record.get("talent") or {}).get("slots") or []:
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
            if not slots:
                continue
        else:
            # 不在当前世界：只能展示配置里的固定天赋；随机池槽位无法预知，留空占位。
            for slot in cfg_slots:
                fid = _int(slot.get("fixed_talent_id"))
                talent = talents.get(str(fid)) if fid else {}
                if not talent and not _int(slot.get("random_pool_group_id")):
                    continue
                slots.append({
                    "slot_id": slot.get("slot_id"),
                    "talent_id": fid if talent else None,
                    "unlocked": False,
                    "required_realm": slot.get("required_npc_realm_id", 0),
                    "conditions": slot.get("unlock_conditions") or [],
                    "known": bool(talent),
                })
        if not slots:
            continue
        rows.append({
            "uid": str(cfg), "cfg": cfg,
            "who": info.get("name") or ("#%s" % cfg),
            "title": info.get("title") or "", "location": location,
            "region": region,
            "location_path": " / ".join(path) if path else "",
            "space_id": space_id, "dao": str(cfg) in dao_ids,
            "slots": slots, "present": present, "gone": gone,
        })
    # 在世优先，其次按名字排序（位置已降级为次要信息，不再作为主分组键）。
    rows.sort(key=lambda r: (0 if (r["present"] and not r["gone"]) else (1 if r["gone"] else 2),
                             str(r["who"]), str(r["uid"])))
    return {"rows": rows, "dao": dao}


def meta(metadata):
    empty = {"items": {}, "npcs": {}, "spaces": {}, "realms": {"0": "凡人"},
             "realm_capacity": {}, "phases": {}}
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
    module["realm_capacity"] = meta_obj.get("realm_capacity") or {}
    payload = module.get("rows")
    dao = {}
    if isinstance(payload, dict):
        rows = payload.get("rows") or []
        dao = payload.get("dao") or {}
        module["rows"] = rows
    else:
        rows = payload or []
    realm_id = str(dao.get("realm_id") or "0")
    module["dao"] = {
        "realm_id": realm_id,
        "realm_name": module["realms"].get(realm_id, ""),
        "count": dao.get("count", 0),
        "capacity": module["realm_capacity"].get(realm_id, 0),
    }
    present = sum(1 for r in rows if r.get("present") and not r.get("gone"))
    gone = sum(1 for r in rows if r.get("gone"))
    absent = sum(1 for r in rows if not r.get("present"))
    module["stats"] = {"total": len(rows), "present": present, "gone": gone, "absent": absent}
    return module


def summary(module):
    rows = module.get("rows") or []
    stats = module.get("stats") or {}
    return "NPC天赋：%d 位 NPC（在世 %d / 已离世 %d / 不在当前世界 %d），%d 个槽位，已解锁 %d 个" % (
        len(rows), stats.get("present", 0), stats.get("gone", 0), stats.get("absent", 0),
        sum(len(r["slots"]) for r in rows),
        sum(1 for r in rows for s in r["slots"] if s["unlocked"]))
