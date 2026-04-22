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
    hot_stocks = data.get("hot_rank_top30", [])
    integrated_hot_list = data.get("integrated_hot_list", [])
    active_a_kill_records = get_active_a_kill_records(target_date)

    candidates = []
    for stock in zt_pool[:30]:
        code = normalize_stock_code(stock.get("代码", stock.get("code", "")))
        name = stock.get("名称", stock.get("name", ""))
        sector = stock.get("所属行业", stock.get("sector", ""))
        change = stock.get("涨跌幅", 9.9)

        open_price = stock.get("开盘价", stock.get("open", 0))
        close_price = stock.get("最新价", stock.get("close", 0))
        high_price = stock.get("最高价", stock.get("high", 0))
        low_price = stock.get("最低价", stock.get("low", 0))
        volume = stock.get("成交额", stock.get("volume", 0))

        is_yizi = (open_price == close_price == high_price == low_price) and change >= 9.9
        is_tzi = (open_price == high_price == close_price) and low_price < open_price and change >= 9.9
        is_guangtou = (high_price == close_price) and (open_price < close_price) and change >= 9.9

        score = 0
        reason_text = ""
        if is_yizi:
            score += 40
            reason_text = "一字板最强，明日大概率连板"
        elif is_tzi:
            score += 35
            reason_text = "T字板分歧转一致，明日可能加速"
        elif is_guangtou:
            score += 30
            reason_text = "光头涨停实体强，明日有溢价"
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
                "pattern": "一字板" if is_yizi else "T字板" if is_tzi else "光头涨停" if is_guangtou else "普通涨停",
                "reason": reason_text,
                "tomorrow_expectation": "连板预期" if score >= 70 else "溢价预期" if score >= 50 else "观察竞价",
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
                    "sector": stock.get("sector", stock.get("所属板块", "")),
                    "change": change,
                    "score": max(0, 30 - idx * 2) + (10 if change >= 7 else 0),
                    "source": f"热榜第{idx}",
                    "pattern": "放量冲高",
                    "reason": f"热榜第{idx}+涨幅{change:.1f}%，明日可能反包" if change < 9.9 else f"热榜第{idx}",
                    "tomorrow_expectation": "反包预期" if change < 9.9 else "连板预期",
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
        stock_meta_map[code] = {
            "name": stock.get("name", stock.get("名称", "")) or existing.get("name", ""),
            "code": code,
            "sector": (
                stock.get("sector", "")
                or stock.get("所属行业", "")
                or stock.get("所属板块", "")
                or existing.get("sector", "")
                or (sector_tags[0] if sector_tags else "")
            ),
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

    all_gem_breathing_candidates = discover_all_gem_breathing_candidates(
        stock_meta_map,
        target_date=target_date,
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
    market_research_snapshot = build_market_research_snapshot(
        data,
        final_gate,
        position_level,
        exit_analysis,
        observation_snapshot=observation_snapshot,
        target_date=target_date,
    )
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
        "abnormal_projection_summary": abnormal_projection_summary,
        "step0_plan": step0_plan,
        "module_logs": logs,
    }
