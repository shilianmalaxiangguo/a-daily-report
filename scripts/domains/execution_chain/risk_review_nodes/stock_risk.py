def build_risk_review_stock_risk_node(context, node_meta=None, node_lookup=None):
    stock_rows = context.get("stock_rows", []) or []
    lines = [
        "**逐只预判明日风险**（基于今日形态）:",
        "| 股票 | 代码 | 今日形态 | 异动灯号 | 明日风险预判 | 风险等级 | 去向 |",
        "|------|------|----------|----------|--------------|----------|------|",
    ]
    for row in stock_rows:
        lines.append(
            f"| {row.get('name', '-')} | {row.get('code', '-')} | {row.get('pattern', '未知')} | "
            f"{row.get('abnormal_light', '🟡 黄灯')} | {row.get('tomorrow_risk', '-')} | "
            f"{row.get('risk_level', '-')} | {row.get('dest', '-')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
