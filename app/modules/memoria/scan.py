# -*- coding: utf-8 -*-
"""留影石扫描：存档里的忆海收录、已看标记与故交往事时间线。"""
import datetime
import json
import os
import re
from functools import lru_cache

# 头像快照由 avatars.py 单独导出；缺失时页面退回首字头像
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_AVATARS_FILE = os.path.join(_ROOT, "memoria_avatars_meta.json")

# 存档 stats 的键 → 展示文案（对应 tbmemoriabondtype.stat）
STAT_LABELS = {"1": "传音", "2": "切磋", "3": "赠礼", "4": "托付", "5": "买卖", "6": "受赠"}

# {0} 无法解析时的降级名词，避免出现「」空壳
FALLBACK_ARG = {
    1: "一件物品", 2: "一桩事", 3: "某个交情", 4: "一段留影", 5: "一场胜负",
    6: "一场赛事", 7: "一场劫难", 8: "一门功法", 9: "旧事", 10: "新的境界",
    11: "一头妖兽",
}

_DATE_BASE = datetime.datetime(1, 1, 1)
_MAX_TICKS = 3000000000000000000  # 约公元 9500 年，超出视为异常值


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _date(ticks):
    ticks = _int(ticks)
    if not ticks or ticks <= 0 or ticks >= _MAX_TICKS:
        return ""
    try:
        return (_DATE_BASE + datetime.timedelta(microseconds=ticks // 10)).strftime("%Y-%m-%d")
    except (OverflowError, ValueError):
        return ""


def _int_map(raw):
    result = {}
    if not isinstance(raw, dict):
        return result
    for key, value in raw.items():
        key_int = _int(key)
        value_int = _int(value)
        if key_int is None or value_int is None:
            continue
        result[key_int] = value_int
    return result


def _int_set(raw):
    result = set()
    for value in raw or []:
        value_int = _int(value)
        if value_int is not None:
            result.add(value_int)
    return result


@lru_cache(maxsize=1)
def _load_avatars():
    """读导出阶段生成的头像快照；文件缺失或损坏时静默退回首字头像。"""
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
    if key:
        return images.get(key, "")
    # 兼容旧版「NPC id 直接作 key」的头像快照
    return images.get(str(npc_id), "")


def _resolve_arg(kind, arg, names):
    """把 bond 记录的 arg 还原成可读名称；解析不到返回空串。"""
    key = str(_int(arg, arg))
    if kind in (1, 8):
        return (names.get("item") or {}).get(key) or ""
    if kind == 2:
        return (names.get("quest") or {}).get(key) or ""
    if kind == 3:
        return (names.get("intimacy") or {}).get(key) or ""
    if kind == 6:
        return (names.get("tournament") or {}).get(key) or ""
    if kind == 9:
        return (names.get("npc") or {}).get(key) or ""
    if kind == 10:
        return ((names.get("realm") or {}).get(key)
                or (names.get("phase") or {}).get(key) or "")
    if kind == 11:
        return (names.get("monster") or {}).get(key) or ""
    return ""


def _bond_text(bond_type, npc_name, arg, names):
    text = (bond_type.get("text") or "").strip()
    if not text:
        return ""
    text = text.replace("{ta}", npc_name)
    if "{0}" in text:
        value = _resolve_arg(_int(bond_type.get("arg"), 0), arg, names)
        if not value:
            value = FALLBACK_ARG.get(_int(bond_type.get("arg"), 0), "此事")
        text = text.replace("{0}", value)
    text = re.sub(r"[，、]{2,}", "，", text).strip(" ，、。")
    return text


def _day_text(day):
    return ("第 %d 天" % day) if day and day > 0 else "往昔某日"


def _friend_rows(mem, meta_obj):
    names = (meta_obj.get("names") or {})
    bond_types = (meta_obj.get("bond_types") or {})
    cast = (meta_obj.get("cast") or {})
    logs = mem.get("bond_logs") or {}
    rows = []
    for key, slot in logs.items():
        npc_id = _int(key)
        if npc_id is None or not isinstance(slot, dict):
            continue
        npc_key = str(npc_id)
        name = ((names.get("npc") or {}).get(npc_key)
                or (cast.get(npc_key) or {}).get("name") or ("NPC %s" % npc_id))
        grouped, total = {}, 0
        for record in slot.get("records") or []:
            if not isinstance(record, dict):
                continue
            type_id = _int(record.get("type"))
            bond_type = bond_types.get(str(type_id))
            if not bond_type:
                continue
            text = _bond_text(bond_type, name, record.get("arg"), names)
            if not text:
                continue
            day = _int(record.get("day"), 0)
            merge_key = (type_id, str(record.get("arg")), day)
            if merge_key in grouped:
                grouped[merge_key]["n"] += 1
            else:
                grouped[merge_key] = {"day": day, "text": text, "n": 1}
            total += 1
        if not grouped:
            continue
        records = sorted(grouped.values(), key=lambda item: (-item["day"], item["text"]))
        for record in records:
            record["day_text"] = _day_text(record["day"])
        stats = []
        raw_stats = slot.get("stats") if isinstance(slot.get("stats"), dict) else {}
        for stat_key, label in STAT_LABELS.items():
            count = _int(raw_stats.get(stat_key), 0) or 0
            if count > 0:
                stats.append({"key": stat_key, "label": label, "value": count})
        latest = max((record["day"] for record in records), default=0)
        rows.append({
            "npc": npc_id, "name": name,
            "title": (cast.get(npc_key) or {}).get("title", ""),
            "avatar": _avatar_for(npc_id),
            "count": total, "merged": len(records),
            "latest": latest, "latest_text": _day_text(latest),
            "stats": stats, "records": records,
        })
    rows.sort(key=lambda row: (-row["latest"], row["name"]))
    return rows


def scan_memoria(obj, meta_obj):
    meta_obj = meta_obj or {}
    player = (obj or {}).get("playerModel") or {}
    mem = player.get("memoria") or {}
    unlocked = _int_map(mem.get("unlocked"))
    viewed = _int_set(mem.get("viewed"))
    dao = _int_set(((player.get("npc_dao_ally") or {}).get("npc_ids")))
    cast = meta_obj.get("cast") or {}

    shooting, bonds, adventure = {}, [], []
    for entry in meta_obj.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        npc_id = entry.get("npc") or 0
        got = entry_id in unlocked
        seen = bool(got) and entry_id in viewed
        row = {
            "id": entry_id, "cat": entry.get("cat"), "npc": npc_id,
            "title": entry.get("title") or "", "hint": entry.get("hint") or "",
            "sort": entry.get("sort") or 0,
            "got": got, "viewed": seen, "date": _date(unlocked.get(entry_id)) if got else "",
        }
        category = entry.get("cat")
        if category == 1:
            npc_key = str(npc_id)
            profile = cast.get(npc_key) or {}
            card = shooting.get(npc_key)
            if card is None:
                card = shooting[npc_key] = {
                    "npc": npc_id,
                    "name": profile.get("name") or ("NPC %s" % npc_id),
                    "title": profile.get("title", ""),
                    "avatar": _avatar_for(npc_id),
                    "gender": profile.get("gender", 0),
                    "pet": bool(profile.get("pet")),
                    "layer": profile.get("layer", ""),
                    "segs": [], "total": 0, "got": 0, "viewed": 0, "last": "",
                }
            card["segs"].append(row)
        elif category == 2:
            npc_key = str(npc_id)
            profile = cast.get(npc_key) or {}
            row.update({
                "name": profile.get("name") or ("NPC %s" % npc_id),
                "npc_title": profile.get("title", ""),
                "avatar": _avatar_for(npc_id),
                "dao": npc_id in dao,
            })
            bonds.append(row)
        elif category == 3:
            row.update({
                "quest": entry.get("quest") or 0,
                "name": entry.get("event_name") or ("奇遇 %s" % (entry.get("quest") or 0)),
                "desc": entry.get("event_desc") or "",
                "realm": entry.get("realm") or 0,
                "realm_name": entry.get("realm_name") or "未知境界",
            })
            adventure.append(row)

    for card in shooting.values():
        card["segs"].sort(key=lambda seg: (seg.get("sort") or 0, seg.get("id") or 0))
        card["total"] = len(card["segs"])
        card["got"] = sum(1 for seg in card["segs"] if seg["got"])
        card["viewed"] = sum(1 for seg in card["segs"] if seg["viewed"])
        dates = [seg["date"] for seg in card["segs"] if seg["date"]]
        card["last"] = max(dates) if dates else ""
    shooting_rows = sorted(shooting.values(),
                           key=lambda card: (card["got"] - card["total"], card["name"]))

    adventure.sort(key=lambda row: (row.get("realm") or 0, row.get("sort") or 0, row.get("id") or 0))
    bonds.sort(key=lambda row: (0 if row["got"] else 1, row.get("sort") or 0))

    friends = _friend_rows(mem, meta_obj)
    totals = {
        "shooting": {"got": sum(card["got"] for card in shooting_rows),
                     "total": sum(card["total"] for card in shooting_rows),
                     "viewed": sum(card["viewed"] for card in shooting_rows)},
        "bond": {"got": sum(1 for row in bonds if row["got"]),
                 "total": len(bonds),
                 "viewed": sum(1 for row in bonds if row["viewed"])},
        "adventure": {"got": sum(1 for row in adventure if row["got"]),
                      "total": len(adventure),
                      "viewed": sum(1 for row in adventure if row["viewed"])},
        "friends": {"count": len(friends),
                    "records": sum(row["count"] for row in friends)},
    }
    totals["unseen"] = (totals["shooting"]["got"] - totals["shooting"]["viewed"]
                        + totals["bond"]["got"] - totals["bond"]["viewed"]
                        + totals["adventure"]["got"] - totals["adventure"]["viewed"])
    totals["unlocked"] = (totals["shooting"]["got"] + totals["bond"]["got"]
                          + totals["adventure"]["got"])
    totals["entries"] = (totals["shooting"]["total"] + totals["bond"]["total"]
                         + totals["adventure"]["total"])
    return {
        "shooting": shooting_rows, "bonds": bonds,
        "adventure": adventure, "friends": friends,
        "stats": totals,
        "character": {"name": player.get("playerName") or "未命名"},
        "hint": "" if mem else "该存档尚未产生忆海数据，以下均为未收录状态。",
    }


def meta(metadata):
    return metadata.get("memoria") or {"entries": [], "cast": {}, "bond_types": {},
                                       "names": {}, "stats": {}}


def prepare(game_dir):
    return None


def scan(obj, meta_obj, state=None):
    return scan_memoria(obj, meta_obj)


def post(rows, state, original, path):
    return rows


def enrich(module, meta_obj, state=None):
    return module


def summary(module):
    stats = (module.get("rows") or {}).get("stats") or {}
    shooting = stats.get("shooting") or {}
    bond = stats.get("bond") or {}
    adventure = stats.get("adventure") or {}
    friends = stats.get("friends") or {}
    return ("留影石：留影 %d/%d 段，结缘 %d/%d 位，奇遇留影 %d/%d 桩，故交 %d 人；未看 %d 条" % (
        shooting.get("got", 0), shooting.get("total", 0),
        bond.get("got", 0), bond.get("total", 0),
        adventure.get("got", 0), adventure.get("total", 0),
        friends.get("count", 0), stats.get("unseen", 0)))
