# -*- coding: utf-8 -*-
"""NPC物品：配置表 → 模块快照（自 meta_update.py 原样搬入）。"""
import re

from meta_update import (
    SCHEMA, _int, _rows, _text, build_realms, build_spaces,
)

# 物品说明里带游戏富文本标记（<color=#ffc600>…</color>、<b>…</b>，以及只给颜色的
# <#7fc368>），展示前要剥掉，否则玩家看到的就是一堆尖括号。只吃掉带标签名或
# 十六进制色的尖括号，避免误伤正常文案。
_RICH_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9_]*(?:=[^<>]{0,40})?/?>|<#[0-9A-Fa-f]{3,8}>")


def _plain(text):
    """去掉富文本标记与多余空白，得到可直接展示的一行说明。"""
    return " ".join(_RICH_TAG.sub("", str(text or "")).split())


def _constant_values(tables):
    """tbconstants 有主表和多张分表，全部合并后再取常量，避免同键折叠时丢字段。"""
    result = {}
    for name, value in tables.items():
        if name != "tbconstants" and not str(name).startswith("tbconstants."):
            continue
        for row in _rows(value):
            if isinstance(row, dict):
                for key, item in row.items():
                    result[str(key)] = item
    return result


def _collect_drop_items(drop_id, drops, out, seen=None, depth=0):
    """递归展开掉落表：dropList 直接给物品，rewardDropList 指向下一张表。"""
    if not drop_id or depth > 8:
        return
    key = str(drop_id)
    if seen is None:
        seen = set()
    if key in seen:
        return
    seen.add(key)
    row = drops.get(key) or {}
    for variant in row.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        for entry in variant.get("dropList") or []:
            if isinstance(entry, dict) and entry.get("itemId") is not None:
                out.add(_int(entry.get("itemId")))
        for entry in variant.get("rewardDropList") or []:
            if isinstance(entry, dict) and entry.get("rewardDropId") is not None:
                _collect_drop_items(entry.get("rewardDropId"), drops, out, seen, depth + 1)


def _gift_pool_meta(tables):
    """AI 聊天赠礼：按境界档展开四张掉落表，并派生境界分档边界。"""
    constants = _constant_values(tables)
    drops = {str(row.get("id")): row for row in _rows(tables.get("tbrewarddrop") or [])
             if isinstance(row, dict) and row.get("id") is not None}
    keys = (("1", "AINPC_CHAT_REWARD_LIANQI_DROP_ID"),
            ("2", "AINPC_CHAT_REWARD_ZHUJI_DROP_ID"),
            ("3", "AINPC_CHAT_REWARD_JIEDAN_DROP_ID"),
            ("4", "AINPC_CHAT_REWARD_YUANYING_DROP_ID"))
    pools = {}
    for bucket, key in keys:
        items = set()
        _collect_drop_items(_int(constants.get(key)), drops, items)
        pools[bucket] = sorted(items)
    phases = {}
    for row in _rows(tables.get("tbcultivaterealm") or []):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        values = [_int(x) for x in (row.get("phases") or []) if _int(x) > 0]
        if values:
            phases[_int(row.get("id"))] = min(values)
    limits = [phases[r] - 1 for r in (2, 3, 4) if r in phases]
    return {
        "gift_pools": pools,
        "gift_bucket_limits": limits,
        "gift_cycle_days": _int(constants.get("AINPC_CHAT_REWARD_CYCLE_DAYS")),
        "gift_total_count": _int(constants.get("AINPC_CHAT_REWARD_CYCLE_TOTAL_COUNT")),
        "gift_per_npc_count": _int(constants.get("AINPC_CHAT_REWARD_PER_NPC_MAX_COUNT")),
    }


# 只展示设定文案、不在行内展开效果的类型：材料、药材、器胚、法宝、璞石、妖丹、
# 文玩礼物、货币等。其余类型（功法、心法、丹药、灵物、灵根果等）的说明本身就是
# 效果，直接放进行内。
LORE_TYPES = frozenset({4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 21, 93, 99})
SCOPE_BOTH = ("战斗内外均可使用", "戰鬥內外均可使用", "usable in and out of battle")
SCOPE_BATTLE = ("仅限战斗中使用", "僅限戰鬥中使用", "can only be used in combat")


def _split_scope(text):
    """丹药说明末尾的使用范围拆成标签，正文只留效果。"""
    raw = text or ""
    low = raw.lower()
    for phrase in SCOPE_BOTH:
        if phrase.lower() in low:
            return raw.replace(phrase, "").strip(" ·，,。\n"), "战斗内/外可用"
    for phrase in SCOPE_BATTLE:
        if phrase.lower() in low:
            return raw.replace(phrase, "").strip(" ·，,。\n"), "仅限战斗"
    return raw, ""


def _item_extras(items, tables):
    """按品类补五行与用途标签；五行只从配置里的真实来源推导，缺失就不显示。"""
    elements = {_int(r.get("id")): _text(r.get("element_name"))
                for r in _rows(tables.get("tbelement") or []) if isinstance(r, dict)}
    materials = {}
    for row in _rows(tables.get("tbalchemymaterial") or []):
        if isinstance(row, dict):
            materials[_int(row.get("id"))] = (_int(row.get("element_type")),
                                             _int(row.get("spirit_value")))
    herbs = {}
    for row in _rows(tables.get("tbpillherb") or []):
        if isinstance(row, dict) and row.get("item_id") is not None:
            herbs[_int(row.get("item_id"))] = (_int(row.get("element")), _int(row.get("tier")),
                                              bool(row.get("is_rare")))
    skills = {_int(r.get("item_id")): r for r in _rows(tables.get("tbskill") or [])
              if isinstance(r, dict) and _int(r.get("item_id"))}
    passives = {_int(r.get("item_id")): r for r in _rows(tables.get("tbpassiveskill") or [])
                if isinstance(r, dict) and _int(r.get("item_id"))}
    attributes = {_int(r.get("id")): _text(r.get("name"))
                  for r in _rows(tables.get("tbattribute") or []) if isinstance(r, dict)}
    prototypes, outputs = {}, {}
    for row in _rows(tables.get("tbalchemyprototype") or []):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        pid = _int(row.get("id"))
        prototypes[pid] = row
        elems = [_int(e.get("element_type")) for e in (row.get("effects") or [])
                 if isinstance(e, dict) and _int(e.get("element_type"))]
        element = elems[0] if elems else 0
        for tier in row.get("score_tiers") or []:
            oid = _int(tier.get("output_item_id")) if isinstance(tier, dict) else 0
            if oid:
                old = outputs.get(oid)
                if old is None or (not old[0] and element):
                    outputs[oid] = (element, pid)
    for key, item in items.items():
        iid = _int(key)
        tid = item.get("type_id") or 0
        element, tags, detail = 0, [], ""
        if tid == 9 and iid in materials:
            element, spirit = materials[iid]
            if spirit:
                tags.append("灵气 %d" % spirit)
        elif tid in (21, 99) and iid in herbs:
            element, tier, rare = herbs[iid]
            if tier:
                tags.append("%d 阶" % tier)
            if rare:
                tags.append("稀有")
        elif tid == 8 and iid in prototypes:
            proto = prototypes[iid]
            elems = [_int(e.get("element_type")) for e in (proto.get("effects") or [])
                     if isinstance(e, dict) and _int(e.get("element_type"))]
            element = elems[0] if elems else 0
            outs = []
            for tier in proto.get("score_tiers") or []:
                oid = _int(tier.get("output_item_id")) if isinstance(tier, dict) else 0
                if oid and oid not in outs:
                    outs.append(oid)
            out_name = (items.get(str(outs[0])) or {}).get("name") if outs else ""
            if out_name:
                tags.append("可炼 %s" % out_name)
            spirit = _int(proto.get("recommended_total_spirit"))
            if spirit:
                tags.append("推荐灵气 %d" % spirit)
            tiers = [t for t in (proto.get("score_tiers") or []) if isinstance(t, dict)]
            if tiers:
                best = max(tiers, key=lambda t: _int(t.get("score_min")))
                attrs = []
                for attr in best.get("attributes") or []:
                    if not isinstance(attr, dict):
                        continue
                    name = attributes.get(_int(attr.get("type"))) or ""
                    if name:
                        attrs.append("%s +%s" % (name, attr.get("value")))
                if attrs:
                    detail = "最高评价属性：" + "、".join(attrs)
        elif tid in (16, 17) and iid in outputs:
            element = outputs[iid][0]
        elif tid == 95 and iid in skills:
            element = _int(skills[iid].get("element"))
        elif tid == 3 and iid in passives:
            element = _int(passives[iid].get("element"))
        if tid in (18, 19):
            effect, scope = _split_scope(item.get("desc") or "")
            if scope:
                tags.append(scope)
        else:
            effect = "" if tid in LORE_TYPES else (item.get("desc") or "")
        if item.get("can_gift"):
            tags.append("可赠予NPC")
        # 没有五行也没有用途标签的品类（如璞石、炼丹炉、缺少炼器配置的器胚），
        # 退回到展示说明本身，避免行内只剩一个名字。
        if not effect and not tags and not element:
            effect = item.get("desc") or ""
        item["element"] = element
        item["element_name"] = elements.get(element, "")
        item["tags"] = tags
        item["detail"] = detail
        item["effect"] = effect


def build_items(tables):
    """NPC物品：名称、类型、品质、偷窃参数、索要模板、可赠私物与持有者的可偷状态。"""
    item_types = {}
    for row in _rows(tables["tbitemtype"]):
        if isinstance(row, dict) and row.get("id") is not None:
            item_types[str(row["id"])] = _text(row.get("typeName"))
    steals = {str(r.get("id")): r for r in _rows(tables["tbsteal"]) if isinstance(r, dict)}
    items = {}
    for row in _rows(tables["tbitem"]):
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        rule = steals.get(str(row.get("steal_id"))) if row.get("steal_id") else None
        steal = None
        if rule:
            steal = {
                "rate": int(round(float(rule.get("rate_base") or 0) * 100)),
                "count": rule.get("steal_count") or 1,
                "kill": bool(rule.get("trigger_kill")),
                "intimacy": rule.get("intimacy_delta_self") or 0,
                "alignment": rule.get("alignment_delta_success") or 0,
            }
        items[str(row["id"])] = {
            "name": _text(row.get("itemName")) or ("未识别物品"),
            "type": item_types.get(str(row.get("itemType")), "") or "未分类",
            "type_id": _int(row.get("itemType")),
            "quality": row.get("quality"),
            "price": row.get("price"),
            # 物品说明：完整文案留给悬停，行内是否展示由 _item_extras 按品类决定。
            "desc": _plain(_text(row.get("itemDesc"))),
            "can_gift": bool(row.get("canGift")),
            "steal": steal,
            "demand": bool(row.get("canDemand")),
            "demand_cost": _int(row.get("intimacy_deduction")),
        }
    realms = build_realms(tables)
    # 索要：tbnpcbagrule 按 NPC 配置指向索要模板，模板里是该 NPC 可被索要的固定物品池。
    templates = {str(r.get("id")): r for r in _rows(tables["tbnpcitemdemandholdtemplate"])
                 if isinstance(r, dict) and r.get("id") is not None}
    demands = {}
    supplies = {}
    for rule in _rows(tables["tbnpcbagrule"]):
        if not isinstance(rule, dict) or rule.get("npcId") is None:
            continue
        npc_key = str(rule.get("npcId"))
        supply = {_int(entry.get("itemId")) for entry in (rule.get("supplyItemList") or [])
                  if isinstance(entry, dict) and entry.get("itemId") is not None}
        if supply:
            supplies[npc_key] = sorted(supply)
        template = templates.get(str(rule.get("demandTemplateId")))
        if not template:
            continue
        ids = []
        for entry in template.get("demandItemList") or []:
            if isinstance(entry, dict) and entry.get("itemId") is not None:
                ids.append(_int(entry.get("itemId")))
        if ids:
            demands[str(rule.get("npcId"))] = ids
    tiers = []
    for row in _rows(tables["tbnpcintimacy"]):
        if not isinstance(row, dict) or row.get("intimacyRequirement") is None:
            continue
        name = _text(row.get("intimacyName")).replace("\u200b", "").strip()
        if not name:
            continue
        tiers.append({"name": name, "need": _int(row.get("intimacyRequirement"))})
    tiers.sort(key=lambda t: t["need"])
    npc_rows = [r for r in _rows(tables["tbnpcbasecfg"]) if isinstance(r, dict)]
    # 若整张表都没有 can_steal 字段，视为该版本取消了这层限制，改由物品参数单独判定。
    has_flag = any("can_steal" in row for row in npc_rows)
    npcs = {}
    for row in npc_rows:
        if row.get("id") is None:
            continue
        layer = row.get("propLayerId")
        npcs[str(row["id"])] = {
            "name": _text(row.get("npcName")) or _text(row.get("npcTitle")) or ("#%s" % row["id"]),
            "realm": realms.get(str(layer or 0)) or _text(row.get("layerZeroShowText")) or "凡人",
            "can_steal": bool(row.get("can_steal", True)) if has_flag else True,
            "demand": demands.get(str(row["id"])) or [],
            "supply": supplies.get(str(row["id"])) or [],
        }
    if not items:
        raise ValueError("物品配置为空")
    _item_extras(items, tables)
    result = {"schema": SCHEMA, "items": items, "npcs": npcs, "intimacy": tiers,
              "spaces": build_spaces(tables), "realms": realms}
    result.update(_gift_pool_meta(tables))
    return result


# 插件统一入口
build = build_items
