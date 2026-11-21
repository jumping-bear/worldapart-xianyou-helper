# -*- coding: utf-8 -*-
"""城镇声望：委托、称号与货架解锁。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "reputation", "声望"
KEY, LABEL_EN = "reputation", "Town Reputation"
ORDER, SELECT, SCHEMA = 96, "latest", 3  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "reputation_meta.json"
TABLES = frozenset({
    "tbtown", "tbcityreputation", "tbcityreputationtitle", "tbreputationtitle",
    "tbcommissionforce", "tbcommissionforcetaskrefresh", "tbcommissiontaskpool",
    "tbquest", "tbrewarddrop", "tbitem", "tbnpcbagrule", "tbnpcbasecfg",
    "tbconditionexpr",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("towns"), list)


def empty():
    return {"schema": DATA_SCHEMA, "towns": [], "active_count": 0,
            "shelf_count": 0, "warnings": []}
