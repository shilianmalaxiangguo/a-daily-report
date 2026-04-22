def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.exchange_monitor_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _resolve_risk_level(deviation_days):
    if deviation_days >= 20:
        return "🔴 高风险"
    if deviation_days >= 10:
        return "🟡 中风险"
    return "🟢 低风险"


def build_exchange_monitor_sections_contract(data):
    data = data or {}
    lines = []
    logs = []

    lines.append("## 十二、异动监控")
    lines.append("> **数据来源**: 异动检测API（监控交易所异动规则）")
    lines.append("")

    lines.append("### 1. 当日异动预警")
    lines.append("**说明**: 当日涨幅达到触发条件将触发交易所异动监控")
    lines.append("")
    today_predictions = data.get("exchange_monitor_today", [])
    if today_predictions:
        lines.append("| 股票 | 代码 | 偏离天数 | 偏离度 | 触发条件 | 实际涨幅 | 触发状态 | 风险等级 |")
        lines.append("|------|------|----------|--------|----------|----------|----------|----------|")
        for pred in today_predictions:
            deviation_days = pred.get("deviation_days", 0)
            actual_change = pred.get("actual_change_pct")
            if actual_change is not None:
                actual_change_str = f"{actual_change:+.2f}%"
            else:
                actual_change_str = "N/A"
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
        lines.append("**暂无当日异动预警**")
        lines.append("")

    lines.append("### 2. 次日异动预警")
    lines.append("**说明**: 次日涨幅达到触发条件将触发交易所异动监控")
    lines.append("")
    nextday_predictions = data.get("exchange_monitor_nextday", [])
    if nextday_predictions:
        lines.append("| 股票 | 代码 | 偏离天数 | 偏离度 | 触发条件 | 风险等级 |")
        lines.append("|------|------|----------|--------|----------|----------|")
        for pred in nextday_predictions:
            deviation_days = pred.get("deviation_days", 0)
            lines.append(
                f"| {pred.get('name', '?')} | {pred.get('code', '?')} | {deviation_days}天 | {pred.get('deviation_pct', 0):.2f}% | "
                f"涨幅达{pred.get('trigger_pct', 0):+.2f}%触发 | {_resolve_risk_level(deviation_days)} |"
            )
        lines.append("")
    else:
        lines.append("**暂无次日异动预警**")
        lines.append("")

    lines.append("---")
    lines.append("")
    _append_log(
        logs,
        "render.exchange_monitor_sections",
        "success",
        "已生成异动监控章节",
        today_count=len(today_predictions),
        nextday_count=len(nextday_predictions),
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
