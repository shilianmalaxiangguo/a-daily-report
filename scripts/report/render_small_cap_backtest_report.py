"""Render a standalone comparison report for small-cap rotation v0.3.

The report deliberately keeps the frozen equal-weight curve model separate from
the 10,000-yuan whole-lot account simulation. It consumes frozen artifacts and
does not alter the daily report or its snapshots.
"""
from __future__ import annotations

import html
import hashlib
import importlib.util
import json
import statistics
import sys
from math import isfinite
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "snapshots/replay/2026-10-30_replay.json"
SELL_RULES_PY = ROOT / "docs/reviews/2026-10-30-wiki-evidence/sell_rules.py"
SELL_RULES_JSON = ROOT / "docs/reviews/2026-10-30-wiki-evidence/sell_rules.json"
ECHARTS = ROOT / ".generated/vendor/echarts/echarts.min.js"
OUTPUT = ROOT / "reports/research/small_cap_rotation_v0.3_backtest_compare_2026-10-30.html"
RECENT_START = "2025-02-28"


def pct(value, digits=1):
    if value is None:
        return "—"
    return f"{float(value):+.{digits}f}%"


def number(value, digits=2):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def metric(curve):
    values = [float(x) for x in curve]
    if len(values) < 2 or any(not isfinite(x) or x <= 0 for x in values):
        raise ValueError("净值数据不完整，停止生成")
    daily = [values[i] / values[i - 1] - 1 for i in range(1, len(values))]
    years = len(daily) / 252
    peak = values[0]
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    return {
        "total_pct": (values[-1] / values[0] - 1) * 100,
        "cagr_pct": ((values[-1] / values[0]) ** (1 / years) - 1) * 100 if years else None,
        "max_drawdown_pct": drawdown * 100,
        "lowest_nav": min(values) / values[0],
        "final_nav": values[-1] / values[0],
        "sessions": len(values),
    }


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法载入 {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def real_account_results():
    """Return the two account runs and a same-window ChiNext reference."""
    module = load_module(SELL_RULES_PY, "small_cap_sell_rules_report")
    start = module.days.index(RECENT_START)
    base = module.simulate(start, 0, rule=None, keep_nav=True)
    tp10 = module.simulate(start, 0, rule="TP10", keep_nav=True)
    decisions = list(range(start, module.n - 1, 20))
    span = module.days[start:]
    index_nav = module.an.ra.sd.chinext[start:] / module.an.ra.sd.chinext[start]
    reference = module.an.ra.profile(index_nav, span, decisions, start)
    reference.update(
        start=span[0],
        final_nav=float(index_nav[-1]),
        fees_pct_of_start=None,
        idle_pct=None,
        rule_sales=None,
        beats_chinext=None,
    )
    return {"base": base, "tp10": tp10, "chinext": reference, "end": span[-1],
            "dates": span, "index_nav": [float(x) for x in index_nav],
            "input_sha256": module.h['inputs_sha256'],
            "anchor_offset_sessions": (start - module.days.index('2024-07-01')) % 20}


def table(headers, rows, classes=None):
    head = "".join(f"<th>{html.escape(str(item))}</th>" for item in headers)
    body = []
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            klass = f' class="{classes[index]}"' if classes and index < len(classes) and classes[index] else ""
            cells.append(f"<td{klass}>{value}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def render():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    backtest = snapshot["data"]["reading_backtest"]
    sell_rules = json.loads(SELL_RULES_JSON.read_text(encoding="utf-8"))
    real = real_account_results()
    if (real['tp10']['span'] != real['dates'] or real['base']['span'] != real['dates']
            or any(len(real[key]['nav']) != len(real['dates']) for key in ('base','tp10'))):
        raise ValueError("账户模拟日期与净值长度不符，停止生成")
    dates = list(backtest["dates"])
    curves = {key: list(value) for key, value in backtest["curves"].items()}
    if (backtest['schema'] != 'strategy_backtest.v4' or dates != sorted(set(dates))
            or dates[0] != backtest['start'] or dates[-1] != backtest['end']
            or len(dates) != backtest['sessions']
            or any(len(curve) != len(dates) for curve in curves.values())):
        raise ValueError("回测日期或曲线长度不符，停止生成")
    for curve in curves.values():
        metric(curve)
    recent_index = next(i for i, day in enumerate(dates) if day >= RECENT_START)
    chart_keys = [
        "small_cap_plan", "small_cap_plan_hold", "small_cap_pool", "399006.SZ",
        "932000.CSI", "index", "live_rule", "alpha", "alpha_regime", "beta", "beta_offense", "stance", "random",
    ]
    chart_keys = [key for key in chart_keys if key in curves]
    chart_names = {
        "small_cap_plan": "小盘轮换 v0.3（止盈10%）",
        "small_cap_plan_hold": "小盘轮换（不止盈）",
        "small_cap_pool": "股票池（不止盈）",
        "399006.SZ": "创业板指",
        "932000.CSI": "中证2000",
        "index": "中证全指",
        "random": "随机抽样中位曲线（20次）",
        "live_rule": "旧方案：动态阿尔法／贝塔",
        "alpha": "旧方案：阿尔法六项检查",
        "alpha_regime": "旧方案：阿尔法（防守期不买）",
        "beta": "旧方案：高贝塔篮子",
        "beta_offense": "旧方案：贝塔（进攻期买）",
        "stance": "旧方案：按阶段轮换",
        "account_tp10": "整手账户模拟：止盈10%",
        "account_base": "整手账户模拟：不止盈",
    }
    chart_payload = {
        "full": {"dates": dates, "curves": {key: curves[key] for key in chart_keys}},
        "recent": {
            "dates": dates[recent_index:],
            "curves": {
                key: [round(value / curves[key][recent_index], 6) for value in curves[key][recent_index:]]
                for key in chart_keys
            },
        },
        "names": chart_names,
        "account": {"dates": real['dates'], "curves": {
            "account_tp10": [round(float(x), 8) for x in real['tp10']['nav']],
            "account_base": [round(float(x), 8) for x in real['base']['nav']],
            "399006.SZ": real['index_nav']}},
        "metadata": {"version": "v0.3", "recent_start": RECENT_START,
                     "curve_end": dates[-1], "account_end": real['end'],
                     "curve_input_sha256": backtest['inputs_sha256'],
                     "account_input_sha256": real['input_sha256'],
                     "snapshot_sha256": hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
                     "sell_rules_sha256": hashlib.sha256(SELL_RULES_JSON.read_bytes()).hexdigest()},
    }

    ideal_rows, full_rows = [], []
    source_stats = {
        "small_cap_plan": backtest.get("plan", {}).get("full"),
        "small_cap_plan_hold": backtest.get("plan_hold", {}).get("full"),
        "small_cap_pool": backtest.get("pool", {}).get("full"),
        "399006.SZ": backtest.get("comparisons", {}).get("399006.SZ", {}).get("full"),
        "932000.CSI": backtest.get("comparisons", {}).get("932000.CSI", {}).get("full"),
        "index": backtest.get("stats", {}).get("index", {}).get("full"),
        "random": {"cagr_pct": backtest.get("null", {}).get("random", {}).get("cagr_pct", {}).get("median"),
                   "max_drawdown_pct": backtest.get("null", {}).get("random", {}).get("max_drawdown_pct", {}).get("median")},
    }
    for key in ('live_rule', 'alpha', 'alpha_regime', 'beta', 'beta_offense', 'stance'):
        source_stats[key] = backtest['stats'][key]['full']
    for key in chart_keys:
        full = source_stats.get(key) or metric(curves[key])
        recent = metric(curves[key][recent_index:])
        full_rows.append([
            html.escape(chart_names[key]), pct(full.get("cagr_pct")), pct(full.get("max_drawdown_pct")),
            '路径统计中位' if key == 'random' else pct(full.get('total_pct')),
        ])
        if key == 'random':
            continue  # Window medians cannot be inferred from a pointwise-median path.
        ideal_rows.append([html.escape(chart_names[key]), pct(recent['total_pct']), pct(recent['cagr_pct']),
                           pct(recent['max_drawdown_pct']), number(recent['lowest_nav'], 3), number(recent['final_nav'], 3)])

    chart_payload['recent_metrics'] = {key: metric(curves[key][recent_index:]) for key in chart_keys if key != 'random'}
    chart_payload['account_metrics'] = {key: {**metric(values), **{k: float(v) for k,v in real[source].items()
                                      if v is not None and k in ('cagr_pct','max_drawdown_pct','lowest_nav','final_nav','fees_pct_of_start','idle_pct')}}
                                      for key,source,values in [('account_tp10','tp10',real['tp10']['nav']), ('account_base','base',real['base']['nav']),
                                                                 ('399006.SZ','chinext',real['index_nav'])]}

    real_rows = []
    for key, label in (("tp10", "止盈10%"), ("base", "不止盈（对照）"), ("chinext", "创业板指")):
        item = real[key]
        real_rows.append([
            html.escape(label), pct(metric(item['nav'] if key != 'chinext' else real['index_nav'])['total_pct']),
            pct(item.get("cagr_pct")), pct(item.get("max_drawdown_pct")),
            number(item.get("lowest_nav"), 3), number(item.get("final_nav"), 3),
            number(item.get("fees_pct_of_start"), 2) if key != "chinext" else "—",
            number(item.get("idle_pct"), 1) + "%" if item.get("idle_pct") is not None else "—",
            str(item.get("rule_sales")) if item.get("rule_sales") is not None else "—",
        ])

    path_rows = []
    for index, (tp, base) in enumerate(zip(sell_rules["TP10"]["paths"], sell_rules["base"]["paths"]), 1):
        path_rows.append([
            f"{index}", html.escape(tp["start"]), pct(tp["cagr_pct"]), pct(base["cagr_pct"]),
            f'{tp["cagr_pct"] - base["cagr_pct"]:+.2f}', pct(tp["max_drawdown_pct"]),
            number(tp["lowest_nav"], 3), str(tp["periods"]),
        ])
    tp_recent = sell_rules["TP10"]["recent"]
    four_median = statistics.median(x['cagr_pct'] for x in sell_rules['TP10']['paths'][:4])
    sell_names = {'base':'不止盈（基准）','T10':'每10日换手','T40':'每40日换手','REBAL':'换手时全部重买',
                  'GAP':'高开兑现','GAP+':'高开兑现后补股','UP7':'单日收盘涨7%后卖','SPIKE':'成交额三倍且收涨后卖',
                  'TP10':'止盈10%（主策略）','TP20':'止盈20%','SL10':'个股止损10%','SL15':'个股止损15%',
                  'TRAIL':'从持仓最高收盘回落10%卖','BBI':'按BBI离场','ST':'持有期间戴帽卖'}
    sell_rows = [[html.escape(sell_names[key]), pct(statistics.median(p['cagr_pct'] for p in value['paths'])),
                  f"{min(p['max_drawdown_pct'] for p in value['paths']):.1f}% 至 {max(p['max_drawdown_pct'] for p in value['paths']):.1f}%",
                  pct(value['recent']['cagr_pct']),pct(value['recent']['max_drawdown_pct'])]
                 for key,value in sell_rules.items()]

    payload = json.dumps(chart_payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace('<', '\\u003c')
    echarts = ECHARTS.read_text(encoding="utf-8")
    html_doc = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>小盘轮换 v0.3 回测对比</title>
<style>
:root {{ color-scheme: light; --bg:#f1f0ed; --paper:#fff; --ink:#242321; --muted:#6d6a64; --line:#dedbd4; --soft:#f7f6f2; --red:#b74232; --green:#23745b; --blue:#356d91; --purple:#7653a8; --amber:#9a6b19; }}
* {{ box-sizing:border-box; }} html {{ background:var(--bg); }} body {{ margin:0; color:var(--ink); background:var(--bg); font-family:"Avenir Next","PingFang SC","Microsoft YaHei",sans-serif; line-height:1.7; letter-spacing:0; }}
.sheet {{ width:min(1320px,calc(100% - 28px)); margin:22px auto 44px; background:var(--paper); border-top:6px solid var(--ink); }}
header {{ padding:40px 54px 34px; border-bottom:1px solid var(--line); }} h1,h2,h3 {{ margin:0; font-family:"Songti SC","STSong",Georgia,serif; font-weight:500; }} h1 {{ font-size:44px; line-height:1.18; }} h2 {{ font-size:29px; line-height:1.3; margin-bottom:14px; }} h3 {{ font-size:21px; margin:24px 0 8px; }} p {{ margin:10px 0; }} .kicker {{ color:var(--red); font:12px/1.4 "SFMono-Regular",Consolas,monospace; letter-spacing:.04em; }} .subtitle {{ max-width:980px; color:var(--muted); font-family:"Songti SC","STSong",Georgia,serif; font-size:20px; margin-top:15px; }} .meta {{ color:var(--muted); font:12px/1.5 "SFMono-Regular",Consolas,monospace; margin-top:20px; }}
.findings {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); border-bottom:1px solid var(--line); }} .finding {{ padding:22px 26px; border-right:1px solid var(--line); }} .finding:last-child {{ border-right:0; }} .finding strong {{ display:block; font-family:"Songti SC","STSong",Georgia,serif; font-size:18px; font-weight:500; }} .finding p {{ color:var(--muted); font-size:14px; margin:4px 0 0; }} main {{ padding:42px 54px 64px; }} section {{ padding-bottom:42px; margin-bottom:46px; border-bottom:1px solid var(--line); }} section:last-child {{ border-bottom:0; margin-bottom:0; }} .note {{ color:var(--muted); font-size:14px; background:var(--soft); border:1px solid var(--line); padding:12px 15px; }} .rule-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 32px; }} .rule-grid p {{ border-bottom:1px solid var(--line); padding:8px 0; margin:0; }} .rule-grid b {{ font-weight:600; }} .chart {{ width:100%; height:440px; margin:14px 0 8px; border:1px solid var(--line); }} .chart.small {{ height:400px; }} .switches {{ display:flex; gap:8px; flex-wrap:wrap; margin:0 0 10px; }} button {{ border:1px solid var(--line); background:var(--paper); color:var(--ink); padding:7px 12px; cursor:pointer; font:inherit; font-size:14px; }} button[aria-pressed="true"] {{ border-color:var(--ink); background:var(--ink); color:#fff; }} .table-wrap {{ overflow-x:auto; border:1px solid var(--line); }} table {{ border-collapse:collapse; width:100%; min-width:760px; font-size:14px; }} th,td {{ padding:9px 11px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }} th:first-child,td:first-child {{ text-align:left; }} th {{ background:var(--soft); font-weight:600; color:#55514a; }} tr:last-child td {{ border-bottom:0; }} tbody tr:first-child {{ background:#fcf6ed; }} .accent {{ color:var(--red); font-weight:600; }} .good {{ color:var(--green); font-weight:600; }} .muted {{ color:var(--muted); }} .two-col {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:30px; min-width:0; }} ul {{ margin:8px 0; padding-left:22px; }} li {{ margin:5px 0; }} footer {{ color:var(--muted); font-size:13px; padding-top:4px; overflow-wrap:anywhere; }} details {{ margin:20px 0; }} summary {{ cursor:pointer; padding:14px; border:1px solid var(--line); background:var(--soft); font-weight:600; }} a {{ color:var(--blue); }}
@media (max-width:760px) {{ .sheet {{ width:100%; margin:0; border-top-width:4px; }} header,main {{ padding-left:18px; padding-right:18px; }} h1 {{ font-size:32px; }} .subtitle {{ font-size:17px; }} .findings,.rule-grid,.two-col {{ grid-template-columns:1fr; }} .finding {{ border-right:0; border-bottom:1px solid var(--line); }} .finding:last-child {{ border-bottom:0; }} .chart {{ height:350px; }} .chart.small {{ height:330px; }} section {{ padding-bottom:30px; margin-bottom:34px; }} }}
</style>
</head>
<body>
<div class="sheet">
<header><div class="kicker">RESEARCH / FROZEN BACKTEST / 2026-10-30</div>
<h1>小盘轮换 v0.3：回测与账户模型对比</h1>
<p class="subtitle">按你的决定，小盘轮换 v0.3 作为当前主策略。以最近20个月为主要观察窗口，对比不止盈、股票池、创业板指、中证2000、中证全指，以及此前的阿尔法／贝塔方案。</p>
<div class="meta">策略版本：v0.3 · 冻结曲线：2024-03-04 至 2026-10-30（645个交易日） · 账户模拟：{RECENT_START} 至 {real['end']}（约20个月）</div></header>
<div class="findings"><div class="finding"><strong>当前主策略</strong><p>每20个交易日换手，主板和创业板，5只冷门且最近一季收入、利润同比为正的股票；收盘高于买价10%后次日开盘卖出，钱留到下一换手日。</p></div>
<div class="finding"><strong>1万元整手账户模拟</strong><p>以2月28日为窗口内的首次决策日起算，止盈10%年化 {pct(real['tp10'].get('cagr_pct'))}，最大回撤 {pct(real['tp10'].get('max_drawdown_pct'))}。换手日历与7月1日起的标准节奏一致。</p></div>
<div class="finding"><strong>阅读方式</strong><p>历史数字是可行性证据，不是未来收益预期。下一步看规则能否在样本外持续执行，不能用单个年化数字替代记账。</p></div></div>
<main>
<section><h2>最近20个月：主策略与其他方案</h2><p>区间：{dates[recent_index]} 至 {dates[-1]}，{len(dates)-recent_index}个交易日。所有线从窗口首日收盘归一为1，保留此前持仓和买入价；这是连续策略的区间表现，不是在该日拿1万元重新买入。</p>
<div class="switches"><button id="show-main" aria-pressed="true">主策略与基准</button><button id="show-old" aria-pressed="false">加入旧方案</button></div>
<div id="recent-chart" class="chart"></div>
{table(["对象","累计收益","年化收益","最大回撤","窗口最低净值","期末净值"], ideal_rows)}
<p class="note">主策略、不止盈和股票池采用理想化等权，每次买卖按每边0.1%成本计算；旧阿尔法／贝塔方案采用10个等额名额、5日持有，买入0.075%、卖出0.125%成本。指数为价格指数，不计交易费用。股票池采用不止盈卖法：主策略减股票池同时含选股与卖法差异；比较选股时先看“不止盈减股票池”。</p>
<p class="muted">随机参考为20次抽样的逐日中位曲线；近期单次路径未冻结，不能从该线推算“20次近期收益中位数”，因此近期统计表不列它。随机参考采用旧方案的10个名额与5日持有，也不是主策略股票池内随机挑5只的对照。</p></section>

<section><h2>1万元整手账户：同窗口进场起点检验</h2><p>以 {RECENT_START} 收盘为首次决策日，下一个交易日开盘开始买，每20个交易日再换手。模拟至 {real['end']}，共{len(real['dates'])}个交易日、{real['tp10']['periods']}个期间（含未完成的末期）。保留每笔原买入成本、现金和持仓；万一免五，卖出另计0.05%印花税、0.001%过户费，现金不计息，默认滑点为0。</p>
<div id="account-chart" class="chart small"></div>
{table(["对象","累计收益","年化","最大回撤","最低净值","期末净值","费用占本金(%)","平均闲置现金","止盈卖出次数"], real_rows)}
<p class="note">止盈10%比不止盈年化高 {real['tp10']['cagr_pct'] - real['base']['cagr_pct']:+.2f} 个百分点，最大回撤浅 {number(abs(real['base']['max_drawdown_pct']) - abs(real['tp10']['max_drawdown_pct']), 2)} 个百分点。它从2月28日以1万元现金开始模拟；20日换手相位与7月1日标准日历完全一致。与曲线截取的区别是从窗口首日重新投入本金，重新计算整手股数与持仓。</p>
<p class="muted">账户模型未使用日报公开的固定3只备选上限，而是在完整排序中继续找可买股票；因此买入候选范围还未完全一致。账户0.7底线未在该卖法脚本中触发执行，这两条路径最低净值均高于0.7。以上结果属于账户模拟，未连接你的实际成交。</p></section>

<section><h2>采用的规则与执行页差异</h2><div class="rule-grid">
<p><b>换手</b> 从2024-07-01起每20个交易日定名单，下一交易日开盘换股。</p>
<p><b>选股</b> 非ST、上市满120天；近20日日均成交额最低五分之一；已公告最近一季收入、利润同比均为正；只留主板和创业板。</p>
<p><b>买卖</b> 5只，整手；新名单仍有的旧股保留；收盘相对买价涨10%后次日开盘卖，资金留到下一换手日。</p>
<p><b>约束</b> 不上杠杆；账户收盘净值跌破0.7，次日开盘起卖出停用。跳空、跌停或停牌可能使亏损超过30%。</p>
</div><p class="note">已核实日报执行页每期按固定1万元估算，尚未把跨期现金、真实旧仓与原始买入价连续接起来。正确记账应使用上一日实际现金与持仓，卖出后更新现金，止盈沿用原买入成本；本次生成报告，没有修改日报交易逻辑。</p>
<p><a href="../../wiki/交易思想/小盘轮换策略.md">完整策略规则</a> · <a href="../../wiki/交易思想/回测与检验证据.md">回测依据与后续检验条件</a></p></section>

<section><h2>历史补充（早于20个月的结果）</h2><p class="muted">按你的偏好，这些结果只作补充，默认收起。下面都是已经看过的数据，不能称为新规则冻结后的样本外检验。</p>
<details id="full-history"><summary>展开全历史理想化曲线与对比</summary><p>区间：2024-03-04 至 2026-10-30；这套曲线向前沿用7月1日的20日节奏，包含7月以前的模拟，不应与7月1日开始的账户结果直接横比。</p>
<div id="full-chart" class="chart"></div>{table(["对象","年化","最大回撤","累计收益"], full_rows)}
<p class="muted">随机一行的年化和回撤分别为20次路径各自统计量的中位数；它们不一定来自同一条路径，也不等于逐日中位曲线的统计。</p></details>
<details><summary>展开八条账户起点路径与14种替代卖法</summary><p>以下全部账户检验截至2026-10-29。各路径共享大部分行情，不是8次独立实验。差值单位为百分点，期间数含末期。</p>
{table(["路径","起点","止盈10%年化","不止盈年化","年化差值(百分点)","止盈10%回撤","最低净值","期间数"], path_rows)}
<div class="two-col"><div><h3>47.5%究竟指什么</h3><p>2024年7月四个起点的止盈10%年化中位为 {pct(four_median,2)}；全部八个起点年化中位为 {pct(statistics.median(x['cagr_pct'] for x in sell_rules['TP10']['paths']),2)}。这两个数字的分母不同，都不是未来预期。</p></div><div><h3>另一个较短窗口</h3><p>原结果中的“近期”从 {tp_recent['start']} 开始，到2026-10-29；止盈10%年化 {pct(tp_recent['cagr_pct'])}，回撤 {pct(tp_recent['max_drawdown_pct'])}。该窗口约18个月，与上面的20个月不是同一段数据。</p></div></div>
<h3>其他卖法的历史结果</h3>{table(["卖法","八起点年化中位","八起点最大回撤范围","18个月年化","18个月回撤"], sell_rows)}
<p class="muted">这些卖法共用相同选股池和账户参数；止盈10%是比较之后采纳的。结果较好只能支持继续检验，不能排除挑选偏差。</p></details></section>

<section><h2>当前判断与剩余问题</h2><p><b>判断：</b>按你的决定，小盘轮换 v0.3 是当前主策略；已有历史可行性证据，继续用之后的新数据前推。执行重点是按规则记账、观察止盈与不止盈两本账，并以创业板指作为收益与回撤参照。</p><ul>
<li>最近20个月是当前观察范围；是否更适合今天的市场需要由后续记录检验，数据本身不能证明变化一定由AI量化造成。</li>
<li>止盈10%是在查看历史结果后采纳的，仍属于需要前推确认的规则。</li>
<li>数据和检验主要来自同一冻结数据链，不是独立数据源复核。</li>
<li>集合竞价挂单、冲击成本、红利税、退市处理等现实因素没有完整纳入。</li>
<li>账户模拟是1万元示例；备选范围和日报跨期记账仍有差异，尚不能声明完全复现实盘。</li>
</ul><p class="note"><b>下一步：</b>把每个换手周期的实际成交、期末净值和两本账继续写入同一记录；至少完成6个新的换手周期，再比较止盈10%是否仍然同时满足收益更高、回撤不更深。</p></section>

<footer>来源：{SNAPSHOT.relative_to(ROOT)}；{SELL_RULES_JSON.relative_to(ROOT)}；模拟逻辑：{SELL_RULES_PY.relative_to(ROOT)}。本页为研究阅读页，不覆盖正式日报和冻结快照。</footer>
</main></div>
<script id="backtest-payload" type="application/json">{payload}</script>
<script>{echarts}</script>
<script>
(() => {{
  const data = JSON.parse(document.getElementById('backtest-payload').textContent);
  const colors = {{small_cap_plan:'#b74232', small_cap_plan_hold:'#7653a8', small_cap_pool:'#c48c35', '399006.SZ':'#356d91', '932000.CSI':'#23745b', index:'#242321', random:'#9b9891',account_tp10:'#b74232',account_base:'#7653a8',live_rule:'#5d769b',alpha:'#ab738a',alpha_regime:'#bc9ab0',beta:'#4e8d93',beta_offense:'#87b5ba',stance:'#847959'}};
  const kinds = {{small_cap_plan:'solid',small_cap_plan_hold:'dashed',small_cap_pool:'dotted',random:'dashed'}};
  const oldKeys = new Set(['live_rule','alpha','alpha_regime','beta','beta_offense','stance']);
  function draw(id, set) {{
    const node = document.getElementById(id); const chart = echarts.init(node);
    const keys = Object.keys(set.curves);
    chart.setOption({{animation:false, tooltip:{{trigger:'axis',valueFormatter:v => v == null ? '—' : Number(v).toFixed(3)}},
      legend:{{top:4,type:'scroll',data:keys.map(k => data.names[k]),selected:Object.fromEntries(keys.map(k=>[data.names[k],!oldKeys.has(k)&&k!=='random']))}}, grid:{{left:48,right:18,top:46,bottom:36}},
      xAxis:{{type:'category',data:set.dates,axisLabel:{{formatter:v => v.slice(2,7),color:'#6d6a64'}},axisLine:{{lineStyle:{{color:'#dedbd4'}}}}}},
      yAxis:{{type:'value',scale:true,axisLabel:{{color:'#6d6a64'}},splitLine:{{lineStyle:{{color:'#eeeae3'}}}}}},
      series:keys.map(k => ({{name:data.names[k],type:'line',data:set.curves[k],showSymbol:false,lineStyle:{{width:k==='small_cap_plan'||k==='account_tp10'?3:1.7,color:colors[k],type:kinds[k]||'solid'}},itemStyle:{{color:colors[k]}}}}))
    }});
    window.addEventListener('resize', () => chart.resize());
    return chart;
  }}
  const recent = draw('recent-chart', data.recent); draw('account-chart',data.account);
  ['show-main','show-old'].forEach(id=>document.getElementById(id).addEventListener('click',()=>{{
    const old = id==='show-old';
    recent.setOption({{legend:{{selected:Object.fromEntries(Object.keys(data.recent.curves).map(k=>[data.names[k],k!=='random'&&(!oldKeys.has(k)||old)]))}}}});
    document.getElementById('show-main').setAttribute('aria-pressed',String(!old));
    document.getElementById('show-old').setAttribute('aria-pressed',String(old));
  }}));
  let full;
  document.getElementById('full-history').addEventListener('toggle',event=>{{
    if(event.currentTarget.open){{ if(!full) full=draw('full-chart',data.full); else full.resize(); }}
  }});
}})();
</script>
</body></html>'''
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html_doc, encoding="utf-8")
    print(OUTPUT)
    print(f"bytes={OUTPUT.stat().st_size}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "scripts"))
    render()
