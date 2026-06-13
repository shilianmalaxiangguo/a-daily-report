#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块资金流向增强模块

在现有 sector_fund_flow 基础上,增加:
1. 板块扩散质量评分
2. 板块成交占比趋势追踪
3. 量化环境识别

整合到日报的"板块资金流向"章节
"""

from __future__ import annotations
from typing import Dict, List, Any

# 导入新开发的模块
from domains.market_state.sector_diffusion_quality_scorer import (
    calculate_sector_diffusion_quality,
    build_sector_diffusion_summary
)
from domains.market_state.quant_environment_detector import (
    detect_quant_environment,
    build_quant_environment_summary
)
from domains.market_state.sector_turnover_trend_tracker import (
    build_sector_turnover_trend,
    build_top5_sector_turnover_summary,
    detect_quant_exit_signal
)

__all__ = [
    "build_enhanced_sector_fund_flow_report",
    "build_sector_internal_analysis_data",
    "extract_sector_data_from_fund_flow",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        if isinstance(value, str):
            normalized = value.strip().replace(",", "")
            for token in ("亿元", "亿", "%", "倍", "元"):
                normalized = normalized.replace(token, "")
            if normalized in ("", "-", "--"):
                return float(default)
            value = normalized
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


def _first_value(data: Dict[str, Any], *keys: str):
    for key in keys:
        if key in data and data.get(key) not in (None, ""):
            return data.get(key)
    return None


def _safe_str(value) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "是", "新高", "创新高"}
    return bool(value)


def _normalize_new_high_dates(value) -> List[str]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return [_safe_str(item) for item in value if _safe_str(item)]
    if isinstance(value, str):
        normalized = value.replace("，", ",").replace(";", ",").replace("；", ",")
        return [item.strip() for item in normalized.split(",") if item.strip()]
    return [_safe_str(value)]


def _sector_name_from_entry(entry: Dict[str, Any]) -> str:
    return _safe_str(_first_value(entry, "name", "sector_name", "板块", "行业"))


def _sector_entries(sector_fund_flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not sector_fund_flow:
        return []
    for key in ("inflow", "sectors", "sector_turnover"):
        value = sector_fund_flow.get(key)
        if isinstance(value, list):
            return value
    return []


def _contains_sector(value, sector_name: str) -> bool:
    if not sector_name or value in (None, ""):
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_contains_sector(item, sector_name) for item in value)
    return sector_name in str(value)


def _raw_sector_stocks(sector_name: str, market_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    if not market_data:
        return []

    for container_key in ("sector_stocks", "sector_components"):
        container = market_data.get(container_key)
        if isinstance(container, dict):
            stocks = container.get(sector_name)
            if isinstance(stocks, list):
                return [stock for stock in stocks if isinstance(stock, dict)]
            for key, value in container.items():
                if _contains_sector(key, sector_name) and isinstance(value, list):
                    return [stock for stock in value if isinstance(stock, dict)]

    for pool_key in ("stocks", "stock_pool"):
        pool = market_data.get(pool_key)
        if isinstance(pool, list):
            return [
                stock
                for stock in pool
                if isinstance(stock, dict)
                and (
                    _contains_sector(stock.get("sector"), sector_name)
                    or _contains_sector(stock.get("sector_name"), sector_name)
                )
            ]

    return []


def _normalize_stock(raw_stock: Dict[str, Any]) -> Dict[str, Any]:
    new_high_dates = _normalize_new_high_dates(raw_stock.get("new_high_dates"))
    is_new_high = _truthy(_first_value(raw_stock, "is_new_high", "new_high")) or bool(new_high_dates)

    return {
        "code": _safe_str(_first_value(raw_stock, "code", "stock_code", "代码")),
        "name": _safe_str(_first_value(raw_stock, "name", "stock_name", "名称")),
        "volume": _stock_volume_yi(raw_stock),
        "change_pct": _safe_float(_first_value(raw_stock, "change_pct", "zdf", "涨跌幅")),
        "volume_ratio": _safe_float(_first_value(raw_stock, "volume_ratio", "量比")),
        "is_new_high": is_new_high,
        "new_high_dates": new_high_dates,
        "intraday_high": _safe_float(_first_value(raw_stock, "intraday_high", "high")),
        "close": _safe_float(raw_stock.get("close")),
    }


def _stock_volume_yi(raw_stock: Dict[str, Any]) -> float:
    yi_value = _first_value(
        raw_stock,
        "amount_yi",
        "volume_yi",
        "turnover_yi",
        "cje_yi",
        "成交额_亿",
        "成交额(亿)",
    )
    if yi_value not in (None, ""):
        return _safe_float(yi_value)

    raw_value = _first_value(raw_stock, "volume", "turnover", "amount", "cje", "成交额", "成交金额")
    volume = _safe_float(raw_value)
    if raw_value not in (None, "") and abs(volume) >= 1_000_000:
        return volume / 100_000_000
    return volume


def _sort_stocks(stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        stocks,
        key=lambda stock: (-_safe_float(stock.get("volume")), stock.get("code") or "", stock.get("name") or ""),
    )


def _sector_stocks_with_ratios(sector_name: str, market_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    stocks = [_normalize_stock(stock) for stock in _raw_sector_stocks(sector_name, market_data)]
    sorted_stocks = _sort_stocks(stocks)
    total_volume = sum(_safe_float(stock.get("volume")) for stock in sorted_stocks)
    for stock in sorted_stocks:
        stock["volume_ratio_in_sector"] = (
            _safe_float(stock.get("volume")) / total_volume if total_volume > 0 else 0.0
        )
    return sorted_stocks


def _stock_identity(stock: Dict[str, Any]) -> str:
    return stock.get("code") or stock.get("name") or ""


def _compact_stock(stock: Dict[str, Any], include_support: bool = False) -> Dict[str, Any]:
    result = {
        "code": stock.get("code") or "",
        "name": stock.get("name") or "",
        "volume": _safe_float(stock.get("volume")),
        "volume_ratio_in_sector": _safe_float(stock.get("volume_ratio_in_sector")),
        "change_pct": _safe_float(stock.get("change_pct")),
        "volume_ratio": _safe_float(stock.get("volume_ratio")),
    }
    if stock.get("is_new_high"):
        result["is_new_high"] = True
    if stock.get("new_high_dates"):
        result["new_high_dates"] = list(stock.get("new_high_dates") or [])
    if include_support:
        result["intraday_support"] = _intraday_support(stock)
    return result


def _core_anchor_stocks(stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        stock
        for stock in stocks
        if _safe_float(stock.get("volume")) > 100
        and _safe_float(stock.get("volume_ratio_in_sector")) > 0.15
    ]


def _core_anchor_status(stock: Dict[str, Any]) -> str:
    change_pct = _safe_float(stock.get("change_pct"))
    volume_ratio = _safe_float(stock.get("volume_ratio"))

    if change_pct > 0 and volume_ratio >= 1.2:
        return "放量上涨"
    if -2 < change_pct <= 0 and volume_ratio >= 0.8:
        return "横住不破"
    if change_pct < -2 and volume_ratio < 0.8:
        return "缩量下跌"
    if change_pct < -2 and volume_ratio >= 1.2:
        return "放量下杀"
    return "待观察"


def _empty_core_anchor() -> Dict[str, Any]:
    return {
        "code": "",
        "name": "",
        "volume": 0.0,
        "volume_ratio_in_sector": 0.0,
        "change_pct": 0.0,
        "volume_ratio": 0.0,
        "status": "待观察",
    }


def _core_anchor_from_stocks(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    anchors = _core_anchor_stocks(stocks)
    if not anchors:
        return _empty_core_anchor()

    anchor = anchors[0]
    result = _compact_stock(anchor)
    result["status"] = _core_anchor_status(anchor)
    return result


def _avg_change(stocks: List[Dict[str, Any]]) -> float:
    if not stocks:
        return 0.0
    return sum(_safe_float(stock.get("change_pct")) for stock in stocks) / len(stocks)


def _volume_ratio(stocks: List[Dict[str, Any]], total_volume: float) -> float:
    if total_volume <= 0:
        return 0.0
    return sum(_safe_float(stock.get("volume")) for stock in stocks) / total_volume


def _leader_and_core_sets(stocks: List[Dict[str, Any]]):
    leaders = stocks[:2]
    core_anchors = _core_anchor_stocks(stocks)
    core_ids = {_stock_identity(stock) for stock in leaders + core_anchors if _stock_identity(stock)}
    core_group = [stock for stock in stocks if _stock_identity(stock) in core_ids]
    followers = [stock for stock in stocks if _stock_identity(stock) not in core_ids]
    return leaders, core_anchors, core_group, followers


def _build_relative_position(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_volume = sum(_safe_float(stock.get("volume")) for stock in stocks)
    leaders, core_anchors, core_group, followers = _leader_and_core_sets(stocks)

    core_total_volume_ratio = _volume_ratio(core_group, total_volume)
    core_follower_change_gap = _avg_change(core_group) - _avg_change(followers)

    if core_total_volume_ratio > 0.5 and core_follower_change_gap > 5:
        conclusion = "资金向核心集中"
    elif core_total_volume_ratio < 0.4 and core_follower_change_gap < 3:
        conclusion = "资金扩散"
    else:
        conclusion = "资金分布待确认"

    return {
        "leaders": [_compact_stock(stock) for stock in leaders],
        "core_anchors": [_compact_stock(stock) | {"status": _core_anchor_status(stock)} for stock in core_anchors],
        "followers": [_compact_stock(stock) for stock in followers],
        "leader_avg_change": _avg_change(leaders),
        "core_avg_change": _avg_change(core_anchors),
        "follower_avg_change": _avg_change(followers),
        "leader_volume_ratio": _volume_ratio(leaders, total_volume),
        "core_volume_ratio": _volume_ratio(core_anchors, total_volume),
        "follower_volume_ratio": _volume_ratio(followers, total_volume),
        "core_total_volume_ratio": core_total_volume_ratio,
        "core_follower_change_gap": core_follower_change_gap,
        "conclusion": conclusion,
    }


def _intraday_support(stock: Dict[str, Any]) -> str:
    intraday_high = _safe_float(stock.get("intraday_high"))
    close = _safe_float(stock.get("close"))

    if intraday_high > 0 and close > 0:
        close_position = close / intraday_high
        if close_position >= 0.97:
            return "强"
        if close_position >= 0.93:
            return "中"
        return "弱"

    if stock.get("is_new_high"):
        return "中"
    return "弱"


def _combined_support(support_values: List[str], stocks: List[Dict[str, Any]] = None) -> str:
    if not support_values:
        return "弱"
    ranks = {"弱": 0, "中": 1, "强": 2}
    counts = {label: support_values.count(label) for label in ranks}
    top_count = max(counts.values())
    count_winners = [label for label, count in counts.items() if count == top_count]
    if len(count_winners) == 1 and top_count > len(support_values) / 2:
        return count_winners[0]

    if stocks:
        volume_by_support = {label: 0.0 for label in ranks}
        for support, stock in zip(support_values, stocks):
            volume_by_support[support] = volume_by_support.get(support, 0.0) + _safe_float(stock.get("volume"))
        return max(volume_by_support, key=lambda label: (volume_by_support[label], ranks.get(label, 0)))

    return max(count_winners, key=lambda label: ranks.get(label, 0))


def _elastic_carrier_from_stocks(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    elastic_stocks = [
        stock
        for stock in stocks
        if 50 <= _safe_float(stock.get("volume")) <= 150
        and _safe_float(stock.get("change_pct")) > 5
        and stock.get("is_new_high")
    ]
    elastic_stocks = _sort_stocks(elastic_stocks)
    support_values = [_intraday_support(stock) for stock in elastic_stocks]

    return {
        "count": len(elastic_stocks),
        "stocks": [_compact_stock(stock, include_support=True) for stock in elastic_stocks],
        "new_high_count": sum(1 for stock in elastic_stocks if stock.get("is_new_high")),
        "intraday_support": _combined_support(support_values, elastic_stocks),
    }


def _follower_support_quality_from_stocks(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_volume = sum(_safe_float(stock.get("volume")) for stock in stocks)
    _, _, _, followers = _leader_and_core_sets(stocks)
    avg_change = _avg_change(followers)
    gain_5pct_count = sum(1 for stock in followers if _safe_float(stock.get("change_pct")) > 5)
    gain_3pct_count = sum(1 for stock in followers if _safe_float(stock.get("change_pct")) > 3)
    follower_volume_ratio = _volume_ratio(followers, total_volume)

    if gain_5pct_count >= 5 and gain_3pct_count >= 10 and follower_volume_ratio > 0.4:
        grade = "A"
    elif gain_5pct_count >= 3 and gain_3pct_count >= 5:
        grade = "B"
    else:
        grade = "C"

    return {
        "grade": grade,
        "avg_change": avg_change,
        "gain_5pct_count": gain_5pct_count,
        "gain_3pct_count": gain_3pct_count,
        "volume_ratio": follower_volume_ratio,
        "description": (
            f"后排承接{grade}级，涨幅>5% {gain_5pct_count}只，"
            f"涨幅>3% {gain_3pct_count}只，成交占比{follower_volume_ratio * 100:.1f}%"
        ),
    }


def _has_second_wave_new_high(stock: Dict[str, Any]) -> bool:
    return len(stock.get("new_high_dates") or []) >= 2


def _second_wave_new_high_group_from_stocks(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    second_wave_stocks = [stock for stock in stocks if _has_second_wave_new_high(stock)]
    second_wave_stocks = _sort_stocks(second_wave_stocks)
    count = len(second_wave_stocks)
    total = len(stocks)
    ratio = count / total if total else 0.0

    if count:
        description = f"近5日至少2次创新高的个股有{count}只，占板块{ratio * 100:.1f}%"
    else:
        description = "近5日暂无二波创新高群"

    return {
        "count": count,
        "ratio": ratio,
        "stocks": [_compact_stock(stock) for stock in second_wave_stocks],
        "description": description,
    }


def _filtered_lianban_stocks(sector_name: str, lianban_data: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if not lianban_data:
        return []
    return [
        _normalize_stock(stock)
        for stock in lianban_data
        if isinstance(stock, dict) and _contains_sector(stock.get("sector"), sector_name)
    ]


def _turnover_share(entry: Dict[str, Any], *keys: str) -> float:
    return _safe_float(_first_value(entry, *keys))


def _total_turnover_value(
    sector_fund_flow: Dict[str, Any],
    sector_entries: List[Dict[str, Any]],
) -> float:
    turnover_keys = (
        "total_turnover",
        "total_turnover_yi",
        "market_turnover",
        "market_turnover_yi",
        "turnover",
        "total_amount",
        "total_amount_yi",
        "market_amount",
        "market_amount_yi",
        "amount_yi",
        "成交额",
        "市场成交额",
    )
    value = _first_value(sector_fund_flow or {}, *turnover_keys)
    if value not in (None, ""):
        return _safe_float(value)

    for entry in sector_entries:
        value = _first_value(entry, *turnover_keys)
        if value not in (None, ""):
            return _safe_float(value)
    return 0.0


def _build_sector_fund_flow_between_sectors(
    sector_fund_flow: Dict[str, Any],
    sector_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    changes = []
    total_turnover_change_pct = _safe_float(sector_fund_flow.get("total_turnover_change_pct"))
    total_turnover = _total_turnover_value(sector_fund_flow, sector_entries)

    for entry in sector_entries:
        sector_name = _sector_name_from_entry(entry)
        if not sector_name:
            continue
        today_share = _turnover_share(
            entry,
            "today_turnover_share",
            "turnover_share_today",
            "today_share",
            "current_turnover_share",
            "turnover_share",
        )
        yesterday_share = _turnover_share(
            entry,
            "yesterday_turnover_share",
            "turnover_share_yesterday",
            "yesterday_share",
            "prev_turnover_share",
        )
        if not total_turnover_change_pct:
            total_turnover_change_pct = _safe_float(entry.get("total_turnover_change_pct"))
        changes.append(
            {
                "sector_name": sector_name,
                "today_share": today_share,
                "yesterday_share": yesterday_share,
                "change": today_share - yesterday_share,
            }
        )

    risers = sorted([item for item in changes if item["change"] > 0], key=lambda item: item["change"], reverse=True)
    decliners = sorted([item for item in changes if item["change"] < 0], key=lambda item: item["change"])
    flow_type = "扩散分流" if total_turnover_change_pct > 10 else "轮动切换"

    flows = []
    decliner_index = 0
    riser_index = 0
    decliner_remaining = abs(decliners[decliner_index]["change"]) if decliners else 0.0
    riser_remaining = risers[riser_index]["change"] if risers else 0.0

    while decliner_index < len(decliners) and riser_index < len(risers):
        allocated_pct = min(decliner_remaining, riser_remaining)
        if allocated_pct > 0:
            decliner = decliners[decliner_index]
            riser = risers[riser_index]
            volume_change = allocated_pct * total_turnover / 100 if total_turnover > 0 else 0.0
            flows.append(
                {
                    "from_sector": decliner["sector_name"],
                    "to_sector": riser["sector_name"],
                    "from_change": decliner["change"],
                    "to_change": riser["change"],
                    "volume_change": volume_change,
                    "type": flow_type,
                }
            )

        decliner_remaining -= allocated_pct
        riser_remaining -= allocated_pct

        if decliner_remaining <= 0:
            decliner_index += 1
            if decliner_index < len(decliners):
                decliner_remaining = abs(decliners[decliner_index]["change"])
        if riser_remaining <= 0:
            riser_index += 1
            if riser_index < len(risers):
                riser_remaining = risers[riser_index]["change"]

    if flows:
        first_flow = flows[0]
        description = (
            f"{first_flow['from_sector']}成交占比下降，"
            f"{first_flow['to_sector']}成交占比上升，判断为{flow_type}"
        )
    else:
        description = "板块间成交占比变化暂不明显"

    return {
        "flows": flows,
        "description": description,
    }


def build_sector_internal_analysis_data(
    sector_fund_flow: Dict[str, Any],
    market_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    构建板块内部分析数据，供后续报告阶段消费。
    """
    sector_entries = _sector_entries(sector_fund_flow)
    sectors = []

    for entry in sector_entries[:10]:
        sector_name = _sector_name_from_entry(entry)
        if not sector_name:
            continue

        stocks = _sector_stocks_with_ratios(sector_name, market_data)
        follower_support = _follower_support_quality_from_stocks(stocks)
        second_wave_new_highs = _second_wave_new_high_group_from_stocks(stocks)
        sectors.append(
            {
                "sector_name": sector_name,
                "core_anchor": _core_anchor_from_stocks(stocks),
                "relative_position": _build_relative_position(stocks),
                "elastic_carrier": _elastic_carrier_from_stocks(stocks),
                "follower_support": follower_support,
                "follower_support_quality": follower_support,
                "second_wave_new_highs": second_wave_new_highs,
                "second_wave_new_high_group": second_wave_new_highs,
                "total_stocks": len(stocks),
                "turnover_share_change": _safe_float(entry.get("turnover_share_change")),
            }
        )

    return {
        "sectors": sectors,
        "sector_fund_flow": _build_sector_fund_flow_between_sectors(sector_fund_flow or {}, sector_entries),
    }


def extract_sector_data_from_fund_flow(
    sector_fund_flow: Dict[str, Any],
    zt_pool: List[Dict[str, Any]] = None,
    lianban_data: List[Dict[str, Any]] = None,
    market_data: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    从现有的 sector_fund_flow 数据中提取板块数据,用于扩散质量评分

    Args:
        sector_fund_flow: 现有的板块资金流向数据
        zt_pool: 涨停池数据
        lianban_data: 连板数据
        market_data: 市场数据

    Returns:
        板块数据列表,每个元素包含:
        - sector_name: 板块名称
        - data: 板块详细数据(用于评分)
    """
    sector_fund_flow = sector_fund_flow or {}
    sectors_data = []

    # 从资金流入数据中提取板块
    inflow_sectors = sector_fund_flow.get("inflow") or []

    for sector in inflow_sectors[:10]:  # 取前10个板块
        sector_name = sector.get("name") or sector.get("sector_name")
        if not sector_name:
            continue

        # 构建板块数据
        sector_data = {
            "core_anchor": _extract_core_anchor(sector_name, market_data),
            "elastic_carrier": _extract_elastic_carrier(sector_name, lianban_data, market_data),
            "limit_up_count": _count_sector_limit_ups(sector_name, zt_pool),
            "total_stocks": _estimate_sector_total_stocks(sector_name, market_data),
            "second_wave_new_highs": _count_second_wave_new_highs(sector_name, lianban_data, market_data),
            "turnover_share_change": _safe_float(sector.get("turnover_share_change"))
        }

        sectors_data.append({
            "sector_name": sector_name,
            "data": sector_data
        })

    return sectors_data


def _extract_core_anchor(sector_name: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
    """提取核心锚数据"""
    return _core_anchor_from_stocks(_sector_stocks_with_ratios(sector_name, market_data))


def _extract_elastic_carrier(
    sector_name: str,
    lianban_data: List[Dict[str, Any]] = None,
    market_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """提取弹性载体数据"""
    stocks = _sector_stocks_with_ratios(sector_name, market_data)
    lianban_new_high_count = sum(
        1 for stock in _filtered_lianban_stocks(sector_name, lianban_data) if stock.get("is_new_high")
    )
    if stocks:
        result = _elastic_carrier_from_stocks(stocks)
        if result["new_high_count"] == 0 and lianban_new_high_count:
            return {
                "count": lianban_new_high_count,
                "stocks": [],
                "new_high_count": lianban_new_high_count,
                "intraday_support": "中",
            }
        return result

    return {
        "new_high_count": lianban_new_high_count,
        "intraday_support": "中" if lianban_new_high_count else "弱"
    }


def _count_sector_limit_ups(sector_name: str, zt_pool: List[Dict[str, Any]]) -> int:
    """统计板块涨停数"""
    if not zt_pool:
        return 0

    count = 0
    for stock in zt_pool:
        if sector_name in str(stock.get("sector") or ""):
            count += 1

    return count


def _estimate_sector_total_stocks(sector_name: str, market_data: Dict[str, Any] = None) -> int:
    """估算板块总股票数"""
    stocks = _sector_stocks_with_ratios(sector_name, market_data)
    if stocks:
        return len(stocks)
    return 20


def _count_second_wave_new_highs(
    sector_name: str,
    lianban_data: List[Dict[str, Any]] = None,
    market_data: Dict[str, Any] = None
) -> int:
    """统计二波创新高数"""
    stocks = []
    stocks.extend(_sector_stocks_with_ratios(sector_name, market_data))
    stocks.extend(_filtered_lianban_stocks(sector_name, lianban_data))

    seen = set()
    count = 0
    for stock in stocks:
        identity = _stock_identity(stock)
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        if _has_second_wave_new_high(stock):
            count += 1
    return count


def build_enhanced_sector_fund_flow_report(
    sector_fund_flow: Dict[str, Any],
    zt_pool: List[Dict[str, Any]] = None,
    lianban_data: List[Dict[str, Any]] = None,
    market_data: Dict[str, Any] = None,
    sector_turnover_history: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    构建增强的板块资金流向报告

    Args:
        sector_fund_flow: 现有的板块资金流向数据
        zt_pool: 涨停池数据
        lianban_data: 连板数据
        market_data: 市场数据
        sector_turnover_history: 板块成交占比历史数据

    Returns:
        {
            "original_fund_flow": 原始资金流向数据,
            "diffusion_quality": 板块扩散质量评分,
            "turnover_trend": 板块成交占比趋势,
            "quant_environment": 量化环境识别,
            "markdown_sections": Markdown章节列表
        }
    """
    sector_fund_flow = sector_fund_flow or {}

    # 1. 提取板块数据
    sectors_data = extract_sector_data_from_fund_flow(
        sector_fund_flow,
        zt_pool,
        lianban_data,
        market_data
    )

    # 2. 计算板块扩散质量
    diffusion_summary = build_sector_diffusion_summary(sectors_data)

    # 3. 构建板块成交占比趋势
    turnover_summary = None
    if sector_turnover_history:
        turnover_summary = build_top5_sector_turnover_summary(sector_turnover_history)

    # 4. 识别量化环境
    quant_environment = None
    if market_data:
        quant_environment = detect_quant_environment(market_data)

    # 5. 生成Markdown章节
    markdown_sections = _build_markdown_sections(
        sector_fund_flow,
        diffusion_summary,
        turnover_summary,
        quant_environment
    )

    return {
        "original_fund_flow": sector_fund_flow,
        "diffusion_quality": diffusion_summary,
        "turnover_trend": turnover_summary,
        "quant_environment": quant_environment,
        "markdown_sections": markdown_sections
    }


def _build_markdown_sections(
    sector_fund_flow: Dict[str, Any],
    diffusion_summary: Dict[str, Any],
    turnover_summary: Dict[str, Any],
    quant_environment: Dict[str, Any]
) -> List[str]:
    """构建Markdown章节"""
    sections = []

    # 章节1: 板块扩散质量评分
    if diffusion_summary and diffusion_summary.get("sectors"):
        sections.append("### 板块扩散质量评分")
        sections.append("")
        sections.append("| 板块 | 总分 | 评级 | 核心锚 | 弹性载体 | 后排承接 | 二波新高 | 成交占比 |")
        sections.append("|------|------|------|--------|----------|----------|----------|----------|")

        for sector in diffusion_summary["sectors"][:5]:
            details = sector["details"]
            sections.append(
                f"| {sector['sector_name']} | "
                f"{sector['total_score']} | "
                f"{sector['level']} | "
                f"{details['core_anchor']['score']}/30 | "
                f"{details['elastic_carrier']['score']}/25 | "
                f"{details['follower_support']['score']}/20 | "
                f"{details['second_wave_new_highs']['score']}/15 | "
                f"{details['turnover_share_change']['score']}/10 |"
            )

        sections.append("")
        sections.append(f"**结论**: {diffusion_summary['summary']}")
        sections.append("")

    # 章节2: 板块成交占比趋势
    if turnover_summary and turnover_summary.get("sectors"):
        sections.append("### 板块成交占比趋势 (近5日)")
        sections.append("")
        sections.append("| 板块 | 最新占比 | 3日趋势 | 5日均线 | 趋势序列 | 结论 |")
        sections.append("|------|----------|---------|---------|----------|------|")

        for sector in turnover_summary["sectors"][:5]:
            sections.append(
                f"| {sector['sector_name']} | "
                f"{sector['latest_share']:.1f}% | "
                f"{sector['trend_3d']} | "
                f"{sector['ma5']:.1f}% | "
                f"{sector['formatted_series']} | "
                f"{'⚠️ ' if sector['trend_3d'] == '分化' else ''}"
                f"{'✅ ' if sector['trend_3d'] == '强化' else ''}"
                f"{sector['trend_3d']} |"
            )

        sections.append("")

        # 量化离场/进场信号
        if turnover_summary.get("quant_exit_signal"):
            sections.append(f"**⚠️ 量化离场信号**: {turnover_summary['summary']}")
        elif turnover_summary.get("quant_entry_signal"):
            sections.append(f"**✅ 量化进场信号**: {turnover_summary['summary']}")
        else:
            sections.append(f"**市场状态**: {turnover_summary['summary']}")

        sections.append("")

    # 章节3: 量化环境识别
    if quant_environment:
        nested_environment = quant_environment.get("environment")
        env = nested_environment if isinstance(nested_environment, dict) and nested_environment else quant_environment
        sections.append("### 量化环境识别")
        sections.append("")
        sections.append(f"**当前环境**: {env.get('summary', '待识别')}")
        sections.append("")

        if env.get("modes"):
            sections.append("**检测到的模式**:")
            for mode in env["modes"]:
                sections.append(f"- **{mode['mode']}**: {mode['description']}")
                sections.append(f"  - 证据: {mode['evidence']}")
                sections.append(f"  - 动作: {mode['action']}")

        sections.append("")
        sections.append(f"**动作建议**: {env.get('action', '继续观察')}")
        sections.append("")

    # 章节4: 原始资金流向数据(保留现有格式)
    sections.append("### 资金流入TOP10")
    sections.append("")
    sections.append("| 排名 | 板块 | 净流入 | 涨跌幅 |")
    sections.append("|------|------|--------|--------|")

    inflow = sector_fund_flow.get("inflow") or []
    for idx, sector in enumerate(inflow[:10], 1):
        sections.append(
            f"| {idx} | "
            f"{sector.get('name', '?')} | "
            f"{_safe_float(sector.get('zljlr', 0)):+.2f}亿 | "
            f"{_safe_float(sector.get('zdf', 0)):+.2f}% |"
        )

    sections.append("")

    return sections
