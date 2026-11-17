# -*- coding: utf-8 -*-
"""宗门扫描：当前职位、贡献、声望、任务与收购委托。"""
import os


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


def meta(metadata):
    return metadata.get("sect") or {
        "schema": 1, "sects": [], "positions": [], "career": [], "realms": {"0": "凡人"},
        "phases": {}, "constants": {}, "task_types": {}, "warnings": [],
    }


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    player = (obj or {}).get("playerModel") or {}
    sect_id = _int(player.get("current_sect_id"))
    position_id = _int(player.get("current_sect_position_id"))
    behavior = player.get("behavior_value") or {}
    sect_reputes = _key_map(behavior.get("sect_reputes"))
    component = player.get("sectComponent") or {}
    tasks_state = component.get("task_component") or {}
    progression = component.get("progression_component") or {}
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
    if sect_id == 0 and _int(progression.get("applied_sect_id")):
        warnings.append("存档未入宗，但仍有任职申请记录")

    sect = sects.get(sect_id) or {}
    task_catalog = {_int(item.get("id")): item for item in sect.get("tasks") or []}
    order_catalog = {_int(item.get("id")): item for item in sect.get("purchases") or []}
    exchange = sect.get("exchange") or []

    records = _key_map(tasks_state.get("task_records"))
    completed_ids = set()
    for pool_id, record in records.items():
        if isinstance(record, dict):
            # 未来版本可能把任务池 id 放进记录体内，或调整键名，这里两种都认。
            pool_id = _int(record.get("pool_id") or record.get("task_pool_id") or pool_id)
            code = _int(record.get("state"), 0)
        else:
            code = _int(record, 0)
        if code in (1, 2, 3):
            completed_ids.add(pool_id)
        elif code not in (0,):
            # 未知状态不再当作已完成，只提示，避免误报进度。
            warnings.append("任务记录 %s 状态未识别（%s），按未完成处理" % (pool_id, code))

    offers = []
    for pool_id in tasks_state.get("current_offer_pool_ids") or []:
        pool_id = _int(pool_id)
        if not pool_id:
            continue
        task = task_catalog.get(pool_id)
        if not task:
            warnings.append("本期任务 %s 未在当前宗门任务池中" % pool_id)
            continue
        item = dict(task)
        item["locked"] = _int(task.get("min_position")) > _int(position.get("level"))
        item["completed"] = pool_id in completed_ids
        item["state"] = "已完成" if item["completed"] else ("可领取" if not item["locked"] else "职位不足")
        offers.append(item)

    purchase_current = []
    for order_id in tasks_state.get("current_purchase_order_ids") or []:
        order_id = _int(order_id)
        order = order_catalog.get(order_id)
        if order:
            purchase_current.append(dict(order, state="待交付"))
        elif order_id:
            warnings.append("征收委托 %s 未在当前宗门委托池中" % order_id)
    delivered = [_int(value) for value in tasks_state.get("delivered_purchase_order_ids") or []]

    # 已接取的宗门任务不在 tbsecttaskpool 里，而在 questComponent.quests 中；
    # 只读 current_offer_pool_ids 会漏掉它们，导致“本期任务只有 3 个”的错觉。
    duty_quests = meta_obj.get("duty_quests") or {}
    accepted = []
    quest_log = ((player.get("questComponent") or {}).get("quests") or {})
    for key, entry in quest_log.items():
        if not isinstance(entry, dict):
            continue
        quest_id = _int(entry.get("questId") or key)
        info = duty_quests.get(str(quest_id))
        if not info:
            continue
        state = _int(entry.get("state"))
        if state in (4, 5):
            continue
        progresses = entry.get("objectiveProgresses") or []
        progress_now = progress_target = 0
        if progresses and isinstance(progresses[0], dict):
            progress_now = _int(progresses[0].get("currentValue"))
            progress_target = _int(progresses[0].get("targetValue"))
        state_text = {0: "可接取", 1: "进行中", 2: "待提交", 3: "已提交", 6: "待提交"}.get(state, "进行中")
        accepted.append(dict(info, quest=quest_id, state=state, state_text=state_text,
                             progress_now=progress_now, progress_target=progress_target))
    accepted.sort(key=lambda item: (0 if item["state"] in (2, 6) else 1 if item["state"] == 1 else 2,
                                    item["quest"]))

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
            "targets": _key_map(progression.get("promotion_quest_targets")),
        }

    constants = meta_obj.get("constants") or {}
    # 优先用快照里的道具 id（build 从 tbitem 名称派生），旧快照缺字段时回退。
    contribution_id = _int(constants.get("SECT_CONTRIBUTION_ITEM_ID"), 50002)
    stone_id = _int(constants.get("STONE_ITEM_ID"), 50000)
    contribution = bag.get(contribution_id, 0)
    # 委托板只挂 3 条；已接任务在任务日志里，单独计数。每周期上限来自职位 task_limit。
    limit = _int(position.get("task_limit")) or _int(constants.get("SECT_TASK_DEFAULT_LIMIT"), 3)
    accepted_count = sum(1 for item in accepted if item["state"] in (1, 2, 6))
    settled_count = _int(tasks_state.get("current_cycle_settled_count")) or \
        sum(1 for item in accepted if item["state"] == 3)
    slots = {
        "offered": len(offers),
        "limit": limit,
        "accepted": accepted_count,
        "settled": settled_count,
        "submit": sum(1 for item in accepted if item["state"] in (2, 6)),
        "remaining": max(0, limit - accepted_count - settled_count),
    }
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
        "offers": offers,
        "accepted": accepted,
        "slots": slots,
        "offer_contribution": sum(_int(item.get("contribution")) for item in offers
                                  if not item["completed"]),
        "offer_reputation": sum(_int(item.get("reputation")) for item in offers
                                if not item["completed"]),
        "completed": sorted(completed_ids),
        "purchase": {
            "current": purchase_current,
            "delivered": delivered,
            "refresh": _time_text(tasks_state.get("next_refresh_time")),
            "last_refresh": _time_text(tasks_state.get("last_refresh_time")),
        },
        "salary": {
            "next_time": _time_text(progression.get("next_salary_grant_time")),
            "amount": _int(progression.get("next_salary_grant_amount")),
            "annual": _int(position.get("salary")),
        },
        "promotion": promotion,
        "exchange_affordable": affordable,
        "exchange_total": len(exchange),
        "refresh": {
            "last": _time_text(tasks_state.get("last_refresh_time")),
            "next": _time_text(tasks_state.get("next_refresh_time")),
            "serial": _int(tasks_state.get("current_refresh_serial")),
        },
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
    return "宗门：%s · %s；贡献 %d，宗门声望 %d，委托板 %d 条，差遣/要务/重任已接 %d" % (
        rows.get("sect_name") or "未知宗门", rows.get("position_name") or "未知职位",
        _int(rows.get("contribution")), _int(rows.get("reputation")),
        len(rows.get("offers") or []),
        len(rows.get("accepted") or []))
