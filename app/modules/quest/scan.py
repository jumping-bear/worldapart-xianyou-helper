# -*- coding: utf-8 -*-
"""支线扫描：任务状态、奖励、剧情线与前置链路。"""
import os


DONE_STATES = (2, 3)
DOING_STATES = (1, 6)


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


def _egg_matches(note, quest_id, cond):
    return (_int(note.get("quest")) == quest_id
            or (note.get("alias") and (cond or {}).get("alias") == note.get("alias")))


def _eval_check(check, ctx):
    """按当前存档判定单个条件；返回 ok(True/False/None)、当前显示值与缺口描述。"""
    kind = check.get("kind") or ""
    need = _int(check.get("need"))
    text = check.get("text") or "条件"
    cur, ok, is_level = None, None, False
    if kind == "favor":
        cur = ctx["favor"].get(_int(check.get("npc")), 0)
        ok = cur >= need
    elif kind == "city_rep":
        cur = _int(ctx["city_rep"].get(str(_int(check.get("city"))), 0))
        ok = cur >= need
    elif kind == "sect_rep":
        cur = ctx["sect_rep"]
        ok = cur >= need
    elif kind in ("phase", "realm"):
        cur = ctx["player_realm"]
        ok = cur >= need
    elif kind == "layer":
        cur = ctx["layer"]
        ok = cur >= need
    elif kind == "money":
        cur = ctx["money"]
        ok = cur >= need
    elif kind in ("quest_done", "quest_hold", "quest_accepted", "quest_active"):
        quest_id = _int(check.get("quest"))
        code = ctx["quests"].get(quest_id, -1)
        if kind == "quest_done":
            cur = 1 if code in DONE_STATES else 0
        elif kind == "quest_hold":
            cur = 1 if code in DOING_STATES else 0
        elif kind == "quest_accepted":
            cur = 1 if quest_id in ctx["quests"] else 0
        else:
            cur = 1 if code in DOING_STATES else 0
        ok = cur >= need
        text = text or "任务状态"
    elif kind == "attr":
        attr_id = _int(check.get("attr"))
        exp = ctx["attr_exp"].get(str(attr_id), ctx["attr_exp"].get(attr_id, 0))
        cur, is_level = _attr_level(exp, ctx["attr_levels"].get(str(attr_id)) or [])
        ok = cur >= need
    elif kind == "npc_realm":
        cur = ctx["npc_realms"].get(_int(check.get("npc")))
        if cur is not None:
            ok = _cmp(check.get("op") or "≥", cur, need)
    if cur is None:
        cur_text = "未知"
    elif is_level:
        cur_text = "Lv%d" % cur
    elif kind in ("quest_done", "quest_hold", "quest_accepted", "quest_active"):
        cur_text = "已完成" if cur >= need else "未完成"
    else:
        cur_text = str(cur)
    gap = ""
    if ok is False:
        if is_level:
            gap = "%s（需 Lv%d，当前 Lv%d）" % (text, need, cur)
        elif kind == "npc_realm":
            gap = "%s（当前 %s）" % (text, cur_text)
        elif kind in ("quest_done", "quest_hold", "quest_accepted", "quest_active"):
            gap = text
        else:
            gap = "%s（需 %d，当前 %s）" % (text, need, cur_text)
    return {"kind": kind, "text": text, "need": need, "cur": cur,
            "cur_text": cur_text, "ok": ok, "gap": gap}


def _eval_tree(tree, ctx):
    """递归判定条件树，保留 且/或/非 逻辑，输出可展示的缺口链。"""
    checks = []

    def walk(node):
        if not isinstance(node, dict):
            return {"ok": None, "gaps": [], "text": "", "checks": []}
        op = node.get("op")
        if op:
            children = [walk(child) for child in (node.get("children") or [])]
            vals = [child["ok"] for child in children]
            gaps = [g for child in children for g in child["gaps"]]
            if op == "and":
                ok = False if False in vals else (None if None in vals else True)
            elif op == "or":
                ok = True if True in vals else (None if None in vals else False)
                if ok is True:
                    gaps = []
                else:
                    parts = [c["gaps"][0] if c["gaps"] else c["text"] for c in children]
                    gaps = ["满足其一：" + " 或 ".join(p for p in parts if p)]
            elif op == "not":
                inner = children[0] if children else {"ok": None, "gaps": [], "text": "", "checks": []}
                ok = None if inner["ok"] is None else (not inner["ok"])
                # 展示时把“非(条件)”整体翻转，避免 ✓ 出现在需要“不满足”的条件上造成误读
                flipped = []
                for check in inner.get("checks") or []:
                    item = dict(check)
                    item["ok"] = None if check.get("ok") is None else (not check["ok"])
                    item["text"] = "非（%s）" % check.get("text", "")
                    item["gap"] = "" if item["ok"] is not False else "目前仍满足「%s」" % check.get("text", "")
                    flipped.append(item)
                gaps = ["目前仍满足「%s」" % inner["text"]] if inner["ok"] is True else []
                return {"ok": ok, "gaps": gaps,
                        "text": "非（%s）" % inner.get("text", ""), "checks": flipped}
            else:
                ok = None
            return {"ok": ok, "gaps": gaps, "text": node.get("text") or "",
                    "checks": [c for child in children for c in child["checks"]]}
        ev = _eval_check(node.get("leaf") or {}, ctx)
        checks.append(ev)
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
    if flags["not"] or (flags["and"] and flags["or"]):
        return "混合逻辑（且/或/非）"
    if flags["or"]:
        return "满足其一（或）"
    if flags["and"]:
        return "全部满足（且）"
    return "单一条件"


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def meta(metadata):
    return metadata.get("quest") or {
        "quests": [], "groups": [], "realms": {"0": "凡人"},
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


def _start_text(root):
    """剧情线起点的进入方式，用于“整条线未开始”的提示。"""
    label = root.get("status_label")
    giver = (root.get("giver") or {}).get("name") or ""
    if label == "可接取":
        return "：与%s对话接取" % giver if giver else "：与委托人对话接取"
    if label == "待触发":
        return "：" + (root.get("status_hint") or "完成前置后自动触发")
    if label == "条件不足":
        return "，但接取条件未满足：%s" % (root.get("cond_text") or "")
    if label == "剧情接取":
        return "：在剧情对话中接取"
    if label == "疑似已跳过":
        return "：同一段剧情里可能已经选了别的分支"
    if label == "触发未知":
        return "：触发方式不固定，需要在剧情中留意"
    if label == "疑似已触发":
        return "：前置已完成但本环没有记录"
    if label == "未选分支":
        return "：" + (root.get("status_hint") or "已选择另一分支")
    if label == "不可达":
        return "：" + (root.get("unreachable_text") or "已无法接取")
    return ""


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
    }
    egg_notes = meta_obj.get("egg_notes") or []
    gate_diag = []
    for gate in ((meta_obj.get("diagnostics") or {}).get("option_gates") or []):
        leaf = gate.get("leaf") or {}
        gate_diag.append({
            "quest": _int(gate.get("quest")), "quest_name": gate.get("quest_name") or "",
            "dialogue": _int(gate.get("dialogue")), "sub": _int(gate.get("sub")),
            "alias": gate.get("alias") or "", "text": gate.get("text") or "",
            "option": gate.get("option") or "", "no_grey": bool(gate.get("no_grey")),
            "grey": gate.get("grey") or "", "priority": gate.get("priority") or "",
            "context": gate.get("context") or {},
            "eval": _eval_check(leaf, ctx) if leaf else None,
        })

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
            cond_fail = "、".join(cond_eval["gaps"])
            if cond.get("mode") == "unknown" and not (cond.get("tree") or {}).get("op"):
                cond_ok = None
        gate_eval = []
        for gate in (quest.get("option_gates") or []):
            leaf = gate.get("leaf") or {}
            ev = _eval_check(leaf, ctx) if leaf else None
            gate_eval.append({
                "dialogue": _int(gate.get("dialogue")),
                "sub": _int(gate.get("sub")),
                "option": gate.get("option") or "",
                "text": gate.get("text") or "",
                "no_grey": bool(gate.get("no_grey")),
                "alias": gate.get("alias") or "",
                "context": gate.get("context") or {},
                "eval": ev,
            })
        reasons = []
        if realm_ids and player_realm and player_realm not in realm_ids:
            reasons.append("境界已过（限%s）" % "/".join(realms.get(str(value), str(value))
                                                       for value in realm_ids))
        if giver_id and giver_id in retired:
            reasons.append("委托人%s已退隐" % (giver.get("name") or ""))
        space_closed = bool(location.get("realm") and player_realm
                            and player_realm > _int(location.get("realm")))
        rows.append({
            "id": quest_id,
            "name": quest.get("name") or ("支线 %s" % quest_id),
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
            "acq_mixed": bool((cond or {}).get("mixed")),
            "option_gates": quest.get("option_gates") or [],
            "trigger_detail": quest.get("trigger_detail"),
            "trigger_label": (quest.get("trigger_detail") or {}).get("label") or "",
            "cond_text": (cond or {}).get("text") or "",
            "cond_fail_text": cond_fail,
            "cond_need": 0,
            "cond_cur": None,
            "cond_ok": cond_ok,
            "cond_eval": cond_eval,
            "gate_eval": gate_eval,
            "egg_note": next((note for note in egg_notes if _egg_matches(note, quest_id, cond)), None),
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
        # 已完成的环如果挂在没走的选项后，改挂到同段剧情里实际走的那个选项
        for peer in rows:
            if (peer["id"] != row["id"] and peer["done"] and peer["prev"] == prev_row["prev"]
                    and peer["chain_id"] == prev_row["chain_id"]):
                row["prev"] = peer["id"]
                break
    # 后续环自己没有委托人时，沿用前置环的地点。
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
    for row in rows:
        gate = row.get("gate") or {}
        ids = [_int(value) for value in gate.get("quests") or []]
        names, done = [], True
        for gate_id in ids:
            gate_row = by_id.get(gate_id)
            names.append(gate_row["name"] if gate_row else ("任务 %s" % gate_id))
            if not gate_row or not gate_row["done"]:
                done = False
        row["gate_names"] = "、".join(names)
        row["gate_event"] = gate.get("event") or "任务提交"
        row["gate_done"] = bool(ids) and done
        row["gate_space"] = _int(gate.get("space"))
        row["gate_space_name"] = space_names.get(str(row["gate_space"]), "")
        row["gate_layer"] = _int(gate.get("layer"))
        row["gate_npc"] = _int(gate.get("npc"))
        row["gate_favor"] = _int(gate.get("favor"))
        ready, hint = False, ""
        if ids:
            hint = "完成「%s」后自动触发（%s）" % (row["gate_names"], row["gate_event"])
        elif row["gate_space"]:
            hint = "进入「%s」后触发" % (row["gate_space_name"] or ("场景 %s" % row["gate_space"]))
        elif row["gate_layer"]:
            ready = _int(layer) >= row["gate_layer"]
            hint = "修炼层数达到 %d 后触发（当前 %d）" % (row["gate_layer"], _int(layer))
        elif row["gate_npc"]:
            cur_favor = favor.get(row["gate_npc"], 0)
            ready = cur_favor >= row["gate_favor"]
            hint = "%s好感度达到 %d 后触发（当前 %d）" % (
                npc_names.get(str(row["gate_npc"])) or ("NPC %s" % row["gate_npc"]),
                row["gate_favor"], cur_favor)
        elif row["gate_event"] == "接取条件满足":
            ready = row["cond_ok"] is True
            hint = "接取条件满足后自动触发"
        row["gate_ready"] = ready
        row["gate_hint"] = hint

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

    # 流水按“已提交某剧情选项”条件接取：没走那条选项的分支就是未选分支。
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

    def chain_root(row):
        seen, cur = {row["id"]}, row
        while cur["prev"] in by_id and cur["prev"] not in seen:
            seen.add(cur["id"])
            cur = by_id[cur["prev"]]
        return cur

    # 前置链传播：起点不可达或已选另一分支时，后续环同样走不到
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
            row["unreachable_text"] = "前置「%s」不可达：%s" % (blocked["name"], blocked["unreachable_text"])
            row["blocked_by"] = blocked["name"]
        elif missed is not None:
            row["branch_missed"] = True
            row["branch_chosen"] = missed["branch_chosen"]
            row["branch_via"] = missed["name"]
            if len(missed_names) > 1:
                row["branch_path"] = " › ".join(reversed(missed_names))

    for row in rows:
        if row["done"]:
            label, cls = row["state_name"], "ok"
        elif row["doing"]:
            label, cls = row["state_name"], ""
        elif row["unreachable"]:
            label, cls = "不可达", "warn"
        elif row["branch_missed"]:
            label, cls = "未选分支", ""
        elif row["cond_ok"] is False:
            label, cls = "条件不足", "warn"
        elif row["record_gap"]:
            label, cls = "后续已完成", "warn"
        elif row["prev"] and not row["prev_done"]:
            label, cls = "前置未完成", ""
        elif row["same_flow_done"]:
            label, cls = "疑似已跳过", "warn"
        elif row["gate_done"]:
            label, cls = "疑似已触发", "warn"
        elif row["gate_ready"]:
            label, cls = "疑似已触发", "warn"
        elif row["gate_names"] or row.get("gate_hint"):
            label, cls = "待触发", ""
        elif row["acq_source"] == 2 and (row.get("acq_dialogue") or row.get("acq_flows")):
            label, cls = "剧情接取", ""
        elif row["acq_source"] == 2:
            label, cls = "触发未知", ""
        elif row["acq_source"] == 1:
            label, cls = "可接取", "ok"
        else:
            label, cls = "未接取", ""
        row["status_label"], row["status_cls"] = label, cls
        root = chain_root(row)
        row["chain_root_id"], row["chain_root_name"] = root["id"], root["name"]
        row["chain_stalled"] = bool(not root["accepted"] and root is not row)
        if row["accepted"]:
            hint = ""
        elif row["unreachable"]:
            hint = row["unreachable_text"]
        elif row["branch_missed"]:
            if row.get("branch_via"):
                hint = "需要走「%s」分支，但已选「%s」" % (
                    row.get("branch_path") or row["branch_via"], row["branch_chosen"])
            else:
                hint = ("已选择另一条同名路线（%s）" if row["branch_chosen"] == row["name"]
                        else "已选择另一分支：%s") % row["branch_chosen"]
        elif row["cond_ok"] is False:
            hint = "接取条件：%s" % (row["cond_fail_text"] or row["cond_text"])
        elif row["record_gap"]:
            hint = "后续任务已完成，可能是自动跳过或记录缺失"
        elif row["prev"] and not row["prev_done"]:
            if row["chain_stalled"]:
                hint = "整条剧情线未开始，起点「%s」%s" % (root["name"], _start_text(root))
            else:
                hint = "需先完成：%s（%s）" % (row["prev_name"], row["prev_state_name"])
        elif row["same_flow_done"]:
            hint = "与「%s」由同一段剧情接取，可能是同源分支，也可能已完成但没留下记录" % row["same_flow_done"]
        elif row["gate_done"]:
            hint = "前置「%s」已完成但本环无记录，可能已触发过或记录缺失" % row["gate_names"]
        elif row["gate_ready"]:
            hint = "%s，但本环无记录，可能已触发过" % (row.get("gate_hint") or "触发条件已满足")
        elif row.get("gate_hint"):
            hint = row["gate_hint"]
        elif row["acq_source"] == 2 and row.get("acq_dialogue"):
            hint = "在剧情对话中接取（对话 %s）" % (row["acq_dialogue"].get("dialogue") or "")
        elif row["acq_source"] == 2:
            hint = "配置里没有触发条件，通常由剧情脚本或对话触发，游戏内没有固定入口"
        elif row["acq_source"] == 1:
            hint = "与委托人对话接取"
            if row["cond_text"]:
                hint += "，条件：%s" % row["cond_text"]
        else:
            hint = "接取方式未知"
        row["status_hint"] = hint

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
        "stones_todo": sum(r["reward_stone"] for r in reward_rows if not r["done"]),
        "stones_done": sum(r["reward_stone"] for r in reward_rows if r["done"]),
        "hidden": sum(1 for r in rows if r["hidden"]),
        "branch": sum(1 for r in rows if r["branch"]),
        "branches": _int((meta_obj.get("stats") or {}).get("branches")),
        "chains": _int((meta_obj.get("stats") or {}).get("chains")),
        "unreachable": sum(1 for r in rows if not r["done"] and r["unreachable"]),
        "unreachable_stones": sum(r["reward_stone"] for r in rows if not r["done"] and r["unreachable"]),
        "can_accept": sum(1 for r in rows if r["status_label"] == "可接取"),
        "waiting": sum(1 for r in rows if r["status_label"] == "待触发"),
        "cond_fail": sum(1 for r in rows if r["status_label"] == "条件不足"),
        "suspect": sum(1 for r in rows if r["status_label"] == "疑似已触发"),
        "dialogue": sum(1 for r in rows if r["status_label"] == "剧情接取"),
        "skipped": sum(1 for r in rows if r["status_label"] == "疑似已跳过"),
        "unknown": sum(1 for r in rows if r["status_label"] == "触发未知"),
        "blocked_prev": sum(1 for r in rows if r["status_label"] == "前置未完成"),
        "missed": sum(1 for r in rows if r["status_label"] == "未选分支"),
        "record_gap": sum(1 for r in rows if r["status_label"] == "后续已完成"),
        "worth": sum(1 for r in rows if not r["accepted"] and not r["unreachable"]
                     and not r.get("branch_missed") and r["rewards"]
                     and r["status_label"] in ("可接取", "待触发", "剧情接取", "前置未完成")),
        "blocked_by_prev": sum(1 for r in rows if r.get("blocked_by")),
        "player_layer": _int(layer),
        "player_realm": player_realm,
        "player_realm_name": realms.get(str(player_realm)) or "",
    }
    return {"rows": rows, "stats": stats, "groups": meta_obj.get("groups") or [],
            "chains": meta_obj.get("chains") or [], "branches": meta_obj.get("branches") or [],
            "edges": meta_obj.get("edges") or [],
            "diagnostics": meta_obj.get("diagnostics") or {},
            "egg_notes": egg_notes,
            "gate_diag": gate_diag,
            "attr_names": meta_obj.get("attr_names") or {},
            "realms": realms, "states": states}


def post(rows, state, original, path):
    if isinstance(rows, dict):
        rows["src"] = os.path.basename(original) if original else os.path.basename(path or "")
    return rows


def enrich(module, meta_obj, state=None):
    return module


def summary(module):
    stats = (module.get("rows") or {}).get("stats") or {}
    return "支线：%d 个，已完成 %d 个，进行中 %d 个，未接取 %d 个；带奖励 %d 个，当前不可达 %d 个" % (
        stats.get("total", 0), stats.get("done", 0), stats.get("doing", 0),
        stats.get("todo", 0), stats.get("with_rewards", 0), stats.get("unreachable", 0))
