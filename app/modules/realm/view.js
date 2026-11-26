/* 境界修为：当前进度、突破清单与材料获取图鉴。 */
(function(){
var KEY='worldapart.realm.v1';
var state=Object.assign({q:'',filter:'all',realm:0,expandAll:0,aux:{}},store.get(KEY,{}));
function save(){store.set(KEY,state)}
function qcls(q){return qClass(q,'q')}
function pctText(value){return Math.round(Number(value)||0)+'%'}
function fmtYears(days,years){
  var y=Number(years)||0,d=Number(days)||0;
  if(!d)return '—';
  if(y>=1)return (y>=10?Math.round(y):y.toFixed(1))+' 年（'+d+' 天）';
  return d+' 天';
}
var KIND={official:'官方',quest:'任务',monster:'妖兽',auction:'拍卖',tournament:'赛事',worldboss:'镇劫',explore:'秘宝',shop:'商店',event:'奇遇',steal:'偷窃',unknown:'缺来源'};
var SPAWNED={};
var CONFTIP={official:'游戏内标注的获取途径',derived:'由掉落表反推的获取途径',mechanic:'机制可行，但需要 NPC 恰好持有',none:'配置里没有正常获取途径'};
var MOD_LABEL={quest:'任务页',hongchen:'红尘页',event:'奇遇页'};
var MOD_PAGE={quest:'任务',hongchen:'红尘',event:'奇遇'};

function srcChip(s){
  var detail=s.detail?`<em>${esc(s.detail)}</em>`:'';
  var state=s.state_name?`<span class="st st-${s.state}">${esc(s.state_name)}</span>`:'';
  var mod=s.link_module||'quest';
  var jump=s.link&&s.quest_name?`<button type="button" class="rsrc-jump" data-quest="${esc(s.quest_name)}" data-module="${esc(mod)}" title="到${MOD_PAGE[mod]||'任务'}页查看「${esc(s.quest_name)}」">${MOD_LABEL[mod]||'任务页'}</button>`:'';
  return `<span class="rsrc k-${s.kind} c-${s.conf||'derived'}" title="${esc(CONFTIP[s.conf]||'')}">`+
    `<i>${KIND[s.kind]||'来源'}</i>${esc(s.label||'')}${detail}${state}${jump}</span>`;
}
function groupSources(sources,skipSteal){
  var groups={},order=[];
  (sources||[]).forEach(function(s){
    if(s.kind==='steal'&&skipSteal)return;
    if(s.kind==='unknown')return;
    var key=s.kind+'|'+s.label;
    if(!groups[key]){groups[key]={kind:s.kind,label:s.label,conf:s.conf,details:[],state:s.state,state_name:s.state_name,quest:s.quest,quest_name:s.quest_name,link:s.link,link_module:s.link_module};order.push(key)}
    if(s.detail&&groups[key].details.indexOf(s.detail)<0)groups[key].details.push(s.detail);
  });
  return order.map(function(key){
    var g=groups[key];
    var detail=g.details.length>2?g.details.slice(0,2).join('、')+' 等 '+(g.details.length)+' 项':g.details.join('、');
    return srcChip({kind:g.kind,label:g.label,detail:detail,conf:g.conf,state:g.state,state_name:g.state_name,quest:g.quest,quest_name:g.quest_name,link:g.link,link_module:g.link_module});
  }).join('');
}
function uniqLabels(sources,kinds){
  var seen={},out=[];
  (sources||[]).forEach(function(s){
    if(kinds&&kinds.indexOf(s.kind)<0)return;
    var text=s.label||'';if(!text||seen[text])return;seen[text]=1;out.push(text);
  });
  return out;
}

function matUse(row){
  var used=(row.used||[]).map(function(u){return u.label}).filter(Boolean);
  return used.length?used:['突破配置未引用'];
}

function expGap(t){return Math.max(0,(Number(t.exp_need)||0)-(Number(t.exp_have)||0))}

function matNeedRow(entry){
  var cat=(DATA.modules.realm.byId||{})[entry.id]||{};
  var ok=entry.owned>=entry.need;
  var labels=uniqLabels(cat.sources,['official','auction','tournament','worldboss','explore','shop','event']);
  if(labels.length>3)labels=labels.slice(0,3);
  return `<div class="rneed ${ok?'ok':'miss'}">
    <span class="rn-dot ${qcls(cat.quality)}"></span>
    <span class="rn-name">${esc(entry.name||cat.name||entry.id)}</span>
    <span class="rn-count">${entry.owned}/${entry.need}</span>
    ${labels.length?`<span class="rn-src">${esc(labels.join(' · '))}</span>`:''}
    ${cat.has_source?'':'<span class="rn-warn">游戏未标注来源</span>'}
    ${entry.auction&&entry.auction.length?`<span class="rn-tag">本期拍卖有</span>`:''}
    ${entry.held&&entry.held.length?`<span class="rn-tag steal">${entry.held.length} 人持有</span>`:''}
  </div>`;
}

function battleText(b){
  if(!b)return '无';
  var bits=['坚持 '+(b.turns||'?')+' 回合'];
  if(b.invincible)bits.push('敌人无敌');
  if(!b.escape)bits.push('不可逃跑');
  return bits.join('、');
}
function battleMain(b){
  if(!b)return '无';
  return '坚持 '+(b.turns||'?')+' 回合';
}
function battleSub(b){
  if(!b)return '';
  var bits=[];
  if(b.invincible)bits.push('敌人无敌');
  if(!b.escape)bits.push('不可逃跑');
  return bits.join(' · ');
}

function rewardText(r){
  if(!r)return '';
  var bits=[];
  if(r.lifespan&&r.lifespan>r.lifespan_now)bits.push('寿元上限 '+r.lifespan_now+' → '+r.lifespan);
  if(r.path)bits.push('道途点 +'+r.path);
  if(r.spirit)bits.push('灵根点 +'+r.spirit);
  var d=r.delta||{},names=(DATA.modules.realm||{}).attr_names||{};
  Object.keys(d).forEach(function(k){
    var v=Number(d[k])||0;if(!v||k==='999')return;
    bits.push((names[k]||'未识别属性')+' +'+v);
  });
  return bits.join(' · ');
}

function noSourceWarn(mats){
  var names=(mats||[]).filter(function(e){
    var cat=(DATA.modules.realm.byId||{})[e.id]||{};
    return !cat.has_source;
  }).map(function(e){return e.name||'未识别'});
  if(!names.length)return '';
  return `<div class="rwarn">注意：${esc(names.join('、'))} 在当前游戏配置里没有获取途径，可能尚未投放；如果背包或 NPC 处已有，请先保留。</div>`;
}

function monsterHtml(mo){
  if(!mo)return '';
  var spawns=mo.spawns||[],rare=mo.rare_spawns||[],teams=mo.teams||[];
  var auxSpawns=mo.aux_spawns||[],auxTeams=mo.aux_teams||[];
  var stageMats=(mo.stage_mat_names||[]).join('、')||'—';
  var auxMats=(mo.aux_mat_names||[]).join('、')||'—';
  function row(item){
    var mats=(item.mats_names||[]).join('、');
    return `<div class="rmon-row${item.rare?' rare':''}">
      <span class="rmon-space">${esc(item.space_name||'')}</span>
      <b>${esc(item.name||'')}</b>
      <span class="rmon-tag${item.rare?' rare':''}">${item.rare?'稀有':'普通'}</span>
      <span class="rmon-mat">掉落 ${esc(mats)}</span>
    </div>`;
  }
  function rows(list){return list.map(function(x){return row(x)}).join('')}
  function teamNames(list,limit){
    var seen={},out=[];
    (list||[]).forEach(function(t){
      var name=t.name||'';
      if(!name||seen[name])return;
      seen[name]=1;out.push(name);
    });
    return out.slice(0,limit||4);
  }
  var rareBlock=rare.length?rows(rare):
    `<div class="rmon-none">所有地图当前都没有稀有妖兽刷新</div>`;
  var body='';
  if(spawns.length)body=rows(spawns);
  else if(!teams.length)body=`<div class="rmon-none">当前阶段材料没有妖兽掉落，主要靠拍卖 / 赛事 / 任务 / 秘境等其他途径。</div>`;
  else body=`<div class="rmon-none">会掉落的 ${teams.length} 支妖兽队伍在存档里都没有刷新记录：${esc(teamNames(teams).join('、'))}</div>`;
  var missing=(teams.length&&(mo.missing_names||[]).length)?
    `<div class="rmon-miss">没有妖兽掉落的阶段材料：${esc(mo.missing_names.join('、'))}</div>`:'';
  var auxBlock='';
  if(auxTeams.length){
    var shown={};rare.forEach(function(x){shown[x.team+'|'+x.space]=1});
    var auxNow=auxSpawns.filter(function(x){return !shown[x.team+'|'+x.space]});
    var auxBody=auxNow.length?rows(auxNow):
      `<div class="rmon-none">${auxSpawns.length?'会掉助道灵物的稀有妖兽已在上面列出':
        '会掉助道灵物的 '+auxTeams.length+' 支妖兽队伍在存档里都没有刷新记录：'+esc(teamNames(auxTeams).join('、'))}</div>`;
    auxBlock=`<div class="rmon-sub">助道灵物 · 妖兽刷新</div>${auxBody}`+
      `<div class="rmon-miss">可从妖兽获得的助道灵物：${esc((mo.aux_covered_names||[]).join('、')||auxMats)}；其余助道灵物主要来自拍卖 / 任务 / 商店等途径。</div>`;
  }
  var total=spawns.length+rare.length+auxSpawns.length;
  var stateCls=total?'ok':'idle';
  // 结论放在摘要行：不展开也知道本轮有没有刷，展开才看具体在哪张图。
  var stateText=total?`已刷新 ${total} 支`:'本轮无刷新';
  var refresh=mo.refresh_until?`<span class="rmon-count">下一轮刷新 ${esc(mo.refresh_until)}</span>`:'';
  return `<details class="rmon">
    <summary class="rmon-head">
      <b>妖兽刷新</b>
      <span class="rmon-sum">全地图 · ${esc(stageMats)}</span>
      <span class="rmon-state ${stateCls}">${stateText}</span>
      ${refresh}
    </summary>
    <div class="rmon-body">
      <div class="rmon-sub">稀有妖兽（全地图）</div>
      ${rareBlock}
      <div class="rmon-sub">当前阶段材料 · 妖兽刷新</div>
      ${body}${missing}
      ${auxBlock}
      <div class="rmon-note">每个场景从自己的候选妖兽里按权重抽取（候选稀有权重 20、普通 80，只有一个候选的场景固定刷它），同一轮所有场景共用一个刷新日期；妖兽被击败后要等下一轮刷新才会重新出现。助道灵物不计入突破材料缺口。</div>
    </div>
  </details>`;
}

function targetHtml(t){
  if(!t)return '';
  var kind={layer:'升层',phase:'阶段突破',realm:'境界突破',cap:'已到上限'}[t.kind]||'突破';
  var gap=expGap(t);
  var rows=(t.materials||[]).map(matNeedRow).join('');
  var extra='';
  if(t.kind==='realm'){
    var methods=(t.rate&&t.rate.methods||[]).map(function(m){
      return `<span class="rmethod">${esc(m.name)}：${m.need} 件辅材 · ${pctText(m.rate)}</span>`;
    }).join('');
    extra=auxHtml()+`<div class="rgrid">
      <div><span>成功率</span><b>${pctText(t.rate.base)}${t.rate.limit?' → '+pctText(t.rate.max):''}</b><em>${t.rate.limit?'基础 → 满配（'+t.rate.limit+' 件辅材）':'无辅材'}</em></div>
      <div><span>突破耗时</span><b>${fmtYears(t.days,t.years)}</b><em>期间不获得修为</em></div>
      <div><span>验证战斗</span><b>${esc(battleMain(t.battle))}</b><em>${esc(battleSub(t.battle)||'突破验证副本')}</em></div>
      <div><span>失败代价</span><b class="bad">修为倒退 1 层</b><em>连续失败会累计记录</em></div>
    </div>`;
    if(methods)extra+=`<div class="rmethods"><span>突破方式</span>${methods}</div>`;
  }
  var reward=rewardText(t.rewards);
  if(reward)extra+=`<div class="rreward"><span>突破奖励</span>${esc(reward)}</div>`;
  var gapLine=gap?('还差 <b>'+gap+'</b> 修为'):'修为已满';
  var title=String(t.label||'').replace(/（境界突破）$/,'');
  return `<div class="rtarget k-${t.kind}">
    <div class="rt-head"><span class="rt-kind">${kind}</span><b>${esc(title)}</b>
      <span class="rt-exp">${gapLine}</span></div>
    ${rows?`<div class="rt-mats">${rows}</div>`:`<div class="rt-none">${esc(t.note||'')}</div>`}
    ${extra}
    ${(rows&&t.note&&t.kind!=='realm')?`<div class="rt-note">${esc(t.note)}</div>`:''}
  </div>`;
}

/* ---------------- 助道灵物（辅材）选择 ---------------- */
function auxRealm(){return (DATA.modules.realm||{}).realm||{}}
function auxIds(){
  var key=String((auxRealm()||{}).id||'0');
  if(!state.aux||typeof state.aux!=='object')state.aux={};
  if(!Array.isArray(state.aux[key]))state.aux[key]=[];
  return state.aux[key];
}
function auxItems(){
  var byId=(DATA.modules.realm||{}).byId||{};
  return (auxRealm().optional||[]).map(function(opt){
    var cat=byId[opt.id]||{};
    var src=(cat.sources||[]).filter(function(s){return s.kind!=='steal'&&s.kind!=='unknown'})[0];
    return {
      id:opt.id, name:cat.name||'未识别', bonus:Number(opt.bonus)||0,
      attrs:(opt.attrs||[]).filter(function(a){return a&&a.name}),
      owned:Number(cat.owned)||0, has:!!cat.has_source,
      src:src?src.label:''
    };
  }).sort(function(a,b){
    return (b.owned>0)-(a.owned>0)||b.bonus-a.bonus||a.id-b.id;
  });
}
function auxHtml(){
  var realm=auxRealm(), items=auxItems();
  if(!items.length)return '';
  var limit=Number(realm.optional_limit)||0;
  var base=Number(realm.rate)||0;
  var ids=auxIds();
  var top=items.slice().sort(function(a,b){return b.bonus-a.bonus}).slice(0,limit||items.length);
  var max=Math.min(100,base+top.reduce(function(sum,x){return sum+x.bonus},0));
  var selected=items.filter(function(x){return ids.indexOf(x.id)>=0});
  var sum=selected.reduce(function(total,x){return total+x.bonus},0);
  var rows=items.map(function(x){
    var on=ids.indexOf(x.id)>=0;
    var full=!on&&limit&&ids.length>=limit;
    var attrText=x.attrs.map(function(a){return a.text}).join('、');
    return `<label class="raux-i${on?' on':''}${full?' full':''}">
      <input type="checkbox" data-id="${x.id}"${on?' checked':''}${full?' disabled':''}>
      <span class="raux-name">${esc(x.name)}</span>
      <span class="raux-bonus">+${x.bonus}%</span>
      <span class="raux-owned${x.owned?'':' none'}">${x.owned?'持有 '+x.owned:'未持有'}</span>
      ${attrText?`<span class="raux-attrs">${esc(attrText)}</span>`:''}
      ${x.has?'':'<span class="raux-warn">无来源</span>'}
      ${x.src?`<span class="raux-src">${esc(x.src)}</span>`:''}
    </label>`;
  }).join('');
  var agg={},order=[];
  selected.forEach(function(x){
    x.attrs.forEach(function(a){
      var key=a.name+'|'+(a.format==null?'':a.format);
      if(!agg[key]){agg[key]={name:a.name,format:a.format,value:0};order.push(key)}
      agg[key].value+=Number(a.value)||0;
    });
  });
  var totals=order.map(function(key){
    var item=agg[key],value=Math.round(item.value*10)/10;
    return item.name+' +'+value+(item.format===2?'%':'');
  });
  return `<div class="raux" data-limit="${limit}">
    <div class="raux-head">
      <b>助道灵物</b>
      <span>最多选 ${limit||'?'} 件，成功率和属性只在本次突破生效</span>
      <div class="raux-sum">已选 <b>${selected.length}</b>/${limit||'?'} · ${base}% + ${sum}% = <b class="ok">${Math.min(100,base+sum)}%</b><em>满配 ${max}%</em></div>
    </div>
    <div class="raux-list">${rows}</div>
    ${totals.length?`<div class="raux-total">属性合计：${esc(totals.join('、'))}</div>`:''}
    <div class="raux-tip">优先带已持有、加成高的；缺的辅材可在下方材料图鉴筛「本境界辅材」查获取途径。</div>
  </div>`;
}
function bindAux(){
  var boxes=document.querySelectorAll('#realm .raux');
  boxes.forEach(function(box){
    if(box.dataset.bound)return;
    box.dataset.bound='1';
    var limit=Number(box.dataset.limit)||0;
    box.querySelectorAll('input[type=checkbox]').forEach(function(cb){
      cb.onchange=function(){
        var ids=auxIds().slice(),id=Number(cb.dataset.id);
        if(cb.checked){
          if(limit&&ids.length>=limit){cb.checked=false;return}
          if(ids.indexOf(id)<0)ids.push(id);
        }else{
          ids=ids.filter(function(x){return x!==id});
        }
        var key=String((auxRealm()||{}).id||'0');
        state.aux[key]=ids;save();
        var html=auxHtml();
        boxes.forEach(function(b){if(b===box)b.outerHTML=html;else b.outerHTML=auxHtml()});
        bindAux();
      };
    });
  });
}

function effectChips(row){
  var list=[],seen={};
  (row.used||[]).forEach(function(u){
    var text='',cls='';
    if(u.kind==='realm'){text='境界突破必需 ×1';cls='need'}
    else if(u.kind==='phase'){text='阶段突破必需 ×1';cls='need'}
    else if(u.kind==='optional'){
      var bonusText='成功率 +'+(u.bonus||0)+'%';
      if(!seen[bonusText]){seen[bonusText]=1;list.push({text:bonusText,cls:'bonus'})}
      (u.attrs||[]).forEach(function(attr){
        if(attr.text&&!seen[attr.text]){seen[attr.text]=1;list.push({text:attr.text,cls:'attr'})}
      });
      return;
    }
    if(text&&!seen[text]){seen[text]=1;list.push({text:text,cls:cls})}
  });
  if(!list.length)list.push({text:'未在突破配置中使用',cls:'none'});
  return list.map(function(x){return '<span class="reff '+x.cls+'">'+esc(x.text)+'</span>'}).join('');
}

function matCard(row){
  var q=qcls(row.quality);
  var used=matUse(row);
  var sources=groupSources(row.sources,true)||'<span class="rmuted">暂无正常获取途径</span>';
  var avail=[];
  avail.push('背包 <b>'+row.owned+'</b>');
  if(row.held&&row.held.length)avail.push('NPC：'+row.held.map(function(h){return esc(h.name)+'×'+h.count}).join('、'));
  else avail.push('NPC 持有：无');
  if(row.auction&&row.auction.length)avail.push('本期拍卖：'+row.auction.map(function(a){return esc(a.venue)+'×'+a.qty}).join('、'));
  else avail.push('本期拍卖：未刷出');
  var srcKinds=[];
  (row.sources||[]).forEach(function(s){
    var k=s.kind==='steal'?'':KIND[s.kind];
    if(k&&srcKinds.indexOf(k)<0)srcKinds.push(k);
  });
  var badges='';
  if(row.current)badges+=`<span class="rm-badge need">当前缺 ${Math.max(0,(row.need||1)-row.owned)}</span>`;
  if(row.optional)badges+=`<span class="rm-badge optional">本境界辅材</span>`;
  if(row.owned>0)badges+=`<span class="rm-badge have">持有 ${row.owned}</span>`;
  var bonus=(row.used||[]).filter(function(u){return u.kind==='optional'})[0];
  if(bonus){
    var attrText=(bonus.attrs||[]).map(function(a){return a.text}).join('、');
    badges+=`<span class="rm-badge bonus" title="${esc(attrText)}">+${bonus.bonus||0}%</span>`;
  }
  if(row.auction&&row.auction.length)badges+=`<span class="rm-badge auction">本期拍卖</span>`;
  if(row.held&&row.held.length)badges+=`<span class="rm-badge steal">NPC持有</span>`;
  if((row.sources||[]).some(function(s){return s.kind==='monster'})){
    badges+=`<span class="rm-badge ${SPAWNED[row.name]?'spawn':'nospawn'}">妖兽${SPAWNED[row.name]?'已刷新':'未刷新'}</span>`;
  }
  if(!row.has_source)badges+=`<span class="rm-badge none">无来源</span>`;
  else if(row.best_conf==='official')badges+=`<span class="rm-badge official">官方途径</span>`;
  else badges+=`<span class="rm-badge derived">反推途径</span>`;
  var warn=row.has_source?'':`<div class="rwarn">游戏当前没有标注这件材料的正常获取途径${row.held&&row.held.length?'；有 NPC 持有，可尝试索要或偷窃':'，可能尚未投放'}。</div>`;
  var steal=(row.sources||[]).filter(function(s){return s.kind==='steal'})[0];
  return `<details class="rmat ${row.current?'current':''}" data-id="${row.id}">
    <summary>
      <span class="rm-dot ${q}"></span>
      <span class="rm-name">${hi(row.name,state.q||'')}</span>
      <span class="rm-type">${esc(row.type_label||'')}</span>
      <span class="rm-used">${esc(used[0]||'')}</span>
      <span class="rm-src" title="获取途径">${esc(srcKinds.join(' · ')||'无正常来源')}</span>
      <span class="rm-badges">${badges}</span>
    </summary>
    <div class="rmbody">
      ${row.desc?`<div class="rmdesc">${esc(row.desc)}</div>`:''}
      <div class="rmline"><b>用途</b><div class="rtags">${used.map(function(u){return '<span class="rtag">'+esc(u)+'</span>'}).join('')}</div></div>
      <div class="rmline"><b>效果</b><div class="reffs">${effectChips(row)}</div></div>
      <div class="rmline"><b>获取途径</b><div class="rsrcs">${sources||'<span class="rmuted">暂无记录</span>'}</div></div>
      ${steal?`<div class="rmline"><b>偷窃</b><span class="rmuted">${esc(steal.detail||'')}，被发现会掉好感/声望</span></div>`:''}
      <div class="rmline"><b>当前</b><span class="rmuted">${avail.join(' ｜ ')}</span></div>
      ${warn}
    </div>
  </details>`;
}

function renderMats(){
  var m=DATA.modules.realm,host=$('realm-mats');if(!m||!host)return;
  // 妖兽刷新集合：材料行直接标“妖兽已刷新/未刷新”，不用展开也不必去上面找
  SPAWNED={};
  var mo=m.monsters||{};
  (mo.spawns||[]).concat(mo.rare_spawns||[]).forEach(function(s){
    (s.mats_names||[]).forEach(function(n){SPAWNED[n]=true});
  });
  var rows=m.materials||[];
  var q=(state.q||'').trim().toLowerCase();
  var selectedRealm=Number(state.realm)||0;
  if(['all','current','optional','sourced','unsourced','available'].indexOf(state.filter)<0)state.filter='all';
  var picked=rows.filter(function(row){
    if(selectedRealm&&Number(row.realm)!==selectedRealm)return false;
    if(state.filter==='current'&&!row.current)return false;
    if(state.filter==='optional'&&!row.optional)return false;
    if(state.filter==='sourced'&&!row.has_source)return false;
    if(state.filter==='unsourced'&&row.has_source)return false;
    if(state.filter==='available'&&!(row.owned>0||(row.held||[]).length||(row.auction||[]).length))return false;
    if(!q)return true;
    var hay=[row.name,row.desc,row.type_label,(row.used||[]).map(function(u){return u.label}).join(' '),
      (row.sources||[]).map(function(s){return s.label+' '+s.detail}).join(' ')].join(' ').toLowerCase();
    return hay.indexOf(q)>=0;
  });
  picked.sort(function(a,b){
    return (b.current?1:0)-(a.current?1:0)||(Number(a.realm)-Number(b.realm))||
      (Number(a.type)-Number(b.type))||(Number(b.quality)-Number(a.quality))||(a.id-b.id);
  });
  host.innerHTML=picked.length?picked.map(matCard).join(''):'<div class="empty">没有符合条件的材料</div>';
  if(state.expandAll)document.querySelectorAll('#realm-mats .rmat').forEach(function(d){d.open=true});
  var expand=$('realm-expand');if(expand)expand.textContent=state.expandAll?'收起全部':'展开全部';
  var count=$('realm-count');if(count)count.textContent='显示 '+picked.length+' / '+rows.length;
  document.querySelectorAll('#realm-filters .chip').forEach(function(btn){
    btn.classList.toggle('on',btn.id==='realm-only'?!!selectedRealm:btn.dataset.filter===state.filter);
  });
  var only=$('realm-only');
  if(only){
    var realmName='';
    (m.realms||[]).forEach(function(r){if(Number(r.id)===selectedRealm)realmName=r.name});
    only.style.display=selectedRealm?'':'none';
    if(selectedRealm)only.innerHTML=esc(realmName)+' <i>×</i>';
  }
}

function renderRoadmap(m){
  var rank={},order=0;
  (m.realms||[]).forEach(function(realm){(realm.phases||[]).forEach(function(pid){
    var phase=(m.phases||{})[String(pid)];if(!phase)return;
    (phase.layers||[]).forEach(function(lid){rank[String(lid)]=order++});
  })});
  var current=m.layer?String(m.layer.id):'';
  return (m.realms||[]).map(function(realm){
    var phases=(realm.phases||[]).map(function(pid){
      var phase=(m.phases||{})[String(pid)];if(!phase)return '';
      var dots=(phase.layers||[]).map(function(lid){
        var info=(m.layers||{})[String(lid)]||{};
        var cls=lid===Number(current)?'now':(rank[String(lid)]<rank[current]?'past':'');
        var mat=(phase.mats||[]).map(function(x){return ((m.byId||{})[x.id]||{}).name||'未识别'}).join('、');
        var tip=phase.name+' '+(info.layer||'')+' 层 · 修为 '+(info.exp||0)+(mat?' · 阶段材料：'+mat:'');
        return `<i class="rdot ${cls}" title="${esc(tip)}"></i>`;
      }).join('');
      return `<div class="rphase"><span>${esc(phase.name)}</span><div class="rdots">${dots}</div></div>`;
    }).join('');
    var isNow=Number(realm.id)===Number((m.realm||{}).id);
    return `<button type="button" class="rmap-realm${isNow?' now':''}" data-realm="${realm.id}">
      <div class="rr-name">${esc(realm.name)}${isNow?'<em>当前</em>':''}</div>
      <div class="rr-sub">${realm.days?(fmtYears(realm.days,realm.years)+' 突破'):'版本上限'}</div>
      <div class="rr-phases">${phases}</div>
    </button>`;
  }).join('');
}

function miniRow(title,block,meta){
  var rows=(block.materials||[]).map(matNeedRow).join('');
  return `<div class="rmini">
    <div class="rmini-head"><b>${esc(title)}</b><span>${meta||''}</span></div>
    ${rows?`<div class="rt-mats">${rows}</div>`:''}
    ${block.note?`<div class="rt-note">${esc(block.note)}</div>`:''}
  </div>`;
}

function renderRealm(){
  var host=$('realm');if(!host)return;
  var m=DATA.modules.realm;
  if(!m||!m.ok){host.innerHTML=sourceHtml(m||{})+'<div class="empty">暂无可用的境界数据，请确认存档已导出。</div>';return}
  var byId={};(m.materials||[]).forEach(function(row){byId[row.id]=row});m.byId=byId;

  var phaseLayers=(m.phase&&m.phase.layers)||[];
  var layerIndex=phaseLayers.indexOf(m.layer.id);
  var layerNo=layerIndex>=0?layerIndex+1:(m.layer.layer||1);
  var hero=`<div class="rhero">
    <div class="rhero-main">
      <div class="rrealm">${esc(m.realm.name||'')} <span>${esc(m.phase.name||'')}</span>
        <em>${layerNo} / ${phaseLayers.length||'?'} 层</em></div>
      <div class="rexp"><b>修为</b> ${m.exp} / ${m.need||'?'}</div>
      <div class="rbar"><i style="width:${m.pct}%"></i></div>
      <div class="rmeta">积攒修为 ${m.reserve} / ${m.reserve_limit||'?'}${m.last?` · 上次突破 ${m.last.years} 年（护法 ${m.last.friends} 位）`:''}${m.failure&&m.failure.streak?` · 连续失败 ${m.failure.streak} 次`:''}</div>
    </div>
  </div>`;

  var sp=m.spirit||{},spc=sp.config||{};
  var spiritLine=`<div class="rspirit"><span class="rs-ic">灵</span>永久灵眼 ${sp.permanent_count||0} 个（已吸 ${sp.permanent_exp||0}/${sp.permanent_total||0}）<i>·</i>本轮灵眼 ${sp.cycle_count||0} 个`+
    (spc.total?`<i>·</i>每眼 ${spc.total} 修为、每次拖动 ${spc.drag} 修为`:'')+`</div>`;
  var counts={all:(m.materials||[]).length,current:0,optional:0,sourced:0,unsourced:0,available:0};
  (m.materials||[]).forEach(function(row){
    if(row.current)counts.current++;
    if(row.optional)counts.optional++;
    if(row.has_source)counts.sourced++;else counts.unsourced++;
    if(row.owned>0||(row.held||[]).length||(row.auction||[]).length)counts.available++;
  });

  var next=m.next||{};
  // 后续突破只保留一份紧凑清单：阶段突破与境界突破分开列，避免和主目标重复整卡。
  var later='';
  if(next.kind!=='realm'){
    var laterRows=[];
    if(next.kind==='layer'&&m.phase_preview){
      laterRows.push(miniRow('阶段突破',m.phase_preview,'修为满 + 阶段材料'));
    }
    if(m.preview){
      var pr=m.preview.rate||{};
      laterRows.push(miniRow('本境界突破（提前准备）',m.preview,
        '成功率 '+pctText(pr.base||0)+' → 满配 '+pctText(pr.max||0)+' · '+fmtYears(m.preview.days,m.preview.years)));
      laterRows.push(auxHtml());
    }
    if(laterRows.length){
      later=`<details class="rfold"><summary>接下来还要准备 <em>阶段突破 / 本境界突破</em></summary>
        <div class="rfold-body">${laterRows.join('')}</div></details>`;
    }
  }

  var hint={layer:'只差修为',phase:'修为 + 阶段材料',realm:'修为 + 材料 + 验证战斗',cap:'当前上限'}[next.kind||'']||'';
  host.innerHTML=sourceHtml(m)+hero+monsterHtml(m.monsters)+spiritLine+
    `<div class="rsec"><h2>突破目标</h2><span class="rsec-hint">${hint}</span></div>`+
    targetHtml(next)+later+
    `<div class="rsec"><h2>材料图鉴</h2><span class="rsec-hint" id="realm-count"></span></div>
     <div class="rtools">
       <input id="realm-q" class="rsearch" type="search" placeholder="搜索材料名、用途或来源，例如：金火丹砂 / 拍卖 / 天宗论剑" value="${esc(state.q||'')}">
       <div class="chips" id="realm-filters">
         <button type="button" class="chip" data-filter="all">全部 <i>${counts.all}</i></button>
         <button type="button" class="chip" data-filter="current">当前缺口 <i>${counts.current}</i></button>
         <button type="button" class="chip" data-filter="optional">本境界辅材 <i>${counts.optional}</i></button>
         <button type="button" class="chip" data-filter="sourced">有来源 <i>${counts.sourced}</i></button>
         <button type="button" class="chip" data-filter="unsourced">无来源 <i>${counts.unsourced}</i></button>
         <button type="button" class="chip" data-filter="available">当前可拿 <i>${counts.available}</i></button>
         <button type="button" class="chip" id="realm-only" data-filter="realm">本境界 <i>×</i></button>
         <button type="button" class="chip action" id="realm-expand">展开全部</button>
       </div>
       <span class="rtools-note">点击境界卡片可只看该境界材料</span>
     </div>
     <div class="rmats" id="realm-mats"></div>
     <details class="rfold">
       <summary>境界路线图 <em>共 ${counts.all} 件突破材料</em></summary>
       <div class="rfold-body"><div class="rmap">${renderRoadmap(m)}</div></div>
     </details>
     <details class="rfold">
       <summary>规则说明 <em>突破类型、来源标记与成功率</em></summary>
       <div class="rfold-body"><div class="tip">境界突破分三种：升层只看修为；阶段突破要修为满 + 1 件阶段材料；境界突破要修为满 + 4 件境界材料，还会进入验证战斗，失败会倒退 1 层修为。<br>
       材料来源标记：「官方」是游戏内标注的获取途径；「拍卖 / 赛事 / 镇劫 / 秘宝 / 商店 / 奇遇」是从掉落表反推出来的具体玩法；「缺来源」表示当前配置没有正常获取途径，可能尚未投放。<br>
       成功率按配置推算（基础成功率 + 所选辅材加成），游戏内可能还有护法或其他修正；偷窃需要 NPC 恰好持有该物品。助道灵物的属性加成只在本次突破生效。</div></div>
     </details>`;

  var input=$('realm-q');
  if(input)input.oninput=function(){state.q=this.value;save();renderMats()};
  document.querySelectorAll('#realm-filters .chip').forEach(function(btn){
    btn.onclick=function(){
      if(btn.id==='realm-expand'){state.expandAll=state.expandAll?0:1;save();renderMats();return}
      if(btn.id==='realm-only'){state.realm=0;state.filter='all'}
      else if(btn.dataset.filter)state.filter=btn.dataset.filter;
      save();renderMats();
    };
  });
  document.querySelectorAll('.rmap-realm').forEach(function(btn){
    btn.onclick=function(){
      var id=Number(btn.dataset.realm);
      state.realm=Number(state.realm)===id?0:id;
      state.filter='all';
      save();renderMats();
      var mats=$('realm-mats');if(mats&&state.realm)mats.scrollIntoView({behavior:'smooth',block:'start'});
    };
  });
  bindAux();
  renderMats();
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
// 材料来源里的「任务页」按钮：切到任务页并按任务名过滤。
document.addEventListener('click',function(e){
  var btn=e.target.closest?e.target.closest('.rsrc-jump'):null;
  if(!btn)return;
  e.preventDefault();e.stopPropagation();
  var name=btn.getAttribute('data-quest');
  var key=btn.getAttribute('data-module')||'quest';
  if(!window.PROGRESS_GOTO||!window.PROGRESS_GOTO(key,name)){
    btn.textContent='未启用';
    setTimeout(function(){btn.textContent=MOD_LABEL[key]||'任务页'},1500);
  }
});
window.PROGRESS_VIEWS['realm']=renderRealm;
})();
