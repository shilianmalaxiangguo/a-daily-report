def build_entry_plan_judgement_node(context, node_meta=None, node_lookup=None):
    target_date = context.get("target_date", "")
    mainline_name = str(context.get("mainline_name", "") or "").strip()
    final_gate = context.get("final_gate", {}) or {}
    focus_group = context.get("focus_group", []) or []
    conviction_codes = context.get("conviction_codes", set()) or set()
    leader_memory_codes = context.get("leader_memory_codes", set()) or set()
    market_research_snapshot = context.get("market_research_snapshot", {}) or {}
    quant_system_available = bool(context.get("quant_system_available", False))
    stop_prior_low_trading_days = int(context.get("stop_prior_low_trading_days", 3) or 3)
    position_level = str(context.get("position_level", "") or "").strip()

    get_trade_permission = context["get_trade_permission"]
    fetch_recent_price_bars = context["fetch_recent_price_bars"]
    evaluate_live_tradability = context["evaluate_live_tradability"]
    build_intraday_execution_plan = context["build_intraday_execution_plan"]
    build_stop_execution_plan = context["build_stop_execution_plan"]
    enrich_stop_plan_with_reference_anchors = context["enrich_stop_plan_with_reference_anchors"]
    build_waiting_stock_plan = context["build_waiting_stock_plan"]
    finalize_waiting_candidate = context["finalize_waiting_candidate"]
    build_trade_price_focus = context["build_trade_price_focus"]
    build_observation_price_focus_text = context["build_observation_price_focus_text"]
    analyze_buy_signal = context.get("analyze_buy_signal")

    executable_stocks = []
    waiting_stocks = []
    untradable_stocks = []
    rejected_stocks = []
    lines = []

    if quant_system_available and focus_group:
        lines.append("**明日买点预计算表**:")
        lines.append("| 股票 | 代码 | 买入资格 | 怎么买 | 日线预设区间 | 60分钟确认点 | 价格怎么盯 | 明天具体怎么做 |")
        lines.append("|------|------|----------|----------|------------|--------------|----------|----------|")

        for stock in focus_group:
            code = stock.get("code", "")
            name = stock.get("name", "")
            close = stock.get("close", 0)
            volume = stock.get("volume", 0)
            permission = get_trade_permission(
                stock,
                mainline_name=mainline_name,
                conviction_codes=conviction_codes,
                leader_memory_codes=leader_memory_codes,
                final_gate=final_gate,
                state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
            )
            recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4)
            daily_anchor_bars = fetch_recent_price_bars(
                code,
                target_date,
                lookback_days=max(stop_prior_low_trading_days + 5, 10),
            )
            tradability_guard = evaluate_live_tradability(stock, target_date, recent_bars=recent_bars)

            if not tradability_guard.get("can_trade", True):
                untradable_stocks.append(
                    {
                        **stock,
                        "reason": tradability_guard.get("reason", ""),
                        "permission_label": permission.get("permission_label", ""),
                        "permission_reason": permission.get("permission_reason", ""),
                        "tradability_guard": tradability_guard,
                        "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                    }
                )
                lines.append(
                    f"| {name} | {code} | {permission.get('permission_label', '-')} | 不可交易 | - | - | - | "
                    f"⚠️{tradability_guard.get('status_label', '不可交易')} |"
                )
                continue

            signal = analyze_buy_signal(code, name, close, volume)

            if signal and not signal.is_valid and "跌破" in signal.reason:
                rejected_stocks.append(
                    {
                        **stock,
                        "reason": signal.reason,
                        "permission_label": permission.get("permission_label", ""),
                        "permission_reason": permission.get("permission_reason", ""),
                    }
                )
                lines.append(
                    f"| {name} | {code} | {permission.get('permission_label', '-')} | - | - | - | - | ❌已破位，明日不碰 |"
                )
            elif signal and signal.is_valid and permission.get("can_execute"):
                signal_type_map = {
                    "panic_buy": "🚨恐慌盘",
                    "sweet_zone": "甜品区",
                    "breakout": "放量突破",
                }
                buy_type = signal_type_map.get(signal.signal_type, signal.signal_type)
                entry_low = signal.entry_price * 0.97
                entry_high = signal.entry_price * 1.03
                trigger_range = f"{entry_low:.2f}-{entry_high:.2f}"
                minute_plan = build_intraday_execution_plan(
                    code,
                    target_date,
                    signal.entry_price,
                    signal.signal_type,
                    fallback_stop=signal.stop_loss,
                )
                stop_plan = minute_plan.get("stop_plan") or build_stop_execution_plan(
                    signal.entry_price,
                    signal.stop_loss,
                    structure_label="日线预估结构止损",
                )
                stop_plan = enrich_stop_plan_with_reference_anchors(
                    stop_plan,
                    code,
                    target_date,
                    recent_bars=daily_anchor_bars,
                )
                executable_stocks.append(
                    {
                        **stock,
                        "signal": signal,
                        "entry_price": signal.entry_price,
                        "entry_range": (entry_low, entry_high),
                        "stop_loss": stop_plan["effective_stop"] if stop_plan else signal.stop_loss,
                        "stop_plan": stop_plan,
                        "minute_plan": minute_plan,
                        "position_pct": signal.position_pct,
                        "permission_label": permission.get("permission_label", ""),
                        "permission_reason": permission.get("permission_reason", ""),
                        "tradability_guard": tradability_guard,
                        "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                        "watch_source": "execute_layer",
                    }
                )
                price_focus = build_trade_price_focus(minute_plan, stop_plan)
                confirm_price = minute_plan.get("confirm_price_60m")
                confirm_text = f"{confirm_price:.2f}" if confirm_price else "-"
                action_text = "60分钟确认后买入" if final_gate.get("can_new_entry", False) else "仅保留执行预案（禁买）"
                price_focus_text = (
                    price_focus.get("compact_text", "-")
                    if final_gate.get("can_new_entry", False)
                    else build_observation_price_focus_text(price_focus)
                )
                lines.append(
                    f"| {name} | {code} | {permission.get('permission_label', '-')} | {buy_type} | "
                    f"{trigger_range} | {confirm_text} | {price_focus_text} | {action_text} |"
                )
            else:
                base_reason = signal.reason if signal else "无结构中枢或无买点"
                wait_reason = permission.get("permission_reason") or base_reason
                if signal and signal.is_valid and not permission.get("can_execute"):
                    wait_reason = f"{permission.get('permission_reason')}；结构预案已出现，但当前只保留观察权"
                elif not signal and permission.get("can_execute"):
                    wait_reason = f"{permission.get('permission_reason')}；但当前还没走出明确结构预案"
                elif signal and not signal.is_valid and permission.get("can_execute"):
                    wait_reason = f"{permission.get('permission_reason')}；{signal.reason}"
                waiting_item = build_waiting_stock_plan(
                    {
                        **stock,
                        "condition": wait_reason,
                        "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                        "tradability_guard": tradability_guard,
                    },
                    target_date,
                    reason=wait_reason,
                    signal_type=getattr(signal, "signal_type", "") if signal else "",
                    recent_bars=daily_anchor_bars,
                )
                waiting_item = finalize_waiting_candidate(waiting_item, stock, permission)
                waiting_stocks.append(waiting_item)
                minute_plan = waiting_item.get("minute_plan") or {}
                stop_plan = waiting_item.get("stop_plan")
                price_focus = build_trade_price_focus(minute_plan, stop_plan)
                confirm_price = minute_plan.get("confirm_price_60m")
                confirm_text = f"{confirm_price:.2f}" if confirm_price else "-"
                price_focus_text = build_observation_price_focus_text(price_focus)
                lines.append(
                    f"| {name} | {code} | {permission.get('permission_label', '-')} | 观察 | - | "
                    f"{confirm_text} | {price_focus_text} | ⏳明日继续观察 |"
                )
    else:
        lines.append("**买点判断** (量化系统不可用，使用基础判断):")
        lines.append("| 股票 | 代码 | 执行权限 | 今日涨幅 | 判断 | 60分钟确认点 | 价格怎么盯 | 动作 |")
        lines.append("|------|------|----------|----------|------|--------------|----------|------|")

        for stock in focus_group:
            change = stock.get("change", 0)
            name = stock.get("name", "")
            code = stock.get("code", "")
            waiting_item = None
            permission = get_trade_permission(
                stock,
                mainline_name=mainline_name,
                conviction_codes=conviction_codes,
                leader_memory_codes=leader_memory_codes,
                final_gate=final_gate,
                state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
            )
            recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4)
            daily_anchor_bars = fetch_recent_price_bars(
                code,
                target_date,
                lookback_days=max(stop_prior_low_trading_days + 5, 10),
            )
            tradability_guard = evaluate_live_tradability(stock, target_date, recent_bars=recent_bars)

            if not tradability_guard.get("can_trade", True):
                untradable_stocks.append(
                    {
                        **stock,
                        "reason": tradability_guard.get("reason", ""),
                        "permission_label": permission.get("permission_label", ""),
                        "permission_reason": permission.get("permission_reason", ""),
                        "tradability_guard": tradability_guard,
                        "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                    }
                )
                lines.append(
                    f"| {name} | {code} | {permission.get('permission_label', '-')} | {change:+.2f}% | 不可交易 | - | - | "
                    f"⚠️{tradability_guard.get('status_label', '不可交易')} |"
                )
                continue

            if change >= 9:
                judgment = "🔥 涨停"
                minute_plan = build_intraday_execution_plan(code, target_date, stock.get("close", 0), fallback_stop=None)
                stop_plan = minute_plan.get("stop_plan") or build_stop_execution_plan(stock.get("close", 0))
                stop_plan = enrich_stop_plan_with_reference_anchors(stop_plan, code, target_date, recent_bars=daily_anchor_bars)
                if permission.get("can_execute"):
                    action = "可执行" if final_gate.get("can_new_entry", False) else "预案观察"
                    executable_stocks.append(
                        {
                            **stock,
                            "trigger": "涨停",
                            "entry_price": stock.get("close", 0),
                            "stop_plan": stop_plan,
                            "minute_plan": minute_plan,
                            "stop_loss": stop_plan["effective_stop"] if stop_plan else 0,
                            "permission_label": permission.get("permission_label", ""),
                            "permission_reason": permission.get("permission_reason", ""),
                            "tradability_guard": tradability_guard,
                            "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                            "watch_source": "execute_layer",
                        }
                    )
                else:
                    action = "等权限"
                    waiting_item = build_waiting_stock_plan(
                        {
                            **stock,
                            "condition": permission.get("permission_reason", "等待权限"),
                            "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                            "tradability_guard": tradability_guard,
                        },
                        target_date,
                        reason=permission.get("permission_reason", "等待权限"),
                        recent_bars=daily_anchor_bars,
                    )
                    waiting_item = finalize_waiting_candidate(waiting_item, stock, permission)
                    waiting_stocks.append(waiting_item)
            elif change >= 5:
                judgment = "✅ 大涨"
                minute_plan = build_intraday_execution_plan(code, target_date, stock.get("close", 0), fallback_stop=None)
                stop_plan = minute_plan.get("stop_plan") or build_stop_execution_plan(stock.get("close", 0))
                stop_plan = enrich_stop_plan_with_reference_anchors(stop_plan, code, target_date, recent_bars=daily_anchor_bars)
                if permission.get("can_execute"):
                    action = "可执行" if final_gate.get("can_new_entry", False) else "预案观察"
                    executable_stocks.append(
                        {
                            **stock,
                            "trigger": f"涨{change:.1f}%",
                            "entry_price": stock.get("close", 0),
                            "stop_plan": stop_plan,
                            "minute_plan": minute_plan,
                            "stop_loss": stop_plan["effective_stop"] if stop_plan else 0,
                            "permission_label": permission.get("permission_label", ""),
                            "permission_reason": permission.get("permission_reason", ""),
                            "tradability_guard": tradability_guard,
                            "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                            "watch_source": "execute_layer",
                        }
                    )
                else:
                    action = "等权限"
                    waiting_item = build_waiting_stock_plan(
                        {
                            **stock,
                            "condition": permission.get("permission_reason", "等待权限"),
                            "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                            "tradability_guard": tradability_guard,
                        },
                        target_date,
                        reason=permission.get("permission_reason", "等待权限"),
                        recent_bars=daily_anchor_bars,
                    )
                    waiting_item = finalize_waiting_candidate(waiting_item, stock, permission)
                    waiting_stocks.append(waiting_item)
            elif change >= 2:
                judgment = "🟡 小涨"
                action = "等次日"
                waiting_item = build_waiting_stock_plan(
                    {
                        **stock,
                        "condition": permission.get("permission_reason", "等待放量突破"),
                        "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                        "tradability_guard": tradability_guard,
                    },
                    target_date,
                    reason=permission.get("permission_reason", "等待放量突破"),
                    recent_bars=daily_anchor_bars,
                )
                waiting_item = finalize_waiting_candidate(waiting_item, stock, permission)
                waiting_stocks.append(waiting_item)
            else:
                judgment = "🟠 震荡"
                action = "等信号"
                waiting_item = build_waiting_stock_plan(
                    {
                        **stock,
                        "condition": permission.get("permission_reason", "等待转折确认"),
                        "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                        "tradability_guard": tradability_guard,
                    },
                    target_date,
                    reason=permission.get("permission_reason", "等待转折确认"),
                    recent_bars=daily_anchor_bars,
                )
                waiting_item = finalize_waiting_candidate(waiting_item, stock, permission)
                waiting_stocks.append(waiting_item)

            if change >= 5:
                confirm_price = minute_plan.get("confirm_price_60m") if minute_plan else None
                price_focus = build_trade_price_focus(minute_plan, stop_plan)
                confirm_text = f"{confirm_price:.2f}" if confirm_price else "-"
                price_focus_text = (
                    price_focus.get("compact_text", "-")
                    if final_gate.get("can_new_entry", False)
                    else build_observation_price_focus_text(price_focus)
                )
                lines.append(
                    f"| {name} | {code} | {permission.get('permission_label', '-')} | {change:+.2f}% | "
                    f"{judgment} | {confirm_text} | {price_focus_text} | {action} |"
                )
            else:
                minute_plan = waiting_item.get("minute_plan") if waiting_item else {}
                stop_plan = waiting_item.get("stop_plan") if waiting_item else None
                price_focus = build_trade_price_focus(minute_plan, stop_plan)
                confirm_price = minute_plan.get("confirm_price_60m") if minute_plan else None
                confirm_text = f"{confirm_price:.2f}" if confirm_price else "-"
                price_focus_text = build_observation_price_focus_text(price_focus)
                lines.append(
                    f"| {name} | {code} | {permission.get('permission_label', '-')} | {change:+.2f}% | "
                    f"{judgment} | {confirm_text} | {price_focus_text} | {action} |"
                )

    lines.append("")
    return {
        "lines": lines,
        "exports": {
            "executable_stocks": executable_stocks,
            "waiting_stocks": waiting_stocks,
            "untradable_stocks": untradable_stocks,
            "rejected_stocks": rejected_stocks,
        },
        "module_logs": [],
    }
