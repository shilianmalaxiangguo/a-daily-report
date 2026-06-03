from __future__ import annotations

import re

import daily_report_analysis_utils as analysis_utils
from selection.anchor_reversal_contracts import build_anchor_reversal_decision
from selection.advantage_dedup_runtime import build_grouped_advantage_score
from selection.candidate_execution_contracts import (
    build_participation_window_from_candidate,
    build_participation_window_policy,
)

__all__ = [
    "build_extreme_conviction_groups",
    "build_extreme_conviction_list",
    "build_leader_memory_bank",
    "build_sector_trend_snapshot",
]

_MISSING = object()
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
    "待补充板块",
    "待补充",
    "-",
}


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _is_valid_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_SECTOR_LABELS)


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


def sector_name_matches(sector_a, sector_b):
    return analysis_utils.sector_name_matches(sector_a, sector_b)


def stock_matches_sector(stock, sector_name):
    if not stock or not sector_name:
        return False
    sector = str(stock.get("sector", "") or "")
    if sector and (sector_name in sector or sector in sector_name):
        return True
    for concept in stock.get("concepts", [])[:5]:
        concept = str(concept)
        if concept and (sector_name in concept or concept in sector_name):
            return True
    return False


def _stable_code_rank(value):
    text = normalize_stock_code(value)
    digits = "".join(ch for ch in str(text or "") if ch.isdigit())
    if not digits:
        return 999999
    try:
        return int(digits)
    except ValueError:
        return 999999


def _safe_float_or_none(value):
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace("%", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def _first_number(stock, *keys):
    for key in keys:
        value = _safe_float_or_none((stock or {}).get(key))
        if value is not None:
            return value
    return None


def _iter_text_terms(value):
    if value in (None, ""):
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_text_terms(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_text_terms(item)
        return
    for part in re.split(r"[,，、/|;；+＋\s]+", str(value or "")):
        text = part.strip()
        if text:
            yield text


def _text_term_matches(a, b):
    a = str(a or "").strip().lower()
    b = str(b or "").strip().lower()
    return bool(a and b and (a in b or b in a))


def _theme_keyword_in_text(keyword, text):
    keyword = str(keyword or "").strip()
    text = str(text or "")
    if not keyword or not text:
        return False
    if keyword.isascii() and keyword.isalpha() and len(keyword) <= 2:
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])", text, flags=re.IGNORECASE))
    return keyword.lower() in text.lower()


def _theme_keywords_in_text(text):
    return {keyword for keyword in _THEME_KEYWORDS if _theme_keyword_in_text(keyword, text)}


def _text_contains_any(text, markers):
    return any(marker in str(text or "") for marker in markers)


_BLOCKING_RISK_FLAGS = {
    "st",
    "st_warning",
    "stock_st",
    "delist_risk",
    "delisting_risk",
    "holder_reduce",
    "holder_reduce_announcement",
    "reduction_plan",
    "risk_warning",
    "other_risk_warning",
    "abnormal_volatility",
    "regulatory_investigation",
    "judicial_forced_sale",
    "forced_sale",
    "judicial_auction",
    "passive_reduction",
}

_HYPE_DOWNGRADE_FLAGS = {
    "hype_expectation_downgrade",
    "theme_clarification",
    "business_clarification",
}

_HYPE_DOWNGRADE_MARKERS = (
    "尚未与",
    "尚未达成合作",
    "未达成合作",
    "没有合作",
    "暂无合作",
    "无合作",
    "未开展业务合作",
    "无相关规划",
    "暂无相关规划",
    "无重组计划",
    "无相关业务",
    "业务占比较小",
    "占比较小",
    "占比很小",
    "尚未形成营业收入",
    "未形成营业收入",
    "尚未产生营业收入",
    "未产生营业收入",
    "尚未形成利润",
    "未形成利润",
    "尚未产生利润",
    "未产生利润",
    "尚未量产",
    "未量产",
    "尚未完成交付",
    "未完成交付",
    "距离批量化生产还需要较长周期",
    "传闻不实",
    "不属实",
)

_THEME_KEYWORDS = (
    "AIDC",
    "AI",
    "美国客户",
    "海外客户",
    "数据中心",
    "算力",
    "液冷",
    "储能",
    "固态电池",
    "钠离子",
    "航天卫星",
    "卫星电池",
    "商业航天",
    "鸿蒙",
    "开源鸿蒙",
    "华为",
    "阿里",
    "字节",
    "比亚迪",
    "特斯拉",
)


_DRIVER_THEME_GROUPS = (
    ("AIDC", ("AIDC", "数据中心", "算力", "液冷", "美国客户", "海外客户")),
    ("数据中心", ("AIDC", "数据中心", "算力", "液冷", "美国客户", "海外客户")),
    ("算力", ("AIDC", "数据中心", "算力", "液冷", "AI")),
    ("储能", ("储能", "固态电池", "钠离子", "卫星电池")),
    ("固态电池", ("储能", "固态电池", "钠离子")),
    ("航天卫星", ("航天卫星", "卫星电池", "商业航天")),
    ("商业航天", ("航天卫星", "卫星电池", "商业航天")),
    ("鸿蒙", ("鸿蒙", "开源鸿蒙", "华为")),
    ("华为", ("鸿蒙", "开源鸿蒙", "华为")),
    ("比亚迪", ("比亚迪", "特斯拉")),
    ("特斯拉", ("比亚迪", "特斯拉")),
)


def _append_unique_driver_tag(tags, value):
    seen = {str(tag or "").strip().lower() for tag in tags}
    for term in _iter_text_terms(value):
        text = str(term or "").strip()
        key = text.lower()
        if text and key not in seen:
            tags.append(text)
            seen.add(key)


def _related_driver_keywords(seed_terms):
    related = set()
    seed_text = " / ".join(str(term or "") for term in seed_terms)
    for anchor, group_terms in _DRIVER_THEME_GROUPS:
        if _theme_keyword_in_text(anchor, seed_text) or any(_theme_keyword_in_text(term, seed_text) for term in group_terms):
            related.update(group_terms)
    return related


def _infer_current_driver_tags(stock, *, mainline_name=""):
    stock = stock or {}
    tags = []
    for key in ("current_driver_tags", "active_driver_tags", "炒作主线", "上涨原因标签"):
        _append_unique_driver_tag(tags, stock.get(key))
    driver_text = " / ".join(
        str(stock.get(key) or "")
        for key in (
            "reason",
            "conviction_reason",
            "xuangubao_stock_reason",
            "popularity_tag",
            "rank_reason",
            "hot_reason",
        )
    )
    for keyword in _theme_keywords_in_text(f"{mainline_name} / {driver_text}"):
        _append_unique_driver_tag(tags, keyword)

    related_keywords = _related_driver_keywords(tags)
    source_values = []
    for key in ("sector", "concepts", "xuangubao_related_plate_names", "related_plate_names", "plates", "tags"):
        source_values.extend(_iter_text_terms(stock.get(key)))
    for term in source_values:
        term_text = str(term or "").strip()
        if not term_text:
            continue
        term_keywords = _theme_keywords_in_text(term_text)
        if any(keyword in related_keywords for keyword in term_keywords):
            for keyword in term_keywords:
                if keyword in related_keywords:
                    _append_unique_driver_tag(tags, keyword)
            continue
        if any(_text_term_matches(term_text, tag) for tag in tags):
            _append_unique_driver_tag(tags, term_text)
    return tags


def _iter_risk_values(value):
    if value in (None, ""):
        return
    if isinstance(value, dict):
        for key in (
            "risk_flags",
            "risk_summary",
            "source_endpoints",
            "risk_events",
            "events",
            "announcement_risks",
            "investor_qa_risks",
            "investor_interaction_risks",
            "qa_risks",
            "title",
            "risk_type",
            "st_reason",
            "st_explain",
            "trade_type",
            "question",
            "answer",
            "reason",
            "summary",
        ):
            if key in value:
                yield from _iter_risk_values(value.get(key))
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_risk_values(item)
        return
    text = str(value).strip()
    if text:
        yield text


def _negative_news_text(stock):
    stock = stock or {}
    parts = []
    for key in (
        "negative_news_summary",
        "news_risk_summary",
        "risk_summary",
        "announcement_risk",
        "stock_risk",
        "risk_events",
        "announcement_risks",
        "investor_qa_risks",
        "investor_interaction_risks",
        "qa_risks",
        "investor_qa_summary",
        "investor_interaction_summary",
        "qa_risk_summary",
        "irm_summary",
        "tushare_risk_summary",
        "st_reason",
        "st_explain",
        "stk_shock_reason",
        "监管风险",
        "负面消息",
    ):
        value = stock.get(key)
        if value not in (None, ""):
            parts.extend(_iter_risk_values(value))
    for flag_key in ("news_risk_flags", "negative_news_flags", "risk_flags"):
        flags = stock.get(flag_key) or []
        parts.extend(_iter_risk_values(flags))
    return " / ".join(parts)


def _has_blocking_risk_flag(stock):
    stock = stock or {}
    flags = []
    for flag_key in ("news_risk_flags", "negative_news_flags", "risk_flags"):
        flags.extend(_iter_risk_values(stock.get(flag_key) or []))
    flags.extend(_iter_risk_values((stock.get("stock_risk") or {}).get("risk_flags") if isinstance(stock.get("stock_risk"), dict) else []))
    normalized = {str(flag or "").strip().lower() for flag in flags if str(flag or "").strip()}
    return bool(normalized & _BLOCKING_RISK_FLAGS)


def _has_hype_expectation_downgrade(stock):
    stock = stock or {}
    flags = []
    for flag_key in ("news_risk_flags", "negative_news_flags", "risk_flags"):
        flags.extend(_iter_risk_values(stock.get(flag_key) or []))
    flags.extend(_iter_risk_values((stock.get("stock_risk") or {}).get("risk_flags") if isinstance(stock.get("stock_risk"), dict) else []))
    normalized = {str(flag or "").strip().lower() for flag in flags if str(flag or "").strip()}
    if normalized & _HYPE_DOWNGRADE_FLAGS:
        return True
    return _text_contains_any(_negative_news_text(stock), _HYPE_DOWNGRADE_MARKERS)


def _hype_downgrade_driver_match(stock, *, mainline_name=""):
    if not _has_hype_expectation_downgrade(stock):
        return "none"
    risk_text = _negative_news_text(stock)
    driver_terms = []
    for key in (
        "current_driver_tags",
        "active_driver_tags",
        "炒作主线",
        "上涨原因标签",
        "xuangubao_stock_reason",
    ):
        driver_terms.extend(_iter_text_terms((stock or {}).get(key)))
    driver_terms.extend(_iter_text_terms(mainline_name))
    broad_driver_text = " / ".join(
        str((stock or {}).get(key) or "")
        for key in ("reason", "conviction_reason", "xuangubao_stock_reason")
    )
    risk_theme_keywords = _theme_keywords_in_text(risk_text)
    driver_theme_keywords = _theme_keywords_in_text(broad_driver_text)
    driver_theme_keywords.update(_theme_keywords_in_text(" / ".join(driver_terms)))
    if risk_theme_keywords and driver_theme_keywords and (risk_theme_keywords & driver_theme_keywords):
        return "current_driver_hit"
    for term in driver_terms:
        if any(_text_term_matches(term, risk_term) for risk_term in _iter_text_terms(risk_text)):
            return "current_driver_hit"
        if str(term or "").strip() and str(term).lower() in str(risk_text or "").lower():
            return "current_driver_hit"
    for risk_term in _iter_text_terms(risk_text):
        if len(str(risk_term or "")) >= 2 and str(risk_term).lower() in broad_driver_text.lower():
            return "current_driver_hit"
    if driver_terms:
        return "driver_miss"
    return "unknown"


def _has_blocking_negative_news(stock):
    if _has_blocking_risk_flag(stock):
        return True
    name = str((stock or {}).get("name") or (stock or {}).get("名称") or "").upper()
    if name.startswith("*ST") or name.startswith("ST") or "退" in name:
        return True
    text = _negative_news_text(stock)
    return _text_contains_any(
        text,
        (
            "监管立案",
            "立案调查",
            "证监会立案",
            "涉嫌信息披露",
            "信息披露违法",
            "实控人被抓",
            "实际控制人被抓",
            "刑事",
            "退市风险",
            "实施其他风险警示",
            "其他风险警示",
            "风险警示",
            "重大违法",
            "ST风险",
            "减持",
            "拟减持",
            "被动减持",
            "集中竞价减持",
            "大宗交易减持",
            "司法强制执行",
            "强制执行",
            "强制卖出",
            "强制执行卖出",
            "法院通过集中竞价",
            "司法拍卖",
            "被法院",
            "股份将被法院",
            "异常波动",
            "风险提示公告",
        ),
    )


def _candidate_combined_text(stock, *extra_values):
    stock = stock or {}
    parts = [str(value or "") for value in extra_values if str(value or "").strip()]
    for key in (
        "reason",
        "conviction_reason",
        "core_level",
        "pattern",
        "volume_summary",
        "abnormal_summary",
        "abnormal_type",
        "abnormal_setup_signal_label",
        "xuangubao_stock_reason",
        "stock_setup",
        "trend_aesthetic",
        "trend_structure",
        "trend_structure_quality",
        "shape_quality",
        "kline_shape",
        "price_action_summary",
        "capacity_profile",
        "turnover_capacity",
        "volume_capacity",
        "ma_binding_strategy",
        "holding_strategy",
        "position_strategy",
        "acceptance_profile",
    ):
        value = stock.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    return " / ".join(parts)


def _has_upper_shadow_repair(stock):
    stock = stock or {}
    combined = _candidate_combined_text(stock)
    setup_id = str(stock.get("abnormal_setup_signal_id") or stock.get("setup_signal_id") or "").strip()
    follow_state = str(stock.get("abnormal_follow_state") or stock.get("follow_state") or "").strip()
    return bool(
        stock.get("upper_shadow_repaired")
        or setup_id == "upper_shadow_reclaim"
        or "长上影后收复" in combined
        or "吃掉上影" in combined
        or "放量突破上影" in combined
        or (setup_id == "upper_shadow_digest" and follow_state == "跌不下去")
    )


def _has_unrepaired_upper_shadow_risk(stock):
    stock = stock or {}
    if _has_upper_shadow_repair(stock):
        return False
    combined = _candidate_combined_text(stock)
    return bool(
        stock.get("upper_shadow_unrepaired")
        or stock.get("unrepaired_upper_shadow")
        or _text_contains_any(combined, ("连续长上影", "长上影未修复", "上影线未修复", "阶段长上影未修复"))
    )


def _has_broken_sell_line_risk(stock):
    stock = stock or {}
    if stock.get("sell_line_repaired") or stock.get("ma_sell_line_repaired"):
        return False
    combined = _candidate_combined_text(stock)
    return bool(
        stock.get("broken_sell_ma_line")
        or stock.get("sell_ma_line_broken")
        or _text_contains_any(
            combined,
            (
                "跌破MA5收不回",
                "跌破MA10收不回",
                "跌破MA20收不回",
                "跌破卖点线收不回",
                "破卖点线未修复",
            ),
        )
    )


def _append_unique(values, value):
    if value and value not in values:
        values.append(value)


def _bar_value(row, *keys, default=0.0):
    for key in keys:
        value = _safe_float_or_none((row or {}).get(key))
        if value is not None:
            return value
    return float(default)


def _bar_date(row):
    return str((row or {}).get("date") or (row or {}).get("trade_date") or "").strip()


def _candidate_recent_bars(stock):
    stock = stock or {}
    for key in (
        "recent_bars",
        "daily_bars",
        "price_bars",
        "stock_klines",
        "kline_rows",
        "klines",
    ):
        value = stock.get(key)
        if isinstance(value, list):
            rows = [row for row in value if isinstance(row, dict)]
            if rows:
                return sorted(rows, key=lambda row: _bar_date(row) or "")
    return []


def _ma(values, window):
    values = list(values or [])
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _pct_change(current, base):
    if current is None or base in (None, 0):
        return None
    return (current / base - 1) * 100


def _consecutive_close_below_ma(closes, window):
    count = 0
    for idx in range(len(closes) - 1, -1, -1):
        current_window = closes[: idx + 1]
        ma_value = _ma(current_window, window)
        if ma_value is not None and closes[idx] < ma_value:
            count += 1
            continue
        break
    return count


def _avg_intraday_range_pct(highs, lows, closes):
    values = []
    for high, low, close in zip(highs or [], lows or [], closes or []):
        if close:
            values.append((high - low) / close * 100)
    if not values:
        return None
    return sum(values) / len(values)


def _pullback_repair_count(closes, lookback=20):
    closes = list(closes or [])
    if len(closes) < 3:
        return 0
    start = max(1, len(closes) - int(lookback or 20))
    count = 0
    for idx in range(start, len(closes) - 1):
        if closes[idx] < closes[idx - 1] and closes[idx + 1] >= closes[idx]:
            count += 1
    return count


def _build_trend_aesthetic_review_from_bars(stock):
    rows = _candidate_recent_bars(stock)[-120:]
    if len(rows) < 8:
        return None

    closes = [_bar_value(row, "close", "收盘", "收盘价") for row in rows]
    highs = [_bar_value(row, "high", "最高", "最高价") for row in rows]
    lows = [_bar_value(row, "low", "最低", "最低价") for row in rows]
    pct_changes = [_bar_value(row, "pct_chg", "change_pct", "涨跌幅") for row in rows]
    close = closes[-1]
    ma3 = _ma(closes, 3)
    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    ma20 = _ma(closes, 20)
    previous_ma20 = _ma(closes[:-10], 20) if len(closes) >= 30 else None
    ma20_slope = _pct_change(ma20, previous_ma20)
    recent20_high = max(highs[-20:])
    recent20_low = min(lows[-20:])
    previous20_high = max(highs[-40:-20]) if len(highs) >= 40 else None
    previous20_low = min(lows[-40:-20]) if len(lows) >= 40 else None
    position20 = (
        (close - recent20_low) / (recent20_high - recent20_low) * 100
        if recent20_high and recent20_high != recent20_low
        else 50.0
    )
    peak = highs[0]
    max_drawdown = 0.0
    for high, low in zip(highs, lows):
        peak = max(peak, high)
        if peak:
            max_drawdown = min(max_drawdown, (low / peak - 1) * 100)
    big_down60 = sum(1 for value in pct_changes[-60:] if value <= -7)
    big_up60 = sum(1 for value in pct_changes[-60:] if value >= 7)
    high_shift = "上移" if previous20_high is not None and recent20_high >= previous20_high else "下移" if previous20_high is not None else ""
    low_shift = "上移" if previous20_low is not None and recent20_low >= previous20_low else "下移" if previous20_low is not None else ""
    below_ma3_days = _consecutive_close_below_ma(closes, 3)
    recent_range = _avg_intraday_range_pct(highs[-20:], lows[-20:], closes[-20:])
    previous_range = _avg_intraday_range_pct(highs[-40:-20], lows[-40:-20], closes[-40:-20]) if len(closes) >= 40 else None
    range_contraction_ratio = recent_range / previous_range if previous_range else None
    pullback_repairs = _pullback_repair_count(closes, lookback=20)

    reasons = []
    metrics = {
        "bars": len(rows),
        "close": round(close, 3),
        "ma5_gap_pct": round(_pct_change(close, ma5) or 0.0, 2),
        "ma20_gap_pct": round(_pct_change(close, ma20) or 0.0, 2) if ma20 is not None else None,
        "ma20_slope_pct": round(ma20_slope, 2) if ma20_slope is not None else None,
        "max_drawdown_pct": round(max_drawdown, 2),
        "position20_pct": round(position20, 2),
        "high_shift": high_shift or "-",
        "low_shift": low_shift or "-",
        "big_down60_count": big_down60,
        "big_up60_count": big_up60,
        "below_ma3_days": below_ma3_days,
        "range_contraction_ratio": round(range_contraction_ratio, 2) if range_contraction_ratio is not None else None,
        "pullback_repair_count": pullback_repairs,
    }

    weak_alignment = bool(ma5 is not None and ma10 is not None and ma20 is not None and ma5 < ma10 < ma20 and close < ma20)
    broken_structure = bool(
        (big_down60 >= 2 and close < (ma20 or close) and (high_shift == "下移" or low_shift == "下移"))
        or (max_drawdown <= -28 and close < (ma20 or close) and position20 <= 35)
        or (weak_alignment and position20 <= 45)
        or (pct_changes[-1] <= -9.5 and close < (ma5 or close))
    )
    if broken_structure:
        if big_down60 >= 2 or pct_changes[-1] <= -9.5:
            reasons.append("放量或急跌破坏")
        if high_shift == "下移" or low_shift == "下移":
            reasons.append("高低点下移")
        if close < (ma20 or close):
            reasons.append("MA20下方")
        if position20 <= 35:
            reasons.append("20日区间低位")
        return {
            "status": "不通过",
            "source": "recent_bars",
            "reasons": reasons or ["日K结构破坏"],
            "metrics": metrics,
            "action": "降级观察，重新站回关键线并有承接修复后再评估",
        }

    current_acceptance_weak = bool(
        ma5 is not None
        and ma20 is not None
        and close < ma5
        and close < ma20
        and position20 < 45
        and pct_changes[-1] <= -5
    )
    if current_acceptance_weak:
        return {
            "status": "不通过",
            "source": "recent_bars",
            "reasons": ["短线承接转弱", "MA20下方", "20日区间中低位"],
            "metrics": metrics,
            "action": "历史趋势样本待修复，重新站回短中线承接后再评估",
        }
    big_drop_below_short_mid = bool(
        ma5 is not None
        and ma20 is not None
        and close < ma5
        and close < ma20
        and pct_changes[-1] <= -7
    )
    if big_drop_below_short_mid:
        return {
            "status": "不通过",
            "source": "recent_bars",
            "reasons": ["短线承接转弱", "大跌跌破短中线承接", "MA20下方"],
            "metrics": metrics,
            "action": "历史趋势样本待修复，重新站回短中线承接后再评估",
        }
    weak_rebound_below_key_mas = bool(
        ma5 is not None
        and ma20 is not None
        and close < ma5
        and close < ma20
        and position20 <= 35
        and pct_changes[-1] < 3
    )
    if weak_rebound_below_key_mas:
        return {
            "status": "不通过",
            "source": "recent_bars",
            "reasons": ["弱反抽未收回短中线", "MA20下方", "20日区间低位"],
            "metrics": metrics,
            "action": "弱反抽只观察，重新站回MA5/MA20并有承接修复后再评估",
        }

    good_reasons = []
    if high_shift == "上移" and low_shift == "上移":
        good_reasons.append("高低点上移")
    if ma20 is not None and close >= ma20 and (ma20_slope is None or ma20_slope >= -1):
        good_reasons.append("MA20上方或趋势未破")
    if position20 >= 45:
        good_reasons.append("20日区间位置健康")
    if pullback_repairs >= 2 and (range_contraction_ratio is None or range_contraction_ratio <= 1.5) and position20 >= 45:
        good_reasons.append("平台呼吸")
    if high_shift == "上移" and low_shift == "上移" and pullback_repairs >= 2:
        good_reasons.append("蛇形走位")
    if big_up60 >= 2:
        good_reasons.append("攻击有辨识度")
    if not good_reasons:
        good_reasons = ["未见形态破坏"]
    return {
        "status": "通过",
        "source": "recent_bars",
        "reasons": good_reasons,
        "metrics": metrics,
        "action": "保留极度看好比较资格",
    }


def _iter_nested_text_values(value):
    if value in (None, ""):
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_nested_text_values(nested)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_nested_text_values(item)
        return
    text = str(value).strip()
    if text:
        yield text


def _trend_aesthetic_combined_text(stock, pattern=""):
    stock = stock or {}
    parts = [_candidate_combined_text(stock, pattern)]
    for key in (
        "trend_aesthetic_review",
        "trend_fate",
        "trend_review",
        "shape_review",
        "a_kill_review",
        "elimination_event",
        "monitoring_rows",
    ):
        value = stock.get(key)
        if value not in (None, ""):
            parts.extend(_iter_nested_text_values(value))
    return " / ".join(part for part in parts if str(part or "").strip())


def _has_trend_aesthetic_repair(stock, text):
    stock = stock or {}
    status_text = str(stock.get("trend_aesthetic_status") or stock.get("shape_status") or "").strip().lower()
    if status_text in {"pass", "passed", "ok", "good", "healthy", "通过", "合格"}:
        return True
    return bool(
        stock.get("trend_aesthetic_repaired")
        or stock.get("a_kill_repaired")
        or stock.get("shape_repaired")
        or _text_contains_any(
            text,
            (
                "重新站回",
                "站回MA20",
                "站回MA10",
                "站回MA7",
                "站回MA5",
                "承接修复",
                "右侧确认",
                "再攻击放量",
                "回踩不破",
                "放量吃掉",
            ),
        )
    )


def _trend_aesthetic_bad_reasons(stock, text):
    stock = stock or {}
    reasons = []
    status_text = str(stock.get("trend_aesthetic_status") or stock.get("shape_status") or "").strip().lower()
    if status_text in {"fail", "failed", "bad", "ugly", "reject", "rejected", "不通过", "不合格", "丑"}:
        _append_unique(reasons, "形态质量不合格")
    if stock.get("a_kill_risk") or stock.get("a_kill") or stock.get("trend_aesthetic_a_kill"):
        _append_unique(reasons, "A杀风险")
    if _text_contains_any(text, ("a_kill", "a-kill", "A杀", "A型杀跌")):
        _append_unique(reasons, "A杀风险")
    if _text_contains_any(text, ("断崖", "瀑布", "崩盘", "杀跌", "放量下杀", "放量大跌")):
        _append_unique(reasons, "下跌速度过快")
    if _text_contains_any(text, ("反抽不过", "弱反抽", "冲不过MA3", "冲不过MA7", "冲不过MA10")):
        _append_unique(reasons, "反抽不过关键线")
    if _text_contains_any(text, ("低点下移", "高点下移", "高低点下移", "重心下移")):
        _append_unique(reasons, "重心下移")
    if _text_contains_any(
        text,
        (
            "跌破MA3收不回",
            "跌破MA7收不回",
            "跌破MA10收不回",
            "跌破MA20收不回",
            "连续3日MA3下方",
            "MA20下拐",
        ),
    ):
        _append_unique(reasons, "关键线收不回")
    return reasons


def _trend_aesthetic_good_reasons(stock, text):
    stock = stock or {}
    reasons = []
    status_text = str(stock.get("trend_aesthetic_status") or stock.get("shape_status") or "").strip().lower()
    if status_text in {"pass", "passed", "ok", "good", "healthy", "通过", "合格"}:
        _append_unique(reasons, "形态质量合格")
    if _text_contains_any(text, ("上升趋势", "强趋势", "趋势比价链", "趋势核心")):
        _append_unique(reasons, "上升趋势")
    if _text_contains_any(text, ("平台震荡", "横盘消化", "箱体震荡", "平台整理")):
        _append_unique(reasons, "平台震荡")
    if _text_contains_any(text, ("呼吸", "蛇形走位", "沿MA5", "沿MA10", "低点上移", "高点上移")):
        _append_unique(reasons, "走势有呼吸")
    if _text_contains_any(text, ("缩量回踩", "回踩不破", "MA5不破", "MA10不破", "线位有响应")):
        _append_unique(reasons, "回撤有承接")
    if _text_contains_any(text, ("放量突破", "再攻击放量", "强实体", "光头大阳", "涨停", "T字", "连板")):
        _append_unique(reasons, "攻击有辨识度")
    return reasons


def _build_trend_aesthetic_review(stock, *, pattern=""):
    bar_review = _build_trend_aesthetic_review_from_bars(stock)
    if bar_review is not None:
        return bar_review

    text = _trend_aesthetic_combined_text(stock, pattern)
    bad_reasons = _trend_aesthetic_bad_reasons(stock, text)
    if bad_reasons and not _has_trend_aesthetic_repair(stock, text):
        return {
            "status": "不通过",
            "reasons": bad_reasons,
            "action": "降级观察，重新站回关键线并有承接修复后再评估",
        }

    good_reasons = _trend_aesthetic_good_reasons(stock, text)
    if not good_reasons:
        good_reasons = ["未见形态破坏"]
    return {
        "status": "通过",
        "reasons": good_reasons,
        "action": "保留极度看好比较资格",
    }


def _build_selection_shape_review(trend_aesthetic_review):
    review = trend_aesthetic_review or {}
    return {
        "name": "选股形态审美",
        "status": review.get("status", "通过"),
        "source": review.get("source", "pattern_text"),
        "focus": ["120日日K", "呼吸感", "蛇形走位", "重心上移", "平台消化", "缩量回踩"],
        "avoid": ["A杀", "破位弱反抽", "放量下杀", "高低点下移", "MA20下方收不回"],
        "reasons": list(review.get("reasons") or []),
        "metrics": dict(review.get("metrics") or {}),
        "action": review.get("action", ""),
    }


def _has_positive_trend_aesthetic_evidence(trend_aesthetic_review):
    review = trend_aesthetic_review or {}
    if review.get("status") != "通过":
        return False
    reasons = [str(reason or "").strip() for reason in list(review.get("reasons") or [])]
    return any(reason and reason != "未见形态破坏" for reason in reasons)


def _trend_aesthetic_reason_labels(trend_aesthetic_review, *, limit=2):
    preferred = ("平台呼吸", "蛇形走位", "高低点上移", "攻击有辨识度", "20日区间位置健康")
    reasons = [str(reason or "").strip() for reason in list((trend_aesthetic_review or {}).get("reasons") or [])]
    labels = []
    for preferred_label in preferred:
        if preferred_label in reasons and preferred_label not in labels:
            labels.append(preferred_label)
        if len(labels) >= limit:
            return labels
    for reason in reasons:
        if not reason or reason == "未见形态破坏" or reason in labels:
            continue
        labels.append(reason)
        if len(labels) >= limit:
            break
    return labels


def _build_final_sniper_risk_review(stock, *, mainline_name=""):
    reasons = []
    downgrade_reasons = []
    notes = []
    if _has_blocking_negative_news(stock):
        reasons.append("公告风险未确认干净")
    driver_match = _hype_downgrade_driver_match(stock, mainline_name=mainline_name)
    if driver_match == "current_driver_hit":
        downgrade_reasons.append("炒作预期降维")
        downgrade_reasons.append("澄清命中当前上涨主线")
    elif driver_match == "driver_miss":
        notes.append("澄清未命中当前上涨主线")
    elif driver_match == "unknown":
        downgrade_reasons.append("炒作预期降维")
    if _has_unrepaired_upper_shadow_risk(stock):
        reasons.append("连续长上影未修复")
    if _has_broken_sell_line_risk(stock):
        reasons.append("跌破对应卖点线收不回")
    trend_review = _build_trend_aesthetic_review(stock, pattern=str((stock or {}).get("pattern", "") or ""))
    if trend_review["status"] != "通过":
        reasons.append("趋势形态不合格")
    elif not _has_positive_trend_aesthetic_evidence(trend_review):
        reasons.append("缺少正向形态证据")
    if reasons:
        return {
            "status": "取消主买/补位资格",
            "risk_level": "A",
            "score_penalty": 100,
            "reasons": reasons + downgrade_reasons,
            "notes": notes,
            "hype_driver_match": driver_match,
            "action": "降级观察，修复后重新评估",
        }
    if downgrade_reasons:
        penalty = 30 if driver_match == "current_driver_hit" else 18
        return {
            "status": "降级观察",
            "risk_level": "B",
            "score_penalty": penalty,
            "reasons": downgrade_reasons,
            "notes": notes,
            "hype_driver_match": driver_match,
            "action": "保留观察资格，强行情可跟踪承接，但不作为主买加速和盘中加仓理由",
        }
    return {
        "status": "通过",
        "risk_level": "C",
        "score_penalty": 0,
        "reasons": [],
        "notes": notes,
        "hype_driver_match": driver_match,
        "action": "可进入主买/补位比较",
    }


def _can_keep_hype_downgrade_as_observation(stock, *, is_anchor=False, is_mainline=False, lianban=0, pattern="", change_pct=None, mainline_name=""):
    driver_match = _hype_downgrade_driver_match(stock, mainline_name=mainline_name)
    if driver_match in ("none", "driver_miss"):
        return True
    hot_core = bool(is_anchor and is_mainline)
    strong_price = bool(
        int(lianban or 0) >= 2
        or _text_contains_any(str(pattern or ""), ("T字", "一字", "强实体", "光头", "涨停"))
        or (change_pct is not None and change_pct >= 9.5)
    )
    trend_review = _build_trend_aesthetic_review(stock, pattern=pattern)
    return bool(hot_core and strong_price and trend_review.get("status") == "通过")


def _has_current_price_evidence(stock, pattern=""):
    stock = stock or {}
    price_keys = (
        "change_pct",
        "change",
        "pct_chg",
        "涨跌幅",
        "open",
        "high",
        "low",
        "close",
        "开盘价",
        "最高价",
        "最低价",
        "收盘价",
    )
    return any(stock.get(key) not in (None, "") for key in price_keys) or bool(str(pattern or "").strip())


def _candidate_is_limit_down(stock, change_pct=None, pattern=""):
    stock = stock or {}
    if stock.get("is_limit_down"):
        return True
    status_text = " / ".join(
        str(stock.get(key) or "")
        for key in ("limit_status", "zt_status", "涨停状态", "status", "trade_status", "tag")
    )
    if "跌停" in status_text or "跌停" in str(pattern or ""):
        return True
    return change_pct is not None and change_pct <= -9.5


def _has_extreme_price_entry_signal(stock, *, change_pct=None, pattern="", lianban=0, is_anchor=False, is_mainline=False):
    stock = stock or {}
    combined = " / ".join(
        str(stock.get(key) or "")
        for key in (
            "reason",
            "conviction_reason",
            "core_level",
            "volume_summary",
            "abnormal_summary",
            "xuangubao_stock_reason",
        )
    )
    pattern_text = str(pattern or "")
    strong_pattern = _text_contains_any(pattern_text, ("涨停", "T字", "T板", "一字", "光头", "大阳", "强实体"))
    explicit_limit_up = _text_contains_any(combined, ("涨停", "封板", "连板", "回封", "强实体"))
    limit_up_days = int(_safe_float(stock.get("xuangubao_limit_up_days", 0), 0) or 0)

    if change_pct is not None:
        if change_pct >= 5:
            return True
        if is_anchor and is_mainline and change_pct >= 3:
            return True
        return False
    return bool(strong_pattern or explicit_limit_up or int(lianban or 0) >= 1 or limit_up_days >= 1)


def _is_one_word_limit_candidate(stock, *, pattern="", change_pct=None):
    stock = stock or {}
    pattern_text = str(pattern or "")
    status_text = " / ".join(
        str(stock.get(key) or "")
        for key in ("limit_status", "zt_status", "涨停状态", "status", "tag")
    )
    if _text_contains_any(f"{pattern_text} / {status_text}", ("一字板", "一字涨停", "一字")):
        return True

    open_price = _first_number(stock, "open", "开盘价")
    high_price = _first_number(stock, "high", "最高价")
    low_price = _first_number(stock, "low", "最低价")
    close_price = _first_number(stock, "close", "收盘价")
    if None in (open_price, high_price, low_price, close_price):
        return False
    if change_pct is None or change_pct < 9.5:
        return False
    prices = [open_price, high_price, low_price, close_price]
    return max(prices) - min(prices) <= max(abs(close_price) * 0.001, 0.01)


def _has_one_word_limit_independent_confirmation(stock):
    stock = stock or {}
    if stock.get("one_word_limit_confirmed"):
        return True
    setup_id = str(stock.get("abnormal_setup_signal_id") or stock.get("setup_signal_id") or "").strip()
    follow_state = str(stock.get("abnormal_follow_state") or stock.get("follow_state") or "").strip()
    return bool(
        setup_id
        and setup_id not in ("fresh_abnormal_probe", "abnormal_failed")
        and follow_state in ("跌不下去", "缩量消化")
    )


def _is_unconfirmed_one_word_limit_candidate(stock, *, change_pct=None, pattern=""):
    return _is_one_word_limit_candidate(
        stock,
        pattern=pattern,
        change_pct=change_pct,
    ) and not _has_one_word_limit_independent_confirmation(stock)


def _passes_extreme_conviction_price_gate(stock, *, change_pct=None, pattern="", lianban=0, is_anchor=False, is_mainline=False, mainline_name=""):
    if not _can_keep_hype_downgrade_as_observation(stock, is_anchor=is_anchor, is_mainline=is_mainline, lianban=lianban, pattern=pattern, change_pct=change_pct, mainline_name=mainline_name):
        return False
    if _has_blocking_negative_news(stock):
        return False
    if _has_unrepaired_upper_shadow_risk(stock):
        return False
    if _has_broken_sell_line_risk(stock):
        return False
    if _build_trend_aesthetic_review(stock, pattern=pattern)["status"] != "通过":
        return False
    if stock.get("allow_extreme_conviction"):
        return True
    if _candidate_is_limit_down(stock, change_pct=change_pct, pattern=pattern):
        return False
    if change_pct is not None and change_pct < -2:
        return False
    if _is_unconfirmed_one_word_limit_candidate(stock, change_pct=change_pct, pattern=pattern):
        return False
    if _text_contains_any(pattern, ("下跌趋势", "缩量调整", "高位大绿棒")):
        return False
    if _has_anchor_certainty_entry_path(stock, pattern=pattern, is_anchor=is_anchor, is_mainline=is_mainline):
        return True
    if not _has_current_price_evidence(stock, pattern=pattern):
        return True
    if _text_contains_any(pattern, ("震荡整理", "普通形态")) and not _has_extreme_price_entry_signal(
        stock,
        change_pct=change_pct,
        pattern=pattern,
        lianban=lianban,
        is_anchor=is_anchor,
        is_mainline=is_mainline,
    ):
        return False
    return _has_extreme_price_entry_signal(
        stock,
        change_pct=change_pct,
        pattern=pattern,
        lianban=lianban,
        is_anchor=is_anchor,
        is_mainline=is_mainline,
    )


def _has_anchor_certainty_entry_path(stock, *, pattern="", is_anchor=False, is_mainline=False):
    if not (is_anchor and is_mainline):
        return False
    combined = _candidate_combined_text(stock, pattern)
    has_ma_binding = _text_contains_any(
        combined,
        ("MA5入/MA7清/MA5T", "MA5B", "MA7清", "MA5T", "沿MA5", "MA5不破", "回踩不破"),
    )
    has_acceptance = _text_contains_any(
        combined,
        ("承接", "大容量", "趋势资金", "趋势比价链", "热门股", "反复做", "低点上移"),
    )
    return bool(has_ma_binding or has_acceptance)


def _conviction_attack_state(stock, *, is_anchor=False, is_mainline=False):
    if is_anchor and is_mainline:
        return "100%"
    if stock.get("allow_full_attack") or stock.get("a_grade_candidate"):
        return "100%"
    return "50%"


def _conviction_participation_window(stock, *, is_anchor=False, is_mainline=False):
    return build_participation_window_from_candidate(
        stock,
        is_anchor=is_anchor,
        is_mainline=is_mainline,
    )


def _infer_leader_speed_profile(stock, *, is_anchor=False, is_mainline=False, lianban=0, pattern="", change_pct=None):
    stock = stock or {}
    combined = _candidate_combined_text(stock, pattern)
    capacity_text = " / ".join(
        str(stock.get(key) or "")
        for key in ("turnover_capacity", "capacity_profile", "volume_capacity", "成交容量", "成交额")
    )
    close_ma = str(stock.get("close_ma_alignment") or stock.get("ma_alignment") or "").upper()
    is_limit_style = int(lianban or 0) >= 1 or _text_contains_any(combined, ("涨停", "T字", "一字", "连板", "光头"))
    is_large_capacity = _text_contains_any(f"{combined} / {capacity_text}", ("大容量", "large", "容量龙", "趋势资金")) or (
        close_ma in ("MA5", "MA10") and _text_contains_any(combined, ("趋势比价链", "趋势核心"))
    )

    if is_limit_style or (change_pct is not None and change_pct >= 9.5):
        return {
            "leader_speed_tier_code": "extreme_acceleration",
            "leader_speed_tier": "极致加速龙头",
            "buy_ma_line": "MA3",
            "sell_ma_line": "MA5",
            "ma_role_reason": "极致加速票容错最小，MA3是买点线，MA5是卖点线",
        }
    if is_large_capacity:
        return {
            "leader_speed_tier_code": "large_capacity_trend",
            "leader_speed_tier": "大容量趋势龙头",
            "buy_ma_line": "MA10",
            "sell_ma_line": "MA20",
            "ma_role_reason": "大容量趋势票呼吸更深，MA10是买点线，MA20是生命线",
        }
    if is_anchor or is_mainline or _text_contains_any(combined, ("龙", "核心", "强趋势", "辨识度")) or (change_pct is not None and change_pct >= 5):
        return {
            "leader_speed_tier_code": "strong_trend",
            "leader_speed_tier": "高弹性强趋势龙",
            "buy_ma_line": "MA5",
            "sell_ma_line": "MA10",
            "ma_role_reason": "强趋势票以MA5承接为买点线，MA10收不回则降级",
        }
    return {
        "leader_speed_tier_code": "not_leader",
        "leader_speed_tier": "观察样本",
        "buy_ma_line": "MA10",
        "sell_ma_line": "MA20",
        "ma_role_reason": "未形成明确龙头身份，只能等结构确认",
    }


def _build_acceptance_repair_required(profile):
    buy_line = profile.get("buy_ma_line") or "买点线"
    return f"缩量回撤到{buy_line}附近，线位有响应，站回VWAP/关键强弱线，修复或再攻击时成交确认"


def _build_common_selection_check(stock, *, sector="", is_mainline=False):
    sector_text = str(sector or stock.get("sector") or "所属方向").strip() or "所属方向"
    mainline_text = "主线资金仍在同方向选择" if is_mainline else f"{sector_text}资金仍有继续选择理由"
    return f"昨日持筹者不急卖，明日新买盘有清晰买点可接，{mainline_text}"


def _assign_sniper_roles(conviction_list):
    has_anchor_contract = any(
        str((item or {}).get("anchor_reversal_decision") or (item or {}).get("sector_anchor") or "").strip()
        for item in conviction_list or []
    )
    if has_anchor_contract:
        primary_assigned = False
        backup_assigned = False
        for item in conviction_list or []:
            anchor_decision = str((item or {}).get("anchor_reversal_decision") or "").strip()
            role = "候选观察"
            if anchor_decision == "可作为主对象" and not primary_assigned:
                role = "明日主买对象"
                primary_assigned = True
            elif anchor_decision in {"可作为主对象", "可作为补位"} and not backup_assigned:
                role = "明日补位对象"
                backup_assigned = True
            item["sniper_role"] = role
            item["primary_buy_candidate"] = role == "明日主买对象"
            item["backup_buy_candidate"] = role == "明日补位对象"
        return conviction_list

    action_idx = 0
    for item in conviction_list or []:
        anchor_decision = str((item or {}).get("anchor_reversal_decision") or "").strip()
        if anchor_decision in {"降级观察", "不参与"}:
            role = "候选观察"
        elif action_idx == 0:
            role = "明日主买对象"
            action_idx += 1
        elif action_idx == 1:
            role = "明日补位对象"
            action_idx += 1
        else:
            role = "候选观察"
        item["sniper_role"] = role
        item["primary_buy_candidate"] = role == "明日主买对象"
        item["backup_buy_candidate"] = role == "明日补位对象"
    return conviction_list


def _strength_already_contains_lianban_bonus(stock, *, tomorrow_strength=0, lianban=0):
    if int(lianban or 0) < 2:
        return False
    base_strength = _safe_float_or_none((stock or {}).get("base_strength_score"))
    if base_strength is None:
        return False
    return _safe_float(tomorrow_strength, 0) - base_strength >= 8


def _append_suppressed_advantage_points(advantage_dedup, points):
    if not points:
        return advantage_dedup
    updated = dict(advantage_dedup or {})
    suppressed_points = list(updated.get("suppressed_points") or [])
    for point in points:
        point = dict(point or {})
        score = _safe_float(point.get("score", 0), 0)
        suppressed_points.append(
            {
                "group": str(point.get("group") or "misc"),
                "label": str(point.get("label") or point.get("group") or "misc"),
                "score": score,
                "raw_score": _safe_float(point.get("raw_score", score), score),
                "source": str(point.get("source") or ""),
            }
        )
    updated["suppressed_points"] = suppressed_points
    updated["repeated_advantage_count"] = len(suppressed_points)
    return updated


def _build_conviction_participation_fields(stock, *, sector="", is_anchor=False, is_mainline=False):
    sector_text = str(sector or stock.get("sector") or "主线").strip() or "主线"
    if not _is_valid_sector_label(sector_text):
        sector_text = "主线"
    window = _conviction_participation_window(stock, is_anchor=is_anchor, is_mainline=is_mainline)
    if window == "打板/错过":
        board_script = "只做首次强封且大单金额持续进入，封死买不到就不追"
        missed_action = f"封死买不到就沿{sector_text}趋势比价链找低位承接，找不到就跳过"
    elif "回封参与" in window:
        board_script = "首次封板只看大单金额持续进入，弱封不追"
        missed_action = f"过快封死就沿{sector_text}趋势比价链找低位承接，找不到就跳过"
    else:
        board_script = "不以涨停为唯一条件，先等价格确认和承接连续"
        missed_action = f"确认前快速拉高就跳过，只沿{sector_text}趋势比价链找低位承接，找不到就跳过"

    participation = {
        "participation_window": window,
        "attack_state": _conviction_attack_state(stock, is_anchor=is_anchor, is_mainline=is_mainline),
        "auction_script": "09:20后看价格位置、匹配金额、委托稳定和板块同步，任一不合格按0%不参与",
        "first_minutes_script": "09:30-09:35只看主动资金是否继续抬价，承接不连续按0%不参与",
        "board_script": board_script,
        "reseal_script": "开板释放抛压后快速回封，且封单质量改善、板块同步",
        "missed_action": missed_action,
        "invalid_condition": "竞价表态、开盘承接、板块同步任一失败，按0%不参与",
    }
    participation.update(build_participation_window_policy(window, missed_action, candidate=stock))
    return participation


def _build_core_identity_fields(
    *,
    is_anchor=False,
    is_mainline=False,
    lianban=0,
    reason="",
    pattern="",
    reason_parts=None,
    attack_state="50%",
):
    reason_text = str(reason or "")
    pattern_text = str(pattern or "")
    basis = [str(part).strip() for part in (reason_parts or []) if str(part).strip()]
    early_allowed = bool(is_anchor and is_mainline)
    if early_allowed:
        role = "trend_chain_anchor"
        chain_position = "high_anchor" if int(lianban or 0) >= 2 or pattern_text in ("T字板", "一字板") else "core_transmitter"
    elif is_mainline or "龙一" in reason_text or int(lianban or 0) >= 2 or pattern_text in ("T字板", "一字板") or int(lianban or 0) >= 1:
        role = "core_transmitter"
        chain_position = "middle_transmitter"
    else:
        role = "tracked_sample"
        chain_position = "unassigned"
    return {
        "role": role,
        "chain_position": chain_position,
        "early_participation_allowed": early_allowed,
        "position_state": attack_state,
        "basis": basis,
    }


def _candidate_layer_fields(stock, *, is_anchor=False, is_mainline=False, lianban=0, change_pct=None, pattern="", mainline_name=""):
    if _has_blocking_negative_news(stock):
        return {
            "candidate_layer": "risk_blocked",
            "execution_eligibility": "blocked_by_negative_news",
        }
    if _hype_downgrade_driver_match(stock, mainline_name=mainline_name) in ("current_driver_hit", "unknown"):
        return {
            "candidate_layer": "watch_sample",
            "execution_eligibility": "hype_downgrade_observation",
        }
    if is_anchor and is_mainline:
        return {
            "candidate_layer": "executable_candidate",
            "execution_eligibility": "auction_reseal",
        }
    if int(lianban or 0) >= 1 or _text_contains_any(pattern, ("涨停", "T字", "一字", "光头", "强实体")):
        return {
            "candidate_layer": "executable_candidate",
            "execution_eligibility": "auction_reseal",
        }
    return {
        "candidate_layer": "watch_sample",
        "execution_eligibility": "structure_confirm_only",
    }


def _candidate_matches_current_mainline(stock, mainline_name):
    if sector_name_matches((stock or {}).get("sector", ""), mainline_name):
        return True
    for term in _iter_text_terms((stock or {}).get("current_driver_tags")):
        if sector_name_matches(term, mainline_name) or _text_term_matches(term, mainline_name):
            return True
    for term in _iter_text_terms((stock or {}).get("concepts")):
        if sector_name_matches(term, mainline_name) or _text_term_matches(term, mainline_name):
            return True
    return False


def _anchor_reversal_rank(decision):
    decision_text = str((decision or {}).get("anchor_reversal_decision") or "").strip()
    priority_text = str((decision or {}).get("repair_priority") or "").strip()
    role_text = str((decision or {}).get("candidate_role") or "").strip()
    if decision_text == "可作为主对象":
        return 4
    if decision_text == "可作为补位":
        return 3
    if priority_text == "优先修复" or role_text == "板块锚":
        return 4
    if priority_text == "次优先修复":
        return 3
    if decision_text == "不参与":
        return 0
    if decision_text == "降级观察":
        return 1
    return 2


def _apply_anchor_reversal_sorting(conviction_list):
    if not conviction_list:
        return []
    has_decision = any(str((item or {}).get("sector_anchor") or "").strip() for item in conviction_list)
    if not has_decision:
        return list(conviction_list)
    return sorted(
        conviction_list,
        key=lambda item: (
            _anchor_reversal_rank(item),
            item.get("conviction_score", 0),
            item.get("tomorrow_strength", 0),
            item.get("连板数", item.get("lianban", 0)),
            -_stable_code_rank(item.get("code", "")),
        ),
        reverse=True,
    )


def build_sector_trend_snapshot(candidates, watchlist, evaluated_stocks, dragon_stocks, zt_pool_by_sector=None, top_n=5, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_sector_trend_snapshot_legacy_body(
            candidates,
            watchlist,
            evaluated_stocks,
            dragon_stocks,
            zt_pool_by_sector=zt_pool_by_sector,
            top_n=top_n,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_extreme_conviction_list(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_extreme_conviction_list_legacy_body(
            evaluated_stocks,
            mainline_name,
            sector_snapshot=sector_snapshot,
            top_n=top_n,
            risk_context=risk_context,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_leader_memory_bank(sector_snapshot, watchlist, dragon_stocks, hot_rank_top30=None, top_n=5, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_leader_memory_bank_legacy_body(
            sector_snapshot,
            watchlist,
            dragon_stocks,
            hot_rank_top30=hot_rank_top30,
            top_n=top_n,
        )
    finally:
        _restore_runtime_bindings(previous)


def _pick_sector_anchor_stock(sector_name, sector_stocks, dragon_stocks):
    if not sector_stocks:
        return None

    dragon_by_code = {
        normalize_stock_code(stock.get("code", "")): stock
        for stock in (dragon_stocks or [])
        if stock_matches_sector(stock, sector_name)
    }

    def _priority(stock):
        code = normalize_stock_code(stock.get("code", ""))
        dragon = dragon_by_code.get(code, {})
        lianban = int(stock.get("连板数", stock.get("lianban", dragon.get("lianban", 0))) or 0)
        tomorrow_strength = _safe_float(stock.get("tomorrow_strength", stock.get("score", 0)))
        raw_score = _safe_float(stock.get("score", 0))
        change = _first_number(stock, "change_pct", "change", "pct_chg", "涨跌幅") or 0.0
        turnover = _first_number(stock, "turnover", "成交额", "amount", "成交金额") or 0.0
        if turnover > 10000:
            turnover = turnover / 1e8
        reason = " / ".join(str((source or {}).get("reason", "") or "") for source in (stock, dragon))
        pattern = str(stock.get("pattern", ""))
        combined = _candidate_combined_text(stock, pattern)
        role_text = str(stock.get("candidate_role") or stock.get("候选身份") or "").strip()
        source_tier = str(stock.get("source_tier") or "").strip()
        source_text = " / ".join(str(stock.get(key) or "") for key in ("source", "_source", "data_source") if stock.get(key))

        def _rank(*keys):
            for key in keys:
                try:
                    value = int(float(str(stock.get(key) or "").strip()))
                except ValueError:
                    continue
                if value > 0:
                    return value
            return 9999

        hot_rank = _rank("hot_rank", "popularity_rank")
        turnover_rank = _rank("turnover_rank")
        anchor_identity = 0
        if role_text == "板块锚":
            anchor_identity += 45
        if code in dragon_by_code:
            anchor_identity += 40
        if _text_contains_any(reason, ("板块锚", "锚定龙", "龙一", "前排")):
            anchor_identity += 30
        if role_text in {"大容量中军", "分支龙头"}:
            anchor_identity += 24
        if source_tier == "anchor_reversal_source" and _text_contains_any(source_text, ("hot_capacity", "成交额", "热榜")):
            anchor_identity += 28
        if turnover >= 100:
            anchor_identity += 30
        elif turnover >= 50:
            anchor_identity += 18
        elif turnover >= 20:
            anchor_identity += 8
        if hot_rank <= 5:
            anchor_identity += 26
        elif hot_rank <= 15:
            anchor_identity += 16
        elif hot_rank <= 30:
            anchor_identity += 8
        if turnover_rank <= 3:
            anchor_identity += 22
        elif turnover_rank <= 10:
            anchor_identity += 12
        elif turnover_rank <= 20:
            anchor_identity += 6
        if _text_contains_any(f"{combined} / {reason}", ("大容量", "趋势资金", "趋势比价链", "反复做", "MA5入/MA7清/MA5T")):
            anchor_identity += 18
        if _text_contains_any(f"{combined} / {reason}", ("低位补涨", "套利工具", "套利载体", "阶段套利", "跟风", "被板块带动")):
            anchor_identity -= 35
        is_one_day_limit = bool(
            lianban <= 1
            and (_text_contains_any(f"{pattern} / {combined} / {source_text}", ("涨停", "首板", "一字板", "T字板")) or change >= 9.5)
        )
        if is_one_day_limit and turnover < 20 and hot_rank > 30 and role_text not in {"板块锚", "大容量中军"}:
            anchor_identity -= 18
        pattern_rank = 0
        if pattern == "一字板":
            pattern_rank = 3
        elif pattern == "T字板":
            pattern_rank = 2
        elif "涨停" in pattern:
            pattern_rank = 1
        return (anchor_identity, tomorrow_strength, raw_score, turnover, lianban, pattern_rank, change)

    return max(sector_stocks, key=_priority)


def _build_sector_trend_snapshot_legacy_body(candidates, watchlist, evaluated_stocks, dragon_stocks, zt_pool_by_sector=None, top_n=5):
    sector_buckets = {}

    def _ensure_bucket(sector_name):
        if not _is_valid_sector_label(sector_name):
            return None
        return sector_buckets.setdefault(
            sector_name,
            {
                "candidates": [],
                "watchlist": [],
                "evaluated": [],
                "candidate_codes": set(),
                "watch_codes": set(),
                "strong_codes": set(),
                "core_codes": set(),
            },
        )

    for stock in candidates or []:
        sector = str(stock.get("sector", "") or "").strip()
        bucket = _ensure_bucket(sector)
        if not bucket:
            continue
        code = normalize_stock_code(stock.get("code", ""))
        bucket["candidates"].append(stock)
        if code:
            bucket["candidate_codes"].add(code)
            if _safe_float(stock.get("score", 0)) >= 50:
                bucket["strong_codes"].add(code)

    for stock in watchlist or []:
        sector = str(stock.get("sector", "") or "").strip()
        bucket = _ensure_bucket(sector)
        if not bucket:
            continue
        code = normalize_stock_code(stock.get("code", ""))
        bucket["watchlist"].append(stock)
        if code:
            bucket["watch_codes"].add(code)

    for stock in evaluated_stocks or []:
        sector = str(stock.get("sector", "") or "").strip()
        bucket = _ensure_bucket(sector)
        if not bucket:
            continue
        code = normalize_stock_code(stock.get("code", ""))
        bucket["evaluated"].append(stock)
        lianban = int(stock.get("连板数", stock.get("lianban", 0)) or 0)
        if code and (_safe_float(stock.get("tomorrow_strength", 0)) >= 60 or lianban >= 2):
            bucket["core_codes"].add(code)

    snapshot = []
    for sector, bucket in sector_buckets.items():
        trend_count = len(bucket["candidate_codes"])
        watch_count = len(bucket["watch_codes"])
        strong_count = len(bucket["strong_codes"])
        core_count = len(bucket["core_codes"])
        limit_up_count = len((zt_pool_by_sector or {}).get(sector, []))
        base_strength_sum = sum(
            _safe_float(s.get("base_strength_score", s.get("score", s.get("tomorrow_strength", 0))))
            for s in bucket["evaluated"][:5]
        )

        anchor_source = (
            list(bucket["evaluated"])
            + list(bucket["watchlist"])
            + list(bucket["candidates"])
            + [stock for stock in (dragon_stocks or []) if stock_matches_sector(stock, sector)]
        )
        anchor_stock = _pick_sector_anchor_stock(sector, anchor_source, dragon_stocks or [])
        anchor_name = anchor_stock.get("name", "-") if anchor_stock else "-"
        anchor_code = normalize_stock_code(anchor_stock.get("code", "")) if anchor_stock else ""
        anchor_lianban = int(anchor_stock.get("连板数", anchor_stock.get("lianban", 0)) or 0) if anchor_stock else 0
        anchor_pattern = str(anchor_stock.get("pattern", "")) if anchor_stock else ""
        raw_anchor_reason = str((anchor_stock or {}).get("anchor_reason") or (anchor_stock or {}).get("reason") or "").strip()
        anchor_status = str((anchor_stock or {}).get("anchor_status") or (anchor_stock or {}).get("status") or "").strip()
        anchor_reason = "板块辨识度最高"
        anchor_identity_text = _candidate_combined_text(anchor_stock, anchor_pattern) if anchor_stock else ""
        anchor_failure_text = " / ".join(text for text in (anchor_status, raw_anchor_reason) if text)
        if _text_contains_any(anchor_failure_text, ("失效", "走弱", "破位", "A杀", "退潮", "杀跌")):
            anchor_reason = raw_anchor_reason or anchor_status
        elif _text_contains_any(anchor_identity_text, ("板块锚", "锚定龙", "大容量", "趋势资金", "MA5入/MA7清/MA5T")):
            anchor_reason = "板块锚，资金更容易反复回看"
        elif anchor_lianban >= 3:
            anchor_reason = "板块高标，资金已记住"
        elif anchor_lianban == 2:
            anchor_reason = "连板先锋，后续优先回看"
        elif "龙一" in str(anchor_stock.get("reason", "")):
            anchor_reason = "首波先锋，优先做重点观察谁"
        elif anchor_pattern in ["一字板", "T字板"]:
            anchor_reason = "强异动已出现，等分歧后再看转强"

        density_points = []
        if trend_count:
            density_points.append({"group": "trend_breadth", "label": "候选扩散", "score": trend_count * 10})
        if watch_count:
            density_points.append({"group": "watch_breadth", "label": "观察池扩散", "score": watch_count * 8})
        if strong_count:
            density_points.append({"group": "sector_strength", "label": "强候选数量", "score": strong_count * 10})
        if core_count:
            density_points.append({"group": "sector_strength", "label": "核心前排数量", "score": core_count * 12})
        if limit_up_count:
            density_points.append({"group": "sector_strength", "label": "涨停池强度", "score": min(limit_up_count, 6) * 4})
        if base_strength_sum:
            density_points.append({"group": "sector_strength", "label": "基础强度合计", "score": int(base_strength_sum / 20)})
        density_dedup = build_grouped_advantage_score(density_points)
        density_score = int(density_dedup["total_score"])

        snapshot.append(
            {
                "sector": sector,
                "trend_count": trend_count,
                "watch_count": watch_count,
                "strong_count": strong_count,
                "core_count": core_count,
                "limit_up_count": limit_up_count,
                "base_strength_sum": base_strength_sum,
                "density_score": density_score,
                "density_dedup": density_dedup,
                "anchor_name": anchor_name,
                "anchor_code": anchor_code,
                "anchor_lianban": anchor_lianban,
                "anchor_reason": anchor_reason,
                "anchor_status": anchor_status,
            }
        )

    snapshot.sort(
        key=lambda x: (
            x.get("density_score", 0),
            x.get("core_count", 0),
            x.get("strong_count", 0),
            x.get("trend_count", 0),
        ),
        reverse=True,
    )
    return snapshot[:top_n]


def _has_st_resume_systemic_risk(risk_context):
    for warning in (risk_context or {}).get("systemic_risk_warnings", []) or []:
        if (
            (warning or {}).get("risk_source") == "st_resume_experience"
            and (warning or {}).get("risk_level") == "high"
        ):
            return True
    return False


def _st_resume_systemic_risk_reason(risk_context):
    for warning in (risk_context or {}).get("systemic_risk_warnings", []) or []:
        if (warning or {}).get("risk_source") == "st_resume_experience":
            return str((warning or {}).get("reason") or "").strip()
    return ""


def _apply_st_resume_observation_policy(candidate, risk_context):
    reason = _st_resume_systemic_risk_reason(risk_context) or "多个突发ST复牌，明日先防守观察。"
    updated = dict(candidate or {})
    updated["systemic_risk_review"] = {
        "status": "降主动性",
        "reason": reason,
        "action": "保留主买/补位比较，但只在固定交易窗口内条件成立后评估50%标准进攻；风险扩散未钝化就回到0%。",
        "position_cap_pct": 50,
    }
    final_review = dict(updated.get("final_risk_review") or {})
    notes = list(final_review.get("notes") or [])
    note = "突发ST复牌经验风险只降低主动性，不直接取消个股买入资格"
    if note not in notes:
        notes.append(note)
    final_review["notes"] = notes
    updated["final_risk_review"] = final_review
    core_identity = dict(updated.get("core_identity") or {})
    if core_identity:
        basis = list(core_identity.get("basis") or [])
        warning_reason = "突发ST复牌经验风险"
        if warning_reason not in basis:
            basis.append(warning_reason)
        core_identity["basis"] = basis
        updated["core_identity"] = core_identity
    return updated


def _is_shape_repair_candidate(stock, trend_review):
    stock = stock or {}
    if (trend_review or {}).get("status") == "通过":
        return False
    if (trend_review or {}).get("action") != "历史趋势样本待修复，重新站回短中线承接后再评估":
        return False
    if _candidate_is_limit_down(stock, change_pct=_first_number(stock, "change_pct", "change", "pct_chg", "涨跌幅"), pattern=str(stock.get("pattern", "") or "")):
        return False
    return _text_contains_any(
        _candidate_combined_text(stock, str(stock.get("pattern", "") or "")),
        ("龙回头", "历史好形态", "趋势比价链", "上升趋势", "平台震荡"),
    )


def _is_dragon_rebound_watch_candidate(stock, trend_review):
    stock = stock or {}
    if (trend_review or {}).get("status") == "通过":
        return False
    text = _candidate_combined_text(stock, str(stock.get("pattern", "") or ""))
    if not _text_contains_any(text, ("龙回头", "龙头回头")):
        return False
    return _text_contains_any(
        text,
        ("A杀", "放量下杀", "杀跌", "弱反抽", "MA20下方", "20日区间低位"),
    ) or (trend_review or {}).get("action") in {
        "降级观察，重新站回关键线并有承接修复后再评估",
        "弱反抽只观察，重新站回MA5/MA20并有承接修复后再评估",
    }


def _shape_repair_priority(item):
    reasons = set(((item or {}).get("trend_aesthetic_review") or {}).get("reasons") or [])
    if "短线承接转弱" in reasons:
        return 2
    if "大跌跌破短中线承接" in reasons:
        return 1
    return 0


def build_extreme_conviction_groups(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None, *, helpers=None):
    conviction_list = build_extreme_conviction_list(
        evaluated_stocks,
        mainline_name,
        sector_snapshot=sector_snapshot,
        top_n=top_n,
        risk_context=risk_context,
        helpers=helpers,
    )
    conviction_codes = {str(item.get("code") or "") for item in conviction_list}
    repair_pool = []
    dragon_rebound_watch_pool = []
    for stock in evaluated_stocks or []:
        code = str((stock or {}).get("code") or "")
        if not code or code in conviction_codes:
            continue
        trend_review = _build_trend_aesthetic_review(stock, pattern=str((stock or {}).get("pattern", "") or ""))
        if _is_dragon_rebound_watch_candidate(stock, trend_review):
            dragon_rebound_watch_pool.append(
                {
                    **stock,
                    "candidate_layer": "dragon_rebound_watch_pool",
                    "execution_eligibility": "dragon_rebound_watch_only",
                    "repair_status": "龙回头观察",
                    "next_action": "单独观察是否重新站回短中线承接；A杀未修复前不进正式名单，继续走坏再取关淘汰",
                    "trend_aesthetic_review": {
                        **trend_review,
                        "reasons": list(dict.fromkeys(list(trend_review.get("reasons") or []) + ["龙回头样本", "A杀未修复"])),
                    },
                }
            )
            continue
        if not _is_shape_repair_candidate(stock, trend_review):
            continue
        repair_pool.append(
            {
                **stock,
                "candidate_layer": "shape_repair_pool",
                "execution_eligibility": "shape_repair_only",
                "repair_status": "待修复",
                "next_action": "保留跟踪，重新站回短中线承接后再评估；继续走坏再取关淘汰",
                "trend_aesthetic_review": trend_review,
            }
        )
    repair_pool.sort(
        key=lambda item: (
            _shape_repair_priority(item),
            _safe_float(item.get("tomorrow_strength", item.get("score", 0)), 0),
            -_stable_code_rank(item.get("code", "")),
        ),
        reverse=True,
    )
    dragon_rebound_watch_pool.sort(
        key=lambda item: (
            _safe_float(item.get("tomorrow_strength", item.get("score", 0)), 0),
            -_stable_code_rank(item.get("code", "")),
        ),
        reverse=True,
    )
    return {
        "extreme_conviction_list": conviction_list,
        "shape_repair_pool": repair_pool,
        "dragon_rebound_watch_pool": dragon_rebound_watch_pool,
    }


def _build_extreme_conviction_list_legacy_body(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None):
    if not evaluated_stocks:
        return []

    anchor_codes = {
        normalize_stock_code(item.get("anchor_code", ""))
        for item in (sector_snapshot or [])
        if item.get("anchor_code")
    }

    conviction_list = []
    for stock in evaluated_stocks:
        driver_tags = _infer_current_driver_tags(stock, mainline_name=mainline_name)
        if driver_tags:
            stock = {**stock, "current_driver_tags": driver_tags}
        code = normalize_stock_code(stock.get("code", ""))
        sector = stock.get("sector", "")
        if not _is_valid_sector_label(sector):
            sector = ""
        tomorrow_strength = _safe_float(stock.get("tomorrow_strength", stock.get("score", 0)))
        lianban = int(stock.get("连板数", stock.get("lianban", 0)) or 0)
        reason = str(stock.get("reason", ""))
        pattern = str(stock.get("pattern", ""))
        is_mainline = _candidate_matches_current_mainline(stock, mainline_name)
        is_anchor = code in anchor_codes
        change_pct = _first_number(stock, "change_pct", "change", "pct_chg", "涨跌幅")
        if not _passes_extreme_conviction_price_gate(
            stock,
            change_pct=change_pct,
            pattern=pattern,
            lianban=lianban,
            is_anchor=is_anchor,
            is_mainline=is_mainline,
            mainline_name=mainline_name,
        ):
            continue
        trend_aesthetic_review = _build_trend_aesthetic_review(stock, pattern=pattern)
        if trend_aesthetic_review["status"] != "通过":
            continue
        selection_shape_review = _build_selection_shape_review(trend_aesthetic_review)
        final_risk_review = _build_final_sniper_risk_review(stock, mainline_name=mainline_name)
        if final_risk_review["status"] == "取消主买/补位资格":
            continue

        advantage_points = []
        suppressed_advantage_points = []
        if is_mainline:
            advantage_points.append({"group": "market_selection", "label": "主线内核", "score": 18})
        if is_anchor:
            advantage_points.append({"group": "market_selection", "label": "板块锚定龙", "score": 12})
        if lianban >= 2:
            lianban_point = {"group": "market_selection", "label": f"{lianban}连板", "score": 8}
            if _strength_already_contains_lianban_bonus(stock, tomorrow_strength=tomorrow_strength, lianban=lianban):
                suppressed_advantage_points.append(lianban_point)
            else:
                advantage_points.append(lianban_point)
        if "龙一" in reason:
            advantage_points.append({"group": "market_selection", "label": "首波先锋", "score": 6})
        if pattern == "T字板":
            advantage_points.append({"group": "shape_confirmation", "label": "分歧转一致形态", "score": 4})
        advantage_dedup = _append_suppressed_advantage_points(
            build_grouped_advantage_score(advantage_points),
            suppressed_advantage_points,
        )
        conviction_score = tomorrow_strength + advantage_dedup["total_score"]
        conviction_score -= _safe_float(final_risk_review.get("score_penalty", 0), 0)

        reason_parts = []
        if is_mainline:
            reason_parts.append("主线内核")
        if is_anchor:
            reason_parts.append("板块锚定龙")
        if lianban >= 2:
            reason_parts.append(f"{lianban}连板")
        elif lianban == 1:
            reason_parts.append("首板")
        elif "龙一" in reason:
            reason_parts.append("首波先锋")
        if pattern == "T字板":
            reason_parts.append("分歧转一致形态")
        elif pattern == "一字板":
            reason_parts.append("资金顶出辨识度")
        elif "光头" in pattern:
            reason_parts.append("强实体异动")
        layer_fields = _candidate_layer_fields(
            stock,
            is_anchor=is_anchor,
            is_mainline=is_mainline,
            lianban=lianban,
            change_pct=change_pct,
            pattern=pattern,
            mainline_name=mainline_name,
        )

        if not reason_parts:
            if layer_fields["candidate_layer"] == "watch_sample":
                reason_parts.append("修复观察")
            else:
                reason_parts.append("趋势辨识度高")
        if (
            trend_aesthetic_review["status"] == "通过"
            and trend_aesthetic_review.get("reasons")
            and trend_aesthetic_review.get("reasons") != ["未见形态破坏"]
        ):
            reason_parts.append("趋势审美")
            reason_parts.extend(_trend_aesthetic_reason_labels(trend_aesthetic_review))

        action_rule = "修复观察只看09:50-10:10窗口，未确认不参与"
        if is_anchor and is_mainline:
            action_rule = "优先盯竞价表态、开盘承接和回封质量，继续强就只做它"
        elif lianban >= 2:
            action_rule = "先看竞价承接，回封或结构确认命中才参与"

        participation_fields = _build_conviction_participation_fields(
            stock,
            sector=sector,
            is_anchor=is_anchor,
            is_mainline=is_mainline,
        )
        leader_speed_profile = _infer_leader_speed_profile(
            stock,
            is_anchor=is_anchor,
            is_mainline=is_mainline,
            lianban=lianban,
            pattern=pattern,
            change_pct=change_pct,
        )
        anchor_reversal_decision = build_anchor_reversal_decision(
            stock,
            sector_snapshot=sector_snapshot or [],
            mainline_name=mainline_name,
        )
        anchor_decision = str(anchor_reversal_decision.get("anchor_reversal_decision") or "").strip()
        if anchor_decision == "不参与":
            action_rule = "板块锚已失效，后排套利/跟风不参与，只记录风险反馈"
            layer_fields = {
                "candidate_layer": "watch_sample",
                "execution_eligibility": "anchor_failed_no_participation",
            }
            participation_fields["attack_state"] = "0%"
            participation_fields["participation_window"] = "no_trade"
        elif anchor_decision == "降级观察" and layer_fields.get("candidate_layer") != "watch_sample":
            action_rule = "板块锚反推未通过，只观察承接，不新增参与"
            layer_fields = {
                "candidate_layer": "watch_sample",
                "execution_eligibility": "anchor_reversal_observation",
            }
            participation_fields["attack_state"] = "0%"
            participation_fields["participation_window"] = "no_trade"
        candidate = {
                **stock,
                "conviction_score": round(conviction_score, 1),
                "conviction_reason": " / ".join(reason_parts),
                "conviction_rule": action_rule,
                **anchor_reversal_decision,
                **layer_fields,
                "core_identity": _build_core_identity_fields(
                    is_anchor=is_anchor,
                    is_mainline=is_mainline,
                    lianban=lianban,
                    reason=reason,
                    pattern=pattern,
                    reason_parts=reason_parts,
                    attack_state=participation_fields.get("attack_state", "50%"),
                ),
                **participation_fields,
                **leader_speed_profile,
                "acceptance_repair_required": _build_acceptance_repair_required(leader_speed_profile),
                "common_selection_check": _build_common_selection_check(stock, sector=sector, is_mainline=is_mainline),
                "final_risk_review": final_risk_review,
                "trend_aesthetic_review": trend_aesthetic_review,
                "selection_shape_review": selection_shape_review,
                "advantage_dedup": advantage_dedup,
            }
        if _has_st_resume_systemic_risk(risk_context):
            candidate = _apply_st_resume_observation_policy(candidate, risk_context)
        conviction_list.append(candidate)

    conviction_list.sort(
        key=lambda x: (
            x.get("conviction_score", 0),
            x.get("tomorrow_strength", 0),
            x.get("连板数", x.get("lianban", 0)),
            -_stable_code_rank(x.get("code", "")),
        ),
        reverse=True,
    )
    conviction_list = _apply_anchor_reversal_sorting(conviction_list)
    return _assign_sniper_roles(conviction_list[:top_n])


def _build_leader_memory_bank_legacy_body(sector_snapshot, watchlist, dragon_stocks, hot_rank_top30=None, top_n=5):
    if not sector_snapshot:
        return []

    hot_rank_map = {
        normalize_stock_code(stock.get("code", "")): idx
        for idx, stock in enumerate(hot_rank_top30 or [], 1)
        if stock.get("code")
    }
    watch_map = {
        normalize_stock_code(stock.get("code", "")): stock
        for stock in (watchlist or [])
        if stock.get("code")
    }
    dragon_map = {
        normalize_stock_code(stock.get("code", "")): stock
        for stock in (dragon_stocks or [])
        if stock.get("code")
    }

    memory_bank = []
    seen_codes = set()
    for item in sector_snapshot:
        code = normalize_stock_code(item.get("anchor_code", ""))
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        watch_stock = watch_map.get(code, {})
        dragon_stock = dragon_map.get(code, {})
        sector = item.get("sector", "") or watch_stock.get("sector", "") or dragon_stock.get("sector", "")
        if not _is_valid_sector_label(sector):
            sector = "未归类"
        lianban = int(
            watch_stock.get("连板数", watch_stock.get("lianban", dragon_stock.get("lianban", item.get("anchor_lianban", 0))))
            or 0
        )
        hot_rank = hot_rank_map.get(code)

        remember_reason_parts = [item.get("anchor_reason", "板块辨识度最高")]
        if hot_rank and hot_rank <= 20:
            remember_reason_parts.append(f"热榜第{hot_rank}")
        if lianban >= 2:
            remember_reason_parts.append(f"{lianban}连板已被资金记住")
        elif "龙一" in str(watch_stock.get("reason", "")):
            remember_reason_parts.append("首波龙一")

        remember_score = _safe_float(item.get("density_score", 0))
        remember_score += 12 if hot_rank and hot_rank <= 10 else 6 if hot_rank and hot_rank <= 20 else 0
        remember_score += lianban * 4

        memory_bank.append(
            {
                "name": item.get("anchor_name", "-") or watch_stock.get("name", "-") or dragon_stock.get("name", "-"),
                "code": code,
                "sector": sector,
                "remember_score": round(remember_score, 1),
                "remember_reason": " / ".join([part for part in remember_reason_parts if part]),
                "remember_window": "10~20个交易日",
                "action_rule": "后续若板块再发力，优先回看它；只在固定交易窗口内做分歧后再转强",
            }
        )

    memory_bank.sort(
        key=lambda item: (
            item.get("remember_score", 0),
            item.get("sector", ""),
        ),
        reverse=True,
    )
    return memory_bank[:top_n]
