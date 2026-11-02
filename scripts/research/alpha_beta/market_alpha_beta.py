"""备用阿尔法／贝塔研究；不进入小盘日报。原规则和成本仅供历史比较。"""
"""Alpha/beta reading: is the market moving stocks together, or are stocks moving on their own?

User definitions (2026-10-29): alpha is a stock's own move with little relation to
the market; beta is the market's rise or fall carrying stocks with it. Each stock's
daily returns are regressed on the 中证全指 daily returns over the same sessions:
beta is the slope, the market share of daily movement is R², and the stock's own
return is its summed daily return minus beta times the summed market return.
"""
import json
from math import copysign, exp, fsum, isfinite, log1p, sqrt
from pathlib import Path
from statistics import median

from report.market_returns import price_rows, validate_market_returns, eligible_artifact_rows as _eligible

WINDOWS = (20, 60)
DEFAULT_WINDOW = 20
# Two-sided 5% Student t critical values for df = window - 2.
T_CRITICAL = {20: 2.1009, 60: 2.0017}
CHANCE_SHARE = 0.025
REGIME_MIN_POINTS = 20
LIST_SIZE = 20
CONCEPT_LIST_SIZE = 10
# The label follows what drove the move: a significant own part on an actual rise
# is the user's alpha; a move the market explains is beta. Daily co-movement (R²)
# is shown beside it rather than overriding a stock's own rally.
LABELS = {'alpha_up': '独立上涨', 'resilient': '抗跌', 'beta': '跟随大盘',
          'lagging': '跟涨乏力', 'alpha_down': '独立走弱', 'none': '无明显方向'}
VERDICTS = {'beta': '贝塔主导：大盘涨跌带动个股共振为主',
            'alpha': '阿尔法活跃：个股独立行情较多，大盘带动偏弱',
            'mixed': '贝塔与阿尔法并存'}


def _round(value, digits):
    return None if value is None else round(value, digits)


def _prefix(ys, xs):
    """Running sums over sessions where both the stock and the market have returns."""
    count, sx, sy, sxx, syy, sxy, growth = [0], [0.], [0.], [0.], [0.], [0.], [0.]
    for y, x in zip(ys, xs):
        ok = y is not None and x is not None
        count.append(count[-1] + ok)
        growth.append(growth[-1] + (log1p(y / 100) if ok else 0.))
        sx.append(sx[-1] + (x if ok else 0.))
        sy.append(sy[-1] + (y if ok else 0.))
        sxx.append(sxx[-1] + (x * x if ok else 0.))
        syy.append(syy[-1] + (y * y if ok else 0.))
        sxy.append(sxy[-1] + (x * y if ok else 0.))
    return count, sx, sy, sxx, syy, sxy, growth


def _fit(sums, start, end):
    """OLS of stock on market for sessions [start, end); None unless every session is present."""
    count, sx, sy, sxx, syy, sxy, growth = sums
    n = end - start
    if n < 3 or count[end] - count[start] != n:
        return None
    x, y = sx[end] - sx[start], sy[end] - sy[start]
    vx = sxx[end] - sxx[start] - x * x / n
    vy = syy[end] - syy[start] - y * y / n
    cxy = sxy[end] - sxy[start] - x * y / n
    if vx <= 1e-12:
        return None
    beta = cxy / vx
    corr = max(-1., min(1., cxy / sqrt(vx * vy))) if vy > 1e-12 else 0.
    residual = max(vy - beta * cxy, 0.) / (n - 2)
    t_corr = corr * sqrt((n - 2) / (1 - corr * corr)) if vy > 1e-12 and corr * corr < 1 else None
    return {'n': n, 'mx': x / n, 'my': y / n, 'vx': vx, 'vy': vy, 'cxy': cxy, 'ols_beta': beta,
            'se_beta': sqrt(residual / vx), 'r2': corr * corr, 't_corr': t_corr,
            'total_pct': (exp(growth[end] - growth[start]) - 1) * 100}


def _shrink(fits):
    """Vasicek adjustment: a beta estimated from few sessions moves toward the
    cross-sectional mean in proportion to its own sampling uncertainty."""
    betas = [fit['ols_beta'] for fit in fits]
    mean = fsum(betas) / len(betas) if betas else 1.
    variance = fsum((b - mean) ** 2 for b in betas) / (len(betas) - 1) if len(betas) > 1 else 0.
    for fit in fits:
        spread = variance + fit['se_beta'] ** 2
        weight = variance / spread if spread > 0 else 1.
        beta = weight * fit['ols_beta'] + (1 - weight) * mean
        intercept = fit['my'] - beta * fit['mx']
        residual = max(fit['vy'] - 2 * beta * fit['cxy'] + beta * beta * fit['vx'], 0.) / (fit['n'] - 2)
        se = sqrt(residual * (1 / fit['n'] + fit['mx'] ** 2 / fit['vx']))
        fit.update(beta=beta, weight=weight, intercept=intercept, t_alpha=intercept / se if se > 0 else None)
    return {'mean': mean, 'variance': variance}


def _label(fit, window):
    critical = T_CRITICAL[window]
    if fit['t_alpha'] is not None and fit['t_alpha'] >= critical:
        return 'alpha_up' if fit['total_pct'] > 0 else 'resilient'
    if fit['t_alpha'] is not None and fit['t_alpha'] <= -critical:
        return 'alpha_down' if fit['total_pct'] < 0 else 'lagging'
    return 'beta' if fit['t_corr'] is not None and fit['t_corr'] >= critical else 'none'


def _market_returns(value):
    rows = {row['date']: (row['close'] - row['pre_close']) / row['pre_close'] * 100
            for row in value['benchmark']['rows']}
    return [rows.get(day) for day in value['trade_dates']]


def _stock_returns(value):
    days = value['trade_dates']
    returns = [[None] * len(days) for _ in value['codes']]
    for column, day in enumerate(days):
        for index, close, previous, *_ in price_rows(value, day):
            returns[index][column] = (close - previous) / previous * 100
    return returns




def _stock_detail(fit, ys, xs, start, end, window):
    stock, market = ys[start:end], xs[start:end]
    market_part = fit['beta'] * fsum(market)
    own = fsum(stock) - market_part
    own5 = fsum(stock[-5:]) - fit['beta'] * fsum(market[-5:])
    down = [a for a, b in zip(stock, market) if b < 0]
    up = [a for a, b in zip(stock, market) if b > 0]
    return {'label': _label(fit, window), 'beta': fit['beta'], 'ols_beta': fit['ols_beta'], 'r2': fit['r2'], 't_alpha': fit['t_alpha'],
            'total_pct': fit['total_pct'], 'sum_pct': fsum(stock), 'market_pp': market_part, 'own_pp': own,
            'own5_pp': own5, 'down_days': len(down), 'up_days': len(up),
            'down_mean_pct': fsum(down) / len(down) if down else None,
            'up_mean_pct': fsum(up) / len(up) if up else None}


def _regime(points, today):
    values = [p['sync'] for p in points if p['sync'] is not None]
    current = points[-1]
    strength = None
    if len(values) >= REGIME_MIN_POINTS and current['sync'] is not None:
        rank = sum(v <= current['sync'] for v in values) / len(values)
        strength = '强' if rank >= 2 / 3 else '弱' if rank <= 1 / 3 else '中'
    else:
        rank = None
    # Chance gives about 2.5% significant positive own parts, whether or not the price rose.
    expected = current['complete'] * CHANCE_SHARE
    outperform = current['alpha_up'] + current['resilient']
    ratio = outperform / expected if expected else None
    abundance = None if ratio is None else '多' if ratio >= 2 else '一般' if ratio >= 1 else '少'
    if strength is None or abundance is None:
        verdict = None
    elif strength == '强' and abundance in ('少', '一般'):
        verdict = 'beta'
    elif strength == '弱' and abundance in ('多', '一般'):
        verdict = 'alpha'
    else:
        verdict = 'mixed'
    return {'verdict': verdict, 'verdict_text': VERDICTS.get(verdict), 'strength': strength,
            'sync': current['sync'], 'sync_rank': rank, 'sync_points': len(values),
            'alpha_up': current['alpha_up'], 'resilient': current['resilient'], 'outperform': outperform,
            'complete': current['complete'], 'expected': expected,
            'ratio': ratio, 'abundance': abundance, **today}


def build_alpha_beta(value, target_date, *, concepts=None, tracked_ids=()):
    """Return the reading projection; raises when the frozen facts are not for target_date."""
    validate_market_returns(value, target_date)
    days = value['trade_dates']
    market = _market_returns(value)
    returns = _stock_returns(value)
    eligible, excluded = _eligible(value)
    sums = {index: _prefix(returns[index], market) for index in eligible}
    profile = value['profile']
    total = len(days)

    # Market regime over every 20-session window that ends inside the data span.
    points = []
    for end in range(DEFAULT_WINDOW, total + 1):
        fits = [(index, fit) for index in eligible
                if (fit := _fit(sums[index], end - DEFAULT_WINDOW, end)) is not None]
        _shrink([fit for _, fit in fits])
        labels = [_label(fit, DEFAULT_WINDOW) for _, fit in fits]
        day = days[end - 1]
        same = [r[end - 1] for r in (returns[i] for i in eligible) if r[end - 1] is not None]
        m = market[end - 1]
        nonzero = [r for r in same if r != 0]
        points.append({
            'date': day, 'market_pct': m,
            'median_pct': median(same) if same else None,
            'up_count': sum(r > 0 for r in same), 'down_count': sum(r < 0 for r in same), 'valid_count': len(same),
            'same_share': (sum(copysign(1, r) == copysign(1, m) for r in nonzero) / len(nonzero) * 100
                           if nonzero and m not in (None, 0) else None),
            'sync': median(fit['r2'] for _, fit in fits) if fits else None,
            'alpha_up': labels.count('alpha_up'), 'resilient': labels.count('resilient'),
            'complete': len(fits)})
    today = {key: points[-1][key] for key in ('market_pct', 'median_pct', 'up_count', 'down_count',
                                               'valid_count', 'same_share')}
    regime = _regime(points, today)

    windows, listed = {}, set()
    for window in WINDOWS:
        if total < window:
            continue
        start, end = total - window, total
        fits = [(index, fit) for index in eligible if (fit := _fit(sums[index], start, end)) is not None]
        if not fits:
            continue
        prior = _shrink([fit for _, fit in fits])
        stocks = [(index, _stock_detail(fit, returns[index], market, start, end, window)) for index, fit in fits]
        def pick(label, key):
            return sorted((s for s in stocks if s[1]['label'] == label), key=lambda s: (key(s[1]), value['codes'][s[0]]))
        ranked = {'alpha_up': pick('alpha_up', lambda d: -d['own_pp']),
                  'resilient': pick('resilient', lambda d: -d['own_pp']),
                  'alpha_down': pick('alpha_down', lambda d: d['own_pp']),
                  'beta': pick('beta', lambda d: -d['r2'])}
        industries = {}
        for index, detail in stocks:
            industry = profile['industries'][index] or '行业待确认'
            bucket = industries.setdefault(industry, [0, 0])
            bucket[1] += 1
            bucket[0] += detail['label'] == 'alpha_up'
        clusters = sorted(((name, hit, size) for name, (hit, size) in industries.items() if hit),
                          key=lambda row: (-row[1], -row[1] / row[2], row[0]))[:5]
        counts = {key: sum(d['label'] == key for _, d in stocks) for key in LABELS}
        lists = {}
        for key, rows in ranked.items():
            lists[key] = []
            for index, detail in rows[:LIST_SIZE]:
                listed.add(index)
                lists[key].append({'code': value['codes'][index], 'name': profile['names'][index] or '名称待确认',
                                   'industry': profile['industries'][index] or '行业待确认',
                                   **{k: _round(v, 4) if isinstance(v, float) else v for k, v in detail.items()}})
        windows[window] = {
            'window': window, 'start_date': days[start], 'end_date': days[end - 1],
            'complete': len(stocks), 'counts': counts, 'expected_by_chance': len(stocks) * CHANCE_SHARE,
            't_critical': T_CRITICAL[window], 'beta_prior': {k: _round(v, 4) for k, v in prior.items()},
            'lists': lists,
            'clusters': [{'industry': name, 'alpha_up': hit, 'complete': size} for name, hit, size in clusters],
            'scatter': [[_round(d['r2'], 3), _round(d['own_pp'], 2), list(LABELS).index(d['label']), index]
                        for index, d in stocks],
        }
    if not windows:
        # A dated gap (e.g. a missing benchmark session) means no judgement, not untrusted facts.
        return None
    scatter_codes = sorted({row[3] for w in windows.values() for row in w['scatter']})
    position = {index: i for i, index in enumerate(scatter_codes)}
    for w in windows.values():
        for row in w['scatter']:
            row[3] = position[row[3]]
    return {
        'schema': 'market_alpha_beta.v1', 'target_date': target_date,
        'benchmark': {'code': value['benchmark']['code'], 'name': value['benchmark']['name']},
        'query_date': value['query_date'], 'profile_query_date': profile['query_date'],
        'source_hash': value['artifact_hash'], 'dates': days,
        'market': [_round(v, 6) for v in market], 'regime': regime,
        'series': [{k: _round(v, 6) if isinstance(v, float) else v for k, v in p.items()} for p in points],
        'universe': {'priced': len(value['codes']), 'eligible': len(eligible), 'excluded': excluded,
                     'st_basis': 'target_day_list' if value['st_codes'] is not None else 'name_at_query',
                     'issues': value['issues'], 'rejected_rows': value['rejected_rows']},
        'windows': {str(k): v for k, v in windows.items()},
        'default_window': DEFAULT_WINDOW if DEFAULT_WINDOW in windows else min(windows),
        'labels': LABELS, 'label_keys': list(LABELS),
        'scatter_stocks': {'codes': [value['codes'][i] for i in scatter_codes],
                           'names': [profile['names'][i] or '名称待确认' for i in scatter_codes],
                           'industries': [profile['industries'][i] or '行业待确认' for i in scatter_codes]},
        'paths': {value['codes'][i]: [_round(r, 6) for r in returns[i]] for i in sorted(listed)},
        'concepts': concept_alpha_beta(concepts, days, market, tracked_ids) if concepts else None,
    }


def concept_trend_returns(trend):
    """Daily concept index changes already frozen with the sector history."""
    ranking = trend.get('ranking_returns') or trend.get('heat') or {}
    names = {t['track_id']: t.get('name') for t in trend.get('tracks', [])}
    return {'dates': ranking.get('dates') or [],
            'rows': [{'track_id': r['track_id'], 'name': names.get(r['track_id']) or r.get('name'),
                      'pct': r['pct']} for r in ranking.get('rows', [])]}


def concept_alpha_beta(concepts, days, market, tracked_ids=()):
    """The same market model applied to concept indices; overlapping baskets are not summed."""
    by_date = dict(zip(days, market))
    dates = concepts['dates']
    xs = [by_date.get(day) for day in dates]
    tracked = set(tracked_ids)
    result = {}
    for window in WINDOWS:
        if len(dates) < window:
            continue
        start, end = len(dates) - window, len(dates)
        fits = []
        for row in concepts['rows']:
            ys = [v if isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v) else None
                  for v in row['pct']]
            fit = _fit(_prefix(ys, xs), start, end)
            if fit is not None:
                fits.append((row, ys, fit))
        if not fits:
            continue
        _shrink([fit for _, _, fit in fits])
        rows = []
        for row, ys, fit in fits:
            detail = _stock_detail(fit, ys, xs, start, end, window)
            rows.append({'track_id': row['track_id'], 'name': row['name'], 'tracked': row['track_id'] in tracked,
                         **{k: _round(v, 4) if isinstance(v, float) else v for k, v in detail.items()}})
        result[str(window)] = {
            'window': window, 'start_date': dates[start], 'end_date': dates[end - 1], 'complete': len(rows),
            'counts': {key: sum(r['label'] == key for r in rows) for key in LABELS},
            'stronger': sorted((r for r in rows if r['label'] in ('alpha_up', 'resilient')),
                               key=lambda r: (-r['own_pp'], r['name']))[:CONCEPT_LIST_SIZE],
            'beta': sorted((r for r in rows if r['label'] == 'beta'),
                           key=lambda r: (-r['r2'], r['name']))[:CONCEPT_LIST_SIZE],
            'tracked': sorted((r for r in rows if r['tracked']), key=lambda r: -r['own_pp']),
        }
    return result or None


# ---------------------------------------------------------------- rendering


def _sign(value, digits=2, unit='%'):
    if value is None:
        return '事实不足'
    shown = 0. if abs(value) < 0.5 * 10 ** -digits else value
    return f'{shown:+.{digits}f}{unit}'


def _tone(value):
    if value is None or abs(value) < 0.005:
        return 'ab-flat'
    return 'ab-up' if value > 0 else 'ab-down'


LIST_TITLES = {'alpha_up': '独立上涨（阿尔法）', 'resilient': '抗跌', 'alpha_down': '独立走弱',
               'beta': '跟随大盘最紧'}


def headline(projection):
    regime = projection['regime']
    window = projection['windows'].get(str(projection['default_window'])) or {}
    if not regime['verdict']:
        return None
    clusters = '、'.join(f"{c['industry']}{c['alpha_up']}只" for c in window.get('clusters', [])[:3])
    position = {'强': '偏高', '弱': '偏低'}.get(regime['strength'], '居中')
    text = (f"{regime['verdict_text']}。近20日共振度{regime['sync']:.2f}（近{regime['sync_points']}个窗口中{position}）；"
            f"独立上涨{regime['alpha_up']}只、抗跌{regime['resilient']}只，独立收益显著为正合计{regime['outperform']}只，"
            f"随机约{regime['expected']:.0f}只")
    if clusters:
        text += f'；独立上涨集中在{clusters}'
    return text + '。'


def _metric(soup, label, value, note, tone=None):
    from report.fact_utils import html_text as _text
    node = soup.new_tag('div', attrs={'class': 'ab-metric'})
    node.append(_text(soup, 'small', label))
    strong = _text(soup, 'strong', value)
    if tone:
        strong['class'] = tone
    node.append(strong)
    node.append(_text(soup, 'p', note))
    return node


def _number_cells(soup, line, row, keys):
    from report.fact_utils import html_text as _text
    for key in keys:
        cell = _text(soup, 'td', _sign(row[key], unit='%' if key == 'total_pct' else ''))
        cell['class'] = _tone(row[key])
        line.append(cell)


def _table(soup, rows, *, concept=False, with_type=False):
    from report.fact_utils import html_text as _text
    wrapper = soup.new_tag('div', attrs={'class': 'table-responsive ab-table-wrap'})
    table = soup.new_tag('table', attrs={'class': 'table ab-table', 'data-ab-table': 'concept' if concept else 'stock'})
    head = soup.new_tag('thead')
    tr = soup.new_tag('tr')
    columns = ((['概念', '窗口涨跌', '独立收益', '关联度', '贝塔'] + (['类型'] if with_type else [])) if concept else
               ['股票', '行业', '窗口涨跌', '大盘贡献', '独立收益', '近5日独立', '关联度', '贝塔', '大盘跌日均值'])
    for column in columns:
        tr.append(_text(soup, 'th', column))
    head.append(tr)
    table.append(head)
    body = soup.new_tag('tbody')
    for row in rows:
        line = soup.new_tag('tr')
        if concept:
            cell = soup.new_tag('td')
            cell.append(_text(soup, 'strong', row['name']))
            if row.get('tracked'):
                cell.append(_text(soup, 'small', '跟踪中'))
            line.append(cell)
            _number_cells(soup, line, row, ('total_pct', 'own_pp'))
        else:
            line['data-ab-code'] = row['code']
            cell = soup.new_tag('td')
            button = soup.new_tag('button', attrs={'type': 'button', 'class': 'ab-pick', 'data-ab-code': row['code'],
                                                   'aria-label': f"{row['name']}，查看走势"})
            button.append(_text(soup, 'strong', row['name']))
            button.append(_text(soup, 'small', row['code']))
            cell.append(button)
            line.append(cell)
            line.append(_text(soup, 'td', row['industry']))
            _number_cells(soup, line, row, ('total_pct', 'market_pp', 'own_pp', 'own5_pp'))
        line.append(_text(soup, 'td', f"{row['r2']:.2f}"))
        line.append(_text(soup, 'td', f"{row['beta']:.2f}"))
        if concept and with_type:
            line.append(_text(soup, 'td', LABELS[row['label']]))
        elif not concept:
            cell = _text(soup, 'td', _sign(row['down_mean_pct']) + f"（{row['down_days']}日）")
            cell['class'] = _tone(row['down_mean_pct'])
            line.append(cell)
        body.append(line)
    if not rows:
        empty = soup.new_tag('tr')
        cell = _text(soup, 'td', '这一类本窗口没有概念。' if concept else '这一类本窗口没有股票。')
        cell['colspan'] = str(len(columns))
        empty.append(cell)
        body.append(empty)
    table.append(body)
    wrapper.append(table)
    return wrapper


def window_summary(window):
    n = window['counts']
    return (f"{window['start_date']}至{window['end_date']}，合格股票{window['complete']}只：独立上涨{n['alpha_up']}只、"
            f"抗跌{n['resilient']}只、跟随大盘{n['beta']}只、跟涨乏力{n['lagging']}只、"
            f"独立走弱{n['alpha_down']}只、无明显方向{n['none']}只。下表各取前20；点股票名看走势。")


def render_alpha_beta(soup, projection, *, compact=False):
    """compact: the decision board above already states the verdict and the headline numbers."""
    from report.fact_utils import html_text as _text
    regime = projection['regime']
    default = str(projection['default_window'])
    window = projection['windows'][default]
    section = soup.new_tag('section', attrs={'id': 'daily-alphabeta', 'class': 'sector-daily-section daily-alphabeta'
                                             + (' dash-section' if compact else ''),
                                             'data-ab-window': default, 'data-ab-list': 'alpha_up'})
    if compact:
        section.append(_text(soup, 'h2', '大盘明细：贝塔与阿尔法'))
        position = {'强': '近两个月偏高', '弱': '近两个月偏低'}.get(regime['strength'], '近两个月居中')
        section.append(_text(soup, 'p', (f"近20日共振度{regime['sync']:.2f}（{position}），独立上涨{regime['alpha_up']}只、"
                                         f"抗跌{regime['resilient']}只；下面是逐日走势、个股分类、全市场分布和概念。")
                             if regime['sync'] is not None else '共振度资料不足；下面是可取得的个股分类与分布。'))
        section.select('p')[-1]['class'] = 'dash-takeaway'
        _render_alpha_beta_body(soup, section, projection, default, window, compact=True)
        return section
    section.append(_text(soup, 'small', '阿尔法 · 贝塔'))
    section.append(_text(soup, 'h2', '今天是贝塔行情，还是阿尔法行情？'))
    verdict = _text(soup, 'p', regime['verdict_text'] or '资料不足，暂不下结论')
    verdict['class'] = 'ab-verdict' + (f" ab-verdict-{regime['verdict']}" if regime['verdict'] else '')
    section.append(verdict)
    section.append(_text(soup, 'p', '贝塔：大盘涨跌带动个股一起动。阿尔法：个股自己的行情，与大盘涨跌关系不大。'
                         f"每只股票用最近{default}个交易日的日涨跌对{projection['benchmark']['name']}回归，"
                         '拆成“大盘贡献”（贝塔×大盘涨跌）和“独立收益”（其余部分）。'
                         '独立收益显著为正、窗口内确实上涨的，算独立上涨；显著为正但仍下跌的，只算抗跌。'))
    metrics = soup.new_tag('div', attrs={'class': 'ab-metrics'})
    strength_note = (f"近{regime['sync_points']}个窗口中排第{round(regime['sync_rank'] * 100)}百分位"
                     if regime['sync_rank'] is not None else '可比窗口不足，不判断高低')
    metrics.append(_metric(soup, '大盘带动（近20日共振度）',
                           (f"{regime['sync']:.2f} · {regime['strength']}" if regime['strength'] else
                            (f"{regime['sync']:.2f}" if regime['sync'] is not None else '事实不足')),
                           '个股日波动中被大盘解释的比例（中位数）；' + strength_note))
    metrics.append(_metric(soup, '独立行情（近20日独立上涨）',
                           f"{regime['alpha_up']}只 · {regime['abundance'] or '事实不足'}",
                           f"另有抗跌{regime['resilient']}只；独立收益显著为正共{regime['outperform']}只，"
                           f"随机约{regime['expected']:.0f}只（合格股票{regime['complete']}只×2.5%）"
                           + (f"，为随机的{regime['ratio']:.1f}倍" if regime['ratio'] is not None else '')))
    same = regime['same_share']
    metrics.append(_metric(soup, f"今日 {projection['benchmark']['name']}",
                           _sign(regime['market_pct']), f"个股中位数{_sign(regime['median_pct'])}；"
                           f"上涨{regime['up_count']}只、下跌{regime['down_count']}只", _tone(regime['market_pct'])))
    metrics.append(_metric(soup, '今日与大盘同向', f'{same:.0f}%' if same is not None else '事实不足',
                           '与大盘同方向涨跌的个股占比；两者无关时约50%'))
    section.append(metrics)
    if window['clusters']:
        section.append(_text(soup, 'p', '独立上涨集中的行业：' + '、'.join(
            f"{c['industry']} {c['alpha_up']}只（占该行业{c['alpha_up'] / c['complete'] * 100:.0f}%）"
            for c in window['clusters']) + '。行业为查询日归属。'))
    _render_alpha_beta_body(soup, section, projection, default, window)
    return section


def _render_alpha_beta_body(soup, section, projection, default, window, *, compact=False):
    from report.fact_utils import html_text as _text
    regime = projection['regime']
    section.append(soup.new_tag('div', attrs={'id': 'ab-regime-chart', 'class': 'ab-chart ab-regime-chart', 'role': 'img',
                                             'aria-label': '近两个月大盘涨跌、同向比例、共振度与独立上涨只数'}))
    section.append(_text(soup, 'small', '上图：中证全指日涨跌（柱）与当天同向比例（线）。下图：以当天为终点的20日共振度（线），'
                         '独立上涨与抗跌只数（堆叠柱），虚线为随机预期。共振度越高，个股越像跟着大盘走；柱子高出虚线越多，独立行情越真实。'))

    section.append(_text(soup, 'h3', '个股：谁在走自己的行情'))
    controls = soup.new_tag('div', attrs={'class': 'ab-controls'})
    tabs = soup.new_tag('div', attrs={'class': 'reading-tags', 'role': 'group', 'aria-label': '个股类别'})
    for key, title in LIST_TITLES.items():
        button = soup.new_tag('button', attrs={'type': 'button', 'class': 'reading-tag', 'data-ab-list': key,
                                               'aria-pressed': str(key == 'alpha_up').lower()})
        button.append(_text(soup, 'strong', title))
        button.append(_text(soup, 'small', f"{window['counts'][key]}只"))
        tabs.append(button)
    controls.append(tabs)
    sizes = soup.new_tag('div', attrs={'class': 'reading-tags', 'role': 'group', 'aria-label': '观察窗口'})
    for size in WINDOWS:
        button = _text(soup, 'button', f'{size}日')
        button.attrs.update({'type': 'button', 'class': 'reading-tag', 'data-ab-window': str(size),
                             'aria-pressed': str(str(size) == default).lower()})
        if str(size) not in projection['windows']:
            button['disabled'] = ''
            button['title'] = f'尚缺完整{size}日资料'
        sizes.append(button)
    controls.append(sizes)
    section.append(controls)
    summary = _text(soup, 'p', window_summary(window))
    summary['id'] = 'ab-window-summary'
    section.append(summary)
    grid = soup.new_tag('div', attrs={'class': 'ab-stock-grid'})
    table_box = soup.new_tag('div', attrs={'id': 'ab-stock-table', 'class': 'ab-stock-table'})
    table_box.append(_table(soup, window['lists']['alpha_up']))
    grid.append(table_box)
    side = soup.new_tag('article', attrs={'class': 'ab-path-card'})
    side.append(_text(soup, 'h4', '实际走势 vs 只跟大盘'))
    side.append(soup.new_tag('p', attrs={'id': 'ab-path-summary', 'class': 'ab-path-summary', 'aria-live': 'polite'}))
    side.append(soup.new_tag('div', attrs={'id': 'ab-path-chart', 'class': 'ab-chart ab-path-chart', 'role': 'img',
                                          'aria-label': '所选个股实际累计涨跌、按贝塔只跟大盘的累计涨跌与中证全指'}))
    side.append(_text(soup, 'small', '“只跟大盘”= 每天用贝塔×中证全指当日涨跌累计；实际走势与它的距离就是独立收益。'))
    grid.append(side)
    section.append(grid)
    section.append(_text(soup, 'h4', '全市场分布：关联度 × 独立收益'))
    section.append(soup.new_tag('div', attrs={'id': 'ab-scatter-chart', 'class': 'ab-chart ab-scatter-chart', 'role': 'img',
                                             'aria-label': '每只合格股票的大盘关联度与独立收益'}))
    section.append(_text(soup, 'small', '横轴是每天跟大盘一起波动的程度，虚线右侧为显著同步；纵轴是扣掉大盘贡献后的独立收益。'
                         '紫色大点是独立上涨：越靠左上，越是自己的行情。悬浮查看名称与数值。'))

    concepts = projection.get('concepts') or {}
    concept_window = concepts.get(default)
    if concept_window:
        n = concept_window['counts']
        section.append(_text(soup, 'h3', '概念板块：独立行情还是跟着大盘'))
        section.append(_text(soup, 'p', f"同花顺概念指数用同一方法；{concept_window['start_date']}至{concept_window['end_date']}，"
                             f"完整概念{concept_window['complete']}个：独立上涨{n['alpha_up']}个、抗跌{n['resilient']}个、"
                             f"跟随大盘{n['beta']}个、跟涨乏力{n['lagging']}个、独立走弱{n['alpha_down']}个。概念成分互相重叠，不相加。"))
        section.select('p')[-1]['id'] = 'ab-concept-summary'
        concept_grid = soup.new_tag('div', attrs={'id': 'ab-concepts', 'class': 'ab-concept-grid'})
        for key, title, with_type in (('stronger', '比大盘推算更强的概念', True), ('beta', '跟随大盘最紧的概念', False)):
            card = soup.new_tag('div', attrs={'class': 'ab-concept-card', 'data-ab-concepts': key})
            card.append(_text(soup, 'h4', title))
            card.append(_table(soup, concept_window[key], concept=True, with_type=with_type))
            concept_grid.append(card)
        if concept_window['tracked']:
            card = soup.new_tag('div', attrs={'class': 'ab-concept-card ab-concept-tracked', 'data-ab-concepts': 'tracked'})
            card.append(_text(soup, 'h4', '跟踪中的概念'))
            card.append(_table(soup, concept_window['tracked'], concept=True, with_type=True))
            concept_grid.append(card)
        section.append(concept_grid)

    details = soup.new_tag('details', attrs={'class': 'ab-method'})
    details.append(_text(soup, 'summary', '口径与限制'))
    universe = projection['universe']
    for text in (
        f"大盘基准：{projection['benchmark']['name']}（{projection['benchmark']['code']}）。股票范围：沪深A股，"
        f"剔除目标日ST {universe['excluded']['st']}只、资料区间内新上市 {universe['excluded']['new_listing']}只；北交所不含。"
        + ('ST按目标日名单。' if universe['st_basis'] == 'target_day_list' else 'ST名单未取得，按查询日简称识别。'),
        '日涨跌按来源收盘价与前收盘价计算；窗口内每天都有涨跌的股票才参与，缺一天就不判断，不补零。',
        '贝塔按全市场分布做了收缩（Vasicek）：20个交易日估出的极端贝塔，按其不确定程度拉向平均值，避免高波动股的大盘贡献被夸大。',
        f"显著：t值≥{T_CRITICAL[20]}（20日）或≥{T_CRITICAL[60]}（60日），约为5%双侧显著。独立收益显著为正且窗口内上涨为独立上涨，"
        '仍下跌为抗跌；显著为负且下跌为独立走弱，仍上涨为跟涨乏力；独立收益不显著而与大盘显著正相关为跟随大盘，其余为无明显方向。'
        '关联度（R²）表示每天跟大盘一起波动的程度，独立上涨的股票也可能关联度不低：它同时有贝塔和阿尔法。',
        '大盘贡献与独立收益按日涨跌相加拆分，与复利计算的窗口涨跌略有出入，大涨大跌的股票出入更大。',
        '共振度看它在近两个月窗口中的位置：上三分之一为强、下三分之一为弱。独立收益显著为正的只数（独立上涨加抗跌）'
        '与随机预期（合格股票×2.5%）比较：2倍及以上为多，1至2倍为一般，不足1倍为少。这些分档是阅读约定，不是买卖条件。',
        f"股票简称与行业为{projection['profile_query_date']}查询的资料，不是历史简称或历史行业；行情查询于{projection['query_date']}。"
        '20个交易日样本小，涨跌停会截断涨跌，标签可能随窗口变化；结论不证明独立行情会持续，也不是买卖指令。',
    ):
        details.append(_text(soup, 'p', text))
    gaps = [f"{issue['date']} {issue['reason']}" for issue in universe['issues']]
    rejected = sum(universe['rejected_rows'].values())
    if rejected:
        gaps.append(f'收盘价无效或与来源涨跌幅不一致而剔除的行情{rejected}行')
    if gaps:
        details.append(_text(soup, 'p', '资料缺口：' + '；'.join(gaps) + '。'))
    section.append(details)
    node = soup.new_tag('script', attrs={'id': 'market-alpha-beta-data', 'type': 'application/json'})
    node.string = json.dumps(projection, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    section.append(node)
    script = soup.new_tag('script', attrs={'id': 'market-alpha-beta-driver'})
    script.string = (Path(__file__).with_name('market_alpha_beta_charts.js')).read_text(encoding='utf-8')
    section.append(script)
