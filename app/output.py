# -*- coding: utf-8 -*-
"""静态页面资源与输出：CSS、HTML 模板、版本哈希与原子写入。"""
import hashlib
import json
import os
import re

from . import common

CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}body{background:#0e1014;color:#e8eaed;font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;padding:26px 20px 60px}.wrap{max-width:1180px;margin:0 auto}h1{font-size:23px;font-weight:600;letter-spacing:.5px}.sub,.source{color:#8b93a1;font-size:12px;line-height:1.8}.sub{margin-top:6px}.tabs{display:flex;gap:8px;margin:20px 0 16px}.tab{border:1px solid #29303c;background:#171a21;color:#9aa3b2;border-radius:9px;padding:9px 18px;cursor:pointer;font-size:14px}.tab.active{background:#263b34;border-color:#3d735b;color:#c9f5dd}.panel{display:none}.panel.active{display:block}.source{margin-bottom:14px}.cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0 22px}.card{background:#171a21;border:1px solid #232833;border-radius:12px;padding:13px 17px;min-width:145px}.card .k{color:#8b93a1;font-size:12px}.card .v{font-size:21px;font-weight:600;margin-top:4px}.card .v span{font-size:12px;color:#8b93a1;font-weight:400}table{width:100%;border-collapse:separate;border-spacing:0 8px}th{text-align:left;color:#7d8593;font-size:12px;font-weight:500;padding:0 12px}td{background:#15181f;padding:12px;vertical-align:middle}tr.row td:first-child{border-radius:10px 0 0 10px}tr.row td:last-child{border-radius:0 10px 10px 0}.who{font-size:15px;font-weight:600}.bed,.muted{color:#7d8593;font-size:12px;margin-top:3px}.parts{display:flex;gap:24px;flex-wrap:wrap}.part .pl{color:#9aa3b2;font-size:12px;margin-bottom:6px}.dots{display:flex;gap:4px}.dot{width:18px;height:18px;border-radius:5px;background:#252b36;display:flex;align-items:center;justify-content:center;font-size:10px;color:#5d6675}.dot.on{background:#2f7d54;color:#c9f5dd}.dot.miss{background:#3a2126;color:#a45d6b}.bar{height:6px;border-radius:3px;background:#232833;overflow:hidden;margin-top:8px}.bar i{display:block;height:100%;background:linear-gradient(90deg,#3ddc84,#2f9e6b)}.pct{font-variant-numeric:tabular-nums;font-weight:600;font-size:15px;text-align:right}.pct small{display:block;color:#7d8593;font-weight:400;font-size:11px;margin-top:2px}.full{color:#3ddc84}.badge{display:inline-block;margin-left:5px;padding:1px 6px;border-radius:6px;background:#242a34;color:#9aa3b2;font-size:10px;font-weight:400;vertical-align:middle}.badge.dao{background:#27374a;color:#b9d9ff}.filters{display:grid;grid-template-columns:2fr repeat(4,1fr);gap:9px;margin:14px 0}.filters input,.filters select{width:100%;background:#15181f;border:1px solid #29303c;border-radius:8px;color:#e8eaed;padding:9px 10px;font-size:12px;outline:none}.filters input:focus,.filters select:focus{border-color:#527c69}.filters .wide{grid-column:span 2}.result-info{color:#8b93a1;font-size:12px;margin:10px 2px 14px}.npc{background:#15181f;border:1px solid #232833;border-radius:10px;margin:0 0 8px;overflow:hidden}.npc summary{cursor:pointer;padding:12px 14px;list-style:none;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.npc summary::-webkit-details-marker{display:none}.npc summary:before{content:"›";color:#6f7787;font-size:20px;transform:rotate(0);transition:.15s}.npc[open] summary:before{transform:rotate(90deg)}.npc summary .location{margin-left:auto;color:#8b93a1;font-size:12px}.slots{border-top:1px solid #232833;padding:4px 14px 12px}.slot{padding:11px 0;border-bottom:1px solid #20252e}.slot:last-child{border-bottom:0}.slot-head{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.talent-name{font-size:14px;font-weight:600}.lock{margin-left:auto;font-size:11px;color:#b98289}.lock.on{color:#6edda2}.effect{color:#b4bdca;font-size:12px;line-height:1.7;margin-top:6px}.condition{color:#7d8593;font-size:11px;line-height:1.7;margin-top:4px}.q1{color:#9fd6a9}.q2{color:#82baf5}.q3{color:#c7a1ef}.q4{color:#e8c76d}.q5{color:#e88b82}.empty{background:#171a21;border:1px dashed #303846;border-radius:10px;padding:28px;text-align:center;color:#8b93a1;font-size:13px}.warnings{margin:12px 0;color:#c9a976;font-size:12px;line-height:1.8}.tip{margin-top:24px;color:#6f7787;font-size:12px;line-height:1.9}@media(max-width:850px){.filters{grid-template-columns:repeat(2,1fr)}.filters .wide{grid-column:span 2}.parts{gap:12px}.npc summary .location{margin-left:0;width:100%}}@media(max-width:560px){body{padding:18px 10px 40px}.filters{grid-template-columns:1fr}.filters .wide{grid-column:span 1}td{padding:9px 6px}.dot{width:15px;height:15px}.cards{gap:8px}.card{min-width:130px}}
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
.eend{background:#12161c;border:1px solid #212836;border-radius:8px;padding:10px 12px;margin-top:8px}
.eend.got{border-color:#3d735b;background:#131d18}
.eend-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.egrade{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;border-radius:6px;font-size:11px;background:#242a34;color:#9aa3b2;padding:0 4px}
.egrade.g1{background:#22392e;color:#8ee6b3}.egrade.g2{background:#27374a;color:#b9d9ff}.egrade.g3{background:#3a2126;color:#e88b82}
.eend-title{font-size:13px;font-weight:600}
.eend-sum{color:#9aa3b2;font-size:12px;line-height:1.75;margin-top:5px}
.eend-detail{color:#c9a976;font-size:11px;line-height:1.7;margin-top:4px}
.efchips{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}
.efchip{background:#1a2029;border:1px solid #2b3340;border-radius:7px;padding:3px 8px;font-size:11px;color:#b4bdca}
.efchip i{font-style:normal;color:#7d8593;margin-left:5px}
.efchip.got{border-color:#3d735b;background:#1a2a22}
.badge.ok{background:#22392e;color:#8ee6b3}.badge.off{background:#2a2d33;color:#8b93a1}.badge.warn{background:#3a3226;color:#e8c76d}
.badge.loc-exact{background:#22392e;color:#8ee6b3}.badge.loc-inferred{background:#333026;color:#e8c76d}.badge.loc-unknown{background:#2a2d33;color:#8b93a1}
.event-chips{margin:0 0 10px}
@media(max-width:560px){.evloc{margin-left:0;width:100%}.evbody{padding:10px 12px 12px}}
"""

HTML_TEMPLATE = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>不问凡尘 · 仙友助手</title><style>__CSS__</style></head><body><div class="wrap"><h1>不问凡尘 · 仙友助手 <span class="appver">v__VER__</span></h1><div class="sub">只读分析解密副本，不修改游戏存档；筛选条件会保留在本机浏览器。</div><div id="warnings" class="warnings"></div><div id="tabs" class="tabs"></div><section id="bedroom" class="panel"></section><section id="talent" class="panel"></section><section id="items" class="panel"></section><section id="pill" class="panel"></section><section id="forge" class="panel"></section><section id="event" class="panel"></section><div class="tip">游戏保存后按 F8 可立即导出副本，平时插件每 60 秒自动同步。本页仅在数据变化时自动刷新。<br>配置来源优先使用游戏当前 YooAsset 清单；更新失败时使用兼容缓存或内置快照。若存档结构、加密或 Unity 格式大改，仍需更新工具。</div></div><script src="仙友助手版本.js"></script><script>
const INITIAL_VERSION=window.PROGRESS_VERSION||'';const DATA=__DATA__;
const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const store={get(k,d){try{const v=localStorage.getItem(k);return v===null?d:JSON.parse(v)}catch(e){return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
const labels={bedroom:'仙居楼互动',talent:'NPC天赋',items:'NPC物品',pill:'炼丹',forge:'炼器',event:'奇遇'};let active=store.get('worldapart.active.tab.v2',DATA.enabled[0]||'');if(!DATA.enabled.includes(active))active=DATA.enabled[0]||'';
function sourceHtml(m){return `<div class="source">存档：${esc(m.src||'暂无')} ｜ 原始更新：${esc(m.stamp_text)} ｜ 配置：${esc(m.config)}${m.config_warning?' ｜ '+esc(m.config_warning):''}</div>`}
function showTab(name){active=name;store.set('worldapart.active.tab.v2',name);document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===name));document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.tab===name))}
function initTabs(){$('tabs').innerHTML=DATA.enabled.map(n=>`<button class="tab" data-tab="${n}">${labels[n]}</button>`).join('');document.querySelectorAll('.tab').forEach(x=>x.onclick=()=>showTab(x.dataset.tab));if(!DATA.enabled.length){$('warnings').innerHTML=DATA.warnings.map(esc).join('<br>');return}showTab(active)}
function renderBedroom(){const m=DATA.modules.bedroom;if(!m)return;const rows=m.rows||[],done=rows.filter(r=>r.total>=18).length;const goals=[[1,'十八摸Ⅰ'],[3,'十八摸Ⅱ'],[5,'十八摸Ⅲ'],[10,'十八摸Ⅳ']];let cards=`<div class="card"><div class="k">已完成 18/18</div><div class="v">${done} <span>位</span></div></div>`;for(const [n,name] of goals)cards+=`<div class="card"><div class="k">${name}</div><div class="v">${done>=n?'已达成':'还差 '+(n-done)+' 位'}</div></div>`;const body=rows.map(r=>{const parts=r.parts.map(p=>`<div class="part"><div class="pl">${esc(p.label)}</div><div class="dots">${Array.from({length:6},(_,i)=>`<i class="dot ${p.got.includes(i)?'on':'miss'}">${i}</i>`).join('')}</div></div>`).join('');const pct=Math.min(100,Math.floor(r.total*100/18));return `<tr class="row"><td><div class="who">${esc(r.who)}${r.resident?'':'<span class="badge">未入住</span>'}</div><div class="bed">${esc(r.bed)}</div></td><td><div class="parts">${parts}</div></td><td style="width:150px"><div class="pct ${r.total>=18?'full':''}">${r.total}/18<small>${r.total>=18?'已完成':'进行中'}</small></div><div class="bar"><i style="width:${pct}%"></i></div></td></tr>`}).join('');$('bedroom').innerHTML=sourceHtml(m)+`<div class="cards">${cards}</div>${rows.length?`<table><thead><tr><th>仙友 / 寝室</th><th>各部位 6 段</th><th></th></tr></thead><tbody>${body}</tbody></table>`:'<div class="empty">暂无仙居楼互动数据</div>'}<div class="tip">仙居楼互动：进入仙居楼与入住的仙友互动，每位仙友 3 个部位、每个部位 6 段（0~3 为四段升阶，4 为循环段，5 为回落段）；18/18 才算 1 位，对应成就「十八摸 Ⅰ~Ⅳ」。</div>`}
const FILTER_KEY='worldapart.talent.filters.v3';
const FILTER_DEFAULTS={q:'',npc:'',region:'',location:'',category:'',quality:'',realm:'',unlocked:'',dao:''};
let filters=Object.assign({},FILTER_DEFAULTS,store.get('worldapart.talent.filters.v2',{}),store.get(FILTER_KEY,{}));
function uniq(values){return [...new Set(values)].sort((a,b)=>{const an=Number(a),bn=Number(b);if(a!==''&&b!==''&&!Number.isNaN(an)&&!Number.isNaN(bn))return an-bn;return String(a).localeCompare(String(b),'zh-CN')})}
function catValue(t){return t.category===null||t.category===undefined||t.category===''?'':String(t.category)}
function categoryLabel(t){const value=catValue(t),name=t.category_name||'';return value?(name?`${name}（${value}）`:`分类 ${value}`):'未分类'}
function initTalent(){
 const m=DATA.modules.talent;if(!m)return;
 const talents=m.talents||[],regions=uniq(m.rows.map(r=>r.region||r.location||'未知区域'));
 const categories=uniq(talents.map(catValue)),qualities=uniq(talents.map(t=>t.quality==null?'':String(t.quality))),realms=uniq(talents.map(t=>String(t.realm_id??0)));
 const opts=(values,kind)=>`<option value="">全部${kind}</option>`+values.map(v=>{
  let label=v,value=v;
  if(kind==='分类'){const sample=talents.find(t=>catValue(t)===v)||{category:v};label=v?categoryLabel(sample):'未分类';value=v||'__uncategorized__'}
  if(kind==='品质'){label=v?`品质 ${v}`:'未知品质';value=v||'__unknown__'}
  if(kind==='境界')label=(m.realms||{})[v]||`境界 ${v}`;
  return `<option value="${esc(value)}">${esc(label)}</option>`
 }).join('');
 const advancedKeys=['category','quality','realm','unlocked','dao'];
 const advancedCount=advancedKeys.filter(key=>filters[key]!=='').length;
 $('talent').innerHTML=sourceHtml(m)+`
  <div class="search-panel"><div class="search-fields">
   <label class="search-field"><span>找天赋</span><input id="fq" placeholder="输入天赋名称、效果、悬停或触发描述" value="${esc(filters.q)}"></label>
   <label class="search-field"><span>找 NPC（可选）</span><input id="fnpc" placeholder="输入 NPC 名称，与天赋条件叠加" value="${esc(filters.npc)}"></label>
  </div></div>
  <div class="filter-bar">
   <label class="filter-field"><span>区域</span><select id="fregion">${opts(regions,'区域')}</select></label>
   <label class="filter-field"><span>具体位置</span><select id="flocation"></select></label>
   <div class="filter-actions"><button type="button" id="fclear" class="filter-button">清空筛选</button></div>
  </div>
  <details id="fadvanced" class="advanced-filters"${advancedCount?' open':''}><summary>更多筛选 <span id="fadvancedcount" class="filter-count">${advancedCount?`（${advancedCount}）`:''}</span></summary><div class="advanced-grid">
   <label><span>天赋分类</span><select id="fcategory">${opts(categories,'分类')}</select></label>
   <label><span>天赋品质</span><select id="fquality">${opts(qualities,'品质')}</select></label>
   <label><span>天赋境界</span><select id="frealm">${opts(realms,'境界')}</select></label>
   <label><span>解锁状态</span><select id="funlocked"><option value="">全部解锁状态</option><option value="1">已解锁</option><option value="0">未解锁</option></select></label>
   <label><span>同道状态</span><select id="fdao"><option value="">全部同道状态</option><option value="1">已同道</option><option value="0">未同道</option></select></label>
  </div></details>
  <div id="tresult" class="result-info"></div><div id="tlist"></div>`;
 function updateLocations(){
  const locations=uniq(m.rows.filter(r=>!filters.region||(r.region||r.location||'未知区域')===filters.region).map(r=>r.location||'未知地点'));
  if(filters.location&&!locations.includes(filters.location))filters.location='';
  $('flocation').innerHTML=opts(locations,'具体位置');$('flocation').value=filters.location||'';
 }
 function updateAdvancedCount(){const count=advancedKeys.filter(key=>filters[key]!=='').length;$('fadvancedcount').textContent=count?`（${count}）`:''}
 function saveAndRender(){store.set(FILTER_KEY,filters);updateAdvancedCount();renderTalentList()}
 $('fregion').value=filters.region||'';
 updateLocations();
 for(const key of ['q','npc','location','category','quality','realm','unlocked','dao']){
  const node=$('f'+key);node.value=filters[key]??'';
  node.addEventListener(node.tagName==='INPUT'?'input':'change',()=>{filters[key]=node.value;saveAndRender()})
 }
 $('fregion').addEventListener('change',()=>{filters.region=$('fregion').value;updateLocations();saveAndRender()});
 $('fclear').addEventListener('click',()=>{filters=Object.assign({},FILTER_DEFAULTS);store.set(FILTER_KEY,filters);initTalent()});
 renderTalentList();
}
function hi(value,q){
 const text=String(value??'');if(!q)return esc(text);const lower=text.toLowerCase();let at=0,out='',found;
 while((found=lower.indexOf(q,at))>=0){out+=esc(text.slice(at,found))+'<mark>'+esc(text.slice(found,found+q.length))+'</mark>';at=found+q.length}
 return out+esc(text.slice(at));
}
function talentText(t){return [t.name,t.effect,t.hover,t.trigger].map(v=>String(v||'')).join('\n').toLowerCase()}
function talentBadges(t,m){const quality=t.quality==null?'未知品质':`品质 ${t.quality}`,cat=categoryLabel(t),realm=(m.realms||{})[String(t.realm_id??0)]||`境界 ${t.realm_id??0}`;return `<span class="badge">${esc(quality)}</span><span class="badge category-badge">${esc(cat)}</span><span class="badge">${esc(realm)}</span>`}
function talentMatchesFilters(t,s){
 if(filters.category==='__uncategorized__'&&catValue(t)!=='')return false;
 if(filters.category&&filters.category!=='__uncategorized__'&&catValue(t)!==filters.category)return false;
 if(filters.quality==='__unknown__'&&t.quality!=null)return false;
 if(filters.quality&&filters.quality!=='__unknown__'&&String(t.quality??'')!==filters.quality)return false;
 if(filters.realm!==''&&String(t.realm_id??0)!==filters.realm)return false;
 return filters.unlocked===''||String(s.unlocked?1:0)===filters.unlocked;
}
function talentSlotHtml(s,t,m,focus,q){
 const name=t.name||`天赋 #${s.talent_id}`;
 const req=s.required_realm?`<div class="condition">槽位要求：${esc((m.realms||{})[String(s.required_realm)]||('境界 '+s.required_realm))}</div>`:'';
 const conditions=(s.conditions||[]).length?`<div class="condition">解锁条件：${s.conditions.map(esc).join('；')}</div>`:'';
 return `<div class="slot${focus?' focus':''}"><div class="slot-head"><span class="muted">槽位 ${esc(s.slot_id??'?')}</span><span class="talent-name q${esc(t.quality??0)}">${hi(name,q)}</span>${talentBadges(t,m)}<span class="lock ${s.unlocked?'on':''}">${s.unlocked?'已解锁':'未解锁'}</span></div><div class="effect">${hi(t.effect||'暂无效果说明',q)}</div>${req}${conditions}</div>`;
}
function renderTalentList(){
 const m=DATA.modules.talent,talentMap=Object.fromEntries((m.talents||[]).map(t=>[String(t.id),t]));
 const q=filters.q.trim().toLowerCase(),npcQ=filters.npc.trim().toLowerCase();
 const groups={},npcSet=new Set();let slotCount=0;
 for(const row of m.rows){
  if(filters.region&&(row.region||row.location||'未知区域')!==filters.region)continue;
  if(filters.location&&(row.location||'未知地点')!==filters.location)continue;
  if(filters.dao!==''&&String(row.dao?1:0)!==filters.dao)continue;
  const npcText=[row.who,row.title].map(v=>String(v||'')).join('\n').toLowerCase();
  if(npcQ&&!npcText.includes(npcQ))continue;
  for(const s of row.slots||[]){
   const t=talentMap[String(s.talent_id)]||{},name=t.name||`天赋 #${s.talent_id}`,text=talentText(t);
   if(q&&!text.includes(q))continue;
   if(!talentMatchesFilters(t,s))continue;
   const rank=!q?0:name.toLowerCase().includes(q)?0:String(t.effect||'').toLowerCase().includes(q)?1:text.includes(q)?2:3;
   const key=String(s.talent_id);
   if(!groups[key])groups[key]={t,name,owners:[],rank};
   else groups[key].rank=Math.min(groups[key].rank,rank);
   groups[key].owners.push({row,s});npcSet.add(row.uid);slotCount++;
  }
 }
 const sorted=Object.values(groups).sort((a,b)=>a.rank-b.rank||Number(b.t.quality||0)-Number(a.t.quality||0)||a.name.localeCompare(b.name,'zh-CN'));
 const cards=sorted.map(group=>{
  const t=group.t,extras=[];
  if(t.hover)extras.push(`<div class="talent-extra">${hi('悬停说明：'+t.hover,q)}</div>`);
  if(t.trigger)extras.push(`<div class="talent-extra">${hi('触发说明：'+t.trigger,q)}</div>`);
  const owners=group.owners.sort((a,b)=>Number(b.row.dao)-Number(a.row.dao)||a.row.who.localeCompare(b.row.who,'zh-CN')).map(({row,s})=>{
   const all=(row.slots||[]).map(slot=>talentSlotHtml(slot,talentMap[String(slot.talent_id)]||{},m,String(slot.talent_id)===String(s.talent_id),q)).join('');
   const location=row.location_path||row.location||'未知地点';
   return `<details class="npc owner"><summary><span class="who">${hi(row.who,npcQ)}</span>${row.dao?'<span class="badge dao">已同道</span>':'<span class="badge">未同道</span>'}<span class="badge hide-mobile">全部 ${row.slots.length} 项天赋</span><span class="badge">槽位 ${esc(s.slot_id??'?')}</span><span class="lock ${s.unlocked?'on':''}">${s.unlocked?'已解锁':'未解锁'}</span><span class="location">${esc(location)}</span></summary><div class="slots">${all}</div></details>`;
  }).join('');
  return `<article class="talent-group"><div class="talent-head"><span class="talent-title q${esc(t.quality??0)}">${hi(group.name,q)}</span>${talentBadges(t,m)}<div class="talent-effect">${hi(t.effect||'暂无效果说明',q)}</div>${extras.join('')}</div><div class="owners"><div class="owners-label">${group.owners.length} 位 NPC 拥有此天赋；点击 NPC 可展开其全部天赋，当前天赋已高亮</div>${owners}</div></article>`;
 });
 $('tresult').textContent=`筛选结果：${sorted.length} 项天赋，${npcSet.size} 位 NPC，${slotCount} 条槽位记录（共 ${m.rows.length} 位有天赋记录）`;
 $('tlist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合组合筛选条件的天赋</div>';
}
const ITEM_KEY='worldapart.item.filters.v1';
const ITEM_DEFAULTS={q:'',npc:'',region:'',location:'',type:'',quality:'',steal:'',demand:''};
let itemFilters=Object.assign({},ITEM_DEFAULTS,store.get(ITEM_KEY,{}));
let itemCache=null;
let itemRenderState={groups:{},q:'',npcQ:''};
let itemSort=store.get('worldapart.item.sort.v1','rate');
let itemPage={};
function itemRateOf(o){return o.v.ok&&o.t.steal?o.t.steal.rate:-1}
function itemSortOwners(owners){
 const list=owners.slice();
 list.sort((a,b)=>{
  const okDiff=Number(b.v.ok)-Number(a.v.ok);
  if(okDiff)return okDiff;
  if(itemSort==='count'&&b.count!==a.count)return b.count-a.count;
  const rateDiff=itemRateOf(b)-itemRateOf(a);
  if(itemSort!=='name'&&rateDiff)return rateDiff;
  if(itemSort==='rate'&&b.count!==a.count)return b.count-a.count;
  return String(a.row.who).localeCompare(String(b.row.who),'zh-CN');
 });
 return list;
}
function stealDetailHtml(rule){
 if(!rule)return '';
 const parts=['一次最多 <b>'+rule.count+'</b> 个','善恶值 <b>'+rule.alignment+'</b>','好感 <b>'+rule.intimacy+'</b>'];
 if(rule.kill)parts.push('<span class="bad">失手触发击杀</span>');
 return '<span class="steal-detail">'+parts.join(' · ')+'</span>';
}
function itemOwnersHtml(iid){
 const state=itemRenderState,group=state.groups[iid];
 if(!group)return '';
 const all=itemSortOwners(group.owners);
 const limit=30*(itemPage[iid]||1),shown=all.slice(0,limit),rest=all.length-shown.length;
 const owners=shown.map(o=>{
  const badge=o.v.ok?'<span class="badge steal">可偷</span>':'<span class="badge nosteal">'+esc(o.v.label)+'</span>';
  let rate='';
  if(o.v.ok&&o.t.steal){
   rate='<span class="steal-ok">'+o.t.steal.rate+'%<span class="ratebar"><i style="width:'+Math.max(0,Math.min(100,o.t.steal.rate))+'%"></i></span></span>';
   if(o.t.steal.kill)rate+='<span class="badge deadly">致命</span>';
  }
  const inPool=(o.row.demand||[]).some(id=>String(id)===String(iid));
  const demandBadge=!inPool?'':(o.t.demand?'<span class="badge demand">索要 -'+esc(o.t.demand_cost||0)+' 好感</span>':'<span class="badge demand-absent">不可索要</span>');
  return '<details class="npc owner" data-uid="'+esc(o.row.uid)+'" data-item="'+esc(iid)+'"><summary><span class="who">'+hi(o.row.who,state.npcQ)+'</span>'+(o.row.realm?'<span class="badge">'+esc(o.row.realm)+'</span>':'')+badge+demandBadge+'<span class="badge">×'+esc(o.count)+'</span>'+rate+'<span class="location">'+esc(o.row.location_path||o.row.location||'未知地点')+'</span>'+stealDetailHtml(o.v.ok?o.t.steal:null)+'</summary><div class="slots"></div></details>';
 }).join('');
 const blocked=all.filter(o=>!o.v.ok).length;
 const labels={rate:'按成功率从高到低',count:'按持有数量从多到少',name:'按 NPC 名称排序'};
 const tools='<div class="item-tools">'
  +['rate','count','name'].map(k=>'<button type="button" class="sortbtn'+(itemSort===k?' on':'')+'" data-sort="'+k+'">'+({rate:'成功率',count:'数量',name:'名称'})[k]+'</button>').join('')
  +'<span class="meta">'+esc(labels[itemSort]||labels.rate)+'</span></div>';
 const head='<div class="owners-label">'+group.stealable+' 位可偷'+(blocked?' · '+blocked+' 位不可偷':'')+'；点击 NPC 可在下方展开其全部持有物品</div>';
 const more=rest?'<button type="button" class="loadmore" data-more="'+esc(iid)+'">显示更多（还有 '+rest+' 位）</button>':'';
 return tools+head+owners+more;
}
function itemIndex(){
 const m=DATA.modules.items;
 if(!itemCache||itemCache.m!==m)itemCache={m:m,cat:Object.fromEntries((m.catalog||[]).map(t=>[String(t.id),t])),rows:new Map(m.rows.map(r=>[r.uid,r]))};
 return itemCache;
}
function itemVerdict(row,t){
 if(!row.can_steal)return{ok:false,label:'NPC 不可偷'};
 if(!t.steal)return{ok:false,label:'物品不可偷'};
 return{ok:true,label:'可偷'};
}
function itemRate(group){
 const rates=group.owners.filter(o=>o.v.ok&&o.t.steal).map(o=>o.t.steal.rate);
 return rates.length?rates.reduce((a,b)=>a+b,0)/rates.length:0;
}
function intimacyName(row){
 const tiers=(DATA.modules.items.intimacy||[]);
 let name='';
 for(const t of tiers){if(row.intimacy!=null&&row.intimacy>=t.need)name=t.name}
 return name;
}
function npcItemsHtml(uid,focus){
 const idx=itemIndex(),row=idx.rows.get(uid);
 if(!row)return '';
 const cat=idx.cat;
 const list=(row.items||[]).map(pair=>{
  const t=cat[String(pair[0])]||{name:'物品 #'+pair[0],quality:0,type:''};
  return{o:t,t:t,count:pair[1]||1,v:itemVerdict(row,t)};
 });
 list.sort((a,b)=>Number(b.v.ok)-Number(a.v.ok)||String(a.t.name).localeCompare(String(b.t.name),'zh-CN'));
 const bagIds=new Set(list.map(o=>String(o.t.id)));
 const focusId=focus!==undefined&&focus!==null?String(focus):'';
 const stealRows=list.map(o=>{
  const rule=o.t.steal,verdict=o.v.ok?'<span class="steal-ok">可偷</span>':'<span class="muted">'+esc(o.v.label)+'</span>';
  const current=focusId&&String(o.t.id)===focusId;
  const effect=o.v.ok&&rule?'<div class="effect">成功率 '+rule.rate+'% · 一次最多 '+rule.count+' 个 · 善恶值 '+rule.alignment+' · 好感 '+rule.intimacy+(rule.kill?' · <span class="steal-risk">失手触发击杀</span>':'')+'</div>':'';
  return '<div class="slot'+(current?' focus':'')+'"><div class="slot-head"><span class="talent-name q'+esc(o.t.quality??0)+'">'+esc(o.t.name)+'</span>'+(current?'<span class="badge steal">当前物品</span>':'')+'<span class="badge">×'+esc(o.count)+'</span><span class="badge">'+esc(o.t.type||'未分类')+'</span>'+verdict+'</div>'+effect+'</div>';
 }).join('');
 const demands=(row.demand||[]).map(id=>{
  const key=String(id),t=cat[key]||{name:'物品 #'+key,quality:0,type:''};
  return{t:t};
 });
 demands.sort((a,b)=>Number(!!b.t.demand)-Number(!!a.t.demand)||(a.t.demand_cost||0)-(b.t.demand_cost||0)||String(a.t.name).localeCompare(String(b.t.name),'zh-CN'));
 const demandRows=demands.map(o=>{
  const ok=!!o.t.demand,current=focusId&&String(o.t.id)===focusId;
  const absent=bagIds.has(String(o.t.id))?'':'<span class="badge demand-absent">不在背包</span>';
  const value=ok?'<span class="badge demand">好感 -'+esc(o.t.demand_cost||0)+'</span>':'<span class="badge nosteal">不可索要</span>';
  return '<div class="slot'+(current?' focus':'')+'"><div class="slot-head"><span class="talent-name q'+esc(o.t.quality??0)+'">'+esc(o.t.name)+'</span>'+absent+'<span class="badge">品质 '+esc(o.t.quality??'未知')+'</span>'+value+'</div></div>';
 }).join('');
 const fav=row.intimacy!=null?'<div class="item-sec-note">好感 '+esc(row.intimacy)+(intimacyName(row)?'（'+esc(intimacyName(row))+'）':'')+' · 无好感门槛 · 每周期 1 次 · 消耗不随境界折算</div>':'';
 return '<div class="item-sec"><div class="item-sec-head"><span>偷取</span><span class="meta">'+list.length+' 件 · 来自他的背包</span></div>'+(stealRows||'<div class="empty">他目前没有持有物品</div>')+'</div>'
  +'<div class="item-sec"><div class="item-sec-head"><span>索要</span><span class="meta">'+demands.length+' 件 · 来自索要模板</span></div>'+fav+(demandRows||'<div class="empty">这个 NPC 没有索要模板</div>')+'</div>';
}
function renderItemList(){
 itemPage={};
 const m=DATA.modules.items,idx=itemIndex();
 const q=itemFilters.q.trim().toLowerCase(),npcQ=itemFilters.npc.trim().toLowerCase();
 const groups={},npcSet=new Set();let pairCount=0;
 for(const row of m.rows){
  if(itemFilters.region&&(row.region||'未知区域')!==itemFilters.region)continue;
  if(itemFilters.location&&(row.location||'未知地点')!==itemFilters.location)continue;
  if(npcQ&&!((row.who+' '+(row.realm||'')).toLowerCase().includes(npcQ)))continue;
  for(const pair of row.items||[]){
   const iid=String(pair[0]),t=idx.cat[iid];
   if(!t)continue;
   if(q&&!String(t.name).toLowerCase().includes(q))continue;
   if(itemFilters.type&&(t.type||'未分类')!==(itemFilters.type==='__none__'?'未分类':itemFilters.type))continue;
   if(itemFilters.quality==='__unknown__'&&t.quality!=null)continue;
   if(itemFilters.quality&&itemFilters.quality!=='__unknown__'&&String(t.quality??'')!==itemFilters.quality)continue;
   const v=itemVerdict(row,t);
   if(itemFilters.steal==='1'&&!v.ok)continue;
   if(itemFilters.steal==='0'&&v.ok)continue;
   if(itemFilters.demand==='1'&&!((row.demand||[]).some(id=>String(id)===iid)&&t.demand))continue;
   if(!groups[iid])groups[iid]={t:t,owners:[],stealable:0,total:0};
   groups[iid].owners.push({row:row,t:t,count:pair[1]||1,v:v});
   groups[iid].total+=pair[1]||1;
   if(v.ok){groups[iid].stealable++;const rate=t.steal?t.steal.rate:0;if(rate>(groups[iid].bestRate||0))groups[iid].bestRate=rate;}
   npcSet.add(row.uid);pairCount++;
  }
 }
 const npcMode=!q&&!!npcQ;
 if(npcMode){
  const npcs={};
  for(const row of m.rows){
   if(itemFilters.region&&(row.region||'未知区域')!==itemFilters.region)continue;
   if(itemFilters.location&&(row.location||'未知地点')!==itemFilters.location)continue;
   if(!(row.who+' '+(row.realm||'')).toLowerCase().includes(npcQ))continue;
   for(const pair of row.items||[]){
    const iid=String(pair[0]),t=idx.cat[iid];
    if(!t)continue;
    if(itemFilters.type&&(t.type||'未分类')!==(itemFilters.type==='__none__'?'未分类':itemFilters.type))continue;
    if(itemFilters.quality==='__unknown__'&&t.quality!=null)continue;
    if(itemFilters.quality&&itemFilters.quality!=='__unknown__'&&String(t.quality??'')!==itemFilters.quality)continue;
    const v=itemVerdict(row,t);
    if(itemFilters.steal==='1'&&!v.ok)continue;
    if(itemFilters.steal==='0'&&v.ok)continue;
    if(itemFilters.demand==='1'&&!((row.demand||[]).some(id=>String(id)===iid)&&t.demand))continue;
    if(!npcs[row.uid])npcs[row.uid]={row:row,items:0,stealable:0,demandable:(row.demand||[]).filter(did=>{const dt=idx.cat[String(did)];return dt&&dt.demand}).length};
    npcs[row.uid].items++;
    if(v.ok)npcs[row.uid].stealable++;
   }
  }
  const list=Object.values(npcs).sort((a,b)=>b.stealable-a.stealable||b.items-a.items||String(a.row.who).localeCompare(String(b.row.who),'zh-CN'));
  const cards=list.map(g=>'<details class="item-group npc-card" data-uid="'+esc(g.row.uid)+'"><summary class="item-head"><span class="item-arrow">›</span><span class="item-title">'+hi(g.row.who,npcQ)+'</span>'+(g.row.realm?'<span class="badge">'+esc(g.row.realm)+'</span>':'')+'<span class="badge steal">可偷 '+g.stealable+' 件</span>'+(g.demandable?'<span class="badge demand">可索要 '+g.demandable+' 件</span>':'')+'<span class="item-stat">共 '+g.items+' 件 · '+esc(g.row.location_path||g.row.location||'未知地点')+'</span></summary><div class="slots"></div></details>');
  itemRenderState={groups:{},q:q,npcQ:npcQ};
  $('iresult').textContent='筛选结果：'+list.length+' 位 NPC，'+list.reduce((sum,g)=>sum+g.items,0)+' 件物品（正在按 NPC 查看，清空 NPC 搜索即回到物品列表）';
  $('ilist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合条件的 NPC</div>';
  return;
 }
 const sorted=Object.values(groups).sort((a,b)=>b.stealable-a.stealable||itemRate(b)-itemRate(a)||String(a.t.name).localeCompare(String(b.t.name),'zh-CN'));
 const cards=sorted.map(group=>{
  const stat='可偷 '+group.stealable+' 处'+(group.bestRate?' · 最高 '+group.bestRate+'%':'')+' · 共 '+group.total+' 个';
  return '<details class="item-group" data-item="'+esc(group.t.id)+'"><summary class="item-head"><span class="item-arrow">›</span><span class="item-title q'+esc(group.t.quality??0)+'">'+hi(group.t.name,q)+'</span><span class="badge">'+esc(group.t.type||'未分类')+'</span><span class="badge">品质 '+esc(group.t.quality??'未知')+'</span><span class="item-stat">'+stat+'</span></summary><div class="owners"></div></details>';
 });
 itemRenderState={groups:Object.fromEntries(sorted.map(g=>[String(g.t.id),g])),q:q,npcQ:npcQ};
 $('iresult').textContent='筛选结果：'+sorted.length+' 种物品，'+npcSet.size+' 位 NPC，'+pairCount+' 条持有记录（共 '+m.rows.length+' 位 NPC 持有物品）';
 $('ilist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合条件的物品</div>';
}
function initItems(){
 const m=DATA.modules.items;if(!m)return;
 const catalog=m.catalog||[],regions=uniq(m.rows.map(r=>r.region||'未知区域'));
 const types=uniq(catalog.map(t=>t.type||'未分类'));
 const qualities=uniq(catalog.map(t=>t.quality==null?'':String(t.quality)));
 const opts=(values,kind)=>'<option value="">全部'+kind+'</option>'+values.map(v=>{
  let label=v,value=v;
  if(kind==='类型'){label=v||'未分类';value=v||'__none__'}
  if(kind==='品质'){label=v?'品质 '+v:'未知品质';value=v||'__unknown__'}
  return '<option value="'+esc(value)+'">'+esc(label)+'</option>'
 }).join('');
 $('items').innerHTML=sourceHtml(m)+`
  <style>
  .item-sec{margin-top:14px;border-top:1px solid #2a3340;padding-top:10px}
  .item-sec-head{display:flex;align-items:baseline;gap:8px;margin:2px 0 4px;font-size:13px;font-weight:600}
  .item-sec-head .meta{font-weight:400;color:#8b93a1;font-size:12px}
  .item-sec-note{font-size:12px;color:#8b93a1;margin:0 0 6px}
  .badge.demand{background:rgba(110,221,162,.14);color:#6edda2;border:1px solid rgba(110,221,162,.35)}
  .badge.demand-absent{background:transparent;color:#8b93a1;border:1px dashed #4a5563}
  </style>
  <div class="search-panel"><div class="search-fields">
   <label class="search-field"><span>找物品</span><input id="iq" placeholder="输入物品名称" value="${esc(itemFilters.q)}"></label>
   <label class="search-field"><span>找 NPC（可选）</span><input id="inpc" placeholder="输入 NPC 名称，与物品条件叠加" value="${esc(itemFilters.npc)}"></label>
  </div></div>
  <div class="filter-bar four">
   <label class="filter-field"><span>区域</span><select id="iregion">${opts(regions,'区域')}</select></label>
   <label class="filter-field"><span>具体位置</span><select id="ilocation"></select></label>
   <label class="filter-field"><span>偷窃</span><select id="isteal"><option value="">全部持有者</option><option value="1">只看可偷</option><option value="0">只看不可偷</option></select></label>
   <label class="filter-field"><span>索要</span><select id="idemand"><option value="">全部物品</option><option value="1">只看可索要</option></select></label>
   <div class="filter-actions"><button type="button" id="iclear" class="filter-button">清空筛选</button></div>
  </div>
  <details id="iadvanced" class="advanced-filters"><summary>更多筛选 <span id="iadvancedcount" class="filter-count"></span></summary><div class="advanced-grid">
   <label><span>物品类型</span><select id="itype">${opts(types,'类型')}</select></label>
   <label><span>物品品质</span><select id="iquality">${opts(qualities,'品质')}</select></label>
  </div></details>
  <div id="iresult" class="result-info"></div><div id="ilist"></div>`;
 const advancedKeys=['type','quality'];
 function updateCount(){const count=advancedKeys.filter(key=>itemFilters[key]!=='').length;$('iadvancedcount').textContent=count?`（${count}）`:''}
 function updateItemLocations(){
  const locations=uniq(m.rows.filter(r=>!itemFilters.region||(r.region||'未知区域')===itemFilters.region).map(r=>r.location||'未知地点'));
  if(itemFilters.location&&!locations.includes(itemFilters.location))itemFilters.location='';
  $('ilocation').innerHTML=opts(locations,'具体位置');$('ilocation').value=itemFilters.location||'';
 }
 function saveAndRender(){store.set(ITEM_KEY,itemFilters);updateCount();renderItemList()}
 $('iregion').value=itemFilters.region||'';updateItemLocations();
 for(const key of ['q','npc','location','type','quality','steal','demand']){
  const node=$('i'+key);node.value=itemFilters[key]??'';
  node.addEventListener(node.tagName==='INPUT'?'input':'change',()=>{itemFilters[key]=node.value;saveAndRender()});
 }
 $('iregion').addEventListener('change',()=>{itemFilters.region=$('iregion').value;updateItemLocations();saveAndRender()});
 $('iclear').addEventListener('click',()=>{itemFilters=Object.assign({},ITEM_DEFAULTS);store.set(ITEM_KEY,itemFilters);initItems()});
 updateCount();renderItemList();
}
document.addEventListener('toggle',event=>{
 const node=event.target;
 if(!node||!node.classList||!node.open||!node.closest('#items'))return;
 if(node.classList.contains('npc-card')){
  const slots=node.querySelector('.slots');
  if(slots&&!slots.dataset.filled){slots.dataset.filled='1';slots.innerHTML=npcItemsHtml(node.dataset.uid)}
  return;
 }
 if(node.classList.contains('item-group')){
  const owners=node.querySelector('.owners');
  if(owners&&!owners.dataset.filled){owners.dataset.filled='1';owners.innerHTML=itemOwnersHtml(node.dataset.item)}
  return;
 }
 if(node.classList.contains('owner')){
  const box=node.querySelector('.slots');
  if(!box||box.dataset.filled)return;
  box.dataset.filled='1';
  box.innerHTML=npcItemsHtml(node.dataset.uid,node.dataset.item);
 }
},true);
function refreshItemOwners(iid){
 const nodes=document.querySelectorAll('#items .item-group');
 for(const node of nodes){
  if(node.dataset.item!==String(iid))continue;
  const box=node.querySelector('.owners');
  if(!box)return;
  box.dataset.filled='1';
  box.innerHTML=itemOwnersHtml(String(iid));
  return;
 }
}
document.addEventListener('click',event=>{
 if(!event.target.closest('#items'))return;
 const more=event.target.closest('[data-more]');
 if(more){
  const iid=more.dataset.more;
  itemPage[iid]=(itemPage[iid]||1)+1;
  refreshItemOwners(iid);
  return;
 }
 const sort=event.target.closest('[data-sort]');
 if(sort){
  itemSort=sort.dataset.sort;
  store.set('worldapart.item.sort.v1',itemSort);
  document.querySelectorAll('#items .item-group[open]').forEach(node=>refreshItemOwners(node.dataset.item));
 }
});
const PILL_COLOR={1:'#e8c76d',2:'#ff7b72',3:'#6edda2',4:'#6aa9ff',5:'#d18bff',6:'#9a7bff'};
const PILL_TYPE={1:'丹方属性',2:'丹方',3:'减毒',4:'奖励',5:'传送口',6:'传送口'};
const PILL_ELEMENT=['无','金','木','水','火','土'];
const PILL_ELEMENT_COLOR=['#8b93a1','#e6dcae','#8ccf92','#7fc0ee','#ee9a86','#d8b273'];
const PILL_TYPES={recipe:[2],effect:[1],cleanse:[3],reward:[4],portal:[5,6]};
const PILL_TYPE_LABEL={recipe:'丹方',effect:'丹方属性',cleanse:'减毒',reward:'奖励',portal:'传送口'};
const PILL_KEYWORDS=['攻击','暴击','生命','破韧','防御','速度','灵力','伤害','净化','复活','修为','灼烧','共鸣','同道','灵气'];
const PILL_ORDER=['recipe','effect','cleanse','reward','portal','other'];
const PILL_FILTER_KEY='worldapart.pill.filters.v3';
const PILL_DEFAULTS={types:Object.keys(PILL_TYPES),elements:['1','2','3','4','5'],tiers:[],keywords:[],q:'',hideDone:false};
// 未知类型（游戏新增拾取物）自动归入「其他」，不会从筛选里消失
let PILL_GROUPS=PILL_TYPES,PILL_LABELS=PILL_TYPE_LABEL;
let pillFilter=Object.assign({},PILL_DEFAULTS,store.get(PILL_FILTER_KEY,{}));
if(!Array.isArray(pillFilter.types))pillFilter.types=PILL_DEFAULTS.types.slice();
if(!Array.isArray(pillFilter.elements))pillFilter.elements=PILL_DEFAULTS.elements.slice();
if(!Array.isArray(pillFilter.tiers))pillFilter.tiers=[];
if(!Array.isArray(pillFilter.keywords))pillFilter.keywords=[];
function poiFill(p){
 return p[1]===2?(PILL_ELEMENT_COLOR[p[2]]||PILL_COLOR[2]):(PILL_COLOR[p[1]]||'#9aa3b0');
}
function pillName(p,mp){const t=p[1];
 if(t===2){const id=(mp.pool||[])[p[5]]||'';const r=(mp.recipes||{})[id];return (r&&r.n)||('丹方 '+id)}
 if(t===1){const e=(mp.effects||{})[String(p[4])];return e?e[0]:('药效 '+p[4])}
 if(t===3)return '减毒';
 if(t===4){const r=(mp.rewards||{})[String(p[8])];return r?r[0]:('奖励 '+p[8])}
 if(t===5||t===6){const pt=(mp.portals||{})[String(p[10])];return pt?pt[0]:('传送门 '+p[10])}
 return (PILL_LABELS.other||'其他')+' ('+t+')'}
function pillDesc(p,mp){
 if(p[1]===1){const e=(mp.effects||{})[String(p[4])];return e?`${e[3]}　拾取经验 ${e[4]}`:''}
 if(p[1]===4){const r=(mp.rewards||{})[String(p[8])];return r?`${r[3]}　价值 ${r[4]}~${r[5]}`:''}
 if(p[1]>=5){const pt=(mp.portals||{})[String(p[10])];return pt?pt[3]:''}
 if(p[1]===3)return '拾取后削减丹毒';
 return ''}
function pillText(p,mp){
 if(p[1]===2){const r=(mp.recipes||{})[String((mp.pool||[])[p[5]]||'')];return r?r.d||'':''}
 if(p[1]===1){const e=(mp.effects||{})[String(p[4])];return e?e[3]||'':''}
 return '';
}
function portalCost(mp,cfg){
 const pt=(mp.portals||{})[String(cfg)];
 if(!pt)return '';
 return pt[5]?`${pt[4]||'妖丹'} ×${pt[5]}`:'无需妖丹';
}
function initPill(){
 const m=DATA.modules&&DATA.modules.pill;if(!m)return;const host=$('pill');
 const st=m.rows||{},maps=(st.map&&st.map.maps)||[];
 if(!maps.length){host.innerHTML=sourceHtml(m)+'<div class="empty">暂无炼丹盘面数据</div>';return}
 const pick=parseInt(store.get('worldapart.pill.map.v1',0),10)||0;
 const mp=maps[pick>=0&&pick<maps.length?pick:0];
 const cols=mp.cols,rowsN=mp.rows,ts=mp.tile_size||20,consumed=new Set(st.consumed||[]);
 const learned=new Set((st.manual||[]).map(r=>String(r.id)));
 const compById=new Map();(mp.pois||[]).forEach((p,i)=>compById.set(p[0],(mp.comps||[])[i]));
 // 游戏新增拾取物类型时不再被筛掉，统一落到「其他」
 const extra=[...new Set(mp.pois.map(p=>p[1]).filter(t=>PILL_COLOR[t]===undefined))].sort((a,b)=>a-b);
 if(extra.length){
  PILL_LABELS=Object.assign({},PILL_TYPE_LABEL,{other:'其他'});
  PILL_GROUPS=Object.assign({},PILL_TYPES,{other:extra});
  if(!pillFilter.types.includes('other'))pillFilter.types=pillFilter.types.concat('other');
 }else{PILL_LABELS=PILL_TYPE_LABEL;PILL_GROUPS=PILL_TYPES}
 pillFilter.types=pillFilter.types.filter(k=>PILL_GROUPS[k]);
 const cards=[[`炼丹等级`,`${st.level||0} 级`,`经验 ${st.exp||0}`],
  [`炉火`,`${st.current_furnace||0} 号炉`,`已解锁 ${st.furnace||0} 座`],
  [`丹方手记`,`${(st.manual||[]).length} / ${Object.keys(mp.recipes||{}).length} 张`,`最高 ${st.highest_grade||0} 品`],
  [`盘面拾取点`,`${mp.pois.length} 个`,`已拾取 ${consumed.size}`]]
  .map(([k,v,s])=>`<div class="card"><div class="k">${esc(k)}</div><div class="v">${esc(v)}<span> ${esc(s)}</span></div></div>`).join('');
 host.innerHTML=sourceHtml(m)+`<div class="cards">${cards}</div>`+
  (maps.length>1?`<div class="chips" id="pillmaps"><span class="chip-label">盘面</span>`+
   maps.map((x,i)=>`<button class="chip${x===mp?' on':''}" data-map="${i}">${esc(x.name)}<i>${(x.pois||[]).length}</i></button>`).join('')+`</div>`:'')+
  `<div class="pill-grid"><div class="mapbox"><canvas id="pillmap"></canvas><svg id="pillsvg" viewBox="0 0 ${cols} ${rowsN}" xmlns="http://www.w3.org/2000/svg"></svg><div class="map-tip" id="pillherbtip"></div></div>`+
  `<div class="pill-side">`+
  `<div class="fsec"><div class="fhead"><b>显示对象</b><span class="fhint">Alt+点击 独选</span>`+
   `<span class="fops"><button type="button" data-op="none" data-row="types">清</button><button type="button" data-op="all" data-row="types">全</button></span></div>`+
   `<div class="chips" id="pillchips"></div></div>`+
  `<div class="fsec" id="pillcond"><div class="fhead"><b>筛选条件</b><span class="fhint">仅作用于丹方 / 丹方属性</span></div>`+
   `<div class="frow"><span class="chip-label">五行</span><div class="chips" id="pillelems"></div>`+
    `<span class="fops"><button type="button" data-op="none" data-row="elements">清</button><button type="button" data-op="all" data-row="elements">全</button></span></div>`+
   `<div class="frow"><span class="chip-label">阶数</span><div class="chips" id="pilltiers"></div>`+
    `<span class="fops"><button type="button" data-op="none" data-row="tiers">清</button><button type="button" data-op="all" data-row="tiers">全</button></span></div>`+
   `<div class="frow"><span class="chip-label">药效</span><div class="chips" id="pillkeys"></div>`+
    `<span class="fops"><button type="button" data-op="none" data-row="keywords">清</button></span></div>`+
  `</div>`+
  `<div class="fsec"><div class="fhead"><b>视图</b></div><div class="chips" id="pillview"></div></div>`+
  `<input id="pillq" class="pill-search" placeholder="搜索名称 / 丹方药效 / 奖励说明">`+
  `<div class="pill-active" id="pillactive"></div>`+
  `<div class="pill-detail" id="pillinfo">点击盘面上的标记或右侧结果查看详情</div>`+
  `<div class="pill-sum" id="pillsum"></div>`+
  `<div class="pill-list" id="pilllist"></div>`+
  `<div class="legend">${[1,3,4,5].map(t=>`<span><i style="background:${PILL_COLOR[t]}"></i>${PILL_TYPE[t]}</span>`).join('')}${[1,2,3,4,5].map(t=>`<span><i style="background:${PILL_ELEMENT_COLOR[t]}"></i>${PILL_ELEMENT[t]}丹方</span>`).join('')}<span><i style="background:#5a4a36"></i>山</span><span><i style="background:#26414a"></i>沼泽</span></div></div></div>`+
  `<div class="manual"><div class="manual-head">丹方手记<span>已学会 ${(st.manual||[]).length} 张 · 点击定位盘面</span></div><div class="manual-list" id="pillmanual"></div></div>`+
  `<div class="tip">盘面为游戏内置固定地图（${cols}×${rowsN} 格，每格 ${ts} 单位），并非随机生成；带删除线的拾取点表示本存档已拾取过。「迷雾」开启后只显示已探索区域，落在迷雾里的拾取点会一起隐藏。「药材路线」默认关闭，打开后显示盘面自带的 ${(mp.trajectories||[]).length} 条药材分布轨迹，鼠标停在线路上才会显示药材名。</div>`;
 // 地形
 const cv=$('pillmap');cv.width=cols;cv.height=rowsN;
 const ctx=cv.getContext('2d');const img=ctx.createImageData(cols,rowsN);const px=img.data;
 const palette={0:[20,18,16],1:[90,74,54],2:[38,66,74]};let i=0;
 for(const [v,c] of mp.runs){const col=palette[v]||palette[0];for(let k=0;k<c;k++){px[i]=col[0];px[i+1]=col[1];px[i+2]=col[2];px[i+3]=255;i+=4}}
 ctx.putImageData(img,0,0);
 const svg=$('pillsvg'),NS='http://www.w3.org/2000/svg';
 // 迷雾：未探索区域压暗，已探索的笔迹按半径揭开
 const strokes=(st.fog||{})[mp.name||'default']||[];
 let fogLayer=null;
 if(strokes.length){
  const defs=document.createElementNS(NS,'defs');
  const mask=document.createElementNS(NS,'mask');
  mask.setAttribute('id','pillfogmask');mask.setAttribute('maskUnits','userSpaceOnUse');
  mask.setAttribute('x','0');mask.setAttribute('y','0');
  mask.setAttribute('width',cols);mask.setAttribute('height',rowsN);
  const cover=document.createElementNS(NS,'rect');
  cover.setAttribute('x','0');cover.setAttribute('y','0');
  cover.setAttribute('width',cols);cover.setAttribute('height',rowsN);
  cover.setAttribute('fill','#000');mask.appendChild(cover);
  strokes.forEach(([seg,sx,sy,ex,ey,r])=>{
   if(seg){
    const line=document.createElementNS(NS,'line');
    line.setAttribute('x1',sx/ts);line.setAttribute('y1',sy/ts);
    line.setAttribute('x2',ex/ts);line.setAttribute('y2',ey/ts);
    line.setAttribute('stroke','#fff');line.setAttribute('stroke-width',Math.max(r*2/ts,.8));
    line.setAttribute('stroke-linecap','round');mask.appendChild(line);
   }else{
    const c=document.createElementNS(NS,'circle');
    c.setAttribute('cx',sx/ts);c.setAttribute('cy',sy/ts);
    c.setAttribute('r',Math.max(r/ts,.8));c.setAttribute('fill','#fff');mask.appendChild(c);
   }
  });
  defs.appendChild(mask);svg.appendChild(defs);
  fogLayer=document.createElementNS(NS,'rect');
  fogLayer.setAttribute('x','0');fogLayer.setAttribute('y','0');
  fogLayer.setAttribute('width',cols);fogLayer.setAttribute('height',rowsN);
  fogLayer.setAttribute('id','pillfog');
  fogLayer.setAttribute('fill','#06080a');fogLayer.setAttribute('fill-opacity','.82');
  fogLayer.setAttribute('mask','url(#pillfogmask)');
  svg.appendChild(fogLayer);
 }
 // 判断某个坐标是否在已探索范围内
 function exploredAt(x,y){
  for(let k=0;k<strokes.length;k++){
   const s=strokes[k],r=s[5];
   if(s[0]){
    const dx=s[3]-s[1],dy=s[4]-s[2],len=dx*dx+dy*dy;
    let t=len?((x-s[1])*dx+(y-s[2])*dy)/len:0;
    t=t<0?0:t>1?1:t;
    const px=s[1]+t*dx-x,py=s[2]+t*dy-y;
    if(px*px+py*py<=r*r)return true;
   }else{
    const px=x-s[1],py=y-s[2];
    if(px*px+py*py<=r*r)return true;
   }
  }
  return false;
 }
 // 药材轨迹
 const herbs=mp.herbs||{};
 const herbLayer=document.createElementNS(NS,'g');herbLayer.setAttribute('id','pillherb');
 svg.appendChild(herbLayer);
 // 药材轨迹：名字用 HTML 悬浮提示（盘面 500×500 缩放后 SVG 文字只剩几像素，没法看）
 const herbTip=$('pillherbtip');
 (mp.trajectories||[]).forEach(([hid,,,segs])=>{
  if(!segs||!segs.length)return;const pts=segs.map(s=>`${s[1]/ts},${s[2]/ts}`).join(' ');
  const name=herbs[String(hid)]||('药材 '+hid);
  const group=document.createElementNS(NS,'g');group.setAttribute('class','herb-track');
  const line=document.createElementNS(NS,'polyline');line.setAttribute('points',pts);
  line.setAttribute('fill','none');line.setAttribute('stroke','#8f7bd8');line.setAttribute('stroke-opacity','.28');
  line.setAttribute('stroke-width','.8');group.appendChild(line);
  const hit=document.createElementNS(NS,'polyline');hit.setAttribute('points',pts);
  hit.setAttribute('fill','none');hit.setAttribute('stroke','#fff');hit.setAttribute('stroke-opacity','0');
  hit.setAttribute('stroke-width','4');hit.setAttribute('pointer-events','stroke');group.appendChild(hit);
  hit.addEventListener('mouseenter',()=>{herbTip.textContent=name;herbTip.classList.add('on')});
  hit.addEventListener('mousemove',e=>{
   const r=mapbox.getBoundingClientRect();
   herbTip.style.left=(e.clientX-r.left)+'px';
   herbTip.style.top=(e.clientY-r.top)+'px';
  });
  hit.addEventListener('mouseleave',()=>herbTip.classList.remove('on'));
  herbLayer.appendChild(group)});
 // 拾取点
 const dots=[];
 mp.pois.forEach(p=>{
  const c=document.createElementNS(NS,'circle');
  c.setAttribute('cx',p[6]/ts);c.setAttribute('cy',p[7]/ts);
  c.setAttribute('r',p[1]===2?2.4:1.7);
  c.setAttribute('fill',poiFill(p));
  c.setAttribute('fill-opacity',p[1]===4?'.75':'.95');
  c.setAttribute('stroke','#0b0d10');c.setAttribute('stroke-width','.4');
  c.classList.add('poi-dot');
  const tip=document.createElementNS(NS,'title');
  tip.textContent=pillName(p,mp);c.appendChild(tip);
  if(consumed.has(p[0]))c.classList.add('dim');
  if(strokes.length&&!exploredAt(p[6],p[7]))c.classList.add('unseen');
  c.addEventListener('click',()=>showPoi(p));
  svg.appendChild(c);dots.push(c);
 });
 const routeLayer=document.createElementNS(NS,'g');
 routeLayer.setAttribute('id','pillroute');svg.appendChild(routeLayer);
 const ring=document.createElementNS(NS,'circle');
 ring.setAttribute('id','pillring');
 ring.setAttribute('fill','none');ring.setAttribute('stroke','#fff');
 ring.setAttribute('stroke-width','.9');ring.setAttribute('r','6');
 ring.style.display='none';svg.appendChild(ring);
 // 把传送路线画在盘面上，避免只给坐标却看不到门在哪
 function drawRoute(steps){
  while(routeLayer.firstChild)routeLayer.removeChild(routeLayer.firstChild);
  steps.forEach(([cfg,x1,y1,x2,y2])=>{
   const line=document.createElementNS(NS,'line');
   line.setAttribute('x1',x1/ts);line.setAttribute('y1',y1/ts);
   line.setAttribute('x2',x2/ts);line.setAttribute('y2',y2/ts);
   line.setAttribute('stroke','#4fe0c0');line.setAttribute('stroke-width','1.4');
   line.setAttribute('stroke-dasharray','5 4');line.setAttribute('stroke-opacity','.9');
   routeLayer.appendChild(line);
   [[x1,y1,'入'],[x2,y2,'出']].forEach(([x,y,label])=>{
    const dot=document.createElementNS(NS,'circle');
    dot.setAttribute('cx',x/ts);dot.setAttribute('cy',y/ts);dot.setAttribute('r','5');
    dot.setAttribute('fill','#0b1412');dot.setAttribute('fill-opacity','.65');
    dot.setAttribute('stroke','#4fe0c0');dot.setAttribute('stroke-width','1.6');
    routeLayer.appendChild(dot);
    const text=document.createElementNS(NS,'text');
    text.setAttribute('x',x/ts);text.setAttribute('y',y/ts-7.5);
    text.setAttribute('fill','#4fe0c0');text.setAttribute('font-size','9');
    text.setAttribute('text-anchor','middle');text.textContent=label;
    routeLayer.appendChild(text);
   });
  });
 }
 $('pillinfo').onclick=e=>{
  const jump=e.target.closest('[data-x]');
  if(jump){
   ring.setAttribute('cx',+jump.dataset.x/ts);
   ring.setAttribute('cy',+jump.dataset.y/ts);
   ring.style.display='';
  }
 };
 function showPoi(p){
  const isRecipe=p[1]===2;
  const rid=isRecipe?String((mp.pool||[])[p[5]]||''):'';
  const rec=isRecipe?(mp.recipes||{})[rid]:null;
  const tags=[PILL_TYPE[p[1]]||''];
  if(isRecipe&&rec)tags.push(`${PILL_ELEMENT[rec.e]||'—'}系 · ${rec.t||0} 阶`);
  else if(p[1]<=3&&p[2])tags.push(`${PILL_ELEMENT[p[2]]||''}${p[3]?` · ${p[3]}阶`:''}`);
  if(isRecipe&&rec)tags.push(learned.has(rid)?'已学会':'未学会');
  if(consumed.has(p[0]))tags.push('已拾取');
  let html=`<b>${esc(pillName(p,mp))}</b>　<span class="muted">${esc(tags.filter(Boolean).join(' · '))}</span>`+
   `<div style="margin-top:4px">坐标 ${p[6]}, ${p[7]}　编号 #${p[0]}</div>`;
  if(rec){
   const tiers=(rec.g||[]).join(' / ')||'—';
   html+=`<div class="rec-info"><div><span>丹毒上限</span>${rec.x||0}</div>`+
    `<div><span>成丹门槛</span>${tiers}</div>`+
    `<div><span>灵力 / 时长</span>${rec.s||0} / ${rec.tm||0}</div>`+
    `<div><span>可炼次数</span>${rec.m||'不限'}</div></div>`;
   if(rec.d)html+=`<div class="muted" style="margin-top:6px">${esc(rec.d)}</div>`;
  }else if(p[1]===1&&(mp.effects||{})[String(p[4])]){
   const eff=mp.effects[String(p[4])];
   if(eff[7])html+=`<div class="rec-info"><div><span>主属性</span>${esc(eff[7])}</div>`+
    `<div><span>数值</span>${eff[6]}</div></div>`;
   if(eff[3])html+=`<div class="muted" style="margin-top:6px">${esc(eff[3])}</div>`;
  }else if(pillDesc(p,mp)){
   html+=`<div class="muted" style="margin-top:4px">${esc(pillDesc(p,mp))}</div>`;
  }
  const comp=compById.has(p[0])?compById.get(p[0]):-1;
  const steps=(mp.routes||{})[String(comp)]||[];
  if(mp.main!==undefined&&comp>=0){
   if(comp===mp.main){
    html+=`<div class="route"><span>传送</span>无需传送，与你出发的区域连通</div>`;
   }else{
    if(steps.length){
     html+=`<div class="route"><span>传送 ${steps.length} 次</span>`+steps.map(([cfg,x1,y1,x2,y2])=>{
      const name=((mp.portals||{})[String(cfg)]||[])[0]||('传送口 '+cfg);
      return `<button class="route-item" data-x="${x1}" data-y="${y1}">${esc(name)}`+
       `<i>${Math.round(x1)},${Math.round(y1)} → ${Math.round(x2)},${Math.round(y2)}</i></button>`;
     }).join('')+`</div>`;
    }else{
     html+=`<div class="route"><span>传送</span>这一片没有连通传送口，暂时过不去</div>`;
    }
   }
  }
  if(p[1]===5||p[1]===6){
   const pt=(mp.portals||{})[String(p[10])];
   html+=`<div class="muted" style="margin-top:4px">${pt&&pt[2]?'双向传送':'单向传送'} · `+
    `${pt&&pt[5]?`消耗 ${esc(pt[4]||'妖丹')} ×${pt[5]}`:'不需要妖丹'}</div>`;
   const other=mp.pois.find(q=>(q[1]===5||q[1]===6)&&q[10]===p[10]&&q[0]!==p[0]);
   if(other)html+=`<div class="route"><span>${p[1]===5?'出口':'入口'}</span>`+
    `${p[1]===5?'穿过这里就是':'从这里可以回到'} ${Math.round(other[6])},${Math.round(other[7])}`+
    `<button class="route-item" data-x="${other[6]}" data-y="${other[7]}">定位</button></div>`;
  }
  $('pillinfo').innerHTML=html;
  drawRoute(comp>=0&&comp!==mp.main?steps:[]);
  ring.setAttribute('cx',p[6]/ts);ring.setAttribute('cy',p[7]/ts);ring.style.display='';
  markSelected(p[0]);
 }
 // 筛选：①显示对象 ②筛选条件（仅丹方/丹方属性） ③视图 ④搜索
 const mapbox=cv.parentElement,side=host.querySelector('.pill-side');
 const chips=$('pillchips'),elems=$('pillelems'),tierBox=$('pilltiers'),keys=$('pillkeys'),viewBox=$('pillview');
 const allElems=['1','2','3','4','5'];
 const tierValues=[...new Set(mp.pois.filter(p=>p[1]===1||p[1]===2).map(p=>p[3]).filter(t=>t>0))].sort((a,b)=>a-b);
 const allTypes=()=>Object.keys(PILL_GROUPS);
 // 还原上次的筛选条件，按当前盘面能力裁剪
 pillFilter.types=pillFilter.types.filter(k=>PILL_GROUPS[k]);
 if(!pillFilter.types.length)pillFilter.types=allTypes();
 pillFilter.elements=pillFilter.elements.map(String).filter(v=>allElems.includes(v));
 pillFilter.tiers=pillFilter.tiers.map(String).filter(t=>tierValues.includes(+t));
 // 阶数是「选中即显示」的多选：空集合等于一个都不显示，所以默认全选
 if(!pillFilter.tiers.length)pillFilter.tiers=tierValues.map(String);
 pillFilter.keywords=pillFilter.keywords.filter(k=>PILL_KEYWORDS.includes(k));
 let keyExpanded=false;const expandedGroups=new Set();
 let fogOn=fogLayer?store.get('worldapart.pill.fog.v1',false)===true:false;
 if(fogLayer)mapbox.classList.toggle('showfog',fogOn);
 // 药材轨迹默认隐藏，避免 45 条线在盘面中间叠成一张网
 let herbOn=store.get('worldapart.pill.herbs.v1',false)===true;
 mapbox.classList.toggle('showherb',herbOn);
 function saveFilter(){
  store.set(PILL_FILTER_KEY,{types:pillFilter.types,elements:pillFilter.elements,
   tiers:pillFilter.tiers,keywords:pillFilter.keywords,q:pillFilter.q,hideDone:pillFilter.hideDone});
 }
 function typeKey(t){for(const k in PILL_GROUPS)if(PILL_GROUPS[k].includes(t))return k;return 'other'}
 function typeSelected(p){return pillFilter.types.some(k=>(PILL_GROUPS[k]||[]).includes(p[1]))}
 function isDone(p){return p[1]===2?learned.has(String((mp.pool||[])[p[5]]||'')):consumed.has(p[0])}
 // skip 表示统计某一组时先忽略该组自身条件，才能看出「勾上它还剩多少」
 function passBase(p,skip){
  if(p[1]===1||p[1]===2){
   if(skip!=='elements'&&p[2]>0&&!pillFilter.elements.includes(String(p[2])))return false;
   if(skip!=='tiers'&&!pillFilter.tiers.includes(String(p[3])))return false;
   if(skip!=='keywords'&&pillFilter.keywords.length){
    const text=pillText(p,mp);
    if(!pillFilter.keywords.some(k=>text.includes(k)))return false;
   }
  }
  if(pillFilter.hideDone&&consumed.has(p[0]))return false;
  const q=pillFilter.q.trim();
  if(q&&!(pillName(p,mp).includes(q)||pillText(p,mp).includes(q)))return false;
  return true;
 }
 function countsByType(){
  const out={};allTypes().forEach(k=>out[k]=0);
  mp.pois.forEach(p=>{
   if(!passBase(p,''))return;
   for(const k in PILL_GROUPS){if(PILL_GROUPS[k].includes(p[1])){out[k]++;break}}
  });
  return out;
 }
 function countsByElement(){
  const out={};
  mp.pois.forEach(p=>{
   if((p[1]!==1&&p[1]!==2)||!typeSelected(p)||!p[2]||!passBase(p,'elements'))return;
   out[p[2]]=(out[p[2]]||0)+1;
  });
  return out;
 }
 function countsByTier(){
  const out={};
  mp.pois.forEach(p=>{
   if((p[1]!==1&&p[1]!==2)||!typeSelected(p)||!passBase(p,'tiers'))return;
   out[p[3]]=(out[p[3]]||0)+1;
  });
  return out;
 }
 function countsByKeyword(){
  const out={};
  mp.pois.forEach(p=>{
   if((p[1]!==1&&p[1]!==2)||!typeSelected(p)||!passBase(p,'keywords'))return;
   const text=pillText(p,mp);if(!text)return;
   PILL_KEYWORDS.forEach(k=>{if(text.includes(k))out[k]=(out[k]||0)+1});
  });
  return out;
 }
 function renderTypes(){
  const counts=countsByType();
  chips.innerHTML=allTypes().map(k=>{
   const n=counts[k]||0;
   return `<button class="chip${pillFilter.types.includes(k)?' on':''}${n?'':' zero'}" data-chip="${k}">${PILL_LABELS[k]}<i>${n}</i></button>`;
  }).join('');
 }
 function renderElems(){
  const counts=countsByElement();
  elems.innerHTML=allElems.map(v=>{
   const n=counts[v]||0;
   return `<button class="chip${pillFilter.elements.includes(v)?' on':''}${n?'':' zero'}" data-elem="${v}">${PILL_ELEMENT[+v]}<i>${n}</i></button>`;
  }).join('');
 }
 function renderTiers(){
  const counts=countsByTier();
  tierBox.innerHTML=tierValues.length?tierValues.map(t=>{
   const n=counts[t]||0;
   return `<button class="chip${pillFilter.tiers.includes(String(t))?' on':''}${n?'':' zero'}" data-tier="${t}">${t} 阶<i>${n}</i></button>`;
  }).join(''):'<span class="fhint">当前盘面没有阶数</span>';
 }
 function renderKeys(){
  const counts=countsByKeyword();
  const positive=PILL_KEYWORDS.filter(k=>counts[k]).sort((a,b)=>counts[b]-counts[a]);
  const pinned=pillFilter.keywords.filter(k=>!positive.includes(k));
  const shown=keyExpanded?positive.concat(pinned):[...new Set([...positive.slice(0,8),...pinned])];
  const total=positive.length+pinned.length;
  keys.innerHTML=shown.map(k=>
   `<button class="chip${pillFilter.keywords.includes(k)?' on':''}" data-key="${k}">${k}<i>${counts[k]||0}</i></button>`).join('')+
   (total>8?`<button class="chip more" data-op="more" data-row="keywords">${keyExpanded?'收起':'更多 '+total}</button>`:'');
 }
 function renderView(){
  viewBox.innerHTML=(fogLayer?`<button class="chip${fogOn?' on':''}" data-view="fog">迷雾</button>`:'')+
   `<button class="chip${herbOn?' on':''}" data-view="herb">药材路线</button>`+
   `<button class="chip${pillFilter.hideDone?' on':''}" data-view="done">隐藏已拾取</button>`;
 }
 function renderCond(){
  $('pillcond').classList.toggle('off',!(pillFilter.types.includes('recipe')||pillFilter.types.includes('effect')));
 }
 function renderActive(){
  const tags=[];
  if(pillFilter.types.length!==allTypes().length)
   pillFilter.types.forEach(k=>tags.push(['types',k,PILL_LABELS[k]]));
  if(pillFilter.elements.length!==5)
   pillFilter.elements.forEach(v=>tags.push(['elements',v,PILL_ELEMENT[+v]+'行']));
  if(pillFilter.tiers.length!==tierValues.length)
   pillFilter.tiers.forEach(t=>tags.push(['tiers',t,t+' 阶']));
  pillFilter.keywords.forEach(k=>tags.push(['keywords',k,k]));
  if(pillFilter.q.trim())tags.push(['q','hidden','搜索 '+pillFilter.q.trim()]);
  if(pillFilter.hideDone)tags.push(['done','hidden','隐藏已拾取']);
  if(herbOn)tags.push(['herb','hidden','药材路线']);
  if(fogOn)tags.push(['fog','hidden','迷雾']);
  $('pillactive').innerHTML=tags.length?
   '<span class="ptag-label">已选</span>'+tags.map(([row,v,label])=>
    `<button class="ptag" data-tagrow="${row}" data-tagval="${esc(v)}">${esc(label)}<b>×</b></button>`).join('')+
    '<button class="ptag clear" data-tagrow="all">清空</button>'
   :'<span class="ptag-label">未设筛选，显示全部拾取点</span>';
 }
 function itemHtml(p){
  const isRecipe=p[1]===2,rid=isRecipe?String((mp.pool||[])[p[5]]||''):'';
  let sub;
  if(isRecipe){sub=`${PILL_ELEMENT[p[2]]||''}·${p[3]||0}阶`;if(learned.has(rid))sub+=' · 已学会'}
  else if(p[1]===1){const e=(mp.effects||{})[String(p[4])];sub=(e&&e[7])||'丹方属性';if(p[3])sub+=' · '+p[3]+'阶'}
  else if(p[1]===4){const r=(mp.rewards||{})[String(p[8])];sub='奖励'+(r?' · 品质 '+r[2]:'')}
  else if(p[1]===5||p[1]===6)sub='传送口 · '+portalCost(mp,p[10]);
  else sub=PILL_TYPE[p[1]]||'其他';
  const comp=compById.has(p[0])?compById.get(p[0]):-1;
  if(p[1]!==5&&p[1]!==6&&mp.main!==undefined&&comp>=0&&comp!==mp.main)sub+=' · 需传送';
  return `<div class="pill-item${isDone(p)?' done':''}" data-id="${p[0]}">`+
   `<i class="dotmark" style="background:${poiFill(p)}"></i>`+
   `<span class="nm">${esc(pillName(p,mp))}</span><span class="tp">${esc(sub)}</span></div>`;
 }
 function renderList(matched){
  const picked=matched.filter(p=>consumed.has(p[0])).length;
  $('pillsum').innerHTML=`结果 <b>${matched.length}</b> 项 · 已拾取 ${picked} 项`;
  if(!matched.length){
   const acts=[];
   if(pillFilter.tiers.length<tierValues.length)acts.push('<button type="button" class="pill-act" data-relax="tiers">放宽到全部阶数</button>');
   if(pillFilter.keywords.length)acts.push('<button type="button" class="pill-act" data-relax="keywords">清空药效</button>');
   if(pillFilter.elements.length!==5)acts.push('<button type="button" class="pill-act" data-relax="elements">恢复全部五行</button>');
   if(pillFilter.q.trim())acts.push('<button type="button" class="pill-act" data-relax="q">清空搜索</button>');
   if(pillFilter.hideDone)acts.push('<button type="button" class="pill-act" data-relax="done">显示已拾取</button>');
   acts.push('<button type="button" class="pill-act" data-relax="all">清空全部筛选</button>');
   $('pilllist').innerHTML='<div class="empty" style="margin:0;border:0">没有符合条件的拾取点'+
    '<div class="empty-acts">'+acts.join('')+'</div></div>';
   return;
  }
  const groups={};matched.forEach(p=>{const k=typeKey(p[1]);(groups[k]=groups[k]||[]).push(p)});
  const keysNow=PILL_ORDER.filter(k=>groups[k]);
  const single=keysNow.length===1;
  $('pilllist').innerHTML=keysNow.map(k=>{
   const list=k==='recipe'?groups[k].slice().sort((a,b)=>(b[3]||0)-(a[3]||0)):groups[k];
   const limit=expandedGroups.has(k)?list.length:60;
   return '<div class="pill-group"><div class="pghead"><span class="pgname">'+esc(PILL_LABELS[k])+'</span>'+
    '<i class="pgcount">'+list.length+'</i>'+
    (single?'':'<button type="button" class="pgonly" data-only="'+k+'">只看这类</button>')+'</div>'+
    list.slice(0,limit).map(itemHtml).join('')+
    (list.length>limit?'<button type="button" class="pgmore" data-expand="'+k+'">展开全部 '+list.length+' 项</button>':'')+
    '</div>';
  }).join('');
 }
 function markSelected(id){
  document.querySelectorAll('#pilllist .pill-item.focus').forEach(n=>n.classList.remove('focus'));
  const node=document.querySelector('#pilllist .pill-item[data-id="'+id+'"]');
  if(node){node.classList.add('focus');node.scrollIntoView({block:'nearest'})}
 }
 function resetAll(){
  pillFilter.types=allTypes();pillFilter.elements=allElems.slice();
  pillFilter.tiers=tierValues.map(String);pillFilter.keywords=[];pillFilter.q='';pillFilter.hideDone=false;
  $('pillq').value='';
 }
 function applyOp(row,op){
  if(op==='more'){keyExpanded=!keyExpanded;renderKeys();return}
  if(row==='types')pillFilter.types=op==='all'?allTypes():[];
  else if(row==='elements')pillFilter.elements=op==='all'?allElems.slice():[];
  else if(row==='tiers')pillFilter.tiers=op==='all'?tierValues.map(String):[];
  else if(row==='keywords')pillFilter.keywords=[];
  applyFilter();
 }
 function removeTag(row,val){
  if(row==='all')resetAll();
  else if(row==='q'){pillFilter.q='';$('pillq').value=''}
  else if(row==='done')pillFilter.hideDone=false;
  else if(row==='fog'){fogOn=false;if(fogLayer)mapbox.classList.remove('showfog');store.set('worldapart.pill.fog.v1',false)}
  else if(row==='herb'){herbOn=false;mapbox.classList.remove('showherb');store.set('worldapart.pill.herbs.v1',false)}
  else if(row==='types')pillFilter.types=pillFilter.types.filter(x=>x!==val);
  else if(row==='elements')pillFilter.elements=pillFilter.elements.filter(x=>x!==val);
  else if(row==='tiers')pillFilter.tiers=pillFilter.tiers.filter(x=>x!==val);
  else if(row==='keywords')pillFilter.keywords=pillFilter.keywords.filter(x=>x!==val);
  applyFilter();
 }
 function relaxFilter(kind){
  if(kind==='all')resetAll();
  else if(kind==='tiers')pillFilter.tiers=tierValues.map(String);
  else if(kind==='keywords')pillFilter.keywords=[];
  else if(kind==='elements')pillFilter.elements=allElems.slice();
  else if(kind==='q'){pillFilter.q='';$('pillq').value=''}
  else if(kind==='done')pillFilter.hideDone=false;
  applyFilter();
 }
 side.addEventListener('click',e=>{
  const op=e.target.closest('[data-op]');
  if(op){applyOp(op.dataset.row,op.dataset.op);return}
  const view=e.target.closest('[data-view]');
  if(view){
   if(view.dataset.view==='fog'&&fogLayer){
    fogOn=!fogOn;mapbox.classList.toggle('showfog',fogOn);
    store.set('worldapart.pill.fog.v1',fogOn);renderView();renderActive();return;
   }
   if(view.dataset.view==='herb'){
    herbOn=!herbOn;mapbox.classList.toggle('showherb',herbOn);
    store.set('worldapart.pill.herbs.v1',herbOn);renderView();renderActive();return;
   }
   if(view.dataset.view==='done'){pillFilter.hideDone=!pillFilter.hideDone;applyFilter();return}
  }
  const tag=e.target.closest('[data-tagrow]');
  if(tag){removeTag(tag.dataset.tagrow,tag.dataset.tagval);return}
  const relax=e.target.closest('[data-relax]');
  if(relax){relaxFilter(relax.dataset.relax);return}
  const only=e.target.closest('[data-only]');
  if(only){pillFilter.types=[only.dataset.only];applyFilter();return}
  const more=e.target.closest('[data-expand]');
  if(more){expandedGroups.add(more.dataset.expand);applyFilter();return}
  const item=e.target.closest('[data-id]');
  if(item&&item.classList.contains('pill-item')){
   const p=mp.pois.find(x=>String(x[0])===item.dataset.id);
   if(p)showPoi(p);
   return;
  }
  const btn=e.target.closest('.chip');if(!btn)return;
  if(btn.dataset.chip!==undefined){
   const key=btn.dataset.chip;
   pillFilter.types=e.altKey?[key]:(pillFilter.types.includes(key)?pillFilter.types.filter(x=>x!==key):pillFilter.types.concat(key));
   applyFilter();return;
  }
  if(btn.dataset.elem!==undefined){
   const v=btn.dataset.elem;
   pillFilter.elements=e.altKey?[v]:(pillFilter.elements.includes(v)?pillFilter.elements.filter(x=>x!==v):pillFilter.elements.concat(v));
   applyFilter();return;
  }
  if(btn.dataset.tier!==undefined){
   const t=btn.dataset.tier;
   pillFilter.tiers=e.altKey?[t]:(pillFilter.tiers.includes(t)?pillFilter.tiers.filter(x=>x!==t):pillFilter.tiers.concat(t));
   applyFilter();return;
  }
  if(btn.dataset.key!==undefined){
   const k=btn.dataset.key;
   pillFilter.keywords=e.altKey?[k]:(pillFilter.keywords.includes(k)?pillFilter.keywords.filter(x=>x!==k):pillFilter.keywords.concat(k));
   applyFilter();return;
  }
 });
 const mapChips=$('pillmaps');
 if(mapChips)mapChips.onclick=e=>{
  const btn=e.target.closest('[data-map]');if(!btn)return;
  store.set('worldapart.pill.map.v1',+btn.dataset.map);initPill();
 };
 $('pillq').value=pillFilter.q;
 $('pillq').oninput=e=>{pillFilter.q=e.target.value;applyFilter()};
 function applyFilter(){
  const matched=[];
  mp.pois.forEach((p,idx)=>{
   const ok=typeSelected(p)&&passBase(p,'');
   dots[idx].classList.toggle('off',!ok);
   if(ok)matched.push(p);
  });
  renderTypes();renderElems();renderTiers();renderKeys();renderView();renderCond();renderActive();
  renderList(matched);
  saveFilter();
 }
 applyFilter();
 // 丹方手记
 const manual=st.manual||[];
 if(manual.length){
  const recipePoi={};
  mp.pois.forEach(p=>{if(p[1]===2){const rid=(mp.pool||[])[p[5]];if(rid)recipePoi[String(rid)]=p}});
  $('pillmanual').innerHTML=manual.map(r=>`<div class="manual-item" data-recipe="${esc(String(r.id))}">`+
   `<span class="nm">${esc(r.name)}</span>`+
   `<span class="tag">${esc(PILL_ELEMENT[r.element]||'')}${r.tier?`·${r.tier}阶`:''}</span>`+
   `<span class="tag">${r.grade} 品</span><span class="tag">丹毒 ${r.toxin}</span>`+
   `<span class="tag">药效 ${(r.effects||[]).length}</span></div>`).join('');
  $('pillmanual').onclick=e=>{
   const it=e.target.closest('[data-recipe]');if(!it)return;
   const p=recipePoi[it.dataset.recipe];
   if(p)showPoi(p);
   else $('pillinfo').innerHTML='该丹方在当前盘面上没有固定拾取点';
  };
 }
}
const FORGE_ELEM_COLORS=['#8b93a1','#e6dcae','#8ccf92','#7fc0ee','#ee9a86','#d8b273'];
const FORGE_FILTER_KEY='worldapart.forge.filters.v1';
function initForge(){
 const m=DATA.modules&&DATA.modules.forge;if(!m)return;const host=$('forge'),st=m.rows||{};
 const elem=id=>(m.elements||{})[String(id)]||'';
 const slotName=id=>(m.slots||{})[String(id)]||'';
 const realmName=id=>(m.realms||{})[String(id)]||('境界 '+id);
 const attrName=id=>(m.attributes||{})[String(id)]||('属性 '+id);
 const tierName=id=>((m.score_tiers||[]).find(x=>Number(x.id)===Number(id))||{}).name||(id+' 阶');
 const ratio=(a,b)=>b?Math.min(100,Math.round(a*100/b)):0;
 function grid(p){
  const n=Number(p.board)||5,blocked=new Set((p.blocked||[]).map(c=>c[0]+','+c[1])),bonus={};
  (p.bonus||[]).forEach(c=>bonus[c[0]+','+c[1]]=c[2]);
  let cells='';
  for(let y=0;y<n;y++)for(let x=0;x<n;x++){
   const key=x+','+y;let cls='fcell',style='';
   if(blocked.has(key))cls+=' block';
   else if(bonus[key])style='background:'+(FORGE_ELEM_COLORS[bonus[key]]||'#3a4652')+';opacity:.55';
   cells+='<i class="'+cls+'" style="'+style+'" title="'+x+','+y+'"></i>';
  }
  return '<div class="fgrid" style="grid-template-columns:repeat('+n+',20px)">'+cells+'</div>';
 }
 const cards=[
  ['炼器等级','Lv'+st.level,st.level_title||''],
  ['经验',st.exp+' / '+(st.exp_need||'—'),st.exp_need&&st.exp>=st.exp_need?'已达升级线':'继续炼制积累'],
  ['真火',st.true_fire,'本级基础值'],
  ['天赋点',st.talent_points,'已解锁 '+(st.unlocked||[]).length+' · 已领悟 '+(st.learned||[]).length],
  ['最高器契',st.best_score,st.best_tier_name||'—'],
  ['器胚库存',(st.embryo_total||0)+' 件',(st.embryos||[]).length+' 种'],
 ].map(([k,v,s])=>'<div class="card"><div class="k">'+esc(k)+'</div><div class="v">'+esc(v)+'<span> '+esc(s)+'</span></div></div>').join('');
 const embryoRows=(st.embryos||[]).map(e=>{
  const need=(e.need||[]).map(r=>esc(elem(r.e))+'×'+r.need+(r.gap?' <span class="fgap">缺 '+r.gap+'</span>':' <span class="fok">足</span>')).join(' · ');
  const wash=(e.effects||[]).map(x=>esc(elem(x.e))+' '+x.energy+' · '+esc(x.mat_name)+'×'+x.count).join('；')||'—';
  return '<tr class="row"><td><div class="who">'+esc(e.name)+'</div><div class="bed">'+esc(e.realm_name)+' · '+esc(e.slot_name)+' · '+e.board+'×'+e.board+'</div></td>'+
   '<td style="width:56px">×'+e.count+'</td><td>'+need+'</td><td class="muted">'+wash+'</td><td style="width:84px">'+e.rec_total+' 灵性</td></tr>';
 }).join('');
 const pityRows=(st.pity||[]).map(p=>{
  const left=Math.max(0,p.total-p.count);
  return '<tr class="row"><td>'+esc(p.realm_name)+'</td><td>'+esc(p.quality_name)+'：'+p.count+' / '+p.total+'</td>'+
   '<td class="muted">'+(left?'还差 '+left+' 次':'下一次必出')+'</td><td style="width:150px"><div class="bar"><i style="width:'+ratio(p.count,p.total)+'%"></i></div></td></tr>';
 }).join('');
 const elemCards=(st.elements||[]).map(e=>'<div class="card"><div class="k">'+esc(elem(e.element))+'行材料</div><div class="v">'+e.count+' <span>件 · 灵性 '+e.spirit+'</span></div></div>').join('')||'<div class="card"><div class="k">材料</div><div class="v">0 <span>件</span></div></div>';
 const matRows=(st.materials||[]).map(r=>'<tr class="row"><td><div class="who fq'+r.quality+'">'+esc(r.name)+'</div><div class="bed">'+esc(elem(r.element))+' · '+esc(realmName(r.realm))+'</div></td>'+
  '<td style="width:56px">×'+r.count+'</td><td style="width:60px">'+r.spirit+'</td><td class="muted">灵性合计 '+(r.count*r.spirit)+'</td></tr>').join('');
 const artRows=(st.artifacts||[]).map(a=>{
  const affixes=(a.affixes||[]).map(x=>'<span class="fchip fq'+x.quality+'">'+esc(x.text)+(x.pending?'（未激活）':'')+'</span>').join('')||'<span class="muted">无词条</span>';
  const attrs=(a.attrs||[]).map(pair=>esc(pair[0])+' +'+pair[1]).join(' · ')||'—';
  const wash=(a.wash||[]).map(w=>esc(elem(w.e))+' '+esc(w.material)+'×'+w.count).join('；')||'—';
  const pity=(a.pity||[]).map(p=>esc(p.name)+' '+p.count+'/'+p.total).join(' · ')||'—';
  return '<details class="fart"><summary><span class="fname">'+esc(a.name)+'</span>'+
   (a.equipped?'<span class="badge dao">已装备</span>':'')+
   (a.slot_name?'<span class="badge">'+esc(a.slot_name)+'</span>':'')+
   '<span class="badge">'+esc(a.realm_name)+'</span>'+
   '<span class="badge">'+(a.crafted?esc(a.tier_name||'未定阶'):'非炼器所得')+'</span>'+
   '<span class="fstat">器契 '+a.score+' · '+(a.affixes||[]).length+' 条词条</span></summary>'+
   '<div class="fbody"><div class="fline"><b>基础属性</b>'+attrs+'</div>'+
   '<div class="fline"><b>词条</b><span class="fchips">'+affixes+'</span></div>'+
   '<div class="fline"><b>洗练材料</b>'+wash+'</div>'+
   '<div class="fline"><b>洗练保底</b>'+pity+'</div></div></details>';
 }).join('')||'<div class="empty">还没有法宝数据</div>';
 const realms=uniq((m.catalog||[]).map(p=>String(p.realm)));
 const slots=uniq((m.catalog||[]).map(p=>String(p.slot)));
 let state=Object.assign({q:'',realm:'',slot:''},store.get(FORGE_FILTER_KEY,{}));
 function protoCard(p){
  const need=(p.need||[]).map(r=>elem(r.e)+'×'+r.v).join(' · ')||'无指定';
  const rec=(p.rec||[]).map(r=>elem(r.e)+' '+r.v).join(' · ')||'—';
  const washSlots=(p.effects||[]).map(x=>'<span class="fchip fq3">'+esc(elem(x.e))+' '+x.energy+' · '+esc(x.mat_name)+'×'+x.count+'</span>').join('')||'<span class="muted">无词条槽</span>';
  const tierHtml=(p.tiers||[]).map(t=>'<div class="fline"><b>'+esc(tierName(t.t))+'</b>门槛 '+t.min+' · '+((t.attrs||[]).map(pair=>esc(attrName(pair[0]))+' +'+pair[1]).join(' / ')||'—')+'</div>').join('');
  const tiers=(p.tiers||[]).map(t=>tierName(t.t)+' '+t.min).join(' / ');
  return '<details class="fproto"><summary><span class="fname">'+esc(p.name)+'</span>'+
   '<span class="badge">'+esc(realmName(p.realm))+'</span>'+
   '<span class="badge">'+esc(slotName(p.slot))+'</span>'+
   '<span class="badge">'+p.board+'×'+p.board+'</span>'+
   '<span class="badge">需 '+esc(need)+'</span>'+
   '<span class="ftiers">'+esc(tiers)+'</span></summary>'+
   '<div class="fbody"><div class="fcols">'+
   '<div class="fcol"><div class="fcol-t">棋盘（虚线＝封炉格，带色格＝聚灵格）</div>'+grid(p)+'</div>'+
   '<div class="fcol"><div class="fcol-t">炼制要求</div><div class="fline">五行需求 <b>'+esc(need)+'</b></div>'+
   '<div class="fline">推荐灵蕴 '+esc(rec)+'（合计 '+p.rec_total+'）</div><div class="fline">真火消耗 '+p.energy+'</div></div>'+
   '<div class="fcol"><div class="fcol-t">词条槽 · 洗练材料</div><div class="fchips">'+washSlots+'</div></div>'+
   '<div class="fcol"><div class="fcol-t">四阶门槛</div>'+tierHtml+'</div>'+
   '</div></div></details>';
 }
 function renderList(){
  const q=state.q.trim();
  const list=(m.catalog||[]).filter(p=>(state.realm===''||String(p.realm)===state.realm)&&
   (state.slot===''||String(p.slot)===state.slot)&&
   (!q||p.name.includes(q)||(p.tiers||[]).some(t=>String(t.out_name||'').includes(q))));
  $('fgcount').textContent='筛选结果：'+list.length+' / '+(m.catalog||[]).length+' 件器胚';
  $('fglist').innerHTML=list.map(protoCard).join('')||'<div class="empty">没有符合条件的器胚</div>';
 }
 function renderRealmChips(){realmBox.innerHTML='<span class="chip-label">境界</span>'+[['','全部']].concat(realms.map(r=>[r,realmName(r)])).map(
   ([value,label])=>'<button class="chip'+(state.realm===value?' on':'')+'" data-realm="'+esc(value)+'">'+esc(label)+'</button>').join('');
 }
 function renderSlotChips(){slotBox.innerHTML='<span class="chip-label">部位</span>'+[['','全部']].concat(slots.map(s=>[s,slotName(s)])).map(
   ([value,label])=>'<button class="chip'+(state.slot===value?' on':'')+'" data-slot="'+esc(value)+'">'+esc(label)+'</button>').join('');
 }
 host.innerHTML=sourceHtml(m)+'<div class="cards">'+cards+'</div>'+
  '<div class="forge-sec">我的器胚<span>按持有件数与五行缺口</span></div>'+
  ((st.embryos||[]).length?'<table><thead><tr><th>器胚</th><th>数量</th><th>五行需求 / 缺口</th><th>洗练材料</th><th>推荐灵性</th></tr></thead><tbody>'+embryoRows+'</tbody></table>':'<div class="empty">背包里没有器胚</div>')+
  '<div class="forge-sec">洗练保底<span>同境界、同品质法宝共享计数</span></div>'+
  ((st.pity||[]).length?'<table><tbody>'+pityRows+'</tbody></table>':'<div class="empty">暂无洗练保底数据</div>')+
  '<div class="forge-sec">全部器胚<span>门槛为该阶所需器契分数</span></div>'+
  '<div class="search-panel"><div class="search-fields" style="grid-template-columns:1fr"><label class="search-field"><span>找器胚 / 法宝</span><input id="fgq" placeholder="输入器胚或法宝名称"></label></div></div>'+
  '<div class="chips" id="fgrealm"></div><div class="chips" id="fgslot"></div><div id="fgcount" class="result-info"></div><div id="fglist"></div>'+
  '<div class="forge-sec">材料盘点<span>按五行统计件数与灵性</span></div>'+
  '<div class="cards">'+elemCards+'</div>'+
  ((st.materials||[]).length?'<table><thead><tr><th>材料</th><th>数量</th><th>灵性</th><th></th></tr></thead><tbody>'+matRows+'</tbody></table>':'<div class="empty">背包里没有炼器材料</div>')+
  '<div class="forge-sec">我的法宝<span>器契即炼器分数，“未激活”为待洗练词条</span></div>'+artRows+
  '<div class="tip">五行需求按“该五行精粹需占几格”计算；缺口＝背包该五行材料总件数－需求格数，只作库存参考，实际摆盘还受封炉格与聚灵格影响。器契达到凡/玄/地/天四档门槛即对应阶，天阶最高。</div>';
 const realmBox=$('fgrealm'),slotBox=$('fgslot');
 $('fgq').value=state.q;
 $('fgq').oninput=e=>{state.q=e.target.value;renderList()};
 realmBox.onclick=e=>{const btn=e.target.closest('[data-realm]');if(!btn)return;state.realm=btn.dataset.realm;store.set(FORGE_FILTER_KEY,state);renderRealmChips();renderList()};
 slotBox.onclick=e=>{const btn=e.target.closest('[data-slot]');if(!btn)return;state.slot=btn.dataset.slot;store.set(FORGE_FILTER_KEY,state);renderSlotChips();renderList()};
 renderRealmChips();renderSlotChips();renderList();
}
const EVENT_FILTER_KEY='worldapart.event.filters.v1';
function initEvent(){
 const m=DATA.modules&&DATA.modules.event;if(!m)return;
 const host=$('event'),st=m.rows||{},rows=st.rows||[],catalog=st.reward_index||[];
 const stats=st.stats||{},metaStats=st.meta_stats||{};
 if(!rows.length&&!catalog.length){host.innerHTML=sourceHtml(m)+'<div class="empty">暂无奇遇配置</div>';return}
 const byId={};rows.forEach(r=>byId[r.id]=r);
 const itemNames={};catalog.forEach(x=>itemNames[x.item]=x.name);
 let state=Object.assign({q:'',status:'',realm:'',mode:'event',missing:false},store.get(EVENT_FILTER_KEY,{}));
 const gradeName=g=>(st.grades||{})[String(g)]||('第'+g+'档');
 const gradeCls=g=>'g'+(g||0);
 const confName=c=>c==='exact'?'位置确定':c==='inferred'?'位置推断':'位置未定';
 const confCls=c=>c==='exact'?'loc-exact':c==='inferred'?'loc-inferred':'loc-unknown';
 const locText=r=>{const l=r.location;if(!l)return '位置未定';const path=((l.path&&l.path.length)?l.path:[l.name]).join(' / ');return (l.spot?l.spot+' · ':'')+path};
 const itemName=id=>itemNames[id]||('物品 '+id);
 const rewardChip=(x,got)=>`<span class="efchip fq${x.quality||0}${got?' got':''}" title="掉率 ${x.chance}%">${esc(x.name)} ×${x.min===x.max?x.min:x.min+'-'+x.max}${x.chance>=100?'':'<i>'+x.chance+'%</i>'}</span>`;
 const cards=
  `<div class="card"><div class="k">奇遇达成</div><div class="v">${stats.achieved||0} <span>/ ${stats.events||0}</span></div></div>`+
  `<div class="card"><div class="k">结局收集</div><div class="v">${stats.got_endings||0} <span>/ ${stats.endings||0}</span></div></div>`+
  `<div class="card"><div class="k">实际所得</div><div class="v">${stats.granted||0} <span>条奖励</span></div></div>`+
  `<div class="card"><div class="k">地点定位</div><div class="v">${metaStats.exact||0} <span>确定 · 推断 ${metaStats.inferred||0}</span></div></div>`;
 function eventCard(r){
  const endings=r.endings||[];
  const got=endings.filter(e=>e.got).length;
  const badges=`<span class="badge ${r.achieved?'ok':'off'}">${r.achieved?'已达成':'未达成'}</span>`+
   `<span class="badge">结局 ${got}/${endings.length}</span>`+
   `<span class="badge">${r.one_off?'一次性':'可重复'}</span>`+
   (r.parent&&byId[r.parent]?`<span class="badge">隶属 ${esc(byId[r.parent].name)}</span>`:'')+
   `<span class="badge ${confCls((r.location||{}).conf)}">${confName((r.location||{}).conf)}</span>`;
  const grants=(r.grants||[]).length?`<div class="evline"><b>实际所得</b>${r.grants.map(g=>`${esc(itemName(g.item))} ×${g.count}${g.delivered?'':'（未交付）'}`).join(' · ')}</div>`:'';
  const picked=(r.choices||[]).length?`<div class="evline"><b>选择记录</b>${r.choices.map(c=>esc(c.text)+(c.count>1?' ×'+c.count:'')).join(' · ')}</div>`:'';
  const unknown=r.unknown_ending?`<div class="evline"><b>结局</b>#${r.ending}（配置未收录）</div>`:'';
  const body=endings.map(e=>`<div class="eend${e.got?' got':''}"><div class="eend-head">`+
   `<span class="egrade ${gradeCls(e.grade)}">${esc(gradeName(e.grade))}</span>`+
   `<span class="eend-title">${esc(e.title)}</span>`+
   (e.got?'<span class="badge ok">已达成</span>':'')+
   (e.reward_ok===false?'<span class="badge warn">奖励未收录</span>':'')+
   `</div>${e.summary?`<div class="eend-sum">${esc(e.summary)}</div>`:''}`+
   `${(e.detail||[]).length?`<div class="eend-detail">${e.detail.map(esc).join(' · ')}</div>`:''}`+
   `<div class="efchips">${e.rewards.length?e.rewards.map(x=>rewardChip(x,e.got)).join(''):'<span class="muted">无奖励记录</span>'}</div></div>`).join('');
  return `<details class="ev"><summary><span class="evname">${esc(r.name)}</span>${badges}<span class="evloc">${esc(locText(r))}</span></summary>`+
   `<div class="evbody">${r.desc?`<div class="evdesc">${esc(r.desc)}</div>`:''}${grants}${picked}${unknown}<div>${body}</div></div></details>`;
 }
 function itemCard(x){
  const sources=(x.sources||[]).slice().sort((a,b)=>(b.got?1:0)-(a.got?1:0)||(b.expected||0)-(a.expected||0));
  const rowsHtml=sources.map(s=>`<div class="evline"><b>${esc(s.event_name)}</b>${esc(s.ending_title)}`+
   ` <span class="muted">${s.chance>=100?'必得':s.chance+'%'} · 期望 ${s.expected}</span>`+
   (s.got?' <span class="badge ok">已达成</span>':'')+`</div>`).join('');
  return `<details class="ev"><summary><span class="evname fq${x.quality||0}">${esc(x.name)}</span>`+
   `<span class="badge">${esc(x.type||'物品')}</span>`+
   `<span class="badge ${x.owned?'ok':'off'}">${x.owned?'已拥有 '+x.owned:'未拥有'}</span>`+
   `<span class="evloc">${sources.length} 个结局产出</span></summary><div class="evbody">${rowsHtml}</div></details>`;
 }
 function matchedRows(){
  const q=state.q.trim();
  return rows.filter(r=>{
   if(state.status==='done'&&!r.achieved)return false;
   if(state.status==='todo'&&r.achieved)return false;
   if(state.realm==='__current__'){if(Number(r.realm||0)!==Number(st.current_realm||0))return false}
   else if(state.realm!==''&&String(r.realm||0)!==state.realm)return false;
   if(state.missing&&!r.endings.some(e=>e.rewards.some(x=>!x.owned)))return false;
   if(!q)return true;
   const hay=[r.name,r.desc,locText(r),(r.choices||[]).map(c=>c.text).join(' '),
    r.endings.map(e=>[e.title,e.summary].join(' ')).join(' '),
    r.endings.map(e=>e.rewards.map(x=>x.name).join(' ')).join(' ')].join(' ');
   return hay.includes(q);
  });
 }
 function matchedItems(){
  const q=state.q.trim();
  return catalog.filter(x=>(!state.missing||!x.owned)&&
   (!q||x.name.includes(q)||(x.sources||[]).some(s=>s.event_name.includes(q)||s.ending_title.includes(q))));
 }
 function refreshChips(){
  document.querySelectorAll('#evmode .chip').forEach(b=>b.classList.toggle('on',b.dataset.mode===state.mode));
  document.querySelectorAll('#evstatus .chip').forEach(b=>b.classList.toggle('on',b.dataset.status===state.status));
  document.querySelectorAll('#evrealm .chip').forEach(b=>b.classList.toggle('on',b.dataset.realm===state.realm));
  $('evmiss').classList.toggle('on',!!state.missing);
  const itemMode=state.mode==='item';
  $('evstatus').style.display=itemMode?'none':'';
  $('evrealm').style.display=itemMode?'none':'';
 }
 function renderAll(){
  refreshChips();
  if(state.mode==='item'){
   const list=matchedItems();
   $('evcount').textContent=`筛选结果：${list.length} / ${catalog.length} 种奖励物品`;
   $('evlist').innerHTML=list.map(itemCard).join('')||'<div class="empty">没有符合条件的奖励物品</div>';
   return;
  }
  const list=matchedRows();
  $('evcount').textContent=`筛选结果：${list.length} / ${rows.length} 个奇遇`;
  const groups={};list.forEach(r=>{const key=r.realm_name||'未知境界';(groups[key]=groups[key]||[]).push(r)});
  $('evlist').innerHTML=Object.keys(groups).map(key=>
   `<div class="evgroup">${esc(key)}<span>${groups[key].length} 个</span></div>`+groups[key].map(eventCard).join('')
  ).join('')||'<div class="empty">没有符合条件的奇遇</div>';
 }
 const realmNames=[...new Set(rows.map(r=>r.realm_name||'未知境界'))];
 const realmList=[...new Set(rows.map(r=>String(r.realm||0)))];
 host.innerHTML=sourceHtml(m)+`<div class="cards">${cards}</div>`+
  `<div class="search-panel"><div class="search-fields" style="grid-template-columns:1fr"><label class="search-field"><span>找奇遇 / 结局 / 奖励物品</span><input id="evq" placeholder="输入奇遇名、结局名或奖励物品名称"></label></div></div>`+
  `<div class="chips event-chips" id="evmode"><span class="chip-label">视角</span><button class="chip" data-mode="event">按奇遇</button><button class="chip" data-mode="item">按物品反查</button></div>`+
  `<div class="chips event-chips" id="evstatus"><span class="chip-label">状态</span><button class="chip" data-status="">全部</button><button class="chip" data-status="todo">未达成</button><button class="chip" data-status="done">已达成</button></div>`+
  `<div class="chips event-chips" id="evrealm"><span class="chip-label">境界</span><button class="chip" data-realm="">全部</button>`+
   (st.current_realm?`<button class="chip" data-realm="__current__">当前境界${st.current_realm_name?' · '+esc(st.current_realm_name):''}</button>`:'')+
   realmList.map((value,i)=>`<button class="chip" data-realm="${esc(value)}">${esc(realmNames[i]||('境界 '+value))}</button>`).join('')+`</div>`+
  `<div class="chips event-chips"><button class="chip" id="evmiss">只看有未拥有奖励</button></div>`+
  `<div id="evcount" class="result-info"></div><div id="evlist"></div>`+
  `<div class="tip">结局按品级排列，奖励掉率取自掉落表；已拥有的数量来自当前背包。“位置推断”表示该奇遇没有独立交互点，地点由场景名或母事件继承得到。奇遇结算与对话选择均为只读读取，不会改动存档。</div>`;
 $('evq').value=state.q;
 $('evq').oninput=e=>{state.q=e.target.value;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evmode').onclick=e=>{const b=e.target.closest('[data-mode]');if(!b)return;state.mode=b.dataset.mode;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evstatus').onclick=e=>{const b=e.target.closest('[data-status]');if(!b)return;state.status=b.dataset.status;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evrealm').onclick=e=>{const b=e.target.closest('[data-realm]');if(!b)return;state.realm=b.dataset.realm;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evmiss').onclick=()=>{state.missing=!state.missing;store.set(EVENT_FILTER_KEY,state);renderAll()};
 renderAll();
}
$('warnings').innerHTML=(DATA.warnings||[]).map(esc).join('<br>');initTabs();renderBedroom();initTalent();initItems();initPill();initForge();initEvent();

let polledVersion=INITIAL_VERSION;setInterval(()=>{const script=document.createElement('script');script.src='仙友助手版本.js?t='+Date.now();script.onload=()=>{const next=window.PROGRESS_VERSION||'';if(next&&next!==polledVersion){location.reload();return}polledVersion=next||polledVersion;script.remove()};script.onerror=()=>script.remove();document.head.appendChild(script)},3000);
</script></body></html>"""


def build_html(payload):
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return HTML_TEMPLATE.replace("__CSS__", CSS).replace(
        "__VER__", common.APP_VERSION).replace("__DATA__", data)


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
    version = hashlib.sha256(
        (canonical + "\0" + CSS + "\0" + HTML_TEMPLATE + "\0"
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
