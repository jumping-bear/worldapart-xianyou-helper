/* 心法与功法：配装体检 + 获取路线（总览 / 心法 / 功法 / 共鸣）。 */
(function(){
const TAB_KEY='worldapart.martial.tab.v1';
const FILTER_KEY='worldapart.martial.filters.v1';
const TABS=[['overview','总览'],['core','心法'],['arts','功法'],['resonance','共鸣']];
const FILTER_DEFAULTS={q:'',sect:'',element:'',tier:'',state:'',source:'',mystery:''};
const STATE_CLASS={'已运转':'on','已学会未运转':'learned','卷册在包':'bag','尚未获得':'off','特殊':'special'};
const LEVEL_CLASS={high:'high',mid:'mid',low:'low',info:'info',warn:'warn'};
let tab=store.get(TAB_KEY,'overview');
if(!TABS.some(item=>item[0]===tab))tab='overview';
let filters=Object.assign({},FILTER_DEFAULTS,store.get(FILTER_KEY,{}));
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
 else if(tab==='arts'){view.innerHTML=artsTab(m);bindFilters(m,'arts')}
 else view.innerHTML=resonanceHtml(m);
 bindTargets();
}

function overviewHtml(m){
 const st=m.stats||{},ch=m.character||{},equip=m.equip||{};
 const spirit=ch.spirit||[];
 const maxPoint=Math.max(1,...spirit.map(item=>Number(item.point)||0));
 const cards=[
  ['心法槽',`${st.core_used||0}/${st.core_total||0}`,'已装 / 槽位'],
  ['已运转功法',`${st.art_used||0}/${st.art_total||0}`,'运转 / 已学'],
  ['共鸣技能',`${st.resonance_used||0}/${st.resonance_total||0}`,'已装 / 槽位'],
  ['体检结论',`${st.issues||0}`,'条'],
 ];
 const cardHtml=cards.map(item=>`<div class="card martial-card-stat"><div class="k">${item[0]}</div><div class="v">${esc(item[1])}<span>${item[2]}</span></div></div>`).join('');
 const equipHtml=`<div class="martial-equip">
  <div class="martial-equip-main">
   <div><span>角色</span><b>${esc(ch.name||'未知角色')}</b></div>
   <div><span>门派</span><b>${esc(ch.sect_name||'未入宗门')}</b></div>
   <div><span>境界</span><b>${esc(ch.realm||'待识别')}${ch.layer?` · 第 ${esc(ch.layer_index||ch.layer)} 层`:''}</b></div>
  </div>
  <div class="martial-spirit">${spirit.length?spirit.map(item=>`<div class="martial-spirit-row"><span class="martial-spirit-name">${esc(item.name)}</span><span class="martial-spirit-bar"><i style="width:${Math.max(2,Math.round((Number(item.point)||0)*100/maxPoint))}%"></i></span><b>${esc(item.point)}</b></div>`).join(''):'<span class="muted">五行灵根未记录</span>'}</div>
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
  : `<div class="martial-resonance-grid" id="martial-resonance-slots">${support.map(slot=>`<div class="martial-resonance${slot.empty?' empty':''}"><span class="martial-resonance-no">${esc(slot.slot)}</span><span class="martial-resonance-name">${slot.empty?'空':esc(slot.name)}</span>${slot.empty?'':`<span class="badge">${esc(slot.element_name)}</span>`}</div>`).join('')}</div>`;
 const diagnosis=(m.diagnosis||[]).map(item=>`<button type="button" class="martial-diag ${LEVEL_CLASS[item.level]||'info'}" data-target-kind="${esc((item.target||{}).kind||'')}" data-target-id="${esc((item.target||{}).id||0)}"><span class="martial-diag-lv">${esc(item.level_name||'')}</span><span class="martial-diag-text">${esc(item.text)}</span><span class="martial-diag-id">${esc(item.id)}</span></button>`).join('');
 const bag=(m.bags||[]).filter(item=>!item.learned);
 const bagHtml=bag.length?bag.map(item=>`<div class="martial-bag-row"><span class="martial-bag-name">${esc(item.name)}</span><span class="badge">${esc(item.kind)}</span><span class="martial-bag-progress">${esc(item.comprehend)}/${esc(item.limit||'?')}</span>${item.count>1?`<span class="badge">×${esc(item.count)}</span>`:''}</div>`).join(''):'<div class="muted">背包里没有未参悟的卷册</div>';
 const notes=(m.warnings||[]).length?`<details class="martial-note" id="martial-note"><summary>数据说明（${(m.warnings||[]).length}）</summary><div>${(m.warnings||[]).map(esc).join('<br>')}${((m.catalog_stats||{}).excluded||[]).length?`<br>已排除：${((m.catalog_stats||{}).excluded||[]).map(item=>esc(item.id+' '+item.reason)).join('；')}`:''}</div></details>`:'';
 return `<div class="cards martial-cards">${cardHtml}</div>${equipHtml}
  <div class="martial-sec-title">心法槽 <span>点击功法格可跳到功法页</span></div>${slotHtml}
  <div class="martial-sec-title">共鸣技能 <span>${esc((m.stats||{}).resonance_used||0)}/${esc((m.stats||{}).resonance_total||0)}</span></div>${supportHtml}
  <div class="martial-sec-title">体检结论 <span>按 高 → 中 → 低 → 提示 排序</span></div>
  <div class="martial-diags">${diagnosis||'<div class="empty">暂无体检结论</div>'}</div>
  <div class="martial-sec-title" id="martial-bag">卷册 <span>在包未参悟</span></div>
  <div class="martial-bag">${bagHtml}</div>${notes}`;
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
 </div><div id="martial-arts-list"></div>`;
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
