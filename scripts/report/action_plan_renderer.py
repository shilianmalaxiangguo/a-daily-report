from report.action_plan_node_registry import build_action_plan_node_specs
from report.action_plan_node_runtime import run_action_plan_nodes
from report.action_plan_nodes import (
    build_action_plan_alerts_node,
    build_action_plan_observation_blocks_node,
    build_action_plan_overview_node,
    build_action_plan_positioning_node,
    build_action_plan_schedule_node,
    build_action_plan_table_node,
)


ACTION_PLAN_NODE_BUILDERS = {
    "overview": build_action_plan_overview_node,
    "action_table": build_action_plan_table_node,
    "observation_blocks": build_action_plan_observation_blocks_node,
    "positioning": build_action_plan_positioning_node,
    "schedule": build_action_plan_schedule_node,
    "alerts": build_action_plan_alerts_node,
}


def render_action_plan_section(context):
    context = context or {}
    node_specs = build_action_plan_node_specs(
        ACTION_PLAN_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    result = run_action_plan_nodes(node_specs, context)
    return result["lines"]
