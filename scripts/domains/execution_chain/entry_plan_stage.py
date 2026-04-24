from domains.execution_chain.entry_plan_node_registry import build_entry_plan_node_specs
from domains.execution_chain.entry_plan_node_runtime import run_entry_plan_nodes
from domains.execution_chain.entry_plan_nodes.conclusion import build_entry_plan_conclusion_node
from domains.execution_chain.entry_plan_nodes.entry_judgement import build_entry_plan_judgement_node
from domains.execution_chain.entry_plan_nodes.overview import build_entry_plan_overview_node
from domains.execution_chain.entry_plan_nodes.priority_discipline import build_entry_plan_priority_discipline_node
from domains.execution_chain.entry_plan_nodes.stop_anchor import build_entry_plan_stop_anchor_node
from domains.execution_chain.entry_plan_nodes.trigger_summary import build_entry_plan_trigger_summary_node
from domains.execution_chain.stage_runtime import get_execution_stage_label


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.entry_plan_stage",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


ENTRY_PLAN_NODE_BUILDERS = {
    "overview": build_entry_plan_overview_node,
    "priority_discipline": build_entry_plan_priority_discipline_node,
    "entry_judgement": build_entry_plan_judgement_node,
    "trigger_summary": build_entry_plan_trigger_summary_node,
    "stop_anchor": build_entry_plan_stop_anchor_node,
    "conclusion": build_entry_plan_conclusion_node,
}


def build_entry_plan_runtime(stage_context, stage_meta, stage_lookup=None, enabled_node_keys=None):
    stage_context = stage_context or {}
    stage_lookup = stage_lookup or {}

    target_date = stage_context.get("target_date", "")
    mainline_name = str(stage_context.get("mainline_name", "") or "").strip()
    position_level = str(stage_context.get("position_level", "") or "").strip()
    final_gate = stage_context.get("final_gate", {}) or {}
    focus_group = stage_context.get("focus_group", []) or []
    keep_group = stage_context.get("keep_group", []) or []
    delete_group = stage_context.get("delete_group", []) or []
    extreme_conviction_list = stage_context.get("extreme_conviction_list", []) or []
    leader_memory_bank = stage_context.get("leader_memory_bank", []) or []
    market_research_snapshot = stage_context.get("market_research_snapshot", {}) or {}
    quant_system_available = bool(stage_context.get("quant_system_available", False))
    stop_prior_low_trading_days = int(stage_context.get("stop_prior_low_trading_days", 3) or 3)

    normalize_stock_code = stage_context["normalize_stock_code"]
    build_front_structure_layer_text = stage_context["build_front_structure_layer_text"]

    stage_label = str(stage_meta.get("label", "") or "Step 4").strip() or "Step 4"
    stage_title = str(stage_meta.get("title", "") or "明日买点预计算").strip() or "明日买点预计算"
    next_stage_label = get_execution_stage_label(stage_lookup, "pk_decision") if stage_lookup else "Step 5"

    conviction_codes = {
        normalize_stock_code(stock.get("code", ""))
        for stock in (extreme_conviction_list or [])
        if stock.get("code")
    }
    leader_memory_codes = {
        normalize_stock_code(stock.get("code", ""))
        for stock in (leader_memory_bank or [])
        if stock.get("code")
    }

    step4_structure_layer_text = build_front_structure_layer_text(
        final_gate=final_gate,
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        position_level=position_level,
        state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
        target_date=target_date,
    )

    node_context = {
        **stage_context,
        "stage_label": stage_label,
        "stage_title": stage_title,
        "next_stage_label": next_stage_label,
        "conviction_codes": conviction_codes,
        "leader_memory_codes": leader_memory_codes,
        "step4_structure_layer_text": step4_structure_layer_text,
        "quant_system_available": quant_system_available,
        "stop_prior_low_trading_days": stop_prior_low_trading_days,
    }
    node_specs = build_entry_plan_node_specs(ENTRY_PLAN_NODE_BUILDERS, enabled_node_keys=enabled_node_keys)
    runtime_result = run_entry_plan_nodes(node_specs, node_context)

    exports = {
        "conviction_codes": conviction_codes,
        "leader_memory_codes": leader_memory_codes,
        "executable_stocks": runtime_result["context"].get("executable_stocks", []) or [],
        "waiting_stocks": runtime_result["context"].get("waiting_stocks", []) or [],
        "untradable_stocks": runtime_result["context"].get("untradable_stocks", []) or [],
        "rejected_stocks": runtime_result["context"].get("rejected_stocks", []) or [],
        "step4_structure_layer_text": step4_structure_layer_text,
    }
    return {
        "lines": runtime_result["lines"],
        "exports": exports,
        "module_logs": list(runtime_result.get("module_logs") or []),
    }


def build_entry_plan_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    logs = []
    result = build_entry_plan_runtime(stage_context, stage_meta, stage_lookup=stage_lookup)

    exports = dict(result.get("exports") or {})
    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成明日买点预计算阶段",
        stage_key=(stage_meta or {}).get("stage_key", "entry_plan"),
        executable_count=len(exports.get("executable_stocks", []) or []),
        waiting_count=len(exports.get("waiting_stocks", []) or []),
        untradable_count=len(exports.get("untradable_stocks", []) or []),
        rejected_count=len(exports.get("rejected_stocks", []) or []),
    )
    return {
        "lines": list(result.get("lines") or []),
        "exports": exports,
        "module_logs": list(result.get("module_logs") or []) + logs,
    }
