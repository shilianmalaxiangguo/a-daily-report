from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo


BATCH_SCHEMA_VERSION = "daily_report_consensus_batch.v1"
REVIEW_SCHEMA_VERSION = "daily_report_consensus_review.v1"
REVIEW_REQUEST_SCHEMA_VERSION = "daily_report_consensus_review_request.v1"
FUNNEL_SCHEMA_VERSION = "daily_report_consensus_funnel.v1"
TRAINING_EXPORT_SCHEMA_VERSION = "daily_report_consensus_training_export.v1"
REVIEW_CONTRACT_VERSION = "daily_report_consensus_review_contract.v1"
PROMPT_VERSION = "daily_report_consensus_prompt.v1"

DEFAULT_REVIEW_SYSTEM_PROMPT = (
    "你只负责复核一份冻结的A股唯一提案。严格按请求中的 JSON 契约返回。"
)
DEFAULT_REVIEW_TEMPERATURE = 0.7
DEFAULT_REVIEW_MAX_TOKENS = 500

REVIEW_COUNT = 10
CONSENSUS_THRESHOLD = 7
MAX_CONCURRENCY = 5
REVIEW_TIMEOUT_SECONDS = 120.0
BATCH_TIMEOUT_SECONDS = 300.0

REVIEW_STATUSES = frozenset({"completed", "failed", "timeout", "contract_invalid"})
REVIEW_VOTES = frozenset(
    {"confirm_existing", "deny_existing", "confirm_no_object", None}
)
COMPLETED_VOTES = frozenset(
    {"confirm_existing", "deny_existing", "confirm_no_object"}
)
OUTPUT_FILENAMES = (
    "batch.json",
    "reviews.jsonl",
    "summary.txt",
    "run.jsonl",
    "funnel.jsonl",
)

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)
_ALLOWED_REVIEW_RESPONSE_KEYS = frozenset(
    {
        "vote",
        "reason",
        "missing_facts",
        "alternative_mentions",
        "provider_request_id",
    }
)
_PROHIBITED_REVIEW_KEY_PARTS = frozenset(
    {
        "position",
        "positionpct",
        "newentry",
        "newentrypct",
        "b1",
        "b2",
        "holding",
        "oldposition",
        "exit",
        "sell",
        "buy",
        "action",
        "仓位",
        "新仓",
        "旧仓",
        "退出",
        "卖出",
        "买入",
    }
)


class ConsensusContractError(ValueError):
    """Raised when a frozen batch or review violates the versioned contract."""

    def __init__(self, message: str, *, reason_codes: Sequence[str] = ()):
        super().__init__(message)
        self.reason_codes = tuple(dict.fromkeys(str(item) for item in reason_codes if item))


@dataclass(frozen=True)
class _LLMReviewTransportResult:
    response: Any
    provider_request_id: str = ""
    failure_reason: str = ""
    reason_codes: tuple[str, ...] = ()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, set):
        return sorted(
            (_json_ready(item) for item in value),
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _date(value: Any) -> str:
    text = _text(value)
    try:
        return date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return ""


def parse_rfc3339(value: Any, *, field: str = "timestamp") -> datetime:
    text = _text(value)
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError) as error:
        raise ConsensusContractError(
            f"{field} 必须是带时区 RFC3339 时间",
            reason_codes=("missing_timestamp",),
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ConsensusContractError(
            f"{field} 必须包含时区",
            reason_codes=("missing_timestamp",),
        )
    return parsed


def normalize_rfc3339(value: Any, *, field: str = "timestamp") -> str:
    return parse_rfc3339(value, field=field).isoformat(timespec="seconds")


def shanghai_rfc3339(value: Any, *, field: str = "timestamp") -> str:
    return parse_rfc3339(value, field=field).astimezone(_SHANGHAI_TZ).isoformat(
        timespec="seconds"
    )


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).astimezone(_SHANGHAI_TZ).isoformat(
        timespec="seconds"
    )


def _build_review_seeds(run_id: str, *, seed_supported: bool) -> list[int | None]:
    if not seed_supported:
        return [None] * REVIEW_COUNT
    seeds: list[int] = []
    used: set[int] = set()
    for sequence in range(1, REVIEW_COUNT + 1):
        digest = hashlib.sha256(f"{run_id}:{sequence}".encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big") % (2**31)
        while seed in used:
            seed = (seed + 1) % (2**31)
        used.add(seed)
        seeds.append(seed)
    return seeds


def _stock(value: Any) -> dict[str, str]:
    value = value if isinstance(value, Mapping) else {}
    nested = value.get("stock") if isinstance(value.get("stock"), Mapping) else {}
    source = {**value, **nested}
    raw_code = _text(
        source.get("code")
        or source.get("stock_code")
        or source.get("ts_code")
        or source.get("symbol")
    )
    digits = "".join(char for char in raw_code.split(".", 1)[0] if char.isdigit())
    code = digits[-6:] if len(digits) >= 6 else raw_code
    stock = {
        "name": _text(source.get("name") or source.get("stock_name") or source.get("名称")),
        "code": code,
        "sector": _text(
            source.get("sector") or source.get("sector_name") or source.get("industry")
        ),
    }
    return {key: item for key, item in stock.items() if item}


def _position_pct(value: Any) -> float:
    if value in (None, "") or isinstance(value, bool):
        return 0.0
    try:
        number = float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return 0.0
    return number if 0 <= number <= 100 else 0.0


def build_proposal(selection_workflow: Any) -> dict[str, Any]:
    workflow = selection_workflow if isinstance(selection_workflow, Mapping) else {}
    raw_final = workflow.get("proposed_final")
    if not isinstance(raw_final, Mapping):
        raw_final = workflow.get("final")
    proposed_final = deepcopy(dict(raw_final)) if isinstance(raw_final, Mapping) else {}
    stock = _stock(proposed_final.get("execution_object"))
    position_pct = _position_pct(proposed_final.get("position_pct"))
    kind = "object" if stock and position_pct > 0 else "no_object"
    identity = stock if kind == "object" else {}
    proposal = {
        "kind": kind,
        "identity": identity,
        "proposed_final": proposed_final,
    }
    proposal["proposal_hash"] = sha256_json(
        {
            "kind": kind,
            "identity": identity,
            "proposed_final": proposed_final,
        }
    )
    return proposal


def _fact_id(fact: Mapping[str, Any], index: int) -> str:
    explicit = _text(fact.get("fact_id") or fact.get("sample_id") or fact.get("id"))
    return explicit or f"fact:{index:04d}:{sha256_json(fact)[:16]}"


def filter_time_valid_facts(
    facts: Iterable[Any],
    *,
    decision_cutoff_at: Any,
    target_date: Any,
    query_date: Any = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    cutoff = parse_rfc3339(decision_cutoff_at, field="decision_cutoff_at").astimezone(
        timezone.utc
    )
    normalized_target = _date(target_date)
    normalized_query = _date(query_date) if query_date else ""
    valid: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for index, raw in enumerate(facts or (), start=1):
        if not isinstance(raw, Mapping):
            record = {
                "fact_id": f"fact:{index:04d}:invalid",
                "fact_hash": sha256_json({"value": _json_ready(raw)}),
                "status": "excluded",
                "reason_codes": ["quality_failed"],
            }
            excluded.append(record)
            records.append(record)
            continue
        fact = deepcopy(dict(raw))
        fact_id = _fact_id(fact, index)
        fact_hash = sha256_json(fact)
        reasons: list[str] = []
        if "value" not in fact or fact.get("value") is None:
            reasons.append("quality_failed")
        available_at = fact.get("available_at")
        try:
            available_utc = parse_rfc3339(
                available_at, field=f"{fact_id}.available_at"
            ).astimezone(timezone.utc)
        except ConsensusContractError:
            available_utc = None
            reasons.append("missing_timestamp")
        if available_utc is not None and available_utc > cutoff:
            reasons.append("future_available")

        for field in ("trade_date", "source_date"):
            raw_date = fact.get(field)
            if raw_date in (None, ""):
                continue
            normalized = _date(raw_date)
            if not normalized or (normalized_target and normalized > normalized_target):
                reasons.append("source_date_conflict")
        raw_query_date = fact.get("query_date")
        if raw_query_date not in (None, ""):
            fact_query_date = _date(raw_query_date)
            if (
                not fact_query_date
                or (normalized_query and fact_query_date != normalized_query)
                or (normalized_target and fact_query_date > normalized_target)
            ):
                reasons.append("query_date_mismatch")

        reasons = list(dict.fromkeys(reasons))
        record = {
            "fact_id": fact_id,
            "fact_hash": fact_hash,
            "status": "excluded" if reasons else "included",
            "reason_codes": reasons,
        }
        records.append(record)
        if reasons:
            excluded.append(record)
        else:
            valid.append(fact)
    return valid, excluded, records


def build_frozen_batch(
    *,
    target_date: Any,
    query_date: Any,
    formal_input: Any,
    selection_workflow: Any,
    facts: Iterable[Any] = (),
    decision_cutoff_at: Any,
    collected_at: Any | None = None,
    run_id: str | None = None,
    model_version: str,
    prompt_version: str = PROMPT_VERSION,
    contract_version: str = REVIEW_CONTRACT_VERSION,
    knowledge_versions: Any = None,
    required_fact_ids: Iterable[str] = (),
    review_context: Any = None,
    review_system_prompt: str = DEFAULT_REVIEW_SYSTEM_PROMPT,
    review_temperature: float = DEFAULT_REVIEW_TEMPERATURE,
    review_max_tokens: int = DEFAULT_REVIEW_MAX_TOKENS,
    seed_supported: bool = False,
) -> dict[str, Any]:
    normalized_target = _date(target_date)
    normalized_query = _date(query_date)
    issue_codes: list[str] = []
    if not normalized_target:
        issue_codes.append("target_date_invalid")
    if not normalized_query or (
        normalized_target and normalized_query > normalized_target
    ):
        issue_codes.append("query_date_mismatch")
    cutoff_dt: datetime | None = None
    try:
        cutoff_dt = parse_rfc3339(
            decision_cutoff_at, field="decision_cutoff_at"
        )
        cutoff = cutoff_dt.isoformat(timespec="seconds")
    except ConsensusContractError:
        cutoff = ""
        issue_codes.append("missing_timestamp")
    if (
        cutoff_dt is not None
        and normalized_target
        and cutoff_dt.astimezone(_SHANGHAI_TZ).date().isoformat()
        != normalized_target
    ):
        issue_codes.append("decision_cutoff_date_mismatch")
    collected_source = collected_at or cutoff or _now_rfc3339()
    try:
        collected = normalize_rfc3339(collected_source, field="collected_at")
    except ConsensusContractError:
        collected = ""
        issue_codes.append("missing_timestamp")

    valid_facts: list[dict[str, Any]] = []
    excluded_facts: list[dict[str, Any]] = []
    fact_records: list[dict[str, Any]] = []
    if cutoff:
        valid_facts, excluded_facts, fact_records = filter_time_valid_facts(
            facts,
            decision_cutoff_at=cutoff,
            target_date=normalized_target,
            query_date=normalized_query,
        )

    required = {_text(item) for item in required_fact_ids if _text(item)}
    included_ids = {
        record["fact_id"] for record in fact_records if record.get("status") == "included"
    }
    if required - included_ids:
        issue_codes.append("required_fact_missing")
    if not fact_records:
        issue_codes.append("required_fact_missing")

    formal = deepcopy(dict(formal_input)) if isinstance(formal_input, Mapping) else {}
    formal_input_hash = _text(formal.get("input_hash"))
    if (
        formal.get("schema_version") != "formal_decision_input.v1"
        or formal.get("source_valid") is not True
        or not formal_input_hash
    ):
        issue_codes.append("formal_input_invalid")
    formal_date = _date(formal.get("report_date"))
    if not formal_date or (normalized_target and formal_date != normalized_target):
        issue_codes.append("source_date_conflict")
    if not formal_input_hash:
        formal_input_hash = sha256_json(formal)

    proposal = build_proposal(selection_workflow)
    workflow = (
        selection_workflow if isinstance(selection_workflow, Mapping) else {}
    )
    workflow_date = _date(workflow.get("target_date"))
    if (
        workflow.get("schema_version") != "selection_workflow.v1"
        or not isinstance(workflow.get("final"), Mapping)
        or (workflow_date and normalized_target and workflow_date != normalized_target)
    ):
        issue_codes.append("selection_workflow_invalid")
    model = _text(model_version)
    if not model:
        issue_codes.append("model_version_missing")
    normalized_seed_supported = seed_supported is True
    if not isinstance(seed_supported, bool):
        issue_codes.append("review_config_invalid")
    try:
        temperature = float(review_temperature)
    except (TypeError, ValueError):
        temperature = DEFAULT_REVIEW_TEMPERATURE
        issue_codes.append("review_config_invalid")
    try:
        max_tokens = int(review_max_tokens)
    except (TypeError, ValueError):
        max_tokens = DEFAULT_REVIEW_MAX_TOKENS
        issue_codes.append("review_config_invalid")
    if not 0 <= temperature <= 2 or max_tokens <= 0:
        issue_codes.append("review_config_invalid")
    system_prompt = _text(review_system_prompt)
    if not system_prompt:
        issue_codes.append("review_config_invalid")
        system_prompt = DEFAULT_REVIEW_SYSTEM_PROMPT
    normalized_review_context = (
        deepcopy(_json_ready(dict(review_context)))
        if isinstance(review_context, Mapping)
        else {}
    )
    normalized_review_context["time_valid_facts"] = deepcopy(valid_facts)
    review_config = {
        "system_prompt": system_prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "max_retries": 0,
    }
    compact_fact_records = [deepcopy(record) for record in fact_records]
    frozen_input_payload = {
        "target_date": normalized_target,
        "query_date": normalized_query,
        "decision_cutoff_at": cutoff,
        "formal_input_hash": formal_input_hash,
        "time_valid_fact_hashes": [sha256_json(item) for item in valid_facts],
        "knowledge_versions": _json_ready(knowledge_versions or {}),
        "review_context": normalized_review_context,
        "review_config": review_config,
    }
    input_hash = sha256_json(frozen_input_payload)
    normalized_run_id = _text(run_id) or (
        f"{normalized_target or 'invalid'}-{uuid.uuid4().hex}"
    )
    review_seeds = _build_review_seeds(
        normalized_run_id,
        seed_supported=normalized_seed_supported,
    )
    prompt_text = canonical_json(
        _review_prompt_payload(
            {
                "target_date": normalized_target,
                "proposal": proposal,
                "review_context": normalized_review_context,
            }
        )
    )
    prompt_hash = sha256_json(
        {
            "prompt_version": prompt_version,
            "contract_version": contract_version,
            "system_prompt": system_prompt,
            "prompt": prompt_text,
            "review_config": review_config,
        }
    )
    issue_codes = list(dict.fromkeys(issue_codes))
    return {
        "schema_version": BATCH_SCHEMA_VERSION,
        "run_id": normalized_run_id,
        "target_date": normalized_target,
        "query_date": normalized_query,
        "input_hash": input_hash,
        "formal_input_hash": formal_input_hash,
        "proposal_hash": proposal["proposal_hash"],
        "proposal": proposal,
        "decision_hash": None,
        "freeze_hash": None,
        "contract_version": contract_version,
        "model_version": model,
        "prompt_version": prompt_version,
        "prompt_hash": prompt_hash,
        "frozen_at": collected,
        "decision_cutoff_at": cutoff,
        "review_count": REVIEW_COUNT,
        "reviews_path": "reviews.jsonl",
        "input_status": "invalid" if issue_codes else "ready",
        "input_issue_codes": issue_codes,
        "facts": {
            "raw_count": len(fact_records),
            "time_valid_count": len(valid_facts),
            "excluded_count": len(excluded_facts),
            "records": compact_fact_records,
        },
        "time_roles": {
            "target_date": normalized_target,
            "query_date": normalized_query,
            "collected_at": collected,
            "decision_cutoff_at": cutoff,
        },
        "review_context": normalized_review_context,
        "review_config": review_config,
        "review_variability": {
            "seed_supported": normalized_seed_supported,
            "seeds": review_seeds,
        },
        "consensus": {},
        "periods": {},
        "funnel": {},
    }


def _normalized_response_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(key or "").lower())


def _find_prohibited_response_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            current = f"{path}.{key}" if path else str(key)
            normalized = _normalized_response_key(key)
            if any(part in normalized for part in _PROHIBITED_REVIEW_KEY_PARTS):
                found.append(current)
            found.extend(_find_prohibited_response_keys(item, current))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_find_prohibited_response_keys(item, f"{path}[{index}]"))
    return found


def _parse_review_response(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return deepcopy(dict(raw))
    text = str(raw or "").strip()
    match = _JSON_FENCE_RE.match(text)
    if match:
        text = match.group(1).strip()
    if not text:
        raise ConsensusContractError(
            "复核没有返回结果", reason_codes=("review_failed",)
        )
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError) as error:
        raise ConsensusContractError(
            "复核结果不是有效 JSON", reason_codes=("contract_invalid",)
        ) from error
    if not isinstance(parsed, dict):
        raise ConsensusContractError(
            "复核结果必须是 JSON 对象", reason_codes=("contract_invalid",)
        )
    return parsed


def validate_review_response(raw: Any, *, proposal_kind: str) -> dict[str, Any]:
    response = _parse_review_response(raw)
    unexpected = sorted(set(response) - _ALLOWED_REVIEW_RESPONSE_KEYS)
    prohibited = sorted(set(_find_prohibited_response_keys(response)))
    if unexpected or prohibited:
        details = unexpected or prohibited
        raise ConsensusContractError(
            f"复核结果包含不允许的字段：{'、'.join(details)}",
            reason_codes=("contract_invalid",),
        )
    vote = response.get("vote")
    if vote not in COMPLETED_VOTES:
        raise ConsensusContractError(
            "复核票值不符合契约", reason_codes=("contract_invalid",)
        )
    if proposal_kind == "object" and vote == "confirm_no_object":
        raise ConsensusContractError(
            "有对象提案不能使用无对象确认票",
            reason_codes=("contract_invalid",),
        )
    if proposal_kind == "no_object" and vote == "confirm_existing":
        raise ConsensusContractError(
            "无对象提案不能使用对象确认票",
            reason_codes=("contract_invalid",),
        )
    raw_reason = response.get("reason")
    if not isinstance(raw_reason, str):
        raise ConsensusContractError(
            "复核理由必须是文本", reason_codes=("contract_invalid",)
        )
    reason = _text(raw_reason)
    if not reason:
        raise ConsensusContractError(
            "复核理由不能为空", reason_codes=("contract_invalid",)
        )
    raw_missing_facts = response.get("missing_facts")
    raw_alternatives = response.get("alternative_mentions")
    if not isinstance(raw_missing_facts, list):
        raise ConsensusContractError(
            "复核缺失事实必须是列表", reason_codes=("contract_invalid",)
        )
    if not isinstance(raw_alternatives, list):
        raise ConsensusContractError(
            "复核替代对象说明必须是列表", reason_codes=("contract_invalid",)
        )
    if any(not isinstance(item, str) or not _text(item) for item in raw_missing_facts):
        raise ConsensusContractError(
            "复核缺失事实列表只能包含非空文本",
            reason_codes=("contract_invalid",),
        )
    missing_facts = [_text(item) for item in raw_missing_facts]
    if missing_facts:
        raise ConsensusContractError(
            "复核声明关键事实缺失，不能形成有效票",
            reason_codes=("missing_facts_reported",),
        )
    alternatives: list[dict[str, str]] = []
    for item in raw_alternatives:
        if isinstance(item, Mapping):
            stock = _stock(item)
            evidence = _text(item.get("evidence") or item.get("reason"))
            normalized = {**stock, **({"evidence": evidence} if evidence else {})}
        elif isinstance(item, str):
            normalized = {"text": _text(item)} if _text(item) else {}
        else:
            raise ConsensusContractError(
                "复核替代对象说明只能包含文本或对象",
                reason_codes=("contract_invalid",),
            )
        if not normalized:
            raise ConsensusContractError(
                "复核替代对象说明不能为空",
                reason_codes=("contract_invalid",),
            )
        alternatives.append(normalized)
    provider_request_id = response.get("provider_request_id", "")
    if not isinstance(provider_request_id, str):
        raise ConsensusContractError(
            "提供方请求标识必须是文本", reason_codes=("contract_invalid",)
        )
    if alternatives:
        vote = "deny_existing"
    return {
        "vote": vote,
        "reason": reason,
        "missing_facts": list(dict.fromkeys(missing_facts)),
        "alternative_mentions": alternatives,
        "provider_request_id": _text(provider_request_id),
    }


def build_review_request(batch: Mapping[str, Any], sequence: int) -> dict[str, Any]:
    if batch.get("schema_version") != BATCH_SCHEMA_VERSION:
        raise ConsensusContractError(
            "共识批次版本不正确", reason_codes=("quality_failed",)
        )
    if batch.get("input_status") != "ready":
        raise ConsensusContractError(
            "关键数据不完整，停止生成正式决定",
            reason_codes=tuple(batch.get("input_issue_codes") or ("quality_failed",)),
        )
    if sequence not in range(1, REVIEW_COUNT + 1):
        raise ConsensusContractError(
            "复核序号必须为 1 到 10", reason_codes=("quality_failed",)
        )
    variability = (
        batch.get("review_variability")
        if isinstance(batch.get("review_variability"), Mapping)
        else {}
    )
    seed_supported = variability.get("seed_supported") is True
    seeds = variability.get("seeds")
    if not isinstance(seeds, list) or len(seeds) != REVIEW_COUNT:
        if variability:
            raise ConsensusContractError(
                "复核 seed 登记不完整", reason_codes=("review_config_invalid",)
            )
        seeds = [None] * REVIEW_COUNT
    if seed_supported:
        valid_seeds = all(
            isinstance(item, int) and not isinstance(item, bool) and 0 <= item < 2**31
            for item in seeds
        )
        if not valid_seeds or len(set(seeds)) != REVIEW_COUNT:
            raise ConsensusContractError(
                "复核 seed 必须是十个唯一整数",
                reason_codes=("review_config_invalid",),
            )
    elif any(item is not None for item in seeds):
        raise ConsensusContractError(
            "当前提供方不支持 seed，登记值必须为空",
            reason_codes=("review_config_invalid",),
        )
    return {
        "schema_version": REVIEW_REQUEST_SCHEMA_VERSION,
        "sequence": sequence,
        "review_run_id": f"{batch['run_id']}:{sequence:02d}",
        "target_date": batch["target_date"],
        "input_hash": batch["input_hash"],
        "proposal_hash": batch["proposal_hash"],
        "contract_version": batch["contract_version"],
        "model_version": batch["model_version"],
        "prompt_hash": batch["prompt_hash"],
        "seed_supported": seed_supported,
        "seed": seeds[sequence - 1],
        "proposal": deepcopy(batch["proposal"]),
        "review_context": deepcopy(batch.get("review_context") or {}),
        "review_config": deepcopy(batch.get("review_config") or {}),
        "response_contract": {
            "allowed_fields": sorted(_ALLOWED_REVIEW_RESPONSE_KEYS),
            "allowed_votes": sorted(item for item in COMPLETED_VOTES if item),
            "account_fields_allowed": False,
        },
    }


def _review_prompt_payload(request: Mapping[str, Any]) -> dict[str, Any]:
    proposal = request.get("proposal") if isinstance(request.get("proposal"), Mapping) else {}
    identity = proposal.get("identity") if isinstance(proposal.get("identity"), Mapping) else {}
    proposal_label = (
        f"{_text(identity.get('name'))}({_text(identity.get('code'))})"
        if proposal.get("kind") == "object"
        else "无对象"
    )
    return {
        "任务": "只复核既有唯一提案，不重新选股，不给仓位或账户动作",
        "目标日": request.get("target_date"),
        "提案": proposal_label,
        "提案载荷": proposal,
        "冻结证据": request.get("review_context") or {},
        "返回格式": {
            "vote": "confirm_existing | deny_existing | confirm_no_object",
            "reason": "简短理由",
            "missing_facts": [],
            "alternative_mentions": [],
        },
        "限制": [
            "不得返回仓位、B1、B2、旧仓、退出或其他账户动作字段",
            "提到其他股票只表示否决当前提案，不能把它改成新提案",
            "只返回 JSON 对象",
        ],
    }


def build_review_prompt(request: Mapping[str, Any]) -> str:
    return canonical_json(_review_prompt_payload(request))


def make_llm_reviewer(
    llm_service: Any,
    *,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Callable[[dict[str, Any]], Any]:
    def review(request: dict[str, Any]) -> Any:
        frozen_config = (
            request.get("review_config")
            if isinstance(request.get("review_config"), Mapping)
            else {}
        )
        resolved_system_prompt = (
            system_prompt
            if system_prompt is not None
            else frozen_config.get("system_prompt", DEFAULT_REVIEW_SYSTEM_PROMPT)
        )
        resolved_temperature = (
            temperature
            if temperature is not None
            else frozen_config.get("temperature", DEFAULT_REVIEW_TEMPERATURE)
        )
        resolved_max_tokens = (
            max_tokens
            if max_tokens is not None
            else frozen_config.get("max_tokens", DEFAULT_REVIEW_MAX_TOKENS)
        )
        expected_config = {
            "system_prompt": _text(resolved_system_prompt),
            "temperature": float(resolved_temperature),
            "max_tokens": int(resolved_max_tokens),
            "max_retries": 0,
        }
        if frozen_config and expected_config != dict(frozen_config):
            raise ConsensusContractError(
                "复核配置与冻结批次不一致",
                reason_codes=("review_config_mismatch",),
            )
        service_model = _text(getattr(llm_service, "model", ""))
        if service_model != _text(request.get("model_version")):
            raise ConsensusContractError(
                "实际复核模型与冻结批次不一致",
                reason_codes=("review_config_mismatch",),
            )
        service_seed_supported = bool(
            getattr(llm_service, "seed_supported", False)
        )
        if service_seed_supported != (request.get("seed_supported") is True):
            raise ConsensusContractError(
                "实际 seed 能力与冻结批次不一致",
                reason_codes=("review_config_mismatch",),
            )

        prompt = build_review_prompt(request)
        structured_chat = getattr(llm_service, "chat_with_metadata", None)
        if not callable(structured_chat):
            if service_seed_supported:
                raise ConsensusContractError(
                    "支持 seed 的复核服务必须返回结构化请求信息",
                    reason_codes=("review_config_mismatch",),
                )
            return _LLMReviewTransportResult(
                response=llm_service.chat(
                    prompt,
                    system_prompt=expected_config["system_prompt"],
                    temperature=expected_config["temperature"],
                    max_tokens=expected_config["max_tokens"],
                    max_retries=0,
                )
            )

        result = structured_chat(
            prompt,
            system_prompt=expected_config["system_prompt"],
            temperature=expected_config["temperature"],
            max_tokens=expected_config["max_tokens"],
            max_retries=0,
            seed=request.get("seed"),
        )
        if not isinstance(result, Mapping):
            return _LLMReviewTransportResult(
                response="",
                failure_reason="结构化复核响应不正确",
                reason_codes=("review_config_mismatch",),
            )

        provider_request_id = _text(result.get("provider_request_id"))
        errors: list[str] = []
        effective_config = result.get("effective_config")
        if not isinstance(effective_config, Mapping):
            errors.append("实际复核配置缺失")
        else:
            if _text(effective_config.get("model")) != service_model:
                errors.append("实际复核模型不一致")
            try:
                actual_temperature = float(effective_config.get("temperature"))
            except (TypeError, ValueError):
                actual_temperature = None
            if actual_temperature != expected_config["temperature"]:
                errors.append("实际 temperature 不一致")
            actual_max_tokens = effective_config.get("max_tokens")
            if (
                not isinstance(actual_max_tokens, int)
                or isinstance(actual_max_tokens, bool)
                or actual_max_tokens != expected_config["max_tokens"]
            ):
                errors.append("实际 max_tokens 不一致")
        if result.get("seed_supported") != service_seed_supported:
            errors.append("实际 seed 能力不一致")
        actual_seed = result.get("seed")
        expected_seed = request.get("seed") if service_seed_supported else None
        if actual_seed != expected_seed:
            errors.append("实际 seed 不一致")
        return _LLMReviewTransportResult(
            response=result.get("content"),
            provider_request_id=provider_request_id,
            failure_reason="；".join(errors),
            reason_codes=("review_config_mismatch",) if errors else (),
        )

    setattr(review, "seed_supported", bool(getattr(llm_service, "seed_supported", False)))
    setattr(review, "model_version", _text(getattr(llm_service, "model", "")))
    return review


def _base_review_record(
    batch: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    started_at: str,
    ended_at: str,
    duration_seconds: float,
    request_started: bool = True,
    provider_request_id: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "sequence": request["sequence"],
        "review_run_id": request["review_run_id"],
        "target_date": batch["target_date"],
        "status": "failed",
        "input_hash": batch["input_hash"],
        "proposal_hash": batch["proposal_hash"],
        "contract_version": batch["contract_version"],
        "model_version": batch["model_version"],
        "prompt_hash": batch["prompt_hash"],
        "seed_supported": request.get("seed_supported") is True,
        "seed": request.get("seed"),
        "proposal": deepcopy(batch["proposal"]),
        "vote": None,
        "reason": "",
        "alternative_mentions": [],
        "missing_facts": [],
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": round(max(0.0, duration_seconds), 6),
        "request_started": bool(request_started),
        "provider_request_id": _text(provider_request_id),
        "failure_reason": "",
        "reason_codes": [],
    }


def run_consensus_reviews(
    batch: Mapping[str, Any],
    reviewer: Callable[[dict[str, Any]], Any],
    *,
    max_concurrency: int = MAX_CONCURRENCY,
    review_timeout_seconds: float = REVIEW_TIMEOUT_SECONDS,
    batch_timeout_seconds: float = BATCH_TIMEOUT_SECONDS,
    monotonic_fn: Callable[[], float] = time.monotonic,
    now_fn: Callable[[], str] = _now_rfc3339,
) -> list[dict[str, Any]]:
    if batch.get("input_status") != "ready":
        raise ConsensusContractError(
            "关键数据不完整，停止生成正式决定",
            reason_codes=tuple(batch.get("input_issue_codes") or ("quality_failed",)),
        )
    requests = [build_review_request(batch, sequence) for sequence in range(1, REVIEW_COUNT + 1)]
    max_workers = max(1, min(int(max_concurrency), MAX_CONCURRENCY, REVIEW_COUNT))
    review_timeout = max(0.001, float(review_timeout_seconds))
    batch_timeout = max(0.001, float(batch_timeout_seconds))
    batch_started_mono = monotonic_fn()
    started: dict[int, tuple[float, str]] = {}
    started_lock = threading.Lock()

    def invoke(request: dict[str, Any]) -> tuple[Any, float, str, float, str]:
        start_mono = monotonic_fn()
        start_stamp = now_fn()
        with started_lock:
            started[request["sequence"]] = (start_mono, start_stamp)
        raw = reviewer(deepcopy(request))
        end_mono = monotonic_fn()
        return raw, start_mono, start_stamp, end_mono, now_fn()

    executor = ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="daily-report-consensus",
    )
    futures = {executor.submit(invoke, request): request for request in requests}
    pending = set(futures)
    records: dict[int, dict[str, Any]] = {}
    try:
        while pending:
            now_mono = monotonic_fn()
            batch_expired = now_mono - batch_started_mono >= batch_timeout
            completed = {future for future in pending if future.done()}
            for future in completed:
                pending.remove(future)
                request = futures[future]
                sequence = request["sequence"]
                try:
                    raw, start_mono, start_stamp, end_mono, end_stamp = future.result()
                    duration = end_mono - start_mono
                    transport_result = (
                        raw if isinstance(raw, _LLMReviewTransportResult) else None
                    )
                    provider_request_id = (
                        transport_result.provider_request_id if transport_result else ""
                    )
                    response_raw = transport_result.response if transport_result else raw
                    completed_after_batch_deadline = (
                        end_mono - batch_started_mono >= batch_timeout
                    )
                    if duration > review_timeout or completed_after_batch_deadline:
                        record = _base_review_record(
                            batch,
                            request,
                            started_at=start_stamp,
                            ended_at=end_stamp,
                            duration_seconds=duration,
                            provider_request_id=provider_request_id,
                        )
                        record.update(
                            status="timeout",
                            failure_reason=(
                                "整批复核超时"
                                if completed_after_batch_deadline
                                else "单次复核超时"
                            ),
                            reason_codes=["review_timeout"],
                        )
                    else:
                        if transport_result and transport_result.failure_reason:
                            record = _base_review_record(
                                batch,
                                request,
                                started_at=start_stamp,
                                ended_at=end_stamp,
                                duration_seconds=duration,
                                provider_request_id=provider_request_id,
                            )
                            record.update(
                                status="contract_invalid",
                                failure_reason=transport_result.failure_reason,
                                reason_codes=list(transport_result.reason_codes)
                                or ["review_config_mismatch"],
                            )
                        else:
                            try:
                                response = validate_review_response(
                                    response_raw,
                                    proposal_kind=batch["proposal"]["kind"],
                                )
                            except ConsensusContractError as error:
                                record = _base_review_record(
                                    batch,
                                    request,
                                    started_at=start_stamp,
                                    ended_at=end_stamp,
                                    duration_seconds=duration,
                                    provider_request_id=provider_request_id,
                                )
                                reason_codes = list(error.reason_codes) or ["contract_invalid"]
                                status = (
                                    "failed"
                                    if "review_failed" in reason_codes
                                    else "contract_invalid"
                                )
                                record.update(
                                    status=status,
                                    failure_reason=_text(error),
                                    reason_codes=reason_codes,
                                )
                            else:
                                record = _base_review_record(
                                    batch,
                                    request,
                                    started_at=start_stamp,
                                    ended_at=end_stamp,
                                    duration_seconds=duration,
                                    provider_request_id=provider_request_id,
                                )
                                record.update(status="completed", **response)
                                if transport_result:
                                    record["provider_request_id"] = provider_request_id
                    records[sequence] = record
                except Exception as error:
                    with started_lock:
                        start_mono, start_stamp = started.get(
                            sequence, (batch_started_mono, now_fn())
                        )
                    end_mono = monotonic_fn()
                    record = _base_review_record(
                        batch,
                        request,
                        started_at=start_stamp,
                        ended_at=now_fn(),
                        duration_seconds=end_mono - start_mono,
                    )
                    if end_mono - batch_started_mono >= batch_timeout:
                        record.update(
                            status="timeout",
                            failure_reason="整批复核超时",
                            reason_codes=["review_timeout"],
                        )
                    elif isinstance(error, ConsensusContractError):
                        reason_codes = list(error.reason_codes) or ["contract_invalid"]
                        record.update(
                            status=(
                                "failed"
                                if "review_failed" in reason_codes
                                else "contract_invalid"
                            ),
                            failure_reason=_text(error),
                            reason_codes=reason_codes,
                        )
                    else:
                        record.update(
                            status="failed",
                            failure_reason=f"{type(error).__name__}: {_text(error)}",
                            reason_codes=["review_failed"],
                        )
                    records[sequence] = record

            if not pending:
                break

            now_mono = monotonic_fn()
            timed_out: list[Any] = []
            with started_lock:
                for future in pending:
                    sequence = futures[future]["sequence"]
                    start_info = started.get(sequence)
                    if start_info and now_mono - start_info[0] >= review_timeout:
                        timed_out.append(future)
            if batch_expired:
                timed_out = list(pending)
            for future in timed_out:
                if future not in pending:
                    continue
                pending.remove(future)
                request = futures[future]
                sequence = request["sequence"]
                with started_lock:
                    start_info = started.get(sequence)
                request_started = start_info is not None
                end_mono = monotonic_fn()
                end_stamp = now_fn()
                start_mono, start_stamp = start_info or (end_mono, end_stamp)
                record = _base_review_record(
                    batch,
                    request,
                    started_at=start_stamp,
                    ended_at=end_stamp,
                    duration_seconds=end_mono - start_mono,
                    request_started=request_started,
                )
                if request_started:
                    record.update(
                        status="timeout",
                        failure_reason=(
                            "整批复核超时" if batch_expired else "单次复核超时"
                        ),
                        reason_codes=["review_timeout"],
                    )
                else:
                    record.update(
                        status="failed",
                        failure_reason="整批时限内未开始复核",
                        reason_codes=["review_not_started"],
                    )
                records[sequence] = record
                future.cancel()
            if pending:
                wait(pending, timeout=0.01, return_when=FIRST_COMPLETED)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return [records[sequence] for sequence in range(1, REVIEW_COUNT + 1)]


def _review_integrity_errors(
    batch: Mapping[str, Any], reviews: Sequence[Mapping[str, Any]]
) -> list[str]:
    errors: list[str] = []
    if len(reviews) != REVIEW_COUNT:
        errors.append("review_count_mismatch")
    if not all(isinstance(item, Mapping) for item in reviews):
        return ["review_record_type_invalid"]
    sequences = [item.get("sequence") for item in reviews]
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in sequences):
        errors.append("review_sequence_mismatch")
    elif sorted(sequences) != list(range(1, REVIEW_COUNT + 1)):
        errors.append("review_sequence_mismatch")
    for review in reviews:
        if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
            errors.append("review_schema_mismatch")
        for field in (
            "target_date",
            "input_hash",
            "proposal_hash",
            "contract_version",
            "model_version",
            "prompt_hash",
        ):
            if review.get(field) != batch.get(field):
                errors.append("hash_mismatch" if field.endswith("hash") else f"{field}_mismatch")
        if review.get("status") not in REVIEW_STATUSES:
            errors.append("review_status_invalid")
        if review.get("vote") not in REVIEW_VOTES:
            errors.append("review_vote_invalid")
        if not isinstance(review.get("request_started"), bool):
            errors.append("review_started_flag_invalid")
        if not isinstance(review.get("seed_supported"), bool):
            errors.append("review_seed_flag_invalid")
        sequence = review.get("sequence")
        if isinstance(sequence, int) and not isinstance(sequence, bool):
            try:
                expected_seed = build_review_request(batch, sequence).get("seed")
            except ConsensusContractError:
                errors.append("review_seed_registration_invalid")
            else:
                if review.get("seed") != expected_seed:
                    errors.append("review_seed_mismatch")
        if not isinstance(review.get("provider_request_id"), str):
            errors.append("provider_request_id_invalid")
        status = review.get("status")
        vote = review.get("vote")
        if status == "completed" and review.get("request_started") is not True:
            errors.append("review_started_flag_invalid")
        if status == "completed" and vote not in COMPLETED_VOTES:
            errors.append("review_vote_status_mismatch")
        if status != "completed" and vote is not None:
            errors.append("review_vote_status_mismatch")
        if isinstance(sequence, int) and not isinstance(sequence, bool):
            expected_review_run_id = f"{batch.get('run_id')}:{sequence:02d}"
            if review.get("review_run_id") != expected_review_run_id:
                errors.append("review_run_id_mismatch")
        if canonical_json(review.get("proposal")) != canonical_json(batch.get("proposal")):
            errors.append("proposal_payload_mismatch")
        if not isinstance(review.get("missing_facts"), list):
            errors.append("review_missing_facts_type_invalid")
        if not isinstance(review.get("alternative_mentions"), list):
            errors.append("review_alternative_mentions_type_invalid")
        if not isinstance(review.get("reason_codes"), list):
            errors.append("review_reason_codes_type_invalid")
        if status == "completed" and not _text(review.get("reason")):
            errors.append("review_reason_missing")
        if status != "completed" and not _text(review.get("failure_reason")):
            errors.append("review_failure_reason_missing")
        try:
            started_at = parse_rfc3339(review.get("started_at"), field="started_at")
            ended_at = parse_rfc3339(review.get("ended_at"), field="ended_at")
        except ConsensusContractError:
            errors.append("review_timestamp_invalid")
        else:
            if ended_at < started_at:
                errors.append("review_timestamp_invalid")
        try:
            duration = float(review.get("duration_seconds"))
        except (TypeError, ValueError):
            errors.append("review_duration_invalid")
        else:
            if duration < 0:
                errors.append("review_duration_invalid")
    return list(dict.fromkeys(errors))


def calculate_consensus(
    batch: Mapping[str, Any], reviews: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    input_issues = list(batch.get("input_issue_codes") or [])
    integrity_errors = _review_integrity_errors(batch, reviews)
    integrity_valid = batch.get("input_status") == "ready" and not integrity_errors
    status_counts = Counter(_text(item.get("status")) for item in reviews)
    model_request_count = sum(
        1 for item in reviews if item.get("request_started") is True
    )
    proposal_kind = (batch.get("proposal") or {}).get("kind")
    confirmation_vote = (
        "confirm_no_object" if proposal_kind == "no_object" else "confirm_existing"
    )
    confirmation_count = sum(
        1
        for item in reviews
        if item.get("status") == "completed" and item.get("vote") == confirmation_vote
    )
    denial_count = sum(
        1
        for item in reviews
        if item.get("status") == "completed" and item.get("vote") == "deny_existing"
    )
    all_completed = (
        len(reviews) == REVIEW_COUNT
        and status_counts.get("completed", 0) == REVIEW_COUNT
    )
    stable = bool(
        integrity_valid
        and all_completed
        and confirmation_count >= CONSENSUS_THRESHOLD
    )
    if not integrity_valid:
        result_status = "input_invalid"
        formal_decision_mode = "stop"
    elif stable and proposal_kind == "object":
        result_status = "stable_object"
        formal_decision_mode = "commit_proposal"
    elif stable:
        result_status = "stable_no_object"
        formal_decision_mode = "commit_no_object"
    else:
        result_status = "unstable"
        formal_decision_mode = "clear_new_entry"
    reason_counts = Counter(
        _text(item.get("reason"))
        for item in reviews
        if _text(item.get("reason")) and item.get("vote") != confirmation_vote
    )
    reason_codes = list(
        dict.fromkeys(
            [*input_issues, *integrity_errors]
            + [
                code
                for item in reviews
                for code in item.get("reason_codes") or []
                if code
            ]
        )
    )
    return {
        "status": result_status,
        "stable_consensus": stable,
        "formal_decision_mode": formal_decision_mode,
        "proposal_kind": proposal_kind,
        "confirmation_vote": confirmation_vote,
        "confirmation_count": confirmation_count,
        "denial_count": denial_count,
        "denominator": REVIEW_COUNT,
        "model_request_count": model_request_count,
        "ratio": confirmation_count / REVIEW_COUNT,
        "ratio_label": f"{confirmation_count}/{REVIEW_COUNT}",
        "all_reviews_completed": all_completed,
        "integrity_valid": integrity_valid,
        "status_counts": {
            status: status_counts.get(status, 0)
            for status in sorted(REVIEW_STATUSES)
        },
        "failure_count": REVIEW_COUNT - status_counts.get("completed", 0),
        "selection_hit_count": confirmation_count if proposal_kind == "object" else 0,
        "disagreement_reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                reason_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "reason_codes": reason_codes,
        "kelly_eligible": False,
        "kelly_note": "该比例只表示同一冻结输入下的选择一致性，不是未来胜率，也不直接决定仓位。",
    }


def apply_consensus_to_selection_workflow(
    selection_workflow: Any, consensus: Mapping[str, Any]
) -> dict[str, Any]:
    if consensus.get("formal_decision_mode") == "stop":
        raise ConsensusContractError(
            "关键数据不完整，停止生成正式决定",
            reason_codes=tuple(consensus.get("reason_codes") or ("quality_failed",)),
        )
    workflow = deepcopy(dict(selection_workflow)) if isinstance(selection_workflow, Mapping) else {}
    proposed = workflow.get("proposed_final")
    if not isinstance(proposed, Mapping):
        proposed = workflow.get("final") if isinstance(workflow.get("final"), Mapping) else {}
    proposed = deepcopy(dict(proposed))
    workflow["proposed_final"] = deepcopy(proposed)
    workflow["consensus"] = deepcopy(dict(consensus))
    if consensus.get("formal_decision_mode") == "commit_proposal":
        workflow["final"] = deepcopy(proposed)
        return workflow

    final = deepcopy(proposed)
    final.update(
        {
            "execution_object": {},
            "position_pct": 0,
            "action_text": "0%不参与",
            "fail_action": "0%不参与",
            "b1_only": False,
            "b2_allowed": False,
            "trigger_paths": [],
        }
    )
    if consensus.get("formal_decision_mode") == "clear_new_entry":
        final["reason"] = "十次独立复核未形成至少7次一致确认，明日新仓0%不参与"
        final.setdefault("failure_conditions", []).append(
            "十次独立复核未形成至少7次一致确认"
        )
    workflow["final"] = final
    if isinstance(workflow.get("flowchart_payload"), Mapping):
        workflow["flowchart_payload"] = {
            **workflow["flowchart_payload"],
            "final_label": "无执行对象",
        }
    return workflow


def build_period_windows(
    *,
    target_date: Any,
    settled_trade_dates: Iterable[Any],
    metrics_by_date: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_target = _date(target_date)
    if not normalized_target:
        raise ConsensusContractError(
            "目标日期不正确", reason_codes=("target_date_invalid",)
        )
    settled = sorted(
        {
            normalized
            for item in settled_trade_dates or ()
            if (normalized := _date(item)) and normalized <= normalized_target
        }
    )
    metrics = metrics_by_date if isinstance(metrics_by_date, Mapping) else {}
    target_day = date.fromisoformat(normalized_target)
    monday = target_day.fromordinal(target_day.toordinal() - target_day.weekday())

    def window(name: str, dates: list[str], *, unsettled: bool = False) -> dict[str, Any]:
        rows = [
            {
                "trade_date": trade_date,
                "metrics": deepcopy(metrics.get(trade_date))
                if trade_date in metrics
                else None,
            }
            for trade_date in dates
        ]
        missing = [row["trade_date"] for row in rows if row["metrics"] is None]
        if unsettled:
            status = "unsettled"
        elif not dates:
            status = "empty"
        elif missing:
            status = "partial"
        else:
            status = "complete"
        return {
            "name": name,
            "status": status,
            "dates_used": dates,
            "missing_dates": missing,
            "covered_from": dates[0] if dates else None,
            "covered_to": dates[-1] if dates else None,
            "rows": rows,
        }

    target_settled = normalized_target in settled
    week_dates = [
        item
        for item in settled
        if monday <= date.fromisoformat(item) <= target_day
    ]
    return {
        "today": window(
            "today",
            [normalized_target] if target_settled else [],
            unsettled=not target_settled,
        ),
        "week": window("week", week_dates),
        "recent_7": window("recent_7", settled[-7:]),
        "recent_10": window("recent_10", settled[-10:]),
        "recent_20": window("recent_20", settled[-20:]),
    }


def _funnel_record(
    *,
    stage: str,
    unit: str,
    sample_id: str,
    parent_id: str | None,
    batch: Mapping[str, Any],
    status: str,
    reason_codes: Iterable[str] = (),
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": FUNNEL_SCHEMA_VERSION,
        "stage": stage,
        "unit": unit,
        "sample_id": sample_id,
        "parent_id": parent_id,
        "target_date": batch.get("target_date"),
        "input_hash": batch.get("input_hash"),
        "status": status,
        "reason_codes": list(dict.fromkeys(item for item in reason_codes if item)),
        "covered_from": batch.get("target_date"),
        "covered_to": batch.get("target_date"),
        "payload": deepcopy(dict(payload or {})),
    }


def build_funnel_records(
    batch: Mapping[str, Any],
    reviews: Sequence[Mapping[str, Any]],
    consensus: Mapping[str, Any],
    *,
    outcome: Mapping[str, Any] | None = None,
    export_version: str = "v1",
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    run_scope = _text(batch.get("run_id"))
    fact_records = (batch.get("facts") or {}).get("records") or []
    for fact in fact_records:
        raw_id = f"raw:{run_scope}:{fact.get('fact_id')}"
        records.append(
            _funnel_record(
                stage="raw_facts",
                unit="fact",
                sample_id=raw_id,
                parent_id=None,
                batch=batch,
                status="included",
                payload={"fact_hash": fact.get("fact_hash")},
            )
        )
        records.append(
            _funnel_record(
                stage="time_valid_facts",
                unit="fact",
                sample_id=f"time:{run_scope}:{fact.get('fact_id')}",
                parent_id=raw_id,
                batch=batch,
                status=fact.get("status") or "excluded",
                reason_codes=fact.get("reason_codes") or (),
                payload={"fact_hash": fact.get("fact_hash")},
            )
        )

    batch_id = f"batch:{batch.get('run_id')}"
    review_complete = bool(
        consensus.get("all_reviews_completed") and consensus.get("integrity_valid")
    )
    records.append(
        _funnel_record(
            stage="complete_reviews",
            unit="batch",
            sample_id=batch_id,
            parent_id=None,
            batch=batch,
            status="included" if review_complete else "excluded",
            reason_codes=(
                ()
                if review_complete
                else tuple(consensus.get("reason_codes") or ("review_failed",))
            ),
            payload={"review_count": len(reviews)},
        )
    )
    decision_hash = _text(batch.get("decision_hash")) or sha256_json(
        {
            "run_id": batch.get("run_id"),
            "proposal_hash": batch.get("proposal_hash"),
            "consensus": consensus,
        }
    )
    decision_id = f"decision:{run_scope}:{decision_hash}"
    stable = bool(consensus.get("stable_consensus"))
    records.append(
        _funnel_record(
            stage="stable_consensus",
            unit="decision",
            sample_id=decision_id,
            parent_id=batch_id,
            batch=batch,
            status="included" if stable else "excluded",
            reason_codes=() if stable else ("consensus_insufficient",),
            payload={"ratio_label": consensus.get("ratio_label")},
        )
    )
    outcome = outcome if isinstance(outcome, Mapping) else {}
    outcome_reason_codes: list[str] = []
    if not (
        outcome.get("t1_settled")
        and outcome.get("t2_settled")
        and outcome.get("facts_complete")
    ):
        outcome_reason_codes.append("outcome_incomplete")
    target_day = _date(batch.get("target_date"))
    t1_trade_date = _date(outcome.get("t1_trade_date"))
    t2_trade_date = _date(outcome.get("t2_trade_date"))
    if not (
        target_day
        and t1_trade_date
        and t2_trade_date
        and target_day < t1_trade_date < t2_trade_date
    ):
        outcome_reason_codes.append("outcome_date_invalid")
    posterior_available_at = outcome.get("posterior_available_at")
    try:
        posterior_at = parse_rfc3339(
            posterior_available_at, field="posterior_available_at"
        )
    except ConsensusContractError:
        posterior_at = None
        outcome_reason_codes.append("posterior_timestamp_invalid")
    if (
        posterior_at is not None
        and t2_trade_date
        and posterior_at.astimezone(_SHANGHAI_TZ).date().isoformat()
        < t2_trade_date
    ):
        outcome_reason_codes.append("posterior_timestamp_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", _text(outcome.get("outcome_hash"))):
        outcome_reason_codes.append("outcome_hash_invalid")
    outcome_reason_codes = list(dict.fromkeys(outcome_reason_codes))
    outcome_complete = not outcome_reason_codes
    outcome_id = f"outcome:{run_scope}:{decision_hash}:t1_t2"
    records.append(
        _funnel_record(
            stage="matured_outcomes",
            unit="outcome",
            sample_id=outcome_id,
            parent_id=decision_id,
            batch=batch,
            status="included" if stable and outcome_complete else "excluded",
            reason_codes=(
                ()
                if stable and outcome_complete
                else tuple(outcome_reason_codes or ("consensus_insufficient",))
            ),
            payload=outcome,
        )
    )
    quality_passed = bool(outcome.get("quality_passed", outcome_complete))
    training_id = (
        f"training:{run_scope}:{decision_hash}:{_text(export_version) or 'v1'}"
    )
    records.append(
        _funnel_record(
            stage="training_candidates",
            unit="training_sample",
            sample_id=training_id,
            parent_id=outcome_id,
            batch=batch,
            status=(
                "included"
                if stable and outcome_complete and quality_passed
                else "excluded"
            ),
            reason_codes=(
                ()
                if stable and outcome_complete and quality_passed
                else (
                    ("quality_failed",)
                    if outcome_complete
                    else tuple(outcome_reason_codes or ("outcome_incomplete",))
                )
            ),
            payload={
                "export_version": _text(export_version) or "v1",
                "sample_kind": (
                    "abstention"
                    if consensus.get("proposal_kind") == "no_object"
                    else "selection"
                ),
            },
        )
    )
    return records


def funnel_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    stages: dict[str, dict[str, Any]] = {}
    for item in records:
        stage = _text(item.get("stage"))
        if not stage:
            continue
        current = stages.setdefault(
            stage,
            {
                "unit": item.get("unit"),
                "included": 0,
                "excluded": 0,
                "reason_counts": {},
            },
        )
        status = "included" if item.get("status") == "included" else "excluded"
        current[status] += 1
        counter = Counter(current["reason_counts"])
        counter.update(item.get("reason_codes") or [])
        current["reason_counts"] = dict(sorted(counter.items()))
    return {
        "schema_version": FUNNEL_SCHEMA_VERSION,
        "stages": stages,
        "cross_unit_conversion_rates": None,
    }


def _proposal_label(batch: Mapping[str, Any]) -> str:
    proposal = batch.get("proposal") if isinstance(batch.get("proposal"), Mapping) else {}
    identity = proposal.get("identity") if isinstance(proposal.get("identity"), Mapping) else {}
    if proposal.get("kind") != "object":
        return "无对象"
    name = _text(identity.get("name"))
    code = _text(identity.get("code"))
    return f"{name}({code})" if name and code else name or code or "未命名对象"


def _summary_cell(value: Any, *, fallback: str = "-") -> str:
    """Keep a plain-text table row intact when a model reason contains markup."""
    text = _text(value).replace("|", "/")
    return text or fallback


def _consensus_status_label(status: Any) -> str:
    return {
        "stable_object": "稳定共识",
        "stable_no_object": "稳定不参与",
        "input_invalid": "停止生成",
        "unstable": "未形成稳定共识",
    }.get(_text(status), "结果未知")


def render_consensus_summary(
    batch: Mapping[str, Any],
    reviews: Sequence[Mapping[str, Any]],
    consensus: Mapping[str, Any],
    *,
    periods: Mapping[str, Any] | None = None,
    funnel: Mapping[str, Any] | None = None,
) -> str:
    label = _proposal_label(batch)
    status = consensus.get("status")
    if status == "stable_object":
        conclusion = f"唯一结论：{label}通过十次独立复核；仓位与B1/B2继续按既有正式账户规则计算。"
    elif status == "stable_no_object":
        conclusion = "唯一结论：无对象提案形成稳定共识，明日新仓0%不参与。"
    elif status == "input_invalid":
        conclusion = "唯一结论：关键数据不完整，停止生成正式决定。"
    else:
        conclusion = "唯一结论：当前没有稳定对象，明日新仓0%不参与。"
    timing = review_timing_summary(reviews)
    timing_p50 = timing.get("p50_seconds")
    timing_slowest = timing.get("slowest_seconds")
    lines = [
        conclusion,
        f"共识比例：{consensus.get('ratio_label', '0/10')}（固定分母10次）。",
        "执行条件：十次均完成、输入和提案哈希一致，且至少7次精确确认既有提案。",
        "不执行条件：确认不足7次，或任一复核失败、超时、返回账户动作字段。",
        "",
        "十次统计：",
        "对象 | 确认数 | 否决数 | 失败数 | 共识结果 | P50(s) | 最慢(s)",
        "{object_label} | {confirmation}/{denominator} | {denial} | {failure} | "
        "{result} | {p50:.3f} | {slowest:.3f}".format(
            object_label=_summary_cell(label),
            confirmation=_summary_cell(consensus.get("confirmation_count"), fallback="0"),
            denominator=_summary_cell(consensus.get("denominator"), fallback=str(REVIEW_COUNT)),
            denial=_summary_cell(consensus.get("denial_count"), fallback="0"),
            failure=_summary_cell(consensus.get("failure_count"), fallback="0"),
            result=_summary_cell(_consensus_status_label(status)),
            p50=float(timing_p50 or 0),
            slowest=float(timing_slowest or 0),
        ),
        "",
        "十次结果表（纯文本）：",
        "序号 | 结果 | 状态 | 耗时(s) | 理由",
    ]
    vote_labels = {
        "confirm_existing": "确认既有提案",
        "deny_existing": "否决既有提案",
        "confirm_no_object": "确认无对象",
        None: "未形成有效票",
    }
    status_labels = {
        "completed": "已完成",
        "failed": "失败",
        "timeout": "超时",
        "contract_invalid": "返回内容不符合约定",
    }
    for review in sorted(reviews, key=lambda item: int(item.get("sequence") or 0)):
        lines.append(
            "{sequence} | {vote} | {status_text} | {duration:.3f} | {reason}".format(
                sequence=_summary_cell(review.get("sequence")),
                vote=_summary_cell(vote_labels.get(review.get("vote"), "未形成有效票")),
                status_text=_summary_cell(status_labels.get(review.get("status"), "结果未知")),
                duration=float(review.get("duration_seconds") or 0),
                reason=_summary_cell(
                    review.get("reason") or review.get("failure_reason") or "未提供理由"
                ),
            )
        )
    lines.extend(["", "分歧与缺失："])
    disagreements = consensus.get("disagreement_reasons") or []
    if disagreements:
        for item in disagreements:
            lines.append(f"- {item.get('reason')}：{item.get('count')}次")
    else:
        lines.append("- 无")
    if consensus.get("reason_codes"):
        lines.append("- 原因码：" + "、".join(consensus.get("reason_codes") or []))
    lines.extend(["", "周期简报："])
    periods = periods if isinstance(periods, Mapping) else {}
    for key in ("today", "week", "recent_7", "recent_10", "recent_20"):
        item = periods.get(key) if isinstance(periods.get(key), Mapping) else {}
        lines.append(
            f"- {key}: {item.get('status', 'empty')}；"
            f"{item.get('covered_from') or '-'} 至 {item.get('covered_to') or '-'}；"
            f"缺失{len(item.get('missing_dates') or [])}日"
        )
    lines.extend(["", "样本漏斗："])
    stages = (funnel or {}).get("stages") if isinstance(funnel, Mapping) else {}
    for stage, item in (stages or {}).items():
        lines.append(
            f"- {stage}: 纳入{item.get('included', 0)}，排除{item.get('excluded', 0)}，"
            f"统计单位={item.get('unit') or '-'}"
        )
    lines.extend(["", str(consensus.get("kelly_note") or "")])
    return "\n".join(lines).rstrip() + "\n"


def consensus_output_directory(
    root_dir: str | os.PathLike[str],
    *,
    target_date: str,
    run_id: str,
    replay: bool,
) -> Path:
    root = Path(root_dir)
    base = root / "logs" / "daily_report_consensus"
    if replay:
        base /= "replay"
    return base / _date(target_date) / _text(run_id)


def _write_utf8(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def write_consensus_outputs(
    output_dir: str | os.PathLike[str],
    *,
    batch: Mapping[str, Any],
    reviews: Sequence[Mapping[str, Any]],
    summary_text: str,
    run_records: Sequence[Mapping[str, Any]],
    funnel_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    target = Path(output_dir)
    if target.exists():
        raise FileExistsError(f"运行目录已存在，不能覆盖：{target}")
    if len(reviews) != REVIEW_COUNT:
        raise ConsensusContractError(
            "复核文件必须恰好包含十条记录", reason_codes=("review_count_mismatch",)
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=str(target.parent))
    )
    try:
        serialized = {
            "batch.json": json.dumps(
                _json_ready(batch), ensure_ascii=False, sort_keys=True, indent=2
            )
            + "\n",
            "reviews.jsonl": "".join(
                canonical_json(item) + "\n" for item in reviews
            ),
            "summary.txt": str(summary_text or ""),
            "run.jsonl": "".join(
                canonical_json(item) + "\n" for item in run_records
            ),
            "funnel.jsonl": "".join(
                canonical_json(item) + "\n" for item in funnel_records
            ),
        }
        for filename in OUTPUT_FILENAMES:
            _write_utf8(staging / filename, serialized[filename])
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    paths = {filename: str(target / filename) for filename in OUTPUT_FILENAMES}
    return {
        "output_dir": str(target),
        "paths": paths,
        "sha256": {filename: sha256_file(path) for filename, path in paths.items()},
    }


def review_timing_summary(reviews: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    durations = [
        float(item.get("duration_seconds") or 0)
        for item in reviews
        if item.get("status") in REVIEW_STATUSES
    ]
    return {
        "review_count": len(reviews),
        "p50_seconds": round(median(durations), 6) if durations else None,
        "slowest_seconds": round(max(durations), 6) if durations else None,
        "failure_count": sum(1 for item in reviews if item.get("status") != "completed"),
    }


def export_training_candidates(
    output_path: str | os.PathLike[str],
    samples: Iterable[Mapping[str, Any]],
    *,
    export_version: str,
    generated_at: Any | None = None,
) -> dict[str, Any]:
    path = Path(output_path)
    if path.exists():
        raise FileExistsError(f"训练候选文件已存在，不能覆盖：{path}")
    stamp = normalize_rfc3339(
        generated_at or _now_rfc3339(), field="generated_at"
    )
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for raw in samples:
        sample = deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}
        reasons: list[str] = []
        if not sample.get("stable_consensus"):
            reasons.append("quality_failed")
        if not sample.get("outcome_complete"):
            reasons.append("outcome_incomplete")
        if not _text(sample.get("input_hash")) or not _text(sample.get("outcome_hash")):
            reasons.append("quality_failed")
        row = {
            "schema_version": TRAINING_EXPORT_SCHEMA_VERSION,
            "export_version": _text(export_version),
            "generated_at": stamp,
            **sample,
        }
        if reasons:
            row["reason_codes"] = list(dict.fromkeys(reasons))
            excluded.append(row)
        else:
            row["sample_kind"] = (
                "abstention" if sample.get("proposal_kind") == "no_object" else "selection"
            )
            accepted.append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    quality_path = path.with_suffix(path.suffix + ".quality.json")
    quality_staging = quality_path.with_name(
        f".{quality_path.name}.tmp-{uuid.uuid4().hex}"
    )
    try:
        _write_utf8(staging, "".join(canonical_json(item) + "\n" for item in accepted))
        quality = {
            "schema_version": TRAINING_EXPORT_SCHEMA_VERSION,
            "export_version": _text(export_version),
            "generated_at": stamp,
            "accepted_count": len(accepted),
            "excluded_count": len(excluded),
            "excluded": excluded,
            "training_started": False,
        }
        _write_utf8(
            quality_staging,
            json.dumps(quality, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
        os.replace(staging, path)
        os.replace(quality_staging, quality_path)
    except Exception:
        staging.unlink(missing_ok=True)
        quality_staging.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        quality_path.unlink(missing_ok=True)
        raise
    return {
        "path": str(path),
        "quality_path": str(quality_path),
        "row_count": len(accepted),
        "excluded_count": len(excluded),
        "sha256": sha256_file(path),
        "training_started": False,
    }


__all__ = [
    "BATCH_SCHEMA_VERSION",
    "BATCH_TIMEOUT_SECONDS",
    "CONSENSUS_THRESHOLD",
    "ConsensusContractError",
    "FUNNEL_SCHEMA_VERSION",
    "MAX_CONCURRENCY",
    "OUTPUT_FILENAMES",
    "PROMPT_VERSION",
    "REVIEW_CONTRACT_VERSION",
    "REVIEW_COUNT",
    "REVIEW_REQUEST_SCHEMA_VERSION",
    "REVIEW_SCHEMA_VERSION",
    "REVIEW_TIMEOUT_SECONDS",
    "TRAINING_EXPORT_SCHEMA_VERSION",
    "apply_consensus_to_selection_workflow",
    "build_frozen_batch",
    "build_funnel_records",
    "build_period_windows",
    "build_proposal",
    "build_review_prompt",
    "build_review_request",
    "calculate_consensus",
    "canonical_json",
    "consensus_output_directory",
    "export_training_candidates",
    "filter_time_valid_facts",
    "funnel_summary",
    "make_llm_reviewer",
    "normalize_rfc3339",
    "parse_rfc3339",
    "render_consensus_summary",
    "review_timing_summary",
    "run_consensus_reviews",
    "sha256_file",
    "sha256_json",
    "shanghai_rfc3339",
    "validate_review_response",
    "write_consensus_outputs",
]
