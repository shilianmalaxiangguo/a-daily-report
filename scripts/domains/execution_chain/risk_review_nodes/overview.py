def build_risk_review_overview_node(context, node_meta=None, node_lookup=None):
    stage_label = str(context.get("stage_label", "") or "Step 3").strip() or "Step 3"
    stage_title = str(context.get("stage_title", "") or "明日风险预判").strip() or "明日风险预判"
    return {
        "lines": [
            "",
            f"#### {stage_label} - {stage_title}",
            "> **先看结论**：先剔掉明天容易直接掉队的对象，再保留能继续进入执行层的候选。",
            "> **只排什么雷**：个股转弱、批量跌停和A杀风险。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }
