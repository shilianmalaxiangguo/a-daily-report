from report.board_tag_analysis_node_registry import build_board_tag_analysis_node_specs
from report.board_tag_analysis_node_runtime import run_board_tag_analysis_nodes


def _data(context):
    return context.get("data") or {}


def _format_count(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _sorted_distribution_items(distribution):
    items = []
    for raw_name, raw_count in (distribution or {}).items():
        name = str(raw_name or "").strip()
        if not name:
            continue
        try:
            count = float(raw_count)
        except (TypeError, ValueError):
            continue
        items.append((name, count, raw_count))
    return sorted(items, key=lambda item: (-item[1], item[0]))


def _render_distribution_items(items, limit):
    rendered = []
    for name, _, raw_count in items[:limit]:
        rendered.append(f"{name}{_format_count(raw_count)}次")
    return "、".join(rendered)


def _render_board_tag_fallback_summary(tag_distribution, status_distribution, high_lianban_stocks, market_stats):
    tag_items = _sorted_distribution_items(tag_distribution)
    if not tag_items:
        return "**暂无板块分布数据**"

    top_name, _, top_raw_count = tag_items[0]
    top_tags_text = _render_distribution_items(tag_items, 8)
    lines = [
        f"**主热标签**：{top_name}（{_format_count(top_raw_count)}次）",
        f"- **热度分布**：{top_tags_text}。",
    ]

    status_items = _sorted_distribution_items(status_distribution)
    if status_items:
        lines.append(f"- **热榜偏好**：{_render_distribution_items(status_items, 5)}。")

    high_lianban_count = len(high_lianban_stocks or [])
    if high_lianban_count:
        lines.append(f"- **连板特征**：高位连板样本{high_lianban_count}只，短线资金仍集中在辨识度方向。")

    market_stats = market_stats or {}
    up_count = market_stats.get("up_count")
    down_count = market_stats.get("down_count")
    if up_count is not None and down_count is not None:
        lines.append(f"- **资金偏好**：上涨{up_count}家、下跌{down_count}家，热榜标签集中度优先看前排承接。")

    return "\n".join(lines)


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

    analysis_text = ""
    if tag_distribution and callable(analyze_sector_distribution):
        analysis_text = analyze_sector_distribution(
            tag_distribution,
            status_distribution,
            high_lianban_stocks,
            top_n=15,
            market_stats=data.get("market_stats", {}),
        )
    if not isinstance(analysis_text, str) or not analysis_text.strip():
        analysis_text = _render_board_tag_fallback_summary(
            tag_distribution,
            status_distribution,
            high_lianban_stocks,
            data.get("market_stats", {}),
        )
    lines.append(analysis_text)
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
