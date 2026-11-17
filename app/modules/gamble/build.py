# -*- coding: utf-8 -*-
"""赌石：配置表 → 模块快照。

数据来源：
    tbgamblestonerawtemplate / fleshquality / crack / bloom / embryoexchangeband
    tbgamblestonebuyoffer / buyoffernpc / tbitem / tbalchemyprototype
    tbnpcbagrule / tbnpcbasecfg / tbinitialspacenpc / tbspace / tbconditionexpr
    tbconstants

快照内只放展示与推算需要的字段，不保存原始配置表的全部列。
"""
import random

from meta_update import _int, _plain, _rows, _text, build_realms, build_spaces

QUALITY_NAMES = ["白", "绿", "蓝", "紫", "橙"]
SLOT_NAMES = {"1": "攻击", "2": "防御", "3": "辅助", "4": "速度"}
RISK_ORDER = {"稳健": 0, "均衡": 1, "波动": 2, "高风险": 3}
_TEMPLATE_SAMPLES = 9000


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _weighted_index(rng, weights):
    """按权重抽一个下标；权重全 0 时返回 0。"""
    total = 0.0
    for weight in weights or []:
        total += max(0.0, _num(weight))
    if total <= 0:
        return 0
    pick = rng.random() * total
    for index, weight in enumerate(weights):
        weight = max(0.0, _num(weight))
        if weight <= 0:
            continue
        pick -= weight
        if pick <= 0:
            return index
    return max(0, len(weights) - 1)


def _pick(rng, rows, weights):
    if not rows:
        return None
    return rows[min(_weighted_index(rng, weights), len(rows) - 1)]


def compute_value(flesh, blooms, cracks):
    """按配置权重推算一块璞石的满解估值。

    公式来自游戏内“基础估值 / 80% 起算 / 玉纹加成 / 整石折损 / 天成倍率”的展示文案，
    与存档里的 current_value 在 0% 刮开时对齐（等于璞石基础价）。
    """
    base = _num((flesh or {}).get("base_value")) * _num((flesh or {}).get("anchor_ratio"), 0.8)
    ratio = 1.0
    for bloom in blooms or []:
        ratio += _num(bloom.get("ratio_add"))
    loss = 1.0
    for crack in cracks or []:
        loss *= max(0.0, 1.0 - _num(crack.get("base_loss")))
    legend = 1.0
    for bloom in blooms or []:
        if bloom.get("is_legend"):
            legend *= _num(bloom.get("legend_factor"), 1.0) or 1.0
    return base * ratio * loss * legend


def allowed_bands(bands, quality, item_id=0):
    """品质可用的兑换价格带；专属璞石只走自己的专属带。"""
    exclusive = [band for band in bands or []
                 if _int(band.get("exclusive_item_id")) == _int(item_id) and _int(item_id)]
    if exclusive:
        return sorted(exclusive, key=lambda band: _int(band.get("min_value")))
    result = [band for band in bands or []
              if not _int(band.get("exclusive_item_id")) and _int(quality) in (band.get("qualities") or [])]
    return sorted(result, key=lambda band: (_int(band.get("min_value")), _int(band.get("id"))))


def _sample_value(rng, template, flesh_rows, bloom_rows, crack_rows):
    flesh = None
    weights = template.get("flesh_quality_weights") or []
    if weights:
        index = _weighted_index(rng, weights)
        flesh = flesh_rows[min(index, len(flesh_rows) - 1)] if flesh_rows else None
    if flesh is None and flesh_rows:
        flesh = flesh_rows[0]
    flesh_id = _int((flesh or {}).get("id"), 1)

    bloom_key = {1: "w_white", 2: "w_green", 3: "w_blue", 4: "w_purple", 5: "w_orange"}.get(flesh_id, "w_white")
    eligible = [bloom for bloom in bloom_rows if _num(bloom.get(bloom_key)) > 0]
    bloom_weights = [_num(bloom.get(bloom_key)) for bloom in eligible]
    bloom_count = _weighted_index(rng, template.get("bloom_count_weights") or [])
    blooms = [_pick(rng, eligible, bloom_weights) for _ in range(bloom_count)]
    blooms = [bloom for bloom in blooms if bloom]

    crack_count = _weighted_index(rng, template.get("crack_count_weights") or [])
    crack_type_weights = template.get("crack_type_weights") or []
    cracks = []
    for _ in range(crack_count):
        index = _weighted_index(rng, crack_type_weights)
        if crack_rows:
            cracks.append(crack_rows[min(index, len(crack_rows) - 1)])
    return compute_value(flesh, blooms, cracks)


def _stats(template, flesh_rows, bloom_rows, crack_rows, bands):
    rng = random.Random(0x5A17 + _int(template.get("item_id")))
    values = [_sample_value(rng, template, flesh_rows, bloom_rows, crack_rows)
              for _ in range(_TEMPLATE_SAMPLES)]
    values.sort()
    count = len(values) or 1
    p10 = values[int(count * 0.10)] if values else 0
    p50 = values[count // 2] if values else 0
    p90 = values[min(count - 1, int(count * 0.90))] if values else 0
    mean = sum(values) / count if values else 0
    spread = p90 / max(1.0, p10)
    if spread < 2.6:
        risk = "稳健"
    elif spread < 4.0:
        risk = "均衡"
    elif spread < 6.0:
        risk = "波动"
    else:
        risk = "高风险"

    band_rows = []
    for band in allowed_bands(bands, _int(template.get("quality")), _int(template.get("item_id"))):
        minimum = _int(band.get("min_value"))
        chance = sum(1 for value in values if value >= minimum) / count
        band_rows.append({
            "id": _int(band.get("id")), "name": band.get("name"),
            "min_value": minimum, "chance": round(chance * 100, 1),
        })
    low_chance = band_rows[0]["chance"] if band_rows else 0
    top_chance = band_rows[-1]["chance"] if band_rows else 0
    if top_chance >= 25:
        style = "冲档"
    elif low_chance >= 85 and spread < 4:
        style = "保底"
    else:
        style = "均衡"
    return {
        "mean": int(round(mean)), "p10": int(round(p10)),
        "p50": int(round(p50)), "p90": int(round(p90)),
        "spread": round(spread, 2), "risk": risk, "style": style,
        "low_chance": low_chance, "top_chance": top_chance,
        "bands": band_rows,
    }


def _condition_info(condition_id, conditions, spaces):
    condition_id = _int(condition_id)
    if not condition_id:
        return {"id": 0, "city_id": 0, "city": "", "need": 0, "text": "常驻"}
    row = conditions.get(str(condition_id)) or {}
    names, values = [], []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "name" and isinstance(value, str) and value not in (
                        "int", "index", "string", "variable"):
                    names.append(value)
                elif key == "value" and isinstance(value, (int, float, str, bool)):
                    values.append(value)
                walk(value)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(row.get("condition"))
    city_id = need = 0
    if "城镇声望至少" in names or "城镇声望至少" in values:
        ints = [value for value in values if isinstance(value, int) and not isinstance(value, bool)]
        if len(ints) >= 2:
            city_id, need = ints[-2], ints[-1]
    city = (spaces.get(str(city_id)) or {}).get("name") or ""
    text = ("%s声望 ≥ %d" % (city, need)) if city else ("声望 ≥ %d" % need if need else "条件 %s" % condition_id)
    return {"id": condition_id, "city_id": city_id, "city": city, "need": need, "text": text}


def _prototype_info(proto_id, prototypes, items, realms):
    proto = prototypes.get(str(proto_id)) or {}
    item = items.get(str(proto_id)) or {}
    name = item.get("name") or _text(proto.get("name")) or ("器胚 %s" % proto_id)
    realm_id = _int(item.get("cultivate_realm"))
    slot = _int(proto.get("slot_type"))
    return {
        "id": _int(proto_id), "name": name,
        "realm": realm_id, "realm_name": realms.get(str(realm_id)) or ("境界%s" % realm_id),
        "slot": slot, "slot_name": SLOT_NAMES.get(str(slot), ""),
    }


def build(tables):
    items_raw = {str(_int(row.get("id"))): row for row in _rows(tables.get("tbitem"))
                 if isinstance(row, dict) and row.get("id") is not None}
    realms = build_realms(tables)
    spaces = build_spaces(tables)

    def item_info(item_id):
        row = items_raw.get(str(item_id)) or {}
        return {
            "id": _int(item_id),
            "name": _text(row.get("itemName")) or ("璞石 %s" % item_id),
            "price": _int(row.get("price")),
            "quality": _int(row.get("quality")),
            "cultivate_realm": _int(row.get("cultivateRealm")),
            "desc": _plain(row.get("itemDesc")),
        }

    descriptions = {}
    for item_id, row in items_raw.items():
        descriptions[item_id] = _plain(row.get("itemDesc"))

    flesh_rows = []
    for row in _rows(tables.get("tbgamblestonefleshquality")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        flesh_rows.append({
            "id": _int(row.get("id")), "name": _text(row.get("name")) or ("玉肉 %s" % row.get("id")),
            "short_name": _text(row.get("short_name")),
            "base_value": _int(row.get("base_value")),
            "anchor_ratio": round(_num(row.get("anchor_ratio"), 0.8), 4),
        })
    flesh_rows.sort(key=lambda row: row["id"])

    crack_rows = []
    for row in _rows(tables.get("tbgamblestonecrack")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        crack_rows.append({
            "id": _int(row.get("id")), "name": _text(row.get("name")) or ("裂痕 %s" % row.get("id")),
            "base_loss": round(_num(row.get("base_loss")), 4),
        })
    crack_rows.sort(key=lambda row: row["id"])

    bloom_rows = []
    for row in _rows(tables.get("tbgamblestonebloom")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        bloom_rows.append({
            "id": _int(row.get("id")), "name": _text(row.get("name")) or ("玉纹 %s" % row.get("id")),
            "rarity": _int(row.get("rarity")),
            "floor_add": round(_num(row.get("floor_add")), 4),
            "ratio_add": round(_num(row.get("ratio_add")), 4),
            "find_stim": _int(row.get("find_stim")),
            "is_legend": bool(row.get("is_legend")),
            "legend_factor": round(_num(row.get("legend_factor")), 4),
            "legend_floor": round(_num(row.get("legend_floor")), 4),
            "w_white": _int(row.get("w_white")), "w_green": _int(row.get("w_green")),
            "w_blue": _int(row.get("w_blue")), "w_purple": _int(row.get("w_purple")),
            "w_orange": _int(row.get("w_orange")),
        })
    bloom_rows.sort(key=lambda row: row["id"])

    prototypes = {}
    for row in _rows(tables.get("tbalchemyprototype")):
        if isinstance(row, dict) and row.get("id") is not None:
            prototypes[str(_int(row.get("id")))] = row

    bands = []
    embryo_ids = set()
    for row in _rows(tables.get("tbgamblestoneembryoexchangeband")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        embryo_ids |= {_int(value) for value in (row.get("embryo_id_list") or []) if _int(value)}
        bands.append(row)

    referenced_items = {}
    for row in _rows(tables.get("tbgamblestonerawtemplate")):
        if isinstance(row, dict) and _int(row.get("item_id")):
            referenced_items[str(_int(row.get("item_id")))] = item_info(row.get("item_id"))
    for embryo_id in embryo_ids:
        referenced_items[str(embryo_id)] = item_info(embryo_id)

    bands_out = []
    for row in bands:
        qualities = [_int(value) for value in (row.get("allowed_stone_quality_list") or []) if _int(value)]
        embryo_list = [_prototype_info(value, prototypes, referenced_items, realms)
                       for value in (row.get("embryo_id_list") or []) if _int(value)]
        prices = [_int(value) for value in (row.get("embryo_price_list") or [])]
        for index, embryo in enumerate(embryo_list):
            if index < len(prices):
                embryo["price"] = prices[index]
        bands_out.append({
            "id": _int(row.get("id")),
            "name": _text(row.get("name")) or ("价格带 %s" % row.get("id")),
            "qualities": qualities,
            "quality_names": [QUALITY_NAMES[q - 1] if 0 < q <= len(QUALITY_NAMES) else str(q) for q in qualities],
            "exclusive_item_id": _int(row.get("exclusive_stone_item_id")),
            "min_value": _int(row.get("min_value")),
            "embryos": embryo_list,
            "remark": _plain(row.get("remark")),
        })
    bands_out.sort(key=lambda band: (1 if band["exclusive_item_id"] else 0,
                                     band["min_value"], band["id"]))

    templates = []
    for row in _rows(tables.get("tbgamblestonerawtemplate")):
        if not isinstance(row, dict) or not _int(row.get("item_id")):
            continue
        item_id = _int(row.get("item_id"))
        info = referenced_items.get(str(item_id)) or item_info(item_id)
        name = info.get("name") or ("璞石 %s" % item_id)
        family, _, variant = name.partition("·")
        template = {
            "item_id": item_id, "name": name, "family": family.strip(),
            "variant": variant.strip() or name, "shape": _int(row.get("shape")),
            "quality": _int(row.get("quality")), "base_price": _int(row.get("base_price")) or info.get("price"),
            "open_float": round(_num(row.get("open_float")), 4),
            "price_factor": round(_num(row.get("price_factor"), 1.0), 4),
            "buy_offer_rule_id": _int(row.get("buy_offer_rule_id")),
            "can_gather_drop": bool(row.get("can_gather_drop")),
            "flesh_quality_weights": [_int(value) for value in (row.get("flesh_quality_weights") or [])],
            "crack_count_weights": [_int(value) for value in (row.get("crack_count_weights") or [])],
            "crack_type_weights": [_int(value) for value in (row.get("crack_type_weights") or [])],
            "bloom_count_weights": [_int(value) for value in (row.get("bloom_count_weights") or [])],
            "desc": descriptions.get(str(item_id), ""),
        }
        template["stats"] = _stats(template, flesh_rows, bloom_rows, crack_rows, bands_out)
        template["exclusive"] = any(_int(band.get("exclusive_item_id")) == item_id
                                    for band in bands_out)
        templates.append(template)
    templates.sort(key=lambda row: (row["quality"], row["item_id"]))

    # 收购商：10 位常驻买家，每位有 3 套报价对话变体，合并成一位。
    base_npcs = {str(_int(row.get("id"))): row for row in _rows(tables.get("tbnpcbasecfg"))
                 if isinstance(row, dict) and row.get("id") is not None}
    buyers = {}
    for row in _rows(tables.get("tbgamblestonebuyoffernpc")):
        if not isinstance(row, dict) or row.get("npc_id") is None:
            continue
        npc_id = _int(row.get("npc_id"))
        base = base_npcs.get(str(npc_id)) or {}
        buyer = buyers.setdefault(npc_id, {
            "id": npc_id,
            "name": _text(base.get("npcName")) or ("收购商 %s" % npc_id),
            "title": _text(base.get("npcTitle")),
            "offer_min": 100, "offer_max": 100, "variants": 0,
        })
        buyer["offer_min"] = min(buyer["offer_min"], _int(row.get("offer_min_percent"), 100))
        buyer["offer_max"] = max(buyer["offer_max"], _int(row.get("offer_max_percent"), 100))
        buyer["variants"] += 1
    buyers_out = sorted(buyers.values(), key=lambda buyer: (-buyer["offer_max"], -buyer["offer_min"], buyer["name"]))

    # 杂货铺货架：按城市声望解锁。
    conditions = {str(_int(row.get("id"))): row for row in _rows(tables.get("tbconditionexpr"))
                  if isinstance(row, dict) and row.get("id") is not None}
    places = {str(_int(row.get("npcId"))): row for row in _rows(tables.get("tbinitialspacenpc"))
              if isinstance(row, dict) and row.get("npcId") is not None}
    stone_ids = {str(template["item_id"]) for template in templates}
    shops = []
    for row in _rows(tables.get("tbnpcbagrule")):
        if not isinstance(row, dict):
            continue
        supplied = [item for item in (row.get("supplyItemList") or [])
                    if isinstance(item, dict) and str(_int(item.get("itemId"))) in stone_ids]
        if not supplied:
            continue
        npc_id = _int(row.get("npcId"))
        base = base_npcs.get(str(npc_id)) or {}
        place = places.get(str(npc_id)) or {}
        space_id = _int(place.get("spaceId"))
        space = spaces.get(str(space_id)) or {}
        path = space.get("path") or []
        city = space.get("region") or (path[0] if path else "")
        shelves = {}
        for item in supplied:
            group = _int(item.get("rotationGroup"))
            cond_id = _int(item.get("dealCondId"))
            key = (group, cond_id)
            shelves.setdefault(key, []).append(item)
        shelf_rows = []
        for (group, cond_id), entries in shelves.items():
            condition = _condition_info(cond_id, conditions, spaces)
            stone_rows = []
            seen = set()
            for entry in entries:
                item_id = _int(entry.get("itemId"))
                if item_id in seen:
                    continue
                seen.add(item_id)
                info = referenced_items.get(str(item_id)) or item_info(item_id)
                stone_rows.append({"id": item_id, "name": info.get("name") or ("璞石 %s" % item_id),
                                   "quality": next((t["quality"] for t in templates if t["item_id"] == item_id), 0),
                                   "price": info.get("price") or 0})
            stone_rows.sort(key=lambda stone: (stone["quality"], stone["id"]))
            shelf_rows.append({"group": group, "condition": condition, "stones": stone_rows})
        shelf_rows.sort(key=lambda shelf: (_int((shelf.get("condition") or {}).get("need")),
                                           _int(shelf.get("group"))))
        shops.append({
            "npc_id": npc_id,
            "name": _text(base.get("npcName")) or ("掌柜 %s" % npc_id),
            "title": (path[-1] if path else "") or _text(base.get("npcTitle")) or "杂货铺",
            "npc_title": _text(base.get("npcTitle")),
            "city": city,
            "space_id": space_id,
            "space_path": " / ".join(path) or city,
            "shelves": shelf_rows,
        })
    shops.sort(key=lambda shop: (shop["city"], shop["name"]))

    constants = {}
    for row in _rows(tables.get("tbconstants")):
        if isinstance(row, dict):
            constants.update({key: value for key, value in row.items()
                              if isinstance(key, str) and key.startswith("GAMBLE_STONE")})
            break

    return {
        "schema": 1,
        "qualities": QUALITY_NAMES,
        "realms": realms,
        "slots": SLOT_NAMES,
        "items": referenced_items,
        "templates": templates,
        "flesh": flesh_rows,
        "cracks": crack_rows,
        "blooms": bloom_rows,
        "bands": bands_out,
        "buyers": buyers_out,
        "shops": shops,
        "constants": {
            "bloom_progress_percent": _int(constants.get("GAMBLE_STONE_BUY_OFFER_BLOOM_PROGRESS_PERCENT"), 10),
            "crack_progress_percent": _int(constants.get("GAMBLE_STONE_BUY_OFFER_CRACK_PROGRESS_PERCENT"), 10),
            "npc_cooldown_turns": _int(constants.get("GAMBLE_STONE_BUY_OFFER_NPC_COOLDOWN_TURNS"), 2),
        },
    }
