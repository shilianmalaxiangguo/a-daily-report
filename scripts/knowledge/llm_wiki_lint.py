#!/usr/bin/env python3
"""Read-only validation for the local LLM Wiki manifest and navigation."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from knowledge.llm_wiki_context import SOURCE_PATHS, WIKI_LANGUAGE, WIKI_VERSION
from knowledge.llm_wiki_manifest import build_knowledge_manifest, validate_knowledge_manifest
from knowledge.llm_wiki_router import KNOWLEDGE_INDEX


_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_LOG_HEADING_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] (ingest|query|lint|contract) \| .+$")


def _unique_sorted(items):
    return sorted(set(str(item) for item in items if str(item).strip()))


def _index_links(index_path: Path, *, root: Path) -> tuple[set[str], list[str]]:
    errors = []
    if not index_path.is_file():
        return set(), ["wiki_index_missing:wiki/index.md"]
    root = root.resolve()
    wiki_root = (root / "wiki").resolve()
    links = set()
    text = index_path.read_text(encoding="utf-8")
    for raw_target in _MARKDOWN_LINK_RE.findall(text):
        target = unquote(str(raw_target or "").strip().strip("<>").split("#", 1)[0])
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        resolved = (index_path.parent / target).resolve()
        try:
            resolved.relative_to(wiki_root)
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            errors.append(f"wiki_index_link_outside:{target}")
            continue
        links.add(relative)
        if not resolved.exists():
            errors.append(f"wiki_index_link_missing:{relative}")
    return links, errors


def _log_errors(log_path: Path) -> list[str]:
    if not log_path.is_file():
        return ["wiki_log_missing:wiki/log.md"]
    headings = [
        line.strip()
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]
    if not headings:
        return ["wiki_log_entry_missing"]
    errors = []
    for heading in headings:
        match = _LOG_HEADING_RE.match(heading)
        if match:
            try:
                date.fromisoformat(match.group(1))
            except ValueError:
                match = None
        if not match:
            errors.append(f"wiki_log_heading_invalid:{heading}")
    return errors


def lint_knowledge_wiki(
    *,
    entries: Sequence[Mapping[str, Any]] = KNOWLEDGE_INDEX,
    root: Path = ROOT,
    expected_source_paths: Sequence[str] = SOURCE_PATHS,
) -> dict[str, Any]:
    root = Path(root)
    manifest = build_knowledge_manifest(
        entries,
        root=root,
        wiki_version=WIKI_VERSION,
        language=WIKI_LANGUAGE,
        expected_source_paths=expected_source_paths,
    )
    errors = list(validate_knowledge_manifest(manifest))
    warnings = [str(item) for item in manifest.get("warnings") or []]
    errors.extend(item for item in warnings if item.startswith("source_missing:"))

    index_links, index_errors = _index_links(root / "wiki" / "index.md", root=root)
    errors.extend(index_errors)
    source_paths = {
        str(source_path or "").strip()
        for source_path in manifest.get("expected_source_paths") or []
    }
    for source_path in sorted(path for path in source_paths if path):
        if source_path not in index_links:
            errors.append(f"wiki_index_source_unlinked:{source_path}")
    errors.extend(_log_errors(root / "wiki" / "log.md"))
    return {
        "manifest": manifest,
        "errors": _unique_sorted(errors),
        "warnings": _unique_sorted(warnings),
    }


def main() -> int:
    result = lint_knowledge_wiki()
    manifest = result["manifest"]
    print(
        "LLM Wiki lint: "
        f"entries={len(manifest.get('entries') or [])} "
        f"errors={len(result['errors'])} warnings={len(result['warnings'])}"
    )
    for error in result["errors"]:
        print(f"ERROR {error}")
    for warning in result["warnings"]:
        print(f"WARNING {warning}")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
