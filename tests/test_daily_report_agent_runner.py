"""Retired orchestration cannot restore old account prescriptions."""
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from agent_runner.daily_report_agent_runner import (
    DailyReportAgentDependencies, DailyReportAgentRequest, DailyReportAgentRunner,
)


class DailyReportAgentRunnerTest(unittest.TestCase):
    def test_retired_runner_never_reads_or_writes_even_with_injected_loader(self):
        for mode in ('replay', 'fresh'):
            with self.subTest(mode=mode), TemporaryDirectory() as folder:
                load = Mock(side_effect=AssertionError('retired flow must not load'))
                runner = DailyReportAgentRunner(root_dir=folder, dependencies=DailyReportAgentDependencies(load_data=load))
                result = runner.run(DailyReportAgentRequest(target_date='2026-10-20', mode=mode))
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['error']['code'], 'retired_report_runner')
                self.assertIn('daily_report_entry_demo.py', result['error']['message'])
                self.assertEqual(list(Path(folder).iterdir()), [])
                load.assert_not_called()

    def test_default_request_does_not_reinstate_old_account_flags(self):
        request = DailyReportAgentRequest(target_date='2026-10-20')
        self.assertFalse(request.update_decision_ledger)
        self.assertFalse(request.review_prior_participation)
        self.assertEqual(request.output_variant, 'sector')


if __name__ == '__main__':
    unittest.main()
