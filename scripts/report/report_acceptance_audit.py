from __future__ import annotations

import json
import re
from pathlib import Path

from report.surface_wording import find_legacy_surface_wording

FRONT_PAGE_HEADINGS = [
    "## 一、交易纪律",
    "## 二、市场基底",
    "## 三、周期与主线",
    "## 四、资金意图",
    "## 五、个股解读",
    "## 六、明日执行计划",
    "## 七、最终结论",
]

APPENDIX_HEADING = "## 八、详细附录"

REQUIRED_EXECUTION_WINDOWS = [
    "09:25-09:40",
    "09:50-10:10",
    "10:00左右卖",
    "10:00左右买",
    "午后",
    "尾盘",
]

REQUIRED_EXECUTION_CONDITIONS = [
    ("10点确认", ("10点确认", "10点附近确认")),
    (
        "参与窗口",
        (
            "参与窗口",
            "参与窗",
            "竞价表态",
            "开盘前几分钟",
            "回封参与",
            "打板",
            "60分钟确认",
            "60分钟K线确认",
        ),
    ),
    ("30分钟结构止损", ("30分钟结构止损", "30分钟结构定止损", "30分钟定止损")),
    ("不做 / 不开新仓 / 空仓", ("不做", "不开新仓", "空仓")),
]

APPENDIX_DUPLICATE_FRONT_PAGE_HEADINGS = {
    "附录：一、交易纪律",
    "附录：二、市场基底",
    "附录：三、周期与主线",
    "附录：四、资金意图",
    "附录：五、个股解读",
    "附录：六、明日执行计划",
    "附录：七、最终结论",
}

DEGRADED_MARKERS = (
    "missing_dependency",
    "degraded",
    "source_status",
    "数据缺失",
    "数据不足",
    "降级",
    "缺失",
)

NO_TRADE_MARKERS = ("不做", "不开新仓", "空仓等待")

UNIQUE_FOCUS_EVIDENCE_FAMILIES = [
    ("主线一致性", ("主线", "周期主线", "当天主攻线")),
    ("承接", ("承接",)),
    ("资金痕迹", ("资金", "资金痕迹")),
    ("60分钟确认", ("60分钟确认", "60分钟K线确认")),
    ("排除/不做兜底", ("不满足", "不做", "不开新仓", "排除")),
]

UNIQUE_FOCUS_BUY_LABELS = ("唯一买入", "可执行候选", "买入")
UNIQUE_FOCUS_OBSERVATION_ONLY_MARKERS = (
    "只看，不买",
    "不给买入指令",
    "不构成买入指令",
    "仅观察",
    "只观察",
    "观察",
    "不买",
    "不直接给资格",
    "不直接给买入资格",
    "条件未满足",
    "等10点确认",
    "待确认",
    "不开新仓",
    "不做",
)

REASONING_SURFACE_HEADING = "### 0. 推理裁决"
REASONING_REQUIRED_LABELS = ("结论", "关键证据", "触发条件", "失败条件", "排除对象", "推理深度")
REASONING_CHAIN_LEAK_MARKERS = ("chain-of-thought", "思维链", "完整推理链", "隐藏推理")
SIMULATION_NOISE_MARKERS = (
    "MiroFish",
    "mirofish",
    "多智能体",
    "多智能体一致认为",
    "多智能体共识",
    "沙盘推演",
    "沙盘推演显示",
    "某情景下可能爆发",
    "模型认为胜率提高",
    "综合模拟后建议买入",
    "虽然规则未满足，但推演偏乐观",
)
THEORY_ACTION_MARKERS = (
    "能量释放，所以可以买",
    "能量释放，所以可以加仓",
    "能量释放，所以提高仓位",
    "群体行为共振，所以可以买",
    "群体行为共振，所以可以加仓",
    "群体行为共振，所以提高仓位",
)

THEORY_CONCEPT_TERMS = ("能量学", "能量释放", "群体行为")
THEORY_ACTION_CONTEXT_MARKERS = ("买", "加仓", "仓位", "候选资格", "资格")

THEORY_NOISE_MARKERS = (
    "能量学判断",
    "能量释放完成",
    "群体行为共振",
)


def _m(*parts):
    return "".join(parts)


LEGACY_POSITION_STYLE_MARKERS = (
    "空仓 / 短线确认",
    "空仓 / 短线 / 波段 / 尾盘量化例外",
    _m("B档", "30%"),
    _m("A-档", "50%"),
    _m("A", "档", "80%", "-100%"),
    _m("30%", "条件试错"),
)
POSITION_STYLE_GRADE_MARKERS = ("0% / 不参与", "50% / 标准进攻", "100% / 核心进攻")
MONTHLY_RHYTHM_HEADING = "### 月度攻防与进攻仓位"
MONTHLY_RHYTHM_REQUIRED_LABELS = ("本月模式", "当月收益", "盈利垫", "进攻仓位三态", "明日最大仓位")
POSITION_ATTACK_GRADE_LABELS = {"0%", "50%", "100%"}
POSITION_ATTACK_GRADE_MIN_POSITION = {
    "0%": 0,
    "50%": 50,
    "100%": 100,
}
LEGACY_CANDIDATE_SECTION_TITLES = ("### 1. 主线内观察候选", "### 1. 主线内可执行候选", "### 2. 跨线观察候选")
MAINLINE_CAPACITY_REGIME_HEADING = "### 4. 主线容量与格局判断"
MAINLINE_CAPACITY_REGIME_HEADER = "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |"
LEGACY_DOUBLE_MAINLINE_HEADER = "| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |"
MAINLINE_ATTACK_EVIDENCE_HEADING = "#### 主线攻击证据"
MAINLINE_ATTACK_EVIDENCE_HEADER = "| 板块 | 攻击状态 | 净流入排名 | 净流入 | 涨停数 | 高标高度 | 成交占比变化 | 结论 |"
__all__ = ["audit_report_markdown"]


def _finding(code, message, line=None):
    result = {"code": code, "message": message}
    if line is not None:
        result["line"] = line
    return result


def _lines(markdown):
    return str(markdown or "").splitlines()


def _front_page_lines(lines):
    front = []
    for line in lines:
        if line == APPENDIX_HEADING:
            break
        front.append(line)
    return front


def _appendix_lines(lines):
    for index, line in enumerate(lines):
        if line == APPENDIX_HEADING:
            return lines[index + 1 :]
    return []


def _section_after(lines, start_marker):
    try:
        start = list(lines).index(start_marker)
    except ValueError:
        return []
    section = []
    for line in list(lines)[start + 1 :]:
        text = str(line)
        if text.startswith("## ") or text.startswith("### "):
            break
        section.append(line)
    return section


def _split_md_row(line):
    text = str(line or "").strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def _parse_percent_int(value):
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return int(float(match.group(0)))
    except ValueError:
        return None


def _is_separator_cells(cells):
    joined = "".join(cells).replace(" ", "")
    return bool(joined) and set(joined) <= {"-", ":"}


def _audit_front_page_headings(lines):
    findings = []
    front = _front_page_lines(lines)
    headings = [line for line in front if line in FRONT_PAGE_HEADINGS]
    if headings != FRONT_PAGE_HEADINGS:
        findings.append(
            _finding(
                "front_page_heading_order",
                "front page headings must appear exactly once in canonical order before appendices",
            )
        )
    for heading in FRONT_PAGE_HEADINGS:
        if headings.count(heading) > 1:
            findings.append(_finding("duplicate_front_page_heading", f"duplicated front-page heading: {heading}"))
    return findings


def _extract_execution_window_labels(lines):
    labels = []
    in_window_table = False
    for line in _front_page_lines(lines):
        cells = _split_md_row(line)
        if cells and cells[0] == "时间窗口":
            in_window_table = True
            continue
        if not in_window_table:
            continue
        if not cells:
            break
        if _is_separator_cells(cells):
            continue
        labels.append(cells[0])
    return labels


def _audit_execution_windows(lines):
    labels = set(_extract_execution_window_labels(lines))
    findings = []
    for window in REQUIRED_EXECUTION_WINDOWS:
        if window not in labels:
            findings.append(
                _finding(
                    "execution_window_missing",
                    f"front-page execution plan is missing required window: {window}",
                )
            )
    return findings


def _audit_execution_conditions(lines):
    if not _extract_execution_window_labels(lines):
        return []
    front_text = "\n".join(_front_page_lines(lines))
    findings = []
    for label, markers in REQUIRED_EXECUTION_CONDITIONS:
        if any(marker in front_text for marker in markers):
            continue
        findings.append(
            _finding(
                "execution_condition_missing",
                f"front-page execution plan has time windows but is missing required actionable condition: {label}",
            )
        )
    return findings


def _audit_unique_action_target_contract(lines):
    findings = []
    for offset, line in enumerate(_front_page_lines(lines), 1):
        cells = _split_md_row(line)
        if len(cells) < 5 or cells[0] != "只看唯一对象":
            continue
        participation_window = cells[2]
        condition = cells[3]
        fallback = cells[4]
        is_fast_window = any(marker in participation_window for marker in ("竞价", "回封", "打板"))
        uses_structure_condition = "60分钟确认" in condition and not any(
            marker in condition for marker in ("竞价", "开盘前几分钟", "回封", "打板")
        )
        if is_fast_window and uses_structure_condition:
            findings.append(
                _finding(
                    "fast_window_polluted_by_structure_condition",
                    "fast participation windows must render auction/opening/reseal steps instead of legacy 60-minute structure condition",
                    line=offset,
                )
            )
        if is_fast_window and fallback != "不满足回到0%":
            findings.append(
                _finding(
                    "fast_window_fallback_not_zero",
                    "fast participation windows must fall back to 0% when the preplanned path does not trigger",
                    line=offset,
                )
            )
    return findings


def _audit_monthly_rhythm_section(lines):
    front = _front_page_lines(lines)
    findings = []
    for offset, line in enumerate(front, 1):
        cells = _split_md_row(line)
        if cells and cells[0] == "今日信号等级":
            findings.append(
                _finding(
                    "legacy_signal_grade_label",
                    "front page must use 进攻仓位三态 instead of 今日信号等级",
                    line=offset,
                )
            )
        if cells and cells[0] == "仓位攻击等级":
            findings.append(
                _finding(
                    "legacy_position_grade_label",
                    "front page must use 进攻仓位三态 instead of 仓位攻击等级",
                    line=offset,
                )
            )
    if MONTHLY_RHYTHM_HEADING not in front:
        findings.append(
            _finding(
                "monthly_rhythm_missing",
                "front page must render monthly attack/defense rhythm before stock selection",
            )
        )
        return findings
    section_text = "\n".join(_section_after(front, MONTHLY_RHYTHM_HEADING))
    section_lines = _section_after(front, MONTHLY_RHYTHM_HEADING)
    section_values = {}
    for line in section_lines:
        cells = _split_md_row(line)
        if len(cells) >= 2 and not _is_separator_cells(cells):
            section_values[cells[0]] = cells[1]
    for label in MONTHLY_RHYTHM_REQUIRED_LABELS:
        if f"| {label} |" not in section_text:
            findings.append(
                _finding(
                    "monthly_rhythm_field_missing",
                    f"monthly rhythm section is missing required field: {label}",
                )
            )
    attack_grade = section_values.get("进攻仓位三态")
    if attack_grade is not None and attack_grade not in POSITION_ATTACK_GRADE_LABELS:
        findings.append(
            _finding(
                "position_attack_grade_invalid",
                "进攻仓位三态 must be one of: 0%, 50%, 100%",
            )
        )
    max_position = _parse_percent_int(section_values.get("明日最大仓位"))
    min_position = POSITION_ATTACK_GRADE_MIN_POSITION.get(attack_grade)
    if max_position is not None and min_position is not None and min_position > max_position:
        findings.append(
            _finding(
                "position_attack_grade_exceeds_max_position",
                "进攻仓位三态 cannot require more position than 明日最大仓位 allows",
            )
        )
    return findings


def _audit_candidate_section_contract(lines):
    front = _front_page_lines(lines)
    findings = []
    for index, line in enumerate(front, 1):
        if line in LEGACY_CANDIDATE_SECTION_TITLES:
            findings.append(
                _finding(
                    "legacy_candidate_section_title",
                    f"front-page candidate section must use 个股裁决 / 备用观察 instead of legacy title: {line}",
                    line=index,
                )
            )
    if "## 五、个股解读" in front and "### 1. 个股裁决" not in front:
        findings.append(
            _finding(
                "candidate_verdict_missing",
                "front-page stock section must render 个股裁决 with 当前状态",
            )
        )
    stock_section = "\n".join(_section_after(front, "### 1. 个股裁决"))
    if stock_section and "| 当前状态 |" not in stock_section:
        findings.append(
            _finding(
                "candidate_state_missing",
                "front-page 个股裁决 must include 当前状态",
            )
        )
    return findings


def _audit_mainline_capacity_regime_contract(lines):
    front = _front_page_lines(lines)
    findings = []
    for index, line in enumerate(front, 1):
        if str(line).strip() == LEGACY_DOUBLE_MAINLINE_HEADER:
            findings.append(
                _finding(
                    "legacy_double_mainline_table",
                    "front-page mainline section must use 主线容量与格局判断 instead of legacy double-mainline table",
                    line=index,
                )
            )
    if MAINLINE_CAPACITY_REGIME_HEADING not in front or MAINLINE_CAPACITY_REGIME_HEADER not in front:
        findings.append(
            _finding(
                "mainline_capacity_regime_missing",
                "front-page cycle section must render 主线容量与格局判断",
            )
        )
    if MAINLINE_ATTACK_EVIDENCE_HEADING not in front or MAINLINE_ATTACK_EVIDENCE_HEADER not in front:
        findings.append(
            _finding(
                "mainline_attack_evidence_missing",
                "front-page cycle section must render 主线攻击证据",
            )
        )
    return findings


def _audit_legacy_surface_wording(lines):
    front_text = "\n".join(_front_page_lines(lines))
    findings = []
    for marker in find_legacy_surface_wording(front_text):
        findings.append(
            _finding(
                "legacy_surface_wording",
                f"front page must use 资格/条件/可做 wording instead of legacy marker: {marker}",
            )
        )
    return findings


def _strip_heading_marks(line):
    text = str(line or "").strip()
    while text.startswith("#"):
        text = text[1:].lstrip()
    return text


def _audit_appendix_duplicate_front_page_sections(lines):
    findings = []
    appendix = _appendix_lines(lines)
    appendix_start_line = len(lines) - len(appendix)
    for index, line in enumerate(appendix, 1):
        heading = _strip_heading_marks(line)
        if heading in APPENDIX_DUPLICATE_FRONT_PAGE_HEADINGS:
            findings.append(
                _finding(
                    "appendix_duplicate_front_page_section",
                    f"appendix mirrors front-page section heading: {heading}",
                    line=appendix_start_line + index,
                )
            )
    return findings


def _audit_duplicate_no_trade(lines):
    findings = []
    seen = {}
    for index, line in enumerate(lines, 1):
        text = str(line).strip()
        if not text or text.startswith("|") or text.startswith("#"):
            continue
        if not any(marker in text for marker in NO_TRADE_MARKERS):
            continue
        seen.setdefault(text, []).append(index)
    for text, indexes in seen.items():
        if len(indexes) > 1:
            findings.append(
                _finding(
                    "duplicate_no_trade_conclusion",
                    f"repeated no-trade conclusion: {text}",
                    line=indexes[1],
                )
            )
    return findings


def _audit_degraded_fake_zero(lines):
    findings = []
    for index, line in enumerate(lines, 1):
        text = str(line)
        if "0.00%" not in text:
            continue
        if any(marker in text for marker in DEGRADED_MARKERS):
            findings.append(
                _finding(
                    "degraded_fake_zero_percent",
                    "degraded or missing data must not render as a real 0.00%",
                    line=index,
                )
            )
    return findings


def _audit_reasoning_surface(lines):
    findings = []
    front = _front_page_lines(lines)
    front_text = "\n".join(front)
    front_text_lower = front_text.lower()
    for marker in REASONING_CHAIN_LEAK_MARKERS:
        if marker.lower() in front_text_lower:
            findings.append(
                _finding(
                    "reasoning_chain_leakage",
                    f"front page must not expose reasoning chain marker: {marker}",
                )
            )
    if REASONING_SURFACE_HEADING not in front:
        return findings
    section_text = "\n".join(_section_after(front, REASONING_SURFACE_HEADING))
    missing = [label for label in REASONING_REQUIRED_LABELS if f"| {label} |" not in section_text]
    if missing:
        findings.append(
            _finding(
                "reasoning_surface_incomplete",
                "reasoning surface is missing required rows: " + ", ".join(missing),
            )
        )
    return findings


def _audit_anti_noise_language(lines):
    findings = []
    front = _front_page_lines(lines)
    for index, line in enumerate(front, 1):
        text = str(line)
        simulation_codes_on_line = set()
        theory_codes_on_line = set()

        def append_simulation_finding(message):
            code = "simulation_noise_language"
            if code in simulation_codes_on_line:
                return
            simulation_codes_on_line.add(code)
            findings.append(_finding(code, message, line=index))

        def append_theory_finding(code, message):
            if code in theory_codes_on_line:
                return
            theory_codes_on_line.add(code)
            findings.append(_finding(code, message, line=index))

        for marker in SIMULATION_NOISE_MARKERS:
            if marker in text:
                append_simulation_finding(
                    f"front page must not use simulation/noise phrase: {marker}",
                )
        theory_action_found = False
        for marker in THEORY_ACTION_MARKERS:
            if marker in text:
                theory_action_found = True
                append_theory_finding(
                    "theory_driven_action_language",
                    f"front page must not use theory language as an action reason: {marker}",
                )
        if not theory_action_found and _has_theory_action_context(text):
            append_theory_finding(
                "theory_driven_action_language",
                "front page must not use theory concept language to justify action, qualification, or position changes",
            )
        for marker in THEORY_NOISE_MARKERS:
            if marker in text:
                append_theory_finding(
                    "theory_noise_language",
                    f"front page must not use theory/noise phrase: {marker}",
                )
        for term in THEORY_CONCEPT_TERMS:
            if term in text:
                append_theory_finding(
                    "theory_noise_language",
                    f"front page must not use unfieldized theory concept: {term}",
                )
    return findings


def _has_theory_action_context(text):
    return any(term in text for term in THEORY_CONCEPT_TERMS) and any(
        marker in text for marker in THEORY_ACTION_CONTEXT_MARKERS
    )


def _extract_execution_unique_target(lines):
    for line in lines:
        cells = _split_md_row(line)
        if len(cells) >= 4 and cells[0] == "只看唯一对象":
            return cells[1]
    return ""


def _extract_final_unique_target(lines):
    for index, line in enumerate(lines):
        header = _split_md_row(line)
        if "唯一重点对象" not in header:
            continue
        target_index = header.index("唯一重点对象")
        for candidate in lines[index + 1 :]:
            cells = _split_md_row(candidate)
            if not cells:
                continue
            if _is_separator_cells(cells):
                continue
            if len(cells) > target_index:
                return cells[target_index]
    return ""


def _extract_final_execution_style(lines):
    for index, line in enumerate(lines):
        header = _split_md_row(line)
        if "明日执行风格" not in header:
            continue
        style_index = header.index("明日执行风格")
        for candidate in lines[index + 1 :]:
            cells = _split_md_row(candidate)
            if not cells:
                continue
            if _is_separator_cells(cells):
                continue
            if len(cells) > style_index:
                return cells[style_index]
    return ""


def _audit_position_state_rendering(lines):
    front = _front_page_lines(lines)
    style = _extract_final_execution_style(front)
    if not style:
        return []
    if any(marker in style for marker in LEGACY_POSITION_STYLE_MARKERS):
        return [
            _finding(
                "legacy_position_style",
                "final summary must render 0/50/100 position state instead of legacy empty/short/30% style",
            )
        ]
    if not any(marker in style for marker in POSITION_STYLE_GRADE_MARKERS):
        return [
            _finding(
                "position_style_missing_grade",
                "final summary execution style must include 0/50/100 position state",
            )
        ]
    return []


def _is_empty_target(value):
    text = str(value or "").strip()
    if text in ("", "-", "暂无", "不做"):
        return True
    if re.search(r"(?<!\d)\d{6}(?!\d)", text):
        return False
    return "暂无" in text or "不做" in text


def _target_identity(value):
    text = str(value or "").strip()
    match = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
    if match:
        return match.group(1)
    return text


def _audit_unique_focus(lines):
    front = _front_page_lines(lines)
    findings = []
    execution_target = _extract_execution_unique_target(front)
    final_target = _extract_final_unique_target(front)
    execution_empty = _is_empty_target(execution_target)
    final_empty = _is_empty_target(final_target)
    if execution_empty != final_empty:
        findings.append(
            _finding(
                "unique_focus_mismatch",
                f"execution target {execution_target} conflicts with final summary target {final_target}",
            )
        )
        return findings
    if execution_empty and final_empty:
        findings.extend(_audit_empty_unique_focus_contradictions(front))
        return findings
    if _target_identity(execution_target) != _target_identity(final_target):
        findings.append(
            _finding(
                "unique_focus_mismatch",
                f"execution target {execution_target} conflicts with final summary target {final_target}",
            )
        )
        return findings
    findings.extend(_audit_concrete_unique_focus_evidence(front, execution_target))
    return findings


def _audit_concrete_unique_focus_evidence(front_lines, target):
    evidence_text = "\n".join(line for line in front_lines if not str(line).lstrip().startswith("#"))
    missing = []
    for label, markers in UNIQUE_FOCUS_EVIDENCE_FAMILIES:
        if any(marker in evidence_text for marker in markers):
            continue
        missing.append(label)
    if not missing:
        return []
    return [
        _finding(
            "unique_focus_evidence_missing",
            f"concrete unique target {target} is missing front-page decision evidence: {', '.join(missing)}",
        )
    ]


def _has_stock_reference(cells):
    text = " ".join(cells)
    return bool(re.search(r"(?<!\d)\d{6}(?!\d)", text))


def _has_observation_only_qualifier(cells):
    text = " ".join(cells)
    return any(marker in text for marker in UNIQUE_FOCUS_OBSERVATION_ONLY_MARKERS)


def _has_actionable_buy_label(cells, header):
    row_text = " ".join(cells)
    if any(label in row_text for label in UNIQUE_FOCUS_BUY_LABELS):
        return True
    for index, title in enumerate(header):
        if "明日资格" not in title or index >= len(cells):
            continue
        value = cells[index].strip()
        if value in ("有", "是", "具备"):
            return True
        if any(label in value for label in UNIQUE_FOCUS_BUY_LABELS):
            return True
        if "可执行" in value or "可买" in value:
            return True
    return False


def _audit_empty_unique_focus_contradictions(front_lines):
    findings = []
    header = []
    for offset, line in enumerate(front_lines):
        cells = _split_md_row(line)
        if not cells:
            header = []
            continue
        if _is_separator_cells(cells):
            continue
        next_cells = _split_md_row(front_lines[offset + 1]) if offset + 1 < len(front_lines) else []
        if _is_separator_cells(next_cells):
            header = cells
            continue
        if not _has_stock_reference(cells):
            continue
        if _has_observation_only_qualifier(cells):
            continue
        if not _has_actionable_buy_label(cells, header):
            continue
        findings.append(
            _finding(
                "unique_focus_contradiction",
                "unique target is empty, but the front page labels a concrete stock as buyable or executable",
                line=offset + 1,
            )
        )
    return findings


def audit_report_markdown(markdown):
    lines = _lines(markdown)
    findings = []
    findings.extend(_audit_front_page_headings(lines))
    findings.extend(_audit_monthly_rhythm_section(lines))
    findings.extend(_audit_candidate_section_contract(lines))
    findings.extend(_audit_mainline_capacity_regime_contract(lines))
    findings.extend(_audit_legacy_surface_wording(lines))
    findings.extend(_audit_execution_windows(lines))
    findings.extend(_audit_execution_conditions(lines))
    findings.extend(_audit_unique_action_target_contract(lines))
    findings.extend(_audit_appendix_duplicate_front_page_sections(lines))
    findings.extend(_audit_duplicate_no_trade(lines))
    findings.extend(_audit_degraded_fake_zero(lines))
    findings.extend(_audit_reasoning_surface(lines))
    findings.extend(_audit_anti_noise_language(lines))
    findings.extend(_audit_unique_focus(lines))
    findings.extend(_audit_position_state_rendering(lines))
    return {
        "passed": not findings,
        "findings": findings,
        "finding_count": len(findings),
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Audit a generated daily-report markdown file.")
    parser.add_argument("markdown_path")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    path = Path(args.markdown_path)
    result = audit_report_markdown(path.read_text(encoding="utf-8"))
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["passed"]:
            print("report_acceptance_audit: passed")
        else:
            for finding in result["findings"]:
                line_suffix = f":{finding['line']}" if "line" in finding else ""
                print(f"{finding['code']}{line_suffix} {finding['message']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
