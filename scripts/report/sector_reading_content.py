"""Current sector facts and optional charts, independent of account decisions."""
from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from report.sector_reading_primitives import _finite_number, _frozen_sector_facts, _text


SOURCE_LABELS = {
    'tushare.ths_daily': '同花顺板块指数',
    'iwencai.concept_index': '同花顺问财概念指数',
    'tushare.daily.industry_aggregate': '行业汇总（成交额加权）',
}
# Keep facts, not the retired tournament, calendar or threshold-based verdicts.
CHARTS = {
    't0_market_breadth': ('市场涨跌家数', 't0_market_breadth'),
    'market_turnover_trend': ('两市成交额', 'market_turnover_top50_trend'),
    'top50_share_trend': ('头部成交占比与创业板指', 'market_turnover_top50_trend'),
    'turnover_top30': ('成交额Top30', 'turnover_top30'),
    'cffex_position_trend': ('股指期货净空结构趋势', 'cffex_position_trend'),
    'lhb_net_flow': ('龙虎榜披露', 'lhb_net_flow'),
    'new_high_share_trend': ('创新高全A占比', 'new_high_share_trend'),
}

_CHART_NUMERIC_FIELDS = {
    't0_market_breadth': ('up_count', 'down_count', 'all_a_change_pct', 'new_high_share_pct'),
    'market_turnover_top50_trend': ('total_turnover', 'top50_share_pct', 'change_pct_point', 'top50_turnover', 'chinext_close'),
    'cffex_position_trend': ('member_net_short_notional_yi', 'member_net_short_change',
                             'top20_cross_section_net_short', 'top20_cross_section_change'),
    'turnover_top30': ('rank', 'turnover', 'change_pct'),
    'lhb_net_flow': ('rank', 'amount', 'abs_amount', 'change_pct'),
    'new_high_share_trend': ('new_high_count', 'new_high_share_pct'),
}
_CHART_METADATA_FIELDS = {
    't0_market_breadth': ('target_date', 'trade_date', 'source_date'),
    'market_turnover_top50_trend': ('target_date', 'trade_date', 'source_date', 'schema', 'method', 'trade_dates', 'artifact_hash'),
    'cffex_position_trend': ('target_date', 'trade_date', 'source_date', 'calendar', 'complete_day_count'),
    'turnover_top30': ('trade_date', 'source', 'complete', 'unit'),
    'lhb_net_flow': ('trade_date', 'source'),
    'new_high_share_trend': ('target_date', 'trade_date', 'source_date', 'schema', 'method', 'trade_dates',
                             'window_days', 'calendar', 'cache_repairs'),
}
_CHART_ITEM_FIELDS = {
    't0_market_breadth': ('date', 'up_count', 'down_count', 'flat_count', 'stock_count', 'sample_label',
                         'all_a_change_pct', 'new_high_share_pct'),
    'market_turnover_top50_trend': ('date', 'total_turnover', 'top50_share_pct', 'change_pct_point',
                                    'top50_turnover', 'chinext_close', 'sample_label', 'top50_sample_label',
                                    'share_provenance', 'chinext_provenance', 'top50_scope',
                                    'top50_market_amount_yi', 'top50_scope_evidence', 'sample_count', 'top50_codes', 'missing_reason',
                                    'coverage_count', 'coverage_provenance'),
    'cffex_position_trend': ('date', 'member_net_short_notional_yi', 'member_net_short_change',
                             'top20_cross_section_net_short', 'top20_cross_section_change'),
    'turnover_top30': ('rank', 'name', 'code', 'turnover', 'change_pct', 'sector',
                       'name_source', 'name_query_date', 'name_retrieved_at'),
    'lhb_net_flow': ('rank', 'name', 'code', 'sector', 'amount', 'abs_amount', 'change_pct', 'side', 'status', 'limit_status', 'reason'),
    'new_high_share_trend': ('date', 'new_high_count', 'new_high_share_pct', 'all_a_denominator',
                             'eligible_count', 'excluded_counts', 'new_high_codes', 'source_sha256', 'missing_reason'),
}
_PROVENANCE_FIELDS = ('trade_date', 'source_date', 'query_date', 'data_source', 'source',
                      'available_at', 'retrieved_at')


def source_note_text(value):
    """Keep the factual gap in reading copy; retain exception names in raw evidence."""
    return re.sub(r'[（(](?:[A-Za-z_][A-Za-z_0-9.]*)?(?:Error|Exception|Timeout)[）)]', '', str(value))


def _strict_number(value):
    """Accept finite numbers; never coerce booleans, blanks or placeholders."""
    if isinstance(value, bool) or value is None:
        return value if value is None else None
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else None
    if isinstance(value, str) and value.strip():
        try:
            number = float(value.strip())
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def _count(value):
    number = _strict_number(value)
    return int(number) if number is not None and number >= 0 and number == int(number) else None


def breadth_counts(stats):
    """Validate the same breadth sample in the headline and historical charts."""
    up, down = _count(stats.get('up_count')), _count(stats.get('down_count'))
    flat, count = _count(stats.get('flat_count')), _count(stats.get('stock_count'))
    valid = up is not None and down is not None
    if 'flat_count' in stats and flat is None:
        valid = False
    if 'stock_count' in stats:
        valid = valid and count is not None and count > 0 and flat is not None
        if valid:
            valid = up + down + flat == count
    if stats.get('sample_label') and count is None:
        valid = False
    return (up, down, count) if valid else (None, None, None)


def sector_facts(snapshot, target_date, *, recorded=False):
    if not isinstance(target_date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', target_date):
        raise ValueError('报告日期格式不符')
    parsed_target = date.fromisoformat(target_date)
    if parsed_target > datetime.now(ZoneInfo('Asia/Shanghai')).date():
        raise ValueError('报告日期不能晚于当前上海日期')
    # Do not even inspect legacy decisions when validating market facts.
    if snapshot is None:
        snapshot = {'date': target_date, 'data': {}}
    data = snapshot.get('data') if isinstance(snapshot, dict) else None
    if not isinstance(data, dict):
        raise ValueError('板块快照内容不完整')
    projection = {'date': snapshot.get('date'), 'data': {
        key: data.get(key) for key in ('target_date', 'source_date', 'sector_change_up', 'sector_change_down')
    }}
    rows, _ = _frozen_sector_facts(
        projection, target_date, include_nonpositive=True,
        query_date_cutoff=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat(),
        require_provenance=not recorded,
    )
    if recorded:
        # Older index records have their own fact date and source but did not
        # record query/source dates. Keep that absence, never synthesize them.
        raw_by_id = {(r.get('data_source'), str(r.get('code') or r.get('name'))): r
                     for key in ('sector_change_up', 'sector_change_down')
                     for r in data.get(key) or [] if isinstance(r, dict)}
        for row in rows:
            raw = raw_by_id.get((row['data_source'], row['code'] or row['name']), {})
            row.update({key: raw[key] for key in ('source_date', 'query_date', 'retrieved_at', 'available_at') if raw.get(key)})
            row['provenance_note'] = '历史留存值；未记录的来源日或查询日保持缺失'
        return [row for row in rows if recorded_fact(row, target_date)]
    return [row for row in rows if _valid_fact_times(
        row, parsed_target, date.fromisoformat(str(row['query_date']))
    )]


def recorded_fact(value, target_date):
    """Read a dated archived value without claiming complete upstream provenance."""
    from report.sector_reading_primitives import _fact_date
    if not isinstance(value, dict):
        return {}
    dates = [_fact_date(value[key]) for key in ('date', 'trade_date', 'source_date') if value.get(key)]
    if not dates or any(day != target_date for day in dates):
        return {}
    query = _fact_date(value.get('query_date')) if value.get('query_date') else None
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date()
    if value.get('query_date') and (query is None or not target_date <= query <= today.isoformat()):
        return {}
    if not _valid_fact_times(value, date.fromisoformat(target_date), date.fromisoformat(query) if query else None):
        return {}
    return value


def _valid_fact_times(value, fact_day, query_day):
    """Check supplied timestamps without inventing missing publication times."""
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    timestamps = {}
    try:
        for field in ('available_at', 'retrieved_at'):
            if not value.get(field):
                continue
            stamp = datetime.fromisoformat(str(value[field]))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=ZoneInfo('Asia/Shanghai'))
            stamp = stamp.astimezone(ZoneInfo('Asia/Shanghai'))
            if stamp.date() < fact_day or (query_day is not None and stamp.date() > query_day) or stamp > now:
                return False
            if field == 'retrieved_at' and query_day is not None and stamp.date() != query_day:
                return False
            timestamps[field] = stamp
        return not (len(timestamps) == 2 and timestamps['available_at'] > timestamps['retrieved_at'])
    except (TypeError, ValueError, OverflowError):
        return False


def dated_reading_fact(value, target_date, *, required):
    """Fact dates stay on target; a later retrieval is not a later market fact."""
    if not isinstance(value, dict) or any(not value.get(key) for key in required):
        return {}
    try:
        target = date.fromisoformat(target_date)
        fact_dates = [date.fromisoformat(str(value[key])) for key in ('date', 'trade_date', 'source_date') if value.get(key)]
        query = date.fromisoformat(str(value['query_date']))
        if (fact_dates and all(day == target for day in fact_dates)
                and isinstance(value.get('data_source'), str) and value['data_source'].strip()
                and target <= query <= datetime.now(ZoneInfo('Asia/Shanghai')).date()
                and _valid_fact_times(value, target, query)):
            return value
    except (KeyError, TypeError, ValueError):
        pass
    return {}


def _table(soup, headings, rows):
    wrapper = soup.new_tag('div', attrs={'class': 'sector-daily-facts'})
    table = soup.new_tag('table')
    head = soup.new_tag('thead')
    tr = soup.new_tag('tr')
    for label in headings:
        tr.append(_text(soup, 'th', label))
    head.append(tr)
    table.append(head)
    body = soup.new_tag('tbody')
    for values in rows:
        tr = soup.new_tag('tr')
        for value in values:
            tr.append(_text(soup, 'td', str(value)))
        body.append(tr)
    table.append(body)
    wrapper.append(table)
    return wrapper


def chart_evidence(source_html, target_date, excluded=(), *, recorded=False, snapshot_payload=None):
    """Return a shell containing only dated, selected chart facts and rendering code."""
    shell = BeautifulSoup(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" '
                          f'content="width=device-width,initial-scale=1"><title>{target_date}</title></head>'
                          '<body></body></html>', 'html.parser')
    if source_html is None and not snapshot_payload:
        return shell, []
    source = BeautifulSoup(source_html or '', 'html.parser')
    if source_html and (source.title is None or set(re.findall(r'\d{4}-\d{2}-\d{2}', source.title.get_text())) != {target_date}):
        raise ValueError('日报日期与目标日期不一致')
    payload_node = source.select_one('#bear-chart-payload')
    payload = json.loads(payload_node.get_text()) if payload_node else (snapshot_payload or {})
    if not isinstance(payload, dict):
        raise ValueError('图表事实格式不符')
    revised_high = (snapshot_payload or {}).get('new_high_share_trend')
    if isinstance(revised_high, dict) and revised_high.get('schema') == 'sector_new_high.v1':
        from report.sector_new_high import validate_new_high_series
        validate_new_high_series(revised_high, target_date)
        payload = {**payload, 'new_high_share_trend': revised_high}
    else:
        revised_high = None
    revised_top50 = (snapshot_payload or {}).get('market_turnover_top50_trend')
    if isinstance(revised_top50, dict) and revised_top50.get('schema') == 'sector_top50.v1':
        payload = {**payload, 'market_turnover_top50_trend': revised_top50}
    selected, kept = {}, []
    for key, (label, payload_key) in CHARTS.items():
        if key in excluded:
            continue
        card = source.select_one(f'[data-bear-chart-card="{key}"]')
        fact = payload.get(payload_key)
        split_history = False
        if key == 'new_high_share_trend' and not fact and 't0_market_breadth' in selected:
            breadth = selected['t0_market_breadth']
            if any(row.get('new_high_share_pct') is not None for row in breadth['items']):
                fact = {field: deepcopy(breadth[field]) for field in _PROVENANCE_FIELDS if field in breadth}
                fact.update(target_date=target_date, items=[{
                    **{field: deepcopy(row[field]) for field in ('date', *_PROVENANCE_FIELDS) if field in row},
                    'new_high_share_pct': row.get('new_high_share_pct'), 'new_high_count': None,
                } for row in breadth['items']])
                split_history = True
        if (source_html and card is None and not split_history and not (key == 'new_high_share_trend' and revised_high)) or not isinstance(fact, dict) or not fact.get('items'):
            continue
        source_name = str(fact.get('data_source') or fact.get('source') or '').strip()
        if not recorded and (not source_name or not fact.get('query_date')):
            raise ValueError('图表事实缺少来源或查询日期')
        source_name = source_name or '历史板块日报内嵌数值（上游来源未完整记录）'
        try:
            query = date.fromisoformat(str(fact['query_date'])) if fact.get('query_date') else None
        except (TypeError, ValueError) as error:
            raise ValueError('图表查询日期格式不符') from error
        # Fact dates remain capped at the report date; a later, honest retrieval
        # is retrospective evidence rather than a prediction made at the time.
        target_day = date.fromisoformat(target_date)
        if query is not None and (query < target_day or query > datetime.now(ZoneInfo('Asia/Shanghai')).date() \
                or not _valid_fact_times(fact, target_day, query)):
            raise ValueError('图表查询日期或可用时间与目标日不一致')
        if query is None and not _valid_fact_times(fact, target_day, None):
            raise ValueError('历史图表取得时间不符')
        declared = [fact[k] for k in ('target_date', 'trade_date', 'source_date') if fact.get(k)]
        if (not recorded and not fact.get('source_date')) or any(day != target_date for day in declared):
            raise ValueError('图表来源日期与目标日期不一致')
        if not isinstance(fact['items'], list) or any(not isinstance(row, dict) for row in fact['items']):
            raise ValueError('图表明细格式不符')
        timeline = payload_key in {'t0_market_breadth', 'market_turnover_top50_trend', 'cffex_position_trend', 'new_high_share_trend'}
        dates = []
        for row in fact['items']:
            row_dates = [row[k] for k in ('date', 'trade_date', 'source_date') if row.get(k)]
            query_dates = [row['query_date']] if row.get('query_date') else []
            if timeline and not row_dates:
                raise ValueError('图表时间序列缺少明细日期')
            for day in [*row_dates, *query_dates]:
                if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
                    raise ValueError('图表明细日期格式不符')
                date.fromisoformat(day)
            if len(set(row_dates)) > 1 or any(day > target_date for day in row_dates):
                raise ValueError('图表明细日期冲突或包含未来日期')
            if any(date.fromisoformat(day) > (query or datetime.now(ZoneInfo('Asia/Shanghai')).date()) for day in query_dates):
                raise ValueError('图表明细查询日期晚于本批整理日期')
            if row_dates and any(day < row_dates[0] for day in query_dates):
                raise ValueError('图表查询日期早于事实日期')
            row_day = date.fromisoformat(row_dates[0]) if row_dates else date.fromisoformat(target_date)
            row_query = date.fromisoformat(query_dates[0]) if query_dates else query
            if (row_query is not None and row_query < row_day) or not _valid_fact_times(row, row_day, row_query):
                raise ValueError('图表明细可用时间无法证明')
            if not timeline and any(day != target_date for day in row_dates):
                raise ValueError('图表排行不是目标日事实')
            dates.extend(row_dates[:1])
        if ((timeline and ((not recorded and target_date not in dates) or len(dates) != len(set(dates))))
                or (not recorded and not dates and not declared)):
            raise ValueError('图表事实缺少目标日期或包含未来日期')
        selected_fact = {field: deepcopy(fact[field]) for field in (*_CHART_METADATA_FIELDS[payload_key], *_PROVENANCE_FIELDS)
                         if field in fact}
        selected_fact['items'] = []
        for source_row in fact['items']:
            row = {field: deepcopy(source_row[field]) for field in (*_CHART_ITEM_FIELDS[payload_key], *_PROVENANCE_FIELDS)
                   if field in source_row}
            for field in _CHART_NUMERIC_FIELDS.get(payload_key, ()):
                if field in row:
                    row[field] = _strict_number(row[field])
            if payload_key == 't0_market_breadth':
                up, down, count = breadth_counts(source_row)
                row.update(up_count=up, down_count=down)
                if 'stock_count' in source_row:
                    row['stock_count'] = count
                    # When a declared denominator cannot be reconciled, do not
                    # leave the flat count looking like a valid partial sample.
                    row['flat_count'] = _count(source_row['flat_count']) if count is not None else None
                elif 'flat_count' in source_row:
                    row['flat_count'] = _count(source_row['flat_count'])
            # A normalized date is used by every renderer, regardless of which
            # equivalent source field supplied the original timeline.
            if timeline:
                row['date'] = (source_row.get('date') or source_row.get('trade_date')
                               or source_row.get('source_date'))
            selected_fact['items'].append(row)
        selected[payload_key] = selected_fact
        if timeline:
            selected[payload_key]['items'].sort(key=lambda row: row['date'])
        if payload_key == 'cffex_position_trend':
            selected[payload_key]['default_window'] = 60
        display_label = ('正文成交样本' if key == 'turnover_top30' and
                         (fact.get('source') == 'markdown_core_table' or fact.get('complete') is False)
                         else label)
        if key == 'new_high_share_trend' and fact.get('schema') == 'sector_new_high.v1':
            display_label = '创新高占比 · 当日有成交A股样本'
        # Rebuild the container rather than importing old captions, action prose
        # or arbitrary scripts hidden inside an otherwise valid chart card.
        card = shell.new_tag('section', attrs={'class': 'bear-chart-card', 'data-bear-chart-card': key})
        card.append(_text(shell, 'p', f'{display_label} · 事实截至 {target_date}'))
        if recorded and (query is None or not fact.get('source_date')):
            card.append(_text(shell, 'small', '历史留存数值，查询凭据不完整；不冒充已重新核验，也不因字段缺失抹掉原记录。'))
        if recorded and not dates and not declared:
            card.append(_text(shell, 'small', '本组留存在该日原板块页，逐项交易日期未记录；不补造日期。'))
        if key == 'cffex_position_trend':
            control = shell.new_tag('div', attrs={'class': 'bear-chart-window-control',
                'data-bear-chart-window-control': key, 'role': 'group', 'aria-label': '股指期货时间范围'})
            for size in (60, 20):
                button = _text(shell, 'button', f'{size}日')
                button.attrs.update({'type': 'button', 'data-window-size': str(size), 'aria-pressed': str(size == 60).lower()})
                control.append(button)
            card.append(control)
        frame = shell.new_tag('div', attrs={'class': 'bear-chart-frame'})
        chart = shell.new_tag('div', attrs={'data-bear-chart': key, 'class': 'bear-chart', 'aria-label': label})
        if key in {'turnover_top30', 'lhb_net_flow'}:
            frame['style'] = 'height:480px;overflow-y:auto'
            chart['style'] = f'height:{max(340, len(fact["items"]) * 36 + 48)}px'
        frame.append(chart)
        card.append(frame)
        notes = {
            't0_market_breadth': '缺失保留断点；涨跌家数和价格变化分别比较。',
            'market_turnover_trend': '成交额低于1.5万亿为紫色，1.5万亿至不足2万亿为绿色，2万亿及以上为红色；两条参考线仅供数值比较，成交额不等于资金净流入。',
            'top50_share_trend': '集中度与创业板指分轴显示；已核实的同范围日期才连线，历史范围未核实仅显示独立点。缺失不补零，不按固定占比判定机会，也不跨口径判断升降。',
            'cffex_position_trend': '默认最近60个有记录事实日，可切20日；历史缺报未补齐，不表示连续60个交易日。中信代客净空不等于机构自营方向。',
            'turnover_top30': (
                '目标日完整成交额排名，不作为买入名单。'
                if fact.get('source') != 'markdown_core_table' and fact.get('complete') is not False
                else '仅正文成交样本，未提供完整目标日榜单，不代表全市场前30；不作为买入名单。'
            ),
            'lhb_net_flow': '龙虎榜披露只覆盖上榜样本，不代表全市场资金，更不直接识别交易者意图。',
            'new_high_share_trend': '创新高独立展示；保留5%、2%、1%、0.2%数值参考线，不据此自动决定买卖。' +
                ('' if fact.get('schema') == 'sector_new_high.v1' else '历史旧占比可能使用固定5000分母，并非当日全A实际总数。'),
        }
        card.append(_text(shell, 'small', notes[key]))
        if key == 'cffex_position_trend':
            calendar = fact.get('calendar') or {}
            if calendar.get('verified') is True:
                count = len(calendar['trade_dates'])
                valid = fact['complete_day_count']
                card.contents[-1].string = (f'按真实开市日历显示最近{count}个交易日，三项事实齐全{valid}/{count}日；'
                    '可切20日，缺失保留断点，不用更早的日期凑数。中信代客净空不等于机构自营方向。')
        if key == 'top50_share_trend' and fact.get('schema') == 'sector_top50.v1':
            card.contents[-1].string = ('最近25个真实交易日；沪深同范围Top50成交额 / 沪深A股成交额，'
                '不含北交所。红线为占比（左轴），蓝线为创业板点位（右轴）；不表示因果关系。缺日断开，不补零。')
        if key == 'new_high_share_trend' and fact.get('schema') == 'sector_new_high.v1':
            card.append(_text(shell, 'small', fact['method']))
            gaps = [r for r in fact['items'] if r.get('missing_reason')]
            card.append(_text(shell, 'small',
                f'开放交易日历窗口{len(fact["items"])}日，已核对{len(fact["items"]) - len(gaps)}日；'
                '本图按同一口径重算，不拼接历史混合统计。'))
            if gaps:
                card.append(_text(shell, 'small', '缺失：' + '；'.join(
                    r['date'] + ' ' + source_note_text(r['missing_reason']) for r in gaps)))
        if split_history:
            card.append(_text(shell, 'small', '从原涨跌家数记录分离已留存的创新高占比；原始分母和逐日查询凭据未完整记录，创新高数量未留存。目标日缺失保持断点，不把旧值挪到今天。'))
        if key == 'new_high_share_trend' and not any(
                row.get('date') == target_date and row.get('new_high_share_pct') is not None
                for row in selected_fact['items']):
            card.append(_text(shell, 'small', f'{target_date}创新高占比未取得；仅展示已记录历史，不补零。'))
        # Chart-first pages show every available chart directly. Keep the
        # factual card and its provenance, but do not hide it behind an
        # accordion whose only purpose was to make room for retired prose.
        card['class'] = [*card.get('class', []), 'sector-chart-evidence']
        kept.append(card)
    if selected:
        vendor = Path(__file__).resolve().parents[2] / '.generated/vendor/echarts/echarts.min.js'
        if not vendor.is_file():
            raise ValueError('本地图表组件缺失；可用 - 只生成快照阅读页，不联网加载')
        loader = shell.new_tag('script', attrs={'data-bear-echarts-loader': 'inline'})
        loader.string = vendor.read_text(encoding='utf-8').replace('</script', '<\\/script')
        shell.body.append(loader)
        style = shell.new_tag('style')
        style.string = '.bear-chart-frame{height:360px;min-width:0}.bear-chart{width:100%;height:100%;min-width:0}'
        shell.head.append(style)
        node = shell.new_tag('script', attrs={'id': 'bear-chart-payload', 'type': 'application/json'})
        node.string = json.dumps(selected, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
        shell.body.append(node)
    return shell, kept


def chart_driver():
    """Load current factual chart functions without reading the old HTML template."""
    templates = Path(__file__).resolve().parents[1] / 'templates'
    functions = (templates / 'sector_market_chart_functions.js').read_text(encoding='utf-8')
    driver = (templates / 'sector_reading_charts.js').read_text(encoding='utf-8')
    return '(() => {' + chr(10) + functions + chr(10) + driver + chr(10) + '})();'


def historical_prices(soup, record, trend, target_date):
    """Optional numeric history: no old hypotheses, thresholds or action prose."""
    from report.sector_trend_tracking import validate_trend_evidence
    if not validate_trend_evidence(trend, record) or trend.get('target_date') != target_date:
        raise ValueError('历史价格事实与日期记录不符')
    detail = soup.new_tag('details')
    detail.append(_text(soup, 'summary', '已保存板块价格路径（历史样本）'))
    detail.append(_text(soup, 'p',
        f'来源：{trend["source"]}；取得于 {trend["retrieved_at"]}。'
        '只展示历史样本的数值，不自动续为当前观察名单；后选历史路径不是当时预测。'
        '缺失不补零，原判断保存在原始档案。'))
    detail['data-history-hash'] = trend['artifact_hash']
    for track in trend['tracks']:
        detail.append(_text(soup, 'h3', track['name']))
        detail.append(_text(soup, 'small', f'口径：{track["method"]}；历史样本标识：{track["track_id"]}'))
        values = []
        for point in track['path']:
            if point['date'] > target_date:
                raise ValueError('历史价格路径包含未来日期')
            values.append([point['date'], *[
                f'{_finite_number(point.get(key)):.2f}' if _finite_number(point.get(key)) is not None else '待确认'
                for key in ('change_pct', 'cumulative_pct', 'excess_pp', 'drawdown_pct')
            ]])
        detail.append(_table(soup, ['日期', '当日涨跌（%）', '累计涨跌（%）', '强于全A（百分点）', '回撤（%）'], values))
    return detail
