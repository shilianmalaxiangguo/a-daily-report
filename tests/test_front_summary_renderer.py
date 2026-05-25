import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ACTION_TEXT = "只买军工一号，参与窗口确认后执行"

from report.front_summary_renderer import render_front_digest, render_front_summary_sections, render_mvp_focus_summary


class FrontSummaryRendererTest(unittest.TestCase):
    def assertNoEnglishTradingJargon(self, rendered):
        lowered = rendered.lower()
        for forbidden in ("act right", "setup", "probe", "follow through"):
            self.assertNotIn(forbidden, lowered)

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
                    "front_follow_action_text": ACTION_TEXT,
                },
                "enabled_node_keys": ["mvp_focus"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🎯 明日MVP摘要", rendered)
        self.assertNotIn("### 🧭 前台摘要", rendered)

    def test_render_front_digest_outputs_mainline_capacity_regime_and_turnover_share_tables(self):
        lines = render_front_digest(
            {
                "headline": "只看主线核心承接",
                "state_text": "修复延续",
                "mainline_label": "半导体",
                "style_action_text": "主线内做减法",
                "risk_parts": ["跌停2只"],
                "can_open_text": "只等确认",
                "turnover_share_trend_summary": "近25个交易日主线成交额占比趋势：当前17.0%，区间12.4%-17.0%，主线成交占比抬升，资金聚焦度走强。",
                "mainline_capacity_regime_summary": {
                    "mainline_capacity": "双线孕育",
                    "mainline_regime": "主线+背景线",
                    "primary_line": "半导体",
                    "other_lines": "电力 / 化学制品",
                    "confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
                    "sector_relationship_state": "半导体尝试替代，电力退成背景线待确认",
                    "mainline_process": "半导体启动，电力背景线",
                    "tomorrow_action": "先看资金是否继续选择半导体；背景线只观察回流",
                },
                "turnover_share_trend_rows": [
                    {
                        "date": "04-23",
                        "cycle_mainline": "电力",
                        "daily_attack_line": "电力",
                        "mainline_turnover": "2000亿",
                        "market_turnover": "12000亿",
                        "share": "16.0%",
                        "share_change": "-",
                        "interpretation": "旧周期退潮",
                    },
                    {
                        "date": "04-24",
                        "cycle_mainline": "半导体",
                        "daily_attack_line": "算力",
                        "mainline_turnover": "2180亿",
                        "market_turnover": "12834亿",
                        "share": "17.0%",
                        "share_change": "+1.2pct",
                        "interpretation": "主线占比继续抬升，资金仍在主线内加强",
                    }
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
        self.assertIn("| 双线孕育 | 主线+背景线 | 半导体 | 电力 / 化学制品 | 半导体高标和涨停更集中，成交占比靠前 | 半导体尝试替代，电力退成背景线待确认 | 半导体启动，电力背景线 | 先看资金是否继续选择半导体；背景线只观察回流 |", rendered)
        self.assertNotIn("| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |", rendered)
        self.assertIn("> 近25个交易日主线成交额占比趋势：当前17.0%，区间12.4%-17.0%，主线成交占比抬升，资金聚焦度走强。", rendered)
        self.assertIn("| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |", rendered)
        self.assertIn("| 04-24 | 半导体 | 算力 | 2180亿 | 12834亿 | 17.0% | +1.2pct | 主线占比继续抬升，资金仍在主线内加强 |", rendered)
        self.assertLess(rendered.index("04-24"), rendered.index("04-23"))

    def test_render_front_digest_outputs_full_contract_summary(self):
        lines = render_front_digest(
            {
                "headline": ACTION_TEXT,
                "state_text": "强分歧修复；环境可做",
                "mainline_label": "主攻线军工；趋势密度最强军工(3只)",
                "mainline_turnover_text": "主线未切换，军工仍是中心；成交额占比 10.2% -> 12.8% -> 15.1%，节奏偏强化",
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
        self.assertIn(f"- **先说结论**: {ACTION_TEXT}", rendered)
        self.assertIn("- **主线更替与占比**: 主线未切换，军工仍是中心；成交额占比 10.2% -> 12.8% -> 15.1%，节奏偏强化", rendered)
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
                "intervention_cycle": "预演参与窗口命中后只做50%标准进攻或0%",
                "exit_cycle": "失守关键位就作废",
                "delete_preview": "军工弱票 / 军工后排",
                "buy_target_text": "军工一号(000001)，只按预演参与窗口，不追盘中情绪顶点",
                "bridge_prep_label": "条件执行预备态",
                "bridge_prep_text": "军工一号，等待突破升级",
                "mainline_probe_text": "军工一号(000001)",
                "crossline_probe_text": "高端装备一号(000002)",
                "validation_probe_text": "军工二号(000003)",
                "front_follow_action_text": "只买军工一号，预演参与窗口命中后执行",
                "compact": False,
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 🎯 明日MVP摘要", rendered)
        self.assertIn("**特殊标的先看谁**: 军工一号(000001)", rendered)
        self.assertIn("**主线研究对象**: 军工一号(军工) / 军工二号(军工)", rendered)
        self.assertIn("**异常承接先看谁**: 军工一号(承接) / 军工二号(回封)", rendered)
        self.assertIn("**明天能不能开仓**: 只等唯一动作", rendered)
        self.assertIn("**明日唯一动作**: 只买军工一号，预演参与窗口命中后执行", rendered)

    def test_front_summary_renderers_replace_english_trading_jargon(self):
        context = {
            "headline": "军工 act right 后只等 setup 完整",
            "state_text": "probe Flow 可继续 follow through",
            "mainline_label": "半导体 setup 确认",
            "mainline_turnover_text": "follow through 仍在主线内",
            "special_probe_text": "军工一号是 mainline probe",
            "contract_logic_text": "setup 先满足，再看 act right",
            "rotation_summary_text": "probe 到 follow through",
            "weak_to_strong_active": True,
            "weak_to_strong_summary_text": "setup 后 act right",
            "style_action_text": "只做 probe，不追",
            "risk_parts": ["follow through 失败"],
            "can_open_text": "setup 不完整先等",
            "execution_framework_text": "act right 再执行",
            "special_probe_summary_text": "特殊 probe",
            "abnormal_preview": "异常 probe",
            "front_follow_action_text": "follow through 后执行",
        }

        rendered = "\n".join(render_front_digest(context) + render_mvp_focus_summary(context))

        self.assertNoEnglishTradingJargon(rendered)
        self.assertIn("走势符合强势标准", rendered)
        self.assertIn("形态条件", rendered)
        self.assertIn("优先观察对象", rendered)
        self.assertIn("延续承接", rendered)


if __name__ == "__main__":
    unittest.main()
