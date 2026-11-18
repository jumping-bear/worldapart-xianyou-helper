/* 赌石：璞石库存、开石进度、兑换价格带与收购商参考。仅本模块选择器。 */
(function () {
  'use strict';
  var KEY = 'worldapart.gamble.v2';
  var QLABEL = { 1: '白', 2: '绿', 3: '蓝', 4: '紫', 5: '橙' };

  function fmt(n) {
    n = Number(n || 0);
    return n.toLocaleString('zh-CN');
  }
  function qtag(q) {
    return '<span class="gmb-q q' + (q || 0) + '">' + (QLABEL[q] || '?') + '</span>';
  }
  function tag(text, cls) {
    return '<span class="gmb-tag ' + (cls || '') + '">' + esc(text) + '</span>';
  }
  function bandChips(bands) {
    return (bands || []).map(function (band) {
      return '<span class="gmb-band' + (band.hit ? ' hit' : '') + '">' + esc(band.name || '档位') +
        ' · ' + Number(band.chance || 0).toFixed(1) + '%</span>';
    }).join('');
  }
  function metric(label, value, sub) {
    return '<div class="gmb-metric"><span>' + esc(label) + '</span><b>' + value + '</b>' +
      (sub ? '<small>' + esc(sub) + '</small>' : '') + '</div>';
  }
  function chipRow(label, items, active, attr, prefix) {
    return '<div class="gmb-chips"><span>' + esc(label) + '</span>' +
      items.map(function (item) {
        return '<button type="button" class="gmb-chip' + (String(active) === String(item.value) ? ' on' : '') +
          '" ' + attr + '="' + esc(item.value) + '">' + esc(item.label) +
          (item.count !== undefined ? '<i>' + item.count + '</i>' : '') + '</button>';
      }).join('') + '</div>';
  }

  function initGamble(DATA) {
    var module = (DATA.modules || {}).gamble;
    var host = document.getElementById('gamble');
    if (!module || !host) return;
    var rows = module.rows || {};
    var stones = rows.stones || [];
    var bag = rows.bag || [];
    var summary = rows.summary || {};
    var meta = module;
    var state = Object.assign({ tab: 'mine', q: '', status: 'active', text: '', spoiler: false }, store.get(KEY, {}));
    if (['mine', 'guide', 'bands', 'buyers', 'notes'].indexOf(state.tab) < 0) state.tab = 'mine';
    if (['active', 'done', 'all'].indexOf(state.status) < 0) state.status = 'active';
    var guideQ = Number(state.guideQ || 0);
    if (!guideQ) {
      var first = bag[0] || stones[0] || {};
      guideQ = first.quality || 2;
    }
    state.guideQ = guideQ;

    var shopMap = {};
    (meta.shops || []).forEach(function (shop) {
      (shop.shelves || []).forEach(function (shelf) {
        (shelf.stones || []).forEach(function (stone) {
          if (!shopMap[stone.id]) {
            shopMap[stone.id] = (shop.city || '') + '·' + (shop.title || shop.name || '杂货铺') +
              '（' + ((shelf.condition || {}).text || '常驻') + '）';
          }
        });
      });
    });

    function save() { store.set(KEY, state); }
    function match(item) {
      if (state.q && String(item.quality) !== String(state.q)) return false;
      var text = (state.text || '').trim().toLowerCase();
      if (text && String(item.name || '').toLowerCase().indexOf(text) < 0) return false;
      return true;
    }
    function seenIds(list) {
      var set = {};
      (list || []).forEach(function (row) { set[row.id] = true; });
      return set;
    }
    function adviceFor(stone) {
      return (state.spoiler && stone.exact_advice) ? stone.exact_advice : stone.advice;
    }

    function stoneCard(stone) {
      var advice = adviceFor(stone);
      var stats = stone.stats || {};
      var odds = stone.odds || {};
      var bands = stone.bands || [];
      var seenB = seenIds(stone.seen_blooms);
      var seenC = seenIds(stone.seen_cracks);
      var seenTags = [];
      if (stone.seen_flesh) seenTags.push(tag('玉肉：' + (stone.seen_flesh.short_name || stone.seen_flesh.name || '已见'), 'on'));
      (stone.seen_blooms || []).forEach(function (bloom) {
        seenTags.push(tag(bloom.name + ' +' + Math.round((bloom.ratio_add || 0) * 100) + '%' +
          (bloom.is_legend ? ' · 天成' : ''), bloom.is_legend ? 'legend on' : 'on'));
      });
      (stone.seen_cracks || []).forEach(function (crack) {
        seenTags.push(tag(crack.name + ' -' + Math.round((crack.base_loss || 0) * 100) + '%', 'bad on'));
      });
      if (!seenTags.length) seenTags.push(tag('尚未刮开见肉', 'muted'));

      var hidden = '';
      if (state.spoiler) {
        var hiddenTags = [];
        (stone.hidden_blooms || []).forEach(function (bloom) {
          hiddenTags.push(tag(bloom.name + ' +' + Math.round((bloom.ratio_add || 0) * 100) + '%' +
            (bloom.is_legend ? ' · 天成 ×' + Number(bloom.legend_factor || 1).toFixed(2) : '') +
            (seenB[bloom.id] ? ' · 已见' : ' · 未见'), bloom.is_legend ? 'legend' : ''));
        });
        (stone.hidden_cracks || []).forEach(function (crack) {
          hiddenTags.push(tag(crack.name + ' -' + Math.round((crack.base_loss || 0) * 100) + '%' +
            (seenC[crack.id] ? ' · 已见' : ' · 未见'), 'bad'));
        });
        hidden = '<div class="gmb-hidden"><div class="gmb-hidden-h">透视：存档内已生成内容' +
          (stone.exact_value !== null && stone.exact_value !== undefined
            ? ' · 满解推算 <b>' + fmt(stone.exact_value) + '</b>' : '') + '</div>' +
          '<div class="gmb-tags">' + (hiddenTags.join('') || tag('没有玉纹/裂痕', 'muted')) + '</div></div>';
      } else {
        hidden = '<div class="gmb-hint">未刮开区域默认不展示；开启「透视」可查看存档内已生成的玉纹/裂痕。</div>';
      }

      var offer = stone.buy_offer;
      var offerHtml = '';
      if (offer) {
        var priceText = offer.price ? fmt(offer.price) : '待识别';
        var pctText = offer.percent ? Number(offer.percent).toFixed(0) + '%' : '';
        offerHtml = '<div class="gmb-offer"><b>' + esc(offer.npc_name || '收购商') + '</b>' +
          (offer.npc_title ? '<small>' + esc(offer.npc_title) + '</small>' : '') +
          '<span>报价 ' + priceText + (pctText ? ' · 当前估价的 ' + pctText : '') + '</span>' +
          (offer.range ? '<em>该买家常规区间 ' + esc(offer.range) + '</em>' : '') + '</div>';
      }

      return '<article class="gmb-card" data-q="' + (stone.quality || '') + '" data-status="' +
        (stone.exchanged ? 'done' : 'progress') + '">' +
        '<div class="gmb-card-h"><b class="gmb-name">' + esc(stone.name) + '</b>' + qtag(stone.quality) +
        (stone.exchanged ? '<span class="badge gmb-done">已兑换</span>' : '<span class="badge">进行中</span>') +
        '<span class="gmb-price">当前估价 <b>' + fmt(stone.current_value) + '</b></span></div>' +
        '<div class="gmb-prog"><span class="gmb-bar"><i style="width:' + Number(stone.progress || 0) + '%"></i></span>' +
        '<em>刮开 ' + Number(stone.progress || 0).toFixed(1) + '%</em></div>' +
        '<div class="gmb-metrics">' +
        metric('满解常见', fmt(odds.p50 || 0), '较差 ' + fmt(odds.p10 || 0) + ' · 较好 ' + fmt(odds.p90 || 0)) +
        metric('下一档', stone.next_band ? stone.next_band.name : '已够最高档',
          stone.next_band ? '门槛 ' + fmt(stone.next_band.min_value) + ' · 命中率 ' +
            Number(stone.next_band.chance || 0).toFixed(1) + '%' : '') +
        metric('风格', esc(stats.style || '—'), (stats.risk || '') + (stats.spread ? ' · 波动 ' + stats.spread + 'x' : '')) +
        '</div>' +
        '<div class="gmb-tags">' + seenTags.join('') + '</div>' +
        '<div class="gmb-odds">' + bandChips(bands) + '</div>' +
        '<div class="gmb-advice ' + (advice && advice.tone || 'info') + '">' +
        esc((advice && advice.text) || '') + '</div>' +
        offerHtml + hidden +
        (stone.exchanged && stone.exchanged_name ? '<div class="gmb-hint">已兑换：' + esc(stone.exchanged_name) + '</div>' : '') +
        '</article>';
    }

    function bagCard(item) {
      var stats = item.stats || {};
      var bands = (stats.bands || []).map(function (band) {
        return { name: band.name, min_value: band.min_value, chance: band.chance, hit: false };
      });
      return '<article class="gmb-card" data-q="' + (item.quality || '') + '" data-status="open">' +
        '<div class="gmb-card-h"><b class="gmb-name">' + esc(item.name) + '</b>' + qtag(item.quality) +
        (item.exclusive ? '<span class="badge gmb-done">专属</span>' : '') +
        '<span class="badge">未开 ×' + item.untouched + '</span>' +
        '<span class="gmb-price">参考价 <b>' + fmt(item.base_price) + '</b></span></div>' +
        '<div class="gmb-metrics">' +
        metric('满解估值', fmt(stats.p10 || 0) + ' ~ ' + fmt(stats.p90 || 0), '较差 ~ 较好 · 常见 ' + fmt(stats.p50 || 0)) +
        metric('风格', esc(stats.style || '—'), (stats.risk || '') + (stats.spread ? ' · 波动 ' + stats.spread + 'x' : '')) +
        metric('最低档 / 最高档', Number(stats.low_chance || 0).toFixed(1) + '% / ' + Number(stats.top_chance || 0).toFixed(1) + '%', '') +
        '</div>' +
        '<div class="gmb-odds">' + bandChips(bands) + '</div>' +
        '<div class="gmb-hint">' + (item.in_progress ? '另有 ' + item.in_progress + ' 块已开，见进行中列表。' : '') +
        (shopMap[item.item_id] ? '货架：' + esc(shopMap[item.item_id]) : '非杂货铺常规货源') + '</div>' +
        '</article>';
    }

    function renderList() {
      var list = document.getElementById('gmb-list');
      if (!list) return;
      var html = '';
      if (state.status === 'active' || state.status === 'all') {
        var bagRows = bag.filter(match);
        if (bagRows.length) {
          html += '<div class="gmb-group">未开璞石<span>' + bagRows.reduce(function (sum, row) { return sum + row.untouched; }, 0) + ' 块</span></div>';
          html += bagRows.map(bagCard).join('');
        }
      }
      if (state.status === 'active' || state.status === 'all') {
        var progressRows = stones.filter(function (stone) { return !stone.exchanged && match(stone); });
        if (progressRows.length) {
          html += '<div class="gmb-group">进行中<span>' + progressRows.length + ' 块</span></div>';
          html += progressRows.map(stoneCard).join('');
        }
      }
      if (state.status === 'done' || state.status === 'all') {
        var doneRows = stones.filter(function (stone) { return stone.exchanged && match(stone); });
        if (doneRows.length) {
          html += '<div class="gmb-group">已兑换<span>' + doneRows.length + ' 块</span></div>';
          html += doneRows.map(stoneCard).join('');
        }
      }
      list.innerHTML = html || '<div class="empty">没有符合条件的璞石。</div>';
    }

    function renderAdvice() {
      var box = document.getElementById('gmb-advice');
      if (!box) return;
      var tips = stones.filter(function (stone) {
        return !stone.exchanged && adviceFor(stone);
      }).sort(function (a, b) {
        return (adviceFor(b).priority || 0) - (adviceFor(a).priority || 0) ||
          (b.current_value || 0) - (a.current_value || 0);
      }).slice(0, 3);
      var html = tips.map(function (stone) {
        var advice = adviceFor(stone);
        return '<div class="gmb-tip ' + (advice.tone || 'info') + '"><b>' + esc(stone.name) +
          '</b><span>' + esc(advice.text) + '</span></div>';
      }).join('');
      if (!html) {
        if (bag.length) {
          html = '<div class="gmb-tip info"><b>背包还有璞石</b><span>先开一块见肉；同品质同价时，想稳选叩道/凝魄/藏锋，想冲档选乘云/玄符/证真。</span></div>';
        } else {
          html = '<div class="gmb-tip info"><b>暂无璞石</b><span>去各地杂货铺购买，或关注副本/奇遇奖励；声望越高，货架越多。</span></div>';
        }
      }
      box.innerHTML = html;
    }

    function renderGuide() {
      var box = document.getElementById('gmb-guide');
      var chips = document.getElementById('gmb-guide-chips');
      if (!box || !chips) return;
      var qualities = (meta.qualities || []).map(function (name, index) {
        return { value: index + 1, label: name, count: (meta.templates || []).filter(function (t) {
          return !t.exclusive && t.quality === index + 1;
        }).length };
      }).filter(function (item) { return item.count; });
      chips.innerHTML = qualities.map(function (item) {
        return '<button type="button" class="gmb-chip gmb-qchip q' + item.value + (Number(state.guideQ) === item.value ? ' on' : '') +
          '" data-guide-q="' + item.value + '">' + esc(item.label) + '<i>' + item.count + '</i></button>';
      }).join('');
      var rows = (meta.templates || []).filter(function (t) {
        return !t.exclusive && t.quality === Number(state.guideQ);
      })
        .sort(function (a, b) {
          var sa = a.stats || {}, sb = b.stats || {};
          return (sb.top_chance || 0) - (sa.top_chance || 0) || (sb.p50 || 0) - (sa.p50 || 0);
        });
      if (!rows.length) {
        box.innerHTML = '<div class="empty">该品质暂无配置。</div>';
        return;
      }
      var byTop = rows.slice().sort(function (a, b) {
        return (b.stats.top_chance || 0) - (a.stats.top_chance || 0);
      }).slice(0, 3);
      var bySafe = rows.slice().sort(function (a, b) {
        return (b.stats.p10 || 0) - (a.stats.p10 || 0);
      }).slice(0, 3);
      var reco = '<div class="gmb-reco"><div><b>想冲最高档</b>' +
        byTop.map(function (t) {
          return '<span>' + esc(t.variant || t.name) + '<i>' + Number(t.stats.top_chance || 0).toFixed(1) + '%</i></span>';
        }).join('') + '</div><div><b>求稳</b>' +
        bySafe.map(function (t) {
          return '<span>' + esc(t.variant || t.name) + '<i>较差 ' + fmt(t.stats.p10 || 0) + '</i></span>';
        }).join('') + '</div></div>';
      box.innerHTML = reco + '<div class="gmb-table-wrap"><table class="gmb-table"><thead><tr>' +
        '<th>玉料</th><th>风格</th><th>满解估值（较差~较好）</th><th>最低档</th><th>最高档</th><th>参考价</th>' +
        '</tr></thead><tbody>' + rows.map(function (t) {
          var stats = t.stats || {};
          var bands = stats.bands || [];
          var top = bands[bands.length - 1] || {};
          return '<tr class="' + (stats.style === '冲档' ? 'hot' : '') + '">' +
            '<td><b>' + esc(t.variant || t.name) + '</b><small>' + esc(t.family || '') + '</small></td>' +
            '<td>' + esc(stats.style || '—') + '<small>' + esc(stats.risk || '') + '</small></td>' +
            '<td>' + fmt(stats.p10 || 0) + ' ~ ' + fmt(stats.p90 || 0) + '<small>常见 ' + fmt(stats.p50 || 0) + '</small></td>' +
            '<td>' + Number(stats.low_chance || 0).toFixed(1) + '%' +
            '<small>' + (bands[0] ? fmt(bands[0].min_value) : '') + '</small></td>' +
            '<td class="gmb-hot">' + Number(stats.top_chance || 0).toFixed(1) + '%' +
            '<small>' + (top.min_value ? fmt(top.min_value) : '') + '</small></td>' +
            '<td>' + fmt(t.base_price || 0) + '</td>' +
            '</tr>';
        }).join('') + '</tbody></table></div>' +
        '<div class="gmb-hint">同品质同价，差异只在裂纹与玉纹权重；「冲档」表示最高价格带命中率更高，但低估值区间也更低。' +
        '<br>“较差 / 常见 / 较好”对应 10% / 50% / 90% 分位：约一成结果比“较差”更低，不是保底。</div>';
    }

    function renderBands() {
      var box = document.getElementById('gmb-bands');
      if (!box) return;
      var bands = meta.bands || [];
      var html = '';
      [1, 2, 3, 4, 5].forEach(function (quality) {
        var rows = bands.filter(function (band) {
          return !band.exclusive_item_id && (band.qualities || []).indexOf(quality) >= 0;
        });
        if (!rows.length) return;
        html += '<div class="gmb-group gmb-qgroup q' + quality + '">' + QLABEL[quality] + '色璞石<span>3 档</span></div>' +
          '<div class="gmb-table-wrap"><table class="gmb-table"><thead><tr>' +
          '<th>价格带</th><th>最低估值</th><th>可换器胚</th></tr></thead><tbody>' +
          rows.map(function (band) {
            return '<tr><td><b>' + esc(band.name) + '</b></td><td>' + fmt(band.min_value) + '</td>' +
              '<td class="gmb-embryos">' + (band.embryos || []).map(function (embryo) {
                return '<span class="gmb-tag">' + esc(embryo.name) +
                  '<small>' + esc((embryo.realm_name || '') + ' ' + (embryo.slot_name || '')) + '</small></span>';
              }).join('') + '</td></tr>';
          }).join('') + '</tbody></table></div>';
      });
      var exclusive = bands.filter(function (band) { return band.exclusive_item_id; });
      if (exclusive.length) {
        html += '<div class="gmb-group">专属璞石<span>' + exclusive.length + ' 条</span></div>';
        html += exclusive.map(function (band) {
          var item = (meta.items || {})[String(band.exclusive_item_id)] || {};
          return '<div class="gmb-exclusive"><b>' + esc(item.name || ('璞石 ' + band.exclusive_item_id)) +
            '</b><span>门槛 ' + fmt(band.min_value) + '</span><em>' +
            (band.embryos || []).map(function (embryo) { return esc(embryo.name); }).join('、') + '</em></div>';
        }).join('');
      }
      box.innerHTML = html || '<div class="empty">暂无兑换配置。</div>';
    }

    function renderBuyers() {
      var box = document.getElementById('gmb-buyers');
      if (!box) return;
      var constants = meta.constants || {};
      var rows = meta.buyers || [];
      var best = rows.filter(function (buyer) { return buyer.offer_min >= 100; });
      var worst = rows.filter(function (buyer) { return buyer.offer_max <= 90; });
      var reco = '<div class="gmb-reco"><div><b>优先卖</b>' +
        best.map(function (buyer) {
          return '<span>' + esc(buyer.name) + '<i>' + buyer.offer_min + '%~' + buyer.offer_max + '%</i></span>';
        }).join('') + '</div><div><b>尽量拒绝</b>' +
        worst.map(function (buyer) {
          return '<span>' + esc(buyer.name) + '<i>' + buyer.offer_min + '%~' + buyer.offer_max + '%</i></span>';
        }).join('') + '</div></div>';
      box.innerHTML = reco + '<div class="gmb-table-wrap"><table class="gmb-table"><thead><tr>' +
        '<th>收购商</th><th>身份</th><th>报价区间</th><th>建议</th><th>当前状态</th>' +
        '</tr></thead><tbody>' + rows.map(function (buyer) {
          var tone = buyer.offer_min >= 100 ? 'good' : (buyer.offer_max <= 90 ? 'bad' : 'normal');
          var advice = buyer.offer_min >= 100 ? '优先卖给他' : (buyer.offer_max <= 90 ? '压价，尽量拒绝' : '正常，可谈');
          return '<tr><td><b>' + esc(buyer.name) + '</b></td><td>' + esc(buyer.title || '') + '</td>' +
            '<td class="gmb-' + tone + '">' + buyer.offer_min + '%~' + buyer.offer_max + '%</td>' +
            '<td>' + advice + '</td><td>' + (buyer.cooldown_until ? '冷却至第 ' + buyer.cooldown_until + ' 轮' : '可来访') + '</td></tr>';
        }).join('') + '</tbody></table></div>' +
        '<div class="gmb-hint">报价按「当前估价」的百分比；刮开进度达到玉纹/裂痕阈值时可能触发来访，拒绝后该买家冷却 ' +
        Number(constants.npc_cooldown_turns || 2) + ' 轮。100%~120% 的买家优先，60%~90% 的买家只在急需回血时考虑。</div>';
    }

    var qualityChips = [{ value: '', label: '全部' }].concat([1, 2, 3, 4, 5].map(function (q) {
      var count = bag.filter(function (row) { return row.quality === q; }).reduce(function (sum, row) { return sum + row.untouched; }, 0) +
        stones.filter(function (stone) { return stone.quality === q && !stone.exchanged; }).length;
      return { value: q, label: QLABEL[q], count: count };
    }).filter(function (item) { return item.count; }));
    var statusChips = [
      { value: 'active', label: '待处理', count: summary.untouched + summary.in_progress },
      { value: 'done', label: '已兑换', count: summary.exchanged },
      { value: 'all', label: '全部', count: summary.bag_total + summary.exchanged }
    ];
    var tabs = [
      { key: 'mine', label: '我的璞石', count: summary.untouched + summary.in_progress },
      { key: 'guide', label: '选石指南' },
      { key: 'bands', label: '兑换图鉴' },
      { key: 'buyers', label: '收购商', count: (meta.buyers || []).length },
      { key: 'notes', label: '说明' }
    ];

    function setTab(key, scroll) {
      state.tab = key;
      save();
      Array.prototype.forEach.call(document.querySelectorAll('#gmb-subnav [data-tab]'), function (node) {
        node.classList.toggle('on', node.getAttribute('data-tab') === key);
      });
      Array.prototype.forEach.call(host.querySelectorAll('[data-panel]'), function (node) {
        node.hidden = node.getAttribute('data-panel') !== key;
      });
      if (scroll) {
        var nav = document.getElementById('gmb-subnav');
        if (nav) nav.scrollIntoView({ block: 'start', behavior: 'smooth' });
      }
    }

    host.innerHTML = sourceHtml(module) +
      '<div class="gmb-cards">' +
      '<div class="card"><div class="k">背包璞石</div><div class="v">' + fmt(summary.bag_total) + '<small>未开 ' + fmt(summary.untouched) + '</small></div></div>' +
      '<div class="card"><div class="k">进行中</div><div class="v">' + fmt(summary.in_progress) + '<small>待刮开/待兑换</small></div></div>' +
      '<div class="card"><div class="k">已兑换</div><div class="v">' + fmt(summary.exchanged) + '<small>已换成器胚</small></div></div>' +
      '<div class="card"><div class="k">最高估价</div><div class="v">' + fmt(summary.best_value) + '<small>当前可见估价</small></div></div>' +
      '</div>' +
      '<div class="gmb-subnav" id="gmb-subnav">' + tabs.map(function (tab) {
        return '<button type="button" class="gmb-tab' + (state.tab === tab.key ? ' on' : '') +
          '" data-tab="' + tab.key + '">' + esc(tab.label) +
          (tab.count !== undefined ? '<i>' + tab.count + '</i>' : '') + '</button>';
      }).join('') + '</div>' +
      '<div class="gmb-panel" data-panel="mine">' +
      '<div class="gmb-advice-box"><div class="gmb-sec-h">下一步建议</div><div id="gmb-advice"></div></div>' +
      '<div class="gmb-toolbar"><input id="gmb-search" placeholder="搜玉料名 / 词缀" value="' + esc(state.text) + '"></div>' +
      '<div class="gmb-chips" id="gmb-qchips"><span class="chip-label">璞石品阶(白~橙)</span>' + qualityChips.map(function (item) {
        return '<button type="button" class="gmb-chip' +
          (String(state.q) === String(item.value) ? ' on' : '') +
          (item.value ? ' gmb-qchip q' + item.value : '') +
          '" data-q="' + esc(item.value) + '">' + esc(item.label) +
          (item.count !== undefined ? '<i>' + item.count + '</i>' : '') + '</button>';
      }).join('') + '</div>' +
      '<div class="gmb-chips" id="gmb-statuschips">' + statusChips.map(function (item) {
        return '<button type="button" class="gmb-chip' + (state.status === item.value ? ' on' : '') +
          '" data-status="' + item.value + '">' + esc(item.label) +
          '<i>' + item.count + '</i></button>';
      }).join('') + '</div>' +
      '<div id="gmb-list"></div>' +
      '<details class="gmb-advanced"><summary>高级：复盘透视（会剧透）</summary>' +
      '<label class="gmb-switch"><input type="checkbox" id="gmb-spoiler"' +
      (state.spoiler ? ' checked' : '') + '> 显示未刮开的玉纹/裂痕与精确满解估值</label>' +
      '<div class="gmb-hint">读取的是存档里已经生成、但游戏尚未刮开的数据；只适合开完/卖完后复盘，默认关闭。</div>' +
      '</details></div>' +
      '<div class="gmb-panel" data-panel="guide" hidden><section class="gmb-sec">' +
      '<div class="gmb-sec-h">选石指南</div>' +
      '<div class="gmb-hint">同一品质同价，差异只在裂纹与玉纹权重；先看推荐，再查表。</div>' +
      '<div class="gmb-chips" id="gmb-guide-chips"></div><div id="gmb-guide"></div></section></div>' +
      '<div class="gmb-panel" data-panel="bands" hidden><section class="gmb-sec">' +
      '<div class="gmb-sec-h">兑换图鉴</div>' +
      '<div class="gmb-hint">完全解开后才能兑换；选低档时余值折灵石，不会凭空消失。价格带按满解估价判定。</div>' +
      '<div id="gmb-bands"></div></section></div>' +
      '<div class="gmb-panel" data-panel="buyers" hidden><section class="gmb-sec">' +
      '<div class="gmb-sec-h">收购商</div><div id="gmb-buyers"></div></section></div>' +
      '<div class="gmb-panel" data-panel="notes" hidden><section class="gmb-sec">' +
      '<div class="gmb-sec-h">推算说明与数据来源</div>' +
      '<p class="gmb-note-p">满解推算：基础估值 × 80% 起算 ×（1 + 玉纹加成）× 裂痕折损 × 天成倍率；未计入天赋、活动或版本新增加成，实际以游戏内估价为准。</p>' +
      '<p class="gmb-note-p">未开石的区间与档位概率按同品质 10 种玉料的配置权重模拟，代表这一类玉料的长期分布，不代表单块结果。进行中的璞石按“已看见的玉肉/玉纹/裂痕 + 同类权重”重新推算。</p>' +
      '<p class="gmb-note-p">透视读取的是存档里已经生成、但游戏尚未刮开的数据，属于剧透功能；默认关闭，放在「高级」里避免误触。</p>' +
      '<p class="gmb-note-p">数据来源：赌石璞石模板、玉肉、裂痕、玉纹、兑换价格带、收购商、杂货铺货架与城镇声望配置表；存档来源：playerModel.gamble_stone 与背包。</p>' +
      '</section></div>';

    document.getElementById('gmb-search').addEventListener('input', function (event) {
      state.text = event.target.value;
      save();
      renderList();
    });
    host.addEventListener('click', function (event) {
      var tab = event.target.closest('#gmb-subnav [data-tab]');
      if (tab) {
        setTab(tab.getAttribute('data-tab'), true);
        return;
      }
      var q = event.target.closest('#gmb-qchips [data-q]');
      if (q) {
        state.q = q.getAttribute('data-q');
        save();
        document.querySelectorAll('#gmb-qchips [data-q]').forEach(function (node) {
          node.classList.toggle('on', node.getAttribute('data-q') === state.q);
        });
        renderList();
        return;
      }
      var status = event.target.closest('#gmb-statuschips [data-status]');
      if (status) {
        state.status = status.getAttribute('data-status');
        save();
        document.querySelectorAll('#gmb-statuschips [data-status]').forEach(function (node) {
          node.classList.toggle('on', node.getAttribute('data-status') === state.status);
        });
        renderList();
        return;
      }
      var guide = event.target.closest('[data-guide-q]');
      if (guide) {
        state.guideQ = Number(guide.getAttribute('data-guide-q'));
        save();
        renderGuide();
      }
    });
    document.getElementById('gmb-spoiler').addEventListener('change', function (event) {
      state.spoiler = !!event.target.checked;
      save();
      renderAdvice();
      renderList();
    });

    setTab(state.tab, false);
    renderAdvice();
    renderList();
    renderGuide();
    renderBands();
    renderBuyers();
  }

  window.PROGRESS_VIEWS = window.PROGRESS_VIEWS || {};
  window.PROGRESS_VIEWS.gamble = initGamble;
})();
