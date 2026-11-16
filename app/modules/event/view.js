/* 奇遇：页面渲染（自 output.py 原样搬入）。 */
(function(){
const EVENT_FILTER_KEY='worldapart.event.filters.v1';
function initEvent(){
 const m=DATA.modules&&DATA.modules.event;if(!m)return;
 const host=$('event'),st=m.rows||{},rows=st.rows||[],catalog=st.reward_index||[];
 const stats=st.stats||{},metaStats=st.meta_stats||{};
 if(!rows.length&&!catalog.length){host.innerHTML=sourceHtml(m)+'<div class="empty">暂无奇遇配置</div>';return}
 const byId={};rows.forEach(r=>byId[r.id]=r);
 const childrenOf={};rows.forEach(r=>{if(r.parent&&byId[r.parent])(childrenOf[r.parent]=childrenOf[r.parent]||[]).push(r)});
 const topRows=rows.filter(r=>!(r.parent&&byId[r.parent]));
 const groupMembers=r=>[r].concat(childrenOf[r.id]||[]);
 const itemNames={};catalog.forEach(x=>itemNames[x.item]=x.name);
 const attrs=st.attrs||{},money=st.money||0,ch=st.character||DATA.character||{};
 let state=Object.assign({q:'',status:'',realm:'',mode:'event',missing:false,condOnly:false,itemQuality:'',itemType:'',itemUse:false,itemSort:'score',focus:0},store.get(EVENT_FILTER_KEY,{}));
 const gradeName=g=>(st.grades||{})[String(g)]||('第'+(g||'?')+'档');
 const gradeCls=g=>'g'+(g||0);
 const confName=c=>c==='exact'?'位置确定':c==='inferred'?'位置推断':'位置未定';
 const confCls=c=>c==='exact'?'loc-exact':c==='inferred'?'loc-inferred':'loc-unknown';
 const locText=r=>{const l=r.location;if(!l)return '位置未定';const path=((l.path&&l.path.length)?l.path:[l.name]).join(' / ');return (l.spot?l.spot+' · ':'')+path};
 const itemName=id=>itemNames[id]||('物品 '+id);
 const cmp=(a,op,b)=>{if(a===null||a===undefined)return null;switch(op){case'>=':return a>=b;case'>':return a>b;case'<=':return a<=b;case'<':return a<b;case'==':return a===b;case'!=':return a!==b;default:return null}};
 const condPass=c=>{
  if(!c||!c.checks||!c.checks.length)return null;
  let ok=true;
  for(const k of c.checks){
   let value=null;
   if(k.t==='attr')value=(attrs[k.a]||{}).level||0;
   else if(k.t==='money')value=money;
   else return null;
   const part=cmp(value,k.op,k.v);if(part===null)return null;ok=ok&&part;
  }
  return ok;
 };
 const condSummary=r=>{
  const seen=new Set(),list=[];
  for(const n of Object.values((r.tree||{}).nodes||{})){
   for(const o of n.options||[])for(const c of o.conds||[])for(const k of c.checks||[]){
    let value=null,label='';
    if(k.t==='attr'){const a=attrs[k.a]||{};value=a.level||0;label=`${a.name||('属性'+k.a)} ${k.op} ${k.v}（当前 ${value}）`}
    else if(k.t==='money'){value=money;label=`灵石 ${k.op} ${k.v}（当前 ${value}）`}
    else continue;
    const opt=o.t||'继续',key=opt+'|'+label;
    if(seen.has(key))continue;seen.add(key);
    list.push({opt,label,ok:cmp(value,k.op,k.v),gate:['>=','>','=='].includes(k.op)});
   }
  }
  return list;
 };
 const checkText=k=>k.t==='attr'?`${(attrs[k.a]||{}).name||('属性'+k.a)} ${k.op} ${k.v}`:k.t==='money'?`灵石 ${k.op} ${k.v}`:`物品 ${k.i} ${k.op} ${k.v}`;
 const rewardChip=(x,got)=>`<span class="efchip fq${x.quality||0}${got?' got':''}" title="${esc((x.desc||'')+' · 掉率 '+x.chance+'%')}">${esc(x.name)} ×${x.min===x.max?x.min:x.min+'-'+x.max}${x.chance>=100?'':'<i>'+x.chance+'%</i>'}<span class="q">品质${x.quality||0}</span></span>`;
 const realmRows=topRows.filter(r=>Number(r.realm||0)===Number(st.current_realm||0));
 const gateRows=topRows.filter(r=>!r.achieved&&groupMembers(r).some(m=>condSummary(m).some(c=>c.gate&&c.ok===false)));
 const cards=
  `<div class="card"><div class="k">奇遇达成</div><div class="v">${stats.achieved||0} <span>/ ${stats.events||0}</span></div>${stats.history?`<div class="s">含历史记录 ${stats.history} 个</div>`:''}</div>`+
  `<div class="card"><div class="k">当前境界可做</div><div class="v">${realmRows.filter(r=>!r.achieved).length} <span>/ ${realmRows.length}</span></div><div class="s">${esc(st.current_realm_name||'当前境界')} 还未达成</div></div>`+
  `<div class="card"><div class="k">属性门槛不足</div><div class="v">${gateRows.length} <span>个</span></div><div class="s">出发前优先补属性</div></div>`+
  `<div class="card"><div class="k">奖励图鉴</div><div class="v">${catalog.length} <span>种</span></div><div class="s">未拥有 ${catalog.filter(x=>!x.owned).length} 种</div></div>`;
 
 function treeHtml(r,id,seen,depth){
  const t=r.tree||{},n=(t.nodes||{})[id];
  if(!n)return '';
  if(seen.has(id))return '<div class="tloop">↩ 回到上文</div>';
  if(depth>8)return '<div class="tloop">…分支过深，已省略</div>';
  seen.add(id);
  const picked=new Set((r.choices||[]).map(c=>c.text));
  const narration=n.text||'';
  let html=`<div class="tnode">${narration?`<div class="ttext" title="${esc(narration)}">${esc(narration.length>90?narration.slice(0,90)+'…':narration)}</div>`:''}`;
  (n.options||[]).forEach(o=>{
   const seenText=new Set(),chips=[];
   (o.conds||[]).forEach(c=>{
    const full=c.text||'条件';if(seenText.has(full))return;seenText.add(full);
    const p=condPass(c);
    const brief=(c.checks&&c.checks.length)?c.checks.map(checkText).join(' 且 '):full;
    const short=brief.length>40?brief.slice(0,40)+'…':brief;
    chips.push(`<span class="cchip ${p===true?'ok':p===false?'bad':'unk'}" title="${esc(full)}">${p===true?'✓':p===false?'✗':'?'} ${esc(short)}</span>`);
   });
   const shown=chips.slice(0,4),more=chips.length-shown.length;
   html+=`<div class="topt${picked.has(o.t)?' picked':''}"><span class="tarrow">↳</span>${o.t?`<b>${esc(o.t)}</b>`:'<span class="muted">继续</span>'}`+
    shown.join('')+(more?`<span class="cchip unk">+${more} 条条件</span>`:'')+(o.eff||[]).map(e=>`<span class="effchip">${esc(e)}</span>`).join('')+`</div>`;
   if(o.to&&o.to.startsWith('e:')){
    const eid=+o.to.slice(2),e=(r.endings||[]).find(x=>x.id===eid);
    html+=`<div class="tend">结局：${e?`<b>${esc(e.title)}</b><span class="egrade ${gradeCls(e.grade)}">${esc(e.grade_name||gradeName(e.grade))}</span>${e.rewards.map(x=>rewardChip(x,e.got)).join('')}`:'#'+eid}</div>`;
   }else if(o.to){
    html+=`<div class="tbranch">${treeHtml(r,o.to,seen,depth+1)}</div>`;
   }
   (o.after||[]).forEach(tid=>{
    const eid=+tid.slice(2),e=(r.endings||[]).find(x=>x.id===eid);
    html+=`<div class="tend">结算结局：${e?`<b>${esc(e.title)}</b>${e.rewards.map(x=>rewardChip(x,e.got)).join('')}`:'#'+eid}</div>`;
   });
  });
  seen.delete(id);
  return html+'</div>';
 }
 function eventCard(r,nested){
  const endings=r.endings||[];
  const got=endings.filter(e=>e.got||e.history_got).length;
  const conds=condSummary(r);
  const branches=nested?[]:(childrenOf[r.id]||[]);
  const badges=`<span class="badge ${r.achieved?'ok':'off'}">${r.achieved?(r.achieved_via_branch?'分支达成':'已达成'):'未达成'}</span>`+
   `<span class="badge">结局 ${got}/${endings.length}</span>`+
   `<span class="badge">${r.one_off?'一次性':'可重复'}</span>`+
   (r.history_only?'<span class="badge">历史达成</span>':'')+
   (branches.length?`<span class="badge">含 ${branches.length} 条分支</span>`:'')+
   (nested&&r.branch_selected?'<span class="badge ok">已选此分支</span>':'')+
   (nested&&r.branch_closed?'<span class="badge off">未选分支</span>':'')+
   (!nested&&r.parent&&byId[r.parent]?`<span class="badge">隶属 ${esc(byId[r.parent].name)}</span>`:'')+
   `<span class="badge ${confCls((r.location||{}).conf)}">${confName((r.location||{}).conf)}</span>`;
  const condHtml=conds.length?(()=>{
   const groups={};conds.forEach(c=>{(groups[c.opt]=groups[c.opt]||[]).push(c)});
   return `<div class="evline"><b>选项条件</b><div class="condopts">`+Object.keys(groups).map(opt=>
    `<div class="condopt"><span class="condname">${esc(opt)}</span>`+
    groups[opt].map(c=>`<span class="cchip ${c.ok===false?'bad':c.ok===true?'ok':'unk'}">${c.ok===false?'✗':c.ok===true?'✓':'?'} ${esc(c.label)}</span>`).join('')+
    `</div>`).join('')+`</div></div>`;
  })():'';
  const grants=(r.grants||[]).length?`<div class="evline"><b>实际所得</b>${r.grants.map(g=>`${esc(itemName(g.item))} ×${g.count}${g.delivered?'':'（未交付）'}`).join(' · ')}</div>`:'';
  const picked=(r.choices||[]).length?`<div class="evline"><b>选择记录</b>${r.choices.map(c=>esc(c.text)+(c.count>1?`<span class="muted">（累计选 ${c.count} 次）</span>`:'')).join(' · ')}</div>`+
   `<div class="muted small">括号里是存档累计点击次数，不是奖励倍数。</div>`:'';
  const unknown=r.unknown_ending?`<div class="evline"><b>结局</b>#${r.ending}（配置未收录）</div>`:'';
  const closedHint=r.branch_closed?'<div class="evline muted">母奇遇已因其它分支达成，此分支不再计入未完成。</div>':'';
  const body=endings.map(e=>`<div class="eend${e.got?' got':''}"><div class="eend-head">`+
   `<span class="egrade ${gradeCls(e.grade)}">${esc(e.grade_name||gradeName(e.grade))}</span>`+
   `<span class="eend-title">${esc(e.title)}</span>`+
   (e.got?'<span class="badge ok">已达成</span>':'')+
   (e.history_got&&!e.got?'<span class="badge">历史达成</span>':'')+
   (e.reward_ok===false?'<span class="badge warn">奖励未收录</span>':'')+
   `</div>${e.rewards.length?`<div class="erewards"><b>奖励</b><div class="efchips">${e.rewards.map(x=>rewardChip(x,e.got)).join('')}</div></div>`:'<div class="muted small">无奖励记录</div>'}`+
   `${(e.path||[]).length?`<div class="epath"><b>达成路径</b><div class="psteps">${e.path.map((step,i)=>`<span class="pstep"><i>${i+1}</i>${esc(step)}</span>`).join('<span class="parrow">›</span>')}</div></div>`:''}`+
   `${e.summary?`<div class="eend-sum">${esc(e.summary)}</div>`:''}`+
   `${(e.detail||[]).length?`<div class="eend-detail">${e.detail.map(esc).join(' · ')}</div>`:''}</div>`).join('');
  const tree=r.tree?`<details class="etree"><summary>完整对话分支（可选） <span class="muted">静态可确认 ${r.tree_endings||0}/${endings.length} 条结局</span></summary>`+
   `<div class="treewrap">${treeHtml(r,r.tree.root,new Set(),0)}</div>`+
   `<div class="muted small">分支只作补充；优先看上方每条结局的奖励和「达成路径」。✓/✗ 表示当前角色是否满足条件，未标结局的分支由结算判定。</div></details>`:'';
  const branchHtml=branches.length?`<div class="evbranches"><div class="evbranch-head">分支路线 ${branches.length} 条 · 任一分支达成即视为整条奇遇完成，其余分支不再计入未完成</div>`+
   branches.map(k=>eventCard(k,true)).join('')+`</div>`:'';
  return `<details class="ev${nested?' evbranch':''}${r.branch_selected?' branch-done':''}${r.branch_closed?' branch-closed':''}" data-event="${r.id}"${state.focus===r.id?' open':''}><summary><span class="evname">${esc(r.name)}</span>${badges}<span class="evloc">${esc(locText(r))}</span></summary>`+
   `<div class="evbody">${r.desc?`<div class="evdesc">${esc(r.desc)}</div>`:''}${closedHint}${condHtml}${grants}${picked}${unknown}<div>${body}</div>${tree}${branchHtml}</div></details>`;
 }
 function itemCard(x){
  const sources=(x.sources||[]).slice().sort((a,b)=>(b.got?1:0)-(a.got?1:0)||(b.expected||0)-(a.expected||0));
  const srcIds=[...new Set(sources.map(s=>s.event))];
  const endedIds=srcIds.filter(id=>{const r=byId[id];return r&&(r.achieved||r.branch_closed)});
  const srcBadge=srcIds.length?`<span class="badge ${endedIds.length===srcIds.length?'ok':''}" title="已结算的结局或母奇遇已完成的未选分支都算已结束">来源奇遇 ${endedIds.length}/${srcIds.length} 已完成</span>`:'';
  const rowsHtml=sources.map(s=>{
   const ev=byId[s.event];
   const evDone=!!(ev&&ev.achieved),evClosed=!!(ev&&ev.branch_closed);
   const status=s.got?' <span class="badge ok">已获得此结局</span>':
    evDone?' <span class="badge ok">奇遇已完成</span>':
    evClosed?' <span class="badge off" title="母奇遇已由其它分支达成，此分支未选，该奖励已无法再通过这条分支获取">母奇遇已完成·未选此分支</span>':'';
   return `<div class="evline"><b>${esc(s.event_name)}</b>${esc(s.ending_title)}`+
    ` <span class="muted">${s.chance>=100?'必得':s.chance+'%'} · 期望 ${s.expected}</span>`+
    status+` <button class="jumpbtn" data-jump="${s.event}">查看奇遇</button></div>`;
  }).join('');
  const useHint=t=>({'炼丹药材':'可作炼丹配方材料','炼丹成品':'成品丹药，可用于服用、任务或 NPC 求购','炼器材料':'可作炼器材料','NPC 求购':'NPC 会收购，或任务需要它'}[t]||t);
  const reasons=(x.reasons||[]).map(t=>`<span class="reason" title="评分理由">${esc(t)}</span>`).join('');
  const uses=(x.use||[]).length?`<div class="reasons">${x.use.map(t=>`<span class="reason use" title="${esc(useHint(t))}">${esc(t)}</span>`).join('')}</div>`:'';
  return `<details class="ev"><summary><span class="evname fq${x.quality||0}">${esc(x.name)}</span>`+
   `<span class="badge">品质 ${x.quality||0} · ${esc(x.type||'物品')}</span>`+
   `<span class="badge ${x.owned?'ok':'off'}">${x.owned?'已拥有 '+x.owned:'未拥有'}</span>`+
   `<span class="badge score">参考价值 ${x.score||0}</span>`+
   srcBadge+
   `<span class="evloc">${sources.length} 个结局产出</span></summary>`+
   `<div class="evbody">${x.desc?`<div class="itemdesc"><b>物品描述：</b>${esc(x.desc)}</div>`:''}`+
   `${reasons?`<div class="reasons">${reasons}</div>`:''}${uses}${rowsHtml}</div></details>`;
 }
 function rowHay(r){
  return [r.name,r.desc,locText(r),(r.choices||[]).map(c=>c.text).join(' '),
   r.endings.map(e=>[e.title,e.summary,(e.path||[]).join(' ')].join(' ')).join(' '),
   r.endings.map(e=>e.rewards.map(x=>x.name).join(' ')).join(' ')].join(' ');
 }
 function matchedRows(){
  const q=state.q.trim();
  return topRows.filter(r=>{
   const members=groupMembers(r);
   if(state.status==='done'&&!r.achieved)return false;
   if(state.status==='todo'&&r.achieved)return false;
   if(state.realm==='__current__'){if(Number(r.realm||0)!==Number(st.current_realm||0))return false}
   else if(state.realm!==''&&String(r.realm||0)!==state.realm)return false;
   if(state.missing&&!members.some(m=>m.endings.some(e=>e.rewards.some(x=>!x.owned))))return false;
   if(state.condOnly&&!members.some(m=>condSummary(m).some(c=>c.gate&&c.ok===false)))return false;
   if(!q)return true;
   return members.some(m=>rowHay(m).includes(q));
  });
 }
 function matchedItems(){
  const q=state.q.trim();
  const list=catalog.filter(x=>{
   if(state.missing&&x.owned)return false;
   if(state.itemQuality!==''&&String(x.quality||0)!==state.itemQuality)return false;
   if(state.itemType&&(x.type||'未分类')!==state.itemType)return false;
   if(state.itemUse&&!(x.use||[]).length)return false;
   if(!q)return true;
   return x.name.includes(q)||(x.desc||'').includes(q)||(x.use||[]).some(u=>u.includes(q))||
    (x.sources||[]).some(s=>s.event_name.includes(q)||s.ending_title.includes(q));
  });
  if(state.itemSort==='quality')list.sort((a,b)=>(b.quality||0)-(a.quality||0)||(b.score||0)-(a.score||0));
  else if(state.itemSort==='name')list.sort((a,b)=>a.name.localeCompare(b.name,'zh'));
  else list.sort((a,b)=>(b.score||0)-(a.score||0));
  return list;
 }
 const qualityList=[...new Set(catalog.map(x=>x.quality||0))].sort((a,b)=>a-b);
 const typeList=[...new Set(catalog.map(x=>x.type||'未分类'))].sort((a,b)=>a.localeCompare(b,'zh'));
 function renderItemChips(){
  $('evitemq').innerHTML='<span class="chip-label">品质</span><button class="chip'+(state.itemQuality===''?' on':'')+'" data-itemq="">全部</button>'+
   qualityList.map(q=>`<button class="chip${String(state.itemQuality)===String(q)?' on':''}" data-itemq="${q}">品质 ${q}</button>`).join('');
  const sel=$('evitemtype');
  if(sel)sel.innerHTML='<option value="">全部类别</option>'+typeList.map(t=>`<option value="${esc(t)}"${state.itemType===t?' selected':''}>${esc(t)}</option>`).join('');
  document.querySelectorAll('#evitemuse [data-isort]').forEach(b=>b.classList.toggle('on',b.dataset.isort===state.itemSort));
  $('evuseonly').classList.toggle('on',!!state.itemUse);
  $('evunowned').classList.toggle('on',!!state.missing);
 }
 function refreshChips(){
  document.querySelectorAll('#evmode .chip').forEach(b=>b.classList.toggle('on',b.dataset.mode===state.mode));
  document.querySelectorAll('#evstatus .chip').forEach(b=>b.classList.toggle('on',b.dataset.status===state.status));
  document.querySelectorAll('#evrealm .chip').forEach(b=>b.classList.toggle('on',b.dataset.realm===state.realm));
  $('evmiss').classList.toggle('on',!!state.missing);
  $('evcond').classList.toggle('on',!!state.condOnly);
  const itemMode=state.mode==='item';
  $('evstatus').style.display=itemMode?'none':'';
  $('evrealm').style.display=itemMode?'none':'';
  $('evcond').style.display=itemMode?'none':'';
  $('evmiss').style.display=itemMode?'none':'';
  $('evitemq').style.display=itemMode?'':'none';
  $('evitemuse').style.display=itemMode?'':'none';
  renderItemChips();
 }
 function renderAll(){
  refreshChips();
  $('evq').value=state.q;
  if(state.mode==='item'){
   const list=matchedItems();
   const sortName={'score':'参考价值','quality':'品质','name':'名称'}[state.itemSort]||'参考价值';
   $('evcount').textContent=`筛选结果：${list.length} / ${catalog.length} 种奖励物品 · 按${sortName}排序 · 未拥有 ${catalog.filter(x=>!x.owned).length} 种 · “NPC 求购”＝NPC 会收购或任务需要`;
   $('evlist').innerHTML=list.map(itemCard).join('')||'<div class="empty">没有符合条件的奖励物品，试试放宽品质或用途筛选。</div>';
   return;
  }
  const list=matchedRows();
  const folded=rows.length-topRows.length;
  $('evcount').textContent=`筛选结果：${list.length} / ${topRows.length} 个奇遇`+(folded?` · ${folded} 条分支已归到母奇遇下`:'');
  const groups={};list.forEach(r=>{const key=r.realm_name||'未知境界';(groups[key]=groups[key]||[]).push(r)});
  const empty=state.condOnly?'<div class="empty">当前没有“属性门槛不足”的奇遇；点「挑奖励」可以查看全部奖励与路线。</div>':'<div class="empty">没有符合条件的奇遇</div>';
  $('evlist').innerHTML=Object.keys(groups).map(key=>
   `<div class="evgroup">${esc(key)}<span>${groups[key].length} 个</span></div>`+groups[key].map(r=>eventCard(r)).join('')
  ).join('')||empty;
  if(state.focus){
   const card=document.querySelector(`#evlist [data-event="${state.focus}"]`);
   state.focus=0;
   if(card){for(let p=card.parentElement;p;p=p.parentElement){if(p.tagName==='DETAILS')p.open=true}
    card.classList.add('flash');card.scrollIntoView({block:'center',behavior:'smooth'});setTimeout(()=>card.classList.remove('flash'),1700)}
  }
 }
 const realmNames=[...new Set(topRows.map(r=>r.realm_name||'未知境界'))];
 const realmList=[...new Set(topRows.map(r=>String(r.realm||0)))];
 host.innerHTML=sourceHtml(m)+`<div class="notice"><b>境界提示：</b>奇遇绑定所在地点，配置里没有“境界高就关闭低阶奇遇”的硬限制；突破后低境界奇遇仍需回到对应地点才会遇到。当前境界的奇遇建议先清。</div>`+`<div class="notice"><b>分支归并：</b>同一母奇遇下的子奇遇折叠在母奇遇里；任一分支被选择或达成，整条奇遇即视为完成，其余未选分支不再计入未达成。无法确定父子关系的奇遇仍单独展示。</div>`+`<div class="cards">${cards}</div>`+
  `<div class="legend"><span>奖励颜色：</span><span><i style="background:#b4bdca"></i>品质0</span><span><i style="background:#a8dfb4"></i>品质1</span><span><i style="background:#a6cff0"></i>品质2</span><span><i style="background:#cbb2ee"></i>品质3</span><span><i style="background:#f0d38a"></i>品质4</span><span><i style="background:#f0a6a6"></i>品质5</span><span>越靠右越稀有</span></div>`+
  `<div class="legend"><span>结局品级：</span><span><i style="background:#8ee6b3"></i>上品</span><span><i style="background:#b9d9ff"></i>中品</span><span><i style="background:#e88b82"></i>下品</span><span>只代表结局平均奖励高低，具体看掉落</span></div>`+
  `<div class="chips event-chips" id="evgoals"><span class="chip-label">我想…</span>`+
   `<button class="chip" data-goal="check">出发前检查</button>`+
   `<button class="chip" data-goal="reward">挑奖励</button>`+
   `<button class="chip" data-goal="item">奖励图鉴</button>`+
   `<button class="chip" data-goal="collect">看收集</button><button class="chip" id="evreset">重置筛选</button></div>`+
  `<div class="search-panel"><div class="search-fields" style="grid-template-columns:1fr"><label class="search-field"><span>找奇遇 / 结局 / 奖励物品</span><input id="evq" placeholder="输入奇遇名、结局名或奖励物品名称"></label></div></div>`+
  `<div class="chips event-chips" id="evmode"><span class="chip-label">视角</span><button class="chip" data-mode="event">按奇遇</button><button class="chip" data-mode="item">按物品反查</button></div>`+
  `<div class="chips event-chips" id="evstatus"><span class="chip-label">状态</span><button class="chip" data-status="">全部</button><button class="chip" data-status="todo">未达成</button><button class="chip" data-status="done">已达成</button></div>`+
  `<div class="chips event-chips" id="evrealm"><span class="chip-label">境界</span><button class="chip" data-realm="">全部</button>`+
   (st.current_realm?`<button class="chip" data-realm="__current__">当前境界${st.current_realm_name?' · '+esc(st.current_realm_name):''}</button>`:'')+
   realmList.map((value,i)=>`<button class="chip" data-realm="${esc(value)}">${esc(realmNames[i]||('境界 '+value))}</button>`).join('')+`</div>`+
  `<div class="chips event-chips"><button class="chip" id="evcond">只看属性门槛不足</button><button class="chip" id="evmiss">只看有未拥有奖励</button></div>`+
  `<div class="chips event-chips" id="evitemq" style="display:none"></div>`+
  `<div class="chips event-chips" id="evitemuse" style="display:none"><button class="chip" id="evuseonly">只看有用途</button><button class="chip" id="evunowned">只看未拥有</button><select id="evitemtype" class="itemselect"></select><span class="chip-label">排序</span><button class="chip" data-isort="score">参考价值</button><button class="chip" data-isort="quality">品质</button><button class="chip" data-isort="name">名称</button></div>`+
  `<div id="evcount" class="result-info"></div><div id="evlist"></div>`+
  `<div class="tip">选择记录里的“累计选 N 次”是存档里的点击次数，不是奖励倍数。`+
  `「NPC 求购」表示该物品可被 NPC 收购或用于 NPC 需求任务；「炼丹药材 / 炼器材料」表示可作对应配方材料。`+
  ` 当前角色属性：${Object.values(attrs).map(a=>`${esc(a.name)} Lv${a.level}（${a.exp}/${a.next||'—'}）`).join(' · ')||'未读取到探索属性'}；灵石 ${money}。`+
  ` 结局的「达成路径」来自配置里的设计备注，共 ${metaStats.endings_with_path||0}/${stats.endings||0} 条；静态能连到结局的分支共 ${metaStats.tree_endings||0} 条，其余由游戏结算判定。`+
  ` 奇遇按地点境界分组；配置里没有“角色境界高于某值就关闭奇遇”的硬条件，能否再遇到主要取决于还能不能回到该地点。`+
  ` 历史达成按角色保存在本地，不写入游戏存档。</div>`;
 $('evq').value=state.q;
 $('evq').oninput=e=>{state.q=e.target.value;state.focus=0;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evmode').onclick=e=>{const b=e.target.closest('[data-mode]');if(!b)return;state.mode=b.dataset.mode;state.focus=0;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evstatus').onclick=e=>{const b=e.target.closest('[data-status]');if(!b)return;state.status=b.dataset.status;state.focus=0;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evrealm').onclick=e=>{const b=e.target.closest('[data-realm]');if(!b)return;state.realm=b.dataset.realm;state.focus=0;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evcond').onclick=()=>{state.condOnly=!state.condOnly;state.focus=0;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evmiss').onclick=()=>{state.missing=!state.missing;state.focus=0;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evitemq').onclick=e=>{const b=e.target.closest('[data-itemq]');if(!b)return;state.itemQuality=b.dataset.itemq;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evitemtype').onchange=e=>{state.itemType=e.target.value;store.set(EVENT_FILTER_KEY,state);renderAll()};
 $('evitemuse').onclick=e=>{
  const sort=e.target.closest('[data-isort]');
  if(sort){state.itemSort=sort.dataset.isort;store.set(EVENT_FILTER_KEY,state);renderAll();return}
  if(e.target.closest('#evuseonly')){state.itemUse=!state.itemUse;store.set(EVENT_FILTER_KEY,state);renderAll()}
  if(e.target.closest('#evunowned')){state.missing=!state.missing;store.set(EVENT_FILTER_KEY,state);renderAll()}
 };
 $('evlist').onclick=e=>{
  const b=e.target.closest('[data-jump]');if(!b)return;
  const r=byId[Number(b.dataset.jump)];if(!r)return;
  state.mode='event';state.q=r.name;state.status='';state.realm='';
  state.condOnly=false;state.missing=false;state.focus=r.id;
  store.set(EVENT_FILTER_KEY,state);renderAll();
 };
 $('evgoals').onclick=e=>{
  const b=e.target.closest('[data-goal]');if(!b)return;
  const goal=b.dataset.goal;state.focus=0;state.q='';
  if(goal==='check'){state.mode='event';state.status='todo';state.condOnly=true;state.missing=false;state.realm=''}
  else if(goal==='reward'){state.mode='event';state.status='todo';state.condOnly=false;state.missing=false;if(st.current_realm)state.realm='__current__'}
  else if(goal==='item'){state.mode='item';state.missing=false;state.condOnly=false;state.itemQuality='';state.itemType='';state.itemUse=false;state.itemSort='score'}
  else{state.mode='event';state.status='done';state.condOnly=false;state.missing=false;state.realm=''}
  store.set(EVENT_FILTER_KEY,state);renderAll();
 };
 $('evreset').onclick=()=>{
  state={q:'',status:'',realm:'',mode:'event',missing:false,condOnly:false,itemQuality:'',itemType:'',itemUse:false,itemSort:'score',focus:0};
  store.set(EVENT_FILTER_KEY,state);renderAll();
 };
 renderAll();
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['event']=initEvent;
})();
