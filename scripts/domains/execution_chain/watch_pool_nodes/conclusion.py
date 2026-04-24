def build_watch_pool_conclusion_node(context, node_meta=None, node_lookup=None):
    watchlist = context.get("watchlist", []) or []
    abnormal_watch_pool = context.get("abnormal_watch_pool", []) or []
    mainline_competition_snapshot = context.get("mainline_competition_snapshot", []) or []
    abnormal_projection_summary = context.get("abnormal_projection_summary", {}) or {}
    sector_trend_snapshot_step1 = context.get("sector_trend_snapshot_step1", []) or []
    leader_memory_bank = context.get("leader_memory_bank", []) or []
    tracking_memory_status = context.get("tracking_memory_status", {}) or {}
    next_stage_label = str(context.get("next_stage_label", "") or "Step 2").strip() or "Step 2"

    lines = [
        "**结论**:",
        f"- **明天观察池**: {len(watchlist)}只，按今日形态预判明日延续性排序",
        "- **优先顺序**: 一字板/T字板 > 光头涨停 > 放量涨停 > 反包候选",
    ]
    if abnormal_watch_pool:
        resilient_count = len([item for item in abnormal_watch_pool if item.get("follow_state") in ["跌不下去", "缩量消化"]])
        lines.append(f"- **异动后跟踪**: {len(abnormal_watch_pool)}只里有{resilient_count}只处于“跌不下去/缩量消化”，优先留给明日60分钟确认")
    if mainline_competition_snapshot:
        lines.append(f"- **主线竞争格局**: {mainline_competition_snapshot[0].get('sector', '未知')}目前是主攻线，其他方向先看是否能继续争夺能量。")
    if abnormal_projection_summary:
        lines.append(f"- **异常投影视角**: {abnormal_projection_summary.get('projection_label', '-')}")
    if sector_trend_snapshot_step1:
        densest_sector = sector_trend_snapshot_step1[0]
        lines.append(
            f"- **趋势密度最高**: {densest_sector.get('sector', '未知')}，当前活跃趋势股{densest_sector.get('trend_count', 0)}只，优先盯{densest_sector.get('anchor_name', '锚定龙头')}"
        )
    if leader_memory_bank:
        memory_names = [f"{item.get('name')}({item.get('code')})" for item in leader_memory_bank[:3]]
        lines.append(f"- **龙头记忆优先**: {', '.join(memory_names)}")

    trusted_memory_names = [
        f"{item.get('name')}({item.get('code')})"
        for item in tracking_memory_status.get("today_validated_items", [])[:3]
    ]
    if trusted_memory_names:
        lines.append(f"- **历史可信跟踪**: {', '.join(trusted_memory_names)}（只影响优先回看，不直接给执行权）")
    elif tracking_memory_status.get("today_tentative_items"):
        lines.append("- **历史记忆状态**: 仍以临时假设为主，今天继续验证，不允许直接继承为买点")

    lines.append(f"- **接着做什么**: 进入{next_stage_label}，从观察池识别明日核心标的")
    lines.append("- **重要**: 明日开盘前需重新确认这些标的的竞价情况")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
