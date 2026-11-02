import datetime as dt
import copy
import html as html_lib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge.llm_wiki_manifest import stable_json_hash
from report.elimination_tournament import build_elimination_tournament_payload
from report.elimination_tournament import build_sector_capital_preflight_daily_context
from report.elimination_tournament import build_sector_capital_preflight_payload
from report.elimination_tournament import elimination_tournament_html_path
from report.elimination_tournament import render_elimination_tournament_html
from report.elimination_tournament import render_sector_capital_preflight_html
from report.elimination_tournament import sector_tournament_three_axis_display
from report.elimination_tournament import sector_capital_preflight_html_path
from report.elimination_tournament import _normalize_preflight_payload
from report.elimination_tournament import _sync_preflight_final_action_layer
from report.candidate_decision_evidence import (
    build_sector_diffusion_stage_evidence,
    build_sector_tournament_three_axis,
    canonical_sector_diffusion_stage_evidence_hash,
    canonical_sector_tournament_three_axis_hash,
)


def _embedded_json_payload(rendered_html, script_id):
    match = re.search(
        rf'<script type="application/json" id="{script_id}">(.*?)</script>',
        rendered_html,
        re.S,
    )
    if not match:
        return {}
    return json.loads(html_lib.unescape(match.group(1)))


def _visible_html(rendered_html):
    return re.sub(r'<script\b[^>]*>.*?</script>', "", rendered_html, flags=re.S)


class EliminationTournamentPayloadTest(unittest.TestCase):
    def _workflow(self, target_date="2026-06-12"):
        return {
            "schema_version": "selection_workflow.v1",
            "target_date": target_date,
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

    def test_preflight_payload_rejects_non_tier_final_action_everywhere(self):
        target = {"name": "长电科技", "code": "600584", "sector": "半导体"}
        for position_pct in (33, 40, 60, 75, None):
            with self.subTest(position_pct=position_pct):
                final_action = {
                    "label": "50%条件执行",
                    "target": target,
                    "reason": "旧文案不能替代结构化仓位",
                }
                if position_pct is not None:
                    final_action["position_pct"] = position_pct
                payload = _normalize_preflight_payload(
                    {
                        "schema_version": "sector_capital_preflight.v1",
                        "final_action": final_action,
                        "layers": [],
                    }
                )

                self.assertEqual(payload["final_action"]["position_pct"], 0)
                self.assertEqual(payload["final_action"]["target"], {})
                self.assertEqual(payload["final_action"]["label"], "0%不参与")
                self.assertTrue(
                    all(row["action"] != "允许进入执行窗口" for row in payload["decision_list"])
                )
                self.assertNotEqual(
                    payload["tplus_rehearsal"]["tplus1"]["participation_qualification"],
                    "有条件参与",
                )

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

    def test_stage_evidence_is_read_only_and_shared_with_preflight(self):
        workflow = self._workflow()
        baseline = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            variant="replay",
            selection_workflow=workflow,
            position_decision={"target_position_pct": 0},
        )
        workflow["sector_diffusion_stage_evidence"] = build_sector_diffusion_stage_evidence(
            target_date="2026-06-12",
            local_trend_sector_proof={
                "direction": "化工原料",
                "source_date": "2026-06-12",
                "source_date_matches_target": True,
                "continuity_dates": ["2026-06-11", "2026-06-12"],
                "cross_day_continuity_status": "confirmed",
                "divergence_acceptance_status": "confirmed",
                "internal_expansion_status": "unresolved",
                "competition_comparison_status": "unresolved",
            },
            price_acceptance_rows=[
                {
                    "status": "accepted",
                    "source_date": "2026-06-12",
                    "sector": "化工原料",
                }
            ],
            source_refs=["selection_workflow.local_trend_sector_proof"],
        )
        before_final = copy.deepcopy(workflow["final"])

        tournament = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            variant="replay",
            selection_workflow=workflow,
            position_decision={"target_position_pct": 0},
        )
        preflight = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            variant="replay",
            source_payloads={"selection_workflow": workflow},
            elimination_tournament_payload=tournament,
        )

        self.assertEqual(workflow["final"], before_final)
        self.assertEqual(tournament["final_action"], baseline["final_action"])
        self.assertEqual(
            tournament["sector_diffusion_stage_evidence"],
            workflow["sector_diffusion_stage_evidence"],
        )
        self.assertEqual(
            preflight["sector_diffusion_stage_evidence"],
            tournament["sector_diffusion_stage_evidence"],
        )
        rendered = render_sector_capital_preflight_html(preflight)
        self.assertIn("板块传导阶段证据", rendered)
        self.assertIn("早期确认候选", rendered)
        self.assertIn("下一环", rendered)
        self.assertIn("板块内部扩散", rendered)
        self.assertIn("内部扩散、竞争方向对照", rendered)
        embedded = _embedded_json_payload(rendered, "sector-capital-preflight-payload")
        self.assertEqual(
            embedded["sector_diffusion_stage_evidence"]["artifact_hash"],
            workflow["sector_diffusion_stage_evidence"]["artifact_hash"],
        )

    def test_three_axis_and_ten_questions_are_shared_with_preflight_html(self):
        workflow = self._workflow()
        stage = build_sector_diffusion_stage_evidence(
            target_date="2026-06-12",
            local_trend_sector_proof={
                "direction": "化工原料",
                "source_date": "2026-06-12",
                "source_date_matches_target": True,
                "continuity_dates": ["2026-06-11", "2026-06-12"],
                "cross_day_continuity_status": "confirmed",
                "divergence_acceptance_status": "confirmed",
                "internal_expansion_status": "confirmed",
                "competition_comparison_status": "confirmed",
            },
            price_acceptance_rows=[
                {
                    "status": "accepted",
                    "source_date": "2026-06-12",
                    "sector": "化工原料",
                }
            ],
        )
        workflow["sector_diffusion_stage_evidence"] = stage
        workflow["sector_tournament_three_axis"] = build_sector_tournament_three_axis(
            target_date="2026-06-12",
            sector_diffusion_stage_evidence=stage,
            local_trend_sector_proof={
                "direction": "化工原料",
                "source_date": "2026-06-12",
                "continuity_dates": ["2026-06-11", "2026-06-12"],
                "cross_day_continuity_status": "confirmed",
                "divergence_acceptance_status": "confirmed",
                "internal_expansion_status": "confirmed",
                "competition_comparison_status": "confirmed",
                "competition_state": "单主线聚焦",
                "leader_structure_status": "leader_driven",
                "stage_mainline_evidence": {
                    "cycle_mainline": "化工原料",
                    "cycle_mainline_source_date": "2026-06-11",
                    "daily_attack_line": "机器人",
                    "daily_attack_line_source_date": "2026-06-12",
                    "phase_rotation_status": "confirmed",
                    "phase_rotation_dates": ["2026-06-10", "2026-06-11", "2026-06-12"],
                    "sector_index_slope_status": "upward",
                    "sector_index_slope_dates": ["2026-06-10", "2026-06-11", "2026-06-12"],
                    "sector_index_slope_evidence": [
                        {"text": "板块指数收盘路径持续抬高", "source_date": "2026-06-12"}
                    ],
                    "intraday_rotation_count": 2,
                    "intraday_rotation_source_date": "2026-06-12",
                },
            },
            market_participation_limit={
                "source_date": "2026-06-12",
                "market_state": "震荡混沌",
                "broad_market_confirmation": False,
                "systemic_risk": False,
            },
        )
        before_final = copy.deepcopy(workflow["final"])

        tournament = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            selection_workflow=workflow,
            position_decision={"target_position_pct": 0},
        )
        preflight = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            source_payloads={"selection_workflow": workflow},
            elimination_tournament_payload=tournament,
        )
        rendered = render_sector_capital_preflight_html(preflight)
        embedded = _embedded_json_payload(rendered, "sector-capital-preflight-payload")

        self.assertEqual(workflow["final"], before_final)
        self.assertEqual(
            tournament["sector_tournament_three_axis"],
            workflow["sector_tournament_three_axis"],
        )
        self.assertEqual(
            preflight["sector_tournament_three_axis"],
            workflow["sector_tournament_three_axis"],
        )
        self.assertEqual(
            preflight["dual_cluster_projection"]["artifact_hash"],
            tournament["dual_cluster_projection"]["artifact_hash"],
        )
        self.assertEqual(len(preflight["decision_list"]), 10)
        self.assertEqual(
            embedded["sector_tournament_three_axis"]["artifact_hash"],
            workflow["sector_tournament_three_axis"]["artifact_hash"],
        )
        self.assertIn("空间坐标", rendered)
        self.assertIn("时间坐标", rendered)
        self.assertIn("认知坐标", rendered)
        self.assertIn("阶段主线", rendered)
        self.assertIn("板块资金扩散双群聚", rendered)
        self.assertIn("持续核心、动态冲击、迁移带分开比较", rendered)
        self.assertIn(
            tournament["dual_cluster_projection"]["artifact_hash"],
            rendered,
        )
        visible_rendered = _visible_html(rendered)
        internal_gap_names = [
            item
            for item in preflight["dual_cluster_projection"]["evidence_gaps"]
            if re.match(r"^[A-Za-z][A-Za-z0-9_]*(?:[.:-].*)?$", item)
        ]
        self.assertTrue(internal_gap_names)
        for internal_name in internal_gap_names:
            self.assertNotIn(internal_name, visible_rendered)
        self.assertNotIn("unresolved", visible_rendered)
        self.assertIn("板块指数收盘路径持续抬高", rendered)
        self.assertIn("聚焦主升", rendered)
        self.assertIn("剩余传播空间是否大于已形成共识", rendered)

    def test_three_axis_displays_same_start_path_and_liquidity_context_from_one_artifact(self):
        target_date = "2026-06-12"
        stage_record = {
            "direction": "化工原料",
            "source_date": target_date,
            "stage_start_date": "2026-06-10",
            "trading_calendar": ["2026-06-10", "2026-06-11", target_date],
            "active_trade_dates": ["2026-06-10", target_date],
            "sector_index_path": [
                {
                    "trade_date": "2026-06-10",
                    "index_value": 100.0,
                    "relative_strength_rank": 1,
                    "source_date": target_date,
                },
                {
                    "trade_date": "2026-06-11",
                    "index_value": 90.0,
                    "relative_strength_rank": 1,
                    "source_date": target_date,
                },
                {
                    "trade_date": target_date,
                    "index_value": 110.0,
                    "relative_strength_rank": 1,
                    "source_date": target_date,
                },
            ],
            "relative_strength_metric": "window_return_pct",
            "relative_strength_window": {
                "start_date": "2026-06-10",
                "end_date": target_date,
                "trade_dates": ["2026-06-10", "2026-06-11", target_date],
            },
            "comparison_universe_scope": {
                "directions": ["化工原料", "机器人"],
                "source_date": target_date,
            },
            "comparison_universe": [
                {
                    "direction": "化工原料",
                    "metric_value": 10.0,
                    "source_date": target_date,
                },
                {
                    "direction": "机器人",
                    "metric_value": 5.0,
                    "source_date": target_date,
                },
            ],
            "trend_stock_count": 3,
            "comparable_stock_count": 8,
            "trend_definition_version": "stage-trend-density.v1",
        }
        proof = {
            "direction": "化工原料",
            "source_date": target_date,
            "continuity_dates": ["2026-06-11", target_date],
            "cross_day_continuity_status": "confirmed",
            "divergence_acceptance_status": "confirmed",
            "internal_expansion_status": "confirmed",
            "competition_comparison_status": "confirmed",
            "competition_state": "单主线聚焦",
            "stage_mainline_evidence": {
                "directions": [stage_record],
                "daily_attack_line": "化工原料",
                "daily_attack_line_source_date": target_date,
            },
        }
        stage = build_sector_diffusion_stage_evidence(
            target_date=target_date,
            local_trend_sector_proof=proof,
            price_acceptance_rows=[
                {"status": "accepted", "source_date": target_date, "sector": "化工原料"}
            ],
        )
        evidence = build_sector_tournament_three_axis(
            target_date=target_date,
            sector_diffusion_stage_evidence=stage,
            local_trend_sector_proof=proof,
            market_participation_limit={
                "source_date": target_date,
                "broad_market_confirmation": False,
                "systemic_risk": False,
            },
            liquidity_allocation_facts={
                "current_total_turnover": 800.0,
                "current_turnover_source_date": target_date,
                "previous_total_turnover": 1000.0,
                "previous_turnover_source_date": "2026-06-11",
                "up_count": 1000,
                "down_count": 3000,
                "market_breadth_source_date": target_date,
            },
        )
        display = sector_tournament_three_axis_display(
            evidence,
            trade_date=target_date,
        )
        self.assertIn("区间突破", display["relative_path_text"])
        self.assertIn("区间收益=10.00%", display["relative_path_text"])
        self.assertIn("集中式上涨", display["liquidity_allocation_text"])
        self.assertIn("成交额=缩量", display["liquidity_allocation_text"])
        self.assertTrue(
            any(
                "同起点位置=区间突破" in row.get("evidence", "")
                for row in evidence["ten_questions"]
            )
        )
        self.assertIn(
            "集中式上涨",
            evidence["ten_questions"][2].get("evidence", ""),
        )

        payload = {
            "schema_version": "sector_capital_preflight.v1",
            "trade_date": target_date,
            "sector_tournament_three_axis": evidence,
            "decision_list": [],
            "layers": [],
            "final_action": {},
        }
        rendered = render_sector_capital_preflight_html(payload)
        embedded = _embedded_json_payload(rendered, "sector-capital-preflight-payload")
        self.assertIn(display["relative_path_text"], rendered)
        self.assertIn(display["liquidity_allocation_text"], rendered)
        self.assertEqual(
            embedded["sector_tournament_three_axis"]["artifact_hash"],
            evidence["artifact_hash"],
        )

    def test_three_axis_rejects_future_sources_and_broken_hashes(self):
        workflow = self._workflow()
        stage = build_sector_diffusion_stage_evidence(
            target_date="2026-06-12",
            local_trend_sector_proof={
                "direction": "化工原料",
                "source_date": "2026-06-12",
                "source_date_matches_target": True,
                "continuity_dates": ["2026-06-11", "2026-06-12"],
                "cross_day_continuity_status": "confirmed",
                "divergence_acceptance_status": "confirmed",
                "internal_expansion_status": "unresolved",
                "competition_comparison_status": "unresolved",
            },
            price_acceptance_rows=[
                {"status": "accepted", "source_date": "2026-06-12"}
            ],
        )
        evidence = build_sector_tournament_three_axis(
            target_date="2026-06-12",
            sector_diffusion_stage_evidence=stage,
            local_trend_sector_proof={
                "direction": "化工原料",
                "source_date": "2026-06-12",
                "continuity_dates": ["2026-06-11", "2026-06-12"],
                "cross_day_continuity_status": "confirmed",
                "divergence_acceptance_status": "confirmed",
            },
            market_participation_limit={
                "source_date": "2026-06-12",
                "broad_market_confirmation": False,
                "systemic_risk": False,
            },
        )
        future = copy.deepcopy(evidence)
        future["source_dates"].append("2026-06-13")
        future["artifact_hash"] = canonical_sector_tournament_three_axis_hash(future)
        broken = copy.deepcopy(evidence)
        broken["time_axis"]["stage"] = "趋势延续"
        future_direction = copy.deepcopy(evidence)
        future_direction["direction_source_date"] = "2026-06-13"
        future_direction["input_payload"]["local_trend_sector_proof"][
            "direction_source_date"
        ] = "2026-06-13"
        future_direction["input_hash"] = stable_json_hash(
            future_direction["input_payload"]
        )
        future_direction["artifact_hash"] = (
            canonical_sector_tournament_three_axis_hash(future_direction)
        )
        mismatched_stage = copy.deepcopy(evidence)
        mismatched_stage["stage_mainline"]["cycle_mainline"] = "错配板块"
        mismatched_stage["artifact_hash"] = (
            canonical_sector_tournament_three_axis_hash(mismatched_stage)
        )

        for invalid in (future, broken, future_direction, mismatched_stage):
            with self.subTest(invalid=invalid):
                workflow["sector_tournament_three_axis"] = invalid
                tournament = build_elimination_tournament_payload(
                    trade_date="2026-06-12",
                    selection_workflow=workflow,
                )
                self.assertEqual(tournament["sector_tournament_three_axis"], {})

    def test_stage_evidence_rejects_future_direction_source(self):
        workflow = self._workflow()
        stage = build_sector_diffusion_stage_evidence(
            target_date="2026-06-12",
            local_trend_sector_proof={
                "direction": "化工原料",
                "source_date": "2026-06-12",
                "source_date_matches_target": True,
                "continuity_dates": ["2026-06-11", "2026-06-12"],
                "cross_day_continuity_status": "confirmed",
                "divergence_acceptance_status": "confirmed",
            },
            price_acceptance_rows=[
                {"status": "accepted", "source_date": "2026-06-12"}
            ],
        )
        future_direction = copy.deepcopy(stage)
        future_direction["direction_source_date"] = "2026-06-13"
        future_direction["input_payload"]["local_trend_sector_proof"][
            "direction_source_date"
        ] = "2026-06-13"
        future_direction["input_hash"] = stable_json_hash(
            future_direction["input_payload"]
        )
        future_direction["artifact_hash"] = (
            canonical_sector_diffusion_stage_evidence_hash(future_direction)
        )
        workflow["sector_diffusion_stage_evidence"] = future_direction

        tournament = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            selection_workflow=workflow,
        )

        self.assertEqual(tournament["sector_diffusion_stage_evidence"], {})

    def test_quant_trace_without_observable_facts_reports_no_attributable_trace(self):
        workflow = self._workflow()
        tournament = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            selection_workflow=workflow,
        )
        preflight = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            elimination_tournament_payload=tournament,
        )
        quant_layer = next(
            layer for layer in preflight["layers"] if layer["id"] == "quant_trace"
        )

        self.assertIn("未观察到有来源的可归因痕迹", quant_layer["note"])
        self.assertNotIn("重心抬高、回踩承接和放量不崩", json.dumps(quant_layer, ensure_ascii=False))
        quant_decision = next(
            row
            for row in preflight["decision_list"]
            if row["item"] == "是否有量化参与痕迹"
        )
        self.assertEqual(quant_decision["conclusion"], "未观察到可归因痕迹")
        self.assertEqual(
            quant_decision["evidence"],
            "未观察到有来源的可归因痕迹",
        )
        self.assertNotIn(
            "重心抬高",
            json.dumps(quant_decision, ensure_ascii=False),
        )

    def test_new_three_axis_rebuilds_stale_preflight_decision_list(self):
        workflow = self._workflow()
        stage = build_sector_diffusion_stage_evidence(
            target_date="2026-06-12",
            local_trend_sector_proof={
                "direction": "化工原料",
                "source_date": "2026-06-12",
                "source_date_matches_target": True,
                "continuity_dates": ["2026-06-11", "2026-06-12"],
                "cross_day_continuity_status": "confirmed",
                "divergence_acceptance_status": "confirmed",
                "internal_expansion_status": "confirmed",
                "competition_comparison_status": "confirmed",
            },
            price_acceptance_rows=[
                {"status": "accepted", "source_date": "2026-06-12"}
            ],
        )
        workflow["sector_diffusion_stage_evidence"] = stage
        workflow["sector_tournament_three_axis"] = build_sector_tournament_three_axis(
            target_date="2026-06-12",
            sector_diffusion_stage_evidence=stage,
            local_trend_sector_proof={
                "direction": "化工原料",
                "source_date": "2026-06-12",
                "continuity_dates": ["2026-06-11", "2026-06-12"],
                "cross_day_continuity_status": "confirmed",
                "divergence_acceptance_status": "confirmed",
                "internal_expansion_status": "confirmed",
                "competition_comparison_status": "confirmed",
                "competition_state": "单主线聚焦",
            },
            market_participation_limit={
                "source_date": "2026-06-12",
                "broad_market_confirmation": False,
                "systemic_risk": False,
            },
        )
        tournament = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            selection_workflow=workflow,
        )
        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            sector_capital_preflight={
                "schema_version": "sector_capital_preflight.v1",
                "trade_date": "2026-06-12",
                "decision_list": [
                    {
                        "item": "旧结论",
                        "conclusion": "旧三坐标",
                        "evidence": "旧事实",
                    }
                ],
            },
            elimination_tournament_payload=tournament,
        )

        self.assertEqual(len(payload["decision_list"]), 10)
        self.assertEqual(
            [row["item"] for row in payload["decision_list"]],
            [
                row["question"]
                for row in workflow["sector_tournament_three_axis"]["ten_questions"]
            ],
        )
        self.assertNotIn("旧结论", json.dumps(payload["decision_list"], ensure_ascii=False))

    def test_legacy_decision_list_drops_default_quant_claim_without_facts(self):
        tournament = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            selection_workflow=self._workflow(),
        )
        payload = build_sector_capital_preflight_payload(
            trade_date="2026-06-12",
            sector_capital_preflight={
                "schema_version": "sector_capital_preflight.v1",
                "trade_date": "2026-06-12",
                "decision_list": [
                    {
                        "item": "是否有量化参与痕迹",
                        "conclusion": "待价格行为验证",
                        "evidence": "可观察重心抬高、回踩承接和放量换手",
                    }
                ],
            },
            elimination_tournament_payload=tournament,
        )

        self.assertEqual(
            payload["decision_list"][0]["conclusion"],
            "未观察到可归因痕迹",
        )
        self.assertEqual(
            payload["decision_list"][0]["evidence"],
            "未观察到有来源的可归因痕迹",
        )

    def test_stage_evidence_for_another_date_is_not_reused(self):
        workflow = self._workflow()
        workflow["sector_diffusion_stage_evidence"] = {
            "schema_version": "sector_diffusion_stage_evidence.v1",
            "decision_scope": "explanation_only",
            "formal_effect": "none",
            "target_date": "2026-06-13",
            "direction": "化工原料",
            "stage": "健康扩散候选",
        }

        payload = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            selection_workflow=workflow,
        )

        self.assertEqual(payload["sector_diffusion_stage_evidence"], {})

    def test_stage_evidence_rejects_future_sources_and_broken_hashes(self):
        workflow = self._workflow()
        evidence = build_sector_diffusion_stage_evidence(
            target_date="2026-06-12",
            local_trend_sector_proof={
                "direction": "化工原料",
                "source_date": "2026-06-12",
                "source_date_matches_target": True,
                "continuity_dates": ["2026-06-11", "2026-06-12"],
                "cross_day_continuity_status": "confirmed",
                "divergence_acceptance_status": "confirmed",
                "internal_expansion_status": "confirmed",
                "competition_comparison_status": "confirmed",
            },
            price_acceptance_rows=[
                {
                    "status": "accepted",
                    "source_date": "2026-06-12",
                    "sector": "化工原料",
                }
            ],
        )
        scenarios = []
        future_source = copy.deepcopy(evidence)
        future_source["source_dates"] = ["2026-06-12", "2026-06-13"]
        future_source["artifact_hash"] = canonical_sector_diffusion_stage_evidence_hash(
            future_source
        )
        scenarios.append(future_source)
        broken_input = copy.deepcopy(evidence)
        broken_input["input_payload"]["target_date"] = "2026-06-11"
        broken_input["artifact_hash"] = canonical_sector_diffusion_stage_evidence_hash(
            broken_input
        )
        scenarios.append(broken_input)
        broken_artifact = copy.deepcopy(evidence)
        broken_artifact["stage"] = "早期确认候选"
        scenarios.append(broken_artifact)

        for invalid in scenarios:
            with self.subTest(invalid=invalid):
                workflow["sector_diffusion_stage_evidence"] = invalid
                payload = build_elimination_tournament_payload(
                    trade_date="2026-06-12",
                    selection_workflow=workflow,
                )
                self.assertEqual(payload["sector_diffusion_stage_evidence"], {})

    def test_tournament_rejects_workflow_from_another_date(self):
        workflow = self._workflow("2026-06-13")
        workflow["final"] = {
            "execution_object": {
                "name": "未来样本",
                "code": "600000",
                "sector": "化工原料",
            },
            "position_pct": 50,
            "action_text": "50%条件执行",
            "source_node": "N8",
        }

        payload = build_elimination_tournament_payload(
            trade_date="2026-06-12",
            selection_workflow=workflow,
        )

        self.assertEqual(payload["trade_date"], "2026-06-12")
        self.assertEqual(payload["final_action"]["position_pct"], 0)
        self.assertEqual(payload["final_action"]["target"], {})
        self.assertEqual(payload["sector_diffusion_stage_evidence"], {})
        self.assertIn("来源日期不属于目标日", payload["final_action"]["reason"])

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

    def test_non_tier_final_position_does_not_survive_tournament(self):
        target = {"name": "和远气体", "code": "002971", "sector": "化工原料"}
        for position_pct in (33, 75, None):
            with self.subTest(position_pct=position_pct):
                workflow = self._workflow("2026-07-19")
                workflow["final"] = {
                    "execution_object": target,
                    "position_pct": position_pct,
                    "action_text": "旧文案不能替代结构化仓位",
                    "source_node": "N8",
                }
                payload = build_elimination_tournament_payload(
                    trade_date="2026-07-19",
                    variant="replay",
                    selection_workflow=workflow,
                    final_target_resolution={
                        "new_entry_target": target,
                        "display_target": target,
                        "capital_priority_decision": {
                            "capital_priority": "new_entry",
                        },
                    },
                    position_decision={"target_position_pct": position_pct},
                )

                account_layer = next(
                    layer for layer in payload["layers"] if layer["id"] == "account_execution"
                )
                final_layer = payload["layers"][-1]

                self.assertEqual(payload["final_action"]["label"], "0%不参与")
                self.assertEqual(payload["final_action"]["position_pct"], 0)
                self.assertEqual(payload["final_action"]["target"], {})
                self.assertEqual(account_layer["survivor_count"], 0)
                self.assertEqual(final_layer["survivor_count"], 0)

    def test_same_stock_t_zero_increment_does_not_create_b1(self):
        target = {"name": "和远气体", "code": "002971", "sector": "化工原料"}
        payload = build_elimination_tournament_payload(
            trade_date="2026-07-19",
            variant="replay",
            selection_workflow=self._workflow("2026-07-19"),
            final_target_resolution={
                "new_entry_target": target,
                "display_target": target,
                "capital_priority_decision": {
                    "capital_priority": "same_stock_t",
                    "reason": "同股旧仓已满足当前计划总档",
                },
                "account_exposure_plan": {
                    "schema_version": "position_tier_exposure.v2",
                    "position_fact_status": "confirmed",
                    "old_position_pct": 50,
                    "planned_new_entry_pct": 50,
                    "new_entry_pct": 0,
                    "same_stock_target": True,
                    "same_stock_t": False,
                },
            },
            position_decision={"target_position_pct": 0},
        )

        self.assertEqual(payload["final_action"]["label"], "0%不参与")
        self.assertEqual(payload["final_action"]["position_pct"], 0)
        self.assertEqual(payload["final_action"]["target"], {})
        self.assertEqual(payload["layers"][-1]["survivor_count"], 0)

    def test_tournament_prefers_v2_current_increment_over_planned_total_tier(self):
        target = {"name": "和远气体", "code": "002971", "sector": "化工原料"}
        workflow = self._workflow("2026-07-19")
        workflow["final"] = {
            "execution_object": target,
            "position_pct": 100,
            "action_text": "2x计划总档",
            "source_node": "N8",
        }
        payload = build_elimination_tournament_payload(
            trade_date="2026-07-19",
            variant="replay",
            selection_workflow=workflow,
            final_target_resolution={
                "new_entry_target": target,
                "display_target": target,
                "capital_priority_decision": {
                    "capital_priority": "same_stock_t",
                    "reason": "旧仓已有1x，只新增B2对应的1x",
                },
                "account_exposure_plan": {
                    "schema_version": "position_tier_exposure.v2",
                    "position_fact_status": "confirmed",
                    "old_position_pct": 50,
                    "planned_new_entry_pct": 100,
                    "new_entry_pct": 50,
                    "same_stock_target": True,
                    "same_stock_t": True,
                },
            },
            position_decision={"target_position_pct": 100},
        )

        self.assertEqual(payload["final_action"]["label"], "50%条件执行")
        self.assertEqual(payload["final_action"]["position_pct"], 50)
        self.assertEqual(payload["final_action"]["target"]["code"], "002971")
        self.assertEqual(payload["layers"][-1]["survivor_count"], 1)

    def test_preflight_final_layer_does_not_default_non_tier_action_to_b1(self):
        target = {"name": "和远气体", "code": "002971", "sector": "化工原料"}
        layers = [
            {
                "id": "price_action",
                "survivors": [{"stock": target, "status": "survived"}],
                "entries": [{"stock": target, "status": "survived"}],
            },
            {
                "id": "final_action",
                "input_count": 1,
                "survivor_count": 1,
                "survivors": [{"stock": target, "status": "final_action"}],
                "entries": [{"stock": target, "status": "final_action"}],
            },
        ]
        for position_pct in (33, 75, None):
            with self.subTest(position_pct=position_pct):
                final_action = {"target": target, "label": "50%条件执行"}
                if position_pct is not None:
                    final_action["position_pct"] = position_pct
                synced = _sync_preflight_final_action_layer(layers, final_action)
                final_layer = next(layer for layer in synced if layer["id"] == "final_action")

                self.assertEqual(final_layer["survivor_count"], 0)
                self.assertEqual(final_layer["survivors"], [])

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
        workflow = self._workflow("2026-07-01")
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
        workflow = self._workflow("2026-07-01")
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
    def _payload(self, trade_date="2026-06-12"):
        return {
            "schema_version": "elimination_tournament.v1",
            "trade_date": trade_date,
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
        self.assertIn("过程候选淘汰赛", html)
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
            str(ROOT / "reports" / "replay" / "2026-06-12_过程候选淘汰赛.html"),
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

    def test_leader_reverse_reason_excludes_unrelated_global_sector_evidence(self):
        source = build_elimination_tournament_payload(
            trade_date="2026-07-29",
            variant="replay",
            selection_workflow={
                "schema_version": "selection_workflow.v1",
                "target_date": "2026-07-29",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                    "source_node": "N8",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "明新旭腾", "code": "605068", "sector": "汽车配件"},
                        "source_pools": ["extreme_conviction_list"],
                        "entered_reason": "T字板只作过程证据",
                        "entry_basis": "涨停、热榜或旧龙头记忆不能作为新仓入口",
                        "candidate_origin": "legacy_signal_only",
                        "sector": "汽车配件",
                        "sector_role": "板块锚",
                        "reversal_decision": "降级观察",
                    }
                ],
            },
        )

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-07-29",
            variant="replay",
            source_payloads={
                "daily_context": {
                    "hot_rank_top50": [
                        {"code": "605068", "name": "明新旭腾", "rank": 8, "concepts": ["汽车零部件"]}
                    ],
                    "hot_plates": [{"name": "半导体", "order": 1}],
                    "current_mainline_history_record": {
                        "leading_line": "国产芯片替代",
                        "primary_mainline": "半导体",
                    },
                    "current_sector_turnover_snapshot": {
                        "sector_name": "半导体",
                        "turnover_share_pct": 7.2,
                    },
                }
            },
            elimination_tournament_payload=source,
        )

        market_layer = next(layer for layer in payload["layers"] if layer["id"] == "market_capital_structure")
        entry = market_layer["entries"][0]

        self.assertEqual(entry["stock_label"], "明新旭腾(605068)")
        self.assertEqual(entry["status"], "eliminated")
        self.assertIn("热榜第8", entry["reason"])
        self.assertNotIn("当日记录主线=国产芯片替代", entry["reason"])
        self.assertNotIn("成交跟踪板块=半导体", entry["reason"])

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

    def test_sector_capital_preflight_routes_limit_down_anchor_to_risk_review_first(self):
        source = build_elimination_tournament_payload(
            trade_date="2026-07-16",
            variant="live",
            selection_workflow={
                "schema_version": "selection_workflow.v1",
                "target_date": "2026-07-16",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                    "source_node": "N8",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "华天科技", "code": "002185", "sector": "半导体"},
                        "candidate_origin": "sector_capital_carrier_v1",
                        "source_pools": ["sector_capital_carrier_strategy", "hot_rank", "turnover"],
                        "entered_reason": "半导体进入板块候选；个股证据：热榜关注、容量成交",
                        "sector_role": "板块锚",
                        "reversal_decision": "可作为主对象",
                        "same_day_quote": {
                            "stock_code": "002185",
                            "name": "华天科技",
                            "change_pct": -10.0,
                            "limit_status": "跌停",
                        },
                        "price_action_block_reason": "同日跌幅-10.00%，按跌停/接近跌停处理",
                        "brooks_price_action_judge": {
                            "status": "risk_first",
                            "verdict": "跌停风险优先",
                            "participation_effect": "只按跌停反包专项复核，不新增资格",
                        },
                    }
                ],
            },
        )
        sector_entry = dict(next(layer for layer in source["layers"] if layer["id"] == "sector")["entries"][0])
        stale_positive_entry = {
            **sector_entry,
            "status": "survived",
            "reason": "旧载荷仍保留正向身份",
            "next_basis": "进入下一层",
            "elimination_basis": "",
            "sector_role": "板块锚",
            "reversal_decision": "可作为主对象",
        }
        for layer in source["layers"]:
            if layer["id"] in {"sector_role", "leader_reverse", "price_action"}:
                layer["entries"] = [dict(stale_positive_entry)]

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-07-16",
            variant="live",
            elimination_tournament_payload=source,
        )
        by_id = {layer["id"]: layer for layer in payload["layers"]}
        market_entry = by_id["market_capital_structure"]["entries"][0]

        self.assertEqual(market_entry["stock_label"], "华天科技(002185)")
        self.assertEqual(market_entry["status"], "eliminated")
        self.assertIn("跌停", market_entry["reason"])
        self.assertIn("只作风险复核", market_entry["reason"])
        self.assertNotIn("进入板块资金扩散层", market_entry["next_basis"])
        self.assertEqual(by_id["sector_capital_diffusion"]["input_count"], 0)
        self.assertEqual(by_id["capital_carrier"]["input_count"], 0)
        self.assertEqual(by_id["carrier_role"]["input_count"], 0)
        self.assertEqual(by_id["quant_trace"]["input_count"], 0)
        self.assertEqual(by_id["price_action"]["input_count"], 0)
        self.assertTrue(
            all(
                layer["input_count"] == 0
                and layer["eliminated_count"] == 0
                and layer["survivor_count"] == 0
                for layer in payload["layers"][1:]
            )
        )
        self.assertTrue(
            all(
                not any(entry.get("stock_label") == "华天科技(002185)" for entry in layer.get("entries") or [])
                for layer in payload["layers"][1:]
            )
        )

    def test_sector_capital_preflight_rechecks_limit_down_risk_in_modern_saved_layers(self):
        stale_entry = {
            "stock": {"name": "华天科技", "code": "002185", "sector": "半导体"},
            "stock_label": "华天科技(002185)",
            "status": "survived",
            "reason": "旧载荷仍保留正向身份",
            "next_basis": "进入下一层",
            "elimination_basis": "",
            "sector_role": "板块锚",
            "reversal_decision": "可作为主对象",
            "same_day_quote": {
                "stock_code": "002185",
                "name": "华天科技",
                "change_pct": -10.0,
                "limit_status": "跌停",
            },
        }
        stale_payload = {
            "schema_version": "sector_capital_preflight.v1",
            "trade_date": "2026-07-16",
            "variant": "frozen",
            "final_action": {"label": "0%不参与", "position_pct": 0, "target": {}},
            "layers": [
                {
                    "id": "market_capital_structure",
                    "title": "市场资金结构",
                    "entries": [dict(stale_entry)],
                },
                {
                    "id": "sector_capital_diffusion",
                    "title": "板块资金扩散",
                    "entries": [dict(stale_entry)],
                },
                {
                    "id": "capital_carrier",
                    "title": "板块内资金载体",
                    "entries": [dict(stale_entry)],
                },
            ],
        }

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-07-16",
            variant="frozen",
            sector_capital_preflight=stale_payload,
        )
        by_id = {layer["id"]: layer for layer in payload["layers"]}
        market_entry = by_id["market_capital_structure"]["entries"][0]

        self.assertEqual(market_entry["status"], "eliminated")
        self.assertEqual(market_entry["sector_role"], "风险复核样本")
        self.assertIn("只作风险复核", market_entry["reason"])
        self.assertEqual(by_id["sector_capital_diffusion"]["input_count"], 0)
        self.assertEqual(by_id["capital_carrier"]["input_count"], 0)

    def test_sector_capital_preflight_keeps_complete_limit_down_reversal_plan(self):
        source = build_elimination_tournament_payload(
            trade_date="2026-07-16",
            variant="live",
            selection_workflow={
                "schema_version": "selection_workflow.v1",
                "target_date": "2026-07-16",
                "final": {
                    "execution_object": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                    "position_pct": 50,
                    "action_text": "50%条件执行",
                    "source_node": "N8",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                        "candidate_origin": "sector_first",
                        "source_pools": ["sector_capital_carrier_strategy", "hot_rank"],
                        "status": "最终执行对象",
                        "sector_role": "板块锚",
                        "reversal_decision": "可作为主对象",
                        "same_day_quote": {"change_pct": -10.0, "limit_status": "跌停"},
                        "execution_eligibility": "跌停反包专项",
                        "participation_window": "09:50-10:10跌停反包确认",
                        "cancellation": "继续封死或站不回VWAP就不参与",
                        "fallback_state": "不满足回到0%不参与",
                        "limit_down_reversal_plan": {
                            "status": "complete",
                            "contract_text": "跌停反包专项 / 09:50-10:10跌停反包确认 / 继续封死或站不回VWAP就不参与 / 不满足回到0%不参与",
                            "participation_window": "09:50-10:10跌停反包确认",
                            "cancellation": "继续封死或站不回VWAP就不参与",
                            "fallback_state": "不满足回到0%不参与",
                        },
                    }
                ],
            },
        )

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-07-16",
            variant="live",
            elimination_tournament_payload=source,
        )
        market_entry = next(layer for layer in payload["layers"] if layer["id"] == "market_capital_structure")[
            "entries"
        ][0]

        self.assertEqual(market_entry["status"], "survived")
        self.assertNotEqual(market_entry.get("sector_role"), "风险复核样本")
        self.assertNotIn("只作风险复核", market_entry["reason"])

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
        self.assertIn("板块资金载体差异复核", html)
        self.assertIn("T0同源策略只作差异复核；最终0%不新增明日对象", html)
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
                    "stages": [
                        {
                            "title": "纸面动作",
                            "input_count": 1,
                            "eliminated_count": 0,
                            "survivor_count": 1,
                            "survivors": [
                                {
                                    "label": "长电科技(600584)",
                                    "reason": "板块被资金选择，且主样本具备资金载体证据",
                                }
                            ],
                            "eliminated": [],
                        }
                    ],
                }
            },
            elimination_tournament_payload=self._payload(),
        )

        final_layer = payload["layers"][-1]
        html = render_sector_capital_preflight_html(payload)

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
        self.assertIn("未观察到有来源的可归因痕迹", quant_layer["note"])
        self.assertEqual(final_layer["id"], "final_action")
        self.assertEqual(final_layer["input_count"], 0)
        self.assertEqual(final_layer["survivor_count"], 0)
        self.assertEqual(payload["tplus_rehearsal"]["tplus1"]["participation_qualification"], "只观察承接，不新增参与")
        self.assertIn("板块资金载体差异复核", html)
        self.assertIn("差异复核收口", html)
        self.assertIn("复核样本", html)
        self.assertNotIn("<td>纸面动作</td>", html)
        self.assertNotIn("<td>参与或观察</td>", html)

    def test_sector_capital_preflight_tplus_rehearsal_keeps_confirmed_old_position_visible(self):
        payload = build_sector_capital_preflight_payload(
            trade_date="2026-07-15",
            variant="live",
            source_payloads={
                "final_target_resolution": {
                    "existing_position_target": {
                        "name": "长电科技",
                        "code": "600584",
                        "has_position": True,
                    },
                    "account_exposure_plan": {"position_fact_status": "confirmed"},
                    "capital_priority_decision": {"capital_priority": "wait"},
                }
            },
            elimination_tournament_payload=self._payload("2026-07-15"),
        )

        action = payload["tplus_rehearsal"]["tplus1"]["action"]

        self.assertEqual(action, "不新增参与，只按旧仓预案处理")
        self.assertNotIn("空仓", action)

    def test_sector_capital_preflight_rejects_tournament_from_another_date(self):
        future = self._payload("2026-07-16")
        future["final_action"] = {
            "label": "50%条件执行",
            "position_pct": 50,
            "target": {"name": "未来样本", "code": "600000"},
            "source": "selection_workflow.final",
            "reason": "未来来源动作",
        }

        payload = build_sector_capital_preflight_payload(
            trade_date="2026-07-15",
            elimination_tournament_payload=future,
        )

        self.assertEqual(payload, {})

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
