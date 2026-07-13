from __future__ import annotations

import datetime as _dt
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import urllib.parse
import urllib.request

from market_data.kline_dates import normalize_kline_date_str


SCHEMA_VERSION = "report_index_cross_validation.v1"
VERIFICATION_PROVIDER = "tencent.fqkline.day"
CONTRACT_START_DATE = "2026-07-13"
PRICE_ABS_TOLERANCE = 0.05
CHANGE_PCT_ABS_TOLERANCE = 0.02

REPORT_INDEX_SPECS = (
    {
        "name": "上证指数",
        "code": "000001",
        "tencent_symbol": "sh000001",
        "container_key": "indices",
        "nested_key": "上证指数",
    },
    {
        "name": "深证成指",
        "code": "399001",
        "tencent_symbol": "sz399001",
        "container_key": "indices",
        "nested_key": "深证成指",
    },
    {
        "name": "创业板指",
        "code": "399006",
        "tencent_symbol": "sz399006",
        "container_key": "indices",
        "nested_key": "创业板指",
    },
    {
        "name": "中证全指",
        "code": "000985",
        "tencent_symbol": "sh000985",
        "container_key": "wind_a_alternative",
        "nested_key": "",
    },
    {
        "name": "中证500",
        "code": "000905",
        "tencent_symbol": "sh000905",
        "container_key": "csi500_index",
        "nested_key": "",
    },
    {
        "name": "中证1000",
        "code": "000852",
        "tencent_symbol": "sh000852",
        "container_key": "csi1000_index",
        "nested_key": "",
    },
)


def _optional_float(value):
    try:
        if value in (None, ""):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _first_float(payload, *keys):
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = _optional_float(payload.get(key))
        if value is not None:
            return value
    return None


def _primary_payload(report_data, spec):
    container = (report_data or {}).get(spec["container_key"])
    if spec["nested_key"]:
        if isinstance(container, dict):
            return container.get(spec["nested_key"]) or {}
        if isinstance(container, (list, tuple)):
            for item in container:
                if not isinstance(item, dict):
                    continue
                if item.get("name") == spec["name"] or str(item.get("code") or "") == spec["code"]:
                    return item
        return {}
    return container if isinstance(container, dict) else {}


def _normalize_primary_fact(payload, spec):
    payload = payload if isinstance(payload, dict) else {}
    return {
        "provider": str(payload.get("data_source") or payload.get("source") or "").strip(),
        "trade_date": normalize_kline_date_str(
            payload.get("trade_date") or payload.get("source_date") or payload.get("date")
        ),
        "code": str(payload.get("code") or "").strip(),
        "close": _first_float(payload, "close", "price", "点位"),
        "pre_close": _first_float(payload, "pre_close", "prev_close", "昨收"),
        "change_pct": _first_float(payload, "change_pct", "涨跌幅", "pct_chg"),
    }


def _empty_verification_fact(*, error=""):
    return {
        "provider": VERIFICATION_PROVIDER,
        "trade_date": "",
        "close": None,
        "pre_close": None,
        "change_pct": None,
        "error": str(error or ""),
    }


def fetch_tencent_index_daily_fact(symbol, target_date, *, urlopen_fn=None, timeout_seconds=8):
    target = normalize_kline_date_str(target_date)
    if not target:
        return _empty_verification_fact(error="目标日期无效")

    target_day = _dt.date.fromisoformat(target)
    start = (target_day - _dt.timedelta(days=15)).isoformat()
    query = urllib.parse.urlencode(
        {"param": f"{symbol},day,{start},{target},20,qfq"}
    )
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "Mozilla/5.0 daily-report-index-validation",
        },
    )
    opener = urlopen_fn or urllib.request.urlopen
    try:
        with opener(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return _empty_verification_fact(error=error)

    symbol_payload = ((payload or {}).get("data") or {}).get(symbol) or {}
    raw_rows = symbol_payload.get("day") or symbol_payload.get("qfqday") or []
    rows = []
    for raw in raw_rows:
        if not isinstance(raw, (list, tuple)) or len(raw) < 5:
            continue
        date_text = normalize_kline_date_str(raw[0])
        close = _optional_float(raw[2])
        if not date_text or close is None or close <= 0 or date_text > target:
            continue
        rows.append(
            {
                "trade_date": date_text,
                "open": _optional_float(raw[1]),
                "close": close,
                "high": _optional_float(raw[3]),
                "low": _optional_float(raw[4]),
            }
        )
    rows.sort(key=lambda item: item["trade_date"])
    if not rows:
        return _empty_verification_fact(error="腾讯日K未返回目标日期之前的数据")

    current = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else {}
    pre_close = _optional_float(previous.get("close"))
    change_pct = None
    if pre_close is not None and pre_close > 0:
        change_pct = (current["close"] - pre_close) / pre_close * 100
    return {
        "provider": VERIFICATION_PROVIDER,
        "trade_date": current["trade_date"],
        "close": current["close"],
        "pre_close": pre_close,
        "change_pct": change_pct,
        "source_url": url,
        "error": "",
    }


def _fact_field_failures(label, fact, target_date):
    failures = []
    if fact.get("trade_date") != target_date:
        source_date = fact.get("trade_date") or "缺失"
        failures.append(f"{label}日期为{source_date}，目标日期为{target_date}")
    close = _optional_float(fact.get("close"))
    pre_close = _optional_float(fact.get("pre_close"))
    change_pct = _optional_float(fact.get("change_pct"))
    if close is None or close <= 0:
        failures.append(f"{label}收盘缺失")
    if pre_close is None or pre_close <= 0:
        failures.append(f"{label}前收缺失")
    if change_pct is None:
        failures.append(f"{label}涨跌幅缺失")
    if fact.get("error"):
        failures.append(f"{label}读取失败：{fact['error']}")
    return failures


def _difference(left, right):
    left_value = _optional_float(left)
    right_value = _optional_float(right)
    if left_value is None or right_value is None:
        return None
    return abs(left_value - right_value)


def _source_difference_check(primary, verification):
    close_diff = _difference(primary.get("close"), verification.get("close"))
    pre_close_diff = _difference(primary.get("pre_close"), verification.get("pre_close"))
    change_pct_diff = _difference(primary.get("change_pct"), verification.get("change_pct"))
    failures = []
    if close_diff is not None and close_diff > PRICE_ABS_TOLERANCE:
        failures.append(f"收盘差异{close_diff:.4f}点超过{PRICE_ABS_TOLERANCE:.2f}点")
    if pre_close_diff is not None and pre_close_diff > PRICE_ABS_TOLERANCE:
        failures.append(f"前收差异{pre_close_diff:.4f}点超过{PRICE_ABS_TOLERANCE:.2f}点")
    if change_pct_diff is not None and change_pct_diff > CHANGE_PCT_ABS_TOLERANCE:
        failures.append(
            f"涨跌幅差异{change_pct_diff:.4f}个百分点超过{CHANGE_PCT_ABS_TOLERANCE:.2f}个百分点"
        )
    return failures, close_diff, pre_close_diff, change_pct_diff


def _source_identity_failures(primary, verification, spec):
    failures = []
    primary_provider = str(primary.get("provider") or "").strip().lower()
    verification_provider = str(verification.get("provider") or "").strip().lower()
    if not primary_provider or primary_provider == "unknown":
        failures.append("主来源标识缺失")
    if str(primary.get("code") or "").strip() != spec["code"]:
        failures.append("主来源代码与指数清单不一致")
    if verification_provider != VERIFICATION_PROVIDER:
        failures.append("核对来源不是腾讯日K")
    if not primary_provider or not verification_provider:
        return failures
    primary_family = primary_provider.split(".", 1)[0]
    verification_family = verification_provider.split(".", 1)[0]
    if primary_family and primary_family == verification_family:
        failures.append("主来源与核对来源不是独立来源")
    return failures


def build_report_index_cross_validation(
    report_data,
    target_date,
    *,
    fetch_verification_fact_fn=None,
):
    target = normalize_kline_date_str(target_date)
    fetcher = fetch_verification_fact_fn or fetch_tencent_index_daily_fact
    checks = []
    all_failures = []
    providers = set()
    verification_by_symbol = {}

    if fetch_verification_fact_fn is None:
        with ThreadPoolExecutor(max_workers=len(REPORT_INDEX_SPECS)) as executor:
            future_by_symbol = {
                executor.submit(fetcher, spec["tencent_symbol"], target): spec["tencent_symbol"]
                for spec in REPORT_INDEX_SPECS
            }
            for future in as_completed(future_by_symbol):
                symbol = future_by_symbol[future]
                try:
                    verification_by_symbol[symbol] = future.result()
                except Exception as error:
                    verification_by_symbol[symbol] = _empty_verification_fact(error=error)

    for spec in REPORT_INDEX_SPECS:
        primary = _normalize_primary_fact(_primary_payload(report_data, spec), spec)
        providers.add(primary.get("provider") or "unknown")
        try:
            verification = verification_by_symbol.get(spec["tencent_symbol"])
            if fetch_verification_fact_fn is not None:
                verification = fetcher(spec["tencent_symbol"], target)
        except Exception as error:
            verification = _empty_verification_fact(error=error)
        verification = dict(verification or _empty_verification_fact(error="核对来源返回空数据"))

        reasons = []
        reasons.extend(_fact_field_failures("主来源", primary, target))
        reasons.extend(_fact_field_failures("核对来源", verification, target))
        reasons.extend(_source_identity_failures(primary, verification, spec))
        difference_failures, close_diff, pre_close_diff, change_pct_diff = _source_difference_check(
            primary,
            verification,
        )
        reasons.extend(difference_failures)

        status = "failed" if reasons else "success"
        reason = "；".join(reasons)
        if reasons:
            all_failures.extend(f"{spec['name']}：{item}" for item in reasons)
        checks.append(
            {
                "name": spec["name"],
                "code": spec["code"],
                "status": status,
                "primary": primary,
                "verification": verification,
                "close_diff": close_diff,
                "pre_close_diff": pre_close_diff,
                "change_pct_diff": change_pct_diff,
                "reason": reason,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "target_date": target,
        "status": "failed" if all_failures else "success",
        "primary_provider": next(iter(providers)) if len(providers) == 1 else "mixed",
        "verification_provider": VERIFICATION_PROVIDER,
        "tolerances": {
            "price_abs": PRICE_ABS_TOLERANCE,
            "change_pct_abs": CHANGE_PCT_ABS_TOLERANCE,
        },
        "checks": checks,
        "failures": all_failures,
        "checked_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def index_cross_validation_required(target_date):
    target = normalize_kline_date_str(target_date)
    return bool(target and target >= CONTRACT_START_DATE)


def _dedupe(items):
    result = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def index_cross_validation_failures(report_data, target_date):
    target = normalize_kline_date_str(target_date)
    artifact = (report_data or {}).get("index_cross_validation")
    if not isinstance(artifact, dict):
        return ["指数交叉核对证据缺失"]

    failures = []
    if artifact.get("schema_version") != SCHEMA_VERSION:
        failures.append("指数交叉核对证据版本不正确")
    if normalize_kline_date_str(artifact.get("target_date")) != target:
        failures.append("指数交叉核对证据日期与日报日期不一致")
    recorded_failures = artifact.get("failures") or []
    if not isinstance(recorded_failures, (list, tuple, set)):
        recorded_failures = [recorded_failures]
    if artifact.get("status") != "success":
        failures.extend(recorded_failures or ["指数交叉核对未通过"])
    elif recorded_failures:
        failures.extend(f"指数交叉核对仍记录失败原因：{item}" for item in recorded_failures)
    if artifact.get("verification_provider") != VERIFICATION_PROVIDER:
        failures.append("指数交叉核对来源不是腾讯日K")

    checks = artifact.get("checks") if isinstance(artifact.get("checks"), list) else []
    expected_count = len(REPORT_INDEX_SPECS)
    if len(checks) != expected_count:
        failures.append(
            f"指数交叉核对必须包含{expected_count}个且仅包含这{expected_count}个指数"
        )
    name_counts = {}
    for item in checks:
        if not isinstance(item, dict):
            failures.append("指数交叉核对包含无效明细")
            continue
        name = str(item.get("name") or "")
        name_counts[name] = name_counts.get(name, 0) + 1
    duplicate_names = sorted(name for name, count in name_counts.items() if name and count > 1)
    if duplicate_names:
        failures.append("指数交叉核对包含重复指数：" + "、".join(duplicate_names))
    by_name = {
        str(item.get("name") or ""): item
        for item in checks
        if isinstance(item, dict) and item.get("name")
    }
    expected_names = {spec["name"] for spec in REPORT_INDEX_SPECS}
    if set(by_name) != expected_names:
        missing = sorted(expected_names - set(by_name))
        extra = sorted(set(by_name) - expected_names)
        if missing:
            failures.append("指数交叉核对缺少：" + "、".join(missing))
        if extra:
            failures.append("指数交叉核对包含未知指数：" + "、".join(extra))

    for spec in REPORT_INDEX_SPECS:
        check = by_name.get(spec["name"])
        if not isinstance(check, dict):
            continue
        if str(check.get("code") or "") != spec["code"]:
            failures.append(f"{spec['name']}代码与核对清单不一致")
        if check.get("status") != "success":
            failures.append(f"{spec['name']}交叉核对未通过")
        if str(check.get("reason") or "").strip():
            failures.append(f"{spec['name']}仍记录失败原因：{check['reason']}")
        primary = check.get("primary") if isinstance(check.get("primary"), dict) else {}
        verification = check.get("verification") if isinstance(check.get("verification"), dict) else {}
        failures.extend(f"{spec['name']}：{item}" for item in _fact_field_failures("主来源", primary, target))
        failures.extend(
            f"{spec['name']}：{item}"
            for item in _fact_field_failures("核对来源", verification, target)
        )
        failures.extend(f"{spec['name']}：{item}" for item in _source_identity_failures(primary, verification, spec))
        difference_failures, close_diff, pre_close_diff, change_pct_diff = _source_difference_check(
            primary,
            verification,
        )
        failures.extend(f"{spec['name']}：{item}" for item in difference_failures)
        for field, label, recomputed in (
            ("close_diff", "收盘差异", close_diff),
            ("pre_close_diff", "前收差异", pre_close_diff),
            ("change_pct_diff", "涨跌幅差异", change_pct_diff),
        ):
            stored = _optional_float(check.get(field))
            if stored is None:
                failures.append(f"{spec['name']}{label}记录缺失")
            elif recomputed is None or abs(stored - recomputed) > 1e-6:
                failures.append(f"{spec['name']}{label}记录与来源数据不一致")

        current = _normalize_primary_fact(_primary_payload(report_data, spec), spec)
        changed = any(
            str(current.get(key) or "").strip() != str(primary.get(key) or "").strip()
            for key in ("provider", "code", "trade_date")
        )
        for key in ("close", "pre_close", "change_pct"):
            diff = _difference(current.get(key), primary.get(key))
            if diff is None or diff > 1e-6:
                changed = True
        if changed:
            failures.append(f"{spec['name']}载荷在核对后发生变化")

    return _dedupe(failures)


__all__ = [
    "CONTRACT_START_DATE",
    "REPORT_INDEX_SPECS",
    "SCHEMA_VERSION",
    "build_report_index_cross_validation",
    "fetch_tencent_index_daily_fact",
    "index_cross_validation_failures",
    "index_cross_validation_required",
]
