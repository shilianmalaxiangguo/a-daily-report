def render_front_digest(context):
    context = context or {}
    risk_parts = context.get("risk_parts") or []
    lines = [
        "### 🧭 前台摘要",
        f"- **先说结论**: {context.get('headline', '-')}",
        f"- **市场现在什么状态**: {context.get('state_text', '-')}",
        f"- **明日主看方向**: {context.get('mainline_label', '-')}",
    ]
    if context.get("special_probe_text"):
        lines.append(f"- **特殊标的先看谁**: {context.get('special_probe_text')}")
    if context.get("philosophy_constraint_text"):
        lines.append(f"- **理念约束**: {context.get('philosophy_constraint_text')}")
    if context.get("contract_logic_text"):
        lines.append(f"- **底层逻辑**: {context.get('contract_logic_text')}")
    if context.get("alignment_pool_text"):
        lines.append(f"- **方向站队池**: {context.get('alignment_pool_text')}")
    if context.get("rotation_summary_text"):
        lines.append(f"- **主线内部轮动**: {context.get('rotation_summary_text')}")
    if context.get("rotation_narrative_text"):
        lines.append(f"- **叙事节点**: {context.get('rotation_narrative_text')}")
    if context.get("weak_to_strong_summary_text"):
        prefix = "弱转强先看谁" if context.get("weak_to_strong_active") else "弱转强为什么先不做"
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
    context = context or {}
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
            "弱转强为什么先不做",
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
