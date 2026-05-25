import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class SectorNarrativeAliasTest(unittest.TestCase):
    def test_hard_tech_electronics_family_keeps_surface_tags_and_driver_branches(self):
        from knowledge.sector_narrative_alias import build_sector_driver_tag_profile, resolve_sector_narrative_label

        tags = ["元件", "PCB", "MLCC", "CPO概念", "存储芯片", "芯片概念"]
        profile = build_sector_driver_tag_profile(tags)

        self.assertEqual(resolve_sector_narrative_label("元器件", tags), "泛半导体/硬科技电子")
        self.assertEqual(profile["family"], "泛半导体/硬科技电子")
        self.assertEqual(
            profile["driver_branches"],
            ["光通信/CPO", "存储/芯片", "PCB/电子材料", "被动元件/MLCC"],
        )
        self.assertIn("元件", profile["surface_tags"])

    def test_consumer_electronics_is_not_forced_into_semiconductor_family(self):
        from knowledge.sector_narrative_alias import build_sector_driver_tag_profile, resolve_sector_narrative_label

        tags = ["消费电子概念", "苹果概念", "AI眼镜", "智能穿戴"]
        profile = build_sector_driver_tag_profile(tags)

        self.assertEqual(resolve_sector_narrative_label("消费电子", tags), "AI终端/消费电子")
        self.assertEqual(profile["family"], "AI终端/消费电子")
        self.assertEqual(profile["driver_branches"], ["AI终端/消费电子"])

    def test_surface_component_label_without_driver_evidence_keeps_original_label(self):
        from knowledge.sector_narrative_alias import build_sector_driver_tag_profile, resolve_sector_narrative_label

        tags = ["数据中心", "储能", "AIDC", "铅酸电池"]
        profile = build_sector_driver_tag_profile(tags)

        self.assertEqual(resolve_sector_narrative_label("元器件", tags), "元器件")
        self.assertEqual(profile["family"], "AI算力基础设施")
        self.assertEqual(profile["driver_branches"], ["数据中心/液冷算力", "电力/储能"])

    def test_hotlist_non_semiconductor_families_keep_their_own_driver_branch(self):
        from knowledge.sector_narrative_alias import build_sector_driver_tag_profile, resolve_sector_narrative_label

        compute_tags = ["数据中心", "液冷服务器", "英伟达概念"]
        auto_tags = ["汽车电子", "无人驾驶", "小米概念"]
        power_tags = ["储能", "电力", "虚拟电厂"]
        robot_tags = ["人形机器人", "军工"]

        self.assertEqual(resolve_sector_narrative_label("数据中心", compute_tags), "AI算力基础设施")
        self.assertEqual(build_sector_driver_tag_profile(compute_tags)["driver_branches"], ["数据中心/液冷算力"])
        self.assertEqual(resolve_sector_narrative_label("汽车电子", auto_tags), "智能汽车")
        self.assertEqual(build_sector_driver_tag_profile(auto_tags)["driver_branches"], ["智能汽车/无人驾驶"])
        self.assertEqual(resolve_sector_narrative_label("储能", power_tags), "电力储能")
        self.assertEqual(build_sector_driver_tag_profile(power_tags)["driver_branches"], ["电力/储能"])
        self.assertEqual(resolve_sector_narrative_label("人形机器人", robot_tags), "人形机器人")
        self.assertEqual(build_sector_driver_tag_profile(robot_tags)["driver_branches"], ["人形机器人"])


if __name__ == "__main__":
    unittest.main()
