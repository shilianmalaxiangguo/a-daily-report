from __future__ import annotations

import html
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

ZERO_POSITION_REQUIRED_EXECUTION_WINDOWS = [
    "09:25-09:40",
    "09:50-10:10",
    "10:00左右卖",
    "10:00左右观察",
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

ZERO_POSITION_UNIQUE_FOCUS_EVIDENCE_FAMILIES = [
    ("主线一致性", ("主线", "周期主线", "当天主攻线")),
    ("承接", ("承接",)),
    ("资金痕迹", ("资金", "资金痕迹")),
    ("观察窗口", ("观察窗", "观察窗口", "09:50-10:10")),
    ("排除/不做兜底", ("不满足", "不做", "不新增参与", "排除")),
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
ZERO_POSITION_ACTION_MARKERS = ("明日主买对象", "明日补位对象", "新增参与")
ZERO_POSITION_CURRENT_DECISION_ACTION_LABELS = ("主买对象", "补位对象")
ZERO_POSITION_LEGACY_TOMORROW_WORDING_MARKERS = (
    "明日可能反包",
    "关注埋伏",
    "明日买点预计算",
    "买入窗口",
    "买点窗口",
    "买点质量",
    "买点线",
    "可执行爆发",
    "真正可执行对象",
    "新仓止损",
    "10:00左右买",
    "尾盘开新仓",
    "回封/打板",
)
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
TOP50_TURNOVER_HEADER = "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |"
MAINLINE_TURNOVER_HEADER = "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |"
NEW_HIGH_FEEDBACK_HEADING = "### 3. 创新高趋势反馈"
MARKET_STATUS_HEADING = "### 2. 市场状态结论"
MARKET_STATUS_HEADER = "| 项目 | 结论 | 依据 |"
MARGIN_PRESSURE_FRONT_HEADER = "| 日期 | 融资余额 | 两市成交额 | 融资承接比 | 状态 |"
MARGIN_PRESSURE_APPENDIX_HEADER = "| 日期 | 融资余额 | 两市成交额 | 融资承接比 | 压力差 | 状态 | 较前日 |"
EXTREME_CONVICTION_TRACKING_HEADING = "**明日极度看好近25日跟踪表**"
EXTREME_CONVICTION_TRACKING_HEADER = "| 入选日 | 股票 | 代码 | 排名 | 所属方向 | 观察位窗口 | 复盘状态 | 历史复盘动作 | 作废线 | 记录ID |"
__all__ = ["audit_report_markdown"]

CHANLUN_TOMORROW_DECISION_HEADING = "明日抉择"
CHANLUN_ZERO_POSITION_ACTION_MARKERS = ("空仓等待", "不参与", "不新增参与", "禁止参与")


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


def _report_target_date(lines):
    for line in lines:
        match = re.search(r"#\s*(\d{4}-\d{2}-\d{2})\s+a股市场分析", str(line or ""), re.I)
        if match:
            return match.group(1)
    return ""


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


def _clean_html_cell(value):
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _extract_chanlun_tomorrow_decision_values(companion_html):
    text = str(companion_html or "")
    heading_match = re.search(r"<h2\b[^>]*>\s*明日抉择\s*</h2>", text, re.I)
    if not heading_match:
        return None
    table_match = re.search(r"<table\b[^>]*>(.*?)</table>", text[heading_match.end() :], re.I | re.S)
    if not table_match:
        return {}
    values = {}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table_match.group(1), re.I | re.S):
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.I | re.S)
        if len(cells) < 2:
            continue
        label = _clean_html_cell(cells[0])
        value = _clean_html_cell(cells[1])
        if label:
            values[label] = value
    return values


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
    front = _front_page_lines(lines)
    labels = set(_extract_execution_window_labels(lines))
    required_windows = (
        ZERO_POSITION_REQUIRED_EXECUTION_WINDOWS
        if _final_summary_is_zero_position(front)
        else REQUIRED_EXECUTION_WINDOWS
    )
    findings = []
    for window in required_windows:
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
    front = _front_page_lines(lines)
    front_text = "\n".join(front)
    required_conditions = list(REQUIRED_EXECUTION_CONDITIONS)
    if _final_summary_is_zero_position(front):
        required_conditions = [
            (label, markers)
            for label, markers in required_conditions
            if label not in {"30分钟结构止损", "参与窗口"}
        ]
    findings = []
    for label, markers in required_conditions:
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


def _extract_table_rows_after_header(lines, header_line):
    rows = []
    try:
        start = list(lines).index(header_line)
    except ValueError:
        return rows
    for line in list(lines)[start + 1 :]:
        cells = _split_md_row(line)
        if not cells:
            break
        if _is_separator_cells(cells):
            continue
        rows.append(cells)
    return rows


def _extract_all_table_rows_after_header(lines, header_line):
    source_lines = list(lines)
    tables = []
    for start, line in enumerate(source_lines):
        if line != header_line:
            continue
        rows = []
        for row_line in source_lines[start + 1 :]:
            cells = _split_md_row(row_line)
            if not cells:
                break
            if _is_separator_cells(cells):
                continue
            rows.append(cells)
        tables.append({"start": start, "rows": rows})
    return tables


def _has_recent_mainline_turnover_summary_near(lines, table_start):
    start = max(0, int(table_start or 0) - 4)
    nearby_text = "\n".join(list(lines)[start : int(table_start or 0)])
    return "近25个交易日主线成交额占比趋势" in nearby_text


def _has_real_mainline_turnover_value(value):
    text = str(value or "").strip()
    if not text or text in {"-", "待累计", "数据暂缺"}:
        return False
    return bool(re.search(r"\d", text))


def _mainline_turnover_row_has_unconfirmed_label_with_real_amount(cells):
    if len(cells) < 7:
        return False
    cycle_mainline = str(cells[1] or "").strip()
    daily_attack_line = str(cells[2] or "").strip()
    has_unconfirmed_label = cycle_mainline == "暂无确认主线" or daily_attack_line == "暂无确认主攻线"
    if not has_unconfirmed_label:
        return False
    return _has_real_mainline_turnover_value(cells[3]) or _has_real_mainline_turnover_value(cells[5])


def _audit_market_base_freshness(lines):
    target_date = _report_target_date(lines)
    if not target_date:
        return []
    front = _front_page_lines(lines)
    findings = []
    top50_rows = _extract_table_rows_after_header(front, TOP50_TURNOVER_HEADER)
    if top50_rows:
        row_dates = [cells[0] for cells in top50_rows if cells and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0])]
        if row_dates and target_date not in row_dates:
            findings.append(
                _finding(
                    "top50_target_date_missing",
                    f"Top50成交额占比趋势 must include report date {target_date}, got {row_dates[0]} to {row_dates[-1]}",
                )
            )
        if len(row_dates) < 25:
            findings.append(
                _finding(
                    "top50_recent_window_incomplete",
                    f"Top50成交额占比趋势 must render recent 25 trading rows, got {len(row_dates)}",
                )
            )

    mainline_tables = _extract_all_table_rows_after_header(lines, MAINLINE_TURNOVER_HEADER)
    if mainline_tables and target_date >= "2026-05-20":
        for table in mainline_tables:
            mainline_rows = table["rows"]
            row_dates = [cells[0] for cells in mainline_rows if cells and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0])]
            if not row_dates:
                continue
            table_line = table["start"] + 1
            if target_date not in row_dates:
                findings.append(
                    _finding(
                        "mainline_turnover_target_date_missing",
                        f"主线成交额占比趋势必须包含报告日期 {target_date}，当前日期范围是 {row_dates[0]} 到 {row_dates[-1]}",
                        line=table_line,
                    )
                )
            if len(row_dates) < 25:
                findings.append(
                    _finding(
                        "mainline_turnover_recent_window_incomplete",
                        f"主线成交额占比趋势必须渲染近25个交易日，当前只有 {len(row_dates)} 行",
                        line=table_line,
                    )
                )
            if not _has_recent_mainline_turnover_summary_near(lines, table["start"]):
                findings.append(
                    _finding(
                        "mainline_turnover_trend_summary_missing",
                        "主线成交额占比趋势必须给出近25个交易日解读",
                        line=table_line,
                    )
                )
            for offset, cells in enumerate(mainline_rows, start=table_line + 2):
                if _mainline_turnover_row_has_unconfirmed_label_with_real_amount(cells):
                    findings.append(
                        _finding(
                            "mainline_turnover_unconfirmed_label_with_real_amount",
                            "主线成交额占比趋势不能把已有成交额或占比的历史行标成暂无确认主线",
                            line=offset,
                        )
                    )

    new_high_section = _section_after(front, NEW_HIGH_FEEDBACK_HEADING)
    if new_high_section:
        section_text = "\n".join(new_high_section)
        if "最近可用因子日" in section_text:
            findings.append(
                _finding(
                    "new_high_previous_factor_date_substitute",
                    "创新高趋势反馈 must not substitute a previous factor date for the report date",
                )
            )
        has_target_row = any(str(line).startswith(f"| {target_date} |") for line in new_high_section)
        if not has_target_row:
            findings.append(
                _finding(
                    "new_high_target_date_missing",
                    f"创新高趋势反馈 must include report date row: {target_date}",
                )
            )
    return findings


def _audit_market_base_readability(lines):
    front = _front_page_lines(lines)
    findings = []
    for index, line in enumerate(front, 1):
        if str(line).strip() == MARKET_STATUS_HEADING:
            next_line = str(front[index]).strip() if index < len(front) else ""
            if next_line.startswith("| 市场贴合度 |"):
                findings.append(
                    _finding(
                        "market_fit_row_outside_status_table",
                        "市场贴合度必须进入市场状态结论表格，不能单独插在标题下面",
                        line=index + 1,
                    )
                )
    if MARKET_STATUS_HEADING in front:
        section = _section_after(front, MARKET_STATUS_HEADING)
        if MARKET_STATUS_HEADER not in section:
            findings.append(
                _finding(
                    "market_status_table_basis_missing",
                    "市场状态结论必须使用 项目/结论/依据 三列表格",
                )
            )
        section_text = "\n".join(section)
        if "| 融资承接压力 | 待累计 |" in section_text and MARGIN_PRESSURE_APPENDIX_HEADER in lines:
            findings.append(
                _finding(
                    "market_status_margin_pressure_stale",
                    "融资承接附录已有结构化数据时，市场状态结论不能继续写待累计",
                )
            )
    if MARGIN_PRESSURE_FRONT_HEADER in front:
        rows = _extract_table_rows_after_header(front, MARGIN_PRESSURE_FRONT_HEADER)
        dated_rows = [cells for cells in rows if cells and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0])]
        if len(dated_rows) < 10:
            findings.append(
                _finding(
                    "margin_pressure_recent_window_incomplete",
                    f"首页融资承接表必须展示近10日，当前只有 {len(dated_rows)} 行",
                )
            )
    if MARGIN_PRESSURE_APPENDIX_HEADER in lines:
        rows = _extract_table_rows_after_header(lines, MARGIN_PRESSURE_APPENDIX_HEADER)
        dated_rows = [cells for cells in rows if cells and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0])]
        if len(dated_rows) < 25:
            findings.append(
                _finding(
                    "margin_pressure_appendix_window_incomplete",
                    f"附录融资承接表必须展示完整25日，当前只有 {len(dated_rows)} 行",
                )
            )
    return findings


def _audit_extreme_conviction_tracking(lines):
    text = "\n".join(lines)
    if EXTREME_CONVICTION_TRACKING_HEADING not in text or EXTREME_CONVICTION_TRACKING_HEADER not in lines:
        return [
            _finding(
                "extreme_conviction_tracking_missing",
                "report must render 明日极度看好近25日跟踪表 from structured ledger data",
            )
        ]
    findings = []
    rows = _extract_table_rows_after_header(lines, EXTREME_CONVICTION_TRACKING_HEADER)
    if not rows:
        findings.append(
            _finding(
                "extreme_conviction_tracking_empty",
                "明日极度看好近25日跟踪表 must include at least one structured sample row",
            )
        )
        return findings
    elimination_markers = ("A杀淘汰", "A杀冷却", "A杀出清", "禁买", "a_kill", "a-kill")
    for row in rows:
        row_text = " ".join(row)
        row_text_lower = row_text.lower()
        if any(marker in row_text for marker in elimination_markers[:4]) or any(
            marker in row_text_lower for marker in elimination_markers[4:]
        ):
            findings.append(
                _finding(
                    "extreme_conviction_tracking_contains_a_kill",
                    "明日极度看好近25日跟踪表必须排除A杀样本",
                )
            )
            break
        if "若已买入" in row_text:
            findings.append(
                _finding(
                    "extreme_conviction_tracking_action_wording_not_historical",
                    "明日极度看好近25日跟踪表必须使用历史复盘口径，不能写成明日动作",
                )
            )
            break
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
        if len(cells) >= 5 and cells[0] == "只看条件观察对象":
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


def _final_summary_is_zero_position(lines):
    style = _extract_final_execution_style(lines)
    target = _extract_final_unique_target(lines)
    if "0% / 不参与" in style:
        return True
    for line in lines:
        cells = _split_md_row(line)
        if not cells or _is_separator_cells(cells):
            continue
        if any("0%不参与" in cell for cell in cells) and _is_empty_target(target):
            return True
    return False


def _is_zero_position_conflict_line(cells):
    row_text = " ".join(cells)
    if "不新增参与" in row_text:
        return False
    if not _has_stock_reference(cells):
        return False
    if len(cells) >= 2 and cells[0] in ZERO_POSITION_CURRENT_DECISION_ACTION_LABELS and not _is_empty_target(cells[1]):
        return True
    return any(marker in row_text for marker in ZERO_POSITION_ACTION_MARKERS)


def _audit_zero_position_tomorrow_action_consistency(lines):
    front = _front_page_lines(lines)
    if not _final_summary_is_zero_position(front):
        return []
    findings = []
    for offset, line in enumerate(front, 1):
        cells = _split_md_row(line)
        if not cells or _is_separator_cells(cells):
            continue
        if not _is_zero_position_conflict_line(cells):
            continue
        findings.append(
            _finding(
                "zero_position_tomorrow_action_conflict",
                "final summary is 0%不参与, but a front-page tomorrow action still names a concrete participation target",
                line=offset,
            )
        )
    for offset, line in enumerate(lines, 1):
        cells = _split_md_row(line)
        if not cells or _is_separator_cells(cells):
            continue
        if len(cells) < 2 or cells[0] not in ZERO_POSITION_CURRENT_DECISION_ACTION_LABELS:
            continue
        if _is_empty_target(cells[1]):
            continue
        findings.append(
            _finding(
                "zero_position_tomorrow_action_conflict",
                "final summary is 0%不参与, but a current decision panel still names a main or backup participation object",
                line=offset,
            )
        )
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        if not any(marker in text for marker in ZERO_POSITION_LEGACY_TOMORROW_WORDING_MARKERS):
            continue
        findings.append(
            _finding(
                "zero_position_legacy_tomorrow_wording",
                "final summary is 0%不参与, but report still contains old tomorrow-action wording",
                line=offset,
            )
        )
    return findings


def _audit_chanlun_tomorrow_decision_consistency(lines, companion_html):
    if companion_html is None:
        return []
    front = _front_page_lines(lines)
    if not _final_summary_is_zero_position(front):
        return []
    values = _extract_chanlun_tomorrow_decision_values(companion_html)
    if values is None:
        return [
            _finding(
                "chanlun_tomorrow_decision_missing",
                "final summary is 0%不参与, but companion HTML is missing 明日抉择",
            )
        ]
    max_position = _parse_percent_int(values.get("明日最大仓位"))
    participation = values.get("新增参与", "")
    final_action = values.get("最终执行条件", "")
    if (
        max_position == 0
        and "不参与" in participation
        and any(marker in final_action for marker in CHANLUN_ZERO_POSITION_ACTION_MARKERS)
    ):
        return []
    return [
        _finding(
            "chanlun_tomorrow_decision_conflict",
            "final summary is 0%不参与, but companion HTML 明日抉择 does not match 0%不参与",
        )
    ]


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
    findings.extend(
        _audit_concrete_unique_focus_evidence(
            front,
            execution_target,
            zero_position=_final_summary_is_zero_position(front),
        )
    )
    return findings


def _audit_concrete_unique_focus_evidence(front_lines, target, *, zero_position=False):
    evidence_text = "\n".join(line for line in front_lines if not str(line).lstrip().startswith("#"))
    missing = []
    families = ZERO_POSITION_UNIQUE_FOCUS_EVIDENCE_FAMILIES if zero_position else UNIQUE_FOCUS_EVIDENCE_FAMILIES
    for label, markers in families:
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


def audit_report_markdown(markdown, companion_html=None):
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
    findings.extend(_audit_market_base_freshness(lines))
    findings.extend(_audit_market_base_readability(lines))
    findings.extend(_audit_extreme_conviction_tracking(lines))
    findings.extend(_audit_reasoning_surface(lines))
    findings.extend(_audit_anti_noise_language(lines))
    findings.extend(_audit_unique_focus(lines))
    findings.extend(_audit_zero_position_tomorrow_action_consistency(lines))
    findings.extend(_audit_chanlun_tomorrow_decision_consistency(lines, companion_html))
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
    parser.add_argument("--companion-html", help="Optional companion 上证缠论 HTML file to audit with the markdown.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    path = Path(args.markdown_path)
    companion_html = None
    if args.companion_html:
        companion_html = Path(args.companion_html).read_text(encoding="utf-8")
    result = audit_report_markdown(path.read_text(encoding="utf-8"), companion_html=companion_html)
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
