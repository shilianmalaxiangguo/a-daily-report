from __future__ import annotations

__all__ = [
    "analyze_position_management",
    "analyze_position_management_report",
    "parse_position_string",
    "build_personal_position_context",
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

    raw_text = str(position_str or "").strip()
    position_str = raw_text.replace("我的仓位是", "").strip()
    pattern = r"([^\d\s]+)\s+(\d+(?:\.\d+)?)\s*%"
    matches = re.findall(pattern, position_str)

    positions = []
    for name, position in matches:
        positions.append({
            "name": name.strip(),
            "position": float(position),
        })
    if positions:
        return positions

    lot_match = re.search(r"(\d+(?:\.\d+)?)\s*手\s*([\u4e00-\u9fa5A-Za-z0-9*STst]+)", raw_text)
    if not lot_match:
        return positions

    def _float_after(label):
        match = re.search(rf"{label}\s*([+-]?\d+(?:\.\d+)?)", raw_text)
        return float(match.group(1)) if match else None

    lots = float(lot_match.group(1))
    name = lot_match.group(2).strip("，,。；; ")
    position = {
        "name": name,
        "lots": lots,
        "shares": int(lots * 100),
        "cost": _float_after("成本"),
        "total_asset": _float_after("总资产"),
        "daily_profit": _float_after("当日盈利"),
    }
    capital_match = re.search(r"(\d+(?:\.\d+)?\s*w)\s*本金", raw_text, flags=re.IGNORECASE)
    if capital_match:
        position["account_capital"] = capital_match.group(1).replace(" ", "")
    profit_pct_match = re.search(r"当日盈利[^\d+-]*[+-]?\d+(?:\.\d+)?\s+([+-]?\d+(?:\.\d+)?)\s*%", raw_text)
    if profit_pct_match:
        position["daily_profit_pct"] = float(profit_pct_match.group(1))
    positions.append({key: value for key, value in position.items() if value is not None})
    return positions


def _format_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    text = f"{number:.3f}".rstrip("0").rstrip(".")
    return text


def _find_position_quote(data, position):
    data = data or {}
    code = str(position.get("code") or position.get("stock_code") or "").strip()
    name = str(position.get("name") or "").strip()
    fallback = {}
    for key in ("turnover_rank", "lhb_net_sell_top10", "lhb_net_buy_top10", "hot_rank_top30", "zt_pool", "dt_pool"):
        rows = data.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_code = str(row.get("code") or row.get("代码") or "").strip()
            row_name = str(row.get("name") or row.get("名称") or "").strip()
            if (code and row_code == code) or (name and row_name == name):
                if row.get("close") not in (None, "") or row.get("price") not in (None, "") or row.get("最新价") not in (None, ""):
                    return row
                if not fallback:
                    fallback = row
    return fallback


def _format_account_profile(position):
    capital = str(position.get("account_capital") or "").strip()
    total_asset = _format_number(position.get("total_asset"))
    daily_profit = _format_number(position.get("daily_profit"))
    daily_profit_pct = _format_number(position.get("daily_profit_pct"))
    parts = []
    if capital:
        parts.append(f"{capital}本金")
    if total_asset:
        parts.append(f"总资产{total_asset}")
    if daily_profit and daily_profit_pct:
        sign = "+" if not daily_profit_pct.startswith("-") else ""
        parts.append(f"当日盈利{daily_profit}（{sign}{daily_profit_pct}%）")
    elif daily_profit:
        parts.append(f"当日盈利{daily_profit}")
    return "；".join(parts) or "约1w账户"


def build_personal_position_context(data, positions):
    positions = list(positions or [])
    if not positions:
        return {}
    primary = dict(positions[0])
    quote = _find_position_quote(data, primary)
    name = primary.get("name") or quote.get("name") or quote.get("名称") or "旧仓"
    code = primary.get("code") or primary.get("stock_code") or quote.get("code") or quote.get("代码") or ""
    shares = primary.get("shares")
    if not shares and primary.get("lots") not in (None, ""):
        shares = int(float(primary.get("lots")) * 100)
    cost = _format_number(primary.get("cost"))
    close = _format_number(quote.get("close") or quote.get("price") or quote.get("最新价"))
    support = str(primary.get("support_band") or "42.84~43.05").strip()
    label = f"{name}({code})" if code else str(name)
    summary_parts = [f"持有{label}"]
    if shares:
        summary_parts.append(f"{shares}股")
    if cost:
        summary_parts.append(f"成本{cost}")
    decision = "先处理旧仓"
    if close:
        decision = f"先看{close}能否守住，跌破{support}或09:50-10:10收不回先卖"
    summary = "，".join(summary_parts) + f"；{decision}；新开仓0手"
    return {
        "account_profile": {"capital_text": _format_account_profile(primary)},
        "existing_position_summary": {
            "has_position": True,
            "summary": summary,
        },
    }


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
        "> **交易策略**: 看大做小。日线中枢定环境，买卖动作只落在三段固定交易窗口；结构止损优先，最晚不超过单笔-5%。日报盘前若无30分钟数据，则先用锚定股近5个交易日最低价做大概止损放哪。",
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
            "- 买入逻辑：先看日线环境，再按09:30-09:35、09:50-10:10或14:30-14:55三段固定交易窗口分层介入",
            "- 止损逻辑：买后按失效价和单笔-5%底线处理风险；若盘前无更细数据，日报先用锚定股近5个交易日最低价给预估锚点；最晚不超过单笔-5%",
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
