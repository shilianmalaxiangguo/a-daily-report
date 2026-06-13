import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_report_markdown_hooks as hooks
from knowledge.trading_philosophy import build_trading_philosophy_snapshot


class TradingPhilosophyModuleTest(unittest.TestCase):
    def test_snapshot_exposes_latest_trading_chain_and_rules(self):
        snapshot = build_trading_philosophy_snapshot(target_date="2026-04-22")
        rendered = "\n".join(snapshot["trading_philosophy_lines"])

        self.assertEqual(snapshot["source"], "skillhub")
        self.assertIn("结构中枢周期", snapshot["main_derivation_chain"])
        self.assertIn("观察资格/买入资格", snapshot["main_derivation_chain"])
        self.assertIn("环境条件满足", snapshot["decision_gate_chain"])
        self.assertIn("固定交易窗口条件", snapshot["decision_gate_chain"])
        self.assertIn("失效价和单笔-5%底线", snapshot["decision_gate_chain"])
        self.assertIn("普通结构只看09:50-10:10窗口", rendered)
        self.assertIn("不为新故事切掉旧事实", rendered)
        self.assertIn("10cm", rendered)
        self.assertIn("20cm", rendered)

    def test_report_preamble_reuses_trading_philosophy_sections(self):
        lines = hooks.use_report_preamble("2026-04-22", compact=False)
        rendered = "\n".join(lines)

        self.assertIn("# 2026-04-22 A股日报", rendered)
        self.assertNotIn("交易理念底线", rendered)
        self.assertNotIn("策略定位与能力边界", rendered)
        self.assertNotIn("实验重放模式", rendered)
        self.assertNotIn("真实持仓", rendered)


if __name__ == "__main__":
    unittest.main()
