import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.html_report_view import (
    build_daily_report_view,
    daily_report_view_has_required_facts,
    missing_required_fact_labels,
)


class FakePostgresDailyReportService:
    def __init__(self, *, snapshot=None, mentions=None, coverage=None, market_totals=None, market_breadth=None):
        self.snapshot = snapshot or {}
        self.mentions = mentions or []
        self.coverage = coverage or {
            "tables": {
                "daily_report_fact_fields": {"target_count": 8, "max_trade_date": "2026-06-05"},
                "sector_attack_evidence_daily": {"target_count": 2, "max_trade_date": "2026-06-05"},
            }
        }
        self.market_totals = market_totals or {}
        self.market_breadth = market_breadth or {}
        self.loaded_dates = []

    def is_postgres_backed(self):
        return True

    def load_daily_report_snapshot(self, trade_date):
        self.loaded_dates.append(trade_date)
        return {
            "source": f"postgresql://daily-report-facts/{trade_date}",
            "field_count": 8 if self.snapshot else 0,
            "target_field_count": 8 if self.snapshot else 0,
            "data": self.snapshot,
        }

    def daily_report_fact_coverage(self, trade_date):
        return self.coverage

    def query_market_daily_total(self, trade_date, *, market_scope="all_a"):
        return dict(self.market_totals.get(trade_date) or {})

    def query_market_breadth_counts(self, trade_date):
        return dict(self.market_breadth.get(trade_date) or {})

    def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
        return list(self.mentions)


class DailyReportHtmlViewTest(unittest.TestCase):
    def test_builds_view_from_postgres_facts_without_large_json_artifact(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_decision": {
                        "final_action": "0%不参与，等待主线承接重新出现",
                        "max_position": "0%",
                        "allow_new_entry": False,
                        "cancel_conditions": ["成交额继续萎缩", "主线扩散不足"],
                    },
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "电力", "turnover_share_pct": 18.2}
                        ]
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
                "top50_turnover_share_series": {
                    "rows": [
                        {"trade_date": "2026-06-04", "share_pct": 19.0},
                        {"trade_date": "2026-06-05", "share_pct": 17.5},
                    ]
                },
                "mainline_context": {
                    "confirmed_line": "电力",
                    "attack_evidence": ["净流入居前", "高位锚点保持"],
                },
                "data_status": {"两市成交额": True, "大盘涨跌统计": True},
            },
            mentions=[
                {
                    "mention_trade_date": "2026-06-05",
                    "stock_code": "001896",
                    "stock_name": "豫能控股",
                    "planned_window": "09:50-10:10",
                    "review_status": "等待更多事实",
                    "next_action": "只在承接成立时参与",
                    "invalidation": "跌破认错线",
                    "reason": "电力方向前排",
                }
            ],
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertEqual(view["meta"]["trade_date"], "2026-06-05")
        self.assertEqual(view["meta"]["run_mode"], "replay")
        self.assertEqual(view["meta"]["source"], "postgresql://daily-report-facts/2026-06-05")
        self.assertEqual(view["tomorrow_action"]["position_state"], "0%")
        self.assertFalse(view["tomorrow_action"]["can_participate"])
        self.assertEqual(view["tomorrow_action"]["primary_target"], {})
        self.assertEqual(view["tomorrow_action"]["observation_target"], {})
        self.assertEqual(view["market_spine"]["turnover_summary"], "1000")
        self.assertEqual(view["market_spine"]["top50_turnover_share_pct"], 17.5)
        self.assertEqual(view["market_spine"]["up_count"], 2600)
        self.assertEqual(view["market_spine"]["down_count"], 2100)
        self.assertEqual(view["mainline_evidence"]["confirmed_line"], "电力")
        self.assertEqual(view["candidate_actions"][0]["stock_code"], "001896")
        self.assertEqual(view["diagnostics"]["large_json_artifact"], False)
        self.assertTrue(daily_report_view_has_required_facts(view))
        self.assertEqual(missing_required_fact_labels(view), [])

    def test_zero_position_keeps_concrete_target_as_observation_not_primary_target(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {
                        "final_action": "0%不参与；只观察雅克科技，不新增参与",
                        "allow_new_entry": False,
                    },
                    "final_target_resolution": {
                        "watch_target": {"name": "雅克科技", "code": "002409"},
                        "display_target": {"name": "雅克科技", "code": "002409"},
                        "new_entry_target": {},
                    },
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-10", "mainline": "半导体", "turnover_share_pct": 14.0}
                        ]
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 26441.43,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-10", "share_pct": 20.53}]},
                "mainline_context": {"confirmed_line": "半导体", "attack_evidence": ["成交占比抬升"]},
                "data_status": {"两市成交额": True, "大盘涨跌统计": True},
            }
        )

        view = build_daily_report_view("2026-06-10", service, run_mode="frozen")
        action = view["tomorrow_action"]

        self.assertFalse(action["can_participate"])
        self.assertEqual(action["primary_target"], {})
        self.assertEqual(action["observation_target"]["code"], "002409")
        self.assertEqual(action["observation_target"]["name"], "雅克科技")

    def test_builds_chart_payloads_from_saved_daily_facts(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "current_mainline": "AI算力",
                        "turnover_share_trend_rows": [
                            {
                                "trade_date": "2026-06-04",
                                "mainline_name": "AI算力",
                                "mainline_turnover": 3200,
                                "market_turnover": 12000,
                                "turnover_share_pct": 26.67,
                                "share_delta_pct": 1.2,
                            },
                            {
                                "trade_date": "2026-06-05",
                                "mainline_name": "AI算力",
                                "mainline_turnover": 3500,
                                "market_turnover": 12500,
                                "turnover_share_pct": 28.0,
                                "share_delta_pct": 1.33,
                            },
                        ],
                        "mainline_attack_evidence_summary": {
                            "primary_line": "AI算力",
                            "evidence_rows": [
                                {
                                    "sector": "CPO",
                                    "role": "主攻线",
                                    "turnover_share_delta_pct": 2.1,
                                    "fund_strength": 82,
                                    "limit_up_count": 5,
                                    "height": 4,
                                }
                            ],
                        },
                        "cycle_calendar_rows": [
                            {"week_label": "06-01当周", "mainline": "AI算力", "phase": "强化"}
                        ],
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 12500,
                "top50_turnover_share_series": {
                    "rows": [
                        {
                            "trade_date": "2026-06-04",
                            "total_turnover": 12000,
                            "share_pct": 19.0,
                            "up_count": 2400,
                            "down_count": 2300,
                        },
                        {
                            "trade_date": "2026-06-05",
                            "total_turnover": 12500,
                            "share_pct": 20.2,
                            "up_count": 2600,
                            "down_count": 2100,
                        },
                    ]
                },
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
                "sector_fund_flow": {
                    "inflow": [
                        {
                            "name": "CPO",
                            "amount": 58.5,
                            "change_pct": 3.2,
                            "limit_up_count": 5,
                            "turnover_share_pct": 28.0,
                        },
                        {
                            "name": "电力",
                            "amount": 21.0,
                            "change_pct": 1.1,
                            "limit_up_count": 1,
                            "turnover_share_pct": 4.8,
                        },
                    ]
                },
                "tag_distribution": {"CPO": 8, "算力": 6, "电力": 2},
                "integrated_hot_list": [
                    {"stock_name": "新易盛", "code": "300502", "tags": ["CPO", "算力"]},
                    {"stock_name": "华电辽能", "code": "600396", "tags": ["电力"]},
                ],
                "hot_rank_sample_size": 100,
                "hot_rank_sample_target": 100,
                    "realtime_tag_evidence_snapshot": {
                        "tag_rows": [
                            {"tag": "CPO", "role": "主tag", "stock_count": 8, "sample_stocks": ["新易盛"]}
                        ]
                    },
                    "turnover_rank": [
                        {
                            "rank": 1,
                            "name": "中际旭创",
                            "code": "300308",
                            "sector": "通信设备",
                            "turnover": 466.76,
                            "change_pct": 2.17,
                            "close": 1180,
                            "zt_status": "正常",
                        },
                        {
                            "rank": 2,
                            "name": "新易盛",
                            "code": "300502",
                            "sector": "通信设备",
                            "turnover": 268.04,
                            "change_pct": 8.38,
                            "close": 785.73,
                            "zt_status": "正常",
                        },
                    ],
                    "new_high_feedback": {
                        "new_high_count": 82,
                        "all_a_share_pct": 1.64,
                        "leading_sectors": "元器件、通信设备",
                        "summary": "创新高扩散回升",
                        "trend_rows": [
                            {
                                "trade_date": "2026-06-04",
                                "new_high_count": 20,
                                "all_a_share_pct": 0.4,
                                "leading_sectors": "半导体",
                            },
                            {
                                "trade_date": "2026-06-05",
                                "new_high_count": 82,
                                "all_a_share_pct": 1.64,
                                "leading_sectors": "元器件、通信设备",
                            },
                        ],
                        "sector_distribution": [
                            {
                                "sector": "元器件",
                                "new_high_count": 18,
                                "share_pct": 21.95,
                                "representative_stocks": ["三环集团"],
                            },
                            {
                                "sector": "通信设备",
                                "new_high_count": 6,
                                "share_pct": 7.32,
                                "representative_stocks": ["太辰光"],
                            },
                        ],
                        "top_stocks": [
                            {
                                "name": "太辰光",
                                "code": "300570",
                                "sector": "通信设备",
                                "pct_chg": 18.07,
                                "close": 181.71,
                                "topdays": 250,
                            }
                        ],
                    },
                    "lhb_net_buy_top10": [
                        {
                            "rank": 1,
                            "name": "英维克",
                            "code": "002837",
                            "sector": "专用机械",
                            "net_buy_amount_yi": 8.01,
                            "change_pct": 10,
                            "close": 69.72,
                            "zt_status": "涨停",
                        }
                    ],
                    "lhb_net_sell_top10": [
                        {
                            "rank": 1,
                            "name": "北玻股份",
                            "code": "002613",
                            "sector": "专用机械",
                            "net_buy_amount_yi": -2.31,
                            "change_pct": -4.95,
                            "close": 5.19,
                            "zt_status": "正常",
                        }
                    ],
                    "price_band_style_series": {
                        "latest_spread_pct": 2.68,
                        "latest_style_label": "高潮",
                        "latest_absolute_label": "高价占优",
                        "summary": "百元股占优",
                        "rows": [
                            {
                                "trade_date": "2026-06-04",
                                "high_price_pct": 1.2,
                                "low_price_pct": -0.4,
                                "spread_pct": 1.6,
                                "style_label": "修复",
                                "absolute_label": "高价占优",
                            },
                            {
                                "trade_date": "2026-06-05",
                                "high_price_pct": 2.1,
                                "low_price_pct": -0.58,
                                "spread_pct": 2.68,
                                "style_label": "高潮",
                                "absolute_label": "高价占优",
                            },
                        ],
                    },
                }
            )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")
        charts = view["charts"]

        self.assertEqual(charts["market_capacity"]["status"], "ready")
        self.assertEqual(charts["market_capacity"]["points"][-1]["top50_share_pct"], 20.2)
        self.assertEqual(charts["mainline_turnover_share"]["status"], "ready")
        self.assertEqual(charts["mainline_turnover_share"]["points"][-1]["mainline"], "AI算力")
        self.assertEqual(charts["sector_heatmap"]["status"], "ready")
        self.assertEqual(charts["sector_heatmap"]["rows"][0]["sector"], "CPO")
        self.assertEqual(charts["sector_heatmap"]["columns"][-1]["key"], "attention")
        self.assertIn("注意力", charts["sector_heatmap"]["calculation_note"])
        self.assertEqual(charts["mainline_attack_scatter"]["points"][0]["sector"], "CPO")
        self.assertEqual(charts["hot_tag_composition"]["tags"][0]["tag"], "CPO")
        self.assertEqual(charts["cycle_week_view"]["rows"][0]["week_label"], "06-01当周")
        self.assertEqual(charts["turnover_rank"]["status"], "ready")
        self.assertEqual(charts["turnover_rank"]["title"], "Top50成交额占比")
        self.assertEqual(charts["turnover_rank"]["share_points"][-1]["share_pct"], 20.2)
        self.assertEqual(charts["turnover_rank"]["share_delta_pct"], 1.2)
        self.assertEqual(charts["turnover_rank"]["rows"][0]["name"], "中际旭创")
        self.assertEqual(charts["new_high"]["status"], "ready")
        self.assertEqual(charts["new_high"]["new_high_count"], 82.0)
        self.assertEqual(charts["new_high"]["sector_rows"][0]["sector"], "元器件")
        self.assertEqual(charts["lhb"]["status"], "ready")
        self.assertEqual(charts["lhb"]["buy_rows"][0]["name"], "英维克")
        self.assertEqual(charts["lhb"]["sell_rows"][0]["name"], "北玻股份")
        self.assertEqual(charts["price_band"]["status"], "ready")
        self.assertEqual(charts["price_band"]["latest_style_label"], "高潮")
        self.assertEqual(charts["tail_window"]["status"], "ready")
        self.assertTrue(charts["tail_window"]["missing_stock_pool"])
        self.assertEqual(missing_required_fact_labels(view), [])

    def test_sector_heatmap_prefers_sector_attack_evidence_rows(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "新型电力", "turnover_share_pct": 0.6}
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "混沌轮动", "attack_evidence": ["多方向分散"]},
                "sector_fund_flow": {"inflow": [{"name": "银行", "net_inflow_yi": 26.9, "change_pct": 1.1}]},
                "tag_distribution": {"光纤概念": 8},
                "sector_attack_evidence_rows": [
                    {
                        "date": "2026-06-08",
                        "sector_name": "光通信/CPO",
                        "net_inflow_amount": -103.39,
                        "limit_up_count": 3,
                        "high_anchor_height": 2,
                        "turnover_share_pct": 27.67,
                        "turnover_share_change": -1.48,
                    }
                ],
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["sector_heatmap"]

        self.assertEqual(chart["status"], "ready")
        row = chart["rows"][0]
        self.assertEqual(row["sector"], "光通信/CPO")
        self.assertEqual(row["fund"], -103.39)
        self.assertEqual(row["breadth"], -1.48)
        self.assertEqual(row["limit_up"], 3.0)
        self.assertEqual(row["height"], 2.0)
        self.assertEqual(row["continuity"], 27.67)
        self.assertIsNone(row["attention"])
        self.assertIn("板块攻击证据", chart["calculation_note"])

    def test_sector_heatmap_degrades_when_attack_evidence_lacks_capacity_share(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "新型电力", "turnover_share_pct": 0.6}
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "混沌轮动", "attack_evidence": ["多方向分散"]},
                "sector_attack_evidence_rows": [
                    {
                        "date": "2026-06-08",
                        "sector_name": "光通信/CPO",
                        "net_inflow_amount": -103.39,
                        "limit_up_count": 3,
                        "high_anchor_height": 2,
                        "turnover_share_change": -1.48,
                    }
                ],
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["sector_heatmap"]

        self.assertEqual(chart["status"], "missing")
        self.assertIn("板块成交占比事实不足", chart["missing_reasons"])

    def test_mainline_attack_scatter_uses_sector_attack_evidence_rows_when_dedicated_rows_missing(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "混沌轮动", "turnover_share_pct": 27.67}
                        ],
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "混沌轮动", "attack_evidence": ["板块攻击证据已入库"]},
                "sector_attack_evidence_rows": [
                    {
                        "date": "2026-06-08",
                        "sector_name": "光通信/CPO",
                        "net_inflow_amount": -103.39,
                        "limit_up_count": 3,
                        "high_anchor_height": 2,
                        "turnover_share_pct": 27.67,
                        "turnover_share_change": -1.48,
                    }
                ],
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["mainline_attack_scatter"]

        self.assertEqual(chart["status"], "ready")
        point = chart["points"][0]
        self.assertEqual(point["sector"], "光通信/CPO")
        self.assertEqual(point["role"], "板块攻击证据")
        self.assertEqual(point["turnover_share_pct"], 27.67)
        self.assertEqual(point["turnover_share_delta_pct"], -1.48)
        self.assertEqual(point["fund_strength"], -103.39)
        self.assertEqual(point["limit_up_count"], 3.0)
        self.assertEqual(point["height"], 2.0)
        self.assertEqual(point["source_date"], "2026-06-08")

    def test_mainline_attack_scatter_keeps_missing_metrics_distinct_from_zero(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "混沌轮动", "turnover_share_pct": 27.67}
                        ],
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "混沌轮动", "attack_evidence": ["板块攻击证据已入库"]},
                "sector_attack_evidence_rows": [
                    {"date": "2026-06-08", "sector_name": "真实零值", "turnover_share_change": 0, "limit_up_count": 0},
                    {"date": "2026-06-08", "sector_name": "缺失样本"},
                ],
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        points = view["charts"]["mainline_attack_scatter"]["points"]

        self.assertEqual(points[0]["turnover_share_delta_pct"], 0.0)
        self.assertEqual(points[0]["limit_up_count"], 0.0)
        self.assertIsNone(points[0]["fund_strength"])
        self.assertIsNone(points[0]["height"])
        self.assertIsNone(points[1]["turnover_share_delta_pct"])
        self.assertIsNone(points[1]["fund_strength"])
        self.assertIsNone(points[1]["limit_up_count"])
        self.assertIsNone(points[1]["height"])

    def test_mainline_attack_scatter_requires_capacity_share_for_plotting(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "混沌轮动", "turnover_share_pct": 27.67}
                        ],
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "混沌轮动", "attack_evidence": ["板块攻击证据已入库"]},
                "sector_attack_evidence_rows": [
                    {
                        "date": "2026-06-08",
                        "sector_name": "光通信/CPO",
                        "net_inflow_amount": -103.39,
                        "limit_up_count": 3,
                        "high_anchor_height": 2,
                        "turnover_share_change": -1.48,
                    }
                ],
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["mainline_attack_scatter"]

        self.assertEqual(chart["status"], "missing")
        self.assertIn("板块成交占比事实不足", chart["missing_reasons"])
        self.assertEqual(chart["points"][0]["turnover_share_delta_pct"], -1.48)

    def test_capacity_counts_treat_missing_text_as_missing_not_zero(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "电力", "turnover_share_pct": 2.1}
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {
                    "rows": [
                        {
                            "trade_date": "2026-06-07",
                            "share_pct": 23.28,
                            "total_turnover": 31006.9,
                            "up_count": "-",
                            "down_count": "数据暂缺",
                        },
                        {"trade_date": "2026-06-08", "share_pct": 21.11, "total_turnover": 28234.29},
                    ]
                },
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["成交额集中"]},
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        point = view["charts"]["market_capacity"]["points"][0]

        self.assertIsNone(point["up_count"])
        self.assertIsNone(point["down_count"])

    def test_new_high_and_price_band_require_target_date_rows(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "电力", "turnover_share_pct": 2.1}
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["成交额集中"]},
                "new_high_feedback": {
                    "new_high_count": 40,
                    "all_a_share_pct": 0.8,
                    "factor_trade_date": "2026-06-08",
                    "trend_rows": [{"trade_date": "2026-06-08", "new_high_count": 40}],
                },
                "price_band_style_series": {
                    "rows": [
                        {
                            "trade_date": "2026-06-08",
                            "high_price_pct": -3.13,
                            "low_price_pct": -1.76,
                            "spread_pct": -1.36,
                        }
                    ]
                },
            }
        )

        view = build_daily_report_view("2026-06-09", service, run_mode="replay")

        self.assertEqual(view["charts"]["new_high"]["status"], "missing")
        self.assertIn("日期不匹配", view["charts"]["new_high"]["missing_reasons"][0])
        self.assertEqual(view["charts"]["price_band"]["status"], "missing")
        self.assertIn("目标日期价格带", view["charts"]["price_band"]["missing_reasons"][0])

    def test_lhb_filters_rows_when_source_dates_are_present(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-09", "mainline": "电力", "turnover_share_pct": 2.1}
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-09", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["成交额集中"]},
                "lhb_net_buy_top10": [
                    {
                        "trade_date": "2026-06-08",
                        "name": "旧样本",
                        "code": "000001",
                        "net_buy_amount_yi": 9.0,
                    },
                    {
                        "trade_date": "2026-06-09",
                        "name": "英维克",
                        "code": "002837",
                        "net_buy_amount_yi": 8.01,
                    },
                ],
            }
        )

        chart = build_daily_report_view("2026-06-09", service, run_mode="replay")["charts"]["lhb"]

        self.assertEqual(chart["status"], "ready")
        self.assertEqual(chart["buy_rows"][0]["name"], "英维克")
        self.assertNotIn("旧样本", [row["name"] for row in chart["buy_rows"]])

    def test_lhb_chart_builds_seat_interpretation_from_inst_detail(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-09", "mainline": "专用机械", "turnover_share_pct": 2.1}
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-09", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "专用机械", "attack_evidence": ["龙虎榜资金确认"]},
                "lhb_net_buy_top10": [
                    {
                        "trade_date": "2026-06-09",
                        "name": "英维克",
                        "code": "002837",
                        "sector": "专用机械",
                        "net_buy_amount_yi": 8.01,
                        "change_pct": 10,
                        "zt_status": "涨停",
                    }
                ],
                "lhb_analysis": [{"代码": "002837", "reasons": ["日涨幅偏离值达到7%"]}],
                "lhb_inst_detail": [
                    {
                        "trade_date": "20260609",
                        "code": "002837",
                        "exalter": "机构专用",
                        "seat_type": "机构",
                        "side": "1",
                        "buy": 80000000,
                        "sell": 10000000,
                        "net_buy": 70000000,
                        "reason": "日涨幅偏离值达到7%",
                    },
                    {
                        "trade_date": "20260609",
                        "code": "002837",
                        "exalter": "机构专用",
                        "seat_type": "机构",
                        "side": "0",
                        "buy": 80000000,
                        "sell": 10000000,
                        "net_buy": 70000000,
                        "reason": "日涨幅偏离值达到7%",
                    },
                    {
                        "trade_date": "20260609",
                        "code": "002837",
                        "exalter": "东方财富证券股份有限公司拉萨东环路第二证券营业部",
                        "seat_type": "非机构",
                        "buy": 10000000,
                        "sell": 20000000,
                        "net_buy": -10000000,
                        "reason": "日涨幅偏离值达到7%",
                    },
                    {
                        "code": "002837",
                        "exalter": "无日期污染席位",
                        "seat_type": "机构",
                        "buy": 900000000,
                        "sell": 0,
                        "net_buy": 900000000,
                        "reason": "日涨幅偏离值达到7%",
                    },
                ],
            }
        )

        chart = build_daily_report_view("2026-06-09", service, run_mode="replay")["charts"]["lhb"]
        row = chart["buy_rows"][0]

        self.assertEqual(chart["seat_detail_status"], "available")
        self.assertEqual(row["institution_net_buy_yi"], 0.7)
        self.assertEqual(row["broker_net_buy_yi"], -0.1)
        self.assertEqual(row["list_quality"], "主线好榜")
        self.assertIn("机构+0.70亿", row["capital_read"])
        self.assertIn("非机构-0.10亿", row["capital_read"])
        self.assertEqual(chart["interpretation_rows"][0]["list_quality"], "主线好榜")
        self.assertEqual(chart["seat_summaries"][0]["top_buy_seat"], "机构专用")

    def test_mainline_attack_scatter_reads_sector_evidence_rows_from_attack_summary(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "电力", "turnover_share_pct": 2.1}
                        ],
                        "mainline_attack_evidence_summary": {
                            "sector_evidence_rows": [
                                {
                                    "trade_date": "2026-06-08",
                                    "sector_name": "新型电力",
                                    "net_inflow_amount": 18.5,
                                    "share": "2.1%",
                                    "turnover_share_change": 0.7,
                                    "limit_up_count": 2,
                                    "high_anchor_height": 3,
                                }
                            ]
                        },
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["成交额集中"]},
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["mainline_attack_scatter"]

        self.assertEqual(chart["status"], "ready")
        self.assertEqual(chart["points"][0]["sector"], "新型电力")
        self.assertEqual(chart["points"][0]["turnover_share_pct"], 2.1)
        self.assertEqual(chart["points"][0]["source_date"], "2026-06-08")

    def test_trend_charts_keep_latest_25_days_through_target_date(self):
        capacity_rows = []
        share_rows = []
        for day in range(1, 31):
            trade_date = f"2026-05-{day:02d}"
            capacity_rows.append(
                {
                    "trade_date": trade_date,
                    "total_turnover": 10000 + day,
                    "share_pct": 10 + day / 10,
                    "up_count": 2000 + day,
                    "down_count": 2500 - day,
                }
            )
            share_rows.append(
                {
                    "trade_date": trade_date,
                    "mainline": "AI算力",
                    "turnover_share_pct": 20 + day / 10,
                }
            )
        capacity_rows.append({"trade_date": "2026-06-01", "total_turnover": 99999, "share_pct": 99.9})
        share_rows.append({"trade_date": "2026-06-01", "mainline": "未来线", "turnover_share_pct": 99.9})
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "current_mainline": "AI算力",
                        "turnover_share_trend_rows": share_rows,
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 12500,
                "top50_turnover_share_series": {"rows": capacity_rows},
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
            }
        )

        view = build_daily_report_view("2026-05-30", service, run_mode="replay")
        capacity_points = view["charts"]["market_capacity"]["points"]
        mainline_points = view["charts"]["mainline_turnover_share"]["points"]

        self.assertEqual(len(capacity_points), 25)
        self.assertEqual(capacity_points[0]["date"], "2026-05-06")
        self.assertEqual(capacity_points[-1]["date"], "2026-05-30")
        self.assertNotIn("2026-06-01", [point["date"] for point in capacity_points])
        self.assertEqual(len(mainline_points), 25)
        self.assertEqual(mainline_points[0]["date"], "2026-05-06")
        self.assertEqual(mainline_points[-1]["date"], "2026-05-30")
        self.assertNotIn("未来线", [point["mainline"] for point in mainline_points])

    def test_market_capacity_keeps_missing_history_fields_as_missing(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "current_mainline": "AI算力",
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-07", "mainline": "AI算力", "turnover_share_pct": 26.0},
                            {"trade_date": "2026-06-08", "mainline": "AI算力", "turnover_share_pct": 27.0},
                        ],
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {
                    "rows": [
                        {"trade_date": "2026-06-07", "share_pct": 20.2},
                        {"trade_date": "2026-06-08", "share_pct": 21.11},
                    ]
                },
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["market_capacity"]

        self.assertEqual(chart["status"], "ready")
        self.assertIsNone(chart["points"][0]["total_turnover"])
        self.assertIsNone(chart["points"][0]["up_count"])
        self.assertIsNone(chart["points"][0]["down_count"])
        self.assertEqual(chart["points"][1]["total_turnover"], 28234.29)
        self.assertEqual(chart["points"][1]["up_count"], 899)
        self.assertIn("缺失保持空值", chart["calculation_note"])

    def test_mainline_turnover_chart_requires_target_date_row(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "current_mainline": "AI算力",
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-05-29", "mainline": "AI算力", "turnover_share_pct": 27.0},
                            {"trade_date": "2026-06-01", "mainline": "未来线", "turnover_share_pct": 99.0},
                        ],
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 12500,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-05-30", "share_pct": 20.2}]},
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
            }
        )

        view = build_daily_report_view("2026-05-30", service, run_mode="replay")
        chart = view["charts"]["mainline_turnover_share"]

        self.assertEqual(chart["status"], "missing")
        self.assertIn("主线成交占比趋势", missing_required_fact_labels(view))
        self.assertNotIn("未来线", [point["mainline"] for point in chart["points"]])

    def test_sector_heatmap_degrades_when_capacity_share_is_missing(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "AI算力", "turnover_share_pct": 28.0}
                        ]
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 12500,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-05", "share_pct": 20.2}]},
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
                "sector_fund_flow": {"inflow": [{"name": "CPO", "amount": 58.5}]},
                "tag_distribution": {"CPO": 8},
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")
        chart = view["charts"]["sector_heatmap"]

        self.assertEqual(chart["status"], "missing")
        self.assertIn("板块成交占比事实不足", chart["missing_reasons"])

    def test_sector_heatmap_keeps_unknown_secondary_metrics_visible_as_missing(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "AI算力", "turnover_share_pct": 28.0}
                        ]
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 12500,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-05", "share_pct": 20.2}]},
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
                "sector_fund_flow": {"inflow": [{"name": "CPO", "amount": 58.5, "turnover_share_pct": 28.0}]},
                "tag_distribution": {"CPO": 8},
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")
        chart = view["charts"]["sector_heatmap"]

        self.assertEqual(chart["status"], "ready")
        row = chart["rows"][0]
        self.assertEqual(row["fund"], 58.5)
        self.assertIsNone(row["breadth"])
        self.assertIsNone(row["limit_up"])
        self.assertIsNone(row["height"])
        self.assertEqual(row["continuity"], 28.0)
        self.assertIn("缺失不按0计算", chart["calculation_note"])

    def test_market_capacity_chart_enriches_history_from_structured_market_facts(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-07", "mainline": "电力", "turnover_share_pct": 1.8},
                            {"trade_date": "2026-06-08", "mainline": "电力", "turnover_share_pct": 2.1},
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {
                    "rows": [
                        {"trade_date": "2026-06-07", "share_pct": 23.28},
                        {"trade_date": "2026-06-08", "share_pct": 21.11},
                    ]
                },
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["成交额集中"]},
            },
            market_totals={
                "2026-06-07": {"trade_date": "2026-06-07", "total_amount_yi": 31006.9},
                "2026-06-08": {"trade_date": "2026-06-08", "total_amount_yi": 28234.29},
            },
            market_breadth={
                "2026-06-07": {"up_count": 1520, "down_count": 3920},
                "2026-06-08": {"up_count": 899, "down_count": 4591},
            },
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["market_capacity"]

        self.assertEqual(chart["status"], "ready")
        self.assertEqual(chart["points"][0]["total_turnover"], 31006.9)
        self.assertEqual(chart["points"][0]["up_count"], 1520)
        self.assertEqual(chart["points"][0]["down_count"], 3920)

    def test_market_capacity_chart_does_not_enrich_market_total_from_amount_yi(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-07", "mainline": "电力", "turnover_share_pct": 1.8},
                            {"trade_date": "2026-06-08", "mainline": "电力", "turnover_share_pct": 2.1},
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {
                    "rows": [
                        {"trade_date": "2026-06-07", "share_pct": 23.28},
                        {"trade_date": "2026-06-08", "share_pct": 21.11},
                    ]
                },
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["成交额集中"]},
            },
            market_totals={
                "2026-06-07": {"trade_date": "2026-06-07", "amount_yi": 6000.0},
                "2026-06-08": {"trade_date": "2026-06-08", "total_amount_yi": 28234.29},
            },
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["market_capacity"]

        self.assertEqual(chart["status"], "ready")
        self.assertIsNone(chart["points"][0]["total_turnover"])
        self.assertEqual(chart["points"][1]["total_turnover"], 28234.29)

    def test_market_capacity_chart_uses_market_amount_yi_from_top50_series(self):
        top50_rows = [
            {
                "trade_date": f"2026-05-{day:02d}",
                "market_amount_yi": 30000.0 + day,
                "share_pct": 18.0 + day / 10,
            }
            for day in range(1, 26)
        ]
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-05-25", "mainline": "电力", "turnover_share_pct": 2.1},
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": top50_rows},
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["成交额集中"]},
            },
        )

        view = build_daily_report_view("2026-05-25", service, run_mode="replay")
        chart = view["charts"]["market_capacity"]

        self.assertEqual(chart["status"], "ready")
        self.assertEqual(len(chart["points"]), 25)
        self.assertEqual(chart["points"][0]["total_turnover"], 30001.0)
        self.assertEqual(chart["points"][-1]["total_turnover"], 30025.0)
        self.assertFalse([point for point in chart["points"] if point["total_turnover"] is None])

    def test_market_capacity_chart_uses_total_amount_yi_as_market_total(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "电力", "turnover_share_pct": 2.1},
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {
                    "rows": [
                        {"trade_date": "2026-06-05", "total_amount_yi": 30000.0, "share_pct": 20.0},
                    ]
                },
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["成交额集中"]},
            },
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")
        chart = view["charts"]["market_capacity"]

        self.assertEqual(chart["status"], "ready")
        self.assertEqual(chart["points"][0]["total_turnover"], 30000.0)

    def test_market_capacity_chart_does_not_treat_top_amount_as_market_total(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "电力", "turnover_share_pct": 2.1},
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {
                    "rows": [
                        {
                            "trade_date": "2026-06-04",
                            "top_amount_yi": 6000.0,
                            "top50_amount_yi": 6000.0,
                            "amount_yi": 6000.0,
                            "share_pct": 20.0,
                        },
                        {
                            "trade_date": "2026-06-05",
                            "market_amount_yi": 30000.0,
                            "top_amount_yi": 6000.0,
                            "share_pct": 20.0,
                        },
                    ]
                },
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["成交额集中"]},
            },
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")
        chart = view["charts"]["market_capacity"]

        self.assertEqual(chart["status"], "ready")
        self.assertIsNone(chart["points"][0]["total_turnover"])
        self.assertEqual(chart["points"][1]["total_turnover"], 30000.0)

    def test_sector_heatmap_keeps_missing_attention_distinct_from_zero(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "新型电力", "turnover_share_pct": 0.6}
                        ]
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "混沌轮动", "attack_evidence": ["多方向分散"]},
                "tag_distribution": {"真实零值": 0},
                "sector_attack_evidence_rows": [
                    {"date": "2026-06-08", "sector_name": "真实零值", "net_inflow_amount": 0, "turnover_share_pct": 1.0},
                    {"date": "2026-06-08", "sector_name": "缺失注意力", "net_inflow_amount": -10.5, "turnover_share_pct": 0.8},
                ],
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        rows = view["charts"]["sector_heatmap"]["rows"]

        self.assertEqual(rows[0]["attention"], 0.0)
        self.assertIsNone(rows[1]["attention"])

    def test_cycle_week_view_falls_back_to_turnover_trend_when_calendar_has_only_labels(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "AI算力", "turnover_share_pct": 27.0}
                        ],
                        "cycle_calendar_rows": [
                            {"week_label": "06-08当周"},
                            {"week_label": "06-01当周", "mainline": "", "phase": "", "action": ""},
                        ],
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["cycle_week_view"]

        self.assertEqual(chart["status"], "ready")
        self.assertEqual(chart["rows"][0]["week_label"], "06-08当周")
        self.assertEqual(chart["rows"][0]["mainline"], "AI算力")
        self.assertEqual(chart["rows"][0]["phase"], "成交占比27.00%")
        self.assertEqual(chart["rows"][0]["action"], "AI算力")
        self.assertIn("主线成交占比趋势", chart["calculation_note"])

    def test_cycle_week_view_reads_weekday_calendar_cells(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-08", "mainline": "AI算力", "turnover_share_pct": 27.0}
                        ],
                    },
                },
                "cycle_calendar_rows": [
                    {
                        "week_label": "06-08当周",
                        "monday": {
                            "date": "06-08",
                            "mainline": "电力",
                            "state": "支线轮动",
                            "daily_attack_line": "混沌轮动",
                        },
                        "tuesday": {"mainline": "-", "state": "-"},
                    }
                ],
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-08", "share_pct": 21.11}]},
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="replay")
        chart = view["charts"]["cycle_week_view"]

        self.assertEqual(chart["status"], "ready")
        self.assertEqual(chart["rows"][0]["week_label"], "06-08当周")
        self.assertEqual(chart["rows"][0]["mainline"], "电力")
        self.assertEqual(chart["rows"][0]["phase"], "支线轮动")
        self.assertEqual(chart["rows"][0]["action"], "混沌轮动")
        self.assertRegex(chart["rows"][0]["color"], r"^#[0-9A-F]{6}$")

    def test_hot_tag_composition_accepts_front50_sample_with_clear_note(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "AI算力", "turnover_share_pct": 28.0}
                        ]
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 12500,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-05", "share_pct": 20.2}]},
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
                "tag_distribution": {"CPO": 8, "算力": 6},
                "integrated_hot_list": [{"stock_name": "新易盛", "code": "300502", "tags": ["CPO"]}],
                "hot_rank_sample_size": 50,
                "hot_rank_sample_target": 50,
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")
        chart = view["charts"]["hot_tag_composition"]

        self.assertEqual(chart["status"], "ready")
        self.assertIn("前50", chart["calculation_note"])

    def test_hot_tag_composition_requires_at_least_front50_sample(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "AI算力", "turnover_share_pct": 28.0}
                        ]
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 12500,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-05", "share_pct": 20.2}]},
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
                "tag_distribution": {"CPO": 8, "算力": 6},
                "integrated_hot_list": [{"stock_name": "新易盛", "code": "300502", "tags": ["CPO"]}],
                "hot_rank_sample_size": 1,
                "hot_rank_sample_target": 50,
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")
        chart = view["charts"]["hot_tag_composition"]

        self.assertEqual(chart["status"], "missing")
        self.assertIn("同花顺热榜样本不足", chart["missing_reasons"][0])

    def test_hot_tag_composition_accepts_explicit_top100_sample(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "AI算力", "turnover_share_pct": 28.0}
                        ]
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 12500,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-05", "share_pct": 20.2}]},
                "mainline_context": {"confirmed_line": "AI算力", "attack_evidence": ["成交额集中"]},
                "tag_distribution": {"CPO": 8, "算力": 6},
                "integrated_hot_list": [{"stock_name": "新易盛", "code": "300502", "tags": ["CPO"]}],
                "hot_rank_sample_size": 100,
                "hot_rank_sample_target": 100,
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")
        chart = view["charts"]["hot_tag_composition"]

        self.assertEqual(chart["status"], "ready")
        self.assertIn("前100", chart["calculation_note"])

    def test_mainline_turnover_chart_accepts_rendered_report_row_fields(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "double_mainline_summary": {
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "国产芯片替代 / AI算力基础设施",
                            "relationship": "当天主攻线是周期主线内部加强",
                        },
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-06-04",
                                "cycle_mainline": "电力",
                                "daily_attack_line": "电力",
                                "mainline_turnover": "0.00亿",
                                "market_turnover": "27791.64亿",
                                "share": "0.00%",
                                "share_change": "待累计",
                            },
                            {
                                "date": "2026-06-05",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "国产芯片替代 / AI算力基础设施",
                                "mainline_turnover": "4155.30亿",
                                "market_turnover": "31006.90亿",
                                "share": "13.40%",
                                "share_change": "+13.40pct",
                            },
                        ],
                    },
                },
                "market_stats": {"up_count": 3277, "down_count": 2113},
                "total_turnover": 31006.9,
                "top50_turnover_share_series": {
                    "rows": [
                        {"trade_date": "2026-06-04", "share_pct": 22.36, "total_turnover": 27791.64},
                        {"trade_date": "2026-06-05", "share_pct": 23.28, "total_turnover": 31006.9},
                    ]
                },
                "mainline_context": {"confirmed_line": "半导体", "attack_evidence": ["成交占比可复盘"]},
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")
        chart = view["charts"]["mainline_turnover_share"]

        self.assertEqual(chart["status"], "ready")
        self.assertEqual(chart["points"][-1]["mainline"], "半导体")
        self.assertEqual(chart["points"][-1]["cycle_mainline"], "半导体")
        self.assertEqual(chart["points"][-1]["daily_attack_line"], "国产芯片替代 / AI算力基础设施")
        self.assertEqual(chart["points"][-1]["turnover_share_pct"], 13.4)
        self.assertEqual(chart["points"][-1]["mainline_turnover"], 4155.3)
        self.assertEqual(chart["points"][-1]["market_turnover"], 31006.9)
        self.assertEqual(chart["points"][-1]["share_delta_pct"], 13.4)
        self.assertEqual(view["mainline_evidence"]["cycle_mainline"], "半导体")
        self.assertEqual(view["mainline_evidence"]["daily_attack_line"], "国产芯片替代 / AI算力基础设施")
        self.assertNotIn("主线成交占比趋势", missing_required_fact_labels(view))

    def test_mainline_evidence_uses_latest_turnover_row_when_double_summary_cycle_is_empty(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "current_mainline": "",
                        "double_mainline_summary": {
                            "cycle_mainline": "-",
                            "daily_attack_line": "国产芯片替代 / AI算力基础设施",
                            "relationship": "当日观察分支，不按周期主线处理",
                        },
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-06-04",
                                "cycle_mainline": "电力",
                                "daily_attack_line": "电力",
                                "share": "0.90%",
                            },
                            {
                                "date": "2026-06-05",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "国产芯片替代 / AI算力基础设施",
                                "share": "13.40%",
                            },
                        ],
                    },
                },
                "market_stats": {"up_count": 3277, "down_count": 2113},
                "total_turnover": 31006.9,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-05", "share_pct": 23.28}]},
                "mainline_context": {"attack_evidence": ["成交占比可复盘"]},
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertEqual(view["mainline_evidence"]["cycle_mainline"], "半导体")
        self.assertEqual(view["mainline_evidence"]["daily_attack_line"], "国产芯片替代 / AI算力基础设施")
        self.assertEqual(view["charts"]["mainline_turnover_share"]["points"][-1]["cycle_mainline"], "半导体")

    def test_missing_market_capacity_chart_stops_html_dashboard_generation(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_decision": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "电力", "turnover_share_pct": 18.2}
                        ]
                    },
                },
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["净流入居前"]},
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertEqual(view["charts"]["market_capacity"]["status"], "missing")
        self.assertIn("市场容量趋势", missing_required_fact_labels(view))

    def test_missing_explanation_charts_degrades_without_required_fact_missing(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_decision": {"final_action": "0%不参与", "allow_new_entry": False},
                    "mainline_turnover_summary": {
                        "turnover_share_trend_rows": [
                            {"trade_date": "2026-06-05", "mainline": "电力", "turnover_share_pct": 18.2}
                        ]
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
                "top50_turnover_share_series": {"rows": [{"trade_date": "2026-06-05", "share_pct": 19.0}]},
                "mainline_context": {"confirmed_line": "电力", "attack_evidence": ["净流入居前"]},
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertNotIn("板块容量热力图", missing_required_fact_labels(view))
        self.assertEqual(view["charts"]["sector_heatmap"]["status"], "missing")
        self.assertIn("板块容量热力图", view["diagnostics"]["degraded_facts"])

    def test_top50_share_requires_target_date_row(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_decision": {"final_action": "0%不参与", "allow_new_entry": False}
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
                "top50_turnover_share_series": {
                    "rows": [
                        {"trade_date": "2026-06-04", "share_pct": 20.5},
                    ]
                },
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertIsNone(view["market_spine"]["top50_turnover_share_pct"])
        self.assertIn("Top50成交额占比", missing_required_fact_labels(view))
        self.assertIn("市场容量趋势", missing_required_fact_labels(view))
        self.assertEqual(view["charts"]["market_capacity"]["status"], "missing")
        self.assertFalse(daily_report_view_has_required_facts(view))

    def test_mainline_evidence_is_required_for_html_report(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_decision": {"final_action": "0%不参与", "allow_new_entry": False}
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
                "top50_turnover_share_series": {
                    "rows": [
                        {"trade_date": "2026-06-05", "share_pct": 19.0},
                    ]
                },
                "mainline_context": {},
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertIn("主线证据", missing_required_fact_labels(view))
        self.assertFalse(daily_report_view_has_required_facts(view))

    def test_mainline_evidence_reads_runtime_mainline_summary_fields(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {"final_action": "0%不参与", "allow_new_entry": False},
                    "current_mainline_history_record": {
                        "primary_mainline": "AI算力基础设施",
                        "phase": "发酵",
                    },
                    "mainline_turnover_summary": {
                        "current_mainline": "AI算力基础设施",
                        "turnover_share_trend_rows": [
                            {
                                "trade_date": "2026-06-08",
                                "mainline": "AI算力基础设施",
                                "turnover_share_pct": 32.1,
                            }
                        ],
                        "mainline_attack_evidence_summary": {
                            "labels": ["成交额集中", "前排承接"],
                            "conclusion": "主线仍有攻击证据",
                        },
                        "fund_flow": "成交额集中在前排容量核心",
                    },
                },
                "market_stats": {"up_count": 899, "down_count": 4591},
                "total_turnover": 28234.29,
                "top50_turnover_share_series": {
                    "rows": [{"trade_date": "2026-06-08", "share_pct": 32.1}],
                },
            }
        )

        view = build_daily_report_view("2026-06-08", service, run_mode="frozen")

        self.assertEqual(view["mainline_evidence"]["confirmed_line"], "AI算力基础设施")
        self.assertIn("成交额集中", view["mainline_evidence"]["attack_evidence"])
        self.assertTrue(daily_report_view_has_required_facts(view))

    def test_missing_required_facts_are_reported_without_reading_live_sources(self):
        service = FakePostgresDailyReportService(snapshot={})

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertFalse(daily_report_view_has_required_facts(view))
        self.assertIn("明日动作", missing_required_fact_labels(view))
        self.assertIn("市场结构", missing_required_fact_labels(view))
        self.assertIn("Top50成交额占比", missing_required_fact_labels(view))
        self.assertIn("主线证据", missing_required_fact_labels(view))
        self.assertEqual(service.loaded_dates, ["2026-06-05"])
        self.assertEqual(view["diagnostics"]["large_json_artifact"], False)

    def test_negative_participation_text_without_bool_is_not_participation(self):
        for final_action in (
            "空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
            "未出现执行资格前不新增参与",
            "不执行，只观察",
        ):
            with self.subTest(final_action=final_action):
                service = FakePostgresDailyReportService(
                    snapshot={
                        "market_research_snapshot": {
                            "front_page_final_gate": {
                                "final_action": final_action,
                            }
                        },
                        "market_stats": {"up_count": 2600, "down_count": 2100},
                        "total_turnover": 1000,
                    }
                )

                view = build_daily_report_view("2026-06-05", service, run_mode="replay")

                self.assertEqual(view["tomorrow_action"]["action_summary"], final_action)
                self.assertFalse(view["tomorrow_action"]["can_participate"])

    def test_non_participation_keeps_watch_target_as_observation_not_primary_target(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {
                        "final_action": "0%不参与，只观察",
                        "allow_new_entry": False,
                    },
                    "final_target_resolution": {
                        "watch_target": {"name": "双星新材", "code": "002585"},
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
            }
        )

        view = build_daily_report_view("2026-06-10", service, run_mode="replay")

        self.assertFalse(view["tomorrow_action"]["can_participate"])
        self.assertEqual(view["tomorrow_action"]["primary_target"], {})
        self.assertEqual(view["tomorrow_action"]["observation_target"]["code"], "002585")

    def test_empty_selection_workflow_final_blocks_stale_selected_candidate_in_html_view(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {"execution_object": {}, "position_pct": 0},
        }
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {
                        "final_action": "0%不参与，只观察",
                        "allow_new_entry": False,
                    },
                    "selection_workflow": workflow,
                    "selected_position_candidate": {
                        "name": "和远气体",
                        "code": "002971",
                        "candidate_role": "过程候选",
                        "observation_layer": "process_observation",
                    },
                },
                "selected_position_candidate": {"name": "和远气体", "code": "002971"},
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
            }
        )

        view = build_daily_report_view("2026-06-10", service, run_mode="replay")

        self.assertFalse(view["tomorrow_action"]["can_participate"])
        self.assertEqual(view["tomorrow_action"]["primary_target"], {})
        self.assertEqual(view["tomorrow_action"]["observation_target"], {})

    def test_nested_execution_context_empty_selection_workflow_blocks_stale_html_candidate(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {"execution_object": {}, "position_pct": 0},
        }
        stale = {"name": "和远气体", "code": "002971"}
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {
                        "final_action": "0%不参与，只观察",
                        "allow_new_entry": False,
                    },
                    "selected_position_candidate": dict(stale),
                },
                "execution_stage_context": {
                    "selection_workflow": workflow,
                    "selected_position_candidate": dict(stale),
                },
                "selected_position_candidate": dict(stale),
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
            }
        )

        view = build_daily_report_view("2026-06-10", service, run_mode="replay")

        self.assertFalse(view["tomorrow_action"]["can_participate"])
        self.assertEqual(view["tomorrow_action"]["primary_target"], {})
        self.assertEqual(view["tomorrow_action"]["observation_target"], {})

    def test_html_view_rejects_process_watch_target_when_final_is_empty(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {"execution_object": {}, "position_pct": 0},
        }
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {
                        "final_action": "0%不参与，只观察",
                        "allow_new_entry": False,
                    },
                    "selection_workflow": workflow,
                    "final_target_resolution": {
                        "watch_target": {
                            "name": "和远气体",
                            "code": "002971",
                            "front_observation_qualified": True,
                            "observation_layer": "process_observation",
                            "identity": "过程候选",
                        },
                        "capital_priority_decision": {"capital_priority": "wait"},
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
            }
        )

        view = build_daily_report_view("2026-06-10", service, run_mode="replay")

        self.assertFalse(view["tomorrow_action"]["can_participate"])
        self.assertEqual(view["tomorrow_action"]["primary_target"], {})
        self.assertEqual(view["tomorrow_action"]["observation_target"], {})

        service = FakePostgresDailyReportService(
            snapshot={
                "selection_workflow": workflow,
                "market_research_snapshot": {
                    "front_page_final_gate": {
                        "final_action": "0%不参与，只观察",
                        "allow_new_entry": False,
                    },
                    "selected_position_candidate": {"name": "和远气体", "code": "002971"},
                },
                "selected_position_candidate": {"name": "和远气体", "code": "002971"},
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
            }
        )

        view = build_daily_report_view("2026-06-10", service, run_mode="replay")

        self.assertFalse(view["tomorrow_action"]["can_participate"])
        self.assertEqual(view["tomorrow_action"]["primary_target"], {})
        self.assertEqual(view["tomorrow_action"]["observation_target"], {})

    def test_reads_current_runtime_decision_fields_and_target(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {
                        "final_action": "50%条件执行，条件满足才50%条件执行",
                    },
                    "position_decision": {
                        "target_position_pct": 50,
                        "trigger_text": "09:50-10:10窗口确认承接",
                    },
                    "two_layer_decision_payload": {
                        "front_decision": {
                            "position_plan": "50%条件执行",
                            "execution_object": {"name": "豫能控股", "code": "001896"},
                        }
                    },
                    "final_target_resolution": {
                        "watch_target": {"name": "豫能控股", "code": "001896"},
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertEqual(view["tomorrow_action"]["position_state"], "50%")
        self.assertTrue(view["tomorrow_action"]["can_participate"])
        self.assertEqual(view["tomorrow_action"]["primary_target"]["code"], "001896")
        self.assertIn("09:50-10:10", view["tomorrow_action"]["participation_window"])

    def test_normalizes_numeric_position_pct_to_allowed_three_states(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {
                        "final_action": "条件成立才参与",
                        "allow_new_entry": True,
                        "target_position_pct": 75,
                    },
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
            }
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertEqual(view["tomorrow_action"]["position_state"], "50%")
        self.assertNotEqual(view["tomorrow_action"]["position_state"], "75%")


if __name__ == "__main__":
    unittest.main()
