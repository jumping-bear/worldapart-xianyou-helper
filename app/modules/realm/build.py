# -*- coding: utf-8 -*-
"""境界修为：配置表 → 模块快照。

只做“境界进度 + 突破条件 + 材料获取途径”，不复制全量配置：
* 境界/阶段/层、修为门槛、突破材料、成功率、耗时、验证战斗都从表里派生；
* 材料来源优先用游戏自带的 sourceRoutes，再由掉落表反推拍卖/赛事/镇劫/秘宝/商店/奇遇；
* 所有新材料（itemType 94/97/98）都会自动进入图鉴，后续版本新增内容无需改代码。
"""
from collections import defaultdict

from meta_update import SCHEMA, _int, _plain, _rows, _text, build_spaces

MATERIAL_TYPES = {94: "阶段灵物", 97: "境界灵物", 98: "助道灵物"}
TYPE_RANK = {97: 0, 94: 1, 98: 2}
QUEST_STATES = {0: "可接取", 1: "进行中", 2: "已完成", 3: "已提交", 4: "已失败", 5: "已放弃", 6: "待提交"}
SOURCE_RANK = {"official": 0, "quest": 1, "monster": 2, "auction": 3, "tournament": 4,
               "worldboss": 5, "explore": 6, "shop": 7, "event": 8, "steal": 9,
               "unknown": 10}
CONF_RANK = {"none": 0, "mechanic": 1, "derived": 2, "official": 3}


def _item_name(row):
    return _plain(row.get("itemName")) or "未识别物品"


def _pct(value):
    """把配置里的 0~1 概率转成百分数；字段缺失或换成字符串时也不会中断构建。"""
    try:
        return int(round(float(value) * 100))
    except (TypeError, ValueError):
        return 0


def _item_desc(row):
    return _plain(row.get("itemDesc"))


def _qty_list(raw):
    out = []
    for entry in raw or []:
        if not isinstance(entry, dict):
            continue
        item_id = _int(entry.get("type") if entry.get("type") is not None else entry.get("item_id"))
        if item_id:
            out.append({"id": item_id, "qty": max(1, _int(entry.get("value"), 1))})
    return out


def _drop_index(tables):
    drops = {str(_int(row.get("id"))): row
             for row in _rows(tables.get("tbrewarddrop")) if isinstance(row, dict)}
    memo = {}

    def resolve(drop_id, stack=()):
        key = str(_int(drop_id))
        if key in memo:
            return memo[key]
        if key in stack:
            return set()
        row = drops.get(key) or {}
        found = set()
        for variant in row.get("variants") or []:
            if not isinstance(variant, dict):
                continue
            for entry in variant.get("dropList") or []:
                if isinstance(entry, dict) and entry.get("itemId"):
                    found.add(_int(entry.get("itemId")))
            for entry in variant.get("rewardDropList") or []:
                if isinstance(entry, dict) and entry.get("rewardDropId"):
                    found |= resolve(entry.get("rewardDropId"), stack + (key,))
        memo[key] = found
        return found

    return resolve


def _route_data(tables):
    pois = {str(_int(row.get("id"))): _text(row.get("showName"))
            for row in _rows(tables.get("tbmappoi")) if isinstance(row, dict)}
    # trackType=2 指向丹方，取丹方名；取不到就只说「炼丹配方」，不外露配方编号。
    recipes = {str(_int(row.get("id"))): _text(row.get("name"))
               for row in _rows(tables.get("tbpillrecipe")) if isinstance(row, dict)}
    routes = {}
    for row in _rows(tables.get("tbsourceroute")):
        if not isinstance(row, dict):
            continue
        track_type = _int(row.get("trackType"))
        track_param = _int(row.get("trackParam"))
        detail = ""
        if track_type == 1:
            detail = pois.get(str(track_param), "")
        elif track_type == 2:
            detail = recipes.get(str(track_param), "") or "炼丹配方"
        routes[str(_int(row.get("id")))] = {
            "label": _plain(row.get("des")), "detail": detail}
    return routes


def _venue_names(tables):
    out = defaultdict(list)
    for row in _rows(tables.get("tbauctionvenue")):
        if not isinstance(row, dict):
            continue
        realm = _int(row.get("realm_id"))
        name = _text(row.get("venue_name"))
        if realm and name and name not in out[realm]:
            out[realm].append(name)
    return {realm: names[0] for realm, names in out.items()}


def _dungeon_names(tables):
    out = {}
    for row in _rows(tables.get("tbworldbossdungeon")):
        if isinstance(row, dict):
            out[str(_int(row.get("id")))] = _text(row.get("name"))
    return out


def _battle_info(tables):
    out = {}
    for row in _rows(tables.get("tbspecialbattle")):
        if not isinstance(row, dict):
            continue
        out[str(_int(row.get("id")))] = {
            "id": _int(row.get("id")),
            "turns": _int(row.get("pass_enemy_turns")),
            "invincible": bool(row.get("enemy_invincible")),
            "escape": bool(row.get("canEscape")),
        }
    return out


def _referenced_material_ids(tables):
    """突破配置里实际引用到的材料 id（不受 itemType 变化影响）。"""
    ids = set()
    for row in _rows(tables.get("tbcultivaterealm")):
        if not isinstance(row, dict):
            continue
        for entry in _qty_list(row.get("breakthrough_material")):
            ids.add(entry["id"])
        for pool in row.get("optional_material_pool") or []:
            if isinstance(pool, dict) and pool.get("item_id"):
                ids.add(_int(pool.get("item_id")))
    for row in _rows(tables.get("tbcultivatephase")):
        if isinstance(row, dict):
            for entry in _qty_list(row.get("breakthrough_material")):
                ids.add(entry["id"])
    return ids


def _attr_meta(tables):
    out = {}
    for row in _rows(tables.get("tbattribute")):
        if isinstance(row, dict) and row.get("id") is not None:
            out[_int(row.get("id"))] = {
                "name": _plain(row.get("name")) or ("属性%s" % row.get("id")),
                "format": _int(row.get("format")),
            }
    return out


def _attr_entries(raw, attr_meta):
    out = []
    for entry in raw or []:
        if not isinstance(entry, dict):
            continue
        attr_id = _int(entry.get("type"))
        value = entry.get("value")
        info = attr_meta.get(attr_id) or {}
        name = info.get("name") or ("属性%s" % attr_id)
        suffix = "%" if info.get("format") == 2 else ""
        number = ("%g" % value) if isinstance(value, (int, float)) else str(value)
        out.append({"id": attr_id, "name": name, "value": value,
                    "format": info.get("format"),
                    "text": "%s +%s%s" % (name, number, suffix)})
    return out


def _used_by(tables, material_ids, attr_meta=None):
    used = defaultdict(list)

    def add(mats, entry):
        for item in mats:
            if item["id"] in material_ids:
                used[item["id"]].append(dict(entry))

    realms = sorted((row for row in _rows(tables.get("tbcultivaterealm")) if isinstance(row, dict)),
                    key=lambda r: _int(r.get("id")))
    realm_name = {_int(row.get("id")): _plain(row.get("realm_name")) for row in realms}
    for row in realms:
        realm_id = _int(row.get("id"))
        next_id = _int(row.get("next_realm"))
        label = ("%s → %s" % (realm_name.get(realm_id), realm_name.get(next_id))
                 if next_id and next_id in realm_name else "%s（当前上限）" % realm_name.get(realm_id))
        add(_qty_list(row.get("breakthrough_material")),
            {"kind": "realm", "label": label, "realm": realm_id})
        for pool in row.get("optional_material_pool") or []:
            if not isinstance(pool, dict):
                continue
            item_id = _int(pool.get("item_id"))
            if item_id in material_ids:
                bonus = _pct(pool.get("success_rate_bonus"))
                used[item_id].append({
                    "kind": "optional", "realm": realm_id, "bonus": bonus,
                    "label": "%s 突破辅材 +%d%%" % (realm_name.get(realm_id), bonus),
                    "attrs": _attr_entries(pool.get("attr_bonuses"), attr_meta or {}),
                })

    phases = [row for row in _rows(tables.get("tbcultivatephase")) if isinstance(row, dict)]
    by_realm = defaultdict(list)
    for row in phases:
        by_realm[_int(row.get("realm"))].append(row)
    for rows in by_realm.values():
        rows.sort(key=lambda r: _int(r.get("id")))
        for index, row in enumerate(rows):
            nxt = rows[index + 1] if index + 1 < len(rows) else None
            label = ("%s → %s" % (_plain(row.get("phase_name")), _plain(nxt.get("phase_name")))
                     if nxt else "%s（本境界最后一阶段）" % _plain(row.get("phase_name")))
            add(_qty_list(row.get("breakthrough_material")),
                {"kind": "phase", "label": label, "phase": _int(row.get("id"))})
    return used


def _call_args(spec, key="arguments"):
    out = []
    for arg in spec.get(key) or []:
        if not isinstance(arg, list) or not arg:
            continue
        if arg[0] == "int":
            out.append(_int(arg[1].get("value")))
        elif arg[0] == "list":
            for element in arg[1].get("elements") or []:
                if isinstance(element, list) and element and element[0] == "int":
                    out.append(_int(element[1].get("value")))
    return out


def _call_name(spec):
    head = spec.get("func") or []
    if not head:
        return ""
    if head[0] == "variable":
        return str((head[1] or {}).get("name") or "")
    if head[0] == "index":
        owner = head[1].get("target") or []
        owner_name = owner[1].get("name") if isinstance(owner, list) and len(owner) > 1 else ""
        index = head[1].get("index") or []
        key = index[1].get("value") if isinstance(index, list) and len(index) > 1 else ""
        return ("%s.%s" % (owner_name, key)) if owner_name else str(key or "")
    return ""


def _walk_calls(node, out):
    if isinstance(node, dict):
        if "target" in node and "arguments" in node:
            name = _call_name(node)
            if name:
                out.append((name, _call_args(node)))
        if isinstance(node.get("func"), list):
            name = _call_name(node)
            if name:
                out.append((name, _call_args(node)))
        for value in node.values():
            _walk_calls(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk_calls(value, out)


def _quest_flow_drops(flows, start, resolve):
    """跟随任务流水，取出「获得奖励」引用的掉落表。"""
    seen, queue, drops = set(), [_int(start)], set()
    while queue and len(seen) < 80:
        flow_id = queue.pop(0)
        if flow_id in seen:
            continue
        seen.add(flow_id)
        flow = flows.get(flow_id) or {}
        calls = []
        _walk_calls(flow.get("action"), calls)
        for name, args in calls:
            if name.rsplit(".", 1)[-1] == "获得奖励" and args:
                drops.add(_int(args[0]))
        for nxt in flow.get("nextIds") or []:
            queue.append(_int(nxt))
    return drops


def _monster_catalog(tables, material_ids, resolve):
    """妖兽队伍 → 掉落材料；只保留会掉突破材料的队伍。"""
    monsters = {}
    for row in _rows(tables.get("tbmonster")):
        if isinstance(row, dict) and row.get("id") is not None:
            monsters[_int(row.get("id"))] = _plain(row.get("name")) or "未识别妖兽"
    out = {}
    for row in _rows(tables.get("tbmonsterteam")):
        if not isinstance(row, dict):
            continue
        mats = sorted(resolve(row.get("drop")) & material_ids)
        if not mats:
            continue
        names = [monsters.get(_int(mid)) for mid in row.get("monsters") or [] if monsters.get(_int(mid))]
        name = "、".join(names) or "未识别妖兽队伍"
        out[str(_int(row.get("id")))] = {
            "id": _int(row.get("id")), "name": name,
            "rare": bool(row.get("isRare")), "boss": bool(row.get("isBoss")),
            "realm": _int(row.get("realm_id")), "phase": _int(row.get("phase")),
            "weight": _int(row.get("refresh_weight")), "mats": mats,
        }
    return out


def _space_names(tables):
    out = {}
    for space_id, info in build_spaces(tables).items():
        name = info.get("name") or "未识别地点"
        region = info.get("region") or ""
        out[space_id] = ("%s·%s" % (region, name)) if region and region != name else name
    return out


def _sources(tables, material_ids, monster_teams=None):
    resolve = _drop_index(tables)
    routes = _route_data(tables)
    venues = _venue_names(tables)
    dungeons = _dungeon_names(tables)
    items = {_int(row.get("id")): row for row in _rows(tables.get("tbitem")) if isinstance(row, dict)}
    npc_names = {_int(row.get("id")): _text(row.get("npcName"))
                 for row in _rows(tables.get("tbnpcbasecfg")) if isinstance(row, dict)}
    sources = defaultdict(list)
    seen = set()

    def add(item_id, kind, label, detail="", conf="derived", extra=None):
        if item_id not in material_ids or not label:
            return
        key = (item_id, kind, label, detail)
        if key in seen:
            return
        seen.add(key)
        entry = {"kind": kind, "label": label, "detail": detail, "conf": conf}
        if extra:
            entry.update(extra)
        sources[item_id].append(entry)

    # 1) 游戏自带的物品获取途径
    for item_id in material_ids:
        row = items.get(item_id) or {}
        for route_id in row.get("sourceRoutes") or []:
            info = routes.get(str(_int(route_id))) or {}
            label = info.get("label") or "未识别途径"
            detail = info.get("detail") or ""
            if detail and detail in label:
                detail = ""
            add(item_id, "official", label, detail, "official")

    # 2) 拍卖会：按境界池 → 掉落表
    for row in _rows(tables.get("tbauctionitempool")):
        if not isinstance(row, dict) or _int(row.get("generate_type")) != 2:
            continue
        realm = _int(row.get("realm_id"))
        venue = venues.get(realm) or ("境界%s拍卖会" % realm)
        for item_id in resolve(row.get("type_param1")):
            add(item_id, "auction", venue, "境界%s 拍品" % realm)

    # 3) 赛事排名奖励
    for row in _rows(tables.get("tbtournamentreward")):
        if not isinstance(row, dict):
            continue
        label = _plain(row.get("display_name")) or ("第%s名奖励" % row.get("reward_rank"))
        for item_id in resolve(row.get("reward_drop_id")):
            add(item_id, "tournament", "赛事排名奖励", label)

    # 4) 镇劫之役奖励
    for row in _rows(tables.get("tbworldbossrewardtier")):
        if not isinstance(row, dict):
            continue
        dungeon = dungeons.get(str(_int(row.get("dungeon_id")))) or "镇劫之役"
        label = _plain(row.get("label")) or ""
        detail = label or ("第%s名" % row.get("rank_min"))
        for item_id in resolve(row.get("reward_drop_id")):
            add(item_id, "worldboss", "镇劫之役 · %s" % dungeon, detail)

    # 5) 诸天开藏的“大秘宝”
    for row in _rows(tables.get("tbsceneexploration")):
        if not isinstance(row, dict):
            continue
        name = _plain(row.get("explorationName")) or "探索点"
        for drop_id in row.get("treasure_drops") or []:
            for item_id in resolve(drop_id):
                add(item_id, "explore", "诸天开藏 · 大秘宝",
                    "" if name in "诸天开藏 · 大秘宝" else name)

    # 6) 商店供应
    for row in _rows(tables.get("tbnpcbagrule")):
        if not isinstance(row, dict):
            continue
        npc = npc_names.get(_int(row.get("npcId"))) or ""
        for entry in row.get("supplyItemList") or []:
            if not isinstance(entry, dict):
                continue
            item_id = _int(entry.get("itemId"))
            if item_id in material_ids:
                add(item_id, "shop", "商店供应", npc)

    # 7) 奇遇结局（带上奇遇名，材料页可以直接跳到奇遇页对应卡片）
    quest_table = tables.get("tbquest")
    quest_rows = quest_table.get("rows") if isinstance(quest_table, dict) else quest_table
    quest_names = {_int(row.get("id")): _plain(row.get("name"))
                   for row in _rows(quest_rows) if isinstance(row, dict)
                   and row.get("id") is not None}
    for row in _rows(tables.get("tbrandomeventending")):
        if not isinstance(row, dict):
            continue
        title = _plain(row.get("title")) or "未记录结局"
        event_id = _int(row.get("event_quest_id"))
        event_name = quest_names.get(event_id) or ""
        for item_id in resolve(row.get("reward_drop_id")):
            add(item_id, "event", "奇遇结局 · %s" % title, "", "derived",
                {"quest": event_id, "quest_name": event_name,
                 "link": bool(event_name), "link_module": "event"})

    # 8) 具体任务：主线 / 支线 / 红尘 / 隐藏 / 委托 等
    quest_types = {}
    for row in _rows(tables.get("tbquesttype")):
        if isinstance(row, dict) and row.get("id") is not None:
            quest_types[_int(row.get("id"))] = _plain(row.get("text")).strip("[]【】 ")
    flows = {_int(row.get("id")): row
             for row in _rows(tables.get("tbgameactionflow")) if isinstance(row, dict)}
    for row in _rows(quest_rows):
        if not isinstance(row, dict):
            continue
        found = set()
        if row.get("rewardId"):
            found |= resolve(row.get("rewardId"))
        for objective in row.get("objectives") or []:
            if isinstance(objective, dict) and objective.get("rewardId"):
                found |= resolve(objective.get("rewardId"))
        for field in ("questSubmitFlowId", "questAcqFlowId"):
            if row.get(field):
                for drop_id in _quest_flow_drops(flows, row.get(field), resolve):
                    found |= resolve(drop_id)
        rewards = found & material_ids
        if not rewards:
            continue
        kind = quest_types.get(_int(row.get("type"))) or "任务"
        name = _plain(row.get("name")) or "未识别任务"
        module = "hongchen" if "红尘" in kind else ("quest" if "支线" in kind else "")
        for item_id in rewards:
            add(item_id, "quest", "%s · %s" % (kind, name), "", "derived",
                {"quest": _int(row.get("id")), "quest_name": name, "link": bool(module),
                 "link_module": module})

    # 9) 妖兽：具体哪些怪物队伍会掉（稀有 / 普通）
    for team in (monster_teams or {}).values():
        for item_id in team.get("mats") or []:
            add(item_id, "monster", team.get("name"),
                "稀有妖兽" if team.get("rare") else "普通妖兽", "derived",
                {"team": team.get("id"), "rare": bool(team.get("rare"))})

    # 10) 偷窃机制：任何材料都可能从持有它的 NPC 身上偷到
    steals = {str(_int(row.get("id"))): row
              for row in _rows(tables.get("tbsteal")) if isinstance(row, dict)}
    for item_id in material_ids:
        row = steals.get(str(item_id))
        if not row:
            continue
        rate = _pct(row.get("rate_base"))
        add(item_id, "steal", "可偷窃", "基础成功率 %d%%（需 NPC 持有）" % rate, "mechanic")

    # 9) 官方只写了「任务获得」但任务表找不到具体奖励的，补一句提示，避免玩家空找
    for item_id in material_ids:
        rows = sources.get(item_id) or []
        if any(row.get("kind") == "quest" for row in rows):
            continue
        for row in rows:
            if row.get("kind") == "official" and "任务" in (row.get("label") or "") \
                    and not row.get("detail"):
                row["detail"] = "任务表未找到具体奖励"

    # 10) 没有“正常玩法来源”的，明确提示，避免玩家白找（只剩偷窃不算稳定来源）
    for item_id in material_ids:
        rows = sources.get(item_id) or []
        if not any(row.get("conf") in ("official", "derived") for row in rows):
            sources[item_id].append({
                "kind": "unknown", "label": "游戏未标注来源",
                "detail": "当前配置里没有可获取途径，可能尚未投放", "conf": "none"})

    for item_id, rows in sources.items():
        rows.sort(key=lambda s: (SOURCE_RANK.get(s["kind"], 8), s["label"]))
    return sources


def _best_conf(rows):
    best = "none"
    for row in rows:
        conf = row.get("conf") or "none"
        if CONF_RANK.get(conf, 0) > CONF_RANK.get(best, 0):
            best = conf
    return best


def _material_catalog(tables, used, sources, material_ids):
    catalog = {}
    type_names = {_int(row.get("id")): _text(row.get("typeName"))
                  for row in _rows(tables.get("tbitemtype")) if isinstance(row, dict)}
    for row in _rows(tables.get("tbitem")):
        if not isinstance(row, dict):
            continue
        item_id = _int(row.get("id"))
        if item_id not in material_ids:
            continue
        item_type = _int(row.get("itemType"))
        rows = sorted(used.get(item_id) or [], key=lambda x: (0 if x.get("kind") != "optional" else 1,
                                                              x.get("label") or ""))
        catalog[str(item_id)] = {
            "id": item_id, "name": _item_name(row), "desc": _item_desc(row),
            "type": item_type,
            "type_label": type_names.get(item_type) or MATERIAL_TYPES.get(item_type) or "突破材料",
            "quality": _int(row.get("quality")), "price": _int(row.get("price")),
            "realm": _int(row.get("cultivateRealm")), "req": _int(row.get("required_cultivation")),
            "used": rows,
            "sources": sources.get(item_id) or [],
            "best_conf": _best_conf(sources.get(item_id) or []),
            "has_source": any(row.get("conf") in ("official", "derived")
                              for row in sources.get(item_id) or []),
        }
    return catalog


def build(tables):
    realm_rows = sorted((row for row in _rows(tables.get("tbcultivaterealm")) if isinstance(row, dict)),
                        key=lambda r: _int(r.get("id")))
    phase_rows = sorted((row for row in _rows(tables.get("tbcultivatephase")) if isinstance(row, dict)),
                        key=lambda r: _int(r.get("id")))
    layer_rows = sorted((row for row in _rows(tables.get("tbcultivatelayer")) if isinstance(row, dict)),
                        key=lambda r: _int(r.get("id")))
    if not realm_rows or not phase_rows or not layer_rows:
        raise ValueError("境界配置为空")

    item_rows = [row for row in _rows(tables.get("tbitem")) if isinstance(row, dict)]
    material_ids = {_int(row.get("id")) for row in item_rows
                    if _int(row.get("itemType")) in MATERIAL_TYPES}
    # 配置里实际引用的材料也纳入图鉴：即使游戏以后改了 itemType 也不会漏。
    material_ids |= _referenced_material_ids(tables)
    attr_meta = _attr_meta(tables)
    used = _used_by(tables, material_ids, attr_meta)
    resolve = _drop_index(tables)
    monster_teams = _monster_catalog(tables, material_ids, resolve)
    sources = _sources(tables, material_ids, monster_teams)
    catalog = _material_catalog(tables, used, sources, material_ids)

    battles = _battle_info(tables)
    realms = []
    for row in realm_rows:
        days = [_int(x) for x in row.get("cost_days") or [] if _int(x)]
        battle = battles.get(str(_int(row.get("validation_battle_id"))))
        methods = []
        for method in row.get("breakthrough_methods") or []:
            if isinstance(method, dict):
                methods.append({
                    "name": _plain(method.get("method_name")) or "突破方式",
                    "need": _int(method.get("required_optional_material_count")),
                })
        optional = []
        for pool in row.get("optional_material_pool") or []:
            if isinstance(pool, dict) and pool.get("item_id"):
                optional.append({"id": _int(pool.get("item_id")),
                                 "bonus": _pct(pool.get("success_rate_bonus")),
                                 "attrs": _attr_entries(pool.get("attr_bonuses"), attr_meta)})
        realms.append({
            "id": _int(row.get("id")), "name": _plain(row.get("realm_name")),
            "phases": [_int(x) for x in row.get("phases") or []],
            "next": _int(row.get("next_realm")),
            "mats": _qty_list(row.get("breakthrough_material")),
            "optional": optional,
            "optional_limit": _int(row.get("optional_material_limit")),
            "rate": _pct(row.get("base_breakthrough_rate")),
            "days": days[0] if days else 0,
            "years": round((days[0] if days else 0) / 365, 1),
            "battle": battle,
            "reserve": _int(row.get("cultivate_reserve_exp_limit")),
            "root_cap": _int(row.get("spirit_root_cap")),
            "gains": {"path": _int(row.get("path_point_gain")),
                      "spirit": _int(row.get("spirit_point_gain"))},
            "spirit": {
                "total": _int(row.get("spirit_total_exp")),
                "drag": _int(row.get("spirit_exp_per_drag")),
                "full_days": _int(row.get("spirit_full_absorb_days")),
                "min": _int(row.get("spirit_spot_count_min")),
                "max": _int(row.get("spirit_spot_count_max")),
            },
            "methods": methods,
        })

    phases = {}
    for row in phase_rows:
        phases[str(_int(row.get("id")))] = {
            "id": _int(row.get("id")), "name": _plain(row.get("phase_name")),
            "realm": _int(row.get("realm")),
            "layers": [_int(x) for x in row.get("layers") or []],
            "mats": _qty_list(row.get("breakthrough_material")),
            "path_gain": _int(row.get("path_point_gain")),
        }

    layers = {}
    for row in layer_rows:
        attrs = {}
        for attr in row.get("attrs") or []:
            if isinstance(attr, dict):
                attrs[str(_int(attr.get("type")))] = attr.get("value")
        layers[str(_int(row.get("id")))] = {
            "id": _int(row.get("id")), "phase": _int(row.get("phase")),
            "layer": _int(row.get("layer")),
            "exp": _int(row.get("next_level_exp")),
            "lifespan": _int(attrs.get("999")),
            "attrs": {key: attrs[key] for key in ("4", "2", "3", "8") if key in attrs},
        }

    attr_names = {}
    for row in _rows(tables.get("tbattribute")):
        if isinstance(row, dict) and row.get("id") is not None:
            attr_names[str(_int(row.get("id")))] = _plain(row.get("name"))
    npc_names = {}
    for row in _rows(tables.get("tbnpcbasecfg")):
        if isinstance(row, dict) and row.get("id") is not None:
            npc_names[str(_int(row.get("id")))] = _text(row.get("npcName")) or "未识别人物"
    venues = {}
    for row in _rows(tables.get("tbauctionvenue")):
        if isinstance(row, dict) and row.get("id") is not None:
            venues[str(_int(row.get("id")))] = _text(row.get("venue_name")) or "未识别拍卖行"

    return {
        "schema": SCHEMA,
        "realms": realms, "phases": phases, "layers": layers,
        "materials": catalog, "attr_names": attr_names, "npc_names": npc_names,
        "venues": venues,
        "monster_teams": monster_teams,
        "space_names": _space_names(tables),
        "quest_states": {str(key): value for key, value in QUEST_STATES.items()},
        "type_labels": {str(key): value for key, value in MATERIAL_TYPES.items()},
    }
