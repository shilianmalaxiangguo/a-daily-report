(() => {
  const boot=()=>{
    const root=document.querySelector('.concept-flow');
    if(!root||root.dataset.ready||!window.echarts)return;
    const data=JSON.parse(root.querySelector('#concept-flow-data').textContent);
    const viewNode=document.getElementById('sector-trend-view');
    const view=viewNode?JSON.parse(viewNode.textContent):null;
    const featured=new Set((view?.chart_selection?.heat_rows||[]).map(r=>view.heat.rows[r.index].track_id));
    const selector=root.querySelector('#concept-flow-selector');
    const node=root.querySelector('#concept-flow-matrix');
    const detail=root.querySelector('#concept-flow-detail');
    const chart=echarts.init(node);
    const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const fmt=v=>v==null?'缺失':(v>0?'+':'')+Number(v).toFixed(2)+'亿元';
    let visible=[],selected=null;
    const show=(row,x)=>{
      const day=data.dates[x],amount=row.values[x];
      selected={identity:row.track_id,day};
      detail.textContent=row.name+' · '+row.code+' · '+day+'：'+fmt(amount)+
        (amount==null?'；'+row.missing_reasons[x]:'')+'。净额不代表板块间转账。';
    };
    const draw=()=>{
      chart.dispatchAction({type:'hideTip'});
      visible=selector.value?data.rows.filter(r=>r.track_id===selector.value):
        data.rows.filter(r=>featured.has(r.track_id));
      if(!visible.length&&!selector.value)visible=data.rows.slice(0,10);
      const rows=visible;
      const buttons=root.querySelector('#concept-flow-buttons');
      if(buttons&&document.createElement){
        const choices=[null,...data.rows.filter(r=>featured.has(r.track_id)||r.track_id===selector.value)];
        const previous=[...buttons.querySelectorAll('button')];
        if(previous.length!==choices.length||previous.some((b,i)=>b.dataset.conceptFlow!==(choices[i]?.track_id||''))){
          const focused=previous.includes(document.activeElement)?document.activeElement.dataset.conceptFlow:null;
          buttons.replaceChildren();
          for(const row of choices){
            const button=document.createElement('button');button.type='button';button.className='reading-tag';
            const key=row?.track_id||'';button.dataset.conceptFlow=key;
            button.textContent=row?row.name:'近期比较样本';
            button.addEventListener('click',()=>{selector.value=key;selector.dispatchEvent(new Event('change'));});buttons.append(button);
          }
          if(focused!==null)[...buttons.querySelectorAll('button')].find(b=>b.dataset.conceptFlow===focused)?.focus({preventScroll:true});
        }
        buttons.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(selector.value===b.dataset.conceptFlow)));
      }
      node.style.width=Math.max(node.parentElement.clientWidth,230+data.dates.length*92)+'px';
      node.style.height=Math.max(150,visible.length*35+66)+'px';
      chart.resize();
      const peak=Math.max(1,...visible.flatMap(r=>r.values.filter(v=>v!=null).map(Math.abs)));
      const cells=rows.flatMap((r,y)=>data.dates.map((day,x)=>({value:[x,y],net_amount:r.values[x]})));
      chart.setOption({animation:false,backgroundColor:'transparent',
        textStyle:{fontFamily:'"Avenir Next","PingFang SC",sans-serif'},
        grid:{left:204,right:12,top:42,bottom:12},
        xAxis:{type:'category',data:data.dates,position:'top',axisLabel:{fontSize:11,interval:0},axisTick:{show:false},axisLine:{show:false}},
        yAxis:{type:'category',inverse:true,data:rows.map(r=>r.name+' · '+r.code),
          axisLabel:{fontSize:11,width:192,overflow:'truncate',interval:0},axisTick:{show:false},axisLine:{show:false}},
        tooltip:{trigger:'item',confine:true,formatter:p=>{
          const [x,y]=p.value,row=rows[y],day=data.dates[x];
          if(!row||!day)return '';
          return [escape(row.name+' · '+row.code),escape(day)+'：'+escape(fmt(row.values[x])),
            row.values[x]==null?escape(row.missing_reasons[x]):''].filter(Boolean).join('<br>');
        }},series:[{type:'custom',data:cells,encode:{x:0,y:1},renderItem:(params,api)=>{
          const x=api.value(0),y=api.value(1),row=rows[y];
          if(!row)return;
          const amount=row.values[x];
          const point=api.coord([x,y]),size=api.size([1,1]);
          const active=selected?.identity===row.track_id&&selected.day===data.dates[x];
          const fill=amount==null?'#e0dfe4':amount===0?'#f7f7f8':amount>0?'#E73922':'#07C160';
          return {type:'group',children:[{type:'rect',shape:{x:point[0]-size[0]/2+2,y:point[1]-size[1]/2+2,
            width:size[0]-4,height:size[1]-4,r:3},style:{fill,opacity:amount==null||amount===0?1:.25+.65*Math.sqrt(Math.abs(amount)/peak),
            stroke:active?'#25252b':'transparent',lineWidth:active?2:0}},
            {type:'text',style:{x:point[0],y:point[1],text:amount==null?'缺失':(amount>0?'+':'')+amount.toFixed(1),
              fill:'#25252b',font:'12px "Avenir Next","PingFang SC",sans-serif',align:'center',verticalAlign:'middle'}}]};
        }}]},true);
    };
    selector.addEventListener('change',()=>{
      if(!selector.value){selected=null;detail.textContent='当前展示近期比较样本；点选单元格查看对应概念与日期的净额。';}
      draw();
      const row=visible[0];if(row&&selector.value){show(row,data.dates.length-1);
        document.dispatchEvent(new CustomEvent('concept-price-selection',{detail:{trackId:row.track_id,day:data.dates.at(-1)}}));}});
    chart.on('click',p=>{
      if(p.componentType!=='series'||!Array.isArray(p.value))return;
      const [x,y]=p.value,row=visible[y];if(!row||!data.dates[x])return;show(row,x);draw();
      document.dispatchEvent(new CustomEvent('concept-price-selection',{detail:{trackId:row.track_id,day:data.dates[x]}}));
    });
    document.querySelector('.sector-trend')?.addEventListener('trend-selection-change',()=>{
      const panel=document.getElementById('trend-fact-panel');
      const day=panel?.dataset.trendDate,row=!panel?.hidden&&data.rows.find(r=>r.track_id===panel?.dataset.trendTrack);
      const x=data.dates.indexOf(day);
      if(row){
        if(selector.value||!visible.some(r=>r.track_id===row.track_id))selector.value=row.track_id;
        if(x>=0)show(row,x);
        else{selected=null;detail.textContent=row.name+' · '+row.code+' · '+day+
          '：所选日期不在本次净额窗口（'+data.dates[0]+' 至 '+data.dates.at(-1)+'），不以其他日期净额代替。';}
      }else{selected=null;detail.textContent='所选价格对象没有匹配的概念净额记录；未显示其他对象或日期的金额。';}
      draw();
    });
    draw();root.dataset.ready='true';
    window.addEventListener('resize',draw);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
  window.addEventListener('bear:echarts-ready',boot);
})();
