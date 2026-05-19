import sys
from tempfile import TemporaryDirectory
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.decision_ledger import (
    build_participation_review_facts_from_market_fact,
    build_decision_ledger_index,
    build_decision_ledger_snapshot,
    build_decision_ledger_snapshot_from_markdown_report,
    build_extreme_conviction_backtest_rows,
    classify_cycle_acceptance,
    classify_planned_participation_review,
    classify_validation_state,
    merge_snapshot_with_previous_index,
    parse_extreme_conviction_list_from_markdown,
    prune_replaced_same_day_extreme_mentions,
    render_extreme_conviction_backtest_lines,
    render_extreme_conviction_tracking_lines,
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
| 参与窗口 | 仓位三态 | 涨停惯性 | 盈亏比 | 集合竞价 | 开盘前几分钟 | 均线回归试错 | 打板策略 | 回封参与 | 错过后动作 | MA20作废 | 跟踪周期 | 作废条件 |
|----------|----------|----------|--------|----------|--------------|--------------|----------|----------|------------|----------|----------|----------|
| 竞价表态 + 回封参与 | 100% | 高惯性；高于普通上涨样本；昨日涨停/连板已被资金选择 | 合格；约2.5:1；试错前要求盈亏比不低于2:1 | 09:20后封单稳定且匹配金额继续放大 | 09:30-09:35不回落到昨收附近 | 09:50-10:10均线回归试错；分时黄线承接 | 首次封板只看大单金额持续进入 | 开板释放抛压后快速回封且板块同步走强 | 过快封死就沿电力趋势比价链找低位承接 | 跌破日K MA20作废 | 25个交易日 | 竞价量价背离或开盘跌回昨日强承接区 |
"""

        items = parse_extreme_conviction_list_from_markdown(markdown)

        self.assertEqual(len(items), 1)
        script = items[0]["participation_script"]
        self.assertEqual(script["participation_window"], "竞价表态 + 回封参与")
        self.assertEqual(script["attack_state"], "100%")
        self.assertEqual(script["limit_up_inertia_level"], "高惯性")
        self.assertEqual(script["next_day_limit_probability_band"], "高于普通上涨样本")
        self.assertIn("昨日涨停", script["limit_up_inertia_reason"])
        self.assertEqual(script["risk_reward_state"], "合格")
        self.assertEqual(script["risk_reward_ratio"], 2.5)
        self.assertIn("2:1", script["risk_reward_plan"])
        self.assertIn("09:20", script["auction"])
        self.assertIn("09:30-09:35", script["first_minutes"])
        self.assertIn("分时黄线", script["intraday_yellow_line_probe"])
        self.assertIn("大单金额", script["board"])
        self.assertIn("快速回封", script["reseal"])
        self.assertIn("趋势比价链", script["missed_action"])
        self.assertIn("MA20", script["ma20_invalidation"])
        self.assertEqual(script["tracking_window_trade_days"], 25)
        self.assertIn("量价背离", script["cancellation"])

    def test_parses_focus_watch_table_with_execution_layer_from_markdown_report(self):
        markdown = """
正文

**重点观察名单**（只保留最心动的少数，每只都绑定参与窗口）:
| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 执行分层 | 观察理由 | 明日原则 |
|--------|------|------|----------|----------|----------|----------|----------|
| 1 | 大唐发电 | 601991 | 电力 | 趋势比价链锚点 / 高位锚 | 修复观察 | 修复观察 / 趋势辨识度高 | 修复观察只看09:50-10:10承接确认，未确认不参与 |

**重点观察参与脚本**:
| 参与窗口 | 仓位三态 | 涨停惯性 | 盈亏比 | 集合竞价 | 开盘前几分钟 | 均线回归试错 | 打板策略 | 回封参与 | 错过后动作 | MA20作废 | 跟踪周期 | 作废条件 |
|----------|----------|----------|--------|----------|--------------|--------------|----------|----------|------------|----------|----------|----------|
| 09:50-10:10修复确认 | 50% | 中惯性；高于弱上涨样本；先看09:50-10:10承接再决定 | 待计算；默认要求盈亏比不低于2:1 | 不启用 | 不启用 | 09:50-10:10均线回归试错；分时黄线只作为日内承接确认线 | 不打板 | 不回封 | 未确认就放弃 | 有效跌破日K MA20取消幻想 | 25个交易日 | 09:50-10:10继续走弱 |
"""

        items = parse_extreme_conviction_list_from_markdown(markdown)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "大唐发电")
        self.assertEqual(items[0]["sector"], "电力")
        self.assertEqual(items[0]["core_identity_label"], "趋势比价链锚点 / 高位锚")
        self.assertEqual(items[0]["candidate_layer_label"], "修复观察")
        self.assertEqual(items[0]["candidate_layer"], "watch_sample")
        self.assertEqual(items[0]["execution_eligibility"], "structure_confirm_only")
        self.assertIn("修复观察", items[0]["conviction_reason"])
        self.assertIn("09:50-10:10", items[0]["conviction_rule"])
        self.assertEqual(items[0]["participation_script"]["participation_window"], "09:50-10:10修复确认")

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
        self.assertEqual(fast_plan["source_tier"], "extreme_conviction")
        self.assertEqual(fast_plan["entry_timing"], "open_core")
        self.assertEqual(fast_plan["buy_window"], "09:30-09:35")
        self.assertTrue(fast_plan["auction_required"])
        self.assertTrue(fast_plan["first_minutes_required"])
        self.assertTrue(fast_plan["board_or_reseal_required"])
        self.assertFalse(fast_plan["ordinary_structure_confirm_allowed"])
        self.assertIn("趋势比价链", fast_plan["missed_entry_policy"])
        self.assertTrue(fast_plan["ma_reversion_probe_allowed"])
        self.assertEqual(fast_plan["ma_reversion_window"], "09:50-10:10")
        self.assertIn("分时黄线", fast_plan["intraday_yellow_line_probe"])
        self.assertIn("MA20", fast_plan["ma20_invalidation"])
        self.assertEqual(fast_plan["tracking_window_trade_days"], 25)

        ordinary_plan = snapshot["cases"][1]["planned_participation"]
        self.assertEqual(ordinary_plan["participation_window_type"], "structure_confirm")
        self.assertEqual(ordinary_plan["source_tier"], "extreme_conviction")
        self.assertEqual(ordinary_plan["entry_timing"], "ten_confirm")
        self.assertEqual(ordinary_plan["buy_window"], "09:50-10:10")
        self.assertFalse(ordinary_plan["auction_required"])
        self.assertFalse(ordinary_plan["first_minutes_required"])
        self.assertFalse(ordinary_plan["board_or_reseal_required"])
        self.assertTrue(ordinary_plan["ordinary_structure_confirm_allowed"])
        self.assertTrue(ordinary_plan["ma_reversion_probe_allowed"])

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
        self.assertEqual(script["required_steps"], ["竞价表态", "开盘前几分钟承接", "日K均线回归", "回封/打板"])
        self.assertEqual(script["fallback_state"], "不满足回到0%")
        self.assertEqual(script["participation_basis"]["auction"], "价格位置 / 匹配金额 / 委托稳定 / 板块同步")
        self.assertEqual(script["participation_basis"]["first_minutes"], "主动资金继续抬价 / 承接连续")
        self.assertIn("MA5/MA10", script["participation_basis"]["ma_reversion"])
        self.assertEqual(script["participation_basis"]["board_or_reseal"], "大单金额持续进入 / 快速回封 / 封单质量改善")
        self.assertEqual(script["tracking_window_trade_days"], 25)
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
            self.assertEqual(
                index["by_stock_code"]["601991"][0]["hypothesis"]["sector_candidate"],
                "电力",
            )

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
        self.assertEqual(plan["limit_up_inertia_level"], "高惯性")
        self.assertEqual(plan["next_day_limit_probability_band"], "高于普通上涨样本")
        self.assertIn("2:1", plan["risk_reward_plan"])
        self.assertEqual(plan["risk_reward_min_ratio"], 2.0)
        self.assertEqual(case["mentions"][0]["planned_participation"], plan)

    def test_snapshot_replaces_invalid_sector_with_candidate_plate(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {
                    "code": "002342",
                    "name": "巨力索具",
                    "sector": "HS",
                    "concepts": ["商业航天", "军工"],
                    "conviction_reason": "趋势辨识度高",
                }
            ],
            market_branch="收缩防守",
            sector_relationship_state="暂未分出",
        )

        case = snapshot["cases"][0]
        self.assertEqual(case["hypothesis"]["sector_candidate"], "商业航天")
        self.assertIn("商业航天", case["planned_participation"]["missed_action"])

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

    def test_same_stock_open_cycle_replaces_previous_invalid_sector(self):
        previous_index = {
            "by_stock_code": {
                "001259": [
                    {
                        "case_id": "2026-05-15-001259-01",
                        "stock_name": "利仁科技",
                        "cycle_start_trade_date": "2026-05-15",
                        "latest_trade_date": "2026-05-15",
                        "status": "等待市场选择",
                        "snapshot_path": "data/decision-ledger/2026-05-15.json",
                        "cycle_closed": False,
                        "planned_participation": {
                            "participation_window": "竞价表态 + 回封参与",
                            "missed_action": "过快封死就沿HS趋势比价链找低位承接，找不到就跳过",
                            "missed_entry_policy": "过快封死就沿HS趋势比价链找低位承接，找不到就跳过",
                            "participation_basis": {
                                "missed_entry": "过快封死就沿HS趋势比价链找低位承接，找不到就跳过"
                            },
                            "source_tier": "extreme_conviction",
                        },
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-15",
                                "rank": 1,
                                "source_section": "极度看好名单",
                                "reason": "板块锚定龙",
                                "planned_participation": {
                                    "missed_action": "过快封死就沿HS趋势比价链找低位承接，找不到就跳过",
                                    "source_tier": "extreme_conviction",
                                },
                            }
                        ],
                    }
                ]
            }
        }
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {
                    "code": "001259",
                    "name": "利仁科技",
                    "sector": "股权转让",
                    "conviction_reason": "板块锚定龙",
                }
            ],
            market_branch="收缩防守",
            sector_relationship_state="暂未分出",
        )

        merged = merge_snapshot_with_previous_index(snapshot, previous_index)
        case = merged["cases"][0]

        self.assertEqual(case["case_id"], "2026-05-15-001259-01")
        self.assertEqual(case["hypothesis"]["sector_candidate"], "股权转让")
        self.assertIn("股权转让", case["planned_participation"]["missed_action"])
        self.assertIn("股权转让", case["mentions"][0]["planned_participation"]["missed_action"])
        self.assertNotIn("HS", json.dumps(case, ensure_ascii=False))

    def test_writer_sanitizes_historical_invalid_sector_records_in_index(self):
        stale_index = {
            "artifact_version": 1,
            "latest_trade_date": "2026-05-15",
            "selection_rule_version": "extreme-conviction-ledger-v1",
            "selection_input_hash_by_trade_date": {"2026-05-15": "old"},
            "available_trade_dates": ["2026-05-15"],
            "snapshots": [{"trade_date": "2026-05-15", "path": "data/decision-ledger/2026-05-15.json"}],
            "by_stock_code": {
                "001259": [
                    {
                        "case_id": "2026-05-15-001259-01",
                        "stock_code": "001259",
                        "stock_name": "利仁科技",
                        "cycle_start_trade_date": "2026-05-15",
                        "latest_trade_date": "2026-05-15",
                        "status": "等待市场选择",
                        "snapshot_path": "data/decision-ledger/2026-05-15.json",
                        "cycle_closed": False,
                        "hypothesis": {"sector_candidate": "HS"},
                        "planned_participation": {
                            "source_tier": "extreme_conviction",
                            "missed_action": "过快封死就沿HS趋势比价链找低位承接，找不到就跳过",
                            "missed_entry_policy": "过快封死就沿HS趋势比价链找低位承接，找不到就跳过",
                        },
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-15",
                                "source_section": "极度看好名单",
                                "planned_participation": {
                                    "source_tier": "extreme_conviction",
                                    "missed_action": "过快封死就沿HS趋势比价链找低位承接，找不到就跳过",
                                },
                            }
                        ],
                    }
                ]
            },
        }
        current = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {
                    "code": "603082",
                    "name": "北自科技",
                    "sector": "机器人",
                    "conviction_reason": "趋势辨识度高",
                }
            ],
            market_branch="收缩防守",
            sector_relationship_state="暂未分出",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            ledger_dir = root / "data" / "decision-ledger"
            ledger_dir.mkdir(parents=True)
            (ledger_dir / "index.json").write_text(json.dumps(stale_index, ensure_ascii=False), encoding="utf-8")

            write_decision_ledger_artifacts(current, root_dir=root, review_market_facts_by_stock_code={})
            index = json.loads((ledger_dir / "index.json").read_text(encoding="utf-8"))

        stale_record = index["by_stock_code"]["001259"][0]
        self.assertEqual(stale_record["hypothesis"]["sector_candidate"], "股权转让")
        self.assertIn("股权转让", stale_record["planned_participation"]["missed_action"])
        self.assertNotIn("HS", json.dumps(index, ensure_ascii=False))

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
        self.assertEqual(record["planned_participation"]["source_tier"], "extreme_conviction")
        self.assertEqual(record["planned_participation"]["entry_timing"], "open_core")
        self.assertEqual(record["planned_participation"]["buy_window"], "09:30-09:35")

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

    def test_planned_participation_review_does_not_count_unavailable_limit_as_hit(self):
        planned = {
            "participation_window": "竞价表态 + 回封参与",
            "attack_state": "100%",
            "participation_window_type": "auction_reseal",
        }

        review = classify_planned_participation_review(
            planned,
            auction_matched=True,
            first_minutes_accepted=True,
            board_sealed=True,
            sector_supported=True,
            primary_unavailable=True,
            missed_action_worked=False,
            evidence="一字封死，主目标不可成交",
        )

        self.assertEqual(review["status"], "主目标不可成交")
        self.assertNotEqual(review.get("entry_decision"), "open_buy")
        self.assertIn("不补票", review["reason"])
        self.assertIn("一字封死", review["evidence"])

    def test_market_fact_builder_marks_one_word_limit_as_unavailable_not_open_buy(self):
        facts = build_participation_review_facts_from_market_fact(
            {"entry_timing": "open_core", "buy_window": "09:30-09:35"},
            {
                "stock_code": "603007",
                "stock_name": "花王股份",
                "review_trade_date": "2026-05-14",
                "prev_close": 8.42,
                "open": 9.26,
                "high": 9.26,
                "low": 9.26,
                "close": 9.26,
            },
        )

        self.assertTrue(facts["primary_unavailable"])
        self.assertEqual(facts["entry_decision"], "unavailable")
        self.assertIn("不参与", facts["same_day_action"])

    def test_market_fact_builder_keeps_one_word_limit_unavailable_even_with_minute_bars(self):
        facts = build_participation_review_facts_from_market_fact(
            {"entry_timing": "open_core", "buy_window": "09:30-09:35", "source_tier": "extreme_conviction"},
            {
                "stock_code": "603007",
                "stock_name": "花王股份",
                "review_trade_date": "2026-05-14",
                "prev_close": 8.42,
                "open": 9.26,
                "high": 9.26,
                "low": 9.26,
                "close": 9.26,
                "window_reference_price": 8.42,
                "minute_bars": [
                    {"datetime": "2026-05-14 09:50:00", "open": 9.26, "high": 9.26, "low": 9.26, "close": 9.26},
                    {"datetime": "2026-05-14 10:10:00", "open": 9.26, "high": 9.26, "low": 9.26, "close": 9.26},
                ],
            },
        )

        self.assertTrue(facts["primary_unavailable"])
        self.assertEqual(facts["entry_decision"], "unavailable")
        self.assertIn("不补票", facts["same_day_action"])

    def test_market_fact_builder_does_not_kill_window_entry_from_daily_low_only(self):
        facts = build_participation_review_facts_from_market_fact(
            {"entry_timing": "open_core", "buy_window": "09:50-10:10"},
            {
                "stock_code": "600578",
                "stock_name": "京能电力",
                "review_trade_date": "2026-05-15",
                "prev_close": 5.88,
                "open": 6.00,
                "high": 6.47,
                "low": 5.43,
                "close": 6.47,
            },
        )

        self.assertEqual(facts["entry_decision"], "waiting_window_review")
        self.assertIn("窗口事实", facts["standard_answer_basis"])
        self.assertIn("9:50-10:10", facts["same_day_action"])

    def test_market_fact_builder_uses_default_ma_reversion_window_for_old_open_core_plans(self):
        facts = build_participation_review_facts_from_market_fact(
            {"entry_timing": "open_core", "buy_window": "09:30-09:35", "source_tier": "extreme_conviction"},
            {
                "stock_code": "600578",
                "stock_name": "京能电力",
                "review_trade_date": "2026-05-15",
                "prev_close": 6.37,
                "open": 6.50,
                "high": 7.01,
                "low": 5.88,
                "close": 7.01,
            },
        )

        self.assertEqual(facts["entry_decision"], "waiting_window_review")
        self.assertIn("09:50-10:10", facts["same_day_action"])

    def test_market_fact_builder_confirms_waiting_entry_from_minute_window(self):
        facts = build_participation_review_facts_from_market_fact(
            {"entry_timing": "open_core", "buy_window": "09:30-09:35", "source_tier": "extreme_conviction"},
            {
                "stock_code": "600578",
                "stock_name": "京能电力",
                "review_trade_date": "2026-05-15",
                "prev_close": 6.37,
                "open": 6.50,
                "high": 7.01,
                "low": 5.88,
                "close": 7.01,
                "window_reference_price": 6.00,
                "minute_bars": [
                    {"datetime": "2026-05-15 09:35:00", "open": 6.50, "high": 6.55, "low": 6.20, "close": 6.22},
                    {"datetime": "2026-05-15 09:45:00", "open": 6.22, "high": 6.25, "low": 5.88, "close": 5.96},
                    {"datetime": "2026-05-15 09:50:00", "open": 5.96, "high": 6.05, "low": 5.95, "close": 6.02},
                    {"datetime": "2026-05-15 09:55:00", "open": 6.02, "high": 6.12, "low": 6.00, "close": 6.10},
                    {"datetime": "2026-05-15 10:00:00", "open": 6.10, "high": 6.24, "low": 6.08, "close": 6.22},
                    {"datetime": "2026-05-15 10:10:00", "open": 6.22, "high": 6.35, "low": 6.18, "close": 6.34},
                ],
            },
        )
        review = classify_planned_participation_review(
            {"participation_window": "竞价表态 + 回封参与", "participation_window_type": "auction_reseal"},
            **facts,
        )

        self.assertEqual(facts["entry_decision"], "window_confirm_buy")
        self.assertTrue(facts["first_minutes_accepted"])
        self.assertIn("09:50-10:10承接成立", facts["standard_answer_basis"])
        self.assertIn("窗口收盘", facts["market_outcome"])
        self.assertIn("09:50-10:10", facts["same_day_action"])
        self.assertEqual(review["status"], "预演命中")
        self.assertIn("09:50-10:10承接", review["matched_steps"])

    def test_market_fact_builder_cancels_waiting_entry_from_failed_minute_window(self):
        facts = build_participation_review_facts_from_market_fact(
            {"entry_timing": "open_core", "buy_window": "09:30-09:35", "source_tier": "extreme_conviction"},
            {
                "stock_code": "600578",
                "stock_name": "京能电力",
                "review_trade_date": "2026-05-15",
                "prev_close": 6.37,
                "open": 6.50,
                "high": 7.01,
                "low": 5.70,
                "close": 7.01,
                "window_reference_price": 6.00,
                "minute_bars": [
                    {"datetime": "2026-05-15 09:45:00", "open": 6.22, "high": 6.25, "low": 5.88, "close": 6.01},
                    {"datetime": "2026-05-15 09:50:00", "open": 6.01, "high": 6.03, "low": 5.90, "close": 5.94},
                    {"datetime": "2026-05-15 09:55:00", "open": 5.94, "high": 5.96, "low": 5.78, "close": 5.80},
                    {"datetime": "2026-05-15 10:00:00", "open": 5.80, "high": 5.84, "low": 5.70, "close": 5.72},
                    {"datetime": "2026-05-15 10:10:00", "open": 5.72, "high": 5.76, "low": 5.70, "close": 5.72},
                ],
            },
        )
        review = classify_planned_participation_review(
            {"participation_window": "竞价表态 + 回封参与", "participation_window_type": "auction_reseal"},
            **facts,
        )

        self.assertEqual(facts["entry_decision"], "window_confirm_failed")
        self.assertTrue(facts["cancellation_triggered"])
        self.assertIn("09:50-10:10继续走弱", facts["standard_answer_basis"])
        self.assertIn("0%不参与", facts["same_day_action"])
        self.assertEqual(review["status"], "预演作废")

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
        self.assertEqual(index["extreme_conviction_backtest_rows"][0]["stock_code"], "601991")
        self.assertEqual(index["extreme_conviction_backtest_rows"][0]["buy_point_quality"], "买点成立")
        self.assertEqual(index["extreme_conviction_backtest_rows"][0]["review_status"], "预演命中")

    def test_renders_extreme_conviction_25_day_tracking_table_from_index(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "cycle_start_trade_date": "2026-05-14",
                        "latest_trade_date": "2026-05-15",
                        "cycle_day": 2,
                        "cycle_length_trade_days": 25,
                        "cycle_closed": False,
                        "status": "等待市场选择",
                        "planned_participation": {
                            "participation_window": "竞价表态 + 回封参与",
                            "entry_timing": "open_core",
                            "buy_window": "09:30-09:35",
                            "attack_state": "50%",
                            "ma20_invalidation": "有效跌破日K MA20取消幻想",
                        },
                        "participation_review_status": "预演命中",
                        "participation_review": {
                            "status": "预演命中",
                            "same_day_action": "按09:30-09:35开盘核心参与",
                            "next_action": "若已买入，次日先看是否继续强于市场",
                        },
                        "mentions": [
                            {"mention_trade_date": "2026-05-14", "rank": 1, "source_section": "极度看好名单"}
                        ],
                    }
                ],
                "300001": [
                    {
                        "stock_code": "300001",
                        "stock_name": "普通观察",
                        "cycle_day": 1,
                        "cycle_length_trade_days": 25,
                        "cycle_closed": False,
                        "planned_participation": {"source_tier": "ordinary_watch"},
                        "mentions": [{"mention_trade_date": "2026-05-15", "source_section": "观察池"}],
                    }
                ],
            }
        }

        lines = render_extreme_conviction_tracking_lines(index, max_rows=5)
        rendered = "\n".join(lines)

        self.assertIn("**重点观察25日跟踪表**", rendered)
        self.assertIn("| 股票 | 代码 | 周期日 | 首次入选 | 最近复盘 | 计划窗口 | 买入窗口 | 预演复盘 | 下一步动作 | 作废线 |", rendered)
        self.assertIn("| 京能电力 | 600578 | D2/25 | 2026-05-14 | 2026-05-15 | 竞价表态 + 回封参与 | 09:30-09:35 | 预演命中 | 若已买入，次日先看是否继续强于市场 | 有效跌破日K MA20取消幻想 |", rendered)
        self.assertNotIn("普通观察", rendered)

    def test_builds_extreme_conviction_backtest_rows_from_index(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "cycle_start_trade_date": "2026-05-14",
                        "latest_trade_date": "2026-05-15",
                        "cycle_day": 2,
                        "cycle_closed": False,
                        "planned_participation": {
                            "source_tier": "extreme_conviction",
                            "participation_window": "竞价表态 + 回封参与",
                            "entry_timing": "open_core",
                            "buy_window": "09:30-09:35",
                            "limit_up_inertia_level": "高惯性",
                            "next_day_limit_probability_band": "高于普通上涨样本",
                            "risk_reward_state": "合格",
                            "risk_reward_ratio": 2.5,
                        },
                        "participation_review_status": "预演命中",
                        "participation_review": {
                            "status": "预演命中",
                            "entry_decision": "open_buy",
                            "same_day_action": "按09:30-09:35开盘核心参与",
                            "market_outcome": "开盘+2.00%，最高+10.00%，收盘+10.00%",
                        },
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-14",
                                "rank": 1,
                                "source_section": "极度看好名单",
                            }
                        ],
                    }
                ],
                "603007": [
                    {
                        "stock_code": "603007",
                        "stock_name": "花王股份",
                        "cycle_start_trade_date": "2026-05-13",
                        "latest_trade_date": "2026-05-14",
                        "cycle_day": 2,
                        "cycle_closed": False,
                        "planned_participation": {
                            "source_tier": "extreme_conviction",
                            "participation_window": "竞价表态 + 回封参与",
                            "entry_timing": "open_core",
                            "buy_window": "09:30-09:35",
                            "limit_up_inertia_level": "高惯性",
                            "risk_reward_plan": "默认要求盈亏比不低于2:1",
                        },
                        "participation_review_status": "主目标不可成交",
                        "participation_review": {
                            "status": "主目标不可成交",
                            "entry_decision": "unavailable",
                            "same_day_action": "主目标封死或不可成交，0%不参与",
                            "market_outcome": "一字涨停",
                        },
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-13",
                                "rank": 2,
                                "source_section": "极度看好名单",
                            }
                        ],
                    }
                ],
                "300001": [
                    {
                        "stock_code": "300001",
                        "stock_name": "普通观察",
                        "planned_participation": {"source_tier": "ordinary_watch"},
                        "mentions": [{"mention_trade_date": "2026-05-15", "source_section": "观察池"}],
                    }
                ],
            }
        }

        rows = build_extreme_conviction_backtest_rows(index, max_rows=5)

        self.assertEqual([row["stock_name"] for row in rows], ["京能电力", "花王股份"])
        self.assertEqual(rows[0]["selection_quality"], "高惯性 / 高于普通上涨样本")
        self.assertEqual(rows[0]["risk_reward"], "合格 2.5:1")
        self.assertEqual(rows[0]["buy_point_quality"], "买点成立")
        self.assertEqual(rows[0]["review_status"], "预演命中")
        self.assertIn("开盘核心", rows[0]["standard_action"])
        self.assertEqual(rows[1]["buy_point_quality"], "主目标不可成交")
        self.assertIn("2:1", rows[1]["risk_reward"])

    def test_rebuilt_same_day_snapshot_drops_stale_extreme_mentions_from_previous_index(self):
        stale_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "601991", "name": "大唐发电", "sector": "电力", "conviction_reason": "趋势辨识度高"},
                {"code": "002342", "name": "巨力索具", "sector": "商业航天", "conviction_reason": "趋势辨识度高"},
            ],
            market_branch="旧结果",
            sector_relationship_state="旧结果",
        )
        refreshed_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "001259", "name": "利仁科技", "sector": "股权转让", "conviction_reason": "板块锚定龙"},
            ],
            market_branch="新结果",
            sector_relationship_state="新结果",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(stale_snapshot, root_dir=root)
            result = write_decision_ledger_artifacts(refreshed_snapshot, root_dir=root)

        rows = build_extreme_conviction_backtest_rows(result["index"], max_rows=10)
        self.assertEqual([row["stock_code"] for row in rows if row["mention_trade_date"] == "2026-05-18"], ["001259"])
        self.assertNotIn("601991", result["index"]["by_stock_code"])
        self.assertNotIn("002342", result["index"]["by_stock_code"])

    def test_rebuilt_same_day_snapshot_drops_only_stale_mention_when_stock_has_older_valid_case(self):
        older_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {"code": "601991", "name": "大唐发电", "sector": "电力", "conviction_reason": "旧的有效样本"},
            ],
            market_branch="旧日有效结果",
            sector_relationship_state="旧日有效结果",
        )
        stale_same_day_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "601991", "name": "大唐发电", "sector": "电力", "conviction_reason": "趋势辨识度高"},
                {"code": "002342", "name": "巨力索具", "sector": "商业航天", "conviction_reason": "趋势辨识度高"},
            ],
            market_branch="旧结果",
            sector_relationship_state="旧结果",
        )
        refreshed_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "001259", "name": "利仁科技", "sector": "股权转让", "conviction_reason": "板块锚定龙"},
            ],
            market_branch="新结果",
            sector_relationship_state="新结果",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(older_snapshot, root_dir=root)
            write_decision_ledger_artifacts(stale_same_day_snapshot, root_dir=root)
            result = write_decision_ledger_artifacts(refreshed_snapshot, root_dir=root)

        rows = build_extreme_conviction_backtest_rows(result["index"], max_rows=10)
        same_day_codes = [row["stock_code"] for row in rows if row["mention_trade_date"] == "2026-05-18"]
        old_day_codes = [row["stock_code"] for row in rows if row["mention_trade_date"] == "2026-05-12"]

        self.assertEqual(same_day_codes, ["001259"])
        self.assertEqual(old_day_codes, ["601991"])
        self.assertIn("601991", result["index"]["by_stock_code"])
        self.assertNotIn("002342", result["index"]["by_stock_code"])

    def test_pruning_same_day_extreme_mentions_refreshes_cached_backtest_rows(self):
        index = {
            "by_stock_code": {
                "601991": [
                    {
                        "stock_code": "601991",
                        "stock_name": "大唐发电",
                        "latest_trade_date": "2026-05-18",
                        "cycle_closed": False,
                        "planned_participation": {"source_tier": "extreme_conviction"},
                        "mentions": [
                            {"mention_trade_date": "2026-05-12", "source_section": "极度看好名单"},
                            {"mention_trade_date": "2026-05-18", "source_section": "极度看好名单"},
                        ],
                    }
                ],
                "001259": [
                    {
                        "stock_code": "001259",
                        "stock_name": "利仁科技",
                        "latest_trade_date": "2026-05-18",
                        "cycle_closed": False,
                        "planned_participation": {"source_tier": "extreme_conviction"},
                        "mentions": [
                            {"mention_trade_date": "2026-05-18", "source_section": "极度看好名单"},
                        ],
                    }
                ],
            },
            "extreme_conviction_backtest_rows": [
                {"mention_trade_date": "2026-05-18", "stock_code": "601991", "stock_name": "大唐发电"},
                {"mention_trade_date": "2026-05-18", "stock_code": "001259", "stock_name": "利仁科技"},
                {"mention_trade_date": "2026-05-12", "stock_code": "601991", "stock_name": "大唐发电"},
            ],
        }

        pruned = prune_replaced_same_day_extreme_mentions(
            index,
            trade_date="2026-05-18",
            current_codes={"001259"},
        )

        cached_same_day_codes = [
            row["stock_code"]
            for row in pruned["extreme_conviction_backtest_rows"]
            if row["mention_trade_date"] == "2026-05-18"
        ]
        cached_old_day_codes = [
            row["stock_code"]
            for row in pruned["extreme_conviction_backtest_rows"]
            if row["mention_trade_date"] == "2026-05-12"
        ]

        self.assertEqual(cached_same_day_codes, ["001259"])
        self.assertEqual(cached_old_day_codes, ["601991"])

    def test_rebuilding_index_from_historical_snapshot_drops_future_extreme_mentions(self):
        historical_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-15",
            extreme_conviction_list=[
                {"code": "001259", "name": "利仁科技", "sector": "股权转让", "conviction_reason": "旧日样本"},
            ],
            market_branch="旧日有效结果",
            sector_relationship_state="旧日有效结果",
        )
        historical_case = historical_snapshot["cases"][0]
        historical_case["mentions"].append(
            {
                "mention_trade_date": "2026-05-18",
                "rank": 1,
                "source_section": "极度看好名单",
                "planned_participation": {"source_tier": "extreme_conviction"},
            }
        )
        refreshed_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "000417", "name": "合百集团", "sector": "股权转让", "conviction_reason": "新名单"},
                {"code": "002208", "name": "合肥城建", "sector": "房地产", "conviction_reason": "新名单"},
                {"code": "300657", "name": "弘信电子", "sector": "算力", "conviction_reason": "新名单"},
            ],
            market_branch="新结果",
            sector_relationship_state="新结果",
        )

        index = build_decision_ledger_index(historical_snapshot)
        index = build_decision_ledger_index(refreshed_snapshot, previous_index=index)

        same_day_codes = {
            row["stock_code"]
            for row in index["extreme_conviction_backtest_rows"]
            if row["mention_trade_date"] == "2026-05-18"
        }
        older_mentions = [
            mention
            for record in index["by_stock_code"].get("001259", [])
            for mention in record.get("mentions", [])
        ]

        self.assertEqual(same_day_codes, {"000417", "002208", "300657"})
        self.assertEqual([mention["mention_trade_date"] for mention in older_mentions], ["2026-05-15"])

    def test_backtest_rows_are_built_per_extreme_conviction_mention(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "hypothesis": {"sector_candidate": "电力"},
                        "latest_trade_date": "2026-05-15",
                        "cycle_day": 3,
                        "cycle_closed": False,
                        "planned_participation": {
                            "source_tier": "extreme_conviction",
                            "participation_window": "竞价表态 + 回封参与",
                            "entry_timing": "open_core",
                            "buy_window": "09:30-09:35",
                            "limit_up_inertia_level": "高惯性",
                            "risk_reward_ratio": 2.0,
                        },
                        "participation_review_status": "预演命中",
                        "participation_review": {
                            "status": "预演命中",
                            "review_trade_date": "2026-05-14",
                            "entry_decision": "open_buy",
                            "same_day_action": "按09:30-09:35开盘核心参与",
                            "market_outcome": "开盘+2.00%，最高+10.00%，收盘+10.00%",
                        },
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-13",
                                "rank": 2,
                                "source_section": "极度看好名单",
                                "reason": "板块锚定龙 / 首波先锋",
                                "planned_participation": {
                                    "source_tier": "extreme_conviction",
                                    "buy_window": "09:30-09:35",
                                    "limit_up_inertia_level": "高惯性",
                                    "risk_reward_ratio": 2.0,
                                },
                                "participation_review": {
                                    "status": "预演命中",
                                    "review_trade_date": "2026-05-14",
                                    "entry_decision": "open_buy",
                                    "same_day_action": "按09:30-09:35开盘核心参与",
                                },
                            },
                            {
                                "mention_trade_date": "2026-05-14",
                                "rank": 1,
                                "source_section": "极度看好名单",
                                "reason": "板块锚定龙 / 中位传导",
                                "planned_participation": {
                                    "source_tier": "extreme_conviction",
                                    "buy_window": "09:50-10:10",
                                    "limit_up_inertia_level": "高惯性",
                                    "risk_reward_plan": "默认要求盈亏比不低于2:1",
                                },
                            },
                        ],
                    }
                ]
            }
        }

        rows = build_extreme_conviction_backtest_rows(index, max_rows=5)

        self.assertEqual([row["mention_trade_date"] for row in rows], ["2026-05-14", "2026-05-13"])
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["source_section"], "极度看好名单")
        self.assertEqual(rows[0]["reason"], "板块锚定龙 / 中位传导")
        self.assertEqual(rows[0]["sector_candidate"], "电力")
        self.assertEqual(rows[0]["buy_window"], "09:50-10:10")
        self.assertEqual(rows[0]["review_status"], "等待复盘")
        self.assertEqual(rows[0]["buy_point_quality"], "等待事实")
        self.assertEqual(rows[1]["rank"], 2)
        self.assertEqual(rows[1]["reason"], "板块锚定龙 / 首波先锋")
        self.assertEqual(rows[1]["buy_window"], "09:30-09:35")
        self.assertEqual(rows[1]["review_status"], "预演命中")
        self.assertEqual(rows[1]["buy_point_quality"], "买点成立")

    def test_backtest_rows_dedupe_repeated_mentions_for_same_stock_and_date(self):
        index = {
            "by_stock_code": {
                "688549": [
                    {
                        "stock_code": "688549",
                        "stock_name": "中巨芯",
                        "latest_trade_date": "2026-05-15",
                        "cycle_day": 1,
                        "cycle_closed": False,
                        "planned_participation": {
                            "source_tier": "extreme_conviction",
                            "participation_window": "竞价表态 + 回封参与",
                            "buy_window": "09:30-09:35",
                            "limit_up_inertia_level": "高惯性",
                        },
                        "mentions": [
                            {"mention_trade_date": "2026-05-15", "rank": 1, "source_section": "极度看好名单"},
                            {"mention_trade_date": "2026-05-15", "rank": 1, "source_section": "极度看好名单"},
                        ],
                    }
                ]
            }
        }

        rows = build_extreme_conviction_backtest_rows(index, max_rows=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["stock_code"], "688549")
        self.assertEqual(rows[0]["mention_trade_date"], "2026-05-15")

    def test_renders_extreme_conviction_backtest_table_from_index(self):
        index = {
            "by_stock_code": {
                "600578": [
                    {
                        "stock_code": "600578",
                        "stock_name": "京能电力",
                        "latest_trade_date": "2026-05-15",
                        "cycle_day": 2,
                        "planned_participation": {
                            "source_tier": "extreme_conviction",
                            "participation_window": "竞价表态 + 回封参与",
                            "buy_window": "09:30-09:35",
                            "limit_up_inertia_level": "高惯性",
                            "next_day_limit_probability_band": "高于普通上涨样本",
                            "risk_reward_state": "合格",
                            "risk_reward_ratio": 2.5,
                        },
                        "participation_review": {
                            "status": "预演命中",
                            "entry_decision": "open_buy",
                            "same_day_action": "按09:30-09:35开盘核心参与",
                        },
                        "mentions": [{"mention_trade_date": "2026-05-14", "source_section": "极度看好名单"}],
                    }
                ]
            }
        }

        lines = render_extreme_conviction_backtest_lines(index)
        rendered = "\n".join(lines)

        self.assertIn("**重点观察历史回测表**", rendered)
        self.assertIn("| 入选日 | 股票 | 代码 | 选股样本 | 买点窗口 | 盈亏比 | 买点质量 | 执行复盘 | 标准动作 |", rendered)
        self.assertIn("| 2026-05-14 | 京能电力 | 600578 | 高惯性 / 高于普通上涨样本 | 09:30-09:35 | 合格 2.5:1 | 买点成立 | 预演命中 | 按09:30-09:35开盘核心参与 |", rendered)

    def test_writer_auto_reviews_previous_extreme_conviction_cases_from_market_facts(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-13",
            extreme_conviction_list=[
                {
                    "code": "688146",
                    "name": "中船特气",
                    "sector": "半导体",
                    "conviction_reason": "主线内核 / 板块锚定龙 / 首波先锋",
                    "participation_window": "竞价表态 + 回封参与",
                    "attack_state": "100%",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="半导体主攻",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-14",
            extreme_conviction_list=[
                {
                    "code": "600578",
                    "name": "京能电力",
                    "sector": "电力",
                    "conviction_reason": "板块锚定龙 / 首波先锋",
                }
            ],
            market_branch="主线切到半导体",
            sector_relationship_state="半导体主攻，电力次强",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(
                second,
                root_dir=root,
                review_market_facts_by_stock_code={
                    "688146": {
                        "review_trade_date": "2026-05-14",
                        "prev_close": 117.6,
                        "open": 132.0,
                        "low": 131.71,
                        "high": 141.12,
                        "close": 141.12,
                        "sector_supported": True,
                    }
                },
            )

            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        record = index["by_stock_code"]["688146"][0]
        review = record["participation_review"]
        self.assertEqual(record["latest_trade_date"], "2026-05-14")
        self.assertEqual(record["participation_review_status"], "预演命中")
        self.assertEqual(review["status"], "预演命中")
        self.assertEqual(review["review_trade_date"], "2026-05-14")
        self.assertEqual(review["entry_decision"], "open_buy")
        self.assertIn("09:30-09:35", review["same_day_action"])
        self.assertIn("不补票", review["avoid_action"])
        self.assertIn("30分钟结构", review["next_action"])
        self.assertIn("竞价表态", review["standard_answer_basis"])

    def test_writer_can_review_previous_cases_from_local_stock_kline_table(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-13",
            extreme_conviction_list=[
                {
                    "code": "600578",
                    "name": "京能电力",
                    "sector": "电力",
                    "conviction_reason": "板块锚定龙 / 首波先锋 / 分歧转一致形态",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="电力主攻",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-14",
            extreme_conviction_list=[],
            market_branch="防守",
            sector_relationship_state="暂未分出",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            kline_dir = root / "data" / "snap-ui" / "stock-klines"
            kline_dir.mkdir(parents=True)
            (kline_dir / "2026-05-14-600578.json").write_text(
                json.dumps(
                    {
                        "stockCode": "600578",
                        "stockName": "京能电力",
                        "rows": [
                            {"date": "2026-05-13", "open": 5.45, "high": 5.79, "low": 5.41, "close": 5.79},
                            {"date": "2026-05-14", "open": 6.37, "high": 6.37, "low": 6.10, "close": 6.37},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(second, root_dir=root)
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        review = index["by_stock_code"]["600578"][0]["participation_review"]
        self.assertEqual(review["status"], "预演命中")
        self.assertEqual(review["review_trade_date"], "2026-05-14")
        self.assertIn("开盘核心", review["same_day_action"])

    def test_writer_keeps_daily_low_reversal_as_waiting_window_review(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-14",
            extreme_conviction_list=[
                {
                    "code": "600578",
                    "name": "京能电力",
                    "sector": "电力",
                    "conviction_reason": "板块锚定龙 / 首波先锋 / 分歧转一致形态",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="电力主攻",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-15",
            extreme_conviction_list=[],
            market_branch="防守",
            sector_relationship_state="暂未分出",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            kline_dir = root / "data" / "snap-ui" / "stock-klines"
            kline_dir.mkdir(parents=True)
            (kline_dir / "2026-05-15-600578.json").write_text(
                json.dumps(
                    {
                        "stockCode": "600578",
                        "stockName": "京能电力",
                        "rows": [
                            {"date": "2026-05-14", "open": 5.60, "high": 5.88, "low": 5.55, "close": 5.88},
                            {"date": "2026-05-15", "open": 6.00, "high": 6.47, "low": 5.43, "close": 6.47},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(second, root_dir=root)
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        review = index["by_stock_code"]["600578"][0]["participation_review"]
        self.assertEqual(review["status"], "等待窗口复盘")
        self.assertEqual(review["entry_decision"], "waiting_window_review")
        self.assertIn("窗口事实", review["standard_answer_basis"])

    def test_writer_rewrites_waiting_review_from_local_minute_window(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-14",
            extreme_conviction_list=[
                {
                    "code": "600578",
                    "name": "京能电力",
                    "sector": "电力",
                    "conviction_reason": "板块锚定龙 / 首波先锋 / 分歧转一致形态",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="电力主攻",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-15",
            extreme_conviction_list=[],
            market_branch="防守",
            sector_relationship_state="暂未分出",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            kline_dir = root / "data" / "snap-ui" / "stock-klines"
            minute_dir = root / "data" / "snap-ui" / "stock-minute-bars"
            kline_dir.mkdir(parents=True)
            minute_dir.mkdir(parents=True)
            (kline_dir / "2026-05-15-600578.json").write_text(
                json.dumps(
                    {
                        "stockCode": "600578",
                        "stockName": "京能电力",
                        "rows": [
                            {"date": "2026-05-14", "open": 5.60, "high": 5.88, "low": 5.55, "close": 5.88},
                            {"date": "2026-05-15", "open": 6.00, "high": 6.47, "low": 5.43, "close": 6.47},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (minute_dir / "2026-05-15-600578.json").write_text(
                json.dumps(
                    {
                        "stockCode": "600578",
                        "stockName": "京能电力",
                        "windowReferencePrice": 5.88,
                        "rows": [
                            {"datetime": "2026-05-15 09:45:00", "open": 5.96, "high": 5.99, "low": 5.43, "close": 5.86},
                            {"datetime": "2026-05-15 09:50:00", "open": 5.86, "high": 5.92, "low": 5.82, "close": 5.90},
                            {"datetime": "2026-05-15 09:55:00", "open": 5.90, "high": 6.03, "low": 5.88, "close": 6.01},
                            {"datetime": "2026-05-15 10:00:00", "open": 6.01, "high": 6.18, "low": 5.99, "close": 6.15},
                            {"datetime": "2026-05-15 10:10:00", "open": 6.15, "high": 6.25, "low": 6.12, "close": 6.24},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(second, root_dir=root)
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        review = index["by_stock_code"]["600578"][0]["participation_review"]
        self.assertEqual(review["status"], "预演命中")
        self.assertEqual(review["entry_decision"], "window_confirm_buy")
        self.assertIn("09:50-10:10承接成立", review["standard_answer_basis"])

    def test_waiting_review_mentions_can_be_rewritten_when_new_market_fact_arrives(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-14",
            extreme_conviction_list=[
                {
                    "code": "600578",
                    "name": "京能电力",
                    "sector": "电力",
                    "conviction_reason": "板块锚定龙 / 首波先锋 / 分歧转一致形态",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="电力主攻",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-15",
            extreme_conviction_list=[],
            market_branch="防守",
            sector_relationship_state="暂未分出",
        )
        third = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[],
            market_branch="防守",
            sector_relationship_state="暂未分出",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(
                second,
                root_dir=root,
                review_market_facts_by_stock_code={
                    "600578": {
                        "review_trade_date": "2026-05-15",
                        "prev_close": 5.88,
                        "open": 6.00,
                        "high": 6.47,
                        "low": 5.43,
                        "close": 6.47,
                    }
                },
            )
            write_decision_ledger_artifacts(
                third,
                root_dir=root,
                review_market_facts_by_stock_code={
                    "600578": {
                        "review_trade_date": "2026-05-18",
                        "prev_close": 6.47,
                        "open": 6.60,
                        "high": 7.12,
                        "low": 6.58,
                        "close": 7.12,
                        "first_minutes_accepted": True,
                        "sector_supported": True,
                    }
                },
            )
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        review = index["by_stock_code"]["600578"][0]["participation_review"]
        self.assertEqual(review["review_trade_date"], "2026-05-18")
        self.assertIn(review["status"], {"预演命中", "等待窗口复盘"})
        self.assertNotEqual(review["status"], "等待复盘")

    def test_writer_keeps_previous_review_when_same_stock_reappears_in_open_cycle(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-13",
            extreme_conviction_list=[
                {
                    "code": "603052",
                    "name": "可川科技",
                    "sector": "消费电子",
                    "conviction_reason": "首波先锋 / 分歧转一致形态",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="消费电子次强",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-14",
            extreme_conviction_list=[
                {
                    "code": "603052",
                    "name": "可川科技",
                    "sector": "消费电子",
                    "conviction_reason": "继续分歧转一致",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="消费电子次强",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(
                second,
                root_dir=root,
                review_market_facts_by_stock_code={
                    "603052": {
                        "review_trade_date": "2026-05-14",
                        "prev_close": 104.89,
                        "open": 111.50,
                        "low": 111.50,
                        "high": 115.38,
                        "close": 115.38,
                        "sector_supported": True,
                    }
                },
            )
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))
            snapshot = json.loads((root / "data" / "decision-ledger" / "2026-05-14.json").read_text(encoding="utf-8"))

        record = index["by_stock_code"]["603052"][0]
        self.assertEqual(record["case_id"], "2026-05-13-603052-01")
        self.assertEqual(record["participation_review_status"], "预演命中")
        self.assertEqual(record["participation_review"]["review_trade_date"], "2026-05-14")
        self.assertEqual(snapshot["cases"][0]["participation_review"]["status"], "预演命中")
        self.assertEqual([item["mention_trade_date"] for item in record["mentions"]], ["2026-05-13", "2026-05-14"])

    def test_rewriting_same_trade_date_does_not_duplicate_mentions(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-15",
            extreme_conviction_list=[
                {
                    "code": "688549",
                    "name": "中巨芯",
                    "sector": "半导体",
                    "conviction_reason": "板块锚定龙",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="半导体主攻",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-15",
            extreme_conviction_list=[
                {
                    "code": "688549",
                    "name": "中巨芯",
                    "sector": "半导体",
                    "conviction_reason": "板块锚定龙",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="半导体主攻",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(second, root_dir=root)
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))
            snapshot = json.loads((root / "data" / "decision-ledger" / "2026-05-15.json").read_text(encoding="utf-8"))

        record = index["by_stock_code"]["688549"][0]
        self.assertEqual([item["mention_trade_date"] for item in record["mentions"]], ["2026-05-15"])
        self.assertEqual([item["mention_trade_date"] for item in snapshot["cases"][0]["mentions"]], ["2026-05-15"])

    def test_rewriting_same_trade_date_replaces_rank_changed_mention(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "000417", "name": "合百集团", "sector": "百货", "conviction_reason": "首板"},
                {"code": "603779", "name": "威龙股份", "sector": "红黄酒", "conviction_reason": "首板"},
                {"code": "300657", "name": "弘信电子", "sector": "元器件", "conviction_reason": "首板"},
            ],
            market_branch="旧结果",
            sector_relationship_state="旧结果",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "000417", "name": "合百集团", "sector": "百货", "conviction_reason": "首板"},
                {"code": "300657", "name": "弘信电子", "sector": "元器件", "conviction_reason": "首板"},
                {"code": "603779", "name": "威龙股份", "sector": "红黄酒", "conviction_reason": "首板"},
            ],
            market_branch="新结果",
            sector_relationship_state="新结果",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(second, root_dir=root)
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        rows = [
            row
            for row in index["extreme_conviction_backtest_rows"]
            if row["mention_trade_date"] == "2026-05-18" and row["stock_code"] == "300657"
        ]
        record = index["by_stock_code"]["300657"][0]

        self.assertEqual(len(rows), 1)
        self.assertEqual([mention["rank"] for mention in record["mentions"]], [2])

    def test_build_index_sanitizes_duplicate_same_day_mentions_inside_snapshot(self):
        snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "300657", "name": "弘信电子", "sector": "元器件", "conviction_reason": "首板"},
            ],
            market_branch="新结果",
            sector_relationship_state="新结果",
        )
        snapshot["cases"][0]["mentions"].append(
            {
                "mention_trade_date": "2026-05-18",
                "rank": 2,
                "source_section": "极度看好名单",
                "planned_participation": {"source_tier": "extreme_conviction"},
            }
        )

        index = build_decision_ledger_index(snapshot)
        rows = [
            row
            for row in index["extreme_conviction_backtest_rows"]
            if row["mention_trade_date"] == "2026-05-18" and row["stock_code"] == "300657"
        ]
        record = index["by_stock_code"]["300657"][0]

        self.assertEqual(len(rows), 1)
        self.assertEqual([mention["rank"] for mention in record["mentions"]], [2])

    def test_writer_reviews_latest_unreviewed_mention_even_when_cycle_has_old_review(self):
        first = build_decision_ledger_snapshot(
            trade_date="2026-05-12",
            extreme_conviction_list=[
                {
                    "code": "603007",
                    "name": "花王股份",
                    "sector": "汽车零部",
                    "conviction_reason": "板块锚定龙",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="汽车零部主攻",
        )
        second = build_decision_ledger_snapshot(
            trade_date="2026-05-13",
            extreme_conviction_list=[
                {
                    "code": "603007",
                    "name": "花王股份",
                    "sector": "汽车零部",
                    "conviction_reason": "继续一字强化",
                    "participation_window": "竞价表态 + 回封参与",
                }
            ],
            market_branch="主线爆发",
            sector_relationship_state="汽车零部主攻",
        )
        third = build_decision_ledger_snapshot(
            trade_date="2026-05-14",
            extreme_conviction_list=[],
            market_branch="防守",
            sector_relationship_state="暂未分出",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(first, root_dir=root)
            write_decision_ledger_artifacts(
                second,
                root_dir=root,
                review_market_facts_by_stock_code={
                    "603007": {
                        "review_trade_date": "2026-05-13",
                        "prev_close": 7.65,
                        "open": 8.42,
                        "low": 8.42,
                        "high": 8.42,
                        "close": 8.42,
                    }
                },
            )
            write_decision_ledger_artifacts(
                third,
                root_dir=root,
                review_market_facts_by_stock_code={
                    "603007": {
                        "review_trade_date": "2026-05-14",
                        "prev_close": 8.42,
                        "open": 9.26,
                        "low": 9.26,
                        "high": 9.26,
                        "close": 9.26,
                    }
                },
            )
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        mentions = index["by_stock_code"]["603007"][0]["mentions"]
        self.assertEqual((mentions[0]["participation_review"] or {})["review_trade_date"], "2026-05-13")
        self.assertEqual((mentions[1]["participation_review"] or {})["review_trade_date"], "2026-05-14")
        self.assertEqual((mentions[1]["participation_review"] or {})["status"], "主目标不可成交")


if __name__ == "__main__":
    unittest.main()
