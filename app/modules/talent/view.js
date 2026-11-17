/* NPC 天赋：天赋优先布局。
 * 默认是「天赋列表 + 搜索」，找到天赋后再展开「哪些 NPC 拥有」；
 * 点开 NPC 全量展示它的所有槽位，方便评估整个天赋组合值不值得占同道位。
 * 筛选只做高亮 + 变暗，不删除条目；唯一的隐藏开关是「只看可拜访」。
 */
(function(){
const KEY='worldapart.talent.filters.v5';
const DEFAULTS={q:'',npc:'',category:'',quality:'',realm:'',unlocked:'',dao:'',region:'',location:'',visitable:1};
let filters=Object.assign({},DEFAULTS,store.get(KEY,{}));
function catValue(t){return t.category===null||t.category===undefined||t.category===''?'':String(t.category)}
function categoryLabel(t){const value=catValue(t),name=t.category_name||'';return value?(name||`分类 ${value}`):'未分类'}
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
// 同道提示：容量来自境界配置（realm_capacity），缺失时用口语提示，不硬编码数字。
function daoHint(m){
 const d=m.dao||{};
 if(d.capacity){
  const realm=d.realm_name?`当前境界「${esc(d.realm_name)}」`:'当前境界';
  const full=(d.count||0)>=(d.capacity)?'，同道位已满':'';
  return `${realm}可同道 <b>${d.capacity}</b> 人，已同道 <b>${d.count||0}</b> 人${full}`;
 }
 return '同道数量有限';
}
function initTalent(){
 const m=DATA.modules.talent;if(!m)return;
 const talents=m.talents||[],stats=m.stats||{};
 const categories=uniq(talents.map(catValue)).filter(v=>v!==''),qualities=uniq(talents.map(t=>t.quality==null?'':String(t.quality))),realms=uniq(talents.map(t=>String(t.realm_id??0)));
 const regions=uniq(m.rows.filter(r=>r.present&&!r.gone).map(r=>r.region||r.location||'未知区域'));
 const opts=(values,kind)=>`<option value="">全部${kind}</option>`+values.map(v=>{
  let label=v,value=v;
  if(kind==='分类'){const sample=talents.find(t=>catValue(t)===v)||{category:v};label=categoryLabel(sample);value=v}
  if(kind==='品质'){label=v?`品质 ${v}`:'未知品质';value=v||'__unknown__'}
  if(kind==='境界')label=(m.realms||{})[v]||`境界 ${v}`;
  return `<option value="${esc(value)}">${esc(label)}</option>`
 }).join('');
 const advancedKeys=['unlocked','dao','region','location'];
 const advancedCount=advancedKeys.filter(key=>filters[key]!=='').length;
 $('talent').innerHTML=sourceHtml(m)+`
  <div class="talent-stats">
   <div class="talent-stat"><b>${stats.present||0}</b><span>在世可拜访</span></div>
   <div class="talent-stat"><b>${stats.gone||0}</b><span>已离世</span></div>
   <div class="talent-stat"><b>${stats.absent||0}</b><span>不在当前世界</span></div>
   <div class="talent-stat"><b>${talents.length}</b><span>天赋总数</span></div>
  </div>
  <div class="talent-dao-hint" id="tdao">${daoHint(m)}</div>
  <div class="search-panel"><div class="search-fields">
   <label class="search-field search-hero"><span>找天赋</span><input id="fq" placeholder="输入天赋名称、效果、悬停或触发描述关键词" value="${esc(filters.q)}"></label>
   <label class="search-field"><span>找 NPC（可选）</span><input id="fnpc" placeholder="输入 NPC 名称，与天赋条件叠加" value="${esc(filters.npc)}"></label>
  </div></div>
  <div class="filter-bar talent-filter-bar">
   <label class="filter-field"><span>天赋品质</span><select id="fquality">${opts(qualities,'品质')}</select></label>
   <label class="filter-field"><span>天赋分类</span><select id="fcategory">${opts(categories,'分类')}</select></label>
   <label class="filter-field"><span>天赋境界</span><select id="frealm">${opts(realms,'境界')}</select></label>
   <label class="talent-check"><input type="checkbox" id="fvisitable"${filters.visitable?' checked':''}><span>只看可拜访</span></label>
   <div class="filter-actions"><button type="button" id="fclear" class="filter-button">清空筛选</button></div>
  </div>
  <details id="fadvanced" class="advanced-filters"${advancedCount?' open':''}><summary>更多筛选 <span id="fadvancedcount" class="filter-count">${advancedCount?`（${advancedCount}）`:''}</span></summary><div class="advanced-grid">
   <label><span>解锁状态</span><select id="funlocked"><option value="">全部解锁状态</option><option value="1">已解锁</option><option value="0">未解锁</option></select></label>
   <label><span>同道状态</span><select id="fdao"><option value="">全部同道状态</option><option value="1">已同道</option><option value="0">未同道</option></select></label>
   <label><span>区域</span><select id="fregion">${opts(regions,'区域')}</select></label>
   <label><span>具体位置</span><select id="flocation"></select></label>
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
/* 天赋级筛选：命中高亮、未命中变暗（不删除）。 */
function talentMatches(t,q){
 if(filters.category!==''&&catValue(t)!==filters.category)return false;
 if(filters.quality==='__unknown__'&&t.quality!=null)return false;
 if(filters.quality&&filters.quality!=='__unknown__'&&String(t.quality??'')!==filters.quality)return false;
 if(filters.realm!==''&&String(t.realm_id??0)!==filters.realm)return false;
 if(q&&!talentText(t).includes(q))return false;
 return true;
}
/* NPC 级：定位筛选直接隐藏；名称/同道只做高亮变暗。 */
function npcVisible(row){
 if(filters.visitable&&!(row.present&&!row.gone))return false;
 if(filters.region&&(row.region||'')!==filters.region)return false;
 if(filters.location&&(row.location||'未知地点')!==filters.location)return false;
 return true;
}
function npcHighlight(row,npcQ){
 if(filters.dao!==''&&String(row.dao?1:0)!==filters.dao)return false;
 if(npcQ&&![row.who,row.title].map(v=>String(v||'').toLowerCase()).join('\n').includes(npcQ))return false;
 return true;
}
/* 槽位高亮：该槽位自己的天赋是否命中当前天赋筛选 + 解锁筛选。 */
function slotHighlight(s,talentMap,q){
 const t=talentMap[String(s.talent_id)];
 if(filters.unlocked!==''&&String(s.unlocked?1:0)!==filters.unlocked)return false;
 if(!t||t.id===undefined)return filters.unlocked===''&&!q;
 return talentMatches(t,q);
}
function slotHtml(s,t,m,q,hl){
 if(!t||t.id===undefined){
  return `<div class="slot${hl?'':' slot-dim'}"><div class="slot-head"><span class="muted">槽位 ${esc(s.slot_id??'?')}</span><span class="talent-name muted">随机天赋（尚未生成）</span><span class="lock">未解锁</span></div></div>`;
 }
 const name=t.name||`天赋 #${s.talent_id}`;
 const req=s.required_realm?`<div class="condition">槽位要求：${esc((m.realms||{})[String(s.required_realm)]||('境界 '+s.required_realm))}</div>`:'';
 const conditions=(s.conditions||[]).length?`<div class="condition">解锁条件：${s.conditions.map(esc).join('；')}</div>`:'';
 const effect=t.effect?`<div class="effect">${hi(t.effect||'暂无效果说明',q)}</div>`:'';
 const extras=[];
 if(t.hover)extras.push(`<div class="talent-extra">悬停说明：${hi(t.hover,q)}</div>`);
 if(t.trigger)extras.push(`<div class="talent-extra">触发说明：${hi(t.trigger,q)}</div>`);
 return `<div class="slot${hl?'':' slot-dim'}"><div class="slot-head"><span class="muted">槽位 ${esc(s.slot_id??'?')}</span><span class="talent-name q${esc(t.quality??0)}">${hi(name,q)}</span>${talentBadges(t,m)}<span class="lock ${s.unlocked?'on':''}">${s.unlocked?'已解锁':'未解锁'}</span></div>${effect}${req}${conditions}${extras.join('')}</div>`;
}
/* NPC 面板：完整列出该 NPC 的所有天赋槽位，命中项高亮、其余变暗。 */
function npcCard(row,m,talentMap,q,npcQ){
 const live=row.present&&!row.gone,gone=row.present&&row.gone;
 const cls=gone?' talent-gone-card':(live?'':' talent-absent-card');
 const hl=npcHighlight(row,npcQ);
 const st=statusOf(row);
 const dao=row.dao?'<span class="badge dao">已同道</span>':'';
 const slots=(row.slots||[]).map(s=>slotHtml(s,talentMap[String(s.talent_id)],m,q,slotHighlight(s,talentMap,q))).join('');
 return `<details class="npc${cls}${hl?'':' npc-dim'}"><summary><span class="who">${hi(row.who,npcQ)}</span>${row.title?`<span class="muted">${esc(row.title)}</span>`:''}${dao}<span class="talent-status ${st.cls}">${st.label}</span><span class="location">${esc(placeText(row))}</span><span class="talent-count">${(row.slots||[]).length} 槽位</span></summary><div class="slots">${slots}</div></details>`;
}
/* 天赋卡：命中高亮、未命中变暗；展开后列出拥有它的 NPC。 */
function talentCard(t,holders,m,talentMap,q,npcQ){
 const match=talentMatches(t,q);
 const liveCount=holders.filter(h=>h.row.present&&!h.row.gone).length;
 const name=t.name||(`天赋 #${t.id}`);
 const effect=t.effect?`<div class="effect">${hi(t.effect||'暂无效果说明',q)}</div>`:'';
 const extras=[];
 if(t.hover)extras.push(`<div class="talent-extra">悬停说明：${hi(t.hover,q)}</div>`);
 if(t.trigger)extras.push(`<div class="talent-extra">触发说明：${hi(t.trigger,q)}</div>`);
 const body=`<div class="talent-detail">${effect}${extras.join('')}<div class="talent-holder-note">${holders.length?`拥有此天赋的 NPC（在世 ${liveCount} 位）：`:'暂无 NPC 拥有此天赋'}</div><div class="npc-holders">${holders.map(h=>npcCard(h.row,m,talentMap,q,npcQ)).join('')}</div></div>`;
 return `<details class="talent-card${match?'':' talent-dim'}"><summary><span class="talent-name q${esc(t.quality??0)}">${hi(name,q)}</span>${talentBadges(t,m)}<span class="talent-holder-count">${holders.length} 位 NPC</span></summary>${body}</details>`;
}
function renderTalentList(){
 const m=DATA.modules.talent;
 const talentMap=Object.fromEntries((m.talents||[]).map(t=>[String(t.id),t]));
 const q=filters.q.trim().toLowerCase(),npcQ=filters.npc.trim().toLowerCase();
 // 先建 天赋 -> [(row, slot)] 索引，再按天赋排序渲染。
 const holdersOf={};
 for(const row of m.rows){
  if(!npcVisible(row))continue;
  for(const s of row.slots||[]){
   const tid=String(s.talent_id);
   if(!(tid in holdersOf))holdersOf[tid]=[];
   holdersOf[tid].push({row,slot:s});
  }
 }
 let matchedTalents=0,npcShown=0;
 const cards=(m.talents||[]).map(t=>({t,match:talentMatches(t,q),holders:holdersOf[String(t.id)]||[]}));
 cards.forEach(c=>{if(c.match)matchedTalents++;npcShown+=c.holders.length});
 cards.sort((a,b)=>(b.match-a.match)||((b.t.quality??-1)-(a.t.quality??-1))||String(a.t.name).localeCompare(String(b.t.name),'zh-CN'));
 const html=cards.map(c=>talentCard(c.t,c.holders,m,talentMap,q,npcQ)).join('');
 $('tresult').textContent=`共 ${m.talents.length} 个天赋；命中 ${matchedTalents} 个天赋、${npcShown} 条 NPC 记录（在世 ${m.stats.present} / 已离世 ${m.stats.gone} / 不在当前世界 ${m.stats.absent}）。筛选只高亮、不删除，未命中的内容变暗保留。`;
 $('tlist').innerHTML=html||'<div class="empty">没有天赋数据</div>';
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['talent']=initTalent;
})();
