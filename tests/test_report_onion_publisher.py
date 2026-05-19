import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_onion.publisher import (
    ReportSource,
    build_public_brief_payload,
    contains_forbidden_public_text,
    discover_report_sources,
    publish_report_onion,
    unwrap_snapshot_data,
)


def _snapshot(**overrides):
    data = {
        "market_research_snapshot": {
            "observation": {
                "zt_count": 98,
                "dt_count": 2,
                "rise_fall_ratio_text": "2.01",
                "turnover": 30485.42,
            },
            "state_machine": {
                "state_code": "migrate",
                "observation_summary": "上证-0.00% / 涨停98 / 跌停2 / 涨跌比2.01",
                "leading_line": "通信设备",
            },
            "mainline_rotation_snapshot": {
                "rotation_label": "分化整理",
                "rotation_action": "先看通信设备能否重新聚焦，支线只算轮动",
            },
            "final_gate": {
                "position_level": "二档（防守档）",
                "operation_state": "防守态",
                "can_new_entry": False,
                "final_action": "防守观察，只看主线核心",
            },
            "capital_conclusion": {
                "current_capital_state": "龙虎榜资金强，方向在未知",
                "mainline_attitude": "龙虎榜未验证通信设备",
            },
        },
        "mainline_turnover_summary": {
            "current_mainline": "通信设备",
            "previous_mainline": "通信设备",
            "conclusion": "主线未切换，通信设备仍是中心",
            "action_text": "继续围绕通信设备观察承接，不做多线扩散",
            "data_text": "最近1日主线 通信设备；成交额占比 6.2%，节奏偏持平",
        },
    }
    data.update(overrides)
    return {
        "date": "2026-05-08",
        "mode": "replay",
        "data": data,
    }


class ReportOnionPublicBriefTest(unittest.TestCase):
    def test_unwrap_snapshot_data_supports_saved_snapshot_envelope(self):
        self.assertEqual(unwrap_snapshot_data({"data": {"a": 1}}), {"a": 1})
        self.assertEqual(unwrap_snapshot_data({"a": 1}), {"a": 1})
        self.assertEqual(unwrap_snapshot_data(None), {})

    def test_build_public_brief_uses_snapshot_allowlist_only(self):
        payload = build_public_brief_payload(
            date="2026-05-08",
            title="2026-05-08 a股市场分析",
            mode="replay",
            source_version="snapshot:replay",
            snapshot=_snapshot(
                candidates=[
                    {"name": "大唐发电", "code": "601991", "score": 92},
                ],
                observation_pool={"top": "大唐发电(601991)"},
                candidate_ranking="PK决胜候选：大唐发电(601991)",
                execution_plan="竞价/开盘承接/回封/结构确认分层窗口",
                market_research_snapshot={
                    "observation": {
                        "zt_count": 98,
                        "dt_count": 2,
                        "rise_fall_ratio_text": "2.01",
                        "turnover": 30485.42,
                    },
                    "state_machine": {
                        "state_code": "migrate",
                        "observation_summary": "上证-0.00% / 涨停98 / 跌停2 / 涨跌比2.01",
                        "leading_line": "通信设备",
                    },
                    "mainline_rotation_snapshot": {
                        "rotation_label": "分化整理",
                        "rotation_action": "先看通信设备能否重新聚焦，支线只算轮动",
                    },
                    "final_gate": {
                        "position_level": "二档（防守档）",
                        "operation_state": "防守态",
                        "can_new_entry": False,
                        "final_action": "竞价/开盘承接/回封/结构确认分层窗口",
                    },
                    "capital_conclusion": {
                        "current_capital_state": "龙虎榜资金强，方向在未知",
                        "mainline_attitude": "龙虎榜未验证通信设备",
                    },
                },
            ),
        )

        self.assertEqual(payload["variant"], "public-brief")
        self.assertEqual(payload["sourcePolicy"], "snapshot-allowlist")
        self.assertTrue(payload["failClosed"])
        self.assertEqual(payload["summary"]["mainline"], "通信设备")
        self.assertEqual(payload["summary"]["positionGrade"], "二档（防守档）")
        self.assertFalse(payload["summary"]["canNewEntry"])
        self.assertIn("marketState", payload["summary"])
        self.assertIn("targets", payload["lockedFields"])
        self.assertIn("executionPlan", payload["lockedFields"])
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("大唐发电", serialized)
        self.assertNotIn("601991", serialized)
        self.assertNotIn("09:50-10:10", serialized)
        self.assertNotIn("买点", serialized)
        self.assertNotIn("PK决胜候选", serialized)

    def test_public_brief_returns_independent_locked_fields_list(self):
        first = build_public_brief_payload(
            date="2026-05-08",
            title="2026-05-08 a股市场分析",
            mode="replay",
            source_version="snapshot:replay",
            snapshot=_snapshot(),
        )
        first["lockedFields"].append("mutatedByConsumer")

        second = build_public_brief_payload(
            date="2026-05-08",
            title="2026-05-08 a股市场分析",
            mode="replay",
            source_version="snapshot:replay",
            snapshot=_snapshot(),
        )

        self.assertNotIn("mutatedByConsumer", second["lockedFields"])

    def test_public_brief_markdown_includes_focus_stocks_and_final_conclusion_appendix(self):
        payload = build_public_brief_payload(
            date="2026-05-08",
            title="2026-05-08 a股市场分析",
            mode="replay",
            source_version="snapshot:replay",
            snapshot=_snapshot(
                appendix_c={
                    "current_stock_monitoring_pool": [
                        {
                            "stock_name": "博杰股份",
                            "stock_code": "002975",
                            "source_pool": "主线核心",
                            "sector": "通信设备",
                            "current_action": "竞价/开盘承接/回封/结构确认分层窗口",
                        },
                        {
                            "stock_name": "宇环数控",
                            "stock_code": "002903",
                            "source_pool": "跨线观察",
                            "sector": "机器人",
                            "current_action": "只看不追",
                        },
                    ],
                },
            ),
        )

        markdown = payload["markdown"]
        self.assertIn("## 重点关注个股", markdown)
        self.assertIn("博杰股份", markdown)
        self.assertIn("宇环数控", markdown)
        self.assertIn("##### 附录：最终结论", markdown)
        self.assertIn("市场状态：防守态；主线：通信设备；仓位：二档（防守档）；执行细节不公开。", markdown)
        self.assertNotIn("002975", markdown)
        self.assertNotIn("002903", markdown)
        self.assertNotIn("09:50-10:10", markdown)
        self.assertNotIn("买点", markdown)

    def test_public_brief_fails_closed_when_structured_fields_are_missing(self):
        payload = build_public_brief_payload(
            date="2026-05-08",
            title="2026-05-08 a股市场分析",
            mode="frozen",
            source_version="snapshot:frozen",
            snapshot={"data": {}},
        )

        self.assertEqual(payload["summary"]["marketState"], "unavailable")
        self.assertEqual(payload["summary"]["mainline"], "locked")
        self.assertEqual(payload["summary"]["positionGrade"], "locked")
        self.assertIsNone(payload["summary"]["canNewEntry"])
        self.assertIn("marketState", payload["unavailableFields"])
        self.assertIn("mainline", payload["unavailableFields"])

    def test_forbidden_public_text_detector_blocks_codes_and_execution_terms(self):
        for text in [
            "大唐发电(601991)",
            "竞价/开盘承接/回封/结构确认分层窗口",
            "止损线是-5%",
            "09:50-10:10确认窗口",
            "PK决胜候选",
            "北交所标的830799",
            "北交所标的920118",
        ]:
            self.assertTrue(contains_forbidden_public_text(text), text)

        self.assertFalse(contains_forbidden_public_text("市场底色偏强，执行细节不公开"))


class ReportOnionPublisherIoTest(unittest.TestCase):
    def _write(self, root: Path, relative: str, text: str):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def _write_json(self, root: Path, relative: str, payload: dict):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _write_replay_inputs(self, root: Path):
        self._write(root, "reports/replay/2026-05-08_A股日报_完整版_replay.md", "# 2026-05-08 replay\n\n大唐发电(601991)")
        self._write(root, "reports/replay/2026-05-08_A股日报_执行摘要_replay.md", "# 2026-05-08 brief\n\n私有摘要")
        self._write_json(root, "snapshots/replay/2026-05-08_replay.json", _snapshot())

    def _write_frozen_inputs(self, root: Path, date: str):
        self._write(root, f"reports/{date}_A股日报_完整版.md", f"# {date} full\n\n历史完整日报")
        self._write(root, f"reports/{date}_A股日报_执行摘要.md", f"# {date} brief\n\n历史私有摘要")
        self._write_json(root, f"snapshots/{date}.json", _snapshot(date=date, mode="frozen"))

    def test_discover_report_sources_prefers_replay_over_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "reports/2026-05-08_A股日报_完整版.md", "# frozen title\n")
            self._write(root, "reports/2026-05-08_A股日报_执行摘要.md", "# frozen brief\n")
            replay_full = self._write(root, "reports/replay/2026-05-08_A股日报_完整版_replay.md", "# replay title\n")
            replay_brief = self._write(root, "reports/replay/2026-05-08_A股日报_执行摘要_replay.md", "# replay brief\n")
            replay_snapshot = self._write_json(root, "snapshots/replay/2026-05-08_replay.json", _snapshot())
            self._write_json(root, "snapshots/2026-05-08.json", _snapshot(mode="frozen"))

            sources = discover_report_sources(root)

            self.assertEqual([source.date for source in sources], ["2026-05-08"])
            self.assertEqual(sources[0].mode, "replay")
            self.assertEqual(sources[0].full_markdown_path, replay_full)
            self.assertEqual(sources[0].brief_markdown_path, replay_brief)
            self.assertEqual(sources[0].snapshot_path, replay_snapshot)

    def test_publish_report_onion_writes_public_and_private_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "snap-ui" / ".generated" / "daily-reports" / "public"
            private_dir = root / "snap-ui" / ".generated" / "daily-reports" / "private"
            self._write_replay_inputs(root)
            self._write_frozen_inputs(root, "2026-05-07")

            result = publish_report_onion(root=root, public_output_dir=public_dir, private_output_dir=private_dir)

            self.assertEqual(result["dates"], ["2026-05-08", "2026-05-07"])
            public_index = json.loads((public_dir / "index.json").read_text(encoding="utf-8"))
            private_index = json.loads((private_dir / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(public_index["reports"][0]["availableVariants"], ["public-brief", "full"])
            self.assertEqual(public_index["reports"][0]["lockedVariants"], ["private-brief"])
            self.assertEqual(public_index["reports"][1]["availableVariants"], ["public-brief", "full"])
            self.assertEqual(public_index["reports"][1]["lockedVariants"], ["private-brief"])
            self.assertEqual(
                public_index["reports"][0]["variants"]["full"]["contentPath"],
                "/data/daily-reports/2026-05-08.full.json",
            )
            self.assertEqual(public_index["reports"][0]["variants"]["full"]["access"], "public")
            self.assertEqual(public_index["reports"][0]["variants"]["full"]["policy"], "limited-free")
            self.assertEqual(
                public_index["reports"][1]["variants"]["full"]["contentPath"],
                "/data/daily-reports/2026-05-07.full.json",
            )
            self.assertNotIn("private-brief.json", json.dumps(public_index, ensure_ascii=False))
            self.assertEqual(private_index["reports"][0]["lockedVariants"], [])
            self.assertIn("private-brief", private_index["reports"][0]["availableVariants"])
            self.assertIn("full", private_index["reports"][0]["availableVariants"])
            self.assertIn("full", private_index["reports"][1]["availableVariants"])

            public_payload_text = (public_dir / "2026-05-08.public-brief.json").read_text(encoding="utf-8")
            self.assertNotIn("601991", public_payload_text)
            self.assertTrue((public_dir / "2026-05-08.full.json").exists())
            self.assertTrue((public_dir / "2026-05-07.full.json").exists())
            self.assertTrue((private_dir / "2026-05-08.full.json").exists())
            self.assertTrue((private_dir / "2026-05-07.full.json").exists())

    def test_publish_report_onion_fails_closed_without_markdown_fallback_when_snapshot_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "snap-ui" / ".generated" / "daily-reports" / "public"
            private_dir = root / "snap-ui" / ".generated" / "daily-reports" / "private"
            self._write(root, "reports/2026-05-08_A股日报_完整版.md", "# 2026-05-08 日报\n\n大唐发电(601991)")
            self._write(root, "reports/2026-05-08_A股日报_执行摘要.md", "# 2026-05-08 执行摘要\n\n09:50-10:10确认")
            self._write_json(root, "snapshots/2026-05-08.json", {"data": {}})

            publish_report_onion(root=root, public_output_dir=public_dir, private_output_dir=private_dir)

            public_payload_text = (public_dir / "2026-05-08.public-brief.json").read_text(encoding="utf-8")
            self.assertIn("unavailable", public_payload_text)
            self.assertIn("locked", public_payload_text)
            self.assertNotIn("大唐发电", public_payload_text)
            self.assertNotIn("601991", public_payload_text)
            self.assertNotIn("09:50-10:10", public_payload_text)

    def test_publish_report_onion_rejects_same_output_dir_without_resetting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_replay_inputs(root)
            output_dir = root / "snap-ui" / ".generated" / "daily-reports" / "shared"
            marker = self._write(root, "snap-ui/.generated/daily-reports/shared/marker.txt", "keep")

            with self.assertRaisesRegex(ValueError, "must be separate"):
                publish_report_onion(root=root, public_output_dir=output_dir, private_output_dir=output_dir)

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_publish_report_onion_rejects_private_dir_nested_inside_public_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_replay_inputs(root)
            public_dir = root / "snap-ui" / ".generated" / "daily-reports"
            private_dir = public_dir / "private"
            marker = self._write(root, "snap-ui/.generated/daily-reports/private/marker.txt", "keep")

            with self.assertRaisesRegex(ValueError, "must be sibling"):
                publish_report_onion(root=root, public_output_dir=public_dir, private_output_dir=private_dir)

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_publish_report_onion_rejects_dangerous_public_output_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_replay_inputs(root)
            marker = self._write(root, "reports/marker.txt", "keep")
            private_dir = root / "snap-ui" / ".generated" / "daily-reports" / "private"

            for public_dir in [
                root,
                root / "reports",
                root / "snapshots",
                root / "scripts",
                root / "tests",
                root / "wiki",
                root / "snap-ui",
            ]:
                with self.subTest(public_dir=public_dir):
                    with self.assertRaisesRegex(ValueError, "dangerous output directory"):
                        publish_report_onion(root=root, public_output_dir=public_dir, private_output_dir=private_dir)

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_publish_report_onion_rejects_dangerous_public_output_descendants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_replay_inputs(root)
            markers = [
                self._write(root, "reports/replay/marker.txt", "keep"),
                self._write(root, "snapshots/replay/marker.txt", "keep"),
                self._write(root, "scripts/report_onion/marker.txt", "keep"),
                self._write(root, "tests/fixtures/marker.txt", "keep"),
                self._write(root, "snap-ui/app/marker.txt", "keep"),
            ]
            private_dir = root / "snap-ui" / ".generated" / "daily-reports" / "private"

            for public_dir in [
                root / "reports" / "replay",
                root / "snapshots" / "replay",
                root / "scripts" / "report_onion",
                root / "tests" / "fixtures",
                root / "snap-ui" / "app",
            ]:
                with self.subTest(public_dir=public_dir):
                    with self.assertRaisesRegex(ValueError, "dangerous output directory"):
                        publish_report_onion(root=root, public_output_dir=public_dir, private_output_dir=private_dir)

            for marker in markers:
                self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_publish_report_onion_allows_generated_daily_report_output_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_replay_inputs(root)
            public_dir = root / "snap-ui" / ".generated" / "daily-reports" / "public"
            private_dir = root / "snap-ui" / ".generated" / "daily-reports" / "private"

            result = publish_report_onion(root=root, public_output_dir=public_dir, private_output_dir=private_dir)

            self.assertEqual(result["dates"], ["2026-05-08"])
            self.assertTrue((public_dir / "index.json").exists())
            self.assertTrue((private_dir / "index.json").exists())

    def test_publish_report_onion_public_dir_contains_only_public_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "snap-ui" / ".generated" / "daily-reports" / "public"
            private_dir = root / "snap-ui" / ".generated" / "daily-reports" / "private"
            self._write_replay_inputs(root)

            publish_report_onion(root=root, public_output_dir=public_dir, private_output_dir=private_dir)

            self.assertEqual(
                sorted(path.name for path in public_dir.iterdir()),
                ["2026-05-08.full.json", "2026-05-08.public-brief.json", "index.json"],
            )


if __name__ == "__main__":
    unittest.main()
