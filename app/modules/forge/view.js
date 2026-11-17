/* 炼器：页面渲染。分区锚点导航 + 主次分明的卡片分区，器胚目录按境界/部位两级折叠。 */
(function(){
const FORGE_ELEM_COLORS=['#8b93a1','#e6dcae','#8ccf92','#7fc0ee','#ee9a86','#d8b273'];
const FORGE_FILTER_KEY='worldapart.forge.filters.v1';
function initForge(){
 const m=DATA.modules&&DATA.modules.forge;if(!m)return;const host=$('forge'),st=m.rows||{};
 const elem=id=>(m.elements||{})[String(id)]||'';
 const slotName=id=>(m.slots||{})[String(id)]||'';
 const realmName=id=>(m.realms||{})[String(id)]||('境界 '+id);
 const attrName=id=>(m.attributes||{})[String(id)]||('属性 '+id);
 const tierName=id=>((m.score_tiers||[]).find(x=>Number(x.id)===Number(id))||{}).name||(id+' 阶');
 const ratio=(a,b)=>b?Math.min(100,Math.round(a*100/b)):0;
 function grid(p){
  const n=Number(p.board)||5,blocked=new Set((p.blocked||[]).map(c=>c[0]+','+c[1])),bonus={};
  (p.bonus||[]).forEach(c=>bonus[c[0]+','+c[1]]=c[2]);
  let cells='';
  for(let y=0;y<n;y++)for(let x=0;x<n;x++){
   const key=x+','+y;let cls='fcell',style='';
   if(blocked.has(key))cls+=' block';
   else if(bonus[key])style='background:'+(FORGE_ELEM_COLORS[bonus[key]]||'#3a4652')+';opacity:.55';
   cells+='<i class="'+cls+'" style="'+style+'" title="'+x+','+y+'"></i>';
  }
  return '<div class="fgrid" style="grid-template-columns:repeat('+n+',20px)">'+cells+'</div>';
 }
 const cards=[
  ['炼器等级','Lv'+st.level,st.level_title||''],
  ['经验',st.exp+' / '+(st.exp_need||'—'),st.exp_need&&st.exp>=st.exp_need?'已达升级线':'继续炼制积累'],
  ['真火',st.true_fire,'本级基础值'],
  ['天赋点',st.talent_points,'已解锁 '+(st.unlocked||[]).length+' · 已领悟 '+(st.learned||[]).length],
  ['最高器契',st.best_score,st.best_tier_name||'—'],
  ['器胚库存',(st.embryo_total||0)+' 件',(st.embryos||[]).length+' 种'],
 ].map(([k,v,s])=>'<div class="card"><div class="k">'+esc(k)+'</div><div class="v">'+esc(v)+'<span> '+esc(s)+'</span></div></div>').join('');
 // 分区标题：卡片包裹，区块之间视觉分层
 function fzone(id,title,sub,body){
  return '<section class="fzone" id="'+id+'"><h2 class="fzone-head">'+esc(title)+'<span>'+esc(sub)+'</span></h2>'+body+'</section>';
 }
 // 我的器胚：有五行缺口的排最前并标「缺料」
 const embryoMissing=e=>(e.need||[]).some(r=>r.gap>0);
 const embryosSorted=(st.embryos||[]).slice().sort((a,b)=>(embryoMissing(b)?1:0)-(embryoMissing(a)?1:0)||Number(b.realm)-Number(a.realm)||Number(a.slot)-Number(b.slot)||Number(a.id)-Number(b.id));
 const embryoRows=embryosSorted.map(e=>{
  const missing=embryoMissing(e);
  const need=(e.need||[]).map(r=>esc(elem(r.e))+'×'+r.need+(r.gap?' <span class="fgap">缺 '+r.gap+'</span>':' <span class="fok">足</span>')).join(' · ');
  const wash=(e.effects||[]).map(x=>esc(elem(x.e))+' '+x.energy+' · '+esc(x.mat_name)+'×'+x.count).join('；')||'—';
  return '<tr class="row'+(missing?' fmiss-row':'')+'"><td><div class="who">'+esc(e.name)+(missing?'<span class="badge fmiss">缺料</span>':'')+'</div><div class="bed">'+esc(e.realm_name)+' · '+esc(e.slot_name)+' · '+e.board+'×'+e.board+'</div></td>'+
   '<td style="width:56px">×'+e.count+'</td><td>'+need+'</td><td class="muted">'+wash+'</td><td style="width:84px">'+e.rec_total+' 灵性</td></tr>';
 }).join('');
 const pityRows=(st.pity||[]).map(p=>{
  const left=Math.max(0,p.total-p.count);
  return '<tr class="row"><td>'+esc(p.realm_name)+'</td><td>'+esc(p.quality_name)+'：'+p.count+' / '+p.total+'</td>'+
   '<td class="muted">'+(left?'还差 '+left+' 次':'下一次必出')+'</td><td style="width:150px"><div class="bar"><i style="width:'+ratio(p.count,p.total)+'%"></i></div></td></tr>';
 }).join('');
 const elemCards=(st.elements||[]).map(e=>'<div class="card"><div class="k">'+esc(elem(e.element))+'行材料</div><div class="v">'+e.count+' <span>件 · 灵性 '+e.spirit+'</span></div></div>').join('')||'<div class="card"><div class="k">材料</div><div class="v">0 <span>件</span></div></div>';
 const matRows=(st.materials||[]).map(r=>'<tr class="row"><td><div class="who fq'+r.quality+'">'+esc(r.name)+'</div><div class="bed">'+esc(elem(r.element))+' · '+esc(realmName(r.realm))+'</div></td>'+
  '<td style="width:56px">×'+r.count+'</td><td style="width:60px">'+r.spirit+'</td><td class="muted">灵性合计 '+(r.count*r.spirit)+'</td></tr>').join('');
 const artRows=(st.artifacts||[]).map(a=>{
  const affixes=(a.affixes||[]).map(x=>'<span class="fchip fq'+x.quality+'">'+esc(x.text)+(x.pending?'（未激活）':'')+'</span>').join('')||'<span class="muted">无词条</span>';
  const attrs=(a.attrs||[]).map(pair=>esc(pair[0])+' +'+pair[1]).join(' · ')||'—';
  const wash=(a.wash||[]).map(w=>esc(elem(w.e))+' '+esc(w.material)+'×'+w.count).join('；')||'—';
  const pity=(a.pity||[]).map(p=>esc(p.name)+' '+p.count+'/'+p.total).join(' · ')||'—';
  return '<details class="fart"><summary><span class="fname">'+esc(a.name)+'</span>'+
   (a.equipped?'<span class="badge dao">已装备</span>':'')+
   (a.slot_name?'<span class="badge">'+esc(a.slot_name)+'</span>':'')+
   '<span class="badge">'+esc(a.realm_name)+'</span>'+
   '<span class="badge">'+(a.crafted?esc(a.tier_name||'未定阶'):'非炼器所得')+'</span>'+
   '<span class="fstat">器契 '+a.score+' · '+(a.affixes||[]).length+' 条词条</span></summary>'+
   '<div class="fbody"><div class="fline"><b>基础属性</b>'+attrs+'</div>'+
   '<div class="fline"><b>词条</b><span class="fchips">'+affixes+'</span></div>'+
   '<div class="fline"><b>洗练材料</b>'+wash+'</div>'+
   '<div class="fline"><b>洗练保底</b>'+pity+'</div></div></details>';
 }).join('')||'<div class="empty">还没有法宝数据</div>';
 const realms=uniq((m.catalog||[]).map(p=>String(p.realm)));
 const slots=uniq((m.catalog||[]).map(p=>String(p.slot)));
 let state=Object.assign({q:'',realm:'',slot:''},store.get(FORGE_FILTER_KEY,{}));
 function protoCard(p){
  const need=(p.need||[]).map(r=>elem(r.e)+'×'+r.v).join(' · ')||'无指定';
  const rec=(p.rec||[]).map(r=>elem(r.e)+' '+r.v).join(' · ')||'—';
  const washSlots=(p.effects||[]).map(x=>'<span class="fchip fq3">'+esc(elem(x.e))+' '+x.energy+' · '+esc(x.mat_name)+'×'+x.count+'</span>').join('')||'<span class="muted">无词条槽</span>';
  const tierHtml=(p.tiers||[]).map(t=>'<div class="fline"><b>'+esc(tierName(t.t))+'</b>门槛 '+t.min+' · '+((t.attrs||[]).map(pair=>esc(attrName(pair[0]))+' +'+pair[1]).join(' / ')||'—')+'</div>').join('');
  const tiers=(p.tiers||[]).map(t=>tierName(t.t)+' '+t.min).join(' / ');
  return '<details class="fproto"><summary><span class="fname">'+esc(p.name)+'</span>'+
   '<span class="badge">'+esc(realmName(p.realm))+'</span>'+
   '<span class="badge">'+esc(slotName(p.slot))+'</span>'+
   '<span class="badge">'+p.board+'×'+p.board+'</span>'+
   '<span class="badge">需 '+esc(need)+'</span>'+
   '<span class="ftiers">'+esc(tiers)+'</span></summary>'+
   '<div class="fbody"><div class="fcols">'+
   '<div class="fcol"><div class="fcol-t">棋盘（虚线＝封炉格，带色格＝聚灵格）</div>'+grid(p)+'</div>'+
   '<div class="fcol"><div class="fcol-t">炼制要求</div><div class="fline">五行需求 <b>'+esc(need)+'</b></div>'+
   '<div class="fline">推荐灵蕴 '+esc(rec)+'（合计 '+p.rec_total+'）</div><div class="fline">真火消耗 '+p.energy+'</div></div>'+
   '<div class="fcol"><div class="fcol-t">词条槽 · 洗练材料</div><div class="fchips">'+washSlots+'</div></div>'+
   '<div class="fcol"><div class="fcol-t">四阶门槛</div>'+tierHtml+'</div>'+
   '</div></div></details>';
 }
 function groupCatalog(list){
  const byRealm={};
  list.forEach(p=>{(byRealm[String(p.realm)]=byRealm[String(p.realm)]||[]).push(p)});
  // 有筛选/搜索时自动展开命中分组；默认全部收起，避免几百件器胚一次性铺开
  const activeFilter=state.realm!==''||state.slot!==''||state.q.trim()!=='';
  return Object.keys(byRealm).sort((a,b)=>Number(b)-Number(a)).map(r=>{
   const items=byRealm[r];
   const bySlot={};
   items.forEach(p=>{(bySlot[String(p.slot)]=bySlot[String(p.slot)]||[]).push(p)});
   const slotHtml=Object.keys(bySlot).sort((a,b)=>Number(a)-Number(b)).map(s=>{
    const protos=bySlot[s];
    return '<div class="fgrp-slot"><div class="fgrp-slot-h">'+esc(slotName(s))+'<i>'+protos.length+'</i></div>'+protos.map(protoCard).join('')+'</div>';
   }).join('');
   return '<details class="fgrp"'+(activeFilter?' open':'')+'><summary>'+esc(realmName(r))+'<span class="fgrp-n">'+items.length+' 件</span></summary><div class="fgrp-body">'+slotHtml+'</div></details>';
  }).join('');
 }
 function renderList(){
  const q=state.q.trim();
  const list=(m.catalog||[]).filter(p=>(state.realm===''||String(p.realm)===state.realm)&&
   (state.slot===''||String(p.slot)===state.slot)&&
   (!q||p.name.includes(q)||(p.tiers||[]).some(t=>String(t.out_name||'').includes(q))));
  $('fgcount').textContent='筛选结果：'+list.length+' / '+(m.catalog||[]).length+' 件器胚';
  $('fglist').innerHTML=groupCatalog(list)||'<div class="empty">没有符合条件的器胚</div>';
 }
 function renderRealmChips(){realmBox.innerHTML='<span class="chip-label">境界</span>'+[['','全部']].concat(realms.map(r=>[r,realmName(r)])).map(
   ([value,label])=>'<button class="chip'+(state.realm===value?' on':'')+'" data-realm="'+esc(value)+'">'+esc(label)+'</button>').join('');
 }
 function renderSlotChips(){slotBox.innerHTML='<span class="chip-label">部位</span>'+[['','全部']].concat(slots.map(s=>[s,slotName(s)])).map(
   ([value,label])=>'<button class="chip'+(state.slot===value?' on':'')+'" data-slot="'+esc(value)+'">'+esc(label)+'</button>').join('');
 }
 const navItems=[
  ['fg-my-embryo','我的器胚',(st.embryos||[]).length],
  ['fg-my-artifact','我的法宝',(st.artifacts||[]).length],
  ['fg-catalog','全部器胚',(m.catalog||[]).length],
  ['fg-materials','材料盘点',(st.materials||[]).length],
  ['fg-pity','洗练保底',(st.pity||[]).length],
 ];
 const nav='<nav class="fnav">'+navItems.map(([id,label,n])=>'<a class="fnav-item" href="#'+id+'">'+esc(label)+'<i>'+n+'</i></a>').join('')+'</nav>';
 const myEmbryoBody=(st.embryos||[]).length?'<table><thead><tr><th>器胚</th><th>数量</th><th>五行需求 / 缺口</th><th>洗练材料</th><th>推荐灵性</th></tr></thead><tbody>'+embryoRows+'</tbody></table>':'<div class="empty">背包里没有器胚</div>';
 const myArtifactBody=artRows;
 const catalogBody='<div class="search-panel"><div class="search-fields" style="grid-template-columns:1fr"><label class="search-field"><span>找器胚 / 法宝</span><input id="fgq" placeholder="输入器胚或法宝名称"></label></div></div>'+
  '<div class="chips" id="fgrealm"></div><div class="chips" id="fgslot"></div><div id="fgcount" class="result-info"></div><div id="fglist"></div>';
 const materialsBody='<div class="cards">'+elemCards+'</div>'+((st.materials||[]).length?'<table><thead><tr><th>材料</th><th>数量</th><th>灵性</th><th></th></tr></thead><tbody>'+matRows+'</tbody></table>':'<div class="empty">背包里没有炼器材料</div>');
 const pityBody=(st.pity||[]).length?'<table><tbody>'+pityRows+'</tbody></table>':'<div class="empty">暂无洗练保底数据</div>';
 host.innerHTML=sourceHtml(m)+nav+'<div class="cards">'+cards+'</div>'+
  fzone('fg-my-embryo','我的器胚','按五行缺口排序 · 缺料置顶',myEmbryoBody)+
  fzone('fg-my-artifact','我的法宝','已炼成 · 器契分数 / 词条 / 洗练',myArtifactBody)+
  fzone('fg-catalog','全部器胚','按境界 + 部位折叠 · 高境界在前',catalogBody)+
  fzone('fg-materials','材料盘点','按五行统计件数与灵性',materialsBody)+
  fzone('fg-pity','洗练保底','同境界、同品质法宝共享计数',pityBody)+
  '<div class="tip">五行需求按“该五行精粹需占几格”计算；缺口＝背包该五行材料总件数－需求格数，只作库存参考，实际摆盘还受封炉格与聚灵格影响。器契达到凡/玄/地/天四档门槛即对应阶，天阶最高。</div>';
 const realmBox=$('fgrealm'),slotBox=$('fgslot');
 $('fgq').value=state.q;
 $('fgq').oninput=e=>{state.q=e.target.value;renderList()};
 realmBox.onclick=e=>{const btn=e.target.closest('[data-realm]');if(!btn)return;state.realm=btn.dataset.realm;store.set(FORGE_FILTER_KEY,state);renderRealmChips();renderList()};
 slotBox.onclick=e=>{const btn=e.target.closest('[data-slot]');if(!btn)return;state.slot=btn.dataset.slot;store.set(FORGE_FILTER_KEY,state);renderSlotChips();renderList()};
 renderRealmChips();renderSlotChips();renderList();
}
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['forge']=initForge;
})();
