"""Check report reproducibility and the separation of its two account models."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report import render_small_cap_backtest_report as report


class SmallCapBacktestReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads(report.INPUTS.read_text(encoding='utf-8'))

    def render_copy(self, inputs):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'comparison-inputs.json'
            output = Path(directory) / 'report.html'
            source.write_text(json.dumps(inputs, ensure_ascii=False), encoding='utf-8')
            with patch.object(report, 'INPUTS', source), patch.object(report, 'OUTPUT', output), \
                    patch.object(report, 'ROOT', Path(directory)), redirect_stdout(StringIO()):
                report.render()
            return output.read_text(encoding='utf-8')

    def test_report_has_only_recent_dates_and_separate_account_curves(self):
        rendered = self.render_copy(deepcopy(self.inputs))
        soup = BeautifulSoup(rendered, 'html.parser')
        payload = json.loads(soup.select_one('#backtest-payload').string)
        self.assertNotIn('full', payload)
        self.assertEqual(payload['recent']['dates'][0], '2025-02-28')
        self.assertEqual(payload['account']['dates'][0], '2025-02-28')
        self.assertEqual(payload['account']['dates'][-1], '2026-10-29')
        self.assertEqual(payload['recent']['dates'][-1], '2026-10-29')
        self.assertTrue(all(v[0] == 1 for v in payload['recent']['curves'].values()))
        self.assertNotIn('random', payload['recent_metrics'])
        self.assertEqual(len(soup.select('table')), 2)
        self.assertFalse(soup.select('script[src], link[rel=stylesheet]'))
        self.assertNotIn('47.5%', soup.get_text())
        self.assertNotIn('full-history', rendered)
        self.assertEqual(rendered, self.render_copy(deepcopy(self.inputs)))

    def test_account_metrics_match_independent_curve_calculation(self):
        soup = BeautifulSoup(self.render_copy(deepcopy(self.inputs)), 'html.parser')
        payload = json.loads(soup.select_one('#backtest-payload').string)
        values = self.inputs['account']['tp10']['nav']
        total = values[-1] / values[0] - 1
        annual = (1 + total) ** (252 / (len(values) - 1)) - 1
        drawdown = min(value / max(values[:i + 1]) - 1 for i, value in enumerate(values))
        actual = payload['account_metrics']['account_tp10']
        self.assertAlmostEqual(actual['total_pct'], total * 100)
        self.assertAlmostEqual(actual['cagr_pct'], annual * 100)
        self.assertAlmostEqual(actual['max_drawdown_pct'], drawdown * 100)
        self.assertAlmostEqual(annual * 100, 21.36, places=2)

    def test_rejects_missing_benchmark_and_bad_account_metadata(self):
        cases = []
        value = deepcopy(self.inputs)
        del value['backtest']['curves']['small_cap_plan']
        cases.append(value)
        value = deepcopy(self.inputs)
        value['account']['index_nav'].pop()
        cases.append(value)
        value = deepcopy(self.inputs)
        value['account']['end'] = '2026-10-30'
        cases.append(value)
        value = deepcopy(self.inputs)
        value['account']['tp10']['cagr_pct'] = 47.5
        cases.append(value)
        value = deepcopy(self.inputs)
        value['account']['base']['nav'][3] = float('nan')
        cases.append(value)
        for index, value in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.render_copy(value)


if __name__ == '__main__':
    unittest.main()
