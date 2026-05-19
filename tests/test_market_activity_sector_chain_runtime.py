import sys
import types
import unittest
import io
from contextlib import redirect_stdout
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

    def test_ai_analyze_sector_relationships_uses_local_chain_by_default_without_remote_service(self):
        class ExplodingClient:
            def analyze_sector_relationships(self, sector_list, context_info=""):
                raise AssertionError("DeepSeek should not be called by default")

        result = ai_analyze_sector_relationships(
            ["光模块", "CPO", "医药流通"],
            "测试上下文",
            helpers={
                "ENABLE_REMOTE_SECTOR_LLM": False,
                "get_llm_service": lambda: ExplodingClient(),
            },
        )

        self.assertEqual(result["groups"][0]["name"], "光通信")
        self.assertIn("医药医疗", [group["name"] for group in result["groups"]])
        self.assertNotIn("LLM分析失败", result["insights"])

    def test_ai_analyze_sector_relationships_groups_common_a_share_tags_into_chains(self):
        result = ai_analyze_sector_relationships(
            [
                "HBM",
                "光刻机",
                "光刻胶",
                "EDA",
                "大基金系",
                "摩尔线程概念",
                "工业互联网",
                "物联网",
                "电子身份证",
                "人脸识别",
                "超高清视频",
                "空间计算",
                "电信运营",
                "苹果产业链",
                "无线耳机",
                "LED",
                "家电",
                "高速连接器",
                "新型工业化",
                "机器视觉",
                "上海国资",
                "浙江国资",
                "新疆国资",
                "振兴东北",
                "水泥",
                "家居装饰",
                "陶瓷产业",
                "检测检验",
                "氟化工",
                "工业气体",
                "航海装备",
                "一体化压铸",
                "休闲食品",
                "代糖/甜味剂",
                "出海概念",
                "冰雪产业",
                "碳中和",
            ],
            helpers={"ENABLE_REMOTE_SECTOR_LLM": False},
        )

        groups = {group["name"]: group for group in result["groups"]}
        self.assertEqual(
            groups["半导体"]["sectors"],
            ["HBM", "光刻机", "光刻胶", "EDA", "大基金系", "摩尔线程概念"],
        )
        self.assertEqual(
            groups["数字经济"]["sectors"],
            ["工业互联网", "物联网", "电子身份证", "人脸识别", "超高清视频", "空间计算", "电信运营"],
        )
        self.assertEqual(groups["AI算力"]["sectors"], ["高速连接器"])
        self.assertEqual(groups["高端制造"]["sectors"], ["新型工业化", "机器视觉"])
        self.assertEqual(groups["消费电子"]["sectors"], ["苹果产业链", "无线耳机", "LED", "家电"])
        self.assertEqual(groups["区域国资"]["sectors"], ["上海国资", "浙江国资", "新疆国资", "振兴东北"])
        self.assertEqual(groups["地产基建"]["sectors"], ["水泥", "家居装饰", "陶瓷产业", "检测检验"])
        self.assertEqual(groups["化工材料"]["sectors"], ["氟化工", "工业气体"])
        self.assertEqual(groups["军工装备"]["sectors"], ["航海装备"])
        self.assertEqual(groups["汽车产业链"]["sectors"], ["一体化压铸"])
        self.assertEqual(groups["食品饮料"]["sectors"], ["休闲食品", "代糖/甜味剂"])
        self.assertEqual(groups["出海链"]["sectors"], ["出海概念"])
        self.assertEqual(groups["文旅消费"]["sectors"], ["冰雪产业"])
        self.assertEqual(groups["新能源"]["sectors"], ["碳中和"])
        for group in result["groups"]:
            self.assertNotEqual(group["reason"], "独立板块，暂无明确产业链关联")

    def test_ai_analyze_sector_relationships_remote_failure_falls_back_to_local_chain_without_failure_text(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = ai_analyze_sector_relationships(
                ["光模块", "CPO"],
                "测试上下文",
                helpers={
                    "ENABLE_REMOTE_SECTOR_LLM": True,
                    "get_llm_service": lambda: types.SimpleNamespace(
                        analyze_sector_relationships=lambda *args, **kwargs: (_ for _ in ()).throw(
                            RuntimeError("deepseek timeout")
                        )
                    ),
                },
            )

        self.assertEqual(result["groups"][0]["name"], "光通信")
        self.assertNotIn("LLM分析失败", result["insights"])
        self.assertIn("远程增强失败", buffer.getvalue())
        self.assertIn("使用本地归链", buffer.getvalue())

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
                "ENABLE_REMOTE_SECTOR_LLM": True,
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
                "ENABLE_REMOTE_SECTOR_LLM": True,
                "_llm_call_stats": stats,
                "get_llm_service": lambda: types.SimpleNamespace(
                    analyze_sector_relationships=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
                ),
            },
        )

        self.assertEqual(success["groups"][0]["name"], "军工链")
        self.assertEqual(stats["total_calls"], 1)
        self.assertEqual(stats["sector_analysis_calls"], 1)
        self.assertEqual(failure["groups"][0]["name"], "军工装备")
        self.assertNotIn("LLM分析失败", failure["insights"])


if __name__ == "__main__":
    unittest.main()
