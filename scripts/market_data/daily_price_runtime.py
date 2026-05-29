from __future__ import annotations

import datetime
import os
import signal
import threading

import daily_report_analysis_utils as analysis_utils
from market_data.kline_dates import normalize_kline_date_str as _normalize_kline_date_str
from market_data.kline_dates import parse_kline_date as _parse_kline_date

__all__ = [
    "compute_bar_change_pct",
    "compute_stop_loss_mainline_anchor",
    "compute_trend_article_stop_loss",
    "count_trading_days_between",
    "enrich_stop_plan_with_reference_anchors",
    "evaluate_live_tradability",
    "fetch_daily_price_bars",
    "fetch_recent_price_bars",
    "fetch_quicktiny_daily_price_bars",
    "get_first_bar_after",
    "get_first_bar_on_or_after",
    "get_last_bar_on_or_before",
    "get_limit_up_pct",
    "is_next_trading_day",
    "is_one_word_limit_bar",
    "merge_daily_price_bars",
    "resolve_big_yang_confluence_anchor",
    "run_with_wall_clock_timeout",
    "to_bs_code",
]

_MISSING = object()
STOP_PRIOR_LOW_TRADING_DAYS = 5
_daily_price_bar_cache = {}
_baostock_runtime_state = {
    "logged_in": False,
    "logout_registered": False,
}


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _logout_baostock_silently():
    try:
        import baostock as bs
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            bs.logout()
    except Exception:
        pass
    finally:
        _baostock_runtime_state["logged_in"] = False


def _ensure_baostock_login():
    if _baostock_runtime_state.get("logged_in"):
        return True

    try:
        import atexit
        import baostock as bs
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            login_result = bs.login()
        success = getattr(login_result, "error_code", "") == "0"
        if success:
            _baostock_runtime_state["logged_in"] = True
            if not _baostock_runtime_state.get("logout_registered"):
                atexit.register(_logout_baostock_silently)
                _baostock_runtime_state["logout_registered"] = True
        return success
    except Exception:
        _baostock_runtime_state["logged_in"] = False
        return False


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


def to_bs_code(security_code, is_index=False, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _to_bs_code_legacy_body(security_code, is_index=is_index)
    finally:
        _restore_runtime_bindings(previous)


def run_with_wall_clock_timeout(seconds, fn, *args, helpers=None, default=None, **kwargs):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _run_with_wall_clock_timeout_legacy_body(seconds, fn, *args, default=default, **kwargs)
    finally:
        _restore_runtime_bindings(previous)


def fetch_quicktiny_daily_price_bars(security_code, start_date, end_date, is_index=False, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _fetch_quicktiny_daily_price_bars_legacy_body(
            security_code,
            start_date,
            end_date,
            is_index=is_index,
        )
    finally:
        _restore_runtime_bindings(previous)


def merge_daily_price_bars(primary_bars, fallback_bars, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _merge_daily_price_bars_legacy_body(primary_bars, fallback_bars)
    finally:
        _restore_runtime_bindings(previous)


def fetch_daily_price_bars(
    security_code,
    start_date,
    end_date,
    is_index=False,
    prefer_fast=False,
    allow_baostock_fallback=True,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _fetch_daily_price_bars_legacy_body(
            security_code,
            start_date,
            end_date,
            is_index=is_index,
            prefer_fast=prefer_fast,
            allow_baostock_fallback=allow_baostock_fallback,
        )
    finally:
        _restore_runtime_bindings(previous)


def get_first_bar_after(bars, after_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_first_bar_after_legacy_body(bars, after_date)
    finally:
        _restore_runtime_bindings(previous)


def get_first_bar_on_or_after(bars, target_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_first_bar_on_or_after_legacy_body(bars, target_date)
    finally:
        _restore_runtime_bindings(previous)


def get_last_bar_on_or_before(bars, target_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_last_bar_on_or_before_legacy_body(bars, target_date)
    finally:
        _restore_runtime_bindings(previous)


def is_next_trading_day(prev_date, curr_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _is_next_trading_day_legacy_body(prev_date, curr_date)
    finally:
        _restore_runtime_bindings(previous)


def count_trading_days_between(start_date, end_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _count_trading_days_between_legacy_body(start_date, end_date)
    finally:
        _restore_runtime_bindings(previous)


def get_limit_up_pct(stock_code="", stock_name="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_limit_up_pct_legacy_body(stock_code=stock_code, stock_name=stock_name)
    finally:
        _restore_runtime_bindings(previous)


def is_one_word_limit_bar(
    stock_code="",
    stock_name="",
    open_price=None,
    high_price=None,
    low_price=None,
    close_price=None,
    change_pct=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _is_one_word_limit_bar_legacy_body(
            stock_code=stock_code,
            stock_name=stock_name,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            change_pct=change_pct,
        )
    finally:
        _restore_runtime_bindings(previous)


def compute_bar_change_pct(current_bar, prev_bar=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _compute_bar_change_pct_legacy_body(current_bar, prev_bar=prev_bar)
    finally:
        _restore_runtime_bindings(previous)


def evaluate_live_tradability(stock, target_date="", recent_bars=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _evaluate_live_tradability_legacy_body(stock, target_date=target_date, recent_bars=recent_bars)
    finally:
        _restore_runtime_bindings(previous)


def fetch_recent_price_bars(security_code, target_date, lookback_days=10, fast_fail=False, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _fetch_recent_price_bars_legacy_body(
            security_code,
            target_date,
            lookback_days=lookback_days,
            fast_fail=fast_fail,
        )
    finally:
        _restore_runtime_bindings(previous)


def compute_trend_article_stop_loss(bars, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _compute_trend_article_stop_loss_legacy_body(bars)
    finally:
        _restore_runtime_bindings(previous)


def compute_stop_loss_mainline_anchor(bars, window=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _compute_stop_loss_mainline_anchor_legacy_body(bars, window=window)
    finally:
        _restore_runtime_bindings(previous)


def resolve_big_yang_confluence_anchor(recent_bars, target_date="", window=6, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _resolve_big_yang_confluence_anchor_legacy_body(
            recent_bars,
            target_date=target_date,
            window=window,
        )
    finally:
        _restore_runtime_bindings(previous)


def enrich_stop_plan_with_reference_anchors(stop_plan, security_code, target_date, recent_bars=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _enrich_stop_plan_with_reference_anchors_legacy_body(
            stop_plan,
            security_code,
            target_date,
            recent_bars=recent_bars,
        )
    finally:
        _restore_runtime_bindings(previous)


def _trim_bars_to_target_date(bars, target_date):
    return _trim_bars_to_target_date_legacy_body(bars, target_date)


def _to_bs_code(security_code, is_index=False):
    return _to_bs_code_legacy_body(security_code, is_index=is_index)


def _run_with_wall_clock_timeout(seconds, fn, *args, default=None, **kwargs):
    return _run_with_wall_clock_timeout_legacy_body(seconds, fn, *args, default=default, **kwargs)


def _fetch_quicktiny_daily_price_bars(security_code, start_date, end_date, is_index=False):
    return _fetch_quicktiny_daily_price_bars_legacy_body(security_code, start_date, end_date, is_index=is_index)


def _merge_daily_price_bars(primary_bars, fallback_bars):
    return _merge_daily_price_bars_legacy_body(primary_bars, fallback_bars)


def _fetch_daily_price_bars(
    security_code,
    start_date,
    end_date,
    is_index=False,
    prefer_fast=False,
    allow_baostock_fallback=True,
):
    return _fetch_daily_price_bars_legacy_body(
        security_code,
        start_date,
        end_date,
        is_index=is_index,
        prefer_fast=prefer_fast,
        allow_baostock_fallback=allow_baostock_fallback,
    )


def _fetch_baostock_daily_price_bars(bs_code, start_date, end_date, is_index=False):
    return _fetch_baostock_daily_price_bars_legacy_body(
        bs_code,
        start_date,
        end_date,
        is_index=is_index,
    )


def _get_first_bar_after(bars, after_date):
    return _get_first_bar_after_legacy_body(bars, after_date)


def _get_first_bar_on_or_after(bars, target_date):
    return _get_first_bar_on_or_after_legacy_body(bars, target_date)


def _get_last_bar_on_or_before(bars, target_date):
    return _get_last_bar_on_or_before_legacy_body(bars, target_date)


def _is_next_trading_day(prev_date, curr_date):
    return _is_next_trading_day_legacy_body(prev_date, curr_date)


def _count_trading_days_between(start_date, end_date):
    return _count_trading_days_between_legacy_body(start_date, end_date)


def _get_limit_up_pct(stock_code="", stock_name=""):
    return _get_limit_up_pct_legacy_body(stock_code=stock_code, stock_name=stock_name)


def _is_one_word_limit_bar(
    stock_code="",
    stock_name="",
    open_price=None,
    high_price=None,
    low_price=None,
    close_price=None,
    change_pct=None,
):
    return _is_one_word_limit_bar_legacy_body(
        stock_code=stock_code,
        stock_name=stock_name,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        change_pct=change_pct,
    )


def _compute_bar_change_pct(current_bar, prev_bar=None):
    return _compute_bar_change_pct_legacy_body(current_bar, prev_bar=prev_bar)


def _evaluate_live_tradability(stock, target_date="", recent_bars=None):
    return _evaluate_live_tradability_legacy_body(stock, target_date=target_date, recent_bars=recent_bars)


def _to_bs_code_legacy_body(security_code, is_index=False):
    code = str(security_code or "").strip()
    if not code:
        return ""

    if code.startswith(("sh.", "sz.", "bj.")):
        return code
    if code.startswith(("sh", "sz", "bj")) and len(code) > 2 and "." not in code:
        return f"{code[:2]}.{code[2:]}"

    normalized = normalize_stock_code(code)
    if is_index:
        if normalized == "399001":
            return "sz.399001"
        if normalized == "399006":
            return "sz.399006"
        if normalized == "000001":
            return "sh.000001"
        market = "sh"
    else:
        if normalized.startswith(("8", "4")):
            market = "bj"
        elif normalized.startswith(("6", "9", "5")):
            market = "sh"
        else:
            market = "sz"
    return f"{market}.{normalized}"


def _run_with_wall_clock_timeout_legacy_body(seconds, fn, *args, default=None, **kwargs):
    seconds = _safe_float(seconds)
    if seconds <= 0:
        return fn(*args, **kwargs)

    if os.name != "posix" or threading.current_thread() is not threading.main_thread():
        return fn(*args, **kwargs)

    class _WallClockTimeoutError(TimeoutError):
        pass

    def _timeout_handler(signum, frame):
        raise _WallClockTimeoutError(f"wall clock timeout after {seconds}s")

    previous_handler = signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        return fn(*args, **kwargs)
    except _WallClockTimeoutError:
        return default
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _fetch_quicktiny_daily_price_bars_legacy_body(security_code, start_date, end_date, is_index=False):
    code = _to_bs_code(security_code, is_index=is_index).replace(".", "")
    start_date = _normalize_kline_date_str(start_date)
    end_date = _normalize_kline_date_str(end_date)
    if not code or not start_date or not end_date:
        return []

    try:
        import requests

        start_dt = _parse_kline_date(start_date)
        end_dt = _parse_kline_date(end_date)
        days = 20
        if start_dt and end_dt:
            days = max((end_dt - start_dt).days + 10, 20)
        url = f"https://stock.quicktiny.cn/api/tushare/merged-kline/{code}?days={days}"
        with requests.Session() as session:
            session.trust_env = False
            resp = session.get(url, timeout=(2, 6))
        resp.raise_for_status()
        result = resp.json()
        data = result.get("data", []) if isinstance(result, dict) else []
        bars = []
        for item in data:
            date_text = _normalize_kline_date_str(item.get("date"))
            if not date_text or not (start_date <= date_text <= end_date):
                continue
            bars.append({
                "date": date_text,
                "open": _safe_float(item.get("open")),
                "high": _safe_float(item.get("high")),
                "low": _safe_float(item.get("low")),
                "close": _safe_float(item.get("close")),
                "volume": _safe_float(item.get("volume") or item.get("vol")),
            })
        return sorted(bars, key=lambda x: x.get("date", ""))
    except Exception:
        return []


def _merge_daily_price_bars_legacy_body(primary_bars, fallback_bars):
    merged_by_date = {}
    for bar in fallback_bars or []:
        date_text = _normalize_kline_date_str(bar.get("date"))
        if date_text:
            merged_by_date[date_text] = {
                "date": date_text,
                "open": _safe_float(bar.get("open")),
                "high": _safe_float(bar.get("high")),
                "low": _safe_float(bar.get("low")),
                "close": _safe_float(bar.get("close")),
                "volume": _safe_float(bar.get("volume")),
            }
    for bar in primary_bars or []:
        date_text = _normalize_kline_date_str(bar.get("date"))
        if date_text:
            merged_by_date[date_text] = {
                "date": date_text,
                "open": _safe_float(bar.get("open")),
                "high": _safe_float(bar.get("high")),
                "low": _safe_float(bar.get("low")),
                "close": _safe_float(bar.get("close")),
                "volume": _safe_float(bar.get("volume")),
            }
    return [merged_by_date[key] for key in sorted(merged_by_date.keys())]


def _fetch_daily_price_bars_legacy_body(
    security_code,
    start_date,
    end_date,
    is_index=False,
    prefer_fast=False,
    allow_baostock_fallback=True,
):
    bs_code = _to_bs_code(security_code, is_index=is_index)
    start_date = _normalize_kline_date_str(start_date)
    end_date = _normalize_kline_date_str(end_date)
    if not bs_code or not start_date or not end_date:
        return []

    cache_key = (bs_code, start_date, end_date, bool(is_index), bool(prefer_fast), bool(allow_baostock_fallback))
    if cache_key in _daily_price_bar_cache:
        return [dict(item) for item in _daily_price_bar_cache[cache_key]]

    def _finalize(result_bars):
        result_bars = sorted(result_bars or [], key=lambda x: x.get("date", ""))
        last_bar_date = _normalize_kline_date_str((result_bars[-1] or {}).get("date")) if result_bars else ""
        if result_bars and last_bar_date >= end_date:
            _daily_price_bar_cache[cache_key] = [dict(item) for item in result_bars]
        else:
            _daily_price_bar_cache.pop(cache_key, None)
        return [dict(item) for item in result_bars]

    quicktiny_bars = []
    if prefer_fast:
        quicktiny_bars = _run_with_wall_clock_timeout(
            3,
            _fetch_quicktiny_daily_price_bars,
            security_code,
            start_date,
            end_date,
            is_index=is_index,
            default=[],
        ) or []
        quicktiny_last_date = _normalize_kline_date_str((quicktiny_bars[-1] or {}).get("date")) if quicktiny_bars else ""
        if quicktiny_bars and quicktiny_last_date >= end_date:
            return _finalize(quicktiny_bars)
        if not allow_baostock_fallback:
            return _finalize(quicktiny_bars)

    bars = []
    if allow_baostock_fallback:
        bars = _run_with_wall_clock_timeout(
            6,
            _fetch_baostock_daily_price_bars,
            bs_code,
            start_date,
            end_date,
            is_index=is_index,
            default=[],
        ) or []

    if not bars and not is_index:
        try:
            start_dt = _parse_kline_date(start_date)
            end_dt = _parse_kline_date(end_date)
            lookback_days = 20
            if start_dt and end_dt:
                lookback_days = max((end_dt - start_dt).days + 10, 20)
            recent = fetch_recent_price_bars(security_code, end_date, lookback_days=lookback_days)
            for bar in recent:
                date_text = _normalize_kline_date_str(bar.get("date"))
                if start_date <= date_text <= end_date:
                    bars.append({
                        "date": date_text,
                        "open": _safe_float(bar.get("open")),
                        "high": _safe_float(bar.get("high")),
                        "low": _safe_float(bar.get("low")),
                        "close": _safe_float(bar.get("close")),
                        "volume": _safe_float(bar.get("volume")),
                    })
        except Exception:
            bars = []

    needs_supplement = not bars or _normalize_kline_date_str((bars[-1] or {}).get("date")) < end_date
    if needs_supplement:
        if not quicktiny_bars:
            quicktiny_bars = _run_with_wall_clock_timeout(
                3,
                _fetch_quicktiny_daily_price_bars,
                security_code,
                start_date,
                end_date,
                is_index=is_index,
                default=[],
            ) or []
        if quicktiny_bars:
            bars = _merge_daily_price_bars(bars, quicktiny_bars)

    return _finalize(bars)


def _fetch_baostock_daily_price_bars_legacy_body(bs_code, start_date, end_date, is_index=False):
    bars = []
    try:
        import baostock as bs

        if _ensure_baostock_login():
            if is_index:
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,open,high,low,close,volume",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                )
            else:
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,open,high,low,close,volume",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="3",
                )

            if rs.error_code == "0":
                while (rs.error_code == "0") and rs.next():
                    row = rs.get_row_data()
                    bars.append({
                        "date": _normalize_kline_date_str(row[0]),
                        "open": _safe_float(row[1]),
                        "high": _safe_float(row[2]),
                        "low": _safe_float(row[3]),
                        "close": _safe_float(row[4]),
                        "volume": _safe_float(row[5]),
                    })
    except Exception:
        return []
    return bars


def _get_first_bar_after_legacy_body(bars, after_date):
    after_dt = _parse_kline_date(after_date)
    if after_dt is None:
        return None
    for bar in bars or []:
        bar_dt = _parse_kline_date(bar.get("date"))
        if bar_dt and bar_dt > after_dt:
            return bar
    return None


def _get_first_bar_on_or_after_legacy_body(bars, target_date):
    target_dt = _parse_kline_date(target_date)
    if target_dt is None:
        return None
    for bar in bars or []:
        bar_dt = _parse_kline_date(bar.get("date"))
        if bar_dt and bar_dt >= target_dt:
            return bar
    return None


def _get_last_bar_on_or_before_legacy_body(bars, target_date):
    target_dt = _parse_kline_date(target_date)
    if target_dt is None:
        return None
    result = None
    for bar in bars or []:
        bar_dt = _parse_kline_date(bar.get("date"))
        if bar_dt and bar_dt <= target_dt:
            result = bar
        elif bar_dt and bar_dt > target_dt:
            break
    return result


def _is_next_trading_day_legacy_body(prev_date, curr_date):
    prev_date = _normalize_kline_date_str(prev_date)
    curr_date = _normalize_kline_date_str(curr_date)
    if not prev_date or not curr_date or prev_date >= curr_date:
        return False

    bars = fetch_daily_price_bars("sh.000001", prev_date, curr_date, is_index=True)
    dates = [bar.get("date") for bar in bars if bar.get("date")]
    return len(dates) == 2 and dates[0] == prev_date and dates[-1] == curr_date


def _count_trading_days_between_legacy_body(start_date, end_date):
    start_date = _normalize_kline_date_str(start_date)
    end_date = _normalize_kline_date_str(end_date)
    if not start_date or not end_date or start_date > end_date:
        return 0

    bars = fetch_daily_price_bars("sh.000001", start_date, end_date, is_index=True)
    dates = [bar.get("date") for bar in bars if bar.get("date")]
    return len(dates)


def _get_limit_up_pct_legacy_body(stock_code="", stock_name=""):
    code = normalize_stock_code(stock_code)
    name = str(stock_name or "").upper()
    if "ST" in name:
        return 0.048
    if code.startswith(("43", "83", "87", "88", "89", "92")):
        return 0.298
    if code.startswith(("30", "68")):
        return 0.198
    return 0.098


def _is_one_word_limit_bar_legacy_body(
    stock_code="",
    stock_name="",
    open_price=None,
    high_price=None,
    low_price=None,
    close_price=None,
    change_pct=None,
):
    open_price = _safe_float(open_price)
    high_price = _safe_float(high_price)
    low_price = _safe_float(low_price)
    close_price = _safe_float(close_price)
    change_pct = _safe_float(change_pct)

    if min(open_price, high_price, low_price, close_price) <= 0:
        return False

    tolerance = max(close_price * 0.001, 0.01)
    flat_line = (
        abs(open_price - close_price) <= tolerance
        and abs(open_price - high_price) <= tolerance
        and abs(open_price - low_price) <= tolerance
    )
    limit_up_pct = _get_limit_up_pct(stock_code, stock_name) * 100
    return flat_line and change_pct >= limit_up_pct


def _compute_bar_change_pct_legacy_body(current_bar, prev_bar=None):
    current_close = _safe_float((current_bar or {}).get("close"))
    prev_close = _safe_float((prev_bar or {}).get("close"))
    if current_close <= 0 or prev_close <= 0:
        return 0.0
    return (current_close / prev_close - 1.0) * 100.0


def _evaluate_live_tradability_legacy_body(stock, target_date="", recent_bars=None):
    stock = stock or {}
    code = normalize_stock_code(stock.get("code", ""))
    name = stock.get("name", "")
    recent_bars = list(recent_bars or [])
    normalized_target_date = _normalize_kline_date_str(target_date)

    sorted_bars = sorted(
        [bar for bar in recent_bars if bar.get("date")],
        key=lambda item: _normalize_kline_date_str(item.get("date")),
    )
    if normalized_target_date:
        sorted_bars = [
            bar for bar in sorted_bars
            if _normalize_kline_date_str(bar.get("date")) <= normalized_target_date
        ]

    report_bar = sorted_bars[-1] if sorted_bars else {}
    prev_bar = sorted_bars[-2] if len(sorted_bars) >= 2 else {}
    prev_prev_bar = sorted_bars[-3] if len(sorted_bars) >= 3 else {}

    report_change = stock.get("change")
    if report_change is None and report_bar:
        report_change = _compute_bar_change_pct(report_bar, prev_bar)

    report_day_is_one_word = _is_one_word_limit_bar(
        stock_code=code,
        stock_name=name,
        open_price=stock.get("open", report_bar.get("open")),
        high_price=stock.get("high", report_bar.get("high")),
        low_price=stock.get("low", report_bar.get("low")),
        close_price=stock.get("close", stock.get("price", report_bar.get("close"))),
        change_pct=report_change,
    )
    prev_day_is_one_word = False
    if prev_bar:
        prev_day_is_one_word = _is_one_word_limit_bar(
            stock_code=code,
            stock_name=name,
            open_price=prev_bar.get("open"),
            high_price=prev_bar.get("high"),
            low_price=prev_bar.get("low"),
            close_price=prev_bar.get("close"),
            change_pct=_compute_bar_change_pct(prev_bar, prev_prev_bar),
        )

    if report_day_is_one_word and prev_day_is_one_word:
        status = "invalid_consecutive_one_word"
        reason = "连续一字，默认买不进去，只记强势观察，不计正式执行。"
    elif report_day_is_one_word:
        status = "invalid_report_day_one_word"
        reason = "当日一字，次日默认买不进去，只保留观察/记忆。"
    else:
        status = "tradeable"
        reason = "当前至少具备基本交易可达性。"

    return {
        "can_trade": status == "tradeable",
        "status": status,
        "status_label": _get_strategy_status_label(status) if status != "tradeable" else "可交易",
        "reason": reason,
        "report_day_is_one_word": bool(report_day_is_one_word),
        "prev_day_is_one_word": bool(prev_day_is_one_word),
    }


def _fetch_recent_price_bars_legacy_body(security_code, target_date, lookback_days=10, fast_fail=False):
    code = normalize_stock_code(security_code)
    normalized_target_date = _normalize_kline_date_str(target_date)
    if not code or not normalized_target_date or fast_fail:
        return []

    target_dt = _parse_kline_date(normalized_target_date)
    if target_dt is None:
        return []

    lookback_days = int(_safe_float(lookback_days, 10))
    history_span = max(lookback_days * 2, 10)
    start_date = (target_dt - datetime.timedelta(days=history_span)).strftime("%Y-%m-%d")

    bars = fetch_daily_price_bars(
        code,
        start_date,
        normalized_target_date,
        prefer_fast=True,
        allow_baostock_fallback=True,
        helpers={"fetch_recent_price_bars": lambda *args, **kwargs: []},
    )
    trimmed = _trim_bars_to_target_date(bars or [], normalized_target_date)
    if lookback_days > 0 and len(trimmed) > lookback_days:
        return trimmed[-lookback_days:]
    return trimmed


def _compute_trend_article_stop_loss_legacy_body(bars):
    if not bars:
        return None, None, ""

    sorted_bars = sorted(bars, key=lambda x: str(x.get("date", "")))
    for idx in range(len(sorted_bars) - 1, -1, -1):
        bar = sorted_bars[idx]
        open_price = _safe_float(bar.get("open"))
        close_price = _safe_float(bar.get("close"))
        if open_price > 0 and close_price > 0 and close_price < open_price:
            low_price = _safe_float(bar.get("low"))
            if low_price > 0:
                return round(low_price, 2), bar.get("date"), "最近阴线最低价，跌破=大本营失守/模式失效，直接卖"

    if len(sorted_bars) >= 2:
        prev_bar = sorted_bars[-2]
        low_price = _safe_float(prev_bar.get("low"))
        if low_price > 0:
            return round(low_price, 2), prev_bar.get("date"), "窗口内无阴线，用前一交易日最低价，跌破即卖"

    last_bar = sorted_bars[-1]
    low_price = _safe_float(last_bar.get("low"))
    if low_price > 0:
        return round(low_price, 2), last_bar.get("date"), "仅最近一日数据，用该日最低价，跌破即卖"
    return None, None, ""


def _compute_stop_loss_mainline_anchor_legacy_body(bars, window=None):
    if window is None:
        window = STOP_PRIOR_LOW_TRADING_DAYS
    if not bars:
        return None, None, ""

    sorted_bars = sorted(bars, key=lambda x: str(x.get("date", "")))
    window_bars = sorted_bars[-window:] if len(sorted_bars) > window else sorted_bars
    best_low = None
    best_bar = None
    for bar in window_bars:
        low_price = _safe_float(bar.get("low"))
        if low_price <= 0:
            continue
        if best_low is None or low_price < best_low:
            best_low = low_price
            best_bar = bar
        elif abs(low_price - best_low) < 1e-9:
            best_bar = bar

    if best_low is None or not best_bar:
        return compute_trend_article_stop_loss(window_bars)

    hint = (
        f"近{len(window_bars)}个交易日最低价（与3~5日观察期同尺度前低）；跌破直接卖。"
        "买入侧看放量异常；持有仅3~5日观察，不及预期也卖；大阳线为理想主动卖点"
    )
    return round(best_low, 2), best_bar.get("date"), hint


def _resolve_daily_price_anchor_legacy_body(security_code, target_date, recent_bars=None, window=None):
    if window is None:
        window = STOP_PRIOR_LOW_TRADING_DAYS

    bars = recent_bars
    if bars is None and security_code:
        bars = fetch_recent_price_bars(
            security_code,
            target_date,
            lookback_days=max(window + 5, 10),
        )
    bars = _trim_bars_to_target_date(bars or [], target_date)

    stop_loss, anchor_date, rule_hint = compute_stop_loss_mainline_anchor(bars or [], window=window)
    if stop_loss is None or stop_loss <= 0:
        return {"stop": None, "anchor_date": "", "hint": ""}

    return {
        "stop": round(stop_loss, 2),
        "anchor_date": anchor_date or "",
        "hint": rule_hint or "",
    }


def _attach_daily_price_anchor_legacy_body(stop_plan, daily_anchor):
    if not stop_plan:
        return stop_plan

    enriched = dict(stop_plan)
    daily_anchor = daily_anchor or {}
    daily_stop = _safe_float(daily_anchor.get("stop"))
    if daily_stop > 0:
        enriched["daily_anchor_stop"] = round(daily_stop, 2)
        enriched["daily_anchor_date"] = daily_anchor.get("anchor_date", "") or ""
        enriched["daily_anchor_hint"] = daily_anchor.get("hint", "") or ""
    return enriched


def _resolve_big_yang_confluence_anchor_legacy_body(recent_bars, target_date="", window=6):
    bars = _trim_bars_to_target_date(recent_bars or [], target_date)
    if not bars:
        return {}

    sorted_bars = sorted(bars, key=lambda x: str(x.get("date", "")))
    start_idx = max(0, len(sorted_bars) - max(int(window or 0), 1))
    candidate = None

    for idx in range(start_idx, len(sorted_bars)):
        bar = sorted_bars[idx]
        open_price = _safe_float(bar.get("open"))
        high_price = _safe_float(bar.get("high"))
        low_price = _safe_float(bar.get("low"))
        close_price = _safe_float(bar.get("close"))
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue
        if close_price <= open_price:
            continue

        prev_close = _safe_float(sorted_bars[idx - 1].get("close")) if idx > 0 else 0.0
        if prev_close > 0:
            change_pct = ((close_price / prev_close) - 1) * 100
        else:
            change_pct = ((close_price / open_price) - 1) * 100

        full_range = max(high_price - low_price, 0.0)
        body_ratio = (close_price - open_price) / full_range if full_range > 0 else 0.0
        close_near_high = high_price > 0 and (high_price - close_price) <= max(high_price * 0.01, 0.05)
        is_key_big_yang = change_pct >= 5.0 and body_ratio >= 0.45 and close_near_high
        is_limit_like = change_pct >= 9.5 and close_near_high
        if not is_key_big_yang and not is_limit_like:
            continue

        candidate = {
            "open_anchor": round(open_price, 2),
            "limit_anchor": round(close_price, 2) if is_limit_like else None,
            "date": bar.get("date", ""),
            "change_pct": round(change_pct, 2),
        }

    return candidate or {}


def _attach_breakout_confluence_anchor_legacy_body(stop_plan, breakout_anchor):
    if not stop_plan:
        return stop_plan

    enriched = dict(stop_plan)
    breakout_anchor = breakout_anchor or {}
    open_anchor = _safe_float(breakout_anchor.get("open_anchor"))
    limit_anchor = _safe_float(breakout_anchor.get("limit_anchor"))
    if open_anchor > 0:
        enriched["breakout_open_anchor"] = round(open_anchor, 2)
    if limit_anchor > 0:
        enriched["breakout_limit_anchor"] = round(limit_anchor, 2)
    if breakout_anchor.get("date"):
        enriched["breakout_anchor_date"] = breakout_anchor.get("date", "")
    return enriched


def _enrich_stop_plan_with_reference_anchors_legacy_body(stop_plan, security_code, target_date, recent_bars=None):
    if not stop_plan:
        return stop_plan

    bars = _trim_bars_to_target_date(recent_bars or [], target_date)
    if not bars and security_code:
        bars = fetch_recent_price_bars(
            security_code,
            target_date,
            lookback_days=max(STOP_PRIOR_LOW_TRADING_DAYS + 5, 10),
        )
        bars = _trim_bars_to_target_date(bars or [], target_date)

    enriched = _attach_daily_price_anchor_legacy_body(
        stop_plan,
        _resolve_daily_price_anchor_legacy_body(security_code, target_date, recent_bars=bars),
    )
    return _attach_breakout_confluence_anchor_legacy_body(
        enriched,
        resolve_big_yang_confluence_anchor(bars, target_date=target_date),
    )


def _trim_bars_to_target_date_legacy_body(bars, target_date):
    target_norm = _normalize_kline_date_str(target_date)
    if not bars:
        return []

    trimmed = []
    for bar in bars:
        date_text = _normalize_kline_date_str(bar.get("date") or bar.get("datetime") or "")
        if target_norm and date_text and date_text > target_norm:
            continue
        normalized = dict(bar)
        if date_text:
            normalized["date"] = date_text
        trimmed.append(normalized)
    return sorted(trimmed, key=lambda x: str(x.get("date", "")))
