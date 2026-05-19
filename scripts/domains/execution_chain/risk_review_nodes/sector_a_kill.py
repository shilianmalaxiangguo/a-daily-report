from report.mainline_turnover_summary_support import resolve_mainline_attack_evidence_summary


def build_risk_review_sector_a_kill_node(context, node_meta=None, node_lookup=None):
    mainline_name = str(context.get("mainline_name", "") or "").strip()
    mainline_dt_stocks = context.get("mainline_dt_stocks", []) or []
    structural_a_kill = bool(context.get("structural_a_kill", False))
    structural_reason = str(context.get("structural_reason", "") or "").strip()
    mainline_a_kill = bool(context.get("mainline_a_kill", False))
    a_kill_blacklist_updates = context.get("a_kill_blacklist_updates", []) or []
    risk_sectors_from_dt = context.get("risk_sectors_from_dt", []) or []
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    has_unconfirmed_attack_evidence = bool(attack_summary) and attack_summary.get("attack_state") != "confirmed_attack"

    lines = [
        "**板块级A杀预判**（基于今日跌停分布预判明日）",
        "> **只看什么**：主线有没有批量跌停和结构破坏。",
        "",
    ]
    if has_unconfirmed_attack_evidence:
        lines.append("- ✅ **主线状态**: 当前无确认主攻线，只检查候选方向是否出现批量跌停。")
    elif len(mainline_dt_stocks) >= 3:
        lines.append(f"- ❌ **A杀确认（板块级）**: 当前主线'{mainline_name}'出现批量跌停（{len(mainline_dt_stocks)}只，三人成众）！")
        lines.append(f"  - 跌停股票: {', '.join([item.get('name', '') for item in mainline_dt_stocks[:5]])}")
        lines.append("  - **结论**: 高位站不住，板块级A杀确认，直接删除观察列表。")
    elif structural_a_kill:
        lines.append(f"- ❌ **A杀确认（结构级）**: {structural_reason}")
        if mainline_dt_stocks:
            lines.append(f"  - 结构破坏对象: {', '.join([item.get('name', '') for item in mainline_dt_stocks[:3]])}")
        lines.append("  - **结论**: 这不是正常调整，而是趋势破坏。直接删除观察列表，并进入25天禁买池。")
    elif len(mainline_dt_stocks) >= 1:
        lines.append(f"- ⚠️ **明天要防什么**: 当前主线'{mainline_name}'出现{len(mainline_dt_stocks)}只跌停股")
        lines.append(f"  - 跌停股票: {', '.join([item.get('name', '') for item in mainline_dt_stocks[:3]])}")
        lines.append("  - **说明**: 未达到A杀确认，但需继续观察是否恶化为结构性破坏")

    if mainline_a_kill and a_kill_blacklist_updates:
        lines.append("- **已写入A杀冷却池**（25天内禁买）:")
        for item in a_kill_blacklist_updates[:5]:
            lines.append(
                f"  - {item.get('name', '-') or '-'}({item.get('code', '-') or '-'}) | "
                f"A杀日{item.get('a_kill_date', '-')} | 禁买至{item.get('ban_until', '-')}"
            )

    if not mainline_a_kill and not has_unconfirmed_attack_evidence:
        if risk_sectors_from_dt:
            lines.append("- **其他A杀板块**（批量跌停>=3只，非当前主线）:")
            for risk in risk_sectors_from_dt[:3]:
                lines.append(f"  - {risk['sector']}（跌停{risk['count']}只：{', '.join(risk['stocks'])}）")
            lines.append(f"- ✅ **当前主线**: '{mainline_name}'暂未出现A杀确认，继续观察抗性")
        else:
            lines.append(f"- ✅ **当前主线**: '{mainline_name}'无批量跌停，也无明显结构破坏，暂未出现A杀信号")

    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
