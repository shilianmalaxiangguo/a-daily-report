import sys
from tempfile import TemporaryDirectory
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.decision_ledger import (
    build_decision_ledger_snapshot,
    build_decision_ledger_snapshot_from_markdown_report,
    classify_cycle_acceptance,
    classify_validation_state,
    merge_snapshot_with_previous_index,
    parse_extreme_conviction_list_from_markdown,
    write_decision_ledger_artifacts_from_markdown_report,
    write_decision_ledger_artifacts,
)


class DecisionLedgerTest(unittest.TestCase):
    def test_parses_extreme_conviction_table_from_markdown_report(self):
        markdown = """
正文

**极度看好名单**（只保留最心动的少数，其他只观察）:
| 优先级 | 股票 | 代码 | 所属板块 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|
| 1 | 大唐发电 | 601991 | 电力 | 主线内核 / 板块锚定龙 / 首波先锋 / 分歧转一致形态 | 优先盯首个60分钟确认，若继续强就只做它 |
| 2 | 花王股份 | 603007 | 汽车零部 | 板块锚定龙 / 首波先锋 / 分歧转一致形态 | 只盯分歧后的转强，不追情绪顶点 |

**击球区结果**
"""

        items = parse_extreme_conviction_list_from_markdown(markdown)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["rank"], 1)
        self.assertEqual(items[0]["name"], "大唐发电")
        self.assertEqual(items[0]["code"], "601991")
        self.assertEqual(items[0]["sector"], "电力")
        self.assertIn("主线内核", items[0]["conviction_reason"])
        self.assertIn("60分钟确认", items[0]["conviction_rule"])

    def test_builds_snapshot_from_generated_markdown_report_table(self):
        markdown = """
**极度看好名单**（只保留最心动的少数，其他只观察）:
| 优先级 | 股票 | 代码 | 所属板块 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|
| 1 | 大唐发电 | 601991 | 电力 | 主线内核 / 板块锚定龙 | 优先盯首个60分钟确认 |
"""

        snapshot = build_decision_ledger_snapshot_from_markdown_report(
            markdown,
            trade_date="2026-05-12",
            market_branch="高位停顿轮动",
            sector_relationship_state="周期主线与当天主攻线一致",
            source_report={"path": "reports/2026-05-12_A股日报_完整版.md", "variant": "full"},
        )

        self.assertEqual(snapshot["trade_date"], "2026-05-12")
        self.assertEqual(snapshot["source_report"]["path"], "reports/2026-05-12_A股日报_完整版.md")
        self.assertEqual(len(snapshot["cases"]), 1)
        self.assertEqual(snapshot["cases"][0]["stock_code"], "601991")
        self.assertEqual(snapshot["cases"][0]["hypothesis"]["sector_candidate"], "电力")

    def test_writes_artifacts_from_generated_markdown_report_file(self):
        markdown = """
**极度看好名单**（只保留最心动的少数，其他只观察）:
| 优先级 | 股票 | 代码 | 所属板块 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|
| 1 | 大唐发电 | 601991 | 电力 | 主线内核 / 板块锚定龙 | 优先盯首个60分钟确认 |
"""
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            report_path = root / "reports" / "2026-05-12_A股日报_完整版.md"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(markdown, encoding="utf-8")

            result = write_decision_ledger_artifacts_from_markdown_report(
                report_path,
                trade_date="2026-05-12",
                market_branch="高位停顿轮动",
                sector_relationship_state="周期主线与当天主攻线一致",
                root_dir=root,
                generated_at="2026-05-13T15:00:00+08:00",
            )

            self.assertEqual(result["case_count"], 1)
            snapshot_path = root / "data" / "decision-ledger" / "2026-05-12.json"
            index_path = root / "data" / "decision-ledger" / "index.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["source_report"]["path"], "reports/2026-05-12_A股日报_完整版.md")
            self.assertEqual(index["latest_trade_date"], "2026-05-12")
            self.assertIn("601991", index["by_stock_code"])

    def test_builds_daily_snapshot_from_extreme_conviction_list(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {
                    "code": "601991.SH",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "趋势辨识度高 / 板块锚定龙",
                    "conviction_rule": "先看竞价承接，再等60分钟确认",
                    "pattern": "强实体异动",
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
            source_report={"path": "reports/2026-05-12_A股日报_完整版.md", "variant": "full"},
            generated_at="2026-05-13T00:00:00+08:00",
        )

        self.assertEqual(snapshot["artifact_version"], 1)
        self.assertEqual(snapshot["trade_date"], "2026-05-12")
        self.assertEqual(snapshot["source_report"]["variant"], "full")
        self.assertEqual(len(snapshot["cases"]), 1)

        case = snapshot["cases"][0]
        self.assertEqual(case["case_id"], "2026-05-12-601991-01")
        self.assertEqual(case["stock_code"], "601991")
        self.assertEqual(case["stock_name"], "大唐发电")
        self.assertEqual(case["cycle_day"], 1)
        self.assertEqual(case["cycle_length_trade_days"], 25)

        self.assertEqual(
            case["hypothesis"],
            {
                "stock_setup": "趋势辨识度高 / 板块锚定龙；强实体异动",
                "sector_candidate": "电力",
                "market_branch": "指数高位停顿轮动",
                "sector_relationship_state": "混沌接力",
            },
        )
        self.assertEqual(case["validation"]["status"], "等待市场选择")
        self.assertIsNone(case["validation"]["selection_confirmed_date"])
        self.assertEqual(case["mentions"][0]["mention_trade_date"], "2026-05-12")
        self.assertEqual(case["mentions"][0]["rank"], 1)
        self.assertEqual(case["mentions"][0]["source_section"], "极度看好名单")
        self.assertIn("趋势辨识度高", case["mentions"][0]["reason"])

    def test_same_stock_in_open_cycle_appends_mention(self):
        previous_index = {
            "by_stock_code": {
                "601991": [
                    {
                        "case_id": "2026-05-12-601991-01",
                        "stock_name": "大唐发电",
                        "cycle_start_trade_date": "2026-05-12",
                        "latest_trade_date": "2026-05-12",
                        "status": "等待市场选择",
                        "snapshot_path": "data/decision-ledger/2026-05-12.json",
                        "cycle_closed": False,
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-12",
                                "rank": 1,
                                "source_section": "极度看好名单",
                                "reason": "趋势辨识度高",
                            }
                        ],
                    }
                ]
            }
        }
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-13",
            extreme_conviction_list=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "板块回流后继续有承接",
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
            generated_at="2026-05-13T18:00:00+08:00",
        )

        merged = merge_snapshot_with_previous_index(snapshot, previous_index)
        case = merged["cases"][0]

        self.assertEqual(case["case_id"], "2026-05-12-601991-01")
        self.assertEqual(case["first_seen_trade_date"], "2026-05-12")
        self.assertEqual(case["cycle_start_trade_date"], "2026-05-12")
        self.assertEqual(case["cycle_day"], 2)
        self.assertEqual(len(case["mentions"]), 2)
        self.assertEqual(case["mentions"][1]["mention_trade_date"], "2026-05-13")
        self.assertIn("板块回流", case["mentions"][1]["reason"])

    def test_same_stock_after_closed_cycle_creates_new_case(self):
        previous_index = {
            "by_stock_code": {
                "601991": [
                    {
                        "case_id": "2026-04-01-601991-01",
                        "stock_name": "大唐发电",
                        "cycle_start_trade_date": "2026-04-01",
                        "latest_trade_date": "2026-05-11",
                        "status": "周期结束",
                        "snapshot_path": "data/decision-ledger/2026-05-11.json",
                        "cycle_closed": True,
                        "mentions": [
                            {
                                "mention_trade_date": "2026-04-01",
                                "rank": 1,
                                "source_section": "极度看好名单",
                                "reason": "旧周期",
                            }
                        ],
                    }
                ]
            }
        }
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-13",
            extreme_conviction_list=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "新周期再次进入名单",
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="继承",
            generated_at="2026-05-13T18:00:00+08:00",
        )

        merged = merge_snapshot_with_previous_index(snapshot, previous_index)
        case = merged["cases"][0]

        self.assertEqual(case["case_id"], "2026-05-13-601991-01")
        self.assertEqual(case["first_seen_trade_date"], "2026-05-13")
        self.assertEqual(case["cycle_start_trade_date"], "2026-05-13")
        self.assertEqual(case["cycle_day"], 1)
        self.assertEqual(len(case["mentions"]), 1)

    def test_validation_state_waits_when_stock_intact_and_sector_unselected(self):
        state = classify_validation_state(
            sector_selected=False,
            stock_acceptance=False,
            sector_path_lost=False,
            stock_structure_broken=False,
            stock_setup_intact=True,
        )

        self.assertEqual(state["status"], "等待市场选择")
        self.assertIsNone(state["selection_confirmed_date"])

    def test_validation_state_confirms_only_with_sector_and_stock_evidence(self):
        state = classify_validation_state(
            sector_selected=True,
            stock_acceptance=True,
            sector_selection_evidence="电力方向成交额占比抬升",
            stock_acceptance_evidence="分歧后承接稳定",
            confirmation_date="2026-05-13",
        )

        self.assertEqual(state["status"], "市场选择确认")
        self.assertEqual(state["selection_confirmed_date"], "2026-05-13")
        self.assertIn("电力", state["sector_selection_evidence"])
        self.assertIn("承接", state["stock_acceptance_evidence"])
        self.assertIn("电力", state["selection_confirmed_evidence"])

    def test_validation_state_fails_only_when_sector_lost_and_stock_breaks(self):
        state = classify_validation_state(
            sector_selected=False,
            stock_acceptance=False,
            sector_path_lost=True,
            stock_structure_broken=True,
            failure_reason="所属方向持续失去选择，个股跌破结构并失去承接",
        )

        self.assertEqual(state["status"], "真正失败")
        self.assertIn("结构", state["failure_reason"])

    def test_cycle_acceptance_labels_cover_controlled_outcomes(self):
        samples = [
            (
                {
                    "validation_status": "市场选择确认",
                    "trend_delivered": True,
                },
                "市场选择确认后趋势兑现",
            ),
            (
                {
                    "validation_status": "等待市场选择",
                    "stock_setup_intact": True,
                    "sector_branch_selected": False,
                    "market_selected_other_branch": False,
                },
                "等待市场选择但周期未验证",
            ),
            (
                {
                    "validation_status": "等待市场选择",
                    "stock_setup_intact": True,
                    "market_selected_other_branch": True,
                },
                "市场分支未选择且个股假设保留",
            ),
            (
                {
                    "validation_status": "真正失败",
                },
                "真正失败",
            ),
            (
                {
                    "eliminated_early": True,
                    "continued_strength_after_elimination": True,
                },
                "提前淘汰后继续走强",
            ),
        ]

        for signals, expected in samples:
            with self.subTest(expected=expected):
                result = classify_cycle_acceptance(**signals)
                self.assertEqual(result["status"], "closed")
                self.assertEqual(result["final_label"], expected)
                self.assertTrue(result["reason"])

    def test_writes_daily_snapshot_and_index_artifacts(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {
                    "code": "601991.SH",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "趋势辨识度高",
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
            generated_at="2026-05-13T00:00:00+08:00",
        )
        with TemporaryDirectory() as tempdir:
            result = write_decision_ledger_artifacts(snapshot, root_dir=Path(tempdir))

            snapshot_path = Path(tempdir) / "data" / "decision-ledger" / "2026-05-12.json"
            index_path = Path(tempdir) / "data" / "decision-ledger" / "index.json"
            self.assertEqual(result["snapshot_path"], str(snapshot_path))
            self.assertEqual(result["index_path"], str(index_path))
            self.assertTrue(snapshot_path.exists())
            self.assertTrue(index_path.exists())

            snapshot_text = snapshot_path.read_text(encoding="utf-8")
            index_text = index_path.read_text(encoding="utf-8")
            self.assertIn("大唐发电", snapshot_text)
            self.assertIn('"latest_trade_date": "2026-05-12"', index_text)
            self.assertIn('"available_trade_dates"', index_text)
            self.assertIn('"by_stock_code"', index_text)

    def test_writer_merges_previous_index_when_same_stock_reappears(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "第一次进入名单",
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
            generated_at="2026-05-12T18:00:00+08:00",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-13",
            extreme_conviction_list=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "第二次被点名",
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
            generated_at="2026-05-13T18:00:00+08:00",
        )

        with TemporaryDirectory() as tempdir:
            write_decision_ledger_artifacts(first, root_dir=Path(tempdir))
            write_decision_ledger_artifacts(second, root_dir=Path(tempdir))

            second_snapshot = Path(tempdir, "data", "decision-ledger", "2026-05-13.json").read_text(encoding="utf-8")
            index_text = Path(tempdir, "data", "decision-ledger", "index.json").read_text(encoding="utf-8")

        self.assertIn('"case_id": "2026-05-12-601991-01"', second_snapshot)
        self.assertIn('"cycle_day": 2', second_snapshot)
        self.assertIn("第一次进入名单", second_snapshot)
        self.assertIn("第二次被点名", second_snapshot)
        self.assertIn('"latest_trade_date": "2026-05-13"', index_text)

    def test_index_keeps_stock_cycle_mentions_and_status(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {"code": "601991", "name": "大唐发电", "sector": "电力", "conviction_reason": "第一次进入名单"}
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-13",
            extreme_conviction_list=[
                {"code": "601991", "name": "大唐发电", "sector": "电力", "conviction_reason": "第二次被点名"}
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(second, root_dir=root)
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        stock_records = index["by_stock_code"]["601991"]
        self.assertEqual(len(stock_records), 1)
        self.assertEqual(stock_records[0]["case_id"], "2026-05-12-601991-01")
        self.assertEqual(stock_records[0]["status"], "等待市场选择")
        self.assertFalse(stock_records[0]["cycle_closed"])
        self.assertEqual([item["mention_trade_date"] for item in stock_records[0]["mentions"]], ["2026-05-12", "2026-05-13"])


if __name__ == "__main__":
    unittest.main()
