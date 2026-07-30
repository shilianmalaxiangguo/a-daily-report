from __future__ import annotations

import datetime as _dt
import os

from market_data.tushare_client import load_local_env_file as _load_runtime_env_file
from market_data.kline_dates import normalize_kline_date_str, parse_kline_date
from domains.calendar_events.request import collect_calendar_events_request_bundle
from domains.market_activity.infer import (
    build_market_activity_quant_signal_bundle,
    build_market_activity_sector_analysis_bundle,
)
from domains.market_activity.request import (
    collect_market_activity_capital_snapshot_request_bundle,
    collect_market_activity_hot_rank_request_bundle,
    collect_market_activity_pool_request_bundle,
    collect_market_activity_sector_snapshot_request_bundle,
    collect_market_activity_stock_quote_request_bundle,
)
from domains.market_state.request import collect_market_state_request_bundle
from domains.monitoring.request import collect_monitoring_request_bundle
from domains.new_stock_calendar.request import (
    collect_new_stock_calendar_request_bundle,
    fetch_sina_new_stock_calendar_pages,
)
from domains.watch_candidates.infer import build_watch_candidate_pool_bundle
from domains.watch_candidates.request import collect_watch_candidate_history_request_bundle
from input.request_diagnostics_runtime import (
    build_request_diagnostics,
    render_request_diagnostics_lines,
)
from input.request_registry import build_input_request_registry, resolve_request_target_date
from input.index_cross_validation import (
    build_report_index_cross_validation,
    index_cross_validation_required,
)
from storage.database_service import DatabaseService
from market_data.xueqiu_hot_stock_service import (
    try_fetch_xueqiu_a_share_hot_24h,
    try_fetch_xueqiu_hot_stock_arguments,
)
from market_data.tushare_turnover_service import fetch_stock_batch_quote_info, fetch_stock_turnover_history
from selection.new_stock_narrative_runtime import build_new_stock_research_pool

__all__ = ["run_input_runtime"]

_MISSING = object()
QUICKTINY_EXCHANGE_MONITOR_URL = "https://stock.quicktiny.cn/api/ladder/exchange-monitor/prediction"
QUICKTINY_EXCHANGE_MONITOR_TOKEN_ENVS = (
    "QUICKTINY_EXCHANGE_MONITOR_TOKEN",
    "QUICKTINY_TOKEN",
)


def _quicktiny_exchange_monitor_token(env=None):
    if env is None:
        _load_runtime_env_file()
    source = os.environ if env is None else env
    for key in QUICKTINY_EXCHANGE_MONITOR_TOKEN_ENVS:
        token = str(source.get(key) or "").strip()
        if not token:
            continue
        if token.lower().startswith("bearer "):
            token = token.split(None, 1)[1].strip()
        if token:
            return token
    return ""


def _quicktiny_exchange_monitor_headers(env=None):
    token = _quicktiny_exchange_monitor_token(env)
    if not token:
        return {}
    return {
        "accept": "application/json, text/plain, */*",
        "authorization": f"Bearer {token}",
        "cookie": f"token={token}",
        "referer": "https://stock.quicktiny.cn/anomaly-center?tab=prediction",
    }


def _fetch_quicktiny_exchange_monitor_payload(*, requests_module=None, env=None, timeout=10):
    if requests_module is None:
        import requests as requests_module

    headers = _quicktiny_exchange_monitor_headers(env)
    response = requests_module.get(
        QUICKTINY_EXCHANGE_MONITOR_URL,
        headers=headers or None,
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(f"exchange monitor status {response.status_code}")
    return response.json()


def _margin_pressure_payload_available(payload):
    rows = (payload or {}).get("rows") if isinstance(payload, dict) else []
    return bool((payload or {}).get("available") and rows)


def _latest_etf_turnover_data_date(payload, target_date=""):
    target_day = parse_kline_date(target_date)
    rows = (payload or {}).get("rows") if isinstance(payload, dict) else []
    dates = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        trade_day = parse_kline_date(row.get("trade_date") or row.get("date"))
        if trade_day is None or (target_day and trade_day > target_day):
            continue
        dates.append(trade_day)
    latest = max(dates, default=None)
    return latest.isoformat() if latest else ""


def _future_etf_turnover_data_dates(payload, target_date=""):
    target_day = parse_kline_date(target_date)
    if target_day is None:
        return []
    rows = (payload or {}).get("rows") if isinstance(payload, dict) else []
    dates = {
        parse_kline_date(row.get("trade_date") or row.get("date"))
        for row in rows or []
        if isinstance(row, dict)
    }
    return sorted(date.isoformat() for date in dates if date and date > target_day)


def _invalid_etf_turnover_data_dates(payload):
    rows = (payload or {}).get("rows") if isinstance(payload, dict) else []
    invalid = []
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            invalid.append(f"第{index + 1}行非结构化")
            continue
        raw_date = row.get("trade_date") or row.get("date")
        if parse_kline_date(raw_date) is None:
            invalid.append(str(raw_date or f"第{index + 1}行缺失"))
    return invalid


def _etf_turnover_coverage_anomaly(payload):
    if not isinstance(payload, dict):
        return False
    if payload.get("coverage_anomaly") is True or str(payload.get("coverage_status") or "").strip() == "partial":
        return True
    return any(
        isinstance(row, dict) and row.get("coverage_anomaly") is True
        for row in (payload.get("rows") or [])
    )


def _fetch_margin_pressure_with_retry(fetcher, target_date):
    if not callable(fetcher):
        return {}
    last_payload = {}
    last_error = None
    for _attempt in range(3):
        try:
            last_payload = fetcher(target_date=target_date, window_days=25, calibration_days=250) or {}
        except Exception as error:
            last_error = error
            continue
        if _margin_pressure_payload_available(last_payload):
            return last_payload
    if last_error is not None and not last_payload:
        raise last_error
    return last_payload


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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


def _refresh_final_report_stock_quotes(results, *, target_date, timer, emit, tencent):
    quote_result = collect_market_activity_stock_quote_request_bundle(
        existing_results=results,
        fetch_stock_batch_info=lambda codes: tencent.get_stock_batch_info(codes),
        fetch_tushare_stock_batch_info=lambda codes: fetch_stock_batch_quote_info(codes, target_date),
        target_date=target_date,
        timer=timer,
        emit=emit,
    )
    results.update(quote_result.get("results", {}))
    return quote_result.get("module_logs", [])


def run_input_runtime(target_date=None, *, helpers=None, config=None):
    bindings = {}
    bindings.update(helpers or {})
    bindings.update(config or {})
    previous = _install_runtime_bindings(bindings)
    try:
        return _run_input_runtime_legacy_body(target_date=target_date)
    finally:
        _restore_runtime_bindings(previous)


def _as_sequence(value):
    if value in (None, ""):
        return []
    if isinstance(value, dict):
        for key in ("items", "data", "rows", "list", "inflow", "outflow"):
            nested = value.get(key)
            if isinstance(nested, (list, tuple, set)):
                return list(nested)
        return [value]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _extract_named_values(value):
    names = []
    for item in _as_sequence(value):
        if isinstance(item, dict):
            for key in (
                "name",
                "sector_name",
                "standard_sector",
                "standard_name",
                "primary_mainline",
                "leading_line",
                "mainline",
            ):
                if item.get(key):
                    names.append(item.get(key))
        elif item:
            names.append(item)
    return [str(name).strip() for name in names if str(name or "").strip()]


def _extend_unique(target, values):
    seen = set(target)
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            target.append(text)


def _derive_new_stock_context(results, fallback_mainline=""):
    results = results or {}
    market_research_snapshot = results.get("market_research_snapshot") or {}
    state_machine = market_research_snapshot.get("state_machine") or {}
    market_state_snapshot = results.get("market_state_snapshot") or {}
    current_mainline_history_record = results.get("current_mainline_history_record") or {}

    mainline_name = (
        current_mainline_history_record.get("primary_mainline")
        or state_machine.get("leading_line")
        or market_state_snapshot.get("leading_line")
        or fallback_mainline
        or ""
    )

    potential_mainlines = []
    _extend_unique(potential_mainlines, _extract_named_values(state_machine.get("mainline_candidates")))
    _extend_unique(
        potential_mainlines,
        [
            current_mainline_history_record.get("leading_line"),
            current_mainline_history_record.get("primary_mainline"),
            state_machine.get("leading_line"),
            market_state_snapshot.get("leading_line"),
            mainline_name,
        ],
    )

    sector_ai_analysis = results.get("sector_ai_analysis") or {}
    _extend_unique(potential_mainlines, _extract_named_values(sector_ai_analysis.get("standard_sectors")))
    _extend_unique(potential_mainlines, _extract_named_values(results.get("hot_plates")))
    _extend_unique(potential_mainlines, _extract_named_values(results.get("sector_change_up")))

    sector_fund_flow = results.get("sector_fund_flow") or {}
    if isinstance(sector_fund_flow, dict):
        inflow_rows = sector_fund_flow.get("inflow") or []
    else:
        inflow_rows = sector_fund_flow
    _extend_unique(potential_mainlines, _extract_named_values(inflow_rows))

    context = {
        "mainline_name": mainline_name,
        "potential_mainlines": potential_mainlines,
        "new_stock_profiles": results.get("new_stock_profiles", {}),
    }

    for key in ("new_stock_money_making_effect", "recent_new_stock_money_making_effect"):
        if key in results:
            context[key] = results.get(key)

    support_names = []
    _extend_unique(support_names, _extract_named_values(results.get("hot_plates")))
    _extend_unique(support_names, _extract_named_values(results.get("sector_change_up")))
    _extend_unique(support_names, _extract_named_values(inflow_rows))
    if support_names:
        context["sector_resonance"] = {
            "supported_sectors": support_names,
            "score": min(10, 7 + len(support_names)),
            "source": "hot_plates/sector_change_up/sector_fund_flow",
        }

    return context


def _run_input_runtime_legacy_body(target_date=None):
    """
    获取指定日期的A股市场数据 - 严格按照SKILL.md声明
    
    Args:
        target_date: 目标日期字符串，格式 "YYYY-MM-DD"
                    如果为None，则获取前一天的数据
    """
    # 初始化计时器
    timer = StepTimer()
    timer.start()
    
    print("🚀 A股日报数据获取入口 - SKILL.md对齐版", flush=True)
    print("=" * 60, flush=True)
    
    # ========== 初始化状态跟踪字典 ==========
    data_status = {}  # 数据获取状态
    step_status = {}  # 执行步骤状态
    module_logs = []
    
    # 确定目标日期并初始化首批请求注册表
    request_registry = build_input_request_registry(globals())
    request_registry["database_service_cls"] = globals().get("DatabaseService", DatabaseService)
    target_date = resolve_request_target_date(target_date)
    
    print("📅 目标日期: {}".format(target_date), flush=True)
    print("=" * 60, flush=True)
    
    # 创建数据收集器
    collector = AShareDataCollector()
    tencent = TencentFinanceData()
    
    print("🔍 开始获取市场数据...", flush=True)
    
    results = {}
    
    try:
        market_state_request_result = collect_market_state_request_bundle(
            target_date,
            request_registry=request_registry,
            index_cross_validator=build_report_index_cross_validation,
            require_index_cross_validation=index_cross_validation_required(target_date),
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_state_request_result.get("results", {}))
        data_status.update(market_state_request_result.get("data_status", {}))
        step_status.update(market_state_request_result.get("step_status", {}))
        module_logs.extend(market_state_request_result.get("module_logs", []))

        def _fetch_market_activity_df():
            import akshare as ak

            return ak.stock_market_activity_legu()

        market_activity_pool_result = collect_market_activity_pool_request_bundle(
            target_date,
            get_limit_up_pool=get_limit_up_pool,
            get_limit_down_pool=get_limit_down_pool,
            fetch_market_activity_df=_fetch_market_activity_df,
            request_registry=request_registry,
            current_date=_dt.datetime.now().strftime("%Y-%m-%d"),
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_pool_result.get("results", {}))
        data_status.update(market_activity_pool_result.get("data_status", {}))
        step_status.update(market_activity_pool_result.get("step_status", {}))
        module_logs.extend(market_activity_pool_result.get("module_logs", []))
        market_activity_pool_artifacts = market_activity_pool_result.get("artifacts", {}) or {}
        limit_up_df = market_activity_pool_artifacts.get("limit_up_df")
        limit_down_df = market_activity_pool_artifacts.get("limit_down_df")

        market_activity_hot_rank_result = collect_market_activity_hot_rank_request_bundle(
            target_date,
            existing_results=results,
            fetch_ths_hot_stock=fetch_ths_hot_stock,
            get_integrated_hot_list=get_integrated_hot_list,
            tencent=tencent,
            request_registry=request_registry,
            xueqiu_hot_rank_fetcher=lambda: try_fetch_xueqiu_a_share_hot_24h(size=100),
            xueqiu_argument_fetcher=try_fetch_xueqiu_hot_stock_arguments,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_hot_rank_result.get("results", {}))
        data_status.update(market_activity_hot_rank_result.get("data_status", {}))
        step_status.update(market_activity_hot_rank_result.get("step_status", {}))
        module_logs.extend(market_activity_hot_rank_result.get("module_logs", []))
        
        current_dates = (
            _dt.datetime.now().strftime("%Y-%m-%d"),
            (_dt.datetime.now() - _dt.timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        market_activity_sector_result = collect_market_activity_sector_snapshot_request_bundle(
            target_date,
            fetch_hot_plate=fetch_hot_plate,
            tencent=tencent,
            get_sector_change_from_iwencai=get_sector_change_from_iwencai,
            get_turnover_rank_from_iwencai=get_turnover_rank_from_iwencai,
            request_registry=request_registry,
            timer=timer,
            emit=lambda message: print(message, flush=True),
            current_dates=current_dates,
        )
        results.update(market_activity_sector_result.get("results", {}))
        data_status.update(market_activity_sector_result.get("data_status", {}))
        step_status.update(market_activity_sector_result.get("step_status", {}))
        module_logs.extend(market_activity_sector_result.get("module_logs", []))
        
        calendar_events_result = collect_calendar_events_request_bundle(
            target_date,
            fetch_calendar_events=tencent.get_calendar_events,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(calendar_events_result.get("results", {}))
        data_status.update(calendar_events_result.get("data_status", {}))
        step_status.update(calendar_events_result.get("step_status", {}))
        module_logs.extend(calendar_events_result.get("module_logs", []))

        new_stock_calendar_result = collect_new_stock_calendar_request_bundle(
            target_date,
            fetch_pages=fetch_sina_new_stock_calendar_pages,
            request_registry=request_registry,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(new_stock_calendar_result.get("results", {}))
        data_status.update(new_stock_calendar_result.get("data_status", {}))
        step_status.update(new_stock_calendar_result.get("step_status", {}))
        module_logs.extend(new_stock_calendar_result.get("module_logs", []))

        try:
            stock_risk_map = request_registry["stock_risk_map"](target_date=target_date)
            results["stock_risk_map"] = stock_risk_map or {}
            data_status["个股风险快照"] = True
            step_status["个股风险快照获取"] = True
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.stock_risk_map",
                    "status": "success",
                    "message": "已获取个股ST/减持/公告/互动问答风险快照",
                    "details": {
                        "provider": "tushare.st+stock_st+stk_holdertrade+anns_d+stk_shock+investor_qa",
                        "target_keys": ["stock_risk_map"],
                        "stock_count": len(stock_risk_map or {}),
                    },
                }
            )
        except Exception as error:
            results["stock_risk_map"] = {}
            data_status["个股风险快照"] = False
            step_status["个股风险快照获取"] = False
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.stock_risk_map",
                    "status": "degraded",
                    "message": "个股ST/减持/公告/互动问答风险快照获取失败",
                    "details": {
                        "provider": "tushare.st+stock_st+stk_holdertrade+anns_d+stk_shock+investor_qa",
                        "target_keys": ["stock_risk_map"],
                        "error": str(error),
                    },
                }
            )

        try:
            new_high_fetcher = request_registry.get("new_high_feedback") if isinstance(request_registry, dict) else None
            if callable(new_high_fetcher):
                new_high_feedback = new_high_fetcher(
                    target_date=target_date,
                    stock_risk_map=results.get("stock_risk_map", {}),
                )
            else:
                new_high_feedback = {}
            results["new_high_feedback"] = new_high_feedback or {}
            data_status["创新高趋势反馈"] = bool((new_high_feedback or {}).get("available"))
            step_status["创新高趋势反馈获取"] = bool((new_high_feedback or {}).get("available"))
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.new_high_feedback",
                    "status": "success" if (new_high_feedback or {}).get("available") else "degraded",
                    "message": "已获取创新高趋势反馈",
                    "details": {
                        "provider": (new_high_feedback or {}).get("source") or "tushare.stk_factor_pro.topdays",
                        "target_keys": ["new_high_feedback"],
                        "new_high_count": (new_high_feedback or {}).get("new_high_count", 0),
                    },
                }
            )
        except Exception as error:
            results["new_high_feedback"] = {}
            data_status["创新高趋势反馈"] = False
            step_status["创新高趋势反馈获取"] = False
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.new_high_feedback",
                    "status": "degraded",
                    "message": "创新高趋势反馈获取失败",
                    "details": {
                        "provider": "tushare.stk_factor_pro.topdays",
                        "target_keys": ["new_high_feedback"],
                        "error": str(error),
                    },
                }
            )

        try:
            top50_series_fetcher = (
                request_registry.get("top50_turnover_share_series") if isinstance(request_registry, dict) else None
            )
            if callable(top50_series_fetcher):
                top50_series = top50_series_fetcher(target_date=target_date, window_days=25, limit=50)
            else:
                top50_series = {}
            results["top50_turnover_share_series"] = top50_series or {}
            top50_rows = (top50_series or {}).get("rows") or []
            data_status["Top50成交额占比趋势"] = bool(top50_rows)
            step_status["Top50成交额占比趋势获取"] = bool(top50_rows)
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.top50_turnover_share_series",
                    "status": "success" if top50_rows else "degraded",
                    "message": "已获取Top50成交额占比趋势",
                    "details": {
                        "provider": (top50_series or {}).get("source") or "storage.turnover_rank_daily",
                        "target_keys": ["top50_turnover_share_series"],
                        "row_count": len(top50_rows),
                    },
                }
            )
        except Exception as error:
            results["top50_turnover_share_series"] = {}
            data_status["Top50成交额占比趋势"] = False
            step_status["Top50成交额占比趋势获取"] = False
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.top50_turnover_share_series",
                    "status": "degraded",
                    "message": "Top50成交额占比趋势获取失败",
                    "details": {
                        "provider": "storage.turnover_rank_daily",
                        "target_keys": ["top50_turnover_share_series"],
                        "error": str(error),
                    },
                }
            )

        try:
            etf_turnover_fetcher = (
                request_registry.get("etf_turnover_series") if isinstance(request_registry, dict) else None
            )
            if callable(etf_turnover_fetcher):
                etf_turnover_series = etf_turnover_fetcher(target_date=target_date, window_days=25)
            else:
                etf_turnover_series = {}
            results["etf_turnover_series"] = etf_turnover_series or {}
            etf_rows = (etf_turnover_series or {}).get("rows") or []
            etf_coverage_anomaly = _etf_turnover_coverage_anomaly(etf_turnover_series)
            etf_latest_data_date = _latest_etf_turnover_data_date(etf_turnover_series, target_date)
            etf_future_data_dates = _future_etf_turnover_data_dates(etf_turnover_series, target_date)
            etf_invalid_data_dates = _invalid_etf_turnover_data_dates(etf_turnover_series)
            target_day = parse_kline_date(target_date)
            target_text = target_day.isoformat() if target_day else ""
            etf_date_matches_target = bool(target_text and etf_latest_data_date == target_text)
            etf_available = (etf_turnover_series or {}).get("available") is True
            etf_is_stale_for_target = bool(
                target_text
                and etf_latest_data_date
                and etf_latest_data_date < target_text
            )
            etf_usable = bool(
                etf_available
                and etf_rows
                and etf_date_matches_target
                and not etf_future_data_dates
                and not etf_invalid_data_dates
                and not etf_coverage_anomaly
            )
            data_status["ETF两市成交额趋势"] = etf_usable
            step_status["ETF两市成交额趋势获取"] = etf_usable
            etf_message = "已获取ETF两市成交额趋势"
            if etf_invalid_data_dates:
                etf_message = f"ETF成交额包含无效事实日期：{etf_invalid_data_dates[-1]}"
            elif etf_future_data_dates:
                etf_message = (
                    f"ETF成交额包含目标日之后事实：目标日 {target_text or target_date}，"
                    f"未来事实日 {etf_future_data_dates[-1]}"
                )
            elif etf_rows and not etf_date_matches_target:
                etf_message = (
                    f"ETF成交额缺少目标日事实：目标日 {target_text or target_date}，"
                    f"最后事实日 {etf_latest_data_date or '缺失'}"
                )
            elif etf_rows and etf_coverage_anomaly:
                etf_message = "ETF两市成交额趋势样本覆盖不足"
            elif not etf_rows:
                etf_message = "ETF两市成交额趋势暂无有效事实"
            elif not etf_available:
                etf_message = "ETF两市成交额趋势不可用"
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.etf_turnover_series",
                    "status": "success" if etf_usable else "degraded",
                    "message": etf_message,
                    "details": {
                        "provider": (etf_turnover_series or {}).get("source") or "sina.etf.daily_amount",
                        "target_keys": ["etf_turnover_series"],
                        "row_count": len(etf_rows),
                        "available": etf_available,
                        "requested_trade_date": target_date,
                        "payload_requested_trade_date": (etf_turnover_series or {}).get("requested_trade_date", ""),
                        "latest_data_date": etf_latest_data_date,
                        "future_data_dates": etf_future_data_dates,
                        "invalid_data_dates": etf_invalid_data_dates,
                        "is_stale_for_target": etf_is_stale_for_target,
                        "usable_etf_count": (etf_turnover_series or {}).get("usable_etf_count", 0),
                        "empty_etf_count": (etf_turnover_series or {}).get("empty_etf_count", 0),
                        "coverage_status": (etf_turnover_series or {}).get("coverage_status", ""),
                        "coverage_ratio": (etf_turnover_series or {}).get("coverage_ratio", ""),
                        "overall_coverage_ratio": (etf_turnover_series or {}).get("overall_coverage_ratio", ""),
                        "coverage_reference_count": (etf_turnover_series or {}).get("coverage_reference_count", 0),
                        "latest_covered_etf_count": (etf_turnover_series or {}).get("latest_covered_etf_count", 0),
                        "total_etf_universe_count": (etf_turnover_series or {}).get("total_etf_universe_count", 0),
                        "coverage_anomaly_reason": (etf_turnover_series or {}).get("coverage_anomaly_reason", ""),
                    },
                }
            )
        except Exception as error:
            results["etf_turnover_series"] = {}
            data_status["ETF两市成交额趋势"] = False
            step_status["ETF两市成交额趋势获取"] = False
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.etf_turnover_series",
                    "status": "degraded",
                    "message": "ETF两市成交额趋势获取失败",
                    "details": {
                        "provider": "sina.etf.daily_amount",
                        "target_keys": ["etf_turnover_series"],
                        "error": str(error),
                    },
                }
            )

        try:
            price_band_fetcher = (
                request_registry.get("price_band_style_series") if isinstance(request_registry, dict) else None
            )
            if callable(price_band_fetcher):
                price_band_series = price_band_fetcher(target_date=target_date, window_days=25)
            else:
                price_band_series = {}
            results["price_band_style_series"] = price_band_series or {}
            price_band_rows = (price_band_series or {}).get("rows") or []
            data_status["价格带风格趋势"] = bool(price_band_rows)
            step_status["价格带风格趋势获取"] = bool(price_band_rows)
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.price_band_style_series",
                    "status": "success" if price_band_rows else "degraded",
                    "message": "已获取价格带风格趋势",
                    "details": {
                        "provider": (price_band_series or {}).get("source") or "tushare.ths_daily.price_band_style",
                        "target_keys": ["price_band_style_series"],
                        "row_count": len(price_band_rows),
                    },
                }
            )
        except Exception as error:
            results["price_band_style_series"] = {}
            data_status["价格带风格趋势"] = False
            step_status["价格带风格趋势获取"] = False
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.price_band_style_series",
                    "status": "degraded",
                    "message": "价格带风格趋势获取失败",
                    "details": {
                        "provider": "tushare.ths_daily.price_band_style",
                        "target_keys": ["price_band_style_series"],
                        "error": str(error),
                    },
                }
            )

        try:
            margin_pressure_fetcher = (
                request_registry.get("margin_pressure") if isinstance(request_registry, dict) else None
            )
            margin_pressure = _fetch_margin_pressure_with_retry(margin_pressure_fetcher, target_date)
            results["margin_pressure"] = margin_pressure or {}
            margin_rows = (margin_pressure or {}).get("rows") or []
            data_status["融资承接压力"] = bool((margin_pressure or {}).get("available") and margin_rows)
            step_status["融资承接压力获取"] = bool((margin_pressure or {}).get("available") and margin_rows)
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.margin_pressure",
                    "status": "success" if (margin_pressure or {}).get("available") and margin_rows else "degraded",
                    "message": "已获取融资承接压力",
                    "details": {
                        "provider": (margin_pressure or {}).get("source") or "tushare.margin+tushare.index_daily.market_amount",
                        "target_keys": ["margin_pressure"],
                        "row_count": len(margin_rows),
                        "latest_pressure_label": (margin_pressure or {}).get("latest_pressure_label", ""),
                    },
                }
            )
        except Exception as error:
            results["margin_pressure"] = {}
            data_status["融资承接压力"] = False
            step_status["融资承接压力获取"] = False
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.margin_pressure",
                    "status": "degraded",
                    "message": "融资承接压力获取失败",
                    "details": {
                        "provider": "tushare.margin+tushare.index_daily.market_amount",
                        "target_keys": ["margin_pressure"],
                        "error": str(error),
                    },
                }
            )

        try:
            new_stock_research_result = build_new_stock_research_pool(
                results.get("new_stock_calendar", []),
                target_date=target_date,
                context=_derive_new_stock_context(results),
            )
            results.update(new_stock_research_result or {})
        except Exception as error:
            results["new_stock_research_pool"] = []
            results["new_stock_candidate_upgrades"] = []
            module_logs.append(
                {
                    "module": "selection.new_stock_narrative_runtime",
                    "step": "request.new_stock_scoring",
                    "status": "error",
                    "message": "新股研究池评分失败",
                    "details": {
                        "target_keys": [
                            "new_stock_research_pool",
                            "new_stock_candidate_upgrades",
                        ],
                        "error": str(error),
                    },
                }
            )

        monitoring_result = collect_monitoring_request_bundle(
            target_date,
            analyzer_factory=XuangubaoIntradayAnalyzer,
            fetch_wanzhu_top10=collector.get_wanzhu_top10,
            fetch_exchange_monitor_payload=_fetch_quicktiny_exchange_monitor_payload,
            fetch_stock_batch_info=lambda codes: TencentFinanceData().get_stock_batch_info(codes),
            fetch_tushare_stock_batch_info=lambda codes: fetch_stock_batch_quote_info(codes, target_date),
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(monitoring_result.get("results", {}))
        data_status.update(monitoring_result.get("data_status", {}))
        step_status.update(monitoring_result.get("step_status", {}))
        module_logs.extend(monitoring_result.get("module_logs", []))

        def _fetch_lhb_rows(request_target_date):
            from finshare import get_lhb

            lhb_date = str(request_target_date or "").replace("-", "")
            lhb_df = get_lhb(start_date=lhb_date, end_date=lhb_date)
            if lhb_df is None or len(lhb_df) == 0:
                return []
            return lhb_df.to_dict("records")

        market_activity_capital_result = collect_market_activity_capital_snapshot_request_bundle(
            target_date,
            limit_up_df=limit_up_df,
            existing_results=results,
            fetch_lhb_rows=_fetch_lhb_rows,
            request_registry=request_registry,
            limit_up_provider=market_activity_pool_artifacts.get("limit_up_provider"),
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_capital_result.get("results", {}))
        data_status.update(market_activity_capital_result.get("data_status", {}))
        step_status.update(market_activity_capital_result.get("step_status", {}))
        module_logs.extend(market_activity_capital_result.get("module_logs", []))

        # 原始代码（暂时注释）
        '''
        try:
            import finshare as fs
            import requests

            # 获取龙虎榜数据
            lhb_date = target_date.replace('-', '')
            print(f"   📅 调用finshare.get_lhb({lhb_date})...")
            sys.stdout.flush()
            df = fs.get_lhb(lhb_date, lhb_date)
            print(f"   ✅ 龙虎榜数据获取完成: {len(df)}条")
            sys.stdout.flush()

            if df.empty:
                results['lhb_net_buy_top10'] = []
                results['lhb_net_sell_top10'] = []
                print("   ⚠️ 龙虎榜数据为空", flush=True)
            else:
                print(f"   📊 开始排序龙虎榜数据...")
                # 净买入前10
                df_sorted_buy = df.sort_values('net_buy_amount', ascending=False)
                top10_buy = df_sorted_buy.head(10)
                print(f"   ✅ 净买入前10筛选完成")

                # 净流出前10（净买入为负的，取绝对值最大的10个）
                df_sorted_sell = df.sort_values('net_buy_amount', ascending=True)
                top10_sell = df_sorted_sell.head(10)
                print(f"   ✅ 净流出前10筛选完成")

                # 提取所有股票代码
                print(f"   📝 提取股票代码...")
                buy_codes = [str(row['fs_code']).replace('.SZ', '').replace('.SH', '') for _, row in top10_buy.iterrows()]
                sell_codes = [str(row['fs_code']).replace('.SZ', '').replace('.SH', '') for _, row in top10_sell.iterrows()]
                all_codes = list(set(buy_codes + sell_codes))
                print(f"   ✅ 提取完成: {len(all_codes)} 只股票")

                # 批量获取股票信息（名称、涨跌幅、涨停状态）
                print(f"   📡 腾讯API批量查询 {len(all_codes)} 只股票...")
                codes_with_market = []
                for code in all_codes:
                    if code.startswith('6'):
                        codes_with_market.append(f'sh{code}')
                    else:
                        codes_with_market.append(f'sz{code}')

                # 腾讯API批量查询
                url = f"http://qt.gtimg.cn/q={','.join(codes_with_market)}"
                response = requests.get(url, timeout=10)
                response.encoding = 'gbk'
                lines = response.text.strip().split('\n')
                print(f"   ✅ 腾讯API返回 {len(lines)} 行数据")

                stock_info = {}
                for line in lines:
                    if not line.startswith('v_'):
                        continue
                    parts = line.split('~')
                    if len(parts) < 35:
                        continue

                    code = parts[2]
                    name = parts[1]
                    change_pct = float(parts[32])
                    zt_status = '涨停' if change_pct >= 9.9 else ('跌停' if change_pct <= -9.9 else '正常')

                    stock_info[code] = {
                        'name': name,
                        'change_pct': round(change_pct, 2),
                        'zt_status': zt_status
                    }

                # 构建净买入前10
                print(f"   📊 构建龙虎榜净买入前10...")
                lhb_net_buy = []
                for rank, (_, row) in enumerate(top10_buy.iterrows(), 1):
                    stock_code = str(row['fs_code']).replace('.SZ', '').replace('.SH', '')
                    info = stock_info.get(stock_code, {})
                    stock_name = info.get('name', '')

                    # 使用get_stock_sector获取板块（跳过API调用，避免批量处理卡死）
                    sector = get_stock_sector(
                        stock_name,
                        stock_code,
                        hot_rank_data=results.get('hot_rank_top30'),
                        zt_pool_data=results.get('zt_pool_by_sector'),
                        zt_pool_raw=results.get('zt_pool'),
                        dt_pool_raw=results.get('dt_pool'),
                        lianban_data=results.get('lianban_data'),
                        lhb_data=None,  # 避免循环
                        sector_fund_flow=results.get('sector_fund_flow'),
                        skip_api_call=True  # 跳过东方财富API调用
                    )
                    print(f"      {rank}. {stock_name}({stock_code}) - 板块: {sector}")

                    item = {
                        'rank': rank,
                        'code': stock_code,
                        'net_buy_amount_yi': row['net_buy_amount'] / 100000000,
                        'name': stock_name,
                        'change_pct': info.get('change_pct', 0),
                        'zt_status': info.get('zt_status', '正常'),
                        'sector': sector
                    }
                    lhb_net_buy.append(item)

                # 构建净流出前10
                print(f"   📊 构建龙虎榜净流出前10...")
                lhb_net_sell = []
                for rank, (_, row) in enumerate(top10_sell.iterrows(), 1):
                    stock_code = str(row['fs_code']).replace('.SZ', '').replace('.SH', '')
                    info = stock_info.get(stock_code, {})
                    stock_name = info.get('name', '')

                    # 使用get_stock_sector获取板块（跳过API调用，避免批量处理卡死）
                    sector = get_stock_sector(
                        stock_name,
                        stock_code,
                        hot_rank_data=results.get('hot_rank_top30'),
                        zt_pool_data=results.get('zt_pool_by_sector'),
                        zt_pool_raw=results.get('zt_pool'),
                        dt_pool_raw=results.get('dt_pool'),
                        lianban_data=results.get('lianban_data'),
                        lhb_data=None,  # 避免循环
                        sector_fund_flow=results.get('sector_fund_flow'),
                        skip_api_call=True  # 跳过东方财富API调用
                    )
                    print(f"      {rank}. {stock_name}({stock_code}) - 板块: {sector}")

                    item = {
                        'rank': rank,
                        'code': stock_code,
                        'net_sell_amount_yi': abs(row['net_buy_amount']) / 100000000,
                        'name': stock_name,
                        'change_pct': info.get('change_pct', 0),
                        'zt_status': info.get('zt_status', '正常'),
                        'sector': sector
                    }
                    lhb_net_sell.append(item)

                results['lhb_net_buy_top10'] = lhb_net_buy
                results['lhb_net_sell_top10'] = lhb_net_sell
                elapsed, cum = timer.record("龙虎榜数据获取", 13)
                print(f"   ✅ 龙虎榜净买入前十: {len(lhb_net_buy)} 只")
                print(f"   ✅ 龙虎榜净流出前十: {len(lhb_net_sell)} 只 [⏱ {elapsed:.2f}s]")
        except Exception as e:
            elapsed, cum = timer.record("龙虎榜数据获取(失败)", 13)
            print(f"   ⚠️ 龙虎榜失败: {e} [⏱ {elapsed:.2f}s]")
            import traceback
            traceback.print_exc()
            results['lhb_net_buy_top10'] = []
            results['lhb_net_sell_top10'] = []
        '''
        market_activity_quote_result = collect_market_activity_stock_quote_request_bundle(
            existing_results=results,
            fetch_stock_batch_info=lambda codes: TencentFinanceData().get_stock_batch_info(codes),
            fetch_tushare_stock_batch_info=lambda codes: fetch_stock_batch_quote_info(codes, target_date),
            target_date=target_date,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_quote_result.get("results", {}))
        module_logs.extend(market_activity_quote_result.get("module_logs", []))

        print("\n🎉 所有数据获取完成!", flush=True)
        
        # ========== 全局板块AI分析 ==========
        print("\n🧠 进行全局板块AI分析...", flush=True)
        market_activity_sector_analysis_result = build_market_activity_sector_analysis_bundle(
            results,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_sector_analysis_result.get("results", {}))
        module_logs.extend(market_activity_sector_analysis_result.get("module_logs", []))
        
        # ========== 15. AI多维量化分析（升级版）==========
        print("\n🔬 进行AI多维量化分析... (依赖: 步骤4, 步骤7, 步骤9, 步骤13)", flush=True)

        watch_candidate_result = build_watch_candidate_pool_bundle(
            results,
            emit=lambda message: print(message, flush=True),
        )
        results.update(watch_candidate_result.get("results", {}))
        module_logs.extend(watch_candidate_result.get("module_logs", []))

        def _fetch_quicktiny_history(*, full_code, code, target_date, days=30):
            import requests

            url = f"https://stock.quicktiny.cn/api/tushare/merged-kline/{full_code}?days={days}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("success") or not payload.get("data"):
                return []

            amounts = []
            target_date_compact = str(target_date or "").replace("-", "")
            for item in payload.get("data", []):
                bar_date = item.get("date", "")
                if bar_date and bar_date <= target_date_compact:
                    amount = item.get("amount") or 0
                    if amount:
                        amounts.append(float(amount) / 1e8)
            return amounts

        def _baostock_source_factory():
            from finshare.sources.baostock_source import BaoStockDataSource

            return BaoStockDataSource()

        watch_candidate_history_result = collect_watch_candidate_history_request_bundle(
            target_date,
            candidates=results.get("candidates", []),
            stock_full_info=results.get("stock_full_info", {}),
            get_cache=get_cache,
            fetch_tushare_turnover_history=fetch_stock_turnover_history,
            fetch_quicktiny_history=_fetch_quicktiny_history,
            baostock_source_factory=_baostock_source_factory,
            timer=timer,
            emit=lambda message: print(message, flush=True),
            enable_live_quicktiny=False,
            enable_baostock_fallback=False,
        )
        results.update(watch_candidate_history_result.get("results", {}))
        module_logs.extend(watch_candidate_history_result.get("module_logs", []))

        market_activity_quant_result = build_market_activity_quant_signal_bundle(
            results,
            analyze_volume_anomaly=analyze_volume_anomaly,
            analyze_lhb=analyze_lhb,
            calculate_resonance=calculate_resonance,
            generate_trade_signals=generate_trade_signals,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(market_activity_quant_result.get("results", {}))
        module_logs.extend(market_activity_quant_result.get("module_logs", []))

        print("   ✅ AI多维量化分析完成!", flush=True)
        
        # ========== 数据摘要 ==========
        print("\n" + "=" * 60)
        print("📊 数据摘要", flush=True)
        print("=" * 60)
        print(f"💰 两市总成交额: {results['total_turnover']:.2f}亿元")
        
        if results.get('indices'):
            print("📈 主要指数:", flush=True)
            for name, data in results['indices'].items():
                price = data.get('点位', data.get('price', 0))
                change_pct = data.get('涨跌幅', data.get('change_pct', 0))
                print(f"  {name}: {price:.2f}点 ({change_pct:+.2f}%)")
        
        if results.get('wind_a_alternative'):
            wa = results['wind_a_alternative']
            print(f"🌐 中证全指(Wind全A平替): {wa.get('点位', wa.get('price', 0)):.2f}点 ({wa.get('涨跌幅', wa.get('change_pct', 0)):+.2f}%)")
        if results.get('csi500_index') and _safe_float(results['csi500_index'].get('点位', results['csi500_index'].get('price', 0))) > 0:
            csi500 = results['csi500_index']
            print(f"🌐 中证500: {csi500.get('点位', csi500.get('price', 0)):.2f}点 ({csi500.get('涨跌幅', csi500.get('change_pct', 0)):+.2f}%)")
        if results.get('csi1000_index') and _safe_float(results['csi1000_index'].get('点位', results['csi1000_index'].get('price', 0))) > 0:
            csi1000 = results['csi1000_index']
            print(f"🌐 中证1000: {csi1000.get('点位', csi1000.get('price', 0)):.2f}点 ({csi1000.get('涨跌幅', csi1000.get('change_pct', 0)):+.2f}%)")
        
        if results.get('hot_rank_top30'):
            print(f"🔥 热度前50: {len(results['hot_rank_top30'])} 只")
        
        if results.get('hot_plates'):
            print(f"📊 板块热榜: {len(results['hot_plates'])} 条")
        
        if results.get('zt_pool'):
            print(f"📈 涨停池: {len(results['zt_pool'])} 只")
        
        if results.get('dt_pool'):
            print(f"📉 跌停池: {len(results['dt_pool'])} 只")
        
        if results.get('sector_fund_flow'):
            print(f"💹 行业资金流向: {len(results['sector_fund_flow'])} 条")
        
        if results.get('sector_change_up'):
            print(f"📊 涨幅前10板块: {len(results['sector_change_up'])} 条")
        
        if results.get('sector_change_down'):
            print(f"📊 跌幅前10板块: {len(results['sector_change_down'])} 条")
        
        if results.get('turnover_rank'):
            print(f"💵 成交额排名: {len(results['turnover_rank'])} 条")
        
        if results.get('calendar_events'):
            print(f"📅 预期日历: {len(results['calendar_events'])} 条")
        
        if results.get('xuangubao_data'):
            xgb_news_count = len(results['xuangubao_data'].get('xuangubao_news', []) or [])
            xgb_plate_count = len(results['xuangubao_data'].get('xuangubao_plates', []) or [])
            xgb_limit_up_reason_count = len(results['xuangubao_data'].get('xuangubao_limit_up_reasons', []) or [])
            if xgb_news_count or xgb_plate_count or xgb_limit_up_reason_count:
                print(f"📡 选股通异动: 新闻{xgb_news_count}条，盘面{xgb_plate_count}个，涨停解释{xgb_limit_up_reason_count}条")
        
        if results.get('wanzhu_top10'):
            print(f"🏆 顽主杯前十: {len(results['wanzhu_top10'])} 只")
        
        if results.get('lhb_net_buy_top10'):
            print(f"🐉 龙虎榜净买入前十: {len(results['lhb_net_buy_top10'])} 只")
        
        # ========== 18. 板块四象限数据（击球区分析）==========
        step_status['板块四象限数据获取'] = False
        print("  1️⃣5️⃣ 获取板块四象限数据（击球区分析）...", flush=True)
        try:
            quadrant_data = get_sector_quadrant_data(period=20, strength_period=3)
            if quadrant_data:
                results['sector_quadrant'] = quadrant_data
                hs_analysis = quadrant_data['high_strong_analysis']
                print(f"   ✅ 板块四象限数据获取成功")
                print(f"   📊 高强区间: {hs_analysis['total']}个板块")
                print(f"      🏆 最佳击球区（≥80分）: {hs_analysis['tier1_count']}个")
                print(f"      ⭐ 优质击球区（60-79分）: {hs_analysis['tier2_count']}个")
                print(f"      ✓ 普通击球区（40-59分）: {hs_analysis['tier3_count']}个")
                print(f"      ⚠️ 边缘击球区（<40分）: {hs_analysis['tier4_count']}个")
                step_status['板块四象限数据获取'] = True
                data_status['板块四象限'] = True
                module_logs.append(
                    {
                        "module": "input.runtime",
                        "step": "request.sector_quadrant",
                        "status": "success",
                        "message": "已获取板块四象限击球区数据",
                        "details": {
                            "provider": quadrant_data.get("provider") or "quicktiny.sector_analysis_quadrant",
                            "target_keys": ["sector_quadrant"],
                            "high_strong_count": hs_analysis.get("total", 0),
                            "tier1_count": hs_analysis.get("tier1_count", 0),
                        },
                    }
                )
            else:
                print(f"   ⚠️ 板块四象限数据获取失败")
                data_status['板块四象限'] = False
                module_logs.append(
                    {
                        "module": "input.runtime",
                        "step": "request.sector_quadrant",
                        "status": "degraded",
                        "message": "板块四象限击球区数据为空",
                        "details": {
                            "provider": "quicktiny.sector_analysis_quadrant",
                            "target_keys": ["sector_quadrant"],
                        },
                    }
                )
        except Exception as e:
            print(f"   ⚠️ 板块四象限数据获取异常: {e}")
            data_status['板块四象限'] = False
            module_logs.append(
                {
                    "module": "input.runtime",
                    "step": "request.sector_quadrant",
                    "status": "error",
                    "message": "板块四象限击球区请求失败",
                    "details": {
                        "provider": "quicktiny.sector_analysis_quadrant",
                        "target_keys": ["sector_quadrant"],
                        "error": str(e),
                    },
                }
            )

        final_quote_logs = _refresh_final_report_stock_quotes(
            results,
            target_date=target_date,
            timer=timer,
            tencent=tencent,
            emit=lambda message: print(message, flush=True),
        )
        module_logs.extend(final_quote_logs)
        
        # ========== 添加状态跟踪字典到结果 ==========
        results['data_status'] = data_status
        results['step_status'] = step_status
        request_diagnostics = build_request_diagnostics(module_logs, data_status=data_status, step_status=step_status)
        results["request_diagnostics"] = request_diagnostics

        for line in render_request_diagnostics_lines(request_diagnostics):
            print(line, flush=True)
        
        # 打印状态统计
        print("\n" + "=" * 60)
        print("📊 数据获取状态统计", flush=True)
        print("=" * 60)
        success_count = sum(1 for v in data_status.values() if v)
        total_count = len(data_status)
        print(f"数据源获取成功: {success_count}/{total_count}")
        for key, value in data_status.items():
            status_icon = "✅" if value else "❌"
            print(f"  {status_icon} {key}")
        
        print("\n" + "=" * 60)
        print("📋 执行步骤状态统计", flush=True)
        print("=" * 60)
        step_success_count = sum(1 for v in step_status.values() if v)
        step_total_count = len(step_status)
        print(f"步骤执行成功: {step_success_count}/{step_total_count}")
        for key, value in step_status.items():
            status_icon = "✅" if value else "❌"
            print(f"  {status_icon} {key}")
        
        # 打印计时摘要
        timer.print_summary()
        
        # 打印LLM调用统计
        llm_stats = get_llm_call_stats()
        if llm_stats['total_calls'] > 0:
            print("\n" + "=" * 80)
            print("LLM调用统计", flush=True)
            print("-" * 80)
            print(f"{'类型':<30} {'调用次数':>10} {'总耗时':>12} {'平均耗时':>12}")
            print("-" * 80)
            if llm_stats['event_analysis_calls'] > 0:
                avg_time = llm_stats['event_analysis_time'] / llm_stats['event_analysis_calls']
                print(f"{'事件板块分析':<30} {llm_stats['event_analysis_calls']:>10} {llm_stats['event_analysis_time']:>11.2f}s {avg_time:>11.2f}s")
            if llm_stats['sector_analysis_calls'] > 0:
                avg_time = llm_stats['sector_analysis_time'] / llm_stats['sector_analysis_calls']
                print(f"{'板块关系分析':<30} {llm_stats['sector_analysis_calls']:>10} {llm_stats['sector_analysis_time']:>11.2f}s {avg_time:>11.2f}s")
            print("-" * 80)
            avg_total = llm_stats['total_time'] / llm_stats['total_calls']
            print(f"{'总计':<30} {llm_stats['total_calls']:>10} {llm_stats['total_time']:>11.2f}s {avg_total:>11.2f}s")
            print("=" * 80)
        
        # 将计时数据保存到results中供报告使用
        results['timer_summary'] = timer.get_summary()
        results['llm_stats'] = llm_stats
        
        # 将状态跟踪数据保存到results中供报告使用
        results['data_status'] = data_status
        results['step_status'] = step_status
        results['module_logs'] = module_logs
        results["request_diagnostics"] = request_diagnostics
        
        return results
        
    except Exception as e:
        print(f"\n❌ 数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        results["request_diagnostics"] = build_request_diagnostics(module_logs, data_status=data_status, step_status=step_status)
        return results
