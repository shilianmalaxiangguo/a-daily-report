from report.surface_wording import sanitize_user_visible_text


def build_entry_plan_trigger_summary_node(context, node_meta=None, node_lookup=None):
    final_gate = context.get("final_gate", {}) or {}
    position_level = str(context.get("position_level", "") or "").strip()
    executable_stocks = context.get("executable_stocks", []) or []
    waiting_stocks = context.get("waiting_stocks", []) or []
    untradable_stocks = context.get("untradable_stocks", []) or []
    rejected_stocks = context.get("rejected_stocks", []) or []
    build_stop_execution_plan = context["build_stop_execution_plan"]
    build_trade_price_focus = context["build_trade_price_focus"]
    build_observation_price_focus_text = context["build_observation_price_focus_text"]
    append_price_focus_note = context["append_price_focus_note"]
    append_observation_price_focus_note = context["append_observation_price_focus_note"]
    compose_observation_focus_text = context["compose_observation_focus_text"]
    safe_float = context.get("safe_float", float)

    lines = ["**明日触发条件汇总**:"]
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
                        f"{entry_range[0]:.2f}-{entry_range[1]:.2f}；明日09:50-10:10观察价{confirm_text}，仓位{display_position_pct:.0f}%"
                    )
                    if confirm_rule:
                        lines.append(f"  {item.get('permission_label', '执行资格')}；{confirm_rule}；{price_focus_text}")
                    elif price_focus_text != "-":
                        lines.append(f"  {item.get('permission_label', '执行资格')}；{price_focus_text}")
                    append_price_focus_note(lines, price_focus)
                else:
                    lines.append(
                        f"- ⏳ {item.get('name')}({item.get('code')}) - {buy_type}，日线预设区间"
                        f"{entry_range[0]:.2f}-{entry_range[1]:.2f}，09:50-10:10观察价{confirm_text}，仅观察，禁止买入"
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
                        f"- ✅ {item.get('name')}({item.get('code')}) - {item.get('permission_label', '执行资格')}，"
                        f"明日09:50-10:10观察价{confirm_text}后按{item.get('trigger')}执行"
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

    return {"lines": sanitize_user_visible_text(lines), "exports": {}, "module_logs": []}
