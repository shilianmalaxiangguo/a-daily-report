import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge.topic_lifecycle import (
    build_topic_lifecycle_snapshot,
    format_topic_lifecycle_for_report,
    write_topic_lifecycle_artifact,
)


class TopicLifecycleTest(unittest.TestCase):
    def test_observation_phase_defaults_to_observe_only(self):
        snapshot = build_topic_lifecycle_snapshot(
            {
                "trade_date": "2026-06-14",
                "realtime_tag_evidence_snapshot": {
                    "groups": [
                        {
                            "采用名称": "新概念A",
                            "大方向": "新方向",
                            "当日主攻分支": "新概念A",
                            "表层行业名": ["新概念A"],
                            "辅助名称": ["新概念A"],
                            "关系判断": "证据不足",
                            "注意力证据": "热榜出现，但资金未补齐",
                        }
                    ]
                },
            }
        )

        card = snapshot["cards"][0]
        self.assertEqual(card["lifecycle_phase"], "观察期")
        self.assertEqual(card["participation_qualification"], "只作观察证据")
        self.assertIn("先观察", card["report_effect"]["summary"])

    def test_main_attack_phase_uses_core_fund_spread_evidence(self):
        snapshot = build_topic_lifecycle_snapshot(
            {
                "trade_date": "2026-06-14",
                "realtime_tag_evidence_snapshot": {
                    "groups": [
                        {
                            "采用名称": "PCB电子材料",
                            "大方向": "AI算力基础设施",
                            "当日主攻分支": "PCB电子材料",
                            "表层行业名": ["PCB", "电子材料"],
                            "辅助名称": ["AI服务器PCB"],
                            "资金证据": "资金指向：PCB电子材料 / 核心票成交额放大",
                            "注意力证据": "热榜/雪球指向：AI服务器PCB",
                            "扩散证据": "同分支多只个股上涨",
                        }
                    ]
                },
                "candidate_traces": [
                    {
                        "stock_name": "胜宏科技",
                        "stock_code": "300476",
                        "sector": "PCB电子材料",
                        "mainline": "AI算力基础设施",
                        "final_action": "沿PCB电子材料核心承接继续观察",
                        "anchor_reversal": {
                            "candidate_role": "趋势核心",
                            "anchor_reversal_decision": "可作为主对象",
                            "anchor_reversal_reason": "核心承接稳定",
                        },
                    }
                ],
            }
        )

        card = snapshot["cards"][0]
        self.assertEqual(card["lifecycle_phase"], "主攻期")
        self.assertEqual(card["participation_qualification"], "进入淘汰赛复核")
        self.assertEqual(
            card["report_effect"]["boundary"],
            "题材阶段只作板块证据，不直接生成明日标的或个股资格。",
        )
        self.assertTrue(card["evidence"]["core_stocks"])
        self.assertTrue(card["evidence"]["spread_evidence"])

    def test_counter_evidence_pushes_topic_to_retreat(self):
        snapshot = build_topic_lifecycle_snapshot(
            {
                "trade_date": "2026-06-14",
                "realtime_tag_evidence_snapshot": {
                    "groups": [
                        {
                            "采用名称": "电力",
                            "大方向": "电力",
                            "当日主攻分支": "电力",
                            "表层行业名": ["电力"],
                            "资金证据": "资金指向：电力",
                            "反证信息": "高位一致后后排亏钱效应上升",
                        }
                    ]
                },
                "candidate_traces": [
                    {
                        "stock_name": "京能电力",
                        "stock_code": "600578",
                        "sector": "电力",
                        "mainline": "电力",
                        "final_action": "板块锚反推降级，只观察，不新增参与",
                        "anchor_reversal": {
                            "candidate_role": "套利工具",
                            "anchor_reversal_decision": "降级观察",
                            "anchor_reversal_reason": "套利工具不能替代板块锚",
                        },
                    }
                ],
            }
        )

        card = snapshot["cards"][0]
        self.assertEqual(card["lifecycle_phase"], "退潮期")
        self.assertEqual(card["participation_qualification"], "不进入明日复核")
        self.assertTrue(card["evidence"]["counter_evidence"])

    def test_previous_index_preserves_history_and_phase_age(self):
        previous_index = {
            "available_trade_dates": ["2026-06-12"],
            "by_topic_id": {
                "topic-pcb-electronic-materials": [
                    {
                        "trade_date": "2026-06-12",
                        "phase": "主攻期",
                        "participation_qualification": "进入淘汰赛复核",
                        "snapshot_path": "data/topic-lifecycle/2026-06-12.json",
                    }
                ]
            },
        }
        snapshot = build_topic_lifecycle_snapshot(
            {
                "trade_date": "2026-06-14",
                "realtime_tag_evidence_snapshot": {
                    "groups": [
                        {
                            "采用名称": "PCB电子材料",
                            "大方向": "AI算力基础设施",
                            "当日主攻分支": "PCB电子材料",
                            "表层行业名": ["PCB", "电子材料"],
                            "资金证据": "资金指向：PCB电子材料",
                            "扩散证据": "同分支多只个股上涨",
                        }
                    ]
                },
            },
            previous_index=previous_index,
        )

        card = snapshot["cards"][0]
        self.assertGreaterEqual(card["phase_age_trade_days"], 2)
        self.assertEqual(card["first_seen_trade_date"], "2026-06-12")

    def test_write_artifact_refreshes_daily_file_and_index(self):
        snapshot = build_topic_lifecycle_snapshot(
            {
                "trade_date": "2026-06-14",
                "source_report": {"path": "reports/2026-06-14_A股日报_完整版.md", "variant": "full"},
                "realtime_tag_evidence_snapshot": {
                    "groups": [
                        {
                            "采用名称": "AI算力基础设施",
                            "大方向": "AI算力基础设施",
                            "当日主攻分支": "AI算力基础设施",
                            "表层行业名": ["数据中心", "液冷服务器"],
                            "资金证据": "资金指向：AI算力基础设施",
                            "扩散证据": "同分支多只个股上涨",
                        }
                    ]
                },
                "candidate_traces": [
                    {
                        "stock_name": "工业富联",
                        "stock_code": "601138",
                        "sector": "AI算力基础设施",
                        "mainline": "AI算力基础设施",
                        "final_action": "沿AI算力基础设施核心承接继续观察",
                        "anchor_reversal": {
                            "candidate_role": "大容量中军",
                            "anchor_reversal_decision": "可作为补位",
                            "anchor_reversal_reason": "核心承接稳定",
                        },
                    }
                ],
            }
        )

        with tempfile.TemporaryDirectory() as tempdir:
            result = write_topic_lifecycle_artifact(snapshot, root_dir=Path(tempdir))

            snapshot_path = Path(result["snapshot_path"])
            index_path = Path(result["index_path"])
            self.assertTrue(snapshot_path.exists())
            self.assertTrue(index_path.exists())
            stored_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            stored_index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(stored_snapshot["trade_date"], "2026-06-14")
            self.assertEqual(stored_index["latest_trade_date"], "2026-06-14")
            self.assertTrue(stored_index["active_topics"])
            topic_id = stored_snapshot["cards"][0]["topic_id"]
            self.assertIn(topic_id, stored_index["by_topic_id"])

    def test_formatter_stays_short_and_uses_trading_language(self):
        snapshot = {
            "cards": [
                {
                    "topic_name": "PCB电子材料",
                    "lifecycle_phase": "分歧承接期",
                    "participation_qualification": "只让核心进入复核",
                    "evidence": {
                        "launch_catalyst": ["AI服务器PCB"],
                        "fund_attack": ["资金指向：PCB电子材料"],
                        "core_stocks": [{"name": "胜宏科技", "code": "300476", "role": "趋势核心"}],
                        "spread_evidence": ["同分支多只个股上涨"],
                        "divergence_evidence": ["后排冲高回落"],
                        "acceptance_evidence": ["核心票回撤后承接未破"],
                        "counter_evidence": [],
                    },
                    "report_effect": {
                        "summary": "PCB电子材料处于分歧承接期，明日只看核心承接，不从后排补涨里找机会。",
                    },
                }
            ]
        }

        lines = format_topic_lifecycle_for_report(snapshot)
        rendered = "\n".join(lines)
        self.assertLessEqual(len(lines), 5)
        self.assertIn("只让核心进入复核", rendered)
        self.assertIn("不从后排补涨里找机会", rendered)
        self.assertIn("不直接生成明日标的或个股资格", rendered)
        self.assertNotIn("可进入候选比较", rendered)
        self.assertNotIn("7天", rendered)
        self.assertNotIn("辩论", rendered)

    def test_topic_lifecycle_never_outputs_tomorrow_target(self):
        snapshot = build_topic_lifecycle_snapshot(
            {
                "trade_date": "2026-06-14",
                "realtime_tag_evidence_snapshot": {
                    "groups": [
                        {
                            "采用名称": "PCB电子材料",
                            "大方向": "AI算力基础设施",
                            "当日主攻分支": "PCB电子材料",
                            "表层行业名": ["PCB", "电子材料"],
                            "资金证据": "资金指向：PCB电子材料",
                            "扩散证据": "同分支多只个股上涨",
                        }
                    ]
                },
                "candidate_traces": [
                    {
                        "stock_name": "胜宏科技",
                        "stock_code": "300476",
                        "sector": "PCB电子材料",
                        "mainline": "AI算力基础设施",
                        "final_action": "沿PCB电子材料核心承接继续观察",
                        "anchor_reversal": {
                            "candidate_role": "趋势核心",
                            "anchor_reversal_decision": "可作为主对象",
                            "anchor_reversal_reason": "核心承接稳定",
                        },
                    }
                ],
            }
        )

        rendered = "\n".join(format_topic_lifecycle_for_report(snapshot))

        self.assertIn("进入淘汰赛复核", rendered)
        self.assertIn("不直接生成明日标的或个股资格", rendered)
        self.assertNotIn("明日目标", rendered)
        self.assertNotIn("买入资格", rendered)


if __name__ == "__main__":
    unittest.main()
