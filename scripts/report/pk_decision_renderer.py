from report.pk_decision_node_registry import build_pk_decision_node_specs
from report.pk_decision_node_runtime import run_pk_decision_nodes
from report.pk_decision_nodes import (
    build_pk_conclusion_node,
    build_pk_decision_stack_node,
    build_pk_multi_candidate_node,
    build_pk_observation_candidates_node,
    build_pk_overview_node,
    build_pk_pending_candidates_node,
    build_pk_single_candidate_node,
)


PK_DECISION_NODE_BUILDERS = {
    "overview": build_pk_overview_node,
    "decision_stack": build_pk_decision_stack_node,
    "single_candidate": build_pk_single_candidate_node,
    "multi_candidate": build_pk_multi_candidate_node,
    "pending_candidates": build_pk_pending_candidates_node,
    "observation_candidates": build_pk_observation_candidates_node,
    "conclusion": build_pk_conclusion_node,
}


def render_pk_decision_section(context):
    context = context or {}
    node_specs = build_pk_decision_node_specs(
        PK_DECISION_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    result = run_pk_decision_nodes(node_specs, context)
    return result["lines"]
