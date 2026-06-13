import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.decision_statistics import (
    build_daily_judgment_review_panel,
    build_five_judgment_statistics,
    render_daily_judgment_review_panel_lines,
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
                    "latest_result": "错误",
                    "latest_expected": "电力",
                    "latest_actual": "通信设备",
                    "latest_reason": "资金次日没有继续选择电力",
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
                    "latest_result": "错误",
                    "latest_expected": "竞价命中",
                    "latest_actual": "开盘承接断档",
                    "latest_reason": "竞价命中但开盘承接断档",
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
        self.assertIn("统计范围：2026-05-11至2026-05-12", rendered)
        self.assertNotIn("当前可复盘样本", rendered)
        self.assertIn("| 判断项 | 统计口径 | 正确率 | 最近结论 | 预期 | 实际 | 原因 |", rendered)
        self.assertNotIn("| 判断项 | 统计口径 | 样本 | 正确 | 错误 | 待补事实 | 正确率 | 错在哪 |", rendered)
        self.assertIn("| 主线判断 | 资金第二天是否继续选择这条线 | 50.00% | 错误 | 电力 | 通信设备 | 资金次日没有继续选择电力 |", rendered)
        self.assertIn("| 参与预演判断 | 竞价、开盘、回封、分歧路径是否命中 | 0.00% | 错误 | 竞价命中 | 开盘承接断档 | 竞价命中但开盘承接断档 |", rendered)
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

    def test_same_day_participation_and_cancellation_reviews_remain_separate_samples(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-29",
                                "source_section": "极度看好名单",
                                "participation_review": {
                                    "status": "预演命中",
                                    "fact_inputs": {
                                        "auction_matched": True,
                                        "first_minutes_accepted": True,
                                        "cancellation_triggered": True,
                                    },
                                },
                            }
                        ],
                    }
                ],
                "002806": [
                    {
                        "stock_code": "002806",
                        "stock_name": "华锋股份",
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-29",
                                "source_section": "极度看好名单",
                                "participation_review": {
                                    "status": "预演作废",
                                    "reason": "作废条件出现，原参与方案不再成立。",
                                    "fact_inputs": {"cancellation_triggered": True},
                                },
                            }
                        ],
                    }
                ],
            }
        }

        result = build_five_judgment_statistics(index, target_date="2026-06-01")
        rows = {row["judgment_type"]: row for row in result["rows"]}

        self.assertEqual(rows["participation_rehearsal"]["sample_count"], 2)
        self.assertEqual(rows["participation_rehearsal"]["correct_count"], 1)
        self.assertEqual(rows["participation_rehearsal"]["wrong_count"], 1)
        self.assertEqual(rows["cancellation_condition"]["sample_count"], 2)
        self.assertEqual(rows["cancellation_condition"]["correct_count"], 1)
        self.assertEqual(rows["cancellation_condition"]["wrong_count"], 1)

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

    def test_target_date_is_not_counted_in_historical_statistics(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "mentions": [{"mention_trade_date": "2026-05-29", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {
                                "judgment_type": "mainline",
                                "report_date": "2026-05-29",
                                "is_correct": True,
                            }
                        ],
                    },
                    {
                        "stock_code": "600578",
                        "mentions": [{"mention_trade_date": "2026-06-01", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {
                                "judgment_type": "mainline",
                                "report_date": "2026-06-01",
                                "is_correct": False,
                                "mistake": "当天判断还没有次日验证",
                            }
                        ],
                    },
                ]
            }
        }

        result = build_five_judgment_statistics(index, target_date="2026-06-01")
        mainline_row = result["rows"][1]

        self.assertEqual(mainline_row["sample_count"], 1)
        self.assertEqual(mainline_row["correct_count"], 1)
        self.assertEqual(mainline_row["wrong_count"], 0)
        self.assertEqual(mainline_row["end_date"], "2026-05-29")
        self.assertEqual(mainline_row["latest_mistake"], "")

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

    def test_core_candidate_fallback_reason_does_not_duplicate_actual_evidence(self):
        evidence = "京能电力次日进入资金视野，进入hot_rank_top50，进入integrated_hot_list"
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "report_date": "2026-05-11",
                        "selection_result": {
                            "status": "识别成功",
                            "evidence": evidence,
                        },
                        "mentions": [{"mention_trade_date": "2026-05-11", "source_section": "极度看好名单"}],
                    }
                ]
            }
        }

        result = build_five_judgment_statistics(index)
        row = {item["judgment_type"]: item for item in result["rows"]}["core_candidate"]

        self.assertEqual(row["latest_actual"], evidence)
        self.assertEqual(row["latest_reason"], "候选进入次日资金视野，判断成立")
        self.assertNotEqual(row["latest_actual"], row["latest_reason"])

    def test_daily_panel_separates_previous_settlement_today_judgment_and_recent_window(self):
        index = {
            "available_trade_dates": [
                "2026-05-25",
                "2026-05-26",
                "2026-05-27",
                "2026-05-28",
                "2026-05-29",
                "2026-06-01",
            ],
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "mentions": [{"mention_trade_date": "2026-05-25", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {"judgment_type": "market_state", "report_date": "2026-05-25", "is_correct": True},
                            {"judgment_type": "mainline", "report_date": "2026-05-25", "is_correct": True},
                        ],
                    },
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "mentions": [{"mention_trade_date": "2026-05-26", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {"judgment_type": "market_state", "report_date": "2026-05-26", "is_correct": False, "mistake": "退潮判断偏晚"},
                            {"judgment_type": "mainline", "report_date": "2026-05-26", "is_correct": True},
                        ],
                    },
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "mentions": [{"mention_trade_date": "2026-05-27", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {"judgment_type": "market_state", "report_date": "2026-05-27", "is_correct": True},
                            {"judgment_type": "mainline", "report_date": "2026-05-27", "is_correct": False, "mistake": "资金没有继续选择电力"},
                        ],
                    },
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "mentions": [{"mention_trade_date": "2026-05-28", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {"judgment_type": "market_state", "report_date": "2026-05-28", "is_correct": True},
                            {"judgment_type": "mainline", "report_date": "2026-05-28", "is_correct": True},
                        ],
                    },
                ],
                "002806": [
                    {
                        "stock_code": "002806",
                        "stock_name": "华锋股份",
                        "latest_trade_date": "2026-06-01",
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-29",
                                "source_section": "极度看好名单",
                                "participation_review": {
                                    "status": "预演作废",
                                    "reason": "作废条件出现，原参与方案不再成立。",
                                    "missing_fields": ["return_3d_pct", "return_5d_pct"],
                                    "fact_inputs": {"cancellation_triggered": True},
                                },
                            }
                        ],
                        "judgment_reviews": [
                            {"judgment_type": "market_state", "report_date": "2026-05-29", "is_correct": False, "mistake": "混沌判断偏乐观"},
                            {"judgment_type": "mainline", "report_date": "2026-05-29", "is_correct": True},
                            {"judgment_type": "core_candidate", "report_date": "2026-05-29", "is_correct": True},
                        ],
                    }
                ],
                "000539": [
                    {
                        "stock_code": "000539",
                        "stock_name": "粤电力Ａ",
                        "mentions": [{"mention_trade_date": "2026-06-01", "source_section": "极度看好名单"}],
                        "planned_participation": {
                            "buy_window": "09:30-09:35",
                            "cancellation": "竞价表态、开盘承接、板块同步任一失败，按0%不参与",
                        },
                    }
                ],
            },
        }
        context = {
            "market_state": "混沌",
            "mainline": "新型电力",
            "core_candidates": [{"stock_name": "粤电力Ａ", "stock_code": "000539"}],
            "participation_rehearsal": "09:30-09:35看竞价、开盘承接、回封质量",
            "cancellation_condition": "竞价表态、开盘承接、板块同步任一失败，按0%不参与",
        }

        panel = build_daily_judgment_review_panel(index, "2026-06-01", current_context=context, recent_days=5)
        rendered = "\n".join(render_daily_judgment_review_panel_lines(panel))

        self.assertEqual(panel["previous_trade_date"], "2026-05-29")
        self.assertEqual(panel["recent_start_date"], "2026-05-25")
        self.assertEqual(panel["recent_end_date"], "2026-05-29")
        previous_rows = {row["judgment_type"]: row for row in panel["previous_rows"]}
        self.assertEqual(previous_rows["participation_rehearsal"]["wrong_count"], 1)
        self.assertEqual(previous_rows["cancellation_condition"]["correct_count"], 1)
        today_rows = {row["judgment_type"]: row for row in panel["today_rows"]}
        self.assertIn("粤电力Ａ(000539)", today_rows["core_candidate"]["today_judgment"])
        self.assertNotIn("华锋股份", today_rows["core_candidate"]["today_judgment"])
        self.assertIn("近5个已结算交易日正确率", rendered)
        self.assertIn("结算上一交易日：2026-05-29", rendered)
        self.assertIn("今日判断（2026-06-01，等待下一交易日验证）", rendered)
        self.assertNotIn("### 近5个已结算交易日正确率", rendered)
        self.assertNotIn("### 结算上一交易日：2026-05-29", rendered)
        self.assertNotIn("### 今日判断（2026-06-01，等待下一交易日验证）", rendered)
        self.assertIn("| 市场状态判断 | 混沌 | 下一交易日验证进攻/退潮/修复/混沌/冰点是否成立 |", rendered)

    def test_daily_panel_renders_recent_rows_as_expected_actual_reason(self):
        index = {
            "available_trade_dates": ["2026-05-28", "2026-05-29", "2026-06-01"],
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "mentions": [{"mention_trade_date": "2026-05-29", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {
                                "judgment_type": "market_state",
                                "report_date": "2026-05-29",
                                "expected": "混沌",
                                "actual": "退潮",
                                "is_correct": False,
                                "mistake": "预判混沌，次日实际为退潮",
                            },
                            {
                                "judgment_type": "mainline",
                                "report_date": "2026-05-29",
                                "expected": "无确认主线",
                                "actual": "无确认主线",
                                "is_correct": True,
                                "evidence": "次日主线仍无确认主线",
                            },
                            {
                                "judgment_type": "core_candidate",
                                "report_date": "2026-05-29",
                                "expected": "京能电力(600578)",
                                "actual": "京能电力(600578)进入hot_rank_top50、京能电力(600578)进入integrated_hot_list",
                                "is_correct": True,
                                "evidence": "京能电力(600578)进入hot_rank_top50、京能电力(600578)进入integrated_hot_list",
                            },
                        ],
                    }
                ]
            },
        }

        panel = build_daily_judgment_review_panel(
            index,
            "2026-06-01",
            current_context={"market_state": "混沌", "mainline": "无确认主线"},
            recent_days=5,
        )
        rendered = "\n".join(render_daily_judgment_review_panel_lines(panel))

        self.assertIn("| 判断项 | 正确率 | 最近结论 | 预期 | 实际 | 原因 |", rendered)
        self.assertNotIn("| 判断项 | 样本 | 正确 | 错误 | 待补事实 | 正确率 | 最近错因 |", rendered)
        self.assertIn("| 市场状态判断 | 0.00% | 错误 | 混沌 | 退潮 | 预判混沌，次日实际为退潮 |", rendered)
        self.assertIn(
            "| 核心候选判断 | 100.00% | 正确 | 京能电力(600578) | 候选进入次日资金视野 | 候选进入次日资金视野，判断成立 |",
            rendered,
        )
        self.assertNotIn("### 最近5日判断明细", rendered)
        self.assertNotIn("| 日期 | 判断项 | 结论 | 预期 | 实际 | 原因 |", rendered)
        self.assertNotIn("| 2026-05-29 | 市场状态判断 | 错误 | 混沌 | 退潮 | 预判混沌，次日实际为退潮 |", rendered)
        self.assertNotIn("| 2026-05-29 | 主线判断 | 正确 | 无确认主线 | 无确认主线 | 次日主线仍无确认主线 |", rendered)
        self.assertNotIn(
            "| 2026-05-29 | 核心候选判断 | 正确 | 京能电力(600578) | 京能电力(600578)进入hot_rank_top50、京能电力(600578)进入integrated_hot_list | 候选进入次日资金视野，判断成立 |",
            rendered,
        )
        self.assertNotIn(
            "| 京能电力(600578)进入hot_rank_top50、京能电力(600578)进入integrated_hot_list | 京能电力(600578)进入hot_rank_top50、京能电力(600578)进入integrated_hot_list |",
            rendered,
        )

    def test_daily_panel_keeps_observation_candidates_out_of_core_judgment(self):
        panel = build_daily_judgment_review_panel(
            {"available_trade_dates": ["2026-05-29", "2026-06-01"], "by_stock_code": {}},
            "2026-06-01",
            current_context={
                "market_state": "混沌",
                "mainline": "通信设备",
                "core_candidates": [
                    {
                        "name": "工业富联",
                        "code": "601138",
                        "sniper_role": "明日主买对象",
                        "anchor_reversal_decision": "可作为主对象",
                    },
                    {
                        "name": "亨通光电",
                        "code": "600487",
                        "sniper_role": "候选观察",
                        "anchor_reversal_decision": "降级观察",
                    },
                    {
                        "name": "中天科技",
                        "code": "600522",
                        "sniper_role": "候选观察补充",
                        "anchor_reversal_decision": "降级观察",
                    },
                ],
            },
            recent_days=5,
        )
        rows = {row["judgment_type"]: row for row in panel["today_rows"]}

        self.assertEqual(rows["core_candidate"]["today_judgment"], "工业富联(601138)")
        self.assertNotIn("亨通光电", rows["core_candidate"]["today_judgment"])
        self.assertNotIn("中天科技", rows["core_candidate"]["today_judgment"])

    def test_daily_panel_filters_target_date_ledger_observation_records(self):
        index = {
            "available_trade_dates": ["2026-05-29", "2026-06-01"],
            "by_stock_code": {
                "601138": [
                    {
                        "stock_name": "工业富联",
                        "stock_code": "601138",
                        "report_date": "2026-06-01",
                        "sniper_role": "明日主买对象",
                        "anchor_reversal_decision": "可作为主对象",
                    }
                ],
                "600487": [
                    {
                        "stock_name": "亨通光电",
                        "stock_code": "600487",
                        "report_date": "2026-06-01",
                        "sniper_role": "候选观察",
                        "anchor_reversal_decision": "降级观察",
                    }
                ],
            },
        }

        panel = build_daily_judgment_review_panel(
            index,
            "2026-06-01",
            current_context={"market_state": "混沌", "mainline": "通信设备"},
            recent_days=5,
        )
        rows = {row["judgment_type"]: row for row in panel["today_rows"]}

        self.assertEqual(rows["core_candidate"]["today_judgment"], "工业富联(601138)")
        self.assertNotIn("亨通光电", rows["core_candidate"]["today_judgment"])

    def test_daily_panel_prefers_current_primary_over_stale_same_day_ledger_records(self):
        index = {
            "available_trade_dates": ["2026-05-29", "2026-06-01"],
            "by_stock_code": {
                "601138": [
                    {
                        "stock_name": "工业富联",
                        "stock_code": "601138",
                        "report_date": "2026-06-01",
                    }
                ],
                "600487": [
                    {
                        "stock_name": "亨通光电",
                        "stock_code": "600487",
                        "report_date": "2026-06-01",
                    }
                ],
                "600522": [
                    {
                        "stock_name": "中天科技",
                        "stock_code": "600522",
                        "report_date": "2026-06-01",
                    }
                ],
            },
        }

        panel = build_daily_judgment_review_panel(
            index,
            "2026-06-01",
            current_context={
                "market_state": "混沌",
                "mainline": "通信设备",
                "core_candidates": [
                    {
                        "name": "工业富联",
                        "code": "601138",
                        "sniper_role": "明日主买对象",
                        "anchor_reversal_decision": "可作为主对象",
                    }
                ],
            },
            recent_days=5,
        )
        rows = {row["judgment_type"]: row for row in panel["today_rows"]}

        self.assertEqual(rows["core_candidate"]["today_judgment"], "工业富联(601138)")
        self.assertNotIn("亨通光电", rows["core_candidate"]["today_judgment"])
        self.assertNotIn("中天科技", rows["core_candidate"]["today_judgment"])

    def test_daily_panel_normalizes_empty_today_mainline_to_chaotic_market_state(self):
        index = {
            "available_trade_dates": ["2026-05-29", "2026-06-01"],
            "by_stock_code": {},
        }

        panel = build_daily_judgment_review_panel(
            index,
            "2026-06-01",
            current_context={"market_state": "", "mainline": "暂无"},
            recent_days=5,
        )
        rows = {row["judgment_type"]: row for row in panel["today_rows"]}

        self.assertEqual(rows["market_state"]["today_judgment"], "混沌")
        self.assertEqual(rows["mainline"]["today_judgment"], "无确认主线")

    def test_daily_panel_normalizes_defensive_market_state_to_retreat_bucket(self):
        panel = build_daily_judgment_review_panel(
            {"available_trade_dates": ["2026-05-29", "2026-06-01"], "by_stock_code": {}},
            "2026-06-01",
            current_context={"market_state": "收缩防守", "mainline": "无确认主线"},
            recent_days=5,
        )
        rows = {row["judgment_type"]: row for row in panel["today_rows"]}

        self.assertEqual(rows["market_state"]["today_judgment"], "退潮")

    def test_daily_panel_counts_one_unresolved_daily_judgment_per_trade_date(self):
        index = {
            "available_trade_dates": ["2026-05-29", "2026-06-01"],
            "by_stock_code": {
                "000001": [
                    {
                        "stock_code": "000001",
                        "mentions": [{"mention_trade_date": "2026-05-29", "source_section": "极度看好名单"}],
                    }
                ],
                "000002": [
                    {
                        "stock_code": "000002",
                        "mentions": [{"mention_trade_date": "2026-05-29", "source_section": "极度看好名单"}],
                    }
                ],
                "000003": [
                    {
                        "stock_code": "000003",
                        "mentions": [{"mention_trade_date": "2026-05-29", "source_section": "极度看好名单"}],
                    }
                ],
            },
        }

        panel = build_daily_judgment_review_panel(
            index,
            "2026-06-01",
            current_context={"market_state": "混沌", "mainline": "无确认主线"},
            recent_days=5,
        )
        rendered = "\n".join(render_daily_judgment_review_panel_lines(panel))
        previous_rows = {row["judgment_type"]: row for row in panel["previous_rows"]}

        self.assertEqual(previous_rows["market_state"]["missing_fact_count"], 1)
        self.assertEqual(previous_rows["mainline"]["missing_fact_count"], 1)
        self.assertEqual(previous_rows["core_candidate"]["missing_fact_count"], 1)
        self.assertIn("| 市场状态判断 | 待补事实 | market_state_review |", rendered)
        self.assertNotIn("| 市场状态判断 | 3 | market_state_review |", rendered)

    def test_previous_day_settlement_table_only_renders_resolved_items(self):
        index = {
            "available_trade_dates": ["2026-05-29", "2026-06-01"],
            "by_stock_code": {
                "002806": [
                    {
                        "stock_code": "002806",
                        "stock_name": "华锋股份",
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-29",
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
            },
        }

        panel = build_daily_judgment_review_panel(
            index,
            "2026-06-01",
            current_context={"market_state": "混沌", "mainline": "无确认主线"},
            recent_days=5,
        )
        rendered = "\n".join(render_daily_judgment_review_panel_lines(panel))
        settlement_block = rendered.split("**结算上一交易日：2026-05-29**", 1)[1].split("**上一交易日未完成结算**", 1)[0]

        self.assertNotIn("待补事实", settlement_block)
        self.assertNotIn("市场状态判断", settlement_block)
        self.assertNotIn("主线判断", settlement_block)
        self.assertNotIn("核心候选判断", settlement_block)
        self.assertIn(
            "| 参与预演判断 | 错误 | 预演路径按计划展开 | 预演作废 | 作废条件出现，原参与方案不再成立。 |",
            settlement_block,
        )
        self.assertIn(
            "| 取消条件判断 | 正确 | 取消条件出现时回到0%不参与 | 预演作废 | 作废条件出现，原参与方案不再成立。 |",
            settlement_block,
        )
        self.assertIn("**上一交易日未完成结算**", rendered)
        self.assertIn("| 市场状态判断 | 待补事实 | market_state_review |", rendered)

    def test_previous_day_mixed_settlement_keeps_missing_part_separate(self):
        index = {
            "available_trade_dates": ["2026-05-29", "2026-06-01"],
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "mentions": [{"mention_trade_date": "2026-05-29", "source_section": "极度看好名单"}],
                        "judgment_reviews": [
                            {
                                "judgment_type": "mainline",
                                "report_date": "2026-05-29",
                                "is_correct": True,
                            },
                            {
                                "judgment_type": "mainline",
                                "report_date": "2026-05-29",
                                "missing_fields": ["mainline_review"],
                            },
                        ],
                    }
                ]
            },
        }

        panel = build_daily_judgment_review_panel(
            index,
            "2026-06-01",
            current_context={"market_state": "混沌", "mainline": "无确认主线"},
            recent_days=5,
        )
        rendered = "\n".join(render_daily_judgment_review_panel_lines(panel))
        settlement_block = rendered.split("**结算上一交易日：2026-05-29**", 1)[1].split("**上一交易日未完成结算**", 1)[0]
        unresolved_block = rendered.split("**上一交易日未完成结算**", 1)[1].split("**今日判断", 1)[0]

        self.assertIn("| 主线判断 | 正确 | - | - | 符合预期 |", settlement_block)
        self.assertNotIn("部分正确", settlement_block)
        self.assertIn("| 主线判断 | 待补事实 | mainline_review |", unresolved_block)


if __name__ == "__main__":
    unittest.main()
