/* 探索：五项探索属性的本月入口、切磋次数与委托目标。 */
(function(){
const UI_KEY='worldapart.explore.ui.v3';
const DEFAULTS={view:'attr',attr:0,q:'',type:'',range:'',stamina:0,commission:0};
let ui=Object.assign({},DEFAULTS,store.get(UI_KEY,{}));
if(ui.view!=='place'&&ui.view!=='task')ui.view='attr';
let ATTR_NAMES={};

function save(){store.set(UI_KEY,ui)}
function n(v){const x=Number(v);return Number.isFinite(x)?x:0}
function fmt(v){return n(v).toLocaleString('zh-CN')}
function attrName(id){return ATTR_NAMES[n(id)]||'未识别属性'}
function typesOf(list){
  const counts={};
  list.forEach(e=>{counts[e.button]=(counts[e.button]||0)+1});
  return Object.keys(counts).sort((a,b)=>counts[b]-counts[a]||String(a).localeCompare(String(b),'zh-CN'));
}

function commissionHtml(e){
  return (e.commission||[]).map(c=>{
    const cls=(c.matched?' match':' other')+(c.accepted?' accepted':'');
    const title=`${c.name}（${c.kind}·${c.action}）｜接取：${c.board_place}（${c.board_npc}）`;
    return `<span class="ex-comm${cls}" title="${esc(title)}">${c.accepted?'进行中 · ':''}${esc(c.action)}委托</span>`;
  }).join('');
}

function rowHtml(e,recommended){
  const tags=[];
  if(e.status!=='可做')tags.push(`<span class="ex-tag ${e.status==='精力不足'?'warn':'off'}">${esc(e.status)}</span>`);
  const exp=e.exp_max?`<b>${fmt(e.exp_min)}–${fmt(e.exp_max)}</b> <span>${esc(attrName(e.attr))}</span>`:'<span class="ex-muted">无属性经验</span>';
  const bonus=e.bonus?`<div class="ex-bonus">${esc(e.bonus)}</div>`:'';
  const tag=e.tag?`<span class="ex-tag">${esc(e.tag)}</span>`:'';
  return `<div class="ex-row${e.status==='可做'?'':' off'}${recommended?' rec':''}">
   <div class="ex-npc"><b>${esc(e.name)}</b><span class="ex-sub">${esc(e.button)}${recommended?' · 优先':''}</span></div>
   <div class="ex-exp">${exp}${bonus}</div>
   <div class="ex-stam">${n(e.stamina)?`精力 ${n(e.stamina)}`:'精力 0'}</div>
   <div class="ex-loc" title="${esc(e.path_text)}">${esc(e.path_text)}</div>
   <div class="ex-badges">${tag}${tags.join('')}${commissionHtml(e)}</div>
  </div>`;
}

function rowsHtml(list,recommended){
  return list.map(e=>rowHtml(e,recommended)).join('');
}

function sparBlock(group,r){
  const take=Math.min(3,group.length);
  const rec=group.slice(0,take),rest=group.slice(take);
  return `<div class="ex-note">普通菜单切磋不产出体魄经验；下面只列本月切磋入口。</div>`+
    `<div class="ex-subhead">优先参考 ${rec.length} 个 <span>按经验从高到低；入口彼此独立，按自身成功次数计算</span></div>`+
    rowsHtml(rec,true)+
    (rest.length?`<details class="ex-more"><summary>展开其余 ${rest.length} 个切磋入口</summary>${rowsHtml(rest)}</details>`:'');
}

function attrBlock(list,r){
  const attrs=r.attrs||[];
  return attrs.map(a=>{
    const group=list.filter(e=>n(e.attr)===n(a.id));
    if(!group.length)return '';
    const pct=a.need?Math.min(100,Math.floor(n(a.exp)*100/n(a.need))):100;
    const isSpar=!!n((r.spar||{}).type)&&group.some(e=>n(e.type)===n(r.spar.type));
    return `<section class="ex-attr">
     <div class="ex-attr-head">
      <div class="ex-attr-name">${esc(a.name)}<span class="ex-lv">Lv.${n(a.level)}</span></div>
      <div class="ex-attr-exp">${fmt(a.exp)}${a.need?` / ${fmt(a.need)}`:''}<small>${a.need?'下一级':'已满级'}</small></div>
     </div>
     <div class="ex-bar"><i style="width:${pct}%"></i></div>
     <div class="ex-attr-meta">本月入口 ${group.length} 个</div>
     ${isSpar?sparBlock(group,r):(group.length>8?`${rowsHtml(group.slice(0,8))}<details class="ex-more"><summary>展开其余 ${group.length-8} 个入口</summary>${rowsHtml(group.slice(8))}</details>`:rowsHtml(group))}
    </section>`;
  }).join('')||'<div class="empty">当前筛选下没有可做的入口</div>';
}

function placeBlock(list,r){
  const groups=new Map();
  list.forEach(e=>{
    const key=e.path_text||'未知地点';
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(e);
  });
  const rows=[...groups.entries()].map(([path,items])=>{
    const top=items.slice().sort((a,b)=>n(b.exp_max)-n(a.exp_max)||n(b.exp_min)-n(a.exp_min))[0];
    const stamina=items.reduce((sum,e)=>sum+n(e.stamina),0);
    const matched=items.filter(e=>(e.commission||[]).some(c=>c.matched)).length;
    return {path:path,items:items,top:top,stamina:stamina,matched:matched};
  }).sort((a,b)=>n(b.top.exp_max)-n(a.top.exp_max)||b.items.length-a.items.length||String(a.path).localeCompare(String(b.path),'zh-CN'));
  if(!rows.length)return '<div class="empty">当前筛选下没有可做的入口</div>';
  return rows.map(row=>{
    const items=row.items,top=row.top;
    const types=typesOf(items);
    return `<section class="ex-scene">
     <div class="ex-scene-head"><b>${esc(row.path)}</b><span>${items.length} 个入口 · ${esc(types.join('、'))} · 合计精力 ${row.stamina} · 最高 ${fmt(top.exp_min)}–${fmt(top.exp_max)} ${esc(attrName(top.attr))}${row.matched?` · ${row.matched} 个可顺路委托`:''}</span></div>
     ${rowsHtml(items)}
    </section>`;
  }).join('');
}

function filterList(r){
  const q=(ui.q||'').trim().toLowerCase();
  return (r.entries||[]).filter(e=>{
    if(ui.attr&&n(e.attr)!==n(ui.attr))return false;
    if(ui.type&&e.button!==ui.type)return false;
    if(ui.range&&(e.exp_min+'-'+e.exp_max)!==ui.range)return false;
    if(ui.stamina&&!e.enough)return false;
    if(ui.commission&&!e.matched_task)return false;
    if(q){
      const hay=[e.name,e.button,e.tag,attrName(e.attr),e.path_text,...(e.commission||[]).map(c=>c.name)].join(' ').toLowerCase();
      if(hay.indexOf(q)<0)return false;
    }
    return true;
  }).sort((a,b)=>n(b.exp_max)-n(a.exp_max)||n(b.exp_min)-n(a.exp_min)||String(a.path_text).localeCompare(String(b.path_text),'zh-CN')||String(a.name).localeCompare(String(b.name),'zh-CN'));
}

function statusHtml(r){
  const st=r.stamina||{},t=r.totals||{},d=r.date||{};
  const levels=(r.attrs||[]).map(a=>{
    const expText=a.need?`${fmt(a.exp)}/${fmt(a.need)}`:`${fmt(a.exp)} · 已满级`;
    const active=n(ui.attr)===n(a.id);
    return `<button type="button" class="ex-lvchip${active?' on':''}" data-attr="${n(a.id)}" title="点击只看${esc(a.name)}，再点取消"><b>${esc(a.name)}</b> Lv.${n(a.level)}<i>${expText}</i></button>`;
  }).join('');
  // 存档里的「精力上限」是基础值，天赋/装备加成后当前值可能超过它；此时只报当前值，不写成 148/140。
  const staminaText=n(st.max)&&n(st.cur)<=n(st.max)
    ?`精力 ${fmt(st.cur)}/${fmt(st.max)}`:`精力 ${fmt(st.cur)}`;
  return `<div class="ex-levels">${levels}</div>
   <div class="ex-meta">
    <span>游戏时间 ${n(d.year)} 年 ${n(d.month)} 月 ${n(d.day)} 日</span>
    <span>本月入口 ${fmt(t.entries)} 个（每月刷新，每个 NPC 最多 1 个）· 不在当前世界 ${fmt(t.retired)} 个</span>
    <span>${staminaText}</span>
    <span>委托 ${fmt(t.tasks)} 条 · ${fmt(t.matched_tasks)} 条可顺路</span>
   </div>`;
}

function controlsHtml(r){
  const types=typesOf(r.entries||[]);
  const tasks=(r.commissions||[]).length;
  const typeOpts=['<option value="">全部互动</option>'].concat(types.map(t=>`<option value="${esc(t)}"${ui.type===t?' selected':''}>${esc(t)}</option>`)).join('');
  const rangeOpts=[['','全部经验']].concat((r.ranges||[]).map(([lo,hi])=>[lo+'-'+hi,lo+'–'+hi])).map(([v,l])=>`<option value="${v}"${ui.range===v?' selected':''}>${l}</option>`).join('');
  return `<div class="ex-controls">
    <div class="ex-seg"><button type="button" data-view="attr" class="${ui.view==='attr'?'on':''}">按属性</button><button type="button" data-view="place" class="${ui.view==='place'?'on':''}">按位置</button>${tasks?`<button type="button" data-view="task" class="${ui.view==='task'?'on':''}">委托目标 ${fmt(tasks)}</button>`:''}</div>
    <input id="ex-q" value="${esc(ui.q)}" placeholder="搜索 NPC / 场景 / 互动 / 委托">
    <button type="button" id="ex-match" class="ex-match${ui.commission?' on':''}">可顺路委托 ${fmt((r.totals||{}).matched_tasks)}</button>
   </div>
   <details class="ex-adv"><summary>筛选条件 <span>互动类型 / 经验区间 / 精力</span></summary>
    <div class="ex-adv-grid">
     <select id="ex-type">${typeOpts}</select>
     <select id="ex-range">${rangeOpts}</select>
     <label class="ex-check"><input type="checkbox" id="ex-stamina"${ui.stamina?' checked':''}> 只看精力够</label>
    </div>
   </details>`;
}

function tasksHtml(r){
  const list=r.commissions||[];
  if(!list.length)return '';
  const matched=list.filter(c=>c.matched).length;
  return `<div class="ex-task-list">${list.map(c=>`<div class="ex-task">
    <div><b>${esc(c.name)}</b><span>${esc(c.kind)} · ${esc(c.action)}</span>
     <div class="ex-task-place">接取：${esc(c.board_place)}（${esc(c.board_npc)}）${c.board_enabled?'':' · 未开放'}</div>
     <div class="ex-task-place">目标：${esc(c.target_place||'未识别地点')}（${esc(c.npc_name)}）</div>
    </div>
    <div>${c.matched?'<span class="ex-tag mid">可顺路</span>':'<span class="ex-tag">接取后可做</span>'}${c.accepted?'<span class="ex-tag hi">进行中</span>':''}</div>
   </div>`).join('')}</div>
   <div class="ex-task-note">本月 ${list.length} 条委托，${matched} 条与本月入口动作一致可顺路完成。切磋类委托接取后可直接在 NPC 菜单完成；疏经导脉/说服类委托接取后会在目标 NPC 上临时开启对应入口，不需要等本月抽取。</div>`;
}

function rulesHtml(r){
  const ratios=(r.ratios||[]).join(' / ')||'按 NPC 分组配置';
  const costs=(r.costs||[]).join(' / ')||'—';
  return `<details class="ex-rules-wrap"><summary>刷新与限制</summary>
   <div class="ex-rules">
    <ul>
     <li>每月刷新：每个 NPC 每月最多抽到 1 个特殊互动入口，没抽中的 NPC 本月没有入口。</li>
     <li>抽取概率上限按 NPC 分组配置：${esc(ratios)}。</li>
     <li>入口按自身成功次数计算：完成 1 次后本月消失；未完成的入口月底作废，下月重新抽，不累积。</li>
     <li>每次特殊互动消耗 ${esc(costs)} 精力（0 表示不消耗）；精力不足的行会标灰。</li>
     <li>切磋入口按自身成功次数计算，页面不显示全月次数上限；普通菜单切磋不在本页统计。</li>
     <li>经验范围是基础值，实际获取受天赋与角色加成影响。</li>
     <li>不在当前世界的 NPC（已寿终 / 已退隐 / 尚未登场）不参与抽取，也不计入本月可做入口。</li>
     <li>委托徽标来自当前存档的城镇/宗门委托；“可顺路完成”表示任务动作与本入口一致。</li>
    </ul>
   </div>
  </details>`;
}

function paintBody(panel,r){
  const body=panel.querySelector('#ex-body');
  const count=panel.querySelector('#ex-count');
  if(!body||!count)return;
  if(ui.view==='task'){
    // 委托就在原位展开：不跳到底部，接取点与目标点始终同屏
    const list=r.commissions||[];
    const matched=list.filter(c=>c.matched).length;
    count.textContent=`本月委托 ${list.length} 条 · ${matched} 条可顺路 · 含接取地点与目标地点`;
    body.innerHTML=list.length?tasksHtml(r):'<div class="empty">当前存档没有可接的城镇/宗门委托</div>';
    return;
  }
  const list=filterList(r);
  const scope=ui.attr?(r.entries||[]).filter(e=>n(e.attr)===n(ui.attr)):(r.entries||[]);
  const total=scope.length;
  const hint=ui.view==='place'?'按位置查看 · 场景按最高经验排序':'按属性查看 · 入口按经验从高到低';
  const focus=ui.attr?`只看 ${attrName(ui.attr)} · `:'';
  count.textContent=`${focus}${list.length} / ${total} 个入口 · ${hint}`;
  body.innerHTML=ui.view==='attr'?attrBlock(list,r):placeBlock(list,r);
}

function renderExplore(DATA){
  const panel=$('explore');
  if(!panel)return;
  const m=DATA.modules.explore||{};
  const r=m.rows||{};
  ATTR_NAMES={};
  (r.attrs||[]).forEach(a=>{ATTR_NAMES[n(a.id)]=a.name||'未识别属性'});
  const warnings=(r.warnings||[]).slice(0,5);
  const warnHtml=warnings.length?`<div class="ex-warn">${warnings.map(esc).join('<br>')}${(r.warnings||[]).length>5?`<br>另有 ${(r.warnings||[]).length-5} 条提示`:''}</div>`:'';
  panel.innerHTML=sourceHtml(m)+statusHtml(r)+warnHtml+controlsHtml(r)+
    '<div id="ex-count" class="ex-count"></div><div id="ex-body"></div>'+rulesHtml(r);

  panel.querySelectorAll('[data-view]').forEach(btn=>{
    btn.onclick=function(){
      ui.view=btn.dataset.view;save();
      panel.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('on',x.dataset.view===ui.view));
      paintBody(panel,r);
    };
  });
  panel.querySelectorAll('[data-attr]').forEach(btn=>{
    btn.onclick=function(){
      const id=n(btn.dataset.attr);
      ui.attr=n(ui.attr)===id?0:id;save();
      panel.querySelectorAll('[data-attr]').forEach(x=>x.classList.toggle('on',n(x.dataset.attr)===n(ui.attr)));
      paintBody(panel,r);
    };
  });
  const q=panel.querySelector('#ex-q');
  if(q)q.oninput=function(){ui.q=this.value;save();paintBody(panel,r)};
  const type=panel.querySelector('#ex-type');
  if(type)type.onchange=function(){ui.type=this.value;save();paintBody(panel,r)};
  const range=panel.querySelector('#ex-range');
  if(range)range.onchange=function(){ui.range=this.value;save();paintBody(panel,r)};
  const stamina=panel.querySelector('#ex-stamina');
  if(stamina)stamina.onchange=function(){ui.stamina=this.checked?1:0;save();paintBody(panel,r)};
  const match=panel.querySelector('#ex-match');
  if(match)match.onclick=function(){
    ui.commission=ui.commission?0:1;save();
    match.classList.toggle('on',!!ui.commission);
    paintBody(panel,r);
  };
  paintBody(panel,r);
}

window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['explore']=renderExplore;
})();
