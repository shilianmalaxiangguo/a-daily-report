import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.step1_sections import (
    build_step1_watch_sections,
    inject_step0_research_sections,
)


class ExecutionChainStep1SectionsTest(unittest.TestCase):
    def test_inject_step0_research_sections_replaces_placeholders(self):
        report = [
            "before",
            "<!-- MARKET_RESEARCH_SNAPSHOT_PLACEHOLDER -->",
            "<!-- STEP0_FOLLOW_PLACEHOLDER -->",
            "after",
        ]

        inject_step0_research_sections(
            report,
            market_research_snapshot={"state_machine": {"leading_line": "军工"}},
            step0_plan={"step0_prediction_cn": "🟢 跟随主线"},
            display_mvp_mode=False,
            render_market_research_snapshot_section=lambda snapshot, compact=False: ["market-snapshot"],
            render_step0_follow_section=lambda step0_plan, snapshot, compact=False: ["step0-follow"],
        )

        self.assertEqual(report, ["before", "market-snapshot", "step0-follow", "after"])

    def test_build_step1_watch_sections_renders_watch_candidates_and_memory(self):
        lines = build_step1_watch_sections(
            sector_trend_snapshot_step1=[{"sector": "军工", "trend_count": 3, "strong_count": 2, "limit_up_count": 1, "anchor_name": "军工一号", "anchor_code": "000001", "anchor_reason": "龙头"}],
            mainline_competition_snapshot=[{"role": "主攻线", "sector": "军工", "evidence": "涨停潮", "judgement": "最强", "action": "只盯核心"}],
            leader_memory_bank=[{"name": "老龙头", "code": "000002", "sector": "军工", "remember_reason": "老龙回流", "remember_window": "3日", "action_rule": "回看"}],
            tracking_memory_status={
                "today_seen_count": 3,
                "promoted_items": [{"code": "000002"}],
                "today_tentative_items": [],
                "dropped_items": [],
                "today_validated_items": [{"name": "老龙头", "code": "000002", "sources": ["watchlist"], "follow_state": "今日再次入池"}],
            },
            watchlist=[{"name": "军工一号", "code": "000001", "sector": "军工", "pattern": "涨停", "score": 88, "tomorrow_expectation": "连板预期", "reason": "板块龙一"}],
            abnormal_watch_pool=[{"name": "军工一号", "code": "000001", "sector": "军工", "abnormal_date": "2026-04-22", "setup_signal_label": "涨停异动", "follow_state": "跌不下去", "action_rule": "继续看"}],
            abnormal_projection_summary={"projection_label": "承接强化", "resilient_count": 1, "failed_count": 0, "projection_reason": "主线承接强", "action": "继续跟踪"},
            filtered_by_a_kill=[({"name": "冷却股", "code": "000003"}, {"a_kill_date": "2026-04-20", "remaining_days": 20})],
            display_mvp_mode=False,
            is_degraded_abnormal_snapshot=lambda item: False,
            format_abnormal_observation_columns=lambda item: ("历史锚点", "次日边界"),
        )

        rendered = "\n".join(lines)
        self.assertIn("#### Step 1 - 明天观察池", rendered)
        self.assertIn("**Step 1.05 龙头记忆库**", rendered)
        self.assertIn("**Step 1.3 异动后观察池**", rendered)
        self.assertIn("**Step 1 结论**:", rendered)
        self.assertIn("冷却股(000003)", rendered)


if __name__ == "__main__":
    unittest.main()
