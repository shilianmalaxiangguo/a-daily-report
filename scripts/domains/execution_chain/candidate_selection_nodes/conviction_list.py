from report.surface_wording import sanitize_user_visible_text
from selection.candidate_execution_contracts import (
    build_participation_window_from_candidate,
    build_participation_window_policy,
)


def _clean_cell(value, default="-"):
    text = str(value if value not in (None, "") else default).strip()
    text = sanitize_user_visible_text(text)
    return text.replace("|", "/") or default


def _first_text(stock, *keys):
    for key in keys:
        value = stock.get(key)
        if value not in (None, ""):
            return value
    return ""


def _normalize_attack_state(value, stock=None):
    raw = str(value or "").strip()
    if "100" in raw:
        return "100%"
    if "50" in raw:
        return "50%"
    if raw in ("0", "0%"):
        return "0%"
    return "50%"


def _format_core_identity(stock):
    identity = stock.get("core_identity") or {}
    if not isinstance(identity, dict):
        return "待判定"
    if not identity:
        text = " / ".join(
            str(stock.get(key) or "")
            for key in ("conviction_reason", "reason", "core_level", "pattern")
        )
        is_anchor = "锚定龙" in text or "趋势比价链锚定龙" in text
        is_core = is_anchor or "主线内核" in text or "主线核心" in text or "连板" in text or "龙一" in text
        if is_anchor:
            identity = {"role": "trend_chain_anchor", "chain_position": "high_anchor"}
        elif is_core:
            identity = {"role": "core_transmitter", "chain_position": "middle_transmitter"}
        else:
            identity = {"role": "tracked_sample", "chain_position": "unassigned"}
    role_label = {
        "trend_chain_anchor": "趋势比价链锚点",
        "core_transmitter": "核心传导者",
        "tracked_sample": "跟踪样本",
    }.get(str(identity.get("role") or "").strip(), "待判定")
    position_label = {
        "high_anchor": "高位锚",
        "core_transmitter": "核心传导",
        "middle_transmitter": "中位传导",
        "low_catchup": "低位承接",
        "unassigned": "未分配",
    }.get(str(identity.get("chain_position") or "").strip(), "")
    return _clean_cell(f"{role_label} / {position_label}" if position_label else role_label)


def _format_candidate_layer(stock):
    eligibility = str(stock.get("execution_eligibility") or "").strip()
    layer = str(stock.get("candidate_layer") or "").strip()
    if eligibility == "blocked_by_negative_news" or layer == "risk_blocked":
        return "风险拦截"
    if eligibility in ("auction_reseal", "open_core") or layer == "executable_candidate":
        return "可执行候选"
    if eligibility == "structure_confirm_only" or layer == "watch_sample":
        return "修复观察"

    window = str(_first_text(stock, "participation_window", "conviction_window") or "").strip()
    attack_state = _normalize_attack_state(
        _first_text(stock, "attack_state", "position_state", "target_position_pct"),
        stock=stock,
    )
    identity = stock.get("core_identity") or {}
    if not isinstance(identity, dict):
        identity = {}
    if (
        any(marker in window for marker in ("竞价", "回封", "打板"))
        or attack_state == "100%"
        or identity.get("early_participation_allowed")
    ):
        return "可执行候选"
    return "观察样本"


def _derive_participation_window(stock):
    return build_participation_window_from_candidate(stock)


def _format_required_steps(script):
    steps = script.get("required_steps") or []
    if isinstance(steps, str):
        return _clean_cell(steps)
    return _clean_cell(" / ".join(str(step).strip() for step in steps if str(step).strip()))


def _format_participation_basis(script):
    basis = script.get("participation_basis") or {}
    if not isinstance(basis, dict):
        return _clean_cell(basis)
    parts = []
    for key in ("auction", "first_minutes", "ma_reversion", "board_or_reseal", "structure"):
        value = basis.get(key)
        if value:
            parts.append(str(value).strip())
    return _clean_cell("；".join(parts))


def _format_ma_reversion_probe(script):
    if not script.get("ma_reversion_probe_allowed"):
        return "不启用"
    window = script.get("ma_reversion_window") or "09:50-10:10"
    probe = script.get("ma_reversion_probe") or "只限昨日重点观察且未被风险拦截的样本；回踩日K MA5/MA10或分时黄线不破才允许小仓试错"
    yellow = script.get("intraday_yellow_line_probe") or "分时黄线只作为日内承接确认线"
    return _clean_cell(f"{window}均线回归试错；{probe}；{yellow}")


def _format_tracking_window(script):
    days = script.get("tracking_window_trade_days") or 25
    try:
        days = int(days)
    except (TypeError, ValueError):
        return _clean_cell(days)
    return f"{days}个交易日"


def _format_probability_edge(script):
    level = script.get("limit_up_inertia_level") or "待判定"
    band = script.get("next_day_limit_probability_band") or "等待价格验证"
    reason = script.get("limit_up_inertia_reason") or ""
    return _clean_cell(f"{level}；{band}；{reason}")


def _format_risk_reward(script):
    state = script.get("risk_reward_state") or "待计算"
    ratio = script.get("risk_reward_ratio")
    plan = script.get("risk_reward_plan") or "盈亏比不足时只观察"
    if ratio not in (None, ""):
        return _clean_cell(f"{state}；约{ratio}:1；{plan}")
    return _clean_cell(f"{state}；{plan}")


_QUANT_ANCHOR_FIELDS = (
    ("anchor_zone_role", "锚点区间"),
    ("anchor_line_confluence", "共振线"),
    ("hidden_liquidity_read", "隐藏盘"),
    ("anchor_action_plan", "动作"),
    ("common_selection_factors", "共同选择"),
    ("momentum_feedback_plan", "动量反馈"),
    ("reversal_exit_plan", "反包兑现"),
)


def _clean_anchor_value(value):
    return _clean_cell(value, "").replace("｜", "/").strip()


def _format_quant_anchor_action(script):
    labeled_values = []
    values_by_field = {}
    for field, label in _QUANT_ANCHOR_FIELDS:
        value = _clean_anchor_value(script.get(field))
        if not value:
            continue
        values_by_field[field] = value
        labeled_values.append(f"{label}={value}")
    if not labeled_values:
        return "-"
    summary_values = [
        values_by_field.get("anchor_zone_role"),
        values_by_field.get("anchor_action_plan"),
    ]
    summary = " / ".join(value for value in summary_values if value) or "已记录"
    return _clean_cell(f"量化锚点动作：{summary}｜{'｜'.join(labeled_values)}")


def _format_stock_label(stock):
    name = _clean_cell(stock.get("name") or stock.get("stock_name"), "观察对象")
    code = _clean_cell(stock.get("code") or stock.get("stock_code"), "")
    return f"{name}({code})" if code else name


def _format_risk_review(stock):
    review = stock.get("final_risk_review")
    if isinstance(review, dict):
        status = _clean_cell(review.get("status"), "待复核")
        reasons = [str(reason).strip() for reason in review.get("reasons") or [] if str(reason).strip()]
        return _clean_cell(f"{status}：{' / '.join(reasons)}" if reasons else status)
    return _clean_cell(review, "待复核")


def _format_shape_repair_reasons(stock):
    review = stock.get("trend_aesthetic_review") or {}
    if not isinstance(review, dict):
        review = {}
    reasons = [str(reason).strip() for reason in review.get("reasons") or [] if str(reason).strip()]
    return _clean_cell(" / ".join(reasons), "走势待修复")


def _format_shape_repair_action(stock):
    review = stock.get("trend_aesthetic_review") or {}
    if not isinstance(review, dict):
        review = {}
    return _clean_cell(review.get("action"), "重新站回短中线承接后再评估")


def _format_historical_review_date(stock):
    return _clean_cell(stock.get("mention_trade_date") or stock.get("trade_date"), "-")


def _build_participation_script(stock):
    sector = _clean_cell(stock.get("sector"), "主线")
    participation_script = stock.get("participation_script") or {}
    if not isinstance(participation_script, dict):
        participation_script = {}

    def _script_value(field, *aliases, default):
        value = _first_text(stock, field, *aliases)
        if value:
            return _clean_cell(value)
        for key in (field, *aliases):
            nested = participation_script.get(key)
            if nested not in (None, ""):
                return _clean_cell(nested)
        return _clean_cell(default)

    def _optional_script_value(field):
        value = _first_text(stock, field)
        if value not in (None, ""):
            return _clean_cell(value)
        nested = participation_script.get(field)
        if nested not in (None, ""):
            return _clean_cell(nested)
        return ""

    script = {
        "participation_window": _clean_cell(_derive_participation_window(stock)),
        "attack_state": _clean_cell(_normalize_attack_state(_first_text(stock, "attack_state", "position_state", "target_position_pct"), stock=stock)),
        "anchor_zone_role": _optional_script_value("anchor_zone_role"),
        "anchor_line_confluence": _optional_script_value("anchor_line_confluence"),
        "hidden_liquidity_read": _optional_script_value("hidden_liquidity_read"),
        "anchor_action_plan": _optional_script_value("anchor_action_plan"),
        "common_selection_factors": _optional_script_value("common_selection_factors"),
        "momentum_feedback_plan": _optional_script_value("momentum_feedback_plan"),
        "reversal_exit_plan": _optional_script_value("reversal_exit_plan"),
        "auction_script": _script_value(
            "auction_script",
            "auction",
            default="09:20后看价格位置、匹配金额、委托稳定和板块同步，任一不合格按0%",
        ),
        "first_minutes_script": _script_value(
            "first_minutes_script",
            "first_minutes",
            "opening_script",
            default="09:30-09:35只看主动资金是否继续抬价，承接不连续按0%",
        ),
        "board_script": _script_value(
            "board_script",
            "limit_board_script",
            "board",
            default="只做首次强封或大单金额持续进入，弱封不追",
        ),
        "reseal_script": _script_value(
            "reseal_script",
            "reseal",
            default="开板释放抛压后快速回封，且封单质量改善、板块同步",
        ),
        "missed_action": _script_value(
            "missed_action",
            "missed_entry_action",
            default=f"过快封死就沿{sector}趋势比价链找低位承接，找不到就跳过",
        ),
        "invalid_condition": _script_value(
            "invalid_condition",
            "cancel_condition",
            "failure_condition",
            default="竞价表态、开盘承接、板块同步任一失败，按0%不参与",
        ),
    }
    script.update(build_participation_window_policy(script["participation_window"], script["missed_action"], candidate=stock))
    return script


def build_candidate_selection_conviction_list_node(context, node_meta=None, node_lookup=None):
    extreme_conviction_list = context.get("extreme_conviction_list", []) or []
    shape_repair_pool = context.get("shape_repair_pool", []) or []
    dragon_rebound_watch_pool = context.get("dragon_rebound_watch_pool", []) or []
    historical_extreme_review = context.get("historical_extreme_review", []) or []

    lines = ["**重点观察名单**（只保留最心动的少数，每只都绑定参与窗口）:"]
    if extreme_conviction_list:
        sniper_items = [
            stock for stock in extreme_conviction_list
            if isinstance(stock, dict) and stock.get("sniper_role") in ("明日主买对象", "明日补位对象")
        ]
        if sniper_items:
            lines.append("| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 最终复核 |")
            lines.append("|------|------|--------|--------|--------|--------------|----------|")
            for stock in sniper_items:
                lines.append(
                    f"| {_clean_cell(stock.get('sniper_role'))} | {_format_stock_label(stock)} | "
                    f"{_clean_cell(stock.get('leader_speed_tier'), '待判定')} | "
                    f"{_clean_cell(stock.get('buy_ma_line'))} | {_clean_cell(stock.get('sell_ma_line'))} | "
                    f"{_clean_cell(stock.get('acceptance_repair_required'), '等待承接修复')} | "
                    f"{_format_risk_review(stock)} |"
                )
            lines.append("")
        lines.append("| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 执行分层 | 观察理由 | 明日原则 |")
        lines.append("|--------|------|------|----------|----------|----------|----------|----------|")
        for idx, stock in enumerate(extreme_conviction_list, 1):
            lines.append(
                f"| {idx} | {_clean_cell(stock.get('name'))} | {_clean_cell(stock.get('code'))} | "
                f"{_clean_cell(stock.get('sector'))} | {_format_core_identity(stock)} | {_format_candidate_layer(stock)} | {_clean_cell(stock.get('conviction_reason'))} | "
                f"{_clean_cell(stock.get('conviction_rule'))} |"
            )
        lines.append("")
        lines.append("**重点观察参与脚本**:")
        lines.append("| 参与窗口 | 仓位三态 | 量化锚点动作 | 涨停惯性 | 盈亏比 | 检查步骤 | 加工依据 | 集合竞价 | 开盘前几分钟 | 均线回归试错 | 打板策略 | 回封参与 | 错过后动作 | MA20作废 | 跟踪周期 | 作废条件 |")
        lines.append("|----------|----------|--------------|----------|--------|----------|----------|----------|--------------|--------------|----------|----------|------------|----------|----------|----------|")
        for stock in extreme_conviction_list:
            script = _build_participation_script(stock)
            lines.append(
                f"| {script['participation_window']} | {script['attack_state']} | "
                f"{_format_quant_anchor_action(script)} | "
                f"{_format_probability_edge(script)} | {_format_risk_reward(script)} | "
                f"{_format_required_steps(script)} | {_format_participation_basis(script)} | "
                f"{script['auction_script']} | {script['first_minutes_script']} | "
                f"{_format_ma_reversion_probe(script)} | "
                f"{script['board_script']} | {script['reseal_script']} | "
                f"{script['missed_action']} | {_clean_cell(script.get('ma20_invalidation'))} | "
                f"{_format_tracking_window(script)} | {script['invalid_condition']} |"
            )
    else:
        lines.append("- 暂无重点观察标的，说明当下更适合广泛观察而不是集中出手。")
    if shape_repair_pool:
        lines.append("")
        lines.append("**形态待修复池**（历史形态值得继续看，但当前不进正式名单）:")
        lines.append("| 股票 | 代码 | 板块 | 状态 | 走势问题 | 修复条件 | 下一步 |")
        lines.append("|------|------|------|------|----------|----------|--------|")
        for stock in shape_repair_pool:
            lines.append(
                f"| {_clean_cell(stock.get('name'))} | {_clean_cell(stock.get('code'))} | "
                f"{_clean_cell(stock.get('sector'))} | {_clean_cell(stock.get('repair_status'), '待修复')} | "
                f"{_format_shape_repair_reasons(stock)} | {_format_shape_repair_action(stock)} | "
                f"{_clean_cell(stock.get('next_action'), '保留跟踪，重新站回短中线承接后再评估；继续走坏再取关淘汰')} |"
            )
    if dragon_rebound_watch_pool:
        lines.append("")
        lines.append("**龙回头观察池**（有历史辨识度，但当前A杀或弱反抽未修复，不进正式名单）:")
        lines.append("| 股票 | 代码 | 板块 | 状态 | 走势问题 | 修复条件 | 下一步 |")
        lines.append("|------|------|------|------|----------|----------|--------|")
        for stock in dragon_rebound_watch_pool:
            lines.append(
                f"| {_clean_cell(stock.get('name'))} | {_clean_cell(stock.get('code'))} | "
                f"{_clean_cell(stock.get('sector'))} | {_clean_cell(stock.get('repair_status'), '龙回头观察')} | "
                f"{_format_shape_repair_reasons(stock)} | {_format_shape_repair_action(stock)} | "
                f"{_clean_cell(stock.get('next_action'), '单独观察是否重新站回短中线承接；A杀未修复前不进正式名单，继续走坏再取关淘汰')} |"
            )
    if historical_extreme_review:
        lines.append("")
        lines.append("**历史重点观察样本去向**（逐个复核，不把走坏样本混进正式名单）:")
        lines.append("| 入选日 | 股票 | 代码 | 板块 | 来源 | 去向 | 当前判断 | 依据 | 下一步 |")
        lines.append("|--------|------|------|------|------|------|----------|------|--------|")
        for stock in historical_extreme_review:
            lines.append(
                f"| {_format_historical_review_date(stock)} | {_clean_cell(stock.get('name'))} | "
                f"{_clean_cell(stock.get('code'))} | {_clean_cell(stock.get('sector'))} | "
                f"{_clean_cell(stock.get('source_section'), '极度看好名单')} | "
                f"{_clean_cell(stock.get('destination'))} | {_clean_cell(stock.get('review_status'))} | "
                f"{_clean_cell(stock.get('review_basis'))} | {_clean_cell(stock.get('next_action'))} |"
            )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
