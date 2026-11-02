import json
import sys
import threading
import time
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.daily_report_consensus import (
    BATCH_SCHEMA_VERSION,
    FUNNEL_SCHEMA_VERSION,
    OUTPUT_FILENAMES,
    REVIEW_COUNT,
    ConsensusContractError,
    apply_consensus_to_selection_workflow,
    build_frozen_batch,
    build_funnel_records,
    build_period_windows,
    build_review_prompt,
    build_review_request,
    calculate_consensus,
    canonical_json,
    consensus_output_directory,
    export_training_candidates,
    filter_time_valid_facts,
    funnel_summary,
    make_llm_reviewer,
    render_consensus_summary,
    review_timing_summary,
    run_consensus_reviews,
    sha256_file,
    sha256_json,
    validate_review_response,
    write_consensus_outputs,
)


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "daily_report_consensus"


def _load_fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _build_fixture_batch(fixture, *, run_id=None, seed_supported=False):
    return build_frozen_batch(
        target_date=fixture["target_date"],
        query_date=fixture["query_date"],
        formal_input=fixture["formal_input"],
        selection_workflow=fixture["selection_workflow"],
        facts=fixture["facts"],
        required_fact_ids=fixture.get("required_fact_ids", ["market_width"]),
        decision_cutoff_at=fixture["decision_cutoff_at"],
        collected_at=fixture["decision_cutoff_at"],
        run_id=run_id or fixture["name"],
        model_version="fixture-model-v1",
        seed_supported=seed_supported,
        review_context={"frozen_sample": fixture["name"]},
    )


def _fixture_reviewer(fixture, seen=None):
    def review(request):
        if seen is not None:
            seen.append(deepcopy(request))
        result = fixture["review_results"][request["sequence"] - 1]
        if "raise" in result:
            raise RuntimeError(result["raise"])
        return deepcopy(result)

    return review


def _entry_consensus_data(target_date="2026-08-21"):
    comparison_fields = {
        "sector_continuity": "qualified",
        "stage_fit": "qualified",
        "carrier_quality": "qualified",
        "upside_space": "qualified",
        "loss_boundary": "qualified",
        "executability": "qualified",
    }
    stock = {"name": "甲公司", "code": "600001", "sector": "示例板块"}
    return {
        "position_context_provided": True,
        "candidate_decision_evidence_facts": {
            "schema_version": "candidate_decision_evidence_facts.v1",
            "report_date": target_date,
            "query_date": target_date,
            "source_date": target_date,
            "available_at": f"{target_date}T15:30:00+08:00",
            "collected_at": f"{target_date}T17:55:00+08:00",
            "decision_cutoff_at": f"{target_date}T18:00:00+08:00",
            "trade_dates": [
                "2026-08-20",
                target_date,
                "2026-08-24",
                "2026-08-25",
            ],
            "sector_qualifications": [
                {
                    "sector": "示例板块",
                    "status": "qualified",
                    "source_date": target_date,
                    "source": "fixture.sector",
                }
            ],
            "candidates": [
                {
                    "stock": stock,
                    "sector": "示例板块",
                    "stock_qualification": "qualified",
                    "executability": "qualified",
                    "comparison_fields": comparison_fields,
                    "clear_advantage": True,
                    "evidence_sources": ["fixture.candidate"],
                }
            ],
            "holdings": [],
            "capital_qualifications": {
                "hold": {"status": "not_applicable"},
                "add": {"status": "not_applicable"},
                "replace": {"status": "qualified", "stock": stock},
                "cash": {"status": "qualified"},
                "trend_continue": {"status": "not_applicable"},
            },
        },
        "selection_workflow": {
            "schema_version": "selection_workflow.v1",
            "target_date": target_date,
            "candidate_pool": [{"stock": stock, "candidate_row_id": "fixture:600001"}],
            "final": {
                "execution_object": stock,
                "position_pct": 50,
                "action_text": "50%条件执行",
                "failure_conditions": [],
                "fail_action": "0%不参与",
                "b1_only": True,
                "b2_allowed": False,
            },
        },
        "candidate_decision_evidence": {
            "schema_version": "candidate_decision_evidence.v1",
            "report_date": target_date,
            "volume_price_evidence": {"price_acceptance": "confirmed"},
            "availability": "complete",
        },
        "decision_robustness_version_health": {
            "schema_version": "decision_robustness_version_health.v1",
            "report_date": target_date,
            "availability": "complete",
        },
        "research_execution_evidence": {
            "schema_version": "research_execution_evidence.v1",
            "target_date": target_date,
            "availability": "complete",
        },
        "knowledge": {
            "llm_wiki": {
                "target_date": target_date,
                "knowledge_trace": {"trace_hash": "fixture-trace"},
            }
        },
    }


def _confirm_entry_proposal(_request):
    return {
        "vote": "confirm_existing",
        "reason": "提案与冻结事实一致",
        "missing_facts": [],
        "alternative_mentions": [],
        "provider_request_id": "fixture-request",
    }


class DailyReportConsensusContractTest(unittest.TestCase):
    def test_hash_is_canonical_sha256(self):
        left = {"b": [2, 1], "a": {"x", "y"}}
        right = {"a": {"y", "x"}, "b": [2, 1]}
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(sha256_json(left), sha256_json(right))
        self.assertEqual(len(sha256_json(left)), 64)

    def test_stable_fixture_uses_one_frozen_input_and_exactly_ten_reviews(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        seen = []

        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture, seen))
        consensus = calculate_consensus(batch, reviews)

        self.assertEqual(batch["schema_version"], BATCH_SCHEMA_VERSION)
        self.assertEqual(len(reviews), REVIEW_COUNT)
        self.assertEqual([item["sequence"] for item in reviews], list(range(1, 11)))
        self.assertEqual({item["input_hash"] for item in reviews}, {batch["input_hash"]})
        self.assertEqual(
            {item["proposal_hash"] for item in reviews}, {batch["proposal_hash"]}
        )
        self.assertEqual({item["input_hash"] for item in seen}, {batch["input_hash"]})
        self.assertEqual(consensus["status"], fixture["expected"]["status"])
        self.assertEqual(consensus["confirmation_count"], 7)
        self.assertEqual(consensus["denominator"], 10)
        self.assertTrue(consensus["stable_consensus"])
        self.assertFalse(consensus["kelly_eligible"])

    def test_seven_confirmations_keep_original_proposal_and_alternative_cannot_replace_it(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        consensus = calculate_consensus(batch, reviews)

        committed = apply_consensus_to_selection_workflow(
            fixture["selection_workflow"], consensus
        )

        self.assertEqual(
            committed["final"]["execution_object"],
            fixture["selection_workflow"]["final"]["execution_object"],
        )
        self.assertEqual(committed["final"]["position_pct"], 50)
        self.assertEqual(committed["proposed_final"], committed["final"])
        self.assertNotIn("乙公司", json.dumps(committed["final"], ensure_ascii=False))

    def test_six_confirmations_clear_only_the_new_entry_proposal(self):
        fixture = _load_fixture("divergent_6_of_10.json")
        workflow = deepcopy(fixture["selection_workflow"])
        workflow["existing_position_context"] = {
            "name": "既有持仓",
            "action": "按原规则处理",
        }
        batch = _build_fixture_batch(fixture)
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        consensus = calculate_consensus(batch, reviews)

        committed = apply_consensus_to_selection_workflow(workflow, consensus)

        self.assertEqual(consensus["confirmation_count"], 6)
        self.assertEqual(consensus["ratio_label"], "6/10")
        self.assertEqual(consensus["formal_decision_mode"], "clear_new_entry")
        self.assertFalse(consensus["stable_consensus"])
        self.assertEqual(committed["final"]["execution_object"], {})
        self.assertEqual(committed["final"]["position_pct"], 0)
        self.assertEqual(
            committed["existing_position_context"], workflow["existing_position_context"]
        )

    def test_one_failure_remains_in_the_fixed_denominator(self):
        fixture = _load_fixture("review_failure.json")
        batch = _build_fixture_batch(fixture)
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        consensus = calculate_consensus(batch, reviews)

        self.assertEqual(len(reviews), 10)
        self.assertEqual(reviews[-1]["status"], "failed")
        self.assertIsNone(reviews[-1]["vote"])
        self.assertEqual(consensus["confirmation_count"], 9)
        self.assertEqual(consensus["denominator"], 10)
        self.assertEqual(consensus["failure_count"], 1)
        self.assertEqual(consensus["status"], "unstable")
        self.assertFalse(consensus["stable_consensus"])

    def test_no_object_requires_seven_valid_no_object_votes_and_is_not_a_selection_hit(self):
        fixture = _load_fixture("no_object_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        consensus = calculate_consensus(batch, reviews)

        self.assertEqual(consensus["status"], "stable_no_object")
        self.assertEqual(consensus["confirmation_count"], 7)
        self.assertEqual(consensus["selection_hit_count"], 0)
        self.assertEqual(consensus["formal_decision_mode"], "commit_no_object")

    def test_confirmation_with_missing_facts_is_contract_invalid(self):
        cases = (
            ("object", "confirm_existing"),
            ("no_object", "confirm_no_object"),
        )
        for proposal_kind, vote in cases:
            with self.subTest(proposal_kind=proposal_kind):
                with self.assertRaises(ConsensusContractError) as error:
                    validate_review_response(
                        {
                            "vote": vote,
                            "reason": "仍缺关键事实",
                            "missing_facts": ["板块续证"],
                            "alternative_mentions": [],
                        },
                        proposal_kind=proposal_kind,
                    )
                self.assertIn("missing_facts_reported", error.exception.reason_codes)

    def test_alternative_mention_turns_confirmation_into_denial(self):
        parsed = validate_review_response(
            {
                "vote": "confirm_existing",
                "reason": "另一对象更符合事实",
                "missing_facts": [],
                "alternative_mentions": [
                    {"name": "乙公司", "code": "600002", "evidence": "承接更强"}
                ],
            },
            proposal_kind="object",
        )

        self.assertEqual(parsed["vote"], "deny_existing")
        self.assertEqual(parsed["alternative_mentions"][0]["code"], "600002")

    def test_account_action_field_makes_one_review_invalid_and_the_batch_unstable(self):
        fixture = _load_fixture("stable_7_of_10.json")
        fixture["review_results"][0]["position_pct"] = 50
        batch = _build_fixture_batch(fixture)
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        consensus = calculate_consensus(batch, reviews)

        self.assertEqual(reviews[0]["status"], "contract_invalid")
        self.assertIsNone(reviews[0]["vote"])
        self.assertEqual(consensus["status"], "unstable")
        self.assertEqual(consensus["denominator"], 10)

    def test_hash_mismatch_stops_formal_decision(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        reviews[4]["input_hash"] = "0" * 64

        consensus = calculate_consensus(batch, reviews)

        self.assertFalse(consensus["integrity_valid"])
        self.assertEqual(consensus["formal_decision_mode"], "stop")
        self.assertIn("hash_mismatch", consensus["reason_codes"])
        with self.assertRaises(ConsensusContractError):
            apply_consensus_to_selection_workflow(
                fixture["selection_workflow"], consensus
            )

    def test_critical_fact_available_after_cutoff_stops_before_reviews(self):
        fixture = _load_fixture("critical_fact_missing.json")
        batch = _build_fixture_batch(fixture)

        self.assertEqual(batch["input_status"], "invalid")
        self.assertIn("required_fact_missing", batch["input_issue_codes"])
        self.assertEqual(batch["facts"]["time_valid_count"], 0)
        self.assertIn(
            "future_available", batch["facts"]["records"][0]["reason_codes"]
        )
        with self.assertRaises(ConsensusContractError):
            run_consensus_reviews(batch, lambda request: {})

    def test_empty_required_fact_and_next_day_cutoff_are_rejected(self):
        fixture = _load_fixture("stable_7_of_10.json")
        empty_fact_fixture = deepcopy(fixture)
        empty_fact_fixture["facts"][0]["value"] = None
        empty_batch = _build_fixture_batch(empty_fact_fixture)
        self.assertEqual(empty_batch["input_status"], "invalid")
        self.assertIn(
            "quality_failed", empty_batch["facts"]["records"][0]["reason_codes"]
        )
        self.assertIn("required_fact_missing", empty_batch["input_issue_codes"])

        next_day_fixture = deepcopy(fixture)
        next_day_fixture["decision_cutoff_at"] = "2026-08-22T09:00:00+08:00"
        next_day_batch = _build_fixture_batch(next_day_fixture)
        self.assertEqual(next_day_batch["input_status"], "invalid")
        self.assertIn(
            "decision_cutoff_date_mismatch", next_day_batch["input_issue_codes"]
        )

    def test_review_response_requires_json_object_and_known_fields(self):
        with self.assertRaises(ConsensusContractError):
            validate_review_response("not-json", proposal_kind="object")
        with self.assertRaises(ConsensusContractError):
            validate_review_response(
                {"vote": "confirm_existing", "reason": "确认", "buy_action": "买入"},
                proposal_kind="object",
            )
        parsed = validate_review_response(
            "```json\n{\"vote\":\"confirm_existing\",\"reason\":\"确认\","
            "\"missing_facts\":[],\"alternative_mentions\":[]}\n```",
            proposal_kind="object",
        )
        self.assertEqual(parsed["vote"], "confirm_existing")
        for invalid_response in (
            {
                "vote": "confirm_existing",
                "reason": 42,
                "missing_facts": [],
                "alternative_mentions": [],
            },
            {
                "vote": "confirm_existing",
                "reason": "确认",
                "missing_facts": [42],
                "alternative_mentions": [],
            },
            {
                "vote": "confirm_existing",
                "reason": "确认",
                "missing_facts": [],
                "alternative_mentions": [],
                "provider_request_id": 42,
            },
        ):
            with self.subTest(response=invalid_response):
                with self.assertRaises(ConsensusContractError):
                    validate_review_response(
                        invalid_response,
                        proposal_kind="object",
                    )

    def test_prompt_is_scoped_to_reviewing_the_existing_proposal(self):
        fixture = _load_fixture("stable_7_of_10.json")
        request = build_review_request(_build_fixture_batch(fixture), 1)
        prompt = build_review_prompt(request)

        self.assertIn("只复核既有唯一提案", prompt)
        self.assertIn("不能把它改成新提案", prompt)
        self.assertEqual(request["seed"], None)

    def test_supported_seed_is_unique_and_transport_id_overrides_model_text(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture, seed_supported=True)
        calls = []
        lock = threading.Lock()

        class SeedService:
            model = "fixture-model-v1"
            seed_supported = True

            def chat_with_metadata(
                self,
                prompt,
                *,
                system_prompt,
                temperature,
                max_tokens,
                max_retries,
                seed,
            ):
                with lock:
                    calls.append(seed)
                return {
                    "content": json.dumps(
                        {
                            "vote": "confirm_existing",
                            "reason": "冻结事实支持原提案",
                            "missing_facts": [],
                            "alternative_mentions": [],
                            "provider_request_id": "model-forged-id",
                        },
                        ensure_ascii=False,
                    ),
                    "provider_request_id": f"transport-{seed}",
                    "seed_supported": True,
                    "seed": seed,
                    "effective_config": {
                        "model": self.model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                }

        reviews = run_consensus_reviews(batch, make_llm_reviewer(SeedService()))

        registered = batch["review_variability"]["seeds"]
        self.assertEqual(len(registered), 10)
        self.assertEqual(len(set(registered)), 10)
        self.assertEqual(sorted(calls), sorted(registered))
        self.assertTrue(all(item["status"] == "completed" for item in reviews))
        self.assertEqual(
            {item["provider_request_id"] for item in reviews},
            {f"transport-{seed}" for seed in registered},
        )
        self.assertNotIn(
            "model-forged-id",
            {item["provider_request_id"] for item in reviews},
        )

    def test_transport_id_survives_invalid_model_response(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        lock = threading.Lock()
        request_count = 0

        class InvalidResponseService:
            model = "fixture-model-v1"
            seed_supported = False

            def chat_with_metadata(
                self,
                prompt,
                *,
                system_prompt,
                temperature,
                max_tokens,
                max_retries,
                seed,
            ):
                nonlocal request_count
                with lock:
                    request_count += 1
                    request_id = f"transport-invalid-{request_count}"
                return {
                    "content": json.dumps(
                        {
                            "vote": "confirm_existing",
                            "reason": "正文含账户字段",
                            "missing_facts": [],
                            "alternative_mentions": [],
                            "provider_request_id": "model-forged-id",
                            "position_pct": 50,
                        },
                        ensure_ascii=False,
                    ),
                    "provider_request_id": request_id,
                    "seed_supported": False,
                    "seed": None,
                    "effective_config": {
                        "model": self.model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                }

        reviews = run_consensus_reviews(
            batch,
            make_llm_reviewer(InvalidResponseService()),
        )

        self.assertEqual(request_count, 10)
        self.assertTrue(all(item["status"] == "contract_invalid" for item in reviews))
        self.assertTrue(
            all(item["provider_request_id"].startswith("transport-invalid-") for item in reviews)
        )
        self.assertNotIn(
            "model-forged-id",
            {item["provider_request_id"] for item in reviews},
        )

    def test_effective_model_temperature_and_max_tokens_must_match_batch(self):
        fixture = _load_fixture("stable_7_of_10.json")
        expected = {
            "model": "fixture-model-v1",
            "temperature": 0.7,
            "max_tokens": 500,
        }
        mismatches = {
            "model": "other-model",
            "temperature": 0.6,
            "max_tokens": 501,
        }
        for field, mismatched_value in mismatches.items():
            with self.subTest(field=field):
                batch = _build_fixture_batch(fixture, run_id=f"mismatch-{field}")

                class MismatchService:
                    model = "fixture-model-v1"
                    seed_supported = False

                    def chat_with_metadata(
                        self,
                        prompt,
                        *,
                        system_prompt,
                        temperature,
                        max_tokens,
                        max_retries,
                        seed,
                    ):
                        actual = dict(expected)
                        actual[field] = mismatched_value
                        return {
                            "content": json.dumps(
                                {
                                    "vote": "confirm_existing",
                                    "reason": "冻结事实支持原提案",
                                    "missing_facts": [],
                                    "alternative_mentions": [],
                                },
                                ensure_ascii=False,
                            ),
                            "provider_request_id": f"mismatch-{field}",
                            "seed_supported": False,
                            "seed": None,
                            "effective_config": actual,
                        }

                reviews = run_consensus_reviews(
                    batch,
                    make_llm_reviewer(MismatchService()),
                )

                self.assertTrue(
                    all(item["status"] == "contract_invalid" for item in reviews)
                )
                self.assertTrue(
                    all(
                        "review_config_mismatch" in item["reason_codes"]
                        for item in reviews
                    )
                )
                self.assertTrue(
                    all(item["provider_request_id"] == f"mismatch-{field}" for item in reviews)
                )

    def test_legacy_string_reviewer_service_remains_compatible(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        calls = []

        def chat(
            prompt,
            *,
            system_prompt,
            temperature,
            max_tokens,
            max_retries,
        ):
            calls.append(prompt)
            return json.dumps(
                {
                    "vote": "confirm_existing",
                    "reason": "冻结事实支持原提案",
                    "missing_facts": [],
                    "alternative_mentions": [],
                },
                ensure_ascii=False,
            )

        service = SimpleNamespace(
            model="fixture-model-v1",
            seed_supported=False,
            chat=chat,
        )
        reviews = run_consensus_reviews(batch, make_llm_reviewer(service))

        self.assertEqual(len(calls), 10)
        self.assertTrue(all(item["status"] == "completed" for item in reviews))
        self.assertTrue(all(item["provider_request_id"] == "" for item in reviews))

    def test_reviews_never_exceed_five_concurrent_calls(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        lock = threading.Lock()
        active = 0
        maximum = 0

        def reviewer(request):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.01)
            with lock:
                active -= 1
            return fixture["review_results"][request["sequence"] - 1]

        reviews = run_consensus_reviews(batch, reviewer, max_concurrency=9)

        self.assertEqual(len(reviews), 10)
        self.assertLessEqual(maximum, 5)
        self.assertGreaterEqual(maximum, 2)

    def test_single_review_timeout_is_not_retried_or_removed(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        calls = []

        def reviewer(request):
            calls.append(request["sequence"])
            if request["sequence"] == 1:
                time.sleep(0.03)
            return fixture["review_results"][request["sequence"] - 1]

        reviews = run_consensus_reviews(
            batch,
            reviewer,
            review_timeout_seconds=0.005,
            batch_timeout_seconds=1,
        )
        consensus = calculate_consensus(batch, reviews)

        self.assertEqual(sorted(calls), list(range(1, 11)))
        self.assertEqual(reviews[0]["status"], "timeout")
        self.assertIsNone(reviews[0]["vote"])
        self.assertFalse(consensus["stable_consensus"])

    def test_batch_timeout_marks_unstarted_requests_without_claiming_model_calls(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        calls = []

        def reviewer(request):
            calls.append(request["sequence"])
            time.sleep(0.12)
            return fixture["review_results"][request["sequence"] - 1]

        reviews = run_consensus_reviews(
            batch,
            reviewer,
            max_concurrency=2,
            review_timeout_seconds=1,
            batch_timeout_seconds=0.02,
        )
        consensus = calculate_consensus(batch, reviews)
        time.sleep(0.13)

        self.assertEqual(sorted(calls), [1, 2])
        self.assertEqual(consensus["model_request_count"], 2)
        self.assertEqual(sum(item["request_started"] for item in reviews), 2)
        self.assertTrue(
            all(
                item["status"] == "failed"
                and item["reason_codes"] == ["review_not_started"]
                for item in reviews[2:]
            )
        )

    def test_completed_future_after_batch_deadline_is_timeout_not_confirmation(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)

        def reviewer(request):
            if request["sequence"] == 1:
                time.sleep(0.01)
            return fixture["review_results"][request["sequence"] - 1]

        reviews = run_consensus_reviews(
            batch,
            reviewer,
            max_concurrency=1,
            review_timeout_seconds=1,
            batch_timeout_seconds=0.001,
        )
        consensus = calculate_consensus(batch, reviews)

        self.assertEqual(reviews[0]["status"], "timeout")
        self.assertEqual(reviews[0]["failure_reason"], "整批复核超时")
        self.assertIsNone(reviews[0]["vote"])
        self.assertFalse(consensus["stable_consensus"])


class DailyReportConsensusTimeAndOutputTest(unittest.TestCase):
    def test_time_filter_normalizes_offsets_and_excludes_future_or_conflicting_facts(self):
        facts = [
            {
                "fact_id": "included",
                "trade_date": "2026-08-21",
                "source_date": "2026-08-21",
                "query_date": "2026-08-21",
                "available_at": "2026-08-21T08:00:00Z",
                "value": {"status": "included"},
            },
            {
                "fact_id": "future",
                "trade_date": "2026-08-21",
                "source_date": "2026-08-21",
                "query_date": "2026-08-21",
                "available_at": "2026-08-21T10:00:01Z",
                "value": {"status": "future"},
            },
            {
                "fact_id": "wrong-source",
                "trade_date": "2026-08-22",
                "source_date": "2026-08-22",
                "query_date": "2026-08-21",
                "available_at": "2026-08-21T08:00:00Z",
                "value": {"status": "wrong-source"},
            },
            {
                "fact_id": "missing-time",
                "trade_date": "2026-08-21",
                "value": {"status": "missing-time"},
            },
        ]

        valid, excluded, records = filter_time_valid_facts(
            facts,
            decision_cutoff_at="2026-08-21T18:00:00+08:00",
            target_date="2026-08-21",
            query_date="2026-08-21",
        )

        self.assertEqual([item["fact_id"] for item in valid], ["included"])
        self.assertEqual(len(excluded), 3)
        reasons = {item["fact_id"]: item["reason_codes"] for item in records}
        self.assertIn("future_available", reasons["future"])
        self.assertIn("source_date_conflict", reasons["wrong-source"])
        self.assertIn("missing_timestamp", reasons["missing-time"])

    def test_period_windows_use_settled_trade_dates_and_preserve_missing_metrics(self):
        settled = [
            "2026-08-10",
            "2026-08-11",
            "2026-08-12",
            "2026-08-13",
            "2026-08-14",
            "2026-08-17",
            "2026-08-18",
            "2026-08-19",
            "2026-08-20",
            "2026-08-21",
        ]
        metrics = {item: {"count": index} for index, item in enumerate(settled)}
        metrics.pop("2026-08-19")

        windows = build_period_windows(
            target_date="2026-08-21",
            settled_trade_dates=settled,
            metrics_by_date=metrics,
        )

        self.assertEqual(windows["week"]["dates_used"], settled[-5:])
        self.assertEqual(windows["recent_7"]["dates_used"], settled[-7:])
        self.assertEqual(windows["recent_10"]["dates_used"], settled)
        self.assertEqual(windows["recent_20"]["dates_used"], settled)
        self.assertEqual(windows["recent_7"]["missing_dates"], ["2026-08-19"])
        missing_row = next(
            row
            for row in windows["recent_7"]["rows"]
            if row["trade_date"] == "2026-08-19"
        )
        self.assertIsNone(missing_row["metrics"])

    def test_unsettled_target_is_not_inserted_into_today_or_recent_windows(self):
        windows = build_period_windows(
            target_date="2026-08-24",
            settled_trade_dates=["2026-08-20", "2026-08-21"],
            metrics_by_date={"2026-08-21": {"count": 1}},
        )

        self.assertEqual(windows["today"]["status"], "unsettled")
        self.assertEqual(windows["today"]["dates_used"], [])
        self.assertEqual(windows["recent_7"]["covered_to"], "2026-08-21")

    def test_funnel_has_six_stages_and_no_cross_unit_conversion(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        consensus = calculate_consensus(batch, reviews)
        records = build_funnel_records(
            batch,
            reviews,
            consensus,
            outcome={
                "t1_settled": True,
                "t2_settled": True,
                "facts_complete": True,
                "quality_passed": True,
                "t1_trade_date": "2026-08-24",
                "t2_trade_date": "2026-08-25",
                "posterior_available_at": "2026-08-25T15:30:00+08:00",
                "outcome_hash": "f" * 64,
            },
        )
        summary = funnel_summary(records)

        self.assertEqual(summary["schema_version"], FUNNEL_SCHEMA_VERSION)
        self.assertEqual(
            set(summary["stages"]),
            {
                "raw_facts",
                "time_valid_facts",
                "complete_reviews",
                "stable_consensus",
                "matured_outcomes",
                "training_candidates",
            },
        )
        self.assertIsNone(summary["cross_unit_conversion_rates"])
        self.assertEqual(summary["stages"]["raw_facts"]["unit"], "fact")
        self.assertEqual(summary["stages"]["complete_reviews"]["unit"], "batch")
        self.assertEqual(summary["stages"]["matured_outcomes"]["included"], 1)
        self.assertEqual(summary["stages"]["training_candidates"]["included"], 1)

    def test_funnel_excludes_hash_mismatch_and_unverifiable_outcome(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        reviews[0]["input_hash"] = "0" * 64
        consensus = calculate_consensus(batch, reviews)

        records = build_funnel_records(
            batch,
            reviews,
            consensus,
            outcome={
                "t1_settled": True,
                "t2_settled": True,
                "facts_complete": True,
                "quality_passed": True,
                "t1_trade_date": fixture["target_date"],
                "t2_trade_date": "2026-08-25",
                "posterior_available_at": "2026-08-25T15:30:00+08:00",
                "outcome_hash": "invalid",
            },
        )
        complete_reviews = next(
            item for item in records if item["stage"] == "complete_reviews"
        )
        matured_outcome = next(
            item for item in records if item["stage"] == "matured_outcomes"
        )

        self.assertEqual(complete_reviews["status"], "excluded")
        self.assertIn("hash_mismatch", complete_reviews["reason_codes"])
        self.assertEqual(matured_outcome["status"], "excluded")
        self.assertIn("outcome_date_invalid", matured_outcome["reason_codes"])
        self.assertIn("outcome_hash_invalid", matured_outcome["reason_codes"])

    def test_five_outputs_are_utf8_without_bom_and_directory_is_append_only(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture, run_id="fixed-run")
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        consensus = calculate_consensus(batch, reviews)
        windows = build_period_windows(
            target_date=fixture["target_date"],
            settled_trade_dates=[fixture["target_date"]],
            metrics_by_date={fixture["target_date"]: {"stable": True}},
        )
        funnel_records = build_funnel_records(batch, reviews, consensus)
        funnel = funnel_summary(funnel_records)
        batch = {
            **batch,
            "consensus": consensus,
            "periods": windows,
            "funnel": funnel,
        }
        summary = render_consensus_summary(
            batch, reviews, consensus, periods=windows, funnel=funnel
        )

        with TemporaryDirectory() as temporary:
            output_dir = consensus_output_directory(
                temporary,
                target_date=fixture["target_date"],
                run_id="fixed-run",
                replay=True,
            )
            result = write_consensus_outputs(
                output_dir,
                batch=batch,
                reviews=reviews,
                summary_text=summary,
                run_records=[{"status": "success", "run_id": "fixed-run"}],
                funnel_records=funnel_records,
            )

            self.assertEqual(set(path.name for path in output_dir.iterdir()), set(OUTPUT_FILENAMES))
            self.assertEqual(set(result["sha256"]), set(OUTPUT_FILENAMES))
            for filename in OUTPUT_FILENAMES:
                payload = (output_dir / filename).read_bytes()
                self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))
                payload.decode("utf-8")
                self.assertEqual(result["sha256"][filename], sha256_file(output_dir / filename))
            self.assertEqual(
                len((output_dir / "reviews.jsonl").read_text(encoding="utf-8").splitlines()),
                10,
            )
            self.assertIn("唯一结论", summary)
            self.assertIn("共识比例：7/10", summary)
            with self.assertRaises(FileExistsError):
                write_consensus_outputs(
                    output_dir,
                    batch=batch,
                    reviews=reviews,
                    summary_text=summary,
                    run_records=[],
                    funnel_records=funnel_records,
                )

    def test_summary_has_aggregate_statistics_and_exactly_ten_plain_text_rows(self):
        fixture = _load_fixture("stable_7_of_10.json")
        batch = _build_fixture_batch(fixture)
        reviews = run_consensus_reviews(batch, _fixture_reviewer(fixture))
        for index, review in enumerate(reviews, start=1):
            review["duration_seconds"] = index
        reviews[7]["reason"] = "价格 | 承接\n偏弱"
        consensus = calculate_consensus(batch, reviews)

        summary = render_consensus_summary(batch, reviews, consensus)
        table_lines = (
            summary.split("十次结果表（纯文本）：\n", 1)[1]
            .split("\n\n", 1)[0]
            .splitlines()
        )

        self.assertIn(
            "十次统计：\n"
            "对象 | 确认数 | 否决数 | 失败数 | 共识结果 | P50(s) | 最慢(s)\n"
            "甲公司(600001) | 7/10 | 3 | 0 | 稳定共识 | 5.500 | 10.000",
            summary,
        )
        self.assertEqual(table_lines[0], "序号 | 结果 | 状态 | 耗时(s) | 理由")
        self.assertEqual(len(table_lines), 11)
        self.assertEqual(
            [line.split(" | ", 1)[0] for line in table_lines[1:]],
            [str(index) for index in range(1, 11)],
        )
        self.assertIn(
            "8 | 否决既有提案 | 已完成 | 8.000 | 价格 / 承接 偏弱",
            table_lines,
        )

    def test_training_export_is_explicit_and_never_starts_training(self):
        samples = [
            {
                "sample_id": "selection-1",
                "proposal_kind": "object",
                "stable_consensus": True,
                "outcome_complete": True,
                "input_hash": "a" * 64,
                "outcome_hash": "b" * 64,
            },
            {
                "sample_id": "abstention-1",
                "proposal_kind": "no_object",
                "stable_consensus": True,
                "outcome_complete": True,
                "input_hash": "c" * 64,
                "outcome_hash": "d" * 64,
            },
            {
                "sample_id": "immature",
                "proposal_kind": "object",
                "stable_consensus": True,
                "outcome_complete": False,
                "input_hash": "e" * 64,
                "outcome_hash": "",
            },
        ]
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "training-v1.jsonl"
            result = export_training_candidates(
                path,
                samples,
                export_version="v1",
                generated_at="2026-09-03T18:00:00+08:00",
            )
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            quality = json.loads(
                Path(result["quality_path"]).read_text(encoding="utf-8")
            )

            self.assertEqual(result["row_count"], 2)
            self.assertEqual(result["excluded_count"], 1)
            self.assertFalse(result["training_started"])
            self.assertEqual(
                {item["sample_kind"] for item in rows}, {"selection", "abstention"}
            )
            self.assertFalse(quality["training_started"])

    def test_timing_summary_reports_p50_slowest_and_failures(self):
        rows = [
            {"status": "completed", "duration_seconds": 1},
            {"status": "completed", "duration_seconds": 3},
            {"status": "failed", "duration_seconds": 2},
        ]
        summary = review_timing_summary(rows)
        self.assertEqual(summary["p50_seconds"], 2)
        self.assertEqual(summary["slowest_seconds"], 3)
        self.assertEqual(summary["failure_count"], 1)


class DailyReportConsensusEntryIntegrationTest(unittest.TestCase):
    def test_default_is_sector_and_short_generator_is_retired(self):
        import daily_report_entry_demo as entry
        self.assertEqual(entry._resolve_daily_report_output_mode(SimpleNamespace(output_mode=None)), "sector")
        with patch.object(entry, "run_consensus_reviews") as reviews, self.assertRaises(RuntimeError):
            entry._run_daily_report_consensus_short({}, "2026-08-21", run_mode="replay")
        reviews.assert_not_called()


if __name__ == "__main__":
    unittest.main()
