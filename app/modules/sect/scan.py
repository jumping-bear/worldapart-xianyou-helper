# -*- coding: utf-8 -*-
"""宗门扫描：当前职位、贡献、声望、宗门委托与晋升。

宗门委托走游戏现行「委托」系统：
    存档 questComponent.commission_task_component.force_records[<force_id>]
    - task_ids            本期挂出的委托（每期刷新 9 条）
    - accepted_task_ids   已接的委托
    - accepted_times      接取时间（90 天不做会失效）
    - refresh_time        上次刷新时间（30 天一期）

任务进度从任务日志 questComponent.quests 里按 quest_id 关联；
旧执事堂的 sectComponent.task_component（委托板/灵材征收）已不再展示。
"""
import os

DAY_PER_MONTH = 30  # 游戏历法：每月 30 天（旧执事堂 next_refresh_time 实测 +1 月）
MONTH_PER_YEAR = 12


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bag_counts(bag):
    """玩家背包 → {物品 id: 数量}；兼容 [[槽位, {item_id, count}]] 与平铺字典。"""
    counts = {}

    def add(item_id, count):
        item_id = _int(item_id)
        if item_id:
            counts[item_id] = counts.get(item_id, 0) + _int(count)

    items = (bag or {}).get("items") if isinstance(bag, dict) else None
    if isinstance(items, dict):
        for key, value in items.items():
            if isinstance(value, dict):
                add(value.get("item_id") or key, value.get("count") or value.get("num") or 0)
            else:
                add(key, value)
    elif isinstance(items, list):
        for entry in items:
            if isinstance(entry, dict):
                add(entry.get("item_id"), entry.get("count") or entry.get("num") or 0)
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                payload = entry[1]
                if isinstance(payload, dict):
                    add(payload.get("item_id"), payload.get("count") or payload.get("num") or 0)
                else:
                    add(entry[0], payload)
    return counts


def _key_map(mapping):
    """存档里的字典键可能是 int 也可能是 str，统一成 int。"""
    out = {}
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            out[_int(key)] = value
    return out


def _realm_for_layer(phases, layer):
    best, realm = -1, 0
    for raw, realm_id in (phases or {}).items():
        phase = _int(raw)
        if phase <= _int(layer) and phase > best:
            best, realm = phase, _int(realm_id)
    return realm


def _time_text(value):
    if not isinstance(value, dict):
        return ""
    year, month, day = _int(value.get("year")), _int(value.get("month")), _int(value.get("day"))
    if not (year or month or day):
        return ""
    return "%d年%d月%d日" % (year, month, day)


def _time_days(value):
    """游戏时间 → 绝对天数；非法/零值返回 None。"""
    if not isinstance(value, dict):
        return None
    year, month, day = _int(value.get("year")), _int(value.get("month")), _int(value.get("day"))
    if year <= 0 and month <= 0 and day <= 0:
        return None
    return year * MONTH_PER_YEAR * DAY_PER_MONTH + (month - 1) * DAY_PER_MONTH + (day - 1)


def _add_days(value, days):
    if not isinstance(value, dict):
        return {}
    total = _time_days(value)
    if total is None:
        return {}
    total += _int(days)
    year, rest = divmod(total, MONTH_PER_YEAR * DAY_PER_MONTH)
    month, day = divmod(rest, DAY_PER_MONTH)
    return {"year": year, "month": month + 1, "day": day + 1}


def _quest_log(player):
    """任务日志 → {quest_id: entry}。兼容 int / str 键与 questId 字段。"""
    out = {}
    log = ((player.get("questComponent") or {}).get("quests") or {})
    if not isinstance(log, dict):
        return out
    for key, entry in log.items():
        if not isinstance(entry, dict):
            continue
        quest_id = _int(entry.get("questId") or key)
        if quest_id:
            out[quest_id] = entry
    return out


def _quest_progress(entry):
    progresses = (entry or {}).get("objectiveProgresses") or []
    if progresses and isinstance(progresses[0], dict):
        return _int(progresses[0].get("currentValue")), _int(progresses[0].get("targetValue"))
    return 0, 0


def _state_text(state):
    return {0: "可接取", 1: "进行中", 2: "待提交", 3: "已提交", 6: "待提交"}.get(
        state, "状态未知")


def _task_view(task):
    """委托池配置 → 界面任务卡基础字段。"""
    return {
        "id": task.get("id", 0),
        "quest": task.get("quest", 0),
        "name": task.get("name") or "未识别委托",
        "type": task.get("type", 0),
        "type_name": task.get("type_name") or "委托",
        "difficulty": task.get("difficulty", 1),
        "objective": task.get("objective", ""),
        "location": task.get("location", ""),
        "target": task.get("target", ""),
        "count": task.get("count", 0),
        "quality": task.get("quality", ""),
        "position_text": task.get("position_text", ""),
        "position_ids": task.get("position_ids") or [],
        "contribution": task.get("contribution", 0),
        "reputation": task.get("reputation", 0),
        "stones": task.get("stones", 0),
        "other": task.get("other") or [],
    }


def meta(metadata):
    return metadata.get("sect") or {
        "schema": 1, "sects": [], "positions": [], "career": [], "realms": {"0": "凡人"},
        "phases": {}, "constants": {}, "commission_constants": {},
        "commission_types": {}, "warnings": [],
    }


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    player = (obj or {}).get("playerModel") or {}
    sect_id = _int(player.get("current_sect_id"))
    position_id = _int(player.get("current_sect_position_id"))
    behavior = player.get("behavior_value") or {}
    sect_reputes = _key_map(behavior.get("sect_reputes"))
    bag = _bag_counts(player.get("bag"))

    positions = {_int(item.get("id")): item for item in meta_obj.get("positions") or []}
    sects = {_int(item.get("id")): item for item in meta_obj.get("sects") or []}
    realm_names = meta_obj.get("realms") or {}
    layer = _int((player.get("combat") or {}).get("cultivate_layer_id"))
    realm = _realm_for_layer(meta_obj.get("phases"), layer)
    warnings = []

    position = positions.get(position_id) or {}
    if sect_id and not position:
        warnings.append("存档职位 %s 未在职位表中找到" % position_id)
    if sect_id and sect_id not in sects:
        warnings.append("存档宗门 %s 未在宗门表中找到" % sect_id)
    if sect_id == 0 and _int(((player.get("sectComponent") or {}).get(
            "progression_component") or {}).get("applied_sect_id")):
        warnings.append("存档未入宗，但仍有任职申请记录")

    sect = sects.get(sect_id) or {}
    exchange = sect.get("exchange") or []
    constants = meta_obj.get("constants") or {}
    commission_constants = meta_obj.get("commission_constants") or {}

    # ---------- 宗门委托 ----------
    now_time = (obj or {}).get("currentGameTime") or {}
    force_id = _int((sect.get("commission") or {}).get("force"))
    commission_cfg = sect.get("commission") or {}
    refresh_days = _int(commission_constants.get("COMMISSION_TASK_REFRESH_DAYS"), 30)
    completion_days = _int(commission_constants.get("COMMISSION_TASK_COMPLETION_DAYS"), 90)
    limit = _int(commission_constants.get("max_accepted"), 10)
    catalog = {_int(task.get("id")): task for task in commission_cfg.get("tasks") or []}
    quest_log = _quest_log(player)
    records = _key_map(((player.get("questComponent") or {}).get(
        "commission_task_component") or {}).get("force_records"))
    record = (records.get(force_id) or {}) if force_id else {}

    offered_ids = []
    for value in record.get("task_ids") or []:
        value = _int(value)
        if value and value not in offered_ids:
            offered_ids.append(value)
    accepted_ids = []
    for value in record.get("accepted_task_ids") or []:
        value = _int(value)
        if value and value not in accepted_ids:
            accepted_ids.append(value)
    accepted_times = _key_map(record.get("accepted_times"))

    available, accepted, submitted = [], [], []
    now_days = _time_days(now_time)

    def make_card(pool_id):
        task = catalog.get(pool_id)
        if not task:
            return None
        card = _task_view(task)
        pos_ids = card["position_ids"]
        card["position_ok"] = (not pos_ids) or (position_id in pos_ids)
        card["locked"] = not card["position_ok"]
        return card

    for pool_id in accepted_ids:
        card = make_card(pool_id)
        if not card:
            warnings.append("已接委托 %s 未在当前宗门委托池中" % pool_id)
            continue
        entry = quest_log.get(_int(card["quest"])) or {}
        if not entry:
            warnings.append("委托「%s」在任务日志中找不到进度" % card["name"])
        state_code = _int(entry.get("state"))
        progress_now, progress_target = _quest_progress(entry)
        card.update({
            "state": state_code,
            "state_text": _state_text(state_code) if entry else "状态未知",
            "progress_now": progress_now,
            "progress_target": progress_target,
        })
        accepted_at = accepted_times.get(pool_id)
        accepted_days = _time_days(accepted_at)
        if accepted_days is not None and now_days is not None:
            card["remaining_days"] = max(0, completion_days - (now_days - accepted_days))
        else:
            card["remaining_days"] = None
        if state_code == 3:
            submitted.append(card)
        else:
            accepted.append(card)

    accepted.sort(key=lambda item: (
        0 if item["state_text"] == "待提交" else 1, item.get("remaining_days") or 999, item["name"]))
    pending = [item for item in accepted if item["state_text"] == "待提交"]
    active = [item for item in accepted if item["state_text"] != "待提交"]

    for pool_id in offered_ids:
        if pool_id in accepted_ids:
            continue
        card = make_card(pool_id)
        if not card:
            warnings.append("本期委托 %s 未在当前宗门委托池中" % pool_id)
            continue
        available.append(card)
    available.sort(key=lambda item: (item["locked"], item["difficulty"], item["type"], item["name"]))

    # 顺路：本期可接委托按目标地点归组，先做同地点的。
    groups = {}
    for card in available:
        if card["locked"]:
            continue
        key = card["location"] or "任意地点"
        group = groups.setdefault(key, {
            "location": key, "count": 0, "contribution": 0, "reputation": 0, "names": []})
        group["count"] += 1
        group["contribution"] += _int(card["contribution"])
        group["reputation"] += _int(card["reputation"])
        group["names"].append(card["name"])
    group_list = sorted(groups.values(),
                        key=lambda item: (-item["count"], -item["contribution"], item["location"]))

    last_days = _time_days(record.get("refresh_time"))
    refresh = {
        "last": _time_text(record.get("refresh_time")),
        "next": _time_text(_add_days(record.get("refresh_time"), refresh_days)),
        "days_left": (max(0, refresh_days - (now_days - last_days))
                      if last_days is not None and now_days is not None else None),
        "days": refresh_days,
    }
    commission = {
        "force": force_id,
        "enabled": bool(commission_cfg.get("enabled")),
        "scene": _int(commission_cfg.get("entry_scene")),
        "scene_name": commission_cfg.get("entry_scene_name", ""),
        "npc": _int(commission_cfg.get("entry_npc")),
        "npc_name": commission_cfg.get("entry_npc_name", ""),
        "refresh_count": _int(commission_cfg.get("refresh_count")),
        "refresh": refresh,
        "completion_days": completion_days,
        "limit": limit,
        "offered": len(offered_ids),
        "accepted_count": len(accepted_ids),
        "remaining": max(0, limit - len(accepted_ids)),
        "available": available,
        "accepted": accepted,
        "pending": pending,
        "active": active,
        "submitted": submitted,
        "groups": group_list,
        "locked_count": sum(1 for card in available if card["locked"]),
        "available_contribution": sum(_int(card["contribution"]) for card in available if not card["locked"]),
        "available_reputation": sum(_int(card["reputation"]) for card in available if not card["locked"]),
        "accepted_contribution": sum(_int(card["contribution"]) for card in accepted),
        "accepted_reputation": sum(_int(card["reputation"]) for card in accepted),
        "catalog_size": len(catalog),
    }
    if sect_id and force_id and not catalog:
        warnings.append("本宗门的委托任务池为空（不影响其它模块）")
    if commission_cfg.get("enabled") and not record:
        warnings.append("存档还没有本宗门的委托刷新记录，进一次游戏或过一天后再同步")

    # 晋升：职位链中下一个可晋升职位；条件取职位表（声望、境界）与晋升任务。
    career = [item for item in meta_obj.get("career") or []
              if _int(item.get("level")) > _int(position.get("level"))]
    next_position = career[0] if career else None
    promotion = None
    if sect_id and next_position:
        reputation = sect_reputes.get(sect_id, 0)
        promo_meta = {}
        for item in sect.get("promotions") or []:
            if _int(item.get("position")) == _int(next_position.get("id")):
                promo_meta = item
                break
        promotion = {
            "position": next_position.get("id"),
            "name": next_position.get("name"),
            "level": next_position.get("level"),
            "reputation": _int(next_position.get("reputation")),
            "reputation_now": reputation,
            "reputation_ok": reputation >= _int(next_position.get("reputation")),
            "realm": _int(next_position.get("realm")),
            "realm_name": realm_names.get(str(_int(next_position.get("realm"))), ""),
            "realm_now": realm,
            "realm_now_name": realm_names.get(str(realm), ""),
            "realm_ok": realm >= _int(next_position.get("realm")) if _int(next_position.get("realm")) else True,
            "quest": promo_meta.get("quest", 0),
            "quest_name": promo_meta.get("quest_name", ""),
            "salary": _int(next_position.get("salary")),
            "task_limit": _int(next_position.get("task_limit")),
            "targets": _key_map(((player.get("sectComponent") or {}).get(
                "progression_component") or {}).get("promotion_quest_targets")),
        }

    # 优先用快照里的道具 id（build 从 tbitem 名称派生），旧快照缺字段时回退。
    contribution_id = _int(constants.get("SECT_CONTRIBUTION_ITEM_ID"), 50002)
    stone_id = _int(constants.get("STONE_ITEM_ID"), 50000)
    contribution = bag.get(contribution_id, 0)
    affordable = sum(1 for entry in exchange
                     if _int(entry.get("price")) <= contribution
                     and _int(entry.get("position")) <= _int(position.get("level"))
                     and _int(entry.get("realm")) <= realm)
    return {
        "in_sect": bool(sect_id),
        "sect_id": sect_id,
        "sect_name": sect.get("name") or "",
        "position_id": position_id,
        "position_name": position.get("name") or "",
        "position_level": _int(position.get("level")),
        "realm": realm,
        "realm_name": realm_names.get(str(realm), ""),
        "layer": layer,
        "contribution": contribution,
        "contribution_total": _int(player.get("sect_contribution_total")),
        "stones": bag.get(stone_id, 0),
        "reputation": sect_reputes.get(sect_id, 0),
        "reputations": [{"sect": key, "name": (sects.get(key) or {}).get("name", ""), "value": _int(value)}
                        for key, value in sorted(sect_reputes.items()) if _int(value)],
        "commission": commission,
        "salary": {
            "next_time": _time_text(((player.get("sectComponent") or {}).get(
                "progression_component") or {}).get("next_salary_grant_time")),
            "amount": _int(((player.get("sectComponent") or {}).get(
                "progression_component") or {}).get("next_salary_grant_amount")),
            "annual": _int(position.get("salary")),
        },
        "promotion": promotion,
        "exchange_affordable": affordable,
        "exchange_total": len(exchange),
        "warnings": warnings,
    }


def post(rows, state, original, path):
    if isinstance(rows, dict):
        rows["src"] = os.path.basename(original) if original else os.path.basename(path or "")
    return rows


def enrich(module, meta_obj, state=None):
    module["meta"] = meta_obj or {}
    return module


def summary(module):
    rows = module.get("rows") or {}
    if not rows.get("in_sect"):
        return "宗门：尚未入宗"
    commission = rows.get("commission") or {}
    refresh = commission.get("refresh") or {}
    days_left = refresh.get("days_left")
    refresh_text = ("%d 天后刷新" % days_left) if days_left is not None else "刷新时间未知"
    return ("宗门：%s · %s；可接委托 %d 条（贡献 %d / 声望 %d），已接 %d/%d，"
            "待提交 %d，%s；贡献 %d，宗门声望 %d" % (
                rows.get("sect_name") or "未知宗门", rows.get("position_name") or "未知职位",
                len([card for card in commission.get("available") or [] if not card.get("locked")]),
                _int(commission.get("available_contribution")),
                _int(commission.get("available_reputation")),
                _int(commission.get("accepted_count")), _int(commission.get("limit")),
                len(commission.get("pending") or []), refresh_text,
                _int(rows.get("contribution")), _int(rows.get("reputation"))))
