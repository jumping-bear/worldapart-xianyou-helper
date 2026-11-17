/* 红尘：六条情缘角色卡 + 任务树（IIFE，导出 window.PROGRESS_VIEWS.hongchen） */
(function(){
const KEY='hongchen';
const STATUS={
  done:{label:'已完成',cls:'s-done'}, doing:{label:'进行中',cls:'s-doing'},
  ready:{label:'可接取',cls:'s-ready'}, missed:{label:'已错过',cls:'s-missed'},
  locked:{label:'条件不足',cls:'s-locked'}, todo:{label:'待解锁',cls:'s-todo'}
};
const FILTERS=[['all','全部'],['ready','可接取'],['doing','进行中'],['done','已完成'],['missed','已错过']];
let LINES=[], OPEN='', FILTER='all', QUERY='', CUR=null;

function statusOf(cls){return STATUS[cls]||STATUS.ready}
function byId(line){const m={};(line.quests||[]).forEach(q=>m[q.id]=q);return m}

function ring(pct,color){
  const c=2*Math.PI*16, p=Math.max(0,Math.min(100,Number(pct)||0));
  return '<svg class="hongchen-ring-svg" viewBox="0 0 40 40" aria-hidden="true">'
    +'<circle class="hongchen-ring-bg" cx="20" cy="20" r="16"></circle>'
    +'<circle class="hongchen-ring-fg" cx="20" cy="20" r="16" style="stroke:'+esc(color||'#c9866b')
    +';stroke-dasharray:'+c.toFixed(1)+';stroke-dashoffset:'+(c*(1-p/100)).toFixed(1)+'"></circle></svg>'
    +'<span class="hongchen-ring-pct">'+p+'%</span>';
}

function gateBadges(q){
  const out=[];
  (q.gates||[]).forEach(g=>{if(g&&g.text)out.push('<span class="hongchen-badge gate" title="'+esc(g.alias||'玩家门槛')+'">'+esc(g.text)+'</span>')});
  (q.options||[]).forEach(o=>{if(o&&o.gate&&o.gate.text)
    out.push('<span class="hongchen-badge opt" title="'+esc(o.text||'选项')+'">'+esc(o.gate.text)+'</span>')});
  return out.length?'<div class="hongchen-badges">'+out.join('')+'</div>':'';
}

function nodeHtml(q,map,filter){
  const st=statusOf(q.status_cls);
  const dim=(FILTER!=='all'&&q.status_cls!==FILTER)?' dim':'';
  const sel=(CUR===q.id)?' sel':'';
  const prev=(q.prev&&map[q.prev])?map[q.prev].name:'';
  return '<div class="hongchen-node '+st.cls+dim+sel+'" data-qid="'+q.id+'" title="'+esc(q.desc||'')+'">'
    +'<div class="hongchen-node-top"><span class="hongchen-id">#'+q.id+'</span>'
    +'<span class="hongchen-status">'+st.label+'</span></div>'
    +'<div class="hongchen-nname">'+esc(q.name)+'</div>'
    +(q.desc?'<div class="hongchen-desc">'+esc(q.desc)+'</div>':'')
    +gateBadges(q)
    +'<div class="hongchen-node-foot">'+(prev?'前置 '+esc(prev):'起点')
    +(q.branch?' · 分支':'')+(q.hidden?' · 隐藏':'')+'</div></div>';
}

function treeHtml(line){
  const map=byId(line), qs=line.quests||[];
  const maxDepth=qs.reduce((m,q)=>Math.max(m,q.depth||1),1);
  const cols=[];
  for(let d=1;d<=maxDepth;d++){
    const here=qs.filter(q=>(q.depth||1)===d);
    if(!here.length){cols.push('<div class="hongchen-col gap"><div class="hongchen-col-head">第 '+d+' 环</div><div class="hongchen-col-body">· · ·</div></div>');continue}
    const groups={}, singles=[];
    here.forEach(q=>{if(q.branch&&q.branch_key){(groups[q.branch_key]=groups[q.branch_key]||[]).push(q)}else singles.push(q)});
    let body=singles.map(q=>nodeHtml(q,map,FILTER)).join('');
    Object.keys(groups).forEach(key=>{
      const members=groups[key];
      body+='<div class="hongchen-branch"><div class="hongchen-branch-label">分支选择 · '+members.length+' 选 1</div>'
        +'<div class="hongchen-branch-grid">'+members.map(q=>nodeHtml(q,map,FILTER)).join('')+'</div></div>';
    });
    cols.push('<div class="hongchen-col"><div class="hongchen-col-head"><b>第 '+d+' 环</b><span>'+here.length+' 节点</span></div>'
      +'<div class="hongchen-col-body">'+body+'</div></div>');
  }
  return '<div class="hongchen-tree">'+cols.map((c,i)=>c+(i<cols.length-1?'<div class="hongchen-link">›</div>':'')).join('')+'</div>';
}

function inspectHtml(q,line){
  const st=statusOf(q.status_cls), map=byId(line);
  const gates=[];
  (q.gates||[]).forEach(g=>{if(g&&g.text)gates.push(g.text)});
  (q.options||[]).forEach(o=>{
    if(!o)return;
    const to=(o.to||[]).map(id=>map[id]?map[id].name:('#'+id)).join(' / ');
    gates.push((o.gate?o.gate.text+' → ':'')+o.text+(to?' · '+to:''));
  });
  const next=(q.next||[]).map(id=>map[id]?esc(map[id].name):('#'+id)).join('、');
  return '<div class="hongchen-inspect"><div class="hongchen-inspect-title">'
    +'<span class="hongchen-id">#'+q.id+'</span>'+esc(q.name)
    +'<span class="hongchen-status '+st.cls+'">'+st.label+'</span></div>'
    +(q.desc?'<p class="hongchen-inspect-desc">'+esc(q.desc)+'</p>':'')
    +'<div class="hongchen-inspect-grid">'
    +'<div class="hongchen-ir"><b>所在环</b><span>第 '+(q.depth||1)+' 环</span></div>'
    +'<div class="hongchen-ir"><b>前置</b><span>'+(q.prev&&map[q.prev]?esc(map[q.prev].name):'无（起点）')+'</span></div>'
    +'<div class="hongchen-ir"><b>后续</b><span>'+(next||'无')+'</span></div>'
    +'<div class="hongchen-ir"><b>分支</b><span>'+(q.branch?(esc((q.branch_with||[]).join(' / '))||'互斥选项'):'否')+'</span></div>'
    +(q.fail_text?'<div class="hongchen-ir full"><b>进度提示</b><span>'+esc(q.fail_text)+'</span></div>':'')
    +'</div>'
    +(gates.length?'<div class="hongchen-igates"><b>选项门槛</b>'+gates.map(g=>'<span class="hongchen-badge gate">'+esc(g)+'</span>').join('')+'</div>':'')
    +'</div>';
}

function panelHtml(line){
  const selected=(line.quests||[]).filter(q=>CUR===q.id)[0];
  return '<div class="hongchen-panel" style="--hongchen-accent:'+esc(line.color||'#c9866b')+'">'
    +'<div class="hongchen-panel-head"><div><b>'+esc(line.name)+'</b> · 任务树'
    +'<span class="hongchen-panel-sum">'+esc(line.group)+' ｜ 共 '+(line.progress?line.progress.total:0)+' 环'
    +'，已走 '+(line.progress?line.progress.done:0)+'</span></div><button type="button" class="hongchen-close" title="收起">×</button></div>'
    +'<div class="hongchen-toolbar"><span class="hongchen-chipset">'
    +FILTERS.map(f=>'<button type="button" class="hongchen-chip'+(FILTER===f[0]?' active':'')+'" data-filter="'+f[0]+'">'+f[1]+'</button>').join('')
    +'</span><input class="hongchen-search" type="search" placeholder="搜索任务名 / 编号" value="'+esc(QUERY)+'"></div>'
    +'<div class="hongchen-tree-wrap"'+(QUERY?' data-searching="1"':'')+'>'+treeHtml(line)+'</div>'
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
      +'<span class="hongchen-cardmeta">'+(p.done||0)+'/'+(p.total||0)+' 已完成 · '+(p.ready||0)+' 可接取'
      +(p.missed?' · '+p.missed+' 错过':'')+'</span></span>'
      +'<span class="hongchen-ring">'+ring(p.pct||0,line.color)+'</span>'
      +'<span class="hongchen-arrow">›</span></button>';
  }).join('');
  const line=LINES.filter(l=>l.group===OPEN)[0];
  host.innerHTML='<div class="hongchen-root">'
    +'<div class="hongchen-head"><div><div class="hongchen-title">红尘 · 六段情缘</div>'
    +'<div class="hongchen-sub">'+stats.quests+' 段任务 · '+stats.lines+' 条角色线 · 选项门槛已标注，hover 查看详情</div></div>'
    +'<div class="hongchen-legend">'
    +'<span><i class="hongchen-dot s-done"></i>已完成</span><span><i class="hongchen-dot s-doing"></i>进行中</span>'
    +'<span><i class="hongchen-dot s-ready"></i>可接取</span><span><i class="hongchen-dot s-missed"></i>已错过</span>'
    +'<span><i class="hongchen-dot s-locked"></i>条件不足</span></div></div>'
    +'<div class="hongchen-cards">'+cards+'</div>'
    +(line?panelHtml(line):'<div class="hongchen-empty-hint">选择一位角色，展开她的情缘任务树</div>')
    +'</div>';
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
  render(host,stats);

  host.addEventListener('click',function(e){
    const card=e.target.closest('.hongchen-card');
    if(card){const g=card.getAttribute('data-group');OPEN=(OPEN===g?'':g);CUR=null;
      store.set('hongchen.open',OPEN);render(host,stats);return}
    const chip=e.target.closest('.hongchen-chip');
    if(chip){FILTER=chip.getAttribute('data-filter');store.set('hongchen.filter',FILTER);render(host,stats);return}
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
      const match=!QUERY||String(q.name).toLowerCase().indexOf(QUERY)>=0||String(q.id).indexOf(QUERY)>=0;
      el.classList.toggle('dim',!match||(FILTER!=='all'&&q.status_cls!==FILTER));
    });
  });
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS.hongchen=init;
})();
