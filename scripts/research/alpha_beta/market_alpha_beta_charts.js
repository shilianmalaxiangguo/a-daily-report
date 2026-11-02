(() => {
  const boot = () => {
    const root = document.getElementById('daily-alphabeta');
    if (!root || root.dataset.abReady || !window.echarts) return;
    const data = JSON.parse(document.getElementById('market-alpha-beta-data').textContent);
    const red = '#E73922', green = '#07C160', muted = '#7a7882', rule = '#e6e3e9';
    const tones = {alpha_up: '#5b45b5', resilient: '#a497e3', beta: '#2364aa', lagging: '#dcae6e',
      alpha_down: '#9a5a14', none: '#c4c1cc'};
    const byId = id => document.getElementById(id);
    const charts = {};
    const chart = id => charts[id] || (charts[id] = window.echarts.init(byId(id)));
    const near = v => typeof v === 'number' && Math.abs(v) < 0.005;
    const sign = (v, unit = '%', digits = 2) => v == null ? '事实不足' :
      ((near(v) ? 0 : v) > 0 ? '+' : '') + (near(v) ? 0 : v).toFixed(digits) + unit;
    const tone = v => v == null || near(v) ? 'ab-flat' : v > 0 ? 'ab-up' : 'ab-down';
    const color = v => v == null || near(v) ? muted : v > 0 ? red : green;
    const el = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
    const state = {window: root.dataset.abWindow, list: root.dataset.abList, code: null};
    const win = () => data.windows[state.window];
    const findRow = code => {
      for (const key of Object.keys(win().lists)) {
        const row = win().lists[key].find(r => r.code === code);
        if (row) return row;
      }
      return null;
    };

    const regime = () => {
      const s = data.series, dates = s.map(p => p.date);
      const expected = s.map(p => p.complete ? +(p.complete * 0.025).toFixed(1) : null);
      chart('ab-regime-chart').setOption({
        animation: false,
        tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'}, formatter: items => {
          const p = s[items[0].dataIndex];
          return [`<b>${p.date}</b>`,
            `${data.benchmark.name}：<b style="color:${color(p.market_pct)}">${sign(p.market_pct)}</b>`,
            `个股中位数：<b style="color:${color(p.median_pct)}">${sign(p.median_pct)}</b>`,
            `与大盘同向：${p.same_share == null ? '事实不足' : p.same_share.toFixed(0) + '%'}`,
            `20日共振度：${p.sync == null ? '事实不足' : p.sync.toFixed(2)}`,
            `独立上涨${p.alpha_up}只、抗跌${p.resilient}只（随机约${(p.complete * 0.025).toFixed(0)}只）`].join('<br>');
        }},
        legend: {top: 0, data: [data.benchmark.name + '日涨跌', '同向比例', '20日共振度', '独立上涨', '抗跌', '随机预期']},
        axisPointer: {link: [{xAxisIndex: 'all'}]},
        grid: [{left: 56, right: 56, top: 40, height: '34%'}, {left: 56, right: 56, top: '56%', bottom: 36}],
        xAxis: [{type: 'category', data: dates, gridIndex: 0, axisLabel: {show: false}, axisLine: {lineStyle: {color: rule}}},
                {type: 'category', data: dates, gridIndex: 1, axisLabel: {color: muted, formatter: v => v.slice(5)},
                 axisLine: {lineStyle: {color: rule}}}],
        yAxis: [{type: 'value', gridIndex: 0, name: '涨跌 %', nameTextStyle: {color: muted}, axisLabel: {color: muted},
                 splitLine: {lineStyle: {color: rule}}},
                {type: 'value', gridIndex: 0, name: '同向 %', min: 0, max: 100, nameTextStyle: {color: muted},
                 axisLabel: {color: muted}, splitLine: {show: false}},
                {type: 'value', gridIndex: 1, name: '共振度', min: 0, max: v => Math.max(0.6, Math.ceil(v.max * 10) / 10),
                 nameTextStyle: {color: muted}, axisLabel: {color: muted}, splitLine: {lineStyle: {color: rule}}},
                {type: 'value', gridIndex: 1, name: '只数', nameTextStyle: {color: muted}, axisLabel: {color: muted},
                 splitLine: {show: false}}],
        series: [
          {name: data.benchmark.name + '日涨跌', type: 'bar', xAxisIndex: 0, yAxisIndex: 0, barMaxWidth: 14,
           itemStyle: {color: '#E73922'},
           data: s.map(p => ({value: p.market_pct, itemStyle: {color: color(p.market_pct)}}))},
          {name: '同向比例', type: 'line', xAxisIndex: 0, yAxisIndex: 1, data: s.map(p => p.same_share),
           connectNulls: false, symbolSize: 4, lineStyle: {color: '#2364aa', width: 2}, itemStyle: {color: '#2364aa'},
           markLine: {silent: true, symbol: 'none', lineStyle: {type: 'dashed', color: muted},
                      label: {formatter: '50%', position: 'insideEndTop', color: muted}, data: [{yAxis: 50}]}},
          {name: '20日共振度', type: 'line', xAxisIndex: 1, yAxisIndex: 2, data: s.map(p => p.sync), connectNulls: false,
           symbolSize: 4, lineStyle: {color: '#5b45b5', width: 2.5}, itemStyle: {color: '#5b45b5'}},
          {name: '独立上涨', type: 'bar', stack: 'own', xAxisIndex: 1, yAxisIndex: 3, barMaxWidth: 14, data: s.map(p => p.alpha_up),
           itemStyle: {color: '#a99be6'}},
          {name: '抗跌', type: 'bar', stack: 'own', xAxisIndex: 1, yAxisIndex: 3, barMaxWidth: 14, data: s.map(p => p.resilient),
           itemStyle: {color: '#ddd7f3'}},
          {name: '随机预期', type: 'line', xAxisIndex: 1, yAxisIndex: 3, data: expected, symbol: 'none',
           lineStyle: {color: muted, type: 'dashed', width: 1.5}, itemStyle: {color: muted}},
        ],
      }, true);
    };

    const path = () => {
      const row = state.code && findRow(state.code);
      const summary = byId('ab-path-summary');
      const target = chart('ab-path-chart');
      if (!row || !data.paths[row.code]) {
        summary.textContent = '点选表中的股票查看走势。';
        target.clear();
        return;
      }
      const w = win(), start = data.dates.indexOf(w.start_date), end = data.dates.indexOf(w.end_date) + 1;
      const returns = data.paths[row.code].slice(start, end), market = data.market.slice(start, end);
      const dates = [start > 0 ? data.dates[start - 1] : '起点', ...data.dates.slice(start, end)];
      const cumulate = values => { let level = 1; return [0, ...values.map(v => v == null || level == null ? (level = null) : +(((level *= 1 + v / 100) - 1) * 100).toFixed(3))]; };
      const actual = cumulate(returns), follow = cumulate(market.map(v => v == null ? null : row.beta * v)), bench = cumulate(market);
      summary.replaceChildren();
      summary.append(el('strong', `${row.name}（${row.code}）`), el('span',
        `：${w.window}日涨跌${sign(row.total_pct)}；大盘贡献${sign(row.market_pp, '个百分点')}，独立收益${sign(row.own_pp, '个百分点')}；`
        + `贝塔${row.beta.toFixed(2)}，关联度${row.r2.toFixed(2)}；大盘下跌的${row.down_days}天平均${sign(row.down_mean_pct)}。`
        + `类型：${data.labels[row.label]}。`));
      target.setOption({
        animation: false,
        tooltip: {trigger: 'axis', valueFormatter: v => sign(v)},
        legend: {top: 0, data: ['实际走势', '只跟大盘', data.benchmark.name]},
        grid: {left: 52, right: 20, top: 36, bottom: 32},
        xAxis: {type: 'category', data: dates, boundaryGap: false, axisLabel: {color: muted, formatter: v => v.slice(5)},
                axisLine: {lineStyle: {color: rule}}},
        yAxis: {type: 'value', name: '累计涨跌 %', nameTextStyle: {color: muted}, axisLabel: {color: muted},
                splitLine: {lineStyle: {color: rule}}},
        series: [
          {name: '实际走势', type: 'line', data: actual, symbolSize: 4, lineStyle: {width: 2.5, color: '#5b45b5'}, itemStyle: {color: '#5b45b5'},
           areaStyle: {color: 'rgba(91,69,181,.06)'}},
          {name: '只跟大盘', type: 'line', data: follow, symbolSize: 3, lineStyle: {width: 2, type: 'dashed', color: '#2364aa'}, itemStyle: {color: '#2364aa'}},
          {name: data.benchmark.name, type: 'line', data: bench, symbol: 'none', lineStyle: {width: 1.5, color: '#9a98a3'}, itemStyle: {color: '#9a98a3'}},
        ],
      }, true);
    };

    const scatter = () => {
      const w = win(), stocks = data.scatter_stocks;
      const threshold = (w.t_critical ** 2) / (w.window - 2 + w.t_critical ** 2);
      const series = data.label_keys.map((key, i) => ({
        name: data.labels[key], type: 'scatter', symbolSize: key === 'none' ? 4 : key === 'alpha_up' ? 7 : 5, large: false,
        z: key === 'alpha_up' ? 5 : key === 'none' ? 1 : 3,
        itemStyle: {color: tones[key], opacity: key === 'none' ? 0.45 : 0.85},
        data: w.scatter.filter(p => p[2] === i).map(p => ({value: [p[0], p[1]], idx: p[3]})),
        ...(i === 0 ? {markLine: {silent: true, symbol: 'none', lineStyle: {type: 'dashed', color: muted}, label: {show: false},
          data: [{xAxis: +threshold.toFixed(3)}, {yAxis: 0}]}} : {}),
      }));
      chart('ab-scatter-chart').setOption({
        animation: false,
        tooltip: {trigger: 'item', formatter: p => {
          const i = p.data.idx;
          return `<b>${stocks.names[i]}</b> ${stocks.codes[i]} · ${stocks.industries[i]}<br>关联度 ${p.value[0].toFixed(2)} · 独立收益 `
            + `<b style="color:${color(p.value[1])}">${sign(p.value[1], '个百分点')}</b><br>${p.seriesName}`;
        }},
        legend: {top: 0},
        grid: {left: 60, right: 24, top: 56, bottom: 44},
        xAxis: {type: 'value', min: 0, max: 1, name: '与大盘关联度（R²）', nameLocation: 'middle', nameGap: 28,
                nameTextStyle: {color: muted}, axisLabel: {color: muted}, splitLine: {lineStyle: {color: rule}}},
        yAxis: {type: 'value', name: `${w.window}日独立收益（个百分点）`, nameTextStyle: {color: muted, align: 'left'},
                axisLabel: {color: muted}, splitLine: {lineStyle: {color: rule}}},
        series,
      }, true);
    };

    const stockTable = () => {
      const rows = win().lists[state.list] || [];
      const body = byId('ab-stock-table').querySelector('tbody');
      body.replaceChildren();
      if (!rows.length) {
        const tr = el('tr'), td = el('td', '这一类本窗口没有股票。'); td.colSpan = 9; tr.append(td); body.append(tr);
      }
      for (const row of rows) {
        const tr = el('tr'); tr.dataset.abCode = row.code;
        const pick = el('button', null, 'ab-pick'); pick.type = 'button'; pick.dataset.abCode = row.code;
        pick.setAttribute('aria-label', row.name + '，查看走势');
        pick.append(el('strong', row.name), el('small', row.code));
        const first = el('td'); first.append(pick); tr.append(first, el('td', row.industry));
        for (const [v, unit] of [[row.total_pct, '%'], [row.market_pp, ''], [row.own_pp, ''], [row.own5_pp, '']]) tr.append(el('td', sign(v, unit), tone(v)));
        tr.append(el('td', row.r2.toFixed(2)), el('td', row.beta.toFixed(2)),
          el('td', sign(row.down_mean_pct) + `（${row.down_days}日）`, tone(row.down_mean_pct)));
        body.append(tr);
      }
    };

    const conceptTables = () => {
      const block = byId('ab-concepts');
      if (!block || !data.concepts) return;
      const c = data.concepts[state.window];
      const note = byId('ab-concept-summary');
      if (note) note.textContent = c ? `同花顺概念指数用同一方法；${c.start_date}至${c.end_date}，完整概念${c.complete}个：`
        + `独立上涨${c.counts.alpha_up}个、抗跌${c.counts.resilient}个、跟随大盘${c.counts.beta}个、`
        + `跟涨乏力${c.counts.lagging}个、独立走弱${c.counts.alpha_down}个。概念成分互相重叠，不相加。` : '该窗口概念资料不足。';
      root.querySelectorAll('[data-ab-concepts]').forEach(card => {
        const body = card.querySelector('tbody');
        if (!body) return;
        body.replaceChildren();
        const withType = card.dataset.abConcepts !== 'beta';
        const rows = c ? c[card.dataset.abConcepts] || [] : [];
        if (!rows.length) {
          const tr = el('tr'), td = el('td', c ? '这一类本窗口没有概念。' : '该窗口概念资料不足。'); td.colSpan = withType ? 6 : 5; tr.append(td); body.append(tr);
        }
        for (const row of rows) {
          const tr = el('tr'), name = el('td'); name.append(el('strong', row.name));
          if (row.tracked) name.append(el('small', '跟踪中'));
          tr.append(name);
          for (const [v, unit] of [[row.total_pct, '%'], [row.own_pp, '']]) tr.append(el('td', sign(v, unit), tone(v)));
          tr.append(el('td', row.r2.toFixed(2)), el('td', row.beta.toFixed(2)));
          if (withType) tr.append(el('td', data.labels[row.label]));
          body.append(tr);
        }
      });
    };

    const summary = () => {
      const w = win(), n = w.counts;
      byId('ab-window-summary').textContent = `${w.start_date}至${w.end_date}，合格股票${w.complete}只：独立上涨${n.alpha_up}只、`
        + `抗跌${n.resilient}只、跟随大盘${n.beta}只、跟涨乏力${n.lagging}只、`
        + `独立走弱${n.alpha_down}只、无明显方向${n.none}只。下表各取前20；点股票名看走势。`;
      root.querySelectorAll('button[data-ab-list]').forEach(b => {
        b.setAttribute('aria-pressed', String(b.dataset.abList === state.list));
        const small = b.querySelector('small'); if (small) small.textContent = (n[b.dataset.abList] ?? 0) + '只';
      });
      root.querySelectorAll('button[data-ab-window]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.abWindow === state.window)));
    };

    const select = code => {
      state.code = code;
      root.dataset.abSelected = code || '';
      root.querySelectorAll('#ab-stock-table tbody tr').forEach(tr => tr.setAttribute('aria-selected', String(tr.dataset.abCode === code)));
      path();
    };

    const render = () => {
      root.dataset.abWindow = state.window;
      root.dataset.abList = state.list;
      summary();
      stockTable();
      conceptTables();
      scatter();
      const rows = win().lists[state.list] || [];
      select(rows.some(r => r.code === state.code) ? state.code : rows[0]?.code ||
        Object.values(win().lists).flat()[0]?.code || null);
    };

    root.addEventListener('click', event => {
      const pick = event.target.closest('.ab-pick');
      if (pick) { select(pick.dataset.abCode); return; }
      const list = event.target.closest('button[data-ab-list]');
      if (list) { state.list = list.dataset.abList; render(); return; }
      const size = event.target.closest('button[data-ab-window]');
      if (size && !size.disabled && data.windows[size.dataset.abWindow]) { state.window = size.dataset.abWindow; render(); }
    });
    regime();
    render();
    window.addEventListener('resize', () => Object.values(charts).forEach(c => c.resize()));
    root.dataset.abReady = 'true';
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  window.addEventListener('load', boot);
})();
