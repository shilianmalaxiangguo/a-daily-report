from report.surface_wording import sanitize_user_visible_text


def build_pk_decision_pk_context_node(context, node_meta=None, node_lookup=None):
    trade_gate_open = context.get("trade_gate_open", False)
    display_pending_candidates = context.get("display_pending_candidates", context.get("pending_candidates", [])) or []
    display_observation_candidates = context.get("display_observation_candidates", context.get("observation_candidates", [])) or []
    best_stock = context.get("best_stock")
    watch_anchor = context.get("watch_anchor")
    watch_anchor_type = context.get("watch_anchor_type", "")
    position_level = str(context.get("position_level", "") or "").strip()
    final_gate = context.get("final_gate", {}) or {}
    front_structure_layer_text = context.get("front_structure_layer_text", "")

    safe_float = context.get("safe_float", lambda value, default=0.0: float(default if value in (None, "") else value))
    build_trade_price_focus = context.get("build_trade_price_focus", lambda minute_plan, stop_plan: {})
    build_observation_price_focus_text = context.get("build_observation_price_focus_text", lambda price_focus: "-")
    should_surface_price_note = context.get("should_surface_price_note", lambda price_focus: False)
    build_observation_price_note_text = context.get("build_observation_price_note_text", lambda price_focus: "-")
    append_watch_anchor_note = context.get("append_watch_anchor_note", lambda report_lines, candidate, prefix="  ": None)
    compose_observation_focus_text = context.get(
        "compose_observation_focus_text",
        lambda confirm_text, observation_price_focus_text: f"{confirm_text} / {observation_price_focus_text}",
    )
    build_stop_execution_plan = context.get("build_stop_execution_plan", lambda *args, **kwargs: {})

    pending_lines = []
    if trade_gate_open:
        if display_pending_candidates:
            if len(display_pending_candidates) >= 2:
                pending_lines.append(f"**重点盯盘股排序**（{len(display_pending_candidates)}只，先看谁最可能走成明天唯一能买的那只）:")
                pending_lines.append("| 股票 | 来源 | 60分钟确认点 | 候选顺位 | 说明 |")
                pending_lines.append("|------|------|--------------|----------|------|")
                for idx, candidate in enumerate(display_pending_candidates[:5], 1):
                    minute_plan = candidate.get("minute_plan") or {}
                    confirm_price = minute_plan.get("confirm_price_60m")
                    confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
                    source_text = candidate.get("permission_label", "候选")
                    note = candidate.get("reason", candidate.get("permission_reason", "等待盘中确认"))
                    pending_lines.append(
                        f"| {candidate.get('name')} | {source_text} | {confirm_text} | 第{idx}顺位 | {note} |"
                    )
                pending_lines.append("")
            top_pending = display_pending_candidates[0]
            top_minute_plan = top_pending.get("minute_plan") or {}
            top_stop_plan = top_pending.get("stop_plan")
            top_price_focus = build_trade_price_focus(top_minute_plan, top_stop_plan)
            top_confirm_price = top_minute_plan.get("confirm_price_60m")
            top_price_focus_text = build_observation_price_focus_text(top_price_focus)
            pending_lines.append(f"**明天先盯哪只**: {top_pending.get('name')}({top_pending.get('code')})")
            pending_lines.append(
                f"- **原因**: {top_pending.get('permission_reason', top_pending.get('reason', '当前先看它能否继续证明自己'))}"
            )
            if top_confirm_price:
                pending_lines.append(f"- **60分钟确认点**: {top_confirm_price:.2f}")
            if top_price_focus_text and top_price_focus_text != "-":
                pending_lines.append(f"- **价格怎么盯**: {top_price_focus_text}")
            if should_surface_price_note(top_price_focus):
                pending_lines.append(f"- **价格怎么看**: {build_observation_price_note_text(top_price_focus)}")
            pending_lines.append("- **升级条件**: 明日先完成60分钟确认，再走成明天唯一能买的那只，不能直接追价")
            pending_lines.append("")
        else:
            pending_lines.extend(["**当前没有能下手的票**: 无需PK", ""])

    observation_lines = []
    if not trade_gate_open:
        if display_observation_candidates:
            if len(display_observation_candidates) >= 2:
                observation_lines.append(f"**先看谁排第几**（{len(display_observation_candidates)}只，优先盯强分歧但没坏的对象）:")
                observation_lines.append("| 股票 | 来源 | 买点 | 60分钟确认点 | 先看顺序 | 说明 |")
                observation_lines.append("|------|------|------|--------------|------------|------|")
                source_label_map = {
                    "execute_layer": "执行层",
                    "keep_group_watch": "观察组",
                    "waiting_layer": "等待层",
                    "abnormal_probe": "异常层",
                }
                for idx, candidate in enumerate(display_observation_candidates[:5], 1):
                    signal = candidate.get("signal")
                    minute_plan = candidate.get("minute_plan") or {}
                    confirm_price = minute_plan.get("confirm_price_60m")
                    confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
                    buy_type_map = {"sweet_zone": "甜品区", "breakout": "突破", "panic_buy": "恐慌盘"}
                    buy_type = buy_type_map.get(signal.signal_type, signal.signal_type) if signal else "基础"
                    source_text = source_label_map.get(candidate.get("watch_source", ""), "观察")
                    note = candidate.get("watch_priority_label", "观察")
                    if idx == 1:
                        note = f"{note}，优先看它能否继续证明自己"
                    observation_lines.append(
                        f"| {candidate.get('name')} | {source_text} | {buy_type} | {confirm_text} | 第{idx}顺位 | {note} |"
                    )
                observation_lines.append("")
            top_watch = display_observation_candidates[0]
            top_signal = top_watch.get("signal")
            observation_lines.append(f"**观察优先锚点**: {top_watch.get('name')}({top_watch.get('code')})")
            observation_lines.append(
                f"- **原因**: {top_watch.get('watch_priority_label', '观察优先')}；"
                f"{top_watch.get('reason', top_watch.get('tomorrow_risk', '当前优先盯它的承接变化'))}"
            )
            if top_signal:
                entry_range = top_watch.get("entry_range", (top_signal.entry_price, top_signal.entry_price))
                minute_plan = top_watch.get("minute_plan") or {}
                stop_plan = top_watch.get("stop_plan")
                price_focus = build_trade_price_focus(minute_plan, stop_plan)
                confirm_price = minute_plan.get("confirm_price_60m")
                observation_price_focus_text = build_observation_price_focus_text(price_focus)
                observation_lines.append(f"- **跟踪区间**: {entry_range[0]:.2f}-{entry_range[1]:.2f}")
                if confirm_price:
                    observation_lines.append(f"- **60分钟确认点**: {confirm_price:.2f}")
                if observation_price_focus_text and observation_price_focus_text != "-":
                    observation_lines.append(f"- **价格怎么盯**: {observation_price_focus_text}")
                if should_surface_price_note(price_focus):
                    observation_lines.append(f"- **价格怎么看**: {build_observation_price_note_text(price_focus)}")
                observation_lines.append(f"- **参考依据**: {top_watch.get('ev_model_source', '类型先验')}")
                observation_lines.append("- **观察纪律**: 只记录是否继续走强，不构成明日买入指令")
            observation_lines.append("")
        else:
            observation_lines.extend(["**无执行资格候选**: 当前没有进入执行层的标的，只保留观察池", ""])

    conclusion_lines = ["**结论**:"]
    if best_stock:
        signal = best_stock.get("signal")
        if signal:
            entry_range = best_stock.get("entry_range", (signal.entry_price, signal.entry_price))
            buy_type_map = {
                "sweet_zone": "甜品区买入",
                "breakout": "放量突破买入",
                "panic_buy": "恐慌盘买入",
            }
            buy_type = buy_type_map.get(signal.signal_type, signal.signal_type)
            conclusion_lines.append(f"- **如果要买只买谁**: {best_stock.get('name')}({best_stock.get('code')})")
            conclusion_lines.append(f"- **怎么买**: {buy_type}")
            conclusion_lines.append(f"- **到什么价位再动手**: {entry_range[0]:.2f}-{entry_range[1]:.2f}")
            display_position_pct = safe_float(best_stock.get("position_pct", signal.position_pct))
            conclusion_lines.append(f"- **仓位放多少**: {display_position_pct:.0f}%")
            stop_plan = best_stock.get("stop_plan") or build_stop_execution_plan(
                signal.entry_price,
                best_stock.get("stop_loss", signal.stop_loss),
                structure_label="日线预估结构止损",
            )
            minute_plan = best_stock.get("minute_plan") or {}
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            if confirm_price:
                conclusion_lines.append(f"- **60分钟确认点**: {confirm_price:.2f}")
            conclusion_lines.append(f"- **价格怎么盯**: {price_focus.get('compact_text', '-')}")
            if should_surface_price_note(price_focus):
                conclusion_lines.append(f"- **价格怎么看**: {price_focus.get('note_text', '-')}")
            conclusion_lines.append(f"- **参考依据**: {best_stock.get('ev_model_source', '类型先验')}")
            conclusion_lines.append("- **出手时怎么做**: 明日仅在60分钟确认后买入，买后用30分钟结构止损，最晚不超过单笔-5%；其他标的无论多诱人都**禁止操作**")
        else:
            conclusion_lines.append(f"- **如果要买只买谁**: {best_stock.get('name')}({best_stock.get('code')})")
            conclusion_lines.append("- **出手时怎么做**: 明日仅在60分钟确认后按条件触发买入，买后用30分钟结构止损，其他标的禁止操作")
    else:
        if trade_gate_open and watch_anchor:
            conclusion_lines.append(f"- **明天先盯哪只**: {watch_anchor.get('name')}({watch_anchor.get('code')})")
            conclusion_lines.append("- **现在是什么情况**: 市场允许出手，但还没有缩到一只可买股，明日先等它自己证明")
        else:
            conclusion_lines.append("- **明天没有可买对象**: 明日不产生买入动作")
        conclusion_lines.append(f"- **明天能不能开仓**: {front_structure_layer_text}")
        if watch_anchor:
            minute_plan = watch_anchor.get("minute_plan") or {}
            stop_plan = watch_anchor.get("stop_plan")
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
            observation_price_focus_text = build_observation_price_focus_text(price_focus)
            conclusion_lines.append(f"- **{watch_anchor_type}**: {watch_anchor.get('name')}({watch_anchor.get('code')})")
            conclusion_lines.append(
                f"- **{'现在重点盯什么' if trade_gate_open else '现在重点看什么'}**: "
                f"{compose_observation_focus_text(confirm_text, observation_price_focus_text)}"
            )
            append_watch_anchor_note(conclusion_lines, watch_anchor)
            if should_surface_price_note(price_focus):
                conclusion_lines.append(f"- **价格怎么看**: {build_observation_price_note_text(price_focus)}")
            if trade_gate_open:
                conclusion_lines.append("- **出手时怎么做**: 只能等它走成明天唯一能买的那只后再买，盘中强也不允许提前抢跑")
            elif final_gate.get("allow_conditional_30"):
                conclusion_lines.append("- **当前先不抢**: 二档防守观察，只在10点确认主线承接后评估30%条件试错")
            else:
                conclusion_lines.append(f"- **当前先不买**: {position_level}，当前只允许观察，不允许新买入")
        else:
            conclusion_lines.append("- **明天先怎么观察**: 空仓观望")
    conclusion_lines.append("")

    return {
        "lines": [],
        "exports": {
            "pending_lines": sanitize_user_visible_text(pending_lines),
            "observation_lines": sanitize_user_visible_text(observation_lines),
            "conclusion_lines": sanitize_user_visible_text(conclusion_lines),
        },
        "module_logs": [],
    }
