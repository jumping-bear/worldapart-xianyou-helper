# -*- coding: utf-8 -*-
"""NPC 物品扫描。"""


def bag_items(bag):
    """取出背包持有关系 [(item_id, count)]，兼容列表与字典两种存档形态。"""
    entries = bag.get("items") if isinstance(bag, dict) else bag
    result = []
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2 and isinstance(entry[1], dict):
                entry = entry[1]
            if not isinstance(entry, dict):
                continue
            item_id = entry.get("item_id", entry.get("itemId", entry.get("id")))
            if item_id is None:
                continue
            result.append([item_id, entry.get("count") or entry.get("num") or 1])
    elif isinstance(entries, dict):
        for key, entry in entries.items():
            if isinstance(entry, dict):
                item_id = entry.get("item_id", entry.get("itemId", entry.get("id", key)))
                result.append([item_id, entry.get("count") or entry.get("num") or 1])
            else:
                try:
                    result.append([int(key), int(entry)])
                except (TypeError, ValueError):
                    continue
    return result


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _gift_bucket(layer, limits):
    """按配置派生出的层数边界分档，对应四张 AI 赠礼掉落表。"""
    if layer is None:
        return "1"
    value = _as_int(layer, 0)
    for index, limit in enumerate(limits or []):
        if value <= _as_int(limit, 0):
            return str(index + 1)
    return "4"


def scan_items(obj, meta):
    """收集 NPC 背包持有关系；可赠礼按赠礼池 ∩ 背包实物 ∩ 非货架货计算。"""
    npc_meta = meta.get("npcs") or {}
    space_meta = meta.get("spaces") or {}
    spaces = obj.get("spaces") or {}
    gift_pools = meta.get("gift_pools") or {}
    gift_limits = meta.get("gift_bucket_limits") or []
    gift_per_npc = _as_int(meta.get("gift_per_npc_count"), 10)
    player = obj.get("playerModel") or {}
    player_layer = (player.get("combat") or {}).get("cultivate_layer_id")
    reward_state = player.get("ainpcChatReward") or {}
    gift_used_by_npc = {}
    for key, value in (reward_state.get("perNpcUsedCounts") or {}).items():
        gift_used_by_npc[_as_int(key, -1)] = _as_int(value)
    rows = []
    for uid, npc in (obj.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        held = bag_items(npc.get("bag"))
        if not held:
            continue
        merged = {}
        for item_id, count in held:
            key = str(item_id)
            merged[key] = merged.get(key, 0) + (count or 1)
        held = [[int(key) if key.isdigit() else key, total] for key, total in merged.items()]
        cfg = npc.get("npcCfgId")
        info = npc_meta.get(str(cfg)) or {}
        npc_layer = (npc.get("cultivation_state") or {}).get("cultivate_layer_id")
        player_bucket = _as_int(_gift_bucket(player_layer, gift_limits), 4)
        npc_bucket = _as_int(_gift_bucket(npc_layer, gift_limits), 4)
        bucket = str(min(player_bucket, npc_bucket))
        pool = set(_as_int(x, -1) for x in (gift_pools.get(bucket) or []))
        supply = set(_as_int(x, -1) for x in (info.get("supply") or []))
        gift_ids = sorted(iid for iid, _count in held
                          if isinstance(iid, int) and iid in pool and iid not in supply)
        used = gift_used_by_npc.get(_as_int(cfg, -1), 0)
        space = spaces.get(npc.get("currentSpaceUuid")) or {}
        space_info = space_meta.get(str(space.get("spaceId"))) or {}
        path = space_info.get("path") or []
        location = space_info.get("name") or "未知地点"
        try:
            intimacy = int(npc.get("intimacy") or 0)
        except (TypeError, ValueError):
            intimacy = 0
        rows.append({
            "uid": str(uid), "cfg": cfg,
            "who": info.get("name") or ("#%s" % cfg),
            "realm": info.get("realm") or "",
            "location": location, "region": space_info.get("region") or "",
            "location_path": " / ".join(path) or location,
            "can_steal": bool(info.get("can_steal")),
            "intimacy": intimacy,
            "demand": list(info.get("demand") or []),
            "items": held,
            "gift": gift_ids,
            "gift_used": used,
            "gift_left": max(0, gift_per_npc - used) if gift_per_npc else 0,
        })
    rows.sort(key=lambda r: (str(r["who"]), str(r["uid"])))
    return rows


def meta(metadata):
    empty = {"items": {}, "npcs": {}, "spaces": {}, "realms": {"0": "凡人"}}
    return metadata.get("items") or dict(empty)


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    return scan_items(obj, meta_obj)


def post(rows, state, original, path):
    return rows


def enrich(module, meta_obj, state=None):
    catalog = meta_obj.get("items") or {}
    used = {str(item_id) for row in module["rows"] for item_id, _count in row["items"]}
    used |= {str(item_id) for row in module["rows"] for item_id in (row.get("demand") or [])}
    module["catalog"] = [dict(catalog[key], id=int(key)) for key in sorted(used, key=int)
                         if key in catalog]
    module["realms"] = meta_obj.get("realms") or {"0": "凡人"}
    module["intimacy"] = meta_obj.get("intimacy") or []
    for key in ("gift_pools", "gift_bucket_limits", "gift_cycle_days",
                "gift_total_count", "gift_per_npc_count"):
        module[key] = meta_obj.get(key)
    return module


def summary(module):
    rows = module.get("rows") or []
    catalog = {str(t["id"]): t for t in module.get("catalog") or []}
    pairs = sum(len(r["items"]) for r in rows)
    stealable = sum(1 for r in rows if r["can_steal"]
                    for item_id, _ in r["items"]
                    if (catalog.get(str(item_id)) or {}).get("steal"))
    giftable = sum(len(r.get("gift") or []) for r in rows)
    return "NPC物品：%d 位 NPC，%d 条持有记录，可偷 %d 条，可赠 %d 件" % (
        len(rows), pairs, stealable, giftable)
