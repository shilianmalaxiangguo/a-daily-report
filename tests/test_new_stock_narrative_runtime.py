import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.new_stock_narrative_runtime import (
    build_new_stock_research_pool,
    score_new_stock_narrative,
    should_upgrade_new_stock_candidate,
)


class NewStockNarrativeRuntimeTest(unittest.TestCase):
    def _liqi_context(self):
        return {
            "mainline_name": "电池",
            "potential_mainline": ["锂电池", "新能源"],
            "new_stock_money_making_effect": "strong",
            "new_stock_profiles": {
                "301608": {
                    "sector": "电池",
                    "industry": "锂电池设备",
                    "concept_tags": ["锂电池", "新能源"],
                    "customer_anchors": ["宁德时代", "比亚迪"],
                    "supply_chain_role": "锂电池设备/材料链",
                    "domestic_advantage": "国产制造和成本优势",
                }
            },
        }

    def test_build_pool_enriches_liqi_style_sample_and_upgrades_it(self):
        calendar = [
            {
                "code": "301608",
                "name": "N理奇智能",
                "listing_date": "2026-04-30",
                "issue_price": 20.0,
                "fundraising_yi": 2.944,
                "direct_execution_permission": True,
                "source": "sina_new_stock_calendar",
                "source_status": "success",
            }
        ]

        result = build_new_stock_research_pool(
            calendar,
            target_date="2026-04-29",
            context=self._liqi_context(),
        )

        self.assertIn("new_stock_research_pool", result)
        self.assertIn("new_stock_candidate_upgrades", result)
        self.assertEqual(len(result["new_stock_research_pool"]), 1)

        item = result["new_stock_research_pool"][0]
        self.assertEqual(item["sector"], "电池")
        self.assertEqual(item["listing_window"], "tomorrow_listing")
        self.assertEqual(item["pre_listing_action"], "focus_tomorrow_battle")
        self.assertGreaterEqual(item["new_stock_narrative_score"], 72)
        self.assertTrue(item["upgrade_eligible"])
        self.assertIn("明天可战新股", item["candidate_upgrade_reason"])
        self.assertNotIn("direct_execution_permission", item)

        factors = item["new_stock_factors"]
        self.assertGreaterEqual(factors["mainline_match_score"], 20)
        self.assertGreaterEqual(factors["narrative_association_score"], 18)
        self.assertGreater(factors["market_emotion_score"], 0)
        self.assertGreater(factors["board_resonance_score"], 0)

        upgrades = result["new_stock_candidate_upgrades"]
        self.assertEqual(len(upgrades), 1)
        upgrade = upgrades[0]
        self.assertEqual(upgrade["code"], "301608")
        self.assertEqual(upgrade["name"], "N理奇智能")
        self.assertEqual(upgrade["_source"], "新股研究池")
        self.assertEqual(upgrade["watch_source"], "new_stock_research_pool")
        self.assertEqual(upgrade["core_level"], "新股预期差候选")
        self.assertEqual(upgrade["listing_window"], "tomorrow_listing")
        self.assertEqual(upgrade["pre_listing_action"], "focus_tomorrow_battle")
        self.assertNotIn("direct_execution_permission", upgrade)

    def test_t2_strong_sample_prepares_cash_without_buy_language(self):
        calendar = [
            {
                "code": "001365",
                "name": "天海电子",
                "listing_date": "2026-05-02",
                "issue_price": 18.0,
                "fundraising_yi": 2.1,
                "source": "sina_new_stock_calendar",
                "source_status": "success",
            }
        ]
        context = {
            "mainline_name": "汽车零部件",
            "new_stock_money_making_effect": {"status": "strong"},
            "new_stock_profiles": {
                "001365": {
                    "sector": "汽车零部件",
                    "industry": "车载电子",
                    "concept_tags": ["智能座舱", "汽车电子"],
                    "customer_anchors": ["比亚迪"],
                    "supply_chain_role": "整车配套链",
                    "domestic_advantage": "国产替代和供应链效率",
                }
            },
        }

        result = build_new_stock_research_pool(
            calendar,
            target_date="2026-04-30",
            context=context,
        )

        item = result["new_stock_research_pool"][0]
        self.assertEqual(item["listing_window"], "pre_alert_t2")
        self.assertEqual(item["pre_listing_action"], "prepare_clear_cash")
        self.assertTrue(item["upgrade_eligible"])
        self.assertEqual(len(result["new_stock_candidate_upgrades"]), 1)
        self.assertIn("准备清仓", item["candidate_upgrade_reason"])
        self.assertIn("减仓", item["candidate_upgrade_reason"])
        self.assertIn("现金", item["candidate_upgrade_reason"])
        self.assertNotIn("买入", item["candidate_upgrade_reason"])

    def test_weak_non_mainline_sample_stays_research_only(self):
        calendar = [
            {
                "code": "688888",
                "name": "云海科技",
                "listing_date": "2026-05-02",
                "issue_price": 48.0,
                "fundraising_yi": 18.0,
                "source": "sina_new_stock_calendar",
                "source_status": "success",
            }
        ]
        context = {
            "mainline_name": "机器人",
            "new_stock_money_making_effect": "neutral",
            "new_stock_profiles": {
                "688888": {
                    "sector": "医药",
                    "industry": "医疗器械",
                    "concept_tags": ["医疗服务"],
                    "customer_anchors": ["医院客户"],
                    "supply_chain_role": "通用配套",
                    "domestic_advantage": "本地制造",
                }
            },
        }

        result = build_new_stock_research_pool(
            calendar,
            target_date="2026-05-01",
            context=context,
        )

        item = result["new_stock_research_pool"][0]
        self.assertLess(item["new_stock_factors"]["mainline_match_score"], 20)
        self.assertFalse(item["upgrade_eligible"])
        self.assertEqual(result["new_stock_candidate_upgrades"], [])
        self.assertEqual(should_upgrade_new_stock_candidate(item), False)

    def test_factor_fields_are_present_and_explain_the_score(self):
        record = {
            "code": "301608",
            "name": "N理奇智能",
            "listing_date": "2026-04-30",
            "issue_price": 20.0,
            "fundraising_yi": 2.944,
            "source": "sina_new_stock_calendar",
            "source_status": "success",
        }

        scored = score_new_stock_narrative(
            record,
            context=self._liqi_context(),
            target_date="2026-04-29",
        )

        factors = scored["new_stock_factors"]
        expected_keys = {
            "listing_window_score",
            "mainline_match_score",
            "narrative_association_score",
            "market_emotion_score",
            "board_resonance_score",
            "trade_value_score",
        }
        self.assertTrue(expected_keys.issubset(factors.keys()))
        self.assertEqual(scored["new_stock_narrative_score"], sum(factors[key] for key in expected_keys))
        self.assertTrue(scored["upgrade_eligible"])
        self.assertIn("listing_window", scored)
        self.assertIn("candidate_upgrade_reason", scored)


if __name__ == "__main__":
    unittest.main()
