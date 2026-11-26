# -*- coding: utf-8 -*-
"""心法与功法：配置表 → 模块快照。

只做「配装体检 + 获取路线」需要的字段，不复制全量配置；
所有维度（门派、元素、境界、档位、槽位、价格）都从表里派生，视图不写死。
"""
import json
import re

from meta_update import SCHEMA, _clip, _int, _plain, _rows, _text, build_realms

DESC_LIMIT = 300
SIZE_LIMIT = 800 * 1024


def _element_map(tables):
    out = {}
    for row in _rows(tables.get("tbelement")):
        if isinstance(row, dict) and row.get("id") is not None:
            out[str(row["id"])] = _text(row.get("element_name")) or ("未识别属性")
    out["0"] = "无"
    return out


def _realm_maps(tables):
    """返回 (境界名 map, 境界层起点 → 境界名, 境界层 id → 层信息)。"""
    realms, phases, layers = build_realms(tables), {}, {}
    for row in _rows(tables.get("tbcultivaterealm")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        name = realms.get(str(row["id"])) or ("境界%s" % row["id"])
        for phase in row.get("phases") or []:
            phase = _int(phase)
            if phase:
                phases[str(phase)] = name
    for row in _rows(tables.get("tbcultivatelayer")):
        if isinstance(row, dict) and row.get("id") is not None:
            layers[str(row["id"])] = {"phase": _int(row.get("phase")),
                                      "layer": _int(row.get("layer"))}
    return realms, phases, layers


def _tier_phase(tables):
    """功法境界（skill_tier）→ 该境界的起始层号。"""
    out = {}
    for row in _rows(tables.get("tbcultivaterealm")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        starts = [_int(x) for x in row.get("phases") or [] if _int(x)]
        if starts:
            out[_int(row["id"])] = min(starts)
    return out


def _stack_info(raw):
    """从「当前<..>剑气</color>：{0}/{1}层」提取资源名与单位。"""
    text = _plain(raw)
    if not text:
        return "", "层"
    index = text.find("{0}")
    prefix = text[:index] if index >= 0 else text
    prefix = re.sub(r"^(当前|目标)", "", prefix).strip(" ：:，,。;；")
    unit = "%" if "%" in text else ("点" if "点" in text else "层")
    return prefix, unit


def build(tables):
    warnings = []

    npc_names = {}
    for row in _rows(tables.get("tbnpcbasecfg")):
        if isinstance(row, dict) and row.get("id") is not None:
            name = _text(row.get("npcName")) or _text(row.get("npcTitle"))
            if name:
                npc_names[str(row["id"])] = name

    def npc_name(npc_id):
        return npc_names.get(str(npc_id)) or ("NPC %s" % npc_id)

    item_names, item_prices = {}, {}
    for row in _rows(tables.get("tbitem")):
        if isinstance(row, dict) and row.get("id") is not None:
            key = str(row["id"])
            item_names[key] = _text(row.get("itemName")) or ("未识别物品")
            item_prices[key] = _int(row.get("price"))

    shops = {}
    for rule in _rows(tables.get("tbnpcbagrule")):
        if not isinstance(rule, dict):
            continue
        npc_id = rule.get("npcId")
        for entry in rule.get("supplyItemList") or []:
            item_id = _int(entry.get("itemId") if isinstance(entry, dict) else entry)
            if not item_id:
                continue
            bucket = shops.setdefault(str(item_id), [])
            if not any(item["npc"] == npc_id for item in bucket):
                bucket.append({"npc": npc_id, "name": npc_name(npc_id)})

    skills = {_int(row.get("id")): row for row in _rows(tables.get("tbskill"))
              if isinstance(row, dict)}
    levels = {_int(row.get("id")): row for row in _rows(tables.get("tbskilllevel"))
              if isinstance(row, dict)}

    def tier_item(skill_id):
        skill_id = _int(skill_id)
        skill = skills.get(skill_id) or {}
        desc = _plain((levels.get(skill_id) or {}).get("des")) or _plain(skill.get("des"))
        return {"need": 0, "skill": skill_id, "name": _text(skill.get("name")),
                "desc": _clip(desc, DESC_LIMIT)}

    realms, phases, layers = _realm_maps(tables)
    tier_phase = _tier_phase(tables)

    elements = _element_map(tables)

    sects = []
    for row in _rows(tables.get("tbsect")):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        sect_id = _int(row["id"])
        sects.append({
            "id": sect_id,
            "name": _text(row.get("sectName")) or ("门派 %s" % sect_id),
            "short": _text(row.get("short_name")),
            "elements": [_int(x) for x in row.get("element_ids") or [] if _int(x)],
            "open": bool(row.get("show_in_overview")),
            "join_realm": _int(row.get("join_realm_id")),
        })
    sects.sort(key=lambda item: (not item["open"], item["id"]))

    intimacy = []
    for row in _rows(tables.get("tbnpcintimacy")):
        if isinstance(row, dict) and row.get("intimacyRequirement") is not None:
            intimacy.append({"need": _int(row.get("intimacyRequirement")),
                             "name": _text(row.get("intimacyName"))})
    intimacy.sort(key=lambda item: item["need"])

    learn = {}
    for row in _rows(tables.get("tbminigamelearngongfa")):
        if not isinstance(row, dict):
            continue
        target_type, target_id = _int(row.get("target_type")), _int(row.get("target_id"))
        if target_type and target_id:
            learn[(target_type, target_id)] = {
                "time": _int(row.get("time_consuming")),
                "limit": _int(row.get("comprehend_value_limit")),
            }

    core_teach = {_int(row.get("id")): row for row in _rows(tables.get("tbpassiveskillteachguide"))
                  if isinstance(row, dict)}
    art_teach = {_int(row.get("id")): row for row in _rows(tables.get("tbskillteachguide"))
                 if isinstance(row, dict)}

    def teach_of(row, visible_key=None):
        if not row:
            return None
        out = {"realm": _int(row.get("consult_required_realm")),
               "affinity": _int(row.get("consult_affinity_required")),
               "cost": _int(row.get("consult_affinity_cost"))}
        if visible_key:
            out["visible"] = bool(row.get(visible_key))
        return out

    intro = {}
    for row in _rows(tables.get("tbsectintroskill")):
        if isinstance(row, dict) and _int(row.get("skill_item_id")):
            intro[str(_int(row.get("skill_item_id")))] = row

    raw_cores = [row for row in _rows(tables.get("tbpassiveskill"))
                 if isinstance(row, dict) and _int(row.get("ability_kind")) == 5]
    groups = {}
    for row in raw_cores:
        key = (_text(row.get("name")), _int(row.get("skill_tier")), _int(row.get("sect_id")))
        groups.setdefault(key, []).append(row)
    kept, excluded = [], []
    for rows in groups.values():
        rows.sort(key=lambda row: (bool(row.get("sub_passives")),
                                   _int(row.get("item_id")) != 0,
                                   _int(row.get("id"))), reverse=True)
        kept.append(rows[0])
        for extra in rows[1:]:
            excluded.append({"id": _int(extra.get("id")),
                             "reason": "同名同境界重复，且缺少真意档位/卷册"})
    kept.sort(key=lambda row: (_int(row.get("sect_id")), _int(row.get("skill_tier")),
                               _int(row.get("id"))))

    book_ids, core_passives = set(), []
    for row in kept:
        core_id = _int(row.get("id"))
        book = _int(row.get("item_id"))
        stack, unit = _stack_info(row.get("text_skillBuff_stack"))
        if not stack:
            warnings.append("心法 %s 的层数资源名未识别" % core_id)
        tiers = []
        for sub in row.get("sub_passives") or []:
            if not isinstance(sub, dict):
                continue
            item = tier_item(sub.get("skill_id"))
            item["need"] = _int(sub.get("element_count"))
            if not item["name"]:
                warnings.append("真意技能 %s 缺少名称" % item["skill"])
            tiers.append(item)
        tiers.sort(key=lambda item: (item["need"], item["skill"]))
        if book:
            book_ids.add(book)
        core_passives.append({
            "id": core_id,
            "name": _text(row.get("name")) or ("心法 %s" % core_id),
            "element": _int(row.get("element")),
            "tier": _int(row.get("skill_tier")),
            "sect": _int(row.get("sect_id")),
            "slots": _int(row.get("skill_slot_count")),
            "book": book,
            "price": item_prices.get(str(book), 0) if book else 0,
            "stack": stack,
            "unit": unit,
            "init": [_int(x) for x in row.get("init_skills") or [] if _int(x)],
            "tiers": tiers,
            "teach": teach_of(core_teach.get(core_id)),
            "comprehend": learn.get((2, core_id)),
            "desc": _clip(_plain(row.get("des")), DESC_LIMIT),
            "shops": shops.get(str(book), []) if book else [],
        })
    if not core_passives:
        raise ValueError("心法配置为空（tbpassiveskill ability_kind=5）")

    arts, missing_intro = [], 0
    for row in _rows(tables.get("tbskill")):
        if not isinstance(row, dict) or _int(row.get("ability_kind")) != 2 or not row.get("sect_id"):
            continue
        art_id, book = _int(row.get("id")), _int(row.get("item_id"))
        desc = _plain((levels.get(art_id) or {}).get("des")) or _plain(row.get("des"))
        intro_row = intro.get(str(book)) if book else None
        if book and intro_row is None:
            missing_intro += 1
        if book:
            book_ids.add(book)
        arts.append({
            "id": art_id,
            "name": _text(row.get("name")) or ("功法 %s" % art_id),
            "element": _int(row.get("element")),
            "tier": _int(row.get("skill_tier")),
            "sect": _int(row.get("sect_id")),
            "mystery": bool((intro_row or {}).get("is_mystery")),
            "book": book,
            "price": item_prices.get(str(book), 0) if book else 0,
            "teach": teach_of(art_teach.get(art_id), "consult_visible"),
            "comprehend": learn.get((1, art_id)),
            "desc": _clip(desc, DESC_LIMIT),
            "costs": [{"type": _int(c.get("type")), "value": _int(c.get("value"))}
                      for c in row.get("costs") or [] if isinstance(c, dict)],
            "grade": row.get("skill_grade_correction") or 0,
            "shops": shops.get(str(book), []) if book else [],
        })
    if not arts:
        raise ValueError("功法配置为空（tbskill ability_kind=2 且 sect_id 非空）")
    if missing_intro:
        warnings.append("说明：%d 本功法不在 tbsectintroskill 中，秘传标记按否展示" % missing_intro)

    resonance_rows = [row for row in _rows(tables.get("tbskill"))
                      if isinstance(row, dict) and _int(row.get("ability_kind")) == 3]
    by_name = {}
    for row in resonance_rows:
        by_name.setdefault(_text(row.get("name")), row)
    assigned = {}
    for row in _rows(tables.get("tbskill")):
        if not isinstance(row, dict) or not row.get("resonance_npc_id"):
            continue
        des = _plain((levels.get(_int(row.get("id"))) or {}).get("des"))
        match = re.search(r"【(.+?)】", des)
        skill = by_name.get(match.group(1)) if match else None
        if not skill:
            warnings.append("共鸣词条 %s 未能匹配到技能文案" % _int(row.get("id")))
            continue
        skill_id = _int(skill.get("id"))
        if skill_id in assigned:
            warnings.append("共鸣技能 %s 被多个 NPC 引用，已保留首个" % skill_id)
            continue
        assigned[skill_id] = {"npc": _int(row.get("resonance_npc_id")),
                              "tier": _int(row.get("skill_tier"))}

    resonance = []
    for row in resonance_rows:
        skill_id = _int(row.get("id"))
        tier = _int(row.get("skill_tier"))
        info = assigned.get(skill_id)
        item = {
            "id": skill_id,
            "name": _text(row.get("name")) or ("共鸣 %s" % skill_id),
            "element": _int(row.get("element")),
            "tier": tier,
            "desc": _clip(_plain((levels.get(skill_id) or {}).get("des")), DESC_LIMIT),
        }
        if info:
            item.update({"npc": info["npc"], "npc_name": npc_name(info["npc"]),
                         "unlock_layer": tier_phase.get(info["tier"]) or 0, "source": "npc"})
        else:
            item.update({"npc": 0, "npc_name": "", "unlock_layer": 0, "source": "unopened"})
        resonance.append(item)
    resonance.sort(key=lambda item: (item["tier"], item["id"]))
    if not resonance:
        warnings.append("未找到共鸣技能（tbskill ability_kind=3）")

    used_npcs = {}
    for bucket in shops.values():
        for item in bucket:
            used_npcs[str(item["npc"])] = item["name"]
    for item in resonance:
        if item["npc"]:
            used_npcs[str(item["npc"])] = item["npc_name"]

    data = {
        "schema": SCHEMA,
        "elements": elements,
        "realms": realms,
        "phases": phases,
        "tier_phase": {str(key): value for key, value in sorted(tier_phase.items())},
        "layers": layers,
        "sects": sects,
        "intimacy": intimacy,
        "core_passives": core_passives,
        "arts": arts,
        "resonance": resonance,
        "names": {
            "npc": {key: used_npcs[key] for key in sorted(used_npcs, key=lambda x: int(x))},
            "item": {str(i): item_names[str(i)] for i in sorted(book_ids)
                     if item_names.get(str(i))},
        },
        "stats": {"core": len(core_passives), "arts": len(arts),
                  "resonance": len(resonance), "books": len(book_ids),
                  "excluded": excluded},
        "warnings": warnings,
    }
    size = len(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if size > SIZE_LIMIT:
        raise ValueError("心法与功法快照过大：%.1f KB（上限 800 KB）" % (size / 1024.0))
    return data
