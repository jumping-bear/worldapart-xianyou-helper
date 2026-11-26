# -*- coding: utf-8 -*-
"""探索属性扫描：本月可做的 NPC 入口、切磋剩余次数与委托目标。"""
from meta_update import _int


def _attr_exp(raw):
    result = {}
    if not isinstance(raw, dict):
        return result
    for key, value in raw.items():
        attr_id = _int(key)
        if attr_id:
            result[attr_id] = _int(value)
    return result


def _base_attr(raw, attr_id):
    if not isinstance(raw, dict):
        return 0
    value = raw.get(attr_id, raw.get(str(attr_id)))
    return int(value) if isinstance(value, (int, float)) else 0


def _level(levels, exp):
    thresholds = [int(item) for item in levels or [] if _int(item) > 0]
    level = 1 + sum(1 for threshold in thresholds if exp > threshold)
    need = thresholds[level - 1] if level - 1 < len(thresholds) else 0
    return level, need


def _entry_exp(entry, attr_id):
    for item in entry.get("exp") or []:
        if isinstance(item, list) and len(item) == 3 and _int(item[0]) == attr_id:
            return _int(item[1]), _int(item[2])
    return 0, 0


def _space_path(spaces_raw, space_meta, uuid):
    record = spaces_raw.get(str(uuid)) if isinstance(spaces_raw, dict) else None
    if not isinstance(record, dict):
        return ["未知地点"]
    path = space_meta.get(str(_int(record.get("spaceId"))))
    if isinstance(path, list) and path:
        return [str(item) for item in path]
    return ["未知地点"]


def _task_state(force_records):
    """返回 (本期任务 id, 已接任务 id)。"""
    offered, accepted = set(), set()
    if not isinstance(force_records, dict):
        return offered, accepted
    for record in force_records.values():
        if not isinstance(record, dict):
            continue
        offered.update(_int(value) for value in record.get("task_ids") or [] if _int(value))
        accepted.update(_int(value) for value in record.get("accepted_task_ids") or []
                        if _int(value))
    # 已接任务即使暂时不在本期列表里，也要保留委托徽标。
    offered |= accepted
    return offered, accepted


def scan(obj, meta_obj, state=None):
    obj = obj or {}
    meta_obj = meta_obj or {}
    player = obj.get("playerModel") or {}
    attrs_raw = _attr_exp(player.get("interact_attributes"))
    combat = player.get("combat") or {}
    base_attrs = combat.get("base_attrs") or {}
    stamina_cur = _base_attr(base_attrs, 200)
    stamina_max = _base_attr(base_attrs, 201)

    entry_meta = meta_obj.get("entries") or {}
    npc_meta = meta_obj.get("npcs") or {}
    space_meta = meta_obj.get("spaces") or {}
    task_meta = meta_obj.get("tasks") or {}
    item_names = meta_obj.get("item_names") or {}
    const = meta_obj.get("const") or {}
    spar_type = _int(const.get("spar_type"))

    force_records = ((player.get("questComponent") or {}).get("commission_task_component")
                     or {}).get("force_records") or {}
    offered, accepted = _task_state(force_records)
    tasks_by_npc = {}
    for task_id in sorted(offered):
        info = task_meta.get(str(task_id))
        if not isinstance(info, dict):
            continue
        task = {
            "task": task_id,
            "quest": _int(info.get("quest")),
            "name": info.get("name") or "未识别委托",
            "action": info.get("action") or "",
            "attr": _int(info.get("attr")),
            "kind": info.get("kind") or "",
            "npc": _int(info.get("npc")),
            "board_place": info.get("board_place") or "未知地点",
            "board_npc": info.get("board_npc") or "未识别 NPC",
            "board_enabled": bool(info.get("board_enabled", True)),
            "target_place": info.get("target_place") or "",
            "accepted": task_id in accepted,
        }
        tasks_by_npc.setdefault(task["npc"], []).append(task)

    entries = []
    retired = 0
    warnings = []
    for record in (obj.get("npcs") or {}).values():
        if not isinstance(record, dict):
            continue
        npc_id = _int(record.get("npcCfgId"))
        runtime = record.get("npc_interaction_runtime") or {}
        sub_id = _int(runtime.get("special_sub_id"))
        if _int(record.get("worldStatus")) == 2:
            if sub_id:
                retired += 1
            continue
        if not npc_id or not sub_id:
            continue
        info = entry_meta.get("%d:%d" % (npc_id, sub_id))
        if not isinstance(info, dict):
            continue
        attr_id = _int(info.get("attr"))
        if not attr_id:
            continue
        exp_min, exp_max = _entry_exp(info, attr_id)
        stamina = _int(info.get("stamina"))
        bonus = []
        for item in info.get("drops") or []:
            if not isinstance(item, list) or len(item) != 3:
                continue
            item_id, low, high = _int(item[0]), _int(item[1]), _int(item[2])
            name = item_names.get(str(item_id)) or "未识别物品"
            bonus.append("%s %s" % (name, low) if low == high else "%s %s–%s" % (name, low, high))
        profile = npc_meta.get(str(npc_id)) or {}
        path = _space_path(obj.get("spaces") or {}, space_meta, record.get("currentSpaceUuid"))
        commission = []
        for task in tasks_by_npc.get(npc_id, []):
            commission.append({
                "task": task["task"], "name": task["name"],
                "action": task["action"], "kind": task["kind"],
                "accepted": task["accepted"],
                "matched": task["attr"] == attr_id,
                "board_place": task["board_place"],
                "board_npc": task["board_npc"],
            })
        commission.sort(key=lambda item: (not item["matched"], not item["accepted"],
                                           item["name"]))
        enough = stamina <= 0 or stamina <= stamina_cur
        entry_type = _int(info.get("type"))
        status = "精力不足" if not enough else "可做"
        entries.append({
            "npc": npc_id,
            "name": profile.get("name") or "未识别 NPC",
            "title": profile.get("title") or "",
            "layer": profile.get("layer") or "",
            "sub": sub_id,
            "type": entry_type,
            "button": info.get("name") or "互动",
            "tag": info.get("tag") or "",
            "desc": info.get("desc") or "",
            "attr": attr_id,
            "exp_min": exp_min,
            "exp_max": exp_max,
            "bonus": " · ".join(bonus),
            "stamina": stamina,
            "path": path,
            "path_text": " / ".join(path),
            "region": path[0] if path else "",
            "commission": commission,
            "has_task": bool(commission),
            "matched_task": any(item["matched"] for item in commission),
            "enough": enough,
            "status": status,
        })
        if not path or path == ["未知地点"]:
            warnings.append("%s 的所在场景未在配置中匹配" % entries[-1]["name"])

    entries.sort(key=lambda item: (-item["exp_max"], -item["exp_min"],
                                   item["path_text"], item["name"]))

    by_attr = {}
    attribute_meta = meta_obj.get("attributes") or []
    for row in attribute_meta:
        attr_id = _int(row.get("id"))
        if attr_id:
            by_attr[str(attr_id)] = sum(1 for item in entries if item["attr"] == attr_id)

    # 委托任务是否可以与本月入口顺路完成。
    by_npc_attr = {(item["npc"], item["attr"]) for item in entries}
    commissions = []
    for tasks in tasks_by_npc.values():
        for task in tasks:
            item = dict(task)
            item["matched"] = (task["npc"], task["attr"]) in by_npc_attr
            profile = npc_meta.get(str(task["npc"])) or {}
            item["npc_name"] = profile.get("name") or "未识别 NPC"
            commissions.append(item)
    commissions.sort(key=lambda item: (not item["matched"], not item["accepted"],
                                       item["kind"], item["name"]))

    attributes = []
    for row in attribute_meta:
        attr_id = _int(row.get("id"))
        if not attr_id:
            continue
        exp = attrs_raw.get(attr_id, 0)
        level, need = _level(row.get("levels"), exp)
        attributes.append({
            "id": attr_id,
            "name": row.get("name") or str(attr_id),
            "desc": row.get("desc") or "",
            "exp": exp,
            "level": level,
            "need": need,
            "count": by_attr.get(str(attr_id), 0),
        })
    if not attributes:
        # 配置快照缺失时，至少把存档里已有的属性 id 用数字名展示出来。
        for attr_id in sorted(attrs_raw):
            attributes.append({
                "id": attr_id, "name": str(attr_id), "desc": "",
                "exp": attrs_raw.get(attr_id, 0), "level": 1, "need": 0,
                "count": by_attr.get(str(attr_id), 0),
            })

    if not attrs_raw:
        warnings.insert(0, "存档里没有探索属性经验数据")
    if not entries:
        warnings.insert(0, "存档里没有本月特殊互动入口（可能是新档或本月尚未抽取）")

    game_time = obj.get("currentGameTime") or {}
    return {
        "attrs": attributes,
        "entries": entries,
        "commissions": commissions,
        "ranges": meta_obj.get("exp_ranges") or [],
        "ratios": sorted({_int(row.get("ratio"))
                          for row in (meta_obj.get("groups") or {}).values()
                          if _int(row.get("ratio"))}),
        "costs": sorted({item["stamina"] for item in entries if item["stamina"] > 0}),
        "spar": {"type": spar_type},
        "stamina": {"cur": stamina_cur, "max": stamina_max},
        "date": {"year": _int(game_time.get("year")),
                 "month": _int(game_time.get("month")),
                 "day": _int(game_time.get("day"))},
        "totals": {
            "entries": len(entries),
            "retired": retired,
            "spar": sum(1 for item in entries if spar_type and item["type"] == spar_type),
            "tasks": len(commissions),
            "accepted": sum(1 for item in commissions if item["accepted"]),
            "matched_tasks": sum(1 for item in commissions if item["matched"]),
            "by_attr": by_attr,
        },
        "warnings": warnings,
    }


def summary(module):
    rows = module.get("rows") or {}
    totals = rows.get("totals") or {}
    return "探索：本月 %d 个入口，切磋 %d 个，委托目标 %d 条" % (
        _int(totals.get("entries")), _int(totals.get("spar")),
        _int(totals.get("tasks")))
