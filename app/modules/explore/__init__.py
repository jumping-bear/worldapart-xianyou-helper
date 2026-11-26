# -*- coding: utf-8 -*-
"""探索：五项探索属性的本月互动入口、切磋次数与委托目标。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import scan, summary

KEY, LABEL = "explore", "探索"
KEY, LABEL_EN = "explore", "Exploration"
ORDER, SELECT, SCHEMA = 35, "latest", 4  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "explore_meta.json"
TABLES = frozenset({
    "tbnpcbasecfg", "tbspace", "tbinteractattribute",
    "tbnpcinteractgameentry", "tbnpcinteractiongroup",
    "tbrewarddrop", "tbitem", "tbcommissionforce", "tbcommissiontaskpool",
    "tbcommissionforcetaskrefresh", "tbquest", "tbgameactionflow",
})


def builtin_ok(data):
    return (isinstance(data, dict) and isinstance(data.get("entries"), dict)
            and isinstance(data.get("attributes"), list))


def empty():
    return {"schema": DATA_SCHEMA, "const": {"spar_type": 0},
            "attributes": [], "entries": {}, "npcs": {}, "groups": {}, "spaces": {},
            "tasks": {}, "item_names": {}, "exp_ranges": []}
