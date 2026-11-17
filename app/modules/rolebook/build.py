# -*- coding: utf-8 -*-
"""人物志：配置表 → NPC 全息卡快照。

只从 meta_update 导入公共纯函数，不 import 任何其它模块。
档位说明等共享文本只放 meta（一份），NPC 卡只存档位 id，控制快照体积。
"""
from meta_update import SCHEMA, _int, _plain, _rows, _text

# 善恶值映射到中轴色带的取值范围（evil 越小越恶）
_EVIL_MIN, _EVIL_MAX = -500, 500

_SEX = {1: "男", 2: "女", 3: "其他", 0: "未知"}
_ELEMENT_KEYS = (1, 2, 3, 4, 5)


def _tier(rows, value, min_key, fallback_index=0):
    """档位匹配：取 min_key <= value 中 min 最大的档；没有则回退最低档。

    善恶表 min 为降序（-200/-99/0/200/500），其余为升序，本逻辑对两者通用。
    """
    hit = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _int(row.get(min_key)) <= value:
            if hit is None or _int(row.get(min_key)) > _int(hit.get(min_key)):
                hit = row
    if hit is None and rows:
        hit = rows[fallback_index] if isinstance(rows[fallback_index], dict) else None
    return hit or {}


def _name_map(rows, name_key):
    out = {}
    for row in _rows(rows):
        if isinstance(row, dict) and row.get("id") is not None:
            out[str(row["id"])] = _text(row.get(name_key)) or ("%s %s" % (name_key, row["id"]))
    return out


def _phases(realm_rows):
    """layer(phase) -> realm_id，境界名由 realms 提供。"""
    phases = {}
    for row in _rows(realm_rows):
        if isinstance(row, dict):
            realm_id = _int(row.get("id"))
            for phase in row.get("phases") or []:
                phases[str(_int(phase))] = realm_id
    return phases


def _realm_for_layer(phases, realms, layer):
    if layer in (None, ""):
        return realms.get("0", "凡人")
    best = None
    for raw, realm_id in phases.items():
        phase = _int(raw)
        if phase <= _int(layer) and (best is None or phase > best[0]):
            best = (phase, realm_id)
    if best is None:
        return realms.get("0", "凡人")
    return realms.get(str(best[1])) or ("境界 %s" % best[1])


def _first_text(value, limit=160):
    text = _plain(value)
    return text if len(text) <= limit else text[:limit] + "…"


def _greet(value, limit=120):
    """greetings 是本地化 dict 的列表；取第一条的中文文案。"""
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return _first_text(value[0], limit)
    return _first_text(value, limit)


def _avatar_stem(value):
    name = str(value or "").replace("\\", "/").rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if name else ""


def build(tables):
    npc_rows = _rows(tables.get("tbnpcbasecfg"))
    personas = {str(r["id"]): r for r in _rows(tables.get("tbnpcpersonality"))
                if isinstance(r, dict) and r.get("id") is not None}
    evil_tiers = [r for r in _rows(tables.get("tbnpcevildesc")) if isinstance(r, dict)]
    repute_tiers = [r for r in _rows(tables.get("tbnpcreputedesc")) if isinstance(r, dict)]
    charm_tiers = [r for r in _rows(tables.get("tbnpccharmdesc")) if isinstance(r, dict)]
    wisdom_tiers = [r for r in _rows(tables.get("tbnpcwisdomtitle")) if isinstance(r, dict)]
    intimacy_tiers = sorted(
        [r for r in _rows(tables.get("tbnpcintimacy")) if isinstance(r, dict)],
        key=lambda r: _int(r.get("intimacyRequirement")))
    attack_rules = sorted(
        [r for r in _rows(tables.get("tbalignmentattackgain")) if isinstance(r, dict)],
        key=lambda r: -_int(r.get("priority")))
    alignment_titles = sorted(
        [r for r in _rows(tables.get("tbalignmenttitle")) if isinstance(r, dict)],
        key=lambda r: _int(r.get("minAlignment")))
    chase_rules = sorted(
        [r for r in _rows(tables.get("tbevilattackprobability")) if isinstance(r, dict)],
        key=lambda r: _int(r.get("alignment_threshold")))

    realms = _name_map(tables.get("tbcultivaterealm"), "realm_name")
    realms.setdefault("0", "凡人")
    sects = _name_map(tables.get("tbsect"), "sectName")
    races = _name_map(tables.get("tbnpcrace"), "raceName")
    elements = _name_map(tables.get("tbelement"), "element_name")
    talents = {str(r["id"]): _text(r.get("name")) for r in _rows(tables.get("tbnpctalent"))
               if isinstance(r, dict) and r.get("id") is not None}
    phases = _phases(tables.get("tbcultivaterealm"))

    # 关联内容：按 npc_id / npcId 聚合，NPC 卡只存计数与前几个标题
    memoria = {}
    for row in _rows(tables.get("tbmemoriaentry")):
        if isinstance(row, dict) and row.get("npc_id") is not None:
            memoria.setdefault(str(row["npc_id"]), []).append(_text(row.get("title")))
    topics = {}
    for row in _rows(tables.get("tbnpctopicchat")):
        if isinstance(row, dict) and row.get("npcId") is not None:
            topics.setdefault(str(row["npcId"]), []).append(_text(row.get("topicName")))
    persuade = {}
    for row in _rows(tables.get("tbnpcpersuadetopic")):
        if isinstance(row, dict) and row.get("npcId") is not None:
            persuade.setdefault(str(row["npcId"]), []).append(_text(row.get("topic")))

    # ---- meta：共享档位 / 规则 / 名称表（说明完整，只存一份）----
    def tier_pack(rows, min_key, name_key, desc_key):
        out = []
        for index, row in enumerate(rows):
            pack = {
                "id": index,
                "min": _int(row.get(min_key)),
                "name": _text(row.get(name_key)),
                "desc": _text(row.get(desc_key)),
            }
            if "kill_player_evil_delta" in row:
                pack["kill_delta"] = _int(row.get("kill_player_evil_delta"))
            out.append(pack)
        return out

    meta = {
        "evil_tiers": tier_pack(evil_tiers, "min", "evilName", "evilPrompt"),
        "repute_tiers": tier_pack(repute_tiers, "min", "reputeName", "reputePrompt"),
        "charm_tiers": tier_pack(charm_tiers, "min", "charmName", "charmPrompt"),
        "wisdom_tiers": tier_pack(wisdom_tiers, "min_wisdom", "name", ""),
        "intimacy_tiers": [
            {"min": _int(r.get("intimacyRequirement")),
             "name": _text(r.get("intimacyName")),
             "desc": _text(r.get("intimacyPrompt"))} for r in intimacy_tiers],
        "personalities": {
            key: {"name": _text(r.get("personalityName")),
                  "tip": _text(r.get("personalityPrompt")),
                  "hover": _text(r.get("propHoverTip"))}
            for key, r in personas.items()},
        "attack_rules": [
            {"good": _int(r.get("playerGoodDelta")),
             "evil": _int(r.get("playerEvilDelta")),
             "city": _int(r.get("cityReputationDelta")),
             "sect": _int(r.get("sectReputationDelta")),
             "desc": _text(r.get("ruleDesc"))} for r in attack_rules],
        "alignment_titles": [
            {"min": _int(r.get("minAlignment")), "max": _int(r.get("maxAlignment")),
             "name": _text(r.get("titleName")), "desc": _text(r.get("titleDesc"))}
            for r in alignment_titles],
        "chase": [
            {"threshold": _int(r.get("alignment_threshold")),
             "prob": _int(r.get("chase_probability"))} for r in chase_rules],
        "realms": realms, "sects": sects, "races": races,
        "elements": elements, "talents": talents,
    }

    # tier_pack 用 enumerate 编号，匹配时也需按 enumerate 找 id
    def tier_id(rows, value, min_key):
        hit = _tier(rows, value, min_key)
        if not hit:
            return 0
        for index, row in enumerate(rows):
            if row is hit:
                return index
        return 0

    npcs = []
    stats = {"total": 0, "with_avatar": 0, "dao": 0, "killable": 0,
             "safe_target": 0, "evil_negative": 0, "evil_positive": 0,
             "merchant": 0, "with_memoria": 0, "with_topics": 0}
    for row in npc_rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        npc_id = _int(row.get("id"))
        name = _text(row.get("npcName")) or ("匿名 NPC %s" % npc_id)
        evil = _int(row.get("propEvil"))
        repute = _int(row.get("propRepute"))
        charm = _int(row.get("propCharm"))
        wisdom = _int(row.get("initial_wisdom"))
        sex = _SEX.get(_int(row.get("gender")), "未知")
        race = races.get(str(row.get("propRace"))) or "未知"
        sect_id = _int(row.get("propSect"))
        sect = sects.get(str(sect_id)) if sect_id else ""
        sect = sect or "无门无派"
        realm = _realm_for_layer(phases, realms, row.get("propLayerId"))
        element_names = [elements.get(str(e)) for e in (row.get("element") or [])
                         if str(e) in elements]

        pid = str(_int(row.get("propPersonality")))
        persona = personas.get(pid) or {}
        pLabel = _plain(row.get("PersonalityDesc")) or _text(persona.get("personalityName"))

        dao = bool(row.get("can_be_dao_companion"))
        spar = bool(row.get("can_spar"))
        kill_raw = _int(row.get("can_kill"))
        killable = kill_raw > 0
        steal = bool(row.get("can_steal"))
        merchant = bool(row.get("is_merchant"))
        safe_target = killable and evil < 0

        fixed_talents = []
        for slot in row.get("talent_slots") or []:
            if not isinstance(slot, dict):
                continue
            tid = _int(slot.get("fixed_talent_id"))
            if tid and talents.get(str(tid)):
                fixed_talents.append(talents[str(tid)])
        fixed_talents = list(dict.fromkeys(fixed_talents))

        mem_titles = memoria.get(str(npc_id)) or []
        topic_titles = topics.get(str(npc_id)) or []
        pers_titles = persuade.get(str(npc_id)) or []

        # 攻击此人：按 NPC alignment 区间匹配奖惩规则
        attack = {}
        for rule in attack_rules:
            if _int(rule.get("minNpcAlignment")) <= evil <= _int(rule.get("maxNpcAlignment")):
                attack = {
                    "good": _int(rule.get("playerGoodDelta")),
                    "evil": _int(rule.get("playerEvilDelta")),
                    "city": _int(rule.get("cityReputationDelta")),
                    "sect": _int(rule.get("sectReputationDelta")),
                    "desc": _text(rule.get("ruleDesc")),
                }
                break

        evil_pos = int(round((evil - _EVIL_MIN) / float(_EVIL_MAX - _EVIL_MIN) * 100))
        evil_pos = max(0, min(100, evil_pos))
        avatar = _avatar_stem(row.get("portraitIcon"))

        npcs.append({
            "id": npc_id, "name": name, "avatar": avatar,
            "sex": sex, "age": _int(row.get("age")),
            "race": race, "sect": sect, "realm": realm,
            "element": element_names,
            "personality_id": pid, "personality": pLabel,
            "evil": evil, "evil_tier": tier_id(evil_tiers, evil, "min"),
            "evil_pos": evil_pos,
            "repute": repute, "repute_tier": tier_id(repute_tiers, repute, "min"),
            "charm": charm, "charm_tier": tier_id(charm_tiers, charm, "min"),
            "wisdom": wisdom, "wisdom_tier": tier_id(wisdom_tiers, wisdom, "min_wisdom"),
            "dao": int(dao), "spar": int(spar), "kill": kill_raw,
            "steal": int(steal), "merchant": int(merchant), "killable": int(killable),
            "safe_target": int(safe_target),
            "slots": len(row.get("talent_slots") or []), "talents": fixed_talents,
            "memoria": len(mem_titles), "memoria_titles": mem_titles[:6],
            "topics": len(topic_titles), "topic_titles": topic_titles[:6],
            "persuade": len(pers_titles),
            "attack": attack,
            "greet": _greet(row.get("greetings")),
            "death": _first_text(row.get("death_narrative_text"), 80),
        })

        stats["total"] += 1
        stats["with_avatar"] += 1 if avatar else 0
        stats["dao"] += 1 if dao else 0
        stats["killable"] += 1 if killable else 0
        stats["safe_target"] += 1 if safe_target else 0
        stats["evil_negative"] += 1 if evil < 0 else 0
        stats["evil_positive"] += 1 if evil > 0 else 0
        stats["merchant"] += 1 if merchant else 0
        stats["with_memoria"] += 1 if mem_titles else 0
        stats["with_topics"] += 1 if topic_titles else 0

    npcs.sort(key=lambda item: item["id"])
    return {"schema": SCHEMA, "npcs": npcs, "meta": meta, "stats": stats}
