import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from risk.risk_bundle_runtime import build_risk_bundle_contract


class RiskBundleRuntimeTest(unittest.TestCase):
    def test_risk_bundle_contract_groups_candidates_by_risk_level(self):
        result = build_risk_bundle_contract(
            data={
                "zt_pool": [
                    {"代码": "000001", "最新价": 10, "成交额": 5, "开盘价": 10, "最高价": 10.5, "最低价": 9.8, "封单额": 200000000, "换手率": 8, "炸板次数": 0},
                    {"代码": "000002", "最新价": 8, "成交额": 20, "开盘价": 8.1, "最高价": 8.5, "最低价": 7.5, "封单额": 10000000, "换手率": 35, "炸板次数": 3, "最后封板时间": "14:45"},
                ],
                "zt_pool_by_sector": {"军工": [{"代码": "000001"}], "机器人": [{"代码": "000002"}]},
                "dt_pool_by_sector": {"机器人": [{"name": "机器人二号"}] * 3},
                "sector_fund_flow": {"outflow": [{"name": "机器人", "zdf": -5.2}]},
            },
            target_date="2026-04-22",
            mainline_name="军工",
            core_stocks=[{"name": "军工一号", "code": "000001", "sector": "军工", "pattern": "普通涨停", "change": 9.9, "连板数": 1}],
            secondary_stocks=[{"name": "机器人二号", "code": "000002", "sector": "机器人", "pattern": "一字板", "change": 3.0, "连板数": 3}],
            gem_observation_stocks=[],
            zt_pool_by_sector={"军工": [{"代码": "000001"}], "机器人": [{"代码": "000002"}]},
            dt_pool_by_sector={"机器人": [{"name": "机器人二号"}] * 3},
            persist_a_kill=False,
            normalize_stock_code=lambda code: str(code or "").replace(".SZ", ""),
            safe_float=lambda value, default=0.0: default if value in (None, "") else float(value),
            clamp=lambda value, low, high: max(low, min(high, value)),
            get_abnormal_follow_risk_signal=lambda stock: (
                {"light": "🟢 绿灯", "delta": -12, "reason": "承接强", "forecast": "等60分钟确认"}
                if stock.get("code") == "000001"
                else {"light": "🔴 红灯", "delta": 22, "reason": "承接弱", "forecast": "可能低开"}
            ),
            format_risk_reason=lambda risk_penalties=None, repair_buffers=None, risk_level="": f"{risk_level}:{','.join(risk_penalties or [])}",
            update_a_kill_blacklist=lambda target_date, stocks, sector_name="": [{"sector": sector_name, "count": len(stocks)}],
        )

        self.assertEqual(result["focus_group"][0]["code"], "000001")
        self.assertEqual(result["delete_group"][0]["code"], "000002")
        self.assertTrue(result["mainline_a_kill"] is False or isinstance(result["mainline_a_kill"], bool))
        self.assertEqual(result["abnormal_green_count"], 1)
        self.assertEqual(result["abnormal_red_count"], 1)
        self.assertTrue(any(log["step"] == "risk_scoring" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
