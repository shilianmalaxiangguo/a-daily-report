"""Dashboard surface for the decision board: answer first, then evidence, then detail."""
from html import escape
import json
from pathlib import Path

from bs4 import BeautifulSoup

RED, GREEN, INK, MUTED = '#E73922', '#07C160', '#18171c', '#7a7882'
ALPHA_COLOR, BETA_COLOR, INDEX_COLOR = '#5b45b5', '#2364aa', '#9a98a3'


def _text(soup, tag, text, cls=None):
    node = soup.new_tag(tag)
    node.string = text
    if cls:
        node['class'] = cls
    return node


def _pct(value, digits=2, unit='%'):
    if value is None:
        return '—'
    shown = 0. if abs(value) < 0.5 * 10 ** -digits else value
    return f'{shown:+.{digits}f}{unit}'


def _tone(value):
    if value is None or abs(value) < 0.005:
        return 'dash-flat'
    return 'dash-up' if value > 0 else 'dash-down'


def spark(values, *, width=136, height=36, color=ALPHA_COLOR, compare=None, compare_color=INDEX_COLOR,
          zero=None, label=''):
    """Server-side sparkline; gaps stay gaps, nothing is filled with zero."""
    present = [v for v in [*values, *(compare or [])] if v is not None]
    if len(present) < 2:
        return None
    low, high = min(present), max(present)
    if zero is not None:
        low, high = min(low, zero), max(high, zero)
    if high - low < 1e-9:
        high = low + 1

    def segments(series):
        out, current = [], []
        for k, v in enumerate(series):
            if v is None:
                if current:
                    out.append(current)
                current = []
                continue
            x = 2 + (width - 4) * k / max(len(series) - 1, 1)
            y = 2 + (height - 4) * (1 - (v - low) / (high - low))
            current.append((x, y))
        if current:
            out.append(current)
        return out

    parts = [f'<svg class="dash-spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
             f'role="img" aria-label="{escape(label)}" preserveAspectRatio="none">']
    if zero is not None and low < zero < high:
        y = 2 + (height - 4) * (1 - (zero - low) / (high - low))
        parts.append(f'<line x1="0" x2="{width}" y1="{y:.1f}" y2="{y:.1f}" stroke="#d9d6df" stroke-dasharray="2 2"/>')
    for points in segments(compare or []):
        parts.append('<polyline fill="none" stroke="%s" stroke-width="1.2" stroke-dasharray="3 2" points="%s"/>'
                     % (compare_color, ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)))
    last = None
    for points in segments(values):
        parts.append('<polyline fill="none" stroke="%s" stroke-width="1.8" stroke-linejoin="round" points="%s"/>'
                     % (color, ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)))
        last = points[-1]
    if last:
        parts.append(f'<circle cx="{last[0]:.1f}" cy="{last[1]:.1f}" r="2.4" fill="{color}"/>')
    parts.append('</svg>')
    return BeautifulSoup(''.join(parts), 'html.parser').svg


def _cumulative(daily):
    level, out = 1., [0.]
    for r in daily:
        if r is None or level is None:
            level = None
            out.append(None)
            continue
        level *= 1 + r / 100
        out.append((level - 1) * 100)
    return out


def render_header(soup, header, board, projection, target_date):
    """Compact top bar: date, the stance badge and when the facts were queried."""
    header['class'] = 'daily-header dash-header'
    header.clear()
    line = soup.new_tag('div', attrs={'class': 'dash-title'})
    stamp = soup.new_tag('time', attrs={'datetime': target_date})
    stamp.string = target_date
    line.append(stamp)
    line.append(_text(soup, 'h1', 'A股日报'))
    line.append(_text(soup, 'span', board['stance_text'], f"dash-badge dash-{board['stance']}"))
    header.append(line)
    header.append(_text(soup, 'small', f"行情截至{target_date}收盘；全市场行情查询于{projection['query_date']}。"
                        '以下判断是助手按公开规则给出的建议，不知道你的账户与持仓。', 'dash-fresh'))


TILE_WORDS = {'beta': {'avoid': ('不做', '大盘带着跌'), 'buy': ('可做', '大盘带动上涨'), 'less': ('少做', '大盘带动不强')},
              'alpha': {'buy_only': ('可做', '规则近期有优势'), 'supplement': ('补充', '只买检查全过的'),
                        'watch': ('观察', None), 'none_today': ('暂无', '今天没有检查全过的')}}


def _tile(soup, label, word, reason, tone):
    tile = soup.new_tag('div', attrs={'class': f'dash-tile dash-tile-{tone}'})
    tile.append(_text(soup, 'small', label))
    tile.append(_text(soup, 'strong', word))
    tile.append(_text(soup, 'span', reason))
    return tile


def render_hero(soup, board, interpretation=None, plan=None):
    section = soup.new_tag('section', attrs={'id': 'daily-decision', 'class': 'sector-daily-section dash-hero'})
    left = soup.new_tag('div', attrs={'class': 'dash-hero-main'})
    if interpretation:
        chosen = interpretation['samples'][interpretation['chosen']]
        left.append(_text(soup, 'small', '今日解读', 'dash-kicker'))
        title = soup.new_tag('h2')
        title.append(_text(soup, 'span', chosen['stance'], f"dash-badge dash-{ {'防守': 'defense', '均衡': 'balanced', '进攻': 'offense'}[chosen['stance']] }"))
        title.append(soup.new_string(' ' + chosen['headline']))
        left.append(title)
        reading = soup.new_tag('ul', attrs={'class': 'dash-reading'})
        for sentence in chosen['summary']:
            reading.append(_text(soup, 'li', sentence))
        left.append(reading)
        action_line = soup.new_tag('p', attrs={'class': 'dash-reading-action'})
        from report.small_cap_rotation import day_label
        upcoming = day_label((plan or {}).get('next_session'))
        action_line.append(_text(soup, 'strong', f'下一个交易日{upcoming}：' if upcoming else '下一个交易日：'))
        action_line.append(soup.new_string(chosen['action']))
        left.append(action_line)
        dissent = soup.new_tag('p', attrs={'class': 'dash-dissent'})
        dissent.append(_text(soup, 'strong', '反方：'))
        dissent.append(soup.new_string(chosen['dissent']))
        left.append(dissent)
        votes = '、'.join(f'{stance}{count}次' for stance, count in interpretation['votes'].items())
        others = [item for item in interpretation['samples'] if item['stance'] != chosen['stance']]
        note = (f"独立生成{interpretation['requested_samples']}次，{len(interpretation['samples'])}次通过数字核对：{votes}" + (f"；少数意见：{others[0]['headline']}" if others else '')
                + f"。数字已逐一核对出处；模型{interpretation['model']}，生成于{interpretation['generated_at'][:16].replace('T', ' ')}。")
        if chosen['stance'] != board['stance_text']:
            note += f"解读与规则信号不同（规则：{board['stance_text']}），两者都保留。"
        left.append(_text(soup, 'small', note, 'dash-reading-note'))
    else:
        left.append(_text(soup, 'small', '总体建议（规则信号）', 'dash-kicker'))
        title = soup.new_tag('h2')
        title.append(_text(soup, 'span', board['stance_text'], f"dash-badge dash-{board['stance']}"))
        title.append(soup.new_string(' ' + board['headline']))
        left.append(title)
        reasons = soup.new_tag('ol', attrs={'class': 'dash-reasons'})
        for reason in board['reasons']:
            reasons.append(_text(soup, 'li', reason))
        left.append(reasons)
        left.append(_text(soup, 'small', '今日解读未生成，这里只显示规则信号。', 'dash-reading-note'))
    section.append(left)
    right = soup.new_tag('div', attrs={'class': 'dash-hero-side'})
    right.append(_text(soup, 'h3', f"执行计划：小盘轮换 · 大盘{board['stance_text'][:2]}" if plan else f"规则信号：{board['stance_text']}"))
    tiles = soup.new_tag('div', attrs={'class': 'dash-tiles'})
    beta_word, beta_reason = TILE_WORDS['beta'][board['action_keys']['beta']]
    alpha_word, alpha_reason = TILE_WORDS['alpha'][board['action_keys']['alpha']]
    edge = board['walk_forward']['summary']['alpha']['mean_excess']
    if alpha_reason is None:
        alpha_reason = (f"规则近两个月{'跑输' if (edge or 0) <= 0 else '跑赢'}{abs(edge):.2f}个百分点" if edge is not None
                        else '规则缺少检验样本')
        long_run = board.get('long_run')
        if long_run and long_run['alpha_oos_cagr'] is not None and long_run['alpha_oos_cagr'] <= long_run['index_oos_cagr']:
            alpha_reason += ' · 长期回测也跑输'
    if plan:
        names = '、'.join(p['name'] for p in plan['picks']) or '本期没有符合条件的股票'
        word = '换手日' if plan['sessions_since'] == 0 else f"持有第{plan['sessions_since']}天"
        from report.small_cap_rotation import day_label
        switch = (f"{day_label(plan['next_decision'])}收盘后定新名单" if plan.get('next_decision')
                  else f"{plan['sessions_to_next']}个交易日后定新名单")
        tiles.append(_tile(soup, '小盘轮换', word, f"{names} · {switch}", 'go' if plan['picks'] else 'wait'))
        tiles.append(_tile(soup, '大盘', beta_word, f"贝塔{beta_word} · 只作背景", 'wait'))
        selling = ('收盘比买价高10%次日开盘卖 · 钱留到下一个换手日' if plan.get('take_profit')
                   else '持有遇高开5%以上可开盘兑现')
        tiles.append(_tile(soup, '纪律', '守底线', f'净值跌破0.7全部停下 · {selling}', 'rule'))
    else:
        tiles.append(_tile(soup, '贝塔', beta_word, beta_reason, 'stop' if beta_word == '不做' else 'go' if beta_word == '可做' else 'wait'))
        tiles.append(_tile(soup, '阿尔法', alpha_word, alpha_reason, 'go' if alpha_word in ('可做', '补充') else 'wait' if alpha_word == '观察' else 'stop'))
        tiles.append(_tile(soup, '纪律', '不追高开', '高开>3%不买 · 持有遇高开5%以上开盘卖 · 破失效价离场', 'rule'))
    right.append(tiles)
    preview = soup.new_tag('p', attrs={'class': 'dash-preview'})
    if plan:
        holding = plan.get('holding')
        preview.append(_text(soup, 'strong', '本期名单：'))
        text = '、'.join(f"{p['name']}" for p in plan['picks']) or '没有'
        if plan['backups']:
            text += '（备选：' + '、'.join(p['name'] for p in plan['backups']) + '）'
        if holding:
            text += f"；买入以来合计{_pct(holding['basket_pct'])}，同期创业板指{_pct(holding['chinext_pct'])}"
        preview.append(soup.new_string(text + '。'))
    else:
        buys = [c for c in board['candidates'] if c['status'] == 'buy'][:3]
        preview.append(_text(soup, 'strong', '检查全过：'))
        preview.append(soup.new_string('；'.join(f"{c['name']}（失效价{c['stop']:.2f}元，距现价{_pct(c['stop_distance_pct'])}）"
                                                 for c in buys) + '。' if buys else '今天没有。'))
    right.append(preview)
    summary, pk = board['walk_forward']['summary'], board['pk']
    quick = soup.new_tag('div', attrs={'class': 'dash-quick', 'aria-label': 'PK 速览'})
    for label, value, note, tone in (
        ('检查全过阿尔法 · 近两个月5日后', _pct(summary['alpha']['mean_excess'], unit='个百分点'),
         f"相对中证全指 · 跑赢{summary['alpha']['hit_rate'] * 100:.0f}%的日期" if summary['alpha']['dates'] else '期间没有名单',
         _tone(summary['alpha']['mean_excess'])),
        ('高贝塔 · 近两个月5日后', _pct(summary['beta']['mean_excess'], unit='个百分点'),
         f"相对中证全指 · 跑赢{summary['beta']['hit_rate'] * 100:.0f}%的日期" if summary['beta']['dates'] else '期间没有名单',
         _tone(summary['beta']['mean_excess']))):
        box = soup.new_tag('div', attrs={'class': 'dash-stat'})
        box.append(_text(soup, 'small', label))
        box.append(_text(soup, 'strong', value, tone))
        box.append(_text(soup, 'span', note))
        quick.append(box)
    right.append(quick)
    right.append(_text(soup, 'h3', '出现这些信号就改判断'))
    triggers = soup.new_tag('ul', attrs={'class': 'dash-triggers'})
    for trigger in board['triggers']:
        item = soup.new_tag('li', attrs={'data-met': str(trigger['met']).lower()})
        item.append(_text(soup, 'span', trigger['text']))
        item.append(_text(soup, 'small', trigger['now'] + ('（已出现）' if trigger['met'] else '')))
        triggers.append(item)
    right.append(triggers)
    section.append(right)
    return section


def render_novelty(soup, observations):
    section = soup.new_tag('section', attrs={'id': 'daily-novelty', 'class': 'sector-daily-section dash-section'})
    section.append(_text(soup, 'h2', '今日新现象'))
    section.append(_text(soup, 'p', '拿今天和近期比，按少见程度排序；条越长，今天越不寻常。', 'dash-takeaway'))
    grid = soup.new_tag('div', attrs={'class': 'dash-novelty'})
    for item in observations['items'][:6]:
        card = soup.new_tag('article', attrs={'class': f"dash-card dash-observation dash-kind-{item['kind']}",
                                              'data-observation': item['id']})
        head = soup.new_tag('div', attrs={'class': 'dash-observation-head'})
        head.append(_text(soup, 'strong', item['title']))
        head.append(_text(soup, 'small', f"少见程度 {round(item['score'] * 100)}"))
        card.append(head)
        bar = soup.new_tag('div', attrs={'class': 'dash-meter', 'role': 'img', 'aria-label': f"少见程度{round(item['score'] * 100)}"})
        fill = soup.new_tag('span')
        fill['style'] = f"width:{max(4, round(item['score'] * 100))}%"
        bar.append(fill)
        card.append(bar)
        card.append(_text(soup, 'p', item['text']))
        grid.append(card)
    section.append(grid)
    return section


def _kpi(soup, label, value, sub, *, tone=None, line=None, color=ALPHA_COLOR, zero=None, compare=None):
    tile = soup.new_tag('div', attrs={'class': 'dash-kpi'})
    tile.append(_text(soup, 'small', label))
    tile.append(_text(soup, 'strong', value, tone))
    tile.append(_text(soup, 'span', sub, 'dash-kpi-sub'))
    if line:
        chart = spark(line, color=color, zero=zero, compare=compare, label=label + '近两个月走势')
        if chart is not None:
            tile.append(chart)
    return tile


def render_kpis(soup, board, projection):
    regime, series, market = projection['regime'], projection['series'], board['market']
    section = soup.new_tag('section', attrs={'id': 'daily-kpis', 'class': 'sector-daily-section dash-kpis',
                                             'aria-label': '关键指标'})
    turnover = market['turnover_yi']
    recent = [v for v in turnover[-21:-1] if v is not None]
    average = sum(recent) / len(recent) if recent else None
    counts = board['status_counts']
    tiles = [
        _kpi(soup, '中证全指', _pct(regime['market_pct']), f"近20日{_pct(market['return20_pct'])}",
             tone=_tone(regime['market_pct']), line=market['closes'], color=INK),
        _kpi(soup, '个股中位数', _pct(regime['median_pct']), f"上涨{regime['up_count']}只 · 下跌{regime['down_count']}只",
             tone=_tone(regime['median_pct']), line=[p['median_pct'] for p in series], zero=0, color=INK),
        _kpi(soup, '与大盘同向', f"{regime['same_share']:.0f}%" if regime['same_share'] is not None else '—',
             '两者无关时约50%', line=[p['same_share'] for p in series], zero=50, color=BETA_COLOR),
        _kpi(soup, '共振度', f"{regime['sync']:.2f}" if regime['sync'] is not None else '—',
             f"大盘带动{regime['strength'] or '待确认'}"
             + (f" · 第{round(regime['sync_rank'] * 100)}百分位" if regime['sync_rank'] is not None else ''),
             line=[p['sync'] for p in series], color=BETA_COLOR),
        _kpi(soup, '独立上涨', f"{regime['alpha_up']}只",
             f"显著为正共{regime['outperform']}只 · 随机约{regime['expected']:.0f}只",
             line=[p['alpha_up'] for p in series], color=ALPHA_COLOR),
        _kpi(soup, '两市成交额', f"{turnover[-1] / 1e4:.2f}万亿" if turnover[-1] is not None else '—',
             (f"较前20日均值{_pct((turnover[-1] / average - 1) * 100, 1)}" if average and turnover[-1] else '前20日资料不足'),
             line=turnover, color=INK),
        _kpi(soup, '检查全过阿尔法', f"{counts['buy']}只",
             f"等回调{counts['wait']} · 观察{counts['watch']} · 不做{counts['avoid']}", tone='dash-alpha',
             line=[row['alpha_candidates'] for row in board['walk_forward']['rows']] + [counts['buy']]),
    ]
    for tile in tiles:
        section.append(tile)
    return section


def _row(soup, cells, cls=None):
    tr = soup.new_tag('tr')
    if cls:
        tr['class'] = cls
    for text, tone in cells:
        tr.append(_text(soup, 'td', text, tone))
    return tr


def _table(soup, columns, rows, cls='dash-table'):
    wrapper = soup.new_tag('div', attrs={'class': 'table-responsive dash-table-wrap'})
    table = soup.new_tag('table', attrs={'class': f'table {cls}'})
    head = soup.new_tag('thead')
    tr = soup.new_tag('tr')
    for column in columns:
        tr.append(_text(soup, 'th', column))
    head.append(tr)
    table.append(head)
    body = soup.new_tag('tbody')
    for row in rows:
        body.append(row)
    table.append(body)
    wrapper.append(table)
    return wrapper


def pk_verdict(board):
    summary = board['walk_forward']['summary']
    a, b = summary['alpha']['mean_excess'], summary['beta']['mean_excess']
    pk = board['pk']
    alpha_down = pk['alpha']['down_scenario_pct'] if pk['alpha'] else None
    beta_down = pk['beta']['down_scenario_pct'] if pk['beta'] else None
    scenario = (f"若大盘再跌{board['rules']['scenario_pct']:.0f}%，按贝塔推算阿尔法组约{_pct(alpha_down)}、"
                f"高贝塔组约{_pct(beta_down)}" if alpha_down is not None and beta_down is not None else '')
    if a is not None and a > 0 and (b is None or a > b):
        verdict, text = 'alpha', f"阿尔法占优：近两个月同规则买入检查全过名单，5日后平均相对中证全指{_pct(a, unit='个百分点')}"
    elif b is not None and b > 0 and (a is None or b > a):
        verdict, text = 'beta', f"贝塔占优：高贝塔篮子5日后平均相对中证全指{_pct(b, unit='个百分点')}"
    elif a is None and b is None:
        verdict, text = 'unknown', '资料不足，无法比较'
    else:
        verdict, text = 'neither', (f"两边都没有优势：按同一规则买入后5日，检查全过阿尔法平均相对中证全指{_pct(a, unit='个百分点')}、"
                                    f"高贝塔{_pct(b, unit='个百分点')}，都没跑赢，以观望为主")
    if b is not None and verdict == 'alpha':
        text += f"，高贝塔篮子{_pct(b, unit='个百分点')}"
    elif a is not None and verdict == 'beta':
        text += f"，检查全过阿尔法{_pct(a, unit='个百分点')}"
    return verdict, text + ('；' + scenario if scenario else '') + '。'


def render_pk(soup, board):
    pk, summary = board['pk'], board['walk_forward']['summary']
    verdict, text = pk_verdict(board)
    section = soup.new_tag('section', attrs={'id': 'daily-pk', 'class': 'sector-daily-section dash-section',
                                             'data-pk-verdict': verdict})
    section.append(_text(soup, 'h2', '阿尔法 vs 贝塔 PK'))
    section.append(_text(soup, 'p', 'PK 结论：' + text, f'dash-takeaway dash-pk-{verdict}'))
    grid = soup.new_tag('div', attrs={'class': 'dash-grid dash-grid-2'})
    left = soup.new_tag('article', attrs={'class': 'dash-card'})
    left.append(_text(soup, 'h3', '现在的敞口：大盘再跌或反弹时谁受伤'))
    rows = []
    scenario = board['rules']['scenario_pct']
    for key in ('alpha', 'beta', 'index'):
        item = pk[key]
        if not item:
            continue
        rows.append(_row(soup, [
            (item['label'] + (f"（{item['count']}只）" if item.get('count') else ''), None),
            (f"{item['beta']:.2f}", None),
            (_pct(item.get('total_pct')), _tone(item.get('total_pct'))),
            (_pct(item.get('down_mean_pct')) if key != 'index' else '—', _tone(item.get('down_mean_pct'))),
            (_pct(item['down_scenario_pct']), _tone(item['down_scenario_pct'])),
            (_pct(item['up_scenario_pct']), _tone(item['up_scenario_pct'])),
        ], f'dash-row-{key}'))
    left.append(_table(soup, ['组别', '平均贝塔', '近20日涨跌', '大盘跌日均值', f'大盘−{scenario:.0f}%时', f'大盘+{scenario:.0f}%时'], rows))
    left.append(_text(soup, 'small', '情景只算大盘带来的部分（平均贝塔×大盘涨跌），不含个股自己的涨跌，不是预测。'))
    beta_rows = [_row(soup, [(f"{row['name']} {row['code']}", None), (f"{row['beta']:.2f}", None),
                             (f"{row['r2']:.2f}", None), (_pct(row['total_pct']), _tone(row['total_pct'])),
                             (_pct(row['down_mean_pct']), _tone(row['down_mean_pct'])),
                             (f"{row['amount_yi']:.1f}亿", None)]) for row in board['beta_basket']]
    left.append(_text(soup, 'h4', '高贝塔篮子：大盘反弹最受益、继续下跌最受伤'))
    left.append(_table(soup, ['股票', '贝塔', '关联度', '近20日涨跌', '大盘跌日均值', '日均成交额'], beta_rows, 'dash-table dash-table-compact'))
    grid.append(left)
    right = soup.new_tag('article', attrs={'class': 'dash-card'})
    right.append(_text(soup, 'h3', '按同一规则回到过去：买入后5日相对中证全指'))
    stats = soup.new_tag('div', attrs={'class': 'dash-stats'})
    for label, item in (('检查全过阿尔法', summary['alpha']), ('高贝塔', summary['beta'])):
        box = soup.new_tag('div', attrs={'class': 'dash-stat'})
        box.append(_text(soup, 'small', label))
        box.append(_text(soup, 'strong', _pct(item['mean_excess'], unit='个百分点') if item['dates'] else '无样本',
                         _tone(item['mean_excess'])))
        box.append(_text(soup, 'span', (f"{item['dates']}个日期 · 跑赢{item['hit_rate'] * 100:.0f}% · 中位{_pct(item['median_excess'], unit='')}"
                                        if item['dates'] else '期间没有符合规则的名单')))
        stats.append(box)
    right.append(stats)
    right.append(soup.new_tag('div', attrs={'id': 'pk-forward-chart', 'class': 'dash-chart dash-pk-chart', 'role': 'img',
                                            'aria-label': '每个决策日按规则买入后5日相对中证全指的超额'}))
    right.append(_text(soup, 'small', f"每个决策日只用当日及以前的数据选股；次日开盘买入（开盘涨停或高开超过{board['rules']['chase_pct']:.0f}%不买），"
                       f"第{summary['hold']}个交易日收盘卖出，扣{summary['cost_pct']}%往返成本，等权。相邻日期的持有期重叠，"
                       f"{summary['decision_dates']}个日期约相当于{max(1, summary['decision_dates'] // summary['hold'])}段独立样本，只够看方向。"))
    grid.append(right)
    section.append(grid)
    return section


def render_candidates(soup, board, projection):
    section = soup.new_tag('section', attrs={'id': 'daily-candidates', 'class': 'sector-daily-section dash-section'})
    counts = board['status_counts']
    section.append(_text(soup, 'h2', '阿尔法候选：谁更值得买'))
    section.append(_text(soup, 'p', f"独立上涨{len(board['candidates'])}只中，六项检查全过{counts['buy']}只；"
                         f"只差“急涨末端”或“止损太远”、等回调{counts['wait']}只；成交额不够或目标日涨停、不做{counts['avoid']}只；其余观察{counts['watch']}只。"
                         + ('' if board['walk_forward']['summary']['alpha_edge'] else '同一规则近两个月没有优势，下表是相对最好的观察名单，不是买入清单。'),
                         'dash-takeaway'))
    order = {'buy': 0, 'wait': 1, 'watch': 2, 'avoid': 3}
    featured = sorted(board['candidates'], key=lambda c: (order[c['status']], -c['passes'], -(c['t_alpha'] or 0)))[:6]
    cards = soup.new_tag('div', attrs={'class': 'dash-cards'})
    market = projection['market'][-len(featured[0]['daily']):] if featured else []
    for c in featured:
        card = soup.new_tag('article', attrs={'class': f"dash-card dash-candidate dash-status-{c['status']}",
                                              'data-code': c['code']})
        top = soup.new_tag('div', attrs={'class': 'dash-candidate-top'})
        top.append(_text(soup, 'strong', c['name']))
        top.append(_text(soup, 'small', f"{c['code']} · {c['industry']}"))
        top.append(_text(soup, 'span', board['status_names'][c['status']], f"dash-status dash-status-chip-{c['status']}"))
        card.append(top)
        numbers = soup.new_tag('dl', attrs={'class': 'dash-numbers'})
        for label, value, tone in (('20日涨跌', _pct(c['total_pct']), _tone(c['total_pct'])),
                                   ('独立收益（个百分点）', _pct(c['own_pp'], unit=''), _tone(c['own_pp'])),
                                   ('贝塔', f"{c['beta']:.2f}", None),
                                   ('大盘跌日平均', _pct(c['down_mean_pct']), _tone(c['down_mean_pct']))):
            box = soup.new_tag('div')
            box.append(_text(soup, 'dt', label))
            box.append(_text(soup, 'dd', value, tone))
            numbers.append(box)
        card.append(numbers)
        follow = [None if r is None else c['beta'] * r for r in market]
        chart = spark(_cumulative(c['daily']), compare=_cumulative(follow), width=260, height=48, zero=0,
                      label=f"{c['name']}实际走势与只跟大盘")
        if chart is not None:
            card.append(chart)
            card.append(_text(soup, 'small', '实线：实际累计涨跌；虚线：只跟大盘（贝塔×中证全指）', 'dash-legend'))
        chips = soup.new_tag('ul', attrs={'class': 'dash-checks'})
        for key, label in board['checks'].items():
            chips.append(_text(soup, 'li', ('✓ ' if c['checks'][key] else '✗ ') + label,
                               'dash-pass' if c['checks'][key] else 'dash-fail'))
        card.append(chips)
        card.append(_text(soup, 'p', f"失效价 {c['stop']:.2f} 元（近{board['rules']['stop_lookback']}日最低收盘，距现价{_pct(c['stop_distance_pct'])}）；"
                          f"日均成交额{c['amount_yi']:.1f}亿元；今日{_pct(c['today_pct'])}。", 'dash-stop'))
        cards.append(card)
    if not featured:
        cards.append(_text(soup, 'p', '今天没有独立上涨的股票。', 'dash-empty'))
    section.append(cards)
    rows = []
    for c in sorted(board['candidates'], key=lambda c: (order[c['status']], -c['passes'], -(c['t_alpha'] or 0))):
        rows.append(_row(soup, [
            (f"{c['name']} {c['code']}", None), (c['industry'], None),
            (board['status_names'][c['status']], f"dash-status-text-{c['status']}"), (f"{c['passes']}/{len(c['checks'])}", None),
            (_pct(c['total_pct']), _tone(c['total_pct'])), (_pct(c['own_pp'], unit=''), _tone(c['own_pp'])),
            (_pct(c['own5_pp'], unit=''), _tone(c['own5_pp'])), (f"{c['beta']:.2f}", None),
            (_pct(c['down_mean_pct']), _tone(c['down_mean_pct'])),
            (f"{c['amount_yi']:.1f}" if c['amount_yi'] is not None else '—', None),
            (f"{c['stop']:.2f}", None), (_pct(c['stop_distance_pct']), None)]))
    section.append(_text(soup, 'h3', '全部独立上涨股的检查结果'))
    section.append(_table(soup, ['股票', '行业', '状态', '通过', '20日涨跌', '独立收益', '近5日独立', '贝塔',
                                 '大盘跌日均值', '日均成交额(亿)', '失效价', '距失效价'], rows, 'dash-table dash-table-compact'))
    rules = board['rules']
    section.append(_text(soup, 'small', f"六项检查：近5日独立收益为正；大盘下跌日平均不跌；近3日涨幅比自身平均节奏多出的部分小于2倍日波动×√3；"
                         f"失效价（近{rules['stop_lookback']}日最低收盘）在现价下方{rules['stop_max_pct']:.0f}%以内；"
                         f"20日日均成交额≥{rules['liquidity_yi']:.0f}亿元；目标日未涨停（主板≥9.8%、创业板与科创板≥19.8%视为涨停）。"
                         '失效价按原始收盘价计算，期间若除权需另核。'))
    return section


def render_board_payload(soup, board):
    node = soup.new_tag('script', attrs={'id': 'decision-board-data', 'type': 'application/json'})
    light = {**board, 'candidates': [{k: v for k, v in c.items() if k != 'daily'} for c in board['candidates']]}
    node.string = json.dumps(light, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    script = soup.new_tag('script', attrs={'id': 'decision-board-driver'})
    script.string = (Path(__file__).resolve().parents[1] / 'templates/decision_board_charts.js').read_text(encoding='utf-8')
    return [node, script]


STRATEGY_ORDER = ('live_rule', 'alpha', 'alpha_regime', 'beta', 'beta_offense', 'stance', 'index')
STRATEGY_SHORT = {'alpha': '阿尔法每天买', 'alpha_regime': '阿尔法防守期不买', 'beta': '高贝塔每天买',
                  'beta_offense': '高贝塔只在进攻期买', 'stance': '简化轮换（均衡期一律买阿尔法）',
                  'live_rule': '当前规则', 'index': '中证全指持有'}
SIGNAL_NAMES = {'own': '近20日独立收益', 'own5': '近5日独立收益', 't_alpha': '独立收益t值', 'beta': '贝塔'}
COMPARISON_ORDER = ('399006.SZ', '000688.SH', '932000.CSI', 'equal_weight')
COMPARISON_SHORT = {'399006.SZ': '创业板指持有', '000688.SH': '科创50持有', '932000.CSI': '中证2000持有',
                    'equal_weight': '等权平均（理论参照）'}
NULL_SHORT = {'random': '随机挑10只（{seeds}次中位）', 'random_offense': '随机挑10只、只在进攻期（{seeds}次中位）'}


def _num(value, digits=2, unit=''):
    return '—' if value is None else f'{value:.{digits}f}{unit}'


def _against_random(count, seeds):
    if count is None:
        return ''
    if count <= seeds // 4:
        return f"好于多数随机结果（{seeds}次里{count}次达到）"
    if count >= seeds - seeds // 4:
        return f"不如多数随机结果（{seeds}次里{count}次不比它差）"
    return f"落在随机结果中间（{seeds}次里{count}次不比它差）"


def render_backtest(soup, backtest):
    section = soup.new_tag('section', attrs={'id': 'daily-backtest', 'class': 'sector-daily-section dash-section'})
    section.append(_text(soup, 'h2', '策略回测：这套规则过去有没有用'))
    stats = backtest['stats']
    full = {k: stats[k]['full'] for k in STRATEGY_ORDER}
    oos = {k: stats[k].get('out_of_sample') or {} for k in STRATEGY_ORDER}
    compared = {k: backtest['comparisons'][k] for k in COMPARISON_ORDER if k in (backtest.get('comparisons') or {})}
    null = backtest.get('null') or {}
    plan = backtest.get('plan')
    best = max((k for k in STRATEGY_ORDER if k != 'index'), key=lambda k: full[k].get('cagr_pct') or -1e9)
    holds = [('中证全指', full['index'])] + [(compared[k]['name'], compared[k]['full']) for k in ('399006.SZ', '000688.SH') if k in compared]
    text = (f"{backtest['start']}至{backtest['end']}，{backtest['sessions']}个交易日。持有对照："
            + '、'.join(f"{name}年化{_num(f.get('cagr_pct'), 1, '%')}（最大回撤{_num(f.get('max_drawdown_pct'), 1, '%')}）" for name, f in holds))
    if 'equal_weight' in compared:
        text += f"；等权平均持有全部可交易A股（每日再平衡、不计成本的理论参照）年化{_num(compared['equal_weight']['full'].get('cagr_pct'), 1, '%')}"
    text += '。' + '；'.join(f"{STRATEGY_SHORT[k]}年化{_num(full[k].get('cagr_pct'), 1, '%')}、回撤{_num(full[k].get('max_drawdown_pct'), 1, '%')}"
                           for k in ('live_rule', 'alpha', 'beta', 'beta_offense')) + '。'
    references = [(name, f.get('cagr_pct')) for name, f in holds]
    if 'equal_weight' in compared:
        references.append(('等权平均', compared['equal_weight']['full'].get('cagr_pct')))
    top_name, top_cagr = max(references, key=lambda item: -1e9 if item[1] is None else item[1])
    best_cagr = full[best].get('cagr_pct')
    if best_cagr is not None and top_cagr is not None:
        text += (f"七种做法里年化最高的是{STRATEGY_SHORT[best]}（{_num(best_cagr, 1, '%')}），"
                 + (f"没有超过{top_name}（{_num(top_cagr, 1, '%')}）。" if best_cagr < top_cagr else '超过了全部对照。'))
    if plan and '399006.SZ' in compared:
        anchor = compared['399006.SZ']['full']
        text += (f"{plan['name']}年化{_num(plan['full'].get('cagr_pct'), 1, '%')}、最大回撤{_num(plan['full'].get('max_drawdown_pct'), 1, '%')}；"
                 f"创业板指年化{_num(anchor.get('cagr_pct'), 1, '%')}、最大回撤{_num(anchor.get('max_drawdown_pct'), 1, '%')}，"
                 + ('同时满足“年化更高、回撤更浅”这条用户锚点。' if plan.get('beats_chinext') else '没有同时满足“年化更高、回撤更浅”这条用户锚点。'))
    section.append(_text(soup, 'p', text, 'dash-takeaway'))
    verdict = ''
    if 'random' in null:
        r, seeds = null['random'], null.get('seeds', 20)
        at_least = r.get('runs_at_least', {})
        verdict += (f"同样的买卖规则和成本、每天随机挑10只，跑{seeds}次：年化中位{_num(r['cagr_pct']['median'], 1, '%')}，"
                    f"范围{_num(r['cagr_pct']['min'], 1, '%')}至{_num(r['cagr_pct']['max'], 1, '%')}。"
                    f"{STRATEGY_SHORT['alpha']}{_against_random(at_least.get('alpha'), seeds)}；"
                    f"{STRATEGY_SHORT['beta']}{_against_random(at_least.get('beta'), seeds)}。")
    if 'random_offense' in null:
        ro = null['random_offense']
        verdict += (f"只在进攻期买时，随机挑选的夏普中位{_num(ro['sharpe']['median'], 2)}，"
                    f"{STRATEGY_SHORT['beta_offense']}{_num(full['beta_offense'].get('sharpe'), 2)}；"
                    f"它回撤小，主要因为平均只有{_num(full['beta_offense'].get('exposure_pct'), 0, '%')}的资金在场。")
    live, index_oos = oos.get('live_rule', {}).get('cagr_pct'), oos['index'].get('cagr_pct')
    if live is not None and index_oos is not None and live <= index_oos:
        verdict += (f"当前规则样本外年化{_num(live, 1, '%')}，跑输中证全指，说明“阿尔法近期有优势才买”在过去并不赚钱；"
                    f"因此现行建议里阿尔法只观察、贝塔只在进攻期做（“{STRATEGY_SHORT['beta_offense']}”这一行）。")
    years_span = backtest['sessions'] / 252
    sharpe = full[best].get('sharpe') or 0
    verdict += (f"{years_span:.1f}年的样本里，夏普比率本身的误差约±{((1 + sharpe * sharpe / 2) / years_span) ** 0.5:.2f}，"
                "各做法之间的差异大多在误差之内，排名只作参考，要用之后的对账继续检验。")
    section.append(_text(soup, 'p', verdict, 'dash-takeaway'))
    grid = soup.new_tag('div', attrs={'class': 'dash-grid dash-grid-wide'})
    chart_card = soup.new_tag('article', attrs={'class': 'dash-card'})
    chart_card.append(_text(soup, 'h3', '净值曲线（起点为1，扣成本）'))
    chart_card.append(soup.new_tag('div', attrs={'id': 'bt-equity-chart', 'class': 'dash-chart dash-bt-chart', 'role': 'img',
                                                 'aria-label': '七种做法与持有对照的净值曲线，灰色区间为规则设计时看过的时段'}))
    chart_card.append(_text(soup, 'small', f"灰色区间（{backtest['design_start']}起）是设计规则时看过的数据，之前是样本外。"
                         '虚线是持有对照，点线是等权平均（理论参照），浅灰虚线是随机挑选的逐日中位；点图例可显示或隐藏单条曲线。'))
    grid.append(chart_card)
    table_card = soup.new_tag('article', attrs={'class': 'dash-card'})
    table_card.append(_text(soup, 'h3', '收益与风险'))
    rows = []
    if plan:
        f, o = plan['full'], plan.get('out_of_sample') or {}
        rows.append(_row(soup, [(plan['name'], None), (_num(f.get('cagr_pct'), 1, '%'), _tone(f.get('cagr_pct'))),
                                (_num(f.get('max_drawdown_pct'), 1, '%'), None), (_num(f.get('sharpe'), 2), None),
                                ('—', None), ('—', None), ('—', None), ('—', None),
                                (_num(o.get('cagr_pct'), 1, '%'), _tone(o.get('cagr_pct')))], 'dash-row-plan'))
    if hold := backtest.get('plan_hold'):
        f, o = hold['full'], hold.get('out_of_sample') or {}
        rows.append(_row(soup, [(hold['name'], None), (_num(f.get('cagr_pct'), 1, '%'), _tone(f.get('cagr_pct'))),
                                (_num(f.get('max_drawdown_pct'), 1, '%'), None), (_num(f.get('sharpe'), 2), None),
                                ('—', None), ('—', None), ('—', None), ('—', None),
                                (_num(o.get('cagr_pct'), 1, '%'), _tone(o.get('cagr_pct')))], 'dash-row-plan-hold'))
    if pool := backtest.get('pool'):
        f, o = pool['full'], pool.get('out_of_sample') or {}
        rows.append(_row(soup, [(pool['name'], None), (_num(f.get('cagr_pct'), 1, '%'), _tone(f.get('cagr_pct'))),
                                (_num(f.get('max_drawdown_pct'), 1, '%'), None), (_num(f.get('sharpe'), 2), None),
                                ('—', None), ('—', None), ('—', None), ('—', None),
                                (_num(o.get('cagr_pct'), 1, '%'), _tone(o.get('cagr_pct')))], 'dash-row-pool'))
    for k in STRATEGY_ORDER:
        f, o = full[k], oos[k]
        rows.append(_row(soup, [(STRATEGY_SHORT[k], None), (_num(f.get('cagr_pct'), 1, '%'), _tone(f.get('cagr_pct'))),
                                (_num(f.get('max_drawdown_pct'), 1, '%'), None), (_num(f.get('sharpe'), 2), None),
                                (_num((f.get('win_rate') or 0) * 100, 0, '%') if f.get('win_rate') is not None else '—', None),
                                (_num(f.get('avg_trade_pct'), 2, '%'), _tone(f.get('avg_trade_pct'))),
                                (str(f.get('trades', '—')), None), (_num(f.get('exposure_pct'), 0, '%'), None),
                                (_num(o.get('cagr_pct'), 1, '%'), _tone(o.get('cagr_pct')))], f'dash-row-{k}'))
    for k, item in compared.items():
        f, o = item['full'], item.get('out_of_sample') or {}
        rows.append(_row(soup, [(COMPARISON_SHORT[k], None), (_num(f.get('cagr_pct'), 1, '%'), _tone(f.get('cagr_pct'))),
                                (_num(f.get('max_drawdown_pct'), 1, '%'), None), (_num(f.get('sharpe'), 2), None),
                                ('—', None), ('—', None), ('—', None), ('100%', None),
                                (_num(o.get('cagr_pct'), 1, '%'), _tone(o.get('cagr_pct')))], 'dash-row-compare'))
    for k in ('random', 'random_offense'):
        if k in null:
            item = null[k]
            rows.append(_row(soup, [(NULL_SHORT[k].format(seeds=null.get('seeds', 20)), None),
                                    (_num(item['cagr_pct']['median'], 1, '%'), _tone(item['cagr_pct']['median'])),
                                    (_num(item['max_drawdown_pct']['median'], 1, '%'), None), (_num(item['sharpe']['median'], 2), None),
                                    ('—', None), ('—', None), ('—', None), (_num(item['exposure_pct']['median'], 0, '%'), None),
                                    ('—', None)], 'dash-row-compare'))
    table_card.append(_table(soup, ['做法', '年化', '最大回撤', '夏普', '胜率', '每笔平均', '交易笔数', '持仓时间', '样本外年化'], rows,
                             'dash-table dash-table-compact'))
    if missing := backtest.get('missing_comparisons'):
        table_card.append(_text(soup, 'small', f"{'、'.join(missing)}的历史行情不完整，本次不列这条对照。"))
    years = sorted({y for k in STRATEGY_ORDER for y in stats[k].get('years', {})})
    year_rows = [_row(soup, [(STRATEGY_SHORT[k], None)] + [(_num(stats[k]['years'].get(y), 1, '%'), _tone(stats[k]['years'].get(y)))
                                                             for y in years]) for k in STRATEGY_ORDER]
    year_rows += [_row(soup, [(COMPARISON_SHORT[k], None)] + [(_num(item['years'].get(y), 1, '%'), _tone(item['years'].get(y)))
                                                                for y in years], 'dash-row-compare') for k, item in compared.items()]
    if pool := backtest.get('pool'):
        year_rows.insert(0, _row(soup, [(pool['name'], None)] + [(_num(pool['years'].get(y), 1, '%'), _tone(pool['years'].get(y)))
                                                                 for y in years], 'dash-row-pool'))
    if hold := backtest.get('plan_hold'):
        year_rows.insert(0, _row(soup, [(hold['name'], None)] + [(_num(hold['years'].get(y), 1, '%'), _tone(hold['years'].get(y)))
                                                                 for y in years], 'dash-row-plan-hold'))
    if plan:
        year_rows.insert(0, _row(soup, [(plan['name'], None)] + [(_num(plan['years'].get(y), 1, '%'), _tone(plan['years'].get(y)))
                                                                 for y in years], 'dash-row-plan'))
    chart_card.append(_text(soup, 'h4', '分年度收益'))
    chart_card.append(_table(soup, ['做法', *years], year_rows, 'dash-table dash-table-compact'))
    grid.append(table_card)
    section.append(grid)
    ic_card = table_card
    ic_card.append(_text(soup, 'h4', '信号有没有预测力（IC）'))
    ic_rows = []
    for name, item in backtest['ic'].items():
        ic_rows.append(_row(soup, [(SIGNAL_NAMES.get(name, name), None), (_num(item['mean_ic'], 3), _tone(item['mean_ic'])),
                                   (_num(item['icir'], 2), None), (_num(item['t_stat'], 2), None),
                                   (_num((item['positive_share'] or 0) * 100, 0, '%'), None),
                                   (_num(item['top_minus_bottom_pct'], 2, '个百分点'), _tone(item['top_minus_bottom_pct']))]))
    ic_card.append(_table(soup, ['信号', '平均IC', 'ICIR', 't值', 'IC为正的日子', '前20%减后20%（5日）'], ic_rows, 'dash-table dash-table-compact'))
    own = backtest['ic'].get('own') or {}
    if own.get('mean_ic') is not None and own.get('t_stat') is not None and abs(own['t_stat']) >= 2:
        direction = '越容易回落' if own['mean_ic'] < 0 else '越容易继续走强'
        ic_card.append(_text(soup, 'p', f"近20日独立收益越高的股票，之后5日{direction}：平均IC {own['mean_ic']:.3f}、t值 {own['t_stat']:.1f}，"
                             f"IC为正的日子只占{own['positive_share'] * 100:.0f}%。"
                             + ('这与“利好就是利空”的方向一致：追已经独立涨上去的股票，短期内吃亏的时候更多。'
                                '“反过来做”是看过这组数据后才有的想法，要用之后的新数据检验，本页不据此改规则。' if own['mean_ic'] < 0 else ''),
                             'dash-takeaway'))
    ic_card.append(_text(soup, 'small', 'IC：每天把全部合格股票按信号排序，和之后5日（次日开盘买、第5日收盘卖）的收益排序做相关；为正说明信号越高、之后越涨。'
                         't值按相邻5日重叠折算样本。'))
    rules = backtest['rules']
    section.append(_text(soup, 'small', f"规则与成本：信号只用当日及以前数据；次日开盘买（开盘涨停或高开超过{rules['chase_pct']:.0f}%不买），"
                         f"第{rules['hold']}个交易日收盘卖，收盘跌破失效价则次日开盘卖（跌停开盘卖不出顺延）；最多同时{rules['slots']}只、等权；"
                         f"买入成本{rules['buy_cost_pct']:.3f}%、卖出成本{rules['sell_cost_pct']:.3f}%（含印花税与滑点）。股票范围为当日沪深A股，"
                         f"按改名记录剔除当日ST、上市不足{rules['listed_days']}天的新股，退市股按当时日线保留。涨跌停按涨跌幅估算；未计冲击成本和容量。"
                         '回测结果不保证未来，只说明这套规则在过去这段行情里的表现。', 'dash-note'))
    series = ([{'key': 'small_cap_plan', 'name': plan['name'], 'kind': 'plan'}] if plan else [])
    series += ([{'key': 'small_cap_plan_hold', 'name': backtest['plan_hold']['name'], 'kind': 'reference'}] if backtest.get('plan_hold') else [])
    series += ([{'key': 'small_cap_pool', 'name': backtest['pool']['name'], 'kind': 'plan'}] if backtest.get('pool') else [])
    series += [{'key': k, 'name': STRATEGY_SHORT[k], 'kind': 'hold' if k == 'index' else 'strategy'} for k in STRATEGY_ORDER]
    series += [{'key': k, 'name': COMPARISON_SHORT[k], 'kind': 'reference' if k == 'equal_weight' else 'hold'} for k in compared]
    series += [{'key': k, 'name': NULL_SHORT[k].format(seeds=null.get('seeds', 20)), 'kind': 'random'}
               for k in ('random', 'random_offense') if k in null]
    series = [item for item in series if item['key'] in backtest['curves']]
    node = soup.new_tag('script', attrs={'id': 'strategy-backtest-data', 'type': 'application/json'})
    node.string = json.dumps({'dates': backtest['dates'], 'curves': {item['key']: backtest['curves'][item['key']] for item in series},
                              'design_start': backtest['design_start'], 'series': series,
                              'hidden': [k for k in ('alpha_regime', 'stance', 'random_offense') if k in backtest['curves']]},
                             ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    section.append(node)
    script = soup.new_tag('script', attrs={'id': 'strategy-backtest-driver'})
    script.string = (Path(__file__).resolve().parents[1] / 'templates/strategy_backtest_charts.js').read_text(encoding='utf-8')
    section.append(script)
    return section


def render_ledger(soup, rows, history):
    section = soup.new_tag('section', attrs={'id': 'daily-ledger', 'class': 'sector-daily-section dash-section'})
    section.append(_text(soup, 'h2', '建议对账'))
    done = [r for r in rows if r['status'] == '已对账']
    if not history or not history['records']:
        section.append(_text(soup, 'p', '每天的总体建议、检查全过名单与失效价会冻结在当天的快照里；从下一次正式生成起开始积累，'
                             '5个交易日后自动对账，看它们后来到底涨跌了多少。', 'dash-takeaway'))
        return section
    if not done:
        section.append(_text(soup, 'p', f"已记录{len(history['records'])}天的建议，还没有满5个交易日的，暂不能对账。", 'dash-takeaway'))
    else:
        wins = [r for r in done if r['alpha_pct'] is not None and r['index_pct'] is not None]
        beat = sum(r['alpha_pct'] > r['index_pct'] for r in wins)
        section.append(_text(soup, 'p', f"已对账{len(done)}天：检查全过名单5日后跑赢中证全指{beat}/{len(wins)}天。", 'dash-takeaway'))
    table_rows = [_row(soup, [(r['date'], None), (r['stance'], None), (r.get('interpretation_stance') or '—', None),
                              ('、'.join(p['name'] for p in r.get('picks', [])) or ('—' if r['status'] == '已对账' else r['status']), None),
                              (_pct(r.get('alpha_pct')), _tone(r.get('alpha_pct'))), (_pct(r.get('beta_pct')), _tone(r.get('beta_pct'))),
                              (_pct(r.get('index_pct')), _tone(r.get('index_pct'))), (str(r.get('stopped', '—')), None)])
                  for r in rows]
    section.append(_table(soup, ['建议日', '规则', '解读', '检查全过名单', '名单5日后', '高贝塔5日后', '中证全指', '期间破失效价'],
                          table_rows, 'dash-table dash-table-compact'))
    return section
