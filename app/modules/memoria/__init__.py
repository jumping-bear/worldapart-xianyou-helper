# -*- coding: utf-8 -*-
"""留影石（忆海回溯）：留影、结缘、奇遇留影与故交往事。"""
from meta_update import SCHEMA as DATA_SCHEMA

from .avatars import build_avatars
from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

KEY, LABEL = "memoria", "留影石"
ORDER, SELECT, SCHEMA = 80, "latest", 2  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "memoria_meta.json"
EXTRA_SNAPSHOTS = {"memoria_avatars_meta.json": build_avatars}
TABLES = frozenset({
    "tbmemoriaentry", "tbmemoriabondtype", "tbnpcbasecfg", "tbitem",
    "tbquest", "tbcultivaterealm", "tbnpcintimacy", "tbmonster", "tbtournament",
    "tbnpcinteractgameentry", "tbgameactionflow",
})


def builtin_ok(data):
    return (isinstance(data, dict) and isinstance(data.get("entries"), list)
            and isinstance(data.get("bond_types"), dict))


def empty():
    return {"schema": DATA_SCHEMA, "entries": [], "cast": {}, "bond_types": {},
            "names": {}, "stats": {"entries": 0, "shooting": 0, "bond": 0,
                                   "adventure": 0, "bond_types": 0,
                                   "shooting_reachable": 0, "shooting_blocked": 0}}
