# -*- coding: utf-8 -*-
"""奇遇：结局、奖励与剧情树。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import EVENT_GRADE_NAMES, build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "event", "奇遇"
ORDER, SELECT, SCHEMA = 60, "latest", 23  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "event_meta.json"
TABLES = frozenset({
    "tbrandomeventending", "tbrewarddrop", "tbquest", "tbitem", "tbitemtype",
    "tbspace", "tbcultivaterealm", "tbrandomeventteleportentry",
    "tbspaceactiveevent", "tbinteractaction", "tbspaceinteractui", "tbdialogue",
    "tbgameactionflow", "tbinteractattribute", "tbconditionexpr", "tbpillherb",
    "tbpillrecipe", "tbalchemymaterial", "tbnpcitemdemandholdtemplate",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("events"), list)


def empty():
    return {"schema": DATA_SCHEMA, "events": [], "realms": {"0": "凡人"},
            "grades": EVENT_GRADE_NAMES, "stats": {"events": 0, "endings": 0}}
