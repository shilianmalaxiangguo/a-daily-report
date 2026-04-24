from report.board_tag_analysis_node_registry import build_board_tag_analysis_node_specs
from report.board_tag_analysis_node_runtime import run_board_tag_analysis_nodes


def _data(context):
    return context.get("data") or {}


def build_board_tag_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 十一、板块标签分析"], "exports": {}, "module_logs": []}


def build_board_tag_source_note_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": [
            "> **数据来源**: 同花顺热榜API（基于热度前30个股的板块标签统计）",
            "> **说明**: 热度前30个股详情见第四章，本章聚焦板块分布与资金偏好分析",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_board_tag_analysis_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    analyze_sector_distribution = context.get("analyze_sector_distribution")
    tag_distribution = data.get("tag_distribution", {})
    status_distribution = data.get("status_distribution", {})
    high_lianban_stocks = data.get("high_lianban_stocks", [])
    lines = [
        "### 板块分布AI分析",
        "> **分析维度**: 热榜特征、热度分布、热榜偏好、资金偏好",
        "",
    ]

    if tag_distribution and callable(analyze_sector_distribution):
        analysis_text = analyze_sector_distribution(
            tag_distribution,
            status_distribution,
            high_lianban_stocks,
            top_n=15,
            market_stats=data.get("market_stats", {}),
        )
        lines.append(analysis_text)
    else:
        lines.append("**暂无板块分布数据**")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_board_tag_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["---", ""], "exports": {}, "module_logs": []}


BOARD_TAG_ANALYSIS_NODE_BUILDERS = {
    "header": build_board_tag_header_node,
    "source_note": build_board_tag_source_note_node,
    "analysis": build_board_tag_analysis_node,
    "footer": build_board_tag_footer_node,
}


def build_board_tag_analysis_section_result(context):
    context = context or {}
    node_specs = build_board_tag_analysis_node_specs(
        BOARD_TAG_ANALYSIS_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_board_tag_analysis_nodes(node_specs, context)
