import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class HistoryCacheTest(unittest.TestCase):
    def test_history_cache_persists_source_tagged_turnover_by_code_and_date(self):
        from history_cache import HistoryCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = HistoryCache(cache_dir=Path(tmpdir))
            cache.set("tushare:000001", "2026-05-14", [1.0, 2.0, 3.0], source="tushare_full_window")

            restored = HistoryCache(cache_dir=Path(tmpdir))

            self.assertEqual(restored.get("tushare:000001", "2026-05-14"), [1.0, 2.0, 3.0])
            self.assertEqual(restored.get_cache_stats("2026-05-14")["count"], 1)


if __name__ == "__main__":
    unittest.main()
