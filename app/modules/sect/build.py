# -*- coding: utf-8 -*-
"""宗门：配置表 → 模块快照。

数据来源（2026-11-27 已核对）：

    tbsect                    宗门基础信息、藏经阁兑换 NPC、入宗任务
    tbsectposition            职位、晋升所需宗门声望与境界、年俸
    tbsectpositionquest       各宗门的晋升考核任务
    tbnpcbagrule              藏经阁兑换货架（scriptoriumContributionPrice）
    tbconditionexpr           兑换档位的职位条件（BASE_POS_GE_n）
    tbquest / tbrewarddrop    任务名、目标与奖励（贡献、声望）

宗门委托（游戏现行系统，入口是宗门场景顶部的「委托」按钮）：

    tbcommissionforce            委托势力；force_type=2 是宗门，parameter_id=宗门 id
    tbcommissionforcetaskrefresh 各势力委托的入口场景/NPC、刷新条数
    tbcommissiontaskpool         委托池：任务类型、职位门槛、任务 id、奖励掉落

旧执事堂的 tbsecttaskpool / tbsectpurchaseorder 在当前版本没有游戏入口
（执事堂交互动作 604 未被任何 NPC 或场景 UI 引用），不再进入快照。
"""
import re

from meta_update import _int, _plain, _rows, _text, build_realms


# 委托任务类型：来自游戏 TbStrConfig 的 COMMISSION_TASK_TYPE_* 文案
# （1 找人 / 2 除妖 / 3 争斗 / 4 采集 / 5 疏经 / 6 炼器 / 7 炼丹 / 8 赠礼 /
#  9 恩怨 / 10 偷窃），已用 tbcommissiontaskpool.task_type 与任务名逐一核对。
COMMISSION_TASK_TYPES = {
    1: "找人", 2: "除妖", 3: "争斗", 4: "采集", 5: "疏经",
    6: "炼器", 7: "炼丹", 8: "赠礼", 9: "恩怨", 10: "偷窃",
}
COMMISSION_TASK_TYPE_FALLBACK = "委托"

# 委托周期常量在 tbconstants 主表（不分片）。meta_update 对分片表只保留首个，
# 可能拿到 tbconstants.* 分片而取不到这几项，此时回退到游戏实测值并记录来源。
COMMISSION_CONSTANT_DEFAULTS = {
    "COMMISSION_TASK_REFRESH_DAYS": 30,
    "COMMISSION_TASK_MAX_ACCEPTED_PER_FORCE": 10,
    "COMMISSION_TASK_COMPLETION_DAYS": 90,
}


def _commission_type_name(task_type):
    return COMMISSION_TASK_TYPES.get(task_type) or COMMISSION_TASK_TYPE_FALLBACK


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
            names[quest_id] = _plain(row.get("name")) or ""
    return names


def _strip_type_prefix(name):
    """任务名去掉「[宗门]」这类类型前缀，只留可读任务名。"""
    return re.sub(r"^\[[^\]]*\]\s*", "", name or "").strip()


def _quest_objective(row):
    """任务目标 → 目标文本、地点、目标物/怪物/NPC、数量、品质。"""
    raw_texts = []
    for objective in row.get("objectives") or []:
        if isinstance(objective, dict):
            raw = _text(objective.get("description"))
            if raw:
                raw_texts.append(raw)
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
    match = re.search(r"(?:采集|收集|击败|击杀|讨伐|提交|准备|炼制|筹备|赠送|窃取|偷窃|说服|行医|疏经)\s*(\d+)\s*(?:个|只|名|位|株|份|枚|张|件)", objective)
    if match:
        count = int(match.group(1))
    quality = ""
    quality_match = re.search(r"[（(]([^）)]+品质)[）)]", objective)
    if quality_match:
        quality = quality_match.group(1)
    return {"objective": objective, "location": location, "target": target,
            "count": count, "quality": quality}


def _sect_quests(tables):
    """全部 [宗门] 任务：任务名、目标、地点与数量。

    这些任务就是现行宗门委托的内容（tbcommissiontaskpool.quest_id 指向它们），
    不在旧 tbsecttaskpool 里；已接任务的进度也只能从存档任务日志关联。
    """
    out = {}
    for row in _rows_of(tables, "tbquest"):
        quest_id = _int(row.get("id"))
        name = _plain(row.get("name")) or ""
        if not quest_id or not (name.startswith("[宗门]") or name.startswith("[宗門]")):
            continue
        info = _quest_objective(row)
        info["name"] = _strip_type_prefix(name)
        info["full_name"] = name
        out[str(quest_id)] = info
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


def _sum_drop(entries, rep_map, item_names):
    """把掉落拆成灵石、宗门贡献、宗门/城镇声望、其它物品（其它物品带名称）。"""
    stones, contribution, sect_rep, town_rep, extra = 0, 0, {}, {}, []
    for item_id, low, high in entries:
        count = low if low == high else max(low, high)
        name = item_names.get(item_id) or ""
        if name == "灵石":
            stones += count
            continue
        if name == "宗门贡献":
            contribution += count
            continue
        target = rep_map.get(item_id)
        if target:
            kind, target_id = target
            bucket = sect_rep if kind == "sect" else town_rep
            bucket[target_id] = bucket.get(target_id, 0) + count
            continue
        extra.append({"item": item_id, "name": name or "未识别物品", "count": count})
    return stones, contribution, sect_rep, town_rep, extra


def _position_text(ids, names):
    """职位门槛显示：连续段用「A ~ B」，否则顿号分隔。"""
    names = [name for name in names if name]
    if not ids:
        return ""
    if not names:
        return ""
    if len(names) > 1 and len(ids) == len(range(ids[0], ids[-1] + 1)):
        return "%s ~ %s" % (names[0], names[-1])
    return "、".join(names)


def _commission_constants(tables):
    """委托周期常量：优先 tbconstants 主表，取不到时回退游戏实测值。"""
    values = dict(COMMISSION_CONSTANT_DEFAULTS)
    source = "fallback"
    keys = set(COMMISSION_CONSTANT_DEFAULTS)
    for row in _rows_of(tables, "tbconstants"):
        for key in keys:
            if key in row:
                values[key] = _int(row.get(key), values[key])
                source = "config"
    return values, source


def build(tables):
    realms = build_realms(tables)
    item_names, drops = _reward_items(tables)
    quests = _quest_names(tables)
    sect_quests = _sect_quests(tables)
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

    # 委托势力：force_type=2 → parameter_id 是宗门 id
    force_by_sect = {}
    for row in _rows_of(tables, "tbcommissionforce"):
        if _int(row.get("force_type")) == 2:
            force_by_sect[_int(row.get("parameter_id"))] = _int(row.get("id"))
    refresh_by_force = {}
    for row in _rows_of(tables, "tbcommissionforcetaskrefresh"):
        force_id = _int(row.get("force_id"))
        if force_id:
            refresh_by_force[force_id] = row
    pool_by_force = {}
    for row in _rows_of(tables, "tbcommissiontaskpool"):
        pool_by_force.setdefault(_int(row.get("force_id")), []).append(row)

    commission_constants, constants_source = _commission_constants(tables)
    commission_constants["source"] = constants_source
    commission_constants["max_accepted"] = commission_constants.get(
        "COMMISSION_TASK_MAX_ACCEPTED_PER_FORCE", 10)

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

        # 宗门委托（现行系统）
        force_id = force_by_sect.get(sect_id, 0)
        commission = {
            "force": force_id,
            "enabled": False,
            "entry_scene": 0,
            "entry_scene_name": "",
            "entry_npc": 0,
            "entry_npc_name": "",
            "refresh_count": 0,
            "tasks": [],
        }
        if force_id:
            entry_row = refresh_by_force.get(force_id) or {}
            scene_id = _int(entry_row.get("entry_scene_id"))
            npc_id = _int(entry_row.get("entry_npc_id"))
            commission.update({
                "enabled": bool(entry_row.get("enabled")),
                "entry_scene": scene_id,
                "entry_scene_name": space_names.get(scene_id, ""),
                "entry_npc": npc_id,
                "entry_npc_name": npcs.get(npc_id, ""),
                "refresh_count": _int(entry_row.get("refresh_task_count")),
            })
            for pool_row in pool_by_force.get(force_id, []):
                task_id = _int(pool_row.get("id"))
                quest_id = _int(pool_row.get("quest_id"))
                task_type = _int(pool_row.get("task_type"))
                quest_info = sect_quests.get(str(quest_id)) or {}
                stones, contribution, sect_rep, _town_rep, extra = _sum_drop(
                    drops.get(_int(pool_row.get("reward_drop_id"))) or [], rep_map, item_names)
                pos_ids = sorted({_int(value) for value in
                                  (pool_row.get("sect_position_id") or []) if _int(value)})
                pos_names = [(position_by_id.get(pid) or {}).get("name", "") for pid in pos_ids]
                commission["tasks"].append({
                    "id": task_id,
                    "quest": quest_id,
                    "name": quest_info.get("name") or "未识别委托",
                    "type": task_type,
                    "type_name": _commission_type_name(task_type),
                    "difficulty": _int(pool_row.get("difficulty"), 1),
                    "realm_section": _int(pool_row.get("realm_section")),
                    "objective": quest_info.get("objective", ""),
                    "location": quest_info.get("location", ""),
                    "target": quest_info.get("target", ""),
                    "count": quest_info.get("count", 0),
                    "quality": quest_info.get("quality", ""),
                    "position_ids": pos_ids,
                    "position_names": [text for text in pos_names if text],
                    "position_text": _position_text(pos_ids, pos_names),
                    "contribution": contribution,
                    "reputation": sect_rep.get(sect_id, 0),
                    "stones": stones,
                    "other": extra,
                })
            commission["tasks"].sort(
                key=lambda task: (task["difficulty"], task["type"], task["id"]))
            if exchange and not commission["tasks"]:
                warnings.append("%s 有委托势力但任务池为空" % name)
        elif exchange:
            warnings.append("%s 未配置宗门委托势力（force_type=2）" % name)

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
            "commission": commission,
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
    # 贡献 id 同理，避免写死 50002。
    contribution_id = next((item_id for item_id, row in item_rows.items()
                            if _plain(row.get("itemName")) == "宗门贡献"), 0)
    constants.setdefault("SECT_CONTRIBUTION_ITEM_ID", contribution_id or 50002)

    return {
        "schema": 1,
        "realms": realms,
        "phases": phases,
        "positions": positions,
        "career": career,
        "constants": constants,
        "commission_constants": commission_constants,
        "commission_types": {str(key): value for key, value in COMMISSION_TASK_TYPES.items()},
        "sects": sects,
        "warnings": warnings,
    }
