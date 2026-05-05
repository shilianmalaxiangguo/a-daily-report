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
    resolve_double_mainline_summary,
    resolve_turnover_share_trend_rows,
)


FORBIDDEN_FRONT_PAGE_MARKERS = ("### 🔬 市场研究快照", "Step 0")


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

    injected = []
    inserted = False
    for line in lines:
        injected.append(line)
        if not inserted and str(line).startswith("| 市场状态 |"):
            injected.append(f"| 市场贴合度 | {fit_label} |")
            inserted = True
    if inserted:
        return injected

    try:
        index = injected.index("### 2. 市场状态结论")
    except ValueError:
        injected.extend([
            "### 2. 市场状态结论",
            "| 项目 | 结论 |",
            "|------|------|",
            f"| 市场贴合度 | {fit_label} |",
        ])
        return injected

    insert_at = index + 1
    while insert_at < len(injected) and str(injected[insert_at]).startswith("|"):
        insert_at += 1
    injected.insert(insert_at, f"| 市场贴合度 | {fit_label} |")
    return injected


def _discipline_table(final_gate=None, position_level="", snapshot=None):
    final_gate = final_gate or {}
    position_state = _position_state_contract(snapshot, final_gate=final_gate)
    return [
        "## 一、交易纪律",
        "| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |",
        "|----------|----------|----------|----------|----------|",
        f"| {position_state['discipline']} | 09:50-10:10确认，10:00左右处理买卖 | 仅量化电风扇行情允许尾盘试错，次日高开兑现 | 单笔最晚-5%，不能大亏 | {position_level or '先看市场底色'}；先看周期主线，只在主线个股上做小亏小赚偶尔大赚 |",
        "",
    ]


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
        "earnings_defense": "财报/季报防守月",
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
        final_gate.get("allow_conditional_30")
        and not final_gate.get("can_new_entry")
        and not final_gate.get("should_reduce")
    )


def _grade_from_position_pct(position_pct):
    position_pct = int(_safe_float(position_pct, 0))
    if position_pct >= 80:
        return "A"
    if position_pct >= 50:
        return "A-"
    if position_pct >= 30:
        return "B"
    return "C"


def _normalize_signal_grade(value):
    grade = str(value or "").strip().upper()
    if grade in ("A", "A-", "B", "C"):
        return grade
    return ""


def _position_state_contract(snapshot=None, final_gate=None):
    snapshot = snapshot or {}
    final_gate = final_gate or {}
    position_decision = snapshot.get("position_decision") or {}
    if not isinstance(position_decision, dict):
        position_decision = {}

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
        grade = "B"
    if not grade and _conditional_defense_active(final_gate):
        grade = "B"
    if not grade and final_gate.get("can_new_entry"):
        grade = "A-"
    if not grade:
        grade = "C"

    contract = {
        "C": {
            "grade": "C",
            "discipline": "C档0%观察",
            "execution_style": "C档0% / 仅观察",
            "stock_state": "C档无对象",
            "stock_state_without_target": "C档无对象",
            "default_action": "C档观察，不开新仓",
            "action_with_target": "C档：不满足就空仓；即使有观察对象，也不做新增",
            "action_without_target": "C档：不满足就空仓；没有唯一对象不试错",
        },
        "B": {
            "grade": "B",
            "discipline": "B档30%条件试错",
            "execution_style": "B档30% / 10点确认后条件试错",
            "stock_state": "B档有条件试错对象",
            "stock_state_without_target": "B档条件等待",
            "default_action": "B档防守观察，10点确认后才评估30%条件试错",
            "action_with_target": "B档不是绝对空仓；B档：不满足不开；满足10点确认后最多30%条件试错",
            "action_without_target": "B档不是绝对空仓；B档：不满足不开；没有唯一对象先不下单，只在主线核心完成10点确认后评估30%条件试错",
        },
        "A-": {
            "grade": "A-",
            "discipline": "A-档50%执行",
            "execution_style": "A-档50% / 唯一对象执行",
            "stock_state": "A-档唯一执行对象",
            "stock_state_without_target": "A-档等待唯一对象",
            "default_action": "A-档只看唯一对象，60分钟确认后按50%执行",
            "action_with_target": "A-档：只看唯一对象，60分钟确认后按50%执行，不满足不做",
            "action_without_target": "A-档：没有唯一对象前不开仓，等待市场缩到一只",
        },
        "A": {
            "grade": "A",
            "discipline": "A档80%-100%买定离手",
            "execution_style": "A档80%-100% / 买定离手",
            "stock_state": "A档唯一核心对象",
            "stock_state_without_target": "A档等待唯一核心对象",
            "default_action": "A档唯一核心对象确认后80%-100%买定离手",
            "action_with_target": "A档：唯一核心对象确认后80%-100%买定离手；跌破失效价才降档",
            "action_without_target": "A档：没有唯一核心对象就不强行重仓，等待真正A档对象出现",
        },
    }
    return contract.get(grade, contract["C"])


def _monthly_profit_cushion_text(monthly_rhythm):
    monthly_rhythm = monthly_rhythm or {}
    threshold = _format_pct(monthly_rhythm.get("profit_cushion_pct", 10.0), signed=True)
    if monthly_rhythm.get("profit_cushion"):
        return f"已触发（阈值{threshold}）"
    return f"未触发（阈值{threshold}）"


def _monthly_profit_handling_text(monthly_rhythm, position_decision):
    monthly_rhythm = monthly_rhythm or {}
    if monthly_rhythm.get("profit_cushion") and monthly_rhythm.get("trend_invalid"):
        return "盈利垫后趋势失效，进入收益保护"
    if monthly_rhythm.get("profit_cushion"):
        return "盈利不是降档理由；趋势正确时允许持有/加仓"
    if str((position_decision or {}).get("signal_grade") or "").strip() in ("A", "A-"):
        return "未到盈利垫，按仓位攻击等级执行"
    return "先看仓位攻击等级，不因浮盈浮亏临场改规则"


def _position_attack_grade_label(signal_grade):
    return {
        "A": "A档80%-100%",
        "A-": "A-档50%",
        "B": "B档30%",
        "C": "C档0%",
    }.get(str(signal_grade or "").strip(), "C档0%")


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
        signal_grade = "A" if target_position >= 80 else "A-" if target_position >= 50 else "B" if target_position >= 30 else "C"
    max_position = int(
        _safe_float(
            monthly_rhythm.get("max_position_pct", position_decision.get("target_position_pct", 0)),
            0,
        )
    )
    reason = (
        position_decision.get("sizing_reason")
        or monthly_rhythm.get("reason")
        or "月度节奏只给仓位上限，最终仍看主线、唯一对象和失效价。"
    )
    return [
        "### 月度攻防与仓位等级",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 本月模式 | {_monthly_mode_label(monthly_rhythm.get('month_mode'))} |",
        f"| 当月收益 | {_format_pct(monthly_rhythm.get('month_return_pct', 0.0), signed=True)} |",
        f"| 盈利垫 | {_monthly_profit_cushion_text(monthly_rhythm)} |",
        f"| 仓位攻击等级 | {_position_attack_grade_label(signal_grade)} |",
        f"| 明日最大仓位 | {max_position}% |",
        f"| A级满仓条件 | {'已满足' if position_decision.get('full_attack_ready') else '未满足'} |",
        f"| 收益处理 | {_monthly_profit_handling_text(monthly_rhythm, position_decision)} |",
        f"| 仓位理由 | {reason} |",
        "",
    ]


def _double_mainline_lines(snapshot):
    summary = resolve_double_mainline_summary(snapshot.get("mainline_turnover_summary") or {})
    if not summary:
        summary = resolve_double_mainline_summary(snapshot)
    if not summary:
        summary = {"cycle_mainline": "-", "daily_attack_line": "-", "relationship": "主线待确认", "tomorrow_action": "10点确认，不满足空仓"}
    return [
        "### 4. 双层主线结论",
        "| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |",
        "|----------|------------|----------|----------|",
        "| {cycle_mainline} | {daily_attack_line} | {relationship} | {tomorrow_action} |".format(**summary),
        "",
    ]


def _turnover_share_lines(snapshot):
    rows = resolve_turnover_share_trend_rows(snapshot)
    lines = [
        "### 5. 主线成交额占比趋势",
        "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |",
        "|------|----------|------------|------------|------------|------|----------|------|",
    ]
    if rows:
        for row in rows:
            lines.append(
                "| {date} | {cycle_mainline} | {daily_attack_line} | {mainline_turnover} | {market_turnover} | {share} | {share_change} | {interpretation} |".format(**row)
            )
    else:
        lines.append("| 今日 | - | - | 数据暂缺 | - | 待累计 | 待累计 | 今天开始记录，后续日报自动累计 |")
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
        "| 周期 | 时间段 | 交易日数 | 主导主线 | 市场状态 | 周期解读 |",
        "|------|------|------|------|------|------|",
        f"| 当前周期 | 待累计 | 待累计 | {mainline} | 待确认 | {_append_sentence('周期数据不足，先记录当前主线，后续日报继续补齐趋势。', cycle_note)} |",
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
        for line in capital_lines:
            if line == "#### 龙虎榜资金状态":
                lines.append("### 1. 龙虎榜资金状态")
            elif line == "#### 资金结论":
                lines.append("### 2. 资金结论")
            else:
                lines.append(line)
    else:
        lines.extend([
            "### 1. 龙虎榜资金状态",
            "| 资金强弱 | 资金力度 | 资金方向 | 资金意图 | 风格转向 | 事件属性 |",
            "|----------|----------|----------|----------|----------|----------|",
            "| - | - | - | - | - | - |",
            "### 2. 资金结论",
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
        label = name or code or "唯一对象"
    descriptors = []
    for value in (_text_value(target.get("sector")), _text_value(target.get("direction"))):
        if value and value not in descriptors:
            descriptors.append(value)
    if descriptors:
        label = f"{label}（{'、'.join(descriptors)}）"
    return label


def _effective_unique_action_target(snapshot):
    snapshot = snapshot or {}
    if "reasoning_decision" in snapshot:
        return _enrich_unique_action_target(snapshot, derive_unique_action_target_from_reasoning_decision(snapshot))
    target = snapshot.get("unique_action_target") or {}
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        return _enrich_unique_action_target(snapshot, target)
    return _enrich_unique_action_target(snapshot, derive_unique_action_target_from_reasoning_decision(snapshot))


def _has_unique_action_target(snapshot):
    target = _effective_unique_action_target(snapshot)
    return isinstance(target, dict) and bool(target.get("name") or target.get("code"))


def _candidate_lines(report_lines, snapshot=None, final_gate=None):
    snapshot = snapshot or {}
    position_state = _position_state_contract(snapshot, final_gate=final_gate)
    candidate_snapshot = snapshot.get("candidate_snapshot")
    if not isinstance(candidate_snapshot, dict):
        candidate_snapshot = build_candidate_snapshot({}, market_research_snapshot=snapshot)
    front_page = candidate_snapshot.get("front_page") or {}
    has_unique_object = str(front_page.get("unique_object") or "").strip() not in ("", "-", "暂无", "不做")
    stock_state = position_state["stock_state"] if has_unique_object else position_state.get("stock_state_without_target", position_state["stock_state"])
    backup_watch = front_page.get("backup_watch") if isinstance(front_page.get("backup_watch"), list) else []
    lines = [
        "## 五、个股解读",
        "### 1. 个股裁决",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 唯一对象 | {_unique_target_label(_effective_unique_action_target(snapshot)) if _has_unique_action_target(snapshot) else front_page.get('unique_object') or '暂无'} |",
        f"| 当前状态 | {stock_state} |",
        f"| 备用观察 | {front_page.get('backup_text') or '暂无'} |",
        f"| 今日不买原因 | {front_page.get('no_buy_reason') or '没有唯一对象，完整候选仅保留在附录和快照'} |",
        f"| 明日触发 | {front_page.get('trigger_condition') or '10点确认 + 主线承接 + 个股突破或回踩确认'} |",
        f"| 明日失效 | {front_page.get('failure_condition') or '主线回落 / 放量不承接'} |",
        "",
        "### 2. 备用观察",
        "| 对象 | 所属方向 | 定位 | 触发条件 | 失效条件 |",
        "|------|----------|------|----------|----------|",
    ]
    if backup_watch:
        for item in backup_watch[:3]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {label} | {sector} | {role} | {trigger_condition} | {failure_condition} |".format(
                    label=item.get("label") or "观察对象",
                    sector=item.get("sector") or "-",
                    role=item.get("role") or "观察",
                    trigger_condition=item.get("trigger_condition") or "10点确认承接",
                    failure_condition=item.get("failure_condition") or "主线回落",
                )
            )
    else:
        lines.append("| 暂无 | - | - | - | - |")
    lines.extend([
        "",
        "### 3. 个股结论",
        "| 前台显示 | 完整候选 | 动作原则 |",
        "|----------|----------|----------|",
        "| 只保留唯一对象和备用观察 | 完整候选单保留在结构化快照与附录 | 10点附近确认，买点等60分钟，买后30分钟结构止损 |",
        "",
    ])
    return lines


def _unique_action_target_lines(snapshot):
    target = _effective_unique_action_target(snapshot)
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        label = _unique_target_label(target)
        condition = str(target.get("condition") or "主线确认 + 承接 + 60分钟确认").strip()
    else:
        label = "暂无"
        condition = "主线确认 + 承接 + 60分钟确认未同时满足"
    return [
        "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |",
        "|--------------|------|------|--------------|",
        f"| 只看唯一对象 | {label} | {condition} | 不做 |",
        "",
    ]


def _execution_plan_lines(snapshot=None):
    decision_lines = render_reasoning_decision_lines((snapshot or {}).get("reasoning_decision"))
    return [
        "## 六、明日执行计划",
        *decision_lines,
        *_unique_action_target_lines(snapshot),
        "| 时间窗口 | 要看什么 | 买入资格 | 卖出/风控 | 结论 |",
        "|----------|----------|----------|-----------|------|",
        "| 09:25-09:40 | 竞价强弱、主线核心是否被核、跌停扩散 | 默认无 | 有旧仓先看是否需要降风险 | 不抢 |",
        "| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 仅主线核心可进入观察买点 | 10:00左右处理弱仓/错仓 | 核心确认窗口 |",
        "| 10:00左右卖 | 弱仓、错仓、破结构仓位 | 无 | 该卖就卖，不做自救 | 防大亏 |",
        "| 10:00左右买 | 只看周期主线核心，且必须有承接 | 满足60分钟确认才允许 | 买后用30分钟结构止损 | 小仓或不开 |",
        "| 午后 | 看主线是否延续，不追轮动末端 | 默认谨慎 | 若走弱继续降风险 | 不扩大试错 |",
        "| 尾盘 | 只判断是否量化电风扇行情 | 仅电风扇行情例外，次日高开兑现 | 非电风扇不尾盘开新仓 | 例外，不是常规 |",
        "",
    ]


def _final_summary_lines(report_lines, snapshot, final_gate=None):
    final_gate = final_gate or {}
    cycle = (snapshot.get("mainline_turnover_summary") or {}).get("current_mainline") or (snapshot.get("state_machine") or {}).get("leading_line") or "-"
    daily = (snapshot.get("mainline_turnover_summary") or {}).get("current_mainline") or cycle
    position_state = _position_state_contract(snapshot, final_gate=final_gate)
    action = position_state["default_action"]
    target = _effective_unique_action_target(snapshot)
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        unique_target = _unique_target_label(target)
        one_line_action = position_state["action_with_target"]
    else:
        unique_target = "暂无"
        one_line_action = position_state["action_without_target"]
    return [
        "## 七、最终结论",
        "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
        "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
        f"| {action} | 不确定时不值得主动参与 | {cycle} | {daily} | 先看市场基底 | {unique_target} | {position_state['execution_style']} | {one_line_action} |",
    ]


def render_front_page_v2(report_lines, *, target_date="", market_research_snapshot=None, final_gate=None, position_level=""):
    report_lines = list(report_lines or [])
    snapshot = _with_derived_cycle_layer(market_research_snapshot or {})
    lines = [f"# {target_date} a股市场分析" if target_date else "# a股市场分析", ""]
    lines.extend(_discipline_table(final_gate=final_gate, position_level=position_level, snapshot=snapshot))
    lines.extend(_monthly_rhythm_lines(snapshot))
    market_base = _market_base_lines(report_lines, snapshot)
    lines.extend(market_base or ["## 二、市场基底", "| 项目 | 结论 |", "|------|------|", "| 市场状态 | 待确认 |", ""])
    if lines and lines[-1] != "":
        lines.append("")

    lines.append("## 三、周期与主线")
    _append_nonempty(lines, _cycle_calendar_lines(snapshot))
    _append_nonempty(lines, _cycle_interpretation_lines(snapshot))
    _append_nonempty(lines, _pivot_mainline_lines(snapshot))
    lines.extend(_double_mainline_lines(snapshot))
    lines.extend(_turnover_share_lines(snapshot))

    lines.extend(_capital_intent_lines(snapshot))
    lines.extend(_candidate_lines(report_lines, snapshot, final_gate=final_gate))
    lines.extend(_execution_plan_lines(snapshot))
    lines.extend(_final_summary_lines(report_lines, snapshot, final_gate=final_gate))
    lines = [line for line in lines if not any(marker in str(line) for marker in FORBIDDEN_FRONT_PAGE_MARKERS)]
    return sanitize_front_page_text(lines)
