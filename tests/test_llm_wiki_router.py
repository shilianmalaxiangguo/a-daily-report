import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge.llm_wiki_router import build_llm_wiki_fact_tags, route_llm_wiki_knowledge


class LlmWikiRouterTest(unittest.TestCase):
    def test_builds_fact_tags_from_market_structure_judgement(self):
        facts = build_llm_wiki_fact_tags(
            {
                "market_structure_judgement": {
                    "summary_text": "指数强但真实赚钱效应弱；成交额高位但结构集中，不能按普涨支撑处理",
                    "index_profit_relation": "指数强但真实赚钱效应弱，指数不能代表多数股票体感",
                    "fact_basis": ["上涨家数偏弱，947只", "成交额32600.00亿"],
                }
            }
        )

        self.assertEqual(
            facts["market"],
            {
                "index_trend": "上涨",
                "breadth": "上涨家数偏弱",
                "turnover_distribution": "成交集中",
            },
        )

    def test_builds_fact_tags_from_account_and_candidate_context(self):
        facts = build_llm_wiki_fact_tags(
            {
                "account_profile": {
                    "cash_available": 9800,
                    "capital_text": "约1w账户",
                },
                "selected_position_candidate": {
                    "name": "强核心",
                    "identity": "市场核心",
                    "one_lot_amount": 18000,
                    "action_limit": "核心观察",
                    "risk_items": ["公告风险待确认"],
                    "recover_condition": "重新站回MA5",
                    "drop_condition": "跌破MA10",
                },
            }
        )

        self.assertEqual(facts["account"]["status"], "实际不可买")
        self.assertEqual(facts["account"]["cash_available"], 9800)
        self.assertEqual(facts["candidate"]["identity"], "市场核心")
        self.assertEqual(facts["candidate"]["one_lot_amount"], 18000)
        self.assertIn("候选质量", facts["candidate"]["quality"])
        self.assertIn("动作上限", facts["candidate"]["quality"])
        self.assertIn("风险项", facts["candidate"]["quality"])
        self.assertIn("恢复条件", facts["candidate"]["quality"])
        self.assertIn("取关条件", facts["candidate"]["quality"])

    def test_builds_fact_tags_from_runtime_account_and_candidate_context(self):
        facts = build_llm_wiki_fact_tags(
            {
                "personal_position_context": {
                    "account_profile": {
                        "cash_available": 9800,
                        "capital_text": "约1w账户",
                    },
                },
                "market_research_snapshot": {
                    "selected_position_candidate": {
                        "name": "强核心",
                        "identity": "市场核心",
                        "one_lot_amount": 18000,
                    },
                },
            }
        )

        self.assertEqual(facts["account"]["status"], "实际不可买")
        self.assertEqual(facts["account"]["cash_available"], 9800)
        self.assertEqual(facts["candidate"]["identity"], "市场核心")
        self.assertEqual(facts["candidate"]["one_lot_amount"], 18000)

    def test_routes_market_structure_prior_for_strong_index_weak_breadth(self):
        hits = route_llm_wiki_knowledge(
            {
                "market": {
                    "index_trend": "上涨",
                    "breadth": "上涨家数偏弱",
                    "turnover_distribution": "成交集中",
                }
            },
            scenario="daily_report",
        )

        self.assertGreaterEqual(len(hits), 1)
        first = hits[0]
        self.assertEqual(first["knowledge_id"], "market.low-frequency-focus")
        self.assertEqual(first["prior"], "market-structure-prior")
        self.assertEqual(first["source_path"], "wiki/板块补充/板块中枢与主线延续.md")
        self.assertIn("指数上涨", first["triggered_by"])
        self.assertIn("上涨家数偏弱", first["triggered_by"])
        self.assertIn("只保留主线核心", first["impact"])
        self.assertEqual(first["report_slot"], "市场结构判断")
        self.assertEqual(first["confidence"], "verified")

    def test_routes_account_prior_without_downgrading_market_identity(self):
        hits = route_llm_wiki_knowledge(
            {
                "candidate": {"identity": "市场核心", "one_lot_amount": 18000},
                "account": {"cash_available": 9800, "status": "实际不可买"},
            },
            scenario="daily_report",
        )

        hit = hits[0]
        self.assertEqual(hit["knowledge_id"], "account.unbuyable-core-anchor")
        self.assertEqual(hit["prior"], "account-execution-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/实际账户情况.md")
        self.assertIn("实际不可买", hit["triggered_by"])
        self.assertIn("只影响当前账户参与", hit["impact"])
        self.assertIn("不降低市场核心", hit["impact"])
        self.assertEqual(hit["report_slot"], "账户约束")

    def test_routes_intraday_question_prior_for_do_t_questions(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "这票亏损反弹了，要不要做T",
                "position": {"state": "亏损", "intraday_state": "反弹"},
            },
            scenario="intraday_question",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("intraday.do-t-risk-control", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "intraday.do-t-risk-control")
        self.assertEqual(hit["prior"], "intraday-question-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/做T与风险控制.md")
        self.assertIn("做T", hit["triggered_by"])
        self.assertIn("买回确认", hit["impact"])
        self.assertIn("不把更便宜当作更正确", hit["impact"])

    def test_limits_hits_and_keeps_explainable_contract(self):
        hits = route_llm_wiki_knowledge(
            {
                "market": {
                    "index_trend": "上涨",
                    "breadth": "上涨家数偏弱",
                    "turnover_distribution": "成交集中",
                },
                "candidate": {"identity": "市场核心", "one_lot_amount": 18000},
                "account": {"cash_available": 9800, "status": "实际不可买"},
                "question": "这票亏损反弹了，要不要做T",
            },
            scenario="daily_report",
            limit=2,
        )

        self.assertLessEqual(len(hits), 2)
        for hit in hits:
            self.assertTrue(hit["hit_id"].startswith("kh-"))
            self.assertTrue(hit["knowledge_id"])
            self.assertTrue(hit["source_path"])
            self.assertTrue(hit["triggered_by"])
            self.assertTrue(hit["matched_topics"])
            self.assertTrue(hit["impact"])
            self.assertTrue(hit["report_slot"])
            self.assertIn(hit["confidence"], {"draft", "reviewed", "verified", "disputed", "archived"})


if __name__ == "__main__":
    unittest.main()
