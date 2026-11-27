# -*- coding: utf-8 -*-
"""界面语言：自动判断 + 中英词条。

只翻译固定界面文案与稳定的游戏术语（境界、属性、物品类型等）；
物品名、NPC 名、任务名与描述来自游戏配置，保持原文，避免随版本更新失效。
"""
import locale

try:
    from .i18n_extra import EXTRA as _EXTRA
except Exception:  # pragma: no cover - 词表缺失时只用内置词条
    _EXTRA = {}

LANG_CHOICES = ("auto", "zh", "en")

_SHELL = {
    "zh": {
        "title": "不问凡尘 · 仙友助手",
        "heading": "不问凡尘 · 仙友助手",
        "sub": "只读分析解密副本，不修改游戏存档；筛选条件会保留在本机浏览器。",
        "tip": ("游戏里保存后，点页面上的「立即同步」就能马上刷新；平时插件每 10 秒自动同步一次，本页只在数据变化时重画。"
                '<details class="tip-more"><summary>数据来源说明</summary><div>'
                "配置优先读游戏当前配置；读不到时退回兼容缓存或内置快照。"
                "若存档结构、加密方式或引擎版本大改，仍需更新工具。</div></details>"),
        "notice_update": ('从 <b>v2.2</b> 起，进游戏后按 <b>F3</b> 即可呼出本页面；'
                          '或双击 仙友助手.exe 启用网页版。'
                          '老用户重新运行一次「一键安装.bat」即可更新。'),
        "notice_overlay": ('按顶部显示的快捷键收起或再次呼出（默认为 <b>F3</b>，'
                           '可在「功能设置.bat」里修改），<b>ESC</b> 快速隐藏，右上角可退出工具。'),
        "notice_web": ('使用期间请留着那个黑色小窗口（可以最小化）——'
                       '<b>它负责自动检查数据，关掉后本页就不再自动刷新。</b>'
                       '右下角「立即同步」可马上导出最新存档。'),
        "notice_update_error": "<b>工坊更新未完成：</b>",
        "notice_restart": ('<b>插件已更新：</b>本次页面和查询数据已经是新版，可以继续使用；'
                           '插件侧改动会在退出游戏后自动替换，下次启动完全生效，无需重新订阅或重装。'),
    },
    "en": {
        "title": "WorldApart · Xianyou Helper",
        "heading": "WorldApart · Xianyou Helper",
        "sub": ("Read-only analysis of decrypted save copies. Your save is never modified; "
                "filters are kept in this browser."),
        "tip": ("After saving in game, click “Sync now” to refresh immediately; the plugin also syncs every 10 seconds. "
                "This page only redraws when data changes."
                '<details class="tip-more"><summary>Where the data comes from</summary><div>'
                "Config is read from the game first, then falls back to the compatible cache or the built-in snapshot. "
                "Major save/encryption/engine format changes still need a tool update.</div></details>"),
        "notice_update": ('Since <b>v2.2</b>, press <b>F3</b> in game to open this page; '
                          'you can also double-click 仙友助手.exe (Xianyou Helper.exe) to view it in a browser. '
                          'Existing users can re-run 「一键安装.bat」 (install.bat) to update.'),
        "notice_overlay": ('Press the hotkey shown at the top to hide or show (default <b>F3</b>, '
                           'changeable in 「功能设置.bat」 / Settings.bat). <b>ESC</b> hides instantly; exit from the top-right.'),
        "notice_web": ('Keep the small black console window running (you can minimize it) — '
                       '<b>it refreshes the data; closing it stops auto-refresh.</b> '
                       'Click "Sync now" at the bottom-right to export the latest save.'),
        "notice_update_error": "<b>Workshop update not completed:</b>",
        "notice_restart": ('<b>Plugin updated:</b> this page and its data are already the new version and remain usable. '
                           'Plugin-side changes swap in after you exit the game and take full effect on the next launch — '
                           'no need to resubscribe or reinstall.'),
    },
}

_PHASE = {
    "炼气": "Qi Refining", "筑基": "Foundation", "结丹": "Golden Core",
    "元婴": "Nascent Soul", "化神": "Spirit Transformation",
}
_STAGE = {"初期": "Early", "中期": "Middle", "后期": "Late"}

_ATTR = {
    "生命": "HP", "攻击": "Attack", "防御": "Defense", "生命上限": "Max HP",
    "生命百分比": "HP %", "攻击百分比": "Attack %", "防御百分比": "Defense %",
    "速度": "Speed", "灵力上限": "Max Spirit", "韧性值": "Tenacity",
    "韧性上限": "Max Tenacity", "灵力": "Spirit", "共鸣值": "Resonance",
    "共鸣值上限": "Max Resonance", "护盾": "Shield", "伤害加成": "Damage bonus",
    "伤害减免": "Damage reduction", "生命偷取效率": "Lifesteal", "治疗效率": "Healing",
    "暴击率": "Crit rate", "暴击伤害": "Crit damage", "抗暴": "Crit resist",
    "暴伤减免": "Crit damage reduction", "命中": "Accuracy", "闪避": "Evasion",
    "无视防御": "Defense ignore", "无视防御抵抗": "Ignore-defense resist",
    "精力": "Stamina", "精力上限": "Max stamina", "幸运": "Luck",
}

# 固定界面文案与稳定术语：中文原文 → 英文。缺失时自动显示中文原文。
EN = {
    # ---- 通用 ----
    "不问凡尘 · 仙友助手": "WorldApart · Xianyou Helper",
    "全部": "All", "当前": "Current", "当前位置": "Current location",
    "当前缺口": "Current gaps", "本境界": "This realm", "本境界辅材": "Realm auxiliaries",
    "有来源": "Has source", "无来源": "No source", "当前可拿": "Obtainable now",
    "展开全部": "Expand all", "收起全部": "Collapse all",
    "搜索": "Search", "筛选": "Filter", "显示": "Showing", "共": "Total",
    "件": "items", "条": "entries", "位": "characters", "个": "",
    "层": "layer", "年": "years", "天": "days", "次": "times",
    "已选": "Selected", "满配": "Max", "持有": "Owned", "未持有": "Not owned",
    "属性合计": "Total stats", "无": "None", "未知": "Unknown",
    "存档": "Save", "原始更新": "Original update", "配置": "Config",
    "来源": "Source", "用途": "Used for", "效果": "Effects", "获取途径": "Sources",
    "材料": "Materials", "材料图鉴": "Material codex", "境界路线图": "Realm roadmap",
    "规则说明": "Rules", "突破目标": "Breakthrough target",
    "接下来还要准备": "Also prepare", "后续突破": "Later breakthroughs",
    "阶段突破": "Stage breakthrough", "境界突破": "Realm breakthrough",
    "升层": "Layer up", "已到上限": "At cap", "还差": "Still need", "修为已满": "EXP full",
    "修为": "Cultivation", "积攒修为": "Stored EXP", "上次突破": "Last breakthrough",
    "护法": "Guardians", "连续失败": "Consecutive failures", "成功率": "Success rate",
    "突破耗时": "Breakthrough time", "期间不获得修为": "No EXP gained during this",
    "验证战斗": "Proving battle", "突破验证副本": "Breakthrough trial",
    "失败代价": "Failure penalty", "修为倒退 1 层": "Lose 1 layer of EXP",
    "连续失败会累计记录": "Failures are tracked",
    "突破方式": "Methods", "突破奖励": "Rewards", "提前准备": "Prepare early",
    "助道灵物": "Auxiliary materials",
    "最多选": "Pick up to",
    "件，成功率和属性只在本次突破生效": "items; bonuses apply to this breakthrough only",
    "件辅材": "aux items",
    "清": "Clear", "全": "All", "未学会": "Not learned", "已学会": "Learned",
    "丹方": "Recipe", "完成": "Complete", "未完成": "Incomplete",
    "未开始": "Not started", "未解锁": "Locked", "已跳过": "Skipped",
    "分支选了另一条路": "Chose another branch", "未触发": "Not triggered",
    "条件不足": "Requirements unmet", "未选分支": "Branch unchosen",
    "灵石": "Spirit Stones", "奖励": "Reward", "消耗": "Cost", "售价": "Price",
    "参考价": "Reference price", "品质": "Quality", "品阶": "Tier", "阶": "Tier",
    "在世": "Alive", "已离世": "Dead", "不在当前世界": "Not in this world",
    "有交情": "Acquainted", "道侣": "Dao companion", "朋友": "Friend",
    "入住": "Housed", "师尊": "Master", "弟子": "Disciple",
    "剧情线": "Storylines", "进行中": "In progress", "已完成": "Completed",
    "未接取": "Not accepted", "任务奖励": "Quest rewards", "支线任务": "Side quests",
    "种类": "types", "一次": "One-time", "重复": "Repeatable", "未拥有": "Unowned",
    "可优化": "to improve", "已装配": "Equipped", "未装配": "Not equipped",
    "已运转": "Active", "未运转": "Idle", "参透": "Comprehended",
    "待参透": "to comprehend", "配装": "Build", "硬伤": "critical issues",
    "背包": "Bag", "空着": "Empty", "替换": "replace", "已拾取": "Picked",
    # ---- 覆盖窗口顶栏 ----
    "仙友助手 · 覆盖模式": "Xianyou Helper · Overlay",
    "立即同步": "Sync now", "同步中…": "Syncing…", "收起": "Hide", "退出工具": "Exit",
    "小": "S", "中": "M", "大": "L", "缩小": "Zoom out", "放大": "Zoom in",
    "收起 / 呼出 · ESC 隐藏": "Hide / show · ESC hides",
    "已请求同步，几秒后刷新": "Sync requested; refreshing soon",
    "同步服务没响应：请确认黑色窗口仍在运行":
        "Sync service unavailable: keep the console window running",
    "已请求 · 插件上次导出": "Requested · last export",
    "已请求刷新": "Refresh requested", "存档目录未就绪": "Save folder not ready",
    "让插件立刻导出一次最新存档副本": "Ask the plugin to export the latest save now",
    # ---- 境界页长说明 ----
    "境界突破分三种：升层只看修为；阶段突破要修为满 + 1 件阶段材料；境界突破要修为满 + 4 件境界材料，还会进入验证战斗，失败会倒退 1 层修为。":
        "There are three kinds: layer-up needs EXP only; stage breakthrough needs full EXP + 1 stage material; "
        "realm breakthrough needs full EXP + 4 realm materials and a proving battle — failure loses 1 layer of EXP.",
    "材料来源标记：「官方」是游戏内标注的获取途径；「拍卖 / 赛事 / 镇劫 / 秘宝 / 商店 / 奇遇」是从掉落表反推出来的具体玩法；「缺来源」表示当前配置没有正常获取途径，可能尚未投放。":
        "Source marks: “Official” is the route shown in game; auction / tournament / world boss / treasure / shop / "
        "encounter are derived from drop tables; “No source” means the config has no normal route yet.",
    "成功率按配置推算（基础成功率 + 所选辅材加成），游戏内可能还有护法或其他修正；偷窃需要 NPC 恰好持有该物品。助道灵物的属性加成只在本次突破生效。":
        "Success rate is calculated from config (base + selected auxiliaries); the game may add guardian or other "
        "modifiers. Theft requires the NPC to carry the item. Auxiliary stat bonuses apply only to this breakthrough.",
    "「正在刷新」来自存档里各场景的妖兽状态；普通妖兽也会掉阶段材料，稀有妖兽掉的是助道材料。":
        "“Active” comes from monster states in each scene. Normal monsters also drop stage materials; rare ones drop auxiliary materials.",
    "当前阶段材料没有妖兽掉落，主要靠拍卖 / 赛事 / 任务 / 秘境等其他途径。":
        "No monsters drop the current stage materials; use auction / tournaments / quests / treasure instead.",
    "没有妖兽掉落的阶段材料：": "Stage materials with no monster drops: ",
    "寿元": "Lifespan", "敌人无敌": "Enemy invincible", "不可逃跑": "Cannot flee",
    "回合": "rounds", "人持有": "held by",
    "游戏当前配置": "Game config", "兼容缓存": "Compatible cache",
    "内置快照": "Built-in snapshot", "暂无": "None",
    # ---- 各模块常用标签 ----
    "未开": "Unopened", "已兑换": "Exchanged", "当前可见估价": "Visible estimate",
    "已装配": "Equipped", "天阶": "Heaven tier", "地阶": "Earth tier",
    "玄阶": "Mystic tier", "凡阶": "Mortal tier", "称号": "Title", "赏金": "Reward",
    "可跨档": "Cross-tier ready", "下一档": "Next tier", "难度": "Difficulty",
    "访谈": "Interview", "赠礼": "Gift", "拜托": "Request", "采集": "Gather",
    "采莲": "Gather", "交付": "Deliver", "前往": "Go to", "交谈": "Talk",
    "了解近况": "Learn the latest", "可接": "Available", "展开": "Show",
    "默默无闻": "Unknown", "名扬四海": "World-famous", "名震八荒": "Renowned",
    "技艺": "Craft", "天赋": "talents", "命中": "matched",
    "可同道": "companions allowed", "已同道": "joined",
    "输入 NPC 名称，与天赋条件叠加": "Enter an NPC name to combine with talent filters",
    "筛选只更高，不删除。未命中的内容变暗保留。":
        "Filters only narrow; nothing is deleted. Non-matching entries stay dimmed.",
    "货架": "Shelves", "远近闻名": "Locally known", "名震乡闾": "Renowned in town",
    "声名远扬": "Widely known", "誉满四方": "Famed everywhere", "全城": "City-wide",
    "战斗": "Combat", "游历": "Travel", "财富": "Wealth", "交情": "Rapport",
    "本门流派": "Sect schools", "同系": "Same-element", "完整体检": "Full checkup",
    "已学但没装槽": "learned but not equipped", "已学但没运转": "learned but idle",
    "已学未装": "learned, not equipped", "已学未运转": "learned, idle",
    "需要替换": "replace needed", "里没参悟": "not comprehended", "另有": "Also",
    "展开下方": "expand below", "已学": "Learned", "可优化": "improvements",
    # ---- 物品类型（配置里的分类名，缺失自动回退） ----
    "卜具": "Divination tool", "丹药": "Pill", "道蕴灵材": "Dao material",
    "道蕴信物": "Dao token", "法宝": "Artifact", "法物": "Ritual item",
    "护符": "Talisman", "货币": "Currency", "炼丹炉": "Furnace",
    "炼器材料": "Forging material", "灵根果": "Spirit root fruit", "璞石": "Rough stone",
    "日用": "Daily item", "文房": "Stationery",
    "阶段突破灵物": "Stage breakthrough material", "境界突破灵物": "Realm breakthrough material",
    "助道灵物分类": "Auxiliary material",
    # ---- 宗门 / 拍卖 ----
    "已接": "accepted", "还可接": "can accept", "差": "Missing", "再攒": "Save",
    "可换": "more for", "外务": "external", "贡献": "contribution", "场次": "Session",
    "成交": "Sold", "流拍": "unsold", "收益": "profit", "成功率": "Success rate",
    "挑衅": "Provoke", "虚张声势": "Bluff", "洞察他人": "Insight", "提价": "Raise bid",
    "出价": "Bid", "外门弟子": "Outer disciple", "内门弟子": "Inner disciple",
    "真传弟子": "True disciple", "长老": "Elder", "执事": "Steward",
    "要务": "duty", "重任": "great task", "宗门差遣": "Sect errands",
    "只看未拥有": "Only unowned", "最值": "Best",
    "消耗品": "Consumable", "修士养成材料": "Cultivation material", "妖丹": "Demon core",
    "药材": "Herb", "珍玩": "Curio", "专属信物": "Exclusive token",
    "突破助道灵物": "Breakthrough auxiliary material", "访友": "Visit friend",
    "结局": "Endings",
    "初到此地，尚未建立明显声望。": "New here; no notable reputation yet.",
    "在城镇中略有声名。": "Somewhat known around town.",
    "已被城镇居民熟知。": "Well known by the townsfolk.",
    "声名在一方乡闾中流传。": "Your name circulates across the region.",
    "美名传遍四海，各方皆闻其名。": "Your fame has spread far and wide.",
    "搜索材料名、用途或来源，例如：金火丹砂 / 拍卖 / 天宗论剑":
        "Search materials, uses or sources, e.g. 金火丹砂 / auction",
    "官方途径": "Official route", "反推途径": "Derived route", "官方": "Official",
    "NPC持有": "Held by NPC", "本期拍卖": "In auction", "当前缺": "Need",
    "暂无记录": "No record", "暂无正常获取途径": "No known source",
    "暂无可用的境界数据，请确认存档已导出。": "No cultivation data; make sure the save has been exported.",
    "存档：": "Save: ", "原始更新：": "Original update: ", "配置：": "Config: ",
    "｜": " | ",
    "最多选 5 件，成功率和属性只在本次突破生效": "Pick up to 5; bonuses apply to this breakthrough only",
    "优先带已持有、加成高的；缺的辅材可在下方材料图鉴筛「本境界辅材」查获取途径。":
        "Prefer owned, high-bonus items; filter the codex by Realm auxiliaries to find the rest.",
    "妖兽刷新": "Monster spawns", "当前地图": "Current map", "其他地图": "Other maps",
    "掉落": "Drops", "稀有": "Rare", "普通": "Normal",
    "当前地图没有相关刷新": "No related spawns here",
    "当前地图有刷新": "Spawns available here",
    "当前地图稀有妖兽": "Rare monsters on this map",
    "当前阶段材料 · 妖兽刷新": "Stage materials · spawns",
    "其他地图正在刷新": "Active on other maps",
    "本阶段突破要用": "Needed for this stage",
    "突破清单": "Breakthrough checklist",
    "只差修为": "EXP only", "修为 + 阶段材料": "EXP + stage material",
    "修为 + 材料 + 验证战斗": "EXP + materials + proving battle",
    "当前上限": "Current cap", "修为满 + 阶段材料": "Full EXP + stage material",
    "本境界突破（提前准备）": "This realm's breakthrough (early prep)",
    "阶段突破 / 本境界突破": "Stage / realm breakthroughs",
    "突破类型、来源标记与成功率": "Types, source marks and success rate",
    "点击境界卡片可只看该境界材料": "Click a realm card to filter its materials",
    "没有符合条件的材料": "No matching materials",
    "搜索材料名、用途或来源": "Search materials, uses or sources",
    # ---- 任务/状态 ----
    "可接取": "Available", "进行中": "In progress", "已完成": "Completed",
    "已提交": "Submitted", "已失败": "Failed", "已放弃": "Abandoned",
    "待提交": "Ready to submit", "未接取": "Not accepted", "状态": "State",
    "任务": "Quest", "主线": "Main", "支线": "Side", "红尘": "Romance",
    "隐藏": "Hidden", "委托": "Commission",
    # ---- 境界/阶段/类型 ----
    "炼气期": "Qi Refining", "筑基期": "Foundation", "结丹期": "Golden Core",
    "元婴期": "Nascent Soul", "化神期": "Spirit Transformation",
    "阶段灵物": "Stage material", "境界灵物": "Realm material", "助道灵物（物品）": "Auxiliary material",
    "突破材料": "Breakthrough material",
    # ---- 模块名 ----
    "人物图鉴": "Character Gallery", "境界修为": "Cultivation", "红尘（女主情缘）": "Romance",
    "奇遇": "Encounters", "支线": "Side Quests", "NPC天赋": "NPC Talents",
    "NPC物品": "NPC Items", "心法与功法": "Arts & Manuals", "炼丹": "Alchemy",
    "炼器": "Forging", "赌石": "Stone Gambling", "拍卖会": "Auction", "宗门": "Sect",
    "声望": "Reputation", "仙居楼互动": "Joy House", "留影石": "Memoria",
}

# 属性名与境界名：按名称匹配，游戏改 ID 也不影响；改名后自动回退中文。
EN.update(_ATTR)
_ELEM = {"金": "Metal", "木": "Wood", "水": "Water", "火": "Fire", "土": "Earth"}
for _realm, _realm_en in _PHASE.items():
    EN[_realm + "期"] = _realm_en
    for _stage, _stage_en in _STAGE.items():
        EN[_realm + _stage] = "%s · %s" % (_realm_en, _stage_en)
    for _elem, _elem_en in _ELEM.items():
        EN[_elem + " · " + _realm + "期"] = "%s · %s" % (_elem_en, _realm_en)


def normalize(value):
    value = str(value or "").strip().lower()
    return value if value in LANG_CHOICES else "auto"


def _system_lang():
    """系统语言：Windows 用 UI 语言 ID（中文 0x04），其它平台退回 locale。"""
    try:
        import ctypes
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "zh" if (int(langid) & 0x3FF) == 0x04 else "en"
    except Exception:
        pass
    try:
        name = locale.getdefaultlocale()[0] or ""
    except Exception:
        name = ""
    return "zh" if name.lower().startswith("zh") else "en"


def resolve(cfg, game_lang=""):
    """auto 时优先跟随游戏内语言，读不到再按系统语言。"""
    choice = normalize((cfg or {}).get("ui_lang"))
    if choice in ("zh", "en"):
        return choice
    if game_lang:
        return "en" if str(game_lang).lower().startswith("en") else "zh"
    return _system_lang()


def shell(lang, key):
    table = _SHELL.get(lang) or _SHELL["zh"]
    return table.get(key) or _SHELL["zh"].get(key, "")


def terms(lang):
    if lang != "en":
        return {}
    out = dict(_EXTRA)
    out.update(EN)
    return out
