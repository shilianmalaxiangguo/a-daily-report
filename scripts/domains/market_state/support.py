from __future__ import annotations

import datetime

import daily_report_analysis_utils as analysis_utils
from daily_report_snapshot_io import load_data_snapshot
from market_data.kline_dates import normalize_kline_date_str as _default_normalize_kline_date_str

_DEFAULT_LOAD_DATA_SNAPSHOT = load_data_snapshot

__all__ = [
    "build_market_style_switch_snapshot",
    "build_market_state_machine_snapshot",
    "build_unified_sector_strength_rows",
    "calculate_exit_price_lines",
    "derive_mainline_pulse_snapshot",
    "get_sector_core_hot_stock",
    "get_sector_leader",
    "load_recent_market_turnover_history",
    "load_recent_sector_flow_history",
    "normalize_flow_to_yi",
    "score_abnormal_snapshot",
    "score_environment_snapshot",
    "score_mainline_snapshot",
    "score_memory_snapshot",
    "score_structure_snapshot",
]

_MISSING = object()
_NON_DIRECTIONAL_SECTOR_LABELS = {
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


def _is_directional_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_DIRECTIONAL_SECTOR_LABELS)


def _first_directional_trend_item(items):
    for item in items or []:
        if isinstance(item, dict) and _is_directional_sector_label(item.get("sector")):
            return item
    return {}


def _turnover_rank_amount(row):
    row = row or {}
    for key in ("turnover", "amount_yi", "turnover_yi", "成交额"):
        amount = _safe_float(row.get(key))
        if amount > 0:
            return amount
    return 0.0


def _funding_activity_from_top50(data):
    data = data or {}
    total_turnover = _safe_float(data.get("total_turnover"))
    rank_rows = list(data.get("turnover_rank") or [])
    top50_amount = sum(_turnover_rank_amount(row) for row in rank_rows[:50])
    if total_turnover <= 0 or top50_amount <= 0:
        return {
            "available": False,
            "top50_share_pct": 0.0,
            "regime": "待累计",
            "meaning": "缺少成交额前50或两市成交额，暂不判断资金雨量。",
        }

    share_pct = round(top50_amount / total_turnover * 100, 2)
    if share_pct > 20:
        regime = "资金活跃期"
        meaning = "Top50成交额占比超过20%，说明雨量变大，资金处于活跃期。"
    elif share_pct >= 18:
        regime = "震荡蓄势期"
        meaning = "Top50成交额占比处于18%到20%，资金有活跃但仍在震荡蓄势。"
    else:
        regime = "资金低温期"
        meaning = "Top50成交额占比低于18%，头部资金活跃度不足。"

    return {
        "available": True,
        "top50_share_pct": share_pct,
        "regime": regime,
        "meaning": meaning,
    }


def _new_high_attack_from_feedback(data):
    feedback = (data or {}).get("new_high_feedback") or {}
    if not feedback.get("available"):
        return {
            "available": False,
            "new_high_count": 0,
            "all_a_share_pct": 0.0,
            "leading_sectors": [],
            "strength_label": "待累计",
            "meaning": "缺少阶段新高反馈，暂不判断资金表态方向。",
        }

    count = int(_safe_float(feedback.get("new_high_count")))
    all_a_share_pct = round(_safe_float(feedback.get("all_a_share_pct")), 2)
    sector_rows = []
    for row in feedback.get("sector_distribution") or []:
        sector = str((row or {}).get("sector") or "").strip()
        if _is_directional_sector_label(sector):
            sector_rows.append(
                {
                    "sector": sector,
                    "new_high_count": int(_safe_float((row or {}).get("new_high_count"))),
                    "share_pct": round(_safe_float((row or {}).get("share_pct")), 2),
                }
            )
    leading_sectors = [row["sector"] for row in sector_rows[:3]]
    if all_a_share_pct >= 3 or count >= 150:
        strength_label = "表态强"
    elif all_a_share_pct >= 1.5 or count >= 75:
        strength_label = "表态有效"
    elif count > 0:
        strength_label = "局部表态"
    else:
        strength_label = "待表态"

    direction = "、".join(leading_sectors) if leading_sectors else "未形成清晰雨区"
    return {
        "available": True,
        "new_high_count": count,
        "all_a_share_pct": all_a_share_pct,
        "leading_sectors": leading_sectors,
        "sector_distribution": sector_rows[:5],
        "strength_label": strength_label,
        "meaning": f"阶段新高用于观察资金表态方向，当前雨区主要在{direction}，强度为{strength_label}。",
    }


def _target_sector_alignment(leading_line, new_high_attack):
    leading_line = str(leading_line or "").strip()
    sectors = list((new_high_attack or {}).get("leading_sectors") or [])
    if not leading_line or not sectors:
        return {
            "aligned": False,
            "label": "待确认",
            "meaning": "主线或新高雨区不足，暂不判断标的是否站在雨里。",
        }
    aligned = any(sector_name_matches(leading_line, sector) for sector in sectors)
    if aligned:
        return {
            "aligned": True,
            "label": "主线在雨区",
            "meaning": f"{leading_line}与阶段新高集中方向重合，说明明日核心对象若也在该方向，容器才有放大依据。",
        }
    return {
        "aligned": False,
        "label": "主线不在雨区",
        "meaning": f"{leading_line}不在阶段新高集中方向，市场有雨但暂不证明该方向可放大容器。",
    }


def _build_market_performance_evidence(data, leading_line):
    funding_activity = _funding_activity_from_top50(data)
    new_high_attack = _new_high_attack_from_feedback(data)
    alignment = _target_sector_alignment(leading_line, new_high_attack)
    rain_label = funding_activity.get("regime", "待累计")
    attack_label = new_high_attack.get("strength_label", "待累计")
    if funding_activity.get("available") and new_high_attack.get("available"):
        summary = (
            f"资金雨量处于{rain_label}；阶段新高显示{attack_label}，"
            f"雨区主要在{'、'.join(new_high_attack.get('leading_sectors') or []) or '待确认'}。"
        )
    elif funding_activity.get("available"):
        summary = f"资金雨量处于{rain_label}；新高雨区待累计。"
    elif new_high_attack.get("available"):
        summary = f"资金雨量待累计；阶段新高显示{attack_label}。"
    else:
        summary = "资金雨量和阶段新高雨区均待累计。"
    return {
        "funding_activity": funding_activity,
        "new_high_attack": new_high_attack,
        "target_sector_alignment": alignment,
        "summary": summary,
        "decision_boundary": "单指标不直接给买入或加仓；只作为旧市场表现、主线承接和参与窗口的证据。",
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


def _resolve_database_service_cls():
    service_cls = globals().get("DatabaseService", _MISSING)
    if service_cls is not _MISSING:
        return service_cls
    try:
        from storage.database_service import DatabaseService as service_cls
    except Exception:
        return None
    globals()["DatabaseService"] = service_cls
    return service_cls


def _create_database_service():
    service_cls = _resolve_database_service_cls()
    if service_cls is None:
        return None
    factory = getattr(service_cls, "sqlite_d1_compatible", None)
    if not callable(factory):
        return None
    try:
        return factory()
    except Exception:
        return None


def _should_skip_fact_db(helpers):
    if helpers and "DatabaseService" in helpers:
        return helpers.get("DatabaseService") is None
    return load_data_snapshot is not _DEFAULT_LOAD_DATA_SNAPSHOT


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _optional_float(value):
    try:
        if value in (None, ""):
            return None
        text = str(value).strip()
        if ":" in text:
            text = text.split(":", 1)[0]
        return float(text)
    except (TypeError, ValueError):
        return None


def _round_or_none(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _clamp(value, low, high):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def _data_market_breadth_value(data, observation_snapshot, key):
    data = data or {}
    observation_snapshot = observation_snapshot or {}
    market_stats = data.get("market_stats", {}) or {}
    return data.get(key, market_stats.get(key, observation_snapshot.get(key)))


def _is_heavy_turnover_selloff_context(data, observation_snapshot, current_turnover, turnover_state, turnover_label):
    data = data or {}
    observation_snapshot = observation_snapshot or {}
    indices = data.get("indices", {}) or {}
    sh_index = indices.get("上证指数", {}) or {}
    benchmark_change = _optional_float(
        data.get(
            "benchmark_change_pct",
            sh_index.get("涨跌幅", sh_index.get("change_pct", observation_snapshot.get("benchmark_change_pct"))),
        )
    )
    dt_count = int(
        _safe_float(
            data.get(
                "dt_count",
                len(data.get("dt_pool", []) or [])
                if data.get("dt_pool") is not None
                else observation_snapshot.get("dt_count", 0),
            )
        )
    )
    rise_fall_ratio = _optional_float(_data_market_breadth_value(data, observation_snapshot, "rise_fall_ratio"))
    if rise_fall_ratio is None:
        rise_fall_ratio = _optional_float(_data_market_breadth_value(data, observation_snapshot, "rise_fall_ratio_text"))
    turnover_is_expanding = turnover_state in ("rising", "rebound") or any(
        keyword in str(turnover_label or "") for keyword in ("回升", "放大")
    )
    breadth_broken = dt_count >= 30 or (rise_fall_ratio is not None and rise_fall_ratio < 0.4)
    return bool(
        benchmark_change is not None
        and benchmark_change <= -1.5
        and current_turnover > 0
        and turnover_is_expanding
        and breadth_broken
    )


def _normalize_kline_date_str(value):
    return _default_normalize_kline_date_str(value)


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


def sector_name_matches(sector_a, sector_b):
    return analysis_utils.sector_name_matches(sector_a, sector_b)


def _is_degraded_abnormal_snapshot(item):
    return analysis_utils._is_degraded_abnormal_snapshot(item)


def _split_abnormal_watch_pool(abnormal_watch_pool):
    formal_items = []
    degraded_items = []
    for item in abnormal_watch_pool or []:
        if _is_degraded_abnormal_snapshot(item):
            degraded_items.append(item)
        else:
            formal_items.append(item)
    return formal_items, degraded_items


def _score_to_star_rank(score_pct):
    score_pct = _clamp(score_pct, 0.0, 100.0)
    if score_pct >= 84:
        return 5
    if score_pct >= 72:
        return 4
    if score_pct >= 58:
        return 3
    if score_pct >= 42:
        return 2
    return 1


def _parse_status_board_count(status_label):
    text = str(status_label or "").strip()
    if not text:
        return 0
    if "首板" in text:
        return 1
    if "天" in text and "板" in text:
        after_tian = text.split("天", 1)[1]
        digits = "".join(ch for ch in after_tian if ch.isdigit())
        if digits:
            return int(digits)
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def _count_keyword_hits_in_mapping(mapping, keywords):
    mapping = mapping or {}
    normalized_keywords = [str(keyword or "").upper() for keyword in (keywords or []) if keyword]
    total = 0
    for key, value in mapping.items():
        text = str(key or "").upper()
        if any(keyword in text for keyword in normalized_keywords):
            total += int(_safe_float(value))
    return total


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


def get_previous_date_str(target_date):
    try:
        dt = datetime.datetime.strptime(str(target_date), "%Y-%m-%d").date()
        prev_dt = dt - datetime.timedelta(days=1)
        return prev_dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def score_environment_snapshot(final_gate, position_level):
    return _score_environment_snapshot_legacy_body(final_gate, position_level)


def score_structure_snapshot(market_zhongshu):
    return _score_structure_snapshot_legacy_body(market_zhongshu)


def score_mainline_snapshot(mainline_name, mainline_score, sector_trend_snapshot, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _score_mainline_snapshot_legacy_body(mainline_name, mainline_score, sector_trend_snapshot)
    finally:
        _restore_runtime_bindings(previous)


def score_memory_snapshot(leader_memory_bank, tracking_memory_status, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _score_memory_snapshot_legacy_body(leader_memory_bank, tracking_memory_status)
    finally:
        _restore_runtime_bindings(previous)


def score_abnormal_snapshot(abnormal_watch_pool, selected_candidate, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _score_abnormal_snapshot_legacy_body(abnormal_watch_pool, selected_candidate)
    finally:
        _restore_runtime_bindings(previous)


def normalize_flow_to_yi(value, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _normalize_flow_to_yi_legacy_body(value)
    finally:
        _restore_runtime_bindings(previous)


def load_recent_sector_flow_history(target_date, sector_name, lookback_days=2, max_scan_days=8, *, helpers=None):
    skip_fact_db = _should_skip_fact_db(helpers)
    previous = _install_runtime_bindings(helpers or {})
    try:
        if not skip_fact_db:
            history = _load_recent_sector_flow_history_from_fact_db(
                target_date,
                sector_name,
                lookback_days=lookback_days,
            )
            if history is not None:
                return history
        return _load_recent_sector_flow_history_legacy_body(
            target_date,
            sector_name,
            lookback_days=lookback_days,
            max_scan_days=max_scan_days,
        )
    finally:
        _restore_runtime_bindings(previous)


def load_recent_market_turnover_history(target_date, lookback_days=2, max_scan_days=8, *, helpers=None):
    skip_fact_db = _should_skip_fact_db(helpers)
    previous = _install_runtime_bindings(helpers or {})
    try:
        if not skip_fact_db:
            history = _load_recent_market_turnover_history_from_fact_db(
                target_date,
                lookback_days=lookback_days,
                max_scan_days=max_scan_days,
            )
            if history is not None:
                return history
        return _load_recent_market_turnover_history_legacy_body(
            target_date,
            lookback_days=lookback_days,
            max_scan_days=max_scan_days,
        )
    finally:
        _restore_runtime_bindings(previous)


def calculate_exit_price_lines(core_stock, stock_full_info, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _calculate_exit_price_lines_legacy_body(core_stock, stock_full_info)
    finally:
        _restore_runtime_bindings(previous)


def get_sector_core_hot_stock(sector_name, hot_rank_top30, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_sector_core_hot_stock_legacy_body(sector_name, hot_rank_top30)
    finally:
        _restore_runtime_bindings(previous)


def get_sector_leader(sector_name, dragon_stocks, dt_pool_by_sector, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_sector_leader_legacy_body(sector_name, dragon_stocks, dt_pool_by_sector)
    finally:
        _restore_runtime_bindings(previous)


def build_market_style_switch_snapshot(target_date, data, observation_snapshot=None, abnormal_projection=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_market_style_switch_snapshot_legacy_body(
            target_date,
            data,
            observation_snapshot=observation_snapshot,
            abnormal_projection=abnormal_projection,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_unified_sector_strength_rows(data, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_unified_sector_strength_rows_legacy_body(data)
    finally:
        _restore_runtime_bindings(previous)


def derive_mainline_pulse_snapshot(
    final_gate=None,
    state_code="",
    leading_line="",
    trend_density=0,
    resilient_count=0,
    failed_count=0,
    zt_count=0,
    dt_count=0,
    transition_signal="",
):
    return _derive_mainline_pulse_snapshot_legacy_body(
        final_gate=final_gate,
        state_code=state_code,
        leading_line=leading_line,
        trend_density=trend_density,
        resilient_count=resilient_count,
        failed_count=failed_count,
        zt_count=zt_count,
        dt_count=dt_count,
        transition_signal=transition_signal,
    )


def _derive_mainline_pulse_snapshot(
    final_gate=None,
    state_code="",
    leading_line="",
    trend_density=0,
    resilient_count=0,
    failed_count=0,
    zt_count=0,
    dt_count=0,
    transition_signal="",
):
    return derive_mainline_pulse_snapshot(
        final_gate=final_gate,
        state_code=state_code,
        leading_line=leading_line,
        trend_density=trend_density,
        resilient_count=resilient_count,
        failed_count=failed_count,
        zt_count=zt_count,
        dt_count=dt_count,
        transition_signal=transition_signal,
    )


def _build_market_style_switch_snapshot(target_date, data, observation_snapshot=None, abnormal_projection=None):
    return build_market_style_switch_snapshot(
        target_date,
        data,
        observation_snapshot=observation_snapshot,
        abnormal_projection=abnormal_projection,
    )


def _build_unified_sector_strength_rows(data):
    return build_unified_sector_strength_rows(data)


def build_market_state_machine_snapshot(
    data,
    final_gate,
    position_level,
    exit_analysis,
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    abnormal_watch_pool=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_market_state_machine_snapshot_legacy_body(
            data,
            final_gate,
            position_level,
            exit_analysis,
            main_sectors_info=main_sectors_info,
            secondary_sectors_info=secondary_sectors_info,
            sector_trend_snapshot=sector_trend_snapshot,
            abnormal_watch_pool=abnormal_watch_pool,
        )
    finally:
        _restore_runtime_bindings(previous)


def _score_environment_snapshot_legacy_body(final_gate, position_level):
    if final_gate and final_gate.get("can_new_entry"):
        score = 85
    elif "二档" in str(position_level or ""):
        score = 45
    elif "一档" in str(position_level or ""):
        score = 15
    else:
        score = 55
    if final_gate and final_gate.get("should_reduce"):
        score = max(score - 15, 0)
    return score


def _score_structure_snapshot_legacy_body(market_zhongshu):
    signal = market_zhongshu.get("signal", {}) if market_zhongshu else {}
    signal_type = str(signal.get("signal_type", "") or "")
    status = str(signal.get("status", "") or "")
    text = f"{signal_type} {status}"
    if any(keyword in text for keyword in ["下跌", "向下", "破位"]):
        return 18
    if any(keyword in text for keyword in ["突破", "向上", "上涨"]):
        return 78
    return 48


def _score_mainline_snapshot_legacy_body(mainline_name, mainline_score, sector_trend_snapshot):
    if not mainline_name:
        return 20
    matched_sector = None
    for item in sector_trend_snapshot or []:
        if sector_name_matches(item.get("sector", ""), mainline_name):
            matched_sector = item
            break

    base_score = _safe_float(mainline_score, 0.0)
    if matched_sector:
        density_score = (
            _safe_float(matched_sector.get("trend_count")) * 5
            + _safe_float(matched_sector.get("strong_count")) * 4
            + _safe_float(matched_sector.get("limit_up_count")) * 3
        )
        base_score = max(base_score, 35 + density_score)
    elif base_score <= 0:
        base_score = 35
    return int(_clamp(base_score, 0, 100))


def _score_memory_snapshot_legacy_body(leader_memory_bank, tracking_memory_status):
    validated_count = len((tracking_memory_status or {}).get("today_validated_items", []) or [])
    tentative_count = len((tracking_memory_status or {}).get("today_tentative_items", []) or [])
    leader_count = len(leader_memory_bank or [])
    return int(_clamp(leader_count * 8 + validated_count * 14 + tentative_count * 4, 0, 100))


def _score_abnormal_snapshot_legacy_body(abnormal_watch_pool, selected_candidate):
    abnormal_watch_pool, _ = _split_abnormal_watch_pool(abnormal_watch_pool)
    selected_state = ""
    if selected_candidate:
        selected_state = str(
            selected_candidate.get("abnormal_follow_state", selected_candidate.get("follow_state", "")) or ""
        ).strip()
    resilient_count = len(
        [
            item
            for item in (abnormal_watch_pool or [])
            if item.get("follow_state") in ("跌不下去", "缩量消化")
        ]
    )
    base_score = {
        "跌不下去": 85,
        "缩量消化": 65,
        "新异动待观察": 38,
        "已经转弱": 10,
    }.get(selected_state, 30)
    return int(_clamp(base_score + resilient_count * 4, 0, 100))


def _normalize_flow_to_yi_legacy_body(value):
    value = _safe_float(value, 0.0)
    if abs(value) >= 1000:
        return value / 10000.0
    return value


def _extract_sector_signed_flow(snapshot_data, sector_name):
    if not snapshot_data or not sector_name:
        return None

    sector_fund_flow = snapshot_data.get("sector_fund_flow", {}) or {}
    inflow_sectors = sector_fund_flow.get("inflow", []) if sector_fund_flow else []
    outflow_sectors = sector_fund_flow.get("outflow", []) if sector_fund_flow else []

    for item in inflow_sectors:
        name = item.get("name", "")
        if sector_name_matches(name, sector_name):
            return abs(_safe_float(item.get("zljlr", 0.0)))

    for item in outflow_sectors:
        name = item.get("name", "")
        if sector_name_matches(name, sector_name):
            return -abs(_safe_float(item.get("zljlr", 0.0)))

    return 0.0


def _load_recent_sector_flow_history_from_fact_db(target_date, sector_name, lookback_days=2):
    service = _create_database_service()
    if service is None:
        return None
    end_date = get_previous_date_str(_normalize_kline_date_str(target_date) or target_date)
    if not end_date:
        return None
    try:
        rows = service.query_sector_fund_flow_series(
            end_date,
            sector_name,
            window_days=max(int(lookback_days or 0), 1),
        )
    except Exception:
        return None
    history = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        date = str(row.get("date") or row.get("trade_date") or "").strip()
        inflow = _safe_float(row.get("inflow", row.get("net_inflow_yi")))
        if not date or date >= str(target_date):
            continue
        history.append({"date": date, "inflow": round(inflow, 2)})
    return history[-max(int(lookback_days or 0), 1):]


def _load_recent_sector_flow_history_legacy_body(target_date, sector_name, lookback_days=2, max_scan_days=8):
    history = []
    cursor = _normalize_kline_date_str(target_date)
    scanned_days = 0

    while cursor and len(history) < lookback_days and scanned_days < max_scan_days:
        cursor = get_previous_date_str(cursor)
        if not cursor:
            break
        scanned_days += 1
        snapshot_data, _ = load_data_snapshot(cursor)
        if not snapshot_data:
            continue

        flow_value = _extract_sector_signed_flow(snapshot_data, sector_name)
        if flow_value is None:
            continue
        history.append(
            {
                "date": cursor,
                "inflow": round(_safe_float(flow_value), 2),
            }
        )

    history.reverse()
    return history


def _load_recent_market_turnover_history_from_fact_db(target_date, lookback_days=2, max_scan_days=8):
    service = _create_database_service()
    if service is None:
        return None
    history = []
    cursor = _normalize_kline_date_str(target_date)
    scanned_days = 0
    target_count = max(int(lookback_days or 0), 1)

    while cursor and len(history) < target_count and scanned_days < max_scan_days:
        cursor = get_previous_date_str(cursor)
        if not cursor:
            break
        scanned_days += 1
        try:
            row = service.query_market_daily_total(cursor, market_scope="all_a")
        except Exception:
            return None
        if not row:
            continue
        turnover = _safe_float(row.get("total_amount_yi", row.get("total_turnover_yi", row.get("turnover"))))
        if turnover <= 0:
            continue
        history.append(
            {
                "date": cursor,
                "turnover": round(turnover, 2),
            }
        )

    history.reverse()
    return history


def _load_recent_market_turnover_history_legacy_body(target_date, lookback_days=2, max_scan_days=8):
    history = []
    cursor = _normalize_kline_date_str(target_date)
    scanned_days = 0

    while cursor and len(history) < lookback_days and scanned_days < max_scan_days:
        cursor = get_previous_date_str(cursor)
        if not cursor:
            break
        scanned_days += 1
        snapshot_data, _ = load_data_snapshot(cursor)
        if not snapshot_data:
            continue

        turnover = _safe_float(snapshot_data.get("total_turnover"))
        if turnover <= 0:
            continue
        history.append(
            {
                "date": cursor,
                "turnover": round(turnover, 2),
            }
        )

    history.reverse()
    return history


def _calculate_exit_price_lines_legacy_body(core_stock, stock_full_info):
    if not core_stock:
        return None

    code = normalize_stock_code(core_stock.get("code", ""))
    info = stock_full_info.get(code, {}) if stock_full_info else {}
    close_price = info.get("close", 0) or core_stock.get("close", 0) or 0
    low_price = info.get("low", 0) or core_stock.get("low", 0) or 0

    if not close_price:
        return None

    stop_loss = low_price if low_price and low_price > 0 else close_price * 0.95
    return {
        "code": code,
        "close_price": close_price,
        "stop_loss": round(stop_loss, 2),
    }


def _get_sector_core_hot_stock_legacy_body(sector_name, hot_rank_top30):
    if not sector_name or not hot_rank_top30:
        return None
    for idx, stock in enumerate(hot_rank_top30, 1):
        if stock_matches_sector(stock, sector_name):
            core_stock = dict(stock)
            core_stock["hot_rank"] = idx
            return core_stock
    return None


def _get_sector_leader_legacy_body(sector_name, dragon_stocks, dt_pool_by_sector):
    sector_dragons = [stock for stock in dragon_stocks if stock.get("sector") == sector_name]
    if sector_dragons:
        sector_dragons.sort(key=lambda item: item.get("lianban", 0), reverse=True)
        leader = dict(sector_dragons[0])
        leader["is_limit_down"] = False
        return leader

    dt_stocks = dt_pool_by_sector.get(sector_name, []) if dt_pool_by_sector else []
    if dt_stocks:
        first_dt = dt_stocks[0]
        return {
            "name": first_dt.get("name", "未知"),
            "code": normalize_stock_code(first_dt.get("code", "")),
            "sector": sector_name,
            "lianban": 0,
            "zt_type": "跌停",
            "is_limit_down": True,
        }
    return None


def _extract_market_breadth_snapshot(data, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        market_stats = data.get("market_stats", {}) or {}
        raw_up_count = market_stats.get("up_count")
        raw_down_count = market_stats.get("down_count")

        up_count = int(_safe_float(raw_up_count)) if raw_up_count not in (None, "") else 0
        down_count = int(_safe_float(raw_down_count)) if raw_down_count not in (None, "") else 0
        breadth_available = bool(market_stats) and (up_count > 0 or down_count > 0)

        rise_fall_ratio = None
        if breadth_available:
            if down_count > 0:
                rise_fall_ratio = up_count / down_count
            elif up_count > 0:
                rise_fall_ratio = float(up_count)
            else:
                rise_fall_ratio = 0.0

        rise_fall_ratio_text = f"{rise_fall_ratio:.2f}" if rise_fall_ratio is not None else "暂无"
        up_down_text = f"{up_count}:{down_count}" if breadth_available else "暂无"

        return {
            "up_count": up_count,
            "down_count": down_count,
            "breadth_available": breadth_available,
            "rise_fall_ratio": round(rise_fall_ratio, 4) if rise_fall_ratio is not None else None,
            "rise_fall_ratio_text": rise_fall_ratio_text,
            "up_down_text": up_down_text,
        }
    finally:
        _restore_runtime_bindings(previous)


def _count_keyword_hits_in_items(items, keywords, fields, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        normalized_keywords = [str(keyword or "").upper() for keyword in (keywords or []) if keyword]
        if not normalized_keywords:
            return 0

        seen = set()
        total = 0
        for item in items or []:
            if isinstance(item, dict):
                code = normalize_stock_code(
                    item.get("code", item.get("代码", item.get("stock_code", "")))
                )
                name = str(item.get("name", item.get("名称", "")) or "").strip()
                unique_key = code or name.upper()
                texts = []
                for field in fields:
                    value = item.get(field)
                    if isinstance(value, (list, tuple, set)):
                        texts.extend([str(entry or "") for entry in value])
                    elif value not in (None, ""):
                        texts.append(str(value))
            else:
                unique_key = str(item or "").strip().upper()
                texts = [str(item or "")]

            if not unique_key or unique_key in seen:
                continue
            seen.add(unique_key)

            joined_text = " ".join(texts).upper()
            if any(keyword in joined_text for keyword in normalized_keywords):
                total += 1
        return total
    finally:
        _restore_runtime_bindings(previous)


def get_mainline_star_level(net_inflow, zt_count, dt_count=0, hot_weight=0.0, inflow_history=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        inflow_history = inflow_history or []
        flow_values = [
            _safe_float(item.get("inflow"))
            for item in inflow_history
            if item.get("inflow") is not None
        ]

        inflow_score = _clamp((net_inflow + 3.0) / 15.0 * 100.0, 0.0, 100.0)
        zt_score = _clamp(zt_count / 12.0 * 100.0, 0.0, 100.0)
        breadth_score = _clamp((zt_count - dt_count + 3.0) / 12.0 * 100.0, 0.0, 100.0)
        hot_score = _clamp(hot_weight / 8.0 * 100.0, 0.0, 100.0)

        trend_score = 50.0
        trend_label = "无历史流向对照"
        flow_trend = "unknown"
        if flow_values:
            last_value = flow_values[-1]
            deltas = [net_inflow - last_value]
            if len(flow_values) >= 2:
                deltas.append(flow_values[-1] - flow_values[-2])
            avg_delta = sum(deltas) / len(deltas)
            trend_score = _clamp(50.0 + avg_delta * 4.0, 0.0, 100.0)

            if len(flow_values) >= 2 and net_inflow < flow_values[-1] < flow_values[-2]:
                flow_trend = "shrinking"
                trend_label = f"资金连续收缩（{flow_values[-2]:+.1f}亿→{flow_values[-1]:+.1f}亿→{net_inflow:+.1f}亿）"
            elif net_inflow > last_value:
                flow_trend = "improving"
                trend_label = f"资金回流增强（{last_value:+.1f}亿→{net_inflow:+.1f}亿）"
            elif net_inflow < last_value:
                flow_trend = "weakening"
                trend_label = f"资金略有回落（{last_value:+.1f}亿→{net_inflow:+.1f}亿）"
            else:
                flow_trend = "flat"
                trend_label = f"资金持平（{net_inflow:+.1f}亿）"

        score_pct = (
            inflow_score * 0.36
            + zt_score * 0.24
            + breadth_score * 0.18
            + hot_score * 0.12
            + trend_score * 0.10
        )
        if net_inflow <= 0 and zt_count < 5:
            score_pct -= 6.0
        if dt_count >= 3:
            score_pct -= 8.0
        score_pct = _clamp(score_pct, 0.0, 100.0)

        star_rank = _score_to_star_rank(score_pct)
        return {
            "star_level": "⭐" * star_rank,
            "star_rank": star_rank,
            "score_pct": round(score_pct, 1),
            "trend_label": trend_label,
            "flow_trend": flow_trend,
            "component_scores": {
                "资金": round(inflow_score, 1),
                "涨停广度": round(zt_score, 1),
                "涨跌停结构": round(breadth_score, 1),
                "热度": round(hot_score, 1),
                "连续性": round(trend_score, 1),
            },
        }
    finally:
        _restore_runtime_bindings(previous)


def get_sector_hotlist_weight(sector_name, tag_distribution):
    if not sector_name or not tag_distribution:
        return 0
    total_tags = sum(tag_distribution.values())
    if total_tags <= 0:
        return 0

    if sector_name in tag_distribution:
        return tag_distribution[sector_name] / total_tags * 100

    sector_to_concepts = {
        "通信设备": ["光纤概念", "共封装光学", "CPO", "F5G概念", "5G", "6G概念", "光模块", "光通信", "通信", "高速光互联"],
        "医药医疗": ["创新药", "仿制药", "生物制品", "中药", "化学制药", "医疗器械", "CRO", "CXO", "医疗服务", "重组蛋白"],
        "AI算力": ["算力租赁", "光模块", "CPO", "液冷服务器", "AI芯片", "智算中心", "数据中心", "云计算", "东数西算"],
        "人形机器人": ["减速器", "伺服系统", "传感器", "执行器", "灵巧手", "谐波减速器", "RV减速器"],
        "新能源": ["光伏", "储能", "锂电池", "固态电池", "钠离子电池", "TOPCON电池", "钙钛矿电池", "HJT电池", "风电", "氢能源"],
        "半导体": ["存储芯片", "先进封装", "Chiplet", "光刻胶", "光刻机", "半导体设备", "EDA", "三代半导"],
        "汽车产业链": ["汽车零部件", "智能驾驶", "激光雷达", "毫米波雷达", "车载芯片", "一体化压铸", "热管理"],
        "消费电子": ["MR", "AR", "VR", "折叠屏", "面板", "OLED", "MiniLED", "手机产业链"],
        "商业航天": ["卫星互联网", "火箭发射", "卫星导航", "北斗", "遥感", "星链"],
        "周期资源": ["有色金属", "稀土", "贵金属", "黄金", "铜", "铝", "锂", "钴", "镍", "化工"],
        "金融": ["券商", "银行", "保险", "数字货币", "金融科技", "跨境支付", "稳定币"],
        "消费": ["白酒", "免税", "旅游", "酒店", "食品饮料", "家电", "零售"],
        "房地产": ["房地产开发", "物业管理", "建材", "家居", "基建"],
        "军工": ["航空装备", "航天装备", "船舶", "军工电子", "无人机"],
    }

    related_concepts = sector_to_concepts.get(sector_name, [])
    total_weight = 0
    for tag, count in tag_distribution.items():
        if sector_name in tag or tag in sector_name:
            total_weight += count
            continue
        for concept in related_concepts:
            if concept in tag or tag in concept:
                total_weight += count
                break

    if total_weight > 0:
        return total_weight / total_tags * 100
    return 0


def _get_or_create_sector_bucket(sector_buckets, sector_name):
    sector_name = str(sector_name or "").strip()
    if not sector_name:
        return None

    for bucket in sector_buckets:
        if sector_name_matches(bucket.get("name", ""), sector_name):
            aliases = bucket.setdefault("aliases", set())
            aliases.add(sector_name)
            current_name = bucket.get("name", "")
            if "(分散型)" in current_name and "(分散型)" not in sector_name:
                bucket["name"] = sector_name
            elif sector_name and len(sector_name) < len(current_name or sector_name):
                bucket["name"] = sector_name
            return bucket

    bucket = {
        "name": sector_name,
        "aliases": {sector_name},
        "zt_count": 0,
        "dt_count": 0,
        "dragon_count": 0,
        "net_inflow": 0.0,
        "net_inflow_available": False,
        "net_inflow_source": "",
        "change": 0.0,
        "change_available": False,
        "change_source": "",
        "hot_plate_rank": None,
        "hot_plate_heat": 0.0,
        "hot_plate_change": None,
        "hot_weight": 0.0,
        "hot_stock_count": 0,
        "quadrant_quality_score": 0.0,
        "quadrant_label": "",
        "quadrant_position": None,
        "quadrant_recent_change": None,
        "quadrant_today_change": None,
        "concept_matched_member_count": 0,
        "concept_missing_member_count": 0,
    }
    sector_buckets.append(bucket)
    return bucket


def _match_sector_quadrant_snapshot(sector_name, sector_quadrant):
    if not sector_name or not sector_quadrant:
        return {}

    hs_analysis = (sector_quadrant.get("high_strong_analysis") or {}) if isinstance(sector_quadrant, dict) else {}
    tier_label_map = {
        "tier1_best": "最佳击球区",
        "tier2_good": "优质击球区",
        "tier3_normal": "普通击球区",
        "tier4_edge": "边缘击球区",
    }
    for tier_key, tier_label in tier_label_map.items():
        for item in hs_analysis.get(tier_key, []) or []:
            item_name = item.get("name", "")
            if sector_name_matches(item_name, sector_name):
                return {
                    "quality_score": _safe_float(item.get("quality_score", 0)),
                    "label": tier_label,
                    "position_in_range": _safe_float(item.get("positionInRange")),
                    "recent_change": _safe_float(item.get("recentChange")),
                    "today_change": _optional_float(item.get("todayChange")),
                }

    quadrants = (sector_quadrant.get("quadrants") or {}) if isinstance(sector_quadrant, dict) else {}
    for quadrant_name, quadrant_items in quadrants.items():
        for item in quadrant_items or []:
            item_name = item.get("name", "")
            if sector_name_matches(item_name, sector_name):
                return {
                    "quality_score": _safe_float(item.get("quality_score", 0)),
                    "label": quadrant_name,
                    "position_in_range": _safe_float(item.get("positionInRange")),
                    "recent_change": _safe_float(item.get("recentChange")),
                    "today_change": _optional_float(item.get("todayChange")),
                }
    return {}


def _build_market_style_switch_snapshot_legacy_body(target_date, data, observation_snapshot=None, abnormal_projection=None):
    observation_snapshot = observation_snapshot or {}
    abnormal_projection = abnormal_projection or {}

    current_turnover = _safe_float(data.get("total_turnover"))
    turnover_history = load_recent_market_turnover_history(target_date, lookback_days=2, max_scan_days=8)
    turnover_series = list(turnover_history)
    if current_turnover > 0:
        turnover_series.append(
            {
                "date": _normalize_kline_date_str(target_date),
                "turnover": round(current_turnover, 2),
            }
        )

    prev_turnover = _safe_float(turnover_history[-1].get("turnover")) if turnover_history else 0.0
    prev2_turnover = _safe_float(turnover_history[-2].get("turnover")) if len(turnover_history) >= 2 else 0.0
    turnover_delta_pct = (current_turnover / prev_turnover - 1.0) if current_turnover > 0 and prev_turnover > 0 else None

    turnover_state = "unknown"
    turnover_label = "量能历史不足"
    if current_turnover > 0 and prev_turnover > 0:
        if prev2_turnover > 0 and current_turnover < prev_turnover * 0.97 and prev_turnover < prev2_turnover * 0.97:
            turnover_state = "shrinking"
            turnover_label = "成交额连续回落"
        elif prev2_turnover > 0 and current_turnover > prev_turnover * 1.03 and prev_turnover >= prev2_turnover * 0.98:
            turnover_state = "rising"
            turnover_label = "成交额继续回升"
        elif current_turnover < prev_turnover * 0.97:
            turnover_state = "pullback"
            turnover_label = "成交额冲高后回落"
        elif current_turnover > prev_turnover * 1.03:
            turnover_state = "rebound"
            turnover_label = "成交额重新放大"
        else:
            turnover_state = "flat"
            turnover_label = "成交额横向波动"

    status_distribution = data.get("status_distribution", {}) or {}
    tag_distribution = data.get("tag_distribution", {}) or {}
    high_board_count = sum(
        int(_safe_float(count))
        for label, count in status_distribution.items()
        if _parse_status_board_count(label) >= 3
    )
    subnew_tag_count = max(
        _count_keyword_hits_in_mapping(tag_distribution, ["次新"]),
        _count_keyword_hits_in_items(
            data.get("integrated_hot_list", []) or [],
            ["次新"],
            fields=["all_tags", "sector_tags", "status_tags", "sector"],
        ),
    )
    reorg_tag_count = max(
        _count_keyword_hits_in_mapping(tag_distribution, ["重组", "并购", "借壳"]),
        _count_keyword_hits_in_items(
            data.get("integrated_hot_list", []) or [],
            ["重组", "并购", "借壳"],
            fields=["all_tags", "sector_tags", "status_tags", "sector"],
        ),
    )
    st_stock_count = _count_keyword_hits_in_items(
        (data.get("zt_pool", []) or []) + (data.get("hot_rank_top30", []) or []) + (data.get("integrated_hot_list", []) or []),
        ["ST"],
        fields=["name", "名称"],
    )

    resilient_count = int(_safe_float(observation_snapshot.get("resilient_abnormal_count", 0)))
    failed_count = int(_safe_float(observation_snapshot.get("failed_abnormal_count", 0)))
    trend_density_count = int(_safe_float(observation_snapshot.get("densest_sector_trend_count", 0)))
    leader_memory_count = int(_safe_float(observation_snapshot.get("leader_memory_count", 0)))
    trusted_tracking_count = int(_safe_float(observation_snapshot.get("trusted_tracking_count", 0)))

    trend_signal_count = 0
    trend_evidence = []
    if resilient_count >= 2:
        trend_signal_count += 1
        trend_evidence.append(f"异常承接{resilient_count}强/{failed_count}弱")
    if trend_density_count >= 2:
        trend_signal_count += 1
        trend_evidence.append(f"{observation_snapshot.get('densest_sector', '最强方向')}有{trend_density_count}只活跃趋势股")
    if leader_memory_count >= 3:
        trend_signal_count += 1
        trend_evidence.append(f"龙头记忆保留{leader_memory_count}只")
    if trusted_tracking_count >= 1:
        trend_signal_count += 1
        trend_evidence.append(f"二次确认观察{trusted_tracking_count}只")

    speculative_signal_count = 0
    speculative_evidence = []
    if high_board_count >= 3:
        speculative_signal_count += 1
        speculative_evidence.append(f"3板及以上{high_board_count}只")
    if subnew_tag_count > 0:
        speculative_signal_count += 1
        speculative_evidence.append(f"次新热度{int(subnew_tag_count)}")
    if reorg_tag_count > 0:
        speculative_signal_count += 1
        speculative_evidence.append(f"重组热度{int(reorg_tag_count)}")
    if st_stock_count > 0:
        speculative_signal_count += 1
        speculative_evidence.append(f"ST活跃{int(st_stock_count)}只")

    heavy_turnover_selloff = _is_heavy_turnover_selloff_context(
        data,
        observation_snapshot,
        current_turnover,
        turnover_state,
        turnover_label,
    )
    if heavy_turnover_selloff:
        style_code = "defense"
        style_label = "放量杀跌"
        style_reason = (
            f"{turnover_label}但指数大跌、跌停扩散、涨跌比极差，说明这不是增量进攻，"
            "更像量化动量和风控卖出互相强化后的卖压释放。"
        )
        primary_action = "先防踩踏，等指数图形和主攻线承接同时修复后再给买入资格。"
        switch_action = "若次日放量反包且跌停明显收敛，再重新看局部主攻线是否变成可参与方向。"
    elif turnover_state in ("rising", "rebound") and trend_signal_count >= max(2, speculative_signal_count):
        style_code = "trend"
        style_label = "趋势分歧优先"
        style_reason = f"{turnover_label}，而异常承接和趋势密度都还在，明天更适合等主线趋势分歧，不适合抢纯情绪一致加速。"
        primary_action = "优先做主线趋势股的分歧承接，宁可慢一点，也不抢一致高潮。"
        switch_action = "若首小时量能明显回落，再把关注重心降到高辨识投机先手。"
    elif turnover_state == "shrinking" and speculative_signal_count >= max(2, trend_signal_count):
        style_code = "speculation"
        style_label = "投机先手优先"
        style_reason = f"{turnover_label}，情绪端更适合快进快出，明天重点看高辨识投机先手，不接受买后磨蹭。"
        primary_action = "优先做高辨识投机先手，买后不爆发就撤，不把仓位耗在磨蹭票上。"
        switch_action = "若首小时量能重新放大且主线承接更集中，再切回趋势分歧。"
    else:
        style_code = "dual"
        style_label = "双轨准备"
        style_reason = f"{turnover_label}，但趋势承接没有塌，连板/次新等情绪端也在冒头，明天需要先看量能再决定跟哪一侧。"
        primary_action = "两手准备：量缩偏投机先手，量增回主线趋势分歧。"
        switch_action = "开盘先看首小时量能和主线承接，谁更强，就给谁买入资格。"

    turnover_series_text = " -> ".join(
        f"{item.get('date', '')}:{_safe_float(item.get('turnover')):.0f}亿"
        for item in turnover_series
        if _safe_float(item.get("turnover")) > 0
    ) or "暂无量能序列"

    evidence_parts = [turnover_series_text]
    if trend_evidence:
        evidence_parts.append(trend_evidence[0])
    if speculative_evidence:
        evidence_parts.append(speculative_evidence[0])

    return {
        "style_code": style_code,
        "style_label": style_label,
        "style_reason": style_reason,
        "primary_action": primary_action,
        "switch_action": switch_action,
        "turnover_state": turnover_state,
        "turnover_label": turnover_label,
        "turnover_series": turnover_series,
        "turnover_series_text": turnover_series_text,
        "turnover_delta_pct": _round_or_none(turnover_delta_pct, 4),
        "trend_signal_count": trend_signal_count,
        "trend_evidence": trend_evidence[:4],
        "speculative_signal_count": speculative_signal_count,
        "speculative_evidence": speculative_evidence[:4],
        "high_board_count": high_board_count,
        "subnew_tag_count": int(subnew_tag_count),
        "reorg_tag_count": int(reorg_tag_count),
        "st_stock_count": int(st_stock_count),
        "projection_label": abnormal_projection.get("projection_label", ""),
        "evidence_text": "；".join([part for part in evidence_parts if part]),
    }


def _build_unified_sector_strength_rows_legacy_body(data):
    data = data or {}
    target_date = str(data.get("target_date", "") or "")
    zt_pool_by_sector = data.get("zt_pool_by_sector", {}) or {}
    dt_pool_by_sector = data.get("dt_pool_by_sector", {}) or {}
    sector_fund_flow = data.get("sector_fund_flow", {}) or {}
    hot_plates = data.get("hot_plates", []) or []
    hot_rank_top30 = data.get("hot_rank_top30", []) or []
    tag_distribution = data.get("tag_distribution", {}) or {}
    sector_quadrant = data.get("sector_quadrant", {}) or {}

    sector_buckets = []

    for sector_name, stocks in zt_pool_by_sector.items():
        bucket = _get_or_create_sector_bucket(sector_buckets, sector_name)
        if not bucket:
            continue
        bucket["zt_count"] = max(bucket.get("zt_count", 0), len(stocks or []))
        dragon_count = sum(
            1 for stock in (stocks or [])
            if int(_safe_float(stock.get("连板数", stock.get("lianban", 0)))) >= 2
        )
        bucket["dragon_count"] = max(bucket.get("dragon_count", 0), dragon_count)

    for sector_name, stocks in dt_pool_by_sector.items():
        bucket = _get_or_create_sector_bucket(sector_buckets, sector_name)
        if not bucket:
            continue
        bucket["dt_count"] = max(bucket.get("dt_count", 0), len(stocks or []))

    for item in sector_fund_flow.get("inflow", []) or []:
        bucket = _get_or_create_sector_bucket(sector_buckets, item.get("name", ""))
        if not bucket:
            continue
        net_inflow = _optional_float(item.get("zljlr", item.get("net_inflow", item.get("net_amount"))))
        if net_inflow is not None:
            bucket["net_inflow"] = net_inflow
            bucket["net_inflow_available"] = True
            bucket["net_inflow_source"] = "fund_flow"
        change = _optional_float(item.get("zdf", item.get("change_pct")))
        if change is not None:
            bucket["change"] = change
            bucket["change_available"] = True
            bucket["change_source"] = "fund_flow"

    for item in sector_fund_flow.get("outflow", []) or []:
        bucket = _get_or_create_sector_bucket(sector_buckets, item.get("name", ""))
        if not bucket:
            continue
        net_inflow = _optional_float(item.get("zljlr", item.get("net_inflow", item.get("net_amount"))))
        if net_inflow is not None and not bucket.get("net_inflow_available"):
            bucket["net_inflow"] = net_inflow
            bucket["net_inflow_available"] = True
            bucket["net_inflow_source"] = "fund_flow"
        change = _optional_float(item.get("zdf", item.get("change_pct")))
        if change is not None and not bucket.get("change_available"):
            bucket["change"] = change
            bucket["change_available"] = True
            bucket["change_source"] = "fund_flow"

    concept_flow = data.get("concept_fund_flow") or {}
    concept_flow_rows = []
    if isinstance(concept_flow, dict):
        concept_flow_rows = list(concept_flow.get("rows") or [])
    elif isinstance(concept_flow, list):
        concept_flow_rows = list(concept_flow)
    for item in concept_flow_rows:
        bucket = _get_or_create_sector_bucket(sector_buckets, (item or {}).get("name", ""))
        if not bucket:
            continue
        net_inflow = _optional_float((item or {}).get("net_inflow", (item or {}).get("net_amount")))
        if net_inflow is not None:
            bucket["net_inflow"] = net_inflow
            bucket["net_inflow_available"] = True
            bucket["net_inflow_source"] = "concept_member_moneyflow"
        change = _optional_float((item or {}).get("change_pct", (item or {}).get("zdf")))
        if change is not None and not bucket.get("change_available"):
            bucket["change"] = change
            bucket["change_available"] = True
            bucket["change_source"] = "concept_member_moneyflow"
        bucket["concept_matched_member_count"] = int(_safe_float((item or {}).get("matched_member_count"), 0))
        bucket["concept_missing_member_count"] = int(_safe_float((item or {}).get("missing_member_count"), 0))

    for plate in hot_plates[:20]:
        bucket = _get_or_create_sector_bucket(sector_buckets, plate.get("name", ""))
        if not bucket:
            continue
        plate_rank = int(_safe_float(plate.get("order", plate.get("rank", 0))) or 0) or None
        current_rank = bucket.get("hot_plate_rank")
        if current_rank is None or (plate_rank and plate_rank < current_rank):
            bucket["hot_plate_rank"] = plate_rank
        bucket["hot_plate_heat"] = max(bucket.get("hot_plate_heat", 0.0), _safe_float(plate.get("rate", 0.0)))
        plate_change = _optional_float(plate.get("change_pct", plate.get("zdf", plate.get("change"))))
        if plate_change is not None:
            bucket["hot_plate_change"] = plate_change
            if not bucket.get("change_available"):
                bucket["change"] = plate_change
                bucket["change_available"] = True
                bucket["change_source"] = "hot_plate"

    for bucket in sector_buckets:
        bucket["hot_weight"] = _safe_float(get_sector_hotlist_weight(bucket.get("name", ""), tag_distribution))
        quadrant_snapshot = _match_sector_quadrant_snapshot(bucket.get("name", ""), sector_quadrant)
        bucket["quadrant_quality_score"] = _safe_float(quadrant_snapshot.get("quality_score", 0.0))
        bucket["quadrant_label"] = quadrant_snapshot.get("label", "")
        bucket["quadrant_position"] = quadrant_snapshot.get("position_in_range")
        bucket["quadrant_recent_change"] = quadrant_snapshot.get("recent_change")
        bucket["quadrant_today_change"] = quadrant_snapshot.get("today_change")
        if bucket["quadrant_today_change"] is not None and not bucket.get("change_available"):
            bucket["change"] = bucket["quadrant_today_change"]
            bucket["change_available"] = True
            bucket["change_source"] = "sector_quadrant"

    for stock in hot_rank_top30[:30]:
        for bucket in sector_buckets:
            if stock_matches_sector(stock, bucket.get("name", "")):
                bucket["hot_stock_count"] = int(bucket.get("hot_stock_count", 0)) + 1

    rows = []
    for bucket in sector_buckets:
        sector_name = bucket.get("name", "")
        if not sector_name:
            continue

        inflow_history = load_recent_sector_flow_history(target_date, sector_name, lookback_days=2) if target_date else []
        star_snapshot = get_mainline_star_level(
            bucket.get("net_inflow", 0.0),
            bucket.get("zt_count", 0),
            dt_count=bucket.get("dt_count", 0),
            hot_weight=bucket.get("hot_weight", 0.0),
            inflow_history=inflow_history,
        )
        if not bucket.get("net_inflow_available"):
            star_snapshot = dict(star_snapshot)
            star_snapshot["trend_label"] = "资金流向未匹配"
            star_snapshot["flow_trend"] = "unknown"

        base_score = _safe_float(star_snapshot.get("score_pct", 0.0))
        hot_plate_rank = bucket.get("hot_plate_rank")
        hot_plate_bonus = 0.0
        if hot_plate_rank:
            hot_plate_bonus += max(18.0 - (hot_plate_rank - 1) * 2.0, 0.0)
            if hot_plate_rank <= 3:
                hot_plate_bonus += 4.0
        hot_stock_bonus = min(bucket.get("hot_stock_count", 0) * 4.0, 14.0)
        dragon_bonus = min(bucket.get("dragon_count", 0) * 4.0, 10.0)
        quadrant_bonus = min(bucket.get("quadrant_quality_score", 0.0) * 0.18, 16.0)
        heat_bonus = min(bucket.get("hot_weight", 0.0) * 0.4, 8.0)
        change_bonus = _clamp(_safe_float(bucket.get("change", 0.0)) * 1.8, -6.0, 8.0)
        outflow_penalty = 6.0 if bucket.get("net_inflow", 0.0) < 0 and bucket.get("zt_count", 0) < 2 else 0.0
        dt_penalty = min(bucket.get("dt_count", 0) * 4.0, 12.0)
        unified_score = _clamp(
            base_score * 0.62
            + hot_plate_bonus
            + hot_stock_bonus
            + dragon_bonus
            + quadrant_bonus
            + heat_bonus
            + change_bonus
            - outflow_penalty
            - dt_penalty,
            0.0,
            100.0,
        )

        is_main = (
            unified_score >= 55
            or (
                hot_plate_rank
                and hot_plate_rank <= 3
                and (
                    bucket.get("zt_count", 0) >= 2
                    or bucket.get("hot_stock_count", 0) >= 2
                    or bucket.get("quadrant_quality_score", 0.0) >= 60
                )
            )
            or (bucket.get("zt_count", 0) >= 5 and bucket.get("net_inflow", 0.0) > 0)
        )
        is_secondary = (
            not is_main
            and (
                unified_score >= 38
                or (hot_plate_rank and hot_plate_rank <= 6)
                or bucket.get("zt_count", 0) >= 2
                or bucket.get("hot_stock_count", 0) >= 2
                or bucket.get("quadrant_quality_score", 0.0) >= 50
            )
        )
        if is_main:
            role = "main"
        elif is_secondary:
            role = "secondary"
        else:
            role = "observe"

        strength = "strong" if unified_score >= 70 else "medium" if unified_score >= 55 else "probe" if unified_score >= 40 else "weak"
        evidence_parts = []
        if bucket.get("zt_count", 0):
            evidence_parts.append(f"涨停{bucket.get('zt_count', 0)}")
        if abs(_safe_float(bucket.get("net_inflow", 0.0))) > 0:
            evidence_parts.append(f"资金{bucket.get('net_inflow', 0.0):+.1f}亿")
        if hot_plate_rank:
            evidence_parts.append(f"板块热榜#{hot_plate_rank}")
        if bucket.get("hot_stock_count", 0):
            evidence_parts.append(f"热股{bucket.get('hot_stock_count', 0)}")
        if bucket.get("quadrant_label"):
            evidence_parts.append(f"{bucket.get('quadrant_label')}")

        rows.append(
            {
                "name": sector_name,
                "zt_count": int(bucket.get("zt_count", 0)),
                "dt_count": int(bucket.get("dt_count", 0)),
                "change": round(_safe_float(bucket.get("change", 0.0)), 2),
                "change_available": bool(bucket.get("change_available")),
                "change_source": bucket.get("change_source", ""),
                "net_inflow": round(_safe_float(bucket.get("net_inflow", 0.0)), 2),
                "net_inflow_available": bool(bucket.get("net_inflow_available")),
                "net_inflow_source": bucket.get("net_inflow_source", ""),
                "strength": strength,
                "star_level": star_snapshot.get("star_level", "⭐"),
                "star_score_pct": round(base_score, 1),
                "unified_score": round(unified_score, 1),
                "role": role,
                "dragon_count": int(bucket.get("dragon_count", 0)),
                "hot_plate_rank": hot_plate_rank,
                "hot_plate_change": _round_or_none(bucket.get("hot_plate_change")),
                "hot_stock_count": int(bucket.get("hot_stock_count", 0)),
                "hot_weight": round(_safe_float(bucket.get("hot_weight", 0.0)), 2),
                "quadrant_quality_score": round(_safe_float(bucket.get("quadrant_quality_score", 0.0)), 1),
                "quadrant_label": bucket.get("quadrant_label", ""),
                "concept_matched_member_count": int(bucket.get("concept_matched_member_count", 0)),
                "concept_missing_member_count": int(bucket.get("concept_missing_member_count", 0)),
                "trend_label": star_snapshot.get("trend_label", ""),
                "flow_trend": star_snapshot.get("flow_trend", ""),
                "score_detail": {
                    "连续主线分": round(base_score, 1),
                    "板块热榜加分": round(hot_plate_bonus, 1),
                    "热股加分": round(hot_stock_bonus, 1),
                    "龙头加分": round(dragon_bonus, 1),
                    "击球区加分": round(quadrant_bonus, 1),
                    "热度加分": round(heat_bonus, 1),
                    "涨跌幅修正": round(change_bonus, 1),
                    "风险扣分": round(outflow_penalty + dt_penalty, 1),
                },
                "evidence": " / ".join(evidence_parts) if evidence_parts else "结构证据不足",
            }
        )

    rows.sort(
        key=lambda item: (
            item.get("unified_score", 0),
            item.get("zt_count", 0),
            item.get("net_inflow", 0.0),
            -int(item.get("hot_plate_rank") or 999),
        ),
        reverse=True,
    )
    return rows


def _derive_mainline_pulse_snapshot_legacy_body(
    final_gate=None,
    state_code="",
    leading_line="",
    trend_density=0,
    resilient_count=0,
    failed_count=0,
    zt_count=0,
    dt_count=0,
    transition_signal="",
):
    final_gate = final_gate or {}
    state_code = str(state_code or "").strip()
    leading_line = str(leading_line or "").strip()
    transition_signal = str(transition_signal or "").strip()
    can_new_entry = bool(final_gate.get("can_new_entry"))
    should_reduce = bool(final_gate.get("should_reduce"))
    allow_attack_50_ready = bool(final_gate.get("allow_attack_50_ready"))
    operation_state = str(final_gate.get("operation_state", "") or "").strip()

    if trend_density >= 3 and resilient_count >= 2 and zt_count <= 25:
        driver_type = "趋势抱团驱动"
    elif leading_line and trend_density >= 2 and resilient_count >= 1:
        driver_type = "逻辑催化驱动"
    elif zt_count >= 30:
        driver_type = "情绪驱动"
    else:
        driver_type = "混合驱动"

    if state_code == "contract":
        pulse_stage = "退潮"
    elif state_code == "expand":
        pulse_stage = "加速" if (zt_count >= 40 or trend_density >= 3) else "启动"
    elif state_code == "migrate":
        pulse_stage = "钝化" if transition_signal == "downgrade_risk" else "高位分歧"
    elif state_code == "probe":
        pulse_stage = "分歧承接" if resilient_count >= 2 else "启动"
    else:
        pulse_stage = "启动"

    if resilient_count >= 2 and failed_count == 0:
        acceptance_quality = "强承接"
    elif resilient_count >= 1 and failed_count <= 1:
        acceptance_quality = "分歧承接"
    elif failed_count >= max(2, resilient_count):
        acceptance_quality = "承接转弱"
    else:
        acceptance_quality = "承接一般"

    if state_code == "contract" or transition_signal == "downgrade_risk" or dt_count >= 8:
        passivation_risk = "高"
    elif state_code in {"migrate", "probe"} or failed_count > 0:
        passivation_risk = "中"
    else:
        passivation_risk = "低"

    if not can_new_entry:
        if state_code == "migrate" and transition_signal == "upgrade_ready":
            execution_bias = "prep_only"
            pulse_action_bias = "只保留条件执行预备态"
            pulse_action_reason = (
                f"{leading_line or '主线'}优势开始拉开，但环境条件仍未正式满足；只能保留条件执行预备态，等待次日60分钟确认。"
            )
        elif operation_state == "撤退态":
            execution_bias = "avoid"
            pulse_action_bias = "禁止参与"
            pulse_action_reason = "环境已转撤退，先退出，等下一轮新脉冲。"
        elif allow_attack_50_ready and not should_reduce:
            execution_bias = "conditional_defense"
            pulse_action_bias = "只保留参与窗口预演"
            pulse_action_reason = f"{leading_line or '主线'}仍有观察价值，但环境条件未正式满足；只做参与窗口预演，强核心看竞价表态、开盘前几分钟或回封，普通结构才等60分钟确认，命中后才评估50%标准进攻。"
        elif should_reduce or state_code == "contract":
            execution_bias = "reduce_only"
            pulse_action_bias = "只减不加"
            pulse_action_reason = "环境条件未满足且主线偏弱，当前只允许处理旧仓，不再给新增买入资格。"
        else:
            execution_bias = "watch_only"
            pulse_action_bias = "只观察不出手"
            pulse_action_reason = "环境条件尚未正式满足，研究与观察优先于执行。"
    else:
        if pulse_stage == "退潮":
            execution_bias = "avoid"
            pulse_action_bias = "禁止参与"
            pulse_action_reason = "主线脉冲已经进入退潮段，继续参与性价比极差。"
        elif pulse_stage == "钝化":
            execution_bias = "watch_only"
            pulse_action_bias = "只减不加"
            pulse_action_reason = "主线脉冲已经钝化，逻辑未必错，但这段不再适合追。"
        elif pulse_stage in {"高位分歧", "分歧承接"}:
            execution_bias = "divergence_only"
            pulse_action_bias = "只做分歧承接"
            pulse_action_reason = "当前只能等主线分歧承接后的确认，不做一致加速追价。"
        else:
            execution_bias = "allow_execute"
            pulse_action_bias = "允许做启动/强化段"
            pulse_action_reason = "主线仍处于可参与的启动或强化段，可以继续围绕最强对象做减法。"

    return {
        "driver_type": driver_type,
        "pulse_stage": pulse_stage,
        "acceptance_quality": acceptance_quality,
        "passivation_risk": passivation_risk,
        "execution_bias": execution_bias,
        "pulse_action_bias": pulse_action_bias,
        "pulse_action_reason": pulse_action_reason,
    }


def _build_market_state_machine_snapshot_legacy_body(
    data,
    final_gate,
    position_level,
    exit_analysis,
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    abnormal_watch_pool=None,
):
    main_sectors_info = main_sectors_info or []
    secondary_sectors_info = secondary_sectors_info or []
    sector_trend_snapshot = sector_trend_snapshot or []
    abnormal_watch_pool, degraded_abnormal_watch_pool = _split_abnormal_watch_pool(abnormal_watch_pool)

    indices = data.get("indices", {}) or {}
    sh_index = indices.get("上证指数", {}) or {}
    breadth_snapshot = _extract_market_breadth_snapshot(data)
    up_count = int(_safe_float(breadth_snapshot.get("up_count", 0)))
    down_count = int(_safe_float(breadth_snapshot.get("down_count", 0)))
    rise_fall_ratio = breadth_snapshot.get("rise_fall_ratio")
    breadth_available = bool(breadth_snapshot.get("breadth_available"))
    zt_count = len(data.get("zt_pool", []) or [])
    dt_count = len(data.get("dt_pool", []) or [])
    turnover = _safe_float(data.get("total_turnover", 0.0))
    sh_change = _safe_float(sh_index.get("涨跌幅", sh_index.get("change_pct", 0.0)))
    quadrant_data = data.get("sector_quadrant") or {}
    hs_total = 0
    high_strong_sector_text = "暂无"
    if quadrant_data and quadrant_data.get("high_strong_analysis"):
        hs_total = int(_safe_float((quadrant_data.get("high_strong_analysis") or {}).get("total", 0)))
        high_strong_sector_text = f"{hs_total}个"

    mainline_name = exit_analysis.get("sector_name", "") if exit_analysis else ""
    mainline_candidates = [item.get("name", "") for item in main_sectors_info if item.get("name")]
    secondary_candidates = [item.get("name", "") for item in secondary_sectors_info if item.get("name")]
    leading_line = mainline_name or (mainline_candidates[0] if mainline_candidates else "")

    resilient_count = len(
        [item for item in abnormal_watch_pool if item.get("follow_state") in ("跌不下去", "缩量消化")]
    )
    failed_count = len([item for item in abnormal_watch_pool if item.get("follow_state") == "已经转弱"])

    densest_sector = _first_directional_trend_item(sector_trend_snapshot)
    densest_sector_name = densest_sector.get("sector", "")
    trend_density = int(_safe_float(densest_sector.get("trend_count", 0)))

    if (
        final_gate.get("can_new_entry")
        and zt_count >= 30
        and breadth_available
        and rise_fall_ratio is not None
        and rise_fall_ratio >= 1.2
        and hs_total >= 15
        and leading_line
    ):
        energy_state = "扩张聚焦"
        state_code = "expand"
        flow_direction = f"能量继续向{leading_line}集中"
        state_reason = "涨停、涨跌比和有势板块数量同步走强，主线具备继续承接能力。"
        reflection_focus = "只盯主线内异常后跌不下去的对象，按竞价表态、开盘承接、回封或60分钟结构确认分层参与，不做支线分流。"
        transition_signal = ""
        transition_reason = ""
        transition_action = ""
    elif (
        dt_count >= 15
        or (breadth_available and rise_fall_ratio is not None and rise_fall_ratio < 0.8)
        or position_level == "一档（空仓档）"
        or final_gate.get("operation_state") == "撤退态"
    ):
        energy_state = "收缩防守"
        state_code = "contract"
        flow_direction = "风险释放优先，先等能量重新回流"
        state_reason = "跌停、涨跌比或仓位限制已经进入收缩区，市场先谈防守，不谈进攻。"
        reflection_focus = "先观察恐慌是否结束，再看哪条线最先恢复承接；当前不给买入资格。"
        transition_signal = ""
        transition_reason = ""
        transition_action = ""
    elif leading_line and secondary_candidates:
        energy_state = "迁移竞争"
        state_code = "migrate"
        flow_direction = f"能量在{leading_line}与{secondary_candidates[0]}之间做选择"
        state_reason = "市场并非全面扩张，而是在主线与竞争线之间重排权重。"
        reflection_focus = f"先看能量最终是否继续回流{leading_line}，胜负未定前只给观察权。"
        secondary_sector_name = secondary_candidates[0] if secondary_candidates else ""
        secondary_trend_item = {}
        for item in sector_trend_snapshot or []:
            if sector_name_matches(item.get("sector", ""), secondary_sector_name):
                secondary_trend_item = item
                break
        secondary_trend_count = int(_safe_float(secondary_trend_item.get("trend_count", 0)))
        upgrade_ready = (
            trend_density >= max(2, secondary_trend_count + 1)
            and resilient_count >= 2
            and failed_count == 0
            and breadth_available
            and rise_fall_ratio is not None
            and rise_fall_ratio >= 1.2
            and dt_count <= 6
        )
        downgrade_risk = (
            failed_count >= max(2, resilient_count)
            or dt_count >= 8
            or (breadth_available and rise_fall_ratio is not None and rise_fall_ratio < 1.0)
            or (secondary_trend_count > trend_density and secondary_trend_count >= 2)
        )
        if upgrade_ready:
            transition_signal = "upgrade_ready"
            transition_reason = "主攻线优势已经拉开，但环境层仍未正式满足；更适合进入条件执行预备态，而不是继续无差别仅观察。"
            transition_action = "默认不开新仓，只为主攻线内最强对象保留条件执行预备态。"
        elif downgrade_risk:
            transition_signal = "downgrade_risk"
            transition_reason = "竞争并没有结束，且主攻线承接出现恶化迹象；若继续走坏，应从迁移竞争降回收缩防守。"
            transition_action = "先收缩观察名单，优先确认是否需要重新回到防守。"
        else:
            transition_signal = "hold_watch"
            transition_reason = "主攻线虽在领先，但胜负还没拉开到足以升级；继续保持高质量观察，不提前放松。"
            transition_action = "先看主攻线与竞争线谁继续胜出，维持观察层减法。"
    else:
        energy_state = "试探修复"
        state_code = "probe"
        flow_direction = f"局部试探{leading_line}" if leading_line else "局部试探，尚未形成统一方向"
        state_reason = "局部异常和热点开始出现，但还没有形成足够稳定的全面扩张。"
        reflection_focus = "重点看异常信号是否继续跌不下去，若没有承接，修复就只是噪音。"
        transition_signal = ""
        transition_reason = ""
        transition_action = ""

    market_performance_evidence = _build_market_performance_evidence(data, leading_line)
    observation_summary = (
        f"上证{sh_change:+.2f}% / 涨停{zt_count} / 跌停{dt_count} / "
        f"涨跌比{breadth_snapshot.get('rise_fall_ratio_text', '暂无')} / 有势板块{high_strong_sector_text}"
    )
    if densest_sector_name:
        flow_direction = f"{flow_direction}；趋势密度最强的是{densest_sector_name}"

    pulse_snapshot = _derive_mainline_pulse_snapshot(
        final_gate=final_gate,
        state_code=state_code,
        leading_line=leading_line,
        trend_density=trend_density,
        resilient_count=resilient_count,
        failed_count=failed_count,
        zt_count=zt_count,
        dt_count=dt_count,
        transition_signal=transition_signal,
    )

    return {
        "state_code": state_code,
        "energy_state": energy_state,
        "flow_direction": flow_direction,
        "state_reason": state_reason,
        "reflection_focus": reflection_focus,
        "observation_summary": observation_summary,
        "market_performance_evidence": market_performance_evidence,
        "leading_line": leading_line,
        "mainline_candidates": mainline_candidates[:3],
        "secondary_candidates": secondary_candidates[:3],
        "zt_count": zt_count,
        "dt_count": dt_count,
        "up_count": up_count,
        "down_count": down_count,
        "breadth_available": breadth_available,
        "rise_fall_ratio": round(rise_fall_ratio, 4) if rise_fall_ratio is not None else None,
        "rise_fall_ratio_text": breadth_snapshot.get("rise_fall_ratio_text", "暂无"),
        "turnover": round(turnover, 2),
        "benchmark_change_pct": _round_or_none(sh_change, 4),
        "high_strong_sector_count": hs_total,
        "high_strong_sector_text": high_strong_sector_text,
        "resilient_abnormal_count": resilient_count,
        "failed_abnormal_count": failed_count,
        "degraded_abnormal_count": len(degraded_abnormal_watch_pool),
        "densest_sector": densest_sector_name,
        "densest_sector_trend_count": trend_density,
        "transition_signal": transition_signal,
        "transition_reason": transition_reason,
        "transition_action": transition_action,
        "driver_type": pulse_snapshot.get("driver_type", ""),
        "pulse_stage": pulse_snapshot.get("pulse_stage", ""),
        "acceptance_quality": pulse_snapshot.get("acceptance_quality", ""),
        "passivation_risk": pulse_snapshot.get("passivation_risk", ""),
        "execution_bias": pulse_snapshot.get("execution_bias", ""),
        "pulse_action_bias": pulse_snapshot.get("pulse_action_bias", ""),
        "pulse_action_reason": pulse_snapshot.get("pulse_action_reason", ""),
        "decision_action": final_gate.get("final_action", "") if final_gate else "",
        "operation_state": final_gate.get("operation_state", "") if final_gate else "",
    }
