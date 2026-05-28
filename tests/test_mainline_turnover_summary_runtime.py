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

    def _sector_attack_row(
        self,
        sector,
        *,
        rank,
        amount,
        limit_up,
        height,
        broad=70,
        strong=12,
        share_change=1.2,
    ):
        return {
            "sector_name": sector,
            "net_inflow_rank": rank,
            "net_inflow_amount": amount,
            "limit_up_count": limit_up,
            "high_anchor_height": height,
            "broad_rally_pct": broad,
            "strong_gain_count": strong,
            "turnover_share_change": share_change,
        }

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

    def test_build_mainline_turnover_summary_explains_tushare_moneyflow_amount_scope(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-19",
            current_mainline_history_record={"date": "2026-05-19", "primary_mainline": "半导体"},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={
                "date": "2026-05-19",
                "sector_name": "半导体",
                "sector_turnover": 3440.0,
                "total_turnover": 29089.77,
                "turnover_share_pct": 11.83,
                "source": "tushare.moneyflow_ind_ths",
                "source_query": "turnover_yi",
            },
            recent_sector_turnover_history=[],
        )

        row = result["turnover_share_trend_rows"][0]
        self.assertEqual(row["mainline_turnover"], "3440.00亿")
        self.assertIn("Tushare行业资金流入+流出", row["interpretation"])

    def test_build_mainline_turnover_summary_keeps_recent_25_turnover_share_rows_and_summary(self):
        runtime = self._load_module()
        recent_rows = [
            {
                "date": f"2026-04-{day:02d}",
                "sector_name": "半导体",
                "sector_turnover": 2000.0 + day,
                "total_turnover": 20000.0,
                "turnover_share_pct": 10.0 + index * 0.1,
            }
            for index, day in enumerate(range(1, 25))
        ]

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-20",
            current_mainline_history_record={"date": "2026-05-20", "primary_mainline": "半导体"},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={
                "date": "2026-05-20",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 29764.59,
                "turnover_share_pct": 13.61,
            },
            recent_sector_turnover_history=recent_rows,
        )

        rows = result["turnover_share_trend_rows"]
        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0]["date"], "2026-04-01")
        self.assertEqual(rows[-1]["date"], "2026-05-20")
        self.assertIn("近25个交易日主线成交额占比趋势", result["turnover_share_trend_summary"])
        self.assertIn("当前13.6%", result["turnover_share_trend_summary"])

    def test_build_mainline_turnover_summary_keeps_25_rows_when_some_turnover_is_missing(self):
        runtime = self._load_module()
        recent_rows = [
            {
                "date": f"2026-04-{day:02d}",
                "sector_name": "电力",
                "cycle_mainline": "电力",
                "daily_attack_line": "电力",
                "sector_turnover": 1000.0 + day if day % 5 else 0.0,
                "total_turnover": 20000.0 if day % 5 else 0.0,
                "turnover_share_pct": 5.0 if day % 5 else 0.0,
                "source_status": "history_missing" if day % 5 == 0 else "success",
            }
            for day in range(1, 25)
        ]

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-20",
            current_mainline_history_record={"date": "2026-05-20", "primary_mainline": "半导体"},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={
                "date": "2026-05-20",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 29764.59,
                "turnover_share_pct": 13.61,
            },
            recent_sector_turnover_history=recent_rows,
        )

        rows = result["turnover_share_trend_rows"]
        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[4]["mainline_turnover"], "数据暂缺")
        self.assertIn("近25个交易日主线成交额占比趋势", result["turnover_share_trend_summary"])

    def test_build_mainline_turnover_summary_keeps_daily_cycle_mainline_labels_in_trend_rows(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-20",
            current_mainline_history_record={"date": "2026-05-20", "primary_mainline": "半导体"},
            recent_mainline_history=[
                {"date": "2026-05-18", "primary_mainline": "电力"},
                {"date": "2026-05-19", "primary_mainline": "电力"},
            ],
            current_sector_turnover_snapshot={
                "date": "2026-05-20",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 29764.59,
                "turnover_share_pct": 13.61,
            },
            recent_sector_turnover_history=[
                {
                    "date": "2026-05-18",
                    "sector_name": "半导体",
                    "cycle_mainline": "电力",
                    "daily_attack_line": "电力",
                    "sector_turnover": 3442.0,
                    "total_turnover": 29170.74,
                    "turnover_share_pct": 11.8,
                },
                {
                    "date": "2026-05-19",
                    "sector_name": "半导体",
                    "cycle_mainline": "电力",
                    "daily_attack_line": "电力",
                    "sector_turnover": 3440.0,
                    "total_turnover": 29089.77,
                    "turnover_share_pct": 11.8,
                },
            ],
        )

        rows = result["turnover_share_trend_rows"]
        self.assertEqual(rows[0]["cycle_mainline"], "电力")
        self.assertEqual(rows[1]["cycle_mainline"], "电力")
        self.assertEqual(rows[-1]["cycle_mainline"], "半导体")

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
        self.assertIn("overtake_window_summary", result)

    def test_build_mainline_turnover_summary_maps_auto_parts_fund_flow_to_robot_narrative(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-21",
            current_mainline_history_record={"date": "2026-05-21", "primary_mainline": ""},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={},
            recent_sector_turnover_history=[],
            sector_attack_evidence_rows=[
                {
                    "sector_name": "汽车零部件",
                    "net_inflow_amount": 30.0,
                    "net_inflow_rank": 1,
                    "sector_turnover": 778.0,
                    "turnover_share_pct": 2.22,
                },
                {
                    "sector_name": "电机",
                    "net_inflow_amount": 9.0,
                    "net_inflow_rank": 3,
                    "sector_turnover": 102.0,
                    "turnover_share_pct": 0.29,
                },
                {
                    "sector_name": "生物制药",
                    "limit_up_count": 3,
                    "high_anchor_height": 7,
                },
            ],
        )

        summary = result["mainline_attack_evidence_summary"]
        self.assertEqual(summary["candidate_lines"][0], "人形机器人")
        robot_row = summary["sector_evidence_rows"][0]
        self.assertEqual(robot_row["sector_name"], "人形机器人")
        self.assertEqual(robot_row["surface_sector_names"], ["汽车零部件", "电机"])
        self.assertAlmostEqual(robot_row["net_inflow_amount"], 39.0)
        self.assertAlmostEqual(robot_row["sector_turnover"], 880.0)

    def test_build_mainline_turnover_summary_uses_realtime_tag_snapshot_adopted_branch(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-24",
            current_mainline_history_record={"date": "2026-05-24", "primary_mainline": ""},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={},
            recent_sector_turnover_history=[],
            realtime_tag_evidence_snapshot={
                "groups": [
                    {
                        "采用名称": "国产芯片替代",
                        "大方向": "泛半导体/硬科技电子",
                        "当日主攻分支": "国产芯片替代",
                        "表层行业名": ["元器件", "芯片", "半导体"],
                        "辅助名称": ["PCB"],
                        "关系判断": "父子",
                    }
                ],
                "adopted_labels": ["国产芯片替代"],
            },
            sector_attack_evidence_rows=[
                {
                    "sector_name": "元器件",
                    "net_inflow_amount": 38.0,
                    "net_inflow_rank": 1,
                    "limit_up_count": 7,
                    "high_anchor_height": 4,
                    "turnover_share_change": 1.2,
                    "concepts": ["PCB", "芯片"],
                }
            ],
        )

        self.assertEqual(result["current_mainline"], "国产芯片替代")
        summary = result["mainline_attack_evidence_summary"]
        self.assertEqual(summary["primary_line"], "国产芯片替代")
        self.assertEqual(summary["sector_evidence_rows"][0]["sector_name"], "国产芯片替代")
        self.assertIn("元器件", summary["sector_evidence_rows"][0]["surface_sector_names"])

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

    def test_build_mainline_turnover_summary_keeps_countertrend_attack_as_observation_not_mainline_switch(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-21",
            current_mainline_history_record={
                "date": "2026-05-21",
                "primary_mainline": "人形机器人",
                "leading_line": "人形机器人",
                "rotation_label": "逆势攻击",
                "rotation_summary": "当前逆势攻击；放量杀跌中只有人形机器人局部攻击",
            },
            recent_mainline_history=[{"date": "2026-05-20", "primary_mainline": "半导体"}],
            current_sector_turnover_snapshot={
                "date": "2026-05-21",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 35072.8,
                "turnover_share_pct": 13.3,
            },
            recent_sector_turnover_history=[
                {"date": "2026-05-20", "sector_name": "半导体", "total_turnover": 29764.59, "turnover_share_pct": 13.6}
            ],
            sector_attack_evidence_rows=[
                {
                    "sector_name": "人形机器人",
                    "net_inflow_amount": 39.0,
                    "net_inflow_rank": 1,
                    "limit_up_count": 5,
                    "sector_turnover": 880.0,
                    "turnover_share_pct": 2.51,
                }
            ],
        )

        self.assertEqual(result["current_mainline"], "人形机器人")
        self.assertEqual(result["share_trend_label"], "逆势试攻")
        self.assertIn("观察主攻线", result["conclusion"])
        self.assertNotIn("主线切换为人形机器人", result["conclusion"])
        self.assertEqual(result["double_mainline_summary"]["cycle_mainline"], "半导体")
        self.assertEqual(result["double_mainline_summary"]["daily_attack_line"], "人形机器人")
        self.assertIn("不按周期主线处理", result["double_mainline_summary"]["relationship"])
        self.assertEqual(result["mainline_capacity_regime_summary"]["mainline_process"], "逆势试攻")
        self.assertEqual(result["turnover_share_trend_rows"][-1]["cycle_mainline"], "人形机器人")
        self.assertEqual(result["turnover_share_trend_rows"][-1]["daily_attack_line"], "人形机器人")

    def test_turnover_share_summary_uses_recent_drop_over_window_low_base(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-21",
            current_mainline_history_record={
                "date": "2026-05-21",
                "primary_mainline": "人形机器人",
                "rotation_label": "逆势攻击",
                "rotation_summary": "放量杀跌中只有人形机器人局部攻击",
            },
            recent_mainline_history=[{"date": "2026-05-20", "primary_mainline": "半导体"}],
            current_sector_turnover_snapshot={
                "date": "2026-05-21",
                "sector_name": "人形机器人",
                "sector_turnover": 880.0,
                "total_turnover": 35072.8,
                "turnover_share_pct": 2.5,
            },
            recent_sector_turnover_history=[
                {"date": "2026-04-16", "sector_name": "证券", "turnover_share_pct": 0.8},
                {"date": "2026-05-15", "sector_name": "半导体", "turnover_share_pct": 12.1},
                {"date": "2026-05-18", "sector_name": "电力", "turnover_share_pct": 1.7},
                {"date": "2026-05-19", "sector_name": "电力", "turnover_share_pct": 2.3},
                {"date": "2026-05-20", "sector_name": "半导体", "turnover_share_pct": 13.6},
            ],
            sector_attack_evidence_rows=[
                {
                    "sector_name": "人形机器人",
                    "net_inflow_amount": 39.0,
                    "net_inflow_rank": 1,
                    "limit_up_count": 5,
                    "sector_turnover": 880.0,
                    "turnover_share_pct": 2.5,
                }
            ],
        )

        summary = result["turnover_share_trend_summary"]
        self.assertIn("近5日-9.6pct", summary)
        self.assertIn("主线成交占比回落", summary)
        self.assertNotIn("资金聚焦度走强", summary)

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

    def test_overtake_window_opens_when_rivals_slow_and_primary_holds(self):
        runtime = self._load_module()
        attack = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                self._sector_attack_row("半导体", rank=1, amount=45, limit_up=8, height=4),
                self._sector_attack_row(
                    "机器人",
                    rank=8,
                    amount=-6,
                    limit_up=1,
                    height=1,
                    broad=35,
                    strong=2,
                    share_change=-1.4,
                ),
            ]
        )

        result = runtime.build_overtake_window_summary(
            mainline_attack_evidence_summary=attack,
            mainline_capacity_regime_summary={"primary_line": "半导体", "mainline_regime": "单主线聚焦"},
            current_mainline_history_record={"primary_mainline": "半导体", "secondary_mainline": "机器人"},
        )

        self.assertEqual(result["window_state"], "open")
        self.assertEqual(result["speed_gap"], "失速差拉开")
        self.assertEqual(result["action"], "只在半导体核心里找参与资格")

    def test_overtake_window_waits_when_old_line_has_not_retreated(self):
        runtime = self._load_module()
        attack = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                self._sector_attack_row("半导体", rank=1, amount=45, limit_up=8, height=4),
                self._sector_attack_row(
                    "机器人",
                    rank=2,
                    amount=28,
                    limit_up=5,
                    height=3,
                    broad=68,
                    strong=10,
                    share_change=0.8,
                ),
            ]
        )

        result = runtime.build_overtake_window_summary(
            mainline_attack_evidence_summary=attack,
            mainline_capacity_regime_summary={"primary_line": "半导体", "mainline_regime": "双主线竞争"},
            current_mainline_history_record={"primary_mainline": "半导体", "secondary_mainline": "机器人"},
        )

        self.assertEqual(result["window_state"], "confirm_next")
        self.assertEqual(result["speed_gap"], "未拉开")
        self.assertEqual(result["action"], "等竞价、开盘承接、回封或09:50-10:10窗口")

    def test_overtake_window_observes_chaotic_rotation(self):
        runtime = self._load_module()
        attack = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                self._sector_attack_row(
                    "半导体",
                    rank=4,
                    amount=12,
                    limit_up=2,
                    height=1,
                    broad=45,
                    strong=4,
                    share_change=0.2,
                ),
                self._sector_attack_row(
                    "机器人",
                    rank=5,
                    amount=10,
                    limit_up=2,
                    height=1,
                    broad=42,
                    strong=4,
                    share_change=0.1,
                ),
                self._sector_attack_row(
                    "消费电子",
                    rank=6,
                    amount=9,
                    limit_up=1,
                    height=2,
                    broad=40,
                    strong=3,
                    share_change=0.0,
                ),
            ]
        )

        result = runtime.build_overtake_window_summary(mainline_attack_evidence_summary=attack)

        self.assertEqual(result["window_state"], "observe")
        self.assertEqual(result["action"], "仅观察，不给新增参与资格")

    def test_overtake_window_stands_down_when_everyone_slows(self):
        runtime = self._load_module()
        attack = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                self._sector_attack_row(
                    "半导体",
                    rank=9,
                    amount=-4,
                    limit_up=0,
                    height=1,
                    broad=20,
                    strong=1,
                    share_change=-1.2,
                ),
                self._sector_attack_row(
                    "机器人",
                    rank=10,
                    amount=-6,
                    limit_up=0,
                    height=1,
                    broad=18,
                    strong=1,
                    share_change=-1.5,
                ),
            ]
        )

        result = runtime.build_overtake_window_summary(
            mainline_attack_evidence_summary=attack,
            current_mainline_history_record={"primary_mainline": "半导体", "secondary_mainline": "机器人"},
        )

        self.assertEqual(result["window_state"], "no_trade")
        self.assertEqual(result["action"], "不参与，先防风险")

    def test_trading_arena_fit_marks_short_term_expansion_as_home_arena(self):
        runtime = self._load_module()
        overtake = {
            "window_state": "open",
            "primary_line": "半导体",
            "action": "只在半导体核心里找参与资格",
        }

        result = runtime.build_trading_arena_fit_summary(
            mainline_capacity_regime_summary={"mainline_regime": "单主线聚焦", "mainline_capacity": "单线容量"},
            overtake_window_summary=overtake,
        )

        self.assertEqual(result["fit_state"], "home_arena")
        self.assertEqual(result["arena_label"], "短线/超短线主战场")
        self.assertEqual(result["action"], "按短线/超短线主战场处理，围绕半导体核心继续寻找参与资格")

    def test_trading_arena_fit_keeps_non_home_arena_from_expanding_methods(self):
        runtime = self._load_module()

        result = runtime.build_trading_arena_fit_summary(
            mainline_capacity_regime_summary={
                "mainline_regime": "趋势容量",
                "mainline_capacity": "牛市多线容量",
                "primary_line": "大金融",
            },
            overtake_window_summary={"window_state": "confirm_next", "primary_line": "大金融"},
        )

        self.assertEqual(result["fit_state"], "low_fit")
        self.assertEqual(result["arena_label"], "非主战场")
        self.assertEqual(result["action"], "不扩战法，不为证明全能而新增参与，只保持不拖后腿")

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
