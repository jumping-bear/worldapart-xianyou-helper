# -*- coding: utf-8 -*-
"""赌石：璞石库存、开石进度、兑换价格带与收购商参考。"""
from .build import QUALITY_NAMES, build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "gamble", "赌石"
ORDER, SELECT, SCHEMA = 55, "latest", 2  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "gamble_meta.json"
TABLES = frozenset({
    "tbgamblestonerawtemplate", "tbgamblestonefleshquality", "tbgamblestonecrack",
    "tbgamblestonebloom", "tbgamblestoneembryoexchangeband",
    "tbgamblestonebuyoffernpc",
    "tbitem", "tbalchemyprototype", "tbcultivaterealm",
    "tbnpcbasecfg", "tbnpcbagrule", "tbinitialspacenpc", "tbspace",
    "tbconditionexpr", "tbconstants",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("templates"), list)


def empty():
    return {"schema": 0, "qualities": QUALITY_NAMES, "realms": {"0": "凡人"},
            "slots": {}, "items": {}, "templates": [], "flesh": [], "cracks": [],
            "blooms": [], "bands": [], "buyers": [], "shops": [],
            "constants": {"bloom_progress_percent": 10, "crack_progress_percent": 10,
                          "npc_cooldown_turns": 2}}
