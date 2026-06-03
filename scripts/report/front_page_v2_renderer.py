from __future__ import annotations

from report.reasoning_decision_renderer import render_reasoning_decision_lines
from report.reasoning_decision_support import derive_unique_action_target_from_reasoning_decision
from report.candidate_snapshot_contract import build_candidate_snapshot
from report.market_research_snapshot_nodes import (
    build_market_research_snapshot_cycle_calendar_node,
    build_market_research_snapshot_cycle_interpretation_node,
    build_market_research_snapshot_lhb_capital_intent_node,
    build_market_research_snapshot_pivot_mainline_interpretation_node,
    derive_market_research_cycle_layer,
)
from report.front_summary_renderer import sanitize_front_page_text
from report.mainline_turnover_summary_support import (
    render_hot_sector_turnover_watch_grouped_lines,
    resolve_hot_sector_turnover_watch_rows,
    resolve_hot_sector_turnover_watch_summary,
    resolve_double_mainline_summary,
    resolve_mainline_attack_evidence_summary,
    resolve_mainline_attack_evidence_rows,
    resolve_mainline_capacity_regime_summary,
    resolve_overtake_opening_tone_text,
    resolve_turnover_share_trend_rows,
)
from report.market_structure_judgement import (
    build_market_structure_judgement,
    render_market_structure_section,
)
from report.trading_time_window_contract import (
    OPENING_WINDOW,
    SECOND_CONFIRM_LABEL,
    SECOND_CONFIRM_WINDOW,
    TAIL_WINDOW,
    normalize_participation_window,
    normalize_trading_time_text,
)


FORBIDDEN_FRONT_PAGE_MARKERS = ("### 🔬 市场研究快照", "Step 0")


def _display_latest_first(rows):
    return list(reversed(list(rows or [])))


def _section_between(lines, start_marker, end_marker=None):
    lines = list(lines or [])
    try:
        start = lines.index(start_marker)
    except ValueError:
        return []
    if end_marker is None:
        end = len(lines)
    else:
        try:
            end = lines.index(end_marker, start + 1)
        except ValueError:
            end = len(lines)
    return list(lines[start:end])


def _extract_table(lines, header_line):
    lines = list(lines or [])
    try:
        start = lines.index(header_line)
    except ValueError:
        return []
    table = []
    for line in lines[start:]:
        if not str(line).startswith("|"):
            if table:
                break
            continue
        table.append(line)
    return table


def _strip_heading(lines, heading):
    return [line for line in list(lines or []) if line != heading]


def _append_nonempty(target, lines):
    for line in lines or []:
        if any(marker in str(line) for marker in FORBIDDEN_FRONT_PAGE_MARKERS):
            continue
        target.append(line)


def _market_fit_calibration(snapshot):
    calibration = (snapshot or {}).get("market_fit_calibration") or {}
    return calibration if isinstance(calibration, dict) else {}


def _has_unconfirmed_attack_evidence(snapshot):
    attack_summary = resolve_mainline_attack_evidence_summary(snapshot)
    return bool(attack_summary) and attack_summary.get("attack_state") != "confirmed_attack"


def _dragon_pullback_review(snapshot):
    review = (snapshot or {}).get("dragon_pullback_review") or {}
    return review if isinstance(review, dict) else {}


def _dragon_pullback_review_active(snapshot):
    review = _dragon_pullback_review(snapshot)
    return bool(review.get("leader") and review.get("second_confirmation"))


def _dragon_pullback_laggard_text(snapshot):
    laggards = _dragon_pullback_review(snapshot).get("laggard_feedback") or []
    if isinstance(laggards, str):
        return laggards.strip()
    if not isinstance(laggards, list):
        return ""
    names = [str(item).strip() for item in laggards if str(item).strip()]
    return "、".join(names[:3])


def _dragon_pullback_lines(snapshot):
    if not _dragon_pullback_review_active(snapshot):
        return []
    review = _dragon_pullback_review(snapshot)
    leader = str(review.get("leader") or "").strip()
    laggards = _dragon_pullback_laggard_text(snapshot)
    if laggards:
        result = f"{leader}二次确认；{laggards}低位补涨反哺核心辨识度"
    else:
        result = f"{leader}二次确认；等待低位补涨继续验证"
    return [
        "### 6. 龙头回头复核",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 龙头回头复核 | {result} |",
        "龙头第一波后的回撤只算观察，第二波顶住压力且低位补涨同步，才说明市场继续投票",
        "",
    ]


def _append_sentence(text, addition):
    text = str(text or "").strip()
    addition = str(addition or "").strip()
    if not addition or addition in text:
        return text
    if text and not text.endswith("。"):
        text = f"{text}。"
    if addition and not addition.endswith("。"):
        addition = f"{addition}。"
    return f"{text}{addition}" if text else addition


def _with_derived_cycle_layer(snapshot):
    snapshot = dict(snapshot or {})
    has_refresh_source = bool(
        snapshot.get("target_date")
        or snapshot.get("current_mainline_history_record")
        or snapshot.get("recent_mainline_history")
        or snapshot.get("pivot_mainline_history")
    )
    if (
        not has_refresh_source
        and
        snapshot.get("cycle_calendar_rows")
        and snapshot.get("cycle_interpretation_rows")
        and snapshot.get("pivot_mainline_rows")
    ):
        return snapshot
    cycle_layer = derive_market_research_cycle_layer(snapshot, snapshot.get("state_machine") or {})
    for key, value in cycle_layer.items():
        if value and (has_refresh_source or not snapshot.get(key)):
            snapshot[key] = value
    return snapshot


def _market_base_lines(report_lines, snapshot=None):
    lines = _section_between(report_lines, "## 二、市场基底", "## 三、周期与主线")
    calibration = _market_fit_calibration(snapshot)
    fit_label = str(calibration.get("fit_label") or "").strip()
    if not lines or not fit_label:
        return lines
    if any("| 市场贴合度 |" in str(line) for line in lines):
        return lines

    evidence_text = str(calibration.get("evidence_text") or "").strip()
    fit_row_2col = f"| 市场贴合度 | {fit_label} |"
    fit_row_3col = f"| 市场贴合度 | {fit_label} | {evidence_text or '结合强势样本、主线命中和观察池命中判断。'} |"

    injected = []
    inserted = False
    for index, line in enumerate(lines):
        injected.append(line)
        next_line = str(lines[index + 1]) if index + 1 < len(lines) else ""
        if inserted:
            continue
        text = str(line)
        if text.startswith("| 项目 | 结论 | 依据 |") and next_line.startswith("|"):
            continue
        if text.startswith("|------|") and len(injected) >= 2:
            header = str(injected[-2])
            if header.startswith("| 项目 | 结论 | 依据 |"):
                injected.append(fit_row_3col)
                inserted = True
            elif header.startswith("| 项目 | 结论 |"):
                injected.append(fit_row_2col)
                inserted = True
        elif text.startswith("| 市场状态 |"):
            cells = [part.strip() for part in text.strip().strip("|").split("|")]
            injected.append(fit_row_3col if len(cells) >= 3 else fit_row_2col)
            inserted = True
    if inserted:
        return injected

    try:
        index = injected.index("### 2. 市场状态结论")
    except ValueError:
        injected.extend([
            "### 2. 市场状态结论",
            "| 项目 | 结论 | 依据 |",
            "|------|------|------|",
            fit_row_3col,
        ])
        return injected

    insert_at = index + 1
    while insert_at < len(injected) and not str(injected[insert_at]).startswith("| 项目 | 结论 |"):
        insert_at += 1
    if insert_at < len(injected):
        separator_at = insert_at + 1
        if separator_at < len(injected) and str(injected[separator_at]).startswith("|"):
            header = str(injected[insert_at])
            injected.insert(separator_at + 1, fit_row_3col if "依据" in header else fit_row_2col)
            return injected
    injected.insert(index + 1, fit_row_2col)
    return injected


def _market_structure_judgement(snapshot):
    snapshot = snapshot or {}
    judgement = snapshot.get("market_structure_judgement")
    if isinstance(judgement, dict) and judgement.get("summary_text"):
        return judgement
    return build_market_structure_judgement(data={}, market_research_snapshot=snapshot)


def _discipline_table(final_gate=None, position_level="", snapshot=None):
    final_gate = final_gate or {}
    position_state = _position_state_contract(snapshot, final_gate=final_gate)
    position_label = position_level or "先看市场底色"
    return [
        "## 一、交易纪律",
        "| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |",
        "|----------|----------|----------|----------|----------|",
        f"| {position_state['discipline']} | T日只给T+1观察资格；普通候选只等{SECOND_CONFIRM_WINDOW} MA5回踩收回 | 强核心全天强且偏离MA5不大，{TAIL_WINDOW}最多25%试仓 | 当天新买不可卖；买点失败仓次日先处理 | {position_label}；先分普通候选、强核心、已有旧仓、失败仓和退潮警戒，再决定参与 |",
        f"| 普通候选 | T+1 MA5回踩是基础入口；{OPENING_WINDOW}不抢，{SECOND_CONFIRM_WINDOW}确认站回MA5/VWAP/0轴才可做50% | 没有强核心身份时不做尾盘试仓 | 大高开远离MA5、大低开、收不回MA5或板块退潮都不做 | 分不清是不是强核心，退回MA5回踩，不用混合规则追高 |",
        f"| 强核心 | T+1混合龙头只用于板块核心、高辨识度、承接强；优先MA5回踩，其次健康低开转强 | 全天强、偏离不大且没有舒服回踩，{TAIL_WINDOW}只允许25%试仓 | 秒板/一字无换手、偏离MA5过远、低开后继续下杀都放弃 | 龙头不给舒服买点也不能无条件追，只在三窗口确认后参与 |",
        f"| 已有旧仓/做T | 强势周期用MA5入/MA7清/MA5T；50%底仓跟随，50%机动仓只在确认后做T | 尾盘卖可卖旧仓，隔夜尽量回到50%底仓 | 今天新增仓不能当天卖；做T卖的是昨天以前的旧仓 | 做T先降风险，确认后买回，不用第二笔证明第一笔 |",
        f"| 失败仓/退潮 | 当天MA5买入后收盘跌破MA5，次日先按买点失败仓处理 | 只给{SECOND_CONFIRM_WINDOW}一次站回MA5和分时均价的修复窗口 | 放量下杀、收盘低位、板块核心退潮或反抽不过线，优先处理可卖仓 | 退潮警戒切MA5清，必要时不新增参与，不继续套MA7容错 |",
        "",
    ]


def _opening_tone_lines(snapshot):
    tone_text = resolve_overtake_opening_tone_text(snapshot)
    if not tone_text:
        return []
    return [f"- **今日基调**: {tone_text}", ""]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _format_pct(value, signed=False):
    number = _safe_float(value, 0.0)
    prefix = "+" if signed and number >= 0 else ""
    return f"{prefix}{number:.2f}%"


def _monthly_mode_label(mode):
    labels = {
        "earnings_defense": "财报/季报高筛选月",
        "weak_market_defense": "弱市防守",
        "ordinary_attack": "普通进攻月",
        "strong_attack": "强主线进攻月",
        "attack_prepare": "进攻准备",
        "profit_protection": "收益保护",
    }
    return labels.get(str(mode or "").strip(), str(mode or "").strip() or "未识别")


def _conditional_defense_active(final_gate):
    final_gate = final_gate or {}
    return bool(
        final_gate.get("allow_attack_50_ready")
        and not final_gate.get("can_new_entry")
        and not final_gate.get("should_reduce")
    )


def _countertrend_defense_active(snapshot):
    snapshot = snapshot or {}
    summary = snapshot.get("mainline_turnover_summary") or {}
    state_machine = snapshot.get("state_machine") or {}
    text = " ".join(
        str(value or "")
        for value in (
            summary.get("share_trend_label"),
            summary.get("conclusion"),
            summary.get("action_text"),
            state_machine.get("style_label"),
            state_machine.get("style_reason"),
            state_machine.get("primary_action"),
            snapshot.get("rotation_label"),
            snapshot.get("rotation_reason"),
            snapshot.get("rotation_action"),
        )
    )
    return any(marker in text for marker in ("逆势试攻", "逆势攻击", "放量杀跌", "先防踩踏"))


def _grade_from_position_pct(position_pct):
    position_pct = int(_safe_float(position_pct, 0))
    if position_pct >= 50:
        return "100" if position_pct >= 100 else "50"
    return "0"


def _normalize_signal_grade(value):
    grade = str(value or "").strip().upper().replace("％", "%")
    if grade in ("100", "100%"):
        return "100"
    if grade in ("50", "50%"):
        return "50"
    if grade in ("0", "0%"):
        return "0"
    if grade == "A":
        return "100"
    if grade in ("A-", "B"):
        return "50"
    if grade == "C":
        return "0"
    return ""


def _selected_position_candidate(snapshot):
    selected = (snapshot or {}).get("selected_position_candidate") or {}
    return selected if isinstance(selected, dict) else {}


def _has_selected_position_candidate(snapshot):
    selected = _selected_position_candidate(snapshot)
    return bool(selected.get("name") or selected.get("code") or selected.get("stock_code"))


def _selected_candidate_sources(snapshot):
    selected = _selected_position_candidate(snapshot)
    if not selected:
        return []
    return [
        selected,
        selected.get("planned_participation") if isinstance(selected.get("planned_participation"), dict) else {},
        selected.get("participation_script") if isinstance(selected.get("participation_script"), dict) else {},
    ]


def _selected_candidate_position_pct(snapshot):
    positive_values = []
    fallback_values = []
    for source in _selected_candidate_sources(snapshot):
        for key in ("target_position_pct", "position_pct", "planned_position_pct", "attack_state"):
            raw_value = source.get(key)
            if raw_value in (None, ""):
                continue
            try:
                value = float(str(raw_value).strip().replace("%", "").replace("+", ""))
            except (TypeError, ValueError):
                continue
            value = int(value)
            if value >= 50:
                positive_values.append(value)
            else:
                fallback_values.append(value)
    if positive_values:
        return max(positive_values)
    if fallback_values:
        return max(fallback_values)
    return 0


def _selected_candidate_has_execution_window(snapshot):
    for source in _selected_candidate_sources(snapshot):
        if any(str(source.get(key) or "").strip() for key in ("participation_window", "buy_window", "entry_window", "execution_window")):
            return True
        steps = source.get("required_steps")
        if isinstance(steps, (list, tuple)) and any(str(step or "").strip() for step in steps):
            return True
    return False


def _selected_candidate_has_fallback_condition(snapshot):
    fallback_keys = (
        "fallback_state",
        "cancellation",
        "invalid_condition",
        "invalidation",
        "failure_condition",
        "stop_loss",
        "risk_window",
        "drop_condition",
    )
    fallback_markers = ("回到0", "继续0", "不满足", "不参与", "不做", "失效", "止损", "跌破")
    texts = []
    for source in _selected_candidate_sources(snapshot):
        for key in fallback_keys:
            text = str(source.get(key) or "").strip()
            if text:
                texts.append(text)
    joined = " ".join(texts)
    return any(marker in joined for marker in fallback_markers)


def _selected_candidate_has_execution_basis(snapshot):
    return bool(
        _selected_candidate_position_pct(snapshot) >= 50
        and _selected_candidate_has_execution_window(snapshot)
        and _selected_candidate_has_fallback_condition(snapshot)
    )


def _position_decision(snapshot):
    decision = (snapshot or {}).get("position_decision") or {}
    return decision if isinstance(decision, dict) else {}


def _monthly_rhythm_from_snapshot(snapshot):
    decision = _position_decision(snapshot)
    rhythm = decision.get("monthly_rhythm") or (snapshot or {}).get("monthly_rhythm") or {}
    return rhythm if isinstance(rhythm, dict) else {}


def _market_zero_stress_reason(snapshot=None, final_gate=None):
    snapshot = snapshot or {}
    final_gate = final_gate or {}
    state_machine = snapshot.get("state_machine") or {}
    if not isinstance(state_machine, dict):
        state_machine = {}
    monthly_rhythm = _monthly_rhythm_from_snapshot(snapshot)

    if (
        final_gate.get("market_ice_point")
        or state_machine.get("market_ice_point")
        or monthly_rhythm.get("market_ice_point")
    ):
        return "市场情绪冰点，可能未止跌，不继续参与"

    operation_state = str(final_gate.get("operation_state") or state_machine.get("operation_state") or "").strip()
    execution_bias = str(state_machine.get("execution_bias") or "").strip()
    pulse_stage = str(state_machine.get("pulse_stage") or "").strip()
    energy_state = str(state_machine.get("energy_state") or "").strip()
    if (
        operation_state == "撤退态"
        or execution_bias == "avoid"
        or pulse_stage in {"退潮", "踩踏", "恐慌"}
        or energy_state == "收缩防守"
    ):
        return "市场情绪退潮未止跌，可能还在释放风险，不继续参与"

    if monthly_rhythm.get("trend_invalid") or state_machine.get("trend_invalid"):
        return "趋势失效或承接未修复，不继续参与"

    return ""


def _compose_zero_market_reason(snapshot=None, final_gate=None, detail_reason=""):
    stress_reason = _market_zero_stress_reason(snapshot, final_gate)
    detail_reason = str(detail_reason or "").strip()
    if stress_reason and detail_reason and stress_reason not in detail_reason:
        return f"{stress_reason}；{detail_reason}"
    return detail_reason or stress_reason


def _compose_zero_no_execution_reason(snapshot=None, final_gate=None, basis_reason=""):
    stress_reason = _market_zero_stress_reason(snapshot, final_gate)
    if stress_reason:
        return f"{stress_reason}；指数图形与主攻线承接未修复，所以不给执行目标。"
    basis_reason = str(basis_reason or "").strip()
    if any(marker in basis_reason for marker in ("弱市场", "冰点", "趋势失效", "退潮", "未止跌")):
        return "市场条件未修复，只保留观察锚，不给执行目标。"
    return basis_reason


def _zero_position_exception_context(snapshot=None, final_gate=None, *, has_observation_target=False):
    snapshot = snapshot or {}
    final_gate = final_gate or {}
    decision = _position_decision(snapshot)
    monthly_rhythm = _monthly_rhythm_from_snapshot(snapshot)
    branch_20cm = decision.get("branch_20cm") or {}
    if not isinstance(branch_20cm, dict):
        branch_20cm = {}
    state_machine = snapshot.get("state_machine") or {}
    if not isinstance(state_machine, dict):
        state_machine = {}
    expected_50_preview = bool(
        has_observation_target
        and final_gate.get("allow_attack_50_ready")
        and _selected_candidate_has_execution_basis(snapshot)
        and not final_gate.get("market_ice_point")
        and not monthly_rhythm.get("market_ice_point")
        and not state_machine.get("market_ice_point")
    )

    if _old_position_priority_active(snapshot):
        reason = _text_value(_capital_priority_decision(snapshot).get("reason")) or "账户资金优先只处理旧仓，新强对象只保留观察锚。"
        if "只处理旧仓" not in reason:
            reason = f"{reason}；只处理旧仓，不新增参与。"
        return {
            "basis": reason,
            "reason": "账户资金优先只处理旧仓，不给新增执行目标",
            "attribution": "账户问题",
            "strong": True,
        }
    if _account_unbuyable_core_active(snapshot):
        return {
            "basis": "当前账户买不了一手。",
            "reason": "当前账户买不了一手，只保留观察锚",
            "attribution": "账户问题",
            "strong": True,
        }
    if _snapshot_has_key_data_gap(snapshot):
        return {
            "basis": "关键数据不完整。",
            "reason": "关键数据不完整，不能选出执行目标",
            "attribution": "数据问题",
            "strong": True,
        }
    if branch_20cm.get("direct_ban"):
        reason = str(branch_20cm.get("reason") or "高波动样本当前禁做。").strip()
        return {"basis": reason, "reason": reason, "attribution": "市场问题", "strong": True}
    monthly_reason = str(monthly_rhythm.get("reason") or decision.get("sizing_reason") or "").strip()
    if final_gate.get("should_reduce") and not expected_50_preview:
        basis = _compose_zero_market_reason(snapshot, final_gate, monthly_reason) or "市场要求先降风险，不新增参与。"
        reason = _compose_zero_no_execution_reason(snapshot, final_gate, basis)
        return {
            "basis": basis,
            "reason": reason,
            "attribution": "市场问题",
            "strong": True,
        }
    if _countertrend_defense_active(snapshot):
        return {
            "basis": "逆势攻击或放量下杀，先防踩踏。",
            "reason": "市场条件不支持，暂不保留观察锚",
            "attribution": "市场问题",
            "strong": True,
        }
    monthly_zero = (
        monthly_rhythm.get("target_role") == "defense_0"
        or int(_safe_float(monthly_rhythm.get("max_position_pct"), 50)) <= 0
    )
    market_zero = bool(
        final_gate.get("market_ice_point")
        or monthly_rhythm.get("market_ice_point")
        or state_machine.get("market_ice_point")
        or monthly_rhythm.get("trend_invalid")
        or state_machine.get("trend_invalid")
    )
    if (
        monthly_zero
        and not expected_50_preview
        and (market_zero or any(marker in monthly_reason for marker in ("弱市场", "冰点", "趋势失效")))
    ):
        basis = _compose_zero_market_reason(snapshot, final_gate, monthly_reason) or "弱市场、冰点或趋势失效时，只允许0%保护本金。"
        reason = _compose_zero_no_execution_reason(snapshot, final_gate, basis)
        return {"basis": basis, "reason": reason, "attribution": "市场问题", "strong": True}
    execution_bias = str(state_machine.get("execution_bias") or "").strip()
    if execution_bias == "reduce_only" and not expected_50_preview:
        return {
            "basis": "当前只处理旧仓，不新增参与。",
            "reason": "当前只处理旧仓，不给新增执行目标",
            "attribution": "账户问题",
            "strong": True,
        }
    if execution_bias == "avoid" and any(marker in monthly_reason for marker in ("退潮", "弱市场", "冰点", "趋势失效")):
        reason = monthly_reason or "主线退潮，先保护本金。"
        return {"basis": reason, "reason": reason, "attribution": "市场问题", "strong": True}
    if not has_observation_target:
        return {
            "basis": "候选全部未达参与资格，需要复盘候选筛选。",
            "reason": "候选池没有选出足够强的核心",
            "attribution": "决策问题",
            "strong": False,
        }
    return {
        "basis": "市场条件未到，只保留观察锚",
        "reason": "市场条件未到，只保留观察锚",
        "attribution": "市场问题",
        "strong": False,
    }


def _has_strong_zero_position_exception(snapshot=None, final_gate=None):
    context = _zero_position_exception_context(
        snapshot,
        final_gate=final_gate,
        has_observation_target=_has_selected_position_candidate(snapshot),
    )
    return bool(context.get("strong"))


def _promote_selected_candidate_to_standard_attack(snapshot):
    if not _has_selected_position_candidate(snapshot):
        return
    if not _selected_candidate_has_execution_basis(snapshot):
        return
    decision = dict(_position_decision(snapshot))
    selected_pct = _selected_candidate_position_pct(snapshot)
    target_pct = 100 if selected_pct >= 100 else 50
    signal_grade = "100" if target_pct >= 100 else "50"
    decision.update(
        {
            "signal_grade": signal_grade,
            "target_position_pct": target_pct,
            "participation_mode": decision.get("participation_mode") or ("full_100" if signal_grade == "100" else "attack_50_preview"),
            "sizing_reason": (
                "已有明确候选且没有弱市场、冰点、趋势失效、数据缺口或账户限制，按100%核心进攻；固定交易窗口不成立再回0%。"
                if signal_grade == "100"
                else "已有明确候选且没有弱市场、冰点、趋势失效、数据缺口或账户限制，按50%标准进攻预演；固定交易窗口不成立再回0%。"
            ),
            "front_page_promoted_from_zero": True,
        }
    )
    snapshot["position_decision"] = decision


def _position_state_contract(snapshot=None, final_gate=None):
    snapshot = snapshot or {}
    final_gate = final_gate or {}
    position_decision = _position_decision(snapshot)

    countertrend_defense = _countertrend_defense_active(snapshot)
    grade = _normalize_signal_grade(position_decision.get("signal_grade"))
    if not grade and "target_position_pct" in position_decision:
        grade = _grade_from_position_pct(position_decision.get("target_position_pct"))
    reasoning_decision = snapshot.get("reasoning_decision") or {}
    if (
        not grade
        and isinstance(reasoning_decision, dict)
        and reasoning_decision.get("action") == "conditional_entry"
        and reasoning_decision.get("handoff_buying_evidence") == "clear"
    ):
        grade = "50"
    if not grade and final_gate.get("can_new_entry"):
        grade = "50"
    if not grade and _conditional_defense_active(final_gate) and _has_unique_action_target(snapshot):
        target_pct = int(_safe_float(position_decision.get("target_position_pct"), 0))
        grade = "100" if target_pct >= 100 else "50"
    if not grade and _has_unique_action_target(snapshot) and not _has_strong_zero_position_exception(snapshot, final_gate=final_gate):
        target_pct = int(_safe_float(position_decision.get("target_position_pct"), 0))
        grade = "100" if target_pct >= 100 else "50"
    if not grade:
        grade = "0"
    if (
        grade == "0"
        and _has_selected_position_candidate(snapshot)
        and _selected_candidate_has_execution_basis(snapshot)
        and not _has_strong_zero_position_exception(snapshot, final_gate=final_gate)
    ):
        _promote_selected_candidate_to_standard_attack(snapshot)
        position_decision = _position_decision(snapshot)
        grade = _normalize_signal_grade(position_decision.get("signal_grade")) or _grade_from_position_pct(
            position_decision.get("target_position_pct")
        )
    if _tradable_proxy_priority_active(snapshot) and _resolution_display_target(snapshot):
        proxy_pct = int(_safe_float(_resolution_display_target(snapshot).get("target_position_pct"), 50))
        grade = "100" if proxy_pct >= 100 else "50"
    if grade in ("50", "100") and not _has_unique_action_target(snapshot):
        grade = "0"
    if grade in ("50", "100") and countertrend_defense:
        grade = "0"
    if grade in ("50", "100") and _account_unbuyable_core_active(snapshot) and not _tradable_proxy_priority_active(snapshot):
        grade = "0"

    contract = {
        "0": {
            "grade": "0",
            "discipline": "0%不参与",
            "execution_style": "0% / 不参与",
            "stock_state": "0%无合格标的",
            "stock_state_without_target": "0%无合格标的",
            "default_action": "0%不参与",
            "action_with_target": "0%：条件不满足，即使有观察对象也不新增",
            "action_without_target": "0%：没有合格标的就不参与",
        },
        "50": {
            "grade": "50",
            "discipline": "50%标准进攻",
            "execution_style": "50% / 标准进攻",
            "stock_state": "50%标准进攻对象",
            "stock_state_without_target": "50%等待合格对象",
            "default_action": "50%标准进攻，只做预演命中的合格对象",
            "action_with_target": "50%：只做合格对象，满足预演情境后执行，不满足回到0%",
            "action_without_target": "50%：没有合格对象前不下单，等市场缩到可做目标",
        },
        "100": {
            "grade": "100",
            "discipline": "100%核心进攻",
            "execution_style": "100% / 核心进攻",
            "stock_state": "100%唯一核心对象",
            "stock_state_without_target": "100%等待唯一核心对象",
            "default_action": "100%核心进攻，只做唯一核心对象",
            "action_with_target": "100%：唯一核心对象确认后进攻；跌破失效价才降级",
            "action_without_target": "100%：没有唯一核心对象就不满仓，等待真正核心出现",
        },
    }
    return contract.get(grade, contract["0"])


def _monthly_profit_cushion_text(monthly_rhythm):
    monthly_rhythm = monthly_rhythm or {}
    threshold = _format_pct(monthly_rhythm.get("profit_cushion_pct", 10.0), signed=True)
    if monthly_rhythm.get("month_return_pct") in (None, ""):
        return f"未记录（阈值{threshold}）"
    if monthly_rhythm.get("profit_cushion"):
        return f"已触发（阈值{threshold}）"
    return f"未触发（阈值{threshold}）"


def _monthly_profit_handling_text(monthly_rhythm, position_decision):
    monthly_rhythm = monthly_rhythm or {}
    if monthly_rhythm.get("month_return_pct") in (None, ""):
        return "未记录真实月度收益，不能按盈利垫调整仓位"
    if monthly_rhythm.get("profit_cushion") and monthly_rhythm.get("trend_invalid"):
        return "盈利垫后趋势失效，回到0%保护本金"
    if monthly_rhythm.get("profit_cushion"):
        return "盈利不是降档理由；趋势正确时允许持有/加仓"
    if int(_safe_float((position_decision or {}).get("target_position_pct"), 0)) >= 50:
        return "未到盈利垫，按进攻仓位三态执行"
    return "先看进攻仓位三态，不因浮盈浮亏临场改规则"


def _position_attack_grade_label(signal_grade):
    state = _normalize_signal_grade(signal_grade)
    return {
        "100": "100%",
        "50": "50%",
        "0": "0%",
    }.get(state, "0%")


def _monthly_rhythm_lines(snapshot):
    snapshot = snapshot or {}
    position_decision = snapshot.get("position_decision") or {}
    if not isinstance(position_decision, dict):
        position_decision = {}
    monthly_rhythm = position_decision.get("monthly_rhythm") or snapshot.get("monthly_rhythm") or {}
    if not isinstance(monthly_rhythm, dict):
        monthly_rhythm = {}
    if not position_decision and not monthly_rhythm:
        return []

    signal_grade = str(position_decision.get("signal_grade") or "").strip()
    if not signal_grade:
        target_position = int(_safe_float(position_decision.get("target_position_pct"), 0))
        signal_grade = _grade_from_position_pct(target_position)
    max_position = int(
        _safe_float(
            monthly_rhythm.get("max_position_pct", position_decision.get("target_position_pct", 0)),
            0,
        )
    )
    if (
        not _has_unique_action_target(snapshot)
        or _countertrend_defense_active(snapshot)
        or (_account_unbuyable_core_active(snapshot) and not _tradable_proxy_priority_active(snapshot))
    ):
        signal_grade = "0"
        max_position = 0
    reason = (
        position_decision.get("sizing_reason")
        or monthly_rhythm.get("reason")
        or "月度节奏只给仓位上限，最终仍看主线、核心对象和失效价。"
    )
    return [
        "### 月度攻防与进攻仓位",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 本月模式 | {_monthly_mode_label(monthly_rhythm.get('month_mode'))} |",
        f"| 当月收益 | {_format_pct(monthly_rhythm.get('month_return_pct'), signed=True) if monthly_rhythm.get('month_return_pct') not in (None, '') else '未记录'} |",
        f"| 模拟累计收益 | {_format_pct(monthly_rhythm.get('simulated_cumulative_return_pct'), signed=True) if monthly_rhythm.get('simulated_cumulative_return_pct') not in (None, '') else '未记录'} |",
        f"| 盈利垫 | {_monthly_profit_cushion_text(monthly_rhythm)} |",
        f"| 进攻仓位三态 | {_position_attack_grade_label(signal_grade)} |",
        f"| 明日最大仓位 | {max_position}% |",
        f"| 100%核心条件 | {'已满足' if position_decision.get('full_attack_ready') else '未满足'} |",
        f"| 收益处理 | {_monthly_profit_handling_text(monthly_rhythm, position_decision)} |",
        f"| 仓位理由 | {reason} |",
        "",
    ]


def _mainline_capacity_regime_lines(snapshot):
    summary = resolve_mainline_capacity_regime_summary(snapshot.get("mainline_turnover_summary") or {})
    if not summary:
        summary = resolve_mainline_capacity_regime_summary(snapshot)
    if not summary:
        summary = {
            "mainline_capacity": "容量待累计",
            "mainline_regime": "无主线",
            "primary_line": "暂无",
            "other_lines": "-",
            "confirmation_evidence": "资金未形成明确进攻方向",
            "sector_relationship_state": "暂未分出",
            "mainline_process": "无",
            "tomorrow_action": "不强行找主线，只保留异常观察",
        }
    return [
        "### 4. 主线容量与格局判断",
        "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |",
        "|----------|----------|--------|----------------|--------------|--------------|----------|----------|",
        (
            "| {mainline_capacity} | {mainline_regime} | {primary_line} | {other_lines} | "
            "{confirmation_evidence} | {sector_relationship_state} | {mainline_process} | {tomorrow_action} |"
        ).format(**summary),
        "",
    ]


def _mainline_attack_evidence_lines(snapshot):
    rows = resolve_mainline_attack_evidence_rows(snapshot)
    if not rows:
        rows = [
            {
                "sector_name": "暂无",
                "attack_state": "无主线",
                "net_inflow_rank": "-",
                "net_inflow_amount": "-",
                "limit_up_count": "-",
                "high_anchor_height": "-",
                "turnover_share_change": "-",
                "conclusion": "资金未形成明确进攻方向",
            }
        ]
    lines = [
        "#### 主线攻击证据",
        "| 板块 | 攻击状态 | 净流入排名 | 净流入 | 涨停数 | 高标高度 | 成交占比变化 | 结论 |",
        "|------|----------|------------|--------|--------|----------|--------------|------|",
    ]
    for row in rows[:3]:
        lines.append(
            "| {sector_name} | {attack_state} | {net_inflow_rank} | {net_inflow_amount} | {limit_up_count} | {high_anchor_height} | {turnover_share_change} | {conclusion} |".format(
                **row
            )
        )
    lines.append("")
    return lines


def _turnover_share_lines(snapshot):
    hot_rows = resolve_hot_sector_turnover_watch_rows(snapshot)
    hot_summary_text = resolve_hot_sector_turnover_watch_summary(snapshot)
    rows = resolve_turnover_share_trend_rows(snapshot)
    summary_text = str(
        (snapshot or {}).get("turnover_share_trend_summary")
        or ((snapshot or {}).get("mainline_turnover_summary") or {}).get("turnover_share_trend_summary")
        or ""
    ).strip()
    lines = [
        "### 5. 主线成交额占比趋势（近期热点板块连续跟踪）",
    ]
    if hot_summary_text:
        lines.append(f"> {hot_summary_text}")
        lines.append("")
    if hot_rows:
        lines.extend(render_hot_sector_turnover_watch_grouped_lines(hot_rows))
    else:
        lines.append("#### 近期热点板块成交额连续跟踪：暂无板块")
        lines.extend(
            [
                "| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |",
                "|------|------------|------------|------|------------|----------|------|",
            ]
        )
        lines.append("| 今日 | 数据暂缺 | - | 待累计 | 待累计 | 待累计 | 今天开始记录，后续日报自动累计 |")
        lines.append("")
    if rows:
        lines.append("#### 主线切换成交额记录")
        if summary_text:
            lines.append(f"> {summary_text}")
            lines.append("")
        lines.extend(
            [
                "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |",
                "|------|----------|------------|------------|------------|------|----------|------|",
            ]
        )
        for row in _display_latest_first(rows):
            lines.append(
                "| {date} | {cycle_mainline} | {daily_attack_line} | {mainline_turnover} | {market_turnover} | {share} | {share_change} | {interpretation} |".format(**row)
            )
        lines.append("")
    return lines


def _cycle_calendar_lines(snapshot):
    lines = build_market_research_snapshot_cycle_calendar_node(snapshot).get("lines", [])
    if lines:
        return lines
    return [
        "### 1. 周期日历主视图",
        "| 周次 | 一 | 二 | 三 | 四 | 五 |",
        "|------|------|------|------|------|------|",
        "| 当前周期 | 主线待累计 | 主线待累计 | 主线待累计 | 主线待累计 | 主线待累计 |",
    ]


def _cycle_interpretation_lines(snapshot):
    calibration = _market_fit_calibration(snapshot)
    cycle_note = calibration.get("cycle_note") or ""
    if cycle_note and snapshot.get("cycle_interpretation_rows"):
        snapshot = dict(snapshot)
        rows = []
        for row in snapshot.get("cycle_interpretation_rows") or []:
            if isinstance(row, dict):
                row = dict(row)
                row["interpretation"] = _append_sentence(row.get("interpretation"), cycle_note)
            rows.append(row)
        snapshot["cycle_interpretation_rows"] = rows
    lines = build_market_research_snapshot_cycle_interpretation_node(snapshot).get("lines", [])
    if lines:
        return lines
    summary = resolve_double_mainline_summary(snapshot.get("mainline_turnover_summary") or {}) or resolve_double_mainline_summary(snapshot) or {}
    mainline = summary.get("cycle_mainline") or (snapshot.get("state_machine") or {}).get("leading_line") or "主线待确认"
    return [
        "### 2. 周期解读",
        "| 周期 | 时间段 | 交易日数 | 攻击线 | 周期阶段 | 传递性 | 市场状态 | 明日验证点 | 周期解读 |",
        "|------|------|------|------|------|------|------|------|------|",
        (
            f"| 当前周期 | 待累计 | 待累计 | {mainline} | 待验证 | 待二次验证 | 待确认 | "
            f"验证是否二次攻击，不能由单日攻击自动升级周期主线 | "
            f"{_append_sentence('周期数据不足，只记录攻击线，后续日报继续验证传递性。', cycle_note)} |"
        ),
    ]


def _pivot_mainline_lines(snapshot):
    lines = build_market_research_snapshot_pivot_mainline_interpretation_node(snapshot).get("lines", [])
    if lines:
        return lines
    summary = resolve_double_mainline_summary(snapshot.get("mainline_turnover_summary") or {}) or resolve_double_mainline_summary(snapshot) or {}
    mainline = summary.get("cycle_mainline") or (snapshot.get("state_machine") or {}).get("leading_line") or "主线待确认"
    return [
        "### 3. 中枢与主线解读",
        "| 时间段 | 中枢级别 | 中枢区间 | 所在位置 | 对应主线 | 主线程度 | 演化状态 | 接替关系 | 结构解读 |",
        "|------|------|------|------|------|------|------|------|------|",
        f"| 待累计 | 日线中枢 | 待累计 | 待确认 | {mainline} | 待确认 | 待确认 | 待确认 | 中枢与主线映射数据不足，先不放大结论，只保留观察。 |",
    ]


def _capital_intent_lines(snapshot):
    lines = ["## 四、资金意图"]
    snapshot = _normalize_capital_intent_snapshot(snapshot)
    capital_lines = build_market_research_snapshot_lhb_capital_intent_node(snapshot).get("lines", [])
    if capital_lines:
        has_breakdown = "#### 资金意图拆解" in capital_lines
        for line in capital_lines:
            if line == "#### 资金意图拆解":
                lines.append("### 1. 资金意图拆解")
            elif line == "#### 龙虎榜资金状态":
                lines.append("### 2. 龙虎榜资金状态" if has_breakdown else "### 1. 龙虎榜资金状态")
            elif line == "#### 资金结论":
                lines.append("### 3. 资金结论" if has_breakdown else "### 2. 资金结论")
            else:
                lines.append(line)
    else:
        lines.extend([
            "### 1. 资金意图拆解",
            "| 板块攻击资金 | 强度反馈 | 龙虎榜验证 | 资金一致性 | 明日含义 |",
            "|--------------|----------|------------|------------|----------|",
            "| - | - | - | - | - |",
            "### 2. 龙虎榜资金状态",
            "| 资金强弱 | 资金力度 | 资金方向 | 资金意图 | 风格转向 | 事件属性 |",
            "|----------|----------|----------|----------|----------|----------|",
            "| - | - | - | - | - | - |",
            "### 3. 资金结论",
            "| 当前资金状态 | 对主线的态度 | 对明日动作的含义 |",
            "|--------------|--------------|------------------|",
            "| - | - | - |",
        ])
    lines.append("")
    return lines


def _normalize_capital_intent_snapshot(snapshot):
    snapshot = dict(snapshot or {})
    status = snapshot.get("lhb_capital_status")
    if isinstance(status, list):
        first = next((item for item in status if isinstance(item, dict)), {})
        snapshot["lhb_capital_status"] = {
            "capital_strength": first.get("capital_strength") or first.get("strength") or "-",
            "capital_intensity": first.get("capital_intensity") or first.get("state") or "-",
            "capital_direction": first.get("capital_direction") or first.get("direction") or "-",
            "capital_intent": first.get("capital_intent") or first.get("intent") or "-",
            "style_shift": first.get("style_shift") or first.get("style") or "-",
            "event_attribute": first.get("event_attribute") or first.get("event") or "龙虎榜资金行为",
        }
    conclusion = snapshot.get("capital_conclusion")
    if isinstance(conclusion, list):
        first = next((item for item in conclusion if isinstance(item, dict)), {})
        snapshot["capital_conclusion"] = {
            "current_capital_state": first.get("current_capital_state") or first.get("conclusion") or "-",
            "mainline_attitude": first.get("mainline_attitude") or first.get("evidence") or "-",
            "tomorrow_action_meaning": first.get("tomorrow_action_meaning") or first.get("action") or "-",
        }
    return snapshot


def _split_md_row(line):
    text = str(line or "").strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def _convert_legacy_core_table(table):
    if not table:
        return []
    converted = [
        "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
        "|------|------|----------|--------------|-----------|------|----------|----------|",
    ]
    for row in table[2:]:
        cells = _split_md_row(row)
        if len(cells) < 6:
            continue
        name, code, sector, reason, focus, qualification = cells[:6]
        converted.append(f"| {name} | {code} | {sector} | - | - | {focus} | {reason} | {qualification} |")
    return converted


def _text_value(*values):
    for value in values:
        if value is None:
            continue
        text = " ".join(str(value).replace("|", "｜").split()).strip()
        if text and text not in ("-", "暂无", "不做"):
            return text
    return ""


def _stock_like_from_resolution(value):
    if not isinstance(value, dict):
        return {}
    name = _text_value(value.get("name"), value.get("stock_name"))
    code = _text_value(value.get("code"), value.get("stock_code"), value.get("id"))
    if not (name or code):
        return {}
    return {
        "name": name,
        "code": code,
        "sector": _text_value(value.get("sector"), value.get("sector_name"), value.get("industry")),
        "direction": _text_value(value.get("direction"), value.get("theme"), value.get("line")),
        "role": _text_value(value.get("role"), value.get("render_role")),
        "identity": _text_value(value.get("identity"), value.get("cycle_identity"), value.get("market_identity")),
        "one_lot_amount": value.get("one_lot_amount"),
        "proxy_effect_type": _text_value(
            value.get("proxy_effect_type"),
            value.get("effect_type"),
            value.get("tracking_effect_type"),
        ),
        "proxy_reason": _text_value(value.get("proxy_reason"), value.get("reason")),
        "participation_window": normalize_participation_window(
            _text_value(value.get("participation_window"), value.get("buy_window"), value.get("entry_window"))
        ),
        "participation_window_type": _text_value(value.get("participation_window_type")),
        "required_steps": value.get("required_steps") if isinstance(value.get("required_steps"), list) else [],
        "condition": normalize_trading_time_text(_text_value(value.get("condition"))),
        "fallback_state": normalize_trading_time_text(_text_value(value.get("fallback_state"))),
    }


def _final_target_resolution(snapshot):
    resolution = (snapshot or {}).get("final_target_resolution") or {}
    return resolution if isinstance(resolution, dict) else {}


def _capital_priority_decision(snapshot):
    decision = _final_target_resolution(snapshot).get("capital_priority_decision") or {}
    return decision if isinstance(decision, dict) else {}


def _capital_priority(snapshot):
    return _text_value(_capital_priority_decision(snapshot).get("capital_priority"))


def _old_position_priority_active(snapshot):
    return _capital_priority(snapshot) in {"old_position_t", "old_position", "existing_position", "existing_position_t"}


def _tradable_proxy_priority_active(snapshot):
    return _capital_priority(snapshot) == "tradable_proxy"


def _new_entry_after_old_exit_active(snapshot):
    return _capital_priority(snapshot) == "new_entry_after_old_exit"


def _resolution_target(snapshot, key):
    return _stock_like_from_resolution(_final_target_resolution(snapshot).get(key))


def _resolution_watch_target(snapshot):
    if not (_old_position_priority_active(snapshot) or _tradable_proxy_priority_active(snapshot)):
        return {}
    resolution = _final_target_resolution(snapshot)
    for key in ("watch_target", "new_entry_target", "process_target", "ascii_trace_target"):
        target = _stock_like_from_resolution(resolution.get(key))
        if target:
            return target
    return {}


def _resolution_display_target(snapshot):
    if _old_position_priority_active(snapshot):
        return {}
    if not _tradable_proxy_priority_active(snapshot):
        return {}
    target = _resolution_target(snapshot, "display_target") or _resolution_target(snapshot, "tradable_proxy_target")
    return target


def _resolution_new_entry_target(snapshot):
    return _resolution_target(snapshot, "new_entry_target") or _resolution_target(snapshot, "process_target")


def _iter_unique_target_sources(snapshot):
    snapshot = snapshot or {}
    for key in ("candidate_pool", "core_candidates"):
        items = snapshot.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                yield item
    candidate_snapshot = snapshot.get("candidate_snapshot")
    if isinstance(candidate_snapshot, dict):
        for key in ("records", "full_candidate_pool"):
            items = candidate_snapshot.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    yield item


def _target_matches_candidate(target, candidate):
    target_code = _text_value(target.get("code"), target.get("id"))
    target_name = _text_value(target.get("name"))
    candidate_code = _text_value(candidate.get("code"), candidate.get("id"), candidate.get("stock_code"))
    candidate_name = _text_value(candidate.get("name"), candidate.get("stock_name"))
    if target_code and candidate_code and target_code == candidate_code:
        return True
    return bool(target_name and candidate_name and target_name == candidate_name)


def _enrich_unique_action_target(snapshot, target):
    if not isinstance(target, dict) or not (target.get("name") or target.get("code")):
        return target
    enriched = dict(target)
    for candidate in _iter_unique_target_sources(snapshot):
        if not _target_matches_candidate(enriched, candidate):
            continue
        enriched["code"] = _text_value(enriched.get("code"), candidate.get("code"), candidate.get("id"), candidate.get("stock_code"))
        enriched["name"] = _text_value(enriched.get("name"), candidate.get("name"), candidate.get("stock_name"))
        enriched["sector"] = _text_value(
            enriched.get("sector"),
            candidate.get("sector"),
            candidate.get("sector_name"),
            candidate.get("industry"),
            candidate.get("所属板块"),
        )
        enriched["direction"] = _text_value(
            enriched.get("direction"),
            candidate.get("direction"),
            candidate.get("theme"),
            candidate.get("line"),
            candidate.get("所属方向"),
        )
        break
    return enriched


def _unique_target_label(target):
    target = target or {}
    code = _text_value(target.get("code"), target.get("id"))
    name = _text_value(target.get("name"))
    if code and name:
        label = f"{code} {name}"
    else:
        label = name or code or "对象"
    descriptors = []
    for value in (_text_value(target.get("sector")), _text_value(target.get("direction"))):
        if value and value not in descriptors:
            descriptors.append(value)
    if descriptors:
        label = f"{label}（{'、'.join(descriptors)}）"
    return label


def _conditional_zero_action_text(target, position_decision=None):
    label = _unique_target_label(target)
    participation_window = normalize_participation_window(
        _text_value(target.get("participation_window"), target.get("buy_window"))
    )
    position_decision = position_decision if isinstance(position_decision, dict) else {}
    condition = normalize_trading_time_text(
        _text_value(position_decision.get("trigger_text"))
        or _text_value(target.get("condition"))
        or "主线承接 + 个股强弱重新确认"
    )
    fallback = normalize_trading_time_text(_text_value(target.get("fallback_state")) or "不满足继续0%")
    condition_text = condition if participation_window in condition else f"{participation_window}{condition}"
    return f"盘前0%；只看{label}，{condition_text}成立才保留观察，不能转成新增参与；{fallback}"


def _resolve_sniper_candidates(snapshot, candidate_snapshot):
    snapshot = snapshot or {}
    sources = []
    if isinstance(candidate_snapshot, dict):
        sources.append(candidate_snapshot.get("extreme_conviction_list"))
    sources.append(snapshot.get("extreme_conviction_list"))
    for key in ("candidate_selection", "step2_bundle", "execution_stage_context"):
        nested = snapshot.get(key)
        if isinstance(nested, dict):
            sources.append(nested.get("extreme_conviction_list"))
    for items in sources:
        if isinstance(items, list) and items:
            return items
    return []


def _effective_unique_action_target(snapshot):
    snapshot = snapshot or {}
    if _old_position_priority_active(snapshot):
        return {}
    if _countertrend_defense_active(snapshot):
        return {}
    resolved_display = _resolution_display_target(snapshot)
    if resolved_display:
        return _enrich_unique_action_target(snapshot, resolved_display)
    if "reasoning_decision" in snapshot:
        return _enrich_unique_action_target(snapshot, derive_unique_action_target_from_reasoning_decision(snapshot))
    target = snapshot.get("unique_action_target") or {}
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        return _enrich_unique_action_target(snapshot, target)
    selected = snapshot.get("selected_position_candidate") or {}
    position_decision = snapshot.get("position_decision") or {}
    if (
        isinstance(selected, dict)
        and (selected.get("name") or selected.get("code") or selected.get("stock_code"))
        and int(_safe_float((position_decision or {}).get("target_position_pct"), 0)) >= 50
    ):
        return _enrich_unique_action_target(
            snapshot,
            {
                "name": selected.get("name") or selected.get("stock_name"),
                "code": selected.get("code") or selected.get("stock_code"),
                "sector": selected.get("sector") or selected.get("sector_name"),
                "direction": selected.get("direction") or selected.get("theme"),
                "participation_window": normalize_participation_window(
                    selected.get("participation_window") or selected.get("buy_window")
                ),
                "participation_window_type": selected.get("participation_window_type") or "auction_reseal",
                "required_steps": [
                    normalize_trading_time_text(step)
                    for step in (selected.get("required_steps") or ["竞价表态", "开盘前几分钟承接", "回封/打板"])
                ],
                "fallback_state": normalize_trading_time_text(selected.get("fallback_state") or "条件不满足回到0%"),
                "condition": normalize_trading_time_text(selected.get("condition") or "竞价表态 + 开盘前几分钟 + 回封/打板"),
            },
        )
    return _enrich_unique_action_target(snapshot, derive_unique_action_target_from_reasoning_decision(snapshot))


def _conditional_observation_target(snapshot):
    snapshot = snapshot or {}
    resolved_watch = _resolution_watch_target(snapshot)
    if resolved_watch and not _tradable_proxy_priority_active(snapshot):
        return _enrich_unique_action_target(snapshot, resolved_watch)
    selected = snapshot.get("selected_position_candidate") or {}
    if not isinstance(selected, dict) or not (selected.get("name") or selected.get("code") or selected.get("stock_code")):
        return {}
    if _countertrend_defense_active(snapshot):
        return {}
    return _enrich_unique_action_target(
        snapshot,
        {
            "name": selected.get("name") or selected.get("stock_name"),
            "code": selected.get("code") or selected.get("stock_code"),
            "sector": selected.get("sector") or selected.get("sector_name"),
            "direction": selected.get("direction") or selected.get("theme"),
            "participation_window": normalize_participation_window(
                selected.get("participation_window") or selected.get("buy_window")
            ),
            "participation_window_type": selected.get("participation_window_type") or "structure_confirm",
            "required_steps": [normalize_trading_time_text(step) for step in (selected.get("required_steps") or [])],
            "fallback_state": normalize_trading_time_text(selected.get("fallback_state") or "不满足继续0%"),
            "condition": normalize_trading_time_text(selected.get("condition") or "主线承接 + 个股强弱重新确认"),
        },
    )


def _has_unique_action_target(snapshot):
    target = _effective_unique_action_target(snapshot)
    return isinstance(target, dict) and bool(target.get("name") or target.get("code"))


def _candidate_section_unique_object_label(
    snapshot,
    *,
    observation_target=None,
    has_observation_target=False,
    front_page=None,
    is_zero_participation=False,
):
    if is_zero_participation and has_observation_target:
        return _unique_target_label(observation_target)
    if _has_unique_action_target(snapshot):
        return _unique_target_label(_effective_unique_action_target(snapshot))
    front_page = front_page if isinstance(front_page, dict) else {}
    return front_page.get("unique_object") or "暂无"


def _snapshot_has_key_data_gap(snapshot):
    markers = ("关键数据不完整", "数据缺失", "missing_dependency", "degraded")

    def walk(value):
        if isinstance(value, dict):
            for nested in value.values():
                if walk(nested):
                    return True
            return False
        if isinstance(value, (list, tuple, set)):
            for nested in value:
                if walk(nested):
                    return True
            return False
        text = str(value or "")
        return any(marker in text for marker in markers)

    return walk(snapshot or {})


def _zero_position_no_execution_context(snapshot, final_gate=None, *, has_observation_target):
    return _zero_position_exception_context(
        snapshot,
        final_gate=final_gate,
        has_observation_target=has_observation_target,
    )


def _observation_anchor_lifecycle_rows(observation_target, *, has_observation_target):
    if not has_observation_target:
        return []
    condition = normalize_trading_time_text(
        _text_value((observation_target or {}).get("condition")) or "主线承接 + 个股强弱重新确认"
    )
    return [
        "| 观察锚性质 | 强弱参照，不是执行目标 |",
        f"| 恢复评估条件 | {condition} |",
        "| 观察锚去留 | 明日收盘前未满足恢复评估条件，移出前台观察 |",
    ]


def _sanitize_zero_position_front_page_language(lines):
    replacements = (
        ("勉强可参与", "防守观察"),
        ("谨慎参与", "防守观察"),
        ("核心里找参与资格", "核心承接"),
        ("继续寻找参与资格", "继续观察承接质量"),
        ("寻找参与资格", "观察承接质量"),
        ("找参与资格", "观察承接质量"),
        ("恢复参与资格", "恢复执行资格"),
        ("提高参与资格", "提高执行质量"),
        ("提高参与质量", "提高执行质量"),
        ("再给参与资格", "再评估执行资格"),
        ("参与只看主线、承接和个股结构同时成立。", "只观察主线、承接和个股结构是否同时修复。"),
        ("先等方向确认，再决定是否参与。", "先等方向确认，不新增参与。"),
    )
    sanitized = []
    for line in list(lines or []):
        text = str(line or "")
        for old, new in replacements:
            text = text.replace(old, new)
        sanitized.append(text)
    return sanitized


def _dedupe_top20_capacity_front_lines(lines):
    deduped = []
    seen_detailed_top20 = False
    for line in list(lines or []):
        text = str(line or "")
        if text.startswith("| Top20成交容量 |") and "Top20第20名" in text:
            if seen_detailed_top20:
                cells = text.strip().strip("|").split("|")
                if len(cells) >= 3:
                    cells[-1] = " 详见指数与市场底色表，只作成交容量背景。 "
                    text = "|" + "|".join(cells) + "|"
            else:
                seen_detailed_top20 = True
        deduped.append(text)
    return deduped


def _dedupe_repeated_front_long_cells(lines):
    deduped = []
    seen = set()
    preserve_reason_labels = {"0%原因", "不参与依据", "无执行目标原因"}
    for line in list(lines or []):
        text = str(line or "")
        if not text.startswith("|"):
            deduped.append(text)
            continue
        raw_cells = text.strip().strip("|").split("|")
        row_label = raw_cells[0].strip() if raw_cells else ""
        if row_label in preserve_reason_labels:
            deduped.append(text)
            continue
        changed = False
        cells = []
        for cell in raw_cells:
            norm = " ".join(str(cell or "").split())
            if len(norm) >= 40 and norm in seen:
                cells.append(" 同类历史行说明同上，只看本行数值变化 ")
                changed = True
            else:
                cells.append(cell)
                if len(norm) >= 40:
                    seen.add(norm)
        deduped.append("|" + "|".join(cells) + "|" if changed else text)
    return deduped


def _candidate_decision_contract_rows(snapshot, position_state, *, final_gate=None, observation_target, has_observation_target):
    snapshot = snapshot or {}
    position_state = position_state or {}
    grade = position_state.get("grade")
    rows = [
        f"| 明日仓位 | {position_state.get('discipline') or '0%不参与'} |",
    ]
    if grade == "0":
        context = _zero_position_no_execution_context(
            snapshot,
            final_gate=final_gate,
            has_observation_target=has_observation_target,
        )
        rows.extend(
            [
                "| 执行目标 | 无 |",
                f"| 不参与依据 | {context['basis']} |",
                f"| 无执行目标原因 | {context['reason']} |",
                f"| 责任归因 | {context['attribution']} |",
                *_observation_anchor_lifecycle_rows(
                    observation_target,
                    has_observation_target=has_observation_target,
                ),
            ]
        )
        return rows

    target = _effective_unique_action_target(snapshot)
    rows.extend(
        [
            f"| 执行目标 | {_unique_target_label(target) if isinstance(target, dict) and (target.get('name') or target.get('code')) else '无'} |",
            "| 观察锚 | 无 |",
            "| 无执行目标原因 | - |",
            "| 责任归因 | 市场与个股条件满足 |",
        ]
    )
    return rows


def _existing_position_summary(snapshot):
    summary = (snapshot or {}).get("existing_position_summary") or {}
    if not isinstance(summary, dict):
        return {}
    text = str(summary.get("summary") or "").strip()
    if not summary.get("has_position") and not text:
        return {}
    return {
        "has_position": True,
        "summary": text or "已有昨日持仓，先按持仓预案处理",
    }


def _account_capital_text(snapshot):
    profile = (snapshot or {}).get("account_profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    return str(profile.get("capital_text") or "约1w账户").strip() or "约1w账户"


def _account_profile(snapshot):
    profile = (snapshot or {}).get("account_profile") or {}
    return profile if isinstance(profile, dict) else {}


def _knowledge_hits(snapshot):
    hits = (snapshot or {}).get("knowledge_hits") or []
    return [hit for hit in hits if isinstance(hit, dict)]


def _knowledge_hit(snapshot, knowledge_id):
    for hit in _knowledge_hits(snapshot):
        if hit.get("knowledge_id") == knowledge_id:
            return hit
    return {}


def _account_unbuyable_core_active(snapshot):
    snapshot = snapshot or {}
    main_target = _t0_selected_target(snapshot)
    if not (main_target.get("name") or main_target.get("code")):
        return False
    account_profile = _account_profile(snapshot)
    cash_available = _safe_float(account_profile.get("cash_available"), 0)
    one_lot_amount = _safe_float(main_target.get("one_lot_amount"), 0)
    return bool(cash_available and one_lot_amount and one_lot_amount > cash_available)


def _position_context_provided(snapshot):
    snapshot = snapshot or {}
    if bool(snapshot.get("position_context_provided")):
        return True
    return "existing_position_summary" in snapshot


def _t0_target_label(target):
    target = target or {}
    name = _text_value(target.get("name"), target.get("stock_name"))
    code = _text_value(target.get("code"), target.get("stock_code"), target.get("id"))
    if name and code:
        return f"{name}({code})"
    return name or code or "暂无"


def _account_buy_zone_text(snapshot=None, target=None):
    snapshot = snapshot or {}
    target = target or {}
    selected = _selected_position_candidate(snapshot)
    decision = _position_decision(snapshot)
    for source in (target, selected, decision):
        if not isinstance(source, dict):
            continue
        line = _text_value(
            source.get("buy_ma_line"),
            source.get("entry_ma_line"),
            source.get("ma_buy_line"),
            source.get("buy_line"),
        )
        if line:
            return f"{line}附近" if "附近" not in line else line
    text = " ".join(
        part
        for part in (
            _text_value(decision.get("trigger_text")),
            _text_value(selected.get("condition")),
            _text_value(target.get("condition")),
        )
        if part
    )
    for line in ("MA7", "MA5", "MA3", "MA10"):
        if line in text:
            return f"{line}附近"
    return "MA5附近"


def _account_price_condition_text(snapshot, target, position_state):
    snapshot = snapshot or {}
    target = target or {}
    position_state = position_state or {}
    if position_state.get("grade") == "0":
        return "开盘-5%附近不新开；-3%低开也只观察能否站回0轴/VWAP/MA强弱线，不能转新增参与"
    selected = _selected_position_candidate(snapshot)
    decision = _position_decision(snapshot)
    trigger_raw = _text_value(decision.get("trigger_text"))
    trigger = str(trigger_raw or "").strip()
    if not trigger:
        window = normalize_participation_window(
            _text_value(
                target.get("participation_window"),
                selected.get("participation_window"),
                selected.get("buy_window"),
            )
        )
        window = str(window or SECOND_CONFIRM_WINDOW).replace("窗口条件", "").strip()
        trigger = f"{window or SECOND_CONFIRM_WINDOW}看承接"
    else:
        trigger = str(trigger).replace("窗口条件", "").strip()
    return f"买入区间：{_account_buy_zone_text(snapshot, target)}；{trigger}，不满足0%不参与"


def _no_t0_context_text(position_context_provided):
    return "无昨日持仓，不涉及T0" if position_context_provided else "持仓未输入，不能定义T0对象"


def _ensure_no_trade_fallback(text):
    text = str(text or "").strip()
    if not text:
        return "不满足回到0%不参与"
    if any(marker in text for marker in ("不参与", "不做", "空仓")):
        return text
    if "回到0%" in text or "继续0%" in text:
        return f"{text}不参与"
    return f"{text}，不做"


def _t0_selected_target(snapshot):
    selected = (snapshot or {}).get("selected_position_candidate") or {}
    if not isinstance(selected, dict) or not (selected.get("name") or selected.get("code") or selected.get("stock_code")):
        return {}
    return {
        "name": selected.get("name") or selected.get("stock_name"),
        "code": selected.get("code") or selected.get("stock_code"),
        "sector": selected.get("sector") or selected.get("sector_name"),
        "direction": selected.get("direction") or selected.get("theme"),
        "identity": selected.get("identity") or selected.get("cycle_identity") or selected.get("market_identity"),
        "one_lot_amount": selected.get("one_lot_amount"),
        "buy_ma_line": selected.get("buy_ma_line"),
        "participation_window": selected.get("participation_window") or selected.get("buy_window"),
        "condition": selected.get("condition"),
    }


def _t0_main_target(snapshot, position_state):
    snapshot = snapshot or {}
    position_state = position_state or {}
    if position_state.get("grade") == "0":
        if _countertrend_defense_active(snapshot):
            return {}, ""
        target = _resolution_watch_target(snapshot) or _t0_selected_target(snapshot)
        return (target, "条件观察") if target else ({}, "")

    if "reasoning_decision" in snapshot:
        target = derive_unique_action_target_from_reasoning_decision(snapshot)
        if isinstance(target, dict) and (target.get("name") or target.get("code")):
            return target, "固定交易窗口条件"
    target = snapshot.get("unique_action_target") or {}
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        return target, "固定交易窗口条件"
    target = _t0_selected_target(snapshot)
    return (target, "固定交易窗口条件") if target else ({}, "")


def _account_status_lines(snapshot=None, final_gate=None):
    snapshot = snapshot or {}
    position_state = _position_state_contract(snapshot, final_gate=final_gate)
    holding = _existing_position_summary(snapshot)
    main_target, main_role = _t0_main_target(snapshot, position_state)
    proxy_priority = _tradable_proxy_priority_active(snapshot)
    proxy_target = _resolution_display_target(snapshot) if proxy_priority else {}
    original_target = _resolution_new_entry_target(snapshot) if proxy_priority else {}
    has_main_target = isinstance(main_target, dict) and bool(main_target.get("name") or main_target.get("code"))
    no_holding_t0_target = bool(
        has_main_target
        and not holding
        and position_state.get("grade") != "0"
        and (
            _selected_candidate_has_execution_basis(snapshot)
            or _has_unique_action_target(snapshot)
        )
    )
    zero_position_reason = ""
    if position_state.get("grade") == "0":
        zero_context = _zero_position_no_execution_context(
            snapshot,
            final_gate=final_gate,
            has_observation_target=has_main_target or _has_selected_position_candidate(snapshot),
        )
        zero_position_reason = (
            _market_zero_stress_reason(snapshot, final_gate)
            or str(zero_context.get("basis") or zero_context.get("reason") or "").strip()
        )
    capital_text = _account_capital_text(snapshot)
    account_profile = _account_profile(snapshot)
    account_hit = _knowledge_hit(snapshot, "account.unbuyable-core-anchor")
    cash_available = _safe_float(account_profile.get("cash_available"), 0)
    unbuyable_target = original_target if proxy_priority and original_target else main_target
    one_lot_amount = _safe_float((unbuyable_target or {}).get("one_lot_amount"), 0)
    main_identity = str((unbuyable_target or {}).get("identity") or "").strip()
    actual_unbuyable_core = bool(
        (has_main_target or bool(proxy_target))
        and cash_available
        and one_lot_amount
        and one_lot_amount > cash_available
    )

    position_context_provided = _position_context_provided(snapshot)
    knowledge_basis_label = ""
    position_label = position_state.get("discipline") or "0%不参与"
    price_condition = _account_price_condition_text(snapshot, main_target, position_state)
    if actual_unbuyable_core and proxy_priority and proxy_target:
        account_constraint = (
            f"{capital_text}；先处理旧仓，目标标的买不了一手，改用ETF替代表达"
            if holding
            else f"{capital_text}；目标标的买不了一手，改用ETF替代表达"
        )
        proxy_effect = str(proxy_target.get("proxy_effect_type") or "").strip() or "同主线"
        original_label = _t0_target_label(original_target or main_target)
        proxy_label = _t0_target_label(proxy_target)
        tomorrow_action = (
            str(_capital_priority_decision(snapshot).get("reason") or "").strip()
            or f"目标标的{original_label}，小资金账户可用{proxy_label}替代"
        )
        position_label = position_state.get("discipline") or "50%标准进攻"
        primary_row_label = "明日执行目标"
        main_label = f"{proxy_label}：{proxy_effect}替代表达"
        secondary_row_label = "观察对象"
        identity_text = main_identity or "市场核心"
        backup_label = f"{original_label}：{identity_text}保留观察"
        new_entry_limit = "1"
        price_condition = _account_price_condition_text(snapshot, proxy_target, position_state)
    elif actual_unbuyable_core:
        account_constraint = f"{capital_text}；当前账户买不了一手"
        identity_text = main_identity or "核心身份"
        target_name = str((main_target or {}).get("name") or (main_target or {}).get("stock_name") or _t0_target_label(main_target)).strip()
        tomorrow_action = f"当前账户不参与；{target_name}仍保留{identity_text}观察"
        primary_row_label = "观察对象"
        main_label = f"{_t0_target_label(main_target)}：当前账户买不了一手，只保留观察"
        secondary_row_label = "T0对象"
        backup_label = _no_t0_context_text(position_context_provided)
        new_entry_limit = "0"
        knowledge_basis_label = str(account_hit.get("title") or "").strip()
    elif no_holding_t0_target:
        account_constraint = (
            f"{capital_text}；无昨日持仓先看T0对象"
            if position_context_provided
            else f"{capital_text}；未输入持仓，先确认旧仓再看T0对象"
        )
        position_label = position_state.get("discipline") or "50%标准进攻"
        tomorrow_action = (
            "只看T0主对象，买入区间命中才新开一手"
            if position_context_provided
            else "先确认旧仓情况，再看T0主对象"
        )
        new_entry_limit = "1"
        price_condition = _account_price_condition_text(snapshot, main_target, position_state)
        primary_row_label = "T0主对象"
        main_label = f"{_t0_target_label(main_target)}：{main_role}"
        if position_context_provided:
            secondary_row_label = "T0备用"
            backup_label = "暂无"
        else:
            secondary_row_label = "持仓确认"
            backup_label = "持仓未输入，执行前先确认旧仓情况"
    elif holding:
        if has_main_target and _new_entry_after_old_exit_active(snapshot) and position_state.get("grade") != "0":
            target_label = _t0_target_label(main_target)
            account_constraint = f"{capital_text}；先处理旧仓腾出资金"
            tomorrow_action = f"先处理旧仓，买{target_label}"
            primary_row_label = "旧仓处理"
            main_label = holding.get("summary") or "昨日持仓对象：先按持仓预案处理"
            secondary_row_label = "明日执行目标"
            backup_label = f"{target_label}：{main_role}"
            new_entry_limit = "资金释放后1"
            price_condition = _account_price_condition_text(snapshot, main_target, position_state)
        else:
            account_constraint = f"{capital_text}；已有昨日持仓优先处理"
            tomorrow_action = "先处理旧仓，不新增参与"
            primary_row_label = "T0主对象"
            main_label = holding.get("summary") or "昨日持仓对象：先按持仓预案处理"
            secondary_row_label = "T0备用"
            if has_main_target and _old_position_priority_active(snapshot):
                backup_label = f"{_t0_target_label(main_target)}：观察锚，不能转成新增参与"
            else:
                backup_label = f"{_t0_target_label(main_target)}：仅作观察对象" if has_main_target else "暂无"
            new_entry_limit = "0"
            price_condition = "已有仓按持仓预案处理；跌破失效价或09:50-10:10收不回先降风险"
    elif not position_context_provided:
        account_constraint = f"{capital_text}；未输入持仓，先确认旧仓再看T0对象"
        if position_state.get("grade") == "0":
            tomorrow_action = "0%不参与；只保留观察对象，不新开"
            new_entry_limit = "0"
            primary_row_label = "观察对象"
            main_label = f"{_t0_target_label(main_target)}：观察锚，不是T0" if has_main_target else "暂无"
        else:
            tomorrow_action = "先确认旧仓情况，再看明日执行目标"
            new_entry_limit = "1"
            primary_row_label = "明日执行目标"
            main_label = f"{_t0_target_label(main_target)}：{main_role}" if has_main_target else "暂无"
        secondary_row_label = "T0对象"
        backup_label = _no_t0_context_text(position_context_provided)
    else:
        account_constraint = f"{capital_text}；无昨日持仓先看明日对象"
        if position_state.get("grade") == "0":
            tomorrow_action = "0%不参与；只保留观察对象，不新开"
            new_entry_limit = "0"
            primary_row_label = "观察对象"
            main_label = f"{_t0_target_label(main_target)}：观察锚，不是T0" if has_main_target else "暂无"
        else:
            tomorrow_action = "只看明日执行目标，买入区间命中才新开一手"
            new_entry_limit = "1"
            primary_row_label = "明日执行目标"
            main_label = f"{_t0_target_label(main_target)}：{main_role}" if has_main_target else "暂无"
        secondary_row_label = "T0对象"
        backup_label = _no_t0_context_text(position_context_provided)

    lines = [
        "## 明日账户建议",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 账户约束 | {account_constraint} |",
        f"| 明日仓位 | {position_label} |",
    ]
    if zero_position_reason:
        lines.append(f"| 0%原因 | {zero_position_reason} |")
    lines.extend(
        [
            f"| 明日动作 | {tomorrow_action} |",
            f"| {primary_row_label} | {main_label} |",
            f"| {secondary_row_label} | {backup_label} |",
            f"| 价格条件 | {price_condition} |",
            f"| 新开仓上限 | {new_entry_limit} |",
            "| 今日不看 | T1/T2/T3只放附录观察，不同时盯多只，不为多个名单分散资金 |",
        ]
    )
    if knowledge_basis_label:
        lines.append(f"| 经验库依据 | {knowledge_basis_label} |")
    lines.append("")
    return lines


def _candidate_lines(report_lines, snapshot=None, final_gate=None):
    snapshot = snapshot or {}
    position_state = _position_state_contract(snapshot, final_gate=final_gate)
    candidate_snapshot = snapshot.get("candidate_snapshot")
    if not isinstance(candidate_snapshot, dict):
        candidate_snapshot = build_candidate_snapshot({}, market_research_snapshot=snapshot)
    front_page = candidate_snapshot.get("front_page") or {}
    is_zero_participation = position_state.get("grade") == "0"
    observation_target = _conditional_observation_target(snapshot) if is_zero_participation else {}
    has_observation_target = isinstance(observation_target, dict) and bool(
        observation_target.get("name") or observation_target.get("code")
    )
    has_unique_object = (
        _has_unique_action_target(snapshot)
        or has_observation_target
        or str(front_page.get("unique_object") or "").strip() not in ("", "-", "暂无", "不做")
    )
    if is_zero_participation and has_observation_target:
        stock_state = "0%条件观察"
    else:
        stock_state = position_state["stock_state"] if has_unique_object else position_state.get("stock_state_without_target", position_state["stock_state"])
    front_no_buy_reason = str(front_page.get("no_buy_reason") or "").strip()
    if is_zero_participation and front_no_buy_reason:
        front_no_buy_reason = front_no_buy_reason.replace("没有唯一对象", "没有观察锚").replace("有唯一对象", "有观察锚")
    if has_unique_object and (
        not front_no_buy_reason
        or "没有唯一对象" in front_no_buy_reason
        or (is_zero_participation and "没有观察锚" in front_no_buy_reason)
    ):
        no_buy_reason = "有观察锚，只等观察窗口确认；条件不满足继续0%" if is_zero_participation else "有核心对象，只等固定交易窗口内条件成立；条件不满足回到0%"
    else:
        no_buy_reason = front_no_buy_reason or ("没有观察锚，完整候选仅保留在附录和快照" if is_zero_participation else "没有核心对象，完整候选仅保留在附录和快照")
    backup_watch = front_page.get("backup_watch") if isinstance(front_page.get("backup_watch"), list) else []
    sniper_candidates = _resolve_sniper_candidates(snapshot, candidate_snapshot)
    if position_state.get("grade") == "0" or not has_unique_object:
        sniper_candidates = []
    effective_target = _effective_unique_action_target(snapshot)
    effective_target_code = _text_value(effective_target.get("code"), effective_target.get("stock_code")) if isinstance(effective_target, dict) else ""
    if effective_target_code:
        has_target_in_sniper = any(
            isinstance(item, dict)
            and _text_value(item.get("code"), item.get("stock_code")) == effective_target_code
            for item in sniper_candidates
        )
        if not has_target_in_sniper:
            sniper_candidates = []
    sniper_title = "明日候选观察" if is_zero_participation else "明日主买与补位"
    sniper_header = (
        "| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 观察复核 | 观察窗 |"
        if is_zero_participation
        else "| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 最终复核 | 参与窗 |"
    )
    lines = [
        "## 五、个股解读",
        "### 1. 个股裁决",
        "| 项目 | 结论 |",
        "|------|------|",
        *_candidate_decision_contract_rows(
            snapshot,
            position_state,
            final_gate=final_gate,
            observation_target=observation_target,
            has_observation_target=has_observation_target,
        ),
        f"| {'观察锚' if is_zero_participation else '唯一对象'} | {_candidate_section_unique_object_label(snapshot, observation_target=observation_target, has_observation_target=has_observation_target, front_page=front_page, is_zero_participation=is_zero_participation)} |",
        f"| 当前状态 | {stock_state} |",
        f"| 备用观察 | {front_page.get('backup_text') or '暂无'} |",
        f"| 今日不买原因 | {normalize_trading_time_text(no_buy_reason)} |",
        f"| 明日触发 | {normalize_trading_time_text(front_page.get('trigger_condition') or f'{SECOND_CONFIRM_LABEL} + 主线承接 + 个股突破或回踩确认')} |",
        f"| 明日失效 | {normalize_trading_time_text(front_page.get('failure_condition') or '主线回落 / 放量不承接')} |",
        "",
        f"### 2. {sniper_title}",
        sniper_header,
        "|------|------|--------|--------|--------|--------------|----------|--------|",
    ]
    sniper_rows = 0
    for item in sniper_candidates:
        if not isinstance(item, dict):
            continue
        role = str(item.get("sniper_role") or "").strip()
        if role not in ("明日主买对象", "明日补位对象"):
            continue
        label = _unique_target_label(item)
        risk_review = item.get("final_risk_review") or {}
        if isinstance(risk_review, dict):
            risk_status = str(risk_review.get("status") or "待复核").strip()
        else:
            risk_status = str(risk_review or "待复核").strip()
        lines.append(
            "| {role} | {label} | {tier} | {buy_line} | {sell_line} | {repair} | {risk_status} | {window} |".format(
                role=role,
                label=label,
                tier=item.get("leader_speed_tier") or "待判定",
                buy_line=item.get("buy_ma_line") or "-",
                sell_line=item.get("sell_ma_line") or "-",
                repair=item.get("acceptance_repair_required") or "等待承接修复",
                risk_status=risk_status,
                window=item.get("participation_window") or item.get("buy_window") or "09:50-10:10",
            )
        )
        sniper_rows += 1
    if not sniper_rows:
        lines.append("| 暂无 | - | - | - | - | - | - | - |")
    lines.extend([
        "",
        "### 3. 备用观察",
        "| 对象 | 所属方向 | 定位 | 触发条件 | 失效条件 |",
        "|------|----------|------|----------|----------|",
    ])
    if backup_watch:
        for item in backup_watch[:3]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {label} | {sector} | {role} | {trigger_condition} | {failure_condition} |".format(
                    label=item.get("label") or "观察对象",
                    sector=item.get("sector") or "-",
                role=normalize_trading_time_text(item.get("role") or "观察"),
                trigger_condition=normalize_trading_time_text(item.get("trigger_condition") or f"{SECOND_CONFIRM_WINDOW}确认承接"),
                failure_condition=normalize_trading_time_text(item.get("failure_condition") or "主线回落"),
            )
        )
    else:
        lines.append("| 暂无 | - | - | - | - |")
    lines.extend([
        "",
        "### 4. 个股结论",
        "| 前台显示 | 完整候选 | 动作原则 |",
        "|----------|----------|----------|",
        "| {display_policy} | 完整候选单保留在结构化快照与附录 | {principle} |".format(
            display_policy="只保留观察锚和备用观察" if is_zero_participation else "只保留唯一对象和备用观察",
            principle=(
                "最终0%时只观察，不做新增参与；观察锚重新成立也只作为盘中复核"
                if is_zero_participation
                else f"{OPENING_WINDOW}竞价表态、开盘前几分钟、打板/回封；{SECOND_CONFIRM_LABEL}，买后用失效价和单笔-5%底线处理风险"
            )
        ),
        "",
    ])
    return lines


def _unique_action_target_lines(snapshot, final_gate=None):
    position_state = _position_state_contract(snapshot, final_gate=final_gate)
    is_zero_participation = position_state.get("grade") == "0"
    observation_target = _conditional_observation_target(snapshot) if is_zero_participation else {}
    target = observation_target if observation_target else _effective_unique_action_target(snapshot)
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        label = _unique_target_label(target)
        participation_window = normalize_participation_window(target.get("participation_window"))
        participation_window_type = str(target.get("participation_window_type") or "").strip()
        required_steps = target.get("required_steps") or []
        if isinstance(required_steps, str):
            required_steps = [part.strip() for part in required_steps.split("/") if part.strip()]
        if not required_steps and participation_window_type and participation_window_type != "structure_confirm":
            required_steps = ["竞价表态", "开盘前几分钟承接", "回封/打板"]
        condition = " / ".join(normalize_trading_time_text(step) for step in required_steps if str(step).strip())
        if not condition:
            condition = normalize_trading_time_text(target.get("condition") or "")
        if not condition:
            condition = (
                f"主线确认 + 承接 + {SECOND_CONFIRM_LABEL}"
                if participation_window_type == "structure_confirm"
                else "竞价表态 + 开盘前几分钟 + 回封/打板"
            )
        default_fallback = "不满足回到0%"
        fallback_state = normalize_trading_time_text(str(target.get("fallback_state") or default_fallback).strip() or default_fallback)
    else:
        label = "暂无"
        participation_window = SECOND_CONFIRM_WINDOW
        condition = f"主线确认 + 承接 + {SECOND_CONFIRM_LABEL}未同时满足"
        participation_window_type = "structure_confirm"
        fallback_state = "不满足回到0%"
    if is_zero_participation:
        action_label = "只看观察锚" if observation_target else "只看观察对象"
        return [
            "| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |",
            "|--------------|------|------|------|--------------|",
            f"| {action_label} | {label} | {participation_window} | {condition} | {fallback_state} |",
            "",
        ]
    return [
        "| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |",
        "|--------------|------|------|------|--------------|",
        f"| 只看唯一对象 | {label} | {participation_window} | {condition} | {_ensure_no_trade_fallback(fallback_state)} |",
        "",
    ]


def _execution_plan_lines(snapshot=None, final_gate=None):
    decision_lines = render_reasoning_decision_lines((snapshot or {}).get("reasoning_decision"))
    position_state = _position_state_contract(snapshot, final_gate=final_gate)
    if position_state.get("grade") == "0":
        schedule_lines = [
            "| 09:30-09:35 | 只看跌停扩散、主攻线承接和观察锚是否出现 | 无 | 弱仓/错仓先降风险 | 观察，不抢开盘 |",
            "| 09:50-10:10 | 观察市场底色、主线承接、观察锚强弱 | 无 | 窗口内处理弱仓/错仓 | 条件未同时满足继续0% |",
            f"| {TAIL_WINDOW} | 只判断是否量化电风扇行情 | 无 | 非电风扇不新增参与 | 例外，不是常规 |",
        ]
    else:
        schedule_lines = [
            "| 09:30-09:35 | 开盘前几分钟主动资金、分时承接、板块同步 | 核心对象承接连续可按预演参与 | 弱仓/错仓先降风险 | 前几分钟进攻窗口 |",
            "| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 未走竞价/前几分钟路径的对象进入二次确认 | 窗口内处理弱仓/错仓 | 核心执行窗口 |",
            f"| {TAIL_WINDOW} | 只判断是否量化电风扇行情 | 仅电风扇行情例外，次日高开兑现 | 非电风扇不新增参与 | 例外，不是常规 |",
        ]
    return [
        "## 六、明日执行计划",
        *decision_lines,
        *_unique_action_target_lines(snapshot, final_gate=final_gate),
        "| 时间窗口 | 要看什么 | 买入资格 | 卖出/风控 | 结论 |",
        "|----------|----------|----------|-----------|------|",
        *schedule_lines,
        "",
    ]


def _final_summary_lines(report_lines, snapshot, final_gate=None):
    final_gate = final_gate or {}
    if _has_unconfirmed_attack_evidence(snapshot):
        cycle = "暂无确认主线"
        daily = "暂无确认主攻线"
    else:
        cycle = (snapshot.get("mainline_turnover_summary") or {}).get("current_mainline") or (snapshot.get("state_machine") or {}).get("leading_line") or "-"
        daily = (snapshot.get("mainline_turnover_summary") or {}).get("current_mainline") or cycle
    position_state = _position_state_contract(snapshot, final_gate=final_gate)
    action = position_state["default_action"]
    observation_target = _conditional_observation_target(snapshot) if position_state.get("grade") == "0" else {}
    target = observation_target if observation_target else _effective_unique_action_target(snapshot)
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        unique_target = f"观察锚：{_unique_target_label(target)}" if observation_target else _unique_target_label(target)
        one_line_action = (
            _conditional_zero_action_text(target, snapshot.get("position_decision"))
            if observation_target
            else position_state["action_with_target"]
        )
    else:
        unique_target = "暂无"
        one_line_action = position_state["action_without_target"]
    structure_judgement = _market_structure_judgement(snapshot)
    market_background = structure_judgement.get("tomorrow_rhythm") or "先看市场基底"
    action_reason_text = str(structure_judgement.get("action_reason_text") or "").strip()
    if action_reason_text and action_reason_text not in one_line_action:
        one_line_action = f"{one_line_action}；{action_reason_text}"
    return [
        "## 七、最终结论",
        "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |",
        "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
        f"| {action} | 不确定时不值得主动参与 | {cycle} | {daily} | {market_background} | {unique_target} | {position_state['execution_style']} | {one_line_action} |",
    ]


def render_front_page_v2(report_lines, *, target_date="", market_research_snapshot=None, final_gate=None, position_level=""):
    report_lines = list(report_lines or [])
    snapshot = _with_derived_cycle_layer(market_research_snapshot or {})
    lines = [f"# {target_date} a股市场分析" if target_date else "# a股市场分析", ""]
    lines.extend(_opening_tone_lines(snapshot))
    lines.extend(_account_status_lines(snapshot, final_gate=final_gate))
    lines.extend(_discipline_table(final_gate=final_gate, position_level=position_level, snapshot=snapshot))
    lines.extend(_monthly_rhythm_lines(snapshot))
    market_base = _market_base_lines(report_lines, snapshot)
    lines.extend(market_base or ["## 二、市场基底", "| 项目 | 结论 |", "|------|------|", "| 市场状态 | 待确认 |", ""])
    structure_lines = render_market_structure_section(_market_structure_judgement(snapshot))
    if structure_lines:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(structure_lines)
    if lines and lines[-1] != "":
        lines.append("")

    lines.append("## 三、周期与主线")
    _append_nonempty(lines, _cycle_calendar_lines(snapshot))
    _append_nonempty(lines, _cycle_interpretation_lines(snapshot))
    _append_nonempty(lines, _pivot_mainline_lines(snapshot))
    lines.extend(_mainline_capacity_regime_lines(snapshot))
    lines.extend(_mainline_attack_evidence_lines(snapshot))
    lines.extend(_turnover_share_lines(snapshot))
    lines.extend(_dragon_pullback_lines(snapshot))

    lines.extend(_capital_intent_lines(snapshot))
    lines.extend(_candidate_lines(report_lines, snapshot, final_gate=final_gate))
    lines.extend(_execution_plan_lines(snapshot, final_gate=final_gate))
    lines.extend(_final_summary_lines(report_lines, snapshot, final_gate=final_gate))
    if _position_state_contract(snapshot, final_gate=final_gate).get("grade") == "0":
        lines = _sanitize_zero_position_front_page_language(lines)
    lines = _dedupe_top20_capacity_front_lines(lines)
    lines = _dedupe_repeated_front_long_cells(lines)
    lines = [line for line in lines if not any(marker in str(line) for marker in FORBIDDEN_FRONT_PAGE_MARKERS)]
    return sanitize_front_page_text([normalize_trading_time_text(line) for line in lines])
