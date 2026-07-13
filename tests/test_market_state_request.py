import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.request import collect_market_state_request_bundle, _load_csi1000_from_same_day_run_log


class _TimerStub:
    def __init__(self):
        self.records = []

    def record(self, label, order):
        self.records.append((label, order))
        return 0.1, 0.2


def _index_validation_success(data, target_date):
    return {
        "schema_version": "report_index_cross_validation.v1",
        "target_date": target_date,
        "status": "success",
        "verification_provider": "tencent.fqkline.day",
        "checks": [{"name": f"指数{index}", "status": "success"} for index in range(6)],
        "failures": [],
    }


class MarketStateRequestTest(unittest.TestCase):
    def test_collect_market_state_request_bundle_collects_first_request_slice(self):
        timer = _TimerStub()
        emitted = []
        request_registry = {
            "total_turnover": lambda *, target_date: 12345.6,
            "major_indices": lambda *, target_date: [
                {"code": "000001", "change_pct": 1.2, "data_source": "tushare.index_daily"}
            ],
            "wind_a": lambda *, target_date: {
                "price": 5432.1,
                "change_pct": 0.8,
                "data_source": "tushare.index_daily",
            },
            "csi500": lambda *, target_date: {
                "price": 6262.0,
                "change_pct": 0.9,
                "data_source": "tushare.index_daily",
            },
            "csi1000": lambda *, target_date: {
                "price": 6123.4,
                "change_pct": 1.1,
                "data_source": "tushare.index_daily",
            },
        }

        result = collect_market_state_request_bundle(
            "2026-07-13",
            request_registry=request_registry,
            index_cross_validator=_index_validation_success,
            require_index_cross_validation=True,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["total_turnover"], 12345.6)
        self.assertEqual(result["results"]["turnover_data"]["date"], "2026-07-13")
        self.assertEqual(result["results"]["indices"][0]["code"], "000001")
        self.assertEqual(result["results"]["wind_a_alternative"]["price"], 5432.1)
        self.assertEqual(result["results"]["csi500_index"]["price"], 6262.0)
        self.assertEqual(result["results"]["csi1000_index"]["price"], 6123.4)
        self.assertTrue(result["data_status"]["两市成交额"])
        self.assertTrue(result["data_status"]["主要指数"])
        self.assertTrue(result["data_status"]["中证全指"])
        self.assertTrue(result["data_status"]["中证500"])
        self.assertTrue(result["data_status"]["中证1000"])
        self.assertTrue(result["step_status"]["两市成交额获取"])
        self.assertTrue(result["step_status"]["主要指数获取"])
        self.assertTrue(result["step_status"]["中证全指获取"])
        self.assertTrue(result["step_status"]["中证500获取"])
        self.assertTrue(result["step_status"]["中证1000获取"])
        self.assertTrue(result["data_status"]["指数交叉核对"])
        self.assertTrue(result["step_status"]["指数交叉核对"])
        self.assertEqual(len(result["module_logs"]), 6)
        self.assertEqual(timer.records[0], ("两市成交额获取", 1))
        self.assertTrue(any("两市成交额" in line for line in emitted))
        self.assertIn("  1️⃣ 获取两市成交额（Tushare 优先）...", emitted)
        self.assertIn("  2️⃣ 获取三大指数（Tushare 优先）...", emitted)
        self.assertIn("  3️⃣ 获取中证全指（Tushare 优先）...", emitted)
        self.assertIn("  3.5️⃣ 获取中证500（Tushare 优先）...", emitted)
        self.assertIn("  3.6️⃣ 获取中证1000（Tushare 优先）...", emitted)
        self.assertIn("  3.7️⃣ 交叉核对六个指数（Tushare + 腾讯日K）...", emitted)
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.total_turnover"], "tushare-first")
        self.assertEqual(provider_by_step["request.major_indices"], "tushare.index_daily")
        self.assertEqual(provider_by_step["request.wind_a"], "tushare.index_daily")
        self.assertEqual(provider_by_step["request.csi500"], "tushare.index_daily")
        self.assertEqual(provider_by_step["request.csi1000"], "tushare.index_daily")
        self.assertEqual(provider_by_step["request.index_cross_validation"], "tencent.fqkline.day")

    def test_collect_market_state_request_bundle_backfills_csi1000_from_same_day_fact(self):
        timer = _TimerStub()
        emitted = []
        request_registry = {
            "total_turnover": lambda *, target_date: 12345.6,
            "major_indices": lambda *, target_date: [
                {"code": "000001", "change_pct": 1.2, "data_source": "tushare.index_daily"}
            ],
            "wind_a": lambda *, target_date: {
                "price": 5432.1,
                "change_pct": 0.8,
                "data_source": "tushare.index_daily",
            },
            "csi500": lambda *, target_date: {
                "price": 6262.0,
                "change_pct": 0.9,
                "data_source": "tushare.index_daily",
            },
            "csi1000": lambda *, target_date: {"price": 0, "change_pct": 0},
            "csi1000_fact": lambda *, target_date: {
                "price": 8318.7,
                "change_pct": 2.94,
                "trade_date": target_date,
                "data_source": "postgresql.index_daily_bars",
            },
        }

        result = collect_market_state_request_bundle(
            "2026-06-09",
            request_registry=request_registry,
            index_cross_validator=_index_validation_success,
            require_index_cross_validation=False,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["csi1000_index"]["price"], 8318.7)
        self.assertEqual(result["results"]["csi1000_index"]["data_source"], "postgresql.index_daily_bars")
        self.assertTrue(result["data_status"]["中证1000"])
        self.assertTrue(result["step_status"]["中证1000获取"])
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.csi1000"], "postgresql.index_daily_bars")
        self.assertTrue(any("中证1000" in line and "8318.70" in line for line in emitted))

    def test_collect_market_state_request_bundle_marks_failed_index_cross_validation(self):
        timer = _TimerStub()
        emitted = []
        request_registry = {
            "total_turnover": lambda *, target_date: 12345.6,
            "major_indices": lambda *, target_date: {},
            "wind_a": lambda *, target_date: {"price": 6001.65, "change_pct": -3.43},
            "csi500": lambda *, target_date: {"price": 8138.14, "change_pct": -4.30},
            "csi1000": lambda *, target_date: {"price": 7787.85, "change_pct": -5.01},
        }

        result = collect_market_state_request_bundle(
            "2026-07-13",
            request_registry=request_registry,
            index_cross_validator=lambda data, target_date: {
                "schema_version": "report_index_cross_validation.v1",
                "target_date": target_date,
                "status": "failed",
                "verification_provider": "tencent.fqkline.day",
                "checks": [],
                "failures": ["上证指数：主来源日期为2026-07-10"],
            },
            require_index_cross_validation=True,
            timer=timer,
            emit=emitted.append,
        )

        self.assertFalse(result["data_status"]["指数交叉核对"])
        self.assertFalse(result["step_status"]["指数交叉核对"])
        self.assertEqual(result["results"]["index_cross_validation"]["status"], "failed")
        self.assertTrue(any("上证指数" in line for line in emitted))

    def test_collect_market_state_request_bundle_skips_validation_before_contract_start(self):
        timer = _TimerStub()
        emitted = []
        request_registry = {
            "total_turnover": lambda *, target_date: 12345.6,
            "major_indices": lambda *, target_date: [],
            "wind_a": lambda *, target_date: {"price": 6001.65, "change_pct": -3.43},
            "csi500": lambda *, target_date: {"price": 8138.14, "change_pct": -4.30},
            "csi1000": lambda *, target_date: {"price": 7787.85, "change_pct": -5.01},
        }

        result = collect_market_state_request_bundle(
            "2026-07-12",
            request_registry=request_registry,
            index_cross_validator=lambda data, target_date: self.fail(
                "旧日期不应启动指数交叉核对"
            ),
            require_index_cross_validation=False,
            timer=timer,
            emit=emitted.append,
        )

        self.assertNotIn("index_cross_validation", result["results"])
        self.assertNotIn("指数交叉核对", result["data_status"])
        self.assertNotIn("指数交叉核对", result["step_status"])
        self.assertFalse(any("交叉核对六个指数" in line for line in emitted))
        self.assertFalse(
            any(log["step"] == "request.index_cross_validation" for log in result["module_logs"])
        )

    def test_load_csi1000_from_same_day_run_log_requires_successful_target_date_log(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_dir = root / "logs" / "runs"
            runs_dir.mkdir(parents=True)
            (runs_dir / "20260609-010000__2026-06-08.log").write_text(
                "日报关键数据检查: 成功 / 2026-06-08\n   ✅ 中证1000: 8081.26点 (-3.11%) [⏱ 0.68s]\n",
                encoding="utf-8",
            )
            (runs_dir / "20260609-020000__2026-06-09.log").write_text(
                "日报关键数据检查: 失败 / 2026-06-09\n   ✅ 中证1000: 1.00点 (+0.01%) [⏱ 0.68s]\n",
                encoding="utf-8",
            )
            (runs_dir / "20260609-030000__2026-06-09.log").write_text(
                "日报关键数据检查: 成功 / 2026-06-09\n   ✅ 中证1000: 8318.70点 (+2.94%) [⏱ 0.62s]\n",
                encoding="utf-8",
            )

            fake_file = root / "scripts" / "domains" / "market_state" / "request.py"
            with patch("domains.market_state.request.__file__", str(fake_file)):
                payload = _load_csi1000_from_same_day_run_log("2026-06-09")

        self.assertEqual(payload["price"], 8318.7)
        self.assertEqual(payload["change_pct"], 2.94)
        self.assertEqual(payload["trade_date"], "2026-06-09")
        self.assertEqual(payload["data_source"], "run_log.csi1000_same_day_success")


if __name__ == "__main__":
    unittest.main()
