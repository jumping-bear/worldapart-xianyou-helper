/* 支线：剧情线任务脊柱。默认按玩家进度排序，节点内联展开，不弹窗、不另开面板。 */
(function(){
const KEY='worldapart.quest.story.v4';
const STATUS={done:'已完成',doing:'进行中',ready:'可接取',cond:'条件不足',wait:'未触发（需满足条件）',unpicked:'未选分支'};
const FILTERS=[['all','全部'],['ready','可接取'],['doing','进行中'],['wait','未触发'],
  ['cond','条件不足'],['unpicked','未选分支'],['done','已完成']];
const CHAPTER_ORDER={'炼气':1,'筑基':2,'结丹':3,'元婴':4,'化神':5,'隐藏':6,'支线':7};
const chapCls=c=>({'炼气':'qi','筑基':'zhu','结丹':'jie','元婴':'yuan','化神':'hua','隐藏':'hid'}[c]||'other');

function initQuest(){
 const m=DATA.modules&&DATA.modules.quest;if(!m)return;
 const host=$('quest'),st=m.rows||{},rows=st.rows||[],stats=st.stats||{},lines=st.storylines||[];
 if(!rows.length){host.innerHTML=sourceHtml(m)+'<div class="empty">暂无支线配置</div>';return}
 const byId={};rows.forEach(r=>byId[r.id]=r);
 let state=Object.assign({q:'',status:'all',view:'story',open:{}},store.get(KEY,{}));
 if(!state.open||typeof state.open!=='object')state.open={};

 const sk=r=>r.status_key||'wait';
 const statusText=r=>STATUS[sk(r)]||r.status_label||'';
 const locText=r=>{const l=r.location;if(!l)return r.place_text||r.spot||'位置未定';
   const path=(l.path&&l.path.length)?l.path.join(' / '):l.name;return (r.spot?r.spot+' · ':'')+path};
 const rewardTip=x=>[(x.sources||[]).join('/'),x.type?('类型：'+x.type):'',x.price?('参考价 '+x.price):''].filter(Boolean).join(' · ');
 const rewardChips=(r,limit)=>{
   const list=(r.rewards||[]).filter(x=>x.item!==50000&&x.name!=='灵石');
   const stone=r.reward_stone||0,cap=limit||3;
   let out=list.slice(0,cap).map(x=>`<span class="sq-rw f${x.quality||0}" title="${esc(rewardTip(x))}">${esc(x.name)}×${x.min===x.max?x.min:x.min+'-'+x.max}</span>`);
   if(list.length>cap)out.push(`<span class="sq-rw more">+${list.length-cap}</span>`);
   if(stone)out.push(`<span class="sq-stone">灵石 ${stone}</span>`);
   return out.join('');
 };
 const hay=(r)=>[r.name,r.desc,r.group,r.chain_name,(r.giver||{}).name,locText(r),r.status_hint,
   r.cond_text,r.trigger_text,(r.objectives||[]).map(o=>o.text).join(' '),
   (r.rewards||[]).map(x=>x.name).join(' '),
   (r.option_gates||[]).map(g=>(g.option||'')+' '+(g.text||'')).join(' ')].join(' ').toLowerCase();
 const query=()=>(state.q||'').trim().toLowerCase();
 const match=r=>!query()||hay(r).includes(query());
 const passStatus=r=>state.status==='all'||sk(r)===state.status;

 function checkRow(c){
   const ok=c.ok===true,bad=c.ok===false;
   return `<div class="sq-chk ${ok?'ok':bad?'bad':''}"><span class="sq-mark">${ok?'✓':bad?'✗':'?'}</span>`+
     `<span class="sq-ctext">${esc(c.text||'条件')}</span><span class="sq-cval">${esc(c.cur_text||'')}</span></div>`;
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
 function bodyHtml(r){
   const ce=r.cond_eval||{},checks=ce.checks||[],gaps=ce.gaps||[];
   const logic=ce.logic==='满足其一'?'满足其一即可':ce.logic==='全部满足'?'需要全部满足':(ce.logic?'部分条件满足其一即可':'');
   const cond=checks.length
     ? `<div class="sq-checks">${logic?`<div class="sq-logic">${esc(logic)}</div>`:''}${checks.map(checkRow).join('')}</div>`+
       (gaps.length?`<div class="sq-gap"><b>还差</b>${gaps.map(g=>`<span>${esc(g)}</span>`).join('')}</div>`:'')
     : `<div class="sq-muted">${esc(r.cond_text||r.trigger_text||'无额外触发条件，剧情到这里自动出现')}</div>`;
   const rewards=(r.rewards||[]).length
     ? `<div class="sq-rwlist">${r.rewards.map(x=>`<span class="sq-rw f${x.quality||0}" title="${esc(rewardTip(x))}">${esc(x.name)}×${x.min===x.max?x.min:x.min+'-'+x.max}<i>${esc((x.sources||[]).join('/'))}</i></span>`).join('')}</div>`
     : `<div class="sq-muted">剧情向，无固定奖励</div>`;
   return `<div class="sq-sec">触发条件</div>${cond}`+
     (r.desc?`<div class="sq-sec">这一段剧情</div><div class="sq-desc">${esc(r.desc)}</div>`:'')+
     gatesHtml(r)+
     ((r.objectives||[]).length?`<div class="sq-sec">要做的事</div><ul class="sq-objs">${r.objectives.map(o=>`<li>${esc(o.text)}${o.npc?'<em>'+esc(o.npc)+'</em>':''}</li>`).join('')}</ul>`:'')+
     `<div class="sq-sec">奖励</div>${rewards}`+
     (r.egg_note?eggHtml(r.egg_note):'')+
     (r.egg_note?'':(r.status_hint?`<div class="sq-hint"><b>怎么走</b>${esc(r.status_hint)}</div>`:''))+
     (r.unreachable?`<div class="sq-warn">${esc(r.unreachable_text)}</div>`:'');
 }
 function nodeHtml(r,index){
   const key=sk(r),one=r.hidden?(r.trigger_text||r.cond_text||r.status_hint):(r.status_hint||r.trigger_text||r.cond_text);
   const peers=r.branch_key?rows.filter(x=>x.id!==r.id&&x.branch_key===r.branch_key):[];
   const peerPicked=peers.some(x=>x.done||x.doing);
   const branchTag=r.branch_key&&(r.branch_with||[]).length
     ? ((r.done||r.doing)?'<span class="sq-tag sel">已选</span>':(peerPicked?'<span class="sq-tag unsel">未选</span>':''))
     : '';
   const hit=match(r)&&!!query();
   const open=hit?' open':'';
   return `<details class="sq-node k-${key}${r.hidden?' hidden':''}${hit?' hit':''}" data-q="${r.id}"${open}>`+
     `<summary><span class="sq-step">${index}</span><span class="sq-nm">${esc(r.name)}</span>`+
     `<span class="sq-badge b-${key}">${esc(statusText(r))}</span>`+
     (r.hidden?'<span class="sq-tag hid">不显示在任务面板</span>':'')+
     (r.egg_note?'<span class="sq-tag egg">含隐藏结局</span>':'')+branchTag+
     `<span class="sq-rwline">${rewardChips(r,2)}</span><span class="sq-loc">${esc(locText(r))}</span>`+
     `<span class="sq-one">${esc(one||'')}</span></summary>`+
     `<div class="sq-body">${bodyHtml(r)}</div></details>`;
 }
 function groupBranches(items){
   const out=[],seen={};
   items.forEach(r=>{
     if(r.branch_key&&seen[r.branch_key])return;
     if(r.branch_key){
       const group=items.filter(x=>x.branch_key===r.branch_key);
       seen[r.branch_key]=1;
       if(group.length>1){out.push(group);return}
     }
     out.push([r]);
   });
   return out;
 }
 function lineNodes(line){return (line.quests||[]).map(id=>byId[id]).filter(Boolean)}
 function lineVisible(line){
   const nodes=lineNodes(line);
   if(state.q&&!nodes.some(match))return false;
   if(state.status!=='all'&&!nodes.some(r=>sk(r)===state.status))return false;
   return true;
 }
 function lineRank(line){
   const nodes=lineNodes(line);
   if(!line.total)return nodes.every(r=>r.done)?9:8;
   if(nodes.some(r=>!r.done&&r.doing))return 0;
   if(nodes.some(r=>!r.done&&sk(r)==='ready'))return 1;
   if(nodes.some(r=>!r.done&&sk(r)==='cond'))return 2;
   if(nodes.some(r=>!r.done&&sk(r)==='wait'))return 3;
   if(nodes.every(r=>r.done))return 9;
   return 5;
 }
 function lineHtml(line){
   const nodes=lineNodes(line),visible=nodes.filter(passStatus);
   if(!nodes.length||(!visible.length&&state.status!=='all'))return '';
   if(state.q&&!nodes.some(match))return '';
   const depths=line.depths||{},rings={};
   nodes.forEach(r=>{const d=Number(depths[String(r.id)]||r.chain_index||1);(rings[d]=rings[d]||[]).push(r)});
   const body=Object.keys(rings).map(Number).sort((a,b)=>a-b).map((d,idx,arr)=>{
     const items=rings[d].filter(passStatus);
     if(!items.length)return '';
     const groups=groupBranches(items).map(group=>{
       if(group.length>1){
         return `<div class="sq-pair"><div class="sq-pair-h">${group.length>2?'多选一':'二选一'} · 只能选一条</div><div class="sq-pair-grid">`+
           group.map(r=>nodeHtml(r,d)).join('')+`</div></div>`;
       }
       return nodeHtml(group[0],d);
     }).join('');
     return `<div class="sq-ring"><div class="sq-rail"><span class="sq-dot">${d}</span>${idx<arr.length-1?'<i class="sq-bar"></i>':''}</div><div class="sq-nodes">${groups}</div></div>`;
   }).join('');
   if(!body)return '';
   const stored=state.open[line.id];
   const nextRow=line.next?byId[line.next]:null;
   const open=(state.q?true:(stored!==undefined?stored:(line.doing>0||(nextRow&&(nextRow.doing||sk(nextRow)==='ready')))));
   const npcs=(line.npc||[]).filter(n=>n&&line.name.indexOf(n)<0);
   return `<details class="sq-line" data-line="${esc(line.id)}"${open?' open':''}>`+
     `<summary class="sq-line-h"><span class="sq-chap c-${chapCls(line.chapter)}">${esc(line.chapter)}</span>`+
     `<span class="sq-lname">${esc(line.name)}</span>`+
     (npcs.length?`<span class="sq-npc">${esc(npcs.slice(0,3).join('、'))}</span>`:'')+
     `<span class="sq-prog" title="已走环数 / 可走环数（不含未选分支）">${line.total?('已走 '+line.done+'/'+line.total):'已选另一条路'}</span>`+
     (line.stones_left?`<span class="sq-stone">可拿灵石 ${line.stones_left}</span>`:'')+
     `<span class="sq-caret">›</span></summary>`+
     `<div class="sq-spine">${body}</div></details>`;
 }
 function flatCard(r){
   const key=sk(r),cy=r.cond_eval||{},checks=cy.checks||[];
   return `<details class="sq-flat${r.hidden?' hidden':''}" data-q="${r.id}">`+
     `<summary><span class="sq-nm">${esc(r.name)}</span><span class="sq-badge b-${key}">${esc(statusText(r))}</span>`+
     (r.hidden?'<span class="sq-tag hid">不显示在任务面板</span>':'')+
     `<span class="sq-rwline">${rewardChips(r,2)}</span><span class="sq-loc">${esc(locText(r))}</span></summary>`+
     `<div class="sq-body">`+
       (checks.length?`<div class="sq-checks">${checks.map(checkRow).join('')}</div>`:'')+
       (r.status_hint?`<div class="sq-hint"><b>怎么走</b>${esc(r.status_hint)}</div>`:'')+
       (r.desc?`<div class="sq-muted">${esc(r.desc)}</div>`:'')+
       gatesHtml(r)+eggHtml(r.egg_note)+`</div></details>`;
 }
 function flatHtml(){
   const list=rows.filter(r=>passStatus(r)&&match(r));
   if(!list.length)return '';
   const lineOf={};lines.forEach(line=>(line.quests||[]).forEach(id=>{lineOf[id]=line.name}));
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
     ||(CHAPTER_ORDER[a.chapter]||9)-(CHAPTER_ORDER[b.chapter]||9)
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
 const cards=`<div class="cards">`+
   `<div class="card"><div class="k">支线完成</div><div class="v">${stats.done||0} <span>/ ${stats.total||0}</span></div><div class="s">进行中 ${stats.doing||0}</div></div>`+
   `<div class="card"><div class="k">剧情线</div><div class="v">${stats.storylines||lines.length} <span>条</span></div><div class="s">按委托人 / 章节归拢</div></div>`+
   `<div class="card"><div class="k">还能拿的灵石</div><div class="v">${stats.stones_todo||0}</div><div class="s">未完成支线的奖励</div></div>`+
   `<div class="card"><div class="k">隐藏任务</div><div class="v">${stats.hidden||0} <span>个</span></div><div class="s">不会显示在游戏任务面板</div></div>`+
   `</div>`;
 const legend=`<div class="legend"><span>奖励颜色：</span><span><i style="background:#b4bdca"></i>品质0</span><span><i style="background:#a8dfb4"></i>品质1</span><span><i style="background:#a6cff0"></i>品质2</span><span><i style="background:#cbb2ee"></i>品质3</span><span><i style="background:#f0d38a"></i>品质4</span><span><i style="background:#f0a6a6"></i>品质5</span></div>`;
 host.innerHTML=sourceHtml(m)+cards+
   `<div class="search-panel"><div class="search-fields" style="grid-template-columns:1fr"><label class="search-field"><span>找任务 / 剧情线 / 委托人 / 地点 / 奖励</span><input id="qs" placeholder="例如：未竟之约、纪小蝶、神识、洗髓灵液"></label></div></div>`+
   `<div class="chips" id="qview"><span class="chip-label">视图</span>`+
   `<button class="chip" data-view="story">剧情线</button><button class="chip" data-view="flat">逐条</button></div>`+
   `<div class="chips" id="qstatus"><span class="chip-label">状态</span>`+
   FILTERS.map(([value,label])=>`<button class="chip" data-st="${value}">${label}</button>`).join('')+`</div>`+
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
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['quest']=initQuest;
})();
