import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.reasoning_decision_support import (
    build_reasoning_input_packet,
    compute_input_hash,
    derive_unique_action_target_from_reasoning_decision,
    validate_reasoning_decision,
)


class ReasoningDecisionSupportTest(unittest.TestCase):
    def test_builds_stable_reasoning_input_packet_from_snapshot(self):
        snapshot = {
            "market_fit_calibration": {"fit_label": "主线有效，池子偏窄"},
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "mainline_capacity_regime_summary": {
                    "mainline_capacity": "双线孕育",
                    "mainline_regime": "混沌接力",
                    "primary_line": "半导体",
                    "other_lines": "电力 / 化学制品",
                    "confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
                    "sector_relationship_state": "半导体尝试替代，电力退成背景线待确认",
                    "mainline_process": "启动",
                    "tomorrow_action": "先看资金是否继续选择半导体；背景线只观察回流",
                },
                "double_mainline_summary": {
                    "cycle_mainline": "半导体",
                    "daily_attack_line": "半导体",
                    "relationship": "周期主线与当天主攻线一致",
                    "tomorrow_action": "继续围绕半导体观察承接",
                },
            },
            "current_sector_turnover_snapshot": {
                "date": "2026-04-24",
                "sector_name": "半导体",
                "turnover_share_pct": 18.1,
            },
            "recent_sector_turnover_history": [
                {"date": "2026-04-23", "sector_name": "半导体", "turnover_share_pct": 15.8}
            ],
            "market_performance_evidence": {
                "funding_activity": {"regime": "资金活跃期", "top50_share_pct": 21.0},
                "new_high_attack": {"leading_sectors": ["半导体"], "all_a_share_pct": 2.52},
                "summary": "资金雨量处于资金活跃期，雨区主要在半导体。",
                "decision_boundary": "单指标不直接给买入或加仓。",
            },
            "candidate_pool": [
                {
                    "code": "300613",
                    "name": "富瀚微",
                    "sector": "半导体",
                    "qualification": "观察，等10点确认",
                    "evidence": {"承接": "明日验证承接", "资金痕迹": "主线资金主动进攻"},
                }
            ],
            "source_status": {"ths_sector": "ok"},
        }

        packet = build_reasoning_input_packet("2026-04-24", snapshot, final_gate={"final_action": "观察"})

        self.assertEqual(packet["schema_version"], "reasoning_input.v1")
        self.assertEqual(packet["target_date"], "2026-04-24")
        self.assertEqual(packet["mainline_snapshot"]["current_mainline"], "半导体")
        self.assertEqual(packet["mainline_snapshot"]["mainline_capacity_regime_summary"]["mainline_regime"], "混沌接力")
        self.assertEqual(packet["mainline_snapshot"]["mainline_capacity_regime_summary"]["primary_line"], "半导体")
        self.assertEqual(packet["market_base"]["market_performance_evidence"]["funding_activity"]["regime"], "资金活跃期")
        self.assertIn("半导体", packet["market_base"]["market_performance_evidence"]["new_high_attack"]["leading_sectors"])
        self.assertIn("单指标不直接", packet["market_base"]["market_performance_evidence"]["decision_boundary"])
        self.assertEqual(packet["candidate_pool"][0]["id"], "300613")
        self.assertEqual(packet["candidate_pool"][0]["name"], "富瀚微")
        self.assertEqual(packet["execution_contract"]["final_action"], "观察")
        self.assertEqual(packet["source_status"]["ths_sector"], "ok")

    def test_reasoning_input_packet_derives_capacity_regime_from_legacy_double_mainline(self):
        packet = build_reasoning_input_packet(
            "2026-04-24",
            {
                "mainline_turnover_summary": {
                    "current_mainline": "半导体",
                    "double_mainline_summary": {
                        "cycle_mainline": "半导体",
                        "daily_attack_line": "半导体",
                        "relationship": "周期主线与当天主攻线一致",
                        "tomorrow_action": "继续围绕半导体观察承接",
                    },
                }
            },
        )

        summary = packet["mainline_snapshot"]["mainline_capacity_regime_summary"]
        self.assertEqual(summary["mainline_capacity"], "容量待累计")
        self.assertEqual(summary["mainline_regime"], "单主线聚焦")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["sector_relationship_state"], "周期主线与当天主攻线一致")

    def test_reasoning_input_packet_includes_mainline_attack_evidence_summary(self):
        packet = build_reasoning_input_packet(
            "2026-04-24",
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "candidate_lines": ["电力"],
                        "background_lines": [],
                        "relationship_hint": "双主线竞争",
                        "evidence_labels": ["资金净流入靠前", "批量涨停"],
                        "confirmation_evidence": "半导体资金净流入靠前，涨停更集中",
                        "evidence_gaps": [],
                    }
                }
            },
        )

        self.assertEqual(
            packet["mainline_snapshot"]["mainline_attack_evidence_summary"]["primary_line"],
            "半导体",
        )

    def test_compute_input_hash_is_order_stable_for_dict_keys(self):
        left = {"b": 2, "a": {"d": 4, "c": 3}}
        right = {"a": {"c": 3, "d": 4}, "b": 2}

        self.assertEqual(compute_input_hash(left), compute_input_hash(right))

    def test_packet_input_hash_can_be_recomputed_from_full_packet(self):
        packet = build_reasoning_input_packet(
            "2026-04-24",
            {
                "mainline_turnover_summary": {"current_mainline": "半导体"},
                "candidate_pool": [{"code": "300613", "name": "富瀚微"}],
            },
        )

        self.assertEqual(packet["input_hash"], compute_input_hash(packet))

    def _packet(self):
        return build_reasoning_input_packet(
            "2026-04-24",
            {
                "mainline_turnover_summary": {"current_mainline": "半导体"},
                "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
            },
            final_gate={"final_action": "观察"},
        )

    def _valid_decision(self, packet):
        return {
            "schema_version": "reasoning_decision.v1",
            "target_date": packet["target_date"],
            "input_hash": packet["input_hash"],
            "prompt_version": "manual-current-conversation-v1",
            "reasoning_effort": "xhigh",
            "model_source": "manual",
            "action": "observe",
            "mainline_state": "strengthening",
            "unique_target": None,
            "conclusion": "主线仍需确认，只观察承接。",
            "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
            "trigger_conditions": ["10点后主线继续放量"],
            "failure_conditions": ["主线回落"],
            "excluded_candidates": [{"id": "300613", "name": "富瀚微", "reason": "60分钟确认未完成"}],
            "confidence": "medium",
        }

    def test_validates_well_formed_reasoning_decision(self):
        packet = self._packet()
        result = validate_reasoning_decision(packet, self._valid_decision(packet))

        self.assertTrue(result["passed"], result["findings"])

    def test_rejects_unique_target_outside_candidate_pool(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["unique_target"] = "999999"

        result = validate_reasoning_decision(packet, decision)

        self.assertIn("unique_target_not_in_candidate_pool", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_rejects_unknown_evidence_field(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["evidence"] = [{"field": "unknown.path", "summary": "不可验证证据"}]

        result = validate_reasoning_decision(packet, decision)

        self.assertIn("evidence_field_unknown", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_rejects_conditional_entry_without_trigger_and_failure(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["action"] = "conditional_entry"
        decision["unique_target"] = "300613"
        decision["trigger_conditions"] = []

        result = validate_reasoning_decision(packet, decision)

        self.assertIn("conditional_entry_missing_conditions", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_rejects_low_confidence_aggressive_action(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["action"] = "conditional_entry"
        decision["unique_target"] = "300613"
        decision["confidence"] = "low"

        result = validate_reasoning_decision(packet, decision)

        self.assertIn("low_confidence_aggressive_action", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_requires_xhigh_reasoning_effort(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["reasoning_effort"] = "high"

        result = validate_reasoning_decision(packet, decision)

        self.assertIn("invalid_reasoning_effort", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_rejects_missing_required_decision_fields(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        for key in [
            "prompt_version",
            "reasoning_effort",
            "conclusion",
            "evidence",
            "trigger_conditions",
            "failure_conditions",
            "excluded_candidates",
        ]:
            decision.pop(key)

        result = validate_reasoning_decision(packet, decision)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("required_field_missing", codes)
        self.assertFalse(result["passed"])

    def test_accepts_unique_target_with_surrounding_whitespace(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["action"] = "conditional_entry"
        decision["unique_target"] = " 300613 "

        result = validate_reasoning_decision(packet, decision)

        self.assertTrue(result["passed"], result["findings"])

    def test_derivation_blocks_conditional_entry_with_missing_or_invalid_confidence(self):
        base_decision = {
            "action": "conditional_entry",
            "unique_target": "300613",
            "trigger_conditions": ["10点确认"],
            "failure_conditions": ["主线回落"],
        }
        for confidence in (None, "", "invalid"):
            with self.subTest(confidence=confidence):
                decision = dict(base_decision)
                if confidence is not None:
                    decision["confidence"] = confidence
                snapshot = {
                    "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                    "reasoning_decision": decision,
                }

                self.assertEqual(derive_unique_action_target_from_reasoning_decision(snapshot), {})

    def test_derives_unique_action_target_with_participation_window_fields(self):
        snapshot = {
            "candidate_pool": [
                {
                    "code": "300613",
                    "name": "富瀚微",
                    "sector": "半导体",
                    "participation_window": "竞价表态 + 回封参与",
                    "participation_window_type": "auction_reseal",
                }
            ],
            "reasoning_decision": {
                "action": "conditional_entry",
                "unique_target": "300613",
                "confidence": "medium",
                "handoff_buying_evidence": "clear",
            },
        }

        target = derive_unique_action_target_from_reasoning_decision(snapshot)

        self.assertEqual(target["participation_window"], "09:30-09:35")
        self.assertEqual(target["participation_window_type"], "auction_reseal")
        self.assertEqual(target["required_steps"], ["竞价表态", "开盘前几分钟承接", "回封/打板"])
        self.assertEqual(target["fallback_state"], "不满足回到0%")
        self.assertIn("竞价表态", target["condition"])

    def test_derives_fast_unique_action_target_from_short_auction_window(self):
        snapshot = {
            "candidate_pool": [
                {
                    "code": "300613",
                    "name": "富瀚微",
                    "sector": "半导体",
                    "participation_window": "竞价表态",
                }
            ],
            "reasoning_decision": {
                "action": "conditional_entry",
                "unique_target": "300613",
                "confidence": "medium",
                "handoff_buying_evidence": "clear",
            },
        }

        target = derive_unique_action_target_from_reasoning_decision(snapshot)

        self.assertEqual(target["participation_window"], "09:30-09:35")
        self.assertEqual(target["participation_window_type"], "auction_reseal")
        self.assertEqual(target["required_steps"], ["竞价表态", "开盘前几分钟承接", "回封/打板"])


if __name__ == "__main__":
    unittest.main()
