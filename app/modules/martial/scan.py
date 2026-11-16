# -*- coding: utf-8 -*-
"""心法与功法扫描：把存档状态翻译成「已运转 / 已学会 / 卷册在包 / 尚未获得」，
并生成可定位的体检结论。所有规则只读快照与存档，不修改任何输入。
"""

STATE_ORDER = {"已运转": 0, "卷册在包": 1, "已学会未运转": 2, "尚未获得": 3, "特殊": 4}
LEVEL_ORDER = {"high": 0, "mid": 1, "low": 2, "info": 3, "warn": 4}
LEVEL_NAME = {"high": "高", "mid": "中", "low": "低", "info": "提示", "warn": "告警"}


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _player(obj):
    model = obj.get("playerModel")
    return model if isinstance(model, dict) else obj


def _bag_nodes(bag):
    entries = bag.get("items") if isinstance(bag, dict) else bag

    def walk(node, out):
        if isinstance(node, dict):
            if node.get("item_id") is not None:
                out.append(node)
                return
            for child in node.values():
                walk(child, out)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child, out)

    nodes = []
    walk(entries, nodes)
    return nodes


def _sort_key(mapping, key, fallback):
    value = mapping.get(key)
    return _int((value or {}).get(fallback), _int(key))


def _by_int(mapping):
    """msgpack 解出的字典键可能是 int，统一成 int 便于查找。"""
    if not isinstance(mapping, dict):
        return {}
    return {_int(key): value for key, value in mapping.items()}


def _core_source(core):
    if core.get("shops"):
        return "货架"
    if core.get("teach"):
        return "可请教"
    if core.get("book"):
        return "卷册"
    if core.get("slots") and not core.get("sect"):
        return "特殊"
    return "未开放"


def _art_source(art, init_of):
    if art.get("book") and art.get("shops"):
        return "货架"
    if (art.get("teach") or {}).get("visible"):
        return "可请教"
    if art.get("book"):
        return "卷册"
    if init_of:
        return "入门自带"
    return "未开放"


def _tier_name(meta, tier):
    phases = meta.get("phases") or {}
    tier_phase = meta.get("tier_phase") or {}
    start = tier_phase.get(str(tier))
    if start and str(start) in phases:
        return phases[str(start)]
    return phases.get(str(tier)) or ""


def scan_martial(obj, meta, state=None):
    model = _player(obj)
    combat = model.get("combat") if isinstance(model.get("combat"), dict) else {}
    soul = (model.get("talent_path") or {}) if isinstance(model.get("talent_path"), dict) else {}

    sects = {str(item.get("id")): item for item in meta.get("sects") or []}
    elements = meta.get("elements") or {}
    realms = meta.get("realms") or {}
    phases = meta.get("phases") or {}
    layers = meta.get("layers") or {}

    cores = {_int(item.get("id")): item for item in meta.get("core_passives") or []}
    arts = {_int(item.get("id")): item for item in meta.get("arts") or []}
    resonance_meta = {_int(item.get("id")): item for item in meta.get("resonance") or []}

    init_of = {}
    for core in meta.get("core_passives") or []:
        for skill_id in core.get("init") or []:
            init_of.setdefault(_int(skill_id), []).append(_int(core.get("id")))

    learned_core = {_int(x) for x in combat.get("learned_core_passives") or []}
    learned_skills = {_int(x) for x in (combat.get("learned_skills") or {})}
    learned_support = {_int(x) for x in (combat.get("learned_support_skills") or {})}

    core_slots = _by_int(combat.get("core_passive_slots"))
    configs = _by_int(combat.get("core_passive_skill_configs"))

    slot_rows = []
    installed_ids = set()
    for key, slot in sorted(core_slots.items(), key=lambda item: _sort_key(core_slots, item[0], "slot_index")):
        slot = slot if isinstance(slot, dict) else {}
        core_id = _int(slot.get("core_passive_id"))
        if core_id:
            installed_ids.add(core_id)
        cells = []
        config = configs.get(core_id) if core_id else None
        if isinstance(config, dict):
            for cell_key, cell in sorted(config.items(),
                                         key=lambda item: _sort_key(config, item[0], "slot_index")):
                cell = cell if isinstance(cell, dict) else {}
                skill_id = _int(cell.get("skill_id"))
                art = arts.get(skill_id) or {}
                cells.append({
                    "index": _int(cell.get("slot_index"), _int(cell_key)),
                    "skill_id": skill_id,
                    "name": art.get("name") or "",
                    "element": _int(art.get("element")),
                    "element_name": elements.get(str(_int(art.get("element"))), "待识别"),
                    "tier": _int(art.get("tier")),
                    "tier_name": _tier_name(meta, _int(art.get("tier"))),
                    "empty": not skill_id,
                })
        slot_rows.append({
            "slot": _int(slot.get("slot_index"), _int(key)),
            "core_id": core_id,
            "name": (cores.get(core_id) or {}).get("name") or ("心法 %s" % core_id if core_id else ""),
            "element": _int((cores.get(core_id) or {}).get("element")),
            "element_name": elements.get(str(_int((cores.get(core_id) or {}).get("element"))), "待识别"),
            "tier": _int((cores.get(core_id) or {}).get("tier")),
            "tier_name": _tier_name(meta, _int((cores.get(core_id) or {}).get("tier"))),
            "empty": not core_id,
            "cells": cells,
        })

    running_arts = set()
    for core_id in installed_ids:
        config = configs.get(core_id)
        if not isinstance(config, dict):
            continue
        for cell in config.values():
            skill_id = _int((cell or {}).get("skill_id"))
            if skill_id:
                running_arts.add(skill_id)

    bag = model.get("bag") if isinstance(model.get("bag"), dict) else {}
    scrolls = []
    for node in _bag_nodes(bag):
        target_type = _int(node.get("learn_target_type"))
        target_id = _int(node.get("learn_target_id"))
        if not target_type and not target_id:
            continue
        target = arts.get(target_id) if target_type == 1 else cores.get(target_id) if target_type == 2 else None
        learned = (target_id in learned_skills) if target_type == 1 else (target_id in learned_core)
        comprehend = (target or {}).get("comprehend") or {}
        scrolls.append({
            "uid": _int(node.get("uid")),
            "item_id": _int(node.get("item_id")),
            "type": target_type,
            "kind": {1: "功法", 2: "心法"}.get(target_type, "未知卷册（待识别）"),
            "target": target_id,
            "name": (target or {}).get("name") or ("卷册 #%s" % target_id),
            "known": bool(target),
            "count": _int(node.get("count"), 1),
            "comprehend": _int(node.get("comprehend_value")),
            "limit": _int(comprehend.get("limit")),
            "learned": learned,
        })
    scroll_by_target = {}
    for row in scrolls:
        if not row["learned"]:
            scroll_by_target.setdefault((row["type"], row["target"]), row)

    core_rows = []
    for core_id, core in cores.items():
        state = "已运转" if core_id in installed_ids else "已学会未运转" if core_id in learned_core else "尚未获得"
        if state == "尚未获得" and _core_source(core) == "特殊":
            state = "特殊"
        in_bag = scroll_by_target.get((2, core_id))
        core_rows.append({**core, **{
            "element_name": elements.get(str(core.get("element")), "待识别"),
            "tier_name": _tier_name(meta, _int(core.get("tier"))),
            "sect_name": (sects.get(str(core.get("sect"))) or {}).get("name") or ("通用" if not core.get("sect") else "待识别"),
            "state": state,
            "source": _core_source(core),
            "in_bag": bool(in_bag),
            "bag": in_bag,
            "init_arts": [dict(arts.get(skill_id) or {"id": skill_id, "name": "功法 %s" % skill_id, "book": 0})
                          for skill_id in core.get("init") or []],
            "same_name": [],
        }})
    core_by_id = {row["id"]: row for row in core_rows}
    name_groups = {}
    for row in core_rows:
        name_groups.setdefault(row.get("name"), []).append(row)
    for rows in name_groups.values():
        if len(rows) > 1:
            for row in rows:
                row["same_name"] = [{"id": other["id"], "tier": other["tier"],
                                     "tier_name": other["tier_name"], "desc": other.get("desc")}
                                    for other in rows if other["id"] != row["id"]]
    core_rows.sort(key=lambda row: (STATE_ORDER.get(row["state"], 9), _int(row.get("sect")),
                                    _int(row.get("tier")), _int(row.get("id"))))

    art_rows = []
    for art_id, art in arts.items():
        if art_id in running_arts:
            state = "已运转"
        elif art_id in learned_skills:
            state = "已学会未运转"
        elif (1, art_id) in scroll_by_target:
            state = "卷册在包"
        else:
            state = "尚未获得"
        owners = init_of.get(art_id) or []
        in_bag = scroll_by_target.get((1, art_id))
        art_rows.append({**art, **{
            "element_name": elements.get(str(art.get("element")), "待识别"),
            "tier_name": _tier_name(meta, _int(art.get("tier"))),
            "sect_name": (sects.get(str(art.get("sect"))) or {}).get("name") or "待识别",
            "state": state,
            "source": _art_source(art, owners),
            "init_of": [{"id": cid, "name": (cores.get(cid) or {}).get("name") or ("心法 %s" % cid)}
                        for cid in owners],
            "in_bag": bool(in_bag),
            "bag": in_bag,
        }})
    art_rows.sort(key=lambda row: (STATE_ORDER.get(row["state"], 9), _int(row.get("sect")),
                                   _int(row.get("tier")), _int(row.get("id"))))
    art_by_id = {row["id"]: row for row in art_rows}

    support_slots = _by_int(combat.get("support_skill_slots"))
    support_capacity = len(support_slots)
    installed_support = set()
    support_rows = []
    for key, slot in sorted(support_slots.items(), key=lambda item: _sort_key(support_slots, item[0], "slot_index")):
        slot = slot if isinstance(slot, dict) else {}
        skill_id = _int(slot.get("skill_id"))
        if skill_id:
            installed_support.add(skill_id)
        item = resonance_meta.get(skill_id) or {}
        support_rows.append({
            "slot": _int(slot.get("slot_index"), _int(key)),
            "skill_id": skill_id,
            "name": item.get("name") or "",
            "element": _int(item.get("element")),
            "element_name": elements.get(str(_int(item.get("element"))), "待识别"),
            "empty": not skill_id,
        })

    resonance_realms = _by_int(combat.get("resonance_skill_realms"))
    realm_recorded = bool(resonance_realms)
    resonance_rows = []
    for skill_id, item in resonance_meta.items():
        realm = _int(resonance_realms.get(skill_id)) if realm_recorded else None
        state = "已运转" if skill_id in installed_support else "已学会未运转" if skill_id in learned_support else "尚未获得"
        resonance_rows.append({**item, **{
            "element_name": elements.get(str(item.get("element")), "待识别"),
            "unlock_realm": phases.get(str(item.get("unlock_layer"))) or _tier_name(meta, _int(item.get("tier"))),
            "state": state,
            "learned": skill_id in learned_support,
            "installed": skill_id in installed_support,
            "realm": realm,
            "realm_recorded": realm_recorded,
        }})
    resonance_rows.sort(key=lambda row: (STATE_ORDER.get(row["state"], 9), _int(row.get("tier")), _int(row.get("id"))))

    character = {
        "name": model.get("playerName") or "",
        "sect_id": _int(model.get("current_sect_id")),
        "sect_name": (sects.get(str(_int(model.get("current_sect_id")))) or {}).get("name") or "未入宗门",
        "layer": _int(combat.get("cultivate_layer_id")),
    }
    layer_info = layers.get(str(character["layer"])) or {}
    character["realm"] = phases.get(str(layer_info.get("phase"))) or "待识别"
    character["layer_index"] = _int(layer_info.get("layer"))
    character["spirit"] = [
        {"element": _int(key), "name": elements.get(str(_int(key)), "待识别"), "point": _int(value)}
        for key, value in sorted((soul.get("spirit_root_point_map") or {}).items(),
                                 key=lambda item: _int(item[0]))
    ]

    diagnosis = []

    def add(rule, level, text, target):
        diagnosis.append({"id": rule, "level": level, "level_name": LEVEL_NAME.get(level, level),
                          "text": text, "target": target})

    capacity = len(core_slots)
    if capacity and len(installed_ids) < capacity:
        add("R01", "high", "还有 %d 个心法槽空着" % (capacity - len(installed_ids)),
            {"kind": "core_slots", "id": 0})

    idle_cores = [row for row in core_rows if row["state"] == "已学会未运转"]
    if idle_cores:
        names = "、".join("「%s」" % row["name"] for row in idle_cores[:2])
        more = "等 %d 本" % len(idle_cores) if len(idle_cores) > 2 else ""
        add("R02", "mid", "%s%s已学但没装槽" % (names, more),
            {"kind": "core", "id": idle_cores[0]["id"]})

    for row in slot_rows:
        core_id = row["core_id"]
        if not core_id or core_id not in cores:
            continue
        empty = [_int(cell.get("index")) + 1 for cell in row["cells"] if cell.get("empty")]
        if empty:
            add("R03", "mid", "「%s」第 %s 格功法空着" % (row["name"], "、".join(str(x) for x in empty)),
                {"kind": "core", "id": core_id})

    idle_arts = [row for row in art_rows if row["state"] == "已学会未运转"]
    if idle_arts:
        names = "、".join("「%s」" % row["name"] for row in idle_arts[:2])
        more = "等 %d 本" % len(idle_arts) if len(idle_arts) > 2 else ""
        add("R04", "mid", "%s%s功法已学但没运转" % (names, more),
            {"kind": "art", "id": idle_arts[0]["id"]})

    for row in slot_rows:
        core = cores.get(row["core_id"]) or {}
        if not row["core_id"]:
            continue
        core_element = _int(core.get("element"))
        core_tier = _int(core.get("tier"))
        for cell in row["cells"]:
            art = arts.get(cell["skill_id"]) or {}
            if not art:
                continue
            if core_element and _int(art.get("element")) != core_element:
                add("R05", "high", "「%s」是%s系，装在%s系心法「%s」上" % (
                    art.get("name"), elements.get(str(_int(art.get("element"))), "待识别"),
                    elements.get(str(core_element)), core.get("name")),
                    {"kind": "art", "id": cell["skill_id"]})
            if core_tier and _int(art.get("tier")) != core_tier:
                add("R06", "high", "「%s」是%s功法，心法「%s」是%s" % (
                    art.get("name"), _tier_name(meta, _int(art.get("tier"))),
                    core.get("name"), _tier_name(meta, core_tier)),
                    {"kind": "art", "id": cell["skill_id"]})

    element_count = {}
    for row in slot_rows:
        if row["core_id"] and row["element"]:
            element_count[row["element"]] = element_count.get(row["element"], 0) + 1
    crowded = [count for count in element_count.values() if count > 1]
    if crowded:
        add("R07", "low", "同系心法装了 %d 本，游戏内可能提示对换（待复核）" % sum(crowded),
            {"kind": "core_slots", "id": 0})

    for core_id in sorted(installed_ids):
        core = cores.get(core_id) or {}
        for row in core_rows:
            if row["name"] != core.get("name") or _int(row.get("tier")) <= _int(core.get("tier")):
                continue
            if row["id"] in learned_core:
                add("R08", "mid", "有%s版「%s」可换（已学）" % (row["tier_name"], row["name"]),
                    {"kind": "core", "id": core_id})
                break

    if scrolls:
        pending = [row for row in scrolls if not row["learned"]]
        if pending:
            first = pending[0]
            progress = "%s/%s" % (first["comprehend"], first["limit"] or "?")
            add("R09", "low", "有 %d 本卷册没参悟（%s %s）" % (len(pending), first["name"], progress),
                {"kind": "bag", "id": first["uid"]})

    learned_not_installed = [row for row in resonance_rows
                             if row["learned"] and not row["installed"]]
    if support_capacity and (len(installed_support) < support_capacity or learned_not_installed):
        text = "共鸣技能 %d/%d" % (len(installed_support), support_capacity)
        if learned_not_installed:
            text += "，已学「%s」未装" % learned_not_installed[0]["name"]
            if len(installed_support) >= support_capacity:
                text += "（共鸣槽已满）"
        add("R10", "mid", text, {"kind": "resonance_slots", "id": 0})

    no_source = [row for row in art_rows if row["source"] == "未开放"]
    unopened = [row for row in resonance_rows if row["source"] == "unopened"]
    if no_source or unopened:
        parts = []
        target = None
        if no_source:
            names = "、".join("「%s」" % row["name"] for row in no_source[:2])
            more = "等 %d 本" % len(no_source) if len(no_source) > 2 else ""
            parts.append("%s%s功法来源未开放" % (names, more))
            target = {"kind": "art", "id": no_source[0]["id"]}
        if unopened:
            parts.append("%d 个共鸣技能来源未开放" % len(unopened))
            target = target or {"kind": "resonance", "id": unopened[0]["id"]}
        add("R11", "info", "；".join(parts), target)

    warnings = [item for item in (meta.get("warnings") or [])
                if not str(item).startswith("说明：")]
    if warnings:
        add("R12", "warn", "有 %d 条配置未识别或缺失，已保留条目：%s" % (
            len(warnings), warnings[0]), {"kind": "warning", "id": 0})

    diagnosis.sort(key=lambda item: (LEVEL_ORDER.get(item["level"], 9), item["id"]))
    art_running = sum(1 for row in art_rows if row["state"] == "已运转")
    art_learned = sum(1 for row in art_rows if row["state"] in ("已运转", "已学会未运转"))
    core_learned = sum(1 for row in core_rows if row["state"] in ("已运转", "已学会未运转"))
    stats = {
        "core_used": len(installed_ids), "core_total": capacity,
        "core_learned": core_learned,
        "art_used": art_running, "art_total": art_learned,
        "resonance_used": len(installed_support), "resonance_total": support_capacity,
        "issues": len(diagnosis),
    }
    return {
        "character": character,
        "equip": {"sect": sects.get(str(character["sect_id"])) or {}, "realm": character["realm"],
                  "layer": character["layer"], "layer_index": character["layer_index"],
                  "spirit": character["spirit"], "slots": slot_rows,
                  "support_slots": support_rows, "support_recorded": bool(support_capacity)},
        "core_passives": core_rows,
        "arts": art_rows,
        "resonance": resonance_rows,
        "bags": sorted(scrolls, key=lambda row: (row["learned"], row["kind"], row["target"])),
        "diagnosis": diagnosis,
        "stats": stats,
    }


def meta(metadata):
    empty = {"core_passives": [], "arts": [], "resonance": [], "sects": [], "intimacy": [],
             "elements": {"0": "无"}, "realms": {}, "phases": {}, "tier_phase": {},
             "layers": {}, "names": {"npc": {}, "item": {}},
             "stats": {"core": 0, "arts": 0, "resonance": 0, "books": 0, "excluded": []},
             "warnings": []}
    data = metadata.get("martial")
    return data if isinstance(data, dict) else empty


def enrich(module, meta_obj, state=None):
    target = module.get("rows") if isinstance(module.get("rows"), dict) else module
    target["sects"] = meta_obj.get("sects") or []
    target["intimacy"] = meta_obj.get("intimacy") or []
    target["elements"] = meta_obj.get("elements") or {"0": "无"}
    target["realms"] = meta_obj.get("realms") or {}
    target["phases"] = meta_obj.get("phases") or {}
    target["tier_phase"] = meta_obj.get("tier_phase") or {}
    target["layers"] = meta_obj.get("layers") or {}
    target["names"] = meta_obj.get("names") or {"npc": {}, "item": {}}
    target["catalog_stats"] = meta_obj.get("stats") or {}
    target["warnings"] = list(meta_obj.get("warnings") or [])
    return module


def summary(module):
    rows = module.get("rows") if isinstance(module.get("rows"), dict) else module
    stats = rows.get("stats") or {}
    issues = rows.get("diagnosis") or []
    if not rows.get("core_passives"):
        return "心法与功法：暂无可用配置"
    return "心法与功法：心法 %d/%d，功法 %d/%d，共鸣 %d/%d，体检 %d 条" % (
        stats.get("core_used", 0), stats.get("core_total", 0),
        stats.get("art_used", 0), stats.get("art_total", 0),
        stats.get("resonance_used", 0), stats.get("resonance_total", 0), len(issues))


scan = scan_martial
