"""Lightweight markdown rendering helpers for the daily report pipeline."""

from __future__ import annotations

SECTION_KEYS = ["preamble", "environment", "observation", "execution", "review", "summary"]


def _coerce_sections(data):
    if not isinstance(data, dict):
        return {}

    sections = data.get("sections")
    if isinstance(sections, dict) and sections:
        return sections

    return {key: data.get(key, "") for key in SECTION_KEYS}


def generate_markdown_report_from_sections(sections):
    sections = sections or {}
    return "\n\n".join(
        str(sections.get(key, "") or "").strip() for key in SECTION_KEYS if sections.get(key)
    )


def generate_markdown_report(
    data,
    target_date,
    supplementary_perspective="",
    has_personal_positions=False,
    run_mode=None,
    persist_strategy_tracking=True,
):
    sections = _coerce_sections(data)
    return generate_markdown_report_from_sections(sections)
