from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any, Iterable


CFFEX_PRODUCTS = ("IF", "IH", "IC", "IM")
CFFEX_CONTRACT_MULTIPLIERS = {"IF": 300, "IH": 300, "IC": 200, "IM": 200}
CFFEX_SPOT_INDEX_CODES = {
    "IF": "sh000300",
    "IH": "sh000016",
    "IC": "sh000905",
    "IM": "sh000852",
}
CFFEX_SOURCE_POLICY = "cffex.official.index-futures-position.v1"
CFFEX_BASE_URL = "http://www.cffex.com.cn"

_RANK_TYPE_BY_ID = {"0": "volume", "1": "long", "2": "short"}
_POSITION_RANK_TYPES = ("long", "short")


class CffexDataError(ValueError):
    pass


class CffexSourceError(RuntimeError):
    def __init__(self, message: str, *, url: str = "", status_code: int | None = None):
        super().__init__(message)
        self.url = str(url or "")
        self.status_code = status_code


def normalize_trade_date(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return _dt.date.fromisoformat(text).isoformat()
    except (TypeError, ValueError) as error:
        raise CffexDataError(f"交易日期无效：{value!r}") from error


def cffex_position_rank_url(trade_date: Any, product_code: Any) -> str:
    date_text = normalize_trade_date(trade_date)
    product = _normalize_product_code(product_code)
    compact = date_text.replace("-", "")
    return f"{CFFEX_BASE_URL}/sj/ccpm/{compact[:6]}/{compact[6:]}/{product}.xml"


def cffex_contract_daily_url(trade_date: Any) -> str:
    date_text = normalize_trade_date(trade_date)
    compact = date_text.replace("-", "")
    return f"{CFFEX_BASE_URL}/sj/hqsj/rtj/{compact[:6]}/{compact[6:]}/index.xml"


def content_sha256(raw_bytes: bytes) -> str:
    if not isinstance(raw_bytes, bytes) or not raw_bytes:
        raise CffexDataError("中金所原始文件为空")
    return hashlib.sha256(raw_bytes).hexdigest()


def fetch_cffex_bytes(
    url: str,
    *,
    opener=None,
    timeout_seconds: float = 15,
    max_attempts: int = 3,
    retry_delay_seconds: float = 0.25,
) -> bytes:
    request = urllib.request.Request(
        str(url),
        headers={
            "Accept": "application/xml,text/xml,*/*",
            "User-Agent": "Mozilla/5.0 daily-report-cffex-position-evidence",
        },
    )
    open_fn = opener or urllib.request.urlopen
    attempts = max(int(max_attempts or 1), 1)
    raw_bytes = b""
    for attempt in range(attempts):
        try:
            with open_fn(request, timeout=timeout_seconds) as response:
                raw_bytes = response.read()
            break
        except urllib.error.HTTPError as error:
            raise CffexSourceError(
                f"中金所来源请求失败：{url}；HTTP {error.code}",
                url=url,
                status_code=error.code,
            ) from error
        except Exception as error:
            if attempt + 1 >= attempts:
                raise CffexSourceError(
                    f"中金所来源请求失败：{url}；{error}", url=url
                ) from error
            time.sleep(max(float(retry_delay_seconds or 0), 0.0) * (attempt + 1))
    if not raw_bytes:
        raise CffexSourceError(f"中金所来源返回空文件：{url}", url=url)
    if _is_cffex_not_found_page(raw_bytes):
        raise CffexSourceError(
            f"中金所来源没有该日期文件：{url}",
            url=url,
            status_code=404,
        )
    return raw_bytes


def fetch_tencent_index_daily_bars(
    index_code: Any,
    start_date: Any,
    end_date: Any,
    *,
    opener=None,
    timeout_seconds: float = 15,
) -> list[dict]:
    symbol = str(index_code or "").strip().lower()
    if len(symbol) != 8 or symbol[:2] not in {"sh", "sz"} or not symbol[2:].isdigit():
        raise CffexDataError(f"腾讯指数代码无效：{index_code!r}")
    start = normalize_trade_date(start_date)
    end = normalize_trade_date(end_date)
    if start > end:
        raise CffexDataError(f"指数日线开始日期{start}晚于结束日期{end}")
    calendar_days = (_dt.date.fromisoformat(end) - _dt.date.fromisoformat(start)).days + 1
    query = urllib.parse.urlencode(
        {"param": f"{symbol},day,{start},{end},{max(calendar_days + 20, 40)},qfq"}
    )
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "Mozilla/5.0 daily-report-cffex-spot-history",
        },
    )
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise CffexSourceError(f"腾讯指数日线请求失败：{symbol}；{error}", url=url) from error
    symbol_payload = ((payload or {}).get("data") or {}).get(symbol) or {}
    raw_rows = symbol_payload.get("day") or symbol_payload.get("qfqday") or []
    rows = []
    seen_dates = set()
    for raw in raw_rows:
        if not isinstance(raw, (list, tuple)) or len(raw) < 5:
            continue
        try:
            trade_date = normalize_trade_date(raw[0])
        except CffexDataError:
            continue
        if trade_date < start or trade_date > end or trade_date in seen_dates:
            continue
        prices = [_finite_number(value) for value in raw[1:5]]
        if any(value is None or value <= 0 for value in prices):
            continue
        volume = _finite_number(raw[5]) if len(raw) > 5 else 0.0
        rows.append(
            {
                "trade_date": trade_date,
                "open": prices[0],
                "close": prices[1],
                "high": prices[2],
                "low": prices[3],
                "volume": volume or 0.0,
                "amount": 0.0,
                "source_policy": "tencent.fqkline.day.cffex-spot.v1",
                "source_url": url,
                "source_date": trade_date,
                "query_date": _dt.date.today().isoformat(),
            }
        )
        seen_dates.add(trade_date)
    rows.sort(key=lambda row: row["trade_date"])
    if not rows:
        raise CffexSourceError(f"腾讯指数日线没有返回{symbol}的区间数据", url=url)
    return rows


def parse_member_rank_xml(
    raw_bytes: bytes,
    *,
    expected_trade_date: Any,
    expected_product: Any,
    source_url: str = "",
    query_date: Any | None = None,
    expected_rank_count: int = 20,
) -> list[dict]:
    trade_date = normalize_trade_date(expected_trade_date)
    product = _normalize_product_code(expected_product)
    query = _normalize_query_date(query_date, trade_date)
    root = _parse_xml(raw_bytes, expected_root="positionRank")
    source_hash = content_sha256(raw_bytes)
    rows = []
    seen_keys = set()
    rank_types_by_contract: dict[str, set[str]] = defaultdict(set)
    rank_numbers_by_contract_type: dict[tuple[str, str], set[int]] = defaultdict(set)
    expected_rank_count = _strict_int(expected_rank_count, field="预期排名数量")
    if expected_rank_count <= 0:
        raise CffexDataError("预期排名数量必须为正整数")

    for element in root.findall("data"):
        contract_code = _required_text(element, "instrumentid").upper()
        row_trade_date = normalize_trade_date(_required_text(element, "tradingday"))
        row_product = _normalize_product_code(_required_text(element, "productid"))
        datatype_id = _required_text(element, "datatypeid")
        rank_type = _RANK_TYPE_BY_ID.get(datatype_id)
        if rank_type is None:
            raise CffexDataError(f"未知持仓排名类型：{datatype_id}")
        if row_trade_date != trade_date:
            raise CffexDataError(
                f"持仓排名交易日为{row_trade_date}，目标日期为{trade_date}"
            )
        if row_product != product or not contract_code.startswith(product):
            raise CffexDataError(
                f"持仓排名品种或合约不匹配：{row_product}/{contract_code}，预期{product}"
            )
        rank_no = _strict_int(_required_text(element, "rank"), field="排名")
        quantity = _strict_int(_required_text(element, "volume"), field="数量")
        raw_daily_change = element.findtext("varvolume")
        if rank_type == "volume" and str(raw_daily_change or "").strip() == "":
            daily_change = None
        else:
            daily_change = _strict_int(
                _required_text(element, "varvolume"), field="比上交易日增减"
            )
        if rank_no <= 0:
            raise CffexDataError(f"排名必须为正整数：{rank_no}")
        if quantity < 0:
            raise CffexDataError(f"持仓或成交数量不能为负数：{quantity}")
        key = (contract_code, rank_type, rank_no)
        if key in seen_keys:
            raise CffexDataError(
                f"同一合约、排名类型和名次重复：{contract_code}/{rank_type}/{rank_no}"
            )
        seen_keys.add(key)
        rank_types_by_contract[contract_code].add(rank_type)
        rank_numbers_by_contract_type[(contract_code, rank_type)].add(rank_no)
        rows.append(
            {
                "trade_date": trade_date,
                "source_date": trade_date,
                "query_date": query,
                "product_code": product,
                "contract_code": contract_code,
                "rank_type": rank_type,
                "rank_no": rank_no,
                "member_id": str(element.findtext("partyid") or "").strip(),
                "member_name": _required_text(element, "shortname"),
                "quantity": quantity,
                "daily_change": daily_change,
                "source_url": str(source_url or ""),
                "content_hash": source_hash,
                "source_policy": CFFEX_SOURCE_POLICY,
            }
        )

    if not rows:
        raise CffexDataError(f"{product}持仓排名文件没有有效记录")
    required_types = set(_RANK_TYPE_BY_ID.values())
    for contract_code, present_types in rank_types_by_contract.items():
        missing = sorted(required_types - present_types)
        if missing:
            raise CffexDataError(
                f"{contract_code}缺少排名类型：{','.join(missing)}"
            )
        expected_numbers = set(range(1, expected_rank_count + 1))
        for rank_type in sorted(required_types):
            actual_numbers = rank_numbers_by_contract_type[(contract_code, rank_type)]
            if actual_numbers != expected_numbers:
                raise CffexDataError(
                    f"{contract_code}/{rank_type}排名应为1-{expected_rank_count}连续名次"
                )
    rows.sort(key=lambda row: (row["contract_code"], row["rank_type"], row["rank_no"]))
    return rows


def parse_contract_daily_xml(
    raw_bytes: bytes,
    *,
    expected_trade_date: Any,
    source_url: str = "",
    query_date: Any | None = None,
) -> list[dict]:
    trade_date = normalize_trade_date(expected_trade_date)
    query = _normalize_query_date(query_date, trade_date)
    root = _parse_xml(raw_bytes, expected_root="dailydatas")
    source_hash = content_sha256(raw_bytes)
    rows = []
    seen_keys = set()

    for element in root.findall("dailydata"):
        raw_product = str(element.findtext("productid") or "").strip().upper()
        if raw_product not in CFFEX_PRODUCTS:
            continue
        contract_code = _required_text(element, "instrumentid").upper()
        row_trade_date = normalize_trade_date(_required_text(element, "tradingday"))
        if row_trade_date != trade_date:
            raise CffexDataError(
                f"合约日行情交易日为{row_trade_date}，目标日期为{trade_date}"
            )
        if not contract_code.startswith(raw_product):
            raise CffexDataError(
                f"合约日行情品种或合约不匹配：{raw_product}/{contract_code}"
            )
        key = (raw_product, contract_code)
        if key in seen_keys:
            raise CffexDataError(f"合约日行情重复：{contract_code}")
        seen_keys.add(key)
        settlement_price = _strict_float(
            _required_text(element, "settlementprice"), field="结算价"
        )
        if settlement_price <= 0:
            raise CffexDataError(f"{contract_code}结算价必须大于零")
        close_price = _optional_nonnegative_float(element.findtext("closeprice"), field="收盘价")
        previous_settlement_price = _optional_nonnegative_float(
            element.findtext("presettlementprice"), field="前结算价"
        )
        volume = _strict_int(_required_text(element, "volume"), field="成交量")
        open_interest = _strict_int(_required_text(element, "openinterest"), field="持仓量")
        previous_open_interest = _strict_int(
            _required_text(element, "preopeninterest"), field="前持仓量"
        )
        if min(volume, open_interest, previous_open_interest) < 0:
            raise CffexDataError(f"{contract_code}成交量或持仓量不能为负数")
        rows.append(
            {
                "trade_date": trade_date,
                "source_date": trade_date,
                "query_date": query,
                "product_code": raw_product,
                "contract_code": contract_code,
                "close_price": close_price,
                "settlement_price": settlement_price,
                "previous_settlement_price": previous_settlement_price,
                "volume": volume,
                "open_interest": open_interest,
                "previous_open_interest": previous_open_interest,
                "contract_multiplier": CFFEX_CONTRACT_MULTIPLIERS[raw_product],
                "source_url": str(source_url or ""),
                "content_hash": source_hash,
                "source_policy": CFFEX_SOURCE_POLICY,
            }
        )

    if not rows:
        raise CffexDataError("中金所日行情没有 IF、IH、IC、IM 合约记录")
    rows.sort(key=lambda row: (row["product_code"], row["contract_code"]))
    return rows


def collect_cffex_index_futures_day(
    trade_date: Any,
    *,
    opener=None,
    timeout_seconds: float = 15,
    query_date: Any | None = None,
    strict: bool = True,
    include_raw_bytes: bool = False,
) -> dict:
    target = normalize_trade_date(trade_date)
    query = _normalize_query_date(query_date, target)
    daily_url = cffex_contract_daily_url(target)
    source_files = []
    raw_files = []
    errors = []
    try:
        daily_bytes = fetch_cffex_bytes(
            daily_url, opener=opener, timeout_seconds=timeout_seconds
        )
        contract_rows = parse_contract_daily_xml(
            daily_bytes,
            expected_trade_date=target,
            source_url=daily_url,
            query_date=query,
        )
        source_files.append(
            {
                "kind": "contract_daily",
                "product_code": "",
                "source_url": daily_url,
                "content_hash": content_sha256(daily_bytes),
                "source_date": target,
                "query_date": query,
                "status": "available",
            }
        )
        if include_raw_bytes:
            raw_files.append(
                {
                    "kind": "contract_daily",
                    "product_code": "",
                    "source_url": daily_url,
                    "content_hash": content_sha256(daily_bytes),
                    "raw_bytes": daily_bytes,
                }
            )
    except (CffexDataError, CffexSourceError) as error:
        if strict:
            raise
        contract_rows = []
        errors.append(
            {
                "kind": "contract_daily",
                "source_url": daily_url,
                "reason": str(error),
                "status_code": getattr(error, "status_code", None),
            }
        )

    if not contract_rows:
        return {
            "schema_version": "cffex_index_futures_raw_day.v1",
            "trade_date": target,
            "source_date": target,
            "query_date": query,
            "source_policy": CFFEX_SOURCE_POLICY,
            "contract_rows": [],
            "member_rank_rows": [],
            "source_files": source_files,
            "raw_files": raw_files,
            "source_errors": errors,
            "availability": "unavailable",
        }

    contract_codes = {row["contract_code"] for row in contract_rows}
    member_rank_rows = []
    for product in CFFEX_PRODUCTS:
        url = cffex_position_rank_url(target, product)
        try:
            raw_bytes = fetch_cffex_bytes(url, opener=opener, timeout_seconds=timeout_seconds)
            product_rows = parse_member_rank_xml(
                raw_bytes,
                expected_trade_date=target,
                expected_product=product,
                source_url=url,
                query_date=query,
            )
            missing_contracts = sorted(
                {row["contract_code"] for row in product_rows} - contract_codes
            )
            if missing_contracts:
                raise CffexDataError(
                    f"{product}持仓排名合约缺少同日日行情：{','.join(missing_contracts)}"
                )
            member_rank_rows.extend(product_rows)
            source_files.append(
                {
                    "kind": "member_rank",
                    "product_code": product,
                    "source_url": url,
                    "content_hash": content_sha256(raw_bytes),
                    "source_date": target,
                    "query_date": query,
                    "status": "available",
                }
            )
            if include_raw_bytes:
                raw_files.append(
                    {
                        "kind": "member_rank",
                        "product_code": product,
                        "source_url": url,
                        "content_hash": content_sha256(raw_bytes),
                        "raw_bytes": raw_bytes,
                    }
                )
        except (CffexDataError, CffexSourceError) as error:
            if strict:
                raise
            errors.append(
                {
                    "kind": "member_rank",
                    "product_code": product,
                    "source_url": url,
                    "reason": str(error),
                    "status_code": getattr(error, "status_code", None),
                }
            )

    disclosed_contract_codes = {
        str(row.get("contract_code") or "").upper()
        for row in member_rank_rows
        if row.get("contract_code")
    }
    contract_rows = [
        row for row in contract_rows if row["contract_code"] in disclosed_contract_codes
    ]

    return {
        "schema_version": "cffex_index_futures_raw_day.v1",
        "trade_date": target,
        "source_date": target,
        "query_date": query,
        "source_policy": CFFEX_SOURCE_POLICY,
        "contract_rows": contract_rows,
        "member_rank_rows": member_rank_rows,
        "source_files": source_files,
        "raw_files": raw_files,
        "source_errors": errors,
        "availability": "complete" if not errors else ("partial" if member_rank_rows else "unavailable"),
    }


def normalize_contract_daily_record(row: dict, *, expected_trade_date: Any | None = None) -> dict:
    if not isinstance(row, dict):
        raise CffexDataError("中金所合约日行情记录必须是字典")
    trade_date = normalize_trade_date(row.get("trade_date"))
    if expected_trade_date is not None and trade_date != normalize_trade_date(expected_trade_date):
        raise CffexDataError(f"合约日行情日期{trade_date}不属于目标交易日")
    source_date = normalize_trade_date(row.get("source_date"))
    query_date = _normalize_query_date(_required_record_text(row, "query_date"), source_date)
    if source_date != trade_date:
        raise CffexDataError(f"合约日行情来源日期{source_date}不等于交易日{trade_date}")
    product = _normalize_product_code(row.get("product_code"))
    contract_code = str(row.get("contract_code") or "").strip().upper()
    if not contract_code.startswith(product):
        raise CffexDataError(f"合约代码{contract_code!r}不属于{product}")
    settlement_price = _strict_float(row.get("settlement_price"), field="结算价")
    if settlement_price <= 0:
        raise CffexDataError(f"{contract_code}结算价必须大于零")
    volume = _strict_int(row.get("volume"), field="成交量")
    open_interest = _strict_int(row.get("open_interest"), field="持仓量")
    previous_open_interest = _strict_int(row.get("previous_open_interest"), field="前持仓量")
    if min(volume, open_interest, previous_open_interest) < 0:
        raise CffexDataError(f"{contract_code}成交量或持仓量不能为负数")
    multiplier = _strict_int(row.get("contract_multiplier"), field="合约乘数")
    if multiplier != CFFEX_CONTRACT_MULTIPLIERS[product]:
        raise CffexDataError(f"{contract_code}合约乘数{multiplier}与品种规则不一致")
    return {
        "trade_date": trade_date,
        "source_date": source_date,
        "query_date": query_date,
        "product_code": product,
        "contract_code": contract_code,
        "close_price": _optional_nonnegative_float(row.get("close_price"), field="收盘价"),
        "settlement_price": settlement_price,
        "previous_settlement_price": _optional_nonnegative_float(
            row.get("previous_settlement_price"), field="前结算价"
        ),
        "volume": volume,
        "open_interest": open_interest,
        "previous_open_interest": previous_open_interest,
        "contract_multiplier": multiplier,
        "source_url": _required_record_text(row, "source_url"),
        "content_hash": _normalize_content_hash(row.get("content_hash")),
        "source_policy": _required_record_text(row, "source_policy"),
    }


def normalize_member_rank_record(row: dict, *, expected_trade_date: Any | None = None) -> dict:
    if not isinstance(row, dict):
        raise CffexDataError("中金所会员排名记录必须是字典")
    trade_date = normalize_trade_date(row.get("trade_date"))
    if expected_trade_date is not None and trade_date != normalize_trade_date(expected_trade_date):
        raise CffexDataError(f"会员排名日期{trade_date}不属于目标交易日")
    source_date = normalize_trade_date(row.get("source_date"))
    query_date = _normalize_query_date(_required_record_text(row, "query_date"), source_date)
    if source_date != trade_date:
        raise CffexDataError(f"会员排名来源日期{source_date}不等于交易日{trade_date}")
    product = _normalize_product_code(row.get("product_code"))
    contract_code = str(row.get("contract_code") or "").strip().upper()
    if not contract_code.startswith(product):
        raise CffexDataError(f"合约代码{contract_code!r}不属于{product}")
    rank_type = str(row.get("rank_type") or "").strip().lower()
    if rank_type not in _RANK_TYPE_BY_ID.values():
        raise CffexDataError(f"未知持仓排名类型：{rank_type!r}")
    rank_no = _strict_int(row.get("rank_no"), field="排名")
    quantity = _strict_int(row.get("quantity"), field="数量")
    if rank_type == "volume" and row.get("daily_change") in (None, ""):
        daily_change = None
    else:
        daily_change = _strict_int(row.get("daily_change"), field="比上交易日增减")
    if rank_no <= 0 or quantity < 0:
        raise CffexDataError(f"会员排名或数量无效：{rank_no}/{quantity}")
    return {
        "trade_date": trade_date,
        "source_date": source_date,
        "query_date": query_date,
        "product_code": product,
        "contract_code": contract_code,
        "rank_type": rank_type,
        "rank_no": rank_no,
        "member_id": str(row.get("member_id") or "").strip(),
        "member_name": _required_record_text(row, "member_name"),
        "quantity": quantity,
        "daily_change": daily_change,
        "source_url": _required_record_text(row, "source_url"),
        "content_hash": _normalize_content_hash(row.get("content_hash")),
        "source_policy": _required_record_text(row, "source_policy"),
    }


def assess_cffex_day_scope(
    contract_rows: Iterable[dict],
    member_rank_rows: Iterable[dict],
    *,
    expected_trade_date: Any,
    expected_products: Iterable[str] = CFFEX_PRODUCTS,
    member_name: str = "中信期货",
    expected_rank_count: int = 20,
) -> dict:
    """Assess provenance, disclosed-rank scope, and selected-member coverage."""

    target = normalize_trade_date(expected_trade_date)
    products = tuple(dict.fromkeys(_normalize_product_code(item) for item in expected_products))
    contracts = [dict(row) for row in contract_rows if isinstance(row, dict)]
    ranks = [dict(row) for row in member_rank_rows if isinstance(row, dict)]
    integrity_errors: list[str] = []
    structural_reasons: list[str] = []
    member_reasons: list[str] = []

    unexpected_contract_products = sorted(
        {
            str(row.get("product_code") or "").upper()
            for row in contracts
            if str(row.get("product_code") or "").upper() not in products
        }
    )
    unexpected_rank_products = sorted(
        {
            str(row.get("product_code") or "").upper()
            for row in ranks
            if str(row.get("product_code") or "").upper() not in products
        }
    )
    if unexpected_contract_products or unexpected_rank_products:
        integrity_errors.append(
            "单日事实含范围外品种："
            f"合约={','.join(unexpected_contract_products) or '无'}；"
            f"排名={','.join(unexpected_rank_products) or '无'}"
        )

    contracts = [
        row for row in contracts if str(row.get("product_code") or "").upper() in products
    ]
    ranks = [row for row in ranks if str(row.get("product_code") or "").upper() in products]
    contract_products = {
        str(row.get("product_code") or "").upper() for row in contracts
    }
    rank_products = {str(row.get("product_code") or "").upper() for row in ranks}
    for product in products:
        if product not in contract_products:
            structural_reasons.append(f"{product}目标日合约行情缺失")
        if product not in rank_products:
            structural_reasons.append(f"{product}目标日会员排名缺失")

    contract_key_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
    rank_key_rows: dict[tuple[str, str, str, int], list[dict]] = defaultdict(list)
    for row in contracts:
        product = str(row.get("product_code") or "").upper()
        contract = str(row.get("contract_code") or "").upper()
        contract_key_rows[(product, contract)].append(row)
        integrity_errors.extend(_cffex_row_provenance_errors(row, target, label=f"{product}/{contract}合约行情"))
    for row in ranks:
        product = str(row.get("product_code") or "").upper()
        contract = str(row.get("contract_code") or "").upper()
        rank_type = str(row.get("rank_type") or "").lower()
        try:
            rank_no = _strict_int(row.get("rank_no"), field="排名")
        except CffexDataError:
            rank_no = -1
        rank_key_rows[(product, contract, rank_type, rank_no)].append(row)
        integrity_errors.extend(
            _cffex_row_provenance_errors(
                row,
                target,
                label=f"{product}/{contract}/{rank_type}/{rank_no}会员排名",
            )
        )

    duplicate_contracts = sorted(key for key, rows in contract_key_rows.items() if len(rows) != 1)
    if duplicate_contracts:
        integrity_errors.append(f"合约日行情存在重复自然键：{duplicate_contracts[:5]}")
    duplicate_ranks = sorted(key for key, rows in rank_key_rows.items() if len(rows) != 1)
    if duplicate_ranks:
        integrity_errors.append(f"会员排名存在重复自然键：{duplicate_ranks[:5]}")

    contract_keys = set(contract_key_rows)
    rank_contract_keys = {
        (str(row.get("product_code") or "").upper(), str(row.get("contract_code") or "").upper())
        for row in ranks
    }
    missing_daily = sorted(rank_contract_keys - contract_keys)
    if missing_daily:
        structural_reasons.append(f"会员排名合约缺少同日日行情：{missing_daily[:5]}")
    missing_ranks = sorted(contract_keys - rank_contract_keys)
    if missing_ranks:
        structural_reasons.append(f"合约日行情缺少对应会员排名：{missing_ranks[:5]}")

    expected_numbers = set(range(1, int(expected_rank_count) + 1))
    for product, contract in sorted(rank_contract_keys):
        contract_ranks = [
            row
            for row in ranks
            if str(row.get("product_code") or "").upper() == product
            and str(row.get("contract_code") or "").upper() == contract
        ]
        for rank_type in ("volume", "long", "short"):
            typed = [row for row in contract_ranks if str(row.get("rank_type") or "") == rank_type]
            numbers = {
                int(row.get("rank_no"))
                for row in typed
                if str(row.get("rank_no") or "").isdigit()
            }
            if len(typed) != expected_rank_count or numbers != expected_numbers:
                structural_reasons.append(
                    f"{product}/{contract}{rank_type}排名不是1-{expected_rank_count}连续名次或存在重复"
                )
        for rank_type in _POSITION_RANK_TYPES:
            selected = [
                row
                for row in contract_ranks
                if str(row.get("rank_type") or "") == rank_type
                and _member_name_matches(row.get("member_name"), member_name)
            ]
            if len(selected) != 1:
                member_reasons.append(
                    f"{product}/{contract}{canonical_member_name(member_name)}{rank_type}披露行数量为{len(selected)}"
                )

    contract_sources = {
        (
            str(row.get("source_url") or ""),
            str(row.get("content_hash") or "").lower(),
            str(row.get("source_date") or ""),
            str(row.get("source_policy") or ""),
        )
        for row in contracts
    }
    if len(contract_sources) > 1:
        integrity_errors.append("同一交易日合约行情来源地址、哈希或规则不一致")
    for product in products:
        product_sources = {
            (
                str(row.get("source_url") or ""),
                str(row.get("content_hash") or "").lower(),
                str(row.get("source_date") or ""),
                str(row.get("source_policy") or ""),
            )
            for row in ranks
            if str(row.get("product_code") or "").upper() == product
        }
        if len(product_sources) > 1:
            integrity_errors.append(f"{product}会员排名来源地址、哈希或规则不一致")

    return {
        "integrity_errors": list(dict.fromkeys(integrity_errors)),
        "structural_reasons": list(dict.fromkeys(structural_reasons)),
        "member_reasons": list(dict.fromkeys(member_reasons)),
        "structural_complete": not integrity_errors and not structural_reasons,
        "complete": not integrity_errors and not structural_reasons and not member_reasons,
    }


def _cffex_row_provenance_errors(row: dict, target: str, *, label: str) -> list[str]:
    errors = []
    try:
        trade_date = normalize_trade_date(row.get("trade_date"))
        source_date = normalize_trade_date(row.get("source_date"))
    except CffexDataError:
        errors.append(f"{label}交易日或来源日期无效")
        return errors
    if trade_date != target or source_date != target:
        errors.append(f"{label}交易日或来源日期不属于{target}")
    query_text = str(row.get("query_date") or "").strip()
    if not query_text:
        errors.append(f"{label}缺少查询日期")
    else:
        try:
            query = normalize_trade_date(query_text)
            if query < target:
                errors.append(f"{label}查询日期早于来源日期")
        except CffexDataError:
            errors.append(f"{label}查询日期无效")
    if not str(row.get("source_url") or "").strip():
        errors.append(f"{label}缺少来源地址")
    try:
        _normalize_content_hash(row.get("content_hash"))
    except CffexDataError:
        errors.append(f"{label}内容哈希无效")
    if str(row.get("source_policy") or "").strip() != CFFEX_SOURCE_POLICY:
        errors.append(f"{label}来源规则不匹配")
    return errors


def build_member_position_summary(
    member_rank_rows: Iterable[dict],
    contract_rows: Iterable[dict],
    *,
    member_name: str = "中信期货",
) -> dict:
    ranks = [dict(row) for row in member_rank_rows if isinstance(row, dict)]
    contracts = {
        str(row.get("contract_code") or "").upper(): dict(row)
        for row in contract_rows
        if isinstance(row, dict) and row.get("contract_code")
    }
    disclosed_contracts = sorted(
        {
            str(row.get("contract_code") or "").upper()
            for row in ranks
            if row.get("rank_type") in _POSITION_RANK_TYPES and row.get("contract_code")
        }
    )
    rows_by_contract_type: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in ranks:
        if row.get("rank_type") not in _POSITION_RANK_TYPES:
            continue
        if _member_name_matches(row.get("member_name"), member_name):
            key = (str(row.get("contract_code") or "").upper(), str(row.get("rank_type")))
            rows_by_contract_type[key].append(row)

    included = []
    excluded = []
    official_names = set()
    for contract_code in disclosed_contracts:
        long_rows = rows_by_contract_type.get((contract_code, "long"), [])
        short_rows = rows_by_contract_type.get((contract_code, "short"), [])
        missing = []
        if len(long_rows) != 1:
            missing.append("long")
        if len(short_rows) != 1:
            missing.append("short")
        contract = contracts.get(contract_code)
        if contract is None:
            missing.append("contract_daily")
        if missing:
            excluded.append({"contract_code": contract_code, "missing": missing})
            continue
        long_row = long_rows[0]
        short_row = short_rows[0]
        official_names.update(
            {str(long_row.get("member_name") or ""), str(short_row.get("member_name") or "")}
        )
        product = _normalize_product_code(long_row.get("product_code"))
        settlement_price = _finite_number(contract.get("settlement_price"))
        multiplier = _strict_int(
            contract.get("contract_multiplier", CFFEX_CONTRACT_MULTIPLIERS[product]),
            field="合约乘数",
        )
        if settlement_price is None or settlement_price <= 0 or multiplier <= 0:
            excluded.append(
                {"contract_code": contract_code, "missing": ["settlement_or_multiplier"]}
            )
            continue
        long_quantity = _strict_int(long_row.get("quantity"), field="多头持仓")
        short_quantity = _strict_int(short_row.get("quantity"), field="空头持仓")
        long_change = _strict_int(long_row.get("daily_change"), field="多头日变")
        short_change = _strict_int(short_row.get("daily_change"), field="空头日变")
        long_notional = long_quantity * settlement_price * multiplier
        short_notional = short_quantity * settlement_price * multiplier
        included.append(
            {
                "product_code": product,
                "contract_code": contract_code,
                "settlement_price": settlement_price,
                "contract_multiplier": multiplier,
                "long_quantity": long_quantity,
                "short_quantity": short_quantity,
                "net_short_balance": short_quantity - long_quantity,
                "long_daily_change": long_change,
                "short_daily_change": short_change,
                "net_short_change": short_change - long_change,
                "long_notional": long_notional,
                "short_notional": short_notional,
                "net_short_notional": short_notional - long_notional,
                "market_open_interest": _strict_int(
                    contract.get("open_interest"), field="全市场持仓"
                ),
            }
        )

    by_product = {}
    for product in CFFEX_PRODUCTS:
        product_included = [row for row in included if row["product_code"] == product]
        product_excluded = [
            row
            for row in excluded
            if str(row.get("contract_code") or "").startswith(product)
        ]
        by_product[product] = _aggregate_member_contracts(product_included, product_excluded)
    overall = _aggregate_member_contracts(included, excluded, include_share=False)
    return {
        "member_name": canonical_member_name(member_name),
        "official_member_names": sorted(name for name in official_names if name),
        "included_contracts": included,
        "excluded_contracts": excluded,
        "products": by_product,
        "overall": overall,
        "availability": overall["availability"],
        "interpretation_note": "净空变化等于空头日变减多头日变，不等于新增空单。",
    }


def build_top20_structure(
    current_rank_rows: Iterable[dict],
    previous_rank_rows: Iterable[dict] | None = None,
    *,
    expected_rank_count: int = 20,
) -> dict:
    current = [dict(row) for row in current_rank_rows if isinstance(row, dict)]
    previous = (
        [dict(row) for row in previous_rank_rows if isinstance(row, dict)]
        if previous_rank_rows is not None
        else None
    )
    products = {}
    for product in CFFEX_PRODUCTS:
        current_product = [row for row in current if row.get("product_code") == product]
        previous_product = (
            [row for row in previous if row.get("product_code") == product]
            if previous is not None
            else None
        )
        products[product] = _build_top20_scope(
            current_product,
            previous_product,
            expected_rank_count=expected_rank_count,
        )
    return {
        "overall": _build_top20_scope(
            current,
            previous,
            expected_rank_count=expected_rank_count,
        ),
        "products": products,
        "interpretation_note": "前20多头榜和空头榜是独立截面，差额变化包含会员或披露范围影响。",
    }


def build_contract_market_context(
    contract_rows: Iterable[dict],
    *,
    spot_rows_by_product: dict[str, dict] | None = None,
) -> dict:
    spots = spot_rows_by_product or {}
    rows = []
    by_product: dict[str, list[dict]] = defaultdict(list)
    for raw in contract_rows:
        if not isinstance(raw, dict):
            continue
        product = _normalize_product_code(raw.get("product_code"))
        settlement = _finite_number(raw.get("settlement_price"))
        previous_settlement = _finite_number(raw.get("previous_settlement_price"))
        open_interest = _strict_int(raw.get("open_interest"), field="全市场持仓")
        previous_open_interest = _strict_int(
            raw.get("previous_open_interest"), field="前一日全市场持仓"
        )
        settlement_change_pct = None
        if settlement is not None and previous_settlement not in (None, 0):
            settlement_change_pct = (settlement - previous_settlement) / previous_settlement * 100
        spot = spots.get(product) if isinstance(spots.get(product), dict) else {}
        spot_date = str(spot.get("trade_date") or spot.get("source_date") or "")
        row_date = str(raw.get("trade_date") or "")
        spot_close = _finite_number(spot.get("close")) if spot_date == row_date else None
        basis = settlement - spot_close if settlement is not None and spot_close is not None else None
        item = {
            "trade_date": row_date,
            "product_code": product,
            "contract_code": str(raw.get("contract_code") or "").upper(),
            "settlement_price": settlement,
            "settlement_change_pct": settlement_change_pct,
            "open_interest": open_interest,
            "open_interest_change": open_interest - previous_open_interest,
            "spot_index_code": CFFEX_SPOT_INDEX_CODES[product],
            "spot_close": spot_close,
            "basis": basis,
            "basis_pct": (basis / spot_close * 100) if basis is not None and spot_close else None,
        }
        rows.append(item)
        by_product[product].append(item)

    products = {}
    for product in CFFEX_PRODUCTS:
        product_rows = sorted(by_product.get(product, []), key=lambda row: row["contract_code"])
        front = product_rows[0] if product_rows else None
        far_rows = product_rows[1:]
        front_change = front.get("open_interest_change") if front else None
        far_change = sum(row["open_interest_change"] for row in far_rows)
        rollover_likely = bool(front and front_change < 0 and far_rows and far_change > 0)
        products[product] = {
            "contracts": product_rows,
            "front_contract": front.get("contract_code") if front else "",
            "front_open_interest_change": front_change,
            "far_open_interest_change": far_change if far_rows else None,
            "rollover_status": "likely" if rollover_likely else "not_observed",
            "spot_available": bool(product_rows) and all(
                row.get("spot_close") is not None for row in product_rows
            ),
        }
    return {"products": products, "rows": sorted(rows, key=lambda row: row["contract_code"])}


def build_history_windows(
    rows: Iterable[dict],
    *,
    target_date: Any,
    value_key: str,
    requested_windows: tuple[int, ...] = (20, 60),
    trade_dates: Iterable[str] | None = None,
) -> dict:
    target = normalize_trade_date(target_date)
    values_by_date = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            trade_date = normalize_trade_date(row.get("trade_date"))
        except CffexDataError:
            continue
        if trade_date > target:
            continue
        value = _finite_number(row.get(value_key))
        if trade_date in values_by_date and values_by_date[trade_date] != value:
            existing = values_by_date[trade_date]
            if existing is not None and value is not None:
                raise CffexDataError(f"历史序列同一交易日存在冲突值：{trade_date}")
            values_by_date[trade_date] = existing if existing is not None else value
        else:
            values_by_date[trade_date] = value
    ordered = [
        {"trade_date": trade_date, "value": values_by_date[trade_date]}
        for trade_date in sorted(values_by_date)
    ]
    if trade_dates is not None:
        calendar = list(trade_dates)
        normalized = [normalize_trade_date(day) for day in calendar]
        if (calendar != normalized or calendar != sorted(set(calendar))
                or not calendar or calendar[-1] != target):
            raise CffexDataError('期货交易日历日期或顺序不符')
        ordered = [{'trade_date': day, 'value': values_by_date.get(day)} for day in calendar]
    target_present = any(row['trade_date'] == target for row in ordered)
    result = {}
    for raw_window in requested_windows:
        window = int(raw_window)
        if window <= 0:
            raise CffexDataError(f"历史窗口必须为正整数：{window}")
        selected = ordered[-window:]
        finite_selected = [row for row in selected if row["value"] is not None]
        current_value = values_by_date.get(target)
        percentile = None
        if current_value is not None and finite_selected:
            percentile = (
                sum(row["value"] <= current_value for row in finite_selected)
                / len(finite_selected)
                * 100
            )
        result[str(window)] = {
            "requested_window": window,
            "sample_count": len(finite_selected),
            "observed_trade_day_count": len(selected),
            "start_date": selected[0]["trade_date"] if selected else "",
            "end_date": selected[-1]["trade_date"] if selected else "",
            "target_date_present": target_present,
            "current_value": current_value,
            "empirical_percentile_pct": percentile,
            "coverage_status": (
                "complete"
                if len(selected) == window
                and len(finite_selected) == window
                and target_present
                and current_value is not None
                else "insufficient"
            ),
            "values": selected,
        }
    return result


def canonical_member_name(value: Any) -> str:
    text = str(value or "").strip().replace("（", "(").replace("）", ")")
    if text.endswith("(代客)"):
        text = text[:-4]
    return "".join(text.split())


def _member_name_matches(actual: Any, expected: Any) -> bool:
    return bool(canonical_member_name(actual)) and canonical_member_name(actual) == canonical_member_name(expected)


def _aggregate_member_contracts(rows: list[dict], excluded: list[dict], *, include_share: bool = True) -> dict:
    long_quantity = sum(row["long_quantity"] for row in rows)
    short_quantity = sum(row["short_quantity"] for row in rows)
    long_change = sum(row["long_daily_change"] for row in rows)
    short_change = sum(row["short_daily_change"] for row in rows)
    open_interest = sum(row["market_open_interest"] for row in rows)
    availability = "complete"
    if excluded:
        availability = "partial" if rows else "unavailable"
    elif not rows:
        availability = "unavailable"
    if not rows:
        payload = {
            "long_quantity": None,
            "short_quantity": None,
            "net_short_balance": None,
            "long_daily_change": None,
            "short_daily_change": None,
            "net_short_change": None,
            "long_notional": None,
            "short_notional": None,
            "net_short_notional": None,
            "included_contract_count": 0,
            "excluded_contract_count": len(excluded),
            "availability": availability,
        }
        if include_share:
            payload["net_short_share_of_market_open_interest_pct"] = None
        return payload
    payload = {
        "long_quantity": long_quantity,
        "short_quantity": short_quantity,
        "net_short_balance": short_quantity - long_quantity,
        "long_daily_change": long_change,
        "short_daily_change": short_change,
        "net_short_change": short_change - long_change,
        "long_notional": sum(row["long_notional"] for row in rows),
        "short_notional": sum(row["short_notional"] for row in rows),
        "net_short_notional": sum(row["net_short_notional"] for row in rows),
        "included_contract_count": len(rows),
        "excluded_contract_count": len(excluded),
        "availability": availability,
    }
    if include_share:
        payload["net_short_share_of_market_open_interest_pct"] = (
            (short_quantity - long_quantity) / open_interest * 100 if open_interest > 0 else None
        )
    return payload


def _build_top20_scope(
    current: list[dict],
    previous: list[dict] | None,
    *,
    expected_rank_count: int,
) -> dict:
    current_long = [row for row in current if row.get("rank_type") == "long"]
    current_short = [row for row in current if row.get("rank_type") == "short"]
    long_quantity = sum(_strict_int(row.get("quantity"), field="多头榜持仓") for row in current_long)
    short_quantity = sum(_strict_int(row.get("quantity"), field="空头榜持仓") for row in current_short)
    long_change = sum(_strict_int(row.get("daily_change"), field="多头榜日变") for row in current_long)
    short_change = sum(_strict_int(row.get("daily_change"), field="空头榜日变") for row in current_short)
    current_complete = _top20_scope_is_complete(
        current, expected_rank_count=expected_rank_count
    )
    current_balance = short_quantity - long_quantity if current_complete else None
    previous_balance = None
    membership_changes = None
    previous_complete = bool(previous) and _top20_scope_is_complete(
        previous, expected_rank_count=expected_rank_count
    )
    if previous:
        previous_long = [row for row in previous if row.get("rank_type") == "long"]
        previous_short = [row for row in previous if row.get("rank_type") == "short"]
        if previous_complete:
            previous_balance = sum(
                _strict_int(row.get("quantity"), field="前日空头榜持仓")
                for row in previous_short
            ) - sum(
                _strict_int(row.get("quantity"), field="前日多头榜持仓")
                for row in previous_long
            )
        membership_changes = {
            "long_entered": sorted(_rank_members(current_long) - _rank_members(previous_long)),
            "long_exited": sorted(_rank_members(previous_long) - _rank_members(current_long)),
            "short_entered": sorted(_rank_members(current_short) - _rank_members(previous_short)),
            "short_exited": sorted(_rank_members(previous_short) - _rank_members(current_short)),
            "contracts_entered": sorted(_rank_contracts(current) - _rank_contracts(previous)),
            "contracts_exited": sorted(_rank_contracts(previous) - _rank_contracts(current)),
        }
    cross_section_change = (
        current_balance - previous_balance
        if current_balance is not None and previous_balance is not None
        else None
    )
    listed_change_net = short_change - long_change if current_complete else None
    contracts_changed = bool(
        membership_changes
        and (
            membership_changes.get("contracts_entered")
            or membership_changes.get("contracts_exited")
        )
    )
    return {
        "long_quantity": long_quantity,
        "short_quantity": short_quantity,
        "top20_cross_section_net_short": current_balance,
        "previous_top20_cross_section_net_short": previous_balance,
        "top20_cross_section_change": cross_section_change,
        "long_daily_change": long_change,
        "short_daily_change": short_change,
        "listed_member_daily_change_net": listed_change_net,
        "membership_scope_residual": (
            cross_section_change - listed_change_net
            if cross_section_change is not None and listed_change_net is not None
            else None
        ),
        "long_member_count": len(_rank_members(current_long)),
        "short_member_count": len(_rank_members(current_short)),
        "contract_count": len(_rank_contracts(current)),
        "membership_changes": membership_changes,
        "availability": (
            "complete"
            if current_complete
            else "incomplete"
        ),
        "comparison_availability": (
            "complete"
            if current_complete and previous_complete and not contracts_changed
            else "incomplete"
        ),
    }


def _top20_scope_is_complete(rows: Iterable[dict], *, expected_rank_count: int) -> bool:
    contracts = _rank_contracts(rows)
    if not contracts:
        return False
    expected_numbers = set(range(1, int(expected_rank_count) + 1))
    for contract_code in contracts:
        for rank_type in _POSITION_RANK_TYPES:
            typed_rows = [
                row
                for row in rows
                if str(row.get("contract_code") or "").upper() == contract_code
                and row.get("rank_type") == rank_type
            ]
            numbers = {
                _strict_int(row.get("rank_no"), field="排名")
                for row in typed_rows
            }
            if len(typed_rows) != int(expected_rank_count) or numbers != expected_numbers:
                return False
    return True


def _rank_members(rows: Iterable[dict]) -> set[str]:
    return {
        f"{str(row.get('contract_code') or '').upper()}:"
        f"{str(row.get('member_id') or '').strip() or str(row.get('member_name') or '').strip()}"
        for row in rows
        if row.get("contract_code") and row.get("member_name")
    }


def _rank_contracts(rows: Iterable[dict]) -> set[str]:
    return {
        str(row.get("contract_code") or "").upper()
        for row in rows
        if row.get("contract_code") and row.get("rank_type") in _POSITION_RANK_TYPES
    }


def _parse_xml(raw_bytes: bytes, *, expected_root: str) -> ET.Element:
    content_sha256(raw_bytes)
    try:
        root = ET.fromstring(raw_bytes)
    except ET.ParseError as error:
        raise CffexDataError(f"中金所XML无法解析：{error}") from error
    if root.tag != expected_root:
        raise CffexDataError(f"中金所XML根节点为{root.tag}，预期{expected_root}")
    return root


def _is_cffex_not_found_page(raw_bytes: bytes) -> bool:
    prefix = bytes(raw_bytes or b"").lstrip()[:4096].lower()
    return bool(
        prefix.startswith((b"<!doctype html", b"<html"))
        and b"404_bg.gif" in prefix
        and b"charset=gb2312" in prefix
    )


def _required_text(element: ET.Element, tag: str) -> str:
    text = str(element.findtext(tag) or "").strip()
    if not text:
        raise CffexDataError(f"中金所XML缺少字段：{tag}")
    return text


def _required_record_text(row: dict, key: str) -> str:
    text = str(row.get(key) or "").strip()
    if not text:
        raise CffexDataError(f"中金所记录缺少字段：{key}")
    return text


def _normalize_content_hash(value: Any) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise CffexDataError("中金所内容哈希必须是64位SHA-256十六进制文本")
    return text


def _normalize_product_code(value: Any) -> str:
    product = str(value or "").strip().upper()
    if product not in CFFEX_PRODUCTS:
        raise CffexDataError(f"不支持的股指期货品种：{value!r}")
    return product


def _normalize_query_date(value: Any | None, trade_date: str) -> str:
    query = normalize_trade_date(value or _dt.date.today().isoformat())
    if query < trade_date:
        raise CffexDataError(f"查询日期{query}早于来源交易日{trade_date}")
    return query


def _strict_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise CffexDataError(f"{field}不是有效整数：{value!r}")
    try:
        text = str(value).strip()
        if not text or any(character in text for character in ".eE"):
            raise ValueError
        return int(text)
    except (TypeError, ValueError) as error:
        raise CffexDataError(f"{field}不是有效整数：{value!r}") from error


def _strict_float(value: Any, *, field: str) -> float:
    number = _finite_number(value)
    if number is None:
        raise CffexDataError(f"{field}不是有效数字：{value!r}")
    return number


def _optional_nonnegative_float(value: Any, *, field: str) -> float | None:
    if value in (None, ""):
        return None
    number = _strict_float(value, field=field)
    if number < 0:
        raise CffexDataError(f"{field}不能为负数：{number}")
    return number


def _finite_number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
