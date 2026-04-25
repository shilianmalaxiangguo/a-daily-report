from report.front_summary_node_registry import build_front_summary_node_specs
from report.front_summary_node_runtime import run_front_summary_nodes
from report.mainline_turnover_summary_support import resolve_double_mainline_summary, resolve_turnover_share_trend_rows


ENGLISH_TRADING_JARGON_REPLACEMENTS = (
    ("follow through", "延续承接"),
    ("act right", "走势符合强势标准"),
    ("setup", "形态条件"),
    ("probe", "优先观察对象"),
)

USER_VISIBLE_WORDING_REPLACEMENTS = (
    ("执行权限", "执行资格"),
    ("执行权", "资格"),
    ("闸门未开", "条件未满足"),
    ("环境闸门", "环境条件"),
    ("门控", "条件"),
    ("开闸", "可做"),
    ("放行", "可做"),
)


def sanitize_front_page_text(value):
    if isinstance(value, str):
        sanitized = value
        for source, target in ENGLISH_TRADING_JARGON_REPLACEMENTS:
            sanitized = sanitized.replace(source, target).replace(source.title(), target).replace(source.upper(), target)
        for source, target in USER_VISIBLE_WORDING_REPLACEMENTS:
            sanitized = sanitized.replace(source, target)
        return sanitized
    if isinstance(value, list):
        return [sanitize_front_page_text(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_front_page_text(item) for item in value)
    if isinstance(value, dict):
        return {key: sanitize_front_page_text(item) for key, item in value.items()}
    return value


def _render_double_mainline_summary_table(context):
    summary = resolve_double_mainline_summary(context)
    if not summary:
        return []
    return [
        "| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |",
        "|----------|------------|----------|----------|",
        "| {cycle_mainline} | {daily_attack_line} | {relationship} | {tomorrow_action} |".format(**summary),
    ]


def _render_turnover_share_trend_table(context):
    rows = resolve_turnover_share_trend_rows(context)
    if not rows:
        return []
    lines = [
        "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |",
        "|------|----------|------------|------------|------------|------|----------|------|",
    ]
    for row in rows:
        lines.append(
            "| {date} | {cycle_mainline} | {daily_attack_line} | {mainline_turnover} | {market_turnover} | {share} | {share_change} | {interpretation} |".format(
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
    if context.get("mainline_turnover_text"):
        lines.append(f"- **主线更替与占比**: {context.get('mainline_turnover_text')}")
    lines.extend(_render_double_mainline_summary_table(context))
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
