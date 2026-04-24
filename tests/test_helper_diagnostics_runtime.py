import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnostics.helper_diagnostics_runtime import (
    build_helper_diagnostics,
    clear_helper_logs,
    drain_helper_logs,
    record_helper_log,
    render_helper_diagnostics_lines,
)


class HelperDiagnosticsRuntimeTest(unittest.TestCase):
    def tearDown(self):
        clear_helper_logs()

    def test_record_and_drain_helper_logs(self):
        record_helper_log(
            "domains.market_activity.support",
            "helper.stock_sector.eastmoney",
            "error",
            "Eastmoney行业接口失败",
            provider="eastmoney.company_survey",
            target_keys=["sector"],
            error="timeout",
        )

        logs = drain_helper_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["step"], "helper.stock_sector.eastmoney")
        self.assertEqual(logs[0]["details"]["provider"], "eastmoney.company_survey")
        self.assertEqual(drain_helper_logs(), [])

    def test_build_and_render_helper_diagnostics(self):
        diagnostics = build_helper_diagnostics(
            [
                {
                    "module": "domains.market_activity.support",
                    "step": "helper.stock_sector.eastmoney",
                    "status": "error",
                    "message": "Eastmoney行业接口失败",
                    "details": {
                        "provider": "eastmoney.company_survey",
                        "target_keys": ["sector"],
                        "error": "ConnectTimeout",
                    },
                }
            ]
        )

        self.assertEqual(diagnostics["summary"]["helper_log_count"], 1)
        self.assertEqual(diagnostics["summary"]["error_count"], 1)
        rendered = "\n".join(render_helper_diagnostics_lines(diagnostics))
        self.assertIn("辅助接口体检摘要", rendered)
        self.assertIn("eastmoney.company_survey", rendered)
        self.assertIn("ConnectTimeout", rendered)


if __name__ == "__main__":
    unittest.main()
