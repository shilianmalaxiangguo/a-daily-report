from __future__ import annotations

import daily_report_analysis_utils as analysis_utils

__all__ = [
    "build_extreme_conviction_list",
    "build_leader_memory_bank",
    "build_sector_trend_snapshot",
]

_MISSING = object()


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
        if not sector_name:
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
        tomorrow_strength = _safe_float(stock.get("tomorrow_strength", stock.get("score", 0)))
        lianban = int(stock.get("连板数", stock.get("lianban", 0)) or 0)
        reason = str(stock.get("reason", ""))
        pattern = str(stock.get("pattern", ""))
        is_mainline = sector_name_matches(sector, mainline_name)
        is_anchor = code in anchor_codes

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
        elif "龙一" in reason:
            reason_parts.append("首波先锋")
        if pattern == "T字板":
            reason_parts.append("分歧转一致形态")
        elif pattern == "一字板":
            reason_parts.append("资金顶出辨识度")
        elif "光头" in pattern:
            reason_parts.append("强实体异动")
        if not reason_parts:
            reason_parts.append("趋势辨识度高")

        action_rule = "只盯分歧后的转强，不追情绪顶点"
        if is_anchor and is_mainline:
            action_rule = "优先盯首个60分钟确认，若继续强就只做它"
        elif lianban >= 2:
            action_rule = "先看竞价承接，再等60分钟确认"

        conviction_list.append(
            {
                **stock,
                "conviction_score": round(conviction_score, 1),
                "conviction_reason": " / ".join(reason_parts),
                "conviction_rule": action_rule,
            }
        )

    conviction_list.sort(
        key=lambda x: (
            x.get("conviction_score", 0),
            x.get("tomorrow_strength", 0),
            x.get("连板数", x.get("lianban", 0)),
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
