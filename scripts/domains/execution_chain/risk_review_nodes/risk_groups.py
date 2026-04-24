def build_risk_review_risk_groups_node(context, node_meta=None, node_lookup=None):
    delete_group = context.get("delete_group", []) or []
    keep_group = context.get("keep_group", []) or []
    focus_group = context.get("focus_group", []) or []

    lines = ["**明日风险分组**", ""]
    if delete_group:
        lines.append(f"**🔴 明天先回避组**（{len(delete_group)}只，预判明日风险高）:")
        for item in delete_group:
            lines.append(f"- ❌ {item.get('name')}({item.get('code')}) - {item.get('reason')} - {item.get('tomorrow_risk', '')}")
        lines.append("")
    if keep_group:
        lines.append(f"**🟡 明天先观察组**（{len(keep_group)}只，需看明日竞价）:")
        for item in keep_group:
            lines.append(f"- ⚠️ {item.get('name')}({item.get('code')}) - {item.get('reason')} - {item.get('tomorrow_risk', '')}")
        lines.append("")
    if focus_group:
        lines.append(f"**🟢 明天重点候选组**（{len(focus_group)}只，通过风险筛选，继续进入执行层筛到可买股）:")
        for item in focus_group:
            lines.append(
                f"- ✅ {item.get('name')}({item.get('code')}) - "
                f"{item.get('reason', '风险可控')} - {item.get('tomorrow_risk', '风险可控')}"
            )
        lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
