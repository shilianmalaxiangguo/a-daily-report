from report.exchange_monitor_node_registry import build_exchange_monitor_node_specs
from report.exchange_monitor_node_runtime import run_exchange_monitor_nodes


def _data(context):
    return context.get("data") or {}


def _resolve_risk_level(deviation_days):
    if deviation_days >= 20:
        return "🔴 高风险"
    if deviation_days >= 10:
        return "🟡 中风险"
    return "🟢 低风险"


def build_exchange_monitor_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 十二、异动监控"], "exports": {}, "module_logs": []}


def build_exchange_monitor_source_note_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["> **数据来源**: 异动检测API（监控交易所异动规则）", ""], "exports": {}, "module_logs": []}


def build_exchange_monitor_today_alerts_node(context, node_meta=None, node_lookup=None):
    today_predictions = _data(context).get("exchange_monitor_today", [])
    lines = ["### 1. 当日异动预警", "**说明**: 当日涨幅达到触发条件将触发交易所异动监控", ""]
    if today_predictions:
        lines.extend(
            [
                "| 股票 | 代码 | 偏离天数 | 偏离度 | 触发条件 | 实际涨幅 | 触发状态 | 风险等级 |",
                "|------|------|----------|--------|----------|----------|----------|----------|",
            ]
        )
        for pred in today_predictions:
            deviation_days = pred.get("deviation_days", 0)
            actual_change = pred.get("actual_change_pct")
            actual_change_str = f"{actual_change:+.2f}%" if actual_change is not None else "N/A"
            is_triggered = pred.get("is_triggered")
            if is_triggered is True:
                trigger_status = "✅ 已触发"
            elif is_triggered is False:
                trigger_status = "⏳ 未触发"
            else:
                trigger_status = "❓ 未知"
            lines.append(
                f"| {pred.get('name', '?')} | {pred.get('code', '?')} | {deviation_days}天 | {pred.get('deviation_pct', 0):.2f}% | "
                f"{pred.get('trigger_pct', 0):+.2f}% | {actual_change_str} | {trigger_status} | {_resolve_risk_level(deviation_days)} |"
            )
        lines.append("")
    else:
        lines.extend(["**暂无当日异动预警**", ""])
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_exchange_monitor_nextday_alerts_node(context, node_meta=None, node_lookup=None):
    nextday_predictions = _data(context).get("exchange_monitor_nextday", [])
    lines = ["### 2. 次日异动预警", "**说明**: 次日涨幅达到触发条件将触发交易所异动监控", ""]
    if nextday_predictions:
        lines.extend(
            [
                "| 股票 | 代码 | 偏离天数 | 偏离度 | 触发条件 | 风险等级 |",
                "|------|------|----------|--------|----------|----------|",
            ]
        )
        for pred in nextday_predictions:
            deviation_days = pred.get("deviation_days", 0)
            lines.append(
                f"| {pred.get('name', '?')} | {pred.get('code', '?')} | {deviation_days}天 | {pred.get('deviation_pct', 0):.2f}% | "
                f"涨幅达{pred.get('trigger_pct', 0):+.2f}%触发 | {_resolve_risk_level(deviation_days)} |"
            )
        lines.append("")
    else:
        lines.extend(["**暂无次日异动预警**", ""])
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_exchange_monitor_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["---", ""], "exports": {}, "module_logs": []}


EXCHANGE_MONITOR_NODE_BUILDERS = {
    "header": build_exchange_monitor_header_node,
    "source_note": build_exchange_monitor_source_note_node,
    "today_alerts": build_exchange_monitor_today_alerts_node,
    "nextday_alerts": build_exchange_monitor_nextday_alerts_node,
    "footer": build_exchange_monitor_footer_node,
}


def build_exchange_monitor_section_result(context):
    context = context or {}
    node_specs = build_exchange_monitor_node_specs(
        EXCHANGE_MONITOR_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_exchange_monitor_nodes(node_specs, context)
