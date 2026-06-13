from __future__ import annotations

from report.sniper_target_derivation import clean_text, normalize_stock_code, stock_label


SCHEMA_VERSION = "next_day_attribution.v1"

FINAL_OBSERVATION = "final_observation"
EXECUTION_TARGET = "execution_target"
PROCESS_CROSSLINE = "process_crossline"
PROCESS_OBSERVATION = "process_observation"
HISTORICAL_EVIDENCE = "historical_evidence"
EXCLUDED = "excluded"

FINAL_OBSERVATION_HIT = "final_observation_hit"
EXECUTION_HIT = "execution_hit"
PROCESS_CANDIDATE_HIT = "process_candidate_hit"
PROCESS_CANDIDATE_MISS = "process_candidate_miss"
HISTORICAL_FOLLOWUP = "historical_followup"
EXCLUDED_NOT_COUNTED = "excluded_not_counted"
UNKNOWN = "unknown"


def _stock_payload(value):
    value = value if isinstance(value, dict) else {}
    name = clean_text(value.get("name") or value.get("stock_name") or value.get("名称"))
    code = normalize_stock_code(value.get("code") or value.get("stock_code") or value.get("代码") or value.get("symbol"))
    if not (name or code):
        return {}
    payload = {"code": code, "name": name}
    sector = clean_text(value.get("sector") or value.get("sector_name") or value.get("industry") or value.get("所属行业"))
    if sector:
        payload["sector"] = sector
    return payload


def _stock_key(value):
    payload = _stock_payload(value)
    return payload.get("code") or payload.get("name") or ""


def _dedupe_rows(rows):
    result = []
    seen = set()
    for row in rows:
        key = (_stock_key(row), clean_text(row.get("identity_layer")), clean_text(row.get("source_bucket")))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _position_pct(value):
    value = value if isinstance(value, dict) else {}
    for key in ("position_plan_pct", "target_position_pct", "position_pct"):
        if key not in value:
            continue
        try:
            return int(float(str(value.get(key)).replace("%", "").strip()))
        except (TypeError, ValueError):
            continue
    return 0


def _quote_key(value):
    value = value if isinstance(value, dict) else {}
    code = normalize_stock_code(value.get("code") or value.get("stock_code") or value.get("代码") or value.get("symbol"))
    name = clean_text(value.get("name") or value.get("stock_name") or value.get("名称"))
    return code or name


def _quote_map(next_day_quotes):
    result = {}
    if isinstance(next_day_quotes, dict):
        iterable = next_day_quotes.values()
    else:
        iterable = next_day_quotes or []
    for item in iterable:
        if not isinstance(item, dict):
            continue
        key = _quote_key(item)
        if key:
            result[key] = item
    return result


def _float_value(*values):
    for value in values:
        if value is None:
            continue
        try:
            return float(str(value).replace("%", "").replace(",", "").strip())
        except (TypeError, ValueError):
            continue
    return None


def _quote_return_pct(quote):
    quote = quote if isinstance(quote, dict) else {}
    return _float_value(
        quote.get("pct_chg"),
        quote.get("change_pct"),
        quote.get("涨跌幅"),
        quote.get("return_pct"),
        quote.get("return_1d_pct"),
    )


def _quote_high_pct(quote):
    quote = quote if isinstance(quote, dict) else {}
    high_pct = _float_value(quote.get("high_pct"), quote.get("next_day_high_pct"))
    if high_pct is not None:
        return high_pct
    high = _float_value(quote.get("high"), quote.get("最高"))
    prev_close = _float_value(quote.get("pre_close"), quote.get("prev_close"), quote.get("昨收"))
    if high is not None and prev_close:
        return round((high / prev_close - 1) * 100, 2)
    return None


def _quote_low_pct(quote):
    quote = quote if isinstance(quote, dict) else {}
    low_pct = _float_value(quote.get("low_pct"), quote.get("next_day_low_pct"))
    if low_pct is not None:
        return low_pct
    low = _float_value(quote.get("low"), quote.get("最低"))
    prev_close = _float_value(quote.get("pre_close"), quote.get("prev_close"), quote.get("昨收"))
    if low is not None and prev_close:
        return round((low / prev_close - 1) * 100, 2)
    return None


def _quote_date(quote):
    quote = quote if isinstance(quote, dict) else {}
    for key in ("review_date", "trade_date", "source_date", "query_date", "date"):
        text = clean_text(quote.get(key))
        if text:
            return text
    return ""


def _close_status(return_pct, quote):
    quote = quote if isinstance(quote, dict) else {}
    status = clean_text(quote.get("close_status") or quote.get("status") or quote.get("状态"))
    if status:
        return status
    if return_pct is None:
        return UNKNOWN
    if return_pct >= 9.5:
        return "limit_up"
    if return_pct >= 3:
        return "strong"
    if return_pct <= -3:
        return "failed"
    return "weak"


def _source_bucket(identity_layer):
    if identity_layer == FINAL_OBSERVATION:
        return "final_target_resolution"
    if identity_layer == EXECUTION_TARGET:
        return "final_target_resolution"
    if identity_layer == PROCESS_CROSSLINE:
        return "crossline_observation_stocks"
    if identity_layer == PROCESS_OBSERVATION:
        return "extreme_conviction_list"
    if identity_layer == HISTORICAL_EVIDENCE:
        return "historical_review"
    return "candidates"


def _row_role(identity_layer):
    return {
        FINAL_OBSERVATION: "最终观察对象",
        EXECUTION_TARGET: "明日执行对象",
        PROCESS_CROSSLINE: "跨线过程候选",
        PROCESS_OBSERVATION: "候选观察补充",
        HISTORICAL_EVIDENCE: "历史观察证据",
        EXCLUDED: "排除样本",
    }.get(identity_layer, "待识别")


def _execution_qualification(identity_layer, participation_pct):
    if identity_layer == EXECUTION_TARGET and participation_pct > 0:
        return "qualified"
    if identity_layer == FINAL_OBSERVATION:
        return "observation_only"
    if identity_layer in {PROCESS_CROSSLINE, PROCESS_OBSERVATION, HISTORICAL_EVIDENCE, EXCLUDED}:
        return "not_qualified"
    return "incomplete"


def _counting_bucket(identity_layer, participation_pct, return_pct, missing_fields):
    if missing_fields:
        return UNKNOWN
    if identity_layer == EXECUTION_TARGET and participation_pct > 0:
        return EXECUTION_HIT if (return_pct is not None and return_pct > 0) else PROCESS_CANDIDATE_MISS
    if identity_layer == FINAL_OBSERVATION:
        return FINAL_OBSERVATION_HIT if (return_pct is not None and return_pct > 0) else PROCESS_CANDIDATE_MISS
    if identity_layer in {PROCESS_CROSSLINE, PROCESS_OBSERVATION}:
        return PROCESS_CANDIDATE_HIT if (return_pct is not None and return_pct > 0) else PROCESS_CANDIDATE_MISS
    if identity_layer == HISTORICAL_EVIDENCE:
        return HISTORICAL_FOLLOWUP
    return EXCLUDED_NOT_COUNTED


def _summary_for_row(identity_layer, bucket, return_pct, participation_pct):
    if bucket == UNKNOWN:
        return "次日行情事实缺失，暂不结算"
    pct_text = f"{return_pct:+.2f}%" if return_pct is not None else "待补"
    if bucket == EXECUTION_HIT:
        return f"执行对象次日表现 {pct_text}，计入执行命中"
    if bucket == FINAL_OBSERVATION_HIT:
        return f"最终观察对象次日表现 {pct_text}；因报告仓位为{participation_pct}%，不计为执行命中"
    if bucket == PROCESS_CANDIDATE_HIT:
        return f"过程候选次日表现 {pct_text}，只计入过程候选命中"
    if bucket == PROCESS_CANDIDATE_MISS:
        return f"{_row_role(identity_layer)}次日表现 {pct_text}，计入对应层级失败样本"
    if bucket == HISTORICAL_FOLLOWUP:
        return f"历史证据次日表现 {pct_text}，只计入历史跟踪"
    return "排除样本不计入命中率"


def _make_row(candidate, identity_layer, *, quote, report_position_pct, review_date):
    payload = _stock_payload(candidate)
    row_review_date = _quote_date(quote) or review_date
    missing_fields = []
    if not row_review_date:
        missing_fields.append("review_date")
    return_pct = _quote_return_pct(quote)
    if return_pct is None:
        missing_fields.append("next_day_return_pct")
    source_name = clean_text((quote or {}).get("source_name") or (quote or {}).get("source"))
    if not source_name:
        missing_fields.append("source_name")
    bucket = _counting_bucket(identity_layer, report_position_pct, return_pct, missing_fields)
    return {
        "code": payload.get("code", ""),
        "name": payload.get("name", ""),
        "identity_layer": identity_layer,
        "source_bucket": _source_bucket(identity_layer),
        "report_role_text": _row_role(identity_layer),
        "participation_plan_pct": report_position_pct if identity_layer == EXECUTION_TARGET else 0,
        "execution_qualification": _execution_qualification(identity_layer, report_position_pct),
        "planned_window": "unknown" if identity_layer == EXECUTION_TARGET else "no_trade",
        "next_day_return_pct": return_pct,
        "next_day_high_pct": _quote_high_pct(quote),
        "next_day_low_pct": _quote_low_pct(quote),
        "close_status": _close_status(return_pct, quote),
        "counting_bucket": bucket,
        "attribution_summary": _summary_for_row(identity_layer, bucket, return_pct, report_position_pct),
        "review_date": row_review_date,
        "source_name": source_name,
        "source_quote_time": clean_text((quote or {}).get("source_quote_time") or (quote or {}).get("quote_time")),
        "missing_fields": missing_fields,
    }


def _append_candidate(rows, candidate, identity_layer):
    payload = _stock_payload(candidate)
    if not payload:
        return
    payload["identity_layer"] = identity_layer
    rows.append(payload)


def build_next_day_attribution(
    *,
    report_date,
    review_date,
    final_target_resolution=None,
    position_decision=None,
    process_candidates=None,
    historical_evidence=None,
    next_day_quotes=None,
    source_name="",
    source_quote_time="",
):
    final_target_resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    report_position_pct = _position_pct(position_decision)
    quote_by_key = _quote_map(next_day_quotes)
    raw_rows = []
    new_entry = _stock_payload(final_target_resolution.get("new_entry_target"))
    watch_target = _stock_payload(final_target_resolution.get("watch_target"))
    if new_entry and report_position_pct > 0:
        _append_candidate(raw_rows, new_entry, EXECUTION_TARGET)
    if watch_target:
        _append_candidate(raw_rows, watch_target, FINAL_OBSERVATION)
    for item in process_candidates or []:
        item = item if isinstance(item, dict) else {}
        identity_layer = clean_text(item.get("identity_layer"))
        if identity_layer not in {PROCESS_CROSSLINE, PROCESS_OBSERVATION}:
            identity_layer = PROCESS_CROSSLINE if clean_text(item.get("source_bucket") or item.get("source")) == "crossline_observation_stocks" else PROCESS_OBSERVATION
        _append_candidate(raw_rows, item, identity_layer)
    for item in historical_evidence or []:
        _append_candidate(raw_rows, item, HISTORICAL_EVIDENCE)
    rows = []
    for candidate in _dedupe_rows(raw_rows):
        key = _stock_key(candidate)
        quote = quote_by_key.get(key) or {}
        if isinstance(quote, dict):
            quote = dict(quote)
        quote.setdefault("source_name", source_name)
        quote.setdefault("source_quote_time", source_quote_time)
        rows.append(
            _make_row(
                candidate,
                candidate.get("identity_layer"),
                quote=quote,
                report_position_pct=report_position_pct,
                review_date=review_date,
            )
        )
    summary = _build_summary(rows, report_position_pct)
    return {
        "schema_version": SCHEMA_VERSION,
        "report_date": clean_text(report_date),
        "review_date": clean_text(review_date),
        "source_name": clean_text(source_name),
        "source_quote_time": clean_text(source_quote_time),
        "report_final_action": {
            "position_plan_pct": report_position_pct,
            "new_entry_target": new_entry or None,
            "watch_target": watch_target or None,
        },
        "rows": rows,
        "summary": summary,
    }


def _build_summary(rows, report_position_pct):
    summary = {
        "execution_hit_count": 0,
        "final_observation_hit_count": 0,
        "process_candidate_hit_count": 0,
        "process_candidate_miss_count": 0,
        "historical_followup_count": 0,
        "unknown_count": 0,
        "not_counted_as_execution_reason": "",
    }
    for row in rows:
        bucket = row.get("counting_bucket")
        if bucket == EXECUTION_HIT:
            summary["execution_hit_count"] += 1
        elif bucket == FINAL_OBSERVATION_HIT:
            summary["final_observation_hit_count"] += 1
        elif bucket == PROCESS_CANDIDATE_HIT:
            summary["process_candidate_hit_count"] += 1
        elif bucket == PROCESS_CANDIDATE_MISS:
            summary["process_candidate_miss_count"] += 1
        elif bucket == HISTORICAL_FOLLOWUP:
            summary["historical_followup_count"] += 1
        elif bucket == UNKNOWN:
            summary["unknown_count"] += 1
    if report_position_pct <= 0:
        summary["not_counted_as_execution_reason"] = "报告没有明日执行对象"
    return summary


def render_next_day_attribution_lines(packet):
    packet = packet if isinstance(packet, dict) else {}
    if packet.get("schema_version") != SCHEMA_VERSION:
        return []
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not rows:
        return []
    lines = [
        "## 次日归因闭环",
        "",
        "| 标的 | 日报身份 | 次日表现 | 结算桶 | 归因 |",
        "|------|----------|----------|--------|------|",
    ]
    for row in rows:
        label = stock_label(row)
        return_pct = row.get("next_day_return_pct")
        return_text = "待补事实" if return_pct is None else f"{float(return_pct):+.2f}%"
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    clean_text(row.get("report_role_text"), "-"),
                    return_text,
                    clean_text(row.get("counting_bucket"), "-"),
                    clean_text(row.get("attribution_summary"), "-").replace("|", "｜"),
                ]
            )
            + " |"
        )
    reason = clean_text((packet.get("summary") or {}).get("not_counted_as_execution_reason"))
    if reason:
        lines.extend(["", f"> {reason}。"])
    return lines


def audit_next_day_attribution_packet(packet):
    packet = packet if isinstance(packet, dict) else {}
    findings = []
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    report_action = packet.get("report_final_action") if isinstance(packet.get("report_final_action"), dict) else {}
    position_pct = _position_pct(report_action)
    if position_pct <= 0 and int(summary.get("execution_hit_count") or 0) > 0:
        findings.append(
            {
                "code": "next_day_attribution_execution_hit_without_plan",
                "message": "0%或仅观察报告不能计入执行命中",
            }
        )
    for row in packet.get("rows") or []:
        identity = clean_text(row.get("identity_layer"))
        bucket = clean_text(row.get("counting_bucket"))
        if identity in {PROCESS_CROSSLINE, PROCESS_OBSERVATION} and bucket in {EXECUTION_HIT, FINAL_OBSERVATION_HIT}:
            findings.append(
                {
                    "code": "next_day_attribution_process_counted_as_final",
                    "message": f"过程候选不能计入最终或执行命中: {stock_label(row)}",
                }
            )
        if identity == HISTORICAL_EVIDENCE and bucket != HISTORICAL_FOLLOWUP and not row.get("missing_fields"):
            findings.append(
                {
                    "code": "next_day_attribution_history_counted_as_current",
                    "message": f"历史证据不能计入当前最终对象命中: {stock_label(row)}",
                }
            )
    return {"passed": not findings, "findings": findings}
