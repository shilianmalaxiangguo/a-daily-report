import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


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

    def test_render_includes_ta_tb_tc_timeline_for_old_position_and_tomorrow_target(self):
        from portfolio.position_strategy_report import render_position_strategy_report

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
        )

        self.assertTrue(report.startswith("| 轨道 | 标的 | 2026-06-26（周五） |"))
        self.assertNotIn("```mermaid", report)
        self.assertNotIn("gantt", report)
        self.assertIn("| 轨道 | 标的 | 2026-06-26（周五） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |", report)
        self.assertIn("| Ta旧仓 | 华电辽能 | Ta+0 旧仓占用 | Ta+1 继续处理旧仓 | Ta+2 默认按昨晚预案尾盘卖出；失去持有资格才提前处理 | 空仓 |", report)
        self.assertIn("| Tb明日目标 | 汇源通信(000586) | 空仓 | Tb+0 明日目标 | Tb+1 只按昨晚预案执行或取消 | Tb+2 未执行则回到空仓 |", report)
        self.assertIn("| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 空仓 |", report)
        self.assertIn("第一列是报告日，下一交易日是执行日", report)
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

        self.assertIn("| 轨道 | 标的 | 2026-06-26（周五） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |", report)
        self.assertIn("| Ta旧仓 | 太极实业 | Ta+0 旧仓占用 | Ta+1 继续处理旧仓 | Ta+2 优先处理旧仓，空仓时间尽可能接近全天空仓 | 空仓 |", report)
        self.assertIn("| Tb明日目标 | 空仓 | 空仓 | 没有Tb+0，空仓 | 没有Tb+1，空仓 | 空仓 |", report)
        self.assertIn("| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 空仓 |", report)
        self.assertIn("没有Tb+0/没有Tc+0且只剩Ta+2旧仓时，优先处理旧仓", report)
        self.assertIn("Tb 表示明日目标；Tb+0 是条件买入，不是无条件买入；Tb+1 要继续按昨晚预案处理持有或取消路径；没有明日目标时，必须写明没有Tb+0 / 没有Tb+1。", report)

    def test_render_unknown_position_context_keeps_ta_as_pending(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={
                "position_context_provided": False,
                "selection_workflow": {
                    "final": {
                        "position_pct": 50,
                        "execution_object": {"name": "太极实业", "code": "600667"},
                    }
                },
            },
            target_date="2026-07-03",
            positions=[],
        )

        self.assertIn("| Ta旧仓 | 待确认旧仓 | 先确认旧仓 | 确认后再处理 | 持仓确认后再决定 | 空仓 |", report)
        self.assertIn("持仓未输入时，Ta轨道只表示待确认", report)
        self.assertNotIn("无旧仓时，Ta轨道保持空仓", report)

    def test_render_uses_previous_report_target_and_current_markdown_target_for_timeline(self):
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

        self.assertIn("| 轨道 | 标的 | 2026-06-28（周日） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |", report)
        self.assertIn("| Ta旧仓 | 太极实业(600667) | 上一份日报目标，进入旧仓/旧路径复核 | Ta+1 继续处理旧仓或取消路径 | Ta+2 默认按昨晚预案尾盘卖出；失去持有资格才提前处理 | 空仓 |", report)
        self.assertIn("| Tb明日目标 | 深科技(000021) | 空仓 | 报告日确认明日目标 | Tb+0 条件买入，不是无条件买入 | Tb+1 只按昨晚预案执行或取消 |", report)
        self.assertIn("第一列是上一份日报路径在本轮报告前的占用日", report)

    def test_daily_entry_generates_position_strategy_for_day_order_table_without_positions(self):
        script = textwrap.dedent(
            f"""
            import sys
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
                "execution_stage_context": {{"extreme_conviction_list": [{{"name": "军工一号", "code": "000001"}}]}},
            }}

            def _capture_report_outputs(*args, **kwargs):
                report_output_calls.append(kwargs)
                return {{"full": "# full", "summary": "# summary"}}

            with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-19", "--replay"]), \\
                 patch.object(daily_report_entry_demo, "replay_from_snapshot", return_value=(fake_data, "2026-05-19")), \\
                 patch.object(daily_report_entry_demo, "build_report_preflight", return_value={{"failures": []}}), \\
                 patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \\
                 patch.object(daily_report_entry_demo, "analyze_position_management", side_effect=AssertionError("private position report must not be appended to daily report")), \\
                 patch.object(daily_report_entry_demo, "build_report_outputs", side_effect=_capture_report_outputs), \\
                 patch.object(daily_report_entry_demo, "save_report_outputs", return_value={{}}), \\
                 patch.object(daily_report_entry_demo, "_audit_generated_report_with_chanlun_html"), \\
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
            assert calls[0][0].startswith("| 轨道 | 标的 |")
            assert "```mermaid" not in calls[0][0]
            assert "Tb+0" in calls[0][0]
            assert "Tc+0" in calls[0][0]
            """
        )

        result = subprocess.run([sys.executable, "-c", script], cwd=str(ROOT), capture_output=True, text=True)

        self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
