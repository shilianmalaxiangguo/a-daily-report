from __future__ import annotations

import datetime

import daily_report_analysis_utils as analysis_utils

__all__ = [
    "get_sector_turnover_snapshot_from_ths",
]

_MISSING = object()


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def sector_name_matches(sector_a, sector_b):
    return analysis_utils.sector_name_matches(sector_a, sector_b)


def _resolve_target_date_str(target_date=None):
    if target_date is None:
        return datetime.datetime.now().strftime("%Y-%m-%d")
    if hasattr(target_date, "strftime"):
        return target_date.strftime("%Y-%m-%d")
    return str(target_date)


def _build_empty_snapshot(target_date, sector_name, total_turnover, *, sector_kind="", source_status="missing"):
    total_turnover = round(_safe_float(total_turnover), 2)
    return {
        "date": _resolve_target_date_str(target_date),
        "sector_name": str(sector_name or "").strip(),
        "sector_kind": str(sector_kind or "").strip(),
        "matched_sector_names": [],
        "matched_sector_codes": [],
        "matched_sector_count": 0,
        "sector_turnover": 0.0,
        "total_turnover": total_turnover,
        "turnover_share_pct": 0.0,
        "leader_stock": "",
        "leader_stocks": [],
        "up_count": 0,
        "down_count": 0,
        "sector_market_cap": 0.0,
        "sector_float_market_cap": 0.0,
        "source": "thsdk.market_data_block",
        "source_query": "基础数据",
        "source_status": source_status,
        "source_error": "",
        "failed_sector_codes": [],
    }


def _response_rows(response):
    if response is None:
        return []

    data = getattr(response, "data", None)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    dataframe = getattr(response, "df", None)
    if dataframe is not None:
        try:
            return [
                item for item in dataframe.to_dict("records")
                if isinstance(item, dict)
            ]
        except Exception:
            return []

    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]

    return []


def _pick_catalog_matches(sector_name, catalog_rows):
    exact_matches = []
    fuzzy_matches = []
    expected_name = str(sector_name or "").strip()

    for item in catalog_rows or []:
        item_name = str((item or {}).get("名称") or (item or {}).get("name") or "").strip()
        if not item_name:
            continue
        if item_name == expected_name:
            exact_matches.append(item)
            continue
        if sector_name_matches(item_name, expected_name):
            fuzzy_matches.append(item)

    return exact_matches or fuzzy_matches


def _resolve_sector_catalog_matches(ths_client, sector_name, sector_kind=""):
    sector_kind = str(sector_kind or "").strip().lower()

    def _industry_rows():
        return _response_rows(ths_client.ths_industry())

    def _concept_rows():
        return _response_rows(ths_client.ths_concept())

    if sector_kind == "industry":
        return "industry", _pick_catalog_matches(sector_name, _industry_rows())
    if sector_kind == "concept":
        return "concept", _pick_catalog_matches(sector_name, _concept_rows())

    industry_matches = _pick_catalog_matches(sector_name, _industry_rows())
    if industry_matches:
        return "industry", industry_matches

    concept_matches = _pick_catalog_matches(sector_name, _concept_rows())
    if concept_matches:
        return "concept", concept_matches

    return "", []


def _resolve_ths_client_factory():
    factory = globals().get("ths_client_factory")
    if callable(factory):
        return factory

    from thsdk import THS

    return THS


def get_sector_turnover_snapshot_from_ths(
    sector_name,
    *,
    target_date=None,
    total_turnover=0.0,
    sector_kind="",
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        target_date = _resolve_target_date_str(target_date)
        total_turnover = round(_safe_float(total_turnover), 2)
        try:
            factory = _resolve_ths_client_factory()
        except ModuleNotFoundError as exc:
            snapshot = _build_empty_snapshot(
                target_date,
                sector_name,
                total_turnover,
                sector_kind=sector_kind,
                source_status="missing_dependency",
            )
            snapshot["source_error"] = str(exc)
            return snapshot

        try:
            with factory() as ths_client:
                resolved_kind, matches = _resolve_sector_catalog_matches(ths_client, sector_name, sector_kind=sector_kind)
                if not matches:
                    return _build_empty_snapshot(
                        target_date,
                        sector_name,
                        total_turnover,
                        sector_kind=resolved_kind or sector_kind,
                    )

                matched_sector_names = []
                matched_sector_codes = []
                leader_stocks = []
                failed_sector_codes = []
                error_messages = []
                sector_turnover = 0.0
                up_count = 0
                down_count = 0
                sector_market_cap = 0.0
                sector_float_market_cap = 0.0

                for item in matches:
                    link_code = str(item.get("代码") or item.get("code") or "").strip()
                    item_name = str(item.get("名称") or item.get("name") or "").strip()
                    if not link_code or not item_name:
                        continue

                    matched_sector_names.append(item_name)
                    matched_sector_codes.append(link_code)

                    try:
                        block_rows = _response_rows(ths_client.market_data_block(link_code, "基础数据"))
                    except Exception as exc:
                        failed_sector_codes.append(link_code)
                        error_messages.append(f"{link_code}: {exc}")
                        continue
                    if not block_rows:
                        continue

                    block_row = block_rows[0]
                    sector_turnover += _safe_float(block_row.get("总金额")) / 1e8
                    up_count += int(round(_safe_float(block_row.get("上涨家数"))))
                    down_count += int(round(_safe_float(block_row.get("下跌家数"))))
                    sector_market_cap += _safe_float(block_row.get("板块总市值"))
                    sector_float_market_cap += _safe_float(block_row.get("板块流通市值"))

                    leader_stock = str(block_row.get("领涨股") or "").strip()
                    if leader_stock:
                        leader_stocks.append(leader_stock)

                snapshot = _build_empty_snapshot(
                    target_date,
                    sector_name,
                    total_turnover,
                    sector_kind=resolved_kind,
                    source_status="success",
                )
                snapshot.update(
                    {
                        "matched_sector_names": matched_sector_names,
                        "matched_sector_codes": matched_sector_codes,
                        "matched_sector_count": len(matched_sector_codes),
                        "sector_turnover": round(sector_turnover, 2),
                        "turnover_share_pct": round((sector_turnover / total_turnover) * 100, 2) if total_turnover > 0 else 0.0,
                        "leader_stock": leader_stocks[0] if leader_stocks else "",
                        "leader_stocks": leader_stocks,
                        "up_count": up_count,
                        "down_count": down_count,
                        "sector_market_cap": sector_market_cap,
                        "sector_float_market_cap": sector_float_market_cap,
                        "source_status": "degraded" if failed_sector_codes else ("success" if matched_sector_codes else "degraded"),
                        "source_error": "; ".join(error_messages),
                        "failed_sector_codes": failed_sector_codes,
                    }
                )
                return snapshot
        except Exception as exc:
            snapshot = _build_empty_snapshot(
                target_date,
                sector_name,
                total_turnover,
                sector_kind=sector_kind,
                source_status="error",
            )
            snapshot["source_error"] = str(exc)
            return snapshot
    finally:
        _restore_runtime_bindings(previous)
