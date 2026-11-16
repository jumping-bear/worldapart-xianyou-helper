# -*- coding: utf-8 -*-
"""仙居楼互动（成就「十八摸」）扫描。"""
from ... import common


def scan_bedroom(obj, meta):
    rows = []
    for npc in (obj.get("npcs") or {}).values():
        if not isinstance(npc, dict):
            continue
        bedroom = npc.get("bedroom") or {}
        cfg = npc.get("npcCfgId")
        info = meta.get(cfg) or {}
        unlocked = bedroom.get("unlocked") or []
        actions = [a["id"] for a in (info.get("actions") or []) if a.get("id") is not None][:3]
        if not actions:
            try:
                actions = sorted(unlocked)[:3]
            except TypeError:
                actions = []
        if not actions:
            continue
        labels = {a["id"]: a.get("label") or a.get("slot") or str(a["id"])
                  for a in (info.get("actions") or []) if a.get("id") is not None}
        completed = bedroom.get("completed_touch_feedbacks") or {}
        parts, total = [], 0
        for action in actions:
            got = sorted(v for v in (completed.get(action) or []) if isinstance(v, int) and 0 <= v <= 5)
            total += len(got)
            parts.append({"id": action, "label": labels.get(action, str(action)), "got": got,
                          "miss": [i for i in range(6) if i not in got]})
        rows.append({"cfg": cfg, "who": info.get("npcName") or ("#%s" % cfg),
                     "bed": info.get("bedroom") or "", "total": total, "parts": parts,
                     "resident": len(unlocked) >= 3})
    rows.sort(key=lambda r: (-r["total"], str(r["who"])))
    return rows


def meta(metadata):
    return {int(r["cfg"]): r for r in metadata.get("bedroom", [])
            if isinstance(r, dict) and r.get("cfg") is not None}


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    return scan_bedroom(obj, meta_obj)


def post(rows, state, original, path):
    return rows


def score(rows):
    return sum(row["total"] for row in rows)


def enrich(module, meta_obj, state=None):
    return module


def summary(module):
    rows = module.get("rows") or []
    return "仙居楼互动：%d 位仙友，已满 18/18：%d 位" % (
        len(rows), sum(1 for r in rows if r["total"] >= 18))


def scan_legacy(path, meta_obj):
    """兼容旧调用：读取一个副本并返回仙居楼互动进度。"""
    with open(path, "rb") as f:
        return scan_bedroom(common.unpack(f.read()), meta_obj)
