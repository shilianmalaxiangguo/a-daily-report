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

    def test_builds_fact_tags_from_sector_grid_first_selection(self):
        facts = build_llm_wiki_fact_tags(
            {
                "market_structure_judgement": {
                    "summary_text": "结构性行情用水池九宫格理解，先选板块，再看个股是不是边角标的",
                    "index_profit_relation": "指数强不等于普涨",
                    "fact_basis": ["资金灌入主线板块格子", "板块网格化明显"],
                }
            }
        )

        self.assertEqual(facts["market"]["index_trend"], "上涨")
        self.assertEqual(facts["market"]["market_form"], "结构性行情")
        self.assertEqual(facts["market"]["sector_grid"], "水池九宫格")
        self.assertEqual(facts["market"]["selection_order"], "先选板块")
        self.assertEqual(facts["market"]["corner_sample"], "边角标的")

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

    def test_builds_fact_tags_from_final_target_resolution_capital_priority(self):
        facts = build_llm_wiki_fact_tags(
            {
                "market_research_snapshot": {
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "华电辽能(600396)：已有仓先按MA5T处理",
                    },
                    "final_target_resolution": {
                        "new_entry_target": {"name": "工业富联", "code": "601138"},
                        "existing_position_target": {"name": "华电辽能", "code": "600396"},
                        "capital_priority_decision": {
                            "capital_priority": "new_entry_after_old_exit",
                            "reason": "先处理旧仓，买工业富联；按昨晚预案检查执行资格；不满足回到0%不参与",
                        },
                    },
                },
            }
        )

        self.assertEqual(facts["position"]["state"], "旧仓")
        self.assertEqual(facts["position"]["action"], "换仓")
        self.assertIn("新机会", facts["candidate"]["quality"])
        self.assertIn("换仓", facts["candidate"]["quality"])
        self.assertEqual(facts["capital_priority"], "new_entry_after_old_exit")

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

    def test_routes_sector_grid_first_selection_for_structural_market(self):
        hits = route_llm_wiki_knowledge(
            {
                "market": {
                    "market_form": "结构性行情",
                    "sector_grid": "水池九宫格",
                    "selection_order": "先选板块",
                    "corner_sample": "边角标的",
                },
                "question": "这张图说的九宫格和我说的板块先行、轮动不到边角标的是不是一个意思",
            },
            scenario="review",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("market.sector-grid-first-selection", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "market.sector-grid-first-selection")
        self.assertEqual(hit["prior"], "market-structure-prior")
        self.assertEqual(hit["source_path"], "wiki/板块补充/板块中枢与主线延续.md")
        self.assertIn("结构性行情", hit["triggered_by"])
        self.assertIn("水池九宫格", hit["triggered_by"])
        self.assertIn("先选板块", hit["triggered_by"])
        self.assertIn("边角标的", hit["triggered_by"])
        self.assertIn("资金灌入哪个板块格子", hit["impact"])
        self.assertIn("边角标的不因轮动自动取得参与资格", hit["impact"])
        self.assertEqual(hit["report_slot"], "市场结构判断")
        self.assertEqual(hit["confidence"], "reviewed")

    def test_routes_sector_grid_first_selection_from_water_pillar_terms(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "全市场水池里蓝色粗水柱和红色细水柱分别代表什么，为什么边角标的轮动不到",
            },
            scenario="review",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "market.sector-grid-first-selection")
        self.assertIn("全市场水池", hit["triggered_by"])
        self.assertIn("蓝色粗水柱", hit["triggered_by"])
        self.assertIn("红色细水柱", hit["triggered_by"])
        self.assertIn("水柱", hit["triggered_by"])
        self.assertIn("边角标的", hit["triggered_by"])

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

    def test_builds_fact_tags_from_zero_position_response_script(self):
        facts = build_llm_wiki_fact_tags(
            {
                "final_target_resolution": {
                    "final": {
                        "position_pct": 0,
                        "action_text": "只观察承接，不新增参与；第一动作不直接给买入资格",
                        "failure_conditions": ["B1参与权失败，取消B2确认权", "避免踏空焦虑补足"],
                    }
                }
            }
        )

        tags = facts["decision"]["response_script"]
        self.assertIn("0%不参与", tags)
        self.assertIn("无执行目标", tags)
        self.assertIn("只观察", tags)
        self.assertIn("第一动作", tags)
        self.assertIn("B1", tags)
        self.assertIn("B2", tags)
        self.assertIn("买入资格", tags)
        self.assertIn("踏空焦虑", tags)

    def test_builds_fact_tags_from_participation_script(self):
        facts = build_llm_wiki_fact_tags(
            {
                "final_target_resolution": {
                    "new_entry_target": {"name": "工业富联", "code": "601138"},
                    "tomorrow_action": "第一动作只给B1参与权",
                    "participation_script": {
                        "confirm_conditions": ["板块扩散和个股强度确认后再看B2确认权"],
                        "cancellation_conditions": ["没有买入资格就只观察，避免踏空焦虑补足"],
                        "position_plan": "B1保持连接感，B2等待确认",
                    },
                }
            }
        )

        tags = facts["decision"]["response_script"]
        self.assertIn("第一动作", tags)
        self.assertIn("B1", tags)
        self.assertIn("B2", tags)
        self.assertIn("只观察", tags)
        self.assertIn("买入资格", tags)
        self.assertIn("踏空焦虑", tags)
        decision = facts["decision"]
        self.assertEqual(decision["action_layer"], "只观察")
        self.assertEqual(decision["participation_rhythm"], "第一动作")
        self.assertEqual(decision["b1_role"], "参与权")
        self.assertEqual(decision["b2_role"], "确认权")
        self.assertEqual(decision["qualification"], "买入资格")
        self.assertIn("踏空焦虑", decision["behavior_traps"])

    def test_routes_anti_prediction_response_script_to_daily_action_slot(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "我是不是陷入预测崇拜，想每天一个个股踩准节拍；今天只有第一动作，要不要写成应对剧本，B1保持连接感，B2等确认，避免踏空焦虑",
                "decision": {"response_script": ["0%不参与", "只观察", "无执行目标"]},
            },
            scenario="daily_report",
            limit=5,
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("decision.anti-prediction-response-script", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "decision.anti-prediction-response-script")
        self.assertEqual(hit["prior"], "decision-sample-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/判断样本与市场演变.md")
        for required in [
            "预测崇拜",
            "每天一个个股",
            "踩准节拍",
            "应对剧本",
            "第一动作",
            "B1",
            "B2",
            "连接感",
            "踏空焦虑",
            "0%不参与",
            "只观察",
            "无执行目标",
        ]:
            self.assertIn(required, hit["triggered_by"])
        self.assertEqual(hit["report_slot"], "明日执行结论")
        self.assertIn("日报不是预测节拍", hit["impact"])
        self.assertIn("没有买入资格时0%不参与", hit["impact"])
        self.assertIn("第一动作只给B1参与权", hit["impact"])
        self.assertIn("B2必须等待后续承接", hit["impact"])

    def test_routes_anti_prediction_from_structured_conditions_without_trigger_terms(self):
        hits = route_llm_wiki_knowledge(
            {
                "decision": {
                    "position_plan": "零仓位",
                    "action_layer": "观察层",
                    "b1_role": "参与角色",
                    "b2_role": "确认角色",
                    "qualification": "资格不足",
                    "response_mode": "应对",
                }
            },
            scenario="daily_report",
            limit=1,
        )

        self.assertEqual(hits[0]["knowledge_id"], "decision.anti-prediction-response-script")
        self.assertEqual(
            hits[0]["matched_conditions"],
            ["0%不参与", "只观察", "B1参与权", "B2确认权", "买入资格", "应对剧本"],
        )
        self.assertEqual(hits[0]["triggered_by"], hits[0]["matched_conditions"])

    def test_prefer_only_structured_conditions_do_not_route_anti_prediction(self):
        hits = route_llm_wiki_knowledge(
            {
                "decision": {
                    "b1_role": "参与角色",
                    "b2_role": "确认角色",
                    "qualification": "资格不足",
                    "response_mode": "应对",
                }
            },
            scenario="daily_report",
            limit=5,
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertNotIn("decision.anti-prediction-response-script", ids)

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
        self.assertIn("先判旧仓是否失去持仓资格", hit["impact"])
        self.assertIn("再判新机会是否取得执行资格", hit["impact"])
        self.assertIn("不卖强补弱", hit["impact"])
        self.assertIn("不用FOMO把两笔判断合成一次满仓替换", hit["impact"])
        self.assertEqual(hit["report_slot"], "资金优先级")

    def test_routes_first_principle_fomo_to_cull_weak_keep_strong(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "我彻底FOMO了，A股短线第一性原理是不是去弱留强，旧仓卖了以后能不能满仓换更强方向",
                "position": {"state": "旧仓", "action": "换仓"},
                "candidate": {"quality": ["新机会", "满仓"]},
            },
            scenario="intraday_question",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "position.cull-weak-keep-strong")
        self.assertIn("去弱留强", hit["triggered_by"])
        self.assertIn("第一性原理", hit["triggered_by"])
        self.assertIn("FOMO", hit["triggered_by"])
        self.assertIn("满仓", hit["triggered_by"])
        self.assertIn("卖旧仓看旧仓资格", hit["impact"])
        self.assertIn("买新仓看新仓资格", hit["impact"])

    def test_routes_fomo_buyback_after_must_sell_day_to_discipline(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "昨天必卖后今天反包，我很后悔，空仓旧仓是不是应该0轴卖而不是买回",
                "position": {"state": "旧仓"},
            },
            scenario="review",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "discipline.fomo-external-stimulus")
        self.assertIn("必卖", hit["triggered_by"])
        self.assertIn("反包", hit["triggered_by"])
        self.assertIn("空仓", hit["triggered_by"])
        self.assertIn("旧仓", hit["triggered_by"])
        self.assertIn("0轴卖", hit["triggered_by"])
        self.assertIn("反包先批改情绪反应", hit["impact"])
        self.assertIn("旧仓退出流动性", hit["impact"])

    def test_routes_rhythm_reset_margin_review_from_reasonable_empty_and_external_storage(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "我觉得这次合理空仓可能是节奏踏错和同手同脚，外盘拉升、外盘存储和存储大涨都提示边际主线，旧目标强弩之末时太极实业和宜宾纸业应该怎么反推；如果周一空仓，周五信号源和周五策略也要批改，周二再强不能替旧结论正名",
                "position": {"state": "旧仓", "name": "太极实业"},
            },
            scenario="review",
            limit=5,
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("selection.rhythm-reset-margin-review", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "selection.rhythm-reset-margin-review")
        self.assertEqual(hit["prior"], "selection-review-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/价格行为与能量框架.md")
        for required in [
            "节奏踏错",
            "同手同脚",
            "合理空仓",
            "边际主线",
            "外盘拉升",
            "外盘存储",
            "存储大涨",
            "旧目标强弩之末",
            "周五信号源",
            "周五策略",
            "周一空仓",
            "周二再强",
            "太极实业",
            "宜宾纸业",
        ]:
            self.assertIn(required, hit["triggered_by"])
        self.assertEqual(hit["report_slot"], "超短边际节奏复核")
        self.assertIn("最终0%不是思考终点", hit["impact"])
        self.assertIn("追溯周五选股、买点、持仓预期和退出纪律", hit["impact"])
        self.assertIn("不替周五或周一正名", hit["impact"])
        self.assertIn("T+1复核", hit["impact"])
        self.assertIn("过程候选不覆盖最终动作", hit["impact"])

    def test_routes_performance_rotation_main_attack_from_haaland_analogy(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "业绩线逻辑开始后，科技线是不是应该像哈兰德一样先做牵制点，主攻点切到轮动线和非科技；这种风格变换是不是不合理的超额收益",
            },
            scenario="review",
            limit=5,
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("market.performance-rotation-main-attack", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "market.performance-rotation-main-attack")
        self.assertEqual(hit["source_path"], "wiki/板块补充/板块中枢与主线延续.md")
        for required in [
            "业绩线",
            "科技线",
            "哈兰德",
            "牵制点",
            "主攻点",
            "轮动线",
            "非科技",
            "风格变换",
            "不合理的超额收益",
        ]:
            self.assertIn(required, hit["triggered_by"])
        self.assertEqual(hit["report_slot"], "市场结构判断")
        self.assertIn("主线不是信仰位", hit["impact"])
        self.assertIn("可降为牵制点", hit["impact"])
        self.assertIn("同权比较", hit["impact"])
        self.assertIn("风格切换载体", hit["impact"])

    def test_routes_ta_te_timeline_to_slot_timeline_knowledge(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "账户日序是不是应该迁移成Ta-Te五日表，Td是今日，Te是明日执行日，明日标的为空就只处理旧仓风险",
                "position": {"state": "旧仓", "name": "太极实业"},
            },
            scenario="daily_report",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "discipline.tplus-slot-timeline")
        self.assertIn("Ta", hit["triggered_by"])
        self.assertIn("Td", hit["triggered_by"])
        self.assertIn("Te", hit["triggered_by"])
        self.assertIn("Ta是最远复盘日", hit["impact"])
        self.assertIn("Te是明日执行日", hit["impact"])

    def test_routes_daily_report_final_resolution_to_cull_weak_keep_strong(self):
        facts = build_llm_wiki_fact_tags(
            {
                "final_target_resolution": {
                    "new_entry_target": {"name": "工业富联", "code": "601138"},
                    "existing_position_target": {"name": "华电辽能", "code": "600396"},
                    "capital_priority_decision": {
                        "capital_priority": "new_entry_after_old_exit",
                        "reason": "先处理旧仓，买工业富联；按昨晚预案检查执行资格；不满足回到0%不参与",
                    },
                },
            }
        )
        hits = route_llm_wiki_knowledge(facts, scenario="daily_report")

        hit = next(item for item in hits if item["knowledge_id"] == "position.cull-weak-keep-strong")
        self.assertIn("旧仓", hit["triggered_by"])
        self.assertIn("新机会", hit["triggered_by"])
        self.assertIn("换仓", hit["triggered_by"])

    def test_daily_report_new_entry_without_position_does_not_create_old_position_hit(self):
        facts = build_llm_wiki_fact_tags(
            {
                "existing_position_summary": {"has_position": False},
                "final_target_resolution": {
                    "new_entry_target": {"name": "工业富联", "code": "601138"},
                    "capital_priority_decision": {
                        "capital_priority": "new_entry",
                        "reason": "按昨晚预案检查执行资格；不满足回到0%不参与",
                    },
                },
            }
        )
        hits = route_llm_wiki_knowledge(facts, scenario="daily_report")

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertNotIn("position.cull-weak-keep-strong", ids)
        self.assertNotIn("position", facts)
        self.assertNotIn("candidate", facts)

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

    def test_routes_same_stock_t_failure_control(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "太极实业已有1x，今日目标还是同一只票，早盘强表态后跌破VWAP和跌破MA7，2x是不是尾盘再卖底仓",
                "position": {"state": "旧仓", "capital_priority": "old_position_t"},
            },
            scenario="intraday_question",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("intraday.same-stock-t-failure-control", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "intraday.same-stock-t-failure-control")
        self.assertEqual(hit["source_path"], "wiki/交易思想/做T与风险控制.md")
        self.assertIn("太极实业", hit["triggered_by"])
        self.assertIn("1x", hit["triggered_by"])
        self.assertIn("同一只票", hit["triggered_by"])
        self.assertIn("强表态", hit["triggered_by"])
        self.assertIn("跌破VWAP", hit["triggered_by"])
        self.assertIn("跌破MA7", hit["triggered_by"])
        self.assertIn("同股T候选", hit["impact"])
        self.assertIn("卖出可卖旧仓", hit["impact"])
        self.assertIn("尾盘卖出只适用于正常样本", hit["impact"])
        self.assertEqual(hit["report_slot"], "同股T处理")
        self.assertEqual(hit["confidence"], "reviewed")

    def test_routes_same_stock_t_from_structured_exposure_plan(self):
        facts = build_llm_wiki_fact_tags(
            {
                "final_target_resolution": {
                    "existing_position_target": {"name": "太极实业", "code": "600667"},
                    "new_entry_target": {"name": "太极实业", "code": "600667"},
                    "account_exposure_plan": {"same_stock_t": True},
                    "capital_priority_decision": {
                        "capital_priority": "same_stock_t",
                        "reason": "已有1x旧仓且今日目标仍是同一只票，只按同股T候选处理",
                    },
                }
            }
        )
        hits = route_llm_wiki_knowledge(facts, scenario="daily_report")

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("intraday.same-stock-t-failure-control", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "intraday.same-stock-t-failure-control")
        self.assertIn("same_stock_t", hit["triggered_by"])
        self.assertIn("同股T", hit["triggered_by"])
        self.assertIn("临时2x", hit["triggered_by"])

    def test_does_not_route_same_stock_t_for_different_old_and_new_target(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "太极实业旧仓1x，深科技是新的明日机会，是否需要分账处理",
                "position": {"state": "旧仓", "capital_priority": "new_entry"},
                "candidate": {"quality": ["新机会"]},
            },
            scenario="daily_report",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertNotIn("intraday.same-stock-t-failure-control", ids)

    def test_routes_two_b_confirmation_positioning(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "2B法里B1买0.5B以后，B2是不是当天必须买够？我怕只小赚没有大赚，也怕集合竞价不买满错过初始仓位收益",
                "position": {"state": "短线", "concern": "态度和仓位"},
            },
            scenario="intraday_question",
            limit=5,
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("intraday.two-b-confirmation-positioning", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "intraday.two-b-confirmation-positioning")
        self.assertEqual(hit["source_path"], "wiki/交易思想/做T与风险控制.md")
        self.assertIn("2B法", hit["triggered_by"])
        self.assertIn("B1", hit["triggered_by"])
        self.assertIn("B2", hit["triggered_by"])
        self.assertIn("必须买够", hit["triggered_by"])
        self.assertIn("小赚", hit["triggered_by"])
        self.assertIn("B1只买参与权", hit["impact"])
        self.assertIn("B2不是任务仓", hit["impact"])
        self.assertIn("坏样本只亏B1", hit["impact"])
        self.assertEqual(hit["report_slot"], "2B仓位处理")
        self.assertEqual(hit["confidence"], "reviewed")

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
                "question": "按布鲁克斯价格行为看，不看基本面和指标组合时，成交量放量算资金表态吗，这里是始终入场方向还是等二次入场，交易者等式划不划算，别按图索因也别先用叙事安慰自己",
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
        self.assertIn("基本面", hit["triggered_by"])
        self.assertIn("按图索因", hit["triggered_by"])
        self.assertIn("始终入场", hit["triggered_by"])
        self.assertIn("二次入场", hit["triggered_by"])
        self.assertIn("交易者等式", hit["triggered_by"])
        self.assertIn("先判趋势/交易区间", hit["impact"])
        self.assertIn("成交量只作资金表态证据", hit["impact"])
        self.assertIn("同一失效线", hit["impact"])
        self.assertEqual(hit["report_slot"], "价格行为判断")
        self.assertEqual(hit["confidence"], "reviewed")

    def test_routes_fake_bottom_attack_shape_to_brooks_price_action_trend_framework(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "假底、进攻雏形、再等等、重心上移、缩量横盘、前高附近、利空不深跌、利好不大涨、阳包阴和突破阳线怎么看",
            },
            scenario="intraday_question",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("price-action.brooks-trend-framework", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "price-action.brooks-trend-framework")
        self.assertIn("假底", hit["triggered_by"])
        self.assertIn("进攻雏形", hit["triggered_by"])
        self.assertIn("再等等", hit["triggered_by"])
        self.assertIn("重心上移", hit["triggered_by"])
        self.assertIn("缩量横盘", hit["triggered_by"])
        self.assertIn("前高", hit["triggered_by"])
        self.assertIn("利空不深跌", hit["triggered_by"])
        self.assertIn("利好不大涨", hit["triggered_by"])
        self.assertIn("阳包阴", hit["triggered_by"])
        self.assertIn("突破阳线", hit["triggered_by"])

    def test_routes_entry_quality_three_conditions_for_chasing_rise(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "这篇追涨杀跌文章讲的买点是不是看趋势地基、盈亏同源和股性，异动K线后反包才更可信",
            },
            scenario="intraday_question",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("price-action.entry-quality-three-conditions", ids)
        hit = next(item for item in hits if item["knowledge_id"] == "price-action.entry-quality-three-conditions")
        self.assertEqual(hit["prior"], "entry-quality-prior")
        self.assertEqual(hit["source_path"], "wiki/交易思想/价格行为与能量框架.md")
        self.assertIn("追涨杀跌", hit["triggered_by"])
        self.assertIn("买点", hit["triggered_by"])
        self.assertIn("趋势地基", hit["triggered_by"])
        self.assertIn("盈亏同源", hit["triggered_by"])
        self.assertIn("股性", hit["triggered_by"])
        self.assertIn("异动K", hit["triggered_by"])
        self.assertIn("反包", hit["triggered_by"])
        self.assertIn("先验趋势地基", hit["impact"])
        self.assertIn("贴近认错线", hit["impact"])
        self.assertEqual(hit["report_slot"], "买点质量")
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

    def test_routes_early_belief_fish_body_cycle_framework(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "这篇早信和鱼身的启发是不是说，龙头二次发力时先看无人问津的同线标的，但人声鼎沸时要主动卖飞",
            },
            scenario="review",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "market.early-belief-fish-body-cycle")
        self.assertIn("早信", hit["triggered_by"])
        self.assertIn("鱼身", hit["triggered_by"])
        self.assertIn("无人问津", hit["triggered_by"])
        self.assertIn("龙头二次发力", hit["triggered_by"])
        self.assertIn("人声鼎沸", hit["triggered_by"])
        self.assertIn("主动卖飞", hit["triggered_by"])
        self.assertIn("不替代买入资格", hit["impact"])
        self.assertIn("主动降风险", hit["impact"])

    def test_routes_rebound_quality_active_passive_framework(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "反弹的时候要看板块指数，主动带动反弹可以看参与，跟随指数反弹是减亏离场；指数深V但国产链先于指数上涨，节奏不匹配时先写共振待确认，熟悉资产修复要看持续承接",
            },
            scenario="review",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "market.rebound-quality-active-passive")
        self.assertIn("反弹质量", hit["matched_topics"])
        self.assertIn("主动带动反弹", hit["matched_topics"])
        self.assertIn("熟悉资产修复", hit["matched_topics"])
        self.assertIn("板块指数", hit["triggered_by"])
        self.assertIn("主动带动", hit["triggered_by"])
        self.assertIn("跟随指数", hit["triggered_by"])
        self.assertIn("减亏离场", hit["triggered_by"])
        self.assertIn("熟悉资产修复", hit["triggered_by"])
        self.assertIn("深V", hit["triggered_by"])
        self.assertIn("国产链", hit["triggered_by"])
        self.assertIn("先于指数", hit["triggered_by"])
        self.assertIn("节奏不匹配", hit["triggered_by"])
        self.assertIn("主动带动反弹按进攻线观察", hit["impact"])
        self.assertIn("跟随指数反弹优先按减亏离场", hit["impact"])
        self.assertIn("熟悉资产修复看持续承接", hit["impact"])
        self.assertIn("只写共振待确认", hit["impact"])

    def test_builds_rebound_quality_facts_from_market_structure_judgement(self):
        facts = build_llm_wiki_fact_tags(
            {
                "market_structure_judgement": {
                    "summary_text": "指数深V，国产链先于指数四天上涨，板块高潮碰上指数修复，节奏不匹配，先写共振待确认",
                    "fact_basis": [
                        "主动带动反弹方向可给B1参与权",
                        "跟随指数反弹只作为减亏离场和减风险窗口",
                        "熟悉资产修复来自调研充分且未来预期良好方向，继续看持续承接",
                    ],
                }
            }
        )

        market = facts["market"]
        self.assertIn("主动带动反弹", market["rebound_roles"])
        self.assertIn("跟随指数反弹", market["rebound_roles"])
        self.assertIn("熟悉资产修复", market["rebound_roles"])
        self.assertIn("指数深V", market["rebound_state"])
        self.assertIn("先于指数", market["rebound_state"])
        self.assertIn("板块高潮", market["rebound_state"])
        self.assertIn("节奏共振待确认", market["rebound_state"])
        self.assertIn("B1参与权", market["rebound_action"])
        self.assertIn("减亏离场", market["rebound_action"])
        self.assertIn("持续承接确认", market["rebound_action"])

        hits = route_llm_wiki_knowledge(facts, scenario="daily_report")
        hit = next(item for item in hits if item["knowledge_id"] == "market.rebound-quality-active-passive")
        self.assertIn("主动带动反弹", hit["matched_conditions"])
        self.assertIn("跟随指数反弹", hit["matched_conditions"])
        self.assertIn("熟悉资产修复", hit["matched_conditions"])
        self.assertIn("节奏共振待确认", hit["matched_conditions"])
        self.assertIn("反弹动作分类", hit["matched_conditions"])

    def test_builds_rebound_quality_facts_from_candidate_and_position_text(self):
        facts = build_llm_wiki_fact_tags(
            {
                "selected_position_candidate": {
                    "name": "主动核心",
                    "reason": "主动带动反弹，先于指数修复，按B1参与权观察",
                    "strength_evidence": ["带动市场", "领涨"],
                },
                "final_target_resolution": {
                    "existing_position_target": {
                        "name": "跟随旧仓",
                        "risk_note": "跟随指数反弹，只作为减亏离场和减风险窗口",
                    },
                    "capital_priority_decision": {
                        "capital_priority": "old_position_t",
                        "reason": "旧仓跟随反弹，不按新主线处理",
                    },
                },
            }
        )

        self.assertIn("主动带动反弹", facts["candidate"]["rebound_roles"])
        self.assertIn("先于指数", facts["candidate"]["rebound_state"])
        self.assertIn("B1参与权", facts["candidate"]["rebound_action"])
        self.assertIn("跟随指数反弹", facts["position"]["rebound_roles"])
        self.assertIn("减亏离场", facts["position"]["rebound_action"])

        hits = route_llm_wiki_knowledge(facts, scenario="daily_report")
        hit = next(item for item in hits if item["knowledge_id"] == "market.rebound-quality-active-passive")
        self.assertIn("主动带动反弹", hit["matched_conditions"])
        self.assertIn("反弹动作分类", hit["matched_conditions"])
        self.assertIn("持仓反弹分类", hit["matched_conditions"])
        self.assertIn("持仓动作分类", hit["matched_conditions"])

    def test_stock_shape_weakening_does_not_route_to_rebound_quality_framework(self):
        hits = route_llm_wiki_knowledge(
            {"question": "个股图形走坏了，反弹要不要先降低风险"},
            scenario="review",
        )

        ids = [hit["knowledge_id"] for hit in hits]
        self.assertNotIn("market.rebound-quality-active-passive", ids)

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
