import re
from pathlib import Path


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.market_state.request",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _provider_from_payload(payload, default_provider):
    sources = []
    items = payload if isinstance(payload, list) else [payload]
    for item in items or []:
        if not isinstance(item, dict):
            continue
        source = item.get("data_source")
        if source:
            sources.append(source)
    unique_sources = sorted(set(sources))
    if not unique_sources:
        return default_provider
    if len(unique_sources) == 1:
        return unique_sources[0]
    return ",".join(unique_sources)


def _provider_from_value(value, default_provider):
    source = getattr(value, "data_source", "")
    return source or default_provider


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_date_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def _coerce_named_index_payload(payload, target_date, *, name, code, data_source=""):
    if not isinstance(payload, dict):
        return {}
    source_date = _normalize_date_text(payload.get("trade_date") or payload.get("date") or target_date)
    target = _normalize_date_text(target_date)
    price = _safe_float(payload.get("price", payload.get("点位", payload.get("close"))))
    if price <= 0 or (target and source_date and source_date != target):
        return {}
    result = {
        "name": name,
        "code": str(payload.get("code") or code),
        "price": price,
        "change_pct": _safe_float(payload.get("change_pct", payload.get("涨跌幅"))),
        "trade_date": source_date or target,
        "data_source": data_source or str(payload.get("data_source") or payload.get("source") or ""),
    }
    if payload.get("source"):
        result["source"] = payload.get("source")
    return result


def _coerce_csi1000_payload(payload, target_date, *, data_source=""):
    return _coerce_named_index_payload(
        payload,
        target_date,
        name="中证1000",
        code="000852",
        data_source=data_source,
    )


def _load_csi1000_from_fact_registry(request_registry, target_date):
    fetcher = (request_registry or {}).get("csi1000_fact")
    if not callable(fetcher):
        return {}
    try:
        return _coerce_csi1000_payload(fetcher(target_date=target_date), target_date)
    except Exception:
        return {}


def _load_csi1000_from_database(target_date):
    try:
        from storage.database_service import DatabaseService

        service = DatabaseService.from_environment()
        if not service.is_postgres_backed():
            return {}
        rows = service.query_index_daily_bars("sh000852", target_date, window_days=5) or []
    except Exception:
        return {}
    for row in reversed(rows):
        payload = _coerce_csi1000_payload(row, target_date, data_source="postgresql.index_daily_bars")
        if payload:
            return payload
    return {}


_CSI1000_SUCCESS_LOG_RE = re.compile(
    r"✅\s*中证1000:\s*(?P<price>[0-9]+(?:\.[0-9]+)?)点\s*\((?P<change>[+-]?[0-9]+(?:\.[0-9]+)?)%\)"
)


def _load_csi1000_from_same_day_run_log(target_date):
    target = _normalize_date_text(target_date)
    if not target:
        return {}
    logs_dir = Path(__file__).resolve().parents[3] / "logs" / "runs"
    if not logs_dir.exists():
        return {}
    try:
        paths = sorted(logs_dir.glob(f"*__{target}.log"), reverse=True)
    except OSError:
        return {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if f"日报关键数据检查: 成功 / {target}" not in text:
            continue
        match = _CSI1000_SUCCESS_LOG_RE.search(text)
        if not match:
            continue
        payload = _coerce_csi1000_payload(
            {
                "price": match.group("price"),
                "change_pct": match.group("change"),
                "trade_date": target,
                "data_source": "run_log.csi1000_same_day_success",
                "source": str(path),
            },
            target,
        )
        if payload:
            return payload
    return {}


def _resolve_csi1000_fallback(request_registry, target_date):
    for loader in (
        lambda: _load_csi1000_from_fact_registry(request_registry, target_date),
        lambda: _load_csi1000_from_database(target_date),
        lambda: _load_csi1000_from_same_day_run_log(target_date),
    ):
        payload = loader()
        if payload:
            return payload
    return {}


def _collect_optional_index_request(
    *,
    request_registry,
    request_key,
    result_key,
    label,
    step_key,
    target_date,
    timer,
    emit,
    module_logs,
    data_status,
    step_status,
    timer_order,
    fallback_loader=None,
):
    step_status[f"{label}获取"] = False
    emit(f"  {timer_order}️⃣ 获取{label}（Tushare 优先）...")
    try:
        payload = request_registry[request_key](target_date=target_date)
        results_payload = payload if isinstance(payload, dict) else {}
        price = _safe_float(results_payload.get("price", results_payload.get("点位", 0)))
        change = _safe_float(results_payload.get("change_pct", results_payload.get("涨跌幅", 0)))
        if price <= 0 and callable(fallback_loader):
            fallback_payload = fallback_loader(request_registry, target_date)
            if fallback_payload:
                results_payload = fallback_payload
                price = _safe_float(results_payload.get("price", results_payload.get("点位", 0)))
                change = _safe_float(results_payload.get("change_pct", results_payload.get("涨跌幅", 0)))

        if price > 0:
            data_status[label] = True
            step_status[f"{label}获取"] = True
            elapsed, _ = timer.record(f"{label}获取", str(timer_order))
            emit(f"   ✅ {label}: {price:.2f}点 ({change:+.2f}%) [⏱ {elapsed:.2f}s]")
            _append_log(
                module_logs,
                step_key,
                "success",
                f"已获取{label}",
                provider=_provider_from_payload(results_payload, "tushare-first"),
                target_keys=[result_key],
                price=price,
                change_pct=change,
            )
        else:
            data_status[label] = False
            elapsed, _ = timer.record(f"{label}获取(失败)", str(timer_order))
            emit(f"   ❌ {label}获取失败 [⏱ {elapsed:.2f}s]")
            _append_log(
                module_logs,
                step_key,
                "degraded",
                f"{label}为空或无效",
                provider="tushare-first",
                target_keys=[result_key],
            )
        return results_payload
    except Exception as error:
        data_status[label] = False
        elapsed, _ = timer.record(f"{label}获取(失败)", str(timer_order))
        emit(f"   ❌ {label}获取异常: {error} [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            step_key,
            "error",
            f"{label}请求失败",
            provider="tushare-first",
            target_keys=[result_key],
            error=str(error),
        )
        return {"price": 0, "change_pct": 0}


def collect_market_state_request_bundle(
    target_date,
    *,
    request_registry,
    index_cross_validator=None,
    require_index_cross_validation,
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {}
    module_logs = []

    step_status["两市成交额获取"] = False
    emit("  1️⃣ 获取两市成交额（Tushare 优先）...")
    try:
        total_turnover_float = request_registry["total_turnover"](target_date=target_date)
        results["total_turnover"] = total_turnover_float
        results["turnover_data"] = {
            "total_turnover_yi": total_turnover_float,
            "date": target_date,
        }
        if total_turnover_float > 0:
            data_status["两市成交额"] = True
            step_status["两市成交额获取"] = True
            elapsed, _ = timer.record("两市成交额获取", 1)
            emit("   ✅ 成交额获取完成: {:.2f}亿元 [⏱ {:.2f}s]".format(total_turnover_float, elapsed))
            _append_log(
                module_logs,
                "request.total_turnover",
                "success",
                "已获取两市成交额",
                provider=_provider_from_value(total_turnover_float, "tushare-first"),
                target_keys=["total_turnover", "turnover_data"],
                total_turnover=total_turnover_float,
                row_count=getattr(total_turnover_float, "source_row_count", None),
                retry_count=getattr(total_turnover_float, "source_retry_count", None),
            )
        else:
            data_status["两市成交额"] = False
            elapsed, _ = timer.record("两市成交额获取(失败)", 1)
            emit("   ❌ 成交额获取失败 [⏱ {:.2f}s]".format(elapsed))
            _append_log(
                module_logs,
                "request.total_turnover",
                "degraded",
                "两市成交额为空或无效",
                provider="tushare-first",
                target_keys=["total_turnover", "turnover_data"],
            )
    except Exception as error:
        data_status["两市成交额"] = False
        elapsed, _ = timer.record("两市成交额获取(失败)", 1)
        emit(f"   ❌ 成交额获取异常: {error} [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.total_turnover",
            "error",
            "两市成交额请求失败",
            provider="tushare-first",
            target_keys=["total_turnover", "turnover_data"],
            error=str(error),
        )

    step_status["主要指数获取"] = False
    emit("  2️⃣ 获取三大指数（Tushare 优先）...")
    try:
        indices = request_registry["major_indices"](target_date=target_date)
        results["indices"] = indices
        if indices and len(indices) > 0:
            data_status["主要指数"] = True
            step_status["主要指数获取"] = True
            elapsed, _ = timer.record("主要指数获取", 2)
            emit(f"   ✅ 获取到 {len(indices)} 个指数数据 [⏱ {elapsed:.2f}s]")
            _append_log(
                module_logs,
                "request.major_indices",
                "success",
                "已获取主要指数",
                provider=_provider_from_payload(indices, "tushare-first"),
                target_keys=["indices"],
                index_count=len(indices),
            )
        else:
            data_status["主要指数"] = False
            elapsed, _ = timer.record("主要指数获取(失败)", 2)
            emit(f"   ❌ 主要指数获取失败 [⏱ {elapsed:.2f}s]")
            _append_log(
                module_logs,
                "request.major_indices",
                "degraded",
                "主要指数为空或无效",
                provider="tushare-first",
                target_keys=["indices"],
            )
    except Exception as error:
        data_status["主要指数"] = False
        elapsed, _ = timer.record("主要指数获取(失败)", 2)
        emit(f"   ❌ 主要指数获取异常: {error} [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.major_indices",
            "error",
            "主要指数请求失败",
            provider="tushare-first",
            target_keys=["indices"],
            error=str(error),
        )

    step_status["中证全指获取"] = False
    emit("  3️⃣ 获取中证全指（Tushare 优先）...")
    try:
        wind_a_alt = request_registry["wind_a"](target_date=target_date)
        results["wind_a_alternative"] = wind_a_alt
        wind_a_price = wind_a_alt.get("price", wind_a_alt.get("点位", 0))
        wind_a_change = wind_a_alt.get("change_pct", wind_a_alt.get("涨跌幅", 0))
        if wind_a_price > 0:
            data_status["中证全指"] = True
            step_status["中证全指获取"] = True
            elapsed, _ = timer.record("中证全指获取", 3)
            emit(f"   ✅ 中证全指: {wind_a_price:.2f}点 ({wind_a_change:+.2f}%) [⏱ {elapsed:.2f}s]")
            _append_log(
                module_logs,
                "request.wind_a",
                "success",
                "已获取中证全指",
                provider=_provider_from_payload(wind_a_alt, "tushare-first"),
                target_keys=["wind_a_alternative"],
                price=wind_a_price,
                change_pct=wind_a_change,
            )
        else:
            data_status["中证全指"] = False
            elapsed, _ = timer.record("中证全指获取(失败)", 3)
            emit(f"   ❌ 中证全指获取失败 [⏱ {elapsed:.2f}s]")
            _append_log(
                module_logs,
                "request.wind_a",
                "degraded",
                "中证全指为空或无效",
                provider="tushare-first",
                target_keys=["wind_a_alternative"],
            )
    except Exception as error:
        data_status["中证全指"] = False
        elapsed, _ = timer.record("中证全指获取(失败)", 3)
        emit(f"   ❌ 中证全指获取异常: {error} [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.wind_a",
            "error",
            "中证全指请求失败",
            provider="tushare-first",
            target_keys=["wind_a_alternative"],
            error=str(error),
        )

    if "csi500" in request_registry:
        results["csi500_index"] = _collect_optional_index_request(
            request_registry=request_registry,
            request_key="csi500",
            result_key="csi500_index",
            label="中证500",
            step_key="request.csi500",
            target_date=target_date,
            timer=timer,
            emit=emit,
            module_logs=module_logs,
            data_status=data_status,
            step_status=step_status,
            timer_order="3.5",
        )

    results["csi1000_index"] = _collect_optional_index_request(
        request_registry=request_registry,
        request_key="csi1000",
        result_key="csi1000_index",
        label="中证1000",
        step_key="request.csi1000",
        target_date=target_date,
        timer=timer,
        emit=emit,
        module_logs=module_logs,
        data_status=data_status,
        step_status=step_status,
        timer_order="3.6",
        fallback_loader=_resolve_csi1000_fallback,
    )

    if not require_index_cross_validation:
        return {
            "results": results,
            "data_status": data_status,
            "step_status": step_status,
            "module_logs": module_logs,
        }

    step_status["指数交叉核对"] = False
    emit("  3.7️⃣ 交叉核对六个指数（Tushare + 腾讯日K）...")
    try:
        validation = index_cross_validator(results, target_date) if callable(index_cross_validator) else {}
        results["index_cross_validation"] = validation
        validation_ok = bool(
            isinstance(validation, dict)
            and validation.get("status") == "success"
            and len(validation.get("checks") or []) == 6
        )
        data_status["指数交叉核对"] = validation_ok
        step_status["指数交叉核对"] = validation_ok
        elapsed, _ = timer.record(
            "指数交叉核对" if validation_ok else "指数交叉核对(失败)",
            "3.7",
        )
        if validation_ok:
            emit(f"   ✅ 六个指数交叉核对通过 [⏱ {elapsed:.2f}s]")
        else:
            failures = validation.get("failures") if isinstance(validation, dict) else []
            summary = "；".join(str(item) for item in (failures or [])[:3]) or "核对证据不完整"
            emit(f"   ❌ 六个指数交叉核对失败: {summary} [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.index_cross_validation",
            "success" if validation_ok else "error",
            "六个指数交叉核对通过" if validation_ok else "六个指数交叉核对失败",
            provider=(validation or {}).get("verification_provider", "tencent.fqkline.day")
            if isinstance(validation, dict)
            else "tencent.fqkline.day",
            target_keys=["index_cross_validation"],
            target_date=target_date,
            row_count=len((validation or {}).get("checks") or []) if isinstance(validation, dict) else 0,
            failure_count=len((validation or {}).get("failures") or []) if isinstance(validation, dict) else 1,
        )
    except Exception as error:
        results["index_cross_validation"] = {
            "schema_version": "report_index_cross_validation.v1",
            "target_date": target_date,
            "status": "failed",
            "checks": [],
            "failures": [f"指数交叉核对异常：{error}"],
        }
        data_status["指数交叉核对"] = False
        elapsed, _ = timer.record("指数交叉核对(失败)", "3.7")
        emit(f"   ❌ 六个指数交叉核对异常: {error} [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.index_cross_validation",
            "error",
            "六个指数交叉核对异常",
            provider="tencent.fqkline.day",
            target_keys=["index_cross_validation"],
            target_date=target_date,
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }
