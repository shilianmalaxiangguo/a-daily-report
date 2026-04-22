import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.contracts import build_market_state_action_map
from domains.market_state.nodes.infer_environment_signal import run as run_environment_signal
from domains.market_state.nodes.infer_mainline_candidates import run as run_mainline_candidates
from domains.market_state.nodes.infer_mainline_continuity import run as run_mainline_continuity


class MarketStateNodesTest(unittest.TestCase):
    def test_infer_mainline_candidates_selects_tracked_sector_and_snapshot(self):
        result = run_mainline_candidates(
            {
                "inputs": {
                    "data": {
                        "sector_fund_flow": {
                            "inflow": [{"name": "军工", "zljlr": 12.5}],
                            "outflow": [{"name": "地产", "zljlr": -8.1}],
                        },
                        "zt_pool_by_sector": {"军工": [{"name": "A"}, {"name": "B"}]},
                        "dt_pool_by_sector": {"军工": []},
                        "tag_distribution": {},
                        "target_date": "2026-04-22",
                    },
                    "market_analysis": {"main_sectors": [{"name": "军工"}]},
                    "enhanced_main_sectors": [],
                },
                "helpers": {
                    "get_sector_hotlist_weight": lambda sector, tags: 7.5,
                    "load_recent_sector_flow_history": lambda target_date, sector, lookback_days=2: [{"inflow": 10.0}],
                    "get_mainline_star_level": lambda inflow, zt_count, dt_count=0, hot_weight=0, inflow_history=None: {
                        "star_level": "⭐⭐⭐⭐",
                        "star_rank": 4,
                        "score_pct": 82.0,
                        "flow_trend": "stable",
                        "trend_label": "主升延续",
                        "component_scores": {"资金": 85.0},
                    },
                    "safe_float": float,
                },
            }
        )

        exports = result["exports"]
        self.assertEqual(exports["tracked_sector"], "军工")
        self.assertEqual(exports["sector_inflow"], 12.5)
        self.assertEqual(exports["sector_zt_count"], 2)
        self.assertEqual(exports["mainline_snapshot"]["star_rank"], 4)

    def test_infer_environment_signal_generates_mainline_review_signal(self):
        result = run_environment_signal(
            {
                "state": {
                    "tracked_sector": "军工",
                    "sector_inflow": 12.5,
                    "sector_outflow": 0,
                    "sector_zt_count": 2,
                    "sector_dt_count": 0,
                    "hot_weight": 7.5,
                    "mainline_snapshot": {
                        "score_pct": 82.0,
                        "flow_trend": "stable",
                        "trend_label": "主升延续",
                    },
                },
                "helpers": {
                    "action_map": build_market_state_action_map(),
                    "score_to_level": lambda score: "绿灯" if score >= 70 else "黄灯",
                },
            }
        )

        signal = result["exports"]["environment_signal"]
        self.assertEqual(signal["layer"], "主线地位复核")
        self.assertEqual(signal["level"], "绿灯")
        self.assertIn("军工", signal["status"])

    def test_infer_mainline_continuity_generates_leader_structure_and_core_signals(self):
        result = run_mainline_continuity(
            {
                "inputs": {
                    "data": {
                        "lhb_net_sell_top10": [],
                        "stock_full_info": {"000001": {"open": 10.0, "high": 10.8, "low": 9.8, "close": 10.5}},
                        "hot_rank_top30": [{"name": "军工一号", "code": "000001"}],
                        "target_date": "2026-04-22",
                    }
                },
                "state": {
                    "tracked_sector": "军工",
                    "sector_zt_count": 6,
                    "sector_dt_count": 0,
                    "hot_weight": 8.0,
                },
                "helpers": {
                    "action_map": build_market_state_action_map(),
                    "get_sector_leader": lambda tracked_sector, dragon_stocks, dt_pool_by_sector: {
                        "name": "军工一号",
                        "code": "000001",
                        "zt_type": "换手板",
                        "lianban": 3,
                        "is_limit_down": False,
                    },
                    "get_sector_core_hot_stock": lambda tracked_sector, hot_rank_top30: {
                        "name": "军工一号",
                        "code": "000001",
                        "hot_rank": 4,
                        "change_pct": 5.2,
                    },
                    "normalize_stock_code": lambda code: code,
                    "calculate_exit_price_lines": lambda price_anchor_stock, stock_full_info: {"anchor_name": "军工一号"},
                    "fetch_recent_price_bars": lambda code, target_date, lookback_days=13: [{"low": 9.5}],
                    "compute_stop_loss_mainline_anchor": lambda recent_bars: (9.5, "2026-04-18", "最近前低"),
                    "safe_float": float,
                    "clamp": lambda value, lower, upper: max(lower, min(value, upper)),
                    "level_to_score": lambda level: {"绿灯": 85.0, "黄灯": 65.0, "橙灯": 35.0, "红灯": 10.0}[level],
                },
            }
        )

        exports = result["exports"]
        self.assertEqual(exports["leader_signal"]["level"], "绿灯")
        self.assertEqual(exports["structure_signal"]["level"], "黄灯")
        self.assertEqual(exports["core_signal"]["level"], "绿灯")


if __name__ == "__main__":
    unittest.main()
