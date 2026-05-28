from report.strategy_performance_node_registry import build_strategy_performance_node_specs
from report.strategy_performance_node_runtime import run_strategy_performance_nodes
from report.monitoring_pool_nodes import render_monitoring_pool_nodes
from report.strategy_tracking_review import NEAT_FREAK_ATTRIBUTION_BUCKETS, normalize_neat_freak_attribution_bucket


def _strategy_record_neat_freak_bucket_label(record):
    attribution = record.get("attribution", {}) or {}
    neat_freak_bucket = attribution.get("neat_freak_bucket") if isinstance(attribution, dict) else {}
    if (
        isinstance(neat_freak_bucket, dict)
        and neat_freak_bucket.get("category") in NEAT_FREAK_ATTRIBUTION_BUCKETS
        and neat_freak_bucket.get("label")
    ):
        return neat_freak_bucket.get("label", "-")
    return normalize_neat_freak_attribution_bucket(record, attribution).get("label", "-")


def render_strategy_performance_section(performance_summary, helpers):
    if not performance_summary:
        return []

    helpers = helpers or {}
    ledger_mode_frozen = helpers["ledger_mode_frozen"]
    ledger_mode_replay = helpers["ledger_mode_replay"]
    defensive_exit_rule_text = helpers["defensive_exit_rule_text"]
    format_strategy_record_brief = helpers["format_strategy_record_brief"]
    format_frozen_plan_columns = helpers["format_frozen_plan_columns"]
    get_plan_action_label = helpers["get_plan_action_label"]
    get_recent_record_display_metrics = helpers["get_recent_record_display_metrics"]
    format_pct_range = helpers["format_pct_range"]
    format_pct = helpers["format_pct"]
    safe_float = helpers["safe_float"]

    lines = []
    current_plan = performance_summary.get("current_plan", {})
    ledger_mode = performance_summary.get("ledger_mode", ledger_mode_frozen)
    lines.append("## 十五、策略计划账本")
    lines.append("")
    if ledger_mode == ledger_mode_replay:
        lines.append("> **说明**：当前为实验重放账本，只记录实验结果，不改写官方历史，也不计入正式收益。")
        summary_source_label = performance_summary.get("summary_source_label", "")
        if summary_source_label:
            lines.append(f"> **统计口径**：周/月/结构周期窗口按“{summary_source_label}”合并统计。")
    else:
        lines.append("> **说明**：这里只统计系统自己冻结过的“明日唯一可买计划”。它不知道你的真实持仓，只对自己的计划负责。")
    history_lock_note = performance_summary.get("history_lock_note", "")
    if history_lock_note:
        lines.append(f"> **历史保护**：{history_lock_note}")
    existing_official_record = performance_summary.get("existing_official_record")
    if ledger_mode == ledger_mode_replay and existing_official_record:
        lines.extend(
            [
                "",
                "#### 历史冻结基线 vs 本次实验推演",
                "",
                "| 口径 | 计划摘要 |",
                "|------|----------|",
                f"| 历史冻结基线 | {format_strategy_record_brief(existing_official_record)} |",
                f"| 本次实验推演 | {format_strategy_record_brief(current_plan)} |",
            ]
        )
    lines.append("")

    lines.append("### 1. 本次实验计划" if ledger_mode == ledger_mode_replay else "### 1. 今日冻结计划")
    lines.extend(
        [
            "",
            "| 日期 | 计划状态 | 状态层 | 标的 | 买入区间 | 09:50-10:10窗口 | 次日观察边界 | 历史异动锚点 | 执行止损 | 备注 |",
            "|------|----------|--------|------|----------|-------------|--------------|--------------|----------|------|",
        ]
    )
    plan_name = current_plan.get("stock_name") or current_plan.get("anchor_type") or "无"
    if current_plan.get("stock_code"):
        plan_name = f"{plan_name}({current_plan.get('stock_code')})"
    entry_text, confirm_text, nextday_guard_text, history_anchor_text, execution_text = format_frozen_plan_columns(current_plan)
    note = current_plan.get("trigger_text") or current_plan.get("final_action") or current_plan.get("position_reason") or "-"
    current_plan_label = get_plan_action_label(current_plan.get("action_type", "-"))
    energy_text = current_plan.get("market_energy_state") or "-"
    lines.append(
        f"| {current_plan.get('report_date', '-')} | {current_plan_label} | {energy_text} | "
        f"{plan_name} | {entry_text} | {confirm_text} | {nextday_guard_text} | {history_anchor_text} | {execution_text} | {note} |"
    )
    lines.append("")

    factor_snapshot = current_plan.get("factor_snapshot", {}) or {}
    if factor_snapshot:
        lines.extend(
            [
                "#### 1.1 冻结因子快照",
                "",
                "| 因子 | 分数 | 冻结值 |",
                "|------|------|--------|",
                f"| 环境 | {factor_snapshot.get('environment', {}).get('score', '-')} | "
                f"{factor_snapshot.get('environment', {}).get('position_level', '-')} / {factor_snapshot.get('environment', {}).get('gate_status', '-') or '-'} |",
                f"| 结构 | {factor_snapshot.get('structure', {}).get('score', '-')} | "
                f"{factor_snapshot.get('structure', {}).get('signal_type', '-') or '-'} / {factor_snapshot.get('structure', {}).get('signal_status', '-') or '-'} |",
                f"| 主线 | {factor_snapshot.get('mainline', {}).get('score', '-')} | "
                f"{factor_snapshot.get('mainline', {}).get('name', '-') or '-'} |",
                f"| 记忆 | {factor_snapshot.get('memory', {}).get('score', '-')} | "
                f"可信{factor_snapshot.get('memory', {}).get('trusted_tracking_count', 0)} / 龙头记忆{factor_snapshot.get('memory', {}).get('leader_memory_count', 0)} |",
            ]
        )
        selected_setup = factor_snapshot.get("abnormal", {}).get("selected_setup", {}) or {}
        lines.append(
            f"| 异动 | {factor_snapshot.get('abnormal', {}).get('score', '-')} | "
            f"{selected_setup.get('label', '-') or '-'} / {selected_setup.get('follow_state', '-') or '-'} |"
        )
        state_machine = factor_snapshot.get("state_machine", {}) or {}
        lines.append(
            f"| 市场状态/能量 | {state_machine.get('energy_state', '-') or '-'} | "
            f"{state_machine.get('flow_direction', '-') or '-'} |"
        )
        decision_stack = ((factor_snapshot.get("selection", {}) or {}).get("selected_candidate", {}) or {}).get("decision_stack", {}) or {}
        lines.append(
            f"| 触发/可交易 | {decision_stack.get('trigger_score', '-')} / {decision_stack.get('tradability_score', '-')} | "
            f"{current_plan.get('trigger_text', '-') or '-'} |"
        )
        lines.append("")
        if current_plan.get("factor_snapshot_path"):
            lines.append(f"> **因子快照已冻结**：`{current_plan.get('factor_snapshot_path')}`")
            lines.append("")
        lines.append(
            f"> **卖点拆分**：{current_plan.get('defensive_exit_rule', defensive_exit_rule_text)}；"
            f"{current_plan.get('profit_exit_rule', '-')}"
        )
        if state_machine.get("reflection_focus"):
            lines.append(f"> **状态层反思焦点**：{state_machine.get('reflection_focus')}")
        lines.append("")

    recent_records = performance_summary.get("recent_records", [])
    if recent_records:
        lines.extend(["### 2. 最近计划回放", ""])
        replay_as_of_date = ""
        for record in recent_records:
            replay_as_of_date = (record.get("simulation", {}) or {}).get("as_of_date", "")
            if replay_as_of_date:
                break
        if replay_as_of_date:
            lines.append(
                f"> **口径**：`仅观察 / 不开仓` 样本的 `上证` 固定显示各报告日当天的指数涨跌幅，不再随复盘截止日 `{replay_as_of_date}` 漂移；`已执行` 样本仍按计划实际覆盖区间统计。"
            )
        else:
            lines.append("> **口径**：`仅观察 / 不开仓` 样本的 `上证` 固定显示各报告日当天的指数涨跌幅，不再随复盘日期漂移；`已执行` 样本仍按计划实际覆盖区间统计。")
        lines.extend(
            [
                "",
                "| 报告日 | 标的 | 状态 | 状态层 | 策略收益区间 | 上证 | 超额区间 | 归因 | 盘后归因桶 |",
                "|--------|------|------|--------|--------------|------|----------|------|------------|",
            ]
        )
        for record in recent_records:
            sim = record.get("simulation", {})
            display_metrics = get_recent_record_display_metrics(record)
            stock_label = record.get("stock_name") or record.get("anchor_type") or "无"
            if record.get("stock_code"):
                stock_label = f"{stock_label}({record.get('stock_code')})"
            status = sim.get("status_label") or sim.get("status") or record.get("action_type", "-")
            attribution = record.get("attribution", {}) or {}
            attribution_label = attribution.get("label", "-")
            bucket_label = _strategy_record_neat_freak_bucket_label(record)
            state_text = record.get("market_energy_state", "-") or "-"
            lines.append(
                f"| {record.get('report_date', '-')} | {stock_label} | {status} | {state_text} | "
                f"{format_pct_range(display_metrics.get('strategy_return_worst'), display_metrics.get('strategy_return_best'))} | "
                f"{format_pct(display_metrics.get('benchmark_return'))} | "
                f"{format_pct_range(display_metrics.get('alpha_return_worst'), display_metrics.get('alpha_return_best'))} | "
                f"{attribution_label} | {bucket_label} |"
            )
        lines.append("")

    windows = performance_summary.get("windows", [])
    if windows:
        lines.extend(
            [
                "### 3. 周 / 月 / 结构周期跑赢上证对比",
                "",
                "| 窗口 | 区间 | 计划数 | 触发数 | 策略收益区间 | 上证收益 | 超额收益区间 |",
                "|------|------|--------|--------|--------------|----------|--------------|",
            ]
        )
        for item in windows:
            lines.append(
                f"| {item.get('name', '-')} | {item.get('start_date', '-')} -> {item.get('end_date', '-')} | "
                f"{item.get('plan_count', 0)} | {item.get('triggered_count', 0)} | "
                f"{format_pct_range(item.get('strategy_return_worst'), item.get('strategy_return_best'))} | "
                f"{format_pct(item.get('benchmark_return'))} | "
                f"{format_pct_range(item.get('alpha_return_worst'), item.get('alpha_return_best'))} |"
            )
        lines.append("")

    attribution_week_review = performance_summary.get("attribution_week_review", {}) or {}
    attribution_items = attribution_week_review.get("items", []) or []
    lines.extend(
        [
            "### 4. 错因归属周报",
            "",
            f"> **区间**：{attribution_week_review.get('start_date', '-')} -> {attribution_week_review.get('end_date', '-')}"
            "，先分清是做错、少赚，还是防守正确。",
        ]
    )
    if attribution_items:
        lines.extend(["", "| 盘后归因桶 | 次数 | 代表案例 | 原归因 | 说明 |", "|------------|------|----------|--------|------|"])
        for item in attribution_items:
            lines.append(
                f"| {item.get('label', '-')} | {item.get('count', 0)} | {item.get('sample', '-')} | {item.get('legacy_label', '-') or '-'} | {item.get('reason', '-') or '-'} |"
            )
        lines.append("")
    else:
        lines.extend(["", "- **本周暂无可归因记录**：还需要更多冻结计划来沉淀归因。"])
    highlights = attribution_week_review.get("highlights", []) or []
    if highlights:
        lines.append("- **本周优先复盘点**:")
        for item in highlights[:3]:
            lines.append(f"- {item.get('date', '-')} {item.get('stock', '-')} -> {item.get('label', '-')}：{item.get('reason', '-')}")
    lines.append("")

    gem_20cm_week_review = performance_summary.get("gem_20cm_week_review", {}) or {}
    lines.extend(
        [
            "#### 4.1 创业板20cm观察链周报",
            "",
            f"> **区间**：{gem_20cm_week_review.get('start_date', '-')} -> {gem_20cm_week_review.get('end_date', '-')}"
            "，这里只看创业板20cm预启动合同，不和普通观察对象混在一起。",
        ]
    )
    gem_sample_count = int(safe_float(gem_20cm_week_review.get("sample_count", 0)))
    if gem_sample_count > 0:
        lines.append(
            f"- **总览**: 本周样本{gem_sample_count}只；右侧确认{int(safe_float(gem_20cm_week_review.get('right_side_confirmation_count', 0)))}只；"
            f"再突破{int(safe_float(gem_20cm_week_review.get('rebreak_success_count', 0)))}只；"
            f"升级到30% {int(safe_float(gem_20cm_week_review.get('conditional_upgrade_count', 0)))}只；"
            f"窗口内作废{int(safe_float(gem_20cm_week_review.get('voided_count', 0)))}只；"
            f"窗口到期{int(safe_float(gem_20cm_week_review.get('expired_count', 0)))}只；"
            f"再突破成功但系统给慢了{int(safe_float(gem_20cm_week_review.get('upgrade_lag_count', 0)))}只"
        )
    else:
        lines.append("- **本周暂无创业板20cm合同样本**：先继续积累预启动合同，再看它有没有稳定 edge。")
    lines.append("")

    setup_week_review = performance_summary.get("setup_week_review", {}) or {}
    setup_items = setup_week_review.get("items", []) or []
    lines.extend(
        [
            "### 5. 固定Setup信号库回顾",
            "",
            f"> **区间**：{setup_week_review.get('start_date', '-')} -> {setup_week_review.get('end_date', '-')}"
            "，这里看的是标准 setup 自己的表现，不等于真实成交。",
        ]
    )
    if setup_items:
        lines.extend(["", "| Setup | 出现次数 | 执行次数 | 观察对象 | 强势率 | 平均收益 | 平均相对超额 |", "|-------|----------|----------|----------|--------|----------|--------------|"])
        for item in setup_items:
            lines.append(
                f"| {item.get('setup_label', '-')} | {item.get('plan_count', 0)} | {item.get('execute_count', 0)} | "
                f"{item.get('sample_count', 0)} | {format_pct(item.get('strong_rate'))} | {format_pct(item.get('avg_return'))} | {format_pct(item.get('avg_alpha'))} |"
            )
        lines.append("")
    else:
        lines.extend(["", "- **本周暂无 setup 记录**：固定 setup 库已标准化，但还需要更多冻结计划沉淀表现。", ""])

    ev_week_review = performance_summary.get("ev_week_review", {}) or {}
    ev_items = ev_week_review.get("items", []) or []
    calibration_snapshot = performance_summary.get("ev_calibration_snapshot", {}) or {}
    calibration_global = calibration_snapshot.get("global", {}) or {}
    lines.extend(
        [
            "### 6. 本周EV命中率周报",
            "",
            f"> **区间**：{ev_week_review.get('start_date', '-')} -> {ev_week_review.get('end_date', '-')}"
            "，这里只统计真正进入执行层的计划。",
        ]
    )
    if ev_items:
        lines.extend(["", "| 信号类型 | 执行计划 | 实际触发 | 有效记录 | 命中率 | 平均收益 | 平均超额 |", "|----------|----------|----------|----------|--------|----------|----------|"])
        for item in ev_items:
            lines.append(
                f"| {item.get('signal_label', '-')} | {item.get('plan_count', 0)} | {item.get('triggered_count', 0)} | "
                f"{item.get('sample_count', 0)} | {format_pct(item.get('hit_rate'))} | {format_pct(item.get('avg_return'))} | {format_pct(item.get('avg_alpha'))} |"
            )
        lines.append("")
    else:
        lines.extend(["", "- **本周暂无可验证交易记录**：EV 仍主要依赖类型先验，接下来要靠真实触发记录逐步校准。"])
    global_samples = int(safe_float(calibration_global.get("sample_size", 0)))
    if global_samples > 0:
        lines.append(
            f"- **当前全局校准记录**: {global_samples}笔，全局命中率{format_pct(calibration_global.get('win_rate'))}，"
            f"平均盈利{format_pct(calibration_global.get('avg_win_pct'))}，平均亏损{format_pct(calibration_global.get('avg_loss_pct'))}"
        )
    else:
        lines.append("- **当前全局校准记录**: 0笔，系统仍处于先验学习期。")
    lines.append("")

    self_calibration = performance_summary.get("self_calibration", {}) or {}
    lines.extend(
        [
            "### 7. 系统自校准建议",
            "",
            f"> **校准窗口**：{self_calibration.get('start_date', '-')} -> {self_calibration.get('end_date', '-')}"
            "，先看哪里真的有偏，再决定改哪一层。",
        ]
    )
    if self_calibration.get("overview"):
        lines.append(f"- **窗口概况**: {self_calibration.get('overview')}")
    if self_calibration.get("setup_comment"):
        lines.append(f"- **Setup回顾**: {self_calibration.get('setup_comment')}")
    if self_calibration.get("ev_comment"):
        lines.append(f"- **EV回顾**: {self_calibration.get('ev_comment')}")
    suggestions = self_calibration.get("suggestions", []) or []
    if suggestions:
        lines.extend(["", "| 模块 | 当前判断 | 当前证据 | 下步动作 |", "|------|----------|----------|----------|"])
        for item in suggestions:
            lines.append(
                f"| {item.get('area', '-')} | {item.get('bias', '-')} | {item.get('why', '-') or '-'} | {item.get('action', '-') or '-'} |"
            )
    else:
        lines.append("- **当前无明确校准动作**：继续积累记录。")
    lines.append("")

    structure_cycle_reviews = performance_summary.get("structure_cycle_reviews", []) or []
    graduation_dashboard = performance_summary.get("graduation_dashboard", {}) or {}
    lines.extend(
        [
            "### 8. 跨结构周期毕业看板",
            "",
            f"> **评估口径**：本看板基于 `{graduation_dashboard.get('source_label', '当前账本')}`，判断这套系统到底还停留在原型，还是已经进入可长期辅助阶段。",
            f"- **当前阶段**: {graduation_dashboard.get('stage', '-')}（总分 {graduation_dashboard.get('total_score', 0)}）",
            f"- **判断**: {graduation_dashboard.get('verdict', '-')}",
        ]
    )
    if graduation_dashboard.get("legacy_history_gap"):
        lines.append("- **口径说明**: 官方冻结历史里多数还是旧版本记录，所以“过程完整性/Setup覆盖”分数会偏低，这不代表当前引擎仍是旧形态。")
    lines.append("")

    dimension_scores = graduation_dashboard.get("dimension_scores", []) or []
    if dimension_scores:
        lines.extend(["| 维度 | 得分 | 说明 |", "|------|------|------|"])
        for item in dimension_scores:
            lines.append(f"| {item.get('name', '-')} | {item.get('score', 0)} | {item.get('detail', '-') or '-'} |")
        lines.append("")

    if structure_cycle_reviews:
        lines.extend(["| 结构周期 | 计划数 | 触发数 | 超额区间 | 主导归因 | 主导Setup | 20cm支链 | 结论 |", "|----------|--------|--------|----------|----------|-----------|----------|------|"])
        for item in structure_cycle_reviews:
            lines.append(
                f"| {item.get('cycle_start', '-')} -> {item.get('cycle_end', '-')} | {item.get('plan_count', 0)} | {item.get('triggered_count', 0)} | "
                f"{format_pct_range(item.get('alpha_return_worst'), item.get('alpha_return_best'))} | {item.get('dominant_attribution', '-') or '-'} | "
                f"{item.get('top_setup', '-') or '-'} | {item.get('gem_20cm_summary', '-') or '-'} | {item.get('result_label', '-') or '-'} |"
            )
        lines.append("")

    checks = graduation_dashboard.get("checks", []) or []
    if checks:
        lines.extend(["| 毕业条件 | 状态 | 当前情况 |", "|----------|------|----------|"])
        for item in checks:
            lines.append(f"| {item.get('item', '-')} | {item.get('status', '-')} | {item.get('detail', '-') or '-'} |")
        lines.append("")

    next_actions = graduation_dashboard.get("next_actions", []) or []
    if next_actions:
        lines.append("- **下一阶段动作**:")
        for item in next_actions:
            lines.append(f"- {item}")
    lines.append("")

    monitoring_result = render_monitoring_pool_nodes({"performance_summary": performance_summary})
    monitoring_lines = monitoring_result.get("lines", []) or []
    if monitoring_lines:
        lines.extend(monitoring_lines)
    return lines


def _render_strategy_performance_header_node(context, node_meta=None, node_lookup=None):
    performance_summary = context.get("performance_summary") or {}
    if not performance_summary:
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": ["## 十五、策略计划账本", ""], "exports": {}, "module_logs": []}


def _render_strategy_performance_body_node(context, node_meta=None, node_lookup=None):
    performance_summary = context.get("performance_summary") or {}
    helpers = context.get("helpers") or {}
    lines = render_strategy_performance_section(performance_summary, helpers)
    if lines[:2] == ["## 十五、策略计划账本", ""]:
        lines = lines[2:]
    return {"lines": lines, "exports": {}, "module_logs": []}


STRATEGY_PERFORMANCE_NODE_BUILDERS = {
    "header": _render_strategy_performance_header_node,
    "body": _render_strategy_performance_body_node,
}


def render_strategy_performance_nodes(context):
    context = context or {}
    node_specs = build_strategy_performance_node_specs(
        STRATEGY_PERFORMANCE_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_strategy_performance_nodes(node_specs, context)
