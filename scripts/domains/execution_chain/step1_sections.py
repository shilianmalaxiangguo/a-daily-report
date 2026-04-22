def inject_step0_research_sections(
    report_lines,
    *,
    market_research_snapshot,
    step0_plan,
    display_mvp_mode,
    render_market_research_snapshot_section,
    render_step0_follow_section,
):
    for idx, line in enumerate(report_lines):
        if line == "<!-- MARKET_RESEARCH_SNAPSHOT_PLACEHOLDER -->":
            report_lines[idx : idx + 1] = render_market_research_snapshot_section(
                market_research_snapshot,
                compact=display_mvp_mode,
            )
            break

    for idx, line in enumerate(report_lines):
        if line == "<!-- STEP0_FOLLOW_PLACEHOLDER -->":
            report_lines[idx : idx + 1] = render_step0_follow_section(
                step0_plan,
                market_research_snapshot,
                compact=display_mvp_mode,
            )
            break


def build_step1_watch_sections(
    *,
    sector_trend_snapshot_step1,
    mainline_competition_snapshot,
    leader_memory_bank,
    tracking_memory_status,
    watchlist,
    abnormal_watch_pool,
    abnormal_projection_summary,
    filtered_by_a_kill,
    display_mvp_mode,
    is_degraded_abnormal_snapshot,
    format_abnormal_observation_columns,
):
    lines = []
    sector_trend_snapshot_step1 = sector_trend_snapshot_step1 or []
    mainline_competition_snapshot = mainline_competition_snapshot or []
    leader_memory_bank = leader_memory_bank or []
    tracking_memory_status = tracking_memory_status or {}
    watchlist = watchlist or []
    abnormal_watch_pool = abnormal_watch_pool or []
    abnormal_projection_summary = abnormal_projection_summary or {}
    filtered_by_a_kill = filtered_by_a_kill or []

    lines.append("#### Step 1 - 明天观察池")
    lines.append("> **核心问题**：基于今日各种形态，预判哪些股票明天还有可能延续强势？")
    lines.append("> **预判逻辑**：首板启动 > 炸板反包 > 烂板弱转强 > 跟风套利")
    lines.append("")

    if sector_trend_snapshot_step1:
        lines.append("**Step 1.0 主线趋势密度扫描**（先看哪条线里活跃趋势股最多）")
        lines.append("| 板块 | 活跃趋势股 | 强势候选 | 涨停家数 | 锚定龙头 | 结论 |")
        lines.append("|------|------------|----------|----------|----------|------|")
        sector_preview = sector_trend_snapshot_step1[:3] if display_mvp_mode else sector_trend_snapshot_step1
        for item in sector_preview:
            anchor_text = f"{item.get('anchor_name', '-')}"
            if item.get("anchor_code"):
                anchor_text += f"({item.get('anchor_code')})"
            lines.append(
                f"| {item.get('sector', '-')} | {item.get('trend_count', 0)}只 | "
                f"{item.get('strong_count', 0)}只 | {item.get('limit_up_count', 0)}只 | "
                f"{anchor_text} | {item.get('anchor_reason', '-')} |"
            )
        lines.append("")

    if mainline_competition_snapshot:
        lines.append("**Step 1.01 主线竞争格局**（不是板块名单，而是能量争夺排序）")
        lines.append("| 角色 | 方向 | 当前证据 | 判断 | 操作原则 |")
        lines.append("|------|------|----------|------|----------|")
        for item in mainline_competition_snapshot:
            lines.append(
                f"| {item.get('role', '-')} | {item.get('sector', '-')} | {item.get('evidence', '-')} | "
                f"{item.get('judgement', '-')} | {item.get('action', '-')} |"
            )
        lines.append("")

    if leader_memory_bank:
        lines.append("**Step 1.05 龙头记忆库**（第一次异动先记住，后面优先回看这些）")
        lines.append("| 股票 | 代码 | 板块 | 记忆理由 | 回看窗口 | 明日原则 |")
        lines.append("|------|------|------|----------|----------|----------|")
        for item in leader_memory_bank:
            lines.append(
                f"| {item.get('name', '-')} | {item.get('code', '-')} | {item.get('sector', '-')} | "
                f"{item.get('remember_reason', '-')} | {item.get('remember_window', '-')} | {item.get('action_rule', '-')} |"
            )
        lines.append("")

    lines.append("**Step 1.06 跟踪记忆校验**（昨天的观察先验尸，活下来才允许继续跟）")
    lines.append(f"- **今日重新校验**: {tracking_memory_status.get('today_seen_count', 0)}只")
    lines.append(f"- **升级为可信记忆**: {len(tracking_memory_status.get('promoted_items', []))}只")
    lines.append(f"- **继续作为临时假设**: {len(tracking_memory_status.get('today_tentative_items', []))}只")
    lines.append(f"- **今日剔除旧记忆**: {len(tracking_memory_status.get('dropped_items', []))}只")
    lines.append("- **防错纪律**: 历史记忆只影响跟踪优先级，不直接产生买点；今天没再出现或今天已经转弱，就自动降级/清除。")
    trusted_items = tracking_memory_status.get("today_validated_items", [])[:3]
    if trusted_items:
        lines.append("| 可信记忆 | 代码 | 状态 | 今日证据 | 原则 |")
        lines.append("|----------|------|------|----------|------|")
        for item in trusted_items:
            sources = " / ".join(item.get("sources", [])[:3]) or "-"
            follow_state = item.get("follow_state", "") or "今日再次入池"
            lines.append(
                f"| {item.get('name', '-')} | {item.get('code', '-')} | 已二次确认 | {sources} + {follow_state} | 只保留优先回看权，不直接给执行权 |"
            )
    elif tracking_memory_status.get("new_items"):
        lines.append("- **现在是什么情况**: 还没有形成可信记忆，今天出现的更多是新假设，不能直接当真。")
    else:
        lines.append("- **现在是什么情况**: 暂无可信记忆资产，说明系统宁可不记，也不强行继承旧判断。")
    if tracking_memory_status.get("dropped_items"):
        dropped_preview = tracking_memory_status.get("dropped_items", [])[:3]
        dropped_text = "；".join(
            f"{item.get('name', '-') or item.get('code', '-')}({item.get('code', '-')}) {item.get('reason', '')}"
            for item in dropped_preview
        )
        lines.append(f"- **今日自动清除**: {dropped_text}")
    lines.append("")

    lines.append("**Step 1.1 明日预期强度排序**（按今日形态预判明日延续性）")
    lines.append("")
    if watchlist:
        lines.append("| 排名 | 股票 | 代码 | 所属板块 | 今日形态 | 预判分数 | 明日预期 | 核心逻辑 |")
        lines.append("|------|------|------|----------|----------|----------|----------|----------|")
        watchlist_preview = watchlist[:5] if display_mvp_mode else watchlist[:12]
        for idx, item in enumerate(watchlist_preview, 1):
            lines.append(
                f"| {idx} | {item.get('name', '-')} | {item.get('code', '-')} | {item.get('sector', '-')} | "
                f"{item.get('pattern', '-')} | {item.get('score', 0)}分 | {item.get('tomorrow_expectation', '-')} | {item.get('reason', '-')} |"
            )
        lines.append("")

        lianban_expect = [item for item in watchlist if "连板" in item.get("tomorrow_expectation", "")][:5]
        premium_expect = [item for item in watchlist if "溢价" in item.get("tomorrow_expectation", "")][:3]
        fanbao_expect = [item for item in watchlist if "反包" in item.get("tomorrow_expectation", "")][:3]
        lines.append("**Step 1.2 明日预期分组**:")
        if lianban_expect:
            names = ", ".join([f"{item['name']}({item['code']})" for item in lianban_expect])
            lines.append(f"- **🔥 连板预期**（{len(lianban_expect)}只）: {names}")
        if premium_expect:
            names = ", ".join([f"{item['name']}({item['code']})" for item in premium_expect])
            lines.append(f"- **⭐ 溢价预期**（{len(premium_expect)}只）: {names}")
        if fanbao_expect:
            names = ", ".join([f"{item['name']}({item['code']})" for item in fanbao_expect])
            lines.append(f"- **🔄 反包预期**（{len(fanbao_expect)}只）: {names}")
        lines.append("")
    else:
        lines.append("**观察池为空**: 今日没有符合明日延续预期的标的。")
        lines.append("")

    if abnormal_watch_pool:
        lines.append("**Step 1.3 异动后观察池**（不是追异动，而是看异动后能不能跌下去）")
        lines.append("| 股票 | 代码 | 板块 | 异动日 | 标准Setup | 后续状态 | 历史异动锚点 | 次日观察边界 | 明日原则 |")
        lines.append("|------|------|------|--------|-----------|----------|--------------|--------------|----------|")
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
    else:
        lines.append("**Step 1.3 异动后观察池**: 暂无明确的异动后跟踪对象，说明今天可记忆的异常K线还不够集中。")
        lines.append("")

    lines.append("**Step 1.35 异常投影总结**（用二维异常去反推更高维的状态变化）")
    lines.append(
        f"- **当前投影**: {abnormal_projection_summary.get('projection_label', '-')}"
        f"；承接{abnormal_projection_summary.get('resilient_count', 0)}只 / 转弱{abnormal_projection_summary.get('failed_count', 0)}只"
    )
    lines.append(f"- **投影解释**: {abnormal_projection_summary.get('projection_reason', '-')}")
    if abnormal_projection_summary.get("setup_breakdown"):
        setup_text = " / ".join(f"{label}{count}只" for label, count in abnormal_projection_summary.get("setup_breakdown", []))
        lines.append(f"- **Setup分布**: {setup_text}")
    lines.append(f"- **接着做什么**: {abnormal_projection_summary.get('action', '-')}")
    lines.append("")

    if filtered_by_a_kill:
        lines.append(f"**Step 1.4 A杀过滤**（剔除{len(filtered_by_a_kill)}只）:")
        for candidate, record in filtered_by_a_kill[:5]:
            lines.append(f"- ❌ {candidate.get('name')}({candidate.get('code')}) - A杀日{record.get('a_kill_date')} - 剩余{record.get('remaining_days')}天禁买")
        lines.append("")

    lines.append("**Step 1 结论**:")
    lines.append(f"- **明天观察池**: {len(watchlist)}只，按今日形态预判明日延续性排序")
    lines.append("- **核心逻辑**: 一字板/T字板 > 光头涨停 > 放量涨停 > 反包候选")
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
    lines.append("- **接着做什么**: 进入Step 2，从观察池识别明日核心标的")
    lines.append("- **重要**: 明日开盘前需重新确认这些标的的竞价情况")
    lines.append("")
    return lines
