import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _run_legacy_entry_probe(script_body):
    stub_setup = """
import sys
import types

def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module

sys.path.insert(0, {scripts_path!r})
sys.modules.update(
    {{
        "data_collector": _stub_module("data_collector", AShareDataCollector=type("AShareDataCollector", (), {{}})),
        "ths_hot_stock": _stub_module(
            "ths_hot_stock",
            fetch_ths_hot_stock=lambda *args, **kwargs: [],
            fetch_hot_stock_with_fallback=lambda *args, **kwargs: [],
        ),
        "ths_hot_list": _stub_module("ths_hot_list", fetch_hot_plate=lambda *args, **kwargs: []),
        "tencent_finance_data": _stub_module("tencent_finance_data", TencentFinanceData=type("TencentFinanceData", (), {{}})),
        "xuangubao_intraday": _stub_module(
            "xuangubao_intraday",
            XuangubaoIntradayAnalyzer=type("XuangubaoIntradayAnalyzer", (), {{}}),
        ),
        "limit_up_down_pool": _stub_module(
            "limit_up_down_pool",
            get_limit_up_pool=lambda *args, **kwargs: ([], set()),
            get_limit_down_pool=lambda *args, **kwargs: ([], set()),
            mark_limit_status=lambda *args, **kwargs: {{}},
        ),
        "strong_stock_pool": _stub_module(
            "strong_stock_pool",
            get_strong_stock_pool=lambda *args, **kwargs: [],
            analyze_strong_stocks_by_sector=lambda *args, **kwargs: {{}},
        ),
        "data_validator": _stub_module("data_validator", DataValidator=type("DataValidator", (), {{}})),
        "quantitative_analyzer": _stub_module(
            "quantitative_analyzer",
            VolumeAnomalyDetector=type("VolumeAnomalyDetector", (), {{}}),
            LHBAnalyzer=type("LHBAnalyzer", (), {{}}),
            ResonanceAnalyzer=type("ResonanceAnalyzer", (), {{}}),
            SignalGenerator=type("SignalGenerator", (), {{}}),
            analyze_volume_anomaly=lambda *args, **kwargs: {{}},
            analyze_lhb=lambda *args, **kwargs: {{}},
            calculate_resonance=lambda *args, **kwargs: {{}},
            generate_trade_signals=lambda *args, **kwargs: {{}},
        ),
        "hot_list_integrated": _stub_module(
            "hot_list_integrated",
            get_integrated_hot_list=lambda *args, **kwargs: {{}},
            analyze_sector_distribution=lambda *args, **kwargs: {{}},
        ),
        "history_cache": _stub_module(
            "history_cache",
            get_cache=lambda *args, **kwargs: {{}},
            HistoryCache=type("HistoryCache", (), {{}}),
        ),
        "llm_service": _stub_module("llm_service", get_llm_service=lambda *args, **kwargs: None),
    }}
)
""".format(scripts_path=str(ROOT / "scripts"))

    return subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class MarketResearchSupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("research.market_research_support", fromlist=["market_research_support"])
        except ModuleNotFoundError as error:
            self.fail(f"research.market_research_support should exist: {error}")

    def test_legacy_market_research_wrappers_delegate_to_support_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_build_market_research_snapshot", return_value={"state_machine": {}}) as snapshot_mock, \
     patch.object(daily_report_entry_demo, "run_derive_step0_follow_plan", return_value={"step0_prediction_cn": "观察"}) as step0_mock, \
     patch.object(daily_report_entry_demo, "run_build_dialectical_decision_snapshot", return_value={"stage_label": "主升"}) as dialectical_mock, \
     patch.object(daily_report_entry_demo, "run_build_mainline_competition_snapshot", return_value=[{"sector": "军工", "role": "主攻线"}]) as competition_mock, \
     patch.object(daily_report_entry_demo, "run_build_abnormal_projection_summary", return_value={"projection_label": "异常承接强化"}) as projection_mock, \
     patch.object(daily_report_entry_demo, "run_build_market_observation_snapshot", return_value={"zt_count": 20}) as observation_mock, \
     patch.object(daily_report_entry_demo, "run_build_follow_verdict", return_value={"code": "follow"}) as follow_mock, \
     patch.object(daily_report_entry_demo, "run_render_market_research_snapshot_section", return_value="snapshot-section") as render_snapshot_mock, \
     patch.object(daily_report_entry_demo, "run_render_step0_follow_section", return_value="step0-section") as render_step0_mock, \
     patch.object(daily_report_entry_demo, "run_build_market_research_context_bundle", return_value={"market_state_snapshot": {"leading_line": "军工"}}) as bundle_mock:
    snapshot = daily_report_entry_demo._build_market_research_snapshot({}, {}, "三档（进攻档）", {}, target_date="2026-04-22")
    step0 = daily_report_entry_demo._derive_step0_follow_plan({"state_machine": {}}, {"can_new_entry": True}, "三档（进攻档）")
    dialectical = daily_report_entry_demo._build_dialectical_decision_snapshot({"zt_count": 20}, {"style_label": "主线抱团"}, {"state_code": "expand"}, {"code": "follow"}, {"can_new_entry": True})
    competition = daily_report_entry_demo._build_mainline_competition_snapshot([{"name": "军工"}], [{"name": "机器人"}], [{"sector": "军工"}], ["地产"])
    projection = daily_report_entry_demo._build_abnormal_projection_summary([{"follow_state": "跌不下去"}])
    observation = daily_report_entry_demo._build_market_observation_snapshot({"zt_pool": [{"code": "000001"}]})
    follow = daily_report_entry_demo._build_follow_verdict({"can_new_entry": True}, "三档（进攻档）", {"state_code": "expand"})
    snapshot_section = daily_report_entry_demo._render_market_research_snapshot_section({"observation": {}}, compact=True)
    step0_section = daily_report_entry_demo._render_step0_follow_section({"step0_prediction_cn": "观察"}, {"observation": {}}, compact=True)
    bundle = daily_report_entry_demo.build_market_research_context_bundle({}, "2026-04-22", {}, {}, "三档（进攻档）")

assert snapshot_mock.call_args[0][:4] == ({}, {}, "三档（进攻档）", {})
assert "helpers" in snapshot_mock.call_args.kwargs
assert step0_mock.call_args[0][2] == "三档（进攻档）"
assert dialectical_mock.call_args.kwargs["observation"] == {"zt_count": 20}
assert "helpers" in dialectical_mock.call_args.kwargs
assert competition_mock.call_args.kwargs["main_sectors_info"] == [{"name": "军工"}]
assert "helpers" in competition_mock.call_args.kwargs
assert projection_mock.call_args[0][0] == [{"follow_state": "跌不下去"}]
assert "helpers" in projection_mock.call_args.kwargs
assert observation_mock.call_args[0][0] == {"zt_pool": [{"code": "000001"}]}
assert "helpers" in observation_mock.call_args.kwargs
assert follow_mock.call_args[0][:3] == ({"can_new_entry": True}, "三档（进攻档）", {"state_code": "expand"})
assert "helpers" in follow_mock.call_args.kwargs
assert render_snapshot_mock.call_args[0][0] == {"observation": {}}
assert "helpers" in render_snapshot_mock.call_args.kwargs
assert render_step0_mock.call_args[0][0] == {"step0_prediction_cn": "观察"}
assert "helpers" in render_step0_mock.call_args.kwargs
assert bundle_mock.call_args[0][:5] == ({}, "2026-04-22", {}, {}, "三档（进攻档）")
assert "helpers" in bundle_mock.call_args.kwargs
assert snapshot == {"state_machine": {}}
assert step0 == {"step0_prediction_cn": "观察"}
assert snapshot_section == "snapshot-section"
assert step0_section == "step0-section"
assert bundle == {"market_state_snapshot": {"leading_line": "军工"}}
assert dialectical == {"stage_label": "主升"}
assert competition == [{"sector": "军工", "role": "主攻线"}]
assert projection == {"projection_label": "异常承接强化"}
assert observation == {"zt_count": 20}
assert follow == {"code": "follow"}
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_build_market_research_snapshot_support_delegates_to_contract_with_helpers(self):
        support = self._load_module()
        projection = lambda pool=None: {"projection_label": "承接强化"}
        style_switch = lambda *args, **kwargs: {"style_label": "主线抱团"}
        state_machine = lambda *args, **kwargs: {"leading_line": "军工"}
        rotation = lambda **kwargs: {"summary_text": "军工继续聚焦"}
        probe_group = lambda **kwargs: {"probe_group_label": "先看异常"}
        probe_verdict = lambda **kwargs: {"summary_text": "先看异常承接"}
        follow_verdict = lambda *args, **kwargs: {"label": "🟢 跟随主线"}
        dialectical = lambda **kwargs: {"stage_label": "主升"}

        with patch(
            "research.market_research_support.build_market_research_snapshot_contract",
            return_value={"state_machine": {"leading_line": "军工"}},
        ) as contract_mock:
            result = support.build_market_research_snapshot(
                {"sector_ai_analysis": {}},
                {"can_new_entry": True},
                "三档（进攻档）",
                {"overall_level": "黄灯"},
                target_date="2026-04-22",
                helpers={
                    "_build_abnormal_projection_summary": projection,
                    "_build_market_style_switch_snapshot": style_switch,
                    "_build_market_state_machine_snapshot": state_machine,
                    "_build_mainline_rotation_snapshot": rotation,
                    "_build_abnormal_probe_group": probe_group,
                    "_build_special_probe_verdict": probe_verdict,
                    "_build_follow_verdict": follow_verdict,
                    "_build_dialectical_decision_snapshot": dialectical,
                },
            )

        self.assertEqual(result, {"state_machine": {"leading_line": "军工"}})
        self.assertIs(contract_mock.call_args.kwargs["build_abnormal_projection_summary"], projection)
        self.assertIs(contract_mock.call_args.kwargs["build_market_style_switch_snapshot"], style_switch)
        self.assertIs(contract_mock.call_args.kwargs["build_market_state_machine_snapshot"], state_machine)
        self.assertIs(contract_mock.call_args.kwargs["build_mainline_rotation_snapshot"], rotation)
        self.assertIs(contract_mock.call_args.kwargs["build_abnormal_probe_group"], probe_group)
        self.assertIs(contract_mock.call_args.kwargs["build_special_probe_verdict"], probe_verdict)
        self.assertIs(contract_mock.call_args.kwargs["build_follow_verdict"], follow_verdict)
        self.assertIs(contract_mock.call_args.kwargs["build_dialectical_decision_snapshot"], dialectical)

    def test_build_dialectical_decision_snapshot_support_builds_stage_and_falsification_contract(self):
        support = self._load_module()

        result = support.build_dialectical_decision_snapshot(
            {
                "benchmark_change_pct": -0.3,
                "zt_count": 28,
                "dt_count": 3,
                "densest_sector_trend_count": 3,
                "resilient_abnormal_count": 2,
                "failed_abnormal_count": 1,
                "densest_sector": "军工",
                "rise_fall_ratio": 1.2,
                "rise_fall_ratio_text": "1.2:1",
            },
            {"style_label": "主线抱团", "primary_action": "只做最强方向"},
            {"state_code": "expand"},
            {"code": "follow", "label": "🟢 跟随主线"},
            {"can_new_entry": True},
            helpers={"_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value)},
        )

        self.assertEqual(result["stage_label"], "扩张确认")
        self.assertEqual(result["index_profit_relation"], "指数承压，但赚钱效应还在主线里")
        self.assertIn("军工", result["focus_label"])
        self.assertEqual(result["style_label"], "主线抱团")
        self.assertEqual(len(result["falsification_conditions"]), 4)

    def test_build_abnormal_projection_summary_support_summarizes_follow_state_mix(self):
        support = self._load_module()

        result = support.build_abnormal_projection_summary(
            [
                {"follow_state": "跌不下去", "setup_signal_label": "恐怖阴线异动"},
                {"follow_state": "缩量消化", "setup_signal_label": "长上影异动"},
                {"follow_state": "已经转弱", "setup_signal_label": "恐怖阴线异动"},
                {"follow_state": "已经转弱", "setup_signal_label": "长上影异动", "is_degraded_snapshot": True},
            ],
            helpers={
                "_split_abnormal_watch_pool": lambda pool: (
                    [item for item in pool if not item.get("is_degraded_snapshot")],
                    [item for item in pool if item.get("is_degraded_snapshot")],
                )
            },
        )

        self.assertEqual(result["projection_label"], "异常分化观察")
        self.assertEqual(result["resilient_count"], 2)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["degraded_count"], 1)
        self.assertEqual(result["setup_breakdown"][0][0], "恐怖阴线异动")

    def test_build_market_observation_snapshot_support_collects_breadth_and_counts(self):
        support = self._load_module()

        result = support.build_market_observation_snapshot(
            {
                "indices": {"上证指数": {"涨跌幅": 0.66}},
                "zt_pool": [{"code": "000001"}, {"code": "000002"}],
                "dt_pool": [{"code": "000003"}],
                "total_turnover": 12345.6,
            },
            main_sectors_info=[{"name": "军工"}],
            secondary_sectors_info=[{"name": "机器人"}],
            sector_trend_snapshot=[{"sector": "军工", "trend_count": 3}],
            abnormal_watch_pool=[
                {"follow_state": "跌不下去"},
                {"follow_state": "已经转弱"},
                {"follow_state": "缩量消化", "is_degraded_snapshot": True},
            ],
            leader_memory_bank=[{"code": "000001"}],
            tracking_memory_status={"today_validated_items": [{"code": "000001"}]},
            mainline_competition_snapshot=[{"sector": "军工", "role": "主攻线"}],
            helpers={
                "_split_abnormal_watch_pool": lambda pool: (
                    [item for item in pool if not item.get("is_degraded_snapshot")],
                    [item for item in pool if item.get("is_degraded_snapshot")],
                ),
                "_extract_market_breadth_snapshot": lambda data: {
                    "up_count": 3200,
                    "down_count": 1800,
                    "breadth_available": True,
                    "rise_fall_ratio": 1.7777,
                    "rise_fall_ratio_text": "1.78:1",
                },
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_round_or_none": lambda value, digits=4: round(float(value), digits) if value is not None else None,
            },
        )

        self.assertEqual(result["benchmark_change_pct"], 0.66)
        self.assertEqual(result["zt_count"], 2)
        self.assertEqual(result["dt_count"], 1)
        self.assertEqual(result["resilient_abnormal_count"], 1)
        self.assertEqual(result["failed_abnormal_count"], 1)
        self.assertEqual(result["degraded_abnormal_count"], 1)
        self.assertEqual(result["competition_focus"]["sector"], "军工")
        self.assertEqual(result["trusted_tracking_count"], 1)

    def test_build_follow_verdict_support_respects_reduce_only_and_probe_action(self):
        support = self._load_module()

        result = support.build_follow_verdict(
            {"can_new_entry": False, "should_reduce": True},
            "二档（防守档）",
            {"energy_state": "收缩防守", "execution_bias": "reduce_only"},
            {"action": "先处理异常对象"},
        )

        self.assertEqual(result["code"], "reduce_only")
        self.assertEqual(result["label"], "🟠 只处理旧仓")
        self.assertIn("先处理异常对象", result["action"])

    def test_build_mainline_competition_snapshot_support_builds_ranked_rows(self):
        support = self._load_module()

        result = support.build_mainline_competition_snapshot(
            main_sectors_info=[
                {"name": "军工", "inflow": 12.3, "change_pct": 4.2, "limit_up_count": 3},
                {"name": "机器人", "inflow": 3.1, "change_pct": 1.8},
            ],
            secondary_sectors_info=[{"name": "消费电子", "inflow": 2.2, "change_pct": 1.1}],
            sector_trend_snapshot=[
                {"sector": "军工", "trend_count": 3, "strong_count": 2},
                {"sector": "机器人", "trend_count": 2, "strong_count": 1},
                {"sector": "消费电子", "trend_count": 1, "strong_count": 1},
            ],
            risk_sectors=["地产"],
            helpers={
                "sector_name_matches": lambda left, right: left == right,
                "_normalize_flow_to_yi": lambda value: float(value or 0),
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            },
        )

        self.assertEqual(result[0]["role"], "主攻线")
        self.assertEqual(result[0]["sector"], "军工")
        self.assertIn("资金+12.3亿", result[0]["evidence"])
        self.assertEqual(result[1]["role"], "次强线")
        self.assertEqual(result[2]["role"], "竞争线")
        self.assertEqual(result[3]["role"], "回避线")

    def test_build_mainline_rotation_snapshot_support_summarizes_expand_state_and_ai_narrative(self):
        support = self._load_module()
        builder = getattr(support, "build_mainline_rotation_snapshot", None)
        self.assertIsNotNone(builder)

        result = builder(
            observation={
                "mainline_competition_snapshot": [
                    {"role": "主攻线", "sector": "军工"},
                    {"role": "次强线", "sector": "机器人"},
                    {"role": "竞争线", "sector": "商业航天"},
                ],
                "mainline_candidates": ["军工"],
                "secondary_candidates": ["机器人"],
                "densest_sector_trend_count": 4,
                "resilient_abnormal_count": 2,
                "failed_abnormal_count": 1,
            },
            state_machine={"leading_line": "军工", "state_code": "expand", "pulse_stage": "加速"},
            style_switch={"turnover_label": "放量", "turnover_state": "active", "style_reason": "主线继续收敛"},
            sector_ai_analysis={
                "relationships": {
                    "军工": {"standard_name": "军工装备", "parent": "高端制造", "related": ["卫星", "导弹"], "type": "核心节点"}
                },
                "mapping": {"军工": "军工装备"},
                "standard_sectors": ["军工装备"],
            },
            helpers={
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "sector_name_matches": lambda left, right: left == right,
            },
        )

        self.assertEqual(result["rotation_label"], "爆发")
        self.assertIn("主攻线军工", result["relay_text"])
        self.assertIn("趋势密度4只", result["summary_text"])
        self.assertIn("承接2强/1弱", result["summary_text"])
        self.assertEqual(result["narrative_label"], "军工装备节点")
        self.assertIn("上看高端制造", result["narrative_reason"])
        self.assertIn("相关环节卫星 / 导弹", result["narrative_reason"])

    def test_render_market_research_support_builds_renderer_payload(self):
        support = self._load_module()

        with patch(
            "research.market_research_support.render_market_research_snapshot_section_renderer",
            side_effect=lambda payload: payload,
        ):
            payload = support.render_market_research_snapshot_section(
                {
                    "observation": {
                        "benchmark_change_pct": 1.5,
                        "turnover": 12345,
                        "competition_focus": {"role": "主攻线", "sector": "军工", "evidence": "量能最强"},
                    },
                    "style_switch": {"style_label": "主线抱团", "style_reason": "主线强化", "evidence_text": "成交额集中"},
                    "state_machine": {"energy_state": "修复", "state_reason": "主线回流", "flow_direction": "向主线收敛"},
                    "abnormal_projection": {"projection_label": "承接强化", "projection_reason": "异常股跌不下去"},
                    "follow_verdict": {"label": "🟢 跟随主线", "reason": "主线清晰"},
                },
                compact=True,
                helpers={
                    "_build_mainline_rotation_snapshot": lambda **kwargs: {"rotation_label": "主线切换", "summary_text": "军工继续聚焦"},
                    "_build_dialectical_decision_snapshot": lambda **kwargs: {"stage_label": "主升", "stage_action": "继续跟随"},
                    "_safe_float": lambda value, default=0.0: float(value or default),
                },
            )

        self.assertEqual(payload["compact"], True)
        self.assertEqual(payload["competition_result"], "主攻线 军工")
        self.assertEqual(payload["competition_evidence"], "量能最强")
        self.assertEqual(payload["rotation_summary_text"], "军工继续聚焦")
        self.assertEqual(payload["state_energy"], "修复")
        self.assertEqual(payload["dialectical_decision"]["stage_label"], "主升")

    def test_build_market_research_context_bundle_support_passes_nested_support_helpers(self):
        support = self._load_module()

        helpers = {
            "get_active_a_kill_records": lambda target_date: [],
            "normalize_stock_code": lambda code: str(code or "").zfill(6),
            "safe_float": lambda value: float(value or 0),
            "is_stock_in_a_kill_cooldown": lambda candidate, records: (False, {}),
            "sector_name_matches": lambda sector, mainline_name: sector == mainline_name,
            "build_abnormal_watch_pool": lambda *args, **kwargs: [],
            "decision_strict_mode": False,
            "allow_display_degraded_abnormal_snapshot": True,
            "is_degraded_abnormal_snapshot": lambda item: False,
            "build_sector_trend_snapshot": lambda *args, **kwargs: [],
            "build_leader_memory_bank": lambda *args, **kwargs: [],
            "refresh_tracking_memory": lambda *args, **kwargs: {"today_validated_items": []},
            "discover_all_gem_breathing_candidates": lambda stock_meta_map, target_date="": [],
            "candidate_matches_mainline": lambda item, mainline_name: True,
            "build_gem_observation_pool": lambda candidates, target_date="": [],
            "build_mainline_competition_snapshot": lambda **kwargs: [],
            "build_market_observation_snapshot": lambda data, **kwargs: {},
            "_build_abnormal_projection_summary": lambda pool=None: {},
            "_build_market_style_switch_snapshot": lambda *args, **kwargs: {},
            "_build_market_state_machine_snapshot": lambda *args, **kwargs: {},
            "_build_mainline_rotation_snapshot": lambda **kwargs: {},
            "_build_abnormal_probe_group": lambda **kwargs: {},
            "_build_special_probe_verdict": lambda **kwargs: {},
            "_build_follow_verdict": lambda *args, **kwargs: {},
            "_build_dialectical_decision_snapshot": lambda **kwargs: {},
        }

        with patch(
            "research.market_research_support.build_market_research_context_bundle_contract",
            return_value={"market_state_snapshot": {"leading_line": "军工"}},
        ) as contract_mock:
            result = support.build_market_research_context_bundle(
                {},
                "2026-04-22",
                {"sector_name": "军工"},
                {"can_new_entry": True},
                "三档（进攻档）",
                helpers=helpers,
            )

        self.assertEqual(result, {"market_state_snapshot": {"leading_line": "军工"}})
        self.assertIs(contract_mock.call_args.kwargs["build_market_observation_snapshot"], helpers["build_market_observation_snapshot"])
        self.assertIs(contract_mock.call_args.kwargs["build_market_research_snapshot"], support.build_market_research_snapshot)
        self.assertIs(contract_mock.call_args.kwargs["derive_step0_follow_plan"], support.derive_step0_follow_plan)

    def test_build_market_research_context_bundle_support_accepts_render_mode_overrides(self):
        support = self._load_module()

        helpers = {
            "get_active_a_kill_records": lambda target_date: [],
            "normalize_stock_code": lambda code: str(code or "").zfill(6),
            "safe_float": lambda value: float(value or 0),
            "is_stock_in_a_kill_cooldown": lambda candidate, records: (False, {}),
            "sector_name_matches": lambda sector, mainline_name: sector == mainline_name,
            "build_abnormal_watch_pool": lambda *args, **kwargs: [],
            "decision_strict_mode": True,
            "allow_display_degraded_abnormal_snapshot": False,
            "is_degraded_abnormal_snapshot": lambda item: False,
            "build_sector_trend_snapshot": lambda *args, **kwargs: [],
            "build_leader_memory_bank": lambda *args, **kwargs: [],
            "refresh_tracking_memory": lambda *args, **kwargs: {"today_validated_items": []},
            "discover_all_gem_breathing_candidates": lambda stock_meta_map, target_date="": [],
            "candidate_matches_mainline": lambda item, mainline_name: True,
            "build_gem_observation_pool": lambda candidates, target_date="": [],
            "build_mainline_competition_snapshot": lambda **kwargs: [],
            "build_market_observation_snapshot": lambda data, **kwargs: {},
            "_build_abnormal_projection_summary": lambda pool=None: {},
            "_build_market_style_switch_snapshot": lambda *args, **kwargs: {},
            "_build_market_state_machine_snapshot": lambda *args, **kwargs: {},
            "_build_mainline_rotation_snapshot": lambda **kwargs: {},
            "_build_abnormal_probe_group": lambda **kwargs: {},
            "_build_special_probe_verdict": lambda **kwargs: {},
            "_build_follow_verdict": lambda *args, **kwargs: {},
            "_build_dialectical_decision_snapshot": lambda **kwargs: {},
        }

        with patch(
            "research.market_research_support.build_market_research_context_bundle_contract",
            return_value={"market_state_snapshot": {"leading_line": "军工"}},
        ) as contract_mock:
            support.build_market_research_context_bundle(
                {},
                "2026-04-22",
                {"sector_name": "军工"},
                {"can_new_entry": True},
                "三档（进攻档）",
                decision_strict_mode=False,
                allow_display_degraded_abnormal_snapshot=True,
                helpers=helpers,
            )

        self.assertEqual(contract_mock.call_args.kwargs["decision_strict_mode"], False)
        self.assertEqual(contract_mock.call_args.kwargs["allow_display_degraded_abnormal_snapshot"], True)


if __name__ == "__main__":
    unittest.main()
