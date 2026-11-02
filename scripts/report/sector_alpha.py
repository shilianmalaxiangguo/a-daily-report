"""Same-window sector/member comparisons from validated frozen facts."""
import json
from pathlib import Path
from statistics import median

from report.sector_reading_history import numeric_trend_view


def _path(changes):
    values, level = [0.], 1.
    for change in changes:
        level = level * (1 + change / 100) if level is not None and change is not None else None
        values.append((level - 1) * 100 if level is not None else None)
    return values


def _drawdown(path):
    if any(v is None for v in path):
        return None
    peak, worst = 1., 0.
    for value in path:
        level = 1 + value / 100
        peak = max(peak, level)
        worst = min(worst, (level / peak - 1) * 100)
    return worst


def build_alpha_comparison(raw_view, target_date, choice=None, *, market_history=None):
    view = numeric_trend_view(raw_view, target_date)
    members = view.get('member_comparison')
    if not members or not members['sectors'] or view.get('calendar_verified') is not True:
        return None
    dates = members['trade_dates']
    history = view.get('ranking_returns') or view['heat']
    if len(dates) != 6 or dates != history['dates'][-6:]:
        return None
    changes = {r['track_id']: dict(zip(history['dates'], r['pct'])) for r in history['rows']}
    bars = {(r['code'], r['date']): r['change_pct'] for r in members['daily_rows']}
    names = {r['track_id']: r.get('display_name', r['name']) for r in view['tracks']}
    sectors = {}
    for identity, member in members['sectors'].items():
        daily = [changes.get(identity, {}).get(d) for d in dates[1:]]
        sector_path = _path(daily)
        stocks = []
        for row in member['rows']:
            stock_daily = [bars.get((row['code'], d)) for d in dates[1:]]
            path = _path(stock_daily)
            extra = [a - b if a is not None and b is not None else None for a, b in zip(stock_daily, daily)]
            complete = all(v is not None for v in extra)
            wins = [v > 0 for v in extra] if complete else []
            trailing = next((i for i, win in enumerate(reversed(wins)) if not win), len(wins))
            stocks.append({**row, 'path': path, 'daily_excess': [None, *extra],
                           'stock_pct': path[-1], 'excess_pp': path[-1] - sector_path[-1]
                           if path[-1] is not None and sector_path[-1] is not None else None,
                           'outperform_days': sum(wins) if complete else None,
                           'trailing_days': trailing if complete else None,
                           'max_drawdown_pct': _drawdown(path)})
        returns = sorted(r['stock_pct'] for r in stocks if r['stock_pct'] is not None)
        sectors[identity] = {'track_id': identity, 'name': member['name'],
            'display_name': names.get(identity, member['name'] + ' · ' + member['index_code']),
            'sector_pct': sector_path[-1], 'path': sector_path, 'max_drawdown_pct': _drawdown(sector_path),
            'median_pct': median(returns) if returns else None,
            'median_without_top_pct': median(returns[:-1]) if len(returns) > 1 else None,
            'valid_count': len(returns), 'member_count': member['member_count'],
            'positive_count': sum(v > 0 for v in returns), 'stocks': stocks,
            **({'directory_member_count': member['directory_member_count'],
                'excluded_members': member['excluded_members']} if member.get('excluded_members') else {})}
    primary = (choice or {}).get('primary') or {}
    selected = primary.get('track_id') or next(iter(sectors), '')
    from report.sector_market_relation import build_market_relation
    return {'target_date': target_date, 'dates': dates, 'query_date': members['query_date'],
            'membership_basis': members['membership_basis'], 'selected_sector': selected,
            'selected_stock': ((choice or {}).get('stock') or {}).get('code'), 'sectors': sectors,
            'market_relation': build_market_relation(raw_view, market_history)}


def render_alpha_comparison(soup, value, choice):
    if not choice['daily'][-1]['valid'] and not value.get('market_relation'):
        from report.sector_choice import render_sector_choice
        return render_sector_choice(soup, choice)
    from report.sector_reading_primitives import _text
    section = soup.new_tag('section', attrs={'id': 'daily-choice', 'class': 'sector-daily-section daily-alpha'})
    section.append(_text(soup, 'small', '板块成员 · 同窗比较'))
    section.append(_text(soup, 'h2', '板块成员同窗比较'))
    section.append(_text(soup, 'p', '在所选概念的成员里，比较个股相对所属板块、相对中证全指的同窗表现。'
        '板块共涨不等于贝塔，跑赢板块也不等于阿尔法。'))
    if not choice['daily'][-1]['valid']:
        section.append(_text(soup, 'p', value['target_date'] + '的概念指数行情未取得；板块路径保留缺口，'
            '不抹掉已取得的个股与大盘比较，不据此判断当天板块强弱。'))
    primary, stock = choice.get('primary'), choice.get('stock')
    if primary:
        section.append(_text(soup, 'small', '默认观察起点：' + primary['name'] +
            (' / ' + stock['name'] if stock else '') + '。沿用原比较记录打开，可自由切换，不是买入排序。'))
    else:
        section.append(_text(soup, 'small', '未指定默认观察对象；下列已覆盖样本均可切换，不据缺数替换前次关注。'))
    latest = choice['daily'][-1]
    pair = choice['leader_retention'][-1] if choice['leader_retention'] else None
    rotation = (f'本日{latest["up"]}/{latest["valid"]}个概念指数上涨' +
        (f'，昨日上涨前五仅{pair["retained"]}/{pair["previous_count"]}个留在本日前五' if pair else '') +
        '。概念可能重叠，这不是独立股票的上涨比例，也不决定买卖。') if latest['valid'] else ''
    explanations = []
    for other in choice.get('alternatives') or []:
        paragraph = _text(soup, 'p', f'较长窗口对照：{other["name"]}，5日{other["five_day_pct"]:+.2f}%，'
                          f'20日{other["twenty_day_pct"]:+.2f}%。')
        button = _text(soup, 'button', '对照该板块')
        button.attrs.update({'type': 'button', 'class': 'reading-tag', 'data-alpha-alternative': other['track_id']})
        paragraph.append(button)
        explanations.append(paragraph)
    controls = soup.new_tag('div', attrs={'class': 'reading-tags alpha-sectors', 'role': 'group', 'aria-label': '板块整体与个股比较'})
    ordered = sorted(value['sectors'].values(), key=lambda r: (r['track_id'] != value['selected_sector'], r['name'], r['track_id']))
    for row in ordered:
        button = soup.new_tag('button', attrs={'type': 'button', 'data-alpha-sector': row['track_id'],
            'aria-pressed': str(row['track_id'] == value['selected_sector']).lower(), 'class': 'reading-tag'})
        button.append(_text(soup, 'strong', row['name']))
        pct = row['sector_pct']
        duplicate = sum(r['name'] == row['name'] for r in ordered) > 1
        button.append(_text(soup, 'small', (f'5日 {pct:+.2f}%' if pct is not None else '同窗未齐') +
                                   f' · 成员 {row["valid_count"]}/{row["member_count"]}' +
                                   (f' · 原目录另含{len(row["excluded_members"])}只已摘牌' if row.get('excluded_members') else '') +
                                   (' · ' + row['track_id'].removeprefix('index:') if duplicate else '')))
        button['aria-label'] = row['display_name'] + '，查看板块与个股比较'
        controls.append(button)
    section.append(controls)
    section.append(soup.new_tag('p', attrs={'id': 'alpha-sector-summary', 'class': 'alpha-takeaway', 'aria-live': 'polite'}))
    layout_controls = soup.new_tag('div', attrs={'class': 'alpha-layout-controls'})
    toggle = _text(soup, 'button', '收起成员侧栏')
    toggle.attrs.update({'id': 'alpha-sidebar-toggle', 'type': 'button', 'class': 'reading-tag',
                         'aria-controls': 'alpha-member-sidebar', 'aria-expanded': 'true'})
    layout_controls.append(toggle)
    section.append(layout_controls)
    grid = soup.new_tag('div', attrs={'class': 'alpha-comparison-grid'})
    left = soup.new_tag('aside', attrs={'id': 'alpha-member-sidebar', 'class': 'alpha-member-sidebar',
                                       'aria-labelledby': 'alpha-members-heading'})
    heading = _text(soup, 'h3', '同板块，谁提供了额外表现？')
    heading['id'] = 'alpha-members-heading'
    left.append(heading)
    left.append(_text(soup, 'small', '5日收益差（百分点）= 个股5日收益 − 对应板块5日收益。点选后看路径；正差值也可能只是少跌。'))
    views = soup.new_tag('div', attrs={'class': 'reading-tags alpha-member-views', 'role': 'group',
                                      'aria-label': '成员比较显示方式'})
    for view, label, panel in [('chart', '差值图', 'alpha-stock-chart-panel'), ('list', '个股名单', 'alpha-stock-buttons')]:
        button = _text(soup, 'button', label)
        button.attrs.update({'type': 'button', 'class': 'reading-tag', 'data-alpha-view': view,
                             'aria-pressed': str(view == 'chart').lower(), 'aria-controls': panel})
        views.append(button)
    left.append(views)
    frame = soup.new_tag('div', attrs={'id': 'alpha-stock-chart-panel', 'class': 'alpha-stock-scroll'})
    frame.append(soup.new_tag('div', attrs={'id': 'alpha-stock-chart', 'class': 'alpha-chart',
        'data-alpha-chart': 'stocks', 'role': 'img', 'aria-label': '所选板块各成员同窗收益差'}))
    left.append(frame)
    left.append(soup.new_tag('div', attrs={'id': 'alpha-stock-buttons', 'class': 'reading-tags alpha-stock-buttons',
                                        'role': 'group', 'aria-label': '选择个股与板块比较', 'hidden': ''}))
    grid.append(left)
    right = soup.new_tag('article')
    right.append(_text(soup, 'h3', '大盘—板块—个股 · 同窗走势'))
    relation = value.get('market_relation')
    windows = soup.new_tag('div', attrs={'class': 'reading-tags market-relation-windows', 'role': 'group',
                                        'aria-label': '大盘关系观察窗口'})
    for count in (5, 20, 60):
        button = _text(soup, 'button', f'{count}日')
        button.attrs.update({'type': 'button', 'class': 'reading-tag', 'data-market-window': str(count),
            'aria-pressed': str(bool(relation and count == relation['default_window'])).lower()})
        if not relation or count not in relation['available_windows']:
            button['disabled'] = ''
            button['title'] = f'尚缺完整{count}日成员与大盘同窗资料'
        windows.append(button)
    right.append(windows)
    right.append(soup.new_tag('p', attrs={'id': 'market-relation-summary', 'class': 'alpha-takeaway', 'aria-live': 'polite'}))
    right.append(soup.new_tag('div', attrs={'id': 'market-relation-chart', 'class': 'alpha-chart market-relation-path',
        'data-market-relation-chart': '', 'role': 'img', 'aria-label': '个股、对应板块、中证全指的同窗累计涨跌'}))
    right.append(soup.new_tag('div', attrs={'id': 'market-relation-metrics', 'class': 'market-relation-metrics', 'aria-live': 'polite'}))
    right.append(soup.new_tag('p', attrs={'id': 'market-relation-note', 'class': 'alpha-risk', 'aria-live': 'polite'}))
    right.append(_text(soup, 'h3', '个股相对所属板块 · 原5日比较'))
    right.append(soup.new_tag('p', attrs={'id': 'alpha-stock-summary', 'class': 'alpha-takeaway', 'aria-live': 'polite'}))
    right.append(soup.new_tag('div', attrs={'id': 'alpha-path-chart', 'class': 'alpha-chart alpha-path',
        'data-alpha-chart': 'path', 'role': 'img', 'aria-label': '所选个股与板块同窗收益对照、累计路径及逐日差值'}))
    right.append(soup.new_tag('p', attrs={'id': 'alpha-risk-note', 'class': 'alpha-risk', 'aria-live': 'polite'}))
    grid.append(right)
    section.append(grid)
    for explanation in explanations:
        section.append(explanation)
    section.append(_text(soup, 'h3', '板块内部扩散 · 原5日样本'))
    section.append(_text(soup, 'small', f'截至{value["target_date"]}，用同一5个交易日比较板块指数和成员收益中间值；'
        '再去掉5日涨幅最高的一只，看其余成员的中间涨幅。这个对照只检查结果是否可能受单只强股影响，不是指数贡献分解或卖出建议。只含本次已补查板块。'))
    section.append(soup.new_tag('div', attrs={'id': 'alpha-sector-chart', 'class': 'alpha-chart alpha-overall',
        'data-alpha-chart': 'sectors', 'role': 'img', 'aria-label': '板块指数、成员收益中间值，以及去掉5日涨幅最高一只后的其余成员中间涨幅'}))
    if rotation:
        section.append(_text(soup, 'p', rotation))
    section.append(_text(soup, 'small', '板块整体表现与个股相对表现可以同时存在；这里只展示已覆盖成员，'
        '不推断全市场由哪类行情主导，也不把固定窗口或连续跑赢天数变成买卖条件。'))
    section.append(_text(soup, 'small', f'最新成员查询于{value["query_date"]}，回看截至{value["target_date"]}的行情，不是当时的历史名单或预测。'
        '同向天数和历史差值都不是已识别的独立收益或大盘带动关系。'
        '个股按来源close/pre_close计算，前收盘参考价不一定等于上一日不复权收盘价。'
        '指数不是可成交ETF；复权、费用和可成交性尚未统一核实。'))
    for identity, payload in [('sector-alpha-data', value), ('sector-choice-data', choice)]:
        node = soup.new_tag('script', attrs={'id': identity, 'type': 'application/json'})
        node.string = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('<', chr(92) + 'u003c')
        section.append(node)
    script = soup.new_tag('script')
    script.string = (Path(__file__).resolve().parents[1] / 'templates/sector_alpha_charts.js').read_text(encoding='utf-8')
    section.append(script)
    script = soup.new_tag('script', attrs={'id': 'market-relation-chart-driver'})
    script.string = (Path(__file__).resolve().parents[1] / 'templates/sector_market_relation_charts.js').read_text(encoding='utf-8')
    section.append(script)
    return section
