from report.surface_wording import sanitize_user_visible_text


def build_pk_overview_node(context, node_meta=None, node_lookup=None):
    stage_label = str(context.get("stage_label", "") or "").strip()
    stage_title = str(context.get("stage_title", "") or "PK决胜局（期望值模型）").strip() or "PK决胜局（期望值模型）"
    heading = f"#### {stage_label} - {stage_title}" if stage_label else f"#### {stage_title}"
    return {
        "lines": [
            heading,
            "> **先看结论**：真允许出手时，只保留唯一动作；不允许时，只保留观察。",
            "> **只看什么**：环境、主线、触发、可交易性和历史胜率收益。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_pk_decision_stack_node(context, node_meta=None, node_lookup=None):
    scored_executable_stocks = context.get("scored_executable_stocks") or []
    if not scored_executable_stocks:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        f"**决策栈排序**（{context.get('decision_stack_order_text', '环境 -> 主线 -> 记忆 -> 触发 -> 可交易性 -> EV')}）:",
        "| 股票 | 环境 | 主线 | 记忆 | 触发 | 可交易性 | EV | 备注 |",
        "|------|------|------|------|------|----------|----|------|",
    ]
    for item in scored_executable_stocks:
        stack = item.get("decision_stack", {}) or {}
        note = sanitize_user_visible_text(item.get("permission_label", "-") or "-")
        if item.get("abnormal_setup_signal_label"):
            note = f"{note} / {item.get('abnormal_setup_signal_label')}"
        lines.append(
            f"| {item.get('name', '-')} | {stack.get('environment_score', '-')} | "
            f"{stack.get('mainline_score', '-')} | {stack.get('memory_score', '-')} | "
            f"{stack.get('trigger_score', '-')} | {stack.get('tradability_score', '-')} | "
            f"{stack.get('ev_score', '-')} | {note} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_pk_single_candidate_node(context, node_meta=None, node_lookup=None):
    pk_candidates = context.get("pk_candidates") or []
    if len(pk_candidates) != 1:
        return {"lines": [], "exports": {}, "module_logs": []}

    best_stock = pk_candidates[0]
    signal = best_stock.get("signal")
    lines = [f"**✅ 明天唯一能买的那只**: {best_stock.get('name')}({best_stock.get('code')})"]
    if signal:
        lines.append(f"> **买点**: {signal.signal_type}")
        lines.append(
            f"> **大概成功率**: {best_stock.get('win_rate', 0) * 100:.0f}% | "
            f"**赚赔比**: 1:{best_stock.get('r_reward_ratio', 0):.1f}"
        )
        lines.append(f"> **这笔值不值得做**: {best_stock.get('ev', 0):.2f}元/股")
        lines.append(f"> **参考依据**: {best_stock.get('ev_model_source', '类型先验')}")
        lines.append("> **真到盘中怎么做**: 明日仍需60分钟确认后再买，买后用30分钟结构止损")
    else:
        lines.append("> **真到盘中怎么做**: 明日仅在60分钟确认后按条件触发，买后用30分钟结构止损")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_pk_multi_candidate_node(context, node_meta=None, node_lookup=None):
    pk_candidates = context.get("pk_candidates") or []
    if len(pk_candidates) < 2:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [f"**成功率收益对比表**（{len(pk_candidates)}只进入PK）:"]
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
    lines.extend(["", f"**🏆 PK结果**: **{best_stock.get('name')}({best_stock.get('code')})** 胜出！", "", "**胜出者详细分析**:"])
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
        lines.append(f"- **参考依据**: {best_stock.get('ev_model_source', '类型先验')}")
        lines.append(f"- **仓位放多少**: {float(best_stock.get('position_pct', 0) or 0):.0f}%")
        lines.append("- **真到盘中怎么做**: 明日真正入场仍需60分钟确认，买后立刻切到30分钟结构止损")
    if runner_up:
        lines.append(
            f"- **领先差距**: 比第二名高{best_stock.get('composite_score', 0) - runner_up.get('composite_score', 0):.2f}分"
        )
    lines.append("")

    if runner_up:
        lines.append("**淘汰对比**:")
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
        lines.extend(["", "**淘汰原因**:"])
        for item in pk_candidates[1:]:
            lines.append(
                f"- ❌ {item.get('name')}({item.get('code')}) - EV {item.get('ev', 0):.2f} < "
                f"冠军{best_stock.get('ev', 0):.2f}，差距{best_stock.get('ev', 0) - item.get('ev', 0):.2f}，明日不操作"
            )
        lines.append("")

    return {"lines": lines, "exports": {}, "module_logs": []}


def build_pk_pending_candidates_node(context, node_meta=None, node_lookup=None):
    if not context.get("trade_gate_open"):
        return {"lines": [], "exports": {}, "module_logs": []}
    if context.get("pk_candidates"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": list(context.get("pending_lines") or ["**当前没有能下手的票**: 无需PK", ""]), "exports": {}, "module_logs": []}


def build_pk_observation_candidates_node(context, node_meta=None, node_lookup=None):
    if context.get("trade_gate_open"):
        return {"lines": [], "exports": {}, "module_logs": []}
    lines = [f"**⛔ 当前先不开新仓**: {context.get('position_level', '')}，本轮不做PK出手结论。"]
    lines.extend(list(context.get("observation_lines") or []))
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_pk_conclusion_node(context, node_meta=None, node_lookup=None):
    lines = list(context.get("conclusion_lines") or [])
    if lines and lines[-1] != "":
        lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
