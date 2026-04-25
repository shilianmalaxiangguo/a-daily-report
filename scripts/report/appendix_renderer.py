from report.appendix_node_registry import build_appendix_node_specs
from report.appendix_node_runtime import run_appendix_nodes


def _context_value(context, key, default=None):
    return (context or {}).get(key, default)


def _format_cell(value):
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    if value in (None, ""):
        return "-"
    return str(value)


def _format_pct(value):
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _stock_label(item):
    name = item.get("stock_name") or item.get("name") or "-"
    code = item.get("stock_code") or item.get("code") or ""
    return f"{name}({code})" if code else name


def _append_table(lines, title, headers, rows, empty_row=None):
    lines.extend([title, "", "| " + " | ".join(headers) + " |", "|" + "|".join(["------"] * len(headers)) + "|"])
    if rows:
        for row in rows:
            lines.append("| " + " | ".join(_format_cell(value) for value in row) + " |")
    else:
        fallback = empty_row if empty_row is not None else ["-"] * len(headers)
        lines.append("| " + " | ".join(_format_cell(value) for value in fallback) + " |")
    lines.append("")


def _build_appendix_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["---", "", "## 附录：数据获取与执行步骤清单", ""], "exports": {}}


def _build_appendix_data_status_node(context, node_meta=None, node_lookup=None):
    data_status = _context_value(context, "data_status", {}) or {}
    lines = ["### 一、数据获取清单", "| 数据源 | 状态 | 说明 |", "|--------|------|------|"]
    if data_status:
        for key, value in data_status.items():
            status_icon = "✅" if value else "❌"
            status_text = "成功" if value else "失败"
            lines.append(f"| {key} | {status_icon} {status_text} | {'数据正常' if value else '数据缺失或获取失败'} |")
    else:
        lines.append("| 无状态数据 | ❌ 失败 | 状态跟踪未启用 |")
    lines.append("")
    return {"lines": lines, "exports": {}}


def _build_appendix_step_status_node(context, node_meta=None, node_lookup=None):
    step_status = _context_value(context, "step_status", {}) or {}
    lines = ["### 二、执行步骤清单", "| 步骤 | 状态 | 说明 |", "|------|------|------|"]
    if step_status:
        for key, value in step_status.items():
            status_icon = "✅" if value else "❌"
            status_text = "已执行" if value else "跳过/失败"
            lines.append(f"| {key} | {status_icon} {status_text} | {'正常完成' if value else '未执行或失败'} |")
    else:
        lines.append("| 无状态数据 | ❌ 失败 | 状态跟踪未启用 |")
    lines.append("")
    return {"lines": lines, "exports": {}}


def _build_appendix_summary_stats_node(context, node_meta=None, node_lookup=None):
    data_status = _context_value(context, "data_status", {}) or {}
    step_status = _context_value(context, "step_status", {}) or {}
    lines = ["### 三、统计信息"]
    if data_status:
        success_count = sum(1 for value in data_status.values() if value)
        total_count = len(data_status)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        lines.append(f"- **数据源获取成功率**: {success_count}/{total_count} ({success_rate:.1f}%)")
    if step_status:
        success_count = sum(1 for value in step_status.values() if value)
        total_count = len(step_status)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        lines.append(f"- **步骤执行成功率**: {success_count}/{total_count} ({success_rate:.1f}%)")
    lines.append("")
    return {"lines": lines, "exports": {}}


def _build_appendix_metadata_node(context, node_meta=None, node_lookup=None):
    return {
        "lines": [
            "---",
            "",
            f"**报告生成时间**: {_context_value(context, 'generated_at', '')}",
            f"**数据日期**: {_context_value(context, 'target_date', '')}",
            f"**报告版本**: {_context_value(context, 'report_version', 'v2.5.0')}",
            "",
        ],
        "exports": {},
    }


def _build_appendix_timer_stats_node(context, node_meta=None, node_lookup=None):
    normalized_timer_steps = _context_value(context, "normalized_timer_steps", []) or []
    total_time = float(_context_value(context, "total_time", 0) or 0)
    if not normalized_timer_steps:
        return {"lines": [], "exports": {}}
    lines = ["### 执行时间统计", "", "| 步骤 | 耗时 | 累计 | 占比 |", "|------|------|------|------|"]
    for step_name, elapsed, cumulative in normalized_timer_steps:
        percentage = (elapsed / total_time * 100) if total_time > 0 else 0
        lines.append(f"| {step_name} | {elapsed:.2f}s | {cumulative:.2f}s | {percentage:.1f}% |")
    lines.append(f"| **总计** | - | **{total_time:.2f}s** | 100% |")
    lines.append("")
    return {"lines": lines, "exports": {}}


def _build_mainline_continuity_node(context, node_meta=None, node_lookup=None):
    appendix_b = _context_value(context, "appendix_b", {}) or {}
    lines = []
    _append_table(
        lines,
        "### 附录B：历史主线池",
        ["日期", "主线", "状态", "说明"],
        [
            [item.get("date"), item.get("mainline") or item.get("primary_mainline"), item.get("status"), item.get("note") or item.get("rotation_summary")]
            for item in appendix_b.get("historical_mainline_pool", []) or []
        ],
        empty_row=["暂无", "-", "今天开始记录", "后续日报自动累计"],
    )
    _append_table(
        lines,
        "### 附录B：主线切换记录",
        ["日期", "原主线", "新主线", "原因"],
        [
            [item.get("date"), item.get("from_mainline"), item.get("to_mainline"), item.get("reason")]
            for item in appendix_b.get("mainline_switch_log", []) or []
        ],
        empty_row=["暂无", "-", "-", "今天开始记录"],
    )
    _append_table(
        lines,
        "### 附录B：主线成交额占比完整历史",
        ["日期", "主线", "成交额占比", "来源"],
        [
            [item.get("date"), item.get("mainline") or item.get("sector_name"), item.get("turnover_share_pct"), item.get("source")]
            for item in appendix_b.get("turnover_share_history", []) or []
        ],
        empty_row=["暂无", "-", "待累计", "今天开始记录"],
    )
    _append_table(
        lines,
        "### 附录B：中枢对应主线记录",
        ["时间段", "中枢级别", "中枢区间", "所在位置", "对应主线", "主线程度", "演化状态", "接替关系", "解读"],
        [
            [
                item.get("date_range") or item.get("date"),
                item.get("pivot_level") or item.get("structure_level") or item.get("cycle_level"),
                item.get("pivot_range") or item.get("structure"),
                item.get("position"),
                item.get("mainline"),
                item.get("mainline_degree") or item.get("degree"),
                item.get("evolution") or item.get("structure_state"),
                item.get("replacement") or item.get("replacement_relation"),
                item.get("interpretation") or item.get("note"),
            ]
            for item in appendix_b.get("structure_mainline_records", []) or []
        ],
        empty_row=["暂无", "-", "-", "-", "-", "待累计", "待累计", "待确认", "今天开始记录"],
    )
    return {"lines": lines, "exports": {}}


def _build_stock_continuity_node(context, node_meta=None, node_lookup=None):
    appendix_c = _context_value(context, "appendix_c", {}) or {}
    lines = []
    _append_table(
        lines,
        "### 附录C：当前个股观察监控池",
        ["标的", "来源池", "当前处理"],
        [
            [_stock_label(item), item.get("source_pool"), item.get("current_action") or item.get("current_assessment")]
            for item in appendix_c.get("current_stock_monitoring_pool", []) or []
        ],
        empty_row=["暂无", "-", "今天开始记录"],
    )
    _append_table(
        lines,
        "### 附录C：观察对象生命周期表",
        ["标的", "首次进入日报日期", "来自哪天日报", "已跟踪交易日数", "次日至今每日涨幅", "量能变化", "累计涨幅", "当前解读", "当前处理"],
        [
            [
                _stock_label(item),
                item.get("first_report_date"),
                item.get("source_report_date"),
                item.get("tracked_trading_days"),
                item.get("daily_change_series"),
                item.get("volume_change_summary"),
                item.get("cumulative_change_pct"),
                item.get("current_interpretation"),
                item.get("current_action"),
            ]
            for item in appendix_c.get("stock_lifecycle_records", []) or []
        ],
        empty_row=["暂无", "-", "-", "0", "-", "-", "-", "今天开始记录", "继续累计"],
    )
    _append_table(
        lines,
        "### 附录C：A杀淘汰记录",
        ["标的", "A杀日期", "原因"],
        [
            [_stock_label(item), item.get("a_kill_date"), item.get("reason") or item.get("sector_name")]
            for item in appendix_c.get("a_kill_elimination_records", []) or []
        ],
        empty_row=["暂无", "-", "今天无新增"],
    )
    return {"lines": lines, "exports": {}}


def _build_entry_cycle_calibration_node(context, node_meta=None, node_lookup=None):
    calibration = _context_value(context, "entry_cycle_calibration", {}) or {}
    cases = calibration.get("cases", []) or []
    if not cases:
        return {"lines": [], "exports": {}}

    type_label = {"success": "成功样本", "counterexample": "反例样本"}
    fixed_label = {
        "would_false_kill": "会误杀",
        "would_cut_loss": "会止损",
        "would_not_warn": "不预警",
        "would_survive": "可存活",
    }
    mode_label = {
        "structure_band": "结构容忍带",
        "structure_repair_band": "结构修复带",
        "reclaim_failure_exit": "关键区失败降级",
        "time_stop_or_downgrade": "时间止损/降级",
        "a_kill_exit": "A杀出清",
    }

    lines = []
    _append_table(
        lines,
        "### 附录C：介入周期止损校准",
        ["标的", "类型", "入选日", "爆发/验证日", "介入周期", "最大回撤", "振幅", "固定-5%结果", "建议纪律", "结论"],
        [
            [
                _stock_label(item),
                type_label.get(item.get("case_type"), item.get("case_type")),
                item.get("first_report_date"),
                item.get("breakout_date") or item.get("as_of_date"),
                f"{item.get('cycle_gap_trading_days')}日" if item.get("cycle_gap_trading_days") not in (None, "") else "-",
                _format_pct(item.get("max_drawdown_before_breakout_pct")),
                _format_pct(item.get("range_amplitude_pct")),
                fixed_label.get(item.get("fixed_5pct_stop_result"), item.get("fixed_5pct_stop_result")),
                mode_label.get(item.get("recommended_stop_mode"), item.get("recommended_stop_mode")),
                item.get("interpretation") or item.get("case_note"),
            ]
            for item in cases
        ],
    )
    return {"lines": lines, "exports": {"entry_cycle_calibration": calibration}}


APPENDIX_NODE_BUILDERS = {
    "header": _build_appendix_header_node,
    "data_status": _build_appendix_data_status_node,
    "step_status": _build_appendix_step_status_node,
    "summary_stats": _build_appendix_summary_stats_node,
    "metadata": _build_appendix_metadata_node,
    "timer_stats": _build_appendix_timer_stats_node,
    "mainline_continuity": _build_mainline_continuity_node,
    "stock_continuity": _build_stock_continuity_node,
    "entry_cycle_calibration": _build_entry_cycle_calibration_node,
}


def _build_node_specs(builder_map, enabled_node_keys=None):
    node_specs = build_appendix_node_specs(builder_map, enabled_node_keys=enabled_node_keys)
    known_keys = {spec.get("node_key") for spec in node_specs}
    for node_key in enabled_node_keys or []:
        if node_key in known_keys or node_key not in builder_map:
            continue
        node_specs.append({"node_key": node_key, "title": node_key, "builder": builder_map[node_key]})
    return node_specs


def render_execution_appendix(context):
    context = context or {}
    node_specs = _build_node_specs(
        APPENDIX_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_appendix_nodes(node_specs, context).get("lines", [])
