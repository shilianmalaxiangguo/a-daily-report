import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.execution_wording import TWO_B_CONFIRMATION_CLAUSE


class PositionStrategyReportTest(unittest.TestCase):
    def test_render_separates_holding_actions_and_new_opportunity_actions_by_market_script(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={
                "execution_stage_context": {
                    "extreme_conviction_list": [
                        {
                            "code": "000001",
                            "name": "军工一号",
                            "sector": "军工",
                            "conviction_reason": "板块锚定龙",
                            "planned_participation": {
                                "buy_window": "09:30-09:35",
                                "entry_timing": "open_core",
                                "attack_state": "50%",
                                "cancellation": "竞价表态、开盘承接、板块同步任一失败，按0%不参与",
                            },
                        },
                        {
                            "code": "000002",
                            "name": "算力二号",
                            "sector": "算力",
                            "conviction_reason": "主线补涨",
                            "participation_script": {
                                "buy_window": "09:50-10:10",
                                "entry_timing": "ten_confirm",
                                "attack_state": "50%",
                            },
                        },
                    ]
                }
            },
            target_date="2026-05-19",
            positions=[
                {"name": "军工一号", "position": 30.0},
                {"name": "旧仓三号", "position": 20.0},
            ],
        )

        self.assertIn("# 2026-05-19 持仓策略", report)
        for heading in (
            "# 上证单边上升",
            "# 上证震荡",
            "# 上证单边下跌",
            "# 上证M顶",
            "# 上证W底",
            "# 上证V反",
            "# 上证A杀",
        ):
            self.assertIn(heading, report)
        self.assertIn("## 持仓处理", report)
        self.assertIn("## 新机会处理", report)
        self.assertIn(TWO_B_CONFIRMATION_CLAUSE, report)
        self.assertIn("| 军工一号 | 30.0% | 是 |", report)
        self.assertIn("| 旧仓三号 | 20.0% | 否 |", report)
        self.assertIn("| 军工一号 | 000001 | 军工 | 09:30-09:35 | 50% |", report)
        self.assertIn("| 算力二号 | 000002 | 算力 | 09:50-10:10 | 50% |", report)
        self.assertIn("卖出处理和买入处理分开判断", report)
        self.assertIn("持仓按防守线独立评估", report)
        self.assertNotIn("卖出用于买入", report)
        self.assertNotIn("为了买而卖", report)
        self.assertNotIn("只处理旧仓风险", report)

    def test_render_formats_lot_based_t0_holding_position(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={},
            target_date="2026-06-01",
            positions=[
                {
                    "name": "华电辽能",
                    "lots": 2.0,
                    "shares": 200,
                    "buy_lots": 2.0,
                    "sell_lots": 2.0,
                    "trade_action": "做T",
                }
            ],
        )

        self.assertIn("| 华电辽能 | 2手/200股，今日做T买入2手、卖出2手 | 否 |", report)
        self.assertNotIn("| 卖2手 |", report)

    def test_render_includes_failed_t0_review_note(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={},
            target_date="2026-06-05",
            positions=[
                {
                    "name": "华电辽能",
                    "position": 100.0,
                    "daily_profit_pct": -7.0,
                    "trade_action": "做T",
                    "holding_note": "T失败；0轴买入；尾盘卖出；全仓吃满-7%下跌",
                }
            ],
        )

        self.assertIn("| 华电辽能 | 100.0%，今日做T，T失败；0轴买入；尾盘卖出；全仓吃满-7%下跌 | 否 |", report)

    def test_save_position_strategy_report_writes_replay_path(self):
        from portfolio.position_strategy_report import save_position_strategy_report

        with TemporaryDirectory() as tempdir:
            saved_path = save_position_strategy_report(
                "# strategy",
                "2026-05-19",
                mode="replay",
                output_root=tempdir,
            )

            path = Path(saved_path)
            self.assertEqual(path.name, "2026-05-19_持仓策略_replay.md")
            self.assertEqual(path.parent, Path(tempdir) / "replay")
            self.assertEqual(path.read_text(encoding="utf-8"), "# strategy")

    def test_render_can_use_final_report_markdown_extreme_conviction_table(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={},
            target_date="2026-05-19",
            positions=[{"name": "合百集团", "position": 40.0}],
            source_report_markdown="""
**极度看好名单**（只保留最心动的少数，每只都绑定参与窗口）:
| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|----------|
| 1 | 合百集团 | 000417 | 股权转让 | 板块锚定龙 | 板块锚定龙 | 只盯分歧后的转强 |
""",
        )

        self.assertIn("| 合百集团 | 40.0% | 是 |", report)
        self.assertIn("| 合百集团 | 000417 | 股权转让 |", report)

    def test_render_does_not_turn_observation_appendix_into_new_opportunity_when_new_position_is_zero(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={},
            target_date="2026-05-26",
            positions=[{"name": "晶方科技", "position": 42.0}],
            source_report_markdown="""
## 明日账户建议
| 项目 | 结论 |
|------|------|
| 明日动作 | 先处理旧仓，不新增参与 |
| T0主对象 | 持有晶方科技(603005)，100股，成本43.835；先看45.1能否守住，跌破42.84~43.05或09:50-10:10收不回先卖；新开仓0手 |
| T0备用 | 华天科技(002185)：仅作条件观察 |
| 新开仓上限 | 0 |

**重点观察名单**（只保留最心动的少数，每只都绑定参与窗口）:
| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 执行分层 | 观察理由 | 明日原则 |
|--------|------|------|----------|----------|----------|----------|----------|
| 1 | 步步高 | 002251 | 超市连锁 | 核心传导者 / 中位传导 | 可执行候选 | 板块锚定龙 / 首板 | 修复观察只看09:50-10:10窗口，未确认不参与 |
| 2 | 大众公用 | 600635 | 供气供热 | 核心传导者 / 中位传导 | 可执行候选 | 板块锚定龙 / 首板 | 修复观察只看09:50-10:10窗口，未确认不参与 |
| 3 | 红星发展 | 600367 | 化工原料 | 核心传导者 / 中位传导 | 可执行候选 | 首板 / 趋势审美 | 修复观察只看09:50-10:10窗口，未确认不参与 |

#### 附录A：明日极度看好列表
| 序号 | 股票 | 代码 | 板块 | 名单身份 | 观察理由 | 明日原则 |
|------|------|------|------|------|------|------|
| 1 | 步步高 | 002251 | 超市连锁 | 候选观察 | 板块锚定龙 / 首板 | 最终0%时只作观察样本，不构成明日新增参与 |
""",
        )

        self.assertIn("当前没有明日极度看好候选，明日不设目标标的。", report)
        self.assertIn("| 晶方科技 | 42.0% | 否 |", report)
        self.assertNotIn("| 步步高 | 002251 |", report)
        self.assertNotIn("| 大众公用 | 600635 |", report)
        self.assertNotIn("| 红星发展 | 600367 |", report)
        self.assertNotIn("50%条件执行 | 09:30-09:35", report)

    def test_render_preserves_prior_high_inertia_identity_for_old_holding(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={
                "market_research_snapshot": {
                    "observation": {
                        "tracking_memory_status": {
                            "tentative_items": [
                                {
                                    "name": "上峰水泥",
                                    "code": "000672",
                                    "sector": "国产芯片",
                                    "status": "tentative",
                                    "sources": ["abnormal_watch", "leader_memory", "watchlist"],
                                    "last_reason": "T字板分歧转一致，明日可能加速+板块前排；强异动已出现，等分歧后再看转强 / 观察竞价",
                                    "days_since_seen": 1,
                                }
                            ]
                        }
                    }
                }
            },
            target_date="2026-05-19",
            positions=[{"name": "上峰水泥", "position": 100.0}],
        )

        self.assertIn("| 上峰水泥 | 100.0% | 昨日高惯性回看 |", report)
        self.assertNotIn("| 上峰水泥 | 100.0% | 否 |", report)
        self.assertIn("保留延续观察资格", report)
        self.assertIn("不是当前新买按钮", report)
        self.assertIn("09:50-10:10", report)
        self.assertIn("分时黄线/0轴", report)

    def test_render_candidate_rows_show_open_attack_ten_confirm_and_split_entry(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={
                "execution_stage_context": {
                    "extreme_conviction_list": [
                        {
                            "code": "000672",
                            "name": "上峰水泥",
                            "sector": "国产芯片",
                            "conviction_reason": "T字板分歧转一致，明日可能加速+板块前排",
                            "planned_participation": {
                                "buy_window": "09:30-09:35",
                                "entry_timing": "open_core",
                                "attack_state": "50%",
                            },
                        }
                    ]
                }
            },
            target_date="2026-05-19",
            positions=[],
        )

        self.assertIn("09:30-09:35 开盘强攻/打板入口", report)
        self.assertIn("09:50-10:10 筹码交换/分时黄线或0轴确认入口", report)
        self.assertIn("价格与分时黄色均价线交叉并形成金叉", report)
        self.assertIn("水下强势修复到0轴", report)
        self.assertIn("逻辑确认后再看MA3/MA7/MA10/MA20", report)
        self.assertIn("MA3=攻击线", report)
        self.assertIn("MA7=分歧线", report)
        self.assertIn("MA10=认错线", report)
        self.assertIn("MA20=环境线", report)
        self.assertIn("MA不是买入理由", report)
        self.assertIn("分两笔", report)
        self.assertIn("不把价格更低本身当买点", report)

    def test_render_selects_tomorrow_target_when_extreme_candidates_exist(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={
                "market_research_snapshot": {
                    "state_machine": {
                        "market_performance_evidence": {
                            "funding_activity": {"top50_share_pct": 19.86, "regime": "震荡蓄势期"},
                            "new_high_attack": {"new_high_count": 164, "all_a_share_pct": 3.28},
                        }
                    }
                },
                "execution_stage_context": {
                    "extreme_conviction_list": [
                        {
                            "code": "000586",
                            "name": "汇源通信",
                            "sector": "通信设备",
                            "conviction_reason": "板块锚定龙 / 首板",
                            "planned_participation": {
                                "buy_window": "09:30-09:35",
                                "entry_timing": "open_core",
                                "attack_state": "50%",
                                "cancellation": "竞价表态、开盘承接、板块同步任一失败，按0%不参与",
                            },
                        },
                        {
                            "code": "603333",
                            "name": "尚纬股份",
                            "sector": "电气设备",
                            "conviction_reason": "板块锚定龙 / 首板",
                            "planned_participation": {"attack_state": "50%"},
                        },
                    ]
                },
            },
            target_date="2026-05-19",
            positions=[],
        )

        self.assertIn("## 明日目标标的", report)
        self.assertIn("| 汇源通信 | 000586 | 通信设备 | 50%条件执行 |", report)
        self.assertIn("条件不满足回到0%", report)
        non_ice_scripts = report.split("# 上证A杀", 1)[0]
        self.assertNotIn("默认不开新仓", non_ice_scripts)
        self.assertNotIn("默认不买", non_ice_scripts)
        self.assertNotIn("极度看好全部降为观察", non_ice_scripts)

    def test_render_includes_ta_te_day_order_for_old_position_and_tomorrow_target(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        with TemporaryDirectory() as tempdir:
            report = render_position_strategy_report(
                data={
                    "execution_stage_context": {
                        "extreme_conviction_list": [
                            {
                                "code": "000586",
                                "name": "汇源通信",
                                "sector": "通信设备",
                                "planned_participation": {
                                    "buy_window": "09:50-10:10",
                                    "attack_state": "50%",
                                },
                            }
                        ]
                    }
                },
                target_date="2026-06-26",
                positions=[{"name": "华电辽能", "position": 100.0}],
                output_root=tempdir,
            )

        self.assertTrue(report.startswith("| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |"))
        self.assertNotIn("```mermaid", report)
        self.assertNotIn("gantt", report)
        self.assertIn("| Ta | 2026-06-23（周二） | 最远复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对，不改变Te动作 |", report)
        tc_line = next(line for line in report.splitlines() if line.startswith("| Tc |"))
        self.assertNotIn("华电辽能", tc_line)
        self.assertIn("| Td | 2026-06-26（周五） | 报告日：旧仓进入复核：华电辽能 | 华电辽能 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |", report)
        self.assertIn("| Te | 2026-06-29（周一） | 新目标单独看B1，不用旧仓亏损补仓 | 汇源通信(000586) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |", report)
        self.assertIn("Ta最远，Tb/Tc为前两段，Td是报告日，Te是明日执行日", report)
        self.assertNotIn("旧路径来源", report)
        self.assertNotIn("2026-06-27（周六）", report)
        self.assertNotIn("2026-06-28（周日）", report)
        self.assertNotIn("| 槽位 | 标的 |", report)

    def test_render_empty_tomorrow_target_states_missing_tb_tc_and_early_ta_exit(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={},
            target_date="2026-06-26",
            positions=[{"name": "太极实业", "position": 100.0}],
        )

        self.assertIn("| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |", report)
        self.assertIn("| Td | 2026-06-26（周五） | 报告日：旧仓进入复核：太极实业 | 太极实业 | Te不新增参与，B2取消 | 只观察，不新增参与 |", report)
        self.assertIn("| Te | 2026-06-29（周一） | 只处理旧仓风险 | 太极实业 | 没有B2；只处理旧仓风险 | 旧仓未修复则继续降风险 |", report)
        self.assertIn("Te只处理已确认旧仓风险，不新增参与对象", report)

    def test_render_recovers_postgres_position_summary_for_current_day_order(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        with TemporaryDirectory() as tempdir:
            report = render_position_strategy_report(
                data={
                    "position_context_provided": True,
                    "personal_position_context": {
                        "existing_position_summary": {
                            "has_position": False,
                            "has_pending_position": True,
                            "summary": "持有长电科技(600584)，100%仓位",
                            "name": "长电科技",
                            "code": "600584",
                            "position": 100.0,
                            "position_source": "previous_report_target_default_1x",
                            "source_report_date": "2026-07-09",
                            "inferred_from_previous_report": True,
                        }
                    },
                },
                target_date="2026-07-10",
                positions=[],
                output_root=Path(tempdir),
            )

        self.assertIn(
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584)；前日报计划来源=2026-07-09 | 长电科技(600584) |",
            report,
        )
        self.assertIn(
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |",
            report,
        )
        self.assertIn(
            "- Te只核实前日报计划是否成交；未确认前保持0%不参与，不新增B2。",
            report,
        )
        self.assertIn(
            "| 长电科技（待成交确认） | 0x | 否 | 先确认成交事实；未确认不执行持仓卖出或加仓动作 | 前日报计划推定，未确认不视为B1或旧仓 |",
            report,
        )
        self.assertNotIn("| 长电科技 | 100.0%", report)
        self.assertNotIn("持有长电科技", report)

    def test_render_keeps_unconfirmed_postgres_plan_unconfirmed_on_next_report_day(self):
        from portfolio import position_strategy_report

        snapshots = {
            "2026-07-08": {"position_context_provided": True},
            "2026-07-09": {"position_context_provided": True},
            "2026-07-10": {
                "position_context_provided": True,
                "personal_position_context": {
                    "existing_position_summary": {
                        "has_position": False,
                        "has_pending_position": True,
                        "name": "长电科技",
                        "code": "600584",
                        "position": 100.0,
                        "position_source": "previous_report_target_default_1x",
                        "source_report_date": "2026-07-09",
                        "inferred_from_previous_report": True,
                    }
                },
            },
        }

        with TemporaryDirectory() as tempdir, patch.object(
            position_strategy_report,
            "_load_report_day_data_from_postgres",
            side_effect=lambda day: snapshots.get(day),
        ):
            report = position_strategy_report.render_position_strategy_report(
                data={"position_context_provided": True},
                target_date="2026-07-13",
                positions=[],
                output_root=Path(tempdir),
                prefer_postgres_history=True,
            )

        self.assertIn(
            "| Tc | 2026-07-10（周五） | 上一交易日计划待成交确认：长电科技(600584) | 长电科技(600584) | 未确认成交，不视为B1 | 进入Td先确认成交事实 |",
            report,
        )
        self.assertNotIn("| Tc | 2026-07-10（周五） | 上一交易日路径：长电科技(600584)", report)
        self.assertNotIn("可能形成B1旧仓", report)

    def test_postgres_only_unknown_history_does_not_backfill_current_pending_plan(self):
        from portfolio import position_strategy_report

        snapshots = {
            "2026-07-07": {"position_context_provided": False},
            "2026-07-08": {
                "position_context_provided": True,
                "personal_position_context": {
                    "existing_position_summary": {
                        "has_position": False,
                        "has_pending_position": True,
                        "name": "华天科技",
                        "code": "002185",
                        "position_source": "previous_report_target_default_1x",
                        "inferred_from_previous_report": True,
                    }
                },
            },
            "2026-07-09": {"position_context_provided": False},
        }
        current_data = {
            "position_context_provided": True,
            "personal_position_context": {
                "existing_position_summary": {
                    "has_position": False,
                    "has_pending_position": True,
                    "name": "长电科技",
                    "code": "600584",
                    "default_position_pct": 100.0,
                    "position_source": "previous_report_target_default_1x",
                    "source_report_date": "2026-07-09",
                    "inferred_from_previous_report": True,
                }
            },
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                },
            },
            "final_target_resolution": {
                "new_entry_target": {},
                "display_target": {},
                "capital_priority_decision": {"capital_priority": "wait"},
            },
        }

        with TemporaryDirectory() as tempdir, patch.dict(
            "os.environ",
            {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
            clear=False,
        ), patch.object(
            position_strategy_report,
            "_load_report_day_data_from_postgres",
            side_effect=lambda day: snapshots.get(day, {}),
        ):
            report = position_strategy_report.render_position_strategy_report(
                data=current_data,
                target_date="2026-07-10",
                positions=[],
                output_root=Path(tempdir),
                prefer_postgres_history=True,
            )

        self.assertIn(
            "| Ta | 2026-07-07（周二） | 最远复盘日：持仓未输入 | - | B1事实待确认 |",
            report,
        )
        self.assertIn(
            "| Tb | 2026-07-08（周三） | 历史复盘日计划待成交确认：华天科技(002185) | 华天科技(002185) | 未确认成交，不视为B1 |",
            report,
        )
        self.assertIn(
            "| Tc | 2026-07-09（周四） | 前一交易日持仓未输入 | - | B1事实待确认 | 先确认账户事实，不从当前计划反推历史持仓 |",
            report,
        )
        tc_line = next(line for line in report.splitlines() if line.startswith("| Tc |"))
        self.assertNotIn("长电科技(600584)", tc_line)
        self.assertNotIn("可能形成B1旧仓", tc_line)
        self.assertIn(
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 |",
            report,
        )

    def test_render_prefers_postgres_history_over_markdown_history(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-09_持仓策略.md").write_text(
                "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
                "|------|------|----------|----------|-------------|------|\n"
                "| Td | 2026-07-09（周四） | 报告日：空仓 | 无 | Te不新增参与，B2取消 | 只观察，不新增参与 |\n",
                encoding="utf-8",
            )
            snapshots = {
                "2026-07-07": {"position_context_provided": True},
                "2026-07-08": {"position_context_provided": True},
                "2026-07-09": {
                    "position_context_provided": True,
                    "personal_position_context": {
                        "existing_position_summary": {
                            "has_position": True,
                            "name": "长电科技",
                            "code": "600584",
                            "position": 100.0,
                        }
                    },
                    "final_target_resolution": {
                        "new_entry_target": {},
                        "capital_priority_decision": {"capital_priority": "wait"},
                    },
                },
            }
            with patch(
                "portfolio.position_strategy_report._load_report_day_data_from_postgres",
                side_effect=lambda day: snapshots.get(day, {}),
            ):
                report = render_position_strategy_report(
                    data={"position_context_provided": True},
                    target_date="2026-07-10",
                    positions=[],
                    output_root=root,
                    prefer_postgres_history=True,
                )

        self.assertIn(
            "| Tc | 2026-07-09（周四） | 上一交易日路径：长电科技(600584) | 长电科技(600584) |",
            report,
        )

    def test_postgres_history_loader_unwraps_daily_report_data(self):
        from portfolio.position_strategy_report import _load_report_day_data_from_postgres

        with patch("storage.database_service.DatabaseService.from_environment") as factory:
            factory.return_value.is_postgres_backed.return_value = True
            factory.return_value.load_daily_report_snapshot.return_value = {
                "source": "postgresql.daily_report_facts",
                "field_count": 10,
                "data": {
                    "personal_position_context": {
                        "existing_position_summary": {
                            "has_position": True,
                            "name": "长电科技",
                            "code": "600584",
                        }
                    }
                },
            }

            result = _load_report_day_data_from_postgres("2026-07-10")

        self.assertEqual(
            result["personal_position_context"]["existing_position_summary"]["code"],
            "600584",
        )

    def test_postgres_history_loader_treats_empty_envelope_as_unavailable(self):
        from portfolio.position_strategy_report import _load_report_day_data_from_postgres

        with patch("storage.database_service.DatabaseService.from_environment") as factory:
            factory.return_value.is_postgres_backed.return_value = True
            factory.return_value.load_daily_report_snapshot.return_value = {
                "source": "postgresql.daily_report_facts",
                "field_count": 0,
                "data": {},
            }

            result = _load_report_day_data_from_postgres("2026-07-09")

        self.assertIsNone(result)

    def test_render_zero_final_object_keeps_process_candidate_out_of_tb_path(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-03_A股日报_执行摘要.md").write_text(
                "| 最终对象 | 明日执行对象：太极实业(600667) |\n",
                encoding="utf-8",
            )
            report = render_position_strategy_report(
                data={
                    "final_target_resolution": {
                        "new_entry_target": {},
                        "process_target": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                        "display_target": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                        "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"},
                    },
                    "execution_stage_context": {
                        "extreme_conviction_list": [
                            {
                                "name": "太极实业",
                                "code": "600667",
                                "sector": "半导体",
                                "planned_participation": {"buy_window": "09:50-10:10", "attack_state": "50%"},
                            }
                        ],
                        "selection_workflow": {
                            "final": {
                                "execution_object": {},
                                "position_pct": 0,
                                "action_text": "0%不参与",
                            }
                        },
                    },
                },
                target_date="2026-07-06",
                positions=[],
                source_report_markdown="""
## 明日执行结论
| 项目 | 结论 |
|------|------|
| 明日仓位 | 0%不参与 |
| 明日执行对象 | 太极实业(600667) |
| 执行性质 | 无明日执行对象 |
| 推导摘要 | 最终不新增参与 |
""",
                output_root=root,
            )

        self.assertIn("| Te | 2026-07-07（周二） | 空仓等待B1资格 | 无 | 没有B1/B2；保持空仓 | 空仓等待下一份日报 |", report)
        self.assertIn("当前没有明日极度看好候选，明日不设目标标的。", report)
        self.assertIn("| 太极实业 | 600667 | 半导体 | 无新增参与窗口 | 0%不参与 | 只作过程回放，不新增参与 | 不参与 | - |", report)

    def test_render_timeline_prefers_final_entry_target_over_process_candidate(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={
                "final_target_resolution": {
                    "new_entry_target": {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                        "planned_participation": {"buy_window": "09:30-09:35", "attack_state": "满仓条件执行"},
                    },
                    "display_target": {"name": "华天科技", "code": "002185", "sector": "半导体"},
                    "capital_priority_decision": {"capital_priority": "new_entry"},
                },
                "execution_stage_context": {
                    "extreme_conviction_list": [
                        {
                            "name": "和远气体",
                            "code": "002971",
                            "sector": "化工原料",
                            "planned_participation": {"buy_window": "09:50-10:10", "attack_state": "50%"},
                        }
                    ],
                    "selection_workflow": {
                        "final": {
                            "execution_object": {"name": "华天科技", "code": "002185", "sector": "半导体"},
                            "position_pct": 100,
                            "action_text": "满仓条件执行",
                        }
                    },
                },
            },
            target_date="2026-07-07",
            positions=[],
        )

        self.assertIn("| Td | 2026-07-07（周二） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |", report)
        self.assertIn("| Te | 2026-07-08（周三） | 新目标单独看B1，不用旧仓亏损补仓 | 华天科技(002185) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |", report)
        self.assertNotIn("| Te | 2026-07-08（周三） | 新目标单独看B1，不用旧仓亏损补仓 | 和远气体(002971)", report)
        self.assertIn("| 华天科技 | 002185 | 半导体 | 100%核心进攻候选 | 09:30-09:35 |", report)
        tomorrow_target_section = report.split("## 明日目标标的", 1)[1].split("# 上证单边上升", 1)[0]
        self.assertNotIn("和远气体 | 002971", tomorrow_target_section)

    def test_observation_only_changdian_source_markdown_cannot_fill_tb_target(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        source_report = """
## 日报裁决总览
| 项目 | 结论 |
|------|------|
| 仓位姿态 | 0%不参与 |
| 最终对象 | 观察对象：长电科技(600584) |
| 对象性质 | 观察对象，不新增参与 |
| 推导摘要 | 明日执行目标为无，只观察长电科技(600584)的承接是否重新成立。 |

## 明日执行结论
| 项目 | 结论 |
|------|------|
| 明日仓位 | 0%不参与 |
| 明日执行对象 | 无 |
| 执行目标 | 无 |
| 观察对象 | 长电科技(600584) |

`-- 最终对象=长电科技(600584) 身份=观察对象（执行目标为无）
"""
        with TemporaryDirectory() as tempdir:
            report = render_position_strategy_report(
                data={},
                target_date="2026-07-06",
                positions=[],
                source_report_markdown=source_report,
                output_root=Path(tempdir),
            )

        self.assertIn("| Te | 2026-07-07（周二） | 空仓等待B1资格 | 无 | 没有B1/B2；保持空仓 | 空仓等待下一份日报 |", report)
        self.assertNotIn("| Te | 2026-07-07（周二） | 新目标单独看B1，不用旧仓亏损补仓 | 长电科技(600584)", report)

    def test_render_unknown_position_timeline_does_not_claim_no_old_holding(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        with TemporaryDirectory() as tempdir:
            report = render_position_strategy_report(
                data={
                    "position_context_provided": False,
                    "execution_stage_context": {
                        "extreme_conviction_list": [
                            {
                                "code": "000586",
                                "name": "汇源通信",
                                "sector": "通信设备",
                                "planned_participation": {
                                    "buy_window": "09:50-10:10",
                                    "attack_state": "50%",
                                },
                            }
                        ]
                    },
                },
                target_date="2026-06-26",
                positions=[],
                output_root=Path(tempdir),
            )

        self.assertIn("| Tc | 2026-06-25（周四） | 前一交易日持仓未输入 | - | B1事实待确认 | 先确认账户事实，不从当前计划反推历史持仓 |", report)
        self.assertIn("| Td | 2026-06-26（周五） | 报告日：持仓未输入 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |", report)
        self.assertIn("| Te | 2026-06-29（周一） | 先确认是否已有旧仓 | 汇源通信(000586) | 先确认是否已有B1；未确认不新增B2 | 旧仓事实不清时不新增参与 |", report)
        timeline_text = report.split("# 2026-06-26 持仓策略", 1)[0]
        self.assertNotIn("无旧仓", timeline_text)

    def test_render_day_order_keeps_today_unknown_when_previous_report_had_no_target(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-08_A股日报_执行摘要.md").write_text(
                "\n".join(
                    [
                        "## 日报裁决总览",
                        "| 项目 | 结论 |",
                        "|------|------|",
                        "| 仓位姿态 | 0%不参与 |",
                        "| 最终对象 | 无 |",
                        "| 对象性质 | 无明日执行对象 |",
                        "",
                        "## 明日执行结论",
                        "| 项目 | 结论 |",
                        "|------|------|",
                        "| 明日仓位 | 0%不参与 |",
                        "| 明日执行对象 | 无 |",
                    ]
                ),
                encoding="utf-8",
            )
            report = render_position_strategy_report(
                data={
                    "position_context_provided": False,
                    "execution_stage_context": {
                        "extreme_conviction_list": [
                            {
                                "code": "600584",
                                "name": "长电科技",
                                "sector": "半导体",
                                "planned_participation": {
                                    "buy_window": "09:50-10:10",
                                    "attack_state": "50%",
                                },
                            }
                        ]
                    },
                },
                target_date="2026-07-09",
                positions=[],
                output_root=root,
            )

        self.assertIn(
            "| Td | 2026-07-09（周四） | 报告日：持仓未输入 | 无 |",
            report,
        )
        self.assertIn(
            "| Te | 2026-07-10（周五） | 新目标单独看B1，不用旧仓亏损补仓 | 长电科技(600584) |",
            report,
        )
        td_line = next(line for line in report.splitlines() if line.startswith("| Td |"))
        self.assertNotIn("长电科技(600584)", td_line)

    def test_postgres_only_history_reader_stops_instead_of_using_stale_markdown(self):
        from portfolio import position_strategy_report

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-09_A股日报_执行摘要.md").write_text(
                "| 明日执行对象 | 长电科技(600584) |\n",
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
                clear=False,
            ), patch.object(
                position_strategy_report,
                "_load_report_day_data_from_postgres",
                return_value={},
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "2026-07-09 PostgreSQL 历史账户事实不可用，停止生成",
                ):
                    position_strategy_report._read_report_day_account_state(
                        "2026-07-09",
                        output_root=root,
                        prefer_postgres_history=True,
                    )

    def test_postgres_only_previous_target_reader_stops_before_stale_markdown(self):
        from portfolio import position_strategy_report

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-09_A股日报_执行摘要.md").write_text(
                "| 明日执行对象 | 长电科技(600584) |\n",
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
                clear=False,
            ), patch.object(
                position_strategy_report,
                "_load_report_day_data_from_postgres",
                return_value={},
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "2026-07-09 PostgreSQL 前日报计划事实不可用，停止生成",
                ):
                    position_strategy_report._read_previous_report_target(
                        "2026-07-10",
                        output_root=root,
                        prefer_postgres_history=True,
                    )

    def test_postgres_only_history_reader_keeps_postgres_empty_fact_over_stale_markdown(self):
        from portfolio import position_strategy_report

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-09_A股日报_执行摘要.md").write_text(
                "| 明日执行对象 | 长电科技(600584) |\n",
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
                clear=False,
            ), patch.object(
                position_strategy_report,
                "_load_report_day_data_from_postgres",
                return_value={"position_context_provided": True},
            ):
                state = position_strategy_report._read_report_day_account_state(
                    "2026-07-09",
                    output_root=root,
                    prefer_postgres_history=True,
                )

        self.assertEqual(state["state"], "empty")
        self.assertIn("postgres", state["source"])

    def test_markdown_history_reader_keeps_unknown_account_fact_unknown(self):
        from portfolio import position_strategy_report

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-09_持仓策略.md").write_text(
                "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
                "|------|------|----------|----------|-------------|------|\n"
                "| Td | 2026-07-09（周四） | 报告日：持仓未输入 | - | B1事实待确认 | 只作路径校对 |\n",
                encoding="utf-8",
            )

            state = position_strategy_report._read_report_day_account_state(
                "2026-07-09",
                output_root=root,
            )

        self.assertEqual(state["state"], "unknown")

    def test_render_uses_previous_report_target_as_source_note_not_account_holding(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-06-26_A股日报_执行摘要.md").write_text(
                "| 最终对象 | 明日执行对象：太极实业(600667) |\n",
                encoding="utf-8",
            )
            report = render_position_strategy_report(
                data={},
                target_date="2026-06-29",
                positions=[],
                source_report_markdown="| 明日执行对象 | 深科技(000021) |\n",
                output_root=root,
            )

        self.assertIn("| Ta | 2026-06-24（周三） | 最远复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对，不改变Te动作 |", report)
        self.assertIn("| Tc | 2026-06-26（周五） | 前一交易日持仓未输入 | - | B1事实待确认 | 先确认账户事实，不从当前计划反推历史持仓 |", report)
        self.assertIn("| Td | 2026-06-29（周一） | 报告日：持仓未输入；上一份日报目标来源=2026-06-26 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |", report)
        self.assertIn("| Te | 2026-06-30（周二） | 新目标单独看B1，不用旧仓亏损补仓 | 深科技(000021) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |", report)

    def test_render_day_order_carries_history_paths_without_today_position(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-06_持仓策略.md").write_text(
                "\n".join(
                    [
                        "| 轨道 | 标的 | 2026-07-05（周日） | 2026-07-06（周一） |",
                        "|------|------|------|------|",
                        "| Ta旧仓 | 太极实业(600667) | 上一份日报目标，进入旧仓/旧路径复核 | Ta+1 继续处理旧仓或取消路径 |",
                        "| Tb明日目标 | 空仓 | 空仓 | 空仓 |",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "2026-07-07_持仓策略.md").write_text(
                "\n".join(
                    [
                        "| 轨道 | 标的 | 2026-07-07（周二） | 2026-07-08（周三） |",
                        "|------|------|------|------|",
                        "| Ta旧仓 | 持仓未输入 | 先确认旧仓 | 确认后再处理 |",
                        "| Tb明日目标 | 华天科技(002185) | 空仓 | Tb+0 明日目标 |",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "2026-07-08_持仓策略.md").write_text(
                "\n".join(
                    [
                        "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                        "|------|------|----------|----------|-------------|------|",
                        "| Ta | 2026-07-03（周五） | 最远复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                        "| Tb | 2026-07-06（周一） | 历史复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |",
                        "| Tc | 2026-07-07（周二） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |",
                        "| Td | 2026-07-08（周三） | 报告日：旧仓进入复核；上一份日报目标来源=2026-07-07 | 无 | Te不新增参与，B2取消 | 只观察，不新增参与 |",
                        "| Te | 2026-07-09（周四） | 只处理旧仓风险 | 无 | 没有B2；只处理旧仓风险 | 旧仓未修复则继续降风险 |",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "2026-07-08_A股日报_执行摘要.md").write_text(
                "| 明日执行对象 | 无 |\n| 对象性质 | 无明日执行对象 |\n| 旧仓处理 | 持有华天科技(002185)，100%仓位，上一份日报明日标的默认1x旧仓 |\n",
                encoding="utf-8",
            )
            report = render_position_strategy_report(
                data={
                    "position_context_provided": True,
                    "execution_stage_context": {
                        "extreme_conviction_list": [
                            {
                                "code": "600584",
                                "name": "长电科技",
                                "sector": "半导体",
                                "planned_participation": {
                                    "buy_window": "09:50-10:10",
                                    "attack_state": "50%",
                                },
                            }
                        ]
                    },
                },
                target_date="2026-07-09",
                positions=[],
                output_root=root,
            )

        self.assertIn("| Ta | 2026-07-06（周一） | 最远复盘日：太极实业(600667) | 太极实业(600667) | 历史路径校对 |", report)
        self.assertIn("| Tb | 2026-07-07（周二） | 历史复盘日：空仓 | - | 不生成B1/B2 |", report)
        self.assertIn("| Tc | 2026-07-08（周三） | 上一交易日路径：华天科技(002185) | 华天科技(002185) | 可能形成B1旧仓 |", report)
        self.assertIn("| Td | 2026-07-09（周四） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 |", report)
        self.assertIn("| Te | 2026-07-10（周五） | 新目标单独看B1，不用旧仓亏损补仓 | 长电科技(600584) |", report)
        self.assertIn("| - | - | - | 今日空仓，无旧仓处理 | 无旧仓处理 |", report)
        td_line = next(line for line in report.splitlines() if line.startswith("| Td |"))
        self.assertNotIn("华天科技(002185)", td_line)
        self.assertNotIn("长电科技(600584)", td_line)

    def test_daily_entry_generates_position_strategy_for_day_order_table_without_positions(self):
        script = textwrap.dedent(
            f"""
            import sys
            import tempfile
            import types
            from pathlib import Path
            from unittest.mock import patch

            sys.path.insert(0, {str(ROOT / "scripts")!r})

            def _stub_module(name, **attrs):
                module = types.ModuleType(name)
                for key, value in attrs.items():
                    setattr(module, key, value)
                return module

            sys.modules.update({{
                "data_collector": _stub_module("data_collector", AShareDataCollector=type("AShareDataCollector", (), {{}})),
                "ths_hot_stock": _stub_module("ths_hot_stock", fetch_ths_hot_stock=lambda *a, **k: [], fetch_hot_stock_with_fallback=lambda *a, **k: []),
                "ths_hot_list": _stub_module("ths_hot_list", fetch_hot_plate=lambda *a, **k: []),
                "tencent_finance_data": _stub_module("tencent_finance_data", TencentFinanceData=type("TencentFinanceData", (), {{}})),
                "xuangubao_intraday": _stub_module("xuangubao_intraday", XuangubaoIntradayAnalyzer=type("XuangubaoIntradayAnalyzer", (), {{}})),
                "limit_up_down_pool": _stub_module("limit_up_down_pool", get_limit_up_pool=lambda *a, **k: ([], set()), get_limit_down_pool=lambda *a, **k: ([], set()), mark_limit_status=lambda *a, **k: {{}}),
                "strong_stock_pool": _stub_module("strong_stock_pool", get_strong_stock_pool=lambda *a, **k: [], analyze_strong_stocks_by_sector=lambda *a, **k: {{}}),
                "data_validator": _stub_module("data_validator", DataValidator=type("DataValidator", (), {{}})),
                "quantitative_analyzer": _stub_module(
                    "quantitative_analyzer",
                    VolumeAnomalyDetector=type("VolumeAnomalyDetector", (), {{}}),
                    LHBAnalyzer=type("LHBAnalyzer", (), {{}}),
                    ResonanceAnalyzer=type("ResonanceAnalyzer", (), {{}}),
                    SignalGenerator=type("SignalGenerator", (), {{}}),
                    analyze_volume_anomaly=lambda *a, **k: {{}},
                    analyze_lhb=lambda *a, **k: {{}},
                    calculate_resonance=lambda *a, **k: {{}},
                    generate_trade_signals=lambda *a, **k: {{}},
                ),
                "hot_list_integrated": _stub_module("hot_list_integrated", get_integrated_hot_list=lambda *a, **k: {{}}, analyze_sector_distribution=lambda *a, **k: {{}}),
                "history_cache": _stub_module("history_cache", get_cache=lambda *a, **k: {{}}, HistoryCache=type("HistoryCache", (), {{}})),
                "llm_service": _stub_module("llm_service", get_llm_service=lambda *a, **k: None),
                "pandas": _stub_module(
                    "pandas",
                    DataFrame=lambda rows=None: type(
                        "FakeDataFrame",
                        (),
                        {{"empty": True, "__len__": lambda self: 0}},
                    )(),
                ),
            }})

            import daily_report_entry_demo

            calls = []
            report_output_calls = []
            fake_data = {{
                "data_status": {{"两市成交额": True, "中证全指": True, "成交额排名": True}},
                "total_turnover": 12345.67,
                "wind_a_alternative": {{"price": 6686.86, "data_source": "tushare.index_daily"}},
                "turnover_rank": [{{"code": "000001", "data_source": "tushare.daily"}}],
                "module_logs": [],
                "final_target_resolution": {{
                    "new_entry_target": {{
                        "name": "军工一号",
                        "code": "000001",
                        "sector": "国防军工",
                        "planned_participation": {{"buy_window": "09:50-10:10", "attack_state": "50%"}},
                    }}
                }},
                "execution_stage_context": {{
                    "extreme_conviction_list": [{{"name": "军工一号", "code": "000001"}}],
                    "selection_workflow": {{
                        "final": {{
                            "execution_object": {{"name": "军工一号", "code": "000001", "sector": "国防军工"}},
                            "position_pct": 50,
                            "action_text": "50%条件执行",
                        }}
                    }},
                }},
            }}

            def _capture_report_outputs(*args, **kwargs):
                report_output_calls.append(kwargs)
                return {{"full": "# full", "summary": "# summary"}}

            report_tmp = tempfile.TemporaryDirectory(prefix="daily-report-save-readback-")
            report_root = Path(report_tmp.name)

            def _save_report_outputs(outputs, *args, **kwargs):
                full_path = report_root / "full.md"
                full_path.write_text(outputs["full"], encoding="utf-8")
                return {{"full": full_path}}

            with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-19", "--replay"]), \\
                 patch.object(daily_report_entry_demo, "replay_from_snapshot", return_value=(fake_data, "2026-05-19")), \\
                 patch.object(daily_report_entry_demo, "build_report_preflight", return_value={{"failures": []}}), \\
                 patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \\
                 patch.object(daily_report_entry_demo, "analyze_position_management", side_effect=AssertionError("private position report must not be appended to daily report")), \\
                 patch.object(daily_report_entry_demo, "build_report_outputs", side_effect=_capture_report_outputs), \\
                 patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=_save_report_outputs), \\
                 patch.object(daily_report_entry_demo, "_audit_generated_report_with_chanlun_html"), \\
                 patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", return_value=Path("/tmp/full.html")), \\
                 patch.object(daily_report_entry_demo, "_save_data_snapshot"), \\
                 patch.object(daily_report_entry_demo, "save_position_strategy_report", side_effect=lambda report, date, mode: calls.append((report, date, mode)) or "/tmp/strategy.md"):
                exit_code = daily_report_entry_demo.main()

            assert exit_code == 0
            assert len(report_output_calls) == 1
            assert report_output_calls[0].get("has_personal_positions") is False
            assert report_output_calls[0].get("position_report_text", "") == ""
            assert "personal_position_context" not in fake_data
            assert len(calls) == 1
            assert calls[0][1:] == ("2026-05-19", "replay")
            assert calls[0][0].startswith("| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |")
            assert "```mermaid" not in calls[0][0]
            assert "| Td | 2026-05-19（周二） |" in calls[0][0]
            assert "| Te | 2026-05-20（周三） |" in calls[0][0]
            assert "先确认是否已有B1；未确认不新增B2" in calls[0][0]
            report_tmp.cleanup()
            """
        )

        result = subprocess.run([sys.executable, "-c", script], cwd=str(ROOT), capture_output=True, text=True)

        self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
