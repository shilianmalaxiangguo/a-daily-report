import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from report.market_research_renderer import (
    render_gem_breathing_pool_section,
    render_gem_breathing_step2_section,
    render_market_research_snapshot_section,
    render_step0_follow_section,
)


class MarketResearchRendererTest(unittest.TestCase):
    def test_render_market_research_snapshot_section_renders_cycle_calendar_table(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "cycle_calendar"],
                "cycle_calendar_rows": [
                    {
                        "week_label": "04-14当周",
                        "monday": {"date": "04-14", "mainline": "电力", "state": "主导"},
                        "tuesday": {"date": "04-15", "mainline": "电力", "state": "主导"},
                        "wednesday": {"date": "04-16", "mainline": "电力", "state": "强化"},
                        "thursday": {"date": "04-17", "mainline": "电力", "state": "分化"},
                        "friday": {"date": "04-18", "mainline": "电力", "state": "退潮"},
                    },
                    {
                        "week_label": "04-21当周",
                        "monday": {"date": "04-21", "mainline": "半导体", "state": "接力"},
                        "tuesday": {"date": "04-22", "mainline": "半导体", "state": "修复"},
                        "wednesday": [
                            {"date": "04-23", "mainline": "电力", "state": "反抽"},
                            {"date": "04-23", "mainline": "半导体", "state": "偏弱"},
                        ],
                        "thursday": {"date": "04-24", "mainline": "半导体", "state": "回流"},
                        "friday": {"date": "04-25", "mainline": "-", "state": "-"},
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 1. 周期日历主视图", rendered)
        self.assertIn("| 周次 | 一 | 二 | 三 | 四 | 五 |", rendered)
        self.assertIn("| 04-14当周 | [电力] 主导 | [电力] 主导 | [电力] 强化 | [电力] 分化 | [电力] 退潮 |", rendered)
        self.assertIn("[电力] 反抽 / [半导体] 偏弱", rendered)
        self.assertNotIn("04-14 [电力] 主导", rendered)
        self.assertNotIn("04-23 [电力] 反抽", rendered)
        self.assertNotIn("电力主导", rendered)

    def test_render_market_research_snapshot_section_renders_cycle_interpretation_table(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "cycle_interpretation"],
                "cycle_interpretation_rows": [
                    {
                        "cycle_label": "上个周期",
                        "date_range": "04-14 ~ 04-18",
                        "trading_days": "5日",
                        "mainline": "电力",
                        "market_state": "强化后分化",
                        "interpretation": "电力主导了上个周期，但后半段已经开始退潮，主导能力明显减弱",
                    },
                    {
                        "cycle_label": "当前周期",
                        "date_range": "04-21 ~ 04-24",
                        "trading_days": "4日",
                        "mainline": "半导体",
                        "market_state": "修复接力中",
                        "interpretation": "半导体正在尝试接替电力，但仍停留在修复段，没有进入舒服的攻击段",
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 2. 周期解读", rendered)
        self.assertIn("| 周期 | 时间段 | 交易日数 | 攻击线 | 周期阶段 | 传递性 | 市场状态 | 明日验证点 | 周期解读 |", rendered)
        self.assertIn("| 上个周期 | 04-14 ~ 04-18 | 5日 | 电力 | 已结束周期 | 背景观察 | 强化后分化 |", rendered)
        self.assertIn("半导体正在尝试接替电力", rendered)

    def test_render_market_research_snapshot_section_renders_cycle_attack_transfer_fields(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "cycle_interpretation"],
                "cycle_interpretation_rows": [
                    {
                        "cycle_label": "当前周期",
                        "date_range": "05-14",
                        "trading_days": "1日",
                        "mainline": "半导体",
                        "attack_line": "半导体",
                        "cycle_stage": "切换试攻",
                        "transfer_state": "首次攻击",
                        "market_state": "观察",
                        "tomorrow_validation": "看是否二次攻击，不能由单日攻击自动升级周期主线",
                        "interpretation": "半导体今日攻击成立，但传递性不足，不自动升级周期主线。",
                    }
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 当前周期 | 05-14 | 1日 | 半导体 | 切换试攻 | 首次攻击 | 观察 | 看是否二次攻击，不能由单日攻击自动升级周期主线 | 半导体今日攻击成立，但传递性不足，不自动升级周期主线。 |", rendered)
        self.assertNotIn("| 周期 | 时间段 | 交易日数 | 主导主线 | 市场状态 | 周期解读 |", rendered)
        self.assertNotIn("正在承担当前周期的主线观察任务", rendered)

    def test_render_market_research_snapshot_section_renders_pivot_mainline_interpretation_table(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "pivot_mainline_interpretation"],
                "pivot_mainline_rows": [
                    {
                        "date_range": "04-14 ~ 04-18",
                        "pivot_level": "大中枢",
                        "pivot_range": "3992.41 - 4114.84",
                        "position": "中枢上沿",
                        "structure_state": "上沿承压",
                        "mainline": "电力",
                        "mainline_degree": "大主线",
                        "evolution": "高位分化",
                        "replacement": "中枢震荡",
                        "interpretation": "[电力] 在这一段先主导市场，随后高位分化，主导能力开始减弱",
                    },
                    {
                        "date_range": "04-21 ~ 04-23",
                        "pivot_level": "小中枢",
                        "pivot_range": "3992.41 - 4114.84",
                        "position": "中枢内",
                        "structure_state": "中枢内震荡",
                        "mainline": "半导体",
                        "mainline_degree": "小周期主线",
                        "evolution": "修复接力",
                        "replacement": "接替电力",
                        "interpretation": "[半导体] 开始接替 [电力]，但目前只是修复接力，还没有形成稳定攻击段",
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 3. 中枢与主线解读", rendered)
        self.assertIn("| 时间段 | 中枢级别 | 中枢区间 | 所在位置 | 对应主线 | 主线程度 | 演化状态 | 接替关系 | 结构解读 |", rendered)
        self.assertIn("| 04-14 ~ 04-18 | 大中枢 | 3992.41 - 4114.84 | 中枢上沿 | 电力 | 大主线 | 高位分化 | 中枢震荡 |", rendered)
        self.assertIn("| 04-21 ~ 04-23 | 小中枢 | 3992.41 - 4114.84 | 中枢内 | 半导体 | 小周期主线 | 修复接力 | 接替电力 |", rendered)
        self.assertIn("[半导体] 开始接替 [电力]", rendered)
        self.assertNotIn("震荡 / 修复", rendered)

    def test_render_market_research_snapshot_section_renders_mainline_turnover_node(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_turnover"],
                "mainline_turnover_summary": {
                    "conclusion": "主线未切换，通信仍是中心",
                    "data_text": "最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%，节奏偏强化",
                    "action_text": "继续围绕通信做减法，不追支线分流",
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-04-24",
                            "cycle_mainline": "通信",
                            "daily_attack_line": "通信",
                            "mainline_turnover": "2180.00亿",
                            "market_turnover": "12834.00亿",
                            "share": "17.0%",
                            "share_change": "+1.2pct",
                            "interpretation": "主线占比继续抬升",
                        }
                    ],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |", rendered)
        self.assertIn("| 主线更替与成交额占比 | 主线未切换，通信仍是中心 |", rendered)
        self.assertIn("最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%，节奏偏强化", rendered)
        self.assertIn("继续围绕通信做减法，不追支线分流", rendered)
        self.assertIn("#### 主线成交额占比趋势", rendered)
        self.assertIn("| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |", rendered)
        self.assertIn("| 2026-04-24 | 通信 | 通信 | 2180.00亿 | 12834.00亿 | 17.0% | +1.2pct | 主线占比继续抬升 |", rendered)
        self.assertNotIn("| 盘面风险偏好 |", rendered)

    def test_render_market_research_snapshot_section_renders_mainline_capacity_regime_node(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_capacity_regime"],
                "mainline_turnover_summary": {
                    "mainline_capacity_regime_summary": {
                        "mainline_capacity": "双线孕育",
                        "mainline_regime": "混沌接力",
                        "primary_line": "半导体",
                        "other_lines": "电力 / 化学制品",
                        "confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
                        "sector_relationship_state": "半导体尝试替代，电力退成背景线待确认",
                        "mainline_process": "半导体启动，电力背景线",
                        "tomorrow_action": "先看资金是否继续选择半导体；背景线只观察回流",
                    },
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "candidate_lines": ["电力"],
                        "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
                        "sector_evidence_rows": [
                            {
                                "sector_name": "半导体",
                                "net_inflow_rank": 1,
                                "net_inflow_amount": 45.0,
                                "limit_up_count": 5,
                                "high_anchor_height": 4,
                                "turnover_share_change": 1.6,
                            },
                            {
                                "sector_name": "电力",
                                "net_inflow_rank": 2,
                                "net_inflow_amount": 8.0,
                                "limit_up_count": 1,
                                "high_anchor_height": 1,
                                "turnover_share_change": -0.5,
                            },
                        ],
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("### 4. 主线容量与格局判断", rendered)
        self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
        self.assertIn("| 双线孕育 | 混沌接力 | 半导体 | 电力 / 化学制品 | 半导体高标和涨停更集中，成交占比靠前 | 半导体尝试替代，电力退成背景线待确认 | 半导体启动，电力背景线 | 先看资金是否继续选择半导体；背景线只观察回流 |", rendered)
        self.assertIn("#### 主线攻击证据", rendered)
        self.assertIn("| 半导体 | 确认主攻线 | 第1 | +45.00亿 | 5 | 4 | +1.6pct | 半导体资金净流入靠前，涨停和高标更集中，成交占比扩张 |", rendered)

    def test_render_market_research_snapshot_mainline_focus_downgrades_when_attack_evidence_is_chaotic(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_focus"],
                "competition_result": "主攻线 半导体",
                "competition_evidence": "趋势2只 / 强势1只 / 涨停2只",
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线焦点 | 无确认主攻线 | 多方向局部活跃但资金未明显胜出 | 候选只观察，不给买入资格 |", rendered)
        self.assertNotIn("主攻线 半导体", rendered)

    def test_render_market_research_snapshot_turnover_rows_downgrade_when_attack_evidence_is_chaotic(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "mainline_turnover"],
                "mainline_turnover_summary": {
                    "conclusion": "主线待确认，暂不输出成交额占比结论",
                    "data_text": "最近1日主线 半导体 -> 电力 -> 电力；成交额占比 12.4%，节奏偏持平",
                    "action_text": "先等待主线明确，再谈成交额占比趋势",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    },
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-05-14",
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "mainline_turnover": "4206.70亿",
                            "market_turnover": "33880.86亿",
                            "share": "12.4%",
                            "share_change": "待累计",
                            "interpretation": "主线成交额占比可用，继续观察占比抬升或回落",
                        }
                    ],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 2026-05-14 | 暂无确认主线 | 暂无确认主攻线 | 4206.70亿 | 33880.86亿 | 12.4% | 待累计 | 候选方向成交额占比可记录，但未确认主攻线 |", rendered)
        self.assertNotIn("| 2026-05-14 | 半导体 | 半导体 |", rendered)

    def test_render_market_research_snapshot_rotation_downgrades_when_attack_evidence_is_chaotic(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "rotation"],
                "rotation_label": "爆发",
                "rotation_summary_text": "主攻线半导体 / 次强线电力 / 竞争线光伏设备",
                "rotation_action": "继续围着半导体做减法，只盯主攻线承接",
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线内部轮动 | 混沌轮动 | 多方向局部活跃但资金未明显胜出 | 不围着单一方向做减法，只保留候选观察 |", rendered)
        self.assertNotIn("主攻线半导体", rendered)
        self.assertNotIn("继续围着半导体做减法", rendered)

    def test_render_market_research_snapshot_narrative_downgrades_when_attack_evidence_is_chaotic(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "narrative"],
                "narrative_label": "半导体节点",
                "narrative_reason": "产业催化发酵，半导体目前是主攻线",
                "narrative_action": "继续盯半导体",
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 叙事节点 | 叙事待验证 | 题材只能做背景，先看板块攻击证据是否胜出 | 不把节点热度当主线确认 |", rendered)
        self.assertNotIn("半导体目前是主攻线", rendered)
        self.assertNotIn("继续盯半导体", rendered)

    def test_render_market_research_snapshot_section_renders_lhb_capital_intent_tables(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["header", "lhb_capital_intent"],
                "capital_intent_breakdown": {
                    "sector_fund_attitude": "半导体板块攻击资金确认",
                    "strength_feedback": "涨停5，高标4，成交占比+1.6pct",
                    "lhb_validation": "龙虎榜未验证主线",
                    "capital_consistency": "板块攻击成立，龙虎榜未验证",
                    "tomorrow_meaning": "先按板块攻击线观察，龙虎榜只作为加分，不作为主线否决",
                },
                "lhb_capital_status": {
                    "capital_strength": "强",
                    "capital_intensity": "主线净买明显放大",
                    "capital_direction": "半导体核心",
                    "capital_intent": "资金继续加仓主线核心，不做支线扩散",
                    "style_shift": "从情绪接力转向趋势容量",
                    "event_attribute": "业绩预期叠加产业催化",
                },
                "capital_conclusion": {
                    "current_capital_state": "主线资金主动进攻",
                    "mainline_attitude": "继续确认半导体为周期主线",
                    "tomorrow_action_meaning": "明天只看半导体核心承接，不追非主线龙虎榜热票",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🔬 市场研究快照", rendered)
        self.assertIn("#### 资金意图拆解", rendered)
        self.assertIn("| 板块攻击资金 | 强度反馈 | 龙虎榜验证 | 资金一致性 | 明日含义 |", rendered)
        self.assertIn("| 半导体板块攻击资金确认 | 涨停5，高标4，成交占比+1.6pct | 龙虎榜未验证主线 | 板块攻击成立，龙虎榜未验证 | 先按板块攻击线观察，龙虎榜只作为加分，不作为主线否决 |", rendered)
        self.assertIn("#### 龙虎榜资金状态", rendered)
        self.assertIn("| 资金强弱 | 资金力度 | 资金方向 | 资金意图 | 风格转向 | 事件属性 |", rendered)
        self.assertIn("| 强 | 主线净买明显放大 | 半导体核心 | 资金继续加仓主线核心，不做支线扩散 | 从情绪接力转向趋势容量 | 业绩预期叠加产业催化 |", rendered)
        self.assertIn("#### 资金结论", rendered)
        self.assertIn("| 当前资金状态 | 对主线的态度 | 对明日动作的含义 |", rendered)
        self.assertIn("| 主线资金主动进攻 | 继续确认半导体为周期主线 | 明天只看半导体核心承接，不追非主线龙虎榜热票 |", rendered)

    def test_render_market_research_snapshot_section_does_not_dump_raw_lhb_ranking_when_capital_intent_exists(self):
        lines = render_market_research_snapshot_section(
            {
                "compact": False,
                "enabled_node_keys": ["lhb_capital_intent"],
                "lhb_capital_status": {
                    "capital_strength": "偏强",
                    "capital_intensity": "榜单资金集中",
                    "capital_direction": "机器人",
                    "capital_intent": "试探新方向",
                    "style_shift": "高低切",
                    "event_attribute": "消息催化",
                },
                "lhb_rank_rows": [{"rank": 1, "stock": "原始榜一"}],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 资金强弱 | 资金力度 | 资金方向 | 资金意图 | 风格转向 | 事件属性 |", rendered)
        self.assertNotIn("原始榜一", rendered)
        self.assertNotIn("买入排名", rendered)

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
                    {"name": "军工转债", "code": "123001", "sector": "军工", "tier": "A层", "abnormal_summary": _m("均线", "粘合"), "tomorrow_strength": 82}
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
        self.assertIn("> **只看什么**：波动收敛、量价温和放大、右侧确认。", "\n".join(pool_lines))
        self.assertNotIn(_m("均线", "粘合"), "\n".join(step2_lines + pool_lines))
        self.assertNotIn("核心问题", "\n".join(pool_lines))
        self.assertIn("军工转债", "\n".join(pool_lines))


if __name__ == "__main__":
    unittest.main()
