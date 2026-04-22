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
                    {"stage_key": "execution_gate", "title": "执行门控", "summary": "只等唯一动作"},
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


if __name__ == "__main__":
    unittest.main()
