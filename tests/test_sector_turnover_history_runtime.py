import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class SectorTurnoverHistoryRuntimeTest(unittest.TestCase):
    def _load_module(self):
        try:
            return importlib.import_module("domains.market_state.sector_turnover_history_runtime")
        except ModuleNotFoundError as error:
            self.fail(f"domains.market_state.sector_turnover_history_runtime should exist: {error}")

    def test_load_recent_sector_turnover_history_reads_raw_snapshot_contract(self):
        runtime = self._load_module()

        result = runtime.load_recent_sector_turnover_history(
            "2026-04-24",
            "半导体",
            lookback_days=2,
            helpers={
                "DatabaseService": None,
                "_normalize_kline_date_str": lambda value: str(value),
                "get_previous_date_str": lambda value: {
                    "2026-04-24": "2026-04-23",
                    "2026-04-23": "2026-04-22",
                    "2026-04-22": "",
                }.get(value, ""),
                "load_data_snapshot": lambda cursor: (
                    {
                        "2026-04-23": {
                            "sector_turnover_snapshot": {
                                "date": "2026-04-23",
                                "sector_name": "半导体",
                                "sector_turnover": 2702.94,
                                "total_turnover": 12345.60,
                                "turnover_share_pct": 21.89,
                                "matched_sector_names": ["半导体"],
                                "matched_sector_codes": ["URFI881121"],
                                "source": "thsdk.market_data_block",
                            }
                        },
                        "2026-04-22": {
                            "sector_turnover_snapshot": {
                                "date": "2026-04-22",
                                "sector_name": "半导体",
                                "sector_turnover": 2500.00,
                                "total_turnover": 12000.00,
                                "turnover_share_pct": 20.83,
                                "matched_sector_names": ["半导体"],
                                "matched_sector_codes": ["URFI881121"],
                                "source": "thsdk.market_data_block",
                            }
                        },
                    }.get(cursor, {}),
                    None,
                ),
                "sector_name_matches": lambda left, right: str(left or "") == str(right or "") or str(left or "") in str(right or "") or str(right or "") in str(left or ""),
            },
        )

        self.assertEqual(
            result,
            [
                {
                    "date": "2026-04-22",
                    "sector_name": "半导体",
                    "sector_turnover": 2500.0,
                    "total_turnover": 12000.0,
                    "turnover_share_pct": 20.83,
                    "matched_sector_names": ["半导体"],
                    "matched_sector_codes": ["URFI881121"],
                    "source": "thsdk.market_data_block",
                },
                {
                    "date": "2026-04-23",
                    "sector_name": "半导体",
                    "sector_turnover": 2702.94,
                    "total_turnover": 12345.6,
                    "turnover_share_pct": 21.89,
                    "matched_sector_names": ["半导体"],
                    "matched_sector_codes": ["URFI881121"],
                    "source": "thsdk.market_data_block",
                },
            ],
        )

    def test_default_history_fallback_uses_compact_snapshot_loader(self):
        runtime = self._load_module()
        full_loader = Mock(side_effect=AssertionError("完整快照 loader 不应被调用"))
        compact_loader = Mock(
            return_value=(
                {
                    "sector_turnover_snapshots": [
                        {
                            "date": "2026-07-22",
                            "sector_name": "脑机接口",
                            "sector_turnover": 321.0,
                            "turnover_share_pct": 2.6,
                        }
                    ],
                    "turnover_data": {"total_amount_yi": 12345.0},
                },
                "",
            )
        )

        with patch.object(runtime, "load_data_snapshot", full_loader), \
             patch.object(runtime, "_DEFAULT_LOAD_DATA_SNAPSHOT", full_loader):
            result = runtime.load_recent_sector_turnover_history(
                "2026-07-23",
                "脑机接口",
                lookback_days=1,
                max_scan_days=1,
                helpers={
                    "DatabaseService": None,
                    "_normalize_kline_date_str": lambda value: str(value),
                    "get_previous_date_str": lambda value: "2026-07-22" if value == "2026-07-23" else "",
                    "load_compact_metric_history_snapshot": compact_loader,
                },
            )

        self.assertEqual(result[0]["sector_turnover"], 321.0)
        self.assertEqual(result[0]["total_turnover"], 12345.0)
        compact_loader.assert_called_once_with("2026-07-22")
        full_loader.assert_not_called()

    def test_load_recent_sector_turnover_history_reads_nested_wrapped_snapshot_and_alias_match(self):
        runtime = self._load_module()

        result = runtime.load_recent_sector_turnover_history(
            "2026-04-24",
            "通信设备",
            lookback_days=1,
            helpers={
                "DatabaseService": None,
                "_normalize_kline_date_str": lambda value: str(value),
                "get_previous_date_str": lambda value: {
                    "2026-04-24": "2026-04-23",
                    "2026-04-23": "",
                }.get(value, ""),
                "load_data_snapshot": lambda cursor: (
                    {
                        "2026-04-23": {
                            "decision": {
                                "market_research_snapshot": {
                                    "sector_turnover_snapshots": [
                                        {
                                            "date": "2026-04-23",
                                            "sector_name": "通信",
                                            "sector_turnover": 2000.0,
                                            "total_turnover": 10000.0,
                                            "turnover_share_pct": 20.0,
                                            "matched_sector_names": ["通信设备", "通信服务"],
                                            "matched_sector_codes": ["URFI100001", "URFI100002"],
                                            "source": "thsdk.market_data_block",
                                        },
                                        {
                                            "date": "2026-04-23",
                                            "sector_name": "半导体",
                                            "sector_turnover": 2702.94,
                                            "total_turnover": 12345.6,
                                            "turnover_share_pct": 21.89,
                                            "matched_sector_names": ["半导体"],
                                            "matched_sector_codes": ["URFI881121"],
                                            "source": "thsdk.market_data_block",
                                        },
                                    ]
                                }
                            }
                        }
                    }.get(cursor, {}),
                    None,
                ),
                "sector_name_matches": lambda left, right: str(left or "") == str(right or "") or str(left or "") in str(right or "") or str(right or "") in str(left or ""),
            },
        )

        self.assertEqual(
            result,
            [
                {
                    "date": "2026-04-23",
                    "sector_name": "通信",
                    "sector_turnover": 2000.0,
                    "total_turnover": 10000.0,
                    "turnover_share_pct": 20.0,
                    "matched_sector_names": ["通信设备", "通信服务"],
                    "matched_sector_codes": ["URFI100001", "URFI100002"],
                    "source": "thsdk.market_data_block",
                }
            ],
        )

    def test_load_recent_sector_turnover_history_reads_current_snapshot_key(self):
        runtime = self._load_module()

        result = runtime.load_recent_sector_turnover_history(
            "2026-05-20",
            "电力",
            lookback_days=1,
            helpers={
                "DatabaseService": None,
                "_normalize_kline_date_str": lambda value: str(value),
                "get_previous_date_str": lambda value: {
                    "2026-05-20": "2026-05-19",
                    "2026-05-19": "",
                }.get(value, ""),
                "load_data_snapshot": lambda cursor: (
                    {
                        "data": {
                            "current_sector_turnover_snapshot": {
                                "date": "2026-05-19",
                                "sector_name": "电力",
                                "sector_turnover": 665.0,
                                "total_turnover": 29089.77,
                                "turnover_share_pct": 2.29,
                                "matched_sector_names": ["电力"],
                                "source": "tencent.fundflow.getHyRank",
                            }
                        }
                    },
                    None,
                ),
                "sector_name_matches": lambda left, right: str(left or "") == str(right or "") or str(left or "") in str(right or "") or str(right or "") in str(left or ""),
            },
        )

        self.assertEqual(result[0]["date"], "2026-05-19")
        self.assertEqual(result[0]["sector_name"], "电力")
        self.assertEqual(result[0]["sector_turnover"], 665.0)
        self.assertEqual(result[0]["turnover_share_pct"], 2.29)

    def test_load_recent_sector_turnover_history_reads_tushare_fund_flow_from_snapshot(self):
        runtime = self._load_module()

        result = runtime.load_recent_sector_turnover_history(
            "2026-05-20",
            "半导体",
            lookback_days=1,
            helpers={
                "DatabaseService": None,
                "_normalize_kline_date_str": lambda value: str(value),
                "get_previous_date_str": lambda value: {
                    "2026-05-20": "2026-05-19",
                    "2026-05-19": "",
                }.get(value, ""),
                "load_data_snapshot": lambda cursor: (
                    {
                        "data": {
                            "total_turnover": 29089.77,
                            "sector_fund_flow": {
                                "inflow": [
                                    {
                                        "name": "半导体",
                                        "code": "881121.TI",
                                        "net_buy_amount": 1812.0,
                                        "net_sell_amount": 1628.0,
                                        "turnover_yi": 3440.0,
                                        "data_source": "tushare.moneyflow_ind_ths",
                                        "trade_date": "2026-05-19",
                                    }
                                ],
                                "outflow": [],
                            },
                        }
                    },
                    None,
                ),
                "sector_name_matches": lambda left, right: str(left or "") == str(right or "") or str(left or "") in str(right or "") or str(right or "") in str(left or ""),
            },
        )

        self.assertEqual(result[0]["date"], "2026-05-19")
        self.assertEqual(result[0]["sector_name"], "半导体")
        self.assertEqual(result[0]["sector_turnover"], 3440.0)
        self.assertEqual(result[0]["total_turnover"], 29089.77)
        self.assertEqual(result[0]["turnover_share_pct"], 11.83)
        self.assertEqual(result[0]["source"], "tushare.moneyflow_ind_ths")

    def test_load_recent_sector_turnover_history_fetches_tushare_when_snapshot_lacks_sector(self):
        runtime = self._load_module()
        fetch_calls = []

        result = runtime.load_recent_sector_turnover_history(
            "2026-05-20",
            "半导体",
            lookback_days=1,
            helpers={
                "DatabaseService": None,
                "_normalize_kline_date_str": lambda value: str(value),
                "get_previous_date_str": lambda value: {
                    "2026-05-20": "2026-05-19",
                    "2026-05-19": "",
                }.get(value, ""),
                "load_data_snapshot": lambda cursor: (
                    {
                        "data": {
                            "total_turnover": 29089.77,
                            "sector_fund_flow": {"inflow": [], "outflow": []},
                        }
                    },
                    None,
                ),
                "fetch_tushare_sector_flow": lambda trade_date: fetch_calls.append(trade_date)
                or [
                    {
                        "trade_date": "2026-05-19",
                        "industry": "半导体",
                        "ts_code": "881121.TI",
                        "net_buy_amount": 1812.0,
                        "net_sell_amount": 1628.0,
                    }
                ],
                "sector_name_matches": lambda left, right: str(left or "") == str(right or "") or str(left or "") in str(right or "") or str(right or "") in str(left or ""),
            },
        )

        self.assertEqual(fetch_calls, ["2026-05-19"])
        self.assertEqual(result[0]["date"], "2026-05-19")
        self.assertEqual(result[0]["sector_turnover"], 3440.0)
        self.assertEqual(result[0]["turnover_share_pct"], 11.83)

    def test_load_recent_sector_turnover_history_fills_missing_total_from_fact_db(self):
        runtime = self._load_module()

        result = runtime.load_recent_sector_turnover_history(
            "2026-05-20",
            "半导体",
            lookback_days=1,
            helpers={
                "DatabaseService": None,
                "_normalize_kline_date_str": lambda value: str(value),
                "get_previous_date_str": lambda value: {
                    "2026-05-20": "2026-05-13",
                    "2026-05-13": "",
                }.get(value, ""),
                "load_data_snapshot": lambda cursor: (
                    {
                        "data": {
                            "total_turnover": 0.0,
                            "sector_fund_flow": {
                                "inflow": [
                                    {
                                        "name": "半导体",
                                        "code": "881121.TI",
                                        "turnover_yi": 4024.5,
                                        "data_source": "tushare.moneyflow_ind_ths",
                                        "trade_date": "2026-05-13",
                                    }
                                ],
                                "outflow": [],
                            },
                        }
                    },
                    None,
                ),
                "get_market_total_turnover_from_fact_db": lambda trade_date: 32642.12,
                "sector_name_matches": lambda left, right: str(left or "") == str(right or "") or str(left or "") in str(right or "") or str(right or "") in str(left or ""),
            },
        )

        self.assertEqual(result[0]["total_turnover"], 32642.12)
        self.assertEqual(result[0]["turnover_share_pct"], 12.33)

    def test_load_recent_sector_turnover_history_prefers_fact_db_before_snapshot_scan(self):
        runtime = self._load_module()
        calls = []

        class FakeDatabaseService:
            @classmethod
            def fact_store_from_environment(cls, db_path=None):
                calls.append(("db", db_path))
                return cls()

            def query_mainline_turnover_series(self, end_date, sector_name, *, window_days=25):
                calls.append(("query", end_date, sector_name, window_days))
                return [
                    {
                        "date": "2026-05-18",
                        "sector_name": "半导体",
                        "sector_turnover": 3900.0,
                        "total_turnover": 29170.74,
                        "turnover_share_pct": 13.37,
                        "matched_sector_names": ["半导体"],
                        "matched_sector_codes": ["881121.TI"],
                        "source": "fact_db.mainline_turnover_daily",
                    },
                    {
                        "date": "2026-05-19",
                        "sector_name": "半导体",
                        "sector_turnover": 4050.0,
                        "total_turnover": 29764.59,
                        "turnover_share_pct": 13.61,
                        "matched_sector_names": ["半导体"],
                        "matched_sector_codes": ["881121.TI"],
                        "source": "fact_db.mainline_turnover_daily",
                    },
                ]

        result = runtime.load_recent_sector_turnover_history(
            "2026-05-20",
            "半导体",
            lookback_days=2,
            helpers={
                "DatabaseService": FakeDatabaseService,
                "load_data_snapshot": lambda target_date: calls.append(("snapshot", target_date)) or (None, None),
            },
        )

        self.assertEqual([item["date"] for item in result], ["2026-05-18", "2026-05-19"])
        self.assertEqual(result[-1]["sector_turnover"], 4050.0)
        self.assertEqual(calls, [("db", None), ("query", "2026-05-20", "半导体", 2)])

    def test_postgres_only_sector_turnover_history_returns_database_rows_without_snapshot_scan(self):
        runtime = self._load_module()
        calls = []

        class FakeService:
            def is_postgres_backed(self):
                return True

            def query_mainline_turnover_series(self, end_date, sector_name, *, window_days=25):
                calls.append(("query", end_date, sector_name, window_days))
                return [
                    {
                        "date": "2026-05-19",
                        "sector_name": "半导体",
                        "sector_turnover": 4050.0,
                        "total_turnover": 29764.59,
                        "turnover_share_pct": 13.61,
                        "matched_sector_names": ["半导体"],
                        "source": "postgresql.mainline_turnover_daily",
                    }
                ]

        class FakeDatabaseService:
            @classmethod
            def from_environment(cls, db_path=None):
                calls.append(("from_environment", db_path))
                return FakeService()

        def fail_snapshot_scan(target_date):
            raise AssertionError(f"postgres-only must not scan JSON snapshot {target_date}")

        def fail_index_rebuild(**kwargs):
            raise AssertionError("postgres-only must not rebuild history from JSON snapshots")

        result = runtime.load_recent_sector_turnover_history(
            "2026-05-20",
            "半导体",
            lookback_days=2,
            max_scan_days=60,
            helpers={
                "DatabaseService": FakeDatabaseService,
                "ensure_daily_metric_history_index": fail_index_rebuild,
                "load_data_snapshot": fail_snapshot_scan,
                "postgres_only_runtime": True,
            },
        )

        self.assertEqual([item["date"] for item in result], ["2026-05-19"])
        self.assertEqual(result[0]["sector_turnover"], 4050.0)
        self.assertEqual(calls, [("from_environment", None), ("query", "2026-05-20", "半导体", 2)])

    def test_postgres_only_sector_turnover_history_returns_empty_when_database_service_missing(self):
        runtime = self._load_module()

        def fail_snapshot_scan(target_date):
            raise AssertionError(f"postgres-only must not scan JSON snapshot {target_date}")

        result = runtime.load_recent_sector_turnover_history(
            "2026-05-20",
            "半导体",
            lookback_days=2,
            max_scan_days=60,
            helpers={
                "DatabaseService": None,
                "load_data_snapshot": fail_snapshot_scan,
                "postgres_only_runtime": True,
            },
        )

        self.assertEqual(result, [])

    def test_load_recent_sector_turnover_history_rebuilds_fact_db_when_index_is_stale(self):
        runtime = self._load_module()
        calls = []

        class FakeService:
            rebuilt = False

            def query_mainline_turnover_series(self, end_date, sector_name, *, window_days=25):
                calls.append(("query", end_date, sector_name, window_days, self.rebuilt))
                if not self.rebuilt:
                    return [
                        {
                            "date": "2026-05-11",
                            "sector_name": "半导体",
                            "sector_turnover": 3000.0,
                            "total_turnover": 35654.53,
                            "turnover_share_pct": 8.41,
                            "matched_sector_names": ["半导体"],
                        }
                    ]
                return [
                    {
                        "date": "2026-05-18",
                        "sector_name": "半导体",
                        "sector_turnover": 3900.0,
                        "total_turnover": 29170.74,
                        "turnover_share_pct": 13.37,
                        "matched_sector_names": ["半导体"],
                    },
                    {
                        "date": "2026-05-19",
                        "sector_name": "半导体",
                        "sector_turnover": 4050.0,
                        "total_turnover": 29764.59,
                        "turnover_share_pct": 13.61,
                        "matched_sector_names": ["半导体"],
                    },
                ]

        service = FakeService()

        class FakeDatabaseService:
            @classmethod
            def fact_store_from_environment(cls, db_path=None):
                calls.append(("db", db_path))
                return service

        def ensure_index(**kwargs):
            calls.append(("ensure", kwargs["end_date"], kwargs["window_days"], kwargs["max_scan_days"], kwargs.get("db_path")))
            service.rebuilt = True
            return {"indexed_count": 2}

        result = runtime.load_recent_sector_turnover_history(
            "2026-05-20",
            "半导体",
            lookback_days=2,
            max_scan_days=60,
            helpers={
                "DatabaseService": FakeDatabaseService,
                "ensure_daily_metric_history_index": ensure_index,
                "load_data_snapshot": lambda target_date: calls.append(("snapshot", target_date)) or (None, None),
            },
        )

        self.assertEqual([item["date"] for item in result], ["2026-05-18", "2026-05-19"])
        self.assertEqual(
            calls,
            [
                ("db", None),
                ("query", "2026-05-20", "半导体", 2, False),
                ("ensure", "2026-05-20", 2, 60, None),
                ("db", None),
                ("query", "2026-05-20", "半导体", 2, True),
            ],
        )

    def test_load_recent_sector_turnover_history_rebuilds_fact_db_when_index_is_short(self):
        runtime = self._load_module()
        calls = []

        class FakeService:
            rebuilt = False

            def query_mainline_turnover_series(self, end_date, sector_name, *, window_days=25):
                calls.append(("query", end_date, sector_name, window_days, self.rebuilt))
                if not self.rebuilt:
                    return [
                        {
                            "date": "2026-05-19",
                            "sector_name": "半导体",
                            "sector_turnover": 4050.0,
                            "total_turnover": 29764.59,
                            "turnover_share_pct": 13.61,
                            "matched_sector_names": ["半导体"],
                        }
                    ]
                return [
                    {
                        "date": "2026-05-18",
                        "sector_name": "半导体",
                        "sector_turnover": 3900.0,
                        "total_turnover": 29170.74,
                        "turnover_share_pct": 13.37,
                        "matched_sector_names": ["半导体"],
                    },
                    {
                        "date": "2026-05-19",
                        "sector_name": "半导体",
                        "sector_turnover": 4050.0,
                        "total_turnover": 29764.59,
                        "turnover_share_pct": 13.61,
                        "matched_sector_names": ["半导体"],
                    },
                ]

        service = FakeService()

        class FakeDatabaseService:
            @classmethod
            def fact_store_from_environment(cls, db_path=None):
                calls.append(("db", db_path))
                return service

        def ensure_index(**kwargs):
            calls.append(("ensure", kwargs["end_date"], kwargs["window_days"], kwargs["max_scan_days"], kwargs.get("db_path")))
            service.rebuilt = True
            return {"indexed_count": 2}

        result = runtime.load_recent_sector_turnover_history(
            "2026-05-20",
            "半导体",
            lookback_days=2,
            max_scan_days=60,
            helpers={
                "DatabaseService": FakeDatabaseService,
                "ensure_daily_metric_history_index": ensure_index,
                "load_data_snapshot": lambda target_date: calls.append(("snapshot", target_date)) or (None, None),
            },
        )

        self.assertEqual([item["date"] for item in result], ["2026-05-18", "2026-05-19"])
        self.assertEqual(
            calls,
            [
                ("db", None),
                ("query", "2026-05-20", "半导体", 2, False),
                ("ensure", "2026-05-20", 2, 60, None),
                ("db", None),
                ("query", "2026-05-20", "半导体", 2, True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
