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
            "name": _text(row.get("itemName")) or ("物品 %s" % row["id"]),
            "type": item_types.get(str(row.get("itemType")), "") or "未分类",
            "quality": row.get("quality"),
            "price": row.get("price"),
            # 物品说明：告诉玩家这玩意儿有什么用，是判断值不值得偷/要的依据。
            "desc": _plain(_text(row.get("itemDesc"))),
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
    result = {"schema": SCHEMA, "items": items, "npcs": npcs, "intimacy": tiers,
              "spaces": build_spaces(tables), "realms": realms}
    result.update(_gift_pool_meta(tables))
    return result


# 插件统一入口
build = build_items
