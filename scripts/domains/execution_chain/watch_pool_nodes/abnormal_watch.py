def build_watch_pool_abnormal_watch_node(context, node_meta=None, node_lookup=None):
    abnormal_watch_pool = context.get("abnormal_watch_pool", []) or []
    display_mvp_mode = bool(context.get("display_mvp_mode", False))
    is_degraded_abnormal_snapshot = context["is_degraded_abnormal_snapshot"]
    format_abnormal_observation_columns = context["format_abnormal_observation_columns"]

    if abnormal_watch_pool:
        lines = [
            "**异动后观察池**（不是追异动，而是看异动后能不能跌下去）",
            "| 股票 | 代码 | 板块 | 异动日 | 标准Setup | 后续状态 | 历史异动锚点 | 次日观察边界 | 明日原则 |",
            "|------|------|------|--------|-----------|----------|--------------|--------------|----------|",
        ]
        abnormal_preview = abnormal_watch_pool[:3] if display_mvp_mode else abnormal_watch_pool
        for item in abnormal_preview:
            setup_label = item.get("setup_signal_label", item.get("abnormal_type", "-"))
            if is_degraded_abnormal_snapshot(item):
                setup_label = f"{setup_label}（降级快照，仅观察）"
            history_anchor_text, nextday_guard_text = format_abnormal_observation_columns(item)
            lines.append(
                f"| {item.get('name', '-')} | {item.get('code', '-')} | {item.get('sector', '-')} | {item.get('abnormal_date', '-')} | "
                f"{setup_label} | {item.get('follow_state', '-')} | {history_anchor_text} | {nextday_guard_text} | {item.get('action_rule', '-')} |"
            )
        lines.append("")
        return {"lines": lines, "exports": {}, "module_logs": []}

    return {
        "lines": ["**异动后观察池**: 暂无明确的异动后跟踪对象，说明今天可记忆的异常K线还不够集中。", ""],
        "exports": {},
        "module_logs": [],
    }
