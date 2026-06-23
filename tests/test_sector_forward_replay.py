import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from daily_report_render import ReportCriticalDataMissingError
from replay import sector_forward_replay
from replay.sector_forward_replay import build_tushare_daily_price_refill
from replay.sector_forward_replay import build_forward_replay_daily_rows
from replay.sector_forward_replay import build_tushare_minute_price_refill
from replay.sector_forward_replay import build_tushare_open_trade_date_refill
from replay.sector_forward_replay import build_tushare_index_context_refill
from replay.sector_forward_replay import build_forward_replay_payload
from replay.sector_forward_replay import build_static_minute_price_refill
from replay.sector_forward_replay import discover_forward_replay_pairs
from replay.sector_forward_replay import render_forward_replay_markdown_summary
from replay.sector_forward_replay import render_forward_replay_html


def _embedded_payload(rendered_html):
    match = re.search(
        r'<script type="application/json" id="sector-forward-replay-payload">(.*?)</script>',
        rendered_html,
        re.S,
    )
    if not match:
        return {}
    return json.loads(match.group(1))


class SectorForwardReplayTest(unittest.TestCase):
    def _data(self, date):
        if date == "2026-06-01":
            return {
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "target_date": date,
                    "candidate_pool": [],
                    "final": {"execution_object": {}, "position_pct": 0, "action_text": "0%不参与"},
                },
                "final_target_resolution": {},
                "position_decision": {"target_position_pct": 0},
                "hot_rank_top50": [],
                "hot_plates": [],
                "sector_fund_flow": {"inflow": [], "outflow": []},
            }
        if date == "2026-06-02":
            return {
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "target_date": date,
                    "candidate_pool": [],
                    "final": {"execution_object": {}, "position_pct": 0, "action_text": "0%不参与"},
                },
                "final_target_resolution": {},
                "position_decision": {"target_position_pct": 0},
                "hot_rank_top50": [],
                "hot_plates": [],
                "sector_fund_flow": {"inflow": [], "outflow": []},
            }
        if date == "2026-06-07":
            raise ReportCriticalDataMissingError("2026-06-07 日报事实缺失")
        if date == "2026-06-05":
            return {
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "target_date": date,
                    "candidate_pool": [
                        {
                            "stock": {"name": "兆易创新", "code": "603986", "sector": "半导体"},
                            "entry_basis": "来自市场氛围、板块发酵和板块角色推导",
                            "candidate_origin": "sector_first",
                            "sector": "半导体",
                            "sector_role": "板块锚",
                            "reversal_decision": "可作为主对象",
                            "status": "过程候选",
                        }
                    ],
                    "final": {"execution_object": {}, "position_pct": 0, "action_text": "0%不参与"},
                },
                "final_target_resolution": {},
                "position_decision": {"target_position_pct": 0},
                "hot_rank_top50": [],
                "hot_plates": [{"name": "半导体", "order": 1}],
                "sector_fund_flow": {"inflow": [{"name": "半导体", "change_pct": 1.2, "net_inflow_yi": 12.3}]},
                "integrated_hot_list": [
                    {
                        "code": "603986",
                        "name": "兆易创新",
                        "rank": 4,
                        "sector": "存储芯片",
                        "tags": ["存储芯片", "半导体"],
                    }
                ],
                "turnover_rank": [
                    {
                        "code": "603986",
                        "name": "兆易创新",
                        "rank": 2,
                        "sector": "半导体",
                        "turnover": 83.2,
                        "change_pct": 3.1,
                    }
                ],
            }
        if date == "2026-06-08":
            return {
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "target_date": date,
                    "candidate_pool": [
                        {
                            "stock": {"name": "大唐发电", "code": "601991", "sector": "火力发电"},
                            "entry_basis": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                            "candidate_origin": "legacy_signal_only",
                            "sector": "火力发电",
                            "status": "过程候选",
                        }
                    ],
                    "final": {"execution_object": {}, "position_pct": 0, "action_text": "0%不参与"},
                },
                "final_target_resolution": {},
                "position_decision": {"target_position_pct": 0},
                "hot_rank_top50": [
                    {
                        "code": "603986",
                        "name": "兆易创新",
                        "rank": 29,
                        "change_pct": 2.4,
                        "concepts": ["存储芯片"],
                    }
                ],
                "hot_plates": [{"name": "半导体", "order": 2}],
                "sector_fund_flow": {"inflow": [{"name": "半导体", "change_pct": 2.0, "net_inflow_yi": 18.0}]},
                "turnover_rank": [
                    {
                        "code": "603986",
                        "name": "兆易创新",
                        "rank": 6,
                        "sector": "半导体",
                        "turnover": 77.0,
                    }
                ],
            }
        if date == "2026-06-09":
            return {
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "target_date": date,
                    "candidate_pool": [
                        {
                            "stock": {"name": "大唐发电", "code": "601991", "sector": "火力发电"},
                            "entry_basis": "未证明来自板块发酵和市场选择，不能作为新仓入口",
                            "candidate_origin": "legacy_signal_only",
                            "sector": "火力发电",
                            "status": "过程候选",
                        },
                        {
                            "stock": {"name": "华电能源", "code": "600726", "sector": "火力发电"},
                            "entry_basis": "目标日才出现的强势电力样本",
                            "candidate_origin": "sector_first",
                            "sector": "火力发电",
                            "sector_role": "趋势龙头",
                            "reversal_decision": "可作为主对象",
                            "status": "过程候选",
                        }
                    ],
                    "final": {"execution_object": {}, "position_pct": 0, "action_text": "0%不参与"},
                },
                "final_target_resolution": {},
                "position_decision": {"target_position_pct": 0},
                "hot_rank_top50": [
                    {
                        "code": "601991",
                        "name": "大唐发电",
                        "rank": 4,
                        "change_pct": 6.05,
                        "open_price": 6.10,
                        "close_price": 6.36,
                        "high_price": 6.44,
                        "low_price": 6.02,
                        "sector": "火力发电",
                        "concepts": ["绿色电力"],
                    },
                    {
                        "code": "603986",
                        "name": "兆易创新",
                        "rank": 22,
                        "change_pct": 1.68,
                        "open_price": 118.00,
                        "close_price": 120.00,
                        "high_price": 122.00,
                        "low_price": 117.00,
                        "sector": "半导体",
                        "concepts": ["存储芯片"],
                    }
                ],
                "hot_plates": [{"name": "电力", "order": 1, "tag": "5家涨停"}],
                "sector_fund_flow": {"outflow": [{"name": "新型电力", "change_pct": 0.91, "net_inflow_yi": -1.73}]},
            }
        if date == "2026-06-10":
            return {
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "target_date": date,
                    "candidate_pool": [],
                    "final": {"execution_object": {}, "position_pct": 0, "action_text": "0%不参与"},
                },
                "final_target_resolution": {},
                "position_decision": {"target_position_pct": 0},
                "hot_rank_top50": [
                    {
                        "code": "601991",
                        "name": "大唐发电",
                        "rank": 6,
                        "change_pct": 3.14,
                        "open_price": 6.40,
                        "close_price": 6.56,
                        "high_price": 6.70,
                        "low_price": 6.28,
                        "sector": "火力发电",
                        "concepts": ["绿色电力"],
                    },
                    {
                        "code": "603986",
                        "name": "兆易创新",
                        "rank": 18,
                        "change_pct": 1.20,
                        "open_price": 122.00,
                        "close_price": 124.00,
                        "high_price": 126.00,
                        "low_price": 121.00,
                        "sector": "半导体",
                        "concepts": ["存储芯片"],
                    },
                ],
                "hot_plates": [{"name": "电力", "order": 2}, {"name": "半导体", "order": 4}],
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "新型电力", "change_pct": 1.20, "net_inflow_yi": 3.2},
                        {"name": "半导体", "change_pct": 0.80, "net_inflow_yi": 2.1},
                    ]
                },
            }
        raise ReportCriticalDataMissingError(f"{date} missing")

    def test_uses_previous_available_trading_day_when_requested_date_missing(self):
        payload = build_forward_replay_payload(
            [("2026-06-07", "2026-06-08")],
            loader=self._data,
        )

        pair = payload["pairs"][0]

        self.assertEqual(payload["schema_version"], "sector_forward_replay.v1")
        self.assertEqual(payload["sample_count"], 1)
        self.assertEqual(pair["requested_decision_date"], "2026-06-07")
        self.assertEqual(pair["effective_decision_date"], "2026-06-05")
        self.assertTrue(pair["coverage"]["fallback_used"])
        self.assertEqual(pair["candidate_count"], 1)
        self.assertEqual(pair["evaluations"][0]["stock_label"], "兆易创新(603986)")
        self.assertIn("板块方向命中", pair["evaluations"][0]["target_outcome"])
        self.assertIn("T+1买入日热榜第29", "；".join(pair["evaluations"][0]["target_facts"]))

    def test_target_day_only_reviews_existing_decision_candidates(self):
        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09")],
            loader=self._data,
        )

        pair = payload["pairs"][0]

        self.assertEqual(pair["effective_decision_date"], "2026-06-08")
        self.assertEqual(pair["candidate_count"], 1)
        self.assertNotIn("target_candidate_count", pair)
        self.assertNotIn("target_final_action", pair)
        self.assertEqual(pair["validation_scope"]["target_data_role"], "只复核决策日候选的T+1买入日表现")
        self.assertIn("候选生成", pair["validation_scope"]["target_day_not_used_for"])
        self.assertEqual(pair["evaluations"][0]["stock_label"], "大唐发电(601991)")
        self.assertNotIn("华电能源", json.dumps(pair["evaluations"], ensure_ascii=False))
        self.assertIn("T+1买入日自有流程回看仍收录（仅作结果证据）", "；".join(pair["evaluations"][0]["target_facts"]))
        self.assertIn("决策日 2026-06-08", pair["mermaid"])
        self.assertIn("T+1买入日 2026-06-09", pair["mermaid"])
        self.assertEqual(pair["emotion_projection"]["schema_version"], "t0_tplus2_emotion_projection.v1")
        self.assertIn("T+2市场预案", pair["emotion_projection"]["summary"])

    def test_empty_final_action_does_not_become_decision_candidate(self):
        payload = build_forward_replay_payload(
            [("2026-06-01", "2026-06-02")],
            loader=self._data,
        )

        pair = payload["pairs"][0]
        rendered = render_forward_replay_html(payload)

        self.assertEqual(pair["candidate_count"], 0)
        self.assertEqual(pair["decision_candidate_count"], 0)
        self.assertEqual(pair["evaluations"], [])
        self.assertIn('BDAY["T+1买入日 2026-06-02 复核 0 只决策日候选"]', pair["mermaid"])
        self.assertIn('<tr><td colspan="5">无候选</td></tr>', rendered)
        self.assertNotIn("无执行对象</td><td>", rendered)

    def test_html_renders_static_flow_and_embedded_payload(self):
        payload = build_forward_replay_payload(
            [("2026-06-07", "2026-06-08"), ("2026-06-08", "2026-06-09")],
            loader=self._data,
        )

        rendered = render_forward_replay_html(payload)

        self.assertIn('meta name="artifact" content="sector-forward-replay"', rendered)
        self.assertIn("板块资金扩散前向回测", rendered)
        self.assertIn("流程图", rendered)
        self.assertIn("Mermaid 源码", rendered)
        self.assertIn("决策日候选的T+1买入日逐股复核", rendered)
        self.assertIn("验证范围", rendered)
        self.assertIn("只看T0候选", rendered)
        self.assertIn("T0推演T+2交易环境", rendered)
        self.assertIn("预案与实际分开看", rendered)
        self.assertNotIn("<dt>目标日动作</dt>", rendered)
        self.assertNotIn("<dt>目标日候选</dt>", rendered)
        self.assertIn("决策日淘汰赛明细", rendered)
        self.assertIn("2026-06-07 无可用日报事实，改用上一可用交易日 2026-06-05", rendered)
        self.assertIn("data-mermaid-status', 'local-svg'", rendered)
        self.assertNotIn("cdn.jsdelivr", rendered)
        self.assertNotIn("mermaid.min.js", rendered)
        self.assertIn("sector-window-return-chart", rendered)
        self.assertIn("sector-window-excess-chart", rendered)
        self.assertIn("sector-window-chart-payload", rendered)
        self.assertIn("../../.generated/vendor/echarts/echarts.min.js", rendered)
        self.assertIn(".generated/vendor/echarts/echarts.min.js", rendered)
        embedded = _embedded_payload(rendered)
        self.assertEqual(embedded["sample_count"], 2)
        self.assertEqual(embedded["pairs"][0]["effective_decision_date"], "2026-06-05")

    def test_discovers_available_forward_pairs_without_weekend_guessing(self):
        pairs, discovery = discover_forward_replay_pairs(
            "2026-06-01",
            "2026-06-10",
            loader=self._data,
        )

        self.assertEqual(
            pairs,
            [
                ("2026-06-01", "2026-06-02", "2026-06-05"),
                ("2026-06-02", "2026-06-05", "2026-06-08"),
                ("2026-06-05", "2026-06-08", "2026-06-09"),
                ("2026-06-08", "2026-06-09", "2026-06-10"),
                ("2026-06-09", "2026-06-10", None),
            ],
        )
        self.assertEqual(discovery["available_dates"], ["2026-06-01", "2026-06-02", "2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"])
        self.assertTrue(any(item["date"] == "2026-06-07" for item in discovery["missing_dates"]))

    def test_payload_summarizes_zero_action_root_cause_and_mismatch(self):
        pairs, discovery = discover_forward_replay_pairs(
            "2026-06-05",
            "2026-06-09",
            loader=self._data,
        )
        payload = build_forward_replay_payload(pairs, loader=self._data, discovery=discovery)

        self.assertEqual(payload["summary"]["action_distribution"], {"0%": 2})
        self.assertEqual(payload["summary"]["legacy_action_distribution"], {"0%": 2})
        self.assertTrue(payload["summary"]["zero_only"])
        self.assertFalse(payload["summary"]["all_zero_problem"])
        self.assertIn("周期/账户条件未通过", payload["summary"]["diagnosis_distribution"])
        self.assertIn("板块扩散未通过", payload["summary"]["diagnosis_distribution"])
        self.assertTrue(payload["summary"]["mismatch_samples"])
        self.assertEqual(
            payload["summary"]["mismatch_samples"][0]["type"],
            "T0不参与但T+1证据走强",
        )
        rendered = render_forward_replay_html(payload)
        self.assertIn("全局诊断", rendered)
        self.assertIn("原日报最终动作分布", rendered)
        self.assertIn("旧链路动作分布", rendered)
        self.assertIn("0% 归因分布", rendered)
        self.assertIn("异常错配样本", rendered)
        embedded = _embedded_payload(rendered)
        self.assertEqual(embedded["summary"]["action_distribution"], {"0%": 2})
        self.assertEqual(embedded["summary"]["legacy_action_distribution"], {"0%": 2})

    def test_large_all_zero_sample_is_reported_as_invalid_chain(self):
        pairs = [("2026-06-01", "2026-06-02")] * 20
        payload = build_forward_replay_payload(pairs, loader=self._data)

        verdict = payload["summary"]["system_verdict"]

        self.assertTrue(payload["summary"]["all_zero_problem"])
        self.assertEqual(verdict["level"], "invalid_chain")
        self.assertIn("链路需要复核", verdict["conclusion"])
        self.assertIn("20/20 天最终都是 0%", verdict["conclusion"])
        rendered = render_forward_replay_html(payload)
        self.assertIn("链路需要复核", rendered)
        self.assertIn("停止把该回测当作策略有效证据", rendered)

    def test_paper_strategy_recovers_sector_first_carrier_without_target_lookahead(self):
        payload = build_forward_replay_payload(
            [("2026-06-05", "2026-06-08")],
            loader=self._data,
        )

        pair = payload["pairs"][0]
        strategy = pair["paper_strategy"]

        self.assertEqual(strategy["action_label"], "板块资金载体主样本")
        self.assertEqual(strategy["primary_candidate"]["stock_label"], "兆易创新(603986)")
        self.assertIn("半导体进入板块候选", strategy["primary_candidate"]["reason"])
        self.assertEqual(strategy["target_summary"]["primary_outcome_label"], "板块命中但个股未到执行级别")
        self.assertNotIn("华电能源", json.dumps(strategy, ensure_ascii=False))

    def test_payload_and_html_compare_old_chain_with_new_paper_strategy(self):
        payload = build_forward_replay_payload(
            [("2026-06-05", "2026-06-08"), ("2026-06-08", "2026-06-09")],
            loader=self._data,
        )

        summary = payload["summary"]
        rendered = render_forward_replay_html(payload)

        self.assertIn("paper_action_distribution", summary)
        self.assertEqual(summary["action_distribution"], {"0%": 2})
        self.assertEqual(summary["legacy_action_distribution"], {"0%": 2})
        self.assertNotIn("effective_action", payload["pairs"][0])
        self.assertEqual(payload["pairs"][0]["paper_review_object"]["source"], "sector_capital_carrier_strategy")
        self.assertTrue(payload["pairs"][0]["paper_review_object"]["review_only"])
        self.assertGreater(summary["paper_candidate_count_max"], 0)
        self.assertIn("旧链路 vs 板块优先链路", rendered)
        self.assertIn("新版纸面策略：板块资金载体跟随", rendered)
        self.assertIn("板块优先纸面动作分布", rendered)
        self.assertIn("纸面候选 T+1 买入复核", rendered)

    def test_sector_first_paper_review_object_keeps_legacy_action_as_comparison(self):
        def loader(date):
            data = json.loads(json.dumps(self._data(date), ensure_ascii=False))
            if date == "2026-06-05":
                data["selection_workflow"]["final"] = {
                    "execution_object": {"name": "旧链路股", "code": "000001", "sector": "银行"},
                    "position_pct": 50,
                    "action_text": "50%条件执行",
                    "reason": "旧链路旧对象",
                }
                data["position_decision"] = {"target_position_pct": 50}
            return data

        payload = build_forward_replay_payload(
            [("2026-06-05", "2026-06-08")],
            loader=loader,
        )

        pair = payload["pairs"][0]
        rendered = render_forward_replay_html(payload)

        self.assertEqual(pair["paper_review_object"]["source"], "sector_capital_carrier_strategy")
        self.assertEqual(pair["paper_review_object"]["target"]["code"], "603986")
        self.assertTrue(pair["paper_review_object"]["review_only"])
        self.assertEqual(pair["legacy_final_action"]["target"]["code"], "000001")
        self.assertEqual(pair["paper_review_contrast"]["type"], "legacy_action_vs_paper_review_object")
        self.assertEqual(payload["summary"]["action_distribution"], {"50%": 1})
        self.assertEqual(payload["summary"]["legacy_action_distribution"], {"50%": 1})
        self.assertEqual(payload["summary"]["paper_review_contrast_count"], 1)
        self.assertIn("旧动作 vs 纸面复核对象", rendered)
        self.assertIn("旧链路股(000001)", rendered)
        self.assertIn("兆易创新(603986)", rendered)

    def test_paper_strategy_shows_tplus2_sell_windows_and_return_basis(self):
        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09", "2026-06-10")],
            loader=self._data,
        )

        pair = payload["pairs"][0]
        rendered = render_forward_replay_html(payload)
        row = pair["evaluations"][0]

        self.assertIn("T+1涨幅", rendered)
        self.assertIn("T+2三段卖出窗口复核", rendered)
        self.assertIn("T+2卖出窗口统计", rendered)
        self.assertIn("T+1买入 x T+2卖出窗口矩阵", rendered)
        self.assertIn("买卖时间收益矩阵", rendered)
        self.assertIn("代理收益曲线与最大回撤", rendered)
        self.assertIn("窗口折算收益与指数对照", rendered)
        self.assertIn("单笔代理收益前10", rendered)
        self.assertIn("单笔代理亏损前10", rendered)
        self.assertIn("T+1买入窗口", rendered)
        self.assertIn("日线代理较高窗口", rendered)
        self.assertIn("T0推演与T+2校准", rendered)
        self.assertIn("09:30-09:35", rendered)
        self.assertIn("09:50-10:10", rendered)
        self.assertIn("14:30-14:55", rendered)
        self.assertIsNotNone(row["target_change_pct"])
        self.assertEqual(row["tplus2_exit_review"]["sell_date"], "2026-06-10")
        self.assertEqual(len(row["tplus2_exit_review"]["window_matrix"]), 9)
        matrix_summary = payload["summary"]["trade_window_matrix_summary"]
        self.assertEqual(len(matrix_summary["top_gain_samples"]), 9)
        self.assertIn("top_loss_samples", matrix_summary)
        self.assertTrue(
            all(item["return_pct"] < 0 for item in matrix_summary["top_loss_samples"])
        )
        self.assertEqual(
            [item["window"] for item in row["tplus2_exit_review"]["windows"]],
            ["09:30-09:35", "09:50-10:10", "14:30-14:55"],
        )
        self.assertIn("trade_window_matrix_summary", payload["summary"])
        self.assertIn("target_action_summary", payload["summary"])
        self.assertIn("缺少分时成交价，使用日线代理", rendered)
        self.assertNotIn("按D收盘买入、D+1收盘卖出", rendered)
        self.assertNotIn("T+1卖出收益", rendered)

    def test_trade_window_rank_samples_are_sorted_and_grid_uses_summary_rows(self):
        def pair(decision_date, stock, open_open_return, open_mid_return):
            return {
                "effective_decision_date": decision_date,
                "buy_date": "2026-01-05",
                "sell_date": "2026-01-06",
                "paper_strategy": {
                    "target_summary": {"primary_stock": stock},
                    "target_evaluations": [
                        {
                            "stock_label": stock,
                            "tplus2_exit_review": {
                                "window_matrix": [
                                    {
                                        "buy_window_id": "open_0930_0935",
                                        "buy_window": "09:30-09:35",
                                        "buy_proxy_label": "T+1开盘价代理",
                                        "sell_window_id": "open_0930_0935",
                                        "sell_window": "09:30-09:35",
                                        "sell_proxy_label": "T+2开盘价代理",
                                        "entry_price": 10.0,
                                        "exit_price": 10.0 * (1 + open_open_return / 100),
                                        "return_pct": open_open_return,
                                        "basis": "测试日线代理",
                                    },
                                    {
                                        "buy_window_id": "open_0930_0935",
                                        "buy_window": "09:30-09:35",
                                        "buy_proxy_label": "T+1开盘价代理",
                                        "sell_window_id": "mid_0950_1010",
                                        "sell_window": "09:50-10:10",
                                        "sell_proxy_label": "T+2日内中枢价代理",
                                        "entry_price": 10.0,
                                        "exit_price": 10.0 * (1 + open_mid_return / 100),
                                        "return_pct": open_mid_return,
                                        "basis": "测试日线代理",
                                    },
                                ]
                            },
                        }
                    ],
                },
            }

        matrix_summary = sector_forward_replay._build_trade_window_matrix_summary(
            [
                pair("2026-01-02", "强样本(000001)", 5.0, -2.0),
                pair("2026-01-03", "弱样本(000002)", 7.0, -4.0),
            ]
        )
        grid = sector_forward_replay._trade_window_matrix_summary_grid(
            {"trade_window_matrix_summary": matrix_summary}
        )

        self.assertEqual(
            [item["return_pct"] for item in matrix_summary["top_gain_samples"]],
            [7.0, 5.0],
        )
        self.assertEqual(
            [item["return_pct"] for item in matrix_summary["top_loss_samples"]],
            [-4.0, -2.0],
        )
        self.assertTrue(all(item["return_pct"] < 0 for item in matrix_summary["top_loss_samples"]))
        self.assertIn("+6.00%", grid)
        self.assertIn("正收益 2/2", grid)
        self.assertIn("-3.00%", grid)
        self.assertIn("较高组合", grid)

    def test_trade_window_summary_builds_equity_curve_and_max_drawdown(self):
        def pair(decision_date, stock, return_pct):
            return {
                "effective_decision_date": decision_date,
                "buy_date": "2026-01-05",
                "sell_date": "2026-01-06",
                "paper_strategy": {
                    "target_summary": {"primary_stock": stock},
                    "target_evaluations": [
                        {
                            "stock_label": stock,
                            "tplus2_exit_review": {
                                "window_matrix": [
                                    {
                                        "buy_window_id": "open_0930_0935",
                                        "buy_window": "09:30-09:35",
                                        "buy_proxy_label": "T+1开盘价代理",
                                        "sell_window_id": "open_0930_0935",
                                        "sell_window": "09:30-09:35",
                                        "sell_proxy_label": "T+2开盘价代理",
                                        "entry_price": 10.0,
                                        "exit_price": 10.0 * (1 + return_pct / 100),
                                        "return_pct": return_pct,
                                        "basis": "测试日线代理",
                                    }
                                ]
                            },
                        }
                    ],
                },
            }

        matrix_summary = sector_forward_replay._build_trade_window_matrix_summary(
            [
                pair("2026-01-02", "先涨样本(000001)", 10.0),
                pair("2026-01-03", "回撤样本(000002)", -20.0),
            ]
        )
        curve = matrix_summary["recommended_equity_curve"]
        rendered_rows = sector_forward_replay._render_equity_curve_summary_rows(
            {"trade_window_matrix_summary": matrix_summary}
        )
        recommended_rows = sector_forward_replay._render_recommended_curve_rows(
            {"trade_window_matrix_summary": matrix_summary}
        )

        self.assertEqual(curve["sample_count"], 2)
        self.assertEqual(curve["final_net_value"], 0.88)
        self.assertEqual(curve["cumulative_return_pct"], -12.0)
        self.assertEqual(curve["max_drawdown_pct"], -20.0)
        self.assertEqual(curve["max_drawdown_sample"]["decision_date"], "2026-01-03")
        self.assertIn("期末净值", render_forward_replay_html({"pairs": [], "notes": [], "summary": {"trade_window_matrix_summary": matrix_summary}}))
        self.assertIn("-20.00%", rendered_rows)
        self.assertIn("0.88", recommended_rows)

    def test_window_performance_comparison_includes_index_excess(self):
        def pair(decision_date, stock, return_pct, sh_index):
            return {
                "effective_decision_date": decision_date,
                "buy_date": "2026-01-05",
                "sell_date": "2026-01-06",
                "t0_market_context": {
                    "T0上证指数": f"{sh_index:.2f} / +0.00%",
                    "T0全A指数": f"{sh_index:.2f} / +0.00%",
                    "T0中证500": f"{sh_index:.2f} / +0.00%",
                    "T0创业板指": f"{sh_index:.2f} / +0.00%",
                },
                "paper_strategy": {
                    "target_summary": {"primary_stock": stock},
                    "target_evaluations": [
                        {
                            "stock_label": stock,
                            "tplus2_exit_review": {
                                "window_matrix": [
                                    {
                                        "buy_window_id": "open_0930_0935",
                                        "buy_window": "09:30-09:35",
                                        "buy_proxy_label": "T+1开盘价代理",
                                        "sell_window_id": "late_1430_1455",
                                        "sell_window": "14:30-14:55",
                                        "sell_proxy_label": "T+2收盘价代理",
                                        "entry_price": 10.0,
                                        "exit_price": 10.0 * (1 + return_pct / 100),
                                        "return_pct": return_pct,
                                        "buy_window_entry_change_pct": 1.0,
                                        "buy_close_near_limit": False,
                                        "basis": "测试日线代理",
                                    }
                                ]
                            },
                        }
                    ],
                },
            }

        pair_payloads = [
            pair("2026-01-02", "强样本(000001)", 10.0, 1000.0),
            pair("2026-01-03", "回撤样本(000002)", -5.0, 1100.0),
        ]
        matrix_summary = sector_forward_replay._build_trade_window_matrix_summary(pair_payloads)
        benchmark_summary = sector_forward_replay._build_index_benchmark_summary(pair_payloads)
        comparison = sector_forward_replay._build_window_performance_comparison(
            pair_payloads,
            matrix_summary,
            benchmark_summary,
        )
        rows = sector_forward_replay._render_window_performance_comparison_rows(
            {"window_performance_comparison": comparison}
        )
        benchmark_rows = sector_forward_replay._render_index_benchmark_rows(
            {"index_benchmark_summary": benchmark_summary}
        )
        target_row = next(
            item for item in comparison["rows"]
            if item["buy_window_id"] == "open_0930_0935"
            and item["sell_window_id"] == "late_1430_1455"
            and item["exclusion"] == "未剔除接近涨停买点"
        )

        self.assertEqual(benchmark_summary["rows"][0]["cumulative_return_pct"], 10.0)
        self.assertEqual(target_row["cumulative_return_pct"], 4.5)
        self.assertEqual(target_row["sample_count"], 2)
        self.assertEqual(target_row["period_count"], 2)
        self.assertEqual(target_row["excess_上证指数"], -5.5)
        rendered = render_forward_replay_html({"pairs": [], "notes": [], "summary": {"window_performance_comparison": comparison, "index_benchmark_summary": benchmark_summary}})
        chart_payload = sector_forward_replay._window_performance_chart_payload({"window_performance_comparison": comparison})
        chart_row = next(
            item for item in chart_payload["rows"]
            if item["label"] == "09:30-09:35买 / 14:30-14:55卖（原始）"
        )
        self.assertIn("月化代理收益", rendered)
        self.assertIn("折算周期", rendered)
        self.assertIn("窗口折算收益与指数对照图", rendered)
        self.assertIn("sector-window-return-chart", rendered)
        self.assertIn("sector-window-excess-chart", rendered)
        self.assertEqual(chart_row["sample_text"], "2/2")
        self.assertEqual(chart_row["excess_csi500_pct"], -5.5)
        self.assertIn(">2/2<", rows)
        self.assertIn("-5.50个百分点", rows)
        self.assertIn("+10.00%", benchmark_rows)

    def test_index_benchmark_requires_sample_boundary_coverage(self):
        pair_payloads = [
            {
                "effective_decision_date": "2026-01-02",
                "t0_market_context": {
                    "T0上证指数": "1000.00 / +0.00%",
                    "T0中证500": "待补",
                },
                "paper_strategy": {
                    "target_summary": {"primary_stock": "强样本(000001)"},
                    "target_evaluations": [
                        {
                            "stock_label": "强样本(000001)",
                            "tplus2_exit_review": {
                                "window_matrix": [
                                    {
                                        "buy_window_id": "open_0930_0935",
                                        "buy_window": "09:30-09:35",
                                        "sell_window_id": "late_1430_1455",
                                        "sell_window": "14:30-14:55",
                                        "entry_price": 10.0,
                                        "exit_price": 11.0,
                                        "return_pct": 10.0,
                                    }
                                ]
                            },
                        }
                    ],
                },
            },
            {
                "effective_decision_date": "2026-01-03",
                "t0_market_context": {
                    "T0上证指数": "1100.00 / +0.00%",
                    "T0中证500": "2000.00 / +0.00%",
                },
                "paper_strategy": {},
            },
        ]
        matrix_summary = sector_forward_replay._build_trade_window_matrix_summary(pair_payloads)
        benchmark_summary = sector_forward_replay._build_index_benchmark_summary(pair_payloads)
        comparison = sector_forward_replay._build_window_performance_comparison(
            pair_payloads,
            matrix_summary,
            benchmark_summary,
        )
        csi500_row = next(item for item in benchmark_summary["rows"] if item["label"] == "中证500")
        target_row = next(
            item for item in comparison["rows"]
            if item["buy_window_id"] == "open_0930_0935"
            and item["sell_window_id"] == "late_1430_1455"
            and item["exclusion"] == "未剔除接近涨停买点"
        )
        benchmark_rows = sector_forward_replay._render_index_benchmark_rows(
            {"index_benchmark_summary": benchmark_summary}
        )
        rendered = render_forward_replay_html(
            {"pairs": [], "notes": [], "summary": {"window_performance_comparison": comparison, "index_benchmark_summary": benchmark_summary}}
        )

        self.assertFalse(csi500_row["coverage_complete"])
        self.assertIsNone(csi500_row["cumulative_return_pct"])
        self.assertIsNone(target_row["excess_中证500"])
        self.assertIn("未覆盖样本首尾", benchmark_rows)
        self.assertIn("日线代理跑赢指数对照", rendered)
        self.assertIn("只在指数覆盖样本首尾时计算", rendered)

    def test_window_performance_chart_payload_escapes_script_breakout(self):
        comparison = {
            "rows": [
                {
                    "label": "恶意</script><img src=x onerror=alert(1)>",
                    "sample_count": 1,
                    "all_sample_count": 1,
                    "period_count": 1,
                    "cumulative_return_pct": 1.23,
                    "monthly_return_pct": 2.34,
                    "max_drawdown_pct": -0.56,
                    "excess_中证500": 0.78,
                    "exclusion": "测试",
                }
            ]
        }

        rendered = render_forward_replay_html(
            {"pairs": [], "notes": [], "summary": {"window_performance_comparison": comparison}}
        )

        self.assertIn("sector-window-chart-payload", rendered)
        self.assertIn("\\u003c/script", rendered)
        self.assertNotIn("</script><img", rendered)

    def test_window_performance_comparison_keeps_empty_filtered_row(self):
        pair_payloads = [
            {
                "effective_decision_date": "2026-01-02",
                "buy_date": "2026-01-05",
                "sell_date": "2026-01-06",
                "paper_strategy": {
                    "target_summary": {"primary_stock": "涨停样本(600001)"},
                    "target_evaluations": [
                        {
                            "stock_label": "涨停样本(600001)",
                            "tplus2_exit_review": {
                                "window_matrix": [
                                    {
                                        "buy_window_id": "open_0930_0935",
                                        "buy_window": "09:30-09:35",
                                        "sell_window_id": "late_1430_1455",
                                        "sell_window": "14:30-14:55",
                                        "entry_price": 11.0,
                                        "exit_price": 11.5,
                                        "return_pct": 4.55,
                                        "buy_window_entry_change_pct": 9.8,
                                        "buy_close_near_limit": True,
                                    },
                                    {
                                        "buy_window_id": "late_1430_1455",
                                        "buy_window": "14:30-14:55",
                                        "sell_window_id": "late_1430_1455",
                                        "sell_window": "14:30-14:55",
                                        "entry_price": 11.0,
                                        "exit_price": 11.5,
                                        "return_pct": 4.55,
                                        "buy_window_entry_change_pct": 9.8,
                                        "buy_close_near_limit": True,
                                    },
                                ]
                            },
                        }
                    ],
                },
            }
        ]
        matrix_summary = sector_forward_replay._build_trade_window_matrix_summary(pair_payloads)
        comparison = sector_forward_replay._build_window_performance_comparison(
            pair_payloads,
            matrix_summary,
            {"rows": []},
        )
        rows = sector_forward_replay._render_window_performance_comparison_rows(
            {"window_performance_comparison": comparison}
        )
        filtered_open_row = next(
            item for item in comparison["rows"]
            if item["label"] == "09:30-09:35买 / 14:30-14:55卖（剔除开盘接近涨停）"
        )
        filtered_late_row = next(
            item for item in comparison["rows"]
            if item["label"] == "14:30-14:55买 / 14:30-14:55卖（剔除收盘接近涨停）"
        )
        chart_payload = sector_forward_replay._window_performance_chart_payload(
            {"window_performance_comparison": comparison}
        )
        chart_filtered_row = next(
            item for item in chart_payload["rows"]
            if item["label"] == "09:30-09:35买 / 14:30-14:55卖（剔除开盘接近涨停）"
        )

        self.assertEqual(filtered_open_row["sample_count"], 0)
        self.assertEqual(filtered_open_row["all_sample_count"], 1)
        self.assertIsNone(filtered_open_row["monthly_return_pct"])
        self.assertEqual(filtered_late_row["sample_count"], 0)
        self.assertEqual(chart_filtered_row["sample_text"], "0/1")
        self.assertIsNone(chart_filtered_row["monthly_return_pct"])
        self.assertIn("剔开盘接近涨停", chart_filtered_row["short_label"])
        self.assertIn(">0/1<", rows)
        self.assertIn("剔除T+1开盘买点已接近涨停的样本", rows)

    def test_late_buy_window_exposes_close_near_limit_risk(self):
        window_matrix, _ = sector_forward_replay._build_window_matrix(
            {"name": "涨停样本", "code": "600001"},
            "2026-01-05",
            "2026-01-06",
            {
                "open": 10.2,
                "high": 11.0,
                "low": 10.1,
                "close": 11.0,
                "pre_close": 10.0,
                "source": "fake.daily",
            },
            {
                "open": 11.2,
                "high": 11.5,
                "low": 10.9,
                "close": 11.4,
                "pre_close": 11.0,
                "source": "fake.daily",
            },
        )
        pair_payload = {
            "effective_decision_date": "2026-01-02",
            "buy_date": "2026-01-05",
            "sell_date": "2026-01-06",
            "paper_strategy": {
                "target_summary": {"primary_stock": "涨停样本(600001)"},
                "target_evaluations": [
                    {
                        "stock_label": "涨停样本(600001)",
                        "tplus2_exit_review": {"window_matrix": window_matrix},
                    }
                ],
            },
        }

        matrix_summary = sector_forward_replay._build_trade_window_matrix_summary([pair_payload])
        late_row = next(
            row for row in matrix_summary["rows"]
            if row["buy_window_id"] == "late_1430_1455"
            and row["sell_window_id"] == "late_1430_1455"
        )
        grid = sector_forward_replay._trade_window_matrix_summary_grid(
            {"trade_window_matrix_summary": matrix_summary}
        )
        rows = sector_forward_replay._render_trade_window_matrix_summary_rows(
            {"trade_window_matrix_summary": matrix_summary}
        )

        self.assertEqual(late_row["average_buy_window_entry_change_pct"], 10.0)
        self.assertEqual(late_row["average_buy_day_change_pct"], 10.0)
        self.assertEqual(late_row["near_limit_buy_count"], 1)
        self.assertIn("尾盘买入代理可能只是理论可买", late_row["buyability_note"])
        self.assertIn("买点均涨幅 +10.00%", grid)
        self.assertIn("收盘接近涨停 1/1", grid)
        self.assertIn("尾盘买入代理可能只是理论可买", rows)

    def test_replay_marks_t0_tplus1_tplus2_price_path_and_buyability(self):
        price_refill = build_tushare_daily_price_refill(
            fetch_daily_price_bars_fn=lambda *args, **kwargs: [],
            fetch_daily_price_bars_by_trade_date_fn=lambda trade_date: {
                "2026-06-08": [
                    {"date": "2026-06-08", "stock_code": "603986", "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "data_source": "fake.daily"}
                ],
                "2026-06-09": [
                    {"date": "2026-06-09", "stock_code": "603986", "open": 109.0, "high": 112.0, "low": 108.8, "close": 110.0, "data_source": "fake.daily"}
                ],
                "2026-06-10": [
                    {"date": "2026-06-10", "stock_code": "603986", "open": 111.0, "high": 113.0, "low": 106.0, "close": 107.0, "data_source": "fake.daily"}
                ],
            }.get(trade_date, []),
        )
        minute_refill = build_static_minute_price_refill(
            {
                ("603986", "2026-06-09"): [
                    {"datetime": "2026-06-09 09:30:00", "open": 109.0, "high": 109.8, "low": 108.9, "close": 109.7},
                    {"datetime": "2026-06-09 09:35:00", "open": 109.7, "high": 110.0, "low": 109.6, "close": 110.0},
                ]
            },
            source_label="测试分时",
        )
        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09", "2026-06-10")],
            loader=self._data,
            price_refill=price_refill,
            minute_refill=minute_refill,
        )

        strategy = payload["pairs"][0]["paper_strategy"]
        primary = strategy["target_evaluations"][0]
        review = primary["tplus2_exit_review"]
        buyability = review["buyability_review"]
        rendered = render_forward_replay_html(payload)

        self.assertIn("price_path_review", review)
        self.assertEqual(review["price_path_review"]["t0"]["change_pct"], 2.0)
        self.assertEqual(review["price_path_review"]["tplus1"]["change_pct"], 7.84)
        self.assertEqual(review["price_path_review"]["tplus2"]["change_pct"], -2.73)
        self.assertEqual(review["price_path_review"]["tplus1"]["limit_state"], "接近涨停")
        self.assertEqual(buyability["status"], "可能买不到")
        self.assertIn("09:35前已接近涨停", buyability["reason"])
        self.assertEqual(payload["summary"]["buyability_summary"]["distribution"], {"可能买不到": 1})
        self.assertIn("真实可买性复核", rendered)
        self.assertIn("真实可买性分布", rendered)
        self.assertIn("T0/T+1/T+2价格路径", rendered)
        self.assertIn("可能买不到", rendered)

    def test_buyability_uses_limit_pool_proxy_when_minute_missing(self):
        price_refill = build_tushare_daily_price_refill(
            fetch_daily_price_bars_fn=lambda *args, **kwargs: [],
            fetch_daily_price_bars_by_trade_date_fn=lambda trade_date: {
                "2026-06-08": [
                    {"date": "2026-06-08", "stock_code": "603986", "open": 100.0, "high": 101.0, "low": 98.0, "close": 100.0, "data_source": "fake.daily"}
                ],
                "2026-06-09": [
                    {"date": "2026-06-09", "stock_code": "603986", "open": 110.0, "high": 110.0, "low": 110.0, "close": 110.0, "data_source": "fake.daily"}
                ],
                "2026-06-10": [
                    {"date": "2026-06-10", "stock_code": "603986", "open": 111.0, "high": 112.0, "low": 108.0, "close": 109.0, "data_source": "fake.daily"}
                ],
            }.get(trade_date, []),
        )

        def loader(date):
            data = json.loads(json.dumps(self._data(date), ensure_ascii=False))
            if date == "2026-06-09":
                data["zt_pool"] = [
                    {
                        "code": "603986",
                        "name": "兆易创新",
                        "涨停统计": "1/1",
                        "炸板次数": 0,
                        "首次封板时间": "092500",
                        "最后封板时间": "092500",
                        "change_pct": 10.0,
                        "open": 110.0,
                        "high": 110.0,
                        "low": 110.0,
                        "close": 110.0,
                    }
                ]
            return data

        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09", "2026-06-10")],
            loader=loader,
            price_refill=price_refill,
        )

        buyability = payload["pairs"][0]["paper_strategy"]["target_evaluations"][0]["tplus2_exit_review"]["buyability_review"]
        rendered = render_forward_replay_html(payload)

        self.assertEqual(buyability["status"], "可能买不到")
        self.assertIn("涨停池代理复核", buyability["reason"])
        self.assertIn("首次封板09:25", buyability["reason"])
        self.assertIn("不替代分时成交", buyability["minute_source"])
        self.assertEqual(buyability["proxy_source"], "涨停池")
        self.assertEqual(payload["summary"]["buyability_summary"]["distribution"], {"可能买不到": 1})
        self.assertIn("涨停池/日线代理复核", rendered)

    def test_buyability_prefers_minute_over_limit_pool_proxy(self):
        price_refill = build_tushare_daily_price_refill(
            fetch_daily_price_bars_fn=lambda *args, **kwargs: [],
            fetch_daily_price_bars_by_trade_date_fn=lambda trade_date: {
                "2026-06-08": [
                    {"date": "2026-06-08", "stock_code": "603986", "open": 100.0, "high": 101.0, "low": 98.0, "close": 100.0, "data_source": "fake.daily"}
                ],
                "2026-06-09": [
                    {"date": "2026-06-09", "stock_code": "603986", "open": 110.0, "high": 110.0, "low": 110.0, "close": 110.0, "data_source": "fake.daily"}
                ],
                "2026-06-10": [
                    {"date": "2026-06-10", "stock_code": "603986", "open": 109.0, "high": 111.0, "low": 107.0, "close": 108.0, "data_source": "fake.daily"}
                ],
            }.get(trade_date, []),
        )
        minute_refill = build_static_minute_price_refill(
            {
                ("603986", "2026-06-09"): [
                    {"datetime": "2026-06-09 09:30:00", "open": 101.0, "high": 101.5, "low": 100.8, "close": 101.2},
                    {"datetime": "2026-06-09 09:35:00", "open": 101.2, "high": 101.8, "low": 101.0, "close": 101.4},
                ]
            },
            source_label="测试分时",
        )

        def loader(date):
            data = json.loads(json.dumps(self._data(date), ensure_ascii=False))
            if date == "2026-06-09":
                data["zt_pool"] = [
                    {
                        "code": "603986",
                        "name": "兆易创新",
                        "涨停统计": "1/1",
                        "首次封板时间": "092500",
                        "change_pct": 10.0,
                        "open": 110.0,
                        "high": 110.0,
                        "low": 110.0,
                        "close": 110.0,
                    }
                ]
            return data

        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09", "2026-06-10")],
            loader=loader,
            price_refill=price_refill,
            minute_refill=minute_refill,
        )

        buyability = payload["pairs"][0]["paper_strategy"]["target_evaluations"][0]["tplus2_exit_review"]["buyability_review"]

        self.assertEqual(buyability["status"], "早盘未明显追高")
        self.assertEqual(buyability["minute_source"], "测试分时")
        self.assertNotIn("涨停池代理复核", buyability["reason"])

    def test_buyability_falls_back_to_proxy_when_minute_misses_early_window(self):
        price_refill = build_tushare_daily_price_refill(
            fetch_daily_price_bars_fn=lambda *args, **kwargs: [],
            fetch_daily_price_bars_by_trade_date_fn=lambda trade_date: {
                "2026-06-08": [
                    {"date": "2026-06-08", "stock_code": "603986", "open": 100.0, "high": 101.0, "low": 98.0, "close": 100.0, "data_source": "fake.daily"}
                ],
                "2026-06-09": [
                    {"date": "2026-06-09", "stock_code": "603986", "open": 110.0, "high": 110.0, "low": 110.0, "close": 110.0, "data_source": "fake.daily"}
                ],
                "2026-06-10": [
                    {"date": "2026-06-10", "stock_code": "603986", "open": 109.0, "high": 111.0, "low": 107.0, "close": 108.0, "data_source": "fake.daily"}
                ],
            }.get(trade_date, []),
        )
        minute_refill = build_static_minute_price_refill(
            {
                ("603986", "2026-06-09"): [
                    {"datetime": "2026-06-09 10:00:00", "open": 110.0, "high": 110.0, "low": 110.0, "close": 110.0},
                ]
            },
            source_label="测试分时",
        )

        def loader(date):
            data = json.loads(json.dumps(self._data(date), ensure_ascii=False))
            if date == "2026-06-09":
                data["zt_pool"] = [
                    {
                        "code": "603986",
                        "name": "兆易创新",
                        "涨停统计": "1/1",
                        "首次封板时间": "092500",
                        "change_pct": 10.0,
                        "open": 110.0,
                        "high": 110.0,
                        "low": 110.0,
                        "close": 110.0,
                    }
                ]
            return data

        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09", "2026-06-10")],
            loader=loader,
            price_refill=price_refill,
            minute_refill=minute_refill,
        )

        buyability = payload["pairs"][0]["paper_strategy"]["target_evaluations"][0]["tplus2_exit_review"]["buyability_review"]

        self.assertEqual(buyability["status"], "可能买不到")
        self.assertIn("分时事实未覆盖09:30-09:35", buyability["reason"])
        self.assertIn("涨停池代理复核", buyability["reason"])
        self.assertIn("测试分时", buyability["minute_source"])
        self.assertEqual(buyability["minute_count"], 1)

    def test_buyability_uses_hot_rank_proxy_when_minute_missing(self):
        price_refill = build_tushare_daily_price_refill(
            fetch_daily_price_bars_fn=lambda *args, **kwargs: [],
            fetch_daily_price_bars_by_trade_date_fn=lambda trade_date: {
                "2026-06-08": [
                    {"date": "2026-06-08", "stock_code": "603986", "open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0, "data_source": "fake.daily"}
                ],
                "2026-06-09": [
                    {"date": "2026-06-09", "stock_code": "603986", "open": 103.0, "high": 109.0, "low": 102.0, "close": 108.5, "data_source": "fake.daily"}
                ],
                "2026-06-10": [
                    {"date": "2026-06-10", "stock_code": "603986", "open": 109.0, "high": 112.0, "low": 106.0, "close": 107.0, "data_source": "fake.daily"}
                ],
            }.get(trade_date, []),
        )

        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09", "2026-06-10")],
            loader=self._data,
            price_refill=price_refill,
        )

        buyability = payload["pairs"][0]["paper_strategy"]["target_evaluations"][0]["tplus2_exit_review"]["buyability_review"]

        self.assertEqual(buyability["status"], "追高风险")
        self.assertIn("热榜/日线代理复核", buyability["reason"])
        self.assertIn("不替代分时成交", buyability["minute_source"])
        self.assertEqual(payload["summary"]["buyability_summary"]["distribution"], {"追高风险": 1})

    def test_buyability_uses_minute_even_when_tplus2_date_missing(self):
        price_refill = build_tushare_daily_price_refill(
            fetch_daily_price_bars_fn=lambda *args, **kwargs: [],
            fetch_daily_price_bars_by_trade_date_fn=lambda trade_date: {
                "2026-06-08": [
                    {"date": "2026-06-08", "stock_code": "603986", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "data_source": "fake.daily"}
                ],
                "2026-06-09": [
                    {"date": "2026-06-09", "stock_code": "603986", "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0, "data_source": "fake.daily"}
                ],
            }.get(trade_date, []),
        )
        minute_refill = build_static_minute_price_refill(
            {
                ("603986", "2026-06-09"): [
                    {"datetime": "2026-06-09 09:30:00", "open": 101.0, "high": 101.5, "low": 100.8, "close": 101.2},
                    {"datetime": "2026-06-09 09:35:00", "open": 101.2, "high": 101.8, "low": 101.0, "close": 101.4},
                ]
            },
            source_label="测试分时",
        )

        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09", None)],
            loader=self._data,
            price_refill=price_refill,
            minute_refill=minute_refill,
        )

        review = payload["pairs"][0]["paper_strategy"]["target_evaluations"][0]["tplus2_exit_review"]
        buyability = review["buyability_review"]

        self.assertEqual(review["missing_fields"], ["tplus2_sell_date"])
        self.assertEqual(buyability["status"], "早盘未明显追高")
        self.assertEqual(buyability["minute_count"], 2)
        self.assertEqual(buyability["minute_source"], "测试分时")

    def test_minute_refill_stops_after_repeated_source_errors(self):
        calls = []

        def fetch_minute_bars(code, trade_date):
            calls.append((code, trade_date))
            raise TimeoutError("minute source timeout")

        refill = build_tushare_minute_price_refill(
            fetch_minute_bars_fn=fetch_minute_bars,
            max_errors=1,
        )

        self.assertEqual(refill("603986", "2026-06-09"), [])
        self.assertEqual(refill("601991", "2026-06-10"), [])

        self.assertEqual(calls, [("603986", "2026-06-09")])
        self.assertEqual(refill.summary["errors"], 1)
        self.assertEqual(refill.summary["missing"], 2)
        self.assertIn("分时事实源连续错误", refill.summary["missing_samples"][-1])

    def test_target_action_summary_counts_targets_and_empty_days(self):
        payload = build_forward_replay_payload(
            [
                ("2026-06-01", "2026-06-02"),
                ("2026-06-05", "2026-06-08"),
                ("2026-06-08", "2026-06-09"),
            ],
            loader=self._data,
        )

        target_summary = payload["summary"]["target_action_summary"]
        rendered = render_forward_replay_html(payload)

        self.assertEqual(target_summary["sample_count"], 3)
        self.assertEqual(target_summary["target_day_count"], 2)
        self.assertEqual(target_summary["execution_empty_day_count"], 1)
        self.assertEqual(target_summary["skip_day_count"], 1)
        self.assertIn("2026-06-01", target_summary["execution_empty_dates"])
        self.assertIn("没有从已选板块中恢复出资金载体", target_summary["empty_reason_distribution"])
        self.assertIn("纸面主样本/空仓判定", rendered)
        self.assertIn("空仓判定", rendered)

    def test_t0_projection_groups_tplus2_emotion_and_sell_window_stats(self):
        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09", "2026-06-10")],
            loader=self._data,
        )

        summary = payload["summary"]
        rendered = render_forward_replay_html(payload)
        rows = summary["emotion_projection_summary"]["rows"]

        self.assertTrue(rows)
        self.assertIn("T0只生成T+1/T+2交易环境预案", summary["emotion_projection_summary"]["basis"])
        self.assertTrue(
            any(row["title"] == "T+2市场预案" for row in rows)
        )
        self.assertTrue(
            any(row["scorable_count"] >= row["calibrated_count"] + row["miss_count"] for row in rows)
        )
        self.assertFalse(any("accuracy_pct" in row for row in rows))
        self.assertTrue(
            any(row["return_stats"]["best_window"] for row in rows)
        )
        self.assertIn("T+2实际分布", rendered)
        self.assertIn("后验校准", rendered)
        self.assertIn("大体一致", rendered)
        self.assertNotIn("正确率", rendered)
        self.assertIn("偏离样本窗口", rendered)
        self.assertIn("全部窗口表现", rendered)
        self.assertIn("T0推演T+2交易环境", rendered)
        self.assertNotIn("胜率", rendered)

    def test_tushare_daily_price_refill_takes_priority_for_tplus2_review(self):
        trade_date_calls = []
        single_stock_calls = []

        def fetch_daily_bars_by_trade_date(trade_date):
            trade_date_calls.append(trade_date)
            bars = {
                "2026-06-09": [
                    {"date": "2026-06-09", "stock_code": "601991", "open": 6.0, "high": 6.2, "low": 5.9, "close": 6.0, "data_source": "fake.daily"},
                    {"date": "2026-06-09", "stock_code": "603986", "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "data_source": "fake.daily"},
                ],
                "2026-06-10": [
                    {"date": "2026-06-10", "stock_code": "601991", "open": 6.3, "high": 6.7, "low": 6.1, "close": 6.6, "data_source": "fake.daily"},
                    {"date": "2026-06-10", "stock_code": "603986", "open": 103.0, "high": 112.0, "low": 102.0, "close": 110.0, "data_source": "fake.daily"},
                ],
            }
            return bars.get(trade_date, [])

        def fetch_daily_bars(code, start_date, end_date, is_index=False):
            single_stock_calls.append((code, start_date, end_date, is_index))
            return []

        refill = build_tushare_daily_price_refill(
            fetch_daily_price_bars_fn=fetch_daily_bars,
            fetch_daily_price_bars_by_trade_date_fn=fetch_daily_bars_by_trade_date,
        )
        payload = build_forward_replay_payload(
            [("2026-06-08", "2026-06-09", "2026-06-10")],
            loader=self._data,
            price_refill=refill,
        )

        row = payload["pairs"][0]["evaluations"][0]
        review = row["tplus2_exit_review"]
        rendered = render_forward_replay_html(payload)

        self.assertEqual(review["entry_source"], "TuShare日线(fake.daily)")
        self.assertEqual(review["sell_source"], "TuShare日线(fake.daily)")
        self.assertEqual(review["windows"][0]["return_pct"], 5.0)
        self.assertEqual(len(review["window_matrix"]), 9)
        self.assertEqual(review["window_matrix"][-1]["return_pct"], 10.0)
        self.assertIn("买入价来源=TuShare日线(fake.daily)", review["windows"][0]["basis"])
        matrix_summary = payload["summary"]["trade_window_matrix_summary"]
        self.assertEqual(matrix_summary["best_combo"]["sell_window"], "14:30-14:55")
        self.assertEqual(matrix_summary["best_combo"]["average_return_pct"], 10.0)
        self.assertEqual(trade_date_calls, ["2026-06-08", "2026-06-09", "2026-06-10"])
        self.assertEqual(single_stock_calls, [])
        self.assertEqual(payload["price_refill_summary"]["filled"], 4)
        self.assertIn("TuShare事实源复核", rendered)
        self.assertIn("价格来源", rendered)
        embedded = _embedded_payload(rendered)
        self.assertEqual(embedded["price_refill_summary"]["filled"], 4)

    def test_tushare_daily_price_refill_rejects_wrong_trade_date_rows(self):
        trade_date_calls = []

        def fetch_daily_bars_by_trade_date(trade_date):
            trade_date_calls.append(trade_date)
            return [
                {
                    "date": "2026-06-16",
                    "stock_code": "601991",
                    "open": 6.0,
                    "high": 6.2,
                    "low": 5.9,
                    "close": 6.1,
                    "data_source": "fake.daily",
                }
            ]

        refill = build_tushare_daily_price_refill(
            fetch_daily_price_bars_fn=lambda *args, **kwargs: [],
            fetch_daily_price_bars_by_trade_date_fn=fetch_daily_bars_by_trade_date,
        )

        result = refill("601991", "2026-06-09")

        self.assertEqual(result, {})
        self.assertEqual(trade_date_calls, ["2026-06-09"])
        self.assertEqual(refill.summary["filled"], 0)
        self.assertEqual(refill.summary["missing"], 1)
        self.assertEqual(refill.summary["date_mismatch_samples"], ["2026-06-09 601991: 返回日期2026-06-16"])
        self.assertEqual(refill.summary["filled_samples"], [])

    def test_tushare_trade_calendar_extends_last_tplus2_sell_date(self):
        def fetch_open_trade_dates(start_date, end_date):
            if start_date == "2026-06-05":
                return ["2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"]
            return ["2026-06-11", "2026-06-12"]

        calendar = build_tushare_open_trade_date_refill(
            fetch_open_trade_dates_fn=fetch_open_trade_dates
        )
        pairs, discovery = discover_forward_replay_pairs(
            "2026-06-05",
            "2026-06-10",
            loader=self._data,
            trade_calendar_refill=calendar,
        )

        self.assertEqual(pairs[-1], ("2026-06-09", "2026-06-10", "2026-06-11"))
        self.assertEqual(discovery["trade_calendar_refill_summary"]["filled"], 1)
        self.assertEqual(discovery["trade_calendar_refill_summary"]["open_dates_filled"], 4)

        def fetch_daily_bars_by_trade_date(trade_date):
            bars = {
                "2026-06-10": [
                    {"date": "2026-06-10", "stock_code": "601991", "open": 6.4, "high": 6.7, "low": 6.28, "close": 6.56, "data_source": "fake.daily"}
                ],
                "2026-06-11": [
                    {"date": "2026-06-11", "stock_code": "601991", "open": 6.7, "high": 6.9, "low": 6.5, "close": 6.8, "data_source": "fake.daily"}
                ],
            }
            return bars.get(trade_date, [])

        payload = build_forward_replay_payload(
            pairs[-1:],
            loader=self._data,
            discovery=discovery,
            price_refill=build_tushare_daily_price_refill(
                fetch_daily_price_bars_fn=lambda *args, **kwargs: [],
                fetch_daily_price_bars_by_trade_date_fn=fetch_daily_bars_by_trade_date,
            ),
            trade_calendar_refill=calendar,
        )
        rendered = render_forward_replay_html(payload)

        self.assertEqual(payload["pairs"][0]["sell_date"], "2026-06-11")
        self.assertEqual(payload["trade_calendar_refill_summary"]["filled"], 1)
        self.assertIn("交易日期来源", rendered)
        self.assertIn("2026-06-10-&gt;2026-06-11", rendered)
        self.assertIn("缺少T+2日报事实", payload["pairs"][0]["emotion_review"]["tplus2_market"]["basis"])

    def test_trade_calendar_limits_forward_pairs_to_open_trade_dates(self):
        calendar = build_tushare_open_trade_date_refill(
            fetch_open_trade_dates_fn=lambda start_date, end_date: [
                "2026-04-03",
                "2026-04-07",
                "2026-04-08",
            ]
        )

        def loader(date):
            return {"selection_workflow": {"candidate_pool": []}, "hot_plates": []}

        pairs, discovery = discover_forward_replay_pairs(
            "2026-04-03",
            "2026-04-08",
            loader=loader,
            trade_calendar_refill=calendar,
        )

        self.assertEqual(pairs, [("2026-04-03", "2026-04-07", "2026-04-08"), ("2026-04-07", "2026-04-08", None)])
        self.assertEqual(discovery["available_dates"], ["2026-04-03", "2026-04-07", "2026-04-08"])
        self.assertEqual([item["date"] for item in discovery["skipped_dates"]], ["2026-04-04", "2026-04-05", "2026-04-06"])
        self.assertEqual(discovery["missing_dates"], [])
        self.assertEqual(discovery["trade_calendar_refill_summary"]["open_dates_filled"], 3)

    def test_small_account_review_marks_high_price_one_lot_as_near_full_position(self):
        def fetch_daily_bars_by_trade_date(trade_date):
            bars = {
                "2026-06-05": [
                    {"date": "2026-06-05", "stock_code": "603986", "open": 90.0, "high": 96.0, "low": 88.0, "close": 92.0, "data_source": "fake.daily"}
                ],
                "2026-06-08": [
                    {"date": "2026-06-08", "stock_code": "603986", "open": 95.0, "high": 100.0, "low": 90.0, "close": 96.0, "data_source": "fake.daily"}
                ],
                "2026-06-09": [
                    {"date": "2026-06-09", "stock_code": "603986", "open": 100.0, "high": 105.0, "low": 98.0, "close": 104.0, "data_source": "fake.daily"}
                ],
            }
            return bars.get(trade_date, [])

        payload = build_forward_replay_payload(
            [("2026-06-05", "2026-06-08", "2026-06-09")],
            loader=self._data,
            price_refill=build_tushare_daily_price_refill(
                fetch_daily_price_bars_fn=lambda *args, **kwargs: [],
                fetch_daily_price_bars_by_trade_date_fn=fetch_daily_bars_by_trade_date,
            ),
            account_capital=10000,
            lot_size=100,
        )

        account_row = payload["summary"]["small_account_summary"]["rows"][0]
        rendered = render_forward_replay_html(payload)

        self.assertEqual(account_row["one_lot_amount"], 9500.0)
        self.assertEqual(account_row["one_lot_account_pct"], 95.0)
        self.assertEqual(account_row["account_fit"], "一手接近满仓")
        self.assertIn("50%不能精确落账", account_row["position_50pct_basis"])
        self.assertIn("龙空龙", account_row["small_account_action"])
        self.assertIn("小账户一手换算", rendered)

    def test_small_account_review_keeps_unbuyable_action_when_buyability_is_tight(self):
        fit = sector_forward_replay._small_account_fit(
            178.478,
            account_capital=10000,
            lot_size=100,
            buyability_status="追高风险",
            paper_action="paper_participate",
        )

        self.assertEqual(fit["account_fit"], "当前账户买不了一手")
        self.assertIn("买不了一手", fit["small_account_action"])
        self.assertIn("不参与", fit["small_account_action"])
        self.assertNotIn("账户可买不等于可以买", fit["small_account_action"])

    def test_daily_rows_and_markdown_summary_include_csi500_and_small_account_fields(self):
        def loader(date):
            data = json.loads(json.dumps(self._data(date), ensure_ascii=False))
            data["indices"] = {
                "上证指数": {"price": 4010.03, "change_pct": 1.28},
                "创业板指": {"price": 3961.75, "change_pct": 3.93},
            }
            data["wind_a_alternative"] = {"name": "中证全指", "code": "000985", "price": 6254.74, "change_pct": 2.21}
            data["csi500_index"] = {"name": "中证500", "code": "000905", "price": 6262.0, "change_pct": 0.9}
            data["market_stats"] = {"up_count": 3322, "down_count": 2049}
            data["new_high_feedback"] = {"new_high_count": 82, "all_a_share_pct": 1.64}
            return data

        payload = build_forward_replay_payload(
            [("2026-06-09", "2026-06-10", "2026-06-11")],
            loader=loader,
            account_capital=10000,
            lot_size=100,
        )

        rows = build_forward_replay_daily_rows(payload, loader=loader)
        markdown = render_forward_replay_markdown_summary(payload, rows)

        self.assertEqual(rows[0]["T0中证500"], "6262.00 / +0.90%")
        self.assertEqual(rows[0]["T0涨跌家数"], "3322 / 2049")
        self.assertEqual(rows[0]["T0创新高全A占比"], "82 / 1.64% / 趋势扩散偏冷")
        self.assertIn("账户可做性", rows[0])
        self.assertIn("50%仓位口径", rows[0])
        self.assertIn("T0中证500", markdown)
        self.assertIn("小账户一手换算", markdown)

        html = render_forward_replay_html(payload)
        self.assertIn("T0市场底色", html)
        self.assertIn("中证500", html)
        self.assertIn("6262.00", html)
        self.assertIn("3322 / 2049", html)

    def test_daily_rows_refill_csi500_by_target_date(self):
        calls = []

        def fetch_csi500(target_date):
            calls.append(target_date)
            return {"name": "中证500", "code": "000905", "price": 6123.45, "change_pct": -0.67}

        def loader(date):
            data = json.loads(json.dumps(self._data(date), ensure_ascii=False))
            data["csi500_index"] = {"name": "中证500", "code": "000905", "price": 1.0, "change_pct": 9.99}
            return data

        payload = build_forward_replay_payload(
            [("2026-06-09", "2026-06-10", "2026-06-11")],
            loader=loader,
            account_capital=10000,
            lot_size=100,
        )
        rows = build_forward_replay_daily_rows(
            payload,
            loader=loader,
            index_context_refill=build_tushare_index_context_refill(fetch_csi500_fn=fetch_csi500),
        )

        self.assertEqual(calls, ["2026-06-09"])
        self.assertEqual(rows[0]["T0中证500"], "6123.45 / -0.67%")

    def test_payload_index_context_refill_updates_html_market_context(self):
        def loader(date):
            data = json.loads(json.dumps(self._data(date), ensure_ascii=False))
            data["csi500_index"] = {"name": "中证500", "code": "000905", "price": 1.0, "change_pct": 9.99}
            return data

        def fetch_csi500(target_date):
            return {"name": "中证500", "code": "000905", "price": 6123.45, "change_pct": -0.67}

        payload = build_forward_replay_payload(
            [("2026-06-09", "2026-06-10", "2026-06-11")],
            loader=loader,
            account_capital=10000,
            lot_size=100,
        )
        sector_forward_replay._apply_index_context_refill_to_payload(
            payload,
            build_tushare_index_context_refill(fetch_csi500_fn=fetch_csi500),
        )
        rendered = render_forward_replay_html(payload)

        self.assertIn("6123.45 / -0.67%", rendered)
        self.assertIn("T0市场底色", rendered)

    def test_forward_replay_loader_falls_back_to_snapshot_when_postgres_is_thin(self):
        calls = {"snapshot": 0, "postgres": 0}

        def fake_snapshot(date):
            calls["snapshot"] += 1
            return {"hot_plates": [{"name": "半导体"}], "target_date": date}, ""

        def fake_postgres(date):
            calls["postgres"] += 1
            return {"postgres_only": True}

        original_snapshot = sector_forward_replay.load_data_snapshot
        original_postgres = sector_forward_replay.load_daily_report_data_from_postgres
        try:
            sector_forward_replay.load_data_snapshot = fake_snapshot
            sector_forward_replay.load_daily_report_data_from_postgres = fake_postgres
            data = sector_forward_replay.load_daily_report_data_for_forward_replay("2026-04-01")
        finally:
            sector_forward_replay.load_data_snapshot = original_snapshot
            sector_forward_replay.load_daily_report_data_from_postgres = original_postgres

        self.assertEqual(calls["postgres"], 1)
        self.assertEqual(calls["snapshot"], 1)
        self.assertEqual(data["forward_replay_source"], "snapshot")
        self.assertIn("hot_plates", data)
        self.assertNotIn("postgres_only", data)

    def test_forward_replay_loader_falls_back_when_postgres_has_only_spine_and_indices(self):
        calls = {"snapshot": 0, "postgres": 0}

        def fake_snapshot(date):
            calls["snapshot"] += 1
            return {"hot_plates": [{"name": "半导体"}], "target_date": date}, ""

        def fake_postgres(date):
            calls["postgres"] += 1
            return {
                "selection_workflow": {"final": {"position_pct": 0}},
                "indices": {"上证指数": {"price": 1, "change_pct": 1}},
                "postgres_only": True,
            }

        original_snapshot = sector_forward_replay.load_data_snapshot
        original_postgres = sector_forward_replay.load_daily_report_data_from_postgres
        try:
            sector_forward_replay.load_data_snapshot = fake_snapshot
            sector_forward_replay.load_daily_report_data_from_postgres = fake_postgres
            data = sector_forward_replay.load_daily_report_data_for_forward_replay("2026-04-01")
        finally:
            sector_forward_replay.load_data_snapshot = original_snapshot
            sector_forward_replay.load_daily_report_data_from_postgres = original_postgres

        self.assertEqual(calls["postgres"], 1)
        self.assertEqual(calls["snapshot"], 1)
        self.assertEqual(data["forward_replay_source"], "snapshot")
        self.assertNotIn("postgres_only", data)

    def test_forward_replay_loader_keeps_complete_postgres_without_snapshot(self):
        calls = {"snapshot": 0, "postgres": 0}

        def fake_snapshot(date):
            calls["snapshot"] += 1
            return {"hot_plates": [{"name": "半导体"}], "target_date": date}, ""

        def fake_postgres(date):
            calls["postgres"] += 1
            return {
                "selection_workflow": {"final": {"position_pct": 0}},
                "hot_plates": [{"name": "半导体"}],
                "zt_pool": [{"stock_code": "000001"}],
                "zt_pool_by_sector": {"半导体": [{"stock_code": "000001"}]},
                "sector_fund_flow": {"inflow": [{"name": "半导体"}], "outflow": []},
                "integrated_hot_list": [{"name": "半导体"}],
                "turnover_rank": [{"name": "半导体"}],
                "market_stats": {"up_count": 1, "down_count": 1},
                "new_high_feedback": {"new_high_count": 1, "all_a_share_pct": 1.0},
                "indices": {"上证指数": {"price": 1, "change_pct": 1}},
                "postgres_only": True,
            }

        original_snapshot = sector_forward_replay.load_data_snapshot
        original_postgres = sector_forward_replay.load_daily_report_data_from_postgres
        try:
            sector_forward_replay.load_data_snapshot = fake_snapshot
            sector_forward_replay.load_daily_report_data_from_postgres = fake_postgres
            data = sector_forward_replay.load_daily_report_data_for_forward_replay("2026-06-05")
        finally:
            sector_forward_replay.load_data_snapshot = original_snapshot
            sector_forward_replay.load_daily_report_data_from_postgres = original_postgres

        self.assertEqual(calls["postgres"], 1)
        self.assertEqual(calls["snapshot"], 0)
        self.assertEqual(data["forward_replay_source"], "postgres")
        self.assertIn("selection_workflow", data)

    def test_forward_replay_payload_keeps_expansion_note_for_extended_range(self):
        payload = {
            "start_date": "2026-04-01",
            "end_date": "2026-06-15",
            "pairs": [],
            "notes": [],
            "sample_count": 0,
            "summary": {"coverage": {"requested_end_date": "2026-06-12"}},
            "discovery": {},
        }
        rendered = render_forward_replay_html(payload)

        self.assertIn("扩展观察区间", rendered)
        self.assertIn("不与主区间同权重", rendered)


if __name__ == "__main__":
    unittest.main()
