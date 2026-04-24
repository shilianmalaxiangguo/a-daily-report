def build_entry_plan_stop_anchor_node(context, node_meta=None, node_lookup=None):
    final_gate = context.get("final_gate", {}) or {}
    position_level = str(context.get("position_level", "") or "").strip()
    executable_stocks = context.get("executable_stocks", []) or []
    build_stop_execution_plan = context["build_stop_execution_plan"]
    build_trade_price_focus = context["build_trade_price_focus"]

    lines = []
    if final_gate.get("can_new_entry", False):
        lines.append("**明日止损锚定**（买入后严格执行）:")
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
        lines.append("**明日止损锚定**:")
        lines.append(f"- ⛔ {position_level}禁止买入，无需设置止损")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
