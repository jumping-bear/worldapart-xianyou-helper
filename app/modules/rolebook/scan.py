# -*- coding: utf-8 -*-
"""人物志扫描：按 npcId 标注玩家与该 NPC 的实际状态（好感/亲密/道侣/已结识）。

只读存档，不改任何数据。好感取法与 quest/scan.py 一致（npcs[].intimacy），
道侣取 playerModel.npc_dao_ally.npc_ids（与留影石一致）。
"""
import os


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _id_set(value):
    out = set()
    if isinstance(value, dict):
        value = value.values()
    for item in value or ():
        nid = _int(item)
        if nid:
            out.add(nid)
    return out


def meta(metadata):
    return metadata.get("rolebook") or {"npcs": [], "meta": {}, "stats": {"total": 0}}


def prepare(game_dir):
    return None


def _intimacy_tier(tiers, favor):
    hit = None
    for tier in tiers or []:
        minimum = _int(tier.get("min"))
        if minimum <= favor and (hit is None or minimum > _int(hit.get("min"))):
            hit = tier
    return hit


def scan(obj, meta_obj, state=None):
    """产出 {states: {npcId: {...}}, stats: {...}}，玩家实际状态按 npcId 索引。"""
    player = (obj or {}).get("playerModel") or {}
    tiers = ((meta_obj or {}).get("meta") or {}).get("intimacy_tiers") or []

    # 好感/亲密：与 quest 一致，从 npcs 记录取 npcCfgId + intimacy
    favor = {}
    met = set()
    for record in (obj or {}).get("npcs", {}).values() if isinstance((obj or {}).get("npcs"), dict) else []:
        if not isinstance(record, dict):
            continue
        npc_id = _int(record.get("npcCfgId"))
        if not npc_id:
            continue
        met.add(npc_id)
        favor[npc_id] = _int(record.get("intimacy"))

    # 道侣：playerModel.npc_dao_ally.npc_ids
    dao = _id_set((player.get("npc_dao_ally") or {}).get("npc_ids"))

    # 兼容：部分存档把好感放在交互属性里，键为 npcId
    interact = (player.get("npcComponent") or {}).get("interactAttributes") \
        or player.get("interactAttributes") or {}
    if isinstance(interact, dict):
        for key, value in interact.items():
            npc_id = _int(key)
            if not npc_id:
                if isinstance(value, dict):
                    npc_id = _int(value.get("npcId") or value.get("npcCfgId"))
            if not npc_id or not isinstance(value, dict):
                continue
            if npc_id not in favor and ("intimacy" in value or "favor" in value):
                favor[npc_id] = _int(value.get("intimacy", value.get("favor")))
                met.add(npc_id)

    states = {}
    for npc_id in set(favor) | met | dao:
        value = _int(favor.get(npc_id))
        is_dao = npc_id in dao
        tier = _intimacy_tier(tiers, value) or {}
        states[str(npc_id)] = {
            "favor": value,
            "met": npc_id in met or is_dao,
            "dao": is_dao,
            "tier": tier.get("name") or "",
            "tier_index": tiers.index(tier) if tier in tiers else -1,
        }

    stats = {
        "met": len(met), "dao": len(dao),
        "tracked": len(states),
    }
    return {"states": states, "stats": stats}


def post(rows, state, original, path):
    if isinstance(rows, dict):
        rows["src"] = os.path.basename(original) if original else os.path.basename(path or "")
    return rows


def enrich(module, meta_obj, state=None):
    """把构建期全息卡与存档实测状态合并，供 view.js 直接渲染。"""
    module = dict(module or {})
    built = meta_obj or {}
    meta = built.get("meta") or {}
    tiers = meta.get("intimacy_tiers") or []
    scanned = module.get("rows") if isinstance(module.get("rows"), dict) else {}
    states = scanned.get("states") or {}
    live_stats = scanned.get("stats") or {}

    npcs = []
    for card in built.get("npcs") or []:
        npc = dict(card)
        live = states.get(str(npc.get("id"))) or {}
        favor = _int(live.get("favor"))
        npc["favor"] = favor
        npc["met"] = bool(live.get("met"))
        npc["dao"] = bool(live.get("dao")) or bool(npc.get("dao"))
        tier = _intimacy_tier(tiers, favor) or {}
        npc["intimacy_name"] = live.get("tier") or tier.get("name") or ""
        idx = live.get("tier_index", -1)
        if (idx is None or idx < 0) and tier in tiers:
            idx = tiers.index(tier)
        npc["intimacy_index"] = idx
        npcs.append(npc)

    module["npcs"] = npcs
    module["meta"] = meta
    module["stats"] = built.get("stats") or {}
    module["live_stats"] = live_stats
    return module


def summary(module):
    stats = module.get("stats") or {}
    npcs = module.get("npcs") or []
    return ("人物志：%d 位 NPC，%d 位有头像，%d 位可结道侣，%d 位可击杀（%d 位恶名安全目标），"
            "%d 位有留影关联" % (
                stats.get("total", 0), stats.get("with_avatar", 0), stats.get("dao", 0),
                stats.get("killable", 0), stats.get("safe_target", 0),
                stats.get("with_memoria", 0)))
