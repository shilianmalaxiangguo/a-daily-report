def build_watch_pool_memory_validation_node(context, node_meta=None, node_lookup=None):
    tracking_memory_status = context.get("tracking_memory_status", {}) or {}
    inactive_items = tracking_memory_status.get("inactive_items", []) or []
    reactivated_items = tracking_memory_status.get("reactivated_items", []) or []

    lines = [
        "**跟踪记忆校验**（昨天的观察先验尸，活下来才允许继续跟）",
        f"- **今日重新校验**: {tracking_memory_status.get('today_seen_count', 0)}只",
        f"- **升级为二次确认观察**: {len(tracking_memory_status.get('promoted_items', []))}只",
        f"- **旧强势样本再激活**: {len(reactivated_items)}只",
        f"- **继续作为临时假设**: {len(tracking_memory_status.get('today_tentative_items', []))}只",
        f"- **冷却回看样本**: {len(inactive_items)}只",
        f"- **今日剔除旧记忆**: {len(tracking_memory_status.get('dropped_items', []))}只",
        "- **防错纪律**: 历史记忆只影响跟踪优先级，不直接产生买点；已经转弱先取消买入资格，高辨识度样本转入冷却回看，等重新涨停/再入池再激活。",
    ]

    trusted_items = tracking_memory_status.get("today_validated_items", [])[:3]
    if trusted_items:
        lines.append("| 二次确认观察 | 代码 | 状态 | 今日证据 | 原则 |")
        lines.append("|----------|------|------|----------|------|")
        for item in trusted_items:
            sources = " / ".join(item.get("sources", [])[:3]) or "-"
            follow_state = item.get("follow_state", "") or "今日再次入池"
            lines.append(
                f"| {item.get('name', '-')} | {item.get('code', '-')} | 历史观察已确认 | {sources} + {follow_state} | 只保留优先回看资格，不直接给买入资格 |"
            )
    elif tracking_memory_status.get("new_items"):
        lines.append("- **现在是什么情况**: 还没有形成二次确认观察，今天出现的更多是新假设，不能直接当真。")
    else:
        lines.append("- **现在是什么情况**: 暂无二次确认观察资产，说明系统宁可不记，也不强行继承旧判断。")

    if tracking_memory_status.get("dropped_items"):
        dropped_preview = tracking_memory_status.get("dropped_items", [])[:3]
        dropped_text = "；".join(
            f"{item.get('name', '-') or item.get('code', '-')}({item.get('code', '-')}) {item.get('reason', '')}"
            for item in dropped_preview
        )
        lines.append(f"- **今日自动清除**: {dropped_text}")

    if inactive_items:
        inactive_preview = inactive_items[:3]
        inactive_text = "；".join(
            f"{item.get('name', '-') or item.get('code', '-')}({item.get('code', '-')}) {item.get('inactive_reason', '')}"
            for item in inactive_preview
        )
        lines.append(f"- **冷却回看**: {inactive_text}")

    if reactivated_items:
        reactivated_preview = reactivated_items[:3]
        reactivated_text = "；".join(
            f"{item.get('name', '-') or item.get('code', '-')}({item.get('code', '-')}) 从{item.get('reactivated_from_status', '旧状态')}再激活"
            for item in reactivated_preview
        )
        lines.append(f"- **旧强势样本再激活**: {reactivated_text}")

    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
