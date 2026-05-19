from domains.execution_chain.pk_decision_node_registry import build_pk_decision_node_specs
from domains.execution_chain.pk_decision_node_runtime import run_pk_decision_nodes
from domains.execution_chain.pk_decision_nodes.action_plan_context import build_pk_decision_action_plan_context_node
from domains.execution_chain.pk_decision_nodes.export_stage_state import build_pk_decision_export_stage_state_node
from domains.execution_chain.pk_decision_nodes.front_texts import build_pk_decision_front_texts_node
from domains.execution_chain.pk_decision_nodes.observation_pool import build_pk_decision_observation_pool_node
from domains.execution_chain.pk_decision_nodes.pk_context import build_pk_decision_pk_context_node
from domains.execution_chain.pk_decision_nodes.probe_position import build_pk_decision_probe_position_node
from domains.execution_chain.pk_decision_nodes.render_sections import build_pk_decision_render_sections_node
from domains.execution_chain.pk_decision_nodes.score_candidates import build_pk_decision_score_candidates_node
from domains.execution_chain.pk_decision_nodes.watch_anchor import build_pk_decision_watch_anchor_node


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.pk_decision_stage",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def format_closed_gate_buy_limit_text(position_level, final_gate):
    final_gate = final_gate or {}
    if final_gate.get("allow_attack_50_ready"):
        return "等参与窗口确认；未确认按0%不参与"
    return f"⛔{position_level}禁止新开仓"


PK_DECISION_NODE_BUILDERS = {
    "score_candidates": build_pk_decision_score_candidates_node,
    "observation_pool": build_pk_decision_observation_pool_node,
    "watch_anchor": build_pk_decision_watch_anchor_node,
    "probe_position": build_pk_decision_probe_position_node,
    "front_texts": build_pk_decision_front_texts_node,
    "pk_context": build_pk_decision_pk_context_node,
    "action_plan_context": build_pk_decision_action_plan_context_node,
    "render_sections": build_pk_decision_render_sections_node,
    "export_stage_state": build_pk_decision_export_stage_state_node,
}


def build_pk_decision_runtime(stage_context, stage_meta, stage_lookup=None, enabled_node_keys=None):
    stage_context = stage_context or {}
    stage_meta = stage_meta or {}
    node_context = {
        **stage_context,
        "stage_label": str(stage_meta.get("label", "") or "Step 5").strip() or "Step 5",
        "stage_title": str(stage_meta.get("title", "") or "PK决胜局（期望值模型）").strip() or "PK决胜局（期望值模型）",
    }
    node_specs = build_pk_decision_node_specs(PK_DECISION_NODE_BUILDERS, enabled_node_keys=enabled_node_keys)
    runtime_result = run_pk_decision_nodes(node_specs, node_context)
    return {
        "lines": runtime_result["lines"],
        "exports": dict(runtime_result.get("context", {}).get("stage_exports", {}) or {}),
        "module_logs": list(runtime_result.get("module_logs") or []),
    }


def build_pk_decision_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    logs = []
    result = build_pk_decision_runtime(stage_context, stage_meta, stage_lookup=stage_lookup)
    exports = dict(result.get("exports") or {})
    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成PK决策阶段",
        stage_key=(stage_meta or {}).get("stage_key", "pk_decision"),
        trade_gate_open=bool(exports.get("trade_gate_open")),
        has_best_stock=bool(exports.get("best_stock")),
        has_watch_anchor=bool(exports.get("watch_anchor")),
    )
    return {
        "lines": list(result.get("lines") or []),
        "exports": exports,
        "module_logs": list(result.get("module_logs") or []) + logs,
    }
