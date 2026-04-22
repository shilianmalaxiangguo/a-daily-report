def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.board_tag_analysis_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_board_tag_analysis_sections_contract(data, *, analyze_sector_distribution):
    data = data or {}
    lines = []
    logs = []

    lines.append("## 十一、板块标签分析")
    lines.append("> **数据来源**: 同花顺热榜API（基于热度前30个股的板块标签统计）")
    lines.append("> **说明**: 热度前30个股详情见第四章，本章聚焦板块分布与资金偏好分析")
    lines.append("")
    lines.append("### 板块分布AI分析")
    lines.append("> **分析维度**: 热榜特征、热度分布、热榜偏好、资金偏好")
    lines.append("")

    tag_distribution = data.get("tag_distribution", {})
    status_distribution = data.get("status_distribution", {})
    high_lianban_stocks = data.get("high_lianban_stocks", [])

    if tag_distribution:
        analysis_text = analyze_sector_distribution(
            tag_distribution,
            status_distribution,
            high_lianban_stocks,
            top_n=15,
            market_stats=data.get("market_stats", {}),
        )
        lines.append(analysis_text)
    else:
        lines.append("**暂无板块分布数据**")
    lines.append("")
    lines.append("---")
    lines.append("")

    _append_log(
        logs,
        "render.board_tag_analysis",
        "success",
        "已生成板块标签分析章节",
        tag_count=len(tag_distribution),
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
