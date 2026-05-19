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
            "position_level": "三档（进攻档）",
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
        self.assertEqual(result["cycle_interpretation_rows"][0]["cycle_label"], "上个周期")
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
            position_level="三档（进攻档）",
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

    def test_derive_step0_follow_plan_contract_merges_probe_and_style_actions(self):
        result = derive_step0_follow_plan_contract(
            {
                "state_machine": {"state_code": "contract", "energy_state": "收缩防守"},
                "follow_verdict": {"label": "🟡 条件跟随", "reason": "先看环境", "action": "缩小范围"},
                "style_switch": {"style_label": "轮动", "primary_action": "不要追高"},
                "special_probe_verdict": {"summary_text": "先看异常承接", "action": "看异常龙头"},
            },
            {"can_new_entry": True},
            "二档（防守档）",
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
            position_level="三档（进攻档）",
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


if __name__ == "__main__":
    unittest.main()
