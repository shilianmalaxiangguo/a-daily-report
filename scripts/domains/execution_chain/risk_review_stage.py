from domains.execution_chain.stage_runtime import get_execution_stage_label


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.risk_review_stage",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_risk_review_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    stage_lookup = stage_lookup or {}
    logs = []

    data = stage_context.get("data", {}) or {}
    target_date = stage_context.get("target_date", "")
    mainline_name = str(stage_context.get("mainline_name", "") or "").strip()
    core_stocks = stage_context.get("core_stocks", []) or []
    secondary_stocks = stage_context.get("secondary_stocks", []) or []
    step2_bundle = stage_context.get("step2_bundle", {}) or {}
    market_research_bundle = stage_context.get("market_research_bundle", {}) or {}
    zt_pool_by_sector = stage_context.get("zt_pool_by_sector", {}) or {}
    dt_pool_by_sector = stage_context.get("dt_pool_by_sector", {}) or {}
    build_step3_risk_bundle = stage_context["build_step3_risk_bundle"]
    render_gem_breathing_pool_section = stage_context["render_gem_breathing_pool_section"]

    stage_label = str(stage_meta.get("label", "") or "Step 3").strip() or "Step 3"
    prev_stage_label = get_execution_stage_label(stage_lookup, "candidate_selection") if stage_lookup else "Step 2"
    next_stage_label = get_execution_stage_label(stage_lookup, "entry_plan") if stage_lookup else "Step 4"

    step3_bundle = build_step3_risk_bundle(
        data,
        target_date,
        mainline_name=mainline_name,
        core_stocks=core_stocks,
        secondary_stocks=secondary_stocks,
        gem_observation_stocks=step2_bundle.get("gem_observation_stocks", []),
        zt_pool_by_sector=zt_pool_by_sector,
        dt_pool_by_sector=dt_pool_by_sector,
        persist_a_kill=True,
    )
    delete_group = step3_bundle.get("delete_group", [])
    keep_group = step3_bundle.get("keep_group", [])
    focus_group = step3_bundle.get("focus_group", [])
    abnormal_green_count = step3_bundle.get("abnormal_green_count", 0)
    abnormal_red_count = step3_bundle.get("abnormal_red_count", 0)
    risk_sectors_from_dt = step3_bundle.get("risk_sectors_from_dt", [])
    mainline_a_kill = step3_bundle.get("mainline_a_kill", False)
    mainline_dt_stocks = step3_bundle.get("mainline_dt_stocks", [])
    structural_a_kill = step3_bundle.get("structural_a_kill", False)
    structural_reason = step3_bundle.get("structural_reason", "")
    a_kill_blacklist_updates = step3_bundle.get("a_kill_blacklist_updates", [])

    lines = [
        "",
        f"#### {stage_label} - 明日风险预判",
        f"> **核心问题**：{prev_stage_label}挑出来的核心股，明天有没有可能崩？基于今日形态提前预判。",
        "> **预判逻辑**：烂板炸板→明日低开；缩量涨停→明日炸板；跟风后排→明日断板；高位放量滞涨→明日回调；异动后转弱→直接降级",
        "",
        f"**{stage_label}.1 逐只预判明日风险**（基于今日形态）:",
        "| 股票 | 代码 | 今日形态 | 异动灯号 | 明日风险预判 | 风险等级 | 去向 |",
        "|------|------|----------|----------|--------------|----------|------|",
    ]
    for row in step3_bundle.get("stock_rows", []):
        lines.append(
            f"| {row.get('name', '-')} | {row.get('code', '-')} | {row.get('pattern', '未知')} | "
            f"{row.get('abnormal_light', '🟡 黄灯')} | {row.get('tomorrow_risk', '-')} | "
            f"{row.get('risk_level', '-')} | {row.get('dest', '-')} |"
        )

    lines.extend(
        [
            "",
            f"**{stage_label}.2 板块级A杀预判**（基于今日跌停分布预判明日）",
            "> **预判逻辑**：若某板块今日已有批量跌停，明日该板块跟风股大概率低开",
            "",
        ]
    )
    if len(mainline_dt_stocks) >= 3:
        lines.append(f"- ❌ **A杀确认（板块级）**: 当前主线'{mainline_name}'出现批量跌停（{len(mainline_dt_stocks)}只，三人成众）！")
        lines.append(f"  - 跌停股票: {', '.join([item.get('name', '') for item in mainline_dt_stocks[:5]])}")
        lines.append("  - **结论**: 高位站不住，板块级A杀确认，直接删除观察列表。")
    elif structural_a_kill:
        lines.append(f"- ❌ **A杀确认（结构级）**: {structural_reason}")
        if mainline_dt_stocks:
            lines.append(f"  - 结构破坏对象: {', '.join([item.get('name', '') for item in mainline_dt_stocks[:3]])}")
        lines.append("  - **结论**: 这不是正常调整，而是趋势破坏。直接删除观察列表，并进入25天禁买池。")
    elif len(mainline_dt_stocks) >= 1:
        lines.append(f"- ⚠️ **明天要防什么**: 当前主线'{mainline_name}'出现{len(mainline_dt_stocks)}只跌停股")
        lines.append(f"  - 跌停股票: {', '.join([item.get('name', '') for item in mainline_dt_stocks[:3]])}")
        lines.append("  - **说明**: 未达到A杀确认，但需继续观察是否恶化为结构性破坏")

    if mainline_a_kill and a_kill_blacklist_updates:
        lines.append("- **已写入A杀冷却池**（25天内禁买）:")
        for item in a_kill_blacklist_updates[:5]:
            lines.append(
                f"  - {item.get('name', '-') or '-'}({item.get('code', '-') or '-'}) | "
                f"A杀日{item.get('a_kill_date', '-')} | 禁买至{item.get('ban_until', '-')}"
            )

    if not mainline_a_kill:
        if risk_sectors_from_dt:
            lines.append("- **其他A杀板块**（批量跌停>=3只，非当前主线）:")
            for risk in risk_sectors_from_dt[:3]:
                lines.append(f"  - {risk['sector']}（跌停{risk['count']}只：{', '.join(risk['stocks'])}）")
            lines.append(f"- ✅ **当前主线**: '{mainline_name}'暂未出现A杀确认，继续观察抗性")
        else:
            lines.append(f"- ✅ **当前主线**: '{mainline_name}'无批量跌停，也无明显结构破坏，暂未出现A杀信号")
    lines.append("")

    lines.append(f"**{stage_label}.3 明日风险分组**")
    lines.append("")
    if delete_group:
        lines.append(f"**🔴 明天先回避组**（{len(delete_group)}只，预判明日风险高）:")
        for item in delete_group:
            lines.append(f"- ❌ {item.get('name')}({item.get('code')}) - {item.get('reason')} - {item.get('tomorrow_risk', '')}")
        lines.append("")
    if keep_group:
        lines.append(f"**🟡 明天先观察组**（{len(keep_group)}只，需看明日竞价）:")
        for item in keep_group:
            lines.append(f"- ⚠️ {item.get('name')}({item.get('code')}) - {item.get('reason')} - {item.get('tomorrow_risk', '')}")
        lines.append("")
    if focus_group:
        lines.append(f"**🟢 明天重点候选组**（{len(focus_group)}只，通过风险筛选，继续进入执行层筛到可买股）:")
        for item in focus_group:
            lines.append(
                f"- ✅ {item.get('name')}({item.get('code')}) - "
                f"{item.get('reason', '风险可控')} - {item.get('tomorrow_risk', '风险可控')}"
            )
        lines.append("")

    lines.append(f"**{stage_label}.4 板块级明日风险预判**:")
    if len(delete_group) >= 3:
        lines.append(f"- ⚠️ 明天先回避组达{len(delete_group)}只，说明今日涨停质量差，明日整体风险偏高")
    else:
        lines.append(f"- ✅ 明天先回避组{len(delete_group)}只，在正常范围内，明日风险可控")
    lines.append(f"- **异动承接强不强**: 绿灯{abnormal_green_count}只，红灯{abnormal_red_count}只。绿灯代表“跌不下去”，红灯代表“异动后转弱”。")
    lines.append("")

    lines.append(f"**{stage_label} 结论**:")
    lines.append(f"- **明天先回避谁**: {len(delete_group)}只（烂板/炸板/后排，预判明日风险高）")
    lines.append(f"- **明天先观察谁**: {len(keep_group)}只（有风险信号，需看明日竞价强弱）")
    lines.append(f"- **明天重点候选**: {len(focus_group)}只（形态健康，允许进入{next_stage_label}继续筛到可买股）")
    if focus_group:
        lines.append(f"- **接着做什么**: 进入{next_stage_label}，为候选组预计算买点并筛出明天唯一能买的那只")
    else:
        lines.append("- **接着做什么**: 当前没有能下手的票，明日空仓观望")
    lines.append("")
    lines.extend(
        render_gem_breathing_pool_section(
            step2_bundle.get("gem_observation_stocks", []),
            filtered_out_gem_candidates=market_research_bundle.get("filtered_out_gem_breathing_candidates", []),
        )
    )

    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成风险复核阶段",
        stage_key=stage_meta.get("stage_key", "risk_review"),
        focus_count=len(focus_group),
        keep_count=len(keep_group),
        delete_count=len(delete_group),
    )
    return {
        "lines": lines,
        "exports": {
            "step3_bundle": step3_bundle,
            "delete_group": delete_group,
            "keep_group": keep_group,
            "focus_group": focus_group,
            "abnormal_green_count": abnormal_green_count,
            "abnormal_red_count": abnormal_red_count,
            "risk_sectors_from_dt": risk_sectors_from_dt,
            "mainline_a_kill": mainline_a_kill,
            "mainline_dt_stocks": mainline_dt_stocks,
            "structural_a_kill": structural_a_kill,
            "structural_reason": structural_reason,
            "a_kill_blacklist_updates": a_kill_blacklist_updates,
        },
        "module_logs": list(step3_bundle.get("module_logs") or []) + logs,
    }
