/* NPC 天赋：页面渲染（自 output.py 原样搬入）。 */
(function(){
const FILTER_KEY='worldapart.talent.filters.v3';
const FILTER_DEFAULTS={q:'',npc:'',region:'',location:'',category:'',quality:'',realm:'',unlocked:'',dao:''};
let filters=Object.assign({},FILTER_DEFAULTS,store.get('worldapart.talent.filters.v2',{}),store.get(FILTER_KEY,{}));
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
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['talent']=initTalent;
})();
