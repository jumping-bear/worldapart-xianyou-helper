# -*- coding: utf-8 -*-
"""红尘：六条女主恋爱支线的任务树、选项门槛与存档进度。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "hongchen", "红尘"
ORDER, SELECT, SCHEMA = 90, "latest", 1
SNAPSHOT = "hongchen_meta.json"
TABLES = frozenset({
    "tbquest", "tbquesttype", "tbdialogue", "tbconditionexpr", "tbnpcbasecfg",
    "tbitem", "tbgameactionflow", "tbrewarddrop", "tbinteractattribute",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("lines"), list)


def empty():
    return {"schema": DATA_SCHEMA, "lines": [], "quests": [],
            "states": {}, "types": {}, "attr_names": {}, "stats": {
                "lines": 0, "quests": 0, "with_gates": 0, "gates": 0, "branches": 0},
            "done_states": [2, 3], "doing_states": [1, 6]}
