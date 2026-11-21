# -*- coding: utf-8 -*-
"""人物图鉴扫描：按 npcId 标注玩家与该 NPC 的实际关系与状态。

只读存档，不改任何数据。数据来源：
- 当前位置：存档 spaces[currentSpaceUuid].spaceId → 构建期 meta.spaces（"父地点 / 子地点"）；
- 好感：npcs[].intimacy（与 quest 一致）；
- 关系网：playerModel.npc_relation（师承/道侣/朋友/敌人/冰封/已故/弟子）；
- 道侣：npc_dao_ally.npc_ids + npc_relation.dao_companion_npc_ids；
- 住处：npc_housing.residents / unlocked（已入住/可邀请）；
- 履历：npc_cultivation_history / demonic_cultivator / player_prop_evil / visited_spaces；
- 头像：复用留影石已导出的 memoria_avatars_meta.json（dataURI），缺失退回首字。
"""
import json
import os
from functools import lru_cache

# 头像快照由留影石 avatars.py 导出，人物志只读复用；缺失时页面退回首字头像
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_AVATARS_FILE = os.path.join(_ROOT, "memoria_avatars_meta.json")

# 关系类型 -> 展示标签（关系网可视化用）
REL_LABELS = (
    ("master", "师尊"), ("disciple", "弟子"), ("dao", "道侣"),
    ("friend", "朋友"), ("enemy", "仇敌"), ("frozen", "冰封"),
    ("deceased", "已故"),
)


def _int(value, default=None):
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
        if isinstance(item, dict):
            nid = _int(item.get("npc_id") or item.get("npcCfgId") or item.get("id"))
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
        minimum = _int(tier.get("min"), 0)
        if minimum <= favor and (hit is None or minimum > _int(hit.get("min"), 0)):
            hit = tier
    return hit


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
    return images.get(str(npc_id), "")


def _avatar_ref(npc_id):
    """返回头像在快照里的键，不复制 dataURI；页面端按键去重后再取图。"""
    images, icons = _load_avatars()
    key = icons.get(str(npc_id)) or str(npc_id)
    return key if key in images else ""


def scan(obj, meta_obj, state=None):
    """产出 {states, locs, stats, player}，玩家实际状态按 npcId 索引。"""
    player = (obj or {}).get("playerModel") or {}
    built_meta = (meta_obj or {}).get("meta") or {}
    tiers = built_meta.get("intimacy_tiers") or []
    space_index = built_meta.get("spaces") or {}
    save_spaces = (obj or {}).get("spaces") or {}

    # NPC id -> 名字（来自构建期全息卡，用于关系网展示）
    name_of = {}
    for card in (meta_obj or {}).get("npcs") or []:
        if isinstance(card, dict) and card.get("id") is not None:
            name_of[_int(card["id"])] = card.get("name") or str(card["id"])

    # 好感/亲密 + 实时位置：位置按"在存档里"记录，是否展示不看交情
    favor = {}
    locs = {}
    realtime = {}
    records = (obj or {}).get("npcs")
    for record in records.values() if isinstance(records, dict) else ():
        if not isinstance(record, dict):
            continue
        npc_id = _int(record.get("npcCfgId"))
        if not npc_id:
            continue
        favor[npc_id] = _int(record.get("intimacy"), 0)
        space = save_spaces.get(record.get("currentSpaceUuid")) or {}
        path = space_index.get(str(space.get("spaceId"))) or ""
        parts = [part for part in path.split(" / ") if part] if path else []
        locs[npc_id] = {
            "path": " / ".join(parts),
            "name": parts[-1] if parts else "",
            "region": parts[0] if parts else "",
            # worldStatus 2 = 寿元已尽/已退隐，存档保留记录但世界里已经没有这个人
            "gone": _int(record.get("worldStatus")) == 2,
        }
        cult = record.get("cultivation_state") or {}
        slots = (record.get("talent") or {}).get("slots") or []
        live_talents = []
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            tid = _int(slot.get("talent_id"))
            if tid:
                live_talents.append({"id": tid, "unlocked": bool(slot.get("unlocked"))})
        realtime[npc_id] = {
            "layer_id": _int(cult.get("cultivate_layer_id"), -1),
            "talents": live_talents,
            # 本月激活的特殊互动入口（留影/切磋/说服…），0 表示本月没有。
            "special_sub": _int((record.get("npc_interaction_runtime") or {}).get("special_sub_id")),
        }

    rel = player.get("npc_relation") or {}
    master = _int(rel.get("master_npc_id"))
    disciples = _id_set(rel.get("disciple_npc_ids"))
    friends = _id_set(rel.get("friend_npc_ids"))
    enemies = _id_set(rel.get("enemy_npc_ids"))
    frozen = _id_set(rel.get("frozen_effect_npc_ids"))
    deceased = _id_set(rel.get("deceased_relations"))
    dao_ids = _id_set(rel.get("dao_companion_npc_ids"))
    dao_ids |= _id_set((player.get("npc_dao_ally") or {}).get("npc_ids"))
    single = _int(rel.get("dao_companion_npc_id"))
    if single:
        dao_ids.add(single)

    # 兼容：部分存档把好感放在交互属性里，键为 npcId
    interact = player.get("interact_attributes") or player.get("interactAttributes") \
        or (player.get("npcComponent") or {}).get("interactAttributes") or {}
    if isinstance(interact, dict):
        for key, value in interact.items():
            npc_id = _int(key)
            if not npc_id and isinstance(value, dict):
                npc_id = _int(value.get("npcId") or value.get("npcCfgId"))
            if not npc_id or not isinstance(value, dict):
                continue
            if npc_id not in favor and ("intimacy" in value or "favor" in value):
                favor[npc_id] = _int(value.get("intimacy", value.get("favor")), 0)

    # 住处：residents 为槽位 -> npcId
    housing = player.get("npc_housing") or {}
    residents = set()
    for value in (housing.get("residents") or {}).values() if isinstance(housing.get("residents"), dict) else ():
        nid = _int(value)
        if nid:
            residents.add(nid)
    housing_open = bool(housing.get("unlocked"))

    # 关系表：npcId -> {role_key: [关联 NPC 的 id]}
    rel_map = {}

    def put(nid, role, peers):
        if not nid:
            return
        rel_map.setdefault(nid, {}).setdefault(role, set()).update(peers)

    if master:
        put(master, "master", {0})        # 0 代表"你"
    for nid in disciples:
        put(nid, "disciple", {0})
    for nid in dao_ids:
        put(nid, "dao", dao_ids - {nid} or {0})
    for nid in friends:
        put(nid, "friend", friends - {nid})
    for nid in enemies:
        put(nid, "enemy", enemies - {nid})
    for nid in frozen:
        put(nid, "frozen", {0})
    for nid in deceased:
        put(nid, "deceased", deceased - {nid})

    # 有交情：有过好感、或存档关系表/仙居里出现过。存档里 1007 个 NPC 实例全有位置，
    # 但没打过交道的人不该在图鉴里被当成"认识"，所以不能拿 npcs 表本身当结识依据。
    met_ids = {nid for nid, value in favor.items() if value > 0}
    met_ids |= dao_ids | set(rel_map) | residents

    states = {}
    for npc_id in met_ids:
        value = _int(favor.get(npc_id), 0)
        is_dao = npc_id in dao_ids
        tier = _intimacy_tier(tiers, value) or {}
        raw_roles = rel_map.get(npc_id) or {}
        # 配置里新出现的关系类型不在已知表里时，仍要露出来（显示原始键名），
        # 避免游戏更新后新关系被静默吞掉。
        known_keys = {key for key, _ in REL_LABELS}
        extra_roles = [(key, key) for key in raw_roles if key not in known_keys]
        role_rows = list(REL_LABELS) + extra_roles
        roles = [label for key, label in role_rows if key in raw_roles]
        detail = {}
        for key, label in role_rows:
            peers = raw_roles.get(key)
            if not peers:
                continue
            names = []
            for pid in peers:
                if pid == 0:
                    names.append("你")
                elif pid in name_of:
                    names.append(name_of[pid])
            detail[label] = names or [str(pid) for pid in peers]
        live = locs.get(npc_id) or {}
        states[str(npc_id)] = {
            "favor": value,
            "met": True,
            "dao": is_dao,
            "tier": tier.get("name") or "",
            "tier_index": tiers.index(tier) if tier in tiers else -1,
            "roles": roles,
            "rel_detail": detail,
            "housed": npc_id in residents,
            "housing_open": housing_open,
            "loc": live.get("path") or "",
            "loc_name": live.get("name") or "",
            "region": live.get("region") or "",
            "gone": bool(live.get("gone")),
        }

    cult = player.get("npc_cultivation_history") or {}
    demo = player.get("demonic_cultivator") or {}
    player_state = {
        "evil": _int(player.get("player_prop_evil"), 0),
        "demon_qi": _int(demo.get("current_demonic_qi"), 0),
        "demonic": _int(demo.get("current_demonic_qi"), 0) > 0,
        "visited": len(player.get("visited_spaces") or []),
        "cult_hist": {
            "talent": bool(cult.get("ever_manually_unlocked_talent")),
            "pill": bool(cult.get("ever_used_breakthrough_pill")),
            "fruit": bool(cult.get("ever_used_wisdom_fruit")),
        },
        "counts": {
            "master": 1 if master else 0, "disciple": len(disciples),
            "dao": len(dao_ids), "friend": len(friends), "enemy": len(enemies),
            "frozen": len(frozen), "deceased": len(deceased), "housed": len(residents),
        },
        "names": {
            "master": name_of.get(master, str(master)) if master else "",
            "dao": [name_of.get(i, str(i)) for i in sorted(dao_ids)],
            "friend": [name_of.get(i, str(i)) for i in sorted(friends)],
            "enemy": [name_of.get(i, str(i)) for i in sorted(enemies)],
        },
    }

    stats = {
        "met": len(met_ids), "dao": len(dao_ids), "tracked": len(states),
        "housed": len(residents), "friend": len(friends), "enemy": len(enemies),
        # 在世：存档里有实例、能查到实时空间的人（不等于有交情）
        "present": len(set(locs) & set(name_of)),
        "absent": len(set(name_of) - set(locs)),
    }
    return {"states": states, "locs": locs, "realtime": realtime,
            "stats": stats, "player": player_state}


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
    locs = scanned.get("locs") or {}
    realtime = scanned.get("realtime") or {}
    layers = meta.get("layers") or {}
    talent_meta = meta.get("talents") or {}
    live_stats = scanned.get("stats") or {}
    player = scanned.get("player") or {}

    npcs = []
    avatar_map = {}
    used_avatars = set()
    evil_met = merchant_met = present_count = 0
    safe_present = safe_ready = 0
    for card in built.get("npcs") or []:
        npc = dict(card)
        npc_id = _int(npc.get("id"), 0)
        # 配置占位（匿名/负 id）玩家永远遇不到，页面层直接过滤
        if npc_id <= 0 or str(npc.get("name") or "").startswith("匿名"):
            continue
        live = states.get(str(npc_id)) or {}
        place = locs.get(npc_id) or {}
        # 存档里的实时境界与天赋优先：NPC 会自己修炼、解锁天赋，模板初值不一定是现状。
        rt = realtime.get(str(npc_id)) or realtime.get(npc_id) or {}
        layer_id = _int(rt.get("layer_id"), -1)
        layer_info = layers.get(str(layer_id)) if layer_id >= 0 else None
        if layer_info:
            npc["realm"] = layer_info.get("full") or npc.get("realm")
            npc["realm_short"] = layer_info.get("realm") or npc.get("realm_short")
            npc["realm_raw"] = layer_info.get("phase") or npc.get("realm_raw")
            npc["layer"] = layer_info.get("layer") or npc.get("layer")
            npc["layer_order"] = layer_info.get("order") or npc.get("layer_order")
            npc["realm_live"] = 1
        live_talents = rt.get("talents")
        if live_talents:
            merged = []
            for item in live_talents:
                if not isinstance(item, dict):
                    continue
                tid = _int(item.get("id"))
                info = talent_meta.get(str(tid)) or {}
                merged.append({"id": tid,
                               "name": info.get("name") or ("天赋 %s" % tid),
                               "unlocked": bool(item.get("unlocked"))})
            if merged:
                npc["talents"] = merged
        # 本月特殊互动入口：把 special_sub_id 映射成按钮名/状态标签。
        special_sub = _int(rt.get("special_sub"))
        entry_meta = (meta.get("special_entries") or {}).get(
            "%s|%s" % (npc_id, special_sub)) if special_sub else None
        npc["special_sub"] = special_sub
        npc["special_name"] = (entry_meta or {}).get("name") or ""
        npc["special_type"] = (entry_meta or {}).get("type") or 0
        npc["special_tag"] = (entry_meta or {}).get("tag") or ""
        npc["special_desc"] = (entry_meta or {}).get("desc") or ""
        favor = _int(live.get("favor"), 0)
        npc["favor"] = favor
        npc["met"] = bool(live.get("met"))          # 有交情（不是"在世"）
        npc["dao"] = bool(live.get("dao"))
        npc["roles"] = live.get("roles") or []
        npc["rel_detail"] = live.get("rel_detail") or {}
        npc["housed"] = bool(live.get("housed"))
        npc["housing_open"] = bool(live.get("housing_open"))
        # 位置按"存档里有实例"判定；没交情但有实时位置的也能定位
        npc["present"] = bool(place)
        npc["loc"] = place.get("path") or ""
        npc["loc_name"] = place.get("name") or ""
        npc["region"] = place.get("region") or ""
        npc["gone"] = bool(place.get("gone"))
        # 已退隐再细分：寿元已尽是明确的寿终；其余（境界突破/剧情清退等）
        # 存档没有记录来源，只标“已退隐”，不替游戏下结论。
        if npc["gone"]:
            death_text = str(npc.get("death") or "")
            remaining = npc.get("remaining_years")
            natural = ("寿元" in death_text) or (remaining is not None and _int(remaining) <= 0)
            npc["gone_reason"] = "dead" if natural else "retired"
        elif not npc["present"]:
            npc["gone_reason"] = "absent"
        else:
            npc["gone_reason"] = ""
        # 安全击杀目标：杀他不掉善恶、不扣声望；safe_now 才是"现在就能去杀"的
        npc["safe_now"] = bool(npc.get("safe_target")) and npc["present"] and not npc["gone"]
        tier = _intimacy_tier(tiers, favor) or {}
        npc["intimacy_name"] = live.get("tier") or tier.get("name") or ""
        idx = live.get("tier_index", -1)
        if (idx is None or idx < 0) and tier in tiers:
            idx = tiers.index(tier)
        npc["intimacy_index"] = idx
        if npc["present"]:
            present_count += 1
        if npc.get("safe_target"):
            # 在世口径与"在世"一致（present）；safe_now 再多排除已退隐
            if npc["present"]:
                safe_present += 1
            if npc["safe_now"]:
                safe_ready += 1
        if npc["met"]:
            evil_met += 1 if _int(npc.get("evil"), 0) < 0 else 0
            merchant_met += 1 if npc.get("merchant") else 0
        ref = _avatar_ref(npc["id"])
        if ref:
            avatar_map[str(npc["id"])] = ref
            used_avatars.add(ref)
        npcs.append(npc)

    live_stats = dict(live_stats)
    live_stats["present"] = present_count
    live_stats["absent"] = len(npcs) - present_count
    live_stats["evil_met"] = evil_met
    live_stats["merchant_met"] = merchant_met
    # 安全击杀：safe_target 是图鉴口径（恶名 + 可击杀，185）；
    # safe_target_present 是与"在世"一致的可定位人数，safe_target_ready 再排除已退隐
    safe_total = sum(1 for card in npcs if card.get("safe_target"))
    live_stats["safe_target"] = safe_total
    live_stats["safe_target_present"] = safe_present
    live_stats["safe_target_ready"] = safe_ready
    live_stats["safe_target_absent"] = safe_total - safe_present
    live_stats["gone"] = sum(1 for card in npcs if card.get("gone"))
    live_stats["dead"] = sum(1 for card in npcs if card.get("gone_reason") == "dead")
    live_stats["retired"] = sum(1 for card in npcs if card.get("gone_reason") == "retired")
    live_stats["absent"] = sum(1 for card in npcs if card.get("gone_reason") == "absent")
    live_stats["special"] = sum(1 for card in npcs if card.get("special_name")
                                and card.get("present") and not card.get("gone"))

    module["npcs"] = npcs
    module["meta"] = meta
    module["stats"] = built.get("stats") or {}
    module["live_stats"] = live_stats
    module["player"] = player
    module["avatar_map"] = avatar_map
    # 同一个头像会被几十个 NPC 共用；只存一份，页面端按 avatar_map 的键回查。
    images, _icons = _load_avatars()
    module["avatars"] = {key: images.get(key, "") for key in used_avatars if images.get(key)}
    module["breakthroughs"] = built.get("breakthroughs") or []
    module["death_risk"] = built.get("death_risk") or []
    return module


def summary(module):
    stats = module.get("stats") or {}
    live = module.get("live_stats") or {}
    player = module.get("player") or {}
    counts = player.get("counts") or {}
    return ("人物图鉴：图鉴 %d 位，在世 %d 位，有交情 %d 位；师尊/弟子 %s/%s、道侣 %s、朋友 %s、入住 %s 位" % (
        stats.get("total", 0), live.get("present", 0), live.get("met", 0),
        counts.get("master", 0), counts.get("disciple", 0), counts.get("dao", 0),
        counts.get("friend", 0), counts.get("housed", 0)))
