"""Offline sector reading from dated facts, without legacy account decisions."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from urllib.parse import urlsplit
import sys
from pathlib import Path

from bs4 import BeautifulSoup

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report.sector_reading_primitives import _finite_number, _text
from report.sector_reading_content import (
    SOURCE_LABELS, _count, sector_facts, chart_evidence, chart_driver,
    historical_prices,
    dated_reading_fact, breadth_counts,
    recorded_fact,
)
from report.sector_reading_history import historical_assets, historical_observation_section, choice_track_ids


FLOW_SOURCE_LABELS = {
    'tushare.moneyflow_ind_ths': '同花顺行业净额',
    'tushare.moneyflow+daily.industry_aggregate': '个股净额按行业汇总',
}


def sector_daily_output_path(full_html_path):
    path = Path(full_html_path)
    if '_完整版' not in path.stem:
        raise ValueError('完整版日报文件名不符，停止生成')
    return path.with_name(path.name.replace('_完整版', '_板块日报', 1))


def _dated_fact(value, target_date, *, required):
    return dated_reading_fact(value, target_date, required=required)


def market_background_facts(data, target_date, *, recorded=False):
    """Share the displayed date and number checks with entry validation."""
    fact = lambda value, required: (recorded_fact(value, target_date) if recorded else
                                    _dated_fact(value, target_date, required=required))
    index = fact(data.get('wind_a_alternative'), ('trade_date', 'source_date', 'query_date'))
    stats = fact(data.get('market_stats'), ('trade_date', 'source_date', 'query_date'))
    turnover = fact(data.get('turnover_data'), ('date', 'source_date', 'query_date'))
    amount = _finite_number(turnover.get('total_turnover_yi'))
    up, down, count = breadth_counts(stats)
    return {
        'change_pct': _finite_number(index.get('change_pct')),
        'up_count': up,
        'down_count': down,
        'stock_count': count,
        'amount_yi': amount if amount is not None and amount > 0 else None,
    }


def _sector_flow_facts(data, target_date, *, recorded=False):
    rows, seen = [], {}
    flow = data.get('sector_fund_flow') or {}
    fields = ('name', 'code', 'trade_date', 'source_date', 'query_date', 'data_source', 'available_at', 'retrieved_at',
              'change_pct', 'net_amount', 'net_buy_amount', 'net_sell_amount', 'turnover_yi', 'lead_stock',
              'stock_count', 'matched_stock_count')
    for raw in [*(flow.get('inflow') or []), *(flow.get('outflow') or [])]:
        value = (recorded_fact(raw, target_date) if recorded else
                 _dated_fact(raw, target_date, required=('trade_date', 'source_date', 'query_date')))
        if not value or not value.get('name') or value.get('data_source') not in FLOW_SOURCE_LABELS:
            continue
        amount = _finite_number(value.get('net_amount'))
        change = _finite_number(value.get('change_pct'))
        identity = (value.get('code') or value['name'], value['data_source'])
        signature = (amount, change, _count(value.get('stock_count')),
                     _count(value.get('matched_stock_count')))
        if identity in seen:
            if seen[identity] != signature:
                raise ValueError('同日板块资金存在矛盾记录')
            continue
        seen[identity] = signature
        row = {key: value[key] for key in fields if key in value}
        for key in ('net_buy_amount', 'net_sell_amount', 'turnover_yi'):
            if key in row:
                row[key] = _finite_number(row[key])
        for key in ('stock_count', 'matched_stock_count'):
            if key in row:
                row[key] = _count(row[key])
        row.update(net_amount=amount, change_pct=change)
        if amount is not None:
            rows.append(row)
    rows.sort(key=lambda row: row['net_amount'], reverse=True)
    return rows


def _industry_chart_groups(data, target_date, *, recorded=False):
    """Keep full industry facts in the snapshot, not in the reading page."""
    source_groups = {}
    fields = ('name', 'code', 'identity', 'index_type', 'data_source', 'trade_date', 'source_date',
              'query_date', 'retrieved_at', 'available_at', 'provenance_note')
    for raw in ((data.get('industry_background') or {}).get('rows') or []):
        value = (recorded_fact(raw, target_date) if recorded else
                 _dated_fact(raw, target_date, required=('trade_date', 'source_date', 'query_date')))
        if not value or not isinstance(value.get('name'), str) or not value['name'].strip():
            continue
        source = value.get('data_source')
        if (source not in SOURCE_LABELS or value.get('index_type') not in (None, 'I') or
                (source == 'tushare.ths_daily' and value.get('index_type') != 'I')):
            continue
        change = _finite_number(value.get('change_pct'))
        if change is None:
            continue
        row = {key: value[key] for key in fields if key in value}
        row['change_pct'] = change
        for key in ('close', 'turnover_rate', 'turnover_yi'):
            if key in value:
                row[key] = _finite_number(value[key])
        for key in ('stock_count', 'up_count', 'down_count'):
            if key in value:
                row[key] = _count(value[key])
        source_groups.setdefault(f'{source}:I', {'data_source': source, 'rows': {}})
        previous = source_groups[f'{source}:I']['rows']
        identity = str(value.get('code') or value['name'])
        if identity in previous:
            old = previous[identity]
            signature = lambda item: tuple(item.get(key) for key in (
                'name', 'code', 'identity', 'index_type', 'data_source', 'trade_date', 'source_date',
                'change_pct', 'close', 'turnover_rate', 'turnover_yi', 'stock_count', 'up_count', 'down_count'))
            if signature(old) != signature(row):
                raise ValueError('同日行业背景存在矛盾记录')
            continue
        previous[identity] = row
    result = {}
    for key, group in source_groups.items():
        rows = list(group['rows'].values())
        up = sorted((row for row in rows if row['change_pct'] > 0),
                    key=lambda row: (-row['change_pct'], row['name'], row.get('code') or ''))[:5]
        down = sorted((row for row in rows if row['change_pct'] < 0),
                      key=lambda row: (row['change_pct'], row['name'], row.get('code') or ''))[:5]
        result[key] = {
            'data_source': group['data_source'],
            'label': ('同花顺行业指数' if group['data_source'] == 'tushare.ths_daily'
                      else SOURCE_LABELS[group['data_source']]),
            'total_count': len(rows),
            'positive_count': sum(row['change_pct'] > 0 for row in rows),
            'negative_count': sum(row['change_pct'] < 0 for row in rows),
            'flat_count': sum(row['change_pct'] == 0 for row in rows),
            'up': up,
            'down': down,
        }
    return result


def _sector_chart_section(soup, data, target_date, rows, *, recorded=False):
    section = soup.new_tag('section', attrs={'class': 'sector-daily-section sector-chart-surface',
                                             'id': 'daily-sectors'})
    section.append(_text(soup, 'h2', '板块图表'))
    grouped = {}
    for row in rows:
        grouped.setdefault(row['data_source'], []).append(row)
    background = market_background_facts(data, target_date, recorded=recorded)
    payload = {'target_date': target_date, 'all_a_change_pct': background['change_pct'],
               'change_groups': grouped, 'flow': _sector_flow_facts(data, target_date, recorded=recorded),
               'industry_groups': _industry_chart_groups(data, target_date, recorded=recorded)}
    flow_groups = payload['flow_groups'] = {}
    for row in payload['flow']:
        flow_groups.setdefault(row['data_source'], []).append(row)
    for source, group in grouped.items():
        source_label = ('同花顺概念指数' if source == 'tushare.ths_daily' and data.get('sector_universe') == 'concept'
                        else SOURCE_LABELS.get(source, source))
        chart = soup.new_tag('section', attrs={'class': 'bear-chart-card sector-daily-chart-card'})
        chart.append(_text(soup, 'h3', source_label))
        chart.append(soup.new_tag('div', attrs={'class': 'sector-daily-chart-frame'}))
        node = soup.new_tag('div', attrs={'class': 'sector-daily-chart', 'data-sector-daily-chart': 'change',
                                          'data-sector-source': source, 'role': 'img',
                                          'aria-label': f'{SOURCE_LABELS.get(source, source)}目标日涨跌幅'})
        node['style'] = f'height:{max(360, len(group) * 30 + 82)}px'
        chart.select_one('.sector-daily-chart-frame').append(node)
        chart.append(_text(soup, 'small', f'事实日 {target_date} · 榜单 {len(group)} 条，非全市场排名 · 涨跌幅（%），红涨绿跌'))
        section.append(chart)
    for source, flow_rows in flow_groups.items():
        label = FLOW_SOURCE_LABELS[source]
        chart = soup.new_tag('section', attrs={'class': 'bear-chart-card sector-daily-chart-card'})
        chart.append(_text(soup, 'h3', label))
        frame = soup.new_tag('div', attrs={'class': 'sector-daily-chart-frame sector-flow-chart-frame'})
        node = soup.new_tag('div', attrs={'class': 'sector-daily-chart', 'data-sector-daily-chart': 'flow',
                                          'data-sector-source': source, 'role': 'img',
                                          'aria-label': f'{label}排序图'})
        node['style'] = f'height:{max(360, len(flow_rows) * 30 + 82)}px'
        frame.append(node)
        chart.append(frame)
        chart.append(_text(soup, 'small', f'事实日 {target_date} · {label}（亿元），不是成交额 · '
                           f'榜单 {len(flow_rows)} 条，非全市场排名 · 红为正、绿为负 · '
                           '条目来源、日期与样本字段见悬浮详情；未记录处会明确标出'))
        section.append(chart)
    for group_key, group in payload['industry_groups'].items():
        if not group['up'] and not group['down']:
            continue
        wrapper = soup.new_tag('section', attrs={'class': 'industry-background-charts',
                                                  'data-industry-group': group_key})
        wrapper.append(_text(soup, 'h3', f'{group["label"]} · 涨跌两端样本'))
        wrapper.append(_text(soup, 'small', f'{group["total_count"]} 条行业样本 · 涨跌两端各取最多5条 · '
                             '分类层级可能重叠，不代表市场广度；不与概念混排。'))
        for direction, label, sample in (('up', '涨幅前5', group['up']), ('down', '跌幅前5', group['down'])):
            if not sample:
                continue
            card = soup.new_tag('section', attrs={'class': 'bear-chart-card sector-daily-chart-card industry-chart-card'})
            card.append(_text(soup, 'h4', label))
            frame = soup.new_tag('div', attrs={'class': 'sector-daily-chart-frame industry-chart-frame'})
            node = soup.new_tag('div', attrs={'class': 'sector-daily-chart', 'data-sector-daily-chart': 'industry',
                                              'data-industry-group': group_key, 'data-industry-direction': direction,
                                              'role': 'img', 'aria-label': f'{group["label"]}{label}图'})
            node['style'] = f'height:{max(220, len(sample) * 34 + 70)}px'
            frame.append(node)
            card.append(frame)
            card.append(_text(soup, 'small', f'事实日 {target_date} · {label} · 红涨绿跌'))
            wrapper.append(card)
        section.append(wrapper)
    if not grouped and not flow_groups and not payload['industry_groups']:
        section.append(_text(soup, 'small', '目标日无可核对的板块涨跌或净额图表。'))
    if data.get('sector_universe') == 'concept':
        missing = (data.get('concept_directory') or {}).get('missing_price_codes') or []
        inputs = ((data.get('reading_sector_history') or {}).get('trend') or {}).get('price_inputs') or {}
        if missing and inputs:
            latest = {}
            for row in inputs.get('rows', []):
                if row['ts_code'] in missing and row.get('close') is not None:
                    latest[row['ts_code']] = max(latest.get(row['ts_code'], ''), row['trade_date'])
            # Summarize by last visible date; a code-by-code list buries the reading.
            groups = {}
            for code in missing:
                groups.setdefault(latest.get(code), []).append(code)
            parts = [f'{len(codes)}个最后可见价格在{day}' if day else f'{len(codes)}个没有可用历史价格'
                     for day, codes in sorted(groups.items(), key=lambda item: item[0] or '', reverse=True)]
            if len(missing) <= 3:
                parts = [f'{code}最后可见价格在{latest[code]}' if code in latest else f'{code}没有可用历史价格'
                         for code in missing]
            section.append(_text(soup, 'small', f'{len(missing)}个概念未取得{target_date}行情：' + '；'.join(parts) +
                '。不以其他代码或旧价补成当日行情。'))
        section.append(_text(soup, 'small', '概念是阅读优先顺序，不是买入指令。指数不能直接成交；'
                            '没有核实ETF或篮子映射、成本和成交条件时，不以指数收益冒充可实现收益。'))
    payload_node = soup.new_tag('script', attrs={'type': 'application/json', 'id': 'sector-visualization-payload'})
    payload_node.string = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    section.append(payload_node)
    return section, bool(grouped or flow_groups or payload['industry_groups'])



def _bootstrap_components(soup, main):
    for table in main.select('table'):
        table['class'] = [*table.get('class', []), 'table', 'table-hover']
        if table.parent.name == 'div':
            table.parent['class'] = [*table.parent.get('class', []), 'table-responsive']
        else:
            table.wrap(soup.new_tag('div', attrs={'class': 'table-responsive'}))
    for detail in list(main.select('details')):
        summary = detail.find('summary', recursive=False)
        if summary is None:
            continue
        detail['class'] = [*detail.get('class', []), 'accordion-item']
        summary['class'] = [*summary.get('class', []), 'accordion-header']
        body = soup.new_tag('div', attrs={'class': 'accordion-body'})
        for child in list(detail.contents):
            if child is not summary:
                body.append(child.extract())
        detail.append(body)
        icon = soup.new_tag('svg', attrs={'class': 'accordion-icon', 'viewBox': '0 0 16 16',
                                         'aria-hidden': 'true', 'fill': 'none', 'stroke': 'currentColor'})
        icon.append(soup.new_tag('path', attrs={'d': 'm2 5 6 6 6-6', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}))
        summary.append(icon)
        detail.wrap(soup.new_tag('div', attrs={'class': 'accordion accordion-gap'}))
    for button in main.select('button[data-window-size], button[data-seal-count]'):
        button['class'] = [*button.get('class', []), 'btn-outline', 'theme-primary', 'btn-sm']
    for card in main.select('.bear-chart-card'):
        card['class'] = [*card.get('class', []), 'card', 'card-body']


_TEMPLATES = Path(__file__).resolve().parents[1] / 'templates'
_STYLE = (_TEMPLATES / 'daily_report_reading.css').read_text(encoding='utf-8')
_BOOTSTRAP = (_TEMPLATES / 'vendor' / 'bootstrap-6.0.0-alpha.1.min.css').read_text(encoding='utf-8')

def render_sector_daily(source_html, target_date, *, snapshot, seal_rows=(), full_report_name=None,
                        previous_snapshot=None, previous_record=None,
                        origin='historical_rebuild', hypothesis_record=None, tracked_evidence=(), trend_evidence=None,
                        chart_facts=None, sector_caliber_label='目标日冻结板块榜单',
                        excluded_items=(), caliber_note=None, leader_board=None, historical_snapshot=False):
    # Legacy keyword arguments remain accepted by historical callers, but they
    # cannot supply a current decision, inherited watchlist, or automatic query.
    snapshot = snapshot or {'date': target_date, 'data': {}}
    assets = historical_assets(source_html, snapshot, target_date)
    if not assets and not source_html and snapshot['data'].get('reading_sector_history'):
        from report.sector_reading_history import evidence_hash, numeric_trend_view, validated_flow
        assets = snapshot['data']['reading_sector_history']
        if (assets.get('target_date') != target_date or assets.get('source_sha256') !=
                evidence_hash({k: v for k, v in assets.items() if k != 'source_sha256'})):
            raise ValueError('板块历史事实日期或指纹不符')
        numeric_trend_view(assets['trend'], target_date)
        if assets.get('flow'):
            validated_flow(assets['flow'], target_date)
        if assets.get('concept_flow'):
            from report.sector_concept_flow import validate_concept_flow
            validate_concept_flow(assets['concept_flow'], target_date)
    recorded = bool(assets) or historical_snapshot
    rows = sector_facts(snapshot, target_date, recorded=recorded)
    data = snapshot['data']
    if data.get('reading_market_returns'):
        from report.market_returns import validate_market_returns
        validate_market_returns(data['reading_market_returns'], target_date)
    choice = data.get('reading_choice')
    if choice:
        from report.sector_choice import validate_sector_choice
        validate_sector_choice(choice, data, target_date)
    plan = None
    if data.get('reading_small_cap_plan') is not None:
        from report.small_cap_rotation import SCHEMA, validate_plan
        saved_plan = validate_plan(data['reading_small_cap_plan'], target_date)
        if saved_plan['schema'] == SCHEMA:
            plan = saved_plan
    from report.sector_snapshot_charts import snapshot_chart_payload
    native_charts = snapshot_chart_payload(data, target_date)
    soup, chart_cards = chart_evidence(source_html, target_date, excluded_items, recorded=recorded,
                                      snapshot_payload=native_charts)
    main = soup.new_tag('main', attrs={'class': 'container sector-daily', 'id': 'daily-content'})
    header = soup.new_tag('header', attrs={'class': 'daily-header'})
    edition = soup.new_tag('div', attrs={'class': 'daily-edition', 'aria-hidden': 'true'})
    edition.append(_text(soup, 'span', target_date[:4]))
    edition.append(_text(soup, 'b', target_date[8:10]))
    edition.append(_text(soup, 'small', target_date[5:7] + '月'))
    header.append(edition)
    dateline = soup.new_tag('time', attrs={'datetime': target_date})
    dateline.string = target_date
    header.append(dateline)
    header.append(_text(soup, 'h1', 'A股日报'))
    header.append(_text(soup, 'p', '当前主策略：小盘轮换 v0.3。板块与市场图表只提供背景事实。'))
    main.append(header)
    if plan:
        from report.small_cap_rotation import render_plan
        main.append(render_plan(soup, plan))
    else:
        missing_plan = soup.new_tag('section', attrs={'id': 'daily-plan', 'class': 'sector-daily-section dash-section'})
        missing_plan.append(_text(soup, 'h2', '执行计划：小盘轮换 v0.3'))
        missing_plan.append(_text(soup, 'p', '小盘计划尚缺当前版本的冻结名单或必要数据，本页不补造名单与账户动作。'))
        main.append(missing_plan)
    if choice:
        from report.sector_choice import render_sector_choice
        from report.sector_alpha import build_alpha_comparison, render_alpha_comparison
        alpha = build_alpha_comparison(assets['trend'], target_date, choice,
            market_history=data.get('reading_member_history')) if assets else None
        main.append(render_alpha_comparison(soup, alpha, choice) if alpha else render_sector_choice(soup, choice))
    sector_charts, has_sector_charts = _sector_chart_section(soup, data, target_date, rows, recorded=recorded)
    main.append(sector_charts)
    if assets:
        main.append(historical_observation_section(soup, assets, target_date,
                    preferred_track_id=(choice.get('primary') or {}).get('track_id') if choice else None,
                    retained_track_ids=choice_track_ids(choice)))
    archive = soup.new_tag('section', attrs={'class': 'sector-daily-section sector-chart-surface',
                                             'id': 'daily-evidence'})
    archive.append(_text(soup, 'h2', '市场图表'))
    for card in chart_cards:
        archive.append(card)
    from report.sector_reading_content import CHARTS
    available = {node['data-bear-chart'] for card in chart_cards for node in card.select('[data-bear-chart]')}
    missing = [label for key, (label, _) in CHARTS.items() if key not in available]
    if missing:
        archive.append(_text(soup, 'small', '本次尚缺：' + '、'.join(missing) + '。不画空图、不用别日数字替代；历史窗口不足时仅展示已留存日期。'))
    from report.sector_reading_primitives import _seal_section, seal_rows as clean_seal_rows
    clean_seals = clean_seal_rows(data.get('limit_list_d') or [], target_date)
    seal = _seal_section(soup, clean_seals, target_date)
    seal['id'] = 'daily-seal-amount'
    archive.append(seal)
    if trend_evidence is not None:
        archive.append(historical_prices(soup, hypothesis_record, trend_evidence, target_date))
    if not chart_cards and trend_evidence is None:
        archive.append(_text(soup, 'small', '未提供可核对的市场图表或历史路径；不生成空图，不联网补查。'))
    main.append(archive)
    footer = soup.new_tag('footer')
    footer.append(_text(soup, 'small', f'行情截至{target_date}；历史修订不冒充当时预测。'))
    facts_node = soup.new_tag('script', attrs={'type': 'application/json', 'id': 'sector-reading-facts'})
    facts_node.string = json.dumps({'target_date': target_date, 'rows': rows},
                                   ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    footer.append(facts_node)
    if assets:
        provenance = soup.new_tag('script', attrs={'type': 'application/json', 'id': 'sector-baseline-provenance'})
        provenance.string = json.dumps({k: assets[k] for k in ('target_date', 'source_sha256', 'record_hash')})
        footer.append(provenance)
        from report.sector_reading_history import evidence_hash
        retained = {'schema': 'sector_reading_archive.v2', 'target_date': target_date,
                    'snapshot_hash': evidence_hash(data)}
        if data.get('reading_sector_history') is not None:
            retained['assets_hash'] = evidence_hash(assets)
        else:
            # Older snapshots have no native archive; their page is the only
            # preserved source. Keep it readable through repeated replays.
            retained['assets'] = assets
        retained['view_hashes'] = {key: evidence_hash(json.loads(node.string))
            for key in ('sector-trend-view', 'concept-flow-data')
            if (node := main.select_one('#' + key)) is not None}
        payload_node = soup.select_one('#bear-chart-payload')
        retained['chart_hash'] = evidence_hash(json.loads(payload_node.string) if payload_node else {})
        retained['artifact_hash'] = evidence_hash(retained)
        node = soup.new_tag('script', attrs={'type': 'application/json', 'id': 'sector-retained-history'})
        node.string = json.dumps(retained, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
        footer.append(node)
    if full_report_name:
        url = urlsplit(full_report_name)
        if (url.scheme or url.netloc or url.query or url.fragment or '\\' in full_report_name
                or Path(full_report_name).is_absolute() or not full_report_name.endswith('.html')):
            raise ValueError('历史来源链接须为本地相对 HTML 路径')
    main.append(footer)
    _bootstrap_components(soup, main)
    soup.body.append(main)
    if (assets or clean_seals or has_sector_charts) and not soup.select_one('[data-bear-echarts-loader]'):
        vendor = _TEMPLATES.parent.parent / '.generated/vendor/echarts/echarts.min.js'
        loader = soup.new_tag('script', attrs={'data-bear-echarts-loader': 'inline'})
        loader.string = vendor.read_text(encoding='utf-8').replace('</script', '<\\/script')
        soup.body.insert(0, loader)
    if clean_seals:
        from report.sector_reading_primitives import _SEAL_SCRIPT
        script = soup.new_tag('script', attrs={'id': 'sector-seal-chart-driver'})
        script.string = _SEAL_SCRIPT.replace('ROWS', json.dumps(clean_seals, ensure_ascii=False).replace('<', '\\u003c'))
        soup.body.append(script)
    if has_sector_charts:
        script = soup.new_tag('script', attrs={'id': 'sector-visual-chart-driver'})
        script.string = (_TEMPLATES / 'sector_daily_visuals.js').read_text(encoding='utf-8')
        soup.body.append(script)
    soup.title.string = f'{target_date} · A股日报'
    soup.html['data-bs-theme'] = 'light'
    nav = soup.new_tag('nav', attrs={'class': 'daily-nav', 'aria-label': '日报导航'})
    nav_content = soup.new_tag('div', attrs={'class': 'container'})
    brand = _text(soup, 'a', '每日市场')
    brand['href'], brand['class'] = '#daily-content', 'daily-brand'
    nav_content.append(brand)
    links = soup.new_tag('div', attrs={'class': 'daily-nav-links'})
    nav_links = ([('小盘轮换', 'daily-plan')] + ([('板块成员', 'daily-choice')] if choice else [])
                 + [('板块图表', 'daily-sectors')])
    if assets:
        nav_links.append(('跨日图表', 'daily-history'))
    nav_links.append(('市场图表', 'daily-evidence'))
    for label, anchor in nav_links:
        link = _text(soup, 'a', label)
        link['href'], link['class'] = '#' + anchor, 'btn-text theme-secondary btn-sm'
        links.append(link)
    nav_content.append(links)
    nav.append(nav_content)
    main.insert_before(nav)
    # Legacy CSS supplies chart geometry; the reading stylesheet owns the surface.
    for inherited in soup.head.find_all('style'):
        inherited.string = '@layer report-legacy {\n' + (inherited.string or inherited.get_text()) + '\n}'
    bootstrap = soup.new_tag('style', attrs={'id': 'bootstrap-css', 'data-version': '6.0.0-alpha.1'})
    bootstrap.string = _BOOTSTRAP
    soup.head.append(bootstrap)
    style = soup.new_tag('style')
    style.string = _STYLE
    soup.head.append(style)
    if chart_cards:
        driver = soup.new_tag('script', attrs={'id': 'sector-fact-chart-driver'})
        driver.string = chart_driver()
        soup.body.append(driver)
    script = soup.new_tag('script', attrs={'id': 'sector-daily-archive-resize'})
    script.string = '''(() => {
const main=document.querySelector('.sector-daily');
const resize=()=>requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
main.addEventListener('toggle',event=>{if(event.target.open)resize();},true);
const reveal=()=>{
  const target=document.getElementById(location.hash.slice(1));
  if(!target||!main.contains(target))return;
  for(let node=target;node&&node!==main;node=node.parentElement){if(node.tagName==='DETAILS')node.open=true;}
  requestAnimationFrame(()=>{target.scrollIntoView({block:'start'});resize();});
};
window.addEventListener('hashchange',reveal);
document.querySelectorAll('.daily-nav a').forEach(link=>link.addEventListener('click',()=>{
  if(link.hash===location.hash)reveal();
}));
if(location.hash)reveal();
})();'''
    soup.body.append(script)
    return str(soup)


def replay_output_path(full_html_path, target_date):
    source = Path(full_html_path)
    folder = source.parent if source.parent.name == 'replay' else source.parent / 'replay'
    return folder / f'{target_date}_A股日报_板块日报_replay.html'


def save_sector_daily(source_html, target_date, *, snapshot, full_html_path=None, output_path=None,
                      seal_rows=(), previous_snapshot=None, previous_record=None,
                      origin='historical_rebuild', ledger_root=None,
                      tracked_evidence=None, refresh_tracking=False, membership=None,
                      trend_evidence=None, refresh_trend=False, leader_board=None,
                      hypothesis_record=None, historical_snapshot=False, source_html_path=None):
    """Render and atomically save only this page; no query or research side effects."""
    if refresh_tracking or refresh_trend:
        raise ValueError('板块阅读页只读取冻结事实；补查请另行采集，不自动延续旧名单')
    if output_path is None and full_html_path is None:
        raise ValueError('缺少板块日报输出路径')
    path = Path(output_path) if output_path else sector_daily_output_path(full_html_path)
    if path.suffix != '.html':
        raise ValueError('板块日报必须保存为 HTML')
    if output_path and path.parent.resolve().name != 'replay':
        raise ValueError('显式验证输出必须位于 replay 目录')
    if full_html_path and path.resolve() == Path(full_html_path).resolve():
        raise ValueError('不能覆盖来源日报')
    is_replay = path.parent.resolve().name == 'replay'
    if path.is_symlink() or (path.exists() and not is_replay):
        raise ValueError('不能覆盖正式历史页面，请输出到 replay 目录')
    link = (os.path.relpath(full_html_path, path.parent)
            if full_html_path and Path(full_html_path).is_file() and source_html is not None else None)
    html = render_sector_daily(
        source_html, target_date, snapshot=snapshot, full_report_name=link,
        hypothesis_record=hypothesis_record, trend_evidence=trend_evidence,
        historical_snapshot=historical_snapshot,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(html)
        if is_replay:
            temporary.replace(path)
        else:
            # A formal page is first-publish-only. Hard-linking the completed
            # temp file makes the existence check and publication one atomic
            # no-replace operation on the same filesystem.
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise ValueError('正式板块页已由另一进程发布，请改读 replay') from error
            finally:
                temporary.unlink(missing_ok=True)
            temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def main():
    parser = argparse.ArgumentParser(description='离线生成板块阅读页，不运行旧交易推演')
    parser.add_argument('source', help='历史完整版 HTML；填 - 表示仅使用冻结快照')
    parser.add_argument('snapshot', help='目标日冻结快照 JSON')
    parser.add_argument('--output', help='验证页路径，必须位于 replay 目录')
    parser.add_argument('--history-record', help='可选：已保存的同日历史板块记录，只用于核对价格来源')
    parser.add_argument('--history-trend', help='可选：与历史记录配对的同日价格路径，不作为当前名单')
    args = parser.parse_args()
    snapshot_path = Path(args.snapshot)
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    day = snapshot['date']
    sector_facts(snapshot, day)
    source = Path(args.source) if args.source != '-' else None
    base = source or Path('reports') / f'{day}_A股日报_完整版.html'
    output = Path(args.output) if args.output else replay_output_path(base, day)
    protected = [snapshot_path, *([source] if source else [])]
    if (output.parent.resolve().name != 'replay' or output.is_symlink()
            or output.resolve() in [item.resolve() for item in protected]):
        parser.error('验证页必须写入 replay 目录，且不能覆盖来源或快照')
    if bool(args.history_record) != bool(args.history_trend):
        parser.error('历史记录与价格路径须成对提供')
    record = json.loads(Path(args.history_record).read_text(encoding='utf-8')) if args.history_record else None
    trend = json.loads(Path(args.history_trend).read_text(encoding='utf-8')) if args.history_trend else None
    path = save_sector_daily(
        source.read_text(encoding='utf-8') if source else None, day,
        snapshot=snapshot, full_html_path=source, output_path=output,
        hypothesis_record=record, trend_evidence=trend,
    )
    print(f'板块阅读验证页: {path}')


if __name__ == '__main__':
    main()
