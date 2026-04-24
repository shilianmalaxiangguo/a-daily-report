import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research.tracking_memory_runtime import refresh_tracking_memory


class TrackingMemoryRuntimeTest(unittest.TestCase):
    def test_refresh_tracking_memory_promotes_confirmed_items_and_drops_failed_ones(self):
        saved = {}

        result = refresh_tracking_memory(
            "2026-04-22",
            watchlist=[{"code": "000001", "name": "主线一号", "sector": "军工"}],
            leader_memory_bank=[{"code": "000001", "name": "主线一号", "sector": "军工", "remember_score": 88}],
            abnormal_watch_pool=[
                {
                    "code": "000001",
                    "name": "主线一号",
                    "sector": "军工",
                    "abnormal_score": 81,
                    "action_rule": "缩量后只看确认",
                    "follow_state": "跌不下去",
                },
                {
                    "code": "000002",
                    "name": "走弱二号",
                    "sector": "消费",
                    "abnormal_score": 50,
                    "action_rule": "失守观察",
                    "follow_state": "已经转弱",
                },
            ],
            load_state=lambda: {
                "items": [
                    {
                        "code": "000001",
                        "name": "主线一号",
                        "status": "tentative",
                        "first_seen_date": "2026-04-20",
                        "last_seen_date": "2026-04-21",
                        "confirmations": 1,
                        "failures": 0,
                        "appearances": 1,
                    },
                    {
                        "code": "000002",
                        "name": "走弱二号",
                        "status": "tentative",
                        "first_seen_date": "2026-04-21",
                        "last_seen_date": "2026-04-21",
                        "confirmations": 0,
                        "failures": 0,
                        "appearances": 1,
                    },
                ]
            },
            save_state=lambda state: saved.update(state),
        )

        self.assertEqual(result["today_validated_items"][0]["code"], "000001")
        self.assertTrue(any(item["code"] == "000001" for item in result["promoted_items"]))
        self.assertTrue(any(item["code"] == "000002" for item in result["dropped_items"]))
        self.assertEqual(saved["updated_at"], "2026-04-22")
        self.assertEqual(saved["items"][0]["code"], "000001")


if __name__ == "__main__":
    unittest.main()
