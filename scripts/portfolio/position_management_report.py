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

    t0_match = re.search(
        r"([\u4e00-\u9fa5A-Za-z0-9*STst]+?)\s*做T\s*买\s*(\d+(?:\.\d+)?)\s*手\s*卖\s*(\d+(?:\.\d+)?)\s*手",
        raw_text,
    )
    if t0_match:
        return [
            {
                "name": _clean_position_name(t0_match.group(1)),
                "buy_lots": float(t0_match.group(2)),
                "sell_lots": float(t0_match.group(3)),
                "trade_action": "做T",
            }
        ]

    account_fields = _extract_account_fields(raw_text)
    named_lot_positions = _extract_named_lot_holdings(raw_text)
    if named_lot_positions:
        named_lot_positions[0].update(account_fields)
        _apply_t0_trade_fields(raw_text, named_lot_positions)
        return [{key: value for key, value in position.items() if value is not None} for position in named_lot_positions]

    lot_matches = list(re.finditer(r"(\d+(?:\.\d+)?)\s*手\s*([\u4e00-\u9fa5A-Za-z0-9*STst]+)", raw_text))
    if not lot_matches:
        return positions

    for index, lot_match in enumerate(lot_matches):
        lots = float(lot_match.group(1))
        name = _clean_position_name(lot_match.group(2))
        if _is_position_name_noise(name):
            continue
        position = {
            "name": name,
            "lots": lots,
            "shares": int(lots * 100),
        }
        if index == 0:
            position.update(account_fields)
        positions.append({key: value for key, value in position.items() if value is not None})
    _apply_t0_trade_fields(raw_text, positions)
    return positions


def _extract_account_fields(raw_text):
    import re

    def _float_after(label):
        match = re.search(rf"{label}\s*([+-]?\d+(?:\.\d+)?)", raw_text)
        return float(match.group(1)) if match else None

    account_fields = {
        "cost": _float_after("成本"),
        "total_asset": _float_after("总资产"),
        "daily_profit": _float_after("当日盈利"),
    }
    capital_match = re.search(
        r"(?:账户总资金|总资金|账户资金)[^\d]*(\d+(?:\.\d+)?\s*w)|(\d+(?:\.\d+)?\s*w)\s*本金",
        raw_text,
        flags=re.IGNORECASE,
    )
    if capital_match:
        capital = capital_match.group(1) or capital_match.group(2)
        account_fields["account_capital"] = capital.replace(" ", "")
    profit_pct_match = re.search(r"当日盈利[^\d+-]*[+-]?\d+(?:\.\d+)?\s+([+-]?\d+(?:\.\d+)?)\s*%", raw_text)
    if profit_pct_match:
        account_fields["daily_profit_pct"] = float(profit_pct_match.group(1))
    return {key: value for key, value in account_fields.items() if value is not None}


def _extract_named_lot_holdings(raw_text):
    import re

    patterns = [
        re.compile(
            r"(?:^|[，,。；;\s])(?P<name>[\u4e00-\u9fa5A-Za-z*STst]{2,16})\s*"
            r"(?P<code>\d{6})\s*(?:当前收盘)?(?:仍)?(?:持有|持仓|仓位)?\s*"
            r"(?P<lots>\d+(?:\.\d+)?)\s*手(?P<note>T\+1仓|T\+0仓|底仓|旧仓|仓)?"
        ),
        re.compile(
            r"(?:^|[，,。；;\s])(?P<name>[\u4e00-\u9fa5A-Za-z*STst]{2,16})\s*"
            r"(?:当前收盘)?(?:仍)?(?:持有|持仓|仓位)\s*"
            r"(?P<lots>\d+(?:\.\d+)?)\s*手(?P<note>T\+1仓|T\+0仓|底仓|旧仓|仓)?"
        ),
    ]
    positions = []
    seen = set()
    for pattern in patterns:
        for match in pattern.finditer(raw_text):
            name = _clean_position_name(match.group("name"))
            if _is_position_name_noise(name):
                continue
            lots = float(match.group("lots"))
            code = (match.groupdict().get("code") or "").strip()
            key = (name, code, lots)
            if key in seen:
                continue
            seen.add(key)
            position = {
                "name": name,
                "code": code,
                "lots": lots,
                "shares": int(lots * 100),
                "holding_note": match.group("note") or "",
            }
            positions.append({field: value for field, value in position.items() if value})
    return positions


def _extract_t0_trade_fields(raw_text):
    import re

    if "做T" not in raw_text:
        return {}
    fields = {"trade_action": "做T"}
    buy_match = re.search(r"(?:买入|买)\s*(\d+(?:\.\d+)?)\s*手", raw_text)
    sell_match = re.search(r"(?:卖出|卖)\s*(?:旧仓)?\s*(\d+(?:\.\d+)?)\s*手", raw_text)
    if not sell_match:
        sell_match = re.search(r"(\d+(?:\.\d+)?)\s*手[^，,。；;]{0,8}(?:卖出|卖)", raw_text)
    if buy_match:
        fields["buy_lots"] = float(buy_match.group(1))
    if sell_match:
        fields["sell_lots"] = float(sell_match.group(1))
    return fields


def _apply_t0_trade_fields(raw_text, positions):
    if len(positions or []) != 1:
        return
    fields = _extract_t0_trade_fields(raw_text)
    if fields:
        positions[0].update(fields)


def _format_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    text = f"{number:.3f}".rstrip("0").rstrip(".")
    return text


def _format_lots(value):
    text = _format_number(value)
    return f"{text}手" if text else ""


def _clean_position_name(name):
    import re

    text = str(name or "").strip("，,。；; ")
    for prefix in ("我的仓位是", "仓位是", "持仓是", "我今天", "今天", "我"):
        if text.startswith(prefix) and len(text) > len(prefix):
            text = text[len(prefix):].strip()
    text = re.sub(r"^(?:现在|目前|另外|持仓是|持有)", "", text).strip()
    return text


def _is_position_name_noise(name):
    text = _clean_position_name(name)
    if not text:
        return True
    upper = text.upper()
    if upper in {"T", "T0", "T1", "T+0", "T+1"}:
        return True
    noise_words = {"旧仓", "底仓", "仓", "收盘", "当前收盘", "开盘", "尾盘", "买入", "卖出"}
    if text in noise_words:
        return True
    return any(word in text for word in ("买入", "卖出", "涨停卖出"))


def _position_share_text(position):
    shares = position.get("shares")
    if not shares and position.get("lots") not in (None, ""):
        shares = int(float(position.get("lots")) * 100)
    if shares:
        return f"{shares}股"
    return _format_lots(position.get("lots"))


def _format_t0_trade_text(position):
    if position.get("trade_action") != "做T":
        return ""
    buy_text = _format_lots(position.get("buy_lots"))
    sell_text = _format_lots(position.get("sell_lots"))
    parts = []
    if buy_text:
        parts.append(f"买入{buy_text}")
    if sell_text:
        parts.append(f"卖出{sell_text}")
    return f"今日做T{'、'.join(parts)}" if parts else "今日做T"


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
    holding_summaries = []
    primary_close = ""
    primary_support = str(primary.get("support_band") or "42.84~43.05").strip()
    for index, position in enumerate(positions):
        position = dict(position)
        quote = _find_position_quote(data, position)
        name = position.get("name") or quote.get("name") or quote.get("名称") or "旧仓"
        code = position.get("code") or position.get("stock_code") or quote.get("code") or quote.get("代码") or ""
        share_text = _position_share_text(position)
        t0_trade_text = _format_t0_trade_text(position)
        cost = _format_number(position.get("cost"))
        close = _format_number(quote.get("close") or quote.get("price") or quote.get("最新价"))
        label = f"{name}({code})" if code else str(name)
        summary_parts = [label]
        if share_text:
            summary_parts.append(share_text)
        holding_note = str(position.get("holding_note") or "").strip()
        if holding_note:
            summary_parts.append(holding_note)
        if t0_trade_text:
            summary_parts.append(t0_trade_text)
        if cost:
            summary_parts.append(f"成本{cost}")
        prefix = "" if t0_trade_text and not share_text else "持有"
        holding_summaries.append(f"{prefix}{'，'.join(summary_parts)}")
        if index == 0:
            primary_close = close
    decision = "先处理旧仓"
    if primary.get("trade_action") == "做T":
        decision = "若仍有旧仓，先按买点失败仓处理，09:50-10:10不能修复则优先处理"
    elif len(positions) == 1 and primary_close:
        decision = f"先看{primary_close}能否守住，跌破{primary_support}或09:50-10:10收不回先卖"
    summary = "；".join(holding_summaries) + f"；{decision}；新开仓0手"
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
