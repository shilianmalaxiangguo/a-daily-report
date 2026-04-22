def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.market_activity.report_sections",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_market_activity_report_sections(
    data,
    target_date,
    stock_full_info,
    *,
    get_stock_status,
    get_stock_sector,
    analyze_candlestick_pattern,
):
    data = data or {}
    stock_full_info = stock_full_info or {}
    lines = []
    logs = []

    zt_pool = data.get("zt_pool", [])
    dt_pool = data.get("dt_pool", [])

    lines.append("## 四、热度前三十个股")
    lines.append("> **数据来源**: 同花顺个股热榜")
    lines.append("")
    lines.append("| 排名 | 股票 | 代码 | 热度分(w) | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 连板标签 | 蜡烛图形态 |")
    lines.append("|------|------|------|-----------|----------|--------|--------|--------|--------|--------|----------|------------|")
    if data.get("hot_rank_top30"):
        for idx, stock in enumerate(data["hot_rank_top30"][:30], 1):
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
            get_stock_status(name, code, zt_pool, dt_pool, change_pct)
            sector = get_stock_sector(
                name,
                code,
                hot_rank_data=data.get("hot_rank_top30", []),
                zt_pool_data=data.get("zt_pool_by_sector", {}),
                zt_pool_raw=zt_pool,
                dt_pool_raw=dt_pool,
                lianban_data=data.get("lianban_data", []),
                lhb_data=data.get("lhb_net_buy_top10", []) + data.get("lhb_net_sell_top10", []),
            )
            pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct)
            lines.append(
                f"| {idx} | {name} | {code} | {rate_w:.1f}w | {sector} | {change_pct:+.2f}% | {high:.2f} | {low:.2f} | {open_price:.2f} | {close:.2f} | {tag} | {pattern_name}({pattern_score}分) |"
            )
    lines.append("")

    lines.append("## 五、成交额排名前十且>100亿个股")
    lines.append("**筛选标准**: 成交额>100亿的个股")
    lines.append("")
    lines.append("| 排名 | 股票 | 代码 | 成交额 | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 隔日判断 | 蜡烛图形态 |")
    lines.append("|------|------|------|--------|----------|--------|--------|--------|--------|--------|----------|------------|")
    over_100b = data.get("turnover_over_100b", []) or [stock for stock in data.get("turnover_rank", []) if stock.get("turnover", 0) > 100]
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
            get_stock_status(name, code, zt_pool, dt_pool, change_pct)
            sector = get_stock_sector(
                name,
                code,
                hot_rank_data=data.get("hot_rank_top30", []),
                zt_pool_data=data.get("zt_pool_by_sector", {}),
                zt_pool_raw=zt_pool,
                dt_pool_raw=dt_pool,
                lianban_data=data.get("lianban_data", []),
                lhb_data=data.get("lhb_net_buy_top10", []) + data.get("lhb_net_sell_top10", []),
                sector_fund_flow=data.get("sector_fund_flow", {}),
            )
            pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct)
            judgment = "观望" if stock_turnover > 150 else "关注" if stock_turnover > 120 else "谨慎"
            lines.append(
                f"| {idx} | {name} | {code} | {stock_turnover:.2f}亿 | {sector} | {change_pct:+.2f}% | {high:.2f} | {low:.2f} | {open_price:.2f} | {close:.2f} | {judgment} | {pattern_name}({pattern_score}分) |"
            )
    lines.append("")

    lines.append("## 六、行业资金净流向")
    if data.get("sector_fund_flow", {}).get("is_historical", False):
        lines.append("> **⚠️ 历史日期提示**：板块资金流向数据仅支持当日实时获取，历史数据暂不可用。")
        lines.append("> 如需查看历史资金流向，请参考当日报告或相关金融数据平台。")
        lines.append("")
    lines.append("### 净流入前十")
    lines.append("| 排名 | 板块 | 净流入 | 涨跌幅 |")
    lines.append("|------|------|--------|--------|")
    if data.get("sector_fund_flow") and data["sector_fund_flow"].get("inflow"):
        for idx, sector in enumerate(data["sector_fund_flow"]["inflow"][:10], 1):
            lines.append(f"| {idx} | {sector.get('name', '?')} | {sector.get('zljlr', 0):+.2f}亿 | {sector.get('zdf', 0):+.2f}% |")
    lines.append("")
    lines.append("### 净流出前十")
    lines.append("| 排名 | 板块 | 净流出 | 涨跌幅 |")
    lines.append("|------|------|--------|--------|")
    if data.get("sector_fund_flow") and data["sector_fund_flow"].get("outflow"):
        for idx, sector in enumerate(data["sector_fund_flow"]["outflow"][:10], 1):
            lines.append(f"| {idx} | {sector.get('name', '?')} | {abs(sector.get('zljlr', 0)):.2f}亿 | {sector.get('zdf', 0):+.2f}% |")
    lines.append("")

    lines.append("## 七、龙虎榜数据")
    lines.append("### 净买入前十")
    lines.append("| 排名 | 股票 | 代码 | 净买入(亿) | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 涨停状态 | 蜡烛图形态 |")
    lines.append("|------|------|------|-----------|----------|--------|--------|--------|--------|--------|----------|------------|")
    if data.get("lhb_net_buy_top10"):
        for item in data["lhb_net_buy_top10"][:10]:
            code = item.get("code", "?")
            info = stock_full_info.get(code, {})
            name = item.get("name") or info.get("name", "?")
            change_pct = info.get("change_pct", item.get("change_pct", 0))
            high = info.get("high", 0)
            low = info.get("low", 0)
            open_price = info.get("open", 0)
            close = info.get("close", 0)
            sector = item.get("sector", "")
            if not sector or sector == "未知":
                sector = get_stock_sector(
                    name,
                    code,
                    hot_rank_data=data.get("hot_rank_top30", []),
                    zt_pool_data=data.get("zt_pool_by_sector", {}),
                    zt_pool_raw=zt_pool,
                    dt_pool_raw=dt_pool,
                    lianban_data=data.get("lianban_data", []),
                    lhb_data=data.get("lhb_net_buy_top10", []) + data.get("lhb_net_sell_top10", []),
                    skip_api_call=False,
                )
            pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct)
            lines.append(
                f"| {item.get('rank', 0)} | {name} | {code} | {item.get('net_buy_amount_yi', 0):.2f}亿 | {sector} | {change_pct:+.2f}% | {high:.2f} | {low:.2f} | {open_price:.2f} | {close:.2f} | {item.get('zt_status', '正常')} | {pattern_name}({pattern_score}分) |"
            )
    lines.append("")
    lines.append("### 净流出前十")
    lines.append("| 排名 | 股票 | 代码 | 净流出(亿) | 所属板块 | 涨跌幅 | 最高价 | 最低价 | 开盘价 | 收盘价 | 涨停状态 | 蜡烛图形态 |")
    lines.append("|------|------|------|-----------|----------|--------|--------|--------|--------|--------|----------|------------|")
    if data.get("lhb_net_sell_top10"):
        for item in data["lhb_net_sell_top10"][:10]:
            code = item.get("code", "?")
            info = stock_full_info.get(code, {})
            name = item.get("name") or info.get("name", "?")
            change_pct = info.get("change_pct", item.get("change_pct", 0))
            high = info.get("high", 0)
            low = info.get("low", 0)
            open_price = info.get("open", 0)
            close = info.get("close", 0)
            sector = item.get("sector", "")
            if not sector or sector == "未知":
                sector = get_stock_sector(
                    name,
                    code,
                    hot_rank_data=data.get("hot_rank_top30", []),
                    zt_pool_data=data.get("zt_pool_by_sector", {}),
                    zt_pool_raw=zt_pool,
                    dt_pool_raw=dt_pool,
                    lianban_data=data.get("lianban_data", []),
                    lhb_data=data.get("lhb_net_buy_top10", []) + data.get("lhb_net_sell_top10", []),
                    skip_api_call=False,
                )
            pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct)
            lines.append(
                f"| {item.get('rank', 0)} | {name} | {code} | {abs(item.get('net_buy_amount_yi', 0)):.2f}亿 | {sector} | {change_pct:+.2f}% | {high:.2f} | {low:.2f} | {open_price:.2f} | {close:.2f} | {item.get('zt_status', '正常')} | {pattern_name}({pattern_score}分) |"
            )
    lines.append("")

    _append_log(
        logs,
        "render.market_activity_sections",
        "success",
        "已生成 market_activity 业务域的基础活跃度章节",
        hot_rank_count=len(data.get("hot_rank_top30", []) or []),
        turnover_count=len(over_100b or []),
        lhb_buy_count=len(data.get("lhb_net_buy_top10", []) or []),
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }


def build_advanced_activity_report_sections(
    data,
    stock_full_info,
    *,
    get_stock_sector,
    analyze_candlestick_pattern,
):
    data = data or {}
    stock_full_info = stock_full_info or {}
    lines = []
    logs = []

    lines.append("## 九、连板梯队")
    lines.append("> **数据来源**: akshare涨停池数据（支持历史日期）")
    lines.append("")
    if data.get("lianban_data"):
        lianban_groups = {}
        for stock in data["lianban_data"]:
            lianban_days = stock.get("lianban_days", 0)
            lianban_groups.setdefault(lianban_days, []).append(stock)
        for days in sorted(lianban_groups.keys(), reverse=True):
            stocks = lianban_groups[days]
            if days >= 3:
                lines.append(f"### 【{days}连板】({len(stocks)}只)")
            elif days == 2:
                lines.append(f"### 【2连板】({len(stocks)}只)")
            else:
                lines.append(f"### 【首板/1连板】({len(stocks)}只)")
            lines.append("| 股票 | 代码 | 所属板块 | 涨跌幅 | 首次涨停 | 最高价 | 最低价 | 开盘价 | 收盘价 | 涨停原因 | 蜡烛图形态 |")
            lines.append("|------|------|----------|--------|----------|--------|--------|--------|--------|----------|------------|")
            for stock in stocks[:5]:
                name = stock.get("name", "?")
                code = stock.get("code", "?").replace(".SZ", "").replace(".SS", "")
                info = stock_full_info.get(code, {})
                change_pct = info.get("change_pct", stock.get("change_pct", 0))
                high = info.get("high", 0)
                low = info.get("low", 0)
                open_price = info.get("open", 0)
                close = info.get("close", stock.get("price", 0))
                first_limit_time = stock.get("first_limit_time", "-")
                reason = stock.get("reason", "-")
                if len(reason) > 30:
                    reason = reason[:30] + "..."
                sector = get_stock_sector(
                    name,
                    code,
                    hot_rank_data=data.get("hot_rank_top30", []),
                    zt_pool_data=data.get("zt_pool_by_sector", {}),
                    zt_pool_raw=data.get("zt_pool", []),
                    dt_pool_raw=data.get("dt_pool", []),
                    lianban_data=data.get("lianban_data", []),
                    lhb_data=data.get("lhb_net_buy_top10", []) + data.get("lhb_net_sell_top10", []),
                )
                pattern_name, pattern_score, _ = analyze_candlestick_pattern(open_price, close, high, low, change_pct, first_limit_time)
                lines.append(
                    f"| {name} | {code} | {sector} | {change_pct:+.2f}% | {first_limit_time} | {high:.2f} | {low:.2f} | {open_price:.2f} | {close:.2f} | {reason} | {pattern_name}({pattern_score}分) |"
                )
            lines.append("")
    else:
        lines.append("**暂无连板梯队数据**")
        lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 十、AI多维量化分析")
    lines.append("> **核心升级**: 告别简单加减，采用历史分位数、资金性质识别、多维度共振模型")
    lines.append("")
    lines.append("### 1. 放量异常检测")
    lines.append("| 股票 | 异常类型 | 强度 | 成交量分位 | 涨跌幅 | 信号说明 |")
    lines.append("|------|----------|------|------------|--------|----------|")
    volume_anomalies = data.get("volume_anomalies", [])
    if volume_anomalies:
        for anomaly in volume_anomalies[:10]:
            if isinstance(anomaly, dict):
                a_name = anomaly.get("stock_name", anomaly.get("name", ""))
                a_type_val = str(anomaly.get("anomaly_type", anomaly.get("type", "")))
                a_strength = anomaly.get("strength", "")
                a_pct = anomaly.get("volume_percentile", 0)
                a_chg = anomaly.get("price_change", 0)
                a_reason = anomaly.get("reason", "")
            else:
                a_name = anomaly.stock_name
                a_type_val = anomaly.anomaly_type.value
                a_strength = anomaly.strength
                a_pct = anomaly.volume_percentile
                a_chg = anomaly.price_change
                a_reason = anomaly.reason
            lines.append(f"| {a_name} | {a_type_val} | {a_strength} | {a_pct:.0f}% | {a_chg:+.2f}% | {a_reason} |")
    else:
        lines.append("| - | - | - | - | - | 暂无显著放量异常 |")
    lines.append("")

    lines.append("### 2. 龙虎榜深度分析")
    lines.append("| 股票 | 净买入(亿) | 资金性质 | 行为模式 | 近3日上榜 | 信号强度 |")
    lines.append("|------|-----------|----------|----------|-----------|----------|")
    lhb_analysis = data.get("lhb_analysis", [])
    if lhb_analysis:
        for item in lhb_analysis[:10]:
            if isinstance(item, dict):
                lines.append(
                    f"| {item.get('stock_name', '')} | {item.get('net_buy', 0):+.2f} | {item.get('money_type', '')} | {item.get('pattern', '')} | {item.get('recent_appearances', 0)}次 | {item.get('signal_strength', '')} |"
                )
            else:
                lines.append(
                    f"| {item.stock_name} | {item.net_buy:+.2f} | {item.money_type.value} | {item.pattern} | {item.recent_appearances}次 | {item.signal_strength} |"
                )
    else:
        lines.append("| - | - | - | - | - | 暂无龙虎榜数据 |")
    lines.append("")

    lines.append("### 2. 板块共振评分（多维加权模型）")
    resonance_scores = data.get("resonance_scores", {})
    if resonance_scores:
        def _get_total_score(score_data):
            return score_data.get("total_score", 0) if isinstance(score_data, dict) else getattr(score_data, "total_score", 0)

        def _get_resonance_level(score_data):
            if isinstance(score_data, dict):
                return str(score_data.get("resonance_level", ""))
            return score_data.resonance_level.value

        filtered_scores = {k: v for k, v in resonance_scores.items() if _get_total_score(v) >= 5 and _get_resonance_level(v) != "无共振"}
        if filtered_scores:
            lines.append("| 板块 | 综合得分 | 共振级别 | 强势维度 | 资金流向 | 涨停强度 | 龙虎榜 |")
            lines.append("|------|----------|----------|----------|----------|----------|--------|")
            for sector_name, score_data in sorted(filtered_scores.items(), key=lambda item: _get_total_score(item[1]), reverse=True)[:15]:
                if isinstance(score_data, dict):
                    sd_total = score_data.get("total_score", 0)
                    sd_strength_dims = score_data.get("strength_dimensions", [])
                    sd_dim_scores = score_data.get("dimension_scores", {})
                    sd_res_level_val = str(score_data.get("resonance_level", ""))
                else:
                    sd_total = score_data.total_score
                    sd_strength_dims = score_data.strength_dimensions
                    sd_dim_scores = score_data.dimension_scores
                    sd_res_level_val = score_data.resonance_level.value
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
            lines.append("*暂无有效共振板块（所有板块得分均为0）*")
    else:
        lines.append("*暂无共振评分数据*")
    lines.append("")

    lines.append("### 3. AI量化交易信号")
    trade_signals = data.get("trade_signals", [])
    if trade_signals:
        def _get_signal_score(sig):
            return sig.get("score", 0) if isinstance(sig, dict) else getattr(sig, "score", 0)

        filtered_signals = [sig for sig in trade_signals if _get_signal_score(sig) > 5]
        if filtered_signals:
            lines.append("| 信号类型 | 板块/个股 | 得分 | 操作建议 | 逻辑说明 | 风险等级 |")
            lines.append("|----------|-----------|------|----------|----------|----------|")
            for signal in filtered_signals[:12]:
                if isinstance(signal, dict):
                    sig_type_val = str(signal.get("signal_type", ""))
                    sig_target = signal.get("stock_code", "") or signal.get("sector_name", "")
                    lines.append(
                        f"| {sig_type_val} | {sig_target} | {signal.get('score', 0):.1f} | {signal.get('action', '')} | {signal.get('reason', '')} | {signal.get('risk_level', '')} |"
                    )
                else:
                    sig_target = signal.stock_code if signal.stock_code else signal.sector_name
                    lines.append(
                        f"| {signal.signal_type.value} | {sig_target} | {signal.score:.1f} | {signal.action} | {signal.reason} | {signal.risk_level} |"
                    )
        else:
            lines.append("*暂无有效交易信号（所有信号得分均≤15）*")
    else:
        lines.append("*暂无交易信号*")
    lines.append("")
    lines.append("---")
    lines.append("")

    _append_log(
        logs,
        "render.advanced_activity_sections",
        "success",
        "已生成 market_activity 业务域的高阶活跃度章节",
        lianban_count=len(data.get("lianban_data", []) or []),
        anomaly_count=len(volume_anomalies or []),
        signal_count=len(data.get("trade_signals", []) or []),
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
