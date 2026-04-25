from report.market_overview_node_registry import build_market_overview_node_specs
from report.market_overview_node_runtime import run_market_overview_nodes


def _data(context):
    return context.get("data") or {}


def _target_date(context):
    return str(context.get("target_date", "") or "")


def build_market_overview_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 二、市场基底"], "exports": {}, "module_logs": []}


def build_market_overview_indices_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    lines = [
        "### 1. 指数与市场底色",
        "| 指标 | 数值 | 涨跌幅 | 解读 |",
        "|------|------|--------|------|",
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
            lines.append(f"| {name} | {point:.2f} | {change:+.2f}% | {trend} |")

    if data.get("wind_a_alternative"):
        wa = data["wind_a_alternative"]
        point = wa.get("点位", wa.get("price", 0))
        change = wa.get("涨跌幅", wa.get("change_pct", 0))
        trend = "全市场普跌" if change < -1 else "震荡调整" if change < 0 else "强势上涨"
        lines.append(f"| 中证全指 | {point:.2f} | {change:+.2f}% | {trend} |")
    turnover = float(data.get("total_turnover", 0) or 0)
    zt_count = len(data.get("zt_pool", []))
    dt_count = len(data.get("dt_pool", []))
    up_count = data.get("market_stats", {}).get("up_count", 0)
    down_count = data.get("market_stats", {}).get("down_count", 0)
    lines.append(f"| 两市成交额 | {turnover:.2f}亿 | - | {'量能不差，但赚钱效应不足' if turnover >= 15000 else '量能偏弱，先看不做'} |")
    lines.append(f"| 涨停 / 跌停 | {zt_count} / {dt_count} | - | {'活跃度还在，但亏钱端不轻' if dt_count >= 3 else '情绪尚可'} |")
    lines.append(f"| 涨跌比 | {up_count} / {down_count} | - | {'下跌家数偏多，底色偏防守' if down_count > up_count else '多头仍占优'} |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_overview_volume_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    turnover = data.get("total_turnover", 0)
    zt_count = len(data.get("zt_pool", []))
    dt_count = len(data.get("dt_pool", []))
    up_count = data.get("market_stats", {}).get("up_count", 0)
    down_count = data.get("market_stats", {}).get("down_count", 0)

    if turnover > 20000 and dt_count <= 5 and up_count > down_count:
        market_state = "进攻"
        rr_text = "值得参与"
        meaning = "市场底色偏强，可继续跟踪主线"
    elif turnover > 15000 and down_count <= up_count:
        market_state = "震荡"
        rr_text = "勉强可参与"
        meaning = "量能尚可，但要等更清晰主线信号"
    else:
        market_state = "收缩防守"
        rr_text = "不值得主动参与"
        meaning = "默认先防守，等待下一次更清晰的强化"

    return {
        "lines": [
            "### 2. 市场状态结论",
            "| 项目 | 结论 |",
            "|------|------|",
            f"| 市场状态 | {market_state} |",
            f"| 当前盈亏比 | {rr_text} |",
            "| 当前结构位置 | 日线中枢内震荡 |",
            f"| 明日总体含义 | {meaning} |",
            "",
        ],
        "exports": {"market_overview_turnover": turnover},
        "module_logs": [],
    }


def build_market_overview_sentiment_node(context, node_meta=None, node_lookup=None):
    return {"lines": [], "exports": {}, "module_logs": []}


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
