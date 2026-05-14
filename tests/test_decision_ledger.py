import sys
from tempfile import TemporaryDirectory
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.decision_ledger import (
    build_decision_ledger_index,
    build_decision_ledger_snapshot,
    build_decision_ledger_snapshot_from_markdown_report,
    classify_cycle_acceptance,
    classify_planned_participation_review,
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

    def test_parses_extreme_conviction_participation_script_from_markdown_report(self):
        markdown = """
正文

**极度看好名单**（只保留最心动的少数，每只都绑定参与窗口）:
| 优先级 | 股票 | 代码 | 所属板块 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|
| 1 | 大唐发电 | 601991 | 电力 | 趋势比价链锚定龙 / 分歧转一致 | 竞价表态强且开盘承接继续才参与 |

**极度看好参与脚本**:
| 参与窗口 | 仓位三态 | 集合竞价 | 开盘前几分钟 | 打板策略 | 回封参与 | 错过后动作 | 作废条件 |
|----------|----------|----------|--------------|----------|----------|------------|----------|
| 竞价表态 + 回封参与 | 100% | 09:20后封单稳定且匹配金额继续放大 | 09:30-09:35不回落到昨收附近 | 首次封板只看大单金额持续进入 | 开板释放抛压后快速回封且板块同步走强 | 过快封死就沿电力趋势比价链找低位承接 | 竞价量价背离或开盘跌回昨日强承接区 |
"""

        items = parse_extreme_conviction_list_from_markdown(markdown)

        self.assertEqual(len(items), 1)
        script = items[0]["participation_script"]
        self.assertEqual(script["participation_window"], "竞价表态 + 回封参与")
        self.assertEqual(script["attack_state"], "100%")
        self.assertIn("09:20", script["auction"])
        self.assertIn("09:30-09:35", script["first_minutes"])
        self.assertIn("大单金额", script["board"])
        self.assertIn("快速回封", script["reseal"])
        self.assertIn("趋势比价链", script["missed_action"])
        self.assertIn("量价背离", script["cancellation"])

    def test_planned_participation_contains_fieldized_policy_flags(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {
                    "code": "601991.SH",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "趋势辨识度高 / 板块锚定龙",
                    "pattern": "T字板",
                    "core_level": "主线核心",
                },
                {
                    "code": "300001.SZ",
                    "name": "普通趋势股",
                    "sector": "消费",
                    "conviction_reason": "趋势辨识度高",
                    "pattern": "强实体异动",
                },
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
        )

        fast_plan = snapshot["cases"][0]["planned_participation"]
        self.assertEqual(fast_plan["participation_window_type"], "auction_reseal")
        self.assertTrue(fast_plan["auction_required"])
        self.assertTrue(fast_plan["first_minutes_required"])
        self.assertTrue(fast_plan["board_or_reseal_required"])
        self.assertFalse(fast_plan["ordinary_structure_confirm_allowed"])
        self.assertIn("趋势比价链", fast_plan["missed_entry_policy"])

        ordinary_plan = snapshot["cases"][1]["planned_participation"]
        self.assertEqual(ordinary_plan["participation_window_type"], "structure_confirm")
        self.assertFalse(ordinary_plan["auction_required"])
        self.assertFalse(ordinary_plan["first_minutes_required"])
        self.assertFalse(ordinary_plan["board_or_reseal_required"])
        self.assertTrue(ordinary_plan["ordinary_structure_confirm_allowed"])

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
        plan = snapshot["cases"][0]["planned_participation"]
        self.assertEqual(plan["participation_window"], "竞价表态 + 回封参与")
        self.assertEqual(plan["participation_window_type"], "auction_reseal")
        self.assertTrue(plan["auction_required"])
        self.assertFalse(plan["ordinary_structure_confirm_allowed"])

    def test_builds_snapshot_with_planned_participation_script(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {
                    "code": "601991.SH",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "趋势辨识度高 / 板块锚定龙",
                    "conviction_rule": "先看竞价承接，再等参与窗口确认",
                    "participation_window": "竞价表态 + 回封参与",
                    "attack_state": "100%",
                    "core_identity": {
                        "role": "trend_chain_anchor",
                        "chain_position": "high_anchor",
                        "early_participation_allowed": True,
                        "position_state": "100%",
                        "basis": ["主线内核", "板块锚定龙", "2连板"],
                    },
                    "auction_script": "09:20后封单稳定且匹配金额继续放大",
                    "first_minutes_script": "09:30-09:35不回落到昨收附近",
                    "board_script": "首次封板只看大单金额持续进入",
                    "reseal_script": "开板释放抛压后快速回封且板块同步走强",
                    "missed_action": "过快封死就沿电力趋势比价链找低位承接",
                    "invalid_condition": "竞价量价背离或开盘跌回昨日强承接区",
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
            source_report={"path": "reports/2026-05-12_A股日报_完整版.md", "variant": "full"},
            generated_at="2026-05-13T00:00:00+08:00",
        )

        script = snapshot["cases"][0]["planned_participation"]
        self.assertEqual(snapshot["cases"][0]["core_identity"]["role"], "trend_chain_anchor")
        self.assertEqual(snapshot["cases"][0]["core_identity"]["chain_position"], "high_anchor")
        self.assertTrue(snapshot["cases"][0]["core_identity"]["early_participation_allowed"])
        self.assertEqual(script["participation_window"], "竞价表态 + 回封参与")
        self.assertEqual(script["attack_state"], "100%")
        self.assertIn("09:20", script["auction"])
        self.assertIn("09:30-09:35", script["first_minutes"])
        self.assertIn("大单金额", script["board"])
        self.assertIn("快速回封", script["reseal"])
        self.assertIn("趋势比价链", script["missed_action"])
        self.assertIn("量价背离", script["cancellation"])
        self.assertEqual(script["required_steps"], ["竞价表态", "开盘前几分钟承接", "回封/打板"])
        self.assertEqual(script["fallback_state"], "不满足回到0%")
        self.assertEqual(script["participation_basis"]["auction"], "价格位置 / 匹配金额 / 委托稳定 / 板块同步")
        self.assertEqual(script["participation_basis"]["first_minutes"], "主动资金继续抬价 / 承接连续")
        self.assertEqual(script["participation_basis"]["board_or_reseal"], "大单金额持续进入 / 快速回封 / 封单质量改善")
        self.assertEqual(snapshot["cases"][0]["mentions"][0]["planned_participation"]["attack_state"], "100%")

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
            self.assertEqual(index["selection_rule_version"], "extreme-conviction-ledger-v1")
            self.assertEqual(index["selection_input_hash_by_trade_date"]["2026-05-12"], snapshot["selection_input_hash"])
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
                    "conviction_rule": "先看竞价承接，再等参与窗口确认",
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
        self.assertTrue(snapshot["frozen"])
        self.assertEqual(snapshot["selection_rule_version"], "extreme-conviction-ledger-v1")
        self.assertRegex(snapshot["selection_input_hash"], r"^[0-9a-f]{64}$")
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
        plan = case["planned_participation"]
        self.assertEqual(plan["participation_window"], "竞价表态 + 回封参与")
        self.assertEqual(plan["participation_window_type"], "auction_reseal")
        self.assertEqual(plan["attack_state"], "50%")
        self.assertIn("09:20", plan["auction"])
        self.assertIn("09:30-09:35", plan["first_minutes"])
        self.assertIn("大单金额", plan["board"])
        self.assertIn("快速回封", plan["reseal"])
        self.assertIn("电力", plan["missed_action"])
        self.assertIn("板块同步", plan["cancellation"])
        self.assertEqual(case["mentions"][0]["planned_participation"], plan)

    def test_selection_input_hash_is_stable_for_same_extreme_conviction_inputs(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {"code": "603007", "name": "花王股份", "sector": "汽车零部", "conviction_reason": "板块锚定龙 / 首波先锋"},
                {"code": "603052", "name": "可川科技", "sector": "消费电子", "conviction_reason": "资金顶出辨识度"},
            ],
            market_branch="爆发后分化整理",
            sector_relationship_state="周期主线与当天主攻线一致",
            generated_at="2026-05-13T18:00:00+08:00",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {"conviction_reason": "板块锚定龙 / 首波先锋", "sector": "汽车零部", "name": "花王股份", "code": "603007"},
                {"conviction_reason": "资金顶出辨识度", "sector": "消费电子", "name": "可川科技", "code": "603052"},
            ],
            market_branch="爆发后分化整理",
            sector_relationship_state="周期主线与当天主攻线一致",
            generated_at="2026-05-13T19:00:00+08:00",
        )

        self.assertEqual(first["selection_input_hash"], second["selection_input_hash"])
        self.assertEqual([case["stock_code"] for case in first["cases"]], ["603007", "603052"])

    def test_default_participation_script_routes_t_board_core_to_auction_reseal(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {
                    "code": "601991.SH",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "趋势辨识度高 / 板块锚定龙",
                    "conviction_rule": "观察竞价强弱",
                    "pattern": "T字板",
                    "core_level": "主线核心",
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
            source_report={"path": "reports/2026-05-12_A股日报_完整版.md", "variant": "full"},
            generated_at="2026-05-13T00:00:00+08:00",
        )

        plan = snapshot["cases"][0]["planned_participation"]
        self.assertEqual(plan["participation_window"], "竞价表态 + 回封参与")
        self.assertIn("09:20", plan["auction"])
        self.assertIn("09:30-09:35", plan["first_minutes"])
        self.assertIn("大单金额", plan["board"])
        self.assertIn("快速回封", plan["reseal"])
        self.assertIn("趋势比价链", plan["missed_action"])
        self.assertNotIn("60分钟确认", plan["participation_window"])

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

    def test_index_records_keep_t25_fields_needed_by_workbench(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-13",
            extreme_conviction_list=[
                {
                    "code": "603007",
                    "name": "花王股份",
                    "sector": "汽车零部",
                    "conviction_reason": "板块锚定龙 / 首波先锋",
                    "participation_window": "竞价表态 + 回封参与",
                    "attack_state": "50%",
                }
            ],
            market_branch="爆发后分化整理",
            sector_relationship_state="周期主线与当天主攻线一致",
            generated_at="2026-05-13T18:00:00+08:00",
        )

        index = build_decision_ledger_index(snapshot)
        record = index["by_stock_code"]["603007"][0]

        self.assertEqual(record["stock_code"], "603007")
        self.assertEqual(record["stock_name"], "花王股份")
        self.assertEqual(record["first_seen_trade_date"], "2026-05-13")
        self.assertEqual(record["cycle_day"], 1)
        self.assertEqual(record["cycle_length_trade_days"], 25)
        self.assertEqual(record["planned_participation"]["participation_window"], "竞价表态 + 回封参与")
        self.assertEqual(record["planned_participation"]["attack_state"], "50%")

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

    def test_planned_participation_review_classifies_hit_cancellation_missed_and_premature(self):
        planned = {
            "participation_window": "竞价表态 + 回封参与",
            "attack_state": "100%",
            "auction": "09:20后封单稳定且匹配金额继续放大",
            "first_minutes": "09:30-09:35不回落到昨收附近",
            "board": "首次封板只看大单金额持续进入",
            "reseal": "开板释放抛压后快速回封且板块同步走强",
            "missed_action": "过快封死就沿电力趋势比价链找低位承接",
            "cancellation": "竞价量价背离或开盘跌回昨日强承接区",
            "participation_window_type": "auction_reseal",
            "auction_required": True,
            "first_minutes_required": True,
            "board_or_reseal_required": True,
            "ordinary_structure_confirm_allowed": False,
            "missed_entry_policy": "过快封死就沿电力趋势比价链找低位承接",
        }
        ordinary = {
            "participation_window": "60分钟确认",
            "attack_state": "50%",
            "participation_window_type": "structure_confirm",
            "auction_required": False,
            "first_minutes_required": False,
            "board_or_reseal_required": False,
            "ordinary_structure_confirm_allowed": True,
        }

        hit = classify_planned_participation_review(
            planned,
            auction_matched=True,
            first_minutes_accepted=True,
            board_sealed=True,
            reseal_success=True,
            sector_supported=True,
            cancellation_triggered=False,
        )
        cancelled = classify_planned_participation_review(
            planned,
            auction_matched=False,
            first_minutes_accepted=False,
            cancellation_triggered=True,
            cancellation_evidence="竞价量价背离且开盘跌回昨日强承接区",
        )
        missed = classify_planned_participation_review(
            planned,
            primary_unavailable=True,
            missed_action_worked=True,
            missed_action_evidence="低位电力补涨完成承接",
        )
        premature = classify_planned_participation_review(
            planned,
            auction_matched=True,
            first_minutes_accepted=False,
            board_sealed=False,
            reseal_success=False,
            sector_supported=False,
            cancellation_triggered=False,
        )
        ordinary_hit = classify_planned_participation_review(
            ordinary,
            structure_confirmed=True,
            sector_supported=True,
        )
        ordinary_waiting = classify_planned_participation_review(
            ordinary,
            auction_matched=True,
            first_minutes_accepted=True,
            sector_supported=True,
        )

        self.assertEqual(hit["status"], "预演命中")
        self.assertEqual(hit["planned_window"], "竞价表态 + 回封参与")
        self.assertEqual(hit["attack_state"], "100%")
        self.assertEqual(hit["participation_window_type"], "auction_reseal")
        self.assertIn("竞价表态", hit["matched_steps"])
        self.assertIn("回封参与", hit["matched_steps"])
        self.assertEqual(cancelled["status"], "预演作废")
        self.assertIn("量价背离", cancelled["evidence"])
        self.assertEqual(missed["status"], "错过后方案命中")
        self.assertIn("补涨", missed["evidence"])
        self.assertEqual(premature["status"], "预演过早")
        self.assertIn("承接没有延续", premature["reason"])
        self.assertEqual(ordinary_hit["status"], "预演命中")
        self.assertEqual(ordinary_hit["participation_window_type"], "structure_confirm")
        self.assertIn("60分钟确认", ordinary_hit["matched_steps"])
        self.assertEqual(ordinary_waiting["status"], "等待复盘")

    def test_builds_snapshot_with_planned_participation_review_when_review_facts_exist(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {
                    "code": "601991.SH",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "趋势辨识度高 / 板块锚定龙",
                    "participation_window": "竞价表态 + 回封参与",
                    "attack_state": "100%",
                    "auction_script": "09:20后封单稳定且匹配金额继续放大",
                    "first_minutes_script": "09:30-09:35不回落到昨收附近",
                    "board_script": "首次封板只看大单金额持续进入",
                    "reseal_script": "开板释放抛压后快速回封且板块同步走强",
                    "missed_action": "过快封死就沿电力趋势比价链找低位承接",
                    "invalid_condition": "竞价量价背离或开盘跌回昨日强承接区",
                    "participation_review_facts": {
                        "primary_unavailable": True,
                        "missed_action_worked": True,
                        "missed_action_evidence": "低位电力补涨完成承接",
                    },
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
        )

        review = snapshot["cases"][0]["participation_review"]
        self.assertEqual(review["status"], "错过后方案命中")
        self.assertEqual(review["planned_window"], "竞价表态 + 回封参与")
        self.assertIn("补涨", review["evidence"])

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

    def test_index_keeps_participation_review_summary_for_snap_ui(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {
                    "code": "601991",
                    "name": "大唐发电",
                    "sector": "电力",
                    "conviction_reason": "趋势辨识度高",
                    "participation_window": "竞价表态 + 回封参与",
                    "attack_state": "100%",
                    "auction_script": "09:20后封单稳定且匹配金额继续放大",
                    "first_minutes_script": "09:30-09:35不回落到昨收附近",
                    "board_script": "首次封板只看大单金额持续进入",
                    "reseal_script": "开板释放抛压后快速回封且板块同步走强",
                    "missed_action": "过快封死就沿电力趋势比价链找低位承接",
                    "invalid_condition": "竞价量价背离或开盘跌回昨日强承接区",
                    "participation_review_facts": {
                        "auction_matched": True,
                        "first_minutes_accepted": True,
                        "board_sealed": True,
                        "reseal_success": True,
                        "sector_supported": True,
                    },
                }
            ],
            market_branch="指数高位停顿轮动",
            sector_relationship_state="混沌接力",
        )

        index = build_decision_ledger_index(snapshot)

        record = index["by_stock_code"]["601991"][0]
        self.assertEqual(record["participation_review_status"], "预演命中")
        self.assertEqual(record["participation_review"]["status"], "预演命中")
        self.assertEqual(record["participation_review"]["planned_window"], "竞价表态 + 回封参与")
        self.assertEqual(record["participation_review"]["participation_window_type"], "auction_reseal")
        self.assertIn("竞价表态", record["participation_review"]["matched_steps"])


if __name__ == "__main__":
    unittest.main()
