from __future__ import annotations

JUDGMENT_TYPES = (
    {
        "judgment_type": "market_state",
        "label": "市场状态判断",
        "metric_definition": "进攻/退潮/修复/混沌/冰点是否被次日走势验证",
    },
    {
        "judgment_type": "mainline",
        "label": "主线判断",
        "metric_definition": "资金第二天是否继续选择这条线",
    },
    {
        "judgment_type": "core_candidate",
        "label": "核心候选判断",
        "metric_definition": "选出的票是否进入资金视野",
    },
    {
        "judgment_type": "participation_rehearsal",
        "label": "参与预演判断",
        "metric_definition": "竞价、开盘、回封、分歧路径是否命中",
    },
    {
        "judgment_type": "cancellation_condition",
        "label": "取消条件判断",
        "metric_definition": "不买、空仓、放弃追高是否避免错误参与",
    },
)

JUDGMENT_TYPE_KEYS = {item["judgment_type"] for item in JUDGMENT_TYPES}
_HIT_REVIEW_STATUSES = {"预演命中", "错过后方案命中"}
_MISS_REVIEW_STATUSES = {"预演作废", "预演过早", "主目标不可成交"}
_WAITING_REVIEW_STATUSES = {"", "等待复盘", "等待窗口复盘", "等待事实", "待补事实"}
_OPTIONAL_PERFORMANCE_FIELDS = {
    "return_1d_pct",
    "return_3d_pct",
    "return_5d_pct",
    "max_drawdown_5d_pct",
    "price_source_date",
}


def _clean_text(value, default=""):
    text = " ".join(str(value or "").split()).strip()
    return text or default


def _clean_markdown_cell(value, default="-"):
    text = _clean_text(value, default)
    return text.replace("|", "｜")


def _merge_missing_fields(*values):
    merged = []
    for value in values:
        if isinstance(value, str):
            items = [value]
        else:
            items = list(value or [])
        for item in items:
            text = _clean_text(item)
            if text and text not in merged:
                merged.append(text)
    return merged


def _is_missing_correctness(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "none", "null", "missing", "待补事实", "等待复盘", "等待事实"}
    return False


def _bool_correctness(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "correct", "hit", "命中", "正确", "对"}:
        return True
    if text in {"false", "0", "no", "n", "wrong", "miss", "失败", "错误", "错"}:
        return False
    return None


def _review_date(item, record=None, mention=None):
    item = item or {}
    record = record or {}
    for key in ("report_date", "mention_trade_date", "trade_date", "date", "review_date"):
        text = _clean_text(item.get(key))
        if text:
            return text
    if isinstance(mention, dict):
        text = _clean_text(mention.get("mention_trade_date"))
        if text:
            return text
    for mention in list(record.get("mentions") or []):
        text = _clean_text((mention or {}).get("mention_trade_date"))
        if text:
            return text
    return _clean_text(record.get("report_date") or record.get("cycle_start_trade_date") or record.get("first_seen_trade_date"))


def _mistake_text(item, default=""):
    item = item or {}
    for key in ("mistake", "mistake_reason", "wrong_reason", "error", "reason", "review_note"):
        text = _clean_text(item.get(key))
        if text:
            return text
    return default


def _normalize_judgment_review(item, record=None, mention=None):
    if not isinstance(item, dict):
        return None
    judgment_type = _clean_text(item.get("judgment_type") or item.get("type") or item.get("key"))
    if judgment_type not in JUDGMENT_TYPE_KEYS:
        return None
    missing_fields = _merge_missing_fields(item.get("missing_fields"))
    raw_correct = item.get("is_correct")
    if raw_correct is None and "correct" in item:
        raw_correct = item.get("correct")
    if raw_correct is None and "result" in item:
        raw_correct = item.get("result")
    correctness = None if missing_fields or _is_missing_correctness(raw_correct) else _bool_correctness(raw_correct)
    if correctness is None and not missing_fields:
        missing_fields = _merge_missing_fields(missing_fields, ["review_fact"])
    return {
        "judgment_type": judgment_type,
        "date": _review_date(item, record, mention),
        "is_correct": correctness,
        "missing_fields": missing_fields,
        "mistake": "" if correctness is not False else _mistake_text(item, "判断未被次日事实验证"),
    }


def _record_judgment_reviews(record):
    reviews = []
    for item in list((record or {}).get("judgment_reviews") or []):
        review = _normalize_judgment_review(item, record)
        if review:
            reviews.append(review)
    for mention in list((record or {}).get("mentions") or []):
        for item in list((mention or {}).get("judgment_reviews") or []):
            review = _normalize_judgment_review(item, record, mention)
            if review:
                reviews.append(review)
    return reviews


def _participation_review_from_record(record, mention=None, mention_count=1):
    mention = mention or {}
    review = mention.get("participation_review")
    if isinstance(review, dict) and review:
        return review
    if mention_count == 1:
        review = (record or {}).get("participation_review")
        if isinstance(review, dict) and review:
            return review
    return {}


def _participation_review_status(review, record=None):
    return _clean_text(
        (review or {}).get("status")
        or (review or {}).get("review_status")
        or (record or {}).get("participation_review_status")
    )


def _participation_review_date(review, mention, record):
    return _clean_text((mention or {}).get("mention_trade_date")) or _review_date(review, record)


def _review_facts_missing(review, status):
    missing = [
        item
        for item in _merge_missing_fields((review or {}).get("missing_fields"))
        if item not in _OPTIONAL_PERFORMANCE_FIELDS
    ]
    if status in _WAITING_REVIEW_STATUSES:
        missing = _merge_missing_fields(missing, ["participation_review"])
    return missing


def _fallback_reviews_from_participation(record):
    record = record or {}
    mentions = list(record.get("mentions") or [])
    if not mentions:
        mentions = [{}]
    rows = []
    for mention in mentions:
        review = _participation_review_from_record(record, mention, len(mentions))
        status = _participation_review_status(review, record)
        if not status and not review:
            continue
        date = _participation_review_date(review, mention, record)
        fact_inputs = (review or {}).get("fact_inputs") if isinstance((review or {}).get("fact_inputs"), dict) else {}
        missing = _review_facts_missing(review, status)
        if missing:
            is_correct = None
            mistake = ""
        elif status in _HIT_REVIEW_STATUSES:
            is_correct = True
            mistake = ""
        elif status in _MISS_REVIEW_STATUSES:
            is_correct = False
            mistake = f"{status}：{_clean_text((review or {}).get('reason'), '次日路径没有按预演展开')}"
        else:
            is_correct = None
            mistake = ""
        rows.append(
            {
                "judgment_type": "participation_rehearsal",
                "date": date,
                "is_correct": is_correct,
                "missing_fields": missing,
                "mistake": mistake,
            }
        )
        if fact_inputs.get("cancellation_triggered") is True:
            cancellation_missing = _review_facts_missing(review, status)
            cancellation_correct = status in {"预演作废", "主目标不可成交"} if not cancellation_missing else None
            rows.append(
                {
                    "judgment_type": "cancellation_condition",
                    "date": date,
                    "is_correct": cancellation_correct,
                    "missing_fields": cancellation_missing,
                    "mistake": "" if cancellation_correct in {True, None} else "取消条件出现但复盘未确认避免错误参与",
                }
            )
    return rows


def _status_correctness(status, *, success_tokens=None, failure_tokens=None, waiting_tokens=None):
    text = _clean_text(status)
    if not text:
        return None
    waiting_tokens = tuple(waiting_tokens or ("等待", "待验证", "待补"))
    if any(token in text for token in waiting_tokens):
        return None
    if any(token in text for token in tuple(success_tokens or ())):
        return True
    if any(token in text for token in tuple(failure_tokens or ())):
        return False
    return None


def _fallback_mainline_review(record):
    record = record or {}
    validation = record.get("validation") if isinstance(record.get("validation"), dict) else {}
    status = _clean_text(validation.get("status") or record.get("status"))
    correctness = _status_correctness(
        status,
        success_tokens=("市场选择确认", "主线确认"),
        failure_tokens=("真正失败", "方向持续失去选择", "主线未延续"),
    )
    missing_fields = [] if correctness is not None else ["mainline_review"]
    mistake = ""
    if correctness is False:
        mistake = _clean_text(
            validation.get("failure_reason")
            or validation.get("sector_selection_evidence")
            or validation.get("selection_confirmed_evidence"),
            "资金第二天没有继续选择这条线",
        )
    return {
        "judgment_type": "mainline",
        "date": _review_date({}, record),
        "is_correct": correctness,
        "missing_fields": missing_fields,
        "mistake": mistake,
    }


def _selection_result_payload(record):
    record = record or {}
    result = record.get("selection_result")
    if isinstance(result, dict) and result:
        return result
    for mention in list(record.get("mentions") or []):
        result = (mention or {}).get("selection_result")
        if isinstance(result, dict) and result:
            return result
    return {}


def _fallback_core_candidate_review(record):
    record = record or {}
    result = _selection_result_payload(record)
    validation = record.get("validation") if isinstance(record.get("validation"), dict) else {}
    status = _clean_text(result.get("status"))
    correctness = _status_correctness(
        status,
        success_tokens=("识别成功", "进入资金视野", "市场选择确认"),
        failure_tokens=("识别失败", "未进入资金视野", "真正失败"),
    )
    if correctness is None and validation:
        validation_status = _clean_text(validation.get("status"))
        if validation_status == "市场选择确认" and _clean_text(validation.get("stock_acceptance_evidence")):
            correctness = True
        elif validation_status == "真正失败":
            correctness = False
    missing_fields = [] if correctness is not None else ["core_candidate_review"]
    mistake = ""
    if correctness is False:
        mistake = _clean_text(
            result.get("lesson")
            or result.get("evidence")
            or validation.get("failure_reason")
            or validation.get("stock_acceptance_evidence"),
            "选出的票没有进入资金视野",
        )
    return {
        "judgment_type": "core_candidate",
        "date": _review_date(result, record),
        "is_correct": correctness,
        "missing_fields": missing_fields,
        "mistake": mistake,
    }


def _fallback_market_state_review(record):
    return {
        "judgment_type": "market_state",
        "date": _review_date({}, record),
        "is_correct": None,
        "missing_fields": ["market_state_review"],
        "mistake": "",
    }


def _fallback_reviews_from_existing_ledger_fields(record):
    return [
        _fallback_market_state_review(record),
        _fallback_mainline_review(record),
        _fallback_core_candidate_review(record),
    ]


def _iter_review_rows(index):
    for records in (index or {}).get("by_stock_code", {}).values():
        for record in list(records or []):
            explicit = _record_judgment_reviews(record)
            for row in explicit:
                yield row
            explicit_types = {row["judgment_type"] for row in explicit}
            for row in _fallback_reviews_from_existing_ledger_fields(record):
                if row["judgment_type"] not in explicit_types:
                    yield row
            for row in _fallback_reviews_from_participation(record):
                if row["judgment_type"] not in explicit_types:
                    yield row


def _record_trade_dates(record):
    dates = []
    for key in ("report_date", "cycle_start_trade_date", "first_seen_trade_date", "latest_trade_date"):
        text = _clean_text((record or {}).get(key))
        if text and text not in dates:
            dates.append(text)
    for mention in list((record or {}).get("mentions") or []):
        text = _clean_text((mention or {}).get("mention_trade_date"))
        if text and text not in dates:
            dates.append(text)
    return dates


def _all_trade_dates(index):
    dates = []
    for key in ("available_trade_dates", "trade_dates"):
        for date in list((index or {}).get(key) or []):
            text = _clean_text(date)
            if text and text not in dates:
                dates.append(text)
    for snapshot in list((index or {}).get("snapshots") or []):
        if isinstance(snapshot, dict):
            text = _clean_text(snapshot.get("trade_date") or snapshot.get("date"))
        else:
            text = _clean_text(snapshot)
        if text and text not in dates:
            dates.append(text)
    for records in (index or {}).get("by_stock_code", {}).values():
        for record in list(records or []):
            for text in _record_trade_dates(record):
                if text and text not in dates:
                    dates.append(text)
    return sorted(dates)


def _previous_trade_date(index, target_date):
    target_date = _clean_text(target_date)
    dates = [date for date in _all_trade_dates(index) if date < target_date]
    return dates[-1] if dates else ""


def _recent_settled_trade_dates(index, target_date, recent_days=5):
    target_date = _clean_text(target_date)
    dates = [date for date in _all_trade_dates(index) if date < target_date]
    return dates[-int(recent_days or 5) :]


def _rows_for_dates(rows, dates):
    date_set = {_clean_text(date) for date in dates if _clean_text(date)}
    return [row for row in rows if _clean_text(row.get("date")) in date_set]


def _summary_rows_for_dates(rows, dates):
    filtered = _rows_for_dates(rows, dates)
    grouped = {item["judgment_type"]: [] for item in JUDGMENT_TYPES}
    for row in filtered:
        judgment_type = row.get("judgment_type")
        if judgment_type in grouped:
            grouped[judgment_type].append(row)
    return [{**item, **_summarize_rows(grouped[item["judgment_type"]])} for item in JUDGMENT_TYPES]


def _summarize_rows(rows):
    dates = sorted({_clean_text(row.get("date")) for row in rows if _clean_text(row.get("date"))})
    sample_rows = [row for row in rows if row.get("is_correct") is not None]
    correct_rows = [row for row in sample_rows if row.get("is_correct") is True]
    wrong_rows = [row for row in sample_rows if row.get("is_correct") is False]
    missing_rows = [row for row in rows if row.get("is_correct") is None]
    accuracy = None
    if sample_rows:
        accuracy = round(len(correct_rows) / len(sample_rows) * 100, 2)
    latest_mistake = ""
    for row in sorted(wrong_rows, key=lambda item: _clean_text(item.get("date")), reverse=True):
        latest_mistake = _clean_text(row.get("mistake"))
        if latest_mistake:
            break
    missing_fields = []
    for row in missing_rows:
        missing_fields = _merge_missing_fields(missing_fields, row.get("missing_fields"))
    return {
        "sample_count": len(sample_rows),
        "correct_count": len(correct_rows),
        "wrong_count": len(wrong_rows),
        "missing_fact_count": len(missing_rows),
        "accuracy_pct": accuracy,
        "start_date": dates[0] if dates else None,
        "end_date": dates[-1] if dates else None,
        "latest_mistake": latest_mistake,
        "missing_fields": missing_fields,
    }


def _first_text(*values):
    for value in values:
        if isinstance(value, dict):
            continue
        text = _clean_text(value)
        if text:
            return text
    return ""


def _stock_label(item):
    if not isinstance(item, dict):
        return ""
    name = _clean_text(item.get("stock_name") or item.get("name"))
    code = _clean_text(item.get("stock_code") or item.get("code"))
    if name and code:
        return f"{name}({code})"
    return name or code


def _target_date_records(index, target_date):
    target_date = _clean_text(target_date)
    records = []
    for stock_records in (index or {}).get("by_stock_code", {}).values():
        for record in list(stock_records or []):
            mention_dates = [
                _clean_text((mention or {}).get("mention_trade_date"))
                for mention in list(record.get("mentions") or [])
            ]
            if target_date in mention_dates or _clean_text(record.get("report_date")) == target_date:
                records.append(record)
    return records


def _current_core_candidates(index, target_date, current_context):
    candidates = []
    for item in list((current_context or {}).get("core_candidates") or []):
        label = _stock_label(item)
        if label and label not in candidates:
            candidates.append(label)
    for key in ("selected_candidate", "selected_position_candidate", "best_stock"):
        label = _stock_label((current_context or {}).get(key))
        if label and label not in candidates:
            candidates.append(label)
    for record in _target_date_records(index, target_date):
        label = _stock_label(record)
        if label and label not in candidates:
            candidates.append(label)
    return candidates[:5]


def _planned_payloads(index, target_date, current_context):
    payloads = []
    for item in list((current_context or {}).get("core_candidates") or []):
        if isinstance(item, dict):
            for key in ("planned_participation", "participation_script"):
                payload = item.get(key)
                if isinstance(payload, dict) and payload:
                    payloads.append(payload)
    for key in ("selected_candidate", "selected_position_candidate", "best_stock"):
        item = (current_context or {}).get(key)
        if isinstance(item, dict):
            for subkey in ("planned_participation", "participation_script"):
                payload = item.get(subkey)
                if isinstance(payload, dict) and payload:
                    payloads.append(payload)
    for record in _target_date_records(index, target_date):
        payload = record.get("planned_participation")
        if isinstance(payload, dict) and payload:
            payloads.append(payload)
        for mention in list(record.get("mentions") or []):
            payload = (mention or {}).get("planned_participation")
            if isinstance(payload, dict) and payload:
                payloads.append(payload)
    return payloads


def _current_participation_text(index, target_date, current_context):
    text = _clean_text((current_context or {}).get("participation_rehearsal"))
    if text:
        return text
    for payload in _planned_payloads(index, target_date, current_context):
        window = _first_text(payload.get("buy_window"), payload.get("participation_window"), payload.get("window"))
        required_steps = " / ".join(_clean_text(item) for item in list(payload.get("required_steps") or []) if _clean_text(item))
        if window and required_steps:
            return f"{window}看{required_steps}"
        if window:
            return f"{window}看竞价、开盘承接、回封质量"
    return "待补事实"


def _current_cancellation_text(index, target_date, current_context):
    text = _clean_text((current_context or {}).get("cancellation_condition"))
    if text:
        return text
    for payload in _planned_payloads(index, target_date, current_context):
        text = _first_text(payload.get("cancellation"), payload.get("cancel_condition"), payload.get("ma20_invalidation"))
        if text:
            return text
    return "待补事实"


def _today_judgment_rows(index, target_date, current_context=None):
    current_context = current_context or {}
    market_state = _first_text(
        current_context.get("market_state"),
        current_context.get("market_status"),
        current_context.get("market_branch"),
    )
    mainline = _first_text(
        current_context.get("mainline"),
        current_context.get("current_mainline"),
        current_context.get("mainline_name"),
    )
    if mainline in {"暂无", "无", "暂无明确主线", "无确认主线"}:
        mainline = "无确认主线"
    if not market_state:
        market_state = "混沌" if mainline == "无确认主线" else "待补事实"
    core_candidates = _current_core_candidates(index, target_date, current_context)
    participation = _current_participation_text(index, target_date, current_context)
    cancellation = _current_cancellation_text(index, target_date, current_context)
    values = {
        "market_state": {
            "today_judgment": market_state,
            "next_verify": "下一交易日验证进攻/退潮/修复/混沌/冰点是否成立",
        },
        "mainline": {
            "today_judgment": mainline,
            "next_verify": "下一交易日验证资金是否继续选择这条线",
        },
        "core_candidate": {
            "today_judgment": "、".join(core_candidates) if core_candidates else "待补事实",
            "next_verify": "下一交易日验证是否进入资金视野",
        },
        "participation_rehearsal": {
            "today_judgment": participation,
            "next_verify": "下一交易日验证竞价、开盘、回封、分歧路径是否命中",
        },
        "cancellation_condition": {
            "today_judgment": cancellation,
            "next_verify": "下一交易日验证是否避免错误参与",
        },
    }
    return [{**item, **values[item["judgment_type"]]} for item in JUDGMENT_TYPES]


def build_daily_judgment_review_panel(index, target_date, current_context=None, recent_days=5):
    review_rows = list(_iter_review_rows(index))
    recent_dates = _recent_settled_trade_dates(index, target_date, recent_days=recent_days)
    previous_date = _previous_trade_date(index, target_date)
    return {
        "schema_version": "daily_judgment_review_panel.v1",
        "target_date": _clean_text(target_date),
        "previous_trade_date": previous_date,
        "recent_start_date": recent_dates[0] if recent_dates else None,
        "recent_end_date": recent_dates[-1] if recent_dates else None,
        "recent_days": len(recent_dates),
        "recent_rows": _summary_rows_for_dates(review_rows, recent_dates),
        "previous_rows": _summary_rows_for_dates(review_rows, [previous_date] if previous_date else []),
        "today_rows": _today_judgment_rows(index, target_date, current_context=current_context),
    }


def build_five_judgment_statistics(index):
    grouped = {item["judgment_type"]: [] for item in JUDGMENT_TYPES}
    for row in _iter_review_rows(index):
        judgment_type = row.get("judgment_type")
        if judgment_type in grouped:
            grouped[judgment_type].append(row)

    summary_rows = []
    all_dates = []
    total_samples = 0
    total_missing = 0
    for item in JUDGMENT_TYPES:
        rows = grouped[item["judgment_type"]]
        summary = _summarize_rows(rows)
        all_dates.extend([date for date in (summary.get("start_date"), summary.get("end_date")) if date])
        total_samples += int(summary.get("sample_count") or 0)
        total_missing += int(summary.get("missing_fact_count") or 0)
        summary_rows.append({**item, **summary})

    sorted_dates = sorted(set(all_dates))
    return {
        "schema_version": "five_judgment_statistics.v1",
        "sample_count": total_samples,
        "missing_fact_count": total_missing,
        "start_date": sorted_dates[0] if sorted_dates else None,
        "end_date": sorted_dates[-1] if sorted_dates else None,
        "rows": summary_rows,
    }


def _format_accuracy(value):
    if value is None:
        return "待补事实"
    return f"{float(value):.2f}%"


def _format_settlement_result(row):
    if int(row.get("wrong_count") or 0) > 0:
        return "错误"
    if int(row.get("correct_count") or 0) > 0:
        if int(row.get("missing_fact_count") or 0) > 0:
            return "部分正确"
        return "正确"
    return "待补事实"


def _has_settlement(row):
    return int(row.get("correct_count") or 0) > 0 or int(row.get("wrong_count") or 0) > 0


def render_daily_judgment_review_panel_lines(panel):
    panel = panel or {}
    lines = ["## 判断纠偏与今日五项结论"]
    recent_start = _clean_text(panel.get("recent_start_date"))
    recent_end = _clean_text(panel.get("recent_end_date"))
    recent_days = int(panel.get("recent_days") or 0)
    if recent_start and recent_end:
        lines.append(f"### 近{recent_days}个已结算交易日正确率（{recent_start}至{recent_end}）")
    else:
        lines.append("### 近5个已结算交易日正确率")
    lines.append("| 判断项 | 样本 | 正确 | 错误 | 待补事实 | 正确率 | 最近错因 |")
    lines.append("|--------|------|------|------|----------|--------|----------|")
    for row in list(panel.get("recent_rows") or []):
        lines.append(
            "| {label} | {sample_count} | {correct_count} | {wrong_count} | {missing_fact_count} | {accuracy_pct} | {latest_mistake} |".format(
                label=_clean_markdown_cell(row.get("label")),
                sample_count=int(row.get("sample_count") or 0),
                correct_count=int(row.get("correct_count") or 0),
                wrong_count=int(row.get("wrong_count") or 0),
                missing_fact_count=int(row.get("missing_fact_count") or 0),
                accuracy_pct=_clean_markdown_cell(_format_accuracy(row.get("accuracy_pct"))),
                latest_mistake=_clean_markdown_cell(row.get("latest_mistake"), "-"),
            )
        )
    previous_date = _clean_text(panel.get("previous_trade_date"))
    lines.append("")
    lines.append(f"### 结算上一交易日：{previous_date or '待补事实'}")
    resolved_previous_rows = [row for row in list(panel.get("previous_rows") or []) if _has_settlement(row)]
    unresolved_previous_rows = [row for row in list(panel.get("previous_rows") or []) if not _has_settlement(row)]
    lines.append("| 判断项 | 样本 | 正确 | 错误 | 结算 | 错在哪 |")
    lines.append("|--------|------|------|------|------|--------|")
    if not resolved_previous_rows:
        lines.append("| 暂无已结算项 | 0 | 0 | 0 | 未结算 | - |")
    for row in resolved_previous_rows:
        lines.append(
            "| {label} | {sample_count} | {correct_count} | {wrong_count} | {result} | {latest_mistake} |".format(
                label=_clean_markdown_cell(row.get("label")),
                sample_count=int(row.get("sample_count") or 0),
                correct_count=int(row.get("correct_count") or 0),
                wrong_count=int(row.get("wrong_count") or 0),
                result=_format_settlement_result(row),
                latest_mistake=_clean_markdown_cell(row.get("latest_mistake"), "-"),
            )
        )
    if unresolved_previous_rows:
        lines.append("")
        lines.append("### 上一交易日未完成结算")
        lines.append("| 判断项 | 待补数量 | 缺少事实 |")
        lines.append("|--------|----------|----------|")
        for row in unresolved_previous_rows:
            missing_fields = "、".join(row.get("missing_fields") or []) or "review_fact"
            lines.append(
                "| {label} | {missing_fact_count} | {missing_fields} |".format(
                    label=_clean_markdown_cell(row.get("label")),
                    missing_fact_count=int(row.get("missing_fact_count") or 0),
                    missing_fields=_clean_markdown_cell(missing_fields),
                )
            )
    target_date = _clean_text(panel.get("target_date"))
    lines.append("")
    lines.append(f"### 今日判断（{target_date or '待补事实'}，等待下一交易日验证）")
    lines.append("| 判断项 | 今日结论 | 下一交易日验证点 |")
    lines.append("|--------|----------|------------------|")
    for row in list(panel.get("today_rows") or []):
        lines.append(
            "| {label} | {today_judgment} | {next_verify} |".format(
                label=_clean_markdown_cell(row.get("label")),
                today_judgment=_clean_markdown_cell(row.get("today_judgment"), "待补事实"),
                next_verify=_clean_markdown_cell(row.get("next_verify"), "待补事实"),
            )
        )
    lines.append("")
    return lines


def render_five_judgment_statistics_lines(stats):
    stats = stats or {}
    rows = list(stats.get("rows") or [])
    lines = ["**五项判断复盘统计表**:"]
    sample_count = int(stats.get("sample_count") or 0)
    start_date = _clean_text(stats.get("start_date"))
    end_date = _clean_text(stats.get("end_date"))
    if sample_count and start_date and end_date:
        lines.append(f"- 当前可复盘样本：{sample_count}条，覆盖{start_date}至{end_date}。")
    else:
        lines.append("- 当前可复盘样本：待补事实。")
    lines.append("> 历史复盘只统计过去判断，不作为明日新增参与依据。")
    lines.append("")
    lines.append("| 判断项 | 统计口径 | 样本 | 正确 | 错误 | 待补事实 | 正确率 | 错在哪 |")
    lines.append("|--------|----------|------|------|------|----------|--------|--------|")
    if not rows:
        rows = [{**item, **_summarize_rows([])} for item in JUDGMENT_TYPES]
    for row in rows:
        lines.append(
            "| {label} | {metric_definition} | {sample_count} | {correct_count} | {wrong_count} | {missing_fact_count} | {accuracy_pct} | {latest_mistake} |".format(
                label=_clean_markdown_cell(row.get("label")),
                metric_definition=_clean_markdown_cell(row.get("metric_definition")),
                sample_count=int(row.get("sample_count") or 0),
                correct_count=int(row.get("correct_count") or 0),
                wrong_count=int(row.get("wrong_count") or 0),
                missing_fact_count=int(row.get("missing_fact_count") or 0),
                accuracy_pct=_clean_markdown_cell(_format_accuracy(row.get("accuracy_pct"))),
                latest_mistake=_clean_markdown_cell(row.get("latest_mistake"), "-"),
            )
        )
    lines.append("")
    return lines


__all__ = [
    "JUDGMENT_TYPES",
    "build_daily_judgment_review_panel",
    "build_five_judgment_statistics",
    "render_daily_judgment_review_panel_lines",
    "render_five_judgment_statistics_lines",
]
