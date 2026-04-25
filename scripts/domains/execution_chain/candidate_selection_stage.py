from domains.execution_chain.candidate_selection_node_registry import build_candidate_selection_node_specs
from domains.execution_chain.candidate_selection_node_runtime import run_candidate_selection_nodes
from domains.execution_chain.candidate_selection_nodes.conclusion import build_candidate_selection_conclusion_node
from domains.execution_chain.candidate_selection_nodes.conviction_list import build_candidate_selection_conviction_list_node
from domains.execution_chain.candidate_selection_nodes.core_candidates import build_candidate_selection_core_candidates_node
from domains.execution_chain.candidate_selection_nodes.crossline_watch import build_candidate_selection_crossline_watch_node
from domains.execution_chain.candidate_selection_nodes.ignored_candidates import build_candidate_selection_ignored_candidates_node
from domains.execution_chain.candidate_selection_nodes.mainline_summary import build_candidate_selection_mainline_summary_node
from domains.execution_chain.candidate_selection_nodes.overview import build_candidate_selection_overview_node
from domains.execution_chain.candidate_selection_nodes.quadrant_analysis import build_candidate_selection_quadrant_analysis_node
from domains.execution_chain.candidate_selection_nodes.secondary_candidates import build_candidate_selection_secondary_candidates_node
from domains.execution_chain.candidate_selection_nodes.trend_density_review import build_candidate_selection_trend_density_review_node
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


CANDIDATE_SELECTION_NODE_BUILDERS = {
    "overview": build_candidate_selection_overview_node,
    "trend_density_review": build_candidate_selection_trend_density_review_node,
    "core_candidates": build_candidate_selection_core_candidates_node,
    "secondary_candidates": build_candidate_selection_secondary_candidates_node,
    "crossline_watch": build_candidate_selection_crossline_watch_node,
    "ignored_candidates": build_candidate_selection_ignored_candidates_node,
    "mainline_summary": build_candidate_selection_mainline_summary_node,
    "conviction_list": build_candidate_selection_conviction_list_node,
    "quadrant_analysis": build_candidate_selection_quadrant_analysis_node,
    "conclusion": build_candidate_selection_conclusion_node,
}


def build_candidate_selection_runtime(stage_context, stage_meta, stage_lookup=None, enabled_node_keys=None):
    stage_context = stage_context or {}
    stage_lookup = stage_lookup or {}
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
    render_gem_breathing_step2_section = stage_context.get("render_gem_breathing_step2_section")
    safe_float = stage_context["safe_float"]
    ai_analyze_sector_relationships = stage_context.get("ai_analyze_sector_relationships")

    stage_label = str(stage_meta.get("label", "") or "Step 2").strip() or "Step 2"
    stage_title = str(stage_meta.get("title", "") or "明日核心标的").strip() or "明日核心标的"
    next_stage_label = get_execution_stage_label(stage_lookup, "risk_review") if stage_lookup else "Step 3"

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

    node_context = {
        "stage_label": stage_label,
        "stage_title": stage_title,
        "next_stage_label": next_stage_label,
        "data": data,
        "target_date": target_date,
        "position_level": stage_context.get("position_level", ""),
        "final_gate": stage_context.get("final_gate", {}) or {},
        "exit_analysis": exit_analysis,
        "dragon_stocks": dragon_stocks,
        "display_mvp_mode": display_mvp_mode,
        "safe_float": safe_float,
        "render_gem_breathing_step2_section": render_gem_breathing_step2_section,
        "filtered_out_gem_candidates": market_research_bundle.get("filtered_out_gem_breathing_candidates", []),
        "ai_analyze_sector_relationships": ai_analyze_sector_relationships,
        "primary_mainline": primary_mainline,
        "evaluated_stocks": evaluated_stocks,
        "core_stocks": core_stocks,
        "secondary_stocks": secondary_stocks,
        "ignored_stocks": ignored_stocks,
        "crossline_observation_stocks": crossline_observation_stocks,
        "gem_observation_stocks": gem_observation_stocks,
        "sector_trend_snapshot": sector_trend_snapshot,
        "extreme_conviction_list": extreme_conviction_list,
    }
    node_specs = build_candidate_selection_node_specs(CANDIDATE_SELECTION_NODE_BUILDERS, enabled_node_keys=enabled_node_keys)
    runtime_result = run_candidate_selection_nodes(node_specs, node_context)

    exports = {
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
        "mainline_in_quadrant": runtime_result["context"].get("mainline_in_quadrant"),
        "mainline_score": runtime_result["context"].get("mainline_score", 0),
    }
    return {
        "lines": runtime_result["lines"],
        "exports": exports,
        "module_logs": list(step2_bundle.get("module_logs") or []) + list(runtime_result.get("module_logs") or []),
    }


def build_candidate_selection_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    logs = []
    result = build_candidate_selection_runtime(stage_context, stage_meta, stage_lookup=stage_lookup)

    exports = dict(result.get("exports") or {})
    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成核心候选阶段",
        stage_key=(stage_meta or {}).get("stage_key", "candidate_selection"),
        core_count=len(exports.get("core_stocks", []) or []),
        secondary_count=len(exports.get("secondary_stocks", []) or []),
    )
    return {
        "lines": list(result.get("lines") or []),
        "exports": exports,
        "module_logs": list(result.get("module_logs") or []) + logs,
    }
