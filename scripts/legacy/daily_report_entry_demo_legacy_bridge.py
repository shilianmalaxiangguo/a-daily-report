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


def build_legacy_sections(report_text, target_date=None):
    """Split an already-produced historical report without regenerating it.

    The former implementation imported the current entry and rebuilt the
    retired account report as a second production path.  Historical callers
    must provide text explicitly; the current entry never invokes this bridge.
    """
    if isinstance(report_text, dict):
        raise RuntimeError('旧完整报告分段桥不再生成日报；请传入已有历史文本')
    report = str(report_text or '')
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
