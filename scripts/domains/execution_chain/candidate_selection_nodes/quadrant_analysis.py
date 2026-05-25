from report.mainline_turnover_summary_support import (
    resolve_display_mainline_name,
    resolve_mainline_attack_evidence_summary,
)


def _call_ai_sector_relationships(ai_analyze_sector_relationships, sector_names, context_text, tag_evidence_snapshot):
    try:
        return ai_analyze_sector_relationships(
            sector_names,
            context_text,
            tag_evidence_snapshot=tag_evidence_snapshot,
        )
    except TypeError as error:
        if "tag_evidence_snapshot" not in str(error):
            raise
        return ai_analyze_sector_relationships(sector_names, context_text)


def build_candidate_selection_quadrant_analysis_node(context, node_meta=None, node_lookup=None):
    data = context.get("data", {}) or {}
    exit_analysis = context.get("exit_analysis", {}) or {}
    dragon_stocks = context.get("dragon_stocks", []) or []
    primary_mainline = str(context.get("primary_mainline", "") or "").strip()
    ai_analyze_sector_relationships = context.get("ai_analyze_sector_relationships")
    display_mvp_mode = bool(context.get("display_mvp_mode", False))
    target_date = context.get("target_date", "")
    position_level = context.get("position_level", "")
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    has_unconfirmed_attack_evidence = bool(attack_summary) and attack_summary.get("attack_state") != "confirmed_attack"

    quadrant_data = data.get("sector_quadrant")
    if not quadrant_data or not quadrant_data.get("high_strong_analysis"):
        return {"lines": [], "exports": {"mainline_in_quadrant": None, "mainline_score": 0}, "module_logs": []}

    hs_analysis = quadrant_data["high_strong_analysis"]
    current_mainline = "" if has_unconfirmed_attack_evidence else resolve_display_mainline_name(
        context,
        fallback=primary_mainline or exit_analysis.get("sector_name", ""),
    )
    mainline_in_quadrant = None
    mainline_score = 0
    if current_mainline:
        for tier_name, tier_label in [
            ("tier1_best", "🏆 最佳击球区"),
            ("tier2_good", "⭐ 优质击球区"),
            ("tier3_normal", "✓ 普通击球区"),
        ]:
            matched = next(
                (
                    sector
                    for sector in hs_analysis.get(tier_name, [])
                    if current_mainline in sector["name"] or sector["name"] in current_mainline
                ),
                None,
            )
            if matched:
                mainline_in_quadrant = tier_label
                mainline_score = matched.get("quality_score", 0)
                break
        if not mainline_in_quadrant:
            mainline_in_quadrant = "❌ 不在击球区"

    lines = [
        "**击球区结果**",
        "> **只看什么**: 当前主线在不在击球区，得分够不够。",
        "",
        "**击球区质量分层**:",
        "| 等级 | 得分范围 | 板块数 | 特征 |",
        "|------|----------|--------|------|",
        f"| 🏆 最佳击球区 | 80-100分 | {hs_analysis.get('tier1_count', 0)}个 | 高位置+强动量+放量 |",
        f"| ⭐ 优质击球区 | 60-79分 | {hs_analysis.get('tier2_count', 0)}个 | 至少两项强 |",
        f"| ✓ 普通击球区 | 40-59分 | {hs_analysis.get('tier3_count', 0)}个 | 勉强符合 |",
        f"| ⚠️ 边缘击球区 | <40分 | {hs_analysis.get('tier4_count', 0)}个 | 伪击球区，应过滤 |",
        "",
    ]
    if has_unconfirmed_attack_evidence:
        lines.append("**主线位置判断**: 当前无确认主攻线，击球区只作为候选板块质量参考")
        lines.append("")
    elif mainline_in_quadrant:
        lines.append(f"**主线位置判断**: 当前主线'{current_mainline or '未知'}'位于{mainline_in_quadrant}（得分{mainline_score}分）")
        lines.append("")

    if not display_mvp_mode and ai_analyze_sector_relationships:
        all_sector_names = []
        for stock in dragon_stocks[:5]:
            sector_name = stock.get("sector", "")
            if sector_name and sector_name not in all_sector_names:
                all_sector_names.append(sector_name)
        for tier_key in ["tier1_best", "tier2_good", "tier3_normal"]:
            for sector in hs_analysis.get(tier_key, []):
                sector_name = sector.get("name", "")
                if sector_name and sector_name not in all_sector_names:
                    all_sector_names.append(sector_name)
        ai_analysis = _call_ai_sector_relationships(
            ai_analyze_sector_relationships,
            all_sector_names,
            f"市场环境: {position_level}, 日期: {target_date}",
            data.get("realtime_tag_evidence_snapshot") or context.get("realtime_tag_evidence_snapshot") or {},
        )
        if ai_analysis.get("groups"):
            lines.append("**板块归并结果**")
            lines.append("> **只看什么**: 哪些分散标签其实指向同一条主线。")
            lines.append("")
            lines.append("| 大方向 | 包含标签 | 主线依据 | 资金状态 |")
            lines.append("|--------|----------|----------|----------|")
            for group in ai_analysis.get("groups", []):
                sectors_text = "、".join(group.get("sectors", [])[:3])
                if len(group.get("sectors", [])) > 3:
                    sectors_text += f" 等{len(group.get('sectors', []))}个"
                lines.append(
                    f"| **{group.get('name', '-')}** | {sectors_text} | "
                    f"{group.get('reason', '-')} | {group.get('investment_logic', '-')} |"
                )
            lines.append("")

    return {
        "lines": lines,
        "exports": {"mainline_in_quadrant": mainline_in_quadrant, "mainline_score": mainline_score},
        "module_logs": [],
    }
