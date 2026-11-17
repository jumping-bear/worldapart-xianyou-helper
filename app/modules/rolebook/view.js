/* 人物图鉴：以"现在在哪、他和我什么关系、能对他做什么"为主线的 NPC 档案墙。 */
(function () {
  'use strict';
  var STORE_KEY = 'worldapart.rolebook.filters.v4';
  var DEFAULTS = {
    q: '', rel: '', evil: '', realm: '', sect: '', personality: '',
    present: 0, met: 0, dao: 0, friend: 0, housed: 0, evilneg: 0,
    spar: 0, steal: 0, merchant: 0, attackable: 0, memoria: 0, talent: 0,
    sort: 'relevance'
  };
  var PAGE = 48;  // 分批渲染步长
  var filters = Object.assign({}, DEFAULTS, store.get(STORE_KEY, {}));
  var view = null, drawer = null, mask = null, lastData = null;
  var shown = PAGE, currentRows = [], currentMeta = null;

  function persist() { store.set(STORE_KEY, filters); }
  function num(v) { return Number(v || 0); }
  function pad(v) { return String(v == null ? '' : v); }

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

  // 卡片只保留玩家做决策会用到的能力标记
  function abilityIcons(c) {
    var out = [];
    if (c.met) out.push('<span class="rolebook-ico rolebook-ico-met" title="有交情">识</span>');
    if (c.housed) out.push('<span class="rolebook-ico rolebook-ico-house" title="已入住仙居">宅</span>');
    if (c.dao) out.push('<span class="rolebook-ico rolebook-ico-dao" title="道侣">道</span>');
    if (c.spar) out.push('<span class="rolebook-ico rolebook-ico-spar" title="可切磋">切</span>');
    if (c.steal) out.push('<span class="rolebook-ico rolebook-ico-steal" title="可偷窃">窃</span>');
    if (c.merchant) out.push('<span class="rolebook-ico rolebook-ico-mer" title="商人">商</span>');
    if (c.memoria) out.push('<span class="rolebook-ico rolebook-ico-mem" title="留有影像">影</span>');
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

  function optList(values, selected, allLabel) {
    var html = '<option value="">' + esc(allLabel) + '</option>';
    values.forEach(function (v) {
      html += '<option value="' + esc(v) + '"' + (String(selected) === String(v) ? ' selected' : '') +
        '>' + esc(v) + '</option>';
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

  // 位置两层：主=空间名，副=完整路径/地区。不在存档里的只给配置常驻地区。
  function placeLines(c) {
    if (c.present && !c.gone) {
      return { main: c.loc_name || c.loc, sub: c.loc, off: false };
    }
    if (c.present && c.gone) {
      return { main: '已退隐', sub: '不在当前世界', off: true };
    }
    return {
      main: '尚未在当前世界出现',
      sub: c.config_region ? ('常驻地区（配置）：' + c.config_region) : '暂无实时位置',
      off: true
    };
  }
  function placeText(c) { return placeLines(c).main; }

  // 相关性权重：与我有关的人排在最前
  function relevance(c) {
    var w = 0;
    if (c.roles && c.roles.length) w += 10 + c.roles.length;
    if (c.dao) w += 6;
    if (c.housed) w += 5;
    if (c.met) w += 4;
    if (c.memoria) w += 2;
    return w;
  }

  function match(c) {
    if (filters.q) {
      var hay = (c.name + ' ' + c.title + ' ' + c.sect + ' ' + c.personality + ' ' + c.realm +
        ' ' + c.loc + ' ' + c.region + ' ' + c.config_region + ' ' +
        (c.roles || []).join(' ') + ' ' + c.id).toLowerCase();
      if (hay.indexOf(filters.q.toLowerCase()) < 0) return false;
    }
    if (filters.evil === 'bad' && !(c.evil < 0)) return false;
    if (filters.evil === 'mid' && c.evil !== 0) return false;
    if (filters.evil === 'good' && !(c.evil > 0)) return false;
    if (filters.realm && c.realm_short !== filters.realm && c.realm !== filters.realm) return false;
    if (filters.sect && c.sect !== filters.sect) return false;
    if (filters.personality && c.personality !== filters.personality) return false;
    if (filters.present && !c.present) return false;
    if (filters.met && !c.met) return false;
    if (filters.dao && !c.dao) return false;
    if (filters.friend && (c.roles || []).indexOf('朋友') < 0) return false;
    if (filters.housed && !c.housed) return false;
    if (filters.evilneg && !(c.evil < 0)) return false;
    if (filters.spar && !c.spar) return false;
    if (filters.steal && !c.steal) return false;
    if (filters.merchant && !c.merchant) return false;
    if (filters.attackable && !c.killable) return false;
    if (filters.memoria && !c.memoria) return false;
    if (filters.talent && !(c.talents || []).length) return false;
    if (filters.rel) {
      if (filters.rel === 'present') { if (!c.present) return false; }
      else if (filters.rel === 'met') { if (!c.met) return false; }
      else if ((c.roles || []).indexOf(filters.rel) < 0) return false;
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
      if (by === 'favor') return b.favor - a.favor;
      if (by === 'layer') return b.layer_order - a.layer_order;
      return a.id - b.id;
    });
    return rows;
  }

  function cardHtml(c, meta, map) {
    var cls = evilClass(c.evil);
    var badges = roleTags(c) || (c.met ? '<span class="rolebook-role-none">有交情 · 暂无关系</span>'
                                     : (c.present ? '<span class="rolebook-role-none">在世 · 尚未结识</span>'
                                                  : '<span class="rolebook-role-none">未在当前世界</span>'));
    var place = placeLines(c);
    return '<article class="rolebook-card rolebook-card-' + cls + '" data-npc="' + c.id + '" tabindex="0">' +
      '<div class="rolebook-card-top">' + avatarHtml(c, '', map) +
        '<div class="rolebook-card-id">' +
          '<div class="rolebook-card-name">' + esc(c.name) + '</div>' +
          '<div class="rolebook-card-title">' + esc(c.title || c.sect) + '</div>' +
          '<div class="rolebook-card-realm">' + esc(c.realm) + '</div>' +
        '</div></div>' +
      '<div class="rolebook-card-place' + (place.off ? ' rolebook-card-place-off' : '') + '" title="' + esc(place.sub) + '">' +
        '<span class="rolebook-pin">⌖</span>' +
        '<span class="rolebook-place-box"><span class="rolebook-place-main">' + esc(place.main) + '</span>' +
        '<span class="rolebook-place-sub">' + esc(place.sub) + '</span></span></div>' +
      '<div class="rolebook-card-badges">' + badges + '</div>' +
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

  var CHIPS = [
    ['present', '在世'], ['met', '有交情'], ['dao', '道侣'], ['friend', '朋友'], ['housed', '已入住'],
    ['evilneg', '负善恶'], ['spar', '可切磋'], ['steal', '可偷窃'],
    ['merchant', '商人'], ['attackable', '可攻击'], ['memoria', '有留影'], ['talent', '固定天赋']
  ];

  function updateCount(rows, total) {
    var info = $('rolebook-count');
    if (!info) return;
    var present = rows.filter(function (c) { return c.present; }).length;
    var met = rows.filter(function (c) { return c.met; }).length;
    info.innerHTML = '命中 <b>' + rows.length + '</b> / ' + total + ' 位 · 在世 <b>' + present +
      '</b> 位 · 有交情 <b>' + met + '</b> 位';
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
      return '<p class="rolebook-note">存档里没有与此人的师承、道侣、朋友或仇敌记录。</p>';
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

  function locationHtml(c) {
    var place = placeLines(c);
    var mainCls = place.off ? ' rolebook-place-unknown' : '';
    var note;
    if (c.present && !c.gone) {
      note = '当前所在（存档实时）· 地区 ' + (c.region || '—') + ' · 可直接去这里找 ' + c.name;
    } else if (c.present && c.gone) {
      note = '寿元已尽或已退隐，当前世界找不到这个人';
    } else {
      note = '不在当前存档里，可能尚未生成或已退隐；配置只给到门派驻地这一级，仅供参考';
    }
    var live = c.present && !c.gone
      ? '<div class="rolebook-place-name">' + esc(c.loc_name || c.loc) + '</div>' +
        '<div class="rolebook-place-path">' + esc(c.loc) + '</div>'
      : '<div class="rolebook-place-name' + mainCls + '">' + esc(place.main) + '</div>' +
        '<div class="rolebook-place-path rolebook-place-unknown">' + esc(place.sub) + '</div>';
    return '<div class="rolebook-place-card">' +
      '<div class="rolebook-place-head"><span class="rolebook-place-ico">⌖</span>' +
        '<div class="rolebook-place-body"><b>当前所在</b>' + live +
        '<small>' + esc(note) + '</small></div></div></div>';
  }

  function attackHtml(c, meta) {
    if (!c.killable) {
      return '<p class="rolebook-note">此人在配置里不可攻击。' +
        (c.dao ? '对方与你有道侣关系，动手也会直接破坏关系。' : '') + '</p>';
    }
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
    return '<p class="rolebook-note">可攻击。动手后的代价：</p>' +
      '<div class="rolebook-attack-grid">' +
      delta('善值', a.good, true) + delta('恶值', a.evil, false) +
      delta('城镇声望', a.city, false) + delta('宗门声望', a.sect, false) + '</div>' +
      (a.desc ? '<p class="rolebook-note">' + esc(a.desc) + '</p>' : '') +
      (chase ? '<div class="rolebook-chase"><span>被追杀的恶值阈值</span><ul>' + chase + '</ul></div>' : '');
  }

  function favorHtml(c, meta) {
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
    if (!c.met) {
      return '<p class="rolebook-note">尚未结识，暂无好感记录。</p>';
    }
    return '<p class="rolebook-lede">好感 <b>' + esc(c.favor) + '</b>' +
      (c.intimacy_name ? '（' + esc(c.intimacy_name) + '）' : '') +
      (c.dao ? ' ｜ <span class="rolebook-dao-tag">道侣</span>' : '') + '</p>' +
      '<div class="rolebook-stages">' + bars + '</div>';
  }

  function housingHtml(c) {
    var text = c.housed ? '已入住你的仙居'
      : (c.housing_open ? '未入住 · 仙居已开，可邀请' : '未入住');
    return '<div class="rolebook-inline"><span>住处</span>' +
      '<span class="rolebook-tag' + (c.housed ? ' rolebook-tag-gold' : '') + '">' + esc(text) + '</span></div>';
  }

  function actsHtml(c) {
    var items = [
      ['可结道侣', c.dao_capable], ['可切磋', c.spar],
      ['可偷窃', c.steal], ['商人', c.merchant]
    ];
    return '<div class="rolebook-acts">' + items.map(function (p) {
      return '<span class="rolebook-act' + (p[1] ? ' on' : ' off') + '">' +
        p[0] + ' ' + (p[1] ? '✓' : '×') + '</span>';
    }).join('') + '</div>' +
      (!c.killable ? '<p class="rolebook-note">配置上不可攻击（剧情或寿元保护角色）。</p>' : '');
  }

  function openDrawer(c, meta, map) {
    if (!drawer) return;
    var cls = evilClass(c.evil);
    var persona = (meta.personalities || {})[c.personality_id] || {};
    var html = '';
    html += '<div class="rolebook-drawer-head rolebook-head-' + cls + '">' +
      avatarHtml(c, 'rolebook-avatar-lg', map) +
      '<div class="rolebook-drawer-id"><h3>' + esc(c.name) + '</h3>' +
        '<div>' + esc(c.title || '无称号') + ' · ' + esc(c.sect) + '</div>' +
        '<div class="rolebook-drawer-sub">' + esc(c.realm) + '<span class="rolebook-id">ID ' + esc(c.id) + '</span></div>' +
        (c.roles && c.roles.length ? '<div class="rolebook-drawer-roles">' + roleTags(c) + '</div>' : '') +
      '</div>' +
      '<button type="button" class="rolebook-close" aria-label="关闭">×</button></div>';

    html += '<div class="rolebook-drawer-body">';
    html += section('当前所在', locationHtml(c));
    html += section('是谁',
      '<div class="rolebook-grid2">' +
      kv('身份', c.title || '—') + kv('门派', c.sect) +
      kv('境界', c.realm) + kv('年龄', (c.age || 0) + ' 岁') +
      kv('性别', c.sex) + kv('种族', c.race) +
      kv('性格', c.personality || '未知') + kv('五行', (c.element || []).join('、') || '—') +
      '</div>' +
      (persona.desc ? '<p class="rolebook-note">' + esc(persona.desc) + '</p>' : '') +
      ((c.talents || []).length ? '<div class="rolebook-inline"><span>固定天赋</span>' +
        c.talents.map(function (t) { return '<span class="rolebook-tag rolebook-tag-gold">' + esc(t) + '</span>'; }).join('') +
        '</div>' : ''));
    html += section('我和他', relationHtml(c, meta) + favorHtml(c, meta) + housingHtml(c));
    html += section('能做什么', actsHtml(c));
    html += section('善恶与后果',
      '<div class="rolebook-duo">' +
        '<div class="rolebook-duo-item rolebook-duo-' + cls + '"><span>善恶值</span><b>' + esc(c.evil) + '</b>' +
          '<small>' + esc(tierName(meta, 'evil_tiers', c.evil_tier)) + '</small>' + evilBand(c) + '</div>' +
        '<div class="rolebook-duo-item"><span>声望值</span><b>' + esc(c.repute) + '</b>' +
          '<small>' + esc(tierName(meta, 'repute_tiers', c.repute_tier)) + '</small></div>' +
      '</div>' +
      (tierDesc(meta, 'evil_tiers', c.evil_tier) ? '<p class="rolebook-note">' +
        esc(tierDesc(meta, 'evil_tiers', c.evil_tier)) + '</p>' : '') +
      attackHtml(c, meta));
    var rel = [];
    if (c.memoria_titles && c.memoria_titles.length)
      rel.push('<div class="rolebook-rel-label">留影（' + c.memoria + '）</div><div class="rolebook-tags">' +
        c.memoria_titles.map(function (t) { return '<span class="rolebook-tag">' + esc(t) + '</span>'; }).join('') + '</div>');
    if (c.topic_titles && c.topic_titles.length)
      rel.push('<div class="rolebook-rel-label">可聊话题（' + c.topics + '）</div><div class="rolebook-tags">' +
        c.topic_titles.map(function (t) { return '<span class="rolebook-tag rolebook-tag-blue">' + esc(t) + '</span>'; }).join('') + '</div>');
    if (c.persuade) rel.push('<div class="rolebook-rel-label">可说服话题</div><p class="rolebook-note">' + c.persuade + ' 个</p>');
    if (c.death) rel.push('<div class="rolebook-rel-label">寿终叙事</div><p class="rolebook-note">' + esc(c.death) + '</p>');
    html += section('履历', rel.length ? rel.join('') : '<p class="rolebook-note">暂无留影、话题或剧情记录。</p>');
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

  function statsHtml(m) {
    var live = m.live_stats || {}, counts = (m.player || {}).counts || {}, stats = m.stats || {};
    var items = [
      ['道侣', counts.dao || 0], ['朋友', counts.friend || 0], ['敌仇', counts.enemy || 0],
      ['已入住', counts.housed || 0], ['负善恶', live.evil_met || 0]
    ];
    return '<div class="rolebook-player"><div class="rolebook-player-stats">' +
      items.map(function (x) {
        return '<div class="rolebook-pstat"><b>' + esc(x[1]) + '</b><span>' + esc(x[0]) + '</span></div>';
      }).join('') + '</div>' +
      '<div class="rolebook-player-note">共收录 <b>' + esc(stats.total || 0) + '</b> 位 NPC · ' +
      '你的善恶值 <b>' + esc((m.player || {}).evil || 0) + '</b>' +
      ((m.player || {}).demonic ? ' · <span class="rolebook-demon">魔修气 ' + esc(m.player.demon_qi) + '</span>' : '') +
      '</div></div>';
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
    CHIPS.forEach(function (p) {
      var el = $('rolebook-f-' + p[0]);
      if (!el) return;
      el.onclick = function () {
        filters[p[0]] = filters[p[0]] ? 0 : 1;
        persist(); syncChips(); renderCards(m, true);
      };
    });
    var more = $('rolebook-more');
    if (more) more.onclick = loadMore;
    var reset = $('rolebook-reset');
    if (reset) reset.onclick = function () {
      filters = Object.assign({}, DEFAULTS); persist();
      ['rolebook-evil', 'rolebook-realm', 'rolebook-sect', 'rolebook-personality',
       'rolebook-rel', 'rolebook-sort'].forEach(function (id) {
        var el = $(id); if (el) el.value = '';
      });
      var qa = $('rolebook-q'); if (qa) qa.value = '';
      syncChips(); renderCards(m, true);
    };
  }

  function syncChips() {
    CHIPS.forEach(function (p) {
      var el = $('rolebook-f-' + p[0]);
      if (el) el.classList.toggle('on', !!filters[p[0]]);
    });
  }

  function initRolebook(DATA) {
    var m = DATA.modules.rolebook;
    if (!m) return;
    // 占位 NPC（匿名 / 负 id）玩家永远遇不到，页面层不再展示
    m.npcs = (m.npcs || []).filter(function (n) {
      return n && num(n.id) > 0 && String(n.name || '').indexOf('匿名') !== 0;
    });
    lastData = m;
    var npcs = m.npcs || [], meta = m.meta || {}, stats = m.stats || {};

    var realms = uniq(npcs.map(function (c) { return c.realm_short; }).filter(Boolean));
    var sects = uniq(npcs.map(function (c) { return c.sect; }));
    var persons = uniq(npcs.map(function (c) { return c.personality; }).filter(Boolean));

    view = $('rolebook');
    if (!view) return;
    view.innerHTML = sourceHtml(m) +
      '<div class="rolebook-hero">' +
        '<div class="rolebook-hero-text"><h2>人物图鉴 · NPC 档案</h2>' +
        '<p><b>在世</b>是存档里真实存在、能定位的人；<b>有交情</b>才是打过交道的那一小撮。' +
        '位置来自存档实时空间，不在当前世界的只给配置常驻地区。</p></div>' +
        '<div class="rolebook-hero-figures">' +
          '<div><b>' + esc(stats.total || 0) + '</b><span>图鉴</span></div>' +
          '<div><b>' + esc((m.live_stats || {}).present || 0) + '</b><span>在世</span></div>' +
          '<div><b>' + esc((m.live_stats || {}).met || 0) + '</b><span>有交情</span></div>' +
        '</div>' +
      '</div>' +
      statsHtml(m) +
      '<div class="rolebook-filters">' +
        '<div class="rolebook-filters-row">' +
          '<label class="rolebook-search"><span>查找 NPC</span>' +
            '<input id="rolebook-q" placeholder="名字 / 称号 / 门派 / 境界 / 地点 / 关系" value="' + esc(filters.q) + '"></label>' +
          '<label class="rolebook-field"><span>范围</span><select id="rolebook-rel">' +
            [['', '全部 NPC'], ['present', '在世（可定位）'], ['met', '有交情'], ['师尊', '师尊'], ['弟子', '弟子'],
             ['道侣', '道侣'], ['朋友', '朋友'], ['仇敌', '仇敌'], ['已故', '已故']]
              .map(function (p) {
                return '<option value="' + p[0] + '"' + (filters.rel === p[0] ? ' selected' : '') + '>' + p[1] + '</option>';
              }).join('') + '</select></label>' +
          '<label class="rolebook-field"><span>善恶</span><select id="rolebook-evil">' +
            '<option value="">全部</option><option value="bad"' + (filters.evil === 'bad' ? ' selected' : '') + '>恶名</option>' +
            '<option value="mid"' + (filters.evil === 'mid' ? ' selected' : '') + '>中庸</option>' +
            '<option value="good"' + (filters.evil === 'good' ? ' selected' : '') + '>善念</option></select></label>' +
          '<label class="rolebook-field"><span>境界</span><select id="rolebook-realm">' +
            optList(realms, filters.realm, '全部境界') + '</select></label>' +
          '<label class="rolebook-field"><span>门派</span><select id="rolebook-sect">' +
            optList(sects, filters.sect, '全部门派') + '</select></label>' +
          '<label class="rolebook-field"><span>性格</span><select id="rolebook-personality">' +
            optList(persons, filters.personality, '全部性格') + '</select></label>' +
        '</div>' +
        '<div class="rolebook-filters-row rolebook-filters-row2">' +
          '<label class="rolebook-field"><span>排序</span><select id="rolebook-sort">' +
            [['relevance', '与我相关优先'], ['layer', '境界高低'], ['favor', '好感优先'],
             ['evil', '由恶到善'], ['evilDesc', '由善到恶'], ['name', '按名字'], ['id', '按 ID']]
              .map(function (p) {
                return '<option value="' + p[0] + '"' + (filters.sort === p[0] ? ' selected' : '') + '>' + p[1] + '</option>';
              }).join('') + '</select></label>' +
        '</div>' +
        '<div class="rolebook-chips">' +
          '<span class="rolebook-chips-label">快捷筛选</span>' +
          CHIPS.map(function (p) {
            return '<button type="button" id="rolebook-f-' + p[0] + '" class="rolebook-chip">' + p[1] + '</button>';
          }).join('') +
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
