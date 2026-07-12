#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Versioned trading-philosophy knowledge pack for the A股日报 pipeline.

This module is the single source of truth for the latest trading philosophy
extracted from the newer skill workspace. Other hooks should consume the data
here instead of hard-coding scattered text fragments.
"""

from __future__ import annotations

from typing import Dict, List

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from report.execution_wording import TWO_B_CONFIRMATION_CLAUSE

KNOWLEDGE_VERSION = "2026-04-22"
KNOWLEDGE_SOURCE = "skillhub"
KNOWLEDGE_SOURCE_PATH = "/Users/chaixixi/.workbuddy/skills/a-daily-report/SKILL.md"

MAIN_DERIVATION_CHAIN = [
    "结构中枢周期",
    "市场环境",
    "热点聚焦/趋势密度",
    "主线脉冲阶段",
    "龙头记忆",
    "固定Setup异动信号",
    "观察资格/买入资格",
    "09:50-10:10窗口",
    "失效价和单笔-5%底线",
    "周期归因",
    "自校准",
]

DECISION_GATE_CHAIN = [
    "环境条件满足",
    "主线确认",
    "异常/触发",
    "可交易性",
    "固定交易窗口条件",
    "失效价和单笔-5%底线",
]

PARTICIPATION_WINDOW_LAYER_TEXT = (
    f"强核心走09:30-09:35竞价表态、开盘前几分钟或回封；"
    f"普通结构只看09:50-10:10窗口；{TWO_B_CONFIRMATION_CLAUSE}"
)

TRADING_PHILOSOPHY_BOTTOM_LINE_TEXT = "不买庄股，不靠孤立技术指标做买卖，不跟随大神/专家指令抄作业；这类方法即便偶尔赚钱，更多也是运气，不构成可复制优势"
TRADING_PHILOSOPHY_TACTICAL_TEXT = "狙击手视角更接近卫宫切嗣式交易：不和市场正面缠斗，不为证明勇敢或追求漂亮买点而硬上；先隐藏、先观察、先等待，只在胜率明显倾斜时，对唯一目标做最务实的一击"
TRADING_PHILOSOPHY_RISK_TEXT = "这里的务实，不是靠消息、庄股或违规冒进，而是允许等待、绕行和放弃；宁可少赚，也不接受为了面子、预判正确或体面而承担大亏"
TRADING_PHILOSOPHY_PUT_CONTRACT_TEXT = "短线参与更像在主线里卖短久期put：先选愿意接的货，再定guard和confirm，再给一个有限观察合同；不破guard就继续站队，重回confirm才升级执行"
TRADING_PHILOSOPHY_ALIGNMENT_TEXT = "现在这个位置先做选方向、选站队，不做全面撒网；最近半个月到一个月持续发酵、反复被资金选择的方向优先进入站队池，周末一次性新故事先降级为探针"
TRADING_PHILOSOPHY_10CM_CONTRACT_TEXT = f"10cm主模式按周度合同处理：只对主线核心、异常承接、率先转强对象给3~5日观察合同；{PARTICIPATION_WINDOW_LAYER_TEXT}"
TRADING_PHILOSOPHY_20CM_CONTRACT_TEXT = "20cm创业板按两段合同处理：先给5~10日呼吸感观察合同，右侧确认后再切到1~3日快速验证；固定交易窗口内条件成立也只进入复盘和下一份日报判断，当晚日报未决定买就继续0%不参与"
TRADING_PHILOSOPHY_CYCLE_CONTRACT_TEXT = "观察周期看愿不愿继续站在它这边，介入周期看是否到了被市场指派接货的时点，退出周期看合同该续命、兑现还是作废"
TRADING_PHILOSOPHY_WEAK_TO_STRONG_TEXT = "弱转强不是抄底，也不是追高，而是只做第一波强势基础仍在、随后出现假弱、再等超预期转强的对象"
TRADING_PHILOSOPHY_FAKE_WEAK_TEXT = "假弱优先于真弱：跌不下去、缩量消化、长上影后仍能收住、恐怖洗盘后快速修复才继续看；已经转弱、A杀、重心下移就按真弱降级"
TRADING_PHILOSOPHY_WEAK_TO_STRONG_RESONANCE_TEXT = "弱转强必须有板块效应：缺少主线/板块共振的形态，即便看起来像假弱，也按孤胆英雄处理，只保留观察权"
TRADING_PHILOSOPHY_WEAK_TO_STRONG_RETREAT_TEXT = "退潮期的弱转强先降级：环境收缩、防守、退潮时，即便有强基底和假弱特征，也不能硬拗成顶级买点"
TRADING_PHILOSOPHY_SWITCHING_TEXT = "不为新故事切掉旧事实：市场已经证明谁强，就别因为一个更性感的短期催化、独立故事或主观想象，把已经在赚钱的主线核心轻易切掉"
TRADING_PHILOSOPHY_HOLD_VS_ENTRY_TEXT = "先分清赚的是持有的钱，还是切入的钱：主升阶段最大的 edge 往往不是更早发现，而是围绕已被市场证明的强者更少切换"
TRADING_PHILOSOPHY_DESENSITIZATION_TEXT = "外部风险一旦被市场脱敏，就降级成背景变量；真正主导动作的，重新回到主线强度、赚钱效应和承接质量本身"
TRADING_PHILOSOPHY_SUBJECTIVITY_TEXT = "主观理解可以帮助观察，但不能主导切换、扛单和硬上；交易动作必须服从市场已经承认的事实"
TRADING_PHILOSOPHY_DUAL_MODE_TEXT = "当前系统默认以10cm主线核心/异常承接作为主模式，以20cm右侧补充分支承接弹性样本；20cm只有在主线、流动性、确认链和风险边界都清楚时才参与，不把20cm当成默认主战场"
TRADING_PHILOSOPHY_DISCIPLINE_EDGE_TEXT = "真正的对手大多仍停留在追涨杀跌、眼红冲动和情绪化随手交易；这套体系追求的是‘不是量化胜似量化’的纪律优势"
TRADING_PHILOSOPHY_SCOPE_TEXT = "更适合复盘、指标、规律、仓位管理、情绪交易、短线进出；不适合听消息、追热点、躺死长线、无脑持有"

__all__ = [
    "LEDGER_MODE_FROZEN",
    "LEDGER_MODE_REPLAY",
    "KNOWLEDGE_VERSION",
    "KNOWLEDGE_SOURCE",
    "KNOWLEDGE_SOURCE_PATH",
    "MAIN_DERIVATION_CHAIN",
    "DECISION_GATE_CHAIN",
    "PARTICIPATION_WINDOW_LAYER_TEXT",
    "use_execution_framework_text",
    "use_contract_logic_digest_text",
    "use_trading_philosophy_lines",
    "use_strategy_positioning_lines",
    "use_report_preamble",
    "build_trading_philosophy_snapshot",
]


def use_execution_framework_text() -> str:
    return f"日线结构中枢定环境，{PARTICIPATION_WINDOW_LAYER_TEXT}，按失效价和单笔-5%底线处理风险"


def use_contract_logic_digest_text() -> str:
    return (
        "短线参与更像在主线里卖短久期put：先在最近半个月到一个月持续发酵的方向里选边站队，"
        "10cm按3~5日观察合同处理，20cm先做5~10日呼吸感观察再切1~3日快速验证；"
        "弱转强只做强基底上的假弱，不做真弱反抽；不破guard续命，重回confirm再接货"
    )


def use_trading_philosophy_lines(
    include_system_requirement: bool = True,
    compact: bool = False,
) -> List[str]:
    if compact:
        lines = [
            "- **方向性错误回避**：不买庄股，不抄作业。",
            "- **战术气质**：先藏、先等、只做高确定性一击。",
            "- **站队优先**：只站市场已选方向，不为新故事切换。",
            "- **模式分层**：10cm按合同处理；20cm先观察，固定交易窗口只记录承接，结果进入复盘和下一份日报判断。",
            "- **弱转强纪律**：只做假弱非真弱；缺共振、退潮先降级。",
            "- **执行原则**：少切换，少主观，少大亏。",
            f"- **适配边界**：{TRADING_PHILOSOPHY_SCOPE_TEXT}。",
        ]
        if include_system_requirement:
            lines.append(f"- **系统要求**：{' -> '.join(DECISION_GATE_CHAIN)}。")
        return lines

    lines = [
        f"- **方向性错误回避**：{TRADING_PHILOSOPHY_BOTTOM_LINE_TEXT}。",
        f"- **战术气质 / 风险翻译 / 合同视角**：{TRADING_PHILOSOPHY_TACTICAL_TEXT}；{TRADING_PHILOSOPHY_RISK_TEXT}；{TRADING_PHILOSOPHY_PUT_CONTRACT_TEXT}。",
        f"- **站队优先 / 切换纪律**：{TRADING_PHILOSOPHY_ALIGNMENT_TEXT}；{TRADING_PHILOSOPHY_SWITCHING_TEXT}。",
        f"- **模式分层**：{TRADING_PHILOSOPHY_10CM_CONTRACT_TEXT}；{TRADING_PHILOSOPHY_20CM_CONTRACT_TEXT}；{TRADING_PHILOSOPHY_CYCLE_CONTRACT_TEXT}。",
        f"- **弱转强纪律**：{TRADING_PHILOSOPHY_WEAK_TO_STRONG_TEXT}；{TRADING_PHILOSOPHY_FAKE_WEAK_TEXT}；{TRADING_PHILOSOPHY_WEAK_TO_STRONG_RESONANCE_TEXT}；{TRADING_PHILOSOPHY_WEAK_TO_STRONG_RETREAT_TEXT}。",
        f"- **持有/切入 / 环境理解 / 去主观化**：{TRADING_PHILOSOPHY_HOLD_VS_ENTRY_TEXT}；{TRADING_PHILOSOPHY_DESENSITIZATION_TEXT}；{TRADING_PHILOSOPHY_SUBJECTIVITY_TEXT}。",
        f"- **模式分层补充 / 适配边界**：{TRADING_PHILOSOPHY_DUAL_MODE_TEXT}；{TRADING_PHILOSOPHY_DISCIPLINE_EDGE_TEXT}；{TRADING_PHILOSOPHY_SCOPE_TEXT}。",
    ]
    if include_system_requirement:
        lines.append(f"- **系统要求**：所有新开仓都必须回到“{' -> '.join(DECISION_GATE_CHAIN)}”这条链上。")
    return lines


def use_strategy_positioning_lines(compact: bool = False) -> List[str]:
    if compact:
        return [
            "- **策略定位**：复盘 + 指标 + 规律 + 仓位 + 情绪 + 短线。",
            "- **策略禁区**：不听消息、不追热点、不躺死长线、不无脑持有。",
            "- **落地方式**：先复盘事实，再给仓位，再做短线进出。",
        ]
    return [
        "- **我适合做什么**：复盘、指标、规律、仓位管理、情绪交易、短线进出。",
        "- **我不适合做什么**：听消息、追热点、躺死长线、无脑持有。",
        "- **策略思路**：先把市场还原成可复盘事实，再从指标和规律里找边际；先给仓位和边界，再谈方向与节奏。",
        "- **思想核心**：不把故事当信号，不把热度当能力，不把长期幻想当持有理由。",
        "- **输出要求**：每份日报必须明确今天是研究、等待、执行还是退出，并落到具体仓位与动作。",
    ]


def use_report_preamble(
    target_date: str,
    run_mode: str = LEDGER_MODE_FROZEN,
    has_personal_positions: bool = False,
    compact: bool = False,
) -> List[str]:
    return [
        f"# {target_date} A股日报",
        "",
    ]


def build_trading_philosophy_snapshot(
    target_date: str,
    run_mode: str = LEDGER_MODE_FROZEN,
    has_personal_positions: bool = False,
    compact: bool = False,
) -> Dict[str, object]:
    return {
        "version": KNOWLEDGE_VERSION,
        "source": KNOWLEDGE_SOURCE,
        "source_path": KNOWLEDGE_SOURCE_PATH,
        "main_derivation_chain": list(MAIN_DERIVATION_CHAIN),
        "main_derivation_chain_text": " -> ".join(MAIN_DERIVATION_CHAIN),
        "decision_gate_chain": list(DECISION_GATE_CHAIN),
        "decision_gate_chain_text": " -> ".join(DECISION_GATE_CHAIN),
        "execution_framework_text": use_execution_framework_text(),
        "contract_logic_digest_text": use_contract_logic_digest_text(),
        "trading_philosophy_lines": use_trading_philosophy_lines(
            include_system_requirement=True,
            compact=compact,
        ),
        "strategy_positioning_lines": use_strategy_positioning_lines(compact=compact),
        "report_preamble_lines": use_report_preamble(
            target_date,
            run_mode=run_mode,
            has_personal_positions=has_personal_positions,
            compact=compact,
        ),
    }
