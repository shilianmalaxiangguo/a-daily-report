import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.front_page_v2_renderer import render_front_page_v2


class FrontPageV2RendererTest(unittest.TestCase):
    def test_front_page_surfaces_monthly_rhythm_position_grade_and_month_return(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-12",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "机器人"},
                    "position_decision": {
                        "signal_grade": "A-",
                        "target_position_pct": 50,
                        "full_attack_ready": False,
                        "sizing_reason": "唯一对象未完成A档确认，先按A-执行。",
                        "monthly_rhythm": {
                            "month_mode": "ordinary_attack",
                            "target_role": "attack_prepare",
                            "month_return_pct": 6.8,
                            "profit_cushion_pct": 10.0,
                            "max_position_pct": 50,
                            "allow_full_attack": False,
                            "profit_cushion": False,
                            "trend_invalid": False,
                            "reason": "处于进攻准备期，先允许A-以下参与，不开放A级满仓/重仓。",
                        },
                    },
                },
            )
        )

        self.assertIn("### 月度攻防与仓位等级", rendered)
        self.assertIn("| 本月模式 | 普通进攻月 |", rendered)
        self.assertIn("| 当月收益 | +6.80% |", rendered)
        self.assertIn("| 盈利垫 | 未触发（阈值+10.00%） |", rendered)
        self.assertIn("| 仓位攻击等级 | A-档50% |", rendered)
        self.assertIn("| 明日最大仓位 | 50% |", rendered)
        self.assertIn("| 收益处理 | 未到盈利垫，按仓位攻击等级执行 |", rendered)

    def test_front_page_maps_position_attack_grade_to_fixed_position_slabs(self):
        cases = [
            ("C", 0, "C档0%"),
            ("B", 30, "B档30%"),
            ("A-", 50, "A-档50%"),
            ("A", 100, "A档80%-100%"),
        ]

        for signal_grade, target_position_pct, expected_label in cases:
            with self.subTest(signal_grade=signal_grade):
                rendered = "\n".join(
                    render_front_page_v2(
                        [],
                        target_date="2026-05-12",
                        market_research_snapshot={
                            "position_decision": {
                                "signal_grade": signal_grade,
                                "target_position_pct": target_position_pct,
                                "monthly_rhythm": {"max_position_pct": target_position_pct},
                            },
                        },
                    )
                )

                self.assertIn(f"| 仓位攻击等级 | {expected_label} |", rendered)

    def test_front_page_renders_position_state_machine_across_front_sections(self):
        cases = [
            (
                "C",
                0,
                {},
                "C档0% / 仅观察",
                "C档无对象",
                "C档0%观察",
                "C档：不满足就空仓",
            ),
            (
                "B",
                30,
                {"allow_conditional_30": True, "can_new_entry": False, "should_reduce": False},
                "B档30% / 10点确认后条件试错",
                "B档有条件试错对象",
                "B档30%条件试错",
                "B档：不满足不开",
            ),
            (
                "A-",
                50,
                {"can_new_entry": True},
                "A-档50% / 唯一对象执行",
                "A-档唯一执行对象",
                "A-档50%执行",
                "A-档：只看唯一对象",
            ),
            (
                "A",
                100,
                {"can_new_entry": True},
                "A档80%-100% / 买定离手",
                "A档唯一核心对象",
                "A档80%-100%买定离手",
                "A档：唯一核心对象确认后80%-100%买定离手",
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
                                "full_attack_ready": grade == "A",
                                "monthly_rhythm": {
                                    "month_mode": "ordinary_attack",
                                    "max_position_pct": target_position_pct,
                                },
                            },
                        },
                        final_gate=final_gate,
                        position_level="三档（进攻档）" if grade in ("A-", "A") else "",
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
        self.assertIn("| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 60分钟确认未同时满足 | 不做 |", rendered)

    def test_b_grade_without_unique_target_renders_as_condition_waiting_not_object_ready(self):
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
                        "signal_grade": "B",
                        "target_position_pct": 30,
                        "monthly_rhythm": {"month_mode": "earnings_defense", "max_position_pct": 30},
                    },
                },
                final_gate={"allow_conditional_30": True, "can_new_entry": False, "should_reduce": False},
                position_level="二档（防守档）",
            )
        )

        self.assertIn("| 唯一对象 | 暂无 |", rendered)
        self.assertIn("| 当前状态 | B档条件等待 |", rendered)
        self.assertNotIn("| 当前状态 | B档有条件试错对象 |", rendered)
        self.assertIn("| B档防守观察，10点确认后才评估30%条件试错 |", rendered)

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
        self.assertIn("| 今日不买原因 | 60分钟确认未完成 |", stock_section)
        self.assertIn("| 明日触发 | 10点确认；主线承接 |", stock_section)
        self.assertIn("| 明日失效 | 主线回落；跌破关键位 |", stock_section)
        self.assertIn("### 2. 备用观察", stock_section)
        self.assertIn("| 富瀚微(300613) | 半导体 | 主线备选 | 10点确认承接 | 跌破关键位 |", stock_section)
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
        self.assertIn("| 触发条件 | 10点后主线继续放量；候选股完成60分钟确认 |", rendered)
        self.assertIn("| 失败条件 | 主线回落；候选股承接失败 |", rendered)
        self.assertIn("| 排除对象 | 富瀚微(300613)：60分钟确认未完成 |", rendered)
        self.assertIn("| 推理深度 | xhigh |", rendered)
        self.assertNotIn("| 置信度 | medium |", rendered)
        self.assertNotIn("chain-of-thought", rendered)
        self.assertNotIn("思维链", rendered)

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
        reasoning_section = rendered[rendered.index("### 0. 推理裁决") : rendered.index("| 明日唯一动作 |")]
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
                        "conclusion": "只看富瀚微，满足确认才允许条件试错。",
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
        self.assertIn(f"| 只看唯一对象 | {expected_label} | 主线确认 + 承接 + 60分钟确认 | 不做 |", rendered)
        self.assertIn(
            f"| B档防守观察，10点确认后才评估30%条件试错 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | {expected_label} | B档30% / 10点确认后条件试错 |",
            rendered,
        )
        self.assertIn("| B档30% / 10点确认后条件试错 |", rendered)
        self.assertIn("B档不是绝对空仓；B档：不满足不开", rendered)

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
        self.assertIn(f"| 只看唯一对象 | {expected_label} | 主线确认 + 承接 + 60分钟确认 | 不做 |", rendered)
        for line in rendered.splitlines():
            if line.startswith("| 只看唯一对象 |") or line.startswith("| B档防守观察"):
                self.assertNotIn("AI|端侧", line)

    def test_reasoning_conditional_entry_without_clear_handoff_stays_c_grade(self):
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

        self.assertIn("| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 60分钟确认未同时满足 | 不做 |", rendered)
        self.assertIn("| C档观察，不开新仓 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | C档0% / 仅观察 |", rendered)
        self.assertNotIn("| B档30% / 10点确认后条件试错 |", rendered)

    def test_conditional_defense_final_summary_does_not_collapse_to_empty_style(self):
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
                    "allow_conditional_30": True,
                    "should_reduce": False,
                    "final_action": "防守观察，只看主线核心；09:50-10:10完成10点确认后才评估30%条件试错，否则不开新仓",
                },
                position_level="二档（防守档）",
            )
        )

        self.assertIn("| B档防守观察，10点确认后才评估30%条件试错 |", rendered)
        self.assertNotIn("| 防守观察，只看主线核心；09:50-10:10完成10点确认后才评估30%条件试错，否则不开新仓 |", rendered)
        self.assertIn("| B档30% / 10点确认后条件试错 |", rendered)
        self.assertIn("B档不是绝对空仓", rendered)
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
        self.assertIn("| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 60分钟确认未同时满足 | 不做 |", rendered)
        self.assertIn("| C档观察，不开新仓 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | C档0% / 仅观察 |", rendered)

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
        self.assertIn("| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 60分钟确认未同时满足 | 不做 |", rendered)
        self.assertIn("| C档观察，不开新仓 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | C档0% / 仅观察 |", rendered)

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
                self.assertIn("| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 60分钟确认未同时满足 | 不做 |", rendered)
                self.assertIn("| C档观察，不开新仓 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | C档0% / 仅观察 |", rendered)

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

    def test_market_fit_embeds_in_existing_sections_without_standalone_modules(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "## 二、市场基底",
                    "### 1. 指数与市场底色",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "| 上证指数 | 4079.90 | -0.33% | 震荡修复 |",
                    "### 2. 市场状态结论",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    "| 市场状态 | 收缩防守 |",
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
                final_gate={"can_new_entry": False, "allow_conditional_30": True, "final_action": "观察，等10点确认"},
                position_level="轻仓",
            )
        )

        self.assertIn("| 市场贴合度 | 主线有效，池子偏窄 |", rendered)
        self.assertIn("强势样本集中半导体", rendered)
        self.assertIn("| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |", rendered)
        turnover_section = rendered[rendered.index("### 5. 主线成交额占比趋势") :]
        self.assertLess(turnover_section.index("2026-04-23"), turnover_section.index("2026-04-24"))
        front_stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        self.assertNotIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", front_stock_section)
        self.assertIn("| 唯一对象 | 300613 富瀚微 |", front_stock_section)
        self.assertIn("| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |", rendered)
        self.assertIn("| 只看唯一对象 | 300613 富瀚微 | 主线确认 + 承接 + 60分钟确认 | 不做 |", rendered)
        for forbidden in ("## 市场贴合度校准", "## 大阳线与承接", "## 主力画图", "执行权", "闸门", "门控", "开闸", "放行"):
            self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()
