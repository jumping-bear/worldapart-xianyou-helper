/* 红尘：角色卡 + 环进度轴导航 + 聚焦当前环的任务树（IIFE，导出 window.PROGRESS_VIEWS.hongchen）
 * 交互：顶部进度轴可点击跳转到任意环；主体只展开“聚焦环”，通过上一环/下一环与
 *       相邻环快捷芯片步进，避免几十环横向铺开需要一路拖拽。
 */
(function(){
const KEY='hongchen';
const STATUS={
  done:{label:'已完成',cls:'s-done'}, doing:{label:'进行中',cls:'s-doing'},
  ready:{label:'可接取',cls:'s-ready'}, unpicked:{label:'另一条路',cls:'s-unpicked'},
  skipped:{label:'已跳过',cls:'s-skipped'},
  locked:{label:'未解锁',cls:'s-locked'}, notstarted:{label:'未开始',cls:'s-notstarted'}
};
// 过滤项 value 对应状态类；'cando' 合并“可接取 + 未开始(可开启分支)”。
const FILTERS=[['all','全部'],['cando','可做'],['doing','进行中'],['done','已完成'],
               ['notstarted','未开始'],['unpicked','另一条路'],['skipped','已跳过'],['locked','未解锁']];
let LINES=[], OPEN='', FILTER='all', QUERY='', CUR=null, REMAIN=true, STATS={};

function statusOf(cls){return STATUS[cls]||STATUS.notstarted}
function byId(line){const m={};(line.quests||[]).forEach(q=>m[q.id]=q);return m}
function ringOf(q){return Number(q.depth)||1}
// 女主此刻在哪：来自存档实时位置，不在存档就直说“不在当前世界”，不拿常驻地冒充。
function placeText(line){
  const loc=line.location||{};
  if(!loc.present)return '不在当前世界';
  const label=loc.path||loc.name||'位置未知';
  return (loc.gone?'已退隐 · ':'在 ')+label;
}

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
  if(FILTER==='cando')return q.status_cls==='ready';
  return q.status_cls===FILTER;
}
function matchQuery(q){
  if(!QUERY)return true;
  return String(q.name).toLowerCase().indexOf(QUERY)>=0||String(q.id).indexOf(QUERY)>=0;
}
function isDim(q){return !matchFilter(q)||!matchQuery(q)}

function gateBadges(q){
  const out=[];
  (q.gates||[]).forEach(g=>{
    if(!g||!g.text)return;
    // 任务依赖型前置由树的连线和详情表达，节点上不再重复堆「已提交过主线…」。
    if(g.kind==='quest'||g.kind==='quest_option')return;
    out.push('<span class="hongchen-badge gate" title="'+esc(g.source==='optionCondition'?'选项门槛（游戏里可能不提示）':'门槛')+'">'+esc(g.text)+'</span>');
  });
  return out.length?'<div class="hongchen-badges">'+out.join('')+'</div>':'';
}

function nodeOptions(q){
  const opts=q.options||[];
  if(!opts.length)return '';
  const shown=opts.slice(0,4);
  return '<div class="hongchen-node-opts">'+shown.map(o=>{
    const chk=(o&&o.check)||{};
    const cls=chk.ok===true?' ok':(chk.ok===false?' no':'');
    const gate=o.gate&&o.gate.text?'<em>'+esc(o.gate.text)+'</em>':'';
    return '<div class="hongchen-node-opt'+cls+'" title="'+esc(o.text||'')+(o.gate&&o.gate.text?' · 需 '+esc(o.gate.text):'')+'">'
      +'<span>'+esc(o.text||'—')+'</span>'+gate+'</div>';
  }).join('')
    +(opts.length>shown.length?'<div class="hongchen-node-opt more">还有 '+(opts.length-shown.length)+' 个选项，点开看</div>':'')
    +'</div>';
}

function nodeHtml(q,map,step){
  const st=statusOf(q.status_cls);
  const dim=isDim(q)?' dim':'';
  const sel=(CUR===q.id)?' sel':'';
  const prev=(q.prev&&map[q.prev])?map[q.prev].name:'';
  // 分支任务用“N 选 1”提示，未选的那条写成“另一条路”，绝不写“已错过”。
  let foot=q.status_cls==='skipped'?'孤立节点 · 剧情已越过'
    :((q.branch?'分支 · ':'')+(prev?'前置「'+esc(prev)+'」':'起点'));
  if(q.hidden)foot+=' · 隐藏';
  let note='';
  if((q.status_cls==='unpicked'||q.status_cls==='skipped')&&q.fail_text)
    note='<div class="hongchen-node-note">'+esc(q.fail_text)+'</div>';
  return '<div class="hongchen-node '+st.cls+dim+sel+'" data-qid="'+q.id+'" data-ring="'+ringOf(q)+'" title="'+esc(q.desc||q.name)+'">'
    +'<div class="hongchen-node-top"><span class="hongchen-id">#'+q.id+'</span>'
    +'<span class="hongchen-ringtag">'+(step?'第 '+step+' 步':'第 '+ringOf(q)+' 环')+'</span>'
    // 未开始的任务不写状态字，避免一屏全是「未开始」；状态仍靠颜色区分。
    +'<span class="hongchen-status">'+(q.status_cls==='notstarted'?'':st.label)+'</span></div>'
    +'<div class="hongchen-nname">'+esc(q.name)+'</div>'
    +(q.desc?'<div class="hongchen-desc">'+esc(q.desc)+'</div>':'')
    +note+gateBadges(q)+nodeOptions(q)
    +'<div class="hongchen-node-foot">'+foot+'</div></div>';
}

// 按真实前置关系画树：根任务在最左，后续任务逐级缩进，分支并列。
// 数据全来自 prev 与分支组，游戏后续新增任务只需重导快照即可正确成树。
function treeHtml(line,only,steps){
  const map=byId(line);
  const children={};
  (line.quests||[]).forEach(q=>{
    if(only&&!only[q.id])return;
    const p=(q.prev&&map[q.prev]&&(!only||only[q.prev]))?q.prev:0;
    (children[p]=children[p]||[]).push(q);
  });
  const seen={};
  const levelOf=d=>Math.min(d,6);
  function renderFrom(parentId,depth){
    const kids=(children[parentId]||[]).filter(q=>!seen[q.id]);
    if(!kids.length)return '';
    const groups=[], groupMap={};
    kids.forEach(q=>{
      const key=q.branch_key||('solo:'+q.id);
      if(!groupMap[key]){groupMap[key]=[];groups.push(groupMap[key]);}
      groupMap[key].push(q);
    });
    let html='';
    groups.forEach(group=>{
      if(group.length>1){
        html+='<div class="hongchen-tree-branch" style="--lv:'+levelOf(depth)+'">'
          +'<span class="hongchen-tree-fork">⑂ 分支 '+group.length+' 选 1</span>'
          +'<div class="hongchen-node-grid">'+group.map(q=>{seen[q.id]=1;return nodeHtml(q,map,steps&&steps[q.id])}).join('')+'</div></div>';
        group.forEach(q=>{html+=renderFrom(q.id,depth+1)});
      }else{
        const q=group[0];
        seen[q.id]=1;
        html+='<div class="hongchen-tree-lv" style="--lv:'+levelOf(depth)+'">'+nodeHtml(q,map,steps&&steps[q.id])+'</div>';
        html+=renderFrom(q.id,depth+1);
      }
    });
    return html;
  }
  let html=renderFrom(0,0);
  // 兜底：prev 指向线外任务或形成环时，单独列出来，绝不静默丢任务。
  const rest=(line.quests||[]).filter(q=>!seen[q.id]&&(!only||only[q.id]));
  if(rest.length){
    html+='<div class="hongchen-tree-loose"><div class="hongchen-tree-fork">未挂到主线的任务</div>'
      +'<div class="hongchen-node-grid">'+rest.map(q=>{seen[q.id]=1;return nodeHtml(q,map,steps&&steps[q.id])}).join('')+'</div></div>';
  }
  return html;
}

// 一条角色线里其实有多条互不相连的任务链。玩家能理解的是“故事线 + 第几步”，
// 而不是抽象的第 N 环；所以按根任务拆成故事线，各自从第 1 步开始编号。
function chainsOf(line){
  const map=byId(line), kids={}, all=[];
  (line.quests||[]).forEach(q=>{
    const p=(q.prev&&map[q.prev])?q.prev:0;
    (kids[p]=kids[p]||[]).push(q); all.push(q);
  });
  const seen={};
  function walk(q){
    const out=[q]; seen[q.id]=1;
    (kids[q.id]||[]).forEach(c=>{if(!seen[c.id])out.push.apply(out,walk(c))});
    return out;
  }
  const chains=(kids[0]||[]).map(r=>({root:r,nodes:walk(r)}));
  const loose=all.filter(q=>!seen[q.id]);
  if(loose.length)chains.push({root:null,nodes:loose,loose:true});
  chains.forEach(c=>{
    c.branchOnly=c.nodes.length>0&&c.nodes.every(n=>n.branch);
    c.done=c.nodes.filter(n=>n.status_cls==='done').length;
    c.total=c.nodes.length;
    c.next=c.nodes.filter(n=>n.status_cls==='doing')[0]||c.nodes.filter(n=>n.status_cls==='ready')[0]||null;
    const cls=c.nodes.map(n=>n.status_cls);
    c.status=cls.indexOf('doing')>=0?'doing'
      :(cls.indexOf('ready')>=0?'ready'
      :(c.done?'done':(cls.indexOf('locked')>=0?'locked':'notstarted')));
    c.title=c.root?c.root.name:(c.loose?'未挂到故事线的任务':'故事线');
    c.step={}; c.nodes.forEach((n,i)=>{c.step[n.id]=i+1});
  });
  return chains;
}

function storyStatusText(c){
  if(c.status==='done')return c.done===c.total?'已完成':'已走过 '+c.done+' 步';
  if(c.status==='doing')return '进行中';
  if(c.status==='ready')return '可接取';
  if(c.status==='locked')return '差条件';
  return '未开始';
}

function storySection(c,open){
  const st=statusOf(c.status);
  const ids={}; c.nodes.forEach(n=>{ids[n.id]=1});
  const next=c.next?'<div class="hongchen-story-next">下一步：<b>'+esc(c.next.name)+'</b></div>':'';
  return '<details class="hongchen-story'+(c.branchOnly?' is-branch':'')+'" data-chain="'+(c.root?c.root.id:'loose')+'"'
    +(open?' open':'')+'>'
    +'<summary><span class="hongchen-dot '+st.cls+'"></span>'
    +'<span class="hongchen-story-name">'+esc(c.title)+'</span>'
    +'<span class="hongchen-story-meta">'+c.done+'/'+c.total+' 步 · '+storyStatusText(c)+'</span></summary>'
    +'<div class="hongchen-story-body">'+next+'<div class="hongchen-tree">'+treeHtml(c.line,ids,c.step)+'</div></div></details>';
}

function storiesHtml(line){
  const chains=chainsOf(line);
  const mains=chains.filter(c=>!c.branchOnly), branches=chains.filter(c=>c.branchOnly);
  // 默认展开有进度的故事线；都没有进度时展开第一条，其余收起，避免一屏铺满几十个未开始任务。
  const active=mains.filter(c=>['doing','ready'].indexOf(c.status)>=0)[0]||mains[0]||null;
  let html='<div class="hongchen-stories">';
  mains.forEach(c=>{c.line=line;html+=storySection(c,c===active)});
  if(branches.length){
    const body=branches.map(c=>{
      c.line=line;
      const ids={}; c.nodes.forEach(n=>{ids[n.id]=1});
      return '<div class="hongchen-story-branchbox"><div class="hongchen-branch-label">'
        +(c.nodes.length>1?'分支 '+c.nodes.length+' 选 1（'+esc(c.title)+'）':esc(c.title))+'</div>'
        +'<div class="hongchen-node-grid">'+c.nodes.map(n=>nodeHtml(n,byId(line),c.step[n.id])).join('')+'</div></div>';
    }).join('');
    html+='<details class="hongchen-story is-branch" data-chain="branch"><summary>'
      +'<span class="hongchen-dot s-unpicked"></span><span class="hongchen-story-name">对话分支</span>'
      +'<span class="hongchen-story-meta">'+branches.length+' 组 · 二选一</span></summary>'
      +'<div class="hongchen-story-body">'+body+'</div></details>';
  }
  return html+'</div>';
}

// 「还差什么」：展开面板最上方，先给结论（下一步 + 各类数量），细节按需展开。
// 计数按钮直接筛选下方任务树；chip 点击跳到对应节点；分支另列"当时选了另一条路"。
function remainHtml(line){
  const r=line.remaining;
  if(!r)return '';
  const count=cls=>{
    if(cls==='ready')return (r.ready||[]).length;
    if(cls==='doing')return (r.doing||[]).length;
    if(cls==='notstarted')return (r.notstarted||[]).length;
    return (r.locked||[]).length;
  };
  const chips=(items,cls,showWhy)=>'<div class="hongchen-remain-list">'
    +items.map(it=>'<button type="button" class="hongchen-remain-chip '+cls+'" data-jump="'+it.id
      +'" title="'+esc(it.name)+(it.reason?' · '+esc(it.reason):'')+'">'
      +'<span class="hongchen-remain-name">'+esc(it.name)+'</span>'
      +(showWhy&&it.reason?'<span class="hongchen-remain-why">'+esc(it.reason)+'</span>':'')
      +'</button>').join('')
    +'</div>';
  const fold=(title,cls,items,showWhy)=>{
    if(!items||!items.length)return '';
    // 未开始通常很多，默认折叠；差条件也只给看一眼，不占首屏。
    return '<details class="hongchen-remain-sec hongchen-remain-fold">'
      +'<summary class="hongchen-remain-t"><i class="hongchen-dot '+cls+'"></i>'+title
      +'<em>'+items.length+'</em></summary>'
      +chips(items,cls,showWhy)+'</details>';
  };

  const counts=[['ready','可接取','s-ready'],['doing','进行中','s-doing'],
                ['notstarted','未开始','s-notstarted'],['locked','差条件','s-locked']]
    .filter(x=>count(x[0])>0)
    .map(x=>'<button type="button" class="hongchen-remain-count '+x[2]+'" data-filter="'+x[0]
      +'" title="只显示'+x[1]+'的任务">'+x[1]+'<em>'+count(x[0])+'</em></button>').join('');

  const p0=line.progress||{};
  const idle=!((p0.done||0)+(p0.doing||0)) && !(r.ready&&r.ready.length);
  const next=(!idle&&r.next)?('<button type="button" class="hongchen-remain-next" data-jump="'+r.next.id
    +'" title="跳到这个任务"><span>下一步</span><b>'+esc(r.next.name)+'</b>'
    +(r.next.why?'<em>'+esc(r.next.why)+'</em>':'')+'</button>'):'';

  const ready=r.ready&&r.ready.length
    ?'<div class="hongchen-remain-sec is-ready"><div class="hongchen-remain-t">'
      +'<i class="hongchen-dot s-ready"></i>可接取<em>'+r.ready.length+'</em>'
      +'<span class="hongchen-remain-flag">现在就能做</span></div>'+chips(r.ready,'s-ready',false)+'</div>'
    :'';

  let alts='';
  const choices=r.choices||[];
  if(choices.length){
    alts='<div class="hongchen-remain-sec hongchen-remain-alts">'
      +'<div class="hongchen-remain-t"><i class="hongchen-dot s-unpicked"></i>当时选了另一条路'
      +'<em>'+choices.length+'</em></div>'
      +'<div class="hongchen-remain-tip">'+esc(r.choice_note||'')+'</div>'
      +'<div class="hongchen-remain-choice-list">'
      +choices.map(c=>{
        const fork=c.parent_id
          ?'<button type="button" class="hongchen-remain-fork" data-jump="'+c.parent_id
            +'" title="第 '+c.depth+' 环 · 跳到这个分叉点">'+esc(c.text)+'</button>'
          :'<span class="hongchen-remain-fork is-plain">'+esc(c.text)+'</span>';
        return '<div class="hongchen-remain-choice">'+fork+'</div>';
      }).join('')
      +'</div></div>';
  }

  const empty=(!ready&&!choices.length&&!count('doing')&&!count('notstarted')&&!count('locked'))
    ?'<div class="hongchen-remain-all">✓ 这条线已走完</div>':'';
  const sum=r.done?'这条线已走完':(idle?'尚未开启':('还差 '+r.left+' 项'));
  return '<div class="hongchen-remain'+(REMAIN?'':' is-fold')+'">'
    +'<div class="hongchen-remain-head"><span class="hongchen-remain-title">还差什么</span>'
    +'<span class="hongchen-remain-sum'+(r.done?' is-done':'')+'">'+esc(sum)+'</span>'
    +'<button type="button" class="hongchen-remain-toggle">'+(REMAIN?'收起':'展开')+'</button></div>'
    +'<div class="hongchen-remain-body">'
    +(counts?'<div class="hongchen-remain-counts">'+counts+'</div>':'')
    +next+empty+ready
    +fold('进行中','s-doing',r.doing,false)
    +fold('未开始','s-notstarted',r.notstarted,false)
    +fold('差条件','s-locked',r.locked,true)
    +alts
    +'</div></div>';
}

// 「怎么触发」：直接回答"这任务怎么来"——方式 + 可跳转的前置 + 人话条件。
// 未选分支/已跳过节点同样显示，让人一眼看出是被剧情越过，而不是卡了 bug。
function triggerHtml(q,line){
  const map=byId(line);
  const src=Number(q.acq_source||0);
  const giver=(q.giver&&q.giver.name)||'';
  const byNpc=(src===1)||(src!==2&&!!giver);
  const way=byNpc?(giver?('与「'+giver+'」对话接取'):'与剧情人物对话接取')
                 :'自动触发（剧情推进时出现）';
  let prevHtml='';
  if(q.prev){
    const p=map[q.prev];
    prevHtml=p?('先完成 <button type="button" class="hongchen-jump" data-jump="'+p.id
        +'" title="跳到「'+esc(p.name)+'」">'+esc(p.name)+'</button>'
        +'<em class="hongchen-tr-state '+statusOf(p.status_cls).cls+'">'+statusOf(p.status_cls).label+'</em>')
      :'先走完上一段剧情';
  }
  const conds=(q.gates||[]).filter(g=>g&&g.text).map(g=>esc(g.text));
  return '<div class="hongchen-trigger">'
    +'<div class="hongchen-tr"><b>怎么触发</b><span>'+esc(way)+'</span></div>'
    +(prevHtml?'<div class="hongchen-tr"><b>前置</b><span>'+prevHtml+'</span></div>':'')
    +(conds.length?'<div class="hongchen-tr"><b>条件</b><span>'+conds.join('、')+'</span></div>':'')
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
    :(q.status_cls==='skipped'
      ?'<div class="hongchen-inspect-note is-skipped">这条分支在本档已跳过：它与同线其它任务没有关联，且剧情已经推进到更后面的环，游戏里不会再出现。</div>'
      :(q.status_cls==='notstarted'?'<div class="hongchen-inspect-note">前置剧情还没走到，先推进前面的任务吧。</div>':''));
  return '<div class="hongchen-inspect"><div class="hongchen-inspect-title">'
    +'<span class="hongchen-id">#'+q.id+'</span>'+esc(q.name)
    +'<span class="hongchen-status '+st.cls+'">'+st.label+'</span></div>'
    +triggerHtml(q,line)
    +(q.desc?'<p class="hongchen-inspect-desc">'+esc(q.desc)+'</p>':'')
    +notice
    +'<div class="hongchen-inspect-grid">'

    +'<div class="hongchen-ir"><b>前置</b><span>'+(q.prev&&map[q.prev]?esc(map[q.prev].name):'无（起点）')+'</span></div>'
    +'<div class="hongchen-ir"><b>后续</b><span>'+(next||'无')+'</span></div>'
    +'<div class="hongchen-ir"><b>分支</b><span>'+(q.branch?(esc((q.branch_with||[]).join(' / '))||'互斥选项'):'否')+'</span></div>'
    +(q.fail_text?'<div class="hongchen-ir full"><b>进度提示</b><span>'+esc(q.fail_text)+'</span></div>':'')
    +'</div>'
    +(gates.length?'<div class="hongchen-igates"><b>选项门槛</b>'+gates.map(g=>{
        const cls=g.ok===true?' ok':(g.ok===false?' no':'');
        let val='';
        if(g.kind==='quest'){
          // 任务门槛：显示「已提交过主线「探访云嫣」 · 已提交 ✓」，不再写裸状态码。
          const mark=g.ok===true?'✓':(g.ok===false?'✗':'');
          val=' · '+(g.cur||'未接取')+(mark?' '+mark:'');
        }else{
          const haveCur=(g.cur!==undefined&&g.cur!==null&&g.cur!=='');
          const haveNeed=(g.need!==undefined&&g.need!==null&&g.need!=='');
          if(haveCur||haveNeed){
            val='当前 '+(haveCur?g.cur:'?')+' / 需 '+(haveNeed?g.need:'?');
            const state=g.ok===true?'已满足':(g.ok===false?'未满足':'');
            if(state)val+=' · '+state;
          }
        }
        return '<span class="hongchen-badge gate'+cls+'">'+esc(g.text)
          +(val?'<em class="hongchen-gate-val">'+esc(val)+'</em>':'')+'</span>';
      }).join('')+'</div>':'')
    +'</div>';
}

// 开启条件后面带上“当前值”，玩家不用自己翻存档核对。
function openText(line){
  const o=line.open||{};
  if(!o.text)return '';
  const ck=o.check||{};
  return '开启：'+o.text+(ck.desc?'（'+ck.desc+'）':'');
}

function panelHtml(line){
  const selected=(line.quests||[]).filter(q=>CUR===q.id)[0];
  const p=line.progress||{};
  const started=(p.done||0)+(p.doing||0)>0;
  const headline=p.headline||((p.done||0)+'/'+(p.base||0)+' 已完成');
  return '<div class="hongchen-panel" style="--hongchen-accent:'+esc(line.color||'#c9866b')+'">'
    +'<div class="hongchen-panel-head"><div><b>'+esc(line.name)+'</b> · 情缘任务线'
    +'<span class="hongchen-panel-place'+((line.location&&line.location.gone)?' is-gone':'')
    +((line.location&&line.location.present)?'':' is-away')+'" title="存档里的实时位置">'
    +esc(placeText(line))+'</span>'
    +((line.open&&line.open.text)?'<span class="hongchen-panel-open" title="整条线的开启条件">'+esc(openText(line))+'</span>':'')
    +'<span class="hongchen-panel-sum">'+esc(headline)+'</span></div>'
    +'<button type="button" class="hongchen-close" title="收起">×</button></div>'
    +remainHtml(line)
    +(started?'':'<div class="hongchen-line-notice">这条线还没开启：目前没有可接取的任务。等剧情推进或与她结识后，这里会自动更新；下面的节点仍可查看。</div>')
    +'<div class="hongchen-toolbar"><span class="hongchen-chipset">'
    +FILTERS.map(f=>'<button type="button" class="hongchen-chip'+(FILTER===f[0]?' active':'')+'" data-filter="'+f[0]+'">'+f[1]+'</button>').join('')
    +'</span><input class="hongchen-search" type="search" placeholder="搜索任务名 / 编号" value="'+esc(QUERY)+'"></div>'
    +'<div class="hongchen-guide">任务按真实前置关系分组：每条故事线从第一个任务开始按顺序展开，第 N 步表示在这条线里的位置，⑂ 处是二选一的分支。'
    +'<span class="hongchen-guide-more">点故事线标题展开或收起；有进度的线会默认展开。</span></div>'
    +storiesHtml(line)
    +'<div class="hongchen-hint">点任务节点即可展开详情，详情就显示在这个节点下方，页面不会跳走。</div>'
    +'</div>';
}

function render(host,stats){
  const cards=LINES.map(line=>{
    const p=line.progress||{}, active=OPEN===line.group;
    const started=(p.done||0)+(p.doing||0)>0;
    const portrait=line.avatar?'<img src="'+esc(line.avatar)+'" alt="" loading="lazy">'
      :'<span>'+esc((line.name||'?').slice(0,1))+'</span>';
    return '<button type="button" class="hongchen-card'+(active?' active':'')+'" data-group="'+esc(line.group)
      +'" style="--hongchen-accent:'+esc(line.color||'#c9866b')+'">'
      +'<span class="hongchen-portrait">'+portrait+'</span>'
      +'<span class="hongchen-cinfo"><span class="hongchen-name">'+esc(line.name)+'</span>'
      +'<span class="hongchen-place'+((line.location&&line.location.gone)?' is-gone':'')
      +((line.location&&line.location.present)?'':' is-away')+'" title="存档里的实时位置">'
      +esc(placeText(line))+'</span>'
      +'<span class="hongchen-cardmeta">'+(started
        ?('已完成 '+(p.done||0)+'/'+(p.base||p.total||0)+(p.ready?' · <b class="hongchen-ready-count">可接取 '+p.ready+'</b>':''))
        :('尚未开启 · 共 '+(p.base||p.total||0)+' 个节点'))+'</span>'
      +((!started&&line.open&&line.open.text)?'<span class="hongchen-cardmeta hongchen-cardopen">'+esc(openText(line))+'</span>':'')
      +'<span class="hongchen-cardmeta hongchen-cardleft'+((line.remaining&&line.remaining.done)?' is-done':'')+'">'
      +esc((line.remaining&&line.remaining.brief)||'')+'</span></span>'
      +'<span class="hongchen-ring">'+ring(p.pct||0,line.color)+'</span>'
      +'<span class="hongchen-arrow">›</span></button>';
  }).join('');
  const line=LINES.filter(l=>l.group===OPEN)[0];
  host.innerHTML='<div class="hongchen-root">'
    +'<div class="hongchen-head"><div><div class="hongchen-title">红尘 · 六段情缘</div>'
    +'<div class="hongchen-sub">'+stats.quests+' 段任务 · '+stats.lines+' 条角色线 · 展开某人按顺序看完整条线</div></div>'
    +'<div class="hongchen-legend">'
    +'<span><i class="hongchen-dot s-done"></i>已完成</span><span><i class="hongchen-dot s-doing"></i>进行中</span>'
    +'<span><i class="hongchen-dot s-ready"></i>可接取</span>'
    +'<span><i class="hongchen-dot s-unpicked"></i>另一条路</span><span><i class="hongchen-dot s-skipped"></i>已跳过</span>'
    +'<span><i class="hongchen-dot s-locked"></i>未解锁</span></div></div>'
    +'<div class="hongchen-cards">'+cards+'</div>'
    +(line?panelHtml(line):'<div class="hongchen-empty-hint">选择一位角色，展开她的情缘任务树</div>')
    +'</div>';
}

// 故事线默认是收起的；跳转到某个任务前先把包含它的那条线展开。
function openStoryFor(host,qid){
  host.querySelectorAll('details.hongchen-story').forEach(function(d){
    if(!qid||d.querySelector('.hongchen-node[data-qid="'+qid+'"]'))d.open=true;
  });
}

// 详情就地展开在节点下方，不整页重绘、不跳页。
function toggleInspect(host,qid){
  openStoryFor(host,qid);
  const line=LINES.filter(l=>l.group===OPEN)[0];if(!line)return;
  host.querySelectorAll('.hongchen-node.sel').forEach(el=>el.classList.remove('sel'));
  const old=host.querySelector('.hongchen-inspect-inline');
  if(old)old.remove();
  if(CUR===qid){CUR=null;return}
  const q=byId(line)[qid];if(!q)return;
  const node=host.querySelector('.hongchen-node[data-qid="'+qid+'"]');if(!node)return;
  CUR=qid;
  node.classList.add('sel');
  const box=document.createElement('div');
  box.className='hongchen-inspect-inline';
  box.innerHTML=inspectHtml(q,line);
  const anchor=node.closest('.hongchen-tree-lv')||node.closest('.hongchen-tree-branch')||node;
  anchor.insertAdjacentElement('afterend',box);
}

// 跳到指定任务节点：选中并就地展开详情。
function jumpTo(host,stats,qid){
  const line=LINES.filter(l=>l.group===OPEN)[0]; if(!line)return;
  const q=(line.quests||[]).filter(x=>x.id===qid)[0]; if(!q)return;
  CUR=null; render(host,stats);
  setTimeout(function(){openStoryFor(host,qid);toggleInspect(host,qid)},30);
}

function init(){
  const host=$('hongchen'); if(!host)return;
  const m=DATA.modules&&DATA.modules.hongchen;
  const payload=(m&&m.rows)||{};
  LINES=payload.rows||[];
  STATS=payload.stats||{};
  const stats=STATS;
  if(!LINES.length){
    host.innerHTML=sourceHtml(m||{})+'<div class="hongchen-empty">暂无红尘任务配置</div>';return;
  }
  OPEN=store.get('hongchen.open',''); FILTER=store.get('hongchen.filter','all');
  if(!LINES.some(l=>l.group===OPEN))OPEN='';
  const line0=LINES.filter(l=>l.group===OPEN)[0];
  render(host,stats);
  if(line0)setTimeout(function(){
    const cur=host.querySelector('.hongchen-sec.is-current');
    if(cur&&cur.scrollIntoView)cur.scrollIntoView({block:'start'});
  },60);

  host.addEventListener('click',function(e){
    const card=e.target.closest('.hongchen-card');
    if(card){const g=card.getAttribute('data-group');OPEN=(OPEN===g?'':g);CUR=null;
      store.set('hongchen.open',OPEN);render(host,stats);
      if(OPEN)setTimeout(function(){
        const cur=host.querySelector('.hongchen-sec.is-current');
        if(cur&&cur.scrollIntoView)cur.scrollIntoView({behavior:'smooth',block:'start'});
      },60);
      return}
    const chip=e.target.closest('.hongchen-chip');
    if(chip){FILTER=chip.getAttribute('data-filter');store.set('hongchen.filter',FILTER);render(host,stats);return}
    const remainCount=e.target.closest('.hongchen-remain-count');
    if(remainCount){FILTER=remainCount.getAttribute('data-filter');store.set('hongchen.filter',FILTER);render(host,stats);return}
    const toggle=e.target.closest('.hongchen-remain-toggle');
    if(toggle){REMAIN=!REMAIN;const box=toggle.closest('.hongchen-remain');
      if(box)box.classList.toggle('is-fold',!REMAIN);toggle.textContent=REMAIN?'收起':'展开';return}
    const jump=e.target.closest('[data-jump]');
    if(jump){jumpTo(host,stats,Number(jump.getAttribute('data-jump')));return}
    const node=e.target.closest('.hongchen-node');
    if(node){toggleInspect(host,Number(node.getAttribute('data-qid')));return}
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
// 供境界修为的「红尘页」按钮直接定位到某个任务。
window.PROGRESS_GOTO_hongchen=function(needle){
  const name=String(needle||'').trim();
  if(!name)return false;
  let line=null, quest=null;
  LINES.forEach(function(l){
    (l.quests||[]).forEach(function(q){
      if(quest||q.name!==name)return;
      line=l; quest=q;
    });
  });
  if(!quest)LINES.forEach(function(l){
    (l.quests||[]).forEach(function(q){
      if(quest||String(q.name).indexOf(name)<0)return;
      line=l; quest=q;
    });
  });
  if(!quest)return false;
  const host=$('hongchen');
  if(!host)return false;
  OPEN=line.group; CUR=null; QUERY=''; FILTER='all';
  REMAIN=true;
  store.set('hongchen.open',OPEN); store.set('hongchen.filter',FILTER);
  render(host,STATS);
  setTimeout(function(){
    openStoryFor(host,quest.id);
    toggleInspect(host,quest.id);
    const node=host.querySelector('.hongchen-node[data-qid="'+quest.id+'"]');
    if(node&&node.scrollIntoView)node.scrollIntoView({behavior:'smooth',block:'center'});
  },60);
  return true;
};
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS.hongchen=init;
})();
