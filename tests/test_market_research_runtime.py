import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research.market_research_runtime import (
    _build_sector_attack_evidence_rows,
    build_market_research_snapshot_contract,
    derive_step0_follow_plan_contract,
)
from report.market_research_snapshot_nodes import derive_market_research_cycle_layer


class MarketResearchRuntimeTest(unittest.TestCase):
    def _minimal_snapshot_kwargs(self, leading_line="半导体"):
        return {
            "final_gate": {"can_new_entry": True},
            "position_level": "50%条件执行",
            "exit_analysis": {"overall_level": "黄灯"},
            "observation_snapshot": {
                "abnormal_watch_pool": [{"code": "000001"}],
                "main_sectors_info": [{"name": leading_line}],
                "secondary_sectors_info": [{"name": "电力"}],
                "sector_trend_snapshot": [{"sector": leading_line}],
            },
            "target_date": "2026-04-24",
            "build_abnormal_projection_summary": lambda pool: {"projection_label": "承接强化"},
            "build_market_style_switch_snapshot": lambda target_date, data, observation_snapshot, abnormal_projection: {"style_label": "主线抱团"},
            "build_market_state_machine_snapshot": lambda *args, **kwargs: {"leading_line": leading_line, "state_code": "probe", "energy_state": "试探修复"},
            "build_mainline_rotation_snapshot": lambda **kwargs: {"summary_text": f"{leading_line}尝试接力"},
            "build_abnormal_probe_group": lambda **kwargs: {"probe_group_label": "先看异常"},
            "build_special_probe_verdict": lambda **kwargs: {"summary_text": "先看异常承接", "action": f"看{leading_line}异常股"},
            "build_follow_verdict": lambda *args, **kwargs: {"label": "🟡 条件跟随", "reason": "修复未稳", "action": f"只看{leading_line}"},
            "build_dialectical_decision_snapshot": lambda **kwargs: {"stage_label": "试探修复", "stage_action": "先等确认"},
        }

    def test_derive_market_research_cycle_layer_builds_cycle_rows(self):
        result = derive_market_research_cycle_layer(
            {
                "recent_mainline_history": [
                    {"date": "2026-04-14", "primary_mainline": "电力", "market_state": "主导"},
                    {"date": "2026-04-15", "primary_mainline": "电力", "market_state": "强化"},
                    {"date": "2026-04-16", "primary_mainline": "电力", "market_state": "分化"},
                    {"date": "2026-04-17", "primary_mainline": "电力", "market_state": "退潮"},
                    {"date": "2026-04-21", "primary_mainline": "半导体", "market_state": "接力"},
                    {"date": "2026-04-22", "primary_mainline": "半导体", "market_state": "修复"},
                    {"date": "2026-04-23", "primary_mainline": "半导体", "market_state": "回流"},
                ],
                "current_mainline_history_record": {"date": "2026-04-24", "primary_mainline": "半导体", "market_state": "试探修复"},
                "pivot_mainline_history": [
                    {
                        "date_range": "04-14 ~ 04-18",
                        "pivot_level": "大中枢",
                        "pivot_range": "3992.41 - 4114.84",
                        "position": "中枢上沿",
                        "structure_state": "上沿承压",
                        "mainline": "电力",
                        "mainline_degree": "大主线",
                        "evolution": "高位分化",
                        "replacement": "中枢震荡",
                    }
                ],
            },
            state_machine={"leading_line": "半导体", "energy_state": "试探修复"},
        )

        self.assertIn("cycle_calendar_rows", result)
        self.assertEqual(result["cycle_calendar_rows"][0]["week_label"], "04-13当周")
        self.assertEqual(result["cycle_calendar_rows"][0]["tuesday"], {"date": "04-14", "mainline": "电力", "state": "主导"})
        self.assertEqual(result["cycle_calendar_rows"][1]["friday"], {"date": "04-24", "mainline": "半导体", "state": "试探修复"})
        self.assertEqual(result["cycle_interpretation_rows"][0]["cycle_label"], "近5周期-1")
        self.assertEqual(result["cycle_interpretation_rows"][1]["cycle_label"], "当前周期")
        self.assertEqual(result["cycle_interpretation_rows"][1]["trading_days"], "4日")
        self.assertIn("半导体", result["cycle_interpretation_rows"][1]["interpretation"])
        self.assertEqual(result["pivot_mainline_rows"][0]["pivot_level"], "大中枢")
        self.assertEqual(result["pivot_mainline_rows"][0]["mainline_degree"], "大主线")
        self.assertEqual(result["pivot_mainline_rows"][0]["evolution"], "高位分化")
        self.assertEqual(result["pivot_mainline_rows"][0]["replacement"], "中枢震荡")
        self.assertEqual(result["pivot_mainline_rows"][0]["structure_state"], "上沿承压")
        self.assertRegex(result["pivot_mainline_rows"][0]["interpretation"], r"。$")

    def test_derive_market_research_cycle_layer_separates_daily_attack_from_cycle_mainline(self):
        result = derive_market_research_cycle_layer(
            {
                "recent_mainline_history": [
                    {"date": "2026-05-12", "primary_mainline": "电力", "market_state": "主导"},
                    {"date": "2026-05-13", "primary_mainline": "电力", "market_state": "观察"},
                ],
                "current_mainline_history_record": {
                    "date": "2026-05-14",
                    "primary_mainline": "半导体",
                    "market_state": "观察",
                },
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中",
                    }
                },
            },
            state_machine={"leading_line": "半导体", "energy_state": "观察"},
        )

        current = result["cycle_interpretation_rows"][-1]
        self.assertEqual(current["attack_line"], "半导体")
        self.assertEqual(current["cycle_stage"], "切换试攻")
        self.assertEqual(current["transfer_state"], "首次攻击")
        self.assertIn("二次攻击", current["tomorrow_validation"])
        self.assertIn("今日攻击成立", current["interpretation"])
        self.assertIn("不自动升级周期主线", current["interpretation"])
        self.assertNotIn("正在承担当前周期的主线观察任务", current["interpretation"])

    def test_derive_market_research_cycle_layer_keeps_countertrend_attack_defensive(self):
        result = derive_market_research_cycle_layer(
            {
                "recent_mainline_history": [
                    {"date": "2026-05-20", "primary_mainline": "半导体", "rotation_label": "支线轮动"},
                ],
                "current_mainline_history_record": {
                    "date": "2026-05-21",
                    "primary_mainline": "人形机器人",
                    "rotation_label": "逆势攻击",
                    "rotation_summary": "当前逆势攻击；放量杀跌中只有人形机器人局部攻击",
                },
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    }
                },
            },
            state_machine={"leading_line": "人形机器人", "energy_state": "收缩防守"},
        )

        current = result["cycle_interpretation_rows"][-1]
        self.assertEqual(current["market_state"], "逆势攻击")
        self.assertEqual(current["transfer_state"], "逆势试攻")
        self.assertIn("先防踩踏", current["tomorrow_validation"])
        self.assertIn("放量杀跌", current["interpretation"])
        pivot = result["pivot_mainline_rows"][-1]
        self.assertEqual(pivot["mainline_degree"], "观察主攻线")
        self.assertEqual(pivot["evolution"], "逆势攻击")
        self.assertIn("不按周期主线处理", pivot["interpretation"])

    def test_derive_market_research_cycle_layer_uses_chaotic_attack_state_without_declaring_attack(self):
        result = derive_market_research_cycle_layer(
            {
                "recent_mainline_history": [
                    {"date": "2026-05-12", "primary_mainline": "电力", "market_state": "主导"},
                    {"date": "2026-05-13", "primary_mainline": "电力", "market_state": "观察"},
                ],
                "current_mainline_history_record": {
                    "date": "2026-05-14",
                    "primary_mainline": "半导体",
                    "market_state": "观察",
                },
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "chaotic_rotation",
                        "primary_line": "",
                        "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                        "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                    }
                },
            },
            state_machine={"leading_line": "半导体", "energy_state": "观察"},
        )

        current = result["cycle_interpretation_rows"][-1]
        self.assertEqual(current["attack_line"], "混沌轮动")
        self.assertEqual(current["cycle_stage"], "混沌轮动")
        self.assertEqual(current["transfer_state"], "混沌轮动")
        self.assertIn("单一方向胜出", current["tomorrow_validation"])
        self.assertIn("当前多线分散", current["interpretation"])
        self.assertNotIn("今日攻击成立", current["interpretation"])
        self.assertNotIn("看半导体是否二次攻击", current["tomorrow_validation"])

    def test_derive_market_research_cycle_layer_calendar_uses_latest_25_trading_days(self):
        trading_dates = [
            "2026-04-01",
            "2026-04-02",
            "2026-04-03",
            "2026-04-06",
            "2026-04-07",
            "2026-04-08",
            "2026-04-09",
            "2026-04-10",
            "2026-04-13",
            "2026-04-14",
            "2026-04-15",
            "2026-04-16",
            "2026-04-17",
            "2026-04-20",
            "2026-04-21",
            "2026-04-22",
            "2026-04-23",
            "2026-04-24",
            "2026-04-27",
            "2026-04-28",
            "2026-04-29",
            "2026-04-30",
            "2026-05-01",
            "2026-05-04",
            "2026-05-05",
            "2026-05-06",
        ]
        history = [
            {
                "date": trade_date,
                "primary_mainline": "电力" if index % 3 == 0 else "半导体",
                "market_state": "观察",
            }
            for index, trade_date in enumerate(trading_dates[:-1])
        ]

        result = derive_market_research_cycle_layer(
            {
                "recent_mainline_history": history,
                "current_mainline_history_record": {
                    "date": "2026-05-06",
                    "primary_mainline": "通信",
                    "market_state": "试探",
                },
            },
            state_machine={"leading_line": "通信"},
        )
        rendered_cells = [
            cell
            for row in result["cycle_calendar_rows"]
            for field in ("monday", "tuesday", "wednesday", "thursday", "friday")
            for cell in (row[field] if isinstance(row[field], list) else [row[field]])
            if isinstance(cell, dict) and cell.get("date")
        ]

        self.assertEqual(len(rendered_cells), 25)
        self.assertEqual(rendered_cells[0]["date"], "04-02")
        self.assertEqual(rendered_cells[-1]["date"], "05-06")

    def test_derive_market_research_cycle_layer_calendar_uses_rotation_state_when_market_state_missing(self):
        result = derive_market_research_cycle_layer(
            {
                "recent_mainline_history": [
                    {
                        "date": "2026-05-13",
                        "primary_mainline": "电力",
                        "rotation_label": "爆发",
                        "state_code": "expand",
                    },
                    {
                        "date": "2026-05-14",
                        "primary_mainline": "半导体",
                        "rotation_label": "",
                        "state_code": "contract",
                    },
                ],
                "current_mainline_history_record": {
                    "date": "2026-05-15",
                    "primary_mainline": "半导体",
                    "rotation_label": "支线轮动",
                    "state_code": "contract",
                },
            },
            state_machine={"leading_line": "半导体"},
        )

        row = result["cycle_calendar_rows"][0]
        self.assertEqual(row["wednesday"], {"date": "05-13", "mainline": "电力", "state": "爆发"})
        self.assertEqual(row["thursday"], {"date": "05-14", "mainline": "半导体", "state": "收缩分歧"})
        self.assertEqual(row["friday"], {"date": "05-15", "mainline": "半导体", "state": "支线轮动"})

    def test_derive_market_research_cycle_layer_treats_pivot_as_mainline_cycle_carrier(self):
        result = derive_market_research_cycle_layer(
            {
                "recent_mainline_history": [
                    {"date": "2026-04-20", "primary_mainline": "电力", "market_state": "退潮"},
                    {"date": "2026-04-21", "primary_mainline": "半导体", "market_state": "接力"},
                    {"date": "2026-04-22", "primary_mainline": "半导体", "market_state": "震荡"},
                ],
                "current_mainline_history_record": {"date": "2026-04-23", "primary_mainline": "半导体", "market_state": "强化"},
                "pivot_level": "小中枢",
                "pivot_range": "3992-4114",
                "pivot_position": "中枢内",
            },
            state_machine={"leading_line": "半导体", "energy_state": "强化"},
        )

        row = result["pivot_mainline_rows"][0]
        self.assertEqual(row["date_range"], "04-21 ~ 04-23")
        self.assertEqual(row["pivot_level"], "小中枢")
        self.assertEqual(row["mainline"], "半导体")
        self.assertEqual(row["mainline_degree"], "小周期主线")
        self.assertEqual(row["evolution"], "接力后强化")
        self.assertEqual(row["replacement"], "接替电力")
        self.assertIn("中枢是主线周期载体", row["interpretation"])

    def test_derive_market_research_cycle_layer_places_record_on_actual_weekday(self):
        result = derive_market_research_cycle_layer(
            {
                "current_mainline_history_record": {
                    "date": "2026-04-24",
                    "primary_mainline": "半导体",
                    "market_state": "观察",
                }
            },
            state_machine={"leading_line": "半导体"},
        )

        row = result["cycle_calendar_rows"][0]
        self.assertEqual(row["week_label"], "04-20当周")
        self.assertEqual(row["monday"], {"mainline": "-", "state": "-"})
        self.assertEqual(row["thursday"], {"mainline": "-", "state": "-"})
        self.assertEqual(row["friday"], {"date": "04-24", "mainline": "半导体", "state": "观察"})

    def test_build_market_research_snapshot_contract_composes_state_machine_bundle(self):
        result = build_market_research_snapshot_contract(
            data={
                "sector_ai_analysis": {"mapping": {"军工": "军工"}},
                "mainline_turnover_summary": {
                    "conclusion": "主线未切换，军工仍是中心",
                    "data_text": "最近3日主线 军工 -> 军工 -> 军工；成交额占比 10.2% -> 12.8% -> 15.1%",
                    "action_text": "继续围绕军工做减法",
                },
            },
            final_gate={"can_new_entry": True},
            position_level="50%条件执行",
            exit_analysis={"overall_level": "黄灯"},
            observation_snapshot={
                "abnormal_watch_pool": [{"code": "000001"}],
                "main_sectors_info": [{"name": "军工"}],
                "secondary_sectors_info": [{"name": "机器人"}],
                "sector_trend_snapshot": [{"sector": "军工"}],
            },
            target_date="2026-04-22",
            build_abnormal_projection_summary=lambda pool: {"projection_label": "承接强化"},
            build_market_style_switch_snapshot=lambda target_date, data, observation_snapshot, abnormal_projection: {"style_label": "主线抱团"},
            build_market_state_machine_snapshot=lambda *args, **kwargs: {"leading_line": "军工", "state_code": "expand"},
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "军工继续聚焦"},
            build_abnormal_probe_group=lambda **kwargs: {"probe_group_label": "先看异常"},
            build_special_probe_verdict=lambda **kwargs: {"summary_text": "先看异常承接", "action": "看军工异常股"},
            build_follow_verdict=lambda *args, **kwargs: {"label": "🟢 跟随主线", "reason": "主线清晰", "action": "只跟军工"},
            build_dialectical_decision_snapshot=lambda **kwargs: {"stage_label": "主升", "stage_action": "继续跟随"},
        )

        self.assertEqual(result["state_machine"]["leading_line"], "军工")
        self.assertEqual(result["follow_verdict"]["label"], "🟢 跟随主线")
        self.assertEqual(result["mainline_rotation_snapshot"]["summary_text"], "军工继续聚焦")
        self.assertEqual(result["mainline_turnover_summary"]["conclusion"], "主线未切换，军工仍是中心")
        self.assertEqual(result["special_probe_verdict"]["action"], "看军工异常股")
        self.assertTrue(any(log["step"] == "follow_verdict" for log in result["module_logs"]))

    def test_market_fit_uses_visible_observation_pool_not_full_candidate_pool(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="电力")
        kwargs["observation_snapshot"] = {
            "abnormal_watch_pool": [
                {"code": f"{index:06d}", "sector": "电力"}
                for index in range(5)
            ],
            "leader_memory_bank": [],
            "main_sectors_info": [{"name": "电力"}],
            "secondary_sectors_info": [],
            "sector_trend_snapshot": [],
        }
        result = build_market_research_snapshot_contract(
            data={
                "zt_pool": [
                    {"code": f"{index:06d}", "sector": "电力"}
                    for index in range(20)
                ],
                "candidates": [
                    {"code": f"{index:06d}", "sector": "电力"}
                    for index in range(126)
                ],
            },
            **kwargs,
        )

        evidence_text = result["market_fit_calibration"]["evidence_text"]

        self.assertIn("观察池命中5只", evidence_text)
        self.assertNotIn("观察池命中20只", evidence_text)

    def test_derive_step0_follow_plan_contract_merges_probe_and_style_actions(self):
        result = derive_step0_follow_plan_contract(
            {
                "state_machine": {"state_code": "contract", "energy_state": "收缩防守"},
                "follow_verdict": {"label": "🟡 条件跟随", "reason": "先看环境", "action": "缩小范围"},
                "style_switch": {"style_label": "轮动", "primary_action": "不要追高"},
                "special_probe_verdict": {"summary_text": "先看异常承接", "action": "看异常龙头"},
            },
            {"can_new_entry": True},
            "0%不参与",
        )

        self.assertEqual(result["step0_prediction"], "DIFFICULT")
        self.assertIn("先看特殊标的", result["step0_action"])
        self.assertIn("不要追高", result["step0_action"])
        self.assertIn("先看异常承接", result["step0_reason"])
        self.assertTrue(any(log["step"] == "step0_plan" for log in result["module_logs"]))

    def test_build_market_research_snapshot_contract_derives_mainline_turnover_summary_when_missing(self):
        result = build_market_research_snapshot_contract(
            data={
                "current_mainline_history_record": {"date": "2026-04-24", "primary_mainline": "通信"},
                "recent_mainline_history": [
                    {"date": "2026-04-22", "primary_mainline": "通信"},
                    {"date": "2026-04-23", "primary_mainline": "通信"},
                ],
                "current_sector_turnover_snapshot": {"date": "2026-04-24", "sector_name": "通信", "turnover_share_pct": 18.1},
                "recent_sector_turnover_history": [
                    {"date": "2026-04-22", "sector_name": "通信", "turnover_share_pct": 12.4},
                    {"date": "2026-04-23", "sector_name": "通信", "turnover_share_pct": 15.8},
                ],
            },
            final_gate={"can_new_entry": True},
            position_level="50%条件执行",
            exit_analysis={"overall_level": "黄灯"},
            observation_snapshot={
                "abnormal_watch_pool": [{"code": "000001"}],
                "main_sectors_info": [{"name": "通信"}],
                "secondary_sectors_info": [{"name": "机器人"}],
                "sector_trend_snapshot": [{"sector": "通信"}],
            },
            target_date="2026-04-24",
            build_abnormal_projection_summary=lambda pool: {"projection_label": "承接强化"},
            build_market_style_switch_snapshot=lambda target_date, data, observation_snapshot, abnormal_projection: {"style_label": "主线抱团"},
            build_market_state_machine_snapshot=lambda *args, **kwargs: {"leading_line": "通信", "state_code": "expand"},
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "通信继续聚焦"},
            build_abnormal_probe_group=lambda **kwargs: {"probe_group_label": "先看异常"},
            build_special_probe_verdict=lambda **kwargs: {"summary_text": "先看异常承接", "action": "看通信异常股"},
            build_follow_verdict=lambda *args, **kwargs: {"label": "🟢 跟随主线", "reason": "主线清晰", "action": "只跟通信"},
            build_dialectical_decision_snapshot=lambda **kwargs: {"stage_label": "主升", "stage_action": "继续跟随"},
            build_mainline_turnover_summary=lambda **kwargs: {
                "conclusion": "主线未切换，通信仍是中心",
                "data_text": "最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%，节奏偏强化",
                "action_text": "继续围绕通信做减法，不追支线分流",
            },
        )

        self.assertEqual(result["mainline_turnover_summary"]["conclusion"], "主线未切换，通信仍是中心")
        self.assertIn("18.1%", result["mainline_turnover_summary"]["data_text"])

    def test_build_market_research_snapshot_contract_uses_mainline_capacity_node_by_default(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="通信")

        result = build_market_research_snapshot_contract(
            data={
                "current_mainline_history_record": {
                    "date": "2026-04-24",
                    "primary_mainline": "通信",
                    "secondary_mainline": "机器人",
                },
                "recent_mainline_history": [
                    {"date": "2026-04-22", "primary_mainline": "通信"},
                    {"date": "2026-04-23", "primary_mainline": "通信"},
                ],
                "current_sector_turnover_snapshot": {
                    "date": "2026-04-24",
                    "sector_name": "通信",
                    "sector_turnover": 4050.0,
                    "total_turnover": 35000.0,
                    "turnover_share_pct": 11.57,
                    "source_status": "success",
                },
                "recent_sector_turnover_history": [
                    {
                        "date": "2026-04-22",
                        "sector_name": "通信",
                        "sector_turnover": 2744.0,
                        "total_turnover": 28000.0,
                        "turnover_share_pct": 9.8,
                    },
                    {
                        "date": "2026-04-23",
                        "sector_name": "通信",
                        "sector_turnover": 3286.0,
                        "total_turnover": 31000.0,
                        "turnover_share_pct": 10.6,
                    },
                ],
            },
            **kwargs,
        )

        summary = result["mainline_turnover_summary"]
        self.assertEqual(summary["current_mainline"], "通信")
        self.assertEqual(summary["share_trend_label"], "强化")
        self.assertEqual(
            summary["mainline_capacity_regime_summary"]["mainline_capacity"],
            "双线孕育",
        )
        self.assertTrue(
            any(log["step"] == "run.summary" for log in result["module_logs"]),
            result["module_logs"],
        )

    def test_build_market_research_snapshot_contract_loads_latest_25_mainline_history_days(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        calls = []

        result = build_market_research_snapshot_contract(
            data={"target_date": "2026-04-24"},
            build_mainline_history_record=lambda target_date, payload: {
                "date": target_date,
                "primary_mainline": "半导体",
            },
            load_recent_mainline_history=lambda target_date, **load_kwargs: calls.append((target_date, load_kwargs)) or [
                {"date": "2026-04-22", "primary_mainline": "半导体"},
                {"date": "2026-04-23", "primary_mainline": "半导体"},
            ],
            **kwargs,
        )

        self.assertEqual(calls, [("2026-04-24", {"lookback_days": 25, "max_scan_days": 60})])
        self.assertEqual(len(result["recent_mainline_history"]), 2)

    def test_build_market_research_snapshot_contract_loads_latest_25_sector_turnover_days(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        kwargs["target_date"] = "2026-05-20"
        calls = []

        result = build_market_research_snapshot_contract(
            data={"target_date": "2026-05-20", "total_turnover": 29764.59},
            build_mainline_history_record=lambda target_date, payload: {
                "date": target_date,
                "primary_mainline": "半导体",
            },
            load_recent_mainline_history=lambda target_date, **load_kwargs: [],
            get_sector_turnover_snapshot_from_ths=lambda sector_name, **snapshot_kwargs: {
                "date": "2026-05-20",
                "sector_name": sector_name,
                "sector_turnover": 4050.0,
                "total_turnover": 29764.59,
                "turnover_share_pct": 13.61,
            },
            load_recent_sector_turnover_history=lambda target_date, sector_name, **load_kwargs: calls.append(
                (target_date, sector_name, load_kwargs)
            )
            or [
                {
                    "date": "2026-05-19",
                    "sector_name": sector_name,
                    "sector_turnover": 3440.0,
                    "total_turnover": 29089.77,
                    "turnover_share_pct": 11.83,
                }
            ],
            build_mainline_turnover_summary=lambda **summary_kwargs: {
                "current_mainline": summary_kwargs["current_mainline_history_record"]["primary_mainline"],
                "turnover_share_trend_rows": [],
            },
            **kwargs,
        )

        self.assertEqual(calls, [("2026-05-20", "半导体", {"lookback_days": 25})])
        self.assertEqual(result["recent_sector_turnover_history"][0]["date"], "2026-05-19")

    def test_build_market_research_snapshot_contract_loads_turnover_by_each_daily_mainline(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        kwargs["target_date"] = "2026-05-20"
        calls = []

        result = build_market_research_snapshot_contract(
            data={"target_date": "2026-05-20", "total_turnover": 29764.59},
            build_mainline_history_record=lambda target_date, payload: {
                "date": target_date,
                "primary_mainline": "半导体",
            },
            load_recent_mainline_history=lambda target_date, **load_kwargs: [
                {"date": "2026-05-18", "primary_mainline": "电力", "daily_attack_line": "电力"},
                {"date": "2026-05-19", "primary_mainline": "电力", "daily_attack_line": "电力"},
            ],
            get_sector_turnover_snapshot_from_ths=lambda sector_name, **snapshot_kwargs: {
                "date": "2026-05-20",
                "sector_name": sector_name,
                "sector_turnover": 4050.0,
                "total_turnover": 29764.59,
                "turnover_share_pct": 13.61,
            },
            load_recent_sector_turnover_history=lambda target_date, sector_name, **load_kwargs: calls.append(
                (target_date, sector_name, load_kwargs)
            )
            or [
                {
                    "date": "2026-05-18",
                    "sector_name": sector_name,
                    "sector_turnover": 486.0,
                    "total_turnover": 29170.74,
                    "turnover_share_pct": 1.67,
                },
                {
                    "date": "2026-05-19",
                    "sector_name": sector_name,
                    "sector_turnover": 665.0,
                    "total_turnover": 29089.77,
                    "turnover_share_pct": 2.29,
                }
            ],
            build_mainline_turnover_summary=lambda **summary_kwargs: {
                "current_mainline": summary_kwargs["current_mainline_history_record"]["primary_mainline"],
                "turnover_share_trend_rows": summary_kwargs["recent_sector_turnover_history"],
            },
            **kwargs,
        )

        self.assertEqual(
            calls,
            [
                ("2026-05-20", "电力", {"lookback_days": 25}),
            ],
        )
        self.assertEqual([row["cycle_mainline"] for row in result["recent_sector_turnover_history"]], ["电力", "电力"])

    def test_build_market_research_snapshot_contract_uses_tencent_sector_flow_turnover_before_ths(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")

        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-04-24",
                "total_turnover": 26414.92,
                "sector_fund_flow": {
                    "inflow": [
                        {
                            "name": "半导体",
                            "code": "pt01801081",
                            "cje": 26381045.0,
                            "zdf": 1.56,
                        }
                    ],
                    "outflow": [],
                },
            },
            build_mainline_history_record=lambda target_date, payload: {
                "date": target_date,
                "primary_mainline": "半导体",
            },
            get_sector_turnover_snapshot_from_tencent_fund_flow=lambda *args, **kwargs: {
                "date": "2026-04-24",
                "sector_name": "半导体",
                "sector_code": "pt01801081",
                "sector_turnover": 2638.1,
                "total_turnover": 26414.92,
                "turnover_share_pct": 9.99,
                "source": "tencent.fundflow.getHyRank",
                "source_status": "success",
            },
            get_sector_turnover_snapshot_from_ths=lambda *args, **kwargs: self.fail("腾讯成交额可用时不应再调用 thsdk"),
            build_mainline_turnover_summary=lambda **kwargs: {
                "current_snapshot": kwargs["current_sector_turnover_snapshot"],
                "turnover_share_trend_rows": [
                    {
                        "date": "2026-04-24",
                        "cycle_mainline": "半导体",
                        "daily_attack_line": "半导体",
                        "mainline_turnover": "2638.10亿",
                        "market_turnover": "26414.92亿",
                        "share": "10.0%",
                        "share_change": "待累计",
                        "interpretation": "主线成交额占比可用，继续观察占比抬升或回落",
                    }
                ],
            },
            **kwargs,
        )

        snapshot = result["current_sector_turnover_snapshot"]
        self.assertEqual(snapshot["sector_code"], "pt01801081")
        self.assertEqual(snapshot["sector_turnover"], 2638.1)
        self.assertEqual(snapshot["turnover_share_pct"], 9.99)
        self.assertEqual(snapshot["source"], "tencent.fundflow.getHyRank")
        self.assertEqual(result["mainline_turnover_summary"]["current_snapshot"]["source"], "tencent.fundflow.getHyRank")

    def test_build_market_research_snapshot_contract_feeds_structured_attack_evidence_into_mainline_summary(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="电力")
        captured = {}

        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-05-15",
                "total_turnover": 33880.86,
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "半导体", "zljlr": 45.0, "turnover_yi": 4206.7},
                        {"name": "电力", "zljlr": 8.0, "turnover_yi": 2300.0},
                    ],
                    "outflow": [],
                },
                "zt_pool_by_sector": {
                    "半导体": [
                        {"名称": "中船特气", "涨停统计": "4连板"},
                        {"名称": "芯片一号", "涨停统计": "首板"},
                        {"名称": "芯片二号", "涨停统计": "首板"},
                        {"名称": "芯片三号", "涨停统计": "首板"},
                        {"名称": "芯片四号", "涨停统计": "首板"},
                    ],
                    "电力": [{"名称": "电力一号", "涨停统计": "首板"}],
                },
            },
            build_mainline_history_record=lambda target_date, payload: {
                "date": target_date,
                "primary_mainline": "电力",
            },
            get_sector_turnover_snapshot_from_tencent_fund_flow=lambda *args, **kwargs: {
                "date": "2026-05-15",
                "sector_name": "电力",
                "sector_turnover": 2300.0,
                "total_turnover": 33880.86,
                "turnover_share_pct": 6.79,
            },
            build_mainline_turnover_summary=lambda **kwargs: captured.update(kwargs)
            or {
                "current_mainline": "半导体",
                "mainline_attack_evidence_summary": {"attack_state": "confirmed_attack", "primary_line": "半导体"},
            },
            **kwargs,
        )

        evidence_rows = captured["sector_attack_evidence_rows"]
        semiconductor = next(row for row in evidence_rows if row["sector_name"] == "半导体")
        self.assertEqual(semiconductor["net_inflow_rank"], 1)
        self.assertEqual(semiconductor["net_inflow_amount"], 45.0)
        self.assertEqual(semiconductor["limit_up_count"], 5)
        self.assertEqual(semiconductor["high_anchor_height"], 4)
        self.assertEqual(semiconductor["high_anchor_name"], "中船特气")
        self.assertEqual(semiconductor["turnover_share_pct"], 12.42)
        self.assertEqual(result["mainline_turnover_summary"]["current_mainline"], "半导体")

    def test_build_market_research_snapshot_contract_derives_dragon_pullback_review_from_ladder_feedback(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="电力")

        result = build_market_research_snapshot_contract(
            data={
                "zt_pool_by_sector": {
                    "电力": [
                        {"名称": "华电辽能", "涨停统计": "5连板", "pressure_hold_confirmed": True},
                        {"名称": "高位跟随", "涨停统计": "3连板"},
                        {"名称": "京能电力", "涨停统计": "2连板"},
                        {"名称": "大唐发电", "涨停统计": "首板"},
                    ]
                }
            },
            **kwargs,
        )

        self.assertEqual(
            result.get("dragon_pullback_review"),
            {
                "sector": "电力",
                "leader": "华电辽能",
                "leader_height": 5,
                "second_confirmation": True,
                "laggard_feedback": ["京能电力", "大唐发电"],
                "pullback": "第一波后回撤观察，当前用低位反馈复核",
            },
        )

    def test_build_market_research_snapshot_contract_keeps_dragon_pullback_empty_without_leader_pressure_hold(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="电力")

        result = build_market_research_snapshot_contract(
            data={
                "zt_pool_by_sector": {
                    "电力": [
                        {"名称": "华电辽能", "涨停统计": "5连板"},
                        {"名称": "京能电力", "涨停统计": "2连板"},
                        {"名称": "大唐发电", "涨停统计": "首板"},
                    ]
                }
            },
            **kwargs,
        )

        self.assertEqual(result.get("dragon_pullback_review"), {})

    def test_build_market_research_snapshot_contract_keeps_dragon_pullback_empty_without_laggard_feedback(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="电力")

        result = build_market_research_snapshot_contract(
            data={
                "zt_pool_by_sector": {
                    "电力": [
                        {"名称": "华电辽能", "涨停统计": "5连板", "second_wave_confirmed": True},
                        {"名称": "高位跟随", "涨停统计": "3连板"},
                    ]
                }
            },
            **kwargs,
        )

        self.assertEqual(result.get("dragon_pullback_review"), {})

    def test_build_market_research_snapshot_contract_rewrites_current_history_from_confirmed_attack(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        kwargs["target_date"] = "2026-05-21"

        result = build_market_research_snapshot_contract(
            data={"target_date": "2026-05-21", "total_turnover": 35072.8},
            build_mainline_history_record=lambda target_date, payload: {
                "date": target_date,
                "primary_mainline": "半导体",
                "leading_line": "半导体",
                "secondary_mainline": "电力",
                "competition_mainline": "证券",
                "rotation_label": "爆发",
                "rotation_summary": "主攻线半导体 / 次强线电力 / 竞争线证券",
            },
            load_recent_mainline_history=lambda target_date, **load_kwargs: [
                {"date": "2026-05-20", "primary_mainline": "半导体"}
            ],
            get_sector_turnover_snapshot_from_ths=lambda sector_name, **snapshot_kwargs: {
                "date": "2026-05-21",
                "sector_name": sector_name,
                "sector_turnover": 4655.0,
                "total_turnover": 35072.8,
                "turnover_share_pct": 13.27,
            },
            load_recent_sector_turnover_history=lambda *args, **kwargs: [],
            build_mainline_turnover_summary=lambda **kwargs: {
                "current_mainline": "人形机器人",
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "人形机器人",
                    "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                },
            },
            **kwargs,
        )

        current_record = result["current_mainline_history_record"]
        self.assertEqual(current_record["primary_mainline"], "人形机器人")
        self.assertEqual(current_record["leading_line"], "人形机器人")
        self.assertEqual(current_record["secondary_mainline"], "")
        self.assertIn("人形机器人资金净流入靠前", current_record["rotation_summary"])
        self.assertNotIn("主攻线半导体", current_record["rotation_summary"])

    def test_build_market_research_snapshot_contract_keeps_countertrend_label_when_attack_line_rewrites_history(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        kwargs["target_date"] = "2026-05-21"

        def build_rotation(**rotation_kwargs):
            return {
                "rotation_label": "逆势攻击",
                "summary_text": "当前逆势攻击；放量杀跌中只有人形机器人局部攻击",
                "rotation_action": "先防踩踏，只观察次日是否修复承接",
            }
        kwargs["build_mainline_rotation_snapshot"] = build_rotation

        result = build_market_research_snapshot_contract(
            data={"target_date": "2026-05-21", "total_turnover": 35072.8},
            build_mainline_history_record=lambda target_date, payload: {
                "date": target_date,
                "primary_mainline": "半导体",
                "leading_line": "半导体",
                "secondary_mainline": "电力",
                "competition_mainline": "证券",
                "rotation_label": payload["mainline_rotation_snapshot"]["rotation_label"],
                "rotation_summary": payload["mainline_rotation_snapshot"]["summary_text"],
            },
            load_recent_mainline_history=lambda target_date, **load_kwargs: [
                {"date": "2026-05-20", "primary_mainline": "半导体", "rotation_label": "支线轮动"}
            ],
            get_sector_turnover_snapshot_from_ths=lambda sector_name, **snapshot_kwargs: {
                "date": "2026-05-21",
                "sector_name": sector_name,
                "sector_turnover": 880.0,
                "total_turnover": 35072.8,
                "turnover_share_pct": 2.51,
            },
            load_recent_sector_turnover_history=lambda *args, **kwargs: [],
            build_mainline_turnover_summary=lambda **summary_kwargs: {
                "current_mainline": "人形机器人",
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "人形机器人",
                    "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                },
            },
            **kwargs,
        )

        current_record = result["current_mainline_history_record"]
        self.assertEqual(current_record["primary_mainline"], "人形机器人")
        self.assertEqual(current_record["rotation_label"], "逆势攻击")
        self.assertIn("放量杀跌", current_record["rotation_summary"])
        self.assertNotEqual(current_record["rotation_label"], "爆发")

    def test_build_market_research_snapshot_contract_refreshes_cycle_layer_after_countertrend_attack_rewrite(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        kwargs["target_date"] = "2026-05-21"
        kwargs["build_mainline_rotation_snapshot"] = lambda **rotation_kwargs: {
            "rotation_label": "逆势攻击",
            "summary_text": "当前逆势攻击；放量杀跌中只有人形机器人局部攻击",
            "rotation_action": "先防踩踏，只观察次日是否修复承接",
        }

        result = build_market_research_snapshot_contract(
            data={"target_date": "2026-05-21", "total_turnover": 35072.8},
            build_mainline_history_record=lambda target_date, payload: {
                "date": target_date,
                "primary_mainline": "半导体",
                "leading_line": "半导体",
                "rotation_label": payload["mainline_rotation_snapshot"]["rotation_label"],
                "rotation_summary": payload["mainline_rotation_snapshot"]["summary_text"],
            },
            load_recent_mainline_history=lambda target_date, **load_kwargs: [
                {"date": "2026-05-20", "primary_mainline": "半导体", "rotation_label": "支线轮动"}
            ],
            get_sector_turnover_snapshot_from_ths=lambda sector_name, **snapshot_kwargs: {
                "date": "2026-05-21",
                "sector_name": sector_name,
                "sector_turnover": 880.0,
                "total_turnover": 35072.8,
                "turnover_share_pct": 2.51,
            },
            load_recent_sector_turnover_history=lambda *args, **kwargs: [],
            build_mainline_turnover_summary=lambda **summary_kwargs: {
                "current_mainline": "人形机器人",
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "人形机器人",
                    "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                },
            },
            **kwargs,
        )

        cycle_layer = derive_market_research_cycle_layer(result, result["state_machine"])
        current = cycle_layer["cycle_interpretation_rows"][-1]
        self.assertEqual(current["market_state"], "逆势攻击")
        self.assertEqual(current["transfer_state"], "逆势试攻")
        self.assertIn("先防踩踏", current["tomorrow_validation"])

    def test_build_market_research_snapshot_contract_refreshes_stale_current_record_before_countertrend_attack_alignment(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        kwargs["target_date"] = "2026-05-21"
        kwargs["build_mainline_rotation_snapshot"] = lambda **rotation_kwargs: {
            "rotation_label": "逆势攻击",
            "summary_text": "当前逆势攻击；放量杀跌中只有人形机器人局部攻击",
            "rotation_action": "先防踩踏，只观察次日是否修复承接",
        }

        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-05-21",
                "total_turnover": 35072.8,
                "current_mainline_history_record": {
                    "date": "2026-05-21",
                    "primary_mainline": "半导体",
                    "leading_line": "半导体",
                    "secondary_mainline": "电力",
                    "competition_mainline": "证券",
                    "rotation_label": "爆发",
                    "rotation_summary": "旧结论：成交额继续回升，而异常承接和趋势密度都还在",
                },
            },
            get_sector_turnover_snapshot_from_ths=lambda sector_name, **snapshot_kwargs: {
                "date": "2026-05-21",
                "sector_name": sector_name,
                "sector_turnover": 880.0,
                "total_turnover": 35072.8,
                "turnover_share_pct": 2.51,
            },
            load_recent_sector_turnover_history=lambda *args, **kwargs: [],
            build_mainline_turnover_summary=lambda **summary_kwargs: {
                "current_mainline": "人形机器人",
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "人形机器人",
                    "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                },
            },
            **kwargs,
        )

        current_record = result["current_mainline_history_record"]
        self.assertEqual(current_record["primary_mainline"], "人形机器人")
        self.assertEqual(current_record["rotation_label"], "逆势攻击")
        self.assertIn("放量杀跌", current_record["rotation_summary"])
        self.assertNotIn("异常承接和趋势密度都还在", current_record["rotation_summary"])

        cycle_layer = derive_market_research_cycle_layer(result, result["state_machine"])
        current_cycle = cycle_layer["cycle_interpretation_rows"][-1]
        self.assertEqual(current_cycle["market_state"], "逆势攻击")
        self.assertEqual(current_cycle["transfer_state"], "逆势试攻")

    def test_build_sector_attack_evidence_rows_parses_slash_zt_type_as_board_count(self):
        rows = _build_sector_attack_evidence_rows(
            {
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "半导体", "zljlr": 12.0},
                        {"name": "化学制品", "zljlr": 8.0},
                        {"name": "光伏设备", "zljlr": 5.0},
                        {"name": "家居用品", "zljlr": 4.0},
                    ]
                },
                "zt_pool_by_sector": {
                    "半导体": [{"name": "中船特气", "zt_type": "4/3"}],
                    "化学制品": [{"name": "和远气体", "zt_type": "4/2"}],
                    "光伏设备": [{"name": "协鑫集成", "zt_type": "1/1"}],
                    "家居用品": [{"name": "蒙娜丽莎", "zt_type": "5/5"}],
                    "电力": [{"name": "金房能源", "涨停统计": "4天2板"}],
                    "军工": [{"name": "军工一号", "涨停统计": "4连板"}],
                    "算力": [{"name": "算力一号", "涨停统计": "首板"}],
                },
            },
            {},
            [],
            0,
        )

        by_sector = {row["sector_name"]: row for row in rows}
        self.assertEqual(by_sector["半导体"]["high_anchor_height"], 3)
        self.assertEqual(by_sector["化学制品"]["high_anchor_height"], 2)
        self.assertEqual(by_sector["光伏设备"]["high_anchor_height"], 1)
        self.assertEqual(by_sector["家居用品"]["high_anchor_height"], 5)
        self.assertEqual(by_sector["电力"]["high_anchor_height"], 2)
        self.assertEqual(by_sector["军工"]["high_anchor_height"], 4)
        self.assertEqual(by_sector["算力"]["high_anchor_height"], 1)
        self.assertNotIn(42, [row["high_anchor_height"] for row in rows])

    def test_build_sector_attack_evidence_rows_merges_cross_taxonomy_sector_flow(self):
        rows = _build_sector_attack_evidence_rows(
            {
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "IT服务", "zljlr": 42.0, "turnover_yi": 538.0},
                        {"name": "软件开发", "zljlr": 14.0, "turnover_yi": 323.0},
                    ],
                    "outflow": [
                        {"name": "建筑装饰", "zljlr": -2.0, "turnover_yi": 212.0},
                        {"name": "工程机械", "zljlr": -5.0, "turnover_yi": 53.0},
                    ],
                },
                "zt_pool_by_sector": {
                    "软件服务": [{"name": "彩讯股份", "zt_type": "2/2"}],
                    "建筑工程": [{"name": "圣晖集成", "zt_type": "4/3"}],
                },
            },
            {},
            [],
            29089.77,
        )

        by_sector = {row["sector_name"]: row for row in rows}
        self.assertEqual(by_sector["软件服务"]["net_inflow_amount"], 56.0)
        self.assertEqual(by_sector["软件服务"]["sector_turnover"], 861.0)
        self.assertEqual(by_sector["软件服务"]["turnover_share_pct"], 2.96)
        self.assertEqual(by_sector["建筑工程"]["net_inflow_amount"], -7.0)
        self.assertEqual(by_sector["建筑工程"]["sector_turnover"], 265.0)
        self.assertEqual(by_sector["建筑工程"]["turnover_share_pct"], 0.91)

    def test_build_market_research_snapshot_contract_adds_turnover_share_change_to_attack_evidence(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        captured = {}

        build_market_research_snapshot_contract(
            data={
                "target_date": "2026-05-15",
                "current_mainline_history_record": {"date": "2026-05-15", "primary_mainline": "半导体"},
                "recent_sector_turnover_history": [
                    {"date": "2026-05-14", "sector_name": "半导体", "turnover_share_pct": 10.8}
                ],
                "current_sector_turnover_snapshot": {
                    "date": "2026-05-15",
                    "sector_name": "半导体",
                    "sector_turnover": 4206.7,
                    "total_turnover": 33880.86,
                    "turnover_share_pct": 12.4,
                },
                "sector_fund_flow": {
                    "inflow": [{"name": "半导体", "zljlr": 45.0, "turnover_yi": 4206.7}],
                    "outflow": [],
                },
                "zt_pool_by_sector": {"半导体": [{"名称": "中船特气", "涨停统计": "4连板"}]},
            },
            build_mainline_turnover_summary=lambda **kwargs: captured.update(kwargs) or {"current_mainline": "半导体"},
            **kwargs,
        )

        semiconductor = next(row for row in captured["sector_attack_evidence_rows"] if row["sector_name"] == "半导体")
        self.assertEqual(semiconductor["turnover_share_pct"], 12.4)
        self.assertEqual(semiconductor["turnover_share_change"], 1.6)

    def test_build_market_research_snapshot_contract_passes_realtime_tag_snapshot_to_mainline_summary(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="元器件")
        captured = {}
        tag_snapshot = {
            "groups": [
                {
                    "采用名称": "国产芯片替代",
                    "大方向": "泛半导体/硬科技电子",
                    "当日主攻分支": "国产芯片替代",
                    "表层行业名": ["元器件", "芯片"],
                    "辅助名称": ["PCB"],
                    "关系判断": "父子",
                }
            ]
        }

        build_market_research_snapshot_contract(
            data={
                "target_date": "2026-05-24",
                "realtime_tag_evidence_snapshot": tag_snapshot,
                "sector_fund_flow": {
                    "inflow": [{"name": "元器件", "zljlr": 38.0, "turnover_yi": 3200.0}],
                    "outflow": [],
                },
                "zt_pool_by_sector": {
                    "元器件": [
                        {"名称": "芯片一号", "涨停统计": "4连板"},
                        {"名称": "芯片二号", "涨停统计": "首板"},
                        {"名称": "芯片三号", "涨停统计": "首板"},
                    ]
                },
            },
            build_mainline_turnover_summary=lambda **kwargs: captured.update(kwargs) or {"current_mainline": "国产芯片替代"},
            **kwargs,
        )

        self.assertIs(captured["realtime_tag_evidence_snapshot"], tag_snapshot)

    def test_build_market_research_snapshot_contract_rebuilds_existing_summary_when_attack_evidence_is_missing(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="电力")
        captured = {}

        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-05-15",
                "total_turnover": 33880.86,
                "mainline_turnover_summary": {
                    "current_mainline": "电力",
                    "conclusion": "主线未切换，电力仍是中心",
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-05-15",
                            "cycle_mainline": "电力",
                            "mainline_turnover": "2300.00亿",
                            "market_turnover": "33880.86亿",
                        }
                    ],
                },
                "current_mainline_history_record": {"date": "2026-05-15", "primary_mainline": "电力"},
                "sector_fund_flow": {
                    "inflow": [{"name": "半导体", "zljlr": 45.0, "turnover_yi": 4206.7}],
                    "outflow": [],
                },
                "zt_pool_by_sector": {
                    "半导体": [
                        {"名称": "中船特气", "涨停统计": "4连板"},
                        {"名称": "芯片一号", "涨停统计": "首板"},
                        {"名称": "芯片二号", "涨停统计": "首板"},
                        {"名称": "芯片三号", "涨停统计": "首板"},
                        {"名称": "芯片四号", "涨停统计": "首板"},
                    ]
                },
            },
            build_mainline_turnover_summary=lambda **kwargs: captured.update(kwargs)
            or {
                "current_mainline": "半导体",
                "mainline_attack_evidence_summary": {"attack_state": "confirmed_attack", "primary_line": "半导体"},
            },
            **kwargs,
        )

        self.assertEqual(captured["sector_attack_evidence_rows"][0]["sector_name"], "半导体")
        self.assertEqual(result["mainline_turnover_summary"]["current_mainline"], "半导体")

    def test_build_market_research_snapshot_contract_rebuilds_stale_empty_mainline_turnover_summary(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")

        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-04-24",
                "total_turnover": 26414.92,
                "mainline_turnover_summary": {
                    "current_mainline": "",
                    "conclusion": "主线待确认，暂不输出成交额占比结论",
                    "turnover_share_trend_rows": [],
                },
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "半导体", "code": "pt01801081", "turnover_yi": 2638.1}
                    ],
                    "outflow": [],
                },
            },
            build_mainline_history_record=lambda target_date, payload: {
                "date": target_date,
                "primary_mainline": "半导体",
            },
            get_sector_turnover_snapshot_from_tencent_fund_flow=lambda *args, **kwargs: {
                "date": "2026-04-24",
                "sector_name": "半导体",
                "sector_turnover": 2638.1,
                "total_turnover": 26414.92,
                "turnover_share_pct": 9.99,
                "source": "tencent.fundflow.getHyRank",
                "source_status": "success",
            },
            build_mainline_turnover_summary=lambda **kwargs: {
                "current_mainline": "半导体",
                "conclusion": "主线未切换，半导体仍是中心",
                "turnover_share_trend_rows": [
                    {
                        "date": "2026-04-24",
                        "cycle_mainline": "半导体",
                        "daily_attack_line": "半导体",
                        "mainline_turnover": "2638.10亿",
                        "market_turnover": "26414.92亿",
                        "share": "10.0%",
                        "share_change": "待累计",
                        "interpretation": "主线成交额占比可用，继续观察占比抬升或回落",
                    }
                ],
            },
            **kwargs,
        )

        self.assertEqual(result["mainline_turnover_summary"]["current_mainline"], "半导体")
        self.assertEqual(result["mainline_turnover_summary"]["turnover_share_trend_rows"][0]["share"], "10.0%")

    def test_build_market_research_snapshot_contract_rebuilds_stale_switch_summary_after_countertrend_rotation_refresh(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        captured = {}
        kwargs["build_mainline_rotation_snapshot"] = lambda **kwargs: {
            "rotation_label": "逆势攻击",
            "summary_text": "当前逆势攻击；成交额继续回升但指数大跌、跌停扩散、涨跌比极差，说明这不是增量进攻。",
            "rotation_action": "先防踩踏，只观察人形机器人次日是否修复承接",
        }

        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-05-21",
                "total_turnover": 35072.8,
                "current_mainline_history_record": {
                    "date": "2026-05-21",
                    "primary_mainline": "半导体",
                    "rotation_label": "爆发",
                },
                "recent_mainline_history": [
                    {"date": "2026-05-20", "primary_mainline": "半导体", "rotation_label": "支线轮动"},
                ],
                "mainline_turnover_summary": {
                    "current_mainline": "人形机器人",
                    "previous_mainline": "半导体",
                    "share_trend_label": "切换",
                    "conclusion": "主线切换为人形机器人，旧主线半导体退出中心",
                    "data_text": "最近3日主线 电力 -> 半导体 -> 人形机器人；成交额占比 2.3% -> 13.6% -> 2.5%，节奏偏切换",
                    "action_text": "只围绕新主线人形机器人重新收缩，不对旧主线做回流预判",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    },
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-05-21",
                            "cycle_mainline": "人形机器人",
                            "daily_attack_line": "人形机器人",
                            "mainline_turnover": "880.00亿",
                            "market_turnover": "35072.80亿",
                            "share": "2.5%",
                            "share_change": "-11.1pct",
                            "interpretation": "主线成交额占比可用，继续观察占比抬升或回落",
                        }
                    ],
                },
                "current_sector_turnover_snapshot": {
                    "date": "2026-05-21",
                    "sector_name": "半导体",
                    "sector_turnover": 4655.0,
                    "total_turnover": 35072.8,
                    "turnover_share_pct": 13.3,
                },
                "recent_sector_turnover_history": [
                    {
                        "date": "2026-05-20",
                        "sector_name": "半导体",
                        "sector_turnover": 4050.0,
                        "total_turnover": 29764.59,
                        "turnover_share_pct": 13.6,
                    }
                ],
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "汽车零部件", "zljlr": 30.0, "turnover_yi": 778.0},
                        {"name": "电机", "zljlr": 9.0, "turnover_yi": 102.0},
                    ],
                    "outflow": [],
                },
                "zt_pool_by_sector": {
                    "汽车零部件": [
                        {"名称": "三花智控", "涨停统计": "首板"},
                        {"名称": "拓普集团", "涨停统计": "首板"},
                        {"名称": "五洲新春", "涨停统计": "首板"},
                    ],
                    "电机": [
                        {"名称": "鸣志电器", "涨停统计": "首板"},
                        {"名称": "昊志机电", "涨停统计": "首板"},
                    ],
                },
            },
            build_mainline_turnover_summary=lambda **kwargs: captured.update(kwargs)
            or {
                "current_mainline": "人形机器人",
                "share_trend_label": "逆势试攻",
                "conclusion": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理",
                "data_text": "最近2日主线 半导体 -> 人形机器人；成交额占比 13.6% -> 2.5%，节奏偏逆势试攻",
                "action_text": "人形机器人只按观察主攻线处理，先防踩踏，再看次日是否修复承接",
                "double_mainline_summary": {
                    "cycle_mainline": "半导体",
                    "daily_attack_line": "人形机器人",
                    "relationship": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线处理",
                },
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "人形机器人",
                    "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                },
            },
            **kwargs,
        )

        self.assertEqual(captured["current_mainline_history_record"]["rotation_label"], "逆势攻击")
        self.assertIn("指数大跌", captured["current_mainline_history_record"]["rotation_summary"])
        self.assertEqual(result["current_mainline_history_record"]["primary_mainline"], "人形机器人")
        self.assertEqual(result["mainline_turnover_summary"]["share_trend_label"], "逆势试攻")
        self.assertIn("观察主攻线", result["mainline_turnover_summary"]["conclusion"])
        self.assertNotIn("主线切换为人形机器人", result["mainline_turnover_summary"]["conclusion"])

    def test_build_market_research_snapshot_contract_derives_lhb_capital_intent_from_lhb_rows(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="通信")
        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-04-24",
                "total_turnover": 12000.0,
                "lhb_net_buy_top10": [
                    {"name": "通信一号", "code": "000001", "sector": "通信", "net_buy_amount_yi": 4.2},
                    {"name": "通信二号", "code": "000002", "sector": "通信", "net_buy_amount_yi": 2.1},
                    {"name": "电力一号", "code": "000003", "sector": "电力", "net_buy_amount_yi": 1.3},
                ],
                "lhb_net_sell_top10": [
                    {"name": "消费一号", "code": "000004", "sector": "消费", "net_buy_amount_yi": -1.5},
                ],
            },
            **kwargs,
        )

        self.assertEqual(result["lhb_capital_status"]["capital_direction"], "通信")
        self.assertEqual(result["lhb_capital_status"]["capital_strength"], "强")
        self.assertIn("净买入", result["lhb_capital_status"]["capital_intensity"])
        self.assertIn("主线", result["capital_conclusion"]["mainline_attitude"])

    def test_build_market_research_snapshot_contract_ignores_board_labels_for_lhb_direction(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-05-18",
                "total_turnover": 29170.74,
                "lhb_net_buy_top10": [
                    {"name": "华工科技", "code": "000988", "sector": "HS", "net_buy_amount_yi": 16.98},
                    {"name": "弘信电子", "code": "300657", "sector": "GEM", "net_buy_amount_yi": 4.09},
                    {"name": "富创精密", "code": "688409", "sector": "STAR", "net_buy_amount_yi": 7.28},
                ],
                "lhb_net_sell_top10": [
                    {"name": "粤传媒", "code": "002181", "sector": "HS", "net_buy_amount_yi": -2.74},
                ],
            },
            **kwargs,
        )

        self.assertEqual(result["lhb_capital_status"]["capital_direction"], "未归类")
        self.assertNotIn("HS", result["lhb_capital_status"]["capital_intensity"])
        self.assertNotIn("方向在HS", result["capital_conclusion"]["current_capital_state"])

    def test_build_market_research_snapshot_contract_does_not_let_lhb_mismatch_veto_mainline(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")
        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-05-15",
                "total_turnover": 33880.86,
                "lhb_net_buy_top10": [
                    {"name": "电力一号", "code": "000001", "sector": "电力", "net_buy_amount_yi": 14.57},
                ],
                "lhb_net_sell_top10": [
                    {"name": "消费一号", "code": "000002", "sector": "消费", "net_buy_amount_yi": -26.16},
                ],
            },
            **kwargs,
        )

        self.assertEqual(result["capital_conclusion"]["mainline_attitude"], "龙虎榜未验证半导体")
        self.assertEqual(result["capital_conclusion"]["tomorrow_action_meaning"], "先看板块攻击证据，龙虎榜只作为验证层")
        self.assertNotIn("资金没有完全确认主线", result["capital_conclusion"]["mainline_attitude"])

    def test_build_market_research_snapshot_contract_uses_sector_attack_as_primary_capital_evidence(self):
        kwargs = self._minimal_snapshot_kwargs(leading_line="半导体")

        result = build_market_research_snapshot_contract(
            data={
                "target_date": "2026-05-15",
                "total_turnover": 33880.86,
                "current_mainline_history_record": {"date": "2026-05-15", "primary_mainline": "半导体"},
                "recent_sector_turnover_history": [
                    {"date": "2026-05-14", "sector_name": "半导体", "turnover_share_pct": 10.8}
                ],
                "current_sector_turnover_snapshot": {
                    "date": "2026-05-15",
                    "sector_name": "半导体",
                    "sector_turnover": 4206.7,
                    "total_turnover": 33880.86,
                    "turnover_share_pct": 12.4,
                },
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "半导体", "zljlr": 45.0, "turnover_yi": 4206.7},
                        {"name": "电力", "zljlr": 8.0, "turnover_yi": 2300.0},
                    ],
                    "outflow": [],
                },
                "zt_pool_by_sector": {
                    "半导体": [
                        {"名称": "中船特气", "涨停统计": "4连板"},
                        {"名称": "芯片一号", "涨停统计": "首板"},
                        {"名称": "芯片二号", "涨停统计": "首板"},
                        {"名称": "芯片三号", "涨停统计": "首板"},
                        {"名称": "芯片四号", "涨停统计": "首板"},
                    ]
                },
                "lhb_net_buy_top10": [
                    {"name": "电力一号", "code": "000001", "sector": "电力", "net_buy_amount_yi": 14.57},
                ],
                "lhb_net_sell_top10": [
                    {"name": "消费一号", "code": "000002", "sector": "消费", "net_buy_amount_yi": -26.16},
                ],
            },
            build_mainline_turnover_summary=lambda **kwargs: {
                "current_mainline": "半导体",
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "半导体",
                    "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
                },
            },
            **kwargs,
        )

        breakdown = result["capital_intent_breakdown"]
        self.assertEqual(breakdown["sector_fund_attitude"], "半导体板块攻击资金确认：净流入第1，+45.00亿")
        self.assertEqual(breakdown["strength_feedback"], "涨停5，高标4，成交占比+1.6pct")
        self.assertEqual(breakdown["lhb_validation"], "龙虎榜方向在电力，未验证主线")
        self.assertEqual(breakdown["capital_consistency"], "板块攻击成立，龙虎榜未验证")
        self.assertEqual(breakdown["tomorrow_meaning"], "先按板块攻击线观察，龙虎榜只作为加分，不作为主线否决")
        self.assertEqual(result["capital_conclusion"]["mainline_attitude"], "板块攻击成立，龙虎榜未验证")
        old_misleading_attitude = "资金没有完全确认主线，" + "先看是否轮动"
        self.assertNotEqual(result["capital_conclusion"]["mainline_attitude"], old_misleading_attitude)

    def test_build_market_research_snapshot_contract_saves_cycle_context_when_callback_is_available(self):
        saved = []
        kwargs = self._minimal_snapshot_kwargs("电力")
        kwargs["target_date"] = "2026-05-29"
        kwargs["data"] = {
            "recent_mainline_history": [
                {"date": "2026-05-27", "primary_mainline": "电力", "market_state": "主导"},
                {"date": "2026-05-28", "primary_mainline": "电力", "market_state": "强化"},
            ],
            "current_sector_turnover_snapshot": {
                "date": "2026-05-29",
                "sector_name": "电力",
                "sector_turnover": 320,
                "total_turnover": 10000,
                "turnover_share_pct": 3.2,
            },
        }

        result = build_market_research_snapshot_contract(
            **kwargs,
            save_market_cycle_context=lambda trade_date, snapshot: saved.append((trade_date, snapshot)),
        )

        self.assertEqual(saved[0][0], "2026-05-29")
        self.assertEqual(saved[0][1]["current_mainline_history_record"]["primary_mainline"], "电力")
        self.assertEqual(saved[0][1]["cycle_interpretation_rows"][-1]["cycle_label"], "当前周期")
        self.assertEqual(saved[0][1]["cycle_calendar_rows"][0]["week_label"], "05-25当周")
        self.assertEqual(result["cycle_interpretation_rows"][-1]["attack_line"], "电力")


if __name__ == "__main__":
    unittest.main()
