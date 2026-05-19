import sys
import unittest
from urllib.parse import parse_qs, urlparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DataCollectorShimTest(unittest.TestCase):
    def test_local_data_collector_shim_imports_for_entry_runtime(self):
        try:
            module = __import__("data_collector", fromlist=["data_collector"])
        except ModuleNotFoundError as error:
            self.fail(f"data_collector shim should exist for entry runtime: {error}")

        self.assertTrue(hasattr(module, "AShareDataCollector"))
        collector = module.AShareDataCollector()
        self.assertTrue(hasattr(collector, "get_wanzhu_top10"))

    def test_wanzhu_top10_fetches_direct_hunanwanzhu_rows_when_legacy_missing(self):
        module = __import__("data_collector", fromlist=["data_collector"])
        module._load_legacy_collector_class = lambda: None
        calls = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return (
                    '{"errno":0,"code":0,"data":{"list":[{"count":70,'
                    '"stock_desc":"电力-算电协同","stock_name":"大唐发电",'
                    '"stock_code":"601991","yes_count":80,"total_fund":"123.45"}]}}'
                ).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            calls.append(request.full_url)
            return _Response()

        module.urlopen = fake_urlopen
        collector = module.AShareDataCollector()

        rows = collector.get_wanzhu_top10("2026-05-18")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["name"], "大唐发电")
        self.assertEqual(rows[0]["code"], "601991")
        self.assertEqual(rows[0]["holder_count"], 70)
        self.assertEqual(rows[0]["source_date"], "2026-05-18")
        self.assertEqual(rows[0]["query_date"], "2026-05-18")
        query = parse_qs(urlparse(calls[0]).query)
        self.assertEqual(query["stock_date"], ["2026-05-18"])
        self.assertEqual(query["page_size"], ["20"])
        self.assertEqual(query["fund_rank"], ["0"])

    def test_wanzhu_top10_falls_back_to_recent_published_date(self):
        module = __import__("data_collector", fromlist=["data_collector"])
        module._load_legacy_collector_class = lambda: None
        payloads = [
            b'{"code":1000,"message":"u\\u00272026-05-19\\u0027 is not in list","data":{}}',
            (
                '{"errno":0,"code":0,"data":{"list":[{"count":70,'
                '"stock_desc":"电力-算电协同","stock_name":"大唐发电",'
                '"stock_code":"601991","yes_count":80,"total_fund":"123.45"}]}}'
            ).encode("utf-8"),
        ]
        calls = []

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return self._payload

        def fake_urlopen(request, timeout=0):
            calls.append(request.full_url)
            return _Response(payloads.pop(0))

        module.urlopen = fake_urlopen
        collector = module.AShareDataCollector()

        rows = collector.get_wanzhu_top10("2026-05-19")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["query_date"], "2026-05-19")
        self.assertEqual(rows[0]["source_date"], "2026-05-18")
        queried_dates = [parse_qs(urlparse(url).query)["stock_date"][0] for url in calls]
        self.assertEqual(queried_dates, ["2026-05-19", "2026-05-18"])


if __name__ == "__main__":
    unittest.main()
