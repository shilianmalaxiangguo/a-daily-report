from domains.execution_chain.risk_review_node_registry import build_risk_review_node_specs
from domains.execution_chain.risk_review_node_runtime import run_risk_review_nodes
from domains.execution_chain.risk_review_nodes.conclusion import build_risk_review_conclusion_node
from domains.execution_chain.risk_review_nodes.gem_pool import build_risk_review_gem_pool_node
from domains.execution_chain.risk_review_nodes.overview import build_risk_review_overview_node
from domains.execution_chain.risk_review_nodes.risk_groups import build_risk_review_risk_groups_node
from domains.execution_chain.risk_review_nodes.sector_a_kill import build_risk_review_sector_a_kill_node
from domains.execution_chain.risk_review_nodes.sector_outlook import build_risk_review_sector_outlook_node
from domains.execution_chain.risk_review_nodes.stock_risk import build_risk_review_stock_risk_node
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


RISK_REVIEW_NODE_BUILDERS = {
    "overview": build_risk_review_overview_node,
    "stock_risk": build_risk_review_stock_risk_node,
    "sector_a_kill": build_risk_review_sector_a_kill_node,
    "risk_groups": build_risk_review_risk_groups_node,
    "sector_outlook": build_risk_review_sector_outlook_node,
    "conclusion": build_risk_review_conclusion_node,
    "gem_pool": build_risk_review_gem_pool_node,
}


def build_risk_review_runtime(stage_context, stage_meta, stage_lookup=None, enabled_node_keys=None):
    stage_context = stage_context or {}
    stage_lookup = stage_lookup or {}
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
    render_gem_breathing_pool_section = stage_context.get("render_gem_breathing_pool_section")

    stage_label = str(stage_meta.get("label", "") or "Step 3").strip() or "Step 3"
    stage_title = str(stage_meta.get("title", "") or "明日风险预判").strip() or "明日风险预判"
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

    node_context = {
        "stage_label": stage_label,
        "stage_title": stage_title,
        "next_stage_label": next_stage_label,
        "mainline_name": mainline_name,
        "data": data,
        "realtime_tag_evidence_snapshot": data.get("realtime_tag_evidence_snapshot") or {},
        "stock_rows": step3_bundle.get("stock_rows", []) or [],
        "delete_group": delete_group,
        "keep_group": keep_group,
        "focus_group": focus_group,
        "abnormal_green_count": abnormal_green_count,
        "abnormal_red_count": abnormal_red_count,
        "risk_sectors_from_dt": risk_sectors_from_dt,
        "mainline_turnover_summary": stage_context.get("mainline_turnover_summary", {}) or {},
        "mainline_a_kill": mainline_a_kill,
        "mainline_dt_stocks": mainline_dt_stocks,
        "structural_a_kill": structural_a_kill,
        "structural_reason": structural_reason,
        "a_kill_blacklist_updates": a_kill_blacklist_updates,
        "gem_observation_stocks": step2_bundle.get("gem_observation_stocks", []),
        "filtered_out_gem_candidates": market_research_bundle.get("filtered_out_gem_breathing_candidates", []),
        "render_gem_breathing_pool_section": render_gem_breathing_pool_section,
    }
    node_specs = build_risk_review_node_specs(RISK_REVIEW_NODE_BUILDERS, enabled_node_keys=enabled_node_keys)
    runtime_result = run_risk_review_nodes(node_specs, node_context)

    exports = {
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
    }
    return {
        "lines": runtime_result["lines"],
        "exports": exports,
        "module_logs": list(step3_bundle.get("module_logs") or []) + list(runtime_result.get("module_logs") or []),
    }


def build_risk_review_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    logs = []
    result = build_risk_review_runtime(stage_context, stage_meta, stage_lookup=stage_lookup)

    exports = dict(result.get("exports") or {})
    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成风险复核阶段",
        stage_key=(stage_meta or {}).get("stage_key", "risk_review"),
        focus_count=len(exports.get("focus_group", []) or []),
        keep_count=len(exports.get("keep_group", []) or []),
        delete_count=len(exports.get("delete_group", []) or []),
    )
    return {
        "lines": list(result.get("lines") or []),
        "exports": exports,
        "module_logs": list(result.get("module_logs") or []) + logs,
    }
