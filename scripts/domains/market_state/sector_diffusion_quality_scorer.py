#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块扩散质量评分系统

基于《板块中枢与主线延续》理论,量化评估板块扩散质量:
- 核心锚稳定性 (30分)
- 弹性载体强度 (25分)
- 后排承接度 (20分)
- 二波创新高群 (15分)
- 成交占比变化 (10分)

用于判断:
1. 量化资金是否仍在当前板块
2. 板块是否从"先铺"进入"筛选核心"阶段
3. 是否应该降低攻击频次或退出
"""

from __future__ import annotations

__all__ = [
    "calculate_sector_diffusion_quality",
    "build_sector_diffusion_summary",
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


def _score_core_anchor_stability(sector_data):
    """
    核心锚稳定性 (30分)

    判断标准:
    - 中军放量上涨或横住不破: 30分
    - 中军缩量横盘: 15分
    - 中军下跌或失去承接: 0分
    """
    core_anchor = sector_data.get("core_anchor") or {}

    # 中军状态
    anchor_status = str(core_anchor.get("status") or "").strip()
    anchor_change_pct = _safe_float(core_anchor.get("change_pct"))
    anchor_volume_ratio = _safe_float(core_anchor.get("volume_ratio"), 1.0)

    # 中军放量上涨
    if anchor_change_pct > 0 and anchor_volume_ratio >= 1.2:
        return {
            "score": 30,
            "label": "中军放量上涨",
            "detail": f"涨幅{anchor_change_pct:+.2f}%, 量比{anchor_volume_ratio:.2f}倍"
        }

    # 中军横住不破
    if -2 < anchor_change_pct <= 0 and anchor_volume_ratio >= 0.8:
        return {
            "score": 30,
            "label": "中军横住不破",
            "detail": f"涨幅{anchor_change_pct:+.2f}%, 量比{anchor_volume_ratio:.2f}倍"
        }

    # 中军缩量横盘
    if -2 < anchor_change_pct <= 2 and anchor_volume_ratio < 0.8:
        return {
            "score": 15,
            "label": "中军缩量横盘",
            "detail": f"涨幅{anchor_change_pct:+.2f}%, 量比{anchor_volume_ratio:.2f}倍"
        }

    # 中军下跌
    return {
        "score": 0,
        "label": "中军下跌或失去承接",
        "detail": f"涨幅{anchor_change_pct:+.2f}%, 量比{anchor_volume_ratio:.2f}倍"
    }


def _score_elastic_carrier_strength(sector_data):
    """
    弹性载体强度 (25分)

    判断标准:
    - 高弹性标的创新高 AND 分时承接好: 25分
    - 高弹性标的创新高 BUT 分时承接一般: 15分
    - 高弹性标的未创新高: 0分
    """
    elastic_carrier = sector_data.get("elastic_carrier") or {}

    new_high_count = _safe_int(elastic_carrier.get("new_high_count"))
    intraday_support = str(elastic_carrier.get("intraday_support") or "").strip()

    if new_high_count >= 1 and intraday_support in ("强", "稳定"):
        return {
            "score": 25,
            "label": "弹性载体创新高且承接好",
            "detail": f"{new_high_count}只创新高, 分时{intraday_support}"
        }

    if new_high_count >= 1:
        return {
            "score": 15,
            "label": "弹性载体创新高但承接一般",
            "detail": f"{new_high_count}只创新高, 分时{intraday_support or '待观察'}"
        }

    return {
        "score": 0,
        "label": "弹性载体未创新高",
        "detail": "无创新高标的"
    }


def _score_follower_support(sector_data):
    """
    后排承接度 (20分)

    判断标准:
    - 后排涨停数 / 板块总股票数 * 20
    """
    limit_up_count = _safe_int(sector_data.get("limit_up_count"))
    total_stocks = _safe_int(sector_data.get("total_stocks"), 1)

    ratio = limit_up_count / total_stocks if total_stocks > 0 else 0
    score = min(int(ratio * 20), 20)

    return {
        "score": score,
        "label": f"后排承接{score}/20分",
        "detail": f"{limit_up_count}/{total_stocks}涨停, 占比{ratio*100:.1f}%"
    }


def _score_second_wave_new_highs(sector_data):
    """
    二波创新高群 (15分)

    判断标准:
    - 二波有3只以上创新高: 15分
    - 二波有1-2只创新高: 8分
    - 二波无创新高: 0分
    """
    second_wave_new_highs = _safe_int(sector_data.get("second_wave_new_highs"))

    if second_wave_new_highs >= 3:
        return {
            "score": 15,
            "label": "二波创新高群充分",
            "detail": f"{second_wave_new_highs}只二波创新高"
        }

    if second_wave_new_highs >= 1:
        return {
            "score": 8,
            "label": "二波创新高群不足",
            "detail": f"仅{second_wave_new_highs}只二波创新高"
        }

    return {
        "score": 0,
        "label": "无二波创新高",
        "detail": "板块扩散失败"
    }


def _score_turnover_share_change(sector_data):
    """
    成交占比变化 (10分)

    判断标准:
    - 成交占比扩张(+1.0pct以上): 10分
    - 成交占比小幅扩张(+0.3~1.0pct): 6分
    - 成交占比持平(-0.3~+0.3pct): 3分
    - 成交占比收缩: 0分
    """
    turnover_share_change = _safe_float(sector_data.get("turnover_share_change"))

    if turnover_share_change >= 1.0:
        return {
            "score": 10,
            "label": "成交占比明显扩张",
            "detail": f"{turnover_share_change:+.1f}pct"
        }

    if turnover_share_change >= 0.3:
        return {
            "score": 6,
            "label": "成交占比小幅扩张",
            "detail": f"{turnover_share_change:+.1f}pct"
        }

    if turnover_share_change >= -0.3:
        return {
            "score": 3,
            "label": "成交占比持平",
            "detail": f"{turnover_share_change:+.1f}pct"
        }

    return {
        "score": 0,
        "label": "成交占比收缩",
        "detail": f"{turnover_share_change:+.1f}pct"
    }


def calculate_sector_diffusion_quality(sector_name, sector_data):
    """
    计算板块扩散质量总分

    Args:
        sector_name: 板块名称
        sector_data: 板块数据字典,包含:
            - core_anchor: 核心锚数据
            - elastic_carrier: 弹性载体数据
            - limit_up_count: 涨停数
            - total_stocks: 板块总股票数
            - second_wave_new_highs: 二波创新高数
            - turnover_share_change: 成交占比变化

    Returns:
        {
            "sector_name": str,
            "total_score": int,
            "level": str,  # "强扩散" | "中等扩散" | "弱扩散"
            "details": {
                "core_anchor": {...},
                "elastic_carrier": {...},
                "follower_support": {...},
                "second_wave_new_highs": {...},
                "turnover_share_change": {...}
            },
            "conclusion": str,
            "action": str
        }
    """
    # 计算各项得分
    core_anchor_result = _score_core_anchor_stability(sector_data)
    elastic_carrier_result = _score_elastic_carrier_strength(sector_data)
    follower_support_result = _score_follower_support(sector_data)
    second_wave_result = _score_second_wave_new_highs(sector_data)
    turnover_result = _score_turnover_share_change(sector_data)

    # 总分
    total_score = (
        core_anchor_result["score"] +
        elastic_carrier_result["score"] +
        follower_support_result["score"] +
        second_wave_result["score"] +
        turnover_result["score"]
    )

    # 评级
    if total_score >= 70:
        level = "强扩散"
        conclusion = f"{sector_name}扩散质量优秀,量化资金仍在,可继续围绕核心寻找参与资格"
        action = f"继续围绕{sector_name}核心做减法,不追支线分流"
    elif total_score >= 50:
        level = "中等扩散"
        conclusion = f"{sector_name}扩散质量中等,部分指标不足,降低攻击频次"
        action = "等竞价、开盘承接、回封或09:50-10:10窗口,不追后排"
    else:
        level = "弱扩散"
        conclusion = f"{sector_name}扩散质量不足,量化资金可能离场,先防分化"
        action = "不追高位加速,先处理旧仓,不为新候选分散资金"

    return {
        "sector_name": sector_name,
        "total_score": total_score,
        "level": level,
        "details": {
            "core_anchor": core_anchor_result,
            "elastic_carrier": elastic_carrier_result,
            "follower_support": follower_support_result,
            "second_wave_new_highs": second_wave_result,
            "turnover_share_change": turnover_result
        },
        "conclusion": conclusion,
        "action": action
    }


def build_sector_diffusion_summary(sectors_data):
    """
    构建多个板块的扩散质量摘要

    Args:
        sectors_data: 板块数据列表,每个元素包含sector_name和sector_data

    Returns:
        {
            "sectors": [质量评分结果列表],
            "summary": str,
            "top_sector": str,
            "weak_sectors": [str]
        }
    """
    results = []

    for item in sectors_data or []:
        sector_name = item.get("sector_name") or item.get("name")
        sector_data = item.get("data") or item

        if not sector_name:
            continue

        result = calculate_sector_diffusion_quality(sector_name, sector_data)
        results.append(result)

    # 按总分排序
    results.sort(key=lambda x: x["total_score"], reverse=True)

    # 找出最强和最弱板块
    top_sector = results[0]["sector_name"] if results else None
    weak_sectors = [r["sector_name"] for r in results if r["total_score"] < 50]

    # 生成摘要
    if not results:
        summary = "无板块数据,无法评估扩散质量"
    elif results[0]["total_score"] >= 70:
        summary = f"{top_sector}扩散质量{results[0]['total_score']}分(强扩散),量化资金仍在,继续围绕核心做减法"
    elif results[0]["total_score"] >= 50:
        summary = f"{top_sector}扩散质量{results[0]['total_score']}分(中等扩散),降低攻击频次,等窗口确认"
    else:
        summary = f"所有板块扩散质量不足,最高{results[0]['total_score']}分,量化资金可能离场,先防分化"

    return {
        "sectors": results,
        "summary": summary,
        "top_sector": top_sector,
        "weak_sectors": weak_sectors
    }
