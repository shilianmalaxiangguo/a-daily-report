from __future__ import annotations

from selection.candidate_trace_contracts import build_candidate_trace


ACTION_CEILINGS = ("主买", "补位", "核心观察", "修复观察", "不参与")
_ACTION_RANK = {name: index for index, name in enumerate(ACTION_CEILINGS)}


def _candidate_label(candidate):
    candidate = candidate or {}
    name = str(candidate.get("name") or candidate.get("名称") or "").strip()
    code = str(candidate.get("code") or candidate.get("代码") or "").strip()
    if name and code:
        return f"{name}({code})"
    return name or code or "暂无"


def _join_texts(values):
    return "；".join(str(value) for value in _as_list(values) if value not in (None, ""))


def _format_items(items):
    if not items:
        return ""
    texts = []
    for item in items:
        if isinstance(item, dict):
            item_type = str(item.get("类型") or item.get("type") or "").strip()
            evidence = str(item.get("证据") or item.get("evidence") or "").strip()
            if item_type and evidence:
                texts.append(f"{item_type}：{evidence}")
            elif item_type or evidence:
                texts.append(item_type or evidence)
        else:
            texts.append(str(item))
    return "；".join(text for text in texts if text)


def _format_outcome(outcome):
    if not outcome:
        return ""
    if isinstance(outcome, dict):
        return "；".join(f"{key}：{value}" for key, value in outcome.items() if value not in (None, ""))
    return str(outcome)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]
    return [item for item in values if item not in (None, "")]


def _has_marker(values, marker):
    return any(marker in str(value) for value in _as_list(values))


def _as_number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_limit_number(value):
    numeric = _as_number(value)
    if numeric.is_integer():
        return int(numeric)
    return numeric


def _position_nature(candidate):
    explicit = candidate.get("position_nature", candidate.get("仓位性质"))
    if explicit not in (None, ""):
        return explicit
    current_position = _as_number(candidate.get("current_position_shares", candidate.get("当前持仓", 0)))
    return "已有仓" if current_position > 0 else "无仓"


def _stock_code(candidate):
    text = str(candidate.get("code") or candidate.get("代码") or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _stock_name(candidate):
    candidate = candidate or {}
    return str(candidate.get("name") or candidate.get("名称") or "").strip()


def _candidate_tier(candidate):
    candidate = candidate or {}
    return str(candidate.get("tier") or candidate.get("层级") or "").strip()


def _branch_path_text(*parts):
    return "；".join(str(part).strip() for part in parts if str(part or "").strip())


def _format_lot_amount(value):
    amount = _as_number(value)
    if amount <= 0:
        return ""
    rounded = round(amount)
    if abs(amount - rounded) < 0.01:
        return str(int(rounded))
    return f"{amount:.2f}"


def _parse_pct(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if "半仓" in text:
            return 50.0
        if "满仓" in text:
            return 100.0
        if "空仓" in text or "不参与" in text:
            return 0.0
        text = text.replace("%", "").replace("％", "").strip()
        return _as_number(text)
    return _as_number(value)


def _format_pct(value):
    if value is None:
        return ""
    numeric = _as_number(value)
    rounded = round(numeric, 1)
    if abs(rounded - int(rounded)) < 0.01:
        return f"{int(rounded)}%"
    return f"{rounded:.1f}%"


def _format_pct_delta(value):
    rounded = round(abs(_as_number(value)), 1)
    if abs(rounded - int(rounded)) < 0.01:
        return str(int(rounded))
    return f"{rounded:.1f}"


def _resolve_target_position_pct(candidate):
    candidate = candidate or {}
    for key in ("target_position_pct", "planned_position_pct", "计划仓位档", "计划仓位", "仓位档"):
        parsed = _parse_pct(candidate.get(key))
        if parsed is not None:
            return parsed
    return None


def _account_base_cash(candidate):
    candidate = candidate or {}
    for key in ("account_equity", "账户本金", "账户总资金", "available_cash", "可用资金", "account_cash", "账户资金"):
        cash = _as_number(candidate.get(key))
        if cash > 0:
            return cash
    return 0.0


def _resolve_actual_position_pct(candidate, target_position_pct):
    candidate = candidate or {}
    for key in ("actual_position_pct", "实际仓位", "actual_position", "当前仓位"):
        parsed = _parse_pct(candidate.get(key))
        if parsed is not None:
            return parsed

    latest_price = _as_number(candidate.get("latest_price", candidate.get("最新价", candidate.get("price", 0))))
    account_cash = _account_base_cash(candidate)
    current_position = _as_number(candidate.get("current_position_shares", candidate.get("当前持仓", 0)))
    if current_position > 0 and latest_price > 0 and account_cash > 0:
        return current_position * latest_price / account_cash * 100

    if target_position_pct is None:
        return None
    if target_position_pct <= 0:
        return 0.0
    if latest_price <= 0 or account_cash <= 0:
        return None

    lot_amount = latest_price * 100
    if lot_amount <= 0 or lot_amount > account_cash:
        return 0.0

    target_amount = account_cash * target_position_pct / 100
    lots = int(target_amount // lot_amount)
    if lots <= 0:
        lots = 1
    return min(lots * lot_amount / account_cash * 100, 100.0)


def _position_deviation_text(candidate, target_position_pct, actual_position_pct):
    if target_position_pct is None or actual_position_pct is None:
        return ""
    if target_position_pct <= 0:
        return "不参与"
    if actual_position_pct <= 0:
        return "一手超过可用资金，实际不可买"

    delta = actual_position_pct - target_position_pct
    if abs(delta) < 0.1:
        return "匹配计划档"

    direction = "超配" if delta > 0 else "低配"
    detail = f"一手颗粒度{direction}{_format_pct_delta(delta)}pct"
    if abs(target_position_pct - 50) < 0.1 and 40 <= actual_position_pct <= 60:
        return f"{detail}，仍按半仓档"
    return detail


def _resolve_account_trade_status(candidate):
    candidate = candidate or {}
    explicit = str(candidate.get("account_trade_status") or candidate.get("账户状态") or "").strip()
    if explicit in ("实际可买", "实际不可买"):
        return explicit, str(candidate.get("account_trade_reason") or candidate.get("账户状态原因") or "").strip()

    code = _stock_code(candidate)
    latest_price = _as_number(candidate.get("latest_price", candidate.get("最新价", candidate.get("price", 0))))
    available_cash = _as_number(
        candidate.get(
            "available_cash",
            candidate.get("可用资金", candidate.get("account_cash", candidate.get("账户资金", 0))),
        )
    )
    can_trade_star_market = bool(
        candidate.get("can_trade_star_market", candidate.get("可买科创板", candidate.get("科创板可买", False)))
    )
    reasons = []

    if code.startswith("688") and not can_trade_star_market:
        reasons.append("688不适配")

    lot_amount = latest_price * 100 if latest_price > 0 else 0
    if available_cash > 0 and lot_amount > available_cash:
        reasons.append(f"一手约{_format_lot_amount(lot_amount)}，超过可用资金{_format_lot_amount(available_cash)}")

    if reasons:
        return "实际不可买", "；".join(reasons)
    return "实际可买", "账户条件适配"


def build_daily_quality_decision_panel(
    *,
    market_emotion_label="",
    account_attention_load="",
    holding_priority_action="",
    daily_new_entry_limit=0,
    primary_buy_candidate=None,
    backup_candidate=None,
    forbidden_actions=None,
    ignored_noise_items=None,
):
    visible_fields = {
        "市场情绪状态": market_emotion_label,
        "账户后台任务负担": account_attention_load,
        "持仓优先动作": holding_priority_action,
        "今日新增上限": daily_new_entry_limit,
        "主买对象": _candidate_label(primary_buy_candidate),
        "补位对象": _candidate_label(backup_candidate),
        "禁止动作": _join_texts(forbidden_actions),
        "忽略清单": _join_texts(ignored_noise_items),
    }
    return {
        "visible_fields": visible_fields,
        "data": {
            "market_emotion_label": market_emotion_label,
            "account_attention_load": account_attention_load,
            "holding_priority_action": holding_priority_action,
            "daily_new_entry_limit": daily_new_entry_limit,
            "primary_buy_candidate": primary_buy_candidate,
            "backup_candidate": backup_candidate,
            "forbidden_actions": _as_list(forbidden_actions),
            "ignored_noise_items": _as_list(ignored_noise_items),
        },
    }


def build_candidate_quality_contract(
    candidate,
    *,
    selection_quality_label="",
    entry_quality_label="",
    action_ceiling="不参与",
    risk_items=None,
    cost_items=None,
    holding_action="",
    new_entry_action="",
    recovery_conditions=None,
    removal_conditions=None,
    latest_review_at="",
    worst_case_plan=None,
    current_upside_engine="",
    recognition_text="",
    trend_aesthetic_text="",
    price_behavior_text="",
    one_sentence_discipline="",
):
    if action_ceiling not in ACTION_CEILINGS:
        raise ValueError(f"unknown action ceiling: {action_ceiling}")

    candidate = candidate or {}
    risk_items = _as_list(risk_items)
    cost_items = _as_list(cost_items)
    recovery_conditions = _as_list(recovery_conditions)
    removal_conditions = _as_list(removal_conditions)
    worst_case_plan = worst_case_plan or {}
    current_position = _as_limit_number(candidate.get("current_position_shares", candidate.get("当前持仓", 0)))
    sellable = _as_limit_number(candidate.get("sellable_shares", candidate.get("可卖数量", 0)))
    locked = _as_limit_number(candidate.get("locked_shares", candidate.get("不可卖数量", 0)))
    account_trade_status, account_trade_reason = _resolve_account_trade_status(candidate)
    target_position_pct = _resolve_target_position_pct(candidate)
    actual_position_pct = _resolve_actual_position_pct(candidate, target_position_pct)
    position_deviation = _position_deviation_text(candidate, target_position_pct, actual_position_pct)

    visible_row = {
        "候选": _candidate_label(candidate),
        "当前持仓": current_position,
        "可卖数量": sellable,
        "不可卖数量": locked,
        "仓位性质": _position_nature(candidate),
        "账户状态": account_trade_status,
        "计划仓位档": _format_pct(target_position_pct),
        "实际仓位": _format_pct(actual_position_pct),
        "仓位偏离": position_deviation,
        "周期身份": candidate.get("cycle_identity", candidate.get("周期身份", "")),
        "选股质量": selection_quality_label,
        "买点质量": entry_quality_label,
        "风险项": _format_items(risk_items),
        "成本项": _format_items(cost_items),
        "动作上限": action_ceiling,
        "持仓动作": holding_action,
        "新开仓动作": new_entry_action,
        "恢复条件": _join_texts(recovery_conditions),
        "取关条件": _join_texts(removal_conditions),
        "最晚复核": latest_review_at,
    }
    single_stock_fields = {
        "当前上涨发动机": current_upside_engine,
        "市场辨识度": recognition_text,
        "趋势审美": trend_aesthetic_text,
        "价格行为与承接": price_behavior_text,
        "选股质量": selection_quality_label,
        "买点质量": entry_quality_label,
        "账户状态": account_trade_status,
        "计划仓位档": visible_row["计划仓位档"],
        "实际仓位": visible_row["实际仓位"],
        "仓位偏离": position_deviation,
        "风险项": visible_row["风险项"],
        "成本项": visible_row["成本项"],
        "动作上限": action_ceiling,
        "持仓动作": holding_action,
        "新开仓动作": new_entry_action,
        "恢复条件": visible_row["恢复条件"],
        "取关条件": visible_row["取关条件"],
        "最坏情境": worst_case_plan.get("最坏情境", ""),
        "触发条件": worst_case_plan.get("触发条件", ""),
        "应对动作": worst_case_plan.get("应对动作", ""),
        "一句话纪律": one_sentence_discipline,
    }
    trace_candidate = {
        **candidate,
        "action_ceiling": action_ceiling,
        "account_trade_status": account_trade_status,
        "account_trade_reason": account_trade_reason,
        "new_entry_action": new_entry_action,
        "final_action": candidate.get("final_action") or new_entry_action,
        "trigger_condition": candidate.get("trigger_condition") or worst_case_plan.get("触发条件", ""),
        "failure_condition": candidate.get("failure_condition") or visible_row["取关条件"],
    }
    trace = build_candidate_trace(trace_candidate)

    return {
        "visible_row": visible_row,
        "single_stock_fields": single_stock_fields,
        "trace": trace,
        "data": {
            "candidate": dict(candidate),
            "trace": trace,
            "selection_quality_label": selection_quality_label,
            "entry_quality_label": entry_quality_label,
            "risk_items": risk_items,
            "cost_items": cost_items,
            "action_ceiling": action_ceiling,
            "holding_action": holding_action,
            "new_entry_action": new_entry_action,
            "recovery_conditions": recovery_conditions,
            "removal_conditions": removal_conditions,
            "latest_review_at": latest_review_at,
            "worst_case_plan": dict(worst_case_plan),
            "account_trade_status": account_trade_status,
            "account_trade_reason": account_trade_reason,
            "target_position_pct": target_position_pct,
            "actual_position_pct": actual_position_pct,
            "position_deviation": position_deviation,
            "trace": trace,
        },
    }


def evaluate_candidate_quality_sample(candidate):
    candidate = candidate or {}
    risk_flags = _as_list(candidate.get("risk_flags"))
    cost_flags = _as_list(candidate.get("cost_flags"))
    selection_quality = str(candidate.get("selection_quality") or "").strip() or "中"
    entry_cost_state = str(candidate.get("entry_cost_state") or "").strip()
    quality_role = str(candidate.get("quality_role") or "").strip()
    is_core = bool(candidate.get("is_core"))
    current_position = _as_number(candidate.get("current_position_shares", 0))
    sellable = _as_number(candidate.get("sellable_shares", 0))
    locked = _as_number(candidate.get("locked_shares", 0))
    trend_context = str(candidate.get("trend_context") or "")
    account_trade_status, account_trade_reason = _resolve_account_trade_status(candidate)

    action_ceiling = "补位"
    entry_quality_label = "等确认"
    holding_action = "无仓"
    new_entry_action = "等触发条件成立"
    reasons = []

    if current_position > 0:
        holding_action = f"已有仓按失效线处理，可卖{sellable:g}，不可卖{locked:g}"

    if quality_role == "主买对象":
        action_ceiling = "主买"
        new_entry_action = "按触发条件成立后参与"
        reasons.append("主买对象，风险和成本未触发降级时保留主买")
    elif quality_role == "核心观察":
        action_ceiling = "核心观察"
        new_entry_action = "不新增参与，等待恢复条件"
        reasons.append("今日新增上限未打开，主对象只保留核心观察")

    if selection_quality == "高" and entry_cost_state == "高成本":
        action_ceiling = "核心观察"
        entry_quality_label = "不舒服"
        new_entry_action = "不追高，等回踩确认"
        reasons.append("好票高成本，保护选股资格但不追高")

    if selection_quality == "低" and entry_cost_state == "低成本":
        action_ceiling = "不参与"
        entry_quality_label = "看似便宜"
        new_entry_action = "不新增参与，MA/VWAP只作已有仓处理参考"
        reasons.append("差票低成本，不能因为位置便宜获得新增资格")

    if candidate.get("engine_clarified") or _has_marker(risk_flags, "上涨发动机被澄清"):
        if is_core and selection_quality == "高":
            action_ceiling = "核心观察"
            new_entry_action = "不主买，等待发动机重新被资金确认"
        else:
            action_ceiling = "不参与"
            new_entry_action = "不新增参与"
        reasons.append("发动机澄清，当前上涨理由被伤到")

    if current_position and "MA/VWAP" in trend_context and action_ceiling not in ("不参与", "核心观察"):
        action_ceiling = "修复观察"
        new_entry_action = "不新增参与，先按持仓节奏处理"
        reasons.append("持仓节奏必须结合趋势、MA/VWAP和可卖数量")

    if _has_marker(risk_flags, "风险信息缺失") and action_ceiling != "不参与":
        action_ceiling = "修复观察"
        reasons.append("风险信息缺失，不能主买")

    if _has_marker(cost_flags, "远离MA/VWAP") and action_ceiling == "主买":
        action_ceiling = "补位"
        reasons.append("远离MA/VWAP，成本项限制动作")

    if account_trade_status == "实际不可买":
        new_entry_action = "账户条件不适配，只观察强度，不参与"
        reasons.append(account_trade_reason)

    return {
        "selection_quality_label": selection_quality,
        "entry_quality_label": entry_quality_label,
        "action_ceiling": action_ceiling,
        "holding_action": holding_action,
        "new_entry_action": new_entry_action,
        "risk_items": [{"类型": "风险项", "证据": str(flag)} for flag in risk_flags],
        "cost_items": [{"类型": "成本项", "证据": str(flag)} for flag in cost_flags],
        "decision_reason": "；".join(reasons),
    }


def evaluate_candidate_quality_sample_contract(candidate):
    evaluation = evaluate_candidate_quality_sample(candidate)
    return build_candidate_quality_contract(
        candidate,
        selection_quality_label=evaluation["selection_quality_label"],
        entry_quality_label=evaluation["entry_quality_label"],
        action_ceiling=evaluation["action_ceiling"],
        risk_items=evaluation["risk_items"],
        cost_items=evaluation["cost_items"],
        holding_action=evaluation["holding_action"],
        new_entry_action=evaluation["new_entry_action"],
        one_sentence_discipline=evaluation["decision_reason"],
    )


def _movement_direction(previous_action, intraday_action):
    if intraday_action == previous_action:
        return "保持"
    if _ACTION_RANK[intraday_action] < _ACTION_RANK[previous_action]:
        return "上调"
    return "下调"


def _build_intraday_action_result(previous_action, intraday_action, reason, daily_new_entry_limit):
    visible_fields = {
        "前一晚动作层级": previous_action,
        "盘中动作": intraday_action,
        "变化方向": _movement_direction(previous_action, intraday_action),
        "是否允许新增": "是" if intraday_action in ("主买", "补位") and daily_new_entry_limit > 0 else "否",
        "原因": reason,
        "处理动作": "允许按触发条件新增参与" if intraday_action in ("主买", "补位") and daily_new_entry_limit > 0 else "不新增参与，按原计划观察或处理持仓",
    }
    return {
        "visible_fields": visible_fields,
        "data": {
            "previous_action": previous_action,
            "intraday_action": intraday_action,
            "movement": visible_fields["变化方向"],
            "new_entry_allowed": visible_fields["是否允许新增"] == "是",
            "reason": reason,
            "daily_new_entry_limit": daily_new_entry_limit,
        },
    }


def resolve_intraday_action_update(
    previous_action_ceiling,
    *,
    daily_new_entry_limit=0,
    recovery_hit=False,
    removal_triggered=False,
    risk_clean=False,
    sector_sync=False,
    reclaimed_vwap_or_ma=False,
    volume_healthy=False,
    strong_line_reclaimed=False,
    sector_returned=False,
    risk_repaired=False,
    primary_failed=False,
    strongest_same_mainline=False,
    comfortable_entry=False,
):
    if previous_action_ceiling not in ACTION_CEILINGS:
        raise ValueError(f"unknown action ceiling: {previous_action_ceiling}")

    daily_new_entry_limit = _as_limit_number(daily_new_entry_limit)

    if removal_triggered:
        return _build_intraday_action_result(
            previous_action_ceiling,
            "不参与",
            "取关条件触发，原观察失败，先停止新增参与",
            daily_new_entry_limit,
        )

    if daily_new_entry_limit <= 0:
        return _build_intraday_action_result(
            previous_action_ceiling,
            previous_action_ceiling,
            "今日新增上限为0，盘中不做新增升级",
            daily_new_entry_limit,
        )

    if previous_action_ceiling == "不参与":
        return _build_intraday_action_result(
            previous_action_ceiling,
            "不参与",
            "前一晚为不参与，盘中不能直接升为主买或补位",
            daily_new_entry_limit,
        )

    if previous_action_ceiling == "修复观察":
        if strong_line_reclaimed and sector_returned and risk_repaired:
            return _build_intraday_action_result(
                previous_action_ceiling,
                "核心观察",
                "重新站回强弱线，板块回流，风险项修复，只能先升为核心观察",
                daily_new_entry_limit,
            )
        return _build_intraday_action_result(
            previous_action_ceiling,
            "修复观察",
            "修复条件未完整命中，继续修复观察",
            daily_new_entry_limit,
        )

    if previous_action_ceiling == "核心观察":
        if risk_clean and sector_sync and reclaimed_vwap_or_ma and volume_healthy and recovery_hit:
            return _build_intraday_action_result(
                previous_action_ceiling,
                "补位",
                "风险干净、板块同步、VWAP/MA收回、量能健康，恢复条件命中",
                daily_new_entry_limit,
            )
        return _build_intraday_action_result(
            previous_action_ceiling,
            "核心观察",
            "核心观察升级条件未完整命中",
            daily_new_entry_limit,
        )

    if previous_action_ceiling == "补位":
        if primary_failed and strongest_same_mainline and comfortable_entry:
            return _build_intraday_action_result(
                previous_action_ceiling,
                "主买",
                "主买对象失格，该票成为同主线最强替代，且买点仍舒服",
                daily_new_entry_limit,
            )
        return _build_intraday_action_result(
            previous_action_ceiling,
            "补位",
            "补位升级主买条件未完整命中",
            daily_new_entry_limit,
        )

    return _build_intraday_action_result(
        previous_action_ceiling,
        "主买",
        "前一晚已经是主买，盘中只按触发条件执行",
        daily_new_entry_limit,
    )


def build_candidate_quality_review_record(
    *,
    sample_date,
    candidate,
    market_emotion_label="",
    selection_quality_snapshot="",
    entry_quality_snapshot="",
    risk_items_snapshot=None,
    cost_items_snapshot=None,
    action_ceiling_snapshot="不参与",
    holding_action_snapshot="",
    new_entry_action_snapshot="",
    actual_outcome=None,
    entry_window_result="",
    user_deviation="",
    error_category="",
    improvement_owner="",
    sample_protection_result="",
):
    if action_ceiling_snapshot not in ACTION_CEILINGS:
        raise ValueError(f"unknown action ceiling: {action_ceiling_snapshot}")

    risk_items_snapshot = _as_list(risk_items_snapshot)
    cost_items_snapshot = _as_list(cost_items_snapshot)
    visible_fields = {
        "样本日期": sample_date,
        "样本": _candidate_label(candidate),
        "当时市场情绪": market_emotion_label,
        "当时选股质量": selection_quality_snapshot,
        "当时买点质量": entry_quality_snapshot,
        "当时风险项": _format_items(risk_items_snapshot),
        "当时成本项": _format_items(cost_items_snapshot),
        "当时动作上限": action_ceiling_snapshot,
        "当时持仓动作": holding_action_snapshot,
        "当时新开仓动作": new_entry_action_snapshot,
        "实际走势": _format_outcome(actual_outcome),
        "买点是否出现": entry_window_result,
        "用户是否偏离": user_deviation,
        "错误原因": error_category,
        "改进归因": improvement_owner,
        "样本保护结果": sample_protection_result,
    }
    return {
        "visible_fields": visible_fields,
        "data": {
            "sample_date": sample_date,
            "candidate": dict(candidate or {}),
            "market_emotion_label": market_emotion_label,
            "selection_quality_snapshot": selection_quality_snapshot,
            "entry_quality_snapshot": entry_quality_snapshot,
            "risk_items_snapshot": risk_items_snapshot,
            "cost_items_snapshot": cost_items_snapshot,
            "action_ceiling_snapshot": action_ceiling_snapshot,
            "holding_action_snapshot": holding_action_snapshot,
            "new_entry_action_snapshot": new_entry_action_snapshot,
            "actual_outcome": dict(actual_outcome or {}) if isinstance(actual_outcome, dict) else actual_outcome,
            "entry_window_result": entry_window_result,
            "user_deviation": user_deviation,
            "error_category": error_category,
            "improvement_owner": improvement_owner,
            "sample_protection_result": sample_protection_result,
        },
    }


def evaluate_sample_protection_change(
    *,
    changed_sample="",
    fixed_samples=None,
    harmed_protected_samples=None,
    preserved_samples=None,
):
    fixed_samples = _as_list(fixed_samples)
    harmed_protected_samples = _as_list(harmed_protected_samples)
    preserved_samples = _as_list(preserved_samples)
    allowed = not harmed_protected_samples
    if harmed_protected_samples:
        conclusion = "破坏基础保护样本，不能进入V1"
    elif fixed_samples:
        conclusion = "修复样本且保护样本未受损，可进入V1"
    else:
        conclusion = "未形成规则修复，仅记录"
    visible_fields = {
        "变更样本": changed_sample,
        "修复样本": _join_texts(fixed_samples),
        "受损保护样本": _join_texts(harmed_protected_samples),
        "保持保护样本": _join_texts(preserved_samples),
        "是否可进入V1": "是" if allowed else "否",
        "结论": conclusion,
        "处理动作": "记录复盘结论，不自动调权重" if allowed else "退回调整，先恢复保护样本",
    }
    return {
        "visible_fields": visible_fields,
        "data": {
            "changed_sample": changed_sample,
            "fixed_samples": fixed_samples,
            "harmed_protected_samples": harmed_protected_samples,
            "preserved_samples": preserved_samples,
            "allowed_for_v1": allowed,
            "conclusion": conclusion,
        },
    }


__all__ = [
    "ACTION_CEILINGS",
    "build_candidate_quality_review_record",
    "build_candidate_quality_contract",
    "build_daily_quality_decision_panel",
    "evaluate_sample_protection_change",
    "evaluate_candidate_quality_sample_contract",
    "evaluate_candidate_quality_sample",
    "resolve_intraday_action_update",
]
