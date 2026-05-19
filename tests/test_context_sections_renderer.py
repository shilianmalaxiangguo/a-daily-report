import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from report.context_sections_renderer import (
    render_context_tail_sections,
    render_ai_market_insight_section,
    render_mainline_discipline_section,
    render_supplementary_perspective_section,
)


class ContextSectionsRendererTest(unittest.TestCase):
    def test_render_context_tail_sections_can_render_only_enabled_nodes(self):
        lines = render_context_tail_sections(
            {
                "mainline_name": "军工",
                "supplementary_perspective": "第一行\n第二行",
                "market_insight": {
                    "market_trend": "强分歧修复",
                    "zt_count": 42,
                    "dt_count": 3,
                    "energy_state": "修复",
                    "flow_direction": "回流军工",
                    "mainline_text": "军工",
                    "risk_text": "高位抱团",
                    "focus_text": "军工持续性，量能变化，板块轮动",
                },
                "enabled_node_keys": ["supplementary_perspective", "market_insight"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 十三点五、补充观察", rendered)
        self.assertIn("## 十四、市场快照", rendered)
        self.assertNotIn("#### 💡 主线执行纪律", rendered)

    def test_render_mainline_discipline_section(self):
        lines = render_mainline_discipline_section("军工")
        rendered = "\n".join(lines)
        self.assertIn("#### 💡 主线执行纪律", rendered)
        self.assertIn("> **主线**: 军工", rendered)
        self.assertIn("**只做什么，不做什么？**", rendered)
        self.assertIn("认准'军工'，就在'军工'里找机会", rendered)
        self.assertNotIn("为什么只看主线，不做B/C？", rendered)

    def test_render_supplementary_perspective_section(self):
        lines = render_supplementary_perspective_section("第一行\n第二行")
        rendered = "\n".join(lines)
        self.assertIn("## 十三点五、补充观察", rendered)
        self.assertIn("以下只做补充观察，不单独给执行资格。", rendered)
        self.assertNotIn(_m("执行", "权"), rendered)
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
        self.assertIn("## 十四、市场快照", rendered)
        self.assertIn("- **核心特征**: 强分歧修复，涨停42只，跌停3只", rendered)
        self.assertIn("- **能量状态**: 修复 - 回流军工", rendered)
        self.assertIn("- **资金主线**: 军工", rendered)
        self.assertIn("- **风险点**: 高位抱团", rendered)

    def test_render_ai_market_insight_section_uses_no_mainline_when_attack_evidence_is_chaotic(self):
        lines = render_ai_market_insight_section(
            {
                "market_trend": "大幅下跌",
                "zt_count": 55,
                "dt_count": 17,
                "energy_state": "观察",
                "flow_direction": "轮动",
                "mainline_text": "半导体",
                "risk_text": "元件、半导体",
                "focus_text": "半导体持续性，量能变化，板块轮动",
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("- **资金主线**: 暂无确认主攻线", rendered)
        self.assertIn("- **关注重点**: 多方向局部活跃但资金未明显胜出", rendered)
        self.assertNotIn("- **资金主线**: 半导体", rendered)


if __name__ == "__main__":
    unittest.main()
