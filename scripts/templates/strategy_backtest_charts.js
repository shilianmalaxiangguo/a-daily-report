(() => {
  const boot = () => {
    const node = document.getElementById('bt-equity-chart');
    if (!node || node.dataset.ready || !window.echarts) return;
    const data = JSON.parse(document.getElementById('strategy-backtest-data').textContent);
    const muted = '#7a7882', rule = '#e6e3e9';
    const colors = {live_rule: '#E73922', alpha: '#5b45b5', alpha_regime: '#a497e3', beta: '#2364aa', beta_offense: '#8fb3dd',
      stance: '#b0742a', index: '#18171c', '399006.SZ': '#d97706', '000688.SH': '#0e7490', equal_weight: '#4b5563',
      random: '#9ca3af', random_offense: '#cbd5e1', small_cap_plan: '#c026d3', small_cap_plan_hold: '#86198f', small_cap_pool: '#e879f9', '932000.CSI': '#65a30d'};
    const dash = {strategy: 'solid', hold: 'dashed', reference: 'dotted', random: 'dashed', plan: 'solid'};
    const series = data.series || Object.keys(data.names || {}).map(k => ({key: k, name: data.names[k], kind: k === 'index' ? 'hold' : 'strategy'}));
    const hidden = new Set(data.hidden || []);
    const start = data.dates.findIndex(d => d >= data.design_start);
    const chart = window.echarts.init(node);
    chart.setOption({
      animation: false,
      tooltip: {trigger: 'axis', valueFormatter: v => v == null ? '—' : v.toFixed(3)},
      legend: {top: 0, type: 'scroll', data: series.map(s => s.name),
               selected: Object.fromEntries(series.map(s => [s.name, !hidden.has(s.key)]))},
      grid: {left: 48, right: 16, top: 40, bottom: 36},
      xAxis: {type: 'category', data: data.dates, axisLabel: {color: muted, formatter: v => v.slice(2, 7)},
              axisLine: {lineStyle: {color: rule}}},
      yAxis: {type: 'value', scale: true, axisLabel: {color: muted}, splitLine: {lineStyle: {color: rule}}},
      series: series.map((s, n) => ({
        name: s.name, type: 'line', data: data.curves[s.key], showSymbol: false,
        lineStyle: {width: s.kind === 'plan' ? 3 : s.key === 'index' || s.key === 'live_rule' ? 2.6 : s.kind === 'strategy' ? 1.5 : 1.8,
                    color: colors[s.key] || muted, type: dash[s.kind] || 'solid'},
        itemStyle: {color: colors[s.key] || muted},
        ...(n === 0 && start > 0 ? {markArea: {silent: true, itemStyle: {color: 'rgba(122,120,130,0.10)'},
          data: [[{xAxis: data.dates[start]}, {xAxis: data.dates[data.dates.length - 1]}]]}} : {}),
      })),
    }, true);
    window.addEventListener('resize', () => chart.resize());
    node.dataset.ready = 'true';
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  window.addEventListener('load', boot);
})();
