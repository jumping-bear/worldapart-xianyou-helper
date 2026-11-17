# -*- coding: utf-8 -*-
"""心法与功法：配装体检与获取路线。

模块契约见 docs/心法功法模块设计.md；只新增本目录与根目录 martial_meta.json。
"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, scan, summary

KEY, LABEL = "martial", "心法与功法"
ORDER, SELECT, SCHEMA = 75, "latest", 1  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "martial_meta.json"
TABLES = frozenset({
    "tbpassiveskill", "tbskill", "tbskilllevel", "tbitem", "tbsect",
    "tbsectintroskill", "tbpassiveskillteachguide", "tbskillteachguide",
    "tbminigamelearngongfa", "tbnpcbasecfg", "tbnpcbagrule", "tbnpcintimacy",
    "tbcultivaterealm", "tbcultivatelayer", "tbelement",
})


def builtin_ok(data):
    return (isinstance(data, dict)
            and isinstance(data.get("core_passives"), list)
            and isinstance(data.get("arts"), list))


def empty():
    return {
        "schema": DATA_SCHEMA, "elements": {"0": "无"}, "realms": {}, "phases": {},
        "layers": {}, "tier_phase": {}, "sects": [], "intimacy": [],
        "core_passives": [], "arts": [], "resonance": [],
        "names": {"npc": {}, "item": {}}, "stats": {"core": 0, "arts": 0, "resonance": 0,
                                                    "books": 0, "excluded": []},
        "warnings": [],
    }
