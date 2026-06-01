import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research import tracking_memory_runtime as runtime
from research.tracking_memory_runtime import refresh_tracking_memory


class TrackingMemoryRuntimeTest(unittest.TestCase):
    def test_refresh_tracking_memory_uses_configured_database_state_store(self):
        saved = {}

        class StubService:
            def is_postgres_backed(self):
                return True

            def load_tracking_memory_state(self):
                return {
                    "items": [
                        {
                            "code": "601991",
                            "name": "大唐发电",
                            "sector": "电力",
                            "status": "tentative",
                            "first_seen_date": "2026-05-28",
                            "last_seen_date": "2026-05-28",
                            "confirmations": 1,
                            "failures": 0,
                            "appearances": 1,
                        }
                    ]
                }

            def save_tracking_memory_state(self, state):
                saved.update(state)
                return len(state.get("items") or [])

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return StubService()

        with patch.object(runtime, "DatabaseService", StubDatabaseService, create=True):
            with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                result = refresh_tracking_memory(
                    "2026-05-29",
                    watchlist=[{"code": "601991", "name": "大唐发电", "sector": "电力"}],
                    leader_memory_bank=[
                        {"code": "601991", "name": "大唐发电", "sector": "电力", "remember_score": 90}
                    ],
                    abnormal_watch_pool=[],
                )

        self.assertEqual(result["today_validated_items"][0]["code"], "601991")
        self.assertEqual(saved["updated_at"], "2026-05-29")
        self.assertEqual(saved["items"][0]["code"], "601991")

    def test_postgres_configured_service_failure_does_not_use_json_state(self):
        class BrokenDatabaseService:
            @classmethod
            def from_environment(cls):
                raise RuntimeError("database unavailable")

        with patch.object(runtime, "DatabaseService", BrokenDatabaseService, create=True):
            with patch.object(runtime, "_load_tracking_memory_state") as load_json:
                with patch.object(runtime, "_save_tracking_memory_state") as save_json:
                    with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                            refresh_tracking_memory(
                                "2026-05-29",
                                watchlist=[{"code": "601991", "name": "大唐发电", "sector": "电力"}],
                                leader_memory_bank=[],
                                abnormal_watch_pool=[],
                            )

        load_json.assert_not_called()
        save_json.assert_not_called()

    def test_postgres_only_runtime_without_database_rejects_json_state(self):
        with patch.object(runtime, "_load_tracking_memory_state") as load_json:
            with patch.object(runtime, "_save_tracking_memory_state") as save_json:
                with patch.dict("os.environ", {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "PostgreSQL-only tracking memory storage"):
                        refresh_tracking_memory(
                            "2026-05-29",
                            watchlist=[{"code": "601991", "name": "大唐发电", "sector": "电力"}],
                            leader_memory_bank=[],
                            abnormal_watch_pool=[],
                        )

        load_json.assert_not_called()
        save_json.assert_not_called()

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

    def test_failed_high_value_memory_turns_inactive_instead_of_deleted(self):
        saved = {}

        result = refresh_tracking_memory(
            "2026-04-10",
            watchlist=[],
            leader_memory_bank=[],
            abnormal_watch_pool=[
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "通信设备",
                    "abnormal_score": 45,
                    "action_rule": "跌停后取消买入资格",
                    "follow_state": "已经转弱",
                },
            ],
            load_state=lambda: {
                "items": [
                    {
                        "code": "000586",
                        "name": "汇源通信",
                        "sector": "通信设备",
                        "status": "tentative",
                        "first_seen_date": "2026-04-09",
                        "last_seen_date": "2026-04-09",
                        "confirmations": 1,
                        "failures": 0,
                        "appearances": 1,
                        "sources": ["abnormal_watch", "leader_memory", "watchlist"],
                        "last_reason": "首波先锋，优先做观察锚点 / 5连板已被资金记住",
                        "follow_state": "新异动待观察",
                        "evidence_score": 6,
                    },
                ]
            },
            save_state=lambda state: saved.update(state),
        )

        self.assertFalse(any(item["code"] == "000586" for item in result["dropped_items"]))
        inactive = [item for item in result["inactive_items"] if item["code"] == "000586"]
        self.assertEqual(len(inactive), 1)
        self.assertEqual(inactive[0]["status"], "inactive_failed")
        self.assertEqual(inactive[0]["first_seen_date"], "2026-04-09")
        self.assertIn("取消买入资格", inactive[0]["inactive_reason"])
        self.assertFalse(any(item["code"] == "000586" for item in result["today_tentative_items"]))
        self.assertEqual(saved["items"][0]["code"], "000586")
        self.assertEqual(saved["items"][0]["status"], "inactive_failed")

    def test_missing_high_value_memory_enters_recall_cooling_after_tentative_expiry(self):
        saved = {}

        result = refresh_tracking_memory(
            "2026-04-15",
            watchlist=[],
            leader_memory_bank=[],
            abnormal_watch_pool=[],
            load_state=lambda: {
                "items": [
                    {
                        "code": "000586",
                        "name": "汇源通信",
                        "sector": "通信设备",
                        "status": "tentative",
                        "first_seen_date": "2026-04-09",
                        "last_seen_date": "2026-04-09",
                        "confirmations": 1,
                        "failures": 0,
                        "appearances": 1,
                        "sources": ["abnormal_watch", "leader_memory", "watchlist"],
                        "last_reason": "首波先锋，优先做观察锚点 / 5连板已被资金记住",
                        "follow_state": "新异动待观察",
                        "evidence_score": 6,
                    },
                    {
                        "code": "000333",
                        "name": "普通三号",
                        "sector": "家电",
                        "status": "tentative",
                        "first_seen_date": "2026-04-09",
                        "last_seen_date": "2026-04-09",
                        "confirmations": 0,
                        "failures": 0,
                        "appearances": 1,
                        "sources": ["watchlist"],
                        "last_reason": "普通溢价预期",
                        "follow_state": "",
                        "evidence_score": 1,
                    },
                ]
            },
            save_state=lambda state: saved.update(state),
        )

        self.assertTrue(any(item["code"] == "000333" for item in result["dropped_items"]))
        self.assertFalse(any(item["code"] == "000586" for item in result["dropped_items"]))
        inactive = [item for item in result["inactive_items"] if item["code"] == "000586"]
        self.assertEqual(len(inactive), 1)
        self.assertEqual(inactive[0]["status"], "inactive_recall")
        self.assertEqual(inactive[0]["days_since_seen"], 6)
        self.assertIn("冷却回看", inactive[0]["inactive_reason"])
        self.assertEqual(saved["items"][0]["code"], "000586")
        self.assertEqual(saved["items"][0]["status"], "inactive_recall")

    def test_reappearing_inactive_high_value_memory_is_reactivated_not_new(self):
        saved = {}

        result = refresh_tracking_memory(
            "2026-05-19",
            watchlist=[{"code": "000586", "name": "汇源通信", "sector": "光通信", "tomorrow_expectation": "溢价预期"}],
            leader_memory_bank=[
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "光通信",
                    "remember_score": 76,
                    "remember_reason": "首波先锋，优先做重点观察谁 / 首波龙一",
                }
            ],
            abnormal_watch_pool=[
                {
                    "code": "000586",
                    "name": "汇源通信",
                    "sector": "光通信",
                    "abnormal_score": 37,
                    "action_rule": "涨停后先看次日承接",
                    "follow_state": "新异动待观察",
                }
            ],
            load_state=lambda: {
                "items": [
                    {
                        "code": "000586",
                        "name": "汇源通信",
                        "sector": "通信设备",
                        "status": "inactive_recall",
                        "first_seen_date": "2026-04-09",
                        "last_seen_date": "2026-04-15",
                        "confirmations": 1,
                        "failures": 0,
                        "appearances": 1,
                        "sources": ["abnormal_watch", "leader_memory", "watchlist"],
                        "last_reason": "首波先锋，优先做观察锚点 / 5连板已被资金记住",
                        "inactive_reason": "连续多日未再次入池，转入冷却回看",
                        "evidence_score": 6,
                    },
                ]
            },
            save_state=lambda state: saved.update(state),
        )

        self.assertFalse(any(item["code"] == "000586" for item in result["new_items"]))
        reactivated = [item for item in result["reactivated_items"] if item["code"] == "000586"]
        self.assertEqual(len(reactivated), 1)
        self.assertEqual(reactivated[0]["first_seen_date"], "2026-04-09")
        self.assertEqual(reactivated[0]["reactivated_from_status"], "inactive_recall")
        self.assertIn("旧强势样本再激活", reactivated[0]["last_reason"])
        self.assertEqual(saved["items"][0]["first_seen_date"], "2026-04-09")


if __name__ == "__main__":
    unittest.main()
