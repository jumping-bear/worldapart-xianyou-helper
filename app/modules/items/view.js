/* NPC 物品：页面渲染。主视图为「物品 → 持有者」反向索引，按品质从高到低分组；
   可切换到「按 NPC 看」的完整清单视角。 */
(function(){
const ITEM_KEY='worldapart.item.filters.v1';
const ITEM_DEFAULTS={q:'',npc:'',region:'',location:'',type:'',quality:'',steal:'',demand:'',gift:''};
let itemFilters=Object.assign({},ITEM_DEFAULTS,store.get(ITEM_KEY,{}));
let itemView=store.get('worldapart.item.view.v1','item');
if(itemView!=='npc')itemView='item';
let itemCache=null;
let itemRenderState={groups:{},q:'',npcQ:''};
let itemSort=store.get('worldapart.item.sort.v1','rate');
let itemPage={};
function fqClass(q){return 'fq'+(q==null||q===''?0:q)}
function qualityLabel(q){return q==null||q===''?'未知品质':(Number(q)>0?'品质 '+q:'无品质')}
function itemRateOf(o){return o.v.ok&&o.t.steal?o.t.steal.rate:-1}
function itemSortOwners(owners){
 const list=owners.slice();
 list.sort((a,b)=>{
  const okDiff=Number(b.v.ok)-Number(a.v.ok);
  if(okDiff)return okDiff;
  if(itemSort==='count'&&b.count!==a.count)return b.count-a.count;
  const rateDiff=itemRateOf(b)-itemRateOf(a);
  if(itemSort!=='name'&&rateDiff)return rateDiff;
  if(itemSort==='rate'&&b.count!==a.count)return b.count-a.count;
  return String(a.row.who).localeCompare(String(b.row.who),'zh-CN');
 });
 return list;
}
function stealDetailHtml(rule){
 if(!rule)return '';
 const parts=['一次最多 <b>'+rule.count+'</b> 个','善恶值 <b>'+rule.alignment+'</b>','好感 <b>'+rule.intimacy+'</b>'];
 if(rule.kill)parts.push('<span class="bad">失手触发击杀</span>');
 return '<span class="steal-detail">'+parts.join(' · ')+'</span>';
}
function itemOwnersHtml(iid){
 const state=itemRenderState,group=state.groups[iid];
 if(!group)return '';
 const all=itemSortOwners(group.owners);
 const limit=30*(itemPage[iid]||1),shown=all.slice(0,limit),rest=all.length-shown.length;
 const owners=shown.map(o=>{
  const badge=o.v.ok?'<span class="badge steal">可偷</span>':'<span class="badge nosteal">'+esc(o.v.label)+'</span>';
  let rate='';
  if(o.v.ok&&o.t.steal){
   rate='<span class="steal-ok">'+o.t.steal.rate+'%<span class="ratebar"><i style="width:'+Math.max(0,Math.min(100,o.t.steal.rate))+'%"></i></span></span>';
   if(o.t.steal.kill)rate+='<span class="badge deadly">致命</span>';
  }
  const inPool=(o.row.demand||[]).some(id=>String(id)===String(iid));
  const giftAble=(o.row.gift||[]).some(id=>String(id)===String(iid));
  const demandBadge=!inPool?'':(o.t.demand?'<span class="badge demand">索要 -'+esc(o.t.demand_cost||0)+' 好感</span>':'<span class="badge demand-absent">不可索要</span>');
  const giftBadge=giftAble?'<span class="badge gift">可赠</span>':'';
  return '<details class="npc owner" data-uid="'+esc(o.row.uid)+'" data-item="'+esc(iid)+'"><summary><span class="who">'+hi(o.row.who,state.npcQ)+'</span>'+(o.row.realm?'<span class="badge">'+esc(o.row.realm)+'</span>':'')+badge+demandBadge+giftBadge+'<span class="badge">×'+esc(o.count)+'</span>'+rate+'<span class="location">'+esc(o.row.location_path||o.row.location||'未知地点')+'</span>'+stealDetailHtml(o.v.ok?o.t.steal:null)+'</summary><div class="slots"></div></details>';
 }).join('');
 const blocked=all.filter(o=>!o.v.ok).length;
 const labels={rate:'按成功率从高到低',count:'按持有数量从多到少',name:'按 NPC 名称排序'};
 const tools='<div class="item-tools">'
  +['rate','count','name'].map(k=>'<button type="button" class="sortbtn'+(itemSort===k?' on':'')+'" data-sort="'+k+'">'+({rate:'成功率',count:'数量',name:'名称'})[k]+'</button>').join('')
  +'<span class="meta">'+esc(labels[itemSort]||labels.rate)+'</span></div>';
 const head='<div class="owners-label">'+group.stealable+' 位可偷'+(blocked?' · '+blocked+' 位不可偷':'')+'；点击 NPC 可在下方展开其全部持有物品</div>';
 const more=rest?'<button type="button" class="loadmore" data-more="'+esc(iid)+'">显示更多（还有 '+rest+' 位）</button>':'';
 return tools+head+owners+more;
}
function itemIndex(){
 const m=DATA.modules.items;
 if(!itemCache||itemCache.m!==m)itemCache={m:m,cat:Object.fromEntries((m.catalog||[]).map(t=>[String(t.id),t])),rows:new Map(m.rows.map(r=>[r.uid,r]))};
 return itemCache;
}
function itemVerdict(row,t){
 if(!row.can_steal)return{ok:false,label:'NPC 不可偷'};
 if(!t.steal)return{ok:false,label:'物品不可偷'};
 return{ok:true,label:'可偷'};
}
function itemRate(group){
 const rates=group.owners.filter(o=>o.v.ok&&o.t.steal).map(o=>o.t.steal.rate);
 return rates.length?rates.reduce((a,b)=>a+b,0)/rates.length:0;
}
function intimacyName(row){
 const tiers=(DATA.modules.items.intimacy||[]);
 let name='';
 for(const t of tiers){if(row.intimacy!=null&&row.intimacy>=t.need)name=t.name}
 return name;
}
/* 一名 NPC 一张表：三个渠道（偷 / 索要 / 赠礼）的结论并列在物品同一行，
   不再把同一批物品拆成三段各铺一遍。默认按「获取成本从低到高」排序，
   玩家从上往下就是推荐的拿取顺序。 */
let npcChannel='';
let npcPage={};
const NPC_PAGE_SIZE=20;
function npcChanOk(o){
 if(!npcChannel)return true;
 if(npcChannel==='steal')return o.v.ok;
 if(npcChannel==='gift')return o.gift;
 if(npcChannel==='demand')return o.demand;
 return true;
}
function npcItemsHtml(uid,focus){
 const idx=itemIndex(),row=idx.rows.get(uid);
 if(!row)return '';
 const cat=idx.cat;
 const focusId=focus!==undefined&&focus!==null?String(focus):'';
 const demandSet=new Set((row.demand||[]).map(id=>String(id)));
 const giftSet=new Set((row.gift||[]).map(id=>String(id)));
 const entries=new Map();
 for(const pair of row.items||[]){
  const key=String(pair[0]);
  const t=cat[key]||{name:'物品 #'+key,quality:null,type:''};
  const count=pair[1]||1;
  if(entries.has(key))entries.get(key).count+=count;
  else entries.set(key,{t:t,count:count});
 }
 for(const key of demandSet){
  if(entries.has(key))continue;
  entries.set(key,{t:cat[key]||{name:'物品 #'+key,quality:null,type:''},count:0});
 }
 const list=[];
 for(const [key,o] of entries){
  const v=itemVerdict(row,o.t);
  const inTemplate=demandSet.has(key)&&!!o.t.demand;
  list.push({
   key:key,t:o.t,count:o.count,v:v,
   demand:inTemplate&&o.count>0,demandPool:demandSet.has(key),
   gift:giftSet.has(key)
  });
 }
 const rankOf=o=>o.gift?0:(o.v.ok?1:(o.demand?2:3));
 list.sort((a,b)=>rankOf(a)-rankOf(b)||Number(b.t.quality||0)-Number(a.t.quality||0)||String(a.t.name).localeCompare(String(b.t.name),'zh-CN'));
 const st={steal:0,demand:0,gift:0};
 for(const o of list){if(o.v.ok)st.steal++;if(o.demand)st.demand++;if(o.gift)st.gift++}
 const gm=DATA.modules.items||{},cycle=gm.gift_cycle_days||0,total=gm.gift_total_count||0,per=gm.gift_per_npc_count||0;
 const tips=[];
 const both=list.filter(o=>o.gift&&o.demand).length;
 if(both)tips.push('有 <b>'+both+'</b> 件既能等他主动赠予、也能花好感索要，优先等赠礼更省。');
 if(st.gift){
  if(row.gift_left>0)tips.push('本轮赠礼还可要 <b>'+esc(row.gift_left)+'</b> 次（单 NPC 整轮 '+per+' 次，已用 '+esc(row.gift_used||0)+'），是否给要看这次聊得让不让他愿意亲近。');
  else tips.push('本轮赠礼次数已用完（'+per+' 次），这些只能靠索要或偷取。');
 }else if(cycle){
  tips.push('他身上暂时没有能进入 AI 赠礼池的物品（赠礼池 ∩ 他的背包，已排除货架货）。');
 }
 const chanBtn=(key,label,num)=>'<button type="button" class="ni-chip'+(npcChannel===key?' on':'')+'" data-ch="'+key+'">'+label+' '+num+'</button>';
 const bar='<div class="ni-bar">'
  +'<span class="ni-title">他身上的 '+list.length+' 件</span>'
  +(row.intimacy!=null?'<span class="ni-k">好感 <b>'+esc(row.intimacy)+'</b>'+(intimacyName(row)?'（'+esc(intimacyName(row))+'）':'')+'</span>':'')
  +'<span class="ni-sep"></span>'
  +'<button type="button" class="ni-chip'+(npcChannel===''?' on':'')+'" data-ch="">全部</button>'
  +(st.steal?chanBtn('steal','能偷',st.steal):'')
  +(st.gift?chanBtn('gift','可赠',st.gift):'')
  +(st.demand?chanBtn('demand','可索要',st.demand):'')
  +'<details class="ni-rule"><summary>判定规则</summary><div class="ni-rule-body">'
   +'<div><b>偷</b>：只在对方「可被偷」且物品本身可偷时成立，行内数字是成功率；把鼠标停在数字上可看每件的「一次最多 / 善恶值 / 好感」消耗，带 ⚠ 表示失手会触发击杀。</div>'
   +'<div><b>索要</b>：来自这个 NPC 的索要模板，一次扣固定好感，与他的境界无关；模板里若有他此刻背包没有的物品会标「缺」。</div>'
   +'<div><b>赠礼</b>：来自 AI 聊天赠礼池与他的背包的交集（已排除货架货）'+(cycle?'，'+cycle+' 游戏日一轮、整轮 '+total+' 次、单 NPC '+per+' 次':'')+'；属于聊天时的随机赠予，不是必得。</div>'
  +'</div></details></div>';
 const shown=list.filter(npcChanOk);
 const limit=NPC_PAGE_SIZE*(npcPage[uid]||1);
 const visible=shown.slice(0,limit),rest=shown.length-visible.length;
 const rows=visible.map(o=>{
  const cur=focusId&&o.key===focusId;
  const name='<span class="ni-name"><span class="talent-name '+fqClass(o.t.quality)+'">'+esc(o.t.name)+'</span>'+(cur?'<span class="badge steal">当前物品</span>':'')+'</span>';
  const count='<span class="ni-n">'+(o.count>0?'×'+esc(o.count):'<i class="nil">缺</i>')+'</span>';
  const type='<span class="ni-type">'+esc(o.t.type||'未分类')+'</span>';
  let steal;
  if(o.v.ok){
   const r=o.t.steal;
   const tip='成功率 '+r.rate+'% · 一次最多 '+r.count+' 个 · 善恶值 '+r.alignment+' · 好感 '+r.intimacy+(r.kill?' · 失手触发击杀':'');
   steal='<span class="ni-c steal ok" title="'+esc(tip)+'">'+r.rate+'%'+(r.kill?'<i class="warn">⚠</i>':'')+'</span>';
  }else{
   steal='<span class="ni-c off" title="'+esc(o.v.label)+'">—</span>';
  }
  let demand;
  if(o.demand)demand='<span class="ni-c demand" title="一次消耗 '+esc(o.t.demand_cost||0)+' 好感">-'+esc(o.t.demand_cost||0)+'</span>';
  else if(o.demandPool&&o.count<=0)demand='<span class="ni-c off" title="在他的索要模板里，但他身上没有这件">缺</span>';
  else demand='<span class="ni-c off">—</span>';
  const gift=o.gift?'<span class="ni-c gift">可赠</span>':'<span class="ni-c off">—</span>';
  return '<div class="ni-row'+(cur?' focus':'')+'">'+name+count+type+steal+demand+gift+'</div>';
 }).join('');
 const tipHtml=tips.length?'<div class="ni-tip">'+tips.join(' ')+'</div>':'';
 const grid=shown.length?'<div class="ni-grid"><div class="ni-row hd"><span>物品</span><span class="ni-n">数量</span><span class="ni-type">类型</span><span class="ni-c">偷取</span><span class="ni-c">索要</span><span class="ni-c">赠礼</span></div>'+rows+'</div>'
  :'<div class="ni-none">这个渠道下没有物品；点上方「全部」看完整清单。</div>';
 const more=rest?'<button type="button" class="ni-more" data-ni-more="'+esc(uid)+'">显示更多（还有 '+rest+' 件）</button>':'';
 return '<div class="npc-items" data-uid="'+esc(uid)+'">'+bar+tipHtml+grid+more+'</div>';
}
function npcPass(row,npcQ){
 if(itemFilters.region&&(row.region||'未知区域')!==itemFilters.region)return false;
 if(itemFilters.location&&(row.location||'未知地点')!==itemFilters.location)return false;
 if(npcQ&&!((row.who+' '+(row.realm||'')).toLowerCase().includes(npcQ)))return false;
 return true;
}
function itemPass(iid,t,row,v,q){
 if(q&&!String(t.name).toLowerCase().includes(q))return false;
 if(itemFilters.type&&(t.type||'未分类')!==(itemFilters.type==='__none__'?'未分类':itemFilters.type))return false;
 if(itemFilters.quality==='__unknown__'&&t.quality!=null)return false;
 if(itemFilters.quality&&itemFilters.quality!=='__unknown__'&&String(t.quality??'')!==itemFilters.quality)return false;
 if(itemFilters.steal==='1'&&!v.ok)return false;
 if(itemFilters.steal==='0'&&v.ok)return false;
 if(itemFilters.demand==='1'&&!((row.demand||[]).some(id=>String(id)===iid)&&t.demand))return false;
 if(itemFilters.gift==='1'&&!(row.gift||[]).some(id=>String(id)===iid))return false;
 return true;
}
function hasItemFilters(){return !!(itemFilters.q||itemFilters.type||itemFilters.quality||itemFilters.steal||itemFilters.demand||itemFilters.gift)}
function renderItems(){
 itemPage={};
 const m=DATA.modules.items,idx=itemIndex();
 const q=itemFilters.q.trim().toLowerCase(),npcQ=itemFilters.npc.trim().toLowerCase();
 const groups={},npcSet=new Set();let pairCount=0;
 for(const row of m.rows){
  if(!npcPass(row,npcQ))continue;
  for(const pair of row.items||[]){
   const iid=String(pair[0]),t=idx.cat[iid];
   if(!t)continue;
   const v=itemVerdict(row,t);
   if(!itemPass(iid,t,row,v,q))continue;
   if(!groups[iid])groups[iid]={t:t,owners:[],stealable:0,total:0};
   groups[iid].owners.push({row:row,t:t,count:pair[1]||1,v:v});
   groups[iid].total+=pair[1]||1;
   if(v.ok){groups[iid].stealable++;const rate=t.steal?t.steal.rate:0;if(rate>(groups[iid].bestRate||0))groups[iid].bestRate=rate;}
   npcSet.add(row.uid);pairCount++;
  }
 }
 const sorted=Object.values(groups).sort((a,b)=>b.stealable-a.stealable||itemRate(b)-itemRate(a)||String(a.t.name).localeCompare(String(b.t.name),'zh-CN'));
 const buckets={};
 for(const g of sorted){
  const key=g.t.quality==null?'__none__':String(g.t.quality);
  const b=buckets[key]||(buckets[key]={q:g.t.quality,groups:[],items:0,total:0,stealable:0});
  b.groups.push(g);b.items++;b.total+=g.total;b.stealable+=g.stealable;
 }
 const order=Object.keys(buckets).sort((a,b)=>{
  if(a==='__none__'&&b==='__none__')return 0;
  if(a==='__none__')return 1;
  if(b==='__none__')return -1;
  return Number(b)-Number(a);
 });
 const cards=order.map(key=>{
  const b=buckets[key];
  const inner=b.groups.map(group=>{
   const stat='可偷 '+group.stealable+' 处'+(group.bestRate?' · 最高 '+group.bestRate+'%':'')+' · 共 '+group.total+' 个';
   return '<details class="item-group" data-item="'+esc(group.t.id)+'"><summary class="item-head"><span class="item-arrow">›</span><span class="item-title '+fqClass(group.t.quality)+'">'+hi(group.t.name,q)+'</span><span class="badge">'+esc(group.t.type||'未分类')+'</span><span class="badge">'+esc(qualityLabel(group.t.quality))+'</span><span class="item-stat">'+stat+'</span></summary><div class="owners"></div></details>';
  }).join('');
  return '<details class="qsec" open><summary><span class="qsec-arrow">›</span><span class="qsec-title '+fqClass(b.q)+'">'+esc(qualityLabel(b.q))+'</span><span class="badge">'+b.items+' 种</span><span class="qsec-meta">可偷 '+b.stealable+' 处 · 共 '+b.total+' 个</span></summary><div class="qsec-body">'+inner+'</div></details>';
 });
 itemRenderState={groups:Object.fromEntries(sorted.map(g=>[String(g.t.id),g])),q:q,npcQ:npcQ};
 $('iresult').textContent='筛选结果：'+sorted.length+' 种物品（按品质从高到低分组），'+npcSet.size+' 位 NPC，'+pairCount+' 条持有记录';
 $('ilist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合条件的物品</div>';
}
function renderNpcs(){
 itemPage={};
 npcPage={};
 const m=DATA.modules.items,idx=itemIndex();
 const npcQ=itemFilters.npc.trim().toLowerCase(),q=itemFilters.q.trim().toLowerCase();
 const itemFilterOn=hasItemFilters();
 const npcs={};
 for(const row of m.rows){
  if(!npcPass(row,npcQ))continue;
  let matched=0,stealable=0;
  for(const pair of row.items||[]){
   const iid=String(pair[0]),t=idx.cat[iid];
   if(!t)continue;
   const v=itemVerdict(row,t);
   if(!itemPass(iid,t,row,v,q))continue;
   matched++;
   if(v.ok)stealable++;
  }
  if(itemFilterOn&&!matched)continue;
  const demandable=(row.demand||[]).filter(did=>{const dt=idx.cat[String(did)];return dt&&dt.demand}).length;
  const giftable=(row.gift||[]).length;
  npcs[row.uid]={row:row,total:(row.items||[]).length,matched:matched,stealable:stealable,demandable:demandable,giftable:giftable};
 }
 const list=Object.values(npcs).sort((a,b)=>b.stealable-a.stealable||b.total-a.total||String(a.row.who).localeCompare(String(b.row.who),'zh-CN'));
 const cards=list.map(g=>{
  const held=itemFilterOn?'符合 '+g.matched+' / 共 '+g.total+' 件':'共 '+g.total+' 件';
  return '<details class="item-group npc-card" data-uid="'+esc(g.row.uid)+'"><summary class="item-head"><span class="item-arrow">›</span><span class="item-title">'+hi(g.row.who,npcQ)+'</span>'+(g.row.realm?'<span class="badge">'+esc(g.row.realm)+'</span>':'')+'<span class="badge steal">可偷 '+g.stealable+' 件</span>'+(g.demandable?'<span class="badge demand">可索要 '+g.demandable+' 件</span>':'')+(g.giftable?'<span class="badge gift">可赠 '+g.giftable+' 件</span>':'')+'<span class="item-stat">'+held+' · '+esc(g.row.location_path||g.row.location||'未知地点')+'</span></summary><div class="slots"></div></details>';
 });
 itemRenderState={groups:{},q:q,npcQ:npcQ};
 $('iresult').textContent='筛选结果：'+list.length+' 位 NPC，共 '+list.reduce((s,g)=>s+g.total,0)+' 件物品（按 NPC 查看完整清单）';
 $('ilist').innerHTML=cards.length?cards.join(''):'<div class="empty">没有符合条件的 NPC</div>';
}
function renderList(){if(itemView==='npc')renderNpcs();else renderItems()}
function initItems(){
 const m=DATA.modules.items;if(!m)return;
 const catalog=m.catalog||[],regions=uniq(m.rows.map(r=>r.region||'未知区域'));
 const types=uniq(catalog.map(t=>t.type||'未分类'));
 const opts=(values,kind)=>'<option value="">全部'+kind+'</option>'+values.map(v=>{
  let label=v,value=v;
  if(kind==='类型'){label=v||'未分类';value=v||'__none__'}
  return '<option value="'+esc(value)+'">'+esc(label)+'</option>'
 }).join('');
 function qualityOptions(){
  const vals=[...new Set(catalog.map(t=>t.quality==null?'__unknown__':String(t.quality)))];
  const known=vals.filter(v=>v!=='__unknown__').sort((a,b)=>Number(b)-Number(a));
  let out='<option value="">全部品质</option>'+known.map(v=>'<option value="'+v+'">品质 '+v+'</option>').join('');
  if(vals.includes('__unknown__'))out+='<option value="__unknown__">未知品质</option>';
  return out;
 }
 $('items').innerHTML=sourceHtml(m)+`
  <style>
  .npc-items{margin:4px 0 8px}
  .ni-title{font-size:13px;font-weight:600;margin-right:2px}
  .ni-k{color:#8b93a1;font-size:12px}
  .ni-k b{color:#cfd6e2;font-weight:600}
  .ni-sep{width:1px;height:14px;background:#2f3a47;margin:0 4px}
  .ni-tip{font-size:12px;line-height:1.65;color:#c8b06a;background:rgba(200,176,106,.09);border:1px solid rgba(200,176,106,.26);border-radius:8px;padding:6px 10px;margin:0 0 8px}
  .ni-tip b{color:#e6d08a}
  .ni-bar{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:0 0 8px}
  .ni-chip{background:#1b222c;border:1px solid #35404f;border-radius:999px;color:#9aa3b2;padding:4px 11px;font-size:12px;cursor:pointer;font-family:inherit}
  .ni-chip:hover{background:#25303d;color:#cfd6e2}
  .ni-chip.on{background:#263b34;border-color:#3d735b;color:#c9f5dd}
  .ni-rule{margin-left:auto;font-size:12px;color:#8b93a1}
  .ni-rule>summary{cursor:pointer;color:#8894a4;padding:2px 0;list-style:none}
  .ni-rule>summary::-webkit-details-marker{display:none}
  .ni-rule>summary:hover{color:#cfd6e2}
  .ni-rule>summary::before{content:'?  ';color:#6f7787}
  .ni-rule-body{margin-top:6px;line-height:1.75;color:#8b93a1;background:#12161c;border:1px solid #232b36;border-radius:8px;padding:8px 10px;max-width:640px}
  .ni-rule-body b{color:#cfd6e2;margin-right:2px}
  .ni-grid{display:flex;flex-direction:column;gap:1px;max-width:760px}
  .ni-row{display:grid;grid-template-columns:minmax(0,1fr) 44px 68px 64px 62px 50px;align-items:center;gap:10px;padding:7px 10px;border-radius:7px;font-size:13px}
  .ni-row.hd{font-size:11px;color:#778292;padding:0 10px 5px;border-bottom:1px solid #232b36;border-radius:0}
  .ni-row:not(.hd):nth-child(odd){background:rgba(255,255,255,.016)}
  .ni-row:not(.hd):hover{background:#1b222c}
  .ni-row.focus{background:rgba(110,221,162,.11);box-shadow:inset 0 0 0 1px rgba(110,221,162,.32)}
  .ni-name{min-width:0;display:flex;align-items:center;gap:6px;overflow:hidden;white-space:nowrap}
  .ni-name .talent-name{overflow:hidden;text-overflow:ellipsis}
  .ni-n{text-align:right;color:#9aa3b2;font-size:12px;font-variant-numeric:tabular-nums}
  .ni-n .nil{color:#5d6673;font-style:normal;font-size:11px;border:1px dashed #3c4655;border-radius:4px;padding:0 4px}
  .ni-type{color:#8b93a1;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .ni-c{font-size:12px;text-align:center;border-radius:5px;padding:2px 0;white-space:nowrap;font-variant-numeric:tabular-nums}
  .ni-c.off{color:#5d6673}
  .ni-c.steal.ok{color:#f0b45f;background:rgba(240,180,95,.13);cursor:help}
  .ni-c.demand{color:#6edda2;background:rgba(110,221,162,.13);cursor:help}
  .ni-c.gift{color:#9fc0ff;background:rgba(150,190,255,.13)}
  .ni-c .warn{color:#e4736b;font-style:normal;margin-left:2px}
  .ni-none{padding:10px 2px;color:#778292;font-size:12px}
  .ni-more{display:block;width:100%;max-width:760px;margin:7px 0 2px;background:#1b222c;border:1px dashed #35404f;border-radius:8px;color:#9aa3b2;padding:8px;font-size:12px;cursor:pointer;font-family:inherit}
  .ni-more:hover{background:#25303d;color:#c6cfda}
  .badge.demand{background:rgba(110,221,162,.14);color:#6edda2;border:1px solid rgba(110,221,162,.35)}
  .badge.gift{background:rgba(150,190,255,.14);color:#9fc0ff;border:1px solid rgba(150,190,255,.35)}
  .badge.demand-absent{background:transparent;color:#8b93a1;border:1px dashed #4a5563}
  .item-viewbar{display:flex;gap:8px;margin-bottom:14px}
  .viewbtn{background:#1b222c;border:1px solid #35404f;border-radius:8px;color:#9aa3b2;padding:9px 16px;cursor:pointer;font-size:13px}
  .viewbtn:hover{background:#25303d}
  .viewbtn.on{background:#263b34;border-color:#3d735b;color:#c9f5dd}
  .filter-bar.items{grid-template-columns:repeat(3,minmax(0,1fr));align-items:end}
  .filter-bar.items .filter-actions{grid-column:1 / -1;justify-content:flex-end}
  .qsec{background:#12161c;border:1px solid #232b36;border-radius:12px;margin:0 0 16px;overflow:hidden}
  .qsec>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;padding:13px 16px}
  .qsec>summary::-webkit-details-marker{display:none}
  .qsec>summary:hover{background:#171d27}
  .qsec-arrow{color:#6f7787;font-size:16px;transition:.15s;display:inline-block}
  .qsec[open]>summary .qsec-arrow{transform:rotate(90deg)}
  .qsec-title{font-size:15px;font-weight:650}
  .qsec-meta{margin-left:auto;color:#778292;font-size:11px;font-weight:400}
  .qsec-body{padding:4px 12px 12px}
  @media(max-width:850px){.filter-bar.items{grid-template-columns:repeat(2,minmax(0,1fr))}.filter-bar.items .filter-actions{grid-column:span 2}}
  @media(max-width:720px){.ni-row{grid-template-columns:minmax(0,1fr) 36px 54px 56px 46px;gap:6px;padding:6px 6px}.ni-row .ni-type{display:none}.ni-name .badge{display:none}.ni-rule{margin-left:0;width:100%}.ni-sep{display:none}}
  @media(max-width:560px){.filter-bar.items{grid-template-columns:1fr}.filter-bar.items .filter-actions{grid-column:span 1}.qsec-body{padding:4px 8px 8px}}
  </style>
  <div class="search-panel">
   <div class="item-viewbar">
    <button type="button" class="viewbtn" id="iview-item" data-view="item">按物品找</button>
    <button type="button" class="viewbtn" id="iview-npc" data-view="npc">按 NPC 看</button>
   </div>
   <div class="search-fields">
    <label class="search-field"><span>找物品</span><input id="iq" placeholder="输入物品名称" value="${esc(itemFilters.q)}"></label>
    <label class="search-field"><span>找 NPC（可选）</span><input id="inpc" placeholder="输入 NPC 名称，与物品条件叠加" value="${esc(itemFilters.npc)}"></label>
   </div>
  </div>
  <div class="filter-bar items">
   <label class="filter-field"><span>品质</span><select id="iquality">${qualityOptions()}</select></label>
   <label class="filter-field"><span>类型</span><select id="itype">${opts(types,'类型')}</select></label>
   <label class="filter-field"><span>区域</span><select id="iregion">${opts(regions,'区域')}</select></label>
   <label class="filter-field"><span>具体位置</span><select id="ilocation"></select></label>
   <label class="filter-field"><span>偷窃</span><select id="isteal"><option value="">全部持有者</option><option value="1">只看可偷</option><option value="0">只看不可偷</option></select></label>
   <label class="filter-field"><span>索要</span><select id="idemand"><option value="">全部物品</option><option value="1">只看可索要</option></select></label>
   <label class="filter-field"><span>赠礼</span><select id="igift"><option value="">全部物品</option><option value="1">只看可赠</option></select></label>
   <div class="filter-actions"><button type="button" id="iclear" class="filter-button">清空筛选</button></div>
  </div>
  <div id="iresult" class="result-info"></div><div id="ilist"></div>`;
 function updateItemLocations(){
  const locations=uniq(m.rows.filter(r=>!itemFilters.region||(r.region||'未知区域')===itemFilters.region).map(r=>r.location||'未知地点'));
  if(itemFilters.location&&!locations.includes(itemFilters.location))itemFilters.location='';
  $('ilocation').innerHTML=opts(locations,'具体位置');$('ilocation').value=itemFilters.location||'';
 }
 function saveAndRender(){store.set(ITEM_KEY,itemFilters);renderList()}
 function applyView(){
  $('iview-item').classList.toggle('on',itemView==='item');
  $('iview-npc').classList.toggle('on',itemView==='npc');
 }
 $('iview-item').addEventListener('click',()=>{itemView='item';store.set('worldapart.item.view.v1',itemView);applyView();renderList()});
 $('iview-npc').addEventListener('click',()=>{itemView='npc';store.set('worldapart.item.view.v1',itemView);applyView();renderList()});
 $('iregion').value=itemFilters.region||'';updateItemLocations();
 for(const key of ['q','npc','location','type','quality','steal','demand','gift']){
  const node=$('i'+key);node.value=itemFilters[key]??'';
  node.addEventListener(node.tagName==='INPUT'?'input':'change',()=>{itemFilters[key]=node.value;saveAndRender()});
 }
 $('iregion').addEventListener('change',()=>{itemFilters.region=$('iregion').value;updateItemLocations();saveAndRender()});
 $('iclear').addEventListener('click',()=>{itemFilters=Object.assign({},ITEM_DEFAULTS);store.set(ITEM_KEY,itemFilters);initItems()});
 applyView();renderList();
}
document.addEventListener('toggle',event=>{
 const node=event.target;
 if(!node||!node.classList||!node.open||!node.closest('#items'))return;
 if(node.classList.contains('npc-card')){
  const slots=node.querySelector('.slots');
  if(slots&&!slots.dataset.filled){slots.dataset.filled='1';slots.innerHTML=npcItemsHtml(node.dataset.uid)}
  return;
 }
 if(node.classList.contains('item-group')){
  const owners=node.querySelector('.owners');
  if(owners&&!owners.dataset.filled){owners.dataset.filled='1';owners.innerHTML=itemOwnersHtml(node.dataset.item)}
  return;
 }
 if(node.classList.contains('owner')){
  const box=node.querySelector('.slots');
  if(!box||box.dataset.filled)return;
  box.dataset.filled='1';
  box.innerHTML=npcItemsHtml(node.dataset.uid,node.dataset.item);
 }
},true);
function refreshItemOwners(iid){
 const nodes=document.querySelectorAll('#items .item-group');
 for(const node of nodes){
  if(node.dataset.item!==String(iid))continue;
  const box=node.querySelector('.owners');
  if(!box)return;
  box.dataset.filled='1';
  box.innerHTML=itemOwnersHtml(String(iid));
  return;
 }
}
document.addEventListener('click',event=>{
 if(!event.target.closest('#items'))return;
 const chip=event.target.closest('[data-ch]');
 if(chip){
  const ch=chip.dataset.ch;
  npcChannel=(npcChannel===ch)?'':ch;
  const host=chip.closest('.npc-items');
  if(host)host.outerHTML=npcItemsHtml(host.dataset.uid);
  return;
 }
 const niMore=event.target.closest('[data-ni-more]');
 if(niMore){
  const uid=niMore.dataset.niMore;
  npcPage[uid]=(npcPage[uid]||1)+1;
  const host=niMore.closest('.npc-items');
  if(host)host.outerHTML=npcItemsHtml(uid);
  return;
 }
 const more=event.target.closest('[data-more]');
 if(more){
  const iid=more.dataset.more;
  itemPage[iid]=(itemPage[iid]||1)+1;
  refreshItemOwners(iid);
  return;
 }
 const sort=event.target.closest('[data-sort]');
 if(sort){
  itemSort=sort.dataset.sort;
  store.set('worldapart.item.sort.v1',itemSort);
  document.querySelectorAll('#items .item-group[open]').forEach(node=>refreshItemOwners(node.dataset.item));
 }
});
window.PROGRESS_VIEWS=window.PROGRESS_VIEWS||{};
window.PROGRESS_VIEWS['items']=initItems;
})();
