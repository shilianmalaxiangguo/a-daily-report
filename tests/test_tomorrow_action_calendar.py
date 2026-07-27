import sys
import unittest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.tomorrow_action_calendar import (
    build_tomorrow_action_calendar,
    build_tomorrow_action_calendar_from_service,
)


class TomorrowActionCalendarTest(unittest.TestCase):
    def _index_bars(self):
        return [
            {"date": "2026-04-30", "open": 100.0, "close": 100.0},
            {"date": "2026-05-06", "open": 100.0, "close": 101.0},
            {"date": "2026-05-07", "open": 100.0, "close": 99.0},
            {"date": "2026-05-08", "open": 100.0, "close": 102.0},
            {"date": "2026-05-11", "open": 100.0, "close": 100.5},
        ]

    @staticmethod
    def _quote(trade_date, stock_code, open_price, close_price):
        return {
            "trade_date": trade_date,
            "stock_code": stock_code,
            "open": open_price,
            "close": close_price,
        }

    def test_each_plan_is_half_account_for_two_days_and_overlap_is_combined(self):
        quotes = {
            ("2026-05-06", "000001"): self._quote("2026-05-06", "000001", 100.0, 102.0),
            ("2026-05-07", "000001"): self._quote("2026-05-07", "000001", 101.0, 103.0),
            ("2026-05-07", "000002"): self._quote("2026-05-07", "000002", 200.0, 204.0),
            ("2026-05-08", "000002"): self._quote("2026-05-08", "000002", 204.0, 202.0),
        }
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-08",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-04-30", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"},
                    {"report_date": "2026-05-06", "action_type": "execute", "stock_name": "乙", "stock_code": "000002"},
                    {"report_date": "2026-05-07", "action_type": "no_trade", "can_new_entry": False},
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda day, codes: [
                quotes[(day, code)] for code in codes if (day, code) in quotes
            ],
        )

        first, overlap, carry = result["records"]
        self.assertEqual("2026-05-06", first["execution_date"])
        self.assertAlmostEqual(1.0, first["daily_return_pct"], places=6)
        self.assertEqual(50.0, first["total_position_pct"])
        self.assertEqual([1], [leg["holding_day"] for leg in first["active_legs"]])

        expected_overlap = (
            0.5 * ((103.0 / 101.0 - 1.0) * 100.0)
            + 0.5 * ((204.0 / 200.0 - 1.0) * 100.0)
        )
        self.assertEqual("2026-05-07", overlap["execution_date"])
        self.assertAlmostEqual(expected_overlap, overlap["daily_return_pct"], places=6)
        self.assertEqual(100.0, overlap["total_position_pct"])
        self.assertEqual([2, 1], [leg["holding_day"] for leg in overlap["active_legs"]])
        self.assertEqual(
            ["甲(000001)", "乙(000002)"],
            [item["label"] for item in overlap["action_items"]],
        )
        self.assertEqual(
            ["2026-04-30", "2026-05-06"],
            [item["plan_date_label"] for item in overlap["action_items"]],
        )

        self.assertEqual("2026-05-08", carry["execution_date"])
        self.assertEqual("no_new_entry", carry["plan_action_kind"])
        self.assertEqual("target", carry["action_kind"])
        self.assertEqual("乙(000002)", carry["action_label"])
        self.assertEqual(2, carry["active_legs"][0]["holding_day"])
        self.assertAlmostEqual(
            0.5 * ((202.0 / 204.0 - 1.0) * 100.0),
            carry["daily_return_pct"],
            places=6,
        )

    def test_same_stock_overlap_is_two_x_full_account(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-07",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-04-30", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"},
                    {"report_date": "2026-05-06", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"},
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda day, _codes: [self._quote(day, "000001", 100.0, 103.0)],
        )

        overlap = result["records"][1]
        self.assertAlmostEqual(3.0, overlap["daily_return_pct"], places=6)
        self.assertEqual(100.0, overlap["total_position_pct"])
        self.assertEqual(1, len(overlap["action_items"]))
        self.assertEqual("2x/100%", overlap["action_items"][0]["position_label"])
        self.assertEqual("第1+2日", overlap["action_items"][0]["holding_label"])
        self.assertEqual("2026-04-30/2026-05-06", overlap["action_items"][0]["plan_date_label"])

    def test_no_new_entry_keeps_prior_second_day_but_explicit_empty_clears_it(self):
        base_records = [
            {"report_date": "2026-04-30", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"}
        ]
        no_new = build_tomorrow_action_calendar(
            target_report_date="2026-05-07",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": base_records + [
                    {"report_date": "2026-05-06", "action_type": "no_trade", "can_new_entry": False}
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda day, _codes: [self._quote(day, "000001", 100.0, 104.0)],
            requested_count=1,
        )
        carry = no_new["records"][0]
        self.assertEqual("target", carry["action_kind"])
        self.assertEqual("no_new_entry", carry["plan_action_kind"])
        self.assertEqual(2, carry["active_legs"][0]["holding_day"])
        self.assertAlmostEqual(2.0, carry["daily_return_pct"], places=6)

        empty = build_tomorrow_action_calendar(
            target_report_date="2026-05-07",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": base_records + [
                    {"report_date": "2026-05-06", "action_type": "no_trade", "tomorrow_account_empty": True}
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda *_: self.fail("explicit empty must clear the carry leg"),
            requested_count=1,
        )["records"][0]
        self.assertEqual("empty", empty["action_kind"])
        self.assertEqual([], empty["active_legs"])
        self.assertEqual(0.0, empty["daily_return_pct"])
        self.assertAlmostEqual(1.0, empty["excess_shanghai_pct"], places=6)

    def test_no_new_entry_without_any_active_leg_is_account_empty(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-07",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-05-06", "action_type": "no_trade", "can_new_entry": False},
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda *_: [],
        )

        record = result["records"][0]
        self.assertEqual("empty", record["action_kind"])
        self.assertEqual("空仓", record["action_label"])
        self.assertEqual("no_new_entry", record["plan_action_kind"])
        self.assertEqual([], record["active_legs"])
        self.assertEqual(1, result["summary"]["empty_count"])
        self.assertEqual(1, result["summary"]["no_new_entry_count"])

    def test_calendar_notes_mark_holiday_and_sample_outside_without_affecting_records(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-06-22",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-06-16", "action_type": "no_trade", "can_new_entry": False},
                    {"report_date": "2026-06-17", "action_type": "no_trade", "can_new_entry": False},
                ],
            },
            index_bars=[
                {"date": "2026-06-17", "open": 100.0, "close": 100.0},
                {"date": "2026-06-18", "open": 100.0, "close": 100.0},
                {"date": "2026-06-22", "open": 100.0, "close": 100.0},
            ],
            stock_quote_loader=lambda *_: [],
        )

        self.assertEqual(2, result["record_count"])
        self.assertEqual(
            [{"date": "2026-06-19", "weekday_label": "周五", "kind": "holiday", "label": "端午休假", "source": "market_holiday_schedule"}],
            result["calendar_notes"],
        )

    def test_friday_and_holiday_eve_use_next_actual_index_bar(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-11",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-04-30", "action_type": "no_trade", "tomorrow_account_empty": True},
                    {"report_date": "2026-05-08", "action_type": "no_trade", "tomorrow_account_empty": True},
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda *_: [],
        )
        self.assertEqual(
            ["2026-05-06", "2026-05-11"],
            [row["execution_date"] for row in result["records"]],
        )
        self.assertEqual(["周三", "周一"], [row["weekday_label"] for row in result["records"]])

    def test_latest_report_uses_future_open_dates_for_both_holding_days(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-08",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-05-08", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"}
                ],
            },
            index_bars=self._index_bars()[:-1],
            stock_quote_loader=lambda *_: self.fail("future day must not load stock returns"),
            future_open_dates=["2026-05-11", "2026-05-12"],
        )
        record = result["records"][0]
        self.assertEqual("2026-05-11", record["execution_date"])
        self.assertEqual("future", record["performance_status"])
        self.assertEqual(1, record["active_legs"][0]["holding_day"])

    def test_missing_one_active_leg_or_index_open_remains_incomplete(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-07",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-04-30", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"},
                    {"report_date": "2026-05-06", "action_type": "execute", "stock_name": "乙", "stock_code": "000002"},
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda day, _codes: [self._quote(day, "000001", 100.0, 101.0)],
        )
        overlap = result["records"][1]
        self.assertEqual("incomplete", overlap["performance_status"])
        self.assertIsNone(overlap["daily_return_pct"])
        self.assertIn("stock_intraday_return", overlap["missing_fields"])

        missing_index = build_tomorrow_action_calendar(
            target_report_date="2026-05-06",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [{"report_date": "2026-04-30", "action_type": "no_trade", "tomorrow_account_empty": True}],
            },
            index_bars=[{"date": "2026-05-06", "close": 101.0}],
            stock_quote_loader=lambda *_: [],
        )
        self.assertEqual("2026-05-06", missing_index["records"][0]["execution_date"])
        self.assertIn("shanghai_intraday_return", missing_index["records"][0]["missing_fields"])

    def test_conflicting_index_bars_keep_trade_date_but_reject_return(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-06",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {
                        "report_date": "2026-04-30",
                        "action_type": "no_trade",
                        "tomorrow_account_empty": True,
                    }
                ],
            },
            index_bars=[
                {"date": "2026-05-06", "open": 100.0, "close": 101.0},
                {"date": "2026-05-06", "open": 100.0, "close": 102.0},
            ],
            stock_quote_loader=lambda *_: [],
        )

        record = result["records"][0]
        self.assertEqual("2026-05-06", record["execution_date"])
        self.assertEqual("incomplete", record["performance_status"])
        self.assertIsNone(record["shanghai_return_pct"])
        self.assertIn("shanghai_intraday_return", record["missing_fields"])

    def test_summary_compounds_daily_account_and_index_returns(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-07",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-04-30", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"},
                    {"report_date": "2026-05-06", "action_type": "execute", "stock_name": "乙", "stock_code": "000002"},
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda day, codes: [
                self._quote(day, code, 100.0, 102.0 if day == "2026-05-06" else 101.0)
                for code in codes
            ],
        )
        summary = result["summary"]
        self.assertEqual(2, summary["valid_count"])
        self.assertEqual(2, summary["plan_target_count"])
        self.assertEqual(2, summary["holding_count"])
        self.assertAlmostEqual(1.0, result["records"][0]["daily_return_pct"], places=6)
        self.assertAlmostEqual(1.0, result["records"][1]["daily_return_pct"], places=6)
        self.assertAlmostEqual(2.01, summary["cumulative_daily_return_pct"], places=6)
        self.assertAlmostEqual(-0.01, summary["cumulative_shanghai_return_pct"], places=6)
        self.assertAlmostEqual(2.02, summary["cumulative_excess_shanghai_pct"], places=6)

    def test_cumulative_returns_use_rolling_month_and_fixed_start_scopes(self):
        report_start = date(2026, 6, 1)
        report_end = date(2026, 7, 20)
        report_dates = [
            report_start + timedelta(days=offset)
            for offset in range((report_end - report_start).days + 1)
        ]
        trade_dates = [report_day + timedelta(days=1) for report_day in report_dates]
        result = build_tomorrow_action_calendar(
            target_report_date=report_end.isoformat(),
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {
                        "report_date": report_day.isoformat(),
                        "action_type": "execute",
                        "stock_name": "甲",
                        "stock_code": "000001",
                    }
                    for report_day in report_dates
                ],
            },
            index_bars=[
                {"date": trade_day.isoformat(), "open": 100.0, "close": 100.0}
                for trade_day in trade_dates
            ],
            stock_quote_loader=lambda day, codes: [
                self._quote(
                    day,
                    code,
                    100.0,
                    110.0 if day == "2026-06-17" else 102.0,
                )
                for code in codes
            ],
        )

        scopes = result["cumulative_returns"]
        self.assertEqual(25, result["record_count"])
        self.assertEqual(24, scopes["rolling_25"]["valid_count"])
        self.assertAlmostEqual(
            (1.02**24 - 1.0) * 100.0,
            scopes["rolling_25"]["cumulative_daily_return_pct"],
            places=6,
        )
        self.assertEqual("2026-07-01", scopes["current_month"]["period_start"])
        self.assertEqual(20, scopes["current_month"]["valid_count"])
        self.assertAlmostEqual(
            (1.02**20 - 1.0) * 100.0,
            scopes["current_month"]["cumulative_daily_return_pct"],
            places=6,
        )
        self.assertEqual("2026-06-17", scopes["since_start"]["period_start"])
        self.assertEqual(34, scopes["since_start"]["valid_count"])
        self.assertAlmostEqual(
            (1.10 * 1.02**33 - 1.0) * 100.0,
            scopes["since_start"]["cumulative_daily_return_pct"],
            places=6,
        )

    def test_summary_distinguishes_target_plans_from_holding_days(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-08",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-04-30", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"},
                    {"report_date": "2026-05-06", "action_type": "no_trade", "can_new_entry": False},
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda day, _codes: [self._quote(day, "000001", 100.0, 102.0)],
        )

        summary = result["summary"]
        self.assertEqual(1, summary["plan_target_count"])
        self.assertEqual(2, summary["holding_count"])
        self.assertEqual(1, summary["no_new_entry_count"])

    def test_more_than_two_active_legs_never_render_over_full_position(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-08",
            mode="frozen",
            ledger={
                "mode": "frozen",
                "records": [
                    {"report_date": "2026-05-01", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"},
                    {"report_date": "2026-05-02", "action_type": "execute", "stock_name": "乙", "stock_code": "000002"},
                    {"report_date": "2026-05-03", "action_type": "execute", "stock_name": "丙", "stock_code": "000003"},
                ],
            },
            index_bars=self._index_bars(),
            stock_quote_loader=lambda day, codes: [
                self._quote(day, code, 100.0, 101.0) for code in codes
            ],
        )

        record = result["records"][-1]
        self.assertEqual("incomplete", record["action_kind"])
        self.assertEqual([], record["action_items"])
        self.assertIsNone(record["total_position_pct"])
        self.assertIn("account_position_limit", record["missing_fields"])

    def test_latest_25_records_are_unique_and_duplicate_date_uses_last_value(self):
        bars = []
        records = []
        for day in range(1, 32):
            day_text = f"2026-03-{day:02d}"
            bars.append({"date": day_text, "open": 100.0, "close": 100.0})
            records.append({"report_date": day_text, "action_type": "no_trade", "tomorrow_account_empty": True})
        records.append({"report_date": "2026-03-07", "action_type": "execute", "stock_name": "重复末值", "stock_code": "000001"})
        result = build_tomorrow_action_calendar(
            target_report_date="2026-03-31",
            mode="frozen",
            ledger={"mode": "frozen", "records": records},
            index_bars=bars,
            stock_quote_loader=lambda *_: [],
        )
        self.assertEqual(25, result["record_count"])
        self.assertEqual("2026-03-07", result["report_date_start"])
        self.assertEqual("2026-03-31", result["report_date_end"])

    def test_conflicting_or_nonfinite_quotes_remain_incomplete(self):
        ledger = {
            "mode": "frozen",
            "records": [{"report_date": "2026-04-30", "action_type": "execute", "stock_name": "甲", "stock_code": "000001"}],
        }
        quote_sets = [
            [self._quote("2026-05-06", "000001", 100.0, 101.0), self._quote("2026-05-06", "000001", 100.0, 102.0)],
            [self._quote("2026-05-06", "000001", float("nan"), 101.0)],
        ]
        for quotes in quote_sets:
            with self.subTest(quotes=quotes):
                result = build_tomorrow_action_calendar(
                    target_report_date="2026-05-06",
                    mode="frozen",
                    ledger=ledger,
                    index_bars=self._index_bars(),
                    stock_quote_loader=lambda *_args, rows=quotes: rows,
                )
                self.assertEqual("incomplete", result["records"][0]["performance_status"])
                self.assertIsNone(result["records"][0]["daily_return_pct"])

    def test_mode_mismatch_returns_source_incomplete(self):
        result = build_tomorrow_action_calendar(
            target_report_date="2026-05-08",
            mode="replay",
            ledger={"mode": "frozen", "records": [{"report_date": "2026-05-07"}]},
            index_bars=self._index_bars(),
            stock_quote_loader=lambda *_: [],
        )
        self.assertEqual([], result["records"])
        self.assertIn("ledger_mode", result["missing_fields"])

    def test_service_prefers_factor_history_and_requests_one_context_record(self):
        calls = []

        class FakeService:
            def query_tomorrow_action_history(self, end_date, *, mode, limit):
                calls.append(("actions", end_date, mode, limit))
                return [{"report_date": "2026-06-02", "action_type": "execute", "stock_code": "600584", "stock_name": "长电科技"}]

            def query_index_daily_bars(self, *_args, **_kwargs):
                return [
                    {"date": "2026-06-02", "open": 4000.0, "close": 4000.0},
                    {"date": "2026-06-03", "open": 4000.0, "close": 4040.0},
                ]

            def query_stock_daily_quotes_recent(self, day, _codes):
                return [{"trade_date": day, "stock_code": "600584", "open": 10.0, "close": 10.2}]

        result = build_tomorrow_action_calendar_from_service(
            target_report_date="2026-06-03",
            mode="frozen",
            service=FakeService(),
            requested_count=25,
        )
        self.assertIn(("actions", "2026-06-03", "frozen", 26), calls)
        self.assertEqual("postgresql.strategy_factor_snapshot_fields", result["source"])
        self.assertAlmostEqual(1.0, result["records"][0]["daily_return_pct"], places=6)

    def test_service_requests_history_back_to_fixed_cumulative_start(self):
        calls = []

        class FakeService:
            def query_tomorrow_action_history(self, end_date, *, mode, limit):
                calls.append((end_date, mode, limit))
                return []

            def load_strategy_performance_ledger(self, mode):
                return {"mode": mode, "records": []}

            def query_index_daily_bars(self, *_args, **_kwargs):
                return []

            def query_stock_daily_quotes_recent(self, *_args, **_kwargs):
                return []

        build_tomorrow_action_calendar_from_service(
            target_report_date="2026-07-20",
            mode="frozen",
            service=FakeService(),
        )

        self.assertEqual([("2026-07-20", "frozen", 36)], calls)

    def test_service_database_failure_returns_source_incomplete(self):
        class FailingService:
            def query_tomorrow_action_history(self, *_args, **_kwargs):
                raise Exception("connection closed")

        result = build_tomorrow_action_calendar_from_service(
            target_report_date="2026-06-03",
            mode="frozen",
            service=FailingService(),
        )
        self.assertEqual("source_incomplete", result["status"])
        self.assertIn("postgresql", result["missing_fields"])


if __name__ == "__main__":
    unittest.main()
