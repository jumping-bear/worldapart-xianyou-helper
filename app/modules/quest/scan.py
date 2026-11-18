# -*- coding: utf-8 -*-
"""支线扫描：任务状态、奖励、剧情线与前置链路。"""
import os


DONE_STATES = (2, 3)
DOING_STATES = (1, 6)

# 展示层只保留玩家看得懂的六类状态；底层判定词一律不往外露。
STATUS_DONE = "已完成"
STATUS_DOING = "进行中"
STATUS_READY = "可接取"
STATUS_COND = "条件不足"
STATUS_WAIT = "未触发（需满足条件）"
STATUS_UNPICKED = "未选分支"

STATUS_KEYS = {
    STATUS_DONE: "done",
    STATUS_DOING: "doing",
    STATUS_READY: "ready",
    STATUS_COND: "cond",
    STATUS_WAIT: "wait",
    STATUS_UNPICKED: "unpicked",
}


def _attr_level(exp, thresholds):
    """探索属性经验 → 等级，阈值来自 tbinteractattribute.levelConfigs.maxExp。"""
    levels = [value for value in thresholds or [] if isinstance(value, int) and value > 0]
    if not levels:
        return 0, False
    return sum(1 for value in levels if exp > value) + 1, True


def _cmp(op, cur, need):
    ops = {">=": cur >= need, "≥": cur >= need, "=": cur == need,
           "≠": cur != need, "!=": cur != need, ">": cur > need,
           "<": cur < need, "≤": cur <= need, "<=": cur <= need}
    return ops.get(op)


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _realm_name(ctx, realm_id):
    return (ctx.get("realms") or {}).get(str(_int(realm_id))) or ""


def _lookup_rep(mapping, keys):
    """城镇声望可能按城镇 id 或声望 id 落库，两种键都试。"""
    if not isinstance(mapping, dict):
        return 0
    for key in keys:
        if key in (None, "", 0):
            continue
        if str(key) in mapping:
            return _int(mapping[str(key)])
        if key in mapping:
            return _int(mapping[key])
    for raw_key, value in mapping.items():
        for key in keys:
            if key not in (None, "", 0) and _int(raw_key) == _int(key):
                return _int(value)
    return 0


def _eval_check(check, ctx):
    """按当前存档判定单个条件；返回 ok(True/False/None)、当前显示值与缺口描述。"""
    kind = check.get("kind") or ""
    need = _int(check.get("need"))
    text = check.get("text") or "条件"
    neg = bool(check.get("neg"))
    cur, raw_ok, is_level = None, None, False
    if kind == "favor":
        cur = ctx["favor"].get(_int(check.get("npc")), 0)
        raw_ok = cur >= need
    elif kind == "city_rep":
        cur = _lookup_rep(ctx["city_rep"], [check.get("city"), check.get("rep")])
        raw_ok = cur >= need
    elif kind == "sect_rep":
        cur = ctx["sect_rep"]
        raw_ok = cur >= need
    elif kind in ("phase", "realm"):
        cur = ctx["player_realm"]
        raw_ok = cur >= need
    elif kind == "layer":
        cur = ctx["layer"]
        raw_ok = cur >= need
    elif kind == "money":
        cur = ctx["money"]
        raw_ok = cur >= need
    elif kind in ("quest_done", "quest_hold", "quest_accepted", "quest_active"):
        quest_id = _int(check.get("quest"))
        code = ctx["quests"].get(quest_id)
        if kind == "quest_done":
            cur = 1 if code in DONE_STATES else 0
        elif kind == "quest_hold":
            cur = 1 if code in DOING_STATES else 0
        elif kind == "quest_accepted":
            cur = 1 if code is not None else 0
        else:
            cur = 1 if code in DOING_STATES else 0
        raw_ok = cur >= need
    elif kind == "quest_none":
        quest_id = _int(check.get("quest"))
        code = ctx["quests"].get(quest_id)
        cur = 1 if (code in DOING_STATES or code in DONE_STATES) else 0
        raw_ok = cur == 0
    elif kind == "attr":
        attr_id = _int(check.get("attr"))
        exp = ctx["attr_exp"].get(str(attr_id), ctx["attr_exp"].get(attr_id, 0))
        cur, is_level = _attr_level(exp, ctx["attr_levels"].get(str(attr_id)) or [])
        raw_ok = cur >= need
    elif kind == "npc_realm":
        cur = ctx["npc_realms"].get(_int(check.get("npc")))
        if cur is not None:
            raw_ok = _cmp(check.get("op") or "≥", cur, need)
    ok = None if raw_ok is None else (not raw_ok if neg else raw_ok)

    if cur is None:
        cur_text = "未知"
    elif kind in ("phase", "realm", "npc_realm"):
        cur_text = _realm_name(ctx, cur) or str(cur)
    elif kind == "attr" or is_level:
        cur_text = "Lv%d" % cur
    elif kind in ("quest_done", "quest_hold", "quest_accepted", "quest_active"):
        code = ctx["quests"].get(_int(check.get("quest")))
        cur_text = "已完成" if code in DONE_STATES else ("进行中" if code in DOING_STATES else "未开始")
    elif kind == "quest_none":
        cur_text = "已选过" if cur else "未涉及"
    else:
        cur_text = str(cur)

    gap = ""
    if ok is False:
        if neg:
            gap = "目前已经%s" % (check.get("pos_text") or text)
        elif is_level:
            gap = "%s（需 Lv%d，当前 Lv%d）" % (text, need, cur)
        elif kind in ("phase", "realm", "npc_realm"):
            gap = "%s，当前 %s" % (text, cur_text)
        elif kind in ("quest_done", "quest_hold", "quest_accepted", "quest_active",
                      "quest_none"):
            gap = text
        else:
            gap = "%s（需 %d，当前 %s）" % (text, need, cur_text)
    return {"kind": kind, "text": text, "need": need, "cur": cur,
            "cur_text": cur_text, "ok": ok, "gap": gap, "neg": neg,
            "pos_text": check.get("pos_text") or text,
            "neg_text": check.get("neg_text") or text}


def _eval_tree(tree, ctx):
    """递归判定条件树，保留 且/或/非 逻辑，输出可展示的缺口链。"""
    def walk(node):
        if not isinstance(node, dict):
            return {"ok": None, "gaps": [], "text": "", "checks": []}
        op = node.get("op")
        if op in ("and", "or"):
            children = [walk(child) for child in (node.get("children") or [])]
            values = [child["ok"] for child in children]
            if op == "and":
                ok = False if False in values else (None if None in values else True)
                gaps = [] if ok else [gap for child in children for gap in child["gaps"]]
            else:
                ok = True if True in values else (None if None in values else False)
                gaps = []
                if ok is False:
                    parts = [child["text"] for child in children]
                    gaps = ["任选其一：" + " 或 ".join(part for part in parts if part)]
            return {"ok": ok, "gaps": gaps, "text": node.get("text") or "",
                    "checks": [check for child in children for check in child["checks"]]}
        if op == "not":
            inner = walk((node.get("children") or [{}])[0])
            ok = None if inner["ok"] is None else (not inner["ok"])
            checks = []
            for check in inner["checks"]:
                item = dict(check)
                item["ok"] = None if check["ok"] is None else (not check["ok"])
                item["text"] = (check.get("pos_text") if check.get("neg")
                                else (check.get("neg_text") or check.get("text")))
                item["neg"] = not check.get("neg", False)
                item["gap"] = "" if item["ok"] is not False else ("目前已经%s" % check.get("text"))
                checks.append(item)
            gaps = [check["gap"] for check in checks if check["gap"]] if ok is False else []
            return {"ok": ok, "gaps": gaps, "text": node.get("text") or "", "checks": checks}
        ev = _eval_check(node.get("leaf") or {}, ctx)
        return {"ok": ev["ok"], "gaps": [ev["gap"]] if ev["gap"] else [],
                "text": ev["text"], "checks": [ev]}

    result = walk(tree)
    unique, seen = [], set()
    for check in result["checks"]:
        key = (check["kind"], check["text"], check["need"], check.get("cur"))
        if key not in seen:
            seen.add(key)
            unique.append(check)
    return {"ok": result["ok"], "checks": unique, "gaps": result["gaps"],
            "logic": _tree_logic(tree)}


def _tree_logic(tree):
    flags = {"and": False, "or": False, "not": False}

    def walk(node):
        if not isinstance(node, dict):
            return
        op = node.get("op")
        if op:
            flags[op] = True
            for child in node.get("children") or []:
                walk(child)

    walk(tree)
    if flags["or"] and not flags["and"]:
        return "满足其一"
    if flags["and"] and not flags["or"]:
        return "全部满足"
    if flags["and"] and flags["or"]:
        return "部分条件满足其一"
    return ""


def meta(metadata):
    return metadata.get("quest") or {
        "quests": [], "groups": [], "storylines": [], "realms": {"0": "凡人"},
        "states": {}, "types": {}, "phases": {}, "chains": [], "branches": [],
        "edges": [], "diagnostics": {}, "stats": {},
    }


def prepare(game_dir):
    return None


def _realm_for_layer(phases, layer):
    if layer is None:
        return 0
    best = 0
    for raw, realm_id in (phases or {}).items():
        phase = _int(raw)
        if phase <= _int(layer) and phase > best:
            best = phase
    return _int((phases or {}).get(str(best)))


def _fallback_storylines(rows):
    """旧快照没有 storylines 时，按 chain 兜底聚成线，保证页面不空白。"""
    clusters = {}
    for row in rows:
        key = row.get("chain_id") or ("q%d" % row["id"])
        clusters.setdefault(key, []).append(row)
    out = []
    for key, items in clusters.items():
        items.sort(key=lambda row: (row.get("chain_index") or 0, row["id"]))
        out.append({"id": key, "name": items[0].get("chain_name") or items[0]["name"],
                    "chapter": "支线", "group": items[0].get("group") or "",
                    "quests": [row["id"] for row in items],
                    "depths": {str(row["id"]): row.get("chain_index") or 1 for row in items},
                    "npc": [], "size": len(items), "first": items[0]["id"]})
    return out


def scan(obj, meta_obj, state=None):
    player = obj.get("playerModel") or {}
    component = player.get("questComponent") or {}
    saved = component.get("quests") or {}
    saved = {_int(key): value for key, value in saved.items() if isinstance(value, dict)}
    states = meta_obj.get("states") or {}
    realms = meta_obj.get("realms") or {}
    layer = (player.get("combat") or {}).get("cultivate_layer_id")
    player_realm = _realm_for_layer(meta_obj.get("phases") or {}, layer)

    retired, npc_places = set(), {}
    favor, npc_realms = {}, {}
    phases = meta_obj.get("phases") or {}
    spaces = obj.get("spaces") or {}
    space_names = meta_obj.get("space_names") or {}
    npc_homes = meta_obj.get("npc_homes") or {}
    npc_names = meta_obj.get("npc_names") or {}
    for record in (obj.get("npcs") or {}).values():
        if not isinstance(record, dict):
            continue
        npc_id = _int(record.get("npcCfgId"))
        favor[npc_id] = _int(record.get("intimacy"))
        cultivation = record.get("cultivation_state") or {}
        if cultivation.get("cultivate_layer_id") is not None:
            npc_realms[npc_id] = _realm_for_layer(phases, cultivation.get("cultivate_layer_id"))
        if _int(record.get("worldStatus")) == 2:
            retired.add(npc_id)
        space_uuid = record.get("currentSpaceUuid") or ""
        space = spaces.get(space_uuid) or {}
        if space.get("spaceId"):
            npc_places[npc_id] = _int(space.get("spaceId"))
    behavior = player.get("behavior_value") or {}
    city_rep = behavior.get("city_reputes") or {}
    sect_rep = behavior.get("sect_reputes") or {}
    ctx = {
        "favor": favor, "city_rep": city_rep,
        "sect_rep": max([_int(v) for v in sect_rep.values()] or [0]),
        "player_realm": player_realm, "layer": _int(layer),
        "money": _int(player.get("money")),
        "quests": {quest_id: _int((value or {}).get("state"), 0)
                   for quest_id, value in saved.items()},
        "attr_exp": player.get("interact_attributes") or {},
        "attr_levels": meta_obj.get("attr_levels") or {},
        "npc_realms": npc_realms,
        "phases": phases,
        "realms": realms,
    }
    egg_notes = meta_obj.get("egg_notes") or []

    rows = []
    for quest in meta_obj.get("quests") or []:
        quest_id = _int(quest.get("id"))
        item = saved.get(quest_id) or {}
        code = _int(item.get("state"), 0)
        realm_ids = [_int(value) for value in (quest.get("realm_ids") or []) if _int(value)]
        giver = quest.get("giver") or {}
        giver_id = _int(giver.get("id"))
        location = quest.get("location") or {}
        cond = quest.get("acq_cond") or None
        cond_ok, cond_fail = None, ""
        cond_eval = None
        if cond:
            cond_eval = _eval_tree(cond.get("tree"), ctx)
            cond_ok = cond_eval["ok"]
            cond_fail = "；".join(cond_eval["gaps"])
        gate_eval = []
        for gate in (quest.get("option_gates") or []):
            leaf = gate.get("leaf") or {}
            ev = _eval_check(leaf, ctx) if leaf else None
            gate_eval.append({
                "dialogue": _int(gate.get("dialogue")),
                "sub": _int(gate.get("sub")),
                "option": gate.get("option") or "",
                "text": gate.get("text") or "",
                "hint": gate.get("hint") or "",
                "hint_missing": bool(gate.get("hint_missing")),
                "context": gate.get("context") or {},
                "eval": ev,
            })
        reasons = []
        if realm_ids and player_realm and player_realm not in realm_ids:
            reasons.append("境界已过（这条支线限%s）" % "/".join(
                realms.get(str(value), str(value)) for value in realm_ids))
        if giver_id and giver_id in retired:
            reasons.append("委托人%s已退隐" % (giver.get("name") or ""))
        space_closed = bool(location.get("realm") and player_realm
                            and player_realm > _int(location.get("realm")))
        egg_note = next((note for note in egg_notes
                         if _int(note.get("quest")) == quest_id
                         or quest_id in [_int(v) for v in note.get("to") or []]), None)
        rows.append({
            "id": quest_id,
            "name": quest.get("name") or "未命名支线",
            "group": quest.get("group") or "",
            "desc": quest.get("desc") or "",
            "hidden": bool(quest.get("hidden")),
            "type_name": quest.get("type_name") or "支线",
            "acq_source": _int(quest.get("acq_source")),
            "one_off": bool(quest.get("one_off")),
            "branch": bool(quest.get("branch")),
            "branch_key": quest.get("branch_key") or "",
            "branch_with": quest.get("branch_with") or [],
            "chain_id": quest.get("chain_id") or "",
            "chain_name": quest.get("chain_name") or "",
            "chain_index": _int(quest.get("chain_index")),
            "rewards": quest.get("rewards") or [],
            "reward_stone": _int(quest.get("reward_stone")),
            "location": quest.get("location"),
            "spot": quest.get("spot") or "",
            "giver": quest.get("giver"),
            "giver_place": space_names.get(str(npc_places.get(giver_id) or ""), ""),
            "place_text": ((location or {}).get("name")
                           or space_names.get(str(npc_places.get(giver_id) or ""), "")
                           or ("常驻%s" % npc_homes[str(giver_id)]
                               if giver_id and npc_homes.get(str(giver_id)) else "")),
            "prev": _int(quest.get("prev")),
            "next": quest.get("next") or [],
            "branch_of": _int(quest.get("acq_branch_of")),
            "branch_siblings": quest.get("acq_branch_siblings") or [],
            "prev_options": quest.get("prev_options") or [],
            "acq_cond": cond,
            "acq_readable": (cond or {}).get("readable") or "",
            "option_gates": quest.get("option_gates") or [],
            "trigger_detail": quest.get("trigger_detail"),
            "trigger_text": quest.get("trigger_text") or "",
            "trigger_label": (quest.get("trigger_detail") or {}).get("label") or "",
            "cond_text": (cond or {}).get("text") or "",
            "cond_fail_text": cond_fail,
            "cond_ok": cond_ok,
            "cond_eval": cond_eval,
            "gate_eval": gate_eval,
            "egg_note": egg_note,
            "gate": quest.get("gate"),
            "acq_dialogue": quest.get("acq_dialogue"),
            "acq_flows": quest.get("acq_flows") or [],
            "objectives": quest.get("objectives") or [],
            "realm_ids": realm_ids,
            "space_closed": space_closed,
            "npc_retired": bool(giver_id and giver_id in retired),
            "unreachable": bool(reasons),
            "unreachable_text": "；".join(reasons),
            "accepted": bool(item),
            "accept_time": _int(item.get("acceptTime")),
            "state": code,
            "state_name": states.get(str(code)) or ("状态 %s" % code),
            "done": code in DONE_STATES,
            "doing": code in DOING_STATES,
            "same_name": quest.get("same_name") or [],
        })

    by_id = {row["id"]: row for row in rows}
    # 多个剧情入口汇到同一环时，优先接在实际走过的那条分支后面。
    for row in rows:
        options = row.get("prev_options") or []
        prev_row = by_id.get(row["prev"])
        if options and not (prev_row and prev_row["done"]):
            for option in options:
                peer = by_id.get(_int(option))
                if peer and peer["done"] and peer["id"] != row["id"]:
                    row["prev"] = peer["id"]
                    break
        prev_row = by_id.get(row["prev"])
        if not (row["done"] and prev_row and not prev_row["done"]):
            continue
        for peer in rows:
            if (peer["id"] != row["id"] and peer["done"] and peer["prev"] == prev_row["prev"]
                    and peer["chain_id"] == prev_row["chain_id"]):
                row["prev"] = peer["id"]
                break

    for row in rows:
        row["place_inherited"] = False

    def place_of(row, seen=None):
        if row["place_text"]:
            return row["place_text"]
        seen = seen or set()
        prev = by_id.get(row["prev"])
        if not prev or prev["id"] in seen:
            return ""
        seen.add(row["id"])
        found = place_of(prev, seen)
        if found:
            row["place_text"] = found
            row["place_inherited"] = True
        return found

    for row in rows:
        place_of(row)

    layer_phases = meta_obj.get("layer_phases") or {}
    phase_names = meta_obj.get("phase_names") or {}

    def _realm_text(layer_value):
        realm_name = str(realms.get(str(_realm_for_layer(phases, _int(layer_value)))) or "").strip()
        return realm_name.replace("期", "") or realm_name or ("第 %d 层" % _int(layer_value))

    def _current_phase(layer_value):
        """玩家当前层（propLayerId）→ 阶段全称：29 → 筑基后期。"""
        return layer_phases.get(str(_int(layer_value))) or _realm_text(layer_value)

    def _gate_phase(value):
        """触发条件里的「修炼阶段」是阶段 id（33 → 结丹后期），不是 propLayerId。"""
        return (phase_names.get(str(_int(value)))
                or layer_phases.get(str(_int(value)))
                or _realm_text(value))

    for row in rows:
        gate = row.get("gate") or {}
        detail = gate.get("trigger_detail") or {}
        ids = [_int(value) for value in gate.get("quests") or []]
        names, done = [], True
        for gate_id in ids:
            gate_row = by_id.get(gate_id)
            names.append(gate_row["name"] if gate_row else "未收录任务")
            if not gate_row or not gate_row["done"]:
                done = False
        row["gate_names"] = "、".join(names)
        row["gate_event"] = gate.get("event") or ""
        row["gate_done"] = bool(ids) and done
        row["gate_pending"] = bool(ids) and not row["gate_done"]
        row["gate_space"] = _int(gate.get("space"))
        row["gate_space_name"] = space_names.get(str(row["gate_space"]), "")
        row["gate_layer"] = _int(gate.get("layer"))
        row["gate_npc"] = _int(gate.get("npc"))
        row["gate_favor"] = _int(gate.get("favor"))
        ready, hint, check = True, "", None
        if ids:
            ready = done
            hint = "完成「%s」后自动触发" % row["gate_names"]
        elif row["gate_layer"]:
            need_name = _gate_phase(row["gate_layer"])
            cur_name = _current_phase(layer)
            ready = _int(layer) >= row["gate_layer"]
            text = "修炼到「%s」后自动出现" % need_name
            hint = text if ready else "%s（当前 %s）" % (text, cur_name)
            check = {"kind": "realm", "text": text, "cur_text": cur_name, "ok": ready}
        elif row["gate_space"]:
            place = row["gate_space_name"] or "指定地点"
            hint = "进入「%s」后出现" % place
            ready = False
            check = {"kind": "scene_enter", "text": hint, "cur_text": "尚未进入", "ok": False}
        elif row["gate_npc"]:
            npc_name = npc_names.get(str(row["gate_npc"])) or "对方"
            cur_favor = _int(favor.get(row["gate_npc"], 0))
            ready = cur_favor >= row["gate_favor"]
            text = "与「%s」好感达到 %d 后出现" % (npc_name, row["gate_favor"])
            hint = text if ready else "%s（当前 %d）" % (text, cur_favor)
            check = {"kind": "npc_favor", "text": text, "cur_text": "当前 %d" % cur_favor,
                     "ok": ready}
        elif row["gate_event"] == "接取条件满足":
            hint = "满足条件后自动触发"
        elif row["gate_event"]:
            hint = detail.get("label") or ("%s后自动触发" % row["gate_event"])
        row["gate_ready"] = ready
        row["gate_hint"] = hint
        if check:
            cond_eval = row.get("cond_eval")
            if not isinstance(cond_eval, dict):
                cond_eval = {"checks": [], "gaps": [], "logic": ""}
                row["cond_eval"] = cond_eval
            cond_eval.setdefault("checks", []).insert(0, check)
            if not check["ok"]:
                cond_eval.setdefault("gaps", []).append(check["text"])

    siblings = {}
    for ids in (meta_obj.get("flow_accepts") or {}).values():
        ids = [_int(value) for value in ids]
        for quest_id in ids:
            siblings[quest_id] = [value for value in ids if value != quest_id]
    for row in rows:
        row["same_flow_done"] = ""
        for other in siblings.get(row["id"], []):
            peer = by_id.get(other)
            if peer and peer["done"]:
                row["same_flow_done"] = peer["name"]
                break
    branch_rows = {}
    for row in rows:
        if row["branch_key"]:
            branch_rows.setdefault(row["branch_key"], []).append(row)
    for row in rows:
        prev = by_id.get(row["prev"])
        row["prev_name"] = prev["name"] if prev else ""
        row["prev_state_name"] = prev["state_name"] if prev else ""
        row["prev_done"] = bool(prev and prev["done"])
        peers = [item for item in branch_rows.get(row["branch_key"], []) if item["id"] != row["id"]]
        chosen = [item for item in peers if item["done"] or item["doing"]]
        row["branch_missed"] = bool(chosen) and not (row["done"] or row["doing"])
        row["branch_chosen"] = chosen[0]["name"] if chosen else ""
        row["record_gap"] = (not row["done"] and not row["doing"]
                             and any(by_id[n]["done"] for n in row["next"] if n in by_id))

    for row in rows:
        row["branch_of_name"] = ""
        row["branch_of_done"] = False
        req_row = by_id.get(_int(row.get("branch_of")))
        if not req_row:
            continue
        row["branch_of_name"] = req_row["name"]
        row["branch_of_done"] = bool(req_row["done"])
        if req_row["done"] or row["done"] or row["doing"]:
            continue
        chosen = None
        for other in row.get("branch_siblings") or []:
            peer = by_id.get(_int(other))
            if peer and peer["id"] != row["id"] and (peer["done"] or peer["doing"]):
                chosen = peer
                break
        if chosen:
            row["branch_missed"] = True
            row["branch_chosen"] = chosen["name"]
            row["branch_via"] = req_row["name"]

    # 前置链传播：起点无法再接或已选另一分支时，后续环同样走不到。
    for row in rows:
        if row["done"] or row["doing"] or row["unreachable"] or row["branch_missed"]:
            continue
        seen, cur = {row["id"]}, row
        blocked, missed = None, None
        missed_names = []
        while cur["prev"] in by_id and cur["prev"] not in seen:
            seen.add(cur["id"])
            cur = by_id[cur["prev"]]
            if cur["unreachable"] and blocked is None:
                blocked = cur
            if cur["branch_missed"]:
                if missed is None:
                    missed = cur
                missed_names.append(cur["name"])
        if blocked is not None:
            row["unreachable"] = True
            row["unreachable_text"] = "前置「%s」无法再接：%s" % (blocked["name"],
                                                               blocked["unreachable_text"])
            row["blocked_by"] = blocked["name"]
        elif missed is not None:
            row["branch_missed"] = True
            row["branch_chosen"] = missed["branch_chosen"]
            row["branch_via"] = missed["name"]
            if len(missed_names) > 1:
                row["branch_path"] = " › ".join(reversed(missed_names))

    # 剧情线信息（章节/线名）：同名任务与前置按钮要标清“哪一个”，不能只给任务名。
    quest_index = meta_obj.get("quest_index") or {}
    line_of, chapter_of = {}, {}
    for line in (meta_obj.get("storylines") or []):
        for qid in line.get("quests") or []:
            line_of[_int(qid)] = line.get("name") or ""
            chapter_of[_int(qid)] = line.get("chapter") or ""
    name_ids = {}
    for row in rows:
        if row["name"]:
            name_ids.setdefault(row["name"], []).append(row["id"])
    dup_names = {name: ids for name, ids in name_ids.items() if len(ids) > 1}

    def _ref_label(name, qid):
        """同名任务只写名字会认错，后面补章节：完成「小蝶所托」（炼气）后出现。"""
        qid = _int(qid)
        chapter = chapter_of.get(qid) or ""
        if name and name in dup_names and chapter:
            return "「%s」（%s）" % (name, chapter)
        return "「%s」" % (name or "前置任务")

    for row in rows:
        exclusive_failed = any(check.get("kind") == "quest_none" and check.get("ok") is False
                               for check in ((row.get("cond_eval") or {}).get("checks") or []))
        if row["done"]:
            label = STATUS_DONE
        elif row["doing"]:
            label = STATUS_DOING
        elif row["branch_missed"] or row["same_flow_done"] or exclusive_failed:
            label = STATUS_UNPICKED
        elif row["cond_ok"] is False:
            label = STATUS_WAIT if row["trigger_text"] else STATUS_COND
        elif row["unreachable"]:
            label = STATUS_WAIT
        elif row["prev"] and not row["prev_done"]:
            label = STATUS_WAIT
        elif row["record_gap"]:
            label = STATUS_WAIT
        elif row["gate_pending"]:
            label = STATUS_WAIT
        elif not row["gate_ready"]:
            label = STATUS_WAIT
        elif row["cond_text"] and row["cond_ok"] is not True:
            label = STATUS_WAIT
        elif row["accepted"] and row["state"] in (4, 5):
            label = STATUS_WAIT
        else:
            label = STATUS_READY
        row["status_label"] = label
        row["status_key"] = STATUS_KEYS[label]
        row["status_cls"] = ("ok" if label in (STATUS_DONE, STATUS_READY)
                             else ("warn" if label in (STATUS_COND,) else ""))

        if row["done"] or row["doing"]:
            hint = ""
        elif row["branch_missed"]:
            if row.get("branch_path"):
                hint = "前面的「%s」只能选一条，你走的是「%s」" % (
                    row["branch_path"], row["branch_chosen"])
            elif row.get("branch_via"):
                hint = "「%s」处只能选一条，你走的是「%s」" % (
                    row["branch_via"], row["branch_chosen"])
            elif row["branch_chosen"]:
                hint = "这处只能选一条，你走的是「%s」" % row["branch_chosen"]
            else:
                hint = "这处只能选一条"
        elif row["same_flow_done"]:
            hint = "与「%s」出自同一段剧情，只能走其中一条" % row["same_flow_done"]
        elif exclusive_failed:
            hint = "这处只能二选一，你已经走了另一条"
        elif row["unreachable"]:
            hint = row["unreachable_text"]
        elif row["cond_ok"] is False:
            hint = "还差：%s" % (row["cond_fail_text"] or row["cond_text"])
        elif row["record_gap"]:
            hint = "后续环节已完成，这一环可能已被跳过"
        elif row["prev"] and not row["prev_done"]:
            hint = "先完成%s" % _ref_label(row["prev_name"], row.get("prev"))
        elif row["gate_pending"]:
            hint = row["gate_hint"]
        elif not row["gate_ready"]:
            hint = row["gate_hint"]
        elif row["trigger_text"]:
            hint = row["trigger_text"]
        elif row["accepted"] and row["state"] in (4, 5):
            hint = "任务已%s，回委托人处可以重接" % row["state_name"]
        elif row["acq_source"] == 1:
            giver_name = (row.get("giver") or {}).get("name") or "委托人"
            hint = "与%s对话接取" % giver_name
        elif row.get("acq_dialogue"):
            hint = "在剧情对话中接取"
        elif row["gate_hint"]:
            hint = row["gate_hint"]
        elif row["cond_text"]:
            hint = "条件：%s" % row["cond_text"]
        elif row["acq_source"] == 2:
            hint = "剧情推进到这里时自动出现"
        else:
            hint = "与委托人对话后出现"
        row["status_hint"] = hint
        # 折叠行也要有一句“怎么触发”，已完成的任务同样能回看。
        if row["trigger_text"]:
            trigger_line = row["trigger_text"]
        elif row["gate_hint"] and not row["gate_ready"]:
            trigger_line = row["gate_hint"]
        elif row["cond_text"]:
            trigger_line = "条件：%s" % row["cond_text"]
        elif row["gate_hint"]:
            trigger_line = row["gate_hint"]
        elif row["prev_name"] and row["prev_done"]:
            trigger_line = "完成%s后自动出现" % _ref_label(row["prev_name"], row.get("prev"))
        elif row["prev_name"]:
            trigger_line = "完成%s后出现" % _ref_label(row["prev_name"], row.get("prev"))
        elif row["acq_source"] == 1:
            trigger_line = "与%s对话接取" % ((row.get("giver") or {}).get("name") or "委托人")
        elif row.get("acq_dialogue"):
            trigger_line = "在剧情对话中接取"
        else:
            trigger_line = "剧情推进到这里时自动出现"
        # 折叠行引用了同名任务时补章节，避免「完成小蝶所托后」让人以为是另一个。
        ref_ids = list((row.get("gate") or {}).get("quests") or [])
        if row.get("prev"):
            ref_ids.append(row["prev"])
        for qid in ref_ids:
            other = by_id.get(_int(qid))
            if not other or other["name"] not in dup_names:
                continue
            old = "「%s」" % other["name"]
            if old in trigger_line and (old + "（") not in trigger_line:
                trigger_line = trigger_line.replace(old, _ref_label(other["name"], qid), 1)
        row["trigger_line"] = trigger_line

    # 同名任务：把“另一个同名任务是什么状态、在哪条线”一并给前端，页面才讲得清。
    for row in rows:
        ids = row.get("same_name") or []
        if not ids:
            continue
        info = []
        for qid in ids:
            other = by_id.get(_int(qid))
            if not other:
                continue
            info.append({
                "id": other["id"],
                "name": other["name"],
                "chapter": chapter_of.get(other["id"]) or "",
                "line": line_of.get(other["id"]) or "",
                "region": ((other.get("location") or {}).get("region") or ""),
                "giver": (other.get("giver") or {}).get("name") or "",
                "status_label": other["status_label"],
                "status_key": other["status_key"],
                "done": other["done"],
            })
        if info:
            row["ambiguous"] = True
            row["same_name_info"] = info

    # 怎么触发 + 前置任务：让玩家不只知道“要完成 XXX”，还知道 XXX 是什么、在哪、能不能点过去。
    def _ref(qid):
        qid = _int(qid)
        if not qid:
            return None
        local = by_id.get(qid) or {}
        info = quest_index.get(str(qid)) or {}
        side = bool(local) or bool(info.get("side"))
        return {
            "id": qid,
            "name": local.get("name") or info.get("name") or ("任务 %s" % qid),
            "type_name": ("支线" if local else (info.get("type_name") or "其他任务")),
            "side": side,
            "line": line_of.get(qid) or "",
            "chapter": chapter_of.get(qid) or "",
            "status_label": local.get("status_label") or ("不在本页" if not side else ""),
            "status_key": local.get("status_key") or ("out" if not side else ""),
            "done": bool(local.get("done")),
        }

    for row in rows:
        # 接取方式：1 = 找 NPC，2 = 自动触发（QuestAcqSource）
        giver = row.get("giver") or {}
        auto = _int(row.get("acq_source")) == 2
        how = {"auto": auto,
               "text": "自动触发（条件满足时出现）" if auto else "找「%s」接取" % (giver.get("name") or "委托人")}
        if giver.get("name"):
            how["giver"] = giver["name"]
            home = npc_homes.get(str(_int(giver.get("id")))) or ""
            if home:
                how["giver_home"] = home
        place = row.get("location") or {}
        if place.get("path"):
            how["place"] = " / ".join(place["path"])
        elif row.get("place_text"):
            how["place"] = row["place_text"]
        row["how"] = how

        refs, seen = [], set()
        # cond_eval 里的 checks 只带文案与结果，任务 id 在 acq_cond 的原始条件里，按下标对齐取。
        acq_checks = (row.get("acq_cond") or {}).get("checks") or []
        eval_checks = (row.get("cond_eval") or {}).get("checks") or []
        for index, check in enumerate(acq_checks):
            if check.get("kind") not in ("quest_done", "quest_hold", "quest_accepted", "quest_active"):
                continue
            ref = _ref(check.get("quest"))
            if not ref or ref["id"] in seen:
                continue
            result = eval_checks[index] if index < len(eval_checks) else {}
            ref["need_text"] = check.get("text") or ""
            ref["ok"] = result.get("ok")
            seen.add(ref["id"])
            refs.append(ref)
        # “满足其一”的条件：已经满足的那条才是真正放行的前置，别把没走的另一条当成要求。
        if (row.get("acq_cond") or {}).get("mode") == "any" and refs:
            row["prereq_any"] = True
            satisfied = [ref for ref in refs if ref.get("ok") is True]
            refs = satisfied or refs
        refs = [ref for ref in refs if not ref["done"]]
        if row.get("prev") and row["prev"] not in seen and not row.get("prev_done"):
            ref = _ref(row["prev"])
            if ref:
                ref["need_text"] = "先完成「%s」" % ref["name"]
                ref["ok"] = False
                refs.append(ref)
        row["prereq"] = refs

    storylines = []
    for line in (meta_obj.get("storylines") or _fallback_storylines(rows)):
        ids = [_int(value) for value in line.get("quests") or [] if _int(value) in by_id]
        if not ids:
            continue
        nodes = [by_id[quest_id] for quest_id in ids]
        done = sum(1 for node in nodes if node["done"])
        unpicked = sum(1 for node in nodes if node["status_key"] == "unpicked")
        reachable = [node for node in nodes if node["status_key"] != "unpicked"]
        stones_left = sum(node["reward_stone"] for node in reachable if not node["done"])
        next_node = next((node for node in nodes
                          if not node["done"] and node["status_key"] in ("ready", "cond", "wait")), None)
        storylines.append({
            "id": line.get("id") or ("s%d" % ids[0]),
            "name": line.get("name") or nodes[0]["name"],
            "chapter": line.get("chapter") or "支线",
            "region": line.get("region") or "",
            "group": line.get("group") or "",
            "quests": ids,
            "depths": line.get("depths") or {},
            "npc": line.get("npc") or [],
            "size": len(ids),
            "done": done,
            "total": len(reachable),
            "stones_left": stones_left,
            "next": next_node["id"] if next_node else 0,
            "doing": sum(1 for node in nodes if node["doing"]),
        })

    total = len(rows)
    reward_rows = [r for r in rows if r["rewards"]]
    stats = {
        "total": total,
        "done": sum(1 for r in rows if r["done"]),
        "doing": sum(1 for r in rows if r["doing"]),
        "todo": sum(1 for r in rows if not r["accepted"]),
        "failed": sum(1 for r in rows if r["state"] == 4),
        "with_rewards": len(reward_rows),
        "rewards_done": sum(1 for r in reward_rows if r["done"]),
        "rewards_todo": sum(1 for r in reward_rows if not r["done"]),
        "stones_todo": sum(r["reward_stone"] for r in reward_rows
                           if not r["done"] and r["status_key"] != "unpicked"),
        "stones_done": sum(r["reward_stone"] for r in reward_rows if r["done"]),
        "hidden": sum(1 for r in rows if r["hidden"]),
        "branch": sum(1 for r in rows if r["branch"]),
        "branches": _int((meta_obj.get("stats") or {}).get("branches")),
        "chains": _int((meta_obj.get("stats") or {}).get("chains")),
        "storylines": len(storylines),
        "unreachable": sum(1 for r in rows if not r["done"] and r["unreachable"]),
        "unreachable_stones": sum(r["reward_stone"] for r in rows if not r["done"] and r["unreachable"]),
        "can_accept": sum(1 for r in rows if r["status_key"] == "ready"),
        "cond_fail": sum(1 for r in rows if r["status_key"] == "cond"),
        "waiting": sum(1 for r in rows if r["status_key"] == "wait"),
        "missed": sum(1 for r in rows if r["status_key"] == "unpicked"),
        "player_layer": _int(layer),
        "player_realm": player_realm,
        "player_realm_name": realms.get(str(player_realm)) or "",
    }
    return {"rows": rows, "stats": stats, "storylines": storylines,
            "dup_names": meta_obj.get("dup_names") or {},
            "groups": meta_obj.get("groups") or [],
            "chains": meta_obj.get("chains") or [], "branches": meta_obj.get("branches") or [],
            "edges": meta_obj.get("edges") or [],
            "diagnostics": meta_obj.get("diagnostics") or {},
            "egg_notes": egg_notes,
            "attr_names": meta_obj.get("attr_names") or {},
            "quest_index": meta_obj.get("quest_index") or {},
            "chapter_order": meta_obj.get("chapter_order") or {},
            "chapter_tones": meta_obj.get("chapter_tones") or {},
            "realms": realms, "states": states}


def post(rows, state, original, path):
    if isinstance(rows, dict):
        rows["src"] = os.path.basename(original) if original else os.path.basename(path or "")
    return rows


def enrich(module, meta_obj, state=None):
    return module


def summary(module):
    stats = (module.get("rows") or {}).get("stats") or {}
    return "支线：%d 个，已完成 %d 个，进行中 %d 个，未接取 %d 个；剧情线 %d 条" % (
        stats.get("total", 0), stats.get("done", 0), stats.get("doing", 0),
        stats.get("todo", 0), stats.get("storylines", 0))
