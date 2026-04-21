import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LegacyEntryImportTest(unittest.TestCase):
    def test_local_support_modules_import_for_legacy_wrappers(self):
        script = (
            "import sys; "
            f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
            "import daily_report_analysis_utils as analysis_utils; "
            "import daily_report_markdown_hooks as markdown_hooks; "
            "print(analysis_utils.normalize_stock_code('000001.SZ')); "
            "print('\\n'.join(markdown_hooks.use_trading_philosophy_lines(compact=True)))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("000001", result.stdout)
        self.assertIn("方向性错误回避", result.stdout)
        self.assertIn("系统要求", result.stdout)


if __name__ == "__main__":
    unittest.main()
