from __future__ import annotations

import datetime

import daily_report_analysis_utils as analysis_utils

__all__ = [
    "get_sector_turnover_snapshot_from_tencent_fund_flow",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _resolve_target_date_str(target_date=None):
    if target_date is None:
        return datetime.datetime.now().strftime("%Y-%m-%d")
    if hasattr(target_date, "strftime"):
        return target_date.strftime("%Y-%m-%d")
    return str(target_date)


def _build_empty_snapshot(target_date, sector_name, total_turnover, *, source_status="missing"):
    return {
        "date": _resolve_target_date_str(target_date),
        "sector_name": str(sector_name or "").strip(),
        "sector_code": "",
        "sector_kind": "industry",
        "matched_sector_names": [],
        "matched_sector_codes": [],
        "matched_sector_count": 0,
        "sector_turnover": 0.0,
        "total_turnover": round(_safe_float(total_turnover), 2),
        "turnover_share_pct": 0.0,
        "leader_stock": "",
        "leader_stocks": [],
        "source": "tencent.fundflow.getHyRank",
        "source_query": "cje",
        "source_status": source_status,
        "source_error": "",
    }


def _iter_fund_flow_rows(sector_fund_flow):
    if isinstance(sector_fund_flow, list):
        for item in sector_fund_flow:
            if isinstance(item, dict):
                yield item
        return

    if not isinstance(sector_fund_flow, dict):
        return

    for bucket in ("inflow", "outflow"):
        for item in sector_fund_flow.get(bucket, []) or []:
            if isinstance(item, dict):
                yield item


def _sector_name_matches(left, right):
    if str(left or "").strip() == str(right or "").strip():
        return True
    return analysis_utils.sector_name_matches(left, right)


def _pick_sector_row(sector_name, sector_fund_flow):
    sector_name = str(sector_name or "").strip()
    if not sector_name:
        return None

    fuzzy_match = None
    for row in _iter_fund_flow_rows(sector_fund_flow):
        row_name = str((row or {}).get("name") or "").strip()
        if not row_name:
            continue
        if row_name == sector_name:
            return row
        if fuzzy_match is None and _sector_name_matches(row_name, sector_name):
            fuzzy_match = row
    return fuzzy_match


def _pick_sector_row_by_name_or_code(sector_name, sector_code, rows):
    sector_code = str(sector_code or "").strip()
    sector_name = str(sector_name or "").strip()
    name_match = None
    for row in rows or []:
        row_code = str((row or {}).get("code") or "").strip()
        row_name = str((row or {}).get("name") or "").strip()
        if sector_code and row_code == sector_code:
            return row
        if sector_name and row_name == sector_name:
            return row
        if name_match is None and sector_name and _sector_name_matches(row_name, sector_name):
            name_match = row
    return name_match


def _resolve_turnover_yi(row):
    if not isinstance(row, dict):
        return 0.0

    for key in ("turnover_yi", "sector_turnover_yi", "sector_turnover"):
        value = row.get(key)
        if value not in (None, ""):
            return _safe_float(value)

    cje = row.get("cje")
    if cje not in (None, ""):
        return _safe_float(cje) / 1e4

    return 0.0


def _row_source(row):
    return str((row or {}).get("data_source") or "tencent.fundflow.getHyRank").strip()


def _row_source_query(row):
    row = row or {}
    if row.get("turnover_yi") not in (None, ""):
        return "turnover_yi"
    if row.get("sector_turnover_yi") not in (None, ""):
        return "sector_turnover_yi"
    if row.get("sector_turnover") not in (None, ""):
        return "sector_turnover"
    if row.get("cje") not in (None, ""):
        return "cje"
    return "cje"


def _fetch_tencent_sector_fund_flow_rows():
    import requests

    url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/fundflow/Fundflow/getHyRank?t=zljlr&o=1"
    response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    payload = response.json()
    return list(((payload.get("data") or {}).get("data") or []))


def get_sector_turnover_snapshot_from_tencent_fund_flow(
    sector_name,
    sector_fund_flow=None,
    *,
    target_date=None,
    total_turnover=0.0,
    fetch_sector_fund_flow_rows=None,
):
    target_date = _resolve_target_date_str(target_date)
    total_turnover = round(_safe_float(total_turnover), 2)
    row = _pick_sector_row(sector_name, sector_fund_flow)
    if not row:
        return _build_empty_snapshot(target_date, sector_name, total_turnover, source_status="missing")

    sector_turnover = round(_resolve_turnover_yi(row), 2)
    if sector_turnover <= 0:
        fetcher = fetch_sector_fund_flow_rows or _fetch_tencent_sector_fund_flow_rows
        try:
            refetched_row = _pick_sector_row_by_name_or_code(
                sector_name,
                row.get("code"),
                fetcher(),
            )
        except Exception:
            refetched_row = None
        if refetched_row:
            row = refetched_row
            sector_turnover = round(_resolve_turnover_yi(row), 2)

    if sector_turnover <= 0:
        snapshot = _build_empty_snapshot(target_date, sector_name, total_turnover, source_status="missing_field")
        snapshot.update(
            {
                "sector_name": str(row.get("name") or sector_name or "").strip(),
                "sector_code": str(row.get("code") or "").strip(),
                "matched_sector_names": [str(row.get("name") or sector_name or "").strip()],
                "matched_sector_codes": [str(row.get("code") or "").strip()] if row.get("code") else [],
                "matched_sector_count": 1 if row.get("code") else 0,
                "source": _row_source(row),
                "source_query": _row_source_query(row),
                "source_error": "missing cje/turnover_yi",
            }
        )
        return snapshot

    leader_stock = str((row.get("lzg") or {}).get("name") or row.get("lzg_name") or "").strip()
    sector_code = str(row.get("code") or "").strip()
    sector_name = str(row.get("name") or sector_name or "").strip()
    return {
        "date": target_date,
        "sector_name": sector_name,
        "sector_code": sector_code,
        "sector_kind": "industry",
        "matched_sector_names": [sector_name] if sector_name else [],
        "matched_sector_codes": [sector_code] if sector_code else [],
        "matched_sector_count": 1 if sector_code else 0,
        "sector_turnover": sector_turnover,
        "total_turnover": total_turnover,
        "turnover_share_pct": round((sector_turnover / total_turnover) * 100, 2) if total_turnover > 0 else 0.0,
        "leader_stock": leader_stock,
        "leader_stocks": [leader_stock] if leader_stock else [],
        "source": _row_source(row),
        "source_query": _row_source_query(row),
        "source_status": "success",
        "source_error": "",
    }
