import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.legacy_stage_summary import build_legacy_report_stage_rows


class LegacyStageSummaryTest(unittest.TestCase):
    def test_legacy_stage_summary_uses_dynamic_stage_keys_instead_of_fixed_steps(self):
        rows = build_legacy_report_stage_rows(
            {
                "report_stages": [
                    {"stage_key": "market_environment", "title": "环境与跟随裁决", "summary": "🟡 条件跟随；先看环境"},
                    {"stage_key": "selection_focus", "title": "主线与筛选", "summary": "观察池15只"},
                    {"stage_key": "execution_gate", "title": "执行" + "门" + "控", "summary": "只等唯一动作"},
                ],
                "watchlist_count": 15,
                "core_count": 2,
                "secondary_count": 1,
                "crossline_count": 1,
                "risk_summary": "当前只等唯一动作",
                "trade_gate_open": True,
                "best_stock": {"name": "军工一号", "code": "000001"},
                "watch_anchor": None,
                "watch_anchor_type": "",
                "abnormal_probe_parts": ["主线异动里先看谁：军工一号(000001)"],
            }
        )

        keys = [row["stage_key"] for row in rows]
        self.assertEqual(keys[0], "market_environment")
        self.assertIn("selection_focus", keys)
        self.assertIn("candidate_selection", keys)
        self.assertIn("risk_review", keys)
        self.assertIn("decisive_choice", keys)
        self.assertTrue(all("Step" not in row["stage_key"] for row in rows))
        self.assertTrue(any("军工一号(000001)" in row["guidance"] for row in rows))

    def test_legacy_stage_summary_can_render_only_enabled_nodes(self):
        rows = build_legacy_report_stage_rows(
            {
                "report_stages": [
                    {"stage_key": "market_environment", "title": "环境与跟随裁决", "summary": "🟡 条件跟随；先看环境"},
                    {"stage_key": "selection_focus", "title": "主线与筛选", "summary": "观察池15只"},
                ],
                "watchlist_count": 15,
                "core_count": 2,
                "secondary_count": 1,
                "crossline_count": 1,
                "risk_summary": "当前只等唯一动作",
                "trade_gate_open": True,
                "best_stock": {"name": "军工一号", "code": "000001"},
                "enabled_node_keys": ["market_environment", "decisive_choice"],
            }
        )

        keys = [row["stage_key"] for row in rows]
        self.assertEqual(keys, ["market_environment", "decisive_choice"])
        self.assertTrue(any("军工一号(000001)" in row["guidance"] for row in rows))

    def test_legacy_stage_summary_uses_data_driven_fallbacks_for_market_focus_and_style(self):
        rows = build_legacy_report_stage_rows(
            {
                "report_stages": [],
                "step0_prediction_cn": "🟢 明朗",
                "step0_action": "允许强势跟随",
                "watchlist_count": 15,
                "tracking_memory_status": {
                    "today_validated_items": [{"name": "老龙头", "code": "000002", "follow_state": "今日再次入池"}]
                },
                "final_gate": {"can_new_entry": True},
                "trade_gate_open": True,
                "best_stock": {"name": "军工一号", "code": "000001"},
            }
        )

        row_map = {row["stage_key"]: row["guidance"] for row in rows}
        self.assertEqual(row_map["market_environment"], "🟢 明朗；允许强势跟随")
        self.assertEqual(row_map["selection_focus"], "军工一号(000001)：已缩成明天唯一执行候选")
        self.assertEqual(row_map["execution_plan"], "短线；只等明天唯一能买的那只自己走出来")

    def test_legacy_stage_summary_turns_candidate_and_risk_rows_into_trade_directives(self):
        rows = build_legacy_report_stage_rows(
            {
                "report_stages": [],
                "core_count": 2,
                "secondary_count": 1,
                "crossline_count": 1,
                "risk_summary": "高位分歧加大",
                "best_stock": {"name": "军工一号", "code": "000001", "r_reward_ratio": 2.4},
                "final_gate": {"can_new_entry": True},
            }
        )

        row_map = {row["stage_key"]: row["guidance"] for row in rows}
        self.assertEqual(
            row_map["candidate_selection"],
            "2只主线核心 / 1只备选 / 1只跨线观察；先只在主线核心里做减法，目标缩到军工一号(000001)",
        )
        self.assertEqual(
            row_map["risk_review"],
            "高位分歧加大；只接受预估赚赔比 1:2.4 的试错，不接受大亏硬扛",
        )

    def test_legacy_stage_summary_selection_focus_drops_count_when_final_target_is_resolved(self):
        rows = build_legacy_report_stage_rows(
            {
                "report_stages": [],
                "watchlist_count": 15,
                "position_decision": {"target_position_pct": 50, "signal_grade": "50"},
                "final_target_resolution": {
                    "new_entry_target": {"name": "工业富联", "code": "601138"},
                    "display_target": {"name": "工业富联", "code": "601138"},
                    "capital_priority_decision": {
                        "capital_priority": "new_entry_after_old_exit",
                        "reason": "先处理旧仓，买工业富联(601138)",
                    },
                },
            }
        )

        row_map = {row["stage_key"]: row["guidance"] for row in rows}
        self.assertEqual(row_map["selection_focus"], "工业富联(601138)：明日目标标的，固定交易窗口内条件成立才执行")
        self.assertNotIn("15只；", row_map["selection_focus"])


if __name__ == "__main__":
    unittest.main()
