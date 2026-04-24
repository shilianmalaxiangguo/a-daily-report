def build_candidate_selection_core_candidates_node(context, node_meta=None, node_lookup=None):
    core_stocks = context.get("core_stocks", []) or []
    primary_mainline = str(context.get("primary_mainline", "") or "").strip()
    display_mvp_mode = bool(context.get("display_mvp_mode", False))

    lines = ["**明日核心预判**（主线内可执行候选）:"]
    lines.append("> **异动加权纪律**：`跌不下去` 明显上调优先级，`缩量消化` 保留高位观察权，`已经转弱` 即使形态漂亮也会降级。")
    if primary_mainline:
        lines.append(f"> **主线过滤**：当前主攻线先缩到`{primary_mainline}`这条线；跨线强票单列观察，不直接授予执行权。")

    if core_stocks:
        lines.append("| 序号 | 股票 | 代码 | 板块 | 今日形态 | 异动跟踪 | 预判强度 | 核心级别 | 明日预判 |")
        lines.append("|------|------|------|------|----------|----------|----------|----------|----------|")
        core_preview = core_stocks[:2] if display_mvp_mode else core_stocks
        for idx, stock in enumerate(core_preview, 1):
            lines.append(
                f"| {idx} | {stock.get('name', '-')} | {stock.get('code', '-')} | {stock.get('sector', '-')} | "
                f"{stock.get('pattern', '-')} | {stock.get('abnormal_summary', '无明显异动')} | "
                f"{stock.get('tomorrow_strength', 0)}分 | {stock.get('core_level', '-')} | {stock.get('tmr_forecast', '-')} |"
            )
    else:
        lines.append("- 无明日核心股")

    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
