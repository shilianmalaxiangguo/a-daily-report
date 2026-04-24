def build_watch_pool_abnormal_projection_node(context, node_meta=None, node_lookup=None):
    abnormal_projection_summary = context.get("abnormal_projection_summary", {}) or {}

    lines = [
        "**异常投影总结**（用二维异常去反推更高维的状态变化）",
        f"- **当前投影**: {abnormal_projection_summary.get('projection_label', '-')}"
        f"；承接{abnormal_projection_summary.get('resilient_count', 0)}只 / 转弱{abnormal_projection_summary.get('failed_count', 0)}只",
        f"- **当前信号**: {abnormal_projection_summary.get('projection_reason', '-')}",
    ]
    if abnormal_projection_summary.get("setup_breakdown"):
        setup_text = " / ".join(f"{label}{count}只" for label, count in abnormal_projection_summary.get("setup_breakdown", []))
        lines.append(f"- **Setup分布**: {setup_text}")
    lines.append(f"- **接着做什么**: {abnormal_projection_summary.get('action', '-')}")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
