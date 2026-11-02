(() => {
  const boot = () => {
    const root = document.querySelector('.observation-flow');
    if (!root || root.dataset.ready || !window.echarts) return;
    const data = JSON.parse(root.querySelector('#observation-flow-data').textContent);
    const chartNode = root.querySelector('#observation-flow-chart');
    const chart = echarts.init(chartNode);
    const select = root.querySelector('#observation-track');
    const channel = root.querySelector('#observation-channel');
    const windowSelect = root.querySelector('#observation-window');
    const disclosure = root.querySelector('#observation-flow-disclosure');
    const facts = root.querySelector('#observation-flow-facts');
    const ink = getComputedStyle(document.documentElement).getPropertyValue('--reader-text').trim() || '#25252b';
    const fontFamily = '"Avenir Next","PingFang SC",sans-serif';
    const colors = ['#E73922','#07C160','#2364AA','#B000FF','#A62A19','#087B43','#174374','#7400A8','#E88373','#648DBA'];
    // Sector identity colors are presentation only, never rise/fall signals.
    const colorFor = identity => {
      let hash = 0;
      for (const c of identity) hash = (hash * 31 + c.codePointAt(0)) >>> 0;
      return colors[hash % colors.length];
    };
    const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const channels = ids => ids.map(id => (data.channels.find(item => item.id === id) || {}).label).filter(Boolean).join('、');
    const included = ids => channel.value ? ids.filter(id => id === channel.value) : ids;
    const edgeTitle = edge => `${edge.source_date} ${edge.source_sector} → ${edge.target_date} ${edge.target_sector}`;
    const recordFacts = record => `<p><time>${escape(record.date)}</time> · 原始来源：${escape((data.source_labels || {})[record.source || ''] || (record.source ? '已冻结的历史来源' : '未记录'))}<br>原始依据：${escape(record.rotation_summary || '未记录')}</p>`;
    const edgeFacts = edge => `<article class="observation-relay-fact"><h4>${escape(edgeTitle(edge))}</h4><p>${escape(channels(edge.channels))} · ${edge.value}条通道，不是资金量。${escape(edge.interval)}</p>${recordFacts(edge.source_record)}${recordFacts(edge.target_record)}</article>`;
    let visibleNodes = [], visibleLinks = [], visibleDates = [], rendered = false;
    const related = edge => !select.value || edge.source_sector === select.value || edge.target_sector === select.value;
    const renderFacts = () => {
      const edges = visibleLinks.filter(related);
      const node = visibleNodes.findLast(item => !select.value || item.sector === select.value);
      facts.innerHTML = edges.length ? edgeFacts(edges.at(-1)) : node ?
        `<h4>${escape(node.date)} ${escape(node.sector)}</h4><p>${escape(channels(node.channels))}；当前区间没有该板块的可比接力，未补画连线。</p>${recordFacts(node.record)}` :
        '<p>所选板块或通道在当前区间缺少真实记录；可切换通道或扩大报告范围，未补画连线。</p>';
    };
    const columnStep = () => visibleDates.length > 1 ? (chartNode.clientWidth - 210) / (visibleDates.length - 1) : 170;
    const columnX = index => visibleDates.length === 1 ? chartNode.clientWidth / 2 - 9 : 42 + columnStep() * index;
    const seriesBounds = () => ({
      // A positive depth avoids ECharts' zero-depth division for a single day.
      // Only real nodes are used; the plot ends at the last recorded node, not
      // at the last date header, so empty trailing columns stay empty.
      left: columnX(0) - columnStep(),
      width: (Math.max(...visibleNodes.map(node => node.depth), 0) + 1) * columnStep() + 18
    });
    const comparisonOnly = edge => edge.missing_dates.length > 0 || !edge.calendar_known;
    const dateHeaderGraphics = () => {
      const recorded = new Set(data.history.map(row => row.date));
      const graphics = visibleDates.flatMap((date, index) => {
        const x = columnX(index) + 9;
        const empty = !visibleNodes.some(node => node.date === date);
        const items = [{id:`date-${index}`, type:'text', silent:true, x, y:18,
          style:{text:date, fill:ink, font:`600 12px ${fontFamily}`, align:'center', verticalAlign:'middle'}}];
        if (empty) items.push(
          {id:`missing-label-${index}`, type:'text', silent:true, x, y:39,
            style:{text:recorded.has(date) ? '所选通道未记录' : '缺少日报', fill:'#77717f', font:`11px ${fontFamily}`, align:'center'}},
          {id:`missing-line-${index}`, type:'line', silent:true,
            shape:{x1:x, y1:62, x2:x, y2:chartNode.clientHeight - 62}, style:{stroke:'#b8b0be', lineDash:[4,5], opacity:.5}}
        );
        return items;
      });
      if (visibleLinks.some(comparisonOnly)) graphics.push({id:'gap-note', type:'text', silent:true, x:42, y:chartNode.clientHeight - 24,
        style:{text:'浅灰色带：缺日报或未核对交易日历，仅比较前后报告，不代表连续接力', fill:'#77717f', font:`12px ${fontFamily}`}});
      if (!visibleNodes.length) graphics.push({id:'empty-note', type:'text', silent:true, left:'center', top:'middle',
        style:{text:'当前选择没有真实记录，未补画接力', fill:ink, font:`13px ${fontFamily}`, align:'center'}});
      return graphics;
    };
    const size = () => {
      const count = Math.max(visibleDates.length, 1);
      const perDate = visibleDates.map(date => visibleNodes.filter(node => node.date === date).length);
      const maxNodes = Math.max(...perDate, 0);
      chartNode.style.width = `${Math.max(chartNode.parentElement.clientWidth, (count - 1) * 132 + 210)}px`;
      chartNode.style.height = `${Math.max(520, maxNodes * 42 + 120)}px`;
      chart.resize();
      if (rendered) chart.setOption({graphic:dateHeaderGraphics(), ...(visibleNodes.length ? {series:[{id:'relay', ...seriesBounds()}]} : {})});
    };
    const draw = () => {
      const requested = Number(windowSelect.value) || 7;
      const firstReport = data.history.slice(-requested)[0];
      visibleDates = data.dates.filter(date => !firstReport || date >= firstReport.date);
      const dates = new Set(visibleDates);
      visibleNodes = data.nodes.filter(node => dates.has(node.date) && included(node.channels).length)
        .map(node => ({...node, depth:visibleDates.indexOf(node.date), channels:included(node.channels)}));
      const names = new Set(visibleNodes.map(node => node.name));
      visibleLinks = data.links.filter(edge => names.has(edge.source) && names.has(edge.target) && included(edge.channels).length)
        .map(edge => ({...edge, channels:included(edge.channels), value:included(edge.channels).length}));
      const highlighted = new Set(visibleLinks.filter(related).flatMap(edge => [edge.source, edge.target]));
      visibleNodes.filter(node => node.sector === select.value).forEach(node => highlighted.add(node.name));
      rendered = false;
      size();
      if (!visibleNodes.length) {
        rendered = true;
        chart.clear();
        chart.setOption({animation:false, graphic:dateHeaderGraphics()}, true);
        renderFacts();
        return;
      }
      chart.setOption({
        animation:false, backgroundColor:'transparent', color:colors, textStyle:{color:ink,fontFamily},
        tooltip:{trigger:'item', confine:true, backgroundColor:'#fff', borderColor:'rgba(100,96,120,.15)', padding:10, textStyle:{color:ink,fontSize:12,fontFamily}, formatter:params => {
          if (params.dataType === 'edge') return `${escape(edgeTitle(params.data))}<br>${escape(channels(params.data.channels))}<br>${params.data.value}条通道 · 非资金量<br>${escape(params.data.interval)}`;
          const node = visibleNodes.find(item => item.name === params.name);
          return node ? `${escape(node.date)} ${escape(node.sector)}<br>${escape(channels(node.channels))}<br>点击查看流入、流出与原始依据` : '';
        }},
        graphic:dateHeaderGraphics(),
        series:[{id:'relay', type:'sankey', ...seriesBounds(), top:62, bottom:58, nodeWidth:18, nodeGap:34,
          draggable:false, nodeAlign:'left', emphasis:{focus:'adjacency'}, layoutIterations:32,
          data:visibleNodes.map(node => ({...node, depth:node.depth + 1, value:node.channels.length,
            itemStyle:{color:colorFor(node.sector), opacity:!select.value || highlighted.has(node.name) ? 1 : .2},
            label:{formatter:() => `${node.sector}\n${node.channels.length}条通道`}})),
          links:visibleLinks.map(edge => ({...edge,
            lineStyle:{color:comparisonOnly(edge) ? '#aaa3af' : 'source', opacity:related(edge) ? (comparisonOnly(edge) ? .18 : .42) : .06},
            emphasis:{lineStyle:{opacity:comparisonOnly(edge) ? .25 : .85}}
          })),
          lineStyle:{color:'source',curveness:.5}, label:{color:ink,fontSize:12,lineHeight:18,width:104,overflow:'break',backgroundColor:'rgba(255,255,255,.88)',padding:[2,4]}}]
      }, true);
      rendered = true;
      renderFacts();
      const focus = visibleNodes.findLast(node => select.value && node.sector === select.value);
      if (focus) chartNode.parentElement.scrollLeft = columnX(focus.depth) - chartNode.parentElement.clientWidth / 2;
      else chartNode.parentElement.scrollLeft = 0;
    };
    select.addEventListener('change', draw);
    channel.addEventListener('change', draw);
    windowSelect.addEventListener('change', draw);
    chart.on('click', params => {
      disclosure.open = true;
      if (params.dataType === 'edge') {
        facts.innerHTML = edgeFacts(params.data);
        return;
      }
      const node = visibleNodes.find(item => item.name === params.name);
      if (!node) return;
      const edges = visibleLinks.filter(edge => edge.source === node.name || edge.target === node.name);
      facts.innerHTML = `<h4>${escape(node.date)} ${escape(node.sector)} · ${escape(channels(node.channels))}</h4>` +
        (edges.length ? edges.map(edgeFacts).join('') : `<p>当前区间没有可比接力，未补画连线。</p>${recordFacts(node.record)}`);
    });
    draw();
    root.dataset.ready = 'true';
    root.querySelector('.observation-flow-fallback').hidden = true;
    new ResizeObserver(size).observe(root);
    window.addEventListener('resize', size);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
  window.addEventListener('bear:echarts-ready', boot);
})();
