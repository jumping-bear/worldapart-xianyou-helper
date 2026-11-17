/* NPC 物品：页面渲染。主视图为「物品 → 持有者」反向索引，按品质从高到低分组；
   可切换到「按 NPC 看」的完整清单视角。 */
(function(){
const ITEM_KEY='worldapart.item.filters.v1';
const ITEM_DEFAULTS={q:'',npc:'',region:'',location:'',type:'',quality:'',steal:'',demand:''};
let itemFilters=Object.assign({},ITEM_DEFAULTS,store.get(ITEM_KEY,{}));
let itemView=store.get('worldapart.item.view.v1','item');
if(itemView!=='npc')itemView='item';
let itemCache=null;
let itemRenderState={groups:{},q:'',npcQ:''};
let itemSort=store.get('worldapart.item.sort.v1','rate');
let itemPage={};
function fqClass(q){return 'fq'+(q==null||q===''?0:q)}
function qualityLabel(q){return q==null||q===''?'未知品质':(Number(q)>0?'品质 '+q:'无品质')}
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
  return '<div class="slot'+(current?' focus':'')+'"><div class="slot-head"><span class="talent-name '+fqClass(o.t.quality)+'">'+esc(o.t.name)+'</span>'+(current?'<span class="badge steal">当前物品</span>':'')+'<span class="badge">×'+esc(o.count)+'</span><span class="badge">'+esc(o.t.type||'未分类')+'</span>'+verdict+'</div>'+effect+'</div>';
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
  return '<div class="slot'+(current?' focus':'')+'"><div class="slot-head"><span class="talent-name '+fqClass(o.t.quality)+'">'+esc(o.t.name)+'</span>'+absent+'<span class="badge">'+esc(qualityLabel(o.t.quality))+'</span>'+value+'</div></div>';
 }).join('');
 const fav=row.intimacy!=null?'<div class="item-sec-note">好感 '+esc(row.intimacy)+(intimacyName(row)?'（'+esc(intimacyName(row))+'）':'')+' · 无好感门槛 · 每周期 1 次 · 消耗不随境界折算</div>':'';
 return '<div class="item-sec"><div class="item-sec-head"><span>偷取</span><span class="meta">'+list.length+' 件 · 来自他的背包</span></div>'+(stealRows||'<div class="empty">他目前没有持有物品</div>')+'</div>'
  +'<div class="item-sec"><div class="item-sec-head"><span>索要</span><span class="meta">'+demands.length+' 件 · 来自索要模板</span></div>'+fav+(demandRows||'<div class="empty">这个 NPC 没有索要模板</div>')+'</div>';
}
function npcPass(row,npcQ){
 if(itemFilters.region&&(row.region||'未知区域')!==itemFilters.region)return false;
 if(itemFilters.location&&(row.location||'未知地点')!==itemFilters.location)return false;
 if(npcQ&&!((row.who+' '+(row.realm||'')).toLowerCase().includes(npcQ)))return false;
 return true;
}
function itemPass(iid,t,row,v,q){
 if(q&&!String(t.name).toLowerCase().includes(q))return false;
 if(itemFilters.type&&(t.type||'未分类')!==(itemFilters.type==='__none__'?'未分类':itemFilters.type))return false;
 if(itemFilters.quality==='__unknown__'&&t.quality!=null)return false;
 if(itemFilters.quality&&itemFilters.quality!=='__unknown__'&&String(t.quality??'')!==itemFilters.quality)return false;
 if(itemFilters.steal==='1'&&!v.ok)return false;
 if(itemFilters.steal==='0'&&v.ok)return false;
 if(itemFilters.demand==='1'&&!((row.demand||[]).some(id=>String(id)===iid)&&t.demand))return false;
 return true;
}
function hasItemFilters(){return !!(itemFilters.q||itemFilters.type||itemFilters.quality||itemFilters.steal||itemFilters.demand)}
function renderItems(){
 itemPage={};
 const m=DATA.modules.items,idx=itemIndex();
 const q=itemFilters.q.trim().toLowerCase(),npcQ=itemFilters.npc.trim().toLowerCase();
 const groups={},npcSet=new Set();let pairCount=0;
 for(const row of m.rows){
  if(!npcPass(row,npcQ))continue;
  for(const pair of row.items||[]){
   const iid=String(pair[0]),t=idx.cat[iid];
   if(!t)continue;
   const v=itemVerdict(row,t);
   if(!itemPass(iid,t,row,v,q))continue;
   if(!groups[iid])groups[iid]={t:t,owners:[],stealable:0,total:0};
   groups[iid].owners.push({row:row,t:t,count:pair[1]||1,v:v});
   groups[iid].total+=pair[1]||1;
   if(v.ok){groups[iid].stealable++;const rate=t.steal?t.steal.rate:0;if(rate>(groups[iid].bestRate||0))groups[iid].bestRate=rate;}
   npcSet.add(row.uid);pairCount++;
  }
 }
 const sorted=Object.values(groups).sort((a,b)=>b.stealable-a.stealable||itemRate(b)-itemRate(a)||String(a.t.name).localeCompare(String(b.t.name),'zh-CN'));
 const buckets={};
 for(const g of sorted){
  const key=g.t.quality==null?'__none__':String(g.t.quality);
  const b=buckets[key]||(buckets[key]={q:g.t.quality,groups:[],items:0,total:0,stealable:0});
  b.groups.push(g);b.items++;b.total+=g.total;b.stealable+=g.stealable;
 }
 const order=Object.keys(buckets).sort((a,b)=>{
  if(a==='__none__'&&b==='__none__')return 0;
  if(a==='__none__')return 1;
  if(b==='__none__')return -1;
  return Number(b)-Number(a);
 });
 const cards=order.map(key=>{
  const b=buckets[key];
  const inner=b.groups.map(group=>{
   const stat='可偷 '+group.stealable+' 处'+(group.bestRate?' · 最高 '+group.bestRate+'%':'')+' · 共 '+group.total+' 个';
   return '<details class="item-group" data-item="'+esc(group.t.id)+'"><summary class="item-head"><span class="item-arrow">›</span><span class="item-title '+fqClass(group.t.quality)+'">'+hi(group.t.name,q)+'</span><span class="badge">'+esc(group.t.type||'未分类')+'</span><span class="badge">'+esc(qualityLabel(group.t.quality))+'</span><span class="item-stat">'+stat+'</span></summary><div class="owners"></div></details>';
  }).join('');
  return '<details class="qsec" open><summary><span class="qsec-arrow">›</span><span class="qsec-title '+fqClass(b.q)+'">'+esc(qualityLabel(b.q))+'</span><span class="badge">'+b.items+' 种</span><span class="qsec-meta">可偷 '+b.stealable+' 处 · 共 '+b.total+' 个</span></summary><div class="qsec-body">'+inner+'</div></details>';
 });
 itemRenderState={groups:Object.fromEntries(sorted.map(g=>[String(g.t.id),g])),q:q,npcQ:npcQ};
 $('iresult').textContent='筛选结果：'+sorted.length+' 种物品（按品质从高到低分组），'+npcSet.size+' 位 NPC，'+pairCount+' 条持有记录';
 $('ilist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合条件的物品</div>';
}
function renderNpcs(){
 itemPage={};
 const m=DATA.modules.items,idx=itemIndex();
 const npcQ=itemFilters.npc.trim().toLowerCase(),q=itemFilters.q.trim().toLowerCase();
 const itemFilterOn=hasItemFilters();
 const npcs={};
 for(const row of m.rows){
  if(!npcPass(row,npcQ))continue;
  let matched=0,stealable=0;
  for(const pair of row.items||[]){
   const iid=String(pair[0]),t=idx.cat[iid];
   if(!t)continue;
   const v=itemVerdict(row,t);
   if(!itemPass(iid,t,row,v,q))continue;
   matched++;
   if(v.ok)stealable++;
  }
  if(itemFilterOn&&!matched)continue;
  const demandable=(row.demand||[]).filter(did=>{const dt=idx.cat[String(did)];return dt&&dt.demand}).length;
  npcs[row.uid]={row:row,total:(row.items||[]).length,matched:matched,stealable:stealable,demandable:demandable};
 }
 const list=Object.values(npcs).sort((a,b)=>b.stealable-a.stealable||b.total-a.total||String(a.row.who).localeCompare(String(b.row.who),'zh-CN'));
 const cards=list.map(g=>{
  const held=itemFilterOn?'符合 '+g.matched+' / 共 '+g.total+' 件':'共 '+g.total+' 件';
  return '<details class="item-group npc-card" data-uid="'+esc(g.row.uid)+'"><summary class="item-head"><span class="item-arrow">›</span><span class="item-title">'+hi(g.row.who,npcQ)+'</span>'+(g.row.realm?'<span class="badge">'+esc(g.row.realm)+'</span>':'')+'<span class="badge steal">可偷 '+g.stealable+' 件</span>'+(g.demandable?'<span class="badge demand">可索要 '+g.demandable+' 件</span>':'')+'<span class="item-stat">'+held+' · '+esc(g.row.location_path||g.row.location||'未知地点')+'</span></summary><div class="slots"></div></details>';
 });
 itemRenderState={groups:{},q:q,npcQ:npcQ};
 $('iresult').textContent='筛选结果：'+list.length+' 位 NPC，共 '+list.reduce((s,g)=>s+g.total,0)+' 件物品（按 NPC 查看完整清单）';
 $('ilist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合条件的 NPC</div>';
}
function renderList(){if(itemView==='npc')renderNpcs();else renderItems()}
function initItems(){
 const m=DATA.modules.items;if(!m)return;
 const catalog=m.catalog||[],regions=uniq(m.rows.map(r=>r.region||'未知区域'));
 const types=uniq(catalog.map(t=>t.type||'未分类'));
 const opts=(values,kind)=>'<option value="">全部'+kind+'</option>'+values.map(v=>{
  let label=v,value=v;
  if(kind==='类型'){label=v||'未分类';value=v||'__none__'}
  return '<option value="'+esc(value)+'">'+esc(label)+'</option>'
 }).join('');
 function qualityOptions(){
  const vals=[...new Set(catalog.map(t=>t.quality==null?'__unknown__':String(t.quality)))];
  const known=vals.filter(v=>v!=='__unknown__').sort((a,b)=>Number(b)-Number(a));
  let out='<option value="">全部品质</option>'+known.map(v=>'<option value="'+v+'">品质 '+v+'</option>').join('');
  if(vals.includes('__unknown__'))out+='<option value="__unknown__">未知品质</option>';
  return out;
 }
 $('items').innerHTML=sourceHtml(m)+`
  <style>
  .item-sec{margin-top:14px;border-top:1px solid #2a3340;padding-top:10px}
  .item-sec-head{display:flex;align-items:baseline;gap:8px;margin:2px 0 4px;font-size:13px;font-weight:600}
  .item-sec-head .meta{font-weight:400;color:#8b93a1;font-size:12px}
  .item-sec-note{font-size:12px;color:#8b93a1;margin:0 0 6px}
  .badge.demand{background:rgba(110,221,162,.14);color:#6edda2;border:1px solid rgba(110,221,162,.35)}
  .badge.demand-absent{background:transparent;color:#8b93a1;border:1px dashed #4a5563}
  .item-viewbar{display:flex;gap:8px;margin-bottom:14px}
  .viewbtn{background:#1b222c;border:1px solid #35404f;border-radius:8px;color:#9aa3b2;padding:9px 16px;cursor:pointer;font-size:13px}
  .viewbtn:hover{background:#25303d}
  .viewbtn.on{background:#263b34;border-color:#3d735b;color:#c9f5dd}
  .filter-bar.items{grid-template-columns:repeat(3,minmax(0,1fr));align-items:end}
  .filter-bar.items .filter-actions{grid-column:1 / -1;justify-content:flex-end}
  .qsec{background:#12161c;border:1px solid #232b36;border-radius:12px;margin:0 0 16px;overflow:hidden}
  .qsec>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;padding:13px 16px}
  .qsec>summary::-webkit-details-marker{display:none}
  .qsec>summary:hover{background:#171d27}
  .qsec-arrow{color:#6f7787;font-size:16px;transition:.15s;display:inline-block}
  .qsec[open]>summary .qsec-arrow{transform:rotate(90deg)}
  .qsec-title{font-size:15px;font-weight:650}
  .qsec-meta{margin-left:auto;color:#778292;font-size:11px;font-weight:400}
  .qsec-body{padding:4px 12px 12px}
  @media(max-width:850px){.filter-bar.items{grid-template-columns:repeat(2,minmax(0,1fr))}.filter-bar.items .filter-actions{grid-column:span 2}}
  @media(max-width:560px){.filter-bar.items{grid-template-columns:1fr}.filter-bar.items .filter-actions{grid-column:span 1}.qsec-body{padding:4px 8px 8px}}
  </style>
  <div class="search-panel">
   <div class="item-viewbar">
    <button type="button" class="viewbtn" id="iview-item" data-view="item">按物品找</button>
    <button type="button" class="viewbtn" id="iview-npc" data-view="npc">按 NPC 看</button>
   </div>
   <div class="search-fields">
    <label class="search-field"><span>找物品</span><input id="iq" placeholder="输入物品名称" value="${esc(itemFilters.q)}"></label>
    <label class="search-field"><span>找 NPC（可选）</span><input id="inpc" placeholder="输入 NPC 名称，与物品条件叠加" value="${esc(itemFilters.npc)}"></label>
   </div>
  </div>
  <div class="filter-bar items">
   <label class="filter-field"><span>品质</span><select id="iquality">${qualityOptions()}</select></label>
   <label class="filter-field"><span>类型</span><select id="itype">${opts(types,'类型')}</select></label>
   <label class="filter-field"><span>区域</span><select id="iregion">${opts(regions,'区域')}</select></label>
   <label class="filter-field"><span>具体位置</span><select id="ilocation"></select></label>
   <label class="filter-field"><span>偷窃</span><select id="isteal"><option value="">全部持有者</option><option value="1">只看可偷</option><option value="0">只看不可偷</option></select></label>
   <label class="filter-field"><span>索要</span><select id="idemand"><option value="">全部物品</option><option value="1">只看可索要</option></select></label>
   <div class="filter-actions"><button type="button" id="iclear" class="filter-button">清空筛选</button></div>
  </div>
  <div id="iresult" class="result-info"></div><div id="ilist"></div>`;
 function updateItemLocations(){
  const locations=uniq(m.rows.filter(r=>!itemFilters.region||(r.region||'未知区域')===itemFilters.region).map(r=>r.location||'未知地点'));
  if(itemFilters.location&&!locations.includes(itemFilters.location))itemFilters.location='';
  $('ilocation').innerHTML=opts(locations,'具体位置');$('ilocation').value=itemFilters.location||'';
 }
 function saveAndRender(){store.set(ITEM_KEY,itemFilters);renderList()}
 function applyView(){
  $('iview-item').classList.toggle('on',itemView==='item');
  $('iview-npc').classList.toggle('on',itemView==='npc');
 }
 $('iview-item').addEventListener('click',()=>{itemView='item';store.set('worldapart.item.view.v1',itemView);applyView();renderList()});
 $('iview-npc').addEventListener('click',()=>{itemView='npc';store.set('worldapart.item.view.v1',itemView);applyView();renderList()});
 $('iregion').value=itemFilters.region||'';updateItemLocations();
 for(const key of ['q','npc','location','type','quality','steal','demand']){
  const node=$('i'+key);node.value=itemFilters[key]??'';
  node.addEventListener(node.tagName==='INPUT'?'input':'change',()=>{itemFilters[key]=node.value;saveAndRender()});
 }
 $('iregion').addEventListener('change',()=>{itemFilters.region=$('iregion').value;updateItemLocations();saveAndRender()});
 $('iclear').addEventListener('click',()=>{itemFilters=Object.assign({},ITEM_DEFAULTS);store.set(ITEM_KEY,itemFilters);initItems()});
 applyView();renderList();
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
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['items']=initItems;
})();
