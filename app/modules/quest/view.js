/* 支线：页面渲染。2.1 返工：交互式卡关排查助手 + 可点击任务树 + 剧情选项情境。 */
(function(){
const QUEST_FILTER_KEY='worldapart.quest.filters.v3';
function initQuest(){
 const m=DATA.modules&&DATA.modules.quest;if(!m)return;
 const host=$('quest'),st=m.rows||{},rows=st.rows||[],stats=st.stats||{};
 if(!rows.length){host.innerHTML=sourceHtml(m)+'<div class="empty">暂无支线配置</div>';return}
 const edges=st.edges||[],diag=st.diagnostics||{},eggNotes=st.egg_notes||[],gateDiag=st.gate_diag||[];
 const byId={};rows.forEach(r=>byId[r.id]=r);
 const gateByKey={};gateDiag.forEach(g=>gateByKey[g.dialogue+':'+g.option]=g);
 let state=Object.assign({q:'',status:'all',group:'',view:'chain'},store.get(QUEST_FILTER_KEY,{}));
 const groups=[...new Set(rows.map(r=>r.group||'其他支线'))];
 const giverName=r=>(r.giver&&r.giver.name)||'';
 const locText=r=>{const l=r.location;if(!l){if(r.place_text)return r.place_text;return r.spot||'位置未定'}const path=((l.path&&l.path.length)?l.path:[l.name]).join(' / ');return (r.spot?r.spot+' · ':'')+path};
 const statusText=r=>r.status_label||(!r.accepted?'未接取':r.state_name);
 const statusCls=r=>r.status_cls||(r.done?'ok':r.state===4?'warn':'');
 const linkName=id=>byId[id]?byId[id].name:('#'+id);
 const rewardTip=x=>[(x.sources||[]).join('/'),x.type?('类型：'+x.type):'',x.price?('参考价 '+x.price):'',x.desc||''].filter(Boolean).join(' · ');
 const rewardChip=x=>`<span class="efchip fq${x.quality||0}" title="${esc(rewardTip(x))}">${esc(x.name)} ×${x.min===x.max?x.min:x.min+'-'+x.max}<span class="q">${esc(x.sources.join('/'))}</span></span>`;
 const gateChips=r=>(r.option_gates||[]).filter(g=>g.priority==='P0'||!g.priority).map(g=>
   `<span class="qgate ${g.no_grey?'nogrey':''}" title="${esc((g.option||'')+' · '+(g.alias||'')+' · '+(g.grey||'游戏内无灰字提示'))}">${g.no_grey?'[无灰字] ':''}需${esc(g.text)}</span>`).join('');
 // 把一个条件评估渲染成一行，✓/✗/? 一眼可读。
 function checkLine(c){
  if(!c)return '';
  const ok=c.ok===true,bad=c.ok===false;
  return `<div class="dchk ${ok?'ok':(bad?'warn':'')}"><span class="dmark">${ok?'✓':bad?'✗':'?'}</span>`+
   `<span class="dtxt">${esc(c.text||'条件')}</span><span class="dval">${esc(c.cur_text||'')}</span></div>`;
 }
 function condHtml(ce,hideGaps){
  if(!ce||!ce.checks||!ce.checks.length)return '';
  return `<div class="dchks">${ce.checks.map(checkLine).join('')}</div>`+
   (!hideGaps&&ce.gaps&&ce.gaps.length?`<div class="dgaps"><b>还差</b>${ce.gaps.map(g=>`<span>${esc(g)}</span>`).join('')}</div>`:'')+
   (ce.logic?`<div class="dlogic">判定：${esc(ce.logic)}</div>`:'');
 }
 // 彩蛋注解：仅在任务/剧情节点上折叠呈现，默认不剧透。
 function eggHtml(note){
  if(!note)return '';
  return `<details class="degg"><summary><span class="degg-t">展开剧情 · 隐藏结局</span><span class="degg-h">默认折叠，点击才显示</span></summary>`+
   `<div class="degg-body">`+
   (note.trigger?`<div class="eggrow"><b>如何触发</b>${esc(note.trigger)}</div>`:'')+
   (note.complete?`<div class="eggrow"><b>如何完成</b>${esc(note.complete)}</div>`:'')+
   (note.item_name?`<div class="eggrow"><b>关键道具</b>${esc(note.item_name)}${note.item_desc?'：'+esc(note.item_desc):''}</div>`:'')+
   (note.egg?`<div class="eggrow egg"><b>隐藏结局</b>${esc(note.egg)}</div>`:'')+
   `</div></details>`;
 }
 function detailBody(r){
  const link=(r.prev?esc(linkName(r.prev))+' › ':'')+esc(r.name)+(r.next.length?' › '+r.next.map(linkName).map(esc).join(' / '):'');
  return (r.desc?`<div class="evdesc">${esc(r.desc)}</div>`:'')+
   (giverName(r)?`<div class="qline"><b>委托人</b>${esc(giverName(r))}${r.npc_retired?'<span class="badge warn">已退隐</span>':''}</div>`:'')+
   (r.objectives.length?`<div class="qline"><b>目标</b>${r.objectives.slice(0,3).map(o=>esc(o.text)).join(' · ')}</div>`:'')+
   (r.rewards.length?`<div class="qline"><b>奖励</b><div class="efchips">${r.rewards.map(rewardChip).join('')}</div></div>`:`<div class="qline"><b>奖励</b><span class="muted">剧情向，无固定奖励</span></div>`)+
   (gateChips(r)?`<div class="qline"><b>门槛</b><div class="qgates">${gateChips(r)}</div></div>`:'')+
   (r.acq_readable?`<div class="qline"><b>接取条件</b><span title="${esc(r.acq_readable)}">${esc(r.acq_readable)}</span>${r.acq_mixed?'<span class="badge warn">混合逻辑</span>':''}</div>`:'')+
   (r.cond_eval?`<div class="qline"><b>你当前</b>${condHtml(r.cond_eval)}</div>`:'')+
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
   `<span class="rwline">${rewardChips(r,2)}</span>`+actHint(r)+
   `<span class="evloc">${esc(locText(r))}</span></summary>`+
   `<div class="evbody">${detailBody(r)}</div></details>`;
 }
 function stepRow(r,cls){
  return `<details class="qstep ${cls||''}"><summary>`+
   `<span class="stepno">${r.chain_index||1}</span>`+
   `<span class="evname">${esc(r.name)}</span>`+
   `<span class="badge ${statusCls(r)}">${esc(statusText(r))}</span>`+
   (r.hidden?'<span class="badge">隐藏</span>':'')+
   `<span class="rwline">${rewardChips(r,3)}</span>`+actHint(r)+
   `<span class="evloc">${esc(locText(r))}</span></summary>`+
   `<div class="evbody">${detailBody(r)}</div></details>`;
 }
 function optionCard(r,chosen,missed){
  return `<div class="qopt ${chosen?'chosen':''} ${missed?'missed':''}">`+
   `<div class="qname">${esc(r.name)}</div>`+
   `<div class="qoptmeta"><span class="badge ${statusCls(r)}">${esc(statusText(r))}</span>`+
   (r.unreachable?'<span class="badge warn">不可达</span>':'')+`</div>`+
   (gateChips(r)?`<div class="qgates">${gateChips(r)}</div>`:'')+
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
 // 任务树：节点可点击查看触发条件/选项门槛/当前达成；隐藏与彩蛋默认折叠。
 function treeBlock(items,full){
  const all=(full&&full.length)?full:items;
  const chainIds=new Set(all.map(r=>r.id));
  const chainEdges=edges.filter(e=>chainIds.has(e.from)&&chainIds.has(e.to));
  const levels={};
  all.forEach(r=>{const lv=r.chain_index||1;(levels[lv]=levels[lv]||[]).push(r)});
  const lvKeys=Object.keys(levels).map(Number).sort((a,b)=>a-b);
  const kindName={sequential:'顺序',branch:'分叉',conditional:'条件',triggered:'触发'};
  const nodeHtml=r=>{
   const outs=chainEdges.filter(e=>e.from===r.id);
   const inN=chainEdges.filter(e=>e.to===r.id).length;
   const tip=r.hidden?('隐藏任务 · 任务列表不可见'+(r.trigger_label?'；'+r.trigger_label:'')):
     ((r.acq_cond&&r.acq_cond.readable)?r.acq_cond.readable:(r.status_hint||r.name));
   const gateCount=(r.gate_eval||[]).length;
   return `<div class="tnode ${r.hidden?'ishidden':''} ${r.done?'isdone':''}" data-node-quest="${r.id}" title="${esc(tip)}">`+
    `<span class="thead"><span class="tid">${r.id}</span><span class="tname">${esc(r.name)}</span>`+
    (r.hidden?'<span class="tflag hidden">隐藏·不进任务列表</span>':'')+
    (inN>1?`<span class="tflag merge" title="${inN} 条路径在此汇合">汇合 ${inN}</span>`:'')+
    (gateCount?`<span class="tflag gate" title="点击查看该节点的选项门槛与对话情境">门槛 ${gateCount}</span>`:'')+
    `<span class="badge ${statusCls(r)}">${esc(statusText(r))}</span>`+
    `<span class="tmore">点开详情 ›</span></span>`+
    (outs.length?`<div class="tout">`+outs.map(e=>
      `<span class="tedge k-${e.kind}${e.egg?' egg':''}${e.hidden?' tohidden':''}" title="${esc(e.label)}">`+
      `<i>${kindName[e.kind]||e.kind}</i>→${esc(linkName(e.to))}${e.label?' · '+esc(e.label):''}`+
      (e.egg?' <b>彩蛋</b>':'')+`</span>`).join('')+`</div>`:'')+
    (r.egg_note?'<div class="t eggtip">含隐藏结局 · 点开节点后展开剧情</div>':'')+
    `</div>`;
  };
  return `<details class="qtree" open><summary><span class="evname">${esc(all[0].chain_name||'支线')} · 任务树</span>`+
   `<span class="badge">${all.length} 环</span><span class="badge">${chainEdges.length} 关系</span>`+
   `<span class="mutedsm">点击任一节点看触发条件 / 门槛 / 当前达成</span></summary>`+
   `<div class="qtreebody">`+lvKeys.map(lv=>
     `<div class="tlevel"><span class="tlabel">第 ${lv} 环</span><div class="tnodes">`+
     levels[lv].map(nodeHtml).join('')+`</div></div>`).join('')+`</div></details>`;
 }
 // 剧情选项门槛：按剧情线分组，点击展开完整对话情境（替代平铺 chip 面板）。
 function gateTreeSection(){
  const list=gateDiag.filter(g=>g.priority!=='P2');
  if(!list.length)return '';
  const byStory={};
  list.forEach(g=>{const story=(g.context&&g.context.story)||'其他剧情';(byStory[story]=byStory[story]||[]).push(g)});
  const stories=Object.keys(byStory).sort((a,b)=>byStory[b].length-byStory[a].length||a.localeCompare(b,'zh-CN'));
  return `<details class="qtree gatetree"><summary><span class="evname">剧情选项门槛</span>`+
   `<span class="badge">${list.length} 处</span><span class="badge">按剧情线分组</span>`+
   `<span class="mutedsm">点选项看完整对话情境与当前门槛</span></summary><div class="qtreebody">`+
   stories.map(story=>{
    const items=byStory[story];
    return `<div class="gstory"><div class="gstory-h">${esc(story)}<span class="mutedsm">${items.length} 处选项门槛</span></div>`+
     `<div class="gopts">`+items.map(g=>{
      const ev=g.eval||{},ok=ev.ok;
      return `<button class="gopt ${ok===false?'blocked':''}" data-gate="${esc(g.dialogue+':'+g.option)}">`+
       `<span class="gopt-name">${esc(g.option||('对话 '+g.dialogue))}</span>`+
       `<span class="gopt-need">需${esc(g.text)}${g.no_grey?' · 无灰字':''}</span>`+
       `<span class="gopt-cur ${ok===true?'ok':ok===false?'warn':''}">${esc(ev.cur_text||'')||'查看'}</span>`+
       `</button>`;
     }).join('')+`</div></div>`;
   }).join('')+`</div></details>`;
 }
 // ===== 卡关排查助手 =====
 function playerLine(){
  return `当前角色：${esc(stats.player_realm_name||'未知境界')} · 修炼层数 ${stats.player_layer||0}`;
 }
 function diagPanel(){
  const quick=[
   ...eggNotes.map(n=>({key:'q:'+n.quest,label:'隐藏 · '+n.quest_name})),
   ...gateDiag.filter(g=>g.no_grey).slice(0,3).map(g=>({key:'g:'+g.dialogue+':'+g.option,label:(g.context&&g.context.story?g.context.story+' · ':'')+g.option})),
  ];
  return `<div class="qdiag" id="qdiag"><div class="qdiag-h"><div class="qdiag-t">卡关排查助手<span>顺着触发链看“为什么没出现 → 还差什么 → 怎么办”</span></div>`+
   `<div class="qdiag-search"><input id="qdiagInput" list="qdiagList" placeholder="输入任务名或剧情选项，如：未竟之约、凝神观剑"><datalist id="qdiagList">`+
   rows.map(r=>`<option value="${esc(r.name)}">`).join('')+
   gateDiag.filter(g=>g.no_grey).map(g=>`<option value="${esc(g.option)}">`).join('')+`</datalist><button id="qdiagGo">排查</button></div></div>`+
   `<div class="qdiag-meta">${playerLine()}</div>`+
   `<div class="qdiag-quick">`+quick.map(q=>`<button class="qdq" data-diag="${esc(q.key)}">${esc(q.label)}</button>`).join('')+`</div>`+
   `<div class="qdiag-report" id="qdiagReport"><div class="qdiag-empty">选一个任务或剧情选项，我帮你看卡在哪一步。<br>`+
   `<span>例如点上方「隐藏 · 未竟之约」，可看到完整触发链、当前存档满足到哪一步、以及洗髓灵液的隐藏结局（默认折叠，不剧透）。</span></div></div></div>`;
 }
 function ancestorsOf(qid){
  const seen=new Set(),out=[];const queue=[qid];
  while(queue.length&&out.length<14){
   const cur=queue.shift();
   edges.filter(e=>e.to===cur).forEach(e=>{
    if(e.from!==qid&&!seen.has(e.from)&&byId[e.from]){seen.add(e.from);out.push(byId[e.from]);queue.push(e.from)}
   });
   const r=byId[cur];
   if(r&&r.prev&&!seen.has(r.prev)&&byId[r.prev]){seen.add(r.prev);out.push(byId[r.prev]);queue.push(r.prev)}
  }
  out.sort((a,b)=>(a.chain_index||0)-(b.chain_index||0)||a.id-b.id);
  return out;
 }
 function questReport(r){
  const anc=ancestorsOf(r.id),steps=anc.concat([r]);
  const chain=steps.map((s,i)=>{
   const target=s.id===r.id;
   const edge=target?null:edges.find(e=>e.to===s.id);
   return `<div class="dstep ${s.done?'ok':''} ${target?'target':''}" ${target?'':`data-jump="${s.id}"`}>`+
    `<span class="dstep-no">${target?'◆':(i+1)}</span>`+
    `<span class="dstep-name">${esc(s.name)}${s.hidden?' <em>隐藏</em>':''}</span>`+
    `<span class="badge ${statusCls(s)}">${esc(statusText(s))}</span>`+
    (edge&&edge.label?`<span class="dstep-edge">${esc(edge.label)}</span>`:'')+
    (target&&r.status_hint?`<span class="dstep-hint">${esc(r.status_hint)}</span>`:'')+
    `</div>`;
  }).join('');
  const outs=edges.filter(e=>e.from===r.id&&e.egg).map(e=>
    `<div class="dstep egg"><span class="dstep-no">→</span><span class="dstep-name">${esc(linkName(e.to))} <em>彩蛋后续</em></span><span class="dstep-edge">${esc(e.label)}</span></div>`).join('');
  const gates=(r.gate_eval||[]).map(g=>{
   const c=g.context||{},ev=g.eval||{};
   return `<div class="dgate"><div class="dgate-h">${esc(c.story||('对话 '+g.dialogue))} · 选项「${esc(g.option)}」`+
    (g.no_grey?'<span class="badge warn">无灰字</span>':'')+`</div>`+
    (c.lines&&c.lines.length?`<div class="dgate-scene">${c.lines.map(l=>`<div>${esc(l.text)}</div>`).join('')}</div>`:'')+
    (c.siblings&&c.siblings.length?`<div class="dgate-opts">${c.siblings.map(s=>`<span class="${esc(s)===g.option?'cur':''}">${esc(s)}</span>`).join('')}</div>`:'')+
    `<div class="dgate-eval">${checkLine(ev)}</div></div>`;
  }).join('');
  return `<div class="dreport"><div class="dreport-h"><span class="dreport-title">${esc(r.name)}</span>`+
   `<span class="badge ${statusCls(r)}">${esc(statusText(r))}</span>`+
   (r.hidden?'<span class="badge warn">隐藏 · 不进任务列表</span>':'')+
   (r.chain_name?`<span class="mutedsm">${esc(r.chain_name)}</span>`:'')+`</div>`+
   `<div class="dsec-t">触发链（从入口到这里，当前存档逐环状态）</div><div class="dchain">${chain}${outs}</div>`+
   (r.cond_eval&&r.cond_eval.checks&&r.cond_eval.checks.length?
    `<div class="dsec-t">${r.accepted?'接取时的条件（已接取，仅供回顾）':'当前条件达成情况'}</div>${condHtml(r.cond_eval,r.accepted)}`:'')+
   (gates?`<div class="dsec-t">对话选项门槛与情境</div>${gates}`:'')+
   (r.egg_note?eggHtml(r.egg_note):'')+
   (r.status_hint?`<div class="dadvice"><b>说明</b>${esc(r.status_hint)}</div>`:'')+
   `</div>`;
 }
 function gateReport(g){
  const c=g.context||{},ev=g.eval||{};
  const story=(c.story||'剧情对话');
  const lines=(c.lines||[]).map(l=>`<div class="dline"><span class="dl-sub">${esc(l.sub)}</span>${esc(l.text)}</div>`).join('');
  const siblings=(c.siblings||[]).map(s=>`<span class="dopt ${esc(s)===g.option?'cur':''}">${esc(s)}</span>`).join('');
  const attrGuide=(ev.kind==='attr'?`<div class="dadvice"><b>提升方向</b>${esc(ev.text)}是探索属性，可通过打坐修炼、阅历与部分奇遇事件提升；把等级练到 ${esc(ev.need)} 再回来选这个选项即可。</div>`:'');
  return `<div class="dreport"><div class="dreport-h"><span class="dreport-title">${esc(g.option||('对话 '+g.dialogue))}</span>`+
   `<span class="badge">${esc(story)}</span>`+(g.no_grey?'<span class="badge warn">游戏内无灰字</span>':'')+`</div>`+
   `<div class="dsec-t">这是一段「${esc(story)}」剧情里的选项，不是散落的门槛</div>`+
   (c.npc_name?`<div class="dmeta">在场人物：${esc(c.npc_name)} · 对话 ${esc(g.dialogue)}-${esc(g.sub)}</div>`:'')+
   (lines?`<div class="dscene">${lines}</div>`:'')+
   (siblings?`<div class="dsec-t">当时的对话选项</div><div class="dopts">${siblings}</div>`:'')+
   `<div class="dsec-t">这个选项的门槛（你当前）</div>${checkLine(ev)}`+
   (ev.gap?`<div class="dgaps"><b>还差</b><span>${esc(ev.gap)}</span></div>`:'')+
   (g.grey?`<div class="dmeta">游戏内灰字提示：${esc(g.grey)}</div>`:'')+
   attrGuide+`</div>`;
 }
 function openReport(key){
  const box=$('qdiagReport');if(!box)return;
  const kind=key.slice(0,1),id=key.slice(2);
  let html='';
  if(kind==='q'){const r=byId[+id];html=r?questReport(r):'<div class="qdiag-empty">没找到这个任务</div>'}
  else{const g=gateByKey[id]||gateDiag.find(x=>x.dialogue+':'+x.option===id);html=g?gateReport(g):'<div class="qdiag-empty">没找到这个选项</div>'}
  box.innerHTML=html;
  box.querySelectorAll('[data-jump]').forEach(el=>el.onclick=()=>openReport('q:'+el.dataset.jump));
 }
 function matched(){
  const q=state.q.trim();
  return rows.filter(r=>{
   if(state.status==='todo'&&r.accepted)return false;
   if(state.status==='doing'&&!r.doing)return false;
   if(state.status==='done'&&!r.done)return false;
   if(state.status==='reward'&&!r.rewards.length)return false;
   if(state.status==='branch'&&!r.branch)return false;
   if(state.status==='pitfall'&&!(r.option_gates||[]).some(x=>x.priority==='P0'||!x.priority))return false;
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
    (r.branch_with||[]).join(' '),linkName(r.prev),r.next.map(linkName).join(' '),
    (r.option_gates||[]).map(g=>g.text+' '+g.alias).join(' ')].join(' ');
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
  const breakdown=`未接取 ${stats.todo||0} 个：可接取 ${stats.can_accept||0} · 条件不足 ${stats.cond_fail||0} · 待触发 ${stats.waiting||0} · 剧情接取 ${stats.dialogue||0} · 未选分支 ${stats.missed||0} · 不可达 ${stats.unreachable||0}`;
  if(state.view==='tree'||state.view==='chain'){
   const allMap=new Map();
   rows.forEach(r=>{const key=r.chain_id||('q'+r.id);if(!allMap.has(key))allMap.set(key,[]);allMap.get(key).push(r)});
   const map=new Map();
   list.forEach(r=>{const key=r.chain_id||('q'+r.id);if(!map.has(key))map.set(key,[]);map.get(key).push(r)});
   const chains=[...map.entries()].sort((a,b)=>chainRank(a[1])-chainRank(b[1])
    ||String(a[1][0].chain_name||'').localeCompare(String(b[1][0].chain_name||''),'zh-CN'));
   $('qcount').textContent=(state.view==='tree'?'任务树：':'筛选结果：')+`${chains.length} 条剧情线 / ${list.length} 个支线 · ${breakdown}`;
   const gateSec=gateTreeSection();
   $('qlist').innerHTML=gateSec+chains.map(([key,items])=>
     state.view==='tree'?treeBlock(items,allMap.get(key)):chainBlock(items,allMap.get(key))).join('')||'<div class="empty">没有符合条件的支线，试试放宽筛选。</div>';
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
  diagPanel()+
  `<div class="cards">`+
  `<div class="card"><div class="k">支线完成</div><div class="v">${stats.done||0} <span>/ ${stats.total||0}</span></div><div class="s">进行中 ${stats.doing||0} · 未接取 ${stats.todo||0}</div></div>`+
  `<div class="card"><div class="k">带奖励支线</div><div class="v">${stats.rewards_done||0} <span>/ ${stats.with_rewards||0}</span></div><div class="s">已提交 / 全部</div></div>`+
  `<div class="card"><div class="k">未拿奖励</div><div class="v">${stats.rewards_todo||0} <span>个</span></div><div class="s">灵石约 ${stats.stones_todo||0}（含分支）</div></div>`+
  `<div class="card"><div class="k">当前不可达</div><div class="v">${stats.unreachable||0} <span>个</span></div><div class="s">${esc(stats.player_realm_name||'未知境界')}${stats.blocked_by_prev?' · 前置连带 '+stats.blocked_by_prev:''}</div></div>`+
  `<div class="card qpcard"><div class="k">隐藏 / 彩蛋</div><div class="v">${eggNotes.length} <span>条注解</span></div><div class="s">默认折叠，点开才剧透</div></div>`+
  `</div>`+
  `<div class="legend"><span>奖励颜色：</span><span><i style="background:#b4bdca"></i>品质0</span><span><i style="background:#a8dfb4"></i>品质1</span><span><i style="background:#a6cff0"></i>品质2</span><span><i style="background:#cbb2ee"></i>品质3</span><span><i style="background:#f0d38a"></i>品质4</span><span><i style="background:#f0a6a6"></i>品质5</span></div>`+
  `<div class="search-panel"><div class="search-fields" style="grid-template-columns:1fr"><label class="search-field"><span>找支线 / 剧情线 / 委托人 / 奖励 / 门槛</span><input id="qs" placeholder="输入任务名、剧情线、地点、NPC、奖励或门槛"></label></div></div>`+
  `<div class="chips" id="qview"><span class="chip-label">视图</span>`+
   `<button class="chip" data-view="chain">剧情线</button><button class="chip" data-view="tree">任务树</button><button class="chip" data-view="flat">逐条</button></div>`+
  `<div class="chips" id="qstatus"><span class="chip-label">状态</span>`+
   `<button class="chip" data-st="all">全部</button><button class="chip" data-st="pitfall">易踩坑门槛</button><button class="chip" data-st="worth">值得做 ${stats.worth||0}</button>`+
   `<button class="chip" data-st="todo">未接取 ${stats.todo||0}</button><button class="chip" data-st="can">可接取 ${stats.can_accept||0}</button>`+
   `<button class="chip" data-st="cond">条件不足 ${stats.cond_fail||0}</button><button class="chip" data-st="wait">待触发 ${stats.waiting||0}</button>`+
   `<button class="chip" data-st="dialog">剧情接取 ${stats.dialogue||0}</button><button class="chip" data-st="prev">前置未完成 ${stats.blocked_prev||0}</button>`+
   `<button class="chip" data-st="missed">未选分支 ${stats.missed||0}</button><button class="chip" data-st="doing">进行中 ${stats.doing||0}</button>`+
   `<button class="chip" data-st="done">已完成 ${stats.done||0}</button><button class="chip" data-st="branch">二选一</button>`+
   `<button class="chip" data-st="blocked">不可达 ${stats.unreachable||0}</button></div>`+
  `<div class="chips" id="qgroups"><span class="chip-label">剧情线</span><button class="chip" data-group="">全部</button>`+
   groups.map(name=>`<button class="chip" data-group="${esc(name)}">${esc(name)}</button>`).join('')+`</div>`+
  `<div id="qcount" class="result-info"></div><div id="qlist"></div>`+
  `<div class="tip">「卡关排查助手」是入口：输入任务名或剧情选项，或点快捷按钮，就能看到触发链、当前存档逐环状态、还差什么条件；隐藏任务（如未竟之约）默认不剧透，点「展开剧情」才显示洗髓灵液的隐藏结局。`+
  `「任务树」按环数分层，点击任一节点看它的触发条件、选项门槛与当前达成；隐藏任务标「隐藏·不进任务列表」，彩蛋关系默认折叠。`+
  `「剧情选项门槛」按剧情线分组（如云嫣），点选项看完整对话情境与当时有哪些选择——选项门槛不再平铺成一堆 chip。`+
  `「条件不足」等状态会结合当前存档显示还差哪一条（如“神识 ≥ 10（需 Lv10，当前 Lv8）”）。`+
  `折叠状态、筛选与搜索会记住。</div>`+
  `<div class="qmodal" id="qmodal"><div class="qmodal-bg"></div><div class="qmodal-box"><button class="qmodal-x" id="qmodalX">×</button><div id="qmodalBody"></div></div></div>`;
 const doDiag=()=>{
  const val=$('qdiagInput').value.trim();if(!val)return;
  let r=rows.find(x=>x.name===val);
  if(r){openReport('q:'+r.id);return}
  let g=gateDiag.find(x=>x.option===val||x.dialogue+':'+x.option===val);
  if(g){openReport('g:'+g.dialogue+':'+g.option);return}
  r=rows.find(x=>x.name.includes(val))||gateDiag.find(x=>(x.option||'').includes(val)||((x.context&&x.context.story)||'').includes(val));
  if(r){openReport(r.id!==undefined?'q:'+r.id:'g:'+r.dialogue+':'+r.option)}
 };
 $('qdiagGo').onclick=doDiag;
 $('qdiagInput').onkeydown=e=>{if(e.key==='Enter')doDiag()};
 $('qdiag').onclick=e=>{const b=e.target.closest('[data-diag]');if(b)openReport(b.dataset.diag)};
 $('qdiagReport').onclick=e=>{const b=e.target.closest('[data-jump]');if(b)openReport('q:'+b.dataset.jump)};
 $('qlist').onclick=e=>{
  const n=e.target.closest('[data-node-quest]');
  if(n){const r=byId[+n.dataset.nodeQuest];if(r)$('qmodalBody').innerHTML=nodeDetailHtml(r);$('qmodal').classList.add('on');return}
  const g=e.target.closest('[data-gate]');
  if(g){const gate=gateByKey[g.dataset.gate];if(gate)$('qmodalBody').innerHTML=gateReport(gate);$('qmodal').classList.add('on')}
 };
 $('qmodalX').onclick=()=>$('qmodal').classList.remove('on');
 $('qmodal').querySelector('.qmodal-bg').onclick=()=>$('qmodal').classList.remove('on');
 $('qs').oninput=e=>{state.q=e.target.value;store.set(QUEST_FILTER_KEY,state);renderAll()};
 $('qview').onclick=e=>{const b=e.target.closest('[data-view]');if(!b)return;state.view=b.dataset.view;store.set(QUEST_FILTER_KEY,state);renderAll()};
 $('qstatus').onclick=e=>{const b=e.target.closest('[data-st]');if(!b)return;state.status=b.dataset.st;store.set(QUEST_FILTER_KEY,state);renderAll()};
 $('qgroups').onclick=e=>{const b=e.target.closest('[data-group]');if(!b)return;state.group=b.dataset.group;store.set(QUEST_FILTER_KEY,state);renderAll()};
 renderAll();
}
function nodeDetailHtml(r){
 const check=(c)=>c?`<div class="dchk ${c.ok===true?'ok':c.ok===false?'warn':''}"><span class="dmark">${c.ok===true?'✓':c.ok===false?'✗':'?'}</span><span class="dtxt">${esc(c.text||'')}</span><span class="dval">${esc(c.cur_text||'')}</span></div>`:'';
 const gates=(r.gate_eval||[]).map(g=>{const c=g.context||{};return `<div class="dgate"><div class="dgate-h">${esc(c.story||('对话 '+g.dialogue))} · 选项「${esc(g.option)}」${g.no_grey?'<span class="badge warn">无灰字</span>':''}</div>`+
   (c.lines&&c.lines.length?`<div class="dgate-scene">${c.lines.map(l=>`<div>${esc(l.text)}</div>`).join('')}</div>`:'')+
   (c.siblings&&c.siblings.length?`<div class="dgate-opts">${c.siblings.map(s=>`<span class="${esc(s)===g.option?'cur':''}">${esc(s)}</span>`).join('')}</div>`:'')+
   `<div class="dgate-eval">${check(g.eval)}</div></div>`}).join('');
 return `<div class="dreport"><div class="dreport-h"><span class="dreport-title">${esc(r.name)}</span>`+
  `<span class="badge ${r.done?'ok':r.doing?'':'warn'}">${esc(r.status_label||'')}</span>`+
  (r.hidden?'<span class="badge warn">隐藏 · 不进任务列表</span>':'')+
  (r.chain_name?`<span class="mutedsm">${esc(r.chain_name)} · 第 ${r.chain_index||1} 环</span>`:'')+`</div>`+
  (r.desc?`<div class="dmeta">${esc(r.desc)}</div>`:'')+
  `<div class="dsec-t">${r.accepted?'接取条件（已接取，仅供回顾）':'触发条件'}</div>`+
  (r.acq_readable?`<div class="dmeta">${esc(r.acq_readable)}</div>`:'')+
  (r.cond_eval&&r.cond_eval.checks&&r.cond_eval.checks.length?`<div class="dchks">${r.cond_eval.checks.map(check).join('')}</div>`+(!r.accepted&&r.cond_eval.gaps&&r.cond_eval.gaps.length?`<div class="dgaps"><b>还差</b>${r.cond_eval.gaps.map(g=>`<span>${esc(g)}</span>`).join('')}</div>`:''):'<div class="dmeta">无特殊触发条件</div>')+
  (gates?`<div class="dsec-t">选项门槛与对话情境</div>${gates}`:'')+
  (r.egg_note?eggHtml(r.egg_note):'')+
  (r.status_hint?`<div class="dadvice"><b>当前情况</b>${esc(r.status_hint)}</div>`:'')+
  `</div>`;
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['quest']=initQuest;
})();
