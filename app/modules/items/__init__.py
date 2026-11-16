# -*- coding: utf-8 -*-
"""NPC 物品。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "items", "NPC物品"
ORDER, SELECT, SCHEMA = 30, "latest", 21  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "items_meta.json"
TABLES = frozenset({
    "tbnpcbasecfg", "tbspace", "tbcultivaterealm", "tbitem", "tbsteal", "tbitemtype",
    "tbnpcbagrule", "tbnpcitemdemandholdtemplate", "tbnpcintimacy",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("items"), dict)


def empty():
    return {"schema": DATA_SCHEMA, "items": {}, "npcs": {}, "spaces": {},
            "realms": {"0": "凡人"}}
