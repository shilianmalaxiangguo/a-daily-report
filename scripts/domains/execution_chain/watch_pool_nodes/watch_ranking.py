def build_watch_pool_watch_ranking_node(context, node_meta=None, node_lookup=None):
    watchlist = context.get("watchlist", []) or []
    display_mvp_mode = bool(context.get("display_mvp_mode", False))

    lines = ["**明日预期强度排序**（按今日形态预判明日延续性）", ""]
    if watchlist:
        lines.append("| 排名 | 股票 | 代码 | 所属板块 | 今日形态 | 预判分数 | 明日预期 | 入池依据 |")
        lines.append("|------|------|------|----------|----------|----------|----------|----------|")
        watchlist_preview = watchlist[:5] if display_mvp_mode else watchlist[:12]
        for idx, item in enumerate(watchlist_preview, 1):
            lines.append(
                f"| {idx} | {item.get('name', '-')} | {item.get('code', '-')} | {item.get('sector', '-')} | "
                f"{item.get('pattern', '-')} | {item.get('score', 0)}分 | {item.get('tomorrow_expectation', '-')} | {item.get('reason', '-')} |"
            )
        lines.append("")

        lianban_expect = [
            item
            for item in watchlist
            if "连板" in item.get("tomorrow_expectation", "") and "一字" not in str(item.get("pattern", ""))
        ][:5]
        premium_expect = [
            item
            for item in watchlist
            if "溢价" in item.get("tomorrow_expectation", "") and "一字" not in str(item.get("pattern", ""))
        ][:3]
        fanbao_expect = [item for item in watchlist if "反包" in item.get("tomorrow_expectation", "")][:3]
        lines.append("**明日预期分组**:")
        if lianban_expect:
            names = ", ".join([f"{item['name']}({item['code']})" for item in lianban_expect])
            lines.append(f"- **🔥 连板预期**（{len(lianban_expect)}只）: {names}")
        if premium_expect:
            names = ", ".join([f"{item['name']}({item['code']})" for item in premium_expect])
            lines.append(f"- **⭐ 溢价预期**（{len(premium_expect)}只）: {names}")
        if fanbao_expect:
            names = ", ".join([f"{item['name']}({item['code']})" for item in fanbao_expect])
            lines.append(f"- **🔄 反包预期**（{len(fanbao_expect)}只）: {names}")
        lines.append("")
    else:
        lines.extend(["**观察池为空**: 今日没有符合明日延续预期的标的。", ""])

    return {"lines": lines, "exports": {}, "module_logs": []}
