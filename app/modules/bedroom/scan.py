# -*- coding: utf-8 -*-
"""仙居楼互动（成就「十八摸」）扫描。"""
import json
import os
from functools import lru_cache

from ... import common

# 头像快照由留影石（memoria/avatars.py）导出；模块间禁止 import，这里直接读快照文件，
# 文件缺失或格式变化时静默退回首字头像。
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_AVATARS_FILE = os.path.join(_ROOT, "memoria_avatars_meta.json")


@lru_cache(maxsize=1)
def _load_avatars():
    try:
        with open(_AVATARS_FILE, encoding="utf-8-sig") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return {}, {}
    if not isinstance(raw, dict):
        return {}, {}
    images = raw.get("avatars") if isinstance(raw.get("avatars"), dict) else {}
    icons = raw.get("icons") if isinstance(raw.get("icons"), dict) else {}
    clean_images = {str(key): value for key, value in images.items()
                    if isinstance(value, str) and value.startswith("data:image/")}
    clean_icons = {str(key): str(value) for key, value in icons.items()}
    return clean_images, clean_icons


def _avatar_for(npc_id):
    images, icons = _load_avatars()
    key = icons.get(str(npc_id))
    return images.get(key, "") if key else ""


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
                     "resident": len(unlocked) >= 3, "avatar": _avatar_for(cfg)})
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


def merge_rows(rows_list):
    """跨槽位合并同一角色「曾经获得过」的段：每个仙友、每个部位取并集。

    成就「十八摸」按历史累计判定，旧槽位里拿到过的段不能因为换档就消失；
    合并后进度只增不减，新互动会立刻反映出来。
    """
    merged = {}
    for rows in rows_list:
        for row in rows:
            cfg = row.get("cfg")
            if cfg is None:
                continue
            item = merged.get(cfg)
            if item is None:
                item = {"cfg": cfg, "who": "", "bed": "", "labels": {}, "order": [],
                        "got": {}, "resident": False, "avatar": ""}
                merged[cfg] = item
            if row.get("who"):
                item["who"] = row["who"]
            if row.get("bed"):
                item["bed"] = row["bed"]
            if row.get("avatar"):
                item["avatar"] = row["avatar"]
            item["resident"] = item["resident"] or bool(row.get("resident"))
            order = []
            for part in row.get("parts") or []:
                action_id = part.get("id")
                if action_id is None:
                    continue
                order.append(action_id)
                item["labels"][action_id] = (part.get("label")
                                             or item["labels"].get(action_id, str(action_id)))
                item["got"].setdefault(action_id, set()).update(
                    value for value in (part.get("got") or [])
                    if isinstance(value, int) and 0 <= value <= 5)
            if order:
                item["order"] = order
    out = []
    for item in merged.values():
        parts, total = [], 0
        for action_id in (item["order"] or sorted(item["got"])):
            got = sorted(item["got"].get(action_id, ()))
            total += len(got)
            parts.append({"id": action_id, "label": item["labels"].get(action_id, str(action_id)),
                          "got": got, "miss": [i for i in range(6) if i not in got]})
        out.append({"cfg": item["cfg"], "who": item["who"] or ("#%s" % item["cfg"]),
                    "bed": item["bed"], "total": total, "parts": parts,
                    "resident": item["resident"], "avatar": item["avatar"]})
    out.sort(key=lambda row: (-row["total"], str(row["who"])))
    return out


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
