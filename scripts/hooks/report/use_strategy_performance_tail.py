import time

from report.monitoring_pool_support import build_monitoring_pool_summary


HOOK_NAME = "report.strategy_performance_tail"


def _ensure_monitoring_pool_summary(performance_summary, strategy_factor_snapshot, target_date):
    performance_summary = performance_summary or {}
    current_plan = (performance_summary.get("current_plan") or {}) if isinstance(performance_summary, dict) else {}
    factor_snapshot = (current_plan.get("factor_snapshot") or strategy_factor_snapshot or {}) if isinstance(current_plan, dict) else (strategy_factor_snapshot or {})
    monitoring_pool = (performance_summary.get("monitoring_pool") or {}) if isinstance(performance_summary, dict) else {}
    has_existing_pool = bool((monitoring_pool.get("main_pool") or []) or (monitoring_pool.get("secondary_pool") or []))
    if has_existing_pool:
        return performance_summary

    monitoring_context = {
        "core_stocks": factor_snapshot.get("core_stocks", []) or [],
        "secondary_stocks": factor_snapshot.get("secondary_stocks", []) or [],
        "crossline_observation_stocks": factor_snapshot.get("crossline_observation_stocks", []) or [],
        "gem_observation_stocks": factor_snapshot.get("gem_observation_stocks", []) or [],
        "generic_watch_stocks": factor_snapshot.get("generic_watch_stocks", []) or [],
    }
    if not any(monitoring_context.values()):
        return performance_summary

    enriched_summary = dict(performance_summary)
    enriched_summary["monitoring_pool"] = build_monitoring_pool_summary(monitoring_context, target_date)
    return enriched_summary


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "hooks.report.use_strategy_performance_tail",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def run(ctx):
    started_at = time.perf_counter()
    ctx = ctx or {}
    inputs = ctx.get("inputs") or {}
    helpers = ctx.get("helpers") or {}
    logs = []
    lines = []

    target_date = inputs.get("target_date", "")
    data = inputs.get("data")
    if data is None:
        data = {}
    market_zhongshu = inputs.get("market_zhongshu", {}) or {}
    final_gate = inputs.get("final_gate", {}) or {}
    exit_analysis = inputs.get("exit_analysis", {}) or {}
    position_level = inputs.get("position_level", "")
    position_reason = inputs.get("position_reason", "")
    best_stock = inputs.get("best_stock")
    watch_anchor = inputs.get("watch_anchor")
    watch_anchor_type = inputs.get("watch_anchor_type", "")
    factor_context = inputs.get("factor_context", {}) or {}
    persist_strategy_tracking = bool(inputs.get("persist_strategy_tracking", True))
    run_mode = inputs.get("run_mode", "frozen")

    build_strategy_factor_snapshot = helpers.get("build_strategy_factor_snapshot")
    build_strategy_plan_context = helpers.get("build_strategy_plan_context")
    update_strategy_performance_book = helpers.get("update_strategy_performance_book")
    render_strategy_performance_nodes = helpers.get("render_strategy_performance_nodes")
    append_strategy_performance_section = helpers.get("append_strategy_performance_section")

    strategy_factor_snapshot = (
        build_strategy_factor_snapshot(
            target_date,
            data,
            market_zhongshu,
            final_gate,
            exit_analysis,
            position_level,
            position_reason,
            factor_context,
        )
        if callable(build_strategy_factor_snapshot)
        else {}
    )
    _append_log(
        logs,
        "derive.strategy_factor_snapshot",
        "success",
        "已生成策略因子快照",
        has_snapshot=bool(strategy_factor_snapshot),
    )

    strategy_plan_context = (
        build_strategy_plan_context(
            target_date,
            data,
            market_zhongshu,
            final_gate,
            exit_analysis,
            position_level,
            position_reason,
            best_stock=best_stock,
            watch_anchor=watch_anchor,
            watch_anchor_type=watch_anchor_type,
            factor_snapshot=strategy_factor_snapshot,
        )
        if callable(build_strategy_plan_context)
        else {}
    )
    _append_log(
        logs,
        "derive.strategy_plan_context",
        "success",
        "已生成策略计划上下文",
        has_plan=bool(strategy_plan_context),
        persist_strategy_tracking=persist_strategy_tracking,
        run_mode=run_mode,
    )

    strategy_performance_summary = None
    if persist_strategy_tracking:
        strategy_performance_summary = (
            update_strategy_performance_book(
                data,
                target_date,
                strategy_plan_context,
                market_zhongshu,
                ledger_mode=run_mode,
            )
            if callable(update_strategy_performance_book)
            else None
        )
        data["strategy_tracking"] = {
            "plan": strategy_plan_context,
            "performance_summary": strategy_performance_summary,
        }
        _append_log(
            logs,
            "persist.strategy_performance_book",
            "success",
            "已更新策略绩效账本",
            used_existing_summary=False,
        )
    else:
        strategy_tracking = data.get("strategy_tracking", {}) or {}
        strategy_performance_summary = strategy_tracking.get("performance_summary")
        used_existing_summary = bool(strategy_performance_summary)
        _append_log(
            logs,
            "persist.strategy_performance_book",
            "success",
            "已解析策略绩效账本来源",
            used_existing_summary=used_existing_summary,
        )

    strategy_performance_summary = _ensure_monitoring_pool_summary(
        strategy_performance_summary,
        strategy_factor_snapshot,
        target_date,
    )

    if callable(render_strategy_performance_nodes):
        render_result = render_strategy_performance_nodes(
            {
                "performance_summary": strategy_performance_summary or {},
                "helpers": helpers.get("strategy_performance_helpers") or {},
            }
        ) or {}
        lines.extend(render_result.get("lines", []) or [])
        logs.extend(render_result.get("module_logs", []) or [])
    elif callable(append_strategy_performance_section):
        append_strategy_performance_section(lines, strategy_performance_summary)
    _append_log(
        logs,
        "render.strategy_performance_section",
        "success",
        "已渲染策略绩效尾部",
        line_count=len(lines),
        has_performance_summary=bool(strategy_performance_summary),
    )

    exports = {
        "strategy_factor_snapshot": strategy_factor_snapshot,
        "strategy_plan_context": strategy_plan_context,
        "strategy_performance_summary": strategy_performance_summary,
    }
    return {
        "value": {
            "lines": lines,
            "exports": exports,
            "module_logs": logs,
        },
        "patches": {
            "derived": {
                "strategy_performance_tail": exports,
            }
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "warnings": [],
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
        },
        "artifacts": {},
    }
