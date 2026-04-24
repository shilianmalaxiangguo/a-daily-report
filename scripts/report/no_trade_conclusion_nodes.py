from report.no_trade_conclusion_node_registry import build_no_trade_conclusion_node_specs
from report.no_trade_conclusion_node_runtime import run_no_trade_conclusion_nodes


def build_no_trade_table_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": [
            "#### 最终结论",
            "| 项目 | 结论 | 理由 |",
            "|------|------|------|",
            f"| 明日环境预判 | 🔴 极度困难 | {context.get('reason', '')} |",
            "| 明天观察池 | 无 | 环境恶劣，没有活口 |",
            f"| 明日核心股 | 无 | 未进入{context.get('candidate_stage_label', '候选筛选')} |",
            "| 明日策略 | 空仓观望 | 等待市场情绪修复 |",
            "",
        ],
        "exports": {},
    }


def build_no_trade_plan_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": [
            "**明日计划**: 等待市场情绪修复，跌停<15只、涨跌比>0.8时再评估。即使修复，也只轻仓试错。",
            "",
        ],
        "exports": {},
    }


NO_TRADE_CONCLUSION_NODE_BUILDERS = {
    "table": build_no_trade_table_node,
    "plan": build_no_trade_plan_node,
}


def render_no_trade_conclusion_section(context):
    context = context or {}
    node_specs = build_no_trade_conclusion_node_specs(
        NO_TRADE_CONCLUSION_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_no_trade_conclusion_nodes(node_specs, context).get("lines", [])
