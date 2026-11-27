# -*- coding: utf-8 -*-
"""静态页面资源与输出：CSS、HTML 模板、版本哈希与原子写入。"""
import hashlib
import json
import os
import re
from html import escape as _html_escape

from . import common, i18n, registry

# ---------------------------------------------------------------- 品质色阶
# 档位以游戏代码为准，不能按页面展示反推：
#   Game/LubanDatas/ItemQuality.cs       白=0 绿=1 蓝=2 紫=3 黄=4 红=5（物品类）
#   .../GambleStone/GambleStoneQualityUtility.cs  白=1 绿=2 蓝=3 紫=4 橙=5（璞石）
# 两套编号基准不同，必须分开定义，否则璞石的白色会被当成绿色。
# 新增档位只在本表追加一行：CSS 变量、档位类和前端 clamp 都会自动跟着变，
# 各模块无需改动，也不会出现「新档位没有样式、静默继承成普通文字色」。
QUALITY_COLORS = (
    ("#cfd6df", "#1a1d22", "#2b3340"),  # 0 白
    ("#9fd6a9", "#18261c", "#31543c"),  # 1 绿
    ("#82baf5", "#172330", "#2f4e69"),  # 2 蓝
    ("#c7a1ef", "#221a2e", "#4a3566"),  # 3 紫
    ("#e8c76d", "#2b2415", "#65552a"),  # 4 黄
    ("#f0a6a6", "#2e1a1a", "#6b3232"),  # 5 红
)
GAMBLE_QUALITY_COLORS = (
    ("#8b93a1", "#1a1d22", "#2b3340"),  # 0 无
    ("#e6e6e6", "#3a3a3a", "#5c5c5c"),  # 1 白
    ("#9fe5bd", "#23402f", "#3a6b4f"),  # 2 绿
    ("#9ccdf5", "#1f3547", "#315a78"),  # 3 蓝
    ("#d9b5f5", "#3a2a47", "#5c4470"),  # 4 紫
    ("#f0c987", "#45351f", "#6d552f"),  # 5 橙
)

# 品质显示名：与游戏 tbstrconfig.ITEM_QUALITY_DICT 完全一致（0=凡品 … 5=圣品）。
# 游戏本身在越界时回退成数字（AuctionEntryTextUtil.ResolveItemQualityName 的 ISIL 可见），
# 这里保持同样行为：游戏将来新增档位而本表未更新时显示数字，而不是编一个错误的名字。
QUALITY_NAMES = ("凡品", "高品", "珍品", "绝品", "仙品", "圣品")


# 外壳层设计令牌：先与现有取值 1:1 对应（视觉零变化），
# 后续收敛取值、再做深浅主题时只需要覆盖这里，页面和模块都不用动。
SHELL_TOKENS = r"""
:root{
color-scheme:dark;
/* 表面 */
--bg:#0e1014;
--surface:#171a21;
--surface-alt:#15181f;
--surface-sunken:#141920;
--surface-raised:#242a34;
--surface-soft:#171d27;
--surface-track:#232833;
--surface-track-strong:#29303c;
--input-bg:#10141a;
--btn-bg:#1b222c;
--btn-border:#35404f;
--btn-hover:#25303d;
--btn-border-hover:#526175;
/* 描边 */
--border:#232833;
--border-subtle:#2b3340;
--border-strong:#29303c;
--border-raised:#242a34;
/* 文字 */
--text:#e8eaed;
--text-soft:#c9d3e0;
--text-body:#b4bdca;
--text-dim:#9aa3b2;
--text-muted:#8b93a1;
--text-faint:#778292;
/* 强调 */
--accent:#3d735b;
--accent-bg:#263b34;
--accent-fg:#c9f5dd;
/* 语义 */
--ok:#3ddc84;
--ok-fill:#2f7d54;
--ok-border:#2f5b47;
--ok-text:#8ee6b3;
--ok-bg:#16261d;
--gold:#e0c37a;
--gold-bg:#241f16;
--gold-border:#4a3d27;
--purple:#c4b5f0;
--purple-bg:#1e1a29;
--purple-border:#3c3550;
--danger-bg:#3a2126;
--danger-bg-soft:#1f1616;
--danger-border:#5c3535;
--danger-text:#f0b6b0;
--warn-text:#e0a6a0;
--info-bg:#18202b;
--info-border:#3a4658;
--info-text:#a9b7c8;
/* 强调色的强弱档：模块里反复出现的金色高亮、成功、危险、信息、正文强调都从这里取 */
--gold-strong:#e8c76d;
--gold-soft:#f0d38a;
--gold-warm:#ffc987;
--gold-line:#5a4c2a;
--ok-strong:#8fd0a9;
--ok-solid:#2f9e6b;
--ok-pale:#bfe8d3;
--danger-strong:#e88b82;
--danger-line:#6b3a44;
--info-strong:#a9dbe8;
--info-line:#2e455c;
--ink-strong:#d6dee8;
--ink:#9fb0c4;
}
"""


def _tier_rules(prefix, colors):
    """展开成「--{prefix}N 变量 + .{prefix}N 档位类」。

    档位类只负责声明 --tier-fg/-bg/-bd，具体用在哪由各模块自己的选择器决定。
    模块只消费变量、不重复声明颜色，所以新增档位不需要改任何模块。
    """
    variables, classes = [], []
    for index, (fg, bg, bd) in enumerate(colors):
        variables.append("--%s%d:%s;--%s%d-bg:%s;--%s%d-bd:%s"
                         % (prefix, index, fg, prefix, index, bg, prefix, index, bd))
        classes.append(".%s%d{--tier-fg:var(--%s%d);--tier-bg:var(--%s%d-bg);"
                       "--tier-bd:var(--%s%d-bd);color:var(--tier-fg)}"
                       % ((prefix, index) * 4))
    return variables, classes


def _quality_css():
    """品质色阶的 CSS 变量与档位类。"""
    item_vars, item_classes = _tier_rules("q", QUALITY_COLORS)
    stone_vars, stone_classes = _tier_rules("gq", GAMBLE_QUALITY_COLORS)
    # .fq / .f 是既有前缀，统一指向物品色阶，模块不必再各写一套颜色。
    alias = []
    for index in range(len(QUALITY_COLORS)):
        alias.append(".fq%d,.f%d{--tier-fg:var(--q%d);--tier-bg:var(--q%d-bg);"
                     "--tier-bd:var(--q%d-bd);color:var(--tier-fg)}"
                     % (index, index, index, index, index))
    return ":root{%s}\n%s\n%s" % (";".join(item_vars + stone_vars),
                                  "\n".join(item_classes + stone_classes),
                                  "\n".join(alias))


CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#2b3340;border:2px solid var(--bg);border-radius:6px}::-webkit-scrollbar-thumb:hover{background:#3a4657}::-webkit-scrollbar-corner{background:transparent}::selection{background:#2f5b45;color:#e8eaed}:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}body{background:var(--bg);color:var(--text);font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding:26px 20px 60px}.wrap{max-width:1180px;margin:0 auto}h1{font-size:23px;font-weight:600;letter-spacing:.5px}.sub{color:var(--text-faint);font-size:11px;line-height:1.7;margin-top:3px}.tabs{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:6px;margin:14px 0 14px}
@media(max-width:880px){.tabs{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(max-width:640px){.tabs{grid-template-columns:repeat(4,minmax(0,1fr))}}.tab{border:1px solid var(--border-strong);background:var(--surface);color:var(--text-dim);border-radius:8px;padding:7px 8px;cursor:pointer;font-size:13px;white-space:nowrap;text-align:center;transition:background .12s,color .12s,border-color .12s}.tab:hover{background:var(--btn-bg);color:var(--text-soft)}.tab.active{background:var(--accent-bg);border-color:var(--accent);color:var(--accent-fg)}.panel{display:none}.panel.active{display:block}.source{display:flex;flex-wrap:wrap;gap:1px 12px;color:var(--text-faint);font-size:11px;line-height:1.7;margin:0 0 12px}
.src-item{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.src-sep{color:var(--border-strong)}
.src-who{color:var(--text-muted)}
.src-warn{color:var(--gold)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:12px;margin:16px 0 22px}.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:13px 17px;min-width:0;transition:border-color .12s}
.card:hover{border-color:var(--border-subtle)}.card .k{color:var(--text-muted);font-size:12px}.card .v{font-size:20px;font-weight:600;margin-top:4px;font-variant-numeric:tabular-nums}.card .v span{font-size:12px;color:var(--text-muted);font-weight:400}table{width:100%;border-collapse:separate;border-spacing:0 4px}th{text-align:left;color:var(--text-faint);font-size:12px;font-weight:500;padding:0 12px;position:sticky;top:0;z-index:3;background:var(--bg);box-shadow:0 6px 8px -8px rgba(0,0,0,.75)}td{background:var(--surface-alt);padding:12px;vertical-align:middle;font-variant-numeric:tabular-nums;transition:background .12s}
tr.row:hover td{background:var(--surface-soft)}tr.row td:first-child{border-radius:12px 0 0 12px}tr.row td:last-child{border-radius:0 12px 12px 0}.who{font-size:15px;font-weight:600}.bed,.muted{color:var(--text-faint);font-size:12px;margin-top:3px}.parts{display:flex;gap:24px;flex-wrap:wrap}.part .pl{color:var(--text-dim);font-size:12px;margin-bottom:6px}.dots{display:flex;gap:4px}.dot{width:18px;height:18px;border-radius:6px;background:#252b36;display:flex;align-items:center;justify-content:center;font-size:10px;color:#5d6675}.dot.on{background:var(--ok-fill);color:var(--accent-fg)}.dot.miss{background:var(--danger-bg);color:var(--danger-text)}.bar{height:6px;border-radius:6px;background:var(--border);overflow:hidden;margin-top:8px}.bar i{display:block;height:100%;background:linear-gradient(90deg,#3ddc84,#2f9e6b)}.pct{font-variant-numeric:tabular-nums;font-weight:600;font-size:15px;text-align:right}.pct small{display:block;color:#7d8593;font-weight:400;font-size:11px;margin-top:2px}.full{color:var(--ok)}.badge{display:inline-block;margin-left:5px;padding:1px 6px;border-radius:6px;background:var(--surface-raised);color:var(--text-dim);font-size:11px;font-weight:400;vertical-align:middle}.badge.dao{background:#27374a;color:#b9d9ff}.filters{display:grid;grid-template-columns:2fr repeat(4,1fr);gap:9px;margin:14px 0}.filters input,.filters select{width:100%;background:var(--surface-alt);border:1px solid var(--border-strong);border-radius:8px;color:var(--text);padding:9px 10px;font-size:12px;outline:none}.filters input:focus,.filters select:focus{border-color:#527c69}.filters .wide{grid-column:span 2}.result-info{color:var(--text-muted);font-size:12px;margin:10px 2px 14px}.sec-title{display:flex;align-items:baseline;gap:8px;margin:18px 2px 9px;font-size:13px;font-weight:600;color:var(--text-soft);line-height:1.4}.sec-title small{color:var(--text-faint);font-size:11px;font-weight:400}.npc{background:var(--surface-alt);border:1px solid var(--border);border-radius:12px;margin:0 0 8px;overflow:hidden;transition:border-color .12s}
.npc:hover{border-color:var(--border-strong)}.npc summary{cursor:pointer;padding:12px 14px;list-style:none;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.npc summary::-webkit-details-marker{display:none}.npc summary:before{content:"›";color:var(--text-faint);font-size:20px;transform:rotate(0);transition:.15s}.npc[open] summary:before{transform:rotate(90deg)}.npc summary .location{margin-left:auto;color:var(--text-muted);font-size:12px}.slots{border-top:1px solid var(--border);padding:4px 14px 12px}.slot{padding:11px 0;border-bottom:1px solid var(--border)}.slot:last-child{border-bottom:0}.slot-head{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.talent-name{font-size:14px;font-weight:600}.lock{margin-left:auto;font-size:11px;color:#b98289}.lock.on{color:#6edda2}.effect{color:#b4bdca;font-size:12px;line-height:1.7;margin-top:6px}.condition{color:#7d8593;font-size:11px;line-height:1.7;margin-top:4px}.q1{color:#9fd6a9}.q2{color:#82baf5}.q3{color:#c7a1ef}.q4{color:#e8c76d}.q5{color:#e88b82}.empty{background:#171a21;border:1px dashed #303846;border-radius:12px;padding:28px;text-align:center;color:#8b93a1;font-size:13px}.warnings{margin:12px 0;color:#c9a976;font-size:12px;line-height:1.8}.tip{margin-top:22px;color:#6f7787;font-size:12px;line-height:1.9}.tip-more{margin-top:6px}.tip-more summary{cursor:pointer;color:#6f7787;font-size:11px;list-style:none}.tip-more summary::-webkit-details-marker{display:none}.tip-more summary:before{content:'›';display:inline-block;margin-right:6px;transition:.15s}.tip-more[open] summary:before{transform:rotate(90deg)}.tip-more div{margin-top:5px;color:#5f6773;font-size:11px;line-height:1.8}@media(max-width:850px){.filters{grid-template-columns:repeat(2,1fr)}.filters .wide{grid-column:span 2}.parts{gap:12px}.npc summary .location{margin-left:0;width:100%}}@media(max-width:560px){body{padding:18px 10px 40px}.filters{grid-template-columns:1fr}.filters .wide{grid-column:span 1}td{padding:9px 6px}.dot{width:15px;height:15px}.cards{gap:8px}.card{min-width:130px}}
"""
CSS += r"""
.talent-group{background:#15181f;border:1px solid #293140;border-radius:12px;margin:0 0 14px;overflow:hidden}.talent-head{padding:17px 18px}.talent-title{font-size:20px;font-weight:650;margin-right:7px}.talent-effect{color:#e0e6ed;background:#1b2029;border-left:3px solid #d4b45f;border-radius:4px;font-size:14px;line-height:1.85;margin-top:12px;padding:10px 12px}.talent-extra{color:#8f99a8;font-size:12px;line-height:1.7;margin-top:7px}.owners{border-top:1px solid #252c37;padding:9px 12px 12px}.owners-label{color:#8b93a1;font-size:11px;margin:3px 3px 8px}.owner{background:#11151b;margin-bottom:7px}.owner:last-child{margin-bottom:0}.owner summary{padding:11px 12px}.owner .slots{background:#15181f}.slot.focus{background:#1b2923;border-left:3px solid #55c78b;padding-left:10px}.slot.focus .talent-name{color:#8ee6b3}mark{background:#66551e;color:#fff0ae;border-radius:4px;padding:0 2px}.result-hint{color:#778292;font-size:11px;margin:-6px 2px 13px}@media(max-width:560px){.talent-head{padding:14px 12px}.talent-title{font-size:18px}.owners{padding:8px}.owner summary .location{width:auto;margin-left:auto}.owner .badge.hide-mobile{display:none}}
"""
CSS += r"""
.search-panel{background:#171b23;border:1px solid #293140;border-radius:12px;padding:15px;margin:16px 0 12px}.search-fields{display:grid;grid-template-columns:1fr 1fr;gap:14px}.search-field>span,.filter-field>span,.advanced-grid label>span{display:block;color:#aeb8c7;font-size:12px;margin:0 0 7px}.search-field:first-child>span{color:#d9c785}.search-field input,.filter-field select,.advanced-grid select{width:100%;background:#10141a;border:1px solid #303949;border-radius:8px;color:#e8eaed;padding:11px 12px;font-size:13px;outline:none}.search-field input:focus,.filter-field select:focus,.advanced-grid select:focus{border-color:#698c78;box-shadow:0 0 0 2px #263b34}.search-field input::placeholder{color:#667182}.filter-bar{display:grid;grid-template-columns:minmax(150px,1fr) minmax(190px,1.35fr) auto;align-items:end;gap:12px;margin:0 2px 14px}.filter-actions{display:flex;gap:8px}.filter-button{background:#1b222c;border:1px solid #35404f;border-radius:8px;color:#c6cfda;padding:10px 14px;min-height:40px;cursor:pointer;white-space:nowrap;font-size:12px}.filter-button:hover{background:#25303d;border-color:#526175}.filter-button.primary{color:#e2d7ac;border-color:#655d3d}.filter-count{color:#e8c76d}.advanced-filters{background:#141820;border:1px solid #293140;border-radius:12px;margin:0 0 14px;padding:0 13px}.advanced-filters summary{cursor:pointer;list-style:none;color:#9da8b7;font-size:12px;padding:11px 1px}.advanced-filters summary::-webkit-details-marker{display:none}.advanced-filters summary:before{content:"›";display:inline-block;margin-right:7px;transition:.15s}.advanced-filters[open] summary:before{transform:rotate(90deg)}.advanced-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;border-top:1px solid #252c37;padding:13px 0 15px}.owner summary .location{line-height:1.6;text-align:right}.category-badge{color:#d8c78f}.search-note{color:#758092;font-size:11px;margin:10px 2px 0}@media(max-width:850px){.filter-bar{grid-template-columns:1fr 1fr}.filter-actions{grid-column:span 2}.advanced-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.owner summary .location{text-align:left}}@media(max-width:560px){.search-panel{padding:12px}.search-fields,.filter-bar,.advanced-grid{grid-template-columns:1fr}.filter-actions{grid-column:span 1}.filter-button{flex:1}.owner summary .location{width:100%;text-align:left}}
"""
CSS += r"""
.item-group{background:#15181f;border:1px solid #293140;border-radius:12px;margin:0 0 14px;overflow:hidden}.item-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:11px 12px 0}.sortbtn{background:#1b222c;border:1px solid #35404f;border-radius:6px;color:#9aa3b2;padding:5px 11px;font-size:11px;cursor:pointer}.sortbtn:hover{background:#25303d}.sortbtn.on{background:#263b34;border-color:#3d735b;color:#c9f5dd}.item-tools .meta{margin-left:auto;color:#778292;font-size:11px}.ratebar{width:62px;height:5px;border-radius:6px;background:#232833;overflow:hidden;display:inline-block;vertical-align:middle;margin-left:6px}.ratebar i{display:block;height:100%;background:#4fbf83}.badge.deadly{background:#3a2126;color:#e88b82}.loadmore{display:block;width:calc(100% - 24px);margin:8px 12px 12px;background:#1b222c;border:1px dashed #35404f;border-radius:8px;color:#9aa3b2;padding:9px;font-size:12px;cursor:pointer}.loadmore:hover{background:#25303d;color:#c6cfda}.steal-detail{flex-basis:100%;color:#8b93a1;font-size:11px;line-height:1.7;margin-top:2px}.steal-detail b{color:#b4bdca;font-weight:600}.steal-detail .bad{color:#e88b82}.npc-card .slots{padding:0 14px 12px}.appver{display:inline-block;color:var(--text-muted);background:var(--surface);border:1px solid var(--border-strong);border-radius:999px;padding:2px 9px;font-size:11px;font-weight:500;vertical-align:middle;margin-left:6px;letter-spacing:0;font-variant-numeric:tabular-nums}.item-group>summary{list-style:none;cursor:pointer}.item-group>summary::-webkit-details-marker{display:none}.item-arrow{color:#6f7787;font-size:18px;transition:.15s;display:inline-block}.item-group[open] .item-arrow{transform:rotate(90deg)}.item-head{padding:16px 18px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.item-title{font-size:20px;font-weight:650}.item-stat{margin-left:auto;color:#8b93a1;font-size:12px}.owner .badge.steal{background:#22392e;color:#8ee6b3}.owner .badge.nosteal{background:#2a2d33;color:#8b93a1}.steal-ok{color:#6edda2;font-size:12px;font-weight:600}.steal-risk{color:#e88b82}.filter-bar.four{grid-template-columns:minmax(140px,1fr) minmax(165px,1.3fr) minmax(125px,1fr) auto}@media(max-width:850px){.filter-bar.four{grid-template-columns:1fr 1fr}.filter-bar.four .filter-actions{grid-column:span 2}}@media(max-width:560px){.filter-bar.four{grid-template-columns:1fr}.filter-bar.four .filter-actions{grid-column:span 1}.item-head{padding:13px 12px}.item-title{font-size:18px}.item-stat{margin-left:0;width:100%}}
.pill-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr);gap:16px;align-items:start}
.mapbox{position:relative;background:#12100e;border:1px solid #293140;border-radius:12px;overflow:hidden}
.mapbox canvas{display:block;width:100%;height:auto;image-rendering:pixelated}
.mapbox svg{position:absolute;inset:0;width:100%;height:100%}
.poi-dot{cursor:pointer;transition:opacity .15s}
.poi-dot.dim{opacity:.2}
.poi-dot.off{display:none}
#pillfog{display:none}
#pillherb{display:none}
.mapbox.showherb #pillherb{display:block}
.mapbox.showfog #pillfog{display:block}
.mapbox.showfog .poi-dot.unseen{opacity:0;pointer-events:none}
.pill-side{display:flex;flex-direction:column;gap:10px;min-width:0}
.chips{display:flex;gap:7px;flex-wrap:wrap}
.chip{background:#171b23;border:1px solid #2b3340;color:#9aa3b2;border-radius:20px;padding:6px 13px;font-size:12px;cursor:pointer;font-family:inherit}
.chip.on{background:#263b34;border-color:#3d735b;color:#c9f5dd}
.chip i{font-style:normal;color:#7d8593;margin-left:4px}
.chip-label{align-self:center;color:#6f7787;font-size:11px;letter-spacing:.5px}
.rec-info{display:grid;grid-template-columns:1fr 1fr;gap:3px 12px;margin-top:7px;padding-top:7px;border-top:1px solid #242c37}
.rec-info div{color:#c9d2df}
.rec-info span{color:#7d8593;margin-right:6px;font-size:11px}
.near{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:8px;padding-top:7px;border-top:1px solid #242c37;color:#7d8593;font-size:11px}
.route-item{background:#1d232c;border:1px solid #2b3340;color:#b9c6d6;border-radius:12px;padding:3px 9px;font-size:11px;cursor:pointer;font-family:inherit}
.route-item:hover{border-color:#3d735b;color:#c9f5dd}
.route{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:6px;color:#a8b3c1;font-size:11px}
.route>span{color:#7d8593;margin-right:2px}
.route-item i{font-style:normal;color:#6f7787;margin-left:5px}
.pill-search{width:100%;background:#10141a;border:1px solid #303949;border-radius:8px;color:#e8eaed;padding:10px 12px;font-size:13px;outline:none;font-family:inherit}
.pill-list{max-height:380px;overflow:auto;border:1px solid #232833;border-radius:12px;background:#141820}
.pill-item{display:flex;gap:8px;align-items:center;padding:9px 11px;border-bottom:1px solid #1e242d;cursor:pointer;font-size:12px}
.pill-item:hover{background:#1b222c}
.pill-item .dotmark{width:8px;height:8px;border-radius:50%;flex:none}
.pill-item .nm{flex:1;color:#d5dce6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pill-item .tp{color:#7d8593;font-size:11px}
.pill-item.done .nm{color:#6f7787;text-decoration:line-through}
.pill-detail{background:#15181f;border:1px solid #293140;border-radius:12px;padding:11px 13px;font-size:12px;line-height:1.8;color:#b4bdca;min-height:52px}
.pill-detail b{color:#e8eaed}
.legend{display:flex;gap:12px;flex-wrap:wrap;color:#8b93a1;font-size:11px}
.legend span{display:flex;align-items:center;gap:4px}
.legend i{width:8px;height:8px;border-radius:50%;display:inline-block}
@media(max-width:850px){.pill-grid{grid-template-columns:1fr}}
.manual{margin-top:14px;border:1px solid #232833;border-radius:12px;background:#141820;overflow:hidden}
.manual-head{display:flex;justify-content:space-between;align-items:baseline;padding:11px 13px;background:#171b23;color:#d5dce6;font-size:13px}
.manual-head span{color:#7d8593;font-size:11px;font-weight:400}
.manual-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px;padding:11px}
.manual-item{display:flex;gap:7px;align-items:center;flex-wrap:wrap;background:#181d25;border:1px solid #242c37;border-radius:8px;padding:9px 11px;font-size:12px;cursor:pointer}
.manual-item:hover{border-color:#3d735b}
.manual-item .nm{color:#dfe6ef;font-weight:600;margin-right:auto}
.manual-item .tag{color:#86909e;font-size:11px;background:#1d232c;border-radius:6px;padding:2px 6px}
.fsec{background:#141820;border:1px solid #232b36;border-radius:12px;padding:9px 11px 11px}
.fhead{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.fhead b{color:#cdd6e2;font-size:12px;font-weight:600}
.fhint{color:#6f7787;font-size:11px}
.fops{margin-left:auto;display:flex;gap:5px}
.fops button{background:#1b222c;border:1px solid #2b3340;color:#8b93a1;border-radius:6px;padding:2px 8px;font-size:11px;line-height:1.6;cursor:pointer;font-family:inherit}
.fops button:hover{color:#c9f5dd;border-color:#3d735b}
.frow{display:flex;align-items:flex-start;gap:8px;margin-top:9px}
.frow>.chip-label{min-width:26px;padding-top:6px}
.frow .chips{flex:1;min-width:0}
.frow .fops{margin-left:0;padding-top:4px}
.chip.zero{opacity:.4}
.chip.zero.on{opacity:.75}
#pillcond.off{opacity:.4;pointer-events:none}
.pill-active{display:flex;gap:6px;flex-wrap:wrap;align-items:center;min-height:22px}
.ptag-label{color:#6f7787;font-size:11px}
.ptag{background:#243430;border:1px solid #3a5f4f;color:#bfe8d3;border-radius:12px;padding:3px 9px;font-size:11px;cursor:pointer;font-family:inherit}
.ptag b{color:#7fa695;font-weight:400;margin-left:5px}
.ptag:hover{border-color:#5b8f76}
.ptag.clear{background:#1b222c;border-color:#35404f;color:#9aa3b2}
.pill-sum{color:#8b93a1;font-size:11px}
.pill-sum b{color:#e0e6ed;font-weight:600}
.pill-list{max-height:430px}
.pill-item .tp{max-width:56%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:none}
.pill-group{border-bottom:1px solid #1c222b}
.pill-group:last-child{border-bottom:0}
.pghead{position:sticky;top:0;z-index:1;display:flex;align-items:center;gap:7px;padding:7px 11px;background:#171d25;border-bottom:1px solid #1e242d}
.pgname{color:#c9d2df;font-size:11px;font-weight:600}
.pgcount{font-style:normal;color:#7d8593;font-size:11px}
.pgonly{margin-left:auto;background:#1b222c;border:1px solid #2b3340;color:#8b93a1;border-radius:12px;padding:2px 8px;font-size:11px;cursor:pointer;font-family:inherit}
.pgonly:hover{color:#c9f5dd;border-color:#3d735b}
.pgmore{display:block;width:100%;background:#161b22;border:0;border-top:1px dashed #2b3340;color:#86909e;padding:7px;font-size:11px;cursor:pointer;font-family:inherit}
.pgmore:hover{color:#c9f5dd}
.pill-item.focus{background:#1f2b25;box-shadow:inset 2px 0 0 #55c78b}
.empty-acts{display:flex;gap:7px;flex-wrap:wrap;justify-content:center;margin-top:10px}
.pill-act{background:#1b222c;border:1px solid #35404f;color:#b9c6d6;border-radius:12px;padding:4px 11px;font-size:11px;cursor:pointer;font-family:inherit}
.pill-act:hover{border-color:#3d735b;color:#c9f5dd}
#pillring{animation:pillring 1.6s ease-in-out infinite}
@keyframes pillring{0%,100%{stroke-opacity:1}50%{stroke-opacity:.3}}
.herb-track polyline{transition:stroke-opacity .15s}
.herb-track:hover polyline{stroke-opacity:.75}
.map-tip{position:absolute;left:0;top:0;z-index:4;pointer-events:none;background:#0f1319;border:1px solid #39424f;border-radius:6px;padding:3px 8px;font-size:12px;line-height:1.5;color:#e4e9f1;white-space:nowrap;transform:translate(-50%,-160%);opacity:0;transition:opacity .12s}
.map-tip.on{opacity:1}
@media(prefers-reduced-motion:reduce){#pillring{animation:none}}
"""
CSS += r"""
.forge-sec{margin:24px 0 9px;font-size:15px;font-weight:650;color:#d7dee8}
.forge-sec span{color:#7d8593;font-size:11px;font-weight:400;margin-left:8px}
.fproto,.fart{background:#15181f;border:1px solid #232833;border-radius:12px;margin:0 0 8px;overflow:hidden}
.fproto>summary,.fart>summary{list-style:none;cursor:pointer;padding:11px 13px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.fproto>summary::-webkit-details-marker,.fart>summary::-webkit-details-marker{display:none}
.fproto[open]>summary,.fart[open]>summary{border-bottom:1px solid #232833}
.fname{font-size:14px;font-weight:600;color:#e4eaf2}
.ftiers,.fstat{margin-left:auto;color:#9aa3b2;font-size:11px;font-variant-numeric:tabular-nums}
.fbody{padding:11px 13px 13px}
.fcols{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
.fcol{min-width:0}
.fcol-t{color:#7d8593;font-size:11px;margin-bottom:6px}
.fgrid{display:inline-grid;gap:3px}
.fcell{width:20px;height:20px;border-radius:4px;background:#20262f;display:block}
.fcell.block{background:#0c0e12;border:1px dashed #39424f}
.fline{color:#b4bdca;font-size:12px;line-height:1.9}
.fline b{color:#e8eaed;font-weight:600;margin-right:4px}
.fchips{display:inline-flex;gap:6px;flex-wrap:wrap;vertical-align:middle}
.fchip{background:#1a2029;border:1px solid #2b3340;border-radius:6px;padding:2px 8px;font-size:11px;color:#b4bdca}
.fgap{color:#e8a17c}.fok{color:#6edda2}.fmat{color:#b4bdca;font-size:12px;line-height:1.7}
@media(max-width:560px){.ftiers,.fstat{margin-left:0;width:100%}}
"""

CSS += r"""
.evgroup{display:flex;align-items:center;gap:8px;margin:20px 2px 9px;color:#cfd8e3;font-size:13px;font-weight:600}
.evgroup span{color:#778292;font-weight:400;font-size:11px}
.ev{background:#15181f;border:1px solid #232833;border-radius:12px;margin:0 0 8px;overflow:hidden}
.ev summary{cursor:pointer;padding:12px 14px;list-style:none;display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.ev summary::-webkit-details-marker{display:none}
.ev summary:before{content:"›";color:#6f7787;font-size:20px;transition:.15s}
.ev[open] summary:before{transform:rotate(90deg)}
.evname{font-size:15px;font-weight:600}
.evloc{margin-left:auto;color:#8b93a1;font-size:12px}
.evbody{border-top:1px solid #232833;padding:11px 14px 14px}
.evdesc{color:#b4bdca;font-size:12px;line-height:1.85}
.evline{color:#b4bdca;font-size:12px;line-height:1.9;margin-top:6px}
.evline b{color:#d9c785;margin-right:7px;font-weight:600}
.eend{background:#12161c;border:1px solid #212836;border-radius:8px;padding:10px 12px;margin-top:8px}
.eend.got{border-color:#3d735b;background:#131d18}
.eend-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.egrade{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:20px;border-radius:6px;font-size:11px;background:#242a34;color:#9aa3b2;padding:0 5px}
.egrade.g1{background:#22392e;color:#8ee6b3}.egrade.g2{background:#27374a;color:#b9d9ff}.egrade.g3{background:#3a2126;color:#e88b82}
.eend-title{font-size:13px;font-weight:600}
.eend-sum{color:#9aa3b2;font-size:12px;line-height:1.75;margin-top:5px}
.eend-detail{color:#c9a976;font-size:11px;line-height:1.7;margin-top:4px}
.erewards{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px}
.erewards>b,.epath>b{flex:none;display:inline-flex;align-items:center;height:22px;padding:0 8px;border-radius:6px;background:#2b2415;border:1px solid #4a3f24;color:#e8c76d;font-size:11px;font-weight:600}
.efchips{flex:1;min-width:0;display:flex;gap:6px;flex-wrap:wrap}
.epath{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:#9aa3b2;font-size:11px;line-height:1.7;margin-top:8px;background:#101720;border:1px solid #1f2b3a;border-radius:6px;padding:6px 8px}
.ereq{display:flex;align-items:center;gap:6px;flex-wrap:wrap;color:#9aa3b2;font-size:11px;line-height:1.7;margin-top:7px;background:#101720;border:1px solid #2b3340;border-radius:6px;padding:5px 8px}
.psteps{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.parrow{color:#6f9ec9;font-size:13px;font-weight:700}
.pstep{display:inline-flex;align-items:center;gap:5px;color:#d5dee8;background:#18222d;border-radius:6px;padding:2px 7px 2px 3px}
.pstep i{font-style:normal;display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;border-radius:50%;background:#2d4a63;color:#cfe8ff;font-size:10px}
.efchips{display:flex;gap:6px;flex-wrap:wrap}
.efchip{display:inline-flex;align-items:center;height:22px;box-sizing:border-box;background:var(--tier-bg,#1a2029);border:1px solid var(--tier-bd,#2b3340);border-radius:6px;padding:0 8px;font-size:11px;color:var(--tier-fg,#b4bdca)}
.efchip i{font-style:normal;color:var(--text-faint);margin-left:5px}
.efchip .q{font-size:10px;color:var(--text-faint);margin-left:4px}
.efchip.got{border-color:var(--accent);background:var(--ok-bg)}
.badge.ok{background:#22392e;color:#8ee6b3}.badge.off{background:#2a2d33;color:#8b93a1}.badge.warn{background:#3a3226;color:#e8c76d}
.badge.loc-exact{background:#22392e;color:#8ee6b3}.badge.loc-inferred{background:#333026;color:#e8c76d}.badge.loc-unknown{background:#2a2d33;color:#8b93a1}
.event-chips{margin:0 0 10px}
@media(max-width:560px){.evloc{margin-left:0;width:100%}.evbody{padding:10px 12px 12px}}
.charline{background:#141820;border:1px solid #232b36;border-radius:12px;padding:9px 13px;color:#b4bdca;font-size:12px;line-height:1.8;margin:0 0 12px}
.charline b{color:#e8eaed}
.notice{background:#16202b;border:1px solid #2d4356;border-radius:8px;color:#a9c4d8;font-size:12px;line-height:1.8;padding:8px 11px;margin:0 0 10px}
.notice b{color:#d7e9f7}
.notice-tip{position:relative;padding-right:34px}
.notice-x{position:absolute;top:6px;right:8px;background:none;border:0;color:#7f96a8;font:14px/1 "Microsoft YaHei",system-ui,sans-serif;cursor:pointer;padding:2px 5px;border-radius:4px}
.notice-x:hover{color:#cfe3f2;background:#1d2b38}
.notice-hidden{display:none}
.webbar{display:inline-flex;align-items:center;gap:6px;margin-left:10px;vertical-align:middle;
 font:12px/1.4 "Microsoft YaHei",system-ui,sans-serif}
.webbar[hidden]{display:none!important}
.webbar button{background:#1c2a24;border:1px solid #36604c;color:#bfe9d2;border-radius:6px;
 padding:3px 10px;font-size:12px;cursor:pointer;font-family:inherit;vertical-align:middle}
.webbar button:hover{background:#243a30}
.webbar button:disabled{opacity:.7;cursor:default}
.webbar span{color:#8b93a1;font-size:11px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle}
#xy-refresh{position:fixed;left:0;right:0;top:0;z-index:9999;display:none;align-items:center;justify-content:center;gap:9px;padding:10px 16px;background:rgba(18,23,31,.97);border-bottom:1px solid #2d4356;color:#d7e9f7;font-size:12px;box-shadow:0 6px 18px rgba(0,0,0,.45)}
#xy-refresh.on{display:flex}
#xy-refresh .spin{width:13px;height:13px;box-sizing:border-box;border:2px solid #3d735b;border-top-color:#8ee6b3;border-radius:50%;animation:xyspin .8s linear infinite;flex:none}
#xy-refresh .bar{position:absolute;left:0;right:0;bottom:-1px;height:2px;overflow:hidden}
#xy-refresh .bar:before{content:"";display:block;width:35%;height:100%;background:linear-gradient(90deg,transparent,#6edda2,transparent);animation:xybar 1s linear infinite}
@keyframes xyspin{to{transform:rotate(360deg)}}
@keyframes xybar{0%{transform:translateX(-100%)}100%{transform:translateX(390%)}}
.card .s{color:#778292;font-size:11px;margin-top:3px}
.small{font-size:11px}
.badge.score{background:#2c2a1f;color:#e8c76d}
.reasons{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 8px}
.reason{background:#1d232c;border:1px solid #2b3340;border-radius:6px;padding:2px 8px;font-size:11px;color:#c9d2df}
.reason.use{background:#17242c;border-color:#2d4f5f;color:#a9dbe8}
.itemdesc{color:#9aa3b2;font-size:12px;line-height:1.8;margin:2px 0 8px;background:#10141a;border-radius:6px;padding:7px 9px}
.itemdesc b{color:#c9d2df;font-weight:600}
.itemselect{background:#15181f;border:1px solid #29303c;border-radius:8px;color:#e8eaed;padding:5px 9px;font-size:12px;outline:none;min-height:28px}
.itemselect:focus{border-color:#527c69}
.cchip{display:inline-flex;align-items:center;gap:4px;border-radius:6px;padding:2px 7px;font-size:11px;background:#242a34;color:#9aa3b2;border:1px solid #2b3340;line-height:1.6}
.cchip.ok{background:#1a2a22;border-color:#3d735b;color:#8ee6b3}
.cchip.bad{background:#2e1d21;border-color:#6b3a44;color:#e88b82}
.condopts{display:flex;flex-direction:column;gap:5px;margin-top:5px}
.condopt{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.condname{color:#c9d2df;font-size:11px;background:#1b222c;border-radius:6px;padding:2px 7px;max-width:100%}
.effchip{display:inline-block;border-radius:6px;padding:2px 7px;font-size:11px;background:#1b2230;color:#9fc3e8;border:1px solid #2b3a4d}
.etree{margin-top:10px;border:1px solid #232833;border-radius:8px;background:#12161c;overflow:hidden}
.etree>summary{cursor:pointer;padding:9px 12px;color:#b9c6d6;font-size:12px;list-style:none}
.etree>summary::-webkit-details-marker{display:none}
.etree>summary:before{content:"›";display:inline-block;margin-right:6px;transition:.15s}
.etree[open]>summary:before{transform:rotate(90deg)}
.treewrap{padding:4px 12px 12px;border-top:1px solid #20252e}
.tnode{border-left:2px solid #2b3a33;padding:6px 0 2px 10px;margin-top:6px}
.ttext{color:#9aa3b2;font-size:11px;line-height:1.7;background:#0f1319;border-radius:6px;padding:5px 7px}
.topt{display:flex;align-items:center;gap:6px;flex-wrap:wrap;color:#d5dce6;font-size:12px;margin-top:6px;background:#151b23;border:1px solid #232c38;border-radius:6px;padding:5px 8px}
.topt b{color:#e8eaed;font-weight:600}
.tarrow{color:#6f9ec9;font-weight:700}
.topt.picked{border-color:#3d735b;background:#152019}
.topt.picked b{color:#8ee6b3}
.topt.picked b:before{content:"已选 ";color:#6edda2;font-size:10px}
.tbranch{margin-left:14px;border-left:1px dashed #2b3340;padding-left:8px}
.tbranch.alt{border-left-color:#4c5d74;margin-top:6px}
.talt-h{font-size:11px;color:#a9c4de;margin-bottom:3px}
.tend{color:#9aa3b2;font-size:12px;margin-top:6px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;background:#101720;border-radius:6px;padding:5px 8px}
.tend b{color:#e8eaed}
.tloop{color:#778292;font-size:11px;margin-top:5px}
.jumpbtn{background:#2d4a63;border:1px solid #4f7fa6;color:#d7efff;border-radius:6px;padding:4px 11px;font-size:11px;cursor:pointer;font-weight:600;white-space:nowrap}
.jumpbtn:hover{background:#3a5f7e;color:#fff}
.jumpbtn:after{content:" →"}
.ev.flash{animation:evflash 1.6s ease-out}
@keyframes evflash{0%{box-shadow:0 0 0 2px #4f7fa6;background:#1a2530}100%{box-shadow:0 0 0 0 transparent}}
.qgroup{display:flex;align-items:center;gap:8px;margin:20px 2px 9px;color:#cfd8e3;font-size:13px;font-weight:600}
.qgroup .gmeta{margin-left:auto;color:#778292;font-weight:400;font-size:11px}
.qline{color:#b4bdca;font-size:12px;line-height:1.9;margin-top:6px}
.qline b{color:#d9c785;margin-right:7px;font-weight:600}
.qchain{border:1px solid #232833;border-radius:12px;margin:10px 0;background:#12171f;overflow:hidden}
.qchain>summary{display:flex;align-items:center;gap:8px;padding:11px 14px;cursor:pointer;list-style:none}
.qchain>summary::-webkit-details-marker{display:none}
.qchain>summary:hover{background:#171d27}
.qchain[open]>summary{border-bottom:1px solid #232833}
.qchainbody{padding:10px 14px 14px}
.qstep{border-left:2px solid #2b3340;margin:7px 0 7px 6px;padding-left:12px}
.qstep>summary{display:flex;align-items:center;gap:8px;cursor:pointer;list-style:none;padding:4px 0}
.qstep>summary::-webkit-details-marker{display:none}
.qstep .stepno{width:20px;height:20px;line-height:20px;text-align:center;border-radius:50%;background:#232b37;color:#9fb0c4;font-size:11px;flex:none}
.qstep .evbody{padding:2px 0 6px 28px}
.qbranch{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:9px 0 9px 18px}
.qbranch.three{grid-template-columns:repeat(3,minmax(0,1fr))}
.qopt{border:1px solid #2a303c;border-radius:8px;background:#11161f;padding:9px 11px;min-width:0}
.qopt.chosen{border-color:#4d7a5f;background:#15211a}
.qopt.missed{opacity:.72}
.qopt .qname{font-weight:600;color:#e6edf5;font-size:13px}
.qopt .rw{font-size:11px;color:#b9c2cf;margin-top:5px;line-height:1.6}
.qopt .why{font-size:11px;color:#d3ae74;margin-top:5px;line-height:1.6}
.qopt .qoptmeta{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px}
.qchain>summary{flex-wrap:wrap}
.qsechd{display:flex;align-items:center;gap:8px;margin:16px 0 4px;font-size:11px;color:#93a0b1}
.qsechd:before{content:"";width:3px;height:11px;border-radius:4px;background:#3d735b;flex:none}
.qsechd i{margin-left:auto;font-style:normal;color:#6f7787}
.qwalk .qstep{border-left-color:#2f6b4c}
.qstep>summary{flex-wrap:wrap}
.qstep .qact{font-size:11px;color:#8fd0a9}
.rwline{display:flex;gap:5px;flex-wrap:wrap;align-items:center;margin-left:2px}
.rwstone{font-size:11px;color:#e8c76d}
.qitemdescs{margin:4px 0 8px;display:flex;flex-direction:column;gap:6px}
.qitemdesc{background:#10141a;border:1px solid #222a35;border-radius:6px;padding:6px 9px;font-size:12px;line-height:1.7;color:#9aa3b2}
.qitemdesc b{color:#c9d2df;font-weight:600;margin-right:6px}
.qitemdesc .qtype{font-size:10px;color:#7d8593;border:1px solid #2b3441;border-radius:4px;padding:0 4px;margin-right:6px;white-space:nowrap}
.qitemdesc .qnum{color:#e8c76d;margin-left:6px}
.mutedsm{font-size:11px;color:#6f7787}
.qnext{display:flex;align-items:center;gap:8px;flex-wrap:wrap;background:#16231c;border:1px solid #2f5b45;border-radius:8px;padding:8px 11px;margin:2px 0 6px;font-size:12px;color:#c9f5dd}
.qnext b{color:#8fd0a9;font-weight:600}
.qnext span{color:#8b93a1;font-size:11px}
.qfold{border:1px dashed #2b3441;border-radius:8px;margin:8px 0;background:#10151c}
.qfold>summary{display:flex;align-items:center;gap:8px;padding:9px 11px;cursor:pointer;list-style:none;font-size:12px;color:#9aa3b2}
.qfold>summary::-webkit-details-marker{display:none}
.qfold>summary:before{content:"›";color:#6f7787;font-size:16px;transition:.15s}
.qfold[open]>summary:before{transform:rotate(90deg)}
.qfold .qfoldn{color:#c3cbd7}
.qfold .qfoldx{margin-left:auto;color:#6f7787;font-size:11px;text-align:right}
.qfoldbody{padding:0 11px 8px}
.qopt .rwline{margin-top:6px}
.qfinal b{color:#d9c785;font-weight:600;margin-right:2px;font-size:11px}
@media(max-width:640px){.qbranch,.qbranch.three{grid-template-columns:1fr;margin-left:0}}
@media(max-width:560px){.topt{font-size:11px}.tbranch{margin-left:6px;padding-left:6px}.epath{flex-direction:column;gap:4px}}
"""

CSS += SHELL_TOKENS
CSS += r"""
/* 键盘可达性：只用键盘聚焦时显示轮廓，鼠标点击不出现框 */
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* 系统开启「减少动态效果」时，动画与过渡直接完成，避免眩晕与掉帧 */
@media (prefers-reduced-motion: reduce){
*,*:before,*:after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important}
}
"""
CSS += _quality_css()
HTML_TEMPLATE = r"""<!doctype html><html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title><style>__CSS__ __PLUGIN_CSS__ </style></head><body><div class="wrap"><h1>__HEADING__ <span class="appver">v__VER__</span><span id="webbar" class="webbar" hidden><button id="web-sync" type="button">立即同步</button><span id="web-tip"></span></span></h1><div class="sub">__SUB__</div>__CONSOLE_NOTE__<div id="warnings" class="warnings"></div><div id="tabs" class="tabs"></div>__PANELS__<div class="tip">__TIP__</div></div><script src="仙友助手版本.js"></script><script>
const INITIAL_VERSION=window.PROGRESS_VERSION||'';const DATA=__DATA__;
// 品质档位统一在这里钳制：超出当前色阶的编号落到最高档并保持可见，不会静默继承成普通文字色。
const QUALITY_MAX=__QUALITY_MAX__,GAMBLE_QUALITY_MAX=__GAMBLE_QUALITY_MAX__;
// 高品质展示阈值集中在这里：奇遇达到 3 档起标、支线 4 档起标，避免各模块各写一个魔法数字。
const HI_QUALITY=3,HI_QUALITY_STRICT=4;
function qTier(q,max){var cap=max==null?QUALITY_MAX:max,v=parseInt(q,10);if(!isFinite(v)||v<0)return 0;return v>cap?cap:v}
function qClass(q,prefix,max){return (prefix||'q')+qTier(q,max)}
// 品质名与游戏 ITEM_QUALITY_DICT 同源；越界时和游戏一样回退成数字。
const QUALITY_NAMES=__QUALITY_NAMES__;
function qName(q){var v=parseInt(q,10);if(!isFinite(v)||v<0)return '';return QUALITY_NAMES[v]||String(v)}
const LANG=DATA.lang||'zh',EN=DATA.i18n||{};
// 先匹配完整说法，再做通用词替换：避免「第 54 天」先被「天」拆成「第 54 days」。
const TR_FIRST=[
 [/每眼 (\d+) 修为 · 每次拖动 (\d+) 修为/g,'$1 EXP per spot · $2 per drag'],
 [/已走过 (\d+) 步/g,'$1 steps walked'],
 [/二选一 · 只能走一条[；;]?\s*/g,'Pick one of two · only one path; '],
 [/已选一条后[，,]?\s*另一条不再计入未完成/g,
  'After choosing one, the other no longer counts as incomplete'],
 [/这些是当时/g,'These are branches from when you '],
 [/不会再出现/g,'will not appear again'],[/也不算漏做/g,'not counted as missed'],
 [/无接取门槛/g,'No acceptance requirement'],
 [/任务按真实前置关系分组[：:]?/g,'Quests are grouped by real prerequisites: '],
 [/点故事线标题展开或收起/g,'Click a storyline title to expand or collapse'],
 [/有进度的线会默认展开/g,'lines with progress start expanded'],
 [/累计选 (\d+) 次/g,'picked $1 times'],
 [/是存档里的点击次数/g,'is the click count in the save'],
 [/不是奖励倍数/g,'not a reward multiplier'],
 [/表示该物品可被 NPC 收购或用于 NPC 需求任务/g,
  'means an NPC buys it or needs it for a request'],
 [/表示可作对应配方材料/g,'means it can be used as a recipe material'],
 [/游戏内置固定地图/g,'a fixed in-game map'],[/并非随机生成/g,'not randomly generated'],
 [/表示本存档已拾取过/g,'means already picked in this save'],
 [/落在迷雾里的拾取点会一起隐藏/g,'pickups in fog are hidden too'],
 [/打开后显示/g,'shows when enabled'],[/定位盘面/g,'locate on board'],
 [/好感度/g,'affinity'],[/已学会/g,'Learned'],[/已拾取过/g,'already picked'],
 [/已探索区域/g,'explored areas'],[/默认关闭/g,'off by default'],
 [/鼠标停在/g,'hover over'],[/暂无称号/g,'No title'],
 [/未开始/g,'Not started'],[/已完成/g,'Completed'],[/持有/g,'Owned'],
 [/已走完/g,'Complete'],[/下一档/g,'Next tier'],[/未开放/g,'Not open'],
 [/可达/g,'Reachable'],[/宗门要务/g,'Sect priority'],[/宗门重任/g,'Sect duty'],
 [/要务/g,'priority'],[/重任/g,'duty'],[/全清/g,'Clear all'],
 [/坐标/g,'Coords'],[/盘面/g,'board'],[/删除线/g,'strikethrough'],
 [/药材路线/g,'herb routes'],[/迷雾/g,'Fog'],[/留影/g,'Memoria'],
 [/腋下/g,'Armpit'],
 [/紫(?=[:：\s\d])/g,'Purple'],[/橙(?=[:：\s\d])/g,'Orange'],
 [/蓝(?=[:：\s\d])/g,'Blue'],[/绿(?=[:：\s\d])/g,'Green'],[/红(?=[:：\s\d])/g,'Red'],
 [/红尘任务线/g,'Romance questline'],[/特殊/g,'Special'],
 [/(\d+)年(\d+)月(\d+)日/g,'Year $1 · Month $2 · Day $3'],
 [/已提交过主线「?([^」]+)」?/g,'Completed main story “$1”'],
 [/已提交过/g,'Completed '],
 [/前置任务\s*进行中/g,'Prerequisite quest in progress'],
 [/前置任务\s*已提交/g,'Prerequisite quest submitted'],
 [/完成([^，。;；]{1,24}?)后自动触发/g,'Auto-triggers after completing $1'],
 [/蓝色原胚/g,'blue blanks'],[/紫色原胚/g,'purple blanks'],[/橙色原胚/g,'orange blanks'],
 [/炼气支线/g,'Qi Refining side quests'],[/筑基支线/g,'Foundation side quests'],
 [/结丹支线/g,'Golden Core side quests'],[/元婴支线/g,'Nascent Soul side quests'],
 [/化神支线/g,'Spirit Transformation side quests'],[/隐藏支线/g,'Hidden side quests'],
 [/主线/g,'main story'],[/支线/g,'side quests'],
 [/赛事排名/g,'Tournament rank'],[/暂未实装/g,'not implemented yet'],
 [/等级/g,' Lv '],[/原胚/g,' blanks'],[/门户/g,'portal'],[/渡口/g,'crossing'],
 [/进入指定地点后触发/g,'Triggers after entering the specified location'],
 [/后自动出现/g,' then appears automatically'],[/后出现/g,' then appears'],
 [/后自动触发/g,' then auto-triggers'],[/后触发/g,' then triggers'],
 [/未在进行/g,'not in progress'],[/未完成/g,'not completed'],
 [/好感/g,'affinity'],[/声望/g,'reputation'],[/达到/g,'reaches'],
 [/已走完/g,'Complete'],[/旧版内容/g,'Legacy content'],
 [/已被同名新版本替代/g,'replaced by a newer same-name version'],
 [/版本里没有接取入口/g,'has no acceptance entry in this version'],
 [/配方/g,'Recipe'],[/造成/g,'Deals'],[/土系伤害/g,'Earth damage'],
 [/目标破韧时/g,'when the target breaks tenacity'],
 [/的(?=[A-Za-z])/g,"'s "],[/先(?=(Complete|Finish|Reach|Talk|Accept|Go))/g,'First, '],
 [/当前版本无解锁入口/g,'No unlock entry in this version'],
 [/已废弃[（(]旧版任务[)）]/g,'Deprecated (legacy quest)'],
 [/已完成[（(]部分分支未选[)）]/g,'Completed (some branches unchosen)'],
 [/(\d+) years (\d+) 月 (\d+) 日/g,'Year $1 · Month $2 · Day $3'],
 [/第 (\d+) 时段/g,'period $1'],
 [/第 (\d+) 天/g,'Day $1'],
 [/第 (\d+) 月/g,'Month $1'],
 [/仅在 (\d+) 月/g,'Only in month $1'],
 [/满足条件后自动触发/g,'Auto-triggers when requirements are met'],
 [/完成「([^」]+)」后自动触发/g,'Auto-triggers after completing “$1”'],
 [/修炼到指定阶段后触发/g,'Triggers after reaching the specified cultivation phase'],
 [/满足条件后/g,'When requirements are met, '],
 [/前置任务/g,'Prerequisite quest'],
 [/奇遇进行中/g,'Encounter in progress'],
 [/接取条件满足/g,'Acceptance requirements met'],
 [/任务提交/g,'Quest submitted'],
 [/进入场景/g,'Enter scene'],
 [/修炼阶段达到/g,'Cultivation phase reached'],
 [/未选此分支/g,'Branch not chosen'],
 [/对话选项/g,'Dialogue option'],
 [/任务分支/g,'Quest branch'],
 [/暂未开放/g,'Not open yet'],
 [/未知的药效/g,'Unknown effect'],
 [/未知的丹方/g,'Unknown recipe'],
 [/高风险/g,'High risk'],
 [/选了另一条路[，,]?\s*这条不会再出现[，,]?\s*也不算漏做/g,'Chose another path; the route will not appear again and is not counted as missed'],
 [/选了另一条路/g,'Chose another path'],
 [/这条不会再出现/g,'this route will not appear again'],
 [/也不算漏做/g,'not counted as missed'],
 [/尚未完成「([^」]+)」/g,'Not yet completed: “$1”'],
 [/不满足[:：]\s*/g,'Not met: '],
 [/说明[:：]\s*/g,'Note: '],
 [/完成「([^」]+)」/g,'Complete “$1”'],
 [/与「([^」]+)」二选一/g,'Choose one of “$1”'],
 [/蓝色/g,'blue '],[/紫色/g,'purple '],[/橙色/g,'orange '],
 [/神识/g,'Divine Sense'],[/体魄/g,'Constitution'],[/辩道/g,'Debate'],
 [/灵机/g,'Spiritual Insight'],[/医术/g,'Medicine'],
 [/经验/g,' EXP'],
 [/双向/g,'two-way'],[/单向/g,'one-way'],
 [/稀有妖兽/g,'rare monsters'],
 [/非\(/g,'not ('],[/已接取/g,'accepted '],[/已提交/g,'submitted ']
];
const TR_LAST=[
 [/「/g,'“'],[/」/g,'”'],[/（/g,'('],[/）/g,')'],[/【/g,'['],[/】/g,']']
];
const TR_RULES=[
 // 组合句优先：先整句/整段匹配，再交给后面的通用词替换，避免留下半中半英。
 // 长段落可能是整块文本节点，这类规则不加首尾锚点，按句子逐段替换。
 [/修为达到「(.+?)」/g,'Reach “$1”'],
 [/修为达到/g,'Reach '],
 [/境界达到/g,'Reach realm '],
 [/你的修炼层数/g,'your cultivation layer'],
 [/开启：/g,'Unlock: '],
 [/整条线的开启条件/g,'unlock condition for the whole route'],
 [/无需前置（剧情自动出现）/g,'No prerequisite (appears automatically)'],
 [/与「(.+?)」对话接取/g,'Accept by talking to “$1”'],
 [/尚未开启 · 共 (\d+) 个节点/g,'Not started · $1 nodes'],
 [/条件[:：]\s*/g,'Condition: '],
 [/炼气期/g,'Qi Refining'],
 [/筑基期/g,'Foundation'],
 [/结丹期/g,'Golden Core'],
 [/元婴期/g,'Nascent Soul'],
 [/化神期/g,'Spirit Transformation'],
 [/好感度/g,'affinity'],
 [/容易误选/g,'easy to misclick'],
 [/来源不可用/g,'source unavailable'],
 [/分钟/g,'min'],
 [/当前/g,'current '],
 [/需要/g,'requires'],
 [/选项「/g,'Option 「'],
 [/ 且 /g,' and '],
 [/ 或 /g,' or '],
 [/且/g,' and '],
 [/或/g,' or '],
 [/，/g,', '],
 [/你的/g,'your '],
 [/你当前/g,'your current '],
 [/仍是凡人/g,'is still a mortal'],
 [/尚未开始修炼/g,'has not started cultivating'],
 [/正在进行/g,'in progress'],
 [/已提交过/g,'already submitted '],
 [/MainStory/g,'main story'],
 [/完成前置任务后自动触发/g,'Triggers automatically after the prerequisite quest'],
 [/前置任务 未接取/g,'prerequisite not accepted'],
 [/前置剧情还没走到/g,'The prerequisite story has not reached here yet'],
 [/当前版本无解锁入口/g,'No unlock entry in this version'],
 [/等待剧情触发（尚未结识或剧情未到）/g,'Waiting for the story (not met yet or story not reached)'],
 [/以实际选项为准）/g,'actual option prevails)'],
 [/仅 (\d+) 条结局产出/g,'only $1 ending rewards'],
 [/需 NPC 持有）/g,'requires NPC ownership)'],
 [/基础成功率 (\d+)/g,'Base success rate $1'],
 [/单价 (\d+)/g,'unit price $1'],
 [/还差: /g,'Still needed: '],
 [/合计/g,'Total'],
 [/选择记录里的“累计选 N 次”是存档里的点击次数，不是奖励倍数。/g,
  'In choice records, “picked N times” is the save’s click count, not a reward multiplier. '],
 [/「NPC 求购」表示该物品可被 NPC 收购或用于 NPC 需求任务；「炼丹药材 \/ 炼器材料」表示可作对应配方材料。/g,
  '“NPC demand” means an NPC buys it or needs it for a request; “alchemy herb / forging material” means it works as a recipe material.'],
 [/ 当前角色属性：/g,' Character stats: '],
 [/；灵石 ([\d,]+)。/g,'; Spirit Stones $1.'],
 [/ 结局的「达成路径」来自配置里的设计备注，共 (\d+)\/(\d+) 条；静态能连到结局的分支共 (\d+) 条，其余由游戏结算判定。/g,
  ' Ending “paths” come from design notes in the config: $1/$2 endings. $3 branches link to endings statically; the rest are decided by the game.'],
 [/ 奇遇按地点境界分组；配置里没有“角色境界高于某值就关闭奇遇”的硬条件，能否再遇到主要取决于还能不能回到该地点。/g,
  ' Encounters are grouped by location realm; the config has no “close low-realm encounters at high realm” rule, so re-encountering them depends on returning to that location.'],
 [/ 历史达成按角色保存在本地，不写入游戏存档。/g,
  ' Past achievements are stored locally per character and never written to the save.'],
 [/「剧情线」按委托人 \/ 章节把支线串成一条路：点剧情线展开脊柱，点任务看触发条件、选项门槛与奖励。隐藏任务用虚线框标出，触发方式直接写在任务名下面；同一处只能选一条的分支会并排显示，已选 \/ 未选一眼可辨。搜索框会直接定位并展开对应剧情线里的任务。折叠状态、筛选与搜索会记住。/g,
  '“Storylines” chain side quests by client and chapter: open a line to see its spine, click a quest for its trigger, option gates and rewards. Hidden quests use a dashed border and show their trigger right under the name; mutually exclusive branches are shown side by side so chosen and unchosen are obvious. Search jumps to and expands the matching quest. Collapse state, filters and search are remembered.'],
 [/找「(.+?)」接取/g,'Accept from “$1”'],
 [/游戏内选项提示：/g,'In-game option hint: '],
 [/「(.+?)」第 (\d+) 格还空着/g,'“$1” slot $2 is still empty'],
 [/「(.+?)」第 (\d+) 格空着/g,'“$1” slot $2 is empty'],
 [/槽位 (\d+) 空着/g,'Slot $1 is empty'],
 [/合计：/g,'Total: '],
 [/参悟 (\d+) 分钟/g,'$1 min of comprehending'],
 [/有 (\d+) 条配置未识别或缺失，已保留条目：/g,
  '$1 config entries unrecognized or missing; kept: '],
 [/共鸣条件从效果原文提取「携带 X 系心法」与【X…Y】相生标签，未识别的不计入统计。/g,
  'Resonance conditions are extracted from effect text (“carry an X core art” and 【X…Y】 generation tags); unrecognized ones are excluded from counts.'],
 [/有 (\d+) 本卷册没参悟（(.+?) (.+?)）/g,'$1 scrolls not comprehended ($2 $3)'],
 [/真意最高档需求 (\d+) (.+?)，是否达标请在游戏内确认（阈值机制待复核）/g,
  'Highest true-intent tier needs $1 $2; confirm in game (thresholds pending review)'],
 [/已学功法里没有(.+?)(.+?)的同门功法/g,'No same-sect technique learned for $1 · $2'],
 [/参悟在包(.+?)卷册「(.+?)」（(.+?)）/g,'Comprehend scroll “$2” in the bag ($1 · $3)'],
 [/共鸣词条 (\d+) 未能匹配到技能文案/g,'Resonance entry $1 has no matching skill text'],
 [/共鸣词条 (\d+)/g,'Resonance entry $1'],
 [/共 (\d+) 步，(\d+) 步可直接执行，(\d+) 步需要游戏内确认/g,
  '$1 steps: $2 executable now, $3 need in-game confirmation'],
 [/共 (\d+) 条获取路线，(\d+) 条来源可确认，(\d+) 条需要人工确认/g,
  '$1 routes: $2 confirmable, $3 need manual confirmation'],
 [/候选按「已有卷册 → 货架 → 请教 → 仅卷册 → 未开放」排列，仅为可执行顺序，不是推荐指数。/g,
  'Candidates are ordered “scroll owned → shelf → consult → scroll only → unavailable”; this is execution order, not a recommendation score.'],
 [/只使用已学会与在包资源；同名换版仅按同名字段对照，不推断升阶。/g,
  'Uses only learned resources and scrolls in the bag; same-name versions are compared by field, without inferring upgrades.'],
 [/说明：(\d+) 本功法不在 tbsectintroskill 中，秘传标记按否展示/g,
  'Note: $1 techniques are missing from tbsectintroskill; secret flags are shown as no'],
 [/已排除：/g,'Excluded: '],
 [/同名同境界重复，且缺少真意档位\/卷册/g,'duplicate same-name same-realm entry missing true-intent tiers/scrolls'],
 [/^奇遇绑定所在地点，配置里没有“境界高就关闭低阶奇遇”的硬限制；突破后低境界奇遇仍需回到对应地点才会遇到。当前境界的奇遇建议先清。$/,
  'Encounters are tied to their locations; the config has no “close low-realm encounters at high realm” rule, so you still need to return to the location after breaking through. Clear this realm’s encounters first.'],
 [/^同一母奇遇下的子奇遇折叠在母奇遇里；任一分支被选择或达成，整条奇遇即视为完成，其余未选分支不再计入未达成。无法确定父子关系的奇遇仍单独展示。$/,
  'Sub-encounters are folded under their parent; once any branch is chosen or achieved the whole encounter counts as done, and unchosen branches no longer count as incomplete. Encounters with unknown parentage are still shown separately.'],
 [/^状态 (.+) · 命中 /,'State $1 · matched '],
 [/^品质(\d+)$/,'Quality $1'],
 [/（(\d+)\/(\d+|—)）/g,'($1/$2)'],
 [/^位 · 可安全击杀$/,' · safe-killable'],
 [/^\/ (\d+) 位 · 其中在世$/,'/ $1 · alive'],
 [/^位 · 有交情$/,' · acquainted'],
 [/^加载更多（还有 (\d+) 位）$/,'Load more ($1 more)'],
 [/^显示更多（还有 (\d+) 位）$/,'Show more ($1 more)'],
 [/^共收录 (\d+) 位/,'Total $1'],
 [/^共 (\d+) 个天赋；命中 (\d+) 个天赋、(\d+) 条 NPC 记录（在世 (\d+) \/ 已离世 (\d+) \/ 不在当前世界 (\d+)）。筛选只高亮、不删除，未命中的内容变暗保留。$/,
  '$1 talents; $2 matched, $3 NPC records (alive $4 / dead $5 / elsewhere $6). Filters only highlight; non-matching entries stay dimmed.'],
 [/^共 (\d+) 位可偷 · (\d+) 位不可偷；点击 NPC 可在下方展开其全部持有物品$/,
  '$1 stealable · $2 not stealable; click an NPC to list all held items'],
 [/^(\d+) 位可偷；点击 NPC 可在下方展开其全部持有物品$/,
  '$1 stealable; click an NPC to list all held items'],
 [/^(\d+) 位可偷 · (\d+) 位不可偷$/,'$1 stealable · $2 not stealable'],
 [/^暂无成交记录$/,'No sales yet'],
 [/^上期寄售：成交 (\d+) 件、流拍 (\d+) 件，收益 /,'Last consignment: sold $1, unsold $2, profit '],
 [/^另有 (\d+) 条隐藏结算记录（付款\/领取记账）未展示$/,'$1 hidden settlement records (payment/claim journal) not shown'],
 [/^(\d+) 条隐藏结算记录（付款\/领取记账）未展示$/,'$1 hidden settlement records (payment/claim journal) not shown'],
 [/^(\d+) 条隐藏结算记录/,'$1 hidden settlement records'],
 [/^选择记录里的“累计选 N 次”是存档里的点击次数，不是奖励倍数。$/,
  'In choice records, “picked N times” is the click count from the save, not a reward multiplier.'],
 [/^「NPC 求购」表示该物品可被 NPC 收购或用于 NPC 需求任务；「炼丹药材 \/ 炼器材料」表示可作对应配方材料。$/,
  '“NPC demand” means the item can be bought by an NPC or used for an NPC request; “alchemy herb / forging material” means it works as a recipe material.'],
 [/^ 当前角色属性：/,' Current character stats: '],
 [/^；灵石 ([\d,]+)。/,'; Spirit Stones $1.'],
 [/^ 结局的「达成路径」来自配置里的设计备注，共 (\d+)\/(\d+) 条；静态能连到结局的分支共 (\d+) 条，其余由游戏结算判定。$/,
  ' Ending “paths” come from design notes in the config: $1/$2 endings. $3 branches link to endings statically; the rest are decided by the game.'],
 [/^ 奇遇按地点境界分组；配置里没有“角色境界高于某值就关闭奇遇”的硬条件，能否再遇到主要取决于还能不能回到该地点。$/,
  ' Encounters are grouped by location realm; the config has no “close low-realm encounters at high realm” rule, so re-encountering them depends on returning to the location.'],
 [/^ 历史达成按角色保存在本地，不写入游戏存档。$/,' Past achievements are stored locally per character and never written to the save.'],
 [/^剧情线：(\d+) 条 \/ (\d+) 个支线 · 共 (\d+) 条$/,'Storylines: $1 / $2 side quests · $3 total'],
 [/^逐个看：(\d+) \/ (\d+) 个支线 · 共 (\d+) 条剧情线$/,'One by one: $1 / $2 side quests · $3 storylines'],
 [/^已走 (\d+)\/(\d+)$/,'$1/$2 walked'],
 [/^已选另一条路$/,'Chose another path'],
 [/^多选一 · 只能选一条$/,'Pick one · only one can be chosen'],
 [/^二选一 · 只能选一条$/,'Pick one of two · only one can be chosen'],
 [/^修炼到「(.+?)」后自动出现$/,'Appears after reaching “$1”'],
 [/^剧情推进到这里时自动出现$/,'Appears when the story reaches here'],
 [/^剧情到这里自动出现，不需要额外条件$/,'Appears when the story reaches here; no extra condition'],
 [/^完成上面的前置后自动出现$/,'Appears after the prerequisites above'],
 [/^完成「(.+?)」后自动出现$/,'Appears after completing “$1”'],
 [/^(\d+) 段任务 · (\d+) 条角色线 · 展开某人按顺序看完整条线$/,'$1 quests · $2 character routes · open a character to see the full line'],
 [/^已走过 (\d+) 步$/,'$1 steps walked'],
 [/^(\d+)\/(\d+) 步 · /,'$1/$2 steps · '],
 [/^(\d+)\/(\d+) 步 · 未开始$/,'$1/$2 steps · not started'],
 [/^(\d+)\/(\d+) 步 · 可接取$/,'$1/$2 steps · available'],
 [/^(\d+)\/(\d+) 步 · 进行中$/,'$1/$2 steps · in progress'],
 [/^(\d+)\/(\d+) 步 · 差条件$/,'$1/$2 steps · locked'],
 [/^(\d+)\/(\d+) 步 · 已完成$/,'$1/$2 steps · completed'],
 [/^可接取 (\d+)$/,'$1 available'],
 [/^件拍品，参考总值$/,'lots · total reference value'],
 [/^第 (\d+) 步$/,'Step $1'],
 [/^第 (\d+) 环 · 跳到这个分叉点$/,'Ring $1 · jump to this fork'],
 [/^(\d+) 组 · 二选一$/,'$1 groups · pick one of two'],
 [/^对话分支$/,'Dialogue branches'],
 [/^未挂到故事线的任务$/,'Tasks not attached to a storyline'],
 [/^任务按真实前置关系分组：每条故事线从第一个任务开始按顺序展开，第 N 步表示在这条线里的位置，⑂ 处是二选一的分支。$/,
  'Tasks are grouped by real prerequisites: each storyline expands in order from its first task, “step N” is the position in that line, and ⑂ marks a two-way branch.'],
 [/^点故事线标题展开或收起；有进度的线会默认展开。$/,'Click a storyline title to expand or collapse; lines with progress start expanded.'],
 [/^点任务节点即可展开详情，详情就显示在这个节点下方，页面不会跳走。$/,'Click a task node to expand its details right below it; the page does not jump away.'],
 [/^这条线还没开启：目前没有可接取的任务。等剧情推进或与她结识后，这里会自动更新；下面的节点仍可查看。$/,
  'This route has not opened yet: no quest is available right now. It updates as the story advances or after you meet her; the nodes below are still viewable.'],
 [/^尚未开启 · 共 (\d+) 个节点$/,'Not started · $1 nodes'],
 [/^；背包还有 (\d+) 种卷册待参悟$/,'; $1 scrolls waiting in the bag'],
 [/^；背包没有待参悟卷册$/,'; no scrolls waiting in the bag'],
 [/^；下一档需 (\d+) 点，差 (\d+)$/,'; next tier needs $1 pts, $2 short'],
 [/^；已满档$/,'; maxed out'],
 [/^灵根 (\d+) 点 → 解锁 (\d+)\/(\d+) 档/,'Spirit root $1 pts → $2/$3 tiers unlocked'],
 [/^(\d+) 本功法没有匹配的心法：/,'$1 techniques have no matching core art: '],
 [/^共鸣「(.+?)」(.+?)，当前未满足$/,'Resonance “$1” $2, not met yet'],
 [/^「(.+?)」尚未获得，当前只是试算$/,'“$1” not owned yet; this is only a simulation'],
 [/^相生 (.+?)→(.+?)（需(.+?)系心法）$/,'Generates $1→$2 (needs a $3 core art)'],
 [/^需(.+?)系心法$/,'Needs a $1 core art'],
 [/^心法 (\d+)\/3$/,'Core arts $1/3'],
 [/^共鸣 (\d+)\/4$/,'Resonance $1/4'],
 [/^功法 (\d+)\/4$/,'Techniques $1/4'],
 [/^合计：参悟 (\d+) 分钟$/,'Total: $1 min of comprehending'],
 [/^参悟 (\d+) 分钟$/,'$1 min of comprehending'],
 [/^卷册待参悟 (\d+) 种$/,'Scrolls to comprehend: $1'],
 [/^另有 (\d+) 条，展开下方「完整体检」查看$/,'Also $1 more; expand “Full checkup” below'],
 [/^完整体检（(\d+) 条）$/,'Full checkup ($1)'],
 [/^第 (\d+) 段已获得$/,'Segment $1 obtained'],
 [/^第 (\d+) 段未获得$/,'Segment $1 not obtained'],
 [/^还差 (\d+) 位$/,'$1 more needed'],
 [/^索要 -(\d+) 好感$/,'Request · -$1 affinity'],
 [/^善恶值 (\d+)$/,'Alignment $1'],
 [/^无好感门槛 · 每周期 1 次 · 消耗不随境界折算$/,'No affinity requirement · once per cycle · cost does not scale with realm'],
 [/^(\d+) 件 · 来自他的背包$/,'$1 items · from their bag'],
 [/^(\d+) 件 · 来自索要模板$/,'$1 items · from their request template'],
 [/^他目前没有持有物品$/,'They hold no items right now'],
 [/^这个 NPC 没有索要模板$/,'This NPC has no request template'],
 [/^筛选结果：(\d+) 种物品（按品质从高到低分组），(\d+) 位 NPC，(\d+) 条持有记录$/,
  'Results: $1 item types (grouped by quality), $2 NPCs, $3 ownership records'],
 [/^一次最多 (\d+) 个$/,'up to $1 per request'],
 [/^成功率 (\d+)%$/,'Success rate $1%'],
 [/^每出价揭示 (\d+) 格，最多 (\d+)%$/,'$1 cells revealed per bid, up to $2%'],
 [/^(\d+) 件拍品，参考总值 /,'$1 lots, total reference value '],
 [/^上期寄售：暂无成交记录$/,'Last consignment: no sales yet'],
 [/^在 /g,'At '],
 [/^已退隐 · /g,'Retired · '],
 [/ (\d+) 段任务 · (\d+) 条角色线 · 展开某人按顺序看完整条线/g,'$1 quests · $2 character routes · open a character to see the full line'],
 [/^先完成 /g,'Finish first: '],
 [/与「([^」]+)」对话接取/g,'Talk to “$1” to accept'],
 [/（第 (\d+) 层）/g,' (layer $1)'],
 [/^无接取门槛，(.*)$/g,'No acceptance requirement — $1'],
 [/与「([^」]+)」对话，选择「([^」]+)」接取/g,'Talk to “$1”, choose “$2” to accept'],
 [/与「([^」]+)」对话时选择「([^」]+)」/g,'Talk to “$1” and choose “$2”'],
 [/剧情对话中选择「([^」]+)」/g,'Choose “$1” in the story dialogue'],
 [/^分支 · /g,'Branch · '],
 [/ · 隐藏$/g,' · hidden'],
 [/前置「([^」]+)」/g,'Prerequisite “$1”'],
 [/分支 (\d+) 选 1/g,'Branch · pick 1 of $1'],
 [/委托人「([^」]+)」/g,'Client “$1”'],
 [/^常驻地 /g,'Home: '],
 [/^与(.+)对话接取$/g,'Talk to $1 to accept'],
 [/累计选 (\d+) 次/g,'picked $1 times'],
 [/结局 (\d+)\/(\d+)/g,'endings $1/$2'],
 [/静态可确认 (\d+)\/(\d+) 条结局/g,'$1/$2 endings statically confirmable'],
 [/分支已归到母奇遇下/g,'branch merged into parent encounter'],
 [/另有 (\d+) 隐藏结算记录/g,'$1 hidden settlement records'],
 [/筛选结果：(\d+) 种物品（按品质从高到低分组）/g,'Results: $1 item types (grouped by quality)'],
 [/，(\d+) 位 NPC，(\d+) 条持有记录/g,', $1 NPCs, $2 ownership records'],
 [/^合计：参悟 (\d+) 分钟/g,'Total: $1 min of comprehending'],
 [/^(\d+) 位$/g,'$1'],
 [/还差 /g,'Left: '],
 [/个可接取/g,' available'],
 [/个进行中/g,' in progress'],
 [/个未开始/g,' not started'],
 [/个差条件/g,' locked'],
 [/、/g,' · '],
 [/尚未开启 · 共 (\d+) 个节点/g,'Not started · $1 nodes'],
 [/等待剧情触发（尚未结识或剧情未到）/g,'waits for story (not met yet or story not reached)'],
 [/筛选结果：(\d+) \/ (\d+) 个奇遇/g,'Results: $1 / $2 encounters'],
 [/筛选结果：(\d+) \/ (\d+) 种奖励物品/g,'Results: $1 / $2 reward items'],
 [/共 (\d+) 本功法/g,'$1 techniques total'],
 [/共 (\d+) 本心法/g,'$1 core arts total'],
 [/(\d+) 条持有记录/g,'$1 holdings'],
 [/(\d+) 件器胚/g,'$1 vessel blanks'],
 [/(\d+) 个结局产出/g,'$1 ending sources'],
 [/有 (\d+) 处高优先级问题/g,'$1 high-priority issues'],
 [/(\d+) 位可偷/g,'$1 stealable'],
 [/(\d+) 位不可偷/g,'$1 not stealable'],
 [/(\d+) 个节点/g,'$1 nodes'],
 [/(\d+) 位 NPC/g,'$1 NPCs'],
 [/含 (\d+) 条分支/g,'$1 branches'],
 [/显示 (\d+) \/ (\d+)/g,'Showing $1 / $2'],
 [/共 (\d+) 件突破材料/g,'Total $1 materials'],
 [/其他地图 (\d+) 处/g,'Other maps: $1'],
 [/当前地图「(.+?)」没有相关妖兽刷新/g,'No matching spawns on $1'],
 [/当前地图「(.+?)」没有稀有妖兽刷新/g,'No rare spawns on $1'],
 [/当前地图无相关刷新/g,'No related spawns here'],
 [/当前地图有刷新/g,'Spawns available here'],
 [/当前地图稀有妖兽/g,'Rare monsters on this map'],
 [/积攒修为 (\d+) \/ (\d+)/g,'Stored EXP $1 / $2'],
 [/· 上次突破 (\d+) 年（护法 (\d+) 位）/g,'· Last breakthrough $1 years (guardians $2)'],
 [/· 连续失败 (\d+) 次/g,'· $1 consecutive failures'],
 [/基础 → 满配（(\d+) 件辅材）/g,'Base → max ($1 aux items)'],
 [/寿元上限 (\d+) → (\d+)/g,'Max lifespan $1 → $2'],
 [/道途点 \+(\d+)/g,'Path points +$1'],
 [/灵根点 \+(\d+)/g,'Spirit root +$1'],
 [/攻速 \+(\d+)/g,'Attack speed +$1'],
 [/生命上限 \+(\d+)/g,'Max HP +$1'],
 [/暴伤减免 \+(\d+)%/g,'Crit damage reduction +$1%'],
 [/暴击伤害 \+(\d+)%/g,'Crit damage +$1%'],
 [/攻击 \+(\d+)/g,'Attack +$1'],
 [/防御 \+(\d+)/g,'Defense +$1'],
 [/海元 \+(\d+)/g,'Haiyuan +$1'],
 [/Results: (\d+) 种物品（按品质从高到低分组）/g,'Results: $1 items (grouped by quality, high to low)'],
 [/｜ (\d+) NPC，(\d+) 持有记录/g,'| $1 NPCs, $2 holdings'],
 [/品质 (\d+)/g,'Quality $1'],
 [/可偷 (\d+) 处/g,'Stealable $1'],
 [/(\d+) 种类 最低：(.+)/g,'$1 types; lowest: $2'],
 [/未拥有 (\d+) 种/g,'$1 unowned'],
 [/Results: (\d+) \/ (\d+) 奇遇/g,'Results: $1 / $2 encounters'],
 [/另有 (\d+) 条隐藏结局（付费\/隐藏结局）未展示/g,'$1 hidden endings not shown'],
 [/在「(.+?)」(\d+) 选 1：你选了(.+?)，未选(.+)/g,'At “$1”, $2-way choice: picked $3; not picked: $4'],
 [/在「(.+?)」选了(.+?)后，未走(.+)/g,'At “$1” picked $2; skipped: $3'],
 [/前置「(.+?)」没有走/g,'Prerequisite “$1” skipped'],
 [/到任务页查看「(.+?)」/g,'View “$1” in Quests'],
 [/到红尘页查看「(.+?)」/g,'View “$1” in Romance'],
 [/到奇遇页查看「(.+?)」/g,'View “$1” in Encounters'],
 [/已跳到第 (\d+) 环/g,'Jumped to ring $1'],
 [/第 (\d+) 环/g,'Ring $1'],
 [/还有 (\d+) 个选项，点开看/g,'$1 more options; open for details'],
 [/等 (\d+) 个选项/g,'+$1 options'],
 [/献祭 (\d+) 轮/g,'$1 rounds'],
 [/自身血 (\d+) 次 \/ 野兽 (\d+) 次/g,'own blood $1, beasts $2'],
 [/，最近结算「(.+?)」/g,'; latest ending “$1”'],
 [/存档只保留累计次数与最近一次结算，逐次选择没有记录。/g,'The save keeps only totals and the latest settlement; individual choices are not recorded.'],
 [/(\d+) 分支已回归母奇遇下/g,'$1 branches merged into parents'],
 [/(\d+) 级 经验 (\d+)/g,'Lv $1 · EXP $2'],
 [/(\d+) 号炉 已解锁 (\d+) 座/g,'Furnace #$1 · $2 unlocked'],
 [/(\d+) \/ (\d+) 张 最高 (\d+) 品/g,'$1 / $2 · best quality $3'],
 [/(\d+) 个 已拾取 (\d+)/g,'$1 · $2 picked'],
 [/(\d+) 个支线/g,'$1 side quests'],
 [/配装没有硬伤，有 (\d+) 处可优化；背包还有 (\d+) 种功法待参透/g,'No critical issues; $1 improvements; $2 techniques left to comprehend'],
 [/「(.+?)」等 (\d+) 本已学但没装配（槽位已满，需替换）/g,'“$1” and $2 more learned but not equipped (slots full)'],
 [/「(.+?)」第 (\d+) 格功法空着/g,'“$1” slot $2 is empty'],
 [/「(.+?)」「(.+?)」等 (\d+) 本功法已学但没运转/g,'“$1”, “$2” and $3 more learned but idle'],
 [/第 (\d+) 层/g,'Layer $1'],
 [/完成「(.+?)」后自动出现/g,'Appears after completing “$1”'],
 [/完成「(.+?)」后出现/g,'Appears after completing “$1”'],
 [/完成后出现/g,'Appears after completion'],
 [/需 (.+)/g,'Requires $1'],
 [/存档：/g,'Save: '],
 [/原始更新：/g,'Original update: '],
 [/配置：/g,'Config: '],
 [/｜/g,' | '],
 [/永久灵眼 (\d+) 个（已吸 (\d+)\/(\d+)）/g,'Permanent spots $1 (absorbed $2/$3)'],
 [/本轮灵眼 (\d+) 个/g,'Cycle spots $1'],
 [/每眼 (\d+) 修为、每次拖动 (\d+) 修为/g,'$1 EXP per spot, $2 per drag'],
 [/坚持 (\d+) 回合/g,'Hold $1 rounds'],
 [/(\d+) 年（(\d+) 天）/g,'$1 years ($2 days)'],
 [/\s位 · /g,' · '],
 [/(\d+) 人持有/g,'held by $1'],
 [/In auction有/g,'In auction'],
 [/寿元 \+(\d+)/g,'Lifespan +$1'],
 [/敌人无敌、不可逃跑/g,'Enemy invincible, cannot flee'],
 [/会掉落的 (\d+) 支妖兽队伍在存档里都没有刷新记录/g,'$1 monster teams have no recorded spawn'],
 [/没有妖兽掉落的阶段材料/g,'Stage materials with no monster drops'],
 [/(\d+) 镇 · \+([\d,]+) 声望 · \+([\d,]+) 灵石/g,'$1 towns · +$2 Reputation · +$3 Spirit Stones'],
 [/(\d+) 城镇/g,'$1 towns'],
 [/声望 ([\d,]+)/g,'Reputation $1'],
 [/([\d,]+) 灵石/g,'$1 Spirit Stones'],
 [/当前 ([\d,]+) · 下一档 ([\d,]+)（还差 ([\d,]+)）/g,'Current $1 · Next tier $2 (still need $3)'],
 [/(\d+) 可接 · (\d+) 进行中/g,'$1 available · $2 in progress'],
 [/难度 (\d+)/g,'Difficulty $1'],
 [/未开 (\d+)/g,'Unopened $1'],
 [/已兑换 (\d+)/g,'Exchanged $1'],
 [/已装配 (\d+)/g,'$1 equipped'],
 [/称号 (\d+)/g,'Title $1'],
 [/赏金 (\d+)/g,'Reward $1'],
 [/(\d+) total 天赋/g,'$1 total talents'],
 [/命中 (\d+) 天赋/g,'$1 matched talents'],
 [/(\d+) NPC 记录（在世 (\d+) \/ 已离世 (\d+) \/ 不在当前世界 (\d+)）/g,'$1 NPC records (alive $2 / dead $3 / elsewhere $4)'],
 [/Current realm \[(.+?)\] 可同道 (\d+) 人，已同道 (\d+) 人/g,'Current realm [$1] · $2 companions allowed, $3 joined'],
 [/展开 (\d+)/g,'Show $1'],
 [/\+(\d+) 声望 \+(\d+) 灵石/g,'+$1 Reputation +$2 Spirit Stones'],
 [/(\d+) 天阶/g,'Heaven tier $1'],
 [/(\d+) 间/g,'$1'],
 [/(\d+)\s*城镇 · 点[击]?行?查看委托与货架/g,'$1 towns · click a row to view commissions and shelves'],
 [/等 (\d+) types/g,'and $1 more'],
 [/前往(.+?)，与(.+?)交谈，了解近期情况/g,'Go to $1 and talk to $2 about the situation'],
 [/前往(.+?)，击败(\d+)只(.+)/g,'Go to $1 and defeat $2 $3'],
 [/前往(.+?)，采集(\d+)个(.+)/g,'Go to $1 and gather $2 $3'],
 [/前往(.+?)，为(.+?)完成一次疏经导脉/g,'Go to $1 and treat $2'],
 [/前往(.+?)，与(.+?)完成一次切磋/g,'Go to $1 and spar with $2'],
 [/前往(.+?)，通过赠礼使(.+?)累计增加(\d+)点亲密度/g,'Go to $1 and gift $2 to raise affinity by $3'],
 [/(\d+) · 可获/g,'$1 · rewards'],
 [/与 (\d+) 档相同/g,'Same as tier $1'],
 [/(\d+) 档/g,'$1 tiers'],
 [/(\d+) 城 ·/g,'$1 towns ·'],
 [/(\d+)\s*城镇/g,'$1 towns'],
 [/(\d+) ?镇/g,'$1 towns'],
 [/委托/g,'Commission'], [/声望/g,'Reputation'], [/灵石/g,'Spirit Stones'],
 [/货架/g,'Shelves'], [/访谈/g,'Interview'], [/赠礼/g,'Gift'], [/讨伐/g,'Subjugate'],
 [/采集/g,'Gather'], [/行医/g,'Heal'], [/切磋/g,'Spar'], [/交付/g,'Deliver'],
 [/前往/g,'Go to'], [/交谈/g,'Talk'], [/可获/g,'rewards'], [/全城/g,'City-wide'],
 [/：/g,': '],
 [/采集 /g,'Gather '],
 [/已学但没装槽/g,'learned but not equipped'],
 [/已学但没运转/g,'learned but idle'],
 [/已学未装/g,'learned, not equipped'],
 [/已学未运转/g,'learned, idle'],
 [/需要替换/g,'replace needed'],
 [/里没参悟/g,'not comprehended'],
 [/Scroll in bag/g,'Scroll in bag'],
 [/完整体检/g,'Full checkup'],
 [/另有 (\d+)，展开下方/g,'Also $1; expand below'],
 [/本门流派（(\d+)）/g,'Sect schools ($1)'],
 [/同系/g,'Same-element'],
 [/已学 (\d+)\/(\d+)/g,'Learned $1/$2'],
 [/可同道/g,'companions allowed'],
 [/已同道/g,'joined'],
 [/人，/g,' · '],
 [/配装没有硬伤，有 /g,'No critical issues; '],
 [/处可优化/g,' improvements'],
 [/处高优先级问题/g,' high-priority issues'],
 [/配装没有发现问题/g,'No issues found'],
 [/背包还有 /g,'Bag has '],
 [/种功法待参透/g,' techniques to comprehend'],
 [/另有 (\d+) 条，展开下方「完整体检」查看/g,'Also $1 more; expand 「Full checkup」 below'],
 [/本已学但没装槽（槽位已满，需要替换）/g,' learned but not equipped (slots full, replace needed)'],
 [/本功法已学但没运转/g,' techniques learned but idle'],
 [/本功法已学但没装配/g,' techniques learned but not equipped'],
 [/已满/g,'full'],
 [/Techniquelearned/g,' techniques learned'],
 [/另有 (\d+)，expand below/g,'Also $1; expand below'],
 [/成交 (\d+)，流拍 (\d+)，收益 ([\d,]+)/g,'Sold $1, unsold $2, profit $3'],
 [/再攒 (\d+) 可换/g,'Save $1 more for'],
 [/Commission板/g,'Commission board'],
 [/本期没有征收/g,'No collections this cycle.'],
 [/本期挂出/g,'offered this cycle'],
 [/会轮换出新的一批/g,'rotate in a new batch'],
 [/只能同时接/g,'concurrent limit'],
 [/你能同时接的上限是/g,'your concurrent limit is'],
 [/由职位决定/g,'set by rank'],
 [/是两套/g,'are separate'],
 [/已接的会进入任务日志/g,'accepted ones go to the quest log'],
 [/计在/g,'count toward'],
 [/这三类找执事/g,'get these from stewards'],
 [/领取/g,'claim'],
 [/凡人 not achieved yet/g,'Mortal (not achieved)'],
 [/最值[:：] /g,'Best: '],
 [/筛选结果[:：] /g,'Results: '],
 [/(\d+) \/ (\d+)奇遇/g,'$1 / $2 encounters'],
 [/(\d+)分支已归到母奇遇下/g,'$1 branches merged into parents'],
 [/另有 (\d+)隐藏结算记录/g,'$1 hidden settlement records'],
 [/付款\/claim记账/g,'payment/claim journal'],
 [/未展示/g,'not shown'],
 [/已接 (\d+)/g,'$1 accepted'],
 [/还可接 (\d+)/g,'$1 can accept'],
 [/差 /g,'Missing '],
 [/(\d+)年(\d+)月(\d+)日/g,'$1/$2/$3'],
 [/贡献/g,'contribution'], [/外务/g,'external'], [/访友/g,'Visit friend'],
 [/外门弟子/g,'Outer disciple'], [/内门弟子/g,'Inner disciple'],
 [/真传弟子/g,'True disciple'], [/长老/g,'Elder'], [/执事/g,'Steward'],
 [/突破助道灵物/g,'Breakthrough auxiliary material'],
 [/(\d+) ?条?外务Commission/g,'$1 external commissions'],
 [/不等于/g,'does not mean'],
 [/——/g,' — '],
 [/条\(set by rank\)/g,'(set by rank)'],
 [/待提交/g,'to submit'],
 [/Elderclaim/g,'Elders'],
 [/结局 (\d+)\/(\d+)/g,'Ending $1/$2'],
 [/，不在Commission/g,', not on the commission'],
 [/炼气期/g,'Qi Refining'], [/筑基期/g,'Foundation'], [/结丹期/g,'Golden Core'],
 [/元婴期/g,'Nascent Soul'], [/化神期/g,'Spirit Transformation'],
 [/（/g,'('], [/）/g,')'],
 [/赏金/g,'Reward'], [/称号/g,'Title'], [/难度/g,'Difficulty'],
 [/品质/g,'Quality'], [/槽位/g,'Slot'], [/功法/g,'Technique'], [/心法/g,'Core art'],
 [/门派/g,'Sect'], [/境界/g,'Realm'], [/属性/g,'Stats'], [/技能/g,'Skill'],
 [/奖励/g,'Rewards'], [/消耗/g,'Cost'], [/需求/g,'Requirement'],
 [/状态/g,'State'], [/进度/g,'Progress'], [/可接/g,'Available'],
 [/当前/g,'Current'], [/点击/g,'Click'], [/查看/g,'View'], [/全部/g,'All'],
 [/第 (\d+) 格/g,'Slot $1'],
 [/槽位 (\d+)/g,'Slot $1'],
 [/传送 (\d+) 次/g,'Teleport ×$1'],
 [/最高 (\d+) 品/g,'Best quality $1'],
 [/已解锁 (\d+) 座/g,'$1 unlocked'],
 [/已拾取 (\d+)/g,'$1 picked'],
 [/传送 (\d+) 次/g,'Teleport ×$1'],
 [/经验 (\d+)/g,'EXP $1'],
 [/编号 #(\d+)/g,'#$1'],
 [/共 (\d+) (个|项|条|位|件)/g,'$1 total'],
 [/(\d+) 号炉/g,'Furnace #$1'],
 [/(\d+) 级/g,'Lv $1'],
 [/(\d+) 岁/g,'age $1'],
 [/(\d+) 年/g,'$1 years'],
 [/(\d+) 天/g,'$1 days'],
 [/(\d+) 层/g,'layer $1'],
 [/(\d+) 次/g,'×$1'],
 [/(\d+) (个|项|条|位|张|座|枚|块|件)/g,'$1'],
 [/(\d+) 种功法/g,'$1 techniques'],
 [/(\d+) 种/g,'$1 types'],
 [/(\d+) 本/g,'$1'],
 [/(\d+) 处/g,'$1'],
 [/坐标 ([\d,\s]+) 编号 #(\d+)/g,'Coords $1 · #$2'],
 [/剧情线 (\d+) 条/g,'Storylines: $1'],
 [/进行中 (\d+)/g,'In progress $1'],
 [/已完成 (\d+)/g,'Completed $1'],
 [/未接取 (\d+)/g,'Not accepted $1'],
 [/满配 (\d+)%$/,'Max $1%'],
 [/还差 (\d+) 修为/g,'Still need $1 EXP'],
 [/已选 (\d+)\/(\d+)/g,'Selected $1/$2'],
 [/(\d+) \/ (\d+) 层/g,'Layer $1 / $2']
];
const TR_CJK=/[\u4e00-\u9fff]/;
const TR_CACHE=new Map();
let TR_INDEX=null;
function trPhrase(text){
 if(!TR_CJK.test(text))return text;
 if(!TR_INDEX){
   TR_INDEX={};
   Object.keys(EN).forEach(function(key){
     if(key.length<4)return;
     const head=key.charAt(0);
     (TR_INDEX[head]||(TR_INDEX[head]=[])).push(key);
   });
   Object.keys(TR_INDEX).forEach(function(head){
     TR_INDEX[head].sort(function(a,b){return b.length-a.length});
   });
 }
 const seen={};
 let out=text;
 for(let i=0;i<text.length;i++){
   const bucket=TR_INDEX[text.charAt(i)];
   if(!bucket)continue;
   bucket.forEach(function(key){
     if(seen[key]||out.indexOf(key)<0)return;
     seen[key]=1;
     out=out.split(key).join(EN[key]!==undefined?EN[key]:key);
   });
 }
 return out;
}
const CN_DIGITS={'零':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9};
function cnNumber(text){
 if(text==='十')return 10;
 const at=text.indexOf('十');
 if(at<0)return CN_DIGITS[text];
 const tens=at===0?1:CN_DIGITS[text.charAt(0)];
 const ones=at===text.length-1?0:CN_DIGITS[text.charAt(text.length-1)];
 if(tens===undefined||ones===undefined)return null;
 return tens*10+ones;
}
// 中文数字 + 单位：配置里会出现「十三层」「十二层」，先转成 layer 13 再走通用替换。
function trNumbers(text){
 return text.replace(/([零一二两三四五六七八九十]+)层/g,function(all,num){
   const value=cnNumber(num);return value===null?all:('layer '+value);
 });
}
function trText(text){
 if(LANG!=='en'||!text)return text;
 const trimmed=text.trim();
 if(!trimmed||!TR_CJK.test(trimmed))return text;
 if(TR_CACHE.has(trimmed))return TR_CACHE.get(trimmed);
 let out=EN[trimmed];
 if(out===undefined){
   out=trimmed;
   TR_FIRST.forEach(function(rule){out=out.replace(rule[0],rule[1])});
   TR_RULES.forEach(function(rule){out=out.replace(rule[0],rule[1])});
   out=trNumbers(out);
   TR_LAST.forEach(function(rule){out=out.replace(rule[0],rule[1])});
   if(TR_CJK.test(out)&&out.length<=60)out=trPhrase(out);
   if(out===trimmed)out=undefined;
 }
 if(out===undefined||out===trimmed)out=text;
 else out=text.replace(trimmed,out);
 TR_CACHE.set(trimmed,out);
 return out;
}
function localize(root){
 if(LANG!=='en'||!root)return;
 try{
   const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,null);
   const nodes=[];
   while(walker.nextNode())nodes.push(walker.currentNode);
   nodes.forEach(function(node){const next=trText(node.nodeValue);if(next!==node.nodeValue)node.nodeValue=next});
   const attrs=['title','placeholder','aria-label'];
   const scan=function(el){
     if(!el.getAttribute)return;
     attrs.forEach(function(name){
       const value=el.getAttribute(name);
       if(!value)return;
       const next=trText(value);
       if(next!==value)el.setAttribute(name,next);
     });
   };
   if(root.nodeType===1)scan(root);
   if(root.querySelectorAll)root.querySelectorAll('[title],[placeholder],[aria-label]').forEach(scan);
 }catch(e){}
}
window.XY_LANG=LANG;
window.XY_T=function(text){return LANG==='en'?(EN[text]||text):text};
const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const store={get(k,d){try{const v=localStorage.getItem(k);return v===null?d:JSON.parse(v)}catch(e){return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
const labels=Object.assign({bedroom:'仙居楼互动',talent:'NPC天赋',items:'NPC物品',pill:'炼丹',forge:'炼器',event:'奇遇',quest:'支线'},(LANG==='en'?DATA.labels_en:DATA.labels)||{});let active=store.get('worldapart.active.tab.v2',DATA.enabled[0]||'');if(!DATA.enabled.includes(active))active=DATA.enabled[0]||'';
function shortSave(name){const s=String(name||'');if(!s)return '';const base=s.replace(/\.msgpack(\.bin)?$/i,'').replace(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/i,'').replace(/_gameworld$/i,'');const mo=base.match(/^slots_(auto|manual)(?:_(\d+))?$/i);if(mo)return (mo[1].toLowerCase()==='auto'?'自动存档':'手动存档')+(mo[2]?' '+parseInt(mo[2],10):'');return base||s}
function sourceHtml(m){const L=LANG==='en';const CFG={'游戏当前配置':'Game config','兼容缓存':'Compatible cache','内置快照':'Built-in snapshot'};const cfgName=L?(CFG[m.config]||m.config):m.config;const ch=DATA.character||{};const gd=ch.date||{};const who=ch.name?`${L?'Character ':'角色 '}${esc(ch.name)}${ch.layer_name?' · '+esc(ch.layer_name):''}${ch.layer?`（${L?'layer ':'第 '}${ch.layer_local||ch.layer}${L?'':' 层'}）`:''}`:'';const full=[who,`${L?'Save ':'存档 '}${m.src||(L?'none':'暂无')}`,`${L?'Updated ':'更新 '}${m.stamp_text}`,`${L?'Config ':'配置 '}${cfgName}`].join(' | ');const parts=[];if(who)parts.push(`<span class="src-item src-who">${who}</span>`);parts.push(`<span class="src-item">${L?'Save ':'存档 '}${esc(shortSave(m.src)||(L?'none':'暂无'))}</span>`);parts.push(`<span class="src-item">${L?'Updated ':'更新 '}${esc(m.stamp_text)}</span>`);parts.push(`<span class="src-item">${L?'Config ':'配置 '}${esc(cfgName)}</span>`);if(m.config_warning)parts.push(`<span class="src-item src-warn">${esc(m.config_warning)}</span>`);if(m.merged)parts.push(`<span class="src-item">${L?'Merged ':'合并 '}${m.merged}${L?'':' 份'}</span>`);return `<div class="source" title="${esc(full)}">${parts.join('<span class="src-sep">·</span>')}</div>`}
function showTab(name){active=name;store.set('worldapart.active.tab.v2',name);document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===name));document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.tab===name));if(window.PROGRESS_RENDER_TAB)window.PROGRESS_RENDER_TAB(name)}
function initTabs(){$('tabs').innerHTML=DATA.enabled.map(n=>`<button class="tab" data-tab="${n}">${labels[n]}</button>`).join('');document.querySelectorAll('.tab').forEach(x=>x.onclick=()=>showTab(x.dataset.tab));if(!DATA.enabled.length){$('warnings').innerHTML=DATA.warnings.map(esc).join('<br>');return}showTab(active)}

/* ---- 模块共享的展示工具（由天赋/物品/炼器共用） ---- */
function uniq(values){return [...new Set(values)].sort((a,b)=>{const an=Number(a),bn=Number(b);if(a!==''&&b!==''&&!Number.isNaN(an)&&!Number.isNaN(bn))return an-bn;return String(a).localeCompare(String(b),'zh-CN')})}
function hi(value,q){
 const text=String(value??'');if(!q)return esc(text);const lower=text.toLowerCase();let at=0,out='',found;
 while((found=lower.indexOf(q,at))>=0){out+=esc(text.slice(at,found))+'<mark>'+esc(text.slice(found,found+q.length))+'</mark>';at=found+q.length}
 return out+esc(text.slice(at));
}
$('warnings').innerHTML=(DATA.warnings||[]).map(esc).join('<br>');initTabs();
__PLUGIN_JS__
// 页签按需渲染：十六个模块全量建 DOM 会让覆盖窗口在 4K 下瞬间吃掉大量内存和显存，
// 并拖慢游戏。切到哪个页签才渲染哪个，数据刷新后仍由整页重载统一重建。
const renderedTabs=new Set();
function renderTab(key){
 if(renderedTabs.has(key))return;
 const view=(window.PROGRESS_VIEWS||{})[key];
 if(typeof view!=='function')return;
 renderedTabs.add(key);
 window.__xyRendering=true;
 try{
   view(DATA);
   const panel=document.getElementById(key);
   if(panel&&window.XY_LANG==='en')localize(panel);
 }catch(e){console.error('模块 '+key+' 渲染失败',e)}
 setTimeout(function(){window.__xyRendering=false},30);
}
window.PROGRESS_RENDER_TAB=renderTab;
window.PROGRESS_GOTO=function(key,needle){
 if(!key||!(DATA.enabled||[]).includes(key))return false;
 showTab(key);
 if(!needle)return true;
 var hook=window['PROGRESS_GOTO_'+key];
 if(typeof hook==='function'&&hook(needle))return true;
 var tries=0;
 (function focus(){
  var input=document.getElementById('qs');
  if(input){
   input.value=needle;
   input.dispatchEvent(new Event('input',{bubbles:true}));
   try{input.scrollIntoView({behavior:'smooth',block:'center'})}catch(e){}
   return;
  }
  if(tries++<20)setTimeout(focus,50);
 })();
 return true;
};
renderTab(active);
// 首屏提示条可以关掉：老玩家读一次就不需要它一直占 50px 高度。
(function(){
 const key='worldapart.notice.dismissed.v1';
 const seen=store.get(key,[]);
 document.querySelectorAll('[data-notice]').forEach(function(box){
   if(seen.indexOf(box.getAttribute('data-notice'))>=0){box.classList.add('notice-hidden');return}
   const btn=box.querySelector('.notice-x');
   if(btn)btn.onclick=function(){
     box.classList.add('notice-hidden');
     const list=store.get(key,[]);
     if(list.indexOf(box.getAttribute('data-notice'))<0)list.push(box.getAttribute('data-notice'));
     store.set(key,list);
   };
 });
})();

let polledVersion=INITIAL_VERSION;
let pageVisible=true,reloadTimer=null,manualUntil=0,pendingSince=0;
let lastReload=Number(sessionStorage.getItem('xy-last-reload')||0)||0;
// 刷新前记住每个页签的滚动位置，刷新后回到原处，避免“看着看着跳回顶部”。
const SCROLL_KEY='worldapart.scroll.v1';
if('scrollRestoration' in history){try{history.scrollRestoration='manual'}catch(e){}}
// 正在滚动 / 点击 / 输入时先不打断，等手停下来再刷新；最多推迟 15 秒。
let lastActive=Date.now();
['pointerdown','keydown','wheel','touchstart','scroll'].forEach(function(ev){
 window.addEventListener(ev,function(){lastActive=Date.now()},{passive:true});
});
function saveScroll(){
 try{const m=store.get(SCROLL_KEY,{})||{};m[active]=window.scrollY||window.pageYOffset||0;store.set(SCROLL_KEY,m)}catch(e){}
}
function restoreScroll(){
 let y=0;
 try{y=Number((store.get(SCROLL_KEY,{})||{})[active]||0)}catch(e){y=0}
 if(!y)return;
 const go=function(){try{window.scrollTo(0,y)}catch(e){}};
 go();setTimeout(go,80);setTimeout(go,220);setTimeout(go,500);
}
// 展开过的卡片也按摘要文字记住：刷新后不会整页收起，只留下“跳一下”的感觉。
const OPEN_KEY='worldapart.open.v1';
function saveOpen(){
 try{
  const list=[];
  document.querySelectorAll('details[open]').forEach(function(d){
   const s=d.querySelector('summary');
   const t=s?(s.textContent||'').trim().slice(0,90):'';
   if(t)list.push(t);
  });
  store.set(OPEN_KEY,{tab:active,list:list});
 }catch(e){}
}
function restoreOpen(){
 let saved=null;
 try{saved=store.get(OPEN_KEY,null)}catch(e){}
 if(!saved||saved.tab!==active||!saved.list||!saved.list.length)return;
 const set=new Set(saved.list);
 const go=function(){
  document.querySelectorAll('details').forEach(function(d){
   if(d.open)return;
   const s=d.querySelector('summary');
   const t=s?(s.textContent||'').trim().slice(0,90):'';
   if(t&&set.has(t))d.open=true;
  });
 };
 go();setTimeout(go,80);setTimeout(go,220);
}
function showRefreshing(){
 let el=document.getElementById('xy-refresh');
 if(!el){
  el=document.createElement('div');el.id='xy-refresh';
  el.innerHTML='<span class="spin"></span><span class="txt"></span><span class="bar"></span>';
  document.body.appendChild(el);
 }
 const txt=el.querySelector('.txt');
 if(txt)txt.textContent=window.XY_T?window.XY_T('数据已更新，正在刷新…'):'数据已更新，正在刷新…';
 el.classList.add('on');
}
function reloadNow(){
 saveScroll();
 saveOpen();
 lastReload=Date.now();
 try{sessionStorage.setItem('xy-last-reload',String(lastReload))}catch(e){}
 showRefreshing();
 // 留一点时间把“正在刷新”提示画出来，再做整页重建。
 setTimeout(function(){location.reload()},380);
}
// 同步时存档可能连续更新好几次：只安排一次重载。
// 手动点「立即同步」时尽快刷新；自动更新则至少间隔 6 秒，避免反复重建大页面拖慢游戏。
function scheduleReload(){
 if(reloadTimer)return;
 pendingSince=Date.now();
 const floor=Date.now()<manualUntil?1200:6000;
 const wait=Math.max(0,floor-(Date.now()-lastReload));
 reloadTimer=setTimeout(tryReload,wait);
}
function tryReload(){
 reloadTimer=null;
 // 浮窗收起时先不重建页面，等下次呼出再检查，避免在游戏过程中占用显卡和内存。
 if(!pageVisible)return;
 if(Date.now()-lastActive<900&&Date.now()-pendingSince<15000){
  reloadTimer=setTimeout(tryReload,700);return;
 }

 reloadNow();
}
function checkVersion(){
 if(!pageVisible||reloadTimer)return;
 const script=document.createElement('script');
 script.src='仙友助手版本.js?t='+Date.now();
 script.onload=()=>{const next=window.PROGRESS_VERSION||'';script.remove();if(next&&next!==polledVersion){scheduleReload();return}polledVersion=next||polledVersion};
 script.onerror=()=>script.remove();
 document.head.appendChild(script);
}
window.XY_HIDE=function(){pageVisible=false};
window.XY_SHOW=function(){pageVisible=true;checkVersion()};
// 覆盖窗口收起时不刷新页面；呼出后立即补一次检查。
function syncVisibility(){
 const call=window.pywebview&&window.pywebview.api&&window.pywebview.api.state;
 if(!call)return;
 try{Promise.resolve(call()).then(s=>{
   const vis=!s||s.visible!==false;
   if(vis&&!pageVisible)checkVersion();
   pageVisible=vis;
 },()=>{})}catch(e){}
}
setInterval(checkVersion,3000);
setInterval(syncVisibility,2500);
// 浮窗点「立即同步」后，接下来 10 秒每 1.5 秒查一次，数据一到就尽快刷新。
let quickUntil=0;
window.PROGRESS_CHECK_FAST=function(){quickUntil=Date.now()+10000};
// 手动同步：新数据一到就尽快刷新，不用等自动刷新的 6 秒间隔。
window.PROGRESS_MANUAL_SYNC=function(){manualUntil=Date.now()+15000;window.PROGRESS_CHECK_FAST()};
setInterval(()=>{if(Date.now()<quickUntil)checkVersion()},1500);
// 上次是同一页签的直接刷新：把展开的卡片和阅读位置接上。
restoreOpen();
restoreScroll();

/* ---- 网页版「立即同步」：通过本机回环服务通知插件马上导出 ---- */
(function(){
 const url=DATA.sync_url||'';
 const bar=$('webbar'),btn=$('web-sync'),tip=$('web-tip');
 if(!url||!bar||!btn)return;
 bar.hidden=false;
 let timer=null;
 function say(text){
   tip.textContent=text||'';
   if(timer)clearTimeout(timer);
   if(text)timer=setTimeout(function(){tip.textContent=''},10000);
 }
 btn.onclick=function(){
   if(btn.disabled)return;
   btn.disabled=true;btn.textContent='同步中…';
   try{if(window.PROGRESS_MANUAL_SYNC)window.PROGRESS_MANUAL_SYNC()}catch(e){}
   const tag=document.createElement('script');
   tag.src=url+'?t='+Date.now();
   const done=function(ok){
     tag.remove();
     if(!ok){btn.disabled=false;btn.textContent='立即同步';say('同步服务没响应：请确认黑色窗口仍在运行');return}
     // 插件已收到请求：按钮保持“等待数据”，等页面真正刷新时一起消失。
     btn.textContent='等待数据…';
     say('已请求同步，插件导出后会自动刷新');
     setTimeout(function(){if(document.body.contains(btn)){btn.disabled=false;btn.textContent='立即同步'}},15000);
   };
   tag.onload=function(){done(true)};
   tag.onerror=function(){done(false)};
   document.head.appendChild(tag);
 };
})();

/* ---- 英文界面：渲染后按词条翻译固定文案，游戏数据保持中文 ---- */
if(LANG==='en'){
 const trNode=function(node){const next=trText(node.nodeValue);if(next!==node.nodeValue)node.nodeValue=next};
 ['warnings','tabs','webbar'].forEach(function(id){const el=document.getElementById(id);if(el)localize(el)});
 let localizing=false;
 try{
   new MutationObserver(function(list){
     if(localizing||window.__xyRendering)return;
     localizing=true;
     try{
       list.forEach(function(m){
         if(m.type==='characterData'){trNode(m.target)}
         else{m.addedNodes.forEach(function(node){
           if(node.nodeType===3)trNode(node);else if(node.nodeType===1)localize(node);
         })}
       });
     }finally{setTimeout(function(){localizing=false},0)}
   }).observe(document.body,{childList:true,subtree:true,characterData:true});
 }catch(e){}
}
</script></body></html>"""


def _panels(tabs):
    return "".join(
        '<section id="%s" class="panel"></section>' % re.sub(r"[^0-9A-Za-z_-]", "", str(item.get("key") or ""))
        for item in tabs if item.get("key"))


def _plugin_assets():
    return registry.assets_css(), registry.assets_js()


def build_html(payload):
    tabs = payload.get("tabs") or [{"key": key} for key in payload.get("enabled") or ()]
    lang = payload.get("lang") or "zh"
    data = dict(payload)
    labels = dict(data.get("labels") or {})
    labels_en = dict(data.get("labels_en") or {})
    for item in tabs:
        key = str(item.get("key") or "")
        if key:
            labels.setdefault(key, str(item.get("label") or key))
            labels_en.setdefault(key, str(item.get("label_en") or item.get("label") or key))
    if labels:
        data["labels"] = labels
    data["labels_en"] = labels_en
    data["lang"] = lang
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    body = body.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    css, js = _plugin_assets()
    # 只有打包后的 exe 才有那个黑色控制台窗口；关掉它就没有自动刷新了。
    if lang == "en":
        if common.OVERLAY_MODE:
            console_note = '<div class="notice">%s</div>' % i18n.shell("en", "notice_overlay")
        else:
            console_note = ("" if not common.FROZEN
                            else '<div class="notice">%s</div>' % i18n.shell("en", "notice_web"))
        console_note = ('<div class="notice notice-tip" data-notice="overlay-hint">'
                        '<button type="button" class="notice-x" aria-label="Dismiss" '
                        'title="Dismiss this hint">×</button>%s</div>'
                        % i18n.shell("en", "notice_update")) + console_note
    else:
        if common.OVERLAY_MODE:
            console_note = ('<div class="notice">按顶部显示的快捷键收起或再次呼出（默认为 <b>F3</b>，'
                            '可在「功能设置.bat」里修改），<b>ESC</b> 快速隐藏，右上角可退出工具。</div>')
        else:
            console_note = (""
                            if not common.FROZEN else
                            '<div class="notice">使用期间请留着那个黑色小窗口（可以最小化）——'
                            '<b>它负责自动检查数据，关掉后本页就不再自动刷新。</b>'
                            '右下角「立即同步」可马上导出最新存档。</div>')
        console_note = ('<div class="notice notice-tip" data-notice="overlay-hint">'
                        '<button type="button" class="notice-x" aria-label="关闭提示" '
                        'title="关闭这条提示">×</button>'
                        '从 <b>v2.2</b> 起，进游戏后按 <b>F3</b> 即可呼出本页面；'
                        '或双击 仙友助手.exe 启用网页版。'
                        '老用户重新运行一次「一键安装.bat」即可更新。</div>'
                        ) + console_note
    update_error = str(data.get("update_error") or "").strip()
    if update_error:
        console_note = ('<div class="notice" style="border-color:#a05a2c;color:#e0a56a">%s %s</div>'
                        % (_html_escape(i18n.shell(lang, "notice_update_error")),
                           _html_escape(update_error))) + console_note
    if data.get("restart_needed"):
        console_note = ('<div class="notice" style="border-color:#3d6b8c;color:#9cc8e8">%s</div>'
                        % i18n.shell(lang, "notice_restart")) + console_note
    return (HTML_TEMPLATE.replace("__CSS__", CSS)
            .replace("__PLUGIN_CSS__", css)
            .replace("__PANELS__", _panels(tabs))
            .replace("__CONSOLE_NOTE__", console_note)
            .replace("__TITLE__", i18n.shell(lang, "title"))
            .replace("__HEADING__", i18n.shell(lang, "heading"))
            .replace("__SUB__", i18n.shell(lang, "sub"))
            .replace("__TIP__", i18n.shell(lang, "tip"))
            .replace("__LANG__", "en" if lang == "en" else "zh-CN")
            .replace("__VER__", common.APP_VERSION)
            .replace("__PLUGIN_JS__", js.replace("</script", "<\\/script"))
            .replace("__QUALITY_MAX__", str(len(QUALITY_COLORS) - 1))
            .replace("__GAMBLE_QUALITY_MAX__", str(len(GAMBLE_QUALITY_COLORS) - 1))
            .replace("__QUALITY_NAMES__", json.dumps(list(QUALITY_NAMES), ensure_ascii=False))
            .replace("__DATA__", body))


def _atomic_text(path, text):
    tmp = path + ".%s.tmp" % os.getpid()
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def disk_version():
    try:
        with open(common.OUT_VERSION, encoding="utf-8") as f:
            match = re.search(r'PROGRESS_VERSION="([0-9a-f]{64})"', f.read())
            return match.group(1) if match else ""
    except Exception:
        return ""


def write_outputs(payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    css, js = _plugin_assets()
    version = hashlib.sha256(
        (canonical + "\0" + CSS + "\0" + css + "\0" + js + "\0" + HTML_TEMPLATE + "\0"
         + common.APP_VERSION).encode("utf-8")).hexdigest()
    previous = disk_version()
    changed = version != previous or not os.path.exists(common.OUT_HTML)
    if changed:
        _atomic_text(common.OUT_HTML, build_html(payload))
        _atomic_text(common.OUT_VERSION, 'window.PROGRESS_VERSION="%s";\n' % version)
    return version, changed


def console_summary(payload):
    from . import registry
    for name in payload.get("enabled", []):
        module = payload["modules"].get(name) or {}
        text = registry.describe(name, module)
        if text:
            print(text)
        print("  来源：%s ｜ %s" % (module.get("src") or "暂无", module.get("stamp_text") or "未知"))
    for warning in payload.get("warnings") or []:
        print("提示：%s" % warning)

