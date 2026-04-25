import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DailyReportSkillDocsTest(unittest.TestCase):
    def _read(self, relative_path):
        path = ROOT / relative_path
        self.assertTrue(path.exists(), f"Missing required skill doc: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_skill_routes_natural_language_intents_and_references(self):
        skill = self._read("SKILL.md")

        for intent in [
            "generate_report",
            "review_report_output",
            "fix_report_defect",
            "review_trade_case",
            "extract_workflow_memory",
            "optimize_skill",
        ]:
            self.assertIn(intent, skill)

        for reference in [
            "references/report-contract.md",
            "references/memory-governance.md",
            "references/verification.md",
        ]:
            self.assertIn(reference, skill)

        self.assertIn("natural-language", skill)
        self.assertIn("users do not need to remember commands", skill)
        self.assertNotIn("workflow_memory_runtime.py", skill)
        self.assertNotIn("data/workflow_memory.json", skill)

    def test_skill_preserves_report_optimization_priority_order(self):
        skill = self._read("SKILL.md")
        priorities = [
            "report acceptance audit",
            "structured history",
            "only-focus audit",
            "entry-cycle calibration",
            "workflow memory",
            "skill refactor",
        ]

        positions = [skill.index(priority) for priority in priorities]
        self.assertEqual(positions, sorted(positions))

    def test_references_state_memory_governance_and_safety_rules(self):
        report_contract = self._read("references/report-contract.md")
        memory_governance = self._read("references/memory-governance.md")
        verification = self._read("references/verification.md")
        combined = "\n".join([report_contract, memory_governance, verification])

        for required in [
            "review artifacts only",
            "manual apply only",
            "independent evidence",
            "latest user instruction overrides memory",
            "workflow memory is not stock tracking memory",
            "no auto-apply",
            "do not build a memory platform",
            "not a command manual",
        ]:
            self.assertIn(required, combined)

    def test_future_change_specs_default_to_inherited_report_contract(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        combined = "\n".join([skill, report_contract])

        for required in [
            "Future Change Inheritance",
            "delta spec",
            "default inherit",
            "report contract",
            "unless the latest user instruction explicitly overrides it",
            "new report requests do not need to restate existing guardrails",
        ]:
            self.assertIn(required, combined)

    def test_verification_reference_names_practical_commands(self):
        verification = self._read("references/verification.md")

        for required in [
            "venv/bin/python scripts/daily_report_entry_demo.py",
            "scripts/report/report_acceptance_audit.py",
            "venv/bin/python -m unittest",
            "tests.test_report_acceptance_audit",
            "tests.test_entry_plan_node_runtime",
            "git diff --check",
        ]:
            self.assertIn(required, verification)


if __name__ == "__main__":
    unittest.main()
