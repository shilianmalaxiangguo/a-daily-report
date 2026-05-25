from report.surface_wording import sanitize_user_visible_text
from report.mainline_turnover_summary_support import (
    resolve_mainline_attack_evidence_summary,
    resolve_mainline_capacity_regime_summary,
)


def _render_gem_breathing_step2_lines(gem_observation_stocks, filtered_out_gem_candidates=None, display_mvp_mode=False):
    gem_observation_stocks = gem_observation_stocks or []
    filtered_out_gem_candidates = filtered_out_gem_candidates or []
    if not gem_observation_stocks and not filtered_out_gem_candidates:
        return []

    preview = gem_observation_stocks[:2] if display_mvp_mode else gem_observation_stocks[:4]
    lines = [
        "> **主线侧翼弹性层**：若主板强锚仍在，创业板20cm只作为主线白银弹性观察，不单列成独立战场。",
        "> **观察纪律**：只先进观察池，先看波动收敛、量价温和放大和右侧确认；确认前只观察不执行。",
    ]
    if filtered_out_gem_candidates:
        filtered_preview = filtered_out_gem_candidates[:2] if display_mvp_mode else filtered_out_gem_candidates[:4]
        filtered_text = "；".join(
            f"{item.get('name', '-')}({item.get('code', '-')})/{item.get('sector', '-')}：{item.get('filtered_reason', '-') or '-'}"
            for item in filtered_preview
        )
        lines.append(f"> **主线过滤提示**：当前有20cm预启动样本，但因非主线被过滤：{filtered_text}")
    if not preview:
        lines.append("")
        return lines

    lines.extend(
        [
            "| 序号 | 股票 | 代码 | 板块 | 预启动层级 | 当前线索 | 预判强度 | 明日原则 |",
            "|------|------|------|------|------------|----------|----------|----------|",
        ]
    )
    for i, item in enumerate(preview, 1):
        lines.append(
            f"| {i} | {item.get('name', '-')} | {item.get('code', '-')} | {item.get('sector', '-')} | "
            f"{item.get('tier', '-') or '-'} | {sanitize_user_visible_text(item.get('abnormal_summary', item.get('note', '-')) or '-')} | "
            f"{item.get('tomorrow_strength', 0)}分 | 先看右侧确认和60分钟确认，不满足继续观察 |"
        )
    lines.append("")
    return lines


def _render_gem_breathing_step2_section(context, gem_observation_stocks, filtered_out_gem_candidates, display_mvp_mode):
    return _render_gem_breathing_step2_lines(
        gem_observation_stocks,
        filtered_out_gem_candidates=filtered_out_gem_candidates,
        display_mvp_mode=display_mvp_mode,
    )


def build_candidate_selection_mainline_summary_node(context, node_meta=None, node_lookup=None):
    core_stocks = context.get("core_stocks", []) or []
    secondary_stocks = context.get("secondary_stocks", []) or []
    crossline_observation_stocks = context.get("crossline_observation_stocks", []) or []
    gem_observation_stocks = context.get("gem_observation_stocks", []) or []
    filtered_out_gem_candidates = context.get("filtered_out_gem_candidates", []) or []
    primary_mainline = str(context.get("primary_mainline", "") or "").strip()
    display_mvp_mode = bool(context.get("display_mvp_mode", False))
    safe_float = context["safe_float"]
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    capacity_summary = resolve_mainline_capacity_regime_summary(context)
    confirmed_attack_line = (
        str(attack_summary.get("primary_line") or "").strip()
        if attack_summary.get("attack_state") == "confirmed_attack"
        else ""
    )
    no_confirmed_attack = bool(attack_summary) and not confirmed_attack_line
    share_trend_label = str((context.get("mainline_turnover_summary") or {}).get("share_trend_label") or "").strip()
    countertrend_attack = bool(confirmed_attack_line and share_trend_label == "逆势试攻")

    core_sectors = {}
    sector_best_strength = {}
    for stock in core_stocks + secondary_stocks:
        sector = stock.get("sector", "其他")
        core_sectors[sector] = core_sectors.get(sector, 0) + 1
        strength = safe_float(stock.get("tomorrow_strength", 0))
        sector_best_strength[sector] = max(sector_best_strength.get(sector, 0), strength)

    lines = []
    if no_confirmed_attack:
        reason = (
            attack_summary.get("confirmation_evidence")
            or capacity_summary.get("confirmation_evidence")
            or "主线攻击证据不足"
        )
        lines.append("**明日核心方向预判**: 无确认主攻线")
        lines.append(f"> **明日纪律**: {reason}，核心标的只保留观察，不按主线买入。")
        if primary_mainline:
            lines.append(f"> **候选补充**: {primary_mainline}只是候选观察，不视为确认主攻线。")
        lines.extend(
            _render_gem_breathing_step2_section(
                context,
                gem_observation_stocks,
                filtered_out_gem_candidates,
                display_mvp_mode,
            )
        )
        lines.append("")
        return {"lines": lines, "exports": {}, "module_logs": []}

    effective_mainline = confirmed_attack_line or primary_mainline
    if effective_mainline:
        matching_stocks = [
            stock
            for stock in core_stocks + secondary_stocks
            if str((stock or {}).get("sector") or "").strip() == effective_mainline
        ]
        if not matching_stocks and effective_mainline == primary_mainline:
            matching_stocks = list(core_stocks + secondary_stocks)
        mainline_count = len(matching_stocks)
        mainline_best_strength = max((safe_float(stock.get("tomorrow_strength", 0)) for stock in matching_stocks), default=0)
        if countertrend_attack:
            lines.append(f"**明日核心方向预判**: {effective_mainline}（局部逆势活跃只按观察处理）")
            lines.append("> **明日纪律**: 放量杀跌里先防踩踏，只看次日承接修复，不把局部强势当成参与资格。")
            if primary_mainline and primary_mainline != effective_mainline:
                lines.append(f"> **候选补充**: {primary_mainline}只是局部活口，不视为确认主攻线。")
            lines.extend(
                _render_gem_breathing_step2_section(
                    context,
                    gem_observation_stocks,
                    filtered_out_gem_candidates,
                    display_mvp_mode,
                )
            )
            lines.append("")
            return {"lines": lines, "exports": {}, "module_logs": []}
        lines.append(f"**明日核心方向预判**: {effective_mainline}（主线内{mainline_count}只，最强样本{int(mainline_best_strength)}分）")
        lines.append(f"> **明日纪律**: 认准'{effective_mainline}'，只在主线里等最强对象自己走出来；综合分只用于个股排序，不累加成板块分。")
        if crossline_observation_stocks:
            strongest_crossline = sorted(
                crossline_observation_stocks,
                key=lambda item: (safe_float(item.get("tomorrow_strength", 0)), safe_float(item.get("score", 0))),
                reverse=True,
            )[0]
            lines.append(
                f"> **跨线补充**: {strongest_crossline.get('sector', '其他')}里的{strongest_crossline.get('name', '-')}"
                "更像承接观察对象，不视为主攻线切换。"
            )
        lines.extend(
            _render_gem_breathing_step2_section(
                context,
                gem_observation_stocks,
                filtered_out_gem_candidates,
                display_mvp_mode,
            )
        )
        lines.append("")
        return {"lines": lines, "exports": {}, "module_logs": []}

    if core_sectors:
        sorted_sectors = sorted(core_sectors.items(), key=lambda item: (item[1], sector_best_strength[item[0]]), reverse=True)
        main_sector = sorted_sectors[0]
        lines.append(f"**明日核心方向预判**: {main_sector[0]}（{main_sector[1]}只，最强样本{int(sector_best_strength.get(main_sector[0], 0))}分）")
        lines.append(f"> **明日纪律**: 认准'{main_sector[0]}'，明日若该板块竞价强势，只看该板块核心是否满足参与条件；综合分不累加成板块分。")
        lines.extend(
            _render_gem_breathing_step2_section(
                context,
                gem_observation_stocks,
                filtered_out_gem_candidates,
                display_mvp_mode,
            )
        )
        lines.append("")
        return {"lines": lines, "exports": {}, "module_logs": []}

    return {"lines": [], "exports": {}, "module_logs": []}
