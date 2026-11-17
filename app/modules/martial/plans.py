# -*- coding: utf-8 -*-
"""M3：推进方案、获取路线与本门流派。

只使用快照里已有的状态、门派、元素、境界、价格、货架与请教字段；
不推断升阶关系，不输出推荐指数，无法由配置确认的机制统一标注「待复核」。
"""

CONFIRM = "可确认"
REVIEW = "待复核"
SOURCE_RANK = {"货架": 1, "可请教": 2, "卷册": 3, "未开放": 4}


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sect_map(meta):
    return {_int(item.get("id")): item for item in meta.get("sects") or []}


def _sect_name(meta, sect_id):
    sect = _sect_map(meta).get(_int(sect_id))
    if sect:
        return sect.get("name") or ("门派 %s" % sect_id)
    return "通用" if not _int(sect_id) else ("门派 %s" % sect_id)


def _element_name(meta, element):
    return (meta.get("elements") or {}).get(str(_int(element)), "待识别")


def _tier_name(meta, tier):
    tier = _int(tier)
    if not tier:
        return ""
    phases = meta.get("phases") or {}
    start = (meta.get("tier_phase") or {}).get(str(tier))
    if start and str(start) in phases:
        return phases[str(start)]
    return phases.get(str(tier)) or ("境界%s" % tier)


def _current_tier(rows, meta):
    layer = _int((rows.get("character") or {}).get("layer"))
    best_key, best_start = 0, -1
    for key, start in (meta.get("tier_phase") or {}).items():
        start = _int(start)
        if start and layer >= start > best_start:
            best_key, best_start = _int(key), start
    return best_key


def _art_matches(core, art):
    if _int(core.get("tier")) and _int(art.get("tier")) != _int(core.get("tier")):
        return False
    element = _int(core.get("element"))
    if element and _int(art.get("element")) != element:
        return False
    sect = _int(core.get("sect"))
    if sect and _int(art.get("sect")) != sect:
        return False
    return True


def _mismatch_text(meta, core, art):
    bits = []
    if _int(core.get("element")) and _int(art.get("element")) != _int(core.get("element")):
        bits.append("元素 %s≠%s" % (_element_name(meta, art.get("element")),
                                  _element_name(meta, core.get("element"))))
    if _int(core.get("tier")) and _int(art.get("tier")) != _int(core.get("tier")):
        bits.append("境界 %s≠%s" % (_tier_name(meta, art.get("tier")),
                                  _tier_name(meta, core.get("tier"))))
    return "、".join(bits) or "元素/境界记录缺失"


def _acquire_cost(row):
    price = _int(row.get("price")) if row.get("book") else 0
    teach = row.get("teach") or {}
    affinity = (_int(teach.get("affinity")) + _int(teach.get("cost"))
                if row.get("source") == "可请教" else 0)
    minutes = _int((row.get("comprehend") or {}).get("time"))
    return price, affinity, minutes


def _cost_text(price, affinity, minutes):
    bits = []
    if price:
        bits.append("%d 灵石" % price)
    if affinity:
        bits.append("好感 %d" % affinity)
    if minutes:
        bits.append("参悟 %d 分钟" % minutes)
    return " · ".join(bits)


def _source_text(meta, row):
    source = row.get("source") or "未开放"
    bits = [source]
    shops = [item.get("name") for item in row.get("shops") or [] if item.get("name")]
    if shops:
        bits.append("、".join(shops))
    teach = row.get("teach") or {}
    if source == "可请教":
        bits.append("%s · 好感 %d · 消耗 %d" % (
            _tier_name(meta, teach.get("realm")) or "境界未记录",
            _int(teach.get("affinity")), _int(teach.get("cost"))))
    compre = row.get("comprehend") or {}
    if compre:
        bits.append("参悟 %d 分钟" % _int(compre.get("time")))
    return " · ".join(bit for bit in bits if bit)


def _pick(candidates):
    """已有卷册 → 货架 → 请教 → 仅卷册 → 未开放；同级按价格、条目 id。

    这是获取顺序，不是推荐指数；仅用于给出可执行的具体候选。
    """
    return sorted(candidates, key=lambda row: (
        0 if row.get("state") == "卷册在包" else 1,
        SOURCE_RANK.get(row.get("source"), 5),
        _int(row.get("price")),
        _int(row.get("id")),
    ))


def _categorize(steps):
    """给步骤分类，视图按「配置 / 卷册 / 共鸣 / 复核」折叠展示。"""
    for step in steps:
        kind = (step.get("target") or {}).get("kind")
        if kind == "bag":
            step["category"] = "卷册"
        elif kind in ("resonance", "resonance_slots"):
            step["category"] = "共鸣"
        elif "同系心法" in step.get("text", ""):
            step["category"] = "复核"
        else:
            step["category"] = "配置"


def _plan_fix(rows, meta):
    steps, gaps = [], []
    slots = (rows.get("equip") or {}).get("slots") or []
    cores = rows.get("core_passives") or []
    arts = rows.get("arts") or []
    sect_id = _int((rows.get("character") or {}).get("sect_id"))

    installed = {_int(slot.get("core_id")) for slot in slots if _int(slot.get("core_id"))}
    idle_cores = sorted(
        [row for row in cores if row.get("state") == "已学会未运转"],
        key=lambda row: (0 if _int(row.get("sect")) == sect_id else 1,
                         _int(row.get("tier")), _int(row.get("id"))))

    empty_slots = [slot for slot in slots if not _int(slot.get("core_id"))]
    for slot in empty_slots:
        if not idle_cores:
            gaps.append({"kind": "core", "sect": sect_id, "element": 0, "tier": 0,
                         "reason": "槽位 %s 空着" % slot.get("slot")})
            continue
        core = idle_cores.pop(0)
        steps.append({
            "text": "槽位 %s 装上「%s」" % (slot.get("slot"), core.get("name")),
            "detail": "%s · %s · %s" % (_sect_name(meta, core.get("sect")),
                                        _element_name(meta, core.get("element")),
                                        _tier_name(meta, core.get("tier"))),
            "cost": "0 灵石（已学会）",
            "confirm": CONFIRM,
            "target": {"kind": "core", "id": _int(core.get("id"))},
        })

    swapped = set()
    for core_id in sorted(installed):
        current = next((row for row in cores if _int(row.get("id")) == core_id), None)
        if not current or _int(current.get("tier")) <= 0:
            continue
        replacement = next(
            (row for row in cores
             if row.get("name") == current.get("name")
             and _int(row.get("tier")) > _int(current.get("tier"))
             and row.get("state") == "已学会未运转"
             and _int(row.get("id")) not in swapped), None)
        if not replacement:
            continue
        swapped.add(_int(replacement.get("id")))
        steps.append({
            "text": "把「%s」换成同名%s版" % (current.get("name"), _tier_name(meta, replacement.get("tier"))),
            "detail": "%s → %s" % (_tier_name(meta, current.get("tier")),
                                  _tier_name(meta, replacement.get("tier"))),
            "cost": "0 灵石（已学会）",
            "confirm": CONFIRM,
            "target": {"kind": "core", "id": core_id},
        })

    placed = set()
    idle_arts = sorted(
        [row for row in arts if row.get("state") == "已学会未运转" and _int(row.get("id")) not in swapped],
        key=lambda row: (0 if _int(row.get("sect")) == sect_id else 1,
                         _int(row.get("tier")), _int(row.get("id"))))

    def take_art(core):
        for row in idle_arts:
            art_id = _int(row.get("id"))
            if art_id in placed:
                continue
            if _art_matches(core, row):
                placed.add(art_id)
                return row
        return None

    for slot in slots:
        core = next((row for row in cores if _int(row.get("id")) == _int(slot.get("core_id"))), None)
        if not core:
            continue
        for cell in slot.get("cells") or []:
            index = _int(cell.get("index")) + 1
            if cell.get("empty"):
                replacement = take_art(core)
                if replacement:
                    steps.append({
                        "text": "「%s」第 %d 格装上「%s」" % (core.get("name"), index, replacement.get("name")),
                        "detail": "%s · %s" % (_element_name(meta, replacement.get("element")),
                                              _tier_name(meta, replacement.get("tier"))),
                        "cost": "0 灵石（已学会）",
                        "confirm": CONFIRM,
                        "target": {"kind": "art", "id": _int(replacement.get("id"))},
                    })
                else:
                    gaps.append({"kind": "art", "sect": _int(core.get("sect")),
                                 "element": _int(core.get("element")), "tier": _int(core.get("tier")),
                                 "reason": "「%s」第 %d 格空着" % (core.get("name"), index)})
                    steps.append({
                        "text": "「%s」第 %d 格还空着" % (core.get("name"), index),
                        "detail": "已学功法里没有%s%s的同门功法" % (
                            _element_name(meta, core.get("element")) if _int(core.get("element")) else "",
                            _tier_name(meta, core.get("tier"))),
                        "cost": "",
                        "confirm": REVIEW,
                        "target": {"kind": "core", "id": _int(core.get("id"))},
                    })
                continue

            art_id = _int(cell.get("skill_id"))
            art = next((row for row in arts if _int(row.get("id")) == art_id), None)
            if art and _art_matches(core, art):
                placed.add(art_id)
                continue
            replacement = take_art(core)
            if replacement:
                steps.append({
                    "text": "「%s」第 %d 格把「%s」换成「%s」" % (
                        core.get("name"), index, art.get("name") if art else cell.get("name"),
                        replacement.get("name")),
                    "detail": "%s；换为 %s · %s" % (
                        _mismatch_text(meta, core, art or {}),
                        _element_name(meta, replacement.get("element")),
                        _tier_name(meta, replacement.get("tier"))),
                    "cost": "0 灵石（已学会）",
                    "confirm": CONFIRM,
                    "target": {"kind": "art", "id": _int(replacement.get("id"))},
                })
            else:
                gaps.append({"kind": "art", "sect": _int(core.get("sect")),
                             "element": _int(core.get("element")), "tier": _int(core.get("tier")),
                             "reason": "「%s」第 %d 格「%s」与本心法不一致" % (
                                 core.get("name"), index, art.get("name") if art else cell.get("name"))})
                steps.append({
                    "text": "「%s」第 %d 格「%s」与本心法不一致" % (
                        core.get("name"), index, art.get("name") if art else cell.get("name")),
                    "detail": "%s；暂无已学功法可替换" % _mismatch_text(meta, core, art or {}),
                    "cost": "",
                    "confirm": REVIEW,
                    "target": {"kind": "art", "id": art_id},
                })

    minutes = 0
    grouped = {}
    for bag in rows.get("bags") or []:
        if bag.get("learned"):
            continue
        key = (_int(bag.get("type")), _int(bag.get("target")))
        if key in grouped:
            grouped[key]["count"] += _int(bag.get("count"), 1)
            continue
        grouped[key] = {"bag": bag, "count": max(1, _int(bag.get("count"), 1))}
    for item in grouped.values():
        bag, count = item["bag"], item["count"]
        target = _int(bag.get("target"))
        kind = "心法" if _int(bag.get("type")) == 2 else "功法"
        catalog = cores if _int(bag.get("type")) == 2 else arts
        row = next((entry for entry in catalog if _int(entry.get("id")) == target), {})
        compre = row.get("comprehend") or {}
        minutes += _int(compre.get("time"))
        progress = "%d/%s" % (_int(bag.get("comprehend")), _int(bag.get("limit")) or "?")
        steps.append({
            "text": "参悟在包%s卷册「%s」（%s）%s" % (
                kind, bag.get("name"), progress, " ×%d" % count if count > 1 else ""),
            "detail": "参悟 %d 分钟" % _int(compre.get("time")) if compre else "参悟耗时未记录",
            "cost": "0 灵石",
            "confirm": CONFIRM,
            "minutes": _int(compre.get("time")),
            "target": {"kind": "bag", "id": _int(bag.get("uid"))},
        })

    equip = rows.get("equip") or {}
    support = equip.get("support_slots") or []
    if equip.get("support_recorded") and support:
        free = sum(1 for slot in support if not slot.get("skill_id"))
        for row in rows.get("resonance") or []:
            if not (row.get("learned") and not row.get("installed")):
                continue
            if free > 0:
                free -= 1
                steps.append({
                    "text": "共鸣槽装上「%s」" % row.get("name"),
                    "detail": _element_name(meta, row.get("element")),
                    "cost": "0 灵石（已学会）",
                    "confirm": CONFIRM,
                    "target": {"kind": "resonance", "id": _int(row.get("id"))},
                })
            else:
                steps.append({
                    "text": "共鸣槽已满，「%s」需要替换现有共鸣" % row.get("name"),
                    "detail": "替换规则未在配置中记录",
                    "cost": "",
                    "confirm": REVIEW,
                    "target": {"kind": "resonance", "id": _int(row.get("id"))},
                })

    counts = {}
    for slot in slots:
        core = next((row for row in cores if _int(row.get("id")) == _int(slot.get("core_id"))), None)
        if core and _int(core.get("element")):
            counts[_int(core.get("element"))] = counts.get(_int(core.get("element")), 0) + 1
    for element, count in sorted(counts.items()):
        if count <= 1:
            continue
        steps.append({
            "text": "同系心法同时运转 %d 本（%s）" % (count, _element_name(meta, element)),
            "detail": "游戏内对换/上限规则待复核，先保留现状",
            "cost": "",
            "confirm": REVIEW,
            "target": {"kind": "core_slots", "id": 0},
        })

    _categorize(steps)
    review = sum(1 for step in steps if step["confirm"] == REVIEW)
    if not steps:
        summary = "当前配装没有可补的缺口"
    else:
        summary = "共 %d 步，%d 步可直接执行，%d 步需要游戏内确认" % (
            len(steps), len(steps) - review, review)
    plan = {
        "id": "fix",
        "title": "方案 A · 先补现有配装",
        "summary": summary,
        "confirm": REVIEW if review else CONFIRM,
        "steps": steps,
        "totals": {"price": 0, "affinity": 0, "minutes": minutes},
        "note": "只使用已学会与在包资源；同名换版仅按同名字段对照，不推断升阶。",
    }
    return plan, gaps


def _plan_acquire(rows, meta, gaps):
    steps = []
    totals = {"price": 0, "affinity": 0, "minutes": 0}
    cores = rows.get("core_passives") or []
    arts = rows.get("arts") or []
    for gap in gaps:
        pool = cores if gap["kind"] == "core" else arts
        candidates = [
            row for row in pool
            if row.get("state") in ("尚未获得", "卷册在包")
            and (not gap.get("sect") or _int(row.get("sect")) == _int(gap.get("sect")))
            and (not gap.get("element") or _int(row.get("element")) == _int(gap.get("element")))
            and (not gap.get("tier") or _int(row.get("tier")) == _int(gap.get("tier")))
        ]
        if not candidates:
            steps.append({
                "text": "%s：没有同门同系的候选" % gap["reason"],
                "detail": "配置里找不到%s%s的条目" % (
                    _element_name(meta, gap.get("element")) if gap.get("element") else "",
                    _tier_name(meta, gap.get("tier"))),
                "cost": "",
                "confirm": REVIEW,
                "target": {"kind": gap["kind"], "id": 0},
            })
            continue
        row = _pick(candidates)[0]
        price, affinity, minutes = _acquire_cost(row)
        totals["price"] += price
        totals["affinity"] += affinity
        totals["minutes"] += minutes
        confirm = CONFIRM if row.get("state") == "卷册在包" or row.get("source") != "未开放" else REVIEW
        steps.append({
            "text": "%s：%s「%s」" % (gap["reason"], "心法" if gap["kind"] == "core" else "功法",
                                    row.get("name")),
            "detail": "%s · %s · %s" % (_sect_name(meta, row.get("sect")),
                                        _element_name(meta, row.get("element")),
                                        _source_text(meta, row)),
            "cost": _cost_text(price, affinity, minutes),
            "confirm": confirm,
            "target": {"kind": gap["kind"], "id": _int(row.get("id"))},
        })

    for step in steps:
        step["category"] = "获取"
    review = sum(1 for step in steps if step["confirm"] == REVIEW)
    if not steps:
        summary = "没有需要新获取的条目"
    else:
        summary = "共 %d 条获取路线，%d 条来源可确认，%d 条需要人工确认" % (
            len(steps), len(steps) - review, review)
    return {
        "id": "acquire",
        "title": "方案 B · 补齐缺口",
        "summary": summary,
        "confirm": REVIEW if review else CONFIRM,
        "steps": steps,
        "totals": totals,
        "note": "候选按「已有卷册 → 货架 → 请教 → 仅卷册 → 未开放」排列，仅为可执行顺序，不是推荐指数。",
    }


def build_schools(rows, meta):
    tier = _current_tier(rows, meta)
    cores = [row for row in rows.get("core_passives") or [] if _int(row.get("sect"))]
    arts = rows.get("arts") or []
    current_sect = _int((rows.get("character") or {}).get("sect_id"))
    out = []
    for sect in meta.get("sects") or []:
        if not sect.get("open"):
            continue
        sect_id = _int(sect.get("id"))
        pool = [row for row in cores if _int(row.get("sect")) == sect_id]
        if not pool:
            continue
        same_tier = [row for row in pool if _int(row.get("tier")) == tier]
        core_tier = tier if same_tier else max(_int(row.get("tier")) for row in pool)
        tier_pool = [row for row in pool if _int(row.get("tier")) == core_tier]
        tier_pool.sort(key=lambda row: (0 if row.get("state") != "尚未获得" else 1,
                                        _int(row.get("id"))))
        core = tier_pool[0]
        element = _int(core.get("element"))
        art_pool = [
            row for row in arts
            if _int(row.get("sect")) == sect_id
            and _int(row.get("tier")) == core_tier
            and (not element or _int(row.get("element")) == element)
        ]
        art_pool.sort(key=lambda row: (0 if row.get("state") != "尚未获得" else 1,
                                       0 if row.get("mystery") else 1,
                                       _int(row.get("id"))))
        picked = art_pool[:4]
        notes = []
        if not same_tier:
            notes.append("角色当前境界（%s）没有同档心法，展示该门派最高档（%s）" % (
                _tier_name(meta, tier) or "未识别", _tier_name(meta, core_tier)))
        if not element:
            notes.append("心法未记录元素，元素一致性无法判定")
        if len(picked) < 2:
            notes.append("同门同系同境界功法不足 2 本")
        elif len(picked) < 4:
            notes.append("本门同档功法共 %d 本，已全部列出" % len(picked))
        need = max([_int(item.get("need")) for item in core.get("tiers") or []] or [0])
        caveat = ""
        if need:
            caveat = "真意最高档需求 %d %s，是否达标请在游戏内确认（阈值机制待复核）" % (
                need, core.get("unit") or "层")
        out.append({
            "id": sect_id,
            "name": sect.get("name") or "",
            "current": sect_id == current_sect,
            "element": element,
            "element_name": _element_name(meta, element),
            "tier": core_tier,
            "tier_name": _tier_name(meta, core_tier),
            "status": CONFIRM if (element and len(picked) >= 2) else REVIEW,
            "core": {
                "id": _int(core.get("id")),
                "name": core.get("name"),
                "state": core.get("state"),
                "slots": _int(core.get("slots")),
                "stack": core.get("stack") or "",
                "unit": core.get("unit") or "",
            },
            "arts": [{
                "id": _int(row.get("id")),
                "name": row.get("name"),
                "state": row.get("state"),
                "mystery": bool(row.get("mystery")),
            } for row in picked],
            "learned": sum(1 for row in picked
                           if row.get("state") in ("已运转", "已学会未运转")),
            "note": "；".join(notes),
            "caveat": caveat,
        })
    out.sort(key=lambda item: (0 if item["current"] else 1, _int(item["tier"]), item["id"]))
    return out


def build_plans(rows, meta):
    fix, gaps = _plan_fix(rows, meta)
    return {"plans": [fix, _plan_acquire(rows, meta, gaps)], "schools": build_schools(rows, meta)}
