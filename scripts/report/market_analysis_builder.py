def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.market_analysis_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_market_and_sector_analysis_contract(
    data,
    market_analysis,
    sh_change,
    indices,
    exit_analysis,
    main_sectors_info,
    secondary_sectors_info,
    *,
    ai_group_concepts_into_chains,
):
    data = data or {}
    market_analysis = market_analysis or {}
    indices = indices or {}
    exit_analysis = exit_analysis or {}
    main_sectors_info = main_sectors_info or []
    secondary_sectors_info = secondary_sectors_info or []
    lines = []
    logs = []

    lines.append("## 八、市场与板块分析")
    lines.append("")
    lines.append("### 1. 市场整体状态")
    lines.append(f"- **现在是什么情况**: {market_analysis.get('market_status', '震荡整理')}")
    lines.append(
        f"- **主要指数**: 上证{sh_change:+.2f}%，深证{indices.get('深证成指', {}).get('涨跌幅', 0):+.2f}%，创业{indices.get('创业板指', {}).get('涨跌幅', 0):+.2f}%"
    )
    total_turnover = data.get("total_turnover", 0)
    lines.append(
        f"- **量能水平**: {total_turnover:.2f}亿元，{'量能充沛' if total_turnover > 18000 else '量能适中' if total_turnover > 12000 else '量能萎缩'}"
    )
    lines.append("")

    lines.append("### 2. 主线板块分析")
    mainline_name = exit_analysis.get("sector_name", "") if exit_analysis else ""
    if mainline_name and mainline_name != "暂无明确主线":
        lines.append(f"**当前主线**: {mainline_name}")
        lines.append("> 来源：统一执行链综合分析")
    elif main_sectors_info:
        lines.append("**主线板块**（涨停潮≥15只 + 出阳线）：")
        for idx, sector in enumerate(main_sectors_info[:3], 1):
            zt_count = sector.get("zt_count", 0)
            change = sector.get("change", 0)
            net_inflow = sector.get("net_inflow", 0)
            lines.append(f"{idx}. **{sector['name']}**: 涨停{zt_count}只，涨幅{change:+.2f}%，净流入{net_inflow:.1f}亿")
    else:
        lines.append("**暂无明确主线板块**（无涨停潮≥15只的板块）")
    lines.append("")

    lines.append("### 3. 次强板块分析")
    if secondary_sectors_info:
        lines.append("**次强板块**（涨停5-14只 + 出阳线）：")
        for idx, sector in enumerate(secondary_sectors_info[:5], 1):
            zt_count = sector.get("zt_count", 0)
            change = sector.get("change", 0)
            net_inflow = sector.get("net_inflow", 0)
            lines.append(f"{idx}. **{sector['name']}**: 涨停{zt_count}只，涨幅{change:+.2f}%，净流入{net_inflow:.1f}亿")
    else:
        lines.append("**暂无明确次强板块**（无涨停5-14只的板块）")
    lines.append("")

    lines.append("### 4. 风险板块分析")
    risk_sectors = market_analysis.get("risk_sectors", [])
    if risk_sectors:
        for idx, sector in enumerate(risk_sectors[:3], 1):
            risk_level = "🔴高风险" if sector["risk_level"] == "high" else "🟡中风险"
            change = sector["change"]
            change_label = "跌幅" if change < 0 else "涨幅"
            lines.append(f"{idx}. **{sector['name']}**: 净流出{sector['net_outflow']:.1f}亿，{change_label}{change:+.2f}% ({risk_level})")
    else:
        lines.append("**暂无明确风险板块**")
    lines.append("")

    lines.append("### 5. 市场关注度分析")
    hot_sectors = market_analysis.get("hot_sectors", [])
    if hot_sectors:
        all_concepts = [sector for sector, _ in hot_sectors]
        concept_chains = ai_group_concepts_into_chains(all_concepts)
        lines.append("**热榜关注产业链**（AI归纳，热度前30个股概念分布）：")
        for chain_name, concepts in concept_chains.items():
            total_count = sum(count for sector, count in hot_sectors if sector in concepts)
            if len(concepts) > 1:
                lines.append(f"- **{chain_name}**: {total_count}只股票 (包含: {', '.join(concepts)})")
            else:
                lines.append(f"- **{chain_name}**: {total_count}只股票")
    else:
        lines.append("**热榜数据暂无**")
    lines.append("")
    lines.append("")
    lines.append("---")
    lines.append("")

    _append_log(
        logs,
        "render.market_and_sector_analysis",
        "success",
        "已生成市场与板块分析章节",
        hot_sector_count=len(hot_sectors),
        risk_sector_count=len(risk_sectors),
        mainline_name=mainline_name,
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
