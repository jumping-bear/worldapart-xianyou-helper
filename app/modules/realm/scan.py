# -*- coding: utf-8 -*-
"""境界修为扫描：当前境界、修为缺口、下一目标与材料持有情况。"""
from meta_update import _int


def meta(metadata):
    return (metadata or {}).get("realm") or {}


def prepare(game_dir):
    return None


def _bag_counts(bag):
    """背包条目计数：兼容 [索引, 条目] 列表与普通列表/字典。"""
    counts = {}

    def walk(node):
        if isinstance(node, dict):
            item_id = node.get("item_id", node.get("itemId"))
            if item_id is not None:
                try:
                    key = int(item_id)
                except (TypeError, ValueError):
                    return
                counts[key] = counts.get(key, 0) + int(node.get("count") or node.get("num") or 1)
                return
            for child in node.values():
                walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(bag.get("items") if isinstance(bag, dict) else bag)
    return counts


def _npc_holders(npcs, material_ids, limit=8):
    holders = {}
    for npc in (npcs or {}).values():
        if not isinstance(npc, dict):
            continue
        cfg = _int(npc.get("npcCfgId"))
        for item_id, count in _bag_counts(npc.get("bag")).items():
            if item_id not in material_ids:
                continue
            rows = holders.setdefault(item_id, [])
            if len(rows) >= limit:
                continue
            rows.append({"cfg": cfg, "count": count})
    return holders


def _auction_items(player, material_ids):
    auction = player.get("auction_component") or {}
    generated = auction.get("generated_reward_items") or {}
    out = {}
    for entry in generated.values():
        if not isinstance(entry, dict):
            continue
        item_id = _int(entry.get("item_id"))
        if item_id not in material_ids:
            continue
        out.setdefault(item_id, []).append({
            "venue": _int(entry.get("venue_id")),
            "qty": max(1, _int(entry.get("quantity"), 1)),
        })
    return out


def _material_state(meta_obj, counts, holders, auctions):
    state = {}
    for key, info in (meta_obj.get("materials") or {}).items():
        item_id = _int(info.get("id")) or _int(key)
        state[item_id] = {
            "id": item_id,
            "owned": counts.get(item_id, 0),
            "held": holders.get(item_id) or [],
            "auction": auctions.get(item_id) or [],
        }
    return state


def _with_state(mats, state):
    out = []
    for entry in mats or []:
        item_id = _int(entry.get("id"))
        info = state.get(item_id) or {}
        out.append({
            "id": item_id, "need": max(1, _int(entry.get("qty"), 1)),
            "owned": info.get("owned", 0),
            "held": info.get("held") or [],
            "auction": info.get("auction") or [],
        })
    return out


def _rate_info(realm):
    base = _int(realm.get("rate"))
    limit = _int(realm.get("optional_limit"))
    bonuses = sorted((_int(opt.get("bonus")) for opt in realm.get("optional") or []), reverse=True)
    top = bonuses[:limit] if limit > 0 else []
    max_rate = min(100, base + sum(top))
    methods = []
    for method in realm.get("methods") or []:
        need = _int(method.get("need"))
        methods.append({
            "name": method.get("name") or "突破方式",
            "need": need,
            "rate": min(100, base + sum(bonuses[:need])),
        })
    return {
        "base": base, "limit": limit, "max": max_rate,
        "optional": [{"id": _int(opt.get("id")), "bonus": _int(opt.get("bonus"))}
                     for opt in realm.get("optional") or []],
        "methods": methods,
    }


def _rewards(meta_obj, realm):
    layers = meta_obj.get("layers") or {}
    realms = {_int(row.get("id")): row for row in meta_obj.get("realms") or []}
    next_realm = realms.get(_int(realm.get("next")))
    if not next_realm:
        return None
    phases = meta_obj.get("phases") or {}
    current_phase = phases.get(str((realm.get("phases") or [0])[-1])) or {}
    current_layers = current_phase.get("layers") or []
    next_phase = phases.get(str((next_realm.get("phases") or [0])[0])) or {}
    next_layers = next_phase.get("layers") or []
    current = layers.get(str(current_layers[-1] if current_layers else 0)) or {}
    target = layers.get(str(next_layers[0] if next_layers else 0)) or {}
    delta = {}
    # 属性 id 由配置表决定，这里只跳过寿元（单独展示），其余新增属性自动带入。
    for key in sorted(set((current.get("attrs") or {})) | set((target.get("attrs") or {})),
                      key=lambda item: _int(item)):
        if str(key) == "999":
            continue
        before = _int((current.get("attrs") or {}).get(key))
        after = _int((target.get("attrs") or {}).get(key))
        if after != before:
            delta[str(key)] = after - before
    gains = realm.get("gains") or {}
    return {
        "realm": _int(next_realm.get("id")), "name": next_realm.get("name"),
        "path": _int(gains.get("path")), "spirit": _int(gains.get("spirit")),
        "lifespan": _int(target.get("lifespan")), "lifespan_now": _int(current.get("lifespan")),
        "delta": delta,
    }


def scan(obj, meta_obj, state=None):
    if not meta_obj or not meta_obj.get("layers"):
        return {}
    player = (obj or {}).get("playerModel") or {}
    combat = player.get("combat") or {}
    layer_id = _int(combat.get("cultivate_layer_id"))
    layer = (meta_obj.get("layers") or {}).get(str(layer_id))
    if not layer:
        return {"ok": False}
    phase = (meta_obj.get("phases") or {}).get(str(layer.get("phase"))) or {}
    realms = {_int(row.get("id")): row for row in meta_obj.get("realms") or []}
    realm = realms.get(_int(phase.get("realm"))) or {}

    exp = _int(combat.get("cultivate_exp"))
    need = _int(layer.get("exp"))
    reserve = _int(combat.get("cultivate_reserve_exp"))
    reserve_limit = _int(realm.get("reserve"))

    phases = meta_obj.get("phases") or {}
    realm_phases = [str(item) for item in realm.get("phases") or []]
    layers_in_phase = [str(item) for item in phase.get("layers") or []]
    last_in_phase = bool(layers_in_phase) and str(layer_id) == layers_in_phase[-1]
    last_phase = bool(realm_phases) and str(phase.get("id")) == realm_phases[-1]

    material_ids = {_int(key) for key in (meta_obj.get("materials") or {})}
    counts = _bag_counts(player.get("bag"))
    holders = _npc_holders((obj or {}).get("npcs") or {}, material_ids)
    auctions = _auction_items(player, material_ids)
    mat_state = _material_state(meta_obj, counts, holders, auctions)

    next_info = None
    if not last_in_phase:
        index = layers_in_phase.index(str(layer_id))
        next_layer_id = _int(layers_in_phase[index + 1]) if index + 1 < len(layers_in_phase) else 0
        next_layer = (meta_obj.get("layers") or {}).get(str(next_layer_id)) or {}
        next_info = {
            "kind": "layer", "label": "%s · %s 层" % (phase.get("name"), next_layer.get("layer")),
            "exp_need": need, "exp_have": exp, "materials": [],
            "note": "修为满即可升层，不需要材料",
        }
    elif last_phase and _int(realm.get("next")):
        rate = _rate_info(realm)
        next_info = {
            "kind": "realm", "label": "%s（境界突破）" % ((realms.get(_int(realm.get("next"))) or {}).get("name")),
            "exp_need": need, "exp_have": exp,
            "materials": _with_state(realm.get("mats"), mat_state),
            "rate": rate, "days": _int(realm.get("days")), "years": realm.get("years"),
            "battle": realm.get("battle"), "rewards": _rewards(meta_obj, realm),
            "note": "失败会倒退 1 层修为",
        }
    elif last_phase:
        next_info = {
            "kind": "cap", "label": "%s · 已达开放上限" % realm.get("name"),
            "exp_need": need, "exp_have": exp, "materials": [],
            "note": "当前版本没有更高境界",
        }
    else:
        realm_phase_ids = [str(item) for item in realm.get("phases") or []]
        current_index = realm_phase_ids.index(str(phase.get("id"))) \
            if str(phase.get("id")) in realm_phase_ids else -1
        next_phase = phases.get(realm_phase_ids[current_index + 1]) if 0 <= current_index + 1 < len(realm_phase_ids) else {}
        next_info = {
            "kind": "phase", "label": "%s（阶段突破）" % (next_phase.get("name") or "下一阶段"),
            "exp_need": need, "exp_have": exp,
            "materials": _with_state(phase.get("mats"), mat_state),
            "note": "修为满 + 阶段材料即可突破，无失败风险",
        }

    preview = None
    if _int(realm.get("next")):
        preview = {
            "label": "%s → %s" % (realm.get("name"), (realms.get(_int(realm.get("next"))) or {}).get("name")),
            "materials": _with_state(realm.get("mats"), mat_state),
            "rate": _rate_info(realm), "days": _int(realm.get("days")),
            "years": realm.get("years"), "battle": realm.get("battle"),
            "rewards": _rewards(meta_obj, realm),
        }

    phase_preview = None
    realm_phase_ids = [str(item) for item in realm.get("phases") or []]
    current_index = realm_phase_ids.index(str(phase.get("id"))) \
        if str(phase.get("id")) in realm_phase_ids else -1
    next_phase = phases.get(realm_phase_ids[current_index + 1]) if 0 <= current_index + 1 < len(realm_phase_ids) else {}
    if next_phase and phase.get("mats"):
        phase_preview = {
            "label": "%s → %s" % (phase.get("name"), next_phase.get("name")),
            "materials": _with_state(phase.get("mats"), mat_state),
            "note": "修为满 + 阶段材料即可突破，无失败风险",
        }

    # 当前阶段突破材料 + 当前境界助道灵物的妖兽刷新情况
    stage_block = phase_preview or preview
    stage_ids = {_int(entry.get("id")) for entry in (stage_block or {}).get("materials") or []}
    aux_ids = {_int(opt.get("id")) for opt in realm.get("optional") or []}
    monsters = None
    if stage_ids or aux_ids:
        monster_teams = meta_obj.get("monster_teams") or {}
        space_names = meta_obj.get("space_names") or {}
        stage_teams = {key: team for key, team in monster_teams.items()
                       if set(_int(m) for m in team.get("mats") or []) & stage_ids}
        # 助道灵物同样由妖兽掉落，单独统计，避免被当成阶段突破材料计入缺口。
        aux_teams = {key: team for key, team in monster_teams.items()
                     if set(_int(m) for m in team.get("mats") or []) & aux_ids}
        spaces = (obj or {}).get("spaces") or {}
        spawns = []
        aux_spawns = []
        rare_spawns = []
        refresh_dates = {}
        for uid, space in spaces.items():
            if not isinstance(space, dict):
                continue
            state = space.get("interactState") or {}
            cd = state.get("monster_born_cd_until")
            if isinstance(cd, dict):
                key = (_int(cd.get("year")), _int(cd.get("month")), _int(cd.get("day")))
                refresh_dates[key] = refresh_dates.get(key, 0) + 1
            monster = state.get("monster") or {}
            team_id = _int(monster.get("monster_team_id"))
            team_any = monster_teams.get(str(team_id))
            space_id = _int(space.get("spaceId"))
            space_name = space_names.get(str(space_id)) or "未识别地点"
            if team_any and team_any.get("rare"):
                rare_spawns.append({
                    "team": team_id, "name": team_any.get("name"), "rare": True,
                    "space": space_id, "space_name": space_name,
                    "mats": sorted(set(_int(m) for m in team_any.get("mats") or [])),
                })
            team = stage_teams.get(str(team_id))
            if team:
                spawns.append({
                    "team": team_id, "name": team.get("name"), "rare": bool(team.get("rare")),
                    "space": space_id, "space_name": space_name,
                    "mats": sorted(set(_int(m) for m in team.get("mats") or []) & stage_ids),
                })
            aux_team = aux_teams.get(str(team_id))
            if aux_team:
                aux_spawns.append({
                    "team": team_id, "name": aux_team.get("name"), "rare": bool(aux_team.get("rare")),
                    "space": space_id, "space_name": space_name,
                    "mats": sorted(set(_int(m) for m in aux_team.get("mats") or []) & aux_ids),
                })
        spawns.sort(key=lambda row: (0 if row.get("rare") else 1, row.get("space_name") or ""))
        rare_spawns.sort(key=lambda row: row.get("space_name") or "")
        aux_spawns.sort(key=lambda row: (0 if row.get("rare") else 1, row.get("space_name") or ""))
        teams = [{"id": team.get("id"), "name": team.get("name"), "rare": bool(team.get("rare")),
                  "weight": _int(team.get("weight")), "mats": sorted(
                      set(_int(m) for m in team.get("mats") or []) & stage_ids)}
                 for team in stage_teams.values()]
        teams.sort(key=lambda row: (0 if row.get("rare") else 1, row.get("id") or 0))
        aux_teams_out = [{"id": team.get("id"), "name": team.get("name"),
                          "rare": bool(team.get("rare")),
                          "weight": _int(team.get("weight")), "mats": sorted(
                              set(_int(m) for m in team.get("mats") or []) & aux_ids)}
                         for team in aux_teams.values()]
        aux_teams_out.sort(key=lambda row: (0 if row.get("rare") else 1, row.get("id") or 0))
        covered = set().union(*(set(team["mats"]) for team in teams)) if teams else set()
        aux_covered = set().union(*(set(team["mats"]) for team in aux_teams_out)) if aux_teams_out else set()
        refresh_until = ""
        if refresh_dates:
            day = max(refresh_dates, key=refresh_dates.get)
            if day[0] or day[1] or day[2]:
                refresh_until = "%d年%d月%d日" % day
        monsters = {
            "stage_label": (stage_block or {}).get("label") or "",
            "stage_mats": sorted(stage_ids),
            "spawns": spawns, "rare_spawns": rare_spawns,
            "teams": teams[:12],
            "missing": sorted(stage_ids - covered),
            "aux_mats": sorted(aux_ids),
            "aux_spawns": aux_spawns,
            "aux_teams": aux_teams_out[:12],
            "aux_covered": sorted(aux_covered),
            "refresh_until": refresh_until,
            "spawn_count": len(spawns),
        }

    spots = player.get("spirit_spot_runtime") or {}
    permanent = spots.get("permanent_spots") or {}
    current_spots = spots.get("spots") or {}
    spirit = {
        "reserve": reserve, "limit": reserve_limit,
        "permanent_count": len(permanent),
        "permanent_exp": sum(_int(v.get("absorbed_exp")) for v in permanent.values() if isinstance(v, dict)),
        "permanent_total": sum(_int(v.get("fixed_total_exp")) for v in permanent.values() if isinstance(v, dict)),
        "cycle_count": len(current_spots),
        "cycle_exp": sum(_int(v.get("absorbed_exp")) for v in current_spots.values() if isinstance(v, dict)),
        "cycle_total": sum(_int(v.get("fixed_total_exp")) for v in current_spots.values() if isinstance(v, dict)),
        "cycle_start_day": _int(spots.get("cycle_start_day")),
        "config": realm.get("spirit") or {},
    }

    notice = player.get("realm_breakthrough_notice") or {}
    last = None
    if notice.get("completed"):
        days = max(0, _int(notice.get("end_units")) - _int(notice.get("start_units"))) / 12.0
        last = {
            "days": round(days), "years": round(days / 365, 1),
            "friends": len(notice.get("friends") or []),
        }

    achievement = player.get("achievement_component") or {}
    quest_component = player.get("questComponent") or {}
    saved_quests = quest_component.get("quests") or {}
    quest_state = {}
    for key, value in saved_quests.items():
        try:
            quest_state[int(key)] = _int((value or {}).get("state"))
        except (TypeError, ValueError):
            continue
    missing = 0
    for entry in (next_info or {}).get("materials") or []:
        missing += max(0, entry["need"] - entry["owned"])

    return {
        "ok": True,
        "who": player.get("playerName") or "",
        "layer": layer, "phase": phase, "realm": realm,
        "exp": exp, "need": need,
        "pct": min(100, round(exp * 100.0 / need)) if need else 100,
        "reserve": reserve, "reserve_limit": reserve_limit,
        "blocked": {
            "phase": bool(combat.get("phase_breakthrough_blocked")),
            "realm": bool(combat.get("realm_breakthrough_blocked")),
        },
        "failure": {
            "streak": _int(achievement.get("consecutive_realm_breakthrough_failure_count")),
            "target": _int(achievement.get("realm_breakthrough_failure_target_realm_id")),
        },
        "next": next_info,
        "preview": preview,
        "phase_preview": phase_preview,
        "monsters": monsters,
        "spirit": spirit,
        "last": last,
        "materials": mat_state,
        "quest_state": quest_state,
        "missing": missing,
    }


def post(rows, state, original, path):
    return rows


def enrich(module, meta_obj, state=None):
    payload = module or {}
    data = payload.get("rows") if isinstance(payload.get("rows"), dict) else None
    if data is None:
        return payload
    module = dict(payload)
    module.update(data)
    if not module.get("ok"):
        return module
    catalog = meta_obj.get("materials") or {}
    npc_names = meta_obj.get("npc_names") or {}
    venues = meta_obj.get("venues") or {}
    current_ids = {entry["id"] for entry in (module.get("next") or {}).get("materials") or []}
    # 图鉴的“当前缺口”除了下一目标，还包括本境界突破和当前阶段突破要用的材料，
    # 这样即使当前只是在刷层，也能提前看到真正要准备的东西。
    focus = {}
    for block in (module.get("next"), module.get("preview")):
        for entry in (block or {}).get("materials") or []:
            focus[_int(entry.get("id"))] = max(1, _int(entry.get("need"), 1))
    for entry in (module.get("phase") or {}).get("mats") or []:
        focus.setdefault(_int(entry.get("id")), max(1, _int(entry.get("qty"), 1)))
    optional_ids = {_int(opt.get("id")) for opt in (module.get("realm") or {}).get("optional") or []}

    def decorate(entry):
        entry = dict(entry)
        entry["name"] = (catalog.get(str(entry["id"])) or {}).get("name") or "未识别物品"
        held = []
        for item in entry.get("held") or []:
            held.append({"cfg": item.get("cfg"), "count": item.get("count"),
                         "name": npc_names.get(str(item.get("cfg"))) or "未识别人物"})
        entry["held"] = held
        auction = []
        for item in entry.get("auction") or []:
            auction.append({"venue": venues.get(str(item.get("venue"))) or "未识别拍卖行",
                            "qty": item.get("qty")})
        entry["auction"] = auction
        return entry

    for key in ("next", "preview", "phase_preview"):
        block = module.get(key)
        if isinstance(block, dict):
            block["materials"] = [decorate(entry) for entry in block.get("materials") or []]

    materials = []
    for key, info in catalog.items():
        item_id = _int(key)
        state_row = (module.get("materials") or {}).get(item_id) or {}
        row = dict(info)
        row["owned"] = state_row.get("owned", 0)
        row["need"] = focus.get(item_id, 0)
        row["on_target"] = item_id in focus
        row["current"] = item_id in focus and row["owned"] < row["need"]
        row["optional"] = item_id in optional_ids
        row["held"] = []
        for item in state_row.get("held") or []:
            row["held"].append({"cfg": item.get("cfg"), "count": item.get("count"),
                                "name": npc_names.get(str(item.get("cfg"))) or "未识别人物"})
        row["auction"] = []
        for item in state_row.get("auction") or []:
            row["auction"].append({"venue": venues.get(str(item.get("venue"))) or "未识别拍卖行",
                                   "qty": item.get("qty")})
        state_names = meta_obj.get("quest_states") or {}
        saved = module.get("quest_state") or {}
        for source in row.get("sources") or []:
            quest_id = _int(source.get("quest"))
            if not quest_id:
                continue
            code = saved.get(quest_id, saved.get(str(quest_id)))
            source["state"] = code
            source["state_name"] = ("未接取" if code is None
                                    else ((state_names.get(str(code)) or ("状态 %s" % code))))
        materials.append(row)
    materials.sort(key=lambda row: (0 if row.get("current") else 1,
                                    0 if row.get("on_target") else 1,
                                    0 if row.get("optional") else 1,
                                    _int(row.get("realm")), _int(row.get("type")),
                                    -_int(row.get("quality")), row.get("id")))
    module["materials"] = materials
    module["focus_missing"] = sum(max(0, row["need"] - row["owned"]) for row in materials
                                   if row.get("on_target"))
    monsters = module.get("monsters")
    if isinstance(monsters, dict):
        def names(ids):
            return [(catalog.get(str(_int(item))) or {}).get("name") or "未识别物品" for item in ids or []]
        monsters["stage_mat_names"] = names(monsters.get("stage_mats"))
        monsters["missing_names"] = names(monsters.get("missing"))
        monsters["aux_mat_names"] = names(monsters.get("aux_mats"))
        monsters["aux_covered_names"] = names(monsters.get("aux_covered"))
        for key in ("spawns", "rare_spawns", "teams", "aux_spawns", "aux_teams"):
            for row in monsters.get(key) or []:
                row["mats_names"] = names(row.get("mats"))
    module["realms"] = meta_obj.get("realms") or []
    module["phases"] = meta_obj.get("phases") or {}
    module["layers"] = meta_obj.get("layers") or {}
    module["attr_names"] = meta_obj.get("attr_names") or {}
    module["type_labels"] = meta_obj.get("type_labels") or {}
    return module


def summary(module):
    if not module or not module.get("ok"):
        return "境界修为：暂无有效存档"
    next_info = module.get("next") or {}
    gap = max(0, _int(next_info.get("exp_need")) - _int(next_info.get("exp_have")))
    target = next_info.get("label") or "下一目标"
    missing = _int(module.get("focus_missing")) or _int(module.get("missing"))
    tail = "；待备 %d 件材料" % missing if missing else ""
    return "境界修为：%s · %s 层，修为 %d/%d；下一目标 %s（差 %d 修为）%s" % (
        (module.get("phase") or {}).get("name") or "?",
        (module.get("layer") or {}).get("layer") or "?",
        _int(module.get("exp")), _int(module.get("need")), target, gap, tail)
