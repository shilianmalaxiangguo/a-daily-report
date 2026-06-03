import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.candidate_trace_contracts import (
    ARTIFACT_VERSION,
    CHECK_RESULTS,
    VALID_TIERS,
    VISIBLE_SCOPE,
    __all__ as TRACE_CONTRACT_EXPORTS,
    build_candidate_trace,
    build_candidate_trace_artifact_payload,
    build_eliminated_summary,
)


class CandidateTraceContractsTest(unittest.TestCase):
    def test_build_candidate_trace_for_t0_condition_observation(self):
        trace = build_candidate_trace(
            {
                "name": "华天科技",
                "code": "002185",
                "tier": "T0",
                "source_pools": ["主线核心候选"],
                "mainline": "半导体",
                "sector": "半导体",
                "market_fit": "部分满足",
                "market_evidence": "市场不支持强进攻，但允许核心候选条件观察",
                "mainline_fit": "满足",
                "mainline_evidence": "半导体仍在主线候选内",
                "stock_structure_fit": "部分满足",
                "stock_structure_evidence": "承接未破，但早盘仍需确认",
                "latest_price": 13.2,
                "available_cash": 10000,
                "trigger_condition": "主线承接 + 个股突破或回踩确认",
                "failure_condition": "主线回落或放量不承接",
                "final_action": "09:50-10:10确认，不满足继续不参与",
            }
        )

        self.assertEqual(trace["stock_code"], "002185")
        self.assertEqual(trace["stock_name"], "华天科技")
        self.assertEqual(trace["tier"], "T0")
        self.assertEqual(trace["source_pools"], ["主线核心候选"])
        self.assertEqual(trace["mainline"], "半导体")
        self.assertEqual(trace["sector"], "半导体")
        self.assertIn({"field": "账户适配", "value": "实际可买", "source": "account_context"}, trace["key_inputs"])
        self.assertEqual([check["result"] for check in trace["checks"]], ["部分满足", "满足", "部分满足"])
        self.assertIn("市场条件部分满足", trace["branch_path"])
        self.assertIn("进入 T0 条件观察", trace["branch_path"])
        self.assertEqual(trace["final_action"], "09:50-10:10确认，不满足继续不参与")
        self.assertEqual(trace["trigger_condition"], "主线承接 + 个股突破或回踩确认")
        self.assertEqual(trace["failure_condition"], "主线回落或放量不承接")
        self.assertEqual(trace["missing_data"], [])
        self.assertLessEqual(len(trace["visible_summary"]), 40)

    def test_missing_data_is_not_positive_reason(self):
        trace = build_candidate_trace(
            {
                "name": "缺数样本",
                "code": "000001",
                "tier": "T1",
                "source_pools": ["主线核心候选"],
                "mainline": "",
                "sector": "",
                "market_fit": "",
                "mainline_fit": "",
                "stock_structure_fit": "",
                "final_action": "",
            }
        )

        results = {check["label"]: check["result"] for check in trace["checks"]}
        self.assertEqual(results["市场条件"], "数据缺失")
        self.assertEqual(results["主线条件"], "数据缺失")
        self.assertEqual(results["个股结构"], "数据缺失")
        self.assertIn("关键数据不完整", trace["final_action"])
        self.assertIn("mainline", trace["missing_data"])
        self.assertIn("sector", trace["missing_data"])
        self.assertIn("市场条件数据缺失", trace["branch_path"])

    def test_trade_narrative_sector_is_used_as_visible_sector(self):
        trace = build_candidate_trace(
            {
                "name": "工业富联",
                "code": "601138",
                "mainline": "AI算力基础设施",
                "sector": "通信设备",
                "trade_narrative_sector": "AI算力基础设施",
                "market_fit": "满足",
                "mainline_fit": "满足",
                "stock_structure_fit": "部分满足",
                "final_action": "09:50-10:10确认",
            }
        )

        self.assertEqual(trace["sector"], "AI算力基础设施")

    def test_check_results_are_controlled(self):
        self.assertEqual(CHECK_RESULTS, ("满足", "部分满足", "未满足", "数据缺失"))
        trace = build_candidate_trace(
            {
                "name": "异常样本",
                "code": "000002",
                "tier": "T2",
                "market_fit": "很强",
                "mainline_fit": "满足",
                "stock_structure_fit": "未满足",
            }
        )
        self.assertEqual(trace["checks"][0]["result"], "数据缺失")
        self.assertEqual(trace["checks"][1]["result"], "满足")
        self.assertEqual(trace["checks"][2]["result"], "未满足")

    def test_account_status_respects_explicit_values(self):
        buy_trace = build_candidate_trace(
            {
                "name": "显式可买",
                "code": "000001",
                "account_trade_status": "实际可买",
            }
        )
        no_buy_trace = build_candidate_trace(
            {
                "name": "显式不可买",
                "code": "000002",
                "账户状态": "实际不可买",
            }
        )

        self.assertIn({"field": "账户适配", "value": "实际可买", "source": "account_context"}, buy_trace["key_inputs"])
        self.assertIn({"field": "账户适配", "value": "实际不可买", "source": "account_context"}, no_buy_trace["key_inputs"])
        self.assertNotIn("account_context", buy_trace["missing_data"])
        self.assertNotIn("account_context", no_buy_trace["missing_data"])

    def test_account_status_688_without_star_market_is_not_buyable(self):
        trace = build_candidate_trace({"name": "科创样本", "code": "688001", "latest_price": 10, "available_cash": 10000})

        self.assertIn({"field": "账户适配", "value": "实际不可买", "source": "account_context"}, trace["key_inputs"])
        self.assertNotIn("account_context", trace["missing_data"])

    def test_account_status_one_lot_over_cash_is_not_buyable(self):
        trace = build_candidate_trace({"name": "高价样本", "code": "000001", "latest_price": 101, "available_cash": 10000})

        self.assertIn({"field": "账户适配", "value": "实际不可买", "source": "account_context"}, trace["key_inputs"])
        self.assertNotIn("account_context", trace["missing_data"])

    def test_account_status_price_or_cash_only_is_missing_data(self):
        price_trace = build_candidate_trace({"name": "有价样本", "code": "000001", "latest_price": 10})
        cash_trace = build_candidate_trace({"name": "有钱样本", "code": "000002", "available_cash": 10000})

        self.assertIn({"field": "账户适配", "value": "数据缺失", "source": "account_context"}, price_trace["key_inputs"])
        self.assertIn({"field": "账户适配", "value": "数据缺失", "source": "account_context"}, cash_trace["key_inputs"])
        self.assertIn("account_context", price_trace["missing_data"])
        self.assertIn("account_context", cash_trace["missing_data"])

    def test_account_status_price_and_cash_affordable_is_buyable(self):
        trace = build_candidate_trace({"name": "可买样本", "code": "000001", "latest_price": 10, "available_cash": 10000})

        self.assertIn({"field": "账户适配", "value": "实际可买", "source": "account_context"}, trace["key_inputs"])
        self.assertNotIn("account_context", trace["missing_data"])

    def test_account_status_missing_price_and_cash_is_missing_data(self):
        trace = build_candidate_trace({"name": "缺账户样本", "code": "000001"})

        self.assertIn({"field": "账户适配", "value": "数据缺失", "source": "account_context"}, trace["key_inputs"])
        self.assertIn("account_context", trace["missing_data"])

    def test_account_context_not_required_when_market_condition_already_blocks_new_entry(self):
        trace = build_candidate_trace(
            {
                "name": "市场不支持样本",
                "code": "000001",
                "tier": "T2",
                "mainline": "电力",
                "sector": "电力",
                "market_fit": "未满足",
                "mainline_fit": "满足",
                "stock_structure_fit": "部分满足",
            }
        )

        self.assertIn({"field": "账户适配", "value": "数据缺失", "source": "account_context"}, trace["key_inputs"])
        self.assertNotIn("account_context", trace["missing_data"])
        self.assertEqual(trace["final_action"], "")
        self.assertIn("条件未满足，继续不参与", trace["branch_path"])

    def test_exported_constants_and_all_are_contractual(self):
        self.assertEqual(ARTIFACT_VERSION, 1)
        self.assertEqual(VISIBLE_SCOPE, "T0_T1_T2_T3")
        self.assertEqual(VALID_TIERS, ("T0", "T1", "T2", "T3"))
        self.assertEqual(CHECK_RESULTS, ("满足", "部分满足", "未满足", "数据缺失"))
        self.assertEqual(
            set(TRACE_CONTRACT_EXPORTS),
            {
                "ARTIFACT_VERSION",
                "VISIBLE_SCOPE",
                "CHECK_RESULTS",
                "VALID_TIERS",
                "build_candidate_trace",
                "build_eliminated_summary",
                "build_candidate_trace_artifact_payload",
            },
        )

    def test_build_eliminated_summary_groups_reasons_and_caps_representatives(self):
        summary = build_eliminated_summary(
            [
                {"name": "大众公用", "reason": "主线不匹配"},
                {"name": "红星发展", "reason": "主线不匹配"},
                {"name": "步步高", "reason": "主线不匹配"},
                {"name": "中船特气", "reason": "账户不适配"},
                {"name": "第四只", "reason": "主线不匹配"},
                {"name": "", "reason": ""},
            ]
        )

        by_reason = {item["reason"]: item for item in summary}
        self.assertEqual(by_reason["主线不匹配"]["count"], 4)
        self.assertEqual(by_reason["主线不匹配"]["representatives"], ["大众公用", "红星发展", "步步高"])
        self.assertEqual(by_reason["账户不适配"]["count"], 1)
        self.assertEqual(by_reason["数据缺失"]["treatment"], "关键数据不完整，停止生成动作")

    def test_build_candidate_trace_tolerates_non_dict_input(self):
        trace = build_candidate_trace("x")

        self.assertEqual(trace["stock_code"], "")
        self.assertEqual(trace["stock_name"], "")
        self.assertIn({"field": "账户适配", "value": "数据缺失", "source": "account_context"}, trace["key_inputs"])
        self.assertIn("account_context", trace["missing_data"])
        self.assertIn("关键数据不完整", trace["final_action"])

    def test_build_eliminated_summary_tolerates_non_dict_items(self):
        summary = build_eliminated_summary(["x"])

        self.assertEqual(
            summary,
            [
                {
                    "reason": "数据缺失",
                    "count": 1,
                    "representatives": ["观察对象"],
                    "treatment": "关键数据不完整，停止生成动作",
                }
            ],
        )

    def test_build_candidate_trace_artifact_payload(self):
        trace = build_candidate_trace({"name": "华天科技", "code": "002185", "tier": "T0"})
        payload = build_candidate_trace_artifact_payload(
            trade_date="2026-05-26",
            traces=[trace],
            eliminated_summary=[{"reason": "主线不匹配", "count": 1, "representatives": ["大众公用"], "treatment": "保留观察，不进入动作分层"}],
            generated_at="2026-05-27T00:00:00+08:00",
            source_report={"path": "reports/2026-05-26_A股日报_完整版.md", "variant": "full"},
        )

        self.assertEqual(payload["artifact_version"], 1)
        self.assertEqual(payload["trade_date"], "2026-05-26")
        self.assertEqual(payload["visible_scope"], "T0_T1_T2_T3")
        self.assertEqual(payload["traces"][0]["stock_code"], "002185")
        self.assertEqual(payload["eliminated_summary"][0]["reason"], "主线不匹配")

    def test_candidate_trace_preserves_anchor_ma_path_and_limit_up_role(self):
        trace = build_candidate_trace(
            {
                "name": "大唐发电",
                "code": "601991",
                "tier": "T0",
                "mainline": "电力",
                "sector": "电力",
                "sector_anchor": "大唐发电(601991)",
                "candidate_role": "板块锚",
                "relationship_to_anchor": "资金回流优先看板块锚，候选本身就是板块锚",
                "repair_priority": "优先修复",
                "anchor_reversal_decision": "可作为主对象",
                "anchor_reversal_reason": "候选就是板块锚，MA5入/MA7清/MA5T和承接路径明确，涨停只是证据，慢即是快",
                "ma_binding_strategy": "MA5入/MA7清/MA5T",
                "leader_certainty_path": "板块锚优先，MA5入/MA7清/MA5T和承接路径明确",
                "limit_up_evidence_role": "涨停只是证据，不能替代板块锚和承接路径",
            }
        )

        anchor = trace["anchor_reversal"]
        self.assertEqual(anchor["ma_binding_strategy"], "MA5入/MA7清/MA5T")
        self.assertIn("承接路径明确", anchor["leader_certainty_path"])
        self.assertIn("涨停只是证据", anchor["limit_up_evidence_role"])

    def test_candidate_trace_accepts_why_not_sector_anchor_alias(self):
        trace = build_candidate_trace(
            {
                "name": "华电辽能",
                "code": "600396",
                "tier": "T1",
                "mainline": "电力",
                "sector": "电力",
                "sector_anchor": "大唐发电(601991)",
                "candidate_role": "大容量中军",
                "为什么不做板块锚": "大唐发电短线加速过热，华电辽能承接更适合补位",
                "anchor_reversal_decision": "可作为补位",
            }
        )

        self.assertEqual(
            trace["anchor_reversal"]["why_not_anchor"],
            "大唐发电短线加速过热，华电辽能承接更适合补位",
        )

    def test_candidate_trace_preserves_nested_anchor_reversal_payload(self):
        trace = build_candidate_trace(
            {
                "name": "京能电力",
                "code": "600578",
                "tier": "T1",
                "mainline": "电力",
                "sector": "电力",
                "anchor_reversal": {
                    "sector_anchor": "大唐发电(601991)",
                    "candidate_role": "套利工具",
                    "relationship_to_anchor": "被大唐发电(601991)带动，只能反馈板块强度",
                    "why_not_anchor": "不能证明比板块锚更值得参与",
                    "anchor_reversal_decision": "降级观察",
                    "anchor_reversal_reason": "套利工具不能替代板块锚",
                    "limit_up_evidence_role": "涨停只是证据，不能替代板块锚和承接路径",
                },
            }
        )

        anchor = trace["anchor_reversal"]
        self.assertEqual(anchor["sector_anchor"], "大唐发电(601991)")
        self.assertEqual(anchor["anchor_reversal_decision"], "降级观察")
        self.assertIn("涨停只是证据", anchor["limit_up_evidence_role"])

    def test_candidate_trace_blocks_action_when_anchor_reversal_downgrades(self):
        trace = build_candidate_trace(
            {
                "name": "京能电力",
                "code": "600578",
                "tier": "T1",
                "mainline": "电力",
                "sector": "电力",
                "market_fit": "满足",
                "mainline_fit": "满足",
                "stock_structure_fit": "满足",
                "latest_price": 5,
                "available_cash": 10000,
                "anchor_reversal": {
                    "sector_anchor": "大唐发电(601991)",
                    "candidate_role": "套利工具",
                    "anchor_reversal_decision": "降级观察",
                    "anchor_reversal_reason": "套利工具不能替代板块锚",
                },
            }
        )

        self.assertEqual(trace["final_action"], "板块锚反推降级，只观察，不新增参与")
        self.assertIn("板块锚反推降级观察", trace["branch_path"])
        self.assertIn("只观察，不新增参与", trace["visible_summary"])


if __name__ == "__main__":
    unittest.main()
