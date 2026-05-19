import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class MainlineAttackEvidenceRuntimeTest(unittest.TestCase):
    def _load_module(self):
        return importlib.import_module("domains.market_state.mainline_turnover_summary_runtime")

    def test_confirmed_single_mainline_requires_fund_and_strength_evidence(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {
                    "sector_name": "半导体",
                    "net_inflow_amount": 42.5,
                    "net_inflow_rank": 1,
                    "limit_up_count": 8,
                    "high_anchor_height": 4,
                    "high_anchor_name": "中船特气",
                    "broad_rally_pct": 72.0,
                    "strong_gain_count": 18,
                    "turnover_share_pct": 12.4,
                    "turnover_share_change": 1.6,
                },
                {
                    "sector_name": "电力",
                    "net_inflow_amount": 8.0,
                    "net_inflow_rank": 5,
                    "limit_up_count": 2,
                    "high_anchor_height": 2,
                    "turnover_share_pct": 7.1,
                    "turnover_share_change": -0.4,
                },
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "confirmed_attack")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["candidate_lines"], [])
        self.assertIn("资金净流入靠前", summary["evidence_labels"])
        self.assertIn("批量涨停", summary["evidence_labels"])
        self.assertIn("高标强度突出", summary["evidence_labels"])
        self.assertIn("成交占比扩张", summary["evidence_labels"])
        self.assertEqual(summary["evidence_gaps"], [])
        self.assertEqual(summary["confirmation_evidence"], "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张")

    def test_double_line_competition_when_two_sectors_have_cross_validated_attack(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {
                    "sector_name": "半导体",
                    "net_inflow_amount": 35.0,
                    "net_inflow_rank": 1,
                    "limit_up_count": 7,
                    "high_anchor_height": 4,
                },
                {
                    "sector_name": "电力",
                    "net_inflow_amount": 30.0,
                    "net_inflow_rank": 2,
                    "limit_up_count": 6,
                    "high_anchor_height": 3,
                },
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "confirmed_attack")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["candidate_lines"], ["电力"])
        self.assertEqual(summary["relationship_hint"], "双主线竞争")

    def test_chaotic_rotation_when_three_local_hotspots_have_no_clear_winner(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {"sector_name": "半导体", "net_inflow_amount": 12.0, "net_inflow_rank": 3, "limit_up_count": 2},
                {"sector_name": "电力", "net_inflow_amount": 11.0, "net_inflow_rank": 4, "high_anchor_height": 2},
                {"sector_name": "化学制品", "net_inflow_amount": 9.0, "net_inflow_rank": 5, "strong_gain_count": 8},
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "chaotic_rotation")
        self.assertEqual(summary["primary_line"], "")
        self.assertEqual(summary["candidate_lines"], ["半导体", "电力", "化学制品"])
        self.assertEqual(summary["relationship_hint"], "混沌接力")
        self.assertIn("多方向局部活跃但资金未明显胜出", summary["confirmation_evidence"])

    def test_no_attack_when_evidence_is_distributed_and_weak(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {
                    "sector_name": "机器人",
                    "net_inflow_amount": 2.0,
                    "net_inflow_rank": 12,
                    "limit_up_count": 1,
                    "turnover_share_change": -0.2,
                },
                {"sector_name": "军工", "net_inflow_amount": -1.0, "net_inflow_rank": 24, "limit_up_count": 0},
            ],
            market_regime="弱市",
        )

        self.assertEqual(summary["attack_state"], "no_attack")
        self.assertEqual(summary["primary_line"], "")
        self.assertEqual(summary["candidate_lines"], [])
        self.assertEqual(summary["confirmation_evidence"], "资金未形成明确进攻方向")

    def test_limit_up_without_fund_support_is_candidate_not_confirmed(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {"sector_name": "电力", "net_inflow_amount": -6.0, "net_inflow_rank": 28, "limit_up_count": 9, "high_anchor_height": 4}
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "candidate_attack")
        self.assertEqual(summary["primary_line"], "")
        self.assertEqual(summary["candidate_lines"], ["电力"])
        self.assertIn("情绪强于资金确认", summary["evidence_gaps"])

    def test_fund_probe_without_strength_support_is_candidate_not_confirmed(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {
                    "sector_name": "半导体",
                    "net_inflow_amount": 50.0,
                    "net_inflow_rank": 1,
                    "limit_up_count": 1,
                    "high_anchor_height": 1,
                    "broad_rally_pct": 42.0,
                }
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "candidate_attack")
        self.assertEqual(summary["primary_line"], "")
        self.assertEqual(summary["candidate_lines"], ["半导体"])
        self.assertIn("资金试探但强度不足", summary["evidence_gaps"])

    def test_small_ranked_inflow_and_batch_limit_ups_are_not_enough_to_confirm_mainline(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {
                    "sector_name": "化学制品",
                    "net_inflow_amount": 3.39,
                    "net_inflow_rank": 3,
                    "limit_up_count": 5,
                    "high_anchor_height": 2,
                    "turnover_share_pct": 1.64,
                    "turnover_share_change": 0.0,
                },
                {
                    "sector_name": "养殖业",
                    "net_inflow_amount": 7.59,
                    "net_inflow_rank": 1,
                    "limit_up_count": 2,
                    "high_anchor_height": 2,
                    "turnover_share_pct": 0.29,
                    "turnover_share_change": 0.0,
                },
                {
                    "sector_name": "家居用品",
                    "net_inflow_amount": 0.74,
                    "net_inflow_rank": 11,
                    "limit_up_count": 2,
                    "high_anchor_height": 5,
                    "turnover_share_pct": 0.28,
                    "turnover_share_change": 0.0,
                },
            ],
            market_regime="震荡",
        )

        self.assertNotEqual(summary["attack_state"], "confirmed_attack")
        self.assertEqual(summary["attack_state"], "chaotic_rotation")
        self.assertEqual(summary["primary_line"], "")
        self.assertIn("化学制品", summary["candidate_lines"])
        self.assertIn("资金确认不足", summary["evidence_gaps"])


if __name__ == "__main__":
    unittest.main()
