from __future__ import annotations

import daily_report_analysis_utils as analysis_utils
from selection.candidate_execution_contracts import (
    build_participation_window_from_candidate,
    build_participation_window_policy,
)

__all__ = [
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
}


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
            "title",
            "risk_type",
            "st_reason",
            "st_explain",
            "trade_type",
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
            "异常波动",
            "风险提示公告",
        ),
    )


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


def _passes_extreme_conviction_price_gate(stock, *, change_pct=None, pattern="", lianban=0, is_anchor=False, is_mainline=False):
    if _has_blocking_negative_news(stock):
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


def _candidate_layer_fields(stock, *, is_anchor=False, is_mainline=False, lianban=0, change_pct=None, pattern=""):
    if _has_blocking_negative_news(stock):
        return {
            "candidate_layer": "risk_blocked",
            "execution_eligibility": "blocked_by_negative_news",
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


def build_extreme_conviction_list(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_extreme_conviction_list_legacy_body(
            evaluated_stocks,
            mainline_name,
            sector_snapshot=sector_snapshot,
            top_n=top_n,
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
        change = _safe_float(stock.get("change", 0))
        volume = _safe_float(stock.get("volume", 0))
        reason = str(stock.get("reason", ""))
        pattern = str(stock.get("pattern", ""))
        is_anchor = 1 if ("龙一" in reason or "前排" in reason or code in dragon_by_code) else 0
        pattern_rank = 0
        if pattern == "一字板":
            pattern_rank = 3
        elif pattern == "T字板":
            pattern_rank = 2
        elif "涨停" in pattern:
            pattern_rank = 1
        return (lianban, is_anchor, tomorrow_strength, raw_score, pattern_rank, change, volume)

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
        strength_sum = sum(_safe_float(s.get("tomorrow_strength", s.get("score", 0))) for s in bucket["evaluated"][:5])

        anchor_source = bucket["evaluated"] or bucket["watchlist"] or bucket["candidates"]
        anchor_stock = _pick_sector_anchor_stock(sector, anchor_source, dragon_stocks or [])
        anchor_name = anchor_stock.get("name", "-") if anchor_stock else "-"
        anchor_code = normalize_stock_code(anchor_stock.get("code", "")) if anchor_stock else ""
        anchor_lianban = int(anchor_stock.get("连板数", anchor_stock.get("lianban", 0)) or 0) if anchor_stock else 0
        anchor_pattern = str(anchor_stock.get("pattern", "")) if anchor_stock else ""
        anchor_reason = "板块辨识度最高"
        if anchor_lianban >= 3:
            anchor_reason = "板块高标，资金已记住"
        elif anchor_lianban == 2:
            anchor_reason = "连板先锋，后续优先回看"
        elif "龙一" in str(anchor_stock.get("reason", "")):
            anchor_reason = "首波先锋，优先做重点观察谁"
        elif anchor_pattern in ["一字板", "T字板"]:
            anchor_reason = "强异动已出现，等分歧后再看转强"

        density_score = (
            trend_count * 10
            + watch_count * 8
            + strong_count * 10
            + core_count * 12
            + min(limit_up_count, 6) * 4
            + int(strength_sum / 20)
        )

        snapshot.append(
            {
                "sector": sector,
                "trend_count": trend_count,
                "watch_count": watch_count,
                "strong_count": strong_count,
                "core_count": core_count,
                "limit_up_count": limit_up_count,
                "density_score": density_score,
                "anchor_name": anchor_name,
                "anchor_code": anchor_code,
                "anchor_lianban": anchor_lianban,
                "anchor_reason": anchor_reason,
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


def _build_extreme_conviction_list_legacy_body(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3):
    if not evaluated_stocks:
        return []

    anchor_codes = {
        normalize_stock_code(item.get("anchor_code", ""))
        for item in (sector_snapshot or [])
        if item.get("anchor_code")
    }

    conviction_list = []
    for stock in evaluated_stocks:
        code = normalize_stock_code(stock.get("code", ""))
        sector = stock.get("sector", "")
        if not _is_valid_sector_label(sector):
            sector = ""
        tomorrow_strength = _safe_float(stock.get("tomorrow_strength", stock.get("score", 0)))
        lianban = int(stock.get("连板数", stock.get("lianban", 0)) or 0)
        reason = str(stock.get("reason", ""))
        pattern = str(stock.get("pattern", ""))
        is_mainline = sector_name_matches(sector, mainline_name)
        is_anchor = code in anchor_codes
        change_pct = _first_number(stock, "change_pct", "change", "pct_chg", "涨跌幅")
        if not _passes_extreme_conviction_price_gate(
            stock,
            change_pct=change_pct,
            pattern=pattern,
            lianban=lianban,
            is_anchor=is_anchor,
            is_mainline=is_mainline,
        ):
            continue

        conviction_score = tomorrow_strength
        if is_mainline:
            conviction_score += 18
        if is_anchor:
            conviction_score += 12
        if lianban >= 2:
            conviction_score += 8
        if "龙一" in reason:
            conviction_score += 6
        if pattern == "T字板":
            conviction_score += 4

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
        )

        if not reason_parts:
            if layer_fields["candidate_layer"] == "watch_sample":
                reason_parts.append("修复观察")
            else:
                reason_parts.append("趋势辨识度高")

        action_rule = "修复观察只看09:50-10:10承接确认，未确认不参与"
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
        conviction_list.append(
            {
                **stock,
                "conviction_score": round(conviction_score, 1),
                "conviction_reason": " / ".join(reason_parts),
                "conviction_rule": action_rule,
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
            }
        )

    conviction_list.sort(
        key=lambda x: (
            x.get("conviction_score", 0),
            x.get("tomorrow_strength", 0),
            x.get("连板数", x.get("lianban", 0)),
            -_stable_code_rank(x.get("code", "")),
        ),
        reverse=True,
    )
    return conviction_list[:top_n]


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
                "action_rule": "后续若板块再发力，优先回看它；只做分歧后的60分钟再转强",
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
