import html as html_lib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.elimination_tournament import build_elimination_tournament_payload
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
        self.assertEqual(payload["final_action"], source["final_action"])
        self.assertIn("selection_workflow", payload["source_payloads"])
        self.assertEqual(payload["source_payloads"]["elimination_tournament_payload"]["schema_version"], "elimination_tournament.v1")
        self.assertIn("flowchart TD", payload["mermaid"])
        for label in (
            "周期概率窗口",
            "唯一明日动作或不参与",
            "白痴指数复核",
            "压缩/合并/降级低价值高成本层",
            "下一轮优化",
        ):
            self.assertIn(label, payload["mermaid"])
        self.assertEqual(
            [layer["id"] for layer in payload["layers"]],
            [
                "market_capital_structure",
                "sector_capital_diffusion",
                "capital_carrier",
                "carrier_role",
                "quant_trace",
                "price_action",
                "cycle_probability_window",
                "counter_evidence_account",
                "final_action",
            ],
        )
        self.assertEqual(payload["layers"][0]["source_layer_id"], "sector")
        self.assertEqual(payload["layers"][-1]["entries"][0]["stock"], {})
        self.assertEqual(payload["layers"][-1]["entries"][0]["stock_name"], "无执行对象")
        for layer in payload["layers"]:
            self.assertEqual(layer["input_count"], len(layer["entries"]))
            self.assertEqual(layer["eliminated_count"], len(layer["eliminated"]))
            self.assertEqual(layer["survivor_count"], len(layer["survivors"]))
            for entry in layer["entries"]:
                self.assertIn("stock_code", entry)
                self.assertIn("stock_name", entry)
                self.assertIn("sector", entry)
                self.assertNotIn("risk_row", entry)
        self.assertEqual(payload["decision_list"][0]["item"], "市场能否进攻")
        self.assertEqual(payload["decision_list"][-1]["item"], "账户是否适配")
        self.assertEqual(payload["idiot_index_review"][0]["step"], "涨停池起点")
        self.assertEqual(payload["idiot_index_review"][0]["action"], "降为证据层，不作起点")

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
            elimination_tournament_payload=self._payload(),
        )

        html = render_sector_capital_preflight_html(payload)

        self.assertIn('meta name="artifact" content="sector-capital-preflight"', html)
        self.assertIn("板块资金扩散生成前复核", html)
        self.assertIn("生成前复核流程", html)
        self.assertIn("flowchart TD", html)
        self.assertIn("相关决策列表", html)
        self.assertIn("白痴指数复核表", html)
        self.assertIn("市场能否进攻", html)
        self.assertIn("涨停池起点", html)
        self.assertIn("降为证据层，不作起点", html)
        self.assertIn("市场资金结构", html)
        self.assertIn("板块资金扩散", html)
        self.assertIn("板块内资金载体", html)
        self.assertIn("量化参与痕迹", html)
        self.assertIn("周期概率窗口", html)
        self.assertIn("反方证据与账户/盈亏比/时间窗口", html)
        self.assertIn("价格行为确认", html)
        self.assertIn("唯一明日动作", html)
        self.assertIn('id="sector-capital-preflight-payload"', html)
        embedded = _embedded_json_payload(html, "sector-capital-preflight-payload")
        self.assertEqual(embedded["schema_version"], "sector_capital_preflight.v1")
        self.assertEqual(embedded["derivation_contract"], "sector_capital_diffusion_first.v1")
        self.assertEqual(embedded["final_action"]["label"], "0%不参与")
        self.assertEqual(embedded["decision_list"][0]["item"], "市场能否进攻")
        self.assertEqual(embedded["idiot_index_review"][0]["step"], "涨停池起点")
        self.assertEqual(embedded["layers"][0]["id"], "market_capital_structure")
        self.assertEqual(embedded["layers"][-1]["id"], "final_action")
        self.assertIn("stock_code", embedded["layers"][0]["entries"][0])
        self.assertIn("<strong>本层输入 1 只：</strong>和远气体(002971)", html)
        self.assertIn("无执行对象", html)
        self.assertIn("0%不参与", html)

    def test_sector_capital_preflight_final_layer_uses_input_entries(self):
        source = self._payload()
        final_layer = next(layer for layer in source["layers"] if layer["id"] == "final_resolution")
        final_layer["input_count"] = 1
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

        self.assertIn("<strong>本层输入 1 只：</strong>和远气体(002971)", final_layer_html)
        self.assertIn("上一轮晋级，进入最终动作复核", final_layer_html)

    def test_sector_capital_preflight_path_follows_saved_markdown_parent(self):
        path = sector_capital_preflight_html_path(
            ROOT / "reports" / "replay" / "2026-06-12_A股日报_完整版_replay.md",
            "2026-06-12",
        )

        self.assertEqual(
            str(path),
            str(ROOT / "reports" / "replay" / "2026-06-12_板块资金扩散生成前复核.html"),
        )


if __name__ == "__main__":
    unittest.main()
