# -*- coding: utf-8 -*-
"""宗门：职位晋升、贡献兑换、宗门任务与灵材征收。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "sect", "宗门"
ORDER, SELECT, SCHEMA = 85, "latest", 5  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "sect_meta.json"
TABLES = frozenset({
    "tbsect", "tbsectposition", "tbsectreputation", "tbsecttaskpool",
    "tbsectpurchaseorder", "tbsectpositionquest", "tbsectconstants",
    "tbquest", "tbrewarddrop", "tbitem", "tbitemtype", "tbnpcbasecfg",
    "tbnpcbagrule", "tbconditionexpr", "tbcultivaterealm", "tbspace",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("sects"), list) \
        and isinstance(data.get("positions"), list)


def empty():
    return {"schema": DATA_SCHEMA, "sects": [], "positions": [], "realms": {"0": "凡人"},
            "phases": {}, "constants": {}, "career": [], "warnings": []}
