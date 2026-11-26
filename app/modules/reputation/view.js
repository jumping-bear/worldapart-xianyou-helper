/* 城镇声望：委托、称号与货架解锁。 */
(function(){
const REP_KEY='worldapart.reputation.ui.v1';
const DEFAULTS={town:0,showAll:false,sort:'rep'};
let ui=Object.assign({},DEFAULTS,store.get(REP_KEY,{}));
let cache=null;

function save(){store.set(REP_KEY,ui)}
function n(v){const x=Number(v);return Number.isFinite(x)?x:0}
function num(v){return n(v).toLocaleString('zh-CN')}
function badge(text,cls){return `<span class="badge ${cls||''}">${esc(text)}</span>`}
function qualityClass(q){return qClass(q,'q')}

function view(){
 if(!cache||cache.m!==DATA.modules.reputation){
  const m=DATA.modules.reputation||{};
  const c=m.meta||{};
  const rows=m.rows||{};
  const config={};
  (c.towns||[]).forEach(town=>{config[n(town.id)]=town});
  const states={};
  (rows.towns||[]).forEach(row=>{states[n(row.id)]=row});
  cache={m:m,rows:rows,config:config,states:states};
 }
 return cache;
}

function activeTowns(){
 return (view().rows.towns||[]).filter(row=>row.active);
}

function focusTown(){
 return activeTowns().slice().sort((a,b)=>
  n((b.crossed||[]).length)-n((a.crossed||[]).length)
  || n(b.available_gain)-n(a.available_gain)
  || n(b.reputation)-n(a.reputation))[0];
}

function dashboardHtml(rows){
 const totals=rows.totals||{};
 const towns=activeTowns();
 const cross=towns.filter(row=>(row.crossed||[]).length);
 const accepted=towns.reduce((sum,row)=>sum+n(row.accepted),0);
 const nearest=towns.filter(row=>row.next_gate&&n(row.after)<n(row.next_gate.rep))
  .map(row=>({row:row,gap:n(row.next_gate.rep)-n(row.after)}))
  .sort((a,b)=>a.gap-b.gap)[0];
 const highest=totals.highest||{};
 return `<div class="rep-actions">
  <div class="rep-action primary"><div class="k">可接委托</div><div class="v">${num(totals.available_tasks)} 条</div><div class="s">${num(totals.towns)} 城 · +${num(totals.available_gain)} 声望 · +${num(totals.available_stones)} 灵石${accepted?` · ${num(accepted)} 进行中`:''}</div></div>
  <div class="rep-action"><div class="k">可跨档</div><div class="v">${num(cross.length)} 个城镇</div><div class="s">${cross.length?cross.slice(0,3).map(row=>esc(row.name)).join('、'):'完成后仍差下一档'}</div></div>
  <div class="rep-action"><div class="k">下一档</div><div class="v">${nearest?`差 ${num(nearest.gap)}`:'全部可达'}</div><div class="s">${nearest?`${esc(nearest.row.name)} · 完成后 ${num(nearest.row.after)} / ${num(nearest.row.next_gate.rep)}`:'完成后均达当前下一档'}</div></div>
  <div class="rep-action"><div class="k">最高城镇</div><div class="v">${highest.name?esc(highest.name):'—'}</div><div class="s">声望 ${num(highest.reputation)} · 全城货架 ${num(totals.unlocked_shelf)} 档</div></div>
 </div>
 <div class="rep-stats">
  <span>总声望 <b>${num(totals.total_reputation)}</b></span>
  <span>开放城镇 <b>${num(totals.towns)}</b></span>
  <span>已解锁货架 <b>${num(totals.unlocked_shelf)}</b></span>
  <span>已见解锁 <b>${num(totals.seen)}</b></span>
 </div>`;
}

function townRows(){
 const v=view();
 const list=(v.rows.towns||[]).slice();
 if(!ui.showAll)return list.filter(row=>row.active);
 return list;
}

function townTable(){
 const list=townRows();
 if(!list.length)return `<div class="rep-empty">还没有城镇声望数据。</div>`;
 list.sort((a,b)=>{
  if(ui.sort==='order')return n(a.id)-n(b.id);
  return n(b.reputation)-n(a.reputation)||String(a.name).localeCompare(String(b.name),'zh-CN');
 });
 const head=`<div class="rep-tr rep-th">
  <span>城镇</span><span>当前声望</span><span>称号</span><span>本月委托</span><span>完成后</span><span>跨档</span><span>下一档</span>
 </div>`;
 const body=list.map(row=>{
  const on=n(ui.town)===n(row.id);
  const cross=(row.crossed||[]).map(item=>badge(item.label,'ok')).join('')||'<span class="rep-muted">—</span>';
  const next=row.next_gate?`${num(row.next_gate.rep)} · ${esc(row.next_gate.label)}${n(row.after)<n(row.next_gate.rep)?`（差 ${num(n(row.next_gate.rep)-n(row.after))}）`:''}`:'<span class="rep-muted">已满</span>';
  const offers=row.state==='本期未刷新'?'<span class="rep-muted">本期未刷新</span>'
   :`${num(row.offers.length)} 条${row.accepted?`（${num(row.accepted)} 进行中）`:''} · 可获 +${num(row.available_gain)} 声望 · +${num(row.available_stones??row.stones_gain)} 灵石`;
  return `<div class="rep-tr${on?' on':''}${row.active?'':' off'}${(row.crossed||[]).length?' crossable':''}" data-town="${n(row.id)}">
   <span class="rep-town-name">${esc(row.name)}${row.active?'':badge('未开放','off')}${row.seen?badge('已见解锁','ok'):''}${(row.crossed||[]).length?badge('本月可跨档','warn'):''}</span>
   <span class="rep-rep">${num(row.reputation)}</span>
   <span>${esc(row.title)}</span>
   <span class="rep-offers">${offers}</span>
   <span class="rep-after">${num(row.after)}</span>
   <span class="rep-cross">${cross}</span>
   <span class="rep-next">${next}</span>
  </div>`;
 }).join('');
 return `<div class="rep-head">城镇总表<span>${num(list.length)} 个城镇 · 点击行查看委托与货架</span></div><div class="rep-table">${head}${body}</div>`;
}

function chips(list){
 const sorted=list.slice().sort((a,b)=>
  n((b.crossed||[]).length)-n((a.crossed||[]).length)
  || n(b.available_gain)-n(a.available_gain)
  || n(b.reputation)-n(a.reputation));
 return `<div class="rep-chips">${sorted.map(row=>`<button type="button" class="rep-chip${n(ui.town)===n(row.id)?' on':''}${row.active?'':' off'}" data-town="${n(row.id)}">
  ${esc(row.name)}<i>${num(row.reputation)}</i>${(row.crossed||[]).length?'<em>可跨档</em>':''}</button>`).join('')}</div>`;
}

function tierHtml(tier,reputation){
 const items=tier.items||[];
 const names=items.slice(0,4).map(item=>esc(item.name)).join('、')+(items.length>4?` 等 ${items.length} 种`:'');
 const state=tier.unlocked?badge('已解锁','ok'):(tier.after?badge('本月可跨入','warn'):badge('未解锁','off'));
 const diff=Math.max(0,n(tier.threshold)-n(reputation));
 return `<div class="rep-tier${tier.unlocked?' on':''}">
  <div class="rep-tier-head"><b>${num(tier.threshold)} 声望</b>${state}${tier.duplicate?badge(`与 ${num(tier.same_as)} 档相同`,'off'):''}
   <span class="rep-tier-price">${num(tier.price)} 灵石</span></div>
  <div class="rep-tier-items">${names||'无物品'}</div>
  ${items.length?`<details class="rep-tier-all"><summary>展开 ${items.length} 种</summary>
   <div class="rep-tier-list">${items.map(item=>`<span class="rep-item ${qualityClass(item.quality)}">${esc(item.name)}<i>${num(item.price)}</i></span>`).join('')}</div>
  </details>`:''}
  ${!tier.unlocked&&!tier.after?`<div class="rep-tier-hint">还差 ${num(diff)} 声望</div>`:''}
 </div>`;
}

function routeHtml(row){
 const offers=row.offers||[];
 if(!offers.length)return '';
 const groups={},materials={};
 offers.forEach(offer=>{
  const loc=offer.location||'未标注地点';
  const group=groups[loc]||(groups[loc]={tasks:[],items:{}});
  group.tasks.push(offer);
  if(offer.action==='采集'||offer.action==='收集'){
   const count=Math.max(1,n(offer.count));
   group.items[offer.target]=(group.items[offer.target]||0)+count;
   materials[offer.target]=(materials[offer.target]||0)+count;
  }
 });
 const materialList=Object.entries(materials).map(([name,count])=>`<span class="rep-mat">${esc(name)}<i>×${num(count)}</i></span>`).join('');
 const routeRows=Object.entries(groups).map(([loc,group])=>{
  const tasks=group.tasks.map(offer=>{
   const what=offer.target||offer.name;
   const count=offer.action==='采集'||offer.action==='收集'||offer.action==='讨伐'?(offer.count?` ×${num(offer.count)}`:''):'';
   return `<span class="rep-route-task${offer.accepted?' doing':''}">${esc(offer.action||'委托')} ${esc(what)}${count}${offer.accepted?' · 进行中':''}</span>`;
  }).join('');
  return `<div class="rep-route-row"><b>${esc(loc)}</b><div>${tasks}</div></div>`;
 }).join('');
 return `<div class="rep-route rep-block">
  <div class="rep-sub">顺路清单<span>按地点合并 ${offers.length} 条委托</span></div>
  ${materialList?`<div class="rep-gather"><span>本次需收集</span>${materialList}</div>`:''}
  <div class="rep-route-list">${routeRows}</div>
 </div>`;
}

function townHeaderHtml(row){
 const cross=(row.crossed||[]).map(item=>badge(item.label,'warn')).join('');
 return `<div class="rep-town-head">
  <div class="rep-town-title"><b>${esc(row.name)}</b>${badge(row.title,'ok')}${row.active?'':badge('未开放','off')}${row.seen?badge('已见解锁','ok'):''}${cross}</div>
  <div class="rep-town-stats">
   <span>当前 <b>${num(row.reputation)}</b></span>
   <span>完成后 <b>${num(row.after)}</b></span>
   <span>可接 <b>${num(row.available??(row.offers||[]).length)}</b></span>
   <span>进行中 <b>${num(row.accepted)}</b></span>
  </div>
 </div>`;
}

function offersHtml(row){
 const offers=row.offers||[];
 const body=offers.length?offers.map(offer=>`<div class="rep-offer${offer.accepted?' doing':''}">
   <div class="rep-offer-top">
    <span class="rep-offer-name">${esc(offer.name)}</span>
    ${offer.action&&offer.action!=='其他'?badge(offer.action,'act'):''}
    ${badge('难度 '+n(offer.difficulty))}
    ${offer.accepted?badge('进行中','warn'):badge('可接取','')}
    <span class="rep-num">+${num(offer.reputation)} 声望</span>
    ${offer.stones?`<span class="rep-num">+${num(offer.stones)} 灵石</span>`:''}
   </div>
   ${offer.objective?`<div class="rep-offer-obj">${esc(offer.objective)}</div>`:''}
   <div class="rep-offer-meta">
    ${offer.location?`<span class="rep-loc">${esc(offer.location)}</span>`:''}
    ${offer.target?`<span>${esc(offer.action||'目标')} ${esc(offer.target)}${offer.count?` ×${num(offer.count)}`:''}${offer.quality?` · ${esc(offer.quality)}`:''}</span>`:''}
    ${offer.submit_npc_name?`<span>交付：${esc(offer.submit_npc_name)}</span>`:''}
   </div>
  </div>`).join(''):`<div class="rep-empty">本期没有委托记录${row.active?'，等待下次刷新':'（该城镇未开放委托）'}。</div>`;
 return `<div class="rep-block">
  <div class="rep-head">本期委托<span>${num(row.available??offers.length)} 可接 · ${num(row.accepted)} 进行中</span></div>
  ${body}
 </div>`;
}

function shelfHtml(row){
 const v=view(),town=v.config[n(row.id)]||{},shelf=town.shelf||{};
 const tiers=row.tier_states||[];
 const next=tiers.find(tier=>!tier.unlocked);
 const lead=next?`当前 ${num(row.reputation)} · 下一档 ${num(next.threshold)}（还差 ${num(Math.max(0,n(next.threshold)-n(row.reputation)))}）`:'已解锁全部档位';
 const body=tiers.length?tiers.map(tier=>tierHtml(tier,row.reputation)).join(''):`<div class="rep-empty">该城镇暂未配置声望货架。</div>`;
 return `<div class="rep-block">
  <div class="rep-head">声望货架${shelf.npc_name?` · ${esc(shelf.npc_name)}`:''}</div>
  <div class="rep-shelf-lead">${lead}</div>
  ${body}
 </div>`;
}

function titlesHtml(row){
 const v=view(),town=v.config[n(row.id)]||{};
 const body=(town.titles||[]).map(title=>{
  const on=n(row.reputation)>=n(title.min)&&n(row.reputation)<=n(title.max);
  return `<div class="rep-title${on?' on':''}">
   <span>${num(title.min)} – ${num(title.max)}</span><b>${esc(title.name)}</b>
   <span class="rep-muted">${esc(title.desc||'')}</span>
  </div>`;
 }).join('');
 if(!body)return '';
 return `<details class="rep-block rep-pool">
  <summary>称号档位<span>当前 ${esc(row.title)}</span></summary>
  <div class="rep-titles">${body}</div>
 </details>`;
}

function tipsHtml(rows){
 const list=[].concat(rows.warnings||[],DATA.modules.reputation.config_warnings||[]);
 if(!list.length)return '';
 return `<details class="rep-warn"><summary>数据提示 ${list.length} 条</summary>${list.map(text=>`<div>${esc(text)}</div>`).join('')}</details>`;
}

function render(){
 const v=view(),rows=v.rows,box=$('reputation');
 if(!box)return;
 const totals=rows.totals||{};
 const list=townRows();
 if(!ui.town||!v.states[n(ui.town)]||(!ui.showAll&&!v.states[n(ui.town)].active)){
  const first=focusTown()||list[0]||(v.rows.towns||[])[0];
  ui.town=first?n(first.id):0;save();
 }
 const row=v.states[n(ui.town)]||focusTown();
 box.innerHTML=sourceHtml(DATA.modules.reputation)
  +dashboardHtml(rows)
  +tipsHtml(rows)
  +`<div class="rep-tools">
     <label class="rep-check"><input type="checkbox" id="repall"${ui.showAll?' checked':''}>显示未开放城镇</label>
     <select id="repsort" class="rep-input rep-sort">
      <option value="rep"${ui.sort==='rep'?' selected':''}>按声望排序</option>
      <option value="order"${ui.sort==='order'?' selected':''}>按城镇顺序</option>
     </select>
     <span class="rep-meta">点击城镇行或标签查看委托与货架</span>
    </div>`
  +chips(townRows())
  +(row?townHeaderHtml(row)
    +`<div class="rep-layout">
       <div class="rep-main">${routeHtml(row)}${offersHtml(row)}</div>
       <aside class="rep-side">${shelfHtml(row)}${titlesHtml(row)}</aside>
      </div>`
    :`<div class="rep-empty">还没有城镇声望数据。</div>`)
  +townTable();
 bind();
}

function bind(){
 const box=$('reputation');
 if(!box)return;
 const all=$('repall');
 if(all)all.onchange=()=>{ui.showAll=all.checked;save();render()};
 const sort=$('repsort');
 if(sort)sort.onchange=()=>{ui.sort=sort.value;save();render()};
 box.querySelectorAll('[data-town]').forEach(node=>node.onclick=()=>{
  ui.town=n(node.dataset.town);save();render();
 });
}

function initReputation(){
 const m=DATA.modules&&DATA.modules.reputation;
 if(!m)return;
 render();
}

window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['reputation']=initReputation;
})();
