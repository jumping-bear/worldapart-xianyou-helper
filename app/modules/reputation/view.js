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
function qualityClass(q){return 'q'+Math.max(0,Math.min(9,n(q)))}

function view(){
 if(!cache||cache.m!==DATA.modules.reputation){
  const m=DATA.modules.reputation||{};
  const c=m.config||{};
  const rows=m.rows||{};
  const config={};
  (c.towns||[]).forEach(town=>{config[n(town.id)]=town});
  const states={};
  (rows.towns||[]).forEach(row=>{states[n(row.id)]=row});
  cache={m:m,rows:rows,config:config,states:states};
 }
 return cache;
}

function cardsHtml(totals){
 const highest=totals.highest||{};
 return `<div class="rep-cards">
  <div class="card"><div class="k">城镇声望</div><div class="v">${num(totals.total_reputation)}</div><div class="s">${num(totals.towns)} 个开放城镇</div></div>
  <div class="card"><div class="k">本期可获</div><div class="v">${num(totals.available_gain)}</div><div class="s">${num(totals.available_tasks)} 条委托 · ${num(totals.available_stones)} 灵石</div></div>
  <div class="card"><div class="k">已解锁货架</div><div class="v">${num(totals.unlocked_shelf)}</div><div class="s">达到首档货架门槛</div></div>
  <div class="card"><div class="k">已见解锁</div><div class="v">${num(totals.seen)}</div><div class="s">存档解锁提示</div></div>
  <div class="card"><div class="k">最高城镇</div><div class="v">${highest.name?esc(highest.name):'—'}</div><div class="s">声望 ${num(highest.reputation)}</div></div>
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
  const next=row.next_gate?`${num(row.next_gate.rep)} · ${esc(row.next_gate.label)}`:'<span class="rep-muted">已满</span>';
  const offers=row.state==='本期未刷新'?'<span class="rep-muted">本期未刷新</span>'
   :`${num(row.offers.length)} 条 · +${num(row.reputation_gain)} 声望 · +${num(row.stones_gain)} 灵石`;
  return `<div class="rep-tr${on?' on':''}${row.active?'':' off'}" data-town="${n(row.id)}">
   <span class="rep-town-name">${esc(row.name)}${row.active?'':badge('未开放','off')}${row.seen?badge('已见解锁','ok'):''}</span>
   <span class="rep-rep">${num(row.reputation)}</span>
   <span>${esc(row.title)}</span>
   <span class="rep-offers">${offers}</span>
   <span class="rep-after">${num(row.after)}</span>
   <span class="rep-cross">${cross}</span>
   <span class="rep-next">${next}</span>
  </div>`;
 }).join('');
 return `<div class="rep-table">${head}${body}</div>`;
}

function chips(list){
 return `<div class="rep-chips">${list.map(row=>`<button type="button" class="rep-chip${n(ui.town)===n(row.id)?' on':''}${row.active?'':' off'}" data-town="${n(row.id)}">
  ${esc(row.name)}<i>${num(row.reputation)}</i></button>`).join('')}</div>`;
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

function detailHtml(){
 const v=view(),row=v.states[n(ui.town)]||v.rows.towns.find(item=>item.active);
 if(!row)return '';
 if(n(ui.town)!==n(row.id)){ui.town=n(row.id);save()}
 const town=v.config[n(row.id)]||{};
 const shelf=town.shelf||{};
 const tiers=row.tier_states||[];
 const shelfHtml=tiers.length?tiers.map(tier=>tierHtml(tier,row.reputation)).join(''):`<div class="rep-empty">该城镇暂未配置声望货架。</div>`;
 const offerHtml=(row.offers||[]).length?(row.offers||[]).map(offer=>`<div class="rep-offer${offer.accepted?' doing':''}">
   <span class="rep-offer-name">${esc(offer.name)}</span>
   ${badge('难度 '+n(offer.difficulty))}
   ${offer.accepted?badge('进行中','warn'):badge('可接取','')}
   <span class="rep-num">+${num(offer.reputation)} 声望</span>
   ${offer.stones?`<span class="rep-num">+${num(offer.stones)} 灵石</span>`:''}
  </div>`).join(''):`<div class="rep-empty">本期没有委托记录${row.active?'，等待下次刷新':'（该城镇未开放委托）'}。</div>`;
 const titles=(town.titles||[]).map(title=>{
  const on=n(row.reputation)>=n(title.min)&&n(row.reputation)<=n(title.max);
  return `<div class="rep-title${on?' on':''}">
   <span>${num(title.min)} – ${num(title.max)}</span><b>${esc(title.name)}</b>
   <span class="rep-muted">${esc(title.desc||'')}</span>
  </div>`;
 }).join('');
 return `<div class="rep-block">
  <div class="rep-head">${esc(row.name)}<span>${esc(row.title)} · 当前 ${num(row.reputation)} · 完成后 ${num(row.after)}</span></div>
  <div class="rep-detail-grid">
   <div>
    <div class="rep-sub">声望货架${shelf.npc_name?` · ${esc(shelf.npc_name)}`:''}</div>
    ${shelfHtml}
   </div>
   <div>
    <div class="rep-sub">本期委托<span>${num(row.available)} 可接 · ${num(row.accepted)} 进行中</span></div>
    ${offerHtml}
   </div>
  </div>
  <div class="rep-sub">称号档位</div>
  <div class="rep-titles">${titles||'<div class="rep-empty">未配置称号。</div>'}</div>
 </div>`;
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
  const first=list[0]||(v.rows.towns||[])[0];
  ui.town=first?n(first.id):0;save();
 }
 box.innerHTML=sourceHtml(DATA.modules.reputation)
  +cardsHtml(totals)
  +tipsHtml(rows)
  +`<div class="rep-tools">
     <label class="rep-check"><input type="checkbox" id="repall"${ui.showAll?' checked':''}>显示未开放城镇</label>
     <select id="repsort" class="rep-input rep-sort">
      <option value="rep"${ui.sort==='rep'?' selected':''}>按声望排序</option>
      <option value="order"${ui.sort==='order'?' selected':''}>按城镇顺序</option>
     </select>
     <span class="rep-meta">点击城镇行或下方标签查看货架与委托明细</span>
    </div>`
  +chips(townRows().slice().sort((a,b)=>n(b.reputation)-n(a.reputation)))
  +townTable()
  +detailHtml();
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
