#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable analysis primitives for a-daily-report.

This module owns low-level stock-code normalization and decision helpers that
are shared across the report pipeline. Keeping them together makes it easier to
extract later pipeline stages without dragging the huge entry script around.
"""

from __future__ import annotations

from typing import Any, Dict

MAX_SINGLE_TRADE_LOSS_PCT = 0.05

__all__ = [
    "MAX_SINGLE_TRADE_LOSS_PCT",
    "normalize_stock_code",
    "sector_name_matches",
    "_is_degraded_abnormal_snapshot",
    "build_stop_execution_plan",
    "calculate_price_range",
    "get_abnormal_rank_adjustment",
    "merge_position_gate",
    "_candidate_matches_mainline",
]


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_or_none(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _clamp(value, low, high):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def _same_price_level(a, b, tolerance=0.011):
    a = _safe_float(a, 0.0)
    b = _safe_float(b, 0.0)
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) <= tolerance


def _is_near_anchor_price(value, anchor, pct=0.01, min_abs=0.03):
    value = _safe_float(value, 0.0)
    anchor = _safe_float(anchor, 0.0)
    if value <= 0 or anchor <= 0:
        return False
    return abs(value - anchor) <= max(abs(anchor) * pct, min_abs)


def normalize_stock_code(code):
    """统一股票代码格式。"""
    if not code:
        return ""
    return (
        str(code)
        .replace(".SZ", "")
        .replace(".SS", "")
        .replace(".SH", "")
        .replace("sz", "")
        .replace("sh", "")
    )


def sector_name_matches(sector_a, sector_b):
    """判断两个板块名称是否指向同一方向。"""
    if not sector_a or not sector_b:
        return False
    a = str(sector_a)
    b = str(sector_b)
    return a == b or a in b or b in a


def _is_degraded_abnormal_snapshot(item):
    return bool((item or {}).get("is_degraded_snapshot"))


def build_stop_execution_plan(entry_price, structure_stop=None, structure_label="结构止损"):
    """构建盘前大概止损放哪方案。"""
    try:
        entry = float(entry_price or 0)
    except (TypeError, ValueError):
        return None

    if entry <= 0:
        return None

    hard_stop = round(entry * (1 - MAX_SINGLE_TRADE_LOSS_PCT), 2)

    structure = None
    try:
        structure = float(structure_stop or 0)
    except (TypeError, ValueError):
        structure = None

    if structure is not None and structure <= 0:
        structure = None

    effective_stop = hard_stop
    rule = "30分钟结构未落地前，先用-5%硬止损底线"
    if structure is not None:
        structure = round(structure, 2)
        effective_stop = round(max(structure, hard_stop), 2)
        if structure > hard_stop:
            rule = f"{structure_label}优先"
        elif structure < hard_stop:
            rule = f"{structure_label}过深，改用-5%硬止损"
        else:
            rule = f"{structure_label}与-5%硬止损重合"

    if structure is not None:
        summary = f"预估{effective_stop:.2f} / 最晚{hard_stop:.2f}"
    else:
        summary = f"先看30分钟结构 / 最晚{hard_stop:.2f}"

    return {
        "entry_price": round(entry, 2),
        "structure_stop": structure,
        "structure_label": structure_label if structure is not None else "",
        "hard_stop": hard_stop,
        "effective_stop": effective_stop,
        "rule": rule,
        "summary": summary,
    }


def calculate_price_range(stock_data):
    """计算买入价格区间和卖出止损价。"""
    close_price = stock_data.get("close", 0)
    open_price = stock_data.get("open", 0)
    high_price = stock_data.get("high", 0)
    low_price = stock_data.get("low", 0)
    change_pct = stock_data.get("change_pct", 0)

    if close_price == 0:
        return {
            "buy_range": "数据缺失",
            "stop_loss": "数据缺失",
            "take_profit": "数据缺失",
            "buy_low": 0,
            "buy_high": 0,
            "stop_loss_price": 0,
            "take_profit_price": 0,
        }

    buy_low = close_price * 0.98
    buy_high = close_price * 1.02

    if change_pct >= 9.9:
        buy_low = open_price * 0.99
        buy_high = open_price * 1.01

    if change_pct <= -9.9:
        return {
            "buy_range": "不建议买入（跌停）",
            "stop_loss": "-",
            "take_profit": "-",
            "buy_low": 0,
            "buy_high": 0,
            "stop_loss_price": 0,
            "take_profit_price": 0,
        }

    avg_buy_price = (buy_low + buy_high) / 2
    stop_plan = build_stop_execution_plan(avg_buy_price)
    stop_loss_price = stop_plan["hard_stop"] if stop_plan else avg_buy_price * 0.95

    take_profit_price = avg_buy_price * 1.10

    buy_range = f"{buy_low:.2f} - {buy_high:.2f}"
    stop_loss = f"{stop_loss_price:.2f}"
    take_profit = f"{take_profit_price:.2f}"

    return {
        "buy_range": buy_range,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "buy_low": buy_low,
        "buy_high": buy_high,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "stop_rule": "盘前预案先给-5%硬止损底线，买入后改用30分钟结构止损",
    }


def get_abnormal_rank_adjustment(abnormal_item):
    """将异动后状态转成 Step 2 可直接使用的排序加权。"""
    if not abnormal_item:
        return 0, "无明显异动", ""
    if _is_degraded_abnormal_snapshot(abnormal_item):
        return 0, "降级快照(仅观察)", abnormal_item.get("action_rule", "")

    state = abnormal_item.get("follow_state", "")
    abnormal_type = abnormal_item.get("abnormal_type", "")
    setup_label = abnormal_item.get("setup_signal_label", "")

    state_bonus_map = {
        "跌不下去": 18,
        "缩量消化": 10,
        "新异动待观察": 3,
        "已经转弱": -12,
    }
    type_bonus_map = {
        "恐怖阴线异动": 6,
        "长上影异动": 4,
        "放量大阳异动": 3,
    }

    bonus = state_bonus_map.get(state, 0) + type_bonus_map.get(abnormal_type, 0)
    if setup_label:
        summary = f"{setup_label}({bonus:+d})"
    else:
        summary = f"{abnormal_type}/{state}({bonus:+d})" if abnormal_type and state else "无明显异动"
    return bonus, summary, abnormal_item.get("action_rule", "")


def merge_position_gate(position_level, exit_analysis):
    """把 Step 1 档位和 Step 4 转折分析合并成最终执行动作。"""
    light = exit_analysis.get("overall_level", "红灯")
    if position_level == "一档（空仓档）":
        return {
            "gate_status": "撤退",
            "position_level": "一档（空仓档）",
            "operation_state": "撤退态",
            "can_new_entry": False,
            "can_hold": False,
            "should_reduce": True,
            "allow_conditional_30": False,
            "base_position_cap_pct": 0,
            "final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
            "final_participation": "市场环境本身未打开，不和市场硬拧",
            "gate_reason": "大盘环境没有给到出手条件，先离场再等下一次趋势",
        }
    if light == "红灯":
        return {
            "gate_status": "撤退",
            "position_level": "一档（空仓档）",
            "operation_state": "撤退态",
            "can_new_entry": False,
            "can_hold": False,
            "should_reduce": True,
            "allow_conditional_30": False,
            "base_position_cap_pct": 0,
            "final_action": "主线退潮确认，停止参与；若你有仓位，尽快退出",
            "final_participation": "不是和市场争辩的时候，而是撤退等下一轮",
            "gate_reason": "主线已经不是可粘住的强趋势，继续抱着只会被动",
        }
    if light == "橙灯":
        return {
            "gate_status": "防守",
            "position_level": "二档（防守档）" if position_level != "一档（空仓档）" else "一档（空仓档）",
            "operation_state": "防守态" if position_level != "一档（空仓档）" else "撤退态",
            "can_new_entry": False,
            "can_hold": position_level != "一档（空仓档）",
            "should_reduce": True,
            "allow_conditional_30": position_level != "一档（空仓档）",
            "base_position_cap_pct": 0,
            "final_action": "禁止新增；若你有旧仓，去弱留强，不强就卖",
            "final_participation": "市场可能还没坏透，但这时只配留最强，不配乱出手",
            "gate_reason": "主线出现退潮预警，先收缩战线，等待真正强者自己走出来",
        }
    if position_level == "二档（防守档）":
        return {
            "gate_status": "防守",
            "position_level": "二档（防守档）",
            "operation_state": "防守态",
            "can_new_entry": False,
            "can_hold": True,
            "should_reduce": False,
            "allow_conditional_30": True,
            "base_position_cap_pct": 0,
            "final_action": "环境未完全打开，先控仓，只看最强核心，禁止新增",
            "final_participation": "这不是猛干的位置，只能观察和持有强者",
            "gate_reason": "市场环境还没完全放行，先让子弹飞一会儿",
        }
    if light == "黄灯":
        return {
            "gate_status": "放行",
            "position_level": position_level,
            "operation_state": "进攻态" if position_level == "三档（进攻档）" else "防守态",
            "can_new_entry": position_level == "三档（进攻档）",
            "can_hold": True,
            "should_reduce": False,
            "allow_conditional_30": True,
            "base_position_cap_pct": 50 if position_level == "三档（进攻档）" else 0,
            "final_action": "优先围绕主线核心出手，去弱留强，继续贴着最强趋势",
            "final_participation": "黄灯不是卖点，而是提醒你别去杂毛，要更聚焦核心",
            "gate_reason": "主线进入强化阶段，买也只买最强，不做分散试错",
        }
    return {
        "gate_status": "放行",
        "position_level": position_level,
        "operation_state": "进攻态" if position_level == "三档（进攻档）" else "防守态",
        "can_new_entry": position_level == "三档（进攻档）",
        "can_hold": True,
        "should_reduce": False,
        "allow_conditional_30": True,
        "base_position_cap_pct": 50 if position_level == "三档（进攻档）" else 0,
        "final_action": "环境和主线同向，围绕最强主线正常参与，像口香糖一样粘住强趋势",
        "final_participation": "做对趋势的前提下，不轻易下车",
        "gate_reason": "大盘环境和主线强度同向，允许执行狙击计划",
    }


def _candidate_matches_mainline(candidate, mainline_name=""):
    candidate = candidate or {}
    mainline_name = str(mainline_name or "").strip()
    if not mainline_name:
        return False

    fields = []
    for key in ("sector", "sector_name", "industry"):
        value = str(candidate.get(key, "") or "").strip()
        if value:
            fields.append(value)

    for key in ("sector_tags", "concepts", "concept_list"):
        values = candidate.get(key) or []
        if isinstance(values, (list, tuple, set)):
            fields.extend(str(item or "").strip() for item in values if str(item or "").strip())

    return any(sector_name_matches(field, mainline_name) for field in fields)
