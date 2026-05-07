def _make_stage(stage_key, title, status, summary, details=None):
    return {
        "stage_key": stage_key,
        "title": title,
        "status": status,
        "summary": summary,
        "details": details or {},
    }


def build_market_environment_stage(ctx):
    market_phase = ((ctx.get("derived") or {}).get("market_phase") or {})
    phase = str(market_phase.get("phase", "") or "unknown").strip() or "unknown"
    status = "ready" if phase not in ("defend", "unknown") else "blocked"
    return _make_stage(
        "market_environment",
        "市场环境",
        status,
        f"当前环境阶段：{phase}",
        {"phase": phase},
    )


def build_selection_focus_stage(ctx):
    mainline = ((ctx.get("derived") or {}).get("mainline") or {})
    strategy_contract = ((ctx.get("derived") or {}).get("strategy_contract") or {})
    primary_line = str(mainline.get("primary_line", "") or "未知").strip() or "未知"
    contract_label = str(strategy_contract.get("contract_label", "") or "unknown").strip() or "unknown"
    return _make_stage(
        "selection_focus",
        "主线与筛选",
        "ready" if primary_line != "未知" else "blocked",
        f"主线{primary_line}，合同{contract_label}",
        {"primary_line": primary_line, "contract_label": contract_label},
    )


def build_execution_gate_stage(ctx):
    action_plan = ((ctx.get("decision") or {}).get("action_plan") or {})
    execution_permission = (((ctx.get("decision") or {}).get("execution_permission") or {}) or {})
    label = str(execution_permission.get("label", "") or "unknown").strip() or "unknown"
    trigger = str(action_plan.get("trigger", "") or "").strip()
    status = "ready" if label == "conditional_30" else ("blocked" if label == "watch_only" else "pending")
    summary = f"{label}"
    if trigger:
        summary = f"{summary}；{trigger}"
    return _make_stage(
        "execution_gate",
        "执行条件",
        status,
        summary,
        {"permission_label": label, "trigger": trigger},
    )


DEFAULT_STAGE_BUILDERS = [
    build_market_environment_stage,
    build_selection_focus_stage,
    build_execution_gate_stage,
]


def build_report_stages(ctx, stage_builders=None):
    builders = list(stage_builders or DEFAULT_STAGE_BUILDERS)
    stages = []
    for builder in builders:
        stage = builder(ctx)
        if stage:
            stages.append(stage)
    return stages
