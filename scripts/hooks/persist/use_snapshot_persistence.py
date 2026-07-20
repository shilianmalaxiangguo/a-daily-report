from collections.abc import Mapping

from daily_report_snapshot_io import _save_data_snapshot
from hooks.persist.snapshot_analysis_node_registry import build_snapshot_analysis_node_specs
from hooks.persist.snapshot_analysis_node_runtime import run_snapshot_analysis_nodes
from hooks.persist.snapshot_analysis_nodes import (
    build_snapshot_mainline_history_node,
    build_snapshot_sector_turnover_node,
)
from knowledge.llm_wiki_context import is_complete_fresh_llm_wiki_context

HOOK_NAME = "persist.snapshot"


SNAPSHOT_ANALYSIS_NODE_BUILDERS = {
    "mainline_history_record": build_snapshot_mainline_history_node,
    "sector_turnover_snapshot": build_snapshot_sector_turnover_node,
}


def _build_snapshot_analysis_payload(ctx):
    request = ctx.get("request") or {}
    node_specs = build_snapshot_analysis_node_specs(
        SNAPSHOT_ANALYSIS_NODE_BUILDERS,
        enabled_node_keys=request.get("enabled_snapshot_node_keys"),
    )
    result = run_snapshot_analysis_nodes(node_specs, ctx)
    node_outputs = dict(result.get("node_outputs") or {})
    if not node_outputs:
        return {}
    return {
        **node_outputs,
        "module_logs": list(result.get("module_logs") or []),
    }


def _build_appendix_continuity_payload(ctx):
    execution_appendix = ((ctx.get("derived") or {}).get("execution_appendix") or {})
    appendix_b = execution_appendix.get("appendix_b") or {}
    appendix_c = execution_appendix.get("appendix_c") or {}
    continuity = {}
    if appendix_b:
        continuity["appendix_b"] = dict(appendix_b)
    if appendix_c:
        continuity["appendix_c"] = dict(appendix_c)
    return continuity


def run(ctx):
    request = ctx.get("request") or {}
    target_date = request.get("target_date")
    payload = {
        "rendered": ctx.get("rendered") or {},
        "decision": ctx.get("decision") or {},
        "diagnostics": ctx.get("diagnostics") or {},
        "runtime": {
            "module_logs": ((ctx.get("runtime") or {}).get("module_logs") or []),
            "trace_events": ((ctx.get("runtime") or {}).get("trace_events") or []),
        },
    }
    knowledge = ctx.get("knowledge") or {}
    has_llm_wiki = isinstance(knowledge, Mapping) and "llm_wiki" in knowledge
    if has_llm_wiki:
        normalized_target_date = str(target_date or "").strip()
        if not normalized_target_date:
            raise ValueError("目标交易日缺失，停止保存快照")
        if not is_complete_fresh_llm_wiki_context(
            knowledge.get("llm_wiki"),
            target_date=normalized_target_date,
        ):
            raise ValueError("知识引用资料不完整，停止保存快照")
        payload["knowledge"] = knowledge
        target_date = normalized_target_date
    analysis_payload = _build_snapshot_analysis_payload(ctx)
    appendix_continuity = _build_appendix_continuity_payload(ctx)
    if appendix_continuity:
        analysis_payload = dict(analysis_payload)
        analysis_payload["appendix_continuity"] = appendix_continuity
    if analysis_payload:
        payload["analysis"] = analysis_payload
    path = _save_data_snapshot(payload, target_date)
    return {
        "value": {"snapshot_path": path},
        "patches": {},
        "diagnostics": {"hook_name": HOOK_NAME, "status": "success", "warnings": []},
        "artifacts": {"snapshot_path": path},
    }
