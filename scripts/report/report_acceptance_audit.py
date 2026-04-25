from __future__ import annotations

import json
import re
from pathlib import Path

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
    ("60分钟确认", ("60分钟确认", "60分钟K线确认")),
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
    "不直接给执行权",
    "条件未满足",
    "等10点确认",
    "待确认",
    "不开新仓",
    "不做",
)

REASONING_SURFACE_HEADING = "### 0. 推理裁决"
REASONING_REQUIRED_LABELS = ("裁决", "结论", "关键证据", "触发条件", "失败条件", "排除对象", "置信度")
REASONING_CHAIN_LEAK_MARKERS = ("chain-of-thought", "思维链", "完整推理链", "隐藏推理")

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
    for marker in REASONING_CHAIN_LEAK_MARKERS:
        if marker in front_text:
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


def _is_empty_target(value):
    text = str(value or "").strip()
    if text in ("", "-", "暂无", "不做"):
        return True
    if re.search(r"(?<!\d)\d{6}(?!\d)", text):
        return False
    return "暂无" in text or "不做" in text


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
    if execution_target != final_target:
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
    findings.extend(_audit_execution_windows(lines))
    findings.extend(_audit_execution_conditions(lines))
    findings.extend(_audit_appendix_duplicate_front_page_sections(lines))
    findings.extend(_audit_duplicate_no_trade(lines))
    findings.extend(_audit_degraded_fake_zero(lines))
    findings.extend(_audit_reasoning_surface(lines))
    findings.extend(_audit_unique_focus(lines))
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
