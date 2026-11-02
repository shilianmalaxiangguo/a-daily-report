from report.mainline_turnover_summary_support import resolve_mainline_attack_evidence_summary
from report.conclusion_support import resolve_target_position_pct
from report.execution_wording import execution_clause_for_position_pct


def _full_row(label, current_evidence, derived_judgement, action_effect):
    return f"| {label} | {current_evidence} | {derived_judgement} | {action_effect} |"


def _display_dt_count(context):
    value = context.get("dt_count")
    if context.get("dt_count_available") is False or value is None:
        return "待确认"
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return "待确认"


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
    dt_count_text = _display_dt_count(context)
    if context.get("compact"):
        lines = [
            f"**盘面风险偏好**: 上证{context.get('zt_count', 0)} / 跌停{dt_count_text}；{context.get('observation_summary', '-')}"
        ]
    else:
        lines = [
            _full_row(
                "盘面风险偏好",
                f"{context.get('zt_count', 0)} / {dt_count_text}",
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
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    densest_sector = context.get("densest_sector", "暂无明确主线")
    trend_count = context.get("densest_sector_trend_count", 0)
    derived = f"趋势密度最强方向为{context.get('densest_sector', '待确认')}，活跃趋势股{trend_count}只"
    action_effect = "优先聚焦主线对象"
    if attack_summary and attack_summary.get("attack_state") == "confirmed_attack":
        primary_line = str(attack_summary.get("primary_line") or "").strip()
        if primary_line:
            densest_sector = f"主攻线 {primary_line}"
            derived = attack_summary.get("confirmation_evidence") or f"{primary_line}攻击证据成立"
    elif attack_summary and attack_summary.get("attack_state") != "confirmed_attack":
        densest_sector = "无确认主攻线"
        derived = attack_summary.get("confirmation_evidence") or "主线攻击证据不足"
        action_effect = "候选只观察，不给买入资格"
    if context.get("compact"):
        lines = [f"**主线焦点**: {densest_sector}；{derived}"]
    else:
        lines = [_full_row("主线焦点", densest_sector, derived, action_effect)]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_step0_follow_abnormal_projection_node(context, node_meta=None, node_lookup=None):
    resilient_count = int(context.get("resilient_abnormal_count", 0) or 0)
    failed_count = int(context.get("failed_abnormal_count", 0) or 0)
    current = f"{resilient_count}强 / {failed_count}弱" if resilient_count > 0 or failed_count > 0 else "未形成样本"
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


def _zero_participation_context(context):
    context = context or {}
    position_decision = context.get("position_decision") or {}
    if isinstance(position_decision, dict):
        grade = str(position_decision.get("signal_grade") or "").strip()
        if grade.startswith("0"):
            return True
        try:
            if "target_position_pct" in position_decision and float(position_decision.get("target_position_pct") or 0) <= 0:
                return True
        except (TypeError, ValueError):
            pass

    final_gate = context.get("final_gate") or {}
    if isinstance(final_gate, dict):
        text = " ".join(str(final_gate.get(key) or "") for key in ("final_action", "action", "summary", "reason"))
        if "0%不参与" in text or "禁止参与" in text or "不新增参与" in text:
            return True
        if final_gate.get("can_new_entry") is False and str(final_gate.get("operation_state") or "") in {"撤退态", "观察态"}:
            return True
    return False


def build_step0_follow_reminder_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    if _zero_participation_context(context):
        reminder = "> **⚠️ 重要提醒**: Step 0 不再单独猜市场，而是直接引用统一市场研究快照；明日不新增参与，只观察风险是否钝化、主攻线承接，结果进入复盘和下一份日报判断。"
    else:
        execution_clause = execution_clause_for_position_pct(resolve_target_position_pct(context))
        reminder = f"> **⚠️ 重要提醒**: Step 0 不再单独猜市场，而是直接引用统一市场研究快照；明日按竞价表态、开盘前几分钟承接、打板/回封、09:50-10:10窗口处理；{execution_clause}；买入后按失效价和单笔-5%底线处理风险。"
    return {
        "lines": [reminder],
        "exports": {},
        "module_logs": [],
    }


def build_step0_follow_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["", ""], "exports": {}, "module_logs": []}
