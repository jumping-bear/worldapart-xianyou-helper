# -*- coding: utf-8 -*-
"""NPC 物品。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "items", "NPC物品"
KEY, LABEL_EN = "items", "NPC Items"
ORDER, SELECT, SCHEMA = 60, "latest", 23  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "items_meta.json"
TABLES = frozenset({
    "tbnpcbasecfg", "tbspace", "tbcultivaterealm", "tbitem", "tbsteal", "tbitemtype",
    "tbnpcbagrule", "tbnpcitemdemandholdtemplate", "tbnpcintimacy",
    "tbconstants", "tbconstants.ainpc", "tbconstants.alchemy", "tbconstants.auction",
    "tbconstants.difficulty", "tbconstants.guide", "tbconstants.memoria",
    "tbconstants.npccultivation", "tbconstants.quickbattle", "tbconstants.randomevent",
    "tbconstants.roleinteract", "tbconstants.sect", "tbconstants.shooting",
    "tbconstants.story", "tbconstants.tournament", "tbconstants.version",
    "tbconstants.worldboss", "tbrewarddrop",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("items"), dict)


def empty():
    return {"schema": DATA_SCHEMA, "items": {}, "npcs": {}, "spaces": {},
            "realms": {"0": "凡人"}, "gift_pools": {}, "gift_bucket_limits": [],
            "gift_cycle_days": 0, "gift_total_count": 0, "gift_per_npc_count": 0}
