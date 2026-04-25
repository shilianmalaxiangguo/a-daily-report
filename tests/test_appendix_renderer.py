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

    def test_render_execution_appendix_outputs_empty_continuity_tables_as_recording_contract(self):
        lines = render_execution_appendix(
            {
                "data_status": {},
                "step_status": {},
                "target_date": "2026-04-24",
                "generated_at": "2026-04-25 08:30:00",
                "report_version": "v2.5.0",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录B：历史主线池", rendered)
        self.assertIn("| 暂无 | - | 今天开始记录 | 后续日报自动累计 |", rendered)
        self.assertIn("### 附录B：主线成交额占比完整历史", rendered)
        self.assertIn("### 附录C：当前个股观察监控池", rendered)
        self.assertIn("### 附录C：观察对象生命周期表", rendered)
        self.assertIn("| 暂无 | - | - | 0 | - | - | - | 今天开始记录 | 继续累计 |", rendered)

    def test_render_execution_appendix_places_execution_log_after_data_continuity_appendices(self):
        lines = render_execution_appendix(
            {
                "data_status": {"hot_rank": True},
                "step_status": {"collect_hot_rank": True},
                "appendix_b": {"historical_mainline_pool": [{"date": "2026-04-24", "mainline": "半导体"}]},
                "appendix_c": {"current_stock_monitoring_pool": [{"name": "富瀚微", "code": "300613"}]},
            }
        )

        rendered = "\n".join(lines)
        self.assertLess(rendered.index("### 附录B：历史主线池"), rendered.index("## 附录：数据获取与执行步骤清单"))
        self.assertLess(rendered.index("### 附录C：当前个股观察监控池"), rendered.index("## 附录：数据获取与执行步骤清单"))

    def test_render_execution_appendix_outputs_structure_mainline_evolution_table(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["mainline_continuity"],
                "appendix_b": {
                    "structure_mainline_records": [
                        {
                            "date_range": "2026-04-21 ~ 2026-04-24",
                            "pivot_level": "小中枢",
                            "pivot_range": "3992-4114",
                            "position": "中枢内",
                            "mainline": "半导体",
                            "mainline_degree": "小周期主线",
                            "evolution": "[半导体] 接替 [电力]",
                            "replacement": "接替前主线",
                            "interpretation": "[半导体] 在中枢内接替 [电力]，但还未进入攻击段",
                        }
                    ]
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录B：中枢对应主线记录", rendered)
        self.assertIn("| 时间段 | 中枢级别 | 中枢区间 | 所在位置 | 对应主线 | 主线程度 | 演化状态 | 接替关系 | 解读 |", rendered)
        self.assertIn("| 2026-04-21 ~ 2026-04-24 | 小中枢 | 3992-4114 | 中枢内 | 半导体 | 小周期主线 | [半导体] 接替 [电力] | 接替前主线 | [半导体] 在中枢内接替 [电力]，但还未进入攻击段 |", rendered)

    def test_render_execution_appendix_outputs_entry_cycle_stop_calibration_table(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["entry_cycle_calibration"],
                "entry_cycle_calibration": {
                    "cases": [
                        {
                            "name": "中嘉博创",
                            "code": "000889",
                            "case_type": "success",
                            "first_report_date": "2026-04-10",
                            "breakout_date": "2026-04-15",
                            "cycle_gap_trading_days": 3,
                            "max_drawdown_before_breakout_pct": -8.05,
                            "range_amplitude_pct": 13.12,
                            "fixed_5pct_stop_result": "would_false_kill",
                            "recommended_stop_mode": "structure_repair_band",
                            "interpretation": "中嘉博创说明固定-5%会误杀：先看收盘修复和后续再突破。",
                        },
                        {
                            "name": "甘肃能源",
                            "code": "000791",
                            "case_type": "counterexample",
                            "first_report_date": "2026-04-13",
                            "breakout_date": "",
                            "cycle_gap_trading_days": 5,
                            "max_drawdown_before_breakout_pct": -2.10,
                            "range_amplitude_pct": 6.40,
                            "fixed_5pct_stop_result": "would_not_warn",
                            "recommended_stop_mode": "reclaim_failure_exit",
                            "interpretation": "甘肃能源没有站稳关键区，应该按关键区失败降级。",
                        },
                        {
                            "name": "津药药业",
                            "code": "600488",
                            "case_type": "counterexample",
                            "first_report_date": "2026-04-03",
                            "breakout_date": "2026-04-07",
                            "cycle_gap_trading_days": 2,
                            "max_drawdown_before_breakout_pct": -7.22,
                            "range_amplitude_pct": 18.30,
                            "fixed_5pct_stop_result": "would_cut_loss",
                            "recommended_stop_mode": "a_kill_exit",
                            "interpretation": "津药药业应该按A杀出清，不当趋势持有。",
                        },
                    ]
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录C：介入周期止损校准", rendered)
        self.assertIn("中嘉博创(000889)", rendered)
        self.assertIn("固定-5%会误杀", rendered)
        self.assertIn("结构修复带", rendered)
        self.assertIn("甘肃能源(000791)", rendered)
        self.assertIn("关键区失败降级", rendered)
        self.assertIn("津药药业(600488)", rendered)
        self.assertIn("A杀出清", rendered)


if __name__ == "__main__":
    unittest.main()
