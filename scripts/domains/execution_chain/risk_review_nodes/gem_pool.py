from report.surface_wording import sanitize_user_visible_text


def _render_gem_breathing_pool_lines(gem_observation_stocks=None, filtered_out_gem_candidates=None):
    gem_observation_stocks = gem_observation_stocks or []
    filtered_out_gem_candidates = filtered_out_gem_candidates or []
    if not gem_observation_stocks and not filtered_out_gem_candidates:
        return []

    lines = [
        "#### Step 3.5 - 创业板20cm预启动观察池",
        "> **先看结论**：创业板20cm样本只保留观察权，不单列成独立战场。",
        "> **只看什么**：波动收敛、量价温和放大、右侧确认。",
    ]
    if filtered_out_gem_candidates:
        filtered_text = "；".join(
            f"{item.get('name', '-')}({item.get('code', '-')})/{item.get('sector', '-')}：{item.get('filtered_reason', '-') or '-'}"
            for item in filtered_out_gem_candidates[:4]
        )
        lines.append(f"> **主线过滤提示**：当前有20cm预启动样本，但因非主线被过滤：{filtered_text}")
    lines.append("")
    if not gem_observation_stocks:
        return lines

    lines.extend(["| 股票 | 层级 | 预启动说明 | 观察动作 |", "|------|------|------------|----------|"])
    for item in gem_observation_stocks:
        lines.append(
            f"| {item.get('name', '-')}({item.get('code', '-')}) | {item.get('tier', '-') or item.get('core_level', '-')} | "
            f"{sanitize_user_visible_text(item.get('note', item.get('abnormal_summary', '-')))} | {sanitize_user_visible_text(item.get('watch_anchor_note', item.get('tmr_forecast', '-')))} |"
        )
    lines.append("")
    return lines


def build_risk_review_gem_pool_node(context, node_meta=None, node_lookup=None):
    gem_observation_stocks = context.get("gem_observation_stocks", []) or []
    filtered_out_gem_candidates = context.get("filtered_out_gem_candidates", []) or []
    lines = _render_gem_breathing_pool_lines(
        gem_observation_stocks,
        filtered_out_gem_candidates=filtered_out_gem_candidates,
    )
    return {"lines": list(lines), "exports": {}, "module_logs": []}
