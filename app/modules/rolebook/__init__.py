# -*- coding: utf-8 -*-
"""人物图鉴：以 NPC 为中心的全息档案（基础/境界/常驻地/性格/善恶/声望/魅力/悟性/亲密/资质/关系网）。

数据全部来自配置表，新增 NPC 或规则只需重跑快照，不改代码。
存档关系（师承/道侣/朋友/仇敌/冰封/已故/入住）与头像在 scan/enrich 阶段合并。
"""
from meta_update import SCHEMA as DATA_SCHEMA

from .build import build
from .scan import enrich, meta, post, prepare, scan, summary

# ORDER=95，避开 quest=70 / talent=20 / memoria=80 / hongchen=90
KEY, LABEL = "rolebook", "人物图鉴"
ORDER, SELECT, SCHEMA = 95, "latest", 2  # 模块自有缓存版本，改数据结构时只递增这里
SNAPSHOT = "rolebook_meta.json"
TABLES = frozenset({
    "tbnpcbasecfg",            # NPC 主表：基础字段、头像、性格/善恶/声望/魅力/悟性原始值、能力标记
    "tbnpcpersonality",        # 14 种性格：personName / personalityPrompt
    "tbnpcevildesc",           # 5 档善恶：min / evilName / evilPrompt / kill_player_evil_delta
    "tbnpcreputedesc",         # 5 档声望：min / reputeName / reputePrompt
    "tbnpccharmdesc",          # 6 档魅力：min / charmName / charmPrompt
    "tbnpcwisdomtitle",        # 悟性称号：min_wisdom / name
    "tbnpcintimacy",           # 8 档亲密：intimacyRequirement / intimacyName / intimacyPrompt
    "tbnpctalent",             # 天赋：资质槽固定天赋名
    "tbmemoriaentry",          # 留影条目：npc_id 关联
    "tbnpctopicchat",          # 可聊话题：npcId
    "tbnpcpersuadetopic",      # 说服话题：npcId
    "tbalignmentattackgain",   # 攻击 NPC 的善恶/声望奖惩
    "tbalignmenttitle",        # 玩家善恶称号
    "tbevilattackprobability", # 追杀概率阈值
    "tbcultivaterealm",        # 境界名与 phases（phase → realm）
    "tbcultivatephase",        # 期名（炼气初期/筑基中期…）+ 所属 realm
    "tbcultivatelayer",        # 层号（propLayerId → phase + 层内序号）
    "tbnpcbehaviorspacemapping", # NPC 行为空间 → 常驻地提示
    "tbspace",                 # 空间名（常驻地兜底）
    "tbsect",                  # 门派名（propSect）
    "tbnpcrace",               # 种族名（propRace）
    "tbelement",               # 五行名（element）
})


def builtin_ok(data):
    return (isinstance(data, dict) and isinstance(data.get("npcs"), list)
            and isinstance(data.get("meta"), dict))


def empty():
    return {"schema": DATA_SCHEMA, "npcs": [], "meta": {}, "stats": {"total": 0}}
