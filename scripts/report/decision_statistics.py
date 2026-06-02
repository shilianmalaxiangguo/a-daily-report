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
        "metric_definition": "首选主目标是否被次日承接验证，备用不抵消主目标失败",
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
DAILY_JUDGMENT_TYPE_KEYS = {"market_state", "mainline", "core_candidate"}
_HIT_REVIEW_STATUSES = {"预演命中", "错过后方案命中"}
_MISS_REVIEW_STATUSES = {"预演作废", "预演过早", "主目标不可成交"}
_WAITING_REVIEW_STATUSES = {"", "等待复盘", "等待窗口复盘", "等待事实", "待补事实"}
_MARKET_STATE_BUCKETS = {"进攻", "退潮", "修复", "混沌", "冰点"}
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
    return text


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


def _split_expected_actual_from_reason(text):
    text = _clean_text(text)
    if not text:
        return "", ""
    markers = (
        ("预判", "，次日实际为"),
        ("预判", "，实际为"),
        ("预期", "，实际"),
        ("预期", "实际"),
    )
    for expected_marker, actual_marker in markers:
        if expected_marker not in text or actual_marker not in text:
            continue
        expected_part = text.split(expected_marker, 1)[1].split(actual_marker, 1)[0]
        actual_part = text.split(actual_marker, 1)[1]
        for separator in ("；", "，", "。", "、"):
            actual_part = actual_part.split(separator, 1)[0]
        return _clean_text(expected_part), _clean_text(actual_part)
    return "", ""


def _distinct_review_reason(judgment_type, correctness, actual, reason, *, default_reason=""):
    actual_text = _clean_text(actual)
    reason_text = _clean_text(reason)
    if not actual_text or not reason_text or actual_text != reason_text or len(reason_text) < 40:
        return reason_text
    if judgment_type == "core_candidate" and correctness is True:
        return "候选进入次日资金视野，判断成立"
    if correctness is True:
        return "实际反馈证明判断成立"
    if correctness is False:
        return _clean_text(default_reason, "实际反馈与预期不一致")
    return "实际反馈已列在实际列，原因待复盘补充"


def _review_detail_fields(item, correctness=None, *, default_reason=""):
    item = item or {}
    mistake = _mistake_text(item)
    expected = _first_text(
        item.get("expected"),
        item.get("expectation"),
        item.get("prediction"),
        item.get("predicted"),
        item.get("today_judgment"),
        item.get("planned"),
    )
    actual = _first_text(
        item.get("actual"),
        item.get("actual_result"),
        item.get("actual_judgment"),
        item.get("review_result"),
        item.get("outcome"),
    )
    if not expected or not actual:
        inferred_expected, inferred_actual = _split_expected_actual_from_reason(mistake)
        expected = expected or inferred_expected
        actual = actual or inferred_actual
    reason = _first_text(
        item.get("reason"),
        item.get("review_reason"),
        item.get("evidence"),
        mistake,
        default_reason,
    )
    if correctness is True and not reason:
        reason = "符合预期"
    reason = _distinct_review_reason(
        _clean_text(item.get("judgment_type") or item.get("type") or item.get("key")),
        correctness,
        actual,
        reason,
        default_reason=default_reason,
    )
    return {
        "expected": expected,
        "actual": actual,
        "reason": reason,
    }


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
    mistake = "" if correctness is not False else _mistake_text(item, "判断未被次日事实验证")
    detail = _review_detail_fields(item, correctness, default_reason=mistake)
    return {
        "judgment_type": judgment_type,
        "date": _review_date(item, record, mention),
        "is_correct": correctness,
        "missing_fields": missing_fields,
        "mistake": mistake,
        "expected": detail["expected"],
        "actual": detail["actual"],
        "reason": detail["reason"],
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
                "expected": _clean_text((review or {}).get("expected") or "预演路径按计划展开"),
                "actual": _clean_text((review or {}).get("actual") or status),
                "reason": _clean_text((review or {}).get("reason") or mistake or status),
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
                    "expected": "取消条件出现时回到0%不参与",
                    "actual": status,
                    "reason": _clean_text((review or {}).get("reason") or status),
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
    expected = _clean_text(
        record.get("mainline")
        or ((record.get("hypothesis") or {}).get("sector_candidate") if isinstance(record.get("hypothesis"), dict) else "")
        or "预判方向延续"
    )
    actual = _clean_text(
        validation.get("actual")
        or validation.get("status")
        or validation.get("sector_selection_evidence")
        or record.get("status")
    )
    return {
        "judgment_type": "mainline",
        "date": _review_date({}, record),
        "is_correct": correctness,
        "missing_fields": missing_fields,
        "mistake": mistake,
        "expected": expected,
        "actual": actual,
        "reason": mistake or _clean_text(validation.get("sector_selection_evidence") or validation.get("selection_confirmed_evidence")),
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
    expected = _clean_text(
        result.get("expected")
        or record.get("stock_name")
        or record.get("stock_code")
        or "预判候选进入资金视野"
    )
    actual = _clean_text(result.get("actual") or result.get("evidence") or validation.get("stock_acceptance_evidence") or status)
    if correctness is True:
        reason = "候选进入次日资金视野，判断成立"
    elif correctness is False:
        reason = mistake or "候选没有进入次日资金视野"
    else:
        reason = actual
    return {
        "judgment_type": "core_candidate",
        "date": _review_date(result, record),
        "is_correct": correctness,
        "missing_fields": missing_fields,
        "mistake": mistake,
        "expected": expected,
        "actual": actual,
        "reason": reason,
    }


def _fallback_market_state_review(record):
    return {
        "judgment_type": "market_state",
        "date": _review_date({}, record),
        "is_correct": None,
        "missing_fields": ["market_state_review"],
        "mistake": "",
        "expected": "",
        "actual": "",
        "reason": "缺少市场状态复盘事实",
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


def _rows_before_target_date(rows, target_date):
    target_date = _clean_text(target_date)
    if not target_date:
        return list(rows or [])
    filtered = []
    for row in list(rows or []):
        row_date = _clean_text((row or {}).get("date"))
        if row_date and row_date < target_date:
            filtered.append(row)
    return filtered


def _summary_rows_for_dates(rows, dates):
    filtered = _rows_for_dates(rows, dates)
    grouped = {item["judgment_type"]: [] for item in JUDGMENT_TYPES}
    for row in filtered:
        judgment_type = row.get("judgment_type")
        if judgment_type in grouped:
            grouped[judgment_type].append(row)
    return [
        {**item, **_summarize_rows(grouped[item["judgment_type"]], judgment_type=item["judgment_type"])}
        for item in JUDGMENT_TYPES
    ]


def _detail_from_group(group_rows, *, date="", judgment_type=""):
    group_rows = list(group_rows or [])
    sample_rows = [row for row in group_rows if row.get("is_correct") is not None]
    wrong_rows = [row for row in sample_rows if row.get("is_correct") is False]
    missing_rows = [row for row in group_rows if row.get("is_correct") is None]
    if wrong_rows:
        selected = wrong_rows[0]
        result = "错误"
    elif sample_rows:
        selected = sample_rows[0]
        result = "正确"
    elif missing_rows:
        selected = missing_rows[0]
        result = "待补事实"
    else:
        selected = {}
        result = "待补事实"
    missing_fields = _merge_missing_fields(selected.get("missing_fields"))
    reason = _first_text(
        selected.get("reason"),
        selected.get("mistake"),
        selected.get("evidence"),
        f"缺少事实：{'、'.join(missing_fields)}" if missing_fields else "",
        "符合预期" if result == "正确" else "",
    )
    return {
        "date": _clean_text(date or selected.get("date")),
        "judgment_type": judgment_type or _clean_text(selected.get("judgment_type")),
        "result": result,
        "expected": _first_text(selected.get("expected"), "-"),
        "actual": _first_text(selected.get("actual"), "-"),
        "reason": reason or "-",
    }


def _detail_rows_for_dates(rows, dates):
    filtered = _rows_for_dates(rows, dates)
    grouped = {}
    for row in filtered:
        date = _clean_text((row or {}).get("date"))
        judgment_type = _clean_text((row or {}).get("judgment_type"))
        if not date or judgment_type not in JUDGMENT_TYPE_KEYS:
            continue
        grouped.setdefault((date, judgment_type), []).append(row)
    details = []
    for date in [_clean_text(item) for item in dates if _clean_text(item)]:
        for judgment in JUDGMENT_TYPES:
            key = (date, judgment["judgment_type"])
            if key not in grouped:
                continue
            details.append({**judgment, **_detail_from_group(grouped[key], date=date, judgment_type=judgment["judgment_type"])})
    return details


def _summarize_rows(rows, *, judgment_type=""):
    daily_groups = {}
    for idx, row in enumerate(list(rows or [])):
        row_date = _clean_text((row or {}).get("date"))
        group_key = row_date if judgment_type in DAILY_JUDGMENT_TYPE_KEYS and row_date else f"__row_{idx}"
        daily_groups.setdefault(group_key, {"date": row_date, "rows": []})["rows"].append(row)

    dates = sorted({group["date"] for group in daily_groups.values() if group["date"]})
    sample_count = 0
    correct_count = 0
    wrong_count = 0
    missing_fact_count = 0
    wrong_rows = []
    missing_fields = []
    detail_groups = []
    for group in daily_groups.values():
        group_rows = list(group["rows"])
        detail_groups.append(_detail_from_group(group_rows, date=group.get("date"), judgment_type=judgment_type))
        sample_rows = [row for row in group_rows if row.get("is_correct") is not None]
        missing_rows = [row for row in group_rows if row.get("is_correct") is None]
        if sample_rows:
            sample_count += 1
            group_wrong_rows = [row for row in sample_rows if row.get("is_correct") is False]
            if group_wrong_rows:
                wrong_count += 1
                wrong_rows.extend(group_wrong_rows)
            else:
                correct_count += 1
        if missing_rows:
            missing_fact_count += 1
            for row in missing_rows:
                missing_fields = _merge_missing_fields(missing_fields, row.get("missing_fields"))
    accuracy = None
    if sample_count:
        accuracy = round(correct_count / sample_count * 100, 2)
    latest_mistake = ""
    for row in sorted(wrong_rows, key=lambda item: _clean_text(item.get("date")), reverse=True):
        latest_mistake = _clean_text(row.get("mistake"))
        if latest_mistake:
            break
    latest_detail = {}
    for detail in sorted(detail_groups, key=lambda item: _clean_text(item.get("date")), reverse=True):
        if detail.get("result") in {"正确", "错误"}:
            latest_detail = detail
            break
    if not latest_detail and detail_groups:
        latest_detail = sorted(detail_groups, key=lambda item: _clean_text(item.get("date")), reverse=True)[0]
    return {
        "sample_count": sample_count,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "missing_fact_count": missing_fact_count,
        "accuracy_pct": accuracy,
        "start_date": dates[0] if dates else None,
        "end_date": dates[-1] if dates else None,
        "latest_mistake": latest_mistake,
        "missing_fields": missing_fields,
        "latest_result": latest_detail.get("result", "待补事实"),
        "latest_expected": latest_detail.get("expected", "-"),
        "latest_actual": latest_detail.get("actual", "-"),
        "latest_reason": latest_detail.get("reason", latest_mistake or "-"),
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


def _is_core_judgment_candidate(item):
    if not isinstance(item, dict):
        return True
    nested_reversal = item.get("anchor_reversal") if isinstance(item.get("anchor_reversal"), dict) else {}
    decision = _first_text(item.get("anchor_reversal_decision"), nested_reversal.get("anchor_reversal_decision"))
    sniper_role = _clean_text(item.get("sniper_role"))
    if bool(item.get("primary_buy_candidate")) or bool(item.get("backup_buy_candidate")):
        return True
    if decision in {"可作为主对象", "可作为补位"}:
        return True
    if sniper_role in {"明日主买对象", "明日补位对象"}:
        return True
    if decision in {"降级观察", "不参与"}:
        return False
    if "候选观察" in sniper_role or "修复观察" in sniper_role:
        return False
    has_anchor_payload = any(
        _clean_text(item.get(key))
        for key in (
            "sector_anchor",
            "candidate_role",
            "relationship_to_anchor",
            "repair_priority",
        )
    )
    return not has_anchor_payload


def _current_core_candidates(index, target_date, current_context):
    candidates = []
    current_items = []
    for item in list((current_context or {}).get("core_candidates") or []):
        if isinstance(item, dict) and _stock_label(item):
            current_items.append(item)
    for key in ("selected_candidate", "selected_position_candidate", "best_stock"):
        item = (current_context or {}).get(key)
        if isinstance(item, dict) and _stock_label(item):
            current_items.append(item)
    for item in current_items:
        if not _is_core_judgment_candidate(item):
            continue
        label = _stock_label(item)
        if label and label not in candidates:
            candidates.append(label)
    if current_items:
        return candidates[:5]
    for record in _target_date_records(index, target_date):
        if not _is_core_judgment_candidate(record):
            continue
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
    else:
        market_state = _normalize_market_state_bucket(market_state)
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
        "recent_detail_rows": _detail_rows_for_dates(review_rows, recent_dates),
        "previous_rows": _summary_rows_for_dates(review_rows, [previous_date] if previous_date else []),
        "today_rows": _today_judgment_rows(index, target_date, current_context=current_context),
    }


def build_five_judgment_statistics(index, target_date=None):
    grouped = {item["judgment_type"]: [] for item in JUDGMENT_TYPES}
    for row in _rows_before_target_date(list(_iter_review_rows(index)), target_date):
        judgment_type = row.get("judgment_type")
        if judgment_type in grouped:
            grouped[judgment_type].append(row)

    summary_rows = []
    all_dates = []
    total_samples = 0
    total_missing = 0
    for item in JUDGMENT_TYPES:
        rows = grouped[item["judgment_type"]]
        summary = _summarize_rows(rows, judgment_type=item["judgment_type"])
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
        return "正确"
    return "待补事实"


def _strip_stock_code_suffix(text):
    text = _clean_text(text)
    for left in ("(", "（"):
        if left in text:
            return _clean_text(text.split(left, 1)[0])
    return text


def _first_signed_pct_segment(text):
    text = _clean_text(text)
    positions = [index for index in (text.find("+"), text.find("-")) if index >= 0]
    if not positions:
        return ""
    return text[min(positions) :].split("，", 1)[0]


def _compact_core_primary_actual(text):
    primary_part = text.split("；", 1)[0]
    primary_tail = primary_part.removeprefix("主目标")
    primary_name = _strip_stock_code_suffix(primary_tail.split("次日", 1)[0])
    primary_pct = _first_signed_pct_segment(primary_tail)
    leader_part = ""
    for part in text.split("；"):
        if part.startswith("更强同方向："):
            leader_part = part.split("：", 1)[1]
            break
    leader_name = _strip_stock_code_suffix(leader_part)
    leader_pct = _first_signed_pct_segment(leader_part)
    if primary_name and primary_pct and leader_name and leader_pct:
        return f"主目标{primary_name}{primary_pct} / {leader_name}{leader_pct}"
    if primary_name and primary_pct:
        return f"主目标{primary_name}{primary_pct}"
    return text


def _compact_review_actual(judgment_type, actual):
    text = _clean_text(actual)
    if len(text) < 40:
        return text
    if judgment_type == "core_candidate":
        if "主目标" in text:
            return _compact_core_primary_actual(text)
        if "未进入资金视野" in text:
            return "未进入资金视野"
        return "候选进入次日资金视野"
    return text


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
    lines.append("| 判断项 | 正确率 | 最近结论 | 预期 | 实际 | 原因 |")
    lines.append("|--------|--------|----------|------|------|------|")
    for row in list(panel.get("recent_rows") or []):
        lines.append(
            "| {label} | {accuracy_pct} | {latest_result} | {expected} | {actual} | {reason} |".format(
                label=_clean_markdown_cell(row.get("label")),
                accuracy_pct=_clean_markdown_cell(_format_accuracy(row.get("accuracy_pct"))),
                latest_result=_clean_markdown_cell(row.get("latest_result"), "待补事实"),
                expected=_clean_markdown_cell(row.get("latest_expected"), "-"),
                actual=_clean_markdown_cell(
                    _compact_review_actual(row.get("judgment_type"), row.get("latest_actual")),
                    "-",
                ),
                reason=_clean_markdown_cell(row.get("latest_reason"), "-"),
            )
        )
    detail_rows = list(panel.get("recent_detail_rows") or [])
    lines.append("")
    lines.append("### 最近5日判断明细")
    lines.append("| 日期 | 判断项 | 结论 | 预期 | 实际 | 原因 |")
    lines.append("|------|--------|------|------|------|------|")
    if not detail_rows:
        lines.append("| 待补事实 | 暂无已结算项 | 待补事实 | - | - | - |")
    for row in detail_rows:
        lines.append(
            "| {date} | {label} | {result} | {expected} | {actual} | {reason} |".format(
                date=_clean_markdown_cell(row.get("date"), "待补事实"),
                label=_clean_markdown_cell(row.get("label")),
                result=_clean_markdown_cell(row.get("result"), "待补事实"),
                expected=_clean_markdown_cell(row.get("expected"), "-"),
                actual=_clean_markdown_cell(row.get("actual"), "-"),
                reason=_clean_markdown_cell(row.get("reason"), "-"),
            )
        )
    previous_date = _clean_text(panel.get("previous_trade_date"))
    lines.append("")
    lines.append(f"### 结算上一交易日：{previous_date or '待补事实'}")
    resolved_previous_rows = [row for row in list(panel.get("previous_rows") or []) if _has_settlement(row)]
    unresolved_previous_rows = [
        row for row in list(panel.get("previous_rows") or []) if int(row.get("missing_fact_count") or 0) > 0
    ]
    lines.append("| 判断项 | 结论 | 预期 | 实际 | 原因 |")
    lines.append("|--------|------|------|------|------|")
    if not resolved_previous_rows:
        lines.append("| 暂无已结算项 | 未结算 | - | - | - |")
    for row in resolved_previous_rows:
        lines.append(
            "| {label} | {result} | {expected} | {actual} | {reason} |".format(
                label=_clean_markdown_cell(row.get("label")),
                result=_format_settlement_result(row),
                expected=_clean_markdown_cell(row.get("latest_expected"), "-"),
                actual=_clean_markdown_cell(
                    _compact_review_actual(row.get("judgment_type"), row.get("latest_actual")),
                    "-",
                ),
                reason=_clean_markdown_cell(row.get("latest_reason"), "-"),
            )
        )
    if unresolved_previous_rows:
        lines.append("")
        lines.append("### 上一交易日未完成结算")
        lines.append("| 判断项 | 状态 | 缺少事实 |")
        lines.append("|--------|------|----------|")
        for row in unresolved_previous_rows:
            missing_fields = "、".join(row.get("missing_fields") or []) or "review_fact"
            lines.append(
                "| {label} | 待补事实 | {missing_fields} |".format(
                    label=_clean_markdown_cell(row.get("label")),
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
    start_date = _clean_text(stats.get("start_date"))
    end_date = _clean_text(stats.get("end_date"))
    if start_date and end_date:
        lines.append(f"- 统计范围：{start_date}至{end_date}。")
    else:
        lines.append("- 统计范围：待补事实。")
    lines.append("> 历史复盘只统计过去判断，不作为明日新增参与依据。")
    lines.append("")
    lines.append("| 判断项 | 统计口径 | 正确率 | 最近结论 | 预期 | 实际 | 原因 |")
    lines.append("|--------|----------|--------|----------|------|------|------|")
    if not rows:
        rows = [{**item, **_summarize_rows([])} for item in JUDGMENT_TYPES]
    for row in rows:
        result = _clean_text(row.get("latest_result")) or _format_settlement_result(row)
        missing_fields = "、".join(row.get("missing_fields") or [])
        reason = _first_text(
            row.get("latest_reason"),
            row.get("latest_mistake"),
            f"缺少事实：{missing_fields}" if missing_fields else "",
            "符合预期" if result == "正确" else "",
            "-",
        )
        lines.append(
            "| {label} | {metric_definition} | {accuracy_pct} | {latest_result} | {expected} | {actual} | {reason} |".format(
                label=_clean_markdown_cell(row.get("label")),
                metric_definition=_clean_markdown_cell(row.get("metric_definition")),
                accuracy_pct=_clean_markdown_cell(_format_accuracy(row.get("accuracy_pct"))),
                latest_result=_clean_markdown_cell(result, "待补事实"),
                expected=_clean_markdown_cell(row.get("latest_expected"), "-"),
                actual=_clean_markdown_cell(
                    _compact_review_actual(row.get("judgment_type"), row.get("latest_actual")),
                    "-",
                ),
                reason=_clean_markdown_cell(reason, "-"),
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
