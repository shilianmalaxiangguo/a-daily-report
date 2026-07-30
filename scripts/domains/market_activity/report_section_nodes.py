from domains.market_activity.quote_lookup import build_market_quote_lookup, normalize_stock_code, resolve_change_pct, resolve_market_quote
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


def _first_available_float(row, keys, default=0.0):
    row = row or {}
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return _safe_float(value, default)
    return float(default)


def _optional_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_QUOTE_PRICE_KEY_GROUPS = (
    ("open", "开盘价", "开盘", "open_price"),
    ("high", "最高价", "最高", "high_price"),
    ("low", "最低价", "最低", "low_price"),
    ("close", "最新价", "收盘价", "收盘", "price", "当前价", "close_price"),
)
_QUOTE_CHANGE_KEYS = {"change_pct", "pct_chg", "pct_change", "涨跌幅", "zdf", "change_rate", "change"}


def _row_has_complete_positive_prices(row):
    if not isinstance(row, dict):
        return False
    for keys in _QUOTE_PRICE_KEY_GROUPS:
        values = [_optional_float(row.get(key)) for key in keys if key in row]
        if not any(value is not None and value > 0 for value in values):
            return False
    return True


def _first_row_float(rows, keys, *, positive_only=False):
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in keys:
            parsed = _optional_float(row.get(key))
            if parsed is None:
                continue
            if positive_only and parsed <= 0:
                continue
            if not positive_only and key in _QUOTE_CHANGE_KEYS and parsed == 0 and not _row_has_complete_positive_prices(row):
                continue
            return parsed
    return None


def _format_optional_pct(value):
    return "待补" if value is None else f"{value:+.2f}%"


def _format_optional_price(value):
    return "-" if value is None else f"{value:.2f}"


def _valid_quote_rows(rows):
    return [row for row in (rows or []) if isinstance(row, dict)]


def _resolve_stock_info(stock_full_info, stock_name, stock_code):
    normalized_code = normalize_stock_code(stock_code)
    if normalized_code:
        for code, info in (stock_full_info or {}).items():
            if normalize_stock_code(code) == normalized_code:
                return info or {}

    expected_name = str(stock_name or "").strip()
    if expected_name:
        for info in (stock_full_info or {}).values():
            if isinstance(info, dict) and str(info.get("name", "")).strip() == expected_name:
                return info or {}
    return {}


def _matching_rows(rows, stock_name, stock_code):
    return [row for row in (rows or []) if _stock_matches(row, stock_name, stock_code)]


def _limit_status_tag(status_text):
    text = str(status_text or "")
    if "跌停" in text:
        return "跌停"
    if "涨停" in text:
        return "涨停"
    return ""


def _has_explicit_limit_word(value):
    text = str(value or "").strip()
    if not text:
        return False
    negative_markers = (
        "未涨停",
        "非涨停",
        "不涨停",
        "没有涨停",
        "并非涨停",
        "未跌停",
        "非跌停",
        "不跌停",
        "没有跌停",
        "并非跌停",
    )
    if any(marker in text for marker in negative_markers):
        return False
    return "涨停" in text or "跌停" in text


def _limit_tag_from_change_pct(change_pct, stock_code=""):
    if change_pct is None:
        return ""
    code = normalize_stock_code(stock_code)
    if code.startswith(("3", "688")):
        return ""
    if change_pct >= 9.8:
        return "涨停"
    if change_pct <= -9.8:
        return "跌停"
    return ""


def _limit_tag_from_rows(rows):
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("涨停统计"):
            return str(row.get("涨停统计")).strip()
        if row.get("limit_status") or row.get("zt_status"):
            tag = _limit_status_tag(row.get("limit_status") or row.get("zt_status"))
            if tag:
                return tag
    return ""


def _broad_index_change_pct(data):
    values = []
    for key in ("wind_a_alternative", "csi1000_index"):
        payload = (data or {}).get(key) or {}
        if not isinstance(payload, dict):
            continue
        value = payload.get("涨跌幅", payload.get("change_pct"))
        if value not in (None, ""):
            values.append(_safe_float(value))
    return min(values) if values else 0.0


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
    quote_lookup = _build_quote_lookup(context)

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
            info = _resolve_stock_info(stock_full_info, name, code)
            quote_info = resolve_market_quote(quote_lookup, stock_code=code, stock_name=name)
            matched_turnover = _matching_rows(data.get("turnover_rank", []), name, code)
            matched_lianban = _matching_rows(_lianban_data(context), name, code)
            matched_zt = _matching_rows(zt_pool, name, code)
            matched_dt = _matching_rows(dt_pool, name, code)
            quote_rows = matched_dt + matched_zt + matched_lianban + matched_turnover + [quote_info, stock, info]
            change_pct = _first_row_float(quote_rows, ("change_pct", "pct_chg", "pct_change", "涨跌幅", "zdf", "change_rate", "change"))
            high = _first_row_float(quote_rows, ("high", "最高价", "最高"), positive_only=True)
            low = _first_row_float(quote_rows, ("low", "最低价", "最低"), positive_only=True)
            open_price = _first_row_float(quote_rows, ("open", "开盘价", "开盘"), positive_only=True)
            close = _first_row_float(quote_rows, ("close", "最新价", "收盘价", "收盘", "price", "当前价"), positive_only=True)
            status_text = ""
            if callable(get_stock_status):
                status_text = get_stock_status(name, code, zt_pool, dt_pool, change_pct)
            status_tag = _limit_status_tag(status_text)
            if not status_tag:
                if matched_dt:
                    status_tag = "跌停"
                elif matched_zt:
                    status_tag = "涨停"
            pool_tag = _limit_tag_from_rows(matched_dt + matched_zt + matched_lianban)
            popularity_tag = stock.get("popularity_tag") or ""
            if _has_explicit_limit_word(popularity_tag) and not (status_tag or pool_tag):
                popularity_tag = ""
            tag = status_tag or pool_tag or _limit_tag_from_change_pct(change_pct, code) or popularity_tag or "-"
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
            if None in (open_price, close, high, low, change_pct):
                pattern_name, pattern_score = "报价待补", 0
            else:
                pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct)
            lines.append(
                f"| {idx} | {name} | {code} | {rate_w:.1f}w | {sector} | {_format_optional_pct(change_pct)} | {_format_optional_price(high)} | {_format_optional_price(low)} | {_format_optional_price(open_price)} | {_format_optional_price(close)} | {tag} | {pattern_name}({pattern_score}分) |"
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
    quote_lookup = _build_quote_lookup(context)

    lines = [
        "| 排名 | 股票 | 代码 | 成交额 | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 隔日判断 | 蜡烛图形态 |",
        "|------|------|------|--------|----------|--------|--------|--------|--------|--------|----------|------------|",
    ]
    over_100b = _resolved_turnover_over_100b(context)
    if over_100b:
        for idx, stock in enumerate(over_100b[:30], 1):
            name = stock.get("name", "?")
            code = stock.get("code", "?").replace("sz", "").replace("sh", "")
            stock_turnover = stock.get("turnover", 0)
            info = _resolve_stock_info(stock_full_info, name, code)
            quote_info = resolve_market_quote(quote_lookup, stock_code=code, stock_name=name)
            matched_turnover = _matching_rows(data.get("turnover_rank", []), name, code)
            quote_rows = matched_turnover + [stock, quote_info, info]
            change_pct = _first_row_float(
                quote_rows,
                ("change_pct", "pct_chg", "pct_change", "涨跌幅", "zdf", "change_rate", "change"),
            )
            high = _first_row_float(quote_rows, ("high", "最高价", "最高"), positive_only=True)
            low = _first_row_float(quote_rows, ("low", "最低价", "最低"), positive_only=True)
            open_price = _first_row_float(quote_rows, ("open", "开盘价", "开盘"), positive_only=True)
            close = _first_row_float(
                quote_rows,
                ("close", "最新价", "收盘价", "收盘", "price", "当前价"),
                positive_only=True,
            )
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
            if None in (open_price, close, high, low, change_pct):
                pattern_name, pattern_score = "报价待补", 0
            else:
                pattern_name, pattern_score, _ = analyze_candlestick_pattern(
                    open_price,
                    close,
                    high,
                    low,
                    change_pct,
                )
            judgment = "观望" if stock_turnover > 150 else "关注" if stock_turnover > 120 else "谨慎"
            lines.append(
                f"| {idx} | {name} | {code} | {stock_turnover:.2f}亿 | {sector} | {_format_optional_pct(change_pct)} | {_format_optional_price(high)} | {_format_optional_price(low)} | {_format_optional_price(open_price)} | {_format_optional_price(close)} | {judgment} | {pattern_name}({pattern_score}分) |"
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
                "index_change_pct": _broad_index_change_pct(data),
                "up_ratio": _safe_float(data.get("market_stats", {}).get("up_count")) / max(_safe_float(data.get("market_stats", {}).get("total_count"), 1), 1) * 100,
                "top50_turnover_share_pct": _safe_float(data.get("top50_turnover_share_pct")),
            },
            sector_turnover_history=data.get("sector_turnover_history") or data.get("recent_sector_turnover_history") or []
        )
    except Exception as e:
        print(f"[警告] 板块资金流向增强模块加载失败: {e}")

    # 如果增强模块可用,使用增强的Markdown章节
    if enhanced_report and enhanced_report.get("markdown_sections"):
        lines = enhanced_report["markdown_sections"]
        exports = {
            "sector_internal_analysis": {
                "diffusion_quality": enhanced_report.get("diffusion_quality"),
                "turnover_trend": enhanced_report.get("turnover_trend"),
                "quant_environment": enhanced_report.get("quant_environment"),
            }
        }
        exports["sector_internal_analysis"] = {
            key: value for key, value in exports["sector_internal_analysis"].items() if value not in (None, "", [], {})
        }
        return {"lines": lines, "exports": exports if exports["sector_internal_analysis"] else {}, "module_logs": []}

    # 否则使用原始格式
    lines = [
        "### 资金流入TOP10",
        "| 排名 | 板块 | 净流入 | 涨跌幅 |",
        "|------|------|--------|--------|",
    ]
    sector_fund_flow = data.get("sector_fund_flow") or {}
    if sector_fund_flow.get("inflow"):
        for idx, sector in enumerate(sector_fund_flow["inflow"][:10], 1):
            net_flow = _first_available_float(sector, ("zljlr", "net_amount", "net_inflow_yi", "net_inflow"))
            change_pct = _first_available_float(sector, ("zdf", "change_pct", "pct_change"))
            sector_name = sector.get("name") or sector.get("sector") or sector.get("sector_name") or sector.get("industry") or "?"
            lines.append(f"| {idx} | {sector_name} | {net_flow:+.2f}亿 | {change_pct:+.2f}% |")
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
            net_flow = _first_available_float(sector, ("zljlr", "net_amount", "net_inflow_yi", "net_inflow"))
            change_pct = _first_available_float(sector, ("zdf", "change_pct", "pct_change"))
            sector_name = sector.get("name") or sector.get("sector") or sector.get("sector_name") or sector.get("industry") or "?"
            lines.append(f"| {idx} | {sector_name} | {abs(net_flow):.2f}亿 | {change_pct:+.2f}% |")
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
    quote_lookup = _build_quote_lookup(context)

    lines = [
        f"| 排名 | 股票 | 代码 | {amount_title} | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 涨停状态 | 蜡烛图形态 |",
        "|------|------|------|-----------|----------|--------|--------|--------|--------|--------|----------|------------|",
    ]
    for item in items[:10]:
        code = item.get("code", "?")
        info = _resolve_stock_info(stock_full_info, item.get("name"), code)
        name = item.get("name") or info.get("name", "?")
        quote_info = resolve_market_quote(quote_lookup, stock_code=code, stock_name=name)
        matched_zt = _matching_rows(zt_pool, name, code)
        matched_dt = _matching_rows(dt_pool, name, code)
        quote_rows = _valid_quote_rows(matched_dt + matched_zt + [quote_info, item, info])
        change_pct = _first_row_float(quote_rows, ("change_pct", "pct_chg", "pct_change", "涨跌幅", "zdf", "change_rate", "change"))
        high = _first_row_float(quote_rows, ("high", "最高价", "最高", "high_price"), positive_only=True)
        low = _first_row_float(quote_rows, ("low", "最低价", "最低", "low_price"), positive_only=True)
        open_price = _first_row_float(quote_rows, ("open", "开盘价", "开盘", "open_price"), positive_only=True)
        close = _first_row_float(quote_rows, ("close", "最新价", "收盘价", "收盘", "price", "当前价", "close_price"), positive_only=True)
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
        if matched_dt:
            status = "跌停"
        elif matched_zt:
            status = "涨停"
        else:
            status = item.get("zt_status", "正常")
        if None in (open_price, close, high, low, change_pct):
            pattern_name, pattern_score = "报价待补", 0
        elif callable(analyze_candlestick_pattern):
            pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct)
        else:
            pattern_name, pattern_score = "未知", 0
        lines.append(
            f"| {item.get('rank', 0)} | {name} | {code} | {amount_formatter(item.get('net_buy_amount_yi', 0))}亿 | {sector} | {_format_optional_pct(change_pct)} | {_format_optional_price(high)} | {_format_optional_price(low)} | {_format_optional_price(open_price)} | {_format_optional_price(close)} | {status} | {pattern_name}({pattern_score}分) |"
        )
    lines.append("")
    return lines


def _compact_lhb_date(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _lhb_row_code(row):
    if not isinstance(row, dict):
        return ""
    return normalize_stock_code(
        row.get("code")
        or row.get("代码")
        or row.get("stock_code")
        or row.get("ts_code")
        or row.get("fs_code")
    )


def _lhb_row_name(row):
    if not isinstance(row, dict):
        return ""
    return _display_text(row.get("name") or row.get("名称") or row.get("stock_name") or row.get("stock_chi_name"))


def _lhb_amount_yi(row, yi_key, raw_key):
    value = _optional_float(row.get(yi_key))
    if value is not None:
        return value
    raw = _optional_float(row.get(raw_key))
    if raw is None:
        return 0.0
    return raw / 1e8 if abs(raw) > 10000 else raw


def _collect_lhb_reasons(row):
    reasons = row.get("reasons") if isinstance(row, dict) else None
    if isinstance(reasons, list):
        return [_display_text(item) for item in reasons if _display_text(item)]
    reason = _display_text((row or {}).get("reason") or (row or {}).get("上榜原因"))
    return [reason] if reason else []


def _build_lhb_stock_context(data, stock_full_info):
    context_by_code = {}

    def ensure(code):
        return context_by_code.setdefault(
            code,
            {
                "name": "",
                "reasons": [],
                "reason_count": 0,
                "list_net_yi": 0.0,
            },
        )

    for code, info in (stock_full_info or {}).items():
        normalized_code = normalize_stock_code(code)
        if not normalized_code:
            continue
        bucket = ensure(normalized_code)
        bucket["name"] = bucket["name"] or _lhb_row_name(info)

    for row in (data.get("lhb_net_buy_top10", []) or []) + (data.get("lhb_net_sell_top10", []) or []):
        code = _lhb_row_code(row)
        if not code:
            continue
        bucket = ensure(code)
        bucket["name"] = bucket["name"] or _lhb_row_name(row)
        if "net_buy_amount_yi" in row:
            bucket["list_net_yi"] += _safe_float(row.get("net_buy_amount_yi"))

    occurrences = {}
    for row in data.get("lhb_analysis", []) or []:
        code = _lhb_row_code(row)
        if not code:
            continue
        bucket = ensure(code)
        bucket["name"] = bucket["name"] or _lhb_row_name(row)
        occurrences[code] = occurrences.get(code, 0) + 1
        for reason in _collect_lhb_reasons(row):
            if reason not in bucket["reasons"]:
                bucket["reasons"].append(reason)
        if "net_buy_amount_yi" in row:
            bucket["list_net_yi"] = _safe_float(row.get("net_buy_amount_yi"))
        elif "net_buy_amount" in row:
            bucket["list_net_yi"] = _safe_float(row.get("net_buy_amount")) / 1e8
        elif "net_amount" in row:
            bucket["list_net_yi"] = _safe_float(row.get("net_amount")) / 1e8
        elif "net_buy" in row:
            bucket["list_net_yi"] = _safe_float(row.get("net_buy"))

    for code, bucket in context_by_code.items():
        bucket["reason_count"] = max(len(bucket.get("reasons") or []), occurrences.get(code, 0))
        if not bucket["name"]:
            bucket["name"] = code
    return context_by_code


def _normalize_lhb_seat_rows(rows, target_date):
    target_compact = _compact_lhb_date(target_date)
    normalized = []
    seen = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        trade_date = _compact_lhb_date(
            row.get("trade_date") or row.get("date") or row.get("source_date") or row.get("query_date")
        )
        if target_compact and trade_date and trade_date != target_compact:
            continue
        code = _lhb_row_code(row)
        exalter = _display_text(row.get("exalter") or row.get("seat") or row.get("seat_name"))
        if not code or not exalter:
            continue
        net_buy_yi = round(_lhb_amount_yi(row, "net_buy_yi", "net_buy"), 6)
        buy_yi = round(_lhb_amount_yi(row, "buy_yi", "buy"), 6)
        sell_yi = round(_lhb_amount_yi(row, "sell_yi", "sell"), 6)
        reason = _display_text(row.get("reason") or row.get("上榜原因"))
        dedupe_key = (code, exalter, buy_yi, sell_yi, net_buy_yi, reason)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "code": code,
                "exalter": exalter,
                "seat_type": "机构" if _display_text(row.get("seat_type")) == "机构" or "机构" in exalter else "非机构",
                "buy_yi": buy_yi,
                "sell_yi": sell_yi,
                "net_buy_yi": net_buy_yi,
                "reason": reason,
            }
        )
    return normalized


def _build_lhb_seat_summary(seat_rows):
    summary_by_code = {}
    for row in seat_rows:
        code = row["code"]
        bucket = summary_by_code.setdefault(
            code,
            {
                "institution_net_yi": 0.0,
                "institution_count": 0,
                "non_institution_net_yi": 0.0,
                "non_institution_count": 0,
                "stock_connect_net_yi": 0.0,
                "stock_connect_count": 0,
                "total_net_yi": 0.0,
                "institution_seats": [],
                "non_institution_seats": [],
                "stock_connect_seats": [],
            },
        )
        net_buy_yi = _safe_float(row.get("net_buy_yi"))
        bucket["total_net_yi"] += net_buy_yi
        if row.get("seat_type") == "机构":
            bucket["institution_net_yi"] += net_buy_yi
            bucket["institution_count"] += 1
            bucket["institution_seats"].append(row)
        else:
            bucket["non_institution_net_yi"] += net_buy_yi
            bucket["non_institution_count"] += 1
            bucket["non_institution_seats"].append(row)
        if "沪股通" in row.get("exalter", "") or "深股通" in row.get("exalter", ""):
            bucket["stock_connect_net_yi"] += net_buy_yi
            bucket["stock_connect_count"] += 1
            bucket["stock_connect_seats"].append(row)
    for bucket in summary_by_code.values():
        for key in ("institution_net_yi", "non_institution_net_yi", "stock_connect_net_yi", "total_net_yi"):
            bucket[key] = round(bucket[key], 6)
    return summary_by_code


def _top_lhb_seat_name(seats, *, by_abs=False):
    if not seats:
        return "-"
    key = (lambda item: abs(_safe_float(item.get("net_buy_yi")))) if by_abs else (lambda item: _safe_float(item.get("net_buy_yi")))
    return sorted(seats, key=key, reverse=True)[0].get("exalter") or "-"


def _format_lhb_signed_yi(value):
    return f"{_safe_float(value):+.2f}"


def _format_lhb_reason(reasons):
    reasons = [reason for reason in reasons or [] if reason]
    if not reasons:
        return "-"
    if len(reasons) <= 2:
        return "；".join(reasons)
    return "；".join(reasons[:2]) + f"等{len(reasons)}项"


def _lhb_divergence_read(institution_net_yi, non_institution_net_yi):
    institution_net_yi = _safe_float(institution_net_yi)
    non_institution_net_yi = _safe_float(non_institution_net_yi)
    if institution_net_yi > 0 and non_institution_net_yi < 0:
        return "机构买、非机构卖"
    if institution_net_yi < 0 and non_institution_net_yi > 0:
        return "机构卖、非机构买"
    if institution_net_yi > 0 and non_institution_net_yi > 0:
        return "机构与非机构同向净买"
    if institution_net_yi < 0 and non_institution_net_yi < 0:
        return "机构与非机构同向净卖"
    if institution_net_yi:
        return "主要由机构表态"
    if non_institution_net_yi:
        return "主要由非机构表态"
    return "席位表态不明显"


def _lhb_display_name(code, stock_context):
    return (stock_context.get(code) or {}).get("name") or code


def _render_lhb_empty_row(columns, text):
    return "| " + " | ".join(["-"] * (columns - 1) + [text]) + " |"


def build_lhb_seat_strength_node(context, node_meta=None, node_lookup=None):
    data = _data(context)
    stock_context = _build_lhb_stock_context(data, _stock_full_info(context))
    seat_rows = _normalize_lhb_seat_rows(data.get("lhb_inst_detail", []) or [], context.get("target_date"))
    lines = [
        "### 席位强度解读",
        "> 席位只反映资金表态，不直接生成明日参与动作。",
        "",
    ]
    if not seat_rows:
        lines.extend(["| 结果 | 说明 |", "|------|------|", "| 席位明细缺失 | 只保留龙虎榜净买卖排行 |", ""])
        return {"lines": lines, "exports": {}, "module_logs": []}

    summary_by_code = _build_lhb_seat_summary(seat_rows)

    institution_rows = [
        (code, summary)
        for code, summary in summary_by_code.items()
        if _safe_float(summary.get("institution_net_yi")) > 0
    ]
    institution_rows = sorted(institution_rows, key=lambda item: item[1].get("institution_net_yi", 0), reverse=True)[:5]
    lines.extend(
        [
            "#### 机构净买强榜",
            "| 股票 | 代码 | 机构净买(亿) | 机构席位数 | 买方代表 | 上榜原因 |",
            "|------|------|--------------|------------|----------|----------|",
        ]
    )
    if institution_rows:
        for code, summary in institution_rows:
            stock_meta = stock_context.get(code, {})
            lines.append(
                f"| {_lhb_display_name(code, stock_context)} | {code} | {_format_lhb_signed_yi(summary.get('institution_net_yi'))} | "
                f"{summary.get('institution_count', 0)} | {_top_lhb_seat_name(summary.get('institution_seats', []))} | "
                f"{_format_lhb_reason(stock_meta.get('reasons'))} |"
            )
    else:
        lines.append(_render_lhb_empty_row(6, "当前无机构净买强样本"))
    lines.append("")

    non_institution_rows = [
        (code, summary)
        for code, summary in summary_by_code.items()
        if _safe_float(summary.get("non_institution_net_yi")) > 0
    ]
    non_institution_rows = sorted(
        non_institution_rows,
        key=lambda item: item[1].get("non_institution_net_yi", 0),
        reverse=True,
    )[:5]
    lines.extend(
        [
            "#### 非机构强榜",
            "| 股票 | 代码 | 非机构净买(亿) | 非机构席位数 | 买方代表 | 上榜原因 |",
            "|------|------|----------------|--------------|----------|----------|",
        ]
    )
    if non_institution_rows:
        for code, summary in non_institution_rows:
            stock_meta = stock_context.get(code, {})
            lines.append(
                f"| {_lhb_display_name(code, stock_context)} | {code} | {_format_lhb_signed_yi(summary.get('non_institution_net_yi'))} | "
                f"{summary.get('non_institution_count', 0)} | {_top_lhb_seat_name(summary.get('non_institution_seats', []))} | "
                f"{_format_lhb_reason(stock_meta.get('reasons'))} |"
            )
    else:
        lines.append(_render_lhb_empty_row(6, "当前无非机构净买强样本"))
    lines.append("")

    stock_connect_rows = [
        (code, summary)
        for code, summary in summary_by_code.items()
        if summary.get("stock_connect_count", 0) > 0
    ]
    stock_connect_rows = sorted(
        stock_connect_rows,
        key=lambda item: abs(_safe_float(item[1].get("stock_connect_net_yi"))),
        reverse=True,
    )[:5]
    lines.extend(
        [
            "#### 股通席位",
            "| 股票 | 代码 | 股通净额(亿) | 方向 | 代表席位 | 上榜原因 |",
            "|------|------|--------------|------|----------|----------|",
        ]
    )
    if stock_connect_rows:
        for code, summary in stock_connect_rows:
            stock_meta = stock_context.get(code, {})
            stock_connect_net = _safe_float(summary.get("stock_connect_net_yi"))
            direction = "净买" if stock_connect_net >= 0 else "净卖"
            lines.append(
                f"| {_lhb_display_name(code, stock_context)} | {code} | {_format_lhb_signed_yi(stock_connect_net)} | {direction} | "
                f"{_top_lhb_seat_name(summary.get('stock_connect_seats', []), by_abs=True)} | {_format_lhb_reason(stock_meta.get('reasons'))} |"
            )
    else:
        lines.append(_render_lhb_empty_row(6, "当前无股通席位样本"))
    lines.append("")

    repeated_rows = []
    for code, stock_meta in stock_context.items():
        reason_count = stock_meta.get("reason_count", 0)
        if reason_count < 2:
            continue
        summary = summary_by_code.get(code, {})
        repeated_rows.append((code, stock_meta, summary))
    repeated_rows = sorted(
        repeated_rows,
        key=lambda item: abs(_safe_float(item[2].get("total_net_yi", item[1].get("list_net_yi", 0)))),
        reverse=True,
    )[:5]
    lines.extend(
        [
            "#### 重复上榜分歧榜",
            "| 股票 | 代码 | 上榜原因数 | 榜单净额(亿) | 机构净额(亿) | 非机构净额(亿) | 分歧读法 |",
            "|------|------|------------|--------------|--------------|----------------|----------|",
        ]
    )
    if repeated_rows:
        for code, stock_meta, summary in repeated_rows:
            institution_net = _safe_float(summary.get("institution_net_yi"))
            non_institution_net = _safe_float(summary.get("non_institution_net_yi"))
            lines.append(
                f"| {_lhb_display_name(code, stock_context)} | {code} | {stock_meta.get('reason_count', 0)} | "
                f"{_format_lhb_signed_yi(stock_meta.get('list_net_yi'))} | {_format_lhb_signed_yi(institution_net)} | "
                f"{_format_lhb_signed_yi(non_institution_net)} | {_lhb_divergence_read(institution_net, non_institution_net)} |"
            )
    else:
        lines.append(_render_lhb_empty_row(7, "当前无重复上榜分歧样本"))
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


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
    "lhb_seat_strength": build_lhb_seat_strength_node,
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
            display_stocks = list(stocks[:5])
            displayed_codes = {str(stock.get("code") or "") for stock in display_stocks}
            for stock in stocks[5:]:
                code = str(stock.get("code") or "")
                if stock.get("trade_narrative_sector") and code not in displayed_codes:
                    display_stocks.append(stock)
                    displayed_codes.add(code)
            for stock in display_stocks:
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
                sector = stock.get("trade_narrative_sector") or get_stock_sector(
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
