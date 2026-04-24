from report.execution_chain_overview_node_registry import build_execution_chain_overview_node_specs
from report.execution_chain_overview_node_runtime import run_execution_chain_overview_nodes


def build_execution_chain_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 十三、统一执行链（狙击手视角）", "### 总-市场整体判断", ""], "exports": {}}


def build_execution_chain_market_summary_node(context, node_meta=None, node_lookup=None):
    primary_mainline = str(context.get("primary_mainline") or "").strip()
    market_trend = context.get("market_trend", "")
    lines = [f"- **基准指数**: 中证全指涨跌幅{float(context.get('csci_change', 0) or 0):+.2f}%"]
    if primary_mainline:
        lines.append(f"- **市场特征**: {market_trend}，主攻线{primary_mainline}领涨")
    else:
        lines.append(f"- **市场特征**: {market_trend}，板块轮动快速")
    lines.append("")
    return {"lines": lines, "exports": {}}


def build_execution_chain_path_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["### 分-六步决策路径", ""], "exports": {}}


EXECUTION_CHAIN_OVERVIEW_NODE_BUILDERS = {
    "header": build_execution_chain_header_node,
    "market_summary": build_execution_chain_market_summary_node,
    "path_header": build_execution_chain_path_header_node,
}


def build_execution_chain_overview_section_result(context):
    context = context or {}
    node_specs = build_execution_chain_overview_node_specs(
        EXECUTION_CHAIN_OVERVIEW_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_execution_chain_overview_nodes(node_specs, context)


def render_execution_chain_overview_section(context):
    return build_execution_chain_overview_section_result(context).get("lines", [])
