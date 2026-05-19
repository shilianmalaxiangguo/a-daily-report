__all__ = [
    "build_candidate_bundle_contract",
    "build_step2_candidate_bundle",
]

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
    "待补充板块",
    "待补充",
    "其他",
    "其它",
    "-",
}


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


def _is_valid_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_SECTOR_LABELS)


def _build_code_map(items, normalize_stock_code, code_keys):
    mapped = {}
    if isinstance(items, dict):
        for code, item in items.items():
            if isinstance(item, dict):
                normalized = normalize_stock_code(item.get("code") or code)
                if normalized:
                    mapped[normalized] = item
        return mapped
    for item in items or []:
        if not isinstance(item, dict):
            continue
        code = ""
        for key in code_keys:
            code = item.get(key)
            if code:
                break
        normalized = normalize_stock_code(code)
        if normalized:
            mapped[normalized] = item
    return mapped


def _related_plate_names(related_plates):
    names = []
    for plate in related_plates or []:
        if not isinstance(plate, dict):
            continue
        name = str(plate.get("plate_name") or plate.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _first_valid_text(values):
    for value in values or []:
        if _is_valid_sector_label(value):
            return str(value).strip()
    return ""


def _infer_sector_from_reason(text):
    text = str(text or "")
    if "长鑫" in text or "国产芯片" in text:
        return "国产芯片"
    keyword_groups = [
        ("半导体", ("长鑫", "存储", "芯片", "光刻", "晶圆", "半导体")),
        ("算力", ("Token工厂", "昇腾", "算力", "服务器", "数据中心", "液冷")),
        ("机器人", ("机器人", "减速器", "智能体", "机器视觉")),
        ("商业航天", ("商业航天", "卫星", "航天", "火箭")),
        ("低空经济", ("低空", "无人机", "eVTOL")),
        ("家用电器", ("小家电", "家用电器", "空调")),
        ("消费电子", ("MiniLED", "车载背光", "VR背光", "背光显示", "消费电子", "无线耳机", "苹果产业链")),
        ("食品饮料", ("葡萄酒", "白兰地", "保健酒", "食品", "饮料")),
        ("天然气", ("天然气", "页岩气", "燃气")),
        ("股权转让", ("股权转让", "资产重组", "并购重组", "控制权")),
    ]
    for sector, markers in keyword_groups:
        if any(marker in text for marker in markers):
            return sector
    return ""


def _first_valid_stock_plate(item):
    return _first_valid_text(
        list(item.get("xuangubao_related_plate_names") or [])
        + list(item.get("concepts") or [])
        + list(item.get("plates") or [])
        + list(item.get("related_plates") or [])
        + [
            _infer_sector_from_reason(
                " / ".join(
                    str(item.get(key) or "")
                    for key in ("reason", "涨停统计", "xuangubao_stock_reason", "abnormal_summary", "volume_summary")
                )
            ),
            item.get("industry"),
            item.get("所属行业"),
            item.get("sector_name"),
        ]
    )


def _enrich_candidate_item(item, code, stock_info_map, volume_anomaly_map):
    stock_info = stock_info_map.get(code, {}) or {}
    for key in ("open", "high", "low", "close", "price", "yclose", "change_pct"):
        if key in stock_info and item.get(key) in (None, ""):
            item[key] = stock_info.get(key)
    for source_key, target_key in (("industry", "industry"), ("所属行业", "所属行业"), ("sector_name", "sector_name")):
        if stock_info.get(source_key) and item.get(target_key) in (None, ""):
            item[target_key] = stock_info.get(source_key)

    volume_anomaly = volume_anomaly_map.get(code, {}) or {}
    reason = volume_anomaly.get("reason")
    if reason and not item.get("volume_summary"):
        item["volume_summary"] = reason


def _enrich_candidate_with_xuangubao_reason(item, code, xuangubao_reason_map):
    reason = xuangubao_reason_map.get(code, {}) or {}
    if not reason:
        return
    related_plates = reason.get("related_plates", []) or []
    item["xuangubao_stock_reason"] = reason.get("stock_reason", "")
    item["xuangubao_related_plates"] = related_plates
    item["xuangubao_related_plate_names"] = _related_plate_names(related_plates)
    item["xuangubao_limit_up_days"] = reason.get("limit_up_days", 0)


def _enrich_candidate_with_stock_risk(item, code, stock_risk_map):
    risk = (stock_risk_map or {}).get(code, {}) or {}
    if not risk:
        return
    item["stock_risk"] = risk
    risk_flags = risk.get("risk_flags") or []
    if risk_flags:
        item["news_risk_flags"] = list(dict.fromkeys(list(item.get("news_risk_flags") or []) + list(risk_flags)))
    risk_summary = str(risk.get("risk_summary") or "").strip()
    if risk_summary and not item.get("news_risk_summary"):
        item["news_risk_summary"] = risk_summary
    risk_events = list(risk.get("risk_events") or [])
    if risk_events:
        item["risk_events"] = list(item.get("risk_events") or []) + risk_events


def _normalize_candidate_sector(item):
    sector = str(item.get("sector") or "").strip()
    if _is_valid_sector_label(sector):
        return
    replacement = _first_valid_stock_plate(item)
    if replacement:
        item["sector"] = replacement


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
    stock_info_map = _build_code_map(data.get("stock_full_info", {}), normalize_stock_code, ("code", "代码", "stock_code"))
    volume_anomaly_map = _build_code_map(data.get("volume_anomalies", []), normalize_stock_code, ("stock_code", "code", "代码"))
    stock_risk_map = _build_code_map(data.get("stock_risk_map", {}), normalize_stock_code, ("code", "stock_code", "ts_code", "代码"))
    xuangubao_reason_map = _build_code_map(
        (data.get("xuangubao_data") or {}).get("xuangubao_limit_up_reasons", []),
        normalize_stock_code,
        ("symbol", "code", "stock_code"),
    )

    lianban_data = data.get("lianban_data", {})
    lb_stocks_map = {}
    if isinstance(lianban_data, dict) and "stocks" in lianban_data:
        lianban_stocks = lianban_data["stocks"]
    elif isinstance(lianban_data, list):
        lianban_stocks = lianban_data
    else:
        lianban_stocks = []
    for lb_stock in lianban_stocks:
        if isinstance(lb_stock, dict):
            code = normalize_stock_code(lb_stock.get("code", ""))
            lb_stocks_map[code] = {
                "连板数": lb_stock.get("连板数", lb_stock.get("lianban_days", 0)),
                "昨日涨停价": lb_stock.get("昨日涨停价", 0),
                "涨停原因": lb_stock.get("涨停原因", lb_stock.get("reason", "")),
                "sector": lb_stock.get("sector") or lb_stock.get("所属行业") or "",
                "plates": list(lb_stock.get("plates") or []),
            }

    evaluated_stocks = []
    for stock in watchlist:
        item = dict(stock)
        code = item.get("code", "")
        normalized_code = normalize_stock_code(code)
        _enrich_candidate_item(item, normalized_code, stock_info_map, volume_anomaly_map)
        _enrich_candidate_with_xuangubao_reason(item, normalized_code, xuangubao_reason_map)
        _enrich_candidate_with_stock_risk(item, normalized_code, stock_risk_map)
        _normalize_candidate_sector(item)
        base_score = item.get("score", 0)
        abnormal_item = abnormal_watch_map.get(code, {}) or abnormal_watch_map.get(normalized_code, {})
        abnormal_bonus, abnormal_summary, abnormal_rule = get_abnormal_rank_adjustment(abnormal_item)
        lb_info = lb_stocks_map.get(code, {})
        if item.get("reason") in (None, "") and lb_info.get("涨停原因"):
            item["reason"] = lb_info.get("涨停原因")
        if lb_info.get("sector") and item.get("sector") in (None, ""):
            item["sector"] = lb_info.get("sector")
        if lb_info.get("plates") and not item.get("plates"):
            item["plates"] = lb_info.get("plates")
        _normalize_candidate_sector(item)
        lb_count = lb_info.get("连板数", 0)
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
                tmr_forecast = f"{tmr_forecast}；异动后承接强，优先看竞价表态、开盘承接和结构确认"
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


def build_step2_candidate_bundle(
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
    helpers=None,
):
    helpers = helpers or {}
    return build_candidate_bundle_contract(
        data,
        exit_analysis,
        candidates,
        watchlist,
        abnormal_watch_map,
        dragon_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        gem_breathing_candidates=gem_breathing_candidates,
        target_date=target_date,
        normalize_stock_code=helpers["normalize_stock_code"],
        get_abnormal_rank_adjustment=helpers["get_abnormal_rank_adjustment"],
        split_candidates_by_mainline=helpers["split_candidates_by_mainline"],
        build_gem_observation_pool=helpers["build_gem_observation_pool"],
        build_sector_trend_snapshot=helpers["build_sector_trend_snapshot"],
        build_extreme_conviction_list=helpers["build_extreme_conviction_list"],
    )
