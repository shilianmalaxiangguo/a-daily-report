def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.market_activity.request",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _build_sector_bucket(records, *, include_zt_type=False):
    buckets = {}
    for item in records or []:
        sector = item.get("所属行业", "未知")
        if sector not in buckets:
            buckets[sector] = []
        row = {
            "code": item.get("代码", ""),
            "name": item.get("名称", ""),
        }
        if include_zt_type:
            row["zt_type"] = item.get("涨停统计", "")
        buckets[sector].append(row)
    return buckets


def _normalize_market_stats_value(value):
    try:
        if isinstance(value, str):
            raw = value.replace("%", "").strip()
            if raw == "":
                return 0
            value = float(raw)
        if value != value:
            return 0
        return int(value)
    except Exception:
        return 0


def _build_code_to_sector_map(existing_results=None):
    existing_results = existing_results or {}
    code_to_sector = {}

    for stock in existing_results.get("zt_pool", []) or []:
        code = stock.get("代码", "")
        sector = stock.get("所属行业", "")
        if code and sector:
            code_to_sector[code] = sector

    for key in ("lhb_net_buy_top10", "lhb_net_sell_top10"):
        for stock in existing_results.get(key, []) or []:
            code = str(stock.get("code", "") or "").replace(".SZ", "").replace(".SS", "")
            sector = stock.get("sector", "")
            if code and sector and sector != "未知":
                code_to_sector[code] = sector

    return code_to_sector


def collect_market_activity_pool_request_bundle(
    target_date,
    *,
    get_limit_up_pool,
    get_limit_down_pool,
    fetch_market_activity_df,
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {"涨停跌停数据获取": False}
    module_logs = []
    artifacts = {"limit_up_df": None, "limit_down_df": None}

    emit("  4️⃣ 获取涨停跌停数据（akshare涨停跌停池模块）...")
    try:
        date_str = str(target_date or "").replace("-", "")

        limit_up_df, limit_up_codes = get_limit_up_pool(date_str)
        artifacts["limit_up_df"] = limit_up_df
        if not limit_up_df.empty:
            zt_pool_records = limit_up_df.to_dict("records")
            results["zt_pool"] = zt_pool_records
            results["limit_up_codes"] = limit_up_codes
            data_status["涨停池"] = True
            emit(f"   ✅ 涨停池: {len(limit_up_df)} 只")
            results["zt_pool_by_sector"] = _build_sector_bucket(zt_pool_records, include_zt_type=True)
            data_status["涨停股板块分布"] = True
            emit(f"   ✅ 涨停股板块分布: {len(results['zt_pool_by_sector'])} 个板块")
        else:
            results["zt_pool"] = []
            results["limit_up_codes"] = set()
            data_status["涨停池"] = False
            emit("   ❌ 涨停池为空")

        limit_down_df, limit_down_codes = get_limit_down_pool(date_str)
        artifacts["limit_down_df"] = limit_down_df
        if not limit_down_df.empty:
            dt_pool_records = limit_down_df.to_dict("records")
            results["dt_pool"] = dt_pool_records
            results["limit_down_codes"] = limit_down_codes
            data_status["跌停池"] = True
            emit(f"   ✅ 跌停池: {len(limit_down_df)} 只")
            results["dt_pool_by_sector"] = _build_sector_bucket(dt_pool_records)
            data_status["跌停股板块分布"] = True
            emit(f"   ✅ 跌停股板块分布: {len(results['dt_pool_by_sector'])} 个板块")
        else:
            results["dt_pool"] = []
            results["limit_down_codes"] = set()
            data_status["跌停池"] = False
            emit("   ❌ 跌停池为空")

        market_activity_df = fetch_market_activity_df()
        emit(f"   📊 大盘涨跌统计原始数据: {len(market_activity_df)} 行")
        if not market_activity_df.empty:
            market_stats = {}
            for _, row in market_activity_df.iterrows():
                item = row[0] if len(row) > 0 else ""
                value = row[1] if len(row) > 1 else 0
                numeric_value = _normalize_market_stats_value(value)
                if item == "上涨":
                    market_stats["up_count"] = numeric_value
                elif item == "下跌":
                    market_stats["down_count"] = numeric_value
                elif item == "涨停":
                    market_stats["zt_count"] = numeric_value
                elif item == "跌停":
                    market_stats["dt_count"] = numeric_value
            results["market_stats"] = market_stats
            data_status["大盘涨跌统计"] = True
            emit(f"   ✅ 大盘涨跌统计: 上涨{market_stats.get('up_count', 0)}家 vs 下跌{market_stats.get('down_count', 0)}家")
        else:
            results["market_stats"] = {}
            data_status["大盘涨跌统计"] = False
            emit("   ⚠️ 大盘涨跌统计数据为空")

        step_status["涨停跌停数据获取"] = True
        elapsed, _ = timer.record("涨停跌停数据获取", 4)
        emit(f"   ✅ 涨停跌停数据完成 [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.pool_snapshot",
            "success",
            "已获取涨停跌停池与市场活跃度快照",
            provider="akshare.limit_up_down+akshare.stock_market_activity_legu",
            target_keys=["zt_pool", "dt_pool", "zt_pool_by_sector", "dt_pool_by_sector", "market_stats"],
            zt_count=len(results.get("zt_pool", [])),
            dt_count=len(results.get("dt_pool", [])),
        )
    except Exception as error:
        elapsed, _ = timer.record("涨停跌停数据获取(失败)", 4)
        emit(f"   ❌ 涨停跌停数据失败: {error} [⏱ {elapsed:.2f}s]")
        results["zt_pool"] = []
        results["dt_pool"] = []
        results["limit_up_codes"] = set()
        results["limit_down_codes"] = set()
        results["market_stats"] = {}
        data_status["涨停池"] = False
        data_status["跌停池"] = False
        data_status["大盘涨跌统计"] = False
        _append_log(
            module_logs,
            "request.pool_snapshot",
            "error",
            "涨停跌停池请求失败",
            provider="akshare.limit_up_down+akshare.stock_market_activity_legu",
            target_keys=["zt_pool", "dt_pool", "zt_pool_by_sector", "dt_pool_by_sector", "market_stats"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
        "artifacts": artifacts,
    }


def collect_market_activity_hot_rank_request_bundle(
    target_date,
    *,
    existing_results,
    fetch_ths_hot_stock,
    get_integrated_hot_list,
    tencent,
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {
        "热度前三十个股获取": False,
        "整合热榜获取": False,
    }
    module_logs = []

    emit(f"  5️⃣ 获取{target_date}热度前三十个股（同花顺首选）...")
    primary_error = ""
    hot_stocks = []
    try:
        hot_stocks = fetch_ths_hot_stock(num=30)
    except Exception as error:
        primary_error = str(error)
        emit(f"   ⚠️ 同花顺热榜失败: {error}，尝试腾讯备用...")
        _append_log(
            module_logs,
            "request.hot_rank.primary",
            "error",
            "同花顺热榜请求失败",
            provider="ths_hot_stock",
            target_keys=["hot_rank_top30"],
            error=str(error),
        )
    else:
        if hot_stocks:
            code_to_sector = _build_code_to_sector_map(existing_results)
            results["code_to_sector"] = code_to_sector
            for stock in hot_stocks:
                if stock.get("code") in code_to_sector:
                    stock["sector"] = code_to_sector[stock.get("code")]
            results["hot_rank_top30"] = hot_stocks
            data_status["热度前三十个股"] = True
            step_status["热度前三十个股获取"] = True
            elapsed, _ = timer.record("热度前三十个股获取", 5)
            emit(f"   ✅ 同花顺热榜成功: {len(hot_stocks)} 只 [⏱ {elapsed:.2f}s]")
            _append_log(
                module_logs,
                "request.hot_rank.primary",
                "success",
                "同花顺热榜成功",
                provider="ths_hot_stock",
                target_keys=["hot_rank_top30"],
                hot_rank_count=len(hot_stocks),
            )
        else:
            primary_error = "empty_result"
            emit("   ⚠️ 同花顺返回空，尝试腾讯备用...")
            _append_log(
                module_logs,
                "request.hot_rank.primary",
                "degraded",
                "同花顺热榜返回空",
                provider="ths_hot_stock",
                target_keys=["hot_rank_top30"],
                error="empty_result",
            )

    if not data_status.get("热度前三十个股"):
        try:
            hot_stocks = tencent.get_hot_stocks(num=30)
            if hot_stocks:
                results["hot_rank_top30"] = hot_stocks
                data_status["热度前三十个股"] = True
                step_status["热度前三十个股获取"] = True
                elapsed, _ = timer.record("热度前三十个股获取", 5)
                emit(f"   ✅ 腾讯热榜成功: {len(hot_stocks)} 只 [⏱ {elapsed:.2f}s]")
                _append_log(
                    module_logs,
                    "request.hot_rank.fallback",
                    "success",
                    "腾讯热榜兜底成功",
                    provider="tencent.get_hot_stocks",
                    target_keys=["hot_rank_top30"],
                    hot_rank_count=len(hot_stocks),
                    fallback_used=True,
                    upstream_error=primary_error,
                )
            else:
                results["hot_rank_top30"] = []
                data_status["热度前三十个股"] = False
                emit("   ❌ 所有热榜数据源失败")
                _append_log(
                    module_logs,
                    "request.hot_rank.fallback",
                    "degraded",
                    "腾讯热榜兜底返回空",
                    provider="tencent.get_hot_stocks",
                    target_keys=["hot_rank_top30"],
                    fallback_used=True,
                    upstream_error=primary_error,
                )
        except Exception as error:
            results["hot_rank_top30"] = []
            data_status["热度前三十个股"] = False
            emit(f"   ❌ 腾讯热榜兜底失败: {error}")
            _append_log(
                module_logs,
                "request.hot_rank.fallback",
                "error",
                "腾讯热榜兜底失败",
                provider="tencent.get_hot_stocks",
                target_keys=["hot_rank_top30"],
                error=str(error),
                fallback_used=True,
                upstream_error=primary_error,
            )

    emit("  5️⃣.5️⃣ 获取整合热榜数据（新数据源）...")
    try:
        integrated_hot_list, tag_distribution, status_distribution, high_lianban_stocks = get_integrated_hot_list(limit=100)
        if integrated_hot_list:
            results["integrated_hot_list"] = integrated_hot_list
            results["tag_distribution"] = tag_distribution
            results["status_distribution"] = status_distribution
            results["high_lianban_stocks"] = high_lianban_stocks
            data_status["整合热榜"] = True
            step_status["整合热榜获取"] = True
            emit(f"   ✅ 整合热榜成功: {len(integrated_hot_list)} 只")
            emit(f"   ✅ 板块标签分布: {len(tag_distribution)} 个板块，{len(status_distribution)} 个状态标签")
            if high_lianban_stocks:
                emit(f"   ✅ 高位连板股: {len(high_lianban_stocks)} 只（非ST股，10天以上）")
        else:
            results["integrated_hot_list"] = []
            results["tag_distribution"] = {}
            results["status_distribution"] = {}
            data_status["整合热榜"] = False
            emit("   ⚠️ 整合热榜返回空")
        _append_log(
            module_logs,
            "request.integrated_hot_rank",
            "success" if data_status.get("整合热榜") else "degraded",
            "已处理整合热榜请求",
            integrated_count=len(results.get("integrated_hot_list", [])),
            provider="hot_list_integrated.get_integrated_hot_list",
            target_keys=["integrated_hot_list", "tag_distribution", "status_distribution", "high_lianban_stocks"],
        )
    except Exception as error:
        results["integrated_hot_list"] = []
        results["tag_distribution"] = {}
        results["status_distribution"] = {}
        data_status["整合热榜"] = False
        emit(f"   ⚠️ 整合热榜失败: {error}")
        _append_log(
            module_logs,
            "request.integrated_hot_rank",
            "error",
            "整合热榜请求失败",
            provider="hot_list_integrated.get_integrated_hot_list",
            target_keys=["integrated_hot_list", "tag_distribution", "status_distribution", "high_lianban_stocks"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }


def collect_market_activity_sector_snapshot_request_bundle(
    target_date,
    *,
    fetch_hot_plate,
    tencent,
    get_sector_change_from_iwencai,
    get_turnover_rank_from_iwencai,
    timer,
    emit,
    current_dates=None,
):
    results = {}
    data_status = {}
    step_status = {
        "板块热榜获取": False,
        "行业资金流向获取": False,
        "板块涨跌幅排行获取": False,
        "成交额排名获取": False,
    }
    module_logs = []

    emit("  6️⃣ 获取板块热榜（同花顺）...")
    try:
        hot_plates = fetch_hot_plate()
        if hot_plates:
            results["hot_plates"] = hot_plates
            data_status["板块热榜"] = True
            step_status["板块热榜获取"] = True
            elapsed, _ = timer.record("板块热榜获取", 6)
            emit(f"   ✅ 板块热榜成功: {len(hot_plates)} 条 [⏱ {elapsed:.2f}s]")
        else:
            results["hot_plates"] = []
            data_status["板块热榜"] = False
            emit("   ❌ 板块热榜返回空")
        _append_log(
            module_logs,
            "request.hot_plates",
            "success" if data_status.get("板块热榜") else "degraded",
            "已处理板块热榜请求",
            provider="ths_hot_list.fetch_hot_plate",
            target_keys=["hot_plates"],
            plate_count=len(results.get("hot_plates", [])),
        )
    except Exception as error:
        results["hot_plates"] = []
        data_status["板块热榜"] = False
        emit(f"   ❌ 板块热榜失败: {error}")
        _append_log(
            module_logs,
            "request.hot_plates",
            "error",
            "板块热榜请求失败",
            provider="ths_hot_list.fetch_hot_plate",
            target_keys=["hot_plates"],
            error=str(error),
        )

    emit("  7️⃣ 获取行业资金流向...")
    try:
        today, yesterday = current_dates or (None, None)
        if target_date == today or target_date == yesterday:
            inflow = tencent.get_sector_fund_flow(flow_type="in", limit=50)
            outflow = tencent.get_sector_fund_flow(flow_type="out", limit=50)
            results["sector_fund_flow"] = {"inflow": inflow, "outflow": outflow}
            if inflow or outflow:
                data_status["行业资金流向"] = True
                step_status["行业资金流向获取"] = True
                elapsed, _ = timer.record("行业资金流向获取", 7)
                emit(f"   ✅ 腾讯财经成功: 净流入{len(inflow)}条, 净流出{len(outflow)}条 [⏱ {elapsed:.2f}s]")
            else:
                results["sector_fund_flow"] = {"inflow": [], "outflow": []}
                data_status["行业资金流向"] = False
                emit("   ❌ 行业资金流向返回空")
        else:
            results["sector_fund_flow"] = {
                "inflow": [],
                "outflow": [],
                "is_historical": True,
                "target_date": target_date,
            }
            data_status["行业资金流向"] = True
            step_status["行业资金流向获取"] = True
            timer.record("行业资金流向获取", 7)
            emit(f"   ⚠️ 历史({target_date})板块资金流向暂不支持，将在报告中提示")
        _append_log(
            module_logs,
            "request.sector_fund_flow",
            "success" if data_status.get("行业资金流向") else "degraded",
            "已处理行业资金流向请求",
            provider="tencent.get_sector_fund_flow",
            target_keys=["sector_fund_flow"],
            historical=bool(results.get("sector_fund_flow", {}).get("is_historical")),
        )
    except Exception as error:
        results["sector_fund_flow"] = {"inflow": [], "outflow": []}
        data_status["行业资金流向"] = False
        emit(f"   ❌ 行业资金流向失败: {error}")
        _append_log(
            module_logs,
            "request.sector_fund_flow",
            "error",
            "行业资金流向请求失败",
            provider="tencent.get_sector_fund_flow",
            target_keys=["sector_fund_flow"],
            error=str(error),
        )

    emit("  8️⃣ 获取板块涨跌幅排行（同花顺问财API）...")
    try:
        sector_up = get_sector_change_from_iwencai(rank_type="up", limit=10)
        sector_down = get_sector_change_from_iwencai(rank_type="down", limit=10)
        results["sector_change_up"] = sector_up or []
        results["sector_change_down"] = sector_down or []
        data_status["板块涨幅排行"] = bool(sector_up)
        data_status["板块跌幅排行"] = bool(sector_down)
        if sector_up or sector_down:
            step_status["板块涨跌幅排行获取"] = True
            elapsed, _ = timer.record("板块涨跌幅排行获取", 8)
            emit(f"   ✅ 板块涨跌幅排行成功 [⏱ {elapsed:.2f}s]")
        else:
            emit("   ❌ 板块涨跌幅排行为空")
        _append_log(
            module_logs,
            "request.sector_change_rank",
            "success" if step_status.get("板块涨跌幅排行获取") else "degraded",
            "已处理板块涨跌幅排行请求",
            provider="iwencai.sector_change_rank",
            target_keys=["sector_change_up", "sector_change_down"],
            up_count=len(results.get("sector_change_up", [])),
            down_count=len(results.get("sector_change_down", [])),
        )
    except Exception as error:
        results["sector_change_up"] = []
        results["sector_change_down"] = []
        data_status["板块涨幅排行"] = False
        data_status["板块跌幅排行"] = False
        timer.record("板块涨跌幅排行获取(失败)", 8)
        emit(f"   ❌ 板块涨跌幅排行失败: {error}")
        _append_log(
            module_logs,
            "request.sector_change_rank",
            "error",
            "板块涨跌幅排行请求失败",
            provider="iwencai.sector_change_rank",
            target_keys=["sector_change_up", "sector_change_down"],
            error=str(error),
        )

    emit("  9️⃣ 获取成交额排名（iwencai API）...")
    try:
        turnover_rank = get_turnover_rank_from_iwencai(limit=50, target_date=target_date)
        if turnover_rank:
            over_100b = [stock for stock in turnover_rank if stock.get("turnover", 0) > 100]
            results["turnover_rank"] = turnover_rank
            results["turnover_over_100b"] = over_100b
            data_status["成交额排名"] = True
            step_status["成交额排名获取"] = True
            elapsed, _ = timer.record("成交额排名获取", 9)
            emit(f"   ✅ 成交额排名成功: {len(turnover_rank)} 条，>100亿: {len(over_100b)} 只 [⏱ {elapsed:.2f}s]")
        else:
            results["turnover_rank"] = []
            results["turnover_over_100b"] = []
            data_status["成交额排名"] = False
            emit("   ❌ 成交额排名返回空")
        _append_log(
            module_logs,
            "request.turnover_rank",
            "success" if data_status.get("成交额排名") else "degraded",
            "已处理成交额排名请求",
            provider="iwencai.turnover_rank",
            target_keys=["turnover_rank", "turnover_over_100b"],
            turnover_count=len(results.get("turnover_rank", [])),
            over_100b_count=len(results.get("turnover_over_100b", [])),
        )
    except Exception as error:
        results["turnover_rank"] = []
        results["turnover_over_100b"] = []
        data_status["成交额排名"] = False
        emit(f"   ❌ 成交额排名失败: {error}")
        _append_log(
            module_logs,
            "request.turnover_rank",
            "error",
            "成交额排名请求失败",
            provider="iwencai.turnover_rank",
            target_keys=["turnover_rank", "turnover_over_100b"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }


def _normalize_lhb_code(fs_code):
    return str(fs_code or "").replace(".SZ", "").replace(".SH", "").replace(".BJ", "")


def _resolve_lhb_sector(code, existing_results=None):
    existing_results = existing_results or {}
    for pool_key in ("zt_pool", "dt_pool"):
        for stock in existing_results.get(pool_key, []) or []:
            if stock.get("代码") == code:
                return stock.get("所属行业", "未知")
    return "未知"


def collect_market_activity_capital_snapshot_request_bundle(
    target_date,
    *,
    limit_up_df,
    existing_results,
    fetch_lhb_rows,
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {
        "连板梯队提取": False,
        "龙虎榜数据获取": False,
    }
    module_logs = []

    emit("  1️⃣3️⃣ 从涨停池提取连板梯队... (依赖: 步骤4)")
    try:
        lianban_data = []
        if limit_up_df is not None and not limit_up_df.empty:
            for _, row in limit_up_df.iterrows():
                lianban_days = row.get("连板数", 1)
                if lianban_days < 2:
                    continue
                first_limit_time_raw = str(row.get("首次封板时间", "")).strip()
                if first_limit_time_raw and len(first_limit_time_raw) >= 6:
                    first_limit_time = f"{first_limit_time_raw[:2]}:{first_limit_time_raw[2:4]}:{first_limit_time_raw[4:6]}"
                elif first_limit_time_raw and len(first_limit_time_raw) == 4:
                    first_limit_time = f"{first_limit_time_raw[:2]}:{first_limit_time_raw[2:4]}:00"
                else:
                    first_limit_time = "15:00:00"
                lianban_data.append(
                    {
                        "code": row["代码"],
                        "name": row["名称"],
                        "lianban_days": lianban_days,
                        "change_pct": row.get("涨跌幅", 0),
                        "turnover": row.get("成交额", 0),
                        "sector": row.get("所属行业", "未知"),
                        "reason": row.get("涨停统计", ""),
                        "open_price": row.get("开盘价", 0),
                        "close_price": row.get("最新价", 0),
                        "high_price": row.get("最高价", 0),
                        "low_price": row.get("最低价", 0),
                        "first_limit_time": first_limit_time,
                    }
                )
        lianban_data.sort(key=lambda item: (-item["lianban_days"], item["first_limit_time"]))
        results["lianban_data"] = lianban_data
        if lianban_data:
            step_status["连板梯队提取"] = True
            emit(f"   ✅ 连板梯队提取成功: {len(lianban_data)} 只（最高{lianban_data[0]['lianban_days']}连板）")
        else:
            emit("   ⚠️ 连板梯队数据为空（无连板股）")
        _append_log(
            module_logs,
            "request.lianban_snapshot",
            "success",
            "已处理连板梯队请求",
            provider="akshare.limit_up_pool",
            target_keys=["lianban_data"],
            lianban_count=len(lianban_data),
        )
    except Exception as error:
        results["lianban_data"] = []
        emit(f"   ⚠️ 连板梯队提取失败: {error}")
        _append_log(
            module_logs,
            "request.lianban_snapshot",
            "error",
            "连板梯队请求失败",
            provider="akshare.limit_up_pool",
            target_keys=["lianban_data"],
            error=str(error),
        )

    emit("  1️⃣3️⃣ 获取龙虎榜数据...")
    try:
        lhb_rows = fetch_lhb_rows(target_date)
        grouped = {}
        for row in lhb_rows or []:
            code = _normalize_lhb_code(row.get("fs_code", ""))
            if not code:
                continue
            bucket = grouped.setdefault(
                code,
                {
                    "代码": code,
                    "net_buy_amount": 0,
                    "close_price": row.get("close_price", 0),
                    "change_rate": row.get("change_rate", 0),
                    "fs_code": row.get("fs_code", ""),
                },
            )
            bucket["net_buy_amount"] += row.get("net_buy_amount", 0) or 0
            bucket["close_price"] = bucket.get("close_price") or row.get("close_price", 0)
            bucket["change_rate"] = bucket.get("change_rate") or row.get("change_rate", 0)

        grouped_rows = list(grouped.values())
        buy_rows = sorted(grouped_rows, key=lambda item: item.get("net_buy_amount", 0), reverse=True)[:10]
        sell_rows = sorted(grouped_rows, key=lambda item: item.get("net_buy_amount", 0))[:10]

        net_buy_top10 = []
        for rank, row in enumerate(buy_rows, 1):
            code = row["代码"]
            net_buy_top10.append(
                {
                    "rank": rank,
                    "code": code,
                    "name": "",
                    "net_buy_amount_yi": (row.get("net_buy_amount", 0) or 0) / 1e8,
                    "change_pct": row.get("change_rate", 0),
                    "zt_status": "正常",
                    "sector": _resolve_lhb_sector(code, existing_results),
                }
            )

        net_sell_top10 = []
        for rank, row in enumerate(sell_rows, 1):
            code = row["代码"]
            net_sell_top10.append(
                {
                    "rank": rank,
                    "code": code,
                    "name": "",
                    "net_buy_amount_yi": (row.get("net_buy_amount", 0) or 0) / 1e8,
                    "change_pct": row.get("change_rate", 0),
                    "zt_status": "正常",
                    "sector": _resolve_lhb_sector(code, existing_results),
                }
            )

        results["lhb_net_buy_top10"] = net_buy_top10
        results["lhb_net_sell_top10"] = net_sell_top10
        results["lhb_analysis"] = grouped_rows
        step_status["龙虎榜数据获取"] = True
        timer.record("龙虎榜数据获取", 13)
        emit(f"   ✅ 龙虎榜: 净买{len(net_buy_top10)}只/净卖{len(net_sell_top10)}只（已去重）")
        _append_log(
            module_logs,
            "request.lhb_snapshot",
            "success",
            "已处理龙虎榜请求",
            provider="finshare.get_lhb",
            target_keys=["lhb_net_buy_top10", "lhb_net_sell_top10", "lhb_analysis"],
            lhb_count=len(grouped_rows),
        )
    except Exception as error:
        results["lhb_net_buy_top10"] = []
        results["lhb_net_sell_top10"] = []
        results["lhb_analysis"] = []
        emit(f"   ⚠️ 龙虎榜获取失败: {error}")
        _append_log(
            module_logs,
            "request.lhb_snapshot",
            "error",
            "龙虎榜请求失败",
            provider="finshare.get_lhb",
            target_keys=["lhb_net_buy_top10", "lhb_net_sell_top10", "lhb_analysis"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }


def _normalize_quote_code(raw_code):
    code = str(raw_code or "")
    for prefix in (".SZ", ".SS", ".SH", "sz", "sh", "bj"):
        code = code.replace(prefix, "")
    return code


def collect_market_activity_stock_quote_request_bundle(
    *,
    existing_results,
    fetch_stock_batch_info,
    timer,
    emit,
):
    existing_results = existing_results or {}
    results = {}
    module_logs = []

    emit("\n📊 批量获取股票完整信息（涨跌幅、最高价、最低价、开盘价、收盘价）...")
    all_stock_codes = set()

    for stock in existing_results.get("hot_rank_top30", []) or []:
        code = _normalize_quote_code(stock.get("code", ""))
        if code:
            all_stock_codes.add(code)

    for stock in existing_results.get("turnover_rank", []) or []:
        code = _normalize_quote_code(stock.get("code", ""))
        if code:
            all_stock_codes.add(code)

    for key in ("lhb_net_buy_top10", "lhb_net_sell_top10", "lianban_data"):
        for stock in existing_results.get(key, []) or []:
            code = _normalize_quote_code(stock.get("code", ""))
            if code:
                all_stock_codes.add(code)

    if all_stock_codes:
        try:
            stock_full_info = fetch_stock_batch_info(list(all_stock_codes))
            results["stock_full_info"] = stock_full_info
            elapsed, _ = timer.record("批量获取股票信息", 15)
            emit(f"   ✅ 成功获取 {len(stock_full_info)} 只股票的完整信息 [⏱ {elapsed:.2f}s]")
            _append_log(
                module_logs,
                "request.stock_quotes",
                "success",
                "已处理批量股票补数请求",
                provider="tencent.get_stock_batch_info",
                target_keys=["stock_full_info", "lhb_net_buy_top10", "lhb_net_sell_top10"],
                stock_count=len(stock_full_info),
            )
        except Exception as error:
            results["stock_full_info"] = {}
            timer.record("批量获取股票信息(失败)", 15)
            emit(f"   ⚠️ 批量查询失败: {error}")
            _append_log(
                module_logs,
                "request.stock_quotes",
                "error",
                "批量股票补数请求失败",
                provider="tencent.get_stock_batch_info",
                target_keys=["stock_full_info", "lhb_net_buy_top10", "lhb_net_sell_top10"],
                error=str(error),
            )
    else:
        results["stock_full_info"] = {}
        timer.record("批量获取股票信息(跳过)", 15)
        _append_log(
            module_logs,
            "request.stock_quotes",
            "degraded",
            "无股票代码可用于批量补数",
            provider="tencent.get_stock_batch_info",
            target_keys=["stock_full_info"],
        )

    stock_full_info_for_fill = results.get("stock_full_info", {}) or {}
    if stock_full_info_for_fill:
        for lhb_list_key in ("lhb_net_buy_top10", "lhb_net_sell_top10"):
            patched_rows = []
            for item in existing_results.get(lhb_list_key, []) or []:
                patched = dict(item)
                code = _normalize_quote_code(patched.get("code", ""))
                if not patched.get("name") and code and code in stock_full_info_for_fill:
                    info = stock_full_info_for_fill[code]
                    name_from_info = info.get("name") or info.get("名称", "")
                    if name_from_info:
                        patched["name"] = name_from_info
                patched_rows.append(patched)
            results[lhb_list_key] = patched_rows

    return {
        "results": results,
        "module_logs": module_logs,
    }
