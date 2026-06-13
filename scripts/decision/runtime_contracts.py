from daily_report_analysis_utils import (
    _is_degraded_abnormal_snapshot,
    normalize_stock_code,
    sector_name_matches,
)


def get_trade_permission_contract(
    stock,
    mainline_name="",
    conviction_codes=None,
    leader_memory_codes=None,
    final_gate=None,
    state_machine_snapshot=None,
    weak_to_strong_context=None,
):
    """Pure permission contract builder extracted from the monolith entry file."""
    stock = stock or {}
    conviction_codes = conviction_codes or set()
    leader_memory_codes = leader_memory_codes or set()
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    weak_to_strong_context = weak_to_strong_context or {}

    if _is_degraded_abnormal_snapshot(stock) or bool(stock.get("abnormal_is_degraded_snapshot")):
        return {
            "can_execute": False,
            "permission_label": "降级观察权",
            "permission_reason": "当前只有降级异常快照，不能进入正式执行层",
            "priority": 0,
        }

    code = normalize_stock_code(stock.get("code", ""))
    sector = str(stock.get("sector", "") or "").strip()
    abnormal_state = str(stock.get("abnormal_follow_state", "") or "").strip()
    watch_source = str(stock.get("watch_source", "") or "").strip()
    is_mainline = bool(mainline_name and sector_name_matches(sector, mainline_name))
    is_conviction = code in conviction_codes
    is_memory = code in leader_memory_codes

    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    pulse_stage = str(state_machine_snapshot.get("pulse_stage", "") or "").strip()
    pulse_action_reason = str(state_machine_snapshot.get("pulse_action_reason", "") or "").strip()
    pulse_action_bias = str(state_machine_snapshot.get("pulse_action_bias", "") or "").strip()
    if not execution_bias and not final_gate.get("can_new_entry", True):
        execution_bias = "watch_only"
    if not pulse_action_reason and execution_bias == "watch_only":
        pulse_action_reason = "环境条件尚未正式满足，先观察，不提前把研究写成执行。"

    def _watch_label():
        if is_conviction:
            return "重点观察权"
        if is_memory:
            return "龙头观察权"
        if is_mainline:
            return "主线观察权"
        return "普通观察权"

    def _watch_permission(reason, priority=None, label=None):
        if priority is None:
            priority = 1 if (is_conviction or is_memory or is_mainline) else 0
        return {
            "can_execute": False,
            "permission_label": label or _watch_label(),
            "permission_reason": reason,
            "priority": priority,
        }

    if watch_source == "gem_breathing_20cm":
        gem_reason = "先看创业板20cm预启动能否走成右侧确认，并只在固定交易窗口内评估50%条件执行；普通结构只看09:50-10:10窗口，不满足继续0%不参与。"
        if pulse_action_reason:
            gem_reason = f"{pulse_action_reason}；{gem_reason}"
        if not is_mainline and mainline_name:
            gem_reason = f"当前主线是{mainline_name}，这只20cm样本先只保留侧翼观察；{gem_reason}"
        return _watch_permission(
            gem_reason,
            priority=1 if is_mainline else 0,
            label="创业板20cm预启动观察权",
        )

    if weak_to_strong_context.get("active") and execution_bias in ("watch_only", "prep_only", "divergence_only"):
        weak_reason = "主线弱转强样本：第一波强势基础仍在，当前是假弱非真弱；先保留固定交易窗口预案，按09:30-09:35、09:50-10:10或14:30-14:55三段窗口评估50%条件执行。"
        if execution_bias == "divergence_only":
            weak_reason = f"{weak_reason}当前只做分歧承接，不直接追一致加速。"
        if pulse_action_reason:
            weak_reason = f"{pulse_action_reason}；{weak_reason}"
        return _watch_permission(
            weak_reason,
            priority=2,
            label="主线弱转强执行预备态",
        )

    if abnormal_state == "已经转弱":
        return {
            "can_execute": False,
            "permission_label": "禁止出手",
            "permission_reason": "异动后已经转弱，取消买入资格",
            "priority": 0,
        }

    if abnormal_state == "新异动待观察":
        return _watch_permission("异动刚出现，先看是否跌得下去", priority=1 if is_conviction else 0)

    if execution_bias == "prep_only" and abnormal_state in ("跌不下去", "缩量消化") and (is_mainline or is_memory or is_conviction):
        prep_prefix = "重点观察" if is_conviction else "龙头" if is_memory and not is_mainline else "主线"
        prep_reason = pulse_action_reason or "环境未开，但主线已经进入可跟踪分歧段；只有次日固定交易窗口内条件成立后才可升级为唯一执行候选。"
        if "固定交易窗口" not in prep_reason:
            prep_reason = f"{prep_reason}；只有次日固定交易窗口内条件成立后才可升级为唯一执行候选。"
        return {
            "can_execute": False,
            "permission_label": f"{prep_prefix}条件执行预备态",
            "permission_reason": prep_reason,
            "priority": 2 if is_conviction else 1,
        }

    if execution_bias in ("avoid", "reduce_only", "watch_only"):
        base_reason = pulse_action_reason or "当前阶段只允许观察，不给买入资格。"
        if pulse_stage:
            base_reason = f"当前主线处于{pulse_stage}，{base_reason}"
        if pulse_action_bias == "只减不加" and "钝化" not in base_reason and pulse_stage == "钝化":
            base_reason = f"当前主线脉冲已钝化，{base_reason}"
        return _watch_permission(base_reason)

    if execution_bias == "divergence_only" and abnormal_state not in ("跌不下去", "缩量消化"):
        reason = pulse_action_reason or "当前只做分歧承接，没有承接证据前只能观察。"
        if pulse_stage:
            reason = f"当前主线处于{pulse_stage}，{reason}"
        return _watch_permission(reason)

    if is_conviction:
        reason = "重点观察名单，且承接未坏"
        if abnormal_state == "跌不下去":
            reason = "重点观察名单 + 异动后跌不下去，允许进入执行层"
        elif abnormal_state == "缩量消化":
            reason = "重点观察名单 + 缩量消化，允许按固定交易窗口确认"
        if execution_bias == "divergence_only":
            reason = f"{reason}；但当前只做分歧承接，不追一致加速"
        return {
            "can_execute": True,
            "permission_label": "重点观察确认资格",
            "permission_reason": reason,
            "priority": 3,
        }

    if abnormal_state == "跌不下去" and (is_memory or is_mainline):
        reason = "主线/龙头锚定股异动后跌不下去，允许进入执行层"
        if execution_bias == "divergence_only":
            reason = f"{reason}；当前只允许分歧承接，不做一致加速追价"
        return {
            "can_execute": True,
            "permission_label": "主线买入资格" if is_mainline else "龙头回看买入资格",
            "permission_reason": reason,
            "priority": 2,
        }

    if abnormal_state == "缩量消化" and (is_memory or is_mainline):
        reason = "正在缩量消化，先保留观察权，等再转强"
        if execution_bias == "divergence_only":
            reason = f"{reason}；当前阶段只接受分歧承接后的确认，不直接追价"
        return {
            "can_execute": False,
            "permission_label": "主线观察权" if is_mainline else "龙头观察权",
            "permission_reason": reason,
            "priority": 1,
        }

    if is_memory:
        return {
            "can_execute": False,
            "permission_label": "龙头观察权",
            "permission_reason": "属于龙头记忆库，但承接条件还不够",
            "priority": 1,
        }

    if is_mainline:
        return {
            "can_execute": False,
            "permission_label": "主线观察权",
            "permission_reason": "在主线里，但未进入重点观察名单或记忆库执行层",
            "priority": 1,
        }

    return {
        "can_execute": False,
        "permission_label": "普通观察权",
        "permission_reason": "非主线核心，不给买入资格",
        "priority": 0,
    }


def resolve_environment_display_contract(position_level="", final_gate=None, state_machine_snapshot=None):
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    display_position_level = str(position_level or final_gate.get("position_level", "") or "").strip() or "50%条件执行"
    display_operation_state = str(final_gate.get("operation_state", "") or state_machine_snapshot.get("operation_state", "") or "观察态").strip()
    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    energy_state = str(state_machine_snapshot.get("energy_state", "") or "").strip()
    headline = "环境条件满足不等于立刻下单，先看特殊标的，再等市场缩到唯一对象"

    if display_position_level == "0%不参与" or execution_bias == "avoid" or display_operation_state == "撤退态":
        display_position_level = "0%不参与"
        display_operation_state = "撤退态"
        headline = "环境关闭，只做等待，不做新增参与"
    elif execution_bias == "prep_only":
        display_position_level = "50%条件执行"
        display_operation_state = "防守态"
        headline = "先看环境，再决定是否保留观察权/旧仓处理权"
    elif execution_bias in ("watch_only", "divergence_only", "reduce_only"):
        display_position_level = "0%不参与"
        display_operation_state = "防守态"
        headline = "先看环境，再决定是否保留观察权/旧仓处理权"
    elif energy_state == "收缩防守" and display_position_level != "0%不参与":
        display_position_level = "0%不参与"
        display_operation_state = "防守态"
        headline = "先看环境，再决定是否保留观察权/旧仓处理权"
    elif execution_bias == "allow_execute" and final_gate.get("can_new_entry"):
        display_position_level = display_position_level or "50%条件执行"
        display_operation_state = display_operation_state or "进攻态"

    return {
        "position_level": display_position_level,
        "operation_state": display_operation_state,
        "headline": headline,
    }


def resolve_environment_reason_contract(position_reason="", environment_display=None, state_machine_snapshot=None):
    environment_display = environment_display or {}
    state_machine_snapshot = state_machine_snapshot or {}
    position_reason = str(position_reason or "").strip()
    headline = str(environment_display.get("headline", "") or "").strip()
    display_position_level = str(environment_display.get("position_level", "") or "").strip()
    display_operation_state = str(environment_display.get("operation_state", "") or "").strip()
    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    energy_state = str(state_machine_snapshot.get("energy_state", "") or "").strip()
    state_reason = str(state_machine_snapshot.get("state_reason", "") or "").strip()

    if display_position_level == "0%不参与" or execution_bias == "avoid" or display_operation_state == "撤退态":
        parts = [
            part
            for part in (
                headline or "环境关闭，只做等待，不做新增参与",
                energy_state or "收缩防守",
                state_reason,
                "顶层环境以执行条件为准，不再沿用旧的偏多口径。",
            )
            if part
        ]
        return "；".join(parts)
    if display_position_level == "50%条件执行" and execution_bias == "prep_only":
        parts = [
            part
            for part in (
                headline or "先看环境，再决定是否保留观察权/旧仓处理权",
                energy_state or "收缩防守",
                state_reason or position_reason,
            )
            if part
        ]
        return "；".join(parts)
    return position_reason or state_reason or headline
