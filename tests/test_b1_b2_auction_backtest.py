from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class B1B2AuctionBacktestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from research import b1_b2_auction_backtest as backtest

        cls.backtest = backtest

    @staticmethod
    def _minute_bars(*, prices=None, volumes=None, trade_date="2026-07-08"):
        from research import b1_b2_auction_backtest as backtest

        times = backtest.expected_a_share_one_minute_bar_times()
        prices = list(prices or [10.0] * len(times))
        if len(prices) < len(times):
            prices.extend([prices[-1]] * (len(times) - len(prices)))
        volumes = list(volumes or [1000.0] * len(times))
        if len(volumes) < len(times):
            volumes.extend([volumes[-1]] * (len(times) - len(volumes)))
        bars = []
        for index, (time_text, close, volume) in enumerate(
            zip(times, prices, volumes, strict=True)
        ):
            open_price = prices[index - 1] if index else close
            bars.append(
                {
                    "datetime": f"{trade_date} {time_text}:00",
                    "open": float(open_price),
                    "high": float(max(open_price, close)),
                    "low": float(min(open_price, close)),
                    "close": float(close),
                    "volume": float(volume),
                    "amount": float(close * volume),
                }
            )
        return bars

    @classmethod
    def _benchmark_fixture(cls, daily_values):
        daily_bars = []
        minute_days = {}
        target_dates = []
        for trade_date, previous_close, open_price, close_price, tail_price in daily_values:
            if not daily_bars:
                daily_bars.append(
                    {
                        "date": previous_close[0],
                        "open": float(previous_close[1]),
                        "high": float(previous_close[1]),
                        "low": float(previous_close[1]),
                        "close": float(previous_close[1]),
                        "volume": 240000.0,
                        "amount": float(previous_close[1]) * 240000.0,
                    }
                )
            prices = [float(close_price)] * 240
            prices[0] = float(open_price)
            bars = cls._minute_bars(prices=prices, trade_date=trade_date)
            for bar in bars:
                if "14:31:00" <= bar["datetime"][-8:] <= "14:55:00":
                    bar.update(
                        open=float(tail_price),
                        high=float(tail_price),
                        low=float(tail_price),
                        close=float(tail_price),
                        amount=float(tail_price) * float(bar["volume"]),
                    )
            minute_days[trade_date] = bars
            target_dates.append(trade_date)
            aggregate = cls.backtest._aggregate_minute_day(bars)
            daily_bars.append(
                {
                    "date": trade_date,
                    **{key: aggregate[key] for key in ("open", "high", "low", "close")},
                    "volume": aggregate["volume"],
                    "amount": aggregate["amount"],
                }
            )
        source = {
            "query_date": cls.backtest.AS_OF_DATE,
            "source_dates": target_dates,
            "bar_time_semantics": "interval_end",
        }
        benchmark = {
            "code": cls.backtest.BENCHMARK_CODE,
            "name": cls.backtest.BENCHMARK_NAME,
            "market_number": cls.backtest.BENCHMARK_MARKET,
            "daily_bars": daily_bars,
            "minute_days": minute_days,
            "source": source,
        }
        benchmark["market_data_sha256"] = cls.backtest._canonical_hash(
            {
                "daily_bars": daily_bars,
                "minute_days": minute_days,
                "source": source,
            }
        )
        return benchmark

    @classmethod
    def _ledger_case(
        cls,
        *,
        case_id,
        name,
        entry_date,
        exit_date,
        entry_price,
        entry_close,
        exit_price,
        held_x=1.0,
        second_leg=False,
    ):
        legs = [
            {
                "weight_x": 1.0,
                "fill_price": float(entry_price),
                "fill_time": "09:30",
            }
        ]
        if second_leg:
            legs.append(
                {
                    "weight_x": 1.0,
                    "fill_price": float(entry_price),
                    "fill_time": "09:56",
                }
            )
        strategy = {
            "traded": True,
            "held_x": float(held_x),
            "legs": legs,
        }
        return {
            "case_id": case_id,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "security_code": "000001" if case_id.endswith("a") else "000002",
            "security_name": name,
            "primary_exit": {"price": float(exit_price)},
            "sensitivity_prices": {"entry_day_close": float(entry_close)},
            "daily_closes": {
                entry_date: float(entry_close),
                exit_date: float(exit_price),
            },
            "strategies": {
                strategy_id: copy.deepcopy(strategy)
                for strategy_id in cls.backtest.STRATEGY_ORDER
            },
        }

    @staticmethod
    def _zero_fee_parameters():
        return {
            "account_capital": 20000.0,
            "commission_rate": 0.0,
            "minimum_commission": 0.0,
            "stamp_tax_rate": 0.0,
            "transfer_fee_rate": 0.0,
        }

    def test_minute_grid_uses_complete_interval_end_slots(self):
        times = self.backtest.expected_a_share_one_minute_bar_times()

        self.assertEqual(len(times), 240)
        self.assertEqual(times[:3], ["09:31", "09:32", "09:33"])
        self.assertEqual(times[119:122], ["11:30", "13:01", "13:02"])
        self.assertEqual(times[-1], "15:00")

    def test_opening_gap_boundaries_are_stable(self):
        classify = self.backtest.classify_opening_gap

        self.assertEqual(classify(5.0), "大幅高开")
        self.assertEqual(classify(2.0), "中高开")
        self.assertEqual(classify(-1.999), "平开")
        self.assertEqual(classify(-2.0), "中低开")
        self.assertEqual(classify(-5.0), "大幅低开")

    def test_opening_b1_signal_fills_on_next_minute_only(self):
        prices = [10.0, 10.05, 10.1, 10.15, 10.2, 10.25]
        bars = self._minute_bars(prices=prices)

        result = self.backtest.find_b1_fill(
            bars,
            previous_close=10.0,
            t0_ma5=9.8,
        )

        self.assertEqual(result["path"], "opening_attack")
        self.assertEqual(result["signal_time"], "09:35")
        self.assertEqual(result["fill_time"], "09:36")
        self.assertEqual(result["fill_price"], bars[5]["open"])

    def test_secondary_window_never_fills_after_1010(self):
        prices = [9.8] * 39 + [10.1, 10.2, 10.3]
        bars = self._minute_bars(prices=prices)

        result = self.backtest.find_b1_fill(
            bars,
            previous_close=10.0,
            t0_ma5=10.0,
        )

        self.assertIsNone(result)

    def test_strategy_legs_keep_formal_b1_and_split_experiment_separate(self):
        features = {
            "open_price": 10.0,
            "open_fill_time": "09:30",
            "b1_fill": {
                "signal_time": "09:35",
                "fill_time": "09:36",
                "fill_price": 10.2,
                "path": "opening_attack",
            },
            "b2_fill": {
                "signal_time": "09:55",
                "fill_time": "09:56",
                "fill_price": 10.5,
                "path": "confirmation",
            },
        }

        two_x = self.backtest.build_strategy_legs(2, features)
        one_x = self.backtest.build_strategy_legs(1, features)

        self.assertEqual(
            [leg["weight_x"] for leg in two_x["auction_1x"]], [1.0]
        )
        self.assertEqual(
            [leg["weight_x"] for leg in two_x["qualified_b1_1x"]], [1.0]
        )
        self.assertEqual(
            [leg["weight_x"] for leg in two_x["split_1x_confirm"]],
            [0.5, 0.5],
        )
        self.assertEqual(
            [leg["weight_x"] for leg in two_x["formal_plan_b1_b2"]],
            [1.0, 1.0],
        )
        self.assertEqual(
            [leg["weight_x"] for leg in two_x["auction_full_plan"]], [2.0]
        )
        self.assertEqual(
            [leg["weight_x"] for leg in one_x["formal_plan_b1_b2"]], [1.0]
        )
        self.assertEqual(
            [leg["weight_x"] for leg in one_x["auction_full_plan"]], [1.0]
        )

    def test_return_calculation_uses_one_common_exit_and_t_plus_one(self):
        legs = {
            "auction_1x": [
                {"weight_x": 1.0, "fill_price": 10.0, "fill_time": "09:30"}
            ],
            "qualified_b1_1x": [
                {"weight_x": 1.0, "fill_price": 10.5, "fill_time": "09:56"}
            ],
        }

        results = self.backtest.evaluate_strategies(
            legs,
            exit_price=11.0,
            exit_time="2026-07-09 14:30-14:55",
            market="SZ",
            account_capital=20000.0,
            commission_rate=0.00025,
            minimum_commission=5.0,
            stamp_tax_rate=0.0005,
            transfer_fee_rate=0.00001,
        )

        self.assertEqual(results["auction_1x"]["exit_price"], 11.0)
        self.assertEqual(results["qualified_b1_1x"]["exit_price"], 11.0)
        self.assertEqual(
            results["auction_1x"]["exit_time"], "2026-07-09 14:30-14:55"
        )
        self.assertGreater(
            results["auction_1x"]["account_return_net_pct"],
            results["qualified_b1_1x"]["account_return_net_pct"],
        )

    def test_actual_one_x_allows_one_lot_inside_sixty_percent_band(self):
        legs = {
            "auction_1x": [
                {"weight_x": 1.0, "fill_price": 103.0, "fill_time": "09:30"}
            ]
        }

        results = self.backtest.evaluate_strategies(
            legs,
            exit_price=106.0,
            exit_time="2026-07-09 14:30-14:55",
            market="SZ",
            account_capital=20000.0,
            commission_rate=0.00025,
            minimum_commission=5.0,
            stamp_tax_rate=0.0005,
            transfer_fee_rate=0.00001,
        )

        self.assertEqual(results["auction_1x"]["actual_shares"], 100)
        self.assertAlmostEqual(
            results["auction_1x"]["actual_position_pct"], 51.5, places=3
        )

    def test_actual_one_x_chooses_closest_lot_count_inside_sixty_percent_band(self):
        legs = {
            "auction_1x": [
                {"weight_x": 1.0, "fill_price": 59.45, "fill_time": "09:30"}
            ]
        }

        results = self.backtest.evaluate_strategies(
            legs,
            exit_price=60.0,
            exit_time="2026-07-01 14:30-14:55",
            market="SZ",
            account_capital=20000.0,
            commission_rate=0.00025,
            minimum_commission=5.0,
            stamp_tax_rate=0.0005,
            transfer_fee_rate=0.00001,
        )

        self.assertEqual(results["auction_1x"]["actual_shares"], 200)
        self.assertAlmostEqual(
            results["auction_1x"]["actual_position_pct"], 59.45, places=3
        )

    def test_summary_separates_trade_win_rate_from_opportunity_positive_rate(self):
        rows = []
        for value, traded in ((2.0, True), (-1.0, True), (0.0, False)):
            strategies = {}
            for strategy_id in self.backtest.STRATEGY_ORDER:
                strategies[strategy_id] = {
                    "traded": traded,
                    "account_return_net_pct": value,
                    "mfe_price_pct": 3.0 if traded else None,
                    "mae_price_pct": -2.0 if traded else None,
                    "actual_shares": 100 if traded else 0,
                    "actual_return_net_pct": value,
                    "actual_all_legs_filled": traded,
                }
            rows.append({"strategies": strategies})

        summary = self.backtest.summarize_strategy_rows(rows)["auction_1x"]

        self.assertAlmostEqual(summary["win_rate_pct"], 50.0)
        self.assertAlmostEqual(summary["opportunity_positive_rate_pct"], 100 / 3, places=3)
        self.assertAlmostEqual(
            summary["mean_actual_account_return_net_pct"], 1 / 3, places=6
        )

    def test_tail_window_vwap_starts_with_first_full_minute_after_1430(self):
        bars = self._minute_bars(trade_date="2026-07-09")
        for bar in bars:
            bar["close"] = 10.0
            bar["volume"] = 100.0
            bar["amount"] = 1000.0
        bar_1430 = next(row for row in bars if row["datetime"].endswith("14:30:00"))
        bar_1430.update(close=100.0, volume=100.0, amount=10000.0)

        price = self.backtest.tail_window_exit_price(bars)

        self.assertEqual(price, 10.0)

    def test_standardized_daily_ledger_sums_two_half_weight_legs_on_overlap_day(self):
        benchmark = self._benchmark_fixture(
            [
                ("2026-01-05", ("2026-01-02", 100.0), 100.0, 101.0, 101.0),
                ("2026-01-06", ("2026-01-05", 101.0), 101.0, 102.0, 102.0),
                ("2026-01-07", ("2026-01-06", 102.0), 102.0, 103.0, 103.0),
            ]
        )
        cases = [
            self._ledger_case(
                case_id="case_a",
                name="旧仓",
                entry_date="2026-01-05",
                exit_date="2026-01-06",
                entry_price=10.0,
                entry_close=11.0,
                exit_price=12.0,
            ),
            self._ledger_case(
                case_id="case_b",
                name="新仓",
                entry_date="2026-01-06",
                exit_date="2026-01-07",
                entry_price=20.0,
                entry_close=22.0,
                exit_price=22.0,
            ),
        ]

        ledger = self.backtest._build_standardized_daily_ledger(
            cases,
            benchmark,
            self._zero_fee_parameters(),
            "auction_1x",
        )
        overlap = next(row for row in ledger["daily"] if row["date"] == "2026-01-06")

        self.assertEqual(overlap["peak_nominal_x"], 2.0)
        self.assertEqual(
            sorted(row["account_weight_pct"] for row in overlap["contributions"]),
            [50.0, 50.0],
        )
        self.assertEqual(
            {row["role"] for row in overlap["contributions"]},
            {"旧仓尾盘退出", "新仓入场至收盘"},
        )
        self.assertAlmostEqual(
            overlap["account_return_pct"],
            sum(row["account_contribution_pct"] for row in overlap["contributions"]),
            places=6,
        )
        self.assertLessEqual(
            max(row["peak_nominal_x"] for row in ledger["daily"]), 2.0
        )

    def test_standardized_daily_ledger_does_not_add_b2_while_old_one_x_is_open(self):
        benchmark = self._benchmark_fixture(
            [
                ("2026-01-05", ("2026-01-02", 100.0), 100.0, 100.0, 100.0),
                ("2026-01-06", ("2026-01-05", 100.0), 100.0, 100.0, 100.0),
                ("2026-01-07", ("2026-01-06", 100.0), 100.0, 100.0, 100.0),
            ]
        )
        cases = [
            self._ledger_case(
                case_id="case_a",
                name="旧仓",
                entry_date="2026-01-05",
                exit_date="2026-01-06",
                entry_price=10.0,
                entry_close=10.0,
                exit_price=10.0,
            ),
            self._ledger_case(
                case_id="case_b",
                name="新仓",
                entry_date="2026-01-06",
                exit_date="2026-01-07",
                entry_price=20.0,
                entry_close=20.0,
                exit_price=20.0,
                held_x=2.0,
                second_leg=True,
            ),
        ]

        ledger = self.backtest._build_standardized_daily_ledger(
            cases,
            benchmark,
            self._zero_fee_parameters(),
            "formal_plan_b1_b2",
        )
        overlap = next(row for row in ledger["daily"] if row["date"] == "2026-01-06")
        new_buys = [
            row
            for row in overlap["actions"]
            if row["action"] == "buy" and row["case_id"] == "case_b"
        ]

        self.assertEqual([row["status"] for row in new_buys], ["executed", "not_executed"])
        self.assertEqual(new_buys[1]["reason"], "旧仓仍占满账户容量，早盘不新增")
        self.assertEqual(overlap["peak_nominal_x"], 2.0)
        self.assertEqual(overlap["ending_nominal_x"], 1.0)

    def test_standardized_daily_ledger_splits_entry_day_and_overnight_exit_return(self):
        benchmark = self._benchmark_fixture(
            [
                ("2026-01-05", ("2026-01-02", 100.0), 100.0, 100.0, 100.0),
                ("2026-01-06", ("2026-01-05", 100.0), 90.0, 90.0, 90.0),
            ]
        )
        case = self._ledger_case(
            case_id="case_a",
            name="隔夜样本",
            entry_date="2026-01-05",
            exit_date="2026-01-06",
            entry_price=10.0,
            entry_close=11.0,
            exit_price=9.0,
        )

        ledger = self.backtest._build_standardized_daily_ledger(
            [case],
            benchmark,
            self._zero_fee_parameters(),
            "auction_1x",
        )
        entry_leg = ledger["daily"][0]["contributions"][0]
        exit_leg = ledger["daily"][1]["contributions"][0]

        self.assertEqual(entry_leg["role"], "新仓入场至收盘")
        self.assertAlmostEqual(entry_leg["price_return_pct"], 10.0, places=6)
        self.assertEqual(exit_leg["role"], "旧仓尾盘退出")
        self.assertAlmostEqual(exit_leg["start_price"], 11.0, places=6)
        self.assertAlmostEqual(exit_leg["price_return_pct"], -18.181818, places=6)

    def test_standardized_daily_ledger_matches_single_trade_when_entry_day_is_flat(self):
        benchmark = self._benchmark_fixture(
            [
                ("2026-01-05", ("2026-01-02", 100.0), 100.0, 100.0, 100.0),
                ("2026-01-06", ("2026-01-05", 100.0), 100.0, 100.0, 100.0),
            ]
        )
        case = self._ledger_case(
            case_id="case_a",
            name="单笔样本",
            entry_date="2026-01-05",
            exit_date="2026-01-06",
            entry_price=10.0,
            entry_close=10.0,
            exit_price=11.0,
        )

        ledger = self.backtest._build_standardized_daily_ledger(
            [case],
            benchmark,
            self._zero_fee_parameters(),
            "auction_1x",
        )

        self.assertAlmostEqual(ledger["cumulative_return_pct"], 5.0, places=6)

    def test_standardized_daily_ledger_marks_intermediate_holding_days(self):
        benchmark = self._benchmark_fixture(
            [
                ("2026-01-05", ("2026-01-02", 100.0), 100.0, 100.0, 100.0),
                ("2026-01-06", ("2026-01-05", 100.0), 100.0, 101.0, 101.0),
                ("2026-01-07", ("2026-01-06", 101.0), 101.0, 102.0, 102.0),
            ]
        )
        case = self._ledger_case(
            case_id="case_a",
            name="三日样本",
            entry_date="2026-01-05",
            exit_date="2026-01-07",
            entry_price=10.0,
            entry_close=10.0,
            exit_price=12.0,
        )
        case["daily_closes"]["2026-01-06"] = 11.0

        ledger = self.backtest._build_standardized_daily_ledger(
            [case],
            benchmark,
            self._zero_fee_parameters(),
            "auction_1x",
        )

        self.assertEqual([row["date"] for row in ledger["daily"]], [
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
        ])
        intermediate = ledger["daily"][1]["contributions"][0]
        self.assertEqual(intermediate["role"], "持仓日收盘标记")
        self.assertAlmostEqual(intermediate["price_return_pct"], 10.0, places=6)
        self.assertAlmostEqual(
            ledger["daily"][2]["contributions"][0]["start_price"],
            11.0,
            places=6,
        )

    def test_benchmark_validator_rejects_missing_dates_minutes_and_amount_mismatch(self):
        benchmark = self._benchmark_fixture(
            [
                ("2026-01-05", ("2026-01-02", 100.0), 100.0, 101.0, 101.0),
                ("2026-01-06", ("2026-01-05", 101.0), 101.0, 102.0, 102.0),
            ]
        )
        target_dates = ["2026-01-05", "2026-01-06"]

        self.backtest.validate_benchmark_market_data(benchmark, target_dates)
        missing_daily = copy.deepcopy(benchmark)
        missing_daily["daily_bars"] = missing_daily["daily_bars"][:-1]
        with self.assertRaisesRegex(ValueError, "daily bar missing"):
            self.backtest.validate_benchmark_market_data(missing_daily, target_dates)
        missing_minute = copy.deepcopy(benchmark)
        missing_minute["minute_days"]["2026-01-05"].pop()
        with self.assertRaisesRegex(ValueError, "240"):
            self.backtest.validate_benchmark_market_data(missing_minute, target_dates)
        wrong_amount = copy.deepcopy(benchmark)
        wrong_amount["daily_bars"][1]["amount"] *= 2.0
        with self.assertRaisesRegex(ValueError, "amount mismatch"):
            self.backtest.validate_benchmark_market_data(wrong_amount, target_dates)

    def test_fixture_validator_rejects_future_or_incomplete_minute_data(self):
        bars = self._minute_bars()
        case = {
            "case_id": "synthetic",
            "report_date": "2026-07-07",
            "entry_date": "2026-07-08",
            "exit_date": "2026-07-09",
            "daily_bars": [
                {
                    "date": "2026-07-07",
                    "open": 9.8,
                    "high": 10.1,
                    "low": 9.7,
                    "close": 10.0,
                    "volume": 1,
                    "amount": 10,
                },
                {
                    "date": "2026-07-08",
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 240000,
                    "amount": 2400000,
                },
                {
                    "date": "2026-07-09",
                    "open": 10.0,
                    "high": 10.0,
                    "low": 10.0,
                    "close": 10.0,
                    "volume": 240000,
                    "amount": 2400000,
                },
            ],
            "minute_days": {
                "2026-07-08": bars,
                "2026-07-09": self._minute_bars(trade_date="2026-07-09"),
            },
        }

        self.backtest.validate_case_market_data(copy.deepcopy(case))
        incomplete = copy.deepcopy(case)
        incomplete["minute_days"]["2026-07-08"].pop()
        with self.assertRaisesRegex(ValueError, "240"):
            self.backtest.validate_case_market_data(incomplete)
        future = copy.deepcopy(case)
        future["minute_days"]["2026-07-08"][0]["datetime"] = (
            "2026-07-09 09:31:00"
        )
        with self.assertRaisesRegex(ValueError, "entry_date"):
            self.backtest.validate_case_market_data(future)

        wrong_volume = copy.deepcopy(case)
        wrong_volume["daily_bars"][1]["volume"] *= 2
        with self.assertRaisesRegex(ValueError, "volume mismatch"):
            self.backtest.validate_case_market_data(wrong_volume)

    def test_fixture_validator_checks_source_dates_and_report_evidence(self):
        fixture_path = ROOT / "tests" / "fixtures" / "b1_b2_auction_backtest" / "cases.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        wrong_dates = copy.deepcopy(fixture)
        wrong_dates["cases"][0]["source"]["source_dates"] = [
            wrong_dates["cases"][0]["entry_date"],
            wrong_dates["cases"][0]["entry_date"],
        ]
        with self.assertRaisesRegex(ValueError, "source_dates mismatch"):
            self.backtest.validate_fixture(wrong_dates)

        wrong_report_hash = copy.deepcopy(fixture)
        wrong_report_hash["cases"][0]["report_source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "report source sha256 mismatch"):
            self.backtest.validate_fixture(wrong_report_hash)

        wrong_coverage = copy.deepcopy(fixture)
        wrong_coverage["coverage"]["no_action_count"] -= 1
        with self.assertRaisesRegex(ValueError, "coverage"):
            self.backtest.validate_fixture(wrong_coverage)

        wrong_provider = copy.deepcopy(fixture)
        wrong_provider["cases"][0]["source"]["host"] = "127.0.0.1"
        with self.assertRaisesRegex(ValueError, "source host mismatch"):
            self.backtest.validate_fixture(wrong_provider)

    def test_backtest_discloses_unverified_tradeability(self):
        fixture_path = ROOT / "tests" / "fixtures" / "b1_b2_auction_backtest" / "cases.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        payload = self.backtest.build_backtest(fixture)

        self.assertTrue(any("停牌" in item for item in payload["limitations"]))
        self.assertTrue(any("涨跌停" in item for item in payload["limitations"]))
        self.assertEqual(
            payload["missed_opportunity_summary"],
            {
                "qualified_b1_not_participated_case_count": 6,
                "missed_positive_auction_outcome_count": 3,
                "avoided_negative_auction_outcome_count": 3,
            },
        )
        self.assertEqual(len(payload["combination_summaries"]), 15)
        empty_group = next(
            group
            for group in payload["combination_summaries"]
            if group["case_count"] == 0
        )
        self.assertIsNone(
            empty_group["strategies"]["auction_1x"][
                "independent_compound_return_pct"
            ]
        )
        huatian = next(
            case for case in payload["cases"] if case["case_id"] == "20260707_002185"
        )
        self.assertEqual(huatian["features"]["status_0935"]["time"], "09:35")
        self.assertEqual(huatian["features"]["status_1010"]["time"], "10:10")
        self.assertEqual(
            huatian["features"]["b1_decision"]["status"], "not_participated"
        )
        self.assertTrue(
            huatian["missed_opportunity"]["missed_positive_auction_outcome"]
        )
        normalized_ledgers = payload["daily_ledgers"]["standardized"]
        actual_ledgers = payload["daily_ledgers"]["actual_lots"]
        self.assertAlmostEqual(
            normalized_ledgers["auction_1x"]["cumulative_return_pct"],
            5.378534,
            places=6,
        )
        self.assertAlmostEqual(
            normalized_ledgers["qualified_b1_1x"]["cumulative_return_pct"],
            5.365208,
            places=6,
        )
        self.assertLess(
            abs(normalized_ledgers["qualified_b1_1x"]["maximum_drawdown_pct"]),
            abs(normalized_ledgers["auction_1x"]["maximum_drawdown_pct"]),
        )
        self.assertAlmostEqual(
            actual_ledgers["auction_1x"]["cumulative_return_pct"],
            -3.014401,
            places=6,
        )
        overlap = next(
            row
            for row in normalized_ledgers["auction_1x"]["daily"]
            if row["date"] == "2026-06-04"
        )
        self.assertEqual(overlap["peak_nominal_x"], 2.0)
        self.assertEqual(
            sorted(item["account_weight_pct"] for item in overlap["contributions"]),
            [50.0, 50.0],
        )
        markdown = self.backtest.render_markdown(payload)
        self.assertIn("佣金万2.5", markdown)
        self.assertIn("印花税万5", markdown)
        self.assertIn("过户费万0.1", markdown)
        self.assertIn("个百分点", markdown)
        self.assertIn("## B1/B2固定回放规则", markdown)
        self.assertIn("B1未执行时B2不单独出现", markdown)
        self.assertIn("逐日账户收益基本打平", markdown)
        self.assertIn("+5.38%", markdown)
        self.assertIn("-11.55%", markdown)
        self.assertIn("逐笔独立旁证（不是账户累计）", markdown)
        self.assertIn("本轮最优解边界与收益解释", markdown)
        self.assertIn("这不代表2万元整手账本相同", markdown)
        explanation = markdown.split("### 本轮最优解边界与收益解释", 1)[1].split(
            "### 逐日账户账本", 1
        )[0]
        self.assertIn("正式B1/B2累计 +5.37%", explanation)
        self.assertIn("开盘直接买完整计划累计 +1.34%", explanation)
        self.assertIn("正式B1/B2累计 -10.45%", explanation)
        self.assertIn("开盘直接买完整计划累计 -1.07%", explanation)
        self.assertIn("拆分1x实验的整手累计为 +1.32%", explanation)

        changed_payload = copy.deepcopy(payload)
        changed_payload["daily_ledgers"]["standardized"]["auction_full_plan"][
            "cumulative_return_pct"
        ] = 12.345
        changed_payload["daily_ledgers"]["standardized"]["auction_full_plan"][
            "maximum_drawdown_pct"
        ] = -4.321
        changed_explanation = self.backtest.render_markdown(changed_payload).split(
            "### 本轮最优解边界与收益解释", 1
        )[1].split("### 逐日账户账本", 1)[0]
        self.assertIn("开盘直接买完整计划累计 +12.35%", changed_explanation)
        self.assertIn("最大回撤 -4.32%", changed_explanation)
        self.assertNotIn("开盘直接买完整计划累计 +1.34%", changed_explanation)

    def test_markdown_is_rendered_only_from_stable_payload(self):
        payload = {
            "schema_version": "b1_b2_auction_backtest.v2",
            "as_of_date": "2026-07-21",
            "coverage": {
                "report_count": 35,
                "positive_case_count": 14,
                "standardized_case_count": 12,
                "window_start": "2026-06-01",
                "window_end": "2026-07-21",
            },
            "parameters": {"primary_exit": "T+2 14:30-14:55"},
            "summaries": {"all": {}, "standardized": {}},
            "scenario_summaries": [],
            "cases": [],
            "limitations": ["样本不足"],
            "conclusion": {"verdict": "初步证据不足"},
        }

        first = self.backtest.render_markdown(copy.deepcopy(payload))
        second = self.backtest.render_markdown(json.loads(json.dumps(payload)))

        self.assertEqual(first, second)
        self.assertIn("14 笔", first)
        self.assertIn("初步证据不足", first)
        self.assertIn("2026-06-01 至 2026-07-21 收益怎么读", first)
        self.assertIn("真实2万元账户区间累计收益", first)


if __name__ == "__main__":
    unittest.main()
