# -*- coding: utf-8 -*-
"""红尘扫描：按存档标注每条角色线任务状态与进度。

跨模块资源（头像 base64）只读取落盘快照文件，不 import 其它模块。
"""
import json
import os
from functools import lru_cache

DONE_STATES = (2, 3)
DOING_STATES = (1, 6)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_AVATARS_FILE = os.path.join(_ROOT, "memoria_avatars_meta.json")


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def meta(metadata):
    return metadata.get("hongchen") or {
        "lines": [], "quests": [], "states": {}, "types": {}, "stats": {},
        "attr_names": {}, "done_states": list(DONE_STATES), "doing_states": list(DOING_STATES),
    }


@lru_cache(maxsize=1)
def _load_avatars():
    try:
        with open(_AVATARS_FILE, encoding="utf-8-sig") as handle:
            raw = json.load(handle)
    except Exception:
        return {}, {}
    images = raw.get("avatars") if isinstance(raw.get("avatars"), dict) else {}
    icons = raw.get("icons") if isinstance(raw.get("icons"), dict) else {}
    return images, icons


def prepare(game_dir):
    return _load_avatars()


def _avatar_for(npc_id, avatars):
    images, icons = avatars if isinstance(avatars, tuple) else ({}, {})
    if not npc_id:
        return ""
    icon = icons.get(str(npc_id)) or icons.get(npc_id) or ""
    return images.get(icon) or ""


def _realm_layer(player):
    return _int((player.get("combat") or {}).get("cultivate_layer_id"))


def _money(player):
    bag = player.get("bag") or {}
    total = 0
    for entry in bag.get("items") or []:
        if not isinstance(entry, list) or len(entry) < 2 or not isinstance(entry[1], dict):
            continue
        info = entry[1]
        if _int(info.get("item_id")) == 50000:
            total += _int(info.get("count"))
    return total


def _context(obj, meta_obj, npc_id):
    player = obj.get("playerModel") or {}
    favor = {}
    for record in (obj.get("npcs") or {}).values():
        if isinstance(record, dict) and record.get("npcCfgId") is not None:
            favor[_int(record["npcCfgId"])] = _int(record.get("intimacy"))
    attrs = {}
    name2attr = {}
    for attr_id, attr_name in (meta_obj.get("attr_names") or {}).items():
        if attr_name:
            name2attr[attr_name] = _int(attr_id)
    for key, value in (player.get("interact_attributes") or {}).items():
        attrs[str(_int(key))] = _int(value)
    return {"favor": favor, "attrs": attrs, "name2attr": name2attr,
            "money": _money(player), "layer": _realm_layer(player),
            "npc_id": _int(npc_id)}


def _eval_gate(gate, ctx):
    """返回 (True/False/None, 说明)。None 表示无法判定，只当提示。"""
    kind = gate.get("kind") or ""
    need = _int(gate.get("need"))
    if kind == "favor":
        npc = _int(gate.get("npc")) or ctx["npc_id"]
        cur = ctx["favor"].get(npc, 0)
        return cur >= need, "%s %d/%d" % (gate.get("attr_name") or "好感", cur, need)
    if kind == "attr":
        name = gate.get("attr_name") or ""
        attr_id = ctx["name2attr"].get(name)
        if attr_id:
            cur = ctx["attrs"].get(str(attr_id), 0)
            return cur >= need, "%s %d/%d" % (name, cur, need)
        return None, ""
    if kind == "money":
        cur = ctx["money"]
        return cur >= need, "灵石 %d/%d" % (cur, need)
    if kind in ("realm", "phase", "layer"):
        cur = ctx["layer"]
        return cur >= need, "修炼层数 %d/%d" % (cur, need)
    return None, ""


def _status_of(quest, code, accepted, ctx, branch_states):
    states = {"已完成": "done", "进行中": "doing", "已错过": "missed",
              "可接取": "ready", "条件不足": "locked", "待解锁": "todo"}
    if code in DONE_STATES:
        return "已完成", "done", "", []
    if code in DOING_STATES:
        return "进行中", "doing", "", []
    key = quest.get("branch_key") or ""
    if key:
        for sibling_id, sibling_code in branch_states.items():
            if sibling_id == quest["id"]:
                continue
            if sibling_code in DONE_STATES or sibling_code in DOING_STATES:
                name = sibling_id
                for other in ctx.get("_branch_names", {}).get(key, []):
                    if other[0] == sibling_id:
                        name = other[1]
                        break
                return "已错过", "missed", "已选择「%s」" % name, []

    fails, hints, pass_all = [], [], True
    for gate in quest.get("gates") or []:
        if not gate:
            continue
        ok, desc = _eval_gate(gate, ctx)
        if desc:
            hints.append(desc)
        if ok is False:
            pass_all = False
            fails.append(gate.get("text") or "附加条件")
    for option in quest.get("options") or []:
        gate = option.get("gate")
        if gate:
            ok, desc = _eval_gate(gate, ctx)
            if desc:
                hints.append(desc)
            if ok is False:
                pass_all = False
                fails.append("[%s] %s" % (option.get("text") or "选项", gate.get("text") or "门槛"))

    prev = _int(quest.get("prev"))
    if prev and prev not in ctx.get("_codes", {}):
        pass_all = False
        fails.append("前置任务 %s 未完成" % prev)
    label = "可接取" if pass_all else ("条件不足" if not prev or prev in ctx.get("_codes", {}) else "待解锁")
    return label, states.get(label, "ready"), "；".join(fails), hints


def scan(obj, meta_obj, state=None):
    player = obj.get("playerModel") or {}
    component = player.get("questComponent") or {}
    saved = {}
    for key, value in (component.get("quests") or {}).items():
        if isinstance(value, dict):
            saved[_int(key)] = value

    # 全部红尘任务的状态码，供分支错过/前置判断。
    codes = {}
    for quest in meta_obj.get("quests") or []:
        code = _int((saved.get(_int(quest.get("id"))) or {}).get("state"), 0)
        codes[_int(quest.get("id"))] = code
    branch_names = {}
    for quest in meta_obj.get("quests") or []:
        branch_names.setdefault(quest.get("branch_key") or "", []).append(
            (_int(quest.get("id")), quest.get("name") or ""))

    lines = []
    for line in meta_obj.get("lines") or []:
        ctx = _context(obj, meta_obj, line.get("npc_id"))
        ctx["_codes"] = {qid: code for qid, code in codes.items()
                         if code in DONE_STATES or code in DOING_STATES}
        ctx["_branch_names"] = branch_names
        quests = []
        for quest in line.get("quests") or []:
            qid = _int(quest.get("id"))
            item = saved.get(qid) or {}
            code = _int(item.get("state"), 0)
            label, cls, fail_text, hints = _status_of(quest, code, bool(item), ctx, codes)
            quests.append({
                "id": qid,
                "name": quest.get("name") or ("红尘 %s" % qid),
                "desc": quest.get("desc") or "",
                "depth": _int(quest.get("depth"), 1),
                "prev": _int(quest.get("prev")),
                "next": quest.get("next") or [],
                "branch": bool(quest.get("branch")),
                "branch_key": quest.get("branch_key") or "",
                "branch_with": quest.get("branch_with") or [],
                "hidden": bool(quest.get("hidden")),
                "giver": quest.get("giver"),
                "gates": quest.get("gates") or [],
                "options": quest.get("options") or [],
                "state": code,
                "accepted": bool(item),
                "accept_time": _int(item.get("acceptTime")),
                "done": code in DONE_STATES,
                "doing": code in DOING_STATES,
                "status": label,
                "status_cls": cls,
                "fail_text": fail_text,
                "hints": hints,
            })
        total = len(quests)
        done = sum(1 for q in quests if q["done"])
        doing = sum(1 for q in quests if q["doing"])
        missed = sum(1 for q in quests if q["status_cls"] == "missed")
        ready = sum(1 for q in quests if q["status_cls"] in ("ready", "locked", "todo"))
        locked = sum(1 for q in quests if q["status_cls"] == "locked")
        pct = int(round(done * 100 / total)) if total else 0
        lines.append({
            "group": line.get("group") or "",
            "name": line.get("name") or "",
            "npc_id": _int(line.get("npc_id")),
            "portrait": line.get("portrait") or "",
            "color": line.get("color") or "#c9866b",
            "quests": quests,
            "roots": line.get("roots") or [],
            "edges": line.get("edges") or [],
            "branches": line.get("branches") or [],
            "progress": {"total": total, "done": done, "doing": doing, "missed": missed,
                         "ready": ready, "locked": locked, "pct": pct},
        })

    stats = {"lines": len(lines),
             "quests": sum(len(line["quests"]) for line in lines),
             "done": sum(line["progress"]["done"] for line in lines),
             "doing": sum(line["progress"]["doing"] for line in lines),
             "missed": sum(line["progress"]["missed"] for line in lines),
             "ready": sum(line["progress"]["ready"] for line in lines)}
    return {"rows": lines, "stats": stats,
            "states": meta_obj.get("states") or {},
            "types": meta_obj.get("types") or {}}


def post(rows, state, original, path):
    if isinstance(rows, dict):
        rows["src"] = os.path.basename(original) if original else os.path.basename(path or "")
    return rows


def enrich(module, meta_obj, state=None):
    data = module if isinstance(module, dict) else {}
    rows = data.get("rows") or {}
    avatars = state if isinstance(state, tuple) else _load_avatars()
    for line in rows.get("rows") or []:
        line["avatar"] = _avatar_for(line.get("npc_id"), avatars)
    return data


def summary(module):
    rows = (module.get("rows") or {}) if isinstance(module, dict) else {}
    stats = rows.get("stats") or {}
    return "红尘：%d 条角色线 / %d 个任务，已完成 %d，进行中 %d，可接取 %d，已错过 %d" % (
        stats.get("lines", 0), stats.get("quests", 0), stats.get("done", 0),
        stats.get("doing", 0), stats.get("ready", 0), stats.get("missed", 0))
