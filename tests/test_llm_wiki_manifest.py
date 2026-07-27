import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge.llm_wiki_manifest import (  # noqa: E402
    build_knowledge_manifest,
    stable_json,
    stable_json_hash,
    validate_knowledge_manifest,
    validate_knowledge_manifest_sources,
)
from knowledge.llm_wiki_router import EXPLICIT_FACT_PATHS, KNOWLEDGE_INDEX  # noqa: E402


def _entry(**overrides):
    entry = {
        "id": "test.rule",
        "prior": "test-prior",
        "source_path": "wiki/交易思想/测试节点.md",
        "title": "测试知识",
        "topics": ["测试"],
        "trigger_terms": ["触发"],
        "fact_conditions": {
            "must_any": [
                {
                    "path": "market.breadth",
                    "contains_any": ["触发"],
                    "label": "测试事实",
                }
            ]
        },
        "scenarios": ["daily_report"],
        "report_slot": "知识引用",
        "confidence": "reviewed",
        "impact": "只解释测试事实，不改变正式决定。",
    }
    entry.update(overrides)
    return entry


class LlmWikiManifestTest(unittest.TestCase):
    def test_compiles_every_current_structured_knowledge_entry(self):
        manifest = build_knowledge_manifest(
            KNOWLEDGE_INDEX,
            root=ROOT,
            wiki_version="2026-07-17",
            language="zh-CN",
        )

        self.assertEqual(len(manifest["entries"]), len(KNOWLEDGE_INDEX))
        self.assertEqual(
            {entry["knowledge_id"] for entry in manifest["entries"]},
            {entry["id"] for entry in KNOWLEDGE_INDEX},
        )
        self.assertEqual(len(manifest["entries"]), len({entry["knowledge_id"] for entry in manifest["entries"]}))
        self.assertTrue(all(entry["kind"] == "knowledge_rule" for entry in manifest["entries"]))
        self.assertTrue(all(entry["decision_scope"] == "explanation_only" for entry in manifest["entries"]))
        self.assertTrue(all(entry["source_ref"]["content_hash"] for entry in manifest["entries"]))
        self.assertTrue(
            all(entry["fact_conditions"].get("must_any") for entry in manifest["entries"])
        )
        self.assertTrue(
            all(
                condition.get("path") in EXPLICIT_FACT_PATHS
                for entry in manifest["entries"]
                for condition in entry["fact_conditions"]["must_any"]
            )
        )
        new_high_entry = next(
            entry
            for entry in manifest["entries"]
            if entry["knowledge_id"] == "market.new-high-breadth-contraction"
        )
        self.assertEqual(
            new_high_entry["source_ref"]["path"],
            "wiki/交易思想/创新高扩散、核心独强与补跌.md",
        )
        self.assertEqual(new_high_entry["source_ref"]["metadata_status"], "complete")
        self.assertEqual(new_high_entry["decision_scope"], "explanation_only")
        live_structure_entry = next(
            entry
            for entry in manifest["entries"]
            if entry["knowledge_id"] == "market.historical-prior-live-structure"
        )
        self.assertEqual(
            live_structure_entry["source_ref"]["path"],
            "wiki/交易思想/历史先验、实时结构与可用窗口.md",
        )
        self.assertEqual(live_structure_entry["source_ref"]["metadata_status"], "complete")
        self.assertEqual(live_structure_entry["decision_scope"], "explanation_only")
        self.assertEqual(
            {
                condition["path"]
                for condition in live_structure_entry["fact_conditions"]["must_any"]
            },
            {
                "market.market_form",
                "market.breadth",
                "market.turnover_distribution",
            },
        )
        self.assertEqual(manifest["schema_version"], "knowledge_manifest.v1")
        self.assertEqual(len(manifest["manifest_hash"]), 64)

    def test_manifest_rejects_routable_entry_without_structured_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n", encoding="utf-8")
            manifest = build_knowledge_manifest(
                [_entry(fact_conditions={})],
                root=root,
                wiki_version="v1",
            )

        self.assertEqual(manifest["availability"], "invalid")
        self.assertIn("fact_conditions_missing:test.rule", manifest["errors"])

    def test_manifest_rejects_structured_condition_outside_fact_path_allowlist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n", encoding="utf-8")
            manifest = build_knowledge_manifest(
                [
                    _entry(
                        fact_conditions={
                            "must_any": [
                                {
                                    "path": "market",
                                    "equals": "上涨",
                                    "label": "过宽父路径",
                                }
                            ]
                        }
                    )
                ],
                root=root,
                wiki_version="v1",
            )

        self.assertEqual(manifest["availability"], "invalid")
        self.assertIn(
            "fact_condition_path_invalid:test.rule:market",
            manifest["errors"],
        )

    def test_manifest_rejects_preferred_condition_outside_fact_path_allowlist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n", encoding="utf-8")
            manifest = build_knowledge_manifest(
                [
                    _entry(
                        fact_conditions={
                            "must_any": [
                                {
                                    "path": "market.breadth",
                                    "equals": "上涨家数偏弱",
                                    "label": "有效确认",
                                }
                            ],
                            "prefer_any": [
                                {
                                    "path": "market",
                                    "equals": "上涨",
                                    "label": "过宽偏好路径",
                                }
                            ],
                        }
                    )
                ],
                root=root,
                wiki_version="v1",
            )

        self.assertEqual(manifest["availability"], "invalid")
        self.assertIn(
            "fact_condition_path_invalid:test.rule:market",
            manifest["errors"],
        )

    def test_manifest_hash_is_stable_for_same_files_and_entry_order(self):
        first = build_knowledge_manifest(KNOWLEDGE_INDEX, root=ROOT, wiki_version="2026-07-17")
        second = build_knowledge_manifest(KNOWLEDGE_INDEX, root=ROOT, wiki_version="2026-07-17")

        self.assertEqual(first, second)
        self.assertEqual(first["manifest_hash"], stable_json_hash(first, excluded_keys={"manifest_hash"}))

    def test_stable_json_orders_mixed_type_set_by_json_encoding(self):
        self.assertEqual(stable_json({"values": {1, "1"}}), '{"values":["1",1]}')

    def test_manifest_normalizes_string_sets_before_hashing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n", encoding="utf-8")
            manifest = build_knowledge_manifest(
                [
                    _entry(
                        topics={"beta", "alpha"},
                        scenarios={"review", "daily_report"},
                        trigger_terms={"触发乙", "触发甲"},
                    )
                ],
                root=root,
                wiki_version="v1",
            )

        entry = manifest["entries"][0]
        self.assertEqual(entry["topics"], ["alpha", "beta"])
        self.assertEqual(entry["applies_to"], ["daily_report", "review"])
        self.assertEqual(entry["trigger_terms"], ["触发乙", "触发甲"])
        self.assertEqual(manifest["manifest_hash"], stable_json_hash(manifest, excluded_keys={"manifest_hash"}))

    def test_validation_rejects_invalid_source_hash_and_entry_source_index_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n", encoding="utf-8")
            manifest = build_knowledge_manifest([_entry()], root=root, wiki_version="v1")

        invalid_hash = copy.deepcopy(manifest)
        invalid_hash["entries"][0]["source_ref"]["content_hash"] = "not-a-sha256"
        invalid_hash["sources"][0]["content_hash"] = "not-a-sha256"
        invalid_hash["manifest_hash"] = stable_json_hash(invalid_hash, excluded_keys={"manifest_hash"})
        invalid_errors = validate_knowledge_manifest(invalid_hash)
        self.assertTrue(any(item.startswith("source_hash_invalid:") for item in invalid_errors))

        mismatched_index = copy.deepcopy(manifest)
        mismatched_index["entries"][0]["source_ref"]["content_hash"] = "0" * 64
        mismatched_index["manifest_hash"] = stable_json_hash(
            mismatched_index,
            excluded_keys={"manifest_hash"},
        )
        self.assertIn(
            "source_index_mismatch:test.rule:wiki/交易思想/测试节点.md",
            validate_knowledge_manifest(mismatched_index),
        )

    def test_source_validation_rejects_self_consistent_but_forged_content_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n", encoding="utf-8")
            manifest = build_knowledge_manifest([_entry()], root=root, wiki_version="v1")
            forged = copy.deepcopy(manifest)
            forged["entries"][0]["source_ref"]["content_hash"] = "0" * 64
            forged["sources"][0]["content_hash"] = "0" * 64
            forged["manifest_hash"] = stable_json_hash(
                forged,
                excluded_keys={"manifest_hash"},
            )

            self.assertEqual(validate_knowledge_manifest(forged), [])
            self.assertIn(
                "source_content_hash_mismatch:wiki/交易思想/测试节点.md",
                validate_knowledge_manifest_sources(forged, root=root),
            )

    def test_validation_rejects_ready_manifest_that_still_has_warnings(self):
        manifest = build_knowledge_manifest(
            KNOWLEDGE_INDEX,
            root=ROOT,
            wiki_version="2026-07-17",
        )
        self.assertTrue(manifest["warnings"])
        manifest["availability"] = "ready"
        manifest["manifest_hash"] = stable_json_hash(
            manifest,
            excluded_keys={"manifest_hash"},
        )

        self.assertIn(
            "manifest_availability_inconsistent",
            validate_knowledge_manifest(manifest),
        )

    def test_validation_reports_malformed_internal_field_types_without_raising(self):
        for malformed in (None, [], 1, "invalid"):
            with self.subTest(manifest=malformed):
                self.assertEqual(
                    validate_knowledge_manifest(malformed),
                    ["manifest_type_invalid"],
                )
                self.assertEqual(
                    validate_knowledge_manifest_sources(malformed, root=ROOT),
                    ["manifest_type_invalid"],
                )

        manifest = build_knowledge_manifest(
            KNOWLEDGE_INDEX,
            root=ROOT,
            wiki_version="2026-07-17",
        )
        list_fields = (
            "entries",
            "sources",
            "expected_source_paths",
            "available_source_paths",
            "missing_source_paths",
            "invalid_source_paths",
            "warnings",
            "errors",
        )
        for field in list_fields:
            with self.subTest(field=field):
                malformed = copy.deepcopy(manifest)
                malformed[field] = 1
                malformed["manifest_hash"] = stable_json_hash(
                    malformed,
                    excluded_keys={"manifest_hash"},
                )

                self.assertIn(
                    f"manifest_field_type_invalid:{field}",
                    validate_knowledge_manifest(malformed),
                )

        for field in ("kind", "lifecycle"):
            with self.subTest(entry_field=field):
                malformed = copy.deepcopy(manifest)
                malformed["entries"][0][field] = []
                malformed["manifest_hash"] = stable_json_hash(
                    malformed,
                    excluded_keys={"manifest_hash"},
                )

                self.assertIn(
                    f"entry_field_type_invalid:{malformed['entries'][0]['knowledge_id']}:{field}",
                    validate_knowledge_manifest(malformed),
                )

        for field in (
            "topics",
            "applies_to",
            "trigger_terms",
            "weak_trigger_terms",
            "relationships",
            "report_slots",
        ):
            with self.subTest(entry_list_field=field):
                malformed = copy.deepcopy(manifest)
                malformed["entries"][0][field] = 1
                malformed["manifest_hash"] = stable_json_hash(
                    malformed,
                    excluded_keys={"manifest_hash"},
                )

                self.assertIn(
                    f"entry_field_type_invalid:{malformed['entries'][0]['knowledge_id']}:{field}",
                    validate_knowledge_manifest(malformed),
                )

    def test_source_byte_change_updates_source_and_manifest_hashes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n\n第一版。\n", encoding="utf-8")
            first = build_knowledge_manifest([_entry()], root=root, wiki_version="v1")

            source.write_text("# 测试节点\n\n第二版。\n", encoding="utf-8")
            second = build_knowledge_manifest([_entry()], root=root, wiki_version="v1")

        self.assertNotEqual(
            first["entries"][0]["source_ref"]["content_hash"],
            second["entries"][0]["source_ref"]["content_hash"],
        )
        self.assertNotEqual(first["manifest_hash"], second["manifest_hash"])

    def test_source_metadata_is_preserved_and_missing_fields_stay_explicit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n", encoding="utf-8")
            complete = build_knowledge_manifest(
                [
                    _entry(
                        source_date="2026-07-15",
                        capture_date="2026-07-16",
                        anchor="判断规则",
                    )
                ],
                root=root,
                wiki_version="v1",
            )["entries"][0]["source_ref"]
            partial = build_knowledge_manifest(
                [_entry()],
                root=root,
                wiki_version="v1",
            )["entries"][0]["source_ref"]

        self.assertEqual(complete["source_date"], "2026-07-15")
        self.assertEqual(complete["capture_date"], "2026-07-16")
        self.assertEqual(complete["anchor"], "判断规则")
        self.assertEqual(complete["metadata_status"], "complete")
        self.assertEqual(complete["missing_metadata"], [])
        self.assertEqual(complete["local_path"], "wiki/交易思想/测试节点.md")
        self.assertEqual(partial["metadata_status"], "partial")
        self.assertEqual(
            partial["missing_metadata"],
            ["source_date", "capture_date", "anchor"],
        )
        self.assertNotIn("source_date", partial)
        self.assertNotIn("capture_date", partial)
        self.assertNotIn("anchor", partial)

    def test_expected_only_source_keeps_explicit_metadata_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            entry_source_path = "wiki/交易思想/测试节点.md"
            expected_only_path = "wiki/运行契约/测试契约.md"
            for source_path in (entry_source_path, expected_only_path):
                source = root / source_path
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(f"# {source.stem}\n", encoding="utf-8")
            manifest = build_knowledge_manifest(
                [_entry(source_path=entry_source_path)],
                root=root,
                wiki_version="v1",
                expected_source_paths=[entry_source_path, expected_only_path],
            )

        expected_only_ref = next(
            source_ref
            for source_ref in manifest["sources"]
            if source_ref["path"] == expected_only_path
        )
        self.assertEqual(expected_only_ref["metadata_status"], "partial")
        self.assertEqual(
            expected_only_ref["missing_metadata"],
            ["source_date", "capture_date", "anchor"],
        )
        self.assertIn(
            f"source_metadata_incomplete:{expected_only_path}:source_date,capture_date,anchor",
            manifest["warnings"],
        )

        malformed = copy.deepcopy(manifest)
        malformed["sources"][1].pop("metadata_status")
        malformed["manifest_hash"] = stable_json_hash(
            malformed,
            excluded_keys={"manifest_hash"},
        )
        self.assertIn(
            f"source_metadata_status_invalid:manifest_source:{expected_only_path}:<missing>",
            validate_knowledge_manifest(malformed),
        )

        diverged = copy.deepcopy(manifest)
        diverged["entries"][0]["source_ref"]["source_date"] = "2099-01-01"
        diverged["manifest_hash"] = stable_json_hash(
            diverged,
            excluded_keys={"manifest_hash"},
        )
        self.assertIn(
            f"source_index_mismatch:test.rule:{entry_source_path}",
            validate_knowledge_manifest(diverged),
        )

    def test_missing_source_is_explicit_and_entry_is_not_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = build_knowledge_manifest([_entry()], root=Path(temp_dir), wiki_version="v1")

        self.assertEqual(manifest["availability"], "missing_sources")
        self.assertEqual(manifest["available_source_paths"], [])
        self.assertEqual(manifest["missing_source_paths"], ["wiki/交易思想/测试节点.md"])
        self.assertFalse(manifest["entries"][0]["available"])
        self.assertEqual(manifest["entries"][0]["source_ref"]["availability"], "missing")
        self.assertTrue(any("source_missing" in warning for warning in manifest["warnings"]))

    def test_source_path_outside_wiki_is_rejected_without_reading(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside = root / "outside.md"
            outside.write_text("不应被读取", encoding="utf-8")
            manifest = build_knowledge_manifest(
                [_entry(source_path="../outside.md")],
                root=root,
                wiki_version="v1",
            )

        self.assertEqual(manifest["availability"], "invalid")
        self.assertFalse(manifest["entries"][0]["available"])
        self.assertEqual(manifest["entries"][0]["source_ref"]["availability"], "invalid")
        self.assertTrue(any("source_path_invalid" in error for error in manifest["errors"]))

    def test_duplicate_id_invalid_lifecycle_and_empty_decision_scope_are_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n", encoding="utf-8")
            invalid = _entry(lifecycle="unknown", decision_scope="")
            manifest = build_knowledge_manifest(
                [invalid, copy.deepcopy(invalid)],
                root=root,
                wiki_version="v1",
            )

        self.assertEqual(manifest["availability"], "invalid")
        self.assertTrue(any("knowledge_id_duplicate:test.rule" in error for error in manifest["errors"]))
        self.assertTrue(any("lifecycle_invalid:test.rule" in error for error in manifest["errors"]))
        self.assertTrue(any("decision_scope_missing:test.rule" in error for error in manifest["errors"]))

    def test_decision_scope_outside_explanation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "wiki/交易思想/测试节点.md"
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n", encoding="utf-8")
            manifest = build_knowledge_manifest(
                [_entry(decision_scope="candidate_selection")],
                root=root,
                wiki_version="v1",
            )

        self.assertEqual(manifest["availability"], "invalid")
        self.assertIn(
            "decision_scope_invalid:test.rule:candidate_selection",
            manifest["errors"],
        )


if __name__ == "__main__":
    unittest.main()
