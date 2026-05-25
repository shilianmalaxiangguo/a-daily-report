import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class XueqiuHotStockServiceTest(unittest.TestCase):
    def test_builds_a_share_24h_hot_stock_url_with_type_22(self):
        from market_data.xueqiu_hot_stock_service import build_xueqiu_hot_stock_url

        url = build_xueqiu_hot_stock_url(page=2, size=50)

        self.assertIn("/v5/stock/hot_stock/list.json", url)
        self.assertIn("detail=1", url)
        self.assertIn("include=1", url)
        self.assertIn("page=2", url)
        self.assertIn("size=50", url)
        self.assertIn("type=22", url)
        self.assertNotIn("type=10", url)

    def test_normalizes_xueqiu_hot_stock_rows_and_marks_provider(self):
        from market_data.xueqiu_hot_stock_service import normalize_xueqiu_hot_stock_payload

        payload = {
            "data": {
                "items": [
                    {
                        "symbol": "SZ300476",
                        "name": "胜宏科技",
                        "current": 88.8,
                        "percent": 12.34,
                        "chg": 9.76,
                    },
                    {
                        "quote": {
                            "symbol": "SH600519",
                            "name": "贵州茅台",
                            "current": 1666.0,
                            "percent": -0.52,
                        }
                    },
                ]
            }
        }

        rows = normalize_xueqiu_hot_stock_payload(payload)

        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["code"], "300476")
        self.assertEqual(rows[0]["full_code"], "SZ300476")
        self.assertEqual(rows[0]["name"], "胜宏科技")
        self.assertEqual(rows[0]["change_pct"], 12.34)
        self.assertEqual(rows[0]["provider"], "xueqiu.hot_stock.type22")
        self.assertEqual(rows[1]["rank"], 2)
        self.assertEqual(rows[1]["code"], "600519")
        self.assertEqual(rows[1]["full_code"], "SH600519")

    def test_builds_xueqiu_hot_stock_argument_url_for_symbols(self):
        from market_data.xueqiu_hot_stock_service import build_xueqiu_hot_stock_argument_url

        url = build_xueqiu_hot_stock_argument_url(["SZ300476", "SH600584"])

        self.assertIn("https://api.xueqiu.com/rainbow/ai/question/generate/hot_stock_argument.json", url)
        self.assertIn("symbols=SZ300476%2CSH600584", url)
        self.assertNotIn("type=10", url)

    def test_normalizes_xueqiu_hot_stock_argument_payload_as_reason_candidates(self):
        from market_data.xueqiu_hot_stock_service import normalize_xueqiu_hot_stock_argument_payload

        payload = {
            "code": 200,
            "data": {
                "SZ300476": {
                    "question": "胜宏科技成Rubin平台核心PCB供应商，请详细分析",
                    "content": "胜宏科技成Rubin平台核心PCB供应商",
                    "url": "https://ai.xueqiu.com/ai/seekball/chat?shareId=s-eb55180f",
                    "score": 8,
                    "record_id": "hs_1f275776",
                    "share_id": "s-eb55180f",
                    "pc_display": False,
                },
                "SH600584": {
                    "question": "长电科技成为英伟达Rubin平台核心封装供应商，请详细分析",
                    "content": "长电科技成为英伟达Rubin平台核心封装供应商",
                    "score": "9",
                    "pc_display": True,
                },
            },
        }

        rows = normalize_xueqiu_hot_stock_argument_payload(payload)

        self.assertEqual(rows[0]["code"], "300476")
        self.assertEqual(rows[0]["full_code"], "SZ300476")
        self.assertEqual(rows[0]["argument"], "胜宏科技成Rubin平台核心PCB供应商")
        self.assertEqual(rows[0]["question"], "胜宏科技成Rubin平台核心PCB供应商，请详细分析")
        self.assertEqual(rows[0]["score"], 8)
        self.assertEqual(rows[0]["provider"], "xueqiu.hot_stock.argument")
        self.assertEqual(rows[0]["source_role"], "雪球AI炒作理由候选")
        self.assertEqual(rows[0]["url"], "https://ai.xueqiu.com/ai/seekball/chat?shareId=s-eb55180f")
        self.assertEqual(rows[0]["share_id"], "s-eb55180f")
        self.assertEqual(rows[0]["record_id"], "hs_1f275776")
        self.assertFalse(rows[0]["pc_display"])
        self.assertEqual(rows[1]["score"], 9)

    def test_fetches_xueqiu_hot_stock_arguments_with_cookie_headers(self):
        from market_data.xueqiu_hot_stock_service import fetch_xueqiu_hot_stock_arguments

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return (
                    b'{"code":200,"data":{"SZ000725":{"content":"glass substrate story",'
                    b'"question":"glass substrate story detail","score":9}}}'
                )

        def fake_opener(request, timeout):
            captured["url"] = request.full_url
            captured["cookie"] = request.headers.get("Cookie")
            captured["timeout"] = timeout
            return FakeResponse()

        rows = fetch_xueqiu_hot_stock_arguments(["SZ000725"], cookie="xq_a_token=abc", timeout=3, opener=fake_opener)

        self.assertIn("hot_stock_argument.json", captured["url"])
        self.assertIn("symbols=SZ000725", captured["url"])
        self.assertEqual(captured["cookie"], "xq_a_token=abc")
        self.assertEqual(captured["timeout"], 3)
        self.assertEqual(rows[0]["full_code"], "SZ000725")
        self.assertEqual(rows[0]["argument"], "glass substrate story")

    def test_fetches_xueqiu_hot_rank_reads_cookie_from_local_env_file(self):
        from market_data import xueqiu_hot_stock_service as service

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"data":{"items":[{"symbol":"SZ300476","name":"\\u80dc\\u5b8f\\u79d1\\u6280"}]}}'

        def fake_opener(request, timeout):
            captured["cookie"] = request.headers.get("Cookie")
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("XUEQIU_COOKIE=xq_a_token=from-dotenv\n", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True), patch.object(service.Path, "cwd", return_value=Path(tmpdir)):
                rows = service.fetch_xueqiu_a_share_hot_24h(opener=fake_opener)

        self.assertEqual(captured["cookie"], "xq_a_token=from-dotenv")
        self.assertEqual(rows[0]["full_code"], "SZ300476")

    def test_get_xueqiu_cookie_can_read_cookie_from_capture_dir_env(self):
        from market_data import xueqiu_hot_stock_service as service

        with tempfile.TemporaryDirectory() as tmpdir:
            capture_dir = Path(tmpdir)
            (capture_dir / "request_header_raw.txt").write_text(
                ":authority: api.xueqiu.com\ncookie: xq_a_token=from-capture;u=1\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"XUEQIU_COOKIE_CAPTURE_DIR": str(capture_dir)}, clear=True):
                self.assertEqual(service.get_xueqiu_cookie(), "xq_a_token=from-capture;u=1")

    def test_try_fetch_xueqiu_arguments_stops_report_when_cookie_expired(self):
        from urllib.error import HTTPError
        from market_data.xueqiu_hot_stock_service import try_fetch_xueqiu_hot_stock_arguments

        def fake_opener(_request, timeout):
            raise HTTPError(
                url="https://api.xueqiu.com/rainbow/ai/question/generate/hot_stock_argument.json",
                code=400,
                msg="Bad Request",
                hdrs={},
                fp=_BytesReader(b'{"error_code":"400016","error_description":"login again"}'),
            )

        result = try_fetch_xueqiu_hot_stock_arguments(["SZ300476"], cookie="expired", opener=fake_opener)

        self.assertEqual(result["rows"], [])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["provider"], "xueqiu.hot_stock.argument")
        self.assertIn("雪球登录态失效", result["diagnostic_note"])
        self.assertIn("关键数据不完整，停止生成", result["diagnostic_note"])
        self.assertFalse(result["can_continue_report"])

    def test_try_fetch_xueqiu_hot_rank_stops_report_when_cookie_expired(self):
        from urllib.error import HTTPError
        from market_data.xueqiu_hot_stock_service import try_fetch_xueqiu_a_share_hot_24h

        def fake_opener(_request, timeout):
            raise HTTPError(
                url="https://stock.xueqiu.com/v5/stock/hot_stock/list.json",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=_BytesReader(b'{"error_code":"400016","error_description":"login again"}'),
            )

        result = try_fetch_xueqiu_a_share_hot_24h(cookie="expired", opener=fake_opener)

        self.assertEqual(result["rows"], [])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["provider"], "xueqiu.hot_stock.type22")
        self.assertIn("关键数据不完整，停止生成", result["diagnostic_note"])
        self.assertFalse(result["can_continue_report"])

    def test_try_fetch_xueqiu_hot_rank_stops_report_when_rows_empty(self):
        from market_data.xueqiu_hot_stock_service import try_fetch_xueqiu_a_share_hot_24h

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"data":{"items":[]}}'

        def fake_opener(_request, timeout):
            return FakeResponse()

        result = try_fetch_xueqiu_a_share_hot_24h(cookie="xq_a_token=valid", opener=fake_opener)

        self.assertEqual(result["rows"], [])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["provider"], "xueqiu.hot_stock.type22")
        self.assertIn("雪球接口返回空", result["diagnostic_note"])
        self.assertIn("关键数据不完整，停止生成", result["diagnostic_note"])
        self.assertFalse(result["can_continue_report"])

    def test_try_fetch_xueqiu_arguments_stops_report_when_rows_empty(self):
        from market_data.xueqiu_hot_stock_service import try_fetch_xueqiu_hot_stock_arguments

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"code":200,"data":{}}'

        def fake_opener(_request, timeout):
            return FakeResponse()

        result = try_fetch_xueqiu_hot_stock_arguments(["SZ300476"], cookie="xq_a_token=valid", opener=fake_opener)

        self.assertEqual(result["rows"], [])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["provider"], "xueqiu.hot_stock.argument")
        self.assertIn("雪球接口返回空", result["diagnostic_note"])
        self.assertIn("关键数据不完整，停止生成", result["diagnostic_note"])
        self.assertFalse(result["can_continue_report"])


class _BytesReader:
    def __init__(self, payload):
        self._payload = BytesIO(payload)

    def read(self, *_args):
        return self._payload.read(*_args)

    def close(self):
        self._payload.close()


if __name__ == "__main__":
    unittest.main()
