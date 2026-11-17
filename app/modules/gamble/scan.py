# -*- coding: utf-8 -*-
"""赌石：读取存档里的璞石实例、背包库存与城镇声望。"""
import copy
import random

from ...common import bag_entries
from .build import _weighted_index, allowed_bands, compute_value

_MAX_ODDS_SAMPLES = 3200


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bools(values, length):
    values = values if isinstance(values, (list, tuple)) else []
    return [bool(values[index]) if index < len(values) else False for index in range(length)]


def _ints(values):
    return [_int(value) for value in values or [] if _int(value)]


def _first(mapping, keys, default=None):
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        if key in mapping and mapping[key] not in (None, "", [], {}):
            return mapping[key]
    return default


def _offer(raw):
    """收购商报价结构在不同版本里字段名不完全一致，尽量宽松地取。"""
    if not raw:
        return None
    if isinstance(raw, (int, float)):
        return {"price": _int(raw), "percent": 0, "npc_id": 0, "raw": raw}
    if not isinstance(raw, dict):
        return {"price": 0, "percent": 0, "npc_id": 0, "raw": str(raw)[:120]}
    nested = raw.get("npc") if isinstance(raw.get("npc"), dict) else {}
    npc_id = _int(_first(raw, ("npc_id", "npcId", "offer_npc_id", "offerNpcId", "buyer_npc_id"))
                  or _first(nested, ("npc_id", "npcId", "id")))
    price = _int(_first(raw, ("price", "offer_price", "offerPrice", "amount", "value", "money",
                              "spirit_stone", "spiritStone")))
    percent = _float(_first(raw, ("percent", "offer_percent", "offerPercent", "ratio", "rate")))
    if percent and percent <= 1.5:
        percent *= 100
    return {"price": price, "percent": percent, "npc_id": npc_id, "raw": raw}


def meta(metadata):
    return metadata.get("gamble") or {
        "schema": 0, "qualities": ["白", "绿", "蓝", "紫", "橙"], "realms": {"0": "凡人"},
        "slots": {}, "items": {}, "templates": [], "flesh": [], "cracks": [], "blooms": [],
        "bands": [], "buyers": [], "shops": [],
        "constants": {"bloom_progress_percent": 10, "crack_progress_percent": 10,
                      "npc_cooldown_turns": 2},
    }


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    player = obj.get("playerModel") or {}
    gamble = player.get("gamble_stone") or {}
    templates = {str(template.get("item_id")): template
                 for template in (meta_obj.get("templates") or []) if isinstance(template, dict)}
    raw_stones = gamble.get("stones") or {}
    if isinstance(raw_stones, dict):
        entries = list(raw_stones.values())
    elif isinstance(raw_stones, (list, tuple)):
        entries = raw_stones
    else:
        entries = []
    stones = []
    for value in entries:
        if not isinstance(value, dict):
            continue
        item_id = _int(value.get("source_item_id") or value.get("itemId"))
        if str(item_id) not in templates:
            continue
        bloom_ids = _ints(value.get("bloom_ids"))
        crack_ids = _ints(value.get("crack_ids"))
        stones.append({
            "instance_id": _int(value.get("instance_id") or value.get("instanceId")),
            "item_id": item_id,
            "seed": value.get("seed"),
            "generation_pending": bool(value.get("generation_pending")),
            "open_float": round(_float(value.get("open_float")), 4),
            "flesh_quality_id": _int(value.get("flesh_quality_id")),
            "bloom_ids": bloom_ids,
            "bloom_seen": _bools(value.get("bloom_seen"), len(bloom_ids)),
            "crack_ids": crack_ids,
            "crack_seen": _bools(value.get("crack_seen"), len(crack_ids)),
            "reveal_ratio": min(1.0, max(0.0, _float(value.get("reveal_ratio")))),
            "seen_flesh": bool(value.get("seen_flesh")),
            "current_value": _int(value.get("current_value")),
            "exchanged": bool(value.get("exchanged")),
            "exchanged_prototype_id": _int(value.get("exchanged_prototype_id")),
            "created_at": _int(value.get("created_at")),
            "updated_at": _int(value.get("updated_at")),
            "crack_talent": value.get("crack_talent"),
            "bloom_talent": value.get("bloom_talent"),
            "buy_offer": _offer(value.get("buy_offer")),
            "buy_offer_processed": value.get("buy_offer_processed_nodes") or [],
        })

    bag_counts = {}
    for entry in bag_entries(player.get("bag")):
        item_id = _int(entry.get("item_id"))
        if str(item_id) not in templates:
            continue
        bag_counts[item_id] = bag_counts.get(item_id, 0) + max(1, _int(entry.get("count"), 1))

    behavior = player.get("behavior_value") or {}
    reputations = behavior.get("city_reputes") if isinstance(behavior.get("city_reputes"), dict) else {}
    return {
        "stones": stones,
        "bag_counts": {str(key): value for key, value in bag_counts.items()},
        "reputations": {str(key): _int(value) for key, value in reputations.items()},
        "event_round": _int(gamble.get("buy_offer_event_round")),
        "cooldowns": gamble.get("buy_offer_npc_cooldown_until_round") or {},
    }


def post(rows, state, original, path):
    return rows


def _flesh_sample(rng, template, flesh_rows):
    rows = flesh_rows or []
    index = _weighted_index(rng, template.get("flesh_quality_weights") or [])
    return rows[min(index, len(rows) - 1)] if rows else None


def _bloom_sample(rng, flesh_id, bloom_rows):
    key = {1: "w_white", 2: "w_green", 3: "w_blue", 4: "w_purple", 5: "w_orange"}.get(flesh_id, "w_white")
    eligible = [row for row in bloom_rows or [] if _int(row.get(key)) > 0]
    if not eligible:
        return None
    return eligible[min(_weighted_index(rng, [_int(row.get(key)) for row in eligible]), len(eligible) - 1)]


def _crack_sample(rng, template, crack_rows):
    if not crack_rows:
        return None
    index = _weighted_index(rng, template.get("crack_type_weights") or [])
    return crack_rows[min(index, len(crack_rows) - 1)]


def _odds(template, stone, flesh_rows, bloom_rows, crack_rows, bands, exact_value):
    """按“已看见的信息 + 配置权重”推算满解估值分布，不泄露未刮开的具体内容。"""
    if not template:
        return None
    allowed = allowed_bands(bands, _int(template.get("quality")), _int(template.get("item_id")))
    if exact_value is not None and stone.get("reveal_ratio", 0) >= 0.999:
        values = [float(exact_value)]
    else:
        rng = random.Random((_int(stone.get("instance_id")) * 7919 + _int(stone.get("item_id"))) & 0xFFFFFFFF)
        bloom_by_id = {_int(row.get("id")): row for row in bloom_rows or []}
        crack_by_id = {_int(row.get("id")): row for row in crack_rows or []}
        flesh_by_id = {_int(row.get("id")): row for row in flesh_rows or []}
        seen_blooms = [bloom_by_id[item_id] for index, item_id in enumerate(stone.get("bloom_ids") or [])
                       if index < len(stone.get("bloom_seen") or []) and stone["bloom_seen"][index]
                       and item_id in bloom_by_id]
        seen_cracks = [crack_by_id[item_id] for index, item_id in enumerate(stone.get("crack_ids") or [])
                       if index < len(stone.get("crack_seen") or []) and stone["crack_seen"][index]
                       and item_id in crack_by_id]
        seen_flesh = flesh_by_id.get(_int(stone.get("flesh_quality_id"))) if stone.get("seen_flesh") else None
        values = []
        for _ in range(_MAX_ODDS_SAMPLES):
            flesh = seen_flesh or _flesh_sample(rng, template, flesh_rows)
            flesh_id = _int((flesh or {}).get("id"), 1)
            bloom_count = _weighted_index(rng, template.get("bloom_count_weights") or [])
            bloom_count = max(bloom_count, len(seen_blooms))
            blooms = list(seen_blooms) + [
                _bloom_sample(rng, flesh_id, bloom_rows)
                for _ in range(max(0, bloom_count - len(seen_blooms)))
            ]
            crack_count = _weighted_index(rng, template.get("crack_count_weights") or [])
            crack_count = max(crack_count, len(seen_cracks))
            cracks = list(seen_cracks) + [
                _crack_sample(rng, template, crack_rows)
                for _ in range(max(0, crack_count - len(seen_cracks)))
            ]
            values.append(compute_value(flesh, [row for row in blooms if row],
                                        [row for row in cracks if row]))
    values.sort()
    count = len(values) or 1
    band_rows = []
    for band in allowed:
        minimum = _int(band.get("min_value"))
        band_rows.append({
            "id": _int(band.get("id")), "name": band.get("name"), "min_value": minimum,
            "chance": round(100.0 * sum(1 for value in values if value >= minimum) / count, 1),
        })
    return {
        "samples": count,
        "p10": int(round(values[int(count * 0.10)])) if values else 0,
        "p50": int(round(values[count // 2])) if values else 0,
        "p90": int(round(values[min(count - 1, int(count * 0.90))])) if values else 0,
        "mean": int(round(sum(values) / count)) if values else 0,
        "bands": band_rows,
    }


def _advice(stone, bands, estimate, exact=False):
    if stone.get("exchanged"):
        return {"tone": "good", "code": "done", "priority": 0,
                "text": "已兑换器胚 %s，这块璞石不会再有后续收益。" % (stone.get("exchanged_name") or stone.get("exchanged_prototype_id"))}
    if stone.get("generation_pending"):
        return {"tone": "info", "code": "pending", "priority": 1,
                "text": "内容尚未生成，进入赌石界面刮开一次后再来看推算。"}

    current = _int(stone.get("current_value"))
    if not estimate:
        estimate = current
    allowed = sorted(bands or [], key=lambda band: _int(band.get("min_value")))
    lowest = allowed[0] if allowed else None
    hit = None
    next_band = None
    for band in allowed:
        if estimate >= _int(band.get("min_value")):
            hit = band
        elif next_band is None:
            next_band = band
    chance_map = {_int(band.get("id")): _float(band.get("chance"))
                  for band in stone.get("bands") or []}

    offer = stone.get("buy_offer") or {}
    price = _int(offer.get("price"))
    percent = _float(offer.get("percent"))
    if not price and percent:
        price = int(round(current * percent / 100.0))
    if price:
        label = offer.get("npc_name") or "收购商"
        basis = "满解推算" if exact else "满解常见值"
        if price >= estimate * 0.98:
            return {"tone": "good", "code": "sell", "priority": 3,
                    "text": "%s 报价 %d，已达到%s %d，建议出售。" % (label, price, basis, estimate)}
        if price >= estimate * 0.85:
            return {"tone": "warn", "code": "consider", "priority": 2,
                    "text": "%s 报价 %d，低于%s %d；不想再刮可以卖，否则建议拒绝继续开石。"
                            % (label, price, basis, estimate)}
        return {"tone": "bad", "code": "reject", "priority": 3,
                "text": "%s 报价 %d，仅%s的 %d%%；建议拒绝，继续开石或等更高报价。"
                        % (label, price, basis, round(100.0 * price / max(1, estimate)))}

    if lowest and estimate < _int(lowest.get("min_value")):
        if exact:
            return {"tone": "warn", "code": "no-band", "priority": 2,
                    "text": "满解推算 %d，未达最低档 %d；建议出售璞石回血，或继续赌天成玉纹。"
                            % (estimate, _int(lowest.get("min_value")))}
        return {"tone": "warn", "code": "no-band", "priority": 2,
                "text": "按满解常见值推算 %d，最低档命中率约 %.1f%%；可继续刮开博天成玉纹，或出售璞石回血。"
                        % (estimate, chance_map.get(_int(lowest.get("id")), 0))}
    progress = _float(stone.get("reveal_ratio"))
    if progress >= 0.999 and hit:
        return {"tone": "good", "code": "exchange", "priority": 3,
                "text": "已完全解开，可兑换「%s」，余值折灵石。" % (hit.get("name") or "")}
    if next_band:
        if exact:
            target = hit.get("name") if hit else "无"
            return {"tone": "warn", "code": "keep", "priority": 2,
                    "text": "满解推算 %d，达不到下一档「%s」（门槛 %d）；继续刮满可兑换「%s」，或保留璞石等收购商。"
                            % (estimate, next_band.get("name") or "", _int(next_band.get("min_value")), target)}
        chance = chance_map.get(_int(next_band.get("id")), 0)
        return {"tone": "info", "code": "keep", "priority": 2,
                "text": "目标「%s」：门槛 %d；按当前已见信息，命中率约 %.1f%%。继续刮开冲档，完全解开后按实际估价兑换。"
                        % (next_band.get("name") or "", _int(next_band.get("min_value")), chance)}
    if hit:
        return {"tone": "good", "code": "exchange", "priority": 2,
                "text": "已够最高档「%s」，完全解开后去兑换。" % (hit.get("name") or "")}
    return {"tone": "info", "code": "open", "priority": 1,
            "text": "先刮开见肉，再根据估价决定出售或兑换。"}


def enrich(module, meta_obj, state=None):
    raw = module.get("rows") or {}
    templates = {str(template.get("item_id")): template
                 for template in (meta_obj.get("templates") or []) if isinstance(template, dict)}
    flesh_rows = meta_obj.get("flesh") or []
    bloom_rows = meta_obj.get("blooms") or []
    crack_rows = meta_obj.get("cracks") or []
    bands = meta_obj.get("bands") or []
    buyers = {str(buyer.get("id")): buyer for buyer in copy.deepcopy(meta_obj.get("buyers") or [])}
    flesh_by_id = {_int(row.get("id")): row for row in flesh_rows}
    bloom_by_id = {_int(row.get("id")): row for row in bloom_rows}
    crack_by_id = {_int(row.get("id")): row for row in crack_rows}

    stones = []
    for stone in raw.get("stones") or []:
        template = templates.get(str(stone.get("item_id"))) or {}
        quality = _int(template.get("quality"))
        stone_bands = copy.deepcopy(allowed_bands(bands, quality, _int(stone.get("item_id"))))
        flesh = flesh_by_id.get(_int(stone.get("flesh_quality_id")))
        all_blooms = [bloom_by_id[item_id] for item_id in stone.get("bloom_ids") or [] if item_id in bloom_by_id]
        all_cracks = [crack_by_id[item_id] for item_id in stone.get("crack_ids") or [] if item_id in crack_by_id]
        exact_value = None
        if template and flesh and not stone.get("generation_pending"):
            exact_value = int(round(compute_value(flesh, all_blooms, all_cracks)))

        seen_blooms = [row for index, row in enumerate(all_blooms)
                       if index < len(stone.get("bloom_seen") or []) and stone["bloom_seen"][index]]
        seen_cracks = [row for index, row in enumerate(all_cracks)
                       if index < len(stone.get("crack_seen") or []) and stone["crack_seen"][index]]
        odds = _odds(template, stone, flesh_rows, bloom_rows, crack_rows, bands, exact_value)

        for band in stone_bands:
            band["chance"] = next((row.get("chance") for row in (odds or {}).get("bands") or []
                                   if _int(row.get("id")) == _int(band.get("id"))), 0)
            band["hit"] = exact_value is not None and exact_value >= _int(band.get("min_value"))

        estimate = exact_value if exact_value is not None else (odds or {}).get("p50") or stone.get("current_value")
        hit_band = None
        next_band = None
        for band in stone_bands:
            if estimate is not None and estimate >= _int(band.get("min_value")):
                hit_band = band
            elif next_band is None:
                next_band = band

        offer = stone.get("buy_offer")
        if offer:
            buyer = buyers.get(str(offer.get("npc_id"))) or {}
            offer["npc_name"] = buyer.get("name") or ""
            offer["npc_title"] = buyer.get("title") or ""
            offer["range"] = ("%d%%~%d%%" % (buyer.get("offer_min", 0), buyer.get("offer_max", 0))
                              if buyer else "")
            if not offer.get("price") and offer.get("percent"):
                offer["price"] = int(round(_int(stone.get("current_value")) * offer["percent"] / 100.0))

        exchanged_name = ""
        if stone.get("exchanged_prototype_id"):
            for band in bands:
                for embryo in band.get("embryos") or []:
                    if _int(embryo.get("id")) == _int(stone.get("exchanged_prototype_id")):
                        exchanged_name = embryo.get("name") or ""
        stone_out = dict(stone)
        stone_out.update({
            "name": template.get("name") or ("璞石 %s" % stone.get("item_id")),
            "quality": quality,
            "shape": template.get("shape"),
            "base_price": template.get("base_price"),
            "stats": template.get("stats"),
            "flesh": flesh,
            "seen_flesh": flesh if stone.get("seen_flesh") else None,
            "seen_blooms": seen_blooms,
            "seen_cracks": seen_cracks,
            "hidden_blooms": all_blooms,
            "hidden_cracks": all_cracks,
            "exact_value": exact_value,
            "odds": odds,
            "bands": stone_bands,
            "hit_band": hit_band,
            "next_band": next_band,
            "exchanged_name": exchanged_name,
            "progress": round(_float(stone.get("reveal_ratio")) * 100, 1),
        })
        stone_out["advice"] = _advice(
            stone_out, stone_bands, (odds or {}).get("p50") or stone_out.get("current_value"),
            exact=_float(stone_out.get("reveal_ratio")) >= 0.999)
        stone_out["exact_advice"] = (_advice(stone_out, stone_bands, exact_value, exact=True)
                                     if exact_value is not None else None)
        stones.append(stone_out)
    stones.sort(key=lambda row: (bool(row.get("exchanged")), -_float(row.get("updated_at")),
                                 _int(row.get("instance_id"))))

    in_progress = {}
    for stone in stones:
        if not stone.get("exchanged"):
            in_progress[stone.get("item_id")] = in_progress.get(stone.get("item_id"), 0) + 1
    bag_rows = []
    for item_id, owned in (raw.get("bag_counts") or {}).items():
        template = templates.get(str(item_id)) or {}
        if not template:
            continue
        touched = in_progress.get(_int(item_id), 0)
        untouched = max(0, _int(owned) - touched)
        if untouched <= 0:
            continue
        bag_rows.append({
            "item_id": _int(item_id), "name": template.get("name") or ("璞石 %s" % item_id),
            "quality": _int(template.get("quality")), "variant": template.get("variant"),
            "owned": _int(owned), "in_progress": touched, "untouched": untouched,
            "base_price": _int(template.get("base_price")), "stats": template.get("stats"),
            "shape": template.get("shape"), "exclusive": bool(template.get("exclusive")),
        })
    bag_rows.sort(key=lambda row: (-row["quality"], -row["untouched"], row["item_id"]))

    reputations = raw.get("reputations") or {}
    shops = copy.deepcopy(meta_obj.get("shops") or [])
    city_rows = {}
    for shop in shops:
        for shelf in shop.get("shelves") or []:
            condition = shelf.get("condition") or {}
            city_id = _int(condition.get("city_id"))
            need = _int(condition.get("need"))
            current = _int(reputations.get(str(city_id)))
            shelf["current_rep"] = current
            shelf["unlocked"] = need <= 0 or current >= need
            if city_id:
                row = city_rows.setdefault(city_id, {
                    "city_id": city_id, "city": condition.get("city") or shop.get("city") or "",
                    "current": current, "need": 0,
                })
                row["need"] = max(row["need"], need)

    cooldowns = raw.get("cooldowns") or {}
    event_round = _int(raw.get("event_round"))
    buyer_rows = list(buyers.values())
    for buyer in buyer_rows:
        until = _int(cooldowns.get(str(buyer.get("id"))))
        buyer["cooldown_until"] = until if until > event_round else 0
    buyer_rows.sort(key=lambda buyer: (-buyer.get("offer_max", 0), -buyer.get("offer_min", 0),
                                       buyer.get("name") or ""))

    summary_data = {
        "bag_total": sum(_int(value) for value in (raw.get("bag_counts") or {}).values()),
        "untouched": sum(row["untouched"] for row in bag_rows),
        "in_progress": sum(1 for stone in stones if not stone.get("exchanged")),
        "exchanged": sum(1 for stone in stones if stone.get("exchanged")),
        "best_value": max([stone.get("current_value") or 0 for stone in stones] or [0]),
        "event_round": event_round,
    }
    module["rows"] = {
        "stones": stones, "bag": bag_rows, "summary": summary_data,
        "reputation": sorted(city_rows.values(), key=lambda row: row["city"]),
        "event_round": event_round,
    }
    module["templates"] = meta_obj.get("templates") or []
    module["flesh"] = flesh_rows
    module["cracks"] = crack_rows
    module["blooms"] = bloom_rows
    module["bands"] = bands
    module["buyers"] = buyer_rows
    module["shops"] = shops
    module["qualities"] = meta_obj.get("qualities") or []
    module["realms"] = meta_obj.get("realms") or {}
    module["slots"] = meta_obj.get("slots") or {}
    module["constants"] = meta_obj.get("constants") or {}
    return module


def summary(module):
    rows = module.get("rows") or {}
    data = rows.get("summary") or {}
    return "赌石：背包 %d 块（未开 %d），进行中 %d 块，已兑换 %d 块，最高估价 %d" % (
        data.get("bag_total", 0), data.get("untouched", 0), data.get("in_progress", 0),
        data.get("exchanged", 0), data.get("best_value", 0))
