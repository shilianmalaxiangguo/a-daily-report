"""Dated factual rows and seal charts shared by current and historical readers."""
from __future__ import annotations

import math
import re
from datetime import date

from report.surface_wording import sanitize_user_visible_text


def _finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _fact_date(value):
    """Parse the two explicit date encodings accepted by frozen facts."""
    text = str(value or '').strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            return None
    if re.fullmatch(r'\d{8}', text):
        try:
            return date.fromisoformat(f'{text[:4]}-{text[4:6]}-{text[6:]}').isoformat()
        except ValueError:
            return None
    return None


def _frozen_sector_facts(
    snapshot,
    target_date,
    *,
    include_nonpositive=False,
    query_date_cutoff=None,
    require_provenance=False,
):
    """Read dated industry facts, never derive a trade from them."""
    data = {}
    if snapshot is not None:
        if not isinstance(snapshot, dict) or snapshot.get('date') != target_date:
            raise ValueError('板块快照日期不符，停止生成')
        data = snapshot.get('data')
        if not isinstance(data, dict) or any(
            data.get(key) not in (None, '', target_date)
            for key in ('target_date', 'source_date')
        ):
            raise ValueError('板块快照来源日期不符，停止生成')
    rows = []
    seen = {}
    source_rows = (('sector_change_up', data.get('sector_change_up') or []),)
    if include_nonpositive:
        source_rows += (('sector_change_down', data.get('sector_change_down') or []),)
    for list_name, raw_rows in source_rows:
        for raw in raw_rows:
            if not isinstance(raw, dict):
                continue
            # Each row must prove its date; the enclosing snapshot is insufficient.
            source = str(raw.get('data_source') or '').strip()
            declared_dates = []
            invalid_date = False
            for key in ('date', 'trade_date', 'source_date'):
                if raw.get(key):
                    parsed = _fact_date(raw.get(key))
                    if parsed is None:
                        invalid_date = True
                        break
                    declared_dates.append(parsed)
            dates = declared_dates
            query = _fact_date(raw.get('query_date')) if raw.get('query_date') else None
            if raw.get('query_date') and query is None:
                invalid_date = True
            if query_date_cutoff is None:
                query_valid = not query or query == target_date
            else:
                try:
                    query_day = date.fromisoformat(query) if query else None
                    query_valid = query_day is None or date.fromisoformat(target_date) <= query_day <= date.fromisoformat(query_date_cutoff)
                except ValueError:
                    query_valid = False
            if invalid_date or not query_valid:
                continue
            if source in ('tushare.ths_daily', 'iwencai.concept_index'):
                # 同花顺板块指数是目标日收盘事实；它没有行业汇总的宽度和成交额字段。
                if (not raw.get('trade_date')
                        or (require_provenance and any(not raw.get(key) for key in ('source_date', 'query_date')))
                        or any(value != target_date for value in dates)):
                    continue
            elif (any(not raw.get(key) for key in ('trade_date', 'source_date', 'query_date'))
                  or any(value != target_date for value in dates)
                  or source != 'tushare.daily.industry_aggregate'):
                continue
            name = sanitize_user_visible_text(str(raw.get('name') or '').strip())
            change = _finite_number(raw.get('change_pct', raw.get('zdf')))
            up = _finite_number(raw.get('up_count'))
            count = _finite_number(raw.get('stock_count'))
            turnover = _finite_number(raw.get('turnover_yi'))
            if source in ('tushare.ths_daily', 'iwencai.concept_index'):
                up = count = turnover = None
            if not name or change is None or (not include_nonpositive and change <= 0):
                continue
            identity = (source, str(raw.get('code') or name).strip()
                        if source in ('tushare.ths_daily', 'iwencai.concept_index') else name)
            fact = {key: value for key, value in raw.items() if key != 'rank'}
            previous = seen.get(identity)
            if previous is not None:
                if list_name in previous['lists']:
                    raise ValueError('板块来源存在重复记录，停止生成')
                if previous['fact'] != fact:
                    raise ValueError('板块涨跌榜事实不一致，停止生成')
                # Overlapping rankings may assign different ranks to one fact.
                previous['lists'].add(list_name)
                continue
            seen[identity] = {'lists': {list_name}, 'fact': fact}
            if (up is None or count is None or count <= 0 or up < 0 or up > count
                    or not up.is_integer() or not count.is_integer()):
                up = count = None
            rows.append({
                'name': name,
                'code': str(raw.get('code') or '').strip(),
                'trade_date': target_date,
                'change_pct': change,
                'up_count': int(up) if up is not None else None,
                'stock_count': int(count) if count is not None else None,
                'turnover_yi': turnover if turnover is not None and turnover >= 0 else None,
                'data_source': source,
            })
            if require_provenance:
                if 'source_date' in raw:
                    rows[-1]['source_date'] = _fact_date(raw['source_date'])
                if 'query_date' in raw:
                    rows[-1]['query_date'] = query
                rows[-1].update({key: raw[key] for key in ('available_at', 'retrieved_at') if key in raw})
    rows.sort(key=lambda row: (-row['change_pct'], row['name']))
    workflow = data.get('selection_workflow') or {}
    axis = workflow.get('sector_tournament_three_axis') if isinstance(workflow, dict) else None
    if axis is not None:
        from report.candidate_decision_evidence import validate_sector_tournament_three_axis
        if not validate_sector_tournament_three_axis(axis, target_date=target_date):
            axis = {}
    else:
        axis = {}
    return rows, axis


def seal_rows(rows, target_date):
    result = []
    seen = set()
    for row in rows:
        if str(row.get('trade_date', '')).replace('-', '') != target_date.replace('-', ''):
            raise ValueError('封板金额来源日期不符，停止生成')
        name = str(row.get('name') or '').strip()
        if not name or re.sub(r'\s+', '', name).upper().startswith(('ST', '*ST')) or row.get('limit') != 'U':
            continue
        try:
            amount = float(row.get('fd_amount'))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(amount) or amount <= 0:
            continue
        code = str(row.get('ts_code') or '').strip()
        if not code or code in seen:
            raise ValueError('封板金额股票代码缺失或重复，停止生成')
        seen.add(code)
        try:
            close = float(row.get('close'))
        except (TypeError, ValueError):
            close = None
        if close is not None and (not math.isfinite(close) or close <= 0):
            close = None
        hands_wan = (
            amount / close / 1000000
            if close is not None
            else None
        )
        if hands_wan is not None and not math.isfinite(hands_wan):
            hands_wan = None
        try:
            pct_chg = float(row.get('pct_chg'))
        except (TypeError, ValueError):
            pct_chg = None
        if pct_chg is not None and not math.isfinite(pct_chg):
            pct_chg = None
        result.append({
            'name': name,
            'code': code,
            'amount_yi': amount / 100000000,
            'hands_wan': hands_wan,
            'pct_chg': pct_chg,
            'close': close,
        })
    return sorted(result, key=lambda row: (-row['amount_yi'], row['code']))


def _text(soup, tag, text):
    element = soup.new_tag(tag)
    element.string = text
    return element


def _seal_section(soup, clean, target_date):
    section = soup.new_tag('section', attrs={'class': 'bear-chart-card'})
    copy = soup.new_tag('div', attrs={'class': 'bear-chart-copy'})
    eyebrow = _text(soup, 'span', '封单观察')
    eyebrow['class'] = 'bear-chart-eyebrow'
    copy.append(eyebrow)
    copy.append(_text(soup, 'h4', '当日封板金额排行（排除 ST、*ST）'))
    copy.append(_text(
        soup, 'p',
        f'{target_date} · 按收盘封单金额降序，柱尾标注金额与手数。'
        f'共 {len(clean)} 只，已排除 ST、*ST。',
    ))
    section.append(copy)
    if not clean:
        section.append(_text(soup, 'p', '目标日有效封板金额不足，暂无排行。'))
        return section
    controls = soup.new_tag('div', attrs={'class': 'seal-controls', 'role': 'group', 'aria-label': '封板金额展示数量'})
    for value, label in [('20', '前20只'), ('all', f'全部{len(clean)}只')]:
        button = _text(soup, 'button', label)
        button['type'] = 'button'
        button['data-seal-count'] = value
        button['aria-pressed'] = str(value == '20').lower()
        controls.append(button)
    section.append(controls)
    section.append(soup.new_tag('div', attrs={
        'id': 'seal-amount-chart', 'style': 'width:100%;height:670px',
        'role': 'img', 'aria-label': '当日封板金额降序柱状图',
    }))
    note = _text(soup, 'p',
        '来源：Tushare 同花顺涨停池封单金额；已按同日收盘价与涨停价核对。'
        '手数按封单金额 ÷ 收盘涨停价 ÷ 100 换算（1手=100股），'
        '按万手显示；价格缺失时手数待确认。缺失或非正金额不补零。')
    note['class'] = 'bear-chart-footnote'
    section.append(note)
    return section


_SEAL_SCRIPT = '''(() => {
const rows=ROWS; let showAll=false;
const css=getComputedStyle(document.documentElement);
const tone={text:css.getPropertyValue('--reader-text').trim()||'#2d1712',
  muted:css.getPropertyValue('--reader-muted').trim()||'#6c4537',
  line:css.getPropertyValue('--reader-line').trim()||'rgba(108,69,55,0.14)',
  red:css.getPropertyValue('--accent-red').trim()||'#e73922',
  green:'#07C160'};
const escapeText=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const formatUnit=(value,unit)=>{
  if(value>0&&value<0.000001)return '<0.000001'+unit;
  const digits=value>0&&value<0.005?Math.min(6,Math.ceil(-Math.log10(value))+1):2;
  return value.toFixed(digits)+unit;
};
const handsText=r=>r.hands_wan==null?'手数待确认':formatUnit(r.hands_wan,'万手');
const draw=()=>{
  const el=document.getElementById('seal-amount-chart');
  if(!window.echarts||!el)return;
  const visible=showAll?rows:rows.slice(0,20);
  const narrow=el.clientWidth<500;
  const labelText=r=>formatUnit(r.amount_yi,'亿')+(narrow?'\\n':' · ')+handsText(r);
  const measure=document.createElement('canvas').getContext('2d');
  measure.font=(narrow?11:12)+'px "Avenir Next", "PingFang SC", sans-serif';
  const right=Math.ceil(Math.max(...visible.flatMap(r=>labelText(r).split('\\n').map(t=>measure.measureText(t).width))))+18;
  el.style.height=Math.max(380,visible.length*(narrow?38:29)+90)+'px';
  const chart=echarts.getInstanceByDom(el)||echarts.init(el);
  chart.resize();
  chart.setOption({backgroundColor:'transparent',animationDuration:520,animationEasing:'cubicOut',
    textStyle:{color:tone.text,fontFamily:'"Avenir Next", "PingFang SC", sans-serif'},
    grid:{left:narrow?100:126,right,top:14,bottom:28,containLabel:false},
    xAxis:{type:'value',splitNumber:narrow?3:5,axisLabel:{color:tone.muted,formatter:value=>`${value}亿`},splitLine:{lineStyle:{color:tone.line,type:'dashed'}}},
    yAxis:{type:'category',inverse:true,data:visible.map((r,i)=>`${i+1}. ${r.name}`),axisLabel:{color:tone.text,fontSize:narrow?11:12,width:narrow?92:118,overflow:'truncate'},axisTick:{show:false},axisLine:{show:false}},
    tooltip:{trigger:'item',confine:true,appendToBody:false,backgroundColor:'rgba(255,255,255,0.96)',
      borderColor:tone.line,borderWidth:1,padding:[8,10],textStyle:{color:tone.text,fontSize:12,lineHeight:18},
      extraCssText:'max-width:260px;white-space:normal;box-shadow:0 10px 28px rgba(32,24,18,.12);border-radius:10px;',
      formatter:p=>{const r=p.data.item;return `<strong>${escapeText(r.name)}(${escapeText(r.code.split('.')[0])})</strong><br>封单金额：${escapeText(formatUnit(r.amount_yi,'亿'))}<br>封单手数（换算）：${escapeText(handsText(r))}<br>涨跌幅：${r.pct_chg==null?'待确认':(r.pct_chg>0?'+':'')+r.pct_chg.toFixed(2)+'%'}`}},
    series:[{name:'封单金额',type:'bar',barWidth:11,data:visible.map(r=>({value:r.amount_yi,item:r})),itemStyle:{borderRadius:[0,7,7,0],color:p=>p.data.item.pct_chg<0?tone.green:tone.red},
      label:{show:true,position:'right',color:tone.muted,fontSize:narrow?11:12,lineHeight:15,formatter:p=>labelText(p.data.item)}}]},true);
};
document.querySelectorAll('[data-seal-count]').forEach(button=>{
  button.addEventListener('click',()=>{
    showAll=button.dataset.sealCount==='all';
    document.querySelectorAll('[data-seal-count]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    draw();
  });
});
window.addEventListener('resize',draw);
window.addEventListener('bear:echarts-ready',draw);
draw();
})();'''
