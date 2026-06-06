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
    def __init__(self, *, snapshot=None, mentions=None, coverage=None):
        self.snapshot = snapshot or {}
        self.mentions = mentions or []
        self.coverage = coverage or {
            "tables": {
                "daily_report_fact_fields": {"target_count": 8, "max_trade_date": "2026-06-05"},
                "sector_attack_evidence_daily": {"target_count": 2, "max_trade_date": "2026-06-05"},
            }
        }
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

    def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
        return list(self.mentions)


class DailyReportHtmlViewTest(unittest.TestCase):
    def test_builds_view_from_postgres_facts_without_large_json_artifact(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_decision": {
                        "final_action": "0% / 不参与，等待主线承接重新出现",
                        "max_position": "0%",
                        "allow_new_entry": False,
                        "cancel_conditions": ["成交额继续萎缩", "主线扩散不足"],
                    }
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
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
        self.assertEqual(view["market_spine"]["turnover_summary"], "1000")
        self.assertEqual(view["mainline_evidence"]["confirmed_line"], "电力")
        self.assertEqual(view["candidate_actions"][0]["stock_code"], "001896")
        self.assertEqual(view["diagnostics"]["large_json_artifact"], False)
        self.assertTrue(daily_report_view_has_required_facts(view))
        self.assertEqual(missing_required_fact_labels(view), [])

    def test_missing_required_facts_are_reported_without_reading_live_sources(self):
        service = FakePostgresDailyReportService(snapshot={})

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertFalse(daily_report_view_has_required_facts(view))
        self.assertIn("明日动作", missing_required_fact_labels(view))
        self.assertIn("市场结构", missing_required_fact_labels(view))
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

    def test_reads_current_runtime_decision_fields_and_target(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_final_gate": {
                        "final_action": "50%标准进攻，条件满足才B档执行",
                    },
                    "position_decision": {
                        "target_position_pct": 50,
                        "trigger_text": "09:50-10:10窗口确认承接",
                    },
                    "two_layer_decision_payload": {
                        "front_decision": {
                            "position_plan": "B档执行",
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


if __name__ == "__main__":
    unittest.main()
