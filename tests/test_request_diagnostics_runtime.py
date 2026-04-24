import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from input.request_diagnostics_runtime import (
    build_request_diagnostics,
    render_request_diagnostics_lines,
)


class RequestDiagnosticsRuntimeTest(unittest.TestCase):
    def test_build_request_diagnostics_groups_errors_degraded_and_fallbacks(self):
        diagnostics = build_request_diagnostics(
            module_logs=[
                {
                    "module": "domains.market_activity.request",
                    "step": "request.hot_rank.primary",
                    "status": "error",
                    "message": "同花顺热榜失败",
                    "details": {
                        "provider": "ths_hot_stock",
                        "target_keys": ["hot_rank_top30"],
                        "error": "ReadTimeout",
                    },
                },
                {
                    "module": "domains.market_activity.request",
                    "step": "request.hot_rank.fallback",
                    "status": "success",
                    "message": "腾讯热榜兜底成功",
                    "details": {
                        "provider": "tencent.get_hot_stocks",
                        "target_keys": ["hot_rank_top30"],
                        "fallback_used": True,
                        "upstream_error": "ReadTimeout",
                    },
                },
                {
                    "module": "domains.market_state.request",
                    "step": "request.major_indices",
                    "status": "degraded",
                    "message": "主要指数为空或无效",
                    "details": {
                        "provider": "iwencai.major_indices",
                        "target_keys": ["indices"],
                    },
                },
            ],
            data_status={"热度前三十个股": True, "主要指数": False},
            step_status={"热度前三十个股获取": True, "主要指数获取": False},
        )

        self.assertEqual(diagnostics["summary"]["request_log_count"], 3)
        self.assertEqual(diagnostics["summary"]["error_count"], 1)
        self.assertEqual(diagnostics["summary"]["degraded_count"], 1)
        self.assertEqual(diagnostics["summary"]["fallback_count"], 1)
        self.assertEqual(diagnostics["failures"][0]["provider"], "ths_hot_stock")
        self.assertEqual(diagnostics["degraded"][0]["target_keys"], ["indices"])
        self.assertEqual(diagnostics["fallbacks"][0]["provider"], "tencent.get_hot_stocks")

    def test_render_request_diagnostics_lines_renders_readable_summary(self):
        diagnostics = build_request_diagnostics(
            module_logs=[
                {
                    "module": "domains.market_activity.request",
                    "step": "request.pool_snapshot",
                    "status": "error",
                    "message": "涨停跌停池请求失败",
                    "details": {
                        "provider": "akshare.limit_up_down",
                        "target_keys": ["zt_pool", "dt_pool", "market_stats"],
                        "error": "ConnectTimeout",
                    },
                }
            ],
            data_status={"涨停池": False},
            step_status={"涨停跌停数据获取": False},
        )

        rendered = "\n".join(render_request_diagnostics_lines(diagnostics))
        self.assertIn("请求体检摘要", rendered)
        self.assertIn("akshare.limit_up_down", rendered)
        self.assertIn("zt_pool, dt_pool, market_stats", rendered)
        self.assertIn("ConnectTimeout", rendered)


if __name__ == "__main__":
    unittest.main()
