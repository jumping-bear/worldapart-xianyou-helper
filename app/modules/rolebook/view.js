/* 人物图鉴（NPC 全息档案）：真实头像 + 重点优先的分批渲染 + 关系网抽屉。 */
(function () {
  'use strict';
  var STORE_KEY = 'worldapart.rolebook.filters.v2';
  var DEFAULTS = {
    q: '', evil: '', realm: '', sect: '', personality: '',
    dao: 0, friend: 0, housed: 0, memoria: 0, talent: 0, safe: 0,
    rel: '', sort: 'relevance'
  };
  var PAGE = 48;  // 分批渲染步长，避免 1686 张一次糊脸
  var filters = Object.assign({}, DEFAULTS, store.get(STORE_KEY, {}));
  var view = null, drawer = null, mask = null, lastData = null;
  var shown = PAGE, currentRows = [], currentMeta = null;

  function persist() { store.set(STORE_KEY, filters); }
  function num(v) { return Number(v || 0); }
  function pad(v) { return String(v == null ? '' : v); }
  function qval(id) { var el = $(id); return el ? el.value : ''; }

  // 真实头像：来自头像快照的 dataURI；无头像回退首字母圆牌
  function avatarHtml(c, cls, map) {
    var uri = (map || {})[String(c.id)];
    var ch = (c.name || '?').slice(0, 1);
    if (uri) {
      return '<span class="rolebook-avatar has-img ' + (cls || '') + '">' +
        '<span class="rolebook-avatar-initial">' + esc(ch) + '</span>' +
        '<img src="' + esc(uri) + '" alt="' + esc(c.name || '') + '" loading="lazy" ' +
        'onerror="this.style.display=\'none\'"></span>';
    }
    return '<span class="rolebook-avatar ' + (cls || '') + '"><span>' + esc(ch) + '</span></span>';
  }

  function abilityIcons(c) {
    var out = [];
    if (c.met) out.push('<span class="rolebook-ico rolebook-ico-met" title="已结识">识</span>');
    if (c.housed) out.push('<span class="rolebook-ico rolebook-ico-house" title="已入住仙居">宅</span>');
    if (c.dao) out.push('<span class="rolebook-ico rolebook-ico-dao" title="道侣">道</span>');
    if (c.spar) out.push('<span class="rolebook-ico rolebook-ico-spar" title="可切磋">切</span>');
    if (c.killable) out.push('<span class="rolebook-ico rolebook-ico-kill" title="可击杀">杀</span>');
    if (c.steal) out.push('<span class="rolebook-ico rolebook-ico-steal" title="可偷窃">窃</span>');
    if (c.merchant) out.push('<span class="rolebook-ico rolebook-ico-mer" title="商人">商</span>');
    if (c.memoria) out.push('<span class="rolebook-ico rolebook-ico-mem" title="有留影关联">影</span>');
    return out.join('');
  }

  function evilClass(v) { return v < 0 ? 'bad' : (v > 0 ? 'good' : 'mid'); }
  function evilBand(c) {
    var cls = evilClass(c.evil);
    return '<div class="rolebook-band rolebook-band-' + cls + '" title="善恶值 ' + c.evil + '">' +
      '<div class="rolebook-band-axis"></div>' +
      '<div class="rolebook-band-dot" style="left:' + c.evil_pos + '%"></div></div>';
  }

  function roleTags(c) {
    return (c.roles || []).map(function (r) {
      return '<span class="rolebook-role rolebook-role-' + esc(r) + '">' + esc(r) + '</span>';
    }).join('');
  }

  function optList(values, labels, selected, allLabel) {
    var html = '<option value="">' + esc(allLabel) + '</option>';
    values.forEach(function (v, i) {
      var label = labels && labels[i] != null ? labels[i] : v;
      html += '<option value="' + esc(v) + '"' + (String(selected) === String(v) ? ' selected' : '') +
        '>' + esc(label) + '</option>';
    });
    return html;
  }

  function tierName(meta, key, idx) {
    var t = ((meta || {})[key] || [])[num(idx)];
    return t ? t.name : '';
  }
  function tierDesc(meta, key, idx) {
    var t = ((meta || {})[key] || [])[num(idx)];
    return t ? (t.desc || '') : '';
  }

  function isSafe(c) { return c.evil < 0 && c.killable; }

  // 相关性权重：与我有关的人排在最前，做成有层次的重点视图
  function relevance(c) {
    var w = 0;
    if (c.roles && c.roles.length) w += 10 + c.roles.length;
    if (c.dao) w += 6;
    if (c.housed) w += 5;
    if (c.met) w += 4;
    if (c.memoria) w += 2;
    if (lastAvatar(c)) w += 3;
    return w;
  }
  function lastAvatar(c) { return !!(lastData && lastData.avatar_map && lastData.avatar_map[String(c.id)]); }

  function match(c) {
    if (filters.safe && !isSafe(c)) return false;
    if (filters.q) {
      var hay = (c.name + ' ' + c.sect + ' ' + c.personality + ' ' + c.realm +
        ' ' + c.place + ' ' + (c.roles || []).join(' ') + ' ' + c.id).toLowerCase();
      if (hay.indexOf(filters.q.toLowerCase()) < 0) return false;
    }
    if (filters.evil === 'bad' && !(c.evil < 0)) return false;
    if (filters.evil === 'mid' && c.evil !== 0) return false;
    if (filters.evil === 'good' && !(c.evil > 0)) return false;
    if (filters.realm && c.realm_short !== filters.realm && c.realm !== filters.realm) return false;
    if (filters.sect && c.sect !== filters.sect) return false;
    if (filters.personality && c.personality !== filters.personality) return false;
    if (filters.dao && !c.dao) return false;
    if (filters.friend && (c.roles || []).indexOf('朋友') < 0) return false;
    if (filters.housed && !c.housed) return false;
    if (filters.memoria && !c.memoria) return false;
    if (filters.talent && !c.talents.length) return false;
    if (filters.rel) {
      if (filters.rel === 'related') {
        if (!(c.roles && c.roles.length) && !c.met && !c.housed) return false;
      } else if ((c.roles || []).indexOf(filters.rel) < 0) return false;
    }
    return true;
  }

  function sortRows(rows) {
    var by = filters.sort;
    rows.sort(function (a, b) {
      if (by === 'relevance') return relevance(b) - relevance(a) || a.id - b.id;
      if (by === 'id') return a.id - b.id;
      if (by === 'name') return String(a.name).localeCompare(String(b.name), 'zh-CN');
      if (by === 'evil') return a.evil - b.evil;
      if (by === 'evilDesc') return b.evil - a.evil;
      if (by === 'wisdom') return b.wisdom - a.wisdom;
      if (by === 'favor') return b.favor - a.favor;
      if (by === 'layer') return b.layer_order - a.layer_order;
      return a.id - b.id;
    });
    return rows;
  }

  function cardHtml(c, meta, map) {
    var cls = evilClass(c.evil);
    var badges = '';
    if (c.roles && c.roles.length) badges += roleTags(c);
    if (isSafe(c)) badges += '<span class="rolebook-badge rolebook-badge-safe">安全目标</span>';
    var rel = c.roles && c.roles.length ? ' · ' + c.roles.join('/') : '';
    return '<article class="rolebook-card rolebook-card-' + cls + '" data-npc="' + c.id + '" tabindex="0">' +
      '<div class="rolebook-card-top">' + avatarHtml(c, '', map) +
        '<div class="rolebook-card-id">' +
          '<div class="rolebook-card-name">' + esc(c.name) + '</div>' +
          '<div class="rolebook-card-realm">' + esc(c.realm) + '</div>' +
          '<div class="rolebook-card-place" title="常驻地 / 出现地点">' + esc(c.place || '') + '</div>' +
        '</div></div>' +
      '<div class="rolebook-card-badges">' + (badges || '<span class="rolebook-role-none">路人 · 暂无交集</span>') + '</div>' +
      evilBand(c) +
      '<div class="rolebook-card-meta">' +
        '<span class="rolebook-evil-label rolebook-evil-' + cls + '">' +
          (c.evil < 0 ? '恶 ' : (c.evil > 0 ? '善 ' : '中 ')) + esc(c.evil) + '</span>' +
        '<span class="rolebook-tier">' + esc(tierName(meta, 'evil_tiers', c.evil_tier)) + '</span>' +
        (c.favor ? '<span class="rolebook-favor">好感 ' + esc(c.favor) + '</span>' : '') +
      '</div>' +
      '<div class="rolebook-card-icos">' + abilityIcons(c) + '</div>' +
      '</article>';
  }

  function updateCount(rows, total) {
    var info = $('rolebook-count');
    if (!info) return;
    var related = rows.filter(function (c) { return relevance(c) > 0; }).length;
    info.innerHTML = '命中 <b>' + rows.length + '</b> / ' + total + ' 位 · 与我相关 <b>' + related +
      '</b> 位' + (filters.safe ? ' ｜ <span class="rolebook-safe-hint">安全目标：恶名且可击杀</span>' : '');
  }

  function renderCards(m, reset) {
    var meta = m.meta || {}, map = m.avatar_map || {};
    if (reset) shown = PAGE;
    currentMeta = meta;
    currentRows = sortRows((m.npcs || []).filter(match));
    updateCount(currentRows, (m.npcs || []).length);
    var box = $('rolebook-grid');
    if (!box) return;
    var more = $('rolebook-more-wrap');
    if (!currentRows.length) {
      box.innerHTML = '<div class="rolebook-empty">没有符合条件的 NPC，试试放宽筛选或清空条件。</div>';
      if (more) more.style.display = 'none';
      return;
    }
    var slice = currentRows.slice(0, shown);
    box.innerHTML = slice.map(function (c) { return cardHtml(c, meta, map); }).join('');
    if (more) {
      more.style.display = currentRows.length > shown ? '' : 'none';
      var btn = $('rolebook-more');
      if (btn) btn.textContent = '加载更多（还有 ' + (currentRows.length - shown) + ' 位）';
    }
  }

  function loadMore() {
    shown += PAGE;
    if (lastData) renderCards(lastData, false);
  }

  function kv(k, v) {
    return '<div class="rolebook-kv"><span>' + esc(k) + '</span><b>' + esc(pad(v)) + '</b></div>';
  }
  function section(title, body, extra) {
    return '<section class="rolebook-sec"><h4>' + esc(title) +
      (extra ? '<small>' + esc(extra) + '</small>' : '') + '</h4>' + body + '</section>';
  }

  function relationHtml(c, meta) {
    var detail = c.rel_detail || {};
    var keys = Object.keys(detail);
    if (!keys.length) {
      return '<p class="rolebook-note">存档里暂无与此人的师承、道侣、朋友或仇敌记录。可在游戏中结缘、交好后再来查看关系网。</p>';
    }
    var nodes = keys.map(function (label) {
      var people = (detail[label] || []).map(function (n) {
        return '<span class="rolebook-relperson">' + esc(n) + '</span>';
      }).join('');
      return '<div class="rolebook-relnode rolebook-relnode-' + esc(label) + '">' +
        '<span class="rolebook-rellabel">' + esc(label) + '</span>' +
        '<div class="rolebook-relpeople">' + people + '</div></div>';
    }).join('');
    return '<div class="rolebook-relnet"><div class="rolebook-relme">你</div>' +
      '<div class="rolebook-relnodes">' + nodes + '</div></div>';
  }

  function placeHtml(c) {
    return '<div class="rolebook-place-card">' +
      '<div class="rolebook-place-main"><span class="rolebook-place-ico">⌖</span>' +
        '<div><b>' + esc(c.place || '来历不明') + '</b>' +
        '<small>常驻地 / 出现地点（按境界与行为场景推断）</small></div></div>' +
      '<div class="rolebook-place-flags">' +
        (c.housed ? '<span class="rolebook-place-on">已入住仙居</span>'
                  : '<span class="rolebook-place-off">' + (c.housing_open ? '可邀请入住' : '未入住') + '</span>') +
        (c.sect && c.sect !== '无门无派' ? '<span class="rolebook-place-sect">' + esc(c.sect) + '</span>' : '') +
      '</div></div>';
  }

  function attackHtml(c, meta) {
    var a = c.attack || {};
    function delta(label, val, good) {
      if (!val) return '';
      var cls = good ? 'up' : 'down';
      return '<span class="rolebook-delta rolebook-delta-' + cls + '">' + esc(label) +
        ' ' + (val > 0 ? '+' : '') + esc(val) + '</span>';
    }
    var chase = (meta.chase || []).map(function (row) {
      return '<li>恶值 ≤ <b>' + esc(row.threshold) + '</b>：追杀概率 <b>' + esc(row.prob) + '%</b></li>';
    }).join('');
    return '<div class="rolebook-attack-grid">' +
      delta('善值', a.good, true) + delta('恶值', a.evil, false) +
      delta('城镇声望', a.city, false) + delta('宗门声望', a.sect, false) + '</div>' +
      (a.desc ? '<p class="rolebook-note">' + esc(a.desc) + '</p>' : '') +
      (chase ? '<div class="rolebook-chase"><span>追杀风险（玩家恶值阈值）</span><ul>' + chase + '</ul></div>' : '');
  }

  function intimacyHtml(c, meta) {
    var tiers = meta.intimacy_tiers || [];
    var idx = c.intimacy_index;
    var bars = tiers.map(function (t, i) {
      var on = idx >= 0 && i <= idx;
      var cur = idx === i;
      return '<div class="rolebook-stage' + (on ? ' on' : '') + (cur ? ' cur' : '') + '">' +
        '<span class="rolebook-stage-dot"></span>' +
        '<span class="rolebook-stage-name">' + esc(t.name) + '</span>' +
        '<span class="rolebook-stage-need">≥' + esc(t.min) + '</span></div>';
    }).join('');
    return '<p class="rolebook-lede">当前好感度 <b>' + esc(c.favor) + '</b>' +
      (c.intimacy_name ? '（' + esc(c.intimacy_name) + '）' : '') +
      (c.dao ? ' ｜ <span class="rolebook-dao-tag">已结为道侣</span>' : '') + '</p>' +
      '<div class="rolebook-stages">' + bars + '</div>';
  }

  function openDrawer(c, meta, map) {
    if (!drawer) return;
    var cls = evilClass(c.evil);
    var persona = (meta.personalities || {})[c.personality_id] || {};
    var html = '';
    html += '<div class="rolebook-drawer-head rolebook-head-' + cls + '">' +
      avatarHtml(c, 'rolebook-avatar-lg', map) +
      '<div class="rolebook-drawer-id"><h3>' + esc(c.name) +
        (isSafe(c) ? '<span class="rolebook-badge rolebook-badge-safe">安全目标</span>' : '') + '</h3>' +
        '<div>' + esc(c.realm) + ' · ' + esc(c.sect) + ' · ID ' + esc(c.id) + '</div>' +
        (c.roles && c.roles.length ? '<div class="rolebook-drawer-roles">' + roleTags(c) + '</div>' : '') +
      '</div>' +
      '<button type="button" class="rolebook-close" aria-label="关闭">×</button></div>';

    html += '<div class="rolebook-drawer-body">';
    html += section('基础档案',
      '<div class="rolebook-grid2">' +
      kv('年龄', c.age) + kv('性别', c.sex) + kv('种族', c.race) +
      kv('门派', c.sect) + kv('境界', c.realm) +
      kv('修炼层数', c.layer ? ('第 ' + c.layer + ' 层') : '凡人') +
      kv('五行', (c.element || []).join('、') || '—') +
      kv('寿元调整', (c.lifespan || 0) === 0 ? '—' : (c.lifespan > 0 ? '+' : '') + c.lifespan) + '</div>');
    html += section('位置与住处', placeHtml(c));
    html += section('关系网', relationHtml(c, meta));
    html += section('性格',
      '<div class="rolebook-personality"><span class="rolebook-tag">' + esc(c.personality || '未知') + '</span>' +
      (persona.name && persona.name !== c.personality ? '<span class="rolebook-muted">' + esc(persona.name) + '</span>' : '') + '</div>' +
      (persona.tip || persona.hover ? '<p class="rolebook-note">' + esc(persona.tip || persona.hover) + '</p>' : ''));
    html += section('善恶与声望',
      '<div class="rolebook-duo">' +
        '<div class="rolebook-duo-item rolebook-duo-' + cls + '"><span>善恶值</span><b>' + esc(c.evil) + '</b>' +
          '<small>' + esc(tierName(meta, 'evil_tiers', c.evil_tier)) + '</small>' + evilBand(c) + '</div>' +
        '<div class="rolebook-duo-item"><span>声望值</span><b>' + esc(c.repute) + '</b>' +
          '<small>' + esc(tierName(meta, 'repute_tiers', c.repute_tier)) + '</small></div>' +
      '</div>' +
      (tierDesc(meta, 'evil_tiers', c.evil_tier) ? '<p class="rolebook-note">' +
        esc(tierDesc(meta, 'evil_tiers', c.evil_tier)) + '</p>' : ''));
    html += section('魅力与悟性',
      '<div class="rolebook-grid2">' +
      kv('魅力', c.charm + ' · ' + tierName(meta, 'charm_tiers', c.charm_tier)) +
      kv('悟性', c.wisdom + ' · ' + tierName(meta, 'wisdom_tiers', c.wisdom_tier)) + '</div>' +
      (tierDesc(meta, 'charm_tiers', c.charm_tier) ? '<p class="rolebook-note">' +
        esc(tierDesc(meta, 'charm_tiers', c.charm_tier)) + '</p>' : ''));
    html += section('亲密关系', intimacyHtml(c, meta));
    html += section('天赋槽', c.talents.length
      ? '<p class="rolebook-lede">' + c.slots + ' 个槽位，固定天赋：</p><div class="rolebook-tags">' +
        c.talents.map(function (t) { return '<span class="rolebook-tag rolebook-tag-gold">' + esc(t) + '</span>'; }).join('') + '</div>'
      : '<p class="rolebook-note">' + c.slots + ' 个槽位，均为随机/条件解锁。</p>');
    html += section('可互动动作',
      '<div class="rolebook-acts">' +
      [['可结道侣', c.dao], ['可切磋', c.spar], ['可击杀', c.killable], ['可偷窃', c.steal], ['商人', c.merchant]]
        .map(function (p) {
          return '<span class="rolebook-act' + (p[1] ? ' on' : '') + '">' + p[0] + ' ' + (p[1] ? '✓' : '×') + '</span>';
        }).join('') + '</div>');
    html += section('攻击此人 · 风险', attackHtml(c, meta));
    var rel = [];
    if (c.memoria_titles && c.memoria_titles.length)
      rel.push('<div class="rolebook-rel-label">留影关联（' + c.memoria + '）</div><div class="rolebook-tags">' +
        c.memoria_titles.map(function (t) { return '<span class="rolebook-tag">' + esc(t) + '</span>'; }).join('') + '</div>');
    if (c.topic_titles && c.topic_titles.length)
      rel.push('<div class="rolebook-rel-label">可聊话题（' + c.topics + '）</div><div class="rolebook-tags">' +
        c.topic_titles.map(function (t) { return '<span class="rolebook-tag rolebook-tag-blue">' + esc(t) + '</span>'; }).join('') + '</div>');
    if (c.persuade) rel.push('<div class="rolebook-rel-label">说服话题</div><p class="rolebook-note">' + c.persuade + ' 个</p>');
    if (c.greet) rel.push('<div class="rolebook-rel-label">招呼语</div><p class="rolebook-note">' + esc(c.greet) + '</p>');
    if (c.death) rel.push('<div class="rolebook-rel-label">寿终叙事</div><p class="rolebook-note">' + esc(c.death) + '</p>');
    html += section('关联内容', rel.length ? rel.join('') : '<p class="rolebook-note">暂无关联内容。</p>');
    html += '</div>';

    drawer.innerHTML = html;
    drawer.classList.add('open');
    if (mask) mask.classList.add('show');
    drawer.querySelector('.rolebook-close').onclick = closeDrawer;
  }

  function closeDrawer() {
    if (drawer) drawer.classList.remove('open');
    if (mask) mask.classList.remove('show');
  }

  function playerHtml(p) {
    var c = p.counts || {};
    var items = [
      ['师尊', c.master || 0], ['弟子', c.disciple || 0], ['道侣', c.dao || 0],
      ['朋友', c.friend || 0], ['仇敌', c.enemy || 0], ['入住仙友', c.housed || 0]
    ];
    var h = p.cult_hist || {};
    var hist = [
      h.talent ? '手点天赋' : null, h.pill ? '用突破丹' : null, h.fruit ? '用悟性果' : null
    ].filter(Boolean).join(' · ') || '暂无记录';
    return '<div class="rolebook-player">' +
      '<div class="rolebook-player-stats">' + items.map(function (x) {
        return '<div class="rolebook-pstat"><b>' + esc(x[1]) + '</b><span>' + esc(x[0]) + '</span></div>';
      }).join('') + '</div>' +
      '<div class="rolebook-player-note">玩家善恶 <b>' + esc(p.evil) + '</b>' +
      (p.demonic ? ' · <span class="rolebook-demon">魔修气 ' + esc(p.demon_qi) + '</span>' : '') +
      ' · 已访场景 ' + esc(p.visited || 0) + ' · 培养履历：' + esc(hist) + '</div></div>';
  }

  function bindEvents(m) {
    function bind(id, key) {
      var el = $(id);
      if (!el) return;
      el.onchange = function () { filters[key] = el.value; persist(); renderCards(m, true); };
    }
    var q = $('rolebook-q');
    if (q) q.oninput = function () { filters.q = q.value.trim(); persist(); renderCards(m, true); };
    bind('rolebook-evil', 'evil');
    bind('rolebook-realm', 'realm');
    bind('rolebook-sect', 'sect');
    bind('rolebook-personality', 'personality');
    bind('rolebook-rel', 'rel');
    bind('rolebook-sort', 'sort');
    [['rolebook-f-dao', 'dao'], ['rolebook-f-friend', 'friend'],
     ['rolebook-f-housed', 'housed'], ['rolebook-f-memoria', 'memoria'],
     ['rolebook-f-talent', 'talent'], ['rolebook-f-safe', 'safe']].forEach(function (p) {
      var el = $(p[0]);
      if (!el) return;
      el.onclick = function () { filters[p[1]] = filters[p[1]] ? 0 : 1; persist(); syncChips(); renderCards(m, true); };
    });
    var more = $('rolebook-more');
    if (more) more.onclick = loadMore;
    var reset = $('rolebook-reset');
    if (reset) reset.onclick = function () {
      filters = Object.assign({}, DEFAULTS); persist();
      ['rolebook-evil', 'rolebook-realm', 'rolebook-sect', 'rolebook-personality',
       'rolebook-rel', 'rolebook-sort'].forEach(function (id) {
        var el = $(id); if (el) el.value = DEFAULTS[({
          'rolebook-evil': 'evil', 'rolebook-realm': 'realm', 'rolebook-sect': 'sect',
          'rolebook-personality': 'personality', 'rolebook-rel': 'rel', 'rolebook-sort': 'sort'
        })[id]];
      });
      var qa = $('rolebook-q'); if (qa) qa.value = '';
      syncChips(); renderCards(m, true);
    };
  }

  function syncChips() {
    [['rolebook-f-dao', 'dao'], ['rolebook-f-friend', 'friend'],
     ['rolebook-f-housed', 'housed'], ['rolebook-f-memoria', 'memoria'],
     ['rolebook-f-talent', 'talent'], ['rolebook-f-safe', 'safe']].forEach(function (p) {
      var el = $(p[0]); if (el) el.classList.toggle('on', !!filters[p[1]]);
    });
  }

  function initRolebook(DATA) {
    var m = DATA.modules.rolebook;
    if (!m) return;
    lastData = m;
    var npcs = m.npcs || [], meta = m.meta || {}, stats = m.stats || {}, player = m.player || {};

    var realms = uniq(npcs.map(function (c) { return c.realm_short; }).filter(Boolean));
    var sects = uniq(npcs.map(function (c) { return c.sect; }));
    var persons = uniq(npcs.map(function (c) { return c.personality; }).filter(Boolean));

    view = $('rolebook');
    if (!view) return;
    view.innerHTML = sourceHtml(m) +
      '<div class="rolebook-hero">' +
        '<div class="rolebook-hero-text"><h2>人物图鉴 · NPC 全息档案</h2>' +
        '<p>按存档真实关系与境界整理 ' + esc(stats.total) + ' 位 NPC。默认优先展示与你相关的人，' +
        '有真实头像者直接贴图。善恶、常驻地、关系网与互动履历一应俱全。</p></div>' +
        '<div class="rolebook-hero-figures"><div><b>' + esc(stats.total) + '</b><span>NPC</span></div>' +
        '<div><b>' + esc(Object.keys(m.avatar_map || {}).length) + '</b><span>有头像</span></div>' +
        '<div><b>' + esc((player.counts || {}).friend || 0) + '</b><span>好友</span></div></div>' +
      '</div>' +
      playerHtml(player) +
      '<div class="rolebook-filters">' +
        '<div class="rolebook-filters-row">' +
          '<label class="rolebook-search"><span>查找 NPC</span>' +
            '<input id="rolebook-q" placeholder="名字 / 门派 / 境界 / 地点 / 关系 / ID" value="' + esc(filters.q) + '"></label>' +
          '<label class="rolebook-field"><span>范围</span><select id="rolebook-rel">' +
            [['', '全部 NPC'], ['related', '与我相关（重点）'], ['师尊', '师尊'], ['弟子', '弟子'],
             ['道侣', '道侣'], ['朋友', '朋友'], ['仇敌', '仇敌'], ['已故', '已故']]
              .map(function (p) {
                return '<option value="' + p[0] + '"' + (filters.rel === p[0] ? ' selected' : '') + '>' + p[1] + '</option>';
              }).join('') + '</select></label>' +
          '<label class="rolebook-field"><span>善恶</span><select id="rolebook-evil">' +
            '<option value="">全部</option><option value="bad"' + (filters.evil === 'bad' ? ' selected' : '') + '>恶名</option>' +
            '<option value="mid"' + (filters.evil === 'mid' ? ' selected' : '') + '>中庸</option>' +
            '<option value="good"' + (filters.evil === 'good' ? ' selected' : '') + '>善念</option></select></label>' +
          '<label class="rolebook-field"><span>境界</span><select id="rolebook-realm">' +
            optList(realms, null, filters.realm, '全部境界') + '</select></label>' +
          '<label class="rolebook-field"><span>门派</span><select id="rolebook-sect">' +
            optList(sects, null, filters.sect, '全部门派') + '</select></label>' +
          '<label class="rolebook-field"><span>性格</span><select id="rolebook-personality">' +
            optList(persons, null, filters.personality, '全部性格') + '</select></label>' +
        '</div>' +
        '<div class="rolebook-filters-row rolebook-filters-row2">' +
          '<label class="rolebook-field"><span>排序</span><select id="rolebook-sort">' +
            [['relevance', '与我相关优先'], ['layer', '境界高低'], ['wisdom', '悟性优先'],
             ['favor', '好感优先'], ['evil', '由恶到善'], ['evilDesc', '由善到恶'],
             ['name', '按名字'], ['id', '按 ID']]
              .map(function (p) {
                return '<option value="' + p[0] + '"' + (filters.sort === p[0] ? ' selected' : '') + '>' + p[1] + '</option>';
              }).join('') + '</select></label>' +
        '</div>' +
        '<div class="rolebook-chips">' +
          '<span class="rolebook-chips-label">快捷筛选</span>' +
          '<button type="button" id="rolebook-f-dao" class="rolebook-chip">道侣</button>' +
          '<button type="button" id="rolebook-f-friend" class="rolebook-chip">朋友</button>' +
          '<button type="button" id="rolebook-f-housed" class="rolebook-chip">已入住</button>' +
          '<button type="button" id="rolebook-f-memoria" class="rolebook-chip">有留影</button>' +
          '<button type="button" id="rolebook-f-talent" class="rolebook-chip">固定天赋</button>' +
          '<button type="button" id="rolebook-f-safe" class="rolebook-chip rolebook-chip-safe">安全目标</button>' +
          '<button type="button" id="rolebook-reset" class="rolebook-chip rolebook-chip-reset">清空</button>' +
        '</div>' +
      '</div>' +
      '<div id="rolebook-count" class="rolebook-count"></div>' +
      '<div id="rolebook-grid" class="rolebook-grid"></div>' +
      '<div id="rolebook-more-wrap" class="rolebook-more-wrap" style="display:none">' +
        '<button type="button" id="rolebook-more" class="rolebook-more">加载更多</button></div>';

    if (!drawer) {
      mask = document.createElement('div'); mask.className = 'rolebook-mask'; document.body.appendChild(mask);
      drawer = document.createElement('aside'); drawer.className = 'rolebook-drawer'; document.body.appendChild(drawer);
      mask.onclick = closeDrawer;
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDrawer(); });
    }

    var grid = $('rolebook-grid');
    function openFromEvent(e) {
      var card = e.target.closest('.rolebook-card');
      if (!card) return;
      var c = npcs.find(function (n) { return n.id === num(card.getAttribute('data-npc')); });
      if (c) openDrawer(c, meta, m.avatar_map || {});
    }
    grid.onclick = openFromEvent;
    grid.onkeydown = function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openFromEvent(e); }
    };

    bindEvents(m);
    syncChips();
    renderCards(m, true);
  }

  window.PROGRESS_VIEWS = window.PROGRESS_VIEWS || {};
  window.PROGRESS_VIEWS.rolebook = initRolebook;
})();
