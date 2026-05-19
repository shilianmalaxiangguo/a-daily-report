from report.market_analysis_node_registry import build_market_analysis_node_specs
from report.market_analysis_node_runtime import run_market_analysis_nodes
from report.market_condition_wording import describe_market_turnover_condition
from report.mainline_turnover_summary_support import resolve_mainline_attack_evidence_summary


def _data(context):
    return context.get("data") or {}


def _market_analysis(context):
    return context.get("market_analysis") or {}


def _indices(context):
    return context.get("indices") or {}


def _exit_analysis(context):
    return context.get("exit_analysis") or {}


def _main_sectors_info(context):
    return context.get("main_sectors_info") or []


def _secondary_sectors_info(context):
    return context.get("secondary_sectors_info") or []


def build_market_analysis_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 八、市场与板块分析", ""], "exports": {}, "module_logs": []}


def build_market_analysis_market_state_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    market_analysis = _market_analysis(context)
    indices = _indices(context)
    sh_change = context.get("sh_change", 0)
    total_turnover = data.get("total_turnover", 0)

    return {
        "lines": [
            "### 1. 市场整体状态",
            f"- **现在是什么情况**: {market_analysis.get('market_status', '震荡整理')}",
            f"- **主要指数**: 上证{sh_change:+.2f}%，深证{indices.get('深证成指', {}).get('涨跌幅', 0):+.2f}%，创业{indices.get('创业板指', {}).get('涨跌幅', 0):+.2f}%",
            f"- **量能水平**: {total_turnover:.2f}亿元，{describe_market_turnover_condition(data)}",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_analysis_mainline_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    attack_summary = resolve_mainline_attack_evidence_summary(data)
    exit_analysis = _exit_analysis(context)
    main_sectors_info = _main_sectors_info(context)
    mainline_name = exit_analysis.get("sector_name", "") if exit_analysis else ""
    lines = ["### 2. 主线板块分析"]
    if attack_summary and attack_summary.get("attack_state") != "confirmed_attack":
        lines.append("**当前主线**: 暂无确认主线")
        lines.append(f"> {attack_summary.get('confirmation_evidence') or '板块攻击证据不足'}")
    elif mainline_name and mainline_name != "暂无明确主线":
        lines.append(f"**当前主线**: {mainline_name}")
        lines.append("> 来源：统一执行链综合分析")
    elif main_sectors_info:
        lines.append("**主线板块**（涨停潮≥15只 + 出阳线）：")
        for idx, sector in enumerate(main_sectors_info[:3], 1):
            zt_count = sector.get("zt_count", 0)
            change = sector.get("change", 0)
            net_inflow = sector.get("net_inflow", 0)
            lines.append(f"{idx}. **{sector['name']}**: 涨停{zt_count}只，涨幅{change:+.2f}%，净流入{net_inflow:.1f}亿")
    else:
        lines.append("**暂无明确主线板块**（无涨停潮≥15只的板块）")
    lines.append("")
    return {"lines": lines, "exports": {"market_analysis_mainline_name": mainline_name}, "module_logs": []}


def build_market_analysis_secondary_node(context, node_meta=None, node_lookup=None):
    secondary_sectors_info = _secondary_sectors_info(context)
    lines = ["### 3. 次强板块分析"]
    if secondary_sectors_info:
        lines.append("**次强板块**（涨停5-14只 + 出阳线）：")
        for idx, sector in enumerate(secondary_sectors_info[:5], 1):
            zt_count = sector.get("zt_count", 0)
            change = sector.get("change", 0)
            net_inflow = sector.get("net_inflow", 0)
            lines.append(f"{idx}. **{sector['name']}**: 涨停{zt_count}只，涨幅{change:+.2f}%，净流入{net_inflow:.1f}亿")
    else:
        lines.append("**暂无明确次强板块**（无涨停5-14只的板块）")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_analysis_risk_sectors_node(context, node_meta=None, node_lookup=None):
    risk_sectors = _market_analysis(context).get("risk_sectors", [])
    lines = ["### 4. 风险板块分析"]
    if risk_sectors:
        for idx, sector in enumerate(risk_sectors[:3], 1):
            risk_level = "🔴高风险" if sector["risk_level"] == "high" else "🟡中风险"
            change = sector["change"]
            change_label = "跌幅" if change < 0 else "涨幅"
            lines.append(f"{idx}. **{sector['name']}**: 净流出{sector['net_outflow']:.1f}亿，{change_label}{change:+.2f}% ({risk_level})")
    else:
        lines.append("**暂无明确风险板块**")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_analysis_hot_chains_node(context, node_meta=None, node_lookup=None):
    market_analysis = _market_analysis(context)
    ai_group_concepts_into_chains = context.get("ai_group_concepts_into_chains")
    hot_sectors = market_analysis.get("hot_sectors", [])
    lines = ["### 5. 市场关注度分析"]
    if hot_sectors:
        all_concepts = [sector for sector, _ in hot_sectors]
        concept_chains = ai_group_concepts_into_chains(all_concepts) if callable(ai_group_concepts_into_chains) else {}
        lines.append("**热榜关注产业链**（AI归纳，热度前30个股概念分布）：")
        for chain_name, concepts in concept_chains.items():
            total_count = sum(count for sector, count in hot_sectors if sector in concepts)
            if len(concepts) > 1:
                lines.append(f"- **{chain_name}**: {total_count}只股票 (包含: {', '.join(concepts)})")
            else:
                lines.append(f"- **{chain_name}**: {total_count}只股票")
    else:
        lines.append("**热榜数据暂无**")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_analysis_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["", "---", ""], "exports": {}, "module_logs": []}


MARKET_ANALYSIS_NODE_BUILDERS = {
    "header": build_market_analysis_header_node,
    "market_state": build_market_analysis_market_state_node,
    "mainline": build_market_analysis_mainline_node,
    "secondary": build_market_analysis_secondary_node,
    "risk_sectors": build_market_analysis_risk_sectors_node,
    "hot_chains": build_market_analysis_hot_chains_node,
    "footer": build_market_analysis_footer_node,
}


def build_market_analysis_section_result(context):
    context = context or {}
    node_specs = build_market_analysis_node_specs(
        MARKET_ANALYSIS_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_market_analysis_nodes(node_specs, context)


def render_market_analysis_section(context):
    return build_market_analysis_section_result(context)["lines"]
