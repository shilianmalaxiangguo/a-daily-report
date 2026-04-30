import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.security_zhongshu_node import analyze_security_zhongshu_from_rows
from decision.zhongshu_runtime import analyze_market_zhongshu


def _platform_rows():
    return [
        {"date": "2026-04-15", "open": 99, "high": 105, "low": 95, "close": 100, "volume": 1, "amount": 10},
        {"date": "2026-04-16", "open": 100, "high": 104, "low": 96, "close": 101, "volume": 1, "amount": 10},
        {"date": "2026-04-17", "open": 101, "high": 103, "low": 97, "close": 100, "volume": 1, "amount": 10},
        {"date": "2026-04-20", "open": 100, "high": 104, "low": 96, "close": 102, "volume": 1, "amount": 10},
        {"date": "2026-04-21", "open": 101, "high": 105, "low": 95, "close": 103, "volume": 1, "amount": 10},
        {"date": "2026-04-22", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1, "amount": 10},
    ]


def _longpan_tail_candidate_rows():
    return [
        {"date": "2026-04-01", "open": 21.7, "high": 22.3, "low": 20.71, "close": 21.88, "volume": 1, "amount": 10},
        {"date": "2026-04-02", "open": 21.88, "high": 23.49, "low": 21.01, "close": 22.9, "volume": 1, "amount": 10},
        {"date": "2026-04-03", "open": 22.9, "high": 23.1, "low": 21.35, "close": 21.8, "volume": 1, "amount": 10},
        {"date": "2026-04-07", "open": 21.8, "high": 23.3, "low": 21.2, "close": 23.0, "volume": 1, "amount": 10},
        {"date": "2026-04-08", "open": 23.0, "high": 23.2, "low": 21.5, "close": 22.0, "volume": 1, "amount": 10},
        {"date": "2026-04-09", "open": 22.0, "high": 24.0, "low": 21.8, "close": 23.6, "volume": 1, "amount": 10},
        {"date": "2026-04-10", "open": 23.6, "high": 24.2, "low": 22.5, "close": 22.9, "volume": 1, "amount": 10},
        {"date": "2026-04-13", "open": 21.9, "high": 22.89, "low": 21.78, "close": 22.41, "volume": 1, "amount": 10},
        {"date": "2026-04-14", "open": 22.51, "high": 24.2, "low": 22.11, "close": 23.68, "volume": 1, "amount": 10},
        {"date": "2026-04-15", "open": 23.46, "high": 23.46, "low": 22.59, "close": 22.77, "volume": 1, "amount": 10},
        {"date": "2026-04-16", "open": 24.1, "high": 25.05, "low": 24.1, "close": 25.05, "volume": 1, "amount": 10},
        {"date": "2026-04-17", "open": 25.8, "high": 27.2, "low": 25.07, "close": 25.99, "volume": 1, "amount": 10},
        {"date": "2026-04-20", "open": 25.92, "high": 27.68, "low": 25.92, "close": 27.31, "volume": 1, "amount": 10},
        {"date": "2026-04-21", "open": 26.22, "high": 26.66, "low": 25.22, "close": 26.02, "volume": 1, "amount": 10},
        {"date": "2026-04-22", "open": 26.55, "high": 28.62, "low": 26.2, "close": 28.62, "volume": 1, "amount": 10},
        {"date": "2026-04-23", "open": 28.62, "high": 31.4, "low": 27.95, "close": 30.45, "volume": 1, "amount": 10},
        {"date": "2026-04-24", "open": 30.44, "high": 33.25, "low": 29.5, "close": 32.56, "volume": 1, "amount": 10},
        {"date": "2026-04-27", "open": 30.44, "high": 33.25, "low": 29.5, "close": 32.56, "volume": 1, "amount": 10},
        {"date": "2026-04-28", "open": 31.28, "high": 31.48, "low": 29.61, "close": 29.99, "volume": 1, "amount": 10},
    ]


class SecurityZhongshuNodeTest(unittest.TestCase):
    def test_analyze_security_zhongshu_from_rows_returns_stock_safe_structure(self):
        result = analyze_security_zhongshu_from_rows(
            _platform_rows(),
            security_code="002975",
            security_name="博杰股份",
            security_type="stock",
            target_date="2026-04-22",
            data_source="unit_fixture",
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["security_code"], "002975")
        self.assertEqual(result["security_name"], "博杰股份")
        self.assertEqual(result["security_type"], "stock")
        self.assertEqual(result["data_source"], "unit_fixture")
        self.assertEqual(result["signal"]["comparison_result"], "突破")
        self.assertEqual(result["signal"]["signal_type"], "个股突破")
        self.assertNotIn("大盘", result["signal"]["signal_type"])
        self.assertEqual(result["latest_structure_segment"]["segment_type"], "connector")
        self.assertIn("practical_daily_node_runtime", result["strict_chanlun_policy"]["source_algorithm"])

    def test_analyze_market_zhongshu_delegates_row_structure_to_security_node(self):
        delegated = {
            "success": True,
            "security_code": "sh000001",
            "security_name": "上证指数",
            "security_type": "index",
            "zhongshu_list": [],
            "current_zhongshu": None,
            "structure_segments": [],
            "latest_structure_segment": None,
            "today_price": 1.0,
            "today_date": "2026-04-22",
            "signal": {},
            "data_source": "test_feed",
            "strict_chanlun_policy": {"source_algorithm": "practical_daily_node_runtime; full_recursive_mode_deferred"},
        }
        frame = pd.DataFrame(_platform_rows())

        with patch("decision.security_zhongshu_node.analyze_security_zhongshu_from_frame", return_value=delegated) as node:
            result = analyze_market_zhongshu(
                index_code="sh000001",
                target_date="2026-04-22",
                fetch_dataframe=lambda **kwargs: (frame, "test_feed"),
                use_chanlun_confirmation=False,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertIs(result, delegated)
        node.assert_called_once()
        self.assertEqual(node.call_args.kwargs["security_type"], "index")
        self.assertEqual(node.call_args.kwargs["security_code"], "sh000001")

    def test_appends_tail_candidate_platform_without_promoting_to_confirmed(self):
        result = analyze_security_zhongshu_from_rows(
            _longpan_tail_candidate_rows(),
            security_code="603906",
            security_name="龙蟠科技",
            security_type="stock",
            target_date="2026-04-28",
            data_source="unit_fixture",
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["zhongshu_list"]), 1)
        self.assertEqual(result["current_zhongshu"]["segment_type"], "zhongshu")
        self.assertEqual(result["current_zhongshu"]["confirmation_status"], "confirmed")
        self.assertEqual(result["current_zhongshu"]["end_date"], "2026-04-20")

        latest = result["latest_structure_segment"]
        self.assertEqual(latest["segment_type"], "candidate_platform")
        self.assertEqual(latest["confirmation_status"], "forming")
        self.assertEqual(latest["candidate_status"], "tail_platform_candidate")
        self.assertTrue(latest["is_current_forming"])
        self.assertEqual(latest["start_date"], "2026-04-21")
        self.assertEqual(latest["end_date"], "2026-04-28")
        self.assertEqual(latest["kline_count"], 6)
        self.assertEqual(latest["zg"], 31.48)
        self.assertEqual(latest["zd"], 29.61)
        self.assertEqual(latest["departure_status"], "confirmed")
        self.assertEqual(latest["departure_direction"], "up")
        self.assertEqual(latest["departure_warning_date"], "2026-04-22")
        self.assertEqual(latest["departure_confirmed_date"], "2026-04-23")
        self.assertEqual(latest["departure_envelope_high"], 27.68)
        self.assertEqual(latest["departure_envelope_low"], 20.71)
        self.assertEqual(latest["departure_source_platform_start_date"], "2026-04-01")
        self.assertEqual(latest["departure_source_platform_end_date"], "2026-04-20")
        self.assertEqual([item["segment_type"] for item in result["structure_segments"]], ["zhongshu", "candidate_platform"])

    def test_keeps_comparison_day_out_of_tail_candidate_platform(self):
        rows = [
            *_longpan_tail_candidate_rows(),
            {"date": "2026-04-29", "open": 30.89, "high": 33.19, "low": 30.32, "close": 32.99, "volume": 1, "amount": 10},
        ]

        result = analyze_security_zhongshu_from_rows(
            rows,
            security_code="603906",
            security_name="龙蟠科技",
            security_type="stock",
            target_date="2026-04-29",
            data_source="unit_fixture",
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["today_date"], "2026-04-29")
        self.assertEqual(result["today_price"], 32.99)

        latest = result["latest_structure_segment"]
        self.assertEqual(latest["segment_type"], "candidate_platform")
        self.assertEqual(latest["confirmation_status"], "forming")
        self.assertEqual(latest["candidate_status"], "tail_platform_candidate")
        self.assertTrue(latest["is_current_forming"])
        self.assertEqual(latest["start_date"], "2026-04-21")
        self.assertEqual(latest["end_date"], "2026-04-28")
        self.assertEqual(latest["kline_count"], 6)
        self.assertEqual(latest["zg"], 31.48)
        self.assertEqual(latest["zd"], 29.61)
        self.assertEqual(latest["departure_status"], "confirmed")
        self.assertEqual(latest["departure_direction"], "up")
        self.assertEqual(latest["departure_warning_date"], "2026-04-22")
        self.assertEqual(latest["departure_confirmed_date"], "2026-04-23")
        self.assertEqual(latest["departure_envelope_high"], 27.68)
        self.assertEqual(latest["departure_envelope_low"], 20.71)
        self.assertEqual(latest["departure_source_platform_start_date"], "2026-04-01")
        self.assertEqual(latest["departure_source_platform_end_date"], "2026-04-20")


if __name__ == "__main__":
    unittest.main()
