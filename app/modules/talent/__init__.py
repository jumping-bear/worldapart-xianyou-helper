# -*- coding: utf-8 -*-
"""NPC 天赋。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "talent", "NPC天赋"
ORDER, SELECT, SCHEMA = 20, "latest", 23  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "talent_meta.json"
TABLES = frozenset({"tbnpcbasecfg", "tbspace", "tbnpctalent", "tbcultivaterealm"})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("talents"), list)


def empty():
    return {"schema": DATA_SCHEMA, "talents": [], "npcs": {}, "spaces": {},
            "realms": {"0": "凡人"}, "realm_capacity": {}, "phases": {}}
