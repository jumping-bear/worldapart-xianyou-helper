/* 宗门：职位晋升、贡献兑换、宗门任务与灵材征收。 */
(function(){
const SECT_KEY='worldapart.sect.ui.v1';
const DEFAULTS={group:'',q:'',onlyAffordable:false,sort:'price',sim:{},simSrc:''};
let ui=Object.assign({},DEFAULTS,store.get(SECT_KEY,{}));
let cache=null;

function save(){store.set(SECT_KEY,ui)}
function n(v){const x=Number(v);return Number.isFinite(x)?x:0}
function num(v){return n(v).toLocaleString('zh-CN')}
function badge(text,cls){return `<span class="badge ${cls||''}">${esc(text)}</span>`}
function qualityClass(q){return 'q'+Math.max(0,Math.min(9,n(q)))}
function view(){
 if(!cache||cache.m!==DATA.modules.sect){
  const m=DATA.modules.sect||{};
  const c=m.meta||{};
  cache={m:m,rows:m.rows||{},config:c,
   sects:Object.fromEntries((c.sects||[]).map(s=>[n(s.id),s])),
   positions:Object.fromEntries((c.positions||[]).map(p=>[n(p.id),p])),
   shop:Object.fromEntries(((c.sects||[]).reduce((a,s)=>a.concat(s.exchange||[]),[])).map(e=>[String(e.item)+'|'+e.npc,e]))};
 }
 return cache;
}
function simState(){
 const v=view(),rows=v.rows;
 if(ui.simSrc!==String(rows.src||'')){ui.sim={};ui.simSrc=String(rows.src||'');save()}
 return ui.sim||{};
}
function simSpent(){
 const v=view(),sim=simState();
 let total=0;
 (v.config.sects||[]).forEach(s=>(s.exchange||[]).forEach(e=>{
  const count=n(sim[String(e.item)+'|'+e.npc]);
  if(count)total+=count*n(e.price);
 }));
 return total;
}
function balance(){return n(view().rows.contribution)-simSpent()}
function canBuy(entry){
 const v=view(),rows=v.rows;
 return n(entry.price)<=balance()
  && n(entry.position)<=n(rows.position_level)
  && n(entry.realm)<=n(rows.realm);
}
function nextShopEntry(rows,balanceValue){
 const sect=view().sects[n(rows.sect_id)]||{};
 return (sect.exchange||[]).filter(entry=>n(entry.price)>balanceValue
  && n(entry.position)<=n(rows.position_level)
  && n(entry.realm)<=n(rows.realm)).sort((a,b)=>n(a.price)-n(b.price))[0];
}
function groupName(key){return key==='low'?'灵果灵物':'功法招式'}

function cardsHtml(rows){
 const offers=(rows.offers||[]).filter(item=>!item.completed);
 const shopCount=rows.exchange_total||0;
 return `<div class="sec-cards">
  <div class="card"><div class="k">当前贡献</div><div class="v">${num(rows.contribution)}</div><div class="s">可兑换 ${n(rows.exchange_affordable)} / ${shopCount} 件</div></div>
  <div class="card"><div class="k">本期可领</div><div class="v">${num(rows.offer_contribution)}</div><div class="s">${offers.length} 项任务 · 声望 +${num(rows.offer_reputation)}</div></div>
  <div class="card"><div class="k">累计贡献</div><div class="v">${num(rows.contribution_total)}</div><div class="s">本宗累计投入</div></div>
  <div class="card"><div class="k">宗门声望</div><div class="v">${num(rows.reputation)}</div><div class="s">${esc(rows.position_name||'未任职')}</div></div>
  <div class="card"><div class="k">灵石</div><div class="v">${num(rows.stones)}</div><div class="s">可用于城镇货架</div></div>
 </div>`;
}

function dashboardHtml(rows){
 const accepted=rows.accepted||[];
 const pending=accepted.filter(item=>item.state_text==='待提交').length;
 const active=accepted.filter(item=>item.state_text==='进行中').length;
 const p=rows.promotion;
 let promotionValue='已满级';
 let promotionSub='当前版本最高职位';
 if(p){
  const missing=[];
  if(!p.reputation_ok)missing.push('声望 '+num(Math.max(0,n(p.reputation)-n(p.reputation_now))));
  if(!p.realm_ok)missing.push('境界');
  promotionValue=missing.length?'差 '+missing.join(' + '):'可晋升';
  promotionSub='下一职位 '+esc(p.name);
 }
 const stats=[
  ['当前贡献',num(rows.contribution)],
  ['委托板',`${(rows.offers||[]).length} 条 · +${num(rows.offer_contribution)}`],
  ['累计贡献',num(rows.contribution_total)],
  ['宗门声望',num(rows.reputation)],
  ['灵石',num(rows.stones)]
 ];
 const next=nextShopEntry(rows,n(rows.contribution));
 const affordSub=next?`再攒 ${num(n(next.price)-n(rows.contribution))} 可换「${esc(next.name)}」`:`当前贡献 ${num(rows.contribution)}`;
 return `<div class="sec-actions">
  <div class="sec-action${pending?' primary':''}"><div class="k">待提交</div><div class="v">${pending}</div><div class="s">${pending?'先去交掉，别占着任务位':'暂无待提交'}</div></div>
  <div class="sec-action"><div class="k">进行中</div><div class="v">${active}</div><div class="s">可同时接 ${n(rows.slots&&rows.slots.limit)} 条 · 已接 ${n(rows.slots&&rows.slots.accepted)} · 还可接 ${n(rows.slots&&rows.slots.remaining)}</div></div>
  <div class="sec-action"><div class="k">晋升</div><div class="v">${promotionValue}</div><div class="s">${promotionSub}</div></div>
  <div class="sec-action"><div class="k">可兑换</div><div class="v">${n(rows.exchange_affordable)} 件</div><div class="s">${affordSub}</div></div>
 </div>
 <div class="sec-stats">${stats.map(item=>`<span>${item[0]} <b>${item[1]}</b></span>`).join('')}</div>`;
}

function careerHtml(rows){
 const v=view(),career=v.config.career||[],current=n(rows.position_id);
 if(!career.length)return '';
 const steps=career.map(pos=>{
  const level=n(pos.level),now=n(rows.position_level);
  const isNext=rows.promotion&&n(pos.id)===n(rows.promotion.position);
  const state=level<now?'done':(n(pos.id)===current?'now':(isNext?'next':''));
  return `<div class="sec-step ${state}">
   <b>${esc(pos.name)}</b>
   <small>${num(pos.reputation)} 声望 · ${esc(v.config.realms[String(pos.realm)]||'无境界要求')}</small>
  </div>`;
 }).join('<span class="sec-arrow">›</span>');
 return `<div class="sec-block">
  <div class="sec-head">晋升<span>${esc(rows.sect_name||'未入宗')}</span></div>
  ${promotionHtml(rows)}
  <details class="sec-pool"><summary>完整职位路径</summary><div class="sec-path">${steps}</div></details>
 </div>`;
}

function promotionHtml(rows){
 const p=rows.promotion;
 if(!p)return `<div class="sec-empty">已达当前版本可晋升的最高职位。</div>`;
 const repPct=p.reputation>0?Math.min(100,Math.round(p.reputation_now*100/p.reputation)):100;
 const realmText=p.realm?`${esc(p.realm_now_name||'未知')} / ${esc(p.realm_name||('境界 '+p.realm))}`:'无境界要求';
 return `<div class="sec-promo">
  <div class="sec-promo-title">下一职位：<b>${esc(p.name)}</b>${p.reputation_ok&&p.realm_ok?badge('条件已达成','ok'):badge('条件未满足','warn')}</div>
  <div class="sec-cond">
   <span class="sec-cond-k">当前职位</span><span class="sec-cond-v">${esc(rows.position_name||'未任职')}</span>
   <span class="sec-cond-k">宗门声望</span><span class="sec-cond-v">${num(p.reputation_now)} / ${num(p.reputation)} ${p.reputation_ok?'✓':''}</span>
   <span class="sec-cond-k">境界</span><span class="sec-cond-v">${realmText}${p.realm_ok?' ✓':''}</span>
   <span class="sec-cond-k">晋升考核</span><span class="sec-cond-v">${esc(p.quest_name||(p.quest?('任务 '+p.quest):'满足条件后前往宗主处晋升'))}</span>
  </div>
  <div class="sec-bar"><i style="width:${repPct}%"></i></div>
  <div class="sec-hint">晋升后年俸 ${num(p.salary)}，每周期任务上限 ${num(p.task_limit)} 项。</div>
 </div>`;
}

function incomeHtml(rows){
 const salary=rows.salary||{},refresh=rows.refresh||{};
 return `<div class="sec-block">
  <div class="sec-head">本月收入<span>${esc(refresh.next?('下次刷新 '+refresh.next):'刷新时间未知')}</span></div>
  <div class="sec-income">
   <div><span>委托板贡献</span><b>+${num(rows.offer_contribution)}</b></div>
   <div><span>委托板声望</span><b>+${num(rows.offer_reputation)}</b></div>
   <div><span>年俸</span><b>${num(salary.annual)}</b></div>
   <div><span>下次俸禄</span><b>${salary.amount>0?num(salary.amount):'待结算'}</b>${salary.next_time?`<small>${esc(salary.next_time)}</small>`:''}</div>
  </div>
  <div class="sec-hint" style="margin-top:8px">仅统计委托板可接任务；已接任务的奖励以游戏内为准。</div>
 </div>`;
}

function tasksHtml(rows){
 const accepted=rows.accepted||[];
 const list=rows.offers||[];
 const slots=rows.slots||{};
 const refresh=rows.refresh||{};
 const pending=accepted.filter(item=>item.state_text==='待提交');
 const done=accepted.filter(item=>item.state_text==='已提交');
 const active=accepted.filter(item=>!['待提交','已提交'].includes(item.state_text));
 const card=item=>{
  const isPending=item.state_text==='待提交';
  const state=isPending?badge('待提交','warn'):(item.state_text==='已提交'?badge('已提交','ok'):badge(item.state_text||'进行中','warn'));
  const progress=item.progress_target?`<span class="sec-num">${num(item.progress_now)}/${num(item.progress_target)}</span>`:'';
  return `<div class="sec-task-card${isPending?' pending':''}${item.state_text==='已提交'?' done':''}">
   <div class="sec-task-top">
    <span class="sec-task-name">${esc(item.name)}</span>
    ${item.action&&item.action!=='其他'?badge(item.action,'act'):''}
    ${state}${progress}
   </div>
   ${item.objective?`<div class="sec-task-obj">${esc(item.objective)}</div>`:''}
   <div class="sec-task-meta">
    ${item.location?`<span>${esc(item.location)}</span>`:''}
    ${item.target?`<span>${esc(item.action||'目标')} ${esc(item.target)}${item.count?` ×${num(item.count)}`:''}${item.quality?` · ${esc(item.quality)}`:''}</span>`:''}
   </div>
  </div>`;
 };
 const group=(title,items)=>items.length?`<div class="sec-sub">${title} ${items.length} 条</div>`+items.map(card).join(''):'';
 // 委托板：每周期只挂 3 条外务委托，到期轮换；「3 条」≠「可同时接上限」。
 const refreshText=refresh.next?`每周期轮换 · 下次刷新 ${esc(refresh.next)}`:'每周期轮换';
 const offerHint=`委托板每周期只挂 <b>${list.length}</b> 条外务委托${refresh.next?`，下次刷新 <b>${esc(refresh.next)}</b>`:''}；做完或换周期才出新的一批。「${list.length} 条」只是本期挂出的数量，不是「只能做 ${list.length} 个」，与可同时接上限 <b>${n(slots.limit)}</b> 条是两回事。`;
 const offerBody=list.length?list.map(item=>{
  const state=item.completed?badge('已完成','ok'):(item.locked?badge('职位不足','warn'):badge('可领取',''));
  return `<div class="sec-task${item.completed?' done':''}">
   <span class="sec-task-name">${esc(item.name)}</span>
   ${badge(item.type_name||'外务委托')}${badge('难度 '+n(item.difficulty))}
   ${item.min_position?badge(item.min_position_name||('职位 '+item.min_position)):''}
   <span class="sec-num">+${num(item.contribution)} 贡献</span>
   ${item.reputation?`<span class="sec-num">+${num(item.reputation)} 声望</span>`:''}
   ${item.stones?`<span class="sec-num">+${num(item.stones)} 灵石</span>`:''}
   ${state}
  </div>`;
 }).join(''):`<div class="sec-empty">本期委托板没有挂出的外务委托。</div>`;
 const offerBlock=`<div class="sec-block">
  <div class="sec-head">委托板 · 外务委托<span>${refreshText}</span></div>
  <div class="sec-hint sec-offer-note">${offerHint}</div>
  ${offerBody}
 </div>`;
 // 差遣/要务/重任：走执事/长老领取，与委托板是两套，已接的进入任务日志。
 const dutyHint=`宗门差遣 / 要务 / 重任与委托板是两套：这三类找执事 / 长老领取，不在委托板上；已接的会进入任务日志，计在「可同时接 <b>${n(slots.limit)}</b> 条」里。`;
 const dutyBody=(group('待提交',pending)+group('进行中',active)+group('已提交',done))
  ||`<div class="sec-empty">当前没有已接取的差遣 / 要务 / 重任。这三类任务找执事 / 长老领取，不在委托板上。</div>`;
 const dutyBlock=`<div class="sec-block">
  <div class="sec-head">宗门差遣 · 要务 · 重任<span>可同时接 ${n(slots.limit)} 条 · 已接 ${n(slots.accepted)} · 待提交 ${pending.length}</span></div>
  <div class="sec-hint">${dutyHint}</div>
  ${dutyBody}
 </div>`;
 return offerBlock+dutyBlock;
}

function shopHtml(rows){
 const v=view(),sect=v.sects[n(rows.sect_id)];
 if(!sect)return '';
 const all=sect.exchange||[];
 const groups=['low','high'];
 const q=String(ui.q||'').trim().toLowerCase();
 const balanceNow=balance();
 const nextEntry=nextShopEntry(rows,balanceNow);
 const list=all.filter(entry=>{
  if(ui.group&&entry.role!==ui.group)return false;
  if(ui.onlyAffordable&&!canBuy(entry))return false;
  if(q){
   const text=(entry.name+' '+(entry.type||'')+' '+(entry.position_name||'')).toLowerCase();
   if(!text.includes(q))return false;
  }
  return true;
 });
 const cat={low:[],high:[]};
 list.forEach(entry=>{(cat[entry.role]||cat.low).push(entry)});
 const sortFn={
  price:(a,b)=>n(a.price)-n(b.price),
  position:(a,b)=>n(a.position)-n(b.position)||n(a.price)-n(b.price),
  name:(a,b)=>String(a.name).localeCompare(String(b.name),'zh-CN')
 }[ui.sort]||((a,b)=>n(a.price)-n(b.price));
 const sim=simState();
 const rowHtml=entry=>{
  const key=String(entry.item)+'|'+entry.npc;
  const got=n(sim[key]);
  const can=canBuy(entry);
  const req=[];
  if(entry.position)req.push(entry.position_name||('职位 '+entry.position));
  if(entry.realm)req.push(entry.realm_name||('境界 '+entry.realm));
  return `<div class="sec-shop-row${can?'':' locked'}">
   <span class="sec-shop-name ${qualityClass(entry.quality)}">${esc(entry.name)}</span>
   ${badge(entry.type||groupName(entry.role))}
   <span class="badge">×${n(entry.count)}</span>
   ${req.length?badge('需 '+req.join(' / '),'warn'):''}
   ${got?badge('模拟兑换 ×'+got,'ok'):''}
   <span class="sec-price">${num(entry.price)} 贡献</span>
   <button type="button" class="sec-buy" data-buy="${esc(key)}" ${can?'':'disabled'}>兑换</button>
  </div>`;
 };
 const body=groups.filter(key=>cat[key].length).map(key=>{
  const items=cat[key].slice().sort(sortFn);
  const sum=items.reduce((total,entry)=>total+n(entry.price),0);
  return `<div class="sec-shop-group">${groupName(key)}<span>${items.length} 件 · 全清 ${num(sum)} 贡献</span></div>`+
   items.map(rowHtml).join('');
 }).join('');
 return `<div class="sec-block">
  <div class="sec-head">贡献兑换<span>${esc(sect.low_npc_name||'')} / ${esc(sect.high_npc_name||'')} · 全清 ${num(sect.exchange_total)} 贡献</span></div>
  <div class="sec-shop-lead">当前可兑换 <b>${n(rows.exchange_affordable)}</b> / ${all.length} 件${nextEntry?` · 再攒 <b>${num(n(nextEntry.price)-balanceNow)}</b> 贡献可换「${esc(nextEntry.name)}」`:''}</div>
  <div class="sec-shop-tools">
   <button type="button" class="sec-chip${ui.group===''?' on':''}" data-group="">全部</button>
   <button type="button" class="sec-chip${ui.group==='low'?' on':''}" data-group="low">灵果灵物</button>
   <button type="button" class="sec-chip${ui.group==='high'?' on':''}" data-group="high">功法招式</button>
   <input id="secq" class="sec-input" placeholder="搜索物品 / 类型" value="${esc(ui.q)}">
   <label class="sec-check"><input type="checkbox" id="seconly"${ui.onlyAffordable?' checked':''}>只看可兑换</label>
   <select id="secsort" class="sec-input sec-sort">
    <option value="price"${ui.sort==='price'?' selected':''}>按价格</option>
    <option value="position"${ui.sort==='position'?' selected':''}>按职位</option>
    <option value="name"${ui.sort==='name'?' selected':''}>按名称</option>
   </select>
   <span class="sec-balance">模拟余额 <b>${num(balanceNow)}</b> 贡献${simSpent()?` · 已花 ${num(simSpent())}`:''}</span>
   <button type="button" class="sec-reset" id="secreset" ${simSpent()?'':'disabled'}>重置模拟</button>
  </div>
  ${body||`<div class="sec-empty">没有符合筛选条件的兑换项。</div>`}
 </div>`;
}

function purchaseHtml(rows){
 const sect=view().sects[n(rows.sect_id)]||{};
 const purchase=rows.purchase||{};
 const current=purchase.current||[],delivered=purchase.delivered||[];
 const pool=sect.purchases||[];
 const currentHtml=current.length?current.map(order=>`<div class="sec-task">
   <span class="sec-task-name">${esc(order.name)}</span><span class="badge">×${n(order.count)}</span>
   <span class="sec-num">+${num(order.contribution)} 贡献</span>${badge(order.state||'待交付')}
  </div>`).join(''):`<div class="sec-empty">本期没有征收委托${delivered.length?`（已交付 ${delivered.length} 单）`:''}。${purchase.refresh?('下次刷新：'+esc(purchase.refresh)):''}</div>`;
 const poolHtml=pool.length?`<details class="sec-pool"><summary>可征收清单 ${pool.length} 项</summary>${
  pool.map(order=>`<div class="sec-task">
   <span class="sec-task-name">${esc(order.name)}</span><span class="badge">×${n(order.count)}</span>
   ${order.min_position?badge(order.min_position_name||('职位 '+order.min_position)):''}
   <span class="sec-num">+${num(order.contribution)} 贡献</span>
   ${order.reputation?`<span class="sec-num">+${num(order.reputation)} 声望</span>`:''}
  </div>`).join('')}</details>`:'';
 return `<div class="sec-block">
  <div class="sec-head">灵材征收<span>${esc(rows.position_name||'')}</span></div>
  ${currentHtml}${poolHtml}
 </div>`;
}

function joinHtml(){
 const v=view(),sects=v.config.sects||[];
 const playable=sects.filter(s=>s.playable),closed=sects.filter(s=>!s.playable);
 return `<div class="sec-notice">当前存档尚未加入宗门。加入后可查看职位晋升、贡献兑换、宗门任务与灵材征收。</div>
  <div class="sec-block"><div class="sec-head">可加入宗门<span>${playable.length} 个</span></div>
   <div class="sec-join">${playable.map(s=>`<div class="sec-join-row">
    <b>${esc(s.name)}</b>${s.region?badge(s.region):''}
    <span class="sec-join-desc">${esc(s.feature||s.desc||'')}</span>
    <span class="sec-join-meta">${s.headquarters_name?esc(s.headquarters_name):''}${s.join_quest?` · 入宗任务 ${s.join_quest}`:''}</span>
   </div>`).join('')}</div>
  </div>
  ${closed.length?`<div class="sec-hint">另有 ${closed.length} 个宗门暂未配置藏经阁兑换，本期不展示：${closed.map(s=>esc(s.name)).join('、')}。</div>`:''}`;
}

function warningsHtml(rows){
 const list=[].concat(rows.warnings||[],DATA.modules.sect.config_warnings||[]);
 if(!list.length)return '';
 return `<details class="sec-warn"><summary>数据提示 ${list.length} 条</summary>${list.map(text=>`<div>${esc(text)}</div>`).join('')}</details>`;
}

function render(){
 const v=view(),rows=v.rows,box=$('sect');
 if(!box)return;
 if(!rows||rows.error){
  box.innerHTML=sourceHtml(DATA.modules.sect||{})+'<div class="empty">没有可用的宗门数据。</div>';
  return;
 }
 if(!rows.in_sect){
  box.innerHTML=sourceHtml(DATA.modules.sect)+cardsHtml(rows)+warningsHtml(rows)+joinHtml();
  return;
 }
 box.innerHTML=sourceHtml(DATA.modules.sect)+dashboardHtml(rows)+warningsHtml(rows)
  +`<div class="sec-layout">
    <div class="sec-main">${tasksHtml(rows)}${purchaseHtml(rows)}</div>
    <aside class="sec-side">${careerHtml(rows)}${incomeHtml(rows)}</aside>
   </div>`
  +shopHtml(rows);
 bind();
}

function bind(){
 const box=$('sect');
 if(!box)return;
 box.querySelectorAll('[data-group]').forEach(button=>button.onclick=()=>{
  ui.group=button.dataset.group;save();render();
 });
 const q=$('secq');
 if(q)q.oninput=()=>{ui.q=q.value;save();render();const next=$('secq');if(next){next.focus();next.setSelectionRange(next.value.length,next.value.length)}};
 const only=$('seconly');
 if(only)only.onchange=()=>{ui.onlyAffordable=only.checked;save();render()};
 const sort=$('secsort');
 if(sort)sort.onchange=()=>{ui.sort=sort.value;save();render()};
 box.querySelectorAll('[data-buy]').forEach(button=>button.onclick=()=>{
  const key=button.dataset.buy;
  const v=view(),rows=v.rows,sect=v.sects[n(rows.sect_id)]||{};
  const entry=(sect.exchange||[]).find(item=>String(item.item)+'|'+item.npc===key);
  if(!entry||!canBuy(entry))return;
  const sim=simState();
  sim[key]=n(sim[key])+1;
  save();render();
 });
 const reset=$('secreset');
 if(reset)reset.onclick=()=>{ui.sim={};save();render()};
}

function initSect(){
 const m=DATA.modules&&DATA.modules.sect;
 if(!m)return;
 if(ui.simSrc!==String((m.rows||{}).src||'')){ui.sim={};ui.simSrc=String((m.rows||{}).src||'');save()}
 render();
}

window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['sect']=initSect;
})();
