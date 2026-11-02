(() => {
let chooseFact;
const memberMarkup=(data,identity,day,full=false)=>{
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const payload=data.member_comparison,sector=payload?.sectors[identity];
  if(!payload)return '';
  if(!sector)return '<p>该板块不在本次精选成分补查范围，没有成分榜。</p>';
  const fmt=(v,unit='')=>v==null?'待确认':Number(v).toFixed(2)+unit;
  const returnText=(value,text)=>{
    const valid=typeof value==='number'&&Number.isFinite(value);
    const sign=!valid?'missing':value>0?'up':value<0?'down':'flat';
    const color=sign==='up'?'#E73922':sign==='down'?'#07C160':'#747281';
    const label=text??(valid?(value>0?'+':'')+value.toFixed(2)+'%':'待确认');
    return '<span data-return-sign="'+sign+'" style="color:'+color+'">'+escape(label)+'</span>';
  };
  const historical=day!==payload.target_date;
  let out=full?'<p><strong>'+escape(sector.name)+'</strong></p>':'';
  out+='<p>最新成分回看 · 行情截至 '+escape(payload.target_date)+' · 成分查询 '+escape(payload.query_date)+
    ' · 名单 '+sector.member_count+' 只</p>';
  if(historical)out+='<p>曲线节点 '+escape(day)+' 没有对应历史成分榜；以下为报告日行情回看，不是该节点当时可知的排名。</p>';
  const lookup=new Map(sector.rows.map(r=>[r.code,r]));
  const relative=data.member_relative?.sectors[identity];
  const relativeText=row=>{
    const r=relative?.rows[row.code];
    return r?'板块同窗 '+fmt(r.sector_pct,'%')+' · 差值 '+fmt(r.excess_pp,'个百分点'):'同窗比较待确认';
  };
  if(relative)out+='<p>同窗日收益：'+escape(data.member_relative.dates.join('、'))+'；以下差值不是已识别的alpha。'+
    escape(data.member_relative.price_basis_note)+'</p>';
  const boards=[['近5日涨幅',sector.gain_codes,'five_day_pct','%',sector.coverage.five_day],
    ['当日成交额',sector.amount_codes,'turnover_yi','亿元',sector.coverage.amount]];
  for(const [title,codes,key,unit,count] of boards){
    out+='<h5>'+title+(full?'有效样本前5':' · 摘要前3')+' · 覆盖 '+count+'/'+sector.member_count+'</h5>';
    if(!codes.length){out+='<p>事实不足，没有完整样本可排名。</p>';continue;}
    if(!full){
      out+=codes.slice(0,3).map(code=>{const r=lookup.get(code);return '<div>'+returnText(r.change_pct,r.name)+
        ' · '+(key==='five_day_pct'?'近5日 '+returnText(r.five_day_pct):fmt(r.turnover_yi,unit))+
        ' · 当日 '+returnText(r.change_pct)+(relative?' · '+escape(relativeText(r)):'')+'</div>';}).join('');
      continue;
    }
    out+='<div class="table-responsive"><table class="table table-hover"><thead><tr><th>股票</th><th>近5日</th><th>当日涨跌</th><th>成交额</th><th>成交活跃度</th>'+
      (relative?'<th>对应板块同窗 / 差值</th>':'')+'</tr></thead><tbody>';
    for(const code of codes){
      const r=lookup.get(code),both=sector.gain_codes.includes(code)&&sector.amount_codes.includes(code);
      out+='<tr><td>'+returnText(r.change_pct,r.name)+'<br><small>'+escape(code)+(both?' · 双榜':'')+'</small></td><td>'+returnText(r.five_day_pct)+
        '</td><td>'+returnText(r.change_pct)+'</td><td>'+fmt(r.turnover_yi,'亿元')+'</td><td>'+fmt(r.activity_ratio,'倍')+'</td>'+
        (relative?'<td>'+escape(relativeText(r))+'</td>':'')+'</tr>';
    }
    out+='</tbody></table></div>';
  }
  if(full)out+='<p>股票名按当日涨跌着色；当日与近5日百分比各自红涨绿跌，零与缺失为灰色。近5日按完整交易日收益复利；成交活跃度 = 当日成交额 / 此前5个完整交易日均额。缺日不补零，未覆盖样本不入对应榜；双榜不是买入排序或买入建议。成员来源仅提供最新名单，未证明报告日历史归属。</p>'+
    payload.notes.map(note=>'<p>'+escape(note)+'</p>').join('');
  else out+='<p>点曲线固定完整双榜与成交活跃度。</p>';
  return out;
};
const initFacts = root => {
  if (root.dataset.factsReady) return;
  const data=JSON.parse(root.querySelector('#sector-trend-view').textContent);
  const tracks=data.focus_track?[...data.tracks.filter(t=>t.track_id!==data.focus_track.track_id),data.focus_track]:data.tracks;
  const select=root.querySelector('#sector-trend-selector');
  const dateSelect=root.querySelector('#trend-date-selector');
  const panel=root.querySelector('#trend-fact-panel');
  const search=root.querySelector('#trend-sector-search');
  const results=root.querySelector('#trend-search-results');
  const status=root.querySelector('#trend-search-status');
  const range=root.querySelector('#trend-date-range');
  const previous=root.querySelector('#trend-date-previous');
  const next=root.querySelector('#trend-date-next');
  let matches=[], active=-1;
  const text=(id,value)=>{const node=root.querySelector('#trend-fact-'+id);if(node)node.textContent=value??'';};
  const reading=value=>data.reading_terms.reduce((s,[token,label])=>s.replaceAll(token,label),value);
  const number=(value,unit='%')=>value==null?'事实不足':(value>=0?'+':'')+Number(value).toFixed(2)+unit;
  chooseFact=(trackId,day)=>{
    const track=tracks.find(t=>t.track_id===trackId);
    if(!track){
      panel.hidden=true;
      const members=root.querySelector('#trend-member-content');
      if(members)members.textContent='暂无所选板块的成分榜。';
      root.dispatchEvent(new CustomEvent('trend-selection-change'));return;
    }
    panel.hidden=false;
    const row=track.path.find(r=>r.date===day)||track.path[track.path.length-1];
    select.value=track.track_id;
    dateSelect.replaceChildren(...track.path.map(r=>new Option(r.date+' · '+
      (r.background?'历史背景':r.date===track.started_date?'首次记录':'观察后复核'),r.date)));
    dateSelect.value=row.date;
    if(search)search.value=track.display_name||track.name;
    if(range){range.max=track.path.length-1;range.value=track.path.indexOf(row);}
    if(previous)previous.disabled=track.path.indexOf(row)===0;
    if(next)next.disabled=track.path.indexOf(row)===track.path.length-1;
    const dateLabel=root.querySelector('#trend-date-label');
    if(dateLabel)dateLabel.textContent=row.date+(row.date===data.target_date?' · 报告日':' · 历史节点');
    const selectedLabel=root.querySelector('#trend-selected-label');
    if(selectedLabel)selectedLabel.textContent=(track.display_name||track.name)+' · '+row.date;
    panel.dataset.trendTrack=track.track_id;panel.dataset.trendDate=row.date;
    root.querySelector('#sector-trend-group').value=track.method;
    root.querySelectorAll('[data-trend-sector]').forEach(button=>{
      button.setAttribute('aria-pressed',String(button.dataset.trendSector===track.track_id));
      const candidate=tracks.find(t=>t.track_id===button.dataset.trendSector)?.path.find(r=>r.date===row.date);
      const recent=button.querySelector('[data-trend-recent]');
      const other=tracks.find(t=>t.track_id===button.dataset.trendSector);
      if(recent)recent.textContent='5日 '+number(candidate?.five_day_pct)+
        (tracks.filter(t=>t.name===other?.name).length>1?' · '+button.dataset.trendSector.replace('index:',''):'');
    });
    root.querySelectorAll('[data-reading-control]').forEach(button=>button.setAttribute('aria-pressed',
      String(root.querySelector('#'+button.dataset.readingControl)?.value===button.dataset.readingValue)));
    const dateButtons=root.querySelector('#trend-date-buttons');
    if(dateButtons&&document.createElement){
      if(dateButtons.dataset.trackId!==track.track_id){
        const previous=[...dateButtons.querySelectorAll('button')];
        const focused=previous.includes(document.activeElement)?document.activeElement.dataset.trendDay:null;
        dateButtons.replaceChildren();dateButtons.dataset.trackId=track.track_id;
        for(const point of track.path){
          const button=document.createElement('button');button.type='button';button.className='reading-tag';
          button.dataset.trendDay=point.date;button.textContent=point.date.slice(5);
          button.setAttribute('aria-label',point.date+'，选择交易日');
          button.addEventListener('click',()=>chooseFact(track.track_id,point.date));dateButtons.append(button);
        }
        if(focused)[...dateButtons.querySelectorAll('button')].find(b=>b.dataset.trendDay===focused)?.focus({preventScroll:true});
      }
      dateButtons.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.trendDay===row.date)));
    }
    root.querySelector('#trend-focus-note').textContent=track.track_id===data.selected_track_id?
      data.focus_note:'当前自主选择观察：'+track.name+'；不改变报告主攻方向。';
    text('title',track.name+' · '+row.date);
    text('method',track.method+' · '+track.started_date+'首次记录');
    text('scope',row.date<track.started_date?
      '观察前历史背景：只用于理解此前走势，不计观察后的续证，也不是事前预测。':
      row.date===track.started_date?
      '首次记录：此前历史背景不能算作已验证一次；观察后的续证从下一交易日开始。':
      '观察后复核：按截至所选日期的滚动5日事实阅读，不使用之后的数据。');
    text('before',row.before);text('judgement',row.judgement);
    text('reason',reading(row.reason));text('next',reading(row.next_test));
    ['change_pct','five_day_pct','drawdown_pct'].forEach(key=>text(key,number(row[key])));
    text('five_day_excess_pp',number(row.five_day_excess_pp,'个百分点'));
    ['breadth','five_day_breadth'].forEach(key=>text(key,row[key]==null?'事实不足':(row[key]*100).toFixed(1)+'%'));
    const members=root.querySelector('#trend-member-content');
    if(members)members.innerHTML=memberMarkup(data,track.track_id,row.date,true);
    root.dispatchEvent(new CustomEvent('trend-selection-change'));
  };
  const closeSearch=()=>{if(results)results.hidden=true;search?.setAttribute('aria-expanded','false');
    search?.removeAttribute('aria-activedescendant');active=-1;};
  const showSearch=()=>{
    const term=search.value.trim().toLocaleLowerCase();
    matches=tracks.filter(t=>(t.name+' '+t.track_id).toLocaleLowerCase().includes(term));active=-1;
    results.replaceChildren();
    for(const [i,track] of matches.slice(0,12).entries()){
      const button=document.createElement('button');button.type='button';button.id='trend-result-'+i;
      button.setAttribute('role','option');button.setAttribute('aria-selected','false');
      button.textContent=track.display_name||track.name;
      button.addEventListener('click',()=>{chooseFact(track.track_id,dateSelect.value);closeSearch();search.focus();});
      results.append(button);
    }
    results.hidden=false;search.setAttribute('aria-expanded','true');
    if(status)status.textContent=matches.length?(matches.length>12?'匹配'+matches.length+'个，显示前12个；继续输入可缩小范围。':
      '匹配'+matches.length+'个；按上下键选择，回车查看。'):'本页精选范围没有匹配概念；不代表完整来源没有该概念，不以相似行业代替。';
  };
  if(search&&results){
    search.addEventListener('input',showSearch);
    search.addEventListener('focus',()=>{search.select();});
    search.addEventListener('keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();closeSearch();return;}
      if(event.key==='ArrowDown'||event.key==='ArrowUp'){
        event.preventDefault();if(results.hidden)showSearch();
        const count=Math.min(matches.length,12);if(!count)return;
        active=(active+(event.key==='ArrowDown'?1:-1)+count)%count;
        [...results.children].forEach((node,i)=>node.setAttribute('aria-selected',String(i===active)));
        search.setAttribute('aria-activedescendant','trend-result-'+active);
      }
      if(event.key==='Enter'){
        event.preventDefault();if(results.hidden)showSearch();
        const track=matches[active<0?0:active];if(track){chooseFact(track.track_id,dateSelect.value);closeSearch();}
      }
    });
    document.addEventListener('click',event=>{if(!event.target.closest('.trend-search'))closeSearch();});
  }
  const moveDate=step=>{
    const path=tracks.find(t=>t.track_id===select.value)?.path||[];
    const index=path.findIndex(r=>r.date===dateSelect.value)+step;
    if(path[index])chooseFact(select.value,path[index].date);
  };
  previous?.addEventListener('click',()=>moveDate(-1));
  next?.addEventListener('click',()=>moveDate(1));
  range?.addEventListener('input',()=>{
    const path=tracks.find(t=>t.track_id===select.value)?.path||[];
    if(path[Number(range.value)])chooseFact(select.value,path[Number(range.value)].date);
  });
  select.addEventListener('change',()=>chooseFact(select.value,dateSelect.value));
  dateSelect.addEventListener('change',()=>chooseFact(select.value,dateSelect.value));
  root.querySelectorAll('[data-trend-sector]').forEach(button=>button.addEventListener('click',()=>
    chooseFact(button.dataset.trendSector,dateSelect.value)));
  root.querySelectorAll('[data-reading-control]').forEach(button=>button.addEventListener('click',()=>{
    const control=root.querySelector('#'+button.dataset.readingControl);if(!control)return;
    control.value=button.dataset.readingValue;
    root.querySelectorAll('[data-reading-control]').forEach(peer=>peer.setAttribute('aria-pressed',
      String(root.querySelector('#'+peer.dataset.readingControl)?.value===peer.dataset.readingValue)));
    control.dispatchEvent(new Event('change',{bubbles:true}));
  }));
  document.addEventListener('concept-price-selection',event=>{
    if(tracks.some(t=>t.track_id===event.detail.trackId))chooseFact(event.detail.trackId,event.detail.day);
  });
  document.addEventListener('sector-track-selection',event=>{
    if(!tracks.some(t=>t.track_id===event.detail.trackId))return;
    chooseFact(event.detail.trackId,event.detail.day||data.target_date);closeSearch();
    const heading=root.querySelector('#trend-selection-heading');
    if(event.detail.scroll!==false){heading?.scrollIntoView({block:'start'});heading?.focus({preventScroll:true});}
  });
  document.querySelectorAll?.('[data-choice-track]').forEach(button=>button.addEventListener('click',()=>{
    document.dispatchEvent(new CustomEvent('sector-track-selection',{detail:{trackId:button.dataset.choiceTrack}}));
  }));
  root.dataset.factsReady='true';
  chooseFact(select.value,dateSelect.value);
};
const boot = () => {
  const root = document.querySelector('.sector-trend');
  if (!root) return;
  initFacts(root);
  if (root.dataset.ready || !window.echarts) return;
  const data = JSON.parse(root.querySelector('#sector-trend-view').textContent);
  const allTracks=data.focus_track?[...data.tracks.filter(t=>t.track_id!==data.focus_track.track_id),data.focus_track]:data.tracks;
  const group = root.querySelector('#sector-trend-group');
  const scope = root.querySelector('#trend-comparison-scope');
  const select = root.querySelector('#sector-trend-selector');
  const nodes = ['comparison','revisions','price','drawdown','breadth'].map(key => root.querySelector('#sector-trend-'+key));
  const [comparison,revisions,priceChart,drawdownChart,breadthChart] = nodes.map(node=>node?echarts.init(node):null);
  const charts=[comparison,revisions,priceChart,drawdownChart,breadthChart].filter(Boolean);
  const css=getComputedStyle(document.documentElement);
  const ink=css.getPropertyValue('--reader-text').trim()||'#25252b';
  const muted=css.getPropertyValue('--reader-muted').trim()||'#747281';
  const rule='rgba(100,96,120,.15)';
  const temperaturePieces=TEMPERATURE_BANDS;
  const colors=['#E73922','#07C160','#2364AA','#B000FF','#A62A19','#087B43','#174374','#7400A8','#E88373','#648DBA'];
  const colorFor=identity=>{let hash=0;for(const c of identity)hash=(hash*31+c.codePointAt(0))>>>0;return colors[hash%colors.length];};
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number=(value,unit='')=>value==null?'缺数据':Number(value).toFixed(2)+unit;
  const fontFamily='"Avenir Next","PingFang SC",sans-serif';
  const tooltip={confine:true,backgroundColor:'#fff',borderColor:rule,padding:10,
    textStyle:{color:ink,fontSize:12,fontFamily},extraCssText:'max-width:250px;white-space:normal;line-height:1.7'};
  const heading=(name,date)=>'<div style="font-weight:700">'+escape(name)+'</div><div style="color:'+muted+'">'+escape(date)+'</div>';
  const metric=(name,value)=>'<div>'+escape(name)+'：<b>'+escape(value)+'</b></div>';
  const label={color:muted,fontSize:11};
  const base={animation:false,backgroundColor:'transparent',color:colors,textStyle:{color:ink,fontFamily},
    legend:{type:'scroll',top:2,left:'center',selectedMode:true,textStyle:label},grid:{left:48,right:16,top:52,bottom:54}};
  const dates=data.trade_dates;
  const heat=data.heat||{dates:data.trade_dates,rows:data.tracks.map(t=>({name:t.name,track_id:t.track_id,
    temp:t.path.map(r=>r.temperature??-4),pct:t.path.map(r=>r.change_pct??null),selected:t.path.map(()=>false)}))};
  const selection=data.chart_selection;
  const hDates=heat.dates,hRows=selection?selection.heat_rows.map(item=>({
    ...heat.rows[item.index],readingGroups:item.groups,readingReturns:item.returns})):heat.rows;
  const heatNote=root.querySelector('#trend-heat-note');
  const monthIndices=new Map();
  dates.forEach((day,i)=>{const month=day.slice(0,7);if(!monthIndices.has(month))monthIndices.set(month,[]);monthIndices.get(month).push(i);});
  const monthLabels=new Map([...monthIndices].map(([month,indices])=>[indices[Math.floor((indices.length-1)/2)],month.slice(5)+'月']));
  const rowsByTrack=new Map(allTracks.map(t=>[t.track_id,new Map(t.path.map(r=>[r.date,r]))]));
  const rowAt=(track,day)=>rowsByTrack.get(track.track_id).get(day);
  const values=(track,key,scale=1)=>dates.map(day=>{const value=rowAt(track,day)?.[key];return value==null?null:value*scale;});
  const xAxis=()=>({type:'category',data:dates,boundaryGap:false,triggerEvent:true,
    axisLabel:{...label,formatter:v=>v.slice(5),hideOverlap:true,showMinLabel:true,showMaxLabel:true},
    axisLine:{lineStyle:{color:rule}},axisTick:{show:false}});
  const yAxis=name=>({type:'value',name,nameTextStyle:label,scale:true,splitNumber:3,
    axisLabel:label,splitLine:{lineStyle:{color:rule,type:'dashed'}}});
  const zoom=()=>[{type:'inside',filterMode:'none'},{type:'slider',filterMode:'none',height:15,bottom:4,showDetail:false}];
  let visible=[];
  const drawComparison=()=>{
    const featured=selection?.comparison.filter(item=>!scope || scope.value==='featured' || item.groups.includes(scope.value));
    visible=featured?featured.map(item=>allTracks.find(t=>t.track_id===item.track_id)).filter(t=>t?.method===group.value):
      allTracks.filter(t=>t.method===group.value);
    const note=root.querySelector('#trend-comparison-note');
    if(note)note.textContent='截至'+data.target_date+' · 当前显示'+visible.length+'个板块 · 相对全A累计差值（百分点）';
    comparison.setOption({...base,tooltip:{...tooltip,trigger:'item',formatter:p=>{
      const track=visible.find(t=>t.track_id===p.seriesId);
      if(!track)return '';
      const day=p.name,row=rowAt(track,day);
      return heading(track.name,day)+metric('相对全A累计差值',number(row?.excess_pp,'个百分点'));
    }},xAxis:xAxis(),yAxis:yAxis('累计差值（百分点）'),dataZoom:zoom(),
      series:visible.map((t,i)=>({id:t.track_id,name:t.display_name||t.name,type:'line',triggerLineEvent:true,symbolSize:4,connectNulls:false,smooth:true,
        itemStyle:{color:colorFor(t.track_id)},lineStyle:{color:colorFor(t.track_id),width:2.2},
        data:values(t,'excess_pp'),emphasis:{focus:'series'},
        markLine:i===0?{silent:true,symbol:'none',label:{show:false},data:[{yAxis:0}]}:undefined}))
      ,graphic:visible.length?[]:[{type:'text',left:'center',top:'middle',
        style:{text:selection?'该口径暂无符合近期走强或翘头的完整样本':
          (data.display_context?.focus_name||'当前主攻')+'：可比事实不足',fill:muted,fontSize:12}}]
    },true);
  };
  const fitCell=()=>{
    const width=nodes[1].parentElement?.clientWidth||0;
    if(!width) return 18;
    return Math.max(18,Math.min(34,Math.floor((width-170)/Math.max(1,hDates.length))-1));
  };
  let cellSize=fitCell();
  const resizeHeat=()=>{
    const node=nodes[1];
    const filled=hDates.length*(cellSize+1)+150;
    node.style.width=Math.max(filled,node.parentElement?.clientWidth||0)+'px';
    node.style.height=(hRows.length*cellSize+56)+'px';
    revisions.resize();
  };
  resizeHeat();
  const monthStarts=new Set(hDates.map((day,i)=>i===0||hDates[i-1].slice(0,7)!==day.slice(0,7)?i:-1));
  const heatMonthLabels=new Map();
  hDates.forEach((day,i)=>{const m=day.slice(0,7);if(!heatMonthLabels.has(m))heatMonthLabels.set(m,i);
    else heatMonthLabels.set(m,Math.max(heatMonthLabels.get(m),i));});
  const monthFirstIndex=[...heatMonthLabels.values()].map(last=>{
    let first=last;while(first>0&&hDates[first-1].slice(0,7)===hDates[last].slice(0,7))first-=1;return first;});
  const cells=hRows.flatMap((row,y)=>hDates.map((day,x)=>[x,y,row.temp[x]==null?-4:row.temp[x]]));
  const drawHeat=()=>revisions.setOption({...base,grid:{left:134,right:16,top:42,bottom:14},
    tooltip:{...tooltip,trigger:'item',transitionDuration:0,position:(point,params,dom,rect,size)=>{
      const scroller=nodes[1].parentElement;
      const left=scroller.scrollLeft+4,right=left+scroller.clientWidth-8;
      const box=nodes[1].getBoundingClientRect();
      const top=Math.max(4,4-box.top),bottom=Math.min(size.viewSize[1]-4,window.innerHeight-box.top-4);
      const [width,height]=size.contentSize;
      const cell=rect||{x:point[0]-cellSize/2,y:point[1]-cellSize/2,width:cellSize,height:cellSize};
      const x=Math.max(left,Math.min(cell.x+cell.width/2-width/2,right-width));
      const y=Math.max(top,Math.min(cell.y+cell.height/2-height/2,bottom-height));
      const candidates=[[x,cell.y-height-10],[x,cell.y+cell.height+10],
        [cell.x-width-10,y],[cell.x+cell.width+10,y]];
      return candidates.find(([a,b])=>a>=left&&a+width<=right&&b>=top&&b+height<=bottom)||candidates[0];
    },formatter:p=>{
      if(!p || !Array.isArray(p.value) || p.value.length<2) return '';
      const row=hRows[p.value[1]],day=hDates[p.value[0]];
      if(!row || !day) return '';
      const pct=row.pct[p.value[0]];
      return heading(row.name,day)+metric('当日涨跌',pct==null?'事实不足':number(pct,'%'))+
        '<div>点击固定板块与日期，在下方看路径</div>';
    }},
    xAxis:[{type:'category',data:hDates,position:'top',boundaryGap:true,triggerEvent:true,
      axisLabel:{...label,interval:0,hideOverlap:false,
        formatter:v=>v===data.target_date?'{target|'+v.slice(8)+'}':v.slice(8),
        rich:{target:{color:ink,fontWeight:800,backgroundColor:'#ECEBF0',padding:[2,1]}},fontSize:10}},
      {type:'category',data:hDates,position:'top',boundaryGap:true,offset:16,axisLine:{show:false},
        axisLabel:{...label,interval:0,hideOverlap:false,fontSize:10,
          formatter:(v,i)=>monthFirstIndex.includes(i)?v.slice(5,7)+'月':''}}],
    yAxis:{type:'category',data:hRows.map(r=>r.name+(r.readingGroups?' · '+r.readingGroups.map(g=>
      g.replace('日涨幅前5','涨').replace('日跌幅前5','跌')).join('/') :'')),inverse:true,
      axisLabel:{...label,width:125,overflow:'truncate',interval:0,fontSize:11},axisTick:{show:false},axisLine:{show:false}},
    visualMap:{type:'piecewise',dimension:2,show:false,
      selectedMode:false,pieces:temperaturePieces},
    series:[{type:'custom',data:cells,encode:{x:0,y:1,tooltip:2},
      renderItem:(params,api)=>{
        const point=api.coord([api.value(0),api.value(1)]),size=api.size([1,1]);
        const side=Math.max(3,Math.min(cellSize-1,Math.abs(size[0])-1,Math.abs(size[1])-1));
        const row=hRows[api.value(1)],day=hDates[api.value(0)];
        const picked=row.selected[api.value(0)];
        const cursor=day===root.querySelector('#trend-date-selector').value&&row.track_id===select.value;
        const stroke=cursor?'#2364AA':picked?ink:'transparent';
        return {type:'rect',shape:{x:point[0]-side/2,y:point[1]-side/2,width:side,height:side,r:1},
          style:{fill:api.visual('color'),stroke,lineWidth:cursor?3:picked?1.6:1},
          emphasis:{style:{stroke:ink,lineWidth:2}}};
      }
    }]
  },true);
  root.querySelector('#trend-matrix-scale').addEventListener('change',event=>{
    cellSize=Number(event.target.value);resizeHeat();drawHeat();
  });
  const drawDetails=()=>{
    const track=allTracks.find(t=>t.track_id===select.value);
    if(!track){
      const name=data.display_context?.focus_name||'当前主攻';
      root.querySelectorAll('[data-trend-name]').forEach(el=>el.textContent=name);
      root.querySelector('#sector-trend-current').textContent=name+' · 可比事实不足';
      [priceChart,drawdownChart,breadthChart].filter(Boolean).forEach(chart=>chart.setOption({animation:false,
        graphic:[{type:'text',left:'center',top:'middle',style:{text:name+'：缺少同名可比路径',fill:muted}}]},true));
      return;
    }
    const path=track.path,last=path[path.length-1];
    const selected=path.find(r=>r.date===root.querySelector('#trend-date-selector').value)||last;
    root.querySelectorAll('[data-trend-name]').forEach(el=>el.textContent=track.name);
    root.querySelector('#sector-trend-current').textContent=track.name+' · '+selected.date+' · '+selected.role+' · '+selected.progress;
    const line=(name,key,color,dashed=false)=>({name,type:'line',data:values(track,key),smooth:true,
      connectNulls:false,symbol:'none',itemStyle:{color},lineStyle:{color,width:2.2,type:dashed?'dashed':'solid'}});
    const axisTip=(title,render)=>({...tooltip,trigger:'axis',formatter:items=>{
      if(!items.length)return '';
      const row=path.find(r=>r.date===items[0].axisValue);
      return row?heading(track.name+' · '+title,row.date)+render(row):'';
    }});
    const displayName=track.display_name||track.name;
    const price=line(displayName,'level',colorFor(track.track_id));
    price.markLine={symbol:'none',silent:true,label:{formatter:'首次记录',position:'insideEndTop',fontSize:10},
      lineStyle:{type:'dashed',color:muted},data:[{xAxis:track.started_date}]};
    const benchmark=line('中证全指','market_level',muted,true);
    const marks=['回踩观察','价格与扩散恢复','仅价格修复'].map((name,i)=>({
      name,type:'scatter',symbol:['triangle','circle','emptyCircle'][i],symbolSize:11,
      itemStyle:{color:colors[i+2]},z:6,
      data:path.filter(r=>r.marker===name).map(r=>[r.date,r.level])
    }));
    priceChart.setOption({...base,legend:{...base.legend,data:[displayName,'中证全指']},
      xAxis:xAxis(),yAxis:yAxis('首日收盘 = 100'),
      tooltip:axisTip('走势',r=>metric(track.name,number(r.level))+metric('中证全指',number(r.market_level))+
        (r.marker?'<div>'+escape(r.marker)+'</div>':'')),
      series:[price,benchmark,...marks]},true);
    drawdownChart.setOption({...base,
      xAxis:xAxis(),yAxis:{...yAxis('回撤 %'),max:0},dataZoom:zoom(),
      tooltip:axisTip('回撤',r=>metric('距此前高点',number(r.drawdown_pct,'%'))),
      series:[{...line('距此前高点','drawdown_pct','#07C160'),areaStyle:{opacity:.12}}]},true);
    const breadth={...line('当日上涨占比','breadth','#E73922'),data:values(track,'breadth',100)};
    const average={...line('5日平均占比','five_day_breadth','#2364AA',true),data:values(track,'five_day_breadth',100)};
    breadth.markLine={symbol:'none',silent:true,label:{show:false},data:[{yAxis:50}],lineStyle:{color:muted,type:'dashed'}};
    breadthChart?.setOption({...base,legend:{...base.legend,data:['当日上涨占比','5日平均占比']},
      xAxis:xAxis(),yAxis:{...yAxis('上涨成员 %'),min:0,max:100,interval:50},dataZoom:zoom(),
      tooltip:axisTip('上涨面',r=>metric('当日上涨占比',number(r.breadth==null?null:r.breadth*100,'%'))+
        metric('5日平均占比',number(r.five_day_breadth==null?null:r.five_day_breadth*100,'%'))),
      series:[breadth,average],
      graphic:path.every(r=>r.breadth==null)?[{type:'text',left:'center',top:'middle',
        style:{text:'缺成员数据，暂不能判断扩散',fill:muted,fontSize:12}}]:[]
    },true);
  };
  group.addEventListener('change',drawComparison);
  scope?.addEventListener('change',drawComparison);
  root.addEventListener('trend-selection-change',()=>{drawComparison();drawDetails();drawHeat();});
  revisions.on('click',p=>{
    if(p.componentType==='xAxis') {chooseFact(select.value,p.value);return;}
    if(!Array.isArray(p.value)) return;
    const row=hRows[p.value[1]],day=hDates[p.value[0]];
    if(row.track_id){chooseFact(row.track_id,day);if(heatNote)heatNote.textContent='';}
    else if(heatNote){heatNote.textContent=row.name+' · '+day+'：不在观察名单，只显示当日涨跌 '+
      (row.pct[p.value[0]]==null?'事实不足':number(row.pct[p.value[0]],'%'));}
  });
  const comparisonDay=p=>p.name || (p.event && dates[Math.round(comparison.convertFromPixel(
    {gridIndex:0},[p.event.offsetX,p.event.offsetY])[0])]);
  comparison.on('mousemove',p=>{
    if(p.componentType!=='series' || p.dataIndex!=null)return;
    const track=p.seriesId?visible.find(t=>t.track_id===p.seriesId):visible[p.seriesIndex],day=comparisonDay(p);
    if(track && day && rowAt(track,day)?.excess_pp!=null){
      comparison.dispatchAction({type:'showTip',seriesIndex:p.seriesIndex,dataIndex:dates.indexOf(day)});
    }
  });
  comparison.on('click',p=>{
    if(p.componentType==='xAxis') {chooseFact(select.value,p.value);return;}
    const track=p.seriesId?visible.find(t=>t.track_id===p.seriesId):visible[p.seriesIndex];
    if(track && p.componentType==='series') chooseFact(track.track_id,comparisonDay(p));
  });
  [priceChart,drawdownChart,breadthChart].filter(Boolean).forEach(chart=>{
    chart.on('click',p=>{
      if(p.componentType==='xAxis') chooseFact(select.value,p.value);
      else if(p.componentType==='series') chooseFact(select.value,Array.isArray(p.value)?p.value[0]:p.name);
    });
    chart.getZr().on('click',event=>{
      const point=[event.offsetX,event.offsetY];
      if(!chart.containPixel({gridIndex:0},point))return;
      const index=Math.round(chart.convertFromPixel({gridIndex:0},point)[0]);
      if(dates[index]) chooseFact(select.value,dates[index]);
    });
  });
  drawComparison();drawDetails();drawHeat();
  root.dataset.ready='true';
  root.querySelector('.trend-fallback').hidden=true;
  const resize=()=>charts.forEach(chart=>chart.resize());
  window.addEventListener('resize',resize);
  new ResizeObserver(resize).observe(root);
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();
window.addEventListener('bear:echarts-ready',boot);
})();
