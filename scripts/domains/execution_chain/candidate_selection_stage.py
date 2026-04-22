from domains.execution_chain.stage_runtime import get_execution_stage_label


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.candidate_selection_stage",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _subheading(stage_label, suffix, title, tail=""):
    return f"**{stage_label}.{suffix} {title}**{tail}"


def build_candidate_selection_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    stage_lookup = stage_lookup or {}
    logs = []
    data = stage_context.get("data", {}) or {}
    target_date = stage_context.get("target_date", "")
    exit_analysis = stage_context.get("exit_analysis", {}) or {}
    candidates = stage_context.get("candidates", []) or []
    watchlist = stage_context.get("watchlist", []) or []
    abnormal_watch_map = stage_context.get("abnormal_watch_map", {}) or {}
    dragon_stocks = stage_context.get("dragon_stocks", []) or []
    zt_pool_by_sector = stage_context.get("zt_pool_by_sector", {}) or {}
    market_research_bundle = stage_context.get("market_research_bundle", {}) or {}
    main_sectors = stage_context.get("main_sectors", []) or []
    display_mvp_mode = bool(stage_context.get("display_mvp_mode", False))
    build_step2_candidate_bundle = stage_context["build_step2_candidate_bundle"]
    render_gem_breathing_step2_section = stage_context["render_gem_breathing_step2_section"]
    safe_float = stage_context["safe_float"]
    ai_analyze_sector_relationships = stage_context.get("ai_analyze_sector_relationships")

    stage_label = str(stage_meta.get("label", "") or "Step 2").strip() or "Step 2"
    title = str(stage_meta.get("title", "") or "明日核心标的").strip() or "明日核心标的"
    next_stage_label = get_execution_stage_label(stage_lookup, "risk_review") if stage_lookup else "Step 3"

    lines = [
        f"#### {stage_label} - {title}",
        "> **核心问题**：观察池里谁明天最有可能成为市场核心？基于今日封单强度、板块地位预判。",
        "> **预判维度**：明日竞价预期 > 板块龙一溢价 > 技术形态支撑 > 异动后抗跌性 > 跟风套利",
        "",
    ]

    step2_bundle = build_step2_candidate_bundle(
        data,
        exit_analysis=exit_analysis,
        candidates=candidates,
        watchlist=watchlist,
        abnormal_watch_map=abnormal_watch_map,
        dragon_stocks=dragon_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        gem_breathing_candidates=market_research_bundle.get("gem_breathing_candidates", []),
        target_date=target_date,
    )

    evaluated_stocks = step2_bundle.get("evaluated_stocks", [])
    core_stocks = step2_bundle.get("core_stocks", [])
    secondary_stocks = step2_bundle.get("secondary_stocks", [])
    ignored_stocks = step2_bundle.get("ignored_stocks", [])
    crossline_observation_stocks = step2_bundle.get("crossline_observation_stocks", [])
    gem_observation_stocks = step2_bundle.get("gem_observation_stocks", [])
    sector_trend_snapshot = step2_bundle.get("sector_trend_snapshot", [])
    extreme_conviction_list = step2_bundle.get("extreme_conviction_list", [])
    primary_mainline = (
        step2_bundle.get("mainline_name", "")
        or exit_analysis.get("sector_name", "")
        or (main_sectors[0] if main_sectors else "")
    )

    if sector_trend_snapshot:
        lines.append(_subheading(stage_label, "0", "主线趋势密度复核", "（不只看单个龙头，还看一条线里有多少活口）:"))
        lines.append("| 板块 | 活跃趋势股 | 核心候选 | 锚定龙头 | 密度分 | 交易含义 |")
        lines.append("|------|------------|----------|----------|--------|----------|")
        for item in sector_trend_snapshot:
            anchor_text = f"{item.get('anchor_name', '-')}"
            if item.get("anchor_code"):
                anchor_text += f"({item.get('anchor_code')})"
            lines.append(
                f"| {item.get('sector', '-')} | {item.get('trend_count', 0)}只 | "
                f"{item.get('core_count', 0)}只 | {anchor_text} | {item.get('density_score', 0)} | "
                f"{item.get('anchor_reason', '-')} |"
            )
        lines.append("")

    lines.append(_subheading(stage_label, "1", "明日核心预判", "（主线内可执行候选）:"))
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

    lines.append(_subheading(stage_label, "2", "明日次核心预判", "（主线内备选观察）:"))
    if secondary_stocks:
        lines.append("| 序号 | 股票 | 代码 | 板块 | 异动跟踪 | 预判强度 | 明日预期 |")
        lines.append("|------|------|------|------|----------|----------|----------|")
        secondary_preview = secondary_stocks[:2] if display_mvp_mode else secondary_stocks
        for idx, stock in enumerate(secondary_preview, 1):
            lines.append(
                f"| {idx} | {stock.get('name', '-')} | {stock.get('code', '-')} | {stock.get('sector', '-')} | "
                f"{stock.get('abnormal_summary', '无明显异动')} | {stock.get('tomorrow_strength', 0)}分 | {stock.get('tmr_forecast', '-')} |"
            )
    else:
        lines.append("- 无次核心股")
    lines.append("")

    if crossline_observation_stocks:
        lines.append(_subheading(stage_label, "25", "跨线观察候选", "（只看能量迁移，不作为主线执行对象）:"))
        lines.append("> **观察纪律**：跨线对象只用于确认资金是否外溢/切换，不代表主攻线已经切换。")
        lines.append("| 序号 | 股票 | 代码 | 板块 | 异动跟踪 | 预判强度 | 观察意义 | 明日原则 |")
        lines.append("|------|------|------|------|----------|----------|----------|----------|")
        crossline_preview = crossline_observation_stocks[:2] if display_mvp_mode else crossline_observation_stocks[:4]
        for idx, stock in enumerate(crossline_preview, 1):
            crossline_sector = stock.get("sector", "其他")
            follow_state = stock.get("abnormal_follow_state", "")
            if follow_state in ["跌不下去", "缩量消化"]:
                observation_reason = f"{crossline_sector}承接偏强，观察是否形成竞争线"
            else:
                observation_reason = f"{crossline_sector}有异动，先看是否只是情绪脉冲"
            lines.append(
                f"| {idx} | {stock.get('name', '-')} | {stock.get('code', '-')} | {crossline_sector} | "
                f"{stock.get('abnormal_summary', '无明显异动')} | {stock.get('tomorrow_strength', 0)}分 | "
                f"{observation_reason} | 只看强弱，不直接给买入指令 |"
            )
        lines.append("")

    if ignored_stocks:
        lines.append(_subheading(stage_label, "3", "暂不关注", f": {len(ignored_stocks)}只（预判明日强度不足）"))
        for stock in ignored_stocks[:3]:
            lines.append(
                f"- {stock.get('name')}({stock.get('code')}) - 强度{stock.get('tomorrow_strength', 0)}分 - "
                f"{stock.get('abnormal_summary', '无明显异动')} - {stock.get('tmr_forecast', '')}"
            )
        lines.append("")

    core_sectors = {}
    sector_strength = {}
    for stock in core_stocks + secondary_stocks:
        sector = stock.get("sector", "其他")
        core_sectors[sector] = core_sectors.get(sector, 0) + 1
        sector_strength[sector] = sector_strength.get(sector, 0) + stock.get("tomorrow_strength", 0)

    if primary_mainline:
        mainline_count = len(core_stocks) + len(secondary_stocks)
        mainline_strength = sum(safe_float(stock.get("tomorrow_strength", 0)) for stock in core_stocks + secondary_stocks)
        lines.append(_subheading(stage_label, "4", "明日核心方向预判", f": {primary_mainline}（主线内{mainline_count}只，主线内强度{int(mainline_strength)}分）"))
        lines.append(f"> **明日纪律**: 认准'{primary_mainline}'，只在主线里等最强对象自己走出来。")
        if crossline_observation_stocks:
            strongest_crossline = sorted(
                crossline_observation_stocks,
                key=lambda item: (
                    safe_float(item.get("tomorrow_strength", 0)),
                    safe_float(item.get("score", 0)),
                ),
                reverse=True,
            )[0]
            lines.append(
                f"> **跨线补充**: {strongest_crossline.get('sector', '其他')}里的{strongest_crossline.get('name', '-')}"
                "更像承接观察对象，不视为主攻线切换。"
            )
        lines.extend(
            render_gem_breathing_step2_section(
                gem_observation_stocks,
                filtered_out_gem_candidates=market_research_bundle.get("filtered_out_gem_breathing_candidates", []),
                display_mvp_mode=display_mvp_mode,
            )
        )
        lines.append("")
    elif core_sectors:
        sorted_sectors = sorted(core_sectors.items(), key=lambda item: (item[1], sector_strength[item[0]]), reverse=True)
        main_sector = sorted_sectors[0]
        lines.append(_subheading(stage_label, "4", "明日核心方向预判", f": {main_sector[0]}（{main_sector[1]}只，板块强度{sector_strength.get(main_sector[0], 0)}分）"))
        lines.append(f"> **明日纪律**: 认准'{main_sector[0]}'，明日若该板块竞价强势，就干该板块核心")
        lines.extend(
            render_gem_breathing_step2_section(
                gem_observation_stocks,
                filtered_out_gem_candidates=market_research_bundle.get("filtered_out_gem_breathing_candidates", []),
                display_mvp_mode=display_mvp_mode,
            )
        )
        lines.append("")

    lines.append(_subheading(stage_label, "5", "极度看好名单", "（只保留最心动的少数，其他只观察）:"))
    if extreme_conviction_list:
        lines.append("| 优先级 | 股票 | 代码 | 所属板块 | 极看理由 | 明日原则 |")
        lines.append("|--------|------|------|----------|----------|----------|")
        for idx, stock in enumerate(extreme_conviction_list, 1):
            lines.append(
                f"| {idx} | {stock.get('name', '-')} | {stock.get('code', '-')} | "
                f"{stock.get('sector', '-')} | {stock.get('conviction_reason', '-')} | "
                f"{stock.get('conviction_rule', '-')} |"
            )
    else:
        lines.append("- 暂无极度看好标的，说明当下更适合广泛观察而不是集中出手。")
    lines.append("")

    lines.append(f"**{stage_label} 结论**:")
    lines.append(f"- **主线核心**: {len(core_stocks)}只（主攻线内最值得盯的可执行候选）")
    lines.append(f"- **主线次核心**: {len(secondary_stocks)}只（主攻线内备选观察）")
    lines.append(f"- **跨线观察**: {len(crossline_observation_stocks)}只（只看资金迁移，不代表主线切换）")
    lines.append(f"- **创业板20cm预启动**: {len(gem_observation_stocks)}只（只先进观察池，等待右侧确认）")
    lines.append(f"- **暂不关注**: {len(ignored_stocks)}只（预判明日强度不足）")
    lines.append(f"- **接着做什么**: 进入{next_stage_label}，预判这些核心股明天有没有崩的风险")
    lines.append("")

    quadrant_data = data.get("sector_quadrant")
    mainline_in_quadrant = None
    mainline_score = 0
    if quadrant_data and quadrant_data.get("high_strong_analysis"):
        hs_analysis = quadrant_data["high_strong_analysis"]
        current_mainline = exit_analysis.get("sector_name", "")
        if current_mainline:
            for tier_name, tier_label in [
                ("tier1_best", "🏆 最佳击球区"),
                ("tier2_good", "⭐ 优质击球区"),
                ("tier3_normal", "✓ 普通击球区"),
            ]:
                matched = next(
                    (
                        sector
                        for sector in hs_analysis.get(tier_name, [])
                        if current_mainline in sector["name"] or sector["name"] in current_mainline
                    ),
                    None,
                )
                if matched:
                    mainline_in_quadrant = tier_label
                    mainline_score = matched.get("quality_score", 0)
                    break
            if not mainline_in_quadrant:
                mainline_in_quadrant = "❌ 不在击球区"

        lines.append(_subheading(stage_label, "6", "击球区判断", "（判断是否有势的核心标准）"))
        lines.append("> **数据来源**: QuickTiny板块四象限API（20日高低+3日强弱）")
        lines.append("> **判断逻辑**: 只有处于击球区的板块才算'有势'，否则只是超跌反弹或弱势震荡")
        lines.append("")
        lines.append("**击球区质量分层**:")
        lines.append("| 等级 | 得分范围 | 板块数 | 特征 |")
        lines.append("|------|----------|--------|------|")
        lines.append(f"| 🏆 最佳击球区 | 80-100分 | {hs_analysis.get('tier1_count', 0)}个 | 高位置+强动量+放量 |")
        lines.append(f"| ⭐ 优质击球区 | 60-79分 | {hs_analysis.get('tier2_count', 0)}个 | 至少两项强 |")
        lines.append(f"| ✓ 普通击球区 | 40-59分 | {hs_analysis.get('tier3_count', 0)}个 | 勉强符合 |")
        lines.append(f"| ⚠️ 边缘击球区 | <40分 | {hs_analysis.get('tier4_count', 0)}个 | 伪击球区，应过滤 |")
        lines.append("")
        if mainline_in_quadrant:
            lines.append(f"**主线位置判断**: 当前主线'{current_mainline or '未知'}'位于{mainline_in_quadrant}（得分{mainline_score}分）")
            lines.append("")

        if not display_mvp_mode and ai_analyze_sector_relationships:
            all_sector_names = []
            for stock in dragon_stocks[:5]:
                sector_name = stock.get("sector", "")
                if sector_name and sector_name not in all_sector_names:
                    all_sector_names.append(sector_name)
            for tier_key in ["tier1_best", "tier2_good", "tier3_normal"]:
                for sector in hs_analysis.get(tier_key, []):
                    sector_name = sector.get("name", "")
                    if sector_name and sector_name not in all_sector_names:
                        all_sector_names.append(sector_name)
            ai_analysis = ai_analyze_sector_relationships(all_sector_names, f"市场环境: {stage_context.get('position_level', '')}, 日期: {target_date}")
            if ai_analysis.get("groups"):
                lines.append(_subheading(stage_label, "7", "AI智能板块归一化分析"))
                lines.append("> **分析目的**: 使用内置LLM识别表面标签分散、实则同源的板块聚集效应")
                lines.append("")
                lines.append("| 大方向 | 包含标签 | 产业链逻辑 | 资金博弈逻辑 |")
                lines.append("|--------|----------|------------|--------------|")
                for group in ai_analysis.get("groups", []):
                    sectors_text = "、".join(group.get("sectors", [])[:3])
                    if len(group.get("sectors", [])) > 3:
                        sectors_text += f" 等{len(group.get('sectors', []))}个"
                    lines.append(
                        f"| **{group.get('name', '-') }** | {sectors_text} | "
                        f"{group.get('reason', '-')} | {group.get('investment_logic', '-')} |"
                    )
                lines.append("")

    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成核心候选阶段",
        stage_key=stage_meta.get("stage_key", "candidate_selection"),
        core_count=len(core_stocks),
        secondary_count=len(secondary_stocks),
    )
    return {
        "lines": lines,
        "exports": {
            "step2_bundle": step2_bundle,
            "evaluated_stocks": evaluated_stocks,
            "core_stocks": core_stocks,
            "secondary_stocks": secondary_stocks,
            "ignored_stocks": ignored_stocks,
            "crossline_observation_stocks": crossline_observation_stocks,
            "gem_observation_stocks": gem_observation_stocks,
            "sector_trend_snapshot": sector_trend_snapshot,
            "extreme_conviction_list": extreme_conviction_list,
            "mainline_name": primary_mainline,
            "mainline_in_quadrant": mainline_in_quadrant,
            "mainline_score": mainline_score,
        },
        "module_logs": list(step2_bundle.get("module_logs") or []) + logs,
    }
