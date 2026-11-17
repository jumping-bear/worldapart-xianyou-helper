/* 人物志（NPC 全息档案）：头像卡片墙 + 多维筛选 + 详情抽屉 + 魔修安全目标。 */
(function () {
  'use strict';
  var STORE_KEY = 'worldapart.rolebook.filters.v1';
  var DEFAULTS = {
    q: '', evil: '', realm: '', sect: '', personality: '',
    dao: 0, kill: 0, extra: '', safe: 0, memoria: 0, talent: 0, sort: 'evil'
  };
  var filters = Object.assign({}, DEFAULTS, store.get(STORE_KEY, {}));
  var view = null, drawer = null, mask = null, lastData = null;

  function persist() { store.set(STORE_KEY, filters); }

  function pad(v) { return String(v == null ? '' : v); }
  function num(v) { return Number(v || 0); }
  function qval(id) { var el = $(id); return el ? el.value : ''; }

  function avatarHtml(card, cls) {
    var ch = (card.name || '?').slice(0, 1);
    return '<div class="rolebook-avatar ' + (cls || '') + '"><span>' + esc(ch) + '</span></div>';
  }

  function abilityIcons(c) {
    var out = [];
    if (c.dao) out.push('<span class="rolebook-ico rolebook-ico-dao" title="可结为道侣">道</span>');
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
    var list = (meta || {})[key] || [];
    var t = list[num(idx)];
    return t ? t.name : '';
  }
  function tierDesc(meta, key, idx) {
    var list = (meta || {})[key] || [];
    var t = list[num(idx)];
    return t ? (t.desc || '') : '';
  }

  // 魔修安全目标：善恶值为负 且 可击杀
  function isSafe(c) { return c.evil < 0 && c.killable; }

  function match(c) {
    if (filters.safe && !isSafe(c)) return false;
    if (filters.q) {
      var hay = (c.name + ' ' + c.sect + ' ' + c.personality + ' ' + c.realm + ' ' + c.id).toLowerCase();
      if (hay.indexOf(filters.q.toLowerCase()) < 0) return false;
    }
    if (filters.evil === 'bad' && !(c.evil < 0)) return false;
    if (filters.evil === 'mid' && c.evil !== 0) return false;
    if (filters.evil === 'good' && !(c.evil > 0)) return false;
    if (filters.realm && c.realm !== filters.realm) return false;
    if (filters.sect && c.sect !== filters.sect) return false;
    if (filters.personality && c.personality !== filters.personality) return false;
    if (filters.dao && !c.dao) return false;
    if (filters.kill && !c.killable) return false;
    if (filters.memoria && !c.memoria) return false;
    if (filters.talent && !c.talents.length) return false;
    return true;
  }

  function sortRows(rows) {
    var by = filters.sort;
    rows.sort(function (a, b) {
      if (by === 'id') return a.id - b.id;
      if (by === 'name') return String(a.name).localeCompare(String(b.name), 'zh-CN');
      if (by === 'evil') return a.evil - b.evil;           // 由恶到善
      if (by === 'evilDesc') return b.evil - a.evil;        // 由善到恶
      if (by === 'wisdom') return b.wisdom - a.wisdom;
      if (by === 'favor') return b.favor - a.favor;
      return a.id - b.id;
    });
    return rows;
  }

  function renderCards(m) {
    var rows = sortRows((m.npcs || []).filter(match));
    var box = $('rolebook-grid');
    var info = $('rolebook-count');
    if (info) {
      info.innerHTML = '命中 <b>' + rows.length + '</b> / ' + m.npcs.length + ' 位 NPC' +
        (filters.safe ? ' ｜ <span class="rolebook-safe-hint">魔修安全目标：恶名且可击杀，下手不增恶值</span>' : '');
    }
    if (!box) return;
    if (!rows.length) {
      box.innerHTML = '<div class="rolebook-empty">没有符合条件的 NPC，试试放宽筛选。</div>';
      return;
    }
    var meta = m.meta || {};
    box.innerHTML = rows.map(function (c) {
      var cls = evilClass(c.evil);
      var badge = isSafe(c) ? '<span class="rolebook-badge rolebook-badge-safe">安全</span>' : '';
      var dao = c.dao ? '<span class="rolebook-badge rolebook-badge-dao">道侣</span>' : '';
      var met = c.met ? '<span class="rolebook-badge rolebook-badge-met">已识</span>' : '';
      return '<article class="rolebook-card rolebook-card-' + cls + '" data-npc="' + c.id + '" tabindex="0">' +
        '<div class="rolebook-card-top">' + avatarHtml(c) +
          '<div class="rolebook-card-id">' +
            '<div class="rolebook-card-name">' + esc(c.name) + dao + '</div>' +
            '<div class="rolebook-card-title">' + esc(c.realm) + ' · ' + esc(c.sect) + '</div>' +
          '</div></div>' +
        '<div class="rolebook-card-personality">' + esc(c.personality || '性格未知') + '</div>' +
        evilBand(c) +
        '<div class="rolebook-card-meta">' +
          '<span class="rolebook-evil-label rolebook-evil-' + cls + '">' +
            (c.evil < 0 ? '恶 ' : (c.evil > 0 ? '善 ' : '中 ')) + esc(c.evil) + '</span>' +
          '<span class="rolebook-tier">' + esc(tierName(meta, 'evil_tiers', c.evil_tier)) + '</span>' +
          badge + met +
        '</div>' +
        '<div class="rolebook-card-icos">' + abilityIcons(c) + '</div>' +
        '</article>';
    }).join('');
  }

  function kv(k, v) {
    return '<div class="rolebook-kv"><span>' + esc(k) + '</span><b>' + esc(pad(v)) + '</b></div>';
  }
  function section(title, body, extra) {
    return '<section class="rolebook-sec"><h4>' + esc(title) +
      (extra ? '<small>' + esc(extra) + '</small>' : '') + '</h4>' + body + '</section>';
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

  function openDrawer(c, meta) {
    if (!drawer) return;
    var cls = evilClass(c.evil);
    var persona = (meta.personalities || {})[c.personality_id] || {};
    var html = '';
    html += '<div class="rolebook-drawer-head rolebook-head-' + cls + '">' +
      avatarHtml(c, 'rolebook-avatar-lg') +
      '<div class="rolebook-drawer-id"><h3>' + esc(c.name) +
        (isSafe(c) ? '<span class="rolebook-badge rolebook-badge-safe">安全目标</span>' : '') + '</h3>' +
        '<div>' + esc(c.realm) + ' · ' + esc(c.sect) + ' · ID ' + esc(c.id) + '</div></div>' +
      '<button type="button" class="rolebook-close" aria-label="关闭">×</button></div>';

    html += '<div class="rolebook-drawer-body">';
    // 基础
    html += section('基础档案',
      '<div class="rolebook-grid2">' +
      kv('年龄', c.age) + kv('性别', c.sex) + kv('种族', c.race) +
      kv('门派', c.sect) + kv('境界', c.realm) +
      kv('五行', (c.element || []).join('、') || '—') + '</div>');
    // 性格
    html += section('性格',
      '<div class="rolebook-personality"><span class="rolebook-tag">' + esc(c.personality || '未知') + '</span>' +
      (persona.name && persona.name !== c.personality ? '<span class="rolebook-muted">' + esc(persona.name) + '</span>' : '') + '</div>' +
      (persona.tip || persona.hover ? '<p class="rolebook-note">' + esc(persona.tip || persona.hover) + '</p>' : ''));
    // 善恶与声望
    html += section('善恶与声望',
      '<div class="rolebook-duo">' +
        '<div class="rolebook-duo-item rolebook-duo-' + cls + '"><span>善恶值</span><b>' + esc(c.evil) + '</b>' +
          '<small>' + esc(tierName(meta, 'evil_tiers', c.evil_tier)) + '</small>' + evilBand(c) + '</div>' +
        '<div class="rolebook-duo-item"><span>声望值</span><b>' + esc(c.repute) + '</b>' +
          '<small>' + esc(tierName(meta, 'repute_tiers', c.repute_tier)) + '</small></div>' +
      '</div>' +
      (tierDesc(meta, 'evil_tiers', c.evil_tier) ? '<p class="rolebook-note">' +
        esc(tierDesc(meta, 'evil_tiers', c.evil_tier)) + '</p>' : ''));
    // 魅力与悟性
    html += section('魅力与悟性',
      '<div class="rolebook-grid2">' +
      kv('魅力', c.charm + ' · ' + tierName(meta, 'charm_tiers', c.charm_tier)) +
      kv('悟性', c.wisdom + ' · ' + tierName(meta, 'wisdom_tiers', c.wisdom_tier)) + '</div>' +
      (tierDesc(meta, 'charm_tiers', c.charm_tier) ? '<p class="rolebook-note">' +
        esc(tierDesc(meta, 'charm_tiers', c.charm_tier)) + '</p>' : ''));
    // 亲密
    html += section('亲密关系', intimacyHtml(c, meta));
    // 资质/天赋
    html += section('天赋槽', c.talents.length
      ? '<p class="rolebook-lede">' + c.slots + ' 个槽位，固定天赋：</p><div class="rolebook-tags">' +
        c.talents.map(function (t) { return '<span class="rolebook-tag rolebook-tag-gold">' + esc(t) + '</span>'; }).join('') + '</div>'
      : '<p class="rolebook-note">' + c.slots + ' 个槽位，均为随机/条件解锁。</p>');
    // 互动动作
    html += section('可互动动作',
      '<div class="rolebook-acts">' +
      [['可结道侣', c.dao], ['可切磋', c.spar], ['可击杀', c.killable], ['可偷窃', c.steal], ['商人', c.merchant]]
        .map(function (p) {
          return '<span class="rolebook-act' + (p[1] ? ' on' : '') + '">' + p[0] + ' ' + (p[1] ? '✓' : '×') + '</span>';
        }).join('') + '</div>');
    // 攻击风险
    html += section('攻击此人 · 风险', attackHtml(c, meta));
    // 关联内容
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

  function bindEvents(m) {
    function bind(id, key, cast) {
      var el = $(id);
      if (!el) return;
      el.onchange = function () { filters[key] = cast ? cast(el.value) : el.value; persist(); renderCards(m); };
    }
    var q = $('rolebook-q');
    if (q) q.oninput = function () { filters.q = q.value.trim(); persist(); renderCards(m); };
    bind('rolebook-evil', 'evil');
    bind('rolebook-realm', 'realm');
    bind('rolebook-sect', 'sect');
    bind('rolebook-personality', 'personality');
    bind('rolebook-sort', 'sort');
    [['rolebook-f-dao', 'dao'], ['rolebook-f-kill', 'kill'],
     ['rolebook-f-memoria', 'memoria'], ['rolebook-f-talent', 'talent'],
     ['rolebook-f-safe', 'safe']].forEach(function (p) {
      var el = $(p[0]);
      if (!el) return;
      el.onclick = function () { filters[p[1]] = filters[p[1]] ? 0 : 1; persist(); syncChips(); renderCards(m); };
    });
    var reset = $('rolebook-reset');
    if (reset) reset.onclick = function () {
      filters = Object.assign({}, DEFAULTS); persist();
      var selects = {
        'rolebook-evil': 'evil', 'rolebook-realm': 'realm', 'rolebook-sect': 'sect',
        'rolebook-personality': 'personality', 'rolebook-sort': 'sort'
      };
      Object.keys(selects).forEach(function (id) {
        var el = $(id); if (el) el.value = DEFAULTS[selects[id]];
      });
      var qa = $('rolebook-q'); if (qa) qa.value = '';
      syncChips(); renderCards(m);
    };
  }

  function syncChips() {
    [['rolebook-f-dao', 'dao'], ['rolebook-f-kill', 'kill'],
     ['rolebook-f-memoria', 'memoria'], ['rolebook-f-talent', 'talent'],
     ['rolebook-f-safe', 'safe']].forEach(function (p) {
      var el = $(p[0]); if (el) el.classList.toggle('on', !!filters[p[1]]);
    });
  }

  function initRolebook(DATA) {
    var m = DATA.modules.rolebook;
    if (!m) return;
    lastData = m;
    var npcs = m.npcs || [], meta = m.meta || {}, stats = m.stats || {};

    // 维度取值
    var realms = uniq(npcs.map(function (c) { return c.realm; }));
    var sects = uniq(npcs.map(function (c) { return c.sect; }));
    var persons = uniq(npcs.map(function (c) { return c.personality; }).filter(Boolean));

    view = $('rolebook');
    if (!view) return;
    view.innerHTML = sourceHtml(m) +
      '<div class="rolebook-hero">' +
        '<div class="rolebook-hero-text"><h2>人物志 · NPC 全息档案</h2>' +
        '<p>把性格、善恶、关系、资质与攻击风险聚合成一张卡。共 ' + esc(stats.total) +
        ' 位 NPC，' + esc(stats.with_avatar) + ' 位有头像，' + esc(stats.dao) +
        ' 位可结道侣，' + esc(stats.safe_target) + ' 位恶名安全目标。</p></div>' +
        '<button type="button" id="rolebook-f-safe" class="rolebook-safe-btn' + (filters.safe ? ' on' : '') + '">' +
          '<span class="rolebook-safe-icon">⚔</span> 魔修模式：安全目标' +
          '<small>恶名且可击杀</small></button>' +
      '</div>' +
      '<div class="rolebook-filters">' +
        '<div class="rolebook-filters-row">' +
          '<label class="rolebook-search"><span>查找 NPC</span>' +
            '<input id="rolebook-q" placeholder="名字 / 门派 / 性格 / ID" value="' + esc(filters.q) + '"></label>' +
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
          '<label class="rolebook-field"><span>排序</span><select id="rolebook-sort">' +
            [['evil', '由恶到善'], ['evilDesc', '由善到恶'], ['wisdom', '悟性优先'],
             ['favor', '好感优先'], ['name', '按名字'], ['id', '按 ID']]
              .map(function (p) {
                return '<option value="' + p[0] + '"' + (filters.sort === p[0] ? ' selected' : '') + '>' + p[1] + '</option>';
              }).join('') + '</select></label>' +
        '</div>' +
        '<div class="rolebook-chips">' +
          '<span class="rolebook-chips-label">快捷筛选</span>' +
          '<button type="button" id="rolebook-f-dao" class="rolebook-chip">可结道侣</button>' +
          '<button type="button" id="rolebook-f-kill" class="rolebook-chip">可击杀</button>' +
          '<button type="button" id="rolebook-f-memoria" class="rolebook-chip">有留影</button>' +
          '<button type="button" id="rolebook-f-talent" class="rolebook-chip">有固定天赋</button>' +
          '<button type="button" id="rolebook-reset" class="rolebook-chip rolebook-chip-reset">清空</button>' +
        '</div>' +
      '</div>' +
      '<div id="rolebook-count" class="rolebook-count"></div>' +
      '<div id="rolebook-grid" class="rolebook-grid"></div>';

    // 抽屉 + 遮罩，挂到 body 避免被面板 overflow 影响
    if (!drawer) {
      mask = document.createElement('div'); mask.className = 'rolebook-mask'; document.body.appendChild(mask);
      drawer = document.createElement('aside'); drawer.className = 'rolebook-drawer'; document.body.appendChild(drawer);
      mask.onclick = closeDrawer;
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDrawer(); });
    }

    var grid = $('rolebook-grid');
    grid.onclick = function (e) {
      var card = e.target.closest('.rolebook-card');
      if (!card) return;
      var c = npcs.find(function (n) { return n.id === num(card.getAttribute('data-npc')); });
      if (c) openDrawer(c, meta);
    };
    grid.onkeydown = function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      var card = e.target.closest('.rolebook-card');
      if (!card) return;
      e.preventDefault();
      var c = npcs.find(function (n) { return n.id === num(card.getAttribute('data-npc')); });
      if (c) openDrawer(c, meta);
    };

    bindEvents(m);
    syncChips();
    renderCards(m);
  }

  window.PROGRESS_VIEWS = window.PROGRESS_VIEWS || {};
  window.PROGRESS_VIEWS.rolebook = initRolebook;
})();
