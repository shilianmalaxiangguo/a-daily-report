def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.market_overview_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_market_trend_sections_contract(data, target_date):
    data = data or {}
    lines = []
    logs = []

    lines.append("## 三、大盘趋势判断")
    lines.append("### 1. 指数表现")
    lines.append("| 指数 | 收盘 | 涨跌幅 | 趋势判断 |")
    lines.append("|------|------|--------|----------|")

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

    lines.append("### 2. 量能分析")
    lines.append("| 日期 | 成交额 | 量能状态 | 判断 |")
    lines.append("|------|--------|---------|------|")
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
    lines.append(f"| {target_date} | {turnover:.2f}亿元 | {level} | {judgment} |")
    lines.append("")

    lines.append("### 3. 市场情绪")
    lines.append("| 指标 | 数据 | 判断 |")
    lines.append("|------|------|------|")
    zt_count = len(data.get("zt_pool", []))
    dt_count = len(data.get("dt_pool", []))
    lines.append(f"| 涨停家数 | {zt_count}只 | {'赚钱效应尚可' if zt_count > 30 else '赚钱效应一般'} |")
    lines.append(f"| 跌停家数 | {dt_count}只 | {'恐慌情绪有限' if dt_count < 5 else '恐慌情绪蔓延'} |")
    up_count = data.get("market_stats", {}).get("up_count", 0)
    down_count = data.get("market_stats", {}).get("down_count", 0)
    zd_ratio = f"{up_count}:{down_count}" if down_count > 0 else f"{up_count}:0"
    rise_fall_ratio = up_count / down_count if down_count > 0 else 0
    ratio_judgment = "多头占优" if rise_fall_ratio > 2 else ("空头占优" if rise_fall_ratio < 0.5 else "相对均衡")
    lines.append(f"| 涨跌比 | {zd_ratio} | {ratio_judgment} |")
    lines.append("")

    _append_log(
        logs,
        "render.market_trend_sections",
        "success",
        "已生成大盘趋势判断章节",
        index_count=len(data.get("indices", {}) or {}),
        turnover=turnover,
        zt_count=zt_count,
        dt_count=dt_count,
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
