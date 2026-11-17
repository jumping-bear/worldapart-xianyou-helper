/* NPC 天赋：以"区域 → NPC 卡"折叠布局为主，一眼看到谁在哪、有什么好天赋、能不能去找。 */
(function(){
const KEY='worldapart.talent.filters.v4';
const DEFAULTS={q:'',npc:'',region:'',location:'',category:'',quality:'',realm:'',unlocked:'',dao:'',visitable:1};
let filters=Object.assign({},DEFAULTS,store.get(KEY,{}));
function catValue(t){return t.category===null||t.category===undefined||t.category===''?'':String(t.category)}
function categoryLabel(t){const value=catValue(t),name=t.category_name||'';return value?(name?`${name}（${value}）`:`分类 ${value}`):'未分类'}
function talentText(t){return [t.name,t.effect,t.hover,t.trigger].map(v=>String(v||'')).join('\n').toLowerCase()}
function talentBadges(t,m){const quality=t.quality==null?'未知品质':`品质 ${t.quality}`,cat=categoryLabel(t),realm=(m.realms||{})[String(t.realm_id??0)]||`境界 ${t.realm_id??0}`;return `<span class="badge">${esc(quality)}</span><span class="badge category-badge">${esc(cat)}</span><span class="badge">${esc(realm)}</span>`}
function statusOf(row){
 if(row.present&&!row.gone)return {cls:'talent-live',label:'在世'};
 if(row.present&&row.gone)return {cls:'talent-gone',label:'已离世'};
 return {cls:'talent-absent',label:'不在当前世界'};
}
function placeText(row){
 if(row.present&&!row.gone)return row.location_path||row.location||'未知地点';
 if(row.present&&row.gone)return '已离世 · 该 NPC 已不在，无法前往';
 return '不在当前世界';
}
function initTalent(){
 const m=DATA.modules.talent;if(!m)return;
 const talents=m.talents||[],stats=m.stats||{};
 const regions=uniq(m.rows.filter(r=>r.present&&!r.gone).map(r=>r.region||r.location||'未知区域'));
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
  <div class="talent-stats">
   <div class="talent-stat"><b>${stats.present||0}</b><span>在世可拜访</span></div>
   <div class="talent-stat"><b>${stats.gone||0}</b><span>已离世</span></div>
   <div class="talent-stat"><b>${stats.absent||0}</b><span>不在当前世界</span></div>
   <div class="talent-stat"><b>${stats.total||0}</b><span>有天赋 NPC</span></div>
  </div>
  <div class="search-panel"><div class="search-fields">
   <label class="search-field"><span>找天赋</span><input id="fq" placeholder="输入天赋名称、效果、悬停或触发描述" value="${esc(filters.q)}"></label>
   <label class="search-field"><span>找 NPC（可选）</span><input id="fnpc" placeholder="输入 NPC 名称，与天赋条件叠加" value="${esc(filters.npc)}"></label>
  </div></div>
  <div class="filter-bar talent-filter-bar">
   <label class="filter-field"><span>区域</span><select id="fregion">${opts(regions,'区域')}</select></label>
   <label class="filter-field"><span>具体位置</span><select id="flocation"></select></label>
   <label class="talent-check"><input type="checkbox" id="fvisitable"${filters.visitable?' checked':''}><span>只看可拜访</span></label>
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
  const locations=uniq(m.rows.filter(r=>r.present&&(!filters.region||(r.region||r.location||'未知区域')===filters.region)).map(r=>r.location||'未知地点'));
  if(filters.location&&!locations.includes(filters.location))filters.location='';
  $('flocation').innerHTML=opts(locations,'具体位置');$('flocation').value=filters.location||'';
 }
 function updateAdvancedCount(){const count=advancedKeys.filter(key=>filters[key]!=='').length;$('fadvancedcount').textContent=count?`（${count}）`:''}
 function saveAndRender(){store.set(KEY,filters);updateAdvancedCount();renderTalentList()}
 $('fregion').value=filters.region||'';
 updateLocations();
 for(const key of ['q','npc','location','category','quality','realm','unlocked','dao']){
  const node=$('f'+key);node.value=filters[key]??'';
  node.addEventListener(node.tagName==='INPUT'?'input':'change',()=>{filters[key]=node.value;saveAndRender()})
 }
 $('fvisitable').addEventListener('change',()=>{filters.visitable=$('fvisitable').checked?1:0;saveAndRender()});
 $('fregion').addEventListener('change',()=>{filters.region=$('fregion').value;updateLocations();saveAndRender()});
 $('fclear').addEventListener('click',()=>{filters=Object.assign({},DEFAULTS);store.set(KEY,filters);initTalent()});
 renderTalentList();
}
function slotMatches(t,s,q){
 if(filters.category==='__uncategorized__'&&catValue(t)!=='')return false;
 if(filters.category&&filters.category!=='__uncategorized__'&&catValue(t)!==filters.category)return false;
 if(filters.quality==='__unknown__'&&t.quality!=null)return false;
 if(filters.quality&&filters.quality!=='__unknown__'&&String(t.quality??'')!==filters.quality)return false;
 if(filters.realm!==''&&String(t.realm_id??0)!==filters.realm)return false;
 if(filters.unlocked!==''&&String(s.unlocked?1:0)!==filters.unlocked)return false;
 if(q&&!talentText(t).includes(q))return false;
 return true;
}
function slotHtml(s,t,m,q){
 if(!t||t.id===undefined){
  return `<div class="slot"><div class="slot-head"><span class="muted">槽位 ${esc(s.slot_id??'?')}</span><span class="talent-name muted">随机天赋（尚未生成）</span><span class="lock">未解锁</span></div></div>`;
 }
 const name=t.name||`天赋 #${s.talent_id}`;
 const req=s.required_realm?`<div class="condition">槽位要求：${esc((m.realms||{})[String(s.required_realm)]||('境界 '+s.required_realm))}</div>`:'';
 const conditions=(s.conditions||[]).length?`<div class="condition">解锁条件：${s.conditions.map(esc).join('；')}</div>`:'';
 const effect=t.effect?`<div class="effect">${hi(t.effect||'暂无效果说明',q)}</div>`:'';
 const extras=[];
 if(t.hover)extras.push(`<div class="talent-extra">悬停说明：${hi(t.hover,q)}</div>`);
 if(t.trigger)extras.push(`<div class="talent-extra">触发说明：${hi(t.trigger,q)}</div>`);
 return `<div class="slot"><div class="slot-head"><span class="muted">槽位 ${esc(s.slot_id??'?')}</span><span class="talent-name q${esc(t.quality??0)}">${hi(name,q)}</span>${talentBadges(t,m)}<span class="lock ${s.unlocked?'on':''}">${s.unlocked?'已解锁':'未解锁'}</span></div>${effect}${req}${conditions}${extras.join('')}</div>`;
}
function talentChip(s,t,q){
 if(!t||t.id===undefined)return `<span class="talent-chip talent-chip-unknown">随机天赋</span>`;
 const name=t.name||(`天赋 #${s.talent_id}`);
 return `<span class="talent-chip q${esc(t.quality??0)}" title="${esc(s.unlocked?'已解锁':'未解锁')}">${hi(name,q)}<i class="talent-chip-lock ${s.unlocked?'on':''}">${s.unlocked?'✓':'锁'}</i></span>`;
}
function npcCard(row,matched,m,talentMap,q,npcQ){
 const live=row.present&&!row.gone,gone=row.present&&row.gone;
 const cls=gone?' talent-gone-card':(live?'':' talent-absent-card');
 const st=statusOf(row);
 const chips=matched.map(s=>talentChip(s,talentMap[String(s.talent_id)],q)).join('');
 const dao=row.dao?'<span class="badge dao">已同道</span>':'';
 return `<details class="npc${cls}"><summary><span class="who">${hi(row.who,npcQ)}</span>${row.title?`<span class="muted">${esc(row.title)}</span>`:''}${dao}<span class="talent-status ${st.cls}">${st.label}</span><span class="talent-count">${matched.length} 项</span><span class="location">${esc(placeText(row))}</span></summary><div class="talent-chips">${chips}</div><div class="slots">${matched.map(s=>slotHtml(s,talentMap[String(s.talent_id)],m,q)).join('')}</div></details>`;
}
function renderTalentList(){
 const m=DATA.modules.talent;
 const talentMap=Object.fromEntries((m.talents||[]).map(t=>[String(t.id),t]));
 const q=filters.q.trim().toLowerCase(),npcQ=filters.npc.trim().toLowerCase();
 const groups={};let npcCount=0,slotCount=0;
 for(const row of m.rows){
  if(filters.visitable&&!(row.present&&!row.gone))continue;
  if(filters.region&&(row.region||'')!==filters.region)continue;
  if(filters.location&&(row.location||'未知地点')!==filters.location)continue;
  if(filters.dao!==''&&String(row.dao?1:0)!==filters.dao)continue;
  const npcText=[row.who,row.title].map(v=>String(v||'')).join('\n').toLowerCase();
  if(npcQ&&!npcText.includes(npcQ))continue;
  const matched=[];
  for(const s of row.slots||[]){
   const t=talentMap[String(s.talent_id)]||{};
   if(slotMatches(t,s,q))matched.push(s);
  }
  if(!matched.length)continue;
  const region=row.region||'不在当前世界';
  (groups[region]=groups[region]||[]).push({row,matched});
  npcCount++;slotCount+=matched.length;
 }
 const regionNames=Object.keys(groups).sort((a,b)=>{if(a==='不在当前世界')return 1;if(b==='不在当前世界')return -1;return a.localeCompare(b,'zh-CN')});
 const html=regionNames.map(region=>{
  const cards=groups[region].map(g=>npcCard(g.row,g.matched,m,talentMap,q,npcQ)).join('');
  return `<details class="talent-region" open><summary><span class="talent-region-name">${esc(region)}</span><span class="talent-region-count">${groups[region].length} 位 NPC</span></summary><div class="talent-region-body">${cards}</div></details>`;
 }).join('');
 $('tresult').textContent=`筛选结果：${npcCount} 位 NPC，${slotCount} 条天赋记录（共 ${m.rows.length} 位有天赋记录，在世 ${m.stats.present} / 已离世 ${m.stats.gone} / 不在当前世界 ${m.stats.absent}）`;
 $('tlist').innerHTML=html||'<div class="empty">没有符合组合筛选条件的天赋</div>';
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['talent']=initTalent;
})();
