#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块成交占比连续追踪模块

追踪TOP5板块的3日/5日成交占比变化,用于判断:
1. 量化资金是否仍在当前板块 (成交占比扩张 vs 收缩)
2. 板块是否从主升进入分化 (占比回落)
3. 是否应该降低攻击频次或退出 (占比持续收缩)

输出示例:
```
板块成交占比连续追踪 (近5日):

主线板块: AI算力
  - 3日占比: 18% → 15% → 13% (收缩)
  - 5日均线: 16.2%
  - 趋势: 分化中
  - 结论: 量化离场信号,降低攻击频次

竞争板块: 人形机器人
  - 3日占比: 5% → 8% → 12% (扩张)
  - 5日均线: 8.3%
  - 趋势: 强化中
  - 结论: 板块先铺阶段,等二波创新高群
```
"""

from __future__ import annotations
from typing import List, Dict, Any

__all__ = [
    "build_sector_turnover_trend",
    "build_top5_sector_turnover_summary",
    "detect_quant_exit_signal",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _calculate_moving_average(values: List[float], window: int) -> float:
    """计算移动平均"""
    if not values or len(values) < window:
        return 0.0
    return sum(values[-window:]) / window


def _detect_trend(values: List[float]) -> str:
    """
    检测趋势

    Returns:
        "强化" | "分化" | "持平" | "震荡"
    """
    if len(values) < 2:
        return "待累计"

    # 取最近3个值
    recent = values[-3:] if len(values) >= 3 else values

    # 计算首尾差值
    delta = recent[-1] - recent[0]

    # 判断趋势
    if delta >= 1.0:
        return "强化"
    elif delta <= -1.0:
        return "分化"
    elif abs(delta) < 0.3:
        return "持平"
    else:
        return "震荡"


def _format_trend_series(values: List[float]) -> str:
    """格式化趋势序列"""
    if not values:
        return "待累计"

    # 取最近3个值
    recent = values[-3:] if len(values) >= 3 else values

    # 格式化
    formatted = [f"{v:.1f}%" for v in recent]

    # 判断方向
    if len(recent) >= 2:
        if recent[-1] > recent[0]:
            direction = "(扩张)"
        elif recent[-1] < recent[0]:
            direction = "(收缩)"
        else:
            direction = "(持平)"
    else:
        direction = ""

    return " → ".join(formatted) + " " + direction


def _build_conclusion(sector_name: str, trend: str, ma5: float, latest: float) -> str:
    """
    构建结论

    Args:
        sector_name: 板块名称
        trend: 趋势 ("强化" | "分化" | "持平" | "震荡")
        ma5: 5日均线
        latest: 最新值

    Returns:
        结论文本
    """
    if trend == "强化":
        if latest >= ma5 * 1.1:
            return f"{sector_name}成交占比明显扩张,量化资金仍在,继续围绕核心做减法"
        else:
            return f"{sector_name}成交占比扩张,但未突破5日均线,观察持续性"

    elif trend == "分化":
        if latest <= ma5 * 0.9:
            return f"{sector_name}成交占比明显收缩,量化离场信号,降低攻击频次"
        else:
            return f"{sector_name}成交占比回落,先防分化,不追高位加速"

    elif trend == "持平":
        return f"{sector_name}成交占比持平,继续观察承接,不做多线扩散"

    else:  # 震荡
        return f"{sector_name}成交占比震荡,边走边确认,等窗口"


def build_sector_turnover_trend(
    sector_name: str,
    turnover_history: List[Dict[str, Any]],
    window_3d: int = 3,
    window_5d: int = 5
) -> Dict[str, Any]:
    """
    构建单个板块的成交占比趋势

    Args:
        sector_name: 板块名称
        turnover_history: 成交占比历史数据,每个元素包含:
            - date: 日期
            - turnover_share_pct: 成交占比
            - sector_turnover: 板块成交额
            - total_turnover: 两市成交额
        window_3d: 3日窗口
        window_5d: 5日窗口

    Returns:
        {
            "sector_name": str,
            "latest_share": float,
            "trend_3d": str,  # "强化" | "分化" | "持平" | "震荡"
            "trend_5d": str,
            "ma3": float,
            "ma5": float,
            "series_3d": [float],
            "series_5d": [float],
            "formatted_series": str,
            "conclusion": str,
            "action": str
        }
    """
    # 提取成交占比序列
    shares = [
        _safe_float(item.get("turnover_share_pct"))
        for item in turnover_history
        if _safe_float(item.get("turnover_share_pct")) > 0
    ]

    if not shares:
        return {
            "sector_name": sector_name,
            "latest_share": 0.0,
            "trend_3d": "待累计",
            "trend_5d": "待累计",
            "ma3": 0.0,
            "ma5": 0.0,
            "series_3d": [],
            "series_5d": [],
            "formatted_series": "待累计",
            "conclusion": f"{sector_name}成交占比数据不足,无法判断趋势",
            "action": "等待数据累计"
        }

    # 计算移动平均
    ma3 = _calculate_moving_average(shares, window_3d)
    ma5 = _calculate_moving_average(shares, window_5d)

    # 检测趋势
    trend_3d = _detect_trend(shares[-window_3d:] if len(shares) >= window_3d else shares)
    trend_5d = _detect_trend(shares[-window_5d:] if len(shares) >= window_5d else shares)

    # 格式化序列
    formatted_series = _format_trend_series(shares)

    # 最新值
    latest_share = shares[-1]

    # 构建结论
    conclusion = _build_conclusion(sector_name, trend_3d, ma5, latest_share)

    # 构建动作建议
    if trend_3d == "强化":
        action = f"继续围绕{sector_name}做减法,不追支线分流"
    elif trend_3d == "分化":
        action = f"{sector_name}虽在中心,但占比回落,先防分化,不追高位加速"
    else:
        action = f"继续围绕{sector_name}观察承接,不做多线扩散"

    return {
        "sector_name": sector_name,
        "latest_share": latest_share,
        "trend_3d": trend_3d,
        "trend_5d": trend_5d,
        "ma3": ma3,
        "ma5": ma5,
        "series_3d": shares[-window_3d:] if len(shares) >= window_3d else shares,
        "series_5d": shares[-window_5d:] if len(shares) >= window_5d else shares,
        "formatted_series": formatted_series,
        "conclusion": conclusion,
        "action": action
    }


def build_top5_sector_turnover_summary(
    sectors_turnover_history: List[Dict[str, Any]],
    top_n: int = 5
) -> Dict[str, Any]:
    """
    构建TOP5板块的成交占比趋势摘要

    Args:
        sectors_turnover_history: 多个板块的成交占比历史数据,每个元素包含:
            - sector_name: 板块名称
            - history: 历史数据列表
        top_n: 取前N个板块

    Returns:
        {
            "sectors": [趋势结果列表],
            "summary": str,
            "expanding_sectors": [str],  # 成交占比扩张的板块
            "shrinking_sectors": [str],  # 成交占比收缩的板块
            "quant_exit_signal": bool,  # 量化离场信号
            "quant_entry_signal": bool  # 量化进场信号
        }
    """
    results = []

    for item in sectors_turnover_history[:top_n]:
        sector_name = item.get("sector_name") or item.get("name")
        history = item.get("history") or []

        if not sector_name:
            continue

        trend = build_sector_turnover_trend(sector_name, history)
        results.append(trend)

    # 按最新成交占比排序
    results.sort(key=lambda x: x["latest_share"], reverse=True)

    # 找出扩张和收缩的板块
    expanding_sectors = [r["sector_name"] for r in results if r["trend_3d"] == "强化"]
    shrinking_sectors = [r["sector_name"] for r in results if r["trend_3d"] == "分化"]

    # 判断量化离场/进场信号
    quant_exit_signal = False
    quant_entry_signal = False

    if results:
        top_sector = results[0]

        # 量化离场信号: 主线板块成交占比持续收缩
        if top_sector["trend_3d"] == "分化" and top_sector["latest_share"] < top_sector["ma5"] * 0.9:
            quant_exit_signal = True

        # 量化进场信号: 新板块成交占比持续扩张
        if len(expanding_sectors) >= 2:
            quant_entry_signal = True

    # 生成摘要
    if not results:
        summary = "无板块成交占比数据,无法判断趋势"
    elif quant_exit_signal:
        summary = f"⚠️ 量化离场信号: {results[0]['sector_name']}成交占比持续收缩({results[0]['formatted_series']}),降低攻击频次"
    elif quant_entry_signal:
        summary = f"✅ 量化进场信号: {len(expanding_sectors)}个板块成交占比扩张({', '.join(expanding_sectors[:2])}),观察二波创新高群"
    else:
        summary = f"主线板块{results[0]['sector_name']}成交占比{results[0]['formatted_series']},趋势{results[0]['trend_3d']}"

    return {
        "sectors": results,
        "summary": summary,
        "expanding_sectors": expanding_sectors,
        "shrinking_sectors": shrinking_sectors,
        "quant_exit_signal": quant_exit_signal,
        "quant_entry_signal": quant_entry_signal
    }


def detect_quant_exit_signal(sector_turnover_trend: Dict[str, Any]) -> Dict[str, bool]:
    """
    检测量化离场信号

    量化离场的三项共振:
    1. 板块成交占比回落
    2. 后排掉队
    3. 核心跌回VWAP或关键均线

    Args:
        sector_turnover_trend: 板块成交占比趋势数据,包含:
            - trend_3d: 3日趋势
            - latest_share: 最新成交占比
            - ma5: 5日均线
            - follower_status: 后排状态 (可选)
            - core_status: 核心状态 (可选)

    Returns:
        {
            "signal_1_turnover_shrink": bool,  # 成交占比回落
            "signal_2_follower_dropout": bool,  # 后排掉队
            "signal_3_core_breakdown": bool,  # 核心跌回关键位
            "all_signals": bool,  # 三项共振
            "action": str
        }
    """
    # 信号1: 成交占比回落
    signal_1 = (
        sector_turnover_trend.get("trend_3d") == "分化" and
        sector_turnover_trend.get("latest_share", 0) < sector_turnover_trend.get("ma5", 0) * 0.9
    )

    # 信号2: 后排掉队 (如果有数据)
    follower_status = sector_turnover_trend.get("follower_status")
    if follower_status:
        signal_2 = follower_status in ("掉队", "弱")
    else:
        signal_2 = False  # 无数据时不判断

    # 信号3: 核心跌回关键位 (如果有数据)
    core_status = sector_turnover_trend.get("core_status")
    if core_status:
        signal_3 = core_status in ("跌回VWAP", "跌破均线", "失去承接")
    else:
        signal_3 = False  # 无数据时不判断

    # 三项共振
    all_signals = signal_1 and signal_2 and signal_3

    # 动作建议
    if all_signals:
        action = "量化离场三项共振,先退出或降级,不等故事证伪"
    elif signal_1:
        action = "成交占比回落,先防分化,不追高位加速"
    else:
        action = "继续观察,暂无明确离场信号"

    return {
        "signal_1_turnover_shrink": signal_1,
        "signal_2_follower_dropout": signal_2,
        "signal_3_core_breakdown": signal_3,
        "all_signals": all_signals,
        "action": action
    }
