import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export.zhongshu_visual_snapshot import normalize_visual_payload


class ZhongshuVisualSnapshotExportTest(unittest.TestCase):
    def test_normalize_visual_payload_keeps_kline_rows_and_zones(self):
        payload = normalize_visual_payload(
            {
                "success": True,
                "today_date": "2026-04-24",
                "today_price": 3042,
                "zhongshu_list": [
                    {
                        "start_date": "2026-04-20",
                        "end_date": "2026-04-24",
                        "zg": 3050,
                        "zd": 2988,
                        "kline_count": 5,
                        "segment_type": "zhongshu",
                    }
                ],
                "signal": {"status": "中枢内"},
            },
            [
                {
                    "date": "2026-04-24",
                    "open": 3036,
                    "high": 3050,
                    "low": 3026,
                    "close": 3042,
                    "volume": 130,
                    "amount": 1300,
                }
            ],
            date="2026-04-24",
            index_code="sh000001",
        )

        self.assertEqual(payload["date"], "2026-04-24")
        self.assertEqual(payload["index_code"], "sh000001")
        self.assertEqual(payload["market_zhongshu"]["zhongshu_list"][0]["zg"], 3050)
        self.assertEqual(payload["index_klines"]["sh000001"][0]["close"], 3042)

    def test_cli_writes_json_with_injected_runner(self):
        from export import zhongshu_visual_snapshot as module

        def fake_runner(target_date, index_code):
            return (
                {"success": True, "today_date": target_date, "today_price": 1, "zhongshu_list": [], "signal": {}},
                [{"date": target_date, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1}],
            )

        temp_dir = Path(tempfile.mkdtemp(prefix="zhongshu-visual-"))
        try:
            out = temp_dir / "visual.json"
            module.main(["--date", "2026-04-24", "--index-code", "sh000001", "--output", str(out)], runner=fake_runner)

            written = json.loads(out.read_text())
            self.assertEqual(written["date"], "2026-04-24")
            self.assertEqual(written["index_klines"]["sh000001"][0]["date"], "2026-04-24")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_security_visual_payload_exports_window_and_policy_contract(self):
        from export.security_zhongshu_visual_snapshot import normalize_security_visual_payload

        payload = normalize_security_visual_payload(
            {
                "success": True,
                "security_code": "603906",
                "security_name": "Longpan Tech",
                "security_type": "stock",
                "zhongshu_list": [],
                "signal": {},
            },
            [
                {
                    "date": "2026-04-29",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "volume": 100,
                    "amount": 1000,
                }
            ],
            date="2026-04-29",
            security_code="603906",
            security_name="Longpan Tech",
            security_type="stock",
        )

        self.assertEqual(payload["calculation_windows"]["structural_base_daily_bars"], 250)
        self.assertEqual(payload["calculation_windows"]["report_display_daily_bars"], 250)
        self.assertEqual(payload["calculation_windows"]["display_row_count"], 1)
        self.assertEqual(payload["security_klines"]["603906"][0]["close"], 10.5)
        self.assertEqual(payload["stock_klines"]["603906"][0]["date"], "2026-04-29")
        self.assertEqual(payload["strict_chanlun_policy"]["default_mode"], "practical_daily_mode")
        self.assertIn("practical_daily_node_runtime", payload["strict_chanlun_policy"]["source_algorithm"])
        self.assertEqual(payload["strict_chanlun_policy"]["security_type"], "stock")


if __name__ == "__main__":
    unittest.main()
