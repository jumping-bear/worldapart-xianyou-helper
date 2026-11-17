/* 红尘：角色卡 + 环进度轴导航 + 聚焦当前环的任务树（IIFE，导出 window.PROGRESS_VIEWS.hongchen）
 * 交互：顶部进度轴可点击跳转到任意环；主体只展开“聚焦环”，通过上一环/下一环与
 *       相邻环快捷芯片步进，避免几十环横向铺开需要一路拖拽。
 */
(function(){
const KEY='hongchen';
const STATUS={
  done:{label:'已完成',cls:'s-done'}, doing:{label:'进行中',cls:'s-doing'},
  ready:{label:'可接取',cls:'s-ready'}, unpicked:{label:'另一条路',cls:'s-unpicked'},
  locked:{label:'未解锁',cls:'s-locked'}, notstarted:{label:'未开始',cls:'s-notstarted'}
};
// 过滤项 value 对应状态类；'cando' 合并“可接取 + 未开始(可开启分支)”。
const FILTERS=[['all','全部'],['cando','可做'],['doing','进行中'],['done','已完成'],
               ['unpicked','另一条路'],['locked','未解锁']];
let LINES=[], OPEN='', FILTER='all', QUERY='', CUR=null, FOCUS=0, REMAIN=true;

function statusOf(cls){return STATUS[cls]||STATUS.notstarted}
function byId(line){const m={};(line.quests||[]).forEach(q=>m[q.id]=q);return m}
function ringOf(q){return Number(q.depth)||1}

function ring(pct,color){
  const c=2*Math.PI*16, p=Math.max(0,Math.min(100,Number(pct)||0));
  return '<svg class="hongchen-ring-svg" viewBox="0 0 40 40" aria-hidden="true">'
    +'<circle class="hongchen-ring-bg" cx="20" cy="20" r="16"></circle>'
    +'<circle class="hongchen-ring-fg" cx="20" cy="20" r="16" style="stroke:'+esc(color||'#c9866b')
    +';stroke-dasharray:'+c.toFixed(1)+';stroke-dashoffset:'+(c*(1-p/100)).toFixed(1)+'"></circle></svg>'
    +'<span class="hongchen-ring-pct">'+p+'%</span>';
}

function matchFilter(q){
  if(FILTER==='all')return true;
  if(FILTER==='cando')return q.status_cls==='ready'||q.status_cls==='notstarted';
  return q.status_cls===FILTER;
}
function matchQuery(q){
  if(!QUERY)return true;
  return String(q.name).toLowerCase().indexOf(QUERY)>=0||String(q.id).indexOf(QUERY)>=0;
}
function isDim(q){return !matchFilter(q)||!matchQuery(q)}

function gateBadges(q){
  const out=[];
  (q.gates||[]).forEach(g=>{if(g&&g.text)out.push('<span class="hongchen-badge gate" title="'+esc(g.alias||'玩家门槛')+'">'+esc(g.text)+'</span>')});
  (q.options||[]).forEach(o=>{if(o&&o.gate&&o.gate.text)
    out.push('<span class="hongchen-badge opt" title="'+esc(o.text||'选项')+'">'+esc(o.gate.text)+'</span>')});
  return out.length?'<div class="hongchen-badges">'+out.join('')+'</div>':'';
}

function nodeHtml(q,map){
  const st=statusOf(q.status_cls);
  const dim=isDim(q)?' dim':'';
  const sel=(CUR===q.id)?' sel':'';
  const prev=(q.prev&&map[q.prev])?map[q.prev].name:'';
  // 分支任务用“N 选 1”提示，未选的那条写成“另一条路”，绝不写“已错过”。
  let foot=(q.branch?'分支 · ':'')+(prev?'前置「'+esc(prev)+'」':'起点');
  if(q.hidden)foot+=' · 隐藏';
  let note='';
  if(q.status_cls==='unpicked'&&q.fail_text)note='<div class="hongchen-node-note">'+esc(q.fail_text)+'</div>';
  return '<div class="hongchen-node '+st.cls+dim+sel+'" data-qid="'+q.id+'" title="'+esc(q.desc||q.name)+'">'
    +'<div class="hongchen-node-top"><span class="hongchen-id">#'+q.id+'</span>'
    +'<span class="hongchen-status">'+st.label+'</span></div>'
    +'<div class="hongchen-nname">'+esc(q.name)+'</div>'
    +(q.desc?'<div class="hongchen-desc">'+esc(q.desc)+'</div>':'')
    +note+gateBadges(q)
    +'<div class="hongchen-node-foot">'+foot+'</div></div>';
}

// 当前进度环：优先最近可接取环；否则最近完成/放弃环的下一环；否则第 1 环。
function currentDepth(line){
  const qs=line.quests||[];
  if(!qs.length)return 1;
  const ready=qs.filter(q=>q.status_cls==='ready').map(ringOf);
  if(ready.length)return Math.min.apply(null,ready);
  let frontier=0;
  qs.forEach(q=>{if(['done','doing','unpicked'].indexOf(q.status_cls)>=0)frontier=Math.max(frontier,ringOf(q))});
  const maxD=Math.max.apply(null,qs.map(ringOf));
  return Math.min(frontier+1,maxD)||1;
}
function maxDepth(line){
  const qs=line.quests||[];
  return qs.length?Math.max.apply(null,qs.map(ringOf)):1;
}
function ringState(line,d){
  const here=(line.quests||[]).filter(q=>ringOf(q)===d);
  if(!here.length)return 'empty';
  const c=here.map(q=>q.status_cls);
  if(c.indexOf('doing')>=0)return 'doing';
  if(c.indexOf('done')>=0)return 'done';
  if(c.indexOf('ready')>=0)return 'ready';
  if(c.indexOf('unpicked')>=0)return 'unpicked';
  return 'notstarted';
}

// 顶部进度轴：一环一个可点击圆点；当前环、聚焦环、有分支环各有标记。
// 每环右下角标出该环还剩几个（"还剩 2"），一眼看出卡在哪一环。
function axisHtml(line,curD){
  const maxD=maxDepth(line), dots=[];
  const rings={};
  (line.rings||[]).forEach(r=>{rings[r.depth]=r});
  for(let d=1;d<=maxD;d++){
    const here=(line.quests||[]).filter(q=>ringOf(q)===d);
    const st=ringState(line,d);
    const hasBranch=here.some(q=>q.branch);
    const left=(rings[d]&&rings[d].left)||0;
    const cls=['hongchen-axis-dot','rs-'+st];
    if(d===curD)cls.push('is-current');
    if(d===FOCUS)cls.push('is-focus');
    if(left)cls.push('has-left');
    const mark=hasBranch?'<i class="hongchen-axis-branch" title="本环有分支选择">⑂</i>':'';
    const leftBadge=left?'<i class="hongchen-axis-left" title="这一环还剩 '+left+' 个任务">'+left+'</i>':'';
    dots.push('<button type="button" class="'+cls.join(' ')+'" data-ring="'+d+'" '
      +'title="第 '+d+' 环 · '+here.length+' 节点'+(left?' · 还剩 '+left:'')+(d===curD?' · 当前进度环':'')+'">'
      +'<span>'+d+'</span>'+mark+leftBadge+'</button>');
  }
  return '<div class="hongchen-axis" role="tablist" aria-label="环进度轴">'+dots.join('')+'</div>';
}

// 聚焦环主体：只渲染这一环的节点，按分支分组；响应式网格，不再横向长列。
function focusBodyHtml(line){
  const map=byId(line);
  const here=(line.quests||[]).filter(q=>ringOf(q)===FOCUS);
  if(!here.length)return '<div class="hongchen-focus-empty">本环暂无任务节点</div>';
  const singles=[], groups={};
  here.forEach(q=>{if(q.branch&&q.branch_key){(groups[q.branch_key]=groups[q.branch_key]||[]).push(q)}else singles.push(q)});
  let html='';
  if(singles.length)html+='<div class="hongchen-node-grid">'+singles.map(q=>nodeHtml(q,map)).join('')+'</div>';
  Object.keys(groups).forEach(key=>{
    const members=groups[key];
    const chosen=members.filter(q=>q.status_cls==='done'||q.status_cls==='doing'||q.status_cls==='unpicked');
    const label=chosen.length?('分支选择 · '+members.length+' 选 1 · 已选'+(chosen.length>1?' '+chosen.length:' 1')):('分支选择 · '+members.length+' 选 1');
    html+='<div class="hongchen-branch"><div class="hongchen-branch-label">'+label+'</div>'
      +'<div class="hongchen-node-grid">'+members.map(q=>nodeHtml(q,map)).join('')+'</div></div>';
  });
  return html;
}

// 相邻环快捷芯片：给出上一环/下一环任务名，点击即跳过去。
function contextHtml(line){
  const wrap=(d,dir)=>{
    if(d<1||d>maxDepth(line))return '';
    const here=(line.quests||[]).filter(q=>ringOf(q)===d);
    if(!here.length)return '';
    const chips=here.slice(0,6).map(q=>{
      const st=statusOf(q.status_cls);
      return '<button type="button" class="hongchen-ctx-chip '+st.cls+'" data-ring="'+d+'" title="'+esc(q.name)+'">'+esc(q.name)+'</button>';
    }).join('');
    const more=here.length>6?'<span class="hongchen-ctx-more">+'+(here.length-6)+'</span>':'';
    return '<div class="hongchen-ctx-side"><span class="hongchen-ctx-dir">'+dir+'</span>'
      +'<div class="hongchen-ctx-chips">'+chips+more+'</div></div>';
  };
  return '<div class="hongchen-context">'+wrap(FOCUS-1,'‹ 上一环')+wrap(FOCUS+1,'下一环 ›')+'</div>';
}

// 「还差什么」：展开面板最上方，直接回答"我还剩哪些、为什么没做"。
// 可接取/未开始/差条件可点击跳到对应节点；分支另列"当时选了另一条路"，不算漏做。
function remainHtml(line){
  const r=line.remaining;
  if(!r)return '';
  const secs=[];
  const section=(title,cls,items,extraClass,flag)=>{
    if(!items||!items.length)return;
    secs.push('<div class="hongchen-remain-sec'+(extraClass?' '+extraClass:'')+'">'
      +'<div class="hongchen-remain-t"><i class="hongchen-dot '+cls+'"></i>'+title
      +'<em>'+items.length+'</em>'
      +(flag?'<span class="hongchen-remain-flag">'+flag+'</span>':'')+'</div>'
      +'<div class="hongchen-remain-list">'
      +items.map(it=>'<button type="button" class="hongchen-remain-chip '+cls+'" data-jump="'+it.id
        +'" title="第 '+it.depth+' 环 · '+esc(it.name)+'">'
        +'<span class="hongchen-remain-name">'+esc(it.name)+'</span>'
        +'<span class="hongchen-remain-ring">第 '+it.depth+' 环</span>'
        +(it.reason?'<span class="hongchen-remain-why">'+esc(it.reason)+'</span>':'')
        +'</button>').join('')
      +'</div></div>');
  };
  // 顺序固定：可接取永远排最前，并加"现在就能做"徽标，长清单里也能一眼找到。
  section('可接取','s-ready',r.ready,'is-ready','现在就能做');
  section('进行中','s-doing',r.doing);
  section('未开始','s-notstarted',r.notstarted);
  section('差条件','s-locked',r.locked);

  let choices='';
  const alts=(r.choices||[]);
  if(alts.length){
    choices='<div class="hongchen-remain-sec hongchen-remain-alts">'
      +'<div class="hongchen-remain-t"><i class="hongchen-dot s-unpicked"></i>当时选了另一条路<em>'+alts.length+'</em></div>'
      +'<div class="hongchen-remain-tip">'+esc(r.choice_note||'')+'</div>'
      +'<div class="hongchen-remain-choice-list">'
      +alts.map(c=>{
        const fork=c.parent_id
          ?'<button type="button" class="hongchen-remain-fork" data-jump="'+c.parent_id
            +'" title="第 '+c.depth+' 环 · 跳到这个分叉点">'+esc(c.text)+'</button>'
          :'<span class="hongchen-remain-fork is-plain">'+esc(c.text)+'</span>';
        return '<div class="hongchen-remain-choice">'+fork+'</div>';
      }).join('')
      +'</div></div>';
  }
  const empty=secs.length?'':'<div class="hongchen-remain-all">✓ 这条线已走完'
    +(alts.length?'；下面的分支是当时走的另一条路':'')+'</div>';
  const sum=r.done?'这条线已走完':('还差 '+r.left+' 项');
  return '<div class="hongchen-remain'+(REMAIN?'':' is-fold')+'">'
    +'<div class="hongchen-remain-head"><span class="hongchen-remain-title">还差什么</span>'
    +'<span class="hongchen-remain-sum'+(r.done?' is-done':'')+'">'+esc(sum)+'</span>'
    +'<button type="button" class="hongchen-remain-toggle">'+(REMAIN?'收起':'展开')+'</button></div>'
    +'<div class="hongchen-remain-body">'+empty+secs.join('')+choices+'</div>'
    +'</div>';
}

function inspectHtml(q,line){
  const st=statusOf(q.status_cls), map=byId(line);
  const gates=[];
  (q.gate_checks||[]).forEach(c=>{if(c&&c.text)gates.push(c)});
  if(!gates.length)(q.gates||[]).forEach(g=>{if(g&&g.text)gates.push({text:g.text,need:0})});
  (q.options||[]).forEach(o=>{
    if(!o)return;
    const to=(o.to||[]).map(id=>map[id]?map[id].name:('#'+id)).join(' / ');
    const check=o.check||{};
    gates.push({text:(o.gate?o.gate.text+' → ':'')+o.text+(to?' · '+to:''),
                need:check.need||0,cur:check.cur,ok:check.ok});
  });
  const next=(q.next||[]).map(id=>map[id]?esc(map[id].name):('#'+id)).join('、');
  const notice=(q.status_cls==='unpicked')
    ?'<div class="hongchen-inspect-note">这条支线当时没选，你走了另一条路；它不会再出现。</div>'
    :(q.status_cls==='notstarted'?'<div class="hongchen-inspect-note">前置剧情还没走到，先推进前面的任务吧。</div>':'');
  return '<div class="hongchen-inspect"><div class="hongchen-inspect-title">'
    +'<span class="hongchen-id">#'+q.id+'</span>'+esc(q.name)
    +'<span class="hongchen-status '+st.cls+'">'+st.label+'</span></div>'
    +(q.desc?'<p class="hongchen-inspect-desc">'+esc(q.desc)+'</p>':'')
    +notice
    +'<div class="hongchen-inspect-grid">'
    +'<div class="hongchen-ir"><b>所在环</b><span>第 '+ringOf(q)+' 环</span></div>'
    +'<div class="hongchen-ir"><b>前置</b><span>'+(q.prev&&map[q.prev]?esc(map[q.prev].name):'无（起点）')+'</span></div>'
    +'<div class="hongchen-ir"><b>后续</b><span>'+(next||'无')+'</span></div>'
    +'<div class="hongchen-ir"><b>分支</b><span>'+(q.branch?(esc((q.branch_with||[]).join(' / '))||'互斥选项'):'否')+'</span></div>'
    +(q.fail_text?'<div class="hongchen-ir full"><b>进度提示</b><span>'+esc(q.fail_text)+'</span></div>':'')
    +'</div>'
    +(gates.length?'<div class="hongchen-igates"><b>选项门槛</b>'+gates.map(g=>{
        const val=g.need?('当前 '+(g.cur===undefined?'?':g.cur)+' / 需 '+g.need):'';
        const state=g.ok===true?'已满足':(g.ok===false?'未满足':'');
        const cls=g.ok===true?' ok':(g.ok===false?' no':'');
        return '<span class="hongchen-badge gate'+cls+'">'+esc(g.text)
          +(val?'<em class="hongchen-gate-val">'+esc(val)+(state?' · '+state:'')+'</em>':'')+'</span>';
      }).join('')+'</div>':'')
    +'</div>';
}

function panelHtml(line){
  const selected=(line.quests||[]).filter(q=>CUR===q.id)[0];
  const p=line.progress||{}, curD=currentDepth(line);
  const here=(line.quests||[]).filter(q=>ringOf(q)===FOCUS);
  const doneHere=here.filter(q=>q.status_cls==='done').length;
  const headline=p.headline||((p.done||0)+'/'+(p.base||0)+' 已完成');
  return '<div class="hongchen-panel" style="--hongchen-accent:'+esc(line.color||'#c9866b')+'">'
    +'<div class="hongchen-panel-head"><div><b>'+esc(line.name)+'</b> · 情缘任务树'
    +'<span class="hongchen-panel-sum">'+esc(line.group)+' ｜ '+esc(headline)+'</span></div>'
    +'<button type="button" class="hongchen-close" title="收起">×</button></div>'
    +remainHtml(line)
    +'<div class="hongchen-toolbar"><span class="hongchen-chipset">'
    +FILTERS.map(f=>'<button type="button" class="hongchen-chip'+(FILTER===f[0]?' active':'')+'" data-filter="'+f[0]+'">'+f[1]+'</button>').join('')
    +'</span><input class="hongchen-search" type="search" placeholder="搜索任务名 / 编号" value="'+esc(QUERY)+'"></div>'
    +'<div class="hongchen-guide">点击顶部圆环可跳转到任意环；下方只展开当前聚焦环，不必横向拖动几十环。'
    +'<span class="hongchen-guide-key"><i class="is-current"></i>当前进度环</span>'
    +'<span class="hongchen-guide-key"><i class="is-focus"></i>正在查看</span>'
    +'<span class="hongchen-guide-key"><i class="rs-branch">⑂</i>有分支</span></div>'
    +axisHtml(line,curD)
    +'<div class="hongchen-focus-nav">'
    +'<button type="button" class="hongchen-step" data-step="-1"'+(FOCUS<=1?' disabled':'')+'>‹ 上一环</button>'
    +'<div class="hongchen-focus-title">第 '+FOCUS+' 环<span>'+here.length+' 节点 · 已走 '+doneHere
    +(FOCUS===curD?' · 当前进度环':'')+'</span></div>'
    +'<button type="button" class="hongchen-step" data-step="1"'+(FOCUS>=maxDepth(line)?' disabled':'')+'>下一环 ›</button></div>'
    +contextHtml(line)
    +'<div class="hongchen-focus-body">'+focusBodyHtml(line)+'</div>'
    +(selected?inspectHtml(selected,line):'<div class="hongchen-hint">点击任一节点查看前置、分支与门槛；暖色标记为带条件的选项。</div>')
    +'</div>';
}

function render(host,stats){
  const cards=LINES.map(line=>{
    const p=line.progress||{}, active=OPEN===line.group;
    const portrait=line.avatar?'<img src="'+esc(line.avatar)+'" alt="" loading="lazy">'
      :'<span>'+esc((line.name||'?').slice(0,1))+'</span>';
    return '<button type="button" class="hongchen-card'+(active?' active':'')+'" data-group="'+esc(line.group)
      +'" style="--hongchen-accent:'+esc(line.color||'#c9866b')+'">'
      +'<span class="hongchen-portrait">'+portrait+'</span>'
      +'<span class="hongchen-cinfo"><span class="hongchen-name">'+esc(line.name)+'</span>'
      +'<span class="hongchen-line">'+esc(line.group)+'</span>'
      +'<span class="hongchen-cardmeta">已完成 '+(p.done||0)+'/'+(p.base||p.total||0)+'</span>'
      +'<span class="hongchen-cardmeta hongchen-cardleft'+((line.remaining&&line.remaining.done)?' is-done':'')+'">'
      +esc((line.remaining&&line.remaining.brief)||'')+'</span></span>'
      +'<span class="hongchen-ring">'+ring(p.pct||0,line.color)+'</span>'
      +'<span class="hongchen-arrow">›</span></button>';
  }).join('');
  const line=LINES.filter(l=>l.group===OPEN)[0];
  host.innerHTML='<div class="hongchen-root">'
    +'<div class="hongchen-head"><div><div class="hongchen-title">红尘 · 六段情缘</div>'
    +'<div class="hongchen-sub">'+stats.quests+' 段任务 · '+stats.lines+' 条角色线 · 展开某人可看「还差什么」'
    +' ｜ 选项门槛已翻译成人话</div></div>'
    +'<div class="hongchen-legend">'
    +'<span><i class="hongchen-dot s-done"></i>已完成</span><span><i class="hongchen-dot s-doing"></i>进行中</span>'
    +'<span><i class="hongchen-dot s-ready"></i>可接取</span><span><i class="hongchen-dot s-notstarted"></i>未开始</span>'
    +'<span><i class="hongchen-dot s-unpicked"></i>另一条路</span><span><i class="hongchen-dot s-locked"></i>未解锁</span></div></div>'
    +'<div class="hongchen-cards">'+cards+'</div>'
    +(line?panelHtml(line):'<div class="hongchen-empty-hint">选择一位角色，展开她的情缘任务树</div>')
    +'</div>';
}

function setFocus(host,stats,d,line){
  const maxD=maxDepth(line||LINES.filter(l=>l.group===OPEN)[0]);
  FOCUS=Math.max(1,Math.min(maxD,d));
  CUR=null;
  render(host,stats);
  const axis=host.querySelector('.hongchen-axis-dot.is-focus');
  if(axis&&axis.scrollIntoView)axis.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});
}

// 跳到指定任务节点：切到它所在的环、选中并滚到它的详情。
function jumpTo(host,stats,qid){
  const line=LINES.filter(l=>l.group===OPEN)[0]; if(!line)return;
  const q=(line.quests||[]).filter(x=>x.id===qid)[0]; if(!q)return;
  FOCUS=ringOf(q); CUR=q.id; render(host,stats);
  setTimeout(function(){
    const el=host.querySelector('.hongchen-node.sel')||host.querySelector('.hongchen-inspect');
    if(el&&el.scrollIntoView)el.scrollIntoView({behavior:'smooth',block:'center'});
  },0);
}

function init(){
  const host=$('hongchen'); if(!host)return;
  const m=DATA.modules&&DATA.modules.hongchen;
  const payload=(m&&m.rows)||{};
  LINES=payload.rows||[];
  const stats=payload.stats||{};
  if(!LINES.length){
    host.innerHTML=sourceHtml(m||{})+'<div class="hongchen-empty">暂无红尘任务配置</div>';return;
  }
  OPEN=store.get('hongchen.open',''); FILTER=store.get('hongchen.filter','all');
  if(!LINES.some(l=>l.group===OPEN))OPEN='';
  const line0=LINES.filter(l=>l.group===OPEN)[0];
  if(line0)FOCUS=currentDepth(line0);
  render(host,stats);

  host.addEventListener('click',function(e){
    const card=e.target.closest('.hongchen-card');
    if(card){const g=card.getAttribute('data-group');OPEN=(OPEN===g?'':g);CUR=null;
      const ln=LINES.filter(l=>l.group===OPEN)[0];if(ln)FOCUS=currentDepth(ln);
      store.set('hongchen.open',OPEN);render(host,stats);return}
    const chip=e.target.closest('.hongchen-chip');
    if(chip){FILTER=chip.getAttribute('data-filter');store.set('hongchen.filter',FILTER);render(host,stats);return}
    const toggle=e.target.closest('.hongchen-remain-toggle');
    if(toggle){REMAIN=!REMAIN;const box=toggle.closest('.hongchen-remain');
      if(box)box.classList.toggle('is-fold',!REMAIN);toggle.textContent=REMAIN?'收起':'展开';return}
    const jump=e.target.closest('[data-jump]');
    if(jump){jumpTo(host,stats,Number(jump.getAttribute('data-jump')));return}
    const dot=e.target.closest('.hongchen-axis-dot');
    if(dot){setFocus(host,stats,Number(dot.getAttribute('data-ring')));return}
    const ctx=e.target.closest('.hongchen-ctx-chip');
    if(ctx){setFocus(host,stats,Number(ctx.getAttribute('data-ring')));return}
    const step=e.target.closest('.hongchen-step');
    if(step&&!step.disabled){setFocus(host,stats,FOCUS+Number(step.getAttribute('data-step')));return}
    const node=e.target.closest('.hongchen-node');
    if(node){const id=Number(node.getAttribute('data-qid'));CUR=(CUR===id?null:id);render(host,stats);
      setTimeout(function(){const t=host.querySelector('.hongchen-inspect');if(t&&t.scrollIntoView)t.scrollIntoView({behavior:'smooth',block:'nearest'})},0);return}
    if(e.target.closest('.hongchen-close')){OPEN='';CUR=null;store.set('hongchen.open','');render(host,stats)}
  });
  host.addEventListener('input',function(e){
    if(!e.target.classList.contains('hongchen-search'))return;
    QUERY=e.target.value.trim().toLowerCase();
    const line=LINES.filter(l=>l.group===OPEN)[0];if(!line)return;
    const map=byId(line);
    host.querySelectorAll('.hongchen-node').forEach(function(el){
      const q=map[Number(el.getAttribute('data-qid'))];
      el.classList.toggle('dim',q?isDim(q):false);
    });
  });
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS.hongchen=init;
})();
