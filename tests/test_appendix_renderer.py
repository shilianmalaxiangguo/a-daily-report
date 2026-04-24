import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.appendix_renderer import render_execution_appendix


class AppendixRendererTest(unittest.TestCase):
    def test_render_execution_appendix_can_render_only_enabled_nodes(self):
        lines = render_execution_appendix(
            {
                "data_status": {"hot_rank": True},
                "step_status": {"collect_hot_rank": True},
                "normalized_timer_steps": [("collect_hot_rank", 1.20, 1.20)],
                "total_time": 1.20,
                "target_date": "2026-04-22",
                "generated_at": "2026-04-22 08:30:00",
                "report_version": "v2.5.0",
                "enabled_node_keys": ["header", "timer_stats"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 附录：数据获取与执行步骤清单", rendered)
        self.assertIn("### 执行时间统计", rendered)
        self.assertNotIn("### 一、数据获取清单", rendered)
        self.assertNotIn("### 二、执行步骤清单", rendered)

    def test_render_execution_appendix_outputs_status_and_timer_tables(self):
        lines = render_execution_appendix(
            {
                "data_status": {
                    "hot_rank": True,
                    "sector_rank": False,
                },
                "step_status": {
                    "collect_hot_rank": True,
                    "build_report": False,
                },
                "normalized_timer_steps": [
                    ("collect_hot_rank", 1.20, 1.20),
                    ("build_report", 2.03, 3.23),
                ],
                "total_time": 3.23,
                "target_date": "2026-04-22",
                "generated_at": "2026-04-22 08:30:00",
                "report_version": "v2.5.0",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 附录：数据获取与执行步骤清单", rendered)
        self.assertIn("| hot_rank | ✅ 成功 | 数据正常 |", rendered)
        self.assertIn("| sector_rank | ❌ 失败 | 数据缺失或获取失败 |", rendered)
        self.assertIn("| collect_hot_rank | ✅ 已执行 | 正常完成 |", rendered)
        self.assertIn("| build_report | ❌ 跳过/失败 | 未执行或失败 |", rendered)
        self.assertIn("| collect_hot_rank | 1.20s | 1.20s |", rendered)
        self.assertIn("**报告版本**: v2.5.0", rendered)
        self.assertIn("**数据日期**: 2026-04-22", rendered)


if __name__ == "__main__":
    unittest.main()
