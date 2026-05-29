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
    "extract_sector_data_from_fund_flow",
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
            "elastic_carrier": _extract_elastic_carrier(sector_name, lianban_data),
            "limit_up_count": _count_sector_limit_ups(sector_name, zt_pool),
            "total_stocks": _estimate_sector_total_stocks(sector_name),
            "second_wave_new_highs": _count_second_wave_new_highs(sector_name, lianban_data),
            "turnover_share_change": _safe_float(sector.get("turnover_share_change"))
        }

        sectors_data.append({
            "sector_name": sector_name,
            "data": sector_data
        })

    return sectors_data


def _extract_core_anchor(sector_name: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
    """提取核心锚数据"""
    # TODO: 从市场数据中提取该板块的核心锚(中军)
    # 这里需要根据实际数据结构来实现
    return {
        "status": "待补充",
        "change_pct": 0.0,
        "volume_ratio": 0.0
    }


def _extract_elastic_carrier(sector_name: str, lianban_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """提取弹性载体数据"""
    # TODO: 从连板数据中提取该板块的弹性载体
    new_high_count = 0
    if lianban_data:
        for stock in lianban_data:
            if sector_name in str(stock.get("sector") or ""):
                if stock.get("is_new_high"):
                    new_high_count += 1

    return {
        "new_high_count": new_high_count,
        "intraday_support": "待补充"
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


def _estimate_sector_total_stocks(sector_name: str) -> int:
    """估算板块总股票数"""
    # TODO: 从数据库或缓存中获取板块总股票数
    # 这里先用一个估算值
    return 20


def _count_second_wave_new_highs(sector_name: str, lianban_data: List[Dict[str, Any]]) -> int:
    """统计二波创新高数"""
    # TODO: 从连板数据中统计二波创新高
    return 0


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
        env = quant_environment.get("environment") or {}
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
