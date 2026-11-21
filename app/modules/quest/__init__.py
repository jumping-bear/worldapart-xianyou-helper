# -*- coding: utf-8 -*-
"""支线：任务状态、奖励、剧情线与前置链路。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import QUEST_STATE_NAMES, build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "quest", "支线"
KEY, LABEL_EN = "quest", "Side Quests"
ORDER, SELECT, SCHEMA = 30, "latest", 52  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "quest_meta.json"
TABLES = frozenset({
    "tbquest", "tbquesttype", "tbrewarddrop", "tbitem", "tbitemtype",
    "tbgameactionflow", "tbnpcbasecfg", "tbspace", "tbcultivaterealm",
    "tbcultivatephase", "tbcultivatelayer", "tbinitialspacenpc",
    "tbconditionexpr", "tbdialogue", "tbinteractattribute",
    "tbinteractaction", "tbspaceinteractui", "tbnpcinteractgameentry", "tbtown",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("quests"), list)


def empty():
    return {"schema": DATA_SCHEMA, "quests": [], "groups": [], "storylines": [],
            "dup_names": {}, "edges": [], "diagnostics": {},
            "realms": {"0": "凡人"}, "layer_phases": {}, "phase_names": {},
            "phase_order": {}, "layer_phase": {},
            "states": {str(k): v for k, v in QUEST_STATE_NAMES.items()},
            "types": {}, "stats": {"quests": 0, "with_rewards": 0, "storylines": 0}}
