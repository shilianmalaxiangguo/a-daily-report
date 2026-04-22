def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.environment_follow_stage",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


_EXPORT_FIELDS = [
    "zt_pool_by_sector",
    "dt_pool_by_sector",
    "zt_pool",
    "hot_stocks",
    "active_a_kill_records",
    "candidates",
    "watchlist",
    "filtered_by_a_kill",
    "mainline_name",
    "stock_meta_map",
    "abnormal_watch_pool_all",
    "abnormal_watch_pool",
    "abnormal_watch_map",
    "sector_trend_snapshot_step1",
    "leader_memory_bank",
    "tracking_memory_status",
    "mainline_competition_snapshot",
    "observation_snapshot",
    "market_research_snapshot",
    "market_state_snapshot",
    "abnormal_projection_summary",
    "step0_plan",
]


def build_environment_follow_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    stage_meta = stage_meta or {}
    bundle = dict(stage_context.get("market_research_bundle") or {})
    display_mvp_mode = bool(stage_context.get("display_mvp_mode", False))
    render_market_research_snapshot_section = stage_context["render_market_research_snapshot_section"]
    render_step0_follow_section = stage_context["render_step0_follow_section"]
    logs = []

    stage_label = str(stage_meta.get("label", "") or "Step 0").strip() or "Step 0"
    title = str(stage_meta.get("title", "") or "明日环境与跟随裁决").strip() or "明日环境与跟随裁决"
    lines = [
        f"#### {stage_label} - {title}",
        "> **核心问题**：今天的市场研究结果，到了明天开盘前，究竟是该跟、该等等，还是根本不该参与？",
        f"> **重要提示**：T日收盘生成的报告，分析的是T+1日（明天）的操作。{stage_label} 不再单独猜市场，而是直接引用统一市场研究快照。",
        "",
        '> **📈 大盘中枢分析**：详见报告开头的"明天仓位怎么放"部分',
        "",
    ]
    lines.extend(
        render_market_research_snapshot_section(
            bundle.get("market_research_snapshot", {}) or {},
            compact=display_mvp_mode,
        )
    )
    lines.extend(
        render_step0_follow_section(
            bundle.get("step0_plan", {}) or {},
            bundle.get("market_research_snapshot", {}) or {},
            compact=display_mvp_mode,
        )
    )

    exports = {field: bundle.get(field) for field in _EXPORT_FIELDS}
    step0_plan = bundle.get("step0_plan", {}) or {}
    exports.update(
        {
            "step0_prediction": step0_plan.get("step0_prediction", "NEUTRAL"),
            "step0_prediction_cn": step0_plan.get("step0_prediction_cn", step0_plan.get("step0_prediction", "NEUTRAL")),
            "step0_reason": step0_plan.get("step0_reason", ""),
            "step0_action": step0_plan.get("step0_action", ""),
        }
    )
    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成环境跟随阶段",
        stage_key=stage_meta.get("stage_key", "environment_follow"),
        line_count=len(lines),
    )
    return {
        "lines": lines,
        "exports": exports,
        "module_logs": logs + list(bundle.get("module_logs") or []),
    }
