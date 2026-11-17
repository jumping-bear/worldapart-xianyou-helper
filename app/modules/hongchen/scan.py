# -*- coding: utf-8 -*-
"""红尘扫描：按存档标注每条角色线任务状态与进度。

跨模块资源（头像 base64）只读取落盘快照文件，不 import 其它模块。

状态语义（面向玩家，避免把"没走到"误报成"已错过"）：
  done        已完成
  doing       进行中
  ready       可接取（前置完成且条件满足）
  unpicked    另一条路（已到分叉点且明确选了另一个互斥选项）—— 不计入完成度分母
  notstarted  未开始（前置未完成，还没走到这里）—— 中性灰，不算漏做
  locked      未解锁（前置已到但好感/属性/灵石等条件不足）

完成度分母 = 全部任务 - 因分支选择放弃的任务(unpicked)。这样二选一选了另一个
不会再被当成"未完成"，玩家能够 100%。

每条线另外产出 remaining（"还差什么"清单）与 rings（每环剩余数），供前端
直接回答"我还剩哪些任务、为什么没做"，而不是让玩家自己在任务树里找。
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
    """返回 (True/False/None, 说明, 当前值, 需求值)。

    None 表示无法判定，只当提示；cur 供前端展示"当前 712 / 需 3"。
    """
    kind = gate.get("kind") or ""
    need = _int(gate.get("need"))
    if kind == "favor":
        npc = _int(gate.get("npc")) or ctx["npc_id"]
        cur = ctx["favor"].get(npc, 0)
        return cur >= need, "%s %d/%d" % (gate.get("attr_name") or "好感", cur, need), cur, need
    if kind == "attr":
        name = gate.get("attr_name") or ""
        attr_id = ctx["name2attr"].get(name)
        if attr_id:
            cur = ctx["attrs"].get(str(attr_id), 0)
            return cur >= need, "%s %d/%d" % (name, cur, need), cur, need
        return None, "", 0, need
    if kind == "money":
        cur = ctx["money"]
        return cur >= need, "灵石 %d/%d" % (cur, need), cur, need
    if kind in ("realm", "phase", "layer"):
        cur = ctx["layer"]
        return cur >= need, "修炼层数 %d/%d" % (cur, need), cur, need
    return None, "", 0, need


def _is_done(code):
    return code in DONE_STATES


def _is_doing(code):
    return code in DOING_STATES


def _status_of(quest, code, ctx):
    """返回 (文案, 状态类, 备注, 提示)。

    关键修正：分支任务只有在"已到分叉点 + 同组兄弟任务被完成/进行中"时才算
    unpicked（未选此分支）；没走到、没开始的按 notstarted / locked 处理，
    绝不再笼统报"已错过"。
    """
    if _is_done(code):
        return "已完成", "done", "", []
    if _is_doing(code):
        return "进行中", "doing", "", []

    qid = _int(quest.get("id"))
    key = quest.get("branch_key") or ""
    is_branch = bool(quest.get("branch")) or bool(key)
    names = ctx.get("_names", {})
    codes = ctx.get("_codes", {})
    active = ctx.get("_active", set())

    # 附加条件（好感/属性/灵石）与门槛提示。
    fails, hints, gate_ok = [], [], True
    for gate in quest.get("gates") or []:
        if not gate:
            continue
        ok, desc, _cur, _need = _eval_gate(gate, ctx)
        if desc:
            hints.append(desc)
        if ok is False:
            gate_ok = False
            fails.append(gate.get("text") or "附加条件")
    for option in quest.get("options") or []:
        gate = option.get("gate")
        if gate:
            ok, desc, _cur, _need = _eval_gate(gate, ctx)
            if desc:
                hints.append(desc)
            if ok is False:
                gate_ok = False
                fails.append("[%s] %s" % (option.get("text") or "选项", gate.get("text") or "门槛"))

    prev = _int(quest.get("prev"))
    prev_done = (not prev) or (prev in active)
    if not prev_done:
        fails.append("前置「%s」未完成" % names.get(prev, ("任务 %s" % prev)))

    if is_branch and key:
        # 只看"同一个互斥分支组"的兄弟任务，不再扫全表。
        siblings = ctx.get("_branch_members", {}).get(key, [])
        chosen = []
        for sid in siblings:
            if sid == qid:
                continue
            scode = codes.get(sid, 0)
            if _is_done(scode) or _is_doing(scode):
                chosen.append(sid)
        fork = _int(ctx.get("_branch_parent", {}).get(key, 0)) or prev
        fork_reached = (fork in active) or bool(chosen)
        if chosen and fork_reached:
            # 优先用玩家实际点选的选项文本（如「言辞支开」），没有则用结果任务名。
            cname = ctx.get("_option_by_target", {}).get((fork, chosen[0])) \
                or names.get(chosen[0], ("任务 %s" % chosen[0]))
            return "未选此分支", "unpicked", "已选择「%s」" % cname, hints
        if not fork_reached:
            return "未开始", "notstarted", "前置剧情还没走到", hints
        if gate_ok:
            return "可接取", "ready", "分叉点已到达，可选择此分支", hints
        return "未解锁", "locked", "；".join(fails) or "条件不足", hints

    # 普通任务。
    if prev_done and gate_ok:
        return "可接取", "ready", "", hints
    if not prev_done:
        return "未开始", "notstarted", "；".join(fails), hints
    return "未解锁", "locked", "；".join(fails) or "条件不足", hints


def _remaining(quests, ctx, base, done):
    """把"还差什么"翻译成玩家能直接行动的清单。

    四类剩余（可接取 / 进行中 / 未开始 / 差条件）+ 按分支组汇总的"当时选了另一条路"。
    分支未选不算漏做，所以单独成组、不并入 left。
    """
    names = ctx.get("_names") or {}
    active = ctx.get("_active") or set()

    def qname(qid):
        return names.get(qid) or ("任务 %s" % qid)

    def entry(quest):
        reason = ""
        if quest["status_cls"] in ("notstarted", "locked"):
            parts = []
            prev = quest["prev"]
            if prev and prev not in active:
                parts.append("前置「%s」未完成" % qname(prev))
            for check in quest.get("gate_checks") or []:
                if check.get("ok") is False:
                    text = check.get("text") or check.get("desc") or "附加条件"
                    parts.append("条件：%s（当前 %s）" % (text, check.get("cur")))
            reason = "；".join(parts) or quest.get("fail_text") or "继续推进前置剧情"
        return {"id": quest["id"], "name": quest["name"], "depth": quest["depth"],
                "status_cls": quest["status_cls"], "status": quest["status"], "reason": reason}

    buckets = {"ready": [], "doing": [], "notstarted": [], "locked": []}
    for quest in quests:
        bucket = buckets.get(quest["status_cls"])
        if bucket is not None:
            bucket.append(entry(quest))
    left = sum(len(items) for items in buckets.values())

    by_id = {quest["id"]: quest for quest in quests}
    order, grouped = [], {}
    for quest in quests:
        key = quest["branch_key"]
        if quest["status_cls"] != "unpicked" or not key:
            continue
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(quest)

    choices = []
    for key in order:
        members = [by_id[m] for m in (ctx.get("_branch_members") or {}).get(key, []) if m in by_id]
        if not members:
            members = grouped[key]
        parent = _int((ctx.get("_branch_parent") or {}).get(key, 0)) \
            or (members[0]["prev"] if members else 0)
        chosen, skipped = [], []
        for member in members:
            label = (ctx.get("_option_by_target") or {}).get((parent, member["id"])) or member["name"]
            item = {"id": member["id"], "name": member["name"], "label": label}
            if member["status_cls"] in ("done", "doing"):
                chosen.append(item)
            elif member["status_cls"] == "unpicked":
                skipped.append(item)
        if not skipped:
            continue
        picked_txt = "".join("「%s」" % c["label"] for c in chosen) or "另一条"
        skipped_txt = "".join("「%s」" % s["label"] for s in skipped)
        parent_name = qname(parent) if parent else ""
        rule = "二选一" if len(members) == 2 else ("%d 选 1" % len(members))
        # 流水型分支（f:）没有可跳转的父任务，用"同一段剧情"表述，避免出现"分叉点"空话。
        where = "在「%s」%s" % (parent_name, rule) if parent_name else ("同一段剧情%s" % rule)
        choices.append({
            "key": key, "parent_id": parent, "parent_name": parent_name or "同一段剧情",
            "member_count": len(members), "chosen": chosen, "skipped": skipped,
            "depth": by_id[parent]["depth"] if parent in by_id
                     else (members[0]["depth"] if members else 1),
            "text": "%s：你选了%s，未选%s" % (where, picked_txt, skipped_txt),
            "note": "选了另一条路，这条不会再出现，也不算漏做",
        })

    if left:
        brief = "还差 " + "、".join(
            "%d 个%s" % (len(buckets[cls]), label)
            for cls, label in (("ready", "可接取"), ("doing", "进行中"),
                               ("notstarted", "未开始"), ("locked", "差条件"))
            if buckets[cls])
    else:
        brief = "已走完"
    return {
        "left": left, "done": left == 0, "brief": brief,
        "headline": "已完成 %d/%d · %s" % (done, base, brief),
        "ready": buckets["ready"], "doing": buckets["doing"],
        "notstarted": buckets["notstarted"], "locked": buckets["locked"],
        "choices": choices,
        "choice_note": "这些是当时选了另一条路的分支，不会再出现，也不算漏做。",
    }


def _rings(quests):
    """每环的剩余数：给环进度轴标"这一环还剩几个"。"""
    if not quests:
        return []
    rings = []
    for depth in range(1, max(q["depth"] for q in quests) + 1):
        here = [q for q in quests if q["depth"] == depth]
        rings.append({
            "depth": depth, "total": len(here),
            "done": sum(1 for q in here if q["done"]),
            "left": sum(1 for q in here if q["status_cls"] in ("ready", "doing", "notstarted", "locked")),
            "ready": sum(1 for q in here if q["status_cls"] == "ready"),
            "unpicked": sum(1 for q in here if q["status_cls"] == "unpicked"),
            "branch": any(q["branch"] for q in here),
        })
    return rings


def scan(obj, meta_obj, state=None):
    player = obj.get("playerModel") or {}
    component = player.get("questComponent") or {}
    saved = {}
    for key, value in (component.get("quests") or {}).items():
        if isinstance(value, dict):
            saved[_int(key)] = value

    # 全部红尘任务的状态码、名称、分支分组，供状态判定使用。
    codes, names = {}, {}
    for quest in meta_obj.get("quests") or []:
        qid = _int(quest.get("id"))
        codes[qid] = _int((saved.get(qid) or {}).get("state"), 0)
        names[qid] = quest.get("name") or ("红尘 %s" % qid)
    branch_members, branch_parent, option_by_target = {}, {}, {}
    for quest in meta_obj.get("quests") or []:
        qid = _int(quest.get("id"))
        for option in quest.get("options") or []:
            for target in option.get("to") or []:
                if option.get("text"):
                    option_by_target[(qid, _int(target))] = option["text"]
    for line in meta_obj.get("lines") or []:
        for branch in line.get("branches") or []:
            bkey = branch.get("key") or ""
            if bkey:
                members = [_int(m) for m in branch.get("members") or []]
                branch_members[bkey] = members
                branch_parent[bkey] = _int(branch.get("parent"))

    lines = []
    for line in meta_obj.get("lines") or []:
        ctx = _context(obj, meta_obj, line.get("npc_id"))
        ctx["_codes"] = codes
        ctx["_active"] = {qid for qid, code in codes.items()
                          if _is_done(code) or _is_doing(code)}
        ctx["_names"] = names
        ctx["_branch_members"] = branch_members
        ctx["_branch_parent"] = branch_parent
        ctx["_option_by_target"] = option_by_target

        quests = []
        for quest in line.get("quests") or []:
            qid = _int(quest.get("id"))
            item = saved.get(qid) or {}
            code = _int(item.get("state"), 0)
            label, cls, fail_text, hints = _status_of(quest, code, ctx)
            # 门槛对比（当前值 / 需求值），供节点详情直接告诉玩家"差多少"。
            gate_checks = []
            for gate in quest.get("gates") or []:
                if not gate:
                    continue
                ok, desc, cur, need = _eval_gate(gate, ctx)
                gate_checks.append({"text": gate.get("text") or "", "kind": gate.get("kind") or "",
                                    "need": need, "cur": cur, "desc": desc, "ok": ok})
            options = []
            for option in quest.get("options") or []:
                if not option:
                    continue
                check = None
                gate = option.get("gate")
                if gate:
                    ok, desc, cur, need = _eval_gate(gate, ctx)
                    check = {"need": need, "cur": cur, "desc": desc, "ok": ok}
                options.append({"text": option.get("text") or "选择",
                                "to": option.get("to") or [], "gate": gate, "check": check})
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
                "gate_checks": gate_checks,
                "options": options,
                "state": code,
                "accepted": bool(item),
                "accept_time": _int(item.get("acceptTime")),
                "done": _is_done(code),
                "doing": _is_doing(code),
                "status": label,
                "status_cls": cls,
                "fail_text": fail_text,
                "hints": hints,
            })

        total = len(quests)
        done = sum(1 for q in quests if q["done"])
        doing = sum(1 for q in quests if q["doing"])
        unpicked = sum(1 for q in quests if q["status_cls"] == "unpicked")
        ready = sum(1 for q in quests if q["status_cls"] == "ready")
        notstarted = sum(1 for q in quests if q["status_cls"] == "notstarted")
        locked = sum(1 for q in quests if q["status_cls"] == "locked")
        # 完成度分母剔除因分支选择放弃的任务，二选一不再算漏做。
        base = total - unpicked
        pct = int(round(done * 100 / base)) if base else 0
        remaining = _remaining(quests, ctx, base, done)
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
            "rings": _rings(quests),
            "remaining": remaining,
            "progress": {"total": total, "base": base, "done": done, "doing": doing,
                         "ready": ready, "notstarted": notstarted, "locked": locked,
                         "unpicked": unpicked, "missed": unpicked, "pct": pct,
                         "left": remaining["left"], "headline": remaining["headline"]},
        })

    stats = {"lines": len(lines),
             "quests": sum(len(line["quests"]) for line in lines),
             "done": sum(line["progress"]["done"] for line in lines),
             "doing": sum(line["progress"]["doing"] for line in lines),
             "ready": sum(line["progress"]["ready"] for line in lines),
             "notstarted": sum(line["progress"]["notstarted"] for line in lines),
             "locked": sum(line["progress"]["locked"] for line in lines),
             "unpicked": sum(line["progress"]["unpicked"] for line in lines)}
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
    return ("红尘：%d 条角色线 / %d 个任务，已完成 %d，进行中 %d，可接取 %d，"
            "未开始 %d，未解锁 %d，分支选了另一条路 %d（不算漏做）" % (
                stats.get("lines", 0), stats.get("quests", 0), stats.get("done", 0),
                stats.get("doing", 0), stats.get("ready", 0), stats.get("notstarted", 0),
                stats.get("locked", 0), stats.get("unpicked", 0)))
