import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.front_summary_renderer import render_front_digest, render_front_summary_sections, render_mvp_focus_summary


class FrontSummaryRendererTest(unittest.TestCase):
    def test_render_front_summary_sections_can_render_only_enabled_nodes(self):
        lines = render_front_summary_sections(
            {
                "front_digest": {
                    "headline": "先观察",
                    "state_text": "防守观察",
                    "mainline_label": "主线待确认",
                    "style_action_text": "先看量能",
                    "risk_parts": ["跌停3只"],
                    "can_open_text": "不开新仓",
                },
                "mvp_focus": {
                    "special_probe_text": "军工一号(000001)",
                    "front_follow_action_text": "只买军工一号，60分钟确认后执行",
                },
                "enabled_node_keys": ["mvp_focus"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🎯 明日MVP摘要", rendered)
        self.assertNotIn("### 🧭 前台摘要", rendered)

    def test_render_front_digest_outputs_full_contract_summary(self):
        lines = render_front_digest(
            {
                "headline": "只买军工一号，60分钟确认后执行",
                "state_text": "强分歧修复；环境放行",
                "mainline_label": "主攻线军工；趋势密度最强军工(3只)",
                "special_probe_text": "军工一号(000001)",
                "philosophy_constraint_text": "只做主线，不做边缘分支",
                "contract_logic_text": "先选边站队，再等确认",
                "alignment_pool_text": "月度站队池：军工；本周发酵方向：高端装备",
                "rotation_summary_text": "主攻线军工 / 次强线高端装备",
                "rotation_narrative_text": "军工仍是资金首选",
                "weak_to_strong_active": True,
                "weak_to_strong_summary_text": "军工一号的弱转强确认最完整",
                "style_action_text": "主线优先，等待唯一动作",
                "risk_parts": ["主线状态强", "跌停1只", "高位连板2只"],
                "can_open_text": "可以开仓，但只剩唯一动作",
                "stage_label": "主升试错段",
                "stage_action": "只做主线强者",
                "index_profit_relation": "指数震荡但赚钱效应修复",
                "execution_framework_text": "日线定环境，60分钟定买点，30分钟定止损",
                "compact": False,
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🧭 前台摘要", rendered)
        self.assertIn("- **先说结论**: 只买军工一号，60分钟确认后执行", rendered)
        self.assertIn("- **执行依据**: 先选边站队，再等确认", rendered)
        self.assertIn("- **弱转强先看谁**: 军工一号的弱转强确认最完整", rendered)
        self.assertIn("- **现在更像哪个阶段**: 主升试错段；只做主线强者", rendered)
        self.assertIn("- **怎么执行**: 日线定环境，60分钟定买点，30分钟定止损", rendered)
        self.assertNotIn("底层逻辑", rendered)

    def test_render_front_digest_uses_action_label_for_inactive_weak_to_strong(self):
        lines = render_front_digest(
            {
                "headline": "先观察",
                "state_text": "防守观察",
                "mainline_label": "军工",
                "weak_to_strong_active": False,
                "weak_to_strong_summary_text": "当前没有符合条件的弱转强对象",
                "style_action_text": "先看量能",
                "risk_parts": ["跌停3只"],
                "can_open_text": "不开新仓",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("- **弱转强先不做**: 当前没有符合条件的弱转强对象", rendered)
        self.assertNotIn("弱转强为什么先不做", rendered)

    def test_render_front_digest_compact_keeps_only_key_markers(self):
        lines = render_front_digest(
            {
                "headline": "先观察",
                "state_text": "防守观察",
                "mainline_label": "主线待确认",
                "special_probe_text": "军工观察",
                "style_action_text": "先看量能",
                "risk_parts": ["跌停3只"],
                "can_open_text": "不开新仓",
                "execution_framework_text": "日线定环境",
                "alignment_pool_text": "这行应该被折叠",
                "compact": True,
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🧭 前台摘要", rendered)
        self.assertIn("先说结论", rendered)
        self.assertIn("特殊标的先看谁", rendered)
        self.assertNotIn("方向站队池", rendered)

    def test_render_mvp_focus_summary_outputs_focus_sections(self):
        lines = render_mvp_focus_summary(
            {
                "special_probe_text": "军工一号(000001)",
                "rotation_summary_text": "主攻线军工 / 次强线高端装备",
                "rotation_narrative_text": "资金仍在军工内轮动",
                "gem_breathing_text": "军工转债(123001)[A层]；只先进观察池",
                "mainline_watch_preview": "军工一号(军工) / 军工二号(军工)",
                "crossline_watch_preview": "高端装备一号(高端装备)",
                "abnormal_preview": "军工一号(承接) / 军工二号(回封)",
                "memory_preview": "军工龙头(军工)",
                "core_preview": "军工一号(核心)",
                "cross_core_preview": "高端装备一号(观察)",
                "special_probe_summary_text": "军工一号是主线异常探针",
                "structure_layer_text": "只等唯一动作",
                "observation_cycle": "先给3~5日观察合同",
                "intervention_cycle": "60分钟确认后只做30%试错",
                "exit_cycle": "失守关键位就作废",
                "delete_preview": "军工弱票 / 军工后排",
                "buy_target_text": "军工一号(000001)，只等60分钟确认，不追盘中情绪顶点",
                "bridge_prep_label": "条件执行预备态",
                "bridge_prep_text": "军工一号，等待突破升级",
                "mainline_probe_text": "军工一号(000001)",
                "crossline_probe_text": "高端装备一号(000002)",
                "validation_probe_text": "军工二号(000003)",
                "front_follow_action_text": "只买军工一号，60分钟确认后执行",
                "compact": False,
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🎯 明日MVP摘要", rendered)
        self.assertIn("**特殊标的先看谁**: 军工一号(000001)", rendered)
        self.assertIn("**主线研究对象**: 军工一号(军工) / 军工二号(军工)", rendered)
        self.assertIn("**异常承接先看谁**: 军工一号(承接) / 军工二号(回封)", rendered)
        self.assertIn("**明天能不能开仓**: 只等唯一动作", rendered)
        self.assertIn("**明日唯一动作**: 只买军工一号，60分钟确认后执行", rendered)


if __name__ == "__main__":
    unittest.main()
