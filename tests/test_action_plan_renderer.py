import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.action_plan_renderer import render_action_plan_result, render_action_plan_section
from report.action_plan_nodes import build_action_plan_candidate_quality_node
from selection.candidate_quality_contracts import (
    build_daily_quality_decision_panel,
    evaluate_candidate_quality_sample_contract,
)


class ActionPlanRendererTest(unittest.TestCase):
    def test_render_action_plan_section_with_watch_only_anchor(self):
        lines = render_action_plan_section(
            {
                "action_rows": [
                    {
                        "action": "👀 明天先盯哪只",
                        "name": "军工观察",
                        "code": "000002",
                        "trigger": "先看预演参与窗口，再看是否走成明天唯一能买的那只",
                        "risk_window": "12.30-12.80 / 3~5日",
                    }
                ],
                "position_section_lines": [
                    "- **市场环境档位**: 二档（防守档）",
                    "- **明日裁决**: 🟡 中性",
                    "- **怎么执行**: 日线定环境，60分钟定买点，30分钟定止损",
                    "- **现在到底是什么状态**: 防守观察",
                    "- **明天仓位放多少**: 0%或50%（持有但不新增）",
                ],
                "pre_market_lines": [
                    "- **跨线重点观察谁**: 军工观察(000002) - 先看预演参与窗口，再看关键区间",
                    "- 查看隔夜消息、外围市场、期货走势",
                ],
                "opening_lines": [
                    "- 观察涨跌比、昨日涨停溢价率",
                    "- 竞价表态与开盘承接同时成立才按预演窗口参与，不成立回到0%",
                ],
                "first_hour_lines": [
                    "- 当前条件不允许新开仓，本时段只确认环境是否继续支持持仓/观察",
                ],
                "intraday_lines": [
                    "- 以观察和处理持仓为主，不做新开仓",
                ],
                "closing_lines": [
                    "- 若你有旧仓，确认30分钟结构止损线是否需要上移",
                ],
                "alert_rows": [
                    {
                        "name": "军工观察",
                        "code": "000002",
                        "deviation_days": 2,
                        "trigger_info": "+3.00%",
                        "actual_change_str": "-",
                        "trigger_status": "待观察",
                    }
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("#### 明日操作计划", rendered)
        self.assertIn("> **先看结论**：明天只执行唯一动作，或者只观察。", rendered)
        self.assertIn("> **怎么执行**：按盘前、09:30-09:35、09:50-10:10、盘中观察、14:30-14:55顺序，不临场改单。", rendered)
        self.assertIn("- **怎么执行**: 日线定环境，09:50-10:10窗口，按失效价和单笔-5%底线处理风险", rendered)
        self.assertIn("- 若你有旧仓，确认风险线是否需要上移", rendered)
        self.assertIn("| 👀 明天先盯哪只 | 军工观察 | 000002 |", rendered)
        self.assertIn("**明天仓位怎么放**:", rendered)
        self.assertIn("**盘前准备（08:30-09:15）**:", rendered)
        self.assertIn("**竞价表态与开盘买卖窗口（09:20-09:35，买卖只在09:30-09:35）**:", rendered)
        self.assertIn("**14:30-14:55买卖窗口（14:30-14:55）**:", rendered)
        self.assertIn("**⚠️ 异动预警**:", rendered)
        self.assertIn("| 军工观察(000002) | 2天 | +3.00% | - | 待观察 |", rendered)
        self.assertNotIn("为什么这样排", rendered)

    def test_render_action_plan_section_can_render_only_enabled_nodes(self):
        lines = render_action_plan_section(
            {
                "action_rows": [
                    {
                        "action": "🔥 唯一买入",
                        "name": "军工一号",
                        "code": "000001",
                        "trigger": "明日09:50-10:10站上10.50",
                        "risk_window": "预估9.50 / 1-3天",
                    }
                ],
                "position_section_lines": [
                    "- **市场环境档位**: 三档（进攻档）",
                ],
                "pre_market_lines": [
                    "- 设价格预警",
                ],
                "enabled_node_keys": ["overview", "action_table", "positioning"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("#### 明日操作计划", rendered)
        self.assertIn("**最终动作表**（只展示真正具备参与资格的对象）:", rendered)
        self.assertNotIn("只展示真正可执行对象", rendered)
        self.assertIn("**明天仓位怎么放**:", rendered)
        self.assertNotIn("**明日执行时间表**:", rendered)
        self.assertNotIn("**⚠️ 异动预警**:", rendered)

    def test_render_action_plan_section_can_enable_candidate_quality_node(self):
        panel = build_daily_quality_decision_panel(
            market_emotion_label="分歧轮动",
            account_attention_load="高",
            holding_priority_action="先处理汇源通信风险仓",
            daily_new_entry_limit=0,
            backup_candidate={"name": "晶方科技", "code": "603005"},
        )
        candidate_contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "汇源通信",
                    "code": "000586",
                    "selection_quality": "低",
                    "entry_cost_state": "低成本",
                    "risk_flags": ["风险信息缺失"],
                    "cost_flags": ["靠近VWAP"],
                    "current_position_shares": 500,
                    "sellable_shares": 100,
                    "locked_shares": 400,
                }
            )
        ]

        disabled_lines = render_action_plan_section(
            {
                "candidate_quality_panel": panel,
                "candidate_quality_contracts": candidate_contracts,
                "enabled_node_keys": ["overview"],
            }
        )
        enabled_lines = render_action_plan_section(
            {
                "candidate_quality_panel": panel,
                "candidate_quality_contracts": candidate_contracts,
                "enabled_node_keys": ["overview", "candidate_quality"],
            }
        )

        self.assertNotIn("候选质量与动作分层", "\n".join(disabled_lines))
        rendered = "\n".join(enabled_lines)
        self.assertIn("##### 候选质量与动作分层", rendered)
        self.assertNotIn("\n## 候选质量与动作分层", rendered)
        self.assertIn("| 候选 | 账户状态 | 计划仓位档 | 实际仓位 | 当前持仓 | 可卖数量 | 选股质量 | 买点质量 | 动作上限 | 新开仓动作 |", rendered)
        self.assertNotIn("| 不可卖数量 |", rendered)
        self.assertIn("| 市场情绪状态 | 分歧轮动 |", rendered)
        self.assertIn("| 汇源通信(000586) | 实际可买 |  |  | 500 | 100 | 低 | 看似便宜 | 不参与 |", rendered)
        self.assertIn("- 持仓动作：已有仓按失效线处理，可卖100，不可卖400", rendered)
        self.assertIn("| 汇源通信(000586) | 实际可买 |  |  | 500 | 100 | 低 | 看似便宜 | 不参与 |", rendered)

    def test_candidate_quality_node_can_materialize_from_daily_context_samples(self):
        lines = render_action_plan_section(
            {
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "退潮修复",
                    "account_attention_load": "中",
                    "holding_priority_action": "先处理旧仓，再看新增",
                    "daily_new_entry_limit": 1,
                    "primary_buy_candidate": {"name": "晶方科技", "code": "603005"},
                    "backup_candidate": {"name": "上峰水泥", "code": "000672"},
                    "forbidden_actions": ["计划外追高"],
                    "ignored_noise_items": ["外盘大涨但A股未确认"],
                },
                "candidate_quality_samples": [
                    {
                        "name": "晶方科技",
                        "code": "603005",
                        "selection_quality": "高",
                        "entry_cost_state": "高成本",
                        "is_core": True,
                        "cost_flags": ["远离MA/VWAP"],
                    },
                    {
                        "name": "上峰水泥",
                        "code": "000672",
                        "selection_quality": "中",
                        "entry_cost_state": "确认中",
                        "current_position_shares": 400,
                        "sellable_shares": 300,
                        "locked_shares": 100,
                        "trend_context": "冲高后回踩MA/VWAP",
                    },
                ],
                "enabled_node_keys": ["overview", "candidate_quality"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("##### 候选质量与动作分层", rendered)
        self.assertIn("| 今日新增上限 | 1 |", rendered)
        self.assertIn("| 主买对象 | 晶方科技(603005) |", rendered)
        self.assertIn("| 补位对象 | 上峰水泥(000672) |", rendered)
        self.assertIn("| 晶方科技(603005) | 实际可买 |  |  | 0 | 0 | 高 | 不舒服 | 核心观察 |", rendered)
        self.assertIn("- 成本项：远离MA/VWAP", rendered)
        self.assertIn("| 上峰水泥(000672) | 实际可买 |  |  | 400 | 300 | 中 | 等确认 | 修复观察 |", rendered)
        self.assertIn("- 持仓动作：已有仓按失效线处理，可卖300，不可卖100", rendered)
        self.assertIn("| 上峰水泥(000672) | 实际可买 |  |  | 400 | 300 | 中 | 等确认 | 修复观察 |", rendered)

    def test_candidate_quality_node_uses_normal_heading_when_rendered_without_overview(self):
        lines = render_action_plan_section(
            {
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "退潮修复",
                    "daily_new_entry_limit": 0,
                },
                "candidate_quality_samples": [
                    {
                        "name": "晶方科技",
                        "code": "603005",
                        "selection_quality": "高",
                        "entry_cost_state": "确认中",
                        "quality_role": "主买对象",
                    }
                ],
                "enabled_node_keys": ["candidate_quality"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 候选质量与动作分层", rendered)
        self.assertNotIn("##### 候选质量与动作分层", rendered)

    def test_candidate_quality_node_can_render_and_export_candidate_traces(self):
        lines = build_action_plan_candidate_quality_node(
            {
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "主线活跃",
                    "daily_new_entry_limit": 1,
                },
                "candidate_quality_samples": [
                    {
                        "name": "华天科技",
                        "code": "002185",
                        "tier": "T0",
                        "source_pools": ["主线核心候选"],
                        "mainline": "半导体",
                        "sector": "半导体",
                        "market_fit": "部分满足",
                        "mainline_fit": "满足",
                        "stock_structure_fit": "部分满足",
                        "latest_price": 13.2,
                        "available_cash": 10000,
                        "final_action": "09:50-10:10确认，不满足继续不参与",
                    }
                ],
                "candidate_trace_eliminated_items": [
                    {"name": "大众公用", "reason": "主线不匹配"},
                ],
                "render_candidate_trace_tables": True,
                "enabled_node_keys": ["candidate_quality"],
            }
        )

        rendered = "\n".join(lines["lines"])
        self.assertIn("候选选股轨迹", rendered)
        self.assertIn("未进入分层原因统计", rendered)
        self.assertEqual(lines["exports"]["candidate_traces"][0]["stock_code"], "002185")
        self.assertEqual(lines["exports"]["candidate_trace_eliminated_summary"][0]["reason"], "主线不匹配")

    def test_candidate_quality_node_prefers_richer_contract_trace_over_incomplete_existing_trace(self):
        lines = build_action_plan_candidate_quality_node(
            {
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "主线活跃",
                    "daily_new_entry_limit": 1,
                },
                "candidate_quality_samples": [
                    {
                        "name": "华电能源",
                        "code": "600726",
                        "tier": "T0",
                        "source_pools": ["观察池"],
                        "mainline": "电力",
                        "sector": "电力",
                        "market_fit": "部分满足",
                        "mainline_fit": "满足",
                        "stock_structure_fit": "部分满足",
                        "trigger_condition": "固定交易窗口内承接确认",
                        "failure_condition": "板块承接转弱",
                    }
                ],
                "candidate_traces": [
                    {
                        "stock_code": "600726",
                        "stock_name": "华电能源",
                        "sector": "电力",
                        "final_action": "关键数据不完整，停止生成动作",
                    }
                ],
                "render_candidate_trace_tables": True,
                "enabled_node_keys": ["candidate_quality"],
            }
        )

        trace = lines["exports"]["candidate_traces"][0]
        self.assertEqual(trace["stock_code"], "600726")
        self.assertEqual(trace["tier"], "T0")
        self.assertEqual(trace["mainline"], "电力")
        self.assertEqual(trace["trigger_condition"], "固定交易窗口内承接确认")

    def test_render_action_plan_result_exposes_candidate_trace_exports(self):
        context = {
            "candidate_quality_panel_fields": {
                "market_emotion_label": "主线活跃",
                "daily_new_entry_limit": 1,
            },
            "candidate_quality_samples": [
                {
                    "name": "华天科技",
                    "code": "002185",
                    "tier": "T0",
                    "source_pools": ["主线核心候选"],
                    "mainline": "半导体",
                    "sector": "半导体",
                    "market_fit": "部分满足",
                    "mainline_fit": "满足",
                    "stock_structure_fit": "部分满足",
                    "latest_price": 13.2,
                    "available_cash": 10000,
                    "final_action": "09:50-10:10确认，不满足继续不参与",
                }
            ],
            "candidate_trace_eliminated_items": [
                {"name": "大众公用", "reason": "主线不匹配"},
            ],
            "render_candidate_trace_tables": True,
            "enabled_node_keys": ["overview", "candidate_quality"],
        }

        result = render_action_plan_result(context)
        legacy_lines = render_action_plan_section(context)

        rendered = "\n".join(result["lines"])
        self.assertEqual(legacy_lines, result["lines"])
        self.assertIn("候选选股轨迹", rendered)
        self.assertEqual(result["context"]["candidate_traces"][0]["stock_code"], "002185")
        self.assertEqual(result["context"]["candidate_trace_eliminated_summary"][0]["reason"], "主线不匹配")


if __name__ == "__main__":
    unittest.main()
