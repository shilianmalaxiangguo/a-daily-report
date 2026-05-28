import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from report.front_page_v2_renderer import render_front_page_v2


class FrontPageV2RendererTest(unittest.TestCase):
    def test_front_page_surfaces_monthly_rhythm_position_grade_and_month_return(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-12",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "机器人"},
                    "unique_action_target": {
                        "name": "机器人一号",
                        "code": "000001",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "full_attack_ready": False,
                        "sizing_reason": "唯一对象未完成100%核心确认，先按50%标准进攻。",
                        "monthly_rhythm": {
                            "month_mode": "ordinary_attack",
                            "target_role": "attack_prepare",
                            "month_return_pct": 6.8,
                            "profit_cushion_pct": 10.0,
                            "max_position_pct": 50,
                            "allow_full_attack": False,
                            "profit_cushion": False,
                            "trend_invalid": False,
                            "reason": "处于进攻准备期，先按50%标准进攻，不开放100%核心进攻。",
                        },
                    },
                },
            )
        )

        self.assertIn("### 月度攻防与进攻仓位", rendered)
        self.assertIn("| 本月模式 | 普通进攻月 |", rendered)
        self.assertIn("| 当月收益 | +6.80% |", rendered)
        self.assertIn("| 盈利垫 | 未触发（阈值+10.00%） |", rendered)
        self.assertIn("| 进攻仓位三态 | 50% |", rendered)
        self.assertIn("| 明日最大仓位 | 50% |", rendered)
        self.assertIn("| 收益处理 | 未到盈利垫，按进攻仓位三态执行 |", rendered)

    def test_front_page_does_not_render_missing_month_return_as_zero(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-20",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "unique_action_target": {
                        "name": "晶方科技",
                        "code": "603005",
                        "condition": "固定交易窗口条件",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "monthly_rhythm": {
                            "month_mode": "attack_prepare",
                            "month_return_pct": None,
                            "month_return_source": "missing",
                            "profit_cushion_pct": 10.0,
                            "profit_cushion": False,
                            "max_position_pct": 50,
                        },
                    },
                },
            )
        )

        self.assertIn("| 当月收益 | 未记录 |", rendered)
        self.assertIn("| 盈利垫 | 未记录（阈值+10.00%） |", rendered)
        self.assertNotIn("| 当月收益 | +0.00% |", rendered)

    def test_front_page_execution_plan_uses_layered_participation_windows(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-12",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "unique_action_target": {
                        "name": "大唐发电",
                        "code": "601991",
                        "condition": "竞价表态 + 回封参与 + 失效价清楚",
                    },
                    "position_decision": {
                        "signal_grade": "100",
                        "target_position_pct": 100,
                        "full_attack_ready": True,
                        "monthly_rhythm": {"max_position_pct": 100},
                    },
                },
            )
        )

        self.assertIn("竞价表态", rendered)
        self.assertIn("开盘前几分钟", rendered)
        self.assertIn("回封参与", rendered)
        self.assertIn("09:50-10:10窗口处理买卖", rendered)
        self.assertIn("09:50-10:10", rendered)
        self.assertIn("14:30-14:55", rendered)
        self.assertNotIn("买点等60分钟", rendered)
        self.assertNotIn(_m("满足60分钟确认", "才允许"), rendered)
        self.assertNotIn("60分钟确认", rendered)
        self.assertNotIn("09:50-10:10确认", rendered)

    def test_front_page_execution_plan_keeps_participation_to_fixed_time_windows(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "unique_action_target": {
                        "name": "富瀚微",
                        "code": "300613",
                        "participation_window": "60分钟确认",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "monthly_rhythm": {"max_position_pct": 50},
                    },
                },
            )
        )

        self.assertIn(
            "| 只看唯一对象 | 300613 富瀚微 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口 | 不满足回到0% |",
            rendered,
        )
        self.assertIn("| 09:30-09:35 |", rendered)
        self.assertIn("| 09:50-10:10 |", rendered)
        self.assertIn("| 14:30-14:55 |", rendered)
        self.assertNotIn("60分钟确认", rendered)

    def test_front_page_unique_action_prefers_structured_required_steps(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-12",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "unique_action_target": {
                        "name": "大唐发电",
                        "code": "601991",
                        "participation_window": "竞价表态 + 回封参与",
                        "participation_window_type": "auction_reseal",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                        "required_steps": ["竞价表态", "开盘前几分钟承接", "回封/打板"],
                        "fallback_state": "不满足回到0%",
                    },
                    "position_decision": {
                        "signal_grade": "100",
                        "target_position_pct": 100,
                        "monthly_rhythm": {"max_position_pct": 100},
                    },
                },
            )
        )

        self.assertIn("| 只看唯一对象 | 601991 大唐发电 | 09:30-09:35 | 竞价表态 / 开盘前几分钟承接 / 回封/打板 | 不满足回到0% |", rendered)
        self.assertNotIn("| 只看唯一对象 | 601991 大唐发电 | 竞价表态 + 回封参与 | 主线确认 + 承接 + 60分钟确认 | 不做 |", rendered)

    def test_front_page_unique_action_uses_window_type_over_legacy_condition(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-12",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "unique_action_target": {
                        "name": "大唐发电",
                        "code": "601991",
                        "participation_window": "竞价表态 + 回封参与",
                        "participation_window_type": "auction_reseal",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                    "position_decision": {
                        "signal_grade": "100",
                        "target_position_pct": 100,
                        "monthly_rhythm": {"max_position_pct": 100},
                    },
                },
            )
        )

        self.assertIn("| 只看唯一对象 | 601991 大唐发电 | 09:30-09:35 | 竞价表态 / 开盘前几分钟承接 / 回封/打板 | 不满足回到0% |", rendered)
        self.assertNotIn("| 只看唯一对象 | 601991 大唐发电 | 竞价表态 + 回封参与 | 主线确认 + 承接 + 60分钟确认 | 不做 |", rendered)

    def test_front_page_renders_dragon_pullback_second_confirmation(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-24",
                market_research_snapshot={
                    "dragon_pullback_review": {
                        "leader": "华电辽能",
                        "second_confirmation": True,
                        "laggard_feedback": ["京能电力", "大唐发电"],
                    }
                },
            )
        )

        self.assertIn("| 龙头回头复核 | 华电辽能二次确认；京能电力、大唐发电低位补涨反哺核心辨识度 |", rendered)
        self.assertIn("龙头第一波后的回撤只算观察，第二波顶住压力且低位补涨同步，才说明市场继续投票", rendered)

    def test_front_page_current_mainline_fields_downgrade_when_attack_evidence_is_chaotic(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-14",
                market_research_snapshot={
                    "target_date": "2026-05-14",
                    "current_mainline_history_record": {"date": "2026-05-14", "primary_mainline": "半导体", "market_state": "观察"},
                    "recent_mainline_history": [{"date": "2026-05-13", "primary_mainline": "电力", "market_state": "观察"}],
                    "pivot_mainline_rows": [
                        {
                            "date_range": "05-14",
                            "pivot_level": "日线中枢",
                            "pivot_range": "-",
                            "position": "中枢内",
                            "mainline": "半导体",
                            "mainline_degree": "周期主线",
                            "evolution": "观察",
                            "replacement": "接替电力",
                            "interpretation": "中枢是主线周期载体：[半导体] 承载在日线中枢，主线程度是周期主线，当前演化为观察；接替电力，动作上先看承接是否稳定。",
                        }
                    ],
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
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
                },
            )
        )

        self.assertIn("| 05-14 | 日线中枢 | - | 中枢内 | 暂无确认主线 | 待确认 | 观察 | 待确认 | 中枢只记录候选方向，不把单日热度升级为周期主线；多方向局部活跃但资金未明显胜出。 |", rendered)
        self.assertIn("| 2026-05-14 | 半导体 | 半导体 | 4206.70亿 | 33880.86亿 | 12.4% | 待累计 | 主线成交额占比可用，继续观察占比抬升或回落 |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 暂无确认主线 | 暂无确认主攻线 |", rendered)
        self.assertNotIn("| 05-14 | 日线中枢 | - | 中枢内 | 半导体 | 周期主线 |", rendered)
        self.assertNotIn("| 2026-05-14 | 暂无确认主线 | 暂无确认主攻线 | 4206.70亿", rendered)
        self.assertNotIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 |", rendered)

    def test_front_page_maps_position_attack_grade_to_fixed_position_slabs(self):
        cases = [
            ("0", 0, "0%"),
            ("50", 50, "50%"),
            ("100", 100, "100%"),
        ]

        for signal_grade, target_position_pct, expected_label in cases:
            with self.subTest(signal_grade=signal_grade):
                rendered = "\n".join(
                    render_front_page_v2(
                        [],
                        target_date="2026-05-12",
                        market_research_snapshot={
                            "unique_action_target": {"name": "机器人一号", "code": "000001"},
                            "position_decision": {
                                "signal_grade": signal_grade,
                                "target_position_pct": target_position_pct,
                                "monthly_rhythm": {"max_position_pct": target_position_pct},
                            },
                        },
                    )
                )

                self.assertIn(f"| 进攻仓位三态 | {expected_label} |", rendered)

    def test_front_page_renders_position_state_machine_across_front_sections(self):
        cases = [
            (
                "0",
                0,
                {},
                "0% / 不参与",
                "0%无合格标的",
                "0%不参与",
                "0%：条件不满足",
            ),
            (
                "50",
                50,
                {"allow_attack_50_ready": True, "can_new_entry": False, "should_reduce": False},
                "50% / 标准进攻",
                "50%标准进攻对象",
                "50%标准进攻",
                "50%：只做合格对象",
            ),
            (
                "100",
                100,
                {"can_new_entry": True},
                "100% / 核心进攻",
                "100%唯一核心对象",
                "100%核心进攻",
                "100%：唯一核心对象确认后进攻",
            ),
        ]
        for grade, target_position_pct, final_gate, execution_style, stock_state, discipline, action_text in cases:
            with self.subTest(grade=grade):
                rendered = "\n".join(
                    render_front_page_v2(
                        [],
                        target_date="2026-05-12",
                        market_research_snapshot={
                            "mainline_turnover_summary": {"current_mainline": "机器人"},
                            "unique_action_target": {
                                "name": "机器人一号",
                                "code": "000001",
                                "condition": "主线确认 + 承接 + 60分钟确认",
                            },
                            "position_decision": {
                                "signal_grade": grade,
                                "target_position_pct": target_position_pct,
                                "full_attack_ready": grade == "100",
                                "monthly_rhythm": {
                                    "month_mode": "ordinary_attack",
                                    "max_position_pct": target_position_pct,
                                },
                            },
                        },
                        final_gate=final_gate,
                        position_level="三档（进攻档）" if grade in ("50", "100") else "",
                    )
                )

                self.assertIn(f"| 当前状态 | {stock_state} |", rendered)
                self.assertIn(f"| {discipline} |", rendered)
                self.assertIn(f"| {execution_style} |", rendered)
                self.assertIn(action_text, rendered)
                self.assertNotIn("| 空仓 / 短线确认 |", rendered)

    def test_candidate_section_uses_observation_title_when_unique_target_is_empty(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "|------|------|----------|--------------|-----------|------|----------|----------|",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |",
                ],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                    },
                },
            )
        )

        self.assertIn("### 1. 个股裁决", rendered)
        front_stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        self.assertIn("| 唯一对象 | 暂无 |", front_stock_section)
        self.assertIn("| 今日不买原因 | 没有唯一对象，完整候选仅保留在附录和快照 |", front_stock_section)
        self.assertNotIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", front_stock_section)
        self.assertIn("| 只看唯一对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)

    def test_50_state_without_unique_target_falls_back_to_zero_not_condition_waiting(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "candidate_snapshot": {
                        "front_page": {
                            "unique_object": "暂无",
                            "backup_text": "富瀚微(300613)",
                            "no_buy_reason": "等待10点确认",
                            "trigger_condition": "10点确认；主线承接",
                            "failure_condition": "主线回落",
                        }
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "monthly_rhythm": {"month_mode": "earnings_defense", "max_position_pct": 50},
                    },
                },
                final_gate={"allow_attack_50_ready": True, "can_new_entry": False, "should_reduce": False},
                position_level="二档（防守档）",
            )
        )

        self.assertIn("| 唯一对象 | 暂无 |", rendered)
        self.assertIn("| 当前状态 | 0%无合格标的 |", rendered)
        self.assertNotIn("B档", rendered)
        self.assertIn("| 0%不参与 |", rendered)

    def test_front_page_uses_extreme_conviction_target_as_tomorrow_action_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-19",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "通信设备"},
                    "selected_position_candidate": {
                        "name": "汇源通信",
                        "code": "000586",
                        "sector": "通信设备",
                        "source_tier": "extreme_conviction",
                        "participation_window": "竞价表态 + 回封参与",
                        "participation_window_type": "auction_reseal",
                        "required_steps": ["竞价表态", "开盘前几分钟承接", "回封/打板"],
                        "fallback_state": "条件不满足回到0%",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "participation_mode": "attack_50_preview",
                        "monthly_rhythm": {"month_mode": "ordinary_attack", "max_position_pct": 50},
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="一档（空仓档）",
            )
        )

        self.assertIn("| 唯一对象 | 000586 汇源通信（通信设备） |", rendered)
        self.assertIn("| 当前状态 | 50%标准进攻对象 |", rendered)
        self.assertIn("| 只看唯一对象 | 000586 汇源通信（通信设备） | 09:30-09:35 | 竞价表态 / 开盘前几分钟承接 / 回封/打板 | 条件不满足回到0% |", rendered)
        self.assertIn("| 50%标准进攻", rendered)
        self.assertNotIn("| 唯一对象 | 暂无 |", rendered)

    def test_countertrend_attack_market_keeps_unique_target_observation_only(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "人形机器人",
                        "share_trend_label": "逆势试攻",
                        "conclusion": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理",
                    },
                    "state_machine": {
                        "style_label": "放量杀跌",
                        "primary_action": "先防踩踏，等指数图形和主攻线承接同时修复后再给买入资格。",
                    },
                    "selected_position_candidate": {
                        "name": "华微电子",
                        "code": "600360",
                        "sector": "半导体",
                        "source_tier": "extreme_conviction",
                        "participation_window": "09:50-10:10",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                },
                final_gate={"can_new_entry": False, "allow_attack_50_ready": True, "should_reduce": True},
                position_level="一档（空仓档）",
            )
        )

        self.assertIn("| 唯一对象 | 暂无 |", rendered)
        self.assertIn("| 当前状态 | 0%无合格标的 |", rendered)
        self.assertIn("| 只看唯一对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 人形机器人 | 人形机器人 | 先看市场基底 | 暂无 | 0% / 不参与 |", rendered)
        self.assertNotIn("50%标准进攻对象", rendered)
        self.assertNotIn("50%标准进攻，只做预演命中的合格对象", rendered)

    def test_zero_participation_surfaces_selected_candidate_as_conditional_observation(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-22",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "元器件"},
                    "selected_position_candidate": {
                        "name": "风华高科",
                        "code": "000636",
                        "sector": "元器件",
                        "source_tier": "extreme_conviction",
                        "participation_window": "09:50-10:10",
                        "condition": "09:50-10:10站上37.62，且元器件/PCB链承接不塌",
                        "fallback_state": "不满足继续0%",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="一档（空仓档）",
            )
        )

        self.assertIn("| 唯一对象 | 条件观察：000636 风华高科（元器件） |", rendered)
        self.assertIn("| 当前状态 | 0%条件观察 |", rendered)
        self.assertIn(
            "| 只看条件观察对象 | 000636 风华高科（元器件） | 09:50-10:10 | 09:50-10:10站上37.62，且元器件/PCB链承接不塌 | 不满足继续0% |",
            rendered,
        )
        self.assertIn(
            "| 0%不参与 | 不确定时不值得主动参与 | 元器件 | 元器件 | 先看市场基底 | 条件观察：000636 风华高科（元器件） | 0% / 不参与 | 盘前0%；只看000636 风华高科（元器件），09:50-10:10站上37.62，且元器件/PCB链承接不塌成立才执行条件50%标准进攻；不满足继续0% |",
            rendered,
        )
        self.assertNotIn("| 补位对象 | 风华高科", rendered)
        self.assertNotIn("| 只看唯一对象 | 暂无 |", rendered)

    def test_front_page_t0_card_caps_20260526_style_candidates(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                    "candidate_snapshot": {
                        "front_page": {
                            "backup_watch": [
                                {"label": "步步高(002251)", "sector": "超市连锁"},
                                {"label": "大众公用(600635)", "sector": "供气供热"},
                                {"label": "红星发展(600367)", "sector": "化工原料"},
                            ]
                        },
                        "extreme_conviction_list": [
                            {
                                "name": "步步高",
                                "code": "002251",
                                "sector": "超市连锁",
                                "sniper_role": "旧主买说法",
                            },
                            {
                                "name": "大众公用",
                                "code": "600635",
                                "sector": "供气供热",
                                "sniper_role": "旧补位说法",
                            },
                        ],
                    },
                },
            )
        )

        self.assertLess(rendered.index("## 明日账户建议"), rendered.index("## 一、交易纪律"))
        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；无昨日持仓先看T0对象 |", account_section)
        self.assertIn("| 明日动作 | 不新开，只做条件观察 |", account_section)
        self.assertIn("| T0主对象 | 华天科技(002185)：条件观察 |", account_section)
        self.assertIn("| T0备用 | 暂无 |", account_section)
        self.assertIn("| 新开仓上限 | 0 |", account_section)
        self.assertIn("| 今日不看 | T1/T2/T3只放附录观察，不同时盯多只，不为多个名单分散资金 |", account_section)
        self.assertNotIn("步步高", account_section)
        self.assertNotIn("大众公用", account_section)
        self.assertNotIn("红星发展", account_section)

    def test_front_page_t0_card_uses_final_action_state_for_new_entry_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "unique_action_target": {"name": "大唐发电", "code": "601991", "sector": "电力"},
                },
                final_gate={"can_new_entry": True},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 明日动作 | 只看T0对象，条件满足才新开一手 |", account_section)
        self.assertIn("| T0主对象 | 大唐发电(601991)：固定交易窗口条件 |", account_section)
        self.assertIn("| 新开仓上限 | 1 |", account_section)
        self.assertIn("| 50%标准进攻 |", rendered)

    def test_front_page_t0_card_prioritizes_existing_position(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "已有昨日持仓晶方科技(603005)，先按持仓预案处理",
                    },
                    "selected_position_candidate": {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；已有昨日持仓优先处理 |", account_section)
        self.assertIn("| 明日动作 | 先处理旧仓，不为新候选分散资金 |", account_section)
        self.assertIn("| T0主对象 | 已有昨日持仓晶方科技(603005)，先按持仓预案处理 |", account_section)
        self.assertIn("| T0备用 | 华天科技(002185)：仅作条件观察 |", account_section)
        self.assertIn("| 新开仓上限 | 0 |", account_section)

    def test_front_page_t0_card_shows_position_decision_for_real_small_account_holding(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "account_profile": {
                        "capital_text": "1w本金；总资产10126.52；当日盈利126.52（+1.27%）",
                    },
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有晶方科技(603005)1手，成本43.835；先看45.10能否守住，跌破42.84~43.05或09:50-10:10收不回先卖；新开仓0手",
                    },
                    "selected_position_candidate": {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 1w本金；总资产10126.52；当日盈利126.52（+1.27%）；已有昨日持仓优先处理 |", account_section)
        self.assertIn("| 明日动作 | 先处理旧仓，不为新候选分散资金 |", account_section)
        self.assertIn(
            "| T0主对象 | 持有晶方科技(603005)1手，成本43.835；先看45.10能否守住，跌破42.84~43.05或09:50-10:10收不回先卖；新开仓0手 |",
            account_section,
        )
        self.assertIn("| T0备用 | 华天科技(002185)：仅作条件观察 |", account_section)
        self.assertIn("| 新开仓上限 | 0 |", account_section)

    def test_zero_participation_final_summary_prefers_position_trigger_text(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-25",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "selected_position_candidate": {
                        "name": "新洁能",
                        "code": "605111",
                        "sector": "半导体",
                        "condition": "当前主线处于退潮，环境已转撤退，先退出，等下一轮新脉冲。",
                        "fallback_state": "不满足继续0%",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                        "trigger_text": "09:50-10:10站上63.22且不破60.06",
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="一档（空仓档）",
            )
        )

        self.assertIn(
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 条件观察：605111 新洁能（半导体） | 0% / 不参与 | 盘前0%；只看605111 新洁能（半导体），09:50-10:10站上63.22且不破60.06成立才执行条件50%标准进攻；不满足继续0% |",
            rendered,
        )
        self.assertNotIn("环境已转撤退，先退出", rendered.split("## 七、最终结论", 1)[-1])

    def test_zero_participation_does_not_surface_sniper_rows_as_actionable(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "混沌轮动",
                        "share_trend_label": "放量杀跌",
                    },
                    "candidate_snapshot": {
                        "extreme_conviction_list": [
                            {
                                "name": "豫能控股",
                                "code": "001896",
                                "sector": "火力发电",
                                "sniper_role": "明日主买对象",
                                "leader_speed_tier": "极致加速龙头",
                                "final_risk_review": {"status": "通过"},
                            },
                            {
                                "name": "浙江世宝",
                                "code": "002703",
                                "sector": "汽车配件",
                                "sniper_role": "明日补位对象",
                                "leader_speed_tier": "极致加速龙头",
                                "final_risk_review": {"status": "通过"},
                            },
                        ],
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="一档（空仓档）",
            )
        )

        self.assertIn("| 唯一对象 | 暂无 |", rendered)
        self.assertIn("| 当前状态 | 0%无合格标的 |", rendered)
        self.assertIn("### 2. 明日候选观察", rendered)
        self.assertIn("| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 观察复核 | 观察窗 |", rendered)
        self.assertIn("| 暂无 | - | - | - | - | - | - | - |", rendered)
        self.assertIn("| 只保留唯一对象和备用观察 | 完整候选单保留在结构化快照与附录 | 最终0%时只观察，不做新增参与；观察对象重新成立后再进入明日动作评估 |", rendered)
        self.assertIn("| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |", rendered)
        self.assertNotIn("### 2. 明日主买与补位", rendered)
        self.assertNotIn("| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |", rendered)
        self.assertIn("| 暂无 | - | - | - | - | - | - | - |", rendered)
        self.assertNotIn("001896 豫能控股", rendered)
        self.assertNotIn("002703 浙江世宝", rendered)
        self.assertNotIn("| 明日主买对象 |", rendered)
        self.assertNotIn("| 明日补位对象 |", rendered)
        self.assertIn("| 09:30-09:35 | 只看跌停扩散、主攻线承接和唯一对象是否出现 | 无 | 弱仓/错仓先降风险 | 观察，不抢开盘 |", rendered)
        self.assertNotIn("买后用30分钟结构止损", rendered)
        self.assertNotIn("合格则参与，不合格回到0%", rendered)
        self.assertNotIn("买后用30分钟结构止损", rendered)

    def test_front_page_renders_sniper_primary_backup_speed_and_risk_review(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "selected_position_candidate": {
                        "name": "大唐发电",
                        "code": "601991",
                        "sector": "电力",
                        "source_tier": "extreme_conviction",
                        "participation_window": "竞价表态 + 回封参与",
                        "participation_window_type": "auction_reseal",
                        "required_steps": ["竞价表态", "开盘前几分钟承接", "回封/打板"],
                        "fallback_state": "条件不满足回到0%",
                    },
                    "candidate_snapshot": {
                        "extreme_conviction_list": [
                            {
                                "name": "大唐发电",
                                "code": "601991",
                                "sector": "电力",
                                "sniper_role": "明日主买对象",
                                "leader_speed_tier": "极致加速龙头",
                                "buy_ma_line": "MA3",
                                "sell_ma_line": "MA5",
                                "acceptance_repair_required": "缩量回撤到MA3附近，站回VWAP",
                                "final_risk_review": {"status": "通过"},
                                "participation_window": "竞价表态 + 回封参与",
                            },
                            {
                                "name": "华电辽能",
                                "code": "600396",
                                "sector": "电力",
                                "sniper_role": "明日补位对象",
                                "leader_speed_tier": "大容量趋势龙头",
                                "buy_ma_line": "MA10",
                                "sell_ma_line": "MA20",
                                "acceptance_repair_required": "缩量回撤到MA10附近，站回VWAP",
                                "final_risk_review": {"status": "通过"},
                                "participation_window": "09:50-10:10",
                            },
                        ],
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "participation_mode": "attack_50_preview",
                        "monthly_rhythm": {"month_mode": "ordinary_attack", "max_position_pct": 50},
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="一档（空仓档）",
            )
        )

        self.assertIn("### 2. 明日主买与补位", rendered)
        self.assertIn("| 明日主买对象 | 601991 大唐发电（电力） | 极致加速龙头 | MA3 | MA5 | 缩量回撤到MA3附近，站回VWAP | 通过 | 竞价表态 + 回封参与 |", rendered)
        self.assertIn("| 明日补位对象 | 600396 华电辽能（电力） | 大容量趋势龙头 | MA10 | MA20 | 缩量回撤到MA10附近，站回VWAP | 通过 | 09:50-10:10 |", rendered)

    def test_front_page_reads_sniper_candidates_from_top_level_snapshot_fallback(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "selected_position_candidate": {
                        "name": "大唐发电",
                        "code": "601991",
                        "sector": "电力",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                    "extreme_conviction_list": [
                        {
                            "name": "大唐发电",
                            "code": "601991",
                            "sector": "电力",
                            "sniper_role": "明日主买对象",
                            "leader_speed_tier": "极致加速龙头",
                            "buy_ma_line": "MA3",
                            "sell_ma_line": "MA5",
                            "acceptance_repair_required": "缩量回撤到MA3附近，站回VWAP",
                            "final_risk_review": {"status": "通过"},
                            "participation_window": "竞价表态 + 回封参与",
                        }
                    ],
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="一档（空仓档）",
            )
        )

        self.assertIn("| 明日主买对象 | 601991 大唐发电（电力） | 极致加速龙头 | MA3 | MA5 |", rendered)

    def test_sniper_rows_follow_unique_action_target_when_final_target_differs(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "unique_action_target": {
                        "name": "华微电子",
                        "code": "600360",
                        "sector": "半导体",
                        "participation_window": "09:50-10:10",
                    },
                    "candidate_snapshot": {
                        "extreme_conviction_list": [
                            {
                                "name": "豫能控股",
                                "code": "001896",
                                "sector": "火力发电",
                                "sniper_role": "明日主买对象",
                            },
                            {
                                "name": "浙江世宝",
                                "code": "002703",
                                "sector": "汽车配件",
                                "sniper_role": "明日补位对象",
                            },
                        ]
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="一档（空仓档）",
            )
        )

        self.assertIn("| 只看唯一对象 | 600360 华微电子（半导体） | 09:50-10:10 |", rendered)
        self.assertIn("| 暂无 | - | - | - | - | - | - | - |", rendered)
        self.assertNotIn("001896 豫能控股", rendered)
        self.assertNotIn("002703 浙江世宝", rendered)

    def test_candidate_section_uses_structured_snapshot_summary_and_hides_full_candidate_table(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "|------|------|----------|--------------|-----------|------|----------|----------|",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |",
                ],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "candidate_snapshot": {
                        "front_page": {
                            "unique_object": "暂无",
                            "backup_text": "富瀚微(300613)；华特气体(688268)",
                            "no_buy_reason": "60分钟确认未完成",
                            "trigger_condition": "10点确认；主线承接",
                            "failure_condition": "主线回落；跌破关键位",
                            "backup_watch": [
                                {
                                    "label": "富瀚微(300613)",
                                    "sector": "半导体",
                                    "role": "主线备选",
                                    "trigger_condition": "10点确认承接",
                                    "failure_condition": "跌破关键位",
                                }
                            ],
                        }
                    },
                },
            )
        )

        stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        self.assertIn("### 1. 个股裁决", stock_section)
        self.assertIn("| 备用观察 | 富瀚微(300613)；华特气体(688268) |", stock_section)
        self.assertIn("| 今日不买原因 | 09:50-10:10窗口未完成 |", stock_section)
        self.assertIn("| 明日触发 | 09:50-10:10窗口；主线承接 |", stock_section)
        self.assertIn("| 明日失效 | 主线回落；跌破关键位 |", stock_section)
        self.assertIn("### 2. 明日候选观察", stock_section)
        self.assertIn("| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 观察复核 | 观察窗 |", stock_section)
        self.assertIn("### 3. 备用观察", stock_section)
        self.assertIn("| 富瀚微(300613) | 半导体 | 主线备选 | 09:50-10:10窗口 | 跌破关键位 |", stock_section)
        self.assertNotIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", stock_section)

    def test_front_page_renders_reasoning_decision_without_chain_of_thought(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [
                        {
                            "code": "300613",
                            "name": "富瀚微",
                            "sector": "半导体",
                            "direction": "AI端侧芯片",
                        }
                    ],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "observe",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": None,
                        "conclusion": "主线仍需确认，明天只观察承接。",
                        "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
                        "trigger_conditions": ["10点后主线继续放量", "候选股完成60分钟确认"],
                        "failure_conditions": ["主线回落", "候选股承接失败"],
                        "excluded_candidates": [{"id": "300613", "name": "富瀚微", "reason": "60分钟确认未完成"}],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("### 0. 推理裁决", rendered)
        self.assertNotIn("| 裁决 | observe |", rendered)
        self.assertNotIn("| 主线状态 | strengthening |", rendered)
        self.assertIn("| 结论 | 主线仍需确认，明天只观察承接。 |", rendered)
        self.assertIn("| 关键证据 | 主线为半导体 |", rendered)
        self.assertIn("| 触发条件 | 09:50-10:10主线继续放量；候选股09:50-10:10窗口满足条件 |", rendered)
        self.assertIn("| 失败条件 | 主线回落；候选股承接失败 |", rendered)
        self.assertIn("| 排除对象 | 富瀚微(300613)：09:50-10:10窗口未完成 |", rendered)
        self.assertIn("| 推理深度 | xhigh |", rendered)
        self.assertNotIn("| 置信度 | medium |", rendered)
        self.assertNotIn("chain-of-thought", rendered)
        self.assertNotIn("思维链", rendered)
        self.assertNotIn("60分钟确认", rendered)

    def test_reasoning_decision_surface_sanitizes_forbidden_markers_and_table_breaks(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "observe",
                        "mainline_state": "unclear",
                        "reasoning_effort": "xhigh",
                        "unique_target": None,
                        "conclusion": "思维链：先想A\n再想B | 这段不该破表",
                        "evidence": [{"field": "x", "summary": "chain-of-thought: hidden | draft"}],
                        "trigger_conditions": ["10点确认\n不要换行", "候选|确认"],
                        "failure_conditions": ["主线回落 | 失败"],
                        "excluded_candidates": [{"id": "300613", "name": "富瀚微", "reason": "思维链 泄漏 | 原因"}],
                        "confidence": "medium|bad",
                    },
                },
            )
        )

        self.assertIn("### 0. 推理裁决", rendered)
        self.assertNotIn("思维链", rendered)
        self.assertNotIn("chain-of-thought", rendered)
        reasoning_section = rendered[rendered.index("### 0. 推理裁决") : rendered.index("| 明日观察动作 |")]
        for line in reasoning_section.splitlines():
            if line.startswith("|") and not line.startswith("|------"):
                self.assertEqual(line.count("|"), 3, line)

    def test_reasoning_decision_unique_target_drives_unique_action_when_snapshot_target_is_missing(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [
                        {
                            "code": "300613",
                            "name": "富瀚微",
                            "sector": "半导体",
                            "direction": "AI端侧芯片",
                        }
                    ],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "conditional_entry",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "只看富瀚微，满足确认才按50%标准进攻。",
                        "handoff_buying_evidence": "clear",
                        "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
                        "trigger_conditions": ["10点后主线继续放量", "富瀚微完成60分钟确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        expected_label = "300613 富瀚微（半导体、AI端侧芯片）"
        self.assertIn(f"| 只看唯一对象 | {expected_label} | 09:50-10:10 | 主线确认 / 承接 / 09:50-10:10窗口 | 不满足回到0% |", rendered)
        self.assertIn(
            f"| 50%标准进攻，只做预演命中的合格对象 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | {expected_label} | 50% / 标准进攻 |",
            rendered,
        )
        self.assertIn("| 50% / 标准进攻 |", rendered)
        self.assertIn("50%：只做合格对象", rendered)

    def test_unique_target_label_keeps_markdown_tables_stable_when_direction_has_table_chars(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [
                        {
                            "code": "300613",
                            "name": "富瀚微",
                            "sector": "半导体",
                            "direction": "AI|端侧\n芯片",
                        }
                    ],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "conditional_entry",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "只看富瀚微。",
                        "handoff_buying_evidence": "clear",
                        "evidence": [],
                        "trigger_conditions": ["10点确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        expected_label = "300613 富瀚微（半导体、AI｜端侧 芯片）"
        self.assertIn(f"| 只看唯一对象 | {expected_label} | 09:50-10:10 | 主线确认 / 承接 / 09:50-10:10窗口 | 不满足回到0% |", rendered)
        for line in rendered.splitlines():
            if line.startswith("| 只看唯一对象 |") or line.startswith("| 50%标准进攻"):
                self.assertNotIn("AI|端侧", line)

    def test_reasoning_conditional_entry_without_clear_handoff_stays_zero_state(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "conditional_entry",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "证据不足，只能观察。",
                        "handoff_buying_evidence": "insufficient",
                        "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
                        "trigger_conditions": ["10点确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("| 只看唯一对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0% / 不参与 |", rendered)
        self.assertNotIn(_m("B档", "30%"), rendered)

    def test_conditional_defense_without_unique_target_renders_zero_state(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "state_machine": {"leading_line": "半导体"},
                    "candidate_snapshot": {
                        "front_page": {
                            "unique_object": "暂无",
                            "backup_text": "富瀚微(300613)",
                            "no_buy_reason": "等待10点确认",
                            "trigger_condition": "10点确认；主线承接",
                            "failure_condition": "主线回落",
                        }
                    },
                },
                final_gate={
                    "can_new_entry": False,
                    "allow_attack_50_ready": True,
                    "should_reduce": False,
                    "final_action": "观察，只看主线核心；09:50-10:10完成10点确认后才评估是否50%标准进攻，否则不参与",
                },
                position_level="二档（防守档）",
            )
        )

        self.assertIn("| 0%不参与 |", rendered)
        self.assertIn("| 09:50-10:10 | 观察市场底色、主线承接、唯一对象强弱 | 无 | 窗口内处理弱仓/错仓 | 条件未同时满足继续0% |", rendered)
        self.assertIn("| 14:30-14:55 | 只判断是否量化电风扇行情 | 无 | 非电风扇不新增参与 | 例外，不是常规 |", rendered)
        self.assertNotIn("10:00左右买", rendered)
        self.assertNotIn("新仓止损", rendered)
        self.assertNotIn("尾盘开新仓", rendered)
        self.assertNotIn(_m("30%", "条件试错"), rendered)
        self.assertNotIn("B档", rendered)
        self.assertNotIn("| 空仓 / 短线确认 |", rendered)

    def test_reasoning_decision_unique_target_only_drives_action_for_conditional_entry(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "observe",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "只观察，不给执行目标。",
                        "evidence": [],
                        "trigger_conditions": ["10点确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("### 1. 个股裁决", rendered)
        self.assertIn("| 只看唯一对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0% / 不参与 |", rendered)

    def test_non_actionable_reasoning_decision_blocks_snapshot_unique_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                    "unique_action_target": {
                        "name": "富瀚微",
                        "code": "300613",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "observe",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "只观察，不给执行目标。",
                        "evidence": [],
                        "trigger_conditions": ["10点确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("### 1. 个股裁决", rendered)
        self.assertNotIn("### 1. 主线内可执行候选", rendered)
        self.assertIn("| 只看唯一对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0% / 不参与 |", rendered)

    def test_empty_or_malformed_reasoning_decision_blocks_snapshot_unique_target(self):
        for reasoning_decision in ({}, "invalid"):
            with self.subTest(reasoning_decision=reasoning_decision):
                rendered = "\n".join(
                    render_front_page_v2(
                        [],
                        target_date="2026-04-24",
                        market_research_snapshot={
                            "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                            "unique_action_target": {
                                "name": "富瀚微",
                                "code": "300613",
                                "condition": "主线确认 + 承接 + 60分钟确认",
                            },
                            "mainline_turnover_summary": {"current_mainline": "半导体"},
                            "reasoning_decision": reasoning_decision,
                        },
                    )
                )

                self.assertIn("### 1. 个股裁决", rendered)
                self.assertNotIn("### 1. 主线内可执行候选", rendered)
                self.assertIn("| 只看唯一对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
                self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0% / 不参与 |", rendered)

    def test_turnover_share_lines_derives_share_change_from_structured_same_mainline_history(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "半导体",
                        "turnover_share_pct": 18.1,
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-23", "sector_name": "半导体", "turnover_share_pct": 15.8},
                    ],
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-04-24",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "2180.00亿",
                                "market_turnover": "12834.00亿",
                                "share": "18.1%",
                                "share_change": "待累计",
                                "interpretation": "主线占比继续抬升",
                            }
                        ],
                    },
                },
            )
        )

        self.assertIn(
            "| 2026-04-24 | 半导体 | 半导体 | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 主线占比继续抬升 |",
            rendered,
        )

    def test_turnover_share_lines_compares_against_previous_day_when_mainline_switches(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "半导体",
                        "turnover_share_pct": 18.1,
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-23", "sector_name": "电力", "turnover_share_pct": 15.8},
                    ],
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-04-24",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "2180.00亿",
                                "market_turnover": "12834.00亿",
                                "share": "18.1%",
                                "share_change": "+2.3pct",
                                "interpretation": "新主线刚切换，先累计半导体自身占比",
                            }
                        ],
                    },
                },
            )
        )

        self.assertIn(
            "| 2026-04-24 | 半导体 | 半导体 | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 新主线刚切换，先累计半导体自身占比 |",
            rendered,
        )
        self.assertNotIn("| 2026-04-24 | 半导体 | 半导体 | 2180.00亿 | 12834.00亿 | 18.1% | 待累计 |", rendered)

    def test_turnover_share_lines_preserve_trend_table_labels_when_current_attack_unconfirmed(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "混沌轮动",
                        "mainline_attack_evidence_summary": {
                            "attack_state": "chaotic_rotation",
                            "primary_line": "",
                            "confirmation_evidence": "多线分散，主攻线尚未胜出",
                        },
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-05-19",
                                "cycle_mainline": "电力",
                                "daily_attack_line": "电力",
                                "mainline_turnover": "665.00亿",
                                "market_turnover": "29089.77亿",
                                "share": "2.3%",
                                "share_change": "+0.6pct",
                                "interpretation": "电力支线轮动，先看回流强度",
                            },
                            {
                                "date": "2026-05-20",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "4050.00亿",
                                "market_turnover": "29764.59亿",
                                "share": "13.6%",
                                "share_change": "+1.5pct",
                                "interpretation": "半导体支线轮动，成交额占比明显抬升",
                            },
                        ],
                    },
                },
            )
        )

        turnover_section = rendered[rendered.index("### 5. 主线成交额占比趋势") :]
        self.assertIn(
            "| 2026-05-19 | 电力 | 电力 | 665.00亿 | 29089.77亿 | 2.3% | +0.6pct | 电力支线轮动，先看回流强度 |",
            turnover_section,
        )
        self.assertIn(
            "| 2026-05-20 | 半导体 | 半导体 | 4050.00亿 | 29764.59亿 | 13.6% | +1.5pct | 半导体支线轮动，成交额占比明显抬升 |",
            turnover_section,
        )
        self.assertNotIn("| 2026-05-20 | 暂无确认主线 | 暂无确认主攻线 | 4050.00亿", turnover_section)

    def test_front_page_replaces_double_mainline_with_capacity_regime_table(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-14",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
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
                        },
                    },
                    "unique_action_target": {
                        "name": "中船特气",
                        "code": "688146",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                },
            )
        )

        self.assertIn("### 4. 主线容量与格局判断", rendered)
        self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
        self.assertIn("| 双线孕育 | 混沌接力 | 半导体 | 电力 / 化学制品 | 半导体高标和涨停更集中，成交占比靠前 | 半导体尝试替代，电力退成背景线待确认 | 半导体启动，电力背景线 | 先看资金是否继续选择半导体；背景线只观察回流 |", rendered)
        self.assertIn("#### 主线攻击证据", rendered)
        self.assertIn("| 板块 | 攻击状态 | 净流入排名 | 净流入 | 涨停数 | 高标高度 | 成交占比变化 | 结论 |", rendered)
        self.assertIn("| 半导体 | 确认主攻线 | 第1 | +45.00亿 | 5 | 4 | +1.6pct | 半导体资金净流入靠前，涨停和高标更集中，成交占比扩张 |", rendered)
        self.assertIn("| 电力 | 候选线 | 第2 | +8.00亿 | 1 | 1 | -0.5pct | 电力仍是候选线，证据不足以确认主攻线 |", rendered)
        self.assertNotIn("### 4. 双层主线结论", rendered)
        self.assertNotIn("| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |", rendered)

    def test_market_fit_embeds_in_existing_sections_without_standalone_modules(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "## 二、市场基底",
                    "### 1. 指数与市场底色",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "| 上证指数 | 4079.90 | -0.33% | 震荡修复 |",
                    "### 2. 市场状态结论",
                    "| 项目 | 结论 | 依据 |",
                    "|------|------|------|",
                    "| 市场状态 | 收缩防守 | 指数弱、跌多涨少 |",
                    "## 三、周期与主线",
                    "**主线内可执行候选**:",
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "|------|------|----------|--------------|-----------|------|----------|----------|",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |",
                    "| 华特气体 | 688268 | 电子化学 | 放量大阳线 | 未完全爆发 | 明日验证承接 | 链内跟随 | 观察 |",
                    "| 股票 | 代码 | 所属方向 | 观察意义 | 明日原则 |",
                    "| 恩捷股份 | 002812 | 电池 | 轮动试探 | 只看强弱，不给买入指令 |",
                ],
                target_date="2026-04-24",
                market_research_snapshot={
                    "market_fit_calibration": {
                        "fit_label": "主线有效，池子偏窄",
                        "evidence_text": "强势样本3只，主线命中2只，观察池命中0只",
                        "cycle_note": "强势样本集中半导体，主线成交额占比抬升时优先看承接",
                        "action_text": "只扩主线内强票池",
                    },
                    "cycle_interpretation_rows": [
                        {
                            "cycle_label": "当前周期",
                            "date_range": "04-21 ~ 04-24",
                            "trading_days": "4日",
                            "mainline": "半导体",
                            "market_state": "修复接力",
                            "interpretation": "半导体接替电力，等待承接确认",
                        }
                    ],
                    "mainline_turnover_summary": {
                        "turnover_share_trend_summary": "近25个交易日主线成交额占比趋势：当前10.0%，区间10.0%-17.5%，主线成交占比回落，先看重新聚焦能否持续。",
                        "double_mainline_summary": {
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "relationship": "周期主线与当天主攻线一致",
                            "tomorrow_action": "继续围绕半导体观察承接",
                        },
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-04-23",
                                "cycle_mainline": "电力",
                                "daily_attack_line": "电力",
                                "mainline_turnover": "2100亿",
                                "market_turnover": "12000亿",
                                "share": "17.5%",
                                "share_change": "-",
                                "interpretation": "上个周期退潮",
                            },
                            {
                                "date": "2026-04-24",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "2638.10亿",
                                "market_turnover": "26414.92亿",
                                "share": "10.0%",
                                "share_change": "抬升",
                                "interpretation": "主线成交额占比抬升，强势样本开始集中",
                            },
                        ],
                    },
                    "unique_action_target": {
                        "name": "富瀚微",
                        "code": "300613",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                },
                final_gate={"can_new_entry": False, "allow_attack_50_ready": True, "final_action": "观察，等10点确认"},
                position_level="轻仓",
            )
        )

        self.assertIn("| 市场贴合度 | 主线有效，池子偏窄 | 强势样本3只，主线命中2只，观察池命中0只 |", rendered)
        market_base = rendered[rendered.index("### 2. 市场状态结论") : rendered.index("## 三、周期与主线")]
        self.assertLess(market_base.index("| 项目 | 结论 | 依据 |"), market_base.index("| 市场贴合度 |"))
        self.assertNotIn("### 2. 市场状态结论\n| 市场贴合度 |", market_base)
        self.assertIn("强势样本集中半导体", rendered)
        self.assertIn("| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |", rendered)
        turnover_section = rendered[rendered.index("### 5. 主线成交额占比趋势") :]
        self.assertIn("> 近25个交易日主线成交额占比趋势：当前10.0%，区间10.0%-17.5%，主线成交占比回落，先看重新聚焦能否持续。", turnover_section)
        self.assertLess(turnover_section.index("2026-04-24"), turnover_section.index("2026-04-23"))
        front_stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        self.assertNotIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", front_stock_section)
        self.assertIn("| 唯一对象 | 300613 富瀚微 |", front_stock_section)
        self.assertIn("| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |", rendered)
        self.assertIn("| 只看唯一对象 | 300613 富瀚微 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口 | 不满足回到0% |", rendered)
        for forbidden in (
            "## 市场贴合度校准",
            "## 大阳线与承接",
            "## 主力画图",
            _m("执行", "权"),
            _m("闸", "门"),
            _m("门", "控"),
            _m("开", "闸"),
            _m("放", "行"),
        ):
            self.assertNotIn(forbidden, rendered)

    def test_front_page_renders_market_structure_before_cycle_section(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "## 二、市场基底",
                    "### 1. 指数与市场底色",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "| 创业板指 | 3914.88 | +1.20% | 强势上涨 |",
                    "### 2. 市场状态结论",
                    "| 项目 | 结论 | 依据 |",
                    "|------|------|------|",
                    "| 市场情绪总状态 | 局部强 | 指数强但涨跌家数偏弱 |",
                ],
                target_date="2026-05-27",
                market_research_snapshot={
                    "market_structure_judgement": {
                        "index_profit_relation": "指数强但真实赚钱效应弱，指数不能代表多数股票体感",
                        "turnover_distribution": "成交额高位但结构集中，不能按普涨支撑处理",
                        "rotation_nature": "消费、白酒更像对立反弹，尚未证明主线切换",
                        "old_mainline_fatigue": "科技仍活跃但短线疲态上升，只保留核心观察",
                        "tomorrow_rhythm": "低频聚焦",
                        "candidate_policy": "只保留主线核心；题材荒时不从旧方向强行扩散候选",
                        "summary_text": "指数强但真实赚钱效应弱；成交额高位但结构集中；明日节奏：低频聚焦",
                        "action_reason_text": "低频聚焦。原因是指数强但真实赚钱效应弱，成交额高位但结构集中。",
                    },
                    "mainline_turnover_summary": {"current_mainline": "科技"},
                },
            )
        )

        self.assertIn("### 3. 市场结构判断", rendered)
        self.assertLess(rendered.index("### 3. 市场结构判断"), rendered.index("## 三、周期与主线"))
        self.assertIn("| 明日节奏 | 低频聚焦；只保留主线核心；题材荒时不从旧方向强行扩散候选 |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 科技 | 科技 | 低频聚焦 |", rendered)
        self.assertIn("低频聚焦。原因是指数强但真实赚钱效应弱，成交额高位但结构集中。", rendered)


if __name__ == "__main__":
    unittest.main()
