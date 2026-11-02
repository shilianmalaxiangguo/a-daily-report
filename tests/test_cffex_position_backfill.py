import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cffex_position_backfill import archive_raw_files, run_backfill, verify_backfill  # noqa: E402
from market_data.cffex_index_futures import (  # noqa: E402
    CFFEX_CONTRACT_MULTIPLIERS,
    CFFEX_PRODUCTS,
    CFFEX_SOURCE_POLICY,
    content_sha256,
)
from market_data.cffex_index_futures import CffexSourceError, fetch_cffex_bytes  # noqa: E402


class _Service:
    def __init__(self):
        self.replaced = []
        self.indices = []

    def is_postgres_backed(self):
        return True

    def upsert_index_daily_bars(self, index_code, rows, **kwargs):
        self.indices.append((index_code, rows, kwargs))
        return len(rows)

    def replace_cffex_index_futures_day(self, trade_date, contracts, ranks, **kwargs):
        self.replaced.append((trade_date, contracts, ranks, kwargs))
        return {
            "replaced_products": list(CFFEX_PRODUCTS),
            "unchanged_products": [],
            "contract_row_count": len(contracts),
            "member_rank_row_count": len(ranks),
        }


class CffexPositionBackfillTest(unittest.TestCase):
    def test_fetch_cffex_bytes_maps_only_known_official_error_page_to_not_found(self):
        official_error = (
            b'<!DOCTYPE html><html><head><meta http-equiv="Content-Type" '
            b'content="text/html; charset=gb2312" /></head>'
            b'<body background="images/404_bg.gif"></body></html>'
        )

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return official_error

        with self.assertRaises(CffexSourceError) as context:
            fetch_cffex_bytes("http://example.test/weekend.xml", opener=lambda *args, **kwargs: _Response())

        self.assertEqual(context.exception.status_code, 404)

    def test_fetch_cffex_bytes_retries_transient_read_failure(self):
        calls = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"<positionRank></positionRank>"

        def opener(*_args, **_kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise TimeoutError("temporary timeout")
            return _Response()

        raw = fetch_cffex_bytes(
            "http://example.test/IF.xml",
            opener=opener,
            retry_delay_seconds=0,
        )

        self.assertEqual(raw, b"<positionRank></positionRank>")
        self.assertEqual(len(calls), 2)

    def test_archive_raw_files_writes_hash_verified_manifest(self):
        raw = b"<positionRank></positionRank>"
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = archive_raw_files(
                temp_dir,
                "2026-08-19",
                [
                    {
                        "kind": "member_rank",
                        "product_code": "IF",
                        "source_url": "http://example.test/IF.xml",
                        "content_hash": content_sha256(raw),
                        "raw_bytes": raw,
                    }
                ],
            )

            self.assertEqual(len(paths), 2)
            day_dir = Path(temp_dir) / "2026-08-19"
            self.assertEqual((day_dir / "IF.xml").read_bytes(), raw)
            manifest = (day_dir / "manifest.json").read_text(encoding="utf-8")
            self.assertIn(content_sha256(raw), manifest)
            self.assertIn("http://example.test/IF.xml", manifest)

    def test_archive_raw_files_rejects_duplicate_filename(self):
        raw = b"<positionRank></positionRank>"
        item = {
            "kind": "member_rank",
            "product_code": "IF",
            "source_url": "http://example.test/IF.xml",
            "content_hash": content_sha256(raw),
            "raw_bytes": raw,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(Exception, "文件名重复"):
                archive_raw_files(temp_dir, "2026-08-19", [item, dict(item)])

    def test_run_backfill_skips_only_official_404_and_writes_complete_day(self):
        service = _Service()

        def collect_fn(trade_date, **kwargs):
            if trade_date == "2026-08-16":
                return {
                    "availability": "unavailable",
                    "source_errors": [{"kind": "contract_daily", "status_code": 404}],
                    "raw_files": [],
                }
            contracts = [_contract(product) for product in CFFEX_PRODUCTS]
            ranks = [
                row
                for product in CFFEX_PRODUCTS
                for row in _rank_rows(product)
            ]
            raw_files = []
            for product in CFFEX_PRODUCTS:
                raw = product.encode("ascii")
                raw_files.append(
                    {
                        "kind": "member_rank",
                        "product_code": product,
                        "source_url": f"http://example.test/{product}.xml",
                        "content_hash": content_sha256(raw),
                        "raw_bytes": raw,
                    }
                )
            index_raw = b"index"
            raw_files.append(
                {
                    "kind": "contract_daily",
                    "product_code": "",
                    "source_url": "http://example.test/index.xml",
                    "content_hash": content_sha256(index_raw),
                    "raw_bytes": index_raw,
                }
            )
            return {
                "availability": "complete",
                "source_errors": [],
                "contract_rows": contracts,
                "member_rank_rows": ranks,
                "raw_files": raw_files,
            }

        def fetch_spot_fn(index_code, start, end, **kwargs):
            return [{"trade_date": "2026-08-17", "close": 100}]

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_backfill(
                "2026-08-16",
                "2026-08-17",
                raw_root=temp_dir,
                database_service=service,
                collect_fn=collect_fn,
                fetch_spot_fn=fetch_spot_fn,
                query_date="2026-08-19",
            )

        self.assertEqual(result["skipped_non_trading_dates"], ["2026-08-16"])
        self.assertEqual(result["processed_trade_dates"], ["2026-08-17"])
        self.assertEqual(len(service.replaced), 1)
        self.assertEqual(len(service.indices), 4)
        self.assertEqual(result["raw_files_saved"], 6)

    def test_run_backfill_rejects_partial_trading_day_before_database_write(self):
        service = _Service()

        def collect_fn(trade_date, **kwargs):
            return {
                "availability": "partial",
                "source_errors": [{"reason": "IM持仓排名缺失"}],
                "contract_rows": [],
                "member_rank_rows": [],
                "raw_files": [],
            }

        def fetch_spot_fn(index_code, start, end, **kwargs):
            return [{"trade_date": start, "close": 100}]

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(RuntimeError, "IM持仓排名缺失"):
                run_backfill(
                    "2026-08-19",
                    "2026-08-19",
                    raw_root=temp_dir,
                    database_service=service,
                    collect_fn=collect_fn,
                    fetch_spot_fn=fetch_spot_fn,
                    query_date="2026-08-19",
                )

        self.assertEqual(service.replaced, [])
        self.assertEqual(service.indices, [])

    def test_run_backfill_keeps_prior_success_when_later_day_fails(self):
        service = _Service()

        def collect_fn(trade_date, **kwargs):
            if trade_date == "2026-08-18":
                return {
                    "availability": "partial",
                    "source_errors": [{"reason": "目标日排名文件缺失"}],
                    "contract_rows": [],
                    "member_rank_rows": [],
                    "raw_files": [],
                }
            return _complete_collected_day(trade_date)

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(RuntimeError, "目标日排名文件缺失"):
                run_backfill(
                    "2026-08-17",
                    "2026-08-18",
                    raw_root=temp_dir,
                    database_service=service,
                    collect_fn=collect_fn,
                    fetch_spot_fn=lambda *_args, **_kwargs: [],
                    query_date="2026-08-19",
                )

        self.assertEqual([item[0] for item in service.replaced], ["2026-08-17"])

    def test_verify_backfill_rejects_product_with_no_rank_rows(self):
        day = _complete_collected_day("2026-08-17")
        day["member_rank_rows"] = [
            row for row in day["member_rank_rows"] if row["product_code"] != "IM"
        ]
        service = _VerifyService(day)

        with self.assertRaisesRegex(RuntimeError, "IM目标日会员排名缺失"):
            verify_backfill(
                service,
                "2026-08-17",
                "2026-08-17",
                expected_trade_dates=["2026-08-17"],
            )

    def test_verify_backfill_rejects_shifted_rank_numbers(self):
        day = _complete_collected_day("2026-08-17")
        for row in day["member_rank_rows"]:
            if row["product_code"] == "IF" and row["rank_type"] == "long":
                row["rank_no"] += 1
        service = _VerifyService(day)

        with self.assertRaisesRegex(RuntimeError, "排名不是1-20连续名次"):
            verify_backfill(
                service,
                "2026-08-17",
                "2026-08-17",
                expected_trade_dates=["2026-08-17"],
            )

    def test_verify_backfill_rejects_inconsistent_product_content_hash(self):
        day = _complete_collected_day("2026-08-17")
        day["member_rank_rows"][0]["content_hash"] = "f" * 64
        service = _VerifyService(day)

        with self.assertRaisesRegex(RuntimeError, "IF会员排名来源地址、哈希或规则不一致"):
            verify_backfill(
                service,
                "2026-08-17",
                "2026-08-17",
                expected_trade_dates=["2026-08-17"],
            )


def _contract(product):
    return {
        "trade_date": "2026-08-17",
        "source_date": "2026-08-17",
        "query_date": "2026-08-19",
        "product_code": product,
        "contract_code": f"{product}2608",
        "close_price": 100.0,
        "settlement_price": 100.0,
        "previous_settlement_price": 99.0,
        "volume": 1000,
        "open_interest": 1100,
        "previous_open_interest": 1000,
        "contract_multiplier": CFFEX_CONTRACT_MULTIPLIERS[product],
        "source_url": "http://example.test/index.xml",
        "content_hash": "a" * 64,
        "source_policy": CFFEX_SOURCE_POLICY,
    }


def _rank_rows(product):
    rows = []
    for rank_type in ("volume", "long", "short"):
        for rank_no in range(1, 21):
            rows.append(
                {
                    "trade_date": "2026-08-17",
                    "source_date": "2026-08-17",
                    "query_date": "2026-08-19",
                    "product_code": product,
                    "contract_code": f"{product}2608",
                    "rank_type": rank_type,
                    "rank_no": rank_no,
                    "member_id": f"{rank_no:04d}",
                    "member_name": (
                        "中信期货(代客)" if rank_no == 1 else f"会员{rank_no}"
                    ),
                    "quantity": 1000 - rank_no,
                    "daily_change": None if rank_type == "volume" else rank_no,
                    "source_url": f"http://example.test/{product}.xml",
                    "content_hash": ({"IF": "b", "IH": "c", "IC": "d", "IM": "e"}[product] * 64),
                    "source_policy": CFFEX_SOURCE_POLICY,
                }
            )
    return rows


def _complete_collected_day(trade_date):
    contracts = [_contract(product) for product in CFFEX_PRODUCTS]
    ranks = [row for product in CFFEX_PRODUCTS for row in _rank_rows(product)]
    for row in [*contracts, *ranks]:
        row["trade_date"] = trade_date
        row["source_date"] = trade_date
    raw_files = []
    for product in CFFEX_PRODUCTS:
        raw = product.encode("ascii")
        raw_files.append(
            {
                "kind": "member_rank",
                "product_code": product,
                "source_url": f"http://example.test/{product}.xml",
                "content_hash": content_sha256(raw),
                "raw_bytes": raw,
            }
        )
    raw_files.append(
        {
            "kind": "contract_daily",
            "product_code": "",
            "source_url": "http://example.test/index.xml",
            "content_hash": content_sha256(b"index"),
            "raw_bytes": b"index",
        }
    )
    return {
        "availability": "complete",
        "source_errors": [],
        "contract_rows": contracts,
        "member_rank_rows": ranks,
        "raw_files": raw_files,
    }


class _VerifyService:
    def __init__(self, day):
        self.day = day

    def query_cffex_index_futures_history(self, _end, *, window_days=60):
        return {
            "trade_dates": ["2026-08-17"],
            "contract_rows": self.day["contract_rows"],
            "member_rank_rows": self.day["member_rank_rows"],
        }

    def query_index_daily_bars(self, *_args, **_kwargs):
        return [{"date": "2026-08-17", "close": 100.0}]


if __name__ == "__main__":
    unittest.main()
