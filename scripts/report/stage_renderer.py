from report.surface_wording import sanitize_user_visible_text


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
        lines.append(f"| {stage_key} | {sanitize_user_visible_text(title)} | {status} | {sanitize_user_visible_text(summary)} |")
    return "\n".join(lines)
