from __future__ import annotations


ARTIFACT_VERSION = 1
VISIBLE_SCOPE = "T0_T1_T2_T3"
CHECK_RESULTS = ("满足", "部分满足", "未满足", "数据缺失")
VALID_TIERS = ("T0", "T1", "T2", "T3")


def _clean_text(value):
    return str(value or "").strip()


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]
    return [_clean_text(item) for item in values if _clean_text(item)]


def _as_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _stock_code(candidate):
    text = _clean_text(candidate.get("code") or candidate.get("代码")).upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _stock_name(candidate):
    return _clean_text(candidate.get("name") or candidate.get("名称"))


def _tier(candidate):
    tier = _clean_text(candidate.get("tier") or candidate.get("分层")).upper()
    return tier if tier in VALID_TIERS else ""


def _controlled_result(value):
    text = _clean_text(value)
    return text if text in CHECK_RESULTS else "数据缺失"


def _format_amount(value):
    amount = _as_number(value)
    rounded = round(amount)
    if abs(amount - rounded) < 0.01:
        return str(int(rounded))
    return f"{amount:.2f}"


def _has_bool_key(candidate, *keys):
    return any(key in candidate for key in keys)


def _truthy(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "是", "可", "可以")
    return bool(value)


def _resolve_account_status(candidate):
    explicit = _clean_text(candidate.get("account_trade_status") or candidate.get("账户状态"))
    if explicit in ("实际可买", "实际不可买"):
        return explicit, _clean_text(candidate.get("account_trade_reason") or candidate.get("账户状态原因")), False

    code = _stock_code(candidate)
    has_star_market_context = _has_bool_key(candidate, "can_trade_star_market", "可买科创板", "科创板可买")
    can_trade_star_market = _truthy(
        candidate.get("can_trade_star_market", candidate.get("可买科创板", candidate.get("科创板可买", False)))
    )
    if code.startswith("688") and (not has_star_market_context or not can_trade_star_market):
        return "实际不可买", "科创板交易资格不适配", False

    has_price = any(key in candidate and candidate.get(key) not in (None, "") for key in ("latest_price", "最新价", "price"))
    has_cash = any(key in candidate and candidate.get(key) not in (None, "") for key in ("available_cash", "可用资金", "account_cash", "账户资金"))
    latest_price = _as_number(candidate.get("latest_price", candidate.get("最新价", candidate.get("price"))))
    available_cash = _as_number(
        candidate.get("available_cash", candidate.get("可用资金", candidate.get("account_cash", candidate.get("账户资金"))))
    )

    if not has_price and not has_cash:
        return "数据缺失", "", True
    if not has_price or not has_cash:
        return "实际可买", "账户条件适配", False
    if latest_price <= 0 or available_cash <= 0:
        return "数据缺失", "", True

    lot_amount = latest_price * 100
    if lot_amount > available_cash:
        return "实际不可买", f"一手约{_format_amount(lot_amount)}，超过可用资金{_format_amount(available_cash)}", False
    return "实际可买", "账户条件适配", False


def _check(label, result, evidence):
    return {
        "label": label,
        "result": _controlled_result(result),
        "evidence": _clean_text(evidence),
    }


def _visible_summary(name, tier, checks, final_action):
    failed = [check["label"] for check in checks if check["result"] in ("未满足", "数据缺失")]
    if failed:
        text = f"{name or '候选'}：{failed[0]}{checks[[check['label'] for check in checks].index(failed[0])]['result']}"
    elif final_action:
        text = f"{name or '候选'}：{final_action}"
    else:
        text = f"{name or '候选'}：进入 {tier or '候选'} 条件观察"
    return text[:40]


def _terminal_step(tier, missing_data, account_status, checks):
    if missing_data:
        return "关键数据不完整，停止生成动作"
    if account_status == "实际不可买":
        return "账户条件不满足，不参与"
    if any(check["result"] == "未满足" for check in checks):
        return "条件未满足，继续不参与"
    return f"进入 {tier or '候选'} 条件观察"


def build_candidate_trace(candidate):
    candidate = dict(candidate or {})
    code = _stock_code(candidate)
    name = _stock_name(candidate)
    tier = _tier(candidate)
    mainline = _clean_text(candidate.get("mainline") or candidate.get("主线"))
    sector = _clean_text(candidate.get("sector") or candidate.get("板块"))
    source_pools = _as_list(candidate.get("source_pools") or candidate.get("来源池"))

    checks = [
        _check("市场条件", candidate.get("market_fit") or candidate.get("市场条件"), candidate.get("market_evidence") or candidate.get("市场证据")),
        _check("主线条件", candidate.get("mainline_fit") or candidate.get("主线条件"), candidate.get("mainline_evidence") or candidate.get("主线证据")),
        _check(
            "个股结构",
            candidate.get("stock_structure_fit") or candidate.get("个股结构"),
            candidate.get("stock_structure_evidence") or candidate.get("个股结构证据"),
        ),
    ]
    account_status, account_reason, account_missing = _resolve_account_status(candidate)

    missing_data = []
    if not mainline:
        missing_data.append("mainline")
    if not sector:
        missing_data.append("sector")
    for key, check in (("market_fit", checks[0]), ("mainline_fit", checks[1]), ("stock_structure_fit", checks[2])):
        if check["result"] == "数据缺失":
            missing_data.append(key)
    if account_missing:
        missing_data.append("account_context")

    final_action = _clean_text(candidate.get("final_action") or candidate.get("最终动作"))
    if missing_data and not final_action:
        final_action = "关键数据不完整，停止生成动作"

    branch_path = [f"{check['label']}{check['result']}" for check in checks]
    branch_path.append(_terminal_step(tier, missing_data, account_status, checks))

    key_inputs = [
        {"field": "账户适配", "value": account_status, "source": "account_context"},
    ]
    if account_reason:
        key_inputs.append({"field": "账户说明", "value": account_reason, "source": "account_context"})

    return {
        "stock_code": code,
        "stock_name": name,
        "tier": tier,
        "source_pools": source_pools,
        "mainline": mainline,
        "sector": sector,
        "key_inputs": key_inputs,
        "checks": checks,
        "branch_path": branch_path,
        "final_action": final_action,
        "trigger_condition": _clean_text(candidate.get("trigger_condition") or candidate.get("触发条件")),
        "failure_condition": _clean_text(candidate.get("failure_condition") or candidate.get("失效条件")),
        "missing_data": missing_data,
        "visible_summary": _visible_summary(name, tier, checks, final_action),
    }


def build_eliminated_summary(items):
    grouped = {}
    for item in items or []:
        item = item or {}
        reason = _clean_text(item.get("reason") or item.get("原因")) or "数据缺失"
        name = _clean_text(item.get("name") or item.get("名称"))
        if reason not in grouped:
            grouped[reason] = {
                "reason": reason,
                "count": 0,
                "representatives": [],
                "treatment": _eliminated_treatment(reason),
            }
        grouped[reason]["count"] += 1
        if name and len(grouped[reason]["representatives"]) < 3:
            grouped[reason]["representatives"].append(name)
    return list(grouped.values())


def _eliminated_treatment(reason):
    treatments = {
        "数据缺失": "关键数据不完整，停止生成动作",
        "账户不适配": "账户条件不满足，不进入动作分层",
        "主线不匹配": "保留观察，不进入动作分层",
    }
    return treatments.get(reason, "条件未满足，不进入动作分层")


def build_candidate_trace_artifact_payload(*, trade_date, traces, eliminated_summary, generated_at="", source_report=None):
    return {
        "artifact_version": ARTIFACT_VERSION,
        "trade_date": trade_date,
        "visible_scope": VISIBLE_SCOPE,
        "generated_at": generated_at,
        "source_report": dict(source_report or {}),
        "traces": list(traces or []),
        "eliminated_summary": list(eliminated_summary or []),
    }


__all__ = [
    "ARTIFACT_VERSION",
    "VISIBLE_SCOPE",
    "CHECK_RESULTS",
    "VALID_TIERS",
    "build_candidate_trace",
    "build_eliminated_summary",
    "build_candidate_trace_artifact_payload",
]
