from __future__ import annotations

__all__ = ["build_entry_cycle_stop_policy", "resolve_entry_cycle_profile"]


DEFAULT_ENTRY_CYCLE_STOP_PROFILES = {
    "002975": {"recommended_stop_mode": "structure_band"},
    "603906": {"recommended_stop_mode": "structure_band"},
    "000889": {"recommended_stop_mode": "structure_repair_band"},
    "603026": {"recommended_stop_mode": "time_stop_or_downgrade"},
    "000791": {"recommended_stop_mode": "reclaim_failure_exit"},
    "600488": {"recommended_stop_mode": "a_kill_exit"},
}


STOP_MODE_LABELS = {
    "structure_repair_band": "结构修复带",
    "structure_band": "结构容忍带",
    "reclaim_failure_exit": "关键区失败降级",
    "a_kill_exit": "A杀出清",
    "time_stop_or_downgrade": "时间止损/降级",
}


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _round_or_none(value, digits=2):
    value = _safe_float(value, 0.0)
    if value <= 0:
        return None
    return round(value, digits)


def _normalize_stock_code(code):
    return (
        str(code or "")
        .replace(".SZ", "")
        .replace(".SH", "")
        .replace(".SS", "")
        .replace("sz", "")
        .replace("sh", "")
        .strip()
    )


def resolve_entry_cycle_profile(stock_code="", explicit_profile=None):
    if explicit_profile:
        return dict(explicit_profile)
    code = _normalize_stock_code(stock_code)
    return dict(DEFAULT_ENTRY_CYCLE_STOP_PROFILES.get(code, {}))


def build_entry_cycle_stop_policy(entry_price, base_stop_plan=None, entry_cycle_profile=None):
    base_stop_plan = base_stop_plan or {}
    entry_cycle_profile = entry_cycle_profile or {}
    recommended_mode = str(entry_cycle_profile.get("recommended_stop_mode", "") or "").strip()
    if not recommended_mode:
        return {}

    execution_stop = _round_or_none(base_stop_plan.get("effective_stop"))
    risk_floor = _round_or_none(base_stop_plan.get("hard_stop"))
    if risk_floor is None:
        entry = _safe_float(entry_price, 0.0)
        risk_floor = round(entry * 0.95, 2) if entry > 0 else None

    if recommended_mode == "structure_repair_band":
        return {
            "recommended_stop_mode": recommended_mode,
            "stop_mode_label": STOP_MODE_LABELS[recommended_mode],
            "primary_exit_mode": STOP_MODE_LABELS[recommended_mode],
            "hard_stop_role": "风险底线，不是观察淘汰线",
            "execution_stop": execution_stop,
            "risk_floor": risk_floor,
            "display_rule": "观察期看收盘修复和后续再突破；买入后按30分钟结构执行。",
            "report_action_text": "先看修复/再突破，固定-5%只作为风险底线。",
        }

    if recommended_mode == "reclaim_failure_exit":
        return {
            "recommended_stop_mode": recommended_mode,
            "stop_mode_label": STOP_MODE_LABELS[recommended_mode],
            "primary_exit_mode": STOP_MODE_LABELS[recommended_mode],
            "hard_stop_role": "风险底线，不是观察淘汰线",
            "execution_stop": execution_stop,
            "risk_floor": risk_floor,
            "display_rule": "关键区没有站稳先降级，不是继续等待-5%。",
            "report_action_text": "关键区失败就降级，不把未触发-5%当成继续持有理由。",
        }

    if recommended_mode == "a_kill_exit":
        return {
            "recommended_stop_mode": recommended_mode,
            "stop_mode_label": STOP_MODE_LABELS[recommended_mode],
            "primary_exit_mode": STOP_MODE_LABELS[recommended_mode],
            "hard_stop_role": "风险底线，不是观察淘汰线",
            "execution_stop": execution_stop,
            "risk_floor": risk_floor,
            "display_rule": "出现结构失真先出清，固定-5%只是滞后的风险提示。",
            "report_action_text": "按A杀/结构失真处理，不继续按趋势票处理。",
        }

    if recommended_mode == "time_stop_or_downgrade":
        return {
            "recommended_stop_mode": recommended_mode,
            "stop_mode_label": STOP_MODE_LABELS[recommended_mode],
            "primary_exit_mode": STOP_MODE_LABELS[recommended_mode],
            "hard_stop_role": "风险底线，不是观察淘汰线",
            "execution_stop": execution_stop,
            "risk_floor": risk_floor,
            "display_rule": "迟迟不脱离震荡就降级，重点控制机会成本。",
            "report_action_text": "按时间止损/降级处理，不继续按趋势票处理。",
        }

    return {
        "recommended_stop_mode": recommended_mode,
        "stop_mode_label": STOP_MODE_LABELS.get(recommended_mode, "结构容忍带"),
        "primary_exit_mode": STOP_MODE_LABELS.get(recommended_mode, "结构容忍带"),
        "hard_stop_role": "风险底线，不是观察淘汰线",
        "execution_stop": execution_stop,
        "risk_floor": risk_floor,
        "display_rule": "买入后按结构止损执行，固定-5%只作为风险底线。",
        "report_action_text": "按结构止损执行，不用固定-5%替代介入周期判断。",
    }
