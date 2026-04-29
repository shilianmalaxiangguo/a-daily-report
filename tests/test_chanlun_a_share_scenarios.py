import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import scenario_runner


class ChanlunAShareScenariosTest(unittest.TestCase):
    def test_builtin_scenarios_cover_required_first_batch(self):
        scenarios = scenario_runner.build_builtin_scenarios()
        scenario_ids = {item["scenario_id"] for item in scenarios}

        self.assertIn("S01_index_250d_platform", scenario_ids)
        self.assertIn("S05_60m_enough_15m_insufficient", scenario_ids)
        self.assertIn("S07_limit_up_sequence", scenario_ids)
        self.assertIn("S12_third_buy_candidate", scenario_ids)
        self.assertGreaterEqual(len(scenarios), 11)

    def test_run_s01_keeps_practical_platform_without_minute_requirement(self):
        scenario = scenario_runner.get_builtin_scenario("S01_index_250d_platform")

        result = scenario_runner.run_scenario(scenario)

        self.assertEqual(result["scenario_id"], "S01_index_250d_platform")
        self.assertEqual(result["expected_behavior"]["structure_state"], "daily_practical_platform")
        self.assertEqual(result["generated"]["minute_confirmation_status"], "not_requested")
        self.assertEqual(result["observation"]["mismatch_type"], "none")

    def test_run_s05_marks_15m_local_only(self):
        scenario = scenario_runner.get_builtin_scenario("S05_60m_enough_15m_insufficient")

        result = scenario_runner.run_scenario(scenario)

        self.assertEqual(result["generated"]["confirmation_primary"], "60m")
        self.assertEqual(result["generated"]["minute_15m_capability_status"], "local_confirmation_only")
        self.assertFalse(result["generated"]["minute_15m_supports_250_day_base"])

    def test_write_artifacts_creates_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            written = scenario_runner.write_builtin_artifacts(
                fixture_dir=root / "fixtures",
                report_dir=root / "reports",
            )

            self.assertGreaterEqual(len(written["fixtures"]), 11)
            self.assertGreaterEqual(len(written["reports"]), 11)
            sample_fixture = root / "fixtures" / "S01_index_250d_platform.json"
            sample_report = root / "reports" / "S01_index_250d_platform.md"
            self.assertTrue(sample_fixture.exists())
            self.assertTrue(sample_report.exists())
            payload = json.loads(sample_fixture.read_text(encoding="utf-8"))
            self.assertEqual(payload["scenario_id"], "S01_index_250d_platform")
            self.assertIn("结论：通过", sample_report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
