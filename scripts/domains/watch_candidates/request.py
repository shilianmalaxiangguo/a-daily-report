from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import queue
import threading


class _HardTimeoutError(TimeoutError):
    pass


class _ImmediateResult:
    def __init__(self, value):
        self._value = value

    def result(self):
        return self._value


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.watch_candidates.request",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _normalize_candidate_code(raw_code):
    code = str(raw_code or "").strip().lower()
    for prefix in (".sz", ".ss", ".sh"):
        code = code.replace(prefix, "")
    if code.startswith("sz") or code.startswith("sh") or code.startswith("bj"):
        code = code[2:]
    return code


def _build_full_code(code):
    if not code:
        return ""
    return f"{'sh' if code.startswith('6') else 'sz'}{code}"


def _extract_cached_history(cache, code_for_lookup, target_date, stats, emit):
    if cache is None:
        return []

    cached_data = cache.get(code_for_lookup, target_date) or []
    if len(cached_data) > 3:
        historical_part = list(cached_data[:-3])
        stats["cache_hits"] += 1
        emit(f"      💾 缓存命中({len(historical_part)}天): {code_for_lookup}")
        return historical_part
    return []


def _cache_has_required_methods(cache):
    required = ("get", "set", "clean_old_cache", "get_cache_stats")
    return cache is not None and all(callable(getattr(cache, method_name, None)) for method_name in required)


def _extract_tushare_cached_history(cache, code_for_lookup, target_date, stats, emit):
    if cache is None:
        return []

    cache_key = f"tushare:{code_for_lookup}"
    cached_entry = {}
    if callable(getattr(cache, "get_entry", None)):
        cached_entry = cache.get_entry(cache_key, target_date) or {}
    cached_data = []
    if cached_entry.get("source") == "tushare_full_window":
        cached_data = cached_entry.get("data") or []
    if len(cached_data) > 0:
        stats["tushare_cache_hits"] += 1
        emit(f"      💾 Tushare缓存命中({len(cached_data)}天): {code_for_lookup}")
        return list(cached_data)
    return []


def _save_tushare_cached_history(cache, code_for_lookup, target_date, records):
    if cache is None or not records:
        return
    cache.set(
        f"tushare:{code_for_lookup}",
        target_date,
        list(records),
        source="tushare_full_window",
        max_length=120,
    )


def _fetch_baostock_history(source, code_for_lookup, target_date):
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    recent_start = target_dt - timedelta(days=25)
    recent_end = target_dt
    recent_data = source.get_historical_data(code_for_lookup, recent_start.date(), recent_end.date()) or []
    return [item.amount / 1e8 for item in recent_data if getattr(item, "amount", 0)]


def _fetch_tushare_turnover_history(fetcher, code_for_lookup, target_date, *, empty_retries=0, emit=None):
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    recent_start = target_dt - timedelta(days=25)
    recent_end = target_dt
    start_date = recent_start.strftime("%Y-%m-%d")
    end_date = recent_end.strftime("%Y-%m-%d")
    attempts = max(1, int(empty_retries or 0) + 1)
    for attempt in range(attempts):
        records = list(fetcher(code_for_lookup, start_date, end_date) or [])
        if records or attempt == attempts - 1:
            return records
        if emit:
            emit(f"      🔁 Tushare成交额历史空数据重试: {code_for_lookup} ({attempt + 1}/{attempts - 1})")
    return []


def _fetch_tushare_turnover_history_payload(fetcher, code_for_lookup, target_date, *, empty_retries=0, emit=None):
    try:
        records = _fetch_tushare_turnover_history(
            fetcher,
            code_for_lookup,
            target_date,
            empty_retries=empty_retries,
            emit=emit,
        )
        return {"records": records, "error": ""}
    except Exception as error:
        return {"records": [], "error": str(error)}


def _merge_history_parts(historical_part, recent_part, data_source, stats):
    if data_source == "Tushare" and recent_part:
        return recent_part, data_source
    if historical_part and recent_part:
        combined = historical_part[:-3] + recent_part if len(historical_part) > 3 else recent_part
        stats["cache_partial"] += 1
        return combined, f"缓存+{data_source}"
    if recent_part:
        return recent_part, data_source
    if historical_part:
        return historical_part, "缓存"
    return [], ""


def _call_with_hard_timeout(timeout_seconds, func, **kwargs):
    if not timeout_seconds or timeout_seconds <= 0:
        return func(**kwargs)

    result_queue = queue.Queue(maxsize=1)

    def _target():
        try:
            result_queue.put(("result", func(**kwargs)))
        except BaseException as error:
            result_queue.put(("error", error))

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        raise _HardTimeoutError(f"QuickTiny request exceeded {timeout_seconds:.2f}s")
    status, payload = result_queue.get_nowait()
    if status == "error":
        raise payload
    return payload


def _resolve_history_provider(stats):
    if stats.get("tushare_success", 0) > 0:
        return "tushare.daily"
    if stats.get("tushare_cache_hits", 0) > 0:
        return "tushare.daily(cache)"
    if stats.get("quicktiny_success", 0) > 0 or stats.get("baostock_success", 0) > 0:
        return "quicktiny.merged_kline+baostock"
    if stats.get("cache_hits", 0) > 0:
        return "cache"
    return "tushare.daily"


def _build_tushare_history_diagnostic_note(stats, worker_count, empty_retries, rescue_threshold):
    note_parts = [
        f"Tushare并发{worker_count}",
        f"空数据重试{empty_retries}次",
        "成功{success}只/失败{fail}只".format(
            success=stats.get("tushare_success", 0),
            fail=stats.get("tushare_fail", 0),
        ),
    ]
    failed_codes = stats.get("tushare_failed_codes") or []
    if failed_codes:
        note_parts.append("失败代码: " + ",".join(str(code) for code in failed_codes))
    if stats.get("tushare_cache_hits", 0):
        note_parts.append("Tushare缓存命中{count}只".format(count=stats.get("tushare_cache_hits", 0)))
    if stats.get("tushare_rescue_triggered", 0):
        note_parts.append("串行补救{count}只".format(count=stats.get("tushare_rescue_attempts", 0)))
        note_parts.append(f"补救阈值{float(rescue_threshold or 0) * 100:.0f}%")
    return "；".join(note_parts)


def collect_watch_candidate_history_request_bundle(
    target_date,
    *,
    candidates,
    stock_full_info,
    get_cache,
    fetch_tushare_turnover_history=None,
    fetch_quicktiny_history,
    baostock_source_factory,
    timer,
    emit,
    limit=20,
    quicktiny_timeout_seconds=3.0,
    cached_history_min_days=20,
    enable_live_quicktiny=True,
    enable_baostock_fallback=True,
    tushare_history_max_workers=4,
    tushare_history_empty_retries=1,
    tushare_empty_rate_rescue_threshold=0.35,
):
    candidates = list(candidates or [])
    stock_full_info = stock_full_info or {}
    logs = []
    results = {
        "stocks_with_history": [],
        "history_fetch_stats": {
            "tushare_success": 0,
            "tushare_fail": 0,
            "tushare_failed_codes": [],
            "tushare_rescue_triggered": 0,
            "tushare_rescue_attempts": 0,
            "tushare_rescue_success": 0,
            "tushare_rescue_fail": 0,
            "tushare_cache_hits": 0,
            "quicktiny_success": 0,
            "quicktiny_fail": 0,
            "baostock_success": 0,
            "baostock_fail": 0,
            "cache_hits": 0,
            "cache_partial": 0,
        },
    }

    emit(
        f"   📊 候选股补数：获取 {min(len(candidates), limit)} 只过程候选的历史成交额"
        "（只作筛选证据，不代表最终动作）..."
    )
    emit("   📝 候选补数策略：Tushare优先（完整近期窗口） → QuickTiny/BaoStock仅兜底 | 缓存仅作降级补充")

    try:
        cache = get_cache() if get_cache else None
        if not _cache_has_required_methods(cache):
            if cache is not None:
                emit("   ⚠️ 历史缓存不可用: 缓存对象缺少必要接口，已跳过缓存")
            cache = None

        if cache is not None:
            cache.clean_old_cache(keep_days=7)
            cache_stats = cache.get_cache_stats(target_date)
            if cache_stats.get("count", 0) > 0:
                emit(f"   💾 今日缓存: {cache_stats['count']}只股票, {cache_stats['size_mb']}MB")
        else:
            cache_stats = {"count": 0, "size_mb": 0}

        baostock_source = None
        candidate_contexts = []
        tushare_contexts = []

        for stock in candidates[:limit]:
            code = stock.get("code", "")
            name = stock.get("name", "")
            current_turnover = stock.get("turnover", 0)

            code_for_lookup = _normalize_candidate_code(code)
            full_code = _build_full_code(code_for_lookup)
            if not code_for_lookup:
                continue

            try:
                tushare_cached_part = _extract_tushare_cached_history(
                    cache,
                    code_for_lookup,
                    target_date,
                    results["history_fetch_stats"],
                    emit,
                )
                historical_part = _extract_cached_history(
                    cache,
                    code_for_lookup,
                    target_date,
                    results["history_fetch_stats"],
                    emit,
                )
                context = {
                    "stock": stock,
                    "code": code,
                    "name": name,
                    "current_turnover": current_turnover,
                    "code_for_lookup": code_for_lookup,
                    "full_code": full_code,
                    "historical_part": historical_part,
                    "tushare_cached_part": tushare_cached_part,
                }
                candidate_contexts.append(context)
                if tushare_cached_part:
                    continue
                if callable(fetch_tushare_turnover_history) and len(historical_part) < cached_history_min_days:
                    tushare_contexts.append(context)
            except Exception as error:
                emit(f"      ⚠️ {name} 历史缓存读取失败: {error}")

        def _process_candidate_context(context):
            nonlocal baostock_source

            code = context["code"]
            name = context["name"]
            current_turnover = context["current_turnover"]
            code_for_lookup = context["code_for_lookup"]
            full_code = context["full_code"]
            historical_part = context["historical_part"]
            tushare_cached_part = context["tushare_cached_part"]
            stock = context["stock"]

            try:
                recent_part = []
                data_source = "未知"
                if tushare_cached_part:
                    combined, merged_source = tushare_cached_part, "Tushare缓存"
                    emit(f"      💾 候选补数Tushare缓存足够: {code_for_lookup} ({len(combined)}天)，跳过实时补充")
                elif len(historical_part) >= cached_history_min_days:
                    combined, merged_source = historical_part, "缓存"
                    emit(f"      💾 候选补数缓存足够: {code_for_lookup} ({len(historical_part)}天)，跳过QuickTiny实时补充")
                else:
                    combined = []
                    merged_source = ""

                    tushare_future = context.get("tushare_future")
                    if tushare_future is not None:
                        payload = tushare_future.result() or {}
                        recent_part = list(payload.get("records") or [])
                        error = payload.get("error") or ""
                        if recent_part:
                            results["history_fetch_stats"]["tushare_success"] += 1
                            data_source = "Tushare"
                            _save_tushare_cached_history(cache, code_for_lookup, target_date, recent_part)
                            emit(f"      ✅ 候选补数Tushare成交额历史成功: {code_for_lookup} ({len(recent_part)}天)")
                        else:
                            results["history_fetch_stats"]["tushare_fail"] += 1
                            results["history_fetch_stats"]["tushare_failed_codes"].append(code_for_lookup)
                            if error:
                                emit(f"      ⚠️ 候选补数Tushare成交额历史失败: {code_for_lookup} - {error}, 将使用QuickTiny/BaoStock兜底")
                            else:
                                emit(f"      ⚠️ 候选补数Tushare成交额历史空数据: {code_for_lookup}")

                    if enable_live_quicktiny:
                        if not recent_part:
                            try:
                                recent_part = list(
                                    _call_with_hard_timeout(
                                        quicktiny_timeout_seconds,
                                        fetch_quicktiny_history,
                                        full_code=full_code,
                                        code=code_for_lookup,
                                        target_date=target_date,
                                        days=30,
                                    )
                                    or []
                                )
                                if recent_part:
                                    results["history_fetch_stats"]["quicktiny_success"] += 1
                                    data_source = "QuickTiny"
                                    emit(f"      ⚡ 候选补数QuickTiny成功: {code_for_lookup} ({len(recent_part)}天)")
                                else:
                                    results["history_fetch_stats"]["quicktiny_fail"] += 1
                            except _HardTimeoutError as error:
                                results["history_fetch_stats"]["quicktiny_fail"] += 1
                                emit(f"      ⏱️ 候选补数QuickTiny超时: {code_for_lookup} - {error}, 将使用BaoStock兜底")
                            except Exception:
                                results["history_fetch_stats"]["quicktiny_fail"] += 1
                                emit(f"      ⚡ 候选补数QuickTiny失败: {code_for_lookup}, 将使用BaoStock兜底")
                    else:
                        if not recent_part:
                            emit(f"      ⏭️ 候选补数跳过QuickTiny实时补充: {code_for_lookup}, 使用缓存/BaoStock")

                    if not recent_part and baostock_source_factory and enable_baostock_fallback:
                        try:
                            if baostock_source is None:
                                baostock_source = baostock_source_factory()
                            recent_part = _fetch_baostock_history(baostock_source, code_for_lookup, target_date)
                            if recent_part:
                                results["history_fetch_stats"]["baostock_success"] += 1
                                data_source = "BaoStock"
                                emit(f"      🔄 候选补数BaoStock兜底成功: {code_for_lookup} ({len(recent_part)}天)")
                            else:
                                results["history_fetch_stats"]["baostock_fail"] += 1
                        except Exception as error:
                            results["history_fetch_stats"]["baostock_fail"] += 1
                            emit(f"      ❌ 候选补数BaoStock也失败: {code_for_lookup} - {error}")
                    elif not recent_part and baostock_source_factory and not enable_baostock_fallback:
                        emit(f"      ⏭️ 候选补数跳过BaoStock兜底: {code_for_lookup}")

                    combined, merged_source = _merge_history_parts(
                        historical_part,
                        recent_part,
                        data_source,
                        results["history_fetch_stats"],
                    )

                if not combined:
                    emit(f"      ⚠️ 候选补数无数据可用: {code_for_lookup}")
                    return

                if cache is not None and len(combined) > 3:
                    cache.set(
                        code_for_lookup,
                        target_date,
                        combined[:-3],
                        source="mixed_partial",
                        max_length=120,
                    )

                full_info = stock_full_info.get(code_for_lookup, {})
                results["stocks_with_history"].append(
                    {
                        "code": code,
                        "name": name,
                        "turnover": current_turnover,
                        "change_pct": full_info.get("change_pct", 0),
                        "sector": stock.get("sector", "unknown"),
                        "hist_turnover": combined,
                        "data_source": merged_source,
                    }
                )
            except Exception as error:
                emit(f"      ⚠️ {name} 历史数据获取失败: {error}")

        try:
            max_workers = int(tushare_history_max_workers or 1)
        except (TypeError, ValueError):
            max_workers = 1
        max_workers = max(1, max_workers)
        worker_count = min(max_workers, len(tushare_contexts)) if tushare_contexts else 1
        if tushare_contexts:
            if worker_count > 1:
                emit(f"      🚀 Tushare成交额历史并发上限: {worker_count}")
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                for context in tushare_contexts:
                    context["tushare_future"] = executor.submit(
                        _fetch_tushare_turnover_history_payload,
                        fetch_tushare_turnover_history,
                        context["code_for_lookup"],
                        target_date,
                        empty_retries=tushare_history_empty_retries,
                        emit=emit,
                    )

                futures_by_context = [(context, context["tushare_future"]) for context in tushare_contexts]
                for _context, future in futures_by_context:
                    future.result()

            failed_contexts = []
            for context in tushare_contexts:
                payload = context.get("tushare_future").result() or {}
                if not payload.get("records"):
                    failed_contexts.append(context)

            failure_rate = (len(failed_contexts) / len(tushare_contexts)) if tushare_contexts else 0
            threshold = float(tushare_empty_rate_rescue_threshold or 0)
            if failed_contexts and threshold > 0 and failure_rate >= threshold:
                results["history_fetch_stats"]["tushare_rescue_triggered"] = 1
                results["history_fetch_stats"]["tushare_rescue_attempts"] = len(failed_contexts)
                emit(f"      🛟 Tushare空返回率{failure_rate * 100:.1f}%，触发串行补救: {len(failed_contexts)}只")
                for context in failed_contexts:
                    code_for_lookup = context["code_for_lookup"]
                    payload = _fetch_tushare_turnover_history_payload(
                        fetch_tushare_turnover_history,
                        code_for_lookup,
                        target_date,
                        empty_retries=0,
                        emit=emit,
                    )
                    if payload.get("records"):
                        results["history_fetch_stats"]["tushare_rescue_success"] += 1
                        context["tushare_future"] = _ImmediateResult(payload)
                    else:
                        results["history_fetch_stats"]["tushare_rescue_fail"] += 1

            if tushare_contexts:
                for context in candidate_contexts:
                    _process_candidate_context(context)
        else:
            for context in candidate_contexts:
                _process_candidate_context(context)

        elapsed, _ = timer.record("候选股历史成交额获取", 15)
        emit(
            "   📈 数据源统计: Tushare成功{tushare_success}只/失败{tushare_fail}只, QuickTiny成功{quicktiny_success}只/失败{quicktiny_fail}只, "
            "BaoStock兜底成功{baostock_success}只/失败{baostock_fail}只, 缓存命中{cache_hits}只".format(
                **results["history_fetch_stats"]
            )
        )
        emit(
            "   📊 数据统计: 缓存完整命中{cache_hits}只, 混合获取{cache_partial}只, "
            "Tushare成功{tushare_success}只, QuickTiny成功{quicktiny_success}只, BaoStock成功{baostock_success}只 [⏱ {elapsed:.2f}s]".format(
                elapsed=elapsed,
                **results["history_fetch_stats"],
            )
        )
        _append_log(
            logs,
            "request.candidate_history",
            "success",
            "已获取候选股历史成交额快照",
            provider=_resolve_history_provider(results["history_fetch_stats"]),
            target_keys=["stocks_with_history", "history_fetch_stats"],
            stock_count=len(results["stocks_with_history"]),
            cache_count=cache_stats.get("count", 0),
            diagnostic_note=_build_tushare_history_diagnostic_note(
                results["history_fetch_stats"],
                worker_count,
                tushare_history_empty_retries,
                tushare_empty_rate_rescue_threshold,
            ),
            tushare_history_max_workers=worker_count,
            tushare_history_empty_retries=tushare_history_empty_retries,
            tushare_empty_rate_rescue_threshold=tushare_empty_rate_rescue_threshold,
            **results["history_fetch_stats"],
        )
    except Exception as error:
        timer.record("候选股历史成交额获取(失败)", 15)
        results["stocks_with_history"] = []
        emit(f"   ⚠️ 候选股历史成交额获取失败: {error}")
        _append_log(
            logs,
            "request.candidate_history",
            "error",
            "候选股历史成交额请求失败",
            provider="tushare.daily",
            target_keys=["stocks_with_history", "history_fetch_stats"],
            error=str(error),
        )

    return {
        "results": results,
        "module_logs": logs,
    }
