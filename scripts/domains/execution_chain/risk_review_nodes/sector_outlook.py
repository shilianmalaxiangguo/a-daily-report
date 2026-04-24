def build_risk_review_sector_outlook_node(context, node_meta=None, node_lookup=None):
    delete_group = context.get("delete_group", []) or []
    abnormal_green_count = int(context.get("abnormal_green_count", 0) or 0)
    abnormal_red_count = int(context.get("abnormal_red_count", 0) or 0)

    lines = ["**板块级明日风险预判**:"]
    if len(delete_group) >= 3:
        lines.append(f"- ⚠️ 明天先回避组达{len(delete_group)}只，说明今日涨停质量差，明日整体风险偏高")
    else:
        lines.append(f"- ✅ 明天先回避组{len(delete_group)}只，在正常范围内，明日风险可控")
    lines.append(f"- **异动承接强不强**: 绿灯{abnormal_green_count}只，红灯{abnormal_red_count}只。绿灯代表“跌不下去”，红灯代表“异动后转弱”。")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
