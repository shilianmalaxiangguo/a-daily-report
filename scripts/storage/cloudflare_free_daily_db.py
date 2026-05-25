from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from contextlib import contextmanager
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


def _price_band_spread_pct(high_pct, low_pct):
    return _safe_float(high_pct) - _safe_float(low_pct)


def _price_band_style_label(spread_pct):
    spread_pct = _safe_float(spread_pct)
    if spread_pct > 2.0:
        return "高潮"
    if spread_pct < -2.0:
        return "冰点"
    return "震荡"


def _text(value):
    return str(value or "").strip()


def _utc_now_text():
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


class CloudflareFreeDailyDb:
    """SQLite implementation of the first D1-shaped daily fact repository."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

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
                CREATE INDEX IF NOT EXISTS idx_stock_daily_quotes_recent_trade_code
                ON stock_daily_quotes_recent(trade_date, stock_code)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_stock_daily_quotes_recent_code_date_high
                ON stock_daily_quotes_recent(stock_code, trade_date, high)
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
                CREATE TABLE IF NOT EXISTS mainline_daily (
                    trade_date TEXT PRIMARY KEY,
                    primary_mainline TEXT NOT NULL DEFAULT '',
                    daily_attack_line TEXT NOT NULL DEFAULT '',
                    secondary_mainline TEXT NOT NULL DEFAULT '',
                    competition_mainline TEXT NOT NULL DEFAULT '',
                    rotation_label TEXT NOT NULL DEFAULT '',
                    leading_line TEXT NOT NULL DEFAULT '',
                    state_code TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0,
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    rotation_summary TEXT NOT NULL DEFAULT '',
                    source_policy TEXT NOT NULL DEFAULT '',
                    source_run_id INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mainline_turnover_daily (
                    trade_date TEXT NOT NULL,
                    primary_mainline TEXT NOT NULL,
                    turnover_scope_key TEXT NOT NULL DEFAULT '',
                    turnover_scope_label TEXT NOT NULL DEFAULT '',
                    sector_turnover_yi REAL NOT NULL DEFAULT 0,
                    total_turnover_yi REAL NOT NULL DEFAULT 0,
                    turnover_share_pct REAL NOT NULL DEFAULT 0,
                    matched_sector_names_json TEXT NOT NULL DEFAULT '[]',
                    matched_sector_codes_json TEXT NOT NULL DEFAULT '[]',
                    source_policy TEXT NOT NULL DEFAULT '',
                    source_run_id INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (trade_date, primary_mainline, turnover_scope_key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sector_fund_flow_daily (
                    trade_date TEXT,
                    sector_name TEXT,
                    net_inflow_yi REAL,
                    source_policy TEXT,
                    source_run_id INTEGER,
                    updated_at TEXT,
                    PRIMARY KEY (trade_date, sector_name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS new_high_feedback_daily (
                    trade_date TEXT PRIMARY KEY,
                    new_high_count INTEGER NOT NULL DEFAULT 0,
                    all_a_share_pct REAL NOT NULL DEFAULT 0,
                    leading_sectors TEXT NOT NULL DEFAULT '',
                    sector_distribution_json TEXT NOT NULL DEFAULT '[]',
                    top_stocks_json TEXT NOT NULL DEFAULT '[]',
                    source_policy TEXT NOT NULL DEFAULT '',
                    source_run_id INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS price_band_style_daily (
                    trade_date TEXT PRIMARY KEY,
                    high_price_code TEXT NOT NULL DEFAULT '',
                    low_price_code TEXT NOT NULL DEFAULT '',
                    high_price_pct REAL NOT NULL DEFAULT 0,
                    low_price_pct REAL NOT NULL DEFAULT 0,
                    spread_pct REAL NOT NULL DEFAULT 0,
                    style_label TEXT NOT NULL DEFAULT '',
                    source_policy TEXT NOT NULL DEFAULT '',
                    source_run_id INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS margin_pressure_daily (
                    trade_date TEXT PRIMARY KEY,
                    margin_balance_yi REAL NOT NULL DEFAULT 0,
                    short_selling_balance_yi REAL NOT NULL DEFAULT 0,
                    margin_trading_balance_yi REAL NOT NULL DEFAULT 0,
                    market_turnover_yi REAL NOT NULL DEFAULT 0,
                    margin_turnover_ratio_pct REAL NOT NULL DEFAULT 0,
                    pressure_diff_pct REAL NOT NULL DEFAULT 0,
                    exchange_count INTEGER NOT NULL DEFAULT 0,
                    stock_count INTEGER NOT NULL DEFAULT 0,
                    source_policy TEXT NOT NULL DEFAULT '',
                    source_run_id INTEGER NOT NULL DEFAULT 0
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extreme_conviction_mentions (
                    record_id TEXT PRIMARY KEY,
                    mention_trade_date TEXT NOT NULL,
                    stock_code TEXT NOT NULL DEFAULT '',
                    stock_name TEXT NOT NULL DEFAULT '',
                    rank_no INTEGER NOT NULL DEFAULT 0,
                    sector_candidate TEXT NOT NULL DEFAULT '',
                    buy_window TEXT NOT NULL DEFAULT '',
                    planned_window TEXT NOT NULL DEFAULT '',
                    review_status TEXT NOT NULL DEFAULT '',
                    next_action TEXT NOT NULL DEFAULT '',
                    invalidation TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    source_section TEXT NOT NULL DEFAULT '',
                    is_a_kill_eliminated INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS monthly_account_ledger (
                    trade_date TEXT NOT NULL,
                    account_id TEXT NOT NULL DEFAULT 'main',
                    month_key TEXT NOT NULL DEFAULT '',
                    month_return_pct REAL,
                    equity REAL,
                    cash REAL,
                    position_market_value REAL,
                    realized_pnl REAL,
                    unrealized_pnl REAL,
                    max_drawdown_pct REAL,
                    planned_trade_count INTEGER NOT NULL DEFAULT 0,
                    unplanned_trade_count INTEGER NOT NULL DEFAULT 0,
                    note TEXT NOT NULL DEFAULT '',
                    source_policy TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (trade_date, account_id)
                )
                """
            )
            conn.commit()

    def _normalize_month_key(self, trade_date="", month_key=""):
        month_key = _text(month_key)
        if month_key:
            return month_key
        trade_date = _text(trade_date)
        if len(trade_date) >= 7 and trade_date[4] == "-":
            return trade_date[:7]
        if len(trade_date) >= 6 and trade_date[:6].isdigit():
            return f"{trade_date[:4]}-{trade_date[4:6]}"
        return ""

    def _nullable_float(self, value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _normalize_monthly_account_ledger(self, row):
        row = row or {}
        trade_date = _text(row.get("trade_date") or row.get("date"))
        account_id = _text(row.get("account_id")) or "main"
        month_key = self._normalize_month_key(trade_date=trade_date, month_key=row.get("month_key"))
        return {
            "trade_date": trade_date,
            "account_id": account_id,
            "month_key": month_key,
            "month_return_pct": self._nullable_float(row.get("month_return_pct", row.get("monthly_return_pct"))),
            "equity": self._nullable_float(row.get("equity")),
            "cash": self._nullable_float(row.get("cash")),
            "position_market_value": self._nullable_float(row.get("position_market_value")),
            "realized_pnl": self._nullable_float(row.get("realized_pnl")),
            "unrealized_pnl": self._nullable_float(row.get("unrealized_pnl")),
            "max_drawdown_pct": self._nullable_float(row.get("max_drawdown_pct")),
            "planned_trade_count": _safe_int(row.get("planned_trade_count")),
            "unplanned_trade_count": _safe_int(row.get("unplanned_trade_count")),
            "note": _text(row.get("note")),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "payload_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
            "updated_at": _utc_now_text(),
        }

    def upsert_monthly_account_ledger(self, row):
        item = self._normalize_monthly_account_ledger(row)
        if not item["trade_date"] or not item["account_id"] or not item["month_key"]:
            return {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO monthly_account_ledger(
                    trade_date, account_id, month_key, month_return_pct, equity, cash,
                    position_market_value, realized_pnl, unrealized_pnl, max_drawdown_pct,
                    planned_trade_count, unplanned_trade_count, note, source_policy,
                    payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date, account_id) DO UPDATE SET
                    month_key=excluded.month_key,
                    month_return_pct=excluded.month_return_pct,
                    equity=excluded.equity,
                    cash=excluded.cash,
                    position_market_value=excluded.position_market_value,
                    realized_pnl=excluded.realized_pnl,
                    unrealized_pnl=excluded.unrealized_pnl,
                    max_drawdown_pct=excluded.max_drawdown_pct,
                    planned_trade_count=excluded.planned_trade_count,
                    unplanned_trade_count=excluded.unplanned_trade_count,
                    note=excluded.note,
                    source_policy=excluded.source_policy,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    item["trade_date"],
                    item["account_id"],
                    item["month_key"],
                    item["month_return_pct"],
                    item["equity"],
                    item["cash"],
                    item["position_market_value"],
                    item["realized_pnl"],
                    item["unrealized_pnl"],
                    item["max_drawdown_pct"],
                    item["planned_trade_count"],
                    item["unplanned_trade_count"],
                    item["note"],
                    item["source_policy"],
                    item["payload_json"],
                    item["updated_at"],
                ),
            )
            conn.commit()
        return item

    def query_monthly_account_ledger(self, end_date, *, account_id="main"):
        end_date = _text(end_date)
        account_id = _text(account_id) or "main"
        month_key = self._normalize_month_key(trade_date=end_date)
        if not end_date or not month_key:
            return {}
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT trade_date, account_id, month_key, month_return_pct, equity, cash,
                       position_market_value, realized_pnl, unrealized_pnl, max_drawdown_pct,
                       planned_trade_count, unplanned_trade_count, note, source_policy,
                       payload_json, updated_at
                FROM monthly_account_ledger
                WHERE account_id = ?
                  AND month_key = ?
                  AND trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT 1
                """,
                (account_id, month_key, end_date),
            ).fetchone()
        if not row:
            return {}
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload_json") or "{}")
        except json.JSONDecodeError:
            item["payload"] = {}
        return item

    def upsert_mainline_daily(self, row):
        row = row or {}
        trade_date = _text(row.get("trade_date") or row.get("date"))
        if not trade_date:
            return {}
        item = {
            "trade_date": trade_date,
            "primary_mainline": _text(row.get("primary_mainline") or row.get("mainline") or row.get("leading_line")),
            "daily_attack_line": _text(row.get("daily_attack_line") or row.get("primary_mainline") or row.get("leading_line")),
            "secondary_mainline": _text(row.get("secondary_mainline")),
            "competition_mainline": _text(row.get("competition_mainline")),
            "rotation_label": _text(row.get("rotation_label")),
            "leading_line": _text(row.get("leading_line") or row.get("primary_mainline")),
            "state_code": _text(row.get("state_code")),
            "confidence": _safe_float(row.get("confidence")),
            "evidence_json": json.dumps(row.get("evidence") or row.get("evidence_json") or {}, ensure_ascii=False, sort_keys=True),
            "rotation_summary": _text(row.get("rotation_summary")),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mainline_daily(
                    trade_date, primary_mainline, daily_attack_line, secondary_mainline,
                    competition_mainline, rotation_label, leading_line, state_code,
                    confidence, evidence_json, rotation_summary, source_policy, source_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                    primary_mainline=excluded.primary_mainline,
                    daily_attack_line=excluded.daily_attack_line,
                    secondary_mainline=excluded.secondary_mainline,
                    competition_mainline=excluded.competition_mainline,
                    rotation_label=excluded.rotation_label,
                    leading_line=excluded.leading_line,
                    state_code=excluded.state_code,
                    confidence=excluded.confidence,
                    evidence_json=excluded.evidence_json,
                    rotation_summary=excluded.rotation_summary,
                    source_policy=excluded.source_policy,
                    source_run_id=excluded.source_run_id
                """,
                (
                    item["trade_date"],
                    item["primary_mainline"],
                    item["daily_attack_line"],
                    item["secondary_mainline"],
                    item["competition_mainline"],
                    item["rotation_label"],
                    item["leading_line"],
                    item["state_code"],
                    item["confidence"],
                    item["evidence_json"],
                    item["rotation_summary"],
                    item["source_policy"],
                    item["source_run_id"],
                ),
            )
            conn.commit()
        return item

    def query_mainline_daily_series(self, end_date, *, window_days=25):
        end_date = _text(end_date)
        window_days = max(_safe_int(window_days, 25), 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trade_date, primary_mainline, daily_attack_line, secondary_mainline,
                       competition_mainline, rotation_label, leading_line, state_code,
                       confidence, evidence_json, rotation_summary, source_policy, source_run_id
                FROM mainline_daily
                WHERE trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (end_date, window_days),
            ).fetchall()
        result = []
        for row in reversed(rows):
            item = dict(row)
            item["date"] = item["trade_date"]
            item["source"] = item.get("source_policy", "")
            result.append(item)
        return result

    def upsert_mainline_turnover_daily(self, row):
        row = row or {}
        trade_date = _text(row.get("trade_date") or row.get("date"))
        primary_mainline = _text(
            row.get("primary_mainline")
            or row.get("sector_name")
            or row.get("cycle_mainline")
            or row.get("daily_attack_line")
        )
        if not trade_date or not primary_mainline:
            return {}
        scope_key = _text(row.get("turnover_scope_key")) or primary_mainline
        item = {
            "trade_date": trade_date,
            "primary_mainline": primary_mainline,
            "turnover_scope_key": scope_key,
            "turnover_scope_label": _text(row.get("turnover_scope_label") or row.get("sector_name") or primary_mainline),
            "sector_turnover_yi": _safe_float(row.get("sector_turnover_yi", row.get("sector_turnover"))),
            "total_turnover_yi": _safe_float(row.get("total_turnover_yi", row.get("total_turnover"))),
            "turnover_share_pct": _safe_float(row.get("turnover_share_pct")),
            "matched_sector_names_json": json.dumps(row.get("matched_sector_names") or [], ensure_ascii=False),
            "matched_sector_codes_json": json.dumps(row.get("matched_sector_codes") or [], ensure_ascii=False),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        if item["turnover_share_pct"] <= 0 and item["sector_turnover_yi"] > 0 and item["total_turnover_yi"] > 0:
            item["turnover_share_pct"] = item["sector_turnover_yi"] / item["total_turnover_yi"] * 100
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mainline_turnover_daily(
                    trade_date, primary_mainline, turnover_scope_key, turnover_scope_label,
                    sector_turnover_yi, total_turnover_yi, turnover_share_pct,
                    matched_sector_names_json, matched_sector_codes_json,
                    source_policy, source_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date, primary_mainline, turnover_scope_key) DO UPDATE SET
                    turnover_scope_label=excluded.turnover_scope_label,
                    sector_turnover_yi=excluded.sector_turnover_yi,
                    total_turnover_yi=excluded.total_turnover_yi,
                    turnover_share_pct=excluded.turnover_share_pct,
                    matched_sector_names_json=excluded.matched_sector_names_json,
                    matched_sector_codes_json=excluded.matched_sector_codes_json,
                    source_policy=excluded.source_policy,
                    source_run_id=excluded.source_run_id
                """,
                (
                    item["trade_date"],
                    item["primary_mainline"],
                    item["turnover_scope_key"],
                    item["turnover_scope_label"],
                    item["sector_turnover_yi"],
                    item["total_turnover_yi"],
                    item["turnover_share_pct"],
                    item["matched_sector_names_json"],
                    item["matched_sector_codes_json"],
                    item["source_policy"],
                    item["source_run_id"],
                ),
            )
            conn.commit()
        return item

    def upsert_sector_fund_flow_daily(self, row):
        row = row or {}
        trade_date = _text(row.get("trade_date") or row.get("date"))
        sector_name = _text(row.get("sector_name"))
        if not trade_date or not sector_name:
            return {}
        item = {
            "trade_date": trade_date,
            "sector_name": sector_name,
            "net_inflow_yi": _safe_float(row.get("net_inflow_yi", row.get("inflow"))),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
            "updated_at": _utc_now_text(),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sector_fund_flow_daily(
                    trade_date, sector_name, net_inflow_yi, source_policy,
                    source_run_id, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date, sector_name) DO UPDATE SET
                    net_inflow_yi=excluded.net_inflow_yi,
                    source_policy=excluded.source_policy,
                    source_run_id=excluded.source_run_id,
                    updated_at=excluded.updated_at
                """,
                (
                    item["trade_date"],
                    item["sector_name"],
                    item["net_inflow_yi"],
                    item["source_policy"],
                    item["source_run_id"],
                    item["updated_at"],
                ),
            )
            conn.commit()
        return item

    def query_sector_fund_flow_series(self, end_date, sector_name, *, window_days=8):
        end_date = _text(end_date)
        sector_name = _text(sector_name)
        window_days = max(_safe_int(window_days, 8), 1)
        if not end_date or not sector_name:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trade_date, sector_name, net_inflow_yi
                FROM sector_fund_flow_daily
                WHERE trade_date <= ?
                  AND sector_name = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (end_date, sector_name, window_days),
            ).fetchall()
        return [
            {
                "date": row["trade_date"],
                "sector_name": row["sector_name"],
                "inflow": _safe_float(row["net_inflow_yi"]),
            }
            for row in reversed(rows)
        ]

    def query_mainline_turnover_series(self, end_date, sector_name, *, window_days=25):
        end_date = _text(end_date)
        sector_name = _text(sector_name)
        window_days = max(_safe_int(window_days, 25), 1)
        if not sector_name:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trade_date, primary_mainline, turnover_scope_key, turnover_scope_label,
                       sector_turnover_yi, total_turnover_yi, turnover_share_pct,
                       matched_sector_names_json, matched_sector_codes_json,
                       source_policy, source_run_id
                FROM mainline_turnover_daily
                WHERE trade_date <= ?
                  AND (
                    primary_mainline = ?
                    OR turnover_scope_key = ?
                    OR turnover_scope_label = ?
                    OR matched_sector_names_json LIKE ?
                  )
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (end_date, sector_name, sector_name, sector_name, f"%{sector_name}%", window_days),
            ).fetchall()
        result = []
        for row in reversed(rows):
            item = dict(row)
            try:
                matched_names = json.loads(item.get("matched_sector_names_json") or "[]")
            except json.JSONDecodeError:
                matched_names = []
            try:
                matched_codes = json.loads(item.get("matched_sector_codes_json") or "[]")
            except json.JSONDecodeError:
                matched_codes = []
            result.append(
                {
                    "date": item["trade_date"],
                    "sector_name": item["primary_mainline"] or item["turnover_scope_label"],
                    "sector_turnover": _safe_float(item.get("sector_turnover_yi")),
                    "total_turnover": _safe_float(item.get("total_turnover_yi")),
                    "turnover_share_pct": _safe_float(item.get("turnover_share_pct")),
                    "matched_sector_names": matched_names,
                    "matched_sector_codes": matched_codes,
                    "source": item.get("source_policy", ""),
                }
            )
        return result

    def upsert_price_band_style_daily(self, row):
        row = row or {}
        trade_date = _text(row.get("trade_date") or row.get("date"))
        if not trade_date:
            return {}
        high_pct = _safe_float(row.get("high_price_pct"))
        low_pct = _safe_float(row.get("low_price_pct"))
        spread_pct = _price_band_spread_pct(high_pct, low_pct)
        style_label = _price_band_style_label(spread_pct)
        item = {
            "trade_date": trade_date,
            "high_price_code": _text(row.get("high_price_code")) or "883916.TI",
            "low_price_code": _text(row.get("low_price_code")) or "883960.TI",
            "high_price_pct": high_pct,
            "low_price_pct": low_pct,
            "spread_pct": spread_pct,
            "style_label": style_label,
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO price_band_style_daily(
                    trade_date, high_price_code, low_price_code, high_price_pct,
                    low_price_pct, spread_pct, style_label, source_policy, source_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                    high_price_code=excluded.high_price_code,
                    low_price_code=excluded.low_price_code,
                    high_price_pct=excluded.high_price_pct,
                    low_price_pct=excluded.low_price_pct,
                    spread_pct=excluded.spread_pct,
                    style_label=excluded.style_label,
                    source_policy=excluded.source_policy,
                    source_run_id=excluded.source_run_id
                """,
                (
                    item["trade_date"],
                    item["high_price_code"],
                    item["low_price_code"],
                    item["high_price_pct"],
                    item["low_price_pct"],
                    item["spread_pct"],
                    item["style_label"],
                    item["source_policy"],
                    item["source_run_id"],
                ),
            )
            conn.commit()
        return item

    def query_price_band_style_series(self, end_date, *, window_days=25):
        end_date = _text(end_date)
        window_days = max(_safe_int(window_days, 25), 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trade_date, high_price_code, low_price_code, high_price_pct,
                       low_price_pct, spread_pct, style_label, source_policy, source_run_id
                FROM price_band_style_daily
                WHERE trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (end_date, window_days),
            ).fetchall()
        result_rows = []
        for row in reversed(rows):
            item = dict(row)
            item["spread_pct"] = _price_band_spread_pct(
                item.get("high_price_pct"),
                item.get("low_price_pct"),
            )
            item["style_label"] = _price_band_style_label(item["spread_pct"])
            result_rows.append(item)
        return {
            "source": "storage.price_band_style_daily",
            "rows": result_rows,
        }

    def upsert_margin_pressure_daily(self, row):
        row = row or {}
        margin_balance = _safe_float(row.get("margin_balance_yi", row.get("rzye_yi")))
        market_turnover = _safe_float(row.get("market_turnover_yi", row.get("total_amount_yi")))
        ratio_pct = _safe_float(row.get("margin_turnover_ratio_pct"))
        if ratio_pct <= 0 and margin_balance > 0 and market_turnover > 0:
            ratio_pct = margin_balance / market_turnover * 100
        item = {
            "trade_date": _text(row.get("trade_date") or row.get("date")),
            "margin_balance_yi": margin_balance,
            "short_selling_balance_yi": _safe_float(row.get("short_selling_balance_yi", row.get("rqye_yi"))),
            "margin_trading_balance_yi": _safe_float(row.get("margin_trading_balance_yi", row.get("rzrqye_yi"))),
            "market_turnover_yi": market_turnover,
            "margin_turnover_ratio_pct": ratio_pct,
            "pressure_diff_pct": ratio_pct - 100 if ratio_pct > 0 else 0,
            "exchange_count": _safe_int(row.get("exchange_count")),
            "stock_count": _safe_int(row.get("stock_count")),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        if not item["trade_date"]:
            return {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO margin_pressure_daily(
                    trade_date, margin_balance_yi, short_selling_balance_yi,
                    margin_trading_balance_yi, market_turnover_yi,
                    margin_turnover_ratio_pct, pressure_diff_pct, exchange_count,
                    stock_count, source_policy, source_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                    margin_balance_yi=excluded.margin_balance_yi,
                    short_selling_balance_yi=excluded.short_selling_balance_yi,
                    margin_trading_balance_yi=excluded.margin_trading_balance_yi,
                    market_turnover_yi=excluded.market_turnover_yi,
                    margin_turnover_ratio_pct=excluded.margin_turnover_ratio_pct,
                    pressure_diff_pct=excluded.pressure_diff_pct,
                    exchange_count=excluded.exchange_count,
                    stock_count=excluded.stock_count,
                    source_policy=excluded.source_policy,
                    source_run_id=excluded.source_run_id
                """,
                (
                    item["trade_date"],
                    item["margin_balance_yi"],
                    item["short_selling_balance_yi"],
                    item["margin_trading_balance_yi"],
                    item["market_turnover_yi"],
                    item["margin_turnover_ratio_pct"],
                    item["pressure_diff_pct"],
                    item["exchange_count"],
                    item["stock_count"],
                    item["source_policy"],
                    item["source_run_id"],
                ),
            )
            conn.commit()
        return item

    def query_margin_pressure_series(self, end_date, *, window_days=25):
        end_date = _text(end_date)
        window_days = max(_safe_int(window_days, 25), 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trade_date, margin_balance_yi, short_selling_balance_yi,
                       margin_trading_balance_yi, market_turnover_yi,
                       margin_turnover_ratio_pct, pressure_diff_pct,
                       exchange_count, stock_count, source_policy, source_run_id
                FROM margin_pressure_daily
                WHERE trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (end_date, window_days),
            ).fetchall()
        result_rows = []
        for row in reversed(rows):
            item = dict(row)
            ratio_pct = _safe_float(item.get("margin_turnover_ratio_pct"))
            if ratio_pct <= 0 and _safe_float(item.get("margin_balance_yi")) > 0 and _safe_float(item.get("market_turnover_yi")) > 0:
                ratio_pct = _safe_float(item.get("margin_balance_yi")) / _safe_float(item.get("market_turnover_yi")) * 100
            item["margin_turnover_ratio_pct"] = ratio_pct
            item["pressure_diff_pct"] = ratio_pct - 100 if ratio_pct > 0 else 0
            item["source"] = item.get("source_policy", "")
            result_rows.append(item)
        return {
            "source": "storage.margin_pressure_daily",
            "rows": result_rows,
        }

    def upsert_new_high_feedback_daily(self, row):
        row = row or {}
        trade_date = _text(row.get("trade_date") or row.get("date"))
        if not trade_date:
            return {}
        item = {
            "trade_date": trade_date,
            "new_high_count": _safe_int(row.get("new_high_count")),
            "all_a_share_pct": _safe_float(row.get("all_a_share_pct")),
            "leading_sectors": _text(row.get("leading_sectors")),
            "sector_distribution_json": json.dumps(row.get("sector_distribution") or [], ensure_ascii=False),
            "top_stocks_json": json.dumps(row.get("top_stocks") or [], ensure_ascii=False),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO new_high_feedback_daily(
                    trade_date, new_high_count, all_a_share_pct, leading_sectors,
                    sector_distribution_json, top_stocks_json, source_policy, source_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                    new_high_count=excluded.new_high_count,
                    all_a_share_pct=excluded.all_a_share_pct,
                    leading_sectors=excluded.leading_sectors,
                    sector_distribution_json=excluded.sector_distribution_json,
                    top_stocks_json=excluded.top_stocks_json,
                    source_policy=excluded.source_policy,
                    source_run_id=excluded.source_run_id
                """,
                (
                    item["trade_date"],
                    item["new_high_count"],
                    item["all_a_share_pct"],
                    item["leading_sectors"],
                    item["sector_distribution_json"],
                    item["top_stocks_json"],
                    item["source_policy"],
                    item["source_run_id"],
                ),
            )
            conn.commit()
        return item

    def query_new_high_feedback_series(self, end_date, *, window_days=25):
        end_date = _text(end_date)
        window_days = max(_safe_int(window_days, 25), 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trade_date, new_high_count, all_a_share_pct, leading_sectors,
                       sector_distribution_json, top_stocks_json, source_policy, source_run_id
                FROM new_high_feedback_daily
                WHERE trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (end_date, window_days),
            ).fetchall()
        result = []
        for row in reversed(rows):
            item = dict(row)
            try:
                sector_distribution = json.loads(item.get("sector_distribution_json") or "[]")
            except json.JSONDecodeError:
                sector_distribution = []
            try:
                top_stocks = json.loads(item.get("top_stocks_json") or "[]")
            except json.JSONDecodeError:
                top_stocks = []
            result.append(
                {
                    "trade_date": item["trade_date"],
                    "new_high_count": _safe_int(item.get("new_high_count")),
                    "all_a_share_pct": _safe_float(item.get("all_a_share_pct")),
                    "leading_sectors": item.get("leading_sectors", ""),
                    "sector_distribution": sector_distribution,
                    "top_stocks": top_stocks,
                    "source": item.get("source_policy", ""),
                }
            )
        return result

    def build_new_high_feedback_from_recent_quotes(
        self,
        trade_date,
        *,
        stock_basic_map=None,
        stock_risk_map=None,
        history_rows=None,
        all_a_denominator=5000,
        recent_listing_days=365,
        lookback_days=250,
    ):
        from domains.market_activity.new_high_runtime import build_new_high_feedback_snapshot

        trade_date = _text(trade_date)
        if not trade_date:
            return {}
        stock_basic_map = stock_basic_map or {}
        stock_risk_map = stock_risk_map or {}
        lookback_days = max(_safe_int(lookback_days, 250), 1)
        with self._connect() as conn:
            target_rows = conn.execute(
                """
                SELECT trade_date, ts_code, stock_code, market, name, open, high, low,
                       close, pct_chg, vol, amount_yi
                FROM stock_daily_quotes_recent
                WHERE trade_date = ? AND high > 0
                """,
                (trade_date,),
            ).fetchall()
            if not target_rows:
                return {}
            coverage_row = conn.execute(
                """
                SELECT COUNT(DISTINCT trade_date) AS available_trade_days
                FROM stock_daily_quotes_recent
                WHERE trade_date < ?
                """,
                (trade_date,),
            ).fetchone()
            available_trade_days = _safe_int(coverage_row["available_trade_days"] if coverage_row else 0)
            if available_trade_days < lookback_days:
                return {
                    "available": False,
                    "status": "insufficient_history",
                    "source": "storage.stock_daily_quotes_recent.high_break",
                    "message": f"本地日线历史不足，只有 {available_trade_days} 个历史交易日，不能重建 {lookback_days} 日新高反馈。",
                    "new_high_count": 0,
                    "all_a_share_pct": 0.0,
                    "sector_distribution": [],
                    "top_stocks": [],
                    "trend_rows": list(history_rows or [])[-25:],
                }
            stock_codes = [_text(row["stock_code"]) for row in target_rows if _text(row["stock_code"])]
            historical_high_by_code = {}
            if stock_codes:
                placeholders = ",".join("?" for _ in stock_codes)
                history = conn.execute(
                    f"""
                    SELECT stock_code, MAX(high) AS previous_high
                    FROM stock_daily_quotes_recent
                    WHERE trade_date < ?
                      AND stock_code IN ({placeholders})
                      AND high > 0
                    GROUP BY stock_code
                    """,
                    [trade_date, *stock_codes],
                ).fetchall()
                historical_high_by_code = {
                    _text(row["stock_code"]): _safe_float(row["previous_high"])
                    for row in history
                }
            total_count = conn.execute(
                """
                SELECT COUNT(*) AS total_count
                FROM stock_daily_quotes_recent
                WHERE trade_date = ?
                """,
                (trade_date,),
            ).fetchone()
        factor_rows = []
        for row in target_rows:
            stock_code = _text(row["stock_code"])
            previous_high = historical_high_by_code.get(stock_code, 0.0)
            if previous_high <= 0 or _safe_float(row["high"]) < previous_high:
                continue
            factor_rows.append(
                {
                    "ts_code": _text(row["ts_code"]),
                    "stock_code": stock_code,
                    "trade_date": trade_date.replace("-", ""),
                    "name": _text(row["name"]),
                    "open": _safe_float(row["open"]),
                    "high": _safe_float(row["high"]),
                    "low": _safe_float(row["low"]),
                    "close": _safe_float(row["close"]),
                    "pct_chg": _safe_float(row["pct_chg"]),
                    "amount_yi": _safe_float(row["amount_yi"]),
                    "topdays": lookback_days,
                }
            )
        denominator = _safe_int(total_count["total_count"] if total_count else 0) or all_a_denominator
        snapshot = build_new_high_feedback_snapshot(
            factor_rows,
            stock_basic_map=stock_basic_map,
            stock_risk_map=stock_risk_map,
            target_date=trade_date,
            topdays_threshold=lookback_days,
            all_a_denominator=denominator,
            recent_listing_days=recent_listing_days,
            history_rows=history_rows,
        )
        if not snapshot.get("available"):
            return snapshot
        snapshot["source"] = "storage.stock_daily_quotes_recent.high_break"
        snapshot["source_policy"] = "storage.stock_daily_quotes_recent.high_break"
        snapshot["topdays_threshold"] = lookback_days
        snapshot["message"] = "Tushare 技术因子未返回时，使用本地日线历史高点重建阶段新高反馈。"
        return snapshot

    def delete_new_high_feedback_outside_dates(self, valid_dates, *, end_date=None):
        valid_dates = [
            _text(date)
            for date in (valid_dates or [])
            if _text(date)
        ]
        end_date = _text(end_date)
        if not valid_dates:
            return 0
        placeholders = ",".join("?" for _ in valid_dates)
        params = list(valid_dates)
        start_date = min(valid_dates)
        date_clause = " AND trade_date >= ?"
        params.append(start_date)
        if end_date:
            date_clause += " AND trade_date <= ?"
            params.append(end_date)
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                DELETE FROM new_high_feedback_daily
                WHERE trade_date NOT IN ({placeholders}){date_clause}
                """,
                params,
            )
            conn.commit()
            return cursor.rowcount

    def _normalize_extreme_conviction_mention(self, row):
        row = row or {}
        mention_date = _text(row.get("mention_trade_date") or row.get("trade_date") or row.get("date"))
        stock_code = _text(row.get("stock_code") or row.get("code"))
        record_id = _text(row.get("record_id")) or f"{mention_date}:{stock_code}"
        return {
            "record_id": record_id,
            "mention_trade_date": mention_date,
            "stock_code": stock_code,
            "stock_name": _text(row.get("stock_name") or row.get("name")),
            "rank_no": _safe_int(row.get("rank_no") or row.get("rank")),
            "sector_candidate": _text(row.get("sector_candidate") or row.get("sector")),
            "buy_window": _text(row.get("buy_window")),
            "planned_window": _text(row.get("planned_window") or row.get("participation_window")),
            "review_status": _text(row.get("review_status")),
            "next_action": _text(row.get("next_action")),
            "invalidation": _text(row.get("invalidation")),
            "reason": _text(row.get("reason")),
            "source_section": _text(row.get("source_section")),
            "is_a_kill_eliminated": 1 if bool(row.get("is_a_kill_eliminated")) else 0,
            "payload_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
            "updated_at": _utc_now_text(),
        }

    def upsert_extreme_conviction_mentions(self, rows):
        normalized = []
        for row in rows or []:
            item = self._normalize_extreme_conviction_mention(row)
            if not item["record_id"] or not item["mention_trade_date"] or not item["stock_code"]:
                continue
            normalized.append(item)
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO extreme_conviction_mentions(
                    record_id, mention_trade_date, stock_code, stock_name, rank_no,
                    sector_candidate, buy_window, planned_window, review_status,
                    next_action, invalidation, reason, source_section,
                    is_a_kill_eliminated, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    mention_trade_date=excluded.mention_trade_date,
                    stock_code=excluded.stock_code,
                    stock_name=excluded.stock_name,
                    rank_no=excluded.rank_no,
                    sector_candidate=excluded.sector_candidate,
                    buy_window=excluded.buy_window,
                    planned_window=excluded.planned_window,
                    review_status=excluded.review_status,
                    next_action=excluded.next_action,
                    invalidation=excluded.invalidation,
                    reason=excluded.reason,
                    source_section=excluded.source_section,
                    is_a_kill_eliminated=excluded.is_a_kill_eliminated,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        item["record_id"],
                        item["mention_trade_date"],
                        item["stock_code"],
                        item["stock_name"],
                        item["rank_no"],
                        item["sector_candidate"],
                        item["buy_window"],
                        item["planned_window"],
                        item["review_status"],
                        item["next_action"],
                        item["invalidation"],
                        item["reason"],
                        item["source_section"],
                        item["is_a_kill_eliminated"],
                        item["payload_json"],
                        item["updated_at"],
                    )
                    for item in normalized
                ],
            )
            conn.commit()
        return len(normalized)

    def _query_recent_quote_bars(self, conn, stock_code, end_date, *, limit=120):
        rows = conn.execute(
            """
            SELECT trade_date AS date, open, high, low, close, pct_chg, vol AS volume
            FROM stock_daily_quotes_recent
            WHERE stock_code = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (_text(stock_code), _text(end_date), int(limit or 120)),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def _is_a_kill_shape_from_bars(self, bars):
        bars = list(bars or [])[-120:]
        if len(bars) < 20:
            return False
        closes = [_safe_float(row.get("close")) for row in bars]
        highs = [_safe_float(row.get("high")) for row in bars]
        lows = [_safe_float(row.get("low")) for row in bars]
        pct_changes = [_safe_float(row.get("pct_chg")) for row in bars]

        def _ma(values, window):
            return sum(values[-window:]) / window if len(values) >= window else None

        close = closes[-1]
        ma5 = _ma(closes, 5)
        ma20 = _ma(closes, 20)
        previous_ma20 = _ma(closes[:-10], 20) if len(closes) >= 30 else None
        ma20_slope = ((ma20 / previous_ma20 - 1) * 100) if ma20 and previous_ma20 else 0.0
        recent20_high = max(highs[-20:])
        recent20_low = min(lows[-20:])
        previous20_high = max(highs[-40:-20]) if len(highs) >= 40 else None
        position20 = (
            (close - recent20_low) / (recent20_high - recent20_low) * 100
            if recent20_high and recent20_high != recent20_low
            else 50.0
        )
        high_shift_down = previous20_high is not None and recent20_high < previous20_high
        big_down60 = sum(1 for value in pct_changes[-60:] if value <= -7)
        last_big_drop = bool(pct_changes and pct_changes[-1] <= -9.5 and (ma5 is None or close < ma5))
        ma20_lost = bool(ma20 and close < ma20)
        return bool(
            ma20_lost
            and (
                (last_big_drop and position20 <= 35)
                or (big_down60 >= 2 and high_shift_down and ma20_slope <= 0)
                or (big_down60 >= 3 and position20 <= 35)
            )
        )

    def replace_extreme_conviction_mentions_for_trade_date(self, trade_date, rows):
        trade_date = _text(trade_date)
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM extreme_conviction_mentions WHERE mention_trade_date = ?",
                (trade_date,),
            )
            conn.commit()
        return self.upsert_extreme_conviction_mentions(rows)

    def mark_a_kill_shape_extreme_conviction_mentions(self, end_date, *, window_days=25, return_details=False):
        end_date = _text(end_date)
        window_days = max(_safe_int(window_days, 25), 1)
        with self._connect() as conn:
            date_rows = conn.execute(
                """
                SELECT DISTINCT mention_trade_date
                FROM extreme_conviction_mentions
                WHERE mention_trade_date <= ?
                ORDER BY mention_trade_date DESC
                LIMIT ?
                """,
                (end_date, window_days),
            ).fetchall()
            dates = [row["mention_trade_date"] for row in reversed(date_rows)]
            if not dates:
                if return_details:
                    return {"updated_count": 0, "updated_records": []}
                return 0
            placeholders = ",".join("?" for _ in dates)
            rows = conn.execute(
                f"""
                SELECT record_id, mention_trade_date, stock_code, stock_name, payload_json
                FROM extreme_conviction_mentions
                WHERE mention_trade_date IN ({placeholders})
                  AND is_a_kill_eliminated = 0
                ORDER BY mention_trade_date ASC, rank_no ASC, stock_code ASC
                """,
                list(dates),
            ).fetchall()
            updated_count = 0
            updated_records = []
            for row in rows:
                bars = self._query_recent_quote_bars(conn, row["stock_code"], end_date)
                if not self._is_a_kill_shape_from_bars(bars):
                    continue
                try:
                    payload = json.loads(row["payload_json"] or "{}")
                except json.JSONDecodeError:
                    payload = {}
                payload["is_a_kill_eliminated"] = True
                cursor = conn.execute(
                    """
                    UPDATE extreme_conviction_mentions
                    SET is_a_kill_eliminated = 1,
                        payload_json = ?,
                        updated_at = ?
                    WHERE record_id = ?
                    """,
                    (
                        json.dumps(payload, ensure_ascii=False, sort_keys=True),
                        _utc_now_text(),
                        row["record_id"],
                    ),
                )
                updated_count += cursor.rowcount
                if cursor.rowcount:
                    updated_records.append(
                        {
                            "record_id": row["record_id"],
                            "mention_trade_date": row["mention_trade_date"],
                            "stock_code": row["stock_code"],
                            "stock_name": row["stock_name"],
                        }
                    )
            conn.commit()
            if return_details:
                return {"updated_count": updated_count, "updated_records": updated_records}
            return updated_count

    def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
        end_date = _text(end_date)
        window_days = max(_safe_int(window_days, 25), 1)
        with self._connect() as conn:
            date_rows = conn.execute(
                """
                SELECT DISTINCT mention_trade_date
                FROM extreme_conviction_mentions
                WHERE mention_trade_date <= ?
                ORDER BY mention_trade_date DESC
                LIMIT ?
                """,
                (end_date, window_days),
            ).fetchall()
            dates = [row["mention_trade_date"] for row in reversed(date_rows)]
            if not dates:
                return []
            placeholders = ",".join("?" for _ in dates)
            query = f"""
                SELECT record_id, mention_trade_date, stock_code, stock_name, rank_no,
                       sector_candidate, buy_window, planned_window, review_status,
                       next_action, invalidation, reason, source_section,
                       is_a_kill_eliminated, payload_json, updated_at
                FROM extreme_conviction_mentions
                WHERE mention_trade_date IN ({placeholders})
            """
            params = list(dates)
            if not include_a_kill:
                query += " AND is_a_kill_eliminated = 0"
            query += " ORDER BY mention_trade_date ASC, rank_no ASC, stock_code ASC"
            rows = conn.execute(query, params).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["rank"] = _safe_int(item.get("rank_no"))
                item["is_a_kill_eliminated"] = bool(item.get("is_a_kill_eliminated"))
                if not include_a_kill and not item["is_a_kill_eliminated"]:
                    bars = self._query_recent_quote_bars(conn, item.get("stock_code"), end_date)
                    if self._is_a_kill_shape_from_bars(bars):
                        continue
                try:
                    item["payload"] = json.loads(item.get("payload_json") or "{}")
                except json.JSONDecodeError:
                    item["payload"] = {}
                result.append(item)
            return result

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

    def upsert_market_daily_total(self, row):
        row = row or {}
        item = {
            "trade_date": _text(row.get("trade_date") or row.get("date")),
            "market_scope": _text(row.get("market_scope")) or "all_a",
            "total_amount_yi": _safe_float(row.get("total_amount_yi", row.get("amount_yi"))),
            "stock_count": _safe_int(row.get("stock_count")),
            "source_policy": _text(row.get("source_policy") or row.get("source")),
            "source_run_id": _safe_int(row.get("source_run_id")),
        }
        if not item["trade_date"]:
            return {}
        with self._connect() as conn:
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
                    item["trade_date"],
                    item["market_scope"],
                    item["total_amount_yi"],
                    item["stock_count"],
                    item["source_policy"],
                    item["source_run_id"],
                ),
            )
            conn.commit()
        return item

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
