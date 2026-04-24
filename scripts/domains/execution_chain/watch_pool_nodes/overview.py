def build_watch_pool_overview_node(context, node_meta=None, node_lookup=None):
    stage_label = str(context.get("stage_label", "") or "Step 1").strip() or "Step 1"
    stage_title = str(context.get("stage_title", "") or "明天观察池").strip() or "明天观察池"
    return {
        "lines": [
            f"#### {stage_label} - {stage_title}",
            "> **先看结论**：先把明天值得继续盯的对象缩成观察池。",
            "> **只看什么**：主线密度、延续形态、异动承接和记忆校验。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }
