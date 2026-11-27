# -*- coding: utf-8 -*-
"""宗门：职位晋升、贡献兑换、宗门任务与灵材征收。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "sect", "宗门"
KEY, LABEL_EN = "sect", "Sect"
ORDER, SELECT, SCHEMA = 94, "latest", 6  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "sect_meta.json"
# 宗门任务走游戏现行「委托」系统（tbcommission*，force_type=2），
# 旧执事堂的 tbsecttaskpool / tbsectpurchaseorder 已从快照移除（游戏内无入口）。
TABLES = frozenset({
    "tbsect", "tbsectposition", "tbsectreputation",
    "tbsectpositionquest", "tbsectconstants",
    "tbcommissionforce", "tbcommissionforcetaskrefresh", "tbcommissiontaskpool",
    "tbconstants",
    "tbquest", "tbrewarddrop", "tbitem", "tbitemtype", "tbnpcbasecfg",
    "tbnpcbagrule", "tbconditionexpr", "tbcultivaterealm", "tbspace",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("sects"), list) \
        and isinstance(data.get("positions"), list)


def empty():
    return {"schema": DATA_SCHEMA, "sects": [], "positions": [], "realms": {"0": "凡人"},
            "phases": {}, "constants": {}, "career": [], "warnings": []}
