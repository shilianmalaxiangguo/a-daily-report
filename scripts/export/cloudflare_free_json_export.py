from __future__ import annotations

import hashlib
import json
from pathlib import Path

from storage.cloudflare_free_daily_db import SCHEMA_VERSION_TURNOVER_SERIES

__all__ = [
    "CloudflareFreeJsonExportService",
]


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _round_amount(value):
    return round(_safe_float(value), 6)


def _round_pct(value):
    return round(_safe_float(value), 4)


def _sector_for_rank(row, stock_industry_map):
    ts_code = str((row or {}).get("ts_code") or "").strip().upper()
    stock_code = str((row or {}).get("stock_code") or "").strip()
    return str(
        (stock_industry_map or {}).get(ts_code)
        or (stock_industry_map or {}).get(stock_code)
        or "未分组"
    ).strip() or "未分组"


def _build_sector_breakdown(db, trade_date, *, limit, rank_scope, stock_industry_map):
    rank_rows = db.query_turnover_rank_rows(trade_date, limit=limit, rank_scope=rank_scope)
    if not rank_rows:
        return None
    by_sector = {}
    for row in rank_rows:
        sector = _sector_for_rank(row, stock_industry_map)
        bucket = by_sector.setdefault(sector, {"sector": sector, "amount_yi": 0.0, "stock_count": 0})
        bucket["amount_yi"] += _safe_float(row.get("amount_yi"))
        bucket["stock_count"] += 1
    total = sum(item["amount_yi"] for item in by_sector.values())
    rows = []
    for item in by_sector.values():
        amount = _round_amount(item["amount_yi"])
        rows.append(
            {
                "sector": item["sector"],
                "amount_yi": amount,
                "share_pct": _round_pct(amount / total * 100.0) if total > 0 else 0.0,
                "stock_count": item["stock_count"],
            }
        )
    rows.sort(key=lambda item: (-item["amount_yi"], item["sector"]))
    return {
        "trade_date": trade_date,
        "rank_limit": limit,
        "sector_source": "tushare.stock_basic.industry" if stock_industry_map else "fallback.unmapped",
        "total_top_amount_yi": _round_amount(total),
        "rows": rows,
    }


def _with_sector_breakdown(db, payload, *, stock_industry_map=None):
    query_window = payload.get("query_window") or {}
    limit = int(query_window.get("rank_limit") or 50)
    rank_scope = query_window.get("rank_scope") or "all_a"
    series = []
    for row in payload.get("rows") or []:
        trade_date = row.get("trade_date")
        if not trade_date:
            continue
        breakdown = _build_sector_breakdown(
            db,
            trade_date,
            limit=limit,
            rank_scope=rank_scope,
            stock_industry_map=stock_industry_map or {},
        )
        if breakdown:
            series.append(breakdown)
    if not series:
        return payload
    return {
        **payload,
        "sector_breakdown_series": series,
        "latest_sector_breakdown": series[-1],
    }


class CloudflareFreeJsonExportService:
    def __init__(self, db, *, artifact_root):
        self.db = db
        self.artifact_root = Path(artifact_root)

    def export_turnover_share_series(self, end_date, *, window_days=30, limit=50, stock_industry_map=None):
        payload = self.db.query_top_turnover_share_series(
            end_date,
            window_days=window_days,
            limit=limit,
        )
        payload = _with_sector_breakdown(self.db, payload, stock_industry_map=stock_industry_map)
        self.db.save_turnover_share_series(payload)
        r2_key = "exports/turnover/top50-share/latest.json"
        content_hash = _write_json(self.artifact_root / r2_key, payload)
        source_run_ids = list(payload.get("source_run_ids") or [])
        self.db.save_report_artifact(
            {
                "trade_date": (payload.get("query_window") or {}).get("end_date", ""),
                "variant": "turnover-top50-share",
                "visibility": "public",
                "r2_key": r2_key,
                "content_hash": content_hash,
                "schema_version": SCHEMA_VERSION_TURNOVER_SERIES,
                "source_run_id": source_run_ids[-1] if source_run_ids else 0,
                "created_at": payload.get("generated_at", ""),
            }
        )
        return {
            "r2_key": r2_key,
            "content_hash": content_hash,
            "schema_version": SCHEMA_VERSION_TURNOVER_SERIES,
            "row_count": len(payload.get("rows") or []),
        }
