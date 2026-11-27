/* 宗门：职位晋升、宗门委托、贡献兑换。 */
(function(){
const SECT_KEY='worldapart.sect.ui.v2';
const DEFAULTS={group:'',q:'',onlyAffordable:false,sort:'price',sim:{},simSrc:''};
let ui=Object.assign({},DEFAULTS,store.get(SECT_KEY,{}));
let cache=null;

function save(){store.set(SECT_KEY,ui)}
function n(v){const x=Number(v);return Number.isFinite(x)?x:0}
function num(v){return n(v).toLocaleString('zh-CN')}
function badge(text,cls){return `<span class="badge ${cls||''}">${esc(text)}</span>`}
function qualityClass(q){return qClass(q,'q')}
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
function commission(rows){return rows.commission||{}}
function refreshText(commissionRow){
 const refresh=commissionRow.refresh||{};
 if(refresh.days_left===null||refresh.days_left===undefined){
  return refresh.last?`上次刷新 ${refresh.last}`:'刷新时间未知';
 }
 if(refresh.days_left<=0)return '已到刷新日，进游戏过一天后刷新';
 return `距下次刷新 ${refresh.days_left} 天${refresh.next?`（${refresh.next}）`:''}`;
}

function dashboardHtml(rows){
 const c=commission(rows);
 const pending=(c.pending||[]).length;
 const active=(c.active||[]).length;
 const available=(c.available||[]).filter(item=>!item.locked).length;
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
  ['累计贡献',num(rows.contribution_total)],
  ['宗门声望',num(rows.reputation)],
  ['灵石',num(rows.stones)],
  ['下期刷新',refreshText(c)]
 ];
 return `<div class="sec-actions">
  <div class="sec-action${pending?' primary':''}"><div class="k">待提交委托</div><div class="v">${pending}</div><div class="s">${pending?'回「委托」面板提交，别占着位置':'暂无待提交'}</div></div>
  <div class="sec-action"><div class="k">进行中</div><div class="v">${active}</div><div class="s">已接 ${n(c.accepted_count)} / ${n(c.limit)} · 还可接 ${n(c.remaining)}</div></div>
  <div class="sec-action"><div class="k">可接委托</div><div class="v">${available}</div><div class="s">${n(c.locked_count)?`另有 ${n(c.locked_count)} 条职位不符`:refreshText(c)}</div></div>
  <div class="sec-action"><div class="k">晋升</div><div class="v">${promotionValue}</div><div class="s">${promotionSub}</div></div>
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
  <div class="sec-hint">晋升后年俸 ${num(p.salary)} 灵石；部分宗门委托只开放给真传弟子及以上职位。</div>
 </div>`;
}

function incomeHtml(rows){
 const c=commission(rows),salary=rows.salary||{};
 return `<div class="sec-block">
  <div class="sec-head">本期委托收益<span>${refreshText(c)}</span></div>
  <div class="sec-income">
   <div><span>可接委托</span><b>+${num(c.available_contribution)}</b><small>声望 +${num(c.available_reputation)}</small></div>
   <div><span>已接未交</span><b>+${num(c.accepted_contribution)}</b><small>声望 +${num(c.accepted_reputation)}</small></div>
   <div><span>年俸</span><b>${num(salary.annual)}</b><small>灵石</small></div>
   <div><span>下次俸禄</span><b>${salary.amount>0?num(salary.amount):'待结算'}</b>${salary.next_time?`<small>${esc(salary.next_time)}</small>`:''}</div>
  </div>
  <div class="sec-hint" style="margin-top:8px">只统计当前存档里已挂出的委托；接取和提交都在游戏「委托」面板内完成。</div>
 </div>`;
}

function commissionGuide(c){
 const place=c.scene_name?`宗门「${esc(c.scene_name)}」`:'宗门驻地';
 const npcHint=c.npc_name?`（${esc(c.npc_name)}在${place}）`:'';
 return `${place}场景顶部有「委托」按钮${npcHint}。任务每 ${num(c.refresh.days||30)} 天刷新 ${num(c.refresh_count||9)} 条，`
  +`最多同时接 ${num(c.limit||10)} 条，接取后 ${num(c.completion_days||90)} 天内不做会失效；完成后回同一面板提交。`;
}

function taskCard(card,kind){
 const isPending=kind==='pending';
 const progress=card.progress_target?`<span class="sec-num">${num(card.progress_now)}/${num(card.progress_target)}</span>`:'';
 const stateBadge=kind==='pending'?badge('待提交','warn')
  :kind==='active'?badge('进行中','warn')
  :kind==='submitted'?badge('已提交','ok')
  :(card.locked?badge('职位不符','warn'):badge('可接取',''));
 const remain=kind==='active'&&card.remaining_days!==null&&card.remaining_days!==undefined
  ?badge(`剩 ${num(card.remaining_days)} 天`,card.remaining_days<=7?'warn':'') :'';
 const meta=[];
 if(card.location)meta.push(card.location);
 if(card.target)meta.push(`${card.target}${card.count?` ×${num(card.count)}`:''}`);
 if(card.position_text)meta.push(`需 ${card.position_text}`);
 return `<div class="sec-task-card${isPending?' pending':''}${card.locked?' locked':''}">
  <div class="sec-task-top">
   <span class="sec-task-name">${esc(card.name)}</span>
   ${badge(card.type_name,'act')}${badge('难度 '+num(card.difficulty))}
   ${stateBadge}${remain}${progress}
  </div>
  ${card.objective?`<div class="sec-task-obj">${esc(card.objective)}</div>`:''}
  <div class="sec-task-meta">
   <span class="sec-task-reward">贡献 +${num(card.contribution)}</span>
   ${card.reputation?`<span class="sec-task-reward">声望 +${num(card.reputation)}</span>`:''}
   ${card.stones?`<span class="sec-task-reward">灵石 +${num(card.stones)}</span>`:''}
   ${meta.map(text=>`<span>${esc(text)}</span>`).join('')}
  </div>
 </div>`;
}

function commissionsHtml(rows){
 const c=commission(rows);
 const groups=(c.groups||[]).filter(g=>n(g.count)>1);
 const groupHint=groups.length
  ?`<div class="sec-route"><b>顺路</b>${groups.slice(0,6).map(g=>`<span title="${esc((g.names||[]).join('、'))}">${esc(g.location)} ×${num(g.count)}</span>`).join('')}${groups.length>6?'<span>…</span>':''}</div>`
  :'';
 const pending=(c.pending||[]).map(card=>taskCard(card,'pending')).join('');
 const active=(c.active||[]).map(card=>taskCard(card,'active')).join('');
 const available=(c.available||[]).map(card=>taskCard(card,'available')).join('');
 const submitted=(c.submitted||[]).map(card=>taskCard(card,'submitted')).join('');
 const empty=`<div class="sec-empty">本期没有可接的宗门委托。进游戏刷新后再同步，或检查是否已接满 ${num(c.limit||10)} 条。</div>`;
 return `<div class="sec-block">
  <div class="sec-head">宗门委托<span>${esc(rows.sect_name||'')} · ${refreshText(c)}</span></div>
  <div class="sec-offer-note">${commissionGuide(c)}</div>
  ${groupHint}
  ${pending?`<div class="sec-sub">待提交 ${(c.pending||[]).length} 条</div>${pending}`:''}
  ${active?`<div class="sec-sub">进行中 ${(c.active||[]).length} 条</div>${active}`:''}
  <div class="sec-sub">本期委托 ${(c.available||[]).length} 条 · 可接 ${(c.available||[]).filter(card=>!card.locked).length}</div>
  ${available||empty}
  ${submitted?`<details class="sec-pool"><summary>已提交 ${(c.submitted||[]).length} 条（下期刷新后移除）</summary>${submitted}</details>`:''}
 </div>`;
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
   <button type="button" class="sec-buy" data-buy="${esc(key)}" ${can?'':'disabled'} title="仅规划，不进游戏存档">模拟 +1</button>
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

function joinHtml(){
 const v=view(),sects=v.config.sects||[];
 const playable=sects.filter(s=>s.playable),closed=sects.filter(s=>!s.playable);
 return `<div class="sec-notice">当前存档尚未加入宗门。加入后可查看职位晋升、宗门委托与贡献兑换。</div>
  <div class="sec-block"><div class="sec-head">可加入宗门<span>${playable.length} 个</span></div>
   <div class="sec-join">${playable.map(s=>`<div class="sec-join-row">
    <b>${esc(s.name)}</b>${s.region?badge(s.region):''}
    <span class="sec-join-desc">${esc(s.feature||s.desc||'')}</span>
    <span class="sec-join-meta">${s.headquarters_name?esc(s.headquarters_name):''}${s.join_quest?` · 入宗任务 ${esc(s.join_quest_name||'未识别任务')}`:''}</span>
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
  box.innerHTML=sourceHtml(DATA.modules.sect)+warningsHtml(rows)+joinHtml();
  return;
 }
 box.innerHTML=sourceHtml(DATA.modules.sect)+dashboardHtml(rows)+warningsHtml(rows)
  +`<div class="sec-layout">
    <div class="sec-main">${commissionsHtml(rows)}</div>
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
