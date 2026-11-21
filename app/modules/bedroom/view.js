/* 仙居楼互动：成就「十八摸」进度。支持未完成优先排序与只看未满，6 段改为实心/空心进度块。 */
(function(){
function bedAvatar(name,src){const initial=esc(String(name||'?').slice(0,1));if(!src)return `<span class="bed-avatar">${initial}</span>`;return `<span class="bed-avatar has-img">${initial}<img src="${esc(src)}" alt="" loading="lazy" onerror="this.remove()"></span>`}

var KEY='worldapart.bedroom.v1';
var state=Object.assign({unfinished:0,less:0},store.get(KEY,{}));
function save(){store.set(KEY,state)}

// 每个部位 6 段：实心＝已获得，空心＝还缺；悬停可见第 N 段状态。
function segBlocks(p){
  return Array.from({length:6},(_,i)=>{
    const on=p.got.includes(i);
    return `<i class="bseg ${on?'on':'miss'}" title="第 ${i+1} 段${on?'已获得':'未获得'}"></i>`;
  }).join('');
}

function renderBedroom(){
  const m=DATA.modules.bedroom;if(!m)return;
  const rows=(m.rows||[]).slice();
  const done=rows.filter(r=>r.total>=18).length;
  const goals=[[1,'十八摸Ⅰ'],[3,'十八摸Ⅱ'],[5,'十八摸Ⅲ'],[10,'十八摸Ⅳ']];
  let cards=`<div class="card"><div class="k">已完成 18/18</div><div class="v">${done} <span>位</span></div></div>`;
  for(const [n,name] of goals)cards+=`<div class="card"><div class="k">${name}</div><div class="v">${done>=n?'已达成':'还差 '+(n-done)+' 位'}</div></div>`;

  rows.sort(state.unfinished
    ? (a,b)=>a.total-b.total||String(a.who).localeCompare(String(b.who),'zh-CN')
    : (a,b)=>b.total-a.total||String(a.who).localeCompare(String(b.who),'zh-CN'));
  const visible=state.less?rows.filter(r=>r.total<18):rows;

  const body=visible.map(r=>{
    const parts=r.parts.map(p=>`<div class="part"><div class="pl">${esc(p.label)} <em>${p.got.length}/6</em></div><div class="dots">${segBlocks(p)}</div></div>`).join('');
    const pct=Math.min(100,Math.floor(r.total*100/18));
    return `<tr class="row${r.total>=18?' full-row':''}"><td><div class="bedwho">${bedAvatar(r.who,r.avatar)}<div><div class="who">${esc(r.who)}${r.resident?'':'<span class="badge">未入住</span>'}</div><div class="bed">${esc(r.bed)}</div></div></div></td><td><div class="parts">${parts}</div></td><td style="width:150px"><div class="pct ${r.total>=18?'full':''}">${r.total}/18<small>${r.total>=18?'已完成':'进行中'}</small></div><div class="bar"><i style="width:${pct}%"></i></div></td></tr>`;
  }).join('');

  const controls=`<div class="chips bed-controls"><span class="chip-label">进度视图</span>`+
    `<button type="button" id="bed-unfinished" class="chip${state.unfinished?' on':''}">未完成优先</button>`+
    `<button type="button" id="bed-less" class="chip${state.less?' on':''}">只看未满</button></div>`;

  $('bedroom').innerHTML=sourceHtml(m)+`<div class="cards">${cards}</div>${controls}`+
    (visible.length?`<table><thead><tr><th>仙友 / 寝室</th><th>各部位 6 段</th><th></th></tr></thead><tbody>${body}</tbody></table>`:'<div class="empty">暂无仙居楼互动数据</div>')+
    `<div class="tip">仙居楼互动：进入仙居楼与入住的仙友互动，每位仙友 3 个部位、每个部位 6 段（0~3 为四段升阶，4 为循环段，5 为回落段）；18/18 才算 1 位，对应成就「十八摸 Ⅰ~Ⅳ」。实心块＝已获得的段，空心块＝还缺的段，悬停可见第几段。这里会合并同一角色所有存档里曾经获得过的段，旧档拿到的不会丢；互动后保存一次即可刷新，档位见上方「来源」。</div>`;

  const b1=$('bed-unfinished'),b2=$('bed-less');
  if(b1)b1.onclick=function(){state.unfinished=state.unfinished?0:1;save();renderBedroom()};
  if(b2)b2.onclick=function(){state.less=state.less?0:1;save();renderBedroom()};
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['bedroom']=renderBedroom;
})();
