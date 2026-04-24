from report.market_overview_node_registry import build_market_overview_node_specs
from report.market_overview_node_runtime import run_market_overview_nodes


def _data(context):
    return context.get("data") or {}


def _target_date(context):
    return str(context.get("target_date", "") or "")


def build_market_overview_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 三、大盘趋势判断"], "exports": {}, "module_logs": []}


def build_market_overview_indices_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    lines = [
        "### 1. 指数表现",
        "| 指数 | 收盘 | 涨跌幅 | 趋势判断 |",
        "|------|------|--------|----------|",
    ]

    if data.get("indices"):
        for name, index_data in data["indices"].items():
            point = (
                index_data.get("点位")
                or index_data.get("close")
                or index_data.get("price")
                or index_data.get("收盘")
                or index_data.get("最新价")
                or 0
            )
            change = index_data.get("涨跌幅", index_data.get("change_pct", 0))
            trend = "弱势震荡" if change < -1 else "震荡调整" if change < 0 else "强势上涨"
            lines.append(f"| {name} | {point:.2f}点 | {change:+.2f}% | {trend} |")

    if data.get("wind_a_alternative"):
        wa = data["wind_a_alternative"]
        point = wa.get("点位", wa.get("price", 0))
        change = wa.get("涨跌幅", wa.get("change_pct", 0))
        trend = "全市场普跌" if change < -1 else "震荡调整" if change < 0 else "强势上涨"
        lines.append(f"| 中证全指 | {point:.2f}点 | {change:+.2f}% | {trend} |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_overview_volume_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    turnover = data.get("total_turnover", 0)
    if turnover > 20000:
        level = "放量"
        judgment = "量能充沛，市场活跃"
    elif turnover > 15000:
        level = "正常轮动"
        judgment = "量能适中，观望情绪"
    else:
        level = "缩量"
        judgment = "量能萎缩，不做"

    return {
        "lines": [
            "### 2. 量能分析",
            "| 日期 | 成交额 | 量能状态 | 判断 |",
            "|------|--------|---------|------|",
            f"| {_target_date(context)} | {turnover:.2f}亿元 | {level} | {judgment} |",
            "",
        ],
        "exports": {"market_overview_turnover": turnover},
        "module_logs": [],
    }


def build_market_overview_sentiment_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    zt_count = len(data.get("zt_pool", []))
    dt_count = len(data.get("dt_pool", []))
    up_count = data.get("market_stats", {}).get("up_count", 0)
    down_count = data.get("market_stats", {}).get("down_count", 0)
    zd_ratio = f"{up_count}:{down_count}" if down_count > 0 else f"{up_count}:0"
    rise_fall_ratio = up_count / down_count if down_count > 0 else 0
    ratio_judgment = "多头占优" if rise_fall_ratio > 2 else ("空头占优" if rise_fall_ratio < 0.5 else "相对均衡")

    return {
        "lines": [
            "### 3. 市场情绪",
            "| 指标 | 数据 | 判断 |",
            "|------|------|------|",
            f"| 涨停家数 | {zt_count}只 | {'赚钱效应尚可' if zt_count > 30 else '赚钱效应一般'} |",
            f"| 跌停家数 | {dt_count}只 | {'恐慌情绪有限' if dt_count < 5 else '恐慌情绪蔓延'} |",
            f"| 涨跌比 | {zd_ratio} | {ratio_judgment} |",
            "",
        ],
        "exports": {
            "market_overview_zt_count": zt_count,
            "market_overview_dt_count": dt_count,
        },
        "module_logs": [],
    }


MARKET_OVERVIEW_NODE_BUILDERS = {
    "header": build_market_overview_header_node,
    "indices": build_market_overview_indices_node,
    "volume": build_market_overview_volume_node,
    "sentiment": build_market_overview_sentiment_node,
}


def build_market_overview_section_result(context):
    context = context or {}
    node_specs = build_market_overview_node_specs(
        MARKET_OVERVIEW_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_market_overview_nodes(node_specs, context)


def render_market_overview_section(context):
    return build_market_overview_section_result(context)["lines"]
