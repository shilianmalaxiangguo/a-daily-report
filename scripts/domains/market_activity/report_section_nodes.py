from domains.market_activity.quote_lookup import build_market_quote_lookup, normalize_stock_code, resolve_change_pct
from domains.market_activity.report_section_node_registry import (
    build_market_activity_advanced_node_specs,
    build_market_activity_basic_node_specs,
)
from domains.market_activity.report_section_node_runtime import run_market_activity_nodes
from domains.market_activity.support import _is_valid_sector_label


def _data(context):
    return context.get("data") or {}


def _stock_full_info(context):
    return context.get("stock_full_info") or {}


def _zt_pool(context):
    return _data(context).get("zt_pool", []) or []


def _dt_pool(context):
    return _data(context).get("dt_pool", []) or []


def _hot_rank_data(context):
    data = _data(context)
    return data.get("hot_rank_top50") or data.get("hot_rank_top30") or []


def _hot_rank_sample_limit(context):
    data = _data(context)
    sample_size = _safe_float(data.get("hot_rank_sample_size"), 0)
    sample_target = _safe_float(data.get("hot_rank_sample_target"), 50)
    if sample_size > 0:
        return int(sample_size)
    if sample_target > 0:
        return int(sample_target)
    return 50


def _lianban_data(context):
    return _data(context).get("lianban_data", []) or []


def _lhb_data(context):
    data = _data(context)
    return (data.get("lhb_net_buy_top10", []) or []) + (data.get("lhb_net_sell_top10", []) or [])


def _resolved_turnover_over_100b(context):
    data = _data(context)
    explicit = data.get("turnover_over_100b", [])
    if explicit:
        return explicit
    return [stock for stock in (data.get("turnover_rank", []) or []) if stock.get("turnover", 0) > 100]


def _display_text(value):
    current = value
    for _ in range(4):
        if isinstance(current, dict):
            if current.get("value") not in (None, ""):
                current = current.get("value")
                continue
            if current.get("name") not in (None, ""):
                current = current.get("name")
                continue
            break
        nested_value = getattr(current, "value", None)
        if nested_value not in (None, "") and nested_value is not current:
            current = nested_value
            continue
        break
    return str(current or "").strip()


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _first_positive_float(*values):
    for value in values:
        parsed = _safe_float(value, 0.0)
        if parsed > 0:
            return parsed
    return 0.0


def _build_quote_lookup(context):
    data = _data(context)
    return build_market_quote_lookup(
        stock_full_info=_stock_full_info(context),
        turnover_rank=data.get("turnover_rank", []),
        lianban_data=data.get("lianban_data", []),
        zt_pool=data.get("zt_pool", []),
        dt_pool=data.get("dt_pool", []),
    )


def _stock_matches(stock, stock_name, stock_code):
    if not isinstance(stock, dict):
        return False
    expected_code = normalize_stock_code(stock_code)
    for key in ("code", "代码", "stock_code", "symbol", "prod_code"):
        if expected_code and normalize_stock_code(stock.get(key)) == expected_code:
            return True
    expected_name = str(stock_name or "").strip()
    for key in ("name", "名称", "stock_name", "stock_chi_name", "prod_name"):
        if expected_name and str(stock.get(key) or "").strip() == expected_name:
            return True
    return False


def _first_valid_plate_name(plates):
    for plate in plates or []:
        if isinstance(plate, dict):
            candidates = (
                plate.get("plate_name"),
                plate.get("name"),
                plate.get("concept_name"),
                plate.get("sector"),
            )
        else:
            candidates = (plate,)
        for candidate in candidates:
            if _is_valid_sector_label(candidate):
                return str(candidate).strip()
    return ""


def _resolve_context_sector(context, stock_name, stock_code):
    data = _data(context)
    xgb_data = data.get("xuangubao_data") or {}

    for item in xgb_data.get("xuangubao_limit_up_reasons", []) or []:
        if _stock_matches(item, stock_name, stock_code):
            plate_name = _first_valid_plate_name(item.get("related_plates") or [])
            if plate_name:
                return plate_name

    for news in xgb_data.get("xuangubao_news", []) or []:
        if not isinstance(news, dict):
            continue
        stocks = list(news.get("stocks") or []) + list(news.get("all_stocks") or [])
        if any(_stock_matches(stock, stock_name, stock_code) for stock in stocks):
            plate_name = _first_valid_plate_name(
                news.get("plates")
                or news.get("bkj_infos")
                or news.get("plate_infos")
                or []
            )
            if plate_name:
                return plate_name

    for stock in data.get("hot_rank_top30", []) or []:
        if _stock_matches(stock, stock_name, stock_code):
            concept = _first_valid_plate_name(stock.get("concepts") or [])
            if concept:
                return concept

    return ""


def build_hot_rank_header_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": [
            "## 四、热度核心结果",
            "> **先看什么**: 只看热度是否继续抱团到主线核心，别被杂讯热榜带偏。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_hot_rank_table_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    stock_full_info = _stock_full_info(context)
    get_stock_status = context.get("get_stock_status")
    get_stock_sector = context.get("get_stock_sector")
    analyze_candlestick_pattern = context.get("analyze_candlestick_pattern")
    zt_pool = _zt_pool(context)
    dt_pool = _dt_pool(context)

    lines = [
        "| 排名 | 股票 | 代码 | 热度分(w) | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 连板标签 | 蜡烛图形态 |",
        "|------|------|------|-----------|----------|--------|--------|--------|--------|--------|----------|------------|",
    ]
    hot_rank_rows = _hot_rank_data(context)
    if hot_rank_rows:
        for idx, stock in enumerate(hot_rank_rows[: _hot_rank_sample_limit(context)], 1):
            name = stock.get("name", "?")
            code = stock.get("code", "?")
            rate_val = int(stock.get("rate", 0)) if isinstance(stock.get("rate"), str) else stock.get("rate", 0)
            rate_w = rate_val / 10000
            tag = stock.get("popularity_tag", "-")
            info = stock_full_info.get(code, {})
            change_pct = info.get("change_pct", 0)
            high = info.get("high", 0)
            low = info.get("low", 0)
            open_price = info.get("open", 0)
            close = info.get("close", 0)
            if callable(get_stock_status):
                get_stock_status(name, code, zt_pool, dt_pool, change_pct)
            sector = get_stock_sector(
                name,
                code,
                hot_rank_data=_hot_rank_data(context),
                zt_pool_data=data.get("zt_pool_by_sector", {}),
                zt_pool_raw=zt_pool,
                dt_pool_raw=dt_pool,
                lianban_data=_lianban_data(context),
                lhb_data=_lhb_data(context),
                xuangubao_data=data.get("xuangubao_data", {}),
                sector_fund_flow=data.get("sector_fund_flow", {}),
            )
            pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct)
            lines.append(
                f"| {idx} | {name} | {code} | {rate_w:.1f}w | {sector} | {change_pct:+.2f}% | {high:.2f} | {low:.2f} | {open_price:.2f} | {close:.2f} | {tag} | {pattern_name}({pattern_score}分) |"
            )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_turnover_header_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": [
            "## 五、成交核心结果",
            "**先看什么**: 只看真放量的成交核心，缩量凑热闹的不算。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_turnover_table_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    stock_full_info = _stock_full_info(context)
    get_stock_status = context.get("get_stock_status")
    get_stock_sector = context.get("get_stock_sector")
    analyze_candlestick_pattern = context.get("analyze_candlestick_pattern")
    zt_pool = _zt_pool(context)
    dt_pool = _dt_pool(context)

    lines = [
        "| 排名 | 股票 | 代码 | 成交额 | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 隔日判断 | 蜡烛图形态 |",
        "|------|------|------|--------|----------|--------|--------|--------|--------|--------|----------|------------|",
    ]
    over_100b = _resolved_turnover_over_100b(context)
    if over_100b:
        for idx, stock in enumerate(over_100b[:15], 1):
            name = stock.get("name", "?")
            code = stock.get("code", "?").replace("sz", "").replace("sh", "")
            stock_turnover = stock.get("turnover", 0)
            info = stock_full_info.get(code, {})
            change_pct = info.get("change_pct", 0)
            high = info.get("high", 0)
            low = info.get("low", 0)
            open_price = info.get("open", 0)
            close = info.get("close", 0)
            if callable(get_stock_status):
                get_stock_status(name, code, zt_pool, dt_pool, change_pct)
            sector = stock.get("sector", "") or stock.get("所属行业", "") or stock.get("industry", "")
            if not _is_valid_sector_label(sector):
                sector = _resolve_context_sector(context, name, code)
            if not _is_valid_sector_label(sector) and callable(get_stock_sector):
                sector = get_stock_sector(
                    name,
                    code,
                    hot_rank_data=_hot_rank_data(context),
                    zt_pool_data=data.get("zt_pool_by_sector", {}),
                    zt_pool_raw=zt_pool,
                    dt_pool_raw=dt_pool,
                    lianban_data=_lianban_data(context),
                    lhb_data=_lhb_data(context),
                    xuangubao_data=data.get("xuangubao_data", {}),
                    sector_fund_flow=data.get("sector_fund_flow", {}),
                )
            if not _is_valid_sector_label(sector):
                sector = "待补充板块"
            pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct)
            judgment = "观望" if stock_turnover > 150 else "关注" if stock_turnover > 120 else "谨慎"
            lines.append(
                f"| {idx} | {name} | {code} | {stock_turnover:.2f}亿 | {sector} | {change_pct:+.2f}% | {high:.2f} | {low:.2f} | {open_price:.2f} | {close:.2f} | {judgment} | {pattern_name}({pattern_score}分) |"
            )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_sector_fund_header_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    lines = ["## 六、板块资金流向"]
    if data.get("sector_fund_flow", {}).get("is_historical", False):
        lines.extend(
            [
                "> **⚠️ 历史日期提示**：板块资金流向数据仅支持当日实时获取，历史数据暂不可用。",
                "> 如需查看历史资金流向，请参考当日报告或相关金融数据平台。",
                "",
            ]
        )
    else:
        lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_sector_fund_inflow_node(context, node_meta=None, node_lookup=None):
    data = _data(context)

    # 尝试使用增强模块
    enhanced_report = None
    try:
        from domains.market_state.sector_fund_flow_enhancer import build_enhanced_sector_fund_flow_report

        enhanced_report = build_enhanced_sector_fund_flow_report(
            sector_fund_flow=data.get("sector_fund_flow") or {},
            zt_pool=data.get("zt_pool") or [],
            lianban_data=data.get("lianban_data") or [],
            market_data={
                "index_change_pct": _safe_float(data.get("wind_a_alternative", {}).get("change_pct")),
                "up_ratio": _safe_float(data.get("market_stats", {}).get("up_count")) / max(_safe_float(data.get("market_stats", {}).get("total_count"), 1), 1) * 100,
                "top50_turnover_share_pct": _safe_float(data.get("top50_turnover_share_pct")),
            },
            sector_turnover_history=data.get("sector_turnover_history") or []
        )
    except Exception as e:
        print(f"[警告] 板块资金流向增强模块加载失败: {e}")

    # 如果增强模块可用,使用增强的Markdown章节
    if enhanced_report and enhanced_report.get("markdown_sections"):
        lines = enhanced_report["markdown_sections"]
        return {"lines": lines, "exports": {}, "module_logs": []}

    # 否则使用原始格式
    lines = [
        "### 资金流入TOP10",
        "| 排名 | 板块 | 净流入 | 涨跌幅 |",
        "|------|------|--------|--------|",
    ]
    sector_fund_flow = data.get("sector_fund_flow") or {}
    if sector_fund_flow.get("inflow"):
        for idx, sector in enumerate(sector_fund_flow["inflow"][:10], 1):
            lines.append(f"| {idx} | {sector.get('name', '?')} | {sector.get('zljlr', 0):+.2f}亿 | {sector.get('zdf', 0):+.2f}% |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_sector_fund_outflow_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    lines = [
        "### 资金流出结果",
        "| 排名 | 板块 | 净流出 | 涨跌幅 |",
        "|------|------|--------|--------|",
    ]
    sector_fund_flow = data.get("sector_fund_flow") or {}
    if sector_fund_flow.get("outflow"):
        for idx, sector in enumerate(sector_fund_flow["outflow"][:10], 1):
            lines.append(f"| {idx} | {sector.get('name', '?')} | {abs(sector.get('zljlr', 0)):.2f}亿 | {sector.get('zdf', 0):+.2f}% |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_lhb_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 七、龙虎榜结果", ""], "exports": {}, "module_logs": []}


def _build_lhb_trade_rows(context, items, amount_title, amount_formatter):
    data = _data(context)
    stock_full_info = _stock_full_info(context)
    get_stock_sector = context.get("get_stock_sector")
    analyze_candlestick_pattern = context.get("analyze_candlestick_pattern")
    zt_pool = _zt_pool(context)
    dt_pool = _dt_pool(context)

    lines = [
        f"| 排名 | 股票 | 代码 | {amount_title} | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 涨停状态 | 蜡烛图形态 |",
        "|------|------|------|-----------|----------|--------|--------|--------|--------|--------|----------|------------|",
    ]
    for item in items[:10]:
        code = item.get("code", "?")
        info = stock_full_info.get(code, {})
        name = item.get("name") or info.get("name", "?")
        change_pct = _safe_float(info.get("change_pct", item.get("change_pct", 0)))
        high = _first_positive_float(info.get("high"), item.get("high"), item.get("high_price"), item.get("最高价"))
        low = _first_positive_float(info.get("low"), item.get("low"), item.get("low_price"), item.get("最低价"))
        open_price = _first_positive_float(info.get("open"), item.get("open"), item.get("open_price"), item.get("开盘价"))
        close = _first_positive_float(info.get("close"), item.get("close"), item.get("close_price"), item.get("收盘价"))
        sector = item.get("sector", "")
        if not _is_valid_sector_label(sector):
            sector = _resolve_context_sector(context, name, code)
        if not _is_valid_sector_label(sector) and callable(get_stock_sector):
            sector = get_stock_sector(
                name,
                code,
                hot_rank_data=_hot_rank_data(context),
                zt_pool_data=data.get("zt_pool_by_sector", {}),
                zt_pool_raw=zt_pool,
                dt_pool_raw=dt_pool,
                lianban_data=_lianban_data(context),
                lhb_data=_lhb_data(context),
                xuangubao_data=data.get("xuangubao_data", {}),
                skip_api_call=False,
            )
        if not _is_valid_sector_label(sector):
            sector = "待补充板块"
        if callable(analyze_candlestick_pattern):
            pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct)
        else:
            pattern_name, pattern_score = "未知", 0
        lines.append(
            f"| {item.get('rank', 0)} | {name} | {code} | {amount_formatter(item.get('net_buy_amount_yi', 0))}亿 | {sector} | {change_pct:+.2f}% | {high:.2f} | {low:.2f} | {open_price:.2f} | {close:.2f} | {item.get('zt_status', '正常')} | {pattern_name}({pattern_score}分) |"
        )
    lines.append("")
    return lines


def build_lhb_buy_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    lines = ["### 净买入结果"]
    lines.extend(_build_lhb_trade_rows(context, data.get("lhb_net_buy_top10", []) or [], "净买入(亿)", lambda value: f"{value:.2f}"))
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_lhb_sell_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    lines = ["### 净流出结果"]
    lines.extend(_build_lhb_trade_rows(context, data.get("lhb_net_sell_top10", []) or [], "净流出(亿)", lambda value: f"{abs(value):.2f}"))
    return {"lines": lines, "exports": {}, "module_logs": []}


MARKET_ACTIVITY_BASIC_NODE_BUILDERS = {
    "hot_rank_header": build_hot_rank_header_node,
    "hot_rank_table": build_hot_rank_table_node,
    "turnover_header": build_turnover_header_node,
    "turnover_table": build_turnover_table_node,
    "sector_fund_header": build_sector_fund_header_node,
    "sector_fund_inflow": build_sector_fund_inflow_node,
    "sector_fund_outflow": build_sector_fund_outflow_node,
    "lhb_header": build_lhb_header_node,
    "lhb_buy": build_lhb_buy_node,
    "lhb_sell": build_lhb_sell_node,
}


def build_market_activity_basic_section_result(context):
    context = context or {}
    node_specs = build_market_activity_basic_node_specs(
        MARKET_ACTIVITY_BASIC_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_market_activity_nodes(node_specs, context)


def render_market_activity_basic_sections(context):
    return build_market_activity_basic_section_result(context)["lines"]


def build_lianban_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    stock_full_info = _stock_full_info(context)
    get_stock_sector = context.get("get_stock_sector")
    analyze_candlestick_pattern = context.get("analyze_candlestick_pattern")

    lines = [
        "## 九、连板结果",
        "> **先看什么**: 只看高标强度、首板扩散和连板梯队有没有继续收拢。",
        "",
    ]
    if data.get("lianban_data"):
        lianban_groups = {}
        for stock in data["lianban_data"]:
            lianban_days = stock.get("lianban_days", 0)
            lianban_groups.setdefault(lianban_days, []).append(stock)
        for days in sorted(lianban_groups.keys(), reverse=True):
            stocks = lianban_groups[days]
            if days >= 3:
                lines.append(f"### {days}连板结果({len(stocks)}只)")
            elif days == 2:
                lines.append(f"### 2连板结果({len(stocks)}只)")
            else:
                lines.append(f"### 首板结果({len(stocks)}只)")
            lines.extend(
                [
                    "| 股票 | 代码 | 所属板块 | 涨跌幅 | 首次涨停 | 最高价 | 最低价 | 开盘价 | 收盘价 | 涨停原因 | 蜡烛图形态 |",
                    "|------|------|----------|--------|----------|--------|--------|--------|--------|----------|------------|",
                ]
            )
            for stock in stocks[:5]:
                name = stock.get("name", "?")
                code = stock.get("code", "?").replace(".SZ", "").replace(".SS", "")
                info = stock_full_info.get(code, {})
                change_pct = _safe_float(info.get("change_pct", stock.get("change_pct", 0)))
                high = _first_positive_float(info.get("high"), stock.get("high"), stock.get("high_price"), stock.get("最高价"))
                low = _first_positive_float(info.get("low"), stock.get("low"), stock.get("low_price"), stock.get("最低价"))
                open_price = _first_positive_float(info.get("open"), stock.get("open"), stock.get("open_price"), stock.get("开盘价"))
                close = _first_positive_float(info.get("close"), stock.get("close"), stock.get("close_price"), stock.get("price"), stock.get("最新价"))
                first_limit_time = stock.get("first_limit_time", "-")
                reason = stock.get("reason", "-")
                if len(reason) > 30:
                    reason = reason[:30] + "..."
                sector = get_stock_sector(
                    name,
                    code,
                    hot_rank_data=_hot_rank_data(context),
                    zt_pool_data=data.get("zt_pool_by_sector", {}),
                    zt_pool_raw=_zt_pool(context),
                    dt_pool_raw=_dt_pool(context),
                    lianban_data=_lianban_data(context),
                    lhb_data=_lhb_data(context),
                    xuangubao_data=data.get("xuangubao_data", {}),
                )
                pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct, first_limit_time)
                lines.append(
                    f"| {name} | {code} | {sector} | {change_pct:+.2f}% | {first_limit_time} | {high:.2f} | {low:.2f} | {open_price:.2f} | {close:.2f} | {reason} | {pattern_name}({pattern_score}分) |"
                )
            lines.append("")
    else:
        lines.extend(["**暂无连板结果**", ""])
    lines.extend(["---", ""])
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_advanced_header_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": [
            "## 十、多维交易结果",
            "> **先看什么**: 只看量能异常、龙虎榜强度和板块共振能不能转成明日动作。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_volume_anomalies_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    quote_lookup = _build_quote_lookup(context)

    lines = [
        "### 1. 放量结果",
        "| 股票 | 异常类型 | 强度 | 成交量分位 | 涨跌幅 | 当前信号 |",
        "|------|----------|------|------------|--------|----------|",
    ]
    volume_anomalies = data.get("volume_anomalies", [])
    if volume_anomalies:
        for anomaly in volume_anomalies[:10]:
            if isinstance(anomaly, dict):
                a_name = anomaly.get("stock_name", anomaly.get("name", ""))
                a_code = anomaly.get("stock_code", anomaly.get("code", ""))
                a_type_val = _display_text(anomaly.get("anomaly_type", anomaly.get("type", "")))
                a_strength = _display_text(anomaly.get("strength", ""))
                a_pct = _safe_float(anomaly.get("volume_percentile", 0))
                a_chg = resolve_change_pct(quote_lookup, stock_code=a_code, stock_name=a_name, fallback=anomaly.get("price_change", 0))
                a_reason = anomaly.get("reason", "")
            else:
                a_name = anomaly.stock_name
                a_code = getattr(anomaly, "stock_code", getattr(anomaly, "code", ""))
                a_type_val = _display_text(getattr(anomaly, "anomaly_type", getattr(anomaly, "type", "")))
                a_strength = _display_text(getattr(anomaly, "strength", ""))
                a_pct = _safe_float(getattr(anomaly, "volume_percentile", 0))
                a_chg = resolve_change_pct(quote_lookup, stock_code=a_code, stock_name=a_name, fallback=getattr(anomaly, "price_change", 0))
                a_reason = anomaly.reason
            lines.append(f"| {a_name} | {a_type_val} | {a_strength} | {a_pct:.0f}% | {a_chg:+.2f}% | {a_reason} |")
    else:
        lines.append("| - | - | - | - | - | 当前无放量结果 |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def _display_lhb_provider(provider):
    text = str(provider or "").strip()
    if text in {"legacy.lhb_snapshot", "finshare.get_lhb"}:
        return "Tushare top_list / 备用龙虎榜源"
    return text or "Tushare top_list"


def _render_lhb_rank_row(item):
    if not isinstance(item, dict):
        return ""
    name = item.get("stock_name") or item.get("name") or item.get("code") or ""
    net_buy = item.get("net_buy")
    if net_buy in (None, ""):
        net_buy = item.get("net_buy_amount_yi", 0)
    net_buy_value = _safe_float(net_buy)
    money_type = "龙虎榜净买入" if net_buy_value >= 0 else "龙虎榜净卖出"
    pattern = item.get("pattern") or item.get("sector") or "-"
    signal_strength = item.get("signal_strength") or item.get("zt_status") or "-"
    return f"| {name} | {net_buy_value:+.2f} | {money_type} | {_display_text(pattern)} | - | {_display_text(signal_strength)} |"


def build_lhb_analysis_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    lhb_status = str(data.get("lhb_data_status") or "").strip()
    lhb_provider = _display_lhb_provider(data.get("lhb_provider"))
    lines = [
        "### 2. 龙虎榜结果",
        "| 股票 | 净买入(亿) | 资金性质 | 行为模式 | 近3日上榜 | 信号强度 |",
        "|------|-----------|----------|----------|-----------|----------|",
    ]
    lhb_analysis = data.get("lhb_analysis", [])
    if lhb_analysis:
        for item in lhb_analysis[:10]:
            if isinstance(item, dict):
                lines.append(
                    f"| {item.get('stock_name', '')} | {item.get('net_buy', 0):+.2f} | {_display_text(item.get('money_type', ''))} | {_display_text(item.get('pattern', ''))} | {item.get('recent_appearances', 0)}次 | {_display_text(item.get('signal_strength', ''))} |"
                )
            else:
                lines.append(
                    f"| {item.stock_name} | {item.net_buy:+.2f} | {_display_text(item.money_type)} | {_display_text(item.pattern)} | {item.recent_appearances}次 | {_display_text(item.signal_strength)} |"
                )
    else:
        rank_rows = (data.get("lhb_net_buy_top10", []) or []) + (data.get("lhb_net_sell_top10", []) or [])
        if rank_rows:
            for item in rank_rows[:10]:
                rendered = _render_lhb_rank_row(item)
                if rendered:
                    lines.append(rendered)
            if len(lines) > 3:
                lines.append("")
                return {"lines": lines, "exports": {}, "module_logs": []}
        if lhb_status == "upstream_empty":
            lines.append(f"| - | - | - | - | - | {lhb_provider} 龙虎榜暂未返回数据，待发布后再判断 |")
        else:
            lines.append("| - | - | - | - | - | 当前无龙虎榜结果 |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_resonance_scores_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    lines = ["### 2. 板块共振结果"]
    resonance_scores = data.get("resonance_scores", {})
    if resonance_scores:
        def _get_total_score(score_data):
            return score_data.get("total_score", 0) if isinstance(score_data, dict) else getattr(score_data, "total_score", 0)

        def _get_resonance_level(score_data):
            if isinstance(score_data, dict):
                return _display_text(score_data.get("resonance_level", ""))
            return _display_text(score_data.resonance_level)

        filtered_scores = {
            k: v
            for k, v in resonance_scores.items()
            if _get_total_score(v) >= 5 and _get_resonance_level(v) not in ("无共振", "NONE", "")
        }
        if filtered_scores:
            lines.extend(
                [
                    "| 板块 | 综合得分 | 共振级别 | 强势维度 | 资金流向 | 涨停强度 | 龙虎榜 |",
                    "|------|----------|----------|----------|----------|----------|--------|",
                ]
            )
            for sector_name, score_data in sorted(filtered_scores.items(), key=lambda item: _get_total_score(item[1]), reverse=True)[:15]:
                if isinstance(score_data, dict):
                    sd_total = score_data.get("total_score", 0)
                    sd_strength_dims = score_data.get("strength_dimensions", [])
                    sd_dim_scores = score_data.get("dimension_scores", {})
                    sd_res_level_val = _display_text(score_data.get("resonance_level", ""))
                else:
                    sd_total = score_data.total_score
                    sd_strength_dims = score_data.strength_dimensions
                    sd_dim_scores = score_data.dimension_scores
                    sd_res_level_val = _display_text(score_data.resonance_level)
                dimension_names = {
                    "fund_flow": "资金流向",
                    "price_action": "价格行为",
                    "volume": "成交量",
                    "lhb": "龙虎榜",
                    "limit_up": "涨停强度",
                    "sentiment": "市场情绪",
                }
                dimensions_cn = [dimension_names.get(d, d) for d in sd_strength_dims[:3]]
                dimension_str = ", ".join(dimensions_cn)
                level_icon = "🔥" if sd_res_level_val == "强共振" else "🟡" if sd_res_level_val == "弱共振" else "⚪"
                lines.append(
                    f"| {sector_name} | {sd_total:.1f} | {level_icon} {sd_res_level_val} | {dimension_str} | {sd_dim_scores.get('fund_flow', 0):.0f} | {sd_dim_scores.get('limit_up', 0):.0f} | {sd_dim_scores.get('lhb', 0):.0f} |"
                )
        else:
            lines.append("*当前无共振结果*")
    else:
        lines.append("*暂无共振结果*")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_trade_signals_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    lines = ["### 3. 交易信号结果"]
    trade_signals = data.get("trade_signals", [])
    if trade_signals:
        def _get_signal_score(sig):
            return sig.get("score", 0) if isinstance(sig, dict) else getattr(sig, "score", 0)

        filtered_signals = [sig for sig in trade_signals if _get_signal_score(sig) > 5]
        if filtered_signals:
            lines.extend(
                [
                    "| 信号类型 | 板块/个股 | 得分 | 操作建议 | 当前证据 | 风险等级 |",
                    "|----------|-----------|------|----------|----------|----------|",
                ]
            )
            for signal in filtered_signals[:12]:
                if isinstance(signal, dict):
                    sig_type_val = _display_text(signal.get("signal_type", ""))
                    sig_target = signal.get("stock_code", "") or signal.get("sector_name", "")
                    lines.append(
                        f"| {sig_type_val} | {sig_target} | {signal.get('score', 0):.1f} | {_display_text(signal.get('action', ''))} | {signal.get('reason', '')} | {_display_text(signal.get('risk_level', ''))} |"
                    )
                else:
                    sig_target = signal.stock_code if signal.stock_code else signal.sector_name
                    lines.append(
                        f"| {_display_text(signal.signal_type)} | {sig_target} | {signal.score:.1f} | {_display_text(signal.action)} | {signal.reason} | {_display_text(signal.risk_level)} |"
                    )
        else:
            lines.append("*当前无有效交易信号*")
    else:
        lines.append("*当前无交易信号*")
    lines.extend(["", "---", ""])
    return {"lines": lines, "exports": {}, "module_logs": []}


MARKET_ACTIVITY_ADVANCED_NODE_BUILDERS = {
    "lianban": build_lianban_node,
    "advanced_header": build_advanced_header_node,
    "volume_anomalies": build_volume_anomalies_node,
    "lhb_analysis": build_lhb_analysis_node,
    "resonance_scores": build_resonance_scores_node,
    "trade_signals": build_trade_signals_node,
}


def build_market_activity_advanced_section_result(context):
    context = context or {}
    node_specs = build_market_activity_advanced_node_specs(
        MARKET_ACTIVITY_ADVANCED_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_market_activity_nodes(node_specs, context)


def render_market_activity_advanced_sections(context):
    return build_market_activity_advanced_section_result(context)["lines"]
