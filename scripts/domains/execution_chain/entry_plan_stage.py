from domains.execution_chain.stage_runtime import get_execution_stage_label


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.entry_plan_stage",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_entry_plan_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    stage_lookup = stage_lookup or {}
    logs = []

    target_date = stage_context.get("target_date", "")
    mainline_name = str(stage_context.get("mainline_name", "") or "").strip()
    position_level = str(stage_context.get("position_level", "") or "").strip()
    final_gate = stage_context.get("final_gate", {}) or {}
    focus_group = stage_context.get("focus_group", []) or []
    keep_group = stage_context.get("keep_group", []) or []
    delete_group = stage_context.get("delete_group", []) or []
    extreme_conviction_list = stage_context.get("extreme_conviction_list", []) or []
    leader_memory_bank = stage_context.get("leader_memory_bank", []) or []
    market_research_snapshot = stage_context.get("market_research_snapshot", {}) or {}
    quant_system_available = bool(stage_context.get("quant_system_available", False))
    stop_prior_low_trading_days = int(stage_context.get("stop_prior_low_trading_days", 3) or 3)

    normalize_stock_code = stage_context["normalize_stock_code"]
    get_execution_framework_text = stage_context["get_execution_framework_text"]
    get_trade_permission = stage_context["get_trade_permission"]
    fetch_recent_price_bars = stage_context["fetch_recent_price_bars"]
    evaluate_live_tradability = stage_context["evaluate_live_tradability"]
    build_intraday_execution_plan = stage_context["build_intraday_execution_plan"]
    build_stop_execution_plan = stage_context["build_stop_execution_plan"]
    enrich_stop_plan_with_reference_anchors = stage_context["enrich_stop_plan_with_reference_anchors"]
    build_waiting_stock_plan = stage_context["build_waiting_stock_plan"]
    finalize_waiting_candidate = stage_context["finalize_waiting_candidate"]
    build_trade_price_focus = stage_context["build_trade_price_focus"]
    build_observation_price_focus_text = stage_context["build_observation_price_focus_text"]
    append_price_focus_note = stage_context["append_price_focus_note"]
    append_observation_price_focus_note = stage_context["append_observation_price_focus_note"]
    compose_observation_focus_text = stage_context["compose_observation_focus_text"]
    build_front_structure_layer_text = stage_context["build_front_structure_layer_text"]
    analyze_buy_signal = stage_context.get("analyze_buy_signal")
    safe_float = stage_context.get("safe_float", float)

    stage_label = str(stage_meta.get("label", "") or "Step 4").strip() or "Step 4"
    next_stage_label = get_execution_stage_label(stage_lookup, "pk_decision") if stage_lookup else "Step 5"

    lines = [
        f"#### {stage_label} - 明日买点预计算",
        "> **核心问题**：基于今日收盘数据，明天什么价格可以买？预计算买点区域，明日盘中触发即执行。",
        "> **预计算逻辑**：明日甜品区 = 今日ZD × (1±3%)，明日突破价 = 今日ZG × 1.02",
        f"> **怎么执行**：{get_execution_framework_text()}",
        "> **说明**：日报这里只给日线结构预案，真正盘中执行时，买点要等首个60分钟K线确认，止损要落到30分钟结构上。",
        "",
        f"**{stage_label}.0 交易优先级纪律**:",
    ]

    conviction_codes = {
        normalize_stock_code(stock.get("code", ""))
        for stock in (extreme_conviction_list or [])
        if stock.get("code")
    }
    leader_memory_codes = {
        normalize_stock_code(stock.get("code", ""))
        for stock in (leader_memory_bank or [])
        if stock.get("code")
    }

    if extreme_conviction_list:
        names = [f"{stock.get('name')}({stock.get('code')})" for stock in extreme_conviction_list]
        lines.append(f"- **极度看好优先**: {', '.join(names)}")
        lines.append("- **先后顺序怎么排**: 先做主线锚定龙，再看普通候选；若极度看好名单全天都不给确认，其余标的宁可继续观察。")
    else:
        lines.append("- **现在先按什么原则**: 没有极度看好的少数标的时，宁可降低频率，也不扩大出手范围。")
    if leader_memory_bank:
        memory_names = [f"{stock.get('name')}({stock.get('code')})" for stock in leader_memory_bank[:3]]
        lines.append(f"- **龙头回看名单**: {', '.join(memory_names)}")
    lines.append("- **盯盘优先级**: 核心可买 > 龙头回看 > 主线盯盘 > 普通观察。没有买入资格，买点到了也只能看。")
    lines.append("- **盘中异动怎么处理**: 绿灯可进入执行层，黄灯保留观察，橙灯先看是否跌得下去，红灯直接取消执行。")
    lines.append("- **纪律补充**: 强者恒强阶段只做领先核心，不为“低位没涨”找理由。")
    lines.append("")

    executable_stocks = []
    waiting_stocks = []
    untradable_stocks = []
    rejected_stocks = []

    if quant_system_available and focus_group:
        lines.append(f"**{stage_label}.1 明日买点预计算表**:")
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
        lines.append(f"**{stage_label}.1 买点判断** (量化系统不可用，使用基础判断):")
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
                stop_plan = enrich_stop_plan_with_reference_anchors(
                    stop_plan,
                    code,
                    target_date,
                    recent_bars=daily_anchor_bars,
                )
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
                stop_plan = enrich_stop_plan_with_reference_anchors(
                    stop_plan,
                    code,
                    target_date,
                    recent_bars=daily_anchor_bars,
                )
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
    lines.append(f"**{stage_label}.2 明日触发条件汇总**:")
    if untradable_stocks:
        lines.append(f"**强势但不可交易**（{len(untradable_stocks)}只，只做观察/记忆，不计执行）:")
        for item in untradable_stocks:
            lines.append(
                f"- ⚠️ {item.get('name')}({item.get('code')}) - "
                f"{(item.get('tradability_guard') or {}).get('status_label', '不可交易')}：{item.get('reason', '')}"
            )
        lines.append("")
    if executable_stocks:
        if final_gate.get("can_new_entry", False):
            lines.append(f"**明日可触发**（{len(executable_stocks)}只，满足条件即可买入）:")
        else:
            lines.append(f"**明天先观察谁**（{len(executable_stocks)}只，仅供观察，⛔{position_level}禁止买入）:")

        for item in executable_stocks:
            if "signal" in item:
                signal = item["signal"]
                entry_range = item.get("entry_range", (signal.entry_price, signal.entry_price))
                buy_type_map = {"panic_buy": "恐慌盘买入", "sweet_zone": "甜品区买入", "breakout": "放量突破"}
                buy_type = buy_type_map.get(signal.signal_type, signal.signal_type)
                stop_plan = item.get("stop_plan") or build_stop_execution_plan(
                    item.get("entry_price", signal.entry_price),
                    item.get("stop_loss"),
                    structure_label="日线预估结构止损",
                )
                minute_plan = item.get("minute_plan") or {}
                price_focus = build_trade_price_focus(minute_plan, stop_plan)
                confirm_price = minute_plan.get("confirm_price_60m")
                confirm_rule = minute_plan.get("confirm_rule_60m", "")
                confirm_text = f"{confirm_price:.2f}" if confirm_price else f"{entry_range[0]:.2f}-{entry_range[1]:.2f}"
                price_focus_text = (
                    price_focus.get("compact_text", "-")
                    if final_gate.get("can_new_entry", False)
                    else build_observation_price_focus_text(price_focus)
                )
                if final_gate.get("can_new_entry", False):
                    display_position_pct = safe_float(item.get("position_pct", signal.position_pct))
                    lines.append(
                        f"- ✅ {item.get('name')}({item.get('code')}) - {buy_type}，日线预设区间"
                        f"{entry_range[0]:.2f}-{entry_range[1]:.2f}；明日首个60分钟确认点{confirm_text}，仓位{display_position_pct:.0f}%"
                    )
                    if confirm_rule:
                        lines.append(f"  {item.get('permission_label', '执行权')}；{confirm_rule}；{price_focus_text}")
                    elif price_focus_text != "-":
                        lines.append(f"  {item.get('permission_label', '执行权')}；{price_focus_text}")
                    append_price_focus_note(lines, price_focus)
                else:
                    lines.append(
                        f"- ⏳ {item.get('name')}({item.get('code')}) - {buy_type}，日线预设区间"
                        f"{entry_range[0]:.2f}-{entry_range[1]:.2f}，60分钟确认点{confirm_text}，仅观察，禁止买入"
                    )
                    if price_focus_text != "-":
                        lines.append(f"  {price_focus_text}")
                    append_observation_price_focus_note(lines, price_focus)
            else:
                if final_gate.get("can_new_entry", False):
                    stop_plan = item.get("stop_plan")
                    minute_plan = item.get("minute_plan") or {}
                    price_focus = build_trade_price_focus(minute_plan, stop_plan)
                    confirm_price = minute_plan.get("confirm_price_60m")
                    confirm_rule = minute_plan.get("confirm_rule_60m", "")
                    price_focus_text = price_focus.get("compact_text", "-")
                    confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
                    lines.append(
                        f"- ✅ {item.get('name')}({item.get('code')}) - {item.get('permission_label', '执行权')}，"
                        f"明日60分钟确认点{confirm_text}后按{item.get('trigger')}执行"
                    )
                    if confirm_rule:
                        lines.append(f"  {confirm_rule}；{price_focus_text}")
                    elif price_focus_text != "-":
                        lines.append(f"  {price_focus_text}")
                    append_price_focus_note(lines, price_focus)
                else:
                    lines.append(f"- ⏳ {item.get('name')}({item.get('code')}) - 仅供观察：{item.get('trigger')}，禁止买入")
        lines.append("")

    if rejected_stocks:
        lines.append(f"**明天先回避谁**（{len(rejected_stocks)}只，已破位不碰）:")
        for item in rejected_stocks:
            lines.append(f"- ❌ {item.get('name')}({item.get('code')}) - {item.get('reason')}，明日不关注")
        lines.append("")

    if waiting_stocks:
        lines.append(f"**明日继续观察**（{len(waiting_stocks)}只，等买点出现）:")
        for item in waiting_stocks:
            reason = item.get("reason", "等待信号")
            minute_plan = item.get("minute_plan") or {}
            stop_plan = item.get("stop_plan")
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
            price_focus_text = build_observation_price_focus_text(price_focus)
            lines.append(f"- ⏳ {item.get('name')}({item.get('code')}) - {item.get('permission_label', '观察权')}：{reason}")
            lines.append(f"  {compose_observation_focus_text(confirm_text, price_focus_text)}")
            append_observation_price_focus_note(lines, price_focus)
        lines.append("")

    if final_gate.get("can_new_entry", False):
        lines.append(f"**{stage_label}.3 明日止损锚定**（买入后严格执行）:")
        if executable_stocks:
            lines.append("| 股票 | 怎么买 | 60分钟确认 | 关键位/带 | 执行止损 | 最晚硬止损 | 跌破动作 |")
            lines.append("|------|----------|------------|----------|----------|------------|----------|")
            for item in executable_stocks:
                if "signal" in item:
                    signal = item["signal"]
                    buy_type_map = {"panic_buy": "🚨恐慌盘", "sweet_zone": "甜品区", "breakout": "放量突破"}
                    buy_type = buy_type_map.get(signal.signal_type, signal.signal_type)
                    stop_plan = item.get("stop_plan") or build_stop_execution_plan(
                        item.get("entry_price", signal.entry_price),
                        item.get("stop_loss"),
                        structure_label="日线预估结构止损",
                    )
                    minute_plan = item.get("minute_plan") or {}
                    price_focus = build_trade_price_focus(minute_plan, stop_plan)
                    confirm_price = minute_plan.get("confirm_price_60m")
                    confirm_text = f"站上{confirm_price:.2f}" if confirm_price else f"{item.get('entry_price'):.2f}"
                    lines.append(
                        f"| {item.get('name')} | {buy_type} | {confirm_text} | "
                        f"{price_focus.get('key_zone_display', '-')} | {price_focus.get('execution_stop_display', '-')} | "
                        f"{price_focus.get('hard_stop_display', '-')} | 跌破执行止损立即卖 |"
                    )
                else:
                    stop_plan = item.get("stop_plan")
                    minute_plan = item.get("minute_plan") or {}
                    price_focus = build_trade_price_focus(minute_plan, stop_plan)
                    confirm_price = minute_plan.get("confirm_price_60m")
                    confirm_text = f"站上{confirm_price:.2f}" if confirm_price else "待盘中确认"
                    lines.append(
                        f"| {item.get('name')} | 基础判断 | {confirm_text} | "
                        f"{price_focus.get('key_zone_display', '-')} | {price_focus.get('execution_stop_display', '-')} | "
                        f"{price_focus.get('hard_stop_display', '-')} | 跌破执行止损立即卖 |"
                    )
            lines.append("")
            lines.append("- 前台把前低/支撑/止损压缩成同一个关键位/带；真正动作只看执行止损，最晚不超过单笔-5%。")
        else:
            lines.append("- 无可执行股票，暂不设置止损")
    else:
        lines.append(f"**{stage_label}.3 明日止损锚定**:")
        lines.append(f"- ⛔ {position_level}禁止买入，无需设置止损")
    lines.append("")

    step4_structure_layer_text = build_front_structure_layer_text(
        final_gate=final_gate,
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        position_level=position_level,
        state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
        target_date=target_date,
    )

    lines.append(f"**{stage_label} 结论**:")
    lines.append(f"- **现在是什么情况**: {step4_structure_layer_text}")
    if final_gate.get("can_new_entry", False) and executable_stocks:
        lines.append(f"- **接着做什么**: 继续进入{next_stage_label}筛选，只允许一只可买股留下来")
    elif waiting_stocks:
        lines.append("- **接着做什么**: 当前还在等待层，先等买点自己长出来")
    elif keep_group or executable_stocks:
        lines.append("- **接着做什么**: 当前只保留观察权，不做任何新买入")
    else:
        lines.append("- **明天先怎么观察**: 当前没有需要特别盯的执行记录，先看市场自己给答案")
    if untradable_stocks:
        lines.append(f"- **哪些票看着强但买不进去**: {len(untradable_stocks)}只（如一字/连续一字，只记观察不计执行收益）")
    lines.append(f"- **执行节奏**: {get_execution_framework_text()}")
    if final_gate.get("can_new_entry", False):
        lines.append("- **⚠️ 重要**: 以上买点基于今日收盘数据预计算，明日若直接高开离买点>5%，则放弃；即便满足价格条件，也要等60分钟确认后再买")
    else:
        lines.append(f"- **⛔ 档位限制**: {position_level}，禁止任何买入操作")
    lines.append("")

    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成明日买点预计算阶段",
        stage_key=stage_meta.get("stage_key", "entry_plan"),
        executable_count=len(executable_stocks),
        waiting_count=len(waiting_stocks),
        untradable_count=len(untradable_stocks),
        rejected_count=len(rejected_stocks),
    )
    return {
        "lines": lines,
        "exports": {
            "conviction_codes": conviction_codes,
            "leader_memory_codes": leader_memory_codes,
            "executable_stocks": executable_stocks,
            "waiting_stocks": waiting_stocks,
            "untradable_stocks": untradable_stocks,
            "rejected_stocks": rejected_stocks,
            "step4_structure_layer_text": step4_structure_layer_text,
        },
        "module_logs": logs,
    }
