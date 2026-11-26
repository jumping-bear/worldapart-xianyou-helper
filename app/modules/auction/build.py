# -*- coding: utf-8 -*-
"""拍卖会：配置表 → 模块快照。"""

from meta_update import _int, _rows, _text

FIELDS = ("id", "realm_id", "space_id", "activity_id", "item_count_min", "item_count_max",
          "rare_item_count_min", "rare_item_count_max", "chest_item_count_min",
          "chest_item_count_max", "npc_count_min", "npc_count_max")


def _venues(tables):
    out = []
    for row in _rows(tables["tbauctionvenue"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        item = {key: _int(row.get(key)) for key in FIELDS}
        item["name"] = _text(row.get("venue_name")) or ("拍卖行 %s" % row["id"])
        out.append(item)
    out.sort(key=lambda v: (v["realm_id"], v["id"]))
    return out


def _chests(tables):
    out = []
    for row in _rows(tables["tbauctionchestconfig"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        out.append({
            "id": _int(row.get("id")),
            "realm_id": _int(row.get("realm_id")),
            "chest_type": _int(row.get("chest_type")),
            "name": _text(row.get("chest_name")) or ("珍匣 %s" % row["id"]),
            "cells": _int(row.get("cell_count")),
            "start_min": _int(row.get("start_price_min")),
            "start_max": _int(row.get("start_price_max")),
            "expected": _int(row.get("expected_total_price")),
            "reveal_per_bid": _int(row.get("reveal_per_bid")),
            "init_reveal": _int(row.get("init_reveal_count")),
            "reveal_cap": _int(row.get("reveal_cap_ratio")),
        })
    out.sort(key=lambda c: (c["realm_id"], c["cells"], c["id"]))
    return out


def _tactics(tables):
    out = []
    for row in _rows(tables["tbauctiontactic"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        out.append({
            "id": _int(row.get("id")),
            "name": _text(row.get("tactic_name")) or ("策略 %s" % row["id"]),
            "desc": _text(row.get("tactic_desc")),
            "anger_min": _int(row.get("anger_add_min")),
            "anger_max": _int(row.get("anger_add_max")),
            "limit": _int(row.get("per_item_limit")),
            "rate": _int(row.get("success_rate_base")),
            "lock": bool(row.get("lock_other_cards")),
        })
    out.sort(key=lambda t: t["id"])
    return out


def _loans(tables):
    out = {}
    for row in _rows(tables["tbauctionloan"]):
        if isinstance(row, dict) and row.get("layer_id") is not None:
            out[str(_int(row.get("layer_id")))] = _int(row.get("loan_max"))
    return out


def _hermits(tables):
    out = []
    for row in _rows(tables["tbauctionhermit"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        out.append({
            "id": _int(row.get("id")),
            "realm": _int(row.get("venue_realm")),
            "npc": _int(row.get("npc_id")),
            "note": _text(row.get("note")),
            "weight": _int(row.get("weight")),
            "gold_ratio": _int(row.get("gold_ratio")),
        })
    out.sort(key=lambda h: (h["realm"], h["id"]))
    return out


def _pool(tables):
    out = []
    for row in _rows(tables["tbauctionitempool"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        out.append({
            "id": _int(row.get("id")),
            "realm_id": _int(row.get("realm_id")),
            "generate_type": _int(row.get("generate_type")),
            "param": _int(row.get("type_param1")),
            "quantity": _int(row.get("quantity"), 1),
            "weight": _int(row.get("weight")),
            "finale": bool(row.get("is_finale")),
            "sort": _int(row.get("sort_hint")),
            "rarity": _int(row.get("item_rarity")),
        })
    out.sort(key=lambda p: (p["realm_id"], p["sort"], p["id"]))
    return out


def _items(tables):
    types = {}
    for row in _rows(tables["tbitemtype"]):
        if isinstance(row, dict) and row.get("id") is not None:
            types[str(row["id"])] = _text(row.get("typeName"))
    out = {}
    for row in _rows(tables["tbitem"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        out[str(row["id"])] = {
            "name": _text(row.get("itemName")) or ("未识别物品"),
            "type": types.get(str(row.get("itemType")), "") or "未分类",
            "quality": row.get("quality"),
            "price": _int(row.get("price")),
        }
    return out


def _realms(tables):
    realms, phases = {"0": "凡人"}, []
    for row in _rows(tables["tbcultivaterealm"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        name = _text(row.get("realm_name")) or ("境界%s" % row["id"])
        realms[str(row["id"])] = name
        raw = row.get("phases") or []
        starts = [_int(v) for v in raw if _int(v)]
        if starts:
            phases.append({"realm": _int(row["id"]), "name": name, "start": min(starts)})
    phases.sort(key=lambda p: p["start"])
    return realms, phases


def build(tables):
    realms, phases = _realms(tables)
    items = _items(tables)
    data = {
        "schema": 1,
        "venues": _venues(tables),
        "chests": _chests(tables),
        "tactics": _tactics(tables),
        "loans": _loans(tables),
        "hermits": _hermits(tables),
        "pool": _pool(tables),
        "items": items,
        "realms": realms,
        "phases": phases,
        "warnings": [],
    }
    if not data["venues"]:
        raise ValueError("拍卖行配置为空")
    if not items:
        raise ValueError("物品配置为空")
    data["stats"] = {
        "venues": len(data["venues"]),
        "chests": len(data["chests"]),
        "tactics": len(data["tactics"]),
        "hermits": len(data["hermits"]),
        "pool": len(data["pool"]),
        "items": len(items),
    }
    return data
