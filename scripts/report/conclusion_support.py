def get_watch_anchor_note(watch_anchor):
    return str((watch_anchor or {}).get("watch_anchor_note", "") or "").strip()


def format_stock_label(stock):
    if not isinstance(stock, dict):
        return str(stock or "").strip()
    name = str(stock.get("name", "") or "").strip()
    code = str(stock.get("code", "") or "").strip()
    if name and code:
        return f"{name}({code})"
    return name or code or "-"


def resolve_today_focus_items(context):
    direct_items = context.get("today_validated_items")
    if direct_items is not None:
        return list(direct_items or [])
    tracking_memory_status = context.get("tracking_memory_status", {}) or {}
    return list(tracking_memory_status.get("today_validated_items", []) or [])


def build_market_outlook_text(context):
    prediction_text = str(context.get("step0_prediction_cn", "") or "").strip()
    action_text = str(context.get("step0_action", "") or "").strip()
    final_gate = context.get("final_gate") or {}
    parts = [part for part in (prediction_text, action_text) if part]
    if parts:
        return "；".join(parts)
    fallback_action = str(final_gate.get("final_action", "") or "").strip()
    if fallback_action:
        return fallback_action
    mainline_text = str(context.get("mainline_label") or context.get("mainline_name") or "").strip()
    if mainline_text:
        return f"先看{mainline_text}是否继续强化"
    return "先看环境确认，不抢判断"


def build_focus_recap_text(context):
    today_focus_items = resolve_today_focus_items(context)
    if today_focus_items:
        parts = []
        for item in today_focus_items[:3]:
            stock_label = format_stock_label(item)
            state_text = str(
                item.get("follow_state")
                or item.get("summary")
                or item.get("status")
                or ""
            ).strip()
            if not state_text:
                sources = [str(source or "").strip() for source in item.get("sources", []) if str(source or "").strip()]
                state_text = f"来自{'/'.join(sources)}" if sources else "继续观察"
            parts.append(f"{stock_label}：{state_text}")
        return "；".join(parts)

    best_stock = context.get("best_stock") or {}
    if best_stock:
        return f"{format_stock_label(best_stock)}：已缩成明天唯一执行候选"

    watch_anchor = context.get("watch_anchor") or {}
    if watch_anchor:
        note_text = get_watch_anchor_note(watch_anchor)
        recap_text = f"{format_stock_label(watch_anchor)}：继续作为重点观察对象"
        if note_text:
            recap_text = f"{recap_text}；{note_text}"
        return recap_text

    return "今天没有新增可信关注对象，明天先空仓观察"


def build_candidate_trade_directive(context):
    core_count = int(context.get("core_count", 0) or 0)
    secondary_count = int(context.get("secondary_count", 0) or 0)
    crossline_count = int(context.get("crossline_count", 0) or 0)
    summary = f"{core_count}只主线核心 / {secondary_count}只备选 / {crossline_count}只跨线观察"

    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    if best_stock:
        directive = f"先只在主线核心里做减法，目标缩到{format_stock_label(best_stock)}"
    elif core_count > 0:
        directive = "先只在主线核心里做减法，不把跨线对象直接当买点"
    elif watch_anchor:
        directive = f"主线核心还不够，只把{format_stock_label(watch_anchor)}当观察锚点"
    else:
        directive = "当前还没缩出可执行对象，先继续观察"
    return f"{summary}；{directive}"


def derive_trade_style(context):
    explicit_style = str(context.get("trade_style", "") or "").strip()
    if explicit_style:
        return explicit_style
    position_level = str(context.get("position_level", "") or "").strip()
    if "空仓" in position_level:
        return "空仓"
    final_gate = context.get("final_gate") or {}
    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    style_switch = context.get("style_switch", {}) or {}
    style_label = str(
        context.get("market_style_label")
        or context.get("style_label")
        or style_switch.get("style_label", "")
        or ""
    ).strip()
    if final_gate and final_gate.get("can_new_entry") is False:
        return "空仓"
    if style_label and any(keyword in style_label for keyword in ("趋势", "波段")) and (best_stock or watch_anchor):
        return "波段"
    if best_stock:
        return "短线"
    if watch_anchor:
        return "观察"
    return "空仓"


def build_risk_trade_note(context):
    best_stock = context.get("best_stock") or {}
    rr = best_stock.get("r_reward_ratio")
    if rr not in (None, ""):
        return f"只接受预估赚赔比 1:{float(rr):.1f} 的试错，不接受大亏硬扛"
    final_gate = context.get("final_gate") or {}
    position_level = str(context.get("position_level", "") or "").strip()
    if (final_gate and final_gate.get("can_new_entry") is False) or "空仓" in position_level:
        return "先守回撤，空仓也不承担大亏"
    return "只接受小亏试错，不接受大亏硬扛"


def derive_risk_guard_text(context):
    best_stock = context.get("best_stock") or {}
    rr = best_stock.get("r_reward_ratio")
    if rr not in (None, ""):
        return f"预估赚赔比 1:{float(rr):.1f}；先小亏小赚，等偶尔大赚；最晚单笔不超过-5%"
    final_gate = context.get("final_gate") or {}
    if final_gate and final_gate.get("can_new_entry") is False:
        return "当前先守住回撤，不为不确定性承担大亏"
    return "先守纪律，再等赔率；没有确认前不为收益承担大亏"
