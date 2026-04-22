import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.exchange_monitor_builder import build_exchange_monitor_sections_contract


class ExchangeMonitorBuilderTest(unittest.TestCase):
    def test_build_exchange_monitor_sections_contract_renders_today_and_nextday_tables(self):
        result = build_exchange_monitor_sections_contract(
            data={
                "exchange_monitor_today": [
                    {
                        "name": "军工一号",
                        "code": "000001",
                        "deviation_days": 12,
                        "deviation_pct": 18.5,
                        "trigger_pct": 5.2,
                        "actual_change_pct": 6.1,
                        "is_triggered": True,
                    }
                ],
                "exchange_monitor_nextday": [
                    {
                        "name": "机器人一号",
                        "code": "000002",
                        "deviation_days": 8,
                        "deviation_pct": 12.3,
                        "trigger_pct": 4.8,
                    }
                ],
            }
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 十二、异动监控", rendered)
        self.assertIn("| 军工一号 | 000001 | 12天 | 18.50% | +5.20% | +6.10% | ✅ 已触发 | 🟡 中风险 |", rendered)
        self.assertIn("| 机器人一号 | 000002 | 8天 | 12.30% | 涨幅达+4.80%触发 | 🟢 低风险 |", rendered)
        self.assertTrue(any(log["step"] == "render.exchange_monitor_sections" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
