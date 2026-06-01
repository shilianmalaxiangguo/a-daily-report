from report.execution_chain_overview_node_registry import build_execution_chain_overview_node_specs
from report.execution_chain_overview_node_runtime import run_execution_chain_overview_nodes
from report.mainline_turnover_summary_support import (
    resolve_display_mainline_name,
    resolve_mainline_attack_evidence_summary,
)


def _looks_like_broad_selloff(market_trend, csci_change):
    text = str(market_trend or "")
    if any(marker in text for marker in ("大幅下跌", "放量下跌", "放量杀跌", "全面崩盘")):
        return True
    try:
        return float(csci_change or 0) <= -1.5
    except (TypeError, ValueError):
        return False


def build_execution_chain_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 十三、统一执行链（狙击手视角）", "### 总-市场整体判断", ""], "exports": {}}


def build_execution_chain_market_summary_node(context, node_meta=None, node_lookup=None):
    primary_mainline = str(context.get("primary_mainline") or "").strip()
    display_primary_mainline = resolve_display_mainline_name(context, fallback=primary_mainline)
    market_trend = context.get("market_trend", "")
    turnover_summary = context.get("mainline_turnover_summary") or {}
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    csci_change = float(context.get("csci_change", 0) or 0)
    csi1000_change_raw = context.get("csi1000_change")
    csi1000_change = None if csi1000_change_raw in (None, "") else float(csi1000_change_raw or 0)
    index_line = f"- **基准指数**: 中证全指涨跌幅{csci_change:+.2f}%"
    if csi1000_change is not None:
        index_line = f"{index_line}，中证1000涨跌幅{csi1000_change:+.2f}%"
    lines = [index_line]
    broad_selloff_change = min(csci_change, csi1000_change) if csi1000_change is not None else csci_change
    if str(turnover_summary.get("share_trend_label") or "").strip() == "逆势试攻" or (
        _looks_like_broad_selloff(market_trend, broad_selloff_change)
        and attack_summary
        and attack_summary.get("attack_state") == "confirmed_attack"
    ):
        attack_line = resolve_display_mainline_name(
            context,
            fallback=attack_summary.get("primary_line") or turnover_summary.get("current_mainline") or "局部方向",
        )
        lines.append(f"- **市场特征**: {market_trend}，放量杀跌里只有{attack_line}局部逆势活跃，先防踩踏")
    elif attack_summary and attack_summary.get("attack_state") != "confirmed_attack":
        lines.append(f"- **市场特征**: {market_trend}，{attack_summary.get('confirmation_evidence') or '主线攻击证据不足'}")
    elif display_primary_mainline:
        lines.append(f"- **市场特征**: {market_trend}，主攻线{display_primary_mainline}领涨")
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
