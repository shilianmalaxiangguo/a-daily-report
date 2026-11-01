import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from report.html_report_renderer import (
    DailyReportHtmlDataMissingError,
    build_daily_report_html_path,
    render_daily_report_html,
    save_daily_report_html,
)


def _view():
    return {
        "meta": {
            "trade_date": "2026-06-05",
            "report_title": "2026-06-05 A股日报",
            "run_mode": LEDGER_MODE_REPLAY,
            "source": "postgresql://daily-report-facts/2026-06-05",
        },
        "tomorrow_action": {
            "position_state": "0%",
            "can_participate": False,
            "primary_target": {},
            "observation_target": {"stock_name": "豫能控股", "stock_code": "001896"},
            "participation_window": "09:50-10:10",
            "action_summary": "不参与 <script>alert(1)</script>",
            "cancel_conditions": ["成交额继续萎缩"],
            "risk_boundary": "跌破认错线",
        },
        "market_spine": {
            "turnover_summary": "1000",
            "top50_turnover_share_pct": 19.0,
            "up_count": 2600,
            "down_count": 2100,
            "breadth_summary": "上涨2600 / 下跌2100",
            "market_phase": "等待承接",
        },
        "mainline_evidence": {
            "confirmed_line": "电力",
            "cycle_mainline": "电力",
            "daily_attack_line": "虚拟电厂",
            "cycle_daily_relationship": "当天主攻线是周期主线内部加强",
            "attack_evidence": ["净流入居前", "高位锚点保持"],
        },
        "charts": {
            "market_capacity": {
                "status": "ready",
                "title": "市场容量趋势",
                "missing_reasons": [],
                "points": [
                    {
                        "date": "2026-06-05",
                        "total_turnover": 1000,
                        "top50_share_pct": 19.0,
                        "up_count": 2600,
                        "down_count": 2100,
                    }
                ],
            },
            "mainline_turnover_share": {
                "status": "ready",
                "title": "主线成交占比趋势",
                "missing_reasons": [],
                "points": [
                    {
                        "date": "2026-06-05",
                        "mainline": "电力",
                        "turnover_share_pct": 18.2,
                        "share_delta_pct": 0.5,
                    }
                ],
            },
            "sector_heatmap": {
                "status": "ready",
                "title": "板块容量热力图",
                "missing_reasons": [],
                "columns": [
                    {"key": "fund", "label": "资金"},
                    {"key": "continuity", "label": "成交占比"},
                    {"key": "limit_up", "label": "涨停"},
                    {"key": "height", "label": "高标"},
                    {"key": "attention", "label": "注意力"},
                ],
                "rows": [{"sector": "电力", "fund": 32.0, "continuity": 18.2, "limit_up": 3, "height": 4, "attention": 6}],
                "calculation_note": "热榜 tag 只作为注意力入口，不作为独立确认。",
            },
            "mainline_attack_scatter": {
                "status": "ready",
                "title": "主线攻击证据",
                "missing_reasons": [],
                "points": [
                    {
                        "sector": "电力",
                        "role": "主攻线",
                        "turnover_share_pct": 18.2,
                        "turnover_share_delta_pct": 1.2,
                        "fund_strength": 76,
                        "limit_up_count": 3,
                        "height": 4,
                    }
                ],
            },
            "hot_tag_composition": {
                "status": "ready",
                "title": "热榜 Tag 构成",
                "missing_reasons": [],
                "tags": [{"tag": "电力", "count": 6, "role": "主tag", "sample_stocks": ["豫能控股"]}],
                "calculation_note": "只回答市场在讲什么，不直接给参与资格。",
            },
                "cycle_week_view": {
                    "status": "ready",
                    "title": "板块周视图",
                    "missing_reasons": [],
                    "rows": [{"week_label": "06-01当周", "mainline": "电力", "phase": "强化", "action": "观察承接"}],
                },
                "turnover_rank": {
                    "status": "ready",
                    "title": "Top50成交额占比",
                    "missing_reasons": [],
                    "share_points": [
                        {"date": "2026-06-04", "share_pct": 19.0, "market_amount_yi": 12000},
                        {"date": "2026-06-05", "share_pct": 20.2, "market_amount_yi": 12500},
                    ],
                    "latest_share_pct": 20.2,
                    "share_delta_pct": 1.2,
                    "rows": [
                        {
                            "rank": 1,
                            "name": "中际旭创",
                            "code": "300308",
                            "sector": "通信设备",
                            "turnover_yi": 466.76,
                            "change_pct": 2.17,
                            "close": 1180,
                            "zt_status": "正常",
                        }
                    ],
                },
                "new_high": {
                    "status": "ready",
                    "title": "创新高扩散",
                    "missing_reasons": [],
                    "new_high_count": 82,
                    "all_a_share_pct": 1.64,
                    "leading_sectors": "元器件、通信设备",
                    "trend_rows": [
                        {
                            "date": "2026-06-05",
                            "new_high_count": 82,
                            "all_a_share_pct": 1.64,
                            "leading_sectors": "元器件、通信设备",
                        }
                    ],
                    "sector_rows": [
                        {
                            "sector": "元器件",
                            "new_high_count": 18,
                            "share_pct": 21.95,
                            "representative_stocks": ["三环集团"],
                        }
                    ],
                    "top_stocks": [
                        {"name": "太辰光", "code": "300570", "sector": "通信设备", "pct_chg": 18.07}
                    ],
                },
                "lhb": {
                    "status": "ready",
                    "title": "龙虎榜资金",
                    "missing_reasons": [],
                    "buy_rows": [
                        {
                            "name": "英维克",
                            "code": "002837",
                            "sector": "专用机械",
                            "net_buy_amount_yi": 8.01,
                            "change_pct": 10,
                            "close": 69.72,
                            "zt_status": "涨停",
                            "list_quality": "主线好榜",
                            "capital_read": "榜单净额+8.01亿；机构+0.70亿；非机构-0.10亿",
                            "institution_net_buy_yi": 0.7,
                            "broker_net_buy_yi": -0.1,
                            "top_buy_seat": "机构专用",
                            "top_sell_seat": "东方财富证券股份有限公司拉萨东环路第二证券营业部",
                        }
                    ],
                    "sell_rows": [
                        {
                            "name": "北玻股份",
                            "code": "002613",
                            "sector": "专用机械",
                            "net_buy_amount_yi": -2.31,
                            "change_pct": -4.95,
                            "close": 5.19,
                            "zt_status": "正常",
                        }
                    ],
                    "seat_detail_status": "available",
                    "interpretation_rows": [
                        {
                            "name": "英维克",
                            "code": "002837",
                            "sector": "专用机械",
                            "list_quality": "主线好榜",
                            "capital_read": "榜单净额+8.01亿；机构+0.70亿；非机构-0.10亿",
                            "institution_net_buy_yi": 0.7,
                            "broker_net_buy_yi": -0.1,
                        }
                    ],
                },
                "price_band": {
                    "status": "ready",
                    "title": "百元股与低价股风格",
                    "missing_reasons": [],
                    "latest_spread_pct": 2.68,
                    "latest_style_label": "高潮",
                    "latest_absolute_label": "高价占优",
                    "points": [
                        {
                            "date": "2026-06-05",
                            "high_price_pct": 2.1,
                            "low_price_pct": -0.58,
                            "spread_pct": 2.68,
                            "style_label": "高潮",
                            "absolute_label": "高价占优",
                        }
                    ],
                },
                "tail_window": {
                    "status": "ready",
                    "title": "尾盘窗口",
                    "missing_reasons": [],
                    "window": "14:30-14:55",
                    "missing_stock_pool": True,
                    "stock_rows": [],
                    "rule_rows": [
                        {"label": "默认节奏", "text": "没有日内强核心承接，不新增参与。"},
                        {"label": "强核心复核", "text": "强核心全天强，也只做尾盘复核，不新增参与。"},
                    ],
                },
            },
        "candidate_actions": [
            {
                "stock_name": "豫能控股",
                "stock_code": "001896",
                "role": "电力前排",
                "buy_window": "09:50-10:10",
                "invalidation": "跌破认错线",
                "missed_action": "条件不成立就不做",
            }
        ],
        "participation_reviews": [
            {
                "stock_name": "豫能控股",
                "stock_code": "001896",
                "review_status": "等待更多事实",
                "missed_action": "不追",
            }
        ],
        "data_sources": [
            {
                "source_label": "PSQL日报事实",
                "source_policy": "postgresql.daily_report_facts",
                "trade_date": "2026-06-05",
                "source_date": "2026-06-05",
                "status": "success",
                "warning": "",
            }
        ],
        "diagnostics": {
            "missing_required_facts": [],
            "degraded_facts": [],
            "render_warnings": [],
            "large_json_artifact": False,
        },
    }


class DailyReportHtmlRendererTest(unittest.TestCase):
    def test_build_path_uses_report_mode_and_html_extension(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            frozen_path = build_daily_report_html_path("2026-06-05", root=root, run_mode=LEDGER_MODE_FROZEN)
            replay_path = build_daily_report_html_path("2026-06-05", root=root, run_mode=LEDGER_MODE_REPLAY)

        self.assertEqual(frozen_path.name, "2026-06-05_A股日报_完整版.html")
        self.assertEqual(frozen_path.parent.name, "reports")
        self.assertEqual(replay_path.name, "2026-06-05_A股日报_完整版_replay.html")
        self.assertEqual(replay_path.parent.name, "replay")

    def test_render_escapes_text_and_contains_reader_design_tokens(self):
        html = render_daily_report_html(_view())

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("--accent: #c20c0c", html)
        self.assertIn("--reader-bg: #ffffff", html)
        self.assertIn("--reader-text: #111111", html)
        self.assertIn("--editor-width: 740px", html)
        self.assertIn("--outline-width: 248px", html)
        self.assertIn('class="bear-shell"', html)
        self.assertIn('class="outline-sidebar"', html)
        self.assertIn('class="outline-sticky"', html)
        self.assertIn('class="outline-nav"', html)
        self.assertIn("position: sticky", html)
        self.assertIn("height: calc(100vh - 48px)", html)
        self.assertIn("box-shadow: inset 3px 0 0 var(--accent-red)", html)
        self.assertNotIn(".window-controls span:first-child", html)
        self.assertNotIn('class="note-rail"', html)
        self.assertNotIn('class="note-item is-active"', html)
        self.assertNotIn('name="viewport"', html)
        self.assertNotIn('class="mobile-nav"', html)
        self.assertNotIn('@media (max-width:', html)
        self.assertIn('<div class="reader-table is-two-column"><table>', html)
        self.assertIn("明日动作", html)
        self.assertIn("明日新仓", html)
        self.assertIn("观察对象", html)
        self.assertIn('<code class="stock-ref">豫能控股(001896)</code>', html)
        self.assertNotIn("<td>参与对象</td>", html)
        self.assertIn("事实完整性", html)
        self.assertIn("PSQL日报事实", html)

    def test_render_includes_chart_dashboard_and_safe_payload(self):
        view = _view()
        view["charts"]["hot_tag_composition"]["tags"][0]["tag"] = "<script>alert(1)</script>"

        html = render_daily_report_html(view)

        self.assertIn('id="daily-chart-market-capacity"', html)
        self.assertIn('id="daily-chart-mainline-share"', html)
        self.assertIn('id="daily-chart-sector-heatmap"', html)
        self.assertIn('id="daily-chart-attack-scatter"', html)
        self.assertIn('id="daily-chart-hot-tag"', html)
        self.assertIn('id="daily-chart-cycle-week"', html)
        self.assertIn('id="daily-chart-turnover-rank"', html)
        self.assertIn('id="daily-chart-turnover-bars"', html)
        self.assertIn('id="daily-chart-new-high"', html)
        self.assertIn('id="daily-chart-new-high-brief"', html)
        self.assertIn('id="daily-chart-lhb"', html)
        self.assertIn('id="daily-chart-price-band"', html)
        self.assertIn('id="daily-chart-tail-window"', html)
        self.assertIn('id="daily-chart-payload"', html)
        self.assertIn("daily-chart-tall", html)
        self.assertIn("\\u003cscript\\u003ealert(1)\\u003c/script\\u003e", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("daily-dashboard-panel", html)
        self.assertIn("Top50成交额占比", html)
        self.assertIn("创新高扩散", html)
        self.assertIn("龙虎榜资金", html)
        self.assertIn("百元股与低价股风格", html)
        self.assertIn("尾盘窗口", html)
        self.assertIn("daily-chart-lhb-brief", html)
        self.assertIn("renderLhbBrief", html)
        self.assertIn("renderTurnoverBrief", html)
        self.assertIn("renderTurnoverRankBrief", html)
        self.assertIn("renderTurnoverRankList", html)
        self.assertIn("turnoverMoveLabel", html)
        self.assertIn("renderNewHighBrief", html)
        self.assertIn("renderPriceBandBrief", html)
        self.assertIn("renderTurnoverRank", html)
        self.assertIn("renderTurnoverRankBars", html)
        self.assertIn("top50ShareRegime", html)
        self.assertIn("turnover_rank_bars", html)
        self.assertIn("turnover-rank-list", html)
        self.assertIn("成交额排行Top20", html)
        self.assertIn("renderNewHigh", html)
        self.assertIn("newHighSectorSummary", html)
        self.assertIn("newHighStockSummary", html)
        self.assertIn("创新高来源", html)
        self.assertIn("代表个股", html)
        self.assertIn("renderLhb", html)
        self.assertIn("榜单净额", html)
        self.assertIn("非机构净额", html)
        self.assertIn("百元-低价差值", html)
        self.assertIn("主线好榜", html)
        self.assertIn("renderPriceBand", html)
        self.assertIn("renderTailWindow", html)

        turnover_script = html[html.index("function top50ShareRegime") : html.index("function renderNewHighBrief")]
        self.assertIn("低于18%：头部资金活跃度不足", turnover_script)
        self.assertIn("高于20%：资金处于活跃期", turnover_script)
        self.assertIn("18%-20%：震荡结构", turnover_script)
        self.assertIn("markLine", turnover_script)
        self.assertIn('formatter: "18% 活跃度不足"', turnover_script)
        self.assertIn('formatter: "20% 资金活跃"', turnover_script)
        self.assertIn("Math.min(17", turnover_script)
        self.assertIn("Math.max(21", turnover_script)
        self.assertIn("renderTurnoverRankList(chart.rows || [])", turnover_script)
        self.assertIn('status.indexOf("涨停")', turnover_script)
        self.assertIn('status.indexOf("跌停")', turnover_script)
        self.assertIn(".turnover-rank-list em.move-up", html)
        self.assertIn(".turnover-rank-list em.move-down", html)
        self.assertIn("turnoverMoveClass", turnover_script)
        self.assertIn("turnoverMoveRichLabel", turnover_script)
        self.assertIn('direction + " " + pct(parsed)', turnover_script)
        self.assertIn('yi(item.turnover_yi) + " / " + turnoverMoveLabel(item)', turnover_script)
        self.assertIn('class="\' + turnoverMoveClass(item) + \'"', turnover_script)
        self.assertIn('"标注：" + escapeText(turnoverMoveLabel(item))', turnover_script)
        self.assertIn("return turnoverMoveRichLabel(item);", turnover_script)
        self.assertIn('up: { color: "#c20c0c"', turnover_script)
        self.assertIn('down: { color: "#1f7a3f"', turnover_script)
        self.assertIn('name: "成交额Top20"', turnover_script)
        self.assertIn("slice(0, 20)", turnover_script)
        self.assertNotIn('name: "成交额Top8"', turnover_script)
        self.assertNotIn("option.grid = [", turnover_script)
        self.assertIn('sourceKey = key === "turnover_rank_bars" ? "turnover_rank" : key', html)

        new_high_script = html[html.index("function renderNewHighBrief") : html.index("function signedYi")]
        self.assertIn('name: "全A占比"', new_high_script)
        self.assertIn("yAxisIndex: 1", new_high_script)
        self.assertNotIn('name: "板块分布"', new_high_script)
        self.assertIn("创新高板块", new_high_script)
        self.assertIn("代表个股", new_high_script)
        self.assertIn("历史日期未展开板块明细；最新日见创新高来源", new_high_script)
        self.assertIn("历史日期未展开个股明细；最新日见代表个股", new_high_script)

        lhb_script = html[html.index("option.tooltip = {", html.index("function renderLhb")) : html.index("option.xAxis = {", html.index("function renderLhb"))]
        self.assertIn('trigger: "item"', lhb_script)
        self.assertIn("max-width:260px", lhb_script)
        self.assertNotIn("买方代表", lhb_script)
        self.assertNotIn("卖方压力", lhb_script)
        self.assertNotIn("上榜原因", lhb_script)
        self.assertNotIn("capital_read", lhb_script)

        lhb_full_script = html[html.index("function lhbNetValue") : html.index("function renderPriceBandBrief")]
        self.assertIn("lhbFlowRows", lhb_full_script)
        self.assertIn("inflowRows.concat(outflowRows)", lhb_full_script)
        self.assertIn(
            ".filter(function (item) { return lhbNetValue(item) < 0; })\n"
            "              .sort(function (left, right) { return lhbNetValue(left) - lhbNetValue(right); })\n"
            "              .slice(0, 6)\n"
            "              .sort(function (left, right) { return lhbNetValue(right) - lhbNetValue(left); })",
            lhb_full_script,
        )
        self.assertIn('name: "净流入"', lhb_full_script)
        self.assertIn('name: "净流出"', lhb_full_script)
        self.assertIn("净流出压力", lhb_full_script)
        self.assertIn("方向：", lhb_full_script)
        self.assertIn("slice(0, 6)", lhb_full_script)
        self.assertNotIn("slice(0, 8)", lhb_full_script)

    def test_render_sector_heatmap_uses_capacity_treemap(self):
        html = render_daily_report_html(_view())
        sector_script = html[html.index('name: "板块容量"') : html.index("function renderAttackScatter")]

        self.assertIn("板块容量热力图", html)
        self.assertIn('name: "板块容量"', html)
        self.assertIn('type: "treemap"', html)
        self.assertIn("nodeClick: false", html)
        self.assertIn("breadcrumb: { show: false }", html)
        self.assertIn("sectorTreemapValue", html)
        self.assertIn("sectorTreemapColor", html)
        self.assertIn("raw: row", html)
        self.assertIn("var item = (params.data && params.data.raw) || {};", html)
        self.assertNotIn("var attention = numberOrNull(row.attention);", html)
        self.assertNotIn("var limitUp = numberOrNull(row.limit_up);", html)
        self.assertIn("maxFundMagnitude", html)
        self.assertIn("sectorTreemapBorderColor(row, maxFundMagnitude)", html)
        self.assertIn('return ["#fff2ef", "#fde5df", "#f8d2c9", "#efbcb1"][level];', html)
        self.assertIn('return ["#fbf0ed", "#f7e0d9", "#edcbc1", "#ddb1a6"][level];', html)
        self.assertIn('return ratio >= 0.46 ? "#b9786f" : "#d9afa5";', html)
        self.assertNotIn("#eef8f2", html)
        self.assertNotIn("#c3decf", html)
        self.assertNotIn("#9fcab0", html)
        self.assertIn('color: "#25211d"', html)
        self.assertIn('metric: { color: "#4d4640", fontSize: 11, fontWeight: 600, lineHeight: 16 }', sector_script)
        self.assertNotIn(
            'metric: { color: "#756f67", fontSize: 11, fontWeight: 500, lineHeight: 16 }',
            sector_script,
        )
        self.assertIn('fontWeight: 600', html)
        self.assertIn("richLabelText", html)
        self.assertIn("成交占比：", html)
        self.assertIn("涨停：", html)
        self.assertIn("高标：", html)
        self.assertIn("注意力：", html)
        self.assertNotIn('name: "板块热力"', html)
        self.assertNotIn('type: "heatmap"', html)
        self.assertNotIn("data.push([columnIndex, rowIndex", html)
        self.assertNotIn("normalizeHeatByColumn", html)

    def test_render_chart_dashboard_uses_readable_single_and_two_column_layouts(self):
        html = render_daily_report_html(_view())

        self.assertIn(".chart-grid-core .daily-chart", html)
        self.assertIn("grid-template-columns: 1fr", html)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", html)
        self.assertNotIn("@media (max-width:", html)
        self.assertIn('class="chart-grid chart-grid-explain"', html)
        self.assertLess(
            html.index('id="daily-chart-mainline-share"'),
            html.index('class="chart-grid chart-grid-explain"'),
        )
        self.assertLess(
            html.index('id="daily-chart-hot-tag"'),
            html.index('id="daily-chart-cycle-week"'),
        )

    def test_render_chart_options_reserve_space_for_dense_labels(self):
        html = render_daily_report_html(_view())

        self.assertIn("containLabel: true", html)
        self.assertIn("labelInterval", html)
        self.assertIn("formatter: shortDate", html)
        self.assertIn('overflow: "truncate"', html)
        self.assertIn("labelLayout: { hideOverlap: true }", html)
        self.assertIn("barMaxWidth", html)
        self.assertIn('height: "44%"', html)
        self.assertIn('top: "64%"', html)
        self.assertIn("bottom: 28", html)
        self.assertIn("bottom: 66", html)

    def test_render_hot_tag_composition_uses_treemap(self):
        html = render_daily_report_html(_view())
        hot_tag_start = html.index("function renderHotTag")
        hot_tag_script = html[hot_tag_start : html.index("function renderCycleWeek(container", hot_tag_start)]

        self.assertIn('name: "Tag构成"', hot_tag_script)
        self.assertIn('type: "treemap"', hot_tag_script)
        self.assertIn("nodeClick: false", hot_tag_script)
        self.assertIn("breadcrumb: { show: false }", hot_tag_script)
        self.assertIn("raw: item", hot_tag_script)
        self.assertIn("sample_stocks", html)
        self.assertIn("tagTreemapStyle(index)", hot_tag_script)
        self.assertIn('color: "#25211d"', hot_tag_script)
        self.assertIn('fontWeight: 600', hot_tag_script)
        self.assertNotIn('name: "Tag数量"', hot_tag_script)
        self.assertNotIn("barMaxWidth: 14", hot_tag_script)
        self.assertNotIn("data: tags.map(function (item) { return number(item.count); })", hot_tag_script)

    def test_render_market_capacity_splits_turnover_and_breadth_axes(self):
        html = render_daily_report_html(_view())
        market_script = html[html.index("function renderMarketCapacity") : html.index("function renderMainlineShare")]

        self.assertIn('name: "成交额"', html)
        self.assertIn('name: "Top50占比"', market_script)
        self.assertIn('name: "市场宽度净值"', market_script)
        self.assertIn("marketBreadthNet(item)", market_script)
        self.assertIn("gridIndex: 1", market_script)
        self.assertIn("yAxisIndex: 2", market_script)
        self.assertIn('name: "Top50"', market_script)
        self.assertIn('height: "44%"', market_script)
        self.assertIn('top: "64%"', market_script)
        self.assertIn("splitNumber: 3", market_script)
        self.assertIn('"净宽度：" + escapeText(marketBreadthNet(item))', market_script)
        self.assertNotIn('name: "上涨家数"', market_script)
        self.assertNotIn('name: "下跌家数"', market_script)
        self.assertNotIn("offset: 52", market_script)

    def test_render_attack_evidence_chart_limits_visible_rows(self):
        html = render_daily_report_html(_view())

        self.assertIn("visibleAttackPoints", html)
        self.assertIn("attackSignalScore", html)
        self.assertIn("slice(0, 12)", html)

    def test_render_attack_evidence_chart_uses_turnover_share_axis(self):
        html = render_daily_report_html(_view())
        attack_script = html[html.index("function renderAttackScatter") : html.index("function renderHotTag")]

        self.assertIn('name: "成交占比"', attack_script)
        self.assertIn("numberOrNull(item.turnover_share_pct)", attack_script)
        self.assertIn('"占比变化：" + escapeText(pct(item.turnover_share_delta_pct))', attack_script)
        self.assertNotIn('name: "占比变化"', attack_script)

    def test_render_attack_evidence_chart_prioritizes_visible_points_with_share(self):
        html = render_daily_report_html(_view())

        self.assertIn("visibleAttackPoints(points)", html)
        self.assertIn("hasAttackShare", html)
        self.assertIn("attackShareValue", html)
        self.assertIn("var shareDiff = attackShareValue(right) - attackShareValue(left);", html)
        self.assertIn("return shareDiff;", html)
        self.assertIn("withShare.concat(withoutShare).slice(0, 12)", html)

    def test_render_attack_evidence_chart_removes_delta_reference_line(self):
        html = render_daily_report_html(_view())
        attack_script = html[html.index("function renderAttackScatter") : html.index("function renderHotTag")]

        self.assertIn("containLabel: true", attack_script)
        self.assertIn("nameGap: 24", attack_script)
        self.assertIn('axisLabel: { color: "#6b6b70", interval: 0, width: 112, overflow: "truncate" }', attack_script)
        self.assertNotIn("markLine", attack_script)
        self.assertNotIn("xAxis: 0", attack_script)

    def test_render_cycle_week_view_uses_readable_structure_rows(self):
        html = render_daily_report_html(_view())

        self.assertIn("cycleWeekMainlineText", html)
        self.assertIn("cycleWeekSecondaryText", html)
        self.assertIn("cleanCycleWeekText", html)
        self.assertIn("cycleWeekLanes", html)
        self.assertIn("cycleWeekLabels", html)
        self.assertIn("weekCardColor", html)
        self.assertIn("item.color", html)
        self.assertNotIn('phase.indexOf("退潮")', html)
        self.assertIn('type: "custom"', html)
        self.assertIn("renderCycleWeekItem", html)
        self.assertIn('name: "周度泳道"', html)
        self.assertIn("renderCycleWeekConnector", html)
        self.assertIn("coordSys.width / Math.max(1, weekLabels.length)", html)
        self.assertIn("coordSys.height / Math.max(1, lanes.length)", html)
        self.assertIn("data: lanes", html)
        self.assertIn("data: weekLabels", html)
        self.assertIn("coordSys.width", html)
        self.assertIn("borderRadius: 6", html)
        self.assertIn("replace(/\\\\n/g, \" \")", html)
        self.assertNotIn('firstLine + "\\\\n" + secondLine', html)
        self.assertNotIn("barWidth: 40", html)
        self.assertNotIn("value: 1,", html)
        self.assertNotIn("return index + 1;", html)
        self.assertNotIn('name: "周视图", type: "line"', html)
        self.assertNotIn('name: "周度时间线"', html)
        self.assertNotIn('return [item.week_label, "周度结构"];', html)

    def test_render_cycle_week_view_resizes_for_dense_rows(self):
        html = render_daily_report_html(_view())

        self.assertIn("resizeCycleWeekContainer", html)
        self.assertIn("Math.max(300, laneCount * 58 + 92)", html)
        self.assertIn("container.style.height", html)

    def test_render_chart_series_keep_missing_values_as_null(self):
        html = render_daily_report_html(_view())

        self.assertIn("return numberOrNull(item.total_turnover);", html)
        self.assertIn("return marketBreadthNet(item);", html)
        self.assertIn("var limitUp = numberOrNull(item[2]);", html)

    def test_render_shows_cycle_and_daily_attack_lines_separately(self):
        html = render_daily_report_html(_view())

        self.assertIn("周期主线", html)
        self.assertIn("当天主攻线", html)
        self.assertIn("<td>电力</td>", html)
        self.assertIn("<td>虚拟电厂</td>", html)
        self.assertIn("当天主攻线是周期主线内部加强", html)

    def test_render_uses_local_echarts_before_cdn_when_available(self):
        html = render_daily_report_html(_view())

        if (ROOT / ".generated" / "vendor" / "echarts" / "echarts.min.js").exists():
            self.assertIn("<script>", html)
            self.assertNotIn("cdn.jsdelivr.net/npm/echarts", html)
        else:
            self.assertIn("cdn.jsdelivr.net/npm/echarts@5.6.0", html)

    def test_render_shows_missing_reason_for_explanation_chart(self):
        view = _view()
        view["charts"]["sector_heatmap"] = {
            "status": "missing",
            "title": "板块容量热力图",
            "missing_reasons": ["板块资金事实不足"],
            "columns": [],
            "rows": [],
        }

        html = render_daily_report_html(view)

        self.assertIn("板块资金事实不足", html)

    def test_render_marks_top50_share_by_thresholds(self):
        low_view = _view()
        low_view["market_spine"]["top50_turnover_share_pct"] = 17.5
        low_html = render_daily_report_html(low_view)

        self.assertIn("Top50成交额占比", low_html)
        self.assertIn('<td class="signal-cold">17.50%</td>', low_html)
        self.assertIn("--signal-green: #1f7a3f", low_html)

        hot_view = _view()
        hot_view["market_spine"]["top50_turnover_share_pct"] = 20.5
        hot_html = render_daily_report_html(hot_view)

        self.assertIn('<td class="signal-hot">20.50%</td>', hot_html)

        neutral_view = _view()
        neutral_view["market_spine"]["top50_turnover_share_pct"] = 19.0
        neutral_html = render_daily_report_html(neutral_view)

        self.assertIn("<td>19.00%</td>", neutral_html)
        self.assertNotIn('<td class="signal-cold">19.00%</td>', neutral_html)
        self.assertNotIn('<td class="signal-hot">19.00%</td>', neutral_html)

        boundary_low_view = _view()
        boundary_low_view["market_spine"]["top50_turnover_share_pct"] = 18.0
        boundary_low_html = render_daily_report_html(boundary_low_view)
        self.assertIn("<td>18.00%</td>", boundary_low_html)
        self.assertNotIn('<td class="signal-cold">18.00%</td>', boundary_low_html)

        boundary_hot_view = _view()
        boundary_hot_view["market_spine"]["top50_turnover_share_pct"] = 20.0
        boundary_hot_html = render_daily_report_html(boundary_hot_view)
        self.assertIn("<td>20.00%</td>", boundary_hot_html)
        self.assertNotIn('<td class="signal-hot">20.00%</td>', boundary_hot_html)

    def test_render_marks_breadth_counts_by_thresholds(self):
        up_view = _view()
        up_view["market_spine"]["up_count"] = 4100
        up_view["market_spine"]["down_count"] = 800
        up_html = render_daily_report_html(up_view)

        self.assertIn("上涨家数", up_html)
        self.assertIn('<td class="signal-hot">4100</td>', up_html)
        self.assertIn("<td>800</td>", up_html)
        self.assertNotIn("上涨2600 / 下跌2100", up_html)

        down_view = _view()
        down_view["market_spine"]["up_count"] = 900
        down_view["market_spine"]["down_count"] = 4100
        down_html = render_daily_report_html(down_view)

        self.assertIn("下跌家数", down_html)
        self.assertIn('<td class="signal-cold">4100</td>', down_html)
        self.assertIn("<td>900</td>", down_html)

        boundary_view = _view()
        boundary_view["market_spine"]["up_count"] = 4000
        boundary_view["market_spine"]["down_count"] = 4000
        boundary_html = render_daily_report_html(boundary_view)

        self.assertIn("<td>4000</td>", boundary_html)
        self.assertNotIn('<td class="signal-hot">4000</td>', boundary_html)
        self.assertNotIn('<td class="signal-cold">4000</td>', boundary_html)

    def test_render_wraps_stock_labels_in_code_style(self):
        html = render_daily_report_html(_view())

        self.assertIn('code.stock-ref', html)
        self.assertIn('<code class="stock-ref">豫能控股(001896)</code>', html)
        self.assertNotIn('<td>豫能控股(001896)</td>', html)

    def test_save_refuses_missing_required_facts(self):
        view = _view()
        view["diagnostics"]["missing_required_facts"] = ["明日动作"]

        with TemporaryDirectory() as tmp:
            with self.assertRaises(DailyReportHtmlDataMissingError):
                save_daily_report_html(view, root=Path(tmp))

            self.assertEqual(list(Path(tmp).glob("**/*.html")), [])
            self.assertEqual(list(Path(tmp).glob("**/*.json")), [])

    def test_save_writes_only_html(self):
        with TemporaryDirectory() as tmp:
            path = save_daily_report_html(_view(), root=Path(tmp))

            self.assertTrue(path.exists())
            self.assertEqual(path.suffix, ".html")
            self.assertIn("2026-06-05_A股日报_完整版_replay.html", str(path))
            self.assertEqual(list(path.parent.glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
