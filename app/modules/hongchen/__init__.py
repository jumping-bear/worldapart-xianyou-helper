# -*- coding: utf-8 -*-
"""红尘：六条女主恋爱支线的任务树、选项门槛与存档进度。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "hongchen", "红尘"
KEY, LABEL_EN = "hongchen", "Romance"
ORDER, SELECT, SCHEMA = 20, "latest", 29  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "hongchen_meta.json"
TABLES = frozenset({
    "tbquest", "tbquesttype", "tbdialogue", "tbconditionexpr", "tbnpcbasecfg",
    "tbitem", "tbitemtype", "tbgameactionflow", "tbrewarddrop", "tbinteractattribute", "tbspace",
    "tbcultivaterealm", "tbcultivatephase", "tbcultivatelayer",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("lines"), list)


def empty():
    return {"schema": DATA_SCHEMA, "lines": [], "quests": [],
            "states": {}, "types": {}, "attr_names": {}, "spaces": {}, "stats": {
                "lines": 0, "quests": 0, "with_gates": 0, "gates": 0, "branches": 0},
            "done_states": [2, 3], "doing_states": [1, 6]}
