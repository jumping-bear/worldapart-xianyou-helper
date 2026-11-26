# -*- coding: utf-8 -*-
"""城镇声望：配置表 → 模块快照。

数据来源（均已核对）：
    tbtown                    城镇与城镇声望 id
    tbcityreputation          城镇声望上下限
    tbreputationtitle         城镇称号档位（titleType=2）
    tbnpcbagrule              城镇货架（带 CITY_<城镇>_REP_GE_<阈值> 条件）
    tbconditionexpr           货架门槛
    tbcommissionforce         委托势力（force_type=1 → 城镇）
    tbcommissionforcetaskrefresh 可刷新委托的城镇与刷新条数
    tbcommissiontaskpool      委托池、难度、奖励掉落
    tbrewarddrop / tbitem     灵石与城镇声望奖励
    tbquest                   委托名称
"""
import re

from meta_update import _int, _plain, _rows, _text


def _rows_of(tables, key):
    value = tables.get(key)
    if isinstance(value, dict):
        value = value.get("rows") or []
    return [row for row in _rows(value) if isinstance(row, dict)]


def _quest_index(tables, npcs):
    """委托详情：名称、目标文本、地点、目标物/怪物/NPC、数量与动作类型。"""
    index = {}
    for row in _rows_of(tables, "tbquest"):
        quest_id = _int(row.get("id"))
        if not quest_id:
            continue
        raw_texts, submit_npc = [], 0
        for objective in row.get("objectives") or []:
            if not isinstance(objective, dict):
                continue
            raw = _text(objective.get("description"))
            if raw:
                raw_texts.append(raw)
            if _int(objective.get("submitNpcID")):
                submit_npc = _int(objective.get("submitNpcID"))
        raw = raw_texts[0] if raw_texts else ""
        highlights = [_plain(match) for match in
                      re.findall(r"<color=[^>]+>(.*?)</color>", raw, re.S)]
        places = [text for text in highlights if "." in text or "·" in text]
        location = "、".join(places)
        target = next((text for text in highlights if text not in places), "")
        if not places and highlights:
            location, target = highlights[0], (highlights[-1] if len(highlights) > 1 else "")
        objective = "；".join(_plain(text) for text in raw_texts)
        count = 0
        match = re.search(r"(?:采集|收集|击败|击杀|讨伐|交付|护送|寻找)\s*(\d+)\s*(?:个|只|名|位|株|份|张)", objective)
        if match:
            count = int(match.group(1))
        quality = ""
        quality_match = re.search(r"[（(]([^）)]+品质)[）)]", objective)
        if quality_match:
            quality = quality_match.group(1)
        action = "其他"
        for keyword, label in (("采集", "采集"), ("采药", "采集"), ("收集", "收集"),
                               ("击败", "讨伐"), ("击杀", "讨伐"), ("讨伐", "讨伐"), ("除患", "讨伐"),
                               ("切磋", "切磋"), ("交谈", "访谈"), ("访谈", "访谈"),
                               ("打听", "访谈"), ("询问", "访谈"),
                               ("疏经导脉", "行医"), ("行医", "行医"),
                               ("赠礼", "赠礼"), ("亲密度", "赠礼"),
                               ("炼制", "炼制"), ("筹备", "筹备"),
                               ("交付", "交付"), ("送达", "交付"), ("护送", "交付")):
            if keyword in objective:
                action = label
                break
        if action == "切磋" and not count:
            count = 1
        index[quest_id] = {
            "name": _plain(row.get("name")) or ("委托 %s" % quest_id),
            "objective": objective,
            "location": location,
            "target": target,
            "count": count,
            "quality": quality,
            "action": action,
            "submit_npc": submit_npc,
            "submit_npc_name": npcs.get(submit_npc, ""),
        }
    return index


def _npc_names(tables):
    names = {}
    for row in _rows_of(tables, "tbnpcbasecfg"):
        npc_id = _int(row.get("id"))
        if npc_id:
            names[npc_id] = _text(row.get("npcName")) or ("NPC %s" % npc_id)
    return names


def _item_index(tables):
    items = {}
    for row in _rows_of(tables, "tbitem"):
        item_id = _int(row.get("id"))
        if item_id:
            items[item_id] = {
                "name": _plain(row.get("itemName")) or "未识别物品",
                "type": _int(row.get("itemType")),
                "quality": _int(row.get("quality")),
                "price": _int(row.get("price")),
            }
    return items


def _drops(tables):
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
    return drops


def _city_condition(aliases, cond_id):
    """CITY_120_REP_GE_800 → (120, 800)。"""
    alias = aliases.get(_int(cond_id), "")
    match = re.match(r"CITY_(\d+)_REP_GE_(\d+)$", alias)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _sum_drop(entries, rep_by_item):
    stones, reputation, other = 0, {}, []
    for item_id, low, high in entries:
        count = low if low == high else max(low, high)
        if item_id == 50000:
            stones += count
        elif item_id in rep_by_item:
            town_id = rep_by_item[item_id]
            reputation[town_id] = reputation.get(town_id, 0) + count
        else:
            other.append({"item": item_id, "count": count})
    return stones, reputation, other


def build(tables):
    items = _item_index(tables)
    npcs = _npc_names(tables)
    quests = _quest_index(tables, npcs)
    drops = _drops(tables)
    aliases = {_int(row.get("id")): str(row.get("alias") or "")
               for row in _rows_of(tables, "tbconditionexpr")}

    towns = []
    for row in _rows_of(tables, "tbtown"):
        town_id = _int(row.get("id"))
        towns.append({
            "id": town_id,
            "name": _plain(row.get("townName")) or ("城镇 %s" % town_id),
            "desc": _plain(row.get("townDesc")),
            "order": _int(row.get("displayOrder")),
            "reputation_id": _int(row.get("townReputationId")),
        })
    town_by_id = {item["id"]: item for item in towns}

    # 城镇声望货币：50005=临州声望 …；按“城镇名+声望”匹配。
    rep_by_item, item_by_town = {}, {}
    for item_id, item in items.items():
        name = item["name"]
        if item["type"] != 5 or not name.endswith("声望"):
            continue
        town_name = name[:-2]
        for town in towns:
            if town["name"] == town_name:
                rep_by_item[item_id] = town["id"]
                item_by_town[town["id"]] = item_id
                break

    # 货架：同一城镇可能配置在多个 NPC 上，按 (城镇, 门槛) 合并。
    shelf_tiers = {}
    shelf_npcs = {}
    for rule in _rows_of(tables, "tbnpcbagrule"):
        npc_id = _int(rule.get("npcId"))
        for supply in rule.get("supplyItemList") or []:
            if not isinstance(supply, dict):
                continue
            condition = _city_condition(aliases, supply.get("dealCondId"))
            if not condition:
                continue
            town_id, threshold = condition
            if town_id not in town_by_id:
                continue
            item_id = _int(supply.get("itemId"))
            item = items.get(item_id) or {"name": "未识别物品", "price": 0,
                                          "quality": 0, "type": 0}
            shelf_npcs.setdefault(town_id, {}).setdefault(npc_id, 0)
            shelf_npcs[town_id][npc_id] += 1
            tier = shelf_tiers.setdefault(town_id, {}).setdefault(threshold, {})
            tier[item_id] = {
                "item": item_id,
                "name": item["name"],
                "price": _int(item.get("price")),
                "quality": _int(item.get("quality")),
                "type": _int(item.get("type")),
                "cost_item": _int(supply.get("costItemId")),
                "cost_count": _int(supply.get("count"), 1),
            }

    # 委托势力：force_type=1 对应城镇；force_type=2 是宗门委托，不在此模块。
    force_to_town = {}
    for row in _rows_of(tables, "tbcommissionforce"):
        if _int(row.get("force_type")) == 1:
            force_to_town[_int(row.get("id"))] = _int(row.get("parameter_id"))
    refresh = {}
    for row in _rows_of(tables, "tbcommissionforcetaskrefresh"):
        force_id = _int(row.get("force_id"))
        if force_id in force_to_town:
            refresh[force_id] = {
                "count": _int(row.get("refresh_task_count")),
                "enabled": bool(row.get("enabled")),
                "npc": _int(row.get("entry_npc_id")),
                "scene": _int(row.get("entry_scene_id")),
                "realm_section": _int(row.get("realm_section")),
            }

    pool_by_force = {}
    for row in _rows_of(tables, "tbcommissiontaskpool"):
        force_id = _int(row.get("force_id"))
        if force_id not in force_to_town:
            continue
        drop_id = _int(row.get("reward_drop_id"))
        stones, reputation, _other = _sum_drop(drops.get(drop_id) or [], rep_by_item)
        quest_id = _int(row.get("quest_id"))
        quest = quests.get(quest_id) or {}
        town_id = force_to_town[force_id]
        pool_by_force.setdefault(force_id, []).append({
            "id": _int(row.get("id")),
            "quest": quest_id,
            "name": quest.get("name") or ("委托 %s" % quest_id),
            "objective": quest.get("objective", ""),
            "location": quest.get("location", ""),
            "target": quest.get("target", ""),
            "count": quest.get("count", 0),
            "quality": quest.get("quality", ""),
            "action": quest.get("action", "其他"),
            "submit_npc": quest.get("submit_npc", 0),
            "submit_npc_name": quest.get("submit_npc_name", ""),
            "type": _int(row.get("task_type")),
            "difficulty": _int(row.get("difficulty"), 1),
            "weight": _int(row.get("weight")),
            "scope": _int(row.get("refresh_scope")),
            "realm_section": _int(row.get("realm_section")),
            "reputation": reputation.get(town_id, 0),
            "stones": stones,
        })

    titles_by_town = {}
    for row in _rows_of(tables, "tbreputationtitle"):
        if _int(row.get("titleType")) != 2:
            continue
        town_id = _int(row.get("targetId"))
        titles_by_town.setdefault(town_id, []).append({
            "id": _int(row.get("id")),
            "min": _int(row.get("minValue")),
            "max": _int(row.get("maxValue")),
            "name": _plain(row.get("titleName")),
            "desc": _plain(row.get("titleDesc")),
        })
    for list_ in titles_by_town.values():
        list_.sort(key=lambda item: item["min"])

    warnings = []
    result = []
    for town in towns:
        town_id = town["id"]
        force_id = next((key for key, value in force_to_town.items() if value == town_id), 0)
        info = refresh.get(force_id) or {}
        raw_tiers = shelf_tiers.get(town_id) or {}
        tiers = []
        seen_sets = {}
        duplicates = []
        for threshold in sorted(raw_tiers):
            tier_items = sorted(raw_tiers[threshold].values(), key=lambda item: item["item"])
            ids = frozenset(item["item"] for item in tier_items)
            same_as = seen_sets.get(ids, 0)
            if same_as:
                duplicates.append("%d（同 %d）" % (threshold, same_as))
            else:
                seen_sets[ids] = threshold
            tiers.append({
                "threshold": threshold,
                "items": tier_items,
                "duplicate": bool(same_as),
                "same_as": same_as,
                "price": tier_items[0]["price"] if tier_items else 0,
            })
        if duplicates:
            warnings.append("%s 的 %s 档货架物品与较早档位完全相同（重复配置）"
                            % (town["name"], "、".join(duplicates)))
        npc_id = 0
        if shelf_npcs.get(town_id):
            npc_id = max(shelf_npcs[town_id].items(), key=lambda pair: pair[1])[0]
        pool = pool_by_force.get(force_id) or []
        pool.sort(key=lambda item: (item["difficulty"], -item["reputation"], item["id"]))
        result.append({
            **town,
            "rep_item": item_by_town.get(town_id, 0),
            "force": force_id,
            "active": bool(info.get("enabled")) and bool(pool),
            "refresh_count": _int(info.get("count")),
            "refresh_npc": _int(info.get("npc")),
            "refresh_npc_name": npcs.get(_int(info.get("npc")), ""),
            "shelf": {
                "npc": npc_id,
                "npc_name": npcs.get(npc_id, ""),
                "tiers": tiers,
                "gates": [tier["threshold"] for tier in tiers],
            },
            "pool": pool,
            "titles": titles_by_town.get(town_id) or [],
        })

    for town in result:
        if town["active"] and not town["shelf"]["tiers"]:
            warnings.append("%s 有委托但未配置声望货架" % town["name"])
        if town["shelf"]["tiers"] and not town["force"]:
            warnings.append("%s 有货架但未配置委托势力" % town["name"])
    active = [town for town in result if town["active"]]
    result.sort(key=lambda town: (0 if town["active"] else 1, town["order"], town["id"]))
    return {
        "schema": 1,
        "towns": result,
        "active_count": len(active),
        "shelf_count": len([town for town in result if town["shelf"]["tiers"]]),
        "warnings": warnings,
    }
