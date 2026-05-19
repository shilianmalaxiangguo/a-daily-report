import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnostics.helper_diagnostics_runtime import clear_helper_logs, drain_helper_logs


def _run_legacy_entry_probe(script_body):
    stub_setup = """
import sys
import types

def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module

sys.path.insert(0, {scripts_path!r})
sys.modules.update(
    {{
        "data_collector": _stub_module("data_collector", AShareDataCollector=type("AShareDataCollector", (), {{}})),
        "ths_hot_stock": _stub_module(
            "ths_hot_stock",
            fetch_ths_hot_stock=lambda *args, **kwargs: [],
            fetch_hot_stock_with_fallback=lambda *args, **kwargs: [],
        ),
        "ths_hot_list": _stub_module("ths_hot_list", fetch_hot_plate=lambda *args, **kwargs: []),
        "tencent_finance_data": _stub_module("tencent_finance_data", TencentFinanceData=type("TencentFinanceData", (), {{}})),
        "xuangubao_intraday": _stub_module(
            "xuangubao_intraday",
            XuangubaoIntradayAnalyzer=type("XuangubaoIntradayAnalyzer", (), {{}}),
        ),
        "limit_up_down_pool": _stub_module(
            "limit_up_down_pool",
            get_limit_up_pool=lambda *args, **kwargs: ([], set()),
            get_limit_down_pool=lambda *args, **kwargs: ([], set()),
            mark_limit_status=lambda *args, **kwargs: {{}},
        ),
        "strong_stock_pool": _stub_module(
            "strong_stock_pool",
            get_strong_stock_pool=lambda *args, **kwargs: [],
            analyze_strong_stocks_by_sector=lambda *args, **kwargs: {{}},
        ),
        "data_validator": _stub_module("data_validator", DataValidator=type("DataValidator", (), {{}})),
        "quantitative_analyzer": _stub_module(
            "quantitative_analyzer",
            VolumeAnomalyDetector=type("VolumeAnomalyDetector", (), {{}}),
            LHBAnalyzer=type("LHBAnalyzer", (), {{}}),
            ResonanceAnalyzer=type("ResonanceAnalyzer", (), {{}}),
            SignalGenerator=type("SignalGenerator", (), {{}}),
            analyze_volume_anomaly=lambda *args, **kwargs: {{}},
            analyze_lhb=lambda *args, **kwargs: {{}},
            calculate_resonance=lambda *args, **kwargs: {{}},
            generate_trade_signals=lambda *args, **kwargs: {{}},
        ),
        "hot_list_integrated": _stub_module(
            "hot_list_integrated",
            get_integrated_hot_list=lambda *args, **kwargs: {{}},
            analyze_sector_distribution=lambda *args, **kwargs: {{}},
        ),
        "history_cache": _stub_module(
            "history_cache",
            get_cache=lambda *args, **kwargs: {{}},
            HistoryCache=type("HistoryCache", (), {{}}),
        ),
        "llm_service": _stub_module("llm_service", get_llm_service=lambda *args, **kwargs: None),
    }}
)
""".format(scripts_path=str(ROOT / "scripts"))

    return subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class MarketActivitySupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("domains.market_activity.support", fromlist=["support"])
        except ModuleNotFoundError as error:
            self.fail(f"domains.market_activity.support should exist: {error}")

    def test_legacy_market_activity_wrappers_delegate_to_support(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_get_stock_status", return_value="+10.00% 涨停(首板)") as status_mock, \
     patch.object(daily_report_entry_demo, "run_get_stock_sector", return_value="军工") as sector_mock:
    status = daily_report_entry_demo.get_stock_status("军工一号", "000001", [{"代码": "000001", "涨停统计": "首板"}], [], 10.0)
    sector = daily_report_entry_demo.get_stock_sector(
        "军工一号",
        "000001",
        hot_rank_data=[{"code": "000001", "concepts": ["机器人"]}],
        zt_pool_raw=[{"代码": "000001", "所属行业": "军工"}],
        xuangubao_data={"xuangubao_limit_up_reasons": []},
    )

assert status_mock.call_args[0] == ("军工一号", "000001", [{"代码": "000001", "涨停统计": "首板"}], [], 10.0)
assert sector_mock.call_args[0] == ("军工一号", "000001")
assert sector_mock.call_args.kwargs["hot_rank_data"] == [{"code": "000001", "concepts": ["机器人"]}]
assert sector_mock.call_args.kwargs["zt_pool_raw"] == [{"代码": "000001", "所属行业": "军工"}]
assert sector_mock.call_args.kwargs["xuangubao_data"] == {"xuangubao_limit_up_reasons": []}
assert status == "+10.00% 涨停(首板)"
assert sector == "军工"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_market_activity_support_preserves_status_and_sector_priority(self):
        support = self._load_module()

        status = support.get_stock_status(
            "军工一号",
            "000001",
            [{"代码": "000001", "名称": "军工一号", "涨停统计": "首板"}],
            [],
            10.0,
        )
        sector_from_raw = support.get_stock_sector(
            "军工一号",
            "000001",
            hot_rank_data=[{"code": "000001", "name": "军工一号", "concepts": ["机器人", "AI"]}],
            zt_pool_raw=[{"代码": "000001", "名称": "军工一号", "所属行业": "军工"}],
            skip_api_call=True,
        )
        sector_from_hot_rank = support.get_stock_sector(
            "机器人一号",
            "000002",
            hot_rank_data=[{"code": "000002", "name": "机器人一号", "concepts": ["机器人", "AI"]}],
            skip_api_call=True,
        )

        self.assertEqual(status, "+10.00% 涨停(首板)")
        self.assertEqual(sector_from_raw, "军工")
        self.assertEqual(sector_from_hot_rank, "机器人")

    def test_market_activity_support_ignores_market_board_labels_when_resolving_sector(self):
        support = self._load_module()

        sector = support.get_stock_sector(
            "巨力索具",
            "002342",
            hot_rank_data=[
                {"code": "002342", "name": "巨力索具", "concepts": ["商业航天", "军工"]},
            ],
            zt_pool_raw=[
                {"代码": "002342", "名称": "巨力索具", "所属行业": "HS"},
            ],
            skip_api_call=True,
        )
        gem_sector = support.get_stock_sector(
            "大普微",
            "301666",
            hot_rank_data=[
                {"code": "301666", "name": "大普微", "concepts": ["存储芯片"]},
            ],
            zt_pool_raw=[
                {"代码": "301666", "名称": "大普微", "所属行业": "GEM"},
            ],
            skip_api_call=True,
        )

        self.assertEqual(sector, "商业航天")
        self.assertEqual(gem_sector, "存储芯片")

    def test_market_activity_support_resolves_sector_from_xuangubao_context(self):
        support = self._load_module()

        limit_up_sector = support.get_stock_sector(
            "华工科技",
            "000988",
            xuangubao_data={
                "xuangubao_limit_up_reasons": [
                    {"symbol": "000988.SZ", "name": "华工科技", "related_plates": [{"plate_name": "光通信"}]},
                ],
            },
            lhb_data=[{"code": "000988", "name": "华工科技", "sector": "HS"}],
            skip_api_call=True,
        )
        news_sector = support.get_stock_sector(
            "科士达",
            "002518",
            xuangubao_data={
                "xuangubao_news": [
                    {
                        "title": "算力方向异动",
                        "stocks": [{"symbol": "002518.SZ", "name": "科士达"}],
                        "plates": [{"name": "算力"}],
                    }
                ],
            },
            lhb_data=[{"code": "002518", "name": "科士达", "sector": "未知"}],
            skip_api_call=True,
        )

        self.assertEqual(limit_up_sector, "光通信")
        self.assertEqual(news_sector, "算力")

    def test_market_activity_support_emits_warning_when_eastmoney_lookup_fails(self):
        support = self._load_module()
        support._stock_industry_cache.clear()
        support._eastmoney_warning_emitted = False
        clear_helper_logs()

        captured = StringIO()
        with patch("requests.get", side_effect=RuntimeError("eastmoney timeout")):
            with redirect_stdout(captured):
                sector = support.get_stock_sector("军工一号", "000001", skip_api_call=False)

        helper_logs = drain_helper_logs()
        self.assertEqual(sector, "未知")
        self.assertIn("Eastmoney行业接口失败", captured.getvalue())
        self.assertEqual(len(helper_logs), 1)
        self.assertEqual(helper_logs[0]["step"], "helper.stock_sector.eastmoney")
        self.assertEqual(helper_logs[0]["details"]["provider"], "eastmoney.company_survey")


if __name__ == "__main__":
    unittest.main()
