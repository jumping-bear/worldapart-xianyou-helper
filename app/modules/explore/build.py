# -*- coding: utf-8 -*-
"""探索属性：本月 NPC 特殊互动入口与委托目标 → 模块快照。

数据来源（已核对）：
    tbnpcinteractgameentry   NPC 特殊互动入口、奖励掉落、精力消耗
    tbnpcinteractiongroup    每个 NPC 的月度抽取概率上限
    tbrewarddrop / tbitem    入口奖励中的属性经验与灵石/亲密度
    tbinteractattribute      探索属性与等级阈值（属性 id/名称/顺序都从表里取）
    tbcommissionforce        委托势力（force_type=1 城镇，2 宗门）
    tbcommissiontaskpool     当前可刷新的委托池
    tbquest                  委托名称与目标描述
    tbgameactionflow         从委托目标流里取出目标 NPC
"""
from collections import Counter
import re

from meta_update import SCHEMA, _int, _plain, _rows, _text, build_spaces


def _rows_of(tables, key):
    value = tables.get(key)
    if isinstance(value, dict):
        value = value.get("rows") or []
    return [row for row in _rows(value) if isinstance(row, dict)]


def _levels(row):
    levels = []
    for item in row.get("levelConfigs") or []:
        if not isinstance(item, dict):
            continue
        need = _int(item.get("maxExp"))
        if need > 0:
            levels.append(need)
    return levels


def _collect_drop(drop_id, drops, bag, depth=0):
    """把奖励掉落展开成 {物品: [最少, 最多]}；兼容嵌套 rewardDropList。"""
    row = drops.get(drop_id)
    if not isinstance(row, dict) or depth > 2:
        return
    for variant in row.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        for item in variant.get("dropList") or []:
            if not isinstance(item, dict):
                continue
            item_id = _int(item.get("itemId"))
            low = _int(item.get("itemCountMin"), 1)
            high = _int(item.get("itemCountMax"), low)
            if not item_id:
                continue
            old = bag.get(item_id)
            bag[item_id] = [min(old[0], low) if old else low,
                            max(old[1], high) if old else high]
        for sub in variant.get("rewardDropList") or []:
            if isinstance(sub, dict):
                _collect_drop(_int(sub.get("rewardDropId")), drops, bag, depth + 1)


def _entry(row, drops, attr_ids):
    bag = {}
    _collect_drop(_int(row.get("reward")), drops, bag)
    exp = [[item_id, bag[item_id][0], bag[item_id][1]]
           for item_id in attr_ids if item_id in bag]
    attr = exp[0][0] if exp else 0
    drops_out = [[item_id, bag[item_id][0], bag[item_id][1]]
                 for item_id in sorted(bag) if item_id not in attr_ids]
    return {
        "type": _int(row.get("interactGameType")),
        "name": _plain(row.get("interactButtonName")),
        "tag": _plain(row.get("stateTagName")),
        "desc": _plain(row.get("stateTagDesc")),
        "stamina": _int(row.get("costStamina")),
        "attr": attr,
        "exp": exp,
        "drops": drops_out,
    }


def _quest_text(quest):
    for objective in quest.get("objectives") or []:
        if not isinstance(objective, dict):
            continue
        text = _plain(objective.get("description"))
        if text:
            return text, objective
    return "", None


def _quest_place(quest):
    """从任务目标描述里取地点；没有地点时返回空串，不猜。"""
    for objective in quest.get("objectives") or []:
        if not isinstance(objective, dict):
            continue
        raw = _text(objective.get("description"))
        if not raw:
            continue
        highlights = [_plain(match) for match in
                      re.findall(r"<color=[^>]+>(.*?)</color>", raw, re.S)]
        for text in highlights:
            if "·" in text or "." in text:
                return text
    return ""


def _flow_npc(flows, flow_id):
    flow = flows.get(flow_id) or {}
    action = flow.get("action") or {}
    for arg in action.get("args") or []:
        if isinstance(arg, list) and len(arg) == 2 and isinstance(arg[1], dict):
            value = _int(arg[1].get("value"))
            if value:
                return value
    return 0


def build_explore(tables):
    attributes = []
    for row in _rows_of(tables, "tbinteractattribute"):
        attr_id = _int(row.get("id"))
        if not attr_id:
            continue
        attributes.append({
            "id": attr_id,
            "name": _plain(row.get("name")) or str(attr_id),
            "desc": _plain(row.get("desc")),
            "levels": _levels(row),
        })
    attributes.sort(key=lambda item: item["id"])
    attr_ids = [item["id"] for item in attributes]
    if not attributes:
        raise ValueError("探索属性配置为空")

    npc_names = {}
    for row in _rows_of(tables, "tbnpcbasecfg"):
        npc_id = _int(row.get("id"))
        if npc_id:
            npc_names[npc_id] = {
                "name": _plain(row.get("npcName")) or "未识别 NPC",
                "spar": bool(row.get("can_spar")),
                "layer": _plain(row.get("layerZeroShowText")),
                "title": _plain(row.get("npcTitle")),
            }

    drops = {_int(row.get("id")): row for row in _rows_of(tables, "tbrewarddrop")}
    entries = {}
    needed_items = set()
    button_attrs = {}
    exp_ranges = set()
    for row in _rows_of(tables, "tbnpcinteractgameentry"):
        npc_id = _int(row.get("npcId"))
        sub_id = _int(row.get("subId"))
        if not npc_id or not sub_id:
            continue
        info = _entry(row, drops, attr_ids)
        if not info["attr"]:
            continue
        entries["%d:%d" % (npc_id, sub_id)] = info
        needed_items.update(item[0] for item in info["drops"])
        button_attrs.setdefault(info["name"], Counter())[info["attr"]] += 1
        for item in info["exp"]:
            exp_ranges.add((item[1], item[2]))

    # 入口按钮名 → 属性：用于把委托任务动作映射到属性，不写死“切磋=体魄”。
    attr_by_action = {name: counts.most_common(1)[0][0]
                      for name, counts in button_attrs.items() if name and counts}
    action_names = sorted(attr_by_action, key=len, reverse=True)
    # SPAR_MONTHLY_LIMIT 在当前版本的托管代码里没有读取点，不能据此做次数限制；
    # 这里只保留“切磋”入口类型，用于页面分组与优先展示。
    spar_type = next((info["type"] for info in entries.values()
                      if info["name"] == "切磋"), 0)

    item_names = {}
    for row in _rows_of(tables, "tbitem"):
        item_id = _int(row.get("id"))
        if item_id in needed_items:
            item_names[str(item_id)] = _plain(row.get("itemName")) or "未识别物品"

    groups = {}
    for row in _rows_of(tables, "tbnpcinteractiongroup"):
        npc_id = _int(row.get("npcId"))
        if npc_id:
            groups[str(npc_id)] = {
                "cycle": _int(row.get("triggerCycleType")),
                "value": _int(row.get("triggerCycleValue")),
                "ratio": _int(row.get("maxTriggerRatio")),
            }

    spaces = {}
    for space_id, space in build_spaces(tables).items():
        spaces[space_id] = list(space.get("path") or [])

    def space_text(space_id):
        path = spaces.get(str(space_id)) or []
        return " / ".join(path) or "未知地点"

    quests = {_int(row.get("id")): row for row in _rows_of(tables, "tbquest")}
    flows = {_int(row.get("id")): row for row in _rows_of(tables, "tbgameactionflow")}
    forces = {_int(row.get("id")): row for row in _rows_of(tables, "tbcommissionforce")}
    refresh_by_force = {_int(row.get("force_id")): row
                        for row in _rows_of(tables, "tbcommissionforcetaskrefresh")}
    tasks = {}
    task_npcs = set()
    for row in _rows_of(tables, "tbcommissiontaskpool"):
        quest_id = _int(row.get("quest_id"))
        quest = quests.get(quest_id)
        if not quest:
            continue
        text, objective = _quest_text(quest)
        action = next((name for name in action_names if name in text), "")
        attr_id = attr_by_action.get(action, 0)
        if not action or not attr_id or not isinstance(objective, dict):
            continue
        npc_id = _flow_npc(flows, _int(objective.get("activeFlowId")))
        if not npc_id:
            continue
        force = forces.get(_int(row.get("force_id"))) or {}
        refresh = refresh_by_force.get(_int(row.get("force_id"))) or {}
        board_npc = _int(refresh.get("entry_npc_id"))
        tasks[str(_int(row.get("id")))] = {
            "quest": quest_id,
            "name": _plain(quest.get("name")) or "未识别委托",
            "action": action,
            "attr": attr_id,
            "npc": npc_id,
            "kind": "宗门" if _int(force.get("force_type")) == 2 else "城镇",
            "board_place": space_text(_int(refresh.get("entry_scene_id"))),
            "board_npc": (npc_names.get(board_npc) or {}).get("name") or "未识别 NPC",
            "board_enabled": bool(refresh.get("enabled")),
            "target_place": _quest_place(quest),
        }
        task_npcs.add(npc_id)

    keep_npcs = set()
    for key in entries:
        keep_npcs.add(_int(key.split(":", 1)[0]))
    keep_npcs |= task_npcs
    npcs = {str(npc_id): npc_names[npc_id] for npc_id in keep_npcs if npc_id in npc_names}

    return {
        "schema": SCHEMA,
        "const": {"spar_type": spar_type},
        "attributes": attributes,
        "entries": entries,
        "npcs": npcs,
        "groups": groups,
        "spaces": spaces,
        "tasks": tasks,
        "item_names": item_names,
        # 经验区间从配置实际掉落里收集，新增一档会直接出现在筛选里。
        "exp_ranges": [[low, high] for low, high in
                       sorted(exp_ranges, key=lambda item: (-item[1], -item[0]))],
    }


build = build_explore
