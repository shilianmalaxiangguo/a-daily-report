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

    def test_build_mainline_turnover_summary_exports_capacity_regime_summary(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-14",
            current_mainline_history_record={
                "date": "2026-05-14",
                "primary_mainline": "半导体",
                "secondary_mainline": "电力",
                "competition_mainline": "化学制品",
                "sector_relationship_state": "混沌接力",
                "mainline_process": "启动",
                "mainline_confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
            },
            recent_mainline_history=[
                {"date": "2026-05-12", "primary_mainline": "电力"},
                {"date": "2026-05-13", "primary_mainline": "电力"},
            ],
            current_sector_turnover_snapshot={
                "date": "2026-05-14",
                "sector_name": "半导体",
                "sector_turnover": 4206.70,
                "total_turnover": 33880.86,
                "turnover_share_pct": 12.4,
            },
            recent_sector_turnover_history=[
                {"date": "2026-05-12", "sector_name": "电力", "total_turnover": 26000.00, "turnover_share_pct": 10.2},
                {"date": "2026-05-13", "sector_name": "电力", "total_turnover": 30000.00, "turnover_share_pct": 11.8},
            ],
        )

        summary = result["mainline_capacity_regime_summary"]
        self.assertEqual(summary["mainline_capacity"], "双线孕育")
        self.assertEqual(summary["mainline_regime"], "混沌接力")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["other_lines"], "电力 / 化学制品")
        self.assertEqual(summary["confirmation_evidence"], "半导体高标和涨停更集中，成交占比靠前")
        self.assertEqual(summary["sector_relationship_state"], "混沌接力")
        self.assertEqual(summary["mainline_process"], "启动")
        self.assertIn("今日33880.86亿", summary["capacity_evidence"])
        self.assertIn("昨日30000.00亿", summary["capacity_evidence"])
        self.assertIn("近25日中位数30000.00亿", summary["capacity_evidence"])

    def test_build_mainline_turnover_summary_can_keep_no_mainline_when_capacity_is_low(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-14",
            current_mainline_history_record={"date": "2026-05-14", "primary_mainline": ""},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={
                "date": "2026-05-14",
                "sector_name": "",
                "total_turnover": 7800.00,
                "turnover_share_pct": 0.0,
            },
            recent_sector_turnover_history=[
                {"date": "2026-05-13", "sector_name": "机器人", "total_turnover": 9200.00, "turnover_share_pct": 4.2},
                {"date": "2026-05-12", "sector_name": "军工", "total_turnover": 9500.00, "turnover_share_pct": 4.1},
            ],
        )

        summary = result["mainline_capacity_regime_summary"]
        self.assertEqual(summary["mainline_capacity"], "低容量")
        self.assertEqual(summary["mainline_regime"], "无主线")
        self.assertEqual(summary["primary_line"], "暂无")
        self.assertEqual(summary["tomorrow_action"], "不强行找主线，只保留异常观察")

    def test_build_mainline_turnover_summary_does_not_promote_three_hotspots_to_multi_line_without_bull_market(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-14",
            current_mainline_history_record={
                "date": "2026-05-14",
                "primary_mainline": "半导体",
                "secondary_mainline": "电力",
                "competition_mainline": "化学制品",
                "market_regime": "震荡",
            },
            recent_mainline_history=[{"date": "2026-05-13", "primary_mainline": "电力"}],
            current_sector_turnover_snapshot={
                "date": "2026-05-14",
                "sector_name": "半导体",
                "total_turnover": 33880.86,
                "turnover_share_pct": 12.4,
            },
            recent_sector_turnover_history=[
                {"date": "2026-05-13", "sector_name": "电力", "total_turnover": 30000.00, "turnover_share_pct": 11.8},
                {"date": "2026-05-12", "sector_name": "化学制品", "total_turnover": 29500.00, "turnover_share_pct": 9.6},
            ],
        )

        summary = result["mainline_capacity_regime_summary"]
        self.assertNotEqual(summary["mainline_regime"], "多主线牛市")
        self.assertEqual(summary["mainline_regime"], "混沌接力")

    def test_build_mainline_turnover_summary_uses_attack_evidence_for_confirmation(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-15",
            current_mainline_history_record={"date": "2026-05-15", "primary_mainline": "电力"},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={
                "date": "2026-05-15",
                "sector_name": "半导体",
                "total_turnover": 30000.0,
                "turnover_share_pct": 12.4,
            },
            recent_sector_turnover_history=[],
            sector_attack_evidence_rows=[
                {
                    "sector_name": "半导体",
                    "net_inflow_amount": 45.0,
                    "net_inflow_rank": 1,
                    "limit_up_count": 8,
                    "high_anchor_height": 4,
                    "turnover_share_change": 1.3,
                }
            ],
        )

        self.assertEqual(result["mainline_attack_evidence_summary"]["attack_state"], "confirmed_attack")
        self.assertEqual(result["mainline_capacity_regime_summary"]["primary_line"], "半导体")
        self.assertEqual(
            result["mainline_capacity_regime_summary"]["confirmation_evidence"],
            "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
        )

    def test_build_mainline_turnover_summary_uses_confirmed_attack_line_as_current_mainline(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-15",
            current_mainline_history_record={"date": "2026-05-15", "primary_mainline": "电力"},
            recent_mainline_history=[{"date": "2026-05-14", "primary_mainline": "电力"}],
            current_sector_turnover_snapshot={
                "date": "2026-05-15",
                "sector_name": "半导体",
                "total_turnover": 33880.86,
                "turnover_share_pct": 12.4,
            },
            recent_sector_turnover_history=[
                {"date": "2026-05-14", "sector_name": "电力", "total_turnover": 30000.0, "turnover_share_pct": 11.8}
            ],
            sector_attack_evidence_rows=[
                {
                    "sector_name": "半导体",
                    "net_inflow_amount": 45.0,
                    "net_inflow_rank": 1,
                    "limit_up_count": 8,
                    "high_anchor_height": 4,
                    "turnover_share_change": 1.3,
                }
            ],
        )

        self.assertEqual(result["current_mainline"], "半导体")
        self.assertEqual(result["previous_mainline"], "电力")
        self.assertEqual(result["conclusion"], "主线切换为半导体，旧主线电力退出中心")
        self.assertEqual(result["double_mainline_summary"]["cycle_mainline"], "半导体")
        self.assertEqual(result["turnover_share_trend_rows"][-1]["cycle_mainline"], "半导体")

    def test_build_mainline_turnover_summary_aligns_turnover_row_to_confirmed_attack_line(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-15",
            current_mainline_history_record={"date": "2026-05-15", "primary_mainline": "电力"},
            recent_mainline_history=[{"date": "2026-05-14", "primary_mainline": "电力"}],
            current_sector_turnover_snapshot={
                "date": "2026-05-15",
                "sector_name": "电力",
                "sector_turnover": 2300.0,
                "total_turnover": 33880.86,
                "turnover_share_pct": 6.79,
            },
            recent_sector_turnover_history=[
                {"date": "2026-05-14", "sector_name": "电力", "total_turnover": 30000.0, "turnover_share_pct": 11.8}
            ],
            sector_attack_evidence_rows=[
                {
                    "sector_name": "半导体",
                    "net_inflow_amount": 45.0,
                    "net_inflow_rank": 1,
                    "limit_up_count": 8,
                    "high_anchor_height": 4,
                    "sector_turnover": 4206.7,
                    "turnover_share_pct": 12.42,
                    "turnover_share_change": 1.3,
                }
            ],
        )

        row = result["turnover_share_trend_rows"][-1]
        self.assertEqual(row["cycle_mainline"], "半导体")
        self.assertEqual(row["daily_attack_line"], "半导体")
        self.assertEqual(row["share"], "12.4%")
        self.assertEqual(row["mainline_turnover"], "4206.70亿")

    def test_build_mainline_turnover_summary_does_not_confirm_primary_mainline_without_attack_evidence(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-15",
            current_mainline_history_record={"date": "2026-05-15", "primary_mainline": "半导体"},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={
                "date": "2026-05-15",
                "sector_name": "半导体",
                "total_turnover": 26000.0,
            },
            recent_sector_turnover_history=[],
            sector_attack_evidence_rows=[
                {"sector_name": "半导体", "net_inflow_amount": 2.0, "net_inflow_rank": 20, "limit_up_count": 0}
            ],
        )

        self.assertEqual(result["mainline_attack_evidence_summary"]["attack_state"], "no_attack")
        self.assertEqual(result["mainline_capacity_regime_summary"]["mainline_regime"], "无主线")
        self.assertEqual(result["mainline_capacity_regime_summary"]["primary_line"], "暂无")
        self.assertEqual(result["mainline_capacity_regime_summary"]["confirmation_evidence"], "资金未形成明确进攻方向")

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
