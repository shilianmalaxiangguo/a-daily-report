import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.mvp_compactor import compact_report_for_mvp


class MvpCompactorTest(unittest.TestCase):
    def test_compact_report_for_mvp_uses_dynamic_stage_headings(self):
        stage_lookup = {
            "environment_follow": {"stage_key": "environment_follow", "label": "环节0", "title": "环境裁决"},
            "watch_pool": {"stage_key": "watch_pool", "label": "环节1", "title": "候选观察"},
        }
        report = [
            "## 二、预期日历（AI智能分析板块）",
            "日历块",
            "## 十三、统一执行链（狙击手视角）",
            "### 总-市场整体判断",
            "市场总览",
            "#### 环节0 - 环境裁决",
            "保留环境裁决",
            "#### 环节1 - 候选观察",
            "这段应该整体被裁掉",
            "#### 最终结论",
            "保留最终结论",
            "## 十四、市场快照",
            "洞察",
            "## 十五、策略计划账本",
            "策略账本",
        ]

        compacted = compact_report_for_mvp(report, stage_lookup=stage_lookup)
        rendered = "\n".join(compacted)

        self.assertIn("#### 环节0 - 环境裁决", rendered)
        self.assertIn("#### 最终结论", rendered)
        self.assertNotIn("市场总览", rendered)
        self.assertNotIn("这段应该整体被裁掉", rendered)
        self.assertNotIn("日历块", rendered)
        self.assertNotIn("洞察", rendered)
        self.assertIn("## 二、统一执行链", rendered)
        self.assertIn("## 三、策略计划账本", rendered)


if __name__ == "__main__":
    unittest.main()
