from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping


SCHEMA_VERSION = "market_polarization_evidence.v1"
DECISION_SCOPE = "explanation_only"
SECTION_HEADING = "## 8月热门股双群聚与动态迁移（研究证据）"
EXPECTED_SOURCE_DATE = "2026-08-28"
EXPECTED_CAPTURE_DATE = "2026-08-30"
EXPECTED_AVAILABLE_FROM = "2026-08-30"
DEFAULT_EVIDENCE_ROOT = (
    Path(__file__).resolve().parents[2] / "data" / "research" / "market-polarization"
)
REQUIRED_NOT_USED_FOR = frozenset(
    {
        "candidate_generation",
        "final_object",
        "position_sizing",
        "execution_nature",
        "account_action",
        "b1",
        "b2",
        "old_position_action",
        "exit_action",
    }
)
REQUIRED_SOURCE_HASHES = frozenset(
    {
        "local_snapshot_bundle_sha256",
        "tushare_daily_2026_08_27_sha256",
        "tushare_daily_2026_08_28_sha256",
        "akshare_limit_up_2026_08_28_sha256",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return ""
    return parsed.isoformat() if parsed.isoformat() == text else ""


def _stable_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_market_polarization_evidence_hash(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    normalized = deepcopy(dict(payload))
    normalized.pop("artifact_hash", None)
    return hashlib.sha256(_stable_json_bytes(normalized)).hexdigest()


def market_polarization_evidence_cache_key(
    evidence_date: Any,
    query_date: Any,
    *,
    analysis_mode: str,
) -> tuple[str, str, str, str]:
    mode = "replay" if str(analysis_mode or "").strip().lower() == "replay" else "fresh"
    return (
        "market_polarization_evidence",
        str(evidence_date or "").strip(),
        str(query_date or "").strip(),
        mode,
    )


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _validate_share(
    row: Mapping[str, Any],
    *,
    numerator_key: str,
    denominator_key: str,
    share_key: str,
    error_prefix: str,
    errors: list[str],
) -> None:
    numerator = _integer(row.get(numerator_key))
    denominator = _integer(row.get(denominator_key))
    share = _finite_number(row.get(share_key))
    if numerator is None or denominator is None or denominator <= 0:
        errors.append(f"{error_prefix}_count_invalid")
        return
    if numerator < 0 or numerator > denominator:
        errors.append(f"{error_prefix}_count_out_of_range")
    if share is None or not math.isclose(
        share,
        numerator / denominator * 100.0,
        rel_tol=0.0,
        abs_tol=0.000001,
    ):
        errors.append(f"{error_prefix}_share_mismatch")


def validate_market_polarization_evidence(
    payload: Any,
    *,
    expected_source_date: Any = "",
    available_on: Any = "",
) -> tuple[bool, list[str]]:
    if not isinstance(payload, Mapping):
        return False, ["market_polarization_evidence_type_invalid"]
    artifact = dict(payload)
    errors: list[str] = []
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("market_polarization_evidence_schema_invalid")
    if artifact.get("decision_scope") != DECISION_SCOPE:
        errors.append("market_polarization_evidence_scope_invalid")
    if artifact.get("study_id") != "august-2026-hot-stock-double-cluster":
        errors.append("market_polarization_evidence_study_invalid")

    source_date = _canonical_date(artifact.get("source_date"))
    capture_date = _canonical_date(artifact.get("capture_date"))
    available_from = _canonical_date(artifact.get("available_from"))
    query_date = _canonical_date(artifact.get("query_date"))
    expected_date = _canonical_date(expected_source_date)
    available_date = _canonical_date(available_on)
    if not source_date:
        errors.append("market_polarization_evidence_source_date_invalid")
    elif source_date != EXPECTED_SOURCE_DATE:
        errors.append("market_polarization_evidence_source_date_mismatch")
    if expected_source_date and not expected_date:
        errors.append("market_polarization_evidence_expected_date_invalid")
    elif expected_date and source_date != expected_date:
        errors.append("market_polarization_evidence_source_date_mismatch")
    if not capture_date or not available_from or not query_date:
        errors.append("market_polarization_evidence_provenance_date_invalid")
    elif not source_date or not (
        source_date <= capture_date <= available_from <= query_date
    ):
        errors.append("market_polarization_evidence_provenance_order_invalid")
    if capture_date and capture_date != EXPECTED_CAPTURE_DATE:
        errors.append("market_polarization_evidence_capture_date_mismatch")
    if available_from and available_from != EXPECTED_AVAILABLE_FROM:
        errors.append("market_polarization_evidence_available_from_mismatch")
    if available_on and not available_date:
        errors.append("market_polarization_evidence_available_on_invalid")
    elif available_date and available_from and (
        available_date < available_from
        or (query_date and query_date > available_date)
    ):
        errors.append("market_polarization_evidence_not_available_yet")

    coverage = artifact.get("coverage")
    if not isinstance(coverage, Mapping):
        errors.append("market_polarization_evidence_coverage_invalid")
        coverage = {}
    snapshot_count = _integer(coverage.get("snapshot_count"))
    snapshot_dates = coverage.get("snapshot_dates")
    missing_dates = coverage.get("missing_trade_dates")
    if snapshot_count is None or snapshot_count <= 0:
        errors.append("market_polarization_evidence_snapshot_count_invalid")
    if not isinstance(snapshot_dates, list) or not snapshot_dates:
        errors.append("market_polarization_evidence_snapshot_dates_invalid")
        snapshot_dates = []
    normalized_snapshot_dates = [_canonical_date(item) for item in snapshot_dates]
    if (
        any(not item for item in normalized_snapshot_dates)
        or normalized_snapshot_dates != sorted(set(normalized_snapshot_dates))
        or (snapshot_count is not None and len(normalized_snapshot_dates) != snapshot_count)
        or (source_date and any(item > source_date for item in normalized_snapshot_dates))
    ):
        errors.append("market_polarization_evidence_snapshot_dates_invalid")
    normalized_missing_dates = (
        [_canonical_date(item) for item in missing_dates]
        if isinstance(missing_dates, list)
        else []
    )
    if (
        not isinstance(missing_dates, list)
        or any(not item for item in normalized_missing_dates)
        or (source_date and any(item > source_date for item in normalized_missing_dates))
    ):
        errors.append("market_polarization_evidence_missing_dates_invalid")
    if normalized_snapshot_dates:
        if coverage.get("coverage_start") != normalized_snapshot_dates[0]:
            errors.append("market_polarization_evidence_coverage_start_mismatch")
        if coverage.get("coverage_end") != normalized_snapshot_dates[-1]:
            errors.append("market_polarization_evidence_coverage_end_mismatch")

    hot_rank = artifact.get("hot_rank")
    if not isinstance(hot_rank, Mapping):
        errors.append("market_polarization_evidence_hot_rank_invalid")
        hot_rank = {}
    if hot_rank.get("declared_field_name") != "hot_rank_top30":
        errors.append("market_polarization_evidence_hot_rank_field_invalid")
    if _integer(hot_rank.get("actual_rows_per_snapshot")) != 50:
        errors.append("market_polarization_evidence_hot_rank_row_size_invalid")
    industries = hot_rank.get("three_industries")
    if not isinstance(industries, list) or len(set(industries)) != 3:
        errors.append("market_polarization_evidence_industries_invalid")
    for name, limit in (("top30", 30), ("top50", 50)):
        row = hot_rank.get(name)
        if not isinstance(row, Mapping):
            errors.append(f"market_polarization_evidence_{name}_invalid")
            continue
        row_count = _integer(row.get("row_count"))
        known_count = _integer(row.get("known_industry_count"))
        if _integer(row.get("limit")) != limit:
            errors.append(f"market_polarization_evidence_{name}_limit_invalid")
        if snapshot_count is not None and row_count != snapshot_count * limit:
            errors.append(f"market_polarization_evidence_{name}_row_count_mismatch")
        if known_count is None or row_count is None or not 0 < known_count <= row_count:
            errors.append(f"market_polarization_evidence_{name}_known_count_invalid")
        _validate_share(
            row,
            numerator_key="three_industry_count",
            denominator_key="row_count",
            share_key="raw_share_pct",
            error_prefix=f"market_polarization_evidence_{name}_raw",
            errors=errors,
        )
        _validate_share(
            row,
            numerator_key="three_industry_count",
            denominator_key="known_industry_count",
            share_key="known_industry_share_pct",
            error_prefix=f"market_polarization_evidence_{name}_known",
            errors=errors,
        )
        members = row.get("persistent_members")
        if not isinstance(members, list) or not members:
            errors.append(f"market_polarization_evidence_{name}_members_invalid")
            continue
        identities = []
        for member in members:
            if not isinstance(member, Mapping):
                errors.append(f"market_polarization_evidence_{name}_member_invalid")
                continue
            code = str(member.get("code") or "").strip()
            stock_name = str(member.get("name") or "").strip()
            present_count = _integer(member.get("present_count"))
            if not code or not stock_name or present_count != snapshot_count:
                errors.append(f"market_polarization_evidence_{name}_member_invalid")
            identities.append((code, stock_name))
        if len(identities) != len(set(identities)):
            errors.append(f"market_polarization_evidence_{name}_member_duplicate")

    overlap = artifact.get("turnover_overlap")
    if not isinstance(overlap, Mapping):
        errors.append("market_polarization_evidence_overlap_invalid")
        overlap = {}
    for name, limit in (("top30", 30), ("top50", 50)):
        row = overlap.get(name)
        if not isinstance(row, Mapping):
            errors.append(f"market_polarization_evidence_overlap_{name}_invalid")
            continue
        average = _finite_number(row.get("daily_average"))
        source_value = _integer(row.get("source_date_value"))
        if (
            _integer(row.get("hot_rank_limit")) != limit
            or _integer(row.get("turnover_limit")) != 50
            or average is None
            or not 0 <= average <= limit
            or source_value is None
            or not 0 <= source_value <= limit
            or not _canonical_date(row.get("source_date"))
            or (source_date and row.get("source_date") > source_date)
        ):
            errors.append(f"market_polarization_evidence_overlap_{name}_invalid")

    source_day = artifact.get("source_day")
    if not isinstance(source_day, Mapping) or source_day.get("trade_date") != source_date:
        errors.append("market_polarization_evidence_source_day_invalid")
        source_day = {}
    turnover_top20 = source_day.get("turnover_top20")
    if not isinstance(turnover_top20, Mapping):
        errors.append("market_polarization_evidence_turnover_top20_invalid")
    else:
        row_count = _integer(turnover_top20.get("row_count"))
        three_count = _integer(turnover_top20.get("three_industry_count"))
        advancers = _integer(turnover_top20.get("advancers"))
        decliners = _integer(turnover_top20.get("decliners"))
        counts = turnover_top20.get("industry_counts")
        if (
            row_count != 20
            or three_count is None
            or not isinstance(counts, Mapping)
            or sum(value for value in counts.values() if isinstance(value, int)) != three_count
            or advancers is None
            or decliners is None
            or advancers + decliners != row_count
        ):
            errors.append("market_polarization_evidence_turnover_top20_invalid")
    concentration = source_day.get("turnover_concentration_pct")
    if not isinstance(concentration, Mapping):
        errors.append("market_polarization_evidence_concentration_invalid")
    else:
        values = [_finite_number(concentration.get(key)) for key in ("top5", "top10", "top20", "top50")]
        if any(value is None for value in values) or values != sorted(values):
            errors.append("market_polarization_evidence_concentration_invalid")
    limit_pool = source_day.get("limit_up_pool")
    if not isinstance(limit_pool, Mapping):
        errors.append("market_polarization_evidence_limit_pool_invalid")
    else:
        ladder = [
            _integer(limit_pool.get(key))
            for key in ("total_count", "board_2_or_more", "board_3_or_more", "board_4_or_more")
        ]
        if any(value is None or value < 0 for value in ladder) or ladder != sorted(ladder, reverse=True):
            errors.append("market_polarization_evidence_limit_pool_invalid")
        leaders = limit_pool.get("height_leaders")
        if not isinstance(leaders, list) or not leaders:
            errors.append("market_polarization_evidence_height_leaders_invalid")
        elif any(
            not isinstance(item, Mapping)
            or not str(item.get("name") or "").strip()
            or (_integer(item.get("board_count")) or 0) < 4
            for item in leaders
        ):
            errors.append("market_polarization_evidence_height_leaders_invalid")

    counterevidence = artifact.get("full_market_counterevidence")
    if not isinstance(counterevidence, Mapping) or not counterevidence:
        errors.append("market_polarization_evidence_counterevidence_invalid")
        counterevidence = {}
    for evidence_date, row in counterevidence.items():
        normalized_date = _canonical_date(evidence_date)
        if not normalized_date or (source_date and normalized_date > source_date) or not isinstance(row, Mapping):
            errors.append("market_polarization_evidence_counterevidence_date_invalid")
            continue
        returns = row.get("return_distribution")
        turnover = row.get("log_turnover_distribution")
        if not isinstance(returns, Mapping) or not isinstance(turnover, Mapping):
            errors.append("market_polarization_evidence_counterevidence_row_invalid")
            continue
        if not returns.get("shape_label") or returns.get("prior_update") not in {"supports", "weakens", "unresolved"}:
            errors.append("market_polarization_evidence_return_shape_invalid")
        if not turnover.get("shape_label") or turnover.get("prior_update") not in {"supports", "weakens", "unresolved"}:
            errors.append("market_polarization_evidence_turnover_shape_invalid")
        shares = [
            _finite_number(returns.get(key))
            for key in ("left_share_pct", "middle_share_pct", "right_share_pct")
        ]
        if any(value is None for value in shares) or not math.isclose(sum(shares), 100.0, abs_tol=0.02):
            errors.append("market_polarization_evidence_return_share_invalid")

    hypothesis = artifact.get("hypothesis_update")
    if not isinstance(hypothesis, Mapping):
        errors.append("market_polarization_evidence_hypothesis_invalid")
    elif (
        hypothesis.get("primary") != "H_hot_stock_core_and_dynamic_shock"
        or hypothesis.get("direction") != "supports_hot_subset_model_not_full_market_bimodality"
        or not isinstance(hypothesis.get("alternatives"), list)
        or len(hypothesis.get("alternatives")) < 3
        or not str(hypothesis.get("confidence_boundary") or "").strip()
        or not str(hypothesis.get("next_evidence") or "").strip()
    ):
        errors.append("market_polarization_evidence_hypothesis_invalid")

    source_hashes = artifact.get("source_hashes")
    if (
        not isinstance(source_hashes, Mapping)
        or not REQUIRED_SOURCE_HASHES.issubset(source_hashes)
    ):
        errors.append("market_polarization_evidence_source_hashes_invalid")
    elif any(not _SHA256_RE.fullmatch(str(value or "")) for value in source_hashes.values()):
        errors.append("market_polarization_evidence_source_hash_invalid")
    warnings = artifact.get("warnings")
    if not isinstance(warnings, list) or not warnings or any(not str(item or "").strip() for item in warnings):
        errors.append("market_polarization_evidence_warnings_invalid")
    not_used_for = artifact.get("not_used_for")
    if not isinstance(not_used_for, list) or not REQUIRED_NOT_USED_FOR.issubset(set(not_used_for)):
        errors.append("market_polarization_evidence_decision_boundary_invalid")
    expected_hash = canonical_market_polarization_evidence_hash(artifact)
    if not expected_hash or artifact.get("artifact_hash") != expected_hash:
        errors.append("market_polarization_evidence_hash_mismatch")
    return not errors, sorted(set(errors))


def load_market_polarization_evidence(
    *,
    evidence_date: Any,
    query_date: Any,
    replay_payload: Any = None,
    replay: bool = False,
    root_dir: str | Path | None = None,
) -> dict | None:
    normalized_evidence_date = _canonical_date(evidence_date)
    normalized_query_date = _canonical_date(query_date)
    if not normalized_evidence_date:
        raise ValueError("market_polarization_evidence_date_invalid")
    if not normalized_query_date:
        raise ValueError("market_polarization_query_date_invalid")
    if replay:
        if not isinstance(replay_payload, Mapping) or not replay_payload:
            return None
        payload = deepcopy(dict(replay_payload))
        valid, errors = validate_market_polarization_evidence(
            payload,
            expected_source_date=normalized_evidence_date,
            available_on=normalized_query_date,
        )
        if not valid:
            if errors == ["market_polarization_evidence_not_available_yet"]:
                return None
            raise ValueError(";".join(errors))
        return payload

    evidence_root = Path(root_dir) if root_dir is not None else DEFAULT_EVIDENCE_ROOT
    path = evidence_root / f"{normalized_evidence_date}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    valid, errors = validate_market_polarization_evidence(
        payload,
        expected_source_date=normalized_evidence_date,
        available_on=normalized_query_date,
    )
    if not valid:
        if errors == ["market_polarization_evidence_not_available_yet"]:
            return None
        raise ValueError(";".join(errors))
    return deepcopy(dict(payload))


def _md(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _pct(value: Any) -> str:
    number = _finite_number(value)
    return "事实不足" if number is None else f"{number:.2f}%"


def _member_names(row: Mapping[str, Any]) -> str:
    return "、".join(_md(item.get("name")) for item in row.get("persistent_members") or [])


def render_market_polarization_evidence_lines(payload: Any) -> list[str]:
    valid, _ = validate_market_polarization_evidence(payload)
    if not valid:
        return []
    artifact = dict(payload)
    coverage = artifact["coverage"]
    hot_rank = artifact["hot_rank"]
    top30 = hot_rank["top30"]
    top50 = hot_rank["top50"]
    overlap = artifact["turnover_overlap"]
    source_day = artifact["source_day"]
    turnover_top20 = source_day["turnover_top20"]
    limit_pool = source_day["limit_up_pool"]
    counterevidence = artifact["full_market_counterevidence"]
    hypothesis = artifact["hypothesis_update"]
    overlap_source_date = _md(
        overlap["top30"].get("source_date") or artifact.get("source_date")
    )
    source_day_date = _md(source_day.get("trade_date") or artifact.get("source_date"))
    leaders = "、".join(
        f"{_md(item.get('name'))}{item.get('board_count')}板"
        for item in limit_pool.get("height_leaders") or []
    )
    top20_industries = "、".join(
        f"{_md(name)} {count}只"
        for name, count in turnover_top20.get("industry_counts", {}).items()
    )
    lines = [
        SECTION_HEADING,
        "",
        "> [!important] 结论上限",
        "> 8月热门集合呈现“持续核心端 + 动态冲击端”的双群聚外观，当前上调的是这套研究模型的权重；全市场稳定双峰、参与者身份和后续收益优势仍未确认。",
        "",
        f"口径：市场来源日 `{artifact['source_date']}`；采集/可用日 `{artifact['capture_date']}` / `{artifact['available_from']}`；本地快照 `{coverage['snapshot_count']}` 份（`{coverage['coverage_start']}` 至 `{coverage['coverage_end']}`），缺 `{_md('、'.join(coverage['missing_trade_dates']))}`。",
        "",
        "### 持续核心端",
        "",
        "| 口径 | 三行业占全部榜单 | 三行业占已知行业 | 18/18持续成员 |",
        "|---|---:|---:|---|",
        f"| 每日前30 | {top30['three_industry_count']}/{top30['row_count']} = {_pct(top30['raw_share_pct'])} | {top30['three_industry_count']}/{top30['known_industry_count']} = {_pct(top30['known_industry_share_pct'])} | {_member_names(top30)} |",
        f"| 每日前50 | {top50['three_industry_count']}/{top50['row_count']} = {_pct(top50['raw_share_pct'])} | {top50['three_industry_count']}/{top50['known_industry_count']} = {_pct(top50['known_industry_share_pct'])} | {_member_names(top50)} |",
        "",
        f"热榜前30/前50与成交额前50的18日平均交集分别为 `{overlap['top30']['daily_average']:.6f}` / `{overlap['top50']['daily_average']:.6f}`；`{overlap_source_date}` 分别为 {overlap['top30']['source_date_value']} / {overlap['top50']['source_date_value']}。旧值 `68.9%` 混用了前50分子与前30分母，本段明确废弃。",
        "",
        "### 动态冲击端",
        "",
        f"`{source_day_date}` 成交额前20中，{top20_industries}，合计 {turnover_top20['three_industry_count']}/{turnover_top20['row_count']}；上涨 {turnover_top20['advancers']} 只、下跌 {turnover_top20['decliners']} 只。高成交集中并不等于同向上涨。",
        f"同日涨停池 {limit_pool['total_count']} 只，二板及以上 {limit_pool['board_2_or_more']} 只、三板及以上 {limit_pool['board_3_or_more']} 只、四板及以上 {limit_pool['board_4_or_more']} 只；高度端为 {leaders}。这些成员随事件和行业迁移，所以称“动态冲击端”，不称固定第二峰。",
        "",
        "### 全市场反证",
        "",
        "| 日期 | 全市场涨跌幅形态 | 左/中/右占比 | 成交额对数形态 | 对长期假设的单日更新 |",
        "|---|---|---:|---|---|",
    ]
    for evidence_date in sorted(counterevidence):
        row = counterevidence[evidence_date]
        returns = row["return_distribution"]
        turnover = row["log_turnover_distribution"]
        shares = "/".join(
            _pct(returns[key])
            for key in ("left_share_pct", "middle_share_pct", "right_share_pct")
        )
        lines.append(
            f"| {evidence_date} | `{_md(returns['shape_label'])}` | {shares} | `{_md(turnover['shape_label'])}` | 涨跌幅 `{_md(returns['prior_update'])}`；成交额 `{_md(turnover['prior_update'])}` |"
        )
    lines.extend(
        [
            "",
            "### 贝叶斯式更新",
            "",
            f"- 首要解释：`{_md(hypothesis['primary'])}`。本轮支持热门集合的双机制外观，不支持把它升级成全市场稳定双峰。",
            "- 重要备择：行业与流动性集中、热榜注意力/幸存者选择、事件轮动但没有稳定第二峰。它们可以与当前解释并存，相关证据不机械连乘。",
            f"- 置信边界：{_md(hypothesis['confidence_boundary'])}",
            "- 行动边界：本段只作解释、研究和复盘，不生成候选、仓位、B1/B2、旧仓动作或退出动作，也不单独取得买入资格。",
            f"- 下一证据：{_md(hypothesis['next_evidence'])}",
            "",
            f"研究产物哈希：`{artifact['artifact_hash']}`。",
        ]
    )
    return lines


__all__ = [
    "DECISION_SCOPE",
    "DEFAULT_EVIDENCE_ROOT",
    "SCHEMA_VERSION",
    "SECTION_HEADING",
    "canonical_market_polarization_evidence_hash",
    "load_market_polarization_evidence",
    "market_polarization_evidence_cache_key",
    "render_market_polarization_evidence_lines",
    "validate_market_polarization_evidence",
]
