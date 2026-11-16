# -*- coding: utf-8 -*-
"""仙居楼互动（成就「十八摸」）。"""
from meta_update import CACHE_SCHEMA, SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, scan_legacy, score, summary

KEY, LABEL = "bedroom", "仙居楼互动"
ORDER, SELECT, SCHEMA = 10, "best", CACHE_SCHEMA
SNAPSHOT = "bedroom_meta.json"
TABLES = frozenset({
    "tbnpcbasecfg", "tbnpcbedroom", "tbscenepresentationinteraction",
    "tbscenepresentationaction",
})


def builtin_ok(data):
    return isinstance(data, list)


def empty():
    return []
