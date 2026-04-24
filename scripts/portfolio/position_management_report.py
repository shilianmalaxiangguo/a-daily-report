from __future__ import annotations

__all__ = [
    "analyze_position_management",
    "analyze_position_management_report",
    "parse_position_string",
]

_MISSING = object()


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


def parse_position_string(position_str):
    return _parse_position_string_legacy_body(position_str)


def analyze_position_management(data, target_date, positions, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _analyze_position_management_legacy_body(data, target_date, positions)
    finally:
        _restore_runtime_bindings(previous)


def _parse_position_string(position_str):
    return _parse_position_string_legacy_body(position_str)


def _analyze_position_management(data, target_date, positions):
    return _analyze_position_management_legacy_body(data, target_date, positions)


def _parse_position_string_legacy_body(position_str):
    import re

    position_str = str(position_str or "").replace("我的仓位是", "").strip()
    pattern = r"([^\d\s]+)\s+(\d+(?:\.\d+)?)\s*%"
    matches = re.findall(pattern, position_str)

    positions = []
    for name, position in matches:
        positions.append({
            "name": name.strip(),
            "position": float(position),
        })
    return positions


def _analyze_position_management_legacy_body(data, target_date, positions):
    return analyze_position_management_report(
        data=data,
        positions=positions,
        build_trading_philosophy_lines=build_trading_philosophy_lines,
        display_mvp_mode=display_mvp_mode,
    )


def analyze_position_management_report(data, positions, build_trading_philosophy_lines, display_mvp_mode):
    if not positions:
        return ""

    report = [
        "",
        "---",
        "",
        "## 【个人持仓管理】（私密信息，仅供参考）",
        "",
        "> **交易策略**: 看大做小。日线中枢定环境，60分钟定买点，30分钟定止损；结构止损优先，最晚不超过单笔-5%。日报盘前若无30分钟数据，则先用锚定股近5个交易日最低价做大概止损放哪。",
    ]
    for philosophy_line in build_trading_philosophy_lines(include_system_requirement=False, compact=display_mvp_mode):
        report.append(f"> {philosophy_line[2:]}")
    report.extend(
        [
            "",
            "### 持仓详情",
            "",
            "| 股票 | 仓位 | 所属板块 | 涨跌幅 | 持有天数 | 板块趋势 | 操作建议 |",
            "|------|------|----------|--------|----------|----------|----------|",
        ]
    )

    sector_fund_flow = data.get("sector_fund_flow", {})
    inflow_list = sector_fund_flow.get("inflow", [])
    outflow_list = sector_fund_flow.get("outflow", [])
    zt_pool = data.get("zt_pool", [])
    dt_pool = data.get("dt_pool", [])
    hot_rank_top30 = data.get("hot_rank_top30", [])
    turnover_rank = data.get("turnover_rank", [])
    lhb_net_buy_top10 = data.get("lhb_net_buy_top10", [])
    lhb_net_sell_top10 = data.get("lhb_net_sell_top10", [])

    def resolve_stock_info(stock_name):
        for items, name_key, code_key, change_key, sector_key in (
            (hot_rank_top30, "name", "code", "change_pct", "sector"),
            (turnover_rank, "name", "code", "change_pct", "sector"),
            (zt_pool, "名称", "代码", "涨跌幅", "所属行业"),
            (dt_pool, "名称", "代码", "涨跌幅", "所属行业"),
            (lhb_net_buy_top10, "name", "code", "change_pct", "sector"),
            (lhb_net_sell_top10, "name", "code", "change_pct", "sector"),
        ):
            for stock in items:
                if stock.get(name_key) == stock_name:
                    return {
                        "name": stock_name,
                        "code": stock.get(code_key, ""),
                        "change_pct": stock.get(change_key, 0),
                        "sector": stock.get(sector_key, "未知"),
                    }
        return {"name": stock_name, "code": "", "change_pct": 0, "sector": "未知"}

    def resolve_sector_trend(sector):
        for flow in inflow_list:
            if flow.get("name") == sector:
                value = flow.get("zljlr", 0)
                if value > 10:
                    return "🔥 强势流入", value
                if value > 0:
                    return "🟢 温和流入", value
                if value > -10:
                    return "🟡 温和流出", value
                return "❄️ 大幅流出", value
        for flow in outflow_list:
            if flow.get("name") == sector:
                value = flow.get("zljlr", 0)
                if value > 10:
                    return "🔥 强势流入", value
                if value > 0:
                    return "🟢 温和流入", value
                if value > -10:
                    return "🟡 温和流出", value
                return "❄️ 大幅流出", value
        return "未知", 0

    for pos in positions:
        stock_name = pos["name"]
        position_pct = pos["position"]
        stock_info = resolve_stock_info(stock_name)
        sector = stock_info.get("sector", "未知")
        change_pct = float(stock_info.get("change_pct", 0) or 0)
        sector_trend, sector_fund = resolve_sector_trend(sector)

        if change_pct <= -9.9:
            operation_advice = "🔴 **立即卖出**（跌停）"
        elif sector_fund < -20 and change_pct < -3:
            operation_advice = "🟠 **建议卖出**（板块大幅流出+个股下跌）"
        elif change_pct > 5:
            operation_advice = "🟢 **考虑卖出**（大阳线，理想卖点）"
        elif sector_fund > 10 and change_pct > 0:
            operation_advice = "✅ **持有**（板块强势+个股上涨）"
        else:
            operation_advice = "⚠️ **观察**（等待确认）"

        report.append(
            f"| {stock_name} | {position_pct}% | {sector} | {change_pct:+.2f}% | 未知天 | {sector_trend} | {operation_advice} |"
        )

    report.extend(
        [
            "",
            "### 交易策略说明",
            "",
            "**观察期规则**（3~5个交易日，与个人纪律一致）：",
            "- 买入逻辑：先看日线环境，再等60分钟确认后介入",
            "- 止损逻辑：买后以30分钟结构止损为主；若盘前无30分钟数据，日报先用锚定股近5个交易日最低价给预估锚点；最晚不超过单笔-5%",
            "- 观察期内走势不及预期 → 卖出，不拖",
            "- 当日放量大阳线 → 理想主动卖点（他人确定性买点即本模式卖点）",
            "",
            "**禁止操作**：",
            "- ❌ 禁止做T（会亏两份钱）",
            "- ❌ 禁止追高（不买昨天/大前天的最佳个股）",
            "- ❌ 禁止买入板块急剧下跌或利空的股票",
            "",
            "**板块监控**：",
            "- 如果板块出现严重利空（如今天航天起飞失败），该板块所有股票都可不参与",
            "- 量化喜欢参与新题材，有新的出来，老的可以不看",
            "",
        ]
    )
    return "\n".join(report)
