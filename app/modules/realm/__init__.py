# -*- coding: utf-8 -*-
"""境界修为：境界/阶段/层、突破条件，以及突破材料的获取途径图鉴。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "realm", "境界修为"
KEY, LABEL_EN = "realm", "Cultivation"
ORDER, SELECT, SCHEMA = 12, "latest", 13  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "realm_meta.json"
TABLES = frozenset({
    "tbcultivaterealm", "tbcultivatephase", "tbcultivatelayer",
    "tbitem", "tbitemtype", "tbattribute",
    "tbsourceroute", "tbmappoi",
    "tbrewarddrop",
    "tbauctionvenue", "tbauctionitempool",
    "tbtournamentreward",
    "tbworldbossrewardtier", "tbworldbossdungeon",
    "tbsceneexploration",
    "tbnpcbagrule", "tbnpcbasecfg",
    "tbsteal",
    "tbmonster", "tbmonsterteam", "tbspace",
    "tbrandomeventending",
    "tbquest", "tbquesttype", "tbgameactionflow",
    "tbspecialbattle",
})


def builtin_ok(data):
    return (isinstance(data, dict) and isinstance(data.get("realms"), list)
            and isinstance(data.get("materials"), dict)
            and isinstance(data.get("layers"), dict))


def empty():
    return {"schema": DATA_SCHEMA, "realms": [], "phases": {}, "layers": {},
            "materials": {}, "attr_names": {}, "npc_names": {}, "venues": {}}
