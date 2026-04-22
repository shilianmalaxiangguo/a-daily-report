def render_stage_board(report_stages):
    report_stages = report_stages or []
    lines = [
        "## 阶段看板",
        "| stage_key | 标题 | 状态 | 摘要 |",
        "|-----------|------|------|------|",
    ]
    for stage in report_stages:
        stage_key = str(stage.get("stage_key", "") or "").strip() or "-"
        title = str(stage.get("title", "") or "").strip() or "-"
        status = str(stage.get("status", "") or "").strip() or "-"
        summary = str(stage.get("summary", "") or "").strip() or "-"
        lines.append(f"| {stage_key} | {title} | {status} | {summary} |")
    return "\n".join(lines)
