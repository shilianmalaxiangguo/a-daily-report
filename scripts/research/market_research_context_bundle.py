from selection.candlestick_signature import infer_signature_big_yangline

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
            "module": "research.market_research_context_bundle",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _merge_text_list(*values):
    merged = []
    seen = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            items = value
        elif value:
            items = [value]
        else:
            items = []
        for item in items:
            text = str(item or "").strip()
            if text and text not in seen:
                seen.add(text)
                merged.append(text)
    return merged


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


def _is_valid_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_SECTOR_LABELS)


def _infer_sector_from_reason(text):
    text = str(text or "")
    if "长鑫" in text or "国产芯片" in text:
        return "国产芯片"
    keyword_groups = [
        ("算力", ("Token工厂", "昇腾", "算力", "服务器", "数据中心", "液冷", "东数西算")),
        ("机器人", ("机器人", "减速器", "智能体", "机器视觉", "智能制造", "智能物流")),
        ("商业航天", ("商业航天", "卫星", "航天", "火箭")),
        ("低空经济", ("低空", "无人机", "eVTOL")),
        ("家用电器", ("小家电", "家用电器", "空调")),
        ("消费电子", ("MiniLED", "车载背光", "VR背光", "背光显示", "消费电子", "无线耳机", "苹果产业链")),
        ("食品饮料", ("葡萄酒", "白兰地", "保健酒", "食品", "饮料")),
        ("天然气", ("天然气", "页岩气", "燃气")),
        ("资产重组", ("股权转让", "资产重组", "并购重组", "控制权", "重整", "实控人变更", "国资入主", "资产置换")),
        ("环保", ("环保", "水务")),
        ("汽车产业链", ("汽车拆解", "汽车", "新能源汽车")),
    ]
    for sector, markers in keyword_groups:
        if any(marker in text for marker in markers):
            return sector
    return ""


def _stock_reason_text(stock):
    return " / ".join(
        str(stock.get(key) or "")
        for key in (
            "涨停统计",
            "涨停原因",
            "reason",
            "stock_reason",
            "xuangubao_stock_reason",
            "abnormal_summary",
            "volume_summary",
        )
    )


def _build_xuangubao_plate_map(data, normalize_stock_code):
    mapped = {}
    reasons = ((data or {}).get("xuangubao_data") or {}).get("xuangubao_limit_up_reasons", []) or []
    for item in reasons:
        if not isinstance(item, dict):
            continue
        code = normalize_stock_code(item.get("symbol") or item.get("code") or item.get("stock_code") or "")
        if not code:
            continue
        for plate in item.get("related_plates") or []:
            if not isinstance(plate, dict):
                continue
            name = str(plate.get("plate_name") or plate.get("name") or "").strip()
            if _is_valid_sector_label(name):
                mapped[code] = name
                break
        if code not in mapped:
            inferred = _infer_sector_from_reason(_stock_reason_text(item))
            if inferred:
                mapped[code] = inferred
    return mapped


def _resolve_stock_sector(stock, code, xuangubao_plate_map):
    for value in (stock.get("sector", ""), stock.get("所属行业", ""), stock.get("所属板块", ""), stock.get("industry", "")):
        if _is_valid_sector_label(value):
            return str(value).strip()
    sector = xuangubao_plate_map.get(code, "")
    if _is_valid_sector_label(sector):
        return sector
    inferred = _infer_sector_from_reason(_stock_reason_text(stock))
    if inferred:
        return inferred
    return "未归类"


def _sanitize_sector_bucket_map(sector_map, xuangubao_plate_map, normalize_stock_code, stock_lookup=None):
    stock_lookup = stock_lookup or {}
    sanitized = {}
    for sector, stocks in (sector_map or {}).items():
        for stock in stocks or []:
            if not isinstance(stock, dict):
                continue
            code = normalize_stock_code(stock.get("代码") or stock.get("code") or stock.get("symbol") or "")
            enriched_stock = {**stock_lookup.get(code, {}), **stock}
            resolved_sector = str(sector or "").strip()
            if not _is_valid_sector_label(resolved_sector):
                resolved_sector = xuangubao_plate_map.get(code, "")
            if not _is_valid_sector_label(resolved_sector):
                resolved_sector = _infer_sector_from_reason(_stock_reason_text(enriched_stock))
            if not _is_valid_sector_label(resolved_sector):
                continue
            sanitized.setdefault(resolved_sector, []).append(enriched_stock)
    return sanitized


def _enrich_price_shape(stock, code, stock_info_map, volume_anomaly_map):
    enriched = dict(stock)
    stock_info = stock_info_map.get(code, {}) or {}
    for key in ("open", "high", "low", "close", "price", "yclose", "change_pct"):
        if key in stock_info and enriched.get(key) in (None, ""):
            enriched[key] = stock_info.get(key)
    volume_anomaly = volume_anomaly_map.get(code, {}) or {}
    reason = volume_anomaly.get("reason")
    if reason and not enriched.get("volume_summary"):
        enriched["volume_summary"] = reason
    return enriched


def build_market_research_context_bundle_contract(
    data,
    target_date,
    exit_analysis,
    final_gate,
    position_level,
    main_sectors_info=None,
    secondary_sectors_info=None,
    main_sectors=None,
    secondary_sectors=None,
    dragon_stocks=None,
    *,
    get_active_a_kill_records,
    normalize_stock_code,
    safe_float,
    is_stock_in_a_kill_cooldown,
    sector_name_matches,
    build_abnormal_watch_pool,
    decision_strict_mode,
    allow_display_degraded_abnormal_snapshot,
    is_degraded_abnormal_snapshot,
    build_sector_trend_snapshot,
    build_leader_memory_bank,
    refresh_tracking_memory,
    discover_all_gem_breathing_candidates,
    candidate_matches_mainline,
    build_gem_observation_pool,
    build_mainline_competition_snapshot,
    build_market_observation_snapshot,
    build_market_research_snapshot,
    derive_step0_follow_plan,
    save_observation_pools=None,
):
    """构建 Step0/Step1 共用的市场研究上下文，供日报与单票诊断复用。"""
    logs = []
    main_sectors_info = main_sectors_info or []
    secondary_sectors_info = secondary_sectors_info or []
    main_sectors = main_sectors or []
    secondary_sectors = secondary_sectors or []
    dragon_stocks = dragon_stocks or []

    zt_pool_by_sector = data.get("zt_pool_by_sector", {})
    dt_pool_by_sector = data.get("dt_pool_by_sector", {})
    zt_pool = data.get("zt_pool", [])
    dt_pool = data.get("dt_pool", [])
    hot_stocks = data.get("hot_rank_top30", [])
    integrated_hot_list = data.get("integrated_hot_list", [])
    active_a_kill_records = get_active_a_kill_records(target_date)
    stock_info_map = _build_code_map(data.get("stock_full_info", {}), normalize_stock_code, ("code", "代码", "stock_code"))
    volume_anomaly_map = _build_code_map(data.get("volume_anomalies", []), normalize_stock_code, ("stock_code", "code", "代码"))
    xuangubao_plate_map = _build_xuangubao_plate_map(data, normalize_stock_code)
    zt_pool_lookup = {
        normalize_stock_code(stock.get("代码", stock.get("code", ""))): stock
        for stock in zt_pool
        if isinstance(stock, dict)
    }
    dt_pool_lookup = {
        normalize_stock_code(stock.get("代码", stock.get("code", ""))): stock
        for stock in dt_pool
        if isinstance(stock, dict)
    }
    zt_pool_by_sector = _sanitize_sector_bucket_map(zt_pool_by_sector, xuangubao_plate_map, normalize_stock_code, zt_pool_lookup)
    dt_pool_by_sector = _sanitize_sector_bucket_map(dt_pool_by_sector, xuangubao_plate_map, normalize_stock_code, dt_pool_lookup)

    candidates = []
    for stock in zt_pool[:30]:
        code = normalize_stock_code(stock.get("代码", stock.get("code", "")))
        stock = _enrich_price_shape(stock, code, stock_info_map, volume_anomaly_map)
        name = stock.get("名称", stock.get("name", ""))
        sector = _resolve_stock_sector(stock, code, xuangubao_plate_map)
        change = stock.get("涨跌幅", stock.get("change_pct", 9.9))

        open_price = stock.get("开盘价", stock.get("open", 0))
        close_price = stock.get("最新价", stock.get("close", 0))
        high_price = stock.get("最高价", stock.get("high", 0))
        low_price = stock.get("最低价", stock.get("low", 0))
        volume = stock.get("成交额", stock.get("volume", 0))
        signature = infer_signature_big_yangline(stock)

        score = 0
        reason_text = ""
        if signature == "一字板":
            score += 18
            reason_text = "一字板封死不可成交，只记录辨识度，等分歧后确认"
        elif "T字板" in signature:
            score += 35
            reason_text = "T字板分歧转一致，明日可能加速"
        elif "大阳线" in signature:
            score += 30
            reason_text = "大阳线封板，明日有溢价"
        elif change >= 9.9:
            score += 25
            reason_text = "涨停但形态一般，明日看竞价"

        if volume > 500000000:
            score += 15
            reason_text += "+放量"
        elif volume > 100000000:
            score += 10
            reason_text += "+有量"

        sector_count = len(zt_pool_by_sector.get(sector, []))
        if sector_count > 0:
            sector_stocks = zt_pool_by_sector.get(sector, [])
            for idx, sector_stock in enumerate(sector_stocks):
                if sector_stock.get("代码", sector_stock.get("code", "")) == code:
                    if idx == 0:
                        score += 20
                        reason_text += "+板块龙一"
                    elif idx <= 2:
                        score += 10
                        reason_text += "+板块前排"
                    break

        candidates.append(
            {
                "name": name,
                "code": code,
                "sector": sector,
                "change": change,
                "volume": volume,
                "score": score,
                "source": "涨停池",
                "pattern": signature if signature != "-" else "普通涨停",
                "reason": reason_text,
                "tomorrow_expectation": "观察竞价"
                if signature == "一字板"
                else "连板预期"
                if score >= 70
                else "溢价预期"
                if score >= 50
                else "观察竞价",
            }
        )

    hot_codes = {candidate["code"] for candidate in candidates}
    for idx, stock in enumerate(hot_stocks[:15], 1):
        code = normalize_stock_code(stock.get("code", ""))
        if code and code not in hot_codes:
            change = stock.get("change", 0)
            candidates.append(
                {
                    "name": stock.get("name", ""),
                    "code": code,
                    "sector": _resolve_stock_sector(stock, code, xuangubao_plate_map),
                    "change": change,
                    "score": max(0, 30 - idx * 2) + (10 if change >= 7 else 0),
                    "source": f"热榜第{idx}",
                    "pattern": "放量冲高",
                    "reason": f"热榜第{idx}+涨幅{change:.1f}%，仅作热度观察" if change < 9.9 else f"热榜第{idx}",
                    "tomorrow_expectation": "热度观察" if change < 9.9 else "连板预期",
                }
            )

    candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
    _append_log(logs, "collect.candidates", "success", "已构建候选池", candidate_count=len(candidates))

    watchlist = []
    filtered_by_a_kill = []
    for candidate in candidates:
        in_cooldown, cooldown_record = is_stock_in_a_kill_cooldown(candidate, active_a_kill_records)
        if in_cooldown:
            filtered_by_a_kill.append((candidate, cooldown_record))
        else:
            watchlist.append(candidate)
    watchlist = watchlist[:15]
    _append_log(
        logs,
        "filter.a_kill",
        "success",
        "已完成A杀冷却过滤",
        watchlist_count=len(watchlist),
        filtered_count=len(filtered_by_a_kill),
    )

    mainline_name = exit_analysis.get("sector_name", "") if exit_analysis else ""
    stock_meta_map = {}

    def register_stock_meta(stock):
        code = normalize_stock_code(stock.get("code", stock.get("代码", "")))
        if not code:
            return
        existing = stock_meta_map.get(code, {})
        sector_tags = _merge_text_list(
            existing.get("sector_tags", []),
            stock.get("sector_tags", []),
            stock.get("hot_tags", []),
        )
        concepts = _merge_text_list(
            existing.get("concepts", []),
            stock.get("concepts", []),
            stock.get("concept_list", []),
        )
        if not sector_tags and concepts:
            sector_tags = list(concepts)
        resolved_sector = _resolve_stock_sector(stock, code, xuangubao_plate_map)
        if resolved_sector == "未归类":
            if _is_valid_sector_label(existing.get("sector", "")):
                resolved_sector = existing.get("sector", "")
            elif sector_tags:
                resolved_sector = sector_tags[0]
        stock_meta_map[code] = {
            "name": stock.get("name", stock.get("名称", "")) or existing.get("name", ""),
            "code": code,
            "sector": resolved_sector,
            "industry": stock.get("industry", stock.get("所属行业", existing.get("industry", ""))),
            "sector_tags": sector_tags,
            "concepts": concepts,
            "concept_list": list(concepts),
            "score": safe_float(stock.get("tomorrow_strength", stock.get("score", existing.get("score", 0)))),
            "source": stock.get("source", existing.get("source", "")),
        }

    for source_list in (
        watchlist,
        hot_stocks[:15],
        integrated_hot_list[:50],
        dragon_stocks[:10],
        data.get("stocks_with_history", [])[:20],
        data.get("turnover_rank", [])[:20],
        zt_pool[:20],
    ):
        for item in source_list or []:
            register_stock_meta(item)

    abnormal_candidates = []
    abnormal_candidate_codes = set()

    def add_abnormal_candidate(stock):
        code = normalize_stock_code(stock.get("code", ""))
        if not code or code in abnormal_candidate_codes:
            return
        abnormal_candidate_codes.add(code)
        abnormal_candidates.append(
            {
                "name": stock.get("name", ""),
                "code": code,
                "sector": stock.get("sector", ""),
                "score": safe_float(stock.get("score", 0)),
                "source": stock.get("source", ""),
            }
        )

    for stock in watchlist[:10]:
        add_abnormal_candidate(stock)

    for anomaly in data.get("volume_anomalies", [])[:6]:
        if isinstance(anomaly, dict):
            anomaly_code = normalize_stock_code(anomaly.get("stock_code", anomaly.get("code", "")))
            anomaly_name = anomaly.get("stock_name", anomaly.get("name", ""))
        else:
            anomaly_code = normalize_stock_code(getattr(anomaly, "stock_code", ""))
            anomaly_name = getattr(anomaly, "stock_name", "")

        if not anomaly_code:
            continue

        meta = stock_meta_map.get(anomaly_code, {})
        add_abnormal_candidate(
            {
                "name": anomaly_name or meta.get("name", ""),
                "code": anomaly_code,
                "sector": meta.get("sector", ""),
                "score": meta.get("score", 0),
                "source": "放量异常",
            }
        )

    for stock in dragon_stocks[:8]:
        sector = stock.get("sector", "")
        lianban = int(stock.get("lianban", stock.get("连板数", 0)) or 0)
        if (mainline_name and sector_name_matches(sector, mainline_name)) or lianban >= 2:
            add_abnormal_candidate(
                {
                    "name": stock.get("name", ""),
                    "code": stock.get("code", ""),
                    "sector": sector,
                    "score": 70 + lianban * 5,
                    "source": "龙头锚定",
                }
            )

    abnormal_watch_pool_all = build_abnormal_watch_pool(
        target_date,
        abnormal_candidates,
        mainline_name=mainline_name,
        top_n=max(len(abnormal_candidates), 5),
        scan_limit=None,
        allow_degraded_snapshot=(not decision_strict_mode and allow_display_degraded_abnormal_snapshot),
        fast_fail=not decision_strict_mode,
    )
    abnormal_watch_pool = abnormal_watch_pool_all[:5]
    abnormal_watch_map = {
        normalize_stock_code(item.get("code", "")): item
        for item in abnormal_watch_pool_all
        if item.get("code") and not is_degraded_abnormal_snapshot(item)
    }
    _append_log(
        logs,
        "build.abnormal_watch",
        "success",
        "已构建异常观察池",
        total_count=len(abnormal_watch_pool_all),
        usable_count=len(abnormal_watch_map),
    )

    sector_trend_snapshot_step1 = build_sector_trend_snapshot(
        candidates,
        watchlist,
        [],
        dragon_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        top_n=5,
    )
    leader_memory_bank = build_leader_memory_bank(
        sector_trend_snapshot_step1,
        watchlist,
        dragon_stocks,
        hot_rank_top30=hot_stocks,
        top_n=5,
    )
    tracking_memory_status = refresh_tracking_memory(
        target_date,
        watchlist,
        leader_memory_bank,
        abnormal_watch_pool_all,
        stock_meta_map=stock_meta_map,
    )
    _append_log(logs, "build.memory", "success", "已构建龙头记忆与跟踪状态", memory_count=len(leader_memory_bank))

    if decision_strict_mode:
        all_gem_breathing_candidates = discover_all_gem_breathing_candidates(
            stock_meta_map,
            target_date=target_date,
        )
    else:
        all_gem_breathing_candidates = []
        _append_log(
            logs,
            "build.gem_breathing",
            "skipped",
            "display-safe 模式跳过 gem breathing 全量发现，避免渲染阶段额外联网",
        )
    gem_breathing_candidates = [
        item
        for item in all_gem_breathing_candidates
        if (not mainline_name) or candidate_matches_mainline(item, mainline_name)
    ][:3]
    filtered_out_gem_breathing_candidates = [
        {
            **item,
            "filtered_reason": f"当前主线是{mainline_name}，该样本不在主线内，因此不纳入正式观察池。",
        }
        for item in all_gem_breathing_candidates
        if mainline_name and not candidate_matches_mainline(item, mainline_name)
    ][:3]
    gem_observation_stocks = build_gem_observation_pool(gem_breathing_candidates, target_date=target_date)

    validated_tracking_codes = {
        normalize_stock_code(item.get("code", ""))
        for item in tracking_memory_status.get("today_validated_items", [])
        if item.get("code")
    }
    if validated_tracking_codes:
        for item in leader_memory_bank:
            code = normalize_stock_code(item.get("code", ""))
            if code in validated_tracking_codes:
                item["remember_score"] = round(safe_float(item.get("remember_score", 0)) + 10, 1)
                item["remember_reason"] = f"{item.get('remember_reason', '')} / 历史跟踪已二次确认".strip(" /")
                item["action_rule"] = "它不是临时起意的新故事，只有今天再次转强才保留优先回看权"
        leader_memory_bank.sort(
            key=lambda item: (item.get("remember_score", 0), item.get("sector", "")),
            reverse=True,
        )
        leader_memory_bank = leader_memory_bank[:5]

    mainline_competition_snapshot = build_mainline_competition_snapshot(
        main_sectors_info=main_sectors_info or [{"name": name} for name in main_sectors[:2]],
        secondary_sectors_info=secondary_sectors_info or [{"name": name} for name in secondary_sectors[:2]],
        sector_trend_snapshot=sector_trend_snapshot_step1,
        risk_sectors=exit_analysis.get("risk_sectors", []),
    )
    observation_snapshot = build_market_observation_snapshot(
        data,
        main_sectors_info=main_sectors_info or [{"name": name} for name in main_sectors[:2]],
        secondary_sectors_info=secondary_sectors_info or [{"name": name} for name in secondary_sectors[:2]],
        sector_trend_snapshot=sector_trend_snapshot_step1,
        abnormal_watch_pool=abnormal_watch_pool,
        leader_memory_bank=leader_memory_bank,
        tracking_memory_status=tracking_memory_status,
        mainline_competition_snapshot=mainline_competition_snapshot,
    )
    if callable(save_observation_pools):
        save_observation_pools(
            target_date,
            {
                "watchlist": watchlist,
                "abnormal_watch_pool": abnormal_watch_pool,
                "abnormal_watch_pool_all": abnormal_watch_pool_all,
                "leader_memory_bank": leader_memory_bank,
                "tracking_memory_status": tracking_memory_status.get("total_items", []),
                "gem_observation_stocks": gem_observation_stocks,
                "filtered_by_a_kill": [item[0] for item in filtered_by_a_kill],
            },
        )
    market_research_snapshot = build_market_research_snapshot(
        data,
        final_gate,
        position_level,
        exit_analysis,
        observation_snapshot=observation_snapshot,
        target_date=target_date,
    )
    mainline_turnover_summary = market_research_snapshot.get("mainline_turnover_summary", {}) or {}
    market_state_snapshot = market_research_snapshot.get("state_machine", {}) or {}
    abnormal_projection_summary = market_research_snapshot.get("abnormal_projection", {}) or {}
    step0_plan = derive_step0_follow_plan(market_research_snapshot, final_gate, position_level)
    _append_log(logs, "build.market_snapshot", "success", "已构建市场研究快照", mainline_name=mainline_name)

    return {
        "zt_pool_by_sector": zt_pool_by_sector,
        "dt_pool_by_sector": dt_pool_by_sector,
        "zt_pool": zt_pool,
        "hot_stocks": hot_stocks,
        "active_a_kill_records": active_a_kill_records,
        "candidates": candidates,
        "watchlist": watchlist,
        "filtered_by_a_kill": filtered_by_a_kill,
        "mainline_name": mainline_name,
        "stock_meta_map": stock_meta_map,
        "abnormal_watch_pool_all": abnormal_watch_pool_all,
        "abnormal_watch_pool": abnormal_watch_pool,
        "abnormal_watch_map": abnormal_watch_map,
        "sector_trend_snapshot_step1": sector_trend_snapshot_step1,
        "leader_memory_bank": leader_memory_bank,
        "tracking_memory_status": tracking_memory_status,
        "gem_breathing_candidates": gem_breathing_candidates,
        "filtered_out_gem_breathing_candidates": filtered_out_gem_breathing_candidates,
        "gem_observation_stocks": gem_observation_stocks,
        "mainline_competition_snapshot": mainline_competition_snapshot,
        "observation_snapshot": observation_snapshot,
        "market_research_snapshot": market_research_snapshot,
        "market_state_snapshot": market_state_snapshot,
        "mainline_turnover_summary": mainline_turnover_summary,
        "abnormal_projection_summary": abnormal_projection_summary,
        "step0_plan": step0_plan,
        "module_logs": logs,
    }
