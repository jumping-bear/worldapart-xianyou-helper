# -*- coding: utf-8 -*-
"""炼器：器胚、材料、法宝与洗练保底。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import FORGE_QUALITY_NAMES, FORGE_SLOT_NAMES, build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "forge", "炼器"
ORDER, SELECT, SCHEMA = 50, "latest", 21  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "forge_meta.json"
TABLES = frozenset({
    "tbalchemyprototype", "tbalchemymaterial", "tbalchemylayout", "tbalchemylevel",
    "tbalchemytalent", "tbalchemyscoretier", "tbalchemyartifactaffixpool",
    "tbalchemywashpity", "tbitem", "tbattribute", "tbelement", "tbcultivaterealm",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("prototypes"), list)


def empty():
    return {"schema": DATA_SCHEMA, "prototypes": [], "materials": {},
            "items": {}, "levels": [], "talents": [], "score_tiers": [],
            "qualities": FORGE_QUALITY_NAMES, "slots": FORGE_SLOT_NAMES,
            "elements": {}, "attributes": {}, "affix_pool": {},
            "pity": [], "realms": {"0": "凡人"}}
