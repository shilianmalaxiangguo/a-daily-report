def render_execution_appendix(context):
    context = context or {}
    data_status = context.get("data_status") or {}
    step_status = context.get("step_status") or {}
    normalized_timer_steps = context.get("normalized_timer_steps") or []
    total_time = float(context.get("total_time", 0) or 0)
    target_date = context.get("target_date", "")
    generated_at = context.get("generated_at", "")
    report_version = context.get("report_version", "v2.5.0")

    lines = [
        "---",
        "",
        "## 附录：数据获取与执行步骤清单",
        "",
        "### 一、数据获取清单",
        "| 数据源 | 状态 | 说明 |",
        "|--------|------|------|",
    ]

    if data_status:
        for key, value in data_status.items():
            status_icon = "✅" if value else "❌"
            status_text = "成功" if value else "失败"
            lines.append(f"| {key} | {status_icon} {status_text} | {'数据正常' if value else '数据缺失或获取失败'} |")
    else:
        lines.append("| 无状态数据 | ❌ 失败 | 状态跟踪未启用 |")

    lines.extend(
        [
            "",
            "### 二、执行步骤清单",
            "| 步骤 | 状态 | 说明 |",
            "|------|------|------|",
        ]
    )

    if step_status:
        for key, value in step_status.items():
            status_icon = "✅" if value else "❌"
            status_text = "已执行" if value else "跳过/失败"
            lines.append(f"| {key} | {status_icon} {status_text} | {'正常完成' if value else '未执行或失败'} |")
    else:
        lines.append("| 无状态数据 | ❌ 失败 | 状态跟踪未启用 |")

    lines.extend(
        [
            "",
            "### 三、统计信息",
        ]
    )

    if data_status:
        success_count = sum(1 for value in data_status.values() if value)
        total_count = len(data_status)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        lines.append(f"- **数据源获取成功率**: {success_count}/{total_count} ({success_rate:.1f}%)")

    if step_status:
        success_count = sum(1 for value in step_status.values() if value)
        total_count = len(step_status)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        lines.append(f"- **步骤执行成功率**: {success_count}/{total_count} ({success_rate:.1f}%)")

    lines.extend(
        [
            "",
            "---",
            "",
            f"**报告生成时间**: {generated_at}",
            f"**数据日期**: {target_date}",
            f"**报告版本**: {report_version}",
            "",
        ]
    )

    if normalized_timer_steps:
        lines.extend(
            [
                "### 执行时间统计",
                "",
                "| 步骤 | 耗时 | 累计 | 占比 |",
                "|------|------|------|------|",
            ]
        )
        for step_name, elapsed, cumulative in normalized_timer_steps:
            percentage = (elapsed / total_time * 100) if total_time > 0 else 0
            lines.append(f"| {step_name} | {elapsed:.2f}s | {cumulative:.2f}s | {percentage:.1f}% |")
        lines.append(f"| **总计** | - | **{total_time:.2f}s** | 100% |")
        lines.append("")

    return lines
