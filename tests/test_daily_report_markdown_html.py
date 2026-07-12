import json
import re
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.markdown_report_html import render_markdown_report_file, render_markdown_report_html
from report.market_overview_builder import build_market_trend_sections_contract


class DailyReportMarkdownHtmlTest(unittest.TestCase):
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
                    "| Te | 2026-06-29（周一） | 新目标单独看B1，不用旧仓亏损补仓 | 汇源通信(000586) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |",
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
            'data-el-tooltip="Te 新目标单独看B1，不用旧仓亏损补仓；B1参与权；B2确认权；B1未变强则取消B2；只检查B1"',
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
        self.assertNotIn("position-day-order", html)
        self.assertNotIn("day-order-card", html)
        self.assertNotIn(".position-day-order-shell", html)
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

    def test_render_day_order_keeps_pending_asset_in_td_and_te_execution_target_empty(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                    "|------|------|----------|----------|-------------|------|",
                    "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                    "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |",
                    "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |",
                    "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |",
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
        self.assertIn('green: cssValue("--signal-green", "#176e54")', html)
        self.assertIn('surface: cssValue("--reader-surface", "rgba(255, 252, 246, 0.86)")', html)
        self.assertIn('color: ["rgba(231,57,34,0.58)", chartTone.red, "rgba(23,110,84,0.5)"]', html)
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
                    f"| 明日仓位 | {position_text} |",
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
        self.assertIn('<h2 class="bear-section-evidence" id="市场语言翻译研究证据">市场语言翻译（研究证据）</h2>', html)
        self.assertIn('<h2 class="bear-section-evidence" id="板块资金扩散淘汰赛">板块资金扩散淘汰赛</h2>', html)
        self.assertLess(html.index('id="明日执行结论"'), html.index('id="市场语言翻译研究证据"'))
        self.assertLess(html.index('id="明日执行结论"'), html.index('id="板块资金扩散淘汰赛"'))
        self.assertIn(".markdown-body h2.bear-section-action", html)
        self.assertIn(".markdown-body h2.bear-section-evidence", html)

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

    def test_render_adds_bear_echarts_for_sector_share_and_turnover_top30(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
                    "> 目标日热点板块占比。",
                    "",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#A88400;border-color:#A88400">[国产芯片替代]</span>',
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-06-09 | 7685.41亿 | 26667.33亿 | 28.8% | +6.2pct | 同板块连续 | 国产芯片替代资金容量扩张 |",
                    "| 2026-06-04 | 数据暂缺 | 数据暂缺 | 待累计 | 待累计 | 待累计 | 不参与图表 |",
                    "",
                    '#### 近期热点板块成交额连续跟踪：<span class="cycle-sector-label" style="color:#DD4C4F;border-color:#DD4C4F">[电力]</span>',
                    "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                    "|------|------------|------------|------|------------|----------|------|",
                    "| 2026-06-08 | 300.00亿 | 28000.00亿 | 1.1% | 待累计 | 待累计 | 非目标日 |",
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
            trade_date="2026-06-09",
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="sector_turnover_share"', html)
        self.assertIn('data-bear-chart="turnover_sector_share"', html)
        self.assertIn('data-bear-chart="turnover_top30"', html)
        self.assertIn("renderSectorTurnoverShareChart", html)
        self.assertIn("renderTurnoverSectorShareChart", html)
        self.assertIn("renderTurnoverTop30Chart", html)
        self.assertIn("confine: true", html)
        self.assertEqual(payload["sector_turnover_share"]["items"][0]["sector"], "国产芯片替代")
        self.assertEqual(payload["sector_turnover_share"]["items"][0]["share_pct"], 28.8)
        self.assertEqual(len(payload["sector_turnover_share"]["items"]), 1)
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["sector"], "通信设备")
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["share_pct"], 73.9)
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["count"], 1)
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["leaders"][0]["name"], "中天科技")
        self.assertEqual(payload["turnover_sector_share"]["items"][0]["leaders"][0]["status"], "涨停")
        self.assertEqual(payload["turnover_top30"]["items"][0]["name"], "中天科技")
        self.assertEqual(payload["turnover_top30"]["items"][0]["status"], "涨停")
        self.assertEqual(payload["turnover_top30"]["items"][1]["status"], "")

    def test_render_adds_bear_echarts_for_top50_trend_and_lhb_flow(self):
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
        )
        payload_text = re.search(r'<script type="application/json" id="bear-chart-payload">(.*?)</script>', html).group(1)
        payload = json.loads(payload_text)

        self.assertIn('data-bear-chart="market_turnover_top50_trend"', html)
        self.assertIn('data-bear-chart="lhb_net_flow"', html)
        self.assertIn("renderMarketTurnoverTop50TrendChart", html)
        self.assertIn("renderLhbNetFlowChart", html)
        self.assertIn('formatter: (value) => value === 0 ? "" : `${Math.abs(value)}亿`', html)
        self.assertIn("创新高全A占比", html)
        self.assertIn("item.new_high_share_pct", html)
        self.assertIn("hasNewHighShare", html)
        self.assertRegex(html, r'name: "创新高全A占比",\s+type: "line",\s+yAxisIndex: 1')
        self.assertIn("青线辅助看趋势扩散", html)
        self.assertIn('symbol: "circle"', html)
        self.assertIn("showSymbol: false", html)
        self.assertIn('lineStyle: { width: 1.8, color: "rgba(23,110,84,0.56)", opacity: 0.74 }', html)
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][0]["date"], "2026-06-08")
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][0]["new_high_share_pct"], 1.16)
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][1]["top50_share_pct"], 21.86)
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][1]["total_turnover"], 26667.33)
        self.assertEqual(payload["market_turnover_top50_trend"]["items"][1]["new_high_share_pct"], 1.64)
        self.assertEqual(payload["lhb_net_flow"]["items"][0]["name"], "英维克")
        self.assertEqual(payload["lhb_net_flow"]["items"][0]["amount"], 8.01)
        self.assertEqual(payload["lhb_net_flow"]["items"][1]["name"], "科泰电源")
        self.assertEqual(payload["lhb_net_flow"]["items"][1]["amount"], 0.35)
        self.assertEqual(payload["lhb_net_flow"]["items"][2]["name"], "华映科技")
        self.assertEqual(payload["lhb_net_flow"]["items"][2]["amount"], -0.12)
        self.assertEqual(payload["lhb_net_flow"]["items"][3]["name"], "北玻股份")
        self.assertEqual(payload["lhb_net_flow"]["items"][3]["amount"], -2.31)

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
                    "账户结论：1x满仓二选一；旧仓弱于指数，优先释放资金。",
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
        self.assertIn("1x满仓二选一；旧仓弱于指数，优先释放资金。", html)
        self.assertNotIn("各50%", html)
        self.assertEqual(series_keys, {"上证指数", "600667", "600584"})
        self.assertEqual(
            [item for item in review_payload["items"] if item["series_key"] == "600584"][0]["role"],
            "昨日目标 / 今日买入",
        )
        self.assertEqual(len([item for item in review_payload["items"] if item["series_key"] == "600584"]), 2)
        self.assertEqual(review_payload["events"][0]["event"], "跌破昨低")
        self.assertEqual(review_payload["account_conclusion"], "1x满仓二选一；旧仓弱于指数，优先释放资金。")

    def test_render_omits_intraday_feedback_chart_without_valid_points(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 图表日报",
                    "",
                    "### 盘面反馈复盘",
                    "账户结论：2x满仓并行；这里还没有分时事实。",
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

    def test_lhb_change_column_uses_limit_status_color(self):
        html = render_markdown_report_html(
            "\n".join(
                [
                    "# 日报",
                    "",
                    "## 七、龙虎榜结果",
                    "",
                    "### 净买入结果",
                    "| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 涨停状态 |",
                    "|------|------|------|------------|----------|--------|----------|",
                    "| 1 | 华工科技 | 000988 | 16.99亿 | 光通信 | +10.00% | 涨停 |",
                    "| 2 | 科士达 | 002518 | 4.92亿 | 算力 | +9.38% | 正常 |",
                    "",
                    "### 净流出结果",
                    "| 排名 | 股票 | 代码 | 净流出(亿) | 所属板块 | 涨跌幅 | 涨停状态 |",
                    "|------|------|------|------------|----------|--------|----------|",
                    "| 1 | 利通电子 | 603629 | 4.09亿 | 消费电子 | -10.00% | 跌停 |",
                    "| 2 | 否定样本 | 603111 | 1.00亿 | 测试板块 | +10.00% | 未涨停 |",
                ]
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">华工科技</code></td><td><code class=\"stock-ref\">000988</code></td><td>16.99亿</td><td>光通信</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">+10.00%</span></td><td>涨停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>1</td><td><code class=\"stock-ref\">利通电子</code></td><td><code class=\"stock-ref\">603629</code></td><td>4.09亿</td><td>消费电子</td>"
            '<td class="has-signal"><span class="signal-marker signal-cold">-10.00%</span></td><td>跌停</td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">科士达</code></td><td><code class=\"stock-ref\">002518</code></td><td>4.92亿</td><td>算力</td>"
            "<td>+9.38%</td><td>正常</td></tr>",
            html,
        )
        self.assertIn(
            "<tr><td>2</td><td><code class=\"stock-ref\">否定样本</code></td><td><code class=\"stock-ref\">603111</code></td><td>1.00亿</td><td>测试板块</td>"
            "<td>+10.00%</td><td>未涨停</td></tr>",
            html,
        )

    def test_lhb_signal_strength_column_uses_limit_status_color(self):
        html = render_markdown_report_html(
            "\n".join(
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
            ),
            title="日报",
            trade_date="2026-06-05",
        )

        self.assertIn(
            "<tr><td>华工科技</td><td>+16.99</td><td>龙虎榜净买入</td><td>光通信</td><td>-</td>"
            '<td class="has-signal"><span class="signal-marker signal-hot">涨停</span></td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>利通电子</td><td>-4.09</td><td>龙虎榜净卖出</td><td>消费电子</td><td>-</td>"
            '<td class="has-signal"><span class="signal-marker signal-cold">跌停</span></td></tr>',
            html,
        )
        self.assertIn(
            "<tr><td>科士达</td><td>+4.92</td><td>龙虎榜净买入</td><td>算力</td><td>-</td><td>正常</td></tr>",
            html,
        )

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

    def test_render_file_uses_relative_local_echarts_path(self):
        with TemporaryDirectory(dir=ROOT) as tempdir:
            source = Path(tempdir) / "daily.md"
            source.write_text("# 标题\n\n| 日期 | Top50占比 | Top50成交额 | 两市成交额 |\n|---|---:|---:|---:|\n| 2026-06-22 | 10% | 100 | 1000 |", encoding="utf-8")

            output = render_markdown_report_file(source, title="标题", trade_date="2026-06-22")
            html = output.read_text(encoding="utf-8")

        self.assertIn('.generated/vendor/echarts/echarts.min.js', html)
        self.assertNotIn('script src="file://', html)

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
