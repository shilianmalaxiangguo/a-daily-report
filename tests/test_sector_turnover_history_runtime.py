import importlib
import sys
import unittest
from pathlib import Path

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

    def test_load_recent_sector_turnover_history_reads_nested_wrapped_snapshot_and_alias_match(self):
        runtime = self._load_module()

        result = runtime.load_recent_sector_turnover_history(
            "2026-04-24",
            "通信设备",
            lookback_days=1,
            helpers={
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


if __name__ == "__main__":
    unittest.main()
