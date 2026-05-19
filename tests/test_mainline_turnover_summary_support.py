import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.mainline_turnover_summary_support import (
    resolve_mainline_attack_evidence_rows,
    resolve_mainline_attack_evidence_summary,
    resolve_mainline_capacity_regime_summary,
)


class MainlineTurnoverSummarySupportTest(unittest.TestCase):
    def test_resolve_mainline_capacity_regime_summary_derives_from_nested_legacy_double_mainline(self):
        summary = resolve_mainline_capacity_regime_summary(
            {
                "mainline_turnover_summary": {
                    "double_mainline_summary": {
                        "cycle_mainline": "电力",
                        "daily_attack_line": "半导体",
                        "relationship": "半导体尝试接替电力",
                        "tomorrow_action": "先看资金是否继续选择半导体",
                    }
                }
            }
        )

        self.assertEqual(summary["mainline_capacity"], "容量待累计")
        self.assertEqual(summary["mainline_regime"], "主线+背景线")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["other_lines"], "电力")
        self.assertEqual(summary["sector_relationship_state"], "半导体尝试接替电力")
        self.assertEqual(summary["tomorrow_action"], "先看资金是否继续选择半导体")

    def test_resolve_mainline_attack_evidence_summary_from_nested_turnover_summary(self):
        summary = resolve_mainline_attack_evidence_summary(
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "candidate_lines": ["电力"],
                        "background_lines": ["化学制品"],
                        "relationship_hint": "双主线竞争",
                        "evidence_labels": ["资金净流入靠前", "批量涨停"],
                        "confirmation_evidence": "半导体资金净流入靠前，涨停更集中",
                        "evidence_gaps": [],
                    }
                }
            }
        )

        self.assertEqual(summary["attack_state"], "confirmed_attack")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["candidate_lines"], ["电力"])
        self.assertEqual(summary["background_lines"], ["化学制品"])

    def test_resolve_mainline_attack_evidence_rows_formats_top_three_audit_rows(self):
        rows = resolve_mainline_attack_evidence_rows(
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "candidate_lines": ["电力"],
                        "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
                        "sector_evidence_rows": [
                            {
                                "sector_name": "半导体",
                                "net_inflow_rank": 1,
                                "net_inflow_amount": 45.0,
                                "limit_up_count": 5,
                                "high_anchor_height": 4,
                                "turnover_share_change": 1.6,
                            },
                            {
                                "sector_name": "电力",
                                "net_inflow_rank": 2,
                                "net_inflow_amount": 8.0,
                                "limit_up_count": 1,
                                "high_anchor_height": 1,
                                "turnover_share_change": -0.5,
                            },
                            {
                                "sector_name": "化学制品",
                                "net_inflow_rank": 5,
                                "net_inflow_amount": 3.2,
                                "limit_up_count": 2,
                                "high_anchor_height": 2,
                            },
                            {
                                "sector_name": "消费",
                                "net_inflow_rank": 8,
                                "net_inflow_amount": 1.0,
                                "limit_up_count": 1,
                            },
                        ],
                    }
                }
            }
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["sector_name"], "半导体")
        self.assertEqual(rows[0]["attack_state"], "确认主攻线")
        self.assertEqual(rows[0]["net_inflow_rank"], "第1")
        self.assertEqual(rows[0]["net_inflow_amount"], "+45.00亿")
        self.assertEqual(rows[0]["limit_up_count"], "5")
        self.assertEqual(rows[0]["high_anchor_height"], "4")
        self.assertEqual(rows[0]["turnover_share_change"], "+1.6pct")
        self.assertEqual(rows[0]["conclusion"], "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张")
        self.assertEqual(rows[1]["attack_state"], "候选线")

    def test_resolve_mainline_attack_evidence_rows_ignores_board_labels(self):
        rows = resolve_mainline_attack_evidence_rows(
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "candidate_attack",
                        "candidate_lines": ["HS", "通信设备", "元件"],
                        "sector_evidence_rows": [
                            {"sector_name": "HS", "limit_up_count": 91, "high_anchor_height": 9},
                            {"sector_name": "GEM", "limit_up_count": 9, "high_anchor_height": 3},
                            {
                                "sector_name": "通信设备",
                                "net_inflow_rank": 1,
                                "net_inflow_amount": 50.0,
                                "limit_up_count": 4,
                                "high_anchor_height": 2,
                            },
                            {"sector_name": "元件", "net_inflow_rank": 2, "net_inflow_amount": 28.0},
                        ],
                    }
                }
            }
        )

        self.assertEqual([row["sector_name"] for row in rows], ["通信设备", "元件"])
        self.assertTrue(all("HS" not in row["conclusion"] for row in rows))


if __name__ == "__main__":
    unittest.main()
