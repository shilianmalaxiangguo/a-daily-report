from __future__ import annotations


SCHEMA_VERSION = "selection_workflow.v1"
DERIVATION_CONTRACT = "sector_first_strict.v1"
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
    parts = []
    sources = [candidate, nested, planned, script]
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
    for source in (_as_dict(candidate), _as_dict(candidate.get("planned_participation")), _as_dict(candidate.get("participation_script"))):
        for key in ("participation_window", "buy_window", "execution_window", "window"):
            value = clean_visible_text(source.get(key))
            if any(marker in value for marker in EXECUTION_WINDOW_MARKERS):
                return True
    return False


def _candidate_has_invalid_condition(candidate):
    text = _candidate_contract_text(candidate, include_quote=False)
    if any(marker in text for marker in ("作废", "取消", "失效", "认错线", "跌破", "站不回", "封死", "打不开")):
        return True
    for source in (_as_dict(candidate), _as_dict(candidate.get("planned_participation")), _as_dict(candidate.get("participation_script"))):
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


def _candidate_blocks_new_entry_by_price(candidate):
    reason = _candidate_limit_down_block_reason(candidate)
    if reason:
        if _candidate_has_explicit_limit_down_reversal_plan(candidate):
            return ""
        return reason
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
        pct = int(float(str(raw or 0).replace("%", "").strip() or 0))
    except (TypeError, ValueError):
        pct = 0
    if pct >= 100:
        return 100
    if pct >= 50:
        return 50
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


def _sector_anchor_keys(context):
    keys = set()
    context = _as_dict(context)
    for item in _as_list(context.get("sector_trend_snapshot")):
        if not isinstance(item, dict):
            continue
        for key in ("anchor_code", "anchor_name", "leader_code", "leader_name", "core_code", "core_name"):
            value = clean_visible_text(item.get(key))
            if value:
                keys.add(normalize_stock_code(value) if any(ch.isdigit() for ch in value) else value)
    return keys


def _candidate_has_legacy_signal(candidate):
    return _text_has_any(_candidate_text_blob(candidate), LEGACY_SIGNAL_MARKERS)


def _candidate_has_sector_derivation(source_key, candidate, context):
    candidate = _as_dict(candidate)
    source_key = clean_text(source_key)
    if "sector_derived_candidates" in source_key or "sector_leader_candidates" in source_key:
        return True
    if clean_visible_text(candidate.get("sector_derivation_evidence")):
        return True
    role = clean_visible_text(candidate.get("candidate_role") or candidate.get("core_identity"))
    source_pools = [
        clean_visible_text(item)
        for item in (candidate.get("source_pools") or [])
        if clean_visible_text(item)
    ]
    if role in {"板块锚", "主线核心", "core"}:
        return True
    if any(_text_has_any(pool, ("主线核心", "板块锚", "板块发酵", "市场选择", "容量核心")) for pool in source_pools):
        return True
    keys = _sector_anchor_keys(context)
    key = stock_key(candidate)
    return bool(key and key in keys)


def _candidate_origin(source_key, candidate, context):
    if clean_text(source_key) == "selected_position_candidate":
        return "manual_observation"
    if "market_emotion_candidates" in clean_text(source_key):
        return "market_emotion_line"
    if _candidate_has_sector_derivation(source_key, candidate, context):
        return "sector_first"
    return "legacy_signal_only"


def _candidate_entry_basis(source_key, candidate, context):
    origin = _candidate_origin(source_key, candidate, context)
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


def _candidate_new_entry_qualified(source_key, candidate, context):
    if _candidate_blocks_new_entry_by_price(candidate):
        return False
    return _candidate_origin(source_key, candidate, context) in {"sector_first", "market_emotion_line"}


def _build_candidate_pool(execution_stage_context, final_stock, selected_position_candidate=None, quote_lookup=None):
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
        candidate_origin = _candidate_origin(source_key, candidate, context)
        new_entry_qualified = _candidate_new_entry_qualified(source_key, candidate, context)
        status = _candidate_status(candidate, final_key)
        eliminated_at = "N6" if status in {"降级观察", "不参与"} else ""
        brooks = _brooks_price_action_judge(candidate)
        price_block_reason = _candidate_blocks_new_entry_by_price(candidate)
        limit_down_block_reason = _candidate_limit_down_block_reason(candidate)
        if price_block_reason and status != "最终执行对象":
            eliminated_at = "N7"
        if status == "最终执行对象":
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
                "entry_basis": _candidate_entry_basis(source_key, candidate, context),
                "candidate_origin": candidate_origin,
                "new_entry_qualified": new_entry_qualified,
                "mainline": clean_visible_text(candidate.get("mainline") or context.get("mainline_name")),
                "sector": clean_visible_text(candidate.get("sector") or candidate.get("sector_name")),
                "current_driver_tags": _candidate_driver_tags(candidate),
                "sector_role": clean_visible_text(candidate.get("candidate_role") or candidate.get("core_identity")),
                "reversal_decision": _anchor_reversal_decision(candidate),
                "leader_debate": _leader_debate(candidate),
                "brooks_price_action_judge": brooks,
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
    selected_key = stock_key(selected_position_candidate)
    if not selected_key:
        return False
    return stock_key(candidate) == selected_key


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


def _candidate_can_be_final_execution_object(candidate, *, source_key="", context=None):
    if _candidate_blocks_new_entry_by_price(candidate):
        return False
    return (
        _anchor_reversal_decision(candidate) == "可作为主对象"
        and _selected_candidate_has_execution_evidence(candidate)
        and _candidate_new_entry_qualified(source_key, candidate, _as_dict(context))
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


def _pick_final_candidate(execution_stage_context, selected_position_candidate=None, position_decision=None, quote_lookup=None):
    if _position_pct(position_decision) <= 0:
        return {}
    context = _as_dict(execution_stage_context)
    sources = _candidate_sources(context)
    if stock_key(selected_position_candidate):
        for source_key, candidate in sources:
            if _candidate_matches_selected(candidate, selected_position_candidate):
                merged = dict(candidate)
                merged.update(
                    {
                        key: value
                        for key, value in _as_dict(selected_position_candidate).items()
                        if value not in (None, "")
                    }
                )
                merged = _candidate_with_quote(merged, quote_lookup)
                if _candidate_can_be_final_execution_object(merged, source_key=source_key, context=context):
                    return stock_payload(merged)
                return {}
        return {}
    for source_key, candidate in sources:
        candidate = _candidate_with_quote(candidate, quote_lookup)
        if _candidate_can_be_final_execution_object(candidate, source_key=source_key, context=context):
            return stock_payload(candidate)
    return {}


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
    if position_pct >= 100:
        return "100%核心进攻"
    if position_pct >= 50:
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
        cap_pct = int(float(str(cap).replace("%", "").strip() or 0))
    except (TypeError, ValueError):
        return position_pct
    return min(position_pct, max(cap_pct, 0))


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
):
    data = _as_dict(data)
    context = _as_dict(execution_stage_context)
    snapshot = _as_dict(market_research_snapshot)
    target_date = clean_text(target_date or data.get("target_date") or snapshot.get("target_date"))
    source_date = clean_text(data.get("source_date") or snapshot.get("source_date") or target_date)
    quote_lookup = _build_quote_lookup(data, context, snapshot, target_date=target_date)
    if _quote_backfill_enabled(data, context, snapshot):
        quote_lookup = _backfill_quote_lookup(
            quote_lookup,
            target_date=target_date,
            execution_stage_context=context,
            selected_position_candidate=selected_position_candidate,
        )
    final_stock = _pick_final_candidate(
        context,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        quote_lookup=quote_lookup,
    )
    missing_fields = _selection_workflow_missing_fields(data, context, snapshot)
    if missing_fields:
        final_stock = {}
    base_position_pct = _position_pct(position_decision) if final_stock else 0
    base_execution_stock = final_stock if base_position_pct else {}
    base_candidate_pool = _build_candidate_pool(context, base_execution_stock, selected_position_candidate)
    premarket_narrative_review = _build_premarket_narrative_review(
        data=data,
        context=context,
        snapshot=snapshot,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        final_target_resolution=final_target_resolution,
        final_stock=final_stock,
        candidate_pool=base_candidate_pool,
        mainline=clean_text(
            context.get("mainline_name")
            or _as_dict(context.get("mainline_turnover_summary")).get("current_mainline"),
            "",
        ),
        base_position_pct=base_position_pct,
    )
    position_pct = _apply_premarket_review_position(base_position_pct, premarket_narrative_review)
    execution_stock = final_stock if position_pct else {}
    candidate_pool = _build_candidate_pool(context, execution_stock, selected_position_candidate, quote_lookup=quote_lookup)
    if premarket_narrative_review:
        final_key = stock_key(final_stock)
        for item in candidate_pool:
            if isinstance(item, dict) and final_key and stock_key(item.get("stock")) == final_key:
                item["premarket_narrative_review"] = dict(premarket_narrative_review)
    conflicts = _selected_candidate_conflicts(context, selected_position_candidate)
    market_state = clean_text(_as_dict(context.get("market_state_snapshot")).get("market_state"), "市场状态待确认")
    mainline = clean_text(
        context.get("mainline_name")
        or _as_dict(context.get("mainline_turnover_summary")).get("current_mainline"),
        "主线待确认",
    )
    market_layer = {
        "market_atmosphere": market_state,
        "profit_effect": clean_text(context.get("profit_effect") or context.get("赚钱效应"), "待确认"),
        "volume_quality": clean_text(context.get("volume_quality") or context.get("成交量质量"), "待确认"),
        "risk_preference": clean_text(context.get("risk_preference") or context.get("风险偏好"), "待确认"),
        "allow_sector_diagnosis": not bool(missing_fields),
    }
    sector_layer = {
        "selected_direction": mainline,
        "sector_fermentation": clean_text(context.get("sector_fermentation") or context.get("板块发酵"), "待确认"),
        "sector_emotion": clean_text(context.get("sector_emotion") or context.get("板块情绪"), "待确认"),
        "turnover_expansion": clean_text(context.get("sector_turnover_expansion") or context.get("板块成交扩散"), "待确认"),
        "backrow_acceptance": clean_text(context.get("backrow_acceptance") or context.get("后排承接"), "待确认"),
    }
    leader_layer = {
        "leader_source": "板块发酵推导" if execution_stock and any(item.get("new_entry_qualified") for item in candidate_pool) else "待确认",
        "leader": stock_label(execution_stock) if execution_stock else "暂无",
        "market_selection_rule": "下一级必须证明承接了上一级资金选择",
    }
    data_completeness = {
        "status": "failed" if missing_fields else "success",
        "missing_fields": missing_fields,
        "action": "关键数据不完整，停止生成" if missing_fields else "继续推导",
    }
    final_label = stock_label(final_stock)
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

    n8_judgement = (
        f"关键数据不完整，停止生成：{'、'.join(missing_fields)}"
        if missing_fields
        else _action_text(base_position_pct)
    )
    n8_source_node = "N8"
    adjusted_action_text = _action_text(position_pct)
    nodes = [
        _node("N0", "数据封装", judgement=f"事实日期：{target_date or '待确认'}", passes_forward={"target_date": target_date}),
        _node("N1", "市场周期判断", input_refs=["N0"], judgement=market_state, passes_forward={"market_layer": market_layer}),
        _node("N2", "资金方向判断", input_refs=["N1"], judgement=f"资金方向：{mainline}", passes_forward={"mainline": mainline, "volume_role": "量能先用于识别资金表态"}),
        _node("N3", "板块关系拆解", input_refs=["N2"], judgement=f"板块方向：{mainline}", passes_forward={"sector_layer": sector_layer}),
        _node("N4", "板块内角色识别", input_refs=["N3"], judgement="识别板块内角色", passes_forward={"leader_layer": leader_layer, "has_sector_roles": bool(context.get("sector_trend_snapshot"))}),
        _node("N5", "候选池归一", input_refs=["N4"], judgement=f"归一候选{len(candidate_pool)}只", passes_forward={"candidate_count": len(candidate_pool)}),
        _node(
            "N6",
            "反推龙头",
            input_refs=["N5"],
            judgement=f"保留对象：{final_label if execution_stock else '无'}",
            passes_forward={
                "execution_object": execution_stock,
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
                "execution_object": execution_stock,
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
                "execution_object": execution_stock,
                "base_position_pct": base_position_pct,
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
    final_failure_conditions = list(missing_fields)
    if premarket_narrative_review and position_pct <= 0 and base_position_pct > 0:
        final_failure_conditions.extend(_clean_list(premarket_narrative_review.get("cancel_conditions")))
        summary = _premarket_review_summary(premarket_narrative_review)
        if summary and summary not in final_failure_conditions:
            final_failure_conditions.append(summary)
    final_reason = _premarket_review_final_reason(premarket_narrative_review)

    return {
        "schema_version": SCHEMA_VERSION,
        "derivation_contract": DERIVATION_CONTRACT,
        "target_date": target_date,
        "source_date": source_date,
        "market_layer": market_layer,
        "sector_layer": sector_layer,
        "leader_layer": leader_layer,
        "data_completeness": data_completeness,
        "nodes": nodes,
        "candidate_pool": candidate_pool,
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
        },
        "flowchart_payload": {
            "nodes": [{"id": node["node_id"], "label": node["node_name"], "judgement": node["judgement"]} for node in nodes],
            "final_label": final_label if position_pct else "无执行对象",
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
        label = _mermaid_escape(f"{node_id} {node.get('node_name')}\\n{node.get('judgement')}")
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
    target = stock_label(final.get("execution_object"))
    pct = final.get("position_pct", 0)
    final_label = _mermaid_escape(f"最终：{target}\\n仓位：{pct}%")
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
    "render_selection_workflow_mermaid",
    "stock_key",
    "stock_label",
    "stock_payload",
    "store_selection_workflow",
]
