from __future__ import annotations

import daily_report_analysis_utils as analysis_utils
from market_data.kline_dates import normalize_kline_date_str as _normalize_kline_date_str

__all__ = [
    "build_abnormal_watch_pool",
    "build_watch_candidate_pool_bundle",
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


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


def sector_name_matches(sector_a, sector_b):
    return analysis_utils.sector_name_matches(sector_a, sector_b)


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


def _build_xuangubao_plate_map(all_data):
    mapped = {}
    reasons = ((all_data or {}).get("xuangubao_data") or {}).get("xuangubao_limit_up_reasons", []) or []
    for item in reasons:
        if not isinstance(item, dict):
            continue
        code = normalize_stock_code(item.get("symbol") or item.get("code") or item.get("stock_code") or "")
        if not code:
            continue
        for plate in item.get("related_plates") or []:
            if not isinstance(plate, dict):
                continue
            name = str(plate.get("plate_name") or plate.get("name") or "").strip()
            if _is_valid_sector_label(name):
                mapped[code] = name
                break
    return mapped


def _resolve_candidate_sector(stock, code, xuangubao_plate_map):
    for value in (stock.get("sector", ""), stock.get("所属行业", ""), stock.get("所属板块", "")):
        if _is_valid_sector_label(value):
            return str(value).strip()
    return xuangubao_plate_map.get(normalize_stock_code(code), "未归类")


def _round_or_none(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _average_numeric(values):
    cleaned = []
    for value in values or []:
        try:
            cleaned.append(float(value))
        except (TypeError, ValueError):
            continue
    return sum(cleaned) / len(cleaned) if cleaned else 0.0


def fetch_recent_price_bars(*args, **kwargs):
    return []


def _resolve_abnormal_setup_signal(abnormal_type, follow_state):
    abnormal_type = str(abnormal_type or "").strip()
    follow_state = str(follow_state or "").strip()

    if follow_state == "新异动待观察":
        setup_id = "fresh_abnormal_probe"
    elif follow_state == "已经转弱":
        setup_id = "abnormal_failed"
    elif abnormal_type == "放量大阳异动":
        setup_id = "burst_hold" if follow_state == "跌不下去" else "burst_digest"
    elif abnormal_type == "长上影异动":
        setup_id = "upper_shadow_reclaim" if follow_state == "跌不下去" else "upper_shadow_digest"
    elif abnormal_type == "恐怖阴线异动":
        setup_id = "horror_wash_hold" if follow_state == "跌不下去" else "horror_wash_digest"
    else:
        setup_id = "abnormal_failed" if follow_state == "已经转弱" else "fresh_abnormal_probe"

    return {
        "id": setup_id,
        "label": setup_id,
        "phase": "",
        "group": "",
        "abnormal_type": abnormal_type,
        "follow_state": follow_state,
    }


def _map_setup_id_to_signal_type(setup_id=""):
    setup_id = str(setup_id or "").strip()
    if setup_id in ("horror_wash_hold", "horror_wash_digest"):
        return "panic_buy"
    if setup_id in ("upper_shadow_reclaim", "upper_shadow_digest"):
        return "sweet_zone"
    if setup_id in ("burst_hold", "burst_digest", "fresh_abnormal_probe"):
        return "breakout"
    return ""


def build_intraday_execution_plan(*args, **kwargs):
    return {}


MAX_SINGLE_TRADE_LOSS_PCT = analysis_utils.MAX_SINGLE_TRADE_LOSS_PCT


def _build_abnormal_follow_rule(abnormal_type, follow_state, anchor_price, abnormal_info):
    abnormal_type = str(abnormal_type or "").strip()
    follow_state = str(follow_state or "").strip()
    if abnormal_type and follow_state:
        return f"{abnormal_type}后重点看{follow_state}，锚点{round(_safe_float(anchor_price), 2) if _safe_float(anchor_price) > 0 else '-'}。"
    return ""


def _refine_abnormal_follow_display(anchor_price, action_rule, minute_plan=None):
    return (round(_safe_float(anchor_price), 2) if _safe_float(anchor_price) > 0 else 0, action_rule)


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.watch_candidates.infer",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_watch_candidate_pool_bundle(all_data, *, emit):
    all_data = all_data or {}
    candidates_dict = {}
    logs = []
    xuangubao_plate_map = _build_xuangubao_plate_map(all_data)

    tr_name_map = {}
    for stock in all_data.get("turnover_rank", []) or []:
        name = stock.get("name", "")
        turnover = stock.get("turnover", 0)
        if name and turnover > 0:
            tr_name_map[name] = turnover

    def safe_add_candidate(stock, source_name, default_turnover=None):
        code = stock.get("code", "") or stock.get("代码", "")
        name = stock.get("name", "") or stock.get("名称", "")
        turnover = stock.get("turnover", 0) or stock.get("成交额", 0) or default_turnover or 0

        if turnover > 10000:
            turnover = turnover / 1e8

        if not code and name:
            for item in all_data.get("turnover_rank", []) or []:
                if item.get("name") == name:
                    code = item.get("code", "")
                    break

        if turnover < 1 and name:
            turnover = tr_name_map.get(name, 0)

        if not code or turnover < 1:
            return False

        if code not in candidates_dict:
            candidates_dict[code] = {
                "code": code,
                "name": name,
                "turnover": turnover,
                "sector": _resolve_candidate_sector(stock, code, xuangubao_plate_map),
                "_source": source_name,
            }
            return True
        return False

    def enrich_new_stock_candidate(candidate, stock):
        candidate.update(
            {
                "_source": stock.get("_source") or "新股研究池",
                "watch_source": stock.get("watch_source") or "new_stock_research_pool",
                "core_level": stock.get("core_level") or "新股预期差候选",
            }
        )
        for key in (
            "candidate_upgrade_reason",
            "new_stock_narrative_score",
            "new_stock_factors",
            "listing_date",
            "listing_window",
            "pre_listing_action",
            "new_stock_cycle_state",
            "c_stage_acceptance",
            "emotion_outlet_status",
            "new_stock_recognition_status",
        ):
            if key in stock:
                candidate[key] = stock.get(key)

    added_count = {"zt": 0, "tr": 0, "lb": 0, "hot": 0, "lhb": 0, "new_stock": 0}

    for stock in all_data.get("zt_pool", []) or []:
        if safe_add_candidate(stock, "涨停池"):
            added_count["zt"] += 1

    for stock in (all_data.get("turnover_rank", []) or [])[:20]:
        if safe_add_candidate(stock, "成交额排名"):
            added_count["tr"] += 1

    for stock in all_data.get("lianban_data", []) or []:
        if safe_add_candidate(stock, "连板"):
            added_count["lb"] += 1

    for stock in all_data.get("hot_rank_top30", []) or []:
        if safe_add_candidate(stock, "热榜"):
            added_count["hot"] += 1

    for stock in all_data.get("lhb_net_buy_top10", []) or []:
        if safe_add_candidate(stock, "龙虎榜"):
            added_count["lhb"] += 1

    counted_new_stock_codes = set()
    for stock in all_data.get("new_stock_candidate_upgrades", []) or []:
        code = stock.get("code", "") or stock.get("代码", "")
        if not code:
            continue
        was_existing = code in candidates_dict
        if safe_add_candidate(stock, "新股研究池", default_turnover=stock.get("turnover", 1)):
            enrich_new_stock_candidate(candidates_dict[code], stock)
            if code not in counted_new_stock_codes:
                added_count["new_stock"] += 1
                counted_new_stock_codes.add(code)
        elif was_existing:
            enrich_new_stock_candidate(candidates_dict[code], stock)
            if code not in counted_new_stock_codes:
                added_count["new_stock"] += 1
                counted_new_stock_codes.add(code)

    candidates = list(candidates_dict.values())
    emit(
        f"   📊 候选池: 涨停{added_count['zt']}只 + 成交额{added_count['tr']}只 + "
        f"连板{added_count['lb']}只 + 热榜{added_count['hot']}只 + 龙虎榜{added_count['lhb']}只 + "
        f"新股{added_count['new_stock']}只 = {len(candidates)}只"
    )
    _append_log(
        logs,
        "infer.watch_candidate_pool",
        "success",
        "已构建 watch_candidates 候选池",
        candidate_count=len(candidates),
        **added_count,
    )

    return {
        "results": {
            "candidates": candidates,
            "added_count": added_count,
        },
        "module_logs": logs,
    }


def build_abnormal_watch_pool(
    target_date,
    candidate_stocks,
    mainline_name="",
    top_n=5,
    scan_limit=None,
    allow_degraded_snapshot=False,
    fast_fail=False,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_abnormal_watch_pool_legacy_body(
            target_date,
            candidate_stocks,
            mainline_name=mainline_name,
            top_n=top_n,
            scan_limit=scan_limit,
            allow_degraded_snapshot=allow_degraded_snapshot,
            fast_fail=fast_fail,
        )
    finally:
        _restore_runtime_bindings(previous)


def _identify_latest_abnormal_bar(recent_bars):
    if not recent_bars or len(recent_bars) < 2:
        return None

    abnormal_candidates = []
    start_idx = max(1, len(recent_bars) - 4)

    for idx in range(start_idx, len(recent_bars)):
        bar = recent_bars[idx]
        prev_bar = recent_bars[idx - 1]

        open_price = _safe_float(bar.get("open", 0))
        high_price = _safe_float(bar.get("high", 0))
        low_price = _safe_float(bar.get("low", 0))
        close_price = _safe_float(bar.get("close", 0))
        volume = _safe_float(bar.get("volume", 0))
        prev_close = _safe_float(prev_bar.get("close", 0))

        if min(open_price, high_price, low_price, close_price) <= 0:
            continue

        change_pct = ((close_price - prev_close) / prev_close * 100) if prev_close > 0 else (
            (close_price - open_price) / open_price * 100
        )
        amplitude_pct = ((high_price - low_price) / low_price * 100) if low_price > 0 else 0.0
        body_pct = (abs(close_price - open_price) / open_price * 100) if open_price > 0 else 0.0
        upper_shadow_pct = (
            (high_price - max(open_price, close_price)) / max(open_price, close_price) * 100
            if max(open_price, close_price) > 0
            else 0.0
        )

        prev_volumes = [
            _safe_float(item.get("volume", 0))
            for item in recent_bars[max(0, idx - 3):idx]
            if _safe_float(item.get("volume", 0)) > 0
        ]
        avg_volume = _average_numeric(prev_volumes)
        volume_ratio = (volume / avg_volume) if avg_volume > 0 else 0.0

        abnormal_type = ""
        abnormal_note = ""
        abnormal_priority = 0

        if close_price < open_price and change_pct <= -5 and amplitude_pct >= 6 and volume_ratio >= 1.2:
            abnormal_type = "恐怖阴线异动"
            abnormal_note = "大阴大振幅，重点看后续还能不能继续杀"
            abnormal_priority = 4
        elif upper_shadow_pct >= 3 and amplitude_pct >= 5 and volume_ratio >= 1.2:
            abnormal_type = "长上影异动"
            abnormal_note = "盘中冲高遇压，重点看承接和回收能力"
            abnormal_priority = 3
        elif close_price > open_price and change_pct >= 5.5 and body_pct >= 3.5 and volume_ratio >= 1.25:
            abnormal_type = "放量大阳异动"
            abnormal_note = "第一波异动已出现，重点看回踩后是否抗跌"
            abnormal_priority = 2

        if not abnormal_type:
            continue

        abnormal_candidates.append(
            {
                "index": idx,
                "date": _normalize_kline_date_str(bar.get("date")),
                "type": abnormal_type,
                "note": abnormal_note,
                "priority": abnormal_priority,
                "change_pct": round(change_pct, 2),
                "volume_ratio": round(volume_ratio, 2),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "body_mid": round((open_price + close_price) / 2, 2),
                "bar": bar,
            }
        )

    if not abnormal_candidates:
        return None

    abnormal_candidates.sort(
        key=lambda item: (
            item.get("index", 0),
            item.get("priority", 0),
            item.get("volume_ratio", 0),
            abs(item.get("change_pct", 0)),
        ),
        reverse=True,
    )
    return abnormal_candidates[0]


def _detect_washout_reclaim_subtype(recent_bars, abnormal_info):
    recent_bars = recent_bars or []
    abnormal_info = abnormal_info or {}
    abnormal_idx = int(_safe_float(abnormal_info.get("index", -1), -1))
    if abnormal_idx < 0 or abnormal_idx >= len(recent_bars):
        return ""

    post_bars = recent_bars[abnormal_idx + 1:]
    if not post_bars:
        return ""

    abnormal_bar = recent_bars[abnormal_idx]
    abnormal_high = _safe_float(abnormal_bar.get("high"))
    abnormal_low = _safe_float(abnormal_bar.get("low"))
    abnormal_open = _safe_float(abnormal_bar.get("open"))
    abnormal_close = _safe_float(abnormal_bar.get("close"))
    latest_bar = post_bars[-1]
    latest_open = _safe_float(latest_bar.get("open"))
    latest_high = _safe_float(latest_bar.get("high"))
    latest_low = _safe_float(latest_bar.get("low"))
    latest_close = _safe_float(latest_bar.get("close"))
    if min(abnormal_high, abnormal_low, abnormal_open, abnormal_close, latest_open, latest_high, latest_low, latest_close) <= 0:
        return ""

    body_top = max(abnormal_open, abnormal_close)
    strong_reclaim = latest_close >= body_top * 0.995
    close_near_high = latest_high <= 0 or (latest_high - latest_close) / latest_close <= 0.01
    low_open_reclaim = latest_open <= abnormal_close * 0.985 and latest_close >= body_top * 0.995 and close_near_high

    gap_down_seen = any(_safe_float(bar.get("open")) < abnormal_low * 0.995 for bar in post_bars)
    gap_up_seen = False
    if len(post_bars) >= 2:
        for idx, bar in enumerate(post_bars[1:], start=1):
            prev_high = _safe_float(post_bars[idx - 1].get("high"))
            bar_open = _safe_float(bar.get("open"))
            if prev_high > 0 and bar_open > prev_high * 1.01:
                gap_up_seen = True
                break
    if gap_down_seen and gap_up_seen and strong_reclaim:
        return "gap_reclaim"
    if low_open_reclaim:
        return "flush_open_reclaim"
    if abnormal_close < abnormal_open and strong_reclaim:
        return "entity_bear_reclaim"
    if abnormal_info.get("type") == "长上影异动" and strong_reclaim:
        return "upper_shadow_eat"
    return ""


def _classify_abnormal_follow_state(recent_bars, abnormal_info):
    abnormal_idx = abnormal_info.get("index", -1)
    if abnormal_idx < 0 or abnormal_idx >= len(recent_bars):
        return "新异动待观察", abnormal_info.get("low", 0)

    post_bars = recent_bars[abnormal_idx + 1:]
    anchor_price = round(_safe_float(abnormal_info.get("low", 0)), 2)
    if not post_bars:
        return "新异动待观察", anchor_price

    latest_bar = post_bars[-1]
    latest_close = _safe_float(latest_bar.get("close", 0))
    post_lows = [_safe_float(bar.get("low", 0)) for bar in post_bars if _safe_float(bar.get("low", 0)) > 0]
    post_volumes = [_safe_float(bar.get("volume", 0)) for bar in post_bars if _safe_float(bar.get("volume", 0)) > 0]

    post_min_low = min(post_lows) if post_lows else anchor_price
    post_avg_volume = _average_numeric(post_volumes)
    abnormal_volume = _safe_float(abnormal_info.get("bar", {}).get("volume", 0))
    volume_shrunk = abnormal_volume > 0 and post_avg_volume > 0 and post_avg_volume <= abnormal_volume * 0.75
    holds_anchor = post_min_low >= anchor_price * 0.99

    abnormal_type = abnormal_info.get("type", "")
    strong_line = _safe_float(abnormal_info.get("body_mid", anchor_price))
    digest_line = anchor_price * 1.03

    if abnormal_type == "放量大阳异动":
        strong_line = _safe_float(abnormal_info.get("close", strong_line)) * 0.98
        digest_line = min(
            _safe_float(abnormal_info.get("open", anchor_price)),
            _safe_float(abnormal_info.get("close", anchor_price)),
        ) * 0.99
    elif abnormal_type == "长上影异动":
        strong_line = max(
            _safe_float(abnormal_info.get("open", strong_line)),
            _safe_float(abnormal_info.get("close", strong_line)),
        ) * 0.995
        digest_line = _safe_float(abnormal_info.get("body_mid", digest_line)) * 0.99

    if not holds_anchor or latest_close < anchor_price * 0.995:
        return "已经转弱", anchor_price
    if latest_close >= strong_line:
        return "跌不下去", anchor_price
    if volume_shrunk and latest_close >= digest_line:
        return "缩量消化", anchor_price
    if latest_close >= anchor_price * 1.02:
        return ("缩量消化", anchor_price) if volume_shrunk else ("跌不下去", anchor_price)
    return "已经转弱", anchor_price


def _build_abnormal_watch_pool_legacy_body(
    target_date,
    candidate_stocks,
    mainline_name="",
    top_n=5,
    scan_limit=None,
    allow_degraded_snapshot=False,
    fast_fail=False,
):
    if not candidate_stocks:
        return []

    state_score_map = {
        "跌不下去": 40,
        "缩量消化": 32,
        "新异动待观察": 24,
        "已经转弱": 8,
    }
    type_score_map = {
        "恐怖阴线异动": 12,
        "长上影异动": 9,
        "放量大阳异动": 8,
    }

    watch_pool = []
    seen_codes = set()

    candidate_iter = candidate_stocks[:scan_limit] if scan_limit else candidate_stocks

    for stock in candidate_iter:
        code = normalize_stock_code(stock.get("code", ""))
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        recent_bars = fetch_recent_price_bars(
            code,
            target_date,
            lookback_days=10,
            fast_fail=fast_fail,
        )
        if len(recent_bars) < 4:
            if allow_degraded_snapshot:
                sector = stock.get("sector", "") or stock.get("所属行业", "") or stock.get("所属板块", "")
                is_mainline = sector_name_matches(sector, mainline_name) if mainline_name else False
                base_score = _safe_float(stock.get("tomorrow_strength", stock.get("score", 0)))
                follow_state = "跌不下去" if (is_mainline or base_score >= 70) else "新异动待观察"
                abnormal_type = "放量大阳异动"
                setup_signal = _resolve_abnormal_setup_signal(abnormal_type, follow_state)
                anchor_price = _safe_float(stock.get("close", stock.get("price", 0)))
                abnormal_score = (
                    state_score_map.get(follow_state, 0)
                    + type_score_map.get(abnormal_type, 0)
                    + min(int(base_score / 10), 12)
                    + (8 if is_mainline else 0)
                )
                watch_pool.append(
                    {
                        "name": stock.get("name", "未知"),
                        "code": code,
                        "sector": sector or "未知",
                        "abnormal_date": target_date,
                        "abnormal_type": abnormal_type,
                        "follow_state": follow_state,
                        "setup_signal_id": setup_signal.get("id", ""),
                        "setup_signal_label": setup_signal.get("label", ""),
                        "setup_signal_phase": setup_signal.get("phase", ""),
                        "anchor_price": round(anchor_price, 2) if anchor_price else 0,
                        "action_rule": "MVP快照回退：先看次日是否继续强于市场，再按预演参与窗口确认。",
                        "abnormal_note": "缺少近期K线，先按强势/主线优先级纳入异常观察。",
                        "abnormal_score": abnormal_score,
                        "source": stock.get("source", ""),
                        "is_mainline": is_mainline,
                        "is_degraded_snapshot": True,
                        "degraded_reason": "missing_recent_bars",
                        "formal_decision_eligible": False,
                    }
                )
            continue

        abnormal_info = _identify_latest_abnormal_bar(recent_bars)
        if not abnormal_info:
            continue

        washout_reclaim_subtype = _detect_washout_reclaim_subtype(recent_bars, abnormal_info)
        follow_state, anchor_price = _classify_abnormal_follow_state(recent_bars, abnormal_info)
        setup_signal = _resolve_abnormal_setup_signal(abnormal_info.get("type", ""), follow_state)
        signal_type = _map_setup_id_to_signal_type(setup_signal.get("id", ""))
        latest_close = _safe_float(recent_bars[-1].get("close", 0))
        minute_plan = (
            build_intraday_execution_plan(
                code,
                target_date,
                latest_close,
                signal_type=signal_type,
                fallback_stop=latest_close * (1 - MAX_SINGLE_TRADE_LOSS_PCT) if latest_close > 0 else None,
            )
            if latest_close > 0
            else {}
        )
        base_action_rule = _build_abnormal_follow_rule(
            abnormal_info.get("type", ""),
            follow_state,
            anchor_price,
            abnormal_info,
        )
        display_anchor_price, display_action_rule = _refine_abnormal_follow_display(
            anchor_price,
            base_action_rule,
            minute_plan,
        )
        sector = stock.get("sector", "") or stock.get("所属行业", "") or stock.get("所属板块", "")
        is_mainline = sector_name_matches(sector, mainline_name) if mainline_name else False
        base_score = _safe_float(stock.get("tomorrow_strength", stock.get("score", 0)))
        abnormal_score = (
            state_score_map.get(follow_state, 0)
            + type_score_map.get(abnormal_info.get("type", ""), 0)
            + min(int(base_score / 10), 12)
            + (8 if is_mainline else 0)
        )

        watch_pool.append(
            {
                "name": stock.get("name", "未知"),
                "code": code,
                "sector": sector or "未知",
                "abnormal_date": abnormal_info.get("date", ""),
                "abnormal_type": abnormal_info.get("type", ""),
                "abnormal_follow_state": follow_state,
                "follow_state": follow_state,
                "setup_signal_id": setup_signal.get("id", ""),
                "setup_signal_label": setup_signal.get("label", ""),
                "setup_signal_phase": setup_signal.get("phase", ""),
                "anchor_price": round(anchor_price, 2) if anchor_price else 0,
                "display_anchor_price": display_anchor_price,
                "confirm_price_60m": _round_or_none(minute_plan.get("confirm_price_60m")),
                "confirm_support_60m": _round_or_none(minute_plan.get("confirm_support_60m")),
                "structure_stop_30m": _round_or_none(minute_plan.get("structure_stop_30m")),
                "confirm_rule_60m": str(minute_plan.get("confirm_rule_60m", "") or "").strip(),
                "washout_reclaim_subtype": washout_reclaim_subtype,
                "action_rule": display_action_rule,
                "raw_action_rule": base_action_rule,
                "abnormal_note": abnormal_info.get("note", ""),
                "abnormal_score": abnormal_score,
                "source": stock.get("source", ""),
                "is_mainline": is_mainline,
                "is_degraded_snapshot": False,
                "degraded_reason": "",
                "formal_decision_eligible": True,
            }
        )

    watch_pool.sort(
        key=lambda item: (
            item.get("abnormal_score", 0),
            item.get("is_mainline", False),
            item.get("abnormal_date", ""),
        ),
        reverse=True,
    )
    return watch_pool[:top_n]
