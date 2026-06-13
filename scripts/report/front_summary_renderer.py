from report.front_summary_node_registry import build_front_summary_node_specs
from report.front_summary_node_runtime import run_front_summary_nodes
from report.mainline_turnover_summary_support import (
    render_hot_sector_turnover_watch_grouped_lines,
    resolve_hot_sector_turnover_watch_rows,
    resolve_hot_sector_turnover_watch_summary,
    resolve_mainline_attack_evidence_rows,
    resolve_mainline_capacity_regime_summary,
    resolve_turnover_share_trend_summary,
    resolve_turnover_share_trend_rows,
)
from report.cycle_sector_style import cycle_sector_color_map_from_calendar_rows, cycle_sector_label
from report.surface_wording import sanitize_user_visible_text
from report.trading_time_window_contract import normalize_trading_time_text


def sanitize_front_page_text(value):
    return normalize_trading_time_text(sanitize_user_visible_text(value))


def _display_latest_first(rows):
    return list(reversed(list(rows or [])))


def _render_mainline_capacity_regime_table(context):
    summary = resolve_mainline_capacity_regime_summary(context)
    if not summary:
        return []
    return [
        "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |",
        "|----------|----------|--------|----------------|--------------|--------------|----------|----------|",
        (
            "| {mainline_capacity} | {mainline_regime} | {primary_line} | {other_lines} | "
            "{confirmation_evidence} | {sector_relationship_state} | {mainline_process} | {tomorrow_action} |"
        ).format(**summary),
    ]


def _render_turnover_share_trend_table(context):
    hot_rows = resolve_hot_sector_turnover_watch_rows(context)
    rows = resolve_turnover_share_trend_rows(context)
    if not hot_rows and not rows:
        return []
    hot_summary = resolve_hot_sector_turnover_watch_summary(context)
    summary = resolve_turnover_share_trend_summary(context)
    color_by_mainline = cycle_sector_color_map_from_calendar_rows((context or {}).get("cycle_calendar_rows") or [])
    lines = []
    if hot_rows:
        if hot_summary:
            lines.append(f"> {hot_summary}")
            lines.append("")
        lines.extend(render_hot_sector_turnover_watch_grouped_lines(hot_rows, color_by_mainline=color_by_mainline))
    if rows:
        lines.append("#### 小周期成交额与主线切换判断")
        if summary:
            lines.append(f"> {summary}")
            lines.append("")
        lines.extend(
            [
                "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
                "|------|------------|------------|------------|------|----------|----------|------|",
            ]
        )
        for row in _display_latest_first(rows):
            rendered_row = dict(row)
            rendered_row["small_cycle_line"] = cycle_sector_label(rendered_row.get("small_cycle_line"), color_by_mainline)
            lines.append(
                "| {date} | {small_cycle_line} | {mainline_turnover} | {market_turnover} | {share} | {share_change} | {cycle_switch_judgement} | {interpretation} |".format(
                    **rendered_row
                )
            )
        lines.append("")
    return lines


def _render_mainline_attack_evidence_table(context):
    rows = resolve_mainline_attack_evidence_rows(context)
    if not rows:
        return []
    lines = [
        "#### 主线攻击证据",
        "| 板块 | 攻击状态 | 净流入排名 | 净流入 | 涨停数 | 高标高度 | 成交占比变化 | 结论 |",
        "|------|----------|------------|--------|--------|----------|--------------|------|",
    ]
    for row in rows[:3]:
        lines.append(
            "| {sector_name} | {attack_state} | {net_inflow_rank} | {net_inflow_amount} | {limit_up_count} | {high_anchor_height} | {turnover_share_change} | {conclusion} |".format(
                **row
            )
        )
    return lines


def render_front_digest(context):
    context = sanitize_front_page_text(context or {})
    risk_parts = context.get("risk_parts") or []
    lines = [
        "### 🧭 前台摘要",
        f"- **先说结论**: {context.get('headline', '-')}",
        f"- **市场现在什么状态**: {context.get('state_text', '-')}",
        f"- **明日主看方向**: {context.get('mainline_label', '-')}",
    ]
    if context.get("opening_tone_text"):
        lines.append(f"- **今日基调**: {context.get('opening_tone_text')}")
    if context.get("mainline_turnover_text"):
        lines.append(f"- **主线更替与占比**: {context.get('mainline_turnover_text')}")
    lines.extend(_render_mainline_capacity_regime_table(context))
    if not context.get("compact"):
        lines.extend(_render_mainline_attack_evidence_table(context))
    lines.extend(_render_turnover_share_trend_table(context))
    if context.get("special_probe_text"):
        lines.append(f"- **特殊标的先看谁**: {context.get('special_probe_text')}")
    if context.get("philosophy_constraint_text"):
        lines.append(f"- **理念约束**: {context.get('philosophy_constraint_text')}")
    if context.get("contract_logic_text"):
        lines.append(f"- **执行依据**: {context.get('contract_logic_text')}")
    if context.get("alignment_pool_text"):
        lines.append(f"- **方向站队池**: {context.get('alignment_pool_text')}")
    if context.get("rotation_summary_text"):
        lines.append(f"- **主线内部轮动**: {context.get('rotation_summary_text')}")
    if context.get("rotation_narrative_text"):
        lines.append(f"- **叙事节点**: {context.get('rotation_narrative_text')}")
    if context.get("weak_to_strong_summary_text"):
        prefix = "弱转强先看谁" if context.get("weak_to_strong_active") else "弱转强先不做"
        lines.append(f"- **{prefix}**: {context.get('weak_to_strong_summary_text')}")
    lines.extend(
        [
            f"- **明天更适合怎么做**: {context.get('style_action_text', '-')}",
            f"- **明天要防什么**: {' / '.join(risk_parts) if risk_parts else '-'}",
            f"- **明天能不能开仓**: {context.get('can_open_text', '-')}",
        ]
    )
    if context.get("stage_label") or context.get("stage_action"):
        lines.append(f"- **现在更像哪个阶段**: {context.get('stage_label', '-')}；{context.get('stage_action', '-')}")
    if context.get("index_profit_relation"):
        lines.append(f"- **指数和赚钱效应是否背离**: {context.get('index_profit_relation')}")
    if context.get("execution_framework_text"):
        lines.append(f"- **怎么执行**: {context.get('execution_framework_text')}")
    if context.get("compact"):
        keep_markers = (
            "先说结论",
            "市场现在什么状态",
            "明日主看方向",
            "今日基调",
            "主线更替与占比",
            "特殊标的先看谁",
            "明天更适合怎么做",
            "明天要防什么",
            "明天能不能开仓",
            "怎么执行",
        )
        lines = [line for line in lines if line.startswith("###") or any(marker in line for marker in keep_markers)]
    lines.append("")
    return lines


def render_mvp_focus_summary(context):
    context = sanitize_front_page_text(context or {})
    lines = ["### 🎯 明日MVP摘要"]
    optional_items = [
        ("特殊标的先看谁", context.get("special_probe_text")),
        ("主线内部轮动", context.get("rotation_summary_text")),
        ("叙事节点", context.get("rotation_narrative_text")),
        ("创业板20cm预启动", context.get("gem_breathing_text") or context.get("filtered_gem_text")),
        ("主线研究对象", context.get("mainline_watch_preview")),
        ("其他方向谁在扛", context.get("crossline_watch_preview")),
        ("观察池先看谁", context.get("generic_watch_preview")),
        ("异常承接先看谁", context.get("abnormal_preview") or context.get("degraded_abnormal_text")),
        ("龙头回看名单", context.get("memory_preview")),
        ("主线先盯谁", context.get("core_preview")),
        ("其他方向还看谁", context.get("cross_core_preview")),
        ("特殊探针", context.get("special_probe_summary_text")),
        ("明天能不能开仓", context.get("structure_layer_text")),
        ("观察周期", context.get("observation_cycle")),
        ("介入周期", context.get("intervention_cycle")),
        ("退出周期", context.get("exit_cycle")),
        ("明天先别碰谁", context.get("delete_preview")),
        ("如果要买只买谁", context.get("buy_target_text")),
        ("明天先盯哪只", context.get("watch_target_text")),
        ("明天到底怎么做", context.get("no_trade_text")),
    ]
    for label, value in optional_items:
        if value:
            lines.append(f"- **{label}**: {value}")
    if context.get("bridge_prep_text"):
        label = context.get("bridge_prep_label") or "条件执行预备态"
        lines.append(f"- **{label}**: {context.get('bridge_prep_text')}")
    if context.get("mainline_probe_text"):
        lines.append(f"- **主线异动里先看谁**: {context.get('mainline_probe_text')}")
    if context.get("crossline_probe_text"):
        lines.append(f"- **跨线异动里先看谁**: {context.get('crossline_probe_text')}")
    if context.get("validation_probe_text"):
        lines.append(f"- **承接验证先看谁**: {context.get('validation_probe_text')}")
    if context.get("front_follow_action_text"):
        lines.append(f"- **明日唯一动作**: {context.get('front_follow_action_text')}")
    if context.get("compact"):
        keep_markers = (
            "特殊标的先看谁",
            "主线研究对象",
            "观察池先看谁",
            "异常承接先看谁",
            "龙头回看名单",
            "创业板20cm预启动",
            "弱转强先看谁",
            "弱转强先不做",
            "明天能不能开仓",
            "观察周期",
            "介入周期",
            "退出周期",
            "明天先别碰谁",
            "明日唯一动作",
        )
        lines = [line for line in lines if line.startswith("###") or any(marker in line for marker in keep_markers)]
    lines.append("")
    return lines


def _build_front_digest_node(context, node_meta=None, node_lookup=None):
    return {"lines": render_front_digest(context.get("front_digest", {}) or {}), "exports": {}, "module_logs": []}


def _build_mvp_focus_node(context, node_meta=None, node_lookup=None):
    return {"lines": render_mvp_focus_summary(context.get("mvp_focus", {}) or {}), "exports": {}, "module_logs": []}


FRONT_SUMMARY_NODE_BUILDERS = {
    "front_digest": _build_front_digest_node,
    "mvp_focus": _build_mvp_focus_node,
}


def build_front_summary_sections_result(context):
    context = context or {}
    node_specs = build_front_summary_node_specs(
        FRONT_SUMMARY_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_front_summary_nodes(node_specs, context)


def render_front_summary_sections(context):
    return sanitize_front_page_text(build_front_summary_sections_result(context).get("lines", []))
