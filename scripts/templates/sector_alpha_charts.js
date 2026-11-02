(() => {
  const boot=()=>{
    const root=document.querySelector('.daily-alpha');
    if(!root||root.dataset.ready||!window.echarts)return;
    const data=JSON.parse(root.querySelector('#sector-alpha-data').textContent);
    const byId=id=>root.querySelector('#'+id);
    const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    // Values that round to zero at this display precision use neutral styling.
    const nearZero=v=>typeof v==='number'&&Math.abs(v)<0.005;
    const fmt=(v,unit='%')=>v==null?'未齐':((nearZero(v)?0:v)>0?'+':'')+(nearZero(v)?0:v).toFixed(2)+unit;
    const memberMiddleLabel='成员收益中间值';
    const trimmedMiddleLabel='去掉5日涨幅最高的一只后，其余成员的中间涨幅';
    const red='#E73922',green='#07C160',blue='#2364AA',muted='#747281',ink='#25252b',rule='#e6e3e9';
    const tone=v=>v==null||nearZero(v)?muted:v>0?red:green;
    const charts=['alpha-sector-chart','alpha-stock-chart','alpha-path-chart'].map(id=>echarts.init(byId(id)));
    const [overall,stockChart,pathChart]=charts;
    const sidebar=byId('alpha-member-sidebar'),sidebarToggle=byId('alpha-sidebar-toggle');
    const stockPanel=byId('alpha-stock-chart-panel'),stockButtons=byId('alpha-stock-buttons');
    let memberView='chart',membersCollapsed=false;
    const resizeStock=()=>{if(!sidebar.hidden&&!stockPanel.hidden)stockChart.resize();};
    const resize=()=>{overall.resize();pathChart.resize();resizeStock();};
    const layoutMembers=()=>{
      stockChart.dispatchAction?.({type:'hideTip'});
      root.dataset.membersCollapsed=String(membersCollapsed);root.dataset.memberView=memberView;
      sidebar.hidden=membersCollapsed;stockPanel.hidden=memberView!=='chart';stockButtons.hidden=memberView!=='list';
      sidebarToggle.setAttribute('aria-expanded',String(!membersCollapsed));
      sidebarToggle.textContent=membersCollapsed?'展开成员侧栏':'收起成员侧栏';
      root.querySelectorAll('[data-alpha-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.alphaView===memberView)));
      resize();
    };
    const base={animation:false,backgroundColor:'transparent',textStyle:{fontFamily:'"Avenir Next","PingFang SC",sans-serif',color:ink},
      tooltip:{confine:true,backgroundColor:'#fff',borderColor:rule,textStyle:{fontSize:12,color:ink},
        extraCssText:'max-width:300px;white-space:normal;line-height:1.7'},
      grid:{left:96,right:58,top:38,bottom:28}};
    const sectors=Object.values(data.sectors).sort((a,b)=>(b.sector_pct??-Infinity)-(a.sector_pct??-Infinity)||a.track_id.localeCompare(b.track_id));
    let identity=data.selected_sector,day=data.target_date,code=data.selected_stock,visible=[];
    const empty=(chart,message)=>chart.setOption({animation:false,graphic:[{type:'text',left:'center',top:'middle',
      style:{text:message,fill:muted,fontSize:13,textAlign:'center',width:260,overflow:'break'}}]},true);
    const chooseSector=id=>{
      const trend=document.querySelector('.sector-trend');
      if(trend)document.dispatchEvent(new CustomEvent('sector-track-selection',{detail:{trackId:id,scroll:false}}));
      else{identity=id;day=data.target_date;code=null;draw();}
    };
    const drawOverall=()=>{
      byId('alpha-sector-chart').style.height=Math.max(220,sectors.length*42+80)+'px';overall.resize();
      overall.setOption({...base,legend:{top:2,data:['板块指数',memberMiddleLabel,'去掉最高涨幅后，中间涨幅'],textStyle:{fontSize:11}},
        grid:{...base.grid,bottom:44},
        xAxis:{type:'value',name:'同5日收益 %',nameLocation:'middle',nameGap:26,splitLine:{lineStyle:{color:rule}},axisLabel:{fontSize:10}},
        yAxis:{type:'category',inverse:true,data:sectors.map(r=>r.name),axisTick:{show:false},axisLine:{show:false},
          axisLabel:{fontSize:11,width:86,overflow:'truncate',color:ink}},
        tooltip:{...base.tooltip,trigger:'axis',axisPointer:{type:'shadow'},formatter:params=>{
          const row=sectors[params[0]?.dataIndex];if(!row)return '';
          return '<b>'+esc(row.display_name)+'</b><br>截至 '+esc(data.target_date)+
            '<br>板块指数 <b>'+fmt(row.sector_pct)+'</b><br>'+memberMiddleLabel+' '+fmt(row.median_pct)+
            '<br>'+trimmedMiddleLabel+' '+fmt(row.median_without_top_pct)+'<br>上涨 '+row.positive_count+'/'+row.valid_count+
            '只；完整样本 '+row.valid_count+'/'+row.member_count+'只'+
            (row.excluded_members?.length?'<br>原目录另含'+row.excluded_members.length+'只窗口前已摘牌股票':'')+
            '<br><small>中间值=按5日涨幅排序后取中间位置；这个对照只检查单只强股影响，不是卖出建议。点选比较个股；概念之间可能重叠</small>';
        }},series:[['sector_pct','板块指数','#4c78b8'],['median_pct',memberMiddleLabel,'#238b85'],['median_without_top_pct','去掉最高涨幅后，中间涨幅','#b97830']]
          .map(([key,name,color])=>({type:'bar',name,itemStyle:{color},barMaxWidth:8,data:sectors.map(r=>({value:r[key],trackId:r.track_id,
            itemStyle:{color,opacity:r.track_id===identity&&day===data.target_date?1:.76}}))}))},true);
    };
    const drawPath=sector=>{
      const stock=sector?.stocks.find(r=>r.code===code);
      if(!sector||!stock||day!==data.target_date){
        root.dataset.selectedStock='';
        byId('alpha-stock-summary').textContent='没有该对象与日期的完整同窗比较。';
        byId('alpha-risk-note').textContent='不借其他板块、个股或日期填充。';
        empty(pathChart,'请选择有同窗记录的个股');return;
      }
      byId('alpha-stock-summary').textContent=stock.name+' · '+stock.code+' · '+data.dates[0]+' 至 '+data.target_date+'；'+
        (stock.outperform_days==null?'逐日记录未齐':stock.outperform_days+'/5日跑赢，最近连续'+stock.trailing_days+'日')+
        (stock.stock_pct!=null&&!nearZero(stock.stock_pct)&&stock.stock_pct<0?'。绝对收益仍下跌，跑赢不等于赚钱。':'。');
      byId('alpha-risk-note').textContent='同一5日窗内最大回撤：个股 '+fmt(stock.max_drawdown_pct)+
        ' / 板块 '+fmt(sector.max_drawdown_pct)+'。这是收盘日收益路径，不含盘中风险与成交成本。'+
        (stock.trailing_days===0?'最近一天已未跑赢，不把累计差值当作仍在增强。':'额外表现能否持续，仍需之后的价格检验。');
      root.dataset.selectedStock=stock.code;
      byId('alpha-stock-buttons').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.alphaStock===code)));
      const zero={silent:true,symbol:'none',label:{show:false},lineStyle:{color:muted,type:'dashed'},data:[{yAxis:0}]};
      const comparison=[
        {label:'板块收益',value:sector.sector_pct,unit:'%',color:blue},
        {label:'个股−板块差',value:stock.excess_pp,unit:'个百分点',color:tone(stock.excess_pp)},
        {label:'个股收益',value:stock.stock_pct,unit:'%',color:tone(stock.stock_pct)},
      ];
      pathChart.setOption({...base,legend:{top:0,data:[stock.name,sector.name,'当日跑赢/跑输'],textStyle:{fontSize:11}},
        graphic:[{type:'text',left:52,top:28,silent:true,style:{text:'同窗收益对照：板块收益 + 个股相对板块差值 = 个股收益',
          fill:muted,fontSize:12,fontWeight:600}}],
        grid:[{left:116,right:116,top:50,height:122},{left:52,right:20,top:232,height:208},{left:52,right:20,top:500,bottom:38}],
        xAxis:[
          {gridIndex:0,type:'value',name:'收益（%） / 差值（百分点）',nameLocation:'middle',nameGap:28,
            splitLine:{lineStyle:{color:rule}},axisLabel:{fontSize:10}},
          {gridIndex:1,type:'category',data:data.dates,boundaryGap:false,
            axisLabel:{fontSize:10,formatter:v=>v.slice(5)},axisTick:{show:false}},
          {gridIndex:2,type:'category',data:data.dates,boundaryGap:true,
            axisLabel:{fontSize:10,formatter:v=>v.slice(5)},axisTick:{show:false}},
        ],
        yAxis:[
          {gridIndex:0,type:'category',inverse:true,data:comparison.map(item=>item.label),axisTick:{show:false},axisLine:{show:false},
            axisLabel:{fontSize:11,color:ink}},
          {gridIndex:1,type:'value',name:'累计收益 %',splitLine:{lineStyle:{color:rule}},axisLabel:{fontSize:10}},
          {gridIndex:2,type:'value',name:'当日差值（百分点）',splitLine:{lineStyle:{color:rule}},axisLabel:{fontSize:10}},
        ],
        tooltip:{...base.tooltip,trigger:'axis',formatter:params=>{
          const first=Array.isArray(params)?params[0]:params;
          if(first?.seriesName==='同窗收益对照'){
            const item=comparison[first.dataIndex];
            return '<b>'+item.label+'</b><br>'+fmt(item.value,item.unit)+
              '<br><small>同一5日窗口的收益对照，不代表因果归因。</small>';
          }
          const i=params[0]?.dataIndex;if(i==null)return '';
          return '<b>'+esc(data.dates[i])+'</b>'+ (i===0?' · 比较起点':'')+
            '<br>'+esc(stock.name)+'累计 <b>'+fmt(stock.path[i])+'</b><br>'+esc(sector.name)+'累计 '+fmt(sector.path[i])+
            '<br>累计差 '+fmt(stock.path[i]!=null&&sector.path[i]!=null?stock.path[i]-sector.path[i]:null,'个百分点')+
            (i?'<br>当日跑赢/跑输 <b style="color:'+tone(stock.daily_excess[i])+'">'+fmt(stock.daily_excess[i],'个百分点')+'</b>':'');
        }},series:[{type:'line',name:stock.name,xAxisIndex:1,yAxisIndex:1,data:stock.path,connectNulls:false,symbolSize:5,lineStyle:{width:2.8},itemStyle:{color:red}},
          {type:'line',name:sector.name,xAxisIndex:1,yAxisIndex:1,data:sector.path,connectNulls:false,symbolSize:4,lineStyle:{width:2},itemStyle:{color:blue}},
          {type:'bar',name:'当日跑赢/跑输',xAxisIndex:2,yAxisIndex:2,barMaxWidth:24,markLine:zero,
            data:stock.daily_excess.map(v=>({value:v,itemStyle:{color:tone(v)}}))},
          {type:'bar',name:'同窗收益对照',xAxisIndex:0,yAxisIndex:0,barMaxWidth:18,
            tooltip:{trigger:'item',formatter:p=>{const item=comparison[p.dataIndex];return '<b>'+item.label+'</b><br>'+fmt(item.value,item.unit)+'<br><small>同一5日窗口的收益对照，不代表因果归因。</small>'; }},
            data:comparison.map(item=>({value:item.value,itemStyle:{color:item.color},label:{show:true,position:'right',color:ink,fontSize:12,
              formatter:()=>fmt(item.value,item.unit)}}))}]},true);
    };
    const draw=()=>{
      charts.forEach(chart=>chart.dispatchAction?.({type:'hideTip'}));
      root.dataset.selectedSector=identity;root.dataset.selectedDate=day;
      root.querySelectorAll('[data-alpha-sector]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.alphaSector===identity&&day===data.target_date)));
      drawOverall();
      const sector=data.sectors[identity];
      if(!sector||day!==data.target_date){
        code=null;root.dataset.selectedStock='';visible=[];byId('alpha-stock-buttons').replaceChildren();
        byId('alpha-stock-chart').style.height='210px';resizeStock();
        byId('alpha-sector-summary').textContent=day!==data.target_date?
          day+'没有冻结的同窗成员比较；上图固定为截至'+data.target_date+'的回看，不是所选日排名。':
          '所选板块未补查成员，不能用其他板块的股票代替。';
        empty(stockChart,'该对象/日期未覆盖成员比较');drawPath(null);
        document.dispatchEvent(new CustomEvent('sector-member-selection'));return;
      }
      byId('alpha-sector-summary').textContent=sector.name+'：指数 '+fmt(sector.sector_pct)+'；'+sector.positive_count+'/'+sector.valid_count+
        '只完整样本上涨，成员收益中间值 '+fmt(sector.median_pct)+'，去掉5日涨幅最高的一只后，其余成员的中间涨幅为 '+fmt(sector.median_without_top_pct)+
        '。有效成员 '+sector.valid_count+'/'+sector.member_count+'只；仅描述本次覆盖，不推断大盘带动或全市场。'+
        (sector.excluded_members?.length?' 原目录'+sector.directory_member_count+'只；'+
          sector.excluded_members.map(r=>r.name+'（'+r.code+'）于'+r.delist_date+'已摘牌').join('、')+
          '，不作为本窗口缺失行情。':'');
      visible=[...sector.stocks].sort((a,b)=>(b.excess_pp??-Infinity)-(a.excess_pp??-Infinity)||a.code.localeCompare(b.code));
      if(!visible.some(r=>r.code===code))code=identity===data.selected_sector&&visible.some(r=>r.code===data.selected_stock)?data.selected_stock:
        (visible.find(r=>r.excess_pp!=null)||visible.find(r=>r.stock_pct!=null)||visible[0])?.code;
      const buttons=byId('alpha-stock-buttons'),previous=[...buttons.querySelectorAll('button')];
      if(previous.length!==visible.length||previous.some((b,i)=>b.dataset.alphaStock!==visible[i].code)){
        const focused=previous.includes(document.activeElement)?document.activeElement.dataset.alphaStock:null;
        buttons.replaceChildren();
        for(const row of visible){
          const b=document.createElement('button');b.type='button';b.className='reading-tag';b.dataset.alphaStock=row.code;
          const name=document.createElement('strong');name.textContent=row.name;
          const info=document.createElement('small');info.textContent=row.code+' · 5日 '+fmt(row.stock_pct);
          const extra=document.createElement('span');extra.className='alpha-stock-excess';
          extra.textContent=fmt(row.excess_pp,'');
          extra.style.color=row.excess_pp==null||nearZero(row.excess_pp)?'#625e6b':row.excess_pp>0?'#b62a1b':'#087a42';
          b.setAttribute('aria-label',row.name+'，'+row.code+'，5日收益'+fmt(row.stock_pct)+'，相对板块差'+fmt(row.excess_pp,'个百分点'));
          b.append(name,info,extra);b.setAttribute('aria-pressed',String(row.code===code));
          b.addEventListener('click',()=>{code=row.code;draw();});buttons.append(b);
        }
        if(focused)[...buttons.querySelectorAll('button')].find(b=>b.dataset.alphaStock===focused)?.focus({preventScroll:true});
      }
      const node=byId('alpha-stock-chart');node.style.height=Math.max(210,visible.length*30+60)+'px';resizeStock();
      stockChart.setOption({...base,grid:{left:100,right:65,top:28,bottom:46},
        xAxis:{type:'value',name:'同5日差值（百分点）',nameLocation:'middle',nameGap:27,axisLabel:{fontSize:10},splitLine:{lineStyle:{color:rule}}},
        yAxis:{type:'category',inverse:true,data:visible.map(r=>r.name),axisLabel:{fontSize:11,width:86,overflow:'truncate'},axisTick:{show:false},axisLine:{show:false}},
        tooltip:{...base.tooltip,trigger:'item',formatter:p=>{
          const r=visible[p.dataIndex];return r?'<b>'+esc(r.name)+' · '+esc(r.code)+'</b><br>个股 '+fmt(r.stock_pct)+
            '<br>板块 '+fmt(sector.sector_pct)+'<br>差值 <b>'+fmt(r.excess_pp,'个百分点')+'</b><br>'+
            (r.outperform_days==null?'逐日未齐':r.outperform_days+'/5日跑赢，最近连续'+r.trailing_days+'日')+
            (r.stock_pct!=null&&!nearZero(r.stock_pct)&&r.stock_pct<0?'<br><b>绝对收益仍下跌</b>':''):'';
        }},series:[{type:'bar',barMaxWidth:13,data:visible.map(r=>({value:r.excess_pp,code:r.code,
          itemStyle:{color:tone(r.excess_pp),opacity:r.code===code?1:.48,borderColor:r.code===code?ink:'transparent',borderWidth:r.code===code?1:0}})),
          label:{show:true,position:'right',fontSize:10,formatter:p=>fmt(p.value,'')},
          markLine:{silent:true,symbol:'none',label:{show:false},data:[{xAxis:0}],lineStyle:{color:muted}}}]},true);
      drawPath(sector);
      document.dispatchEvent(new CustomEvent('sector-member-selection'));
    };
    root.querySelectorAll('[data-alpha-sector]').forEach(b=>b.addEventListener('click',()=>chooseSector(b.dataset.alphaSector)));
    root.querySelectorAll('[data-alpha-alternative]').forEach(b=>b.addEventListener('click',()=>chooseSector(b.dataset.alphaAlternative)));
    overall.on('click',p=>{if(p.componentType==='series'&&p.data?.trackId)chooseSector(p.data.trackId);});
    stockChart.on('click',p=>{if(p.componentType==='series'&&p.data?.code){code=p.data.code;draw();}});
    document.querySelector('.sector-trend')?.addEventListener('trend-selection-change',()=>{
      const panel=document.getElementById('trend-fact-panel');
      identity=panel?.hidden?'':panel?.dataset.trendTrack;day=panel?.dataset.trendDate||'';code=null;draw();
    });
    root.querySelectorAll('[data-alpha-view]').forEach(b=>b.addEventListener('click',()=>{
      memberView=b.dataset.alphaView;layoutMembers();
    }));
    sidebarToggle.addEventListener('click',()=>{
      membersCollapsed=!membersCollapsed;sidebarToggle.focus({preventScroll:true});layoutMembers();
    });
    draw();layoutMembers();root.dataset.ready='true';
    window.addEventListener('resize',resize);
    new ResizeObserver(resize).observe(root);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
  window.addEventListener('bear:echarts-ready',boot);
})();
