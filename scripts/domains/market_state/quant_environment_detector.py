#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化环境识别模块

识别当前市场是否处于量化横行环境,以及具体的量化模式:
1. 窄池子进攻 - 指数强但上涨家数弱,资金集中少数板块
2. 板块先铺再筛核心 - 多板块同步异动,等待筛选核心
3. 量化资金活跃 - 涨停分布分散,成交额集中度下降
4. 单一龙头定价权下降 - 板块节奏优先于个股强度
"""

from __future__ import annotations

__all__ = [
    "detect_market_mode",
    "detect_quant_environment",
    "build_quant_environment_summary",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
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


def _detect_narrow_pool_attack(market_data):
    """
    检测窄池子进攻模式

    特征:
    - 指数涨幅 > 1%
    - 上涨家数占比 < 40%
    - 资金集中在少数板块路径
    """
    index_change = _safe_float(market_data.get("index_change_pct"))
    up_ratio = _safe_float(market_data.get("up_ratio"))
    top50_share = _safe_float(market_data.get("top50_turnover_share_pct"))

    if index_change > 1.0 and up_ratio < 40:
        return {
            "detected": True,
            "mode": "窄池子进攻",
            "description": "指数强但上涨家数弱,资金集中少数板块路径",
            "evidence": f"指数+{index_change:.2f}%, 上涨家数{up_ratio:.1f}%, Top50占比{top50_share:.1f}%",
            "action": "只看被资金持续选择的板块路径,不把指数上涨当普涨环境",
            "risk": "未被选择的方向不能因为指数上涨而提高参与资格"
        }

    return {"detected": False}


def _detect_sector_spread_first(market_data):
    """
    检测板块先铺再筛核心模式

    特征:
    - 多板块同步异动 (3个以上板块涨停数>=3)
    - 单一龙头定价权下降 (无明显龙头)
    - 等待二波创新高群
    """
    sector_limit_up_count = _safe_int(market_data.get("sector_limit_up_count"))
    active_sector_count = _safe_int(market_data.get("active_sector_count"))
    leading_stock_dominance = _safe_float(market_data.get("leading_stock_dominance"))

    if active_sector_count >= 3 and leading_stock_dominance < 0.3:
        return {
            "detected": True,
            "mode": "板块先铺",
            "description": "资金先买出板块效应,再筛真正核心",
            "evidence": f"{active_sector_count}个板块同步异动,无明显龙头",
            "action": "等二波创新高群,不追第一波后排",
            "risk": "没有二波创新高群时,只按轮动脉冲处理"
        }

    return {"detected": False}


def _detect_quant_active(market_data):
    """
    检测量化资金活跃模式

    特征:
    - 涨停分布分散 (涨停股分布在5个以上板块)
    - 成交额集中度下降 (Top20占比 < 15%)
    - 单一龙头定价权下降
    """
    limit_up_sector_count = _safe_int(market_data.get("limit_up_sector_count"))
    top20_share = _safe_float(market_data.get("top20_turnover_share_pct"))
    leading_stock_dominance = _safe_float(market_data.get("leading_stock_dominance"))

    if limit_up_sector_count >= 5 and top20_share < 15:
        return {
            "detected": True,
            "mode": "量化横行",
            "description": "单一龙头定价权下降,板块节奏优先",
            "evidence": f"涨停分布在{limit_up_sector_count}个板块,Top20占比{top20_share:.1f}%",
            "action": "深耕板块运作规律,看资金扩散,不追单一龙头",
            "risk": "个股强度必须放回板块里验证"
        }

    return {"detected": False}


def _detect_single_leader_decline(market_data):
    """
    检测单一龙头定价权下降

    特征:
    - 龙头涨停但板块跟随度低
    - 或板块强但龙头弱
    """
    leading_stock_change = _safe_float(market_data.get("leading_stock_change_pct"))
    sector_avg_change = _safe_float(market_data.get("sector_avg_change_pct"))
    leading_stock_dominance = _safe_float(market_data.get("leading_stock_dominance"))

    # 龙头强但板块弱
    if leading_stock_change > 5 and sector_avg_change < 2:
        return {
            "detected": True,
            "mode": "龙头孤立强",
            "description": "龙头强但板块跟随度低,单一龙头定价权下降",
            "evidence": f"龙头+{leading_stock_change:.2f}%, 板块均值+{sector_avg_change:.2f}%",
            "action": "不把龙头涨停等同于全板块可做,先看板块扩散",
            "risk": "龙头炸板不等于板块立刻失败,必须同时看板块路径"
        }

    # 板块强但龙头弱
    if sector_avg_change > 3 and leading_stock_change < 1:
        return {
            "detected": True,
            "mode": "板块强龙头弱",
            "description": "板块上涨但龙头持续走弱,资金没有围绕核心形成共识",
            "evidence": f"板块均值+{sector_avg_change:.2f}%, 龙头+{leading_stock_change:.2f}%",
            "action": "板块强而龙头弱时降级,不能只看板块涨幅",
            "risk": "资金没有继续围绕核心形成共识"
        }

    return {"detected": False}


def detect_market_mode(market_data):
    """
    检测当前市场模式

    Args:
        market_data: 市场数据字典,包含:
            - index_change_pct: 指数涨跌幅
            - up_ratio: 上涨家数占比
            - top50_turnover_share_pct: Top50成交额占比
            - sector_limit_up_count: 板块涨停数
            - active_sector_count: 活跃板块数
            - leading_stock_dominance: 龙头主导度
            - limit_up_sector_count: 涨停股分布板块数
            - top20_turnover_share_pct: Top20成交额占比

    Returns:
        [
            {
                "detected": bool,
                "mode": str,
                "description": str,
                "evidence": str,
                "action": str,
                "risk": str
            },
            ...
        ]
    """
    modes = []

    # 检测窄池子进攻
    narrow_pool = _detect_narrow_pool_attack(market_data)
    if narrow_pool.get("detected"):
        modes.append(narrow_pool)

    # 检测板块先铺
    sector_spread = _detect_sector_spread_first(market_data)
    if sector_spread.get("detected"):
        modes.append(sector_spread)

    # 检测量化活跃
    quant_active = _detect_quant_active(market_data)
    if quant_active.get("detected"):
        modes.append(quant_active)

    # 检测单一龙头定价权下降
    leader_decline = _detect_single_leader_decline(market_data)
    if leader_decline.get("detected"):
        modes.append(leader_decline)

    return modes


def detect_quant_environment(market_data):
    """
    综合判断是否处于量化横行环境

    量化横行的特征:
    1. 窄池子进攻 OR 板块先铺 OR 量化活跃
    2. 单一龙头定价权下降
    3. 资金必须花小钱办大事

    Returns:
        {
            "is_quant_dominant": bool,
            "confidence": float,  # 0-1
            "modes": [检测到的模式列表],
            "summary": str,
            "action": str
        }
    """
    modes = detect_market_mode(market_data)

    if not modes:
        return {
            "is_quant_dominant": False,
            "confidence": 0.0,
            "modes": [],
            "summary": "未检测到明显的量化横行特征",
            "action": "按传统模式处理,个股强度和板块节奏并重"
        }

    # 计算置信度
    mode_names = [m["mode"] for m in modes]
    confidence = 0.0

    # 窄池子进攻 +0.3
    if "窄池子进攻" in mode_names:
        confidence += 0.3

    # 板块先铺 +0.3
    if "板块先铺" in mode_names:
        confidence += 0.3

    # 量化横行 +0.4
    if "量化横行" in mode_names:
        confidence += 0.4

    # 龙头孤立强或板块强龙头弱 +0.2
    if "龙头孤立强" in mode_names or "板块强龙头弱" in mode_names:
        confidence += 0.2

    confidence = min(confidence, 1.0)

    is_quant_dominant = confidence >= 0.5

    if is_quant_dominant:
        summary = f"量化横行环境(置信度{confidence*100:.0f}%): " + "、".join(mode_names)
        action = "深耕板块运作规律,从板块扩散看资金扩散,不追单一龙头"
    else:
        summary = f"疑似量化环境(置信度{confidence*100:.0f}%): " + "、".join(mode_names)
        action = "观察板块节奏,但仍可关注个股强度"

    return {
        "is_quant_dominant": is_quant_dominant,
        "confidence": confidence,
        "modes": modes,
        "summary": summary,
        "action": action
    }


def build_quant_environment_summary(market_data):
    """
    构建量化环境摘要报告

    Returns:
        {
            "environment": detect_quant_environment结果,
            "details": [模式详情列表],
            "recommendations": [建议列表]
        }
    """
    environment = detect_quant_environment(market_data)

    details = []
    for mode in environment["modes"]:
        details.append({
            "mode": mode["mode"],
            "description": mode["description"],
            "evidence": mode["evidence"],
            "action": mode["action"],
            "risk": mode["risk"]
        })

    recommendations = []

    if environment["is_quant_dominant"]:
        recommendations.extend([
            "板块节奏优先于个股强度,先看资金是否继续选择同一方向",
            "只看被资金持续选择的板块路径,不把每次轮动都当新主线",
            "板块成交占比扩张、宽度扩散、核心承接稳定,说明量化仍在当前方向",
            "成交占比回落、后排掉队、核心跌回VWAP或关键均线,先退出或降级",
            "不把龙头涨停等同于全板块可做,龙头炸板不等于板块立刻失败"
        ])
    else:
        recommendations.extend([
            "观察板块节奏,但仍可关注个股强度",
            "个股强度和板块节奏并重,不偏废任何一方"
        ])

    return {
        "environment": environment,
        "details": details,
        "recommendations": recommendations
    }
