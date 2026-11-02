from __future__ import annotations

import datetime
import math
from copy import deepcopy
from typing import Any

from knowledge.llm_wiki_manifest import is_sha256, stable_json_hash


SCHEMA_VERSION = "decision_robustness_version_health.v1"
FACT_SCHEMA_VERSION = "decision_robustness_version_health_facts.v1"
DECISION_SCOPE = "explanation_only"
FORMAL_EFFECT = "none"

FACT_LAYERS = ("market", "sector", "stock", "account")
FACT_STATUSES = {"observed", "missing", "conflicted"}
EVIDENCE_QUALITIES = {"measured", "recorded", "story_only"}
REGISTERED_PERTURBATION_KINDS = (
    "real_data_error",
    "date_mismatch",
    "missing_range",
    "historical_conflict",
)
VERSION_HYPOTHESES = (
    "old_version_healthy",
    "old_version_weakening",
    "new_version_pending_confirmation",
    "facts_insufficient",
)

_ALLOWED_METRICS = {
    "market": {"market_breadth", "core_concentration"},
    "sector": {"sector_diffusion", "rear_rank_acceptance", "new_direction_cluster"},
    "stock": {"core_price_acceptance"},
    "account": {
        "position_lifecycle",
        "capital_availability",
        "execution_confirmation",
        "funds_release",
    },
}

_REQUIRED_EVALUATION_METRICS = (
    "fewer_losses",
    "fewer_gains",
    "max_drawdown",
    "expected_return",
    "trade_count",
    "incorrectly_blocked_b2",
    "missed_right_tail",
    "unsellable_risk",
    "opportunity_cost",
)

_EMPTY_APPROVED_FORMAL_FIELDS_HASH = stable_json_hash({"fields": []})

_FROZEN_SAMPLE_SPLIT = {
    "schema_version": "decision_robustness_sample_split.v1",
    "frozen_at": "2026-08-07",
    "discovery": {
        "start_date": "2026-03-31",
        "end_date": "2026-06-30",
        "purpose": "fact_and_hypothesis_discovery",
        "result_access": "closed",
    },
    "calibration": {
        "start_date": "2026-07-01",
        "end_date": "2026-08-07",
        "purpose": "registered_field_calibration",
        "result_access": "closed",
    },
    "holdout": {
        "start_date": "2026-08-10",
        "end_date": "2026-12-31",
        "purpose": "out_of_sample_evaluation",
        "result_access": "unread",
    },
}

_FROZEN_EVALUATION_PLAN = {
    "schema_version": "decision_robustness_evaluation_plan.v1",
    "frozen_at": "2026-08-07",
    "executor_issue": "08-07-cross-regime-replay-model-retirement",
    "status": "frozen_not_run",
    "baseline_system": {
        "id": "formal_decision_without_robustness_fields",
        "source_policy": "same_target_date_facts",
    },
    "candidate_rule": {
        "id": "robustness_version_health_explanation_candidate",
        "approved_formal_fields": [],
        "formal_effect": "none",
    },
    "same_source_walk_forward": {
        "mode": "rolling_origin",
        "source_policy": "baseline_and_candidate_share_identical_sources",
        "holdout_policy": "single_pass_after_rule_freeze",
    },
    "ablations": [
        "without_decision_robustness",
        "without_version_health",
        "without_market_layer",
        "without_sector_layer",
        "without_stock_layer",
        "without_account_layer",
    ],
    "regimes": [
        "broad_advance",
        "core_concentration",
        "rotation",
        "systemic_decline",
    ],
    "cost_model": {
        "transaction_costs": "required",
        "sellability": "required",
        "account_capacity": "required",
    },
    "metrics": list(_REQUIRED_EVALUATION_METRICS),
    "results_access": "not_started",
    "formal_effect": "none",
}

_PERTURBATION_REGISTRATION_SOURCE = (
    "08-07-decision-robustness-version-health-evidence.research.frozen_registry"
)
_FROZEN_PERTURBATION_REGISTRY = [
    {
        "registry_id": "real_data_error.market.market_breadth.v1",
        "perturbation_id": "perturb_market_breadth",
        "kind": "real_data_error",
        "layer": "market",
        "registration_status": "pre_registered",
        "registered_at": "2026-08-07",
        "registration_source": _PERTURBATION_REGISTRATION_SOURCE,
        "affected_fields": ["facts_by_layer.market.market_breadth"],
        "allowed_change": {"basis": "target_date_source_correction"},
        "evidence_refs": ["market_breadth"],
    },
    {
        "registry_id": "date_mismatch.sector.sector_diffusion.v1",
        "perturbation_id": "sector_date_mismatch",
        "kind": "date_mismatch",
        "layer": "sector",
        "registration_status": "pre_registered",
        "registered_at": "2026-08-07",
        "registration_source": _PERTURBATION_REGISTRATION_SOURCE,
        "affected_fields": ["facts_by_layer.sector.sector_diffusion"],
        "allowed_change": {"basis": "source_date_differs_from_target_date"},
        "evidence_refs": ["sector_diffusion"],
    },
    {
        "registry_id": "missing_range.stock.core_price_acceptance.v1",
        "perturbation_id": "perturb_core_price_acceptance",
        "kind": "missing_range",
        "layer": "stock",
        "registration_status": "pre_registered",
        "registered_at": "2026-08-07",
        "registration_source": _PERTURBATION_REGISTRATION_SOURCE,
        "affected_fields": ["facts_by_layer.stock.core_price_acceptance"],
        "allowed_change": {"basis": "documented_target_date_coverage_gap"},
        "evidence_refs": ["core_price_acceptance"],
    },
    {
        "registry_id": "historical_conflict.account.position_lifecycle.v1",
        "perturbation_id": "perturb_position_lifecycle",
        "kind": "historical_conflict",
        "layer": "account",
        "registration_status": "pre_registered",
        "registered_at": "2026-08-07",
        "registration_source": _PERTURBATION_REGISTRATION_SOURCE,
        "affected_fields": ["facts_by_layer.account.position_lifecycle"],
        "allowed_change": {"basis": "conflicting_dated_sources"},
        "evidence_refs": ["position_lifecycle"],
    },
]
_FROZEN_PERTURBATION_REGISTRY_BY_ID = {
    row["registry_id"]: row for row in _FROZEN_PERTURBATION_REGISTRY
}

_FROZEN_RESEARCH_PLAN = {
    "registered_perturbation_kinds": list(REGISTERED_PERTURBATION_KINDS),
    "perturbation_registry": deepcopy(_FROZEN_PERTURBATION_REGISTRY),
    "initial_sample_profile": {
        "positive_sample_count": 1,
        "total_sample_count": 3,
        "observed_regimes": ["single_stock_volume_price_paths"],
        "source_date": "2026-08-07",
        "source": "08-06-position-allocation-evidence-payload.same_source_replay",
        "readiness": "insufficient",
    },
    "sample_split": _FROZEN_SAMPLE_SPLIT,
    "evaluation_plan": _FROZEN_EVALUATION_PLAN,
    "approved_formal_fields": [],
    "approved_formal_fields_hash": _EMPTY_APPROVED_FORMAL_FIELDS_HASH,
}
FROZEN_RESEARCH_PLAN_HASH = stable_json_hash(_FROZEN_RESEARCH_PLAN)

_REQUIRED_ARTIFACT_FIELDS = {
    "report_date": str,
    "target_date": str,
    "query_date": str,
    "source_dates": dict,
    "source_hashes": dict,
    "facts_by_layer": dict,
    "registered_perturbations": list,
    "perturbation_registry": list,
    "decision_robustness": dict,
    "version_hypotheses": list,
    "unresolved_distinctions": list,
    "next_review": dict,
    "sample_split": dict,
    "sample_profile": dict,
    "sample_sufficiency": dict,
    "evaluation_plan": dict,
    "approved_formal_fields": list,
    "approved_formal_fields_hash": str,
    "fact_bundle_warnings": list,
    "missing_fields": list,
    "warnings": list,
    "input_hash": str,
    "availability": str,
    "artifact_hash": str,
}

_FACT_FIELDS = {
    "fact_id",
    "metric",
    "subject",
    "status",
    "value",
    "source_date",
    "source",
    "supports",
    "contradicts",
    "distinguishes",
    "missing_fields",
    "evidence_quality",
    "research_only",
}
_REGISTERED_PERTURBATION_FIELDS = {
    "registry_id",
    "perturbation_id",
    "kind",
    "layer",
    "registration_status",
    "target_date",
    "registered_at",
    "registration_source",
    "source_date",
    "affected_fields",
    "allowed_change",
    "evidence_refs",
    "sensitivity",
    "formal_effect",
}
_RAW_REGISTERED_PERTURBATION_FIELDS = _REGISTERED_PERTURBATION_FIELDS - {"formal_effect"}
_PROHIBITED_TARGET_LABEL_INPUTS = {
    "holdout_results",
    "future_results",
    "future_returns",
    "mfe",
    "mae",
    "outcomes",
    "labels",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _date(value: Any) -> str:
    text = _text(value)
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return ""


def _list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _strings(value: Any) -> list[str]:
    return sorted({_text(item) for item in _list(value) if _text(item)})


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {
            _text(key): _json_value(item)
            for key, item in sorted(value.items(), key=lambda row: _text(row[0]))
            if _text(key)
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return _text(value)


def frozen_decision_robustness_research_plan() -> dict:
    plan = deepcopy(_FROZEN_RESEARCH_PLAN)
    plan["plan_hash"] = FROZEN_RESEARCH_PLAN_HASH
    return plan


def canonical_decision_robustness_version_health_hash(payload: Any) -> str:
    return stable_json_hash(
        payload if isinstance(payload, dict) else {},
        excluded_keys={"artifact_hash"},
    )


def _validate_fact_bundle_header(facts: Any, report_date: Any) -> list[str]:
    if not isinstance(facts, dict) or not facts:
        return ["decision_robustness_facts_missing"]
    normalized_date = _date(report_date)
    errors = []
    if facts.get("schema_version") != FACT_SCHEMA_VERSION:
        errors.append("decision_robustness_facts_schema_invalid")
    if not normalized_date:
        errors.append("decision_robustness_report_date_invalid")
    if _date(facts.get("report_date")) != normalized_date:
        errors.append("decision_robustness_facts_report_date_mismatch")
    if "target_date" in facts and _date(facts.get("target_date")) != normalized_date:
        errors.append("decision_robustness_facts_target_date_mismatch")
    if _date(facts.get("query_date")) != normalized_date:
        errors.append("decision_robustness_facts_query_date_mismatch")
    if normalized_date and normalized_date < _FROZEN_SAMPLE_SPLIT["frozen_at"]:
        errors.append("decision_robustness_plan_not_available_on_target_date")
    if not isinstance(facts.get("facts_by_layer"), dict):
        errors.append("decision_robustness_facts_layers_invalid")
    if not isinstance(facts.get("registered_perturbations"), list):
        errors.append("decision_robustness_perturbations_invalid")
    return list(dict.fromkeys(errors))


def _normalize_fact(raw: Any, *, layer: str, report_date: str) -> tuple[dict, list[str]]:
    if not isinstance(raw, dict):
        return {}, [f"decision_robustness_{layer}_fact_invalid"]
    fact_id = _text(raw.get("fact_id"))
    metric = _text(raw.get("metric"))
    if not fact_id:
        return {}, [f"decision_robustness_{layer}_fact_id_missing"]
    if metric not in _ALLOWED_METRICS[layer]:
        return {}, [f"decision_robustness_{layer}_metric_ignored:{fact_id}"]
    status = _text(raw.get("status")).lower()
    status = status if status in FACT_STATUSES else "missing"
    source_date = _date(raw.get("source_date"))
    source = _text(raw.get("source"))
    missing = _strings(raw.get("missing_fields"))
    warnings = []
    if raw.get("source_date") and not source_date:
        warnings.append(f"decision_robustness_{layer}_source_date_invalid:{fact_id}")
    if source_date and source_date > report_date:
        warnings.append(f"decision_robustness_{layer}_source_date_future:{fact_id}")
        source_date = ""
    if status != "missing" and (not source_date or not source):
        status = "missing"
        missing.extend(["source", "source_date"])
    value = _json_value(raw.get("value")) if status != "missing" else None
    if status != "missing" and value in (None, "", [], {}):
        status = "missing"
        missing.append("value")
    quality = _text(raw.get("evidence_quality")).lower() or "recorded"
    if quality not in EVIDENCE_QUALITIES:
        quality = "recorded"
    hypotheses = set(VERSION_HYPOTHESES)
    evidence_usable = status in {"observed", "conflicted"}
    return (
        {
            "fact_id": fact_id,
            "metric": metric,
            "subject": _text(raw.get("subject")),
            "status": status,
            "value": value,
            "source_date": source_date,
            "source": source,
            "supports": (
                sorted(set(_strings(raw.get("supports"))) & hypotheses) if evidence_usable else []
            ),
            "contradicts": (
                sorted(set(_strings(raw.get("contradicts"))) & hypotheses)
                if evidence_usable
                else []
            ),
            "distinguishes": (
                sorted(set(_strings(raw.get("distinguishes"))) & hypotheses)
                if evidence_usable
                else []
            ),
            "missing_fields": sorted(set(missing)),
            "evidence_quality": quality,
            "research_only": bool(raw.get("research_only")) or quality == "story_only",
        },
        warnings,
    )


def _fact_sort_key(row: dict) -> tuple[str, str, str, str, str]:
    return (
        _text(row.get("metric")),
        _text(row.get("subject")),
        _text(row.get("fact_id")),
        _text(row.get("source_date")),
        stable_json_hash({"value": row.get("value")}),
    )


def _normalize_layers(facts: dict, report_date: str) -> tuple[dict, list[str], list[str]]:
    supplied = facts.get("facts_by_layer") if isinstance(facts.get("facts_by_layer"), dict) else {}
    layers = {}
    warnings = []
    missing = []
    seen_fact_ids = set()
    for layer in FACT_LAYERS:
        rows = []
        for raw in _list(supplied.get(layer)):
            row, row_warnings = _normalize_fact(raw, layer=layer, report_date=report_date)
            warnings.extend(row_warnings)
            if not row:
                continue
            fact_id = row["fact_id"]
            if fact_id in seen_fact_ids:
                warnings.append(f"decision_robustness_duplicate_fact_ignored:{fact_id}")
                continue
            seen_fact_ids.add(fact_id)
            rows.append(row)
        rows.sort(key=_fact_sort_key)
        layer_missing = [
            f"metric:{metric}"
            for metric in sorted(_ALLOWED_METRICS[layer])
            if not any(
                row.get("metric") == metric and row.get("status") in {"observed", "conflicted"}
                for row in rows
            )
        ]
        if not rows:
            layer_missing.append("facts")
        layer_missing.extend(
            f"fact:{row['fact_id']}:{field}"
            for row in rows
            for field in _strings(row.get("missing_fields"))
        )
        layer_missing = sorted(set(layer_missing))
        layers[layer] = {
            "facts": rows,
            "missing_fields": layer_missing,
            "source_dates": sorted(
                {row.get("source_date") for row in rows if row.get("source_date")}
            ),
        }
        missing.extend(f"facts_by_layer.{layer}.{field}" for field in layer_missing)
    return layers, sorted(set(warnings)), sorted(set(missing))


def _perturbation_registration_errors(
    raw: Any,
    *,
    report_date: str,
    require_formal_effect: bool,
) -> list[str]:
    raw = raw if isinstance(raw, dict) else {}
    registry_id = _text(raw.get("registry_id"))
    registry = _FROZEN_PERTURBATION_REGISTRY_BY_ID.get(registry_id)
    layer = _text(raw.get("layer")).lower()
    affected_fields = _strings(raw.get("affected_fields"))
    errors = []
    expected_fields = (
        _REGISTERED_PERTURBATION_FIELDS
        if require_formal_effect
        else _RAW_REGISTERED_PERTURBATION_FIELDS
    )
    if set(raw) != expected_fields:
        errors.append("fields")
    if not registry:
        errors.append("registry_id")
        return errors
    for field in (
        "perturbation_id",
        "kind",
        "layer",
        "registration_status",
        "registered_at",
        "registration_source",
    ):
        if _text(raw.get(field)) != _text(registry.get(field)):
            errors.append(field)
    if affected_fields != registry["affected_fields"]:
        errors.append("affected_fields")
    if _json_value(raw.get("allowed_change")) != registry["allowed_change"]:
        errors.append("allowed_change")
    if _strings(raw.get("evidence_refs")) != registry["evidence_refs"]:
        errors.append("evidence_refs")
    target_date = _date(raw.get("target_date"))
    registered_at = _date(raw.get("registered_at"))
    source_date = _date(raw.get("source_date"))
    if target_date != report_date:
        errors.append("target_date")
    if not registered_at or registered_at >= report_date:
        errors.append("registered_at")
    if not source_date or source_date > report_date:
        errors.append("source_date")
    prefix = f"facts_by_layer.{layer}."
    if layer not in FACT_LAYERS or not affected_fields or any(
        not field.startswith(prefix) for field in affected_fields
    ):
        errors.append("affected_fields_scope")
    if require_formal_effect and raw.get("formal_effect") != FORMAL_EFFECT:
        errors.append("formal_effect")
    return sorted(set(errors))


def _normalize_perturbations(
    facts: dict,
    *,
    report_date: str,
) -> tuple[list[dict], list[str]]:
    normalized = []
    warnings = []
    seen = set()
    for index, raw in enumerate(_list(facts.get("registered_perturbations"))):
        raw = raw if isinstance(raw, dict) else {}
        perturbation_id = _text(raw.get("perturbation_id")) or f"row_{index}"
        registry_id = _text(raw.get("registry_id"))
        kind = _text(raw.get("kind")).lower()
        layer = _text(raw.get("layer")).lower()
        target_date = _date(raw.get("target_date"))
        registered_at = _date(raw.get("registered_at"))
        source_date = _date(raw.get("source_date"))
        affected_fields = _strings(raw.get("affected_fields"))
        valid = not _perturbation_registration_errors(
            raw,
            report_date=report_date,
            require_formal_effect=False,
        ) and perturbation_id not in seen
        if not valid:
            warnings.append(f"decision_robustness_unregistered_perturbation_ignored:{perturbation_id}")
            continue
        seen.add(perturbation_id)
        sensitivity = raw.get("sensitivity") if isinstance(raw.get("sensitivity"), dict) else {}
        object_sensitive = sensitivity.get("object_changed") is True
        action_sensitive = sensitivity.get("action_changed") is True
        fact_sensitive = sensitivity.get("fact_changed") is True
        unresolved = sensitivity.get("unresolved") is True or not sensitivity
        sensitivity_status = (
            "unresolved"
            if unresolved
            else "sensitive"
            if object_sensitive or action_sensitive or fact_sensitive
            else "stable"
        )
        normalized.append(
            {
                "registry_id": registry_id,
                "perturbation_id": perturbation_id,
                "kind": kind,
                "layer": layer,
                "registration_status": "pre_registered",
                "target_date": target_date,
                "registered_at": registered_at,
                "registration_source": _text(raw.get("registration_source")),
                "source_date": source_date,
                "affected_fields": affected_fields,
                "allowed_change": _json_value(raw.get("allowed_change")),
                "evidence_refs": _strings(raw.get("evidence_refs")),
                "sensitivity": {
                    "status": sensitivity_status,
                    "object_sensitive": object_sensitive,
                    "action_sensitive": action_sensitive,
                    "fact_sensitive": fact_sensitive,
                    "sensitive_fields": _strings(sensitivity.get("sensitive_fields")),
                    "unresolved": unresolved,
                },
                "formal_effect": FORMAL_EFFECT,
            }
        )
    normalized.sort(key=lambda row: (row["kind"], row["layer"], row["perturbation_id"]))
    return normalized, sorted(set(warnings))


def _normalize_next_review(facts: dict, report_date: str) -> tuple[dict, list[str]]:
    raw = facts.get("next_review") if isinstance(facts.get("next_review"), dict) else {}
    review_date = _date(raw.get("review_date"))
    required_facts = _strings(raw.get("required_facts"))
    stop_conditions = _strings(raw.get("stop_strengthening_conditions"))
    missing = []
    if not review_date or review_date <= report_date:
        review_date = ""
        missing.append("next_review.review_date")
    if not required_facts:
        missing.append("next_review.required_facts")
    if not stop_conditions:
        missing.append("next_review.stop_strengthening_conditions")
    return (
        {
            "review_date": review_date,
            "required_facts": required_facts,
            "stop_strengthening_conditions": stop_conditions,
            "formal_effect": FORMAL_EFFECT,
        },
        missing,
    )


def _normalize_sample_profile(facts: dict, report_date: str) -> tuple[dict, list[str]]:
    raw = facts.get("sample_profile") if isinstance(facts.get("sample_profile"), dict) else {}
    source_date = _date(raw.get("source_date"))
    source = _text(raw.get("source"))
    positive_count = raw.get("positive_sample_count")
    total_count = raw.get("total_sample_count")
    positive_count = positive_count if isinstance(positive_count, int) and positive_count >= 0 else None
    total_count = total_count if isinstance(total_count, int) and total_count >= 0 else None
    regimes = _strings(raw.get("observed_regimes"))
    missing = []
    if not source_date or source_date > report_date or not source:
        source_date = ""
        source = ""
        positive_count = None
        total_count = None
        regimes = []
        missing.append("sample_profile.source")
    if positive_count is None:
        missing.append("sample_profile.positive_sample_count")
    if total_count is None:
        missing.append("sample_profile.total_sample_count")
    if not regimes:
        missing.append("sample_profile.observed_regimes")
    return (
        {
            "positive_sample_count": positive_count,
            "total_sample_count": total_count,
            "observed_regimes": regimes,
            "source_date": source_date,
            "source": source,
        },
        missing,
    )


def _sample_sufficiency(profile: dict) -> dict:
    reasons = []
    positive_count = profile.get("positive_sample_count")
    regimes = _strings(profile.get("observed_regimes"))
    if positive_count is None or positive_count < 2:
        reasons.append("positive_sample_count_below_two")
    if len(regimes) < 2:
        reasons.append("single_or_missing_regime")
    return {
        "status": "insufficient" if reasons else "research_only",
        "reasons": reasons,
        "holdout_results_used": False,
        "decision_scope": DECISION_SCOPE,
        "formal_effect": FORMAL_EFFECT,
    }


def _normalized_inputs(facts: dict, report_date: str) -> tuple[dict, list[str], list[str]]:
    layers, layer_warnings, layer_missing = _normalize_layers(facts, report_date)
    perturbations, perturbation_warnings = _normalize_perturbations(
        facts,
        report_date=report_date,
    )
    next_review, review_missing = _normalize_next_review(facts, report_date)
    sample_profile, sample_missing = _normalize_sample_profile(facts, report_date)
    warnings = sorted(set([*layer_warnings, *perturbation_warnings]))
    sample_raw = facts.get("sample_profile") if isinstance(facts.get("sample_profile"), dict) else {}
    if _PROHIBITED_TARGET_LABEL_INPUTS & (set(facts) | set(sample_raw)):
        warnings.append("decision_robustness_holdout_or_future_results_ignored")
        warnings = sorted(set(warnings))
    missing = sorted(set([*layer_missing, *review_missing, *sample_missing]))
    normalized = {
        "facts_by_layer": layers,
        "registered_perturbations": perturbations,
        "unresolved_distinctions": _strings(facts.get("unresolved_distinctions")),
        "next_review": next_review,
        "sample_profile": sample_profile,
        "fact_bundle_warnings": warnings,
    }
    return normalized, warnings, missing


def validate_decision_robustness_version_health_facts(
    facts: Any,
    *,
    report_date: Any,
) -> tuple[bool, list[str]]:
    errors = _validate_fact_bundle_header(facts, report_date)
    return not errors, errors


def canonical_decision_robustness_version_health_facts_hash(
    facts: Any,
    *,
    report_date: Any,
) -> str:
    errors = _validate_fact_bundle_header(facts, report_date)
    if errors:
        return ""
    normalized_date = _date(report_date)
    normalized, _, _ = _normalized_inputs(facts, normalized_date)
    return stable_json_hash(normalized)


def decision_robustness_version_health_cache_key(
    report_date: Any,
    *,
    analysis_mode: str,
    source_decision_hash: str,
    source_candidate_hash: str,
    source_facts_hash: str,
) -> tuple[str, str, str, str, str, str, str]:
    mode = "replay" if analysis_mode == "replay" else "fresh"
    return (
        "decision_robustness_version_health",
        _date(report_date),
        mode,
        _text(source_decision_hash),
        _text(source_candidate_hash),
        _text(source_facts_hash),
        FROZEN_RESEARCH_PLAN_HASH,
    )


def _decision_robustness(perturbations: list[dict]) -> dict:
    scenarios = [
        {
            "perturbation_id": row["perturbation_id"],
            "kind": row["kind"],
            "layer": row["layer"],
            "affected_fields": list(row["affected_fields"]),
            "sensitivity": deepcopy(row["sensitivity"]),
            "formal_effect": FORMAL_EFFECT,
        }
        for row in perturbations
    ]
    return {
        "scenarios": scenarios,
        "sensitive_perturbation_ids": sorted(
            row["perturbation_id"]
            for row in perturbations
            if row["sensitivity"]["status"] == "sensitive"
        ),
        "unresolved_perturbation_ids": sorted(
            row["perturbation_id"]
            for row in perturbations
            if row["sensitivity"]["status"] == "unresolved"
        ),
        "decision_scope": DECISION_SCOPE,
        "formal_effect": FORMAL_EFFECT,
    }


def _version_hypotheses(layers: dict, missing_fields: list[str]) -> list[dict]:
    facts = [
        row
        for layer in FACT_LAYERS
        for row in (layers.get(layer) or {}).get("facts", [])
        if isinstance(row, dict) and row.get("status") in {"observed", "conflicted"}
    ]
    result = []
    for hypothesis_id in VERSION_HYPOTHESES:
        supporting = sorted(
            row["fact_id"] for row in facts if hypothesis_id in row.get("supports", [])
        )
        counter = sorted(
            row["fact_id"] for row in facts if hypothesis_id in row.get("contradicts", [])
        )
        distinguishing = sorted(
            row["fact_id"] for row in facts if hypothesis_id in row.get("distinguishes", [])
        )
        if hypothesis_id == "facts_insufficient" and missing_fields:
            status = "evidence_present"
        elif supporting and counter:
            status = "contested"
        elif supporting:
            status = "evidence_present"
        elif counter:
            status = "counter_evidence_present"
        else:
            status = "insufficient"
        hypothesis_missing = list(missing_fields)
        if not supporting and hypothesis_id != "facts_insufficient":
            hypothesis_missing.append("supporting_facts")
        if not distinguishing:
            hypothesis_missing.append("distinguishing_facts")
        result.append(
            {
                "hypothesis_id": hypothesis_id,
                "status": status,
                "supporting_fact_ids": supporting,
                "counter_evidence_fact_ids": counter,
                "distinguishing_fact_ids": distinguishing,
                "missing_fields": sorted(set(hypothesis_missing)),
                "formal_effect": FORMAL_EFFECT,
            }
        )
    return result


def _source_dates(report_date: str, normalized: dict) -> dict:
    perturbation_dates = sorted(
        {
            row.get("source_date")
            for row in normalized["registered_perturbations"]
            if row.get("source_date")
        }
    )
    return {
        "target_date": report_date,
        "query_date": report_date,
        "layers": {
            layer: list(normalized["facts_by_layer"][layer]["source_dates"])
            for layer in FACT_LAYERS
        },
        "perturbations": perturbation_dates,
        "sample_profile": normalized["sample_profile"].get("source_date") or "",
        "research_plan_frozen_at": _FROZEN_SAMPLE_SPLIT["frozen_at"],
    }


def _source_hashes(
    *,
    normalized: dict,
    source_decision_hash: str,
    source_candidate_hash: str,
) -> dict:
    return {
        "formal_decision": source_decision_hash,
        "candidate_decision_evidence": source_candidate_hash,
        "fact_bundle": stable_json_hash(normalized),
        "research_plan": FROZEN_RESEARCH_PLAN_HASH,
        **{
            f"{layer}_facts": stable_json_hash(normalized["facts_by_layer"][layer])
            for layer in FACT_LAYERS
        },
    }


def build_decision_robustness_version_health(
    data: Any,
    *,
    report_date: Any,
    source_decision_hash: str,
    candidate_decision_evidence: Any,
) -> dict:
    data = data if isinstance(data, dict) else {}
    normalized_date = _date(report_date)
    facts = data.get("decision_robustness_version_health_facts")
    header_errors = _validate_fact_bundle_header(facts, normalized_date)
    candidate = candidate_decision_evidence if isinstance(candidate_decision_evidence, dict) else {}
    source_candidate_hash = _text(candidate.get("artifact_hash"))
    if (
        header_errors
        or not is_sha256(source_decision_hash)
        or not is_sha256(source_candidate_hash)
        or candidate.get("decision_scope") != DECISION_SCOPE
        or candidate.get("formal_effect") != FORMAL_EFFECT
        or data.get("approved_formal_fields") != []
    ):
        return {}
    normalized, fact_warnings, missing = _normalized_inputs(facts, normalized_date)
    sample_sufficiency = _sample_sufficiency(normalized["sample_profile"])
    warnings = list(fact_warnings)
    if sample_sufficiency["status"] == "insufficient":
        warnings.append("decision_robustness_sample_evidence_insufficient")
    source_hashes = _source_hashes(
        normalized=normalized,
        source_decision_hash=_text(source_decision_hash),
        source_candidate_hash=source_candidate_hash,
    )
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "report_date": normalized_date,
        "target_date": normalized_date,
        "query_date": normalized_date,
        "decision_scope": DECISION_SCOPE,
        "formal_effect": FORMAL_EFFECT,
        "source_decision_hash": _text(source_decision_hash),
        "source_dates": _source_dates(normalized_date, normalized),
        "source_hashes": source_hashes,
        "facts_by_layer": normalized["facts_by_layer"],
        "registered_perturbations": normalized["registered_perturbations"],
        "perturbation_registry": deepcopy(_FROZEN_RESEARCH_PLAN["perturbation_registry"]),
        "decision_robustness": _decision_robustness(normalized["registered_perturbations"]),
        "version_hypotheses": _version_hypotheses(normalized["facts_by_layer"], missing),
        "unresolved_distinctions": normalized["unresolved_distinctions"],
        "next_review": normalized["next_review"],
        "sample_split": deepcopy(_FROZEN_SAMPLE_SPLIT),
        "sample_profile": normalized["sample_profile"],
        "sample_sufficiency": sample_sufficiency,
        "evaluation_plan": deepcopy(_FROZEN_EVALUATION_PLAN),
        "approved_formal_fields": [],
        "approved_formal_fields_hash": _EMPTY_APPROVED_FORMAL_FIELDS_HASH,
        "fact_bundle_warnings": normalized["fact_bundle_warnings"],
        "missing_fields": sorted(set(missing)),
        "warnings": sorted(set(warnings)),
    }
    artifact["input_hash"] = stable_json_hash(
        {
            "source_hashes": source_hashes,
            "approved_formal_fields_hash": artifact["approved_formal_fields_hash"],
        }
    )
    artifact["availability"] = (
        "complete" if not artifact["missing_fields"] and not artifact["warnings"] else "partial"
    )
    artifact["artifact_hash"] = canonical_decision_robustness_version_health_hash(artifact)
    return artifact


def _validate_sample_split(sample_split: Any, report_date: str) -> list[str]:
    if sample_split != _FROZEN_SAMPLE_SPLIT:
        return ["decision_robustness_sample_split_mismatch"]
    discovery = sample_split["discovery"]
    calibration = sample_split["calibration"]
    holdout = sample_split["holdout"]
    ordered = (
        _date(discovery["start_date"])
        <= _date(discovery["end_date"])
        < _date(calibration["start_date"])
        <= _date(calibration["end_date"])
        < _date(holdout["start_date"])
        <= _date(holdout["end_date"])
    )
    if not ordered or holdout.get("result_access") != "unread":
        return ["decision_robustness_sample_split_invalid"]
    if _date(sample_split.get("frozen_at")) > report_date:
        return ["decision_robustness_sample_split_future"]
    return []


def _validate_evaluation_plan(plan: Any, report_date: str) -> list[str]:
    if plan != _FROZEN_EVALUATION_PLAN:
        return ["decision_robustness_evaluation_plan_mismatch"]
    errors = []
    if _date(plan.get("frozen_at")) > report_date:
        errors.append("decision_robustness_evaluation_plan_future")
    if plan.get("status") != "frozen_not_run" or plan.get("results_access") != "not_started":
        errors.append("decision_robustness_evaluation_plan_status_invalid")
    if tuple(plan.get("metrics") or []) != _REQUIRED_EVALUATION_METRICS:
        errors.append("decision_robustness_evaluation_metrics_invalid")
    if plan.get("formal_effect") != FORMAL_EFFECT:
        errors.append("decision_robustness_evaluation_effect_invalid")
    return errors


def validate_decision_robustness_version_health(
    artifact: Any,
    *,
    report_date: Any,
    source_decision_hash: str = "",
    source_candidate_hash: str = "",
    source_facts_hash: str = "",
) -> tuple[bool, list[str]]:
    if not isinstance(artifact, dict):
        return False, ["decision_robustness_artifact_type_invalid"]
    normalized_date = _date(report_date)
    errors = []
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("decision_robustness_schema_invalid")
    allowed_artifact_fields = {
        "schema_version",
        "decision_scope",
        "formal_effect",
        "source_decision_hash",
        *_REQUIRED_ARTIFACT_FIELDS,
    }
    if set(artifact) != allowed_artifact_fields:
        errors.append("decision_robustness_artifact_fields_invalid")
    if any(artifact.get(key) != normalized_date for key in ("report_date", "target_date", "query_date")):
        errors.append("decision_robustness_target_date_mismatch")
    if artifact.get("decision_scope") != DECISION_SCOPE or artifact.get("formal_effect") != FORMAL_EFFECT:
        errors.append("decision_robustness_scope_invalid")
    for field, expected_type in _REQUIRED_ARTIFACT_FIELDS.items():
        if field not in artifact:
            errors.append(f"decision_robustness_required_field_missing:{field}")
        elif not isinstance(artifact.get(field), expected_type):
            errors.append(f"decision_robustness_field_type_invalid:{field}")
    if artifact.get("approved_formal_fields") != []:
        errors.append("decision_robustness_approved_fields_not_empty")
    if artifact.get("approved_formal_fields_hash") != _EMPTY_APPROVED_FORMAL_FIELDS_HASH:
        errors.append("decision_robustness_approved_fields_hash_invalid")
    source_hashes = artifact.get("source_hashes") if isinstance(artifact.get("source_hashes"), dict) else {}
    required_hashes = {
        "formal_decision",
        "candidate_decision_evidence",
        "fact_bundle",
        "research_plan",
        *(f"{layer}_facts" for layer in FACT_LAYERS),
    }
    if any(not is_sha256(source_hashes.get(key)) for key in required_hashes):
        errors.append("decision_robustness_source_hash_invalid")
    if source_decision_hash and source_hashes.get("formal_decision") != source_decision_hash:
        errors.append("decision_robustness_decision_hash_mismatch")
    if source_candidate_hash and source_hashes.get("candidate_decision_evidence") != source_candidate_hash:
        errors.append("decision_robustness_candidate_hash_mismatch")
    if source_facts_hash and source_hashes.get("fact_bundle") != source_facts_hash:
        errors.append("decision_robustness_fact_hash_mismatch")
    if artifact.get("source_decision_hash") != source_hashes.get("formal_decision"):
        errors.append("decision_robustness_source_decision_mismatch")

    layers = artifact.get("facts_by_layer") if isinstance(artifact.get("facts_by_layer"), dict) else {}
    if tuple(layers.keys()) != FACT_LAYERS:
        errors.append("decision_robustness_fact_layers_invalid")
    seen_fact_ids = set()
    for layer in FACT_LAYERS:
        payload = layers.get(layer) if isinstance(layers.get(layer), dict) else {}
        rows = payload.get("facts") if isinstance(payload.get("facts"), list) else []
        if rows != sorted(rows, key=_fact_sort_key):
            errors.append(f"decision_robustness_{layer}_fact_order_invalid")
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"decision_robustness_{layer}_fact_invalid")
                continue
            if set(row) != _FACT_FIELDS:
                errors.append(f"decision_robustness_{layer}_fact_fields_invalid")
            fact_id = _text(row.get("fact_id"))
            if not fact_id or fact_id in seen_fact_ids:
                errors.append("decision_robustness_fact_id_invalid")
            seen_fact_ids.add(fact_id)
            if row.get("metric") not in _ALLOWED_METRICS[layer]:
                errors.append(f"decision_robustness_{layer}_metric_invalid")
            if row.get("status") not in FACT_STATUSES:
                errors.append(f"decision_robustness_{layer}_status_invalid")
            source_date = _date(row.get("source_date"))
            if source_date and source_date > normalized_date:
                errors.append(f"decision_robustness_{layer}_source_invalid")
            if row.get("status") != "missing" and (
                not source_date or source_date > normalized_date or not _text(row.get("source"))
            ):
                errors.append(f"decision_robustness_{layer}_source_invalid")
            if row.get("evidence_quality") == "story_only" and row.get("research_only") is not True:
                errors.append("decision_robustness_story_evidence_scope_invalid")
            if row.get("status") == "missing" and (
                row.get("value") is not None
                or row.get("supports")
                or row.get("contradicts")
                or row.get("distinguishes")
            ):
                errors.append(f"decision_robustness_{layer}_missing_fact_evidence_invalid")
        if source_hashes.get(f"{layer}_facts") != stable_json_hash(payload):
            errors.append(f"decision_robustness_{layer}_hash_mismatch")

    perturbations = artifact.get("registered_perturbations")
    perturbations = perturbations if isinstance(perturbations, list) else []
    allowed_scenario_keys = {
        "perturbation_id",
        "kind",
        "layer",
        "affected_fields",
        "sensitivity",
        "formal_effect",
    }
    seen_perturbation_ids = set()
    seen_registry_ids = set()
    for row in perturbations:
        perturbation_id = _text(row.get("perturbation_id")) if isinstance(row, dict) else ""
        registry_id = _text(row.get("registry_id")) if isinstance(row, dict) else ""
        if (
            not isinstance(row, dict)
            or set(row) != _REGISTERED_PERTURBATION_FIELDS
            or _perturbation_registration_errors(
                row,
                report_date=normalized_date,
                require_formal_effect=True,
            )
            or not perturbation_id
            or perturbation_id in seen_perturbation_ids
            or registry_id in seen_registry_ids
        ):
            errors.append("decision_robustness_registered_perturbation_invalid")
        seen_perturbation_ids.add(perturbation_id)
        seen_registry_ids.add(registry_id)
    if artifact.get("perturbation_registry") != _FROZEN_RESEARCH_PLAN["perturbation_registry"]:
        errors.append("decision_robustness_perturbation_registry_mismatch")
    expected_robustness = _decision_robustness(perturbations)
    if artifact.get("decision_robustness") != expected_robustness:
        errors.append("decision_robustness_sensitivity_mismatch")
    else:
        for scenario in artifact["decision_robustness"]["scenarios"]:
            if set(scenario) != allowed_scenario_keys:
                errors.append("decision_robustness_scenario_fields_invalid")

    missing_fields = _strings(artifact.get("missing_fields"))
    if artifact.get("version_hypotheses") != _version_hypotheses(layers, missing_fields):
        errors.append("decision_robustness_version_hypotheses_mismatch")
    if [row.get("hypothesis_id") for row in artifact.get("version_hypotheses", []) if isinstance(row, dict)] != list(VERSION_HYPOTHESES):
        errors.append("decision_robustness_version_hypotheses_order_invalid")

    errors.extend(_validate_sample_split(artifact.get("sample_split"), normalized_date))
    errors.extend(_validate_evaluation_plan(artifact.get("evaluation_plan"), normalized_date))
    profile = artifact.get("sample_profile") if isinstance(artifact.get("sample_profile"), dict) else {}
    if set(profile) != {
        "positive_sample_count",
        "total_sample_count",
        "observed_regimes",
        "source_date",
        "source",
    }:
        errors.append("decision_robustness_sample_profile_fields_invalid")
    profile_source_date = _date(profile.get("source_date"))
    if profile_source_date and profile_source_date > normalized_date:
        errors.append("decision_robustness_sample_profile_source_date_invalid")
    if profile_source_date and not _text(profile.get("source")):
        errors.append("decision_robustness_sample_profile_source_invalid")
    if not profile_source_date and (
        _text(profile.get("source"))
        or profile.get("positive_sample_count") is not None
        or profile.get("total_sample_count") is not None
        or _strings(profile.get("observed_regimes"))
    ):
        errors.append("decision_robustness_sample_profile_missing_source_invalid")
    if artifact.get("sample_sufficiency") != _sample_sufficiency(profile):
        errors.append("decision_robustness_sample_sufficiency_mismatch")
    if artifact.get("sample_sufficiency", {}).get("holdout_results_used") is not False:
        errors.append("decision_robustness_holdout_leak_detected")

    normalized_source = {
        "facts_by_layer": layers,
        "registered_perturbations": perturbations,
        "unresolved_distinctions": _strings(artifact.get("unresolved_distinctions")),
        "next_review": artifact.get("next_review"),
        "sample_profile": profile,
        "fact_bundle_warnings": _strings(artifact.get("fact_bundle_warnings")),
    }
    next_review = artifact.get("next_review") if isinstance(artifact.get("next_review"), dict) else {}
    if set(next_review) != {
        "review_date",
        "required_facts",
        "stop_strengthening_conditions",
        "formal_effect",
    } or next_review.get("formal_effect") != FORMAL_EFFECT:
        errors.append("decision_robustness_next_review_invalid")
    if source_hashes.get("fact_bundle") != stable_json_hash(normalized_source):
        errors.append("decision_robustness_fact_bundle_hash_mismatch")
    if source_hashes.get("research_plan") != FROZEN_RESEARCH_PLAN_HASH:
        errors.append("decision_robustness_research_plan_hash_mismatch")
    source_dates = artifact.get("source_dates") if isinstance(artifact.get("source_dates"), dict) else {}
    if source_dates != _source_dates(normalized_date, normalized_source):
        errors.append("decision_robustness_source_dates_mismatch")
    expected_input_hash = stable_json_hash(
        {
            "source_hashes": source_hashes,
            "approved_formal_fields_hash": artifact.get("approved_formal_fields_hash"),
        }
    )
    if artifact.get("input_hash") != expected_input_hash:
        errors.append("decision_robustness_input_hash_mismatch")
    expected_availability = (
        "complete"
        if not missing_fields and not _strings(artifact.get("warnings"))
        else "partial"
    )
    if artifact.get("availability") != expected_availability:
        errors.append("decision_robustness_availability_invalid")
    if artifact.get("artifact_hash") != canonical_decision_robustness_version_health_hash(artifact):
        errors.append("decision_robustness_artifact_hash_mismatch")
    return not errors, list(dict.fromkeys(errors))


__all__ = [
    "DECISION_SCOPE",
    "FACT_SCHEMA_VERSION",
    "FORMAL_EFFECT",
    "FROZEN_RESEARCH_PLAN_HASH",
    "REGISTERED_PERTURBATION_KINDS",
    "SCHEMA_VERSION",
    "VERSION_HYPOTHESES",
    "build_decision_robustness_version_health",
    "canonical_decision_robustness_version_health_facts_hash",
    "canonical_decision_robustness_version_health_hash",
    "decision_robustness_version_health_cache_key",
    "frozen_decision_robustness_research_plan",
    "validate_decision_robustness_version_health",
    "validate_decision_robustness_version_health_facts",
]
