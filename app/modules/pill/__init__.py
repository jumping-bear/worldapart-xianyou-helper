# -*- coding: utf-8 -*-
"""炼丹：丹方手记、炉子与盘面拾取点。"""
from meta_update import CACHE_SCHEMA, SCHEMA as DATA_SCHEMA

from .build import build, build_pill_map
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "pill", "炼丹"
ORDER, SELECT, SCHEMA = 40, "latest", CACHE_SCHEMA
SNAPSHOT = "pill_meta.json"
TABLES = frozenset({
    "tbitem", "tbpillrecipe", "tbpillherb", "tbpillsecretportal", "tbpillfurnace",
    "tbpilllevel", "tbcultivaterealm", "tbpillportal", "tbpilleffect",
    "tbpillexplorepoi", "tbattribute",
})
# 炼丹盘面是独立资源，导出快照时与 pill_meta.json 一起写。
EXTRA_SNAPSHOTS = {"pill_map.json": build_pill_map}


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("recipes"), list)


def empty():
    return {"schema": DATA_SCHEMA, "recipes": [], "herbs": [], "portals": [],
            "furnaces": [], "levels": {}, "realms": {"0": "凡人"}}
