#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render/output helpers for the A股日报 pipeline.

This module owns the public report rendering facade and the filesystem layout
for generated markdown artifacts. The heavy market-analysis logic still lives in
scripts/daily_report_entry_demo.py; this layer only orchestrates display-mode
switching, report variants, and persistence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
import types

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
try:
    import daily_report_analysis_utils as analysis_utils
except ImportError:  # pragma: no cover - local compatibility shim for this repo snapshot
    analysis_utils = types.SimpleNamespace(
        normalize_stock_code=lambda code: str(code or "").strip(),
    )

REPORT_VARIANT_FULL = "full"
REPORT_VARIANT_SUMMARY = "summary"

__all__ = [
    "REPORT_VARIANT_FULL",
    "REPORT_VARIANT_SUMMARY",
    "_get_report_output_path",
    "_get_stock_diagnostic_output_path",
    "_inject_report_variant_banner",
    "_render_report_with_display_mode",
    "generate_markdown_report_from_sections",
    "generate_markdown_report",
    "build_report_outputs",
    "save_report_output",
    "save_report_outputs",
    "save_stock_diagnostic_output",
]


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _reports_root() -> Path:
    return _module_dir().parent / "reports"


def _diagnostics_root() -> Path:
    return _reports_root() / "stock_diagnostics"


def _ensure_parent_dir(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _get_report_output_path(target_date: str, mode: str = LEDGER_MODE_FROZEN, variant: str = REPORT_VARIANT_FULL) -> str:
    reports_dir = _reports_root()
    if mode == LEDGER_MODE_REPLAY:
        reports_dir = reports_dir / "replay"
    reports_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
    variant_label = "完整版" if variant == REPORT_VARIANT_FULL else "执行摘要"
    return str(reports_dir / f"{target_date}_A股日报_{variant_label}{suffix}.md")


def _get_stock_diagnostic_output_path(target_date: str, stock_code: str, mode: str = LEDGER_MODE_FROZEN) -> str:
    diagnostics_dir = _diagnostics_root()
    if mode == LEDGER_MODE_REPLAY:
        diagnostics_dir = diagnostics_dir / "replay"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""

    return str(diagnostics_dir / f"{target_date}_{analysis_utils.normalize_stock_code(stock_code)}_单票诊断{suffix}.md")


def _inject_report_variant_banner(report_text: str, variant: str) -> str:
    label = "研究全量版" if variant == REPORT_VARIANT_FULL else "执行摘要版"
    detail = (
        "保留市场趋势、板块动向、热点结构、狙击手推导与账本回放。"
        if variant == REPORT_VARIANT_FULL
        else "只保留盘前最需要看的执行结论，但与全量版共用同一条正式决策链。"
    )
    lines = report_text.splitlines()
    insert_at = 3 if len(lines) >= 3 else len(lines)
    lines[insert_at:insert_at] = [
        f"> **阅读模式**：{label}",
        f"> **用途**：{detail}",
        "",
    ]
    return "\n".join(lines)


def _render_report_with_display_mode(
    display_mvp_mode: bool,
    data: Dict[str, Any],
    target_date: str,
    supplementary_perspective: str = "",
    has_personal_positions: bool = False,
    run_mode: str = LEDGER_MODE_FROZEN,
    persist_strategy_tracking: bool = True,
) -> str:
    import daily_report_entry_demo as _demo

    original_display_mode = getattr(_demo, "DISPLAY_MVP_MODE", False)
    _demo.DISPLAY_MVP_MODE = bool(display_mvp_mode)
    try:
        return _demo.generate_markdown_report(
            data,
            target_date,
            supplementary_perspective=supplementary_perspective,
            has_personal_positions=has_personal_positions,
            run_mode=run_mode,
            persist_strategy_tracking=persist_strategy_tracking,
        )
    finally:
        _demo.DISPLAY_MVP_MODE = original_display_mode


def generate_markdown_report_from_sections(sections):
    ordered_keys = ["preamble", "environment", "observation", "execution", "review", "summary"]
    return "\n\n".join(str(sections.get(key, "") or "").strip() for key in ordered_keys if sections.get(key))


def _extract_sections(data):
    if not isinstance(data, dict):
        return {}

    sections = data.get("sections")
    if isinstance(sections, dict) and sections:
        return sections

    extracted = {key: data.get(key, "") for key in ("preamble", "environment", "observation", "execution", "review", "summary")}
    return {key: value for key, value in extracted.items() if value}


def generate_markdown_report(
    data: Dict[str, Any],
    target_date: str,
    supplementary_perspective: str = "",
    has_personal_positions: bool = False,
    run_mode: str = LEDGER_MODE_FROZEN,
    persist_strategy_tracking: bool = True,
) -> str:
    """Render the default report text.

    This is a thin facade over the legacy implementation so callers can depend
    on a smaller, stable module instead of the huge entry script.
    """

    sections = _extract_sections(data)
    if sections:
        return generate_markdown_report_from_sections(sections)

    import daily_report_entry_demo as _demo
    return _demo.generate_markdown_report(
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        persist_strategy_tracking=persist_strategy_tracking,
    )


def build_report_outputs(
    data: Dict[str, Any],
    target_date: str,
    supplementary_perspective: str = "",
    has_personal_positions: bool = False,
    run_mode: str = LEDGER_MODE_FROZEN,
    position_report_text: str = "",
):
    full_report = _render_report_with_display_mode(
        False,
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        persist_strategy_tracking=True,
    )
    summary_report = _render_report_with_display_mode(
        True,
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        persist_strategy_tracking=False,
    )

    if position_report_text:
        full_report += position_report_text
        summary_report += position_report_text

    return {
        REPORT_VARIANT_FULL: _inject_report_variant_banner(full_report, REPORT_VARIANT_FULL),
        REPORT_VARIANT_SUMMARY: _inject_report_variant_banner(summary_report, REPORT_VARIANT_SUMMARY),
    }


def save_report_output(
    report_text: str,
    target_date: str,
    mode: str = LEDGER_MODE_FROZEN,
    variant: str = REPORT_VARIANT_FULL,
    output_path: str | None = None,
):
    target_path = Path(output_path) if output_path else Path(_get_report_output_path(target_date, mode=mode, variant=variant))
    _ensure_parent_dir(target_path)

    if output_path is None and mode == LEDGER_MODE_FROZEN and target_path.exists():
        replay_path = Path(_get_report_output_path(target_date, mode=LEDGER_MODE_REPLAY, variant=variant))
        _ensure_parent_dir(replay_path)
        replay_path.write_text(report_text, encoding="utf-8")
        print(f"\n🧊 官方报告已冻结，未覆盖历史: {target_path}")
        print(f"🧪 当前结果已转存为实验报告: {replay_path}")
        print(f"📄 报告长度: {len(report_text)} 字符")
        return str(replay_path)

    target_path.write_text(report_text, encoding="utf-8")
    print(f"\n✅ 报告已保存: {target_path}")
    print(f"📄 报告长度: {len(report_text)} 字符")
    return str(target_path)


def save_report_outputs(
    report_outputs,
    target_date: str,
    mode: str = LEDGER_MODE_FROZEN,
    output_dir: str | None = None,
):
    saved_paths = {}
    for variant, report_text in (report_outputs or {}).items():
        if output_dir:
            variant_label = "完整版" if variant == REPORT_VARIANT_FULL else "执行摘要"
            suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
            custom_path = Path(output_dir) / f"{target_date}_A股日报_{variant_label}{suffix}.md"
            saved_paths[variant] = save_report_output(
                report_text,
                target_date,
                mode=mode,
                variant=variant,
                output_path=str(custom_path),
            )
        else:
            saved_paths[variant] = save_report_output(
                report_text,
                target_date,
                mode=mode,
                variant=variant,
            )
    return saved_paths


def save_stock_diagnostic_output(
    report_text: str,
    target_date: str,
    stock_code: str,
    mode: str = LEDGER_MODE_FROZEN,
    output_path: str | None = None,
):
    target_path = Path(output_path) if output_path else Path(_get_stock_diagnostic_output_path(target_date, stock_code, mode=mode))
    _ensure_parent_dir(target_path)
    target_path.write_text(report_text, encoding="utf-8")
    print(f"\n✅ 单票诊断已保存: {target_path}")
    print(f"📄 诊断长度: {len(report_text)} 字符")
    return str(target_path)
