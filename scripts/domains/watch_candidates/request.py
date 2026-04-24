from datetime import datetime, timedelta


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


def _fetch_baostock_history(source, code_for_lookup, target_date):
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    recent_start = target_dt - timedelta(days=25)
    recent_end = target_dt
    recent_data = source.get_historical_data(code_for_lookup, recent_start.date(), recent_end.date()) or []
    return [item.amount / 1e8 for item in recent_data if getattr(item, "amount", 0)]


def _merge_history_parts(historical_part, recent_part, data_source, stats):
    if historical_part and recent_part:
        combined = historical_part[:-3] + recent_part if len(historical_part) > 3 else recent_part
        stats["cache_partial"] += 1
        return combined, f"缓存+{data_source}"
    if recent_part:
        return recent_part, data_source
    if historical_part:
        return historical_part, "缓存"
    return [], ""


def collect_watch_candidate_history_request_bundle(
    target_date,
    *,
    candidates,
    stock_full_info,
    get_cache,
    fetch_quicktiny_history,
    baostock_source_factory,
    timer,
    emit,
    limit=20,
):
    candidates = list(candidates or [])
    stock_full_info = stock_full_info or {}
    logs = []
    results = {
        "stocks_with_history": [],
        "history_fetch_stats": {
            "quicktiny_success": 0,
            "quicktiny_fail": 0,
            "baostock_success": 0,
            "baostock_fail": 0,
            "cache_hits": 0,
            "cache_partial": 0,
        },
    }

    emit(f"   📊 获取 {min(len(candidates), limit)} 只候选股的历史成交额...")
    emit("   📝 策略：QuickTiny API优先 → BaoStock兜底 | 最近3天实时，更早数据用缓存")

    try:
        cache = get_cache() if get_cache else None
        if cache is not None:
            cache.clean_old_cache(keep_days=7)
            cache_stats = cache.get_cache_stats(target_date)
            if cache_stats.get("count", 0) > 0:
                emit(f"   💾 今日缓存: {cache_stats['count']}只股票, {cache_stats['size_mb']}MB")
        else:
            cache_stats = {"count": 0, "size_mb": 0}

        baostock_source = None

        for stock in candidates[:limit]:
            code = stock.get("code", "")
            name = stock.get("name", "")
            current_turnover = stock.get("turnover", 0)

            code_for_lookup = _normalize_candidate_code(code)
            full_code = _build_full_code(code_for_lookup)
            if not code_for_lookup:
                continue

            try:
                historical_part = _extract_cached_history(
                    cache,
                    code_for_lookup,
                    target_date,
                    results["history_fetch_stats"],
                    emit,
                )
                recent_part = []
                data_source = "未知"

                try:
                    recent_part = list(
                        fetch_quicktiny_history(
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
                        emit(f"      ⚡ QuickTiny成功: {code_for_lookup} ({len(recent_part)}天)")
                    else:
                        results["history_fetch_stats"]["quicktiny_fail"] += 1
                except Exception:
                    results["history_fetch_stats"]["quicktiny_fail"] += 1
                    emit(f"      ⚡ QuickTiny失败: {code_for_lookup}, 将使用BaoStock兜底")

                if not recent_part and baostock_source_factory:
                    try:
                        if baostock_source is None:
                            baostock_source = baostock_source_factory()
                        recent_part = _fetch_baostock_history(baostock_source, code_for_lookup, target_date)
                        if recent_part:
                            results["history_fetch_stats"]["baostock_success"] += 1
                            data_source = "BaoStock"
                            emit(f"      🔄 BaoStock兜底成功: {code_for_lookup} ({len(recent_part)}天)")
                        else:
                            results["history_fetch_stats"]["baostock_fail"] += 1
                    except Exception as error:
                        results["history_fetch_stats"]["baostock_fail"] += 1
                        emit(f"      ❌ BaoStock也失败: {code_for_lookup} - {error}")

                combined, merged_source = _merge_history_parts(
                    historical_part,
                    recent_part,
                    data_source,
                    results["history_fetch_stats"],
                )
                if not combined:
                    emit(f"      ⚠️ {code_for_lookup} 无数据可用")
                    continue

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

        elapsed, _ = timer.record("候选股历史成交额获取", 15)
        emit(
            "   📈 数据源统计: QuickTiny成功{quicktiny_success}只/失败{quicktiny_fail}只, "
            "BaoStock兜底成功{baostock_success}只/失败{baostock_fail}只, 缓存命中{cache_hits}只".format(
                **results["history_fetch_stats"]
            )
        )
        emit(
            "   📊 数据统计: 缓存完整命中{cache_hits}只, 混合获取{cache_partial}只, "
            "QuickTiny成功{quicktiny_success}只, BaoStock成功{baostock_success}只 [⏱ {elapsed:.2f}s]".format(
                elapsed=elapsed,
                **results["history_fetch_stats"],
            )
        )
        _append_log(
            logs,
            "request.candidate_history",
            "success",
            "已获取候选股历史成交额快照",
            provider="quicktiny.merged_kline+baostock",
            target_keys=["stocks_with_history", "history_fetch_stats"],
            stock_count=len(results["stocks_with_history"]),
            cache_count=cache_stats.get("count", 0),
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
            provider="quicktiny.merged_kline+baostock",
            target_keys=["stocks_with_history", "history_fetch_stats"],
            error=str(error),
        )

    return {
        "results": results,
        "module_logs": logs,
    }
