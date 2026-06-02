import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.decision_statistics import (
    build_five_judgment_statistics,
    render_five_judgment_statistics_lines,
)


class DecisionStatisticsTest(unittest.TestCase):
    def test_builds_exactly_five_judgment_accuracy_rows(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "mentions": [{"mention_trade_date": "2026-05-11", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {
                                "judgment_type": "market_state",
                                "report_date": "2026-05-11",
                                "is_correct": True,
                            },
                            {
                                "judgment_type": "mainline",
                                "report_date": "2026-05-11",
                                "is_correct": False,
                                "mistake": "资金次日没有继续选择电力",
                            },
                            {
                                "judgment_type": "core_candidate",
                                "report_date": "2026-05-11",
                                "is_correct": True,
                            },
                            {
                                "judgment_type": "participation_rehearsal",
                                "report_date": "2026-05-11",
                                "is_correct": False,
                                "mistake": "竞价命中但开盘承接断档",
                            },
                            {
                                "judgment_type": "cancellation_condition",
                                "report_date": "2026-05-11",
                                "is_correct": True,
                            },
                        ],
                    },
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "mentions": [{"mention_trade_date": "2026-05-12", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {
                                "judgment_type": "market_state",
                                "report_date": "2026-05-12",
                                "is_correct": None,
                                "missing_fields": ["next_day_market_state"],
                            },
                            {
                                "judgment_type": "mainline",
                                "report_date": "2026-05-12",
                                "is_correct": True,
                            },
                        ],
                    },
                ]
            }
        }

        result = build_five_judgment_statistics(index)

        rows = result["rows"]
        self.assertEqual(
            [row["judgment_type"] for row in rows],
            [
                "market_state",
                "mainline",
                "core_candidate",
                "participation_rehearsal",
                "cancellation_condition",
            ],
        )
        market_row = rows[0]
        self.assertEqual(market_row["sample_count"], 1)
        self.assertEqual(market_row["correct_count"], 1)
        self.assertEqual(market_row["missing_fact_count"], 1)
        self.assertEqual(market_row["accuracy_pct"], 100.0)
        self.assertEqual(market_row["start_date"], "2026-05-11")
        self.assertEqual(market_row["end_date"], "2026-05-12")

        mainline_row = rows[1]
        self.assertEqual(mainline_row["sample_count"], 2)
        self.assertEqual(mainline_row["correct_count"], 1)
        self.assertEqual(mainline_row["accuracy_pct"], 50.0)
        self.assertEqual(mainline_row["latest_mistake"], "资金次日没有继续选择电力")

    def test_renderer_outputs_review_table_with_accuracy_and_mistakes(self):
        stats = {
            "sample_count": 2,
            "start_date": "2026-05-11",
            "end_date": "2026-05-12",
            "rows": [
                {
                    "judgment_type": "market_state",
                    "label": "市场状态判断",
                    "metric_definition": "进攻/退潮/修复/混沌/冰点是否被次日走势验证",
                    "sample_count": 1,
                    "correct_count": 1,
                    "wrong_count": 0,
                    "missing_fact_count": 1,
                    "accuracy_pct": 100.0,
                    "latest_mistake": "",
                },
                {
                    "judgment_type": "mainline",
                    "label": "主线判断",
                    "metric_definition": "资金第二天是否继续选择这条线",
                    "sample_count": 2,
                    "correct_count": 1,
                    "wrong_count": 1,
                    "missing_fact_count": 0,
                    "accuracy_pct": 50.0,
                    "latest_mistake": "资金次日没有继续选择电力",
                },
                {
                    "judgment_type": "core_candidate",
                    "label": "核心候选判断",
                    "metric_definition": "选出的票是否进入资金视野",
                    "sample_count": 1,
                    "correct_count": 1,
                    "wrong_count": 0,
                    "missing_fact_count": 0,
                    "accuracy_pct": 100.0,
                    "latest_mistake": "",
                },
                {
                    "judgment_type": "participation_rehearsal",
                    "label": "参与预演判断",
                    "metric_definition": "竞价、开盘、回封、分歧路径是否命中",
                    "sample_count": 1,
                    "correct_count": 0,
                    "wrong_count": 1,
                    "missing_fact_count": 0,
                    "accuracy_pct": 0.0,
                    "latest_mistake": "竞价命中但开盘承接断档",
                },
                {
                    "judgment_type": "cancellation_condition",
                    "label": "取消条件判断",
                    "metric_definition": "不买、空仓、放弃追高是否避免错误参与",
                    "sample_count": 1,
                    "correct_count": 1,
                    "wrong_count": 0,
                    "missing_fact_count": 0,
                    "accuracy_pct": 100.0,
                    "latest_mistake": "",
                },
            ],
        }

        lines = render_five_judgment_statistics_lines(stats)
        rendered = "\n".join(lines)

        self.assertIn("**五项判断复盘统计表**", rendered)
        self.assertIn("当前可复盘样本：2条，覆盖2026-05-11至2026-05-12", rendered)
        self.assertIn("| 判断项 | 统计口径 | 样本 | 正确 | 错误 | 待补事实 | 正确率 | 错在哪 |", rendered)
        self.assertIn("| 主线判断 | 资金第二天是否继续选择这条线 | 2 | 1 | 1 | 0 | 50.00% | 资金次日没有继续选择电力 |", rendered)
        self.assertIn("| 参与预演判断 | 竞价、开盘、回封、分歧路径是否命中 | 1 | 0 | 1 | 0 | 0.00% | 竞价命中但开盘承接断档 |", rendered)
        self.assertIn("历史复盘只统计过去判断，不作为明日新增参与依据。", rendered)

    def test_falls_back_to_participation_and_cancellation_reviews(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "planned_participation": {"source_tier": "extreme_conviction"},
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-11",
                                "source_section": "极度看好名单",
                                "participation_review": {
                                    "status": "预演作废",
                                    "reason": "作废条件出现，原参与方案不再成立。",
                                    "fact_inputs": {"cancellation_triggered": True},
                                },
                            }
                        ],
                    }
                ]
            }
        }

        result = build_five_judgment_statistics(index)
        rows = {row["judgment_type"]: row for row in result["rows"]}

        self.assertEqual(rows["participation_rehearsal"]["sample_count"], 1)
        self.assertEqual(rows["participation_rehearsal"]["wrong_count"], 1)
        self.assertIn("预演作废", rows["participation_rehearsal"]["latest_mistake"])
        self.assertEqual(rows["cancellation_condition"]["sample_count"], 1)
        self.assertEqual(rows["cancellation_condition"]["correct_count"], 1)

    def test_missing_fields_keep_explicit_correctness_out_of_accuracy_denominator(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "mentions": [{"mention_trade_date": "2026-05-11", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {
                                "judgment_type": "market_state",
                                "report_date": "2026-05-11",
                                "is_correct": True,
                                "missing_fields": ["next_day_market_state"],
                            }
                        ],
                    }
                ]
            }
        }

        result = build_five_judgment_statistics(index)
        market_row = result["rows"][0]

        self.assertEqual(market_row["sample_count"], 0)
        self.assertEqual(market_row["correct_count"], 0)
        self.assertEqual(market_row["missing_fact_count"], 1)
        self.assertIsNone(market_row["accuracy_pct"])

    def test_participation_review_status_alias_counts_spec_review_rows(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "planned_participation": {"source_tier": "extreme_conviction"},
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-11",
                                "source_section": "极度看好名单",
                                "participation_review": {
                                    "review_status": "预演命中",
                                    "fact_inputs": {"auction_matched": True, "first_minutes_accepted": True},
                                },
                            }
                        ],
                    }
                ]
            }
        }

        result = build_five_judgment_statistics(index)
        rows = {row["judgment_type"]: row for row in result["rows"]}

        self.assertEqual(rows["participation_rehearsal"]["sample_count"], 1)
        self.assertEqual(rows["participation_rehearsal"]["correct_count"], 1)
        self.assertEqual(rows["participation_rehearsal"]["missing_fact_count"], 0)

    def test_mention_level_judgment_reviews_use_their_own_mention_date(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-11",
                                "source_section": "极度看好名单",
                                "judgment_reviews": [
                                    {
                                        "judgment_type": "mainline",
                                        "is_correct": False,
                                        "mistake": "第一天错",
                                    }
                                ],
                            },
                            {
                                "mention_trade_date": "2026-05-12",
                                "source_section": "极度看好名单",
                                "judgment_reviews": [
                                    {
                                        "judgment_type": "mainline",
                                        "is_correct": False,
                                        "mistake": "第二天错",
                                    }
                                ],
                            },
                        ],
                    }
                ]
            }
        }

        result = build_five_judgment_statistics(index)
        mainline_row = result["rows"][1]

        self.assertEqual(mainline_row["start_date"], "2026-05-11")
        self.assertEqual(mainline_row["end_date"], "2026-05-12")
        self.assertEqual(mainline_row["latest_mistake"], "第二天错")

    def test_falls_back_to_existing_validation_and_selection_fields(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "report_date": "2026-05-11",
                        "validation": {
                            "status": "市场选择确认",
                            "sector_selection_evidence": "电力方向成交额占比抬升",
                        },
                        "selection_result": {
                            "status": "识别成功",
                            "evidence": "京能电力次日进入资金视野",
                        },
                        "mentions": [{"mention_trade_date": "2026-05-11", "source_section": "极度看好名单"}],
                    },
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "report_date": "2026-05-12",
                        "validation": {
                            "status": "真正失败",
                            "failure_reason": "所属方向持续失去选择",
                        },
                        "selection_result": {
                            "status": "识别失败",
                            "lesson": "个股没有进入资金视野",
                        },
                        "mentions": [{"mention_trade_date": "2026-05-12", "source_section": "极度看好名单"}],
                    },
                ]
            }
        }

        result = build_five_judgment_statistics(index)
        rows = {row["judgment_type"]: row for row in result["rows"]}

        self.assertEqual(rows["mainline"]["sample_count"], 2)
        self.assertEqual(rows["mainline"]["correct_count"], 1)
        self.assertEqual(rows["mainline"]["wrong_count"], 1)
        self.assertIn("所属方向持续失去选择", rows["mainline"]["latest_mistake"])
        self.assertEqual(rows["core_candidate"]["sample_count"], 2)
        self.assertEqual(rows["core_candidate"]["correct_count"], 1)
        self.assertEqual(rows["core_candidate"]["wrong_count"], 1)
        self.assertEqual(rows["core_candidate"]["latest_mistake"], "个股没有进入资金视野")


if __name__ == "__main__":
    unittest.main()
