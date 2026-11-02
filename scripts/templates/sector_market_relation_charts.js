(() => {
  const boot=()=>{
    const root=document.querySelector('.daily-alpha');
    if(!root||root.dataset.marketReady||!window.echarts)return;
    const data=JSON.parse(root.querySelector('#sector-alpha-data').textContent),relation=data.market_relation;
    const byId=id=>root.querySelector('#'+id),chart=window.echarts.init(byId('market-relation-chart'));
    const red='#E73922',green='#07C160',muted='#747281',ink='#25252b',rule='#e6e3e9';
    const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const nearZero=v=>typeof v==='number'&&Math.abs(v)<.005;
    const fmt=(v,unit='%')=>v==null?'未齐':((nearZero(v)?0:v)>0?'+':'')+(nearZero(v)?0:v).toFixed(2)+unit;
    const tone=v=>v==null||nearZero(v)?muted:v>0?red:green;
    const path=values=>{
      let level=100;
      return [100,...values.map(v=>level=v==null||level==null?null:level*(1+v/100))];
    };
    const summary=(stock,market)=>{
      const pairs=stock.map((v,i)=>[v,market[i]]).filter(([a,b])=>a!=null&&b!=null);
      const complete=pairs.length===stock.length&&stock.length>0;
      const up=pairs.filter(([,b])=>b>0),down=pairs.filter(([,b])=>b<0);
      const sp=path(stock),mp=path(market),mean=rows=>complete&&rows.length?rows.reduce((sum,[v])=>sum+v,0)/rows.length:null;
      return {valid:pairs.length,complete,same:complete?pairs.filter(([a,b])=>a*b>0).length:null,
        up:up.length,down:down.length,upMean:mean(up),downMean:mean(down),
        stock:complete?sp.at(-1)-100:null,market:complete?mp.at(-1)-100:null,
        extra:complete?sp.at(-1)-mp.at(-1):null,stockPath:sp,marketPath:mp};
    };
    let count=relation?.default_window||5;
    const clear=message=>{
      byId('market-relation-summary').textContent=message;
      byId('market-relation-metrics').replaceChildren();
      byId('market-relation-note').textContent='不借其他个股、板块或日期补齐大盘关系。';
      chart.setOption({animation:false,graphic:[{type:'text',left:'center',top:'middle',
        style:{text:message,fill:muted,fontSize:13,textAlign:'center',width:300,overflow:'break'}}]},true);
    };
    const metric=(label,text,color)=>{
      const node=document.createElement('div');node.className='market-relation-metric';
      const title=document.createElement('small');title.textContent=label;
      const value=document.createElement('strong');value.textContent=text;if(color)value.style.color=color;
      node.append(title,value);byId('market-relation-metrics').append(node);
    };
    const draw=()=>{
      chart.dispatchAction?.({type:'hideTip'});
      const identity=root.dataset.selectedSector,code=root.dataset.selectedStock,day=root.dataset.selectedDate;
      const sector=data.sectors[identity],stock=sector?.stocks.find(row=>row.code===code);
      if(!relation){clear('缺少可核对的大盘同窗资料。');return;}
      if(day!==data.target_date||!stock||!relation.stocks[code]||!relation.sectors[identity]){
        clear('该对象或日期未覆盖大盘同窗比较。');return;
      }
      const dates=relation.dates.slice(-count-1),stockDaily=relation.stocks[code].slice(-count),
        marketDaily=relation.market.slice(-count),sectorDaily=relation.sectors[identity].slice(-count);
      const facts=summary(stockDaily,marketDaily),sectorPath=path(sectorDaily);
      const shared=stockDaily.filter((v,i)=>v!=null&&marketDaily[i]!=null&&sectorDaily[i]!=null).length;
      root.dataset.marketWindow=String(count);
      root.querySelectorAll('[data-market-window]').forEach(b=>b.setAttribute('aria-pressed',String(+b.dataset.marketWindow===count)));
      byId('market-relation-summary').textContent=stock.name+' · '+stock.code+'；近'+count+'个交易日，'+dates[0]+'收盘起至'+data.target_date+
        '。个股与大盘有效 '+facts.valid+'/'+count+'日，三者均有效 '+shared+'/'+count+'日。';
      byId('market-relation-metrics').replaceChildren();
      metric('个股与大盘同向日数 / 观察日数',facts.same==null?'未齐（有效 '+facts.valid+'/'+count+'）':facts.same+' / '+count);
      metric('个股相对大盘累计差',fmt(facts.extra,'个百分点'),tone(facts.extra));
      metric('大盘上涨时 · 个股平均日涨跌（'+facts.up+'日）',fmt(facts.upMean),tone(facts.upMean));
      metric('大盘下跌时 · 个股平均日涨跌（'+facts.down+'日）',fmt(facts.downMean),tone(facts.downMean));
      byId('market-relation-note').textContent=
        (facts.complete?'':'个股与大盘资料未齐，关系摘要不完整；缺失不补零。')+
        (shared<count?'板块或其他同窗价格有缺口。':'')+
        (facts.stock!=null&&facts.stock<-.005?'个股绝对累计仍下跌；相对少跌不等于赚钱。':'')+
        (relation.short_history?'只有5日短窗，不能据此判断持续独立行情；20日资料尚缺。':'')+
        '同向天数、相对涨幅和分组均值仅是观察证据，不证明大盘带动或持续独立收益。'+
        '成员名单查询于'+relation.membership_query_date+'，行情补查于'+relation.query_date+'；这是后查名单回看，不是历史成员。';
      const lines=[
        ['个股 · '+stock.name,facts.stockPath,red],
        ['板块 · '+sector.name,sectorPath,'#2364AA'],
        ['大盘 · '+relation.benchmark.name,facts.marketPath,'#b97830'],
      ].map(([name,values,color])=>({type:'line',name,data:values.map(v=>v==null?null:v-100),
        connectNulls:false,showSymbol:false,symbolSize:5,lineStyle:{width:2.2,color},itemStyle:{color}}));
      chart.setOption({animation:false,backgroundColor:'transparent',
        textStyle:{fontFamily:'"Avenir Next","PingFang SC",sans-serif',color:ink},
        legend:{top:4,type:'scroll',textStyle:{fontSize:11},data:lines.map(row=>row.name)},
        grid:{left:58,right:24,top:64,bottom:36},
        xAxis:{type:'category',data:dates,boundaryGap:false,axisLabel:{fontSize:10,formatter:v=>v.slice(5)},axisTick:{show:false}},
        yAxis:{type:'value',name:'同起点累计涨跌 %',axisLabel:{fontSize:10},splitLine:{lineStyle:{color:rule}}},
        tooltip:{trigger:'axis',confine:true,backgroundColor:'#fff',borderColor:rule,textStyle:{fontSize:12,color:ink},
          formatter:params=>{
            const i=params[0]?.dataIndex;if(i==null)return '';
            return '<b>'+esc(dates[i])+'</b>'+(i===0?' · 比较起点':'')+lines.map(row=>
              '<br>'+esc(row.name)+' <b style="color:'+tone(row.data[i])+'">'+fmt(row.data[i])+'</b>').join('')+
              '<br><small>线色区分对象；数字红涨绿跌。不是可成交净收益。</small>';
          }},series:lines},true);
    };
    root.querySelectorAll('[data-market-window]').forEach(b=>b.addEventListener('click',()=>{
      const requested=+b.dataset.marketWindow;
      if(!relation?.available_windows.includes(requested))return;
      count=requested;draw();
    }));
    document.addEventListener('sector-member-selection',draw);
    window.addEventListener('resize',()=>chart.resize());
    new ResizeObserver(()=>chart.resize()).observe(byId('market-relation-chart'));
    draw();root.dataset.marketReady='true';
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
  window.addEventListener('bear:echarts-ready',boot);
})();
