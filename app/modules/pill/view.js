/* 炼丹：页面渲染（自 output.py 原样搬入）。 */
(function(){
const PILL_COLOR={1:'#e8c76d',2:'#ff7b72',3:'#6edda2',4:'#6aa9ff',5:'#d18bff',6:'#9a7bff'};
const PILL_TYPE={1:'丹方属性',2:'丹方',3:'减毒',4:'奖励',5:'传送口',6:'传送口'};
const PILL_ELEMENT=['无','金','木','水','火','土'];
const PILL_ELEMENT_COLOR=['#8b93a1','#e6dcae','#8ccf92','#7fc0ee','#ee9a86','#d8b273'];
const PILL_TYPES={recipe:[2],effect:[1],cleanse:[3],reward:[4],portal:[5,6]};
const PILL_TYPE_LABEL={recipe:'丹方',effect:'丹方属性',cleanse:'减毒',reward:'奖励',portal:'传送口'};
const PILL_KEYWORDS=['攻击','暴击','生命','破韧','防御','速度','灵力','伤害','净化','复活','修为','灼烧','共鸣','同道','灵气'];
const PILL_ORDER=['recipe','effect','cleanse','reward','portal','other'];
// 用户常常不知道丹方名，只知道想要什么效果。这些词只作为入口，
// 每个词的命中数都从当前数据实时统计，命中为 0 的词自动不显示（游戏改文案也不会误导）。
const EFFECT_TERMS=['回复','气血','攻击','防御','暴击','灵力','速度'];
const PILL_FILTER_KEY='worldapart.pill.filters.v3';
const PILL_DEFAULTS={types:Object.keys(PILL_TYPES),elements:['1','2','3','4','5'],tiers:[],keywords:[],q:'',hideDone:false};
// 未知类型（游戏新增拾取物）自动归入「其他」，不会从筛选里消失
let PILL_GROUPS=PILL_TYPES,PILL_LABELS=PILL_TYPE_LABEL;
let pillFilter=Object.assign({},PILL_DEFAULTS,store.get(PILL_FILTER_KEY,{}));
if(!Array.isArray(pillFilter.types))pillFilter.types=PILL_DEFAULTS.types.slice();
if(!Array.isArray(pillFilter.elements))pillFilter.elements=PILL_DEFAULTS.elements.slice();
if(!Array.isArray(pillFilter.tiers))pillFilter.tiers=[];
if(!Array.isArray(pillFilter.keywords))pillFilter.keywords=[];
function poiFill(p){
 return p[1]===2?(PILL_ELEMENT_COLOR[p[2]]||PILL_COLOR[2]):(PILL_COLOR[p[1]]||'#9aa3b0');
}
function pillName(p,mp){const t=p[1];
 if(t===2){const id=(mp.pool||[])[p[5]]||'';const r=(mp.recipes||{})[id];return (r&&r.n)||('丹方 '+id)}
 if(t===1){const e=(mp.effects||{})[String(p[4])];return e?e[0]:('药效 '+p[4])}
 if(t===3)return '减毒';
 if(t===4){const r=(mp.rewards||{})[String(p[8])];return r?r[0]:('奖励 '+p[8])}
 if(t===5||t===6){const pt=(mp.portals||{})[String(p[10])];return pt?pt[0]:('传送门 '+p[10])}
 return (PILL_LABELS.other||'其他')+' ('+t+')'}
function pillDesc(p,mp){
 if(p[1]===1){const e=(mp.effects||{})[String(p[4])];return e?`${e[3]}　拾取经验 ${e[4]}`:''}
 if(p[1]===4){const r=(mp.rewards||{})[String(p[8])];return r?`${r[3]}　价值 ${r[4]}~${r[5]}`:''}
 if(p[1]>=5){const pt=(mp.portals||{})[String(p[10])];return pt?pt[3]:''}
 if(p[1]===3)return '拾取后削减丹毒';
 return ''}
function pillText(p,mp){
 if(p[1]===2){const r=(mp.recipes||{})[String((mp.pool||[])[p[5]]||'')];return r?r.d||'':''}
 if(p[1]===1){const e=(mp.effects||{})[String(p[4])];return e?e[3]||'':''}
 return '';
}
function portalCost(mp,cfg){
 const pt=(mp.portals||{})[String(cfg)];
 if(!pt)return '';
 return pt[5]?`${pt[4]||'妖丹'} ×${pt[5]}`:'无需妖丹';
}
// 详情面板为空时的视觉引导：三步流程，不堆文字
const PILL_HINT=`<div class="pill-hint">`+
 `<span class="hstep" style="--c:#e8c76d"><i>1</i><b>选丹方</b></span><em>→</em>`+
 `<span class="hstep" style="--c:#ff7b72"><i>2</i><b>点地图</b></span><em>→</em>`+
 `<span class="hstep" style="--c:#6edda2"><i>3</i><b>看路线与妖丹</b></span></div>`;
const PILL_LEGEND=`<div class="legend pill-legend">`+
 `<div class="lg"><span class="lg-t">拾取对象</span>`+
  [2,1,3,4,5].map(t=>`<span><i style="background:${PILL_COLOR[t]}"></i>${PILL_TYPE[t]}</span>`).join('')+
 `</div>`+
 `<div class="lg"><span class="lg-t">五行丹方</span>`+
  [1,2,3,4,5].map(t=>`<span><i style="background:${PILL_ELEMENT_COLOR[t]}"></i>${PILL_ELEMENT[t]}</span>`).join('')+
 `</div>`+
 `<div class="lg"><span class="lg-t">地形</span>`+
  `<span><i style="background:#5a4a36"></i>山</span><span><i style="background:#26414a"></i>沼泽</span></div>`+
 `</div>`;
function initPill(){
 const m=DATA.modules&&DATA.modules.pill;if(!m)return;const host=$('pill');
 const st=m.rows||{},maps=(st.map&&st.map.maps)||[];
 if(!maps.length){host.innerHTML=sourceHtml(m)+'<div class="empty">暂无炼丹盘面数据</div>';return}
 const pick=parseInt(store.get('worldapart.pill.map.v1',0),10)||0;
 const mp=maps[pick>=0&&pick<maps.length?pick:0];
 const cols=mp.cols,rowsN=mp.rows,ts=mp.tile_size||20,consumed=new Set(st.consumed||[]);
 const learned=new Set((st.manual||[]).map(r=>String(r.id)));
 const compById=new Map();(mp.pois||[]).forEach((p,i)=>compById.set(p[0],(mp.comps||[])[i]));
 // 游戏新增拾取物类型时不再被筛掉，统一落到「其他」
 const extra=[...new Set(mp.pois.map(p=>p[1]).filter(t=>PILL_COLOR[t]===undefined))].sort((a,b)=>a-b);
 if(extra.length){
  PILL_LABELS=Object.assign({},PILL_TYPE_LABEL,{other:'其他'});
  PILL_GROUPS=Object.assign({},PILL_TYPES,{other:extra});
  if(!pillFilter.types.includes('other'))pillFilter.types=pillFilter.types.concat('other');
 }else{PILL_LABELS=PILL_TYPE_LABEL;PILL_GROUPS=PILL_TYPES}
 pillFilter.types=pillFilter.types.filter(k=>PILL_GROUPS[k]);
 const cards=[[`炼丹等级`,`${st.level||0} 级`,`经验 ${st.exp||0}`],
  [`炉火`,`${st.current_furnace||0} 号炉`,`已解锁 ${st.furnace||0} 座`],
  [`丹方手记`,`${(st.manual||[]).length} / ${Object.keys(mp.recipes||{}).length} 张`,`最高 ${st.highest_grade||0} 品`],
  [`盘面拾取点`,`${mp.pois.length} 个`,`已拾取 ${consumed.size}`]]
  .map(([k,v,s])=>`<div class="card"><div class="k">${esc(k)}</div><div class="v">${esc(v)}<span> ${esc(s)}</span></div></div>`).join('');
 // 功效入口：命中数实时统计，0 命中的词不显示
 function effectChips(){
  const recipes=Object.values(mp.recipes||{});
  return EFFECT_TERMS.map(term=>{
   const count=recipes.filter(r=>(r.d||'').includes(term)).length;
   return count?`<button type="button" class="chip" data-eff="${esc(term)}">${esc(term)}<i>${count}</i></button>`:'';
  }).join('');
 }
 host.innerHTML=sourceHtml(m)+`<div class="cards">${cards}</div>`+
  `<div class="pill-searchwrap"><input id="pillq" class="pill-search" placeholder="不知道名字也行：搜想要的效果，例如 回复 / 攻击 / 防御"><div class="effchips"><span class="chip-label">按功效</span>${effectChips()}</div><div id="pillhits" class="phits"></div></div>`+
  (maps.length>1?`<div class="chips" id="pillmaps"><span class="chip-label">盘面</span>`+
   maps.map((x,i)=>`<button class="chip${x===mp?' on':''}" data-map="${i}">${esc(x.name)}<i>${(x.pois||[]).length}</i></button>`).join('')+`</div>`:'')+
  `<div class="pill-grid"><div class="mapwrap"><div class="sec-title">炼丹地图<small>点地图上的丹方可看路线，Alt+点击独选对象</small></div><div class="mapbox"><canvas id="pillmap"></canvas><svg id="pillsvg" viewBox="0 0 ${cols} ${rowsN}" xmlns="http://www.w3.org/2000/svg"></svg><div class="map-tip" id="pillherbtip"></div><div class="map-tip" id="pillpoitip"></div></div>${PILL_LEGEND}</div>`+
  `<div class="pill-side">`+
  `<div class="sec-title">丹方详情<small>成丹门槛、可炼次数与传送路线</small></div>`+
  `<div class="pill-detail" id="pillinfo">${PILL_HINT}</div>`+
  `<div class="fsec"><div class="fhead"><b>显示对象</b><span class="fhint">Alt+点击 独选</span>`+
   `<span class="fops"><button type="button" data-op="none" data-row="types">清</button><button type="button" data-op="all" data-row="types">全</button></span></div>`+
   `<div class="chips" id="pillchips"></div></div>`+
  `<details class="fsec fsec-fold" id="pillcond"><summary><b>筛选条件</b><span class="fhint">五行 / 阶数 / 药效</span></summary>`+
   `<div class="frow"><span class="chip-label">五行</span><div class="chips" id="pillelems"></div>`+
    `<span class="fops"><button type="button" data-op="none" data-row="elements">清</button><button type="button" data-op="all" data-row="elements">全</button></span></div>`+
   `<div class="frow"><span class="chip-label">阶数</span><div class="chips" id="pilltiers"></div>`+
    `<span class="fops"><button type="button" data-op="none" data-row="tiers">清</button><button type="button" data-op="all" data-row="tiers">全</button></span></div>`+
   `<div class="frow"><span class="chip-label">药效</span><div class="chips" id="pillkeys"></div>`+
    `<span class="fops"><button type="button" data-op="none" data-row="keywords">清</button></span></div>`+
  `</details>`+
  `<div class="fsec"><div class="fhead"><b>视图</b></div><div class="chips" id="pillview"></div></div>`+
  `<div class="pill-active" id="pillactive"></div>`+
  `<div class="pill-sum" id="pillsum"></div>`+
  `<div class="pill-list" id="pilllist"></div>`+
  `</div></div>`+
  `<div class="manual"><div class="manual-head">丹方手记<span>已学会 ${(st.manual||[]).length} 张 · 点击定位盘面</span></div><div class="manual-list" id="pillmanual"></div></div>`+
  `<div class="tip">盘面为游戏内置固定地图（${cols}×${rowsN} 格，每格 ${ts} 单位），并非随机生成；带删除线的拾取点表示本存档已拾取过。「迷雾」开启后只显示已探索区域，落在迷雾里的拾取点会一起隐藏。「药材路线」默认关闭，打开后显示盘面自带的 ${(mp.trajectories||[]).length} 条药材分布轨迹，鼠标停在线路上才会显示药材名。</div>`;
 // 地形
 const cv=$('pillmap');cv.width=cols;cv.height=rowsN;
 const ctx=cv.getContext('2d');const img=ctx.createImageData(cols,rowsN);const px=img.data;
 const palette={0:[20,18,16],1:[90,74,54],2:[38,66,74]};let i=0;
 for(const [v,c] of mp.runs){const col=palette[v]||palette[0];for(let k=0;k<c;k++){px[i]=col[0];px[i+1]=col[1];px[i+2]=col[2];px[i+3]=255;i+=4}}
 ctx.putImageData(img,0,0);
 const svg=$('pillsvg'),NS='http://www.w3.org/2000/svg';
 // 迷雾：未探索区域压暗，已探索的笔迹按半径揭开
 const strokes=(st.fog||{})[mp.name||'default']||[];
 let fogLayer=null;
 if(strokes.length){
  const defs=document.createElementNS(NS,'defs');
  const mask=document.createElementNS(NS,'mask');
  mask.setAttribute('id','pillfogmask');mask.setAttribute('maskUnits','userSpaceOnUse');
  mask.setAttribute('x','0');mask.setAttribute('y','0');
  mask.setAttribute('width',cols);mask.setAttribute('height',rowsN);
  const cover=document.createElementNS(NS,'rect');
  cover.setAttribute('x','0');cover.setAttribute('y','0');
  cover.setAttribute('width',cols);cover.setAttribute('height',rowsN);
  cover.setAttribute('fill','#000');mask.appendChild(cover);
  strokes.forEach(([seg,sx,sy,ex,ey,r])=>{
   if(seg){
    const line=document.createElementNS(NS,'line');
    line.setAttribute('x1',sx/ts);line.setAttribute('y1',sy/ts);
    line.setAttribute('x2',ex/ts);line.setAttribute('y2',ey/ts);
    line.setAttribute('stroke','#fff');line.setAttribute('stroke-width',Math.max(r*2/ts,.8));
    line.setAttribute('stroke-linecap','round');mask.appendChild(line);
   }else{
    const c=document.createElementNS(NS,'circle');
    c.setAttribute('cx',sx/ts);c.setAttribute('cy',sy/ts);
    c.setAttribute('r',Math.max(r/ts,.8));c.setAttribute('fill','#fff');mask.appendChild(c);
   }
  });
  defs.appendChild(mask);svg.appendChild(defs);
  fogLayer=document.createElementNS(NS,'rect');
  fogLayer.setAttribute('x','0');fogLayer.setAttribute('y','0');
  fogLayer.setAttribute('width',cols);fogLayer.setAttribute('height',rowsN);
  fogLayer.setAttribute('id','pillfog');
  fogLayer.setAttribute('fill','#06080a');fogLayer.setAttribute('fill-opacity','.82');
  fogLayer.setAttribute('mask','url(#pillfogmask)');
  svg.appendChild(fogLayer);
 }
 // 判断某个坐标是否在已探索范围内
 function exploredAt(x,y){
  for(let k=0;k<strokes.length;k++){
   const s=strokes[k],r=s[5];
   if(s[0]){
    const dx=s[3]-s[1],dy=s[4]-s[2],len=dx*dx+dy*dy;
    let t=len?((x-s[1])*dx+(y-s[2])*dy)/len:0;
    t=t<0?0:t>1?1:t;
    const px=s[1]+t*dx-x,py=s[2]+t*dy-y;
    if(px*px+py*py<=r*r)return true;
   }else{
    const px=x-s[1],py=y-s[2];
    if(px*px+py*py<=r*r)return true;
   }
  }
  return false;
 }
 // 药材轨迹
 const herbs=mp.herbs||{};
 const herbLayer=document.createElementNS(NS,'g');herbLayer.setAttribute('id','pillherb');
 svg.appendChild(herbLayer);
 // 药材轨迹：名字用 HTML 悬浮提示（盘面 500×500 缩放后 SVG 文字只剩几像素，没法看）
 const herbTip=$('pillherbtip');
 const poiTip=$('pillpoitip');
 function poiTipText(p){return `${pillName(p,mp)} · ${portalCost(mp,p[10])}`}
 (mp.trajectories||[]).forEach(([hid,,,segs])=>{
  if(!segs||!segs.length)return;const pts=segs.map(s=>`${s[1]/ts},${s[2]/ts}`).join(' ');
  const name=herbs[String(hid)]||('药材 '+hid);
  const group=document.createElementNS(NS,'g');group.setAttribute('class','herb-track');
  const line=document.createElementNS(NS,'polyline');line.setAttribute('points',pts);
  line.setAttribute('fill','none');line.setAttribute('stroke','#8f7bd8');line.setAttribute('stroke-opacity','.28');
  line.setAttribute('stroke-width','.8');group.appendChild(line);
  const hit=document.createElementNS(NS,'polyline');hit.setAttribute('points',pts);
  hit.setAttribute('fill','none');hit.setAttribute('stroke','#fff');hit.setAttribute('stroke-opacity','0');
  hit.setAttribute('stroke-width','4');hit.setAttribute('pointer-events','stroke');group.appendChild(hit);
  hit.addEventListener('mouseenter',()=>{herbTip.textContent=name;herbTip.classList.add('on')});
  hit.addEventListener('mousemove',e=>{
   const r=mapbox.getBoundingClientRect();
   herbTip.style.left=(e.clientX-r.left)+'px';
   herbTip.style.top=(e.clientY-r.top)+'px';
  });
  hit.addEventListener('mouseleave',()=>herbTip.classList.remove('on'));
  herbLayer.appendChild(group)});
 // 拾取点
 const dots=[],portalHits=[];
 mp.pois.forEach(p=>{
  const isPortal=p[1]===5||p[1]===6;
  const c=document.createElementNS(NS,'circle');
  c.setAttribute('cx',p[6]/ts);c.setAttribute('cy',p[7]/ts);
  c.setAttribute('r',isPortal?3.4:(p[1]===2?2.4:1.7));
  c.setAttribute('fill',poiFill(p));
  c.setAttribute('fill-opacity',p[1]===4?'.75':'.95');
  c.setAttribute('stroke','#0b0d10');c.setAttribute('stroke-width','.4');
  c.classList.add('poi-dot');
  if(isPortal)c.classList.add('poi-portal');
  const tip=document.createElementNS(NS,'title');
  tip.textContent=isPortal?poiTipText(p):pillName(p,mp);c.appendChild(tip);
  if(consumed.has(p[0]))c.classList.add('dim');
  if(strokes.length&&!exploredAt(p[6],p[7]))c.classList.add('unseen');
  if(isPortal){
   // 传送口放大命中区 + 悬浮提示，解决 POI 太小难选中
   const hit=document.createElementNS(NS,'circle');
   hit.setAttribute('cx',p[6]/ts);hit.setAttribute('cy',p[7]/ts);
   hit.setAttribute('r','8');hit.setAttribute('fill','transparent');hit.setAttribute('stroke','none');
   hit.setAttribute('pointer-events','all');hit.classList.add('poi-hit');
   hit.addEventListener('click',()=>showPoi(p));
   hit.addEventListener('mouseenter',()=>{poiTip.textContent=poiTipText(p);poiTip.classList.add('on')});
   hit.addEventListener('mousemove',e=>{
    const r=mapbox.getBoundingClientRect();
    poiTip.style.left=(e.clientX-r.left)+'px';
    poiTip.style.top=(e.clientY-r.top)+'px';
   });
   hit.addEventListener('mouseleave',()=>poiTip.classList.remove('on'));
   portalHits.push(hit);
  }else{
   c.addEventListener('click',()=>showPoi(p));
  }
  svg.appendChild(c);dots.push(c);
 });
 const routeLayer=document.createElementNS(NS,'g');
 routeLayer.setAttribute('id','pillroute');svg.appendChild(routeLayer);
 const ring=document.createElementNS(NS,'circle');
 ring.setAttribute('id','pillring');
 ring.setAttribute('fill','none');ring.setAttribute('stroke','#fff');
 ring.setAttribute('stroke-width','.9');ring.setAttribute('r','6');
 ring.style.display='none';svg.appendChild(ring);
 // 传送口命中区铺在最上层，保证可点（不会被路线/圆环挡住）
 portalHits.forEach(h=>svg.appendChild(h));
 // 把传送路线画在盘面上，避免只给坐标却看不到门在哪
 function drawRoute(steps){
  while(routeLayer.firstChild)routeLayer.removeChild(routeLayer.firstChild);
  steps.forEach(([cfg,x1,y1,x2,y2])=>{
   const line=document.createElementNS(NS,'line');
   line.setAttribute('x1',x1/ts);line.setAttribute('y1',y1/ts);
   line.setAttribute('x2',x2/ts);line.setAttribute('y2',y2/ts);
   line.setAttribute('stroke','#4fe0c0');line.setAttribute('stroke-width','1.4');
   line.setAttribute('stroke-dasharray','5 4');line.setAttribute('stroke-opacity','.9');
   routeLayer.appendChild(line);
   [[x1,y1,'入'],[x2,y2,'出']].forEach(([x,y,label])=>{
    const dot=document.createElementNS(NS,'circle');
    dot.setAttribute('cx',x/ts);dot.setAttribute('cy',y/ts);dot.setAttribute('r','5');
    dot.setAttribute('fill','#0b1412');dot.setAttribute('fill-opacity','.65');
    dot.setAttribute('stroke','#4fe0c0');dot.setAttribute('stroke-width','1.6');
    routeLayer.appendChild(dot);
    const text=document.createElementNS(NS,'text');
    text.setAttribute('x',x/ts);text.setAttribute('y',y/ts-7.5);
    text.setAttribute('fill','#4fe0c0');text.setAttribute('font-size','9');
    text.setAttribute('text-anchor','middle');text.textContent=label;
    routeLayer.appendChild(text);
   });
  });
 }
 $('pillinfo').onclick=e=>{
  const jump=e.target.closest('[data-x]');
  if(jump){
   ring.setAttribute('cx',+jump.dataset.x/ts);
   ring.setAttribute('cy',+jump.dataset.y/ts);
   ring.style.display='';
  }
 };
 function showPoi(p){
  const isRecipe=p[1]===2;
  const rid=isRecipe?String((mp.pool||[])[p[5]]||''):'';
  const rec=isRecipe?(mp.recipes||{})[rid]:null;
  const tags=[PILL_TYPE[p[1]]||''];
  if(isRecipe&&rec)tags.push(`${PILL_ELEMENT[rec.e]||'—'}系 · ${rec.t||0} 阶`);
  else if(p[1]<=3&&p[2])tags.push(`${PILL_ELEMENT[p[2]]||''}${p[3]?` · ${p[3]}阶`:''}`);
  if(isRecipe&&rec)tags.push(learned.has(rid)?'已学会':'未学会');
  if(consumed.has(p[0]))tags.push('已拾取');
  let html=`<div class="detail-head"><i class="dh-dot" style="background:${poiFill(p)}"></i>`+
   `<div class="dh-title"><b>${esc(pillName(p,mp))}</b><span class="muted">${esc(tags.filter(Boolean).join(' · '))}</span></div></div>`+
   `<div class="dh-meta">坐标 ${p[6]}, ${p[7]}</div>`;
  if(rec){
   const tiers=(rec.g||[]).join(' / ')||'—';
   html+=`<div class="rec-info"><div><span>丹毒上限</span>${rec.x||0}</div>`+
    `<div><span>成丹门槛</span>${tiers}</div>`+
    `<div><span>灵力 / 时长</span>${rec.s||0} / ${rec.tm||0}</div>`+
    `<div><span>可炼次数</span>${rec.m||'不限'}</div></div>`;
   if(rec.d)html+=`<div class="muted" style="margin-top:6px">${esc(rec.d)}</div>`;
  }else if(p[1]===1&&(mp.effects||{})[String(p[4])]){
   const eff=mp.effects[String(p[4])];
   if(eff[7])html+=`<div class="rec-info"><div><span>主属性</span>${esc(eff[7])}</div>`+
    `<div><span>数值</span>${eff[6]}</div></div>`;
   if(eff[3])html+=`<div class="muted" style="margin-top:6px">${esc(eff[3])}</div>`;
  }else if(pillDesc(p,mp)){
   html+=`<div class="muted" style="margin-top:4px">${esc(pillDesc(p,mp))}</div>`;
  }
  const comp=compById.has(p[0])?compById.get(p[0]):-1;
  const steps=(mp.routes||{})[String(comp)]||[];
  if(mp.main!==undefined&&comp>=0){
   if(comp===mp.main){
    html+=`<div class="route"><span>传送</span>无需传送，与你出发的区域连通</div>`;
   }else{
    if(steps.length){
     html+=`<div class="route route-steps"><span class="route-head">传送 ${steps.length} 次 · 每步所需妖丹</span>`+
      steps.map(([cfg,x1,y1,x2,y2],idx)=>{
       const pt=(mp.portals||{})[String(cfg)]||[];
       const name=pt[0]||('传送口 '+cfg);
       const cost=portalCost(mp,cfg);
       return `<button class="route-item" data-x="${x1}" data-y="${y1}">`+
        `<b class="ri-step">${idx+1}</b>`+
        `<span class="ri-name">${esc(name)}</span>`+
        `<i class="ri-coord">${Math.round(x1)},${Math.round(y1)} → ${Math.round(x2)},${Math.round(y2)}</i>`+
        `<em class="ri-cost ${pt[5]?'has':'free'}">${esc(cost)}</em>`+
        `</button>`;
      }).join('')+`</div>`;
    }else{
     html+=`<div class="route"><span>传送</span>这一片没有连通传送口，暂时过不去</div>`;
    }
   }
  }
  if(p[1]===5||p[1]===6){
   const pt=(mp.portals||{})[String(p[10])];
   const cost=portalCost(mp,p[10]);
   html+=`<div class="portal-cost"><span>${pt&&pt[2]?'双向':'单向'}传送</span>`+
    `<em class="ri-cost ${pt&&pt[5]?'has':'free'}">${esc(cost)}</em></div>`;
   const other=mp.pois.find(q=>(q[1]===5||q[1]===6)&&q[10]===p[10]&&q[0]!==p[0]);
   if(other)html+=`<div class="route"><span>${p[1]===5?'出口':'入口'}</span>`+
    `${p[1]===5?'穿过这里就是':'从这里可以回到'} ${Math.round(other[6])},${Math.round(other[7])}`+
    `<button class="route-item" data-x="${other[6]}" data-y="${other[7]}">定位</button></div>`;
  }
  $('pillinfo').innerHTML=html;
  drawRoute(comp>=0&&comp!==mp.main?steps:[]);
  ring.setAttribute('cx',p[6]/ts);ring.setAttribute('cy',p[7]/ts);ring.style.display='';
  markSelected(p[0]);
 }
 // 筛选：①显示对象 ②筛选条件（仅丹方/丹方属性） ③视图 ④搜索
 const mapbox=cv.parentElement,side=host.querySelector('.pill-side');
 const chips=$('pillchips'),elems=$('pillelems'),tierBox=$('pilltiers'),keys=$('pillkeys'),viewBox=$('pillview');
 // 元素从盘面数据里取：游戏新增五行/异种元素时自动出现在筛选里，不用改代码。
 const allElems=[...new Set(mp.pois.filter(p=>p[1]===1||p[1]===2).map(p=>p[2]).filter(Boolean).map(String))].sort((a,b)=>a-b);
 if(!allElems.length)allElems.push('1','2','3','4','5');
 const tierValues=[...new Set(mp.pois.filter(p=>p[1]===1||p[1]===2).map(p=>p[3]).filter(t=>t>0))].sort((a,b)=>a-b);
 const allTypes=()=>Object.keys(PILL_GROUPS);
 // 还原上次的筛选条件，按当前盘面能力裁剪
 pillFilter.types=pillFilter.types.filter(k=>PILL_GROUPS[k]);
 if(!pillFilter.types.length)pillFilter.types=allTypes();
 pillFilter.elements=pillFilter.elements.map(String).filter(v=>allElems.includes(v));
 pillFilter.tiers=pillFilter.tiers.map(String).filter(t=>tierValues.includes(+t));
 // 阶数是「选中即显示」的多选：空集合等于一个都不显示，所以默认全选
 if(!pillFilter.tiers.length)pillFilter.tiers=tierValues.map(String);
 pillFilter.keywords=pillFilter.keywords.filter(k=>PILL_KEYWORDS.includes(k));
 let keyExpanded=false;const expandedGroups=new Set();
 let fogOn=fogLayer?store.get('worldapart.pill.fog.v1',false)===true:false;
 if(fogLayer)mapbox.classList.toggle('showfog',fogOn);
 // 药材轨迹默认隐藏，避免 45 条线在盘面中间叠成一张网
 let herbOn=store.get('worldapart.pill.herbs.v1',false)===true;
 mapbox.classList.toggle('showherb',herbOn);
 function saveFilter(){
  store.set(PILL_FILTER_KEY,{types:pillFilter.types,elements:pillFilter.elements,
   tiers:pillFilter.tiers,keywords:pillFilter.keywords,q:pillFilter.q,hideDone:pillFilter.hideDone});
 }
 function typeKey(t){for(const k in PILL_GROUPS)if(PILL_GROUPS[k].includes(t))return k;return 'other'}
 function typeSelected(p){return pillFilter.types.some(k=>(PILL_GROUPS[k]||[]).includes(p[1]))}
 function isDone(p){return p[1]===2?learned.has(String((mp.pool||[])[p[5]]||'')):consumed.has(p[0])}
 // skip 表示统计某一组时先忽略该组自身条件，才能看出「勾上它还剩多少」
 function passBase(p,skip){
  if(p[1]===1||p[1]===2){
   if(skip!=='elements'&&p[2]>0&&!pillFilter.elements.includes(String(p[2])))return false;
   if(skip!=='tiers'&&!pillFilter.tiers.includes(String(p[3])))return false;
   if(skip!=='keywords'&&pillFilter.keywords.length){
    const text=pillText(p,mp);
    if(!pillFilter.keywords.some(k=>text.includes(k)))return false;
   }
  }
  if(pillFilter.hideDone&&consumed.has(p[0]))return false;
  const q=pillFilter.q.trim();
  if(q&&!(pillName(p,mp).includes(q)||pillText(p,mp).includes(q)))return false;
  return true;
 }
 function countsByType(){
  const out={};allTypes().forEach(k=>out[k]=0);
  mp.pois.forEach(p=>{
   if(!passBase(p,''))return;
   for(const k in PILL_GROUPS){if(PILL_GROUPS[k].includes(p[1])){out[k]++;break}}
  });
  return out;
 }
 function countsByElement(){
  const out={};
  mp.pois.forEach(p=>{
   if((p[1]!==1&&p[1]!==2)||!typeSelected(p)||!p[2]||!passBase(p,'elements'))return;
   out[p[2]]=(out[p[2]]||0)+1;
  });
  return out;
 }
 function countsByTier(){
  const out={};
  mp.pois.forEach(p=>{
   if((p[1]!==1&&p[1]!==2)||!typeSelected(p)||!passBase(p,'tiers'))return;
   out[p[3]]=(out[p[3]]||0)+1;
  });
  return out;
 }
 function countsByKeyword(){
  const out={};
  mp.pois.forEach(p=>{
   if((p[1]!==1&&p[1]!==2)||!typeSelected(p)||!passBase(p,'keywords'))return;
   const text=pillText(p,mp);if(!text)return;
   PILL_KEYWORDS.forEach(k=>{if(text.includes(k))out[k]=(out[k]||0)+1});
  });
  return out;
 }
 function renderTypes(){
  const counts=countsByType();
  chips.innerHTML=allTypes().map(k=>{
   const n=counts[k]||0;
   return `<button class="chip${pillFilter.types.includes(k)?' on':''}${n?'':' zero'}" data-chip="${k}">${PILL_LABELS[k]}<i>${n}</i></button>`;
  }).join('');
 }
 function renderElems(){
  const counts=countsByElement();
  elems.innerHTML=allElems.map(v=>{
   const n=counts[v]||0;
   return `<button class="chip${pillFilter.elements.includes(v)?' on':''}${n?'':' zero'}" data-elem="${v}">${PILL_ELEMENT[+v]||('元素'+v)}<i>${n}</i></button>`;
  }).join('');
 }
 function renderTiers(){
  const counts=countsByTier();
  tierBox.innerHTML=tierValues.length?tierValues.map(t=>{
   const n=counts[t]||0;
   return `<button class="chip${pillFilter.tiers.includes(String(t))?' on':''}${n?'':' zero'}" data-tier="${t}">${t} 阶<i>${n}</i></button>`;
  }).join(''):'<span class="fhint">当前盘面没有阶数</span>';
 }
 function renderKeys(){
  const counts=countsByKeyword();
  const positive=PILL_KEYWORDS.filter(k=>counts[k]).sort((a,b)=>counts[b]-counts[a]);
  const pinned=pillFilter.keywords.filter(k=>!positive.includes(k));
  const shown=keyExpanded?positive.concat(pinned):[...new Set([...positive.slice(0,8),...pinned])];
  const total=positive.length+pinned.length;
  keys.innerHTML=shown.map(k=>
   `<button class="chip${pillFilter.keywords.includes(k)?' on':''}" data-key="${k}">${k}<i>${counts[k]||0}</i></button>`).join('')+
   (total>8?`<button class="chip more" data-op="more" data-row="keywords">${keyExpanded?'收起':'更多 '+total}</button>`:'');
 }
 function renderView(){
  viewBox.innerHTML=(fogLayer?`<button class="chip${fogOn?' on':''}" data-view="fog">迷雾</button>`:'')+
   `<button class="chip${herbOn?' on':''}" data-view="herb">药材路线</button>`+
   `<button class="chip${pillFilter.hideDone?' on':''}" data-view="done">隐藏已拾取</button>`;
 }
 function renderCond(){
  $('pillcond').classList.toggle('off',!(pillFilter.types.includes('recipe')||pillFilter.types.includes('effect')));
 }
 function renderActive(){
  const tags=[];
  if(pillFilter.types.length!==allTypes().length)
   pillFilter.types.forEach(k=>tags.push(['types',k,PILL_LABELS[k]]));
  if(pillFilter.elements.length!==5)
   pillFilter.elements.forEach(v=>tags.push(['elements',v,(PILL_ELEMENT[+v]||('元素'+v))+'行']));
  if(pillFilter.tiers.length!==tierValues.length)
   pillFilter.tiers.forEach(t=>tags.push(['tiers',t,t+' 阶']));
  pillFilter.keywords.forEach(k=>tags.push(['keywords',k,k]));
  if(pillFilter.q.trim())tags.push(['q','hidden','搜索 '+pillFilter.q.trim()]);
  if(pillFilter.hideDone)tags.push(['done','hidden','隐藏已拾取']);
  if(herbOn)tags.push(['herb','hidden','药材路线']);
  if(fogOn)tags.push(['fog','hidden','迷雾']);
  $('pillactive').innerHTML=tags.length?
   '<span class="ptag-label">已选</span>'+tags.map(([row,v,label])=>
    `<button class="ptag" data-tagrow="${row}" data-tagval="${esc(v)}">${esc(label)}<b>×</b></button>`).join('')+
    '<button class="ptag clear" data-tagrow="all">清空</button>'
   :'<span class="ptag-label">未设筛选，显示全部拾取点</span>';
 }
 function itemHtml(p){
  const isRecipe=p[1]===2,rid=isRecipe?String((mp.pool||[])[p[5]]||''):'';
  let sub;
  if(isRecipe){sub=`${PILL_ELEMENT[p[2]]||''}·${p[3]||0}阶`;if(learned.has(rid))sub+=' · 已学会'}
  else if(p[1]===1){const e=(mp.effects||{})[String(p[4])];sub=(e&&e[7])||'丹方属性';if(p[3])sub+=' · '+p[3]+'阶'}
  else if(p[1]===4){const r=(mp.rewards||{})[String(p[8])];sub='奖励'+(r?' · '+qName(r[2]):'')}
  else if(p[1]===5||p[1]===6)sub='传送口 · '+portalCost(mp,p[10]);
  else sub=PILL_TYPE[p[1]]||'其他';
  const comp=compById.has(p[0])?compById.get(p[0]):-1;
  if(p[1]!==5&&p[1]!==6&&mp.main!==undefined&&comp>=0&&comp!==mp.main)sub+=' · 需传送';
  return `<div class="pill-item${isDone(p)?' done':''}" data-id="${p[0]}">`+
   `<i class="dotmark" style="background:${poiFill(p)}"></i>`+
   `<span class="nm">${esc(pillName(p,mp))}</span><span class="tp">${esc(sub)}</span></div>`;
 }
 function renderList(matched){
  const picked=matched.filter(p=>consumed.has(p[0])).length;
  $('pillsum').innerHTML=`结果 <b>${matched.length}</b> 项 · 已拾取 ${picked} 项`;
  if(!matched.length){
   const acts=[];
   if(pillFilter.tiers.length<tierValues.length)acts.push('<button type="button" class="pill-act" data-relax="tiers">放宽到全部阶数</button>');
   if(pillFilter.keywords.length)acts.push('<button type="button" class="pill-act" data-relax="keywords">清空药效</button>');
   if(pillFilter.elements.length!==5)acts.push('<button type="button" class="pill-act" data-relax="elements">恢复全部五行</button>');
   if(pillFilter.q.trim())acts.push('<button type="button" class="pill-act" data-relax="q">清空搜索</button>');
   if(pillFilter.hideDone)acts.push('<button type="button" class="pill-act" data-relax="done">显示已拾取</button>');
   acts.push('<button type="button" class="pill-act" data-relax="all">清空全部筛选</button>');
   $('pilllist').innerHTML='<div class="empty" style="margin:0;border:0">没有符合条件的拾取点'+
    '<div class="empty-acts">'+acts.join('')+'</div></div>';
   return;
  }
  const groups={};matched.forEach(p=>{const k=typeKey(p[1]);(groups[k]=groups[k]||[]).push(p)});
  const keysNow=PILL_ORDER.filter(k=>groups[k]);
  const single=keysNow.length===1;
  $('pilllist').innerHTML=keysNow.map(k=>{
   const list=k==='recipe'?groups[k].slice().sort((a,b)=>(b[3]||0)-(a[3]||0)):groups[k];
   const limit=expandedGroups.has(k)?list.length:60;
   return '<div class="pill-group"><div class="pghead"><span class="pgname">'+esc(PILL_LABELS[k])+'</span>'+
    '<i class="pgcount">'+list.length+'</i>'+
    (single?'':'<button type="button" class="pgonly" data-only="'+k+'">只看这类</button>')+'</div>'+
    list.slice(0,limit).map(itemHtml).join('')+
    (list.length>limit?'<button type="button" class="pgmore" data-expand="'+k+'">展开全部 '+list.length+' 项</button>':'')+
    '</div>';
  }).join('');
 }
 function markSelected(id){
  document.querySelectorAll('#pilllist .pill-item.focus').forEach(n=>n.classList.remove('focus'));
  const node=document.querySelector('#pilllist .pill-item[data-id="'+id+'"]');
  // 仅高亮列表项，不滚动页面/列表：地图点选时整页曾因 scrollIntoView 跳到下方列表
  if(node)node.classList.add('focus');
 }
 function resetAll(){
  pillFilter.types=allTypes();pillFilter.elements=allElems.slice();
  pillFilter.tiers=tierValues.map(String);pillFilter.keywords=[];pillFilter.q='';pillFilter.hideDone=false;
  $('pillq').value='';
 }
 function applyOp(row,op){
  if(op==='more'){keyExpanded=!keyExpanded;renderKeys();return}
  if(row==='types')pillFilter.types=op==='all'?allTypes():[];
  else if(row==='elements')pillFilter.elements=op==='all'?allElems.slice():[];
  else if(row==='tiers')pillFilter.tiers=op==='all'?tierValues.map(String):[];
  else if(row==='keywords')pillFilter.keywords=[];
  applyFilter();
 }
 function removeTag(row,val){
  if(row==='all')resetAll();
  else if(row==='q'){pillFilter.q='';$('pillq').value=''}
  else if(row==='done')pillFilter.hideDone=false;
  else if(row==='fog'){fogOn=false;if(fogLayer)mapbox.classList.remove('showfog');store.set('worldapart.pill.fog.v1',false)}
  else if(row==='herb'){herbOn=false;mapbox.classList.remove('showherb');store.set('worldapart.pill.herbs.v1',false)}
  else if(row==='types')pillFilter.types=pillFilter.types.filter(x=>x!==val);
  else if(row==='elements')pillFilter.elements=pillFilter.elements.filter(x=>x!==val);
  else if(row==='tiers')pillFilter.tiers=pillFilter.tiers.filter(x=>x!==val);
  else if(row==='keywords')pillFilter.keywords=pillFilter.keywords.filter(x=>x!==val);
  applyFilter();
 }
 function relaxFilter(kind){
  if(kind==='all')resetAll();
  else if(kind==='tiers')pillFilter.tiers=tierValues.map(String);
  else if(kind==='keywords')pillFilter.keywords=[];
  else if(kind==='elements')pillFilter.elements=allElems.slice();
  else if(kind==='q'){pillFilter.q='';$('pillq').value=''}
  else if(kind==='done')pillFilter.hideDone=false;
  applyFilter();
 }
 side.addEventListener('click',e=>{
  const op=e.target.closest('[data-op]');
  if(op){applyOp(op.dataset.row,op.dataset.op);return}
  const view=e.target.closest('[data-view]');
  if(view){
   if(view.dataset.view==='fog'&&fogLayer){
    fogOn=!fogOn;mapbox.classList.toggle('showfog',fogOn);
    store.set('worldapart.pill.fog.v1',fogOn);renderView();renderActive();return;
   }
   if(view.dataset.view==='herb'){
    herbOn=!herbOn;mapbox.classList.toggle('showherb',herbOn);
    store.set('worldapart.pill.herbs.v1',herbOn);renderView();renderActive();return;
   }
   if(view.dataset.view==='done'){pillFilter.hideDone=!pillFilter.hideDone;applyFilter();return}
  }
  const tag=e.target.closest('[data-tagrow]');
  if(tag){removeTag(tag.dataset.tagrow,tag.dataset.tagval);return}
  const relax=e.target.closest('[data-relax]');
  if(relax){relaxFilter(relax.dataset.relax);return}
  const only=e.target.closest('[data-only]');
  if(only){pillFilter.types=[only.dataset.only];applyFilter();return}
  const more=e.target.closest('[data-expand]');
  if(more){expandedGroups.add(more.dataset.expand);applyFilter();return}
  const item=e.target.closest('[data-id]');
  if(item&&item.classList.contains('pill-item')){
   const p=mp.pois.find(x=>String(x[0])===item.dataset.id);
   if(p)showPoi(p);
   return;
  }
  const btn=e.target.closest('.chip');if(!btn)return;
  if(btn.dataset.chip!==undefined){
   const key=btn.dataset.chip;
   pillFilter.types=e.altKey?[key]:(pillFilter.types.includes(key)?pillFilter.types.filter(x=>x!==key):pillFilter.types.concat(key));
   applyFilter();return;
  }
  if(btn.dataset.elem!==undefined){
   const v=btn.dataset.elem;
   pillFilter.elements=e.altKey?[v]:(pillFilter.elements.includes(v)?pillFilter.elements.filter(x=>x!==v):pillFilter.elements.concat(v));
   applyFilter();return;
  }
  if(btn.dataset.tier!==undefined){
   const t=btn.dataset.tier;
   pillFilter.tiers=e.altKey?[t]:(pillFilter.tiers.includes(t)?pillFilter.tiers.filter(x=>x!==t):pillFilter.tiers.concat(t));
   applyFilter();return;
  }
  if(btn.dataset.key!==undefined){
   const k=btn.dataset.key;
   pillFilter.keywords=e.altKey?[k]:(pillFilter.keywords.includes(k)?pillFilter.keywords.filter(x=>x!==k):pillFilter.keywords.concat(k));
   applyFilter();return;
  }
 });
 const mapChips=$('pillmaps');
 if(mapChips)mapChips.onclick=e=>{
  const btn=e.target.closest('[data-map]');if(!btn)return;
  store.set('worldapart.pill.map.v1',+btn.dataset.map);initPill();
 };
 $('pillq').value=pillFilter.q;
 $('pillq').oninput=e=>{pillFilter.q=e.target.value;applyFilter()};
 // 点功效词 = 直接填入搜索并过滤，不需要知道丹方名
 document.querySelectorAll('#pill [data-eff]').forEach(btn=>{
  btn.onclick=()=>{pillFilter.q=btn.dataset.eff;$('pillq').value=pillFilter.q;applyFilter()};
 });
 // 搜索命中列表：直接把「在哪、怎么去」摊在搜索框下面，不用再去盘面上找点。
 function renderHits(){
  const box=$('pillhits');if(!box)return;
  const q=pillFilter.q.trim();
  if(!q){box.innerHTML='';box.classList.remove('on');return}
  // 按功效搜时属性点很多，先把真正的丹方排在前面，避免被冲淡
  const hits=mp.pois.filter(p=>passBase(p,'')&&(pillName(p,mp).includes(q)||pillText(p,mp).includes(q)))
   .sort((a,b)=>(a[1]===2?0:1)-(b[1]===2?0:1)).slice(0,8);
  if(!hits.length){box.innerHTML='<div class="phit phit-none">没有匹配的丹方或拾取点</div>';box.classList.add('on');return}
  box.innerHTML=hits.map((p,i)=>{
   const comp=compById.has(p[0])?compById.get(p[0]):-1;
   const steps=(mp.routes||{})[String(comp)]||[];
   const go=(comp>=0&&comp===mp.main)?'无需传送':(steps.length?'传送 '+steps.length+' 次':'');
   const rid=p[1]===2?String((mp.pool||[])[p[5]]||''):'';
   const rec=p[1]===2?(mp.recipes||{})[rid]:null;
   const flags=[consumed.has(p[0])?'已拾取':(p[1]===2&&learned.has(rid)?'已学会':'')].filter(Boolean).join(' · ');
   return `<button type="button" class="phit" data-hit="${i}" title="${esc((rec&&rec.d)||'')}"><i class="phit-dot" style="background:${poiFill(p)}"></i>`+
    `<b>${esc(pillName(p,mp))}</b><span>${Math.round(p[6])}, ${Math.round(p[7])}</span>`+
    `${go?`<em>${go}</em>`:''}${flags?`<em class="phit-flag">${flags}</em>`:''}</button>`;
  }).join('');
  box.classList.add('on');
  box.querySelectorAll('[data-hit]').forEach(btn=>{btn.onclick=()=>{
   showPoi(hits[+btn.dataset.hit]);
   // 点完命中要立刻看到详情，否则还要再滚一次，闭环就断了
   const info=$('pillinfo');if(info)info.scrollIntoView({block:'nearest'});
  }});
 }
 function applyFilter(){
  const matched=[];
  mp.pois.forEach((p,idx)=>{
   const ok=typeSelected(p)&&passBase(p,'');
   dots[idx].classList.toggle('off',!ok);
   if(ok)matched.push(p);
  });
  renderTypes();renderElems();renderTiers();renderKeys();renderView();renderCond();renderActive();
  renderList(matched);
  renderHits();
  saveFilter();
 }
 applyFilter();
 // 默认示例：自动选中一条「需传送」的丹方，一眼看到 选丹方→路线→妖丹 的完整链路
 (function(){
  let best=null,score=-1;
  mp.pois.forEach(p=>{
   if(p[1]!==2)return;
   const comp=compById.has(p[0])?compById.get(p[0]):-1;
   if(mp.main===undefined||comp<0||comp===mp.main)return;
   const r2=String((mp.pool||[])[p[5]]||'');
   const r=(mp.recipes||{})[r2]||{};
   const s=((r.d||'').includes('攻击')?100:0)+((r.t||0)*10);
   if(s>score){score=s;best=p}
  });
  if(!best)best=mp.pois.find(p=>{if(p[1]!==2)return false;const c=compById.has(p[0])?compById.get(p[0]):-1;return c>=0&&c!==mp.main});
  if(!best)best=mp.pois.find(p=>p[1]===2);
  if(best)showPoi(best);
 })();
 // 丹方手记
 const manual=st.manual||[];
 if(manual.length){
  const recipePoi={};
  mp.pois.forEach(p=>{if(p[1]===2){const rid=(mp.pool||[])[p[5]];if(rid)recipePoi[String(rid)]=p}});
  $('pillmanual').innerHTML=manual.map(r=>`<div class="manual-item" data-recipe="${esc(String(r.id))}">`+
   `<span class="nm">${esc(r.name)}</span>`+
   `<span class="tag">${esc(PILL_ELEMENT[r.element]||'')}${r.tier?`·${r.tier}阶`:''}</span>`+
   `<span class="tag">${r.grade} 品</span><span class="tag">丹毒 ${r.toxin}</span>`+
   `<span class="tag">药效 ${(r.effects||[]).length}</span></div>`).join('');
  $('pillmanual').onclick=e=>{
   const it=e.target.closest('[data-recipe]');if(!it)return;
   const p=recipePoi[it.dataset.recipe];
   if(p)showPoi(p);
   else $('pillinfo').innerHTML='该丹方在当前盘面上没有固定拾取点';
  };
 }
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['pill']=initPill;
})();
