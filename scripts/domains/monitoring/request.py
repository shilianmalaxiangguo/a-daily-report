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


def collect_monitoring_request_bundle(
    target_date,
    *,
    analyzer_factory,
    fetch_wanzhu_top10,
    fetch_exchange_monitor_payload,
    fetch_stock_batch_info,
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

    emit("  1️⃣1️⃣ 获取选股通盘中异动（可选）...")
    try:
        analyzer = analyzer_factory()
        xuangubao_data = analyzer.fetch_xuangubao_data()
        if xuangubao_data and xuangubao_data.get("xuangubao_news"):
            results["xuangubao_data"] = xuangubao_data
            data_status["选股通盘中异动"] = True
            step_status["选股通盘中异动获取"] = True
            elapsed, _ = timer.record("选股通盘中异动获取", 11)
            emit(f"   ✅ 选股通数据成功: {len(xuangubao_data.get('xuangubao_news', []))} 条新闻 [⏱ {elapsed:.2f}s]")
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
        wanzhu_top10 = fetch_wanzhu_top10(target_date)
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
            exchange_quotes = fetch_stock_batch_info([item["code"] for item in today_predictions])
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
