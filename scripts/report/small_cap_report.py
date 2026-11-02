"""Small-cap-only collection, immutable snapshots and desktop HTML.

Replay reads only the selected JSON and its frozen plan, never old HTML.
"""
from __future__ import annotations
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from report.fact_utils import evidence_hash
from report.market_returns import _pages, collect_market_returns, validate_market_returns
from report.small_cap_rotation import (SCHEMA, build_plan, load_inputs,
                                       refresh_plan_inputs, render_plan, validate_plan)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SNAPSHOT = 'small_cap_snapshot.v1'
STYLE = '''
body{margin:0;background:#f5f4f0;color:#222;font:16px/1.7 system-ui,sans-serif;min-width:1180px}
main{width:1280px;max-width:calc(100% - 80px);margin:36px auto 70px}
header{margin-bottom:32px}h1{font-size:32px;margin-bottom:6px}h2{font-size:25px}h3{font-size:20px}
section{background:white;border:1px solid #dcdad3;padding:28px;margin:24px 0}
p{margin:12px 0}.dash-takeaway{font-weight:600}.dash-note,small,.source{color:#62615c}
small{display:block}.table-responsive{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:10px 12px;border-bottom:1px solid #dedcd5;text-align:right;white-space:nowrap}
th{background:#efeee9;color:#36352f}th:nth-child(-n+2),td:nth-child(-n+2){text-align:left}
.dash-plan-account,.dash-plan-fresh{margin-top:28px}.dash-row-backup{color:#696861}
.dash-row-due{background:#fff1d6}.dash-row-sold{color:#63635b}a{color:#54488b}
.limit{background:#fff4db;padding:14px 18px}.source{font-size:14px;overflow-wrap:anywhere}
'''

TRACKING_STYLE = '''
body{background:#edf2f6;color:#183a56;font-family:"Avenir Next","PingFang SC","Microsoft YaHei",sans-serif}
main{margin-top:28px}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
header h1{font-size:27px;margin:0}header p{margin:2px 0;color:#596e7f;font-size:14px}
header nav{display:flex;gap:24px}a{color:#285e86;text-underline-offset:4px}
section{border:1px solid #d8e1e8;padding:26px 30px;margin:20px 0;border-radius:8px}
h2{font-size:21px;margin:0 0 14px}h3{font-size:17px}p{max-width:78em}
.fund-overview{display:grid;grid-template-columns:1.05fr .8fr 1.4fr;gap:32px;align-items:center}
.fund-overview dl{margin:0}.fund-overview dt{font-size:14px;color:#596e7f}.fund-overview dd{margin:4px 0}
.fund-nav{font-size:62px;line-height:1.15;font-weight:600;letter-spacing:-2px;font-variant-numeric:tabular-nums}
.fund-return{font-size:32px;line-height:1.4;font-weight:600}.fund-date{font-size:24px;font-weight:600}
.fund-meta,.source,small,.dash-note{color:#596e7f;font-size:14px}.fund-positive{color:#c43535}.fund-negative{color:#15734e}
.fund-holdings{margin-top:22px;padding-top:16px;border-top:1px solid #d8e1e8;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.fund-holdings a{text-decoration:none;border:1px solid #d8e1e8;border-radius:5px;padding:5px 12px;color:#183a56}
.fund-holdings span{font-size:14px;color:#596e7f}.fund-status{margin-top:14px;font-size:14px}.fund-status strong{color:#c43535}
.chart-heading{display:flex;justify-content:space-between;align-items:baseline}.chart-heading p{margin:0;color:#596e7f;font-size:14px}
.nav-legend{display:flex;gap:26px;align-items:center;margin:14px 0}.nav-legend label{cursor:pointer;font-size:14px;display:flex;gap:7px;align-items:center}
.nav-legend i{width:22px;height:3px;display:inline-block;background:var(--series-color)}
input[type=checkbox]{accent-color:#285e86}input:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid #285e86;outline-offset:4px}
.nav-chart{display:block;width:100%;height:auto}.nav-series[hidden]{display:none}.nav-chart text{font:13px "Avenir Next","PingFang SC",sans-serif;fill:#596e7f}
.nav-chart .nav-axis-label{font-size:12px}.nav-chart .nav-grid{stroke:#e5ebf0}.nav-chart .nav-origin{stroke:#9aafbf;stroke-dasharray:5 5}
.nav-chart .nav-cursor{stroke:#91a5b5;stroke-dasharray:3 4;pointer-events:none}
.nav-inspection{display:flex;gap:26px;align-items:center;font-size:14px;font-variant-numeric:tabular-nums;min-height:32px}
.nav-inspection strong{min-width:165px}.nav-inspection span{white-space:nowrap}.nav-slider{display:flex;gap:18px;align-items:center;color:#596e7f;font-size:14px}
.nav-slider input{flex:1;accent-color:#285e86}.chart-note{font-size:14px;color:#596e7f;margin-bottom:0}
th{background:#f2f6f9;color:#183a56}th,td{border-bottom-color:#d8e1e8;padding:11px 10px}
.fund-disclosure summary{cursor:pointer;font-weight:600}.fund-disclosure p{font-size:14px;color:#596e7f}
.fund-disclosure details[open] summary{margin-bottom:18px}
.plan-disclosure summary{cursor:pointer;font-weight:600}.plan-disclosure>section{margin-top:18px}
'''


def validate_data(data, day):
    market, plan = data.get('reading_market_returns'), data.get('reading_small_cap_plan')
    validate_market_returns(market, day)
    validate_plan(plan, day)
    if plan['schema'] not in ('small_cap_plan.v7', SCHEMA):
        raise ValueError('所选快照没有当前版本小盘计划，停止生成；不重算旧规则')
    return {'reading_market_returns': market, 'reading_small_cap_plan': plan}


def _snapshot_data(path, day):
    snapshot = json.loads(path.read_text(encoding='utf-8'))
    if snapshot.get('date') != day or not isinstance(snapshot.get('data'), dict):
        raise ValueError('快照日期或内容不符，停止生成')
    schema = snapshot.get('schema')
    if schema not in (None, SCHEMA_SNAPSHOT) or (path.parent.name in ('small-cap', 'rebuilt') and schema != SCHEMA_SNAPSHOT):
        raise ValueError('小盘快照版本不符，停止生成')
    if schema == SCHEMA_SNAPSHOT:
        expected = evidence_hash({k: v for k, v in snapshot.items() if k != 'artifact_hash'})
        if snapshot.get('artifact_hash') != expected:
            raise ValueError('小盘快照指纹不符，停止生成')
    return snapshot['data']


def selected_snapshot(root, day, source):
    if source == 'replay':
        candidates = [root / 'snapshots/replay' / f'{day}_replay.json']
    elif source == 'rebuilt':
        candidates = [root / 'snapshots/small-cap/rebuilt' / f'{day}.json']
    else:
        candidates = [root / 'snapshots/small-cap' / f'{day}.json', root / 'snapshots' / f'{day}.json']
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise ValueError(f'{day} 选定来源快照不存在，停止生成')
    return validate_data(_snapshot_data(path, day), day), path


def frozen_plans(root, day, sessions):
    """Only official earlier plans may lock a new live plan; no replay mixing."""
    out = {}
    for earlier in [s for s in sessions if s < day][-20:]:
        candidates = [root / 'snapshots/small-cap' / f'{earlier}.json', root / 'snapshots' / f'{earlier}.json']
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            continue
        plan = _snapshot_data(path, earlier).get('reading_small_cap_plan')
        if plan is not None:
            out[earlier] = validate_plan(plan, earlier)
    return out


def refresh_indices(pro, day, history):
    path = history / 'indices.json'
    value = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'indices': {}}
    start = (datetime.fromisoformat(day) - timedelta(days=150)).strftime('%Y%m%d')
    for code, name in [('399006.SZ', '创业板指'), ('932000.CSI', '中证2000')]:
        item = value['indices'].setdefault(code, {'name': name, 'rows': []})
        known = {row['trade_date']: row for row in item['rows']}
        rows = _pages(pro, 'index_daily', ts_code=code, start_date=start, end_date=day.replace('-', ''),
                      fields='ts_code,trade_date,open,close,pre_close')
        for row in rows:
            stamp = str(row.get('trade_date') or '')
            if row.get('ts_code') != code or not stamp or stamp > day.replace('-', ''):
                raise ValueError('对照指数代码或日期不符')
            old = known.get(stamp)
            if old and any(old.get(key) is not None and row.get(key) is not None and old[key] != row[key]
                           for key in ('open', 'close', 'pre_close')):
                raise ValueError('对照指数与既有同日记录冲突')
            known[stamp] = {**(old or {}), **{key: val for key, val in row.items() if val is not None}}
        item['rows'] = [known[d] for d in sorted(known)]
    value['retrieved_at'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    history.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=history, encoding='utf-8', delete=False) as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        temporary = Path(stream.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def collect(day, *, root=ROOT, pro=None, historical=False):
    from market_data.tushare_client import create_tushare_pro_api
    pro = pro or create_tushare_pro_api()
    history = root / 'data/market-history'
    refresh_plan_inputs(pro, day, history=history)
    refresh_indices(pro, day, history)
    market = collect_market_returns(pro, day, cache_root=root / 'data/market-returns')
    if market.get('st_codes') is None:
        raise ValueError('目标日ST事实缺失，停止生成名单')
    sessions, records = load_inputs(history=history)
    plan, reason = build_plan(market, day, sessions=sessions, records=records,
                              frozen={} if historical else frozen_plans(root, day, sessions))
    if plan is None:
        raise ValueError(f'小盘计划未生成：{reason}')
    return validate_data({'reading_market_returns': market, 'reading_small_cap_plan': plan}, day)


def render(data, day, *, source, tracking=None):
    data = validate_data(data, day)
    soup = BeautifulSoup('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><main></main></body></html>', 'html.parser')
    title = soup.new_tag('title'); title.string = f'{day} 小盘轮换 v0.3'; soup.head.append(title)
    css = soup.new_tag('style'); css.string = STYLE + (TRACKING_STYLE if tracking else ''); soup.head.append(css)
    main = soup.main
    header = soup.new_tag('header')
    if tracking:
        header.append(BeautifulSoup(f'<div><h1>小盘轮换 v0.3</h1><p>{day} 收盘净值报告 · 连续模拟</p></div>'
                                   '<nav aria-label="报告内容"><a href="#nav-curve">净值曲线</a><a href="#fund-positions">成分股</a>'
                                   '<a href="#fund-method">计算说明</a></nav>', 'html.parser'))
    else:
        identity = '历史单期演示（非当前净值报告）' if data['reading_small_cap_plan'].get('account') else '选股名单与换手日历（非账户净值）'
        header.append(BeautifulSoup(f'<h1>{day} 小盘轮换 v0.3</h1><p>{identity} · 5只名单与3只备选 · 每20交易日换手</p>', 'html.parser'))
    main.append(header)
    if not tracking:
        limits = soup.new_tag('p', attrs={'class': 'limit'})
        limits.string = ('历史账户演示：下表保留冻结快照中的1万元单期模拟，不是当前连续净值或实际成交。当前净值请阅读2026-11-02起的连续跟踪报告。'
                         if data['reading_small_cap_plan'].get('account') else
                         '本页仅展示选股名单与换手日历；没有账户净值，不据此推断实际持仓或成交。')
        main.append(limits)
    if tracking:
        from report.small_cap_tracking import render_tracking
        main.append(BeautifulSoup(render_tracking(tracking), 'html.parser'))
    if tracking and tracking['record']['stopped']:
        stopped = soup.new_tag('p', attrs={'class': 'source'})
        stopped.string = '连续模拟已停用，后续定名单和调仓均停止，等待复核。'
        main.append(stopped)
    elif tracking:
        plan_section = render_plan(soup, data['reading_small_cap_plan'], tracked=True)
        disclosure = soup.new_tag('details', attrs={'class': 'plan-disclosure'})
        summary = soup.new_tag('summary')
        summary.string = '本期选股依据与换手日历（非当前持仓）'
        disclosure.append(summary)
        disclosure.append(plan_section)
        main.append(disclosure)
    else:
        main.append(render_plan(soup, data['reading_small_cap_plan']))
    note = soup.new_tag('p', attrs={'class': 'source'})
    note.string = f'事实来源：{source}；行情取得时间：{data["reading_market_returns"]["retrieved_at"]}；小盘计划指纹：{data["reading_small_cap_plan"]["artifact_hash"]}。回测不代表未来收益。'
    main.append(note)
    if not tracking:
        payload = soup.new_tag('script', attrs={'id': 'small-cap-plan', 'type': 'application/json'})
        payload.string = json.dumps(data['reading_small_cap_plan'], ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
        main.append(payload)
    if tracking:
        payload = soup.new_tag('script', attrs={'id': 'small-cap-tracking', 'type': 'application/json'})
        payload.string = json.dumps(tracking['record'], ensure_ascii=False, allow_nan=False).replace('<', chr(92) + 'u003c')
        main.append(payload)
    return str(soup)


def write_new(path, text):
    """Publish complete content without replacing any existing historical file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, encoding='utf-8', delete=False) as stream:
        stream.write(text)
        temp = Path(stream.name)
    try:
        os.link(temp, path)
    except FileExistsError:
        if path.read_text(encoding='utf-8') != text:
            raise ValueError(f'已有同名文件内容不同，停止覆盖：{path.name}') from None
    finally:
        temp.unlink(missing_ok=True)
    return path


def save_snapshot(data, day, *, root=ROOT, historical=False):
    value = {'schema': SCHEMA_SNAPSHOT, 'date': day, 'data': validate_data(data, day)}
    value['artifact_hash'] = evidence_hash(value)
    path = root / ('snapshots/small-cap/rebuilt' if historical else 'snapshots/small-cap') / f'{day}.json'
    return write_new(path, json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
