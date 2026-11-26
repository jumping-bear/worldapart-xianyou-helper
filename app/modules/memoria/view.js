/* 留影石（忆海回溯）：留影 / 结缘 / 奇遇留影 / 故交往事。 */
(function(){
const STATE_KEY='worldapart.memoria.v1';
const DEFAULTS={view:'shooting',q:'',state:'',sort:'gap',realm:''};
const VIEWS=[['shooting','留影'],['bonds','结缘'],['adventure','奇遇留影'],['friends','故交往事']];
let ui=Object.assign({},DEFAULTS,store.get(STATE_KEY,{}));
let data=null;

function save(){store.set(STATE_KEY,ui)}
function n(v){const x=Number(v);return Number.isFinite(x)?x:0}
function pct(a,b){return b>0?Math.round(a*100/b):0}
function badge(text,cls){return `<span class="badge ${cls||''}">${esc(text)}</span>`}
function avatarHtml(name,src){
 const initial=esc(String(name||'?').slice(0,1));
 if(!src)return `<span class="mem-avatar">${initial}</span>`;
 return `<span class="mem-avatar has-img">${initial}<img src="${esc(src)}" alt="" loading="lazy" onerror="this.remove()"></span>`;
}
function defaultSort(view){return view==='friends'?'recent':view==='shooting'?'gap':'status'}
function realmNames(){
 const names=[];
 (data&&data.adventure||[]).forEach(row=>{
  const name=row.realm_name||'未知境界';
  if(!names.includes(name))names.push(name);
 });
 return names;
}
function stateBadge(got,viewed){
 if(!got)return badge('未收录','off');
 return viewed?badge('已看','ok'):badge('未看','warn');
}
function stateMatch(got,viewed){
 if(!ui.state)return true;
 if(ui.state==='got')return !!got;
 if(ui.state==='missing')return !got;
 if(ui.state==='unseen')return !!got&&!viewed;
 return true;
}
function unlockChips(seg){
 const u=seg.unlock||{},chips=[];
 if(seg.got){
  if(u.quality)chips.push(`<span class="mem-chip">${esc(u.quality)}</span>`);
  return chips.length?`<span class="mem-unlock">${chips.join('')}</span>`:'';
 }
 if(u.entry)chips.push(`<span class="mem-chip route">${esc(u.tag||'灵影')}·留影石</span>`);
 if(u.after)chips.push(`<span class="mem-chip need">前置 ${esc(u.after)}</span>`);
 if(n(u.intimacy)>0)chips.push(`<span class="mem-chip need">好感 ≥${n(u.intimacy)}</span>`);
 if(n(u.stamina)>0)chips.push(`<span class="mem-chip">精力 ${n(u.stamina)}</span>`);
 if(u.quest)chips.push(`<span class="mem-chip quest">支线·${esc(u.quest_name||'未识别支线')}</span>`);
 if(u.reachable===false)chips.push(`<span class="mem-chip block">当前版本无入口</span>`);
 return chips.length?`<span class="mem-unlock">${chips.join('')}</span>`:'';
}
// 下一段留影：按段序取第一个未收录的，条件直接摊在角色摘要行，不用展开。
function nextSeg(card){
 return (card.segs||[]).find(seg=>!seg.got)||null;
}
function nextUnlockLine(card){
 const seg=nextSeg(card);if(!seg)return '';
 const u=seg.unlock||{},bits=[];
 if(u.after)bits.push('前置 '+u.after);
 if(n(u.intimacy)>0)bits.push('好感≥'+n(u.intimacy));
 if(n(u.stamina)>0)bits.push('精力 '+n(u.stamina));
 if(u.quest)bits.push('支线·'+(u.quest_name||'未识别支线'));
 if(u.reachable===false)bits.push('当前版本无入口');
 return `<span class="mem-next"><b>下一段</b>${esc(seg.title||'')}`+
  (seg.hint?`<i>${esc(seg.hint)}</i>`:'')+
  (bits.length?`<em>${esc(bits.join(' / '))}</em>`:'')+`</span>`;
}

function initMemoria(){
 const m=DATA.modules.memoria;if(!m)return;
 data=m.rows||{};
 if(!VIEWS.some(v=>v[0]===ui.view))ui.view='shooting';
 if(!ui.sort)ui.sort=defaultSort(ui.view);
 const st=data.stats||{},sc=st.shooting||{},bc=st.bond||{},ac=st.adventure||{},fc=st.friends||{};
 const reach=typeof sc.reachable==='number'?sc.reachable:sc.total;
 const activeCards=(data.shooting||[]).filter(card=>card.active_title);
 const activeCount=activeCards.length,activeFirst=activeCards[0];
 // 本月没有入口时不能再说“入口已激活、点此查看”，否则会把人带进空列表。
 const activeCard=activeCount
  ? `<div class="card mem-click" id="memactive"><div class="k">本月可做</div><div class="v">${activeCount}<small>${esc(activeFirst.name)}·留影${esc(activeFirst.active_title)} 等 · 点此查看</small></div></div>`
  : `<div class="card"><div class="k">本月可做</div><div class="v">0<small>本月暂无入口 · 每月刷新后重抽</small></div></div>`;
 $('memoria').innerHTML=sourceHtml(m)+`
  <div class="mem-cards">
   <div class="card"><div class="k">留影</div><div class="v">${n(sc.got)}<small>共 ${n(sc.total)} 段${reach<n(sc.total)?` · 可达 ${reach}`:''}</small></div></div>
   ${activeCard}
   <div class="card"><div class="k">结缘</div><div class="v">${n(bc.got)}<small>共 ${n(bc.total)} 位</small></div></div>
   <div class="card"><div class="k">奇遇留影</div><div class="v">${n(ac.got)}<small>共 ${n(ac.total)} 桩</small></div></div>
   <div class="card"><div class="k">故交</div><div class="v">${n(fc.count)}<small>${n(fc.records)} 条往事</small></div></div>
   <div class="card mem-click" id="memunseen"><div class="k">未看过</div><div class="v">${n(st.unseen)}<small>点击只看未看</small></div></div>
  </div>
  <div class="mem-tabs" id="memtabs">${VIEWS.map(v=>{
   const count=v[0]==='shooting'?`${n(sc.got)}/${n(sc.total)}`:v[0]==='bonds'?`${n(bc.got)}/${n(bc.total)}`:v[0]==='adventure'?`${n(ac.got)}/${n(ac.total)}`:`${n(fc.count)} 人`;
   return `<button type="button" class="mem-tab" data-view="${v[0]}">${v[1]}<i>${count}</i></button>`;
  }).join('')}</div>
  ${data.hint?`<div class="mem-tip">${esc(data.hint)}</div>`:''}
  <details class="mem-help"><summary>留影规则：解锁条件与刷新逻辑</summary>
   <div class="mem-tip"><b>激活条件</b>：留影按前置段 / 好感 / 精力 / 支线解锁，没有按天数冷却。游戏里偶尔看不到留影石入口，通常是精力不足（入口要求 10）、前置互动段未完成，个别角色还需要好感 30 / 60。</div>
   <div class="mem-tip"><b>为什么做完一段不立刻出下一段</b>：NPC 每月只保留一个特殊互动入口（留影石就是其中之一），完成后入口会立刻清空，要等下一次每月刷新（游戏内月份切换）重新抽取；所以下一段不一定下个月就出现，也不是卡住。</div>
  </details>
  <div class="mem-filters" id="memfilters"></div>
  <div id="memresult" class="mem-result"></div>
  <div id="memlist"></div>`;
 syncTabs();renderFilters();renderList();
 $('memtabs').onclick=e=>{
  const button=e.target.closest('.mem-tab');if(!button)return;
  ui.view=button.dataset.view;ui.state='';ui.q='';ui.realm='';ui.sort=defaultSort(ui.view);save();
  syncTabs();renderFilters();renderList();
 };
 $('memfilters').addEventListener('input',e=>{
  if(e.target.id!=='memq')return;
  ui.q=e.target.value;save();renderList();
 });
 $('memfilters').addEventListener('change',e=>{
  if(e.target.id==='memstate')ui.state=e.target.value;
  else if(e.target.id==='memrealm')ui.realm=e.target.value;
  else if(e.target.id==='memsort')ui.sort=e.target.value;
  else return;
  save();renderList();
 });
 $('memfilters').addEventListener('click',e=>{
  const stateButton=e.target.closest('[data-mstate]');
  if(stateButton){
   ui.state=stateButton.dataset.mstate;save();renderFilters();renderList();return;
  }
  const button=e.target.closest('[data-act]');if(!button)return;
  const open=button.dataset.act==='expand';
  $('memlist').querySelectorAll('details.mem-npc').forEach(item=>{item.open=open});
 });
 const unseen=$('memunseen');
 if(unseen)unseen.onclick=()=>{
  ui.view='shooting';ui.state='unseen';ui.sort=defaultSort(ui.view);save();
  syncTabs();renderFilters();renderList();
 };
 const active=$('memactive');
 if(active)active.onclick=()=>{
  ui.view='shooting';ui.state='active';ui.q='';ui.sort=defaultSort(ui.view);save();
  syncTabs();renderFilters();renderList();
 };
}

function syncTabs(){
 document.querySelectorAll('#memtabs .mem-tab').forEach(button=>{
  button.classList.toggle('on',button.dataset.view===ui.view);
 });
}

function renderFilters(){
 const box=$('memfilters');if(!box)return;
 const friends=ui.view==='friends',adventure=ui.view==='adventure',shooting=ui.view==='shooting';
 const states=[['','全部状态'],['got','已收录'],['missing','未收录'],['unseen','未看过']];
 const sorts={
  shooting:[['gap','已有留影优先'],['date','最近收录'],['name','按姓名']],
  bonds:[['status','未收录优先'],['name','按姓名']],
  adventure:[['status','已收录优先'],['name','按奇遇名']],
  friends:[['recent','最近往来'],['count','记录最多'],['name','按姓名']]
 }[ui.view]||[['status','默认']];
 if(!sorts.some(item=>item[0]===ui.sort))ui.sort=sorts[0][0];
 const realms=adventure?realmNames():[];
 box.classList.toggle('five',adventure&&realms.length>0);
 box.classList.toggle('compact',shooting);
 // 留影页把“状态”换成可点的快捷芯片，数量一眼可见。
 const quick=shooting?(()=>{
  const cards=data.shooting||[],got=cards.filter(c=>c.got>0).length,
    active=cards.filter(c=>c.active_title).length,
    unseen=cards.reduce((sum,c)=>sum+Math.max(0,c.got-c.viewed),0);
  const items=[['','全部',cards.length],['got','已有留影',got],['active','本月可做',active],
    ['missing','未收录',cards.length-got],['unseen','未看过',unseen]];
  return '<div class="mem-quick">'+items.map(([value,label,count])=>
   `<button type="button" data-mstate="${value}" class="${ui.state===value?'on':''}">${label}<em>${count}</em></button>`).join('')+'</div>';
 })():'';
 box.innerHTML=
  `<label class="mem-f"><span>搜索</span><input id="memq" placeholder="${friends?'搜索姓名或往事内容':adventure?'搜索奇遇名或来由':'搜索角色或留影'}" value="${esc(ui.q)}"></label>`+
  (friends||shooting?'':`<label class="mem-f"><span>状态</span><select id="memstate">${states.map(item=>`<option value="${item[0]}"${ui.state===item[0]?' selected':''}>${item[1]}</option>`).join('')}</select></label>`)+
  (adventure?`<label class="mem-f"><span>境界</span><select id="memrealm"><option value="">全部境界</option>${realms.map(name=>`<option value="${esc(name)}"${ui.realm===name?' selected':''}>${esc(name)}</option>`).join('')}</select></label>`:'')+
  `<label class="mem-f"><span>排序</span><select id="memsort">${sorts.map(item=>`<option value="${item[0]}"${ui.sort===item[0]?' selected':''}>${item[1]}</option>`).join('')}</select></label>`+
  (adventure?'':`<div class="mem-actions"><button type="button" class="mem-btn" data-act="expand">展开全部</button><button type="button" class="mem-btn" data-act="collapse">收起全部</button></div>`)+
  quick;
}

function renderList(){
 const q=ui.q.trim().toLowerCase();
 if(ui.view==='shooting')renderShooting(q);
 else if(ui.view==='bonds')renderBonds(q);
 else if(ui.view==='adventure')renderAdventure(q);
 else renderFriends(q);
}

function activeLine(card){
 if(!card||card.got>=card.total)return '';
 const cls=card.active_title?'':(card.active_other?' is-other':' is-off');
 const text=card.active_title?('当前入口：留影 '+card.active_title)
  :(card.active_other?'当前入口是其它互动 · 留影等下次每月刷新':'本月无留影入口 · 每月刷新后重新抽取');
 return `<span class="mem-active${cls}">${esc(text)}</span>`;
}

function shootingCard(card,q){
 const unseen=card.got-card.viewed;
 const open=(ui.state==='missing'&&card.got<card.total)||(ui.state==='unseen'&&unseen>0)||(ui.state==='active'&&!!card.active_title);
 const next=nextSeg(card);
 const cls=card.got===card.total?' is-done':(card.active_title?' has-active':(card.got>0?' has-got':''));
 const segs=(card.segs||[]).map(seg=>`<div class="mem-seg${seg.got?' on':''}">
   <span class="mem-segname">留影 ${esc(seg.title||'')}</span>${seg.got?'':(seg.active?'<span class="mem-chip active">本月入口</span>':'')}${seg.got?'':(next&&seg.id===next.id?'<span class="mem-chip next">下一段</span>':'')}${stateBadge(seg.got,seg.viewed)}
   ${seg.date?`<span class="mem-date">收录 ${esc(seg.date)}</span>`:''}
   ${unlockChips(seg)}
   ${seg.got?'':`<span class="mem-hint">${esc(seg.hint||'尚无记忆')}</span>`}
  </div>`).join('');
 return `<details class="mem-npc${cls}"${open?' open':''}><summary>
   ${avatarHtml(card.name,card.avatar)}
   <span class="mem-id"><span class="mem-name">${hi(card.name,q)}${card.pet?badge('灵宠','dao'):''}${card.layer?badge(card.layer):''}${unseen>0?badge(`未看 ${unseen}`,'warn'):''}${card.blocked>0?badge(`未开放 ${card.blocked} 段`,'off'):''}</span>
    <span class="mem-sub">${esc(card.title||'暂无称号')}${card.last?` · 最近收录 ${esc(card.last)}`:''}${card.reachable<card.total?` · 当前可达 ${card.reachable}/${card.total}`:''}</span>
    <span class="mem-plan">${activeLine(card)}${nextUnlockLine(card)}</span>
    <span class="mem-bar"><i style="width:${pct(card.got,card.total)}%"></i></span></span>
   <span class="mem-pct">${card.got}/${card.total}<small>${card.got===card.total?'已集齐':(card.got?'收录中':'尚未收录')}</small></span>
  </summary><div class="mem-segs">${segs}</div></details>`;
}

function renderShooting(q){
 let cards=(data.shooting||[]).filter(card=>{
  const text=[card.name,card.title,(card.segs||[]).map(seg=>`${seg.title} ${seg.hint||''}`).join(' ')].join('\n').toLowerCase();
  if(q&&!text.includes(q))return false;
  if(ui.state==='active'&&!card.active_title)return false;
  return stateMatch(card.got>0,card.viewed>0);
 });
 cards.sort((a,b)=>{
  if(ui.sort==='date')return String(b.last||'').localeCompare(String(a.last||''))||a.name.localeCompare(b.name,'zh-CN');
  if(ui.sort==='name')return a.name.localeCompare(b.name,'zh-CN');
  // 已有留影 → 本月可做 → 收录更多 → 名字；没有留影的人统一放到后面。
  return (a.got>0?0:1)-(b.got>0?0:1)
   ||((a.active_title?0:1)-(b.active_title?0:1))
   ||(b.got-a.got)||(b.total-a.total)
   ||a.name.localeCompare(b.name,'zh-CN');
 });
 const withGot=cards.filter(card=>card.got>0), noneGot=cards.filter(card=>!card.got);
 const sum=(list,key)=>list.reduce((total,card)=>total+n(card[key]),0);
 const section=(title,list,cls)=>{
  if(!list.length)return '';
  return `<div class="mem-section ${cls}"><div class="mem-section-head">${title}<em>${list.length}</em>`+
   `<span>${sum(list,'got')}/${sum(list,'total')} 段已收录</span></div>`+
   list.map(card=>shootingCard(card,q)).join('')+`</div>`;
 };
 // 默认视角按“已有留影 / 尚未收录”分段；筛选或其它排序时平铺，避免分组标题与筛选结果打架。
 const grouped=ui.state===''&&ui.sort==='gap';
 const body=cards.length?(grouped
   ?section('已有留影',withGot,'has')+section('尚未收录',noneGot,'none')
   :cards.map(card=>shootingCard(card,q)).join(''))
  :`<div class="empty">没有符合条件的留影角色</div>`;
 $('memresult').textContent=`留影：${cards.length} 位角色（已有留影 ${withGot.length} 位）· 合计 ${sum(cards,'total')} 段，已收录 ${sum(cards,'got')} 段`;
 $('memlist').innerHTML=body;
}

function renderBonds(q){
 let rows=(data.bonds||[]).filter(row=>{
  const text=[row.name,row.npc_title,row.hint].join('\n').toLowerCase();
  if(q&&!text.includes(q))return false;
  return stateMatch(row.got,row.viewed);
 });
 rows.sort((a,b)=>{
  if(ui.sort==='name')return a.name.localeCompare(b.name,'zh-CN');
  return (Number(a.got)-Number(b.got))||((a.sort||0)-(b.sort||0))||a.name.localeCompare(b.name,'zh-CN');
 });
 $('memresult').textContent=`结缘：${rows.length} 位角色，已收录 ${rows.filter(row=>row.got).length} 位`;
 $('memlist').innerHTML=rows.length?rows.map(row=>`<details class="mem-npc"${ui.state==='missing'&&!row.got?' open':''}><summary>
  ${avatarHtml(row.name,row.avatar)}
  <span class="mem-id"><span class="mem-name">${hi(row.name,q)}${row.dao?badge('当前道侣','dao'):''}${row.viewed?badge('已看','ok'):''}</span>
   <span class="mem-sub">${esc(row.npc_title||'结缘影像')}${row.date?` · 收录 ${esc(row.date)}`:''}</span></span>
  <span class="mem-pct">${row.got?'已收录':'未收录'}<small>${row.got?(row.viewed?'已看过':'未看过'):'待结缘'}</small></span>
 </summary><div class="mem-segs"><div class="mem-seg${row.got?' on':''}">
  <span class="mem-segname">${esc(row.title||'结缘影像')}</span>${stateBadge(row.got,row.viewed)}
  ${row.got?'':`<span class="mem-hint">${esc(row.hint||'尚无记忆 · 历经后于此显现')}</span>`}
 </div></div></details>`).join(''):`<div class="empty">没有符合条件的结缘角色</div>`;
}

function renderAdventure(q){
 let rows=(data.adventure||[]).filter(row=>{
  const text=[row.name,row.desc,row.realm_name].join('\n').toLowerCase();
  if(q&&!text.includes(q))return false;
  if(ui.realm&&(row.realm_name||'未知境界')!==ui.realm)return false;
  return stateMatch(row.got,row.viewed);
 });
 rows.sort((a,b)=>{
  if(ui.sort==='name')return String(a.name).localeCompare(String(b.name),'zh-CN');
  return (Number(b.got)-Number(a.got))||((a.realm||0)-(b.realm||0))||((a.sort||0)-(b.sort||0));
 });
 const order=realmNames();
 const groups={};
 rows.forEach(row=>{const key=row.realm_name||'未知境界';(groups[key]=groups[key]||[]).push(row)});
 const body=order.filter(name=>groups[name]).map(name=>{
  const list=groups[name],got=list.filter(row=>row.got).length;
  return `<div class="mem-group">${esc(name)}<span>${got}/${list.length} 已收录</span></div>`+
   list.map(row=>`<div class="mem-row">
    <span class="mem-name">${hi(row.name,q)}</span>${stateBadge(row.got,row.viewed)}
    ${row.got?'':`<span class="mem-chip need">完成该奇遇</span>`}
    <span class="mem-desc">${hi(row.desc||'暂无来由',q)}</span>
    <span class="mem-date">${row.got?(row.date?esc(row.date):'日期未知'):'尚无记忆'}</span>
   </div>`).join('');
 }).join('');
 $('memresult').textContent=`奇遇留影：${rows.length} 桩，已收录 ${rows.filter(row=>row.got).length} 桩，未看 ${rows.filter(row=>row.got&&!row.viewed).length} 桩`;
 $('memlist').innerHTML=body||`<div class="empty">没有符合条件的奇遇留影</div>`;
}

function renderFriends(q){
 let rows=(data.friends||[]).filter(row=>{
  if(!q)return true;
  const text=[row.name,row.title,(row.records||[]).map(record=>record.text).join(' ')].join('\n').toLowerCase();
  return text.includes(q);
 });
 rows.sort((a,b)=>{
  if(ui.sort==='count')return b.count-a.count||a.name.localeCompare(b.name,'zh-CN');
  if(ui.sort==='name')return a.name.localeCompare(b.name,'zh-CN');
  return (b.latest-a.latest)||a.name.localeCompare(b.name,'zh-CN');
 });
 $('memresult').textContent=`故交往事：${rows.length} 位角色，${rows.reduce((sum,row)=>sum+row.count,0)} 条记录`;
 $('memlist').innerHTML=rows.length?rows.map(row=>{
  const stats=(row.stats||[]).map(item=>badge(`${item.label} ${item.value}`)).join('');
  const records=(row.records||[]).map(record=>`<div class="mem-rec">
   <span class="mem-day">${esc(record.day_text)}</span>
   <span class="mem-txt">${hi(record.text,q)}${record.n>1?`<i class="mem-x">×${record.n}</i>`:''}</span>
  </div>`).join('');
  return `<details class="mem-npc"><summary>
   ${avatarHtml(row.name,row.avatar)}
   <span class="mem-id"><span class="mem-name">${hi(row.name,q)}${row.title?badge(row.title):''}</span>
    <span class="mem-sub">最近往来 ${esc(row.latest_text||'往昔某日')}${row.merged<row.count?` · ${row.count} 条（合并重复 ${row.count-row.merged} 条）`:''}</span>
    <span class="mem-stats">${stats}</span></span>
   <span class="mem-pct">${row.count}<small>条往事</small></span>
  </summary><div class="mem-timeline">${records}</div></details>`;
 }).join(''):`<div class="empty">没有符合条件的故交记录</div>`;
}

window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['memoria']=initMemoria;
})();
