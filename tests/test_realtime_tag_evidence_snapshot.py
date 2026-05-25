import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class RealtimeTagEvidenceSnapshotTest(unittest.TestCase):
    def test_electronics_chain_adopts_specific_chip_branch_and_keeps_surface_names(self):
        from knowledge.realtime_tag_evidence_snapshot import build_realtime_tag_evidence_snapshot

        result = build_realtime_tag_evidence_snapshot(
            {
                "sector_fund_flow": {"inflow": [{"name": "元器件", "zljlr": 42.0}]},
                "concept_fund_flow": {
                    "inflow": [
                        {"name": "PCB", "zljlr": 21.0},
                        {"name": "国产芯片替代", "zljlr": 18.0},
                    ]
                },
                "hot_rank_top30": [{"name": "样本A", "concepts": ["芯片", "PCB"]}],
                "xueqiu_hot_stock_arguments": [
                    {"stock_name": "样本A", "argument": "国产芯片替代和PCB订单预期"}
                ],
            }
        )

        group = result["groups"][0]
        self.assertEqual(group["采用名称"], "国产芯片替代")
        self.assertEqual(group["大方向"], "泛半导体/硬科技电子")
        self.assertEqual(group["当日主攻分支"], "国产芯片替代")
        self.assertIn("元器件", group["表层行业名"])
        self.assertIn("PCB", group["辅助名称"])
        self.assertIn("热榜", group["注意力证据"])
        self.assertIn("资金", group["资金证据"])
        self.assertIn("国产芯片替代", result["adopted_labels"])

    def test_surface_component_label_without_branch_evidence_stays_surface_label(self):
        from knowledge.realtime_tag_evidence_snapshot import build_realtime_tag_evidence_snapshot

        result = build_realtime_tag_evidence_snapshot(
            {
                "sector_fund_flow": {"inflow": [{"name": "元器件", "zljlr": 12.0}]},
                "hot_rank_top30": [{"name": "样本B", "concepts": ["电子元件"]}],
            }
        )

        group = result["groups"][0]
        self.assertEqual(group["采用名称"], "元器件")
        self.assertEqual(group["大方向"], "")
        self.assertEqual(group["关系判断"], "证据不足")
        self.assertIn("没有细分分支证据", group["未采用名称及原因"])

    def test_consumer_electronics_is_kept_outside_semiconductor_family(self):
        from knowledge.realtime_tag_evidence_snapshot import build_realtime_tag_evidence_snapshot

        result = build_realtime_tag_evidence_snapshot(
            {
                "sector_fund_flow": {"inflow": [{"name": "消费电子", "zljlr": 30.0}]},
                "hot_rank_top30": [{"name": "样本C", "concepts": ["AI眼镜", "智能穿戴"]}],
                "eastmoney_label_rows": [{"name": "样本C", "labels": ["AI眼镜", "苹果概念"]}],
            }
        )

        group = result["groups"][0]
        self.assertEqual(group["采用名称"], "AI终端/消费电子")
        self.assertEqual(group["大方向"], "AI终端/消费电子")
        self.assertNotEqual(group["大方向"], "泛半导体/硬科技电子")
        self.assertIn("消费电子", group["表层行业名"])

    def test_ai_compute_and_pcb_keep_multi_branch_relationship(self):
        from knowledge.realtime_tag_evidence_snapshot import build_realtime_tag_evidence_snapshot

        result = build_realtime_tag_evidence_snapshot(
            {
                "hot_plates": [{"name": "数据中心"}, {"name": "液冷服务器"}, {"name": "PCB"}],
                "concept_fund_flow": {
                    "inflow": [
                        {"name": "数据中心", "zljlr": 35.0},
                        {"name": "PCB", "zljlr": 22.0},
                    ]
                },
                "xueqiu_hot_stock_arguments": [
                    {"name": "样本D", "argument": "液冷数据中心和PCB供应链共振"}
                ],
            }
        )

        adopted = {group["采用名称"]: group for group in result["groups"]}
        self.assertIn("AI算力基础设施", adopted)
        self.assertIn("PCB/电子材料", adopted)
        self.assertEqual(adopted["AI算力基础设施"]["关系判断"], "分支")
        self.assertEqual(adopted["PCB/电子材料"]["大方向"], "泛半导体/硬科技电子")
        self.assertIn("多分支", result["summary_text"])

    def test_ai_compute_branch_does_not_absorb_unrelated_surface_sectors(self):
        from knowledge.realtime_tag_evidence_snapshot import build_realtime_tag_evidence_snapshot

        result = build_realtime_tag_evidence_snapshot(
            {
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "元件", "zljlr": 174.0},
                        {"name": "通信设备", "zljlr": 166.0},
                        {"name": "消费电子", "zljlr": 77.0},
                    ]
                },
                "hot_plates": [{"name": "数据中心"}, {"name": "液冷服务器"}],
                "zt_pool_by_sector": {
                    "元器件": [{"code": "000725"}],
                    "公共交通": [{"code": "600611"}],
                    "家居用品": [{"code": "603833"}],
                    "软件服务": [{"code": "300059"}],
                },
                "xueqiu_hot_stock_arguments": [
                    {"name": "样本F", "argument": "液冷服务器带动数据中心算力链"}
                ],
            }
        )

        compute_group = {group["采用名称"]: group for group in result["groups"]}["AI算力基础设施"]
        self.assertIn("数据中心", compute_group["表层行业名"])
        self.assertIn("液冷服务器", compute_group["表层行业名"])
        self.assertNotIn("公共交通", compute_group["表层行业名"])
        self.assertNotIn("家居用品", compute_group["表层行业名"])
        self.assertNotIn("软件服务", compute_group["表层行业名"])
        self.assertNotIn("消费电子", compute_group["表层行业名"])

    def test_contradiction_text_marks_current_driver_as_constrained(self):
        from knowledge.realtime_tag_evidence_snapshot import build_realtime_tag_evidence_snapshot

        result = build_realtime_tag_evidence_snapshot(
            {
                "concept_fund_flow": {"inflow": [{"name": "AIDC", "zljlr": 16.0}]},
                "xueqiu_hot_stock_arguments": [{"name": "样本E", "argument": "AIDC数据中心合作预期"}],
                "stock_risk_map": {
                    "000001": {
                        "name": "样本E",
                        "risk_summary": "公司在AIDC数据中心领域尚未与美国客户达成合作",
                    }
                },
            }
        )

        group = result["groups"][0]
        self.assertIn("尚未", group["反证信息"])
        self.assertIn("反证", group["未采用名称及原因"])


if __name__ == "__main__":
    unittest.main()
