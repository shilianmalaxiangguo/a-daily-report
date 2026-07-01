from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from selection.candidate_execution_contracts import (
    build_participation_window_from_candidate,
    build_participation_window_policy,
)

ARTIFACT_VERSION = 1
DECISION_REVISION_LEDGER_SCHEMA_VERSION = "decision_revision_ledger.v1"
DEFAULT_CYCLE_LENGTH_TRADE_DAYS = 25
SELECTION_RULE_VERSION = "extreme-conviction-ledger-v1"
_NON_SECTOR_LABELS = {
    "HS",
    "GEM",
    "STAR",
    "BJ",
    "SH",
    "SZ",
    "沪深",
    "创业板",
    "科创板",
    "北交所",
    "未知",
    "未归类",
    "其他",
    "其它",
    "-",
}
_STOCK_SECTOR_REPAIRS = {
    "001259": "股权转让",
    "300721": "湿电子化学品",
    "688549": "电子特气",
}
_QUANT_ANCHOR_LABELS = {
    "锚点区间": "anchor_zone_role",
    "共振线": "anchor_line_confluence",
    "隐藏盘": "hidden_liquidity_read",
    "动作": "anchor_action_plan",
    "共同选择": "common_selection_factors",
    "动量反馈": "momentum_feedback_plan",
    "反包兑现": "reversal_exit_plan",
}
_QUANT_ANCHOR_FIELDS = (
    "anchor_zone_role",
    "anchor_line_confluence",
    "hidden_liquidity_read",
    "anchor_action_plan",
    "common_selection_factors",
    "momentum_feedback_plan",
    "reversal_exit_plan",
)
_SOURCE_DATE_FIELDS = ("snapshot_date", "refill_date", "price_source_date")
_PERFORMANCE_FIELDS = ("return_1d_pct", "return_3d_pct", "return_5d_pct", "max_drawdown_5d_pct")
_WAITING_REVIEW_STATUSES = {"等待复盘", "等待窗口复盘", "等待事实", ""}
_MARKET_STATE_BUCKETS = {"进攻", "退潮", "修复", "混沌", "冰点"}
_NO_CONFIRMED_MAINLINE_LABELS = {"无确认主线", "暂无明确主线", "暂无", "无", "-", "待确认", "主线待确认"}
_JUDGMENT_LABEL_TO_TYPE = {
    "市场状态判断": "market_state",
    "主线判断": "mainline",
    "核心候选判断": "core_candidate",
}
_CANDIDATE_VISIBILITY_FIELDS = (
    "extreme_conviction_list",
    "selected_position_candidate",
    "hot_rank_top50",
    "hot_rank_top30",
    "integrated_hot_list",
    "wanzhu_top10",
    "xueqiu_hot_rank_top100",
    "zt_pool",
    "lianban_data",
    "turnover_rank",
)
_CORE_CANDIDATE_MISS_STATUSES = {"预演作废", "预演过早", "主目标不可成交"}
_CORE_CANDIDATE_HIT_STATUSES = {"预演命中", "错过后方案命中"}
_CORE_CANDIDATE_NEGATIVE_RETURN_PCT = -3.0
_CORE_CANDIDATE_HARD_DRAWDOWN_PCT = -8.0


def _normalize_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return "".join(ch for ch in text if ch.isdigit()) or text


def _clean_text(value, default=""):
    text = str(value or "").strip()
    return text or default


def _final_execution_target_from_action(final_action):
    action = final_action if isinstance(final_action, dict) else {}
    position_pct = _position_plan_pct_from_value(
        action.get("position_pct")
        if "position_pct" in action
        else action.get("target_position_pct")
    )
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    stock_code = _normalize_stock_code(target.get("stock_code") or target.get("code"))
    if stock_code and position_pct in (50, 100):
        return {
            "stock_code": stock_code,
            "stock_name": _clean_text(target.get("stock_name") or target.get("name")),
        }
    return {}


def _same_stock_code(stock_code, target):
    return bool(target and _normalize_stock_code(stock_code) == _normalize_stock_code(target.get("stock_code")))


def _final_execution_label(target):
    name = _clean_text(target.get("stock_name"))
    code = _normalize_stock_code(target.get("stock_code"))
    if name and code:
        return f"{name}({code})"
    return name or code or "明日执行对象"


def _final_execution_history_action(target):
    return f"{_final_execution_label(target)}已进入明日执行计划；只按昨晚预案检查执行资格，不满足回到0%不参与"


def _is_valid_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_SECTOR_LABELS)


def _iter_plate_names(value):
    for item in value or []:
        if isinstance(item, dict):
            for key in ("plate_name", "name", "concept_name", "sector"):
                candidate = _clean_text(item.get(key))
                if candidate:
                    yield candidate
        else:
            candidate = _clean_text(item)
            if candidate:
                yield candidate


def _resolve_sector_candidate(item, default="未归类"):
    item = item or {}
    for value in (
        item.get("sector"),
        item.get("sector_candidate"),
    ):
        if _is_valid_sector_label(value):
            return _clean_text(value)
    for field in (
        "xuangubao_related_plates",
        "related_plates",
        "plates",
        "concepts",
        "xuangubao_related_plate_names",
    ):
        for value in _iter_plate_names(item.get(field)):
            if _is_valid_sector_label(value):
                return _clean_text(value)
    for value in (
        item.get("industry"),
        item.get("所属行业"),
        item.get("sector_name"),
    ):
        if _is_valid_sector_label(value):
            return _clean_text(value)
    return default


def _replace_invalid_sector_tokens(text, sector):
    if not _is_valid_sector_label(sector) or not isinstance(text, str):
        return text
    updated = text
    for label in _NON_SECTOR_LABELS:
        if not label or label in {"-", "其他", "其它", "未知", "未归类"}:
            continue
        updated = updated.replace(f"沿{label}趋势比价链", f"沿{sector}趋势比价链")
        updated = updated.replace(f"{label}趋势比价链", f"{sector}趋势比价链")
    return updated


def _sanitize_sector_references(value, sector):
    if isinstance(value, dict):
        return {key: _sanitize_sector_references(item, sector) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_sector_references(item, sector) for item in value]
    if isinstance(value, str):
        return _replace_invalid_sector_tokens(value, sector)
    return value


def _sector_from_case_or_record(record, default=""):
    record = record or {}
    candidates = [
        (record.get("hypothesis") or {}).get("sector_candidate") if isinstance(record.get("hypothesis"), dict) else "",
        record.get("sector"),
        record.get("sector_candidate"),
        record.get("industry"),
        record.get("所属行业"),
        record.get("sector_name"),
    ]
    for value in candidates:
        if _is_valid_sector_label(value):
            return _clean_text(value)
    stock_code = _normalize_stock_code(record.get("stock_code") or record.get("code"))
    if stock_code and _is_valid_sector_label(_STOCK_SECTOR_REPAIRS.get(stock_code)):
        return _STOCK_SECTOR_REPAIRS[stock_code]
    return default


def _sanitize_case_or_record_sector(record):
    if not isinstance(record, dict):
        return record
    sector = _sector_from_case_or_record(record)
    if not _is_valid_sector_label(sector):
        return record
    updated = _sanitize_sector_references(record, sector)
    hypothesis = dict(updated.get("hypothesis") or {})
    if hypothesis:
        hypothesis["sector_candidate"] = sector
        updated["hypothesis"] = hypothesis
    if not _is_valid_sector_label(updated.get("sector")) and "sector" in updated:
        updated["sector"] = sector
    if not _is_valid_sector_label(updated.get("sector_candidate")) and "sector_candidate" in updated:
        updated["sector_candidate"] = sector
    return updated


def _prune_future_mentions_from_case(record, trade_date):
    if not isinstance(record, dict):
        return record
    trade_date = _clean_text(trade_date)
    if not trade_date:
        return record
    mentions = []
    changed = False
    for mention in list(record.get("mentions") or []):
        mention_date = _clean_text((mention or {}).get("mention_trade_date"))
        if mention_date and mention_date > trade_date:
            changed = True
            continue
        mentions.append(mention)
    if not changed:
        return record
    if not mentions:
        return None
    return _sync_record_to_latest_remaining_mention(record, mentions)


def _dedupe_case_mentions(record):
    if not isinstance(record, dict):
        return record
    mentions = _merge_mentions_without_duplicates([], record.get("mentions") or [])
    if len(mentions) == len(list(record.get("mentions") or [])):
        return record
    if not mentions:
        return None
    return _sync_record_to_latest_remaining_mention(record, mentions)


def _sanitize_decision_ledger_index(index):
    if not isinstance(index, dict):
        return {}
    updated_index = dict(index)
    sanitized_by_stock_code = {}
    for code, records in (index.get("by_stock_code") or {}).items():
        sanitized_by_stock_code[code] = [
            _sanitize_case_or_record_sector(record) for record in list(records or [])
        ]
    updated_index["by_stock_code"] = sanitized_by_stock_code
    if "extreme_conviction_backtest_rows" in updated_index:
        updated_index["extreme_conviction_backtest_rows"] = build_extreme_conviction_backtest_rows(
            {"by_stock_code": sanitized_by_stock_code},
            max_rows=25,
        )
    return updated_index


def _sanitize_decision_ledger_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    updated_snapshot = dict(snapshot)
    trade_date = str(snapshot.get("trade_date") or "").strip()
    cases = []
    for case in list(snapshot.get("cases") or []):
        pruned_case = _prune_future_mentions_from_case(case, trade_date)
        pruned_case = _dedupe_case_mentions(pruned_case)
        if pruned_case:
            cases.append(_sanitize_case_or_record_sector(pruned_case))
    updated_snapshot["cases"] = cases
    return updated_snapshot


def _safe_float(value, default=None):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_or_none(value, digits=2):
    number = _safe_float(value)
    return round(number, digits) if number is not None else None


def _merge_missing_fields(*values):
    merged = []
    for value in values:
        if not value:
            continue
        if isinstance(value, str):
            items = [value]
        else:
            items = list(value or [])
        for item in items:
            field = _clean_text(item)
            if field and field not in merged:
                merged.append(field)
    return merged


def _position_plan_pct_from_value(value):
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"(100|50|0)\s*%?", text)
    if not match:
        number = _safe_float(text)
        return int(number) if number in (0, 50, 100) else None
    number = int(match.group(1))
    return number if number in (0, 50, 100) else None


def _position_plan_pct(planned=None, fallback=None):
    planned = planned or {}
    for value in (
        planned.get("position_plan_pct"),
        planned.get("target_position_pct"),
        planned.get("attack_state"),
        (fallback or {}).get("position_plan_pct") if isinstance(fallback, dict) else None,
        (fallback or {}).get("target_position_pct") if isinstance(fallback, dict) else None,
        (fallback or {}).get("attack_state") if isinstance(fallback, dict) else None,
    ):
        pct = _position_plan_pct_from_value(value)
        if pct in (0, 50, 100):
            return pct
    return None


def _position_plan_label(position_plan_pct):
    labels = {
        0: "0%不参与",
        50: "50%条件执行",
        100: "100%核心进攻",
    }
    return labels.get(position_plan_pct, "仓位三态待补")


def _contract_window_from_planned(planned):
    planned = planned or {}
    buy_window = _clean_text(planned.get("buy_window"))
    if buy_window in {"09:30-09:35", "09:50-10:10", "14:30-14:55", "no_trade"}:
        return buy_window
    text = " / ".join(
        _clean_text(planned.get(key))
        for key in ("participation_window", "entry_timing", "missed_action", "cancellation")
        if _clean_text(planned.get(key))
    )
    if "09:30-09:35" in text or planned.get("entry_timing") == "open_core":
        return "09:30-09:35"
    if "14:30-14:55" in text or planned.get("entry_timing") == "tail_exception":
        return "14:30-14:55"
    if "不参与" in text or "no_trade" in text or planned.get("entry_timing") == "no_trade":
        return "no_trade"
    return "09:50-10:10"


def _cancellation_conditions_from_plan(planned=None, fallback=None):
    planned = planned or {}
    fallback = fallback or {}
    values = []
    for key in ("cancellation", "ma20_invalidation", "cancel_condition", "invalid_condition", "failure_condition"):
        value = planned.get(key)
        if value in (None, "") and isinstance(fallback, dict):
            value = fallback.get(key)
        text = _clean_text(value)
        if text and text not in values:
            values.append(text)
    return values


def _enrich_planned_participation_contract(planned):
    planned = dict(planned or {})
    position_pct = _position_plan_pct(planned)
    if position_pct is None:
        position_pct = 0 if _contract_window_from_planned(planned) == "no_trade" else 50
    cancellation_conditions = _cancellation_conditions_from_plan(planned)
    confirm_conditions = [
        _clean_text(planned.get(key))
        for key in ("auction", "first_minutes", "board", "reseal")
        if _clean_text(planned.get(key)) and _clean_text(planned.get(key)) != "不启用"
    ]
    window = _contract_window_from_planned(planned)
    planned.update(
        {
            "schema_version": "planned_participation.v1",
            "window": window,
            "position_plan_pct": position_pct,
            "action": "participate" if position_pct in (50, 100) and window != "no_trade" else "skip",
            "confirm_conditions": confirm_conditions,
            "cancellation_conditions": cancellation_conditions,
            "missed_entry_plan": planned.get("missed_action") or planned.get("missed_entry_policy"),
            "invalid_price": planned.get("invalid_price") or planned.get("invalidation_price"),
            "risk_reward_ratio": _round_or_none(planned.get("risk_reward_ratio")),
        }
    )
    return planned


def _normalize_source_dates(*payloads, default_snapshot_date=None, default_price_source_date=None):
    source_dates = {key: None for key in _SOURCE_DATE_FIELDS}
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        nested = payload.get("source_dates") if isinstance(payload.get("source_dates"), dict) else {}
        for key in _SOURCE_DATE_FIELDS:
            value = nested.get(key)
            if value in (None, ""):
                value = payload.get(key)
            if value not in (None, ""):
                source_dates[key] = _clean_text(value)
        if not source_dates["price_source_date"]:
            for key in ("price_date", "source_date", "query_date", "trade_date"):
                if payload.get(key) not in (None, ""):
                    source_dates["price_source_date"] = _clean_text(payload.get(key))
                    break
    if not source_dates["snapshot_date"] and default_snapshot_date:
        source_dates["snapshot_date"] = _clean_text(default_snapshot_date)
    if not source_dates["price_source_date"] and default_price_source_date:
        source_dates["price_source_date"] = _clean_text(default_price_source_date)
    return source_dates


def _normalize_performance_payload(performance=None):
    performance = performance if isinstance(performance, dict) else {}
    normalized = {}
    for field in _PERFORMANCE_FIELDS:
        normalized[field] = _round_or_none(performance.get(field)) if field in performance else None
    return normalized


def _price_rows_from_fact(fact):
    fact = fact or {}
    for key in ("price_bars", "daily_bars", "rows"):
        if isinstance(fact.get(key), list):
            return list(fact.get(key) or [])
    return []


def _price_row_date(row):
    return str((row or {}).get("date") or (row or {}).get("trade_date") or "").strip()


def _performance_from_price_rows(fact, baseline_close):
    rows = sorted([row for row in _price_rows_from_fact(fact) if _price_row_date(row)], key=_price_row_date)
    if not rows:
        return {}
    mention_date = _clean_text(
        fact.get("mention_trade_date")
        or fact.get("report_date")
        or fact.get("prev_trade_date")
        or fact.get("snapshot_date")
    )
    baseline = _safe_float(baseline_close)
    follow_rows = rows
    if mention_date:
        mention_index = next((index for index, row in enumerate(rows) if _price_row_date(row) == mention_date), None)
        if mention_index is not None:
            baseline = _safe_float(rows[mention_index].get("close"), baseline)
            follow_rows = rows[mention_index + 1 :]
    elif len(rows) > 1:
        baseline = _safe_float(rows[0].get("close"), baseline)
        follow_rows = rows[1:]
    if baseline in (None, 0):
        return {}

    result = {}
    for days, field in ((1, "return_1d_pct"), (3, "return_3d_pct"), (5, "return_5d_pct")):
        if len(follow_rows) >= days:
            result[field] = _round_or_none(_pct_change(follow_rows[days - 1].get("close"), baseline))
    five_day_lows = [_safe_float(row.get("low")) for row in follow_rows[:5]]
    five_day_lows = [value for value in five_day_lows if value is not None]
    if five_day_lows:
        result["max_drawdown_5d_pct"] = _round_or_none(_pct_change(min(five_day_lows), baseline))
    return result


def _review_performance_from_market_fact(fact, *, prev_close=None, close_price=None, low_price=None):
    fact = fact or {}
    has_close_price = _safe_float(close_price) is not None and _safe_float(prev_close) not in (None, 0)
    source_dates = _normalize_source_dates(
        fact,
        default_snapshot_date=fact.get("report_date") or fact.get("mention_trade_date"),
        default_price_source_date=fact.get("review_trade_date") if has_close_price else None,
    )
    performance = _normalize_performance_payload(fact.get("performance"))
    row_performance = _performance_from_price_rows(fact, prev_close)
    for field, value in row_performance.items():
        if performance.get(field) is None and value is not None:
            performance[field] = value
    if performance.get("return_1d_pct") is None and has_close_price:
        performance["return_1d_pct"] = _round_or_none(_pct_change(close_price, prev_close))
    if performance.get("max_drawdown_5d_pct") is None and has_close_price and _safe_float(low_price) is not None:
        performance["max_drawdown_5d_pct"] = _round_or_none(_pct_change(low_price, prev_close))

    missing_fields = _merge_missing_fields(fact.get("missing_fields"))
    if not source_dates.get("price_source_date"):
        missing_fields = _merge_missing_fields(missing_fields, ["price_source_date"])
        performance = {field: None for field in _PERFORMANCE_FIELDS}
    for field in _PERFORMANCE_FIELDS:
        if performance.get(field) is None:
            missing_fields = _merge_missing_fields(missing_fields, [field])
    return performance, source_dates, missing_fields


def _review_fact_has_price_data(fact):
    fact = fact or {}
    if _price_rows_from_fact(fact):
        return True
    return any(fact.get(key) not in (None, "") for key in ("prev_close", "open", "high", "low", "close"))


def _review_status_for_facts(status):
    return "待补事实" if _clean_text(status) in _WAITING_REVIEW_STATUSES else _clean_text(status)


def _finalize_participation_review(review):
    review = review or {}
    review["fact_status"] = _review_status_for_facts(review.get("status"))
    if review["fact_status"] == "待补事实":
        review["missing_fields"] = _merge_missing_fields(review.get("missing_fields"), ["review_facts"])
    return review


def _build_stock_setup(item):
    reason = _clean_text(item.get("conviction_reason") or item.get("reason"), "形态条件待补充")
    pattern = _clean_text(item.get("pattern"))
    return f"{reason}；{pattern}" if pattern else reason


def _build_case_id(trade_date, stock_code, sequence=1):
    return f"{trade_date}-{stock_code}-{int(sequence):02d}"


def _canonical_json_hash(payload):
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _selection_input_hash(*, trade_date, extreme_conviction_list, market_branch, sector_relationship_state):
    normalized_items = []
    for item in list(extreme_conviction_list or []):
        normalized_items.append(
            {
                "code": _normalize_stock_code(item.get("code") or item.get("stock_code")),
                "name": _clean_text(item.get("name") or item.get("stock_name")),
                "sector": _resolve_sector_candidate(item, ""),
                "conviction_reason": _clean_text(item.get("conviction_reason") or item.get("reason")),
                "conviction_rule": _clean_text(item.get("conviction_rule")),
                "pattern": _clean_text(item.get("pattern")),
            }
        )
    return _canonical_json_hash(
        {
            "selection_rule_version": SELECTION_RULE_VERSION,
            "trade_date": trade_date,
            "market_branch": _clean_text(market_branch),
            "sector_relationship_state": _clean_text(sector_relationship_state),
            "extreme_conviction_list": normalized_items,
        }
    )


def _build_mention(item, *, trade_date, rank):
    mention = {
        "mention_trade_date": trade_date,
        "rank": rank,
        "source_section": "极度看好名单",
        "reason": _clean_text(
            item.get("conviction_reason") or item.get("reason") or item.get("conviction_rule"),
            "判断理由待补充",
        ),
    }
    core_identity = item.get("core_identity")
    if isinstance(core_identity, dict) and core_identity:
        mention["core_identity"] = core_identity
    planned_participation = _build_planned_participation(item)
    if planned_participation:
        mention["planned_participation"] = planned_participation
    return mention


def _split_markdown_row(line):
    text = str(line or "").strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def _is_markdown_separator(cells):
    return bool(cells) and all(set(str(cell).replace(" ", "")) <= {"-", ":"} for cell in cells)


def _header_index(headers, *names):
    for name in names:
        if name in headers:
            return headers.index(name)
    return -1


def _parse_quant_anchor_action_cell(value):
    text = _clean_text(value)
    parsed = {field: "" for field in _QUANT_ANCHOR_FIELDS}
    if not text or text == "-":
        return parsed

    body = text.split("：", 1)[1].strip() if text.startswith("量化锚点动作：") else text
    labeled_parts = [part.strip() for part in body.split("｜") if part.strip()]
    found_labeled_value = False
    for part in labeled_parts:
        if "=" not in part:
            continue
        label, raw_value = part.split("=", 1)
        field = _QUANT_ANCHOR_LABELS.get(label.strip())
        if field is None:
            continue
        parsed[field] = _clean_text(raw_value)
        found_labeled_value = True
    if found_labeled_value:
        return parsed

    legacy_parts = [part.strip() for part in re.split(r"[；;]", body) if part.strip()]
    for field, part in zip(_QUANT_ANCHOR_FIELDS[:4], legacy_parts[:4]):
        parsed[field] = part
    if not parsed["anchor_action_plan"] and body:
        parsed["anchor_action_plan"] = body
    return parsed


def _parse_markdown_table_after_heading(lines, heading_text):
    table_start = -1
    for idx, line in enumerate(lines):
        if _is_markdown_heading_line_for_text(line, heading_text):
            table_start = idx + 1
            break
    if table_start < 0:
        return [], []

    header = []
    rows = []
    for line in lines[table_start:]:
        stripped = line.strip()
        if not stripped:
            if header:
                break
            continue
        if not stripped.startswith("|"):
            if header:
                break
            continue
        cells = _split_markdown_row(stripped)
        if _is_markdown_separator(cells):
            continue
        if not header:
            header = cells
            continue
        rows.append(cells)
    return header, rows


def _parse_markdown_table_after_any_heading(lines, *heading_texts):
    for heading_text in heading_texts:
        header, rows = _parse_markdown_table_after_heading(lines, heading_text)
        if header:
            return header, rows
    return [], []


def _is_report_table_number_line(line):
    text = str(line or "").strip()
    return text.startswith("**T-") and text.endswith("**")


def _is_markdown_heading_line_for_text(line, heading_text):
    text = str(line or "").strip()
    if heading_text not in text:
        return False
    if text.startswith("#"):
        return True
    return text.startswith("**") and heading_text in text[: text.find("**", 2) if text.find("**", 2) > 1 else len(text)]


def _parse_markdown_tables_after_heading(lines, heading_text):
    table_start = -1
    for idx, line in enumerate(lines):
        if _is_markdown_heading_line_for_text(line, heading_text):
            table_start = idx + 1
            break
    if table_start < 0:
        return []

    tables = []
    index = table_start
    while index < len(lines):
        stripped = str(lines[index] or "").strip()
        if "参与脚本" in stripped or "复核脚本" in stripped:
            break
        if tables and stripped.startswith("#"):
            break
        if tables and stripped.startswith("**") and not _is_report_table_number_line(stripped):
            break
        if not stripped or _is_report_table_number_line(stripped):
            index += 1
            continue
        if not stripped.startswith("|"):
            if tables:
                break
            index += 1
            continue

        header = []
        rows = []
        while index < len(lines):
            table_line = str(lines[index] or "").strip()
            if not table_line.startswith("|"):
                break
            cells = _split_markdown_row(table_line)
            if _is_markdown_separator(cells):
                index += 1
                continue
            if not header:
                header = cells
            else:
                rows.append(cells)
            index += 1
        if header:
            tables.append((header, rows))
        continue
    return tables


def _parse_markdown_tables_after_any_heading(lines, *heading_texts):
    for heading_text in heading_texts:
        tables = _parse_markdown_tables_after_heading(lines, heading_text)
        if tables:
            return tables
    return []


def _execution_layer_fields(layer_label):
    label = _clean_text(layer_label)
    if not label:
        return {}
    if "风险" in label:
        return {
            "candidate_layer_label": label,
            "candidate_layer": "risk_blocked",
            "execution_eligibility": "blocked_by_negative_news",
        }
    if "可执行" in label:
        return {
            "candidate_layer_label": label,
            "candidate_layer": "executable_candidate",
            "execution_eligibility": "auction_reseal",
        }
    if "修复" in label:
        return {
            "candidate_layer_label": label,
            "candidate_layer": "watch_sample",
            "execution_eligibility": "structure_confirm_only",
        }
    if "观察" in label:
        return {
            "candidate_layer_label": label,
            "candidate_layer": "watch_sample",
            "execution_eligibility": "structure_confirm_only",
        }
    return {"candidate_layer_label": label}


def _normalize_participation_script(item):
    item = item or {}
    nested = item.get("participation_script") or item.get("planned_participation") or {}
    if not isinstance(nested, dict):
        nested = {}

    def _value(*keys):
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return _clean_text(value)
            value = nested.get(key)
            if value not in (None, ""):
                return _clean_text(value)
        return ""

    script = {
        "participation_window": _value("participation_window", "entry_window", "window"),
        "participation_window_type": _value("participation_window_type", "window_type"),
        "attack_state": _value("attack_state", "position_state", "target_position_pct"),
        "auction_required": _value("auction_required"),
        "first_minutes_required": _value("first_minutes_required"),
        "board_or_reseal_required": _value("board_or_reseal_required"),
        "ordinary_structure_confirm_allowed": _value("ordinary_structure_confirm_allowed"),
        "missed_entry_policy": _value("missed_entry_policy"),
        "source_tier": _value("source_tier"),
        "entry_timing": _value("entry_timing"),
        "buy_window": _value("buy_window"),
        "entry_timing_reason": _value("entry_timing_reason"),
        "limit_up_inertia_level": _value("limit_up_inertia_level"),
        "limit_up_inertia_score": _value("limit_up_inertia_score"),
        "next_day_limit_probability_band": _value("next_day_limit_probability_band"),
        "limit_up_inertia_reason": _value("limit_up_inertia_reason"),
        "risk_reward_min_ratio": _value("risk_reward_min_ratio"),
        "risk_reward_ratio": _value("risk_reward_ratio"),
        "risk_reward_state": _value("risk_reward_state"),
        "risk_reward_plan": _value("risk_reward_plan"),
        "anchor_zone_role": _value("anchor_zone_role", "quant_anchor_zone", "price_anchor_zone"),
        "anchor_line_confluence": _value("anchor_line_confluence", "quant_anchor_confluence", "price_anchor_confluence"),
        "hidden_liquidity_read": _value("hidden_liquidity_read", "hidden_liquidity", "quant_hidden_liquidity"),
        "anchor_action_plan": _value("anchor_action_plan", "quant_anchor_action", "price_anchor_action"),
        "common_selection_factors": _value("common_selection_factors", "quant_common_selection_factors"),
        "momentum_feedback_plan": _value("momentum_feedback_plan", "quant_momentum_feedback"),
        "reversal_exit_plan": _value("reversal_exit_plan", "quant_reversal_exit"),
        "auction": _value("auction", "auction_script"),
        "first_minutes": _value("first_minutes", "first_minutes_script", "opening_script"),
        "board": _value("board", "board_script", "limit_board_script"),
        "reseal": _value("reseal", "reseal_script"),
        "missed_action": _value("missed_action", "missed_entry_action"),
        "cancellation": _value("cancellation", "invalid_condition", "cancel_condition", "failure_condition"),
    }
    preserved = {}
    for key, value in script.items():
        if value in (None, ""):
            continue
        if key in {
            "auction_required",
            "first_minutes_required",
            "board_or_reseal_required",
            "ordinary_structure_confirm_allowed",
        } and isinstance(value, str):
            preserved[key] = value.strip().lower() in ("1", "true", "yes", "y", "是", "需要", "允许")
        elif key in {"limit_up_inertia_score", "risk_reward_min_ratio", "risk_reward_ratio"}:
            preserved[key] = _safe_float(value, None)
        else:
            preserved[key] = value
    return preserved


def _default_participation_script(item):
    item = item or {}
    sector = _resolve_sector_candidate(item, "主线")
    source_tier = _clean_text(item.get("source_tier") or item.get("selection_source_tier"), "extreme_conviction")
    window = build_participation_window_from_candidate(item)
    if window == "打板/错过":
        window = "打板/错过"
        board = "只做首次强封且大单金额持续进入，封死买不到就不追"
        missed = f"封死买不到就沿{sector}趋势比价链找低位承接，找不到就跳过"
    elif "回封参与" in window:
        window = "竞价表态 + 回封参与"
        board = "首次封板只看大单金额持续进入，弱封不追"
        missed = f"过快封死就沿{sector}趋势比价链找低位承接，找不到就跳过"
    else:
        window = "09:50-10:10窗口"
        board = "不以涨停为唯一条件，先等价格确认和承接连续"
        missed = f"确认前快速拉高就跳过，只沿{sector}趋势比价链找低位承接，找不到就跳过"
    planned = {
        "participation_window": window,
        "attack_state": "100%" if item.get("allow_full_attack") or item.get("a_grade_candidate") else "50%",
        "auction": "09:20后看价格位置、匹配金额、委托稳定和板块同步，任一不合格按0%不参与",
        "first_minutes": "09:30-09:35只看主动资金是否继续抬价，承接不连续按0%不参与",
        "board": board,
        "reseal": "开板释放抛压后快速回封，且封单质量改善、板块同步",
        "missed_action": missed,
        "cancellation": "竞价表态、开盘承接、板块同步任一失败，按0%不参与",
    }
    planned.update(build_participation_window_policy(window, missed, source_tier, candidate=item))
    return planned


def _build_planned_participation(item):
    script = _normalize_participation_script(item)
    required_keys = (
        "participation_window",
        "auction",
        "first_minutes",
        "board",
        "reseal",
        "missed_action",
        "cancellation",
    )
    if not any(script.get(key) for key in required_keys):
        return _enrich_planned_participation_contract(_default_participation_script(item))
    planned = {**_default_participation_script(item), **script}
    planned.update(
        build_participation_window_policy(
            planned.get("participation_window"),
            planned.get("missed_action"),
            planned.get("source_tier", "extreme_conviction"),
            candidate=item,
        )
    )
    for key in (
        "participation_window_type",
        "auction_required",
        "first_minutes_required",
        "board_or_reseal_required",
        "ordinary_structure_confirm_allowed",
        "missed_entry_policy",
        "source_tier",
        "entry_timing",
        "buy_window",
        "entry_timing_reason",
        "limit_up_inertia_level",
        "limit_up_inertia_score",
        "next_day_limit_probability_band",
        "limit_up_inertia_reason",
        "risk_reward_min_ratio",
        "risk_reward_ratio",
        "risk_reward_state",
        "risk_reward_plan",
        "decision_reason_basis",
        "ma_execution_anchor",
        "ma_reversion_probe",
        "daily_ma_entry_probe",
        "anchor_zone_role",
        "anchor_line_confluence",
        "hidden_liquidity_read",
        "anchor_action_plan",
        "common_selection_factors",
        "momentum_feedback_plan",
        "reversal_exit_plan",
    ):
        if key in script:
            planned[key] = script[key]
    return _enrich_planned_participation_contract(planned)


def classify_planned_participation_review(
    planned_participation=None,
    *,
    report_date=None,
    review_trade_date=None,
    auction_matched=False,
    first_minutes_accepted=False,
    structure_confirmed=False,
    board_sealed=False,
    reseal_success=False,
    sector_supported=False,
    cancellation_triggered=False,
    primary_unavailable=False,
    missed_action_worked=False,
    cancellation_evidence=None,
    missed_action_evidence=None,
    evidence=None,
    entry_decision=None,
    window_confirmed=False,
    window_failed=False,
    same_day_action=None,
    avoid_action=None,
    next_action=None,
    standard_answer_basis=None,
    market_outcome=None,
    fact_inputs=None,
    performance=None,
    source_dates=None,
    missing_fields=None,
    **_ignored,
):
    planned = planned_participation or {}
    planned_window = _clean_text(planned.get("participation_window"), "未记录参与窗口")
    attack_state = _clean_text(planned.get("attack_state"), "未记录仓位三态")
    participation_window_type = _clean_text(planned.get("participation_window_type"), "structure_confirm")
    if any(key in _ignored for key in ("prev_close", "close", "low", "price_bars", "daily_bars", "rows")):
        performance, source_dates, missing_fields = _review_performance_from_market_fact(
            {
                **_ignored,
                "review_trade_date": review_trade_date,
                "performance": performance,
                "source_dates": source_dates,
                "missing_fields": missing_fields,
            },
            prev_close=_ignored.get("prev_close"),
            close_price=_ignored.get("close"),
            low_price=_ignored.get("low"),
        )

    base = {
        "schema_version": "participation_review.v1",
        "report_date": _clean_text(report_date),
        "planned_window": planned_window,
        "participation_window_type": participation_window_type,
        "attack_state": attack_state,
        "matched_steps": [],
        "evidence": _clean_text(evidence),
        "fact_inputs": {
            "auction_matched": auction_matched,
            "first_minutes_accepted": first_minutes_accepted,
            "board_sealed": board_sealed,
            "reseal_success": reseal_success,
            "sector_supported": sector_supported,
            "cancellation_triggered": cancellation_triggered,
            "primary_unavailable": primary_unavailable,
            "missed_action_worked": missed_action_worked,
        },
        "performance": _normalize_performance_payload(performance),
        "source_dates": _normalize_source_dates(source_dates or {}),
        "missing_fields": _merge_missing_fields(missing_fields),
    }
    if isinstance(fact_inputs, dict):
        for key in base["fact_inputs"]:
            if key in fact_inputs:
                base["fact_inputs"][key] = fact_inputs.get(key)
    optional_fields = {
        "review_trade_date": review_trade_date,
        "entry_decision": entry_decision,
        "same_day_action": same_day_action,
        "avoid_action": avoid_action,
        "next_action": next_action,
        "standard_answer_basis": standard_answer_basis,
        "market_outcome": market_outcome,
    }
    for key, value in optional_fields.items():
        if value not in (None, "", [], {}):
            base[key] = value
    if auction_matched:
        base["matched_steps"].append("竞价表态")
    if first_minutes_accepted:
        base["matched_steps"].append("开盘前几分钟承接")
    if structure_confirmed:
        base["matched_steps"].append("09:50-10:10窗口")
    if board_sealed:
        base["matched_steps"].append("打板策略")
    if reseal_success:
        base["matched_steps"].append("回封参与")
    if sector_supported:
        base["matched_steps"].append("板块同步")
    if window_confirmed:
        base["matched_steps"].append("09:50-10:10承接")

    if cancellation_triggered:
        base.update(
            {
                "status": "预演作废",
                "reason": "作废条件出现，原参与方案不再成立。"
                if not window_failed
                else "09:50-10:10窗口继续走弱，原参与方案不再成立。",
                "evidence": _clean_text(cancellation_evidence, base["evidence"] or "作废条件已触发"),
            }
        )
        return _finalize_participation_review(base)

    if primary_unavailable and not missed_action_worked:
        base.update(
            {
                "status": "主目标不可成交",
                "reason": "主目标封死或不可成交，按错过后动作观察，不补票。",
                "evidence": base["evidence"] or "主目标不可成交",
            }
        )
        return _finalize_participation_review(base)

    if primary_unavailable and missed_action_worked:
        base.update(
            {
                "status": "错过后方案命中",
                "reason": "核心目标不可得，但错过后动作沿原趋势比价链生效。",
                "evidence": _clean_text(missed_action_evidence, base["evidence"] or "错过后动作获得验证"),
            }
        )
        return _finalize_participation_review(base)

    auction_required = bool(planned.get("auction_required")) or participation_window_type == "auction_reseal"
    if (
        participation_window_type == "auction_reseal"
        and auction_required
        and not auction_matched
        and entry_decision not in {"window_confirm_buy", "waiting_window_review"}
        and not window_confirmed
    ):
        base["fact_inputs"]["cancellation_triggered"] = True
        base.update(
            {
                "status": "预演作废",
                "reason": "竞价表态未成立，原参与方案不再成立。",
                "evidence": base["evidence"] or "竞价表态未成立",
            }
        )
        return _finalize_participation_review(base)

    if entry_decision == "window_confirm_buy":
        base.update(
            {
                "status": "预演命中",
                "reason": "09:50-10:10窗口完成承接确认，参与预演获得验证。",
                "evidence": base["evidence"] or "09:50-10:10承接成立",
            }
        )
        return _finalize_participation_review(base)

    if entry_decision == "waiting_window_review":
        base.update(
            {
                "status": "等待窗口复盘",
                "reason": "日线出现下影或盘中分歧，不能仅凭全天低点判定计划窗口失败，需要分钟窗口承接事实。",
                "evidence": base["evidence"] or "等待分钟窗口承接事实",
            }
        )
        return _finalize_participation_review(base)

    if participation_window_type == "structure_confirm":
        if structure_confirmed and sector_supported:
            base.update(
                {
                    "status": "预演命中",
                    "reason": "09:50-10:10窗口和板块同步共同验证。",
                    "evidence": base["evidence"] or "结构确认命中",
                }
            )
            return _finalize_participation_review(base)
        base.update(
            {
                "status": "等待复盘",
                "reason": "普通结构确认样本还缺少09:50-10:10窗口事实。",
                "evidence": base["evidence"],
            }
        )
        return _finalize_participation_review(base)

    if auction_matched and first_minutes_accepted and (board_sealed or reseal_success) and sector_supported:
        base.update(
            {
                "status": "预演命中",
                "reason": "固定交易窗口、承接、封板/回封和板块同步共同验证。",
                "evidence": base["evidence"] or "预演关键步骤连续命中",
            }
        )
        return _finalize_participation_review(base)

    if auction_matched and not first_minutes_accepted:
        base.update(
            {
                "status": "预演过早",
                "reason": "竞价信号出现，但开盘承接没有延续。",
                "evidence": base["evidence"] or "竞价之后承接断档",
            }
        )
        return _finalize_participation_review(base)

    base.update(
        {
            "status": "等待复盘",
            "reason": "参与预演还缺少足够的次日事实。",
            "evidence": base["evidence"],
        }
    )
    return _finalize_participation_review(base)


def _infer_limit_up_pct(stock_code="", stock_name=""):
    code = _normalize_stock_code(stock_code)
    name = str(stock_name or "")
    if "ST" in name.upper() or "退" in name:
        return 5.0
    if code.startswith(("300", "301", "688")):
        return 20.0
    return 10.0


def _pct_change(value, base):
    value_num = _safe_float(value)
    base_num = _safe_float(base)
    if value_num is None or base_num in (None, 0):
        return None
    return (value_num / base_num - 1) * 100


def _close_position(high, low, close):
    high_num = _safe_float(high)
    low_num = _safe_float(low)
    close_num = _safe_float(close)
    if high_num is None or low_num is None or close_num is None:
        return None
    if high_num <= low_num:
        return 1.0 if close_num >= high_num else 0.0
    return max(0.0, min(1.0, (close_num - low_num) / (high_num - low_num)))


def _format_price(value):
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number:.2f}"


def _time_to_minutes(value):
    text = str(value or "").strip()
    if " " in text:
        text = text.rsplit(" ", 1)[-1]
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    return hour * 60 + minute


def _minute_bar_minutes(row):
    row = row or {}
    return _time_to_minutes(
        row.get("time")
        or row.get("datetime")
        or row.get("trade_time")
        or row.get("day")
        or row.get("时间")
    )


def _parse_review_window_minutes(window_text):
    matches = re.findall(r"(\d{1,2}:\d{2})", str(window_text or ""))
    if len(matches) < 2:
        return None, None
    return _time_to_minutes(matches[0]), _time_to_minutes(matches[1])


def _minute_window_review_fact(fact, review_window):
    fact = fact or {}
    minute_bars = fact.get("minute_bars") or fact.get("intraday_bars") or fact.get("minutes") or []
    if not isinstance(minute_bars, list) or not minute_bars:
        return {}
    start_minute, end_minute = _parse_review_window_minutes(review_window)
    if start_minute is None or end_minute is None:
        return {}

    prepared = []
    for row in minute_bars:
        minute_value = _minute_bar_minutes(row)
        if minute_value is None:
            continue
        prepared.append((minute_value, row or {}))
    prepared.sort(key=lambda item: item[0])
    window_rows = [row for minute_value, row in prepared if start_minute <= minute_value <= end_minute]
    if not window_rows:
        return {}

    def _price(row, *keys):
        for key in keys:
            value = _safe_float((row or {}).get(key))
            if value is not None:
                return value
        return None

    window_open = _price(window_rows[0], "open", "开盘")
    window_close = _price(window_rows[-1], "close", "收盘")
    highs = [_price(row, "high", "最高") for row in window_rows]
    lows = [_price(row, "low", "最低") for row in window_rows]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    window_high = max(highs) if highs else None
    window_low = min(lows) if lows else None

    previous_lows = [
        _price(row, "low", "最低")
        for minute_value, row in prepared
        if minute_value < start_minute
    ]
    previous_lows = [value for value in previous_lows if value is not None]
    pre_window_low = min(previous_lows) if previous_lows else None
    reference_price = _safe_float(
        fact.get("window_reference_price")
        or fact.get("intraday_yellow_line_price")
        or fact.get("yellow_line_price")
        or fact.get("ma_reversion_price")
        or fact.get("prev_close")
    )

    reclaimed_reference = (
        reference_price is not None
        and window_close is not None
        and window_close >= reference_price
    )
    closes_up = window_open is not None and window_close is not None and window_close >= window_open
    does_not_break_prior_low = (
        pre_window_low is None
        or window_low is None
        or window_low >= pre_window_low * 0.995
    )
    confirmed = bool(reclaimed_reference and closes_up and does_not_break_prior_low)
    failed = bool(
        reference_price is not None
        and window_close is not None
        and window_open is not None
        and window_low is not None
        and window_close < reference_price
        and window_close < window_open
        and window_low < reference_price
    )

    if confirmed:
        state = "confirmed"
    elif failed:
        state = "failed"
    else:
        state = "mixed"

    return {
        "state": state,
        "window_open": window_open,
        "window_high": window_high,
        "window_low": window_low,
        "window_close": window_close,
        "window_reference_price": reference_price,
        "pre_window_low": pre_window_low,
        "summary": (
            f"{review_window}窗口开{_format_price(window_open)}、高{_format_price(window_high)}、"
            f"低{_format_price(window_low)}、窗口收盘{_format_price(window_close)}、"
            f"参考{_format_price(reference_price)}"
        ),
    }


def _bool_from_fact(fact, key, fallback=False):
    if key not in fact:
        return bool(fallback)
    value = fact.get(key)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "是", "命中", "成立")
    return bool(value)


def _standard_action_text(entry_timing, buy_window, decision):
    window = _clean_text(buy_window, "none")
    if decision == "unavailable":
        return "主目标封死或不可成交，0%不参与；只记录错过后动作，不补票"
    if decision == "skip":
        return "0%不参与；等下一次预演条件重新成立"
    if decision == "waiting_window_review":
        return f"仅凭日线不能判死{window}窗口；等待分钟窗口承接事实回写后再定观察位质量"
    if decision == "window_confirm_buy":
        return f"按{window}承接成立参与；只做计划内试错，不因盘中噪音临时加码"
    if decision == "window_confirm_failed":
        return f"{window}继续走弱，0%不参与；不把日内反抽当观察位"
    if entry_timing == "open_core":
        return f"按{window}开盘核心参与；只在竞价表态、开盘承接、回封/打板同时成立时买"
    if entry_timing == "ten_confirm":
        return f"按{window}完成二次确认后再参与；确认前不抢跑"
    if entry_timing == "tail_exception":
        return f"按{window}尾盘例外确认；只用于避开盘中分歧消耗"
    return "只观察，不生成买入动作"


def build_participation_review_facts_from_market_fact(planned_participation=None, market_fact=None):
    planned = planned_participation or {}
    fact = market_fact or {}
    stock_code = _normalize_stock_code(fact.get("stock_code"))
    stock_name = _clean_text(fact.get("stock_name"))
    entry_timing = _clean_text(planned.get("entry_timing"), "ten_confirm")
    buy_window = _clean_text(planned.get("buy_window"), "09:50-10:10")
    source_tier = _clean_text(planned.get("source_tier"), "extreme_conviction")
    ma_reversion_window = _clean_text(planned.get("ma_reversion_window"))
    if entry_timing == "open_core" and not ma_reversion_window and source_tier == "extreme_conviction":
        ma_reversion_window = "09:50-10:10"
    review_window = ma_reversion_window if entry_timing == "open_core" and ma_reversion_window else buy_window
    limit_up_pct = _safe_float(fact.get("limit_up_pct"), _infer_limit_up_pct(stock_code, stock_name))
    prev_close = _safe_float(fact.get("prev_close"))
    open_price = _safe_float(fact.get("open"))
    high_price = _safe_float(fact.get("high"))
    low_price = _safe_float(fact.get("low"))
    close_price = _safe_float(fact.get("close"))
    performance, source_dates, missing_fields = _review_performance_from_market_fact(
        fact,
        prev_close=prev_close,
        close_price=close_price,
        low_price=low_price,
    )

    open_change_pct = _pct_change(open_price, prev_close)
    high_change_pct = _pct_change(high_price, prev_close)
    low_change_pct = _pct_change(low_price, prev_close)
    close_change_pct = _pct_change(close_price, prev_close)
    close_pos = _close_position(high_price, low_price, close_price)
    board_like = bool(
        high_change_pct is not None
        and close_change_pct is not None
        and high_change_pct >= limit_up_pct - 0.8
        and close_change_pct >= limit_up_pct - 1.0
        and (close_pos or 0) >= 0.85
    )
    one_word_limit = bool(
        board_like
        and open_price is not None
        and high_price is not None
        and low_price is not None
        and close_price is not None
        and abs(open_price - high_price) < 1e-9
        and abs(high_price - low_price) < 1e-9
        and abs(low_price - close_price) < 1e-9
    )
    strong_close = bool(
        close_change_pct is not None
        and close_change_pct > 0
        and close_price is not None
        and open_price is not None
        and close_price >= open_price
        and (close_pos or 0) >= 0.65
    )
    window_review = _minute_window_review_fact(fact, review_window)
    window_confirmed = window_review.get("state") == "confirmed"
    window_failed = window_review.get("state") == "failed"

    auction_matched = _bool_from_fact(
        fact,
        "auction_matched",
        open_change_pct is not None and open_change_pct >= 0 and (low_change_pct is None or low_change_pct >= -3),
    )
    first_minutes_accepted = _bool_from_fact(
        fact,
        "first_minutes_accepted",
        window_confirmed or (strong_close and (low_price is None or open_price is None or low_price >= open_price * 0.95)),
    )
    structure_confirmed = _bool_from_fact(fact, "structure_confirmed", strong_close)
    board_sealed = _bool_from_fact(fact, "board_sealed", board_like and close_price == high_price)
    reseal_success = _bool_from_fact(fact, "reseal_success", board_like and low_price is not None and high_price is not None and low_price < high_price)
    sector_supported = _bool_from_fact(fact, "sector_supported", board_like or strong_close)
    cancellation_triggered = _bool_from_fact(
        fact,
        "cancellation_triggered",
        window_failed or (
            close_change_pct is not None and (close_change_pct <= -3 or (close_pos is not None and close_pos < 0.25))
        ),
    )
    primary_unavailable = _bool_from_fact(fact, "primary_unavailable", one_word_limit)
    missed_action_worked = _bool_from_fact(fact, "missed_action_worked", False)
    needs_window_review = bool(
        entry_timing == "open_core"
        and "09:50" in review_window
        and board_like
        and low_change_pct is not None
        and low_change_pct <= -3
        and not window_confirmed
        and not window_failed
        and not any(
            key in fact
            for key in (
                "first_minutes_accepted",
                "structure_confirmed",
                "cancellation_triggered",
            )
        )
    )

    if primary_unavailable and not missed_action_worked:
        entry_decision = "unavailable"
    elif window_failed:
        entry_decision = "window_confirm_failed"
    elif window_confirmed:
        entry_decision = "window_confirm_buy"
    elif cancellation_triggered:
        entry_decision = "skip"
    elif needs_window_review:
        entry_decision = "waiting_window_review"
    elif entry_timing == "open_core" and auction_matched and first_minutes_accepted and (board_sealed or reseal_success) and sector_supported:
        entry_decision = "open_buy"
    elif entry_timing == "ten_confirm" and structure_confirmed and sector_supported:
        entry_decision = "ten_confirm_buy"
    elif entry_timing == "tail_exception" and structure_confirmed and sector_supported:
        entry_decision = "tail_confirm"
    else:
        entry_decision = "skip"

    outcome_parts = []
    for label, value in (
        ("开盘", open_change_pct),
        ("最高", high_change_pct),
        ("最低", low_change_pct),
        ("收盘", close_change_pct),
    ):
        if value is not None:
            outcome_parts.append(f"{label}{value:+.2f}%")
    if close_pos is not None:
        outcome_parts.append(f"收盘位置{close_pos:.0%}")
    if window_review:
        outcome_parts.append(str(window_review.get("summary") or ""))
    market_outcome = "，".join(outcome_parts)

    basis = []
    if auction_matched:
        basis.append("竞价表态")
    if first_minutes_accepted:
        basis.append("开盘承接")
    if structure_confirmed:
        basis.append("结构确认")
    if board_sealed or reseal_success:
        basis.append("回封/打板")
    if sector_supported:
        basis.append("板块同步")
    if window_confirmed:
        basis.append(f"{review_window}承接成立")
    if window_failed:
        basis.append(f"{review_window}继续走弱")
    if cancellation_triggered:
        basis.append("作废条件")
    if needs_window_review:
        basis.append(f"{review_window}窗口事实待补")
    standard_answer_basis = " / ".join(basis) or "条件不足"
    evidence = _clean_text(
        fact.get("evidence"),
        f"{market_outcome}；标准答案依据：{standard_answer_basis}",
    )

    return {
        "review_trade_date": _clean_text(fact.get("review_trade_date")),
        "auction_matched": auction_matched,
        "first_minutes_accepted": first_minutes_accepted,
        "structure_confirmed": structure_confirmed,
        "board_sealed": board_sealed,
        "reseal_success": reseal_success,
        "sector_supported": sector_supported,
        "cancellation_triggered": cancellation_triggered,
        "primary_unavailable": primary_unavailable,
        "missed_action_worked": missed_action_worked,
        "evidence": evidence,
        "entry_decision": entry_decision,
        "window_confirmed": window_confirmed,
        "window_failed": window_failed,
        "same_day_action": _standard_action_text(
            entry_timing,
            review_window if entry_decision in {"waiting_window_review", "window_confirm_buy", "window_confirm_failed"} else buy_window,
            entry_decision,
        ),
        "avoid_action": "任一预演条件失败按0%；封死买不到就跳过，不补票",
        "next_action": "若已买入，次日先看是否继续强于市场；失效价失守立即卖，不能把短线拿成长线",
        "standard_answer_basis": standard_answer_basis,
        "market_outcome": market_outcome,
        "fact_inputs": {
            "auction_matched": auction_matched,
            "first_minutes_accepted": first_minutes_accepted,
            "board_sealed": board_sealed,
            "reseal_success": reseal_success,
            "sector_supported": sector_supported,
            "cancellation_triggered": cancellation_triggered,
            "primary_unavailable": primary_unavailable,
            "missed_action_worked": missed_action_worked,
        },
        "performance": performance,
        "source_dates": source_dates,
        "missing_fields": missing_fields,
    }


def _parse_participation_scripts(lines):
    header, rows = _parse_markdown_table_after_any_heading(
        lines,
        "极度看好参与脚本",
        "重点观察参与脚本",
        "重点观察复核脚本",
        "过程观察参与脚本",
        "过程观察复核脚本",
        "观察样本参与脚本",
        "观察样本复核脚本",
    )
    if not header:
        return []

    window_idx = _header_index(header, "固定交易窗口条件", "固定交易窗口", "参与窗口")
    attack_idx = _header_index(header, "仓位三态", "进攻仓位三态")
    inertia_idx = _header_index(header, "涨停惯性", "惯性等级", "概率优势")
    risk_reward_idx = _header_index(header, "盈亏比", "风险收益比", "风险收益")
    auction_idx = _header_index(header, "集合竞价", "竞价表态")
    first_minutes_idx = _header_index(header, "开盘前几分钟", "开盘前分钟")
    ma_reversion_idx = _header_index(header, "均线回归观察", "均线回归试错", "日K均线回归", "分时黄线承接")
    quant_anchor_idx = _header_index(header, "量化锚点动作")
    board_idx = _header_index(header, "封板策略", "打板策略", "打板")
    reseal_idx = _header_index(header, "回封观察", "回封参与", "回封")
    missed_idx = _header_index(header, "错过后动作")
    ma20_idx = _header_index(header, "MA20作废", "MA20失效", "趋势作废")
    tracking_idx = _header_index(header, "跟踪周期", "追踪周期", "跟踪天数")
    cancel_idx = _header_index(header, "作废条件", "取消条件")

    scripts = []
    for row in rows:
        def _cell(index):
            return row[index].strip() if 0 <= index < len(row) else ""

        tracking_text = _clean_text(_cell(tracking_idx))
        tracking_days = None
        if tracking_text:
            match = re.search(r"(\d+)", tracking_text)
            if match:
                tracking_days = int(match.group(1))

        inertia_text = _clean_text(_cell(inertia_idx))
        inertia_parts = [part.strip() for part in re.split(r"[；;]", inertia_text) if part.strip()]
        risk_reward_text = _clean_text(_cell(risk_reward_idx))
        risk_reward_parts = [part.strip() for part in re.split(r"[；;]", risk_reward_text) if part.strip()]
        risk_reward_ratio = None
        ratio_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*:\s*1", risk_reward_text)
        if ratio_match:
            risk_reward_ratio = _safe_float(ratio_match.group(1), None)
        quant_anchor_text = _clean_text(_cell(quant_anchor_idx))
        quant_anchor_fields = _parse_quant_anchor_action_cell(quant_anchor_text)

        script = {
            "participation_window": _clean_text(_cell(window_idx)),
            "attack_state": _clean_text(_cell(attack_idx)),
            "limit_up_inertia_level": inertia_parts[0] if len(inertia_parts) >= 1 else "",
            "next_day_limit_probability_band": inertia_parts[1] if len(inertia_parts) >= 2 else "",
            "limit_up_inertia_reason": inertia_parts[2] if len(inertia_parts) >= 3 else inertia_text,
            "risk_reward_state": risk_reward_parts[0] if len(risk_reward_parts) >= 1 else "",
            "risk_reward_plan": risk_reward_parts[-1] if risk_reward_parts else risk_reward_text,
            **quant_anchor_fields,
            "auction": _clean_text(_cell(auction_idx)),
            "first_minutes": _clean_text(_cell(first_minutes_idx)),
            "intraday_yellow_line_probe": _clean_text(_cell(ma_reversion_idx)),
            "board": _clean_text(_cell(board_idx)),
            "reseal": _clean_text(_cell(reseal_idx)),
            "missed_action": _clean_text(_cell(missed_idx)),
            "ma20_invalidation": _clean_text(_cell(ma20_idx)),
            "cancellation": _clean_text(_cell(cancel_idx)),
        }
        if risk_reward_ratio is not None:
            script["risk_reward_ratio"] = risk_reward_ratio
        if tracking_days is not None:
            script["tracking_window_trade_days"] = tracking_days
        scripts.append(
            script
        )
    return scripts


def _parse_stock_label_with_code(label):
    text = _clean_text(label)
    match = re.search(r"(.+?)[（(]\s*([0-9]{6})(?:\.[A-Z]+)?\s*[)）]", text)
    if match:
        return _clean_text(match.group(1)), _normalize_stock_code(match.group(2))
    digits = re.search(r"([0-9]{6})", text)
    code = _normalize_stock_code(digits.group(1)) if digits else ""
    name = _clean_text(re.sub(r"[（(]?\s*[0-9]{6}(?:\.[A-Z]+)?\s*[)）]?", "", text), code)
    return name, code


def _parse_sniper_role_rows(header, rows):
    role_idx = _header_index(header, "角色")
    target_idx = _header_index(header, "标的", "股票", "名称")
    speed_idx = _header_index(header, "速度档")
    buy_line_idx = _header_index(header, "买点线")
    sell_line_idx = _header_index(header, "卖点线")
    repair_idx = _header_index(header, "承接修复条件")
    risk_idx = _header_index(header, "最终复核")
    window_idx = _header_index(header, "固定交易窗口条件", "固定交易窗口", "参与窗", "参与窗口")
    if role_idx < 0 or target_idx < 0 or buy_line_idx < 0 or sell_line_idx < 0:
        return []

    items = []
    for sequence, row in enumerate(rows, 1):
        def _cell(index):
            return row[index].strip() if 0 <= index < len(row) else ""

        role = _clean_text(_cell(role_idx))
        if role not in {"明日主买对象", "明日补位对象"}:
            continue
        name, code = _parse_stock_label_with_code(_cell(target_idx))
        if not code and not name:
            continue
        repair_condition = _clean_text(_cell(repair_idx), "等待承接修复")
        risk_status = _clean_text(_cell(risk_idx), "待复核")
        item = {
            "rank": sequence,
            "name": name,
            "code": code,
            "sector": _resolve_sector_candidate({"code": code}, "未归类"),
            "sniper_role": role,
            "leader_speed_tier": _clean_text(_cell(speed_idx), "待判定"),
            "buy_ma_line": _clean_text(_cell(buy_line_idx)),
            "sell_ma_line": _clean_text(_cell(sell_line_idx)),
            "acceptance_repair_required": repair_condition,
            "final_risk_review": {"status": risk_status},
            "candidate_layer_label": "可执行候选",
            "candidate_layer": "executable_candidate",
            "execution_eligibility": "auction_reseal",
            "conviction_reason": f"{role} / {_clean_text(_cell(speed_idx), '待判定')}",
            "conviction_rule": repair_condition,
        }
        participation_window = _clean_text(_cell(window_idx))
        if participation_window:
            item["participation_window"] = participation_window
        items.append(item)
    return items


def _parse_candidate_list_rows(header, rows, participation_scripts):
    rank_idx = _header_index(header, "优先级", "排名")
    name_idx = _header_index(header, "股票", "名称", "标的")
    code_idx = _header_index(header, "代码", "股票代码")
    sector_idx = _header_index(header, "所属板块", "板块", "所属方向")
    core_identity_idx = _header_index(header, "核心身份", "板块锚与身份")
    layer_idx = _header_index(header, "执行分层")
    reason_idx = _header_index(header, "观察理由", "极看理由", "理由", "板块锚与身份", "承接结果", "速度证据")
    rule_idx = _header_index(header, "明日原则", "原则")

    items = []
    for sequence, row in enumerate(rows, 1):
        def _cell(index):
            return row[index].strip() if 0 <= index < len(row) else ""

        code = _normalize_stock_code(_cell(code_idx))
        name = _clean_text(_cell(name_idx), code)
        if name_idx >= 0 and not code:
            parsed_name, parsed_code = _parse_stock_label_with_code(_cell(name_idx))
            name = parsed_name or name
            code = parsed_code or code
        if not code and not name:
            continue
        try:
            rank = int(_cell(rank_idx) or sequence)
        except ValueError:
            rank = sequence
        item = {
            "rank": rank,
            "name": name,
            "code": code,
            "sector": _clean_text(_cell(sector_idx), "未归类"),
            "conviction_reason": _clean_text(_cell(reason_idx), "判断理由待补充"),
            "conviction_rule": _clean_text(_cell(rule_idx), "明日原则待补充"),
        }
        core_identity_label = _clean_text(_cell(core_identity_idx))
        if core_identity_label:
            item["core_identity_label"] = core_identity_label
        item.update(_execution_layer_fields(_cell(layer_idx)))
        if sequence <= len(participation_scripts):
            item["participation_script"] = _build_planned_participation(participation_scripts[sequence - 1])
        items.append(item)
    return items


def _sector_lookup_from_candidate_rows(tables):
    lookup = {}
    for header, rows in list(tables or []):
        sector_idx = _header_index(header, "所属板块", "板块", "所属方向")
        if sector_idx < 0:
            continue
        name_idx = _header_index(header, "股票", "名称", "标的")
        code_idx = _header_index(header, "代码", "股票代码")
        for row in rows:
            def _cell(index):
                return row[index].strip() if 0 <= index < len(row) else ""

            sector = _clean_text(_cell(sector_idx))
            if not _is_valid_sector_label(sector):
                continue
            code = _normalize_stock_code(_cell(code_idx))
            if not code:
                _, code = _parse_stock_label_with_code(_cell(name_idx))
            if code:
                lookup[code] = sector
    return lookup


def parse_extreme_conviction_list_from_markdown(markdown_text):
    lines = str(markdown_text or "").splitlines()
    tables = _parse_markdown_tables_after_any_heading(
        lines,
        "极度看好名单",
        "重点观察名单",
        "过程观察名单",
        "龙头资格反推结果",
    )

    if not tables:
        return []

    participation_scripts = _parse_participation_scripts(lines)
    sector_lookup = _sector_lookup_from_candidate_rows(tables)
    sniper_items = []
    candidate_items = []
    for header, rows in tables:
        parsed_sniper_items = _parse_sniper_role_rows(header, rows)
        if parsed_sniper_items:
            for item in parsed_sniper_items:
                code = _normalize_stock_code(item.get("code"))
                if _is_valid_sector_label(sector_lookup.get(code)):
                    item["sector"] = sector_lookup[code]
            sniper_items.extend(parsed_sniper_items)
            continue
        parsed_candidate_items = _parse_candidate_list_rows(header, rows, participation_scripts)
        if parsed_candidate_items:
            candidate_items.extend(parsed_candidate_items)
    if not candidate_items:
        return sniper_items

    sniper_by_code = {
        _normalize_stock_code(item.get("code")): item
        for item in sniper_items
        if _normalize_stock_code(item.get("code"))
    }
    merged = []
    seen_codes = set()
    for item in candidate_items:
        code = _normalize_stock_code(item.get("code"))
        sniper = sniper_by_code.get(code)
        if sniper:
            preserved = {
                key: item.get(key)
                for key in (
                    "rank",
                    "name",
                    "code",
                    "sector",
                    "conviction_reason",
                    "conviction_rule",
                    "core_identity_label",
                    "candidate_layer_label",
                    "candidate_layer",
                    "execution_eligibility",
                    "participation_script",
                )
                if item.get(key) not in (None, "")
            }
            item = {**item, **sniper, **preserved, "sector": item.get("sector") or sniper.get("sector")}
        merged.append(item)
        if code:
            seen_codes.add(code)
    for item in sniper_items:
        code = _normalize_stock_code(item.get("code"))
        if code and code not in seen_codes:
            merged.append(item)
    return merged


def _find_open_previous_case(previous_index, stock_code):
    by_stock_code = (previous_index or {}).get("by_stock_code") or {}
    records = by_stock_code.get(stock_code) or []
    for record in reversed(records):
        if not record.get("cycle_closed"):
            return record
    return None


def _copy_mentions(record):
    return [dict(item) for item in list((record or {}).get("mentions") or [])]


def _mention_identity(mention):
    mention = mention or {}
    return (
        _clean_text(mention.get("mention_trade_date")),
        _clean_text(mention.get("source_section")),
    )


def _merge_mentions_without_duplicates(previous_mentions, current_mentions):
    merged = []
    for mention in list(previous_mentions or []) + list(current_mentions or []):
        copied = dict(mention or {})
        key = _mention_identity(copied)
        replaced = False
        for index, existing in enumerate(merged):
            if _mention_identity(existing) == key:
                merged[index] = copied
                replaced = True
                break
        if replaced:
            continue
        merged.append(copied)
    return merged


def _sync_record_to_latest_remaining_mention(record, mentions):
    updated = dict(record or {})
    updated["mentions"] = list(mentions or [])
    latest = updated["mentions"][-1] if updated["mentions"] else {}
    latest_planned = latest.get("planned_participation")
    if isinstance(latest_planned, dict) and latest_planned:
        updated["planned_participation"] = latest_planned
    latest_review = latest.get("participation_review")
    if isinstance(latest_review, dict) and latest_review:
        updated["participation_review"] = dict(latest_review)
        updated["participation_review_status"] = latest_review.get("status")
    return updated


def prune_replaced_same_day_extreme_mentions(previous_index, *, trade_date="", current_codes=None):
    previous_index = previous_index or {}
    trade_date = str(trade_date or "").strip()
    if not trade_date:
        return previous_index
    current_codes = {_normalize_stock_code(code) for code in list(current_codes or []) if _normalize_stock_code(code)}
    updated = dict(previous_index)
    updated_by_stock_code = {}
    for code, records in (previous_index.get("by_stock_code") or {}).items():
        normalized_code = _normalize_stock_code(code)
        kept_records = []
        for record in list(records or []):
            mentions = list((record or {}).get("mentions") or [])
            has_stale_same_day_extreme_mention = any(
                str(mention.get("mention_trade_date") or "").strip() == trade_date
                and _mention_source_tier(mention, _record_planned_participation(record)) == "extreme_conviction"
                and normalized_code not in current_codes
                for mention in mentions
            )
            if not has_stale_same_day_extreme_mention:
                kept_records.append(record)
                continue
            kept_mentions = [
                mention
                for mention in mentions
                if not (
                    str(mention.get("mention_trade_date") or "").strip() == trade_date
                    and _mention_source_tier(mention, _record_planned_participation(record)) == "extreme_conviction"
                )
            ]
            if not kept_mentions:
                continue
            kept_records.append(_sync_record_to_latest_remaining_mention(record, kept_mentions))
        if kept_records:
            updated_by_stock_code[code] = kept_records
    updated["by_stock_code"] = updated_by_stock_code
    if "extreme_conviction_backtest_rows" in updated:
        updated["extreme_conviction_backtest_rows"] = build_extreme_conviction_backtest_rows(
            {"by_stock_code": updated_by_stock_code},
            max_rows=25,
        )
    return updated


def _prune_replaced_same_day_records(previous_index, snapshot):
    snapshot = snapshot or {}
    current_codes = {
        _normalize_stock_code(case.get("stock_code"))
        for case in list(snapshot.get("cases") or [])
        if _normalize_stock_code(case.get("stock_code"))
    }
    return prune_replaced_same_day_extreme_mentions(
        previous_index,
        trade_date=snapshot.get("trade_date"),
        current_codes=current_codes,
    )


def _cycle_day_from_dates(start_trade_date, trade_date):
    try:
        start_day = int(str(start_trade_date).replace("-", ""))
        current_day = int(str(trade_date).replace("-", ""))
    except (TypeError, ValueError):
        return 1
    if current_day <= start_day:
        return 1
    return 2


def classify_validation_state(
    *,
    sector_selected=False,
    stock_acceptance=False,
    sector_path_lost=False,
    stock_structure_broken=False,
    stock_setup_intact=True,
    sector_selection_evidence=None,
    stock_acceptance_evidence=None,
    confirmation_date=None,
    failure_reason=None,
):
    if sector_path_lost and stock_structure_broken:
        return {
            "status": "真正失败",
            "selection_confirmed_date": None,
            "selection_confirmed_evidence": None,
            "sector_selection_evidence": sector_selection_evidence,
            "stock_acceptance_evidence": stock_acceptance_evidence,
            "failure_reason": _clean_text(failure_reason, "板块路径失去选择，个股结构或承接失败"),
        }
    if sector_selected and stock_acceptance:
        sector_evidence = _clean_text(sector_selection_evidence, "所属板块被资金选择")
        stock_evidence = _clean_text(stock_acceptance_evidence, "个股承接或强度跟上")
        return {
            "status": "市场选择确认",
            "selection_confirmed_date": confirmation_date,
            "selection_confirmed_evidence": f"{sector_evidence}；{stock_evidence}",
            "sector_selection_evidence": sector_evidence,
            "stock_acceptance_evidence": stock_evidence,
        }
    return {
        "status": "等待市场选择",
        "selection_confirmed_date": None,
        "selection_confirmed_evidence": None,
        "sector_selection_evidence": sector_selection_evidence,
        "stock_acceptance_evidence": stock_acceptance_evidence,
        "stock_setup_intact": bool(stock_setup_intact),
    }


def _closed_acceptance(final_label, reason, iteration_note=None):
    return {
        "status": "closed",
        "final_label": final_label,
        "reason": reason,
        "iteration_note": iteration_note,
    }


def classify_cycle_acceptance(
    *,
    validation_status=None,
    trend_delivered=False,
    stock_setup_intact=False,
    sector_branch_selected=False,
    market_selected_other_branch=False,
    eliminated_early=False,
    continued_strength_after_elimination=False,
):
    if eliminated_early and continued_strength_after_elimination:
        return _closed_acceptance(
            "提前淘汰后继续走强",
            "样本被提前移除后仍在同周期继续走强，需要复盘淘汰条件。",
            "检查淘汰条件是否过敏。",
        )
    if validation_status == "真正失败":
        return _closed_acceptance(
            "真正失败",
            "所属方向持续失去选择，且个股自身结构或承接也失败。",
        )
    if validation_status == "市场选择确认" and trend_delivered:
        return _closed_acceptance(
            "市场选择确认后趋势兑现",
            "市场选择确认后，个股趋势继续兑现。",
        )
    if market_selected_other_branch and stock_setup_intact:
        return _closed_acceptance(
            "市场分支未选择且个股假设保留",
            "市场选择了其他分支，但个股形态假设尚未被自身走势否定。",
        )
    if validation_status == "等待市场选择" and stock_setup_intact and not sector_branch_selected:
        return _closed_acceptance(
            "等待市场选择但周期未验证",
            "个股结构仍在，但所属方向在周期内没有获得清晰选择。",
        )
    return _closed_acceptance(
        "等待市场选择但周期未验证",
        "周期结束时没有足够证据归入其他验收结论。",
    )


def _snapshot_relative_path(trade_date):
    return f"data/decision-ledger/{trade_date}.json"


def _case_index_record(case, snapshot_path, trade_date):
    planned_participation = case.get("planned_participation") or {}
    planned_participation = planned_participation if isinstance(planned_participation, dict) else {}
    source_report_path = _clean_text(case.get("source_report_path"))
    position_plan_pct = _position_plan_pct(planned_participation, case)
    cancellation_conditions = _cancellation_conditions_from_plan(planned_participation, case)
    source_dates = _normalize_source_dates(
        case,
        planned_participation,
        default_snapshot_date=trade_date,
    )
    missing_fields = _merge_missing_fields(case.get("missing_fields"))
    if position_plan_pct in (50, 100) and not planned_participation:
        missing_fields = _merge_missing_fields(missing_fields, ["planned_participation"])
    if position_plan_pct is None:
        missing_fields = _merge_missing_fields(missing_fields, ["position_plan_pct"])
    if not source_dates.get("snapshot_date"):
        missing_fields = _merge_missing_fields(missing_fields, ["snapshot_date"])
    if not cancellation_conditions and position_plan_pct in (50, 100):
        missing_fields = _merge_missing_fields(missing_fields, ["cancellation_conditions"])
    record = {
        "schema_version": case.get("schema_version") or "decision_ledger_record.v1",
        "report_date": case.get("report_date") or trade_date,
        "source_report_path": source_report_path,
        "case_id": case.get("case_id"),
        "stock_code": case.get("stock_code"),
        "stock_name": case.get("stock_name"),
        "first_seen_trade_date": case.get("first_seen_trade_date"),
        "cycle_start_trade_date": case.get("cycle_start_trade_date"),
        "cycle_day": case.get("cycle_day"),
        "cycle_length_trade_days": case.get("cycle_length_trade_days", DEFAULT_CYCLE_LENGTH_TRADE_DAYS),
        "latest_trade_date": trade_date,
        "status": (case.get("validation") or {}).get("status"),
        "snapshot_path": snapshot_path,
        "cycle_closed": (case.get("cycle_acceptance") or {}).get("status") == "closed",
        "mentions": list(case.get("mentions") or []),
        "position_plan_pct": position_plan_pct,
        "position_plan_label": _position_plan_label(position_plan_pct),
        "cancellation_conditions": cancellation_conditions,
        "source_dates": source_dates,
        "missing_fields": missing_fields,
    }
    if isinstance(planned_participation, dict) and planned_participation:
        record["planned_participation"] = planned_participation
    hypothesis = case.get("hypothesis") or {}
    if isinstance(hypothesis, dict) and hypothesis:
        record["hypothesis"] = dict(hypothesis)
    validation = case.get("validation") or {}
    if isinstance(validation, dict) and validation:
        record["validation"] = dict(validation)
    cycle_acceptance = case.get("cycle_acceptance") or {}
    if isinstance(cycle_acceptance, dict) and cycle_acceptance:
        record["cycle_acceptance"] = dict(cycle_acceptance)
    selection_result = case.get("selection_result") or {}
    if isinstance(selection_result, dict) and selection_result:
        record["selection_result"] = dict(selection_result)
    judgment_reviews = case.get("judgment_reviews") or []
    if isinstance(judgment_reviews, list) and judgment_reviews:
        record["judgment_reviews"] = [dict(item) for item in judgment_reviews if isinstance(item, dict)]
    participation_review = case.get("participation_review") or {}
    if isinstance(participation_review, dict) and participation_review:
        record["participation_review_status"] = participation_review.get("status")
        record["participation_review"] = _compact_participation_review_for_index(participation_review)
    return record


def build_decision_ledger_index(snapshot, previous_index=None):
    previous_index = _sanitize_decision_ledger_index(previous_index or {})
    snapshot = _sanitize_decision_ledger_snapshot(snapshot or {})
    trade_date = snapshot.get("trade_date")
    snapshot_path = _snapshot_relative_path(trade_date)
    available_dates = set(previous_index.get("available_trade_dates") or [])
    if trade_date:
        available_dates.add(trade_date)

    snapshots = [
        item
        for item in list(previous_index.get("snapshots") or [])
        if item.get("trade_date") != trade_date
    ]
    cases = list(snapshot.get("cases") or [])
    snapshots.append(
        {
            "trade_date": trade_date,
            "path": snapshot_path,
            "case_count": len(cases),
            "open_case_count": sum(1 for case in cases if (case.get("cycle_acceptance") or {}).get("status") != "closed"),
        }
    )
    snapshots.sort(key=lambda item: item.get("trade_date") or "")

    by_stock_code = {
        code: list(records or [])
        for code, records in (previous_index.get("by_stock_code") or {}).items()
    }
    for case in cases:
        stock_code = case.get("stock_code")
        if not stock_code:
            continue
        records = [
            record
            for record in by_stock_code.get(stock_code, [])
            if record.get("case_id") != case.get("case_id")
        ]
        records.append(_case_index_record(case, snapshot_path, trade_date))
        by_stock_code[stock_code] = records

    return {
        "artifact_version": ARTIFACT_VERSION,
        "latest_trade_date": max(available_dates) if available_dates else trade_date,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "selection_input_hash_by_trade_date": {
            **(previous_index.get("selection_input_hash_by_trade_date") or {}),
            trade_date: snapshot.get("selection_input_hash"),
        },
        "available_trade_dates": sorted(available_dates),
        "snapshots": snapshots,
        "by_stock_code": by_stock_code,
        "extreme_conviction_backtest_rows": build_extreme_conviction_backtest_rows(
            {"by_stock_code": by_stock_code},
            max_rows=25,
        ),
    }


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json_if_exists(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _postgres_database_configured():
    return (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip().startswith(("postgres://", "postgresql://"))


def _postgres_storage_required():
    return bool(
        os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1"
        or _postgres_database_configured()
    )


def _read_jsonl_if_exists(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _append_jsonl(path, rows):
    rows = [row for row in list(rows or []) if isinstance(row, dict)]
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _snapshot_final_action(snapshot):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    if snapshot.get("decision_revision_policy") == "intermediate_snapshot":
        return {}
    return _normalize_final_action_snapshot(snapshot.get("final_action"))


def _decision_summary_final_action(summary):
    summary = summary if isinstance(summary, dict) else {}
    if "final_action_label" not in summary and "final_target" not in summary:
        return {}
    return _normalize_final_action_snapshot(
        {
            "label": summary.get("final_action_label"),
            "target": summary.get("final_target") or {},
        }
    )


def _latest_final_action_from_revision_ledger(root, trade_date):
    revisions_path = Path(root) / "data" / "decision-ledger" / "revisions" / f"{_clean_text(trade_date)}.jsonl"
    for entry in reversed(_read_jsonl_if_exists(revisions_path)):
        for key in ("current_decision_excerpt", "decision_summary"):
            final_action = _decision_summary_final_action(entry.get(key))
            if final_action:
                return final_action
        action_change = entry.get("action_change") if isinstance(entry.get("action_change"), dict) else {}
        final_action = _normalize_final_action_snapshot(action_change.get("after"))
        if final_action:
            return final_action
    return {}


def _read_same_day_final_action_from_service(service, trade_date):
    if service is None:
        return {}
    for reader_name in ("read_decision_ledger_snapshot", "load_decision_ledger_snapshot"):
        reader = getattr(service, reader_name, None)
        if not callable(reader):
            continue
        try:
            snapshot = reader(trade_date)
        except TypeError:
            snapshot = reader(trade_date=trade_date)
        if not isinstance(snapshot, dict):
            continue
        if _clean_text(snapshot.get("trade_date")) and _clean_text(snapshot.get("trade_date")) != _clean_text(trade_date):
            continue
        final_action = _snapshot_final_action(snapshot)
        if final_action:
            return final_action
    return {}


def _recover_final_action_for_intermediate_snapshot(*, snapshot, previous_snapshot, root, trade_date, service=None):
    if _normalize_final_action_snapshot((snapshot or {}).get("final_action")):
        return {}
    for final_action in (
        _snapshot_final_action(previous_snapshot),
        _read_same_day_final_action_from_service(service, trade_date),
        _latest_final_action_from_revision_ledger(root, trade_date),
    ):
        if final_action:
            return final_action
    return {}


def _remove_file_if_exists(path):
    try:
        if path.exists():
            path.unlink()
            return True
    except OSError:
        return False
    return False


def _utc_timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _decision_revision_case_summary(case):
    case = case if isinstance(case, dict) else {}
    planned = case.get("planned_participation") if isinstance(case.get("planned_participation"), dict) else {}
    hypothesis = case.get("hypothesis") if isinstance(case.get("hypothesis"), dict) else {}
    return {
        "case_id": _clean_text(case.get("case_id")),
        "stock_code": _normalize_stock_code(case.get("stock_code")),
        "stock_name": _clean_text(case.get("stock_name")),
        "sector": _clean_text(case.get("sector") or hypothesis.get("sector_candidate")),
        "stock_setup": _clean_text(hypothesis.get("stock_setup")),
        "market_participation_qualification": _clean_text(case.get("market_participation_qualification")),
        "position_plan_pct": _position_plan_pct_from_value(case.get("position_plan_pct")),
        "position_plan_label": _clean_text(case.get("position_plan_label")),
        "planned_window": _clean_text(planned.get("window") or planned.get("buy_window") or planned.get("participation_window")),
        "planned_action": _clean_text(planned.get("action")),
        "mainline": _clean_text(case.get("mainline")),
        "sample_tier": _clean_text(case.get("sample_tier")),
        "trend_chain_position": _clean_text(case.get("trend_chain_position")),
        "cancellation_conditions": [
            _clean_text(item)
            for item in list(case.get("cancellation_conditions") or planned.get("cancellation_conditions") or [])
            if _clean_text(item)
        ],
        "missing_fields": [
            _clean_text(item)
            for item in list(case.get("missing_fields") or [])
            if _clean_text(item)
        ],
    }


def _normal_final_action_target(target):
    target = target if isinstance(target, dict) else {}
    stock_code = _normalize_stock_code(target.get("stock_code") or target.get("code"))
    stock_name = _clean_text(target.get("stock_name") or target.get("name"))
    if not stock_code and not stock_name:
        return {}
    normalized = {
        "stock_code": stock_code,
        "stock_name": stock_name,
    }
    sector = _clean_text(target.get("sector") or target.get("sector_candidate") or target.get("mainline"))
    if sector:
        normalized["sector"] = sector
    return normalized


def _normalize_final_action_snapshot(final_action):
    if not isinstance(final_action, dict) or not final_action:
        return {}
    target = _normal_final_action_target(final_action.get("target"))
    label = _clean_text(final_action.get("label") or final_action.get("final_action_label"))
    position_pct = _position_plan_pct_from_value(
        final_action.get("position_pct")
        if "position_pct" in final_action
        else final_action.get("target_position_pct")
    )
    if not label:
        label = _position_plan_label(position_pct) if position_pct in (0, 50, 100) else ""
    if not label and target:
        label = "50%条件执行"
    if not label:
        label = "0%不参与"
    normalized = {
        "label": label,
        "target": target,
    }
    if position_pct in (0, 50, 100):
        normalized["position_pct"] = position_pct
    source = _clean_text(final_action.get("source"))
    if source:
        normalized["source"] = source
    reason = _clean_text(final_action.get("reason"))
    if reason:
        normalized["reason"] = reason
    return normalized


def _decision_revision_summary(snapshot):
    snapshot = _sanitize_decision_ledger_snapshot(snapshot or {})
    cases = [_decision_revision_case_summary(case) for case in list(snapshot.get("cases") or [])]
    cases = [case for case in cases if case.get("case_id") or case.get("stock_code") or case.get("stock_name")]
    first_case = cases[0] if cases else {}
    first_raw_case = (snapshot.get("cases") or [{}])[0] if snapshot.get("cases") else {}
    hypothesis = first_raw_case.get("hypothesis") if isinstance(first_raw_case.get("hypothesis"), dict) else {}
    actionable_cases = [
        case
        for case in cases
        if case.get("position_plan_pct") in (50, 100)
        and case.get("market_participation_qualification") == "qualified"
    ]
    canonical_final_action = _normalize_final_action_snapshot(snapshot.get("final_action"))
    if canonical_final_action:
        final_action_label = canonical_final_action.get("label") or "0%不参与"
        final_target = canonical_final_action.get("target") or {}
    elif actionable_cases:
        final_action_label = actionable_cases[0].get("position_plan_label") or "50%条件执行"
        final_target = {
            "stock_code": actionable_cases[0].get("stock_code"),
            "stock_name": actionable_cases[0].get("stock_name"),
        }
    else:
        final_action_label = "0%不参与"
        final_target = {}
    return {
        "trade_date": _clean_text(snapshot.get("trade_date")),
        "selection_rule_version": _clean_text(snapshot.get("selection_rule_version"), SELECTION_RULE_VERSION),
        "selection_input_hash": _clean_text(snapshot.get("selection_input_hash")),
        "market_branch": _clean_text(hypothesis.get("market_branch")),
        "sector_relationship_state": _clean_text(hypothesis.get("sector_relationship_state")),
        "case_count": len(cases),
        "primary_stock": {
            "stock_code": first_case.get("stock_code"),
            "stock_name": first_case.get("stock_name"),
            "sector": first_case.get("sector"),
        } if first_case else {},
        "final_action_label": final_action_label,
        "final_target": final_target,
        "cases": cases,
    }


def _decision_summary_hash(summary):
    return _canonical_json_hash(summary or {})


def _has_decision_revision_snapshot(snapshot):
    return isinstance(snapshot, dict) and bool(_clean_text(snapshot.get("trade_date")))


def _revision_id(trade_date, sequence, summary_hash):
    return f"{_clean_text(trade_date, 'unknown')}-r{int(sequence):03d}-{_clean_text(summary_hash)[:8]}"


def _field_change(field, before, after):
    if before == after:
        return None
    return {"field": field, "before": before, "after": after}


def _case_map(summary):
    return {
        _clean_text(case.get("case_id") or case.get("stock_code") or case.get("stock_name")): case
        for case in list((summary or {}).get("cases") or [])
        if isinstance(case, dict)
    }


def _build_decision_revision_diff(previous_summary, current_summary):
    previous_summary = previous_summary if isinstance(previous_summary, dict) else {}
    current_summary = current_summary if isinstance(current_summary, dict) else {}
    changed_decisions = []
    for field in (
        "market_branch",
        "sector_relationship_state",
        "case_count",
        "primary_stock",
        "final_action_label",
        "final_target",
        "selection_input_hash",
    ):
        change = _field_change(field, previous_summary.get(field), current_summary.get(field))
        if change:
            changed_decisions.append(change)

    previous_cases = _case_map(previous_summary)
    current_cases = _case_map(current_summary)
    added_keys = [key for key in current_cases if key not in previous_cases]
    removed_keys = [key for key in previous_cases if key not in current_cases]
    changed_reasons = []
    for key in sorted(set(previous_cases) & set(current_cases)):
        before_case = previous_cases[key]
        after_case = current_cases[key]
        for field in (
            "stock_setup",
            "market_participation_qualification",
            "position_plan_label",
            "planned_window",
            "planned_action",
            "cancellation_conditions",
            "missing_fields",
        ):
            change = _field_change(field, before_case.get(field), after_case.get(field))
            if change:
                changed_reasons.append({"case_id": key, **change})

    added_evidence = [
        {
            "case_id": key,
            "stock": f"{current_cases[key].get('stock_name')}({current_cases[key].get('stock_code')})",
            "reason": current_cases[key].get("stock_setup"),
        }
        for key in added_keys
    ]
    removed_evidence = [
        {
            "case_id": key,
            "stock": f"{previous_cases[key].get('stock_name')}({previous_cases[key].get('stock_code')})",
            "reason": previous_cases[key].get("stock_setup"),
        }
        for key in removed_keys
    ]
    action_change = {
        "changed": previous_summary.get("final_action_label") != current_summary.get("final_action_label")
        or previous_summary.get("final_target") != current_summary.get("final_target"),
        "before": {
            "label": previous_summary.get("final_action_label"),
            "target": previous_summary.get("final_target") or {},
        },
        "after": {
            "label": current_summary.get("final_action_label"),
            "target": current_summary.get("final_target") or {},
        },
    }
    summary_parts = []
    if changed_decisions:
        summary_parts.append(f"决策字段变化{len(changed_decisions)}项")
    if changed_reasons:
        summary_parts.append(f"样本理由变化{len(changed_reasons)}项")
    if added_evidence:
        summary_parts.append(f"新增样本{len(added_evidence)}个")
    if removed_evidence:
        summary_parts.append(f"移除样本{len(removed_evidence)}个")
    if action_change["changed"]:
        summary_parts.append(
            f"动作由{action_change['before']['label'] or '空'}变为{action_change['after']['label'] or '空'}"
        )
    return {
        "changed_decisions": changed_decisions,
        "changed_reasons": changed_reasons,
        "added_evidence": added_evidence,
        "removed_evidence": removed_evidence,
        "action_change": action_change,
        "diff_summary": "；".join(summary_parts) if summary_parts else "结构化决策无变化",
    }


def build_decision_revision_entry(snapshot, *, previous_snapshot=None, base_revision=None, sequence=1, created_at=None):
    current_summary = _decision_revision_summary(snapshot)
    previous_summary = _decision_revision_summary(previous_snapshot) if previous_snapshot else {}
    current_hash = _decision_summary_hash(current_summary)
    trade_date = current_summary.get("trade_date")
    base_revision = base_revision if isinstance(base_revision, dict) else {}
    base_revision_id = _clean_text(base_revision.get("revision_id"))
    is_initial = not previous_summary
    entry = {
        "schema_version": DECISION_REVISION_LEDGER_SCHEMA_VERSION,
        "revision_id": _revision_id(trade_date, sequence, current_hash),
        "trade_date": trade_date,
        "created_at": created_at or _utc_timestamp(),
        "base_revision_id": "" if is_initial else base_revision_id,
        "revision_type": "initial" if is_initial else "diff",
        "current_hash": current_hash,
        "previous_hash": _decision_summary_hash(previous_summary) if previous_summary else "",
        "source": "decision_ledger_snapshot",
    }
    if is_initial:
        entry["decision_summary"] = current_summary
        entry["changed_decisions"] = []
        entry["changed_reasons"] = []
        entry["added_evidence"] = []
        entry["removed_evidence"] = []
        entry["action_change"] = {
            "changed": False,
            "before": {},
            "after": {
                "label": current_summary.get("final_action_label"),
                "target": current_summary.get("final_target") or {},
            },
        }
        entry["diff_summary"] = "首次结构化决策记录"
        return entry
    entry.update(_build_decision_revision_diff(previous_summary, current_summary))
    entry["current_decision_excerpt"] = {
        "trade_date": current_summary.get("trade_date"),
        "case_count": current_summary.get("case_count"),
        "primary_stock": current_summary.get("primary_stock"),
        "final_action_label": current_summary.get("final_action_label"),
        "final_target": current_summary.get("final_target") or {},
    }
    return entry


def write_decision_revision_ledger_artifact(snapshot, *, previous_snapshot=None, root_dir=".", created_at=None):
    root = Path(root_dir)
    snapshot = _sanitize_decision_ledger_snapshot(snapshot or {})
    trade_date = _clean_text(snapshot.get("trade_date"))
    if not trade_date:
        return {"status": "skipped", "reason": "missing_trade_date", "entries": []}
    revisions_path = root / "data" / "decision-ledger" / "revisions" / f"{trade_date}.jsonl"
    existing_entries = _read_jsonl_if_exists(revisions_path)
    current_summary = _decision_revision_summary(snapshot)
    current_hash = _decision_summary_hash(current_summary)
    if existing_entries and existing_entries[-1].get("current_hash") == current_hash:
        return {
            "status": "unchanged",
            "path": str(revisions_path),
            "entries": [],
            "latest_revision_id": existing_entries[-1].get("revision_id"),
        }

    entries_to_append = []
    sequence = len(existing_entries) + 1
    base_revision = existing_entries[-1] if existing_entries else {}
    previous_snapshot = _sanitize_decision_ledger_snapshot(previous_snapshot or {})
    if previous_snapshot.get("decision_revision_policy") == "intermediate_snapshot":
        previous_snapshot = {}
    if not _has_decision_revision_snapshot(previous_snapshot):
        previous_snapshot = {}
    previous_hash = _decision_summary_hash(_decision_revision_summary(previous_snapshot)) if previous_snapshot else ""

    if not existing_entries and previous_snapshot and previous_hash and previous_hash != current_hash:
        initial_entry = build_decision_revision_entry(
            previous_snapshot,
            sequence=sequence,
            created_at=created_at,
        )
        entries_to_append.append(initial_entry)
        base_revision = initial_entry
        sequence += 1

    previous_for_diff = previous_snapshot if previous_snapshot and previous_hash != current_hash else None
    entry = build_decision_revision_entry(
        snapshot,
        previous_snapshot=previous_for_diff,
        base_revision=base_revision,
        sequence=sequence,
        created_at=created_at,
    )
    if existing_entries and not previous_for_diff:
        entry["base_revision_id"] = _clean_text(base_revision.get("revision_id"))
        entry["revision_type"] = "diff"
        entry["previous_hash"] = _clean_text(base_revision.get("current_hash"))
        entry.update(
            {
                "changed_decisions": [
                    {
                        "field": "decision_summary",
                        "before": "previous revision summary not available in local snapshot",
                        "after": "current snapshot hash changed",
                    }
                ],
                "changed_reasons": [],
                "added_evidence": [],
                "removed_evidence": [],
                "action_change": {"changed": False, "before": {}, "after": {}},
                "diff_summary": "当前结构化决策与上一修订不同；缺少上一快照，只记录哈希变化",
            }
        )
    entries_to_append.append(entry)
    _append_jsonl(revisions_path, entries_to_append)
    return {
        "status": "written",
        "path": str(revisions_path),
        "entries": entries_to_append,
        "latest_revision_id": entries_to_append[-1].get("revision_id"),
    }


def _latest_mention(record):
    mentions = list((record or {}).get("mentions") or [])
    return mentions[-1] if mentions else {}


def _record_planned_participation(record):
    latest = _latest_mention(record)
    planned = (record or {}).get("planned_participation") or latest.get("planned_participation") or {}
    return planned if isinstance(planned, dict) else {}


def _record_is_extreme_conviction(record):
    latest = _latest_mention(record)
    planned = _record_planned_participation(record)
    source_tier = planned.get("source_tier")
    if source_tier:
        return source_tier == "extreme_conviction"
    return planned.get("source_tier") == "extreme_conviction" or "极度看好" in str(latest.get("source_section") or "")


def _mention_source_tier(mention, fallback_planned=None):
    planned = mention.get("planned_participation") or fallback_planned or {}
    if isinstance(planned, dict) and planned.get("source_tier"):
        return planned.get("source_tier")
    if "极度看好" in str(mention.get("source_section") or ""):
        return "extreme_conviction"
    return ""


def _review_is_rewritable(review):
    status = _clean_text((review or {}).get("status"))
    return not status or status in {"等待复盘", "等待窗口复盘"}


def _latest_unreviewed_extreme_mention(record, trade_date):
    if not record or record.get("cycle_closed"):
        return None
    planned = _record_planned_participation(record)
    if not planned:
        return None
    for mention in reversed(list(record.get("mentions") or [])):
        mention_date = str(mention.get("mention_trade_date") or "").strip()
        if not mention_date or not trade_date or not mention_date < str(trade_date):
            continue
        if not _review_is_rewritable(mention.get("participation_review")):
            continue
        if _mention_source_tier(mention, planned) != "extreme_conviction":
            continue
        return mention
    return None


def _record_needs_participation_review(record, trade_date):
    return _latest_unreviewed_extreme_mention(record, trade_date) is not None


def _extract_kline_rows(payload, stock_code):
    payload = payload or {}
    if isinstance(payload.get("rows"), list):
        return list(payload.get("rows") or [])
    stock_klines = payload.get("stock_klines") or payload.get("stockKlines") or {}
    if isinstance(stock_klines, dict):
        rows = stock_klines.get(stock_code) or stock_klines.get(_normalize_stock_code(stock_code)) or []
        return list(rows or []) if isinstance(rows, list) else []
    if isinstance(stock_klines, list):
        return list(stock_klines)
    return []


def _extract_minute_rows(payload, stock_code):
    payload = payload or {}
    for key in ("rows", "minute_bars", "minuteBars", "intraday_bars", "intradayBars", "minutes"):
        if isinstance(payload.get(key), list):
            return list(payload.get(key) or [])
    stock_minutes = payload.get("stock_minute_bars") or payload.get("stockMinuteBars") or payload.get("stock_minutes")
    if isinstance(stock_minutes, dict):
        rows = stock_minutes.get(stock_code) or stock_minutes.get(_normalize_stock_code(stock_code)) or []
        return list(rows or []) if isinstance(rows, list) else []
    return []


def _bar_date(row):
    return str((row or {}).get("date") or (row or {}).get("trade_date") or "").strip()


def _market_fact_from_rows(record, trade_date, rows):
    rows = sorted([row for row in list(rows or []) if _bar_date(row)], key=_bar_date)
    if not rows:
        return None
    mention = _latest_unreviewed_extreme_mention(record, trade_date) or _latest_mention(record)
    mention_date = str(mention.get("mention_trade_date") or record.get("latest_trade_date") or "").strip()
    review_bar = next((row for row in rows if _bar_date(row) == trade_date), None)
    if not review_bar:
        return None

    prev_bar = None
    if mention_date:
        prev_bar = next((row for row in rows if _bar_date(row) == mention_date), None)
    if not prev_bar:
        review_index = rows.index(review_bar)
        prev_bar = rows[review_index - 1] if review_index > 0 else None
    if not prev_bar:
        return None

    return {
        "stock_code": record.get("stock_code"),
        "stock_name": record.get("stock_name"),
        "review_trade_date": trade_date,
        "report_date": mention_date,
        "source_dates": {
            "snapshot_date": mention_date or None,
            "refill_date": None,
            "price_source_date": trade_date,
        },
        "price_bars": rows,
        "prev_close": prev_bar.get("close"),
        "open": review_bar.get("open"),
        "high": review_bar.get("high"),
        "low": review_bar.get("low"),
        "close": review_bar.get("close"),
        "volume": review_bar.get("volume"),
        "prev_volume": prev_bar.get("volume"),
    }


def _load_local_stock_kline_fact(root, record, trade_date):
    stock_code = _normalize_stock_code(record.get("stock_code"))
    if not stock_code:
        return None
    candidates = [
        root / "data" / "market-facts" / "stock-klines" / f"{trade_date}-{stock_code}.json",
    ]
    for path in candidates:
        payload = _read_json_if_exists(path)
        rows = _extract_kline_rows(payload, stock_code)
        fact = _market_fact_from_rows(record, trade_date, rows)
        if fact:
            return fact
    return None


def _load_local_stock_minute_fact(root, record, trade_date):
    stock_code = _normalize_stock_code(record.get("stock_code"))
    if not stock_code:
        return {}
    candidates = [
        root / "data" / "market-facts" / "stock-minute-bars" / f"{trade_date}-{stock_code}.json",
    ]
    for path in candidates:
        payload = _read_json_if_exists(path)
        rows = _extract_minute_rows(payload, stock_code)
        if not rows:
            continue
        fact = {"minute_bars": rows}
        reference_price = _safe_float(
            payload.get("windowReferencePrice")
            or payload.get("window_reference_price")
            or payload.get("intradayYellowLinePrice")
            or payload.get("intraday_yellow_line_price")
            or payload.get("yellowLinePrice")
            or payload.get("yellow_line_price")
        )
        if reference_price is not None:
            fact["window_reference_price"] = reference_price
        return fact
    return {}


def _fetch_stock_minute_fact(record, trade_date):
    stock_code = _normalize_stock_code(record.get("stock_code"))
    if not stock_code:
        return {}
    try:
        from market_data.tushare_minute_service import fetch_tushare_minute_bars

        rows = fetch_tushare_minute_bars(stock_code, period="5", target_date=trade_date)
    except Exception:
        rows = []
    return {"minute_bars": rows} if rows else {}


def _fetch_stock_kline_fact(record, trade_date):
    stock_code = _normalize_stock_code(record.get("stock_code"))
    mention = _latest_unreviewed_extreme_mention(record, trade_date) or _latest_mention(record)
    mention_date = str(mention.get("mention_trade_date") or record.get("latest_trade_date") or "").strip()
    if not stock_code or not mention_date:
        return None
    try:
        from market_data.daily_price_runtime import fetch_daily_price_bars

        rows = fetch_daily_price_bars(stock_code, mention_date, trade_date, prefer_fast=True)
    except Exception:
        rows = []
    return _market_fact_from_rows(record, trade_date, rows)


def _load_review_market_facts(root, trade_date, previous_index):
    facts = {}
    for records in (previous_index.get("by_stock_code") or {}).values():
        for record in list(records or []):
            if not _record_needs_participation_review(record, trade_date):
                continue
            code = _normalize_stock_code(record.get("stock_code"))
            fact = _load_local_stock_kline_fact(root, record, trade_date) or _fetch_stock_kline_fact(record, trade_date)
            if fact:
                minute_fact = _load_local_stock_minute_fact(root, record, trade_date) or _fetch_stock_minute_fact(record, trade_date)
                if minute_fact:
                    fact = {**fact, **minute_fact}
                facts[code] = fact
    return facts


def _compact_participation_review_for_index(review):
    review = review or {}
    return {
        "schema_version": review.get("schema_version"),
        "report_date": review.get("report_date"),
        "status": review.get("status"),
        "fact_status": review.get("fact_status") or _review_status_for_facts(review.get("status")),
        "review_trade_date": review.get("review_trade_date"),
        "planned_window": review.get("planned_window"),
        "participation_window_type": review.get("participation_window_type"),
        "attack_state": review.get("attack_state"),
        "matched_steps": list(review.get("matched_steps") or []),
        "evidence": review.get("evidence"),
        "reason": review.get("reason"),
        "entry_decision": review.get("entry_decision"),
        "same_day_action": review.get("same_day_action"),
        "avoid_action": review.get("avoid_action"),
        "next_action": review.get("next_action"),
        "standard_answer_basis": review.get("standard_answer_basis"),
        "market_outcome": review.get("market_outcome"),
        "fact_inputs": dict(review.get("fact_inputs") or {}),
        "performance": _normalize_performance_payload(review.get("performance")),
        "source_dates": _normalize_source_dates(review.get("source_dates") or {}),
        "missing_fields": _merge_missing_fields(review.get("missing_fields")),
    }


def _clean_markdown_cell(value, default="-"):
    text = _clean_text(value, default)
    return text.replace("|", "/") or default


def _historical_standard_action_text(value):
    text = _clean_text(value, "-")
    replacements = (
        ("开盘核心参与", "开盘核心观察"),
        ("同时成立时买", "同时成立时记录为历史预演"),
        ("买入动作", "新增参与动作"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    if text != "-" and "不作为明日新增参与依据" not in text:
        text = f"{text}；不作为明日新增参与依据"
    return text


def _is_a_kill_eliminated_record(record):
    record = record or {}
    if record.get("is_a_kill_eliminated") or record.get("a_kill_eliminated"):
        return True
    trend_fate = record.get("trend_fate") if isinstance(record.get("trend_fate"), dict) else {}
    elimination_event = trend_fate.get("elimination_event") if isinstance(trend_fate, dict) else {}
    cycle_acceptance = record.get("cycle_acceptance") if isinstance(record.get("cycle_acceptance"), dict) else {}
    texts = [
        record.get("status"),
        record.get("participation_review_status"),
        elimination_event.get("type") if isinstance(elimination_event, dict) else "",
        elimination_event.get("reason") if isinstance(elimination_event, dict) else "",
        cycle_acceptance.get("final_label") if isinstance(cycle_acceptance, dict) else "",
        cycle_acceptance.get("reason") if isinstance(cycle_acceptance, dict) else "",
    ]
    return any("A杀" in str(text or "") or str(text or "").lower() in {"a_kill", "a-kill"} for text in texts)


def _tracking_sort_key(record):
    return (
        bool(record.get("cycle_closed")),
        -int(record.get("cycle_day") or 0),
        str(record.get("cycle_start_trade_date") or ""),
        str(record.get("stock_code") or ""),
    )


def _history_action_text(value):
    text = _clean_text(value)
    if text.startswith("若已买入，"):
        text = text.replace("若已买入，", "历史复盘：", 1)
    return text


def render_extreme_conviction_tracking_lines(index, *, max_rows=8, final_action=None):
    index = index or {}
    final_target = _final_execution_target_from_action(final_action)
    rows = []
    for records in (index.get("by_stock_code") or {}).values():
        for record in list(records or []):
            if not _record_is_extreme_conviction(record):
                continue
            if record.get("cycle_closed"):
                continue
            planned = _record_planned_participation(record)
            review = record.get("participation_review") or {}
            rows.append(
                {
                    "stock_name": record.get("stock_name"),
                    "stock_code": record.get("stock_code"),
                    "cycle": f"D{record.get('cycle_day') or 1}/{record.get('cycle_length_trade_days') or DEFAULT_CYCLE_LENGTH_TRADE_DAYS}",
                    "first_seen": record.get("cycle_start_trade_date") or record.get("first_seen_trade_date"),
                    "latest": record.get("latest_trade_date"),
                    "planned_window": planned.get("participation_window"),
                    "buy_window": planned.get("buy_window"),
                    "review_status": review.get("status") or record.get("participation_review_status") or record.get("status"),
                    "next_action": review.get("next_action") or review.get("same_day_action") or "等待下一次固定交易窗口条件确认",
                    "invalidation": planned.get("ma20_invalidation") or planned.get("cancellation") or "按原计划作废条件处理",
                    "is_final_execution_target": _same_stock_code(record.get("stock_code"), final_target),
                    "_record": record,
                }
            )

    lines = ["**过程观察25日跟踪表**（只展示仍在周期内的样本）:"]
    if not rows:
        lines.append("- 暂无仍在25日周期内的过程观察样本。")
        lines.append("")
        return lines

    rows.sort(key=lambda item: _tracking_sort_key(item["_record"]))
    lines.append("| 股票 | 代码 | 周期日 | 首次入选 | 最近复盘 | 计划窗口 | 观察位窗口 | 预演复盘 | 历史复盘动作 | 作废线 |")
    lines.append("|------|------|--------|----------|----------|----------|----------|----------|------------|--------|")
    for row in rows[:max_rows]:
        lines.append(
            "| {stock_name} | {stock_code} | {cycle} | {first_seen} | {latest} | {planned_window} | {buy_window} | {review_status} | {next_action} | {invalidation} |".format(
                stock_name=_clean_markdown_cell(row.get("stock_name")),
                stock_code=_clean_markdown_cell(row.get("stock_code")),
                cycle=_clean_markdown_cell(row.get("cycle")),
                first_seen=_clean_markdown_cell(row.get("first_seen")),
                latest=_clean_markdown_cell(row.get("latest")),
                planned_window=_clean_markdown_cell(row.get("planned_window")),
                buy_window=_clean_markdown_cell(row.get("buy_window")),
                review_status=_clean_markdown_cell(row.get("review_status")),
                next_action=_clean_markdown_cell(
                    _final_execution_history_action(final_target)
                    if row.get("is_final_execution_target")
                    else _history_action_text(row.get("next_action"))
                ),
                invalidation=_clean_markdown_cell(row.get("invalidation")),
            )
        )
    lines.append("")
    return lines


def _record_first_mention_date(record):
    mentions = list((record or {}).get("mentions") or [])
    for mention in mentions:
        mention_date = _clean_text(mention.get("mention_trade_date"))
        if mention_date:
            return mention_date
    return _clean_text((record or {}).get("cycle_start_trade_date") or (record or {}).get("first_seen_trade_date"))


def _risk_reward_label(planned):
    planned = planned or {}
    state = _clean_text(planned.get("risk_reward_state"))
    ratio = _round_or_none(planned.get("risk_reward_ratio"), 2)
    if ratio is not None:
        ratio_text = f"{ratio:g}:1"
        return f"{state} {ratio_text}".strip()
    plan = _clean_text(planned.get("risk_reward_plan"))
    if plan:
        return f"{state} {plan}".strip()
    min_ratio = _round_or_none(planned.get("risk_reward_min_ratio"), 2)
    if min_ratio is not None:
        return f"{state} 默认不低于{min_ratio:g}:1".strip()
    return state or "待补充"


def _selection_quality_label(planned):
    planned = planned or {}
    level = _clean_text(planned.get("limit_up_inertia_level"), "待验证")
    probability = _clean_text(planned.get("next_day_limit_probability_band"))
    return f"{level} / {probability}" if probability else level


def _selection_result_from_mention_or_record(mention, record):
    result = (mention or {}).get("selection_result")
    if isinstance(result, dict) and result:
        return result
    result = (record or {}).get("selection_result")
    return result if isinstance(result, dict) else {}


def _selection_review_mentions(record):
    mentions = _extreme_conviction_mentions(record)
    if mentions:
        return mentions
    if not _selection_result_from_mention_or_record({}, record):
        return []
    latest = _latest_mention(record)
    return [latest] if latest else []


def _extreme_conviction_mentions(record):
    planned = _record_planned_participation(record)
    mentions = []
    seen_keys = set()
    for mention in list((record or {}).get("mentions") or []):
        if _mention_source_tier(mention, planned) != "extreme_conviction":
            continue
        key = _mention_identity(mention)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        mentions.append(mention)
    return mentions


def _mention_planned_participation(mention, record):
    planned = (mention or {}).get("planned_participation") or _record_planned_participation(record)
    return planned if isinstance(planned, dict) else {}


def _mention_participation_review(mention, record, extreme_mention_count):
    review = (mention or {}).get("participation_review") or {}
    if isinstance(review, dict) and review:
        return review
    if extreme_mention_count == 1:
        fallback = (record or {}).get("participation_review") or {}
        return fallback if isinstance(fallback, dict) else {}
    return {}


def _review_performance(review):
    return _normalize_performance_payload((review or {}).get("performance"))


def _performance_value_from_review(review, field):
    return _review_performance(review).get(field)


def _format_performance_pct(value):
    number = _safe_float(value)
    if number is None:
        return "待补事实"
    return f"{number:+.2f}%"


def _performance_missing_text(missing_fields):
    missing = _merge_missing_fields(missing_fields)
    return "、".join(missing) if missing else "-"


def _buy_point_quality_label(review):
    review = review or {}
    status = _clean_text(review.get("status"))
    decision = _clean_text(review.get("entry_decision"))
    if status == "主目标不可成交" or decision == "unavailable":
        return "主目标不可成交"
    if status == "预演作废" or decision == "skip":
        return "观察位作废"
    if status == "预演过早":
        return "观察位过早"
    if decision in {"open_buy", "ten_confirm_buy", "tail_confirm"} or status == "预演命中":
        return "观察位成立"
    if status == "错过后方案命中":
        return "错过后方案成立"
    if _review_status_for_facts(status) == "待补事实":
        return "待补事实"
    return status or "待补事实"


def _mention_tracking_record_id(mention_date, stock_code):
    return f"{_clean_text(mention_date)}:{_clean_text(stock_code)}"


def _iter_extreme_conviction_mention_coverage_rows(index, *, exclude_a_kill=True):
    index = index or {}
    for records in (index.get("by_stock_code") or {}).values():
        for record in list(records or []):
            if exclude_a_kill and _is_a_kill_eliminated_record(record):
                continue
            extreme_mentions = _extreme_conviction_mentions(record)
            if not extreme_mentions and _record_is_extreme_conviction(record):
                latest = _latest_mention(record)
                extreme_mentions = [latest] if latest else []
            for mention in extreme_mentions:
                mention_date = _clean_text(mention.get("mention_trade_date")) or _record_first_mention_date(record)
                stock_code = _clean_text(record.get("stock_code"))
                if not mention_date or not stock_code:
                    continue
                yield {
                    "record_id": _mention_tracking_record_id(mention_date, stock_code),
                    "mention_trade_date": mention_date,
                    "stock_code": stock_code,
                }


def build_decision_coverage_summary(index, *, surface="tracking", target_window_days=None, exclude_a_kill=True):
    rows = list(_iter_extreme_conviction_mention_coverage_rows(index, exclude_a_kill=exclude_a_kill))
    dates = sorted({_clean_text(row.get("mention_trade_date")) for row in rows if row.get("mention_trade_date")})
    sample_count = len({row.get("record_id") for row in rows if row.get("record_id")})
    target = int(target_window_days) if target_window_days else None
    if not sample_count:
        coverage_status = "missing"
    elif target and sample_count >= target:
        coverage_status = "covered"
    else:
        coverage_status = "partial"
    missing_fields = []
    if not dates:
        missing_fields = _merge_missing_fields(missing_fields, ["start_date", "end_date"])
    return {
        "schema_version": "decision_coverage_summary.v1",
        "surface": _clean_text(surface, "tracking"),
        "sample_count": sample_count,
        "start_date": dates[0] if dates else None,
        "end_date": dates[-1] if dates else None,
        "available_report_count": 0,
        "available_snapshot_count": 0,
        "available_replay_count": 0,
        "target_window_days": target,
        "coverage_status": coverage_status,
        "missing_fields": missing_fields,
    }


def _format_coverage_summary_line(summary, *, window_days=None):
    summary = summary or {}
    sample_count = int(summary.get("sample_count") or 0)
    start_date = _clean_text(summary.get("start_date"))
    end_date = _clean_text(summary.get("end_date"))
    if not sample_count or not start_date or not end_date:
        return "- 当前可复盘样本：待补事实。"
    parts = [f"- 当前可复盘样本：{sample_count}条，覆盖{start_date}至{end_date}。"]
    if window_days:
        parts.append(f"本表展示最近{int(window_days)}个交易日周期内样本。")
    return "".join(parts)


def _format_backtest_coverage_summary_line(summary, *, max_rows=None):
    summary = summary or {}
    sample_count = int(summary.get("sample_count") or 0)
    start_date = _clean_text(summary.get("start_date"))
    end_date = _clean_text(summary.get("end_date"))
    if not sample_count or not start_date or not end_date:
        return "- 当前可复盘样本：待补事实。"
    parts = [f"- 当前可复盘样本：{sample_count}条，覆盖{start_date}至{end_date}。"]
    if max_rows:
        parts.append(f"本表展示最近{int(max_rows)}条历史样本。")
    return "".join(parts)


def build_extreme_conviction_mention_rows(index, *, end_date="", window_days=25, exclude_a_kill=True, final_action=None):
    index = index or {}
    end_date = _clean_text(end_date or index.get("latest_trade_date"))
    final_target = _final_execution_target_from_action(final_action)
    rows = []
    for records in (index.get("by_stock_code") or {}).values():
        for record in list(records or []):
            if exclude_a_kill and _is_a_kill_eliminated_record(record):
                continue
            extreme_mentions = _extreme_conviction_mentions(record)
            if not extreme_mentions and _record_is_extreme_conviction(record):
                extreme_mentions = [_latest_mention(record)]
            if not extreme_mentions:
                continue
            extreme_mention_count = len(extreme_mentions)
            for mention in extreme_mentions:
                mention_date = _clean_text(mention.get("mention_trade_date")) or _record_first_mention_date(record)
                if end_date and mention_date and mention_date > end_date:
                    continue
                planned = _mention_planned_participation(mention, record)
                review = _mention_participation_review(mention, record, extreme_mention_count)
                stock_code = _clean_text(record.get("stock_code"))
                review_status = review.get("status") or record.get("participation_review_status") or "等待复盘"
                rows.append(
                    {
                        "record_id": _mention_tracking_record_id(mention_date, stock_code),
                        "mention_trade_date": mention_date,
                        "stock_name": record.get("stock_name"),
                        "stock_code": stock_code,
                        "rank": mention.get("rank"),
                        "rank_no": mention.get("rank"),
                        "sector_candidate": _sector_from_case_or_record(record),
                        "buy_window": planned.get("buy_window") or planned.get("participation_window"),
                        "planned_window": planned.get("participation_window"),
                        "review_status": review_status,
                        "fact_status": review.get("fact_status") or _review_status_for_facts(review_status),
                        "next_action": review.get("next_action") or review.get("same_day_action") or "等待计划窗口事实回写",
                        "invalidation": planned.get("ma20_invalidation") or planned.get("cancellation") or "按原计划作废条件处理",
                        "is_final_execution_target": _same_stock_code(record.get("stock_code"), final_target),
                        "reason": mention.get("reason") or "",
                        "source_section": mention.get("source_section") or "",
                        "is_a_kill_eliminated": _is_a_kill_eliminated_record(record),
                        "source_dates": _normalize_source_dates(record.get("source_dates") or {}, review.get("source_dates") or {}),
                        "missing_fields": _merge_missing_fields(record.get("missing_fields"), review.get("missing_fields")),
                    }
                )
    rows.sort(
        key=lambda item: (
            str(item.get("mention_trade_date") or ""),
            int(item.get("rank") or 9999),
            str(item.get("stock_code") or ""),
        )
    )
    if not rows:
        return []
    recent_dates = []
    for row in reversed(rows):
        date = row.get("mention_trade_date")
        if not date or date in recent_dates:
            continue
        recent_dates.append(date)
        if len(recent_dates) >= int(window_days or 25):
            break
    recent_date_set = set(recent_dates)
    return [row for row in rows if row.get("mention_trade_date") in recent_date_set]


def render_extreme_conviction_mention_tracking_rows(rows, *, max_rows=None, final_action=None):
    if max_rows is not None:
        rows = list(rows or [])[-int(max_rows):]
    final_target = _final_execution_target_from_action(final_action)
    lines = ["**明日极度看好近25日跟踪表**（按入选日展示，排除A杀样本）:"]
    if not rows:
        lines.append("- 暂无近25个交易日内的明日极度看好样本。")
        lines.append("")
        return lines
    lines.append("| 入选日 | 股票 | 代码 | 排名 | 所属方向 | 观察位窗口 | 复盘状态 | 历史复盘动作 | 作废线 | 记录ID |")
    lines.append("|--------|------|------|------|----------|----------|----------|------------|--------|--------|")
    for row in rows:
        lines.append(
            "| {mention_trade_date} | {stock_name} | {stock_code} | {rank} | {sector_candidate} | {buy_window} | {review_status} | {next_action} | {invalidation} | {record_id} |".format(
                mention_trade_date=_clean_markdown_cell(row.get("mention_trade_date")),
                stock_name=_clean_markdown_cell(row.get("stock_name")),
                stock_code=_clean_markdown_cell(row.get("stock_code")),
                rank=_clean_markdown_cell(row.get("rank")),
                sector_candidate=_clean_markdown_cell(row.get("sector_candidate")),
                buy_window=_clean_markdown_cell(row.get("buy_window")),
                review_status=_clean_markdown_cell(row.get("review_status")),
                next_action=_clean_markdown_cell(
                    _final_execution_history_action(final_target)
                    if row.get("is_final_execution_target")
                    else _history_action_text(row.get("next_action"))
                ),
                invalidation=_clean_markdown_cell(row.get("invalidation")),
                record_id=_clean_markdown_cell(row.get("record_id")),
            )
        )
    lines.append("")
    return lines


def render_extreme_conviction_mention_tracking_lines(index, *, end_date="", window_days=25, max_rows=None, final_action=None):
    rows = build_extreme_conviction_mention_rows(index, end_date=end_date, window_days=window_days, final_action=final_action)
    lines = render_extreme_conviction_mention_tracking_rows(rows, max_rows=max_rows, final_action=final_action)
    summary = build_decision_coverage_summary(index, surface="tracking")
    if lines:
        lines.insert(1, _format_coverage_summary_line(summary, window_days=window_days))
    return lines


def _backtest_row_review_status(review, record, *, allow_record_status=True):
    status = review.get("status")
    if not status and allow_record_status:
        status = record.get("participation_review_status")
    status = status or "等待复盘"
    return status


def build_extreme_conviction_backtest_rows(index, *, max_rows=12, final_action=None):
    index = index or {}
    final_target = _final_execution_target_from_action(final_action)
    rows = []
    for records in (index.get("by_stock_code") or {}).values():
        for record in list(records or []):
            if _is_a_kill_eliminated_record(record):
                continue
            review_mentions = _selection_review_mentions(record)
            if not review_mentions and _record_is_extreme_conviction(record):
                review_mentions = [_latest_mention(record)]
            if not review_mentions:
                continue
            for mention in review_mentions:
                planned = _mention_planned_participation(mention, record)
                review = _mention_participation_review(mention, record, len(review_mentions))
                selection_result = _selection_result_from_mention_or_record(mention, record)
                performance = _review_performance(review)
                source_dates = _normalize_source_dates(record.get("source_dates") or {}, review.get("source_dates") or {})
                missing_fields = _merge_missing_fields(record.get("missing_fields"), review.get("missing_fields"))
                if not source_dates.get("price_source_date") and any(performance.get(field) is not None for field in _PERFORMANCE_FIELDS):
                    missing_fields = _merge_missing_fields(missing_fields, ["price_source_date"])
                for field in _PERFORMANCE_FIELDS:
                    if performance.get(field) is None:
                        missing_fields = _merge_missing_fields(missing_fields, [field])
                review_status = _backtest_row_review_status(
                    review,
                    record,
                    allow_record_status=bool(review) or len(review_mentions) == 1,
                )
                rows.append(
                    {
                        "mention_trade_date": _clean_text(mention.get("mention_trade_date"))
                        or _record_first_mention_date(record),
                        "stock_name": record.get("stock_name"),
                        "stock_code": record.get("stock_code"),
                        "rank": mention.get("rank"),
                        "source_section": mention.get("source_section") or "",
                        "reason": mention.get("reason") or "",
                        "sector_candidate": _sector_from_case_or_record(record),
                        "selection_quality": _selection_quality_label(planned),
                        "buy_window": planned.get("buy_window") or planned.get("participation_window"),
                        "risk_reward": _risk_reward_label(planned),
                        "buy_point_quality": _buy_point_quality_label(review),
                        "review_status": review_status,
                        "fact_status": review.get("fact_status") or _review_status_for_facts(review_status),
                        "standard_action": review.get("same_day_action") or review.get("next_action") or "等待计划窗口事实回写",
                        "market_outcome": review.get("market_outcome") or "",
                        "selection_result_status": selection_result.get("status") or "待验证",
                        "selection_result_evidence": selection_result.get("evidence") or "",
                        "selection_result_lesson": selection_result.get("lesson") or "",
                        "position_plan_pct": _position_plan_pct(planned, record),
                        "position_plan_label": _position_plan_label(_position_plan_pct(planned, record)),
                        "is_final_execution_target": _same_stock_code(record.get("stock_code"), final_target),
                        "source_dates": source_dates,
                        "price_source_date": source_dates.get("price_source_date"),
                        "missing_fields": missing_fields,
                        "return_1d_pct": performance.get("return_1d_pct"),
                        "return_3d_pct": performance.get("return_3d_pct"),
                        "return_5d_pct": performance.get("return_5d_pct"),
                        "max_drawdown_5d_pct": performance.get("max_drawdown_5d_pct"),
                    }
                )
    rows.sort(
        key=lambda item: (
            str(item.get("mention_trade_date") or ""),
            str(item.get("stock_code") or ""),
        ),
        reverse=True,
    )
    return rows[:max_rows]


def render_extreme_conviction_backtest_lines(index, *, max_rows=12, final_action=None):
    rows = build_extreme_conviction_backtest_rows(index, max_rows=max_rows, final_action=final_action)
    final_target = _final_execution_target_from_action(final_action)
    lines = ["**重点观察历史回测表**（拆分选股样本、观察位质量、执行复盘）:"]
    if not rows:
        lines.append("- 暂无可复盘的重点观察历史样本。")
        lines.append("")
        return lines

    summary = build_decision_coverage_summary(index, surface="backtest")
    lines.append(_format_backtest_coverage_summary_line(summary, max_rows=max_rows))
    lines.append("> 历史回测表仅记录过去预演，不作为明日新增参与依据。")
    lines.append("")
    lines.append("| 入选日 | 股票 | 代码 | 选股样本 | 识别评价 | 观察位窗口 | 盈亏比 | 观察位质量 | 执行复盘 | 后续1日 | 后续3日 | 后续5日 | 最大回撤5日 | 来源日期 | 缺失字段 | 历史标准动作 |")
    lines.append("|--------|------|------|----------|----------|----------|--------|----------|----------|----------|----------|----------|------------|----------|----------|----------|")
    for row in rows:
        lines.append(
            "| {mention_trade_date} | {stock_name} | {stock_code} | {selection_quality} | {selection_result_status} | {buy_window} | {risk_reward} | {buy_point_quality} | {review_status} | {return_1d_pct} | {return_3d_pct} | {return_5d_pct} | {max_drawdown_5d_pct} | {price_source_date} | {missing_fields} | {standard_action} |".format(
                mention_trade_date=_clean_markdown_cell(row.get("mention_trade_date")),
                stock_name=_clean_markdown_cell(row.get("stock_name")),
                stock_code=_clean_markdown_cell(row.get("stock_code")),
                selection_quality=_clean_markdown_cell(
                    "明日执行对象"
                    if row.get("is_final_execution_target")
                    else row.get("selection_quality")
                ),
                selection_result_status=_clean_markdown_cell(row.get("selection_result_status")),
                buy_window=_clean_markdown_cell(row.get("buy_window")),
                risk_reward=_clean_markdown_cell(row.get("risk_reward")),
                buy_point_quality=_clean_markdown_cell(row.get("buy_point_quality")),
                review_status=_clean_markdown_cell(row.get("review_status")),
                return_1d_pct=_clean_markdown_cell(_format_performance_pct(row.get("return_1d_pct"))),
                return_3d_pct=_clean_markdown_cell(_format_performance_pct(row.get("return_3d_pct"))),
                return_5d_pct=_clean_markdown_cell(_format_performance_pct(row.get("return_5d_pct"))),
                max_drawdown_5d_pct=_clean_markdown_cell(_format_performance_pct(row.get("max_drawdown_5d_pct"))),
                price_source_date=_clean_markdown_cell(row.get("price_source_date") or (row.get("source_dates") or {}).get("price_source_date") or "待补事实"),
                missing_fields=_clean_markdown_cell(_performance_missing_text(row.get("missing_fields"))),
                standard_action=_clean_markdown_cell(
                    _final_execution_history_action(final_target)
                    if row.get("is_final_execution_target")
                    else _historical_standard_action_text(row.get("standard_action"))
                ),
            )
        )
    lines.append("")
    return lines


def _previous_trade_date_from_index(index, trade_date):
    dates = [
        _clean_text(item)
        for item in list((index or {}).get("available_trade_dates") or [])
        if _clean_text(item) and _clean_text(item) < _clean_text(trade_date)
    ]
    return max(dates) if dates else ""


def _report_paths_for_trade_date(root, trade_date):
    return [
        root / "reports" / "replay" / f"{trade_date}_A股日报_完整版_replay.md",
        root / "reports" / f"{trade_date}_A股日报_完整版.md",
    ]


def _load_markdown_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _parse_stock_labels_from_text(text):
    candidates = []
    for part in re.split(r"[、,，/]+", str(text or "")):
        part = _clean_text(part)
        if not part or part == "待补事实":
            continue
        match = re.search(r"(.+?)[(（]\s*(\d{6})\s*[)）]", part)
        if match:
            name = _clean_text(match.group(1))
            code = _normalize_stock_code(match.group(2))
            candidates.append({"stock_name": name, "stock_code": code, "label": f"{name}({code})"})
        else:
            candidates.append({"stock_name": part, "stock_code": "", "label": part})
    return candidates


def _parse_today_judgments_from_markdown(markdown):
    lines = str(markdown or "").splitlines()
    result = {}
    in_today_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### ") and "今日判断" in stripped:
            in_today_section = True
            continue
        if in_today_section and stripped.startswith("### "):
            break
        if not in_today_section or not stripped.startswith("|"):
            continue
        cells = _split_markdown_row(stripped)
        if len(cells) < 2 or cells[0] == "判断项" or set(cells[0]) <= {"-"}:
            continue
        judgment_type = _JUDGMENT_LABEL_TO_TYPE.get(cells[0])
        if not judgment_type:
            continue
        value = _clean_text(cells[1])
        if judgment_type == "core_candidate":
            result[judgment_type] = {"raw": value, "candidates": _parse_stock_labels_from_text(value)}
        else:
            result[judgment_type] = value
    return result


def _load_previous_today_judgments(root, previous_date):
    for path in _report_paths_for_trade_date(root, previous_date):
        parsed = _parse_today_judgments_from_markdown(_load_markdown_text(path))
        if parsed:
            return parsed
    return {}


def _snapshot_paths_for_trade_date(root, trade_date):
    return [
        root / "snapshots" / "replay" / f"{trade_date}_replay.json",
        root / "snapshots" / f"{trade_date}.json",
    ]


def _load_snapshot_data_for_trade_date(root, trade_date):
    for path in _snapshot_paths_for_trade_date(root, trade_date):
        payload = _read_json_if_exists(path)
        if not payload:
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if isinstance(data, dict):
            return data
    return {}


def _normalize_market_state_bucket(value):
    text = _clean_text(value)
    if not text:
        return ""
    if text in _MARKET_STATE_BUCKETS:
        return text
    if "冰点" in text:
        return "冰点"
    if any(token in text for token in ("退潮", "撤退", "收缩防守", "防守", "风险释放", "禁止参与")):
        return "退潮"
    if "修复" in text:
        return "修复"
    if any(token in text for token in ("进攻", "爆发", "主升", "扩张", "expand")):
        return "进攻"
    if any(token in text for token in ("混沌", "轮动", "无确认主线", "多方向")):
        return "混沌"
    return ""


def _is_no_confirmed_mainline(value):
    text = _clean_text(value)
    if not text:
        return True
    if text in _NO_CONFIRMED_MAINLINE_LABELS:
        return True
    return any(token in text for token in ("无确认主线", "暂无明确主线", "主线待确认", "资金未明显胜出", "多方向局部活跃"))


def _normalize_mainline_judgment(value):
    text = _clean_text(value)
    return "无确认主线" if _is_no_confirmed_mainline(text) else text


def _snapshot_mainline_summary(snapshot_data):
    market_research = snapshot_data.get("market_research_snapshot") if isinstance(snapshot_data.get("market_research_snapshot"), dict) else {}
    summary = snapshot_data.get("mainline_turnover_summary") if isinstance(snapshot_data.get("mainline_turnover_summary"), dict) else {}
    if not summary and isinstance(market_research.get("mainline_turnover_summary"), dict):
        summary = market_research.get("mainline_turnover_summary")
    return summary or {}


def _actual_mainline_from_snapshot_data(snapshot_data):
    snapshot_data = snapshot_data or {}
    summary = _snapshot_mainline_summary(snapshot_data)
    attack = summary.get("mainline_attack_evidence_summary") if isinstance(summary.get("mainline_attack_evidence_summary"), dict) else {}
    current = _clean_text(summary.get("current_mainline") or summary.get("primary_mainline") or attack.get("primary_line"))
    if current:
        return current
    attack_state = _clean_text(attack.get("attack_state"))
    summary_text = "；".join(
        _clean_text(summary.get(key))
        for key in ("conclusion", "data_text", "action_text")
        if _clean_text(summary.get(key))
    )
    if attack_state in {"chaotic_rotation", "no_mainline"} or _is_no_confirmed_mainline(summary_text):
        return "无确认主线"
    market_research = snapshot_data.get("market_research_snapshot") if isinstance(snapshot_data.get("market_research_snapshot"), dict) else {}
    record = (
        snapshot_data.get("current_mainline_history_record")
        if isinstance(snapshot_data.get("current_mainline_history_record"), dict)
        else market_research.get("current_mainline_history_record")
        if isinstance(market_research.get("current_mainline_history_record"), dict)
        else {}
    )
    return _clean_text(record.get("primary_mainline") or record.get("leading_line"))


def _actual_market_state_from_snapshot_data(snapshot_data):
    snapshot_data = snapshot_data or {}
    market_research = snapshot_data.get("market_research_snapshot") if isinstance(snapshot_data.get("market_research_snapshot"), dict) else {}
    state_snapshot = snapshot_data.get("market_state_snapshot") if isinstance(snapshot_data.get("market_state_snapshot"), dict) else {}
    state_machine = market_research.get("state_machine") if isinstance(market_research.get("state_machine"), dict) else {}
    for value in (
        state_snapshot.get("pulse_stage"),
        state_snapshot.get("energy_state"),
        state_snapshot.get("operation_state"),
        state_machine.get("pulse_stage"),
        state_machine.get("energy_state"),
        state_machine.get("operation_state"),
        snapshot_data.get("market_state"),
        market_research.get("market_state"),
    ):
        bucket = _normalize_market_state_bucket(value)
        if bucket:
            return bucket
    summary = _snapshot_mainline_summary(snapshot_data)
    attack = summary.get("mainline_attack_evidence_summary") if isinstance(summary.get("mainline_attack_evidence_summary"), dict) else {}
    if _clean_text(attack.get("attack_state")) == "chaotic_rotation":
        return "混沌"
    return ""


def _iter_stock_visibility_items(snapshot_data, snapshot):
    snapshot_data = snapshot_data or {}
    for case in list((snapshot or {}).get("cases") or []):
        if isinstance(case, dict):
            yield {"code": case.get("stock_code"), "name": case.get("stock_name"), "source": "今日核心候选"}
    market_research = snapshot_data.get("market_research_snapshot") if isinstance(snapshot_data.get("market_research_snapshot"), dict) else {}
    for container in (snapshot_data, market_research):
        for field in _CANDIDATE_VISIBILITY_FIELDS:
            value = container.get(field) if isinstance(container, dict) else None
            if isinstance(value, dict):
                items = [value]
            else:
                items = list(value or []) if isinstance(value, list) else []
            for item in items:
                if isinstance(item, dict):
                    yield {**item, "source": field}


def _stock_item_code(item):
    return _normalize_stock_code((item or {}).get("code") or (item or {}).get("stock_code") or (item or {}).get("代码"))


def _stock_item_name(item):
    return _clean_text((item or {}).get("name") or (item or {}).get("stock_name") or (item or {}).get("名称"))


def _candidate_code(candidate):
    return _normalize_stock_code((candidate or {}).get("stock_code") or (candidate or {}).get("code"))


def _candidate_name(candidate):
    return _clean_text((candidate or {}).get("stock_name") or (candidate or {}).get("name"))


def _candidate_label(candidate):
    candidate = candidate or {}
    label = _clean_text(candidate.get("label"))
    if label:
        return label
    code = _candidate_code(candidate)
    name = _candidate_name(candidate)
    return f"{name}({code})" if name and code else name or code


def _stock_item_matches_candidate(item, candidate):
    code = _stock_item_code(item)
    name = _stock_item_name(item)
    candidate_code = _candidate_code(candidate)
    candidate_name = _candidate_name(candidate)
    return bool(
        (code and candidate_code and code == candidate_code)
        or (name and candidate_name and name == candidate_name)
    )


def _collect_visible_candidate_labels(snapshot_data, snapshot, candidates):
    labels = []
    fact_available = False
    for item in _iter_stock_visibility_items(snapshot_data, snapshot):
        fact_available = True
        code = _stock_item_code(item)
        name = _stock_item_name(item)
        if any(_stock_item_matches_candidate(item, candidate) for candidate in list(candidates or [])):
            label = f"{name}({code})" if name and code else name or code
            source = _clean_text(item.get("source"))
            text = f"{label}进入{source}" if source else f"{label}进入资金视野"
            if text not in labels:
                labels.append(text)
    return labels, fact_available


def _candidate_review_fact(candidate, review_market_facts_by_stock_code=None):
    code = _candidate_code(candidate)
    normalized_facts = {
        _normalize_stock_code(key): dict(value or {})
        for key, value in (review_market_facts_by_stock_code or {}).items()
        if _normalize_stock_code(key) and isinstance(value, dict)
    }
    if code and code in normalized_facts:
        return normalized_facts[code]
    name = _candidate_name(candidate)
    for fact in normalized_facts.values():
        fact_name = _clean_text(fact.get("stock_name") or fact.get("name"))
        if name and fact_name == name:
            return fact
    return {}


def _existing_participation_review_facts_by_stock_code(previous_index, previous_date, trade_date):
    facts = {}
    for code, records in (previous_index or {}).get("by_stock_code", {}).items():
        normalized_code = _normalize_stock_code(code)
        if not normalized_code:
            continue
        for record in list(records or []):
            stock_name = _clean_text((record or {}).get("stock_name"))
            for mention in list((record or {}).get("mentions") or []):
                if _clean_text((mention or {}).get("mention_trade_date")) != _clean_text(previous_date):
                    continue
                review = (mention or {}).get("participation_review")
                if not isinstance(review, dict) or not review:
                    continue
                review_trade_date = _clean_text(review.get("review_trade_date"))
                if review_trade_date and review_trade_date != _clean_text(trade_date):
                    continue
                facts[normalized_code] = {
                    "stock_code": normalized_code,
                    "stock_name": stock_name,
                    "participation_review": dict(review),
                    "status": review.get("status"),
                    "performance": review.get("performance"),
                    "missing_fields": review.get("missing_fields"),
                }
    return facts


def _merge_candidate_review_facts(existing_facts, review_market_facts_by_stock_code=None):
    facts = {
        _normalize_stock_code(code): dict(fact or {})
        for code, fact in (existing_facts or {}).items()
        if _normalize_stock_code(code) and isinstance(fact, dict)
    }
    for code, fact in (review_market_facts_by_stock_code or {}).items():
        normalized_code = _normalize_stock_code(code)
        if normalized_code and isinstance(fact, dict):
            facts[normalized_code] = dict(fact)
    return facts


def _performance_from_candidate_fact(fact):
    fact = fact or {}
    review = fact.get("participation_review") if isinstance(fact.get("participation_review"), dict) else {}
    if review:
        return _normalize_performance_payload(review.get("performance"))
    performance, _source_dates, _missing_fields = _review_performance_from_market_fact(
        fact,
        prev_close=_safe_float(fact.get("prev_close")),
        close_price=_safe_float(fact.get("close")),
        low_price=_safe_float(fact.get("low")),
    )
    return performance


def _core_candidate_primary_outcome(candidate, review_market_facts_by_stock_code=None):
    fact = _candidate_review_fact(candidate, review_market_facts_by_stock_code)
    if not fact:
        return {"fact_available": False}
    review = fact.get("participation_review") if isinstance(fact.get("participation_review"), dict) else {}
    status = _clean_text(
        fact.get("status")
        or fact.get("review_status")
        or fact.get("participation_review_status")
        or review.get("status")
        or review.get("review_status")
    )
    performance = _performance_from_candidate_fact({**fact, **review} if review else fact)
    return_1d = performance.get("return_1d_pct")
    drawdown = performance.get("max_drawdown_5d_pct")
    failed = bool(
        status in _CORE_CANDIDATE_MISS_STATUSES
        or (_safe_float(return_1d) is not None and _safe_float(return_1d) <= _CORE_CANDIDATE_NEGATIVE_RETURN_PCT)
        or (_safe_float(drawdown) is not None and _safe_float(drawdown) <= _CORE_CANDIDATE_HARD_DRAWDOWN_PCT)
    )
    supported = bool(status in _CORE_CANDIDATE_HIT_STATUSES or (_safe_float(return_1d) is not None and _safe_float(return_1d) >= 0))
    return {
        "fact_available": True,
        "status": status,
        "return_1d_pct": return_1d,
        "max_drawdown_5d_pct": drawdown,
        "failed": failed,
        "supported": supported,
    }


def _format_signed_pct(value):
    number = _safe_float(value)
    return "" if number is None else f"{number:+.2f}%"


def _format_primary_candidate_outcome(candidate, outcome):
    label = _candidate_label(candidate)
    if not outcome.get("fact_available"):
        return ""
    parts = [f"主目标{label}"]
    return_1d = _format_signed_pct(outcome.get("return_1d_pct"))
    drawdown = _format_signed_pct(outcome.get("max_drawdown_5d_pct"))
    if return_1d:
        parts.append(f"次日{return_1d}")
    if drawdown:
        parts.append(f"最低{drawdown}")
    status = _clean_text(outcome.get("status"))
    if status and not return_1d and not drawdown:
        parts.append(status)
    if len(parts) == 1:
        parts.append("次日表现待补事实")
    return parts[0] + "，".join(parts[1:])


def _stock_item_rank(item):
    rank = _safe_float((item or {}).get("rank") or (item or {}).get("排名"))
    return int(rank) if rank is not None else None


def _stock_item_change_pct(item):
    for key in ("change_pct", "pct_chg", "涨跌幅"):
        value = _safe_float((item or {}).get(key))
        if value is not None:
            return value
    return None


def _stock_item_tags(item):
    item = item or {}
    tags = []
    for key in ("concepts", "tags", "status_tags", "related_plates", "plates"):
        value = item.get(key)
        if isinstance(value, list):
            tags.extend(_clean_text(entry) for entry in value if _clean_text(entry))
        elif _clean_text(value):
            tags.append(_clean_text(value))
    for key in ("sector", "plate_name", "concept", "concept_name"):
        value = _clean_text(item.get(key))
        if value:
            tags.append(value)
    return {tag for tag in tags if tag and tag not in _NON_SECTOR_LABELS}


def _candidate_visibility_profile(snapshot_data, snapshot, candidate):
    ranks = []
    tags = set()
    for item in _iter_stock_visibility_items(snapshot_data, snapshot):
        if not _stock_item_matches_candidate(item, candidate):
            continue
        rank = _stock_item_rank(item)
        if rank is not None:
            ranks.append(rank)
        tags.update(_stock_item_tags(item))
    return {"rank": min(ranks) if ranks else None, "tags": tags}


def _iter_nested_stock_items(value):
    if isinstance(value, dict):
        if _stock_item_code(value) or _stock_item_name(value):
            yield value
        for child in value.values():
            yield from _iter_nested_stock_items(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nested_stock_items(item)


def _stock_change_pct_from_snapshot(snapshot_data, code, trade_date):
    code = _normalize_stock_code(code)
    if not code:
        return None
    dated = []
    undated = []
    for item in _iter_nested_stock_items(snapshot_data):
        if _stock_item_code(item) != code:
            continue
        change_pct = _stock_item_change_pct(item)
        if change_pct is None:
            continue
        item_date = _clean_text(item.get("trade_date") or item.get("source_date") or item.get("query_date"))
        if item_date == _clean_text(trade_date):
            dated.append(change_pct)
        else:
            undated.append(change_pct)
    values = dated or undated
    return max(values, key=lambda number: abs(number)) if values else None


def _find_stronger_same_theme_leader(snapshot_data, snapshot, primary_candidate, candidates, trade_date):
    primary_profile = _candidate_visibility_profile(snapshot_data, snapshot, primary_candidate)
    primary_rank = primary_profile.get("rank")
    primary_tags = primary_profile.get("tags") or set()
    if primary_rank is None or not primary_tags:
        return {}
    candidate_codes = {_candidate_code(candidate) for candidate in list(candidates or []) if _candidate_code(candidate)}
    best = None
    for item in _iter_stock_visibility_items(snapshot_data, snapshot):
        code = _stock_item_code(item)
        rank = _stock_item_rank(item)
        tags = _stock_item_tags(item)
        if not code or code in candidate_codes or rank is None or rank >= primary_rank:
            continue
        if not (tags & primary_tags):
            continue
        change_pct = _stock_item_change_pct(item)
        if change_pct is None:
            change_pct = _stock_change_pct_from_snapshot(snapshot_data, code, trade_date)
        candidate = {
            "code": code,
            "name": _stock_item_name(item),
            "rank": rank,
            "change_pct": change_pct,
        }
        if best is None or rank < best.get("rank", 999999):
            best = candidate
    return best or {}


def _format_stronger_leader(leader):
    if not leader:
        return ""
    label = f"{leader.get('name')}({leader.get('code')})" if leader.get("name") and leader.get("code") else leader.get("name") or leader.get("code")
    change_pct = _format_signed_pct(leader.get("change_pct"))
    rank = leader.get("rank")
    rank_text = f"，热榜第{rank}" if rank is not None else ""
    return f"更强同方向：{label}{change_pct}{rank_text}"


def _build_core_candidate_review(candidates, visible_labels, snapshot_data, snapshot, previous_date, trade_date, review_market_facts_by_stock_code=None):
    primary = candidates[0] if candidates else {}
    primary_label = _candidate_label(primary)
    primary_visible_labels, _primary_visibility_available = _collect_visible_candidate_labels(snapshot_data, snapshot, [primary])
    primary_outcome = _core_candidate_primary_outcome(primary, review_market_facts_by_stock_code)
    leader = _find_stronger_same_theme_leader(snapshot_data, snapshot, primary, candidates, trade_date)
    actual_parts = []
    primary_outcome_text = _format_primary_candidate_outcome(primary, primary_outcome)
    if primary_outcome_text:
        actual_parts.append(primary_outcome_text)
    elif primary_visible_labels:
        actual_parts.append("、".join(primary_visible_labels))
    elif primary_label:
        actual_parts.append(f"{primary_label}未进入资金视野")
    leader_text = _format_stronger_leader(leader)
    if leader_text:
        actual_parts.append(leader_text)
    if visible_labels:
        actual_parts.append("可见候选：" + "、".join(visible_labels))
    actual = "；".join(actual_parts) if actual_parts else "待补事实"
    expected = "、".join(_candidate_label(item) for item in candidates if item)
    if primary_outcome.get("failed"):
        is_correct = False
        evidence = "主目标次日承接失败，备用/跟风进入资金视野不能抵消核心候选错误"
        mistake = evidence
    elif primary_visible_labels:
        is_correct = True
        evidence = "主目标进入次日资金视野，判断成立"
        mistake = ""
    else:
        is_correct = False
        evidence = "主目标没有进入次日资金视野，备用/跟风不能抵消核心候选错误"
        mistake = evidence
    return _resolved_judgment_review(
        "core_candidate",
        previous_date,
        trade_date,
        expected,
        actual,
        is_correct,
        evidence=evidence,
        mistake=mistake,
    )


def _mainline_judgment_correct(expected, actual):
    expected = _normalize_mainline_judgment(expected)
    actual = _normalize_mainline_judgment(actual)
    if not expected or not actual:
        return None
    if _is_no_confirmed_mainline(expected) or _is_no_confirmed_mainline(actual):
        return _is_no_confirmed_mainline(expected) and _is_no_confirmed_mainline(actual)
    return expected == actual or expected in actual or actual in expected


def _resolved_judgment_review(judgment_type, previous_date, trade_date, expected, actual, is_correct, evidence="", mistake=""):
    review = {
        "judgment_type": judgment_type,
        "report_date": previous_date,
        "review_trade_date": trade_date,
        "expected": expected,
        "actual": actual,
        "is_correct": bool(is_correct),
        "evidence": evidence,
        "source_dates": {
            "snapshot_date": previous_date,
            "refill_date": trade_date,
            "price_source_date": trade_date,
        },
    }
    if not is_correct:
        review["mistake"] = mistake or "判断未被次日事实验证"
    return review


def _build_daily_judgment_reviews(previous_judgments, snapshot_data, snapshot, previous_date, trade_date, review_market_facts_by_stock_code=None):
    reviews = []

    expected_market = _normalize_market_state_bucket(previous_judgments.get("market_state"))
    actual_market = _actual_market_state_from_snapshot_data(snapshot_data)
    if expected_market and actual_market:
        reviews.append(
            _resolved_judgment_review(
                "market_state",
                previous_date,
                trade_date,
                expected_market,
                actual_market,
                expected_market == actual_market,
                evidence=f"次日市场状态归一为{actual_market}",
                mistake=f"预判{expected_market}，次日实际为{actual_market}",
            )
        )

    expected_mainline = _normalize_mainline_judgment(previous_judgments.get("mainline"))
    actual_mainline = _actual_mainline_from_snapshot_data(snapshot_data)
    mainline_correct = _mainline_judgment_correct(expected_mainline, actual_mainline)
    if mainline_correct is not None:
        normalized_actual = _normalize_mainline_judgment(actual_mainline)
        reviews.append(
            _resolved_judgment_review(
                "mainline",
                previous_date,
                trade_date,
                expected_mainline,
                normalized_actual,
                mainline_correct,
                evidence=f"次日主线结论：{normalized_actual}",
                mistake="资金第二天没有继续选择预判方向",
            )
        )

    core_payload = previous_judgments.get("core_candidate") if isinstance(previous_judgments.get("core_candidate"), dict) else {}
    candidates = list(core_payload.get("candidates") or [])
    visible_labels, visibility_fact_available = _collect_visible_candidate_labels(snapshot_data, snapshot, candidates)
    if candidates and visibility_fact_available:
        reviews.append(
            _build_core_candidate_review(
                candidates,
                visible_labels,
                snapshot_data,
                snapshot,
                previous_date,
                trade_date,
                review_market_facts_by_stock_code=review_market_facts_by_stock_code,
            )
        )

    return reviews


def _record_has_extreme_mention_on_date(record, trade_date):
    planned = _record_planned_participation(record)
    for mention in list((record or {}).get("mentions") or []):
        if _clean_text((mention or {}).get("mention_trade_date")) != _clean_text(trade_date):
            continue
        if _mention_source_tier(mention or {}, planned) == "extreme_conviction":
            return True
    return False


def _review_report_date(review):
    return _clean_text((review or {}).get("report_date") or (review or {}).get("date"))


def _has_resolved_judgment_review(record, judgment_type, report_date):
    for item in list((record or {}).get("judgment_reviews") or []):
        if _clean_text((item or {}).get("judgment_type")) != judgment_type:
            continue
        if _review_report_date(item) != _clean_text(report_date):
            continue
        if item.get("is_correct") is not None and not item.get("missing_fields"):
            return True
    return False


def _same_judgment_review_slot(item, review):
    return (
        _clean_text((item or {}).get("judgment_type")) == _clean_text((review or {}).get("judgment_type"))
        and _review_report_date(item) == _clean_text((review or {}).get("report_date"))
    )


def _merge_judgment_reviews(record, reviews):
    existing = [dict(item) for item in list((record or {}).get("judgment_reviews") or []) if isinstance(item, dict)]
    merged = []
    for item in existing:
        should_replace = any(_same_judgment_review_slot(item, review) for review in reviews)
        if not should_replace:
            merged.append(item)
    for review in reviews:
        if any(_same_judgment_review_slot(item, review) for item in merged):
            continue
        merged.append(dict(review))
    return merged


def _apply_daily_judgment_reviews_to_previous_index(previous_index, trade_date, root, snapshot, review_market_facts_by_stock_code=None):
    previous_index = previous_index or {}
    previous_date = _previous_trade_date_from_index(previous_index, trade_date)
    if not previous_date:
        return previous_index
    previous_judgments = _load_previous_today_judgments(root, previous_date)
    if not previous_judgments:
        return previous_index
    snapshot_data = _load_snapshot_data_for_trade_date(root, trade_date)
    if not snapshot_data:
        return previous_index
    candidate_review_facts = _merge_candidate_review_facts(
        _existing_participation_review_facts_by_stock_code(previous_index, previous_date, trade_date),
        review_market_facts_by_stock_code,
    )
    reviews = _build_daily_judgment_reviews(
        previous_judgments,
        snapshot_data,
        snapshot,
        previous_date,
        trade_date,
        review_market_facts_by_stock_code=candidate_review_facts,
    )
    if not reviews:
        return previous_index

    updated_index = dict(previous_index)
    updated_by_stock_code = {}
    for code, records in (previous_index.get("by_stock_code") or {}).items():
        updated_records = []
        for record in list(records or []):
            if _record_has_extreme_mention_on_date(record, previous_date):
                updated_records.append(
                    {
                        **record,
                        "latest_trade_date": trade_date,
                        "judgment_reviews": _merge_judgment_reviews(record, reviews),
                    }
                )
            else:
                updated_records.append(record)
        updated_by_stock_code[code] = updated_records
    updated_index["by_stock_code"] = updated_by_stock_code
    return updated_index


def _attach_review_to_latest_prior_mention(record, trade_date, review):
    mentions = [dict(item) for item in list((record or {}).get("mentions") or [])]
    compact_review = _compact_participation_review_for_index(review)
    planned = _record_planned_participation(record)
    for index in range(len(mentions) - 1, -1, -1):
        mention_date = str(mentions[index].get("mention_trade_date") or "").strip()
        if (
            mention_date
            and str(mention_date) < str(trade_date)
            and _review_is_rewritable(mentions[index].get("participation_review"))
            and _mention_source_tier(mentions[index], planned) == "extreme_conviction"
        ):
            mentions[index]["participation_review"] = compact_review
            return mentions
    return mentions


def _apply_participation_reviews_to_previous_index(previous_index, trade_date, review_market_facts_by_stock_code=None):
    previous_index = previous_index or {}
    facts_by_code = {
        _normalize_stock_code(code): dict(fact or {})
        for code, fact in (review_market_facts_by_stock_code or {}).items()
        if _normalize_stock_code(code)
    }
    if not facts_by_code:
        return previous_index

    updated_index = dict(previous_index)
    updated_by_stock_code = {}
    for code, records in (previous_index.get("by_stock_code") or {}).items():
        normalized_code = _normalize_stock_code(code)
        fact = facts_by_code.get(normalized_code)
        updated_records = []
        for record in list(records or []):
            if not fact or not _record_needs_participation_review(record, trade_date):
                updated_records.append(record)
                continue
            planned = _record_planned_participation(record)
            review_facts = build_participation_review_facts_from_market_fact(
                planned,
                {
                    **fact,
                    "stock_code": record.get("stock_code") or normalized_code,
                    "stock_name": record.get("stock_name"),
                    "review_trade_date": fact.get("review_trade_date") or trade_date,
                },
            )
            review = classify_planned_participation_review(planned, **review_facts)
            compact_review = _compact_participation_review_for_index(review)
            updated_record = {
                **record,
                "latest_trade_date": trade_date,
                "participation_review_status": review.get("status"),
                "participation_review": compact_review,
                "mentions": _attach_review_to_latest_prior_mention(record, trade_date, review),
            }
            updated_records.append(updated_record)
        updated_by_stock_code[code] = updated_records
    updated_index["by_stock_code"] = updated_by_stock_code
    return updated_index


def write_decision_ledger_artifacts(
    snapshot,
    *,
    root_dir=".",
    review_market_facts_by_stock_code=None,
    database_service=None,
    write_json_archive=True,
    write_decision_revision=True,
):
    root = Path(root_dir)
    snapshot = _sanitize_decision_ledger_snapshot(snapshot or {})
    trade_date = snapshot.get("trade_date")
    ledger_dir = root / "data" / "decision-ledger"
    snapshot_path = ledger_dir / f"{trade_date}.json"
    index_path = ledger_dir / "index.json"
    previous_same_day_snapshot = _sanitize_decision_ledger_snapshot(_read_json_if_exists(snapshot_path))
    previous_index = {}
    service = database_service
    postgres_required = _postgres_storage_required()
    if service is None and postgres_required:
        try:
            from storage.database_service import DatabaseService

            service_factory = getattr(DatabaseService, "fact_store_from_environment", None)
            service = service_factory() if callable(service_factory) else DatabaseService.from_environment()
        except Exception as exc:
            return {
                "snapshot_path": str(snapshot_path),
                "index_path": str(index_path),
                "case_count": 0,
                "index": {},
                "fact_db_sync": {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            }
    if postgres_required and (
        service is None
        or not callable(getattr(service, "is_postgres_backed", None))
        or not service.is_postgres_backed()
    ):
        return {
            "snapshot_path": str(snapshot_path),
            "index_path": str(index_path),
            "case_count": 0,
            "index": {},
            "fact_db_sync": {
                "status": "failed",
                "error_type": "RuntimeError",
                "error": "PostgreSQL decision ledger storage is configured but DatabaseService did not select PostgreSQL",
            },
        }
    if (
        service is not None
        and callable(getattr(service, "is_postgres_backed", None))
        and service.is_postgres_backed()
        and callable(getattr(service, "read_decision_ledger_index", None))
    ):
        previous_index = _sanitize_decision_ledger_index(service.read_decision_ledger_index(end_date=trade_date, window_days=25))
    else:
        if postgres_required:
            return {
                "snapshot_path": str(snapshot_path),
                "index_path": str(index_path),
                "case_count": 0,
                "index": {},
                "fact_db_sync": {
                    "status": "failed",
                    "error_type": "RuntimeError",
                    "error": "PostgreSQL decision ledger index reader is unavailable",
                },
            }
        previous_index = _sanitize_decision_ledger_index(_read_json_if_exists(index_path))
    if review_market_facts_by_stock_code is None:
        review_market_facts_by_stock_code = _load_review_market_facts(root, trade_date, previous_index)
    previous_index = _apply_daily_judgment_reviews_to_previous_index(
        previous_index,
        trade_date,
        root,
        snapshot,
        review_market_facts_by_stock_code=review_market_facts_by_stock_code,
    )
    previous_index = _apply_participation_reviews_to_previous_index(
        previous_index,
        trade_date,
        review_market_facts_by_stock_code=review_market_facts_by_stock_code,
    )
    previous_index = _sanitize_decision_ledger_index(previous_index)
    previous_index = _prune_replaced_same_day_records(previous_index, snapshot)
    if not write_decision_revision and not snapshot.get("final_action"):
        recovered_final_action = _recover_final_action_for_intermediate_snapshot(
            snapshot=snapshot,
            previous_snapshot=previous_same_day_snapshot,
            root=root,
            trade_date=trade_date,
            service=service,
        )
        if recovered_final_action:
            snapshot["final_action"] = recovered_final_action
    merged_snapshot = _sanitize_decision_ledger_snapshot(merge_snapshot_with_previous_index(snapshot, previous_index))
    if write_decision_revision:
        merged_snapshot.pop("decision_revision_policy", None)
    else:
        merged_snapshot["decision_revision_policy"] = "intermediate_snapshot"
    index = build_decision_ledger_index(merged_snapshot, previous_index=previous_index)
    fact_db_sync = {"status": "not_run", "rows": 0}
    service_is_postgres = (
        service is not None
        and callable(getattr(service, "is_postgres_backed", None))
        and service.is_postgres_backed()
    )
    if service_is_postgres:
        try:
            structured_result = service.replace_decision_ledger_snapshot(merged_snapshot)
            fact_db_sync = {
                "status": "success",
                "rows": int(structured_result.get("mentions") or 0),
                "cases": int(structured_result.get("cases") or 0),
            }
        except Exception as exc:
            return {
                "snapshot_path": str(snapshot_path),
                "index_path": str(index_path),
                "case_count": len(merged_snapshot.get("cases") or []),
                "index": index,
                "fact_db_sync": {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            }
    stale_json_removed = []
    if write_json_archive:
        _write_json(snapshot_path, merged_snapshot)
        _write_json(index_path, index)
    elif service_is_postgres and fact_db_sync.get("status") == "success":
        for stale_path in (snapshot_path, index_path):
            if _remove_file_if_exists(stale_path):
                stale_json_removed.append(str(stale_path))
    if write_decision_revision:
        revision_ledger = write_decision_revision_ledger_artifact(
            merged_snapshot,
            previous_snapshot=previous_same_day_snapshot,
            root_dir=root,
            created_at=snapshot.get("generated_at"),
        )
    else:
        revision_ledger = {"status": "not_run", "entries": []}
    if write_decision_revision and not write_json_archive:
        revision_ledger = dict(revision_ledger)
        revision_ledger["reason"] = "PostgreSQL-only 路径不写完整 JSON 快照；仅保留本地结构化决策差异记录"
    if not service_is_postgres and service is not None:
        try:
            current_rows = build_extreme_conviction_mention_rows(index, end_date=trade_date, window_days=1, exclude_a_kill=False)
            recent_rows = build_extreme_conviction_mention_rows(index, end_date=trade_date, window_days=25, exclude_a_kill=False)
            service.replace_extreme_conviction_mentions_for_trade_date(
                trade_date,
                current_rows,
            )
            service.upsert_extreme_conviction_mentions(recent_rows)
            fact_db_sync = {"status": "success", "rows": len(recent_rows)}
        except Exception as exc:
            fact_db_sync = {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
    return {
        "snapshot_path": str(snapshot_path),
        "index_path": str(index_path),
        "case_count": len(merged_snapshot.get("cases") or []),
        "index": index,
        "fact_db_sync": fact_db_sync,
        "revision_ledger": revision_ledger,
        "stale_json_removed": stale_json_removed,
    }


def _relative_report_path(report_path, root_dir):
    path = Path(report_path)
    root = Path(root_dir)
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write_decision_ledger_artifacts_from_markdown_report(
    report_path,
    *,
    trade_date,
    market_branch,
    sector_relationship_state,
    root_dir=".",
    generated_at=None,
    write_json_archive=True,
    write_decision_revision=True,
    review_market_facts_by_stock_code=None,
):
    report_file = Path(report_path)
    root = Path(root_dir)
    snapshot = build_decision_ledger_snapshot_from_markdown_report(
        report_file.read_text(encoding="utf-8"),
        trade_date=trade_date,
        market_branch=market_branch,
        sector_relationship_state=sector_relationship_state,
        source_report={
            "path": _relative_report_path(report_file, root),
            "variant": "full",
        },
        generated_at=generated_at,
    )
    if write_json_archive and not snapshot.get("cases"):
        ledger_dir = root / "data" / "decision-ledger"
        snapshot_path = ledger_dir / f"{trade_date}.json"
        existing_snapshot = _read_json_if_exists(snapshot_path)
        existing_case_count = len((existing_snapshot or {}).get("cases") or [])
        if existing_case_count:
            return {
                "snapshot_path": str(snapshot_path),
                "index_path": str(ledger_dir / "index.json"),
                "case_count": existing_case_count,
                "skipped_empty_markdown": True,
                "fact_db_sync": {"status": "skipped", "rows": 0},
            }
    return write_decision_ledger_artifacts(
        snapshot,
        root_dir=root,
        write_json_archive=write_json_archive,
        write_decision_revision=write_decision_revision,
        review_market_facts_by_stock_code=review_market_facts_by_stock_code,
    )


def _source_report_path_from_snapshot(snapshot):
    source_report = (snapshot or {}).get("source_report") if isinstance((snapshot or {}).get("source_report"), dict) else {}
    return _clean_text(source_report.get("path"))


def _case_source_dates(item, trade_date):
    return _normalize_source_dates(item if isinstance(item, dict) else {}, default_snapshot_date=trade_date)


def _case_missing_fields(item, planned, source_dates, position_plan_pct):
    missing = _merge_missing_fields((item or {}).get("missing_fields"))
    if position_plan_pct in (50, 100) and not planned:
        missing = _merge_missing_fields(missing, ["planned_participation"])
    if not source_dates.get("snapshot_date"):
        missing = _merge_missing_fields(missing, ["snapshot_date"])
    if position_plan_pct is None:
        missing = _merge_missing_fields(missing, ["position_plan_pct"])
    if not _cancellation_conditions_from_plan(planned, item):
        missing = _merge_missing_fields(missing, ["cancellation_conditions"])
    return missing


def build_decision_ledger_snapshot(
    *,
    trade_date,
    extreme_conviction_list,
    market_branch,
    sector_relationship_state,
    source_report=None,
    generated_at=None,
    final_action=None,
):
    cases = []
    for idx, item in enumerate(list(extreme_conviction_list or []), 1):
        stock_code = _normalize_stock_code(item.get("code") or item.get("stock_code"))
        stock_name = _clean_text(item.get("name") or item.get("stock_name"), stock_code or "判断样本")
        sector = _resolve_sector_candidate(item, "未归类")
        normalized_item = {**item, "sector": sector}
        case = {
            "case_id": _build_case_id(trade_date, stock_code, 1),
            "stock_code": stock_code,
            "stock_name": stock_name,
            "first_seen_trade_date": trade_date,
            "cycle_start_trade_date": trade_date,
            "cycle_day": 1,
            "cycle_length_trade_days": DEFAULT_CYCLE_LENGTH_TRADE_DAYS,
            "mentions": [_build_mention(normalized_item, trade_date=trade_date, rank=idx)],
            "hypothesis": {
                "stock_setup": _build_stock_setup(normalized_item),
                "sector_candidate": sector,
                "market_branch": _clean_text(market_branch, "待验证市场演变"),
                "sector_relationship_state": _clean_text(sector_relationship_state, "暂未分出"),
            },
            "validation": {
                "status": "等待市场选择",
                "selection_confirmed_date": None,
                "selection_confirmed_evidence": None,
                "sector_selection_evidence": None,
                "stock_acceptance_evidence": None,
            },
            "trend_fate": {
                "label": None,
                "elimination_event": None,
                "missed_upside_after_elimination": None,
            },
            "cycle_acceptance": {
                "status": "open",
                "final_label": None,
                "reason": None,
                "iteration_note": None,
            },
        }
        core_identity = normalized_item.get("core_identity")
        if isinstance(core_identity, dict) and core_identity:
            case["core_identity"] = core_identity
        for key in (
            "sniper_role",
            "primary_buy_candidate",
            "backup_buy_candidate",
            "anchor_reversal_decision",
            "anchor_reversal_reason",
            "sector_anchor",
            "candidate_role",
            "relationship_to_anchor",
            "repair_priority",
        ):
            value = normalized_item.get(key)
            if value not in (None, ""):
                case[key] = value
        planned_participation = _build_planned_participation(normalized_item)
        if planned_participation:
            planned_participation = _enrich_planned_participation_contract(planned_participation)
            position_plan_pct = _position_plan_pct(planned_participation, normalized_item)
            source_dates = _case_source_dates(normalized_item, trade_date)
            case["planned_participation"] = planned_participation
            case["schema_version"] = "decision_ledger_record.v1"
            case["report_date"] = trade_date
            case["source_report_path"] = _source_report_path_from_snapshot({"source_report": source_report or {}})
            case["market_participation_qualification"] = (
                "qualified" if position_plan_pct in (50, 100) else "not_qualified" if position_plan_pct == 0 else "incomplete"
            )
            case["position_plan_pct"] = position_plan_pct
            case["position_plan_label"] = _position_plan_label(position_plan_pct)
            case["mainline"] = _clean_text(normalized_item.get("mainline") or sector)
            case["mainline_attack_evidence_score"] = _round_or_none(
                normalized_item.get("mainline_attack_evidence_score")
                or normalized_item.get("mainline_score")
                or normalized_item.get("score"),
                digits=0,
            )
            evidence_labels = normalized_item.get("mainline_attack_evidence_labels") or normalized_item.get("evidence_labels") or []
            case["mainline_attack_evidence_labels"] = list(evidence_labels) if isinstance(evidence_labels, list) else []
            case["sample_tier"] = _clean_text(normalized_item.get("sample_tier") or planned_participation.get("source_tier"), "high")
            case["trend_chain_position"] = _clean_text(normalized_item.get("trend_chain_position"), "unknown")
            case["cancellation_conditions"] = _cancellation_conditions_from_plan(planned_participation, normalized_item)
            case["source_dates"] = source_dates
            case["missing_fields"] = _case_missing_fields(normalized_item, planned_participation, source_dates, position_plan_pct)
            review_facts = normalized_item.get("participation_review_facts") or normalized_item.get("planned_participation_review_facts") or {}
            if isinstance(review_facts, dict) and review_facts:
                if _review_fact_has_price_data(review_facts) and not any(key in review_facts for key in ("performance", "source_dates", "missing_fields", "fact_inputs")):
                    review_facts = build_participation_review_facts_from_market_fact(planned_participation, review_facts)
                case["participation_review"] = classify_planned_participation_review(
                    planned_participation,
                    report_date=trade_date,
                    **review_facts,
                )
        cases.append(case)

    snapshot = {
        "artifact_version": ARTIFACT_VERSION,
        "trade_date": trade_date,
        "generated_at": generated_at,
        "frozen": True,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "selection_input_hash": _selection_input_hash(
            trade_date=trade_date,
            extreme_conviction_list=extreme_conviction_list,
            market_branch=market_branch,
            sector_relationship_state=sector_relationship_state,
        ),
        "source_report": source_report or {},
        "cases": cases,
    }
    normalized_final_action = _normalize_final_action_snapshot(final_action)
    if normalized_final_action:
        snapshot["final_action"] = normalized_final_action
    return snapshot


def build_decision_ledger_snapshot_from_markdown_report(
    markdown_text,
    *,
    trade_date,
    market_branch,
    sector_relationship_state,
    source_report=None,
    generated_at=None,
):
    return build_decision_ledger_snapshot(
        trade_date=trade_date,
        extreme_conviction_list=parse_extreme_conviction_list_from_markdown(markdown_text),
        market_branch=market_branch,
        sector_relationship_state=sector_relationship_state,
        source_report=source_report,
        generated_at=generated_at,
    )


def merge_snapshot_with_previous_index(snapshot, previous_index=None):
    merged = {**(snapshot or {})}
    merged_cases = []
    trade_date = merged.get("trade_date")
    for case in list(merged.get("cases") or []):
        stock_code = case.get("stock_code")
        previous_case = _find_open_previous_case(previous_index, stock_code)
        if previous_case:
            mentions = _merge_mentions_without_duplicates(
                _copy_mentions(previous_case),
                case.get("mentions") or [],
            )
            previous_review = previous_case.get("participation_review") or {}
            case = {
                **case,
                "case_id": previous_case.get("case_id") or case.get("case_id"),
                "first_seen_trade_date": previous_case.get("cycle_start_trade_date")
                or previous_case.get("first_seen_trade_date")
                or case.get("first_seen_trade_date"),
                "cycle_start_trade_date": previous_case.get("cycle_start_trade_date")
                or case.get("cycle_start_trade_date"),
                "cycle_day": _cycle_day_from_dates(
                    previous_case.get("cycle_start_trade_date") or case.get("cycle_start_trade_date"),
                    trade_date,
                ),
                "mentions": mentions,
            }
            if previous_review and not case.get("participation_review"):
                case["participation_review"] = previous_review
            sector = _clean_text((case.get("hypothesis") or {}).get("sector_candidate"))
            if _is_valid_sector_label(sector):
                case = _sanitize_sector_references(case, sector)
        merged_cases.append(case)
    merged["cases"] = merged_cases
    return merged


__all__ = [
    "build_decision_ledger_snapshot",
    "build_decision_ledger_snapshot_from_markdown_report",
    "build_decision_revision_entry",
    "build_decision_coverage_summary",
    "build_extreme_conviction_backtest_rows",
    "build_extreme_conviction_mention_rows",
    "build_participation_review_facts_from_market_fact",
    "build_decision_ledger_index",
    "classify_cycle_acceptance",
    "classify_planned_participation_review",
    "classify_validation_state",
    "merge_snapshot_with_previous_index",
    "parse_extreme_conviction_list_from_markdown",
    "prune_replaced_same_day_extreme_mentions",
    "render_extreme_conviction_backtest_lines",
    "render_extreme_conviction_mention_tracking_lines",
    "render_extreme_conviction_mention_tracking_rows",
    "render_extreme_conviction_tracking_lines",
    "write_decision_ledger_artifacts",
    "write_decision_ledger_artifacts_from_markdown_report",
    "write_decision_revision_ledger_artifact",
]
