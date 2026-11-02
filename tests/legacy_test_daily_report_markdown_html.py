import copy
import io
import json
import re
import sys
import shutil
import subprocess
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.markdown_report_html import (
    _bear_sector_cycle_swimlane_html,
    _echarts_loader_html,
    _position_timeline_execution_tag,
    _sector_feedback_timeline,
    main as render_markdown_report_main,
    render_markdown_report_file,
    render_markdown_report_html,
)
from report.candidate_decision_evidence import (
    build_sector_diffusion_stage_evidence,
    build_sector_tournament_three_axis,
)
from report.formal_account_decision import build_decision_projection
from report.market_overview_builder import build_market_trend_sections_contract


SECTOR_STAGE_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "sector_stage_mainline"
    / "cxo_2026-07-31_2026-08-14.json"
)


def _lhb_row_html(html: str, code: str) -> str:
    """Return the rendered reader-table row carrying ``code`` in its own cell."""
    for line in html.splitlines():
        if "<tr>" in line and f">{code}<" in line:
            return line
    raise AssertionError(f"渲染结果中缺少代码 {code} 的表格行")


def cffex_chart_states(html, payload):
    """Run emitted chart code with a minimal ECharts merge/DOM adapter."""
    if not shutil.which('node'):
        raise unittest.SkipTest('chart behavior checks require node')
    helpers = html[html.index('const escapeText ='):html.index('const renderMarketStructureChart =')]
    base = html[html.index('const baseChartOption ='):html.index('const marketTrendXAxis =')]
    renderer = html[html.index('const renderCffexPositionTrendChart ='):html.index('const renderMarketTurnoverTrendChart =')]
    script = r'''
const fs=require('fs'), vm=require('vm'), input=JSON.parse(fs.readFileSync(0,'utf8'));
const buttons=[20,60].map(size=>({dataset:{windowSize:String(size)},handlers:{},
  setAttribute(k,v){this[k]=v;},addEventListener(k,fn){this.handlers[k]=fn;}}));
const node={closest:()=>({querySelector:()=>({querySelectorAll:()=>buttons})})};
const handlers={}; let option={};
function merge(a,b){
  if(Array.isArray(b))return b.map((value,i)=>merge(a?.[i],value));
  if(b&&typeof b==='object'){const out={...a};for(const k of Object.keys(b))out[k]=merge(a?.[k],b[k]);return out;}
  return b;
}
const chart={setOption(value){option=merge(option,value);},getOption:()=>option,
  on(name,fn){handlers[name]=fn;}};
global.document={documentElement:{}};
global.getComputedStyle=()=>({getPropertyValue:()=>''});
global.window={echarts:{init:()=>chart}};
vm.runInThisContext(input.code+'\nrenderCffexPositionTrendChart(globalThis.node, globalThis.payload);');
'''
    script = script.replace("vm.runInThisContext", "global.node=node;global.payload=input.payload;\nvm.runInThisContext")
    script += r'''
const states=[];
function capture(){states.push({option,tooltip:option.tooltip.formatter([{dataIndex:0}]),
  lastTooltip:option.tooltip.formatter([{dataIndex:option.xAxis[0].data.length-1}]),
  pressed:buttons.map(b=>b['aria-pressed']),events:Object.keys(handlers)});}
capture();
chart.setOption({legend:{selected:{'中信名义净空':false,'中信净空日变':true,'前20榜单净空差':false}}});
buttons[0].handlers.click();capture();buttons[1].handlers.click();capture();
process.stdout.write(JSON.stringify(states));
'''
    result = subprocess.run(['node', '-e', script], input=json.dumps({'code': helpers + base + renderer, 'payload': payload}),
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def _cffex_position_evidence(
    *,
    target_date="2026-08-19",
    source_date=None,
    item_count=61,
    include_future=False,
    null_index=None,
):
    target = date.fromisoformat(target_date)
    start = target - timedelta(days=item_count - 1)
    dates = [(start + timedelta(days=index)).isoformat() for index in range(item_count)]
    if include_future:
        dates.append((target + timedelta(days=1)).isoformat())

    def values(metric):
        rows = []
        for index, item_date in enumerate(dates):
            value = {
                "member_net_short_change": -3000 + index * 100,
                "member_net_short_notional": 80_000_000_000 + index * 100_000_000,
                "top20_cross_section_net_short": 110_000 + index * 250,
            }[metric]
            if null_index == index:
                value = None
            rows.append({"trade_date": item_date, "value": value})
        return rows

    windows = {}
    for metric in (
        "member_net_short_change",
        "member_net_short_notional",
        "top20_cross_section_net_short",
    ):
        metric_values = values(metric)
        windows[metric] = {
            "20": {"values": metric_values[-20:]},
            "60": {"values": metric_values[-60:]},
        }
    return {
        "schema_version": "cffex_index_futures_position_evidence.v1",
        "target_date": target_date,
        "source_date": source_date or target_date,
        "artifact_hash": "cffex-test-hash",
        "history": {"windows": windows},
    }


def _sector_relative_path_artifact(
    target_date="2026-08-14",
    *,
    records=None,
    daily_attack_line="半导体",
    broad_market_confirmation=False,
):
    if records is None:
        fixture = json.loads(SECTOR_STAGE_FIXTURE.read_text(encoding="utf-8"))
        records = [fixture["record"]]
    records = copy.deepcopy(records)
    for record in records:
        record["source_date"] = target_date
        scope = record.get("comparison_universe_scope")
        if isinstance(scope, dict):
            scope["source_date"] = target_date
        for comparison in record.get("comparison_universe") or []:
            comparison["source_date"] = target_date
    direction = str(records[0].get("direction") or "") if records else ""
    active_dates = list(records[0].get("active_trade_dates") or []) if records else []
    proof = {
        "direction": direction,
        "direction_source_date": target_date,
        "source_date": target_date,
        "source_date_matches_target": True,
        "continuity_dates": [value for value in active_dates if value <= target_date],
        "cross_day_continuity_status": "confirmed",
        "divergence_acceptance_status": "confirmed",
        "internal_expansion_status": "confirmed",
        "competition_comparison_status": "confirmed",
        "competition_state": "单主线聚焦",
        "stage_mainline_evidence": {
            "directions": records,
            "daily_attack_line": daily_attack_line,
            "daily_attack_line_source_date": target_date,
            "intraday_rotation_count": 3,
            "intraday_rotation_source_date": target_date,
        },
        "cross_day_competition": {
            "source_date": target_date,
            "possible_divergence_directions": [direction],
            "possible_beneficiary_directions": [daily_attack_line],
            "confirmation_facts": ["观察阶段方向分歧是否形成承接"],
            "falsification_facts": ["阶段方向失去承接"],
        },
    }
    stage = build_sector_diffusion_stage_evidence(
        target_date=target_date,
        local_trend_sector_proof=proof,
        price_acceptance_rows=[
            {
                "stock": {"code": "600000", "name": "阶段样本"},
                "sector": direction,
                "status": "accepted",
                "source_date": target_date,
                "source_refs": ["fixture.quote"],
            }
        ],
        source_refs=["fixture.stage"],
    )
    return build_sector_tournament_three_axis(
        target_date=target_date,
        sector_diffusion_stage_evidence=stage,
        local_trend_sector_proof=proof,
        market_participation_limit={
            "source_date": target_date,
            "market_state": "震荡混沌",
            "broad_market_confirmation": broad_market_confirmation,
            "systemic_risk": False,
            "weak_market": True,
        },
        source_refs=["fixture.market", "fixture.stage"],
    )


def _sector_relative_path_markdown():
    return "\n".join(
        [
            "# 相对路径日报",
            "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
            "#### 近期热点板块成交额连续跟踪：[CXO/创新药]",
            "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
            "|---|---:|---:|---:|---:|---|---|",
            "| 2026-08-14 | 1200亿 | 20000亿 | 6.0% | +0.2pct | 同板块连续 | 成交占比仅作辅助 |",
            "#### 小周期成交额与主线切换判断",
            "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
            "|---|---|---:|---:|---:|---:|---|---|",
            "| 2026-08-13 | 半导体 | 2200亿 | 20000亿 | 11.0% | +0.5pct | 当日轮动 | 辅助记录 |",
            "| 2026-08-14 | CXO/创新药 | 1200亿 | 20000亿 | 6.0% | +0.2pct | 阶段延续 | 辅助记录 |",
        ]
    )


class DailyReportMarkdownHtmlTest(unittest.TestCase):
    def test_render_omits_markdown_html_comments_from_visible_body(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 注释测试",
                    "",
                    "正文保留。",
                    "<!-- sector_tournament_three_axis artifact_hash="
                    + "a" * 64
                    + " -->",
                    "<!-- 多行内部标记",
                    "仍不可见 -->",
                    "后文保留。",
                ]
            ),
            title="注释测试",
            trade_date="2026-08-17",
        )

        self.assertIn("正文保留。", html)
        self.assertIn("后文保留。", html)
        self.assertNotIn("artifact_hash", html)
        self.assertNotIn("多行内部标记", html)
        self.assertNotIn("仍不可见", html)

    def test_render_tomorrow_action_calendar_before_position_timeline(self):
        calendar = {
            "schema": "tomorrow_action_calendar.v1",
            "mode": "frozen",
            "requested_count": 25,
            "record_count": 4,
            "execution_date_start": "2026-06-01",
            "execution_date_end": "2026-06-04",
            "source": "postgresql.strategy_performance_ledger",
            "records": [
                {
                    "report_date": "2026-05-29",
                    "execution_date": "2026-06-01",
                    "weekday_label": "周一",
                    "action_kind": "empty",
                    "action_label": "空仓",
                    "plan_action_kind": "empty",
                    "plan_action_label": "空仓",
                    "daily_return_pct": 0.0,
                    "excess_shanghai_pct": 1.2,
                    "performance_status": "complete",
                },
                {
                    "report_date": "2026-06-01",
                    "execution_date": "2026-06-02",
                    "weekday_label": "周二",
                    "action_kind": "target",
                    "action_label": "长电科技<script>(600584)",
                    "action_items": [
                        {
                            "label": "长电科技<script>(600584)",
                            "position_label": "1x/50%",
                            "holding_label": "第2日",
                            "plan_date_label": "2026-05-29",
                        },
                        {
                            "label": "华天科技&验证(002185)",
                            "position_label": "1x/50%",
                            "holding_label": "第1日",
                            "plan_date_label": "2026-06-01",
                        },
                    ],
                    "plan_action_kind": "target",
                    "plan_action_label": "华天科技(002185)",
                    "daily_return_pct": 3.2,
                    "excess_shanghai_pct": 2.5,
                    "performance_status": "complete",
                },
                {
                    "report_date": "2026-06-02",
                    "execution_date": "2026-06-03",
                    "weekday_label": "周三",
                    "action_kind": "target",
                    "action_label": "长电科技(600584)",
                    "action_items": [
                        {
                            "label": "长电科技(600584)",
                            "position_label": "2x/100%",
                            "holding_label": "第1+2日",
                            "plan_date_label": "2026-06-01/2026-06-02",
                        }
                    ],
                    "plan_action_kind": "target",
                    "plan_action_label": "长电科技(600584)",
                    "daily_return_pct": None,
                    "excess_shanghai_pct": None,
                    "performance_status": "future",
                },
                {
                    "report_date": "2026-06-03",
                    "execution_date": "2026-06-04",
                    "weekday_label": "周四",
                    "action_kind": "target",
                    "action_label": "长电科技(600584)",
                    "action_items": [
                        {
                            "label": "长电科技(600584)",
                            "position_label": "1x/50%",
                            "holding_label": "第2日",
                            "plan_date_label": "2026-06-02",
                        }
                    ],
                    "plan_action_kind": "no_new_entry",
                    "plan_action_label": "不新增<计划>",
                    "daily_return_pct": None,
                    "excess_shanghai_pct": None,
                    "performance_status": "incomplete",
                },
            ],
            "summary": {
                "valid_count": 2,
                "plan_target_count": 2,
                "holding_count": 3,
                "target_count": 3,
                "empty_count": 1,
                "no_new_entry_count": 1,
                "incomplete_count": 1,
                "future_count": 1,
                "outperform_count": 2,
                "average_daily_return_pct": 1.6,
                "average_excess_shanghai_pct": 1.85,
                "cumulative_daily_return_pct": 3.2,
                "cumulative_shanghai_return_pct": -0.27,
                "cumulative_excess_shanghai_pct": 3.47,
            },
            "cumulative_returns": {
                "rolling_25": {"coverage_status": "complete", "cumulative_daily_return_pct": 3.2},
                "current_month": {"coverage_status": "complete", "cumulative_daily_return_pct": 2.5},
                "since_start": {"coverage_status": "complete", "cumulative_daily_return_pct": 8.75},
            },
        }
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-06-01（周一） | 最远复盘日 | - | 不生成B1/B2 | 只作路径校对 |",
                    "| Tb | 2026-06-02（周二） | 历史复盘日 | - | 不生成B1/B2 | 只作路径校对 |",
                    "| Tc | 2026-06-03（周三） | 上一交易日路径 | - | 不生成B1/B2 | 进入复核 |",
                    "| Td | 2026-06-04（周四） | 报告日 | 无 | 只定Te预案 | 写清条件 |",
                    "| Te | 2026-06-05（周五） | 明日路径 | 无 | 不生成B1/B2 | 不新增 |",
                    "",
                    "# 测试日报",
                ]
            ),
            title="测试日报",
            trade_date="2026-06-04",
            tomorrow_action_calendar=calendar,
        )

        calendar_index = html.index('class="tomorrow-action-calendar"')
        timeline_index = html.index('class="position-timeline-shell is-day-order"')
        self.assertLess(calendar_index, timeline_index)
        self.assertIn("最近25条明日操作日历", html)
        for weekday in ("周一", "周二", "周三", "周四", "周五"):
            self.assertIn(f'<th scope="col">{weekday}</th>', html)
        self.assertIn("2026-06-02", html)
        self.assertIn("当日涨幅", html)
        self.assertIn("+3.20%", html)
        self.assertIn("跑赢上证", html)
        self.assertIn("+2.50%", html)
        self.assertIn('<dd class="is-incomplete">—</dd>', html)
        self.assertIn("有效 2 日", html)
        self.assertIn("平均当日涨幅 +1.60%", html)
        self.assertIn("平均跑赢上证 +1.85%", html)
        self.assertIn("明日标的计划 2 日", html)
        self.assertIn("账户持仓 3 日", html)
        self.assertIn("滚动25天累计收益 +3.20%", html)
        self.assertIn("当前月累计收益 +2.50%", html)
        self.assertIn("2026-06-17起累计收益 +8.75%", html)
        self.assertIn("跑赢 2/2 日", html)
        self.assertIn("未结算 1 日", html)
        self.assertIn("1x/50% · 第2日 · 计划日报 2026-05-29", html)
        self.assertIn("1x/50% · 第1日 · 计划日报 2026-06-01", html)
        self.assertIn("2x/100% · 第1+2日 · 计划日报 2026-06-01/2026-06-02", html)
        self.assertIn("本日计划：不新增&lt;计划&gt;", html)
        self.assertIn("本格计划日报 2026-06-03", html)
        self.assertIn("长电科技&lt;script&gt;(600584)", html)
        self.assertIn("华天科技&amp;验证(002185)", html)
        self.assertNotIn("长电科技<script>", html)
        self.assertNotIn("不新增<计划>", html)

    def test_render_empty_tomorrow_action_calendar_names_the_missing_record_set(self):
        html = render_markdown_report_html(
            "# 测试日报",
            tomorrow_action_calendar={
                "schema": "tomorrow_action_calendar.v1",
                "mode": "replay",
                "requested_count": 25,
                "record_count": 0,
                "status": "source_incomplete",
                "records": [],
                "summary": {},
            },
        )

        self.assertIn("最近25条明日操作日历", html)
        self.assertIn("未读取到近25条明日操作记录", html)
        self.assertNotIn("事实不足", html)
        self.assertNotIn('class="tomorrow-action-calendar-table"', html)

    def test_render_tomorrow_action_calendar_rejects_non_finite_returns(self):
        html = render_markdown_report_html(
            "# 测试日报",
            tomorrow_action_calendar={
                "schema": "tomorrow_action_calendar.v1",
                "mode": "frozen",
                "requested_count": 25,
                "record_count": 1,
                "execution_date_start": "2026-06-01",
                "execution_date_end": "2026-06-01",
                "records": [
                    {
                        "report_date": "2026-05-29",
                        "execution_date": "2026-06-01",
                        "weekday_label": "周一",
                        "action_kind": "empty",
                        "action_label": "空仓",
                        "plan_action_kind": "no_new_entry",
                        "plan_action_label": "不新增",
                        "daily_return_pct": float("nan"),
                        "excess_shanghai_pct": float("inf"),
                        "performance_status": "complete",
                    }
                ],
                "summary": {
                    "valid_count": 1,
                    "average_daily_return_pct": float("nan"),
                    "average_excess_shanghai_pct": float("inf"),
                    "cumulative_daily_return_pct": float("-inf"),
                    "cumulative_shanghai_return_pct": float("nan"),
                    "cumulative_excess_shanghai_pct": float("inf"),
                },
                "cumulative_returns": {
                    "rolling_25": {"coverage_status": "complete", "cumulative_daily_return_pct": float("nan")},
                    "current_month": {"coverage_status": "complete", "cumulative_daily_return_pct": float("inf")},
                    "since_start": {"coverage_status": "source_incomplete", "cumulative_daily_return_pct": 9.9},
                },
            },
        )

        self.assertGreaterEqual(
            html.count('<dd class="is-incomplete">数值未记录</dd>'),
            2,
        )
        self.assertIn("平均当日涨幅 数值未记录", html)
        self.assertIn("滚动25天累计收益 数值未记录", html)
        self.assertIn("当前月累计收益 数值未记录", html)
        self.assertIn("2026-06-17起累计收益 累计值未结算", html)
        self.assertNotIn("事实不足", html)
        self.assertNotIn("nan%", html.lower())
        self.assertNotIn("inf%", html.lower())

    def test_render_tomorrow_action_calendar_excludes_incomplete_rolling_total(self):
        html = render_markdown_report_html(
            "# 测试日报",
            tomorrow_action_calendar={
                "schema": "tomorrow_action_calendar.v1",
                "requested_count": 25,
                "record_count": 1,
                "records": [
                    {
                        "report_date": "2026-08-17",
                        "execution_date": "2026-08-18",
                        "weekday_label": "周二",
                        "action_kind": "empty",
                        "action_label": "空仓",
                        "daily_return_pct": 1.2,
                        "excess_shanghai_pct": 0.3,
                        "performance_status": "complete",
                    }
                ],
                "summary": {"valid_count": 1, "cumulative_daily_return_pct": 1.2},
                "cumulative_returns": {
                    "rolling_25": {
                        "coverage_status": "source_incomplete",
                        "cumulative_daily_return_pct": 9.9,
                    }
                },
            },
        )

        self.assertIn("滚动25天累计收益 累计值未结算", html)
        self.assertNotIn("滚动25天累计收益 +9.90%", html)

    def test_render_tomorrow_action_calendar_names_unsettled_and_future_records(self):
        html = render_markdown_report_html(
            "# 测试日报",
            tomorrow_action_calendar={
                "schema": "tomorrow_action_calendar.v1",
                "requested_count": 25,
                "record_count": 2,
                "records": [
                    {
                        "report_date": "2026-08-17",
                        "execution_date": "2026-08-18",
                        "weekday_label": "周二",
                        "action_kind": "incomplete",
                        "action_label": "事实不足",
                        "performance_status": "incomplete",
                    },
                    {
                        "report_date": "2026-08-18",
                        "execution_date": "2026-08-19",
                        "weekday_label": "周三",
                        "action_kind": "incomplete",
                        "action_label": "事实不足",
                        "performance_status": "future",
                    },
                ],
                "summary": {"incomplete_count": 1, "future_count": 1},
            },
        )

        self.assertIn("账户记录未结算", html)
        self.assertIn("计划待执行", html)
        self.assertEqual(html.count('<dd class="is-incomplete">—</dd>'), 2)
        self.assertEqual(html.count('<dd class="is-pending">待发生</dd>'), 2)
        self.assertIn("未结算 1 日", html)
        self.assertNotIn("事实不足", html)

    def test_render_calendar_labels_holiday_and_sample_outside_cells(self):
        html = render_markdown_report_html(
            "# 测试日报",
            tomorrow_action_calendar={
                "schema": "tomorrow_action_calendar.v1",
                "mode": "frozen",
                "requested_count": 25,
                "record_count": 2,
                "execution_date_start": "2026-06-17",
                "execution_date_end": "2026-06-18",
                "records": [
                    {
                        "report_date": "2026-06-16",
                        "execution_date": "2026-06-17",
                        "weekday_label": "周三",
                        "action_kind": "empty",
                        "action_label": "空仓",
                        "plan_action_kind": "no_new_entry",
                        "plan_action_label": "不新增",
                        "daily_return_pct": 0.0,
                        "excess_shanghai_pct": 0.0,
                        "performance_status": "complete",
                    },
                    {
                        "report_date": "2026-06-17",
                        "execution_date": "2026-06-18",
                        "weekday_label": "周四",
                        "action_kind": "empty",
                        "action_label": "空仓",
                        "plan_action_kind": "no_new_entry",
                        "plan_action_label": "不新增",
                        "daily_return_pct": 0.0,
                        "excess_shanghai_pct": 0.0,
                        "performance_status": "complete",
                    },
                ],
                "calendar_notes": [
                    {
                        "date": "2026-06-19",
                        "weekday_label": "周五",
                        "kind": "holiday",
                        "label": "端午休假",
                        "source": "market_holiday_schedule",
                    }
                ],
                "summary": {
                    "valid_count": 2,
                    "plan_target_count": 0,
                    "holding_count": 0,
                    "empty_count": 2,
                    "no_new_entry_count": 2,
                },
            },
        )

        self.assertIn('aria-label="2026-06-15 周一 样本外"', html)
        self.assertIn('aria-label="2026-06-16 周二 样本外"', html)
        self.assertIn('aria-label="2026-06-19 周五 端午休假"', html)
        self.assertIn("端午休假", html)
        self.assertIn("非交易日", html)
        self.assertIn("空仓 2 日", html)
        self.assertIn("不新增计划 2 日", html)
        self.assertEqual(2, html.count('class="tomorrow-action-calendar-cell is-empty is-complete"'))

    def test_bear_html_preserves_new_high_structure_evidence_without_page_overflow(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 2026-07-13 A股日报",
                    "",
                    "### 4. 创新高趋势反馈",
                    "> 当前非ST阶段新高 6 只，占全A约 0.12%。",
                    "> 结构判断：扩散断层预警：首次进入个位数，板块呈碎片化。",
                    "> 风险含义：只作结构观察，不改变明日对象和仓位。",
                    "> 主要反证：同源数据连续回升、新板块成群时，收缩判断降级。",
                    "> 下一窗口：复核创新高是否连续回升以及核心与板块是否同步。",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-13",
        )

        self.assertIn("结构判断：扩散断层预警", html)
        self.assertIn("主要反证：同源数据连续回升", html)
        self.assertIn("下一窗口：复核创新高是否连续回升", html)
        self.assertIn("overflow-x: auto;", html)

    def test_render_ta_te_day_order_table_as_first_bear_html_block(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-06-23（周二） | 最远复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-06-24（周三） | 历史复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-06-25（周四） | 上一交易日路径：华电辽能 | - | 可能形成B1旧仓 | 进入Td复核，不临场补B2 |",
                    "| Td | 2026-06-26（周五） | 报告日：旧仓进入复核 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |",
                    "| Te | 2026-06-29（周一） | 新目标单独看B1，不用旧仓亏损补仓 | 汇源通信(000586) | B1先到1x/50%；B2确认后补到2x/100% | B1未变强则取消B2；只检查B1 |",
                    "",
                    "# 2026-06-26 持仓策略",
                    "",
                    "正文",
                ]
            ),
            title="测试日报",
            trade_date="2026-06-26",
        )

        body_index = html.index('<div class="markdown-body">')
        timeline_index = html.index("position-timeline-shell", body_index)
        h1_index = html.index("<h1", body_index)
        self.assertLess(timeline_index, h1_index)
        self.assertIn('role="region" aria-label="Ta Te 账户日序"', html)
        self.assertIn('<table class="position-timeline-table">', html)
        self.assertIn('<tr class="timeline-row timeline-row-td">', html)
        self.assertIn('<tr class="timeline-row timeline-row-te">', html)
        self.assertIn('<span class="timeline-lane-code">Td</span>', html)
        self.assertIn('<span class="timeline-lane-code">Te</span>', html)
        self.assertIn('B2不存在直到Te确认', html)
        self.assertIn('B1未变强则取消B2', html)
        self.assertIn(
            'data-el-tooltip="Te 新目标单独看B1，不用旧仓亏损补仓；B1先到1x/50%；B2确认后补到2x/100%；B1未变强则取消B2；只检查B1"',
            html,
        )
        self.assertIn('class="position-timeline-shell is-day-order"', html)
        self.assertIn('tabindex="0" data-el-tooltip=', html)
        self.assertIn('class="timeline-action-badges"', html)
        self.assertIn("setupTimelineTooltips", html)
        self.assertIn("tooltip.textContent = text", html)
        self.assertIn(".el-tooltip-popover", html)
        self.assertIn('<span class="timeline-action-badge is-participate">参与权</span>', html)
        self.assertIn('<span class="timeline-action-badge is-confirm">确认权</span>', html)
        self.assertIn('<span class="timeline-action-badge is-check">检查B1</span>', html)
        self.assertIn('<span class="timeline-action-badge is-empty">空仓</span>', html)
        self.assertEqual(html.count('class="timeline-date-state '), 5)
        self.assertIn('<span class="timeline-date-state is-history">华电辽能</span>', html)
        self.assertIn('<span class="timeline-date-state is-buy">汇源通信</span>', html)
        self.assertNotIn('<span class="timeline-action-badge is-participate">参与权</span></span><span class="timeline-bar-segment is-tb">', html)
        self.assertIn('<span class="timeline-asset-name">汇源通信</span>', html)
        self.assertIn('<span class="timeline-asset-code">000586</span>', html)
        self.assertNotIn('class="timeline-day-cell"', html)
        self.assertNotIn('class="position-day-order-shell"', html)
        self.assertNotIn("day-order-card", html)
        self.assertNotIn(".position-day-order-shell", html)
        self.assertIn('class="position-dual-cluster"', html)
        self.assertIn('aria-label="Ta Te 账户双轨日序"', html)
        self.assertIn('<table class="position-dual-cluster-table">', html)
        self.assertIn('<th>持续核心端</th><th>动态冲击端</th><th>迁移与反证</th>', html)
        self.assertEqual(html.count('class="position-dual-cluster-row '), 5)
        self.assertIn('class="position-day-order-facts"', html)
        self.assertNotIn('<details class="position-day-order-facts" data-position-day-order-facts open>', html)
        self.assertIn('aria-label="账户日序原始六列事实"', html)
        self.assertIn('冲击端B1=1x/50%；B2待确认=另1x/50%', html)
        self.assertRegex(html, r'data-artifact-hash="[0-9a-f]{64}"')
        self.assertIn(".timeline-row-td", html)
        self.assertIn(".timeline-row-te", html)
        self.assertIn(".timeline-action-badge.is-confirm", html)
        self.assertIn(".timeline-action-badge.is-cancel", html)
        self.assertIn(".position-timeline-table", html)
        self.assertIn("min-width: 1824px", html)
        self.assertIn("min-height: 106px", html)
        self.assertIn("height: 72px", html)
        self.assertIn("padding: 12px 0", html)
        self.assertIn("width: auto", html)
        self.assertIn("margin: 0 6px", html)
        self.assertIn("grid-template-areas:", html)
        self.assertIn('"code badges"', html)
        self.assertIn('"text text"', html)
        self.assertIn("grid-area: text", html)
        self.assertIn("-webkit-line-clamp: 3", html)
        self.assertNotIn("width: 332px", html)
        self.assertNotIn("min-width: 960px", html)
        self.assertNotIn(".position-timeline-shell.is-day-order .timeline-row-te .timeline-bar", html)
        self.assertNotIn("justify-self: end", html)
        self.assertNotIn("mermaid.min.js", html)
        self.assertNotIn("bear-gantt-shell", html)
        day_order_html = html[
            timeline_index : html.index("</tbody></table></div></div>", timeline_index)
        ]
        self.assertEqual(["1", "2", "3", "4", "5"], re.findall(r"--bar-start: (\d+);", day_order_html))
        self.assertEqual(["1", "1", "1", "1", "1"], re.findall(r"--bar-span: (\d+);", day_order_html))

    def test_account_dual_cluster_keeps_pending_te_identity_out_of_main_view(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对 |",
                    "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对 |",
                    "| Tc | 2026-07-09（周四） | 前一交易日持仓未输入 | - | B1事实待确认 | 先确认账户事实 |",
                    "| Td | 2026-07-10（周五） | 报告日：外部交易待核实：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察 |",
                    "| Te | 2026-07-13（周一） | 外部交易记录待核实（只核实记录）：伪目标<script>(000001) | 无 | 核实已成交才视为B1；未核实不新增B2 | 0%不参与；只核实记录 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-10",
        )

        dual_view = html.split('<section class="position-dual-cluster"', 1)[1].split("</section>", 1)[0]
        self.assertIn("账户事实未完整；B1/B2均待确认", dual_view)
        self.assertNotIn("伪目标", dual_view)
        self.assertNotIn("伪目标<script>", html)
        self.assertIn("伪目标&lt;script&gt;(000001)", html)
        self.assertIn("overflow-x: auto", html)

    def test_day_order_lane_and_asset_columns_remain_sticky_during_horizontal_scroll(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |",
                    "| Td | 2026-07-13（周一） | 报告日：空仓 | 无 | Te不新增参与，B2取消 | 只观察，不新增参与 |",
                    "| Te | 2026-07-14（周二） | 空仓等待B1资格 | 无 | 没有B1/B2；保持空仓 | 空仓等待下一份日报 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-13",
        )

        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertRegex(
            style,
            r"(?s)\.position-timeline-table\s*\{[^}]*overflow:\s*visible;",
        )
        self.assertRegex(
            style,
            r"(?s)\.timeline-axis-origin,\s*\.timeline-lane\s*\{[^}]*"
            r"width:\s*var\(--timeline-lane-width\);[^}]*"
            r"min-width:\s*var\(--timeline-lane-width\);[^}]*"
            r"max-width:\s*var\(--timeline-lane-width\);",
        )
        self.assertRegex(
            style,
            r"(?s)\.timeline-axis-asset,\s*\.timeline-asset\s*\{[^}]*"
            r"width:\s*var\(--timeline-asset-width\);[^}]*"
            r"min-width:\s*var\(--timeline-asset-width\);[^}]*"
            r"max-width:\s*var\(--timeline-asset-width\);",
        )
        self.assertIn(".timeline-axis-origin,", style)
        self.assertIn(".timeline-axis-asset {\n      position: sticky;", style)
        self.assertIn(".timeline-lane,\n    .timeline-asset {\n      position: sticky;", style)
        self.assertIn('<span class="timeline-date-intent is-empty">空仓执行</span>', html)
        self.assertNotIn('<span class="timeline-date-intent is-buy">参与权</span>', html)

    def test_mermaid_diagram_keeps_horizontal_overflow_inside_its_container(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 测试日报",
                    "",
                    "```mermaid",
                    "flowchart LR",
                    "A[账户事实] --> B[明日账户动作]",
                    "```",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-15",
        )

        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertIn('<div class="fenced-code mermaid" data-mermaid-diagram="true">', html)
        self.assertRegex(
            style,
            r"(?s)\.markdown-body \.mermaid\s*\{[^}]*"
            r"width:\s*100%;[^}]*"
            r"max-width:\s*100%;[^}]*"
            r"min-width:\s*0;[^}]*"
            r"box-sizing:\s*border-box;[^}]*"
            r"overflow-x:\s*auto;",
        )
        self.assertNotRegex(
            style,
            r"(?s)\.markdown-body \.mermaid\s*\{[^}]*min-width:\s*1040px;",
        )
        self.assertEqual(re.findall(r'<script src="([^"]+)"></script>', html), [])
        self.assertIn('data-bear-echarts-loader="inline"', html)
        self.assertIn('data-bear-mermaid-loader="bootcdn"', html)
        self.assertIn("script.async=true", html)
        self.assertIn("https://cdn.bootcdn.net/ajax/libs/echarts/5.6.0/echarts.min.js", html)
        self.assertIn("https://cdn.bootcdn.net/ajax/libs/mermaid/11.12.0/mermaid.min.js", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
    def test_render_current_empty_te_without_b1_as_empty_day_intent(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-10（周五） | 最远复盘日计划待成交确认：长电科技(600584) | 长电科技(600584) | 未确认成交，不视为B1 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-07-13（周一） | 历史复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-07-14（周二） | 前一交易日持仓未输入 | - | B1事实待确认 | 先确认账户事实，不从当前计划反推历史持仓 |",
                    "| Td | 2026-07-15（周三） | 报告日：空仓 | 无 | Te不新增参与，B2取消 | 只观察，不新增参与 |",
                    "| Te | 2026-07-16（周四） | 空仓等待B1资格 | 无 | 没有B1/B2；保持空仓 | 空仓等待下一份日报 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-15",
        )

        self.assertIn('<span class="timeline-date-intent is-empty">空仓执行</span>', html)
        self.assertNotIn('<span class="timeline-date-intent is-buy">参与权</span>', html)

    def test_render_day_order_axis_state_tags_show_each_account_day(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-06（周一） | 最远复盘日：太极实业(600667) | 太极实业(600667) | 历史路径校对 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-07-07（周二） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-07-08（周三） | 上一交易日路径：华天科技(002185) | 华天科技(002185) | 可能形成B1旧仓 | 进入Td复核，不临场补B2 |",
                    "| Td | 2026-07-09（周四） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |",
                    "| Te | 2026-07-10（周五） | 新目标单独看B1，不用旧仓亏损补仓 | 长电科技(600584) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-09",
        )

        self.assertEqual(html.count('class="timeline-date-state '), 5)
        self.assertIn('<span class="timeline-date-state is-history">太极实业</span>', html)
        self.assertEqual(html.count('<span class="timeline-date-state is-history">华天科技</span>'), 1)
        self.assertEqual(html.count('<span class="timeline-date-state is-empty">空仓</span>'), 2)
        self.assertIn('<span class="timeline-date-state is-buy">长电科技</span>', html)

    def test_render_day_order_axis_keeps_unknown_account_fact_unknown(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-07（周二） | 最远复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对 |",
                    "| Tb | 2026-07-08（周三） | 历史复盘日计划待成交确认：华天科技(002185) | 华天科技(002185) | 未确认成交，不视为B1 | 只作路径校对 |",
                    "| Tc | 2026-07-09（周四） | 前一交易日持仓未输入 | - | B1事实待确认 | 先确认账户事实 |",
                    "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与 | 只观察 |",
                    "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1 | 0%不参与；只核实成交记录 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-10",
        )

        self.assertEqual(
            html.count('<span class="timeline-date-state is-unknown">持仓未输入</span>'),
            2,
        )
        self.assertEqual(html.count('<span class="timeline-asset-name">持仓未输入</span>'), 2)

    def test_render_day_order_keeps_unknown_te_badges_pending(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-09（周四） | 最远复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对 |",
                    "| Tb | 2026-07-10（周五） | 历史复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对 |",
                    "| Tc | 2026-07-13（周一） | 前一交易日持仓未输入 | - | B1事实待确认 | 先确认账户事实 |",
                    "| Td | 2026-07-14（周二） | 报告日：持仓未输入 | 无 | Te不新增参与，B2取消 | 只观察，不新增参与 |",
                    "| Te | 2026-07-15（周三） | 先确认是否已有旧仓 | 无 | 先确认是否已有B1；未确认不新增B2 | 旧仓事实不清时不新增参与 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-14",
        )

        te_row = re.search(r'<tr class="timeline-row timeline-row-te">(.*?)</tr>', html, re.S).group(1)
        self.assertIn('<span class="timeline-action-badge is-check">待确认</span>', te_row)
        self.assertNotIn('<span class="timeline-action-badge is-empty">空仓</span>', te_row)
        self.assertIn(
            '<span class="timeline-date-state is-unknown">持仓未输入</span>'
            '<span class="timeline-date-action">执行日</span>'
            '<span class="timeline-date-intent is-check">待确认</span>',
            html,
        )

    def test_render_day_order_keeps_pending_asset_in_td_and_te_execution_target_empty(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |",
                    "| Td | 2026-07-10（周五） | 报告日：外部交易待核实：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |",
                    "| Te | 2026-07-13（周一） | 外部交易记录待核实（只核实记录）：长电科技(600584) | 无 | 核实已成交才视为B1；未核实不新增B2 | 0%不参与；只核实外部交易记录 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-10",
        )

        td_row = re.search(r'<tr class="timeline-row timeline-row-td">(.*?)</tr>', html, re.S).group(1)
        te_row = re.search(r'<tr class="timeline-row timeline-row-te">(.*?)</tr>', html, re.S).group(1)
        self.assertIn('<span class="timeline-asset-name">长电科技</span>', td_row)
        self.assertIn('<span class="timeline-asset-code">600584</span>', td_row)
        self.assertIn('<span class="timeline-asset-empty">无</span>', te_row)
        self.assertNotIn('<span class="timeline-asset-code">600584</span>', te_row)
        self.assertNotIn('<span class="timeline-action-badge is-participate">参与权</span>', te_row)
        self.assertIn('<span class="timeline-action-badge is-check">只核实</span>', te_row)
        self.assertIn('<span class="timeline-date-intent is-empty">空仓执行</span>', html)

    def test_render_day_order_negative_b1_wording_never_shows_participation_badge(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-07-08（周三） | 历史复盘日计划待成交确认：华天科技(002185) | 华天科技(002185) | 未确认成交，不视为B1 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |",
                    "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |",
                    "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-10",
        )

        tb_row = re.search(r'<tr class="timeline-row timeline-row-tb">(.*?)</tr>', html, re.S).group(1)
        tc_row = re.search(r'<tr class="timeline-row timeline-row-tc">(.*?)</tr>', html, re.S).group(1)
        te_row = re.search(r'<tr class="timeline-row timeline-row-te">(.*?)</tr>', html, re.S).group(1)
        self.assertNotIn('is-participate">参与权', tb_row)
        self.assertIn('is-check">待确认', tb_row)
        self.assertNotIn('is-participate">参与权', tc_row)
        self.assertIn('is-empty">空仓', tc_row)
        self.assertNotIn('is-participate">参与权', te_row)
        self.assertIn('is-check">只核实', te_row)

    def test_render_day_order_pending_b1_explanation_never_sets_buy_intent(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对 |",
                    "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对 |",
                    "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |",
                    "| Td | 2026-07-10（周五） | 报告日：前日报计划推定 | 无 | 只定Te预案，不下单 | 报告日确认明日目标 |",
                    "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 无 | 确认已成交才视为B1 | 只核实记录 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-10",
        )

        self.assertIn('<span class="timeline-date-intent is-check">待确认</span>', html)
        self.assertNotIn('<span class="timeline-date-intent is-buy">参与权</span>', html)

    def test_execution_intent_uses_te_text_before_historical_participation_text(self):
        rows = [
            ["Ta最远", "历史对象", "B1参与权；B2确认权"],
            ["Te明日", "无", "确认已成交才视为B1；未确认不新增B2"],
        ]

        self.assertEqual(_position_timeline_execution_tag(rows, 0, 1), "待确认")

    def test_execution_intent_uses_te_text_before_historical_unknown_text(self):
        historical_unknown = ["Ta最远", "历史对象", "持仓未输入；B1事实待确认"]

        self.assertEqual(
            _position_timeline_execution_tag(
                [historical_unknown, ["Te明日", "明日对象", "B1参与权；B2确认权"]],
                0,
                1,
            ),
            "参与权",
        )
        self.assertEqual(
            _position_timeline_execution_tag(
                [historical_unknown, ["Te明日", "无", "明日空仓；没有B1/B2；不买新股、不做T"]],
                0,
                1,
            ),
            "空仓执行",
        )

    def test_render_day_order_b1_not_established_is_empty_execution(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |",
                    "| Td | 2026-07-10（周五） | 报告日：空仓 | 无 | 只定Te预案，不下单 | 写清执行资格和取消条件 |",
                    "| Te | 2026-07-13（周一） | 空仓等待 | 无 | B1不成立；不参与 | 不参与 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-10",
        )

        te_row = re.search(r'<tr class="timeline-row timeline-row-te">(.*?)</tr>', html, re.S).group(1)
        self.assertNotIn('is-participate">参与权', te_row)
        self.assertIn('is-empty">空仓', te_row)
        self.assertIn('<span class="timeline-date-intent is-empty">空仓执行</span>', html)

    def test_render_day_order_confirmed_old_position_without_b2_uses_holding_badge(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-10（周五） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-07-13（周一） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-07-14（周二） | 上一交易日路径待确认 | - | B1事实待确认 | 进入Td复核 |",
                    "| Td | 2026-07-15（周三） | 报告日：旧仓进入复核：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |",
                    "| Te | 2026-07-16（周四） | 只处理旧仓风险 | 长电科技(600584) | 没有B2 | 只处理旧仓风险；旧仓未修复则继续降风险 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-15",
        )

        te_row = re.search(r'<tr class="timeline-row timeline-row-te">(.*?)</tr>', html, re.S).group(1)
        self.assertIn('<span class="timeline-action-badge is-hold">持仓处理</span>', te_row)
        self.assertNotIn('<span class="timeline-action-badge is-empty">空仓</span>', te_row)
        self.assertIn('<span class="timeline-date-intent is-hold">持仓处理</span>', html)

    def test_render_empty_execution_day_intent_when_no_tb_path(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 轨道 | 标的 | 2026-06-26（周五） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |",
                    "|------|------|------|------|------|------|",
                    "| Ta旧仓 | 华电辽能 | Ta+0 旧仓占用 | Ta+1 继续处理旧仓 | Ta+2 默认按昨晚预案尾盘卖出；失去持有资格才提前处理 | 空仓 |",
                    "| Tb明日目标 | 空仓 | 空仓 | 没有Tb+0，空仓 | 没有Tb+1，空仓 | 空仓 |",
                    "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 空仓 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-06-26",
        )

        self.assertIn('<span class="timeline-axis-date is-selected"><span class="timeline-date-main">2026-06-29</span>', html)
        self.assertNotIn('<span class="timeline-axis-date is-selected"><span class="timeline-date-main">2026-06-30</span>', html)
        self.assertIn('<span class="timeline-date-action">执行日</span>', html)
        self.assertIn('<span class="timeline-date-intent is-hold">持仓处理</span>', html)
        self.assertIn('<span class="timeline-bar-segment is-exit is-selected" tabindex="0" data-el-tooltip="Ta+2', html)
        self.assertNotIn('<span class="timeline-bar-segment is-tb is-selected" tabindex="0" data-el-tooltip="Tb+1', html)

    def test_render_market_structure_chart_directive_as_inline_echarts(self):
        chart_payload = {
            "dates": ["2026-07-03", "2026-07-06"],
            "candles": [[4090.0, 4043.0, 4030.0, 4100.0], [4059.0, 4041.0, 4005.0, 4060.0]],
            "volumes": [600000000, 590000000],
            "segments": [
                {
                    "kind": "zhongshu",
                    "startDate": "2026-07-03",
                    "endDate": "2026-07-06",
                    "zg": 4103.93,
                    "zd": 4073.73,
                    "high": 4103.93,
                    "low": 4073.73,
                    "klineCount": 2,
                    "isCurrent": True,
                }
            ],
            "currentSegment": {
                "startDate": "2026-07-03",
                "endDate": "2026-07-06",
                "zg": 4103.93,
                "zd": 4073.73,
            },
            "latestDate": "2026-07-06",
            "latestPrice": 4041.24,
        }
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            companion = root / "chanlun-html" / "2026-07-06_上证指数缠论.html"
            companion.parent.mkdir(parents=True)
            companion.write_text(
                '<script id="chanlun-chart-data" type="application/json">'
                + json.dumps(chart_payload, ensure_ascii=False)
                + "</script>",
                encoding="utf-8",
            )
            output_path = root / "report.html"
            html = render_markdown_report_html(
                "\n".join(
                    [
                        "# 图表日报",
                        "",
                        "**大盘结构图**：",
                        '::market-structure-chart{src="chanlun-html/2026-07-06_上证指数缠论.html" title="2026-07-06 上证指数日线中枢"}',
                    ]
                ),
                title="图表日报",
                trade_date="2026-07-06",
                output_path=output_path,
            )

        self.assertIn('class="market-structure-chart"', html)
        self.assertIn("data-market-structure-chart", html)
        self.assertIn("renderMarketStructureChart", html)
        self.assertIn('"latestDate":"2026-07-06"', html)
        self.assertIn('"volumes":[600000000,590000000]', html)
        self.assertIn("2026-07-06 上证指数日线中枢", html)
        self.assertIn('red: "#C20C0C"', html)
        self.assertIn('green: "#089981"', html)
        self.assertIn('color: "transparent"', html)
        self.assertIn('color: rising ? "transparent" : color', html)
        self.assertIn("borderColor: marketStructureTone.red", html)
        self.assertIn("borderColor: color", html)
        self.assertIn("showTopLabel: Boolean(segment.isCurrent)", html)
        self.assertIn("zoneIntersectsVisibleGrid", html)
        self.assertIn("zoneRight > gridLeft && x < gridRight", html)
        self.assertIn("labelAnchorVisibleInGrid", html)
        self.assertIn("labelIndexVisibleInCurrentZoom", html)
        self.assertIn('{ type: "inside", xAxisIndex: [0, 1], filterMode: "weakFilter" }', html)
        self.assertIn('{ type: "slider", xAxisIndex: [0, 1], filterMode: "weakFilter"', html)
        self.assertIn("item.showLabel && labelIndexVisibleInCurrentZoom(startIndex)", html)
        self.assertIn("encode: { x: [0, 2], y: [1, 3] }", html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("http://127.0.0.1:3040/work-page", html)

    def test_render_ta_te_day_order_b2_cancel_as_cancel_badge(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-03（周五） | 最远复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-07-06（周一） | 历史复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-07-07（周二） | 上一交易日路径：华天科技(002185) | - | 可能形成B1旧仓 | 进入Td复核，不临场补B2 |",
                    "| Td | 2026-07-08（周三） | 报告日：旧仓进入复核 | 无 | Te不新增参与，B2取消 | 只观察，不新增参与 |",
                    "| Te | 2026-07-09（周四） | 只处理旧仓风险 | 无 | 没有B2；只处理旧仓风险 | 旧仓未修复则继续降风险 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-08",
        )

        self.assertIn('<span class="timeline-action-badge is-cancel">取消B2</span>', html)
        self.assertIn('Te不新增参与，B2取消', html)

    def test_render_file_does_not_duplicate_position_timeline_after_reading_map(self):
        timeline = "\n".join(
            [
                "| 轨道 | 标的 | 2026-07-05（周日） | 2026-07-06（周一） | 2026-07-07（周二） | 2026-07-08（周三） |",
                "|------|------|------|------|------|------|",
                "| Ta旧仓 | 太极实业(600667) | 上一份日报目标，进入旧仓/旧路径复核 | Ta+1 继续处理旧仓或取消路径 | Ta+2 优先处理旧仓，空仓时间尽可能接近全天空仓 | 空仓 |",
                "| Tb明日目标 | 空仓 | 空仓 | 没有Tb+0，空仓 | 没有Tb+1，空仓 | 空仓 |",
                "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 下一份日报再复核 |",
            ]
        )
        markdown = "\n".join(
            [
                "# 2026-07-06 A股日报",
                "",
                "## 阅读地图",
                "| 顺序 | 模块 | 用途 |",
                "|---:|---|---|",
                "| 1 | 日报裁决总览 | 先看动作 |",
                "",
                "## 账户日序表",
                timeline,
                "",
                "## 日报裁决总览",
                "正文",
            ]
        )
        with TemporaryDirectory() as tempdir:
            markdown_path = Path(tempdir) / "report.md"
            html_path = Path(tempdir) / "report.html"
            markdown_path.write_text(markdown, encoding="utf-8")

            render_markdown_report_file(
                markdown_path,
                html_path,
                title="测试日报",
                trade_date="2026-07-06",
                prepend_markdown=timeline,
            )
            html = html_path.read_text(encoding="utf-8")

        self.assertEqual(html.count('class="position-timeline-shell"'), 1)
        self.assertEqual(html.count('<tr class="timeline-row timeline-row-ta">'), 1)

    def test_render_empty_execution_day_intent_when_no_old_position_or_tb_path(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 轨道 | 标的 | 2026-06-26（周五） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |",
                    "|------|------|------|------|------|------|",
                    "| Ta旧仓 | 空仓 | Ta+0 空仓 | 空仓 | 空仓 | 空仓 |",
                    "| Tb明日目标 | 空仓 | 空仓 | 没有Tb+0，空仓 | 没有Tb+1，空仓 | 空仓 |",
                    "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 空仓 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-06-26",
        )

        self.assertIn('<span class="timeline-axis-date is-selected"><span class="timeline-date-main">2026-06-29</span>', html)
        self.assertIn('<span class="timeline-date-action">执行日</span>', html)
        self.assertIn('<span class="timeline-date-intent is-empty">空仓执行</span>', html)
        self.assertNotIn('<span class="timeline-bar-segment is-exit is-selected"><span class="timeline-state-code">Ta+2</span>', html)
        self.assertNotIn('<span class="timeline-bar-segment is-tb is-selected"><span class="timeline-state-code">Tb+1</span>', html)

    def test_render_report_day_moves_after_previous_path_source(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 轨道 | 标的 | 2026-06-26（周五） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |",
                    "|------|------|------|------|------|------|",
                    "| Ta旧仓 | 太极实业(600667) | 上一份日报目标，进入旧仓/旧路径复核 | Ta+1 继续处理旧仓或取消路径 | Ta+2 默认按昨晚预案尾盘卖出；失去持有资格才提前处理 | 空仓 |",
                    "| Tb明日目标 | 深科技(000021) | 空仓 | 报告日确认明日目标 | Tb+0 条件买入，不是无条件买入 | Tb+1 只按昨晚预案执行或取消 |",
                    "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 下一份日报再复核 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-06-29",
        )

        self.assertIn('<span class="timeline-date-source">旧路径来源</span>', html)
        self.assertIn('<span class="timeline-axis-date is-report-day"><span class="timeline-date-main">2026-06-29</span>', html)
        self.assertIn('<span class="timeline-axis-date is-selected"><span class="timeline-date-main">2026-06-30</span>', html)
        self.assertNotIn('<span class="timeline-axis-date is-selected"><span class="timeline-date-main">2026-06-29</span>', html)
        self.assertEqual(html.count('<span class="timeline-date-action">执行日</span>'), 1)

    def test_render_builds_bear_outline_and_escapes_text(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 2026-06-05 A股日报",
                    "",
                    "## 市场基底",
                    "<script>alert(1)</script>",
                    "",
                    "| 指标 | 数值 |",
                    "|------|------|",
                    "| Top50成交额占比 | 23.28% |",
                    "| 涨跌比 | 4501 / 900 |",
                    "| 涨跌比 | 1000 / 4301 |",
                    "| ETF两市成交额 | 4406.74亿 |",
                    "",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "|------|------|--------|------|",
                    "| 两市成交额 | 31006.90亿 | +11.57% | 成交额重新放大 |",
                    "| 两市成交额 | 27800.10亿 | -4.20% | 成交额收缩 |",
                    "",
                    "| 指数 | 收盘 | 涨跌幅 | 解读 |",
                    "|------|------|--------|------|",
                    "| 上证指数 | 3385.36 | +0.45% | 小幅修复 |",
                    "| 中证500 | 5830.25 | +0.82% | 中盘修复 |",
                    "| 中证1000 | 6210.12 | -1.25% | 小票承压 |",
                    "",
                    "| 日期 | ETF两市成交额 | 较前日 | 有成交ETF数 |",
                    "|------|----------------|--------|------------|",
                    "| 2026-06-05 | 4406.74亿 | +1.65% | 1544 |",
                    "| 2026-06-02 | 5198.92亿 | +3.18% | 1541 |",
                    "| 2026-05-15 | 5552.59亿 | +14.06% | 1518 |",
                    "",
                    "| 日期 | 当日差值 | 全A占比 |",
                    "|------|----------|---------|",
                    "| 2026-06-05 | +2.30pct | 1.96% |",
                    "| 2026-06-04 | -2.40pct | 5.20% |",
                    "",
                    "```sql",
                    "select * from daily_report_fact_fields where value > 20;",
                    "```",
                    "",
                    "---",
                    "",
                    "### 今日判断",
                    "> 只观察，不新增参与",
                ]
            ),
            title="测试日报",
            trade_date="2026-06-05",
            source_label="Markdown日报",
        )

        self.assertIn("当前日报", html)
        self.assertIn("outline-sticky", html)
        self.assertIn('id="outline-sidebar"', html)
        self.assertIn('data-outline-toggle', html)
        self.assertIn('aria-controls="outline-sticky"', html)
        self.assertIn('aria-expanded="true"', html)
        self.assertIn('aria-label="收起侧边栏"', html)
        self.assertIn('title="收起侧边栏"', html)
        self.assertIn("--outline-toggle-rail-width: 64px", html)
        self.assertIn("--outline-toggle-size: 44px", html)
        self.assertIn(".bear-shell.is-outline-collapsed .outline-sidebar", html)
        self.assertIn(".bear-shell.is-outline-collapsed .editor-pane", html)
        self.assertIn("@media (min-width: 761px)", html)
        self.assertIn(".bear-shell.is-outline-collapsed .reader-document", html)
        self.assertIn(
            "max-width: calc(var(--editor-width) + var(--outline-rail-width) - var(--outline-toggle-rail-width))",
            html,
        )
        self.assertIn('const setOutlineCollapsed = (collapsed) =>', html)
        self.assertIn('shell.classList.toggle("is-outline-collapsed", collapsed)', html)
        self.assertIn('window.dispatchEvent(new Event("resize"))', html)
        self.assertIn('outlineToggle.addEventListener("click"', html)
        self.assertIn('const label = collapsed ? "展开侧边栏" : "收起侧边栏"', html)
        self.assertIn("--outline-rail-width: calc(var(--outline-width) + 36px)", html)
        self.assertIn("position: fixed", html)
        self.assertIn("width: var(--outline-rail-width)", html)
        self.assertIn("height: 100vh", html)
        self.assertIn("margin-left: var(--outline-rail-width)", html)
        self.assertIn("margin-left: 0", html)
        self.assertNotIn("grid-template-columns: minmax(224px, var(--outline-width))", html)
        self.assertIn("is-active", html)
        self.assertIn('class="level-1 is-active" aria-current="true"', html)
        self.assertIn("scrollIntoView", html)
        self.assertIn('target.scrollIntoView({ block: "start", inline: "nearest", behavior: "auto" })', html)
        self.assertIn("requestAnimationFrame", html)
        self.assertIn("event.preventDefault()", html)
        self.assertIn("replaceState", html)
        self.assertIn('const navigationLinks = Array.from(document.querySelectorAll("a[data-outline-anchor]"))', html)
        self.assertIn("for (const link of navigationLinks)", html)
        self.assertIn('if (window.location.protocol === "file:")', html)
        self.assertIn("updateLocationAnchor(id)", html)
        self.assertIn("forcedActiveId", html)
        self.assertIn("releaseForcedActive", html)
        self.assertIn("linkByAnchor", html)
        self.assertIn("headingOffsets", html)
        self.assertIn("refreshHeadingOffsets", html)
        self.assertIn("scrollActiveIntoOutline", html)
        self.assertIn("outline.scrollTo", html)
        self.assertNotIn('behavior: "smooth"', html)
        self.assertNotIn("scroll-behavior: smooth", html)
        self.assertNotIn("clickScrollLockUntil", html)
        self.assertNotIn("clickScrollTargetId", html)
        self.assertNotIn("isNearScrollTarget", html)
        self.assertNotIn("window.setTimeout", html)
        self.assertNotIn("activeLink.scrollIntoView", html)
        self.assertIn(".outline-nav a.is-active::before", html)
        self.assertIn("background: linear-gradient(145deg, rgba(231, 57, 34, 0.92), rgba(255, 138, 31, 0.82))", html)
        self.assertIn("transform: translateY(-50%)", html)
        self.assertIn("hashAnchor", html)
        self.assertNotIn('link.style.setProperty("color"', html)
        self.assertNotIn('link.style.setProperty("background-color"', html)
        self.assertNotIn('link.style.setProperty("border-left-color"', html)
        self.assertIn('window.addEventListener("wheel"', html)
        self.assertIn('window.addEventListener("mousedown"', html)
        self.assertIn('window.addEventListener("hashchange"', html)
        self.assertIn('window.addEventListener("bear:echarts-ready", renderCharts, { once: true })', html)
        self.assertIn("const renderCharts = () =>", html)
        self.assertIn('const outlineMarker = "$" + "outline_nav"', html)
        self.assertNotIn('includes("<nav class=', html)
        self.assertIn('href="#市场基底"', html)
        self.assertIn('data-outline-anchor="市场基底"', html)
        self.assertIn('class="level-3" href="#今日判断" data-outline-anchor="今日判断"', html)
        self.assertIn("--editor-width: 1120px", html)
        self.assertIn("--reader-bg: #fff9ef", html)
        self.assertIn("--reader-text: #2d1712", html)
        self.assertIn("--reader-muted: #6c4537", html)
        self.assertIn("--accent: #e73922", html)
        self.assertIn("--accent-orange: #ff8a1f", html)
        self.assertIn("--accent-soft-text: #7d231b", html)
        self.assertIn("--signal-green: #176e54", html)
        self.assertIn("background: var(--reader-bg)", html)
        self.assertNotIn("linear-gradient(145deg, #fffaf2 0%, #ffe9d0 48%, #ffd0bd 100%)", html)
        self.assertNotIn("radial-gradient(circle at 18% 0%", html)
        self.assertIn("contain: paint", html)
        self.assertNotIn("backdrop-filter", html)
        self.assertNotIn("body::before", html)
        self.assertNotIn("bear-shell::before", html)
        self.assertNotIn("mix-blend-mode", html)
        self.assertNotIn("animation: drift-dots", html)
        self.assertNotIn("@keyframes drift-dots", html)
        self.assertIn('text: cssValue("--reader-text", "#2d1712")', html)
        self.assertIn('muted: cssValue("--reader-muted", "#6c4537")', html)
        self.assertIn('line: cssValue("--reader-line", "rgba(108, 69, 55, 0.14)")', html)
        self.assertIn('red: cssValue("--accent-red", "#e73922")', html)
        self.assertIn('color: ["rgba(231,57,34,0.58)"]', html)
        self.assertIn(
            "color: hasChinext ? [chartTone.red, chartTone.iceBlue] : [chartTone.red]",
            html,
        )
        self.assertIn("color: [chartTone.fluorescentPurple]", html)
        self.assertIn("font-size: 15px", html)
        self.assertIn("pre.fenced-code", html)
        self.assertIn('<pre class="fenced-code"><code class="fenced-code-content" lang="sql">', html)
        self.assertIn("select * from daily_report_fact_fields where value &gt; 20;", html)
        self.assertNotIn("mermaid.min.js", html)
        self.assertNotIn("mermaid.run({querySelector:'.markdown-body .mermaid'})", html)
        self.assertIn("<hr>", html)
        self.assertNotIn('content: "📝"', html)
        self.assertIn("box-decoration-break: clone", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertGreaterEqual(html.count('class="signal-marker signal-hot"'), 4)
        self.assertGreaterEqual(html.count('class="signal-marker signal-cold"'), 3)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-hot">+11.57%</span></td>', html)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-cold">-4.20%</span></td>', html)
        self.assertIn("<td>31006.90亿</td>", html)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-hot">+0.45%</span></td>', html)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-hot">+0.82%</span></td>', html)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-cold">-1.25%</span></td>', html)
        self.assertIn("<td>3385.36</td>", html)
        self.assertIn("<td>5830.25</td>", html)
        self.assertEqual(html.count('<td class="has-signal"><span class="signal-marker signal-cold">4406.74亿</span></td>'), 2)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-hot">5552.59亿</span></td>', html)
        self.assertIn("<td>5198.92亿</td>", html)
        self.assertNotIn('td class="signal-hot"', html)
        self.assertNotIn("snapshots/replay", html)
        self.assertNotIn(".json", html)

    def test_render_distinguishes_extreme_top50_share_above_25(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 1. 指数与市场底色补充",
                    "",
                    "补充说明。",
                    "",
                    "### 1. 指数与市场底色",
                    "> 近25个交易日Top50成交额占比趋势。",
                    "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |",
                    "|------|-----------|------|--------|-------------|------------|",
                    "| 2026-06-10 | 25.01% | 极致 | +0.01pct | 7503.00亿 | 30000.00亿 |",
                    "| 2026-06-09 | 25.00% | 资金活跃期 | +4.99pct | 7500.00亿 | 30000.00亿 |",
                    "| 2026-06-08 | 20.01% | 资金活跃期 | +2.02pct | 6003.00亿 | 30000.00亿 |",
                    "| 2026-06-07 | 20.00% | 震荡 | +2.00pct | 6000.00亿 | 30000.00亿 |",
                    "| 2026-06-06 | 18.00% | 震荡 | +0.01pct | 5400.00亿 | 30000.00亿 |",
                    "| 2026-06-05 | 17.99% | 冰点 | 待累计 | 5397.00亿 | 30000.00亿 |",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-10",
        )

        self.assertIn(
            '<td class="has-signal"><span class="signal-marker signal-extreme">25.01%</span></td>',
            html,
        )
        self.assertIn(
            '<td class="has-signal"><span class="signal-marker signal-hot">25.00%</span></td>',
            html,
        )
        self.assertIn(
            '<td class="has-signal"><span class="signal-marker signal-cold">17.99%</span></td>',
            html,
        )
        self.assertIn("<td>20.00%</td>", html)
        self.assertIn("<td>18.00%</td>", html)
        self.assertNotIn('signal-hot">20.00%</span>', html)
        self.assertNotIn('signal-cold">18.00%</span>', html)
        self.assertIn("--signal-extreme: #F92722", html)
        self.assertIn("--signal-extreme-text: #FFFFFF", html)
        self.assertIn(".signal-marker.signal-extreme", html)
        self.assertIn("text-shadow: 0 1px 1px rgba(94, 0, 0, 0.42)", html)
        self.assertIn('extremeRed: cssValue("--signal-extreme", "#F92722")', html)
        self.assertIn('extremeText: cssValue("--signal-extreme-text", "#FFFFFF")', html)
        self.assertIn('name: ">25%极致"', html)
        self.assertIn("backgroundColor: chartTone.extremeRed", html)
        self.assertIn("color: chartTone.extremeText", html)
        self.assertIn("max: (value) => Math.max(26, Math.ceil(value.max) + 1)", html)

    def test_template_preview_includes_extreme_top50_demo(self):
        html = (ROOT / "scripts" / "templates" / "daily_report_markdown_reader.html").read_text(encoding="utf-8")

        self.assertIn('$outline_nav', html)
        self.assertIn('const outlineMarker = "$" + "outline_nav";', html)
        self.assertIn('document.body.textContent.includes(outlineMarker)', html)
        self.assertIn('<span class="signal-marker signal-extreme">猩红极致</span>', html)
        self.assertIn(
            '<span class="signal-marker signal-extreme">25.16%</span></td><td>超过25%，极致</td>',
            html,
        )
        self.assertIn(
            '<span class="signal-marker signal-hot">23.28%</span></td><td>超过20%，资金活跃</td>',
            html,
        )
        self.assertIn(
            '<span class="signal-marker signal-cold">1.96%</span></td><td>低于2%，偏冷</td>',
            html,
        )

    def test_generated_market_overview_keeps_extreme_wording_and_bear_color_aligned(self):
        contract = build_market_trend_sections_contract(
            data={
                "total_turnover": 30000.0,
                "turnover_rank": [{"turnover": 150.06} for _ in range(50)],
                "zt_pool": [],
                "dt_pool": [],
                "market_stats": {"up_count": 2400, "down_count": 2400},
            },
            target_date="2026-06-10",
        )
        html = render_markdown_report_html(
            "\n".join(contract["lines"]),
            title="图表日报",
            trade_date="2026-06-10",
        )

        self.assertIn(
            '<td class="has-signal"><span class="signal-marker signal-extreme">25.01%</span></td>',
            html,
        )
        self.assertIn("<td>极致</td>", html)
        self.assertIn("<td>Top50成交额占比超过25%，头部成交集中度进入极致区。</td>", html)
        self.assertNotIn("Top50成交额占比超过20%，雨量变大，资金处于活跃期。", html)

    def test_render_marks_stock_name_code_references_as_inline_code(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 个股引用",
                    "",
                    "正文里：大有能源(600403)要像代码一样醒目，普通说明(不是代码)不变。",
                    "",
                    "- 保留：宇环数控(002903)",
                    "- 已有反引号：`华电辽能(600396)`",
                    "",
                    "| 标的 | 说明 |",
                    "|------|------|",
                    "| 天娱数科(002354) | 观察 |",
                    "",
                    "| 股票 | 代码 |",
                    "|------|------|",
                    "| 兆易创新 | 603986 |",
                    "",
                    "关系：未证明比兆易创新(603986)更值得参与。",
                ]
            ),
            title="个股引用",
            trade_date="2026-06-05",
        )

        self.assertIn('<code class="stock-ref">大有能源(600403)</code>', html)
        self.assertIn('<code class="stock-ref">宇环数控(002903)</code>', html)
        self.assertIn('<code class="stock-ref">天娱数科(002354)</code>', html)
        self.assertIn('<td><code class="stock-ref">兆易创新</code></td>', html)
        self.assertIn('<td><code class="stock-ref">603986</code></td>', html)
        self.assertIn('未证明比<code class="stock-ref">兆易创新(603986)</code>更值得参与', html)
        self.assertNotIn('<code class="stock-ref">未证明比兆易创新(603986)</code>', html)
        self.assertIn("<code>华电辽能(600396)</code>", html)
        self.assertNotIn('<code class="stock-ref">华电辽能(600396)</code>', html)
        self.assertIn("普通说明(不是代码)不变", html)

    def test_render_wraps_front_position_conclusion_cells(self):
        position_text = (
            "已决定满仓条件执行；最大可到100%，先B1再B2；"
            "B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；"
            "盘中不满足取消，回到0%不参与"
        )
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 2026-07-09 A股日报",
                    "",
                    "## 日报裁决总览",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    f"| 仓位姿态 | {position_text} |",
                    "| 最终对象 | 明日执行对象：长电科技(600584) |",
                    "",
                    "## 明日执行结论",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    f"| 明日新仓 | {position_text} |",
                    "| 明日执行对象 | 长电科技(600584) |",
                    "",
                    "## 明日账户建议",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    f"| 明日仓位 | {position_text} |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-09",
        )

        wrapped = (
            "已决定满仓条件执行<br>最大可到100%，先B1再B2<br>"
            "B1先买参与权，B2只买确认权<br>B1未变强不补B2，走弱先取消B2并检查B1<br>"
            "盘中不满足取消，回到0%不参与"
        )
        self.assertEqual(html.count(wrapped), 2)
        self.assertIn(f"<td>{position_text}</td>", html)

    def test_bear_html_preserves_the_five_account_action_rows(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 2026-07-14 A股日报",
                    "",
                    "## 明日账户建议",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    "| 明日新仓 | 0%不参与 |",
                    "| 旧仓事实 | 已确认持有长电科技(600584) |",
                    "| 旧仓判断 | 待10:10复核 |",
                    "| 旧仓动作 | 09:50-10:10只复核一次；三层承接成立才保留到14:30-14:55 |",
                    "| 收盘目标仓位 | 待10:10复核后确定 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-14",
        )

        for label in ("明日新仓", "旧仓事实", "旧仓判断", "旧仓动作", "收盘目标仓位"):
            self.assertIn(f"<td>{label}</td>", html)
        self.assertIn("0%不参与", html)
        self.assertIn("已确认持有长电科技(600584)", html)
        self.assertIn("待10:10复核", html)
        self.assertIn("09:50-10:10只复核一次；三层承接成立才保留到14:30-14:55", html)
        self.assertIn("待10:10复核后确定", html)

    def test_render_marks_action_and_evidence_sections_for_bear_reader(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 2026-07-03 A股日报",
                    "",
                    "## 阅读地图",
                    "| 顺序 | 模块 |",
                    "|---:|---|",
                    "| 1 | 明日执行结论 |",
                    "",
                    "## 日报裁决总览",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    "| 最终对象 | 明日执行对象：太极实业(600667) |",
                    "",
                    "## 明日执行结论",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    "| 明日执行对象 | 太极实业(600667) |",
                    "",
                    "## 满仓条件执行条件",
                    "| 触发类型 | 必须满足 |",
                    "|----------|----------|",
                    "| 低开承接型 | 回踩确认 |",
                    "",
                    "## 不执行条件",
                    "- 市场继续走弱",
                    "",
                    "## 知识模块",
                    "- LLM Wiki版本：2026-07-17",
                    "",
                    "## 经验库命中",
                    "| 命中经验 | 知识ID |",
                    "|---|---|",
                    "| 指数强但赚钱效应弱 | `market.low-frequency-focus` |",
                    "",
                    "## 研究与执行分层（研究证据）",
                    "| 对象 | 企业前提 | 估值位置 | 当前价格证据 | 仓位身份 | 冲突处理 | 下一次 T0 复核 |",
                    "|---|---|---|---|---|---|---|",
                    "| 太极实业(600667) | 事实不足 | 事实不足 | 只观察承接 | 无仓位 | 不新增动作 | 下一份T0再核对 |",
                    "",
                    "## 股指期货持仓结构（研究证据）",
                    "| 对象 | 净空变化 |",
                    "|---|---:|",
                    "| 中信期货代客会员汇总 | 3,130 |",
                    "",
                    "## 市场语言翻译（研究证据）",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    "| 当前阶段 | 向下压力扩散 |",
                    "",
                    "## 板块资金扩散淘汰赛",
                    "| 层级 | 输入 |",
                    "|---|---:|",
                    "| 唯一明日动作 | 1 |",
                ]
            ),
            title="测试日报",
            trade_date="2026-07-03",
        )

        self.assertIn('<h2 class="bear-section-map" id="阅读地图">阅读地图</h2>', html)
        self.assertIn('<h2 class="bear-section-action" id="明日执行结论">明日执行结论</h2>', html)
        self.assertIn('<h2 class="bear-section-action" id="满仓条件执行条件">满仓条件执行条件</h2>', html)
        self.assertIn('<h2 class="bear-section-action" id="不执行条件">不执行条件</h2>', html)
        self.assertIn('<h2 class="bear-section-evidence" id="知识模块">知识模块</h2>', html)
        self.assertIn('<h2 class="bear-section-evidence" id="经验库命中">经验库命中</h2>', html)
        self.assertIn('<h2 class="bear-section-evidence" id="研究与执行分层研究证据">研究与执行分层（研究证据）</h2>', html)
        self.assertIn('<h2 class="bear-section-evidence" id="股指期货持仓结构研究证据">股指期货持仓结构（研究证据）</h2>', html)
        self.assertIn('<h2 class="bear-section-evidence" id="市场语言翻译研究证据">市场语言翻译（研究证据）</h2>', html)
        self.assertIn('<h2 class="bear-section-evidence" id="板块资金扩散淘汰赛">板块资金扩散淘汰赛</h2>', html)
        self.assertLess(html.index('id="明日执行结论"'), html.index('id="市场语言翻译研究证据"'))
        self.assertLess(html.index('id="明日执行结论"'), html.index('id="知识模块"'))
        self.assertLess(html.index('id="明日执行结论"'), html.index('id="经验库命中"'))
        self.assertLess(html.index('id="明日执行结论"'), html.index('id="研究与执行分层研究证据"'))
        self.assertLess(html.index('id="研究与执行分层研究证据"'), html.index('id="市场语言翻译研究证据"'))
        self.assertLess(html.index('id="股指期货持仓结构研究证据"'), html.index('id="市场语言翻译研究证据"'))
        self.assertLess(html.index('id="明日执行结论"'), html.index('id="板块资金扩散淘汰赛"'))
        self.assertIn(".markdown-body h2.bear-section-action", html)
        self.assertIn(".markdown-body h2.bear-section-evidence", html)
        research_start = html.index('id="研究与执行分层研究证据"')
        research_end = html.index('id="市场语言翻译研究证据"')
        research_html = html[research_start:research_end]
        self.assertIn('<div class="reader-table"><table>', research_html)
        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertRegex(
            style,
            r"(?s)\.reader-table\s*\{[^}]*"
            r"display:\s*block;[^}]*"
            r"overflow-x:\s*auto;[^}]*"
            r"contain:\s*paint;[^}]*"
            r"-webkit-overflow-scrolling:\s*touch;",
        )

    def test_render_candidate_lifecycle_groups_full_evidence_and_localizes_sources(self):
        rows = [
            (
                "板块锚(688825)",
                "sector_derived_candidates、sector_capital_carrier_strategy、hot_rank、integrated_hot、limit_up、turnover",
                "热榜只作过程证据",
                "板块锚",
                "可作为主对象",
                "只作过程回放，不新增参与",
                "过程候选",
            )
        ]
        for index in range(3):
            rows.append(
                (
                    f"高确信{index}(0000{index + 1:02d})",
                    "extreme_conviction_list",
                    "旧强势记忆只作过程证据",
                    "过程候选",
                    "降级观察",
                    "本板块锚未识别",
                    "降级观察",
                )
            )
        for index in range(4):
            rows.append(
                (
                    f"跨线{index}(3000{index + 1:02d})",
                    "crossline_observation_stocks",
                    "未证明来自板块发酵和市场选择",
                    "过程候选",
                    "降级观察",
                    "只作过程回放，不新增参与",
                    "降级观察",
                )
            )
        for index in range(37):
            action = "风险复核样本" if index in {0, 36} else "降级观察"
            comparison = "降级观察，等待后续行情重新确认" if index in {0, 36} else "只作过程回放，不新增参与"
            reason = 'A & B "quoted"' if index == 1 else "未证明来自板块发酵和市场选择"
            rows.append(
                (
                    f"通用{index:02d}(600{index:03d})",
                    "candidates",
                    reason,
                    "过程候选",
                    "降级观察",
                    comparison,
                    action,
                )
            )
        markdown_rows = ["| " + " | ".join(row) + " |" for row in rows]
        html = render_markdown_report_html(
            "\n".join(
                [
                    "### 候选生命周期证据",
                    "| 股票 | 首次来源 | 进入理由 | 板块角色 | 反推结论 | 对照结果 | 最终动作 |",
                    "|---|---|---|---|---|---|---|",
                    *markdown_rows,
                ]
            ),
            title="候选生命周期测试",
        )

        self.assertIn(
            'class="candidate-lifecycle" data-candidate-count="45" data-focus-count="10" data-collapsed-count="35"',
            html,
        )
        self.assertIn("<span>候选总数</span><strong>45只</strong>", html)
        self.assertIn("<span>重点展开</span><strong>10只</strong>", html)
        self.assertIn("<span>其余收起</span><strong>35只</strong>", html)
        self.assertIn("<span>通用过程池</span><strong>37只</strong>", html)
        self.assertIn("<th>股票</th><th>发现路径</th><th>当前结论</th><th>关键理由</th>", html)
        self.assertNotIn("<th>入口处理</th>", html)
        self.assertNotIn("<th>首次来源</th>", html)
        self.assertIn("板块推导候选、板块资金载体、热榜、综合热度、涨停/连板证据、成交额排行", html)
        self.assertNotIn("sector_derived_candidates", html)
        self.assertNotIn("extreme_conviction_list", html)
        self.assertNotIn("crossline_observation_stocks", html)
        self.assertNotIn(">candidates<", html)
        self.assertIn('<details class="candidate-lifecycle-rest">', html)
        self.assertNotIn('<details class="candidate-lifecycle-rest" open>', html)
        self.assertIn(
            ".candidate-lifecycle-rest:not([open]) > .candidate-lifecycle-table",
            html,
        )
        self.assertNotIn('A & B "quoted"', html)
        self.assertIn("A &amp; B &quot;quoted&quot;", html)
        for row in rows:
            self.assertEqual(html.count(row[0]), 1, row[0])

    def test_render_candidate_lifecycle_handles_empty_and_focus_only_states(self):
        table_header = "\n".join(
            [
                "### 候选生命周期证据",
                "| 股票 | 发现路径 | 入口处理 | 板块角色 | 反推结论 | 对照结果 | 最终动作 |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        empty_html = render_markdown_report_html(table_header, title="空候选测试")

        self.assertIn('class="candidate-lifecycle" data-candidate-count="0"', empty_html)
        self.assertIn("暂无候选生命周期证据", empty_html)
        self.assertNotIn('<details class="candidate-lifecycle-rest">', empty_html)

        focus_html = render_markdown_report_html(
            table_header
            + "\n| 核心候选(688001) | sector_derived_candidates | 板块路径已证明 | 板块锚 | 可作为主对象 | 风险可控 | 过程候选 |",
            title="重点候选测试",
        )

        self.assertIn('data-candidate-count="1" data-focus-count="1" data-collapsed-count="0"', focus_html)
        self.assertIn("核心候选(688001)", focus_html)
        self.assertNotIn('<details class="candidate-lifecycle-rest">', focus_html)

        collapsed_html = render_markdown_report_html(
            table_header
            + "\n| 否定身份样本(600001) | candidates | 普通过程证据 | 非板块锚 | 不能作为最终执行对象 | 降级观察 | 降级观察 |",
            title="仅收起候选测试",
        )

        self.assertIn('data-candidate-count="1" data-focus-count="0" data-collapsed-count="1"', collapsed_html)
        self.assertNotIn('<div class="candidate-lifecycle-focus">', collapsed_html)
        self.assertIn('<details class="candidate-lifecycle-rest">', collapsed_html)

    def test_render_cycle_calendar_keeps_sector_color_markup_safe(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 周期日历",
                    "",
                    "### 1. 周期日历主视图",
                    "| 周次 | 一 | 二 |",
                    "|------|------|------|",
                    (
                        '| 06-01当周 | <span class="cycle-sector-dot" style="color:#D84E42; border-color:#D84E42">●</span><br />'
                        '<span class="cycle-sector-label" style="color:#D84E42; border-color:#D84E42">[电力]</span><br>🔥 爆发 | '
                        "<script>alert(1)</script> |"
                    ),
                ]
            ),
            title="周期日历",
            trade_date="2026-06-05",
        )

        self.assertIn('<div class="cycle-sector-legend" aria-label="板块颜色图例">', html)
        self.assertIn(
            '<span class="cycle-sector-legend-item" style="--cycle-sector-color:#DD4C4F">'
            '<span class="cycle-sector-legend-dot" aria-hidden="true"></span><span>电力</span></span>',
            html,
        )
        self.assertIn('<span class="cycle-sector-label" style="--cycle-sector-color:#DD4C4F">[电力]</span> 🔥 爆发', html)
        self.assertNotIn('class="cycle-sector-dot"', html)
        self.assertNotIn("<br>🔥 爆发", html)
        self.assertIn(".cycle-sector-label", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_render_cycle_calendar_markup_only_applies_to_cycle_calendar_section(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 普通表格",
                    "",
                    "### 普通说明",
                    "| 项目 | 内容 |",
                    "|------|------|",
                    (
                        '| 样本 | <span class="cycle-sector-dot" style="color:#D84E42">●</span><br>'
                        '<span class="cycle-sector-label" style="color:#D84E42;border-color:#D84E42">[电力]</span> |'
                    ),
                ]
            ),
            title="普通表格",
            trade_date="2026-06-05",
        )

        self.assertNotIn('<div class="cycle-sector-legend"', html)
        self.assertNotIn('<td><span class="cycle-sector-label" style="--cycle-sector-color:#DD4C4F">[电力]</span></td>', html)
        self.assertIn("&lt;span class=&quot;cycle-sector-label&quot;", html)

    def test_render_cycle_sector_markup_applies_to_interpretation_and_turnover_surfaces(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 周期色联动",
                    "",
                    "### 2. 周期解读",
                    "| 周期 | 攻击线 |",
                    "|------|--------|",
                    '| 当前周期 | <span class="cycle-sector-label" style="color:#2F7FB8;border-color:#2F7FB8">[半导体]</span> |',
                    "",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#DD4C4F;border-color:#DD4C4F">[电力]</span>',
                    "| 日期 | 板块成交额 |",
                    "|------|------------|",
                    "| 2026-06-02 | 1000.00亿 |",
                    "",
                    "#### 小周期成交额与主线切换判断",
                    "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 |",
                    "|------|------------|------------|------------|------|----------|----------|",
                    '| 2026-06-02 | <span class="cycle-sector-label" style="color:#2F7FB8;border-color:#2F7FB8">[半导体]</span> | 4050.00亿 | 30000.00亿 | 13.5% | +1.5pct | 小周期试攻，未确认切换 |',
                ]
            ),
            title="周期色联动",
            trade_date="2026-06-05",
        )

        self.assertIn('<span class="cycle-sector-label" style="--cycle-sector-color:#2F7FB8">[半导体]</span>', html)
        self.assertIn('<span class="cycle-sector-label" style="--cycle-sector-color:#DD4C4F">[电力]</span>', html)
        self.assertIn("<td>4050.00亿</td>", html)
        self.assertIn("<td>30000.00亿</td>", html)
        self.assertIn("<td>13.5%</td>", html)
        self.assertNotIn("&lt;span class=&quot;cycle-sector-label&quot;", html)

    def test_render_adds_sector_cycle_swimlane_and_turnover_top30(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
                    "> 目标日热点板块占比。",
                    "",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span>',
                    "**T-S01**",
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-08-05 | 7685.41亿 | 26667.33亿 | 28.8% | +2.1pct | 同板块连续 | 国产芯片替代A&B资金容量扩张 |",
                    "| 2026-08-04 | 7000.00亿 | 25000.00亿 | 28.0% | -0.8pct | 同板块连续 | 承接可用 |",
                    "| 2026-08-03 | 数据暂缺 | 数据暂缺 | 待累计 | 待累计 | 待累计 | 成交占比待累计 |",
                    "| 2026-07-29 | 6600.00亿 | 23000.00亿 | 28.7% | 待累计 | 待累计 | 独立观察点 |",
                    "| 2026-07-27 | 数据暂缺 | 数据暂缺 | 待累计 | 待累计 | 待累计 | 方向存在但占比暂缺 |",
                    "",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#4F8A87;border-color:#4F8A87">[光通信/CPO]</span>',
                    "**T-S02**",
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-08-03 | 5524.59亿 | 20110.59亿 | 27.5% | 待累计 | 待累计 | 当日方向 |",
                    "",
                    "#### 小周期成交额与主线切换判断",
                    "**T-S03**",
                    "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
                    "|------|------------|------------|------------|------|----------|----------|------|",
                    '| 2026-08-05 | <span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span> | 7685.41亿 | 26667.33亿 | 28.8% | +2.1pct | 大周期延续 | 可用 |',
                    '| 2026-08-04 | <span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span> | 7000.00亿 | 25000.00亿 | 28.0% | -0.8pct | 大周期延续 | 可用 |',
                    '| 2026-08-03 | <span class="cycle-sector-label" style="color:#4F8A87;border-color:#4F8A87">[光通信/CPO]</span> | 5524.59亿 | 20110.59亿 | 27.5% | 待累计 | 大周期延续 | 可用 |',
                    '| 2026-07-31 | <span class="cycle-sector-label" style="color:#8F945C;border-color:#8F945C">[软件开发]</span> | 1303.29亿 | 25598.98亿 | 5.1% | 待累计 | 大周期延续 | 可用 |',
                    '| 2026-07-29 | <span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span> | 6600.00亿 | 23000.00亿 | 28.7% | 待累计 | 大周期延续 | 可用 |',
                    '| 2026-07-28 | <span class="cycle-sector-label" style="color:#5C7F94;border-color:#5C7F94">[白酒]</span> | 126.00亿 | 20391.39亿 | 0.6% | 待累计 | 大周期延续 | 可用 |',
                    '| 2026-07-27 | <span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span> | 数据暂缺 | 数据暂缺 | 待累计 | 待累计 | 大周期延续 | 暂缺 |',
                    "",
                    "### 附录：五、成交核心结果",
                    "**先看什么**: 只看真放量的成交核心。",
                    "| 排名 | 股票 | 代码 | 成交额 | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 隔日判断 | 蜡烛图形态 |",
                    "|------|------|------|--------|----------|--------|--------|--------|--------|--------|----------|------------|",
                    "| 1 | 中天科技 | 600522 | 249.78亿 | 通信设备 | +9.99% | 54.48 | 48.56 | 50.53 | 54.48 | 观望 | 光头大阳柱涨停(4分) |",
                    "| 2 | 春秋电子 | 603890 | 88.10亿 | AI PC | -9.57% | 28.00 | 25.31 | 27.50 | 25.43 | 谨慎 | 下跌趋势(0分) |",
                ]
            ),
            title="图表日报",
            trade_date="2026-08-05",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="sector_cycle_swimlane"', html)
        self.assertIn("data-sector-cycle-ascii", html)
        self.assertIn("data-sector-cycle-raw-records", html)
        self.assertIn("data-sector-cycle-scroll-controls", html)
        self.assertIn("data-sector-cycle-scroll-range", html)
        self.assertIn('aria-label="时间轴向左滚动"', html)
        self.assertIn('aria-label="时间轴向右滚动"', html)
        self.assertNotIn('data-sector-cycle-raw-records open', html)
        self.assertIn('data-bear-chart="turnover_sector_share"', html)
        self.assertIn('data-bear-chart="turnover_top30"', html)
        self.assertIn("renderSectorCycleSwimlaneChart", html)
        self.assertIn("setupSectorCycleScrollControls", html)
        self.assertIn('card?.classList.contains("is-chart-ready") ? track : ascii', html)
        self.assertIn("Math.ceil(target.scrollWidth - target.clientWidth)", html)
        self.assertIn("if (target !== lastActiveScrollTarget)", html)
        self.assertIn("pendingScrollRatio = lastScrollRatio", html)
        self.assertIn("lastScrollRatio = scrollRatio(target)", html)
        self.assertIn("target.scrollLeft = Math.round(maximum * pendingScrollRatio)", html)
        self.assertIn("target.scrollLeft = Number(range.value) || 0", html)
        self.assertIn('target.addEventListener("scroll"', html)
        self.assertIn("renderTurnoverSectorShareChart", html)
        self.assertIn("renderTurnoverTop30Chart", html)
        self.assertIn("confine: true", html)
        swimlane = payload["sector_cycle_swimlane"]
        self.assertEqual(
            swimlane["dates"],
            ["2026-07-27", "2026-07-28", "2026-07-29", "2026-07-31", "2026-08-03", "2026-08-04", "2026-08-05"],
        )
        lanes = {item["sector"]: item for item in swimlane["lanes"]}
        self.assertEqual(
            [(item["start_date"], item["end_date"]) for item in lanes["国产芯片替代"]["runs"]],
            [
                ("2026-07-27", "2026-07-27"),
                ("2026-07-29", "2026-07-29"),
                ("2026-08-04", "2026-08-05"),
            ],
        )
        chip_observations = {item["date"]: item for item in lanes["国产芯片替代"]["observations"]}
        self.assertEqual(chip_observations["2026-08-05"]["kind"], "combined")
        self.assertEqual(chip_observations["2026-08-03"]["kind"], "missing")
        self.assertIsNone(chip_observations["2026-08-03"]["share_pct"])
        chip_ascii = next(line for line in swimlane["ascii"].splitlines() if line.startswith("国产芯片替代 |"))
        self.assertEqual(chip_ascii.split("|", 1)[1].split()[0], "?")
        self.assertIn("?", swimlane["ascii"])
        self.assertIn("@", swimlane["ascii"])
        self.assertIn("T-S01", html)
        self.assertIn("小周期成交额与主线切换判断", html)
        self.assertLess(html.index("data-sector-cycle-raw-records"), html.index("T-S01"))
        self.assertLess(html.index("T-S03"), html.rindex("附录：五、成交核心结果"))
        self.assertIn("A\\u0026B", payload_text)
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["sector"], "通信设备")
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["share_pct"], 73.9)
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["count"], 1)
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["leaders"][0]["name"], "中天科技")
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["leaders"][0]["status"], "涨停")
        self.assertEqual(payload["turnover_top30"]["items"][0]["name"], "中天科技")
        self.assertEqual(payload["turnover_top30"]["items"][0]["change_pct"], 9.99)
        self.assertEqual(payload["turnover_top30"]["items"][0]["status"], "涨停")
        self.assertEqual(payload["turnover_top30"]["items"][1]["change_pct"], -9.57)
        self.assertEqual(payload["turnover_top30"]["items"][1]["status"], "")

    def test_sector_cycle_swimlane_uses_frozen_common_start_relative_paths(self):
        artifact = _sector_relative_path_artifact(
            broad_market_confirmation=True,
        )
        before = copy.deepcopy(artifact)

        html = render_markdown_report_html(
            _sector_relative_path_markdown(),
            title="相对路径日报",
            trade_date="2026-08-14",
            sector_tournament_three_axis=artifact,
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        swimlane = json.loads(payload_text)["sector_cycle_swimlane"]
        lanes = {item["sector"]: item for item in swimlane["lanes"]}
        stage_lane = lanes["CXO/创新药"]
        attack_lane = lanes["半导体"]

        self.assertEqual(swimlane["schema"], "sector_relative_path_swimlane.v2")
        self.assertEqual(swimlane["comparison_start_date"], "2026-07-31")
        self.assertEqual(swimlane["comparison_end_date"], "2026-08-14")
        self.assertEqual(swimlane["baseline_value"], 100)
        self.assertEqual(stage_lane["normalized_path"][0]["normalized_value"], 100.0)
        self.assertEqual(stage_lane["normalized_path"][-1]["normalized_value"], 113.0)
        self.assertTrue(stage_lane["path_complete"])
        self.assertIn("阶段主线", stage_lane["roles"])
        self.assertNotIn("当日主攻", stage_lane["roles"])
        self.assertEqual(stage_lane["interpretation"], "真正转强")
        self.assertEqual(stage_lane["price_absorption"], "价格吸收较充分")
        self.assertEqual(len(stage_lane["activity_intervals"]), 1)
        interval = stage_lane["activity_intervals"][0]
        self.assertEqual(interval["source_start_date"], "2026-07-31")
        self.assertEqual(interval["source_end_date"], "2026-08-14")
        self.assertEqual(interval["span_trading_days"], 11)
        self.assertEqual(interval["visible_span_trading_days"], 11)
        self.assertEqual(interval["range_kind"], "stage_interval")
        self.assertEqual(interval["status"], "持续反馈")
        self.assertTrue(interval["is_ongoing"])
        self.assertIn("跨日反馈", interval["basis_labels"])
        self.assertIn("轮动", interval["basis_labels"])
        self.assertIn("成交参与", interval["basis_labels"])
        self.assertEqual(swimlane["interval_start_date"], "2026-07-31")
        self.assertEqual(swimlane["interval_end_date"], "2026-08-14")
        self.assertEqual(swimlane["interval_lane_count"], 2)
        self.assertIn("当日主攻", attack_lane["roles"])
        self.assertNotIn("阶段主线", attack_lane["roles"])
        self.assertFalse(attack_lane["path_complete"])
        self.assertEqual(
            attack_lane["activity_intervals"][0]["range_kind"],
            "observed_feedback",
        )
        self.assertFalse(attack_lane["activity_intervals"][0]["is_ongoing"])
        self.assertEqual(attack_lane["interpretation"], "相对价格路径未生成")
        self.assertNotEqual(attack_lane["stage_status"], "事实不足")
        self.assertNotEqual(attack_lane["divergence_test_status"], "事实不足")
        self.assertNotIn("事实不足", json.dumps(attack_lane, ensure_ascii=False))
        self.assertEqual(artifact, before)
        self.assertIn("板块反馈区间泳道", html)
        self.assertIn("反馈起止区间", html)
        self.assertIn("归一价格辅助线", html)
        self.assertIn("逐日反馈与资金节点", html)
        self.assertIn("const relativePathSeries", html)
        self.assertIn("activityIntervalItems", html)
        self.assertIn("const isOngoing = item.is_ongoing === true;", html)
        self.assertIn(
            'const isObservedFeedback = item.range_kind === "observed_feedback";',
            html,
        )
        self.assertIn("const isEnded = !isOngoing || isTerminalStatus;", html)
        self.assertIn("? (isOngoing ? 0.66 : 0.48)", html)
        self.assertIn("? 0.42", html)
        self.assertIn("? 0.54", html)
        self.assertIn(": 0.72", html)
        self.assertIn("? [8, 4]", html)
        self.assertIn("? [2, 3]", html)
        self.assertIn("? [5, 3]", html)
        self.assertIn("if (isOngoing && !isTerminalStatus)", html)
        relative_series_renderer = html.split("const relativePathSeries", 1)[1].split(
            "let chart = null",
            1,
        )[0]
        self.assertNotIn('name: "小周期方向辅助记录"', relative_series_renderer)
        self.assertIn("activityEventItems", html)
        self.assertIn("event_kind: eventKind", html)
        self.assertIn("event_kind_index: eventKindIndex", html)
        self.assertIn("kind === \"institution_net_buy\"", html)
        self.assertIn("kind === \"main_fund_inflow\"", html)
        self.assertIn("const activityEventMarkerPosition", html)
        self.assertIn("const ringRadius = Math.max(18, Math.min(laneHeight * 0.25, 20));", html)
        self.assertNotIn("(kindIndex - (kindCount - 1) / 2) * 6", html)
        self.assertIn("const item = pathItems[params.dataIndex]?.item || {};", html)
        self.assertIn("const normalizedValue = nullableNumber(point?.normalized_value);", html)
        self.assertIn(
            "const metric = nullableNumber(item.relative_strength_metric);",
            html,
        )
        self.assertIn(
            "const coverage = nullableNumber(item.comparison_coverage);",
            html,
        )
        self.assertIn(
            "const density = nullableNumber(item.trend_density);",
            html,
        )
        self.assertIn("maxPathDeviation", html)
        self.assertIn("缺失不补0", html)
        self.assertTrue(
            all(
                not ({"main_fund_inflow", "institution_net_buy", "capital_return"} & set(event["kinds"]))
                for event in stage_lane["activity_events"]
            )
        )

    def test_sector_cycle_swimlane_names_missing_common_price_window(self):
        html = render_markdown_report_html(
            _sector_relative_path_markdown(),
            title="缺少共同价格窗口日报",
            trade_date="2026-08-19",
            sector_tournament_three_axis=_sector_relative_path_artifact(
                target_date="2026-08-19",
                records=[],
                daily_attack_line="半导体",
            ),
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        swimlane = json.loads(payload_text)["sector_cycle_swimlane"]

        self.assertEqual(swimlane["schema"], "sector_relative_path_swimlane.v2")
        self.assertIn("共同起点 | 相对价格路径未生成", swimlane["ascii"])
        self.assertNotIn("事实不足", swimlane["ascii"])

    def test_sector_cycle_swimlane_names_missing_stage_and_price_path(self):
        html = _bear_sector_cycle_swimlane_html(
            {
                "schema": "sector_relative_path_swimlane.v2",
                "dates": ["2026-08-18", "2026-08-19"],
                "lanes": [
                    {
                        "sector": "半导体",
                        "color": "#2F7FB8",
                        "roles": [],
                        "activity_intervals": [],
                    }
                ],
                "ascii": "半导体 | -- --",
                "stage_mainlines": [],
                "daily_attack_line": "",
                "path_status": "事实不足",
                "interval_lane_count": 0,
            }
        )

        self.assertIn("阶段方向未形成 / 当日主攻方向未形成", html)
        self.assertIn("归一价格路径仅作辅助（归一价格路径未生成）", html)
        self.assertNotIn("事实不足", html)

    def test_sector_cycle_swimlane_does_not_bridge_unrecorded_dates_in_v2(self):
        markdown = "\n".join(
            [
                "# 稀疏方向日报",
                "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
                "#### 小周期成交额与主线切换判断",
                "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
                "|---|---|---:|---:|---:|---:|---|---|",
                "| 2026-07-31 | CXO/创新药 | 1000亿 | 20000亿 | 5.0% | 待累计 | 阶段延续 | 辅助记录 |",
                "| 2026-08-14 | CXO/创新药 | 1200亿 | 20000亿 | 6.0% | +1.0pct | 阶段延续 | 辅助记录 |",
            ]
        )

        html = render_markdown_report_html(
            markdown,
            trade_date="2026-08-14",
            sector_tournament_three_axis=_sector_relative_path_artifact(),
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        swimlane = json.loads(payload_text)["sector_cycle_swimlane"]
        lane = next(item for item in swimlane["lanes"] if item["sector"] == "CXO/创新药")

        self.assertGreater(len(swimlane["dates"]), 2)
        self.assertEqual(
            [(item["start_date"], item["end_date"]) for item in lane["runs"]],
            [
                ("2026-07-31", "2026-07-31"),
                ("2026-08-14", "2026-08-14"),
            ],
        )
        self.assertEqual(
            [
                (item["source_start_date"], item["source_end_date"])
                for item in lane["activity_intervals"]
            ],
            [("2026-07-31", "2026-08-14")],
        )

    def test_sector_feedback_timeline_falls_back_when_stage_start_is_outside_axis(self):
        intervals, events, basis_labels = _sector_feedback_timeline(
            {
                "status": "阶段主线候选",
                "stage_start_date": "2026-08-20",
                "active_trade_dates": ["2026-08-13"],
            },
            dates=["2026-08-13", "2026-08-14"],
            normalized_path=[],
            runs=[],
            observations=[],
            capital_events=[],
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(basis_labels, ["跨日反馈"])
        self.assertEqual(
            intervals,
            [
                {
                    "start_index": 0,
                    "end_index": 0,
                    "start_date": "2026-08-13",
                    "end_date": "2026-08-13",
                    "source_start_date": "2026-08-13",
                    "source_end_date": "2026-08-13",
                    "start_basis": "首次可核实反馈",
                    "end_basis": "最近可核实反馈",
                    "range_kind": "observed_feedback",
                    "status": "观察中",
                    "is_ongoing": False,
                    "span_trading_days": 1,
                    "visible_span_trading_days": 1,
                    "evidence_day_count": 1,
                    "evidence_coverage": 1.0,
                    "basis_labels": ["跨日反馈"],
                }
            ],
        )

    def test_sector_feedback_timeline_distinguishes_stage_and_observed_range_endings(self):
        dates = ["2026-08-18", "2026-08-19", "2026-08-20"]
        cases = (
            (
                "ongoing_stage",
                {
                    "status": "阶段主线候选",
                    "stage_start_date": "2026-08-18",
                    "active_trade_dates": ["2026-08-20"],
                },
                "stage_interval",
                True,
            ),
            (
                "ended_stage",
                {
                    "status": "阶段主线候选",
                    "stage_start_date": "2026-08-18",
                    "active_trade_dates": ["2026-08-19"],
                },
                "stage_interval",
                False,
            ),
            (
                "ongoing_observed_feedback",
                {"active_trade_dates": ["2026-08-20"]},
                "observed_feedback",
                True,
            ),
            (
                "ended_observed_feedback",
                {"active_trade_dates": ["2026-08-19"]},
                "observed_feedback",
                False,
            ),
        )

        for name, record, expected_kind, expected_ongoing in cases:
            with self.subTest(name=name):
                intervals, _events, _basis_labels = _sector_feedback_timeline(
                    record,
                    dates=dates,
                    normalized_path=[],
                    runs=[],
                    observations=[],
                    capital_events=[],
                )

                self.assertEqual(len(intervals), 1)
                self.assertEqual(intervals[0]["range_kind"], expected_kind)
                self.assertIs(intervals[0]["is_ongoing"], expected_ongoing)

    def test_sector_feedback_timeline_clips_historical_stage_start_to_first_visible_event(self):
        intervals, events, basis_labels = _sector_feedback_timeline(
            {
                "status": "阶段主线候选",
                "stage_start_date": "2026-07-01",
                "as_of_date": "2026-08-04",
                "active_trade_dates": ["2026-08-04"],
            },
            dates=["2026-07-31", "2026-08-01", "2026-08-04"],
            normalized_path=[],
            runs=[],
            observations=[],
            capital_events=[],
        )

        self.assertEqual([event["date"] for event in events], ["2026-08-04"])
        self.assertEqual(basis_labels, ["跨日反馈"])
        self.assertEqual(len(intervals), 1)
        interval = intervals[0]
        self.assertEqual(interval["source_start_date"], "2026-07-01")
        self.assertEqual(interval["source_end_date"], "2026-08-04")
        self.assertEqual(interval["start_date"], "2026-08-04")
        self.assertEqual(interval["end_date"], "2026-08-04")
        self.assertEqual(interval["start_basis"], "轴内首次可核实反馈")
        self.assertEqual(interval["visible_span_trading_days"], 1)
        self.assertEqual(interval["evidence_coverage"], 1.0)

    def test_sector_feedback_timeline_does_not_restart_ended_stage_after_axis_boundary(self):
        for status in ("阶段主线弱化", "阶段主线失效"):
            with self.subTest(status=status):
                intervals, events, basis_labels = _sector_feedback_timeline(
                    {
                        "status": status,
                        "stage_start_date": "2026-07-01",
                        "last_confirmed_date": "2026-07-15",
                        "active_trade_dates": ["2026-08-04"],
                    },
                    dates=["2026-07-31", "2026-08-01", "2026-08-04"],
                    normalized_path=[],
                    runs=[],
                    observations=[],
                    capital_events=[],
                )

                self.assertEqual(intervals, [])
                self.assertEqual([event["date"] for event in events], ["2026-08-04"])
                self.assertEqual(basis_labels, [])

    def test_sector_cycle_swimlane_stops_weakened_or_invalidated_range_at_last_confirmation(self):
        fixture = json.loads(SECTOR_STAGE_FIXTURE.read_text(encoding="utf-8"))
        base_record = fixture["record"]
        base_record.update(
            {
                "prior_status": "confirmed",
                "recognition_date": "2026-08-13",
                "last_confirmed_date": "2026-08-13",
            }
        )
        cases = [
            (
                "阶段主线弱化",
                "反馈减弱",
                "weakening_evidence",
                [{"text": "跨日回流停止", "source_date": "2026-08-14"}],
            ),
            (
                "阶段主线失效",
                "反馈结束",
                "invalidation_evidence",
                [{"text": "阶段结构失效", "source_date": "2026-08-14"}],
            ),
        ]

        for stage_status, interval_status, field, evidence in cases:
            with self.subTest(stage_status=stage_status):
                record = copy.deepcopy(base_record)
                record[field] = evidence
                html = render_markdown_report_html(
                    _sector_relative_path_markdown(),
                    trade_date="2026-08-14",
                    sector_tournament_three_axis=_sector_relative_path_artifact(
                        records=[record]
                    ),
                )
                payload_text = re.search(
                    r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                    html,
                ).group(1)
                lane = next(
                    item
                    for item in json.loads(payload_text)["sector_cycle_swimlane"]["lanes"]
                    if item["sector"] == "CXO/创新药"
                )
                interval = lane["activity_intervals"][0]

                self.assertEqual(lane["stage_status"], stage_status)
                self.assertEqual(interval["source_start_date"], "2026-07-31")
                self.assertEqual(interval["source_end_date"], "2026-08-13")
                self.assertEqual(interval["end_date"], "2026-08-13")
                self.assertEqual(interval["span_trading_days"], 10)
                self.assertEqual(interval["status"], interval_status)
                self.assertFalse(interval["is_ongoing"])

    def test_sector_cycle_swimlane_maps_target_date_fund_and_institution_evidence(self):
        markdown = _sector_relative_path_markdown() + "\n" + "\n".join(
            [
                "### 板块资金流入强榜",
                "| 板块 | 主力净流入 |",
                "|---|---:|",
                "| CXO/创新药 | +12.50亿 |",
                "### 成交核心结果",
                "| 股票 | 代码 | 所属板块 |",
                "|---|---|---|",
                "| 药明康德 | 603259 | CXO/创新药 |",
                "### 机构净买强榜",
                "| 排名 | 股票 | 代码 | 机构净买(亿) |",
                "|---:|---|---|---:|",
                "| 1 | 药明康德 | 603259 | 3.20 |",
            ]
        )
        html = render_markdown_report_html(
            markdown,
            trade_date="2026-08-14",
            sector_tournament_three_axis=_sector_relative_path_artifact(),
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        swimlane = json.loads(payload_text)["sector_cycle_swimlane"]
        lane = next(
            item for item in swimlane["lanes"] if item["sector"] == "CXO/创新药"
        )
        event = next(
            item for item in lane["activity_events"] if item["date"] == "2026-08-14"
        )

        self.assertIn("main_fund_inflow", event["kinds"])
        self.assertIn("institution_net_buy", event["kinds"])
        self.assertEqual(event["amounts_yi"]["main_fund_inflow"], 12.5)
        self.assertEqual(event["amounts_yi"]["institution_net_buy"], 3.2)
        self.assertEqual(event["stock_names"], ["药明康德"])
        self.assertEqual(
            event["details_by_kind"]["main_fund_inflow"],
            ["主力净流入 +12.50亿"],
        )
        self.assertEqual(
            event["details_by_kind"]["institution_net_buy"],
            ["机构净买 +3.20亿（药明康德）"],
        )
        self.assertNotIn("main_fund_inflow", event["stock_names_by_kind"])
        self.assertEqual(
            event["stock_names_by_kind"]["institution_net_buy"],
            ["药明康德"],
        )
        self.assertEqual(swimlane["capital_event_count"], 1)
        self.assertEqual(swimlane["capital_event_date_count"], 1)
        self.assertIn("主力资金", html)
        self.assertIn("机构净买", html)
        self.assertIn(
            "details: Array.isArray(detailsByKind[eventKind]) ? detailsByKind[eventKind] : []",
            html,
        )
        self.assertIn(
            "stock_names: Array.isArray(stockNamesByKind[eventKind])",
            html,
        )

    def test_sector_cycle_swimlane_ignores_institution_table_without_stock_column(self):
        markdown = _sector_relative_path_markdown() + "\n" + "\n".join(
            [
                "### 成交核心结果",
                "| 股票 | 代码 | 所属板块 |",
                "|---|---|---|",
                "| 药明康德 | 603259 | CXO/创新药 |",
                "### 机构净买强榜",
                "| 排名 | 代码 | 机构净买(亿) |",
                "|---:|---|---:|",
                "| 1 | 603259 | 3.20 |",
            ]
        )
        html = render_markdown_report_html(
            markdown,
            trade_date="2026-08-14",
            sector_tournament_three_axis=_sector_relative_path_artifact(),
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        lane = next(
            item
            for item in json.loads(payload_text)["sector_cycle_swimlane"]["lanes"]
            if item["sector"] == "CXO/创新药"
        )

        self.assertTrue(
            all(
                "institution_net_buy" not in event["kinds"]
                for event in lane["activity_events"]
            )
        )

    def test_sector_cycle_swimlane_ignores_institution_row_without_sector_mapping(self):
        markdown = _sector_relative_path_markdown() + "\n" + "\n".join(
            [
                "### 成交核心结果",
                "| 股票 | 代码 | 所属板块 |",
                "|---|---|---|",
                "| 药明康德 | 603259 | CXO/创新药 |",
                "### 机构净买强榜",
                "| 排名 | 股票 | 代码 | 机构净买(亿) |",
                "|---:|---|---|---:|",
                "| 1 | 恒瑞医药 | 600276 | 3.20 |",
            ]
        )
        html = render_markdown_report_html(
            markdown,
            trade_date="2026-08-14",
            sector_tournament_three_axis=_sector_relative_path_artifact(),
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        lane = next(
            item
            for item in json.loads(payload_text)["sector_cycle_swimlane"]["lanes"]
            if item["sector"] == "CXO/创新药"
        )

        self.assertTrue(
            all(
                "institution_net_buy" not in event["kinds"]
                for event in lane["activity_events"]
            )
        )

    def test_sector_cycle_swimlane_rendering_keeps_complete_formal_decision_projection(self):
        artifact = _sector_relative_path_artifact(broad_market_confirmation=True)
        target = {"code": "603986", "name": "兆易创新"}
        data = {
            "selection_workflow": {
                "final": {"execution_object": target, "position_pct": 50},
                "sector_tournament_three_axis": artifact,
            },
            "final_target_resolution": {
                "new_entry_target": target,
                "position_pct": 50,
                "old_position_plan": {
                    "holding": {"code": "600667", "name": "太极实业"},
                    "action": "hold",
                },
            },
            "position_decision": {
                "execution_nature": "50%条件执行",
                "exit_action": {"action": "失效条件出现则退出"},
            },
            "two_layer_decision_payload": {
                "next_day_action": {
                    "execution_object": target,
                    "position_pct": 50,
                    "b1_action": "B1先买参与权",
                    "b2_action": "确认后才补B2",
                    "exit_action": "失效条件出现则退出",
                },
                "old_position_action_rows": {"旧仓动作": "按原预案处理"},
            },
            "formal_decision_input": {"input_hash": "fixed-formal-input"},
            "formal_account_decision": {
                "formal_execution_object": target,
                "selected_action": "add",
                "account_exposure": {
                    "current_position_pct": 50,
                    "planned_total_position_pct": 100,
                    "executable_new_entry_pct": 50,
                    "closing_target_position_pct": 100,
                },
                "outcomes": {
                    "hold": {"status": "not_selected"},
                    "add": {"status": "selected"},
                    "replace": {"status": "not_selected"},
                    "cash": {"status": "not_selected"},
                },
                "b1": {"action": "已有旧仓作为B1参与权"},
                "b2": {"action": "确认后补B2"},
                "exit_plan": {
                    "action": "失效条件出现则退出",
                    "requires_confirmation_before_reuse": False,
                },
                "decision_hash": "fixed-formal-account",
            },
        }

        def selected_fields(payload):
            projection = build_decision_projection(payload, target_date="2026-08-14")
            return {
                "object": projection["formal_object"],
                "position": projection["decision_position_pct"],
                "execution_nature": projection["execution_nature"],
                "account_action": projection["account_action"],
                "b1": projection["b1"],
                "b2": projection["b2"],
                "old_position_action": projection["old_position_action"],
                "exit_action": projection["exit_action"],
                "funds_destination": projection["funds_destination"],
            }

        before = selected_fields(data)
        html = render_markdown_report_html(
            _sector_relative_path_markdown(),
            trade_date="2026-08-14",
            sector_tournament_three_axis=data["selection_workflow"][
                "sector_tournament_three_axis"
            ],
        )
        after = selected_fields(data)
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)

        self.assertEqual(
            json.loads(payload_text)["sector_cycle_swimlane"]["schema"],
            "sector_relative_path_swimlane.v2",
        )
        self.assertEqual(after, before)
        self.assertEqual(
            list(before),
            [
                "object",
                "position",
                "execution_nature",
                "account_action",
                "b1",
                "b2",
                "old_position_action",
                "exit_action",
                "funds_destination",
            ],
        )

    def test_sector_cycle_swimlane_labels_complete_divergence_repair_separately(self):
        fixture = json.loads(SECTOR_STAGE_FIXTURE.read_text(encoding="utf-8"))
        record = fixture["record"]
        path_by_date = {
            item["trade_date"]: item for item in record["sector_index_path"]
        }
        record.update(
            {
                "divergence_date": "2026-08-11",
                "divergence_date_source_date": "2026-08-14",
                "repair_date": "2026-08-14",
                "repair_date_source_date": "2026-08-14",
                "repair_evidence": [
                    {
                        "kind": "sector_index_repair",
                        "divergence_index_value": path_by_date["2026-08-11"]["index_value"],
                        "repair_index_value": path_by_date["2026-08-14"]["index_value"],
                        "source_date": "2026-08-14",
                    },
                    {
                        "kind": "capital_return",
                        "trade_date": "2026-08-14",
                        "source_date": "2026-08-14",
                    },
                    {
                        "kind": "internal_trend_density",
                        "trend_stock_count": record["trend_stock_count"],
                        "comparable_stock_count": record["comparable_stock_count"],
                        "trend_definition_version": record["trend_definition_version"],
                        "source_date": "2026-08-14",
                    },
                ],
            }
        )
        artifact = _sector_relative_path_artifact(records=[record])

        html = render_markdown_report_html(
            _sector_relative_path_markdown(),
            trade_date="2026-08-14",
            sector_tournament_three_axis=artifact,
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        lane = next(
            item
            for item in json.loads(payload_text)["sector_cycle_swimlane"]["lanes"]
            if item["sector"] == "CXO/创新药"
        )

        self.assertEqual(lane["divergence_test_status"], "分歧已修复")
        self.assertEqual(lane["interpretation"], "高质量修复")

    def test_sector_cycle_swimlane_keeps_window_mismatch_and_missing_day_honest(self):
        fixture = json.loads(SECTOR_STAGE_FIXTURE.read_text(encoding="utf-8"))
        evaluated = fixture["record"]
        mismatched = copy.deepcopy(evaluated)
        mismatched["direction"] = "机器人"
        mismatched["relative_strength_window"]["trade_dates"] = mismatched[
            "relative_strength_window"
        ]["trade_dates"][1:]
        missing_day = copy.deepcopy(evaluated)
        missing_day["sector_index_path"] = [
            item
            for item in missing_day["sector_index_path"]
            if item["trade_date"] != "2026-08-06"
        ]

        mismatch_html = render_markdown_report_html(
            _sector_relative_path_markdown(),
            trade_date="2026-08-14",
            sector_tournament_three_axis=_sector_relative_path_artifact(
                records=[evaluated, mismatched]
            ),
        )
        mismatch_payload = json.loads(
            re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                mismatch_html,
            ).group(1)
        )["sector_cycle_swimlane"]
        mismatch_lane = next(
            item for item in mismatch_payload["lanes"] if item["sector"] == "机器人"
        )
        self.assertFalse(mismatch_lane["path_complete"])
        self.assertEqual(
            mismatch_lane["path_missing_reason"],
            "比较窗口不一致，不能强行归一",
        )
        self.assertTrue(
            all(item["normalized_value"] is None for item in mismatch_lane["normalized_path"])
        )

        missing_html = render_markdown_report_html(
            _sector_relative_path_markdown(),
            trade_date="2026-08-14",
            sector_tournament_three_axis=_sector_relative_path_artifact(
                records=[missing_day]
            ),
        )
        missing_payload = json.loads(
            re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                missing_html,
            ).group(1)
        )["sector_cycle_swimlane"]
        missing_lane = next(
            item for item in missing_payload["lanes"] if item["sector"] == "CXO/创新药"
        )
        gap = next(
            item for item in missing_lane["normalized_path"] if item["date"] == "2026-08-06"
        )
        self.assertIsNone(gap["raw_value"])
        self.assertIsNone(gap["normalized_value"])
        self.assertEqual(missing_payload["path_status"], "部分")
        self.assertEqual(
            [
                (
                    item["source_start_date"],
                    item["source_end_date"],
                    item["span_trading_days"],
                )
                for item in missing_lane["activity_intervals"]
            ],
            [("2026-07-31", "2026-08-14", 11)],
        )
        cxo_ascii = next(
            line
            for line in missing_payload["ascii"].splitlines()
            if line.startswith("CXO/创新药 价格辅助")
        )
        gap_index = missing_payload["dates"].index("2026-08-06")
        self.assertEqual(cxo_ascii.split("|", 1)[1].split()[gap_index], "--")

    def test_sector_cycle_swimlane_rejects_invalid_artifact_and_excludes_future_path(self):
        artifact = _sector_relative_path_artifact()
        invalid = copy.deepcopy(artifact)
        invalid["artifact_hash"] = "invalid"

        invalid_html = render_markdown_report_html(
            _sector_relative_path_markdown(),
            trade_date="2026-08-14",
            sector_tournament_three_axis=invalid,
        )
        invalid_payload = json.loads(
            re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                invalid_html,
            ).group(1)
        )["sector_cycle_swimlane"]
        self.assertEqual(invalid_payload["schema"], "sector_cycle_swimlane.v1")
        self.assertIn("25日板块周期泳道", invalid_html)

        fixture = json.loads(SECTOR_STAGE_FIXTURE.read_text(encoding="utf-8"))
        future_html = render_markdown_report_html(
            _sector_relative_path_markdown(),
            trade_date="2026-08-13",
            sector_tournament_three_axis=_sector_relative_path_artifact(
                target_date="2026-08-13",
                records=[fixture["record"]],
            ),
        )
        future_payload = json.loads(
            re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                future_html,
            ).group(1)
        )["sector_cycle_swimlane"]
        self.assertEqual(future_payload["schema"], "sector_relative_path_swimlane.v2")
        self.assertEqual(future_payload["comparison_end_date"], "2026-08-13")
        self.assertNotIn("2026-08-14", future_payload["dates"])
        self.assertNotIn("2026-08-14", future_payload["ascii"])

    def test_sector_cycle_swimlane_keeps_original_table_when_direction_history_is_missing(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 旧格式日报",
                    "",
                    "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#2F7FB8;border-color:#2F7FB8">[半导体]</span>',
                    "**T-OLD**",
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-07-03 | 5639.55亿 | 32052.62亿 | 17.6% | 待累计 | 待累计 | 旧格式记录 |",
                ]
            ),
            title="旧格式日报",
            trade_date="2026-07-03",
        )

        self.assertNotIn('data-bear-chart="sector_cycle_swimlane"', html)
        self.assertNotIn("data-sector-cycle-raw-records", html)
        self.assertIn("T-OLD", html)
        self.assertIn("5639.55亿", html)

    def test_sector_cycle_swimlane_replaces_expanded_appendix_copy(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 附录泳道日报",
                    "",
                    "#### 附录：市场容量演化",
                    "##### 附录：近期热点板块成交额连续跟踪",
                    "> 附录原始记录。",
                    '##### 附录：近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span>',
                    "**T-064**",
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-08-05 | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 同板块连续 | 资金容量扩张 |",
                    "",
                    "##### 附录：小周期成交额与主线切换判断",
                    "**T-072**",
                    "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
                    "|------|------------|------------|------------|------|----------|----------|------|",
                    '| 2026-08-05 | <span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span> | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 大周期延续 | 可用 |',
                    "",
                    "**T-073**",
                ]
            ),
            title="附录泳道日报",
            trade_date="2026-08-05",
        )

        self.assertEqual(html.count('data-bear-chart="sector_cycle_swimlane"'), 1)
        details_match = re.search(
            r'<details class="sector-cycle-raw-records".*?</details>',
            html,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(details_match)
        details_html = details_match.group(0)
        self.assertIn("T-064", details_html)
        self.assertIn("T-072", details_html)
        self.assertNotIn("T-073", details_html)

    def test_sector_cycle_swimlane_prefers_primary_heading_and_keeps_each_raw_group(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 三来源泳道日报",
                    "",
                    "##### 附录：近期热点板块成交额连续跟踪",
                    '##### 附录：近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span>',
                    "**T-A1**",
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-08-05 | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 同板块连续 | 附录先出现 |",
                    "##### 附录：小周期成交额与主线切换判断",
                    "**T-A2**",
                    "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
                    "|------|------------|------------|------------|------|----------|----------|------|",
                    "| 2026-08-05 | 国产芯片替代 | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 大周期延续 | 附录事实 |",
                    "附录周期组结束后内容",
                    "",
                    "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span>',
                    "**T-P1**",
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-08-05 | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 同板块连续 | 主文事实 |",
                    "#### 小周期成交额与主线切换判断",
                    "**T-P2**",
                    "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
                    "|------|------------|------------|------------|------|----------|----------|------|",
                    "| 2026-08-05 | 国产芯片替代 | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 大周期延续 | 主文事实 |",
                    "主文周期组结束后内容",
                    "",
                    "## 八、详细附录",
                    "### 附录：周期与主线依据",
                    "##### 附录：近期热点板块成交额连续跟踪",
                    '##### 附录：近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span>',
                    "**T-D1**",
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-08-05 | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 同板块连续 | 详细附录事实 |",
                    "##### 附录：小周期成交额与主线切换判断",
                    "**T-D2**",
                    "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
                    "|------|------------|------------|------------|------|----------|----------|------|",
                    "| 2026-08-05 | 国产芯片替代 | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 大周期延续 | 详细附录事实 |",
                    "详细附录周期组结束后内容",
                    "",
                    "## 知识复利候选",
                    "- 后续章节保持可见",
                ]
            ),
            title="三来源泳道日报",
            trade_date="2026-08-05",
        )

        primary_heading_index = html.index('id="5-主线成交额占比趋势近期热点板块连续跟踪"')
        swimlane_index = html.index('data-bear-chart-card="sector_cycle_swimlane"')
        self.assertGreater(swimlane_index, primary_heading_index)
        self.assertEqual(html.count('data-bear-chart="sector_cycle_swimlane"'), 1)
        self.assertEqual(html.count("<h4>25日板块周期泳道</h4>"), 1)
        self.assertEqual(html.count("data-sector-cycle-raw-records"), 3)
        self.assertNotIn("data-sector-cycle-raw-records open", html)
        raw_groups = re.findall(
            r'<details class="sector-cycle-raw-records".*?</details>',
            html,
            flags=re.DOTALL,
        )
        self.assertEqual(len(raw_groups), 3)
        expected_groups = (
            ("T-A1", "T-A2", "附录周期组结束后内容"),
            ("T-P1", "T-P2", "主文周期组结束后内容"),
            ("T-D1", "T-D2", "详细附录周期组结束后内容"),
        )
        for raw_group, (first_token, second_token, outside_marker) in zip(raw_groups, expected_groups):
            self.assertIn(first_token, raw_group)
            self.assertIn(second_token, raw_group)
            self.assertNotIn(outside_marker, raw_group)

    def test_sector_cycle_swimlane_ignores_primary_heading_inside_fenced_code(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 旧格式泳道日报",
                    "",
                    "```markdown",
                    "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
                    "```",
                    "##### 附录：近期热点板块成交额连续跟踪",
                    "**T-LEGACY-A**",
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-08-05 | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 同板块连续 | 旧报告事实 |",
                    "##### 附录：小周期成交额与主线切换判断",
                    "**T-LEGACY-B**",
                    "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
                    "|------|------------|------------|------------|------|----------|----------|------|",
                    "| 2026-08-05 | 国产芯片替代 | 7605.11亿 | 26798.86亿 | 28.4% | +1.7pct | 大周期延续 | 旧报告事实 |",
                ]
            ),
            title="旧格式泳道日报",
            trade_date="2026-08-05",
        )

        self.assertEqual(html.count('data-bear-chart="sector_cycle_swimlane"'), 1)
        self.assertEqual(html.count("<h4>25日板块周期泳道</h4>"), 1)
        self.assertIn("T-LEGACY-A", html)
        self.assertIn("T-LEGACY-B", html)

    def test_detailed_appendix_groups_h3_sections_and_closes_before_next_h2(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 折叠附录日报",
                    "",
                    "## 八、详细附录",
                    "附录引导保留在摘要列表前。",
                    "### 附录：周期与主线依据",
                    "#### 附录：主线攻击证据",
                    "**T-APPENDIX-A**",
                    "| 板块 | 结论 |",
                    "|------|------|",
                    "| 电力 | 仅观察，条件未满足 |",
                    "### 附录：资金A&B复核",
                    "#### 附录：资金结论",
                    "**T-APPENDIX-B**",
                    "- 资金事实完整保留。",
                    "## 知识复利候选",
                    "**T-AFTER-APPENDIX**",
                    "- 后续章节保持可见。",
                ]
            ),
            title="折叠附录日报",
            trade_date="2026-08-05",
        )

        self.assertEqual(html.count('<details class="bear-appendix-section"'), 2)
        self.assertNotIn('<details class="bear-appendix-section" open', html)
        self.assertEqual(html.count('id="附录周期与主线依据"'), 1)
        self.assertEqual(html.count('href="#附录周期与主线依据"'), 2)
        self.assertEqual(html.count('<details class="mobile-nav-appendix">'), 1)
        self.assertNotIn('<details class="mobile-nav-appendix" open', html)
        self.assertIn('<summary><span>详细附录</span><small>2项</small></summary>', html)
        self.assertIn('class="mobile-nav-appendix-links"', html)
        self.assertIn('.mobile-nav-appendix-links a.level-3', html)
        self.assertIn("附录：资金A&amp;B复核", html)
        appendix_groups = re.findall(
            r'<details class="bear-appendix-section".*?</details>',
            html,
            flags=re.DOTALL,
        )
        self.assertEqual(len(appendix_groups), 2)
        self.assertIn("T-APPENDIX-A", appendix_groups[0])
        self.assertNotIn("T-APPENDIX-B", appendix_groups[0])
        self.assertIn("T-APPENDIX-B", appendix_groups[1])
        self.assertNotIn("T-AFTER-APPENDIX", appendix_groups[1])
        self.assertLess(html.rindex("</details>"), html.index("T-AFTER-APPENDIX"))
        self.assertIn("附录引导保留在摘要列表前。", html)
        self.assertIn(".bear-appendix-section > summary", html)
        self.assertIn(".bear-appendix-section-body", html)

    def test_detailed_appendix_without_direct_h3_keeps_body_unwrapped(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 无分组附录日报",
                    "",
                    "## 八、详细附录",
                    "附录正文保持直接可见。",
                    "#### 四级事实标题",
                    "**T-APPENDIX-PLAIN**",
                ]
            ),
            title="无分组附录日报",
            trade_date="2026-08-05",
        )

        self.assertNotIn('class="bear-appendix-section"', html)
        self.assertIn("附录正文保持直接可见。", html)
        self.assertIn("T-APPENDIX-PLAIN", html)

    def test_detailed_appendix_closes_last_h3_group_at_end_of_file(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 文末附录日报",
                    "",
                    "## 八、详细附录",
                    "### 附录：文末事实",
                    "#### 文末事实标题",
                    "**T-APPENDIX-EOF**",
                ]
            ),
            title="文末附录日报",
            trade_date="2026-08-05",
        )

        self.assertEqual(html.count('<details class="bear-appendix-section"'), 1)
        self.assertIsNotNone(
            re.search(
                r'<details class="bear-appendix-section".*?T-APPENDIX-EOF.*?</div></details>',
                html,
                flags=re.DOTALL,
            )
        )

    def test_sector_cycle_swimlane_keeps_blank_direction_date_as_a_run_break(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 方向断点日报",
                    "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span>',
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-08-05 | 7605.11亿 | 26798.86亿 | 28.4% | 待累计 | 待累计 | 可用 |",
                    "| 2026-08-01 | 6000.00亿 | 25000.00亿 | 24.0% | 待累计 | 待累计 | 可用 |",
                    "#### 小周期成交额与主线切换判断",
                    "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
                    "|------|------------|------------|------------|------|----------|----------|------|",
                    '| 2026-08-05 | <span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span> | 7605.11亿 | 26798.86亿 | 28.4% | 待累计 | 大周期延续 | 可用 |',
                    "| 2026-08-04 |  | 数据暂缺 | 数据暂缺 | 待累计 | 待累计 | 待确认 | 方向事实不足 |",
                    '| 2026-08-01 | <span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span> | 6000.00亿 | 25000.00亿 | 24.0% | 待累计 | 大周期延续 | 可用 |',
                ]
            ),
            title="方向断点日报",
            trade_date="2026-08-05",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        swimlane = json.loads(payload_text)["sector_cycle_swimlane"]
        chip_lane = next(item for item in swimlane["lanes"] if item["sector"] == "国产芯片替代")

        self.assertEqual(swimlane["dates"], ["2026-08-01", "2026-08-04", "2026-08-05"])
        self.assertEqual(
            [(item["start_date"], item["end_date"]) for item in chip_lane["runs"]],
            [("2026-08-01", "2026-08-01"), ("2026-08-05", "2026-08-05")],
        )

    def test_turnover_top30_prefers_complete_dated_facts_without_mutating_input(self):
        snapshot = json.loads((ROOT / "snapshots" / "2026-10-13.json").read_text(encoding="utf-8"))
        rows = snapshot["data"]["turnover_rank"]
        before = copy.deepcopy(rows)
        html = render_markdown_report_html(
            "# 日报\n\n## 成交核心结果\n\n| 排名 | 股票 | 代码 | 成交额 | 所属板块 | 涨跌幅 |\n"
            "|---|---|---|---|---|---|\n| 1 | 正文摘要 | 000001 | 1亿 | 样本 | +1% |",
            trade_date="2026-10-13", turnover_rank=list(reversed(rows)),
        )
        payload = json.loads(re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1))
        chart = payload["turnover_top30"]
        self.assertEqual(len(rows), 50)
        self.assertEqual(len(chart["items"]), 30)
        self.assertTrue(chart["complete"])
        self.assertEqual(chart["unit"], "亿元")
        self.assertEqual(chart["trade_date"], "2026-10-13")
        self.assertEqual([item["code"] for item in chart["items"]], [item["code"] for item in before[:30]])
        self.assertEqual(chart["items"][0]["turnover"], 221.13187)
        self.assertEqual(chart["items"][-1]["name"], "先导智能")
        self.assertEqual(chart["items"][-1]["turnover"], 43.462502)
        self.assertEqual(chart["items"][-1]["change_pct"], -9.58)
        self.assertEqual(sum(item["count"] for item in payload["turnover_sector_share"]["items"]), 30)
        self.assertEqual(rows, before)

    def test_turnover_top30_rejects_unknown_dates_and_amounts_without_padding(self):
        base = {"code": "300450", "name": "先导智能", "turnover": 43.462502, "trade_date": "2026-10-13"}
        rows = [base, dict(base),
                {**base, "code": "300451", "trade_date": "2026-10-12"},
                {**base, "code": "300452", "trade_date": ""},
                {**base, "code": "300453", "trade_date": "2026-10-14"}]
        for index, amount in enumerate((None, "NaN", "Infinity", -1, 0, "43亿元")):
            rows.append({**base, "code": str(600000 + index), "turnover": amount})
        html = render_markdown_report_html("# 日报", trade_date="2026-10-13", turnover_rank=rows)
        payload = json.loads(re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1))
        chart = payload["turnover_top30"]
        self.assertEqual(len(chart["items"]), 1)
        self.assertFalse(chart["complete"])
        self.assertIsNone(chart["items"][0]["change_pct"])
        self.assertIn("可核实 1 条", chart["subtitle"])

    def test_turnover_top30_explicit_empty_facts_do_not_reuse_core_summary(self):
        markdown = "# 日报\n\n## 成交核心结果\n\n| 排名 | 股票 | 代码 | 成交额 | 所属板块 | 涨跌幅 |\n|---|---|---|---|---|---|\n| 1 | 摘要 | 000001 | 200亿 | 样本 | +1% |"
        for target_date, rows in (("2026-10-13", []), ("invalid", [{"code": "000001", "name": "摘要", "trade_date": "2026-10-13", "turnover": 200}])):
            with self.subTest(target_date=target_date):
                html = render_markdown_report_html(markdown, trade_date=target_date, turnover_rank=rows)
                payload = json.loads(re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1))
                self.assertNotIn("turnover_top30", payload)

    def test_turnover_snapshot_cli_matches_file_api_and_leaves_sources_untouched(self):
        rows = [{"code": "300450", "name": "先导智能", "turnover": 43.462502, "change_pct": -9.58, "trade_date": "2026-10-13"}]
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            markdown = root / "report.md"
            snapshot = root / "snapshot.json"
            markdown.write_text("# 日报", encoding="utf-8")
            snapshot_text = json.dumps({"date": "2026-10-13", "data": {"target_date": "2026-10-13", "turnover_rank": rows}})
            snapshot.write_text(snapshot_text, encoding="utf-8")
            direct = render_markdown_report_file(markdown, root / "direct.html", trade_date="2026-10-13", turnover_rank=rows)
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(render_markdown_report_main([str(markdown), str(root / "cli.html"), "--snapshot-json", str(snapshot)]), 0)
            def payload(path):
                return json.loads(re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', path.read_text(encoding="utf-8")).group(1))
            self.assertEqual(payload(direct)["turnover_top30"], payload(root / "cli.html")["turnover_top30"])
            self.assertEqual(snapshot.read_text(encoding="utf-8"), snapshot_text)
            self.assertEqual(markdown.read_text(encoding="utf-8"), "# 日报")
            with patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit):
                render_markdown_report_main([str(markdown), str(root / "wrong.html"), "--trade-date", "2026-10-12", "--snapshot-json", str(snapshot)])
            self.assertFalse((root / "wrong.html").exists())

    def test_turnover_top30_uses_code_specific_limit_status_labels(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 附录：五、成交核心结果",
                    "| 排名 | 股票 | 代码 | 成交额 | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 隔日判断 | 蜡烛图形态 |",
                    "|------|------|------|--------|----------|--------|--------|--------|--------|--------|----------|------------|",
                    "| 1 | 华虹宏力 | 688347 | 133.64亿 | 半导体 | -12.58% | 389.50 | 331.12 | 383.96 | 341.00 | 关注 | 下跌趋势(0分) |",
                    "| 2 | 主板示例 | 002432 | 100.00亿 | 半导体 | -10.00% | 10.00 | 9.00 | 10.00 | 9.00 | 谨慎 | 下跌趋势(0分) |",
                    "| 3 | 科创示例 | 688001 | 90.00亿 | 半导体 | -20.00% | 10.00 | 8.00 | 10.00 | 8.00 | 谨慎 | 下跌趋势(0分) |",
                    "| 4 | 明确跌停 | 688002 | 80.00亿 | 半导体 | -12.58% | 10.00 | 8.74 | 10.00 | 8.74 | 谨慎 | 跌停(0分) |",
                ]
            ),
            title="图表日报",
            trade_date="2026-07-23",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)
        items_by_code = {str(item["code"]): item for item in payload["turnover_top30"]["items"]}

        self.assertEqual(items_by_code["688347"]["status"], "大幅回撤")
        self.assertEqual(items_by_code["002432"]["status"], "跌停")
        self.assertEqual(items_by_code["688001"]["status"], "跌停")
        self.assertEqual(items_by_code["688002"]["status"], "跌停")

    def test_render_splits_market_turnover_and_top50_share_into_separate_charts(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 1. 指数与市场底色",
                    "> 近25个交易日Top50成交额占比趋势。",
                    "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |",
                    "|------|-----------|------|--------|-------------|------------|",
                    "| 2026-06-09 | 21.86% | 资金活跃期 | +0.75pct | 5828.45亿 | 26667.33亿 |",
                    "| 2026-06-08 | 21.11% | 资金活跃期 | -2.17pct | 5958.98亿 | 28234.29亿 |",
                    "",
                    "### 4. 创新高趋势反馈",
                    "",
                    "| 日期 | 新高数 | 全A占比 | 趋势信号 | 较前日 | 主导板块 |",
                    "|------|--------|---------|----------|--------|----------|",
                    "| 2026-06-09 | 82 | 1.64% | 趋势扩散偏冷 | +24 | 元器件 |",
                    "| 2026-06-08 | 58 | 1.16% | 趋势扩散偏冷 | -5 | 半导体 |",
                    "",
                    "### 附录：七、龙虎榜结果",
                    "",
                    "#### 附录：净买入结果",
                    "| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 涨停状态 | 蜡烛图形态 |",
                    "|------|------|------|-----------|----------|--------|----------|------------|",
                    "| 1 | 英维克 | 002837 | 8.01亿 | 专用机械 | +10.00% | 涨停 | 光头大阳柱涨停(4分) |",
                    "| 2 | 科泰电源 | 300153 | 0.35亿 | 电源设备 | +3.21% | 正常 | 震荡上行(2分) |",
                    "",
                    "#### 附录：净流出结果",
                    "| 排名 | 股票 | 代码 | 净流出(亿) | 所属板块 | 涨跌幅 | 涨停状态 | 蜡烛图形态 |",
                    "|------|------|------|-----------|----------|--------|----------|------------|",
                    "| 1 | 北玻股份 | 002613 | 2.31亿 | 专用机械 | -4.95% | 正常 | 下跌趋势(0分) |",
                    "| 2 | 华映科技 | 000536 | 0.12亿 | 面板 | -1.02% | 正常 | 弱势整理(1分) |",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-09",
            chinext_index_trend={
                "schema": "chinext_index_trend.v1",
                "items": [
                    {"date": "2026-06-09", "close": 2218.55},
                    {"date": "2026-06-10", "close": 2230.00},
                ],
            },
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="market_turnover_trend"', html)
        self.assertIn('data-bear-chart="top50_share_trend"', html)
        self.assertNotIn('data-bear-chart="market_turnover_top50_trend"', html)
        self.assertIn("两市成交额趋势", html)
        self.assertIn("Top50成交占比与创业板指趋势", html)
        self.assertIn("双轴比较头部成交集中度与创业板指数走势。", html)
        self.assertIn('aria-label="Top50成交占比与创业板指趋势"', html)
        self.assertNotIn("两市成交额 + Top50占比", html)
        self.assertIn('data-bear-chart="new_high_share_trend"', html)
        self.assertIn('data-bear-chart="lhb_net_flow"', html)
        self.assertIn("renderMarketTurnoverTrendChart", html)
        self.assertIn("renderTop50ShareTrendChart", html)
        self.assertNotIn("renderMarketTurnoverTop50TrendChart", html)
        self.assertIn("renderNewHighShareTrendChart", html)
        self.assertIn("renderLhbNetFlowChart", html)
        self.assertIn('formatter: (value) => value === 0 ? "" : `${Math.abs(value)}亿`', html)
        self.assertIn("创新高全A占比", html)
        self.assertIn("item.new_high_share_pct", html)
        market_turnover_renderer = html.split("const renderMarketTurnoverTrendChart", 1)[1].split(
            "const renderTop50ShareTrendChart", 1
        )[0]
        top50_share_renderer = html.split("const renderTop50ShareTrendChart", 1)[1].split(
            "const renderNewHighShareTrendChart", 1
        )[0]
        new_high_share_renderer = html.split("const renderNewHighShareTrendChart", 1)[1].split(
            "const renderSectorCycleSwimlaneChart", 1
        )[0]
        self.assertIn('name: "两市成交额"', market_turnover_renderer)
        self.assertEqual(market_turnover_renderer.count('type: "bar"'), 1)
        self.assertNotIn('type: "line"', market_turnover_renderer)
        self.assertIn("markLine:", market_turnover_renderer)
        self.assertIn("min: 0", market_turnover_renderer)
        self.assertIn(
            "max: (value) => Math.max(40000, Math.ceil(value.max / 5000) * 5000)",
            market_turnover_renderer,
        )
        self.assertEqual(
            re.findall(r'yAxis: (15000|20000|25000|30000|35000),\s+name: "([^"]+)"', market_turnover_renderer),
            [
                ("15000", "1.5万亿以下"),
                ("20000", "2万亿以下"),
                ("25000", "2.5万亿以下"),
                ("30000", "3万亿以下"),
                ("35000", "3.5万亿以上·极致沸点"),
            ],
        )
        self.assertIn("lineStyle: { color: chartTone.extremeRed, width: 1.6, opacity: 1 }", market_turnover_renderer)
        self.assertNotIn("极致沸点", top50_share_renderer)
        self.assertNotIn("top50_share_pct", market_turnover_renderer)
        self.assertNotIn('name: "Top50占比"', market_turnover_renderer)
        self.assertIn('name: "Top50占比"', top50_share_renderer)
        self.assertIn('name: "创业板指"', top50_share_renderer)
        self.assertIn('data: ["Top50占比", "创业板指"]', top50_share_renderer)
        self.assertIn('name: "占比"', top50_share_renderer)
        self.assertIn('name: "创业板指"', top50_share_renderer)
        self.assertIn("yAxisIndex: 1", top50_share_renderer)
        self.assertEqual(top50_share_renderer.count('type: "line"'), 2)
        self.assertNotIn('type: "bar"', top50_share_renderer)
        self.assertIn("top50_share_pct", top50_share_renderer)
        self.assertIn("chinext_close", top50_share_renderer)
        self.assertNotIn("total_turnover", top50_share_renderer)
        self.assertNotIn('name: "两市成交额"', top50_share_renderer)
        self.assertNotIn("创新高全A占比", market_turnover_renderer)
        self.assertNotIn("new_high_share_pct", market_turnover_renderer)
        self.assertRegex(new_high_share_renderer, r'name: "创新高全A占比",\s+type: "line"')
        self.assertRegex(new_high_share_renderer, r'type: "line",\s+z: 10')
        self.assertIn("payload?.thresholds?.mark_lines", new_high_share_renderer)
        self.assertIn("thresholdTone[line.tone]", new_high_share_renderer)
        self.assertIn("extreme: { color: chartTone.extremeRed", new_high_share_renderer)
        self.assertIn("cold: { color: chartTone.iceBlue", new_high_share_renderer)
        self.assertIn("fracture: { color: chartTone.deepIceBlue", new_high_share_renderer)
        self.assertNotIn('name: "2% 冰点"', new_high_share_renderer)
        self.assertNotIn('name: "1%以下 极冰"', new_high_share_renderer)
        self.assertIn("formatPct(item.new_high_share_pct)", new_high_share_renderer)
        self.assertIn('formatter: (value) => `${value}%`', new_high_share_renderer)
        self.assertIn('symbol: "circle"', html)
        self.assertIn("showSymbol: false", html)
        self.assertIn('--signal-fluorescent-purple: #B000FF;', html)
        self.assertIn('fluorescentPurple: cssValue("--signal-fluorescent-purple", "#B000FF")', html)
        self.assertIn(
            "lineStyle: { width: 2.2, color: chartTone.fluorescentPurple, opacity: 1 }",
            new_high_share_renderer,
        )
        self.assertIn("color: [chartTone.fluorescentPurple]", new_high_share_renderer)
        self.assertIn("itemStyle: { color: chartTone.fluorescentPurple }", new_high_share_renderer)
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][0]["date"], "2026-06-08")
        self.assertNotIn("new_high_share_pct", payload["market_turnover_top50_trend"]["items"][0])
        self.assertIsNone(payload["market_turnover_top50_trend"]["items"][0]["chinext_close"])
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][1]["top50_share_pct"], 21.86)
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][1]["total_turnover"], 26667.33)
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][1]["chinext_close"], 2218.55)
        self.assertEqual(payload["market_turnover_top50_trend"]["chinext_available_count"], 1)
        self.assertEqual(payload["new_high_share_trend"]["items"][0]["date"], "2026-06-08")
        self.assertEqual(payload["new_high_share_trend"]["items"][0]["new_high_count"], 58)
        self.assertEqual(payload["new_high_share_trend"]["items"][0]["new_high_share_pct"], 1.16)
        self.assertEqual(payload["new_high_share_trend"]["items"][1]["date"], "2026-06-09")
        self.assertEqual(payload["new_high_share_trend"]["items"][1]["new_high_share_pct"], 1.64)
        self.assertEqual(
            [(item["value"], item["label"]) for item in payload["new_high_share_trend"]["thresholds"]["mark_lines"]],
            [
                (5.0, "5% 极致扩散线"),
                (2.0, "2% 有效扩散分界"),
                (1.0, "1% 极低扩散分界"),
                (0.2, "0.2% 断层观察线"),
            ],
        )
        self.assertIn("0.2%到1%为极低扩散", payload["new_high_share_trend"]["subtitle"])
        self.assertEqual(payload["lhb_net_flow"]["items"][0]["name"], "英维克")
        self.assertEqual(payload["lhb_net_flow"]["items"][0]["amount"], 8.01)
        self.assertEqual(payload["lhb_net_flow"]["items"][1]["name"], "科泰电源")
        self.assertEqual(payload["lhb_net_flow"]["items"][1]["amount"], 0.35)
        self.assertEqual(payload["lhb_net_flow"]["items"][2]["name"], "华映科技")
        self.assertEqual(payload["lhb_net_flow"]["items"][2]["amount"], -0.12)
        self.assertEqual(payload["lhb_net_flow"]["items"][3]["name"], "北玻股份")
        self.assertEqual(payload["lhb_net_flow"]["items"][3]["amount"], -2.31)

    def test_render_top50_share_chart_keeps_original_payload_without_chinext_history(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 1. 指数与市场底色",
                    "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |",
                    "|------|-----------|------|--------|-------------|------------|",
                    "| 2026-06-09 | 21.86% | 资金活跃期 | +0.75pct | 5828.45亿 | 26667.33亿 |",
                ]
            ),
            trade_date="2026-06-09",
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        payload = json.loads(payload_text)
        chart_payload = payload["market_turnover_top50_trend"]

        self.assertNotIn("chinext_available_count", chart_payload)
        self.assertNotIn("chinext_close", chart_payload["items"][0])
        self.assertIn('data-bear-chart="top50_share_trend"', html)
        self.assertIn("Top50成交占比趋势", html)
        self.assertIn("折线只看头部成交集中度。", html)
        self.assertIn('aria-label="Top50成交占比趋势"', html)
        self.assertNotIn("Top50成交占比与创业板指趋势", html)

    def test_render_adds_cffex_position_trend_with_separate_panels(self):
        evidence = _cffex_position_evidence(item_count=60, null_index=10)
        before = copy.deepcopy(evidence)
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "## 明日执行结论",
                    "",
                    "保持观察。",
                    "",
                    "## 股指期货持仓结构（研究证据）",
                    "",
                    "| 口径 | 多头日变 | 空头日变 | 净空变化 |",
                    "|------|---------:|---------:|---------:|",
                    "| 中信期货代客会员汇总 | +15161 | +18291 | +3130 |",
                ]
            ),
            trade_date="2026-08-19",
            cffex_index_futures_position_evidence=evidence,
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        chart_payload = json.loads(payload_text)["cffex_position_trend"]
        items = chart_payload["items"]

        self.assertEqual(evidence, before)
        self.assertEqual(chart_payload["schema"], "cffex_position_trend.v1")
        self.assertEqual(chart_payload["target_date"], "2026-08-19")
        self.assertEqual(chart_payload["max_window"], 60)
        self.assertEqual(len(items), 60)
        self.assertEqual(items[0]["date"], "2026-06-21")
        self.assertEqual(items[-1]["date"], "2026-08-19")
        self.assertEqual(items[0]["member_net_short_notional_yi"], 800.0)
        self.assertIsNone(items[10]["member_net_short_notional_yi"])
        self.assertIsNone(items[10]["member_net_short_change"])
        self.assertIsNone(items[10]["top20_cross_section_net_short"])
        self.assertIsNone(items[10]["top20_cross_section_change"])
        self.assertIsNone(items[11]["top20_cross_section_change"])
        self.assertEqual(items[12]["top20_cross_section_change"], 250.0)

        self.assertEqual(html.count('data-bear-chart="cffex_position_trend"'), 1)
        self.assertEqual(html.count('data-bear-chart-card="cffex_position_trend"'), 1)
        self.assertIn('data-bear-chart-window-control="cffex_position_trend"', html)
        heading_index = html.index('id="股指期货持仓结构研究证据"')
        chart_index = html.index('data-bear-chart-card="cffex_position_trend"')
        table_index = html.index("<table", heading_index)
        self.assertLess(heading_index, chart_index)
        self.assertLess(chart_index, table_index)


    def test_futures_windows_slice_values_tooltips_gaps_and_preserve_legend(self):
        html = (ROOT / 'scripts/templates/daily_report_markdown_reader.html').read_text()
        for count in (7, 30, 75):
            items = [{'date': (date(2026, 7, 1) + timedelta(days=i)).isoformat(),
                      'member_net_short_notional_yi': None if i == count - 4 else 800 + i,
                      'member_net_short_change': None if i == count - 4 else i,
                      'top20_cross_section_net_short': None if i == count - 4 else 1000 + i}
                     for i in range(count)]
            payload = {'items': items, 'default_window': 20, 'target_date': items[-1]['date']}
            before = copy.deepcopy(payload)
            states = cffex_chart_states(html, payload)
            for state, size in zip(states, (60, 20, 60)):
                visible = items[-size:]
                option = state['option']
                self.assertFalse(option.get('dataZoom'))
                self.assertEqual(state['events'], [])
                self.assertEqual(state['pressed'], ['true', 'false'] if size == 20 else ['false', 'true'])
                for axis in option['xAxis']:
                    self.assertEqual(axis['data'], [item['date'] for item in visible])
                for series, key in zip(option['series'], ('member_net_short_notional_yi', 'member_net_short_change', 'top20_cross_section_net_short')):
                    self.assertEqual(series['data'], [item[key] for item in visible])
                self.assertFalse(option['series'][0]['connectNulls'])
                self.assertFalse(option['series'][2]['connectNulls'])
                self.assertIn(visible[0]['date'], state['tooltip'])
                self.assertIn(str(visible[0]['member_net_short_notional_yi']), state['tooltip'])
                self.assertIn('目标日', state['lastTooltip'])
                self.assertEqual(option['series'][0]['markLine']['data'][0]['xAxis'], items[-1]['date'])
            self.assertEqual(states[1]['option']['legend']['selected'], states[2]['option']['legend']['selected'])
            self.assertFalse(states[2]['option']['legend']['selected']['中信名义净空'])
            self.assertEqual(payload, before)

    def test_render_omits_cffex_position_trend_for_invalid_or_empty_payload(self):
        markdown = "\n".join(
            [
                "# 图表日报",
                "",
                "## 股指期货持仓结构（研究证据）",
                "",
                "事实不足。",
            ]
        )
        wrong_date = _cffex_position_evidence(target_date="2026-08-18", item_count=1)
        empty = _cffex_position_evidence(item_count=1, null_index=0)

        for evidence in (wrong_date, empty):
            with self.subTest(evidence=evidence):
                html = render_markdown_report_html(
                    markdown,
                    trade_date="2026-08-19",
                    cffex_index_futures_position_evidence=evidence,
                )
                payload_text = re.search(
                    r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                    html,
                ).group(1)
                self.assertNotIn("cffex_position_trend", json.loads(payload_text))
                self.assertNotIn('data-bear-chart="cffex_position_trend"', html)

    def test_render_cffex_position_trend_excludes_future_rows_without_padding(self):
        evidence = _cffex_position_evidence(
            item_count=60,
            include_future=True,
            null_index=8,
        )
        html = render_markdown_report_html(
            "# 图表日报\n\n## 股指期货持仓结构（研究证据）\n\n事实表保留。",
            trade_date="2026-08-19",
            cffex_index_futures_position_evidence=evidence,
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        items = json.loads(payload_text)["cffex_position_trend"]["items"]

        self.assertEqual(len(items), 59)
        self.assertEqual(items[-1]["date"], "2026-08-19")
        self.assertNotIn("2026-08-20", [item["date"] for item in items])
        self.assertTrue(any(item["member_net_short_change"] is None for item in items))

    def test_render_adds_recent_25_day_t0_market_breadth_chart_after_heading(self):
        raw_items = [
            {
                "date": f"2026-06-{day:02d}",
                "up_count": None if day == 2 else 2500 + day,
                "down_count": None if day == 2 else 2400 - day,
                "all_a_change_pct": None if day == 2 else day / 100,
                "new_high_share_pct": None if day == 2 else day / 10,
            }
            for day in range(1, 28)
        ]
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 指数与市场底色补充",
                    "",
                    "这里只是补充标题，不应插入图卡。",
                    "",
                    "### 1. 指数与市场底色",
                    "",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    "| 原始事实 | 保留 |",
                    "",
                    "### 指数与市场底色",
                    "",
                    "重复正式标题不应再次插入图卡。",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-26",
            t0_market_breadth={"items": list(reversed(raw_items))},
        )
        payload_text = re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
            html,
        ).group(1)
        payload = json.loads(payload_text)
        items = payload["t0_market_breadth"]["items"]

        self.assertEqual(html.count('data-bear-chart="t0_market_breadth"'), 1)
        self.assertEqual(len(items), 25)
        self.assertEqual([item["date"] for item in items], [f"2026-06-{day:02d}" for day in range(2, 27)])
        self.assertNotIn("2026-06-27", [item["date"] for item in items])
        self.assertIsNone(items[0]["up_count"])
        self.assertIsNone(items[0]["down_count"])
        self.assertIsNone(items[0]["all_a_change_pct"])
        self.assertIsNone(items[0]["new_high_share_pct"])

        supplemental_heading_index = html.index("指数与市场底色补充")
        heading_index = html.index('id="1-指数与市场底色"')
        chart_index = html.index('data-bear-chart-card="t0_market_breadth"')
        fact_table_index = html.index("<table", heading_index)
        self.assertLess(supplemental_heading_index, heading_index)
        self.assertLess(heading_index, chart_index)
        self.assertLess(chart_index, fact_table_index)
        self.assertIn('aria-label="T0市场底色"', html)


    def test_market_breadth_marks_only_declines_over_5000_in_purple(self):
        if not shutil.which('node'):
            self.skipTest('chart behavior checks require node')
        counts = [0, 4999, 5000, 5001, 5108, None]
        payload = {'items': [dict(date=f'2026-10-{day:02d}', up_count=300, down_count=count)
                             for day, count in enumerate(counts, 10)]}
        before = copy.deepcopy(payload)
        html = render_markdown_report_html(
            '# 日报\n\n### 指数与市场底色\n', trade_date='2026-10-15', t0_market_breadth=payload)
        frozen = json.loads(re.search(
            r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1))
        helpers = html[html.index('const escapeText ='):html.index('const renderMarketStructureChart =')]
        renderer = html[html.index('const baseChartOption ='):html.index('const renderCffexPositionTrendChart =')]
        script = r'''
const fs=require('fs'),vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
let option;
global.document={documentElement:{}};
global.getComputedStyle=()=>({getPropertyValue:()=>''});
global.window={echarts:{init:()=>({setOption(value){option=value;}})}};
global.payload=input.payload;
vm.runInThisContext(input.code+'\nrenderT0MarketBreadthChart({},globalThis.payload);');
const down=option.series.find(s=>s.name==='下跌家数');
const colors=down.data.map((value,dataIndex)=>typeof down.itemStyle.color==='function'
  ? down.itemStyle.color({value,dataIndex}) : down.itemStyle.color||option.color[1]);
process.stdout.write(JSON.stringify({data:down.data,colors,
  minimum:option.yAxis[0].min({min:-4200}),
  lines:down.markLine.data.map(line=>({value:line.yAxis,
    color:line.lineStyle?.color||down.markLine.lineStyle.color})),
  tooltip:option.tooltip.formatter([{dataIndex:4}]),
  missingTooltip:option.tooltip.formatter([{dataIndex:5}])}));
'''
        result = subprocess.run(['node', '-e', script], input=json.dumps({
            'code': helpers + renderer, 'payload': frozen['t0_market_breadth']}),
            text=True, capture_output=True, check=True)
        chart = json.loads(result.stdout)
        self.assertEqual(chart['data'], [0, -4999, -5000, -5001, -5108, None])
        self.assertEqual(chart['colors'], ['#07C160'] * 3 + ['#B000FF'] * 2 + ['#07C160'])
        self.assertEqual(chart['lines'], [dict(value=-4000, color='#07C160'),
                                         dict(value=-5000, color='#B000FF')])
        self.assertLess(chart['minimum'], -5000)
        self.assertIn('5108家', chart['tooltip'])
        self.assertIn('下跌家数：未记录', chart['missingTooltip'])
        self.assertEqual(payload, before)

    def test_render_adds_new_high_share_chart_without_top50_table(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 创新高趋势反馈",
                    "",
                    "| 日期 | 新高数 | 全A占比 | 趋势信号 | 较前日 | 主导板块 |",
                    "|------|--------|---------|----------|--------|----------|",
                    "| 2026-06-09 | 250 | 5.00% | 极致扩散 | +150 | 半导体 |",
                    "| 2026-06-08 | 100 | 2.00% | 有效扩散 | +55 | 元器件 |",
                    "| 2026-06-05 | 45 | 0.90% | 极低扩散 | -10 | 通信设备 |",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-09",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="new_high_share_trend"', html)
        self.assertEqual(html.count('data-bear-chart="new_high_share_trend"'), 1)
        self.assertNotIn('data-bear-chart="market_turnover_top50_trend"', html)
        self.assertNotIn("market_turnover_top50_trend", payload)
        self.assertEqual(
            [item["new_high_share_pct"] for item in payload["new_high_share_trend"]["items"]],
            [0.9, 2.0, 5.0],
        )

    def test_render_skips_lhb_net_flow_chart_when_amounts_are_zero(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 附录：七、龙虎榜结果",
                    "",
                    "#### 附录：净买入结果",
                    "| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 涨停状态 | 蜡烛图形态 |",
                    "|------|------|------|-----------|----------|--------|----------|------------|",
                    "| 1 | 云创退 | 920305 | 0.00亿 | 待补充板块 | -80.67% | 跌停 | 下跌趋势(0分) |",
                    "| 2 | 新睿电子 | 920211 | 0.00亿 | 待补充板块 | +0.00% | 正常 | 震荡整理(0分) |",
                    "",
                    "#### 附录：净流出结果",
                    "| 排名 | 股票 | 代码 | 净流出(亿) | 所属板块 | 涨跌幅 | 涨停状态 | 蜡烛图形态 |",
                    "|------|------|------|-----------|----------|--------|----------|------------|",
                    "| 1 | 云创退 | 920305 | 0.00亿 | 待补充板块 | -80.67% | 跌停 | 下跌趋势(0分) |",
                    "| 2 | 新睿电子 | 920211 | 0.00亿 | 待补充板块 | +0.00% | 正常 | 震荡整理(0分) |",
                ]
            ),
            title="图表日报",
            trade_date="2026-07-09",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertNotIn("lhb_net_flow", payload)
        self.assertNotIn('data-bear-chart="lhb_net_flow"', html)
        self.assertNotIn("龙虎榜净额表态", html)

    def test_render_adds_bear_echarts_for_board_tag_rank_bar(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 附录：十一、板块标签分析",
                    "",
                    "#### 附录：标签热度排行榜",
                    "> 按标签出现次数排序。",
                    "",
                    "| 排名 | 标签 | 出现次数 | 全标签占比 | 热度条 |",
                    "|------|------|----------|----------|--------|",
                    "| 1 | 光纤概念 | 9 | 8.3% | `####################` |",
                    "| 2 | PCB概念 | 7 | 6.5% | `################` |",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-11",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="board_tag_rank_bar"', html)
        self.assertIn("renderBoardTagRankBarChart", html)
        self.assertNotIn('type: "treemap"', html)
        self.assertNotIn("<th>热度条</th>", html)
        self.assertNotIn("####################", html)
        self.assertEqual(payload["board_tag_rank_bar"]["items"][0]["tag"], "光纤概念")
        self.assertEqual(payload["board_tag_rank_bar"]["items"][0]["count"], 9)
        self.assertEqual(payload["board_tag_rank_bar"]["items"][0]["share_pct"], 8.3)

    def test_render_adds_bear_echarts_for_t100_board_tag_rank_table(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "**T-100**",
                    "| 排名 | 标签 | 出现次数 | 全标签占比 | 热度条 |",
                    "|------|------|----------|----------|--------|",
                    "| 1 | 存储芯片 | 8 | 7.8% | `####################` |",
                    "| 2 | 共封装光学(CPO) | 7 | 6.8% | `##################` |",
                ]
            ),
            title="图表日报",
            trade_date="2026-07-03",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="board_tag_rank_bar"', html)
        self.assertIn("renderBoardTagRankBarChart", html)
        self.assertNotIn("<th>热度条</th>", html)
        self.assertNotIn("####################", html)
        self.assertEqual(payload["board_tag_rank_bar"]["items"][0]["tag"], "存储芯片")
        self.assertEqual(payload["board_tag_rank_bar"]["items"][0]["count"], 8)
        self.assertEqual(payload["board_tag_rank_bar"]["items"][0]["share_pct"], 7.8)

    def test_render_keeps_unscoped_board_like_table_as_plain_table(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "## 普通统计表",
                    "| 排名 | 标签 | 出现次数 | 全标签占比 | 热度条 |",
                    "|------|------|----------|----------|--------|",
                    "| 1 | 样本标签 | 8 | 7.8% | `####################` |",
                ]
            ),
            title="图表日报",
            trade_date="2026-07-03",
        )

        self.assertNotIn('data-bear-chart="board_tag_rank_bar"', html)
        self.assertIn("<th>热度条</th>", html)
        self.assertIn("####################", html)

    def test_render_adds_bear_echarts_for_intraday_feedback_review(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 盘面反馈复盘",
                    "账户结论：1x/50%半仓；旧仓弱于指数，优先释放资金。",
                    "",
                    "#### 盘面反馈分时点",
                    "| 时间 | 对象 | 代码 | 角色 | 涨跌幅 | 相对上证 |",
                    "|------|------|------|------|--------|----------|",
                    "| 09:31 | 上证指数 | 000001 | 上证指数 | -0.20% | 0.00% |",
                    "| 09:31 | 太极实业 | 600667 | 当前持仓 | -4.52% | -4.32% |",
                    "| 09:31 | 长电科技 | 600584 | 昨日目标 | +1.40% | +1.60% |",
                    "| 09:31 | 长电科技 | 600584 | 今日买入 | +1.40% | +1.60% |",
                    "| 09:48 | 上证指数 | 000001 | 上证指数 | -0.38% | 0.00% |",
                    "| 09:48 | 太极实业 | 600667 | 当前持仓 | -6.10% | -5.72% |",
                    "| 09:48 | 长电科技 | 600584 | 今日买入 | +2.10% | +2.48% |",
                    "",
                    "#### 盘面反馈事件",
                    "| 时间 | 对象 | 事件 | 价格 | 说明 |",
                    "|------|------|------|------|------|",
                    "| 09:48 | 太极实业 | 跌破昨低 | 21.40 | 旧仓失效 |",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-23",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)
        review_payload = payload["intraday_feedback_review"]
        series_keys = {item["series_key"] for item in review_payload["items"]}

        self.assertIn('data-bear-chart="intraday_feedback_review"', html)
        self.assertIn("renderIntradayFeedbackReviewChart", html)
        self.assertIn("markPoint", html)
        self.assertIn("1x/50%半仓；旧仓弱于指数，优先释放资金。", html)
        self.assertNotIn("各50%", html)
        self.assertEqual(series_keys, {"上证指数", "600667", "600584"})
        self.assertEqual(
            [item for item in review_payload["items"] if item["series_key"] == "600584"][0]["role"],
            "昨日目标 / 今日买入",
        )
        self.assertEqual(len([item for item in review_payload["items"] if item["series_key"] == "600584"]), 2)
        self.assertEqual(review_payload["events"][0]["event"], "跌破昨低")
        self.assertEqual(review_payload["account_conclusion"], "1x/50%半仓；旧仓弱于指数，优先释放资金。")

    def test_render_omits_intraday_feedback_chart_without_valid_points(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 盘面反馈复盘",
                    "账户结论：2x/100%满仓；这里还没有分时事实。",
                    "",
                    "| 时间 | 对象 | 事件 | 价格 | 说明 |",
                    "|------|------|------|------|------|",
                    "| 09:48 | 太极实业 | 跌破昨低 | 21.40 | 旧仓失效 |",
                ]
            ),
            title="图表日报",
            trade_date="2026-06-23",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertNotIn('data-bear-chart="intraday_feedback_review"', html)
        self.assertNotIn("intraday_feedback_review", payload)

    def test_render_marks_etf_turnover_only_at_extreme_boundaries(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# ETF阈值",
                    "",
                    "| 日期 | ETF两市成交额 |",
                    "|------|----------------|",
                    "| 2026-06-01 | 4499.99亿 |",
                    "| 2026-06-02 | 4500.00亿 |",
                    "| 2026-06-03 | 5000.00亿 |",
                    "| 2026-06-04 | 5500.00亿 |",
                    "| 2026-06-05 | 5500.01亿 |",
                ]
            ),
            title="ETF阈值",
            trade_date="2026-06-05",
        )

        self.assertIn(
            '<td class="has-signal"><span class="signal-marker signal-cold">4499.99亿</span></td>',
            html,
        )
        self.assertIn("<td>4500.00亿</td>", html)
        self.assertIn("<td>5000.00亿</td>", html)
        self.assertIn("<td>5500.00亿</td>", html)
        self.assertIn(
            '<td class="has-signal"><span class="signal-marker signal-hot">5500.01亿</span></td>',
            html,
        )

    def test_render_marks_heat_core_change_column_from_limit_pools_only(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "### 附录：四、热度核心结果",
                    "| 排名 | 股票 | 代码 | 热度分(w) | 所属板块 | 涨跌幅 | 收盘价 |",
                    "|------|------|------|-----------|----------|--------|--------|",
                    "| 1 | 大有能源 | 600403 | 1548.6w | 煤炭开采 | +10.00% | 8.14 |",
                    "| 2 | 华电能源 | 600726 | 1880.5w | 电力 | -10.01% | 9.35 |",
                    "| 3 | 兆易创新 | 603986 | 1313.2w | 存储芯片 | -7.80% | 488.00 |",
                    "",
                    "### 附录：五、成交核心结果",
                    "| 排名 | 股票 | 代码 | 涨跌幅 |",
                    "|------|------|------|--------|",
                    "| 1 | 大有能源 | 600403 | +10.00% |",
                    "",
                    "### 附录：九、连板结果",
                    "| 股票 | 代码 | 所属板块 | 涨跌幅 |",
                    "|------|------|----------|--------|",
                    "| 大有能源 | 600403 | 煤炭开采 | +10.00% |",
                    "",
                    "### 附录：跌停池结果",
                    "| 股票 | 代码 | 所属板块 | 涨跌幅 |",
                    "|------|------|----------|--------|",
                    "| 华电能源 | 600726 | 电力 | -10.01% |",
                ]
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">大有能源</code></td><td><code class=\"stock-ref\">600403</code></td><td>1548.6w</td><td>煤炭开采</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">+10.00%</span></td><td>8.14</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">华电能源</code></td><td><code class=\"stock-ref\">600726</code></td><td>1880.5w</td><td>电力</td>"
            '<td class="has-signal"><span class="signal-marker signal-cold">-10.01%</span></td><td>9.35</td></tr>',
            html,
        )
        self.assertIn("<td>-7.80%</td><td>488.00</td>", html)
        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">大有能源</code></td><td><code class=\"stock-ref\">600403</code></td><td>+10.00%</td></tr>",
            html,
        )

    def test_heat_core_limit_signal_ignores_status_columns_outside_limit_pools(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "### 附录：四、热度核心结果",
                    "| 排名 | 股票 | 代码 | 热度分(w) | 所属板块 | 涨跌幅 | 收盘价 | 连板标签 |",
                    "|------|------|------|-----------|----------|--------|--------|----------|",
                    "| 1 | 绿的谐波 | 688017 | 1397.5w | 自动化设 | +20.00% | 393.00 | 首板涨停 |",
                    "| 2 | 麦捷科技 | 300319 | 907.3w | 东数西算/算力 | +14.43% | 22.28 |  |",
                    "| 3 | 未入池样本 | 301111 | 800.0w | 测试板块 | +20.00% | 20.00 |  |",
                    "| 4 | 否定样本 | 301112 | 700.0w | 测试板块 | +20.00% | 21.00 | 未涨停 |",
                    "| 5 | 金安国纪 | 002636 | 2407.7w | PCB概念 | +9.53% | 84.80 | 4天3板 |",
                    "| 6 | 有研新材 | 600206 | 1200.0w | 半导体 | +8.20% | 30.18 | 2天1板 |",
                    "",
                    "### 附录：资金流入个股TOP10",
                    "| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 涨停状态 |",
                    "|------|------|------|------------|----------|--------|----------|",
                    "| 1 | 麦捷科技 | 300319 | 8.80亿 | 元器件 | +14.43% | 涨停 |",
                    "",
                    "### 附录：九、首板结果",
                    "| 股票 | 代码 | 所属板块 | 涨跌幅 | 首次涨停 |",
                    "|------|------|----------|--------|----------|",
                    "| 绿的谐波 | 688017 | 自动化设 | +20.00% | 14:01:00 |",
                ]
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">绿的谐波</code></td><td><code class=\"stock-ref\">688017</code></td><td>1397.5w</td><td>自动化设</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">+20.00%</span></td><td>393.00</td><td>首板涨停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">麦捷科技</code></td><td><code class=\"stock-ref\">300319</code></td><td>907.3w</td><td>东数西算/算力</td>"
            "<td>+14.43%</td><td>22.28</td><td></td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>3</td><td><code class=\"stock-ref\">未入池样本</code></td><td><code class=\"stock-ref\">301111</code></td><td>800.0w</td><td>测试板块</td>"
            "<td>+20.00%</td><td>20.00</td><td></td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>4</td><td><code class=\"stock-ref\">否定样本</code></td><td><code class=\"stock-ref\">301112</code></td><td>700.0w</td><td>测试板块</td>"
            "<td>+20.00%</td><td>21.00</td><td>未涨停</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>5</td><td><code class=\"stock-ref\">金安国纪</code></td><td><code class=\"stock-ref\">002636</code></td><td>2407.7w</td><td>PCB概念</td>"
            "<td>+9.53%</td><td>84.80</td><td>4天3板</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>6</td><td><code class=\"stock-ref\">有研新材</code></td><td><code class=\"stock-ref\">600206</code></td><td>1200.0w</td><td>半导体</td>"
            "<td>+8.20%</td><td>30.18</td><td>2天1板</td></tr>",
            html,
        )

    def test_heat_core_change_column_uses_row_limit_label_when_pool_table_is_absent(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "### 附录：四、热度核心结果",
                    "| 排名 | 股票 | 代码 | 热度分(w) | 所属板块 | 涨跌幅 | 收盘价 | 连板标签 |",
                    "|------|------|------|-----------|----------|--------|--------|----------|",
                    "| 1 | 达实智能 | 002421 | 2766.1w | IT服务Ⅱ | -10.02% | 4.40 | 跌停 |",
                    "| 2 | 洛阳钼业 | 603993 | 1874.6w | 工业金属 | +10.02% | 19.11 | 首板涨停 |",
                    "| 3 | 未入池样本 | 301111 | 800.0w | 测试板块 | +20.00% | 20.00 |  |",
                    "| 4 | 否定样本 | 301112 | 700.0w | 测试板块 | +20.00% | 21.00 | 未涨停 |",
                    "| 5 | 旧涨停标签样本 | 603993 | 1874.6w | 工业金属 | +3.45% | 17.37 | 首板涨停 |",
                ]
            ),
            title="日报",
            trade_date="2026-06-12",
        )

        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">达实智能</code></td><td><code class=\"stock-ref\">002421</code></td><td>2766.1w</td><td>IT服务Ⅱ</td>"
            '<td class="has-signal"><span class="signal-marker signal-cold">-10.02%</span></td><td>4.40</td><td>跌停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">洛阳钼业</code></td><td><code class=\"stock-ref\">603993</code></td><td>1874.6w</td><td>工业金属</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">+10.02%</span></td><td>19.11</td><td>首板涨停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>3</td><td><code class=\"stock-ref\">未入池样本</code></td><td><code class=\"stock-ref\">301111</code></td><td>800.0w</td><td>测试板块</td>"
            "<td>+20.00%</td><td>20.00</td><td></td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>4</td><td><code class=\"stock-ref\">否定样本</code></td><td><code class=\"stock-ref\">301112</code></td><td>700.0w</td><td>测试板块</td>"
            "<td>+20.00%</td><td>21.00</td><td>未涨停</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>5</td><td><code class=\"stock-ref\">旧涨停标签样本</code></td><td><code class=\"stock-ref\">603993</code></td><td>1874.6w</td><td>工业金属</td>"
            "<td>+3.45%</td><td>17.37</td><td>首板涨停</td></tr>",
            html,
        )

    def _lhb_markdown(self) -> str:
        return "\n".join(
            [
                "# 日报",
                "",
                "### 附录：七、龙虎榜结果",
                "",
                "#### 附录：净买入结果",
                "| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 涨停状态 | 蜡烛图形态 |",
                "|------|------|------|------------|----------|--------|----------|------------|",
                "| 1 | 宗申动力 | 001696 | 1.55亿 | 摩托车 | +9.98% | 涨停 | 光头大阳柱涨停(4分) |",
                "| 2 | 天顺风能 | 002531 | 0.87亿 | 农业综合 | +9.94% | 涨停 | 光头大阳柱涨停(4分) |",
                "",
                "#### 附录：净流出结果",
                "| 排名 | 股票 | 代码 | 净流出(亿) | 所属板块 | 涨跌幅 | 涨停状态 | 蜡烛图形态 |",
                "|------|------|------|------------|----------|--------|----------|------------|",
                "| 1 | 瑞芯微 | 603893 | 5.87亿 | 农业综合 | -9.99% | 跌停 | 下跌趋势(0分) |",
                "| 2 | 涛涛车业 | 301345 | 1.64亿 | 农业综合 | -18.83% | 跌停 | 下跌趋势(0分) |",
                "| 3 | 宝鼎科技 | 002552 | 1.59亿 | 元器件 | -9.99% | 跌停 | 下跌趋势(0分) |",
                "| 4 | 吉大正元 | 003029 | 1.47亿 | 软件服务 | +10.01% | 涨停 | 光头大阳柱涨停(4分) |",
            ]
        )

    def test_lhb_limit_coloring_uses_frozen_target_day_codes_only(self):
        html = render_markdown_report_html(
            self._lhb_markdown(),
            title="日报",
            trade_date="2026-10-16",
            lhb_limit_status={
                "trade_date": "2026-10-16",
                "limit_up_codes": ["001696", "003029"],
                "limit_down_codes": ["002552"],
            },
        )

        self.assertIn('signal-marker signal-hot">+9.98%', _lhb_row_html(html, "001696"))
        self.assertIn('signal-marker signal-hot">+10.01%', _lhb_row_html(html, "003029"))
        self.assertIn('signal-marker signal-cold">-9.99%', _lhb_row_html(html, "002552"))
        for code, change in (("002531", "+9.94%"), ("603893", "-9.99%"), ("301345", "-18.83%")):
            row = _lhb_row_html(html, code)
            self.assertIn(f"<td>{change}</td>", row)
            self.assertNotIn("has-signal", row)
            self.assertNotIn("signal-marker", row)

        payload = json.loads(
            re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                html,
                re.S,
            ).group(1)
        )
        items = {item["code"]: item for item in payload["lhb_net_flow"]["items"]}
        self.assertEqual(
            [
                (items[code]["side"], items[code]["limit_status"], items[code]["status"], items[code]["amount"])
                for code in ("001696", "002531", "603893", "301345", "002552", "003029")
            ],
            [
                ("buy", "涨停", "涨停", 1.55),
                ("buy", "", "", 0.87),
                ("sell", "", "", -5.87),
                ("sell", "", "", -1.64),
                ("sell", "跌停", "跌停", -1.59),
                ("sell", "涨停", "涨停", -1.47),
            ],
        )

    def test_lhb_limit_coloring_is_absent_without_frozen_payload(self):
        html = render_markdown_report_html(
            self._lhb_markdown(),
            title="日报",
            trade_date="2026-10-16",
        )

        for code, label in (
            ("001696", "涨停"),
            ("002531", "涨停"),
            ("603893", "跌停"),
            ("301345", "跌停"),
            ("002552", "跌停"),
            ("003029", "涨停"),
        ):
            row = _lhb_row_html(html, code)
            self.assertIn(f"<td>{label}</td>", row)
            self.assertNotIn("has-signal", row)
            self.assertNotIn("signal-marker", row)
        payload = json.loads(
            re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                html,
                re.S,
            ).group(1)
        )
        for item in payload["lhb_net_flow"]["items"]:
            self.assertEqual(item["limit_status"], "")
            self.assertEqual(item["status"], "")

    def test_lhb_limit_coloring_is_absent_when_frozen_payload_date_differs(self):
        html = render_markdown_report_html(
            self._lhb_markdown(),
            title="日报",
            trade_date="2026-10-16",
            lhb_limit_status={
                "trade_date": "2026-10-15",
                "limit_up_codes": ["001696", "003029"],
                "limit_down_codes": ["002552"],
            },
        )

        for code in ("001696", "002552", "003029"):
            self.assertNotIn("has-signal", _lhb_row_html(html, code))
        payload = json.loads(
            re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                html,
                re.S,
            ).group(1)
        )
        for item in payload["lhb_net_flow"]["items"]:
            self.assertEqual(item["limit_status"], "")

    def test_lhb_limit_coloring_is_absent_when_frozen_payload_is_invalid(self):
        invalid_payloads = (
            "001696,003029",
            {},
            {"trade_date": "2026-10-16"},
            {"trade_date": "2026-10-16", "limit_up_codes": ["001696"], "limit_down_codes": None},
            {"trade_date": "2026-10-16", "limit_up_codes": "001696", "limit_down_codes": ["002552"]},
            {"trade_date": "2026-10-16", "limit_up_codes": [None], "limit_down_codes": ["002552"]},
            {"trade_date": "2026-10-16", "limit_up_codes": [""], "limit_down_codes": ["002552"]},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                html = render_markdown_report_html(
                    self._lhb_markdown(),
                    title="日报",
                    trade_date="2026-10-16",
                    lhb_limit_status=payload,
                )
                for code in ("001696", "002531", "603893", "301345", "002552", "003029"):
                    row = _lhb_row_html(html, code)
                    self.assertNotIn("has-signal", row)
                    self.assertNotIn("signal-marker", row)

    def test_lhb_limit_coloring_trims_frozen_codes_and_keeps_st_names(self):
        markdown = "\n".join(
            [
                "# 日报",
                "",
                "### 附录：净买入结果",
                "| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 涨停状态 |",
                "|------|------|------|------------|----------|--------|----------|",
                "| 1 | ST 宗申动力 | 001696.SZ | 1.55亿 | 摩托车 | +9.98% | 涨停 |",
                "| 2 | ST 兰生 | 600826 | 1.00亿 | 综合 | +9.99% | 涨停 |",
            ]
        )
        html = render_markdown_report_html(
            markdown,
            title="日报",
            trade_date="2026-10-16",
            lhb_limit_status={
                "trade_date": " 2026-10-16 ",
                "limit_up_codes": ["  001696.SZ  "],
                "limit_down_codes": [],
            },
        )

        self.assertIn('signal-marker signal-hot">+9.98%', _lhb_row_html(html, "001696.SZ"))
        self.assertNotIn("has-signal", _lhb_row_html(html, "600826"))
        payload = json.loads(
            re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                html,
                re.S,
            ).group(1)
        )
        items = {item["code"]: item for item in payload["lhb_net_flow"]["items"]}
        self.assertEqual(items["001696.SZ"]["name"], "ST 宗申动力")
        self.assertEqual(items["001696.SZ"]["limit_status"], "涨停")
        self.assertEqual(items["600826"]["name"], "ST 兰生")
        self.assertEqual(items["600826"]["limit_status"], "")

    def test_lhb_signal_strength_labels_never_infer_limit_identity(self):
        markdown = "\n".join(
            [
                "# 日报",
                "",
                "### 2. 龙虎榜结果",
                "| 股票 | 净买入(亿) | 资金性质 | 行为模式 | 近3日上榜 | 信号强度 |",
                "|------|-----------|----------|----------|-----------|----------|",
                "| 华工科技 | +16.99 | 龙虎榜净买入 | 光通信 | - | 涨停 |",
                "| 利通电子 | -4.09 | 龙虎榜净卖出 | 消费电子 | - | 跌停 |",
                "| 科士达 | +4.92 | 龙虎榜净买入 | 算力 | - | 正常 |",
            ]
        )
        html = render_markdown_report_html(
            markdown,
            title="日报",
            trade_date="2026-06-05",
            lhb_limit_status={
                "trade_date": "2026-06-05",
                "limit_up_codes": ["000988"],
                "limit_down_codes": ["603629"],
            },
        )

        self.assertIn(
            "<tr><td>华工科技</td><td>+16.99</td><td>龙虎榜净买入</td><td>光通信</td><td>-</td><td>涨停</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>利通电子</td><td>-4.09</td><td>龙虎榜净卖出</td><td>消费电子</td><td>-</td><td>跌停</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>科士达</td><td>+4.92</td><td>龙虎榜净买入</td><td>算力</td><td>-</td><td>正常</td></tr>",
            html,
        )
        table_rows = [
            line
            for line in html.splitlines()
            if any(f"<tr><td>{name}</td>" in line for name in ("华工科技", "利通电子", "科士达"))
        ]
        self.assertEqual(len(table_rows), 3)
        for row in table_rows:
            self.assertNotIn("signal-marker", row)

    def test_render_demotes_judgment_review_internal_headings_from_outline(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "## 判断纠偏与今日五项结论",
                    "### 近5个已结算交易日正确率（2026-05-29至2026-06-04）",
                    "| 判断项 | 正确率 |",
                    "|--------|--------|",
                    "| 市场状态判断 | 60.00% |",
                    "",
                    "### 结算上一交易日：2026-06-04",
                    "| 判断项 | 结论 |",
                    "|--------|------|",
                    "| 主线判断 | 正确 |",
                    "",
                    "### 今日判断（2026-06-05，等待下一交易日验证）",
                    "| 判断项 | 今日结论 |",
                    "|--------|----------|",
                    "| 核心候选判断 | 大有能源(600403) |",
                ]
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn('href="#判断纠偏与今日五项结论"', html)
        self.assertNotIn('href="#近5个已结算交易日正确率2026-05-29至2026-06-04"', html)
        self.assertNotIn('href="#结算上一交易日2026-06-04"', html)
        self.assertNotIn('href="#今日判断2026-06-05等待下一交易日验证"', html)
        self.assertIn("<p><strong>今日判断（2026-06-05，等待下一交易日验证）</strong></p>", html)

    def test_render_sanitizes_legacy_pseudo_precision_wording(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "| 层级 | 淘汰 | 留存 | 备注 |",
                    "|------|------|------|------|",
                    "| 周期概率窗口 | 1 | 0 | 概率窗口只作条件链合并判断，不输出精确胜率。 |",
                    "",
                    "### 近5个已结算交易日正确率（2026-06-04至2026-06-10）",
                    "| 判断项 | 正确率 |",
                    "|--------|--------|",
                    "| 市场状态判断 | 待补事实 |",
                    "",
                    "##### 附录：Step 5 - PK决胜局（期望值模型）",
                    "> **只看什么**：环境、主线、触发、可交易性和历史胜率收益。",
                    "",
                    "昨日涨停/连板/T字板已经被资金选择，次日冲高或再涨停概率高于普通上涨样本。",
                ]
            ),
            title="日报",
            trade_date="2026-06-12",
        )

        self.assertIn("周期窗口", html)
        self.assertIn("不输出精确预测", html)
        self.assertIn("近5个已结算交易日复盘表现", html)
        self.assertIn("过程候选最终复核", html)
        self.assertIn("历史复盘样本", html)
        self.assertIn("次日是否继续被资金承接需要窗口确认", html)
        self.assertNotIn("周期概率窗口", html)
        self.assertNotIn("正确率", html)
        self.assertNotIn("精确胜率", html)
        self.assertNotIn("期望值模型", html)
        self.assertNotIn("历史胜率收益", html)
        self.assertNotIn("概率高于普通上涨样本", html)

    def test_render_file_defaults_to_html_sibling(self):
        with TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "daily.md"
            source.write_text("# 标题\n\n## 二级\n正文", encoding="utf-8")

            output = render_markdown_report_file(source, title="标题", trade_date="2026-06-05")

            self.assertEqual(output, source.with_suffix(".html"))
            self.assertTrue(output.exists())
            self.assertIn("标题", output.read_text(encoding="utf-8"))

    def test_render_file_accepts_sector_three_axis_payload(self):
        with TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "daily.md"
            source.write_text(_sector_relative_path_markdown(), encoding="utf-8")

            output = render_markdown_report_file(
                source,
                trade_date="2026-08-14",
                sector_tournament_three_axis=_sector_relative_path_artifact(),
            )
            html = output.read_text(encoding="utf-8")
            payload_text = re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                html,
            ).group(1)

        self.assertEqual(
            json.loads(payload_text)["sector_cycle_swimlane"]["schema"],
            "sector_relative_path_swimlane.v2",
        )

    def test_render_file_cli_accepts_chinext_history_payload(self):
        with TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "daily.md"
            output = Path(tempdir) / "daily.html"
            payload_path = Path(tempdir) / "chinext.json"
            source.write_text(
                "\n".join(
                    [
                        "# 标题",
                        "",
                        "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |",
                        "|---|---:|---|---:|---:|---:|",
                        "| 2026-08-12 | 21.86% | 集中 | +0.75pct | 5828.45亿 | 26667.33亿 |",
                    ]
                ),
                encoding="utf-8",
            )
            payload_path.write_text(
                json.dumps(
                    {
                        "schema": "chinext_index_trend.v1",
                        "items": [{"date": "2026-08-12", "close": 3602.0835}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = render_markdown_report_main(
                [
                    str(source),
                    str(output),
                    "--trade-date",
                    "2026-08-12",
                    "--chinext-index-trend-json",
                    str(payload_path),
                ]
            )
            html = output.read_text(encoding="utf-8")
            payload_match = re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                html,
                re.S,
            )
            chart_payload = json.loads(payload_match.group(1))

        self.assertEqual(result, 0)
        self.assertEqual(
            chart_payload["market_turnover_top50_trend"]["items"][0]["chinext_close"],
            3602.0835,
        )
        self.assertIn('data-bear-chart="top50_share_trend"', html)

    def test_render_file_cli_accepts_sector_three_axis_payload(self):
        with TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "daily.md"
            output = Path(tempdir) / "daily.html"
            payload_path = Path(tempdir) / "sector-three-axis.json"
            source.write_text(_sector_relative_path_markdown(), encoding="utf-8")
            payload_path.write_text(
                json.dumps(_sector_relative_path_artifact(), ensure_ascii=False),
                encoding="utf-8",
            )

            result = render_markdown_report_main(
                [
                    str(source),
                    str(output),
                    "--trade-date",
                    "2026-08-14",
                    "--sector-tournament-three-axis-json",
                    str(payload_path),
                ]
            )
            html = output.read_text(encoding="utf-8")
            payload_text = re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                html,
            ).group(1)

        self.assertEqual(result, 0)
        self.assertEqual(
            json.loads(payload_text)["sector_cycle_swimlane"]["schema"],
            "sector_relative_path_swimlane.v2",
        )

    def test_render_file_cli_accepts_cffex_position_evidence_payload(self):
        with TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "daily.md"
            output = Path(tempdir) / "daily.html"
            payload_path = Path(tempdir) / "cffex.json"
            source.write_text(
                "# 标题\n\n## 股指期货持仓结构（研究证据）\n\n目标日事实表。",
                encoding="utf-8",
            )
            payload_path.write_text(
                json.dumps(_cffex_position_evidence(item_count=30), ensure_ascii=False),
                encoding="utf-8",
            )

            result = render_markdown_report_main(
                [
                    str(source),
                    str(output),
                    "--trade-date",
                    "2026-08-19",
                    "--cffex-position-evidence-json",
                    str(payload_path),
                ]
            )
            html = output.read_text(encoding="utf-8")
            payload_match = re.search(
                r'<script type="application/json" id="bear-chart-payload">(.*?)</script>',
                html,
                re.S,
            )
            chart_payload = json.loads(payload_match.group(1))["cffex_position_trend"]

        self.assertEqual(result, 0)
        self.assertEqual(len(chart_payload["items"]), 30)
        self.assertEqual(chart_payload["target_date"], "2026-08-19")
        self.assertIn('data-bear-chart="cffex_position_trend"', html)

    def test_render_file_cli_omits_cffex_chart_without_payload_argument(self):
        with TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "daily.md"
            output = Path(tempdir) / "daily.html"
            source.write_text(
                "# 标题\n\n## 股指期货持仓结构（研究证据）\n\n目标日事实表。",
                encoding="utf-8",
            )

            result = render_markdown_report_main(
                [
                    str(source),
                    str(output),
                    "--trade-date",
                    "2026-08-19",
                ]
            )
            html = output.read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertNotIn('data-bear-chart="cffex_position_trend"', html)

    def test_render_file_cli_rejects_invalid_cffex_position_evidence_payload(self):
        cases = (
            ("{broken", "中金所股指期货持仓结构载荷无法读取"),
            ("[]", "中金所股指期货持仓结构载荷必须是 JSON 对象"),
        )
        for payload_text, expected_error in cases:
            with self.subTest(payload_text=payload_text), TemporaryDirectory() as tempdir:
                source = Path(tempdir) / "daily.md"
                output = Path(tempdir) / "daily.html"
                payload_path = Path(tempdir) / "cffex.json"
                source.write_text("# 标题", encoding="utf-8")
                payload_path.write_text(payload_text, encoding="utf-8")
                stderr = io.StringIO()

                with patch("sys.stderr", stderr), self.assertRaises(SystemExit) as raised:
                    render_markdown_report_main(
                        [
                            str(source),
                            str(output),
                            "--trade-date",
                            "2026-08-19",
                            "--cffex-position-evidence-json",
                            str(payload_path),
                        ]
                    )

                self.assertEqual(raised.exception.code, 2)
                self.assertIn(expected_error, stderr.getvalue())

    def test_render_file_prepends_position_timeline_into_bear_html(self):
        timeline = "\n".join(
            [
                "| 轨道 | 标的 | 2026-06-26（周五） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |",
                "|------|------|------|------|------|------|",
                "| Ta旧仓 | 空仓 | Ta+0 空仓 | 空仓 | 空仓 | 空仓 |",
                "| Tb明日目标 | 空仓 | 空仓 | 没有Tb+0，空仓 | 没有Tb+1，空仓 | 空仓 |",
                "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 空仓 |",
                "",
                "- 顶部长时间轴按日报视角展示：第一列是报告日，下一交易日是执行日。",
            ]
        )
        with TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "daily.md"
            source.write_text("# 标题\n\n## 二级\n正文", encoding="utf-8")

            output = render_markdown_report_file(
                source,
                title="标题",
                trade_date="2026-06-26",
                prepend_markdown=timeline,
            )
            html = output.read_text(encoding="utf-8")

        body_index = html.index('<div class="markdown-body">')
        timeline_index = html.index('class="position-timeline-shell"', body_index)
        h1_index = html.index("<h1", body_index)
        self.assertLess(timeline_index, h1_index)
        self.assertIn('<span class="timeline-date-context">报告日</span>', html)
        self.assertIn('<span class="timeline-date-action">执行日</span>', html)

    def test_render_file_does_not_duplicate_existing_position_timeline(self):
        timeline = "\n".join(
            [
                "| 轨道 | 标的 | 2026-06-28（周日） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |",
                "|------|------|------|------|------|------|",
                "| Ta旧仓 | 太极实业(600667) | 上一份日报目标，进入旧仓/旧路径复核 | Ta+1 继续处理旧仓或取消路径 | Ta+2 默认按昨晚预案尾盘卖出；失去持有资格才提前处理 | 空仓 |",
                "| Tb明日目标 | 深科技(000021) | 空仓 | 报告日确认明日目标 | Tb+0 条件买入，不是无条件买入 | Tb+1 只按昨晚预案执行或取消 |",
                "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 下一份日报再复核 |",
            ]
        )
        with TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "daily.md"
            source.write_text(f"{timeline}\n\n# 标题\n正文", encoding="utf-8")

            output = render_markdown_report_file(
                source,
                title="标题",
                trade_date="2026-06-29",
                prepend_markdown=timeline,
            )
            html = output.read_text(encoding="utf-8")

        self.assertEqual(html.count('class="position-timeline-shell"'), 1)

    def test_render_file_embeds_echarts_for_standalone_first_open(self):
        with TemporaryDirectory(dir=ROOT) as tempdir:
            source = Path(tempdir) / "daily.md"
            source.write_text("# 标题\n\n| 日期 | Top50占比 | Top50成交额 | 两市成交额 |\n|---|---:|---:|---:|\n| 2026-06-22 | 10% | 100 | 1000 |", encoding="utf-8")

            output = render_markdown_report_file(source, title="标题", trade_date="2026-06-22")
            html = output.read_text(encoding="utf-8")

        self.assertEqual(re.findall(r'<script src="([^"]+)"></script>', html), [])
        self.assertIn('data-bear-echarts-loader="inline"', html)
        self.assertIn("Licensed to the Apache Software Foundation", html)
        self.assertIn("window.dispatchEvent(new Event('bear:echarts-ready'))", html)
        self.assertIn(
            'data-source="https://cdn.bootcdn.net/ajax/libs/echarts/5.6.0/echarts.min.js"',
            html,
        )
        self.assertNotIn(".generated/vendor/echarts/echarts.min.js", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertNotIn('script src="file://', html)

    def test_echarts_loader_uses_nonblocking_bootcdn_when_inline_runtime_is_missing(self):
        with patch(
            "report.markdown_report_html._echarts_source_path",
            return_value=ROOT / ".generated" / "missing-echarts.min.js",
        ):
            loader = _echarts_loader_html()

        self.assertIn('data-bear-echarts-loader="bootcdn"', loader)
        self.assertIn("script.async=true", loader)
        self.assertIn("bear:echarts-ready", loader)
        self.assertNotIn('<script src="', loader)

    def test_render_omits_stale_price_band_section_for_target_date(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 2026-06-05 A股日报",
                    "",
                    "## 二、市场基底",
                    "### 3. 价格带风格",
                    "> 最近可用窗口（截至2026-05-27）：近25个交易日价格带风格：最新差值 +0.32pct，当前为震荡。",
                    "",
                    "| 日期 | 百元股涨跌幅 | 低价股涨跌幅 | 当日差值 | 相对风格 | 绝对状态 |",
                    "|------|--------------|--------------|--------------|----------|----------|",
                    "| 2026-05-27 | -1.55% | -1.87% | +0.32pct | 震荡 | 同步回落 |",
                    "",
                    "### 4. 创新高趋势反馈",
                    "目标日新高反馈正常展示。",
                ]
            ),
            title="测试日报",
            trade_date="2026-06-05",
        )

        self.assertNotIn('href="#3-价格带风格"', html)
        self.assertNotIn('<h3 id="3-价格带风格">3. 价格带风格</h3>', html)
        self.assertNotIn("最近可用窗口", html)
        self.assertNotIn("2026-05-27", html)
        self.assertIn("创新高趋势反馈", html)


if __name__ == "__main__":
    unittest.main()
