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
        code = _int(record.get("state"), -1) if isinstance(record, dict) else _int(record, -1)
        if code in (1, 2, 3, -1):
            completed_ids.add(pool_id)

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

    contribution = bag.get(50002, 0)
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
        "stones": bag.get(50000, 0),
        "reputation": sect_reputes.get(sect_id, 0),
        "reputations": [{"sect": key, "name": (sects.get(key) or {}).get("name", ""), "value": _int(value)}
                        for key, value in sorted(sect_reputes.items()) if _int(value)],
        "offers": offers,
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
    module["config"] = meta_obj or {}
    module["config_warnings"] = (meta_obj or {}).get("warnings") or []
    return module


def summary(module):
    rows = module.get("rows") or {}
    if not rows.get("in_sect"):
        return "宗门：尚未入宗"
    return "宗门：%s · %s；贡献 %d，宗门声望 %d，本期任务 %d 项" % (
        rows.get("sect_name") or "未知宗门", rows.get("position_name") or "未知职位",
        _int(rows.get("contribution")), _int(rows.get("reputation")), len(rows.get("offers") or []))
