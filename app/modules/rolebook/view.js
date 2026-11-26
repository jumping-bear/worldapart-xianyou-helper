/* 人物图鉴：以"现在在哪、他和我什么关系、能对他做什么"为主线的 NPC 档案墙。 */
(function () {
  'use strict';
  var STORE_KEY = 'worldapart.rolebook.filters.v8';
  var DEFAULTS = {
    q: '', state: 'alive', rel: '', evil: '', realm: '', sect: '', personality: '', region: '', loc: '',
    met: 0, dao: 0, friend: 0, housed: 0, evilneg: 0,
    safe: 0, spar: 0, steal: 0, merchant: 0, attackable: 0, memoria: 0, talent: 0,
    mortal: 0,
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
  function avatarHtml(c, cls, map, pics) {
    var ref = (map || {})[String(c.id)] || '';
    var uri = ref.indexOf('data:') === 0 ? ref : ((pics || {})[ref] || '');
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
  // 在世 = 当前世界可交互；已寿终/已退隐/尚未登场都不能再攻击、切磋或交易。
  function isAlive(c) { return !!(c.present && !c.gone); }
  function abilityIcons(c) {
    var alive = isAlive(c), out = [];
    if (c.met) out.push('<span class="rolebook-ico rolebook-ico-met" title="有交情">识</span>');
    if (c.housed) out.push('<span class="rolebook-ico rolebook-ico-house" title="已入住仙居">宅</span>');
    if (c.dao) out.push('<span class="rolebook-ico rolebook-ico-dao" title="道侣">道</span>');
    if (alive && c.spar) out.push('<span class="rolebook-ico rolebook-ico-spar" title="可切磋">切</span>');
    if (alive && c.steal) out.push('<span class="rolebook-ico rolebook-ico-steal" title="可偷窃">窃</span>');
    if (alive && c.merchant) out.push('<span class="rolebook-ico rolebook-ico-mer" title="商人">商</span>');
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

  // 凡人寿命徽标：剧情保护 > 已超寿元 > 余寿若干年；修士不显示
  function lifespanText(c) {
    if (!c.mortal) return '';
    if (c.lifespan_protected) return '凡人 · 剧情保护';
    if (c.remaining_years == null) return '凡人';
    return c.remaining_years < 0 ? '凡人 · 已超寿元' : '凡人 · 余寿 ' + c.remaining_years + ' 年';
  }
  // 凡人寿命徽标：剧情保护 > 已超寿元 > 余寿若干年；修士与已退隐的人不显示
  function lifespanHtml(c) {
    if (!c.mortal || c.gone) return '';
    var cls = c.lifespan_protected ? ' rolebook-lifespan-prot'
      : (c.remaining_years != null && c.remaining_years < 0 ? ' rolebook-lifespan-over' : '');
    return '<span class="rolebook-lifespan' + cls + '">' + esc(lifespanText(c)) + '</span>';
  }

  function optList(values, selected, allLabel) {
    var html = '<option value="">' + esc(allLabel) + '</option>';
    values.forEach(function (v) {
      html += '<option value="' + esc(v) + '"' + (String(selected) === String(v) ? ' selected' : '') +
        '>' + esc(v) + '</option>';
    });
    return html;
  }

  // 地点按地区分组：新增地图/子地点直接从存档数据派生，不需要改代码。
  function locOptions(npcs, selected) {
    var groups = {};
    npcs.forEach(function (c) {
      if (!c.loc_name) return;
      var region = c.region || '其他';
      groups[region] = groups[region] || {};
      groups[region][c.loc_name] = 1;
    });
    var html = '<option value="">全部地点</option>';
    Object.keys(groups).sort().forEach(function (region) {
      html += '<optgroup label="' + esc(region) + '">' +
        Object.keys(groups[region]).sort().map(function (name) {
          return '<option value="' + esc(name) + '"' +
            (selected === name ? ' selected' : '') + '>' + esc(name) + '</option>';
        }).join('') + '</optgroup>';
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

  // 位置两层：主=空间名，副=完整路径/地区。不在存档里的如实标注，不用配置常驻地兜底。
  function placeLines(c) {
    if (c.present && !c.gone) {
      return { main: c.loc_name || c.loc, sub: c.loc, off: false };
    }
    if (c.present && c.gone) {
      return c.gone_reason === 'dead'
        ? { main: '已寿终', sub: '寿元已尽 · 不在当前世界', off: true }
        : { main: '已退隐', sub: '不在当前世界（境界突破 / 剧情清退）', off: true };
    }
    return { main: '尚未登场', sub: '存档里还没有这个人', off: true };
  }
  function placeText(c) { return placeLines(c).main; }

  // 相关性权重：与我有关的人排在最前
  function relevance(c) {
    var w = 0;
    if (c.roles && c.roles.length) w += 10 + c.roles.length;
    if (c.dao) w += 6;
    if (c.housed) w += 5;
    if (c.special_name) w += 8;
    if (c.met) w += 4;
    if (c.memoria) w += 2;
    return w;
  }

  function match(c) {
    if (filters.q) {
      var hay = (c.name + ' ' + c.title + ' ' + c.sect + ' ' + c.personality + ' ' + c.realm +
        ' ' + c.loc + ' ' + c.region + ' ' +
        (c.roles || []).join(' ') + ' ' + c.id).toLowerCase();
      if (hay.indexOf(filters.q.toLowerCase()) < 0) return false;
    }
    if (filters.evil === 'bad' && !(c.evil < 0)) return false;
    if (filters.evil === 'mid' && c.evil !== 0) return false;
    if (filters.evil === 'good' && !(c.evil > 0)) return false;
    if (filters.realm && c.realm_short !== filters.realm && c.realm !== filters.realm) return false;
    if (filters.sect && c.sect !== filters.sect) return false;
    if (filters.region && c.region !== filters.region) return false;
    if (filters.loc && c.loc_name !== filters.loc) return false;
    if (filters.personality && c.personality !== filters.personality) return false;
    if (filters.state === 'alive' && !isAlive(c)) return false;
    if (filters.state === 'dead' && c.gone_reason !== 'dead') return false;
    if (filters.state === 'retired' && c.gone_reason !== 'retired') return false;
    if (filters.state === 'absent' && c.gone_reason !== 'absent') return false;
    if (filters.met && !c.met) return false;
    if (filters.special && !c.special_name) return false;
    if (filters.dao && !c.dao) return false;
    if (filters.friend && (c.roles || []).indexOf('朋友') < 0) return false;
    if (filters.housed && !c.housed) return false;
    if (filters.evilneg && !(c.evil < 0)) return false;
    // 攻击/切磋/偷窃/交易都只对“在世”的人生效：寿终、退隐、未登场的人已无法交互。
    if (filters.safe && !(c.safe_target && isAlive(c))) return false;
    if (filters.spar && !(c.spar && isAlive(c))) return false;
    if (filters.steal && !(c.steal && isAlive(c))) return false;
    if (filters.merchant && !(c.merchant && isAlive(c))) return false;
    if (filters.attackable && !(c.killable && isAlive(c))) return false;
    if (filters.memoria && !c.memoria) return false;
    if (filters.talent && !(c.talents || []).length) return false;
    if (filters.mortal && !c.mortal) return false;
    if (filters.rel) {
      if (filters.rel === 'met') { if (!c.met) return false; }
      else if ((c.roles || []).indexOf(filters.rel) < 0) return false;
    }
    return true;
  }

  function sortRows(rows) {
    var by = filters.sort;
    // 安全击杀视角：先把"现在就能去杀的"排前面，再按恶名从重到轻
    if (by === 'safe' || (filters.safe && by === 'relevance')) {
      function rank(c) {
        if (c.safe_now) return 0;
        return c.present && !c.gone ? 1 : 2;
      }
      return rows.sort(function (a, b) {
        return rank(a) - rank(b) || a.evil - b.evil ||
          String(a.name).localeCompare(String(b.name), 'zh-CN');
      });
    }
    rows.sort(function (a, b) {
      if (by === 'special') {
        return (b.special_name ? 1 : 0) - (a.special_name ? 1 : 0) ||
          String(a.name).localeCompare(String(b.name), 'zh-CN');
      }
      if (by === 'relevance') return relevance(b) - relevance(a) || a.id - b.id;
      if (by === 'id') return a.id - b.id;
      if (by === 'name') return String(a.name).localeCompare(String(b.name), 'zh-CN');
      if (by === 'evil') return a.evil - b.evil;
      if (by === 'evilDesc') return b.evil - a.evil;
      if (by === 'favor') return b.favor - a.favor;
      if (by === 'layer') return b.layer_order - a.layer_order;
      if (by === 'lifespan') return lifespanRank(a) - lifespanRank(b) || a.id - b.id;
      return a.id - b.id;
    });
    return rows;
  }

  // 剩余寿元升序：凡人按余寿从少到多排前（已超寿元为负自然在最前），修士排最后
  function lifespanRank(c) {
    if (c.mortal && c.remaining_years != null) return c.remaining_years;
    return 1e9;
  }

  // 击杀规则：NPC 卡只存规则下标，文案与数字统一取 meta.alignment_rules
  function killRuleOf(c, meta) {
    var rules = (meta || {}).alignment_rules || [], id = num(c.kill_rule);
    for (var i = 0; i < rules.length; i++) {
      if (num(rules[i].id) === id) return rules[i];
    }
    return null;
  }
  function killEntries(rule) {
    return [['善值', rule.good_delta], ['恶值', rule.evil_delta],
            ['城镇声望', rule.city_rep], ['宗门声望', rule.sect_rep]];
  }
  function signed(v) { return (v > 0 ? '+' : '') + v; }
  // 卡片悬停用的一句话结论：恶名目标连 0 都写出来，让"不扣"看得见
  function killSummary(c, meta) {
    var rule = killRuleOf(c, meta);
    if (!rule) return '';
    return killEntries(rule).map(function (e) {
      return e[0] + ' ' + signed(e[1]);
    }).join(' · ');
  }

  // 天赋品质色：按数值顺序取色板，新增更高品质时自动落到最亮一档，不用改代码。
  var QUALITY_COLORS = ['#8b93a1', '#9fb0c6', '#6fbf8f', '#5b9bd5', '#b07fd0', '#e0a34a', '#e5533d'];
  function qualityColor(q) {
    var n = Number(q) || 0;
    return QUALITY_COLORS[Math.max(0, Math.min(n, QUALITY_COLORS.length - 1))];
  }

  // 卡片上列出全部天赋：只给名称 + 品质颜色，是否值得洗髓交给玩家自己判断。
  function talentStrip(c, meta) {
    var list = (c.talents || []).filter(Boolean);
    if (!list.length) return '';
    var tmeta = (meta && meta.talents) || {};
    var chips = list.map(function (t) {
      var id = (t && typeof t === 'object') ? String(t.id) : '';
      var info = tmeta[id] || {};
      var name = typeof t === 'string' ? t : (t.name || info.name || '未识别天赋');
      var locked = (t && typeof t === 'object') ? t.unlocked === false : false;
      return '<span class="rolebook-talent-chip' + (locked ? ' is-locked' : '') +
        '" style="--qcolor:' + qualityColor(info.quality) + '"' +
        (info.desc ? ' title="' + esc(info.desc) + '"' : '') + '>' + esc(name) + '</span>';
    }).join('');
    return '<div class="rolebook-card-talents"><span class="rolebook-talent-ico">✦</span>' + chips + '</div>';
  }

  function talentListHtml(c, meta) {
    var list = (c.talents || []).filter(Boolean);
    if (!list.length) return '<p class="rolebook-note">这个角色没有配置天赋。</p>';
    var tmeta = (meta && meta.talents) || {};
    return '<div class="rolebook-talents">' + list.map(function (t) {
      var id = (t && typeof t === 'object') ? String(t.id) : '';
      var info = tmeta[id] || {};
      var name = (t && typeof t === 'object') ? (t.name || info.name || '未识别天赋') : t;
      var desc = info.desc || '';
      var locked = (t && typeof t === 'object') ? t.unlocked === false : false;
      return '<div class="rolebook-talent' + (locked ? ' is-locked' : '') +
        '" style="--qcolor:' + qualityColor(info.quality) + '">' +
        '<div class="rolebook-talent-head"><b>' + esc(name) + '</b>' +
        (locked ? '<span class="rolebook-talent-lock">未解锁</span>' : '') + '</div>' +
        (desc ? '<p>' + esc(desc) + '</p>' : '') +
        '</div>';
    }).join('') + '</div>';
  }

  function cardHtml(c, meta, map, pics) {
    var cls = evilClass(c.evil);
    var badges = roleTags(c);
    // 本月特殊互动入口：留影/切磋/说服等，一张卡只有一个。
    var special = c.special_name
      ? '<span class="rolebook-special" title="' + esc(c.special_desc || '本月特殊互动入口') + '">本月 · ' + esc(c.special_name) + '</span>'
      : '';
    if (c.safe_target && isAlive(c)) {
      badges = '<span class="rolebook-safe" title="击杀此人：' + esc(killSummary(c, meta)) +
        '">安全击杀</span>' + badges;
    }
    if (!badges) {
      badges = c.gone
        ? '<span class="rolebook-role-none">' + (c.gone_reason === 'dead' ? '已寿终' : '已退隐') + '</span>'
        : (c.met ? '<span class="rolebook-role-none">有交情 · 暂无关系</span>'
          : (c.present ? '<span class="rolebook-role-none">在世 · 尚未结识</span>'
                       : '<span class="rolebook-role-none">尚未登场</span>'));
    }
    var place = placeLines(c);
    return '<article class="rolebook-card rolebook-card-' + cls + '" data-npc="' + c.id + '" tabindex="0">' +
      '<div class="rolebook-card-top">' + avatarHtml(c, '', map, pics) +
        '<div class="rolebook-card-id">' +
          '<div class="rolebook-card-name">' + esc(c.name) + '</div>' +
          '<div class="rolebook-card-title">' + esc(c.title || c.sect) + '</div>' +
          '<div class="rolebook-card-realm">' + esc(c.realm_short || c.realm) + '</div>' +
        '</div></div>' +
      '<div class="rolebook-card-place' + (place.off ? ' rolebook-card-place-off' : '') + '" title="' + esc(place.sub) + '">' +
        '<span class="rolebook-pin">⌖</span>' +
        '<span class="rolebook-place-box"><span class="rolebook-place-main">' + esc(place.main) + '</span>' +
        '<span class="rolebook-place-sub">' + esc(place.sub) + '</span></span></div>' +
      '<div class="rolebook-card-badges">' + special + lifespanHtml(c) + badges + '</div>' +
      talentStrip(c, meta) +
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
    ['special', '本月可互动'], ['met', '有交情'], ['mortal', '凡人'], ['dao', '道侣'], ['friend', '朋友'], ['housed', '已入住'],
    ['evilneg', '负善恶'], ['safe', '可安全击杀'], ['spar', '可切磋'], ['steal', '可偷窃'],
    ['merchant', '商人'], ['attackable', '可攻击'], ['memoria', '有留影'], ['talent', '固定天赋']
  ];

  function updateCount(rows, total) {
    var info = $('rolebook-count');
    if (!info) return;
    var alive = rows.filter(isAlive).length;
    var met = rows.filter(function (c) { return c.met; }).length;
    var safeNow = rows.filter(function (c) { return c.safe_now; }).length;
    var STATE_LABEL = { alive: '在世', dead: '已寿终', retired: '已退隐', absent: '尚未登场', '': '全部' };
    info.innerHTML = '状态 <b>' + esc(STATE_LABEL[filters.state || '']) + '</b> · 命中 <b>' + rows.length +
      '</b> / ' + total + ' 位 · 其中在世 <b>' + alive + '</b> 位 · 有交情 <b>' + met + '</b> 位' +
      (filters.safe ? ' · 现在可动手 <b>' + safeNow + '</b> 位' : '');
  }

  function renderCards(m, reset) {
    var meta = m.meta || {}, map = m.avatar_map || {}, pics = m.avatars || {};
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
    box.innerHTML = slice.map(function (c) { return cardHtml(c, meta, map, pics); }).join('');
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
      note = '不在当前存档里，可能尚未生成或已退隐；没有实时位置就不猜地点。';
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

  // 击杀后果：用玩家语言写清"杀了他我会怎样"，安全目标连 0 都摆出来
  function killHtml(c, meta) {
    if (!isAlive(c)) {
      return '<p class="rolebook-note">' +
        (c.gone_reason === 'dead' ? '已寿终，无法再攻击。'
          : c.gone_reason === 'retired' ? '已退隐，不在当前世界，无法攻击。'
            : '尚未登场，无法攻击。') + '</p>';
    }
    if (!c.killable) {
      return '<p class="rolebook-note">配置上不可击杀（剧情或寿元保护角色）。' +
        (c.dao ? '对方与你有道侣关系，动手也会直接破坏关系。' : '') + '</p>';
    }
    var rule = killRuleOf(c, meta);
    if (!rule) return '<p class="rolebook-note">没有匹配到击杀规则。</p>';
    // 恶名目标四项全列（0 也要露出来）；其余只列真正变化的项
    var entries = killEntries(rule);
    if (rule.kind !== 'evil') {
      entries = entries.filter(function (e) { return e[1]; });
    }
    var line = entries.map(function (e) {
      var v = e[1];
      var cls = v > 0 ? 'up' : (v < 0 ? 'down' : 'flat');
      return '<span class="rolebook-kill-delta rolebook-kill-' + cls + '">' + esc(e[0]) +
        ' ' + esc(signed(v)) + '</span>';
    }).join('<span class="rolebook-kill-sep">·</span>');

    var tip;
    if (rule.kind === 'evil') {
      tip = '<p class="rolebook-kill-tip">杀他不掉恶值、不扣城镇与宗门声望' +
        (rule.good_delta > 0 ? '，只会补 ' + esc(rule.good_delta) + ' 点善值' : '') +
        '。想动手又不想背恶名，优先挑这类人。</p>';
    } else if (rule.kind === 'good') {
      tip = '<p class="rolebook-kill-tip rolebook-kill-warn">不推荐：杀善良之人会加恶值，' +
        '还会连累当地城镇与其宗门声望。</p>';
    } else {
      tip = '<p class="rolebook-kill-tip">中庸之人也会沾一点恶值，能不杀就不杀。</p>';
    }
    var where = c.safe_target
      ? (c.safe_now
          ? '<p class="rolebook-kill-tip">他现在就在 <b>' + esc(c.loc_name || c.loc) + '</b>，可直接前往。</p>'
          : '<p class="rolebook-kill-tip rolebook-kill-warn">不在当前世界（未生成或已退隐），暂时杀不到。</p>')
      : '';
    var chase = (meta.chase || []).map(function (row) {
      return '<li>恶值 ≤ <b>' + esc(row.threshold) + '</b>：追杀概率 <b>' + esc(row.prob) + '%</b></li>';
    }).join('');
    return '<div class="rolebook-kill">' +
      '<div class="rolebook-kill-line">' + line + '</div>' +
      (rule.desc ? '<p class="rolebook-note rolebook-kill-raw">' + esc(rule.desc) + '</p>' : '') +
      tip + where +
      (chase ? '<div class="rolebook-chase"><span>被追杀的恶值阈值</span><ul>' + chase + '</ul></div>' : '') +
      '</div>';
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

  function specialHtml(c) {
    if (!c.special_name) {
      return '<p class="rolebook-note">本月没有激活的特殊互动入口；这些入口每月刷新一次。</p>';
    }
    return '<div class="rolebook-inline"><span>本月互动</span>' +
      '<span class="rolebook-tag rolebook-tag-green">' + esc(c.special_name) +
      (c.special_tag ? ' · ' + esc(c.special_tag) : '') + '</span></div>' +
      (c.special_desc ? '<p class="rolebook-note">' + esc(c.special_desc) + '</p>' : '') +
      (c.special_type === 1
        ? '<p class="rolebook-note">留影石：完成当前段后入口会清空，要等下一次每月刷新重新抽取，不是立刻出下一段。</p>'
        : '');
  }

  function actsHtml(c) {
    var alive = isAlive(c);
    var items = [
      ['可结道侣', alive && c.dao_capable], ['可切磋', alive && c.spar],
      ['可偷窃', alive && c.steal], ['商人', alive && c.merchant]
    ];
    var note = !alive
      ? '<p class="rolebook-note">已不在当前世界，无法切磋、偷窃、交易或攻击。</p>'
      : (!c.killable ? '<p class="rolebook-note">配置上不可攻击（剧情或寿元保护角色）。</p>' : '');
    return '<div class="rolebook-acts">' + items.map(function (p) {
      return '<span class="rolebook-act' + (p[1] ? ' on' : ' off') + '">' +
        p[0] + ' ' + (p[1] ? '✓' : '×') + '</span>';
    }).join('') + '</div>' + note;
  }

  function openDrawer(c, meta, map, pics) {
    if (!drawer) return;
    var cls = evilClass(c.evil);
    var persona = (meta.personalities || {})[c.personality_id] || {};
    var html = '';
    html += '<div class="rolebook-drawer-head rolebook-head-' + cls + '">' +
      avatarHtml(c, 'rolebook-avatar-lg', map, pics) +
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
      (c.mortal ? kv('寿元', lifespanText(c)) : '') +
      kv('性别', c.sex) + kv('种族', c.race) +
      kv('性格', c.personality || '未知') + kv('五行', (c.element || []).join('、') || '—') +
      '</div>' +
      (persona.desc ? '<p class="rolebook-note">' + esc(persona.desc) + '</p>' : ''));
    html += section('天赋', talentListHtml(c, meta));
    html += section('我和他', relationHtml(c, meta) + favorHtml(c, meta) + housingHtml(c));
    html += section('能做什么', specialHtml(c) + actsHtml(c));
    html += section('善恶与后果',
      '<div class="rolebook-duo">' +
        '<div class="rolebook-duo-item rolebook-duo-' + cls + '"><span>善恶值</span><b>' + esc(c.evil) + '</b>' +
          '<small>' + esc(tierName(meta, 'evil_tiers', c.evil_tier)) + '</small>' + evilBand(c) + '</div>' +
        '<div class="rolebook-duo-item"><span>声望值</span><b>' + esc(c.repute) + '</b>' +
          '<small>' + esc(tierName(meta, 'repute_tiers', c.repute_tier)) + '</small></div>' +
      '</div>' +
      (tierDesc(meta, 'evil_tiers', c.evil_tier) ? '<p class="rolebook-note">' +
        esc(tierDesc(meta, 'evil_tiers', c.evil_tier)) + '</p>' : ''));
    html += section('击杀后果', killHtml(c, meta));
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
    bind('rolebook-region', 'region');
    bind('rolebook-loc', 'loc');
    bind('rolebook-personality', 'personality');
    bind('rolebook-rel', 'rel');
    bind('rolebook-sort', 'sort');
    // 状态与攻击类快捷筛选互斥：看寿终/退隐/未登场时，自动关掉“可攻击/切磋/偷窃/交易”。
    var stateEl = $('rolebook-state');
    if (stateEl) stateEl.onchange = function () {
      filters.state = stateEl.value;
      if (filters.state !== 'alive') {
        ['safe', 'spar', 'steal', 'merchant', 'attackable'].forEach(function (k) { filters[k] = 0; });
      }
      persist(); syncChips(); renderCards(m, true);
    };
    CHIPS.forEach(function (p) {
      var el = $('rolebook-f-' + p[0]);
      if (!el) return;
      el.onclick = function () {
        filters[p[0]] = filters[p[0]] ? 0 : 1;
        // 攻击类筛选只对在世的人有意义，勾选时自动切回“在世”状态。
        if (filters[p[0]] && ['safe', 'spar', 'steal', 'merchant', 'attackable'].indexOf(p[0]) >= 0) {
          filters.state = 'alive';
          var se = $('rolebook-state'); if (se) se.value = 'alive';
        }
        persist(); syncChips(); renderCards(m, true);
      };
    });
    var more = $('rolebook-more');
    if (more) more.onclick = loadMore;
    var reset = $('rolebook-reset');
    if (reset) reset.onclick = function () {
      filters = Object.assign({}, DEFAULTS); persist();
      ['rolebook-evil', 'rolebook-realm', 'rolebook-sect', 'rolebook-personality',
       'rolebook-rel', 'rolebook-sort', 'rolebook-region', 'rolebook-loc'].forEach(function (id) {
        var el = $(id); if (el) el.value = '';
      });
      var st = $('rolebook-state'); if (st) st.value = DEFAULTS.state;
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
    // 地区来自存档实时位置，只列当前存档里真实存在的地点，避免给出空筛选。
    var regions = uniq(npcs.map(function (c) { return c.region; }).filter(Boolean)).sort();
    // 关系类型从存档里出现过的关系派生：游戏新增关系会自动多一个选项。
    var relValues = uniq(npcs.reduce(function (acc, c) { return acc.concat(c.roles || []); }, []));

    view = $('rolebook');
    if (!view) return;
    var live = m.live_stats || {}, counts = (m.player || {}).counts || {}, stats = m.stats || {};
    view.innerHTML = sourceHtml(m) +
      '<div class="rolebook-hero">' +
        '<div class="rolebook-hero-head"><h2>人物图鉴</h2>' +
          '<span>共收录 <b>' + esc(stats.total || 0) + '</b> 位 · 可安全击杀 <b>' +
            esc(live.safe_target_ready || 0) + '</b> 位</span></div>' +
        '<div class="rolebook-hero-figures">' +
          '<div><b>' + esc(live.present || 0) + '</b><span>在世</span></div>' +
          '<div><b>' + esc(live.met || 0) + '</b><span>有交情</span></div>' +
          '<div><b>' + esc(live.dead || 0) + '</b><span>已寿终</span></div>' +
          '<div><b>' + esc(live.retired || 0) + '</b><span>已退隐</span></div>' +
          '<div><b>' + esc(live.absent || 0) + '</b><span>尚未登场</span></div>' +
          '<div><b>' + esc(counts.dao || 0) + '</b><span>道侣</span></div>' +
          '<div><b>' + esc(counts.friend || 0) + '</b><span>朋友</span></div>' +
          '<div><b>' + esc(counts.housed || 0) + '</b><span>已入住</span></div>' +
          '<div><b>' + esc(live.special || 0) + '</b><span>本月可互动</span></div>' +
        '</div>' +
      '</div>' +
      '<div class="rolebook-filters">' +
        '<div class="rolebook-filters-row">' +
          '<label class="rolebook-search"><span>查找 NPC</span>' +
            '<input id="rolebook-q" placeholder="名字 / 称号 / 门派 / 境界 / 地点 / 关系" value="' + esc(filters.q) + '"></label>' +
          '<label class="rolebook-field"><span>状态</span><select id="rolebook-state" ' +
            'title="在世=当前世界可交互；已寿终=寿元耗尽；已退隐=境界突破/剧情清退；尚未登场=存档里还没有这个人">' +
            [['alive', '在世（可交互）'], ['', '全部状态'], ['dead', '已寿终'], ['retired', '已退隐'], ['absent', '尚未登场']]
              .map(function (p) {
                return '<option value="' + p[0] + '"' + (String(filters.state || '') === p[0] ? ' selected' : '') + '>' + p[1] + '</option>';
              }).join('') + '</select></label>' +
          '<label class="rolebook-field"><span>范围</span><select id="rolebook-rel">' +
            [['', '全部 NPC'], ['met', '有交情']]
              .concat(relValues.map(function (r) { return [r, r]; }))
              .map(function (p) {
                return '<option value="' + p[0] + '"' + (filters.rel === p[0] ? ' selected' : '') + '>' + p[1] + '</option>';
              }).join('') + '</select></label>' +
          '<label class="rolebook-field"><span>善恶</span><select id="rolebook-evil">' +
            '<option value="">全部</option><option value="bad"' + (filters.evil === 'bad' ? ' selected' : '') + '>恶名</option>' +
            '<option value="mid"' + (filters.evil === 'mid' ? ' selected' : '') + '>中庸</option>' +
            '<option value="good"' + (filters.evil === 'good' ? ' selected' : '') + '>善念</option></select></label>' +
          '<label class="rolebook-field"><span>境界</span><select id="rolebook-realm">' +
            optList(realms, filters.realm, '全部境界') + '</select></label>' +
          '<label class="rolebook-field"><span>地区</span><select id="rolebook-region">' +
            optList(regions, filters.region, '全部地区') + '</select></label>' +
          '<label class="rolebook-field"><span>地点</span><select id="rolebook-loc">' +
            locOptions(npcs, filters.loc) + '</select></label>' +
          '<label class="rolebook-field"><span>门派</span><select id="rolebook-sect">' +
            optList(sects, filters.sect, '全部门派') + '</select></label>' +
          '<label class="rolebook-field"><span>性格</span><select id="rolebook-personality">' +
            optList(persons, filters.personality, '全部性格') + '</select></label>' +
        '</div>' +
        '<div class="rolebook-filters-row rolebook-filters-row2">' +
          '<label class="rolebook-field"><span>排序</span><select id="rolebook-sort">' +
            [['relevance', '与我相关优先'], ['special', '本月可互动优先'], ['safe', '安全目标优先'], ['layer', '境界高低'], ['lifespan', '剩余寿元'],
             ['favor', '好感优先'], ['evil', '由恶到善'], ['evilDesc', '由善到恶'], ['name', '按名字'], ['id', '按 ID']]
              .map(function (p) {
                return '<option value="' + p[0] + '"' + (filters.sort === p[0] ? ' selected' : '') + '>' + p[1] + '</option>';
              }).join('') + '</select></label>' +
        '</div>' +
        '<div class="rolebook-chips">' +
          '<span class="rolebook-chips-label">快捷筛选</span>' +
          CHIPS.map(function (p) {
            var tip = p[0] === 'safe'
              ? ' title="图鉴口径 ' + esc((m.live_stats || {}).safe_target || 0) +
                ' 位；只列在世、现在就能去杀的 ' +
                esc((m.live_stats || {}).safe_target_ready || 0) + ' 位"'
              : '';
            return '<button type="button" id="rolebook-f-' + p[0] + '" class="rolebook-chip"' + tip + '>' +
              p[1] + (p[0] === 'special' ? ' ' + esc((m.live_stats || {}).special || 0) : '') + '</button>';
          }).join('') +
          '<button type="button" id="rolebook-reset" class="rolebook-chip rolebook-chip-reset">清空</button>' +
        '</div>' +
        '<div class="rolebook-state-hint">在世＝当前可交互；已寿终＝寿元耗尽；已退隐＝境界突破或剧情清退；尚未登场＝存档里还没有这个人。攻击 / 切磋 / 偷窃 / 交易只对在世的人生效。</div>' +
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
      if (c) openDrawer(c, meta, m.avatar_map || {}, m.avatars || {});
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
