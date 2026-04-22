import time


HOOK_NAME = "report.tail_summary"


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "hooks.report.use_report_tail_summary",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _extract_names(items):
    names = []
    for item in items or []:
        if isinstance(item, dict):
            name = str(item.get("name", "") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            names.append(name)
    return names


def _build_abnormal_probe_parts(inputs, helpers):
    format_abnormal_probe_text = helpers.get("format_abnormal_probe_text")
    abnormal_probe_group = inputs.get("abnormal_probe_group", {}) or {}
    mainline_name = str(inputs.get("mainline_name", "") or "").strip()
    abnormal_probe_parts = []
    if not callable(format_abnormal_probe_text) or not abnormal_probe_group:
        return abnormal_probe_parts

    mainline_probe_text = format_abnormal_probe_text(
        abnormal_probe_group.get("mainline_abnormal_probe"),
        role_label="主线异动里先看谁",
        mainline_name=mainline_name,
        fallback_watch_anchor=abnormal_probe_group.get("fallback_watch_anchor"),
    )
    crossline_probe_text = format_abnormal_probe_text(
        abnormal_probe_group.get("crossline_abnormal_probe"),
        role_label="跨线异动里先看谁",
        mainline_name=mainline_name,
    )
    validation_probe_text = format_abnormal_probe_text(
        abnormal_probe_group.get("validation_probe"),
        role_label="承接验证先看谁",
        mainline_name=mainline_name,
    )
    if mainline_probe_text:
        abnormal_probe_parts.append(f"主线异动里先看谁：{mainline_probe_text}")
    if crossline_probe_text:
        abnormal_probe_parts.append(f"跨线异动里先看谁：{crossline_probe_text}")
    if validation_probe_text:
        abnormal_probe_parts.append(f"承接验证先看谁：{validation_probe_text}")
    return abnormal_probe_parts


def _build_mainline_text(inputs, resolved_mainline_name):
    if resolved_mainline_name:
        return resolved_mainline_name

    main_sector_names = _extract_names(inputs.get("main_sectors_info", []))
    if main_sector_names:
        return "、".join(main_sector_names[:2])

    fallback_main_sectors = _extract_names(inputs.get("main_sectors", []))
    if fallback_main_sectors:
        return "、".join(fallback_main_sectors[:2])

    return "暂无明确主线"


def _build_risk_text(inputs):
    risk_sector_names = _extract_names(inputs.get("risk_sectors", []))
    if risk_sector_names:
        return "、".join(risk_sector_names[:2])
    return "暂无明确风险"


def run(ctx):
    started_at = time.perf_counter()
    ctx = ctx or {}
    inputs = ctx.get("inputs") or {}
    helpers = ctx.get("helpers") or {}
    logs = []
    lines = []

    build_legacy_final_conclusion_lines = helpers.get("build_legacy_final_conclusion_lines")
    build_front_mainline_label = helpers.get("build_front_mainline_label")
    render_mainline_discipline_section = helpers.get("render_mainline_discipline_section")
    render_supplementary_perspective_section = helpers.get("render_supplementary_perspective_section")
    render_ai_market_insight_section = helpers.get("render_ai_market_insight_section")

    abnormal_probe_parts = _build_abnormal_probe_parts(inputs, helpers)
    _append_log(
        logs,
        "derive.abnormal_probe_parts",
        "success",
        "已生成异动探针摘要",
        abnormal_probe_count=len(abnormal_probe_parts),
    )

    display_mvp_mode = bool(inputs.get("display_mvp_mode"))
    mainline_name = str(inputs.get("mainline_name", "") or "").strip()
    market_research_snapshot = inputs.get("market_research_snapshot", {}) or {}
    final_gate = inputs.get("final_gate", {}) or {}
    watchlist = inputs.get("watchlist", []) or []
    core_stocks = inputs.get("core_stocks", []) or []
    secondary_stocks = inputs.get("secondary_stocks", []) or []
    step2_bundle = inputs.get("step2_bundle", {}) or {}
    abnormal_watch_pool = inputs.get("abnormal_watch_pool", []) or []
    exit_analysis = inputs.get("exit_analysis", {}) or {}
    market_state_snapshot = inputs.get("market_state_snapshot", {}) or {}
    supplementary_perspective = str(inputs.get("supplementary_perspective", "") or "").strip()
    resolved_mainline_name = str(exit_analysis.get("sector_name", "") or mainline_name).strip()
    mainline_text = _build_mainline_text(inputs, resolved_mainline_name)
    risk_text = _build_risk_text(inputs)

    if callable(build_legacy_final_conclusion_lines):
        lines.extend(
            build_legacy_final_conclusion_lines(
                {
                    "display_mvp_mode": display_mvp_mode,
                    "step0_prediction": inputs.get("step0_prediction", "NEUTRAL"),
                    "step0_prediction_cn": inputs.get("step0_prediction_cn", "NEUTRAL"),
                    "step0_action": inputs.get("step0_action", ""),
                    "final_gate": final_gate,
                    "mainline_name": mainline_name,
                    "mainline_label": (
                        build_front_mainline_label(
                            market_research_snapshot,
                            fallback_mainline=mainline_name or "",
                        )
                        if callable(build_front_mainline_label)
                        else mainline_name
                    ),
                    "watchlist_count": len(watchlist),
                    "core_count": len(core_stocks),
                    "secondary_count": len(secondary_stocks),
                    "crossline_count": len(step2_bundle.get("crossline_observation_stocks", [])),
                    "abnormal_watch_count": len(abnormal_watch_pool),
                    "front_structure_layer_text": inputs.get("front_structure_layer_text", ""),
                    "trade_gate_open": bool(inputs.get("trade_gate_open")),
                    "best_stock": inputs.get("best_stock"),
                    "watch_anchor": inputs.get("watch_anchor"),
                    "watch_anchor_type": inputs.get("watch_anchor_type", ""),
                    "front_follow_action_text": inputs.get("front_follow_action_text", ""),
                    "abnormal_probe_parts": abnormal_probe_parts,
                }
            )
        )

    if callable(render_mainline_discipline_section):
        lines.extend(render_mainline_discipline_section(resolved_mainline_name))

    if callable(render_supplementary_perspective_section):
        lines.extend(render_supplementary_perspective_section(supplementary_perspective))

    if callable(render_ai_market_insight_section):
        focus_subject = mainline_text if mainline_text != "暂无明确主线" else "市场整体"
        lines.extend(
            render_ai_market_insight_section(
                {
                    "market_trend": inputs.get("market_trend", ""),
                    "zt_count": inputs.get("zt_count", 0),
                    "dt_count": inputs.get("dt_count", 0),
                    "energy_state": market_state_snapshot.get("energy_state", "未知"),
                    "flow_direction": market_state_snapshot.get("flow_direction", "-"),
                    "mainline_text": mainline_text,
                    "risk_text": risk_text,
                    "focus_text": f"{focus_subject}持续性，量能变化，板块轮动",
                }
            )
        )

    _append_log(
        logs,
        "render.tail_summary",
        "success",
        "已渲染最终结论与洞察尾部",
        line_count=len(lines),
        mainline_text=mainline_text,
        risk_text=risk_text,
        has_supplementary_perspective=bool(supplementary_perspective),
    )

    exports = {
        "abnormal_probe_parts": abnormal_probe_parts,
        "mainline_name": resolved_mainline_name,
        "mainline_text": mainline_text,
        "risk_text": risk_text,
    }
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    return {
        "value": {
            "lines": lines,
            "exports": exports,
            "module_logs": logs,
        },
        "patches": {
            "derived": {
                "report_tail_summary": exports,
            }
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "warnings": [],
            "duration_ms": duration_ms,
        },
        "artifacts": {},
    }
