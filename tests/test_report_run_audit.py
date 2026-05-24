import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.report_run_audit import audit_daily_report_run


class ReportRunAuditTest(unittest.TestCase):
    def test_combines_preflight_failures_and_markdown_findings_into_normalized_findings(self):
        def fake_preflight(data, target_date):
            return {
                "target_date": target_date,
                "status": "failed",
                "failures": ["中证全指"],
                "checks": [
                    {
                        "label": "中证全指",
                        "status": "failed",
                        "provider": "unknown",
                        "value": "",
                        "row_count": 0,
                    }
                ],
            }

        def fake_report_audit(markdown):
            return {
                "passed": False,
                "finding_count": 1,
                "findings": [
                    {
                        "code": "duplicate_no_trade",
                        "message": "duplicate no-participation conclusion",
                        "line": 12,
                    }
                ],
            }

        result = audit_daily_report_run(
            target_date="2026-05-24",
            data={"sample": True},
            report_markdown="# report",
            build_preflight=fake_preflight,
            audit_markdown=fake_report_audit,
            decision_ledger_result={
                "case_count": 1,
                "snapshot_path": "data/decision-ledger/2026-05-24.json",
            },
        )

        self.assertFalse(result["passed"])
        self.assertFalse(result["usable"])
        self.assertEqual(result["target_date"], "2026-05-24")
        self.assertEqual(
            [(finding["source"], finding["code"]) for finding in result["findings"]],
            [
                ("preflight", "critical_data_incomplete"),
                ("report_acceptance", "duplicate_no_trade"),
            ],
        )
        self.assertTrue(result["decision_ledger"]["passed"])
        self.assertEqual(result["finding_count"], 2)

    def test_missing_decision_ledger_when_required_creates_finding_while_usable_remains_true(self):
        result = audit_daily_report_run(
            target_date="2026-05-24",
            data={},
            report_markdown="# report",
            build_preflight=lambda data, target_date: {
                "status": "success",
                "failures": [],
                "checks": [],
            },
            audit_markdown=lambda markdown: {
                "passed": True,
                "findings": [],
                "finding_count": 0,
            },
            decision_ledger_required=True,
            decision_ledger_result=None,
        )

        self.assertFalse(result["passed"])
        self.assertTrue(result["usable"])
        self.assertFalse(result["decision_ledger"]["passed"])
        self.assertEqual(result["findings"][0]["source"], "decision_ledger")
        self.assertEqual(result["findings"][0]["code"], "decision_ledger_missing")
        self.assertEqual(result["finding_count"], 1)

    def test_companion_html_does_not_require_audit_callable_to_accept_keyword(self):
        success_result = {
            "passed": True,
            "findings": [],
            "finding_count": 0,
        }

        result = audit_daily_report_run(
            target_date="2026-05-24",
            data={},
            report_markdown="# report",
            companion_html="<html></html>",
            build_preflight=lambda data, target_date: {
                "status": "success",
                "failures": [],
                "checks": [],
            },
            audit_markdown=lambda markdown: success_result,
            decision_ledger_result={"case_count": 1},
        )

        self.assertTrue(result["passed"])
        self.assertIs(result["report_acceptance"], success_result)

    def test_failed_decision_ledger_fact_db_sync_fails_run_without_top_level_passed(self):
        result = audit_daily_report_run(
            target_date="2026-05-24",
            data={},
            report_markdown="# report",
            build_preflight=lambda data, target_date: {
                "status": "success",
                "failures": [],
                "checks": [],
            },
            audit_markdown=lambda markdown: {
                "passed": True,
                "findings": [],
                "finding_count": 0,
            },
            decision_ledger_result={
                "case_count": 1,
                "fact_db_sync": {"status": "failed", "error": "boom"},
            },
        )

        self.assertFalse(result["passed"])
        self.assertFalse(result["decision_ledger"]["passed"])
        self.assertEqual(result["findings"][0]["source"], "decision_ledger")
        self.assertEqual(result["findings"][0]["code"], "fact_db_sync_failed")
        self.assertEqual(
            result["findings"][0]["message"],
            "本地事实库同步失败，判断账本文件已保留",
        )
        self.assertEqual(result["decision_ledger"]["fact_db_sync"]["error"], "boom")


if __name__ == "__main__":
    unittest.main()
