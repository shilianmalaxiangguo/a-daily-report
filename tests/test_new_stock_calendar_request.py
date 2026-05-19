import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.new_stock_calendar.request import (
    collect_new_stock_calendar_request_bundle,
    fetch_sina_new_stock_calendar_pages,
    parse_sina_new_stock_calendar_html,
)


SINA_HTML = """
<html><body>
<table>
<tr><td><div align="center">301608</div></td>
<td><div align="center">301608</div></td>
<td><div align="center"><a>理奇智能</a></div></td>
<td><div align="center">2026-04-22</div></td>
<td><div align="center">2026-04-30</div></td>
<td><div align="right">1472</div></td>
<td><div align="right">1472</div></td>
<td><div align="right">20.00</div></td>
<td><div align="right">18.20</div></td>
<td><div align="right">1.45</div></td>
<td><div align="right">2.944</div></td>
<td><div align="right">0.01</div></td>
<td><div align="center">查看</div></td>
<td><div align="center">预测</div></td>
<td><div align="center">公告</div></td>
</tr>
<tr><td><div align="center">001365</div></td>
<td><div align="center">001365</div></td>
<td><div align="center"><a>天海电子</a></div></td>
<td><div align="center">2026-05-07</div></td>
<td><div align="center">&nbsp;</div></td>
<td><div align="right">7900</div></td>
<td><div align="right">1896</div></td>
<td><div align="right">27.19</div></td>
<td><div align="right">23.40</div></td>
<td><div align="right">1.85</div></td>
<td><div align="right">21.480</div></td>
<td><div align="right">0.00</div></td>
<td><div align="center">查看</div></td>
<td><div align="center">预测</div></td>
<td><div align="center">公告</div></td>
</tr>
</table>
</body></html>
"""


class _TimerStub:
    def __init__(self):
        self.records = []

    def record(self, label, order):
        self.records.append((label, order))
        return 0.01, None


class _ResponseStub:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class _OpenerStub:
    def __init__(self, body):
        self.body = body
        self.urls = []

    def open(self, url, timeout=10):
        self.urls.append((url, timeout))
        return _ResponseStub(self.body)


class NewStockCalendarRequestTest(unittest.TestCase):
    def test_parse_sina_calendar_uses_listing_date_not_net_issue_date(self):
        rows = parse_sina_new_stock_calendar_html(
            SINA_HTML,
            target_date="2026-04-29",
            source_url="fixture://sina",
        )

        self.assertEqual(len(rows), 1)
        item = rows[0]
        self.assertEqual(item["code"], "301608")
        self.assertEqual(item["name"], "理奇智能")
        self.assertEqual(item["net_issue_date"], "2026-04-22")
        self.assertEqual(item["listing_date"], "2026-04-30")
        self.assertEqual(item["listing_window"], "tomorrow_listing")
        self.assertEqual(item["pre_listing_action"], "focus_tomorrow_battle")
        self.assertEqual(item["days_to_listing"], 1)
        self.assertEqual(item["days_since_listing"], -1)
        self.assertEqual(item["market"], "sz")
        self.assertEqual(item["issue_amount_10k"], 1472.0)
        self.assertEqual(item["online_issue_amount_10k"], 1472.0)
        self.assertEqual(item["issue_price"], 20.0)
        self.assertEqual(item["pe_ratio"], 18.2)
        self.assertEqual(item["fundraising_yi"], 2.944)
        self.assertEqual(item["source"], "sina_new_stock_calendar")
        self.assertEqual(item["source_url"], "fixture://sina")
        self.assertEqual(item["source_status"], "success")

    def test_parse_sina_calendar_marks_t2_prepare_cash_window(self):
        rows = parse_sina_new_stock_calendar_html(SINA_HTML, target_date="2026-04-28")

        self.assertEqual(rows[0]["listing_window"], "pre_alert_t2")
        self.assertEqual(rows[0]["pre_listing_action"], "prepare_clear_cash")
        self.assertEqual(rows[0]["days_to_listing"], 2)

    def test_fetch_sina_calendar_pages_decodes_gb18030(self):
        opener = _OpenerStub(SINA_HTML.encode("gb18030"))

        pages = fetch_sina_new_stock_calendar_pages(page_count=1, opener=opener)

        self.assertEqual(len(pages), 1)
        self.assertIn("理奇智能", pages[0]["html"])
        self.assertEqual(pages[0]["page"], 1)
        self.assertIn("/page/1.phtml", pages[0]["source_url"])
        self.assertEqual(opener.urls[0][1], 10)

    def test_collect_request_bundle_builds_success_payload(self):
        timer = _TimerStub()
        emitted = []

        result = collect_new_stock_calendar_request_bundle(
            "2026-04-29",
            fetch_pages=lambda page_count=2: [{"html": SINA_HTML, "source_url": "fixture://sina"}],
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["new_stock_calendar"][0]["code"], "301608")
        self.assertTrue(result["data_status"]["新股上市日历"])
        self.assertTrue(result["step_status"]["新股上市日历获取"])
        self.assertEqual(timer.records[0], ("新股上市日历获取", 11))
        self.assertTrue(any(log["status"] == "success" for log in result["module_logs"]))

    def test_collect_request_bundle_uses_tushare_registry_before_sina_pages(self):
        timer = _TimerStub()
        emitted = []
        legacy_calls = []
        registry_calls = []

        result = collect_new_stock_calendar_request_bundle(
            "2026-05-13",
            fetch_pages=lambda page_count=2: legacy_calls.append(page_count) or [],
            request_registry={
                "new_stock_calendar": lambda *, target_date: registry_calls.append(target_date)
                or [{"code": "001237", "name": "惠康科技", "listing_date": "2026-05-13", "source": "tushare.new_share"}],
            },
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(registry_calls, ["2026-05-13"])
        self.assertEqual(legacy_calls, [])
        self.assertEqual(result["results"]["new_stock_calendar"][0]["source"], "tushare.new_share")
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.new_stock_calendar"], "tushare.new_share")

    def test_collect_request_bundle_is_degraded_when_fetch_fails(self):
        timer = _TimerStub()

        def fail_fetch(page_count=2):
            raise RuntimeError("network down")

        result = collect_new_stock_calendar_request_bundle(
            "2026-04-29",
            fetch_pages=fail_fetch,
            timer=timer,
            emit=lambda message: None,
        )

        self.assertEqual(result["results"]["new_stock_calendar"], [])
        self.assertFalse(result["data_status"]["新股上市日历"])
        self.assertFalse(result["step_status"]["新股上市日历获取"])
        self.assertEqual(timer.records[0], ("新股上市日历获取(失败)", 11))
        self.assertTrue(any(log["status"] == "error" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
