def build_candidate_selection_overview_node(context, node_meta=None, node_lookup=None):
    stage_label = str(context.get("stage_label", "") or "Step 2").strip() or "Step 2"
    stage_title = str(context.get("stage_title", "") or "明日核心标的").strip() or "明日核心标的"
    return {
        "lines": [
            f"#### {stage_label} - {stage_title}",
            "> **先看结论**：从观察池继续缩到明日核心、次核心和跨线观察。",
            "> **只留什么**：主线最强的留核心，跨线对象只留观察。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }
