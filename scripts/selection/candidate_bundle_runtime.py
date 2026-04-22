def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "selection.candidate_bundle_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_candidate_bundle_contract(
    data,
    exit_analysis,
    candidates,
    watchlist,
    abnormal_watch_map,
    dragon_stocks,
    zt_pool_by_sector=None,
    gem_breathing_candidates=None,
    target_date="",
    *,
    normalize_stock_code,
    get_abnormal_rank_adjustment,
    split_candidates_by_mainline,
    build_gem_observation_pool,
    build_sector_trend_snapshot,
    build_extreme_conviction_list,
):
    zt_pool_by_sector = zt_pool_by_sector or {}
    gem_breathing_candidates = gem_breathing_candidates or []
    logs = []

    lianban_data = data.get("lianban_data", {})
    lb_stocks_map = {}
    if lianban_data and "stocks" in lianban_data:
        for lb_stock in lianban_data["stocks"]:
            code = normalize_stock_code(lb_stock.get("code", ""))
            lb_stocks_map[code] = {
                "连板数": lb_stock.get("连板数", 1),
                "昨日涨停价": lb_stock.get("昨日涨停价", 0),
                "涨停原因": lb_stock.get("涨停原因", ""),
            }

    evaluated_stocks = []
    for stock in watchlist:
        item = dict(stock)
        code = item.get("code", "")
        base_score = item.get("score", 0)
        abnormal_item = abnormal_watch_map.get(code, {})
        abnormal_bonus, abnormal_summary, abnormal_rule = get_abnormal_rank_adjustment(abnormal_item)
        lb_info = lb_stocks_map.get(code, {})
        lb_count = lb_info.get("连板数", 1)
        tomorrow_strength = base_score

        if lb_count >= 3:
            tomorrow_strength += 25
            core_level = "🔥🔥 高标核心"
            tmr_forecast = f"{lb_count}进{lb_count+1}，若竞价高开可能继续"
        elif lb_count == 2:
            tomorrow_strength += 20
            core_level = "🔥 连板核心"
            tmr_forecast = "2进3，观察竞价是否超预期"
        elif lb_count == 1 and base_score >= 70:
            tomorrow_strength += 15
            core_level = "⭐ 首板强芯"
            tmr_forecast = "首板形态好，明日有连板预期"
        elif base_score >= 50:
            core_level = "✓ 溢价候选"
            tmr_forecast = "明日可能高开溢价"
        else:
            core_level = "○ 观察备选"
            tmr_forecast = "需看明日竞价强弱"

        tomorrow_strength += abnormal_bonus
        if abnormal_bonus >= 18 and "高标核心" not in core_level and "连板核心" not in core_level:
            core_level = "🔥 异动抗跌核心"
        elif abnormal_bonus >= 10 and core_level in ["✓ 溢价候选", "○ 观察备选"]:
            core_level = "⭐ 抗跌观察芯"
        elif abnormal_bonus < 0:
            core_level = "○ 转弱观察"

        if abnormal_item:
            if abnormal_item.get("follow_state") == "跌不下去":
                tmr_forecast = f"{tmr_forecast}；异动后承接强，优先等60分钟确认"
            elif abnormal_item.get("follow_state") == "缩量消化":
                tmr_forecast = f"{tmr_forecast}；异动后缩量消化，可继续跟"
            elif abnormal_item.get("follow_state") == "已经转弱":
                tmr_forecast = f"{tmr_forecast}；但异动后承接差，只能降级观察"
            elif abnormal_item.get("follow_state") == "新异动待观察":
                tmr_forecast = f"{tmr_forecast}；异动刚出现，先看次日承接"

        item["tomorrow_strength"] = tomorrow_strength
        item["core_level"] = core_level
        item["tmr_forecast"] = tmr_forecast
        item["连板数"] = lb_count
        item["abnormal_bonus"] = abnormal_bonus
        item["abnormal_summary"] = abnormal_summary
        item["abnormal_rule"] = abnormal_rule
        item["abnormal_follow_state"] = abnormal_item.get("follow_state", "")
        item["abnormal_type"] = abnormal_item.get("abnormal_type", "")
        item["abnormal_setup_signal_id"] = abnormal_item.get("setup_signal_id", "")
        item["abnormal_setup_signal_label"] = abnormal_item.get("setup_signal_label", "")
        item["abnormal_setup_signal_phase"] = abnormal_item.get("setup_signal_phase", "")
        item["abnormal_is_degraded_snapshot"] = bool(abnormal_item.get("is_degraded_snapshot", False))
        evaluated_stocks.append(item)

    evaluated_stocks.sort(
        key=lambda item: (
            item.get("tomorrow_strength", 0),
            item.get("abnormal_bonus", 0),
            item.get("score", 0),
        ),
        reverse=True,
    )
    _append_log(logs, "candidate_scoring", "success", "已完成候选评分与排序", evaluated_count=len(evaluated_stocks))

    primary_mainline = str(exit_analysis.get("sector_name", "") or "").strip()
    if primary_mainline:
        mainline_evaluated_stocks, crossline_evaluated_stocks = split_candidates_by_mainline(
            evaluated_stocks,
            primary_mainline,
        )
        if not mainline_evaluated_stocks:
            mainline_evaluated_stocks = list(evaluated_stocks)
            crossline_evaluated_stocks = []
    else:
        mainline_evaluated_stocks = list(evaluated_stocks)
        crossline_evaluated_stocks = []

    crossline_observation_stocks = crossline_evaluated_stocks[:4]
    gem_observation_stocks = build_gem_observation_pool(gem_breathing_candidates, target_date=target_date)

    core_stocks = mainline_evaluated_stocks[:3] if len(mainline_evaluated_stocks) >= 3 else mainline_evaluated_stocks
    secondary_stocks = mainline_evaluated_stocks[3:6] if len(mainline_evaluated_stocks) >= 6 else mainline_evaluated_stocks[3:]
    ignored_stocks = mainline_evaluated_stocks[6:]
    crossline_core_stocks = crossline_observation_stocks[:2] if len(crossline_observation_stocks) >= 2 else crossline_observation_stocks
    crossline_secondary_stocks = crossline_observation_stocks[2:4] if len(crossline_observation_stocks) >= 4 else crossline_observation_stocks[2:]
    crossline_ignored_stocks = crossline_evaluated_stocks[4:]
    sector_trend_snapshot = build_sector_trend_snapshot(
        candidates,
        watchlist,
        evaluated_stocks,
        dragon_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        top_n=5,
    )
    extreme_conviction_list = build_extreme_conviction_list(
        evaluated_stocks,
        exit_analysis.get("sector_name", ""),
        sector_snapshot=sector_trend_snapshot,
        top_n=3,
    )
    _append_log(logs, "candidate_grouping", "success", "已完成主线/跨线/创业板分组", mainline_name=primary_mainline)

    return {
        "evaluated_stocks": evaluated_stocks,
        "mainline_name": primary_mainline,
        "mainline_evaluated_stocks": mainline_evaluated_stocks,
        "core_stocks": core_stocks,
        "secondary_stocks": secondary_stocks,
        "ignored_stocks": ignored_stocks,
        "crossline_evaluated_stocks": crossline_evaluated_stocks,
        "crossline_observation_stocks": crossline_observation_stocks,
        "gem_observation_stocks": gem_observation_stocks,
        "crossline_core_stocks": crossline_core_stocks,
        "crossline_secondary_stocks": crossline_secondary_stocks,
        "crossline_ignored_stocks": crossline_ignored_stocks,
        "sector_trend_snapshot": sector_trend_snapshot,
        "extreme_conviction_list": extreme_conviction_list,
        "module_logs": logs,
    }
