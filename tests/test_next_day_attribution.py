import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.next_day_attribution import (
    audit_next_day_attribution_packet,
    build_next_day_attribution,
    render_next_day_attribution_lines,
)
from report.report_acceptance_audit import audit_report_markdown


class NextDayAttributionTest(unittest.TestCase):
    def _packet(self):
        return build_next_day_attribution(
            report_date="2026-06-10",
            review_date="2026-06-11",
            final_target_resolution={
                "watch_target": {"code": "002409", "name": "雅克科技"},
                "new_entry_target": {},
            },
            position_decision={"position_plan_pct": 0},
            process_candidates=[
                {
                    "code": "002636",
                    "name": "金安国纪",
                    "identity_layer": "process_crossline",
                    "source_bucket": "crossline_observation_stocks",
                },
                {
                    "code": "002585",
                    "name": "双星新材",
                    "identity_layer": "process_observation",
                    "source_bucket": "extreme_conviction_list",
                },
            ],
            historical_evidence=[{"code": "688146", "name": "中船特气"}],
            next_day_quotes=[
                {
                    "code": "002409",
                    "name": "雅克科技",
                    "pct_chg": 10.0,
                    "review_date": "2026-06-11",
                    "source_name": "eastmoney",
                },
                {
                    "code": "002636",
                    "name": "金安国纪",
                    "pct_chg": 9.53,
                    "review_date": "2026-06-11",
                    "source_name": "eastmoney",
                },
                {
                    "code": "002585",
                    "name": "双星新材",
                    "pct_chg": -7.45,
                    "review_date": "2026-06-11",
                    "source_name": "eastmoney",
                },
                {
                    "code": "688146",
                    "name": "中船特气",
                    "pct_chg": 19.79,
                    "review_date": "2026-06-11",
                    "source_name": "eastmoney",
                },
            ],
            source_name="eastmoney",
            source_quote_time="2026-06-11 15:53:35",
        )

    def test_20260610_samples_are_counted_by_identity_layer(self):
        packet = self._packet()

        self.assertEqual(packet["schema_version"], "next_day_attribution.v1")
        by_code = {row["code"]: row for row in packet["rows"]}
        self.assertEqual(by_code["002409"]["counting_bucket"], "final_observation_hit")
        self.assertEqual(by_code["002636"]["counting_bucket"], "process_candidate_hit")
        self.assertEqual(by_code["002585"]["counting_bucket"], "process_candidate_miss")
        self.assertEqual(by_code["688146"]["counting_bucket"], "historical_followup")
        self.assertEqual(packet["summary"]["execution_hit_count"], 0)
        self.assertEqual(packet["summary"]["final_observation_hit_count"], 1)
        self.assertEqual(packet["summary"]["process_candidate_hit_count"], 1)
        self.assertEqual(packet["summary"]["process_candidate_miss_count"], 1)
        self.assertEqual(packet["summary"]["historical_followup_count"], 1)
        self.assertEqual(packet["summary"]["not_counted_as_execution_reason"], "报告没有明日执行对象")

    def test_packet_audit_rejects_execution_hit_without_plan(self):
        packet = self._packet()
        packet["summary"]["execution_hit_count"] = 1

        result = audit_next_day_attribution_packet(packet)

        self.assertFalse(result["passed"])
        self.assertEqual(result["findings"][0]["code"], "next_day_attribution_execution_hit_without_plan")

    def test_rendered_lines_keep_zero_position_from_execution_hit(self):
        rendered = "\n".join(render_next_day_attribution_lines(self._packet()))

        self.assertIn("## 次日归因闭环", rendered)
        self.assertIn("雅克科技(002409)", rendered)
        self.assertIn("final_observation_hit", rendered)
        self.assertIn("报告没有明日执行对象", rendered)
        self.assertNotIn("execution_hit |", rendered)

    def test_report_audit_rejects_process_candidate_counted_as_final(self):
        markdown = "\n".join(
            [
                "# 2026-06-10 a股市场分析",
                "",
                "## 次日归因闭环",
                "| 标的 | 日报身份 | 次日表现 | 结算桶 | 归因 |",
                "|------|----------|----------|--------|------|",
                "| 金安国纪(002636) | 跨线过程候选 | +9.53% | final_observation_hit | 错误混算 |",
            ]
        )

        result = audit_report_markdown(markdown)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("next_day_attribution_process_counted_as_final", codes)
