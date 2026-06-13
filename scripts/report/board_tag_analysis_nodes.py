from report.board_tag_analysis_node_registry import build_board_tag_analysis_node_specs
from report.board_tag_analysis_node_runtime import run_board_tag_analysis_nodes


def _data(context):
    return context.get("data") or {}


def _format_count(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_pct(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if number.is_integer():
        return f"{int(number)}%"
    return f"{number:.1f}%"


def _safe_int(value):
    try:
        if value in (None, ""):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _hot_rank_sample_label(data):
    data = data or {}
    target = _safe_int(data.get("hot_rank_sample_target")) or 50
    sample_size = _safe_int(data.get("hot_rank_sample_size"))
    if not sample_size:
        sample_size = len(data.get("hot_rank_top50") or data.get("hot_rank_top30") or data.get("integrated_hot_list") or [])
    if sample_size and sample_size < target:
        return f"热度样本{sample_size}/{target}只，关键数据不完整，停止生成"
    return f"热度前{target}个股"


def _market_breadth_complete(market_stats):
    market_stats = market_stats or {}
    return _safe_int(market_stats.get("up_count")) > 0 and _safe_int(market_stats.get("down_count")) > 0


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


def _build_board_tag_rank_rows(tag_distribution, *, limit=12):
    items = [item for item in _sorted_distribution_items(tag_distribution) if item[1] > 0]
    visible_items = list(items[:limit])
    total = sum(count for _, count, _ in items)
    max_count = max((count for _, count, _ in visible_items), default=0)
    if total <= 0 or max_count <= 0:
        return []

    rows = []
    for name, count, raw_count in visible_items:
        share_pct = count / total * 100
        bar_width = max(1, round(count / max_count * 20))
        rows.append(
            {
                "tag": name,
                "count": raw_count,
                "share_pct": share_pct,
                "bar": "#" * bar_width,
            }
        )
    return rows


def _render_board_tag_rank_chart(tag_distribution):
    rows = _build_board_tag_rank_rows(tag_distribution)
    if not rows:
        return []

    lines = [
        "### 标签热度排行榜",
        "> **读法**: 按热榜标签出现次数排序，条形长度按本表最高次数归一化；占比为该标签在全部标签出现次数中的比例。",
        "",
        "| 排名 | 标签 | 出现次数 | 全标签占比 | 热度条 |",
        "|------|------|----------|----------|--------|",
    ]
    for index, row in enumerate(rows, 1):
        lines.append(
            "| {rank} | {tag} | {count} | {share_pct} | `{bar}` |".format(
                rank=index,
                tag=row["tag"],
                count=_format_count(row["count"]),
                share_pct=_format_pct(row["share_pct"]),
                bar=row["bar"],
            )
        )
    lines.append("")
    return lines


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
    if _market_breadth_complete(market_stats):
        lines.append(f"- **资金偏好**：上涨{up_count}家、下跌{down_count}家，热榜标签集中度优先看前排承接。")
    elif up_count is not None or down_count is not None:
        lines.append("- **资金偏好**：涨跌家数未采集，关键数据不完整，停止生成。")

    return "\n".join(lines)


def build_board_tag_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 十一、板块标签分析"], "exports": {}, "module_logs": []}


def build_board_tag_source_note_node(context, node_meta=None, node_lookup=None):
    sample_label = _hot_rank_sample_label(_data(context))
    return {
        "lines": [
            f"> **数据来源**: 同花顺热榜API（基于{sample_label}的板块标签统计）",
            f"> **说明**: {sample_label}详情见第四章，本章聚焦板块分布与资金偏好分析",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_board_tag_rank_chart_node(context, node_meta=None, node_lookup=None):
    lines = _render_board_tag_rank_chart(_data(context).get("tag_distribution", {}))
    return {"lines": lines, "exports": {}, "module_logs": []}


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
        market_stats = data.get("market_stats", {})
        analysis_text = analyze_sector_distribution(
            tag_distribution,
            status_distribution,
            high_lianban_stocks,
            top_n=15,
            market_stats=market_stats if _market_breadth_complete(market_stats) else {},
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
    "tag_rank_chart": build_board_tag_rank_chart_node,
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
