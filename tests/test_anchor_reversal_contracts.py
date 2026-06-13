import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.anchor_reversal_contracts import build_anchor_reversal_decision


class AnchorReversalContractsTest(unittest.TestCase):
    def test_marks_sector_anchor_as_primary_repair_target(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "大唐发电",
                "code": "601991",
                "sector": "电力",
                "reason": "电力板块锚定龙 / 趋势比价链锚点",
            },
            sector_snapshot=[
                {
                    "sector": "电力",
                    "anchor_name": "大唐发电",
                    "anchor_code": "601991",
                    "anchor_reason": "板块锚定龙",
                }
            ],
            mainline_name="电力",
        )

        self.assertEqual(decision["sector_anchor"], "大唐发电(601991)")
        self.assertEqual(decision["candidate_role"], "板块锚")
        self.assertEqual(decision["repair_priority"], "优先修复")
        self.assertEqual(decision["anchor_reversal_decision"], "可作为主对象")
        self.assertIn("资金回流优先看板块锚", decision["relationship_to_anchor"])

    def test_crossline_candidate_uses_own_sector_anchor_not_current_mainline_anchor(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "大有能源",
                "code": "600403",
                "sector": "煤炭开采",
                "reason": "T字板分歧转一致，明日可能加速+有量+板块龙一",
            },
            sector_snapshot=[
                {
                    "sector": "通信设备",
                    "anchor_name": "意华股份",
                    "anchor_code": "002897",
                    "anchor_reason": "当前主攻线板块锚",
                },
                {
                    "sector": "煤炭开采",
                    "anchor_name": "大有能源",
                    "anchor_code": "600403",
                    "anchor_reason": "煤炭分支锚",
                },
            ],
            mainline_name="通信设备",
        )

        self.assertEqual(decision["sector_anchor"], "大有能源(600403)")
        self.assertEqual(decision["candidate_role"], "板块锚")
        self.assertEqual(decision["anchor_reversal_decision"], "可作为主对象")
        self.assertIn("候选本身就是板块锚", decision["relationship_to_anchor"])
        self.assertNotIn("意华股份", decision["relationship_to_anchor"])

    def test_crossline_candidate_without_own_anchor_does_not_borrow_current_mainline_anchor(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "大有能源",
                "code": "600403",
                "sector": "煤炭开采",
                "reason": "5连板 / 趋势审美 / 平台呼吸",
            },
            sector_snapshot=[
                {
                    "sector": "半导体",
                    "anchor_name": "兆易创新",
                    "anchor_code": "603986",
                    "anchor_reason": "存储芯片方向容量锚",
                }
            ],
            mainline_name="半导体",
        )

        self.assertEqual(decision["sector_anchor"], "")
        self.assertEqual(decision["anchor_reversal_decision"], "降级观察")
        self.assertIn("本板块锚未识别", decision["relationship_to_anchor"])
        self.assertNotIn("兆易创新", " / ".join(str(value) for value in decision.values()))

    def test_requires_why_not_anchor_for_laggard_to_avoid_downgrade(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "京能电力",
                "code": "600578",
                "sector": "电力",
                "reason": "低位补涨 / 套利工具 / 被板块带动",
                "change_pct": 9.8,
            },
            sector_snapshot=[
                {
                    "sector": "电力",
                    "anchor_name": "大唐发电",
                    "anchor_code": "601991",
                    "anchor_reason": "板块锚定龙",
                }
            ],
            mainline_name="电力",
        )

        self.assertEqual(decision["sector_anchor"], "大唐发电(601991)")
        self.assertEqual(decision["candidate_role"], "套利工具")
        self.assertEqual(decision["repair_priority"], "后排修复")
        self.assertEqual(decision["anchor_reversal_decision"], "降级观察")
        self.assertEqual(decision["why_not_anchor"], "")
        self.assertIn("不能替代板块锚", decision["anchor_reversal_reason"])

    def test_allows_explicit_capacity_substitute_as_backup(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "华电辽能",
                "code": "600396",
                "sector": "电力",
                "reason": "大容量趋势龙头 / 中军承接",
                "capacity_profile": "大容量趋势资金",
                "why_not_anchor": "大唐发电短线加速过热，华电辽能承接更适合补位",
            },
            sector_snapshot=[
                {
                    "sector": "电力",
                    "anchor_name": "大唐发电",
                    "anchor_code": "601991",
                    "anchor_reason": "板块锚定龙",
                }
            ],
            mainline_name="电力",
        )

        self.assertEqual(decision["candidate_role"], "大容量中军")
        self.assertEqual(decision["repair_priority"], "次优先修复")
        self.assertEqual(decision["anchor_reversal_decision"], "可作为补位")
        self.assertIn("大唐发电短线加速过热", decision["why_not_anchor"])

    def test_accepts_why_not_sector_anchor_alias_for_capacity_backup(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "华电辽能",
                "code": "600396",
                "sector": "电力",
                "reason": "大容量趋势龙头 / 中军承接",
                "capacity_profile": "大容量趋势资金",
                "为什么不做板块锚": "大唐发电短线加速过热，华电辽能承接更适合补位",
            },
            sector_snapshot=[
                {
                    "sector": "电力",
                    "anchor_name": "大唐发电",
                    "anchor_code": "601991",
                    "anchor_reason": "板块锚定龙",
                }
            ],
            mainline_name="电力",
        )

        self.assertEqual(decision["candidate_role"], "大容量中军")
        self.assertEqual(decision["anchor_reversal_decision"], "可作为补位")
        self.assertIn("华电辽能承接更适合补位", decision["why_not_anchor"])

    def test_observation_sample_with_why_not_anchor_stays_observation(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "普通样本",
                "code": "000001",
                "sector": "电力",
                "reason": "普通趋势观察",
                "why_not_anchor": "大唐发电短线加速过热，普通样本弹性更高",
            },
            sector_snapshot=[
                {
                    "sector": "电力",
                    "anchor_name": "大唐发电",
                    "anchor_code": "601991",
                    "anchor_reason": "板块锚定龙",
                }
            ],
            mainline_name="电力",
        )

        self.assertEqual(decision["candidate_role"], "观察样本")
        self.assertEqual(decision["repair_priority"], "后排修复")
        self.assertEqual(decision["anchor_reversal_decision"], "降级观察")
        self.assertIn("不能替代板块锚", decision["anchor_reversal_reason"])

    def test_first_wave_dragon_label_alone_stays_observation_sample(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "宇环数控",
                "code": "002903",
                "sector": "通用设备",
                "reason": "首波先锋，仅作承接观察 / 首波龙一",
            },
            sector_snapshot=[
                {
                    "sector": "半导体",
                    "anchor_name": "兆易创新",
                    "anchor_code": "603986",
                    "anchor_reason": "主线容量核心",
                }
            ],
            mainline_name="半导体",
        )

        self.assertEqual(decision["candidate_role"], "观察样本")
        self.assertEqual(decision["anchor_reversal_decision"], "降级观察")
        self.assertEqual(decision["sector_anchor"], "")
        self.assertIn("本板块锚未识别", decision["anchor_reversal_reason"])
        self.assertNotIn("兆易创新", " / ".join(str(value) for value in decision.values()))

    def test_missing_sector_anchor_downgrades_until_anchor_is_identified(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "京能电力",
                "code": "600578",
                "sector": "电力",
                "reason": "低位补涨 / 套利工具 / 被板块带动",
            },
            sector_snapshot=[],
            mainline_name="电力",
        )

        self.assertEqual(decision["sector_anchor"], "")
        self.assertEqual(decision["candidate_role"], "套利工具")
        self.assertEqual(decision["repair_priority"], "待识别")
        self.assertEqual(decision["anchor_reversal_decision"], "降级观察")
        self.assertIn("板块锚未识别", decision["relationship_to_anchor"])

    def test_failed_anchor_makes_laggard_arbitrage_no_participation(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "晶方科技",
                "code": "603005",
                "sector": "半导体",
                "reason": "套利工具 / 跟风样本 / 被封测龙头带动",
            },
            sector_snapshot=[
                {
                    "sector": "半导体",
                    "anchor_name": "华天科技",
                    "anchor_code": "002185",
                    "anchor_status": "板块锚失效",
                    "anchor_reason": "华天科技、长电科技破位走弱",
                }
            ],
            mainline_name="半导体",
        )

        self.assertEqual(decision["sector_anchor"], "华天科技(002185)")
        self.assertEqual(decision["candidate_role"], "套利工具")
        self.assertEqual(decision["repair_priority"], "风险放大")
        self.assertEqual(decision["anchor_reversal_decision"], "不参与")
        self.assertIn("板块锚已失效", decision["relationship_to_anchor"])
        self.assertIn("后排风险更大", decision["anchor_reversal_reason"])

    def test_trade_narrative_sector_overrides_raw_industry_when_finding_anchor(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "工业富联",
                "code": "601138",
                "sector": "通信设备",
                "trade_narrative_sector": "AI算力基础设施",
                "raw_sector": "通信设备",
                "trade_narrative_reason": "当日叙事命中：工业富联获英伟达AI平台大额订单",
            },
            sector_snapshot=[
                {
                    "sector": "AI算力基础设施",
                    "anchor_name": "工业富联",
                    "anchor_code": "601138",
                    "anchor_reason": "AI服务器容量锚",
                },
                {
                    "sector": "通信设备",
                    "anchor_name": "新易盛",
                    "anchor_code": "300502",
                    "anchor_reason": "光模块弹性锚",
                },
            ],
        )

        self.assertEqual(decision["sector_anchor"], "工业富联(601138)")
        self.assertEqual(decision["candidate_role"], "板块锚")
        self.assertEqual(decision["anchor_reversal_decision"], "可作为主对象")

    def test_trade_narrative_migration_uses_narrative_anchor_before_raw_mainline_anchor(self):
        decision = build_anchor_reversal_decision(
            {
                "name": "工业富联",
                "code": "601138",
                "sector": "AI算力基础设施",
                "trade_narrative_sector": "AI算力基础设施",
                "raw_sector": "通信设备",
                "industry": "通信设备",
                "trade_narrative_reason": "当日叙事命中：工业富联获英伟达AI平台大额订单",
            },
            sector_snapshot=[
                {
                    "sector": "通信设备",
                    "anchor_name": "中天科技",
                    "anchor_code": "600522",
                    "anchor_reason": "通信设备趋势锚",
                },
                {
                    "sector": "AI算力基础设施",
                    "anchor_name": "工业富联",
                    "anchor_code": "601138",
                    "anchor_reason": "AI服务器容量锚",
                },
            ],
            mainline_name="通信设备",
        )

        self.assertEqual(decision["sector_anchor"], "工业富联(601138)")
        self.assertEqual(decision["candidate_role"], "板块锚")
        self.assertEqual(decision["anchor_reversal_decision"], "可作为主对象")


if __name__ == "__main__":
    unittest.main()
