import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.context_sections_renderer import (
    render_ai_market_insight_section,
    render_mainline_discipline_section,
    render_supplementary_perspective_section,
)


class ContextSectionsRendererTest(unittest.TestCase):
    def test_render_mainline_discipline_section(self):
        lines = render_mainline_discipline_section("军工")
        rendered = "\n".join(lines)
        self.assertIn("#### 💡 核心交易哲学：看好A，干A！", rendered)
        self.assertIn("> **主线**: 军工", rendered)
        self.assertIn("认准'军工'，就在'军工'里找机会", rendered)

    def test_render_supplementary_perspective_section(self):
        lines = render_supplementary_perspective_section("第一行\n第二行")
        rendered = "\n".join(lines)
        self.assertIn("## 十三点五、补充视角（复盘参考）", rendered)
        self.assertIn("第一行", rendered)
        self.assertIn("第二行", rendered)

    def test_render_ai_market_insight_section(self):
        lines = render_ai_market_insight_section(
            {
                "market_trend": "强分歧修复",
                "zt_count": 42,
                "dt_count": 3,
                "energy_state": "修复",
                "flow_direction": "回流军工",
                "mainline_text": "军工",
                "risk_text": "高位抱团",
                "focus_text": "军工持续性，量能变化，板块轮动",
            }
        )
        rendered = "\n".join(lines)
        self.assertIn("## 十四、AI市场洞察总结", rendered)
        self.assertIn("- **核心特征**: 强分歧修复，涨停42只，跌停3只", rendered)
        self.assertIn("- **能量状态**: 修复 - 回流军工", rendered)
        self.assertIn("- **资金主线**: 军工", rendered)
        self.assertIn("- **风险点**: 高位抱团", rendered)


if __name__ == "__main__":
    unittest.main()
