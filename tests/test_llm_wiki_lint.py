import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge.llm_wiki_lint import lint_knowledge_wiki
from knowledge.llm_wiki_manifest import build_knowledge_manifest, stable_json_hash
from knowledge.llm_wiki_router import KNOWLEDGE_INDEX


def _entry(**overrides):
    value = {
        "id": "test.rule",
        "prior": "test-prior",
        "source_path": "wiki/source.md",
        "title": "测试规则",
        "topics": ["测试"],
        "trigger_terms": ["测试"],
        "fact_conditions": {
            "must_any": [
                {"path": "market.market_form", "contains_any": ["测试"], "label": "测试事实"},
            ]
        },
        "scenarios": ["daily_report"],
        "report_slot": "知识引用",
        "confidence": "reviewed",
        "impact": "只解释测试事实，不改变交易决定。",
    }
    value.update(overrides)
    return value


def _write_fixture(root: Path, *, source=True, broken_link=False):
    wiki = root / "wiki"
    wiki.mkdir(parents=True, exist_ok=True)
    if source:
        (wiki / "source.md").write_text("# 测试来源\n", encoding="utf-8")
    links = ["- [测试来源](source.md)"]
    if broken_link:
        links.append("- [缺失链接](missing.md)")
    (wiki / "index.md").write_text("# 导航\n\n" + "\n".join(links) + "\n", encoding="utf-8")
    (wiki / "log.md").write_text(
        "# 日志\n\n## [2026-07-17] lint | 测试检查\n",
        encoding="utf-8",
    )


class LlmWikiLintTest(unittest.TestCase):
    def test_current_wiki_has_no_lint_errors_and_covers_all_runtime_entries(self):
        result = lint_knowledge_wiki(root=ROOT)

        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["manifest"]["entries"]), len(KNOWLEDGE_INDEX))

    def test_lint_is_deterministic_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_fixture(root)
            before = (root / "wiki" / "source.md").read_bytes()
            first = lint_knowledge_wiki(
                entries=[_entry()],
                root=root,
                expected_source_paths=["wiki/source.md"],
            )
            second = lint_knowledge_wiki(
                entries=[_entry()],
                root=root,
                expected_source_paths=["wiki/source.md"],
            )

            self.assertEqual(first["errors"], [])
            self.assertEqual(first["manifest"]["manifest_hash"], second["manifest"]["manifest_hash"])
            self.assertEqual((root / "wiki" / "source.md").read_bytes(), before)

    def test_lint_reports_duplicate_id_lifecycle_scope_and_required_field_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_fixture(root)
            entries = [
                _entry(),
                _entry(lifecycle="unknown", decision_scope="", title="", impact=""),
            ]

            result = lint_knowledge_wiki(
                entries=entries,
                root=root,
                expected_source_paths=["wiki/source.md"],
            )

        self.assertTrue(any("knowledge_id_duplicate:test.rule" in item for item in result["errors"]))
        self.assertTrue(any("lifecycle_invalid:test.rule:unknown" in item for item in result["errors"]))
        self.assertTrue(any("decision_scope_missing:test.rule" in item for item in result["errors"]))
        self.assertTrue(any("entry_field_missing:test.rule:title" in item for item in result["errors"]))
        self.assertTrue(
            any(
                "entry_field_missing:test.rule:decision_effect" in item
                for item in result["errors"]
            )
        )

    def test_lint_reports_decision_scope_removed_from_compiled_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_fixture(root)
            manifest = build_knowledge_manifest(
                [_entry()],
                root=root,
                wiki_version="test",
                expected_source_paths=["wiki/source.md"],
            )
            manifest["entries"][0].pop("decision_scope")
            manifest["manifest_hash"] = stable_json_hash(
                manifest,
                excluded_keys={"manifest_hash"},
            )

            with patch(
                "knowledge.llm_wiki_lint.build_knowledge_manifest",
                return_value=manifest,
            ):
                result = lint_knowledge_wiki(
                    entries=[_entry()],
                    root=root,
                    expected_source_paths=["wiki/source.md"],
                )

        self.assertIn(
            "entry_field_missing:test.rule:decision_scope",
            result["errors"],
        )

    def test_lint_reports_routable_entry_without_source_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_fixture(root)
            manifest = build_knowledge_manifest(
                [_entry()],
                root=root,
                wiki_version="test",
                expected_source_paths=["wiki/source.md"],
            )
            broken_manifest = copy.deepcopy(manifest)
            broken_manifest["sources"][0]["content_hash"] = ""
            broken_manifest["entries"][0]["source_ref"]["content_hash"] = ""
            broken_manifest["manifest_hash"] = stable_json_hash(
                broken_manifest,
                excluded_keys={"manifest_hash"},
            )

            with patch(
                "knowledge.llm_wiki_lint.build_knowledge_manifest",
                return_value=broken_manifest,
            ):
                result = lint_knowledge_wiki(
                    entries=[_entry()],
                    root=root,
                    expected_source_paths=["wiki/source.md"],
                )

        self.assertIn(
            "source_hash_invalid:manifest_source:wiki/source.md",
            result["errors"],
        )
        self.assertIn("source_hash_invalid:test.rule", result["errors"])

    def test_lint_reports_missing_source_and_broken_index_link(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_fixture(root, source=False, broken_link=True)

            result = lint_knowledge_wiki(
                entries=[_entry()],
                root=root,
                expected_source_paths=["wiki/source.md"],
            )

        self.assertIn("source_missing:wiki/source.md", result["errors"])
        self.assertIn("wiki_index_link_missing:wiki/source.md", result["errors"])
        self.assertIn("wiki_index_link_missing:wiki/missing.md", result["errors"])

    def test_lint_requires_every_expected_runtime_source_in_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_fixture(root)
            (root / "wiki" / "extra.md").write_text("# 额外来源\n", encoding="utf-8")

            result = lint_knowledge_wiki(
                entries=[_entry()],
                root=root,
                expected_source_paths=["wiki/source.md", "wiki/extra.md"],
            )

        self.assertIn("wiki_index_source_unlinked:wiki/extra.md", result["errors"])

    def test_lint_rejects_impossible_log_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_fixture(root)
            (root / "wiki" / "log.md").write_text(
                "# 日志\n\n## [2026-99-99] lint | 测试检查\n",
                encoding="utf-8",
            )

            result = lint_knowledge_wiki(
                entries=[_entry()],
                root=root,
                expected_source_paths=["wiki/source.md"],
            )

        self.assertIn(
            "wiki_log_heading_invalid:## [2026-99-99] lint | 测试检查",
            result["errors"],
        )


if __name__ == "__main__":
    unittest.main()
