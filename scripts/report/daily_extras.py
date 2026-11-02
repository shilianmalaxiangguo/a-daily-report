"""Day-specific additions computed when facts are collected, then frozen with the snapshot."""
import json
from pathlib import Path

from report.small_cap_history import COMPARISONS

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / '.generated/backtest-history'
CACHE = ROOT / '.generated/market-returns-v2'
BACKTEST_START = '2024-01-02'


def reading_core(data, target_date, trend=None, backtest=None):
    # Historical-only compatibility helper.  Keep its old dependencies local so
    # the current small-cap collector does not import the retired decision board.
    from report.daily_observations import build_observations
    from report.decision_board import build_decision_board
    from report.market_alpha_beta import build_alpha_beta, concept_trend_returns
    from report.sector_reading_history import choice_track_ids, numeric_trend_view
    value = data.get('reading_market_returns')
    if not value:
        return None
    if trend is None and (data.get('reading_sector_history') or {}).get('trend'):
        trend = numeric_trend_view(data['reading_sector_history']['trend'], target_date)
    projection = build_alpha_beta(value, target_date, concepts=concept_trend_returns(trend) if trend else None,
                                  tracked_ids=choice_track_ids(data.get('reading_choice')))
    if projection is None:
        return None
    from report.decision_board import long_run_evidence
    board = build_decision_board(value, target_date, projection, long_run=long_run_evidence(backtest))
    if board is None:
        return projection, None, None
    limit = {r['ts_code'] for r in data.get('limit_list_d') or [] if r.get('limit') == 'U'}
    return projection, board, build_observations(value, projection, board, limit_codes=limit or None)


def _iso(value):
    value = str(value)
    return f'{value[:4]}-{value[4:6]}-{value[6:]}' if len(value) == 8 and value.isdigit() else value


def comparison_history(target_date, *, history=HISTORY):
    """Cached daily closes of the comparison indices up to target_date, with their retrieval time."""
    path = history / 'indices.json'
    if not path.is_file():
        return {}
    cached = json.loads(path.read_text(encoding='utf-8'))
    out = {}
    for code, name in COMPARISONS.items():
        rows = (cached.get('indices') or {}).get(code, {}).get('rows') or []
        closes = {_iso(r['trade_date']): float(r['close']) for r in rows
                  if _iso(r['trade_date']) <= target_date and isinstance(r.get('close'), (int, float)) and r['close'] > 0}
        if closes:
            out[code] = {'name': name, 'closes': closes, 'retrieved_at': cached.get('retrieved_at')}
    return out


def refresh_comparison_history(pro, target_date, *, history=HISTORY):
    """Append the comparison indices' recent explicit-date rows to the cache; a changed past value stops."""
    from datetime import date, datetime, timedelta
    from zoneinfo import ZoneInfo
    from report.market_returns import _pages
    path = history / 'indices.json'
    cached = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'indices': {}}
    for code, name in COMPARISONS.items():
        item = cached['indices'].setdefault(code, {'name': name, 'rows': []})
        known = {r['trade_date']: r for r in item['rows']}
        last = max(known) if known else BACKTEST_START.replace('-', '')
        start = (date.fromisoformat(_iso(last)) - timedelta(days=10)).strftime('%Y%m%d')
        rows = _pages(pro, 'index_daily', ts_code=code, start_date=start, end_date=target_date.replace('-', ''),
                      fields='ts_code,trade_date,open,high,low,close,pre_close,amount')
        for row in rows:
            if row.get('ts_code') != code or _iso(row.get('trade_date')) > target_date:
                raise ValueError('对照指数代码或日期不符')
            old = known.get(row['trade_date'])
            if old is not None and old.get('close') != row.get('close'):
                raise ValueError('对照指数同日收盘与本地记录不符')
            known[row['trade_date']] = row
        item['rows'] = [known[d] for d in sorted(known)]
    cached['retrieved_at'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(cached, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)
    return {code: cached['indices'][code]['rows'][-1]['trade_date'] for code in COMPARISONS}


def history_backtest(target_date, market, *, history=HISTORY, cache=CACHE):
    """Long-history backtest ending on target_date; None when the local history is incomplete."""
    from report.strategy_backtest import load_history, run_backtest
    from report.sector_reading_history import evidence_hash
    calendar = json.loads((history / 'calendar.json').read_text(encoding='utf-8'))
    days = sorted({f"{r['cal_date'][:4]}-{r['cal_date'][4:6]}-{r['cal_date'][6:]}" for r in calendar['rows']
                   if int(r['is_open']) == 1} | set(market['trade_dates']))
    days = [d for d in days if BACKTEST_START <= d <= target_date]
    if not days or days[-1] != target_date or any(not (cache / f'{d}.json').is_file() for d in days):
        return None
    bench = json.loads((history / 'benchmark.json').read_text(encoding='utf-8'))['rows']
    known = {str(r['trade_date']) for r in bench}
    bench += [{'trade_date': r['date'].replace('-', ''), 'close': r['close'], 'pre_close': r['pre_close'], 'open': r['open']}
              for r in market['benchmark']['rows'] if r['date'].replace('-', '') not in known]
    basics = json.loads((history / 'basics.json').read_text(encoding='utf-8'))
    names = json.loads((history / 'namechange.json').read_text(encoding='utf-8'))
    h = load_history(cache, days, bench, basics['rows'], names['rows'])
    comparisons = comparison_history(target_date, history=history)
    from report.small_cap_rotation import growth_records
    fina = history / 'fina_indicator.json'
    records = growth_records(json.loads(fina.read_text(encoding='utf-8'))) if fina.is_file() else None
    result, *_ = run_backtest(h, comparisons=comparisons, plan_records=records)
    result.update(target_date=target_date, profile_query={'basics': basics['retrieved_at'], 'namechange': names['retrieved_at']},
                  comparison_query={code: item['retrieved_at'] for code, item in comparisons.items()})
    result['artifact_hash'] = evidence_hash(result)
    return result


def validate_backtest(value, target_date):
    from report.sector_reading_history import evidence_hash
    if (not isinstance(value, dict) or value.get('schema') not in ('strategy_backtest.v1', 'strategy_backtest.v2', 'strategy_backtest.v3', 'strategy_backtest.v4')
            or value.get('target_date') != target_date
            or value.get('end') != target_date
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})):
        raise ValueError('策略回测日期或指纹不符')
    return value


def backtest_brief(value):
    if not value:
        return None
    names = {'live_rule': '当前规则', 'alpha': '阿尔法每天买', 'alpha_regime': '阿尔法防守期不买', 'beta': '高贝塔每天买',
             'beta_offense': '高贝塔只在进攻期买', 'stance': '简化轮换', 'index': '中证全指持有'}
    brief = {'区间': f"{value['start']}至{value['end']}", '交易日': value['sessions']}
    for key, label in names.items():
        stats = value['stats'][key]
        full = stats['full']
        brief[label] = {'年化%': full.get('cagr_pct'), '最大回撤%': full.get('max_drawdown_pct'), '夏普': full.get('sharpe'),
                        '样本外年化%': (stats.get('out_of_sample') or {}).get('cagr_pct')}
    for key, item in (value.get('comparisons') or {}).items():
        full = item['full']
        label = f"对照：{item['name']}" + ('（每日再平衡、不计成本的理论参照）' if key == 'equal_weight' else '持有')
        brief[label] = {'年化%': full.get('cagr_pct'), '最大回撤%': full.get('max_drawdown_pct'), '夏普': full.get('sharpe')}
    null = value.get('null') or {}
    for key, label in (('random', '对照：同规则随机挑10只（20次中位）'), ('random_offense', '对照：同规则随机挑10只只在进攻期买（20次中位）')):
        if key in null:
            brief[label] = {'年化%': null[key]['cagr_pct']['median'], '年化最低%': null[key]['cagr_pct']['min'],
                            '年化最高%': null[key]['cagr_pct']['max'], '夏普': null[key]['sharpe']['median']}
    plan = value.get('plan')
    if plan:
        brief[plan['name']] = {'年化%': plan['full'].get('cagr_pct'), '最大回撤%': plan['full'].get('max_drawdown_pct'),
                                     '夏普': plan['full'].get('sharpe'), '年化高于且回撤浅于创业板指': plan.get('beats_chinext')}
    brief['信号IC'] = {k: {'平均IC': v['mean_ic'], 't值': v['t_stat']} for k, v in value['ic'].items()}
    return brief


def collect_extras(data, target_date, *, snapshots=(), service=None, backtest=True, interpretation=True):
    """Freeze only the current small-cap plan; legacy keyword arguments remain accepted by callers.

    Historical backtest, interpretation and advice helpers above remain available for archive validation.
    They are no longer part of daily collection and cannot prevent the small-cap plan from being built.
    """
    notes = data.setdefault('reading_source_notes', [])
    for key in ('reading_backtest', 'reading_interpretation', 'reading_decision_record',
                'reading_decision_history', 'reading_small_cap_plan'):
        data.pop(key, None)
    try:
        from report.small_cap_rotation import build_plan, load_index, load_inputs
        sessions, records, chinext = load_inputs(target_date)
        frozen = {s['date']: s['data']['reading_small_cap_plan'] for s in snapshots
                  if s.get('date', '') < target_date and (s.get('data') or {}).get('reading_small_cap_plan')}
        plan, reason = build_plan(data['reading_market_returns'], target_date, sessions=sessions, records=records,
                                  chinext=chinext, frozen=frozen, csi2000=load_index('932000.CSI', target_date))
        if plan:
            data['reading_small_cap_plan'] = plan
        else:
            notes.append(f'执行计划未生成：{reason}。')
    except Exception as error:
        notes.append(f'执行计划未生成（{type(error).__name__}），保留缺口。')
