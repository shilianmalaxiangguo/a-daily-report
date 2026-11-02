from __future__ import annotations

import re
from typing import Any

from report.position_tier_contract import (
    POSITION_TIER_B1_PCT,
    normalize_position_tier_pct,
    position_tier_pct_to_x,
)


PREVIOUS_REPORT_TARGET_POSITION_SOURCE = "previous_report_target_default_1x"
SIMULATED_PREVIOUS_REPORT_ROLE = "旧仓处理"
TOMORROW_ACCOUNT_ACTION_SCHEMA_VERSION = "tomorrow_account_action.v1"
TOMORROW_EMPTY_ACCOUNT_ACTION = "empty"
OLD_POSITION_REVIEW_CONDITIONS = (
    "个股相对昨收和分时均价仍有承接",
    "个股相对指数强势没有快速消失",
    "板块核心与板块宽度同步承接，不是个股孤立冲高",
)


def build_tomorrow_empty_account_action(*, source: str = "explicit_input") -> dict[str, str]:
    return {
        "schema_version": TOMORROW_ACCOUNT_ACTION_SCHEMA_VERSION,
        "action": TOMORROW_EMPTY_ACCOUNT_ACTION,
        "source": str(source or "explicit_input").strip() or "explicit_input",
    }


def _normalize_tomorrow_account_action(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    action = str(value.get("action") or "").strip()
    if action not in {TOMORROW_EMPTY_ACCOUNT_ACTION, "明日空仓"}:
        return {}
    return build_tomorrow_empty_account_action(source=str(value.get("source") or "explicit_input"))


def resolve_tomorrow_account_action(*sources: Any) -> dict[str, str]:
    queue = [(source, 0) for source in sources]
    seen: set[int] = set()
    nested_keys = (
        "tomorrow_account_action",
        "final_target_resolution",
        "position_decision",
        "market_research_snapshot",
        "execution_stage_context",
    )
    while queue:
        value, depth = queue.pop(0)
        if not isinstance(value, dict):
            continue
        marker = id(value)
        if marker in seen:
            continue
        seen.add(marker)
        normalized = _normalize_tomorrow_account_action(value)
        if normalized:
            return normalized
        if depth >= 3:
            continue
        for key in nested_keys:
            nested = value.get(key)
            if isinstance(nested, dict):
                queue.append((nested, depth + 1))
    return {}


def is_tomorrow_empty_account_action(value: Any) -> bool:
    return bool(_normalize_tomorrow_account_action(value))


def is_inferred_previous_report_position(summary: Any) -> bool:
    return isinstance(summary, dict) and bool(
        summary.get("inferred_from_previous_report") is True
        or summary.get("position_source") == PREVIOUS_REPORT_TARGET_POSITION_SOURCE
    )


def _position_text(value: Any) -> str:
    if not isinstance(value, dict):
        return str(value or "").strip()
    return "；".join(
        str(value.get(key) or "").strip()
        for key in ("summary", "holding_note", "trade_action", "role", "trade_role")
        if str(value.get(key) or "").strip()
    )


def _position_pct(value: Any) -> float | None:
    value = value if isinstance(value, dict) else {}
    for key in ("position_pct", "position", "default_position_pct"):
        candidate = value.get(key)
        if candidate in (None, ""):
            continue
        try:
            return float(str(candidate).replace("%", "").strip())
        except (TypeError, ValueError):
            continue
    return None


def _position_identity(value: Any) -> dict[str, str]:
    value = value if isinstance(value, dict) else {}
    name = str(value.get("name") or value.get("stock_name") or "").strip()
    code = str(value.get("code") or value.get("stock_code") or "").strip()
    if not (name or code):
        match = re.search(r"([^，；|：:\n]+?)\((\d{6})\)", _position_text(value))
        if match:
            name = re.sub(r"^(?:持有|已有旧仓|当前持仓|已清仓)", "", match.group(1)).strip()
            code = match.group(2)
    return {key: item for key, item in {"name": name, "code": code}.items() if item}


def position_fact_status(summary: Any, *, context_provided: bool = False) -> str:
    summary = summary if isinstance(summary, dict) else {}
    if is_inferred_previous_report_position(summary):
        return "confirmed"
    if summary.get("has_position") is True:
        return "confirmed"
    if summary.get("has_pending_position") is True:
        return "pending_confirmation"
    text = _position_text(summary)
    if any(marker in text for marker in ("持仓未输入", "未输入持仓", "待确认持仓")):
        return "unknown"
    if summary.get("has_position") is False:
        return "none"
    if any(marker in text for marker in ("已确认无旧仓", "无旧仓", "已清仓")):
        return "none"
    if any(
        marker in text
        for marker in (
            "外部交易待核实",
            "外部交易记录待核实",
            "外部成交记录待核实",
            "待成交确认",
            "未确认成交",
            "成交记录待确认",
        )
    ):
        return "pending_confirmation"
    if any(marker in text for marker in ("持有", "已有旧仓", "当前持仓", "旧仓处理", "旧仓先处理")):
        return "confirmed"
    if isinstance(summary.get("old_position_plan"), dict):
        return "confirmed"
    if str(summary.get("trade_role") or "").strip() in {
        "old_position",
        "tplus2_exit",
        "failed_buy",
    }:
        return "confirmed"
    for key in ("position_pct", "position"):
        try:
            if float(str(summary.get(key) or "").replace("%", "").strip()) > 0:
                return "confirmed"
        except (TypeError, ValueError):
            continue
    if text:
        return "unknown"
    return "none" if context_provided else "unknown"


def build_old_position_plan(summary: Any, *, holding: Any = None) -> dict[str, Any]:
    summary = summary if isinstance(summary, dict) else {}
    holding = holding if isinstance(holding, dict) else {}
    if position_fact_status(summary, context_provided=True) != "confirmed":
        return {}

    explicit = summary.get("old_position_plan")
    if isinstance(explicit, dict) and explicit.get("schema_version") == "old_position_plan.v1":
        plan = dict(explicit)
        plan_holding = plan.get("holding") if isinstance(plan.get("holding"), dict) else {}
        plan_position_pct = _position_pct(plan_holding)
        try:
            plan_position_x = (
                position_tier_pct_to_x(plan_position_pct)
                if plan_position_pct is not None
                else None
            )
        except ValueError:
            plan_position_x = None
        plan["account_exposure_mode"] = (
            f"{plan_position_x}x" if plan_position_x is not None else "unknown"
        )
        plan["position_sizing_rule"] = (
            "position_tier" if plan_position_x is not None else "unknown"
        )
        decision_class = str(plan.get("decision_class") or "").strip()
        if decision_class not in {"failed", "review_at_10_10", "normal", "incomplete"}:
            trade_role = str(plan.get("trade_role") or "").strip()
            action = str(plan.get("action") or "").strip()
            if trade_role == "failed_buy":
                decision_class = "failed"
            elif action == "wait_for_repair":
                decision_class = "review_at_10_10"
            elif trade_role == "tplus2_exit":
                decision_class = "normal"
            else:
                decision_class = "incomplete"
            plan["decision_class"] = decision_class
        if decision_class == "failed":
            plan.update(
                {
                    "action": "exit",
                    "primary_action_window": "09:50-10:10",
                    "tail_exit_allowed": False,
                    "tail_exit_condition": "已经失败，不把尾盘新高作为默认等待理由",
                    "closing_target_position_pct": 0,
                    "review_conditions": [],
                }
            )
        elif decision_class == "review_at_10_10":
            plan.update(
                {
                    "action": "wait_for_repair",
                    "primary_action_window": "09:50-10:10",
                    "tail_exit_allowed": True,
                    "tail_exit_condition": "10:10三层承接全部成立，才允许把退出延后到14:30-14:55",
                    "closing_target_position_pct": (
                        0 if plan.get("trade_role") == "tplus2_exit" else None
                    ),
                    "review_conditions": list(OLD_POSITION_REVIEW_CONDITIONS),
                }
            )
        elif decision_class == "normal":
            explicit_tail_plan = bool(
                plan.get("trade_role") == "tplus2_exit"
                or plan.get("primary_action_window") == "14:30-14:55"
                or (
                    plan.get("tail_exit_allowed") is True
                    and "尾盘" in str(plan.get("tail_exit_condition") or "")
                )
            )
            if explicit_tail_plan:
                plan.update(
                    {
                        "action": "exit",
                        "primary_action_window": "14:30-14:55",
                        "tail_exit_allowed": True,
                        "tail_exit_condition": "旧仓逻辑未失效，按明确T+2或尾盘预案退出",
                        "closing_target_position_pct": 0,
                        "review_conditions": [],
                    }
                )
            else:
                plan.update(
                    {
                        "action": "hold",
                        "primary_action_window": "none",
                        "tail_exit_allowed": False,
                        "tail_exit_condition": "没有明确T+2或尾盘预案，不自行增加精确退出结论",
                        "closing_target_position_pct": _position_pct(plan.get("holding")),
                        "review_conditions": [],
                    }
                )
        else:
            plan.update(
                {
                    "action": "hold",
                    "primary_action_window": "none",
                    "tail_exit_allowed": False,
                    "tail_exit_condition": "旧仓周期、失效线或原退出预案不足，不能制造精确退出时刻",
                    "closing_target_position_pct": None,
                    "review_conditions": [],
                }
            )
        return plan

    merged = dict(summary)
    merged.update({key: value for key, value in holding.items() if value not in (None, "")})
    summary_text = _position_text(summary)
    holding_text = _position_text(holding)
    combined_text = "；".join(item for item in (summary_text, holding_text) if item)
    identity = _position_identity(merged) or _position_identity(summary)
    pct = _position_pct(merged)
    failed = any(
        marker in combined_text
        for marker in ("买点失败", "买点失效", "逻辑失效", "已经失败", "必须卖", "T失败")
    )
    explicit_tplus2 = bool(re.search(r"T\s*\+\s*2", combined_text, flags=re.IGNORECASE))
    review = bool(holding.get("trade_action") == "做T") or any(
        marker in combined_text
        for marker in ("09:50-10:10", "10:10", "收不回先卖", "不能修复", "待复核")
    )
    normal = explicit_tplus2 or any(marker in combined_text for marker in ("正常存活", "继续持有", "独立评估"))

    if failed:
        decision_class = "failed"
        action = "exit"
        primary_action_window = "09:50-10:10"
        review_conditions: list[str] = []
        tail_exit_allowed = False
        tail_exit_condition = "已经失败，不把尾盘新高作为默认等待理由"
        closing_target_position_pct = 0
        risk_reward_assessment = "unfavorable"
    elif review:
        decision_class = "review_at_10_10"
        action = "wait_for_repair"
        primary_action_window = "09:50-10:10"
        review_conditions = list(OLD_POSITION_REVIEW_CONDITIONS)
        tail_exit_allowed = True
        tail_exit_condition = "10:10三层承接全部成立，才允许把退出延后到14:30-14:55"
        closing_target_position_pct = 0 if explicit_tplus2 else None
        risk_reward_assessment = "neutral"
    elif normal and explicit_tplus2:
        decision_class = "normal"
        action = "exit"
        primary_action_window = "14:30-14:55"
        review_conditions = []
        tail_exit_allowed = True
        tail_exit_condition = "旧仓逻辑未失效，按明确T+2尾盘预案退出"
        closing_target_position_pct = 0
        risk_reward_assessment = "favorable"
    elif normal:
        decision_class = "normal"
        action = "hold"
        primary_action_window = "none"
        review_conditions = []
        tail_exit_allowed = False
        tail_exit_condition = "没有明确T+2事实，不自行增加尾盘退出结论"
        closing_target_position_pct = pct
        risk_reward_assessment = "neutral"
    else:
        decision_class = "incomplete"
        action = "hold"
        primary_action_window = "none"
        review_conditions = []
        tail_exit_allowed = False
        tail_exit_condition = "旧仓周期、失效线或原退出预案不足，不能制造精确退出时刻"
        closing_target_position_pct = None
        risk_reward_assessment = "incomplete"

    try:
        position_x = position_tier_pct_to_x(pct) if pct is not None else None
    except ValueError:
        position_x = None
    return {
        "schema_version": "old_position_plan.v1",
        "holding": {**identity, "position_pct": pct},
        "account_exposure_mode": f"{position_x}x" if position_x is not None else "unknown",
        "position_sizing_rule": "position_tier" if position_x is not None else "unknown",
        "trade_role": "tplus2_exit" if explicit_tplus2 else ("failed_buy" if failed else "old_position"),
        "risk_reward_assessment": risk_reward_assessment,
        "relative_strength_basis": "10:10复核个股、指数和板块三层承接" if review else "旧仓原预案",
        "rebound_exit_zone": "09:50-10:10内完成退出" if failed else None,
        "invalidation_lines": ["旧仓原失效线"] if failed else [],
        "tail_exit_allowed": tail_exit_allowed,
        "tail_exit_condition": tail_exit_condition,
        "action": action,
        "evidence_sources": list(summary.get("evidence_sources") or ["existing_position_summary"]),
        "decision_class": decision_class,
        "primary_action_window": primary_action_window,
        "review_conditions": review_conditions,
        "closing_target_position_pct": closing_target_position_pct,
    }


def old_position_action_rows(
    *,
    position_fact_status: str,
    existing_position: Any,
    old_position_plan: Any,
    tomorrow_account_action: Any = None,
) -> dict[str, str]:
    existing_position = existing_position if isinstance(existing_position, dict) else {}
    old_position_plan = old_position_plan if isinstance(old_position_plan, dict) else {}
    if is_tomorrow_empty_account_action(tomorrow_account_action):
        fact = {
            "unknown": "持仓未输入",
            "pending_confirmation": "外部交易待核实",
            "none": "已确认无旧仓",
        }.get(position_fact_status)
        if not fact:
            identity = _position_identity(existing_position) or _position_identity(old_position_plan.get("holding"))
            label = (
                f"{identity.get('name')}({identity.get('code')})"
                if identity.get("name") and identity.get("code")
                else identity.get("name") or identity.get("code") or "旧仓"
            )
            fact = f"已确认持有{label}"
        judgment = {
            "unknown": "明日空仓；账户事实待确认",
            "pending_confirmation": "明日空仓；外部交易待核实",
            "none": "明日空仓；当前无旧仓需要卖出",
        }.get(position_fact_status, "明日空仓，覆盖常规旧仓处理时点")
        return {
            "旧仓事实": fact,
            "旧仓判断": judgment,
            "旧仓动作": (
                "不买新股、不做T；集合竞价卖清全部可卖旧仓（当前无旧仓则无需卖出）；"
                "未全部成交继续尽早卖，未清完不能称空仓"
            ),
            "收盘目标仓位": "0%（全部可卖旧仓卖清后；未清完不能称空仓）",
        }
    if position_fact_status == "unknown":
        return {
            "旧仓事实": "持仓未输入",
            "旧仓判断": "无法判断旧仓是否需要退出",
            "旧仓动作": "先核对实际持仓；不从明日新仓0%反推卖出",
            "收盘目标仓位": "待确认",
        }
    if position_fact_status == "pending_confirmation":
        return {
            "旧仓事实": "外部交易待核实",
            "旧仓判断": "外部交易待核实，不视为旧仓",
            "旧仓动作": "只核实成交记录；未确认成交前不卖、不新增B2",
            "收盘目标仓位": "0x（未确认成交前，不代表已确认空仓）",
        }
    if position_fact_status == "none":
        return {
            "旧仓事实": "已确认无旧仓",
            "旧仓判断": "无旧仓需要判断",
            "旧仓动作": "无旧仓需要处理",
            "收盘目标仓位": "0%",
        }

    identity = _position_identity(existing_position) or _position_identity(old_position_plan.get("holding"))
    label = (
        f"{identity.get('name')}({identity.get('code')})"
        if identity.get("name") and identity.get("code")
        else identity.get("name") or identity.get("code") or "旧仓"
    )
    decision_class = str(old_position_plan.get("decision_class") or "incomplete")
    judgment = {
        "failed": "已经失败",
        "review_at_10_10": "待10:10复核",
        "normal": "正常存活",
        "incomplete": "事实不足",
    }.get(decision_class, "事实不足")
    if decision_class == "failed":
        action = "09:50-10:10内完成退出；不等14:30-14:55"
    elif decision_class == "review_at_10_10":
        action = (
            "09:50-10:10只复核一次：个股承接、相对指数强弱、板块同步承接全部成立"
            "才保留到14:30-14:55，否则10:10前退出"
        )
    elif decision_class == "normal" and old_position_plan.get("trade_role") == "tplus2_exit":
        action = "14:30-14:55按T+2预案退出"
    elif decision_class == "normal":
        action = "按原持有预案；不因明日新仓0%自动卖出"
    else:
        action = "旧仓事实不足；先补持仓周期、失效线和原退出预案"

    closing_pct = old_position_plan.get("closing_target_position_pct")
    if closing_pct not in (None, ""):
        closing = f"{int(float(closing_pct))}%"
    elif decision_class == "review_at_10_10":
        closing = "待10:10复核后确定"
    elif decision_class == "normal":
        closing = "按原预案"
    else:
        closing = "待确认"
    return {
        "旧仓事实": f"已确认持有{label}",
        "旧仓判断": judgment,
        "旧仓动作": action,
        "收盘目标仓位": closing,
    }


def existing_position_summary_from_context(context: Any) -> dict[str, Any]:
    context = context if isinstance(context, dict) else {}
    personal_context = context.get("personal_position_context")
    personal_context = personal_context if isinstance(personal_context, dict) else {}
    summary = personal_context.get("existing_position_summary")
    if not isinstance(summary, dict) or not summary:
        summary = context.get("existing_position_summary")
    return summary if isinstance(summary, dict) else {}


def normalize_inferred_previous_target_records(value: Any, _visited: set[int] | None = None) -> int:
    if not isinstance(value, (dict, list)):
        return 0
    if _visited is None:
        _visited = set()
    marker = id(value)
    if marker in _visited:
        return 0
    _visited.add(marker)
    normalized = 0
    if isinstance(value, dict):
        if is_inferred_previous_report_position(value):
            record_changed = False
            name = str(value.get("name") or value.get("stock_name") or "").strip()
            code = str(value.get("code") or value.get("stock_code") or "").strip()
            if not (name or code):
                match = re.search(r"([^，；|：:\n]+?)\((\d{6})\)", str(value.get("summary") or ""))
                if match:
                    name = re.sub(r"^(?:持有|已有旧仓|当前持仓)", "", match.group(1)).strip()
                    code = match.group(2)
            label = f"{name}({code})" if name and code else (name or code or "前日报计划对象")
            source_report_date = str(value.get("source_report_date") or "").strip()
            source_note = f"；上一份日报目标来源={source_report_date}" if source_report_date else ""
            canonical_summary = f"持有{label}，1x/50%半仓，上一份日报明日标的默认1x旧仓{source_note}"
            if value.get("summary") != canonical_summary:
                value["summary"] = canonical_summary
                record_changed = True
            if value.get("has_position") is not True:
                value["has_position"] = True
                record_changed = True
            if value.get("has_pending_position") is not False:
                value["has_pending_position"] = False
                record_changed = True
            if value.get("default_position_pct") != float(POSITION_TIER_B1_PCT):
                value["default_position_pct"] = float(POSITION_TIER_B1_PCT)
                record_changed = True
            for actual_position_key in ("position", "position_pct"):
                if value.get(actual_position_key) != float(POSITION_TIER_B1_PCT):
                    value[actual_position_key] = float(POSITION_TIER_B1_PCT)
                    record_changed = True
            if value.get("inferred_from_previous_report") is not True:
                value["inferred_from_previous_report"] = True
                record_changed = True
            if value.get("role") != SIMULATED_PREVIOUS_REPORT_ROLE:
                value["role"] = SIMULATED_PREVIOUS_REPORT_ROLE
                record_changed = True
            if value.get("holding_note") != "上一份日报明日标的默认1x旧仓":
                value["holding_note"] = "上一份日报明日标的默认1x旧仓"
                record_changed = True
            explicit_plan = value.get("old_position_plan")
            if isinstance(explicit_plan, dict) and explicit_plan.get("schema_version") == "old_position_plan.v1":
                holding = explicit_plan.get("holding") if isinstance(explicit_plan.get("holding"), dict) else {}
                normalized_holding = {
                    **holding,
                    **({"name": name} if name else {}),
                    **({"code": code} if code else {}),
                    "position_pct": POSITION_TIER_B1_PCT,
                }
                if explicit_plan.get("holding") != normalized_holding:
                    explicit_plan["holding"] = normalized_holding
                    record_changed = True
            if record_changed:
                normalized += 1
        for child in value.values():
            normalized += normalize_inferred_previous_target_records(child, _visited)
    elif isinstance(value, list):
        for child in value:
            normalized += normalize_inferred_previous_target_records(child, _visited)
    return normalized


def is_position_timeline_header(line: Any) -> bool:
    text = str(line or "").lstrip()
    return text.startswith("| 轨道 | 标的 |") or text.startswith("| 日序 | 日期 |")


def extract_position_timeline_markdown(position_strategy_report: Any) -> str:
    lines = str(position_strategy_report or "").splitlines()
    if not lines or not is_position_timeline_header(lines[0]):
        return ""
    collected = []
    for line in lines:
        if line.startswith("#"):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def markdown_has_position_timeline(markdown_text: Any) -> bool:
    saw_content = False
    for line in str(markdown_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "## 账户日序表":
            return True
        if not saw_content and is_position_timeline_header(line):
            return True
        saw_content = True
    return False


def prepend_position_timeline_markdown(markdown_text: Any, position_timeline_markdown: Any) -> str:
    timeline = str(position_timeline_markdown or "").strip()
    if not timeline:
        return str(markdown_text or "")
    section = f"## 账户日序表\n{timeline}"
    text = str(markdown_text or "")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "## 账户日序表":
            continue
        end = index + 1
        seen_table = False
        while end < len(lines):
            stripped = lines[end].strip()
            if lines[end].startswith("## "):
                break
            if not stripped:
                end += 1
                continue
            if stripped.startswith("|"):
                seen_table = True
                end += 1
                continue
            if seen_table and stripped.startswith("-"):
                end += 1
                continue
            break
        updated_lines = lines[:index] + [section, ""] + lines[end:]
        return "\n".join(updated_lines).strip() + "\n"
    if markdown_has_position_timeline(markdown_text):
        return str(markdown_text or "")
    text = str(markdown_text or "").lstrip()
    lines = text.splitlines()
    if not lines:
        return f"{section}\n"
    insert_at = 0
    if lines[0].startswith("# "):
        insert_at = 1
        while insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1
        if insert_at < len(lines) and lines[insert_at].strip() == "## 阅读地图":
            insert_at += 1
            while insert_at < len(lines):
                if lines[insert_at].startswith("## "):
                    break
                insert_at += 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
    updated_lines = lines[:insert_at] + ["", section, ""] + lines[insert_at:]
    return "\n".join(updated_lines).strip() + "\n"
