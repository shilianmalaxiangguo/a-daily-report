import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_activity.sector_chain_runtime import (
    ai_analyze_sector_relationships,
    ai_group_concepts_into_chains,
)


class MarketActivitySectorChainRuntimeTest(unittest.TestCase):
    def test_ai_group_concepts_into_chains_uses_local_chain_fallback_in_mvp_mode(self):
        chains = ai_group_concepts_into_chains(
            ["商业航天", "卫星导航", "绿色电力"],
            helpers={"DISPLAY_MVP_MODE": True},
        )

        self.assertEqual(chains["商业航天"], ["商业航天", "卫星导航"])
        self.assertEqual(chains["新能源"], ["绿色电力"])

    def test_ai_group_concepts_into_chains_falls_back_when_llm_groups_empty(self):
        chains = ai_group_concepts_into_chains(
            ["光模块", "CPO", "医药流通"],
            helpers={
                "DISPLAY_MVP_MODE": False,
                "ai_analyze_sector_relationships": lambda sectors, context_info="": {"groups": [], "insights": ""},
            },
        )

        self.assertEqual(chains["光通信"], ["光模块", "CPO"])
        self.assertEqual(chains["医药医疗"], ["医药流通"])

    def test_ai_analyze_sector_relationships_updates_stats_and_handles_failure(self):
        stats = {
            "total_calls": 0,
            "total_time": 0.0,
            "event_analysis_calls": 0,
            "event_analysis_time": 0.0,
            "sector_analysis_calls": 0,
            "sector_analysis_time": 0.0,
        }

        success = ai_analyze_sector_relationships(
            ["军工", "航空"],
            "测试上下文",
            helpers={
                "_llm_call_stats": stats,
                "get_llm_service": lambda: types.SimpleNamespace(
                    analyze_sector_relationships=lambda sector_list, context_info="": {
                        "groups": [{"name": "军工链", "sectors": sector_list}],
                        "insights": "聚焦军工",
                    }
                ),
            },
        )
        failure = ai_analyze_sector_relationships(
            ["军工"],
            helpers={
                "_llm_call_stats": stats,
                "get_llm_service": lambda: types.SimpleNamespace(
                    analyze_sector_relationships=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
                ),
            },
        )

        self.assertEqual(success["groups"][0]["name"], "军工链")
        self.assertEqual(stats["total_calls"], 1)
        self.assertEqual(stats["sector_analysis_calls"], 1)
        self.assertEqual(failure["groups"], [])
        self.assertIn("LLM分析失败", failure["insights"])


if __name__ == "__main__":
    unittest.main()
