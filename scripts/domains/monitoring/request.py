def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.monitoring.request",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _normalize_stock_code(raw_code):
    code = str(raw_code or "")
    for prefix in (".SZ", ".SS", ".SH", "sz", "sh", "bj"):
        code = code.replace(prefix, "")
    return code


def _enrich_rows_with_quotes(rows, quote_map):
    quote_map = quote_map or {}
    enriched = []
    for row in rows or []:
        item = dict(row or {})
        code = _normalize_stock_code(item.get("code") or item.get("代码"))
        quote = quote_map.get(code, {}) if isinstance(quote_map, dict) else {}
        if quote:
            for source_key, target_key in (
                ("change_pct", "change_pct"),
                ("close", "close"),
                ("turnover", "turnover"),
                ("high", "high"),
                ("low", "low"),
                ("open", "open"),
            ):
                if quote.get(source_key) is not None:
                    item[target_key] = quote.get(source_key)
            item["quote_source"] = quote.get("data_source") or "tushare.daily"
        enriched.append(item)
    return enriched


def collect_monitoring_request_bundle(
    target_date,
    *,
    analyzer_factory,
    fetch_wanzhu_top10,
    fetch_exchange_monitor_payload,
    fetch_stock_batch_info,
    fetch_tushare_stock_batch_info=None,
    historical_rebuild=False,
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {
        "选股通盘中异动获取": False,
        "顽主杯热门前十获取": False,
        "异动检测数据获取": False,
    }
    module_logs = []

    if historical_rebuild:
        step_status = {}
        results.update(
            {
                "xuangubao_data": {},
                "wanzhu_top10": [],
                "exchange_monitor_today": [],
                "exchange_monitor_nextday": [],
            }
        )
        for step, provider, target_keys, message in (
            (
                "request.xuangubao",
                "historical_rebuild.excluded_current_xuangubao",
                ["xuangubao_data"],
                "选股通当前板块与涨停解释未参与历史判断",
            ),
            (
                "request.wanzhu_top10",
                "historical_rebuild.excluded_current_wanzhu",
                ["wanzhu_top10"],
                "顽主杯当前榜单未参与历史判断",
            ),
            (
                "request.exchange_monitor",
                "historical_rebuild.excluded_current_exchange_monitor",
                ["exchange_monitor_today", "exchange_monitor_nextday"],
                "当前异动检测未参与历史判断",
            ),
        ):
            _append_log(
                module_logs,
                step,
                "skipped",
                message,
                provider=provider,
                target_keys=target_keys,
                target_date=target_date,
            )
        emit("  1️⃣1️⃣-1️⃣4️⃣ 当前型监控来源未参与历史重建")
        return {
            "results": results,
            "data_status": data_status,
            "step_status": step_status,
            "module_logs": module_logs,
        }

    emit("  1️⃣1️⃣ 获取选股通盘中异动（可选）...")
    try:
        analyzer = analyzer_factory()
        try:
            xuangubao_data = analyzer.fetch_xuangubao_data(target_date=target_date)
        except TypeError:
            xuangubao_data = analyzer.fetch_xuangubao_data()
        news_count = len((xuangubao_data or {}).get("xuangubao_news", []) or [])
        plate_count = len((xuangubao_data or {}).get("xuangubao_plates", []) or [])
        limit_up_reason_count = len((xuangubao_data or {}).get("xuangubao_limit_up_reasons", []) or [])
        diagnostics = (xuangubao_data or {}).get("diagnostics", {}) or {}
        request_counts = dict(diagnostics.get("request_counts") or {})
        request_timings_ms = dict(diagnostics.get("request_timings_ms") or {})
        diagnostic_note = "; ".join(
            f"{key}={value}"
            for key, value in diagnostics.items()
            if key not in {"request_counts", "request_timings_ms"} and value not in (None, "", {})
        )
        if xuangubao_data and (news_count or plate_count or limit_up_reason_count):
            results["xuangubao_data"] = xuangubao_data
            data_status["选股通盘中异动"] = True
            step_status["选股通盘中异动获取"] = True
            elapsed, _ = timer.record("选股通盘中异动获取", 11)
            emit(f"   ✅ 选股通数据成功: 新闻{news_count}条，盘面{plate_count}个，涨停解释{limit_up_reason_count}条 [⏱ {elapsed:.2f}s]")
        else:
            results["xuangubao_data"] = {}
            data_status["选股通盘中异动"] = False
            elapsed, _ = timer.record("选股通盘中异动获取(空)", 11)
            emit(f"   ⚠️ 选股通数据返回空（可选模块） [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.xuangubao",
            "success" if data_status.get("选股通盘中异动") else "degraded",
            "已处理选股通异动请求",
            provider="xuangubao.fetch_xuangubao_data",
            target_keys=["xuangubao_data"],
            optional=True,
            news_count=len((results.get("xuangubao_data") or {}).get("xuangubao_news", []) or []),
            plate_count=len((results.get("xuangubao_data") or {}).get("xuangubao_plates", []) or []),
            limit_up_reason_count=len((results.get("xuangubao_data") or {}).get("xuangubao_limit_up_reasons", []) or []),
            diagnostic_note=diagnostic_note,
            diagnostics=diagnostics,
            request_counts=request_counts,
            request_timings_ms=request_timings_ms,
        )
    except Exception as error:
        results["xuangubao_data"] = {}
        data_status["选股通盘中异动"] = False
        emit(f"   ⚠️ 选股通数据失败（可选模块）: {error}")
        _append_log(
            module_logs,
            "request.xuangubao",
            "error",
            "选股通异动请求失败",
            provider="xuangubao.fetch_xuangubao_data",
            target_keys=["xuangubao_data"],
            optional=True,
            error=str(error),
        )

    emit("  1️⃣2️⃣ 获取顽主杯热门前十...")
    try:
        wanzhu_top10 = list(fetch_wanzhu_top10(target_date) or [])
        wanzhu_quote_provider = ""
        wanzhu_quote_fallback_used = False
        if wanzhu_top10 and callable(fetch_tushare_stock_batch_info):
            try:
                quote_codes = [_normalize_stock_code(item.get("code") or item.get("代码")) for item in wanzhu_top10]
                quote_map = fetch_tushare_stock_batch_info([code for code in quote_codes if code]) or {}
                if quote_map:
                    wanzhu_top10 = _enrich_rows_with_quotes(wanzhu_top10, quote_map)
                    wanzhu_quote_provider = "tushare.daily"
            except Exception as error:
                wanzhu_quote_fallback_used = True
                emit(f"   ⚠️ Tushare顽主杯补价失败: {error}")
        results["wanzhu_top10"] = wanzhu_top10
        if wanzhu_top10:
            data_status["顽主杯热门前十"] = True
            step_status["顽主杯热门前十获取"] = True
            elapsed, _ = timer.record("顽主杯热门前十获取", 12)
            emit(f"   ✅ 顽主杯前十成功: {len(wanzhu_top10)} 只 [⏱ {elapsed:.2f}s]")
        else:
            data_status["顽主杯热门前十"] = False
            elapsed, _ = timer.record("顽主杯热门前十获取(空)", 12)
            emit(f"   ⚠️ 顽主杯数据为空 [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.wanzhu_top10",
            "success" if data_status.get("顽主杯热门前十") else "degraded",
            "已处理顽主杯请求",
            provider="AShareDataCollector.get_wanzhu_top10",
            quote_provider=wanzhu_quote_provider,
            quote_fallback_used=wanzhu_quote_fallback_used,
            target_keys=["wanzhu_top10"],
            stock_count=len(results.get("wanzhu_top10", []) or []),
        )
    except Exception as error:
        results["wanzhu_top10"] = []
        data_status["顽主杯热门前十"] = False
        emit(f"   ⚠️ 顽主杯失败: {error}")
        _append_log(
            module_logs,
            "request.wanzhu_top10",
            "error",
            "顽主杯请求失败",
            provider="AShareDataCollector.get_wanzhu_top10",
            target_keys=["wanzhu_top10"],
            error=str(error),
        )

    emit("  1️⃣4️⃣ 获取异动检测数据...")
    try:
        payload = fetch_exchange_monitor_payload() or {}
        today_predictions = []
        nextday_predictions = []
        for item in payload.get("data", []) or []:
            prediction_item = {
                "code": item.get("code", ""),
                "name": item.get("name", ""),
                "deviation_days": item.get("max_days", 0),
                "deviation_pct": item.get("deviation_value", 0),
                "trigger_pct": item.get("change_rate_target", 0),
            }
            if item.get("is_today"):
                today_predictions.append(prediction_item)
            if item.get("is_nextday"):
                nextday_predictions.append(prediction_item)

        if today_predictions:
            emit("   📊 获取异动股票实时行情，判断触发状态...")
            quote_codes = [item["code"] for item in today_predictions]
            exchange_quotes = {}
            quote_provider = "tencent.get_stock_batch_info"
            quote_fallback_used = False
            if callable(fetch_tushare_stock_batch_info):
                try:
                    exchange_quotes = fetch_tushare_stock_batch_info(quote_codes) or {}
                    if exchange_quotes:
                        quote_provider = "tushare.daily"
                except Exception as error:
                    quote_fallback_used = True
                    emit(f"   ⚠️ Tushare异动补价失败: {error}，切换腾讯兜底")
            if not exchange_quotes:
                quote_fallback_used = callable(fetch_tushare_stock_batch_info)
                exchange_quotes = fetch_stock_batch_info(quote_codes)
            for pred in today_predictions:
                quote = exchange_quotes.get(pred["code"], {}) if isinstance(exchange_quotes, dict) else {}
                actual_change = quote.get("change_pct")
                pred["actual_change_pct"] = actual_change
                pred["is_triggered"] = actual_change >= pred.get("trigger_pct", 0) if actual_change is not None else None
            triggered_count = sum(1 for item in today_predictions if item.get("is_triggered") is True)
            emit(f"   ✅ 已触发: {triggered_count}/{len(today_predictions)}只")

        results["exchange_monitor_today"] = today_predictions
        results["exchange_monitor_nextday"] = nextday_predictions
        step_status["异动检测数据获取"] = True
        elapsed, _ = timer.record("异动检测数据获取", 14)
        emit(f"   ✅ 异动检测: 当日{len(today_predictions)}只，次日{len(nextday_predictions)}只 [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.exchange_monitor",
            "success",
            "已处理异动检测请求",
            provider="quicktiny.exchange_monitor",
            quote_provider=quote_provider if today_predictions else "",
            quote_fallback_used=quote_fallback_used if today_predictions else False,
            target_keys=["exchange_monitor_today", "exchange_monitor_nextday"],
            today_count=len(today_predictions),
            nextday_count=len(nextday_predictions),
        )
    except Exception as error:
        results["exchange_monitor_today"] = []
        results["exchange_monitor_nextday"] = []
        timer.record("异动检测数据获取(异常)", 14)
        emit(f"   ⚠️ 异动检测失败: {error}")
        _append_log(
            module_logs,
            "request.exchange_monitor",
            "error",
            "异动检测请求失败",
            provider="quicktiny.exchange_monitor",
            target_keys=["exchange_monitor_today", "exchange_monitor_nextday"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }
