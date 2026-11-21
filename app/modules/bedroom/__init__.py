# -*- coding: utf-8 -*-
"""仙居楼互动（成就「十八摸」）。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import (enrich, merge_rows as merge, meta, post, prepare, scan, scan_legacy,
                   score, summary)

KEY, LABEL = "bedroom", "仙居楼互动"
KEY, LABEL_EN = "bedroom", "Joy House"
ORDER, SELECT, SCHEMA = 98, "merge", 21  # 模块自有缓存版本，改数据结构时只递增这里
# 成就「十八摸」按“曾经获得过”的段累计，不能只看最新档；合并同一角色所有槽位，
# 每个仙友、每个部位取并集，互动后进度只增不减。
SNAPSHOT = "bedroom_meta.json"
TABLES = frozenset({
    "tbnpcbasecfg", "tbnpcbedroom", "tbscenepresentationinteraction",
    "tbscenepresentationaction",
})


def builtin_ok(data):
    return isinstance(data, list)


def empty():
    return []
