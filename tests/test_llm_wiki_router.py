import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge.llm_wiki_context import build_llm_wiki_context
from knowledge.llm_wiki_manifest import stable_json_hash
from knowledge.llm_wiki_router import (
    build_llm_wiki_fact_bundle,
    build_llm_wiki_fact_tags,
    route_llm_wiki_knowledge,
    route_llm_wiki_knowledge_trace,
)


TRACE_DATES = {
    "target_date": "2026-07-16",
    "query_date": "2026-07-17",
}


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

    def test_builds_and_routes_new_high_breadth_contraction_fact(self):
        sectors = [
            {"sector": sector, "new_high_count": 1}
            for sector in ["半导体", "水运", "纺织", "医药", "银行", "机械"]
        ]
        data = {
            "target_date": "2026-07-13",
            "new_high_feedback": {
                "available": True,
                "trend_rows": [
                    {
                        "trade_date": "2026-07-10",
                        "source_date": "2026-07-10",
                        "source": "same-source",
                        "new_high_count": 18,
                        "all_a_share_pct": 0.36,
                    },
                    {
                        "trade_date": "2026-07-13",
                        "source_date": "2026-07-13",
                        "source": "same-source",
                        "new_high_count": 6,
                        "all_a_share_pct": 0.12,
                        "sector_distribution": sectors,
                    },
                ],
            },
        }

        facts = build_llm_wiki_fact_tags(data)
        self.assertIn("扩散断层预警", facts["market"]["breadth"])
        self.assertIn("首次进入个位数", facts["market"]["breadth"])
        self.assertIn("板块碎片化", facts["market"]["breadth"])

        hits = route_llm_wiki_knowledge(facts, scenario="daily_report", limit=5)
        hit = next(
            item
            for item in hits
            if item["knowledge_id"] == "market.new-high-breadth-contraction"
        )
        self.assertIn("创新高扩散结构", hit["matched_conditions"])
        self.assertIn("不直接改变候选", hit["impact"])

    def test_new_high_trace_keeps_explanation_only_boundary(self):
        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            {"market": {"breadth": "创新高扩散断层预警，趋势生成率首次进入个位数"}},
            manifest=context["manifest"],
            limit=5,
            **TRACE_DATES,
        )

        hit = next(
            item
            for item in trace["hits"]
            if item["knowledge_id"] == "market.new-high-breadth-contraction"
        )
        self.assertEqual(hit["decision_scope"], "explanation_only")
        self.assertIn("selection_workflow", hit["not_used_for"])
        self.assertIn("final_target_resolution", hit["not_used_for"])
        self.assertIn("position_plan", hit["not_used_for"])
        self.assertIn("b1_b2", hit["not_used_for"])
        self.assertIn("exit_action", hit["not_used_for"])
        self.assertEqual(hit["matched_fact_paths"], ["market.breadth"])

    def test_historical_prior_live_structure_requires_registered_market_fact(self):
        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            {
                "market": {
                    "market_form": "历史类比只提供历史先验，实时结构与模型分歧决定当前解释",
                    "breadth": "短促反弹不等于稳定修复，继续观察修复质量",
                }
            },
            manifest=context["manifest"],
            scenario="daily_report",
            limit=10,
            **TRACE_DATES,
        )

        hit = next(
            item
            for item in trace["hits"]
            if item["knowledge_id"] == "market.historical-prior-live-structure"
        )
        self.assertEqual(hit["decision_scope"], "explanation_only")
        self.assertEqual(
            hit["used_for"],
            ["knowledge_citation", "explanation", "review"],
        )
        self.assertEqual(
            hit["not_used_for"],
            [
                "selection_workflow",
                "final_target_resolution",
                "execution_object",
                "position_plan",
                "b1_b2",
                "old_position_handling",
                "exit_action",
            ],
        )
        self.assertEqual(
            hit["matched_fact_paths"],
            ["market.breadth", "market.market_form"],
        )
        self.assertIn("历史先验与当前结构", hit["matched_conditions"])
        self.assertIn("反弹与稳定修复结构", hit["matched_conditions"])

    def test_historical_prior_question_is_human_routable_but_not_a_production_hit(self):
        human_hits = route_llm_wiki_knowledge(
            {"question": "用诺曼底高空急流解释历史类比会不会刻舟求剑？"},
            scenario="intraday_question",
            limit=10,
        )
        self.assertIn(
            "market.historical-prior-live-structure",
            {item["knowledge_id"] for item in human_hits},
        )

        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            {"question": "用诺曼底高空急流解释历史类比会不会刻舟求剑？"},
            manifest=context["manifest"],
            scenario="daily_report",
            limit=10,
            **TRACE_DATES,
        )

        self.assertNotIn(
            "market.historical-prior-live-structure",
            {item["knowledge_id"] for item in trace["hits"]},
        )
        self.assertIn("knowledge_fact_root_rejected:question", trace["warnings"])

    def test_unknown_or_negated_historical_prior_fact_does_not_create_trace_hit(self):
        context = build_llm_wiki_context()
        unknown_trace = route_llm_wiki_knowledge_trace(
            {"market": {"historical_prior": "历史先验与实时结构"}},
            manifest=context["manifest"],
            scenario="daily_report",
            limit=10,
            **TRACE_DATES,
        )
        negated_trace = route_llm_wiki_knowledge_trace(
            {"market": {"market_form": "并非历史类比，也没有实时结构或模型分歧"}},
            manifest=context["manifest"],
            scenario="daily_report",
            limit=10,
            **TRACE_DATES,
        )

        for trace in (unknown_trace, negated_trace):
            self.assertNotIn(
                "market.historical-prior-live-structure",
                {item["knowledge_id"] for item in trace["hits"]},
            )
        self.assertIn(
            "knowledge_fact_path_rejected:market.historical_prior",
            unknown_trace["warnings"],
        )

    def test_routes_direct_new_high_structure_question(self):
        hits = route_llm_wiki_knowledge(
            {"question": "创新高首次跌到个位数，是否说明趋势生成率扩散断层并可能出现核心补跌？"},
            scenario="intraday_question",
            limit=5,
        )

        ids = [item["knowledge_id"] for item in hits]
        self.assertIn("market.new-high-breadth-contraction", ids)

    def test_routes_absolute_new_high_breadth_level_terms(self):
        for term in ["极致扩散", "有效扩散", "扩散偏冷", "极低扩散", "扩散断层"]:
            with self.subTest(term=term):
                hits = route_llm_wiki_knowledge(
                    {"question": f"创新高全A占比处于{term}时应该怎么理解？"},
                    scenario="intraday_question",
                    limit=5,
                )
                hit = next(
                    item
                    for item in hits
                    if item["knowledge_id"] == "market.new-high-breadth-contraction"
                )
                self.assertIn(term, hit["triggered_by"])
                self.assertIn("绝对水位", hit["impact"])

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

    def test_builds_fact_tags_from_quality_sample_after_empty_candidate_placeholders(self):
        facts = build_llm_wiki_fact_tags(
            {
                "personal_position_context": {
                    "account_profile": {
                        "cash_available": 9800,
                    },
                },
                "watch_anchor": {},
                "market_research_snapshot": {
                    "selected_position_candidate": {},
                },
                "execution_stage_context": {
                    "candidate_quality_samples": [
                        {},
                        {
                            "name": "强核心",
                            "identity": "市场核心",
                            "one_lot_amount": 18000,
                            "status": "过程候选",
                        }
                    ],
                },
            }
        )

        self.assertEqual(facts["account"]["status"], "实际不可买")
        self.assertEqual(facts["candidate"]["identity"], "市场核心")
        self.assertEqual(facts["candidate"]["one_lot_amount"], 18000)

    def test_builds_unbuyable_fact_when_known_cash_is_zero(self):
        facts = build_llm_wiki_fact_tags(
            {
                "account_profile": {"cash_available": 0},
                "selected_position_candidate": {
                    "identity": "市场核心",
                    "one_lot_amount": 18000,
                },
            }
        )

        self.assertEqual(facts["account"]["cash_available"], 0)
        self.assertEqual(facts["account"]["status"], "实际不可买")

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
        self.assertEqual(hit["title"], "节奏复位不新增与边际主线复核")
        self.assertIn("节奏复位不新增", hit["matched_topics"])
        self.assertIn("延后确认不新增", hit["matched_topics"])
        self.assertIn("最终0%不是思考终点", hit["impact"])
        self.assertIn("追溯周五选股、买点、持仓预期和退出纪律", hit["impact"])
        self.assertIn("不替周五或周一正名", hit["impact"])
        self.assertIn("T+1复核", hit["impact"])
        self.assertIn("过程候选不覆盖最终动作", hit["impact"])
        self.assertNotIn("节奏复位空仓", hit["title"] + "".join(hit["matched_topics"]) + hit["impact"])
        self.assertNotIn("延后确认空仓", hit["title"] + "".join(hit["matched_topics"]) + hit["impact"])

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

    def test_routes_sector_label_neutrality_and_cycle_objectivity(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "没有最好的股票，只有最好的周期。板块标签不该分高低，要客观看真实趋势和真实赚钱效应；承认变化不等于参与，科技看不懂时休息也可以。",
            },
            scenario="review",
            limit=5,
        )

        hit = next(item for item in hits if item["knowledge_id"] == "market.performance-rotation-main-attack")
        for required in [
            "没有最好的股票",
            "只有最好的周期",
            "板块标签",
            "真实趋势",
            "真实赚钱效应",
            "承认变化不等于参与",
            "科技看不懂时休息也可以",
        ]:
            self.assertIn(required, hit["triggered_by"])
        self.assertIn("板块标签中性", hit["matched_topics"])
        self.assertIn("周期客观性", hit["matched_topics"])
        self.assertIn("没有天然高低", hit["impact"])
        self.assertIn("不直接生成买入资格", hit["impact"])
        self.assertIn("可以不参与", hit["impact"])

    def test_routes_six_layer_trend_derivation_and_multiscale_analogy(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": (
                    "市场到市场趋势、趋势板块、板块生态、板块中趋势个股、个股的六层推导，"
                    "怎样避免用局部领先的个股反推市场已经转强？王虹三维挂谷猜想有什么多尺度方法启示？"
                ),
            },
            scenario="intraday_question",
            limit=5,
        )

        hit = next(item for item in hits if item["knowledge_id"] == "market.six-layer-trend-derivation")
        for required in [
            "市场趋势",
            "趋势板块",
            "板块生态",
            "板块中趋势个股",
            "六层推导",
            "局部领先",
            "王虹",
            "三维挂谷猜想",
        ]:
            self.assertIn(required, hit["triggered_by"])
        self.assertIn("局部领先不反推市场已经全面修复", hit["impact"])
        self.assertIn("多尺度证据逐层传递", hit["impact"])

    def test_six_layer_trend_trace_uses_registered_structure_facts_only(self):
        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            {
                "market": {
                    "selection_order": "市场→市场趋势→趋势板块→板块生态→板块中趋势个股→个股；局部领先最多B1，不反推市场全面修复",
                    "sector_grid": "趋势板块完成跨日持续、分歧承接、内部扩散和竞争方向对照",
                }
            },
            manifest=context["manifest"],
            scenario="daily_report",
            limit=5,
            **TRACE_DATES,
        )

        hit = next(item for item in trace["hits"] if item["knowledge_id"] == "market.six-layer-trend-derivation")
        self.assertEqual(hit["matched_fact_paths"], ["market.sector_grid", "market.selection_order"])
        self.assertEqual(hit["decision_scope"], "explanation_only")
        for excluded in [
            "selection_workflow",
            "final_target_resolution",
            "position_plan",
            "b1_b2",
            "old_position_handling",
            "exit_action",
        ]:
            self.assertIn(excluded, hit["not_used_for"])

        missing_structure = route_llm_wiki_knowledge_trace(
            {"market": {"selection_order": "个股强势可以反推市场已经转强"}},
            manifest=context["manifest"],
            scenario="daily_report",
            limit=5,
            **TRACE_DATES,
        )
        self.assertNotIn(
            "market.six-layer-trend-derivation",
            {item["knowledge_id"] for item in missing_structure["hits"]},
        )

    def test_sector_label_cycle_trace_requires_registered_positive_fact(self):
        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            {
                "market": {
                    "market_form": "板块标签中性；没有最好的股票，只有最好的周期；客观看真实趋势和真实赚钱效应；承认变化不等于参与",
                }
            },
            manifest=context["manifest"],
            scenario="daily_report",
            limit=5,
            **TRACE_DATES,
        )

        hit = next(item for item in trace["hits"] if item["knowledge_id"] == "market.performance-rotation-main-attack")
        self.assertIn("板块标签与周期事实", hit["matched_conditions"])
        self.assertEqual(hit["matched_fact_paths"], ["market.market_form"])
        self.assertEqual(hit["decision_scope"], "explanation_only")
        for excluded in [
            "selection_workflow",
            "final_target_resolution",
            "position_plan",
            "b1_b2",
            "old_position_handling",
            "exit_action",
        ]:
            self.assertIn(excluded, hit["not_used_for"])

        negated = route_llm_wiki_knowledge_trace(
            {
                "market": {
                    "market_form": "并非只有最好的周期，也没有真实趋势或真实赚钱效应",
                }
            },
            manifest=context["manifest"],
            scenario="daily_report",
            limit=5,
            **TRACE_DATES,
        )
        self.assertNotIn(
            "market.performance-rotation-main-attack",
            {item["knowledge_id"] for item in negated["hits"]},
        )

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
        self.assertIn("明日标的为空时", hit["impact"])
        self.assertNotIn("明日无新目标", hit["impact"])

    def test_routes_explicit_tomorrow_empty_to_account_zero_semantics(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "日报写明日空仓时，旧仓是不是集合竞价卖清，新股不买，也不做T？",
                "position": {"state": "旧仓", "name": "长电科技"},
            },
            scenario="daily_report",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "discipline.tomorrow-empty-position-semantics")
        self.assertIn("明日空仓", hit["triggered_by"])
        self.assertIn("集合竞价卖清全部可卖旧仓", hit["impact"])
        self.assertIn("未清完不能称空仓", hit["impact"])
        self.assertIn("覆盖已经失败、待10:10复核和正常T+2", hit["impact"])
        self.assertIn("明日新仓0%只表示不新增参与", hit["impact"])

    def test_routes_non_empty_position_phrases_to_distinction_without_timing_override(self):
        cases = [
            ("明日新仓0%时旧仓怎么办", "明日新仓0%", "只表示不新增参与"),
            ("明日标的为空时旧仓怎么办", "明日标的为空", "明日标的为空同理"),
            ("当前空仓明天还能不能买", "当前空仓", "只描述当前账户事实"),
            ("持仓未知时能不能写账户为0", "持仓未知", "持仓未知保持待确认"),
        ]

        for question, trigger, distinction in cases:
            with self.subTest(question=question):
                hits = route_llm_wiki_knowledge({"question": question}, scenario="daily_report")
                hit = next(
                    item
                    for item in hits
                    if item["knowledge_id"] == "discipline.tomorrow-empty-position-semantics"
                )
                self.assertIn(trigger, hit["triggered_by"])
                self.assertIn(distinction, hit["impact"])
                self.assertIn("这四种情况都不触发上述覆盖", hit["impact"])

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

    def test_routes_unplanned_profit_to_fresh_entry_qualification(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "日报没有标的，我擅自计划外买入后涨了8%，是不是说明这笔交易其实做对了？",
            },
            scenario="review",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "discipline.unplanned-profit-qualification")
        self.assertIn("计划外", hit["triggered_by"])
        self.assertIn("计划外买入", hit["triggered_by"])
        self.assertIn("涨了8%", hit["triggered_by"])
        self.assertIn("不能证明计划外交易正确", hit["impact"])
        self.assertIn("独立重新取得买入资格", hit["impact"])

    def test_routes_loss_aversion_and_fear_of_missing_rebound(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "旧仓已经失败，集合竞价低开我又加仓做T，现在怕卖出后反弹卖飞，能不能继续拿？",
                "position": {"state": "满仓亏损", "decision_class": "failed"},
            },
            scenario="intraday_question",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "position.failed-position-loss-aversion")
        self.assertIn("低开我又加仓", hit["triggered_by"])
        self.assertIn("加仓做T", hit["triggered_by"])
        self.assertIn("卖飞", hit["triggered_by"])
        self.assertIn("不是做T", hit["impact"])
        self.assertIn("不能覆盖失败仓退出", hit["impact"])

    def test_routes_dragon_tiger_list_to_sample_boundary(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "华天科技龙虎榜净买为正，能否证明全市场主力看多，只是榜外小额资金合力踩踏？",
            },
            scenario="review",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "evidence.dragon-tiger-list-sample-boundary")
        self.assertIn("龙虎榜", hit["triggered_by"])
        self.assertIn("净买为正", hit["triggered_by"])
        self.assertIn("榜外小额资金", hit["triggered_by"])
        self.assertIn("只覆盖上榜席位样本", hit["impact"])
        self.assertIn("不能代表全市场主力方向", hit["impact"])
        self.assertIn("不能推导榜外资金行为", hit["impact"])

    def test_routes_long_industry_thesis_away_from_failed_short_trade(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "我想不出2027年除了存储还有什么板块值得参与，长期产业逻辑能不能让我继续拿短线失败仓？",
            },
            scenario="review",
        )

        hit = next(item for item in hits if item["knowledge_id"] == "discipline.long-thesis-short-failure-separation")
        self.assertIn("2027", hit["triggered_by"])
        self.assertIn("存储", hit["triggered_by"])
        self.assertIn("长期产业逻辑", hit["triggered_by"])
        self.assertIn("短线失败仓", hit["triggered_by"])
        self.assertIn("不能给短线失败仓续命", hit["impact"])
        self.assertIn("重新取得持仓资格", hit["impact"])

    def test_does_not_route_failed_position_or_long_thesis_from_general_holding_words(self):
        cases = [
            "科技板块今天强吗",
            "我想继续拿这只盈利股",
        ]

        for question in cases:
            with self.subTest(question=question):
                hits = route_llm_wiki_knowledge({"question": question}, scenario="intraday_question")
                ids = [item["knowledge_id"] for item in hits]
                self.assertNotIn("position.failed-position-loss-aversion", ids)
                self.assertNotIn("discipline.long-thesis-short-failure-separation", ids)

    def test_does_not_route_dragon_tiger_boundary_from_generic_list_lookup(self):
        hits = route_llm_wiki_knowledge(
            {"question": "龙虎榜今天有哪些"},
            scenario="review",
        )

        ids = [item["knowledge_id"] for item in hits]
        self.assertNotIn("evidence.dragon-tiger-list-sample-boundary", ids)

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

    def test_maps_v2_same_stock_satisfied_plan_to_zero_current_entry(self):
        facts = build_llm_wiki_fact_tags(
            {
                "final_target_resolution": {
                    "existing_position_target": {"name": "太极实业", "code": "600667"},
                    "new_entry_target": {"name": "太极实业", "code": "600667"},
                    "account_exposure_plan": {
                        "schema_version": "position_tier_exposure.v2",
                        "old_position_pct": 50,
                        "old_position_x": 1,
                        "planned_new_entry_pct": 50,
                        "planned_new_entry_x": 1,
                        "new_entry_pct": 0,
                        "new_entry_x": 0,
                        "same_stock_target": True,
                        "same_stock_t": False,
                    },
                }
            }
        )

        self.assertEqual(facts["position"]["state"], "旧仓")
        self.assertIn("当前0%新增", facts["position"]["action"])
        self.assertIn("不重复B1", facts["position"]["action"])
        self.assertIn("计划总档1x/50%", facts["decision"]["position_plan"])
        self.assertIn("当前新增0%", facts["decision"]["position_plan"])
        self.assertNotIn("同股T", facts["position"]["action"])

    def test_maps_v2_same_stock_b2_to_one_x_current_increment(self):
        facts = build_llm_wiki_fact_tags(
            {
                "final_target_resolution": {
                    "existing_position_target": {"name": "太极实业", "code": "600667"},
                    "new_entry_target": {"name": "太极实业", "code": "600667"},
                    "account_exposure_plan": {
                        "schema_version": "position_tier_exposure.v2",
                        "old_position_pct": 50,
                        "old_position_x": 1,
                        "planned_new_entry_pct": 100,
                        "planned_new_entry_x": 2,
                        "new_entry_pct": 50,
                        "new_entry_x": 1,
                        "same_stock_target": True,
                        "same_stock_t": True,
                    },
                }
            }
        )
        hits = route_llm_wiki_knowledge(facts, scenario="daily_report", limit=5)

        self.assertIn("当前只新增1x/50%=B2", facts["position"]["action"])
        self.assertIn("总仓位2x/100%", facts["position"]["action"])
        self.assertIn("计划总档2x/100%", facts["decision"]["position_plan"])
        ids = [hit["knowledge_id"] for hit in hits]
        self.assertIn("position.position-tier-exposure-contract", ids)
        self.assertIn("intraday.same-stock-t-failure-control", ids)

    def test_maps_v2_different_stock_two_legs_to_two_x_total(self):
        facts = build_llm_wiki_fact_tags(
            {
                "final_target_resolution": {
                    "existing_position_target": {"name": "太极实业", "code": "600667"},
                    "new_entry_target": {"name": "深科技", "code": "000021"},
                    "account_exposure_plan": {
                        "schema_version": "position_tier_exposure.v2",
                        "old_position_pct": 50,
                        "old_position_x": 1,
                        "planned_new_entry_pct": 50,
                        "planned_new_entry_x": 1,
                        "new_entry_pct": 50,
                        "new_entry_x": 1,
                        "same_stock_target": False,
                        "same_stock_t": False,
                    },
                }
            }
        )

        self.assertIn("不同股旧仓1x/50% + 当前新仓1x/50%", facts["position"]["action"])
        self.assertIn("账户合计2x/100%", facts["position"]["action"])
        self.assertNotIn("200%", str(facts))

    def test_routes_direct_position_tier_question_to_exact_contract(self):
        hits = route_llm_wiki_knowledge(
            {"question": "1x和2x仓位分别是多少？B1和B2分别代表什么？"},
            scenario="intraday_question",
            limit=5,
        )

        hit = next(item for item in hits if item["knowledge_id"] == "position.position-tier-exposure-contract")
        self.assertIn("0=0%不参与", hit["impact"])
        self.assertIn("1x=50%半仓=B1参与权", hit["impact"])
        self.assertIn("2x=100%满仓=B1+B2", hit["impact"])
        self.assertIn("planned_new_entry_pct/x是计划总档", hit["impact"])
        self.assertIn("new_entry_pct/x是当前新增档", hit["impact"])
        self.assertNotIn("200%暴露", hit["impact"])

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

    def test_routes_trend_graphic_narrative_cycle_to_brooks_framework(self):
        hits = route_llm_wiki_knowledge(
            {
                "question": "当前是趋势交易、图形交易、叙事交易和小作文段子交易的周期，逻辑和信息只是引子和助燃剂，只交易趋势时怎样避免亏损后出现策略身份漂移？",
            },
            scenario="intraday_question",
            limit=5,
        )

        hit = next(
            item
            for item in hits
            if item["knowledge_id"] == "price-action.brooks-trend-framework"
        )
        for trigger in [
            "趋势交易",
            "图形交易",
            "叙事交易",
            "小作文段子交易",
            "策略身份漂移",
            "引子和助燃剂",
            "只交易趋势",
        ]:
            self.assertIn(trigger, hit["triggered_by"])

    def test_trend_cycle_trace_still_requires_price_confirmation(self):
        context = build_llm_wiki_context()
        phrase_only = route_llm_wiki_knowledge_trace(
            {"candidate": {"quality": "趋势交易周期"}},
            manifest=context["manifest"],
            limit=5,
            **TRACE_DATES,
        )
        confirmed = route_llm_wiki_knowledge_trace(
            {
                "position": {
                    "capital_priority_reason": "趋势交易周期中趋势仍在，且失效线清楚",
                }
            },
            manifest=context["manifest"],
            limit=5,
            **TRACE_DATES,
        )

        knowledge_id = "price-action.brooks-trend-framework"
        self.assertNotIn(knowledge_id, {item["knowledge_id"] for item in phrase_only["hits"]})
        hit = next(item for item in confirmed["hits"] if item["knowledge_id"] == knowledge_id)
        self.assertEqual(hit["matched_fact_paths"], ["position.capital_priority_reason"])
        self.assertEqual(hit["decision_scope"], "explanation_only")
        self.assertIn("selection_workflow", hit["not_used_for"])
        self.assertIn("position_plan", hit["not_used_for"])

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

    def test_explicit_facts_only_accept_whitelisted_roots_and_report_rejections(self):
        bundle = build_llm_wiki_fact_bundle(
            {
                "knowledge_hit_facts": {
                    "market": {"index_trend": "上涨", "breadth": "上涨家数偏弱"},
                    "account": {"status": "实际不可买"},
                    "question": "指数上涨",
                    "selection_workflow": {"final": {"position_pct": 100}},
                }
            }
        )

        self.assertEqual(bundle["facts_source"], "explicit")
        self.assertEqual(set(bundle["facts"]), {"market", "account"})
        self.assertIn("knowledge_fact_root_rejected:question", bundle["warnings"])
        self.assertIn("knowledge_fact_root_rejected:selection_workflow", bundle["warnings"])
        self.assertEqual(
            bundle["fact_sources"]["market.index_trend"],
            {
                "source": "explicit",
                "input_path": "knowledge_hit_facts.market.index_trend",
            },
        )

    def test_explicit_facts_reject_unknown_nested_paths_before_routing(self):
        bundle = build_llm_wiki_fact_bundle(
            {
                "knowledge_hit_facts": {
                    "market": {
                        "index_trend": "下跌",
                        "forged": "结构性行情 全市场水池",
                    },
                    "candidate": {"unknown": "实际不可买"},
                }
            }
        )

        self.assertEqual(bundle["facts"], {"market": {"index_trend": "下跌"}})
        self.assertIn("knowledge_fact_path_rejected:market.forged", bundle["warnings"])
        self.assertIn("knowledge_fact_path_rejected:candidate.unknown", bundle["warnings"])
        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            bundle["facts"],
            manifest=context["manifest"],
            facts_source=bundle["facts_source"],
            fact_sources=bundle["fact_sources"],
            warnings=bundle["warnings"],
            limit=10,
            **TRACE_DATES,
        )

        ids = {item["knowledge_id"] for item in trace["hits"]}
        self.assertNotIn("market.sector-grid-first-selection", ids)
        self.assertNotIn("account.unbuyable-core-anchor", ids)

    def test_trace_entry_rejects_unknown_nested_fact_paths(self):
        context = build_llm_wiki_context()

        trace = route_llm_wiki_knowledge_trace(
            {
                "market": {
                    "index_trend": "下跌",
                    "forged": "结构性行情 全市场水池",
                },
                "candidate": {"unknown": "实际不可买"},
            },
            manifest=context["manifest"],
            limit=10,
            **TRACE_DATES,
        )

        ids = {item["knowledge_id"] for item in trace["hits"]}
        self.assertNotIn("market.sector-grid-first-selection", ids)
        self.assertNotIn("account.unbuyable-core-anchor", ids)
        self.assertIn("knowledge_fact_path_rejected:market.forged", trace["warnings"])
        self.assertIn("knowledge_fact_path_rejected:candidate.unknown", trace["warnings"])
        self.assertEqual(set(trace["fact_sources"]), {"market.index_trend"})

    def test_trace_replaces_unverified_fact_source_with_canonical_origin(self):
        context = build_llm_wiki_context()

        trace = route_llm_wiki_knowledge_trace(
            {"market": {"breadth": "上涨家数偏弱"}},
            manifest=context["manifest"],
            facts_source="explicit",
            fact_sources={
                "market.breadth": {
                    "source": "official",
                    "input_path": "forged://not-a-source",
                },
                "market.forged": {
                    "source": "explicit",
                    "input_path": "knowledge_hit_facts.market.forged",
                },
            },
            **TRACE_DATES,
        )

        self.assertEqual(
            trace["fact_sources"],
            {
                "market.breadth": {
                    "source": "explicit",
                    "input_path": "knowledge_hit_facts.market.breadth",
                }
            },
        )
        self.assertIn("knowledge_fact_source_rejected:market.breadth", trace["warnings"])
        self.assertIn(
            "knowledge_fact_source_path_rejected:market.forged",
            trace["warnings"],
        )

    def test_trace_is_stable_and_links_rank_score_fact_paths_and_source_hash(self):
        context = build_llm_wiki_context(target_date="2026-07-16", query_date="2026-07-17")
        facts = {
            "market": {
                "index_trend": "上涨",
                "breadth": "上涨家数偏弱",
                "turnover_distribution": "成交集中",
            }
        }

        first = route_llm_wiki_knowledge_trace(
            facts,
            manifest=context["manifest"],
            target_date="2026-07-16",
            query_date="2026-07-17",
        )
        second = route_llm_wiki_knowledge_trace(
            facts,
            manifest=context["manifest"],
            target_date="2026-07-16",
            query_date="2026-07-17",
        )

        self.assertEqual(first["trace_hash"], second["trace_hash"])
        self.assertEqual(first["facts_hash"], second["facts_hash"])
        self.assertEqual(first["manifest_hash"], context["manifest_hash"])
        hit = next(item for item in first["hits"] if item["knowledge_id"] == "market.low-frequency-focus")
        manifest_entry = next(
            item
            for item in context["manifest"]["entries"]
            if item["knowledge_id"] == hit["knowledge_id"]
        )
        self.assertGreaterEqual(hit["score"], 1)
        self.assertGreaterEqual(hit["rank"], 1)
        self.assertIn("market.breadth", hit["matched_fact_paths"])
        self.assertEqual(hit["source_ref"]["content_hash"], manifest_entry["source_ref"]["content_hash"])
        self.assertEqual(hit["decision_scope"], "explanation_only")
        self.assertIn("selection_workflow", hit["not_used_for"])
        self.assertEqual(
            hit["matched_fact_sources"],
            [
                {
                    "path": "market.breadth",
                    "source": "derived",
                    "input_path": "market.breadth",
                },
                {
                    "path": "market.index_trend",
                    "source": "derived",
                    "input_path": "market.index_trend",
                },
                {
                    "path": "market.turnover_distribution",
                    "source": "derived",
                    "input_path": "market.turnover_distribution",
                },
            ],
        )

    def test_trace_requires_target_and_query_dates_before_hits_are_usable(self):
        context = build_llm_wiki_context()
        facts = {"market": {"breadth": "上涨家数偏弱"}}

        missing_both = route_llm_wiki_knowledge_trace(
            facts,
            manifest=context["manifest"],
        )
        missing_query = route_llm_wiki_knowledge_trace(
            facts,
            manifest=context["manifest"],
            target_date="2026-07-16",
        )
        invalid_target = route_llm_wiki_knowledge_trace(
            facts,
            manifest=context["manifest"],
            target_date="not-a-date",
            query_date="2026-07-17",
        )
        invalid_query = route_llm_wiki_knowledge_trace(
            facts,
            manifest=context["manifest"],
            target_date="2026-07-16",
            query_date="2026-02-30",
        )
        noncanonical_target = route_llm_wiki_knowledge_trace(
            facts,
            manifest=context["manifest"],
            target_date=" 2026-07-16",
            query_date="2026-07-17",
        )
        noncanonical_query = route_llm_wiki_knowledge_trace(
            facts,
            manifest=context["manifest"],
            target_date="2026-07-16",
            query_date="2026-07-17 ",
        )

        self.assertEqual(missing_both["availability"], "invalid")
        self.assertEqual(missing_both["hits"], [])
        self.assertIn("目标交易日缺失，知识引用日期无法核对", missing_both["warnings"])
        self.assertIn("查询日期缺失，知识引用时间无法核对", missing_both["warnings"])
        self.assertEqual(missing_query["availability"], "invalid")
        self.assertEqual(missing_query["hits"], [])
        self.assertNotIn("目标交易日缺失，知识引用日期无法核对", missing_query["warnings"])
        self.assertIn("查询日期缺失，知识引用时间无法核对", missing_query["warnings"])
        self.assertEqual(invalid_target["availability"], "invalid")
        self.assertEqual(invalid_target["hits"], [])
        self.assertIn("目标交易日格式无效，知识引用日期无法核对", invalid_target["warnings"])
        self.assertEqual(invalid_query["availability"], "invalid")
        self.assertEqual(invalid_query["hits"], [])
        self.assertIn("查询日期格式无效，知识引用时间无法核对", invalid_query["warnings"])
        self.assertEqual(noncanonical_target["availability"], "invalid")
        self.assertEqual(noncanonical_target["hits"], [])
        self.assertIn("目标交易日格式无效，知识引用日期无法核对", noncanonical_target["warnings"])
        self.assertEqual(noncanonical_query["availability"], "invalid")
        self.assertEqual(noncanonical_query["hits"], [])
        self.assertIn("查询日期格式无效，知识引用时间无法核对", noncanonical_query["warnings"])

    def test_trace_uses_text_only_for_recall_and_structured_path_for_confirmation(self):
        context = build_llm_wiki_context()
        wrong_path = route_llm_wiki_knowledge_trace(
            {"account": {"status": "上涨家数偏弱"}},
            manifest=context["manifest"],
            limit=10,
            **TRACE_DATES,
        )
        confirmed = route_llm_wiki_knowledge_trace(
            {"market": {"breadth": "上涨家数偏弱"}},
            manifest=context["manifest"],
            limit=10,
            **TRACE_DATES,
        )
        legacy = route_llm_wiki_knowledge(
            {"question": "上涨家数偏弱"},
            scenario="daily_report",
            limit=10,
        )

        self.assertNotIn(
            "market.low-frequency-focus",
            {item["knowledge_id"] for item in wrong_path["hits"]},
        )
        self.assertIn(
            "market.low-frequency-focus",
            {item["knowledge_id"] for item in confirmed["hits"]},
        )
        self.assertIn(
            "market.low-frequency-focus",
            {item["knowledge_id"] for item in legacy},
        )

    def test_legacy_list_router_ignores_unregistered_fact_roots(self):
        unknown_only = route_llm_wiki_knowledge(
            {"unrelated": "指数上涨，上涨家数偏弱，成交集中"},
            scenario="daily_report",
            limit=10,
        )
        mixed = route_llm_wiki_knowledge(
            {
                "market": {"breadth": "普涨"},
                "unrelated": "指数上涨，上涨家数偏弱，成交集中",
            },
            scenario="daily_report",
            limit=10,
        )

        self.assertEqual(unknown_only, [])
        self.assertNotIn(
            "market.low-frequency-focus",
            {item["knowledge_id"] for item in mixed},
        )

    def test_trace_hash_tracks_facts_and_manifest_changes(self):
        context = build_llm_wiki_context()
        facts = {"market": {"index_trend": "上涨", "breadth": "上涨家数偏弱"}}
        first = route_llm_wiki_knowledge_trace(
            facts,
            manifest=context["manifest"],
            **TRACE_DATES,
        )
        changed_facts = route_llm_wiki_knowledge_trace(
            {"market": {"index_trend": "上涨", "breadth": "普涨"}},
            manifest=context["manifest"],
            **TRACE_DATES,
        )
        changed_manifest = dict(context["manifest"])
        changed_manifest["manifest_hash"] = "manifest-changed"
        changed_version = route_llm_wiki_knowledge_trace(
            facts,
            manifest=changed_manifest,
            **TRACE_DATES,
        )

        self.assertNotEqual(first["facts_hash"], changed_facts["facts_hash"])
        self.assertNotEqual(first["trace_hash"], changed_facts["trace_hash"])
        self.assertNotEqual(first["manifest_hash"], changed_version["manifest_hash"])
        self.assertNotEqual(first["trace_hash"], changed_version["trace_hash"])

    def test_trace_rejects_self_hashed_manifest_with_invalid_source_hash(self):
        context = build_llm_wiki_context()
        invalid_manifest = copy.deepcopy(context["manifest"])
        source_path = invalid_manifest["entries"][0]["source_ref"]["path"]
        invalid_manifest["entries"][0]["source_ref"]["content_hash"] = "not-a-sha256"
        source_ref = next(
            item for item in invalid_manifest["sources"] if item["path"] == source_path
        )
        source_ref["content_hash"] = "not-a-sha256"
        invalid_manifest["manifest_hash"] = stable_json_hash(
            invalid_manifest,
            excluded_keys={"manifest_hash"},
        )

        trace = route_llm_wiki_knowledge_trace(
            {"market": {"index_trend": "上涨", "breadth": "上涨家数偏弱"}},
            manifest=invalid_manifest,
            **TRACE_DATES,
        )

        self.assertEqual(trace["availability"], "invalid")
        self.assertEqual(trace["hits"], [])
        self.assertTrue(any(item.startswith("source_hash_invalid:") for item in trace["warnings"]))

    def test_trace_reports_malformed_or_declared_invalid_manifest(self):
        for malformed in (None, [], 1, "invalid"):
            with self.subTest(manifest=malformed):
                trace = route_llm_wiki_knowledge_trace(
                    {},
                    manifest=malformed,
                    **TRACE_DATES,
                )
                self.assertEqual(trace["availability"], "invalid")
                self.assertEqual(trace["hits"], [])
                self.assertIn("manifest_type_invalid", trace["warnings"])
                self.assertIn(
                    "知识清单缺失或格式无效，停止生成知识引用",
                    trace["warnings"],
                )

        malformed_trace = route_llm_wiki_knowledge_trace(
            {},
            manifest={"errors": 1},
            **TRACE_DATES,
        )
        self.assertEqual(malformed_trace["availability"], "invalid")
        self.assertEqual(malformed_trace["hits"], [])
        self.assertIn("manifest_field_type_invalid:errors", malformed_trace["warnings"])
        self.assertIn(
            "知识清单缺失或格式无效，停止生成知识引用",
            malformed_trace["warnings"],
        )

        malformed_entry = copy.deepcopy(build_llm_wiki_context()["manifest"])
        knowledge_id = malformed_entry["entries"][0]["knowledge_id"]
        malformed_entry["entries"][0]["report_slots"] = 1
        malformed_entry["manifest_hash"] = stable_json_hash(
            malformed_entry,
            excluded_keys={"manifest_hash"},
        )
        malformed_entry_trace = route_llm_wiki_knowledge_trace(
            {},
            manifest=malformed_entry,
            **TRACE_DATES,
        )
        self.assertEqual(malformed_entry_trace["availability"], "invalid")
        self.assertEqual(malformed_entry_trace["hits"], [])
        self.assertIn(
            f"entry_field_type_invalid:{knowledge_id}:report_slots",
            malformed_entry_trace["warnings"],
        )

        declared_invalid = copy.deepcopy(build_llm_wiki_context()["manifest"])
        declared_invalid["availability"] = "invalid"
        declared_invalid["warnings"] = []
        declared_invalid["errors"] = []
        declared_invalid["manifest_hash"] = stable_json_hash(
            declared_invalid,
            excluded_keys={"manifest_hash"},
        )
        invalid_trace = route_llm_wiki_knowledge_trace(
            {},
            manifest=declared_invalid,
            **TRACE_DATES,
        )
        self.assertEqual(invalid_trace["availability"], "invalid")
        self.assertEqual(invalid_trace["hits"], [])
        self.assertIn(
            "知识清单缺失或格式无效，停止生成知识引用",
            invalid_trace["warnings"],
        )

    def test_trace_reports_non_mapping_facts_without_raising(self):
        manifest = build_llm_wiki_context()["manifest"]
        for malformed in ([], 1, "invalid"):
            with self.subTest(facts=malformed):
                trace = route_llm_wiki_knowledge_trace(
                    malformed,
                    manifest=manifest,
                    **TRACE_DATES,
                )

                self.assertEqual(trace["availability"], "invalid")
                self.assertEqual(trace["hits"], [])
                self.assertIn("knowledge_facts_type_invalid", trace["warnings"])

    def test_trace_rejects_manifest_condition_outside_fact_path_allowlist(self):
        manifest = copy.deepcopy(build_llm_wiki_context()["manifest"])
        entry = next(
            item
            for item in manifest["entries"]
            if item["knowledge_id"] == "market.low-frequency-focus"
        )
        entry["fact_conditions"] = {
            "must_any": [
                {"path": "market", "equals": "上涨", "label": "过宽父路径"},
            ]
        }
        manifest["manifest_hash"] = stable_json_hash(
            manifest,
            excluded_keys={"manifest_hash"},
        )

        trace = route_llm_wiki_knowledge_trace(
            {"market": {"index_trend": "上涨"}},
            manifest=manifest,
            **TRACE_DATES,
        )

        self.assertEqual(trace["availability"], "invalid")
        self.assertEqual(trace["hits"], [])
        self.assertIn(
            "fact_condition_path_invalid:market.low-frequency-focus:market",
            trace["warnings"],
        )

    def test_trace_keeps_decision_boundary_when_no_entries_match(self):
        trace = route_llm_wiki_knowledge_trace(
            {},
            manifest=build_llm_wiki_context()["manifest"],
            **TRACE_DATES,
        )

        self.assertEqual(trace["hits"], [])
        self.assertEqual(trace["decision_scope"], "explanation_only")
        self.assertIn("selection_workflow", trace["not_used_for"])

    def test_trace_rejects_self_hashed_manifest_with_forged_valid_source_hash(self):
        context = build_llm_wiki_context()
        forged_manifest = copy.deepcopy(context["manifest"])
        source_path = forged_manifest["entries"][0]["source_ref"]["path"]
        for entry in forged_manifest["entries"]:
            if entry["source_ref"]["path"] == source_path:
                entry["source_ref"]["content_hash"] = "0" * 64
        source_ref = next(
            item for item in forged_manifest["sources"] if item["path"] == source_path
        )
        source_ref["content_hash"] = "0" * 64
        forged_manifest["manifest_hash"] = stable_json_hash(
            forged_manifest,
            excluded_keys={"manifest_hash"},
        )

        trace = route_llm_wiki_knowledge_trace(
            {"market": {"index_trend": "上涨", "breadth": "上涨家数偏弱"}},
            manifest=forged_manifest,
            **TRACE_DATES,
        )

        self.assertEqual(trace["availability"], "invalid")
        self.assertEqual(trace["hits"], [])
        self.assertIn(
            f"source_content_hash_mismatch:{source_path}",
            trace["warnings"],
        )

    def test_negative_text_and_field_names_do_not_create_knowledge_hits(self):
        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            {
                "market": {"index_trend": "下跌"},
                "龙虎榜": "没有龙虎榜证据，不能代表主力方向",
                "question": "并非指数上涨，也没有上涨家数偏弱或成交集中",
            },
            manifest=context["manifest"],
            scenario="daily_report",
            limit=10,
            **TRACE_DATES,
        )

        ids = {item["knowledge_id"] for item in trace["hits"]}
        self.assertNotIn("market.low-frequency-focus", ids)
        self.assertNotIn("evidence.dragon-tiger-list-sample-boundary", ids)

    def test_negative_marker_in_one_fact_does_not_suppress_other_fact_leaves(self):
        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            {
                "account": {"status": "实际不可买"},
                "candidate": {
                    "identity": "市场核心",
                    "quality": ["候选质量", "动作上限"],
                },
                "decision": {
                    "position_plan": "0%不参与",
                    "action_layer": "只观察",
                    "b1_role": "参与权",
                    "b2_role": "确认权",
                    "response_script": ["B1", "B2"],
                },
            },
            manifest=context["manifest"],
            scenario="daily_report",
            limit=5,
            **TRACE_DATES,
        )

        ids = {item["knowledge_id"] for item in trace["hits"]}
        self.assertIn("candidate.quality-action-layer", ids)
        response_hit = next(
            item
            for item in trace["hits"]
            if item["knowledge_id"] == "decision.anti-prediction-response-script"
        )
        self.assertIn("B1", response_hit["triggered_by"])
        self.assertIn("B2", response_hit["triggered_by"])

    def test_negated_structured_condition_does_not_create_trace_hit(self):
        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            {"decision": {"position_plan": "不是0%不参与"}},
            manifest=context["manifest"],
            scenario="daily_report",
            limit=10,
            **TRACE_DATES,
        )

        ids = {item["knowledge_id"] for item in trace["hits"]}
        self.assertNotIn("decision.anti-prediction-response-script", ids)

    def test_newline_inside_one_fact_does_not_reset_negation_scope(self):
        context = build_llm_wiki_context()
        trace = route_llm_wiki_knowledge_trace(
            {
                "decision": {
                    "action_layer": "只观察",
                    "response_script": "没有B1\nB2",
                }
            },
            manifest=context["manifest"],
            scenario="daily_report",
            limit=10,
            **TRACE_DATES,
        )

        hit = next(
            item
            for item in trace["hits"]
            if item["knowledge_id"] == "decision.anti-prediction-response-script"
        )
        self.assertNotIn("B1", hit["triggered_by"])
        self.assertNotIn("B2", hit["triggered_by"])


if __name__ == "__main__":
    unittest.main()
