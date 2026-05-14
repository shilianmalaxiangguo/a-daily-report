import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class MainlineHistoryRuntimeTest(unittest.TestCase):
    def _load_module(self):
        try:
            return importlib.import_module("domains.market_state.mainline_history_runtime")
        except ModuleNotFoundError as error:
            self.fail(f"domains.market_state.mainline_history_runtime should exist: {error}")

    def test_build_mainline_history_record_prefers_state_machine_and_competition_roles(self):
        runtime = self._load_module()

        result = runtime.build_mainline_history_record(
            "2026-04-24",
            {
                "state_machine": {"leading_line": "军工", "state_code": "expand"},
                "mainline_rotation_snapshot": {"rotation_label": "爆发", "summary_text": "军工继续聚焦"},
                "observation": {
                    "mainline_competition_snapshot": [
                        {"role": "主攻线", "sector": "军工"},
                        {"role": "次强线", "sector": "机器人"},
                        {"role": "竞争线", "sector": "通信"},
                    ]
                },
            },
        )

        self.assertEqual(result["date"], "2026-04-24")
        self.assertEqual(result["primary_mainline"], "军工")
        self.assertEqual(result["secondary_mainline"], "机器人")
        self.assertEqual(result["competition_mainline"], "通信")
        self.assertEqual(result["rotation_label"], "爆发")
        self.assertEqual(result["leading_line"], "军工")
        self.assertEqual(result["state_code"], "expand")
        self.assertEqual(result["rotation_summary"], "军工继续聚焦")
        self.assertEqual(result["source"], "market_research_snapshot")

    def test_build_mainline_history_record_falls_back_to_observation_candidates(self):
        runtime = self._load_module()

        result = runtime.build_mainline_history_record(
            "2026-04-24",
            {
                "state_machine": {},
                "mainline_rotation_snapshot": {},
                "observation": {
                    "mainline_candidates": ["半导体"],
                    "secondary_candidates": ["消费电子"],
                },
            },
        )

        self.assertEqual(result["primary_mainline"], "半导体")
        self.assertEqual(result["secondary_mainline"], "消费电子")
        self.assertEqual(result["competition_mainline"], "")
        self.assertEqual(result["rotation_label"], "")
        self.assertEqual(result["leading_line"], "")

    def test_load_recent_mainline_history_reads_direct_record_contract(self):
        runtime = self._load_module()

        snapshots = {
            "2026-04-23": (
                {
                    "mainline_history_record": {
                        "date": "2026-04-23",
                        "primary_mainline": "通信",
                        "secondary_mainline": "机器人",
                        "competition_mainline": "军工",
                        "rotation_label": "爆发",
                        "leading_line": "通信",
                        "state_code": "expand",
                        "rotation_summary": "通信继续聚焦",
                        "source": "legacy.snapshot",
                    }
                },
                "",
            ),
            "2026-04-22": (
                {
                    "mainline_history_record": {
                        "date": "2026-04-22",
                        "primary_mainline": "军工",
                        "secondary_mainline": "商业航天",
                        "competition_mainline": "",
                        "rotation_label": "分化整理",
                        "leading_line": "军工",
                        "state_code": "migrate",
                        "rotation_summary": "军工高位分化",
                        "source": "legacy.snapshot",
                    }
                },
                "",
            ),
        }

        result = runtime.load_recent_mainline_history(
            "2026-04-24",
            lookback_days=2,
            helpers={
                "load_data_snapshot": lambda target_date: snapshots.get(target_date, (None, None)),
                "get_previous_date_str": lambda value: {
                    "2026-04-24": "2026-04-23",
                    "2026-04-23": "2026-04-22",
                    "2026-04-22": "2026-04-21",
                }.get(value),
                "_normalize_kline_date_str": lambda value: value,
            },
        )

        self.assertEqual(
            result,
            [
                {
                    "date": "2026-04-22",
                    "primary_mainline": "军工",
                    "secondary_mainline": "商业航天",
                    "competition_mainline": "",
                    "rotation_label": "分化整理",
                    "leading_line": "军工",
                    "state_code": "migrate",
                    "rotation_summary": "军工高位分化",
                    "source": "legacy.snapshot",
                },
                {
                    "date": "2026-04-23",
                    "primary_mainline": "通信",
                    "secondary_mainline": "机器人",
                    "competition_mainline": "军工",
                    "rotation_label": "爆发",
                    "leading_line": "通信",
                    "state_code": "expand",
                    "rotation_summary": "通信继续聚焦",
                    "source": "legacy.snapshot",
                },
            ],
        )

    def test_load_recent_mainline_history_reads_nested_analysis_record(self):
        runtime = self._load_module()

        snapshots = {
            "2026-04-23": (
                {
                    "analysis": {
                        "mainline_history_record": {
                            "date": "2026-04-23",
                            "primary_mainline": "通信",
                            "secondary_mainline": "机器人",
                            "competition_mainline": "",
                            "rotation_label": "爆发",
                            "leading_line": "通信",
                            "state_code": "expand",
                            "rotation_summary": "通信继续聚焦",
                            "source": "persist.snapshot",
                        }
                    }
                },
                "",
            ),
            "2026-04-22": (
                {
                    "persist": {
                        "snapshot": {
                            "analysis": {
                                "mainline_history_record": {
                                    "date": "2026-04-22",
                                    "primary_mainline": "军工",
                                    "secondary_mainline": "",
                                    "competition_mainline": "商业航天",
                                    "rotation_label": "再聚焦",
                                    "leading_line": "军工",
                                    "state_code": "probe",
                                    "rotation_summary": "军工重新聚焦",
                                    "source": "persist.snapshot",
                                }
                            }
                        }
                    }
                },
                "",
            ),
        }

        result = runtime.load_recent_mainline_history(
            "2026-04-24",
            lookback_days=2,
            helpers={
                "load_data_snapshot": lambda target_date: snapshots.get(target_date, (None, None)),
                "get_previous_date_str": lambda value: {
                    "2026-04-24": "2026-04-23",
                    "2026-04-23": "2026-04-22",
                    "2026-04-22": "2026-04-21",
                }.get(value),
                "_normalize_kline_date_str": lambda value: value,
            },
        )

        self.assertEqual([item["primary_mainline"] for item in result], ["军工", "通信"])
        self.assertEqual(result[0]["competition_mainline"], "商业航天")
        self.assertEqual(result[1]["source"], "persist.snapshot")

    def test_extract_mainline_history_record_reads_current_record_contract(self):
        runtime = self._load_module()

        result = runtime.extract_mainline_history_record(
            {
                "recent_mainline_history": [
                    {"date": "2026-05-12", "primary_mainline": "电力", "source": "snapshot.history"}
                ],
                "current_mainline_history_record": {
                    "date": "2026-05-13",
                    "primary_mainline": "半导体",
                    "secondary_mainline": "电力",
                    "leading_line": "半导体",
                    "source": "market_research_snapshot",
                },
            }
        )

        self.assertEqual(result["date"], "2026-05-13")
        self.assertEqual(result["primary_mainline"], "半导体")
        self.assertEqual(result["secondary_mainline"], "电力")

    def test_load_recent_mainline_history_reuses_snapshot_recent_history_window(self):
        runtime = self._load_module()

        snapshots = {
            "2026-05-13": (
                {
                    "current_mainline_history_record": {
                        "date": "2026-05-13",
                        "primary_mainline": "半导体",
                        "leading_line": "半导体",
                        "source": "market_research_snapshot",
                    }
                },
                "",
            ),
            "2026-05-12": (
                {
                    "recent_mainline_history": [
                        {"date": "2026-05-08", "primary_mainline": "机器人", "source": "snapshot.history"},
                        {"date": "2026-05-11", "primary_mainline": "电力", "source": "snapshot.history"},
                    ],
                    "current_mainline_history_record": {
                        "date": "2026-05-12",
                        "primary_mainline": "电力",
                        "leading_line": "电力",
                        "source": "market_research_snapshot",
                    },
                },
                "",
            ),
        }

        result = runtime.load_recent_mainline_history(
            "2026-05-14",
            lookback_days=4,
            max_scan_days=4,
            helpers={
                "load_data_snapshot": lambda target_date: snapshots.get(target_date, (None, None)),
                "get_previous_date_str": lambda value: {
                    "2026-05-14": "2026-05-13",
                    "2026-05-13": "2026-05-12",
                    "2026-05-12": "2026-05-11",
                    "2026-05-11": "2026-05-08",
                    "2026-05-08": "2026-05-07",
                }.get(value),
                "_normalize_kline_date_str": lambda value: value,
            },
        )

        self.assertEqual([item["date"] for item in result], ["2026-05-08", "2026-05-11", "2026-05-12", "2026-05-13"])
        self.assertEqual([item["primary_mainline"] for item in result], ["机器人", "电力", "电力", "半导体"])


if __name__ == "__main__":
    unittest.main()
