import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.single_stock_diagnostic_renderer import render_single_stock_diagnostic_markdown


class SingleStockDiagnosticRendererTest(unittest.TestCase):
    def test_render_single_stock_diagnostic_markdown_outputs_four_layers(self):
        markdown = render_single_stock_diagnostic_markdown(
            {
                "target_date": "2026-04-22",
                "name": "军工一号",
                "code": "000001",
                "position_level": "三档（进攻档）",
                "final_action": "允许强势跟随",
                "mainline_name": "军工",
                "driver_type": "主升",
                "pulse_stage": "第一阶段",
                "acceptance_quality": "强",
                "pulse_action_bias": "主线优先",
                "energy_state": "修复",
                "step0_prediction_cn": "🟢 明朗",
                "system_role": "明日核心",
                "sector": "军工",
                "change_pct": 4.23,
                "pattern": "平台突破",
                "abnormal_follow_state": "承接",
                "risk_light": "🟢 绿灯",
                "risk_reason": "承接未坏",
                "permission_label": "执行权",
                "permission_reason": "主线核心且环境放行",
                "risk_level": "低风险",
                "risk_group": "重点候选组",
                "risk_reason_text": "量价匹配良好",
                "risk_penalty_count": 1,
                "repair_buffer_count": 2,
                "raw_risk_score": 4,
                "risk_score": 2,
                "tradability_status": "可交易",
                "tradability_reason": "量能和价格结构都正常",
                "quant_signal_type": "breakout",
                "quant_reason": "突破有效",
                "confirm_text": "12.34",
                "key_zone_display": "12.10-12.40",
                "execution_stop_display": "11.80",
                "hard_stop_display": "11.70",
                "price_note_text": "先看12.34是否站稳",
                "decision_stack": {"environment_score": 8, "mainline_score": 9, "memory_score": 6, "trigger_score": 7, "tradability_score": 8},
                "ev_stack_text": "7.5",
                "final_verdict": "允许执行",
                "final_reason": "环境、主线、可交易性同时放行",
                "risk_tomorrow_text": "若高开过多则放弃",
                "source_tags": ["watchlist", "abnormal_watch"],
            }
        )

        self.assertIn("# 2026-04-22 单票诊断 - 军工一号(000001)", markdown)
        self.assertIn("## 一、市场层", markdown)
        self.assertIn("- **环境档位**: 三档（进攻档）", markdown)
        self.assertIn("## 二、个股层", markdown)
        self.assertIn("- **执行权限**: 执行权", markdown)
        self.assertIn("## 三、执行层", markdown)
        self.assertIn("- **60分钟确认点**: 12.34", markdown)
        self.assertIn("## 四、结论", markdown)
        self.assertIn("- **命中来源**: watchlist / abnormal_watch", markdown)


if __name__ == "__main__":
    unittest.main()
