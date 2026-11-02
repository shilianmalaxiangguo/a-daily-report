// Shared factual chart functions are supplied by sector_reading_content.py.
const chartPayload = JSON.parse(document.getElementById('bear-chart-payload').textContent);
const drawTurnover = (node, payload, share) => {
  const items = payload.items;
  const chart = window.echarts.init(node, null, {renderer: 'canvas'});
  const scopes=[['hs_a','Top50占比 · 沪深'],['hsbj_a','Top50占比 · 含北交所']];
  const series = share ? [
    ...scopes.filter(([scope])=>items.some(item=>item.top50_scope===scope)).map(([scope,name])=>({
      name,type:'line',connectNulls:false,symbol:'circle',symbolSize:4,showSymbol:false,
      itemStyle:{color:scope==='hs_a'?chartTone.red:'#946b37'},lineStyle:{width:2.4},
      data:items.map(item=>item.top50_scope===scope?nullableNumber(item.top50_share_pct):null)})),
    ...(items.some(item=>!scopes.some(([scope])=>scope===item.top50_scope))?[{
      name:'Top50占比 · 范围待确认',type:'scatter',symbolSize:6,itemStyle:{color:chartTone.muted},
      data:items.map(item=>scopes.some(([scope])=>scope===item.top50_scope)?null:nullableNumber(item.top50_share_pct))}]:[]),
    {name: '创业板指', type: 'line', yAxisIndex: 1, connectNulls: false,showSymbol:false,
      itemStyle:{color:chartTone.iceBlue},lineStyle:{width:2.4},
      data: items.map(item => nullableNumber(item.chinext_close))},
  ] : [{name: '两市成交额', type: 'bar', barMaxWidth: 28,
    data: items.map(item => {
      const value=nullableNumber(item.total_turnover);
      return {value,itemStyle:{color:value===null?chartTone.muted:
        value<15000?'#B000FF':value<20000?chartTone.green:chartTone.red}};
    }),
    markLine:{silent:true,symbol:'none',lineStyle:{type:'dashed',width:1.5},
      label:{formatter:'{b}',position:'insideEndTop',fontSize:10},data:[
        {yAxis:15000,name:'1.5万亿',lineStyle:{color:'#B000FF'}},
        {yAxis:20000,name:'2万亿',lineStyle:{color:chartTone.green}},
      ]}}];
  chart.setOption({
    ...baseChartOption(),
    color: [chartTone.red, chartTone.iceBlue],
    legend: {top: 4, left: 'center', data: series.map(item => item.name)},
    grid: {left: 62, right: share ? 64 : 24, top: 56, bottom: 50},
    xAxis: marketTrendXAxis(items),
    yAxis: share ? [
      {type: 'value', name: '占比（%）', scale: true},
      {type: 'value', name: '创业板指', scale: true, splitLine: {show: false}},
    ] : {type: 'value', name: '成交（亿元）', min:0,
      max:value=>Math.max(25000,Math.ceil(value.max/5000)*5000), interval:5000,
      axisLabel:{formatter:value=>Math.round(value).toLocaleString('en-US')}},
    tooltip: {...baseChartOption().tooltip, trigger: 'axis', formatter: params => {
      const index = params[0]?.dataIndex;
      if (index == null) return '';
      const item = items[index];
      if(share){
        const validCalendar=payload.schema==='sector_top50.v1'&&payload.trade_dates?.length===items.length&&
          items.every((r,i)=>r.date===payload.trade_dates[i]&&(i===0||items[i-1].date<r.date));
        const previous=validCalendar&&index>0?items[index-1]:null;
        const ratio=nullableNumber(item.top50_share_pct),close=nullableNumber(item.chinext_close);
        const known=['hs_a','hsbj_a'].includes(item.top50_scope);
        const priorRatio=known&&previous?.top50_scope===item.top50_scope?nullableNumber(previous.top50_share_pct):null;
        const priorClose=previous?nullableNumber(previous.chinext_close):null;
        const signed=(v,unit='')=>(v>0?'+':'')+v.toFixed(2)+unit;
        const ratioChange=ratio!=null&&priorRatio!=null?ratio-priorRatio:null;
        const indexChange=close!=null&&priorClose>0?close-priorClose:null;
        const delta=(v,text)=>v==null?'前值未齐，不判升降':signed(v)+text;
        return '<div class="top50-tip"><div class="top50-tip-date">'+escapeText(item.date)+'</div>'+
          '<div class="top50-tip-metric"><span>头部成交占比'+(known?'':' · 范围未核实')+'</span>'+
          '<strong class="top50-tip-value">'+(ratio==null?'未齐':ratio.toFixed(2)+'%')+'</strong>'+
          '<b class="top50-tip-change">'+delta(ratioChange,'个百分点')+'</b></div>'+
          '<div class="top50-tip-metric"><span>创业板指</span><strong class="top50-tip-value">'+
          (close==null?'未齐':close.toFixed(2))+'</strong><b class="top50-tip-change">'+
          (indexChange==null?'前值未齐，不判升降':signed(indexChange/priorClose*100,'%')+' / '+signed(indexChange,'点'))+
          '</b></div><div class="top50-tip-foot">'+(previous?'变化对照 '+escapeText(previous.date):'窗口首日或日历未核实')+
          '；集中度与指数分开阅读，不表示因果。</div></div>';
      }
      return [escapeText(item.date), ...params.map(param =>
        `${escapeText(param.seriesName)}：${nullableNumber(param.value) === null ? '待确认' : Number(param.value).toFixed(2)}`)].join('<br>');
    }},
    series,
  });
  return chart;
};

const drawBreadth = node => {
  const items = chartPayload.t0_market_breadth.items;
  const chart = window.echarts.init(node, null, {renderer: 'canvas'});
  chart.setOption({
    ...baseChartOption(),
    color: [chartTone.red, chartTone.green, chartTone.iceBlue],
    legend: {top: 4, left: 'center', data: ['上涨家数', '下跌家数', '全A涨跌幅']},
    grid: {left: 58, right: 62, top: 48, bottom: 50},
    xAxis: marketTrendXAxis(items),
    yAxis: [
      {type: 'value', name: '家数', min: value => Math.min(-5200, value.min),
        axisLabel: {color: chartTone.muted, formatter: value => Math.abs(value)}},
      {type: 'value', name: '变化/占比（%）', scale: true, axisLabel: {color: chartTone.muted}},
    ],
    tooltip: {...baseChartOption().tooltip, trigger: 'axis', formatter: params => {
      const index = params[0]?.dataIndex;
      if (index == null) return '';
      const item = items[index];
      const lines = [`<strong>${escapeText(item.date)}</strong>`];
      for (const [label, value, suffix] of [
        ['上涨家数', item.up_count, '家'], ['下跌家数', item.down_count, '家'],
        ['全A涨跌幅', item.all_a_change_pct, '%'],
      ]) {
        const number = nullableNumber(value);
        lines.push(`${label}：${number === null ? '待确认' : `${number}${suffix}`}`);
      }
      return lines.join('<br>');
    }},
    series: [
      {name: '上涨家数', type: 'bar', yAxisIndex: 0, stack: 'breadth', barMaxWidth: 20,
        itemStyle: {borderRadius: [7, 7, 0, 0]},
        data: items.map(item => nullableNumber(item.up_count))},
      {name: '下跌家数', type: 'bar', yAxisIndex: 0, stack: 'breadth', barMaxWidth: 20,
        itemStyle: {borderRadius: [0, 0, 7, 7]},
        data: items.map(item => ({value: nullableNumber(item.down_count) === null ? null : -item.down_count,
          itemStyle: {color: nullableNumber(item.down_count) > 5000 ? '#B000FF' : chartTone.green}})),
        markLine: {silent: true, symbol: 'none', data: [
          {yAxis: -4000, lineStyle: {color: chartTone.green}, label: {formatter: '4000家', position: 'insideEndTop'}},
          {yAxis: -5000, lineStyle: {color: '#B000FF'}, label: {formatter: '5000家', position: 'insideEndBottom'}},
        ]}},
      {name: '全A涨跌幅', type: 'line', yAxisIndex: 1, connectNulls: false,
        data: items.map(item => nullableNumber(item.all_a_change_pct))},
    ],
  });
  return chart;
};

const drawTurnoverTop30 = node => {
  const items = chartPayload.turnover_top30.items;
  const chart = window.echarts.init(node, null, {renderer: 'canvas'});
  chart.setOption({
    ...baseChartOption(),
    grid: {left: 126, right: 145, top: 16, bottom: 28},
    xAxis: {type: 'value', name: '成交（亿元）', axisLabel: {show: true, color: chartTone.muted}},
    yAxis: {type: 'category', inverse: true,
      data: items.map(item => `${nullableNumber(item.rank) === null ? '待确认' : Math.round(nullableNumber(item.rank))}. ${item.name}`),
      axisLabel: {color: chartTone.text, interval: 0, width: 118, overflow: 'truncate'},
      axisTick: {show: false}, axisLine: {show: false}},
    tooltip: {...baseChartOption().tooltip, formatter: params => {
      const item = params.data?.item || {};
      return [
        `<strong>${escapeText(item.name)}(${escapeText(item.code)})</strong>`,
        `成交额：${escapeText(formatAmount(item.turnover))}`,
        `涨跌幅：${escapeText(formatSignedPct(item.change_pct))}`,
        `行业/概念：${escapeText(item.sector || '待确认')}`,
      ].join('<br>');
    }},
    series: [{name: '成交额', type: 'bar', barMaxWidth: 20,
      data: items.map(item => ({value: nullableNumber(item.turnover), item})),
      itemStyle: {color: params => {
        const change = nullableNumber(params.data.item.change_pct);
        return change === null ? chartTone.muted : change < 0 ? chartTone.green : chartTone.red;
      }},
      label: {show: true, position: 'right', color: chartTone.muted,
        formatter: params => `${formatAmount(params.data.item.turnover)} · ${formatSignedPct(params.data.item.change_pct)}`},
    }],
  });
  return chart;
};

const drawLhb = node => {
  const chart = renderLhbNetFlowChart(node, chartPayload.lhb_net_flow);
  chart.setOption({tooltip: {...baseChartOption().tooltip, formatter: params => {
    const item = params.data?.item || {};
    return [`<strong>${escapeText(item.name)}(${escapeText(item.code)})</strong>`,
      `方向：${item.side === 'buy' ? '净买入' : '净流出'}`,
      `净额：${escapeText(formatSignedAmount(item.amount))}`,
      `板块：${escapeText(item.sector || '待确认')}`,
      `涨跌幅：${escapeText(formatSignedPct(item.change_pct))}`,
      item.status ? `状态：${escapeText(item.status)}` : '',
      item.reason ? `披露原因：${escapeText(item.reason)}` : '',
    ].filter(Boolean).join('<br>');
  }}});
  chart.setOption({
    grid: {left: 132, right: 82},
    yAxis: {axisLabel: {width: 124, overflow: 'truncate', fontSize: 12}},
  });
  return chart;
};

const drawNewHigh = node => {
  const items = chartPayload.new_high_share_trend.items;
  const chart = window.echarts.init(node, null, {renderer: 'canvas'});
  chart.setOption({...baseChartOption(),
    color: [chartTone.red, chartTone.iceBlue],
    legend: {top: 4, left: 'center', data: ['创新高占比', '创新高数量']},
    grid: {left: 58, right: 58, top: 56, bottom: 50},
    xAxis: marketTrendXAxis(items),
    yAxis: [{type: 'value', name: '占比（%）', min:0, max:value=>Math.max(6,value.max*1.1)},
      {type: 'value', name: '数量（只）', minInterval: 1, splitLine: {show: false}}],
    tooltip: {...baseChartOption().tooltip, trigger: 'axis', formatter: params => {
      const item = items[params[0]?.dataIndex];
      if (!item) return '';
      const sample = item.all_a_denominator == null ? '' :
        `<br>当日成交样本：${escapeText(item.all_a_denominator)}只<br>参与新高统计：${escapeText(item.eligible_count)}只`+
        `<br>排除ST：${escapeText(item.excluded_counts?.st)}只；上市不足365日：${escapeText(item.excluded_counts?.recent_listing)}只`;
      const gap = item.missing_reason ? '<br>缺失原因：'+escapeText(item.missing_reason) : '';
      return `${escapeText(item.date)}<br>创新高占比：${formatSignedPct(item.new_high_share_pct)}<br>创新高数量：${nullableNumber(item.new_high_count) ?? '待确认'}${sample}${gap}`;
    }},
    series: [{name: '创新高占比', type: 'line', connectNulls: false,
      data: items.map(item => nullableNumber(item.new_high_share_pct)),
      markLine:{silent:true,symbol:'none',lineStyle:{type:'dashed'},
        label:{formatter:'{b}',position:'insideEndTop',fontSize:10},data:[
          {yAxis:5,name:'5%',lineStyle:{color:chartTone.red,width:1.6}},
          {yAxis:2,name:'2%',lineStyle:{color:chartTone.green,width:1.4}},
          {yAxis:1,name:'1%',lineStyle:{color:chartTone.iceBlue,width:1.4}},
          {yAxis:.2,name:'0.2%',lineStyle:{color:chartTone.deepIceBlue,width:1.4},label:{position:'insideEndBottom'}},
        ]}},
    {name: '创新高数量', type: 'bar', yAxisIndex: 1, barMaxWidth: 20,
      data: items.map(item => nullableNumber(item.new_high_count))}],
  });
  return chart;
};

const renderers = {
  t0_market_breadth: drawBreadth,
  cffex_position_trend: node => renderCffexPositionTrendChart(node, chartPayload.cffex_position_trend),
  market_turnover_trend: node => drawTurnover(node, chartPayload.market_turnover_top50_trend, false),
  top50_share_trend: node => drawTurnover(node, chartPayload.market_turnover_top50_trend, true),
  turnover_top30: drawTurnoverTop30,
  lhb_net_flow: drawLhb,
  new_high_share_trend: drawNewHigh,
};

// Initialize only visible cards; closed evidence does not allocate canvases.
const charts = new Map();
const draw = () => {
  if (!window.echarts) return;
  for (const node of document.querySelectorAll('[data-bear-chart]')) {
    let closed = false;
    for (let ancestor = node.parentElement; ancestor; ancestor = ancestor.parentElement) {
      if (ancestor.tagName === 'DETAILS' && !ancestor.open) { closed = true; break; }
    }
    if (closed) continue;
    if (!node.getClientRects().length || !node.clientWidth) continue;
    if (!charts.has(node)) {
      const renderer = renderers[node.dataset.bearChart];
      const chart = renderer?.(node);
      if (chart) charts.set(node, chart);
    } else {
      charts.get(node).resize();
    }
  }
};
let queued = false;
const schedule = () => {
  if (queued) return;
  queued = true;
  requestAnimationFrame(() => { queued = false; draw(); });
};
document.querySelector('main').addEventListener('toggle', schedule, true);
window.addEventListener('resize', schedule);
window.addEventListener('bear:echarts-ready', schedule);
schedule();
