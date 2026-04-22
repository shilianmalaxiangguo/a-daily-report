def _render_decision_stack(lines, decision_stack_order_text, scored_executable_stocks):
    if not scored_executable_stocks:
        return

    lines.append(f"**Step 4.5.0 决策栈排序**（{decision_stack_order_text}）:")
    lines.append("| 股票 | 环境 | 主线 | 记忆 | 触发 | 可交易性 | EV | 备注 |")
    lines.append("|------|------|------|------|------|----------|----|------|")
    for item in scored_executable_stocks:
        stack = item.get("decision_stack", {}) or {}
        note = item.get("permission_label", "-") or "-"
        if item.get("abnormal_setup_signal_label"):
            note = f"{note} / {item.get('abnormal_setup_signal_label')}"
        lines.append(
            f"| {item.get('name', '-')} | {stack.get('environment_score', '-')} | "
            f"{stack.get('mainline_score', '-')} | {stack.get('memory_score', '-')} | "
            f"{stack.get('trigger_score', '-')} | {stack.get('tradability_score', '-')} | "
            f"{stack.get('ev_score', '-')} | {note} |"
        )
    lines.append("")


def _render_single_candidate(lines, pk_candidates):
    best_stock = pk_candidates[0]
    signal = best_stock.get("signal")
    lines.append(f"**✅ 明天唯一能买的那只**: {best_stock.get('name')}({best_stock.get('code')})")
    if signal:
        lines.append(f"> **买点**: {signal.signal_type}")
        lines.append(
            f"> **大概成功率**: {best_stock.get('win_rate', 0) * 100:.0f}% | "
            f"**赚赔比**: 1:{best_stock.get('r_reward_ratio', 0):.1f}"
        )
        lines.append(f"> **这笔值不值得做**: {best_stock.get('ev', 0):.2f}元/股")
        lines.append(f"> **成功率是按什么算的**: {best_stock.get('ev_model_source', '类型先验')}")
        lines.append("> **真到盘中怎么做**: 明日仍需60分钟确认后再买，买后用30分钟结构止损")
    else:
        lines.append("> **真到盘中怎么做**: 明日仅在60分钟确认后按条件触发，买后用30分钟结构止损")
    lines.append("")


def _render_multi_candidate(lines, pk_candidates):
    lines.append(f"**Step 4.5.1 成功率收益对比表**（{len(pk_candidates)}只进入PK）:")
    lines.append("| 股票 | 买点 | 从什么价开始算 | 大概止损放哪 | 大概成功率 | 赚赔比 | 这笔值不值得做 | 参考记录 | EV排名 |")
    lines.append("|------|------|--------|--------|------|--------|----------|------|--------|")

    for i, item in enumerate(pk_candidates, 1):
        signal = item.get("signal")
        if signal:
            buy_type_map = {"sweet_zone": "甜品区", "breakout": "突破", "panic_buy": "恐慌盘"}
            buy_type = buy_type_map.get(signal.signal_type, signal.signal_type)
            entry = signal.entry_price
            stop = item.get("stop_loss", signal.stop_loss)
        else:
            buy_type = "基础"
            entry = item.get("entry_price", item.get("close", 0))
            stop = item.get("stop_loss", entry * 0.95 if entry else 0)

        sample_text = f"{int(float(item.get('ev_sample_size', 0) or 0))} / {int(float(item.get('ev_global_sample_size', 0) or 0))}"
        lines.append(
            f"| {item.get('name')} | {buy_type} | {entry:.2f} | {stop:.2f} | "
            f"{item.get('win_rate', 0.5) * 100:.0f}% | 1:{item.get('r_reward_ratio', 2.0):.1f} | "
            f"{item.get('ev', 0):.2f} | {sample_text} | 第{i}名 |"
        )

    best_stock = pk_candidates[0]
    runner_up = pk_candidates[1] if len(pk_candidates) > 1 else None
    best_signal = best_stock.get("signal")

    lines.append("")
    lines.append(f"**🏆 PK结果**: **{best_stock.get('name')}({best_stock.get('code')})** 胜出！")
    lines.append("")
    lines.append("**胜出者详细分析**:")
    if best_signal:
        profit = best_stock.get("profit_space", 0)
        loss = best_stock.get("loss_space", 0)
        win_rate = best_stock.get("win_rate", 0.5)
        lines.append(f"- **怎么买**: {best_signal.signal_type}")
        lines.append(
            f"- **从什么价开始算**: {best_signal.entry_price:.2f} | "
            f"**大概止损放哪**: {best_stock.get('stop_loss', best_signal.stop_loss):.2f}"
        )
        lines.append(f"- **做对大概能赚多少**: +{profit:.2f} ({best_stock.get('r_reward_ratio', 0):.1f}倍赚赔比)")
        lines.append(f"- **最差会亏多少**: -{loss:.2f} (跌破止损)")
        lines.append(f"- **成功率大概多少**: {win_rate * 100:.0f}%")
        lines.append(
            f"- **这笔值不值得做**: {best_stock.get('ev', 0):.2f}元/股 = "
            f"({win_rate * 100:.0f}% × {profit:.2f}) - ({(1 - win_rate) * 100:.0f}% × {loss:.2f})"
        )
        lines.append(f"- **成功率是按什么算的**: {best_stock.get('ev_model_source', '类型先验')}")
        lines.append(f"- **仓位放多少**: {float(best_stock.get('position_pct', 0) or 0):.0f}%")
        lines.append("- **真到盘中怎么做**: 明日真正入场仍需60分钟确认，买后立刻切到30分钟结构止损")
    if runner_up:
        lines.append(
            f"- **为什么它排第一**: 比第二名高{best_stock.get('composite_score', 0) - runner_up.get('composite_score', 0):.2f}分"
        )
    lines.append("")

    if runner_up:
        lines.append("**Step 4.5.2 为什么没选它**:")
        lines.append(f"| 对比项 | 🏆 {best_stock.get('name')} | ❌ {runner_up.get('name')} | 差距 |")
        lines.append("|--------|---------------------------|---------------------------|------|")
        lines.append(
            f"| 这笔值不值得做 | {best_stock.get('ev', 0):.2f} | {runner_up.get('ev', 0):.2f} | "
            f"+{best_stock.get('ev', 0) - runner_up.get('ev', 0):.2f} |"
        )
        lines.append(
            f"| 大概成功率 | {best_stock.get('win_rate', 0) * 100:.0f}% | "
            f"{runner_up.get('win_rate', 0) * 100:.0f}% | "
            f"{(best_stock.get('win_rate', 0) - runner_up.get('win_rate', 0)) * 100:.0f}% |"
        )
        lines.append(
            f"| 赚赔比 | 1:{best_stock.get('r_reward_ratio', 0):.1f} | "
            f"1:{runner_up.get('r_reward_ratio', 0):.1f} | - |"
        )
        lines.append(
            f"| 综合评分 | {best_stock.get('composite_score', 0):.2f} | "
            f"{runner_up.get('composite_score', 0):.2f} | "
            f"+{best_stock.get('composite_score', 0) - runner_up.get('composite_score', 0):.2f} |"
        )
        lines.append("")
        lines.append("**淘汰原因**:")
        for item in pk_candidates[1:]:
            lines.append(
                f"- ❌ {item.get('name')}({item.get('code')}) - EV {item.get('ev', 0):.2f} < "
                f"冠军{best_stock.get('ev', 0):.2f}，差距{best_stock.get('ev', 0) - item.get('ev', 0):.2f}，明日不操作"
            )
        lines.append("")


def render_pk_decision_section(context):
    context = context or {}
    lines = [
        "#### Step 4.5 - PK决胜局（期望值模型）",
        "> **核心问题**：真正允许出手时，只能买一只，谁的期望值(EV)最高？",
        "> **PK公式**: EV = 成功率 × 盈利空间 - 失败率 × 亏损空间",
        "> **纪律补充**: 只有执行权候选才允许进入PK；观察权候选一律留在观察层。",
        "> **止损口径**: EV暂按日报大概止损放哪测算；次日真实执行以30分钟结构止损为准，最晚不超过单笔-5%。",
        "> **EV校准**: 优先使用历史策略账本中的同类信号结果校准成功率/赚赔比；参考记录不够时回退到类型先验。",
        "",
    ]

    _render_decision_stack(
        lines,
        context.get("decision_stack_order_text", "环境 -> 主线 -> 记忆 -> 触发 -> 可交易性 -> EV"),
        context.get("scored_executable_stocks") or [],
    )

    pk_candidates = context.get("pk_candidates") or []
    if len(pk_candidates) == 1:
        _render_single_candidate(lines, pk_candidates)
    elif len(pk_candidates) >= 2:
        _render_multi_candidate(lines, pk_candidates)
    elif context.get("trade_gate_open"):
        lines.extend(context.get("pending_lines") or ["**当前没有能下手的票**: 无需PK", ""])
    else:
        lines.append(f"**⛔ 当前先不开新仓**: {context.get('position_level', '')}，本轮不做PK出手结论。")
        lines.extend(context.get("observation_lines") or [])

    lines.extend(context.get("conclusion_lines") or [])
    if lines and lines[-1] != "":
        lines.append("")
    return lines
