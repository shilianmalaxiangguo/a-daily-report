"""Small dated opportunity comparison, separate from accounts and orders."""
from copy import deepcopy
from datetime import datetime
import math
from statistics import median
from zoneinfo import ZoneInfo

from report.sector_fact_loader import _target_date
from report.sector_reading_history import evidence_hash, numeric_trend_view

SCHEMA = 'sector_choice.v1'
METHOD = ('比较完整5日与20日日收益复利；两窗上涨且5日强于中证全指、最新日前已有上涨，'
          '才列延续比较。优先保留仍符合这些事实的前次关注，不因新榜首自动替换。'
          '首次比较按5日强弱排列，以20日较强方向作对照；这是本轮可修正的比较方法，不是买入条件。')


def _compound(values):
    if not values or any(v is None for v in values):
        return None
    return (math.prod(1 + v / 100 for v in values) - 1) * 100


def _prior_reference(previous, target):
    if previous is None:
        return None
    if (previous.get('schema') not in (SCHEMA, 'sector_attention_ref.v1')
            or previous.get('artifact_hash') != evidence_hash({k: v for k, v in previous.items() if k != 'artifact_hash'})
            or not previous.get('target_date') or previous['target_date'] >= target):
        raise ValueError('前次关注日期或记录不符，不能当作持仓继承')
    if previous['schema'] == 'sector_attention_ref.v1':
        return deepcopy(previous)
    primary = previous.get('primary')
    if not primary and (previous.get('continuity') or {}).get('kind') == 'unresolved':
        primary = (previous.get('previous_input') or {}).get('primary')
    ref = {'schema': 'sector_attention_ref.v1', 'target_date': previous['target_date'],
           'primary': {k: primary[k] for k in ('track_id', 'name')} if primary else None,
           'record_hash': previous['artifact_hash'], 'created_at': previous.get('created_at')}
    ref['artifact_hash'] = evidence_hash(ref)
    return ref


def build_sector_choice(data, target_date, *, previous=None, created_at=None):
    target = _target_date(target_date)
    assets = data.get('reading_sector_history') or {}
    view = numeric_trend_view(assets['trend'], target)
    if view.get('calendar_verified') is not True:
        raise ValueError('机会比较未核对交易日历，不能把观察点称为5日或20日延续')
    history = view.get('ranking_returns') or view['heat']
    dates = history['dates']
    if not dates or dates[-1] != target:
        raise ValueError('机会比较缺目标交易日')
    prior = _prior_reference(previous, target)
    stamp = created_at or datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    when = datetime.fromisoformat(stamp)
    if (when.tzinfo is None or when > datetime.now(ZoneInfo('Asia/Shanghai'))
            or when.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat() < target):
        raise ValueError('机会比较整理时间与事实日不符')
    if prior and prior.get('created_at') and datetime.fromisoformat(prior['created_at']) > when:
        raise ValueError('前次关注晚于本次比较')
    market = {r['date']: r.get('close') for r in (view.get('price_inputs') or {}).get('market_bars', [])}
    def market_return(count):
        if len(dates) <= count:
            return None
        window = dates[-count-1:]
        if any(not market.get(d) for d in window):
            return None
        return (market[window[-1]]/market[window[0]]-1)*100
    market_five = market_return(5)
    metrics, daily = {}, []
    for source in history['rows']:
        changes = source['pct']
        five = _compound(changes[-5:]) if len(changes) >= 5 else None
        twenty = _compound(changes[-20:]) if len(changes) >= 20 else None
        before = _compound(changes[-5:-1]) if len(changes) >= 5 else None
        row = {'track_id': source['track_id'], 'name': source['name'], 'change_pct': changes[-1],
               'five_day_pct': five, 'twenty_day_pct': twenty, 'before_latest_pct': before,
               'five_day_excess_pp': five-market_five if five is not None and market_five is not None else None}
        row['persistent'] = (all(row[k] is not None for k in
            ('five_day_pct', 'twenty_day_pct', 'before_latest_pct', 'five_day_excess_pp'))
            and all(row[k] > 0 for k in ('five_day_pct', 'twenty_day_pct', 'before_latest_pct', 'five_day_excess_pp')))
        metrics[row['track_id']] = row
    for i in range(max(0, len(dates)-5), len(dates)):
        values = [(r['track_id'], r['pct'][i]) for r in history['rows'] if r['pct'][i] is not None]
        positive = sorted(((key, v) for key, v in values if v > 0), key=lambda p: (-p[1], p[0]))
        daily.append({'date': dates[i], 'up': len(positive), 'valid': len(values),
                      'leaders': [key for key, _ in positive[:5]]})
    overlaps = [{'from_date': a['date'], 'to_date': b['date'],
                 'retained': len(set(a['leaders']) & set(b['leaders'])),
                 'previous_count': len(a['leaders'])} for a, b in zip(daily, daily[1:])]
    latest = daily[-1]
    rotating = len(overlaps) >= 2 and all(p['previous_count'] and p['retained']*2 < p['previous_count']
                                         for p in overlaps[-3:])
    regime = ('日间强势方向更替明显' if rotating else '概念指数共同走强' if latest['up']*2 > latest['valid']
              else '分化，未见概念指数普遍上涨')
    ranked = sorted((r for r in metrics.values() if r['persistent']),
                    key=lambda r: (-r['five_day_pct'], -r['twenty_day_pct'], r['track_id']))
    primary = deepcopy(ranked[0]) if ranked else None
    continuity = {'kind': 'baseline', 'reason': '没有当前比较方法下的前次关注记录；本日建立比较基线，不编造昨天关注或真实持仓。',
                  'previous': None}
    if prior and prior.get('primary'):
        old = metrics.get(prior['primary']['track_id'])
        continuity['previous'] = deepcopy(old or prior['primary'])
        if old is None or any(old.get(k) is None for k in
                              ('five_day_pct', 'twenty_day_pct', 'before_latest_pct', 'five_day_excess_pp')):
            primary = None
            continuity.update(kind='unresolved', reason='前次方向的同口径事实缺失；当前对象仅作比较，不据缺数建议替换。')
        elif old['persistent']:
            primary = deepcopy(old)
            continuity.update(kind='continue', reason='前次方向仍有两窗上涨和相对强势；没有仅因今天另一方向涨得更多而更换。')
        else:
            failed = [label for key, label in (('five_day_pct', '5日上涨'), ('twenty_day_pct', '20日上涨'),
                       ('before_latest_pct', '最新日前已有上涨'), ('five_day_excess_pp', '5日强于中证全指'))
                      if old.get(key) is not None and old[key] <= 0]
            continuity.update(kind='replace' if primary else 'reassess', reason='前次方向不再具备：'+
                '、'.join(failed)+'。重新比较关注优先级，不自动形成卖买订单；切换成本尚未核实。')
    alternatives = []
    if continuity['kind'] == 'unresolved' and ranked:
        alternatives.append(deepcopy(ranked[0]))
    if primary and ranked:
        longer = max(ranked, key=lambda r: (r['twenty_day_pct'], r['five_day_pct']))
        if longer['track_id'] != primary['track_id']:
            alternatives.append(deepcopy(longer))
    leader = max((r for r in metrics.values() if r['change_pct'] is not None),
                 key=lambda r: (r['change_pct'], r['track_id']), default=None)
    members = view.get('member_comparison')
    member_summary, stock, stock_alternative = None, None, None
    if primary and members and (sector := members['sectors'].get(primary['track_id'])):
        relative = view['member_relative']['sectors'][primary['track_id']]['rows']
        valid = [r for r in sector['rows'] if r['five_day_pct'] is not None]
        med = median(r['five_day_pct'] for r in valid) if valid else None
        reduced = sorted(r['five_day_pct'] for r in valid)[:-1]
        member_summary = {'query_date': members['query_date'], 'basis': members['membership_basis'],
                          'valid': len(valid), 'total': sector['member_count'], 'median_five_pct': med,
                          'median_without_top_pct': median(reduced) if reduced else None,
                          'positive': sum(r['five_day_pct'] > 0 for r in valid)}
        daily_bars = {(r['code'], r['date']): r['change_pct'] for r in members['daily_rows']}
        index_row = next(r for r in history['rows'] if r['track_id'] == primary['track_id'])
        if members['trade_dates'][-5:] == dates[-5:]:
            candidates = []
            for row in valid:
                changes = [daily_bars.get((row['code'], d)) for d in dates[-5:]]
                rel = relative[row['code']]
                if any(v is None for v in [*changes, *index_row['pct'][-5:], rel['excess_pp']]):
                    continue
                wins = [a > b for a, b in zip(changes, index_row['pct'][-5:])]
                trailing = next((i for i, v in enumerate(reversed(wins)) if not v), len(wins))
                if (row['five_day_pct'] > 0 and rel['excess_pp'] > 0 and sum(wins) > len(wins)/2
                        and changes[-1] > 0 and wins[-1] and row['turnover_yi'] and 'ST' not in row['name'].upper()):
                    candidates.append({**deepcopy(row), **deepcopy(rel), 'outperform_days': sum(wins),
                                       'trailing_outperform_days': trailing})
            candidates.sort(key=lambda r: (-r['trailing_outperform_days'], -r['outperform_days'], -r['turnover_yi'], r['code']))
            stock = candidates[0] if candidates else None
            stock_alternative = candidates[1] if len(candidates) > 1 else None
    participation = ('已覆盖样本优先比较个股增强，不把今天上涨板块全部买一遍' if stock
                     else '以板块延续比较为先，个股增强另作替代比较' if primary
                     else '现有证据不足以优先一个延续方向；不据此推断账户是否参与')
    result = {'schema': SCHEMA, 'target_date': target, 'source_date': target, 'created_at': stamp,
              'source_hash': evidence_hash(assets), 'method': METHOD, 'regime': regime,
              'participation': participation, 'daily': daily, 'leader_retention': overlaps,
              'market_five_day_pct': market_five, 'primary': primary, 'alternatives': alternatives,
              'today_leader': deepcopy(leader), 'member_summary': member_summary,
              'stock': stock, 'stock_alternative': stock_alternative, 'continuity': continuity,
              'previous_input': prior,
              'limitations': ['未核实概念对应的可成交ETF或篮子；指数收益不是买到的净收益。',
                  '成员仅为查询日最新名单，回看目标日行情；不是目标日当时可知的成员或排名。',
                  '个股差值是历史相对表现，不是已识别alpha；复权、费用、报价与涨跌停可成交性未统一核实。',
                  '概念相互重叠；个股比较仅覆盖已补查概念，不推断全市场个股优于板块。']}
    result['artifact_hash'] = evidence_hash(result)
    return result


def validate_sector_choice(value, data, target_date):
    if (value.get('schema') != SCHEMA or value.get('target_date') != target_date
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})):
        raise ValueError('机会比较日期或记录不符')
    rebuilt = build_sector_choice(data, target_date, previous=value.get('previous_input'), created_at=value['created_at'])
    if rebuilt != value:
        raise ValueError('机会比较与选定快照不符')
    return value


def render_sector_choice(soup, choice):
    from report.sector_reading_primitives import _text
    section = soup.new_tag('section', attrs={'id': 'daily-choice', 'class': 'sector-daily-section daily-choice'})
    section.append(_text(soup, 'h2', '板块事实与尚缺的比较'))
    if not choice['daily'][-1]['valid']:
        section.append(_text(soup, 'p', choice['target_date'] +
            '的概念指数行情未取得，暂不能比较当天板块强弱、方向延续或个股增强。'))
        section.append(_text(soup, 'p', '缺少行情不代表没有机会，也不说明方向更替；已有历史与其他已取得的事实分别保留。'))
        return section
    latest = choice['daily'][-1]
    prior = choice['daily'][-2] if len(choice['daily']) > 1 else None
    evidence = f'{latest["date"]}：{latest["up"]}/{latest["valid"]}个有效概念指数上涨'
    if prior:
        evidence += f'；前一交易日为{prior["up"]}/{prior["valid"]}'
    if choice['leader_retention']:
        pair = choice['leader_retention'][-1]
        evidence += f'；前日上涨前列延续到本日前列{pair["retained"]}/{pair["previous_count"]}个'
    section.append(_text(soup, 'p', evidence+'。概念有重叠，这不是独立股票的上涨比例。'))
    section.append(_text(soup, 'p', '尚无可展示的成员同窗图，不能据概念指数涨跌判断个股与大盘的关系。'
        '贝塔是大盘涨跌带动个股共振；阿尔法是与大盘关系不大的个股独立行情。'
        '板块成员共涨和个股跑赢板块不能替代这两层比较。'))
    fmt = lambda v: '未核实' if v is None else f'{v:+.2f}%'
    def button(row):
        node = _text(soup, 'button', row['name']+' · '+row['track_id'].removeprefix('index:'))
        node.attrs.update({'type': 'button', 'data-choice-track': row['track_id'], 'class': 'choice-object'})
        return node
    primary = choice['primary']
    if primary:
        section.append(_text(soup, 'h3', '默认观察起点 · 不是买入排序'))
        section.append(button(primary))
        section.append(_text(soup, 'p', f'近5日{fmt(primary["five_day_pct"])}，近20日{fmt(primary["twenty_day_pct"])}；'
            f'目标日{fmt(primary["change_pct"])}。'
            f'同5日强于中证全指{primary["five_day_excess_pp"]:+.2f}个百分点。'))
        for other in choice['alternatives']:
            section.append(_text(soup, 'p', f'较长窗口对照：{other["name"]}近20日{fmt(other["twenty_day_pct"])}，'
                f'近5日{fmt(other["five_day_pct"])}。'))
            section.append(button(other))
        if (member := choice['member_summary']):
            section.append(_text(soup, 'p', f'成分补查于{member["query_date"]}，回看截至{choice["target_date"]}：'
                f'{member["valid"]}/{member["total"]}只有完整5日数据，成员5日收益中间值{fmt(member["median_five_pct"])}，'
                f'其中{member["positive"]}只上涨；去掉5日涨幅最高的一只后，其余成员的中间涨幅{fmt(member["median_without_top_pct"])}。'
                '仅用于事后样本比较，不是指数贡献分解、卖出建议或历史成员扩散证明。'))
        section.append(_text(soup, 'h3', '原5日个股相对板块事实'))
        if (stock := choice['stock']):
            section.append(_text(soup, 'p', f'{stock["name"]}（{stock["code"]}）：同5日{fmt(stock["stock_pct"])}，'
                f'对应板块{fmt(stock["sector_pct"])}，差{stock["excess_pp"]:+.2f}个百分点；'
                f'{stock["outperform_days"]}/5日跑赢，最近连续{stock["trailing_outperform_days"]}日跑赢。'
                f'目标日{fmt(stock["change_pct"])}，成交额{stock["turnover_yi"]:.2f}亿元。'))
            if (other := choice['stock_alternative']):
                section.append(_text(soup, 'p', f'同板块对照 {other["name"]}（{other["code"]}）：'
                    f'同5日{fmt(other["stock_pct"])}，{other["outperform_days"]}/5日跑赢，'
                    f'目标日成交额{other["turnover_yi"]:.2f}亿元。'))
            section.append(_text(soup, 'p', '这些差值只是个股相对所属板块的历史表现，不是已识别alpha，'
                '也不证明独立行情、未来收益或可成交净收益。'))
        else:
            section.append(_text(soup, 'p', '原记录未指定个股观察起点；这不是没有个股机会的结论。'))
    else:
        if choice['continuity']['kind'] == 'unresolved':
            section.append(_text(soup, 'p', '前次关注事实尚未补齐，新方向仅作对照，不据缺数替换。'))
            for other in choice['alternatives']:
                section.append(button(other))
                section.append(_text(soup, 'p', f'近5日{fmt(other["five_day_pct"])}，近20日{fmt(other["twenty_day_pct"])}。'))
        else:
            section.append(_text(soup, 'p', '原记录没有默认观察对象；不把固定窗口未入选当作没有机会。'))
    if (old := choice['continuity'].get('previous')):
        section.append(_text(soup, 'p', f'前次关注 {old["name"]}：本次同5日{fmt(old.get("five_day_pct"))}，'
                            f'同20日{fmt(old.get("twenty_day_pct"))}。关注不是实际持仓。'))
    if (leader := choice['today_leader']) and (not primary or leader['track_id'] != primary['track_id']):
        section.append(_text(soup, 'p', f'今日涨幅最高 {leader["name"]}{fmt(leader["change_pct"])}，'
            f'近5日{fmt(leader["five_day_pct"])}、近20日{fmt(leader["twenty_day_pct"])}；'
            '该排名不产生买卖结论。'))
    section.append(_text(soup, 'small', '截至'+choice['target_date']+'的比较，整理于'+choice['created_at'][:10]+
        '；历史修订不是当时作出的预测。未提供账户，不生成持仓、仓位或订单。'))
    node = soup.new_tag('script', attrs={'id': 'sector-choice-data', 'type': 'application/json'})
    import json
    node.string = json.dumps(choice, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    section.append(node)
    return section
