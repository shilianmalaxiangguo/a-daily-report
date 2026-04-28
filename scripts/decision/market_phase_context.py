def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "decision.market_phase_context",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _resolve_base_position(zs_signal_type, zs_signal_status, market_trend, zt_count, dt_count, dt_panic_threshold, main_sectors):
    is_dt_panic = dt_count >= dt_panic_threshold
    if "形成中" in str(zs_signal_status or ""):
        if zs_signal_type in ["跌破支撑", "暴跌至下一中枢"]:
            return (
                "一档（空仓档）",
                f"当前中枢未满20根({zs_signal_status})且价格走弱，先空仓观察，不按有效日线中枢承接。",
                is_dt_panic,
            )
        return (
            "二档（防守档）",
            f"当前中枢未满20根({zs_signal_status})，只作观察，不把形成中突破放大成三档进攻。",
            is_dt_panic,
        )

    if zs_signal_type == "大盘突破":
        if is_dt_panic:
            return (
                "二档（防守档）",
                f"中枢已突破({zs_signal_status})，但跌停{dt_count}只≥{dt_panic_threshold}只为跌停潮(退潮期)，不猛干，持有但不新增",
                is_dt_panic,
            )
        return (
            "三档（进攻档）",
            f"中枢已突破({zs_signal_status})，无跌停潮(dt={dt_count}<{dt_panic_threshold})，积极做多",
            is_dt_panic,
        )

    if zs_signal_type in ["跌破支撑", "暴跌至下一中枢"]:
        return (
            "一档（空仓档）",
            f"中枢跌破({zs_signal_status})，半山腰接飞刀风险极高，必须空仓观望",
            is_dt_panic,
        )

    if zs_signal_type is None:
        if market_trend == "强势上涨" and zt_count > 40 and dt_count < 3 and len(main_sectors) >= 2:
            return ("三档（进攻档）", "市场强势上涨，主线明确，赚钱效应明显（中枢数据不可用，纯情绪判断）", is_dt_panic)
        if market_trend in ["小幅上涨", "震荡整理"] and zt_count > 20 and dt_count < 5 and len(main_sectors) >= 1:
            return ("二档（防守档）", "市场震荡整理，有局部赚钱效应（中枢数据不可用，纯情绪判断）", is_dt_panic)
        return ("一档（空仓档）", "市场调整明显，赚钱效应不足（中枢数据不可用，纯情绪判断）", is_dt_panic)

    if market_trend == "强势上涨" and zt_count > 40 and not is_dt_panic:
        return ("二档（防守档）", f"中枢内震荡({zs_signal_status})，但市场强势(涨停{zt_count}只)，可持有但不新增", is_dt_panic)
    if market_trend in ["小幅上涨", "震荡整理"] and zt_count > 20 and dt_count < 10:
        return ("二档（防守档）", f"中枢内震荡({zs_signal_status})，市场温和，精选个股持有", is_dt_panic)
    return ("一档（空仓档）", f"中枢内震荡({zs_signal_status})且市场偏弱，应清仓或极轻仓观望", is_dt_panic)


def _chanlun_confirmation_is_unconfirmed(market_zhongshu):
    confirmation = (market_zhongshu or {}).get("chanlun_confirmation") or {}
    status = confirmation.get("confirmation_status")
    return status in {
        "forming_daily_level_zhongshu",
        "not_confirmed",
        "insufficient_60m_history",
        "structure_conflict",
    }


def _is_index_recovery_inside_zhongshu(market_zhongshu, zs_signal_type, zt_count, dt_count, dt_panic_threshold, exit_analysis):
    if not market_zhongshu or not market_zhongshu.get("success"):
        return False
    if zs_signal_type != "按个股信号操作":
        return False
    if (exit_analysis or {}).get("overall_level") == "红灯":
        return False

    signal = market_zhongshu.get("signal", {}) or {}
    current = market_zhongshu.get("current_zhongshu", {}) or {}
    if signal.get("comparison_state") != "range":
        return False

    try:
        start_close = float(current.get("start_close") or 0)
        end_close = float(current.get("end_close") or 0)
        today_price = float(signal.get("today_price") or 0)
        zd = float(current.get("zd") or signal.get("zd") or 0)
        zg = float(current.get("zg") or signal.get("zg") or 0)
    except (TypeError, ValueError):
        return False

    if min(start_close, end_close, today_price, zd, zg) <= 0:
        return False

    index_is_rising_in_pivot = end_close >= start_close * 1.01 and today_price >= start_close
    price_still_inside_pivot = zd <= today_price <= zg
    market_still_active = zt_count >= 20
    not_crash_level_dt = dt_count < dt_panic_threshold * 2
    return index_is_rising_in_pivot and price_still_inside_pivot and market_still_active and not_crash_level_dt


def build_market_phase_context_contract(
    data,
    target_date,
    *,
    analyze_market_zhongshu,
    analyze_market_and_sectors,
    resolve_market_mainline_context,
    build_mainline_exit_analysis,
    merge_position_gate,
    build_market_state_machine_snapshot,
    resolve_environment_display_contract,
    calculate_price_range,
    market_zhongshu_lookback_days=120,
    market_zhongshu_min_klines=20,
):
    logs = []
    _append_log(logs, "start", "success", "开始构建市场环境上下文", target_date=target_date)

    market_zhongshu = analyze_market_zhongshu(
        index_code="sh.000001",
        recent_days=market_zhongshu_lookback_days,
        min_zhongshu_klines=market_zhongshu_min_klines,
        target_date=target_date,
    )
    _append_log(logs, "zhongshu", "success", "已完成大盘中枢结构分析", success=bool((market_zhongshu or {}).get("success")))

    market_analysis = analyze_market_and_sectors(data)
    market_trend = market_analysis.get("market_status", "震荡整理")
    mainline_context = resolve_market_mainline_context(data, market_analysis)
    main_sectors_info = mainline_context.get("main_sectors_info", [])
    secondary_sectors_info = mainline_context.get("secondary_sectors_info", [])
    main_sectors = mainline_context.get("main_sectors", [])
    secondary_sectors = mainline_context.get("secondary_sectors", [])
    dragon_stocks = mainline_context.get("dragon_stocks", [])

    exit_analysis = build_mainline_exit_analysis(data, market_analysis, dragon_stocks, main_sectors)
    _append_log(logs, "exit_analysis", "success", "已完成主线退潮与环境闸门分析", overall_level=exit_analysis.get("overall_level", ""))

    turnover = data.get("total_turnover", 0)
    zt_count = len(data.get("zt_pool", []))
    dt_count = len(data.get("dt_pool", []))
    indices = data.get("indices", {})
    sh_change = indices.get("上证指数", {}).get("涨跌幅", 0) if indices else 0
    market_stats = data.get("market_stats", {})
    up_count = market_stats.get("up_count", 0)
    down_count = market_stats.get("down_count", 0)
    rise_fall_ratio = up_count / down_count if down_count > 0 else 0

    zs_signal_type = None
    zs_signal_status = None
    if market_zhongshu and market_zhongshu.get("success"):
        zs_signal = market_zhongshu.get("signal", {})
        zs_signal_type = zs_signal.get("signal_type", "")
        zs_signal_status = zs_signal.get("status", "")

    dt_panic_threshold = 15
    base_position_level, base_position_reason, is_dt_panic = _resolve_base_position(
        zs_signal_type,
        zs_signal_status,
        market_trend,
        zt_count,
        dt_count,
        dt_panic_threshold,
        main_sectors,
    )
    if _chanlun_confirmation_is_unconfirmed(market_zhongshu):
        if "三档" in str(base_position_level):
            base_position_level = "二档（防守档）"
        base_position_reason = f"{base_position_reason}；日K结构仍需60分钟缠论确认，未确认前只作防守观察。"

    if base_position_level == "一档（空仓档）" and _is_index_recovery_inside_zhongshu(
        market_zhongshu,
        zs_signal_type,
        zt_count,
        dt_count,
        dt_panic_threshold,
        exit_analysis,
    ):
        base_position_level = "二档（防守档）"
        base_position_reason = (
            f"指数仍在上行中枢内({zs_signal_status})，单日跌停{dt_count}只和涨跌比偏弱只降为防守观察，"
            "不直接判定空仓；明日仍需10点确认主线承接。"
        )
        _append_log(
            logs,
            "index_recovery_guard",
            "success",
            "指数处在上行中枢内，阻止单日广度分歧直接打到空仓档",
            zt_count=zt_count,
            dt_count=dt_count,
        )
    _append_log(
        logs,
        "base_position",
        "success",
        "已得到基础仓位结论",
        base_position_level=base_position_level,
        market_trend=market_trend,
        zs_signal_type=zs_signal_type,
    )

    final_gate = merge_position_gate(base_position_level, exit_analysis)

    overall_level = exit_analysis.get("overall_level", "红灯")
    sector_name = exit_analysis.get("sector_name", "")
    if (
        zs_signal_type == "大盘突破"
        and "形成中" not in str(zs_signal_status or "")
        and not is_dt_panic
        and not final_gate["can_new_entry"]
        and "暂无明确主线" in str(sector_name)
        and not _chanlun_confirmation_is_unconfirmed(market_zhongshu)
    ):
        final_gate = {
            "gate_status": "放行",
            "position_level": "三档（进攻档）",
            "operation_state": "进攻态",
            "can_new_entry": True,
            "can_hold": True,
            "should_reduce": False,
            "final_action": f"中枢已突破({zs_signal_status})且非跌停潮，普涨行情允许围绕最强趋势参与",
            "final_participation": "中枢突破是最高优先级信号，无单一主线的普涨行情也要敢于跟住强趋势",
            "gate_reason": "中枢突破优先于“暂无明确主线”的表述，普涨行情本身就是可参与环境",
        }
        _append_log(logs, "gate_override", "success", "触发中枢突破覆盖规则", overall_level=overall_level)

    position_level = final_gate.get("position_level", base_position_level)
    gate_reason = final_gate.get("gate_reason", "")
    if gate_reason and gate_reason not in base_position_reason:
        position_reason = f"{base_position_reason}；{gate_reason}"
    else:
        position_reason = base_position_reason

    preliminary_state_machine = build_market_state_machine_snapshot(
        data=data,
        final_gate=final_gate,
        position_level=position_level,
        exit_analysis=exit_analysis,
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        sector_trend_snapshot=data.get("sector_trend_snapshot", []) or [],
        abnormal_watch_pool=[],
    )
    environment_display = resolve_environment_display_contract(
        position_level=position_level,
        final_gate=final_gate,
        state_machine_snapshot=preliminary_state_machine,
    )

    price_info = None
    if position_level not in ["一档（空仓档）", "二档（防守档）"]:
        hot_rank_top30 = data.get("hot_rank_top30", [])
        if hot_rank_top30:
            price_info = calculate_price_range(hot_rank_top30[0])

    _append_log(
        logs,
        "final_position",
        "success",
        "已完成环境上下文定稿",
        position_level=position_level,
        has_price_info=bool(price_info),
        overall_level=overall_level,
    )

    return {
        "market_zhongshu": market_zhongshu,
        "market_analysis": market_analysis,
        "market_trend": market_trend,
        "mainline_context": mainline_context,
        "main_sectors_info": main_sectors_info,
        "secondary_sectors_info": secondary_sectors_info,
        "main_sectors": main_sectors,
        "secondary_sectors": secondary_sectors,
        "dragon_stocks": dragon_stocks,
        "exit_analysis": exit_analysis,
        "turnover": turnover,
        "zt_count": zt_count,
        "dt_count": dt_count,
        "indices": indices,
        "sh_change": sh_change,
        "market_stats": market_stats,
        "up_count": up_count,
        "down_count": down_count,
        "rise_fall_ratio": rise_fall_ratio,
        "zs_signal_type": zs_signal_type,
        "zs_signal_status": zs_signal_status,
        "is_dt_panic": is_dt_panic,
        "dt_panic_threshold": dt_panic_threshold,
        "base_position_level": base_position_level,
        "base_position_reason": base_position_reason,
        "position_level": position_level,
        "position_reason": position_reason,
        "final_gate": final_gate,
        "overall_level": overall_level,
        "price_info": price_info,
        "preliminary_state_machine": preliminary_state_machine,
        "environment_display": environment_display,
        "module_logs": logs,
    }
