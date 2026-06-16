import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.execution_chain_overview_nodes import render_execution_chain_overview_section


class ExecutionChainOverviewNodesTest(unittest.TestCase):
    def test_render_execution_chain_overview_section_can_render_only_enabled_nodes(self):
        lines = render_execution_chain_overview_section(
            {
                "csci_change": 1.23,
                "csi1000_change": 1.56,
                "market_trend": "强分歧修复",
                "primary_mainline": "军工",
                "enabled_node_keys": ["header", "market_summary"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 十三、统一执行链（狙击手视角）", rendered)
        self.assertIn("### 总-市场整体判断", rendered)
        self.assertIn("- **基准指数**: 中证全指涨跌幅+1.23%，中证1000涨跌幅+1.56%", rendered)
        self.assertNotIn("### 分-六步决策路径", rendered)

    def test_render_execution_chain_overview_section_omits_missing_csi500_change(self):
        lines = render_execution_chain_overview_section(
            {
                "csci_change": 1.23,
                "csi500_change": None,
                "csi1000_change": 1.56,
                "market_trend": "强分歧修复",
                "primary_mainline": "军工",
                "enabled_node_keys": ["header", "market_summary"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("- **基准指数**: 中证全指涨跌幅+1.23%，中证1000涨跌幅+1.56%", rendered)
        self.assertNotIn("中证500涨跌幅+0.00%", rendered)

    def test_render_execution_chain_overview_section_does_not_call_primary_mainline_when_attack_evidence_is_chaotic(self):
        lines = render_execution_chain_overview_section(
            {
                "csci_change": -1.23,
                "market_trend": "大幅下跌",
                "primary_mainline": "半导体",
                "enabled_node_keys": ["header", "market_summary"],
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
        self.assertIn("- **市场特征**: 大幅下跌，多方向局部活跃但资金未明显胜出", rendered)
        self.assertNotIn("主攻线半导体领涨", rendered)

    def test_render_execution_chain_overview_section_does_not_call_countertrend_attack_leading(self):
        lines = render_execution_chain_overview_section(
            {
                "csci_change": -2.40,
                "market_trend": "大幅下跌",
                "primary_mainline": "半导体",
                "enabled_node_keys": ["header", "market_summary"],
                "mainline_turnover_summary": {
                    "share_trend_label": "逆势试攻",
                    "conclusion": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("大幅下跌，放量杀跌里只有人形机器人局部逆势活跃，先防踩踏", rendered)
        self.assertNotIn("主攻线半导体领涨", rendered)
        self.assertNotIn("主攻线人形机器人领涨", rendered)

    def test_render_execution_chain_overview_section_does_not_call_stale_switch_leading_on_broad_selloff(self):
        lines = render_execution_chain_overview_section(
            {
                "csci_change": -2.40,
                "market_trend": "大幅下跌",
                "primary_mainline": "半导体",
                "enabled_node_keys": ["header", "market_summary"],
                "mainline_turnover_summary": {
                    "share_trend_label": "切换",
                    "current_mainline": "人形机器人",
                    "conclusion": "主线切换为人形机器人，旧主线半导体退出中心",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("大幅下跌，放量杀跌里只有人形机器人局部逆势活跃，先防踩踏", rendered)
        self.assertNotIn("主攻线半导体领涨", rendered)
        self.assertNotIn("主攻线人形机器人领涨", rendered)

    def test_render_execution_chain_overview_section_uses_adopted_tag_label(self):
        lines = render_execution_chain_overview_section(
            {
                "csci_change": 1.74,
                "market_trend": "小幅上涨",
                "primary_mainline": "元件",
                "enabled_node_keys": ["header", "market_summary"],
                "realtime_tag_evidence_snapshot": {
                    "groups": [
                        {
                            "采用名称": "国产芯片替代",
                            "关系判断": "父子",
                            "表层行业名": ["元件", "元器件"],
                        }
                    ]
                },
                "mainline_turnover_summary": {
                    "current_mainline": "国产芯片替代",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "国产芯片替代",
                        "confirmation_evidence": "国产芯片替代资金净流入靠前，涨停更集中",
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("- **市场特征**: 小幅上涨，主攻线国产芯片替代领涨", rendered)
        self.assertNotIn("主攻线元件领涨", rendered)


if __name__ == "__main__":
    unittest.main()
