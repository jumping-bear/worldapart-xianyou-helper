# -*- coding: utf-8 -*-
"""留影石（忆海回溯）：配置表 → 模块快照。

只保留展示所需的中文字段，不整表落盘（物品/任务表三语原文体积过大）。
"""
from meta_update import SCHEMA, _int, _plain, _rows, _text


def _clean(value):
    """去富文本标签与零宽字符（配置表里有「友善\\u200b」这类脏数据）。"""
    return _text(value).replace("\u200b", "").strip()


def _quest_rows(table):
    """tbquest 是 {rows: [...], overrides: [...]}，只取 rows。"""
    if isinstance(table, dict) and isinstance(table.get("rows"), list):
        return [row for row in table["rows"] if isinstance(row, dict)]
    return [row for row in _rows(table) if isinstance(row, dict)]


def _name_map(table, field):
    names = {}
    for row in _rows(table):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        names[str(_int(row["id"]))] = _clean(row.get(field))
    return names


def _npc_cast(tables, npc_ids):
    """留影/结缘涉及的角色档案：头像资源不可用，只存文字字段。"""
    cast = {}
    for row in _rows(tables["tbnpcbasecfg"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        npc_id = _int(row["id"])
        if npc_id not in npc_ids:
            continue
        cast[str(npc_id)] = {
            "name": _clean(row.get("npcName")) or ("NPC %s" % npc_id),
            "title": _clean(row.get("npcTitle")),
            "gender": _int(row.get("gender")),
            "pet": bool(row.get("isPet")),
            "layer": _clean(row.get("layerZeroShowText")),
        }
    return cast


def _bond_types(tables):
    """存档 bond_logs 的记录类型：只保留游戏内会展示且文案非空的类型。"""
    types = {}
    for row in _rows(tables["tbmemoriabondtype"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        if not row.get("show"):
            continue
        text = _plain(row.get("text"))
        if not text:
            continue
        types[str(_int(row["id"]))] = {
            "name": _clean(row.get("name")),
            "group": _clean(row.get("group")),
            "stat": _int(row.get("stat")),
            "arg": _int(row.get("arg")),
            "text": text,
        }
    return types


def _realms(tables):
    realms, phases = {}, {}
    for row in _rows(tables["tbcultivaterealm"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        realm_id = _int(row["id"])
        name = _clean(row.get("realm_name")) or ("境界 %s" % realm_id)
        realms[str(realm_id)] = name
        for phase in row.get("phases") or []:
            phases[str(_int(phase))] = name
    return realms, phases


def _intimacies(tables):
    return {str(_int(row.get("id"))): _clean(row.get("intimacyName"))
            for row in _rows(tables["tbnpcintimacy"])
            if isinstance(row, dict) and row.get("id") is not None}


def build_memoria(tables):
    entries = []
    npc_ids = set()
    for row in _rows(tables["tbmemoriaentry"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        category = _int(row.get("category"))
        npc_id = _int(row.get("npc_id"))
        if npc_id:
            npc_ids.add(npc_id)
        entries.append({
            "id": _int(row["id"]), "cat": category, "npc": npc_id,
            "title": _plain(row.get("title")), "hint": _plain(row.get("locked_hint")),
            "hidden": bool(row.get("hide_when_locked")),
            "sort": _int(row.get("sort")),
            "quest": _int(row.get("event_quest_id")),
            "realm": _int(row.get("realm")),
        })
    if not entries:
        raise ValueError("留影石配置为空")

    quests = _quest_rows(tables["tbquest"])
    quest_by_id = {}
    for row in quests:
        if row.get("id") is not None:
            quest_by_id[_int(row["id"])] = row

    realms, phases = _realms(tables)
    for entry in entries:
        if entry["cat"] != 3:
            continue
        quest = quest_by_id.get(entry["quest"]) or {}
        entry["event_name"] = _clean(quest.get("name")) or ("奇遇 %s" % entry["quest"])
        entry["event_desc"] = _plain(quest.get("description"))
        entry["realm_name"] = realms.get(str(entry["realm"])) or ""

    bond_types = _bond_types(tables)
    if not bond_types:
        raise ValueError("留影石故交类型配置为空")

    names = {
        "npc": _name_map(tables["tbnpcbasecfg"], "npcName"),
        "item": _name_map(tables["tbitem"], "itemName"),
        "quest": {str(_int(row["id"])): _clean(row.get("name"))
                  for row in quests if row.get("id") is not None},
        "monster": _name_map(tables["tbmonster"], "name"),
        "realm": realms,
        "phase": phases,
        "intimacy": _intimacies(tables),
        "tournament": _name_map(tables["tbtournament"], "name"),
    }
    stats = {
        "entries": len(entries),
        "shooting": sum(1 for row in entries if row["cat"] == 1),
        "bond": sum(1 for row in entries if row["cat"] == 2),
        "adventure": sum(1 for row in entries if row["cat"] == 3),
        "bond_types": len(bond_types),
    }
    entries.sort(key=lambda row: (row["cat"], row["sort"], row["id"]))
    return {
        "schema": SCHEMA,
        "entries": entries,
        "cast": _npc_cast(tables, npc_ids),
        "bond_types": bond_types,
        "names": names,
        "stats": stats,
    }


# 插件统一入口
build = build_memoria
