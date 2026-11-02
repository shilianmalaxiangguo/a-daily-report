import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.formal_account_decision import (
    DECISION_PRODUCT_FREEZE_SCHEMA_VERSION,
    DECISION_PROJECTION_SCHEMA_VERSION,
    FORMAL_ADD_REQUIRED_FIELDS,
    FORMAL_TREND_REQUIRED_FIELDS,
    apply_decision_product_freeze,
    build_decision_product_freeze,
    build_formal_account_decision,
    build_formal_decision_input,
    canonical_decision_product_freeze_hash,
    canonical_decision_projection_hash,
    validate_decision_product_freeze,
)


REPORT_DATE = "2026-08-06"
TRADE_DATES = [
    "2026-08-04",
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
    "2026-08-10",
    "2026-08-11",
]


def _comparison_fields(status="qualified"):
    return {
        "sector_continuity": status,
        "stage_fit": status,
        "carrier_quality": status,
        "upside_space": status,
        "loss_boundary": status,
        "executability": status,
    }


def _candidate(code, *, clear_advantage=False):
    return {
        "stock": {"code": code, "name": f"样本{code}"},
        "sector": "半导体",
        "stock_qualification": "qualified",
        "executability": "qualified",
        "comparison_fields": _comparison_fields(),
        "clear_advantage": clear_advantage,
    }


def _holding(
    code="600000",
    *,
    b1_buy_date="2026-08-05",
    review_date=REPORT_DATE,
    position_pct=50,
    sellable_pct=50,
    planned_exit=None,
    exit_confirmation=None,
    funds_released=False,
):
    row = {
        "stock": {"code": code, "name": f"样本{code}"},
        "decision_date": "2026-08-04",
        "review_date": review_date,
        "b1": {
            "buy_date": b1_buy_date,
            "position_pct": position_pct,
            "sellable_pct": sellable_pct,
            "earliest_sell_date": review_date,
        },
        "exit_confirmation": exit_confirmation or {"status": "unconfirmed"},
        "funds_released": funds_released,
        "source_date": REPORT_DATE,
        "source": "fixture.account",
    }
    if planned_exit is not None:
        row["planned_exit"] = planned_exit
    return row


def _required_conditions(fields):
    return {field: "qualified" for field in fields}


def _facts(
    *,
    report_date=REPORT_DATE,
    candidates=None,
    holdings=None,
    hold_status="qualified",
    add_status="not_qualified",
    replace_status="not_qualified",
    add_code="600000",
    replace_code="600001",
    add_conditions=None,
    trend_status="unresolved",
    trend_code="600000",
    trend_conditions=None,
):
    return {
        "schema_version": "candidate_decision_evidence_facts.v1",
        "report_date": report_date,
        "query_date": report_date,
        "trade_dates": list(TRADE_DATES),
        "sector_qualifications": [
            {
                "sector": "半导体",
                "status": "qualified",
                "source_date": report_date,
                "source": "fixture.sector",
            }
        ],
        "candidates": candidates if candidates is not None else [_candidate("600000")],
        "holdings": holdings if holdings is not None else [_holding()],
        "capital_qualifications": {
            "hold": {"status": hold_status, "stock": {"code": "600000"}},
            "add": {
                "status": add_status,
                "stock": {"code": add_code},
                "required_conditions": (
                    add_conditions
                    if add_conditions is not None
                    else _required_conditions(FORMAL_ADD_REQUIRED_FIELDS)
                ),
            },
            "replace": {"status": replace_status, "stock": {"code": replace_code}},
            "trend_continue": {
                "status": trend_status,
                "stock": {"code": trend_code},
                "required_conditions": (
                    trend_conditions
                    if trend_conditions is not None
                    else _required_conditions(FORMAL_TREND_REQUIRED_FIELDS)
                ),
            },
        },
    }


def _data(**fact_kwargs):
    return {
        "candidate_decision_evidence_facts": _facts(**fact_kwargs),
        "approved_formal_fields": [],
    }


def _workflow(code="600000", position_pct=50):
    stock = {"code": code, "name": f"样本{code}"} if code else {}
    return {
        "schema_version": "selection_workflow.v1",
        "final": {
            "execution_object": stock,
            "position_pct": position_pct if stock else 0,
        },
    }


class FormalAccountDecisionTest(unittest.TestCase):
    def _build(self, data, workflow=None, report_date=REPORT_DATE):
        formal_input = build_formal_decision_input(data, report_date=report_date)
        decision = build_formal_account_decision(
            formal_input,
            selection_workflow=workflow or _workflow(),
            report_date=report_date,
        )
        return formal_input, decision

    def test_candidate_tie_keeps_cash_independent_of_source_order(self):
        candidates = [_candidate("600000"), _candidate("600001")]
        first = build_formal_decision_input(
            _data(candidates=candidates),
            report_date=REPORT_DATE,
        )
        second = build_formal_decision_input(
            _data(candidates=list(reversed(candidates))),
            report_date=REPORT_DATE,
        )

        self.assertEqual(first["candidate_selection"]["status"], "tie_unresolved")
        self.assertEqual(first["candidate_selection"]["winner"], {})
        self.assertEqual(second["candidate_selection"]["status"], "tie_unresolved")
        self.assertEqual(second["candidate_selection"]["winner"], {})

    def test_exactly_one_clear_winner_is_deterministic(self):
        candidates = [_candidate("600000"), _candidate("600001", clear_advantage=True)]
        first = build_formal_decision_input(
            _data(candidates=candidates),
            report_date=REPORT_DATE,
        )
        second = build_formal_decision_input(
            _data(candidates=list(reversed(candidates))),
            report_date=REPORT_DATE,
        )

        self.assertEqual(first["candidate_selection"]["status"], "clear_winner")
        self.assertEqual(first["candidate_selection"]["winner"]["code"], "600001")
        self.assertEqual(first["candidate_selection"], second["candidate_selection"])

    def test_conflicting_duplicate_candidate_is_order_independent_and_not_qualified(self):
        qualified = _candidate("600000", clear_advantage=True)
        conflicted = copy.deepcopy(qualified)
        conflicted["executability"] = "not_qualified"

        first = build_formal_decision_input(
            _data(candidates=[qualified, conflicted]),
            report_date=REPORT_DATE,
        )
        second = build_formal_decision_input(
            _data(candidates=[conflicted, qualified]),
            report_date=REPORT_DATE,
        )

        self.assertEqual(first["candidate_selection"], second["candidate_selection"])
        self.assertEqual(
            first["candidate_selection"]["status"],
            "no_qualified_candidate",
        )
        self.assertEqual(first["candidate_selection"]["winner"], {})

    def test_duplicate_candidate_sources_merge_without_changing_qualification(self):
        first_source = _candidate("600000", clear_advantage=True)
        first_source["evidence_sources"] = ["fixture.a"]
        second_source = copy.deepcopy(first_source)
        second_source["evidence_sources"] = ["fixture.b"]

        formal_input = build_formal_decision_input(
            _data(candidates=[second_source, first_source]),
            report_date=REPORT_DATE,
        )

        self.assertEqual(
            formal_input["candidate_selection"]["status"],
            "clear_winner",
        )
        self.assertEqual(
            formal_input["candidate_ledger"][0]["evidence_sources"],
            ["fixture.a", "fixture.b"],
        )

    def test_each_candidate_uses_its_own_comparison_fields_in_any_source_order(self):
        qualified = _candidate("600000")
        rejected = _candidate("600001")
        rejected["comparison_fields"]["loss_boundary"] = "not_qualified"

        first = build_formal_decision_input(
            _data(candidates=[qualified, rejected]),
            report_date=REPORT_DATE,
        )
        second = build_formal_decision_input(
            _data(candidates=[rejected, qualified]),
            report_date=REPORT_DATE,
        )

        self.assertEqual(first["candidate_selection"], second["candidate_selection"])
        self.assertEqual(
            first["candidate_selection"]["status"],
            "single_qualified",
        )
        self.assertEqual(first["candidate_selection"]["winner"]["code"], "600000")

    def test_b1_buy_day_never_adds_b2(self):
        report_date = "2026-08-05"
        holding = _holding(review_date="2026-08-06")
        holding["source_date"] = report_date
        data = _data(
            report_date=report_date,
            holdings=[holding],
            add_status="qualified",
        )
        data["candidate_decision_evidence_facts"]["trade_dates"] = list(TRADE_DATES)

        _, decision = self._build(data, report_date=report_date)

        self.assertEqual(decision["decision_stage"], "b1_buy_day")
        self.assertEqual(decision["selected_action"], "hold")
        self.assertEqual(decision["b2"]["action"], "not_buy")

    def test_review_day_holds_b1_and_cash_when_add_and_replace_fail(self):
        _, decision = self._build(_data())

        self.assertEqual(decision["selected_action"], "hold")
        self.assertEqual(decision["reason_codes"], ["hold_b1_keep_cash"])
        self.assertEqual(decision["account_exposure"]["current_position_pct"], 50)
        self.assertEqual(decision["account_exposure"]["executable_new_entry_pct"], 0)
        self.assertEqual(
            [name for name, row in decision["outcomes"].items() if row["selected"]],
            ["hold"],
        )

    def test_review_day_adds_same_stock_b2_only_with_all_base_conditions(self):
        _, decision = self._build(_data(add_status="qualified"))

        self.assertEqual(decision["selected_action"], "add")
        self.assertEqual(decision["b2"]["action"], "buy")
        self.assertEqual(decision["b2"]["buy_date"], REPORT_DATE)
        self.assertEqual(decision["b2"]["earliest_sell_date"], "2026-08-07")
        self.assertEqual(decision["account_exposure"]["planned_total_position_pct"], 100)
        self.assertEqual(decision["account_exposure"]["executable_new_entry_pct"], 50)

    def test_missing_one_add_condition_keeps_b1_and_cash(self):
        conditions = _required_conditions(FORMAL_ADD_REQUIRED_FIELDS)
        conditions.pop("risk_adjusted_strongest")

        _, decision = self._build(
            _data(add_status="qualified", add_conditions=conditions)
        )

        self.assertEqual(decision["selected_action"], "hold")
        self.assertEqual(decision["b2"]["action"], "not_buy")

    def test_missing_b1_buy_date_blocks_b2_even_when_review_date_exists(self):
        holding = _holding()
        holding["b1"]["buy_date"] = ""

        formal_input, decision = self._build(
            _data(holdings=[holding], add_status="qualified")
        )

        self.assertIn(
            "b1_buy_date",
            formal_input["position_lifecycle_records"][0]["missing_fields"],
        )
        self.assertNotEqual(decision["selected_action"], "add")
        self.assertEqual(decision["b2"]["action"], "not_buy")

    def test_replacement_waits_for_confirmed_exit_before_reusing_funds(self):
        candidates = [_candidate("600000"), _candidate("600001", clear_advantage=True)]
        data = _data(
            candidates=candidates,
            replace_status="qualified",
            replace_code="600001",
        )

        formal_input, decision = self._build(data, workflow=_workflow("600001"))

        self.assertEqual(formal_input["candidate_selection"]["winner"]["code"], "600001")
        self.assertEqual(decision["selected_action"], "replace")
        self.assertTrue(decision["exit_plan"]["requires_confirmation_before_reuse"])
        self.assertEqual(decision["account_exposure"]["executable_new_entry_pct"], 0)
        self.assertEqual(len(decision["position_lifecycle_records"]), 1)

        released = copy.deepcopy(data)
        released_holding = released["candidate_decision_evidence_facts"]["holdings"][0]
        released_holding["exit_confirmation"] = {
            "status": "confirmed",
            "date": REPORT_DATE,
            "position_pct": 50,
        }
        released_holding["funds_released"] = True
        _, released_decision = self._build(released, workflow=_workflow("600001"))
        self.assertEqual(released_decision["position_lifecycle_records"], [])
        self.assertEqual(released_decision["selected_action"], "replace")
        self.assertEqual(released_decision["account_exposure"]["executable_new_entry_pct"], 50)
        self.assertEqual(released_decision["b1"]["buy_date"], "2026-08-07")
        self.assertEqual(released_decision["b1"]["earliest_sell_date"], "2026-08-10")

    def test_replacement_projects_new_b1_dates_instead_of_old_holding_dates(self):
        candidates = [_candidate("600000"), _candidate("600001", clear_advantage=True)]

        _, decision = self._build(
            _data(
                candidates=candidates,
                replace_status="qualified",
                replace_code="600001",
            ),
            workflow=_workflow("600001"),
        )

        self.assertEqual(decision["b1"]["stock"]["code"], "600001")
        self.assertEqual(decision["b1"]["buy_date"], "2026-08-07")
        self.assertEqual(decision["b1"]["earliest_sell_date"], "2026-08-10")
        self.assertEqual(
            decision["position_lifecycle_dates"],
            {
                "decision_date": REPORT_DATE,
                "b1_buy_date": "2026-08-07",
                "review_date": "2026-08-10",
                "b2_buy_date": "",
                "b1_earliest_sell_date": "2026-08-10",
                "b2_earliest_sell_date": "",
            },
        )

    def test_review_day_planned_exit_goes_to_cash_without_trend_continue(self):
        holding = _holding(
            planned_exit={"date": REPORT_DATE, "reason": "普通交易复核日退出"}
        )

        _, decision = self._build(_data(holdings=[holding]))

        self.assertEqual(decision["selected_action"], "cash")
        self.assertEqual(decision["b1"]["action"], "exit")
        self.assertEqual(decision["exit_plan"]["targets"][0]["sellable_position_pct"], 50)
        self.assertFalse(decision["position_lifecycle_records"][0]["funds_released"])

    def test_due_ordinary_exit_cannot_add_b2(self):
        holding = _holding(
            planned_exit={"date": REPORT_DATE, "reason": "普通交易复核日退出"}
        )

        _, decision = self._build(
            _data(holdings=[holding], add_status="qualified")
        )

        self.assertEqual(decision["selected_action"], "cash")
        self.assertEqual(decision["b1"]["action"], "exit")
        self.assertEqual(decision["b2"]["action"], "not_buy")

    def test_main_uptrend_qualification_keeps_b1_without_auto_b2(self):
        holding = _holding(
            planned_exit={"date": REPORT_DATE, "reason": "普通交易复核日退出"}
        )

        _, decision = self._build(
            _data(
                holdings=[holding],
                trend_status="qualified",
                add_status="not_qualified",
            )
        )

        self.assertEqual(decision["selected_action"], "hold")
        self.assertEqual(decision["b1"]["action"], "hold")
        self.assertEqual(decision["b2"]["action"], "not_buy")

    def test_all_unfinished_a_b_c_holdings_survive_and_released_row_is_removed(self):
        holdings = [
            _holding("600000", position_pct=25, sellable_pct=25),
            _holding("600001", position_pct=25, sellable_pct=25),
            _holding("600002", position_pct=25, sellable_pct=25),
            _holding(
                "600003",
                position_pct=25,
                sellable_pct=25,
                exit_confirmation={
                    "status": "confirmed",
                    "date": REPORT_DATE,
                    "position_pct": 25,
                },
                funds_released=True,
            ),
        ]

        formal_input, decision = self._build(_data(holdings=holdings))

        self.assertEqual(
            [row["stock"]["code"] for row in formal_input["position_lifecycle_records"]],
            ["600000", "600001", "600002"],
        )
        self.assertEqual(decision["account_exposure"]["current_position_pct"], 75)
        self.assertEqual(decision["account_exposure"]["executable_new_entry_pct"], 0)

    def test_confirmed_exit_without_position_pct_does_not_release_holding(self):
        holding = _holding(
            exit_confirmation={"status": "confirmed", "date": REPORT_DATE},
            funds_released=True,
        )

        formal_input, decision = self._build(_data(holdings=[holding]))

        self.assertEqual(len(formal_input["position_lifecycle_records"]), 1)
        self.assertIn(
            "exit_confirmation_position_pct",
            formal_input["position_lifecycle_records"][0]["missing_fields"],
        )
        self.assertEqual(decision["account_exposure"]["current_position_pct"], 50)

    def test_invalid_position_percentage_cannot_create_new_capacity(self):
        holding = _holding(position_pct=120)

        formal_input, decision = self._build(
            _data(holdings=[holding], add_status="qualified")
        )

        self.assertIn(
            "b1_position_pct",
            formal_input["position_lifecycle_records"][0]["missing_fields"],
        )
        self.assertNotEqual(decision["selected_action"], "add")
        self.assertEqual(decision["account_exposure"]["executable_new_entry_pct"], 0)
        self.assertIn("account_exposure_incomplete", decision["missing_fields"])

    def test_hold_qualification_for_one_stock_cannot_authorize_another_stock_add(self):
        data = _data(
            candidates=[_candidate("600001")],
            holdings=[
                _holding("600000", position_pct=25, sellable_pct=25),
                _holding("600001", position_pct=25, sellable_pct=25),
            ],
            add_status="qualified",
            add_code="600001",
        )

        _, decision = self._build(data, workflow=_workflow("600001"))

        self.assertNotEqual(decision["selected_action"], "add")
        self.assertEqual(decision["b2"]["action"], "not_buy")

    def test_b2_bought_on_report_date_is_not_sellable_that_day(self):
        holding = _holding(
            planned_exit={"date": REPORT_DATE, "reason": "普通交易复核日退出"}
        )
        holding["b2"] = {
            "buy_date": REPORT_DATE,
            "position_pct": 50,
            "sellable_pct": 50,
            "earliest_sell_date": "2026-08-07",
        }

        formal_input, decision = self._build(
            _data(
                holdings=[holding],
                hold_status="not_qualified",
            )
        )

        normalized = formal_input["position_lifecycle_records"][0]
        self.assertEqual(normalized["b2"]["sellable_pct"], 0)
        self.assertIn("b2_sellable_pct", normalized["missing_fields"])
        self.assertEqual(
            decision["exit_plan"]["targets"][0]["sellable_position_pct"],
            50,
        )
        self.assertEqual(
            decision["account_exposure"]["closing_target_position_pct"],
            50,
        )

    def test_sellable_percentage_cannot_exceed_leg_position(self):
        holding = _holding(
            position_pct=50,
            sellable_pct=80,
            planned_exit={"date": REPORT_DATE, "reason": "普通交易复核日退出"},
        )

        formal_input, decision = self._build(
            _data(holdings=[holding], hold_status="not_qualified")
        )

        normalized = formal_input["position_lifecycle_records"][0]
        self.assertEqual(normalized["b1"]["sellable_pct"], 50)
        self.assertIn("b1_sellable_pct", normalized["missing_fields"])
        self.assertEqual(
            decision["exit_plan"]["targets"][0]["sellable_position_pct"],
            50,
        )

    def test_exposure_above_100_is_reported_without_expanding_position(self):
        holding = _holding(
            b1_buy_date="2026-08-04",
            review_date="2026-08-05",
            position_pct=75,
            sellable_pct=75,
        )
        holding["b2"] = {
            "buy_date": "2026-08-05",
            "position_pct": 50,
            "sellable_pct": 50,
            "earliest_sell_date": REPORT_DATE,
        }

        _, decision = self._build(
            _data(holdings=[holding], add_status="qualified")
        )

        self.assertEqual(decision["account_exposure"]["current_position_pct"], 125)
        self.assertEqual(decision["account_exposure"]["executable_new_entry_pct"], 0)
        self.assertIn("account_exposure_above_100", decision["missing_fields"])

    def test_empty_approval_list_keeps_new_evidence_read_only(self):
        base = _data(add_status="not_qualified")
        changed = copy.deepcopy(base)
        changed_facts = changed["candidate_decision_evidence_facts"]
        changed_facts["volume_price_evidence"] = {
            "stocks": [{"stock": {"code": "600000"}, "price_acceptance": "accepted"}]
        }
        changed["decision_robustness_version_health"] = {
            "version_health": "sensitive",
        }

        _, first = self._build(base)
        _, second = self._build(changed)

        self.assertEqual(first, second)
        self.assertEqual(first["approved_formal_fields"], [])

    def test_frozen_decision_projection_builds_validates_and_hashes_stably(self):
        data = _data(add_status="not_qualified")
        formal_input, formal_account = self._build(data)
        workflow = _workflow()
        workflow["target_date"] = REPORT_DATE
        workflow["candidate_pool"] = [
            {
                "candidate_row_id": "row-600000",
                "stock": {"code": "600000", "name": "样本600000"},
            }
        ]
        data.update(
            {
                "selection_workflow": workflow,
                "position_decision": {
                    "target_position_pct": 0,
                    "execution_nature": "保留B1",
                },
                "formal_decision_input": formal_input,
                "formal_account_decision": formal_account,
                "final_target_resolution": {
                    "new_entry_target": {},
                    "old_position_plan": {"action": "hold"},
                    "account_exposure_plan": {
                        "old_position_actual_pct": 50,
                        "planned_new_entry_pct": 50,
                        "new_entry_pct": 0,
                        "tomorrow_closing_target_position_pct": 50,
                    },
                    "account_options": formal_account["outcomes"],
                    "formal_account_decision": formal_account,
                },
                "two_layer_decision_payload": {
                    "schema_version": "two_layer_decision_payload.v1",
                    "final_object": {},
                },
                "candidate_decision_evidence": {
                    "schema_version": "candidate_decision_evidence.v1",
                    "report_date": REPORT_DATE,
                    "artifact_hash": "candidate-hash",
                    "volume_price_evidence": {
                        "scope": "stock",
                        "price_acceptance": "unconfirmed",
                    },
                },
                "decision_robustness_version_health": {
                    "schema_version": "decision_robustness_version_health.v1",
                    "report_date": REPORT_DATE,
                    "artifact_hash": "robustness-hash",
                },
                "research_execution_evidence": {
                    "schema_version": "research_execution_evidence.v1",
                    "target_date": REPORT_DATE,
                    "artifact_hash": "research-hash",
                },
                "knowledge": {
                    "llm_wiki": {
                        "target_date": REPORT_DATE,
                        "knowledge_trace": {"trace_hash": "trace-hash"},
                    }
                },
            }
        )

        first = build_decision_product_freeze(data, target_date=REPORT_DATE)
        second = build_decision_product_freeze(
            copy.deepcopy(data),
            target_date=REPORT_DATE,
        )

        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], DECISION_PRODUCT_FREEZE_SCHEMA_VERSION)
        projection = first["decision_projection"]
        self.assertEqual(projection["schema_version"], DECISION_PROJECTION_SCHEMA_VERSION)
        self.assertEqual(projection["candidate_row_id"], "row-600000")
        self.assertEqual(projection["account_action"], "hold")
        self.assertEqual(
            set(projection["account_outcomes"]),
            {"hold", "add", "replace", "cash"},
        )
        self.assertEqual(projection["account_outcomes"]["hold"]["selected"], True)
        self.assertEqual(projection["account_position"]["current_position_pct"], 50)
        self.assertEqual(projection["b1"], formal_account["b1"])
        self.assertEqual(projection["b2"], formal_account["b2"])
        self.assertEqual(projection["formal_account_decision"], formal_account)
        self.assertEqual(
            first["read_only_evidence"]["volume_price_evidence"]["price_acceptance"],
            "unconfirmed",
        )
        valid, errors = validate_decision_product_freeze(
            first,
            target_date=REPORT_DATE,
        )
        self.assertTrue(valid, errors)

        consumed = {}
        applied, review = apply_decision_product_freeze(
            consumed,
            first,
            target_date=REPORT_DATE,
        )
        self.assertTrue(applied, review)
        self.assertEqual(consumed["selection_workflow"], workflow)
        self.assertIsNot(consumed["selection_workflow"], projection["selection_workflow"])

        tampered = copy.deepcopy(first)
        tampered_projection = tampered["decision_projection"]
        tampered_projection["formal_account_decision"]["selected_action"] = "cash"
        tampered_projection["projection_hash"] = canonical_decision_projection_hash(
            tampered_projection
        )
        tampered["decision_projection_hash"] = tampered_projection["projection_hash"]
        tampered["freeze_hash"] = canonical_decision_product_freeze_hash(tampered)
        valid, errors = validate_decision_product_freeze(
            tampered,
            target_date=REPORT_DATE,
        )
        self.assertFalse(valid)
        self.assertIn("decision_product_freeze_formal_account_hash_mismatch", errors)

    def test_partial_freeze_removes_missing_roots_instead_of_materializing_them(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "target_date": REPORT_DATE,
            "final": {"position_pct": 0},
        }
        freeze = build_decision_product_freeze(
            {"selection_workflow": workflow},
            target_date=REPORT_DATE,
            artifact_origin="legacy_snapshot_mapping",
        )
        self.assertEqual(freeze["availability"], "partial")
        valid, errors = validate_decision_product_freeze(
            freeze,
            target_date=REPORT_DATE,
        )
        self.assertTrue(valid, errors)
        consumed = {
            "selection_workflow": {"stale": True},
            "final_target_resolution": {"stale": True},
            "formal_decision_input": {"stale": True},
            "formal_account_decision": {"stale": True},
        }

        applied, review = apply_decision_product_freeze(
            consumed,
            freeze,
            target_date=REPORT_DATE,
        )

        self.assertTrue(applied, review)
        self.assertEqual(consumed["selection_workflow"], workflow)
        self.assertNotIn("final_target_resolution", consumed)
        self.assertNotIn("formal_decision_input", consumed)
        self.assertNotIn("formal_account_decision", consumed)


if __name__ == "__main__":
    unittest.main()
