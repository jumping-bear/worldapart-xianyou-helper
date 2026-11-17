/* 拍卖会：本场拍品、珍匣与竞拍参考。 */
(function () {
const MARGIN_KEY = 'worldapart.auction.margin';
const REVEAL_KEY = 'worldapart.auction.reveal';
let margin = store.get(MARGIN_KEY, 20);
if (typeof margin !== 'number' || margin < 0 || margin > 60) margin = 20;
let reveal = !!store.get(REVEAL_KEY, false);
let filters = {worth: false, chest: false, finale: false};
let activeKey = '';

function money(v) { return Number(v || 0).toLocaleString('zh-CN'); }
function suggest(v) { return Math.max(0, Math.round(Number(v || 0) * (1 - margin / 100))); }
function qbadge(q) { return q == null ? '' : `<span class="au-q au-q${esc(q)}">品质 ${esc(q)}</span>`; }
function typeBadge(t) { return `<span class="au-type">${esc(t || '未分类')}</span>`; }

function headHtml(rows) {
  const c = rows.character || {}, consign = rows.consign || {}, loan = rows.loan || {};
  const consignText = (consign.sold || consign.unsold)
    ? `上期寄售：成交 ${consign.sold} 件、流拍 ${consign.unsold} 件，收益 <b>${money(consign.earnings)}</b> 灵石`
    : '上期寄售：暂无成交记录';
  return `<div class="au-head">
    <div class="au-who"><b>${esc(c.name || '未命名')}</b><span>${esc(c.realm_name || '')} · 第 ${esc(c.layer || 0)} 层</span></div>
    <div class="au-facts">
      <div><span>可贷灵石</span><b>${money(loan.max)}</b></div>
      <div><span>寄售</span><b class="au-inline">${consignText}</b></div>
    </div>
  </div>`;
}

function tabsHtml(sessions) {
  return `<div class="au-tabs">${sessions.map(s =>
    `<button type="button" class="au-tab${s.key === activeKey ? ' active' : ''}" data-key="${esc(s.key)}">
      ${esc(s.venue_name)} · ${stateLabel(s)}<i>${s.items.length} 件</i></button>`).join('')}</div>`;
}

function stateLabel(s) {
  if (s.state === 'current') return s.same_realm ? '本境界' : (s.attend ? '可参加' : '未达境界');
  return '已结束';
}

function controlsHtml(s) {
  const worth = s.items.filter(i => i.ratio >= 1.2).length;
  return `<div class="au-controls">
    <label class="au-check"><input type="checkbox" id="au-worth"${filters.worth ? ' checked' : ''}>只看值得跟（≥1.2 倍）<i>${worth}</i></label>
    <label class="au-check"><input type="checkbox" id="au-chest"${filters.chest ? ' checked' : ''}>只看珍匣</label>
    <label class="au-check"><input type="checkbox" id="au-finale"${filters.finale ? ' checked' : ''}>只看压轴</label>
    <label class="au-margin">目标利润率 <input type="number" id="au-margin" min="0" max="60" step="5" value="${margin}"> %</label>
    <label class="au-check"><input type="checkbox" id="au-reveal"${reveal ? ' checked' : ''}>显示未揭示格</label>
  </div>`;
}

function itemHtml(it) {
  const known = it.value_known !== false;
  const ratio = Number(it.ratio || 0);
  const ratioClass = ratio >= 1.5 ? 'great' : (ratio >= 1.2 ? 'good' : '');
  const flags = [];
  if (it.finale) flags.push('<span class="au-flag gold">压轴</span>');
  if (it.chest) flags.push('<span class="au-flag">珍匣</span>');
  return `<div class="au-item${it.chest ? ' has-chest' : ''}">
    <div class="au-main">
      <div class="au-title"><span class="au-name">${esc(it.name)}</span>${flags.join('')}${typeBadge(it.type)}${qbadge(it.quality)}</div>
      <div class="au-nums">
        <span>起拍 <b>${known ? money(it.base_price) : '—'}</b></span>
        <span>参考 <b>${known ? money(it.true_value) : '—'}</b></span>
        <span class="au-ratio ${known ? ratioClass : ''}">${known ? '×' + ratio.toFixed(2) : '数据缺失'}</span>
        <span>建议上限 <b class="au-suggest">${known ? money(suggest(it.true_value)) : '—'}</b></span>
        <span class="au-qty">×${esc(it.quantity)}</span>
      </div>
    </div>
    ${it.chest ? chestHtml(it) : ''}
  </div>`;
}

function chestHtml(it) {
  const c = it.chest || {};
  const cells = (c.detail || []).map(cell => {
    const shown = cell.revealed || reveal;
    const name = shown ? cell.name : '未揭示';
    const extra = shown ? `${cell.count > 1 ? ' ×' + cell.count : ''}` : '';
    return `<div class="au-cell${cell.revealed ? ' open' : (reveal ? ' peek' : '')}" title="${esc(shown ? cell.name : '未揭示')}">
      <span class="au-cellno">${Number(cell.index) + 1}</span>
      <span class="au-cellname">${esc(name)}${esc(extra)}</span>
      ${shown && cell.quality != null ? qbadge(cell.quality) : ''}
    </div>`;
  }).join('');
  return `<div class="au-chest">
    <div class="au-chesthead"><span>${esc(c.name || '珍匣')} · ${esc(c.cells)} 格</span>
      <span>期望总价 <b>${money(c.expected)}</b></span>
      <span>真实总值 <b>${money(c.true_total)}</b></span>
      <span class="muted">每出价揭示 ${esc(c.reveal_per_bid)} 格，最多 ${esc(c.cap)}%</span>
    </div>
    <div class="au-cells">${cells}</div>
  </div>`;
}

function visibleItems(s) {
  return (s.items || []).filter(it => {
    if (filters.worth && Number(it.ratio || 0) < 1.2) return false;
    if (filters.chest && !it.chest) return false;
    if (filters.finale && !it.finale) return false;
    return true;
  });
}

function sessionHtml(s) {
  const items = visibleItems(s);
  const body = items.length ? items.map(itemHtml).join('') : '<div class="au-none">当前筛选下没有拍品。</div>';
  return `<div class="au-summary">
      <span><b>${s.items.length}</b> 件拍品，参考总值 <b>${money(s.total_value)}</b>，起拍合计 <b>${money(s.total_start)}</b></span>
      <span>值得跟 <b>${s.worth}</b> 件</span>
    </div>
    <div class="au-list">${body}</div>`;
}

function historyHtml(rows) {
  const history = rows.history || [];
  if (!history.length) return '';
  return `<details class="au-history"><summary>历史场次（${history.length}）</summary>
    <div class="au-history-body">${history.map(s => `<div class="au-hrow">
      <span>${esc(s.venue_name)}</span><span class="muted">场次 ${esc(s.occurrence)}</span>
      <span>${s.items.length} 件</span><span>参考总值 ${money(s.total_value)}</span>
    </div>`).join('')}</div>
  </details>`;
}

function staticHtml(m) {
  const tactics = m.tactics || [];
  const hermits = (m.hermits || []).filter(h => h.note);
  return `<div class="au-static">
    ${tactics.length ? `<div class="au-card"><h3>竞拍策略</h3>${tactics.map(t =>
      `<div class="au-line"><b>${esc(t.name)}</b><span>成功率 ${esc(t.rate)}%</span><span class="muted">${esc(t.desc)}</span></div>`).join('')}</div>` : ''}
    ${hermits.length ? `<div class="au-card"><h3>可能出现的掮客</h3>${hermits.map(h =>
      `<div class="au-line"><b>${esc(h.note)}</b><span>收购倍率 ${esc(h.gold_ratio)}%</span></div>`).join('')}</div>` : ''}
    <div class="au-note">参考价值 = 物品参考价 × 数量，来自游戏配置；建议上限按目标利润率预留，仅作竞拍参考，不保证成交。<br>
    未揭示格默认显示“未揭示”，勾选“显示未揭示格”后读取存档里的真实内容。场次按“上次结算时间”区分本场与历史。</div>
  </div>`;
}

function warnHtml(rows) {
  const list = rows.warnings || [];
  if (!list.length) return '';
  return `<div class="au-warn">${list.map(w => `<div>· ${esc(w)}</div>`).join('')}</div>`;
}

function emptyHtml(rows) {
  const consign = rows.consign || {};
  const title = rows.available === false ? '此存档暂无拍卖会数据' : '还没有生成本场拍卖会';
  const desc = rows.note || '拍卖会每月 12 日开拍，持续 31 天。活动开启前进入拍卖行或继续游戏后，下一场拍品会写入存档副本。';
  return `<div class="au-empty">
    <div class="au-empty-title">${esc(title)}</div>
    <div>${esc(desc)}</div>
    ${consign.sold || consign.unsold ? `<div class="au-facts"><div><span>上期寄售</span><b>成交 ${esc(consign.sold)} 件，流拍 ${esc(consign.unsold)} 件，收益 ${money(consign.earnings)}</b></div></div>` : ''}
  </div>` + historyHtml(rows);
}

function renderSession() {
  const m = DATA.modules.auction || {};
  const rows = m.rows || {};
  const sessions = rows.current || [];
  const s = sessions.find(x => x.key === activeKey) || sessions[0];
  if (!s) return;
  activeKey = s.key;
  const body = $('au-body');
  if (!body) return;
  body.innerHTML = controlsHtml(s) + sessionHtml(s);
  bindControls(s);
  document.querySelectorAll('.au-tab').forEach(b => b.classList.toggle('active', b.dataset.key === activeKey));
}

function bindControls(s) {
  const worth = $('au-worth'), chest = $('au-chest'), finale = $('au-finale');
  const marginInput = $('au-margin'), revealInput = $('au-reveal');
  worth.onchange = () => { filters.worth = worth.checked; renderSession(); };
  chest.onchange = () => { filters.chest = chest.checked; renderSession(); };
  finale.onchange = () => { filters.finale = finale.checked; renderSession(); };
  revealInput.onchange = () => { reveal = revealInput.checked; store.set(REVEAL_KEY, reveal); renderSession(); };
  marginInput.onchange = () => {
    let value = Number(marginInput.value);
    if (!Number.isFinite(value)) value = 20;
    margin = Math.min(60, Math.max(0, value));
    store.set(MARGIN_KEY, margin);
    renderSession();
  };
}

function bindTabs() {
  document.querySelectorAll('.au-tab').forEach(btn => {
    btn.onclick = () => { activeKey = btn.dataset.key; renderSession(); };
  });
}

function initAuction() {
  const m = DATA.modules.auction || {};
  const rows = m.rows || {};
  const box = $('auction');
  if (!box) return;
  const sessions = rows.current || [];
  if (!sessions.length) {
    box.innerHTML = sourceHtml(m) + emptyHtml(rows) + warnHtml(rows) + staticHtml(m);
    return;
  }
  if (!sessions.some(x => x.key === activeKey)) activeKey = sessions[0].key;
  box.innerHTML = sourceHtml(m) + headHtml(rows) + warnHtml(rows) + tabsHtml(sessions)
    + '<div id="au-body"></div>' + historyHtml(rows) + staticHtml(m);
  bindTabs();
  renderSession();
}

window.PROGRESS_VIEWS = window.PROGRESS_VIEWS || {};
window.PROGRESS_VIEWS['auction'] = initAuction;
})();
