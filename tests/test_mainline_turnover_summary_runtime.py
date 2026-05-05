import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class MainlineTurnoverSummaryRuntimeTest(unittest.TestCase):
    def _load_module(self):
        try:
            return importlib.import_module("domains.market_state.mainline_turnover_summary_runtime")
        except ModuleNotFoundError as error:
            self.fail(f"domains.market_state.mainline_turnover_summary_runtime should exist: {error}")

    def test_build_mainline_turnover_summary_reports_unchanged_mainline_and_strengthening_share(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-04-24",
            current_mainline_history_record={
                "date": "2026-04-24",
                "primary_mainline": "通信",
                "secondary_mainline": "机器人",
                "competition_mainline": "军工",
                "rotation_label": "爆发",
            },
            recent_mainline_history=[
                {"date": "2026-04-22", "primary_mainline": "通信"},
                {"date": "2026-04-23", "primary_mainline": "通信"},
            ],
            current_sector_turnover_snapshot={
                "date": "2026-04-24",
                "sector_name": "通信",
                "turnover_share_pct": 18.1,
            },
            recent_sector_turnover_history=[
                {"date": "2026-04-22", "sector_name": "通信", "turnover_share_pct": 12.4},
                {"date": "2026-04-23", "sector_name": "通信", "turnover_share_pct": 15.8},
            ],
        )

        self.assertEqual(result["conclusion"], "主线未切换，通信仍是中心")
        self.assertEqual(
            result["data_text"],
            "最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%，节奏偏强化",
        )
        self.assertEqual(result["action_text"], "继续围绕通信做减法，不追支线分流")
        self.assertEqual(result["current_mainline"], "通信")
        self.assertEqual(result["share_trend_label"], "强化")

    def test_build_mainline_turnover_summary_reports_mainline_switch_and_share_reset(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-04-24",
            current_mainline_history_record={
                "date": "2026-04-24",
                "primary_mainline": "通信",
                "secondary_mainline": "军工",
                "competition_mainline": "机器人",
                "rotation_label": "再聚焦",
            },
            recent_mainline_history=[
                {"date": "2026-04-22", "primary_mainline": "军工"},
                {"date": "2026-04-23", "primary_mainline": "军工"},
            ],
            current_sector_turnover_snapshot={
                "date": "2026-04-24",
                "sector_name": "通信",
                "turnover_share_pct": 9.6,
            },
            recent_sector_turnover_history=[
                {"date": "2026-04-22", "sector_name": "军工", "turnover_share_pct": 14.2},
                {"date": "2026-04-23", "sector_name": "军工", "turnover_share_pct": 13.4},
            ],
        )

        self.assertEqual(result["conclusion"], "主线切换为通信，旧主线军工退出中心")
        self.assertEqual(
            result["data_text"],
            "最近3日主线 军工 -> 军工 -> 通信；成交额占比 14.2% -> 13.4% -> 9.6%，节奏偏切换",
        )
        self.assertEqual(result["action_text"], "只围绕新主线通信重新收缩，不对旧主线做回流预判")
        self.assertEqual(result["previous_mainline"], "军工")
        self.assertEqual(result["share_trend_label"], "切换")
        self.assertEqual(result["turnover_share_trend_rows"][-1]["share_change"], "-3.8pct")

    def test_build_mainline_turnover_summary_keeps_previous_mainline_row_labeled_as_itself(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-04-24",
            current_mainline_history_record={"date": "2026-04-24", "primary_mainline": "半导体"},
            recent_mainline_history=[
                {"date": "2026-04-22", "primary_mainline": "电力"},
                {"date": "2026-04-23", "primary_mainline": "半导体"},
            ],
            current_sector_turnover_snapshot={
                "date": "2026-04-24",
                "sector_name": "半导体",
                "sector_turnover": 2638.1,
                "total_turnover": 26414.92,
                "turnover_share_pct": 10.0,
            },
            recent_sector_turnover_history=[
                {
                    "date": "2026-04-22",
                    "sector_name": "电力",
                    "sector_turnover": 2100.0,
                    "total_turnover": 12000.0,
                    "turnover_share_pct": 17.5,
                },
                {
                    "date": "2026-04-23",
                    "sector_name": "半导体",
                    "sector_turnover": 2300.0,
                    "total_turnover": 12500.0,
                    "turnover_share_pct": 18.4,
                },
            ],
        )

        rows = result["turnover_share_trend_rows"]
        self.assertEqual(rows[0]["cycle_mainline"], "电力")
        self.assertEqual(rows[0]["daily_attack_line"], "电力")
        self.assertEqual(rows[-1]["cycle_mainline"], "半导体")
        self.assertEqual(rows[-1]["daily_attack_line"], "半导体")

    def test_build_mainline_turnover_summary_exports_turnover_share_table_rows_even_when_share_missing(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-04-24",
            current_mainline_history_record={"date": "2026-04-24", "primary_mainline": "半导体"},
            recent_mainline_history=[
                {"date": "2026-04-22", "primary_mainline": "电力"},
                {"date": "2026-04-23", "primary_mainline": "半导体"},
            ],
            current_sector_turnover_snapshot={
                "date": "2026-04-24",
                "sector_name": "半导体",
                "sector_turnover": 0.0,
                "total_turnover": 26414.92,
                "turnover_share_pct": 0.0,
                "source_status": "missing_dependency",
            },
            recent_sector_turnover_history=[],
        )

        self.assertEqual(result["double_mainline_summary"]["cycle_mainline"], "半导体")
        self.assertEqual(result["double_mainline_summary"]["daily_attack_line"], "半导体")
        self.assertEqual(result["turnover_share_trend_rows"][0]["date"], "2026-04-24")
        self.assertEqual(result["turnover_share_trend_rows"][0]["cycle_mainline"], "半导体")
        self.assertEqual(result["turnover_share_trend_rows"][0]["mainline_turnover"], "数据暂缺")
        self.assertEqual(result["turnover_share_trend_rows"][0]["market_turnover"], "26414.92亿")
        self.assertEqual(result["turnover_share_trend_rows"][0]["share"], "待累计")
        self.assertIn("缺少板块成交额接口", result["turnover_share_trend_rows"][0]["interpretation"])

    def test_should_rebuild_mainline_turnover_summary_when_existing_summary_misses_switch(self):
        runtime = self._load_module()

        should_rebuild = runtime.should_rebuild_mainline_turnover_summary(
            {
                "current_mainline": "半导体",
                "conclusion": "主线未切换，半导体仍是中心",
                "share_trend_label": "持平",
            },
            current_mainline_history_record={"date": "2026-04-30", "primary_mainline": "半导体"},
            recent_mainline_history=[
                {"date": "2026-04-28", "primary_mainline": "电力"},
                {"date": "2026-04-29", "primary_mainline": "电池"},
            ],
        )

        self.assertTrue(should_rebuild)

    def test_should_keep_mainline_turnover_summary_when_existing_summary_has_switch(self):
        runtime = self._load_module()

        should_rebuild = runtime.should_rebuild_mainline_turnover_summary(
            {
                "current_mainline": "半导体",
                "previous_mainline": "电池",
                "conclusion": "主线切换为半导体，旧主线电池退出中心",
                "share_trend_label": "切换",
            },
            current_mainline_history_record={"date": "2026-04-30", "primary_mainline": "半导体"},
            recent_mainline_history=[
                {"date": "2026-04-28", "primary_mainline": "电力"},
                {"date": "2026-04-29", "primary_mainline": "电池"},
            ],
        )

        self.assertFalse(should_rebuild)


if __name__ == "__main__":
    unittest.main()
