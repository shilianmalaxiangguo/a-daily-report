import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from hooks.report.use_report_sections import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseReportSectionsTest(unittest.TestCase):
    def test_report_sections_compose_from_knowledge_and_action_plan(self):
        ctx = build_empty_context({"target_date": "2026-04-22"})
        ctx = merge_hook_patches(
            ctx,
            {
                "derived": {
                    "market_phase": {"phase": "observe"},
                    "mainline": {"primary_line": "军工"},
                    "strategy_contract": {
                        "contract_label": "conditional_entry",
                        "contract_logic_digest_text": "先选边站队，再等确认",
                    },
                    "report_stages": [
                        {"stage_key": "market_environment", "title": "市场环境", "summary": "环境可做", "status": "ready"},
                        {"stage_key": "selection_focus", "title": "主线与筛选", "summary": "军工最强", "status": "ready"},
                        {"stage_key": "execution_gate", "title": "执行" + "门" + "控", "summary": "等预演参与窗口", "status": "blocked"},
                    ],
                },
                "decision": {
                    "execution_permission": {"label": "attack_50_ready"},
                    "action_plan": {
                        "action_label": "execute_50",
                        "headline": "沿军工进入50%标准进攻",
                        "trigger": "次日完成竞价表态、开盘承接或结构确认参与窗口",
                        "rationale": "环境未坏，主线清晰",
                    },
                },
                "knowledge": {
                    "trading_philosophy": {
                        "version": "2026-04-22",
                        "source": "skillhub",
                        "source_path": "/tmp/source.md",
                        "main_derivation_chain_text": "结构中枢周期 -> 市场环境 -> 主线",
                        "decision_gate_chain_text": "环境可做 -> 主线确认 -> 参与窗口确认",
                        "execution_framework_text": "日线结构中枢定环境，60分钟定买点，30分钟定止损",
                        "contract_logic_digest_text": "先选边站队，再等确认",
                        "report_preamble_lines": ["# 2026-04-22 A股日报"],
                    }
                },
            },
        )

        result = run(ctx)

        sections = result["patches"]["sections"]
        self.assertEqual(sections["preamble"], "# 2026-04-22 A股日报")
        self.assertIn("主推导链", sections["environment"])
        self.assertIn("阶段看板", sections["observation"])
        self.assertIn("selection_focus", sections["observation"])
        self.assertIn("先选边站队，再等确认", sections["observation"])
        self.assertIn("沿军工进入50%标准进攻", sections["execution"])
        self.assertNotIn(_m("30%", "条件试错"), sections["execution"])
        self.assertNotIn("attack_50_ready", sections["execution"])
        self.assertNotIn(_m("执行", "门", "控"), sections["observation"] + sections["execution"])
        self.assertNotIn(_m("环境", "放", "行"), sections["observation"] + sections["execution"])
        self.assertIn("执行条件", sections["observation"] + sections["execution"])
        self.assertIn("交易思想版本：2026-04-22", sections["review"])
        self.assertNotIn("知识复利提示", sections["review"])
        self.assertIn("strategy_contract: conditional_entry", sections["summary"])
        self.assertIn("market_environment", sections["summary"])

    def test_report_sections_surface_ai_friction_only_when_knowledge_update_is_active(self):
        ctx = build_empty_context(
            {
                "target_date": "2026-05-26",
                "knowledge_updates": [
                    {
                        "topic": "AI摩擦与知识复利",
                        "source_path": "wiki/交易思想/AI摩擦与知识复利.md",
                    }
                ],
            }
        )
        ctx = merge_hook_patches(
            ctx,
            {
                "knowledge": {
                    "trading_philosophy": {
                        "version": "2026-04-22",
                        "source": "skillhub",
                        "source_path": "/tmp/source.md",
                        "report_preamble_lines": ["# 2026-05-26 A股日报"],
                    },
                    "llm_wiki": {
                        "version": "2026-05-26",
                        "source": "llm_wiki",
                        "field_mappings": [
                            "AI摩擦与知识复利 -> 消除低效摩擦后必须补上反馈机制；复利方向由接入过程决定，知识节点碰撞形成个人护城河",
                            "必要认知摩擦 -> AI生成后至少复述、重写、对比或沉淀成知识节点，避免只复制结果",
                        ],
                    },
                },
            },
        )

        result = run(ctx)

        review = result["patches"]["sections"]["review"]
        self.assertIn("知识复利提示", review)
        self.assertIn("复利方向：用反馈机制校准新知识，避免只堆积结论。", review)
        self.assertIn("必要认知摩擦：复述、重写、对比或沉淀成知识节点。", review)
        self.assertIn("日报落点：只记录字段化结论，不把文章长文带入交易主链。", review)
        self.assertNotIn("摩擦是资产不是成本", review)
        self.assertNotIn("认知投降", review)

    def test_report_sections_hide_knowledge_compounding_candidates_when_absent(self):
        ctx = build_empty_context({"target_date": "2026-05-26"})
        ctx = merge_hook_patches(
            ctx,
            {
                "knowledge": {
                    "trading_philosophy": {
                        "version": "2026-04-22",
                        "source": "skillhub",
                        "source_path": "/tmp/source.md",
                    },
                    "llm_wiki": {
                        "version": "2026-05-26",
                        "source": "llm_wiki",
                    },
                },
            },
        )

        result = run(ctx)

        review = result["patches"]["sections"]["review"]
        self.assertNotIn("知识复利候选", review)

    def test_report_sections_surface_knowledge_compounding_candidates_as_review_items(self):
        ctx = build_empty_context({"target_date": "2026-05-26"})
        ctx = merge_hook_patches(
            ctx,
            {
                "knowledge": {
                    "trading_philosophy": {
                        "version": "2026-04-22",
                        "source": "skillhub",
                        "source_path": "/tmp/source.md",
                    },
                    "llm_wiki": {
                        "version": "2026-05-26",
                        "source": "llm_wiki",
                        "knowledge_compounding_candidates": [
                            {
                                "related_nodes": ["AI摩擦与知识复利", "判断样本与市场演变"],
                                "new_insight": "判断样本是日报里的反馈机制，用来把 AI 省掉的认知摩擦补回来。",
                                "status": "待确认",
                                "action": "只进入知识复利候选，不自动写入正式 wiki，不改变交易动作。",
                            }
                        ],
                    },
                },
            },
        )

        result = run(ctx)

        review = result["patches"]["sections"]["review"]
        self.assertIn("知识复利候选", review)
        self.assertIn("AI摩擦与知识复利 + 判断样本与市场演变", review)
        self.assertIn("待确认", review)
        self.assertIn("判断样本是日报里的反馈机制，用来把 AI 省掉的认知摩擦补回来。", review)
        self.assertIn("只进入知识复利候选，不自动写入正式 wiki，不改变交易动作。", review)
        self.assertNotIn("摩擦是资产不是成本", review)
        self.assertNotIn("认知投降", review)

    def test_report_sections_surface_knowledge_hits_as_short_table(self):
        ctx = build_empty_context({"target_date": "2026-05-29"})
        ctx = merge_hook_patches(
            ctx,
            {
                "knowledge": {
                    "trading_philosophy": {
                        "version": "2026-04-22",
                        "source": "skillhub",
                        "source_path": "/tmp/source.md",
                    },
                    "llm_wiki": {
                        "version": "2026-05-29",
                        "source": "llm_wiki",
                        "knowledge_hits": [
                            {
                                "knowledge_id": "market.low-frequency-focus",
                                "title": "指数强但赚钱效应弱",
                                "source_path": "wiki/板块补充/板块中枢与主线延续.md",
                                "triggered_by": ["指数上涨", "上涨家数偏弱"],
                                "impact": "只保留主线核心，不从旧方向强行扩散候选。",
                                "report_slot": "市场结构判断",
                            }
                        ],
                    },
                },
            },
        )

        result = run(ctx)

        review = result["patches"]["sections"]["review"]
        self.assertIn("经验库命中", review)
        self.assertIn("| 命中经验 | 触发事实 | 本次影响 | 来源 |", review)
        self.assertIn("| 指数强但赚钱效应弱 | 指数上涨；上涨家数偏弱 | 只保留主线核心，不从旧方向强行扩散候选。 | 板块中枢与主线延续 |", review)

    def test_report_sections_hide_knowledge_hits_table_when_absent(self):
        ctx = build_empty_context({"target_date": "2026-05-29"})
        ctx = merge_hook_patches(
            ctx,
            {
                "knowledge": {
                    "trading_philosophy": {
                        "version": "2026-04-22",
                        "source": "skillhub",
                        "source_path": "/tmp/source.md",
                    },
                    "llm_wiki": {
                        "version": "2026-05-29",
                        "source": "llm_wiki",
                    },
                },
            },
        )

        result = run(ctx)

        review = result["patches"]["sections"]["review"]
        self.assertNotIn("经验库命中", review)

    def test_report_sections_surface_market_structure_knowledge_update(self):
        ctx = build_empty_context(
            {
                "target_date": "2026-05-27",
                "knowledge_updates": [
                    {
                        "topic": "市场结构判断",
                        "new_insight": "指数新高不等于真实赚钱效应改善；上涨家数弱、成交集中、对立方向反弹时，日报应优先进入低频聚焦。",
                        "fact_basis": "指数强势；上涨家数偏弱；成交额高位；消费白酒反弹；科技老主线疲态。",
                        "suggested_nodes": [
                            "wiki/板块补充/板块中枢与主线延续.md",
                            "wiki/交易思想/价格行为与能量框架.md",
                        ],
                        "next_effect": "市场结构判断、候选数量、主线核心筛选、明日节奏",
                    }
                ],
            }
        )
        ctx = merge_hook_patches(
            ctx,
            {
                "knowledge": {
                    "trading_philosophy": {
                        "version": "2026-04-22",
                        "source": "skillhub",
                        "source_path": "/tmp/source.md",
                    },
                    "llm_wiki": {
                        "version": "2026-05-26",
                        "source": "llm_wiki",
                    },
                },
            },
        )

        result = run(ctx)

        review = result["patches"]["sections"]["review"]
        self.assertIn("知识复利提示", review)
        self.assertIn("新增判断：指数新高不等于真实赚钱效应改善", review)
        self.assertIn("事实来源：指数强势；上涨家数偏弱", review)
        self.assertIn("建议沉淀：wiki/板块补充/板块中枢与主线延续.md；wiki/交易思想/价格行为与能量框架.md", review)
        self.assertIn("下次影响：市场结构判断、候选数量、主线核心筛选、明日节奏", review)

    def test_report_sections_combine_market_structure_and_ai_friction_knowledge_updates(self):
        ctx = build_empty_context(
            {
                "target_date": "2026-05-27",
                "knowledge_updates": [
                    {
                        "topic": "市场结构判断",
                        "new_insight": "指数新高不等于真实赚钱效应改善；上涨家数弱时，日报应优先进入低频聚焦。",
                        "fact_basis": "指数强势；上涨家数偏弱；成交额高位。",
                        "suggested_nodes": [
                            "wiki/板块补充/板块中枢与主线延续.md",
                        ],
                        "next_effect": "市场结构判断、候选数量、主线核心筛选、明日节奏",
                    },
                    {
                        "topic": "AI摩擦与知识复利",
                        "source_path": "wiki/交易思想/AI摩擦与知识复利.md",
                    },
                ],
            }
        )
        ctx = merge_hook_patches(
            ctx,
            {
                "knowledge": {
                    "trading_philosophy": {
                        "version": "2026-04-22",
                        "source": "skillhub",
                        "source_path": "/tmp/source.md",
                    },
                    "llm_wiki": {
                        "version": "2026-05-26",
                        "source": "llm_wiki",
                    },
                },
            },
        )

        result = run(ctx)

        review = result["patches"]["sections"]["review"]
        self.assertEqual(review.count("知识复利提示"), 1)
        self.assertIn("新增判断：指数新高不等于真实赚钱效应改善", review)
        self.assertIn("事实来源：指数强势；上涨家数偏弱", review)
        self.assertIn("建议沉淀：wiki/板块补充/板块中枢与主线延续.md", review)
        self.assertIn("下次影响：市场结构判断、候选数量、主线核心筛选、明日节奏", review)
        self.assertIn("复利方向：用反馈机制校准新知识，避免只堆积结论。", review)
        self.assertIn("必要认知摩擦：复述、重写、对比或沉淀成知识节点。", review)
        self.assertIn("日报落点：只记录字段化结论，不把文章长文带入交易主链。", review)


if __name__ == "__main__":
    unittest.main()
