def build_pk_decision_render_sections_node(context, node_meta=None, node_lookup=None):
    render_pk_decision_section = context["render_pk_decision_section"]
    render_action_plan_section = context["render_action_plan_section"]
    lines = []
    lines.extend(render_pk_decision_section(context))
    lines.extend(render_action_plan_section(context))
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
