import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from input.index_cross_validation import (
    REPORT_INDEX_SPECS,
    build_report_index_cross_validation,
    fetch_tencent_index_daily_fact,
    index_cross_validation_failures,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _report_data(target_date="2026-07-13"):
    values = {
        "上证指数": ("000001", 3913.7940, 3996.1616, -2.0612),
        "深证成指": ("399001", 14522.8547, 15046.6695, -3.4813),
        "创业板指": ("399006", 3723.5166, 3842.7314, -3.1023),
        "中证全指": ("000985", 6001.6528, 6215.1138, -3.4345),
        "中证500": ("000905", 8138.1443, 8503.9705, -4.3018),
        "中证1000": ("000852", 7787.8529, 8198.3078, -5.0066),
    }

    def payload(name):
        code, close, pre_close, change_pct = values[name]
        return {
            "name": name,
            "code": code,
            "trade_date": target_date,
            "price": close,
            "close": close,
            "pre_close": pre_close,
            "change_pct": change_pct,
            "涨跌幅": change_pct,
            "data_source": "tushare.index_daily",
        }

    return {
        "target_date": target_date,
        "indices": {
            "上证指数": payload("上证指数"),
            "深证成指": payload("深证成指"),
            "创业板指": payload("创业板指"),
        },
        "wind_a_alternative": payload("中证全指"),
        "csi500_index": payload("中证500"),
        "csi1000_index": payload("中证1000"),
    }


def _verification_facts(data):
    facts = {}
    for spec in REPORT_INDEX_SPECS:
        if spec["container_key"] == "indices":
            primary = data["indices"][spec["name"]]
        else:
            primary = data[spec["container_key"]]
        facts[spec["tencent_symbol"]] = {
            "provider": "tencent.fqkline.day",
            "trade_date": primary["trade_date"],
            "close": round(primary["close"], 3),
            "pre_close": round(primary["pre_close"], 3),
            "change_pct": round(primary["change_pct"], 2),
        }
    return facts


class IndexCrossValidationTest(unittest.TestCase):
    def test_fetch_tencent_index_daily_fact_uses_exact_day_and_previous_close(self):
        payload = {
            "code": 0,
            "data": {
                "sh000001": {
                    "day": [
                        ["2026-07-10", "4031.540", "3996.160", "4074.830", "3995.810", "627450065.000"],
                        ["2026-07-13", "3966.020", "3913.790", "3983.050", "3900.670", "590907356.000"],
                    ]
                }
            },
        }

        fact = fetch_tencent_index_daily_fact(
            "sh000001",
            "2026-07-13",
            urlopen_fn=lambda request, timeout=0: _Response(payload),
        )

        self.assertEqual(fact["trade_date"], "2026-07-13")
        self.assertEqual(fact["close"], 3913.79)
        self.assertEqual(fact["pre_close"], 3996.16)
        self.assertAlmostEqual(fact["change_pct"], -2.0612, places=3)
        self.assertEqual(fact["provider"], "tencent.fqkline.day")

    def test_build_cross_validation_accepts_six_matching_exact_date_indices(self):
        data = _report_data()
        verification = _verification_facts(data)

        result = build_report_index_cross_validation(
            data,
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )
        data["index_cross_validation"] = result

        self.assertEqual(result["schema_version"], "report_index_cross_validation.v1")
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["checks"]), 6)
        self.assertEqual(result["failures"], [])
        self.assertEqual(index_cross_validation_failures(data, "2026-07-13"), [])

    def test_build_cross_validation_rejects_stale_date_and_value_conflict(self):
        data = _report_data()
        verification = _verification_facts(data)
        verification["sh000001"]["trade_date"] = "2026-07-10"
        verification["sh000905"]["close"] += 1.0

        result = build_report_index_cross_validation(
            data,
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )

        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("上证指数" in item and "日期" in item for item in result["failures"]))
        self.assertTrue(any("中证500" in item and "收盘" in item for item in result["failures"]))

    def test_saved_evidence_cannot_validate_payload_changed_after_check(self):
        data = _report_data()
        verification = _verification_facts(data)
        data["index_cross_validation"] = build_report_index_cross_validation(
            data,
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )
        data["indices"]["上证指数"]["close"] = 3996.1616
        data["indices"]["上证指数"]["price"] = 3996.1616

        failures = index_cross_validation_failures(data, "2026-07-13")

        self.assertTrue(any("上证指数" in item and "核对后发生变化" in item for item in failures))

    def test_saved_success_status_cannot_hide_source_value_conflict(self):
        data = _report_data()
        verification = _verification_facts(data)
        data["index_cross_validation"] = build_report_index_cross_validation(
            data,
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )
        data["index_cross_validation"]["checks"][0]["verification"]["close"] += 1.0

        failures = index_cross_validation_failures(data, "2026-07-13")

        self.assertTrue(any("上证指数" in item and "收盘差异" in item for item in failures))

    def test_saved_success_evidence_rejects_internal_contradictions(self):
        data = _report_data()
        verification = _verification_facts(data)
        data["index_cross_validation"] = build_report_index_cross_validation(
            data,
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )

        cases = {
            "重复指数": lambda artifact: artifact["checks"].append(copy.deepcopy(artifact["checks"][0])),
            "错误代码": lambda artifact: artifact["checks"][0].__setitem__("code", "999999"),
            "遗留失败原因": lambda artifact: artifact["failures"].append("旧失败原因"),
            "明细失败原因": lambda artifact: artifact["checks"][0].__setitem__("reason", "旧失败原因"),
            "错误差异记录": lambda artifact: artifact["checks"][0].__setitem__("close_diff", 99.0),
        }

        for label, mutate in cases.items():
            with self.subTest(label=label):
                changed = copy.deepcopy(data)
                mutate(changed["index_cross_validation"])
                self.assertTrue(index_cross_validation_failures(changed, "2026-07-13"))

    def test_cross_validation_rejects_same_provider_on_both_sides(self):
        data = _report_data()
        data["indices"]["上证指数"]["data_source"] = "tencent.fqkline.day"
        verification = _verification_facts(data)

        result = build_report_index_cross_validation(
            data,
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )

        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("上证指数" in item and "独立来源" in item for item in result["failures"]))

    def test_cross_validation_rejects_non_finite_values(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                data = _report_data()
                data["indices"]["上证指数"]["change_pct"] = value
                data["indices"]["上证指数"]["涨跌幅"] = value
                verification = _verification_facts(_report_data())

                result = build_report_index_cross_validation(
                    data,
                    "2026-07-13",
                    fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
                )
                data["index_cross_validation"] = result

                self.assertEqual(result["status"], "failed")
                self.assertTrue(any("上证指数" in item and "涨跌幅缺失" in item for item in result["failures"]))
                self.assertTrue(index_cross_validation_failures(data, "2026-07-13"))

    def test_cross_validation_rejects_missing_or_wrong_source_identity(self):
        data = _report_data()
        data["indices"]["上证指数"].pop("data_source")
        verification = _verification_facts(_report_data())

        result = build_report_index_cross_validation(
            data,
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )

        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("上证指数" in item and "主来源标识缺失" in item for item in result["failures"]))

        verification["sh000001"]["provider"] = "eastmoney.index.daily"
        result = build_report_index_cross_validation(
            _report_data(),
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )

        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("上证指数" in item and "核对来源不是腾讯日K" in item for item in result["failures"]))

    def test_saved_evidence_rejects_payload_identity_changes(self):
        data = _report_data()
        verification = _verification_facts(data)
        data["index_cross_validation"] = build_report_index_cross_validation(
            data,
            "2026-07-13",
            fetch_verification_fact_fn=lambda symbol, target_date: dict(verification[symbol]),
        )

        cases = {
            "代码变化": lambda changed: changed["indices"]["上证指数"].__setitem__("code", "999999"),
            "来源变化": lambda changed: changed["indices"]["上证指数"].__setitem__(
                "data_source", "eastmoney.index.daily"
            ),
            "核对来源变化": lambda changed: changed["index_cross_validation"]["checks"][0][
                "verification"
            ].__setitem__("provider", "eastmoney.index.daily"),
        }

        for label, mutate in cases.items():
            with self.subTest(label=label):
                changed = copy.deepcopy(data)
                mutate(changed)
                failures = index_cross_validation_failures(changed, "2026-07-13")
                self.assertTrue(failures)
                self.assertTrue(any("上证指数" in item for item in failures))

    def test_missing_evidence_fails_for_contract_start_date(self):
        failures = index_cross_validation_failures(_report_data(), "2026-07-13")

        self.assertTrue(any("核对证据缺失" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
