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
    stock = stock or {}
    if stock.get("allow_full_attack") or stock.get("a_grade_candidate"):
        return "100%"
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

    script = {
        "participation_window": _clean_cell(_derive_participation_window(stock)),
        "attack_state": _clean_cell(_normalize_attack_state(_first_text(stock, "attack_state", "position_state", "target_position_pct"), stock=stock)),
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

    lines = ["**重点观察名单**（只保留最心动的少数，每只都绑定参与窗口）:"]
    if extreme_conviction_list:
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
        lines.append("| 参与窗口 | 仓位三态 | 涨停惯性 | 盈亏比 | 检查步骤 | 加工依据 | 集合竞价 | 开盘前几分钟 | 均线回归试错 | 打板策略 | 回封参与 | 错过后动作 | MA20作废 | 跟踪周期 | 作废条件 |")
        lines.append("|----------|----------|----------|--------|----------|----------|----------|--------------|--------------|----------|----------|------------|----------|----------|----------|")
        for stock in extreme_conviction_list:
            script = _build_participation_script(stock)
            lines.append(
                f"| {script['participation_window']} | {script['attack_state']} | "
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
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
