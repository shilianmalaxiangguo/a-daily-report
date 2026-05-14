from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "cloudflare_free_daily.db"
SCHEMA_VERSION_TURNOVER_SERIES = "cf-free-turnover-series/v1"

__all__ = [
    "CloudflareFreeDailyDb",
    "DEFAULT_DB_PATH",
    "SCHEMA_VERSION_TURNOVER_SERIES",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return int(default)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _text(value):
    return str(value or "").strip()


def _utc_now_text():
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class CloudflareFreeDailyDb:
    """SQLite implementation of the first D1-shaped daily fact repository."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_source_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    endpoint TEXT NOT NULL DEFAULT '',
                    params_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT '',
                    row_count INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT '',
                    raw_r2_key TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_daily_quotes_recent (
                    trade_date TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    stock_code TEXT NOT NULL DEFAULT '',
                    market TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL DEFAULT '',
                    open REAL NOT NULL DEFAULT 0,
                    high REAL NOT NULL DEFAULT 0,
                    low REAL NOT NULL DEFAULT 0,
                    close REAL NOT NULL DEFAULT 0,
                    pct_chg REAL NOT NULL DEFAULT 0,
                    vol REAL NOT NULL DEFAULT 0,
                    amount_yi REAL NOT NULL DEFAULT 0,
                    source_run_id INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (trade_date, ts_code)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_daily_totals (
                    trade_date TEXT NOT NULL,
                    market_scope TEXT NOT NULL,
                    total_amount_yi REAL NOT NULL DEFAULT 0,
                    stock_count INTEGER NOT NULL DEFAULT 0,
                    source_policy TEXT NOT NULL DEFAULT '',
                    source_run_id INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (trade_date, market_scope)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turnover_rank_daily (
                    trade_date TEXT NOT NULL,
                    rank_scope TEXT NOT NULL,
                    rank_no INTEGER NOT NULL,
                    ts_code TEXT NOT NULL,
                    stock_code TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL DEFAULT '',
                    amount_yi REAL NOT NULL DEFAULT 0,
                    total_amount_yi REAL NOT NULL DEFAULT 0,
                    amount_share_pct REAL NOT NULL DEFAULT 0,
                    source_run_id INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (trade_date, rank_scope, rank_no)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turnover_share_series (
                    series_key TEXT PRIMARY KEY,
                    end_date TEXT NOT NULL DEFAULT '',
                    window_days INTEGER NOT NULL DEFAULT 0,
                    rank_limit INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    generated_at TEXT NOT NULL DEFAULT '',
                    source_run_ids_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS report_artifacts (
                    trade_date TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    visibility TEXT NOT NULL DEFAULT '',
                    r2_key TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL DEFAULT '',
                    schema_version TEXT NOT NULL DEFAULT '',
                    source_run_id INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (trade_date, variant, r2_key)
                )
                """
            )
            conn.commit()

    def save_provider_source_run(self, run):
        run = run or {}
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO provider_source_runs(
                    trade_date, provider, endpoint, params_json, status, row_count,
                    duration_ms, error_message, raw_r2_key, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _text(run.get("trade_date")),
                    _text(run.get("provider")),
                    _text(run.get("endpoint")),
                    json.dumps(run.get("params") or run.get("params_json") or {}, ensure_ascii=False, sort_keys=True),
                    _text(run.get("status")),
                    _safe_int(run.get("row_count")),
                    _safe_int(run.get("duration_ms")),
                    _text(run.get("error_message")),
                    _text(run.get("raw_r2_key")),
                    _text(run.get("created_at")) or _utc_now_text(),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def upsert_stock_daily_quotes_recent(self, rows, *, source_run_id=0):
        normalized_rows = []
        for row in rows or []:
            trade_date = _text((row or {}).get("trade_date"))
            ts_code = _text((row or {}).get("ts_code")).upper()
            amount_yi = _safe_float((row or {}).get("amount_yi"))
            if not trade_date or not ts_code or amount_yi <= 0:
                continue
            normalized_rows.append(
                (
                    trade_date,
                    ts_code,
                    _text((row or {}).get("stock_code")),
                    _text((row or {}).get("market")).upper(),
                    _text((row or {}).get("name")),
                    _safe_float((row or {}).get("open")),
                    _safe_float((row or {}).get("high")),
                    _safe_float((row or {}).get("low")),
                    _safe_float((row or {}).get("close")),
                    _safe_float((row or {}).get("pct_chg")),
                    _safe_float((row or {}).get("vol")),
                    amount_yi,
                    int(source_run_id or (row or {}).get("source_run_id") or 0),
                )
            )
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO stock_daily_quotes_recent(
                    trade_date, ts_code, stock_code, market, name, open, high, low,
                    close, pct_chg, vol, amount_yi, source_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date, ts_code) DO UPDATE SET
                    stock_code=excluded.stock_code,
                    market=excluded.market,
                    name=excluded.name,
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    pct_chg=excluded.pct_chg,
                    vol=excluded.vol,
                    amount_yi=excluded.amount_yi,
                    source_run_id=excluded.source_run_id
                """,
                normalized_rows,
            )
            conn.commit()
        return len(normalized_rows)

    def rebuild_market_daily_total(self, trade_date, *, market_scope="all_a", source_run_id=0):
        trade_date = _text(trade_date)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount_yi), 0) AS total_amount_yi, COUNT(*) AS stock_count
                FROM stock_daily_quotes_recent
                WHERE trade_date = ?
                """,
                (trade_date,),
            ).fetchone()
            total = {
                "trade_date": trade_date,
                "market_scope": market_scope,
                "total_amount_yi": _safe_float(row["total_amount_yi"] if row else 0),
                "stock_count": _safe_int(row["stock_count"] if row else 0),
                "source_policy": "stock_sum",
                "source_run_id": int(source_run_id or 0),
            }
            conn.execute(
                """
                INSERT INTO market_daily_totals(
                    trade_date, market_scope, total_amount_yi, stock_count, source_policy, source_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date, market_scope) DO UPDATE SET
                    total_amount_yi=excluded.total_amount_yi,
                    stock_count=excluded.stock_count,
                    source_policy=excluded.source_policy,
                    source_run_id=excluded.source_run_id
                """,
                (
                    total["trade_date"],
                    total["market_scope"],
                    total["total_amount_yi"],
                    total["stock_count"],
                    total["source_policy"],
                    total["source_run_id"],
                ),
            )
            conn.commit()
        return total

    def query_market_daily_total(self, trade_date, *, market_scope="all_a"):
        trade_date = _text(trade_date)
        market_scope = _text(market_scope) or "all_a"
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT trade_date, market_scope, total_amount_yi, stock_count,
                       source_policy, source_run_id
                FROM market_daily_totals
                WHERE trade_date = ? AND market_scope = ?
                """,
                (trade_date, market_scope),
            ).fetchone()
        return dict(row) if row else {}

    def rebuild_turnover_rank_daily(self, trade_date, *, rank_scope="all_a", rank_limit=100, source_run_id=0):
        trade_date = _text(trade_date)
        rank_limit = max(_safe_int(rank_limit, 100), 1)
        with self._connect() as conn:
            total_row = conn.execute(
                """
                SELECT total_amount_yi
                FROM market_daily_totals
                WHERE trade_date = ? AND market_scope = ?
                """,
                (trade_date, rank_scope),
            ).fetchone()
            total_amount = _safe_float(total_row["total_amount_yi"] if total_row else 0)
            quote_rows = conn.execute(
                """
                SELECT trade_date, ts_code, stock_code, name, amount_yi
                FROM stock_daily_quotes_recent
                WHERE trade_date = ?
                ORDER BY amount_yi DESC, ts_code ASC
                LIMIT ?
                """,
                (trade_date, rank_limit),
            ).fetchall()
            conn.execute(
                "DELETE FROM turnover_rank_daily WHERE trade_date = ? AND rank_scope = ?",
                (trade_date, rank_scope),
            )
            ranks = []
            for index, row in enumerate(quote_rows, start=1):
                amount_yi = _safe_float(row["amount_yi"])
                share = (amount_yi / total_amount * 100.0) if total_amount > 0 else 0.0
                item = {
                    "trade_date": row["trade_date"],
                    "rank_scope": rank_scope,
                    "rank_no": index,
                    "ts_code": row["ts_code"],
                    "stock_code": row["stock_code"],
                    "name": row["name"],
                    "amount_yi": amount_yi,
                    "total_amount_yi": total_amount,
                    "amount_share_pct": share,
                    "source_run_id": int(source_run_id or 0),
                }
                ranks.append(item)
            conn.executemany(
                """
                INSERT INTO turnover_rank_daily(
                    trade_date, rank_scope, rank_no, ts_code, stock_code, name,
                    amount_yi, total_amount_yi, amount_share_pct, source_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["trade_date"],
                        item["rank_scope"],
                        item["rank_no"],
                        item["ts_code"],
                        item["stock_code"],
                        item["name"],
                        item["amount_yi"],
                        item["total_amount_yi"],
                        item["amount_share_pct"],
                        item["source_run_id"],
                    )
                    for item in ranks
                ],
            )
            conn.commit()
        return ranks

    def query_top_turnover_share_series(self, end_date, *, window_days=30, limit=50, rank_scope="all_a"):
        end_date = _text(end_date)
        window_days = max(_safe_int(window_days, 30), 1)
        limit = max(_safe_int(limit, 50), 1)
        with self._connect() as conn:
            date_rows = conn.execute(
                """
                SELECT DISTINCT trade_date
                FROM turnover_rank_daily
                WHERE trade_date <= ? AND rank_scope = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (end_date, rank_scope, window_days),
            ).fetchall()
            dates = [row["trade_date"] for row in reversed(date_rows)]
            rows = []
            source_run_ids = set()
            for trade_date in dates:
                top_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(amount_yi), 0) AS top_amount_yi,
                           COALESCE(MAX(total_amount_yi), 0) AS market_amount_yi
                    FROM turnover_rank_daily
                    WHERE trade_date = ? AND rank_scope = ? AND rank_no <= ?
                    """,
                    (trade_date, rank_scope, limit),
                ).fetchone()
                source_rows = conn.execute(
                    """
                    SELECT DISTINCT source_run_id
                    FROM turnover_rank_daily
                    WHERE trade_date = ? AND rank_scope = ? AND rank_no <= ?
                    """,
                    (trade_date, rank_scope, limit),
                ).fetchall()
                for source_row in source_rows:
                    source_run_id = _safe_int(source_row["source_run_id"])
                    if source_run_id > 0:
                        source_run_ids.add(source_run_id)
                top_amount = _safe_float(top_row["top_amount_yi"] if top_row else 0)
                market_amount = _safe_float(top_row["market_amount_yi"] if top_row else 0)
                rows.append(
                    {
                        "trade_date": trade_date,
                        "top_amount_yi": top_amount,
                        "market_amount_yi": market_amount,
                        "share_pct": (top_amount / market_amount * 100.0) if market_amount > 0 else 0.0,
                    }
                )
        return {
            "schema_version": SCHEMA_VERSION_TURNOVER_SERIES,
            "generated_at": _utc_now_text(),
            "query_window": {
                "end_date": end_date,
                "window_days": window_days,
                "rank_limit": limit,
                "rank_scope": rank_scope,
            },
            "source_run_ids": sorted(source_run_ids),
            "rows": rows,
        }

    def query_turnover_rank_rows(self, trade_date, *, limit=50, rank_scope="all_a"):
        trade_date = _text(trade_date)
        limit = max(_safe_int(limit, 50), 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.trade_date, r.rank_scope, r.rank_no, r.ts_code, r.stock_code,
                       COALESCE(NULLIF(r.name, ''), q.name) AS name,
                       r.amount_yi, r.total_amount_yi, r.amount_share_pct, r.source_run_id,
                       q.close, q.pct_chg
                FROM turnover_rank_daily r
                LEFT JOIN stock_daily_quotes_recent q
                  ON q.trade_date = r.trade_date AND q.ts_code = r.ts_code
                WHERE r.trade_date = ? AND r.rank_scope = ? AND r.rank_no <= ?
                ORDER BY r.rank_no ASC
                """,
                (trade_date, rank_scope, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_turnover_share_series(self, payload):
        payload = payload or {}
        query_window = payload.get("query_window") or {}
        end_date = _text(query_window.get("end_date"))
        window_days = _safe_int(query_window.get("window_days"))
        rank_limit = _safe_int(query_window.get("rank_limit"))
        rank_scope = _text(query_window.get("rank_scope")) or "all_a"
        series_key = f"top{rank_limit}:{rank_scope}:{end_date}:{window_days}"
        source_run_ids = payload.get("source_run_ids") or []
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO turnover_share_series(
                    series_key, end_date, window_days, rank_limit, payload_json,
                    generated_at, source_run_ids_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(series_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    generated_at=excluded.generated_at,
                    source_run_ids_json=excluded.source_run_ids_json
                """,
                (
                    series_key,
                    end_date,
                    window_days,
                    rank_limit,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    _text(payload.get("generated_at")) or _utc_now_text(),
                    json.dumps(source_run_ids, ensure_ascii=False),
                ),
            )
            conn.commit()
        return series_key

    def save_report_artifact(self, artifact):
        artifact = artifact or {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO report_artifacts(
                    trade_date, variant, visibility, r2_key, content_hash,
                    schema_version, source_run_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date, variant, r2_key) DO UPDATE SET
                    visibility=excluded.visibility,
                    content_hash=excluded.content_hash,
                    schema_version=excluded.schema_version,
                    source_run_id=excluded.source_run_id,
                    created_at=excluded.created_at
                """,
                (
                    _text(artifact.get("trade_date")),
                    _text(artifact.get("variant")),
                    _text(artifact.get("visibility")),
                    _text(artifact.get("r2_key")),
                    _text(artifact.get("content_hash")),
                    _text(artifact.get("schema_version")),
                    _safe_int(artifact.get("source_run_id")),
                    _text(artifact.get("created_at")) or _utc_now_text(),
                ),
            )
            conn.commit()

    def get_report_artifacts(self):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trade_date, variant, visibility, r2_key, content_hash,
                       schema_version, source_run_id, created_at
                FROM report_artifacts
                ORDER BY trade_date, variant, r2_key
                """
            ).fetchall()
        return [dict(row) for row in rows]
