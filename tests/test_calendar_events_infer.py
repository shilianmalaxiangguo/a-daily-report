import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.calendar_events.infer import ai_analyze_event_sectors, analyze_event_sector, minimal_fallback_analysis


class CalendarEventsInferTest(unittest.TestCase):
    def test_minimal_fallback_analysis_recognizes_robot_theme(self):
        result = minimal_fallback_analysis("具身智能机器人大会开幕")
        self.assertEqual(result["main_direction"], "人形机器人")
        self.assertIn("减速器", result["related_sectors"])

    def test_minimal_fallback_analysis_uses_concrete_bucket_instead_of_other(self):
        result = minimal_fallback_analysis("未知行业政策发布")

        self.assertEqual(result["main_direction"], "政策催化")
        self.assertNotIn("其他", result["related_sectors"])
        self.assertIn("政策催化", result["related_sectors"])

    def test_minimal_fallback_analysis_splits_calendar_events_by_theme_not_generic_policy(self):
        samples = {
            "2026年谷歌开发者大会（Google I/O 2026）将于5月19日至20日举办": "AI应用",
            "联想：天禧AI将于5月19日发布4.0大版本，核心升级为天禧Claw": "AI终端",
            "AMD AI开发者日2026将于5月19日在上海举办": "AI算力",
            "金蝶AI峰会2026AI技术论坛将于5月20日举办": "AI应用",
            "2026世界无人机大会5月21日至23日在深圳举行": "低空经济",
            "小米汽车发文，小米YU7 GT将于5月21日正式上市": "汽车产业链",
            "第十届集微半导体大会定于5月27日至29日在张江举行": "半导体",
            "今日有5亿元7天期逆回购到期": "金融流动性",
            "2026年美国临床肿瘤学会年会是美国临床肿瘤学会（ASCO）将于5月29日至6月2日举办": "医药医疗",
            "SpaceX最早将于6月11日确定首次公开发行价格，股票将于6月12日上市": "商业航天",
            "2026年世界杯将于6月11日至7月19日举行": "文旅体育",
            "5月23日，东北地区城市足球联赛（以下简称“东北超”）将在沈阳铁西体育场拉开帷幕": "文旅体育",
            "深圳天微电子：自5月20日起，公司全系列产品价格上调10-30%": "电子元器件",
            "第四届中国能源周——绿色燃料未来论坛将于5月21日举办": "新能源",
            "2026第三届成渝地区（成都）汽车产业链生态合作大会将于5月21日启幕": "汽车产业链",
            "国内成品油将开启新一轮调价窗口": "原油",
            "美团：董事会定于6月1日举行会议并公布2026年第一季度的未经审核财务业绩": "本地生活",
            "台北电脑展（Computex 2026）将于6月2日至5日举行": "消费电子",
            "2026年圣彼得堡国际经济论坛定于6月3日至6日举行": "宏观经济",
            "LME将铅和锌直接合约单日涨跌幅限制从15%下调至12%，新规将于6月8日起生效": "有色金属",
            "IEA公布月度原油市场报告": "原油",
            "中汽协官微：组委会拟定于6月18日至22日举办“2026国际汽车及供应链博览会（香港）”": "汽车产业链",
            "美联储FOMC公布利率决议和经济预期摘要": "金融流动性",
        }

        for title, expected_direction in samples.items():
            with self.subTest(title=title):
                result = minimal_fallback_analysis(title)
                self.assertEqual(result["main_direction"], expected_direction)

    def test_minimal_fallback_analysis_does_not_hide_specific_events_under_policy_catalyst(self):
        titles = [
            "金蝶AI峰会2026AI技术论坛将于5月20日举办",
            "2026年世界杯将于6月11日至7月19日举行",
            "小米汽车发文，小米YU7 GT将于5月21日正式上市",
            "第四届中国能源周——绿色燃料未来论坛将于5月21日举办",
            "2026第三届成渝地区（成都）汽车产业链生态合作大会将于5月21日启幕",
            "国内成品油将开启新一轮调价窗口",
            "台北电脑展（Computex 2026）将于6月2日至5日举行",
            "LME将铅和锌直接合约单日涨跌幅限制从15%下调至12%，新规将于6月8日起生效",
        ]

        for title in titles:
            with self.subTest(title=title):
                result = minimal_fallback_analysis(title)
                self.assertNotEqual(result["main_direction"], "政策催化")
                self.assertNotIn("政策催化", result["related_sectors"])

    def test_normalization_replaces_generic_policy_with_title_semantics(self):
        result = minimal_fallback_analysis("台北电脑展（Computex 2026）将于6月2日至5日举行")
        self.assertEqual(result["main_direction"], "消费电子")

        normalized = ai_analyze_event_sectors(
            "台北电脑展（Computex 2026）将于6月2日至5日举行",
            helpers={
                "_default_get_llm_service": lambda: type(
                    "PolicyClient",
                    (),
                    {
                        "analyze_event_sectors": lambda self, event_title, event_summary="": {
                            "main_direction": "政策催化",
                            "related_sectors": ["政策催化"],
                            "trading_logic": "按会议事件处理",
                            "expectation": "中性",
                            "confidence": "低",
                        }
                    },
                )(),
                "ENABLE_REMOTE_CALENDAR_LLM": True,
            },
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(normalized["main_direction"], "消费电子")
        self.assertNotIn("政策催化", normalized["related_sectors"])

    def test_normalization_replaces_low_confidence_broad_remote_direction(self):
        normalized = ai_analyze_event_sectors(
            "2026年两岸融合发展（福州）大会将于5月21日举办",
            helpers={
                "_default_get_llm_service": lambda: type(
                    "BroadClient",
                    (),
                    {
                        "analyze_event_sectors": lambda self, event_title, event_summary="": {
                            "main_direction": "外贸投资",
                            "related_sectors": ["外贸投资", "宏观经济"],
                            "trading_logic": "低置信度宽泛归类",
                            "expectation": "中性",
                            "confidence": "低",
                        }
                    },
                )(),
                "ENABLE_REMOTE_CALENDAR_LLM": True,
            },
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(normalized["main_direction"], "海峡概念")
        self.assertIn("福建板块", normalized["related_sectors"])

    def test_normalization_prefers_direct_title_semantics_over_mid_confidence_broad_remote_direction(self):
        normalized = ai_analyze_event_sectors(
            "深圳天微电子：自5月20日起，公司全系列产品价格上调10-30%",
            helpers={
                "_default_get_llm_service": lambda: type(
                    "BroadClient",
                    (),
                    {
                        "analyze_event_sectors": lambda self, event_title, event_summary="": {
                            "main_direction": "半导体",
                            "related_sectors": ["半导体", "电子元器件"],
                            "trading_logic": "半导体公司涨价",
                            "expectation": "利好",
                            "confidence": "中",
                        }
                    },
                )(),
                "ENABLE_REMOTE_CALENDAR_LLM": True,
            },
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(normalized["main_direction"], "电子元器件")
        self.assertIn("电子元器件", normalized["related_sectors"])

    def test_ai_normalization_uses_title_semantics_when_remote_llm_returns_other(self):
        class OtherClient:
            def analyze_event_sectors(self, event_title, event_summary=""):
                return {
                    "main_direction": "其他",
                    "related_sectors": ["其他"],
                    "trading_logic": "AI无法识别明确产业链",
                    "expectation": "中性",
                    "confidence": "低",
                }

        result = ai_analyze_event_sectors(
            "金蝶AI峰会2026AI技术论坛将于5月20日举办",
            helpers={
                "_default_get_llm_service": lambda: OtherClient(),
                "ENABLE_REMOTE_CALENDAR_LLM": True,
            },
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["main_direction"], "AI应用")
        self.assertNotIn("政策催化", result["related_sectors"])

    def test_ai_analyze_event_sectors_normalizes_llm_other_to_concrete_bucket(self):
        class OtherClient:
            def analyze_event_sectors(self, event_title, event_summary=""):
                return {
                    "main_direction": "其他",
                    "related_sectors": ["其他"],
                    "trading_logic": "AI无法识别明确产业链",
                    "expectation": "中性",
                    "confidence": "低",
                }

        result = ai_analyze_event_sectors(
            "未知行业政策发布",
            helpers={"_default_get_llm_service": lambda: OtherClient()},
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["main_direction"], "政策催化")
        self.assertNotIn("其他", result["related_sectors"])

    def test_ai_analyze_event_sectors_handles_missing_llm_service_without_other(self):
        result = ai_analyze_event_sectors(
            "某区域发展规划发布",
            helpers={"_default_get_llm_service": lambda: None},
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertNotEqual(result["main_direction"], "其他")
        self.assertTrue(result["related_sectors"])

    def test_ai_analyze_event_sectors_handles_malformed_llm_result_without_other(self):
        class MalformedClient:
            def analyze_event_sectors(self, event_title, event_summary=""):
                return None

        result = ai_analyze_event_sectors(
            "未知行业政策发布",
            helpers={"_default_get_llm_service": lambda: MalformedClient()},
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["main_direction"], "政策催化")
        self.assertTrue(result["related_sectors"])

    def test_ai_analyze_event_sectors_uses_local_rules_by_default_without_llm(self):
        class ExplodingClient:
            def analyze_event_sectors(self, event_title, event_summary=""):
                raise AssertionError("DeepSeek should not be called by default")

        result = ai_analyze_event_sectors(
            "人形机器人产业大会召开",
            helpers={
                "_default_get_llm_service": lambda: ExplodingClient(),
                "ENABLE_REMOTE_CALENDAR_LLM": False,
            },
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["main_direction"], "人形机器人")
        self.assertIn("减速器", result["related_sectors"])

    def test_ai_analyze_event_sectors_falls_back_to_local_rules_when_remote_llm_fails(self):
        class FailingClient:
            def analyze_event_sectors(self, event_title, event_summary=""):
                raise RuntimeError("deepseek timeout")

        emitted = []
        result = ai_analyze_event_sectors(
            "人形机器人产业大会召开",
            helpers={
                "_default_get_llm_service": lambda: FailingClient(),
                "ENABLE_REMOTE_CALENDAR_LLM": True,
            },
            print_fn=emitted.append,
        )

        self.assertEqual(result["main_direction"], "人形机器人")
        self.assertIn("减速器", result["related_sectors"])
        self.assertTrue(any("远程LLM失败" in line for line in emitted))

    def test_analyze_event_sector_prefers_hot_rank_concepts_before_keyword_fallback(self):
        sector = analyze_event_sector(
            "华为折叠屏新品发布",
            hot_rank_data=[
                {"concepts": ["折叠屏", "消费电子"]},
                {"concepts": ["算力"]},
            ],
        )
        self.assertEqual(sector, "折叠屏")

    def test_analyze_event_sector_never_returns_other_for_unknown_event(self):
        sector = analyze_event_sector("完全未知事件")

        self.assertEqual(sector, "政策催化")


if __name__ == "__main__":
    unittest.main()
