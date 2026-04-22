import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from risk.a_kill_blacklist_store import (
    get_active_a_kill_records,
    is_stock_in_a_kill_cooldown,
    load_a_kill_blacklist,
    update_a_kill_blacklist,
)


class AKillBlacklistStoreTest(unittest.TestCase):
    def test_update_and_get_active_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a_kill_blacklist.json"
            updated = update_a_kill_blacklist(
                "2026-04-20",
                [{"name": "军工一号", "code": "SZ000001"}],
                sector_name="军工",
                path=str(path),
            )
            self.assertEqual(updated[0]["code"], "000001")

            data = load_a_kill_blacklist(path=str(path))
            self.assertEqual(len(data["records"]), 1)

            active = get_active_a_kill_records("2026-04-22", path=str(path))
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0]["remaining_days"], 23)

            in_cooldown, record = is_stock_in_a_kill_cooldown({"code": "000001"}, active)
            self.assertTrue(in_cooldown)
            self.assertEqual(record["name"], "军工一号")


if __name__ == "__main__":
    unittest.main()
