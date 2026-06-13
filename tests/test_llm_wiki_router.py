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

    def test_routes_capital_priority_for_old_position_and_new_opportunity(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "长电科技 or 华电辽能，本质是不是汰弱留强",
                "position": {"state": "旧仓", "name": "华电辽能", "action": "做T"},
                "candidate": {"name": "长电科技", "quality": ["新机会", "换仓"]},
                "capital_priority": "先比较旧仓和新机会",
            },
            scenario="intraday_question",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("position.cull-weak-keep-strong", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "position.cull-weak-keep-strong")
        self.assertEqual(hit["prior"], "capital-priority-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/价格行为与能量框架.md")
        self.assertIn("汰弱留强", hit["triggered_by"])
        self.assertIn("换仓", hit["triggered_by"])
        self.assertIn("旧仓", hit["triggered_by"])
        self.assertIn("新机会", hit["triggered_by"])
        self.assertIn("先判旧仓是否仍被市场选择", hit["impact"])
        self.assertIn("窗口和亏损边界清楚", hit["impact"])
        self.assertIn("不卖强补弱", hit["impact"])
        self.assertEqual(hit["report_slot"], "资金优先级")

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

    def test_routes_profit_after_win_discipline(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "最近连续盈利后有点飘了，股池强者也接连走弱，两笔出问题后是不是要直接停手",
                "market": {"signals": ["连板高度下降", "热点宽度收窄", "高位异动减少"]},
            },
            scenario="review",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("discipline.profit-after-win-control", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "discipline.profit-after-win-control")
        self.assertEqual(hit["prior"], "trade-discipline-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/做T与风险控制.md")
        self.assertIn("连续盈利", hit["triggered_by"])
        self.assertIn("飘了", hit["triggered_by"])
        self.assertIn("股池", hit["triggered_by"])
        self.assertIn("两笔出问题", hit["triggered_by"])
        self.assertIn("连板高度", hit["triggered_by"])
        self.assertIn("热点宽度", hit["triggered_by"])
        self.assertIn("连续盈利后先降频降仓", hit["impact"])
        self.assertIn("触发失效直接停手", hit["impact"])
        self.assertEqual(hit["report_slot"], "交易纪律")
        self.assertEqual(hit["confidence"], "reviewed")

    def test_routes_present_execution_discipline(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "短线应该注重当下，不要因为焦虑去预测未来，也不要期待遥不可及的价值投资或新股上市当天暴涨",
            },
            scenario="review",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("discipline.present-execution", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "discipline.present-execution")
        self.assertEqual(hit["prior"], "trade-discipline-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/价格行为与能量框架.md")
        self.assertIn("短线", hit["triggered_by"])
        self.assertIn("当下", hit["triggered_by"])
        self.assertIn("焦虑", hit["triggered_by"])
        self.assertIn("未来", hit["triggered_by"])
        self.assertIn("价值投资", hit["triggered_by"])
        self.assertIn("新股", hit["triggered_by"])
        self.assertIn("暴涨", hit["triggered_by"])
        self.assertIn("盘中执行只看当下价格", hit["impact"])
        self.assertIn("只进观察或研究", hit["impact"])
        self.assertEqual(hit["report_slot"], "交易纪律")
        self.assertEqual(hit["confidence"], "reviewed")

    def test_routes_brooks_price_action_trend_framework(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "按布鲁克斯价格行为看，不看指标组合时，成交量放量算资金表态吗，这里是始终入场方向还是等二次入场，交易者等式划不划算",
            },
            scenario="intraday_question",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("price-action.brooks-trend-framework", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "price-action.brooks-trend-framework")
        self.assertEqual(hit["prior"], "price-action-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/布鲁克斯价格行为趋势.md")
        self.assertIn("布鲁克斯", hit["triggered_by"])
        self.assertIn("价格行为", hit["triggered_by"])
        self.assertIn("指标组合", hit["triggered_by"])
        self.assertIn("成交量", hit["triggered_by"])
        self.assertIn("放量", hit["triggered_by"])
        self.assertIn("资金表态", hit["triggered_by"])
        self.assertIn("始终入场", hit["triggered_by"])
        self.assertIn("二次入场", hit["triggered_by"])
        self.assertIn("交易者等式", hit["triggered_by"])
        self.assertIn("先判趋势/交易区间", hit["impact"])
        self.assertIn("成交量只作资金表态证据", hit["impact"])
        self.assertIn("同一失效线", hit["impact"])
        self.assertEqual(hit["report_slot"], "价格行为判断")
        self.assertEqual(hit["confidence"], "reviewed")

    def test_routes_anti_fake_precision_first_principle(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "日报选股不要伪精确评分，也不要用加权总分或成功率替代淘汰赛条件链；先从板块资金扩散找资金载体，看量化参与痕迹，再按布鲁克斯价格行为和第一性原理重看",
            },
            scenario="candidate_quality",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("principle.anti-fake-precision", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "principle.anti-fake-precision")
        self.assertEqual(hit["prior"], "first-principles-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/反伪精确第一性原理.md")
        self.assertIn("伪精确", hit["triggered_by"])
        self.assertIn("评分", hit["triggered_by"])
        self.assertIn("加权", hit["triggered_by"])
        self.assertIn("成功率", hit["triggered_by"])
        self.assertIn("淘汰赛", hit["triggered_by"])
        self.assertIn("条件链", hit["triggered_by"])
        self.assertIn("板块资金扩散", hit["triggered_by"])
        self.assertIn("资金载体", hit["triggered_by"])
        self.assertIn("量化参与痕迹", hit["triggered_by"])
        self.assertIn("事实数值保留", hit["impact"])
        self.assertIn("主观判断不能写成精确分", hit["impact"])
        self.assertIn("板块资金扩散找资金载体", hit["impact"])
        self.assertEqual(hit["report_slot"], "选股原则")
        self.assertEqual(hit["confidence"], "verified")

    def test_routes_supply_chain_bottleneck_research_framework(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "请按产业链拆解CPO光通信和InP衬底，判断哪个关键材料是供应链瓶颈、有没有不可替代供应商",
                "research_context": {
                    "theme": "AI硬件",
                    "terms": ["产能稀缺", "客户认证", "反方验证"],
                },
            },
            scenario="candidate_quality",
        )

        hit = hits[0]
        self.assertEqual(hit["knowledge_id"], "research.supply-chain-bottleneck")
        self.assertEqual(hit["prior"], "research-framework-prior")
        self.assertEqual(hit["source_path"], "wiki/板块补充/供应链瓶颈研究法.md")
        self.assertIn("供应链瓶颈", hit["triggered_by"])
        self.assertIn("InP", hit["triggered_by"])
        self.assertIn("衬底", hit["triggered_by"])
        self.assertIn("不直接生成买入资格", hit["impact"])
        self.assertEqual(hit["report_slot"], "研究线索")
        self.assertEqual(hit["confidence"], "reviewed")

    def test_plain_industry_chain_question_does_not_force_bottleneck_framework(self):
        hits = route_llm_wiki_knowledge(
            {"question": "汽车产业链今天能不能做"},
            scenario="candidate_quality",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertNotIn("research.supply-chain-bottleneck", ids)

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
