from __future__ import annotations

import datetime
import math
import re
from copy import deepcopy

from report.position_tier_contract import (
    normalize_planned_position_tier_pct,
    planned_position_tier_cap_pct,
)
from report.candidate_decision_evidence import (
    build_sector_diffusion_stage_evidence,
    build_sector_tournament_three_axis,
)


SCHEMA_VERSION = "selection_workflow.v1"
DERIVATION_CONTRACT = "sector_first_strict.v1"
_ISO_DATE_IN_TEXT_PATTERN = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
LEGACY_SIGNAL_MARKERS = (
    "涨停",
    "连板",
    "T字板",
    "一字板",
    "热榜",
    "旧龙头",
)
QUOTE_LIST_KEYS = (
    "selection_workflow_quote_rows",
    "same_day_quote_rows",
    "stock_daily_quotes_recent",
    "hot_rank_top50",
    "hot_rank_top30",
    "integrated_hot_list",
    "turnover_rank",
    "turnover_over_100b",
    "zt_pool",
    "dt_pool",
    "lianban_data",
    "sector_derived_candidates",
    "market_emotion_candidates",
    "sector_leader_candidates",
    "extreme_conviction_list",
    "crossline_observation_stocks",
    "candidates",
    "watchlist",
    "core_stocks",
    "secondary_stocks",
)
STRICT_QUOTE_DATE_KEYS = {
    "selection_workflow_quote_rows",
    "same_day_quote_rows",
    "stock_daily_quotes_recent",
}
QUOTE_CONTAINER_KEYS = (
    "execution_stage_context",
    "market_research_snapshot",
    "candidate_snapshot",
    "step2_bundle",
    "candidate_selection",
    "results",
)
LIMIT_DOWN_THRESHOLD = -9.5
REQUIRED_EXECUTION_WINDOWS = (
    "09:30-09:35",
    "09:50-10:10",
    "14:30-14:55",
)
EXECUTION_WINDOW_MARKERS = REQUIRED_EXECUTION_WINDOWS + ("09:", "09：", "14:", "14：")
EXPLICIT_LIMIT_DOWN_REVERSAL_MARKERS = (
    "跌停反包",
    "跌停后反包",
    "跌停后修复",
    "跌停打开",
    "跌停开板",
    "跌停修复",
    "跌停反核",
    "跌停后反核",
    "跌停水下强势修复",
    "跌停后水下强势修复",
    "反核专项",
    "撬板",
    "翘板",
    "地天",
    "limit_down_reversal",
)
GENERATED_CONTRACT_NOISE_KEYS = {
    "brooks_price_action_judge",
    "common_selection_consistency",
    "compared_against",
    "current_reason",
    "eliminated_at",
    "eliminated_reason",
    "entry_basis",
    "first_seen_node",
    "front_observation_qualified",
    "front_observation_reason",
    "leader_debate",
    "new_entry_qualified",
    "observation_layer",
    "price_action_block_reason",
    "reversal_decision",
    "status",
    "stock_label",
    "workflow_path",
}
NODE_DEFS = [
    ("N0", "数据封装"),
    ("N1", "市场周期判断"),
    ("N2", "资金方向判断"),
    ("N3", "板块关系拆解"),
    ("N4", "板块内角色识别"),
    ("N5", "候选池归一"),
    ("N6", "反推龙头"),
    ("N7", "候选对照淘汰"),
    ("N8", "仓位与执行条件"),
    ("N9", "输出一致性复核"),
]

def clean_text(value, default=""):
    text = " ".join(str(value or "").replace("|", "｜").split()).strip()
    return text if text else default


def clean_visible_text(value, default=""):
    text = clean_text(value, default)
    replacements = (
        ("观察优先" + "锚点", "观察优先对象"),
        ("最终观察" + "锚", "最终观察对象"),
        ("观察" + "锚", "观察对象"),
        ("不是执行对象", "不是执行目标"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return text


def normalize_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def stock_payload(value):
    if not isinstance(value, dict):
        return {}
    name = clean_visible_text(value.get("name") or value.get("stock_name") or value.get("名称"))
    code = normalize_stock_code(
        value.get("code") or value.get("stock_code") or value.get("代码") or value.get("symbol")
    )
    if not (name or code):
        return {}
    payload = {"name": name, "code": code}
    sector = clean_visible_text(value.get("sector") or value.get("sector_name") or value.get("industry") or value.get("板块"))
    if sector:
        payload["sector"] = sector
    return payload


def stock_key(value):
    payload = stock_payload(value)
    return payload.get("code") or payload.get("name") or ""


def stock_label(value):
    payload = stock_payload(value)
    name = payload.get("name", "")
    code = payload.get("code", "")
    if name and code:
        return f"{name}({code})"
    return name or code or "暂无"


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return list(value) if isinstance(value, list) else []


def _clean_list(value):
    if isinstance(value, (list, tuple, set)):
        source = value
    elif value in (None, ""):
        source = []
    else:
        source = [value]
    rows = []
    for item in source:
        text = clean_visible_text(item)
        if text and text not in rows:
            rows.append(text)
    return rows


def _dated_evidence_items(value, target_date):
    if isinstance(value, (list, tuple)):
        source = value
    elif value in (None, ""):
        source = []
    else:
        source = [value]
    rows = []
    for item in source:
        if isinstance(item, dict):
            item_date = next(
                (
                    _valid_trade_date(item.get(key))
                    for key in ("source_date", "trade_date", "date", "query_date")
                    if _valid_trade_date(item.get(key))
                ),
                "",
            )
            text = clean_visible_text(
                item.get("text")
                or item.get("evidence")
                or item.get("description")
            )
        else:
            item_date = ""
            text = clean_visible_text(item)
        embedded_dates = [
            _valid_trade_date(match)
            for match in _ISO_DATE_IN_TEXT_PATTERN.findall(text)
            if _valid_trade_date(match)
        ]
        if (
            not text
            or not (item_date or embedded_dates)
            or (item_date and target_date and item_date > target_date)
            or any(target_date and date > target_date for date in embedded_dates)
        ):
            continue
        source_date = item_date or max(embedded_dates)
        row = {"text": text, "source_date": source_date}
        if row not in rows:
            rows.append(row)
    return rows


def _first_non_empty(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _explicit_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = clean_text(value).lower()
    if text in {"1", "true", "yes", "y", "confirmed", "complete", "完整", "成立", "已确认"}:
        return True
    if text in {"0", "false", "no", "n", "failed", "missing", "incomplete", "不足", "缺失", "未确认", "不成立"}:
        return False
    return None


def _source_value(sources, *keys):
    for source in sources:
        source = _as_dict(source)
        for key in keys:
            if key in source and source.get(key) not in (None, "", [], {}):
                return source.get(key)
    return None


def _safe_float(value):
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace("%", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def _candidate_change_pct(candidate):
    candidate = _as_dict(candidate)
    for source in (_as_dict(candidate.get("same_day_quote")), candidate):
        for key in ("change_pct", "pct_chg", "涨跌幅", "zdf", "change_rate"):
            parsed = _safe_float(source.get(key))
            if parsed is not None:
                return parsed
    return None


def _limit_status_text(candidate):
    candidate = _as_dict(candidate)
    parts = []
    for source in (_as_dict(candidate.get("same_day_quote")), candidate):
        for key in (
            "limit_status",
            "limit_state",
            "zt_status",
            "涨停状态",
            "涨跌停状态",
            "status",
            "tag",
            "pattern",
            "连板标签",
            "candlestick",
        ):
            value = clean_visible_text(source.get(key))
            if value:
                parts.append(value)
    return " / ".join(parts)


def _is_negated_limit_down_text(text):
    return any(marker in text for marker in ("未跌停", "非跌停", "不跌停", "没有跌停", "并非跌停"))


def _candidate_limit_down_block_reason(candidate):
    candidate = _as_dict(candidate)
    if not candidate:
        return ""
    for source in (candidate, _as_dict(candidate.get("same_day_quote"))):
        if source.get("is_limit_down") is True:
            return "同日状态为跌停"
    change_pct = _candidate_change_pct(candidate)
    if change_pct is not None and change_pct <= LIMIT_DOWN_THRESHOLD:
        return f"同日跌幅{change_pct:.2f}%，按跌停/接近跌停处理"
    status_text = _limit_status_text(candidate)
    if "跌停" in status_text and not _is_negated_limit_down_text(status_text):
        return "同日状态为跌停"
    return ""


def _candidate_contract_text(candidate, *, include_quote=True):
    candidate = _as_dict(candidate)
    nested = _as_dict(candidate.get("anchor_reversal"))
    quote = _as_dict(candidate.get("same_day_quote"))
    planned = _as_dict(candidate.get("planned_participation"))
    script = _as_dict(candidate.get("participation_script"))
    reversal_plan = _as_dict(candidate.get("limit_down_reversal_plan"))
    parts = []
    sources = [candidate, nested, planned, script, reversal_plan]
    if include_quote:
        sources.insert(2, quote)
    for source in sources:
        for key, value in source.items():
            if key in GENERATED_CONTRACT_NOISE_KEYS:
                continue
            if isinstance(value, (dict, list)):
                continue
            text = clean_visible_text(value)
            if text:
                parts.append(text)
    return " / ".join(parts)


def _candidate_has_confirmation_window(candidate):
    text = _candidate_contract_text(candidate, include_quote=False)
    if any(marker in text for marker in EXECUTION_WINDOW_MARKERS):
        return True
    for source in (
        _as_dict(candidate),
        _as_dict(candidate.get("planned_participation")),
        _as_dict(candidate.get("participation_script")),
        _as_dict(candidate.get("limit_down_reversal_plan")),
    ):
        for key in ("participation_window", "buy_window", "execution_window", "window"):
            value = clean_visible_text(source.get(key))
            if any(marker in value for marker in EXECUTION_WINDOW_MARKERS):
                return True
    return False


def _candidate_has_invalid_condition(candidate):
    text = _candidate_contract_text(candidate, include_quote=False)
    if any(marker in text for marker in ("作废", "取消", "失效", "认错线", "跌破", "站不回", "封死", "打不开")):
        return True
    for source in (
        _as_dict(candidate),
        _as_dict(candidate.get("planned_participation")),
        _as_dict(candidate.get("participation_script")),
        _as_dict(candidate.get("limit_down_reversal_plan")),
    ):
        for key in ("cancellation", "cancellation_conditions", "invalid_price", "stop_price"):
            if source.get(key) not in (None, "", []):
                return True
    return False


def _candidate_has_zero_fallback(candidate):
    text = _candidate_contract_text(candidate, include_quote=False)
    return "回到0%" in text or "0%不参与" in text or ("0%" in text and "不参与" in text)


def _has_explicit_limit_down_reversal_text(text):
    text = clean_visible_text(text)
    return any(marker in text for marker in EXPLICIT_LIMIT_DOWN_REVERSAL_MARKERS)


def _candidate_has_explicit_limit_down_reversal_plan(candidate):
    text = _candidate_contract_text(candidate, include_quote=False)
    has_reversal = _has_explicit_limit_down_reversal_text(text)
    return bool(
        has_reversal
        and _candidate_has_confirmation_window(candidate)
        and _candidate_has_invalid_condition(candidate)
        and _candidate_has_zero_fallback(candidate)
    )


def _candidate_limit_down_reversal_plan_payload(candidate):
    candidate = _as_dict(candidate)
    if not _candidate_has_explicit_limit_down_reversal_plan(candidate):
        return {}
    payload = {
        "status": "complete",
        "contract_text": _candidate_contract_text(candidate, include_quote=False),
    }
    sources = (
        candidate,
        _as_dict(candidate.get("anchor_reversal")),
        _as_dict(candidate.get("planned_participation")),
        _as_dict(candidate.get("participation_script")),
    )
    for key in (
        "execution_eligibility",
        "participation_window",
        "buy_window",
        "execution_window",
        "window",
        "cancellation",
        "cancellation_conditions",
        "invalid_price",
        "stop_price",
        "fallback_state",
    ):
        value = next((source.get(key) for source in sources if source.get(key) not in (None, "", [])), None)
        if value not in (None, "", []):
            payload[key] = value
    return payload


def candidate_limit_down_risk_review_reason(candidate):
    reason = _candidate_limit_down_block_reason(candidate)
    if not reason:
        candidate = _as_dict(candidate)
        price_action = _as_dict(candidate.get("brooks_price_action_judge"))
        generated_risk_texts = [
            clean_visible_text(candidate.get("price_action_block_reason")),
            clean_visible_text(candidate.get("risk_evidence")),
            clean_visible_text(price_action.get("verdict")),
            clean_visible_text(price_action.get("participation_effect")),
        ]
        explicit_limit_down_text = next(
            (
                text
                for text in generated_risk_texts
                if "跌停" in text and not _is_negated_limit_down_text(text)
            ),
            "",
        )
        if explicit_limit_down_text:
            reason = (
                explicit_limit_down_text
                if "同日" in explicit_limit_down_text
                else "同日状态为跌停"
            )
    if not reason or _candidate_has_explicit_limit_down_reversal_plan(candidate):
        return ""
    return reason


def _candidate_blocks_new_entry_by_price(candidate):
    reason = _candidate_limit_down_block_reason(candidate)
    if reason:
        return candidate_limit_down_risk_review_reason(candidate)
    price_action = _brooks_price_action_judge(candidate)
    if price_action.get("status") in {"risk_first", "price_rejected"}:
        return clean_visible_text(
            price_action.get("participation_effect")
            or price_action.get("verdict")
            or "价格否定优先，不新增参与"
        )
    return ""


def _quote_row_has_price_context(row):
    row = _as_dict(row)
    if not row:
        return False
    if _candidate_change_pct(row) is not None:
        return True
    if _limit_status_text(row):
        return True
    ohlc_keys = (
        ("open", "开盘价", "开盘", "open_price"),
        ("high", "最高价", "最高", "high_price"),
        ("low", "最低价", "最低", "low_price"),
        ("close", "收盘价", "最新价", "收盘", "price", "当前价", "close_price"),
    )
    return all(
        any(_safe_float(row.get(key)) is not None for key in keys)
        for keys in ohlc_keys
    )


def _quote_identity(row, *, code="", name=""):
    row = _as_dict(row)
    normalized_code = normalize_stock_code(
        code
        or row.get("code")
        or row.get("stock_code")
        or row.get("代码")
        or row.get("symbol")
        or row.get("ts_code")
    )
    normalized_name = clean_visible_text(name or row.get("name") or row.get("stock_name") or row.get("名称"))
    return normalized_code, normalized_name


def _quote_rank(row):
    score = 0
    if _candidate_limit_down_block_reason(row):
        score += 10
    if _candidate_change_pct(row) is not None:
        score += 3
    for key in ("open", "high", "low", "close"):
        if _safe_float(_as_dict(row).get(key)) is not None:
            score += 1
    return score


def _normalize_quote_date(value):
    text = clean_text(value)
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def _valid_trade_date(value):
    normalized = _normalize_quote_date(value)
    try:
        return datetime.date.fromisoformat(normalized).isoformat()
    except (TypeError, ValueError):
        return ""


def _mapping_dates(value, *keys):
    value = _as_dict(value)
    dates = []
    for key in keys:
        normalized = _normalize_quote_date(value.get(key))
        if normalized and normalized not in dates:
            dates.append(normalized)
    return dates


def _nested_source_date(value, key):
    source_dates = _as_dict(_as_dict(value).get("source_dates"))
    return _normalize_quote_date(source_dates.get(key))


def _sector_source_date(data, context, snapshot, supplied=None):
    roots = (
        _as_dict(supplied),
        _as_dict(context),
        _as_dict(snapshot),
    )
    dated_sources = list(roots)
    for root in (*roots[1:], _as_dict(data)):
        dated_sources.extend(
            _as_dict(root.get(key))
            for key in (
                "mainline_turnover_summary",
                "current_sector_turnover_snapshot",
                "current_mainline_history_record",
            )
        )
    for source in dated_sources:
        nested = _nested_source_date(source, "sector_source_date")
        if nested:
            return nested
        dates = _mapping_dates(
            source,
            "sector_source_date",
            "trade_date",
            "source_date",
            "date",
        )
        if dates:
            return dates[0]
    return _nested_source_date(data, "sector_source_date")


def _selection_source_dates(target_date, data, context, snapshot, local_trend_sector_proof):
    target_date = _normalize_quote_date(target_date)
    snapshot_date = _nested_source_date(snapshot, "snapshot_date")
    if not snapshot_date:
        dates = _mapping_dates(snapshot, "snapshot_date", "target_date", "trade_date", "source_date", "date")
        snapshot_date = dates[0] if dates else ""
    price_source_date = ""
    for source in (_as_dict(context), _as_dict(snapshot), _as_dict(data)):
        price_source_date = _nested_source_date(source, "price_source_date")
        if price_source_date:
            break
        dates = _mapping_dates(source, "price_source_date")
        if dates:
            price_source_date = dates[0]
            break
    return {
        "report_date": target_date or None,
        "snapshot_date": snapshot_date or None,
        "sector_source_date": _normalize_quote_date(
            _as_dict(local_trend_sector_proof).get("source_date")
        )
        or None,
        "price_source_date": price_source_date or None,
    }


def _quote_row_matches_target_date(row, target_date="", *, require_date=False):
    target_date = _normalize_quote_date(target_date)
    if not target_date:
        return True
    row = _as_dict(row)
    primary_dates = [
        _normalize_quote_date(row.get(key))
        for key in ("trade_date", "target_date", "date", "latest_trade_date")
        if _normalize_quote_date(row.get(key))
    ]
    if primary_dates:
        return target_date in primary_dates
    secondary_dates = [
        _normalize_quote_date(row.get(key))
        for key in ("source_date", "query_date", "report_date")
        if _normalize_quote_date(row.get(key))
    ]
    if secondary_dates:
        return target_date in secondary_dates
    return not require_date


def _quote_source_matches_target_date(source, target_date=""):
    if not _normalize_quote_date(target_date):
        return True
    return _quote_row_matches_target_date(source, target_date, require_date=True)


def _register_quote(lookup, row, *, code="", name="", target_date="", require_date=False):
    row = _as_dict(row)
    if not row or not _quote_row_has_price_context(row):
        return
    if not _quote_row_matches_target_date(row, target_date, require_date=require_date):
        return
    normalized_code, normalized_name = _quote_identity(row, code=code, name=name)
    payload = dict(row)
    if normalized_code:
        payload.setdefault("code", normalized_code)
    if normalized_name:
        payload.setdefault("name", normalized_name)
    for kind, key in (("code", normalized_code), ("name", normalized_name)):
        if not key:
            continue
        existing = lookup.get((kind, key))
        if existing is None or _quote_rank(payload) > _quote_rank(existing):
            lookup[(kind, key)] = payload


def _iter_quote_rows(source, *, depth=0, visited=None, target_date="", trusted_undated=False):
    if depth > 4 or not isinstance(source, dict):
        return
    if visited is None:
        visited = set()
    marker = id(source)
    if marker in visited:
        return
    visited.add(marker)
    source_trusted_undated = bool(trusted_undated or _quote_source_matches_target_date(source, target_date))

    stock_full_info = source.get("stock_full_info") if isinstance(source.get("stock_full_info"), dict) else {}
    for code, info in stock_full_info.items():
        if isinstance(info, dict):
            yield code, "", info, "stock_full_info", source_trusted_undated

    for key in QUOTE_LIST_KEYS:
        rows = source.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                yield "", "", row, key, source_trusted_undated

    for key in QUOTE_CONTAINER_KEYS:
        nested = source.get(key)
        if isinstance(nested, dict):
            yield from _iter_quote_rows(
                nested,
                depth=depth + 1,
                visited=visited,
                target_date=target_date,
                trusted_undated=source_trusted_undated,
            )


def _build_quote_lookup(*sources, target_date=""):
    lookup = {}
    for source in sources:
        for code, name, row, source_key, source_trusted_undated in _iter_quote_rows(
            _as_dict(source),
            target_date=target_date,
        ):
            require_date = source_key in STRICT_QUOTE_DATE_KEYS or (
                bool(_normalize_quote_date(target_date)) and not source_trusted_undated
            )
            _register_quote(
                lookup,
                row,
                code=code,
                name=name,
                target_date=target_date,
                require_date=require_date,
            )
    return lookup


def _candidate_quote(candidate, quote_lookup):
    candidate = _as_dict(candidate)
    code, name = _quote_identity(candidate)
    if code and (quote_lookup or {}).get(("code", code)):
        return (quote_lookup or {}).get(("code", code)) or {}
    if name and (quote_lookup or {}).get(("name", name)):
        return (quote_lookup or {}).get(("name", name)) or {}
    return {}


def _first_quote_value(quote, *keys):
    quote = _as_dict(quote)
    for key in keys:
        value = quote.get(key)
        if value not in (None, ""):
            return value
    return None


def _candidate_with_quote(candidate, quote_lookup):
    candidate = _as_dict(candidate)
    quote = _candidate_quote(candidate, quote_lookup)
    if not quote:
        return candidate
    merged = dict(candidate)
    merged["same_day_quote"] = dict(quote)
    for target_key, source_keys in (
        ("change_pct", ("change_pct", "pct_chg", "涨跌幅", "zdf", "change_rate")),
        ("open", ("open", "开盘价", "开盘", "open_price")),
        ("high", ("high", "最高价", "最高", "high_price")),
        ("low", ("low", "最低价", "最低", "low_price")),
        ("close", ("close", "收盘价", "最新价", "收盘", "price", "当前价", "close_price")),
        ("limit_status", ("limit_status", "limit_state", "zt_status", "涨停状态", "涨跌停状态", "tag", "连板标签")),
    ):
        if merged.get(target_key) in (None, ""):
            value = _first_quote_value(quote, *source_keys)
            if value not in (None, ""):
                merged[target_key] = value
    return merged


def _text_has_any(text, markers):
    return any(marker in text for marker in markers)


def _candidate_price_text(candidate):
    candidate = _as_dict(candidate)
    nested = _as_dict(candidate.get("anchor_reversal"))
    quote = _as_dict(candidate.get("same_day_quote"))
    parts = []
    for source in (candidate, nested, quote):
        for key in (
            "pattern",
            "shape",
            "candlestick",
            "volume_state",
            "volume_pattern",
            "volume_summary",
            "abnormal_summary",
            "abnormal_follow_state",
            "capital_trace",
            "conviction_rule",
            "conviction_reason",
            "entered_reason",
            "reason",
            "anchor_reversal_reason",
            "why_not_anchor",
            "execution_eligibility",
            "limit_up_evidence_role",
            "limit_status",
            "limit_state",
            "zt_status",
            "涨停状态",
            "涨跌停状态",
            "tag",
            "连板标签",
        ):
            value = clean_visible_text(source.get(key))
            if value:
                parts.append(value)
    change_pct = _candidate_change_pct(candidate)
    if change_pct is not None:
        parts.append(f"涨跌幅{change_pct:+.2f}%")
    return " / ".join(parts)


def _candlestick_consequence(candidate):
    candidate = _as_dict(candidate)
    quote = _as_dict(candidate.get("same_day_quote"))

    def price_value(*keys):
        for source in (quote, candidate):
            for key in keys:
                parsed = _safe_float(source.get(key))
                if parsed is not None:
                    return parsed
        return None

    open_price = price_value("open", "open_price", "开盘价", "开盘")
    high_price = price_value("high", "high_price", "最高价", "最高")
    low_price = price_value("low", "low_price", "最低价", "最低")
    close_price = price_value("close", "close_price", "latest_price", "price", "最新价", "收盘价", "收盘", "当前价")
    if None in (open_price, high_price, low_price, close_price) or high_price <= low_price:
        return ""
    tolerance = max(abs(close_price) * 0.01, 0.02)
    if high_price - close_price <= tolerance:
        return "强收盘"
    body_high = max(open_price, close_price)
    upper_shadow = max(high_price - body_high, 0)
    full_range = high_price - low_price
    if upper_shadow >= full_range * 0.35 and high_price - close_price > tolerance:
        return "长上影"
    if close_price <= low_price + tolerance:
        return "弱收盘"
    return ""


def _brooks_price_action_judge(candidate):
    text = _candidate_price_text(candidate)
    candle = _candlestick_consequence(candidate)
    if candle:
        text = f"{text} / {candle}" if text else candle

    volume_signal = "未知"
    if _text_has_any(text, ("缩量", "量缩")):
        volume_signal = "缩量"
    if _text_has_any(text, ("放量", "显著放量", "爆量", "巨量", "倍量")):
        volume_signal = "放量"

    risk_markers = ("放量破位", "放量下杀", "放量大跌", "A杀", "破位", "收不回", "弱收盘")
    rejection_markers = ("冲高回落", "长上影", "炸板", "上影线未修复", "供应", "分歧")
    attack_markers = ("强收盘", "收在高位", "涨停", "大阳", "突破", "回封", "分歧转一致")
    pullback_markers = ("缩量回踩", "缩量消化", "回踩不破", "趋势未破", "低点上移")
    limit_down_reason = _candidate_limit_down_block_reason(candidate)

    if limit_down_reason and _candidate_has_explicit_limit_down_reversal_plan(candidate):
        verdict = "跌停后反包修复待确认"
        action = "只按反包专项执行条件复核，不满足回到0%不参与"
        status = "needs_second_confirmation"
    elif limit_down_reason:
        verdict = "跌停风险优先"
        action = "同日跌停/接近跌停，只能修复观察，不沿用正常强趋势模板"
        status = "risk_first"
    elif _text_has_any(text, risk_markers):
        verdict = "先处理风险"
        action = "价格否定优先，不能用成交量或便宜解释参与"
        status = "risk_first"
    elif volume_signal == "放量" and _text_has_any(text, rejection_markers):
        verdict = "资金表态未被价格接受"
        action = "降级观察，等待后续行情重新确认"
        status = "price_rejected"
    elif volume_signal == "放量" and _text_has_any(text, attack_markers):
        verdict = "资金表态被价格接受"
        action = "进入N7对照，仍需板块同步、账户和时间窗口配合"
        status = "accepted"
    elif volume_signal == "缩量" and _text_has_any(text, pullback_markers):
        verdict = "缩量回踩等待二次确认"
        action = "只保留条件执行可能，不把缩量本身当买入理由"
        status = "needs_second_confirmation"
    else:
        verdict = "价格行为证据不足"
        action = "不新增资格，继续按板块锚、共同选择和风险条件复核"
        status = "insufficient"

    return {
        "price_first_rule": "价格趋势、常用K线和收盘位置优先，指标组合只作辅助",
        "volume_role": "成交量是资金表态，必须由价格结果确认",
        "volume_signal": volume_signal,
        "candlestick_consequence": candle or "待确认",
        "verdict": verdict,
        "participation_effect": action,
        "status": status,
    }


def _leader_debate(candidate):
    candidate = _as_dict(candidate)
    nested = _as_dict(candidate.get("anchor_reversal"))
    role = clean_visible_text(
        candidate.get("candidate_role")
        or candidate.get("core_identity")
        or nested.get("candidate_role")
        or "角色待确认"
    )
    anchor = clean_visible_text(candidate.get("sector_anchor") or nested.get("sector_anchor") or "板块锚待确认")
    decision = _anchor_reversal_decision(candidate) or "待确认"
    why_not_anchor = clean_visible_text(
        candidate.get("why_not_anchor")
        or nested.get("why_not_anchor")
        or candidate.get("anchor_reversal_reason")
        or nested.get("anchor_reversal_reason")
    )
    pro = [part for part in (role, anchor, decision) if part]
    contra = [why_not_anchor] if why_not_anchor else ["反方证据待补"]
    return {
        "question": "为什么做它，为什么不做板块锚",
        "positive_evidence": pro,
        "negative_evidence": contra,
        "conclusion": decision,
    }


def _common_selection_consistency(candidate):
    candidate = _as_dict(candidate)
    nested = _as_dict(candidate.get("anchor_reversal"))
    explicit = clean_visible_text(
        candidate.get("common_selection_consistency")
        or candidate.get("common_selection_check")
        or candidate.get("共同选择")
        or nested.get("common_selection_consistency")
    )
    if explicit:
        return {"status": "已提供", "summary": explicit}
    return {
        "status": "待复核",
        "summary": "昨日持筹者、明日新买盘、主线资金和量化动量仍需在N7对照",
    }


def _position_pct(position_decision=None):
    position_decision = _as_dict(position_decision)
    try:
        raw = position_decision.get("target_position_pct")
        if raw is None:
            raw = position_decision.get("position_pct")
        return normalize_planned_position_tier_pct(raw)
    except (TypeError, ValueError):
        return 0


def _node(
    node_id,
    name,
    *,
    input_refs=None,
    input_summary=None,
    judgement="",
    passes_forward=None,
    cannot_conclude=None,
    conflicts=None,
    candidate_changes=None,
):
    return {
        "node_id": node_id,
        "node_name": name,
        "input_refs": list(input_refs or []),
        "input_summary": list(input_summary or []),
        "judgement": clean_text(judgement, "待确认"),
        "passes_forward": passes_forward if isinstance(passes_forward, dict) else {},
        "cannot_conclude": list(cannot_conclude or []),
        "conflicts": list(conflicts or []),
        "candidate_changes": list(candidate_changes or []),
    }


def _candidate_sources(execution_stage_context):
    context = _as_dict(execution_stage_context)
    rows = []
    candidate_keys = (
        "sector_derived_candidates",
        "market_emotion_candidates",
        "sector_leader_candidates",
        "extreme_conviction_list",
        "crossline_observation_stocks",
        "candidates",
        "watchlist",
        "core_stocks",
        "secondary_stocks",
    )
    for key in candidate_keys:
        for item in _as_list(context.get(key)):
            if isinstance(item, dict):
                rows.append((key, item))
    for nested_key in ("step2_bundle", "candidate_selection", "candidate_snapshot"):
        nested = _as_dict(context.get(nested_key))
        for key in candidate_keys:
            for item in _as_list(nested.get(key)):
                if isinstance(item, dict):
                    rows.append((f"{nested_key}.{key}", item))
    return rows


def _candidate_source_rows(execution_stage_context, selected_position_candidate=None):
    rows = list(_candidate_sources(execution_stage_context))
    selected = selected_position_candidate if isinstance(selected_position_candidate, dict) else {}
    selected_key = stock_key(selected)
    if not selected_key:
        return rows
    matched_rows = []
    remaining_rows = []
    for source_key, candidate in rows:
        if _candidate_matches_selected(candidate, selected):
            merged = dict(candidate)
            merged.update({key: value for key, value in selected.items() if value not in (None, "")})
            if not clean_visible_text(merged.get("candidate_role")) and clean_visible_text(candidate.get("candidate_role")):
                merged["candidate_role"] = candidate.get("candidate_role")
            if not clean_visible_text(merged.get("sector_derivation_evidence")) and clean_visible_text(candidate.get("sector_derivation_evidence")):
                merged["sector_derivation_evidence"] = candidate.get("sector_derivation_evidence")
            matched_rows.append((source_key, merged))
        else:
            remaining_rows.append((source_key, candidate))
    if matched_rows:
        return matched_rows + remaining_rows
    enriched = dict(selected)
    enriched.setdefault("source_pools", ["运行时观察对象"])
    enriched.setdefault("entered_reason", "来自运行时观察对象")
    return [("selected_position_candidate", enriched)] + rows


def _quote_backfill_enabled(*sources):
    return any(_as_dict(source).get("enable_selection_workflow_quote_backfill") for source in sources)


def _candidate_codes_for_quote_backfill(execution_stage_context, selected_position_candidate=None):
    codes = []
    seen = set()
    for _, candidate in _candidate_source_rows(execution_stage_context, selected_position_candidate):
        code = stock_payload(candidate).get("code")
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def _query_quote_backfill_rows(target_date="", stock_codes=None):
    target_date = clean_text(target_date)
    stock_codes = [code for code in stock_codes or [] if code]
    if not target_date or not stock_codes:
        return []
    try:
        from storage.database_service import DatabaseService

        service_factory = getattr(DatabaseService, "fact_store_from_environment", None)
        service = service_factory() if callable(service_factory) else DatabaseService.from_environment()
        reader = getattr(service, "query_stock_daily_quotes_recent", None)
        if not callable(reader):
            return []
        rows = reader(target_date, stock_codes=stock_codes)
    except Exception:
        return []
    return [dict(row) for row in rows or [] if isinstance(row, dict)]


def _backfill_quote_lookup(quote_lookup, target_date="", execution_stage_context=None, selected_position_candidate=None):
    codes = _candidate_codes_for_quote_backfill(execution_stage_context, selected_position_candidate)
    for row in _query_quote_backfill_rows(target_date, codes):
        _register_quote(quote_lookup, row, target_date=target_date, require_date=True)
    return quote_lookup


def _anchor_reversal_decision(candidate):
    candidate = _as_dict(candidate)
    return clean_visible_text(
        candidate.get("anchor_reversal_decision")
        or _as_dict(candidate.get("anchor_reversal")).get("anchor_reversal_decision")
    )


def _candidate_status(candidate, final_key):
    key = stock_key(candidate)
    if final_key and key == final_key:
        return "最终执行对象"
    decision = _anchor_reversal_decision(candidate)
    if decision == "降级观察":
        return "降级观察"
    if decision == "不参与":
        return "不参与"
    return "过程候选"


def _entered_reason(source_key, candidate):
    reason = clean_visible_text(
        candidate.get("entered_reason")
        or candidate.get("conviction_reason")
        or candidate.get("reason")
        or candidate.get("conviction_rule")
        or candidate.get("pattern")
    )
    return reason or f"来自{source_key}"


def _candidate_text_blob(candidate):
    candidate = _as_dict(candidate)
    nested = _as_dict(candidate.get("anchor_reversal"))
    values = []
    for source in (candidate, nested):
        for key in (
            "source_pools",
            "pattern",
            "entered_reason",
            "reason",
            "conviction_rule",
            "candidate_role",
            "core_identity",
            "sector_derivation_evidence",
            "anchor_reason",
            "sector_anchor",
            "limit_up_evidence_role",
        ):
            value = source.get(key)
            if isinstance(value, list):
                values.extend(clean_visible_text(item) for item in value)
            else:
                values.append(clean_visible_text(value))
    return " / ".join(part for part in values if part)


def _candidate_driver_tags(candidate):
    candidate = _as_dict(candidate)
    nested = _as_dict(candidate.get("anchor_reversal"))
    tags = []
    for source in (candidate, nested):
        for key in (
            "current_driver_tags",
            "driver_tags",
            "mainline_tags",
            "trade_narrative_tags",
            "concept_tags",
            "concepts",
        ):
            for item in _clean_list(source.get(key)):
                if item not in tags:
                    tags.append(item)
    return tags


_NON_DIRECTION_SECTOR_NAMES = {
    "-",
    "暂无",
    "待确认",
    "待补事实",
    "事实不足",
    "无确认主线",
    "暂无确认主线",
    "暂无明确主线",
    "主线待确认",
    "无确认主攻线",
    "暂无确认主攻线",
    "未形成跨日胜出方向",
    "当日资金未形成明确进攻方向",
    "候选方向",
    "当前方向",
    "混沌轮动",
    "多方向轮动",
}


def _sector_name(value):
    if isinstance(value, dict):
        value = (
            value.get("sector")
            or value.get("sector_name")
            or value.get("selected_direction")
            or value.get("direction")
            or value.get("name")
        )
    sector = clean_visible_text(value)
    return "" if sector in _NON_DIRECTION_SECTOR_NAMES else sector


_PROOF_WRITER = "selection_workflow.local_trend_sector_proof"
_INTERNAL_EXPANSION_RULE = "趋势数≥2且强势数≥2"


def _sector_canonical_index(*sources):
    """把行业原始名归到报告已经使用的标准板块名，避免同一方向用三套名字各算一遍。"""
    for source in sources:
        analysis = _as_dict(_as_dict(source).get("sector_ai_analysis"))
        mapping = _as_dict(analysis.get("mapping"))
        tree = _as_dict(analysis.get("sector_tree"))
        if not mapping and not tree:
            continue
        canonical = {}
        for name, target in mapping.items():
            name = clean_visible_text(name)
            target = clean_visible_text(target)
            if name and target:
                canonical[name] = target
        families = {}
        for name, target in canonical.items():
            families.setdefault(target, []).append(name)
        for theme, node in tree.items():
            theme = clean_visible_text(theme)
            if not theme:
                continue
            members = families.setdefault(theme, [])
            for member in _as_list(_as_dict(node).get("all_sectors")):
                member = clean_visible_text(member)
                if member and member not in members:
                    members.append(member)
        return {"canonical": canonical, "families": families}
    return {}


def _sector_canonical(name, sector_index=None):
    name = _sector_name(name)
    if not name:
        return ""
    return clean_visible_text(_as_dict(sector_index).get("canonical", {}).get(name)) or name


def _sector_names_match(left, right, sector_index=None):
    left = _sector_name(left)
    right = _sector_name(right)
    if not left or not right:
        return False
    if left == right or (len(left) >= 2 and len(right) >= 2 and (left in right or right in left)):
        return True
    sector_index = _as_dict(sector_index)
    if not sector_index:
        return False
    if _sector_canonical(left, sector_index) != _sector_canonical(right, sector_index):
        return False
    # 同一标准板块只承认"标准名与其成员行业"之间成立，不把两个成员行业互相等同。
    families = _as_dict(sector_index.get("families"))
    return right in (families.get(left) or []) or left in (families.get(right) or [])


def _is_own_proof_payload(value):
    value = _as_dict(value)
    if not value:
        return False
    if value.get("produced_by") == _PROOF_WRITER:
        return True
    return "evidence_gaps" in value and "direction" in value and "complete" in value


def _first_as_of_sector_value(candidates, target_date, *, target_day_only=False):
    target_date = _valid_trade_date(target_date)
    for value, source_date in candidates:
        sector = _sector_name(value)
        source_date = _valid_trade_date(source_date)
        if not sector or not source_date:
            continue
        if target_day_only:
            if source_date != target_date:
                continue
        elif target_date and source_date > target_date:
            continue
        return sector, source_date
    return "", ""


def _select_as_of_status_dates(
    sources,
    *,
    status_key,
    dates_key,
    target_date,
    status_aliases,
):
    target_date = _valid_trade_date(target_date)
    candidates = []
    excluded_future_dates = []
    for source in sources:
        source = _as_dict(source)
        raw_dates = [
            _valid_trade_date(value)
            for value in _as_list(source.get(dates_key))
        ]
        dates = sorted(
            {
                date
                for date in raw_dates
                if date and (not target_date or date <= target_date)
            }
        )
        excluded_future_dates.extend(
            date for date in raw_dates if date and target_date and date > target_date
        )
        raw_status = clean_text(source.get(status_key)).lower()
        status = status_aliases.get(raw_status, "unresolved")
        if dates or raw_status:
            candidates.append((status, dates))
    selected = next(
        (
            row
            for row in candidates
            if len(row[1]) >= 2 and row[0] != "unresolved"
        ),
        None,
    )
    if selected is None:
        selected = next((row for row in candidates if len(row[1]) >= 2), None)
    if selected is None:
        selected = next((row for row in candidates if row[1]), ("unresolved", []))
    status, dates = selected
    if len(dates) < 2:
        status = "unresolved"
    return status, dates, sorted(set(excluded_future_dates))


def _first_target_day_rotation_count(candidates, target_date):
    target_date = _valid_trade_date(target_date)
    for value, source_date in candidates:
        if value in (None, ""):
            continue
        number = _safe_float(value)
        source_date = _valid_trade_date(source_date)
        if (
            number is not None
            and number >= 0
            and number.is_integer()
            and source_date == target_date
        ):
            return int(number), source_date
    return None, ""


def _sector_trend_row(context, direction="", sector_index=None):
    rows = [item for item in _as_list(_as_dict(context).get("sector_trend_snapshot")) if isinstance(item, dict)]
    sector_index = _as_dict(sector_index)
    if direction:
        matched = [item for item in rows if _sector_names_match(item, direction, sector_index)]
        if len(matched) == 1:
            row = dict(matched[0])
            row["matched_sectors"] = [_sector_name(matched[0])]
            return row
        if matched:
            aggregate = {"sector": _sector_name(direction), "matched_sectors": [_sector_name(item) for item in matched]}
            for key in ("trend_count", "strong_count", "limit_up_count"):
                total = 0
                for item in matched:
                    value = _safe_float(item.get(key))
                    if value and value > 0:
                        total += value
                aggregate[key] = total
            return aggregate
    return rows[0] if len(rows) == 1 else {}


def _mainline_summary(*sources):
    for source in sources:
        source = _as_dict(source)
        summary = source.get("mainline_turnover_summary")
        if isinstance(summary, dict) and summary:
            return summary
    return {}


def _liquidity_allocation_facts(data, context, snapshot, *, target_date=""):
    normalized_target_date = _valid_trade_date(target_date)
    sources = (_as_dict(data), _as_dict(context), _as_dict(snapshot))

    def consistent_record_date(record):
        present_values = [
            record.get(key)
            for key in ("source_date", "trade_date", "date", "query_date")
            if record.get(key) not in (None, "")
        ]
        normalized_dates = [_valid_trade_date(value) for value in present_values]
        if (
            not normalized_dates
            or any(not date for date in normalized_dates)
            or len(set(normalized_dates)) != 1
        ):
            return ""
        return normalized_dates[0]

    current_values = set()
    breadth_values = set()
    history_by_date = {}
    for source in sources:
        current = _as_dict(source.get("current_sector_turnover_snapshot"))
        current_date = consistent_record_date(current)
        current_total = _safe_float(current.get("total_turnover"))
        if (
            current_date == normalized_target_date
            and current_total is not None
            and math.isfinite(current_total)
            and current_total > 0
        ):
            current_values.add(round(current_total, 2))

        market_stats = _as_dict(source.get("market_stats"))
        breadth_date = consistent_record_date(market_stats)
        up_count = _safe_float(market_stats.get("up_count"))
        down_count = _safe_float(market_stats.get("down_count"))
        if (
            breadth_date == normalized_target_date
            and up_count is not None
            and down_count is not None
            and up_count >= 0
            and down_count >= 0
            and up_count.is_integer()
            and down_count.is_integer()
            and up_count + down_count > 0
        ):
            breadth_values.add((int(up_count), int(down_count)))

        history_candidates = [(source.get("recent_sector_turnover_history"), 1)]
        summary = _as_dict(source.get("mainline_turnover_summary"))
        history_candidates.append((summary.get("recent_sector_turnover_history"), 1))
        top50_series = _as_dict(source.get("top50_turnover_share_series"))
        history_candidates.append((top50_series.get("rows"), 2))
        for rows, priority in history_candidates:
            for row in _as_list(rows):
                row = _as_dict(row)
                row_date = consistent_record_date(row)
                if not row_date or not normalized_target_date or row_date >= normalized_target_date:
                    continue
                total_turnover = _safe_float(
                    row.get("total_turnover")
                    if row.get("total_turnover") not in (None, "")
                    else row.get("market_amount_yi")
                )
                if (
                    total_turnover is not None
                    and math.isfinite(total_turnover)
                    and total_turnover > 0
                ):
                    history_by_date.setdefault(row_date, []).append(
                        (priority, total_turnover)
                    )

    current_total_turnover = next(iter(current_values)) if len(current_values) == 1 else None
    up_count = down_count = None
    if len(breadth_values) == 1:
        up_count, down_count = next(iter(breadth_values))
    previous_source_date = max(history_by_date) if history_by_date else ""
    previous_rows = history_by_date.get(previous_source_date, [])
    previous_total_turnover = None
    if previous_rows:
        highest_priority = max(priority for priority, _value in previous_rows)
        preferred_values = [
            value for priority, value in previous_rows if priority == highest_priority
        ]
        if len({round(value, 2) for value in preferred_values}) == 1:
            previous_total_turnover = max(
                preferred_values,
                key=lambda value: len(str(value).partition(".")[2].rstrip("0")),
            )
    return {
        "current_total_turnover": current_total_turnover,
        "current_turnover_source_date": (
            normalized_target_date if current_total_turnover is not None else ""
        ),
        "previous_total_turnover": previous_total_turnover,
        "previous_turnover_source_date": (
            previous_source_date if previous_total_turnover is not None else ""
        ),
        "up_count": up_count,
        "down_count": down_count,
        "market_breadth_source_date": (
            normalized_target_date if up_count is not None and down_count is not None else ""
        ),
    }


def _state_snapshot(*sources):
    for source in sources:
        source = _as_dict(source)
        for key in ("market_state_snapshot", "state_machine_snapshot", "state_machine"):
            snapshot = source.get(key)
            if isinstance(snapshot, dict) and snapshot:
                return snapshot
    return {}


def _market_participation_limit(
    data,
    context,
    snapshot,
    *,
    missing_fields=None,
    target_date="",
):
    sources = (_as_dict(context), _as_dict(snapshot), _as_dict(data))
    state = _state_snapshot(*sources)
    summary = _mainline_summary(*sources)
    attack = _as_dict(summary.get("mainline_attack_evidence_summary"))
    structure = _source_value(sources, "market_structure_judgement")
    structure = _as_dict(structure)
    market_state = clean_visible_text(
        _first_non_empty(
            state.get("market_state"),
            state.get("pulse_stage"),
            state.get("operation_state"),
            _as_dict(context.get("market_state_snapshot")).get("market_state"),
        ),
        "市场状态待确认",
    )
    execution_bias = clean_text(
        _first_non_empty(state.get("execution_bias"), context.get("execution_bias"), snapshot.get("execution_bias"))
    )
    pulse_stage = clean_visible_text(_first_non_empty(state.get("pulse_stage"), context.get("pulse_stage")))
    operation_state = clean_visible_text(_first_non_empty(state.get("operation_state"), context.get("operation_state")))
    attack_state = clean_text(attack.get("attack_state"))
    tomorrow_rhythm = clean_visible_text(structure.get("tomorrow_rhythm"))
    systemic_text = " / ".join(
        part
        for part in (
            market_state,
            pulse_stage,
            operation_state,
            execution_bias,
            tomorrow_rhythm,
            clean_visible_text(_source_value(sources, "systemic_risk", "systemic_risk_level")),
        )
        if part
    )
    explicit_systemic = _explicit_bool(_source_value(sources, "systemic_risk_active", "systemic_risk_confirmed"))
    systemic_risk = explicit_systemic is True or _text_has_any(
        systemic_text,
        ("踩踏", "恐慌", "系统性风险", "风险释放未止", "市场同步走弱"),
    )
    explicit_broad_confirmation = _explicit_bool(
        _source_value(
            sources,
            "broad_market_confirmation",
            "market_trend_confirmed",
            "profit_effect_broad_confirmed",
        )
    )
    broad_confirmation = bool(
        not systemic_risk
        and (
            explicit_broad_confirmation is True
            or (
                explicit_broad_confirmation is not False
                and attack_state == "confirmed_attack"
                and execution_bias not in {"avoid", "defense", "watch_only"}
                and pulse_stage not in {"退潮", "踩踏", "恐慌"}
                and operation_state != "撤退态"
            )
        )
    )
    weak_market = bool(
        execution_bias in {"avoid", "defense", "watch_only"}
        or pulse_stage in {"退潮", "冰点", "高位分歧"}
        or operation_state in {"撤退态", "观察态"}
        or attack_state in {"candidate_attack", "chaotic_rotation", "no_attack"}
        or tomorrow_rhythm in {"低频聚焦", "观察聚焦"}
        or _text_has_any(market_state, ("收缩", "防守", "退潮", "撤退", "混沌", "偏弱"))
    )
    facts_incomplete = bool(missing_fields)
    if facts_incomplete:
        max_position_pct = 0
        reason = "关键事实不完整，不取得新参与资格"
        risk = "先补齐市场、板块和执行事实"
    elif systemic_risk:
        max_position_pct = 0
        reason = "系统性风险仍在释放，局部强势不用于扩大参与"
        risk = "单股或单板块不能反向证明市场风险已经解除"
    elif broad_confirmation:
        max_position_pct = 100
        reason = "市场趋势和赚钱效应已形成更广泛确认"
        risk = "B2仍只在个股价格与账户条件确认后执行"
    else:
        max_position_pct = 50
        reason = "市场未形成广泛确认，完整局部趋势最多取得B1参与权"
        risk = "没有局部趋势完整证明时仍回到0%不参与"
    return {
        "source_date": _valid_trade_date(target_date) or None,
        "max_position_pct": max_position_pct,
        "market_state": market_state,
        "attack_state": attack_state or "待确认",
        "weak_market": weak_market,
        "broad_market_confirmation": broad_confirmation,
        "systemic_risk": systemic_risk,
        "facts_complete": not facts_incomplete,
        "b2_allowed": max_position_pct == 100,
        "reason": reason,
        "risk": risk,
    }


def _local_trend_sector_proof(data, context, snapshot, *, target_date="", sector_index=None):
    sources = (_as_dict(context), _as_dict(snapshot), _as_dict(data))
    supplied = _as_dict(_source_value(sources, "local_trend_sector_proof"))
    # 旧快照会把上一轮的证明原样带回来；读回来当外部证据会把自己上一轮的结论锁死。
    if _is_own_proof_payload(supplied):
        supplied = {}
    sector_index = _as_dict(sector_index) or _sector_canonical_index(data, context, snapshot)
    source_date = _sector_source_date(data, context, snapshot, supplied)
    normalized_target_date = _valid_trade_date(target_date)
    source_date = _valid_trade_date(source_date)
    source_date_matches_target = bool(
        normalized_target_date
        and source_date
        and source_date == normalized_target_date
    )
    summary = _mainline_summary(*sources)
    double_mainline = _as_dict(summary.get("double_mainline_summary"))
    attack = _as_dict(summary.get("mainline_attack_evidence_summary"))
    overtake = _as_dict(summary.get("overtake_window_summary"))
    supplied_direction_source_date = _first_non_empty(
        supplied.get("direction_source_date"),
        supplied.get("source_date"),
        supplied.get("sector_source_date"),
        _nested_source_date(supplied, "sector_source_date"),
    )
    summary_source_date = _first_non_empty(
        summary.get("source_date"),
        summary.get("trade_date"),
        summary.get("date"),
    )
    attack_source_date = _first_non_empty(
        attack.get("source_date"),
        attack.get("trade_date"),
        attack.get("date"),
        summary_source_date,
    )
    context_direction_source_date = _first_non_empty(
        context.get("mainline_name_source_date"),
        context.get("sector_source_date"),
        _nested_source_date(context, "sector_source_date"),
        context.get("trade_date"),
        context.get("source_date"),
        context.get("date"),
    )
    direction, direction_source_date = _first_as_of_sector_value(
        (
            (supplied.get("direction"), supplied_direction_source_date),
            (supplied.get("selected_direction"), supplied_direction_source_date),
            (attack.get("primary_line"), attack_source_date),
            (summary.get("current_mainline"), summary_source_date),
            (context.get("mainline_name"), context_direction_source_date),
        ),
        normalized_target_date,
    )
    trend_row = _sector_trend_row(context, direction, sector_index)
    current_record = _as_dict(_source_value(sources, "current_mainline_history_record"))
    recent_history = _source_value(sources, "recent_mainline_history")
    recent_history = [item for item in _as_list(recent_history) if isinstance(item, dict)]
    supplied_continuity_dates = _as_list(
        supplied.get("continuity_dates")
        or supplied.get("cross_day_dates")
        or supplied.get("trade_dates")
    )
    direction_history_dates = []
    for item in recent_history + ([current_record] if current_record else []):
        if not any(
            _sector_names_match(item.get(key), direction, sector_index)
            for key in ("primary_mainline", "leading_line", "mainline", "sector_name", "daily_attack_line")
        ):
            continue
        row_date = _valid_trade_date(
            item.get("date") or item.get("trade_date") or item.get("source_date")
        )
        if row_date:
            direction_history_dates.append(row_date)
    all_continuity_dates = [
        date
        for date in (
            _valid_trade_date(value)
            for value in supplied_continuity_dates + direction_history_dates
        )
        if date and (not normalized_target_date or date <= normalized_target_date)
    ]
    continuity_dates = sorted(set(all_continuity_dates))
    excluded_future_continuity_dates = sorted(
        {
            date
            for date in (
                _valid_trade_date(value)
                for value in supplied_continuity_dates + direction_history_dates
            )
            if date and normalized_target_date and date > normalized_target_date
        }
    )
    supplied_stage_mainline = _as_dict(supplied.get("stage_mainline_evidence"))
    supplied_stage_mainline_directions = [
        deepcopy(item)
        for item in _as_list(
            supplied_stage_mainline.get("directions")
            or supplied.get("stage_mainline_directions")
        )
        if isinstance(item, dict)
    ]
    supplied_cross_day_competition = _as_dict(
        supplied.get("cross_day_competition")
        or supplied_stage_mainline.get("cross_day_competition")
    )
    cycle_mainline, cycle_mainline_source_date = _first_as_of_sector_value(
        (
            (
                supplied_stage_mainline.get("cycle_mainline"),
                supplied_stage_mainline.get("cycle_mainline_source_date"),
            ),
            (
                double_mainline.get("cycle_mainline"),
                _first_non_empty(
                    double_mainline.get("cycle_mainline_source_date"),
                    double_mainline.get("source_date"),
                    summary_source_date,
                ),
            ),
        ),
        normalized_target_date,
    )
    daily_attack_line, daily_attack_line_source_date = _first_as_of_sector_value(
        (
            (
                supplied_stage_mainline.get("daily_attack_line"),
                supplied_stage_mainline.get("daily_attack_line_source_date"),
            ),
            (
                double_mainline.get("daily_attack_line"),
                _first_non_empty(
                    double_mainline.get("daily_attack_line_source_date"),
                    double_mainline.get("source_date"),
                    summary_source_date,
                ),
            ),
        ),
        normalized_target_date,
        target_day_only=True,
    )
    observed_candidate_directions = []
    if attack_source_date == normalized_target_date:
        for value in _as_list(attack.get("candidate_lines")):
            candidate_direction = _sector_name(value)
            if candidate_direction and candidate_direction not in observed_candidate_directions:
                observed_candidate_directions.append(candidate_direction)
    phase_rotation_status, phase_rotation_dates, excluded_future_phase_rotation_dates = (
        _select_as_of_status_dates(
            (supplied_stage_mainline, supplied),
            status_key="phase_rotation_status",
            dates_key="phase_rotation_dates",
            target_date=normalized_target_date,
            status_aliases={
                "1": "confirmed",
                "true": "confirmed",
                "yes": "confirmed",
                "confirmed": "confirmed",
                "完整": "confirmed",
                "成立": "confirmed",
                "已确认": "confirmed",
                "0": "failed",
                "false": "failed",
                "no": "failed",
                "failed": "failed",
                "不足": "failed",
                "缺失": "failed",
                "未确认": "failed",
                "不成立": "failed",
                "unresolved": "unresolved",
            },
        )
    )
    (
        sector_index_slope_status,
        sector_index_slope_dates,
        excluded_future_sector_index_slope_dates,
    ) = _select_as_of_status_dates(
        (supplied_stage_mainline, supplied),
        status_key="sector_index_slope_status",
        dates_key="sector_index_slope_dates",
        target_date=normalized_target_date,
        status_aliases={
            "upward": "upward",
            "flat": "flat",
            "downward": "downward",
            "unresolved": "unresolved",
            "向上": "upward",
            "上行": "upward",
            "持平": "flat",
            "无明显斜率": "flat",
            "向下": "downward",
            "下行": "downward",
        },
    )
    sector_index_slope_evidence = []
    for source in (supplied_stage_mainline, supplied):
        for row in _dated_evidence_items(
            source.get("sector_index_slope_evidence"),
            normalized_target_date,
        ):
            if row not in sector_index_slope_evidence:
                sector_index_slope_evidence.append(row)
    if len(sector_index_slope_dates) < 2:
        sector_index_slope_evidence = []
    intraday_rotation_count, intraday_rotation_source_date = (
        _first_target_day_rotation_count(
            (
                (
                    supplied_stage_mainline.get("intraday_rotation_count"),
                    supplied_stage_mainline.get(
                        "intraday_rotation_source_date"
                    ),
                ),
                (
                    supplied.get("intraday_rotation_count"),
                    supplied.get("intraday_rotation_source_date"),
                ),
            ),
            normalized_target_date,
        )
    )
    explicit_cross_day = _explicit_bool(
        _first_non_empty(
            supplied.get("cross_day_continuity"),
            supplied.get("cross_day_continuous"),
            supplied.get("continuity_confirmed"),
        )
    )
    cross_day_continuity = bool(
        explicit_cross_day is not False
        and len(continuity_dates) >= 2
    )
    cross_day_continuity_status = (
        "confirmed"
        if cross_day_continuity
        else "failed"
        if explicit_cross_day is False
        else "unresolved"
    )
    explicit_divergence = _explicit_bool(
        _first_non_empty(
            supplied.get("divergence_acceptance"),
            supplied.get("divergence_accepted"),
            supplied.get("acceptance_confirmed"),
        )
    )
    acceptance_text = clean_visible_text(
        _first_non_empty(
            supplied.get("divergence_acceptance_text"),
            supplied.get("acceptance_quality"),
            context.get("backrow_acceptance"),
            context.get("后排承接"),
            _state_snapshot(*sources).get("acceptance_quality"),
            overtake.get("own_stability"),
        )
    )
    divergence_acceptance = (
        explicit_divergence
        if explicit_divergence is not None
        else bool(acceptance_text and _text_has_any(acceptance_text, ("强承接", "分歧承接", "承接稳定", "没有塌", "仍承接")))
    )
    divergence_acceptance_status = (
        "confirmed"
        if divergence_acceptance
        else "failed"
        if explicit_divergence is False
        else "unresolved"
    )
    explicit_expansion = _explicit_bool(
        _first_non_empty(
            supplied.get("internal_expansion"),
            supplied.get("sector_internal_expansion"),
            supplied.get("breadth_expansion"),
        )
    )
    trend_count = int(_safe_float(trend_row.get("trend_count")) or 0)
    strong_count = int(_safe_float(trend_row.get("strong_count")) or 0)
    expansion_text = clean_visible_text(
        _first_non_empty(
            supplied.get("internal_expansion_text"),
            context.get("sector_turnover_expansion"),
            context.get("板块成交扩散"),
        )
    )
    internal_expansion = (
        explicit_expansion
        if explicit_expansion is not None
        else bool(trend_count >= 2 and strong_count >= 2)
        or _text_has_any(expansion_text, ("扩散", "抬升", "同步", "成群"))
    )
    internal_expansion_status = (
        "confirmed"
        if internal_expansion
        else "failed"
        if explicit_expansion is False
        else "unresolved"
    )
    explicit_competition = _explicit_bool(
        _first_non_empty(
            supplied.get("competition_comparison"),
            supplied.get("competition_line_compared"),
            supplied.get("rival_comparison_complete"),
        )
    )
    competition_state = clean_visible_text(
        _first_non_empty(
            supplied.get("competition_state"),
            supplied.get("competition_line_state"),
            overtake.get("window_state"),
            attack.get("relationship_hint"),
        )
    )
    competition_comparison = (
        explicit_competition
        if explicit_competition is not None
        else competition_state in {"open", "confirm_next", "单主线聚焦", "双主线竞争"}
    )
    competition_comparison_status = (
        "confirmed"
        if competition_comparison
        else "failed"
        if explicit_competition is False
        else "unresolved"
    )
    evidence_gaps = []
    if not direction:
        evidence_gaps.append("资金选择方向")
    if not cross_day_continuity:
        evidence_gaps.append("跨日持续")
    if not divergence_acceptance:
        evidence_gaps.append("分歧承接")
    if not internal_expansion:
        evidence_gaps.append("内部扩散")
    if not competition_comparison:
        evidence_gaps.append("竞争方向对照")
    if not source_date:
        evidence_gaps.append("板块事实日期缺失")
    elif not source_date_matches_target:
        evidence_gaps.append("板块事实日期不属于目标日")
    return {
        "direction": direction,
        "direction_source_date": direction_source_date or None,
        "complete": not evidence_gaps,
        "source_date": source_date or None,
        "source_date_matches_target": source_date_matches_target,
        "continuity_dates": continuity_dates,
        "excluded_future_continuity_dates": excluded_future_continuity_dates,
        "cross_day_continuity": bool(cross_day_continuity),
        "cross_day_continuity_status": cross_day_continuity_status,
        "divergence_acceptance": bool(divergence_acceptance),
        "divergence_acceptance_status": divergence_acceptance_status,
        "internal_expansion": bool(internal_expansion),
        "internal_expansion_status": internal_expansion_status,
        "competition_comparison": bool(competition_comparison),
        "competition_comparison_status": competition_comparison_status,
        "competition_state": competition_state or "待确认",
        "first_active_divergence": _explicit_bool(
            supplied.get("first_active_divergence")
        ),
        "capital_return_status": clean_text(
            supplied.get("capital_return_status")
        ) or "unresolved",
        "consensus_status": clean_text(
            supplied.get("consensus_status")
        ) or "unresolved",
        "story_spread_status": clean_text(
            supplied.get("story_spread_status")
        ) or "unresolved",
        "trend_continuation_status": clean_text(
            supplied.get("trend_continuation_status")
        ) or "unresolved",
        "leader_structure_status": clean_text(
            supplied.get("leader_structure_status")
        ) or "unresolved",
        "stage_mainline_evidence": {
            "directions": supplied_stage_mainline_directions,
            "candidate_directions": observed_candidate_directions,
            "candidate_direction_source_date": (
                attack_source_date if observed_candidate_directions else None
            ),
            "candidate_direction_evidence": (
                [clean_visible_text(attack.get("confirmation_evidence"))]
                if observed_candidate_directions
                and clean_visible_text(attack.get("confirmation_evidence"))
                else []
            ),
            "cycle_mainline": cycle_mainline,
            "cycle_mainline_source_date": cycle_mainline_source_date or None,
            "daily_attack_line": daily_attack_line,
            "daily_attack_line_source_date": daily_attack_line_source_date or None,
            "phase_rotation_status": phase_rotation_status,
            "phase_rotation_dates": phase_rotation_dates,
            "sector_index_slope_status": sector_index_slope_status,
            "sector_index_slope_dates": sector_index_slope_dates,
            "sector_index_slope_evidence": sector_index_slope_evidence,
            "intraday_rotation_count": intraday_rotation_count,
            "intraday_rotation_source_date": intraday_rotation_source_date or None,
            "excluded_future_phase_rotation_dates": excluded_future_phase_rotation_dates,
            "excluded_future_sector_index_slope_dates": excluded_future_sector_index_slope_dates,
        },
        "cross_day_competition": deepcopy(supplied_cross_day_competition),
        "trend_count": trend_count,
        "strong_count": strong_count,
        "matching_candidates": [],
        "evidence_gaps": evidence_gaps,
        "produced_by": _PROOF_WRITER,
        "observed": {
            "direction": direction or None,
            "sector_rows": list(trend_row.get("matched_sectors") or []),
            "trend_count": trend_count,
            "strong_count": strong_count,
            "internal_expansion_rule": _INTERNAL_EXPANSION_RULE,
            "acceptance_text": clean_visible_text(acceptance_text) or None,
            "expansion_text": clean_visible_text(expansion_text) or None,
            "competition_text": competition_state or None,
        },
    }


def refresh_sector_tournament_three_axis_for_display(
    *,
    target_date="",
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    selection_workflow=None,
):
    data = _as_dict(data)
    context = dict(_as_dict(execution_stage_context))
    snapshot = _as_dict(market_research_snapshot)
    workflow = _as_dict(selection_workflow)
    target_date = clean_text(
        target_date
        or workflow.get("target_date")
        or data.get("target_date")
        or snapshot.get("target_date")
    )
    if not _valid_trade_date(target_date):
        return {}

    proof = _local_trend_sector_proof(
        data,
        context,
        snapshot,
        target_date=target_date,
    )
    sector_index = _sector_canonical_index(data, context, snapshot)
    candidate_pool = _as_list(workflow.get("candidate_pool"))
    stage = build_sector_diffusion_stage_evidence(
        target_date=target_date,
        local_trend_sector_proof=proof,
        price_acceptance_rows=_sector_diffusion_price_acceptance_rows(
            candidate_pool,
            target_date=target_date,
            direction=proof.get("direction"),
            sector_index=sector_index,
        ),
        source_refs=[
            "selection_workflow.candidate_pool",
            "selection_workflow.local_trend_sector_proof",
        ],
    )
    market_limit = _as_dict(workflow.get("market_participation_limit"))
    if not market_limit:
        market_limit = _market_participation_limit(
            data,
            context,
            snapshot,
            target_date=target_date,
        )
    liquidity_facts = _liquidity_allocation_facts(
        data,
        context,
        snapshot,
        target_date=target_date,
    )
    return build_sector_tournament_three_axis(
        target_date=target_date,
        sector_diffusion_stage_evidence=stage,
        local_trend_sector_proof=proof,
        market_participation_limit=market_limit,
        liquidity_allocation_facts=liquidity_facts,
        source_refs=[
            "selection_workflow.market_participation_limit",
            "selection_workflow.local_trend_sector_proof",
            "selection_workflow.sector_diffusion_stage_evidence",
            "selection_workflow.market_stats",
            "selection_workflow.current_sector_turnover_snapshot",
            "selection_workflow.recent_sector_turnover_history",
        ],
    )


def _candidate_matches_local_trend_proof(candidate, proof, sector_index=None):
    proof = _as_dict(proof)
    if not proof.get("complete"):
        return False
    direction = _sector_name(proof.get("direction"))
    candidate = _as_dict(candidate)
    candidate_directions = [
        _sector_name(candidate.get(key))
        for key in ("sector", "sector_name", "mainline", "trade_narrative_sector")
        if _sector_name(candidate.get(key))
    ]
    candidate_directions.extend(_candidate_driver_tags(candidate))
    return bool(
        direction
        and any(_sector_names_match(item, direction, sector_index) for item in candidate_directions)
    )


def _candidate_has_market_emotion_derivation(candidate, context):
    candidate = _as_dict(candidate)
    proof = _as_dict(_as_dict(context).get("market_emotion_line_proof"))
    if _explicit_bool(proof.get("complete")) is not True:
        return False
    required = (
        "scarcity_recognition",
        "capacity_evidence",
        "public_participation",
        "divergence_acceptance",
    )
    if not all(_explicit_bool(proof.get(key)) is True for key in required):
        return False
    proof_leader = proof.get("leader") if isinstance(proof.get("leader"), dict) else {}
    return bool(stock_key(proof_leader) and stock_key(proof_leader) == stock_key(candidate))


def _candidate_has_legacy_signal(candidate):
    return _text_has_any(_candidate_text_blob(candidate), LEGACY_SIGNAL_MARKERS)


def _candidate_has_sector_derivation(
    source_key, candidate, context, local_trend_sector_proof=None, sector_index=None
):
    candidate = _as_dict(candidate)
    proof = _as_dict(local_trend_sector_proof) or _as_dict(_as_dict(context).get("local_trend_sector_proof"))
    # 板块证明成立时，候选只要属于该方向（含其成员行业）就算板块推导来源；
    # 个股是否真能成为执行对象仍由板块角色、执行证据和价格承接单独判定。
    return _candidate_matches_local_trend_proof(candidate, proof, sector_index)


def _candidate_origin(source_key, candidate, context, local_trend_sector_proof=None, sector_index=None):
    if clean_text(source_key) == "selected_position_candidate":
        return "manual_observation"
    if "market_emotion_candidates" in clean_text(source_key) and _candidate_has_market_emotion_derivation(candidate, context):
        return "market_emotion_line"
    if _candidate_has_sector_derivation(
        source_key, candidate, context, local_trend_sector_proof, sector_index
    ):
        return "sector_first"
    return "legacy_signal_only"


def _candidate_entry_basis(
    source_key, candidate, context, local_trend_sector_proof=None, sector_index=None
):
    origin = _candidate_origin(source_key, candidate, context, local_trend_sector_proof, sector_index)
    if origin == "sector_first":
        return clean_visible_text(
            candidate.get("sector_derivation_evidence")
            or candidate.get("anchor_reason")
            or candidate.get("entered_reason")
            or "来自市场氛围、板块发酵和板块角色推导"
        )
    if origin == "market_emotion_line":
        return clean_visible_text(
            candidate.get("market_emotion_evidence")
            or candidate.get("entered_reason")
            or "来自市场情绪线，不来自单只涨停形态"
        )
    if origin == "manual_observation":
        return "手动或持仓对象只进入风险处理/观察链路，不能绕过板块推导取得新仓入口"
    legacy_text = "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口"
    if _candidate_has_legacy_signal(candidate):
        return legacy_text
    return "未证明来自板块发酵和市场选择，不能作为新仓入口"


def _candidate_new_entry_qualified(
    source_key, candidate, context, local_trend_sector_proof=None, sector_index=None
):
    if _candidate_blocks_new_entry_by_price(candidate):
        return False
    target_date = _normalize_quote_date(_as_dict(context).get("_selection_target_date"))
    candidate_dates = _mapping_dates(
        candidate,
        "trade_date",
        "source_date",
        "target_date",
        "date",
    )
    if target_date and candidate_dates and target_date not in candidate_dates:
        return False
    return _candidate_origin(
        source_key, candidate, context, local_trend_sector_proof, sector_index
    ) in {"sector_first", "market_emotion_line"}


def _build_candidate_pool(
    execution_stage_context,
    final_stock,
    selected_position_candidate=None,
    quote_lookup=None,
    local_trend_sector_proof=None,
    sector_index=None,
):
    context = _as_dict(execution_stage_context)
    final_key = stock_key(final_stock)
    pool = []
    seen = set()
    for source_key, raw_candidate in _candidate_source_rows(context, selected_position_candidate):
        candidate = _candidate_with_quote(raw_candidate, quote_lookup)
        key = stock_key(candidate)
        if not key or key in seen:
            continue
        seen.add(key)
        candidate_origin = _candidate_origin(
            source_key, candidate, context, local_trend_sector_proof, sector_index
        )
        new_entry_qualified = _candidate_new_entry_qualified(
            source_key, candidate, context, local_trend_sector_proof, sector_index
        )
        local_trend_sector_match = _candidate_matches_local_trend_proof(
            candidate, local_trend_sector_proof, sector_index
        )
        status = _candidate_status(candidate, final_key)
        eliminated_at = "N6" if status in {"降级观察", "不参与"} else ""
        brooks = _brooks_price_action_judge(candidate)
        price_block_reason = _candidate_blocks_new_entry_by_price(candidate)
        limit_down_reversal_plan = _candidate_limit_down_reversal_plan_payload(candidate)
        limit_down_block_reason = _candidate_limit_down_block_reason(candidate)
        if price_block_reason:
            status = "风险复核样本"
            eliminated_at = "N7"
        elif status == "最终执行对象":
            eliminated_at = ""
        eliminated_reason = "" if status == "最终执行对象" else clean_text(
            (
                price_block_reason
                + "；如要参与必须写成跌停反包专项，并给出确认窗口、作废线和回到0%的条件"
                if price_block_reason and limit_down_block_reason
                else price_block_reason
                if price_block_reason
                else ""
            )
            or
            candidate.get("anchor_reversal_reason")
            or candidate.get("why_not_anchor")
            or candidate.get("conviction_rule")
            or brooks.get("participation_effect")
            or status
        )
        source_pools = list(candidate.get("source_pools") or [source_key])
        explicit_selected = bool(
            source_key == "selected_position_candidate"
            or "运行时观察对象" in source_pools
            or _candidate_matches_selected(candidate, selected_position_candidate)
        )
        front_observation_qualified, front_observation_reason = _candidate_can_be_front_observation_object(
            candidate,
            explicit_selected=explicit_selected,
        )
        observation_layer = "front_observation" if front_observation_qualified else "process_observation"
        stale_final_reason = any(
            marker in clean_visible_text(front_observation_reason)
            for marker in ("已归入明日执行结论", "B1/B2执行计划")
        )
        if status != "最终执行对象" and stale_final_reason:
            front_observation_qualified = False
            front_observation_reason = eliminated_reason or brooks.get("participation_effect") or "仅作过程候选"
            observation_layer = "process_observation"
        if price_block_reason:
            front_observation_qualified = False
            front_observation_reason = (
                f"价格否定优先：{price_block_reason}；只保留过程回放，不进入明日执行结论"
            )
            observation_layer = "process_observation"
        if status == "最终执行对象":
            front_observation_qualified = False
            front_observation_reason = "已归入明日执行结论，后续只按B1/B2执行计划展示"
            observation_layer = "execution_object"
        pool.append(
            {
                "stock": stock_payload(candidate),
                "first_seen_node": "N5",
                "source_pools": source_pools,
                "entered_reason": _entered_reason(source_key, candidate),
                "entry_basis": _candidate_entry_basis(
                    source_key, candidate, context, local_trend_sector_proof, sector_index
                ),
                "candidate_origin": candidate_origin,
                "new_entry_qualified": new_entry_qualified,
                "local_trend_sector_match": local_trend_sector_match,
                "proven_direction": _sector_name(_as_dict(local_trend_sector_proof).get("direction")),
                "price_source_date": next(
                    (
                        date
                        for date in (
                            _mapping_dates(
                                candidate,
                                "trade_date",
                                "source_date",
                                "target_date",
                                "date",
                            )
                            + _mapping_dates(
                                _as_dict(candidate.get("same_day_quote")),
                                "trade_date",
                                "source_date",
                                "target_date",
                                "date",
                            )
                        )
                        if date == _valid_trade_date(context.get("_selection_target_date"))
                    ),
                    None,
                ),
                "mainline": clean_visible_text(candidate.get("mainline") or context.get("mainline_name")),
                "sector": clean_visible_text(candidate.get("sector") or candidate.get("sector_name")),
                "current_driver_tags": _candidate_driver_tags(candidate),
                "sector_role": clean_visible_text(candidate.get("candidate_role") or candidate.get("core_identity")),
                "reversal_decision": _anchor_reversal_decision(candidate),
                "leader_debate": _leader_debate(candidate),
                "brooks_price_action_judge": brooks,
                "limit_down_reversal_plan": limit_down_reversal_plan,
                "common_selection_consistency": _common_selection_consistency(candidate),
                "status": status,
                "price_action_block_reason": price_block_reason,
                "front_observation_qualified": front_observation_qualified,
                "front_observation_reason": clean_visible_text(front_observation_reason),
                "observation_layer": observation_layer,
                "current_reason": clean_visible_text(candidate.get("conviction_rule") or candidate.get("anchor_reversal_reason")),
                "eliminated_at": eliminated_at,
                "eliminated_reason": eliminated_reason,
                "compared_against": [],
                "workflow_path": ["N5", "N6", "N7", "N8"],
            }
        )
    return pool


def _candidate_matches_selected(candidate, selected_position_candidate):
    candidate_payload = stock_payload(candidate)
    selected_payload = stock_payload(selected_position_candidate)
    selected_code = clean_text(selected_payload.get("code"))
    candidate_code = clean_text(candidate_payload.get("code"))
    selected_name = clean_visible_text(selected_payload.get("name"))
    candidate_name = clean_visible_text(candidate_payload.get("name"))
    if selected_code:
        if candidate_code:
            return candidate_code == selected_code
        return bool(selected_name and candidate_name and candidate_name == selected_name)
    return bool(selected_name and candidate_name and candidate_name == selected_name)


def _selected_candidate_has_execution_evidence(candidate):
    candidate = _as_dict(candidate)
    if not candidate:
        return False
    if bool(candidate.get("primary_buy_candidate")):
        return True
    role = clean_text(candidate.get("sniper_role") or candidate.get("candidate_role") or candidate.get("target_role"))
    if role in {"明日主买对象", "板块锚", "core", "主线核心"}:
        return True
    has_window = bool(
        clean_text(candidate.get("participation_window") or candidate.get("buy_window") or candidate.get("execution_window"))
    )
    planned = candidate.get("planned_participation") if isinstance(candidate.get("planned_participation"), dict) else {}
    if planned:
        has_window = has_window or bool(clean_text(planned.get("buy_window") or planned.get("participation_window")))
    return has_window and bool(clean_text(candidate.get("fallback_state") or planned.get("fallback_state")))


def _candidate_can_be_final_execution_object(
    candidate,
    *,
    source_key="",
    context=None,
    local_trend_sector_proof=None,
    sector_index=None,
):
    if not _as_dict(local_trend_sector_proof).get("complete"):
        return False
    if _candidate_blocks_new_entry_by_price(candidate):
        return False
    return (
        _anchor_reversal_decision(candidate) == "可作为主对象"
        and _selected_candidate_has_execution_evidence(candidate)
        and _candidate_new_entry_qualified(
            source_key,
            candidate,
            _as_dict(context),
            local_trend_sector_proof,
            sector_index,
        )
    )


def _candidate_has_target_day_price_acceptance(candidate, context):
    target_date = _valid_trade_date(_as_dict(context).get("_selection_target_date"))
    if not target_date:
        return False
    candidate = _as_dict(candidate)
    candidate_dates = _mapping_dates(
        candidate,
        "trade_date",
        "source_date",
        "target_date",
        "date",
    )
    candidate_dates.extend(
        _mapping_dates(
            _as_dict(candidate.get("same_day_quote")),
            "trade_date",
            "source_date",
            "target_date",
            "date",
        )
    )
    return bool(
        target_date in set(candidate_dates)
        and _brooks_price_action_judge(candidate).get("status") == "accepted"
    )


def _candidate_can_be_front_observation_object(candidate, *, explicit_selected=False):
    candidate = _as_dict(candidate)
    if not candidate:
        return False, "无候选身份"
    decision = _anchor_reversal_decision(candidate)
    nested = _as_dict(candidate.get("anchor_reversal"))
    role = clean_visible_text(
        candidate.get("candidate_role")
        or candidate.get("quality_role")
        or candidate.get("sniper_role")
        or nested.get("candidate_role")
        or candidate.get("core_identity")
    )
    layer = clean_visible_text(candidate.get("candidate_layer") or nested.get("candidate_layer"))
    eligibility = clean_visible_text(candidate.get("execution_eligibility") or nested.get("execution_eligibility"))
    reason_text = clean_visible_text(
        candidate.get("why_not_anchor")
        or candidate.get("anchor_reversal_reason")
        or nested.get("why_not_anchor")
        or nested.get("anchor_reversal_reason")
    )
    entered_reason = clean_visible_text(
        candidate.get("entered_reason")
        or candidate.get("conviction_rule")
        or candidate.get("conviction_reason")
        or candidate.get("reason")
    )
    combined = " / ".join(part for part in (role, layer, eligibility, reason_text, entered_reason) if part)
    hard_blocked_roles = {"观察样本", "跟风样本", "过程候选", "低位补涨", "套利工具", "候选观察补充"}
    hard_blocked_reason = ""
    if role in hard_blocked_roles or layer == "watch_sample":
        hard_blocked_reason = reason_text or "仅过程观察样本"
    observation_layer = clean_visible_text(candidate.get("observation_layer") or nested.get("observation_layer"))
    if observation_layer == "process_observation":
        hard_blocked_reason = reason_text or "上游已限定为过程观察"
    if "本板块锚未识别" in combined or "不能说明为什么不做本板块锚" in combined:
        hard_blocked_reason = reason_text or "板块锚未识别，只能作为过程观察样本"
    if hard_blocked_reason:
        return False, hard_blocked_reason
    if candidate.get("front_observation_qualified") is True:
        return True, clean_visible_text(
            candidate.get("front_observation_reason")
            or "上游明确保留前台观察"
        )
    if candidate.get("front_observation_qualified") is False:
        return False, clean_visible_text(
            candidate.get("front_observation_reason")
            or "上游明确限定为过程观察"
        )
    if explicit_selected and role in {"观察对象", "候选观察"} and layer == "front_observation":
        return True, reason_text or "运行时明确解析为前台观察对象"
    return False, reason_text or "未取得前台观察资格"


def _pick_final_candidate(
    execution_stage_context,
    selected_position_candidate=None,
    position_decision=None,
    quote_lookup=None,
    local_trend_sector_proof=None,
    formal_candidate_selection=None,
    sector_index=None,
):
    if _position_pct(position_decision) <= 0:
        return {}
    context = _as_dict(execution_stage_context)
    sources = _candidate_sources(context)
    formal_selection = _as_dict(formal_candidate_selection)
    if formal_selection:
        if formal_selection.get("status") not in {"clear_winner", "single_qualified"}:
            return {}
        winner = _as_dict(formal_selection.get("winner"))
        if not stock_key(winner):
            return {}
        for source_key, candidate in sources:
            if not _candidate_matches_selected(candidate, winner):
                continue
            candidate = _candidate_with_quote(candidate, quote_lookup)
            if _candidate_can_be_final_execution_object(
                candidate,
                source_key=source_key,
                context=context,
                local_trend_sector_proof=local_trend_sector_proof,
                sector_index=sector_index,
            ) and _candidate_has_target_day_price_acceptance(candidate, context):
                return stock_payload(candidate)
        return {}
    if stock_key(selected_position_candidate):
        selected_in_pool = False
        for source_key, candidate in sources:
            if _candidate_matches_selected(candidate, selected_position_candidate):
                selected_in_pool = True
                merged = dict(candidate)
                merged.update(
                    {
                        key: value
                        for key, value in _as_dict(selected_position_candidate).items()
                        if value not in (None, "")
                    }
                )
                merged = _candidate_with_quote(merged, quote_lookup)
                if _candidate_can_be_final_execution_object(
                    merged,
                    source_key=source_key,
                    context=context,
                    local_trend_sector_proof=local_trend_sector_proof,
                    sector_index=sector_index,
                ):
                    return stock_payload(merged)
        if not selected_in_pool:
            return {}
        for source_key, candidate in sources:
            if _candidate_matches_selected(candidate, selected_position_candidate):
                continue
            candidate = _candidate_with_quote(candidate, quote_lookup)
            if _candidate_can_be_final_execution_object(
                candidate,
                source_key=source_key,
                context=context,
                local_trend_sector_proof=local_trend_sector_proof,
                sector_index=sector_index,
            ):
                return stock_payload(candidate)
        return {}
    for source_key, candidate in sources:
        candidate = _candidate_with_quote(candidate, quote_lookup)
        if _candidate_can_be_final_execution_object(
            candidate,
            source_key=source_key,
            context=context,
            local_trend_sector_proof=local_trend_sector_proof,
            sector_index=sector_index,
        ):
            return stock_payload(candidate)
    return {}


def _sector_diffusion_price_acceptance_rows(candidate_pool, target_date="", direction="", sector_index=None):
    target_date = _valid_trade_date(target_date)
    direction = _sector_name(direction)
    if not direction:
        return []
    rows = []
    for item in _as_list(candidate_pool):
        item = _as_dict(item)
        item_direction = _sector_name(item.get("sector") or item.get("mainline"))
        if direction and not _sector_names_match(item_direction, direction, sector_index):
            continue
        brooks = _as_dict(item.get("brooks_price_action_judge"))
        brooks_status = clean_text(brooks.get("status"))
        source_date = _valid_trade_date(
            item.get("price_source_date")
        )
        rows.append(
            {
                "stock": stock_payload(item.get("stock")),
                "sector": clean_visible_text(item.get("sector")),
                "status": (
                    "accepted"
                    if brooks_status == "accepted"
                    else "rejected"
                    if brooks_status in {"risk_first", "price_rejected"}
                    else "unresolved"
                ),
                "source_date": source_date or None,
                "source_refs": ["selection_workflow.candidate_pool"],
            }
        )
    return rows


def _selection_workflow_missing_fields(data, context, snapshot):
    missing = []
    for source in (_as_dict(data), _as_dict(context), _as_dict(snapshot)):
        for key in ("selection_workflow_missing_fields", "sector_first_missing_fields"):
            for item in _as_list(source.get(key)):
                text = clean_visible_text(item)
                if text and text not in missing:
                    missing.append(text)
    return missing


def _selected_candidate_conflicts(execution_stage_context, selected_position_candidate=None):
    if not stock_key(selected_position_candidate):
        return []
    for _, candidate in _candidate_sources(execution_stage_context):
        if _candidate_matches_selected(candidate, selected_position_candidate):
            return []
    return [f"显式对象不在候选池：{stock_label(selected_position_candidate)}"]


def _action_text(position_pct):
    try:
        position_pct = normalize_planned_position_tier_pct(position_pct)
    except (TypeError, ValueError):
        position_pct = 0
    if position_pct == 100:
        return "100%核心进攻"
    if position_pct == 50:
        return "50%条件执行"
    return "0%不参与"


PREMARKET_NARRATIVE_REVIEW_KEYS = (
    "premarket_narrative_review",
    "premarket_narrative_conflict_review",
    "premarket_external_narrative_review",
    "narrative_conflict_review",
)

STRUCTURAL_COUNTER_EVENT_MARKERS = (
    "出售",
    "削减",
    "取消",
    "限制",
    "禁令",
    "制裁",
    "过剩",
    "降价",
    "涨价",
    "订单",
    "亏损",
    "业绩",
    "监管",
    "政策",
    "关税",
    "库存",
    "停产",
    "事故",
    "调查",
    "破产",
    "违约",
    "油价",
    "商品价格",
    "价格战",
    "需求",
)

BROAD_MARKET_COUNTER_EVENT_MARKERS = (
    "美股",
    "纳指",
    "标普",
    "道指",
    "指数",
    "期货",
    "盘前",
    "海外科技股",
    "韩国指数",
)


def _first_premarket_narrative_payload(*sources):
    for source in sources:
        source = _as_dict(source)
        for key in PREMARKET_NARRATIVE_REVIEW_KEYS:
            value = source.get(key)
            if isinstance(value, dict) and value:
                return value
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and item:
                        return item
    return {}


def _split_chain_text(value):
    if isinstance(value, (list, tuple, set)):
        return _clean_list(value)
    text = clean_visible_text(value)
    if not text:
        return []
    separators = ("->", "→", "=>", "；")
    for separator in separators:
        if separator in text:
            return [part for part in (clean_visible_text(item) for item in text.split(separator)) if part]
    return [text]


def _review_source_list(raw, *keys):
    rows = []
    raw = _as_dict(raw)
    for key in keys:
        for item in _clean_list(raw.get(key)):
            if item not in rows:
                rows.append(item)
    return rows


def _normalize_counter_event(raw):
    raw = _as_dict(raw)
    event = raw.get("counter_event")
    if not isinstance(event, dict):
        event = raw.get("reverse_event") if isinstance(raw.get("reverse_event"), dict) else {}
    payload = dict(event)
    aliases = {
        "title": ("title", "event_title", "news_title"),
        "source": ("source", "provider", "news_source"),
        "source_time": ("source_time", "event_time", "news_time", "time"),
        "level": ("level", "importance", "news_level"),
        "url": ("url", "source_url", "link"),
        "event_type": ("event_type", "type", "kind"),
    }
    for target_key, source_keys in aliases.items():
        if clean_visible_text(payload.get(target_key)):
            continue
        for source_key in source_keys:
            text = clean_visible_text(raw.get(source_key))
            if text:
                payload[target_key] = text
                break
    normalized = {}
    for key in ("title", "source", "source_time", "level", "url", "event_type"):
        text = clean_visible_text(payload.get(key))
        if text:
            normalized[key] = text
    return normalized


def _counter_event_is_structural(counter_event):
    counter_event = _as_dict(counter_event)
    title = clean_visible_text(counter_event.get("title"))
    if not title:
        return False
    event_type = clean_visible_text(counter_event.get("event_type")).lower()
    if event_type in {"structural", "narrative_collapse", "driver_reversal", "counter_event", "反向事件", "叙事崩塌"}:
        return True
    if any(marker in title for marker in STRUCTURAL_COUNTER_EVENT_MARKERS):
        return True
    if any(marker in title for marker in BROAD_MARKET_COUNTER_EVENT_MARKERS):
        return False
    return True


def _normalize_target_exposure(value):
    text = clean_visible_text(value).lower()
    if text in {"direct", "直接", "直接暴露"}:
        return "direct"
    if text in {"indirect", "间接", "间接暴露"}:
        return "indirect"
    if text in {"none", "无", "无暴露"}:
        return "none"
    return "unknown"


def _action_effect_label(effect):
    return {
        "keep": "不调整",
        "observe": "核心观察",
        "no_participation": "不参与",
    }.get(effect, "不调整")


def _action_effect_position_cap(effect):
    if effect in {"observe", "no_participation"}:
        return 0
    return None


def _review_driver_tags(candidate_pool, final_stock):
    final_key = stock_key(final_stock)
    if not final_key:
        return []
    for item in candidate_pool or []:
        if not isinstance(item, dict):
            continue
        if stock_key(item.get("stock")) == final_key:
            return _clean_list(item.get("current_driver_tags"))
    return []


def _premarket_review_summary(review):
    review = _as_dict(review)
    summary = clean_visible_text(review.get("summary"))
    if summary:
        return summary
    chain = _clean_list(review.get("reason_chain"))
    if chain:
        return " -> ".join(chain)
    event = _as_dict(review.get("counter_event"))
    event_title = clean_visible_text(event.get("title"))
    if event_title:
        return event_title
    return "盘前叙事复核无完整触发链"


def _build_premarket_narrative_review(
    *,
    data=None,
    context=None,
    snapshot=None,
    selected_position_candidate=None,
    position_decision=None,
    final_target_resolution=None,
    final_stock=None,
    candidate_pool=None,
    mainline="",
    base_position_pct=0,
):
    raw = _first_premarket_narrative_payload(
        data,
        context,
        snapshot,
        selected_position_candidate,
        position_decision,
        final_target_resolution,
    )
    if not raw:
        return {}
    raw = _as_dict(raw)
    counter_event = _normalize_counter_event(raw)
    overseas_pricing = _review_source_list(raw, "overseas_pricing", "overseas_same_chain_pricing", "external_pricing")
    asia_confirmation = _review_source_list(raw, "asia_confirmation", "asia_market_confirmation")
    a_share_mapping = _review_source_list(raw, "a_share_mapping", "ashare_mapping", "a_stock_mapping", "mapping")
    reason_chain = _split_chain_text(raw.get("reason_chain") or raw.get("chain") or raw.get("derivation_chain"))
    driver_tags = _review_driver_tags(candidate_pool, final_stock)
    original_driver = clean_visible_text(
        raw.get("original_driver")
        or raw.get("current_driver")
        or raw.get("driver")
        or "、".join(driver_tags)
        or mainline
    )
    target_exposure = _normalize_target_exposure(raw.get("target_exposure") or raw.get("exposure"))
    event_title = clean_visible_text(counter_event.get("title"))
    has_counter_event = bool(event_title) and _counter_event_is_structural(counter_event)
    has_overseas = bool(overseas_pricing)
    has_asia = bool(asia_confirmation)
    has_mapping = bool(a_share_mapping)
    explicit_driver_hit = raw.get("driver_hit") or raw.get("current_driver_hit") or raw.get("hit_current_driver")
    hype_driver_match = clean_visible_text(raw.get("hype_driver_match"))
    if hype_driver_match == "current_driver_hit":
        explicit_driver_hit = True
    driver_hit = bool(explicit_driver_hit)
    if not driver_hit and target_exposure in {"direct", "indirect"}:
        evidence_text = " ".join(reason_chain + [event_title] + overseas_pricing + asia_confirmation + a_share_mapping)
        driver_terms = _clean_list(driver_tags + ([original_driver] if original_driver else []))
        driver_hit = any(term and term in evidence_text for term in driver_terms)

    complete_chain = (
        has_counter_event
        and has_overseas
        and has_asia
        and has_mapping
        and target_exposure in {"direct", "indirect"}
        and driver_hit
    )

    if not has_counter_event:
        status = "未触发"
        action_effect = "keep"
        summary = "只有外围风险偏好扰动，缺少反向事件和标的映射"
    elif not complete_chain:
        status = "观察信号"
        action_effect = "keep"
        summary = "叙事反证链条不完整，只记录观察，不降低执行资格"
    else:
        action_effect = "no_participation"
        status = "不参与"
        summary = "叙事反证链条完整，击中最终对象当前上涨发动机，取消明日新增参与"

    explicit_status = clean_visible_text(raw.get("status"))
    if explicit_status and not complete_chain:
        status = explicit_status
    position_cap_pct = _action_effect_position_cap(action_effect)
    if position_cap_pct is not None and base_position_pct:
        position_cap_pct = min(base_position_pct, position_cap_pct)

    review = {
        "status": status,
        "review_window": clean_visible_text(raw.get("review_window")),
        "original_driver": original_driver,
        "counter_event": counter_event,
        "overseas_pricing": overseas_pricing,
        "asia_confirmation": asia_confirmation,
        "a_share_mapping": a_share_mapping,
        "target_exposure": target_exposure,
        "driver_hit": driver_hit,
        "complete_chain": complete_chain,
        "action_effect": action_effect,
        "action_effect_label": _action_effect_label(action_effect),
        "position_cap_pct": position_cap_pct,
        "restore_conditions": _review_source_list(raw, "restore_conditions", "recovery_conditions"),
        "cancel_conditions": _review_source_list(raw, "cancel_conditions", "cancellation_conditions", "failure_conditions"),
        "reason_chain": reason_chain,
        "summary": clean_visible_text(raw.get("summary"), summary),
    }
    if not review["reason_chain"]:
        for item in (
            original_driver,
            event_title,
            "；".join(overseas_pricing),
            "；".join(asia_confirmation),
            "；".join(a_share_mapping),
            target_exposure if target_exposure != "unknown" else "",
            review["action_effect_label"],
        ):
            text = clean_visible_text(item)
            if text:
                review["reason_chain"].append(text)
    return review


def _apply_premarket_review_position(position_pct, review):
    review = _as_dict(review)
    cap = review.get("position_cap_pct")
    if cap in (None, ""):
        return position_pct
    try:
        position_pct = normalize_planned_position_tier_pct(position_pct)
        cap_pct = planned_position_tier_cap_pct(cap)
    except (TypeError, ValueError):
        return 0
    return min(position_pct, cap_pct)


def _premarket_review_judgement(review, action_text):
    review = _as_dict(review)
    if not review:
        return ""
    status = clean_visible_text(review.get("status"), "未触发")
    summary = _premarket_review_summary(review)
    effect = clean_visible_text(review.get("action_effect_label"), "不调整")
    return f"{status}：{summary}；动作上限：{effect}；最终动作：{action_text}"


def _premarket_review_final_reason(review):
    review = _as_dict(review)
    if not review:
        return ""
    parts = [
        f"盘前叙事反证复核={clean_visible_text(review.get('status'), '未触发')}",
        _premarket_review_summary(review),
        f"动作上限={clean_visible_text(review.get('action_effect_label'), '不调整')}",
    ]
    restore = "、".join(_clean_list(review.get("restore_conditions")))
    cancel = "、".join(_clean_list(review.get("cancel_conditions")))
    if restore:
        parts.append(f"恢复条件={restore}")
    if cancel:
        parts.append(f"不参与条件={cancel}")
    return "；".join(part for part in parts if clean_visible_text(part))


def build_selection_workflow(
    *,
    target_date="",
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    selected_position_candidate=None,
    position_decision=None,
    final_target_resolution=None,
    formal_candidate_selection=None,
):
    data = _as_dict(data)
    context = dict(_as_dict(execution_stage_context))
    snapshot = _as_dict(market_research_snapshot)
    target_date = clean_text(target_date or data.get("target_date") or snapshot.get("target_date"))
    source_date = clean_text(data.get("source_date") or snapshot.get("source_date") or target_date)
    context["_selection_target_date"] = target_date
    quote_lookup = _build_quote_lookup(data, context, snapshot, target_date=target_date)
    if _quote_backfill_enabled(data, context, snapshot):
        quote_lookup = _backfill_quote_lookup(
            quote_lookup,
            target_date=target_date,
            execution_stage_context=context,
            selected_position_candidate=selected_position_candidate,
        )
    missing_fields = _selection_workflow_missing_fields(data, context, snapshot)
    sector_index = _sector_canonical_index(data, context, snapshot)
    local_trend_sector_proof = _local_trend_sector_proof(
        data,
        context,
        snapshot,
        target_date=target_date,
        sector_index=sector_index,
    )
    if local_trend_sector_proof.get("source_date_matches_target") is False:
        missing_fields.append("板块事实日期")
    market_participation_limit = _market_participation_limit(
        data,
        context,
        snapshot,
        missing_fields=missing_fields,
        target_date=target_date,
    )
    liquidity_allocation_facts = _liquidity_allocation_facts(
        data,
        context,
        snapshot,
        target_date=target_date,
    )
    context["local_trend_sector_proof"] = local_trend_sector_proof
    context["mainline_name"] = local_trend_sector_proof.get("direction") or ""
    final_stock = _pick_final_candidate(
        context,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        quote_lookup=quote_lookup,
        local_trend_sector_proof=local_trend_sector_proof,
        sector_index=sector_index,
        formal_candidate_selection=formal_candidate_selection,
    )
    if missing_fields:
        final_stock = {}
    planned_position_pct = _position_pct(position_decision) if final_stock else 0
    base_position_pct = min(planned_position_pct, market_participation_limit["max_position_pct"])
    base_execution_stock = final_stock if base_position_pct else {}
    base_candidate_pool = _build_candidate_pool(
        context,
        base_execution_stock,
        selected_position_candidate,
        local_trend_sector_proof=local_trend_sector_proof,
        sector_index=sector_index,
    )
    local_trend_sector_proof["matching_candidates"] = [
        item.get("stock")
        for item in base_candidate_pool
        if item.get("local_trend_sector_match") and item.get("new_entry_qualified")
    ]
    premarket_narrative_review = _build_premarket_narrative_review(
        data=data,
        context=context,
        snapshot=snapshot,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        final_target_resolution=final_target_resolution,
        final_stock=final_stock,
        candidate_pool=base_candidate_pool,
        mainline=clean_text(local_trend_sector_proof.get("direction"), ""),
        base_position_pct=base_position_pct,
    )
    position_pct = _apply_premarket_review_position(base_position_pct, premarket_narrative_review)
    execution_stock = final_stock if position_pct else {}
    candidate_pool = _build_candidate_pool(
        context,
        execution_stock,
        selected_position_candidate,
        quote_lookup=quote_lookup,
        local_trend_sector_proof=local_trend_sector_proof,
        sector_index=sector_index,
    )
    sector_diffusion_stage_evidence = build_sector_diffusion_stage_evidence(
        target_date=target_date,
        local_trend_sector_proof=local_trend_sector_proof,
        price_acceptance_rows=_sector_diffusion_price_acceptance_rows(
            candidate_pool,
            target_date=target_date,
            direction=local_trend_sector_proof.get("direction"),
            sector_index=sector_index,
        ),
        source_refs=[
            "selection_workflow.local_trend_sector_proof",
            "selection_workflow.candidate_pool",
        ],
    )
    sector_tournament_three_axis = build_sector_tournament_three_axis(
        target_date=target_date,
        sector_diffusion_stage_evidence=sector_diffusion_stage_evidence,
        local_trend_sector_proof=local_trend_sector_proof,
        market_participation_limit=market_participation_limit,
        liquidity_allocation_facts=liquidity_allocation_facts,
        source_refs=[
            "selection_workflow.market_participation_limit",
            "selection_workflow.local_trend_sector_proof",
            "selection_workflow.sector_diffusion_stage_evidence",
            "selection_workflow.market_stats",
            "selection_workflow.current_sector_turnover_snapshot",
            "selection_workflow.recent_sector_turnover_history",
        ],
    )
    if premarket_narrative_review:
        final_key = stock_key(final_stock)
        for item in candidate_pool:
            if isinstance(item, dict) and final_key and stock_key(item.get("stock")) == final_key:
                item["premarket_narrative_review"] = dict(premarket_narrative_review)
    conflicts = _selected_candidate_conflicts(context, selected_position_candidate)
    market_state = clean_text(_as_dict(context.get("market_state_snapshot")).get("market_state"), "市场状态待确认")
    mainline = clean_text(
        local_trend_sector_proof.get("direction"),
        "主线待确认",
    )
    market_layer = {
        "market_atmosphere": market_state,
        "profit_effect": clean_text(context.get("profit_effect") or context.get("赚钱效应"), "待确认"),
        "volume_quality": clean_text(context.get("volume_quality") or context.get("成交量质量"), "待确认"),
        "risk_preference": clean_text(context.get("risk_preference") or context.get("风险偏好"), "待确认"),
        "allow_sector_diagnosis": not bool(missing_fields),
        "market_participation_limit": market_participation_limit,
    }
    sector_layer = {
        "selected_direction": local_trend_sector_proof.get("direction") or "",
        "sector_path_selected": bool(local_trend_sector_proof.get("complete")),
        "sector_fermentation": clean_text(context.get("sector_fermentation") or context.get("板块发酵"), "待确认"),
        "sector_emotion": clean_text(context.get("sector_emotion") or context.get("板块情绪"), "待确认"),
        "turnover_expansion": clean_text(context.get("sector_turnover_expansion") or context.get("板块成交扩散"), "待确认"),
        "backrow_acceptance": clean_text(context.get("backrow_acceptance") or context.get("后排承接"), "待确认"),
        "local_trend_sector_proof": local_trend_sector_proof,
        "sector_diffusion_stage_evidence": sector_diffusion_stage_evidence,
    }
    leader_layer = {
        "leader_source": "板块发酵推导" if base_execution_stock and any(item.get("new_entry_qualified") for item in base_candidate_pool) else "待确认",
        "leader": stock_label(base_execution_stock) if base_execution_stock else "暂无",
        "market_selection_rule": "下一级必须证明承接了上一级资金选择",
    }
    data_completeness = {
        "status": "failed" if missing_fields else "success",
        "missing_fields": missing_fields,
        "action": "关键数据不完整，停止生成" if missing_fields else "继续推导",
    }
    base_execution_label = stock_label(base_execution_stock)
    brooks_counts = {}
    for item in candidate_pool:
        status = _as_dict(item.get("brooks_price_action_judge")).get("status", "insufficient")
        brooks_counts[status] = brooks_counts.get(status, 0) + 1
    brooks_risk_count = brooks_counts.get("risk_first", 0) + brooks_counts.get("price_rejected", 0)
    brooks_judgement = (
        f"价格确认{brooks_counts.get('accepted', 0)}只，二次确认{brooks_counts.get('needs_second_confirmation', 0)}只，"
        f"风险/分歧{brooks_risk_count}只"
    )
    common_selection_pending = sum(
        1
        for item in candidate_pool
        if _as_dict(item.get("common_selection_consistency")).get("status") == "待复核"
    )

    if missing_fields:
        n8_judgement = f"关键数据不完整，停止生成：{'、'.join(missing_fields)}"
    elif not local_trend_sector_proof.get("complete"):
        n8_judgement = (
            "0%不参与；局部趋势板块证据不足："
            + "、".join(local_trend_sector_proof.get("evidence_gaps", []))
        )
    else:
        n8_judgement = (
            f"{_action_text(base_position_pct)}；市场参与上限"
            f"{market_participation_limit['max_position_pct']}%"
        )
    n8_source_node = "N8"
    adjusted_action_text = _action_text(position_pct)
    nodes = [
        _node("N0", "数据封装", judgement=f"事实日期：{target_date or '待确认'}", passes_forward={"target_date": target_date}),
        _node("N1", "市场周期判断", input_refs=["N0"], judgement=market_state, passes_forward={"market_layer": market_layer}),
        _node("N2", "资金方向判断", input_refs=["N1"], judgement=f"资金方向：{mainline}", passes_forward={"mainline": mainline, "volume_role": "量能先用于识别资金表态"}),
        _node(
            "N3",
            "板块关系拆解",
            input_refs=["N2"],
            judgement=f"板块方向：{mainline}",
            passes_forward={
                "sector_layer": sector_layer,
                "sector_tournament_three_axis": sector_tournament_three_axis,
            },
        ),
        _node("N4", "板块内角色识别", input_refs=["N3"], judgement="识别板块内角色", passes_forward={"leader_layer": leader_layer, "has_sector_roles": bool(context.get("sector_trend_snapshot"))}),
        _node("N5", "候选池归一", input_refs=["N4"], judgement=f"归一候选{len(base_candidate_pool)}只", passes_forward={"candidate_count": len(base_candidate_pool)}),
        _node(
            "N6",
            "反推龙头",
            input_refs=["N5"],
            judgement=f"保留对象：{base_execution_label if base_execution_stock else '无'}",
            passes_forward={
                "execution_object": base_execution_stock,
                "market_layer": market_layer,
                "sector_layer": sector_layer,
                "leader_layer": leader_layer,
                "leader_debate": "先问为什么做它，再问为什么不做板块锚",
            },
            conflicts=conflicts,
        ),
        _node(
            "N7",
            "候选对照淘汰",
            input_refs=["N6"],
            judgement=f"布鲁克斯价格行为裁判：{brooks_judgement}；共同选择待复核{common_selection_pending}只",
            passes_forward={
                "execution_object": base_execution_stock,
                "brooks_price_action": {
                    "price_first": True,
                    "volume_role": "资金表态证据",
                    "risk_or_rejection_count": brooks_risk_count,
                },
                "common_selection_pending": common_selection_pending,
            },
            cannot_conclude=["成交量不能单独生成买入资格", "指标组合不能替代价格趋势和常用K线"],
        ),
        _node(
            "N8",
            "仓位与执行条件",
            input_refs=["N7"],
            judgement=n8_judgement,
            passes_forward={
                "execution_object": base_execution_stock,
                "base_position_pct": base_position_pct,
                "planned_position_pct": planned_position_pct,
                "market_participation_limit": market_participation_limit,
                "local_trend_sector_proof": local_trend_sector_proof,
                "position_pct": position_pct if not premarket_narrative_review else base_position_pct,
                "data_completeness": data_completeness,
                "premarket_narrative_review": premarket_narrative_review,
            },
        ),
    ]
    if premarket_narrative_review:
        n8_source_node = "N8_5" if position_pct != base_position_pct else "N8"
        nodes.append(
            _node(
                "N8_5",
                "盘前叙事反证复核",
                input_refs=["N8"],
                judgement=_premarket_review_judgement(premarket_narrative_review, adjusted_action_text),
                passes_forward={
                    "execution_object": execution_stock,
                    "position_pct": position_pct,
                    "premarket_narrative_review": premarket_narrative_review,
                },
                cannot_conclude=(
                    ["普通外围波动不能单独降低执行资格"]
                    if premarket_narrative_review.get("status") in {"未触发", "观察信号"}
                    else []
                ),
            )
        )
    nodes.append(
        _node(
            "N9",
            "输出一致性复核",
            input_refs=[n8_source_node],
            judgement="同源输出",
            passes_forward={"source_node": n8_source_node},
            conflicts=conflicts,
        )
    )
    formal_selection = _as_dict(formal_candidate_selection)
    formal_selection_status = clean_text(formal_selection.get("status"))
    formal_selection_reason = {
        "tie_unresolved": "统一候选台账无法证明唯一优势，保持现金",
        "unresolved": "统一候选台账的比较事实不足，保持现金",
        "no_qualified_candidate": "统一候选台账没有取得完整资格的对象，保持现金",
        "facts_invalid": "统一候选台账的目标日事实不完整，保持现金",
    }.get(formal_selection_status, "")
    if (
        not formal_selection_reason
        and formal_selection_status in {"clear_winner", "single_qualified"}
        and not final_stock
    ):
        formal_selection_reason = "统一候选胜者未通过目标日板块、价格和执行事实复核，保持现金"
    final_failure_conditions = list(missing_fields)
    if formal_selection_reason:
        final_failure_conditions.append(formal_selection_reason)
    if not local_trend_sector_proof.get("complete"):
        final_failure_conditions.extend(
            f"局部趋势板块证明缺少{item}"
            for item in local_trend_sector_proof.get("evidence_gaps", [])
        )
    if market_participation_limit.get("systemic_risk"):
        final_failure_conditions.append(market_participation_limit.get("reason"))
    candidate_direction_mismatch = bool(
        local_trend_sector_proof.get("complete")
        and candidate_pool
        and not any(
            item.get("new_entry_qualified")
            and (
                item.get("local_trend_sector_match")
                or item.get("candidate_origin") == "market_emotion_line"
            )
            for item in candidate_pool
        )
    )
    if candidate_direction_mismatch:
        final_failure_conditions.append("个股与已证明方向不匹配")
    if premarket_narrative_review and position_pct <= 0 and base_position_pct > 0:
        final_failure_conditions.extend(_clean_list(premarket_narrative_review.get("cancel_conditions")))
        summary = _premarket_review_summary(premarket_narrative_review)
        if summary and summary not in final_failure_conditions:
            final_failure_conditions.append(summary)
    final_reason = _premarket_review_final_reason(premarket_narrative_review)
    if not final_reason and formal_selection_reason:
        final_reason = formal_selection_reason
    if not final_reason and missing_fields:
        final_reason = "关键数据不完整，停止生成"
    elif not final_reason and market_participation_limit.get("systemic_risk"):
        final_reason = market_participation_limit.get("reason")
    elif not final_reason and not local_trend_sector_proof.get("complete"):
        final_reason = "局部趋势板块证据不足：" + "、".join(
            local_trend_sector_proof.get("evidence_gaps", [])
        )
    elif not final_reason and candidate_direction_mismatch:
        final_reason = "个股与已证明方向不匹配"
    elif not final_reason:
        final_reason = market_participation_limit.get("reason", "")

    return {
        "schema_version": SCHEMA_VERSION,
        "derivation_contract": DERIVATION_CONTRACT,
        "target_date": target_date,
        "source_date": source_date,
        "source_dates": _selection_source_dates(
            target_date,
            data,
            context,
            snapshot,
            local_trend_sector_proof,
        ),
        "market_layer": market_layer,
        "market_participation_limit": market_participation_limit,
        "sector_layer": sector_layer,
        "local_trend_sector_proof": local_trend_sector_proof,
        "sector_diffusion_stage_evidence": sector_diffusion_stage_evidence,
        "sector_tournament_three_axis": sector_tournament_three_axis,
        "leader_layer": leader_layer,
        "data_completeness": data_completeness,
        "nodes": nodes,
        "candidate_pool": candidate_pool,
        "formal_candidate_selection": dict(formal_selection),
        "premarket_narrative_review": premarket_narrative_review,
        "final": {
            "execution_object": execution_stock,
            "position_pct": position_pct,
            "action_text": adjusted_action_text,
            "source_node": n8_source_node,
            "trigger_paths": _clean_list(premarket_narrative_review.get("restore_conditions")) if premarket_narrative_review else [],
            "failure_conditions": final_failure_conditions,
            "fail_action": "0%不参与",
            "premarket_narrative_review": premarket_narrative_review,
            "reason": final_reason,
            "b1_only": position_pct == 50 and not market_participation_limit.get("b2_allowed"),
            "b2_allowed": bool(position_pct and market_participation_limit.get("b2_allowed")),
        },
        "flowchart_payload": {
            "nodes": [{"id": node["node_id"], "label": node["node_name"], "judgement": node["judgement"]} for node in nodes],
            "final_label": stock_label(execution_stock) if position_pct else "无执行对象",
        },
    }


def store_selection_workflow(workflow, *targets):
    if not isinstance(workflow, dict) or not workflow:
        return {}
    stored = dict(workflow)
    for target in targets:
        if isinstance(target, dict):
            target["selection_workflow"] = stored
    return stored


def _mermaid_escape(value):
    return clean_text(value).replace('"', "'")


def _mermaid_wrap(value, *, max_chars=22):
    text = _mermaid_escape(value)
    wrapped = []
    for source_line in text.split("<br/>"):
        remaining = source_line
        while len(remaining) > max_chars:
            boundaries = [
                remaining.rfind(marker, 0, max_chars + 1) + len(marker)
                for marker in ("；", "，", "。", "、", "：", ":", " ")
            ]
            split_at = max(boundaries)
            if split_at < max_chars // 2:
                split_at = max_chars
            wrapped.append(remaining[:split_at])
            remaining = remaining[split_at:]
        wrapped.append(remaining)
    return "<br/>".join(part for part in wrapped if part)


def render_selection_workflow_mermaid(workflow):
    workflow = workflow if isinstance(workflow, dict) else {}
    lines = ["flowchart TD"]
    previous = ""
    known_ids = set()
    edges = []
    for node in workflow.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_id = clean_text(node.get("node_id"))
        if not node_id:
            continue
        known_ids.add(node_id)
        node_title = _mermaid_escape(
            " ".join(part for part in (node_id, clean_text(node.get("node_name"))) if part)
        )
        judgement = _mermaid_wrap(node.get("judgement"))
        label = f"{node_title}<br/>{judgement}"
        lines.append(f'  {node_id}["{label}"]')
        input_refs = [clean_text(item) for item in node.get("input_refs", []) or [] if clean_text(item)]
        if input_refs:
            for input_ref in input_refs:
                edges.append((input_ref, node_id))
        elif previous:
            edges.append((previous, node_id))
        previous = node_id
    for source, target_id in edges:
        if source in known_ids and target_id in known_ids:
            lines.append(f"  {source} --> {target_id}")
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    pct = _position_pct({"target_position_pct": final.get("position_pct", 0)})
    target = stock_label(final.get("execution_object")) if pct > 0 else "暂无"
    final_label = _mermaid_escape(f"最终：{target}<br/>仓位：{pct}%")
    lines.append(f'  FINAL["{final_label}"]')
    source_node = clean_text(final.get("source_node"))
    if source_node in known_ids:
        lines.append(f"  {source_node} --> FINAL")
    elif previous:
        lines.append(f"  {previous} --> FINAL")
    return "\n".join(lines)


__all__ = [
    "build_selection_workflow",
    "clean_text",
    "normalize_stock_code",
    "refresh_sector_tournament_three_axis_for_display",
    "render_selection_workflow_mermaid",
    "stock_key",
    "stock_label",
    "stock_payload",
    "store_selection_workflow",
]
