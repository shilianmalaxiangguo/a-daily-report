from __future__ import annotations

import json
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


def _split_md_row(line):
    text = str(line or "").strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


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
        joined = "".join(cells)
        if joined and set(joined) <= {"-"}:
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
            if set("".join(cells)) <= {"-"}:
                continue
            if len(cells) > target_index:
                return cells[target_index]
    return ""


def _is_empty_target(value):
    return str(value or "").strip() in ("", "-", "暂无", "不做")


def _audit_unique_focus(lines):
    execution_target = _extract_execution_unique_target(lines)
    final_target = _extract_final_unique_target(lines)
    if _is_empty_target(execution_target) or _is_empty_target(final_target):
        return []
    if execution_target != final_target:
        return [
            _finding(
                "unique_focus_mismatch",
                f"execution target {execution_target} conflicts with final summary target {final_target}",
            )
        ]
    return []


def audit_report_markdown(markdown):
    lines = _lines(markdown)
    findings = []
    findings.extend(_audit_front_page_headings(lines))
    findings.extend(_audit_execution_windows(lines))
    findings.extend(_audit_appendix_duplicate_front_page_sections(lines))
    findings.extend(_audit_duplicate_no_trade(lines))
    findings.extend(_audit_degraded_fake_zero(lines))
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
