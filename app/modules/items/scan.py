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


def scan_items(obj, meta):
    """收集 NPC 背包持有关系；是否可偷由 NPC 的 can_steal 和物品 steal 参数共同决定。"""
    npc_meta = meta.get("npcs") or {}
    space_meta = meta.get("spaces") or {}
    spaces = obj.get("spaces") or {}
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
    return module


def summary(module):
    rows = module.get("rows") or []
    catalog = {str(t["id"]): t for t in module.get("catalog") or []}
    pairs = sum(len(r["items"]) for r in rows)
    stealable = sum(1 for r in rows if r["can_steal"]
                    for item_id, _ in r["items"]
                    if (catalog.get(str(item_id)) or {}).get("steal"))
    return "NPC物品：%d 位 NPC，%d 条持有记录，可偷 %d 条" % (len(rows), pairs, stealable)
