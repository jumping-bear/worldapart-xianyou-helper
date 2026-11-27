# -*- coding: utf-8 -*-
"""宗门：配置表 → 模块快照。

数据来源（均已核对）：
    tbsect                 宗门基础信息、藏经阁兑换 NPC、入宗任务
    tbsectposition         职位、晋升所需宗门声望与境界、年俸、任务上限
    tbsectpositionquest    各宗门的晋升考核任务
    tbsecttaskpool         宗门任务池（贡献与声望奖励）
    tbsectpurchaseorder    灵材征收（收购委托）
    tbnpcbagrule           藏经阁兑换货架（scriptoriumContributionPrice）
    tbconditionexpr        兑换档位的职位条件（BASE_POS_GE_n）
    tbquest / tbrewarddrop 任务名与奖励（贡献、声望）
"""
import re

from meta_update import _int, _plain, _rows, _text, build_realms


# task_type 是玩法类型，不是业务分类。游戏 SectTaskType 枚举与
# SectDutyHallViewModel.BuildTaskCard 的映射为 1=HUNT/2=GATHER/3=SPAR/4=FETCH，
# 对应文案见 tbstrconfig.sect 的 DutyTaskTypeHunt/Gather/Spar/Fetch。
# 未知类型兜底为「宗门任务·类型N」，不硬编码新类型。
TASK_TYPES = {1: "讨伐", 2: "采集", 3: "切磋", 4: "寻物"}


def _task_type_name(task_type):
    """任务类型文案：已知类型用固定文案，未知类型兜底为「宗门任务·类型N」。"""
    return TASK_TYPES.get(task_type) or ("宗门任务·类型%d" % task_type)


def _rows_of(tables, key):
    value = tables.get(key)
    if isinstance(value, dict):
        value = value.get("rows") or []
    return [row for row in _rows(value) if isinstance(row, dict)]


def _npc_names(tables):
    names = {}
    for row in _rows_of(tables, "tbnpcbasecfg"):
        npc_id = _int(row.get("id"))
        if npc_id:
            names[npc_id] = _text(row.get("npcName")) or ("NPC %s" % npc_id)
    return names


def _quest_names(tables):
    names = {}
    for row in _rows_of(tables, "tbquest"):
        quest_id = _int(row.get("id"))
        if quest_id:
            names[quest_id] = _plain(row.get("name")) or ("任务 %s" % quest_id)
    return names


def _quest_objective_info(row):
    """从 tbquest 行解析目标/地点/目标物/数量/动作；无目标时返回空字典。

    已接的 [宗门] 任务与委托板任务共用这套解析，避免委托板只有任务名。
    """
    raw_texts = []
    for objective in row.get("objectives") or []:
        if isinstance(objective, dict):
            raw = _text(objective.get("description"))
            if raw:
                raw_texts.append(raw)
    if not raw_texts:
        return {}
    raw = raw_texts[0]
    highlights = [_plain(match) for match in
                  re.findall(r"<color=[^>]+>(.*?)</color>", raw, re.S)]
    places = [text for text in highlights if "." in text or "·" in text]
    location = "、".join(places)
    target = next((text for text in highlights if text not in places), "")
    if not places and highlights:
        location, target = highlights[0], (highlights[-1] if len(highlights) > 1 else "")
    objective = "；".join(_plain(text) for text in raw_texts)
    count = 0
    match = re.search(r"(?:采集|收集|击败|击杀|讨伐|提交|准备)\s*(\d+)\s*(?:个|只|名|位|株|份|枚|张)", objective)
    if match:
        count = int(match.group(1))
    quality = ""
    quality_match = re.search(r"[（(]([^）)]+品质)[）)]", objective)
    if quality_match:
        quality = quality_match.group(1)
    action = "其他"
    for keyword, label in (("采集", "采集"), ("采药", "采集"), ("收集", "收集"),
                           ("击败", "讨伐"), ("击杀", "讨伐"), ("除患", "讨伐"),
                           ("切磋", "切磋"), ("交谈", "访谈"), ("访谈", "访谈"),
                           ("赠礼", "赠礼"), ("亲密度", "赠礼"), ("好感度", "赠礼"),
                           ("筹备", "筹备"), ("提交", "提交"), ("前往", "前往")):
        if keyword in objective:
            action = label
            break
    return {
        "objective": objective, "location": location, "target": target,
        "count": count, "quality": quality, "action": action,
    }


def _duty_quests(tables):
    """已接取的宗门任务：[宗门] 开头的任务目标、地点、目标物与动作。

    这些任务不在 tbsecttaskpool 里（该表只用于委托板），只能从 tbquest 与
    存档 questComponent.quests 关联，否则界面会只看到委托板的 3 条。
    """
    out = {}
    for row in _rows_of(tables, "tbquest"):
        quest_id = _int(row.get("id"))
        name = _plain(row.get("name")) or ""
        if not quest_id or not name.startswith("[宗门]"):
            continue
        info = _quest_objective_info(row)
        out[str(quest_id)] = dict(info, name=name,
                                  objective=info.get("objective", ""),
                                  location=info.get("location", ""),
                                  target=info.get("target", ""),
                                  count=info.get("count", 0),
                                  quality=info.get("quality", ""),
                                  action=info.get("action", "其他"))
    return out


def _condition_aliases(tables):
    aliases = {}
    for row in _rows_of(tables, "tbconditionexpr"):
        alias = str(row.get("alias") or "")
        if alias:
            aliases[_int(row.get("id"))] = alias
    return aliases


def _position_need(alias):
    """BASE_POS_GE_3 → 3；其它条件返回 0。"""
    match = re.match(r"BASE_POS_GE_(\d+)$", alias or "")
    return int(match.group(1)) if match else 0


def _reward_items(tables):
    """tbRewardDrop：按物品 id 汇总灵石 / 宗门声望 / 城镇声望。"""
    items = {}
    for row in _rows_of(tables, "tbitem"):
        item_id = _int(row.get("id"))
        if item_id:
            items[item_id] = _plain(row.get("itemName")) or "未识别物品"
    drops = {}
    for row in _rows_of(tables, "tbrewarddrop"):
        drop_id = _int(row.get("id"))
        if not drop_id:
            continue
        entries = []
        for variant in row.get("variants") or []:
            if not isinstance(variant, dict):
                continue
            for entry in variant.get("dropList") or []:
                if isinstance(entry, dict) and _int(entry.get("itemId")):
                    entries.append((_int(entry.get("itemId")),
                                    _int(entry.get("itemCountMin"), 1),
                                    _int(entry.get("itemCountMax"), 1)))
        drops[drop_id] = entries
    return items, drops


def _sum_drop(entries, rep_map):
    """把掉落拆成灵石、宗门声望、其它物品。rep_map: itemId → ('sect'|'town', id)。"""
    stones, sect_rep, town_rep, extra = 0, {}, {}, []
    for item_id, low, high in entries:
        count = low if low == high else max(low, high)
        if item_id == 50000:
            stones += count
            continue
        target = rep_map.get(item_id)
        if target:
            kind, target_id = target
            bucket = sect_rep if kind == "sect" else town_rep
            bucket[target_id] = bucket.get(target_id, 0) + count
            continue
        extra.append({"item": item_id, "count": count})
    return stones, sect_rep, town_rep, extra


def build(tables):
    realms = build_realms(tables)
    item_names, drops = _reward_items(tables)
    quests = _quest_names(tables)
    quest_rows = {_int(row.get("id")): row for row in _rows_of(tables, "tbquest")}
    npcs = _npc_names(tables)
    aliases = _condition_aliases(tables)

    item_rows = {_int(row.get("id")): row for row in _rows_of(tables, "tbitem")}
    type_names = {_int(row.get("id")): _plain(row.get("typeName"))
                  for row in _rows_of(tables, "tbitemtype")}
    space_names = {_int(row.get("id")): _plain(row.get("spaceName"))
                   for row in _rows_of(tables, "tbspace")}

    # 声望货币：50009=玄一门声望 … 50018=世乐合欢声望；按名称匹配，避免硬编码偏移。
    sect_names = {_int(row.get("id")): _plain(row.get("sectName")) or ("宗门 %s" % row.get("id"))
                  for row in _rows_of(tables, "tbsect")}
    rep_map = {}
    for item_id, name in item_names.items():
        for sect_id, sect_name in sect_names.items():
            if name == sect_name + "声望":
                rep_map[item_id] = ("sect", sect_id)

    positions = []
    position_by_id = {}
    for row in _rows_of(tables, "tbsectposition"):
        position_id = _int(row.get("id"))
        level = _int(row.get("position_level"))
        item = {
            "id": position_id,
            "name": _plain(row.get("position_name")) or ("职位 %s" % position_id),
            "level": level,
            "realm": _int(row.get("required_realm_id")),
            "reputation": _int(row.get("required_sect_reputation")),
            "contribution": _int(row.get("required_contribution")),
            "promotable": bool(row.get("is_player_promotable")),
            "task_limit": _int(row.get("task_limit")),
            "salary": _int(row.get("annual_salary")),
            "purchase_limit": _int(row.get("purchase_limit")),
            "desc": _plain(row.get("position_desc")),
        }
        positions.append(item)
        position_by_id[position_id] = item
    positions.sort(key=lambda item: (item["level"], item["id"]))
    # 玩家可晋升的职位链由职位表 is_player_promotable 决定；其余职位（执事、首座、宗主等）只作职级展示。
    career = [item for item in positions if item.get("promotable")]

    # 境界 → 修炼层数：把每个境界的起始层数摊平成 {层数: 境界}，供存档侧判断。
    phases = {}
    for row in _rows_of(tables, "tbcultivaterealm"):
        realm_id = _int(row.get("id"))
        for phase in row.get("phases") or []:
            if _int(phase):
                phases[str(_int(phase))] = str(realm_id)

    pool = _rows_of(tables, "tbsecttaskpool")
    orders = _rows_of(tables, "tbsectpurchaseorder")
    promo_rows = _rows_of(tables, "tbsectpositionquest")

    # 藏经阁：按 NPC 收集带贡献价的兑换项。
    exchange_by_sect = {}
    for rule in _rows_of(tables, "tbnpcbagrule"):
        npc_id = _int(rule.get("npcId"))
        if not npc_id:
            continue
        for supply in rule.get("supplyItemList") or []:
            if not isinstance(supply, dict) or "scriptoriumContributionPrice" not in supply:
                continue
            item_id = _int(supply.get("itemId"))
            item = item_rows.get(item_id) or {}
            price = _int(supply.get("scriptoriumContributionPrice"))
            pos_need = _int(supply.get("previewRequiredPositionId")) \
                or _position_need(aliases.get(_int(supply.get("dealCondId")), ""))
            realm_need = _int(supply.get("previewRequiredRealmId"))
            type_id = _int(item.get("itemType"))
            group = "功法招式" if type_id in (3, 95) else "灵果灵物"
            entry = {
                "item": item_id,
                "name": item_names.get(item_id) or "未识别物品",
                "count": _int(supply.get("count"), 1),
                "price": price,
                "position": pos_need,
                "position_name": (position_by_id.get(pos_need) or {}).get("name", ""),
                "realm": realm_need,
                "realm_name": realms.get(str(realm_need), ""),
                "group": group,
                "type": type_names.get(type_id, ""),
                "quality": _int(item.get("quality")),
                "sort": _int(supply.get("dealSortId")),
                "npc": npc_id,
                "npc_name": npcs.get(npc_id, ""),
                "role": "",
            }
            exchange_by_sect.setdefault(npc_id, []).append(entry)

    sects = []
    warnings = []
    for row in _rows_of(tables, "tbsect"):
        sect_id = _int(row.get("id"))
        name = _plain(row.get("sectName")) or ("宗门 %s" % sect_id)
        low_npc = _int(row.get("scriptorium_low_npc_id"))
        high_npc = _int(row.get("scriptorium_high_npc_id"))
        exchange = []
        for role, npc_id in (("low", low_npc), ("high", high_npc)):
            for entry in exchange_by_sect.get(npc_id, []):
                entry = dict(entry)
                entry["role"] = role
                entry["npc_name"] = npcs.get(npc_id, "") or entry["npc_name"]
                exchange.append(entry)
        exchange.sort(key=lambda entry: (0 if entry["role"] == "low" else 1,
                                        -entry["sort"], entry["price"]))

        tasks = []
        for pool_row in pool:
            if sect_id not in [_int(value) for value in (pool_row.get("sect_ids") or [])]:
                continue
            drop_id = _int(pool_row.get("reward_drop_id"))
            stones, sect_rep, _town_rep, extra = _sum_drop(drops.get(drop_id) or [], rep_map)
            quest_id = _int(pool_row.get("quest_id"))
            task_type = _int(pool_row.get("task_type"))
            type_name = _task_type_name(task_type)
            difficulty = _int(pool_row.get("task_difficulty"), 1)
            # 委托板任务的目标/地点/动作与已接任务同源（tbquest.objectives）；
            # quest_id=0 的占位配置没有目标，也不在游戏抽选范围内，保持空字段。
            info = _quest_objective_info(quest_rows.get(quest_id) or {}) if quest_id else {}
            tasks.append({
                "id": _int(pool_row.get("id")),
                "quest": quest_id,
                "name": quests.get(quest_id) or ("%s·难度%d" % (type_name, difficulty)),
                "type": task_type,
                "type_name": type_name,
                "objective": info.get("objective", ""),
                "location": info.get("location", ""),
                "target": info.get("target", ""),
                "count": info.get("count", 0),
                "quality": info.get("quality", ""),
                "action": info.get("action", ""),
                "difficulty": difficulty,
                "min_position": _int(pool_row.get("min_position_level")),
                "min_position_name": (position_by_id.get(
                    _int(pool_row.get("min_position_level"))) or {}).get("name", ""),
                "contribution": _int(pool_row.get("reward_contribution")),
                "reputation": sect_rep.get(sect_id, 0),
                "stones": stones,
                "other": extra,
                "weight": _int(pool_row.get("weight")),
                "refresh_scope": _int(pool_row.get("refresh_scope")),
            })
        tasks.sort(key=lambda task: (task["difficulty"], -task["contribution"], task["id"]))

        purchases = []
        for order_row in orders:
            if sect_id not in [_int(value) for value in (order_row.get("sect_ids") or [])]:
                continue
            item_id = _int(order_row.get("item_id"))
            purchases.append({
                "id": _int(order_row.get("id")),
                "item": item_id,
                "name": item_names.get(item_id) or "未识别物品",
                "count": _int(order_row.get("demand_count"), 1),
                "contribution": _int(order_row.get("reward_contribution")),
                "reputation": _int(order_row.get("sect_reputation_reward")),
                "min_position": _int(order_row.get("min_position_level")),
                "min_position_name": (position_by_id.get(
                    _int(order_row.get("min_position_level"))) or {}).get("name", ""),
                "difficulty": _int(order_row.get("task_difficulty"), 1),
                "weight": _int(order_row.get("weight")),
            })
        purchases.sort(key=lambda order: (order["min_position"], order["id"]))

        promotions = []
        for promo in promo_rows:
            if _int(promo.get("sect_id")) != sect_id:
                continue
            position_id = _int(promo.get("position_id"))
            position = position_by_id.get(position_id) or {}
            quest_id = _int(promo.get("quest_id"))
            promotions.append({
                "position": position_id,
                "position_name": position.get("name") or ("职位 %s" % position_id),
                "reputation": position.get("reputation", 0),
                "realm": position.get("realm", 0),
                "realm_name": realms.get(str(position.get("realm", 0)), ""),
                "quest": quest_id,
                "quest_name": quests.get(quest_id, "") if quest_id else "",
                "completion_quest": _int(promo.get("completion_quest_id")),
                "salary": position.get("salary", 0),
                "task_limit": position.get("task_limit", 0),
            })
        promotions.sort(key=lambda item: item["position"])

        sects.append({
            "id": sect_id,
            "name": name,
            "short": _plain(row.get("short_name")),
            "region": _plain(row.get("region_text")),
            "desc": _plain(row.get("sectPrompt")),
            "feature": _plain(row.get("feature_text")),
            "join_quest": _int(row.get("join_quest_id")),
            "join_quest_name": quests.get(_int(row.get("join_quest_id")), ""),
            "headquarters": _int(row.get("headquarters_scene_id")),
            "headquarters_name": space_names.get(_int(row.get("headquarters_scene_id")), ""),
            "leader": _int(row.get("master_npc_id")),
            "leader_name": npcs.get(_int(row.get("master_npc_id")), ""),
            "low_npc": low_npc,
            "low_npc_name": npcs.get(low_npc, ""),
            "high_npc": high_npc,
            "high_npc_name": npcs.get(high_npc, ""),
            "playable": bool(exchange),
            "exchange": exchange,
            "exchange_total": sum(entry["price"] for entry in exchange),
            "tasks": tasks,
            "purchases": purchases,
            "promotions": promotions,
        })

    constants = {}
    for row in _rows_of(tables, "tbsectconstants"):
        for key, value in row.items():
            if isinstance(value, (int, float, str)):
                constants[key] = value
    # 灵石 id 按道具名派生，未来换 id 时不用改代码；找不到时保留旧回退值。
    stone_id = next((item_id for item_id, row in item_rows.items()
                     if _plain(row.get("itemName")) == "灵石"), 0)
    constants.setdefault("STONE_ITEM_ID", stone_id or 50000)

    return {
        "schema": 1,
        "realms": realms,
        "phases": phases,
        "positions": positions,
        "career": career,
        "constants": constants,
        "task_types": {str(key): value for key, value in TASK_TYPES.items()},
        "duty_quests": _duty_quests(tables),
        "sects": sects,
        "warnings": warnings,
    }
