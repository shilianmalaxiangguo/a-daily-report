from __future__ import annotations

import datetime
import json
import os

import daily_report_analysis_utils as analysis_utils
from market_data.kline_dates import normalize_kline_date_str, parse_kline_date

__all__ = [
    "get_major_indices_from_iwencai",
    "get_sector_change_from_iwencai",
    "get_sector_quadrant_data",
    "get_total_turnover_from_iwencai",
    "get_turnover_rank_from_iwencai",
    "get_wind_a_from_iwencai",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


_daily_price_bar_cache = {}
_baostock_runtime_state = {
    "logged_in": False,
    "logout_registered": False,
}


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


def _resolve_query_date(target_date=None):
    if target_date:
        if isinstance(target_date, str):
            return datetime.datetime.strptime(target_date, "%Y-%m-%d")
        return target_date
    return datetime.datetime.now()


def _post_iwencai_query(query, limit="10", *, api_key=None, urlopen_fn=None):
    import urllib.request

    api_key = api_key if api_key is not None else os.environ.get("IWENCAI_API_KEY")
    if not api_key:
        return None

    urlopen_fn = urlopen_fn or urllib.request.urlopen
    url = "https://openapi.iwencai.com/v1/query2data"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "page": "1",
        "limit": str(limit),
        "is_cache": "1",
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    response = urlopen_fn(request, timeout=30)
    return json.loads(response.read().decode("utf-8"))


def get_sector_change_from_iwencai(rank_type="up", limit=10, target_date=None, *, api_key=None, urlopen_fn=None, print_fn=print):
    """
    获取板块涨跌幅排行 - 使用同花顺问财API。
    """
    try:
        query_date = _resolve_query_date(target_date)
        date_str = query_date.strftime("%Y-%m-%d")
        if rank_type == "down":
            query = f"{date_str}跌幅前{limit}的板块，包含板块名称、涨跌幅"
        else:
            query = f"{date_str}涨幅前{limit}的板块，包含板块名称、涨跌幅"
        date_compact = query_date.strftime("%Y%m%d")

        result = _post_iwencai_query(query, limit=limit, api_key=api_key, urlopen_fn=urlopen_fn)
        if result is None:
            print_fn("[问财API] 未设置IWENCAI_API_KEY，返回空数据")
            return []

        if result.get("status_code", 0) == 0 and result.get("datas"):
            sector_rows = []
            for item in result["datas"]:
                sector_name = item.get("指数简称") or item.get("板块名称") or item.get("概念名称") or ""
                if not sector_name:
                    continue
                sector_rows.append(
                    {
                        "name": sector_name,
                        "change_pct": _safe_float(
                            item.get(f"涨跌幅[{date_compact}]")
                            or item.get("涨跌幅")
                            or item.get("最新涨跌幅")
                        ),
                    }
                )
            return sector_rows

        print_fn(f"[问财API] 板块涨跌幅查询失败: {result.get('status_msg', 'unknown error')}")
        return []
    except Exception as error:
        print_fn(f"[问财API] 板块涨跌幅查询异常: {error}")
        return []


def get_turnover_rank_from_iwencai(limit=50, target_date=None, *, api_key=None, urlopen_fn=None, print_fn=print):
    """获取成交额排名 - 使用同花顺问财API。"""
    try:
        query_date = _resolve_query_date(target_date)
        date_str = query_date.strftime("%Y-%m-%d")
        date_compact = query_date.strftime("%Y%m%d")
        query = f"{date_str}成交额前{limit}的股票，包括股票代码、股票简称、成交额、涨跌幅、所属行业"

        result = _post_iwencai_query(query, limit=limit, api_key=api_key, urlopen_fn=urlopen_fn)
        if result is None:
            print_fn("⚠️ 未设置IWENCAI_API_KEY，返回空数据")
            return []

        turnover_rank = []
        for item in result.get("datas") or []:
            industry_list = item.get("所属同花顺行业", [])
            sector = industry_list[0] if industry_list else "未知"
            turnover_rank.append(
                {
                    "code": str(item.get("股票代码", "")).replace(".SZ", "").replace(".SH", "").replace(".BJ", ""),
                    "name": item.get("股票简称", ""),
                    "turnover": _safe_float(item.get(f"成交额[{date_compact}]")) / 1e8,
                    "change_pct": _safe_float(item.get(f"涨跌幅[{date_compact}]")),
                    "sector": sector,
                }
            )
        return turnover_rank
    except Exception as error:
        print_fn(f"⚠️ iwencai成交额排名获取失败: {error}")
        import traceback

        traceback.print_exc()
        return []


def get_total_turnover_from_iwencai(target_date=None, *, api_key=None, urlopen_fn=None, print_fn=print):
    """获取两市成交额 - 使用同花顺问财API。"""
    try:
        query_date = _resolve_query_date(target_date)
        date_str = query_date.strftime("%Y-%m-%d")
        date_compact = query_date.strftime("%Y%m%d")
        query = f"{date_str}两市成交额"

        result = _post_iwencai_query(query, limit="10", api_key=api_key, urlopen_fn=urlopen_fn)
        if result is None:
            print_fn("⚠️ 未设置IWENCAI_API_KEY，返回0")
            return 0.0

        total_turnover = 0.0
        for item in result.get("datas") or []:
            total_turnover += _safe_float(item.get(f"成交额[{date_compact}]")) / 1e8
        return total_turnover
    except Exception as error:
        print_fn(f"⚠️ iwencai两市成交额获取失败: {error}")
        import traceback

        traceback.print_exc()
        return 0.0


def _default_fetch_daily_price_bars(code, start_date, end_date, *, is_index=False):
    from market_data.daily_price_runtime import fetch_daily_price_bars

    return fetch_daily_price_bars(
        code,
        start_date,
        end_date,
        is_index=is_index,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "_safe_float": _safe_float,
            "_normalize_kline_date_str": normalize_kline_date_str,
            "_parse_kline_date": parse_kline_date,
            "_daily_price_bar_cache": _daily_price_bar_cache,
            "_ensure_baostock_login": _ensure_baostock_login,
            "_logout_baostock_silently": _logout_baostock_silently,
        },
    )


def _build_major_index_bar_fallback(target_date=None, *, fetch_daily_price_bars_fn=None, print_fn=print):
    try:
        query_date = _resolve_query_date(target_date)
        end_date = query_date.strftime("%Y-%m-%d")
        start_date = (query_date - datetime.timedelta(days=15)).strftime("%Y-%m-%d")
        index_map = {
            "上证指数": "000001",
            "深证成指": "399001",
            "创业板指": "399006",
        }
        fetch_daily_price_bars_fn = fetch_daily_price_bars_fn or _default_fetch_daily_price_bars
        indices = {}

        for name, code in index_map.items():
            bars = fetch_daily_price_bars_fn(code, start_date, end_date, is_index=True)
            valid_bars = [
                bar for bar in (bars or [])
                if normalize_kline_date_str(bar.get("date")) <= end_date
            ]
            if not valid_bars:
                continue

            latest_bar = valid_bars[-1]
            prev_close = _safe_float(valid_bars[-2].get("close")) if len(valid_bars) >= 2 else 0.0
            close_price = _safe_float(latest_bar.get("close"))
            open_price = _safe_float(latest_bar.get("open"))
            if prev_close > 0:
                change_pct = (close_price - prev_close) / prev_close * 100
            elif open_price > 0:
                change_pct = (close_price - open_price) / open_price * 100
            else:
                change_pct = 0.0

            indices[name] = {
                "name": name,
                "code": code,
                "price": close_price,
                "open": open_price,
                "close": close_price,
                "high": _safe_float(latest_bar.get("high")),
                "low": _safe_float(latest_bar.get("low")),
                "change_pct": change_pct,
                "turnover": 0.0,
                "涨跌幅": change_pct,
                "data_source": "price_bar_fallback",
                "trade_date": normalize_kline_date_str(latest_bar.get("date")),
            }

        if indices:
            print_fn(f"ℹ️ 主要指数已切换到历史K线回补，共获取{len(indices)}个指数")
        return indices
    except Exception as error:
        print_fn(f"⚠️ 主要指数历史K线回补失败: {error}")
        return {}


def get_major_indices_from_iwencai(
    target_date=None,
    *,
    api_key=None,
    urlopen_fn=None,
    fetch_daily_price_bars_fn=None,
    print_fn=print,
):
    """获取主要指数 - 使用同花顺问财API，必要时回退到历史K线。"""
    try:
        query_date = _resolve_query_date(target_date)
        date_str = query_date.strftime("%Y-%m-%d")
        date_compact = query_date.strftime("%Y%m%d")
        query = f"{date_str}上证指数、深证成指、创业板指的开盘价、收盘价、最高价、最低价、涨跌幅、成交额"

        result = _post_iwencai_query(query, limit="10", api_key=api_key, urlopen_fn=urlopen_fn)
        if result is None:
            print_fn("⚠️ 未设置IWENCAI_API_KEY，切换到历史K线回补")
            return _build_major_index_bar_fallback(
                target_date,
                fetch_daily_price_bars_fn=fetch_daily_price_bars_fn,
                print_fn=print_fn,
            )

        indices = {}
        for item in result.get("datas") or []:
            name = item.get("指数简称", "")
            if not name:
                continue
            close_price = _safe_float(item.get(f"收盘价[{date_compact}]"))
            indices[name] = {
                "name": name,
                "code": str(item.get("指数代码", "")).replace(".SH", "").replace(".SZ", ""),
                "price": close_price,
                "open": _safe_float(item.get(f"开盘价[{date_compact}]")),
                "close": close_price,
                "high": _safe_float(item.get(f"最高价[{date_compact}]")),
                "low": _safe_float(item.get(f"最低价[{date_compact}]")),
                "change_pct": _safe_float(item.get(f"涨跌幅[{date_compact}]")),
                "turnover": _safe_float(item.get(f"成交额[{date_compact}]")) / 1e8,
                "涨跌幅": _safe_float(item.get(f"涨跌幅[{date_compact}]")),
            }

        if len(indices) < 3:
            fallback_indices = _build_major_index_bar_fallback(
                target_date,
                fetch_daily_price_bars_fn=fetch_daily_price_bars_fn,
                print_fn=print_fn,
            )
            for name, payload in fallback_indices.items():
                indices.setdefault(name, payload)

        return indices
    except Exception as error:
        print_fn(f"⚠️ iwencai主要指数获取失败: {error}")
        import traceback

        traceback.print_exc()
        return _build_major_index_bar_fallback(
            target_date,
            fetch_daily_price_bars_fn=fetch_daily_price_bars_fn,
            print_fn=print_fn,
        )


def get_wind_a_from_iwencai(target_date=None, *, api_key=None, urlopen_fn=None, print_fn=print):
    """获取中证全指 - 使用同花顺问财API。"""
    try:
        query_date = _resolve_query_date(target_date)
        date_str = query_date.strftime("%Y-%m-%d")
        date_compact = query_date.strftime("%Y%m%d")
        query = f"{date_str}中证全指的点位、涨跌幅"

        result = _post_iwencai_query(query, limit="10", api_key=api_key, urlopen_fn=urlopen_fn)
        if result is None:
            print_fn("⚠️ 未设置IWENCAI_API_KEY，返回空数据")
            return {"price": 0, "change_pct": 0}

        if result.get("datas"):
            item = result["datas"][0]
            return {
                "price": _safe_float(item.get(f"收盘价[{date_compact}]")),
                "change_pct": _safe_float(item.get(f"涨跌幅[{date_compact}]")),
            }
        return {"price": 0, "change_pct": 0}
    except Exception as error:
        print_fn(f"⚠️ iwencai中证全指获取失败: {error}")
        import traceback

        traceback.print_exc()
        return {"price": 0, "change_pct": 0}


def get_sector_quadrant_data(period=20, strength_period=3, *, request_get=None, print_fn=print):
    """获取板块四象限数据（击球区分析）。"""
    import requests

    request_get = request_get or requests.get
    try:
        url = (
            "https://stock.quicktiny.cn/api/sector-analysis/quadrant"
            f"?source=dongcai_concept&period={period}&strengthPeriod={strength_period}"
        )
        response = request_get(url, timeout=10)
        if response.status_code != 200:
            print_fn(f"   ⚠️ 板块四象限API返回状态码: {response.status_code}")
            return None

        data = response.json()
        if not data.get("quadrants"):
            print_fn("   ⚠️ 板块四象限数据格式异常")
            return None

        quadrants = data["quadrants"]
        high_strong = quadrants.get("highStrong", [])

        def calculate_quality_score(sector):
            score = 0
            if sector["positionInRange"] >= 90:
                score += 30
            elif sector["positionInRange"] >= 80:
                score += 25
            elif sector["positionInRange"] >= 70:
                score += 15
            else:
                score += 5

            if sector["recentChange"] >= 8:
                score += 40
            elif sector["recentChange"] >= 5:
                score += 30
            elif sector["recentChange"] >= 3:
                score += 20
            else:
                score += 10

            if sector["volumeRatio"] >= 2.0:
                score += 30
            elif sector["volumeRatio"] >= 1.5:
                score += 20
            elif sector["volumeRatio"] >= 1.0:
                score += 10

            return score

        for sector in high_strong:
            sector["quality_score"] = calculate_quality_score(sector)

        tier1 = [s for s in high_strong if s["quality_score"] >= 80]
        tier2 = [s for s in high_strong if 60 <= s["quality_score"] < 80]
        tier3 = [s for s in high_strong if 40 <= s["quality_score"] < 60]
        tier4 = [s for s in high_strong if s["quality_score"] < 40]

        return {
            "quadrants": quadrants,
            "high_strong_analysis": {
                "total": len(high_strong),
                "tier1_best": sorted(tier1, key=lambda x: x["quality_score"], reverse=True),
                "tier2_good": sorted(tier2, key=lambda x: x["quality_score"], reverse=True),
                "tier3_normal": sorted(tier3, key=lambda x: x["quality_score"], reverse=True),
                "tier4_edge": sorted(tier4, key=lambda x: x["quality_score"], reverse=True),
                "tier1_count": len(tier1),
                "tier2_count": len(tier2),
                "tier3_count": len(tier3),
                "tier4_count": len(tier4),
            },
        }
    except Exception as error:
        print_fn(f"   ⚠️ 板块四象限数据获取失败: {error}")
        return None
