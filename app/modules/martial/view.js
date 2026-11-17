/* 心法与功法：配装体检 + 获取路线（总览 / 心法 / 功法 / 共鸣）。 */
(function(){
const TAB_KEY='worldapart.martial.tab.v1';
const FILTER_KEY='worldapart.martial.filters.v1';
const TABS=[['overview','总览'],['core','心法'],['arts','功法'],['resonance','共鸣'],['build','搭配']];
const FILTER_DEFAULTS={q:'',sect:'',element:'',tier:'',state:'',source:'',mystery:''};
const STATE_CLASS={'已运转':'on','已学会未运转':'learned','卷册在包':'bag','尚未获得':'off','特殊':'special'};
const LEVEL_CLASS={high:'high',mid:'mid',low:'low',info:'info',warn:'warn'};
let tab=store.get(TAB_KEY,'overview');
if(!TABS.some(item=>item[0]===tab))tab='overview';
let filters=Object.assign({},FILTER_DEFAULTS,store.get(FILTER_KEY,{}));
let compareIds=[],compareOpen=false;
let buildCoreIds=[],buildArtIds=[],buildResIds=[],buildQuery='',buildInit=false;
let root=null;

function M(){const payload=DATA.modules.martial||{};return payload.rows||null}
function rowsOf(m,key){return (m&&m[key])||[]}
function tierName(m,tier){
 const start=(m.tier_phase||{})[String(tier)];
 return (start&&(m.phases||{})[String(start)])||(m.phases||{})[String(tier)]||('境界 '+tier);
}
function elementName(m,value){return (m.elements||{})[String(value)]||'待识别'}
function sectName(m,value){
 if(!value)return '通用';
 const sect=(m.sects||[]).find(item=>String(item.id)===String(value));
 return sect?sect.name:('门派 '+value);
}
function itemName(m,book){return ((m.names||{}).item||{})[String(book)]||('卷册 '+book)}
function intimacyLabel(m,need){
 let name='';
 for(const tier of (m.intimacy||[])){
  if(need>=tier.need)name=String(tier.name||'').replace(/[\u200b-\u200d\ufeff]/g,'');
 }
 return name;
}
function stateBadge(state){return `<span class="badge martial-state ${STATE_CLASS[state]||'off'}">${esc(state||'未知')}</span>`}
function sourceBadge(source){return source?`<span class="badge martial-source">${esc(source)}</span>`:''}
function priceText(price){return price?`${esc(price)} 灵石`:'—'}
function shopsText(shops){
 const list=(shops||[]).map(item=>item.name).filter(Boolean);
 return list.length?list.join('、'):'—';
}
function teachText(m,teach){
 if(!teach)return '无记录';
 const label=intimacyLabel(m,teach.affinity);
 return `${esc(tierName(m,teach.realm))} · 好感 ${esc(teach.affinity)}${label?'（'+esc(label)+'）':''} · 消耗 ${esc(teach.cost)}`;
}
function comprehendText(comprehend){
 return comprehend?`${esc(comprehend.time)} 分钟 · 上限 ${esc(comprehend.limit)}`:'无记录';
}

function init(){
 root=$('martial');
 if(!root)return;
 render();
}

function render(){
 const m=M();
 if(!m){root.innerHTML='<div class="empty">心法与功法数据不可用</div>';return}
 root.innerHTML=sourceHtml(DATA.modules.martial||{})
  +`<div class="martial-tabs">${TABS.map(item=>`<button type="button" class="martial-tab${tab===item[0]?' active':''}" data-mtab="${item[0]}">${item[1]}</button>`).join('')}</div>`
  +'<div id="martial-view"></div>';
 root.querySelectorAll('[data-mtab]').forEach(button=>{
  button.addEventListener('click',()=>{tab=button.dataset.mtab;store.set(TAB_KEY,tab);render()});
 });
 const view=$('martial-view');
 if(!rowsOf(m,'core_passives').length){
  view.innerHTML='<div class="empty">心法与功法配置未就绪。<div class="martial-empty-hint">请确认游戏目录可读，或重新导出 martial_meta.json 后再试；存档仍在，刷新页面不会影响进度。</div></div>';
  return;
 }
 if(tab==='overview')view.innerHTML=overviewHtml(m);
 else if(tab==='core'){view.innerHTML=coreTab(m);bindFilters(m,'core')}
 else if(tab==='arts'){view.innerHTML=artsTab(m);bindFilters(m,'arts');bindCompare(m)}
 else if(tab==='build'){view.innerHTML=buildTab(m);bindBuild(m)}
 else view.innerHTML=resonanceHtml(m);
 bindTargets();
}

function uniqueScrolls(m){
 const list=[],seen={};
 (m.bags||[]).filter(item=>!item.learned).forEach(item=>{
  const key=`${item.type}-${item.target}`;
  if(seen[key]){seen[key].count+=Number(item.count)||1;return}
  seen[key]=Object.assign({},item,{count:Number(item.count)||1});
  list.push(seen[key]);
 });
 return list;
}

function heroText(m,pending){
 const issues=m.diagnosis||[];
 const high=issues.filter(item=>item.level==='high').length;
 const mid=issues.filter(item=>item.level==='mid').length;
 const base=high?`有 ${high} 处高优先级问题`:(mid?`配装没有硬伤，有 ${mid} 处可优化`:'配装没有发现问题');
 return pending.length?`${base}；背包还有 ${pending.length} 种卷册待参悟`:`${base}；背包没有待参悟卷册`;
}

function priorityHtml(m){
 const issues=(m.diagnosis||[]).filter(item=>item.level==='high'||item.level==='mid');
 const pending=uniqueScrolls(m);
 const cards=issues.slice(0,3).map(item=>{
  const target=item.target||{};
  return `<button type="button" class="martial-todo ${LEVEL_CLASS[item.level]||'info'}" data-target-kind="${esc(target.kind||'')}" data-target-id="${esc(target.id||0)}">
   <span class="martial-todo-lv">${esc(item.level_name||'')}</span><b>${esc(item.text)}</b><span class="martial-todo-act">去处理</span></button>`;
 });
 if(pending.length){
  cards.push(`<button type="button" class="martial-todo info" data-target-kind="bag" data-target-id="0">
   <span class="martial-todo-lv">提示</span><b>${pending.length} 种卷册在包里没参悟</b><span class="martial-todo-act">看清单</span></button>`);
 }
 if(!cards.length)return '<div class="martial-todo ok"><b>配装检查通过，没有高/中优先级问题</b></div>';
 const more=issues.length>3?`<div class="martial-todo-more">另有 ${issues.length-3} 条，展开下方「完整体检」查看</div>`:'';
 return cards.join('')+more;
}

function resChips(rows,kind){
 const limit=8;
 const chips=rows.slice(0,limit).map(row=>`<button type="button" class="martial-chip martial-chip-btn" data-target-kind="${kind}" data-target-id="${esc(row.id)}">${esc(row.name)}</button>`).join('');
 return chips+(rows.length>limit?`<span class="badge">+${rows.length-limit}</span>`:'');
}

function resourcesHtml(m){
 const idleCores=(m.core_passives||[]).filter(row=>row.state==='已学会未运转');
 const idleArts=(m.arts||[]).filter(row=>row.state==='已学会未运转');
 const idleRes=(m.resonance||[]).filter(row=>row.learned&&!row.installed);
 const scrolls=uniqueScrolls(m);
 const blocks=[];
 if(idleCores.length)blocks.push(`<div class="martial-res-block"><div class="martial-label">心法已学未装 ${idleCores.length}</div><div class="martial-chips">${resChips(idleCores,'core')}</div></div>`);
 if(idleArts.length)blocks.push(`<div class="martial-res-block"><div class="martial-label">功法已学未运转 ${idleArts.length}</div><div class="martial-chips">${resChips(idleArts,'art')}</div></div>`);
 if(idleRes.length)blocks.push(`<div class="martial-res-block"><div class="martial-label">共鸣已学未装 ${idleRes.length}</div><div class="martial-chips">${resChips(idleRes,'resonance')}</div></div>`);
 if(scrolls.length)blocks.push(`<div class="martial-res-block"><div class="martial-label">卷册待参悟 ${scrolls.length} 种</div><div class="martial-scroll-list">${scrolls.map(item=>`<div class="martial-scroll-row"><span class="martial-bag-name">${esc(item.name)}</span><span class="badge">${esc(item.kind)}</span><span class="martial-bag-progress">${esc(item.comprehend)}/${esc(item.limit||'?')}</span>${item.count>1?`<span class="badge">×${esc(item.count)}</span>`:''}</div>`).join('')}</div></div>`);
 return blocks.length?blocks.join(''):'<div class="empty">没有闲置资源</div>';
}

function overviewHtml(m){
 const st=m.stats||{},ch=m.character||{},equip=m.equip||{};
 const spirit=ch.spirit||[];
 const maxPoint=Math.max(1,...spirit.map(item=>Number(item.point)||0));
 const pending=uniqueScrolls(m);
 const hero=`<div class="martial-hero"><div class="martial-hero-top">
   <div class="martial-hero-title">${esc(ch.name||'未知角色')}<span>${esc(ch.sect_name||'未入宗门')} · ${esc(ch.realm||'待识别')}${ch.layer?` · 第 ${esc(ch.layer_index||ch.layer)} 层`:''}</span></div>
   <div class="martial-hero-stats">${[['心法',st.core_used,st.core_total],['功法',st.art_used,st.art_total],['共鸣',st.resonance_used,st.resonance_total]].map(item=>`<div><b>${esc(item[1]||0)}<i>/${esc(item[2]||0)}</i></b><span>${item[0]}</span></div>`).join('')}</div>
  </div><div class="martial-hero-summary">${esc(heroText(m,pending))}</div>
  ${spirit.length?`<div class="martial-spirit martial-spirit-inline">${spirit.map(item=>`<div class="martial-spirit-row"><span class="martial-spirit-name">${esc(item.name)}</span><span class="martial-spirit-bar"><i style="width:${Math.max(2,Math.round((Number(item.point)||0)*100/maxPoint))}%"></i></span><b>${esc(item.point)}</b></div>`).join('')}</div>`:''}
 </div>`;
 const slots=equip.slots||[];
 const slotHtml=slots.length?`<div class="martial-slot-grid" id="martial-core-slots">${slots.map(slot=>{
  const cells=(slot.cells||[]).map(cell=>{
   if(cell.empty)return '<div class="martial-cell empty"><span class="martial-cell-name">空</span><span class="badge martial-state off">待补</span></div>';
   const art=(m.arts||[]).find(item=>Number(item.id)===Number(cell.skill_id))||{};
   return `<button type="button" class="martial-cell" data-target-kind="art" data-target-id="${esc(cell.skill_id)}"><span class="martial-cell-name">${esc(cell.name||'功法 '+cell.skill_id)}</span>${stateBadge(art.state)}<span class="martial-cell-meta">${esc(cell.element_name)} · ${esc(cell.tier_name)}</span></button>`;
  }).join('');
  if(slot.empty)return `<article class="martial-slot" id="martial-core-slot-${esc(slot.slot)}"><div class="martial-slot-head"><span class="martial-slot-no">槽位 ${esc(slot.slot)}</span><span class="badge martial-state off">空槽</span></div><div class="martial-cells">${cells||'<div class="muted">未配置功法格</div>'}</div></article>`;
  return `<article class="martial-slot" id="martial-core-${esc(slot.core_id)}"><div class="martial-slot-head"><span class="martial-slot-no">槽位 ${esc(slot.slot)}</span><span class="martial-slot-name">${esc(slot.name)}</span><span class="badge">${esc(slot.element_name)}</span><span class="badge">${esc(slot.tier_name)}</span></div><div class="martial-cells">${cells||'<div class="muted">未配置功法格</div>'}</div></article>`;
 }).join('')}</div>`:'<div class="empty" id="martial-core-slots">存档未记录心法槽（旧存档或尚未装配）</div>';
 const support=equip.support_slots||[];
 const supportHtml=!equip.support_recorded
  ? '<div class="empty" id="martial-resonance-slots">存档未记录共鸣槽（旧存档）</div>'
  : `<div class="martial-resonance-grid" id="martial-resonance-slots">${support.map(slot=>`<div class="martial-resonance${slot.empty?' empty':''}"><span class="martial-resonance-no">${esc(Number(slot.slot)+1)}</span><span class="martial-resonance-name">${slot.empty?'空':esc(slot.name)}</span>${slot.empty?'':`<span class="badge">${esc(slot.element_name)}</span>`}</div>`).join('')}</div>`;
 const diagnosis=(m.diagnosis||[]).map(item=>`<button type="button" class="martial-diag ${LEVEL_CLASS[item.level]||'info'}" data-target-kind="${esc((item.target||{}).kind||'')}" data-target-id="${esc((item.target||{}).id||0)}"><span class="martial-diag-lv">${esc(item.level_name||'')}</span><span class="martial-diag-text">${esc(item.text)}</span><span class="martial-diag-id">${esc(item.id)}</span></button>`).join('');
 const notes=(m.warnings||[]).length?`<details class="martial-note" id="martial-note"><summary>数据说明（${(m.warnings||[]).length}）</summary><div>${(m.warnings||[]).map(esc).join('<br>')}${((m.catalog_stats||{}).excluded||[]).length?`<br>已排除：${((m.catalog_stats||{}).excluded||[]).map(item=>esc(item.id+' '+item.reason)).join('；')}`:''}</div></details>`:'';
 const plans=(m.plans||[]).map(item=>planCard(item)).join('');
 const schools=(m.schools||[]).map(item=>schoolCard(item)).join('');
 return `${hero}
  <div class="martial-sec-title">优先处理 <span>先解决这些</span></div>
  <div class="martial-todos">${priorityHtml(m)}</div>
  <div class="martial-sec-title">当前配装 <span>点击功法格可跳到功法页</span></div>${slotHtml}
  <div class="martial-sec-title">共鸣技能 <span>${esc(st.resonance_used||0)}/${esc(st.resonance_total||0)}</span></div>${supportHtml}
  <div class="martial-sec-title" id="martial-bag">闲置资源 <span>已学未装 / 卷册 / 共鸣</span></div>
  <div class="martial-res">${resourcesHtml(m)}</div>
  <details class="martial-fold"><summary>本门流派（${(m.schools||[]).length}）<span>门派 · 元素 · 境界一致</span></summary><div class="martial-schools">${schools||'<div class="empty">暂无同门同系组合</div>'}</div></details>
  <details class="martial-fold"><summary>完整体检（${(m.diagnosis||[]).length} 条）<span>高 → 中 → 低 → 提示</span></summary><div class="martial-diags">${diagnosis||'<div class="empty">暂无体检结论</div>'}</div></details>
  <details class="martial-fold"><summary>完整推进方案<span>A 补装 / B 获取</span></summary><div class="martial-plans">${plans||'<div class="empty">暂无可用方案</div>'}</div></details>
  ${notes}`;
}

function confirmBadge(status){return `<span class="badge martial-confirm ${status==='可确认'?'ok':'review'}">${esc(status||'待复核')}</span>`}

function planCard(plan){
 const items=(plan.steps||[]).map((step,index)=>({step,index}));
 const render=item=>{
  const step=item.step,target=step.target||{};
  return `<button type="button" class="martial-step" data-target-kind="${esc(target.kind||'')}" data-target-id="${esc(target.id||0)}">
   <span class="martial-step-no">${item.index+1}</span>
   <span class="martial-step-body"><b>${esc(step.text)}</b>${step.detail?`<i>${esc(step.detail)}</i>`:''}</span>
   ${step.cost?`<span class="martial-step-cost">${esc(step.cost)}</span>`:''}${confirmBadge(step.confirm)}
  </button>`;
 };
 const groups={};
 items.forEach(item=>{const key=item.step.category||'其他';(groups[key]=groups[key]||[]).push(item)});
 const blocks=[];
 ['配置','获取','共鸣','复核','卷册','其他'].forEach(key=>{
  const list=groups[key]||[];
  if(!list.length)return;
  if(key==='卷册'){
   const minutes=list.reduce((sum,item)=>sum+(Number(item.step.minutes)||0),0);
   blocks.push(`<details class="martial-plan-group"><summary>卷册参悟 ${list.length} 种${minutes?` · 合计 ${minutes} 分钟`:''}</summary><div class="martial-steps">${list.map(render).join('')}</div></details>`);
  }else{
   blocks.push(`<div class="martial-steps">${list.map(render).join('')}</div>`);
  }
 });
 const totals=plan.totals||{};
 const parts=[];
 if(Number(totals.price))parts.push(`${esc(totals.price)} 灵石`);
 if(Number(totals.affinity))parts.push(`好感 ${esc(totals.affinity)}`);
 if(Number(totals.minutes))parts.push(`参悟 ${esc(totals.minutes)} 分钟`);
 const totalText=parts.length?`合计：${parts.join(' · ')}`:'不额外消耗资源';
 return `<article class="martial-plan"><div class="martial-plan-head"><b>${esc(plan.title)}</b>${confirmBadge(plan.confirm)}</div>
  <div class="martial-plan-summary">${esc(plan.summary)}</div>
  ${blocks.join('')||'<div class="muted">没有可执行步骤</div>'}
  <div class="martial-plan-total">${totalText}</div>
  ${plan.note?`<div class="martial-same-note">${esc(plan.note)}</div>`:''}</article>`;
}

function schoolCard(school){
 const core=school.core||{};
 const arts=(school.arts||[]).map(item=>`<button type="button" class="martial-chip martial-chip-btn" data-target-kind="art" data-target-id="${esc(item.id)}">${esc(item.name)}${item.mystery?'<i>秘传</i>':''}${item.state==='已学会未运转'?'<i>未运转</i>':item.state==='尚未获得'?'<i>未获得</i>':''}</button>`).join('')||'<span class="muted">无同系功法</span>';
 return `<article class="martial-school"><div class="martial-school-head"><b>${esc(school.name)}</b>${school.current?'<span class="badge">当前门派</span>':''}<span class="badge">${esc(school.element_name||'元素待识别')}</span><span class="badge">${esc(school.tier_name||'境界待识别')}</span>${confirmBadge(school.status)}</div>
  <div class="martial-line"><b>心法</b><button type="button" class="martial-link" data-target-kind="core" data-target-id="${esc(core.id||0)}">${esc(core.name||'—')}</button>${stateBadge(core.state)}${core.slots?`<span class="muted">${esc(core.slots)} 格</span>`:''}</div>
  <div class="martial-line"><b>同系功法</b><span class="martial-chips">${arts}</span></div>
  <div class="martial-plan-total">已学 ${esc(school.learned||0)}/${esc((school.arts||[]).length)} 本${school.note?` · ${esc(school.note)}`:''}</div>
  ${school.caveat?`<div class="martial-same-note">${esc(school.caveat)}</div>`:''}</article>`;
}

function percentText(text){
 const list=String(text||'').match(/\d+(?:\.\d+)?%/g)||[];
 return Array.from(new Set(list)).join(' · ')||'—';
}

function filterOptions(m,rows){
 const sects=(m.sects||[]).map(item=>`<option value="${esc(item.id)}">${esc(item.name)}${item.open?'':'（未开放）'}</option>`).join('');
 const elements=uniq(rows.map(item=>String(item.element))).map(value=>`<option value="${esc(value)}">${esc(elementName(m,value))}</option>`).join('');
 const tiers=uniq(rows.map(item=>String(item.tier))).map(value=>`<option value="${esc(value)}">${esc(tierName(m,value))}</option>`).join('');
 const states=uniq(rows.map(item=>item.state)).map(value=>`<option value="${esc(value)}">${esc(value)}</option>`).join('');
 const sources=uniq(rows.map(item=>item.source)).map(value=>`<option value="${esc(value)}">${esc(value)}</option>`).join('');
 return `<label class="martial-field martial-wide"><span>搜索</span><input data-f="q" placeholder="名称、效果、门派、真意" value="${esc(filters.q)}"></label>
   <label class="martial-field"><span>门派</span><select data-f="sect"><option value="">全部门派</option>${sects}</select></label>
   <label class="martial-field"><span>元素</span><select data-f="element"><option value="">全部元素</option>${elements}</select></label>
   <label class="martial-field"><span>境界</span><select data-f="tier"><option value="">全部境界</option>${tiers}</select></label>
   <label class="martial-field"><span>状态</span><select data-f="state"><option value="">全部状态</option>${states}</select></label>
   <label class="martial-field"><span>来源</span><select data-f="source"><option value="">全部来源</option>${sources}</select></label>`;
}

function coreTab(m){
 return `<div class="martial-filters" id="martial-core-filters">${filterOptions(m,rowsOf(m,'core_passives'))}</div><div id="martial-core-list"></div>`;
}
function artsTab(m){
 return `<div class="martial-filters" id="martial-arts-filters">${filterOptions(m,rowsOf(m,'arts'))}
  <label class="martial-field"><span>秘传</span><select data-f="mystery"><option value="">全部</option><option value="1">仅秘传</option><option value="0">非秘传</option></select></label>
 </div><div id="martial-compare-bar"></div><div id="martial-arts-list"></div>`;
}

function syncFilter(node){
 const key=node.dataset.f;
 if(!(key in FILTER_DEFAULTS))return;
 if(node.tagName==='SELECT'&&![...node.options].some(item=>item.value===String(filters[key]??''))){
  // 切页签或换角色后，旧筛选值可能已不在选项里；不清理会让列表假空。
  filters[key]=FILTER_DEFAULTS[key];
  store.set(FILTER_KEY,filters);
 }
 node.value=filters[key]??'';
}

function bindFilters(m,kind){
 const listId=kind==='core'?'martial-core-list':'martial-arts-list';
 root.querySelectorAll('[data-f]').forEach(node=>{
  syncFilter(node);
  node.addEventListener(node.tagName==='INPUT'?'input':'change',()=>{
   filters[node.dataset.f]=node.value;store.set(FILTER_KEY,filters);
   const list=$(listId);
   if(list)list.innerHTML=kind==='core'?coreListHtml(m):artsListHtml(m);
  });
 });
 const list=$(listId);
 if(list)list.innerHTML=kind==='core'?coreListHtml(m):artsListHtml(m);
}

function matches(row,kind){
 const q=filters.q.trim().toLowerCase();
 if(q){
  const text=[row.name,row.desc,row.sect_name,row.element_name,row.tier_name,row.stack,row.source,row.desc]
   .concat((row.tiers||[]).map(item=>`${item.name} ${item.desc}`)).join(' ').toLowerCase();
  if(!text.includes(q))return false;
 }
 if(filters.sect&&String(row.sect)!==filters.sect)return false;
 if(filters.element&&String(row.element)!==filters.element)return false;
 if(filters.tier&&String(row.tier)!==filters.tier)return false;
 if(filters.state&&row.state!==filters.state)return false;
 if(filters.source&&row.source!==filters.source)return false;
 if(kind==='arts'&&filters.mystery==='1'&&!row.mystery)return false;
 if(kind==='arts'&&filters.mystery==='0'&&row.mystery)return false;
 return true;
}

function coreListHtml(m){
 const rows=rowsOf(m,'core_passives').filter(row=>matches(row,'core'));
 if(!rows.length)return '<div class="empty">没有符合条件的心法</div>';
 return `<div class="martial-result">共 ${rows.length} 本心法</div>`+rows.map(row=>coreCard(m,row)).join('');
}

function coreCard(m,row){
 const tiers=(row.tiers||[]).length
  ? `<table class="martial-tiers"><thead><tr><th>需求</th><th>真意</th><th>效果</th></tr></thead><tbody>${row.tiers.map(item=>`<tr><td class="martial-need">${esc(item.need)} ${esc(row.unit)}</td><td>${esc(item.name||'—')}</td><td>${esc(item.desc||'—')}</td></tr>`).join('')}</tbody></table>`
  : '<div class="muted">无真意档位</div>';
 const init=(row.init_arts||[]).length
  ? row.init_arts.map(item=>`<span class="martial-chip">${esc(item.name)}${item.book?'':'<i>入门</i>'}</span>`).join('')
  : '—';
 const same=(row.same_name||[]).length
  ? `<div class="martial-same-block"><div class="martial-label">同名不同境界</div>${row.same_name.map(item=>`<div class="martial-same"><b>${esc(item.tier_name)}版</b> ${esc(item.desc||'—')}</div>`).join('')}<div class="martial-same-note">只做原文对照，不推断升阶关系。</div></div>`
  : '';
 return `<details class="martial-card" id="mc-${esc(row.id)}"><summary>
   <span class="martial-name">${esc(row.name)}</span>
   <span class="badge">${esc(row.sect_name)}</span><span class="badge">${esc(row.element_name)}</span><span class="badge">${esc(row.tier_name)}</span>
   ${stateBadge(row.state)}${sourceBadge(row.source)}
  </summary><div class="martial-body">
   <div class="martial-desc">${esc(row.desc||'暂无说明')}</div>
   <div class="martial-cols">
    <div class="martial-block"><div class="martial-label">心法真意（${esc(row.stack||'层数')}）</div>${tiers}</div>
    <div class="martial-block"><div class="martial-label">基础信息</div>
     <div class="martial-line"><b>初始功法</b>${init}</div>
     <div class="martial-line"><b>卷册</b>${row.book?`${esc(itemName(m,row.book))}（${priceText(row.price)}）`:'无卷册'}</div>
     <div class="martial-line"><b>请教</b>${teachText(m,row.teach)}</div>
     <div class="martial-line"><b>参悟</b>${comprehendText(row.comprehend)}</div>
     <div class="martial-line"><b>货架</b>${esc(shopsText(row.shops))}</div>
    </div>
   </div>${same}
  </div></details>`;
}

function artsListHtml(m){
 const rows=rowsOf(m,'arts').filter(row=>matches(row,'arts'));
 if(!rows.length)return '<div class="empty">没有符合条件的功法</div>';
 return `<div class="martial-result">共 ${rows.length} 本功法</div>`+rows.map(row=>artCard(m,row)).join('');
}

function artCard(m,row){
 const costs=(row.costs||[]).filter(item=>Number(item.value)).map(item=>item.value);
 const owners=(row.init_of||[]).map(item=>item.name).join('、');
 return `<details class="martial-art" id="ma-${esc(row.id)}"><summary>
   <span class="martial-name">${esc(row.name)}</span>
   <span class="badge">${esc(row.sect_name)}</span><span class="badge">${esc(row.element_name)}</span><span class="badge">${esc(row.tier_name)}</span>
   ${row.mystery?'<span class="badge martial-mystery">秘传</span>':''}
   ${stateBadge(row.state)}${sourceBadge(row.source)}
   <label class="martial-pick"><input type="checkbox" data-cmp="${esc(row.id)}"${compareIds.includes(String(row.id))?' checked':''}><span>对比</span></label>
   <span class="martial-price">${priceText(row.price)}</span>
  </summary><div class="martial-body">
   <div class="martial-desc">${esc(row.desc||'暂无说明')}</div>
   <div class="martial-cols">
    <div class="martial-block"><div class="martial-label">获取</div>
     <div class="martial-line"><b>卷册</b>${row.book?`${esc(itemName(m,row.book))}（${priceText(row.price)}）`:'无卷册'}</div>
     <div class="martial-line"><b>货架</b>${esc(shopsText(row.shops))}</div>
     <div class="martial-line"><b>请教</b>${row.teach&&row.teach.visible?teachText(m,row.teach):'无记录'}</div>
     <div class="martial-line"><b>入门自带</b>${owners?esc(owners):'—'}</div>
    </div>
    <div class="martial-block"><div class="martial-label">基础信息</div>
     <div class="martial-line"><b>参悟</b>${comprehendText(row.comprehend)}</div>
     <div class="martial-line"><b>消耗</b>${costs.length?esc(costs.join(' / ')):'—'}</div>
     <div class="martial-line"><b>状态</b>${esc(row.state)}${row.in_bag?' · 卷册在包':''}</div>
    </div>
   </div>
  </div></details>`;
}

function bindCompare(m){
 renderCompareBar(m);
 root.querySelectorAll('[data-cmp]').forEach(node=>{
  const label=node.closest('label');
  if(label)label.addEventListener('click',event=>event.stopPropagation());
  node.addEventListener('change',()=>{
   const id=String(node.dataset.cmp);
   if(node.checked){
    if(compareIds.length>=4){node.checked=false;renderCompareBar(m,'最多同时对比 4 本');return}
    if(!compareIds.includes(id))compareIds.push(id);
   }else{
    compareIds=compareIds.filter(item=>item!==id);
   }
   compareOpen=false;
   renderCompareBar(m);
  });
 });
}

function compareRows(m){
 return compareIds.map(id=>rowsOf(m,'arts').find(row=>String(row.id)===id)).filter(Boolean);
}

function renderCompareBar(m,hint){
 const bar=$('martial-compare-bar');
 if(!bar)return;
 bar.innerHTML=compareBar(m,hint);
 bar.querySelectorAll('[data-cmp-remove]').forEach(button=>{
  button.addEventListener('click',()=>{
   compareIds=compareIds.filter(id=>id!==String(button.dataset.cmpRemove));
   compareOpen=false;syncComparePicks();renderCompareBar(m);
  });
 });
 const run=bar.querySelector('[data-cmp-run]');
 if(run)run.addEventListener('click',()=>{compareOpen=true;renderCompareBar(m)});
 const clear=bar.querySelector('[data-cmp-clear]');
 if(clear)clear.addEventListener('click',()=>{compareIds=[];compareOpen=false;syncComparePicks();renderCompareBar(m)});
}

function syncComparePicks(){
 root.querySelectorAll('[data-cmp]').forEach(node=>{node.checked=compareIds.includes(String(node.dataset.cmp))});
}

function compareBar(m,hint){
 if(!compareIds.length)return '';
 const rows=compareRows(m);
 const chips=rows.map(row=>`<button type="button" class="martial-chip martial-chip-btn" data-cmp-remove="${esc(row.id)}">${esc(row.name)} ×</button>`).join('');
 return `<div class="martial-compare-bar"><span class="martial-compare-title">对比 ${rows.length}/4</span><span class="martial-chips">${chips}</span>
  ${hint?`<span class="martial-compare-hint">${esc(hint)}</span>`:''}
  <button type="button" class="martial-compare-btn" data-cmp-run${rows.length<2?' disabled':''}>${rows.length<2?'至少选 2 本':'生成对比'}</button>
  <button type="button" class="martial-compare-clear" data-cmp-clear>清空</button></div>${compareOpen?compareTable(rows):''}`;
}

function compareTable(rows){
 const metrics=[
  ['门派',row=>esc(row.sect_name||'—')],
  ['元素',row=>esc(row.element_name||'—')],
  ['境界',row=>esc(row.tier_name||'—')],
  ['秘传',row=>row.mystery?'是':'否'],
  ['状态',row=>stateBadge(row.state)],
  ['来源',row=>esc(row.source||'—')],
  ['价格',row=>priceText(row.price)],
  ['消耗',row=>{const list=(row.costs||[]).map(item=>Number(item.value)).filter(Boolean);return list.length?esc(list.join(' / ')):'—'}],
  ['原文数值',row=>esc(percentText(row.desc))],
  ['效果原文',row=>`<span class="martial-compare-desc">${esc(row.desc||'—')}</span>`],
  ['参悟',row=>esc(comprehendText(row.comprehend))],
 ];
 return `<div class="martial-compare-wrap"><table class="martial-compare"><thead><tr><th>维度</th>${rows.map(row=>`<th><button type="button" class="martial-link" data-target-kind="art" data-target-id="${esc(row.id)}">${esc(row.name)}</button>${row.mystery?'<span class="badge martial-mystery">秘传</span>':''}</th>`).join('')}</tr></thead><tbody>${metrics.map(item=>`<tr><th>${esc(item[0])}</th>${rows.map(row=>`<td>${item[1](row)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
  <div class="martial-same-note">只做并列对照，不排序、不显示推荐指数；数值直接从效果原文提取。</div>`;
}

function buildTab(m){
 const cap=Math.max(1,Number((m.stats||{}).resonance_total)||4);
 return `<div class="martial-build-hint">顺序：先定心法（决定元素与真意档位）→ 选共鸣（检查「携带 X 系心法」条件）→ 最后补功法。</div>
 <div class="martial-builder">
  <div class="martial-build-picks">
   <div class="martial-build-sec"><div class="martial-label">1. 心法 <span id="martial-build-core-count">0/3</span></div>
    <div class="martial-build-actions"><button type="button" class="martial-compare-btn" id="martial-build-auto">按共鸣条件补心法</button><button type="button" class="martial-compare-clear" id="martial-build-current">读取当前配装</button><button type="button" class="martial-compare-clear" id="martial-build-reset">清空</button></div>
    <div class="martial-build-list" id="martial-build-cores"></div>
   </div>
   <div class="martial-build-sec"><div class="martial-label">2. 共鸣 <span id="martial-build-res-count">0/${esc(cap)}</span></div>
    <div class="martial-build-list" id="martial-build-res"></div>
   </div>
   <div class="martial-build-sec"><div class="martial-label">3. 功法 <span id="martial-build-count">0/4</span></div>
    <input class="martial-build-search" id="martial-build-search" placeholder="搜索功法名、门派、元素">
    <div class="martial-build-list" id="martial-build-arts"></div>
   </div>
  </div>
  <div class="martial-build-result" id="martial-build-result"></div>
 </div>`;
}

function coreById(m,id){return rowsOf(m,'core_passives').find(row=>String(row.id)===String(id))||null}
function buildCores(m){return buildCoreIds.map(id=>coreById(m,id)).filter(Boolean)}
function buildArts(m){return buildArtIds.map(id=>rowsOf(m,'arts').find(row=>String(row.id)===id)).filter(Boolean)}
function buildRes(m){return buildResIds.map(id=>rowsOf(m,'resonance').find(row=>String(row.id)===id)).filter(Boolean)}

function spiritOf(m,element){
 const item=(m.character.spirit||[]).find(row=>Number(row.element)===Number(element));
 return item?Number(item.point)||0:0;
}

function coreTierInfo(m,core){
 const points=spiritOf(m,core.element);
 const tiers=core.tiers||[];
 const unlocked=tiers.filter(item=>Number(item.need)<=points).length;
 const next=tiers.find(item=>Number(item.need)>points)||null;
 return {points:points,unlocked:unlocked,total:tiers.length,next:next};
}

function sameCore(row,core){
 if(!core)return false;
 const sect=!Number(core.sect)||Number(row.sect)===Number(core.sect);
 const elem=!Number(core.element)||Number(row.element)===Number(core.element);
 const tier=!Number(core.tier)||Number(row.tier)===Number(core.tier);
 return sect&&elem&&tier;
}

function coreMatchRank(row,core){
 if(!core)return 3;
 let rank=0;
 if(Number(core.sect)&&Number(row.sect)!==Number(core.sect))rank+=2;
 if(Number(core.element)&&Number(row.element)!==Number(core.element))rank+=1;
 if(Number(core.tier)&&Number(row.tier)!==Number(core.tier))rank+=1;
 return rank;
}

function elementIdByName(m,name){
 const hit=Object.keys(m.elements||{}).find(key=>m.elements[key]===name);
 return hit?Number(hit):0;
}

function resonanceCondition(m,row){
 const text=String(row.desc||'');
 const hit=text.match(/携带((?:炼气|筑基|结丹|元婴|化神|炼虚|合体|大乘)(?:或(?:炼气|筑基|结丹|元婴|化神|炼虚|合体|大乘))*)?\s*([金木水火土])系心法/);
 if(hit){
  return {text:hit[0],element:elementIdByName(m,hit[2]),need:hit[2],realms:hit[1]?hit[1].split('或'):[],kind:'carry'};
 }
 const tag=text.match(/【([金木水火土])[^】]*?([金木水火土])】/);
 if(tag&&tag[1]!==tag[2]){
  return {text:tag[0],element:elementIdByName(m,tag[2]),need:tag[2],realms:[],from:tag[1],kind:'synergy'};
 }
 if(text.includes('当前选中心法同系')){
  return {text:'当前选中心法同系',element:0,need:'',realms:[],kind:'follower'};
 }
 return null;
}

function condLabel(cond){
 if(!cond)return '无跨系条件';
 if(cond.kind==='follower')return '随当前心法元素';
 if(cond.kind==='synergy')return `相生 ${cond.from}→${cond.need}（需${cond.need}系心法）`;
 return `需${cond.realms.length?cond.realms.join('/')+' ':''}${cond.need}系心法`;
}

function conditionMet(cores,cond){
 if(!cond)return false;
 if(cond.kind==='follower')return cores.length>0;
 return cores.some(core=>Number(core.element)===Number(cond.element)
  &&(!cond.realms.length||cond.realms.some(realm=>String(core.tier_name||'').startsWith(realm))));
}

function loadCurrentBuild(m){
 const equip=m.equip||{};
 buildCoreIds=(equip.slots||[]).map(slot=>slot.core_id?String(slot.core_id):'').filter(Boolean).slice(0,3);
 buildArtIds=[];
 (equip.slots||[]).forEach(slot=>(slot.cells||[]).forEach(cell=>{
  if(cell.skill_id&&buildArtIds.length<4)buildArtIds.push(String(cell.skill_id));
 }));
 buildResIds=(equip.support_slots||[]).map(slot=>slot.skill_id?String(slot.skill_id):'').filter(Boolean).slice(0,4);
}

function bindBuild(m){
 if(!buildInit){loadCurrentBuild(m);buildInit=true}
 const search=$('martial-build-search');
 search.value=buildQuery;
 search.addEventListener('input',()=>{buildQuery=search.value;renderBuildArts(m)});
 $('martial-build-auto').addEventListener('click',()=>autoBuild(m));
 $('martial-build-current').addEventListener('click',()=>{loadCurrentBuild(m);syncBuild(m)});
 $('martial-build-reset').addEventListener('click',()=>{buildCoreIds=[];buildArtIds=[];buildResIds=[];syncBuild(m)});
 syncBuild(m);
}

function syncBuild(m){renderCoreList(m);renderBuildRes(m);renderBuildArts(m);renderBuildResult(m)}

function updateBuildCount(m){
 const cap=Math.max(1,Number((m.stats||{}).resonance_total)||4);
 const cores=$('martial-build-core-count'),arts=$('martial-build-count'),res=$('martial-build-res-count');
 if(cores)cores.textContent=`${buildCoreIds.length}/3`;
 if(arts)arts.textContent=`${buildArtIds.length}/4`;
 if(res)res.textContent=`${buildResIds.length}/${cap}`;
}

function renderCoreList(m){
 const box=$('martial-build-cores');
 if(!box)return;
 const rows=rowsOf(m,'core_passives').slice().sort((a,b)=>
  (buildCoreIds.includes(String(b.id))?0:1)-(buildCoreIds.includes(String(a.id))?0:1)
  ||Number(a.sect)-Number(b.sect)||Number(a.tier)-Number(b.tier)||Number(a.id)-Number(b.id));
 box.innerHTML=rows.map(row=>{
  const info=coreTierInfo(m,row);
  return `<label class="martial-build-row${buildCoreIds.includes(String(row.id))?' match':''}"><input type="checkbox" data-build-core="${esc(row.id)}"${buildCoreIds.includes(String(row.id))?' checked':''}><span class="martial-build-name">${esc(row.name)}</span><span class="badge">${esc(row.element_name)}</span><span class="badge">${esc(row.tier_name)}</span><span class="badge">灵根 ${esc(info.points)}</span><span class="badge">真意 ${esc(info.unlocked)}/${esc(info.total)}</span>${stateBadge(row.state)}</label>`;
 }).join('');
 box.querySelectorAll('[data-build-core]').forEach(node=>node.addEventListener('change',()=>{
  const id=String(node.dataset.buildCore);
  if(node.checked){
   if(buildCoreIds.length>=3){node.checked=false;return}
   buildCoreIds.push(id);
  }else{
   buildCoreIds=buildCoreIds.filter(item=>item!==id);
  }
  updateBuildCount(m);renderBuildArts(m);renderBuildResult(m);
 }));
 updateBuildCount(m);
}

function renderBuildRes(m){
 const box=$('martial-build-res');
 if(!box)return;
 const cap=Math.max(1,Number((m.stats||{}).resonance_total)||4);
 const rows=rowsOf(m,'resonance');
 box.innerHTML=rows.length?rows.map(row=>{
  const cond=resonanceCondition(m,row);
  return `<label class="martial-build-row"><input type="checkbox" data-build-res="${esc(row.id)}"${buildResIds.includes(String(row.id))?' checked':''}${!buildResIds.includes(String(row.id))&&buildResIds.length>=cap?' disabled':''}><span class="martial-build-name">${esc(row.name)}</span><span class="badge">${esc(row.element_name)}</span><span class="badge">${esc(condLabel(cond))}</span>${stateBadge(row.state)}</label>`;
 }).join(''):'<div class="muted">暂无共鸣技能</div>';
 box.querySelectorAll('[data-build-res]').forEach(node=>node.addEventListener('change',()=>{
  const id=String(node.dataset.buildRes);
  if(node.checked){
   if(buildResIds.length>=cap){node.checked=false;return}
   buildResIds.push(id);
  }else{
   buildResIds=buildResIds.filter(item=>item!==id);
  }
  updateBuildCount(m);renderBuildResult(m);
 }));
 updateBuildCount(m);
}

function renderBuildArts(m){
 const box=$('martial-build-arts');
 if(!box)return;
 const cores=buildCores(m);
 const q=buildQuery.trim().toLowerCase();
 let rows=rowsOf(m,'arts');
 if(q)rows=rows.filter(row=>[row.name,row.sect_name,row.element_name,row.tier_name].join(' ').toLowerCase().includes(q));
 rows=rows.slice().sort((a,b)=>{
  const rank=row=>cores.length?Math.min.apply(null,cores.map(core=>coreMatchRank(row,core))):3;
  return rank(a)-rank(b)||((a.state==='尚未获得')?1:0)-((b.state==='尚未获得')?1:0)||Number(a.id)-Number(b.id);
 });
 box.innerHTML=rows.length?rows.map(row=>{
  const matched=cores.some(core=>sameCore(row,core));
  return `<label class="martial-build-row${matched?' match':''}"><input type="checkbox" data-build-art="${esc(row.id)}"${buildArtIds.includes(String(row.id))?' checked':''}><span class="martial-build-name">${esc(row.name)}</span><span class="badge">${esc(row.sect_name)}</span><span class="badge">${esc(row.element_name)}</span><span class="badge">${esc(row.tier_name)}</span>${row.mystery?'<span class="badge martial-mystery">秘传</span>':''}${stateBadge(row.state)}</label>`;
 }).join(''):'<div class="muted">没有匹配的功法</div>';
 box.querySelectorAll('[data-build-art]').forEach(node=>node.addEventListener('change',()=>{
  const id=String(node.dataset.buildArt);
  if(node.checked){
   if(buildArtIds.length>=4){node.checked=false;return}
   buildArtIds.push(id);
  }else{
   buildArtIds=buildArtIds.filter(item=>item!==id);
  }
  updateBuildCount(m);renderBuildResult(m);
 }));
 updateBuildCount(m);
}

function autoBuild(m){
 const all=rowsOf(m,'core_passives');
 const chosen=buildCores(m);
 const wanted=[];
 buildRes(m).forEach(row=>{
  const cond=resonanceCondition(m,row);
  if(cond&&!conditionMet(chosen,cond)&&!wanted.includes(cond.element))wanted.push(cond.element);
 });
 wanted.forEach(element=>{
  if(buildCoreIds.length>=3)return;
  const pick=all.filter(row=>Number(row.element)===Number(element)&&!buildCoreIds.includes(String(row.id)))
   .sort((a,b)=>((a.state==='尚未获得')?1:0)-((b.state==='尚未获得')?1:0)||Number(b.tier)-Number(a.tier))[0];
  if(pick)buildCoreIds.push(String(pick.id));
 });
 syncBuild(m);
}

function renderBuildResult(m){
 const box=$('martial-build-result');
 if(!box)return;
 box.innerHTML=buildResultHtml(m);
 box.querySelectorAll('[data-build-remove]').forEach(button=>button.addEventListener('click',()=>{
  buildArtIds=buildArtIds.filter(id=>id!==String(button.dataset.buildRemove));
  renderBuildArts(m);renderBuildResult(m);
 }));
}

function buildResultHtml(m){
 const cores=buildCores(m),res=buildRes(m),arts=buildArts(m);
 const tierTotal=cores.reduce((sum,core)=>sum+(core.tiers||[]).length,0);
 const tierUnlocked=cores.reduce((sum,core)=>sum+coreTierInfo(m,core).unlocked,0);
 const conds=res.map(row=>({row:row,cond:resonanceCondition(m,row)}));
 const known=conds.filter(item=>item.cond).length;
 const met=conds.filter(item=>item.cond&&conditionMet(cores,item.cond)).length;
 const issues=[];
 cores.forEach(core=>{if(core.state==='尚未获得')issues.push(`「${core.name}」尚未获得，当前只是试算`)});
 if(cores.length<3)issues.push(`心法 ${cores.length}/3`);
 if(res.length<4)issues.push(`共鸣 ${res.length}/4`);
 if(arts.length<4)issues.push(`功法 ${arts.length}/4`);
 const unmatched=arts.filter(row=>!cores.some(core=>sameCore(row,core)));
 if(unmatched.length)issues.push(`${unmatched.length} 本功法没有匹配的心法：${unmatched.map(row=>row.name).join('、')}`);
 conds.filter(item=>item.cond&&!conditionMet(cores,item.cond)).forEach(item=>{
  issues.push(`共鸣「${item.row.name}」${condLabel(item.cond)}，当前未满足`);
 });
 const coreBlocks=cores.map(core=>{
  const info=coreTierInfo(m,core);
  const chips=(core.tiers||[]).map(item=>{
   const on=Number(item.need)<=info.points;
   return `<span class="martial-chip${on?'':' off'}">${esc(item.need)} ${esc(core.unit||'层')} · ${esc(item.name||'—')}${on?' ✓':''}</span>`;
  }).join('');
  return `<div class="martial-build-core"><div class="martial-build-core-head"><b>${esc(core.name)}</b><span class="badge">${esc(core.element_name)}</span><span class="badge">${esc(core.tier_name)}</span>${stateBadge(core.state)}</div>
   <div class="martial-build-core-meta">灵根 ${esc(info.points)} 点 → 解锁 ${esc(info.unlocked)}/${esc(info.total)} 档${info.next?`；下一档需 ${esc(info.next.need)} 点，差 ${esc(info.next.need-info.points)}`:'；已满档'}</div>
   <div class="martial-chips">${chips||'<span class="muted">无真意档位</span>'}</div></div>`;
 }).join('');
 const condRows=conds.length?conds.map(item=>{
  const ok=conditionMet(cores,item.cond);
  return `<div class="martial-build-cond ${ok?'ok':'warn'}"><b>${esc(item.row.name)}</b><span class="badge">${esc(item.row.element_name)}</span><span class="badge">${esc(condLabel(item.cond))}</span><span class="martial-build-cond-state">${ok?'已满足':(item.cond?'未满足':'无需满足')}</span></div>`;
 }).join(''):'<div class="muted">还没选共鸣</div>';
 const artRows=arts.length?arts.map(row=>{
  const matches=cores.filter(core=>sameCore(row,core));
  return `<div class="martial-build-cond ${matches.length?'ok':'warn'}"><b>${esc(row.name)}</b><span class="badge">${esc(row.element_name)}</span><span class="badge">${esc(row.tier_name)}</span>${matches.length?`<span class="martial-build-cond-state">匹配 ${esc(matches.map(core=>core.name).join('、'))}</span>`:'<span class="martial-build-cond-state">无心法匹配</span>'}</div>`;
 }).join(''):'<div class="muted">还没选功法</div>';
 return `<div class="martial-build-summary ${issues.length?'warn':'ok'}">
   <div class="martial-build-conclusion">${issues.length?`有 ${issues.length} 项待处理`:'心法、共鸣、功法结构完整'}</div>
   <div class="martial-build-metrics">
    <div><b>${cores.length}/3</b><span>心法</span></div>
    <div><b>${res.length}/4</b><span>共鸣</span></div>
    <div><b>${arts.length}/4</b><span>功法</span></div>
    <div><b>${tierUnlocked}/${tierTotal||0}</b><span>真意档位</span></div>
    <div><b>${met}/${known||0}</b><span>共鸣条件</span></div>
   </div>
  </div>
  <div class="martial-build-block"><div class="martial-label">待处理</div>
   ${issues.length?issues.map(text=>`<div class="martial-build-issue">· ${esc(text)}</div>`).join(''):'<div class="martial-build-issue ok">当前组合没有发现结构问题</div>'}
   <div class="martial-same-note">真意档位 = 该元素灵根点 ≥ 配置阈值；灵根点来自存档，阈值来自心法 sub_passives。</div>
   <div class="martial-same-note">共鸣条件从效果原文提取「携带 X 系心法」与【X…Y】相生标签，未识别的不计入统计。</div>
   <div class="martial-same-note">不计算伤害倍率，也不给推荐指数。</div>
  </div>
  <div class="martial-build-block"><div class="martial-label">心法 · 元素与真意</div>${coreBlocks||'<div class="muted">还没选心法</div>'}</div>
  <div class="martial-build-block"><div class="martial-label">共鸣 · 相生条件</div>${condRows}</div>
  <div class="martial-build-block"><div class="martial-label">功法 · 与心法匹配</div>${artRows}</div>`;
}

function resonanceHtml(m){
 const rows=rowsOf(m,'resonance');
 if(!rows.length)return '<div class="empty">暂无共鸣技能配置</div>';
 return `<div class="martial-result">共 ${rows.length} 个共鸣技能；已学 ${rows.filter(item=>item.learned).length} 个，已装 ${rows.filter(item=>item.installed).length} 个</div>
  <div class="martial-resonance-list">${rows.map(row=>{
   const unlock=row.source==='npc'
    ? `与${esc(row.npc_name||('NPC '+row.npc))}完成双修后获得（道侣不是条件）`
    : '来源未开放';
   const realm=row.realm_recorded?(row.realm!=null?`共鸣 ${esc(row.realm)} 重`:'未记录'):'未记录（旧存档）';
   return `<article class="martial-rescard" id="mr-${esc(row.id)}"><div class="martial-reshead"><span class="martial-name">${esc(row.name)}</span><span class="badge">${esc(row.element_name)}</span><span class="badge">${esc(row.unlock_realm||tierName(m,row.tier))}</span>${stateBadge(row.state)}</div>
    <div class="martial-desc">${esc(row.desc||'暂无说明')}</div>
    <div class="martial-line"><b>解锁</b>${unlock}${row.unlock_realm?` · ${esc(row.unlock_realm)}`:''}</div>
    <div class="martial-line"><b>共鸣境界</b>${realm}</div>
    ${row.source!=='npc'?'<div class="martial-same-note">该技能当前没有可用获取来源，保留展示以便后续版本更新。</div>':''}
   </article>`;
  }).join('')}</div>`;
}

function bindTargets(){
 root.querySelectorAll('[data-target-kind]').forEach(node=>{
  node.addEventListener('click',()=>{
   const kind=node.dataset.targetKind,id=node.dataset.targetId;
   focusTarget(kind,id);
  });
 });
}

function focusTarget(kind,id){
 const nextTab={core:'core',art:'arts',resonance:'resonance',core_slots:'overview',resonance_slots:'overview',bag:'overview',warning:'overview'}[kind];
 if(!nextTab)return;
 if(tab!==nextTab){tab=nextTab;store.set(TAB_KEY,tab);render()}
 requestAnimationFrame(()=>{
  let target=null;
  if(kind==='core')target=$('mc-'+id);
  else if(kind==='art')target=$('ma-'+id);
  else if(kind==='resonance')target=$('mr-'+id);
  else if(kind==='core_slots')target=$('martial-core-slots');
  else if(kind==='resonance_slots')target=$('martial-resonance-slots');
  else if(kind==='bag')target=$('martial-bag');
  else if(kind==='warning')target=$('martial-note');
  if(!target)return;
  if(target.tagName==='DETAILS')target.open=true;
  target.scrollIntoView({behavior:'smooth',block:'center'});
  target.classList.add('martial-flash');
  setTimeout(()=>target.classList.remove('martial-flash'),1200);
 });
}

window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['martial']=init;
})();
