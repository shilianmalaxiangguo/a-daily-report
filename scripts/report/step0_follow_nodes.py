def _full_row(label, current_evidence, derived_judgement, action_effect):
    return f"| {label} | {current_evidence} | {derived_judgement} | {action_effect} |"


def build_step0_follow_verdict_node(context, node_meta=None, node_lookup=None):
    lines = [
        f"**明日裁决**: {context.get('step0_prediction_cn', '-')}",
        f"**裁决依据**: {context.get('step0_reason', '-')}",
        f"**开盘前动作**: {context.get('step0_action', '-')}",
    ]
    if not context.get("compact"):
        lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_step0_follow_table_header_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            "| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |",
            "|----------|----------|----------|--------------|",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_step0_follow_risk_preference_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        lines = [
            f"**盘面风险偏好**: 上证{context.get('zt_count', 0)} / 跌停{context.get('dt_count', 0)}；{context.get('observation_summary', '-')}"
        ]
    else:
        lines = [
            _full_row(
                "盘面风险偏好",
                f"{context.get('zt_count', 0)} / {context.get('dt_count', 0)}",
                context.get("observation_summary", "-"),
                "先看风险偏好，再决定能否继续往下判断",
            )
        ]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_step0_follow_style_background_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            _full_row(
                "风格背景",
                context.get("style_label", "-"),
                context.get("style_reason", "-"),
                "背景参考，不直接触发动作",
            )
        ],
        "exports": {},
        "module_logs": [],
    }


def build_step0_follow_mainline_focus_node(context, node_meta=None, node_lookup=None):
    densest_sector = context.get("densest_sector", "暂无明确主线")
    trend_count = context.get("densest_sector_trend_count", 0)
    derived = f"趋势密度最强方向为{context.get('densest_sector', '待确认')}，活跃趋势股{trend_count}只"
    if context.get("compact"):
        lines = [f"**主线焦点**: {densest_sector}；趋势股{trend_count}只"]
    else:
        lines = [_full_row("主线焦点", densest_sector, derived, "优先聚焦主线对象")]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_step0_follow_abnormal_projection_node(context, node_meta=None, node_lookup=None):
    current = f"{context.get('resilient_abnormal_count', 0)}强 / {context.get('failed_abnormal_count', 0)}弱"
    derived = context.get("abnormal_projection_label", "-")
    if context.get("compact"):
        lines = [f"**异常承接**: {current}；{derived}"]
    else:
        lines = [_full_row("异常承接证据", current, derived, "允许继续进入下一步判断")]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_step0_follow_state_summary_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        lines = [f"**最终状态判断**: {context.get('state_energy', '-') }；{context.get('state_reason', '-')}"]
    else:
        lines = [
            _full_row(
                "最终状态判断",
                context.get("state_energy", "-"),
                context.get("state_reason", "-"),
                "动作锚定到“开盘前动作”",
            )
        ]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_step0_follow_conclusion_node(context, node_meta=None, node_lookup=None):
    lines = ["", f"> **Step 0 结论**: {context.get('step0_reason', '-')}"]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_step0_follow_reminder_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            "> **⚠️ 重要提醒**: Step 0 不再单独猜市场，而是直接引用统一市场研究快照；明日前30分钟先确认环境，真正买点一律等60分钟K线确认；买入后再用30分钟结构定止损。"
        ],
        "exports": {},
        "module_logs": [],
    }


def build_step0_follow_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["", ""], "exports": {}, "module_logs": []}
