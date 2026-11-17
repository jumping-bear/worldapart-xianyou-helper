# -*- coding: utf-8 -*-
"""静态页面资源与输出：CSS、HTML 模板、版本哈希与原子写入。"""
import hashlib
import json
import os
import re

from . import common, registry

CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}body{background:#0e1014;color:#e8eaed;font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding:26px 20px 60px}.wrap{max-width:1180px;margin:0 auto}h1{font-size:23px;font-weight:600;letter-spacing:.5px}.sub,.source{color:#8b93a1;font-size:12px;line-height:1.8}.sub{margin-top:6px}.tabs{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 16px}.tab{border:1px solid #29303c;background:#171a21;color:#9aa3b2;border-radius:9px;padding:9px 18px;cursor:pointer;font-size:14px;white-space:nowrap}.tab.active{background:#263b34;border-color:#3d735b;color:#c9f5dd}.panel{display:none}.panel.active{display:block}.source{margin-bottom:14px}.cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0 22px}.card{background:#171a21;border:1px solid #232833;border-radius:12px;padding:13px 17px;min-width:145px}.card .k{color:#8b93a1;font-size:12px}.card .v{font-size:21px;font-weight:600;margin-top:4px}.card .v span{font-size:12px;color:#8b93a1;font-weight:400}table{width:100%;border-collapse:separate;border-spacing:0 8px}th{text-align:left;color:#7d8593;font-size:12px;font-weight:500;padding:0 12px}td{background:#15181f;padding:12px;vertical-align:middle}tr.row td:first-child{border-radius:10px 0 0 10px}tr.row td:last-child{border-radius:0 10px 10px 0}.who{font-size:15px;font-weight:600}.bed,.muted{color:#7d8593;font-size:12px;margin-top:3px}.parts{display:flex;gap:24px;flex-wrap:wrap}.part .pl{color:#9aa3b2;font-size:12px;margin-bottom:6px}.dots{display:flex;gap:4px}.dot{width:18px;height:18px;border-radius:5px;background:#252b36;display:flex;align-items:center;justify-content:center;font-size:10px;color:#5d6675}.dot.on{background:#2f7d54;color:#c9f5dd}.dot.miss{background:#3a2126;color:#a45d6b}.bar{height:6px;border-radius:3px;background:#232833;overflow:hidden;margin-top:8px}.bar i{display:block;height:100%;background:linear-gradient(90deg,#3ddc84,#2f9e6b)}.pct{font-variant-numeric:tabular-nums;font-weight:600;font-size:15px;text-align:right}.pct small{display:block;color:#7d8593;font-weight:400;font-size:11px;margin-top:2px}.full{color:#3ddc84}.badge{display:inline-block;margin-left:5px;padding:1px 6px;border-radius:6px;background:#242a34;color:#9aa3b2;font-size:10px;font-weight:400;vertical-align:middle}.badge.dao{background:#27374a;color:#b9d9ff}.filters{display:grid;grid-template-columns:2fr repeat(4,1fr);gap:9px;margin:14px 0}.filters input,.filters select{width:100%;background:#15181f;border:1px solid #29303c;border-radius:8px;color:#e8eaed;padding:9px 10px;font-size:12px;outline:none}.filters input:focus,.filters select:focus{border-color:#527c69}.filters .wide{grid-column:span 2}.result-info{color:#8b93a1;font-size:12px;margin:10px 2px 14px}.npc{background:#15181f;border:1px solid #232833;border-radius:10px;margin:0 0 8px;overflow:hidden}.npc summary{cursor:pointer;padding:12px 14px;list-style:none;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.npc summary::-webkit-details-marker{display:none}.npc summary:before{content:"›";color:#6f7787;font-size:20px;transform:rotate(0);transition:.15s}.npc[open] summary:before{transform:rotate(90deg)}.npc summary .location{margin-left:auto;color:#8b93a1;font-size:12px}.slots{border-top:1px solid #232833;padding:4px 14px 12px}.slot{padding:11px 0;border-bottom:1px solid #20252e}.slot:last-child{border-bottom:0}.slot-head{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.talent-name{font-size:14px;font-weight:600}.lock{margin-left:auto;font-size:11px;color:#b98289}.lock.on{color:#6edda2}.effect{color:#b4bdca;font-size:12px;line-height:1.7;margin-top:6px}.condition{color:#7d8593;font-size:11px;line-height:1.7;margin-top:4px}.q1{color:#9fd6a9}.q2{color:#82baf5}.q3{color:#c7a1ef}.q4{color:#e8c76d}.q5{color:#e88b82}.empty{background:#171a21;border:1px dashed #303846;border-radius:10px;padding:28px;text-align:center;color:#8b93a1;font-size:13px}.warnings{margin:12px 0;color:#c9a976;font-size:12px;line-height:1.8}.tip{margin-top:24px;color:#6f7787;font-size:12px;line-height:1.9}@media(max-width:850px){.filters{grid-template-columns:repeat(2,1fr)}.filters .wide{grid-column:span 2}.parts{gap:12px}.npc summary .location{margin-left:0;width:100%}}@media(max-width:560px){body{padding:18px 10px 40px}.filters{grid-template-columns:1fr}.filters .wide{grid-column:span 1}td{padding:9px 6px}.dot{width:15px;height:15px}.cards{gap:8px}.card{min-width:130px}}
"""
CSS += r"""
.talent-group{background:#15181f;border:1px solid #293140;border-radius:12px;margin:0 0 14px;overflow:hidden}.talent-head{padding:17px 18px}.talent-title{font-size:19px;font-weight:650;margin-right:7px}.talent-effect{color:#e0e6ed;background:#1b2029;border-left:3px solid #d4b45f;border-radius:5px;font-size:14px;line-height:1.85;margin-top:12px;padding:10px 12px}.talent-extra{color:#8f99a8;font-size:12px;line-height:1.7;margin-top:7px}.owners{border-top:1px solid #252c37;padding:9px 12px 12px}.owners-label{color:#8b93a1;font-size:11px;margin:3px 3px 8px}.owner{background:#11151b;margin-bottom:7px}.owner:last-child{margin-bottom:0}.owner summary{padding:11px 12px}.owner .slots{background:#15181f}.slot.focus{background:#1b2923;border-left:3px solid #55c78b;padding-left:10px}.slot.focus .talent-name{color:#8ee6b3}mark{background:#66551e;color:#fff0ae;border-radius:3px;padding:0 2px}.result-hint{color:#778292;font-size:11px;margin:-6px 2px 13px}@media(max-width:560px){.talent-head{padding:14px 12px}.talent-title{font-size:17px}.owners{padding:8px}.owner summary .location{width:auto;margin-left:auto}.owner .badge.hide-mobile{display:none}}
"""
CSS += r"""
.search-panel{background:#171b23;border:1px solid #293140;border-radius:12px;padding:15px;margin:16px 0 12px}.search-fields{display:grid;grid-template-columns:1fr 1fr;gap:14px}.search-field>span,.filter-field>span,.advanced-grid label>span{display:block;color:#aeb8c7;font-size:12px;margin:0 0 7px}.search-field:first-child>span{color:#d9c785}.search-field input,.filter-field select,.advanced-grid select{width:100%;background:#10141a;border:1px solid #303949;border-radius:8px;color:#e8eaed;padding:11px 12px;font-size:13px;outline:none}.search-field input:focus,.filter-field select:focus,.advanced-grid select:focus{border-color:#698c78;box-shadow:0 0 0 2px #263b34}.search-field input::placeholder{color:#667182}.filter-bar{display:grid;grid-template-columns:minmax(150px,1fr) minmax(190px,1.35fr) auto;align-items:end;gap:12px;margin:0 2px 14px}.filter-actions{display:flex;gap:8px}.filter-button{background:#1b222c;border:1px solid #35404f;border-radius:8px;color:#c6cfda;padding:10px 14px;min-height:40px;cursor:pointer;white-space:nowrap;font-size:12px}.filter-button:hover{background:#25303d;border-color:#526175}.filter-button.primary{color:#e2d7ac;border-color:#655d3d}.filter-count{color:#e8c76d}.advanced-filters{background:#141820;border:1px solid #293140;border-radius:10px;margin:0 0 14px;padding:0 13px}.advanced-filters summary{cursor:pointer;list-style:none;color:#9da8b7;font-size:12px;padding:11px 1px}.advanced-filters summary::-webkit-details-marker{display:none}.advanced-filters summary:before{content:"›";display:inline-block;margin-right:7px;transition:.15s}.advanced-filters[open] summary:before{transform:rotate(90deg)}.advanced-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;border-top:1px solid #252c37;padding:13px 0 15px}.owner summary .location{line-height:1.6;text-align:right}.category-badge{color:#d8c78f}.search-note{color:#758092;font-size:11px;margin:10px 2px 0}@media(max-width:850px){.filter-bar{grid-template-columns:1fr 1fr}.filter-actions{grid-column:span 2}.advanced-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.owner summary .location{text-align:left}}@media(max-width:560px){.search-panel{padding:12px}.search-fields,.filter-bar,.advanced-grid{grid-template-columns:1fr}.filter-actions{grid-column:span 1}.filter-button{flex:1}.owner summary .location{width:100%;text-align:left}}
"""
CSS += r"""
.item-group{background:#15181f;border:1px solid #293140;border-radius:12px;margin:0 0 14px;overflow:hidden}.item-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:11px 12px 0}.sortbtn{background:#1b222c;border:1px solid #35404f;border-radius:7px;color:#9aa3b2;padding:5px 11px;font-size:11px;cursor:pointer}.sortbtn:hover{background:#25303d}.sortbtn.on{background:#263b34;border-color:#3d735b;color:#c9f5dd}.item-tools .meta{margin-left:auto;color:#778292;font-size:11px}.ratebar{width:62px;height:5px;border-radius:3px;background:#232833;overflow:hidden;display:inline-block;vertical-align:middle;margin-left:6px}.ratebar i{display:block;height:100%;background:#4fbf83}.badge.deadly{background:#3a2126;color:#e88b82}.loadmore{display:block;width:calc(100% - 24px);margin:8px 12px 12px;background:#1b222c;border:1px dashed #35404f;border-radius:8px;color:#9aa3b2;padding:9px;font-size:12px;cursor:pointer}.loadmore:hover{background:#25303d;color:#c6cfda}.steal-detail{flex-basis:100%;color:#8b93a1;font-size:11px;line-height:1.7;margin-top:2px}.steal-detail b{color:#b4bdca;font-weight:600}.steal-detail .bad{color:#e88b82}.npc-card .slots{padding:0 14px 12px}.appver{color:#7d8797;font-size:12px;font-weight:500;vertical-align:middle;margin-left:4px}.item-group>summary{list-style:none;cursor:pointer}.item-group>summary::-webkit-details-marker{display:none}.item-arrow{color:#6f7787;font-size:17px;transition:.15s;display:inline-block}.item-group[open] .item-arrow{transform:rotate(90deg)}.item-head{padding:16px 18px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.item-title{font-size:19px;font-weight:650}.item-stat{margin-left:auto;color:#8b93a1;font-size:12px}.owner .badge.steal{background:#22392e;color:#8ee6b3}.owner .badge.nosteal{background:#2a2d33;color:#8b93a1}.steal-ok{color:#6edda2;font-size:12px;font-weight:600}.steal-risk{color:#e88b82}.filter-bar.four{grid-template-columns:minmax(140px,1fr) minmax(165px,1.3fr) minmax(125px,1fr) auto}@media(max-width:850px){.filter-bar.four{grid-template-columns:1fr 1fr}.filter-bar.four .filter-actions{grid-column:span 2}}@media(max-width:560px){.filter-bar.four{grid-template-columns:1fr}.filter-bar.four .filter-actions{grid-column:span 1}.item-head{padding:13px 12px}.item-title{font-size:17px}.item-stat{margin-left:0;width:100%}}
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
.pill-list{max-height:380px;overflow:auto;border:1px solid #232833;border-radius:10px;background:#141820}
.pill-item{display:flex;gap:8px;align-items:center;padding:9px 11px;border-bottom:1px solid #1e242d;cursor:pointer;font-size:12px}
.pill-item:hover{background:#1b222c}
.pill-item .dotmark{width:8px;height:8px;border-radius:50%;flex:none}
.pill-item .nm{flex:1;color:#d5dce6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pill-item .tp{color:#7d8593;font-size:11px}
.pill-item.done .nm{color:#6f7787;text-decoration:line-through}
.pill-detail{background:#15181f;border:1px solid #293140;border-radius:10px;padding:11px 13px;font-size:12px;line-height:1.8;color:#b4bdca;min-height:52px}
.pill-detail b{color:#e8eaed}
.legend{display:flex;gap:12px;flex-wrap:wrap;color:#8b93a1;font-size:11px}
.legend span{display:flex;align-items:center;gap:4px}
.legend i{width:8px;height:8px;border-radius:50%;display:inline-block}
@media(max-width:850px){.pill-grid{grid-template-columns:1fr}}
.manual{margin-top:14px;border:1px solid #232833;border-radius:10px;background:#141820;overflow:hidden}
.manual-head{display:flex;justify-content:space-between;align-items:baseline;padding:11px 13px;background:#171b23;color:#d5dce6;font-size:13px}
.manual-head span{color:#7d8593;font-size:11px;font-weight:400}
.manual-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px;padding:11px}
.manual-item{display:flex;gap:7px;align-items:center;flex-wrap:wrap;background:#181d25;border:1px solid #242c37;border-radius:9px;padding:9px 11px;font-size:12px;cursor:pointer}
.manual-item:hover{border-color:#3d735b}
.manual-item .nm{color:#dfe6ef;font-weight:600;margin-right:auto}
.manual-item .tag{color:#86909e;font-size:11px;background:#1d232c;border-radius:6px;padding:2px 6px}
.fsec{background:#141820;border:1px solid #232b36;border-radius:10px;padding:9px 11px 11px}
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
.pgonly{margin-left:auto;background:#1b222c;border:1px solid #2b3340;color:#8b93a1;border-radius:10px;padding:2px 8px;font-size:11px;cursor:pointer;font-family:inherit}
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
.fproto,.fart{background:#15181f;border:1px solid #232833;border-radius:10px;margin:0 0 8px;overflow:hidden}
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
.fchip{background:#1a2029;border:1px solid #2b3340;border-radius:7px;padding:2px 8px;font-size:11px;color:#b4bdca}
.fq0{color:#cfd6df}.fq1{color:#9fd6a9}.fq2{color:#82baf5}.fq3{color:#c7a1ef}.fq4{color:#e8c76d}
.fgap{color:#e8a17c}.fok{color:#6edda2}.fmat{color:#b4bdca;font-size:12px;line-height:1.7}
@media(max-width:560px){.ftiers,.fstat{margin-left:0;width:100%}}
"""

CSS += r"""
.evgroup{display:flex;align-items:center;gap:8px;margin:20px 2px 9px;color:#cfd8e3;font-size:13px;font-weight:600}
.evgroup span{color:#778292;font-weight:400;font-size:11px}
.ev{background:#15181f;border:1px solid #232833;border-radius:10px;margin:0 0 8px;overflow:hidden}
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
.eend{background:#12161c;border:1px solid #212836;border-radius:9px;padding:10px 12px;margin-top:8px}
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
.epath{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:#9aa3b2;font-size:11px;line-height:1.7;margin-top:8px;background:#101720;border:1px solid #1f2b3a;border-radius:7px;padding:6px 8px}
.psteps{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.parrow{color:#6f9ec9;font-size:13px;font-weight:700}
.pstep{display:inline-flex;align-items:center;gap:5px;color:#d5dee8;background:#18222d;border-radius:6px;padding:2px 7px 2px 3px}
.pstep i{font-style:normal;display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;border-radius:50%;background:#2d4a63;color:#cfe8ff;font-size:10px}
.efchips{display:flex;gap:6px;flex-wrap:wrap}
.efchip{display:inline-flex;align-items:center;height:22px;box-sizing:border-box;background:#1a2029;border:1px solid #2b3340;border-radius:7px;padding:0 8px;font-size:11px;color:#b4bdca}
.efchip i{font-style:normal;color:#7d8593;margin-left:5px}
.efchip .q{font-size:10px;color:#7d8593;margin-left:4px}
.efchip.got{border-color:#3d735b;background:#1a2a22}
.efchip.fq1{background:#18261c;border-color:#31543c;color:#a8dfb4}
.efchip.fq2{background:#172330;border-color:#2f4e69;color:#a6cff0}
.efchip.fq3{background:#221a2e;border-color:#4a3566;color:#cbb2ee}
.efchip.fq4{background:#2b2415;border-color:#65552a;color:#f0d38a}
.efchip.fq5{background:#2e1a1a;border-color:#6b3232;color:#f0a6a6}
.badge.ok{background:#22392e;color:#8ee6b3}.badge.off{background:#2a2d33;color:#8b93a1}.badge.warn{background:#3a3226;color:#e8c76d}
.badge.loc-exact{background:#22392e;color:#8ee6b3}.badge.loc-inferred{background:#333026;color:#e8c76d}.badge.loc-unknown{background:#2a2d33;color:#8b93a1}
.event-chips{margin:0 0 10px}
@media(max-width:560px){.evloc{margin-left:0;width:100%}.evbody{padding:10px 12px 12px}}
.charline{background:#141820;border:1px solid #232b36;border-radius:10px;padding:9px 13px;color:#b4bdca;font-size:12px;line-height:1.8;margin:0 0 12px}
.charline b{color:#e8eaed}
.notice{background:#16202b;border:1px solid #2d4356;border-radius:8px;color:#a9c4d8;font-size:12px;line-height:1.8;padding:8px 11px;margin:0 0 10px}
.notice b{color:#d7e9f7}
.card .s{color:#778292;font-size:11px;margin-top:3px}
.small{font-size:11px}
.badge.score{background:#2c2a1f;color:#e8c76d}
.reasons{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 8px}
.reason{background:#1d232c;border:1px solid #2b3340;border-radius:7px;padding:2px 8px;font-size:11px;color:#c9d2df}
.reason.use{background:#17242c;border-color:#2d4f5f;color:#a9dbe8}
.itemdesc{color:#9aa3b2;font-size:12px;line-height:1.8;margin:2px 0 8px;background:#10141a;border-radius:7px;padding:7px 9px}
.itemdesc b{color:#c9d2df;font-weight:600}
.itemselect{background:#15181f;border:1px solid #29303c;border-radius:8px;color:#e8eaed;padding:5px 9px;font-size:12px;outline:none;min-height:28px}
.itemselect:focus{border-color:#527c69}
.cchip{display:inline-flex;align-items:center;gap:4px;border-radius:7px;padding:2px 7px;font-size:11px;background:#242a34;color:#9aa3b2;border:1px solid #2b3340;line-height:1.6}
.cchip.ok{background:#1a2a22;border-color:#3d735b;color:#8ee6b3}
.cchip.bad{background:#2e1d21;border-color:#6b3a44;color:#e88b82}
.condopts{display:flex;flex-direction:column;gap:5px;margin-top:5px}
.condopt{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.condname{color:#c9d2df;font-size:11px;background:#1b222c;border-radius:6px;padding:2px 7px;max-width:100%}
.effchip{display:inline-block;border-radius:7px;padding:2px 7px;font-size:11px;background:#1b2230;color:#9fc3e8;border:1px solid #2b3a4d}
.etree{margin-top:10px;border:1px solid #232833;border-radius:9px;background:#12161c;overflow:hidden}
.etree>summary{cursor:pointer;padding:9px 12px;color:#b9c6d6;font-size:12px;list-style:none}
.etree>summary::-webkit-details-marker{display:none}
.etree>summary:before{content:"›";display:inline-block;margin-right:6px;transition:.15s}
.etree[open]>summary:before{transform:rotate(90deg)}
.treewrap{padding:4px 12px 12px;border-top:1px solid #20252e}
.tnode{border-left:2px solid #2b3a33;padding:6px 0 2px 10px;margin-top:6px}
.ttext{color:#9aa3b2;font-size:11px;line-height:1.7;background:#0f1319;border-radius:6px;padding:5px 7px}
.topt{display:flex;align-items:center;gap:6px;flex-wrap:wrap;color:#d5dce6;font-size:12px;margin-top:6px;background:#151b23;border:1px solid #232c38;border-radius:7px;padding:5px 8px}
.topt b{color:#e8eaed;font-weight:600}
.tarrow{color:#6f9ec9;font-weight:700}
.topt.picked{border-color:#3d735b;background:#152019}
.topt.picked b{color:#8ee6b3}
.topt.picked b:before{content:"已选 ";color:#6edda2;font-size:10px}
.tbranch{margin-left:14px;border-left:1px dashed #2b3340;padding-left:8px}
.tend{color:#9aa3b2;font-size:12px;margin-top:6px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;background:#101720;border-radius:6px;padding:5px 8px}
.tend b{color:#e8eaed}
.tloop{color:#778292;font-size:11px;margin-top:5px}
.jumpbtn{background:#2d4a63;border:1px solid #4f7fa6;color:#d7efff;border-radius:7px;padding:4px 11px;font-size:11px;cursor:pointer;font-weight:600;white-space:nowrap}
.jumpbtn:hover{background:#3a5f7e;color:#fff}
.jumpbtn:after{content:" →"}
.ev.flash{animation:evflash 1.6s ease-out}
@keyframes evflash{0%{box-shadow:0 0 0 2px #4f7fa6;background:#1a2530}100%{box-shadow:0 0 0 0 transparent}}
.fq5{color:#f0a6a6}
.qgroup{display:flex;align-items:center;gap:8px;margin:20px 2px 9px;color:#cfd8e3;font-size:13px;font-weight:600}
.qgroup .gmeta{margin-left:auto;color:#778292;font-weight:400;font-size:11px}
.qline{color:#b4bdca;font-size:12px;line-height:1.9;margin-top:6px}
.qline b{color:#d9c785;margin-right:7px;font-weight:600}
.qchain{border:1px solid #232833;border-radius:10px;margin:10px 0;background:#12171f;overflow:hidden}
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
.qsechd:before{content:"";width:3px;height:11px;border-radius:2px;background:#3d735b;flex:none}
.qsechd i{margin-left:auto;font-style:normal;color:#6f7787}
.qwalk .qstep{border-left-color:#2f6b4c}
.qstep>summary{flex-wrap:wrap}
.qstep .qact{font-size:11px;color:#8fd0a9}
.rwline{display:flex;gap:5px;flex-wrap:wrap;align-items:center;margin-left:2px}
.rwq{font-size:11px;padding:1px 6px;border-radius:5px;background:#1c222c;border:1px solid #2b3441;color:#c3cbd7;white-space:nowrap}
.rwq.f1{color:#a8dfb4;border-color:#33513f}.rwq.f2{color:#a6cff0;border-color:#2e455c}
.rwq.f3{color:#cbb2ee;border-color:#453a5c}.rwq.f4{color:#f0d38a;border-color:#5a4c2a}
.rwq.f5{color:#f0a6a6;border-color:#5c3535}.rwq.more{color:#7d8593}
.rwstone{font-size:11px;color:#e8c76d}
.qitemdescs{margin:4px 0 8px;display:flex;flex-direction:column;gap:6px}
.qitemdesc{background:#10141a;border:1px solid #222a35;border-radius:7px;padding:6px 9px;font-size:12px;line-height:1.7;color:#9aa3b2}
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

HTML_TEMPLATE = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>不问凡尘 · 仙友助手</title><style>__CSS__ __PLUGIN_CSS__ </style></head><body><div class="wrap"><h1>不问凡尘 · 仙友助手 <span class="appver">v__VER__</span></h1><div class="sub">只读分析解密副本，不修改游戏存档；筛选条件会保留在本机浏览器。</div><div id="warnings" class="warnings"></div><div id="tabs" class="tabs"></div>__PANELS__<div class="tip">游戏保存后按 F8 可立即导出副本，平时插件每 60 秒自动同步。本页仅在数据变化时自动刷新。<br>配置来源优先使用游戏当前 YooAsset 清单；更新失败时使用兼容缓存或内置快照。若存档结构、加密或 Unity 格式大改，仍需更新工具。</div></div><script src="仙友助手版本.js"></script><script>
const INITIAL_VERSION=window.PROGRESS_VERSION||'';const DATA=__DATA__;
const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const store={get(k,d){try{const v=localStorage.getItem(k);return v===null?d:JSON.parse(v)}catch(e){return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
const labels=Object.assign({bedroom:'仙居楼互动',talent:'NPC天赋',items:'NPC物品',pill:'炼丹',forge:'炼器',event:'奇遇',quest:'支线'},DATA.labels||{});let active=store.get('worldapart.active.tab.v2',DATA.enabled[0]||'');if(!DATA.enabled.includes(active))active=DATA.enabled[0]||'';
function sourceHtml(m){return `<div class="source">存档：${esc(m.src||'暂无')} ｜ 原始更新：${esc(m.stamp_text)} ｜ 配置：${esc(m.config)}${m.config_warning?' ｜ '+esc(m.config_warning):''}</div>`}
function showTab(name){active=name;store.set('worldapart.active.tab.v2',name);document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===name));document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.tab===name))}
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
for(const [key,view] of Object.entries(window.PROGRESS_VIEWS||{})){if(!DATA.enabled.includes(key)||typeof view!=='function')continue;try{view(DATA)}catch(e){console.error('模块 '+key+' 渲染失败',e)}}

let polledVersion=INITIAL_VERSION;setInterval(()=>{const script=document.createElement('script');script.src='仙友助手版本.js?t='+Date.now();script.onload=()=>{const next=window.PROGRESS_VERSION||'';if(next&&next!==polledVersion){location.reload();return}polledVersion=next||polledVersion;script.remove()};script.onerror=()=>script.remove();document.head.appendChild(script)},3000);
</script></body></html>"""


def _panels(tabs):
    return "".join(
        '<section id="%s" class="panel"></section>' % re.sub(r"[^0-9A-Za-z_-]", "", str(item.get("key") or ""))
        for item in tabs if item.get("key"))


def _plugin_assets():
    return registry.assets_css(), registry.assets_js()


def build_html(payload):
    tabs = payload.get("tabs") or [{"key": key} for key in payload.get("enabled") or ()]
    data = dict(payload)
    labels = dict(data.get("labels") or {})
    for item in tabs:
        key = str(item.get("key") or "")
        if key:
            labels.setdefault(key, str(item.get("label") or key))
    if labels:
        data["labels"] = labels
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    body = body.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    css, js = _plugin_assets()
    return (HTML_TEMPLATE.replace("__CSS__", CSS)
            .replace("__PLUGIN_CSS__", css)
            .replace("__PANELS__", _panels(tabs))
            .replace("__VER__", common.APP_VERSION)
            .replace("__PLUGIN_JS__", js.replace("</script", "<\\/script"))
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

