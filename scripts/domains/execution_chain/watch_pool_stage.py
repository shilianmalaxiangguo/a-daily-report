from domains.execution_chain.step1_sections import build_step1_watch_sections


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.watch_pool_stage",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_watch_pool_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    logs = []
    lines = build_step1_watch_sections(
        sector_trend_snapshot_step1=stage_context.get("sector_trend_snapshot_step1", []),
        mainline_competition_snapshot=stage_context.get("mainline_competition_snapshot", []),
        leader_memory_bank=stage_context.get("leader_memory_bank", []),
        tracking_memory_status=stage_context.get("tracking_memory_status", {}) or {},
        watchlist=stage_context.get("watchlist", []),
        abnormal_watch_pool=stage_context.get("abnormal_watch_pool", []),
        abnormal_projection_summary=stage_context.get("abnormal_projection_summary", {}) or {},
        filtered_by_a_kill=stage_context.get("filtered_by_a_kill", []),
        display_mvp_mode=bool(stage_context.get("display_mvp_mode", False)),
        is_degraded_abnormal_snapshot=stage_context["is_degraded_abnormal_snapshot"],
        format_abnormal_observation_columns=stage_context["format_abnormal_observation_columns"],
        stage_meta=stage_meta,
        stage_lookup=stage_lookup,
    )
    exports = {
        "watchlist": stage_context.get("watchlist", []),
        "abnormal_watch_pool": stage_context.get("abnormal_watch_pool", []),
        "leader_memory_bank": stage_context.get("leader_memory_bank", []),
        "tracking_memory_status": stage_context.get("tracking_memory_status", {}) or {},
    }
    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成观察池阶段",
        stage_key=stage_meta.get("stage_key", "watch_pool"),
        watch_count=len(exports["watchlist"]),
    )
    return {
        "lines": lines,
        "exports": exports,
        "module_logs": logs,
    }
