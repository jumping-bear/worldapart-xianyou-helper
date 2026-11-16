# -*- coding: utf-8 -*-
"""支线：任务状态、奖励、剧情线与前置链路。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import QUEST_STATE_NAMES, build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "quest", "支线"
ORDER, SELECT, SCHEMA = 70, "latest", 21  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "quest_meta.json"
TABLES = frozenset({
    "tbquest", "tbrewarddrop", "tbitem", "tbitemtype", "tbgameactionflow",
    "tbnpcbasecfg", "tbspace", "tbcultivaterealm", "tbconditionexpr",
})


def builtin_ok(data):
    return isinstance(data, dict) and isinstance(data.get("quests"), list)


def empty():
    return {"schema": DATA_SCHEMA, "quests": [], "groups": [], "realms": {"0": "凡人"},
            "states": {str(k): v for k, v in QUEST_STATE_NAMES.items()},
            "types": {}, "stats": {"quests": 0, "with_rewards": 0}}
