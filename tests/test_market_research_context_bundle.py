import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research.market_research_context_bundle import build_market_research_context_bundle_contract


class MarketResearchContextBundleTest(unittest.TestCase):
    def test_build_market_research_context_bundle_contract_filters_and_builds_snapshots(self):
        result = build_market_research_context_bundle_contract(
            data={
                "zt_pool_by_sector": {"军工": [{"代码": "000001"}]},
                "dt_pool_by_sector": {},
                "zt_pool": [
                    {
                        "代码": "000001",
                        "名称": "军工一号",
                        "所属行业": "军工",
                        "涨跌幅": 10.0,
                        "开盘价": 10.0,
                        "最新价": 10.0,
                        "最高价": 10.0,
                        "最低价": 10.0,
                        "成交额": 600000000,
                    },
                    {
                        "代码": "000002",
                        "名称": "冷却对象",
                        "所属行业": "机器人",
                        "涨跌幅": 9.9,
                        "开盘价": 8.0,
                        "最新价": 8.8,
                        "最高价": 8.8,
                        "最低价": 8.0,
                        "成交额": 200000000,
                    },
                ],
                "hot_rank_top30": [{"code": "000003", "name": "热股一号", "sector": "军工", "change": 6.8}],
                "integrated_hot_list": [{"code": "000004", "name": "综合热股", "sector_tags": ["军工"]}],
                "stocks_with_history": [{"code": "000005", "name": "记忆股", "sector": "军工"}],
                "turnover_rank": [],
                "volume_anomalies": [{"stock_code": "000006", "stock_name": "异常股"}],
            },
            target_date="2026-04-22",
            exit_analysis={"sector_name": "军工", "risk_sectors": ["地产"]},
            final_gate={"can_new_entry": True},
            position_level="三档（进攻档）",
            get_active_a_kill_records=lambda target_date: [{"code": "000002"}],
            normalize_stock_code=lambda code: str(code).zfill(6) if code else "",
            safe_float=lambda value: float(value or 0),
            is_stock_in_a_kill_cooldown=lambda candidate, records: (
                candidate.get("code") == "000002",
                {"reason": "冷却"} if candidate.get("code") == "000002" else {},
            ),
            sector_name_matches=lambda sector, mainline_name: sector == mainline_name,
            build_abnormal_watch_pool=lambda *args, **kwargs: [
                {"code": "000001", "name": "军工一号", "follow_state": "承接"},
                {"code": "000006", "name": "异常股", "follow_state": "转弱", "is_degraded_snapshot": True},
            ],
            decision_strict_mode=False,
            allow_display_degraded_abnormal_snapshot=True,
            is_degraded_abnormal_snapshot=lambda item: bool((item or {}).get("is_degraded_snapshot")),
            build_sector_trend_snapshot=lambda *args, **kwargs: [{"sector": "军工", "trend_count": 2}],
            build_leader_memory_bank=lambda *args, **kwargs: [
                {"code": "000005", "name": "记忆股", "sector": "军工", "remember_score": 60, "remember_reason": "旧龙头"}
            ],
            refresh_tracking_memory=lambda *args, **kwargs: {"today_validated_items": [{"code": "000005"}]},
            discover_all_gem_breathing_candidates=lambda stock_meta_map, target_date="": [
                {"code": "300001", "name": "创业观察", "sector": "军工", "tier": "T1", "note": "有预热"},
                {"code": "300002", "name": "非主线创业", "sector": "机器人", "tier": "T2", "note": "偏离主线"},
            ],
            candidate_matches_mainline=lambda item, mainline_name: item.get("sector") == mainline_name,
            build_gem_observation_pool=lambda candidates, target_date="": [
                {"code": item.get("code"), "name": item.get("name")}
                for item in candidates
            ],
            build_mainline_competition_snapshot=lambda **kwargs: [{"sector": "军工", "role": "主攻线"}],
            build_market_observation_snapshot=lambda data, **kwargs: {
                "mainline_candidates": ["军工"],
                "abnormal_watch_pool": kwargs.get("abnormal_watch_pool", []),
                "leader_memory_bank": kwargs.get("leader_memory_bank", []),
                "sector_trend_snapshot": kwargs.get("sector_trend_snapshot", []),
            },
            build_market_research_snapshot=lambda data, final_gate, position_level, exit_analysis, observation_snapshot=None, target_date="": {
                "state_machine": {"leading_line": "军工"},
                "abnormal_projection": {"projection_label": "强化"},
                "observation": observation_snapshot or {},
            },
            derive_step0_follow_plan=lambda market_research_snapshot, final_gate, position_level: {
                "step0_prediction_cn": "🟢 跟随主线"
            },
        )

        self.assertEqual([item["code"] for item in result["watchlist"]], ["000001", "000003"])
        self.assertEqual(len(result["filtered_by_a_kill"]), 1)
        self.assertIn("000001", result["abnormal_watch_map"])
        self.assertNotIn("000006", result["abnormal_watch_map"])
        self.assertEqual(result["leader_memory_bank"][0]["remember_score"], 70.0)
        self.assertEqual(len(result["gem_breathing_candidates"]), 0)
        self.assertEqual(len(result["filtered_out_gem_breathing_candidates"]), 0)
        self.assertEqual(len(result["gem_observation_stocks"]), 0)
        self.assertEqual(result["market_state_snapshot"]["leading_line"], "军工")
        self.assertEqual(result["step0_plan"]["step0_prediction_cn"], "🟢 跟随主线")
        self.assertTrue(any(log["step"] == "build.market_snapshot" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "build.gem_breathing" and log["status"] == "skipped" for log in result["module_logs"]))

    def test_build_market_research_context_bundle_contract_skips_gem_discovery_in_display_safe_mode(self):
        result = build_market_research_context_bundle_contract(
            data={
                "zt_pool_by_sector": {},
                "dt_pool_by_sector": {},
                "zt_pool": [],
                "hot_rank_top30": [],
                "integrated_hot_list": [],
                "stocks_with_history": [],
                "turnover_rank": [],
                "volume_anomalies": [],
            },
            target_date="2026-04-22",
            exit_analysis={"sector_name": "军工", "risk_sectors": []},
            final_gate={"can_new_entry": True},
            position_level="三档（进攻档）",
            get_active_a_kill_records=lambda target_date: [],
            normalize_stock_code=lambda code: str(code or "").zfill(6),
            safe_float=lambda value: float(value or 0),
            is_stock_in_a_kill_cooldown=lambda candidate, records: (False, {}),
            sector_name_matches=lambda sector, mainline_name: sector == mainline_name,
            build_abnormal_watch_pool=lambda *args, **kwargs: [],
            decision_strict_mode=False,
            allow_display_degraded_abnormal_snapshot=True,
            is_degraded_abnormal_snapshot=lambda item: False,
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_leader_memory_bank=lambda *args, **kwargs: [],
            refresh_tracking_memory=lambda *args, **kwargs: {"today_validated_items": []},
            discover_all_gem_breathing_candidates=lambda stock_meta_map, target_date="": (_ for _ in ()).throw(AssertionError("display-safe render should not fetch gem breathing candidates")),
            candidate_matches_mainline=lambda item, mainline_name: True,
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_mainline_competition_snapshot=lambda **kwargs: [],
            build_market_observation_snapshot=lambda data, **kwargs: {},
            build_market_research_snapshot=lambda data, final_gate, position_level, exit_analysis, observation_snapshot=None, target_date="": {
                "state_machine": {"leading_line": "军工"},
                "abnormal_projection": {"projection_label": "强化"},
                "observation": observation_snapshot or {},
            },
            derive_step0_follow_plan=lambda market_research_snapshot, final_gate, position_level: {
                "step0_prediction_cn": "🟢 跟随主线"
            },
        )

        self.assertEqual(result["gem_breathing_candidates"], [])
        self.assertEqual(result["filtered_out_gem_breathing_candidates"], [])
        self.assertEqual(result["gem_observation_stocks"], [])

    def test_build_market_research_context_bundle_uses_stock_full_info_for_t_board_pattern(self):
        result = build_market_research_context_bundle_contract(
            data={
                "zt_pool_by_sector": {"半导体": [{"代码": "300613"}]},
                "dt_pool_by_sector": {},
                "zt_pool": [
                    {
                        "代码": "300613",
                        "名称": "富瀚微",
                        "所属行业": "半导体",
                        "涨跌幅": 20.01,
                        "最新价": 56.08,
                        "成交额": 1471516672,
                    }
                ],
                "stock_full_info": {
                    "300613": {
                        "open": 55.90,
                        "high": 56.08,
                        "low": 54.21,
                        "close": 56.08,
                        "change_pct": 20.01,
                    }
                },
                "hot_rank_top30": [],
                "integrated_hot_list": [],
                "stocks_with_history": [],
                "turnover_rank": [],
                "volume_anomalies": [{"stock_code": "300613", "reason": "显著放量6.0倍"}],
            },
            target_date="2026-04-24",
            exit_analysis={"sector_name": "半导体", "risk_sectors": []},
            final_gate={"can_new_entry": False},
            position_level="一档",
            get_active_a_kill_records=lambda target_date: [],
            normalize_stock_code=lambda code: str(code or "").zfill(6),
            safe_float=lambda value: float(value or 0),
            is_stock_in_a_kill_cooldown=lambda candidate, records: (False, {}),
            sector_name_matches=lambda sector, mainline_name: sector == mainline_name,
            build_abnormal_watch_pool=lambda *args, **kwargs: [],
            decision_strict_mode=False,
            allow_display_degraded_abnormal_snapshot=True,
            is_degraded_abnormal_snapshot=lambda item: False,
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_leader_memory_bank=lambda *args, **kwargs: [],
            refresh_tracking_memory=lambda *args, **kwargs: {"today_validated_items": []},
            discover_all_gem_breathing_candidates=lambda stock_meta_map, target_date="": [],
            candidate_matches_mainline=lambda item, mainline_name: True,
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_mainline_competition_snapshot=lambda **kwargs: [],
            build_market_observation_snapshot=lambda data, **kwargs: {},
            build_market_research_snapshot=lambda data, final_gate, position_level, exit_analysis, observation_snapshot=None, target_date="": {
                "state_machine": {},
                "abnormal_projection": {},
            },
            derive_step0_follow_plan=lambda market_research_snapshot, final_gate, position_level: {},
        )

        self.assertEqual(result["watchlist"][0]["pattern"], "放量T字板")
        self.assertIn("T字板分歧转一致", result["watchlist"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
