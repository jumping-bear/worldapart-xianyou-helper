/* 支线：剧情线任务脊柱。默认按玩家进度排序，节点内联展开，不弹窗、不另开面板。 */
(function(){
const KEY='worldapart.quest.story.v4';
const STATUS={done:'已完成',doing:'进行中',ready:'可接取',opened:'已开启',cond:'条件不足',wait:'未触发（需满足条件）',unpicked:'未选分支',legacy:'已废弃'};
const FILTERS=[['all','全部'],['ready','可接取'],['opened','已开启'],['doing','进行中'],
  ['wait','未触发'],['cond','条件不足'],['unverified','旧版任务'],['unpicked','未选分支'],['done','已完成']];
// 章节顺序与配色来自配置表（境界表），新增境界不用改代码
const CHAP_TONE=(()=>{ try{ return DATA.modules.quest.rows.chapter_tones||{}; }catch(e){ return {}; } })();
const CHAP_ORDER=(()=>{ try{ return DATA.modules.quest.rows.chapter_order||{}; }catch(e){ return {}; } })();
const chapCls=c=>'c'+((CHAP_TONE&&CHAP_TONE[c]!==undefined)?CHAP_TONE[c]:0);

function initQuest(){
 const m=DATA.modules&&DATA.modules.quest;if(!m)return;
 const host=$('quest'),st=m.rows||{},rows=st.rows||[],stats=st.stats||{},lines=st.storylines||[];
 if(!rows.length){host.innerHTML=sourceHtml(m)+'<div class="empty">暂无支线配置</div>';return}
 const byId={};rows.forEach(r=>byId[r.id]=r);
 // 任务名 → id：让条件里的「任务名」可以点进去看它是什么、在哪
 const questIndex=st.quest_index||{};
 const nameToId={};
 rows.forEach(r=>{if(r.name&&nameToId[r.name]===undefined)nameToId[r.name]=r.id});
 Object.keys(questIndex).forEach(id=>{const nm=(questIndex[id]||{}).name;if(nm&&nameToId[nm]===undefined)nameToId[nm]=+id});
 // 同名任务：游戏里可能有两处同名（如「小蝶所托」），必须按章节区分，不能凭名字乱跳。
 const dupNames=st.dup_names||{};
 const dupNameOf={};
 Object.keys(dupNames).forEach(nm=>(dupNames[nm]||[]).forEach(e=>{dupNameOf[e.id]=nm}));
 const lineMetaOf={};
 lines.forEach(l=>(l.quests||[]).forEach(id=>{lineMetaOf[id]={line:l.name||'',chapter:l.chapter||'',region:l.region||''}}));
 const chapOf=id=>(lineMetaOf[id]||{}).chapter||'';
 const linkify=text=>esc(text||'').replace(/「([^」]{1,40})」(?:（([^）]{1,12})）)?/g,(m0,nm,chap)=>{
   const cands=dupNames[nm];
   let id=nameToId[nm];
   if(cands){
     if(chap){const hit=cands.filter(e=>e.chapter===chap)[0];if(hit)id=hit.id;}
     // 同名又没给章节：宁可不跳，也不能跳到另一个同名任务上去。
     else return m0;
   }
   if(id===undefined)return m0;
   const sfx=(cands&&chap)?`<span class="sq-chap-sfx">（${esc(chap)}）</span>`:'';
   const tail=(chap&&!cands)?`（${esc(chap)}）`:'';
   return '「<a class="sq-ref" data-jump="'+id+'">'+esc(nm)+sfx+'</a>」'+tail;
 });

 let state=Object.assign({q:'',status:'all',view:'story',open:{}},store.get(KEY,{}));
 if(!state.open||typeof state.open!=='object')state.open={};

 const sk=r=>r.status_key||'wait';
 const statusText=r=>STATUS[sk(r)]||r.status_label||'';
 const locText=r=>{const l=r.location;if(!l)return r.place_text||r.spot||(r.hidden?'剧情中触发':'位置未定');
   const path=(l.path&&l.path.length)?l.path.join(' / '):l.name;return (r.spot?r.spot+' · ':'')+path};
 const rewardTip=x=>[(x.sources||[]).join('/'),x.type?('类型：'+x.type):'',x.price?('参考价 '+x.price):''].filter(Boolean).join(' · ');
 const rewardChips=(r,limit)=>{
   const list=(r.rewards||[]).filter(x=>x.name!=='灵石');
   const stone=r.reward_stone||0,cap=limit||3;
   let out=list.slice(0,cap).map(x=>`<span class="sq-rw ${qClass(x.quality,'f')}" title="${esc(rewardTip(x))}">${esc(x.name)}×${x.min===x.max?x.min:x.min+'-'+x.max}</span>`);
   if(list.length>cap)out.push(`<span class="sq-rw more">+${list.length-cap}</span>`);
   if(stone)out.push(`<span class="sq-stone">灵石 ${stone}</span>`);
   return out.join('');
 };
 const isStone=x=>x&&x.name==='灵石';
 // 未完成任务里的高品质奖励：支线首页优先展示这些，而不是“还能拿多少灵石”。
 const hiReward=x=>!isStone(x)&&(Number(x.quality)||0)>=HI_QUALITY_STRICT;
 const hiOfQuest=r=>r&&!r.done&&sk(r)!=='unpicked'?(r.rewards||[]).filter(hiReward):[];
 const hiOfLine=line=>{
   const seen={},out=[];
   (line.quests||[]).forEach(id=>hiOfQuest(byId[id]).forEach(x=>{
     if(seen[x.name])return;seen[x.name]=1;out.push(x);
   }));
   return out.sort((a,b)=>(b.quality||0)-(a.quality||0)||String(a.name).localeCompare(String(b.name),'zh-CN'));
 };
 const hiChip=(x,extra)=>`<span class="sq-hi ${qClass(x.quality,'f')}" title="${esc(rewardTip(x))}">${esc(x.name)}${extra||''}</span>`;
 const hay=(r)=>[r.name,r.desc,r.group,(r.giver||{}).name,locText(r),
   (r.objectives||[]).map(o=>o.text).join(' '),
   (r.rewards||[]).map(x=>x.name).join(' '),
   (r.option_gates||[]).map(g=>(g.option||'')+' '+(g.text||'')).join(' ')].join(' ').toLowerCase();
 const query=()=>(state.q||'').trim().toLowerCase();
 const match=r=>!query()||hay(r).includes(query());
 const passStatus=r=>state.status==='all'
   ||(state.status==='unverified'?!!(r.entry_unverified||r.legacy):sk(r)===state.status);

 function checkRow(c){
   const ok=c.ok===true,bad=c.ok===false;
   return `<div class="sq-chk ${ok?'ok':bad?'bad':''}"><span class="sq-mark">${ok?'✓':bad?'✗':'?'}</span>`+
     `<span class="sq-ctext">${linkify(c.text||'条件')}</span><span class="sq-cval">${esc(c.cur_text||'')}</span></div>`;
 }
 function sceneHtml(g){
   const c=g.context||{},sibs=c.siblings||[],lns=(c.lines||[]).slice(0,4);
   if(!sibs.length&&!lns.length)return '';
   return `<details class="sq-say"><summary>当时的对话${c.npc_name?' · '+esc(c.npc_name):''}</summary><div class="sq-say-body">`+
     lns.map(l=>`<div class="sq-dline"><span>${esc(l.sub)}</span>${esc(l.text)}</div>`).join('')+
     (sibs.length?`<div class="sq-sibs">${sibs.map(s=>`<span class="${esc(s)===g.option?'cur':''}">${esc(s)}</span>`).join('')}</div>`:'')+
     `</div></details>`;
 }
 function gatesHtml(r){
   const gates=r.gate_eval||[];if(!gates.length)return '';
   return `<div class="sq-sec">选项与门槛</div>`+gates.map(g=>{
     const ev=g.eval||{},ok=ev.ok===true,bad=ev.ok===false;
     return `<div class="sq-opt ${ok?'ok':bad?'bad':''}">`+
       `<div class="sq-opt-h"><span class="sq-optn">选项「${esc(g.option||'—')}」</span>`+
       `<span class="sq-dotsep">·</span><span class="sq-need">需 ${esc(g.text||'无额外条件')}</span>`+
       (g.hint_missing?'<span class="sq-tag risk">容易选错</span>':'')+
       `<span class="sq-cur ${ok?'ok':bad?'bad':''}">${ev.cur_text?('· 你当前 '+esc(ev.cur_text)):''}${ok?' ✓':bad?' ✗':''}</span></div>`+
       (g.hint_missing?'<div class="sq-note">游戏内不会提示这个条件，选之前先看清门槛。</div>':'')+
       (g.hint?`<div class="sq-note">游戏内选项提示：${esc(g.hint)}</div>`:'')+
       sceneHtml(g)+`</div>`;
   }).join('');
 }
 function eggHtml(note){
   if(!note)return '';
   const desc=note.item_desc?String(note.item_desc).split('\n')[0]:'';
   return `<details class="sq-egg"><summary>隐藏结局 · 剧透（点开才看）</summary><div class="sq-egg-body">`+
     (note.trigger?`<p><b>怎么触发</b>${esc(note.trigger)}</p>`:'')+
     (note.complete?`<p><b>怎么做</b>${esc(note.complete)}</p>`:'')+
     (note.item_name?`<p><b>关键道具</b>${esc(note.item_name)}${desc?'：'+esc(desc):''}</p>`:'')+
     (note.egg?`<p class="bad"><b>隐藏结局</b>${esc(note.egg)}</p>`:'')+`</div></details>`;
 }
 function howHtml(r){
   const h=r.how||{},pre=r.prereq||[];
   if(!h.text&&!pre.length)return '';
   const where=[];
   if(h.giver)where.push(`委托人「${esc(h.giver)}」${h.giver_home?' · 常驻地 '+esc(h.giver_home):''}`);
   if(h.place)where.push(`地点 ${esc(h.place)}`);
   return `<div class="sq-sec">怎么触发</div><div class="sq-how">`+
     `<span class="sq-howtag ${h.auto?'auto':'npc'}">${esc(h.text||'条件满足时出现')}</span>`+
     (where.length?`<span class="sq-howmeta">${where.join(' ｜ ')}</span>`:'')+
     `</div>`+
     (pre.length?`<div class="sq-prereq"><b>要做的前置${r.prereq_any&&pre.length>1?'（满足其一即可）':''}</b><div class="sq-pres">`+pre.map(p=>{
       const chap=p.chapter||chapOf(p.id);
       const dup=!!dupNameOf[p.id];
       const showLine=!!p.line&&(p.line!==p.name||dup);
       return p.side
         ? `<button class="sq-pre" data-jump="${p.id}" title="点这里跳到「${esc(p.name)}」${chap?'（'+esc(chap)+'）':''}${dup?' · 与当前任务同名，不是同一个任务':''}">
              ${chap?`<span class="sq-chap ${chapCls(chap)}">${esc(chap)}</span>`:''}
              <span>${esc(p.name)}</span><em>${esc(p.status_label||'未完成')}</em>${showLine?`<i>${esc(p.line)}</i>`:''}</button>`
         : `<span class="sq-pre out" title="该任务不在支线页">
              <span>${esc(p.name)}</span><em>${esc(p.type_name||'其他任务')} · 不在支线页</em></span>`
     }).join('')+`</div></div>`:'');
 }
 // 同名任务：不同章节各有一个同名任务时，把“另一个是什么、在哪、什么状态”摆出来，避免认错。
 function sameNameHtml(r){
   const info=r.same_name_info||[];
   if(!info.length)return '';
   const mine=lineMetaOf[r.id]||{},chap=mine.chapter||'';
   const otherDone=info.filter(x=>x.done)[0];
   let lead;
   if(otherDone){
     lead=`游戏里有 ${info.length+1} 个「${esc(r.name)}」：你完成的那个在「${esc((otherDone.chapter||'')+(otherDone.line?' · '+otherDone.line:''))}」，本行这条在「${esc(chap+(mine.line?' · '+mine.line:''))}」——不是同一个任务。`;
   }else{
     lead=`游戏里有 ${info.length+1} 个「${esc(r.name)}」，它们不是同一个任务。本行这条在「${esc(chap+(mine.line?' · '+mine.line:''))}」，另外还有：`;
   }
   return `<div class="sq-sec">同名任务</div><div class="sq-same"><div class="sq-sn-lead">${lead}</div>`+
     info.map(x=>`<button class="sq-sn" data-jump="${x.id}" title="点这里跳到「${esc(x.name)}」">
         <span class="sq-sn-nm">${esc(x.name)}</span>
         ${x.chapter?`<span class="sq-chap ${chapCls(x.chapter)}">${esc(x.chapter)}</span>`:''}
         <span class="sq-sn-line">${esc(x.line||'—')}</span>
         <span class="sq-badge b-${x.status_key||'wait'}">${esc(x.status_label||'')}</span></button>`).join('')+
     `</div>`;
 }
 function bodyHtml(r){
   const ce=r.cond_eval||{},checks=ce.checks||[],gaps=ce.gaps||[];
   const logic=ce.logic==='满足其一'?'满足其一即可':ce.logic==='全部满足'?'需要全部满足':(ce.logic?'部分条件满足其一即可':'');
   const cond=checks.length
     ? `<div class="sq-checks">${logic?`<div class="sq-logic">${esc(logic)}</div>`:''}${checks.map(checkRow).join('')}</div>`+
       (gaps.length?`<div class="sq-gap"><b>还差</b>${gaps.map(g=>`<span>${esc(g)}</span>`).join('')}</div>`:'')
     : `<div class="sq-muted">${esc(r.open_text||r.cond_text||r.trigger_text||r.trigger_line||((r.prereq||[]).length?'完成上面的前置后自动出现':'剧情到这里自动出现，不需要额外条件'))}</div>`;
   const rewards=(r.rewards||[]).length
     ? `<div class="sq-rwlist">${r.rewards.map(x=>`<span class="sq-rw ${qClass(x.quality,'f')}" title="${esc(rewardTip(x))}">${esc(x.name)}×${x.min===x.max?x.min:x.min+'-'+x.max}<i>${esc((x.sources||[]).join('/'))}</i></span>`).join('')}</div>`
     : `<div class="sq-muted">剧情向，无固定奖励</div>`;
   return howHtml(r)+sameNameHtml(r)+`<div class="sq-sec">触发条件</div>${cond}`+
     (r.desc?`<div class="sq-sec">这一段剧情</div><div class="sq-desc">${linkify(r.desc)}</div>`:'')+
     gatesHtml(r)+
     ((r.objectives||[]).length?`<div class="sq-sec">要做的事</div><ul class="sq-objs">${r.objectives.map(o=>`<li>${esc(o.text)}${o.npc?'<em>'+esc(o.npc)+'</em>':''}</li>`).join('')}</ul>`:'')+
     `<div class="sq-sec">奖励</div>${rewards}`+
     (r.egg_note?eggHtml(r.egg_note):'')+
     (r.egg_note?'':(r.status_hint?`<div class="sq-hint"><b>怎么走</b>${esc(r.status_hint)}</div>`:''))+
     (r.unreachable?`<div class="sq-warn">${esc(r.unreachable_text)}</div>`:'');
 }
 function nodeHtml(r,index){
   const key=sk(r),one=r.hidden?(r.trigger_text||r.trigger_line||r.cond_text||r.status_hint):(r.trigger_line||r.status_hint||r.trigger_text||r.cond_text);
   const peers=r.branch_key?rows.filter(x=>x.id!==r.id&&x.branch_key===r.branch_key):[];
   const peerPicked=peers.some(x=>x.done||x.doing);
   const branchTag=r.branch_key&&(r.branch_with||[]).length
     ? ((r.done||r.doing)?'<span class="sq-tag sel">已选</span>':(peerPicked?'<span class="sq-tag unsel">未选</span>':''))
     : '';
   const hit=match(r)&&!!query();
   const open=hit?' open':'';
   return `<details class="sq-node k-${key}${r.hidden?' hidden':''}${hit?' hit':''}" data-q="${r.id}"${open}>`+
     `<summary><span class="sq-step">${index}</span><span class="sq-nm">${esc(r.name)}</span>`+
     (dupNameOf[r.id]?'<span class="sq-tag dup" title="游戏里有多个同名任务，注意区分">同名</span>':'')+
     (r.legacy?'<span class="sq-tag legacy" title="配置里只剩这条任务和接取选项，但既没有触发表达式也没有接取条件，且同名新版本已替代它；游戏里没有入口，后续环节也走不到">旧版任务 · 已废弃</span>':(r.entry_unverified?'<span class="sq-tag legacy" title="配置里仍有任务和接取选项，但当前版本没找到实际入口，可能是旧版遗留；游戏里确认看不到后可当作已错过">旧版入口 · 待确认</span>':''))+
     `<span class="sq-badge b-${key}">${esc(statusText(r))}</span>`+
     (r.hidden?'<span class="sq-tag hid">不显示在任务面板</span>':'')+
     (r.retry_of?'<span class="sq-tag retry" title="失败后的重试记录，跟随宿主任务展示，不单独成线">重试</span>':'')+
     ((r.retry_ids||[]).length?'<span class="sq-tag retry" title="小游戏失败后会生成重试任务，不单独占线">失败可重试</span>':'')+
     (r.egg_note?'<span class="sq-tag egg">含隐藏结局</span>':'')+branchTag+
     `<span class="sq-rwline">${rewardChips(r,2)||'<span class="sq-rw more">剧情向</span>'}</span><span class="sq-loc">${esc(locText(r))}</span>`+
     (!r.done&&r.how?`<span class="sq-mode ${r.how.auto?'auto':'npc'}">${r.how.auto?'自动触发':'找人接取'}</span>`:'')+
     `<span class="sq-one">${linkify(one||'')}</span>${optPreview(r)}</summary>`+
     `<div class="sq-body">${bodyHtml(r)}</div></details>`;
 }
 function optPreview(r){
   // 选项和门槛直接铺在卡片上：玩家在游戏里看到的是「震慑。」，不是任务名。
   const list=(r.gate_eval||[]).filter(g=>g&&g.option);
   if(!list.length)return '';
   return `<span class="sq-opts-inline">`+
     list.slice(0,3).map(g=>{
       const ev=g.eval||{},cls=ev.ok===true?' ok':(ev.ok===false?' no':'');
       const need=g.text&&g.text!=='无额外条件'?`<em>需 ${esc(g.text)}</em>`:'';
       return `<span class="sq-opt-tag${cls}" title="${esc('选项「'+g.option+'」 · 需 '+(g.text||'无额外条件'))}">${esc(g.option)}${need}</span>`;
     }).join('')+
     (list.length>3?`<span class="sq-opt-tag more">等 ${list.length} 个选项</span>`:'')+
     `</span>`;
 }
 // ---- 剧情线结构：按 next 边建图，分叉用并列路线渲染，不再按层号从上往下堆 ----
 function lineGraph(line){
   const ids=(line.quests||[]).filter(id=>byId[id]);
   const set=new Set(ids),children={},parents={};
   ids.forEach(id=>{children[id]=[];parents[id]=[]});
   ids.forEach(id=>{
     (byId[id].next||[]).forEach(x=>{
       if(set.has(x)&&children[id].indexOf(x)<0){children[id].push(x);parents[x].push(id)}
     });
   });
   return {set:set,children:children,parents:parents,roots:ids.filter(id=>!parents[id].length)};
 }
 // 从起点沿唯一后继走到底；遇到分叉停下（分叉交给 forkHtml 渲染）。
 function laneWalk(start,g){
   const out=[],seen=new Set();let cur=start;
   while(cur&&g.set.has(cur)&&!seen.has(cur)){
     seen.add(cur);out.push(byId[cur]);
     const nx=g.children[cur]||[];
     if(nx.length!==1)break;
     cur=nx[0];
   }
   return out;
 }
 const laneRank=nodes=>{
   if(nodes.some(r=>r.done||r.doing))return 0;
   if(nodes.some(r=>{const k=sk(r);return k==='ready'||k==='opened'}))return 1;
   if(nodes.some(r=>sk(r)==='cond'))return 2;
   if(nodes.length&&nodes.every(r=>r.done))return 4;
   return 3;
 };
 const depthOf=(line,r)=>Number((line.depths||{})[String(r.id)]||r.chain_index||1);
 function ringHtml(line,r){
   if(!passStatus(r)||!match(r))return '';
   const d=depthOf(line,r);
   return `<div class="sq-ring"><div class="sq-rail"><span class="sq-dot">${d}</span><i class="sq-bar"></i></div>`+
     `<div class="sq-nodes">${nodeHtml(r,d)}</div></div>`;
 }
 function laneTag(nodes,peerNodes,exclusive){
   if(nodes.some(r=>r.done||r.doing))return '<span class="sq-tag sel">已选</span>';
   if(exclusive&&peerNodes.some(r=>r.done||r.doing))return '<span class="sq-tag unsel">未选</span>';
   const keys=nodes.map(sk);
   if(keys.some(k=>k==='ready'||k==='opened'))return '<span class="sq-tag">可接取</span>';
   if(keys.length&&keys.every(k=>k==='done'))return '<span class="sq-tag">已完成</span>';
   return '';
 }
 function forkMeta(ids){
   const keys=ids.map(id=>(byId[id]||{}).branch_key||'');
   const exclusive=keys.every(k=>k===keys[0]);
   return {exclusive:exclusive,
     label:(ids.length>2?'多选一':'二选一')+(exclusive?' · 只能走一条':' · 可以都做')};
 }
 function laneHtml(line,start,g,ctx,seen){
   const walked=laneWalk(start,g);
   const fresh=walked.filter(r=>!seen.has(r.id));
   if(!fresh.length)return '';
   const last=fresh[fresh.length-1];
   const nx=g.children[last.id]||[];
   const visible=fresh.filter(r=>passStatus(r)&&match(r));
   if(!visible.length&&nx.length<2)return '';
   fresh.forEach(r=>seen.add(r.id));
   const tag=laneTag(walked,ctx.peerNodes||[],ctx.exclusive);
   let inner=visible.map(r=>ringHtml(line,r)).join('');
   if(nx.length>1)inner+=forkHtml(line,nx,g,ctx,seen,true);
   return `<div class="sq-lane${tag.indexOf('sq-tag sel')>=0?' sel':''}">`+
     `<div class="sq-lane-h"><b>${esc((walked[0]||{}).name||'路线')}</b>`+
     `<span class="sq-lane-step">${walked.length} 步</span>${tag}</div>${inner}</div>`;
 }
 function forkHtml(line,ids,g,ctx,seen,nested){
   const meta=forkMeta(ids);
   const walked=ids.map(id=>laneWalk(id,g));
   const peerNodes=[].concat.apply([],walked);
   // 路线按“已选 → 可接取 → 未开启”排前排，但路线内部的步骤永远保持真实先后。
   const ordered=ids.map((id,i)=>({id:id,nodes:walked[i]}))
     .sort((a,b)=>laneRank(a.nodes)-laneRank(b.nodes));
   const lanes=[];
   ordered.forEach(o=>{
     const html=laneHtml(line,o.id,g,{peerNodes:peerNodes,exclusive:meta.exclusive},seen);
     if(html)lanes.push(html);
   });
   if(!lanes.length)return '';
   return `<div class="sq-fork${nested?' nest':''}"><div class="sq-fork-h">${esc(meta.label)}`+
     `<em>${meta.exclusive?'已选一条后，另一条不再计入未完成':'各条路互不影响'}</em></div>`+
     `<div class="sq-lanes${nested?' nest':''}">${lanes.join('')}</div></div>`;
 }
 function lineNodes(line){return (line.quests||[]).map(id=>byId[id]).filter(Boolean)}
 function lineBody(line){
   const g=lineGraph(line),seen=new Set();
   let out=triggerHtml(line);
   if(g.roots.length>1){
     // 多个独立起点：各自成列，不再混在同一层里按顺序排。
     const peerNodes=[].concat.apply([],g.roots.map(id=>laneWalk(id,g)));
     const lanes=g.roots.slice().sort((a,b)=>laneRank(laneWalk(a,g))-laneRank(laneWalk(b,g)))
       .map(id=>laneHtml(line,id,g,{peerNodes:peerNodes,exclusive:false},seen)).filter(Boolean);
     if(lanes.length){
       out+=`<div class="sq-fork roots"><div class="sq-fork-h">${g.roots.length} 个独立起点`+
         `<em>每条路各自独立，不需要按顺序做</em></div><div class="sq-lanes">${lanes.join('')}</div></div>`;
     }
   }else{
     let cur=g.roots[0],prefix='',fork='';
     while(cur&&g.set.has(cur)&&!seen.has(cur)){
       seen.add(cur);
       prefix+=ringHtml(line,byId[cur]);
       const nx=g.children[cur]||[];
       if(nx.length===1){cur=nx[0];continue}
       if(nx.length>1)fork=forkHtml(line,nx,g,{},seen,false);
       break;
     }
     out+=prefix+fork;
   }
   // 兜底：万一以后配置里出现环或断链，没画到的节点单独收在最后，不能丢。
   const left=(line.quests||[]).map(id=>byId[id]).filter(r=>r&&!seen.has(r.id)&&passStatus(r)&&match(r));
   if(left.length)out+=`<div class="sq-fork"><div class="sq-fork-h">未接上主线<em>配置里的后继关系断了</em></div>`+
     `<div class="sq-lanes nest">${left.map(r=>ringHtml(line,r)).join('')}</div></div>`;
   return out;
 }
 const lineText=line=>`${line.name||''} ${line.chapter||''} ${line.region||''}`.toLowerCase();
 function lineVisible(line){
   const nodes=lineNodes(line);
   if(query()&&!nodes.some(match)&&!lineText(line).includes(query()))return false;
   if(state.status!=='all'&&!nodes.some(passStatus))return false;
   return true;
 }
 function lineRank(line){
   if(line.status_key==='doing')return 0;
   if(line.status_key==='ready'){
     // 入口待确认的线排在真正可接取的线后面，但不能排到未开启之后。
     return lineNodes(line).some(r=>sk(r)==='ready'&&!r.entry_unverified)?1:1.5;
   }
   if(line.status_key==='cond'||line.status_key==='wait')return 2;
   if(line.status_key==='legacy')return 7.5;
   if(line.status_key==='done')return 9;
   const nodes=lineNodes(line);
   if(!line.total)return nodes.every(r=>r.done)?9:8;
   if(nodes.some(r=>!r.done&&r.doing))return 0;
   if(nodes.some(r=>!r.done&&sk(r)==='ready'))return 1;
   if(nodes.some(r=>!r.done&&sk(r)==='cond'))return 2;
   if(nodes.some(r=>!r.done&&sk(r)==='wait'))return 3;
   if(nodes.every(r=>r.done))return 9;
   return 5;
 }
 function triggerHtml(line){
   // 场景交互点和任务节点同构：交互点本身 + 它给出的选项，每个选项接一条支线。
   const t=line.trigger||{};
   if(!t.spot&&!t.place&&!(t.options||[]).length)return '';
   const place=t.place||'';
   const opts=(t.options||[]).map(o=>{
     const q=byId[o.quest]||{};
     return `<button type="button" class="sq-int-opt" data-jump="${o.quest}" title="点这里跳到「${esc(q.name||'后续任务')}」">`+
       `<span class="sq-int-optn">选择「${esc(o.text||'调查')}」</span>`+
       (o.gate&&o.gate!=='无额外条件'?`<em>需 ${esc(o.gate)}</em>`:'')+
       `<span class="sq-int-to">→ ${esc(q.name||'后续任务')}${q.id?' · '+esc(statusText(q)):''}</span></button>`;
   }).join('');
   return `<div class="sq-ring sq-ring-int"><div class="sq-rail"><span class="sq-dot">起</span><i class="sq-bar"></i></div>`+
     `<div class="sq-nodes"><details class="sq-node sq-int" open>`+
       `<summary><span class="sq-step">起</span><span class="sq-nm">${esc(t.spot||'场景交互')}</span>`+
       `<span class="sq-badge b-ready">交互点</span>`+
       (place?`<span class="sq-loc">${esc(place)}</span>`:'')+
       `<span class="sq-one">${esc(t.open?('开启：'+t.open):'')}</span></summary>`+
       `<div class="sq-body"><div class="sq-sec">这里的选项 · 各接一条支线</div>`+
       `<div class="sq-int-opts">${opts||'<span class="sq-note">交互后接取后续任务</span>'}</div></div>`+
     `</details></div></div>`;
 }
 function lineHtml(line){
   const nodes=lineNodes(line),visible=nodes.filter(passStatus);
   if(!nodes.length||(!visible.length&&state.status!=='all'))return '';
   if(query()&&!nodes.some(match)&&!lineText(line).includes(query()))return '';
   const body=lineBody(line);
   if(!body)return '';
   const stored=state.open[line.id];
   const nextRow=line.next?byId[line.next]:null;
   const open=(state.q?true:(stored!==undefined?stored:(line.doing>0||(nextRow&&(nextRow.doing||sk(nextRow)==='ready')))));
   const npcs=(line.npc||[]).filter(n=>n&&line.name.indexOf(n)<0);
   return `<details class="sq-line" data-line="${esc(line.id)}"${open?' open':''}>`+
     `<summary class="sq-line-h"><span class="sq-chap ${chapCls(line.chapter)}">${esc(line.chapter)}</span>`+
     (line.region?`<span class="sq-region">${esc(line.region)}</span>`:'')+
     `<span class="sq-lname">${esc(line.name)}</span>`+
     `<span class="sq-badge b-${esc(line.status_key||'wait')}">${esc(line.status_label||'')}</span>`+
     (npcs.length?`<span class="sq-npc">${esc(npcs.slice(0,3).join('、'))}</span>`:'')+
     `<span class="sq-prog" title="已走环数 / 可走环数（不含未选分支）">${line.total?('已走 '+line.done+'/'+line.total):'已选另一条路'}</span>`+
     (()=>{const hi=hiOfLine(line);return hi.length?`<span class="sq-hiwrap" title="未完成支线里品质 ≥4 的奖励">${hi.slice(0,2).map(x=>hiChip(x)).join('')}${hi.length>2?`<span class="sq-hi-more">+${hi.length-2}</span>`:''}</span>`:''})()+
     `<span class="sq-caret">›</span></summary>`+
     `<div class="sq-spine">${body}</div></details>`;
 }
 function flatCard(r){
   const key=sk(r),cy=r.cond_eval||{},checks=cy.checks||[];
   return `<details class="sq-flat${r.hidden?' hidden':''}" data-q="${r.id}">`+
     `<summary><span class="sq-nm">${esc(r.name)}</span><span class="sq-badge b-${key}">${esc(statusText(r))}</span>`+
     (r.hidden?'<span class="sq-tag hid">不显示在任务面板</span>':'')+
     (r.retry_of?'<span class="sq-tag retry" title="失败后的重试记录，跟随宿主任务展示，不单独成线">重试</span>':'')+
     ((r.retry_ids||[]).length?'<span class="sq-tag retry" title="小游戏失败后会生成重试任务，不单独占线">失败可重试</span>':'')+
     `<span class="sq-rwline">${rewardChips(r,2)}</span><span class="sq-loc">${esc(locText(r))}</span></summary>`+
     `<div class="sq-body">`+
       (checks.length?`<div class="sq-checks">${checks.map(checkRow).join('')}</div>`:'')+
       (!checks.length&&r.open_text?`<div class="sq-muted">开启：${esc(r.open_text)}</div>`:'')+
       (r.status_hint?`<div class="sq-hint"><b>怎么走</b>${esc(r.status_hint)}</div>`:'')+
       (r.desc?`<div class="sq-muted">${esc(r.desc)}</div>`:'')+
       gatesHtml(r)+eggHtml(r.egg_note)+`</div></details>`;
 }
 function flatHtml(){
   const list=rows.filter(r=>passStatus(r)&&match(r));
   if(!list.length)return '';
   const lineOf={};lines.forEach(line=>(line.quests||[]).forEach(id=>{lineOf[id]=line.name}));
   rows.forEach(r=>{if(r.retry_of&&lineOf[r.retry_of])lineOf[r.id]=lineOf[r.retry_of]});
   const groups={};
   list.forEach(r=>{const name=lineOf[r.id]||r.chain_name||'其他支线';(groups[name]=groups[name]||[]).push(r)});
   return Object.keys(groups).sort((a,b)=>a.localeCompare(b,'zh-CN')).map(name=>{
     const items=groups[name].sort((a,b)=>(a.chain_index||0)-(b.chain_index||0)||a.id-b.id);
     return `<div class="sq-flat-g">${esc(name)}<span>${items.length} 个</span></div>`+items.map(flatCard).join('');
   }).join('');
 }
 function renderChips(){
   document.querySelectorAll('#qview .chip').forEach(b=>b.classList.toggle('on',b.dataset.view===state.view));
   document.querySelectorAll('#qstatus .chip').forEach(b=>b.classList.toggle('on',b.dataset.st===state.status));
 }
 function render(){
   renderChips();
   const q=$('qs');if(q.value!==state.q)q.value=state.q;
   const list=$('qlist');
   if(state.view==='flat'){
     const count=rows.filter(r=>passStatus(r)&&match(r)).length;
     $('qcount').textContent=`逐个看：${count} / ${rows.length} 个支线 · 共 ${stats.storylines||lines.length} 条剧情线`;
     list.innerHTML=flatHtml()||'<div class="empty">没有符合条件的支线，换个筛选试试。</div>';
     return;
   }
   const visible=lines.filter(lineVisible).sort((a,b)=>lineRank(a)-lineRank(b)
     ||b.size-a.size
     ||(CHAP_ORDER[a.chapter]||99)-(CHAP_ORDER[b.chapter]||99)
     ||(b.done/Math.max(1,b.total))-(a.done/Math.max(1,a.total))
     ||a.name.localeCompare(b.name,'zh-CN'));
   const questCount=visible.reduce((sum,line)=>sum+lineNodes(line).filter(r=>passStatus(r)&&match(r)).length,0);
   $('qcount').textContent=`剧情线：${visible.length} 条 / ${questCount} 个支线 · 共 ${stats.storylines||lines.length} 条`;
   list.innerHTML=visible.map(lineHtml).join('')||'<div class="empty">没有符合条件的剧情线，换个筛选试试。</div>';
   if(query()&&query().length>=2){
     const hit=list.querySelector('.sq-node.hit');
     if(hit&&hit.scrollIntoView)hit.scrollIntoView({block:'center'});
   }
 }
 const hiPending=(()=>{const seen={};rows.forEach(r=>hiOfQuest(r).forEach(x=>{seen[x.name]=x}));
   return Object.keys(seen).map(k=>seen[k]).sort((a,b)=>(b.quality||0)-(a.quality||0));})();
 const cards=`<div class="cards">`+
   `<div class="card"><div class="k">支线完成</div><div class="v">${stats.done||0} <span>/ ${stats.total||0}</span></div><div class="s">进行中 ${stats.doing||0}</div></div>`+
   `<div class="card"><div class="k">剧情线</div><div class="v">${stats.storylines||lines.length} <span>条</span></div><div class="s">按委托人 / 章节归拢</div></div>`+
   `<div class="card"><div class="k">未拿高品质</div><div class="v">${hiPending.length} <span>种</span></div><div class="s">${hiPending.length?('最值：'+esc(hiPending[0].name)):'暂无品质 ≥4 的奖励'}</div></div>`+
   `<div class="card"><div class="k">隐藏任务</div><div class="v">${stats.hidden||0} <span>个</span></div><div class="s">不会显示在游戏任务面板</div></div>`+
   `</div>`;
 const legend=`<div class="legend"><span>物品品质：</span>${QUALITY_NAMES.map((n,i)=>`<span><i style="background:var(--q${i})"></i>${n}</span>`).join('')}</div>`;
 const chipCount=v=>v==='all'?rows.length
   :(v==='unverified'?rows.filter(r=>(r.entry_unverified||r.legacy)&&!r.done).length
     :v==='ready'?rows.filter(r=>sk(r)==='ready'&&!r.entry_unverified).length
     :rows.filter(r=>sk(r)===v).length);
 host.innerHTML=sourceHtml(m)+cards+
   `<div class="search-panel"><div class="search-fields" style="grid-template-columns:1fr"><label class="search-field"><span>找任务 / 剧情线 / 委托人 / 地点 / 奖励</span><input id="qs" placeholder="输入任务名、剧情线、委托人、地点或奖励"></label></div></div>`+
   `<div class="chips" id="qview"><span class="chip-label">视图</span>`+
   `<button class="chip" data-view="story">剧情线</button><button class="chip" data-view="flat">逐条</button></div>`+
   `<div class="chips" id="qstatus"><span class="chip-label">状态</span>`+
   FILTERS.map(([value,label])=>`<button class="chip" data-st="${value}">${label}<i>${chipCount(value)}</i></button>`).join('')+`</div>`+
   `<div id="qcount" class="result-info"></div><div id="qlist"></div>`+
   legend+
   `<div class="tip">「剧情线」按委托人 / 章节把支线串成一条路：点剧情线展开脊柱，点任务看触发条件、选项门槛与奖励。`+
   `隐藏任务用虚线框标出，触发方式直接写在任务名下面；同一处只能选一条的分支会并排显示，已选 / 未选一眼可辨。`+
   `搜索框会直接定位并展开对应剧情线里的任务。折叠状态、筛选与搜索会记住。</div>`;

 $('qview').onclick=e=>{const b=e.target.closest('[data-view]');if(!b)return;state.view=b.dataset.view;store.set(KEY,state);render()};
 $('qstatus').onclick=e=>{const b=e.target.closest('[data-st]');if(!b)return;state.status=b.dataset.st;store.set(KEY,state);render()};
 $('qs').oninput=e=>{state.q=e.target.value;store.set(KEY,state);render()};
 $('qlist').addEventListener('toggle',e=>{
   const el=e.target;
   if(el.classList&&el.classList.contains('sq-line')){state.open[el.dataset.line]=el.open;store.set(KEY,state)}
 },true);
 render();
 // 任务名可点：跳到对应剧情线的节点；不在支线页的任务给出归属提示
 function notice(text){
   const box=$('qcount');if(!box)return;
   const old=document.getElementById('qnotice');
   if(old)old.remove();
   const tip=document.createElement('div');
   tip.id='qnotice';tip.className='sq-notice';tip.textContent=text;
   box.parentNode.insertBefore(tip,box);
   setTimeout(()=>{if(tip.parentNode)tip.remove()},3200);
 }
 function jumpTo(qid){
   qid=Number(qid);
   const line=lines.filter(l=>(l.quests||[]).indexOf(qid)>=0)[0];
   if(!line){
     const info=questIndex[String(qid)]||{};
     notice(info.name?('「'+info.name+'」属于'+(info.type_name||'其他任务')+'，不在支线页。'):'这个任务不在支线页。');
     return;
   }
   state.open[line.id]=true;store.set(KEY,state);render();
   requestAnimationFrame(()=>{
     const el=document.querySelector('[data-q="'+qid+'"]');
     if(!el)return;
     if(el.tagName==='DETAILS')el.open=true;
     if(el.scrollIntoView)el.scrollIntoView({block:'center'});
     el.classList.add('sq-flash');
     setTimeout(()=>el.classList.remove('sq-flash'),1800);
   });
 }
 $('qlist').addEventListener('click',e=>{
   const ref=e.target.closest('[data-jump]');
   if(!ref)return;
   e.preventDefault();e.stopPropagation();
   jumpTo(ref.getAttribute('data-jump'));
 });
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['quest']=initQuest;
})();
