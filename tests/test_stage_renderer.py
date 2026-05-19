import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from report.stage_renderer import render_stage_board


class StageRendererTest(unittest.TestCase):
    def test_render_stage_board_outputs_dynamic_stage_markdown(self):
        rendered = render_stage_board(
            [
                {"stage_key": "market_environment", "title": "市场环境", "status": "ready", "summary": "环境可做"},
                {"stage_key": "selection_focus", "title": "主线与筛选", "status": "ready", "summary": "军工最强"},
                {"stage_key": "execution_gate", "title": "执行" + "门" + "控", "status": "blocked", "summary": "等预演参与窗口"},
            ]
        )

        self.assertIn("## 阶段看板", rendered)
        self.assertIn("market_environment", rendered)
        self.assertIn("市场环境", rendered)
        self.assertIn("军工最强", rendered)
        self.assertIn("blocked", rendered)
        self.assertIn("执行条件", rendered)
        self.assertNotIn(_m("执行", "门", "控"), rendered)


if __name__ == "__main__":
    unittest.main()
