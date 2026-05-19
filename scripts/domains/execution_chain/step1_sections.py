from domains.execution_chain.stage_runtime import get_execution_stage_label
from domains.execution_chain.watch_pool_node_registry import build_watch_pool_node_specs
from domains.execution_chain.watch_pool_node_runtime import run_watch_pool_nodes
from domains.execution_chain.watch_pool_nodes.a_kill_filter import build_watch_pool_a_kill_filter_node
from domains.execution_chain.watch_pool_nodes.abnormal_projection import build_watch_pool_abnormal_projection_node
from domains.execution_chain.watch_pool_nodes.abnormal_watch import build_watch_pool_abnormal_watch_node
from domains.execution_chain.watch_pool_nodes.conclusion import build_watch_pool_conclusion_node
from domains.execution_chain.watch_pool_nodes.leader_memory import build_watch_pool_leader_memory_node
from domains.execution_chain.watch_pool_nodes.mainline_competition import build_watch_pool_mainline_competition_node
from domains.execution_chain.watch_pool_nodes.memory_validation import build_watch_pool_memory_validation_node
from domains.execution_chain.watch_pool_nodes.overview import build_watch_pool_overview_node
from domains.execution_chain.watch_pool_nodes.trend_density import build_watch_pool_trend_density_node
from domains.execution_chain.watch_pool_nodes.watch_ranking import build_watch_pool_watch_ranking_node


WATCH_POOL_NODE_BUILDERS = {
    "overview": build_watch_pool_overview_node,
    "trend_density": build_watch_pool_trend_density_node,
    "mainline_competition": build_watch_pool_mainline_competition_node,
    "leader_memory": build_watch_pool_leader_memory_node,
    "memory_validation": build_watch_pool_memory_validation_node,
    "watch_ranking": build_watch_pool_watch_ranking_node,
    "abnormal_watch": build_watch_pool_abnormal_watch_node,
    "abnormal_projection": build_watch_pool_abnormal_projection_node,
    "a_kill_filter": build_watch_pool_a_kill_filter_node,
    "conclusion": build_watch_pool_conclusion_node,
}


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


def build_step1_watch_runtime(
    *,
    sector_trend_snapshot_step1,
    mainline_competition_snapshot,
    mainline_turnover_summary=None,
    leader_memory_bank,
    tracking_memory_status,
    watchlist,
    abnormal_watch_pool,
    abnormal_projection_summary,
    filtered_by_a_kill,
    display_mvp_mode,
    is_degraded_abnormal_snapshot,
    format_abnormal_observation_columns,
    stage_meta=None,
    stage_lookup=None,
    enabled_node_keys=None,
):
    sector_trend_snapshot_step1 = sector_trend_snapshot_step1 or []
    mainline_competition_snapshot = mainline_competition_snapshot or []
    leader_memory_bank = leader_memory_bank or []
    tracking_memory_status = tracking_memory_status or {}
    watchlist = watchlist or []
    abnormal_watch_pool = abnormal_watch_pool or []
    abnormal_projection_summary = abnormal_projection_summary or {}
    filtered_by_a_kill = filtered_by_a_kill or []
    stage_meta = stage_meta or {}
    stage_lookup = stage_lookup or {}
    stage_label = str(stage_meta.get("label", "") or "Step 1").strip() or "Step 1"
    stage_title = str(stage_meta.get("title", "") or "明天观察池").strip() or "明天观察池"
    next_stage_label = get_execution_stage_label(stage_lookup, "candidate_selection") if stage_lookup else "Step 2"
    node_context = {
        "stage_label": stage_label,
        "stage_title": stage_title,
        "next_stage_label": next_stage_label,
        "sector_trend_snapshot_step1": sector_trend_snapshot_step1,
        "mainline_competition_snapshot": mainline_competition_snapshot,
        "mainline_turnover_summary": mainline_turnover_summary or {},
        "leader_memory_bank": leader_memory_bank,
        "tracking_memory_status": tracking_memory_status,
        "watchlist": watchlist,
        "abnormal_watch_pool": abnormal_watch_pool,
        "abnormal_projection_summary": abnormal_projection_summary,
        "filtered_by_a_kill": filtered_by_a_kill,
        "display_mvp_mode": display_mvp_mode,
        "is_degraded_abnormal_snapshot": is_degraded_abnormal_snapshot,
        "format_abnormal_observation_columns": format_abnormal_observation_columns,
    }
    node_specs = build_watch_pool_node_specs(WATCH_POOL_NODE_BUILDERS, enabled_node_keys=enabled_node_keys)
    return run_watch_pool_nodes(node_specs, node_context)


def build_step1_watch_sections(
    *,
    sector_trend_snapshot_step1,
    mainline_competition_snapshot,
    mainline_turnover_summary=None,
    leader_memory_bank,
    tracking_memory_status,
    watchlist,
    abnormal_watch_pool,
    abnormal_projection_summary,
    filtered_by_a_kill,
    display_mvp_mode,
    is_degraded_abnormal_snapshot,
    format_abnormal_observation_columns,
    stage_meta=None,
    stage_lookup=None,
    enabled_node_keys=None,
):
    result = build_step1_watch_runtime(
        sector_trend_snapshot_step1=sector_trend_snapshot_step1,
        mainline_competition_snapshot=mainline_competition_snapshot,
        mainline_turnover_summary=mainline_turnover_summary,
        leader_memory_bank=leader_memory_bank,
        tracking_memory_status=tracking_memory_status,
        watchlist=watchlist,
        abnormal_watch_pool=abnormal_watch_pool,
        abnormal_projection_summary=abnormal_projection_summary,
        filtered_by_a_kill=filtered_by_a_kill,
        display_mvp_mode=display_mvp_mode,
        is_degraded_abnormal_snapshot=is_degraded_abnormal_snapshot,
        format_abnormal_observation_columns=format_abnormal_observation_columns,
        stage_meta=stage_meta,
        stage_lookup=stage_lookup,
        enabled_node_keys=enabled_node_keys,
    )
    return result["lines"]
