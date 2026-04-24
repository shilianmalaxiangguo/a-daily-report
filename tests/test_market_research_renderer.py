import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_research_renderer import (
    render_gem_breathing_pool_section,
    render_gem_breathing_step2_section,
    render_market_research_snapshot_section,
    render_step0_follow_section,
)


class MarketResearchRendererTest(unittest.TestCase):
    def test_render_market_research_snapshot_section_can_render_only_enabled_nodes(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_focus", "state_summary"],
                "benchmark_change": 0.56,
                "turnover": 12834,
                "observation": {
                    "zt_count": 45,
                    "dt_count": 3,
                    "rise_fall_ratio_text": "1.42",
                    "leader_memory_count": 3,
                    "trusted_tracking_count": 2,
                },
                "competition_result": "主攻线 军工",
                "competition_evidence": "趋势密度和异常承接都在军工",
                "state_energy": "修复",
                "state_reason": "强分歧修复继续",
                "state_flow_direction": "资金回流军工",
                "dialectical_decision": {
                    "stage_label": "主升试错段",
                    "stage_reason": "还没到普涨乱做",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("| 主线焦点 | 主攻线 军工 | 趋势密度和异常承接都在军工 |", rendered)
        self.assertIn("- **统一状态判断**: 修复；强分歧修复继续；资金回流军工", rendered)
        self.assertNotIn("| 盘面风险偏好 |", rendered)
        self.assertNotIn("### 🧠 辩证决策补充", rendered)

    def test_render_market_research_snapshot_section_full_mode(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "benchmark_change": 0.56,
                "turnover": 12834,
                "observation": {
                    "zt_count": 45,
                    "dt_count": 3,
                    "rise_fall_ratio_text": "1.42",
                    "leader_memory_count": 3,
                    "trusted_tracking_count": 2,
                    "densest_sector": "军工",
                    "densest_sector_trend_count": 5,
                },
                "competition_result": "主攻线 军工",
                "competition_evidence": "趋势密度和异常承接都在军工",
                "rotation_label": "主线轮动",
                "rotation_summary_text": "军工内部轮动扩散",
                "rotation_action": "优先主线内切换",
                "narrative_label": "叙事强化",
                "narrative_reason": "事件催化仍在",
                "narrative_action": "继续盯军工",
                "style_label": "趋势主导",
                "style_reason": "主线更强，边缘方向降级",
                "style_evidence_text": "军工趋势股密度最高",
                "abnormal_projection_label": "异常承接偏强",
                "abnormal_projection_reason": "承接样本明显多于失败样本",
                "follow_verdict_label": "允许跟随",
                "follow_verdict_reason": "环境未破坏",
                "state_energy": "修复",
                "state_reason": "强分歧修复继续",
                "state_flow_direction": "资金回流军工",
                "dialectical_decision": {
                    "stage_label": "主升试错段",
                    "stage_reason": "还没到普涨乱做",
                    "index_profit_relation": "指数偏弱但赚钱效应修复",
                    "index_profit_reason": "主线承接好于指数",
                    "focus_label": "主线集中",
                    "focus_action": "只做军工主线",
                    "candidate_focus": "军工核心与承接对象",
                    "candidate_action": "先盯唯一动作",
                    "falsification_conditions": ["军工高位大面积转弱"],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("| 盘面风险偏好 | 热点/趋势/异常 | 上证+0.56%", rendered)
        self.assertIn("| 主线焦点 | 主攻线 军工 | 趋势密度和异常承接都在军工 |", rendered)
        self.assertIn("### 🧠 辩证决策补充", rendered)
        self.assertIn("什么情况下先不认这轮修复", rendered)

    def test_render_step0_follow_section_compact(self):
        lines = render_step0_follow_section(
            {
                "compact": True,
                "step0_prediction_cn": "🟡 中性",
                "step0_reason": "环境未坏，但还需确认",
                "step0_action": "前30分钟只确认环境",
                "zt_count": 45,
                "dt_count": 3,
                "observation_summary": "风险偏好回暖",
                "densest_sector": "军工",
                "densest_sector_trend_count": 5,
                "resilient_abnormal_count": 4,
                "failed_abnormal_count": 1,
                "abnormal_projection_label": "异常承接偏强",
                "state_energy": "修复",
                "state_reason": "强分歧修复继续",
            }
        )
        rendered = "\n".join(lines)
        self.assertIn("**明日裁决**: 🟡 中性", rendered)
        self.assertIn("**异常承接**: 4强 / 1弱；异常承接偏强", rendered)

    def test_render_step0_follow_section_can_render_only_enabled_nodes(self):
        lines = render_step0_follow_section(
            {
                "compact": False,
                "enabled_node_keys": ["verdict", "abnormal_projection", "conclusion"],
                "step0_prediction_cn": "🟡 中性",
                "step0_reason": "环境未坏，但还需确认",
                "step0_action": "前30分钟只确认环境",
                "zt_count": 45,
                "dt_count": 3,
                "observation_summary": "风险偏好回暖",
                "style_label": "趋势主导",
                "style_reason": "主线更强，边缘方向降级",
                "densest_sector": "军工",
                "densest_sector_trend_count": 5,
                "resilient_abnormal_count": 4,
                "failed_abnormal_count": 1,
                "abnormal_projection_label": "异常承接偏强",
                "state_energy": "修复",
                "state_reason": "强分歧修复继续",
            }
        )
        rendered = "\n".join(lines)
        self.assertIn("**明日裁决**: 🟡 中性", rendered)
        self.assertIn("| 异常承接证据 | 4强 / 1弱 | 异常承接偏强 |", rendered)
        self.assertIn("> **Step 0 结论**: 环境未坏，但还需确认", rendered)
        self.assertNotIn("| 盘面风险偏好 |", rendered)
        self.assertNotIn("> **⚠️ 重要提醒**", rendered)

    def test_render_gem_breathing_sections(self):
        step2_lines = render_gem_breathing_step2_section(
            {
                "display_mvp_mode": False,
                "gem_observation_stocks": [
                    {"name": "军工转债", "code": "123001", "sector": "军工", "tier": "A层", "abnormal_summary": "均线粘合", "tomorrow_strength": 82}
                ],
                "filtered_out_gem_candidates": [],
            }
        )
        pool_lines = render_gem_breathing_pool_section(
            {
                "gem_observation_stocks": [
                    {"name": "军工转债", "code": "123001", "tier": "A层", "note": "蛇形走位", "watch_anchor_note": "先看右侧确认"}
                ],
                "filtered_out_gem_candidates": [],
            }
        )
        self.assertIn("主线侧翼弹性层", "\n".join(step2_lines))
        self.assertIn("#### Step 3.5 - 创业板20cm预启动观察池", "\n".join(pool_lines))
        self.assertIn("> **先看结论**：创业板20cm样本只保留观察权，不单列成独立战场。", "\n".join(pool_lines))
        self.assertIn("> **只看什么**：均线粘合、蛇形走位和右侧确认。", "\n".join(pool_lines))
        self.assertNotIn("核心问题", "\n".join(pool_lines))
        self.assertIn("军工转债", "\n".join(pool_lines))


if __name__ == "__main__":
    unittest.main()
