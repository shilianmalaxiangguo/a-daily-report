import datetime as dt
import html as html_lib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.elimination_tournament import build_elimination_tournament_payload
from report.elimination_tournament import build_sector_capital_preflight_daily_context
from report.elimination_tournament import build_sector_capital_preflight_payload
from report.elimination_tournament import elimination_tournament_html_path
from report.elimination_tournament import render_elimination_tournament_html
from report.elimination_tournament import render_sector_capital_preflight_html
from report.elimination_tournament import sector_capital_preflight_html_path


def _embedded_json_payload(rendered_html, script_id):
    match = re.search(
        rf'<script type="application/json" id="{script_id}">(.*?)</script>',
        rendered_html,
        re.S,
    )
    if not match:
        return {}
    return json.loads(html_lib.unescape(match.group(1)))


class EliminationTournamentPayloadTest(unittest.TestCase):
    def _workflow(self):
        return {
            "schema_version": "selection_workflow.v1",
            "target_date": "2026-06-12",
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
                "source_node": "N8",
                "failure_conditions": ["account_context"],
            },
            "candidate_pool": [
                {
                    "stock": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                    "source_pools": ["extreme_conviction_list"],
                    "entered_reason": "板块锚定龙 / 4连板 / 趋势审美 / 平台呼吸 / 蛇形走位",
                    "entry_basis": "来自市场氛围、板块发酵和板块角色推导",
                    "candidate_origin": "sector_first",
                    "new_entry_qualified": True,
                    "mainline": "化工原料",
                    "sector": "化工原料",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                    "current_reason": "候选就是板块锚，分歧后资金优先回看",
                    "brooks_price_action_judge": {
                        "status": "accepted",
                        "verdict": "资金表态被价格接受",
                        "participation_effect": "进入N7对照，仍需板块同步、账户和时间窗口配合",
                    },
                    "status": "过程候选",
                    "front_observation_qualified": False,
                    "observation_layer": "process_observation",
                    "eliminated_at": "",
                    "eliminated_reason": "候选就是板块锚，分歧后资金优先回看",
                    "workflow_path": ["N5", "N6", "N7", "N8"],
                },
                {
                    "stock": {"name": "蓝箭电子", "code": "301348", "sector": "半导体"},
                    "source_pools": ["extreme_conviction_list"],
                    "entered_reason": "首板 / 趋势审美 / 20日区间位置健康",
                    "entry_basis": "来自市场氛围、板块发酵和板块角色推导",
                    "candidate_origin": "sector_first",
                    "new_entry_qualified": True,
                    "mainline": "半导体",
                    "sector": "半导体",
                    "sector_role": "观察样本",
                    "reversal_decision": "降级观察",
                    "current_reason": "不能替代板块锚；无法说明为什么不做兆易创新(603986)",
                    "brooks_price_action_judge": {
                        "status": "accepted",
                        "verdict": "资金表态被价格接受",
                    },
                    "status": "降级观察",
                    "eliminated_at": "N6",
                    "eliminated_reason": "不能替代板块锚；无法说明为什么不做兆易创新(603986)",
                    "workflow_path": ["N5", "N6", "N7", "N8"],
                },
                {
                    "stock": {"name": "旧记忆股", "code": "000001", "sector": "杂项"},
                    "source_pools": ["热榜"],
                    "entered_reason": "热榜记忆",
                    "entry_basis": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                    "candidate_origin": "legacy_signal_only",
                    "new_entry_qualified": False,
                    "sector": "杂项",
                    "sector_role": "观察样本",
                    "reversal_decision": "",
                    "status": "过程候选",
                    "eliminated_at": "",
                    "workflow_path": ["N5", "N6", "N7", "N8"],
                },
            ],
        }

    def test_payload_has_fixed_layers_and_self_consistent_counts(self):
        payload = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            variant="replay",
            selection_workflow=self._workflow(),
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"}
            },
            position_decision={"target_position_pct": 0},
        )

        self.assertEqual(payload["schema_version"], "elimination_tournament.v1")
        self.assertEqual(
            [layer["id"] for layer in payload["layers"]],
            [
                "sector",
                "sector_role",
                "leader_reverse",
                "price_action",
                "account_execution",
                "final_resolution",
            ],
        )
        for layer in payload["layers"][:-1]:
            self.assertEqual(layer["input_count"], len(layer["entries"]))
            self.assertEqual(
                layer["eliminated_count"],
                sum(1 for item in layer["entries"] if item["status"] == "eliminated"),
            )
            self.assertEqual(
                layer["survivor_count"],
                sum(1 for item in layer["entries"] if item["status"] == "survived"),
            )

    def test_identity_passes_but_risk_layer_eliminates_heyuan(self):
        payload = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            variant="replay",
            selection_workflow=self._workflow(),
            candidate_traces={
                "traces": [
                    {
                        "stock_code": "002971",
                        "stock_name": "和远气体",
                        "missing_data": ["account_context"],
                    }
                ]
            },
            decision_ledger={
                "cases": [
                    {
                        "stock_code": "002971",
                        "stock_name": "和远气体",
                        "candidate_role": "板块锚",
                        "anchor_reversal_decision": "可作为主对象",
                        "position_plan_pct": 0,
                        "planned_participation": {"action": "skip", "position_plan_pct": 0},
                    }
                ]
            },
            risk_groups={
                "delete_group": [
                    {
                        "name": "和远气体",
                        "code": "002971",
                        "risk_level": "🔴 高风险",
                        "dest": "明天先回避谁",
                        "risk_penalties": ["炸板57次且尾盘才回封", "高换手连板"],
                        "tomorrow_risk": "仍在消化分歧，明日先看竞价与承接",
                    }
                ]
            },
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"}
            },
            position_decision={"target_position_pct": 0},
        )

        role_layer = next(layer for layer in payload["layers"] if layer["id"] == "sector_role")
        leader_layer = next(layer for layer in payload["layers"] if layer["id"] == "leader_reverse")
        price_layer = next(layer for layer in payload["layers"] if layer["id"] == "price_action")

        role_entry = next(item for item in role_layer["entries"] if item["stock"]["code"] == "002971")
        leader_entry = next(item for item in leader_layer["entries"] if item["stock"]["code"] == "002971")
        price_entry = next(item for item in price_layer["entries"] if item["stock"]["code"] == "002971")

        self.assertEqual(role_entry["status"], "survived")
        self.assertIn("板块锚", role_entry["reason"])
        self.assertEqual(leader_entry["status"], "survived")
        self.assertIn("可作为主对象", leader_entry["reason"])
        self.assertEqual(price_entry["status"], "eliminated")
        self.assertIn("炸板57次且尾盘才回封", price_entry["reason"])
        self.assertIn("高换手连板", price_entry["reason"])
        self.assertIn("明日先看竞价与承接", price_entry["reason"])

    def test_zero_final_action_does_not_backfill_from_process_candidate(self):
        payload = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            variant="replay",
            selection_workflow=self._workflow(),
            final_target_resolution={
                "watch_target": {
                    "name": "和远气体",
                    "code": "002971",
                    "sector": "化工原料",
                    "front_observation_qualified": True,
                },
                "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"},
            },
            position_decision={"target_position_pct": 0},
        )

        final_layer = payload["layers"][-1]
        self.assertEqual(payload["final_action"]["label"], "0%不参与")
        self.assertIn("最终没有新增参与对象", payload["final_action"]["reason"])
        self.assertNotEqual(payload["final_action"]["reason"], "selection_workflow.final")
        self.assertEqual(payload["final_action"]["position_pct"], 0)
        self.assertEqual(payload["final_action"]["target"], {})
        self.assertEqual(final_layer["entries"][0]["stock"], {})
        self.assertEqual(final_layer["entries"][0]["stock_label"], "无执行对象")
        self.assertIn("最终没有新增参与对象", final_layer["entries"][0]["reason"])
        self.assertIn("过程样本", final_layer["note"])

    def test_final_layer_keeps_previous_round_inputs_visible_when_action_exists(self):
        workflow = self._workflow()
        workflow["candidate_pool"] = [workflow["candidate_pool"][0]]
        workflow["final"] = {
            "execution_object": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
            "position_pct": 50,
            "action_text": "50%条件执行",
            "source_node": "N8",
            "failure_conditions": [],
        }
        payload = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            variant="replay",
            selection_workflow=workflow,
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"}
            },
            position_decision={"target_position_pct": 0},
        )

        final_layer = payload["layers"][-1]
        html = render_elimination_tournament_html(payload)
        final_round = html.split('id="layer-final_resolution"', 1)[1]

        self.assertEqual(final_layer["input_count"], 1)
        self.assertEqual(final_layer["input_entries"][0]["stock_label"], "和远气体(002971)")
        self.assertIn("本轮输入 1 只：", final_round)
        self.assertIn("和远气体(002971)", final_round)
        self.assertIn("最终动作 1 只：", final_round)
        self.assertIn("50%条件执行", final_round)

    def test_final_action_reason_includes_premarket_narrative_review_cancel(self):
        workflow = self._workflow()
        workflow["final"] = {
            "execution_object": {},
            "position_pct": 0,
            "action_text": "50%条件执行",
            "source_node": "N8_5",
            "premarket_narrative_review": {
                "status": "不参与",
                "action_effect_label": "不参与",
                "summary": "Meta拟对外出售算力，击中AI算力和存储紧缺叙事",
                "restore_conditions": ["同链板块不继续负反馈"],
                "cancel_conditions": ["标的无法修复承接"],
            },
        }

        payload = build_elimination_tournament_payload(
            trade_date="2026-07-01",
            variant="replay",
            selection_workflow=workflow,
            position_decision={"target_position_pct": 0},
        )

        self.assertEqual(payload["final_action"]["target"], {})
        self.assertIn("盘前叙事反证复核", payload["final_action"]["reason"])
        self.assertIn("Meta拟对外出售算力", payload["final_action"]["reason"])
        self.assertIn("不参与", payload["final_action"]["reason"])
        self.assertNotIn("50%条件执行", payload["final_action"]["reason"])

    def test_final_action_reason_reads_top_level_premarket_narrative_review(self):
        workflow = self._workflow()
        workflow["premarket_narrative_review"] = {
            "status": "不参与",
            "action_effect_label": "不参与",
            "summary": "Meta拟对外出售算力，击中AI算力和存储紧缺叙事",
        }
        workflow["final"] = {
            "execution_object": {},
            "position_pct": 0,
            "action_text": "50%条件执行",
            "source_node": "N8_5",
        }

        payload = build_elimination_tournament_payload(
            trade_date="2026-07-01",
            variant="replay",
            selection_workflow=workflow,
            position_decision={"target_position_pct": 0},
        )

        self.assertIn("盘前叙事反证复核", payload["final_action"]["reason"])
        self.assertIn("Meta拟对外出售算力", payload["final_action"]["reason"])
        self.assertNotIn("50%条件执行", payload["final_action"]["reason"])

    def test_missing_evidence_is_explicit(self):
        workflow = self._workflow()
        workflow["candidate_pool"] = [workflow["candidate_pool"][0]]
        workflow["candidate_pool"][0]["brooks_price_action_judge"] = {}

        payload = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            variant="replay",
            selection_workflow=workflow,
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"}
            },
            position_decision={"target_position_pct": 0},
        )

        price_layer = next(layer for layer in payload["layers"] if layer["id"] == "price_action")
        price_entry = price_layer["entries"][0]

        self.assertEqual(price_entry["status"], "survived")
        self.assertIn("暂无价格层淘汰证据", price_entry["reason"])

    def test_missing_ledger_does_not_render_as_zero_position_fact(self):
        workflow = self._workflow()
        workflow["candidate_pool"] = [workflow["candidate_pool"][0]]

        payload = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            variant="replay",
            selection_workflow=workflow,
            decision_ledger={},
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"}
            },
            position_decision={"target_position_pct": 0},
        )

        account_layer = next(layer for layer in payload["layers"] if layer["id"] == "account_execution")
        account_entry = account_layer["entries"][0]

        self.assertEqual(account_entry["status"], "eliminated")
        self.assertIn("账户/仓位事实缺失", account_entry["reason"])
        self.assertIn("0%不参与", account_entry["reason"])
        self.assertNotIn("决策台账仓位=0%", account_entry["reason"])
        self.assertNotIn("ledger_position_pct", account_entry)


class EliminationTournamentHtmlTest(unittest.TestCase):
    def _payload(self):
        return {
            "schema_version": "elimination_tournament.v1",
            "trade_date": "2026-06-12",
            "variant": "replay",
            "final_action": {
                "label": "0%不参与",
                "position_pct": 0,
                "target": {},
                "source": "selection_workflow.final",
                "reason": "无明日执行对象，保持观察",
            },
            "layers": [
                {
                    "id": "sector",
                    "title": "板块层",
                    "input_count": 1,
                    "eliminated_count": 0,
                    "survivor_count": 1,
                    "survivors": [{"stock_label": "和远气体(002971)"}],
                    "eliminated": [],
                    "entries": [
                        {
                            "stock_label": "和远气体(002971)",
                            "stock": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                            "sector": "化工原料",
                            "sector_role": "板块锚",
                            "status": "survived",
                            "reason": "来自市场氛围、板块发酵和板块角色推导",
                            "next_basis": "进入板块内角色层",
                        }
                    ],
                },
                {
                    "id": "sector_role",
                    "title": "板块内角色层",
                    "input_count": 1,
                    "eliminated_count": 0,
                    "survivor_count": 1,
                    "survivors": [{"stock_label": "和远气体(002971)"}],
                    "eliminated": [],
                    "entries": [
                        {
                            "stock_label": "和远气体(002971)",
                            "stock": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                            "sector": "化工原料",
                            "sector_role": "板块锚",
                            "status": "survived",
                            "reason": "身份=板块锚",
                            "next_basis": "进入龙头反推层",
                        }
                    ],
                },
                {
                    "id": "leader_reverse",
                    "title": "龙头反推层",
                    "input_count": 1,
                    "eliminated_count": 0,
                    "survivor_count": 1,
                    "survivors": [{"stock_label": "和远气体(002971)"}],
                    "eliminated": [],
                    "entries": [
                        {
                            "stock_label": "和远气体(002971)",
                            "stock": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                            "sector": "化工原料",
                            "sector_role": "板块锚",
                            "status": "survived",
                            "reason": "板块锚反推：可作为主对象",
                            "next_basis": "进入价格行为层",
                        }
                    ],
                },
                {
                    "id": "price_action",
                    "title": "价格行为层",
                    "input_count": 1,
                    "eliminated_count": 1,
                    "survivor_count": 0,
                    "survivors": [],
                    "eliminated": [{"stock_label": "和远气体(002971)"}],
                    "entries": [
                        {
                            "stock_label": "和远气体(002971)",
                            "stock": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                            "sector": "化工原料",
                            "sector_role": "板块锚",
                            "status": "eliminated",
                            "reason": "炸板57次且尾盘才回封；高换手连板",
                            "elimination_basis": "风险优先，明日先看竞价与承接，不新增参与",
                        }
                    ],
                },
                {
                    "id": "account_execution",
                    "title": "盈亏比/账户层",
                    "input_count": 0,
                    "eliminated_count": 0,
                    "survivor_count": 0,
                    "survivors": [],
                    "eliminated": [],
                    "entries": [],
                    "note": "数据不足，无法展示本轮淘汰细节",
                },
                {
                    "id": "final_resolution",
                    "title": "最终收口层",
                    "input_count": 0,
                    "eliminated_count": 0,
                    "survivor_count": 0,
                    "survivors": [],
                    "eliminated": [],
                    "entries": [
                        {
                            "stock": {},
                            "stock_label": "无执行对象",
                            "status": "final_action",
                            "reason": "无明日执行对象，保持观察",
                            "source": "selection_workflow.final",
                            "position_pct": 0,
                            "action_label": "0%不参与",
                        }
                    ],
                    "note": "最终没有新增参与对象；前面出现的股票只作为过程样本或观察参照。",
                },
            ],
        }

    def test_renderer_outputs_full_html_with_six_layers(self):
        html = render_elimination_tournament_html(self._payload())

        self.assertIn("<!doctype html>", html)
        self.assertIn('meta name="artifact" content="elimination-tournament"', html)
        self.assertIn('class="final-summary final-action-summary"', html)
        self.assertIn('class="key-paths"', html)
        self.assertIn('class="tournament-flow"', html)
        self.assertEqual(html.count('class="tournament-round round-card"'), 6)
        for title in ("板块层", "板块内角色层", "龙头反推层", "价格行为层", "盈亏比/账户层", "最终收口层"):
            self.assertIn(title, html)
        for index in range(1, 7):
            self.assertIn(f"第{index}轮：", html)
        self.assertGreaterEqual(html.count("本轮输入"), 6)
        self.assertGreaterEqual(html.count("本轮淘汰"), 6)
        self.assertGreaterEqual(html.count("本轮晋级"), 5)
        self.assertEqual(html.count('class="lane-details round-lane input-lane round-inputs'), 6)
        self.assertEqual(html.count('class="lane-details round-lane eliminated-lane round-eliminated'), 6)
        self.assertEqual(html.count('class="lane-details round-lane survived-lane round-survivors'), 6)
        self.assertIn("晋级至：板块内角色层", html)
        self.assertIn("晋级依据", html)
        self.assertIn("淘汰依据", html)
        self.assertIn("炸板57次且尾盘才回封", html)
        self.assertIn("高换手连板", html)
        self.assertIn("数据不足，无法展示本轮淘汰细节", html)
        self.assertIn("<details", html)
        self.assertIn("<summary", html)
        self.assertIn("scroll-list", html)
        self.assertNotIn("<table", html)

    def test_renderer_shows_heyuan_path_as_round_elimination(self):
        html = render_elimination_tournament_html(self._payload())
        leader_round = html.split('id="layer-leader_reverse"', 1)[1].split('id="layer-price_action"', 1)[0]
        price_round = html.split('id="layer-price_action"', 1)[1].split('id="layer-account_execution"', 1)[0]

        self.assertIn("和远气体(002971)", leader_round)
        self.assertIn("本轮晋级（1只）", leader_round)
        self.assertIn("板块锚反推：可作为主对象", leader_round)
        self.assertIn("和远气体(002971)", price_round)
        self.assertIn("本轮淘汰（1只）", price_round)
        self.assertIn("本轮晋级（0只）", price_round)
        self.assertIn("炸板57次且尾盘才回封", price_round)
        self.assertIn("高换手连板", price_round)
        self.assertIn('data-stock-code="002971"', price_round)
        self.assertIn("和远气体(002971)：板块层晋级 -&gt; 板块内角色层晋级 -&gt; 龙头反推层晋级 -&gt; 价格行为层淘汰", html)

    def test_renderer_collapses_long_round_lists_without_hiding_key_path(self):
        payload = self._payload()
        eliminated = []
        for index in range(1, 13):
            eliminated.append(
                {
                    "stock_label": f"早筛淘汰{index:02d}(000{index:03d})",
                    "stock": {"name": f"早筛淘汰{index:02d}", "code": f"000{index:03d}", "sector": "杂项"},
                    "sector": "杂项",
                    "sector_role": "观察样本",
                    "status": "eliminated",
                    "reason": "不是当日主线板块锚",
                    "elimination_basis": "板块层淘汰",
                }
            )
        sector_layer = payload["layers"][0]
        sector_layer["entries"] = eliminated + sector_layer["entries"]
        sector_layer["input_count"] = 13
        sector_layer["eliminated_count"] = 12
        sector_layer["survivor_count"] = 1
        sector_layer["eliminated"] = [{"stock_label": item["stock_label"]} for item in eliminated]

        html = render_elimination_tournament_html(payload)
        sector_round = html.split('id="layer-sector"', 1)[1].split('id="layer-sector_role"', 1)[0]

        self.assertIn("<strong>本轮输入 13 只：</strong>早筛淘汰01(000001)、早筛淘汰02(000002)、早筛淘汰03(000003)", sector_round)
        self.assertIn("等13只", sector_round)
        self.assertIn("<strong>本轮淘汰 12 只：</strong>早筛淘汰01(000001)、早筛淘汰02(000002)、早筛淘汰03(000003)", sector_round)
        self.assertIn("等12只", sector_round)
        self.assertIn('class="lane-details round-lane input-lane round-inputs"', sector_round)
        self.assertIn('class="input-list scroll-list"', sector_round)
        self.assertIn('class="stock-list scroll-list"', sector_round)
        self.assertIn("和远气体(002971)：板块层晋级 -&gt; 板块内角色层晋级 -&gt; 龙头反推层晋级 -&gt; 价格行为层淘汰", html)

    def test_unique_final_action_label_only_appears_in_final_layer(self):
        html = render_elimination_tournament_html(self._payload())
        before_final = html.split('id="layer-final_resolution"', 1)[0]
        after_final = html.split('id="layer-final_resolution"', 1)[1]

        self.assertNotIn("明日唯一动作", before_final)
        self.assertIn("明日唯一动作", after_final)

    def test_renderer_escapes_user_visible_fields(self):
        payload = self._payload()
        payload["layers"][0]["entries"][0]["stock_label"] = "坏股票<script>"
        payload["layers"][0]["entries"][0]["reason"] = "理由 <b>不能执行</b>"

        html = render_elimination_tournament_html(payload)

        self.assertIn("坏股票&lt;script&gt;", html)
        self.assertIn("理由 &lt;b&gt;不能执行&lt;/b&gt;", html)
        self.assertNotIn("坏股票<script>", html)

    def test_elimination_tournament_html_renders_static_flowchart_and_mermaid_fallback(self):
        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            source_payloads={
                "sector_capital_carrier_strategy": {
                    "schema_version": "sector_capital_carrier_paper_strategy.v1",
                    "action": "paper_participate",
                    "action_label": "板块资金载体主样本",
                    "action_reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
                    "primary_candidate": {
                        "stock_label": "和远气体(002971)",
                        "reason": "化工原料进入板块候选；个股证据：热榜关注、容量成交；角色：趋势容量核心",
                    },
                    "stages": [
                        {
                            "title": "板块线索恢复",
                            "input_count": 1,
                            "eliminated_count": 0,
                            "survivor_count": 1,
                            "survivors": [{"label": "化工原料", "reason": "资金流入与板块涨幅同向"}],
                            "eliminated": [],
                        }
                    ],
                }
            },
            elimination_tournament_payload=self._payload(),
        )

        html = render_elimination_tournament_html(payload)

        self.assertIn('meta name="artifact" content="elimination-tournament"', html)
        self.assertIn("明日标的选股淘汰赛", html)
        self.assertIn("生成前复核流程图", html)
        self.assertIn('class="preflight-flowchart"', html)
        self.assertIn('data-flowchart-rendered="static"', html)
        self.assertIn('class="flowchart-mermaid-body mermaid"', html)
        self.assertIn("flowchart-mermaid-head", html)
        self.assertIn('data-layer-id="price_action"', html)
        self.assertIn("Mermaid 文本复核", html)
        self.assertIn("flowchart TD", html)
        self.assertIn("data-mermaid-status', 'local-svg'", html)
        self.assertNotIn("cdn.jsdelivr", html)
        self.assertNotIn("mermaid.min.js", html)

    def test_path_follows_saved_markdown_parent(self):
        path = elimination_tournament_html_path(
            ROOT / "reports" / "replay" / "2026-06-12_A股日报_完整版_replay.md",
            "2026-06-12",
        )

        self.assertEqual(
            str(path),
            str(ROOT / "reports" / "replay" / "2026-06-12_明日标的选股淘汰赛.html"),
        )

    def test_sector_capital_preflight_payload_reuses_elimination_final_action(self):
        source = self._payload()

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            elimination_tournament_payload=source,
        )

        self.assertEqual(payload["schema_version"], "sector_capital_preflight.v1")
        self.assertEqual(payload["derivation_contract"], "sector_capital_diffusion_first.v1")
        for key in ("label", "position_pct", "target", "source", "reason"):
            self.assertEqual(payload["final_action"][key], source["final_action"][key])
        self.assertEqual(payload["final_action"]["failure_conditions"], [])
        self.assertIn("selection_workflow", payload["source_payloads"])
        self.assertEqual(payload["source_payloads"]["elimination_tournament_payload"]["schema_version"], "elimination_tournament.v1")
        self.assertIn("flowchart TD", payload["mermaid"])
        for label in (
            "周期窗口",
            "唯一明日动作或不参与",
            "T+1参与预案",
            "T+2情绪周期推演",
            "只批改不回写T0",
            "白痴指数复核",
            "压缩/合并/降级低价值高成本层",
            "下一轮优化",
        ):
            self.assertIn(label, payload["mermaid"])
        self.assertEqual(payload["tplus_rehearsal"]["schema_version"], "t0_tplus_rehearsal.v1")
        self.assertIn("日报生成日是T0", payload["tplus_rehearsal"]["t0_boundary"])
        self.assertIn("不回写T0", payload["tplus_rehearsal"]["review_boundary"])
        self.assertEqual(payload["tplus_rehearsal"]["tplus1"]["participation_qualification"], "只观察承接，不新增参与")
        self.assertEqual(
            [layer["id"] for layer in payload["layers"]],
            [
                "market_capital_structure",
                "sector_capital_diffusion",
                "capital_carrier",
                "carrier_role",
                "quant_trace",
                "price_action",
                "cycle_window",
                "counter_evidence_account",
                "final_action",
            ],
        )
        self.assertEqual(payload["layers"][0]["source_layer_id"], "sector")
        self.assertEqual(payload["layers"][-1]["entries"][0]["stock"], {})
        self.assertEqual(payload["layers"][-1]["entries"][0]["stock_name"], "无执行对象")
        for layer in payload["layers"]:
            if layer["id"] == "final_action":
                self.assertEqual(layer["input_count"], 0)
                self.assertEqual(layer["survivor_count"], 0)
            else:
                self.assertEqual(layer["input_count"], len(layer["entries"]))
            self.assertEqual(layer["eliminated_count"], len(layer["eliminated"]))
            if layer["id"] != "final_action":
                self.assertEqual(layer["survivor_count"], len(layer["survivors"]))
            for entry in layer["entries"]:
                self.assertIn("stock_code", entry)
                self.assertIn("stock_name", entry)
                self.assertIn("sector", entry)
                self.assertNotIn("risk_row", entry)
        self.assertEqual(payload["decision_list"][0]["item"], "市场能否进攻")
        self.assertEqual(payload["decision_list"][-1]["item"], "账户是否适配")
        self.assertEqual(payload["idiot_index_review"][0]["step"], "涨停池起点")

    def test_sector_capital_preflight_does_not_use_legacy_limit_up_as_market_entry(self):
        legacy_only = build_elimination_tournament_payload(
            trade_date="2026-06-08",
            variant="replay",
            selection_workflow={
                "schema_version": "selection_workflow.v1",
                "target_date": "2026-06-08",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                    "source_node": "N8",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "大有能源", "code": "600403", "sector": "煤炭开采"},
                        "source_pools": ["extreme_conviction_list"],
                        "entry_basis": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                        "candidate_origin": "legacy_signal_only",
                        "sector": "煤炭开采",
                        "sector_role": "观察样本",
                    }
                ],
            },
        )

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-08",
            variant="replay",
            elimination_tournament_payload=legacy_only,
        )

        by_id = {layer["id"]: layer for layer in payload["layers"]}
        self.assertEqual(by_id["market_capital_structure"]["input_count"], 1)
        self.assertEqual(by_id["market_capital_structure"]["eliminated_count"], 1)
        self.assertEqual(by_id["market_capital_structure"]["entries"][0]["stock_label"], "大有能源(600403)")
        self.assertIn("不能作为新仓入口", by_id["market_capital_structure"]["entries"][0]["reason"])
        self.assertEqual(by_id["sector_capital_diffusion"]["input_count"], 0)
        self.assertIn("上一层没有剩余股票", by_id["sector_capital_diffusion"]["note"])
        self.assertNotIn("legacy_signal_recycle", by_id)

        html = render_sector_capital_preflight_html(payload)
        embedded = _embedded_json_payload(html, "sector-capital-preflight-payload")
        embedded_by_id = {layer["id"]: layer for layer in embedded["layers"]}
        self.assertEqual(embedded_by_id["market_capital_structure"]["input_count"], 1)
        self.assertEqual(embedded_by_id["market_capital_structure"]["eliminated_count"], 1)
        self.assertEqual(embedded_by_id["market_capital_structure"]["entries"][0]["stock_label"], "大有能源(600403)")
        self.assertEqual(embedded_by_id["sector_capital_diffusion"]["input_count"], 0)
        self.assertNotIn("legacy_signal_recycle", embedded_by_id)
        self.assertNotIn("旧信号回收", html)
        self.assertIn("不能作为新仓入口", html)

    def test_sector_capital_preflight_keeps_second_wave_trend_leader_for_reverse_check(self):
        source = build_elimination_tournament_payload(
            trade_date="2026-06-08",
            variant="replay",
            selection_workflow={
                "schema_version": "selection_workflow.v1",
                "target_date": "2026-06-08",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                    "source_node": "N8",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "华电辽能", "code": "600396", "sector": "火力发电"},
                        "source_pools": ["crossline_observation_stocks"],
                        "entered_reason": "热榜第6+涨幅0.0%，仅作热度观察",
                        "entry_basis": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                        "candidate_origin": "legacy_signal_only",
                        "sector": "火力发电",
                        "sector_role": "{'role': 'core_transmitter', 'basis': ['趋势审美', '20日区间位置健康', 'MA20上方或趋势未破']}",
                        "reversal_decision": "",
                        "brooks_price_action_judge": {
                            "status": "accepted",
                            "verdict": "资金表态被价格接受",
                            "participation_effect": "进入N7对照，仍需板块同步、账户和时间窗口配合",
                        },
                    }
                ],
            },
        )

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-08",
            variant="replay",
            source_payloads={
                "daily_context": {
                    "hot_rank_top50": [
                        {
                            "code": "600396",
                            "name": "华电辽能",
                            "rank": 6,
                            "concepts": ["超超临界发电", "绿色电力"],
                        }
                    ],
                    "hot_plates": [{"name": "电力", "order": 1}],
                    "zt_pool_by_sector": {
                        "电力": [{"code": "600505", "name": "西昌电力", "zt_type": "4/2"}]
                    },
                    "current_mainline_history_record": {
                        "leading_line": "电力",
                        "primary_mainline": "电力",
                    },
                    "current_sector_turnover_snapshot": {
                        "sector_name": "新型电力",
                        "turnover_share_pct": 0.6,
                    },
                }
            },
            elimination_tournament_payload=source,
        )

        market_layer = next(layer for layer in payload["layers"] if layer["id"] == "market_capital_structure")
        sector_layer = next(layer for layer in payload["layers"] if layer["id"] == "sector_capital_diffusion")
        carrier_layer = next(layer for layer in payload["layers"] if layer["id"] == "capital_carrier")
        role_layer = next(layer for layer in payload["layers"] if layer["id"] == "carrier_role")
        entry = market_layer["entries"][0]
        self.assertEqual(entry["stock_label"], "华电辽能(600396)")
        self.assertEqual(entry["status"], "survived")
        self.assertIn("热榜第6", entry["reason"])
        self.assertIn("当日记录主线=电力", entry["reason"])
        self.assertIn("板块在热度板块榜", entry["reason"])
        self.assertIn("同板块涨停=西昌电力(600505)", entry["reason"])
        self.assertIn("趋势龙头/二波预期", entry["reason"])
        self.assertEqual(sector_layer["input_count"], 1)
        self.assertEqual(carrier_layer["input_count"], 1)
        self.assertEqual(role_layer["input_count"], 1)
        self.assertEqual(role_layer["entries"][0]["status"], "survived")
        self.assertIn("趋势龙头/二波预期", role_layer["entries"][0]["reason"])
        self.assertIn("进入量化参与痕迹层", role_layer["entries"][0]["next_basis"])

    def test_sector_capital_preflight_still_rejects_hot_rank_without_trend_role(self):
        source = build_elimination_tournament_payload(
            trade_date="2026-06-08",
            variant="replay",
            selection_workflow={
                "schema_version": "selection_workflow.v1",
                "target_date": "2026-06-08",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                    "source_node": "N8",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "华电辽能", "code": "600396", "sector": "火力发电"},
                        "source_pools": ["crossline_observation_stocks"],
                        "entered_reason": "热榜第6+涨幅0.0%，仅作热度观察",
                        "entry_basis": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                        "candidate_origin": "legacy_signal_only",
                        "sector": "火力发电",
                        "sector_role": "",
                        "reversal_decision": "",
                    }
                ],
            },
        )

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-08",
            variant="replay",
            source_payloads={
                "daily_context": {
                    "hot_rank_top50": [
                        {
                            "code": "600396",
                            "name": "华电辽能",
                            "rank": 6,
                            "concepts": ["超超临界发电", "绿色电力"],
                        }
                    ],
                    "hot_plates": [{"name": "电力", "order": 1}],
                    "zt_pool_by_sector": {
                        "电力": [{"code": "600505", "name": "西昌电力", "zt_type": "4/2"}]
                    },
                    "current_mainline_history_record": {
                        "leading_line": "电力",
                        "primary_mainline": "电力",
                    },
                    "current_sector_turnover_snapshot": {
                        "sector_name": "新型电力",
                        "turnover_share_pct": 0.6,
                    },
                }
            },
            elimination_tournament_payload=source,
        )

        market_layer = next(layer for layer in payload["layers"] if layer["id"] == "market_capital_structure")
        entry = market_layer["entries"][0]
        self.assertEqual(entry["stock_label"], "华电辽能(600396)")
        self.assertEqual(entry["status"], "eliminated")
        self.assertIn("尚未证明它就是该板块锚/龙头", entry["reason"])
        self.assertIn("涨停或热榜本身只作线索", entry["elimination_basis"])

    def test_sector_capital_preflight_uses_decision_day_probe_evidence_for_power_second_wave(self):
        source = build_elimination_tournament_payload(
            trade_date="2026-06-08",
            variant="replay",
            selection_workflow={
                "schema_version": "selection_workflow.v1",
                "target_date": "2026-06-08",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                    "source_node": "N8",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "大有能源", "code": "600403", "sector": "煤炭开采"},
                        "source_pools": ["extreme_conviction_list"],
                        "entered_reason": "6连板 / 趋势审美 / 20日区间位置健康 / MA20上方或趋势未破",
                        "entry_basis": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                        "candidate_origin": "legacy_signal_only",
                        "sector": "煤炭开采",
                        "sector_role": "{'role': 'core_transmitter', 'basis': ['趋势审美', '20日区间位置健康']}",
                    },
                    {
                        "stock": {"name": "大唐发电", "code": "601991", "sector": "火力发电"},
                        "source_pools": ["crossline_observation_stocks"],
                        "entered_reason": "热榜第3+涨幅0.0%，仅作热度观察",
                        "entry_basis": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                        "candidate_origin": "legacy_signal_only",
                        "sector": "火力发电",
                        "sector_role": "",
                        "brooks_price_action_judge": {
                            "status": "insufficient",
                            "verdict": "价格行为证据不足",
                            "participation_effect": "不新增资格，继续按板块锚、共同选择和风险条件复核",
                        },
                    },
                    {
                        "stock": {"name": "华电辽能", "code": "600396", "sector": "火力发电"},
                        "source_pools": ["crossline_observation_stocks"],
                        "entered_reason": "热榜第6+涨幅0.0%，仅作热度观察",
                        "entry_basis": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                        "candidate_origin": "legacy_signal_only",
                        "sector": "火力发电",
                        "sector_role": "",
                        "brooks_price_action_judge": {
                            "status": "insufficient",
                            "verdict": "价格行为证据不足",
                            "participation_effect": "不新增资格，继续按板块锚、共同选择和风险条件复核",
                        },
                    },
                ],
            },
        )

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-08",
            variant="replay",
            source_payloads={
                "daily_context": {
                    "hot_rank_top50": [
                        {"code": "601991", "name": "大唐发电", "rank": 3, "concepts": ["绿色电力", "风电"]},
                        {"code": "600396", "name": "华电辽能", "rank": 6, "concepts": ["超超临界发电", "绿色电力"]},
                        {"code": "600403", "name": "大有能源", "rank": 9, "concepts": ["煤炭概念"]},
                    ],
                    "hot_plates": [
                        {"name": "电力", "order": 1},
                        {"name": "煤炭开采加工", "order": 6},
                    ],
                    "current_mainline_history_record": {"leading_line": "电力"},
                    "current_sector_turnover_snapshot": {"sector_name": "新型电力", "turnover_share_pct": 0.61},
                    "crossline_observation_stocks": [
                        {
                            "code": "601991",
                            "name": "大唐发电",
                            "sector": "火力发电",
                            "source": "hot_capacity_anchor_source",
                            "source_tier": "anchor_reversal_source",
                            "pattern": "放量冲高",
                        },
                        {
                            "code": "600396",
                            "name": "华电辽能",
                            "sector": "火力发电",
                            "source": "hot_capacity_anchor_source",
                            "source_tier": "anchor_reversal_source",
                            "pattern": "放量冲高",
                        },
                    ],
                    "recent_extreme_conviction_mentions": [
                        {
                            "stock_code": "600726",
                            "stock_name": "华电能源",
                            "sector_candidate": "电力",
                            "reason": "主线内核 / 板块锚定龙 / 5连板 / 趋势审美 / 平台呼吸 / 蛇形走位",
                        }
                    ],
                }
            },
            elimination_tournament_payload=source,
        )

        by_id = {layer["id"]: layer for layer in payload["layers"]}
        market_entries = {entry["stock_label"]: entry for entry in by_id["market_capital_structure"]["entries"]}
        self.assertEqual(market_entries["大有能源(600403)"]["status"], "eliminated")
        self.assertEqual(market_entries["大唐发电(601991)"]["status"], "survived")
        self.assertEqual(market_entries["华电辽能(600396)"]["status"], "survived")
        self.assertIn("趋势/二波线索", market_entries["大唐发电(601991)"]["reason"])
        self.assertIn("同板块趋势锚=华电能源(600726)", market_entries["华电辽能(600396)"]["reason"])
        self.assertEqual(by_id["sector_capital_diffusion"]["input_count"], 2)
        self.assertEqual(by_id["capital_carrier"]["input_count"], 2)
        self.assertEqual(by_id["carrier_role"]["input_count"], 2)
        self.assertEqual(by_id["carrier_role"]["survivor_count"], 2)
        self.assertEqual(by_id["quant_trace"]["input_count"], 2)
        self.assertEqual(by_id["quant_trace"]["survivor_count"], 2)
        self.assertEqual(by_id["price_action"]["input_count"], 2)
        self.assertEqual(by_id["price_action"]["eliminated_count"], 2)
        self.assertIn("价格行为证据不足", by_id["price_action"]["entries"][0]["reason"])
        self.assertIn("不新增资格", by_id["price_action"]["entries"][0]["reason"])
        self.assertIn("趋势载体已识别", by_id["price_action"]["entries"][0]["elimination_basis"])
        self.assertEqual(by_id["cycle_window"]["input_count"], 0)

    def test_sector_capital_preflight_daily_context_merges_nested_trend_evidence(self):
        context = build_sector_capital_preflight_daily_context(
            {
                "hot_plates": [{"name": "电力", "order": 1}],
                "execution_stage_context": {
                    "crossline_observation_stocks": [
                        {
                            "code": "601991",
                            "name": "大唐发电",
                            "sector": "火力发电",
                            "source": "hot_capacity_anchor_source",
                        }
                    ]
                },
            },
            {
                "observation": {
                    "recent_extreme_conviction_mentions": [
                        {
                            "stock_code": "600726",
                            "stock_name": "华电能源",
                            "sector_candidate": "电力",
                            "reason": "主线内核 / 板块锚定龙 / 二波 / 趋势审美",
                        }
                    ]
                }
            },
        )

        self.assertEqual(context["hot_plates"][0]["name"], "电力")
        self.assertEqual(context["crossline_observation_stocks"][0]["name"], "大唐发电")
        self.assertEqual(context["recent_extreme_conviction_mentions"][0]["stock_name"], "华电能源")

    def test_sector_capital_preflight_daily_context_keeps_only_t0_rows(self):
        context = build_sector_capital_preflight_daily_context(
            {
                "market_phase_context": {"trade_date": "2026-06-13", "market_state": "高潮"},
                "hot_plates": [
                    {"trade_date": "2026-06-12", "name": "半导体", "order": 1},
                    {"trade_date": "2026-06-13", "name": "机器人", "order": 1},
                ],
                "sector_fund_flow": {
                    "inflow": [
                        {"trade_date": "2026-06-12", "name": "半导体", "net_inflow_yi": 18.5},
                        {"trade_date": "2026-06-13", "name": "机器人", "net_inflow_yi": 31.2},
                    ]
                },
                "execution_stage_context": {
                    "crossline_observation_stocks": [
                        {"source_date": "2026-06-12", "code": "600584", "name": "长电科技"},
                        {"source_date": "2026-06-13", "code": "300024", "name": "机器人样本"},
                    ]
                },
            },
            trade_date="2026-06-12",
        )

        self.assertNotIn("market_phase_context", context)
        self.assertEqual([item["name"] for item in context["hot_plates"]], ["半导体"])
        self.assertEqual([item["name"] for item in context["sector_fund_flow"]["inflow"]], ["半导体"])
        self.assertEqual([item["name"] for item in context["crossline_observation_stocks"]], ["长电科技"])

    def test_sector_capital_preflight_refreshes_existing_layers_with_daily_context(self):
        source = build_elimination_tournament_payload(
            trade_date="2026-06-08",
            variant="replay",
            selection_workflow={
                "schema_version": "selection_workflow.v1",
                "target_date": "2026-06-08",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                    "source_node": "N8",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "华电辽能", "code": "600396", "sector": "火力发电"},
                        "source_pools": ["crossline_observation_stocks"],
                        "entry_basis": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                        "candidate_origin": "legacy_signal_only",
                        "sector": "火力发电",
                    }
                ],
            },
        )
        stale_preflight = {
            "schema_version": "sector_capital_preflight.v1",
            "trade_date": "2026-06-08",
            "variant": "replay",
            "final_action": {"label": "0%不参与", "position_pct": 0, "target": {}},
            "layers": [
                {
                    "id": "market_capital_structure",
                    "title": "市场资金结构",
                    "entries": [
                        {
                            "stock": {"name": "华电辽能", "code": "600396", "sector": "火力发电"},
                            "status": "eliminated",
                            "reason": "旧理由：只说旧信号，不反推板块锚",
                        }
                    ],
                }
            ],
        }

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-08",
            variant="replay",
            sector_capital_preflight=stale_preflight,
            source_payloads={
                "daily_context": {
                    "hot_rank_top50": [{"code": "600396", "name": "华电辽能", "rank": 6}],
                    "hot_plates": [{"name": "电力", "order": 1}],
                    "zt_pool_by_sector": {"电力": [{"code": "600505", "name": "西昌电力"}]},
                    "current_mainline_history_record": {"leading_line": "电力"},
                }
            },
            elimination_tournament_payload=source,
        )

        market_layer = next(layer for layer in payload["layers"] if layer["id"] == "market_capital_structure")
        reason = market_layer["entries"][0]["reason"]
        self.assertNotIn("旧理由", reason)
        self.assertIn("热榜第6", reason)
        self.assertIn("当日记录主线=电力", reason)
        self.assertIn("同板块涨停=西昌电力(600505)", reason)
        self.assertIn("尚未证明它就是该板块锚/龙头", reason)

    def test_sector_capital_preflight_quant_trace_does_not_eliminate_price_risk_early(self):
        source = self._payload()
        price_layer = next(layer for layer in source["layers"] if layer["id"] == "price_action")
        price_layer["entries"][0]["risk_evidence"] = "炸板57次且尾盘才回封；高换手连板"

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            elimination_tournament_payload=source,
        )

        quant_layer = next(layer for layer in payload["layers"] if layer["id"] == "quant_trace")
        price_layer = next(layer for layer in payload["layers"] if layer["id"] == "price_action")
        cycle_layer = next(layer for layer in payload["layers"] if layer["id"] == "cycle_window")
        counter_layer = next(layer for layer in payload["layers"] if layer["id"] == "counter_evidence_account")
        quant_entry = next(item for item in quant_layer["entries"] if item["stock_code"] == "002971")
        price_entry = next(item for item in price_layer["entries"] if item["stock_code"] == "002971")

        self.assertEqual(quant_entry["status"], "survived")
        self.assertEqual(quant_entry["next_basis"], "进入价格行为确认层")
        self.assertEqual(quant_layer["survivor_count"], 1)
        self.assertEqual(quant_layer["eliminated_count"], 0)
        self.assertEqual(price_entry["status"], "eliminated")
        self.assertIn("炸板57次且尾盘才回封", price_entry["risk_evidence"])
        self.assertEqual(price_layer["survivor_count"], 0)
        self.assertEqual(cycle_layer["input_count"], 0)
        self.assertEqual(cycle_layer["eliminated_count"], 0)
        self.assertEqual(counter_layer["input_count"], 0)
        self.assertEqual(counter_layer["eliminated_count"], 0)
        self.assertEqual(payload["idiot_index_review"][0]["action"], "降为证据层，不作起点")

    def test_cycle_window_explains_zero_final_after_price_acceptance(self):
        source = self._payload()
        source["final_action"] = {
            "label": "0%不参与",
            "position_pct": 0,
            "target": {},
            "source": "selection_workflow.final",
            "reason": "最终没有新增参与对象，动作=0%不参与；条件未满足：account_context",
            "failure_conditions": ["account_context"],
        }
        price_layer = next(layer for layer in source["layers"] if layer["id"] == "price_action")
        price_layer["entries"][0].update(
            {
                "status": "survived",
                "reason": "风险可控",
                "next_basis": "进入周期窗口",
                "elimination_basis": "",
            }
        )
        price_layer["eliminated"] = []
        price_layer["survivors"] = [price_layer["entries"][0]]
        price_layer["eliminated_count"] = 0
        price_layer["survivor_count"] = 1

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            elimination_tournament_payload=source,
        )

        price_layer = next(layer for layer in payload["layers"] if layer["id"] == "price_action")
        cycle_layer = next(layer for layer in payload["layers"] if layer["id"] == "cycle_window")
        cycle_entry = cycle_layer["entries"][0]

        self.assertEqual(price_layer["survivor_count"], 1)
        self.assertEqual(cycle_entry["status"], "eliminated")
        self.assertNotEqual(cycle_entry["reason"], "风险可控")
        self.assertIn("周期窗口未打开", cycle_entry["reason"])
        self.assertIn("account_context", cycle_entry["reason"])
        self.assertIn("最终没有新增参与对象", cycle_entry["elimination_basis"])

    def test_account_layer_keeps_its_own_reason_after_price_acceptance(self):
        source = self._payload()
        source["final_action"] = {
            "label": "0%不参与",
            "position_pct": 0,
            "target": {},
            "source": "selection_workflow.final",
            "reason": "最终没有新增参与对象，动作=0%不参与",
            "failure_conditions": [],
        }
        price_layer = next(layer for layer in source["layers"] if layer["id"] == "price_action")
        price_layer["entries"][0].update(
            {
                "status": "survived",
                "reason": "风险可控",
                "next_basis": "进入周期窗口",
                "elimination_basis": "",
            }
        )
        price_layer["eliminated"] = []
        price_layer["survivors"] = [price_layer["entries"][0]]
        price_layer["eliminated_count"] = 0
        price_layer["survivor_count"] = 1

        account_layer = next(layer for layer in source["layers"] if layer["id"] == "account_execution")
        account_entry = dict(price_layer["entries"][0])
        account_entry.update(
            {
                "status": "eliminated",
                "reason": "决策台账仓位=0%；0%不参与",
                "elimination_basis": "暂无新增参与资格",
                "next_basis": "",
            }
        )
        account_layer["entries"] = [account_entry]
        account_layer["eliminated"] = [account_entry]
        account_layer["survivors"] = []
        account_layer["input_count"] = 1
        account_layer["eliminated_count"] = 1
        account_layer["survivor_count"] = 0

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            elimination_tournament_payload=source,
        )

        cycle_layer = next(layer for layer in payload["layers"] if layer["id"] == "cycle_window")
        counter_layer = next(layer for layer in payload["layers"] if layer["id"] == "counter_evidence_account")

        self.assertEqual(cycle_layer["survivor_count"], 1)
        self.assertIn("进入账户", cycle_layer["entries"][0]["next_basis"])
        self.assertEqual(counter_layer["input_count"], 1)
        self.assertEqual(counter_layer["eliminated_count"], 1)
        self.assertIn("决策台账仓位=0%", counter_layer["entries"][0]["reason"])
        self.assertIn("暂无新增参与资格", counter_layer["entries"][0]["elimination_basis"])

    def test_cycle_window_marks_missing_reason_when_zero_final_has_no_failure_condition(self):
        source = self._payload()
        source["final_action"] = {
            "label": "0%不参与",
            "position_pct": 0,
            "target": {},
            "source": "selection_workflow.final",
            "reason": "最终没有新增参与对象，动作=0%不参与",
            "failure_conditions": [],
        }
        price_layer = next(layer for layer in source["layers"] if layer["id"] == "price_action")
        price_layer["entries"][0].update(
            {
                "status": "survived",
                "reason": "风险可控",
                "next_basis": "进入周期窗口",
                "elimination_basis": "",
            }
        )
        price_layer["eliminated"] = []
        price_layer["survivors"] = [price_layer["entries"][0]]
        price_layer["eliminated_count"] = 0
        price_layer["survivor_count"] = 1

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            elimination_tournament_payload=source,
        )

        cycle_layer = next(layer for layer in payload["layers"] if layer["id"] == "cycle_window")
        cycle_entry = cycle_layer["entries"][0]

        self.assertIn("未给出具体失败条件", cycle_entry["reason"])
        self.assertIn("待补周期/账户/时间窗口理由", cycle_entry["reason"])
        self.assertNotIn("账户/时间条件未满足；最终没有新增参与对象", cycle_entry["reason"])
        self.assertIn("缺少具体失败条件", cycle_entry["elimination_basis"])

    def test_sector_capital_preflight_existing_payload_keeps_observational_final_action(self):
        stale_preflight = {
            "schema_version": "sector_capital_preflight.v1",
            "trade_date": "2026-06-12",
            "variant": "replay",
            "final_action": {
                "label": "50%条件执行",
                "position_pct": 50,
                "target": {"name": "和远气体", "code": "002971"},
                "source": "stale_preflight",
            },
            "layers": [],
        }

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            sector_capital_preflight=stale_preflight,
            elimination_tournament_payload=self._payload(),
        )

        self.assertEqual(payload["final_action"]["label"], "0%不参与")
        self.assertEqual(payload["final_action"]["position_pct"], 0)
        self.assertEqual(payload["final_action"]["target"], {})
        self.assertEqual(payload["final_action"]["source"], "selection_workflow.final")
        self.assertEqual(payload["source_payloads"]["elimination_tournament_payload"]["schema_version"], "elimination_tournament.v1")
        self.assertEqual(payload["source_artifact"], "elimination_tournament.v1")

    def test_sector_capital_preflight_html_renders_mermaid_layers_and_payload(self):
        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            source_payloads={
                "sector_capital_carrier_strategy": {
                    "schema_version": "sector_capital_carrier_paper_strategy.v1",
                    "action": "paper_participate",
                    "action_label": "板块资金载体主样本",
                    "action_reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
                    "primary_candidate": {
                        "stock_label": "和远气体(002971)",
                        "reason": "化工原料进入板块候选；个股证据：热榜关注、容量成交；角色：趋势容量核心",
                    },
                    "stages": [
                        {
                            "title": "板块线索恢复",
                            "input_count": 1,
                            "eliminated_count": 0,
                            "survivor_count": 1,
                            "survivors": [{"label": "化工原料", "reason": "资金流入与板块涨幅同向"}],
                            "eliminated": [],
                        }
                    ],
                }
            },
            elimination_tournament_payload=self._payload(),
        )

        html = render_sector_capital_preflight_html(payload)

        self.assertIn('meta name="artifact" content="sector-capital-preflight"', html)
        self.assertIn("板块资金扩散生成前复核", html)
        self.assertIn("生成前复核流程图", html)
        self.assertIn('class="preflight-flowchart"', html)
        self.assertIn('data-flowchart-rendered="static"', html)
        self.assertIn('class="flowchart-mermaid-body mermaid"', html)
        self.assertIn("flowchart-mermaid-head", html)
        self.assertIn('data-layer-id="price_action"', html)
        self.assertIn("炸板57次且尾盘才回封", html)
        self.assertIn("Mermaid 文本复核", html)
        self.assertIn("flowchart TD", html)
        self.assertIn("T0推演T+1/T+2交易环境", html)
        self.assertIn("T+1参与日预案", html)
        self.assertIn("T+2处理日预案", html)
        self.assertIn("后验只用于批改", html)
        self.assertIn("板块资金载体预案", html)
        self.assertIn("T0同源策略，只作差异复核，不新增第二个明日对象", html)
        self.assertIn("和远气体(002971)", html)
        self.assertIn("相关决策列表", html)
        self.assertIn("白痴指数复核表", html)
        self.assertIn("市场能否进攻", html)
        self.assertIn("涨停池起点", html)
        self.assertIn("降为证据层，不作起点", html)
        self.assertIn("市场资金结构", html)
        self.assertIn("板块资金扩散", html)
        self.assertIn("板块内资金载体", html)
        self.assertIn("量化参与痕迹", html)
        self.assertIn("周期窗口", html)
        self.assertIn("反方证据与账户/盈亏比/时间窗口", html)
        self.assertIn("价格行为确认", html)
        self.assertIn("唯一明日动作", html)
        self.assertIn("data-mermaid-status', 'local-svg'", html)
        self.assertNotIn("cdn.jsdelivr", html)
        self.assertNotIn("mermaid.min.js", html)
        self.assertIn('id="sector-capital-preflight-payload"', html)
        embedded = _embedded_json_payload(html, "sector-capital-preflight-payload")
        self.assertEqual(embedded["schema_version"], "sector_capital_preflight.v1")
        self.assertEqual(embedded["derivation_contract"], "sector_capital_diffusion_first.v1")
        self.assertEqual(embedded["final_action"]["label"], "0%不参与")
        self.assertEqual(embedded["tplus_rehearsal"]["schema_version"], "t0_tplus_rehearsal.v1")
        self.assertIn("T+1/T+2后验事实只用于复盘批改", embedded["tplus_rehearsal"]["review_boundary"])
        self.assertEqual(
            embedded["sector_capital_carrier_strategy"]["schema_version"],
            "sector_capital_carrier_paper_strategy.v1",
        )
        self.assertEqual(
            embedded["sector_capital_carrier_strategy"]["primary_candidate"]["stock_label"],
            "和远气体(002971)",
        )
        self.assertEqual(embedded["decision_list"][0]["item"], "市场能否进攻")
        self.assertEqual(embedded["idiot_index_review"][0]["step"], "涨停池起点")
        self.assertEqual(embedded["layers"][0]["id"], "market_capital_structure")
        self.assertEqual(embedded["layers"][-1]["id"], "final_action")
        self.assertEqual(embedded["layers"][-1]["input_count"], 0)
        self.assertEqual(embedded["layers"][-1]["survivor_count"], 0)
        self.assertIn("stock_code", embedded["layers"][0]["entries"][0])
        self.assertIn("<strong>本层输入 1 只：</strong>和远气体(002971)", html)
        self.assertIn("和远气体(002971)", html)
        self.assertIn("0%不参与", html)

    def test_sector_capital_preflight_keeps_paper_participation_out_of_final_action(self):
        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            source_payloads={
                "sector_capital_carrier_strategy": {
                    "schema_version": "sector_capital_carrier_paper_strategy.v1",
                    "action": "paper_participate",
                    "action_label": "板块资金载体主样本",
                    "action_reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
                    "primary_candidate": {
                        "stock": {"name": "长电科技", "code": "600584", "sector": "半导体"},
                        "stock_label": "长电科技(600584)",
                        "reason": "半导体进入板块候选；个股证据：热榜关注、容量成交；角色：趋势容量核心",
                    },
                }
            },
            elimination_tournament_payload=self._payload(),
        )

        final_layer = payload["layers"][-1]

        self.assertEqual(payload["final_action"]["label"], "0%不参与")
        self.assertEqual(payload["final_action"]["position_pct"], 0)
        self.assertEqual(payload["final_action"]["target"], {})
        self.assertEqual(payload["final_action"]["source"], "selection_workflow.final")
        self.assertEqual(
            payload["sector_capital_carrier_strategy"]["primary_candidate"]["stock_label"],
            "长电科技(600584)",
        )
        quant_layer = next(layer for layer in payload["layers"] if layer["id"] == "quant_trace")
        self.assertNotIn("只观察可见行为", quant_layer["note"])
        self.assertIn("只记录可见行为", quant_layer["note"])
        self.assertEqual(final_layer["id"], "final_action")
        self.assertEqual(final_layer["input_count"], 0)
        self.assertEqual(final_layer["survivor_count"], 0)
        self.assertEqual(payload["tplus_rehearsal"]["tplus1"]["participation_qualification"], "只观察承接，不新增参与")

    def test_sector_capital_preflight_tplus_rehearsal_uses_t0_market_and_sector_facts(self):
        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            source_payloads={
                "daily_context": {
                    "market_phase_context": {"market_state": "冰点修复，整体仍偏弱"},
                    "hot_plates": [{"name": "半导体", "order": 1}],
                    "sector_fund_flow": {
                        "inflow": [{"name": "半导体", "change_pct": 2.1, "net_inflow_yi": 18.5}]
                    },
                    "zt_pool_by_sector": {
                        "半导体": [
                            {"code": "600584", "name": "长电科技"},
                            {"code": "603986", "name": "兆易创新"},
                        ]
                    },
                },
                "sector_capital_carrier_strategy": {
                    "schema_version": "sector_capital_carrier_paper_strategy.v1",
                    "action": "paper_participate",
                    "action_reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
                    "primary_candidate": {
                        "stock": {"name": "长电科技", "code": "600584", "sector": "半导体"},
                        "stock_label": "长电科技(600584)",
                        "sector": "半导体",
                        "reason": "半导体进入板块候选；个股证据：热榜关注、容量成交；角色：趋势容量核心",
                    },
                },
            },
            elimination_tournament_payload=self._payload(),
        )

        rehearsal = payload["tplus_rehearsal"]

        self.assertEqual(rehearsal["tplus1"]["market_emotion"], "冰点修复观察")
        self.assertEqual(rehearsal["tplus1"]["market_cycle"], "周期窗口未打开或修复待确认")
        self.assertEqual(rehearsal["tplus1"]["sector_emotion"], "板块延续确认")
        self.assertEqual(rehearsal["tplus1"]["sector_cycle"], "主升或二波确认")
        self.assertEqual(rehearsal["tplus2"]["market_emotion"], "弱修复或震荡")
        self.assertEqual(rehearsal["tplus2"]["market_cycle"], "先按修复失败风险处理")
        self.assertEqual(rehearsal["tplus2"]["sector_emotion"], "延续后分歧")
        self.assertEqual(rehearsal["tplus2"]["sector_cycle"], "强者横住续命，后排先兑现")
        self.assertIn("T0市场=冰点", rehearsal["basis"])
        self.assertIn("T0板块=扩散", rehearsal["basis"])

    def test_sector_capital_preflight_final_layer_does_not_recover_after_price_elimination(self):
        source = self._payload()
        source["final_action"] = {
            "label": "50%条件执行",
            "position_pct": 50,
            "target": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
            "source": "selection_workflow.final",
            "reason": "最终对象=和远气体(002971)",
        }
        final_layer = next(layer for layer in source["layers"] if layer["id"] == "final_resolution")
        final_layer["input_count"] = 1
        final_layer["survivor_count"] = 1
        final_layer["input_entries"] = [
            {
                "stock_label": "和远气体(002971)",
                "stock": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                "sector": "化工原料",
                "sector_role": "板块锚",
                "status": "survived",
                "reason": "上一轮晋级，进入最终动作复核",
                "next_basis": "最终收口层",
            }
        ]

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            elimination_tournament_payload=source,
        )

        html = render_sector_capital_preflight_html(payload)
        final_layer_html = html.split('id="preflight-layer-final_action"', 1)[1]
        final_layer_html = final_layer_html.split('<script type="application/json"', 1)[0]
        embedded = _embedded_json_payload(html, "sector-capital-preflight-payload")
        embedded_final_layer = embedded["layers"][-1]

        self.assertEqual(embedded_final_layer["id"], "final_action")
        self.assertEqual(embedded_final_layer["input_count"], 0)
        self.assertEqual(embedded_final_layer["input_entries"], [])
        self.assertIn("<strong>本层输入 0 只：</strong>无", final_layer_html)
        self.assertNotIn("上一轮晋级，进入最终动作复核", final_layer_html)

    def test_sector_capital_preflight_zero_final_action_has_zero_final_layer_counts(self):
        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            elimination_tournament_payload=self._payload(),
        )

        final_layer = payload["layers"][-1]

        self.assertEqual(final_layer["id"], "final_action")
        self.assertEqual(final_layer["input_count"], 0)
        self.assertEqual(final_layer["eliminated_count"], 0)
        self.assertEqual(final_layer["survivor_count"], 0)

    def test_sector_capital_preflight_existing_payload_cannot_jump_after_zero_survivors(self):
        stale_payload = {
            "schema_version": "sector_capital_preflight.v1",
            "trade_date": "2026-06-12",
            "variant": "replay",
            "final_action": {"label": "0%不参与", "position_pct": 0, "target": {}},
            "layers": [
                {
                    "id": "market_capital_structure",
                    "title": "市场资金结构",
                    "entries": [
                        {
                            "stock": {"name": "大有能源", "code": "600403", "sector": "煤炭开采"},
                            "status": "eliminated",
                            "reason": "不属于当日被资金选择的板块扩散方向",
                            "next_basis": "",
                            "elimination_basis": "第一层淘汰",
                        }
                    ],
                },
                {
                    "id": "sector_capital_diffusion",
                    "title": "板块资金扩散",
                    "entries": [],
                },
                {
                    "id": "capital_carrier",
                    "title": "板块内资金载体",
                    "entries": [
                        {
                            "stock": {"name": "大唐发电", "code": "601991", "sector": "火力发电"},
                            "status": "survived",
                            "reason": "坏数据：上一层没有剩余却重新出现",
                            "next_basis": "进入下一层",
                            "elimination_basis": "",
                        }
                    ],
                },
            ],
        }

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            sector_capital_preflight=stale_payload,
        )
        by_id = {layer["id"]: layer for layer in payload["layers"]}

        self.assertEqual(by_id["market_capital_structure"]["input_count"], 1)
        self.assertEqual(by_id["market_capital_structure"]["survivor_count"], 0)
        self.assertEqual(by_id["capital_carrier"]["input_count"], 0)
        self.assertEqual(by_id["capital_carrier"]["entries"], [])
        self.assertIn("上一层板块资金扩散没有剩余股票", by_id["capital_carrier"]["note"])

    def test_sector_capital_preflight_path_follows_saved_markdown_parent(self):
        path = sector_capital_preflight_html_path(
            ROOT / "reports" / "replay" / "2026-06-12_A股日报_完整版_replay.md",
            "2026-06-12",
        )

        self.assertEqual(
            str(path),
            str(ROOT / "reports" / "replay" / "2026-06-12_板块资金扩散生成前复核.html"),
        )

    def test_sector_capital_preflight_html_serializes_datetime_values(self):
        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-15",
            sector_capital_preflight={
                "schema_version": "sector_capital_preflight.v1",
                "trade_date": dt.date(2026, 6, 15),
                "layers": [],
            },
            source_payloads={
                "daily_context": {
                    "created_at": dt.datetime(2026, 6, 15, 18, 44),
                }
            },
        )

        html = render_sector_capital_preflight_html(payload)
        embedded = _embedded_json_payload(html, "sector-capital-preflight-payload")

        self.assertEqual(embedded["trade_date"], "2026-06-15")
        self.assertEqual(embedded["source_payloads"]["daily_context"]["created_at"], "2026-06-15T18:44:00")


if __name__ == "__main__":
    unittest.main()
