import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.reasoning_decision_support import build_reasoning_input_packet, compute_input_hash


class ReasoningDecisionSupportTest(unittest.TestCase):
    def test_builds_stable_reasoning_input_packet_from_snapshot(self):
        snapshot = {
            "market_fit_calibration": {"fit_label": "主线有效，池子偏窄"},
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "double_mainline_summary": {
                    "cycle_mainline": "半导体",
                    "daily_attack_line": "半导体",
                    "relationship": "周期主线与当天主攻线一致",
                    "tomorrow_action": "继续围绕半导体观察承接",
                },
            },
            "current_sector_turnover_snapshot": {
                "date": "2026-04-24",
                "sector_name": "半导体",
                "turnover_share_pct": 18.1,
            },
            "recent_sector_turnover_history": [
                {"date": "2026-04-23", "sector_name": "半导体", "turnover_share_pct": 15.8}
            ],
            "candidate_pool": [
                {
                    "code": "300613",
                    "name": "富瀚微",
                    "sector": "半导体",
                    "qualification": "观察，等10点确认",
                    "evidence": {"承接": "明日验证承接", "资金痕迹": "主线资金主动进攻"},
                }
            ],
            "source_status": {"ths_sector": "ok"},
        }

        packet = build_reasoning_input_packet("2026-04-24", snapshot, final_gate={"final_action": "观察"})

        self.assertEqual(packet["schema_version"], "reasoning_input.v1")
        self.assertEqual(packet["target_date"], "2026-04-24")
        self.assertEqual(packet["mainline_snapshot"]["current_mainline"], "半导体")
        self.assertEqual(packet["candidate_pool"][0]["id"], "300613")
        self.assertEqual(packet["candidate_pool"][0]["name"], "富瀚微")
        self.assertEqual(packet["execution_contract"]["final_action"], "观察")
        self.assertEqual(packet["source_status"]["ths_sector"], "ok")

    def test_compute_input_hash_is_order_stable_for_dict_keys(self):
        left = {"b": 2, "a": {"d": 4, "c": 3}}
        right = {"a": {"c": 3, "d": 4}, "b": 2}

        self.assertEqual(compute_input_hash(left), compute_input_hash(right))


if __name__ == "__main__":
    unittest.main()
