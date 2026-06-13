def build_risk_review_conclusion_node(context, node_meta=None, node_lookup=None):
    delete_group = context.get("delete_group", []) or []
    keep_group = context.get("keep_group", []) or []
    focus_group = context.get("focus_group", []) or []
    next_stage_label = str(context.get("next_stage_label", "") or "Step 4").strip() or "Step 4"

    lines = [
        "**结论**:",
        f"- **明天先回避谁**: {len(delete_group)}只（烂板/炸板/后排，预判明日风险高）",
        f"- **明天先观察谁**: {len(keep_group)}只（有风险信号，需看明日竞价强弱）",
    ]
    if focus_group:
        lines.append(f"- **明天重点候选**: {len(focus_group)}只（风险复核后仍可进入{next_stage_label}）")
        lines.append(f"- **接着做什么**: 进入{next_stage_label}，为候选组预计算买点并筛出明天唯一能买的那只")
    else:
        lines.append("- **明天重点候选**: 0只（没有对象进入执行层）")
        lines.append("- **接着做什么**: 不再假装继续筛执行对象；后续只保留观察和空仓预案")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
