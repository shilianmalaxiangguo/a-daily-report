import re


SECTION_KEYS = ("preamble", "environment", "observation", "execution", "review", "summary")


def _section_key_from_heading(line):
    match = re.match(r"^##\s+(.+?)\s*$", line.strip())
    if not match:
        return None
    heading = match.group(1).strip().lower()
    for key in SECTION_KEYS[1:]:
        if heading == key:
            return key
    return None


def _append_block(sections, key, lines):
    block = "\n".join(lines).strip()
    if block:
        sections[key] = block


def build_legacy_sections(data, target_date):
    try:
        import daily_report_entry_demo as legacy_demo
    except (ImportError, ModuleNotFoundError):
        import daily_report_render as legacy_render

        report = legacy_render.generate_markdown_report(data, target_date)
    else:
        report = legacy_demo.generate_markdown_report(data, target_date)

    report = report or ""
    if not report:
        return {}

    sections = {}
    lines = report.splitlines()
    current_key = "preamble"
    current_lines = []

    for line in lines:
        next_key = _section_key_from_heading(line)
        if next_key:
            _append_block(sections, current_key, current_lines)
            current_key = next_key
            current_lines = [line]
            continue

        current_lines.append(line)

    _append_block(sections, current_key, current_lines)
    return {key: sections[key] for key in SECTION_KEYS if key in sections}
