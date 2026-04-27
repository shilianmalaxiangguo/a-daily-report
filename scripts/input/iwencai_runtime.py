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


class IwencaiSkillVersionError(RuntimeError):
    """Raised when OpenAPI rejects the locally installed SkillHub/skill version."""


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


def _is_live_rank_target_date(target_date=None):
    if target_date is None:
        return True
    try:
        return _resolve_query_date(target_date).date() == datetime.datetime.now().date()
    except Exception:
        return False


def _post_iwencai_query(query, limit="10", *, api_key=None, urlopen_fn=None):
    import urllib.error
    import urllib.request

    api_key = api_key if api_key is not None else os.environ.get("IWENCAI_API_KEY")
    if not api_key:
        return None

    urlopen_fn = urlopen_fn or urllib.request.urlopen
    base_url = (os.environ.get("IWENCAI_BASE_URL") or "https://openapi.iwencai.com").rstrip("/")
    url = f"{base_url}/v1/query2data"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "page": "1",
        "limit": str(limit),
        "is_cache": "1",
        "expand_index": "true",
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        response = urlopen_fn(request, timeout=30)
        return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = ""
        try:
            body = error.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        if error.code == 401 and "Skill 版本过低" in body:
            raise IwencaiSkillVersionError(body or str(error)) from error
        raise


def _load_akshare():
    try:
        import akshare as ak

        return ak
    except Exception:
        return None


def _latest_index_row(symbol, target_date=None, *, stock_zh_index_daily_em_fn=None):
    query_date = _resolve_query_date(target_date)
    end_date = query_date.strftime("%Y-%m-%d")
    if stock_zh_index_daily_em_fn is None:
        ak = _load_akshare()
        if ak is None or not hasattr(ak, "stock_zh_index_daily_em"):
            return None, None
        stock_zh_index_daily_em_fn = ak.stock_zh_index_daily_em

    df = stock_zh_index_daily_em_fn(symbol=symbol)
    if df is None or getattr(df, "empty", False):
        return None, None
    df = df.copy()
    if "date" not in df:
        return None, None
    df["date"] = df["date"].astype(str)
    eligible = df[df["date"] <= end_date]
    if eligible.empty:
        return None, None
    row = eligible.iloc[-1]
    prev = eligible.iloc[-2] if len(eligible) >= 2 else None
    return row, prev


def _row_float(row, *keys):
    if row is None:
        return 0.0
    for key in keys:
        value = row.get(key) if hasattr(row, "get") else None
        if value not in (None, ""):
            return _safe_float(value)
    return 0.0


def _row_text(row, *keys):
    if row is None:
        return ""
    for key in keys:
        value = row.get(key) if hasattr(row, "get") else None
        if value not in (None, ""):
            return str(value)
    return ""


def _compute_change_pct(row, prev):
    direct = _row_float(row, "涨跌幅", "change_pct")
    if direct:
        return direct
    close_price = _row_float(row, "close", "收盘", "收盘价")
    prev_close = _row_float(prev, "close", "收盘", "收盘价")
    open_price = _row_float(row, "open", "开盘", "开盘价")
    if prev_close > 0:
        return (close_price - prev_close) / prev_close * 100
    if open_price > 0:
        return (close_price - open_price) / open_price * 100
    return 0.0


def _build_major_index_akshare_fallback(target_date=None, *, print_fn=print):
    index_map = {
        "上证指数": ("sh000001", "000001"),
        "深证成指": ("sz399001", "399001"),
        "创业板指": ("sz399006", "399006"),
    }
    indices = {}
    try:
        for name, (symbol, code) in index_map.items():
            row, prev = _latest_index_row(symbol, target_date)
            if row is None:
                continue
            close_price = _row_float(row, "close", "收盘", "收盘价")
            indices[name] = {
                "name": name,
                "code": code,
                "price": close_price,
                "open": _row_float(row, "open", "开盘", "开盘价"),
                "close": close_price,
                "high": _row_float(row, "high", "最高", "最高价"),
                "low": _row_float(row, "low", "最低", "最低价"),
                "change_pct": _compute_change_pct(row, prev),
                "turnover": _row_float(row, "amount", "成交额") / 1e8,
                "涨跌幅": _compute_change_pct(row, prev),
                "data_source": "akshare.stock_zh_index_daily_em",
                "trade_date": _row_text(row, "date"),
            }
        if indices:
            print_fn(f"ℹ️ 主要指数已切换到 AkShare 回补，共获取{len(indices)}个指数")
        return indices
    except Exception as error:
        print_fn(f"⚠️ 主要指数 AkShare 回补失败: {error}")
        return {}


def _get_total_turnover_akshare_fallback(target_date=None, *, print_fn=print):
    try:
        total = 0.0
        for symbol in ("sh000001", "sz399001"):
            row, _ = _latest_index_row(symbol, target_date)
            if row is not None:
                total += _row_float(row, "amount", "成交额") / 1e8
        if total > 0:
            print_fn(f"ℹ️ 两市成交额已使用 AkShare 指数成交额: {total:.2f}亿元")
        return total
    except Exception as error:
        print_fn(f"⚠️ 两市成交额 AkShare 回补失败: {error}")
        return 0.0


def _get_wind_a_akshare_fallback(target_date=None, *, print_fn=print):
    try:
        row, prev = _latest_index_row("sh000985", target_date)
        if row is None:
            return {"price": 0, "change_pct": 0}
        return {
            "price": _row_float(row, "close", "收盘", "收盘价"),
            "change_pct": _compute_change_pct(row, prev),
            "data_source": "akshare.stock_zh_index_daily_em",
            "trade_date": _row_text(row, "date"),
        }
    except Exception as error:
        print_fn(f"⚠️ 中证全指 AkShare 回补失败: {error}")
        return {"price": 0, "change_pct": 0}


def _get_sector_change_akshare_fallback(rank_type="up", limit=10, *, print_fn=print):
    try:
        ak = _load_akshare()
        if ak is None or not hasattr(ak, "stock_board_industry_name_em"):
            return []
        df = ak.stock_board_industry_name_em()
        if df is None or getattr(df, "empty", False):
            return []
        rows = []
        for _, item in df.iterrows():
            name = _row_text(item, "板块名称", "名称", "行业名称")
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "change_pct": _row_float(item, "涨跌幅", "最新涨跌幅"),
                    "data_source": "akshare.stock_board_industry_name_em",
                }
            )
        rows.sort(key=lambda item: item.get("change_pct", 0), reverse=(rank_type != "down"))
        return rows[: int(limit or 10)]
    except Exception as error:
        print_fn(f"⚠️ 板块涨跌幅 AkShare 回补失败: {error}")
        return []


def _extract_json_response(response):
    body = response.read()
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    return json.loads(body)


def _get_sector_change_tencent_primary(rank_type="up", limit=10, *, urlopen_fn=None, print_fn=print):
    import urllib.request

    urlopen_fn = urlopen_fn or urllib.request.urlopen
    url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/fundflow/Fundflow/getHyRank?t=zljlr&o=1"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://stockapp.finance.qq.com/",
        },
        method="GET",
    )
    try:
        result = _extract_json_response(urlopen_fn(request, timeout=30))
        data = result.get("data", {})
        records = data.get("data", data if isinstance(data, list) else [])
        if not isinstance(records, list):
            return []

        rows = []
        for item in records:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            leader = item.get("lzg") or {}
            if not isinstance(leader, dict):
                leader = {}
            rows.append(
                {
                    "name": name,
                    "change_pct": _safe_float(item.get("zdf") or item.get("change_pct")),
                    "turnover": _safe_float(item.get("cje") or item.get("turnover")) / 10000,
                    "leader_stock": str(leader.get("name") or item.get("leader_stock") or "").strip(),
                    "data_source": "tencent.fundflow.getHyRank",
                }
            )

        rows.sort(key=lambda item: item.get("change_pct", 0.0), reverse=(rank_type != "down"))
        if rows:
            print_fn(f"ℹ️ 板块涨跌幅已使用腾讯行业资金流排行，共获取{min(len(rows), int(limit or 10))}条")
        return rows[: int(limit or 10)]
    except Exception as error:
        print_fn(f"⚠️ 腾讯行业资金流排行获取失败: {error}")
        return []


def _get_turnover_rank_akshare_fallback(limit=50, *, print_fn=print):
    try:
        ak = _load_akshare()
        if ak is None or not hasattr(ak, "stock_zh_a_spot_em"):
            return []
        df = ak.stock_zh_a_spot_em()
        if df is None or getattr(df, "empty", False):
            return []
        rows = []
        for _, item in df.iterrows():
            code = _row_text(item, "代码", "股票代码")
            name = _row_text(item, "名称", "股票简称")
            if not code or not name:
                continue
            rows.append(
                {
                    "code": code.replace(".SZ", "").replace(".SH", "").replace(".BJ", ""),
                    "name": name,
                    "turnover": _row_float(item, "成交额", "amount") / 1e8,
                    "change_pct": _row_float(item, "涨跌幅", "change_pct"),
                    "sector": _row_text(item, "所属行业", "行业", "板块") or "未知",
                    "data_source": "akshare.stock_zh_a_spot_em",
                }
            )
        rows.sort(key=lambda item: item.get("turnover", 0), reverse=True)
        return rows[: int(limit or 50)]
    except Exception as error:
        print_fn(f"⚠️ 成交额排名 AkShare 回补失败: {error}")
        return []


def _get_turnover_rank_eastmoney_primary(limit=50, *, urlopen_fn=None, print_fn=print):
    import urllib.request

    urlopen_fn = urlopen_fn or urllib.request.urlopen
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?pn=1&pz={limit}&po=1&np=1&fid=f6"
        "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
        "&fields=f12,f14,f6,f3,f2,f100"
    ).format(limit=int(limit or 50))
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
        method="GET",
    )
    try:
        result = _extract_json_response(urlopen_fn(request, timeout=30))
        records = (result.get("data") or {}).get("diff") or []
        rows = []
        for item in records:
            if not isinstance(item, dict):
                continue
            code = str(item.get("f12") or "").strip()
            name = str(item.get("f14") or "").strip()
            if not code or not name:
                continue
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "turnover": _safe_float(item.get("f6")) / 1e8,
                    "change_pct": _safe_float(item.get("f3")) / 100,
                    "sector": str(item.get("f100") or "未知").strip() or "未知",
                    "data_source": "eastmoney.push2.clist",
                }
            )
        if rows:
            print_fn(f"ℹ️ 成交额排行已使用东方财富实时排行，共获取{len(rows)}条")
        return rows
    except Exception as error:
        print_fn(f"⚠️ 东方财富成交额排行获取失败: {error}")
        return []


def get_sector_change_from_iwencai(
    rank_type="up",
    limit=10,
    target_date=None,
    *,
    api_key=None,
    urlopen_fn=None,
    tencent_urlopen_fn=None,
    print_fn=print,
):
    """
    获取板块涨跌幅排行 - 优先使用腾讯行业资金流，必要时回退到问财/AkShare。
    """
    if _is_live_rank_target_date(target_date):
        primary_rows = _get_sector_change_tencent_primary(
            rank_type=rank_type,
            limit=limit,
            urlopen_fn=tencent_urlopen_fn if tencent_urlopen_fn is not None else urlopen_fn,
            print_fn=print_fn,
        )
        if primary_rows:
            return primary_rows

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
            print_fn("[问财API] 未设置IWENCAI_API_KEY，切换到 AkShare 板块涨跌幅回补")
            return _get_sector_change_akshare_fallback(rank_type=rank_type, limit=limit, print_fn=print_fn)

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
                        "data_source": "iwencai.query2data",
                    }
                )
            if sector_rows:
                return sector_rows

        print_fn(f"[问财API] 板块涨跌幅查询失败: {result.get('status_msg', 'unknown error')}，切换到 AkShare 回补")
        return _get_sector_change_akshare_fallback(rank_type=rank_type, limit=limit, print_fn=print_fn)
    except IwencaiSkillVersionError as error:
        print_fn(f"[问财API] {error}，切换到 AkShare 板块涨跌幅回补")
        return _get_sector_change_akshare_fallback(rank_type=rank_type, limit=limit, print_fn=print_fn)
    except Exception as error:
        print_fn(f"[问财API] 板块涨跌幅查询异常: {error}，切换到 AkShare 回补")
        return _get_sector_change_akshare_fallback(rank_type=rank_type, limit=limit, print_fn=print_fn)


def get_turnover_rank_from_iwencai(
    limit=50,
    target_date=None,
    *,
    api_key=None,
    urlopen_fn=None,
    eastmoney_urlopen_fn=None,
    print_fn=print,
):
    """获取成交额排名 - 优先使用东方财富，必要时回退到问财/AkShare。"""
    if _is_live_rank_target_date(target_date):
        primary_rows = _get_turnover_rank_eastmoney_primary(
            limit=limit,
            urlopen_fn=eastmoney_urlopen_fn if eastmoney_urlopen_fn is not None else urlopen_fn,
            print_fn=print_fn,
        )
        if primary_rows:
            return primary_rows

    try:
        query_date = _resolve_query_date(target_date)
        date_str = query_date.strftime("%Y-%m-%d")
        date_compact = query_date.strftime("%Y%m%d")
        query = f"{date_str}成交额前{limit}的股票，包括股票代码、股票简称、成交额、涨跌幅、所属行业"

        result = _post_iwencai_query(query, limit=limit, api_key=api_key, urlopen_fn=urlopen_fn)
        if result is None:
            print_fn("⚠️ 未设置IWENCAI_API_KEY，切换到 AkShare 成交额排名回补")
            return _get_turnover_rank_akshare_fallback(limit=limit, print_fn=print_fn)

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
                    "data_source": "iwencai.query2data",
                }
            )
        if turnover_rank:
            return turnover_rank
        print_fn("⚠️ 问财成交额排名返回空，切换到 AkShare 成交额排名回补")
        return _get_turnover_rank_akshare_fallback(limit=limit, print_fn=print_fn)
    except IwencaiSkillVersionError as error:
        print_fn(f"⚠️ {error}，切换到 AkShare 成交额排名回补")
        return _get_turnover_rank_akshare_fallback(limit=limit, print_fn=print_fn)
    except Exception as error:
        print_fn(f"⚠️ iwencai成交额排名获取失败: {error}，切换到 AkShare 成交额排名回补")
        return _get_turnover_rank_akshare_fallback(limit=limit, print_fn=print_fn)


def get_total_turnover_from_iwencai(target_date=None, *, api_key=None, urlopen_fn=None, print_fn=print):
    """获取两市成交额 - 优先使用 AkShare 指数成交额，必要时回退到问财。"""
    akshare_total = _get_total_turnover_akshare_fallback(target_date, print_fn=print_fn)
    if akshare_total > 0:
        return akshare_total

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
    except IwencaiSkillVersionError as error:
        print_fn(f"⚠️ {error}，切换到 AkShare 两市成交额回补")
        return _get_total_turnover_akshare_fallback(target_date, print_fn=print_fn)
    except Exception as error:
        print_fn(f"⚠️ iwencai两市成交额获取失败: {error}")
        import traceback

        traceback.print_exc()
        return _get_total_turnover_akshare_fallback(target_date, print_fn=print_fn)


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
    """获取主要指数 - 优先使用 AkShare 指数日线，必要时回退到问财/历史K线。"""
    akshare_indices = _build_major_index_akshare_fallback(target_date, print_fn=print_fn)
    if len(akshare_indices) >= 3:
        return akshare_indices

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
                "data_source": "iwencai.query2data",
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
    except IwencaiSkillVersionError as error:
        print_fn(f"⚠️ {error}，切换到 AkShare 主要指数回补")
        indices = _build_major_index_akshare_fallback(target_date, print_fn=print_fn)
        if indices:
            return indices
        return _build_major_index_bar_fallback(
            target_date,
            fetch_daily_price_bars_fn=fetch_daily_price_bars_fn,
            print_fn=print_fn,
        )
    except Exception as error:
        print_fn(f"⚠️ iwencai主要指数获取失败: {error}")
        import traceback

        traceback.print_exc()
        indices = _build_major_index_akshare_fallback(target_date, print_fn=print_fn)
        if indices:
            return indices
        return _build_major_index_bar_fallback(
            target_date,
            fetch_daily_price_bars_fn=fetch_daily_price_bars_fn,
            print_fn=print_fn,
        )


def get_wind_a_from_iwencai(target_date=None, *, api_key=None, urlopen_fn=None, print_fn=print):
    """获取中证全指 - 优先使用 AkShare 指数日线，必要时回退到问财。"""
    akshare_wind_a = _get_wind_a_akshare_fallback(target_date, print_fn=print_fn)
    if _safe_float(akshare_wind_a.get("price")) > 0:
        return akshare_wind_a

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
                "data_source": "iwencai.query2data",
            }
        return {"price": 0, "change_pct": 0}
    except IwencaiSkillVersionError as error:
        print_fn(f"⚠️ {error}，切换到 AkShare 中证全指回补")
        return _get_wind_a_akshare_fallback(target_date, print_fn=print_fn)
    except Exception as error:
        print_fn(f"⚠️ iwencai中证全指获取失败: {error}")
        import traceback

        traceback.print_exc()
        return _get_wind_a_akshare_fallback(target_date, print_fn=print_fn)


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
