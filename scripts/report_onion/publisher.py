from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VARIANT_PUBLIC_BRIEF = "public-brief"
VARIANT_PRIVATE_BRIEF = "private-brief"
VARIANT_FULL = "full"
SOURCE_POLICY_PUBLIC = "snapshot-allowlist"
PUBLIC_NOTICE = "完整版暂不公开"
FULL_PUBLIC_SOURCE = "full-markdown-limited-free"
FULL_PUBLIC_POLICY = "limited-free"
LOCKED_FIELDS = ["targets", "executionPlan", "candidateRanking", "pkDetails", "reviewTracking"]

FORBIDDEN_PUBLIC_PATTERNS = [
    re.compile(r"(?<!\d)(?:(?:00|30|60|68)\d{4}|[89]\d{5})(?!\d)"),
    re.compile(r"[\u4e00-\u9fff]{2,}\((?:(?:00|30|60|68)\d{4}|[89]\d{5})\)"),
    re.compile(r"(买点|触发|止损|止盈|PK|候选|观察池|唯一对象|备用观察|执行计划|时间窗口)"),
    re.compile(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}"),
]


def unwrap_snapshot_data(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {}
    data = snapshot.get("data")
    if isinstance(data, dict):
        return data
    return snapshot


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if contains_forbidden_public_text(text):
        return fallback
    return text


def _safe_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def contains_forbidden_public_text(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return any(pattern.search(text) for pattern in FORBIDDEN_PUBLIC_PATTERNS)


def _focus_stock_items(data: dict[str, Any]) -> list[dict[str, str]]:
    appendix_c = _as_dict(data.get("appendix_c"))
    rows = appendix_c.get("current_stock_monitoring_pool")
    if not isinstance(rows, list):
        return []

    items: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _safe_text(row.get("stock_name") or row.get("name"), "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        items.append(
            {
                "name": name,
                "sector": _safe_text(row.get("sector"), "未标注"),
                "source": _safe_text(row.get("source_pool"), "公开关注"),
            }
        )
    return items[:6]


def _format_bool_cn(value: bool | None) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return "-"


def _build_public_brief_markdown(
    *,
    title: str,
    summary: dict[str, Any],
    focus_stocks: list[dict[str, str]],
) -> str:
    lines = [
        f"# {title}",
        "",
        "## 市场简报",
        f"- 市场状态：{summary['marketState']}",
        f"- 主线：{summary['mainline']}",
        f"- 仓位：{summary['positionGrade']}",
        f"- 新开仓：{_format_bool_cn(summary['canNewEntry'])}",
        "",
        "## 重点关注个股",
    ]
    if focus_stocks:
        for item in focus_stocks:
            lines.append(f"- **{item['name']}**：方向：{item['sector']}；来源：{item['source']}")
    else:
        lines.append("- 暂无公开重点关注个股。")

    lines.extend(
        [
            "",
            "##### 附录：最终结论",
            summary["oneLine"],
            "",
            "> 公开版仅展示市场级结论与重点关注名称，不展示代码和执行细节。",
        ]
    )
    return "\n".join(lines)


def build_public_brief_payload(
    *,
    date: str,
    title: str,
    mode: str,
    source_version: str,
    snapshot: Any,
) -> dict[str, Any]:
    data = unwrap_snapshot_data(snapshot)
    research = _as_dict(data.get("market_research_snapshot"))
    state_machine = _as_dict(research.get("state_machine"))
    rotation = _as_dict(research.get("mainline_rotation_snapshot"))
    final_gate = _as_dict(research.get("final_gate"))
    capital = _as_dict(research.get("capital_conclusion"))
    turnover = _as_dict(data.get("mainline_turnover_summary"))

    market_state = _safe_text(
        final_gate.get("operation_state")
        or state_machine.get("state_code")
        or state_machine.get("observation_summary"),
        "unavailable",
    )
    mainline = _safe_text(turnover.get("current_mainline") or state_machine.get("leading_line"), "locked")
    position_grade = _safe_text(final_gate.get("position_level"), "locked")
    rotation_label = _safe_text(rotation.get("rotation_label"), "unavailable")
    capital_state = _safe_text(capital.get("current_capital_state"), "unavailable")
    can_new_entry = _safe_bool(final_gate.get("can_new_entry"))

    unavailable_fields = []
    if market_state == "unavailable":
        unavailable_fields.append("marketState")
    if mainline == "locked":
        unavailable_fields.append("mainline")
    if position_grade == "locked":
        unavailable_fields.append("positionGrade")
    if can_new_entry is None:
        unavailable_fields.append("canNewEntry")

    one_line_parts = [
        f"市场状态：{market_state}",
        f"主线：{mainline}",
        f"仓位：{position_grade}",
    ]
    one_line = "；".join(one_line_parts) + "；执行细节不公开。"
    focus_stocks = _focus_stock_items(data)
    summary = {
        "marketState": market_state,
        "marketBase": _safe_text(state_machine.get("observation_summary"), "unavailable"),
        "mainline": mainline,
        "mainlineRelationship": _safe_text(turnover.get("conclusion"), "unavailable"),
        "rotation": rotation_label,
        "positionGrade": position_grade,
        "canNewEntry": can_new_entry,
        "capitalState": capital_state,
        "oneLine": one_line,
        "riskNote": "公开版只展示市场级结论，可执行细节已锁定。",
    }

    payload = {
        "date": date,
        "title": title,
        "mode": mode,
        "variant": VARIANT_PUBLIC_BRIEF,
        "sourcePolicy": SOURCE_POLICY_PUBLIC,
        "sourceVersion": source_version,
        "failClosed": True,
        "summary": summary,
        "markdown": _build_public_brief_markdown(title=title, summary=summary, focus_stocks=focus_stocks),
        "lockedFields": list(LOCKED_FIELDS),
        "unavailableFields": unavailable_fields,
    }
    if contains_forbidden_public_text(payload):
        raise ValueError(f"public brief contains forbidden text for {date}")
    return payload


FULL_FROZEN_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_A股日报_完整版\.md$")
FULL_REPLAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_A股日报_完整版_replay\.md$")
BRIEF_FROZEN_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_A股日报_执行摘要\.md$")
BRIEF_REPLAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_A股日报_执行摘要_replay\.md$")


@dataclass(frozen=True)
class ReportSource:
    date: str
    title: str
    mode: str
    full_markdown_path: Path
    brief_markdown_path: Path | None
    snapshot_path: Path | None


def _read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _title_from_markdown(markdown: str, date: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or f"{date} A股日报"
    return f"{date} A股日报"


def _maybe_match(
    path: Path,
    frozen_re: re.Pattern[str],
    replay_re: re.Pattern[str],
) -> tuple[str, str] | None:
    replay_match = replay_re.match(path.name)
    if replay_match:
        return replay_match.group(1), "replay"
    frozen_match = frozen_re.match(path.name)
    if frozen_match:
        return frozen_match.group(1), "frozen"
    return None


def _snapshot_path(root: Path, date: str, mode: str) -> Path | None:
    path = (
        root / "snapshots" / "replay" / f"{date}_replay.json"
        if mode == "replay"
        else root / "snapshots" / f"{date}.json"
    )
    return path if path.exists() else None


def _brief_path(root: Path, date: str, mode: str) -> Path | None:
    path = (
        root / "reports" / "replay" / f"{date}_A股日报_执行摘要_replay.md"
        if mode == "replay"
        else root / "reports" / f"{date}_A股日报_执行摘要.md"
    )
    return path if path.exists() else None


def discover_report_sources(root: str | Path) -> list[ReportSource]:
    root_path = Path(root)
    candidates: dict[str, tuple[str, Path]] = {}
    for report_dir in [root_path / "reports", root_path / "reports" / "replay"]:
        if not report_dir.exists():
            continue
        for path in report_dir.iterdir():
            if not path.is_file():
                continue
            matched = _maybe_match(path, FULL_FROZEN_RE, FULL_REPLAY_RE)
            if not matched:
                continue
            date, mode = matched
            if mode == "replay" or date not in candidates:
                candidates[date] = (mode, path)

    sources: list[ReportSource] = []
    for date, (mode, full_path) in candidates.items():
        markdown = _read_text(full_path)
        sources.append(
            ReportSource(
                date=date,
                title=_title_from_markdown(markdown, date),
                mode=mode,
                full_markdown_path=full_path,
                brief_markdown_path=_brief_path(root_path, date, mode),
                snapshot_path=_snapshot_path(root_path, date, mode),
            )
        )
    return sorted(sources, key=lambda source: source.date, reverse=True)


def _full_locked_variant() -> dict[str, Any]:
    return {
        "access": "locked",
        "publicNotice": PUBLIC_NOTICE,
    }


def _full_public_variant(source: ReportSource, *, source_name: str, policy: str) -> dict[str, Any]:
    return {
        "access": "public",
        "contentPath": f"/data/daily-reports/{source.date}.full.json",
        "source": source_name,
        "policy": policy,
    }


def _public_manifest_item(source: ReportSource, *, is_latest: bool) -> dict[str, Any]:
    full_source = FULL_PUBLIC_SOURCE if is_latest else "delayed-full-markdown-public"
    full_policy = FULL_PUBLIC_POLICY if is_latest else "latest-report-delay"
    return {
        "date": source.date,
        "title": source.title,
        "defaultVariant": VARIANT_PUBLIC_BRIEF,
        "availableVariants": [VARIANT_PUBLIC_BRIEF, VARIANT_FULL],
        "lockedVariants": [VARIANT_PRIVATE_BRIEF],
        "variants": {
            VARIANT_PUBLIC_BRIEF: {
                "access": "public",
                "contentPath": f"/data/daily-reports/{source.date}.public-brief.json",
                "source": SOURCE_POLICY_PUBLIC,
                "policy": "structured-only-fail-closed",
            },
            VARIANT_PRIVATE_BRIEF: {
                "access": "locked",
                "publicNotice": PUBLIC_NOTICE,
            },
            VARIANT_FULL: _full_public_variant(source, source_name=full_source, policy=full_policy),
        },
    }


def _private_manifest_item(source: ReportSource, *, is_latest: bool) -> dict[str, Any]:
    full_variant = {
        "access": "local",
        "contentPath": f"/api/daily-reports/{source.date}?variant={VARIANT_FULL}",
        "source": "full-markdown-private",
    }
    return {
        "date": source.date,
        "title": source.title,
        "defaultVariant": VARIANT_PRIVATE_BRIEF,
        "availableVariants": [VARIANT_PRIVATE_BRIEF, VARIANT_FULL, VARIANT_PUBLIC_BRIEF],
        "lockedVariants": [],
        "variants": {
            VARIANT_PUBLIC_BRIEF: {
                "access": "local",
                "contentPath": f"/api/daily-reports/{source.date}?variant={VARIANT_PUBLIC_BRIEF}",
                "source": SOURCE_POLICY_PUBLIC,
                "policy": "structured-only-fail-closed",
            },
            VARIANT_PRIVATE_BRIEF: {
                "access": "local",
                "contentPath": f"/api/daily-reports/{source.date}?variant={VARIANT_PRIVATE_BRIEF}",
                "source": "snapshot-first-execution-summary-fallback",
            },
            VARIANT_FULL: full_variant,
        },
    }


def _private_brief_payload(source: ReportSource, public_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": source.date,
        "title": source.title,
        "mode": source.mode,
        "variant": VARIANT_PRIVATE_BRIEF,
        "sourcePolicy": "snapshot-first-execution-summary-fallback",
        "summary": public_payload["summary"],
        "markdown": _read_text(source.brief_markdown_path),
    }


def _full_payload(source: ReportSource, *, source_policy: str = "full-markdown-private") -> dict[str, Any]:
    return {
        "date": source.date,
        "title": source.title,
        "mode": source.mode,
        "variant": VARIANT_FULL,
        "sourcePolicy": source_policy,
        "markdown": _read_text(source.full_markdown_path),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_output_dirs(root: Path, public_dir: Path, private_dir: Path) -> None:
    root_resolved = root.resolve()
    public_resolved = public_dir.resolve()
    private_resolved = private_dir.resolve()

    if public_resolved == private_resolved:
        raise ValueError("public_output_dir and private_output_dir must be separate directories")

    allowed_snap_ui_generated = root_resolved / "snap-ui" / ".generated" / "daily-reports"
    protected_roots = [
        root_resolved,
        root_resolved / "reports",
        root_resolved / "snapshots",
        root_resolved / "scripts",
        root_resolved / "tests",
        root_resolved / "wiki",
        root_resolved / "snap-ui",
    ]
    for label, output_dir in [("public_output_dir", public_resolved), ("private_output_dir", private_resolved)]:
        if _is_relative_to(output_dir, allowed_snap_ui_generated):
            continue
        for protected_root in protected_roots:
            if _is_relative_to(output_dir, protected_root):
                raise ValueError(f"{label} is a dangerous output directory: {output_dir}")

    if _is_relative_to(private_resolved, public_resolved):
        raise ValueError("public_output_dir and private_output_dir must be sibling/separate directories")
    if _is_relative_to(public_resolved, private_resolved):
        raise ValueError("public_output_dir and private_output_dir must be sibling/separate directories")


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def publish_report_onion(
    *,
    root: str | Path,
    public_output_dir: str | Path,
    private_output_dir: str | Path,
) -> dict[str, Any]:
    root_path = Path(root)
    public_dir = Path(public_output_dir)
    private_dir = Path(private_output_dir)
    _validate_output_dirs(root_path, public_dir, private_dir)
    _reset_dir(public_dir)
    _reset_dir(private_dir)

    sources = discover_report_sources(root_path)
    public_reports = []
    private_reports = []
    written_files: list[str] = []

    latest_date = sources[0].date if sources else ""

    for source in sources:
        is_latest = source.date == latest_date
        snapshot = _read_json(source.snapshot_path)
        public_payload = build_public_brief_payload(
            date=source.date,
            title=source.title,
            mode=source.mode,
            source_version=f"snapshot:{source.mode}",
            snapshot=snapshot,
        )
        public_reports.append(_public_manifest_item(source, is_latest=is_latest))
        private_reports.append(_private_manifest_item(source, is_latest=is_latest))

        public_path = public_dir / f"{source.date}.public-brief.json"
        _write_json(public_path, public_payload)
        written_files.append(str(public_path))
        public_full_path = public_dir / f"{source.date}.full.json"
        public_full_policy = FULL_PUBLIC_POLICY if is_latest else "delayed-full-markdown-public"
        _write_json(public_full_path, _full_payload(source, source_policy=FULL_PUBLIC_SOURCE if is_latest else public_full_policy))
        written_files.append(str(public_full_path))

        private_public_path = private_dir / f"{source.date}.public-brief.json"
        private_brief_path = private_dir / f"{source.date}.private-brief.json"
        _write_json(private_public_path, public_payload)
        _write_json(private_brief_path, _private_brief_payload(source, public_payload))
        written_files.extend([str(private_public_path), str(private_brief_path)])
        full_path = private_dir / f"{source.date}.full.json"
        _write_json(full_path, _full_payload(source))
        written_files.append(str(full_path))

    public_index = {"reports": public_reports}
    private_index = {"reports": private_reports}
    _write_json(public_dir / "index.json", public_index)
    _write_json(private_dir / "index.json", private_index)
    written_files.extend([str(public_dir / "index.json"), str(private_dir / "index.json")])

    return {
        "dates": [source.date for source in sources],
        "publicOutputDir": str(public_dir),
        "privateOutputDir": str(private_dir),
        "writtenFiles": written_files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish daily report onion variants.")
    parser.add_argument("--root", default=".", help="a-daily-report repository root")
    parser.add_argument("--public-output", required=True, help="public generated daily-report output directory")
    parser.add_argument("--private-output", required=True, help="private generated daily-report output directory")
    args = parser.parse_args(argv)
    result = publish_report_onion(
        root=Path(args.root),
        public_output_dir=Path(args.public_output),
        private_output_dir=Path(args.private_output),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
