/* 支线：页面渲染（自 output.py 原样搬入）。 */
(function(){
const QUEST_FILTER_KEY='worldapart.quest.filters.v2';
function initQuest(){
 const m=DATA.modules&&DATA.modules.quest;if(!m)return;
 const host=$('quest'),st=m.rows||{},rows=st.rows||[],stats=st.stats||{};
 if(!rows.length){host.innerHTML=sourceHtml(m)+'<div class="empty">暂无支线配置</div>';return}
 const byId={};rows.forEach(r=>byId[r.id]=r);
 let state=Object.assign({q:'',status:'all',group:'',view:'chain'},store.get(QUEST_FILTER_KEY,{}));
 const groups=[...new Set(rows.map(r=>r.group||'其他支线'))];
 const giverName=r=>(r.giver&&r.giver.name)||'';
 const locText=r=>{const l=r.location;if(!l){if(r.place_text)return r.place_text;return r.spot||'位置未定'}const path=((l.path&&l.path.length)?l.path:[l.name]).join(' / ');return (r.spot?r.spot+' · ':'')+path};
 const statusText=r=>r.status_label||(!r.accepted?'未接取':r.state_name);
 const statusCls=r=>r.status_cls||(r.done?'ok':r.state===4?'warn':'');
 const linkName=id=>byId[id]?byId[id].name:('#'+id);
 const rewardTip=x=>[(x.sources||[]).join('/'),x.type?('类型：'+x.type):'',x.price?('参考价 '+x.price):'',x.desc||''].filter(Boolean).join(' · ');
 const rewardChip=x=>`<span class="efchip fq${x.quality||0}" title="${esc(rewardTip(x))}">${esc(x.name)} ×${x.min===x.max?x.min:x.min+'-'+x.max}<span class="q">${esc(x.sources.join('/'))}</span></span>`;
 function itemDescs(list){
  const seen={},items=[];
  (list||[]).forEach(x=>{if(!x.desc||seen[x.item])return;seen[x.item]=1;items.push(x)});
  if(!items.length)return '';
  return `<div class="qitemdescs">`+items.map(x=>`<div class="qitemdesc"><b>${esc(x.name)}</b>`+
   (x.type?`<span class="qtype">${esc(x.type)}</span>`:'')+esc(x.desc)+
   (x.price?`<span class="qnum">参考价 ${x.price}</span>`:'')+`</div>`).join('')+`</div>`;
 }
 function detailBody(r){
  const link=(r.prev?esc(linkName(r.prev))+' › ':'')+esc(r.name)+(r.next.length?' › '+r.next.map(linkName).map(esc).join(' / '):'');
  return (r.desc?`<div class="evdesc">${esc(r.desc)}</div>`:'')+
   (giverName(r)?`<div class="qline"><b>委托人</b>${esc(giverName(r))}${r.npc_retired?'<span class="badge warn">已退隐</span>':''}</div>`:'')+
   (r.objectives.length?`<div class="qline"><b>目标</b>${r.objectives.slice(0,3).map(o=>esc(o.text)).join(' · ')}</div>`:'')+
   (r.rewards.length?`<div class="qline"><b>奖励</b><div class="efchips">${r.rewards.map(rewardChip).join('')}</div></div>`+itemDescs(r.rewards):`<div class="qline"><b>奖励</b><span class="muted">剧情向，无固定奖励</span></div>`)+
   (r.unreachable?`<div class="qline"><b>不可达</b>${esc(r.unreachable_text)}</div>`:'')+
   (!r.accepted&&r.status_hint?`<div class="qline"><b>接取</b>${esc(r.status_hint)}</div>`:'')+
   (r.branch&&r.branch_with.length?`<div class="qline"><b>分支</b>与「${esc(r.branch_with.join('」「'))}」二选一，实际以选择为准</div>`:'')+
   `<div class="qline"><b>链路</b>${link}</div>`+
   (r.chain_name?`<div class="qline"><b>剧情线</b>${esc(r.chain_name)}</div>`:'');
 }
 function rewardChips(r,limit){
  const list=(r.rewards||[]).filter(x=>x.name!=='灵石'),stone=r.reward_stone||0;
  if(!list.length)return stone?`<span class="rwstone">灵石 ${stone}</span>`:'';
  const shown=list.slice(0,limit||3);
  return shown.map(x=>`<span class="rwq f${x.quality||0}" title="${esc([(x.sources||[]).join('/'),x.type||'',x.desc||''].filter(Boolean).join(' · '))}">${esc(x.name)}×${x.min===x.max?x.min:x.min+'-'+x.max}</span>`).join('')+
   (list.length>shown.length?`<span class="rwq more">+${list.length-shown.length}</span>`:'')+
   (stone?`<span class="rwstone">灵石 ${stone}</span>`:'');
 }
 function actHint(r){
  return (!r.accepted&&['可接取','条件不足','剧情接取'].indexOf(r.status_label)>=0)
   ?`<span class="qact">${esc(r.status_hint)}</span>`:'';
 }
 function card(r){
  return `<details class="ev" data-quest="${r.id}"><summary>`+
   `<span class="evname">${esc(r.name)}</span>`+
   `<span class="badge ${statusCls(r)}">${esc(statusText(r))}</span>`+
   (r.hidden?'<span class="badge">隐藏</span>':'')+
   `<span class="rwline">${rewardChips(r,2)}</span>`+
   actHint(r)+
   `<span class="evloc">${esc(locText(r))}</span></summary>`+
   `<div class="evbody">${detailBody(r)}</div></details>`;
 }
 function stepRow(r,cls){
  return `<details class="qstep ${cls||''}"><summary>`+
   `<span class="stepno">${r.chain_index||1}</span>`+
   `<span class="evname">${esc(r.name)}</span>`+
   `<span class="badge ${statusCls(r)}">${esc(statusText(r))}</span>`+
   (r.hidden?'<span class="badge">隐藏</span>':'')+
   `<span class="rwline">${rewardChips(r,3)}</span>`+
   actHint(r)+
   `<span class="evloc">${esc(locText(r))}</span></summary>`+
   `<div class="evbody">${detailBody(r)}</div></details>`;
 }
 function optionCard(r,chosen,missed){
  return `<div class="qopt ${chosen?'chosen':''} ${missed?'missed':''}">`+
   `<div class="qname">${esc(r.name)}</div>`+
   `<div class="qoptmeta"><span class="badge ${statusCls(r)}">${esc(statusText(r))}</span>`+
   (r.unreachable?'<span class="badge warn">不可达</span>':'')+`</div>`+
   `<div class="rwline">${rewardChips(r,2)||'<span class="mutedsm">剧情向，无固定奖励</span>'}</div>`+
   (r.unreachable?`<div class="why">${esc(r.unreachable_text)}</div>`:'')+
   (r.branch_missed?`<div class="why">未选：${esc(r.status_hint||r.branch_chosen)}</div>`:'')+
   `</div>`;
 }
 function chainBlock(items,full){
  const source=(full&&full.length)?full:items;
  const sorted=[...items].sort((a,b)=>(a.chain_index||0)-(b.chain_index||0)||a.id-b.id);
  const groups={};
  sorted.forEach(r=>{if(r.branch_key)(groups[r.branch_key]=groups[r.branch_key]||[]).push(r)});
  const taken={},walked=[],todo=[],missed=[],dead=[];
  sorted.forEach(r=>{
   if(r.branch_key&&taken[r.branch_key])return;
   const peers=r.branch_key?groups[r.branch_key]:[r];
   if(r.branch_key)taken[r.branch_key]=1;
   if(peers.some(x=>x.done||x.doing))walked.push(peers);
   else if(peers.every(x=>x.unreachable))dead.push(peers);
   else if(peers.every(x=>x.branch_missed))missed.push(peers);
   else todo.push(peers);
  });
  const flat=list=>list.reduce((acc,cur)=>acc.concat(cur),[]);
  const doneRows=source.filter(r=>r.done),total=source.length;
  const got=doneRows.reduce((sum,r)=>sum+(r.reward_stone||0),0);
  const left=source.filter(r=>!r.done).reduce((sum,r)=>sum+(r.reward_stone||0),0);
  const todoN=flat(todo).length,missN=flat(missed).length,deadN=flat(dead).length;
  const next=[...flat(todo)].sort((a,b)=>statusRank(a)-statusRank(b))[0];
  const block=peers=>peers.length<2?stepRow(peers[0]):`<div class="qbranch ${peers.length>2?'three':''}">`+
   peers.map(x=>optionCard(x,x.done||x.doing,peers.some(y=>y.done||y.doing)&&!(x.done||x.doing))).join('')+`</div>`;
  const secHead=(label,meta)=>`<div class="qsechd"><span>${label}</span><i>${meta||''}</i></div>`;
  const allDone=doneRows.length===total;
  const headBadge=allDone?'<span class="badge ok">已走完</span>'
   :(next?(next.status_label==='可接取'?'<span class="badge ok">可接取</span>'
     :(next.status_label==='条件不足'?'<span class="badge warn">条件不足</span>'
     :`<span class="badge">${esc(next.status_label)}</span>`))
   :(todoN?`<span class="badge">未走 ${todoN}</span>`:'<span class="badge warn">无法继续</span>'));
  const rewardRows=source.filter(r=>r.rewards.length);
  const final=rewardRows.length?rewardRows.reduce((a,b)=>((b.chain_index||0)>=(a.chain_index||0)?b:a)):null;
  const head=`<summary><span class="evname">${esc(items[0].chain_name||'支线')}</span>`+
   headBadge+`<span class="badge">已走 ${doneRows.length}/${total}</span>`+
   `<span class="badge">灵石 ${got}${left?' · 可拿 '+left:''}</span>`+
   (final?`<span class="rwline qfinal"><b>终奖</b>${rewardChips(final,3)}</span>`:'')+
   (missN?`<span class="badge">未选 ${missN}</span>`:'')+
   (deadN?`<span class="badge warn">不可达 ${deadN}</span>`:'')+
   `<span class="evloc">${esc(items[0].group||'')}</span></summary>`;
  const nextHtml=next?`<div class="qnext"><b>下一步</b>${esc(next.name)}<span>${esc(next.status_hint)}</span></div>`:'';
  const walkedHtml=walked.length?`<div class="qwalk">`+secHead('已走',`${doneRows.length} 环 · 灵石 ${got}`)+walked.map(block).join('')+`</div>`:'';
  const todoHtml=todo.length?secHead('未走',`${todoN} 环 · 可拿 ${left} 灵石`)+todo.map(block).join(''):'';
  const missedHtml=missed.length?`<details class="qfold"><summary><span class="qfoldt">未选分支</span>`+
   `<span class="qfoldn">${missN} 环</span><span class="qfoldx">已选了另一条路，游戏里不会有入口</span></summary>`+
   `<div class="qfoldbody">${missed.map(block).join('')}</div></details>`:'';
  const deadHtml=dead.length?`<details class="qfold"><summary><span class="qfoldt">不可达</span>`+
   `<span class="qfoldn">${deadN} 环</span><span class="qfoldx">${esc([...new Set(flat(dead).map(r=>r.unreachable_text))].join('；'))}</span></summary>`+
   `<div class="qfoldbody">${dead.map(block).join('')}</div></details>`:'';
  const open=items.some(r=>r.doing)||!!next||(doneRows.length>0&&!allDone);
  return `<details class="qchain" ${open?'open':''}>${head}<div class="qchainbody">`+
   nextHtml+walkedHtml+todoHtml+missedHtml+deadHtml+`</div></details>`;
 }
 function matched(){
  const q=state.q.trim();
  return rows.filter(r=>{
   if(state.status==='todo'&&r.accepted)return false;
   if(state.status==='doing'&&!r.doing)return false;
   if(state.status==='done'&&!r.done)return false;
   if(state.status==='reward'&&!r.rewards.length)return false;
   if(state.status==='branch'&&!r.branch)return false;
   if(state.status==='blocked'&&(r.done||!r.unreachable))return false;
   if(state.status==='can'&&r.status_label!=='可接取')return false;
   if(state.status==='cond'&&r.status_label!=='条件不足')return false;
   if(state.status==='wait'&&r.status_label!=='待触发')return false;
   if(state.status==='suspect'&&r.status_label!=='疑似已触发')return false;
   if(state.status==='skipped'&&r.status_label!=='疑似已跳过')return false;
   if(state.status==='dialog'&&r.status_label!=='剧情接取')return false;
   if(state.status==='unknown'&&r.status_label!=='触发未知')return false;
   if(state.status==='prev'&&r.status_label!=='前置未完成')return false;
   if(state.status==='missed'&&r.status_label!=='未选分支')return false;
   if(state.status==='gap'&&r.status_label!=='后续已完成')return false;
   if(state.status==='worth'){
    if(r.done||r.doing||r.unreachable||r.branch_missed||!(r.rewards||[]).length)return false;
    if(!['可接取','待触发','剧情接取','前置未完成'].includes(r.status_label))return false;
   }
   if(state.group&&(r.group||'其他支线')!==state.group)return false;
   if(!q)return true;
   const hay=[r.name,r.desc,r.group,r.chain_name,giverName(r),locText(r),r.spot,r.unreachable_text,
    (r.objectives||[]).map(o=>o.text).join(' '),r.rewards.map(x=>x.name).join(' '),
    (r.branch_with||[]).join(' '),linkName(r.prev),r.next.map(linkName).join(' ')].join(' ');
   return hay.includes(q);
  });
 }
 function renderChips(){
  document.querySelectorAll('#qview .chip').forEach(b=>b.classList.toggle('on',b.dataset.view===state.view));
  document.querySelectorAll('#qstatus .chip').forEach(b=>b.classList.toggle('on',b.dataset.st===state.status));
  document.querySelectorAll('#qgroups .chip').forEach(b=>b.classList.toggle('on',b.dataset.group===state.group));
 }
 function statusRank(r){
  const order={'可接取':0,'待触发':1,'剧情接取':2,'前置未完成':3,'条件不足':4,'疑似已触发':5,'疑似已跳过':6,'触发未知':7};
  return order[r.status_label]!==undefined?order[r.status_label]:8;
 }
 function chainRank(items){
  if(items.some(r=>r.doing))return 0;
  const pending=items.filter(r=>!r.done&&!r.unreachable&&!r.branch_missed);
  if(pending.length)return 1+Math.min(...pending.map(statusRank));
  if(items.every(r=>r.done))return 9;
  return 10;
 }
 function renderAll(){
  renderChips();
  $('qs').value=state.q;
  const list=matched();
  const breakdown=`未接取 ${stats.todo||0} 个（含折叠的前置未完成/未选分支/不可达）：可接取 ${stats.can_accept||0} · 条件不足 ${stats.cond_fail||0} · 待触发 ${stats.waiting||0} · 疑似已触发 ${stats.suspect||0} · 疑似已跳过 ${stats.skipped||0} · 剧情接取 ${stats.dialogue||0} · 触发未知 ${stats.unknown||0} · 前置未完成 ${stats.blocked_prev||0} · 未选分支 ${stats.missed||0} · 后续已完成 ${stats.record_gap||0} · 不可达 ${stats.unreachable||0}`;
  if(state.view==='chain'){
   const allMap=new Map();
   rows.forEach(r=>{const key=r.chain_id||('q'+r.id);if(!allMap.has(key))allMap.set(key,[]);allMap.get(key).push(r)});
   const map=new Map();
   list.forEach(r=>{const key=r.chain_id||('q'+r.id);if(!map.has(key))map.set(key,[]);map.get(key).push(r)});
   const chains=[...map.entries()].sort((a,b)=>chainRank(a[1])-chainRank(b[1])
    ||String(a[1][0].chain_name||'').localeCompare(String(b[1][0].chain_name||''),'zh-CN'));
   $('qcount').textContent=`筛选结果：${chains.length} 条剧情线 / ${list.length} 个支线 · ${breakdown}`;
   $('qlist').innerHTML=chains.map(([key,items])=>chainBlock(items,allMap.get(key))).join('')||'<div class="empty">没有符合条件的支线，试试放宽筛选。</div>';
  }else{
   const grouped={};
   list.forEach(r=>{const key=r.group||'其他支线';(grouped[key]=grouped[key]||[]).push(r)});
   $('qcount').textContent=`筛选结果：${list.length} / ${rows.length} 个支线 · ${breakdown}`;
   $('qlist').innerHTML=Object.keys(grouped).map(key=>{
    const items=grouped[key].slice().sort((a,b)=>statusRank(a)-statusRank(b)
     ||(a.chain_index||0)-(b.chain_index||0)||String(a.name).localeCompare(String(b.name),'zh-CN'));
    const rewards=items.filter(r=>r.rewards.length).length;
    const stones=items.reduce((sum,r)=>sum+(r.reward_stone||0),0);
    return `<div class="qgroup">${esc(key)}<span class="gmeta">${items.length} 个 · 带奖励 ${rewards} 个 · 灵石 ${stones}</span></div>`+items.map(card).join('');
   }).join('')||'<div class="empty">没有符合条件的支线，试试放宽筛选。</div>';
  }
 }
 host.innerHTML=sourceHtml(m)+
  `<div class="cards">`+
  `<div class="card"><div class="k">支线完成</div><div class="v">${stats.done||0} <span>/ ${stats.total||0}</span></div><div class="s">进行中 ${stats.doing||0} · 未接取 ${stats.todo||0}</div></div>`+
  `<div class="card"><div class="k">带奖励支线</div><div class="v">${stats.rewards_done||0} <span>/ ${stats.with_rewards||0}</span></div><div class="s">已提交 / 全部</div></div>`+
  `<div class="card"><div class="k">未拿奖励</div><div class="v">${stats.rewards_todo||0} <span>个</span></div><div class="s">灵石约 ${stats.stones_todo||0}（含分支）</div></div>`+
  `<div class="card"><div class="k">当前不可达</div><div class="v">${stats.unreachable||0} <span>个</span></div><div class="s">灵石约 ${stats.unreachable_stones||0} · ${esc(stats.player_realm_name||'未知境界')}${stats.blocked_by_prev?' · 前置连带 '+stats.blocked_by_prev:''}</div></div>`+
  `<div class="card"><div class="k">剧情链 / 二选一</div><div class="v">${stats.chains||0} <span>/ ${stats.branches||0}</span></div><div class="s">链 / 分支组</div></div>`+
  `</div>`+
  `<div class="legend"><span>奖励颜色：</span><span><i style="background:#b4bdca"></i>品质0</span><span><i style="background:#a8dfb4"></i>品质1</span><span><i style="background:#a6cff0"></i>品质2</span><span><i style="background:#cbb2ee"></i>品质3</span><span><i style="background:#f0d38a"></i>品质4</span><span><i style="background:#f0a6a6"></i>品质5</span><span>奖励后面的灰字是来源</span></div>`+
  `<div class="search-panel"><div class="search-fields" style="grid-template-columns:1fr"><label class="search-field"><span>找支线 / 剧情线 / 委托人 / 奖励</span><input id="qs" placeholder="输入任务名、剧情线、地点、NPC 或奖励物品"></label></div></div>`+
  `<div class="chips" id="qview"><span class="chip-label">视图</span>`+
   `<button class="chip" data-view="chain">剧情线</button><button class="chip" data-view="flat">逐条</button></div>`+
  `<div class="chips" id="qstatus"><span class="chip-label">状态</span>`+
   `<button class="chip" data-st="all">全部</button><button class="chip" data-st="worth">值得做 ${stats.worth||0}</button><button class="chip" data-st="todo">未接取 ${stats.todo||0}</button>`+
   `<button class="chip" data-st="can">可接取 ${stats.can_accept||0}</button><button class="chip" data-st="cond">条件不足 ${stats.cond_fail||0}</button>`+
   `<button class="chip" data-st="wait">待触发 ${stats.waiting||0}</button><button class="chip" data-st="suspect">疑似已触发 ${stats.suspect||0}</button>`+
   `<button class="chip" data-st="skipped">疑似已跳过 ${stats.skipped||0}</button>`+
   `<button class="chip" data-st="dialog">剧情接取 ${stats.dialogue||0}</button><button class="chip" data-st="unknown">触发未知 ${stats.unknown||0}</button>`+
   `<button class="chip" data-st="prev">前置未完成 ${stats.blocked_prev||0}</button><button class="chip" data-st="missed">未选分支 ${stats.missed||0}</button>`+
   `<button class="chip" data-st="doing">进行中 ${stats.doing||0}</button><button class="chip" data-st="done">已完成 ${stats.done||0}</button>`+
   `<button class="chip" data-st="reward">有奖励</button><button class="chip" data-st="branch">二选一</button>`+
   `<button class="chip" data-st="blocked">不可达 ${stats.unreachable||0}</button></div>`+
  `<div class="chips" id="qgroups"><span class="chip-label">剧情线</span><button class="chip" data-group="">全部</button>`+
   groups.map(name=>`<button class="chip" data-group="${esc(name)}">${esc(name)}</button>`).join('')+`</div>`+
  `<div id="qcount" class="result-info"></div><div id="qlist"></div>`+
  `<div class="tip">奖励来自任务提交、阶段目标与剧情流水，全部实时读取游戏配置，任务或奖励改动后无需更新模块。奖励物品悬停可看类型与说明，展开任务也能看到物品描述。`+
  `「待触发」表示有明确触发条件（前置任务、进入指定场景、修炼层数或好感度达标等），满足后自动出现；「疑似已触发」表示触发条件已满足但本环没有记录，可能已经触发过或记录缺失；`+
  `「剧情接取」表示要在剧情对话里接取，没有固定入口；「触发未知」表示配置里没有触发条件，只能靠剧情脚本触发，游戏内不一定有入口；`+
  `「疑似已跳过」表示同一段剧情流程里接取了几个任务，其中一个已完成、这个没有记录，多半是同源分支被跳过，也可能是记录缺失；`+
  `「条件不足」表示委托人还在，但接取条件没满足（如好感度、城镇声望），展开可以看到当前数值；`+
  `「未选分支」表示同组另一个选项已经做了，后续环也会一并标为未选分支，游戏里不会有入口；`+
  `「后续已完成」表示后续任务有记录但本环没有，可能是自动跳过或记录缺失；「不可达」表示境界已过或委托人已退隐，前置链上的后续环同样不可达。`+
  `剧情线视图把每条线拆成「已走 / 未走 / 未选分支·不可达」三块：已走的在上、未走的在下，未选中或不可达的默认折叠成一行；奖励直接显示在每一环上，不用展开；可继续的线会给出「下一步」。`+
  `「值得做」只列出未完成、可达且有奖励的任务（可接取 / 待触发 / 剧情接取）；「未接取」按任务数统计，包含折叠在未走、未选分支、不可达里的环，所以比展开后看到的条数多。`+
  `折叠状态、筛选和搜索会记住。</div>`;
 $('qs').oninput=e=>{state.q=e.target.value;store.set(QUEST_FILTER_KEY,state);renderAll()};
 $('qview').onclick=e=>{const b=e.target.closest('[data-view]');if(!b)return;state.view=b.dataset.view;store.set(QUEST_FILTER_KEY,state);renderAll()};
 $('qstatus').onclick=e=>{const b=e.target.closest('[data-st]');if(!b)return;state.status=b.dataset.st;store.set(QUEST_FILTER_KEY,state);renderAll()};
 $('qgroups').onclick=e=>{const b=e.target.closest('[data-group]');if(!b)return;state.group=b.dataset.group;store.set(QUEST_FILTER_KEY,state);renderAll()};
 renderAll();
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['quest']=initQuest;
})();
