(() => {
  const payload = JSON.parse(document.getElementById('sector-visualization-payload').textContent);
  const css = getComputedStyle(document.documentElement);
  const ink = css.getPropertyValue('--reader-text').trim() || '#44434a';
  const muted = css.getPropertyValue('--reader-muted').trim() || '#7a7882';
  const rule = css.getPropertyValue('--reader-line').trim() || '#dfdee5';
  const number = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
  const signed = (value, unit = '%') => number(value) === null ? '未记录' : `${value > 0 ? '+' : ''}${value.toFixed(2)}${unit}`;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const color = value => value === 0 ? muted : value < 0 ? '#07C160' : '#E73922';
  const charts = new Map();
  const draw = () => {
    if (!window.echarts) return;
    for (const node of document.querySelectorAll('[data-sector-daily-chart]')) {
      if (!node.clientWidth) continue;
      const flow = node.dataset.sectorDailyChart === 'flow';
      const industry = node.dataset.sectorDailyChart === 'industry';
      const industryGroup = industry ? payload.industry_groups[node.dataset.industryGroup] : null;
      const rows = industry ? (industryGroup?.[node.dataset.industryDirection] || [])
        : flow ? (payload.flow_groups[node.dataset.sectorSource] || [])
        : (payload.change_groups[node.dataset.sectorSource] || []);
      if (!rows.length) continue;
      const valueKey = flow ? 'net_amount' : 'change_pct';
      const unit = flow ? '亿元' : '%';
      const name = flow ? '行业净额' : industry ? '行业涨跌幅' : '涨跌幅';
      const industryExtent = industry ? Math.ceil(Math.max(...[...industryGroup.up, ...industryGroup.down]
        .map(row => Math.abs(row.change_pct)))) : null;
      const chart = charts.get(node) || window.echarts.init(node, null, {renderer: 'canvas'});
      charts.set(node, chart);
      chart.resize();
      chart.setOption({
        animation: false,
        backgroundColor: 'transparent',
        textStyle: {color: ink, fontFamily: '"Avenir Next","PingFang SC",sans-serif'},
        grid: {left: 168, right: 78, top: 24, bottom: 44},
        xAxis: {type: 'value', name: unit, axisLabel: {color: muted, fontSize: 11},
          ...(industry ? {min: node.dataset.industryDirection === 'down' ? -industryExtent : 0,
            max: node.dataset.industryDirection === 'down' ? 0 : industryExtent} : {}),
          splitLine: {lineStyle: {color: rule, type: 'dashed'}}},
        yAxis: {type: 'category', inverse: true, data: rows.map(row => row.name),
          axisLabel: {color: ink, fontSize: 12, interval: 0,
            width: 156, overflow: 'truncate'},
          axisTick: {show: false}, axisLine: {show: false}},
        tooltip: {trigger: 'axis', axisPointer: {type: 'shadow', axis: 'y'}, confine: true,
          backgroundColor: '#fff', borderColor: rule,
          textStyle: {color: ink, fontSize: 12}, formatter: params => {
            const point = Array.isArray(params) ? params[0] : params;
            if (!point) return '';
            const row = rows[point.dataIndex];
            const lines = [`<strong>${escape(row.name)}</strong>`, `${name}：${signed(row[valueKey], unit)}`];
            if (industry) {
              lines.push(`强于全A：${signed(number(payload.all_a_change_pct) === null ? null : row.change_pct - payload.all_a_change_pct, '个百分点')}`);
              lines.push(`行业样本：${industryGroup.total_count} 条 · 来源层级：行业`);
            } else if (flow) {
              lines.push(`当日涨跌：${signed(row.change_pct)}`);
              if (row.stock_count != null || row.matched_stock_count != null) {
                if (row.matched_stock_count != null) {
                  lines.push(`已匹配/记录个股：${row.matched_stock_count}/${row.stock_count ?? '未记录'} 只`);
                } else {
                  lines.push(`板块成分股：${row.stock_count} 只`);
                }
              } else lines.push('板块成分股：未记录');
            }
            else {
              const relative = number(payload.all_a_change_pct) === null ? null : row.change_pct - payload.all_a_change_pct;
              lines.push(`强于全A：${signed(relative, '个百分点')}`);
              lines.push(`上涨/样本：${row.stock_count == null ? '未记录' : `${row.up_count}/${row.stock_count}`}`);
              lines.push(`成交额：${signed(row.turnover_yi, '亿元')}`);
            }
            lines.push(`事实日：${escape(row.trade_date || payload.target_date)}`,
              `来源：${escape(row.data_source || '未记录')}`,
              `来源日：${escape(row.source_date || '未记录')} · 查询日：${escape(row.query_date || '未记录')}`);
            if (row.query_date > payload.target_date) lines.push('事后查询，不代表当时已经取得');
            if (row.retrieved_at) lines.push(`取得于：${escape(row.retrieved_at)}`);
            if (row.provenance_note) lines.push(escape(row.provenance_note));
            return lines.join('<br>');
          }},
        series: [{name, type: 'bar', barMaxWidth: 16,
          data: rows.map(row => ({value: row[valueKey], itemStyle: {color: color(row[valueKey])}})),
          label: {show: true, position: 'right', color: muted, fontSize: 11,
            formatter: params => signed(rows[params.dataIndex][valueKey], flow ? '' : '%')}}],
      }, true);
      if(!flow&&!industry&&!node.dataset.selectionReady){
        chart.on('click',event=>{
          if(event.componentType!=='series')return;
          const row=rows[event.dataIndex];
          if(row?.code)document.dispatchEvent(new CustomEvent('sector-track-selection',
            {detail:{trackId:'index:'+row.code}}));
        });
        node.dataset.selectionReady='true';
      }
    }
  };
  let queued = false;
  const schedule = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; draw(); });
  };
  window.addEventListener('resize', schedule);
  window.addEventListener('bear:echarts-ready', schedule);
  schedule();
})();
