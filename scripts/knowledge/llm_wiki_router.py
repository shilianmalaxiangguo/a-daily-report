"""Explainable LLM Wiki routing for daily-report knowledge hits."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List

from knowledge.llm_wiki_manifest import (
    EXPLICIT_FACT_PATHS,
    stable_json_hash,
    validate_knowledge_manifest,
    validate_knowledge_manifest_sources,
)


TRACE_SCHEMA_VERSION = "knowledge_trace.v1"
EXPLICIT_FACT_ROOTS = (
    "market",
    "account",
    "candidate",
    "position",
    "decision",
    "capital_priority",
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE = (
    "selection_workflow",
    "final_target_resolution",
    "execution_object",
    "position_plan",
    "b1_b2",
    "old_position_handling",
    "exit_action",
)


def is_iso_calendar_date(value: str) -> bool:
    if not value:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


KNOWLEDGE_INDEX = [
    {
        "id": "market.low-frequency-focus",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "指数强但赚钱效应弱",
        "topics": ["市场结构", "低频聚焦", "窄池子进攻"],
        "trigger_terms": ["指数上涨", "上涨家数偏弱", "成交集中", "指数强", "跌多涨少"],
        "fact_conditions": {
            "must_any": [
                {"path": "market.index_trend", "equals": "上涨", "label": "指数上涨"},
                {"path": "market.breadth", "contains_any": ["上涨家数偏弱", "跌多涨少"], "label": "赚钱效应偏弱"},
                {"path": "market.turnover_distribution", "contains_any": ["成交集中"], "label": "成交集中"},
            ]
        },
        "scenarios": ["daily_report", "review"],
        "report_slot": "市场结构判断",
        "confidence": "verified",
        "impact": "指数强但赚钱效应弱时，只保留主线核心，不从旧方向强行扩散候选。",
    },
    {
        "id": "market.sector-grid-first-selection",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "水池九宫格与先选板块",
        "topics": [
            "结构性行情",
            "全市场水池",
            "水池九宫格",
            "先选板块",
            "板块网格化",
            "资金水位",
            "蓝色粗水柱",
            "红色细水柱",
            "主线抱团",
            "边角标的",
        ],
        "trigger_terms": [
            "结构性行情",
            "全市场水池",
            "水池九宫格",
            "九宫格",
            "网格化",
            "板块网格化",
            "先选板块",
            "板块先行",
            "资金水位",
            "蓝色粗水柱",
            "红色细水柱",
            "水柱",
            "蓝柱",
            "红柱",
            "主线抱团",
            "机构抱团",
            "短线题材",
            "边角标的",
            "轮动不到",
            "资金灌入",
            "板块格子",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "market.market_form", "contains_any": ["结构性行情", "全市场水池"], "label": "结构性行情"},
                {"path": "market.sector_grid", "contains_any": ["九宫格", "网格化", "板块格子", "资金水位"], "label": "板块网格"},
                {"path": "market.selection_order", "contains_any": ["先选板块", "板块先行"], "label": "板块先行"},
                {"path": "market.corner_sample", "contains_any": ["边角标的", "轮动不到"], "label": "边角样本"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "市场结构判断",
        "confidence": "reviewed",
        "impact": "结构性行情先问资金灌入哪个板块格子，再在格子内区分机构主线、短线题材和边角标的；先选板块不是只看板块名字，而是看成交占比、宽度、核心承接和竞争方向，边角标的不因轮动自动取得参与资格。",
    },
    {
        "id": "account.unbuyable-core-anchor",
        "prior": "account-execution-prior",
        "source_path": "wiki/交易思想/实际账户情况.md",
        "title": "实际不可买不降低市场身份",
        "topics": ["账户", "实际不可买", "市场核心", "候选比较"],
        "trigger_terms": ["实际不可买", "一手金额过高", "账户本金不足", "市场核心", "买不了"],
        "fact_conditions": {
            "must_any": [
                {"path": "account.status", "contains_any": ["实际不可买", "买不了", "本金不足"], "label": "账户不可买"},
                {"path": "candidate.identity", "contains_any": ["市场核心"], "label": "市场核心身份"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality"],
        "report_slot": "账户约束",
        "confidence": "verified",
        "impact": "实际不可买只影响当前账户参与，不降低市场核心、池内身份或板块锚价值。",
    },
    {
        "id": "decision.anti-prediction-response-script",
        "prior": "decision-sample-prior",
        "source_path": "wiki/交易思想/判断样本与市场演变.md",
        "title": "反预测崇拜与应对剧本",
        "topics": [
            "预测崇拜",
            "每天一个个股",
            "踩准节拍",
            "应对剧本",
            "量化行为博弈",
            "散户行为模式",
            "第一动作",
            "B1参与权",
            "B2确认权",
        ],
        "trigger_terms": [
            "预测崇拜",
            "每天一个个股",
            "每天一个股",
            "踩准节拍",
            "应对剧本",
            "量化行为博弈",
            "散户行为模式",
            "行为陷阱",
            "第一动作",
            "连接感",
            "B1",
            "B2",
            "B1参与权",
            "B2确认权",
            "0%不参与",
            "无执行目标",
            "只观察",
            "不强行凑个股",
            "买入资格",
            "踏空焦虑",
            "阳线追后排",
            "回本卖出",
            "小赚止盈",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "decision.position_plan", "contains_any": ["0%不参与", "零仓位"], "label": "0%不参与"},
                {"path": "decision.execution_object_state", "contains_any": ["无执行目标"], "label": "无执行目标"},
                {"path": "decision.action_layer", "contains_any": ["只观察", "观察层"], "label": "只观察"},
                {"path": "decision.participation_rhythm", "contains_any": ["第一动作", "初始动作"], "label": "第一动作"},
                {"path": "decision.behavior_traps", "contains_any": ["踏空焦虑", "阳线追后排", "回本卖出", "小赚止盈"], "label": "行为陷阱"},
            ],
            "prefer_any": [
                {"path": "decision.b1_role", "contains_any": ["参与权", "参与角色"], "label": "B1参与权"},
                {"path": "decision.b2_role", "contains_any": ["确认权", "确认角色"], "label": "B2确认权"},
                {"path": "decision.qualification", "contains_any": ["买入资格", "资格不足"], "label": "买入资格"},
                {"path": "decision.response_mode", "contains_any": ["应对剧本", "应对"], "label": "应对剧本"},
            ],
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "明日执行结论",
        "confidence": "reviewed",
        "impact": "日报不是预测节拍，而是准备应对剧本；没有买入资格时0%不参与也是有效结论。第一动作只给B1参与权，B2必须等待后续承接、板块扩散和个股强度确认，不能因为踏空焦虑补足。",
    },
    {
        "id": "position.cull-weak-keep-strong",
        "prior": "capital-priority-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "汰弱留强与旧仓新机会分离",
        "topics": ["去弱留强", "汰弱留强", "资金优先级", "旧仓新机会分离", "换仓", "第一性原理", "FOMO"],
        "trigger_terms": [
            "去弱留强",
            "汰弱留强",
            "汰强留弱",
            "卖强补弱",
            "弱替代",
            "浮盈浮亏",
            "换仓",
            "旧仓",
            "新机会",
            "第一性原理",
            "FOMO",
            "fomo",
            "满仓",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "position.state", "contains_any": ["旧仓", "失败仓"], "label": "旧仓事实"},
                {"path": "position.action", "contains_any": ["换仓", "去弱留强", "汰弱留强"], "label": "旧仓动作"},
                {"path": "position.capital_priority_reason", "contains_any": ["旧仓", "新机会", "FOMO", "满仓"], "label": "资金优先级原因"},
                {"path": "candidate.quality", "contains_any": ["新机会", "换仓", "满仓"], "label": "新机会比较"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "资金优先级",
        "confidence": "verified",
        "impact": "先判旧仓是否失去持仓资格，卖旧仓看旧仓资格；再判新机会是否取得执行资格，买新仓看新仓资格；不卖强补弱，也不用FOMO把两笔判断合成一次满仓替换。",
    },
    {
        "id": "market.performance-rotation-main-attack",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "业绩线与战术主攻切换",
        "topics": [
            "业绩线",
            "轮动线",
            "科技线牵制",
            "主攻点切换",
            "风格切换载体",
            "主线战术资源",
        ],
        "trigger_terms": [
            "业绩线",
            "业绩逻辑",
            "业绩超预期",
            "轮动线",
            "科技线",
            "非科技",
            "海外链",
            "国产链",
            "主攻点",
            "牵制点",
            "牵制",
            "哈兰德",
            "挪威",
            "超级巨星",
            "风格变换",
            "风格切换载体",
            "主线真空",
            "不合理的超额收益",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "market.market_form", "contains_any": ["业绩线", "轮动线", "科技线", "风格切换"], "label": "市场风格事实"},
                {"path": "market.sector_grid", "contains_any": ["业绩线", "轮动线", "科技线", "主攻点"], "label": "板块风格事实"},
                {"path": "market.selection_order", "contains_any": ["主攻点", "牵制点", "同权比较"], "label": "主攻比较"},
                {"path": "candidate.quality", "contains_any": ["风格切换载体", "超级巨星", "主线真空"], "label": "风格载体"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "市场结构判断",
        "confidence": "reviewed",
        "impact": "主线不是信仰位，而是战术资源；科技线调整或拥挤时可降为牵制点，业绩线、轮动线和低位趋势线若出现走势活跃、板块逻辑、价格结构和资金扩散共振，就要进入同权比较。最终0%后，强势样本还要复核是孤立情绪还是风格切换载体。",
    },
    {
        "id": "discipline.fomo-external-stimulus",
        "prior": "trade-discipline-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "FOMO 不是交易指令",
        "topics": ["FOMO", "卖飞", "买回", "情绪隔离", "主力情绪", "薛定谔持股", "必卖日执行"],
        "trigger_terms": [
            "FOMO",
            "fomo",
            "卖飞",
            "买回",
            "反包",
            "主力",
            "情绪",
            "后悔",
            "踏空",
            "薛定谔",
            "必卖",
            "空仓",
            "旧仓",
            "0轴卖",
            "纪律成本",
            "可复制",
            "小亏",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "decision.behavior_traps", "contains_any": ["踏空焦虑", "后悔", "FOMO"], "label": "情绪刺激"},
                {"path": "decision.response_script", "contains_any": ["FOMO", "卖飞", "买回", "必卖", "纪律成本"], "label": "纪律复核"},
                {"path": "position.capital_priority_reason", "contains_any": ["FOMO", "卖飞", "踏空", "后悔"], "label": "持仓情绪"},
                {"path": "position.action", "contains_any": ["买回", "必卖", "空仓"], "label": "持仓动作"},
            ]
        },
        "scenarios": ["intraday_question", "review", "daily_report"],
        "report_slot": "交易纪律",
        "confidence": "verified",
        "impact": "FOMO 是外部价格刺激被自己接住后的情绪，不是执行资格；反包先批改情绪反应，不直接批改前一日信息集。必卖日里，反抽、0轴、VWAP和开盘价修复先看作旧仓退出流动性；卖出后第一天因反包、后悔或怕踏空想买回，默认不执行，只能收盘后重新进入 T0 评估。",
    },
    {
        "id": "selection.rhythm-reset-margin-review",
        "prior": "selection-review-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "节奏复位空仓与边际主线复核",
        "topics": [
            "节奏复位空仓",
            "延后确认空仓",
            "错失待批改",
            "公共合理不等于超短边际",
            "边际主线",
            "外盘主线传导",
            "旧信号源批改",
            "跨日一致性复核",
        ],
        "trigger_terms": [
            "节奏踏错",
            "同手同脚",
            "合理空仓",
            "边际主线",
            "节奏复位空仓",
            "延后确认空仓",
            "错失待批改",
            "公共合理不等于超短边际",
            "外盘拉升",
            "外盘存储",
            "美股大回调",
            "美股拉升",
            "存储大涨",
            "旧目标强弩之末",
            "强弩之末",
            "旧信号源批改",
            "周五信号源",
            "周五策略",
            "周一空仓",
            "周一策略",
            "周二再强",
            "周二走强",
            "太极实业",
            "宜宾纸业",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "decision.response_script", "contains_any": ["节奏复位不新增", "延后确认不新增", "错失待批改", "边际主线"], "label": "节奏复核"},
                {"path": "decision.action_layer", "contains_any": ["合理空仓", "不新增", "只观察"], "label": "动作层"},
                {"path": "market.market_form", "contains_any": ["外盘拉升", "美股大回调", "美股拉升", "存储大涨"], "label": "外部市场启发"},
                {"path": "candidate.quality", "contains_any": ["旧目标强弩之末", "边际主线", "旧信号源批改"], "label": "候选边际"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "超短边际节奏复核",
        "confidence": "reviewed",
        "impact": "最终0%不是思考终点；继续批改是防守空仓、节奏复位空仓、延后确认空仓还是错失待批改。周一空仓若来自周五旧信号，必须追溯周五选股、买点、持仓预期和退出纪律；周二再强只算重新比较，不替周五或周一正名。外盘和存储强势默认只作启发，必须完成同链传导和A股确认后才进入T+1复核；过程候选不覆盖最终动作。",
    },
    {
        "id": "discipline.tplus-slot-timeline",
        "prior": "trade-discipline-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "Ta-Te 账户日序时间表",
        "topics": ["Ta-Te", "Ta/Tb/Tc/Td/Te", "日序", "T+2必卖", "空仓", "Td", "Te"],
        "trigger_terms": [
            "Ta",
            "Tb",
            "Tc",
            "Td",
            "Te",
            "Ta-Te",
            "Tabcde",
            "Ta+2",
            "Tb+0",
            "Tb+1",
            "Tc+0",
            "T+2必卖",
            "日序",
            "甘特图",
            "没有Tb",
            "没有Tc",
            "明日Te",
            "五日",
            "全天空仓",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "decision.response_script", "contains_any": ["Ta", "Tb", "Tc", "Td", "Te", "T+2必卖", "日序"], "label": "账户日序"},
                {"path": "position.action", "contains_any": ["T+2必卖", "明日Te", "全天空仓"], "label": "跨日动作"},
                {"path": "position.state", "contains_any": ["Ta", "Tb", "Tc", "Td", "Te"], "label": "跨日持仓事实"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "持仓日序",
        "confidence": "reviewed",
        "impact": "Ta-Te要表格化呈现账户时间占用：Ta是最远复盘日，Tb/Tc是前两段路径，Td是今日报告日，Te是明日执行日。Te只承接昨晚决定的参与、取消或旧仓降风险；明日标的为空时，Te写只处理旧仓风险或空仓等待B1资格。",
    },
    {
        "id": "intraday.do-t-risk-control",
        "prior": "intraday-question-prior",
        "source_path": "wiki/交易思想/做T与风险控制.md",
        "title": "做T先降风险，确认后买回",
        "topics": ["做T", "风险控制", "买回确认", "点位依据"],
        "trigger_terms": ["做T", "亏损", "反弹", "买回", "更便宜"],
        "fact_conditions": {
            "must_any": [
                {"path": "position.action", "contains_any": ["做T", "买回", "降风险"], "label": "做T动作"},
                {"path": "position.capital_priority_reason", "contains_any": ["亏损", "反弹", "更便宜", "买回"], "label": "做T原因"},
                {"path": "candidate.quality", "contains_any": ["做T", "买回确认", "风险控制"], "label": "买回确认"},
            ]
        },
        "scenarios": ["intraday_question", "daily_report", "review"],
        "report_slot": "盘中问股前提",
        "confidence": "verified",
        "impact": "做T先看防守线、止盈线和买回确认，不把更便宜当作更正确。",
    },
    {
        "id": "intraday.same-stock-t-failure-control",
        "prior": "intraday-question-prior",
        "source_path": "wiki/交易思想/做T与风险控制.md",
        "title": "同股T强表态失败处理",
        "topics": ["同股T", "临时2x", "强表态失败", "可卖旧仓", "失败仓", "尾盘卖出边界"],
        "trigger_terms": [
            "同股T",
            "同一只票",
            "同一只股",
            "same_stock_t",
            "1x",
            "2x",
            "临时2x",
            "强表态",
            "诱多",
            "可卖旧仓",
            "底仓",
            "失败仓",
            "跌破VWAP",
            "跌破昨收",
            "跌破MA7",
            "MA7清",
            "尾盘卖出",
            "太极实业",
        ],
        "weak_trigger_terms": ["1x", "2x", "太极实业"],
        "fact_conditions": {
            "must_any": [
                {"path": "position.action", "contains_any": ["同股T", "可卖旧仓", "尾盘卖出"], "label": "同股T动作"},
                {"path": "candidate.quality", "contains_any": ["同股T", "临时2x", "强表态", "诱多"], "label": "强表态事实"},
                {"path": "position.capital_priority", "contains_any": ["same_stock_t", "old_position_t"], "label": "同股资金优先级"},
                {"path": "position.capital_priority_reason", "contains_any": ["跌破VWAP", "跌破昨收", "跌破MA7"], "label": "失效事实"},
            ]
        },
        "scenarios": ["intraday_question", "daily_report", "review"],
        "report_slot": "同股T处理",
        "confidence": "reviewed",
        "impact": "已有1x且今日目标仍是同一只票时，只按同股T候选处理；强表态存活才允许临时2x，快速跌破VWAP、昨收或MA7且不能收回时，卖出可卖旧仓，新买仓位次日按失败仓处理。尾盘卖出只适用于正常样本，失败样本先保护亏损边界。",
    },
    {
        "id": "intraday.two-b-confirmation-positioning",
        "prior": "intraday-question-prior",
        "source_path": "wiki/交易思想/做T与风险控制.md",
        "title": "2B参与权与确认权",
        "topics": ["2B法", "B1", "B2", "参与权", "确认权", "任务仓", "奖励仓", "态度不是仓位", "确认后加速"],
        "trigger_terms": [
            "2B法",
            "2b",
            "B1",
            "B2",
            "0.5B",
            "FOMO",
            "fomo",
            "迷茫",
            "力不从心",
            "追高",
            "赌性",
            "贪念",
            "参与权",
            "确认权",
            "计划补全",
            "补全计划",
            "完成仓位",
            "B1没赢",
            "B1未赢",
            "B2不存在",
            "任务仓",
            "奖励仓",
            "下跌补仓",
            "走弱补仓",
            "必须买够",
            "买够",
            "怕小赚",
            "小赚",
            "少赚",
            "少亏",
            "少亏少赚",
            "大赚",
            "复利",
            "态度",
            "仓位",
            "集合竞价买一半",
            "确认后加速",
            "初始仓位",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "decision.b1_role", "contains_any": ["参与权"], "label": "B1参与权"},
                {"path": "decision.b2_role", "contains_any": ["确认权"], "label": "B2确认权"},
                {"path": "decision.participation_rhythm", "contains_any": ["初始仓位", "确认后加速"], "label": "参与节奏"},
                {"path": "decision.response_script", "contains_any": ["2B法", "B1", "B2", "任务仓", "奖励仓", "必须买够"], "label": "2B执行事实"},
                {"path": "candidate.quality", "contains_any": ["B1", "B2", "追高", "赌性", "贪念"], "label": "仓位行为"},
            ]
        },
        "scenarios": ["intraday_question", "daily_report", "review"],
        "report_slot": "2B仓位处理",
        "confidence": "reviewed",
        "impact": "B1只买参与权，B2只买确认权；B2不是任务仓，没有确认就没有补足义务。交易计划不是仓位完成任务，而是确认、取消和降风险的筛选器；B1没赢之前，B2不存在。短线超额来自确认后加速，不来自所有样本开盘买满；坏样本只亏B1，好样本才给B1+B2。少亏不是畏手畏脚，而是长期跑赢的一部分。",
    },
    {
        "id": "discipline.profit-after-win-control",
        "prior": "trade-discipline-prior",
        "source_path": "wiki/交易思想/做T与风险控制.md",
        "title": "盈利后失控与顺境收紧",
        "topics": ["盈利后失控", "顺境收紧", "连续盈利", "两笔出问题停手", "活跃资金风向标"],
        "trigger_terms": [
            "连续盈利",
            "盈利后",
            "赚了以后",
            "飘了",
            "失控",
            "两笔出问题",
            "直接停手",
            "股池",
            "连板高度",
            "热点宽度",
            "活跃股梯队",
            "高位异动",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "decision.behavior_traps", "contains_any": ["盈利后失控", "飘了", "失控"], "label": "盈利后偏差"},
                {"path": "decision.response_script", "contains_any": ["连续盈利", "两笔出问题", "直接停手"], "label": "顺境纪律"},
                {"path": "candidate.quality", "contains_any": ["股池", "连板高度", "热点宽度", "活跃股梯队"], "label": "活跃资金事实"},
                {"path": "market.market_form", "contains_any": ["连板高度", "热点宽度", "高位异动"], "label": "市场活跃度"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "交易纪律",
        "confidence": "reviewed",
        "impact": "连续盈利后先降频降仓并复核规则；两笔预演不顺或触发失效直接停手，恢复参与要看活跃资金和股池强者修复。",
    },
    {
        "id": "candidate.quality-action-layer",
        "prior": "candidate-quality-prior",
        "source_path": "wiki/交易思想/扣分系统与动作分层.md",
        "title": "候选质量条件链与动作上限",
        "topics": ["候选质量", "动作层级", "恢复条件", "取关条件"],
        "trigger_terms": ["候选质量", "动作上限", "恢复条件", "取关条件", "风险项"],
        "fact_conditions": {
            "must_any": [
                {"path": "candidate.quality", "contains_any": ["候选质量", "动作上限", "恢复条件", "取关条件", "风险项"], "label": "候选质量条件"},
            ]
        },
        "scenarios": ["daily_report", "candidate_quality", "review"],
        "report_slot": "候选质量",
        "confidence": "verified",
        "impact": "候选先看质量、风险和动作上限；旧分数只作兼容字段，最多能做什么由条件链决定。",
    },
    {
        "id": "principle.anti-fake-precision",
        "prior": "first-principles-prior",
        "source_path": "wiki/交易思想/反伪精确第一性原理.md",
        "title": "反伪精确第一性原理",
        "topics": ["第一性原理", "反伪精确", "条件链", "价格行为", "淘汰赛", "板块资金扩散", "资金载体"],
        "trigger_terms": [
            "第一性原理",
            "伪精确",
            "评分",
            "分数",
            "加权",
            "指标",
            "成功率",
            "概率",
            "淘汰赛",
            "条件链",
            "布鲁克斯",
            "板块资金扩散",
            "资金载体",
            "量化参与痕迹",
            "趋势容量核心",
            "板块锚",
            "中军",
            "分支龙头",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "market.selection_order", "contains_any": ["条件链", "板块资金扩散", "资金载体", "淘汰赛"], "label": "选择条件链"},
                {"path": "market.sector_grid", "contains_any": ["板块资金扩散", "板块锚", "中军", "分支龙头"], "label": "板块资金事实"},
                {"path": "candidate.quality", "contains_any": ["条件链", "价格行为", "量化参与痕迹", "趋势容量核心"], "label": "候选条件链"},
                {"path": "decision.response_script", "contains_any": ["第一性原理", "伪精确", "评分", "概率"], "label": "反伪精确复核"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "选股原则",
        "confidence": "verified",
        "impact": "事实数值保留，主观判断不能写成精确分；日报先从市场资金结构和板块资金扩散找资金载体，再按角色、量化参与痕迹、反证、价格行为和账户条件逐层收口。",
    },
    {
        "id": "market.new-stock-cycle-boundary",
        "prior": "market-structure-prior",
        "source_path": "wiki/交易思想/新股周期与市场情绪.md",
        "title": "新股周期不能替代单票承接",
        "topics": ["新股周期", "市场情绪", "承接验证"],
        "trigger_terms": ["新股", "次新", "情绪出口", "弱修复", "强修复"],
        "fact_conditions": {
            "must_any": [
                {"path": "market.market_form", "contains_any": ["新股", "次新", "情绪出口", "弱修复", "强修复"], "label": "新股周期事实"},
                {"path": "market.corner_sample", "contains_any": ["新股", "次新"], "label": "新股样本"},
                {"path": "candidate.identity", "contains_any": ["新股", "次新", "情绪出口"], "label": "候选身份"},
                {"path": "candidate.quality", "contains_any": ["承接验证", "弱修复", "强修复"], "label": "承接质量"},
            ]
        },
        "scenarios": ["daily_report", "review"],
        "report_slot": "市场结构判断",
        "confidence": "verified",
        "impact": "新股情绪只作为周期和承接判断，仍要回到单票承接验证。",
    },
    {
        "id": "knowledge.replay-five-fields",
        "prior": "knowledge-compounding-prior",
        "source_path": "wiki/交易思想/AI摩擦与知识复利.md",
        "title": "复盘沉淀五字段",
        "topics": ["知识复利", "复盘", "判断样本"],
        "trigger_terms": ["复盘", "错题", "当时判断", "实际偏差", "可复用规则"],
        "fact_conditions": {
            "must_any": [
                {"path": "decision.response_mode", "contains_any": ["复盘", "判断样本"], "label": "复盘场景"},
                {"path": "decision.response_script", "contains_any": ["复盘", "错题", "当时判断", "实际偏差", "可复用规则"], "label": "复盘五字段"},
                {"path": "decision.action_layer", "contains_any": ["复盘", "知识复利"], "label": "知识复利层"},
            ]
        },
        "scenarios": ["review", "daily_report", "intraday_question"],
        "report_slot": "知识复利提示",
        "confidence": "reviewed",
        "impact": "复盘按价格事实、当时判断、实际偏差、可复用规则、下次动作沉淀。",
    },
    {
        "id": "market.price-volume-contradiction",
        "prior": "market-structure-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "指数价跌量增先防踩踏",
        "topics": ["价格行为", "成交量", "指数价跌量增"],
        "trigger_terms": ["指数大跌", "放量", "价跌量增", "踩踏", "出货风险"],
        "fact_conditions": {
            "must_any": [
                {"path": "market.index_trend", "contains_any": ["指数大跌", "下跌"], "label": "指数下跌"},
                {"path": "market.turnover_distribution", "contains_any": ["放量", "价跌量增", "踩踏", "出货风险"], "label": "放量卖压"},
                {"path": "market.breadth", "contains_any": ["踩踏", "跌多涨少"], "label": "市场宽度走弱"},
            ]
        },
        "scenarios": ["daily_report", "review"],
        "report_slot": "市场结构判断",
        "confidence": "verified",
        "impact": "指数或全市场大跌且成交放大时，优先按卖压释放、量化踩踏或出货风险处理。",
    },
    {
        "id": "price-action.brooks-trend-framework",
        "prior": "price-action-prior",
        "source_path": "wiki/交易思想/布鲁克斯价格行为趋势.md",
        "title": "布鲁克斯价格行为趋势框架",
        "topics": ["价格行为", "价格趋势优先", "A股量价本地化", "叙事后置", "趋势区间谱系", "始终入场", "二次入场", "交易者等式"],
        "trigger_terms": [
            "布鲁克斯",
            "价格行为",
            "价格趋势",
            "叙事后置",
            "按图索因",
            "按因索图",
            "基本面",
            "找原因",
            "量价",
            "成交量",
            "放量",
            "缩量",
            "资金表态",
            "指标组合",
            "趋势区间",
            "始终入场",
            "二次入场",
            "信号K线",
            "急速与通道",
            "交易者等式",
            "假底",
            "进攻雏形",
            "再等等",
            "重心上移",
            "缩量横盘",
            "前高",
            "利空不深跌",
            "利好不大涨",
            "阳包阴",
            "突破阳线",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "candidate.quality", "contains_any": ["价格行为", "价格趋势", "量价", "信号K线", "假底", "进攻雏形"], "label": "候选价格行为"},
                {"path": "market.turnover_distribution", "contains_any": ["成交量", "放量", "缩量", "资金表态"], "label": "量价事实"},
                {"path": "decision.response_script", "contains_any": ["布鲁克斯", "二次入场", "交易者等式", "再等等"], "label": "价格行为剧本"},
                {"path": "position.capital_priority_reason", "contains_any": ["趋势", "回踩不破", "失效线"], "label": "持仓价格确认"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "价格行为判断",
        "confidence": "reviewed",
        "impact": "先判趋势/交易区间，再看信号是否有后续行情；成交量只作资金表态证据，必须由价格强收盘、回踩不破或后续行情确认；错过强趋势只允许小仓按同一失效线参与。",
    },
    {
        "id": "price-action.entry-quality-three-conditions",
        "prior": "entry-quality-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "追涨杀跌动作中性与买点三条件",
        "topics": ["追涨杀跌", "买点质量", "趋势地基", "盈亏同源点", "股性过滤", "异动K线"],
        "trigger_terms": [
            "追涨杀跌",
            "追涨",
            "杀跌",
            "买点",
            "趋势地基",
            "地基",
            "盈亏同源",
            "股性",
            "异动K线",
            "异动K",
            "旱地拔葱",
            "反包",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "candidate.quality", "contains_any": ["买点", "趋势地基", "盈亏同源", "股性", "异动K线"], "label": "买点质量"},
                {"path": "decision.qualification", "contains_any": ["买入资格", "资格不足"], "label": "买入资格"},
                {"path": "decision.response_script", "contains_any": ["追涨", "杀跌", "再等等", "认错线"], "label": "参与剧本"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "买点质量",
        "confidence": "reviewed",
        "impact": "追涨杀跌只是动作，先验趋势地基、盈亏同源点和股性；无地基急拉只观察，贴近认错线且次日重新承接后才进入参与评估。",
    },
    {
        "id": "discipline.present-execution",
        "prior": "trade-discipline-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "当下执行与心理时间校准",
        "topics": ["当下执行", "心理时间", "短线当下性", "未来焦虑"],
        "trigger_terms": [
            "当下",
            "焦虑",
            "焦躁",
            "未来",
            "短线",
            "价值投资",
            "新股",
            "暴涨",
            "预测",
            "期待",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "decision.response_script", "contains_any": ["当下", "未来", "短线", "预测", "期待"], "label": "执行时间事实"},
                {"path": "decision.behavior_traps", "contains_any": ["焦虑", "焦躁", "未来焦虑"], "label": "心理时间偏差"},
                {"path": "decision.response_mode", "contains_any": ["当下执行", "应对剧本"], "label": "执行模式"},
                {"path": "decision.action_layer", "contains_any": ["观察", "研究"], "label": "动作边界"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "交易纪律",
        "confidence": "reviewed",
        "impact": "计划和复盘可以面向未来，但盘中执行只看当下价格、承接、窗口和失效线；远期价值、新股暴涨想象和题材后续发酵只进观察或研究。",
    },
    {
        "id": "market.logic-chain-expansion",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "炒作逻辑链扩散后再升级",
        "topics": ["主线延续", "炒作逻辑链", "板块扩散"],
        "trigger_terms": ["逻辑链", "上游", "中游", "下游", "扩散", "主线延续"],
        "fact_conditions": {
            "must_any": [
                {"path": "market.sector_grid", "contains_any": ["逻辑链", "上游", "中游", "下游", "扩散"], "label": "板块逻辑链"},
                {"path": "market.selection_order", "contains_any": ["主线延续", "板块扩散"], "label": "主线延续"},
                {"path": "market.market_form", "contains_any": ["扩散", "后排承接"], "label": "市场扩散"},
            ]
        },
        "scenarios": ["daily_report", "review"],
        "report_slot": "市场结构判断",
        "confidence": "verified",
        "impact": "同一炒作逻辑链连续扩散并有后排承接时，才提高修复级别。",
    },
    {
        "id": "market.rebound-quality-active-passive",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "板块反弹质量与主动被动分层",
        "topics": ["反弹质量", "板块指数", "主动做多", "主动带动反弹", "跟随指数反弹", "熟悉资产修复", "节奏共振待确认", "冰点接冰点", "值博率"],
        "trigger_terms": [
            "反弹质量",
            "板块指数",
            "指数走坏",
            "板块走坏",
            "主动做多",
            "主动反弹",
            "主动带动",
            "带动市场",
            "领涨",
            "资金主动",
            "被动带下去",
            "被动下跌",
            "跟随反弹",
            "跟随指数",
            "减亏离场",
            "降风险窗口",
            "熟悉资产修复",
            "调研充分",
            "未来预期良好",
            "持续承接",
            "深V",
            "国产链",
            "先于指数",
            "节奏不匹配",
            "共振待确认",
            "冰点接冰点",
            "值博率",
            "弹簧",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "market.rebound_roles", "contains_any": ["主动带动反弹"], "label": "主动带动反弹"},
                {"path": "market.rebound_roles", "contains_any": ["跟随指数反弹"], "label": "跟随指数反弹"},
                {"path": "market.rebound_roles", "contains_any": ["熟悉资产修复"], "label": "熟悉资产修复"},
                {"path": "market.rebound_state", "contains_any": ["节奏共振待确认"], "label": "节奏共振待确认"},
                {"path": "market.rebound_action", "contains_any": ["减风险", "减亏离场", "B1参与权"], "label": "反弹动作分类"},
                {"path": "candidate.rebound_roles", "contains_any": ["主动带动反弹"], "label": "主动带动反弹"},
                {"path": "candidate.rebound_roles", "contains_any": ["跟随指数反弹"], "label": "跟随指数反弹"},
                {"path": "candidate.rebound_roles", "contains_any": ["熟悉资产修复"], "label": "熟悉资产修复"},
                {"path": "candidate.rebound_action", "contains_any": ["减风险", "减亏离场", "B1参与权"], "label": "反弹动作分类"},
                {"path": "position.rebound_roles", "contains_any": ["跟随指数反弹", "熟悉资产修复"], "label": "持仓反弹分类"},
                {"path": "position.rebound_action", "contains_any": ["减风险", "减亏离场", "持续承接确认"], "label": "持仓动作分类"},
            ],
            "prefer_any": [
                {"path": "market.rebound_state", "contains_any": ["指数深V"], "label": "指数深V"},
                {"path": "market.rebound_state", "contains_any": ["先于指数"], "label": "先于指数"},
                {"path": "market.rebound_state", "contains_any": ["板块高潮"], "label": "板块高潮"},
                {"path": "candidate.rebound_state", "contains_any": ["先于指数"], "label": "先于指数"},
                {"path": "candidate.rebound_state", "contains_any": ["板块高潮"], "label": "板块高潮"},
            ],
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "市场结构判断",
        "confidence": "reviewed",
        "impact": "反弹先分类再写动作：主动带动反弹按进攻线观察，可给B1参与权并等待B2确认；跟随指数反弹优先按减亏离场或降风险窗口；熟悉资产修复看持续承接和板块逻辑共振。板块先于指数上涨后遇到指数深V，只写共振待确认，次日看分歧承接、扩散延续和风险偏好是否被真正带动。",
    },
    {
        "id": "market.early-belief-fish-body-cycle",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "早信不是早买，鱼身只吃中段",
        "topics": ["早信", "鱼身", "无人问津", "人声鼎沸", "龙头二次发力", "后手风险"],
        "trigger_terms": [
            "早信",
            "鱼身",
            "鱼头",
            "鱼尾",
            "无人问津",
            "人声鼎沸",
            "龙头二次发力",
            "二次发力",
            "主动卖飞",
            "终于想通",
            "后手追涨",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "market.rebound_state", "contains_any": ["龙头二次发力", "二次发力", "人声鼎沸"], "label": "周期阶段"},
                {"path": "market.rebound_roles", "contains_any": ["主动带动反弹", "领涨"], "label": "领涨角色"},
                {"path": "candidate.rebound_state", "contains_any": ["龙头二次发力", "二次发力"], "label": "候选二次发力"},
                {"path": "candidate.quality", "contains_any": ["鱼身", "鱼头", "鱼尾", "后手追涨"], "label": "候选周期位置"},
                {"path": "decision.qualification", "contains_any": ["买入资格"], "label": "买入资格"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "市场结构判断",
        "confidence": "reviewed",
        "impact": "早信只提高观察优先级，不替代买入资格；龙头或分支二次发力后，再看固定交易窗口、板块同步、个股承接和亏损边界。鱼身只吃信号确认后到人声鼎沸前的中段，先涨者转弱、补涨扩散或权重拉指数时主动降风险。",
    },
    {
        "id": "research.supply-chain-bottleneck",
        "prior": "research-framework-prior",
        "source_path": "wiki/板块补充/供应链瓶颈研究法.md",
        "title": "供应链瓶颈先研究后交易",
        "topics": ["供应链瓶颈", "产业链拆解", "关键材料", "不可替代", "反方验证"],
        "trigger_terms": [
            "供应链瓶颈",
            "产业链瓶颈",
            "关键瓶颈",
            "不可替代",
            "CPO瓶颈",
            "CPO供应链",
            "光通信瓶颈",
            "InP",
            "衬底",
            "关键材料",
            "产能稀缺",
            "客户认证",
            "反方验证",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "market.sector_grid", "contains_any": ["供应链瓶颈", "产业链瓶颈", "关键瓶颈", "关键材料"], "label": "产业链瓶颈"},
                {"path": "market.selection_order", "contains_any": ["先研究后交易", "反方验证"], "label": "研究顺序"},
                {"path": "candidate.identity", "contains_any": ["不可替代", "产能稀缺", "客户认证"], "label": "瓶颈身份"},
                {"path": "candidate.quality", "contains_any": ["供应链瓶颈", "关键材料", "反方验证"], "label": "研究证据"},
            ]
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "研究线索",
        "confidence": "reviewed",
        "impact": "先拆产业链并验证瓶颈，再把线索降维成研究优先级；不直接生成买入资格，交易动作仍看价格承接、板块选择和失效条件。",
    },
]


_STRICT_FACT_SEPARATOR = "\x1e"


def _flatten_terms(value: Any, *, include_keys: bool = True) -> List[str]:
    terms: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if include_keys:
                terms.append(str(key))
            terms.extend(_flatten_terms(item, include_keys=include_keys))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            terms.extend(_flatten_terms(item))
    elif value is not None:
        text = str(value).strip()
        if text:
            terms.append(text)
    return terms


def _joined_terms(
    facts: Dict[str, Any],
    *,
    include_keys: bool = True,
    separator: str = " ",
) -> str:
    terms = _flatten_terms(facts or {}, include_keys=include_keys)
    market = (facts or {}).get("market") if isinstance(facts, dict) else {}
    if isinstance(market, dict) and str(market.get("index_trend", "") or "").strip() == "上涨":
        terms.append("指数上涨")
    return separator.join(terms)


def _value_at_path(value: Any, path: str) -> Any:
    current = value
    for part in str(path or "").split("."):
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _condition_matches(
    facts: Dict[str, Any],
    condition: Dict[str, Any],
    *,
    strict: bool = False,
) -> bool:
    values = _flatten_terms(_value_at_path(facts, str(condition.get("path") or "")))
    if not values:
        return False
    if condition.get("exists"):
        return True
    if "equals" in condition:
        expected = str(condition.get("equals") or "").strip()
        return any(value == expected for value in values)
    matcher = _strict_term_matches if strict else _term_matches
    if "contains" in condition:
        expected = str(condition.get("contains") or "").strip()
        return any(matcher(expected, value) for value in values)
    expected_values = [str(item or "").strip() for item in condition.get("contains_any") or []]
    return any(
        matcher(expected, value)
        for expected in expected_values
        for value in values
    )


def _matched_fact_condition_details(
    entry: Dict[str, Any],
    facts: Dict[str, Any],
    *,
    strict: bool = False,
) -> List[Dict[str, str]]:
    conditions = entry.get("fact_conditions") if isinstance(entry.get("fact_conditions"), dict) else {}
    matched_by_group: Dict[str, List[Dict[str, str]]] = {"must_any": [], "prefer_any": []}
    for group in matched_by_group:
        for condition in conditions.get(group) or []:
            if not isinstance(condition, dict) or not _condition_matches(
                facts,
                condition,
                strict=strict,
            ):
                continue
            label = str(condition.get("label") or condition.get("path") or "").strip()
            if label:
                matched_by_group[group].append(
                    {
                        "label": label,
                        "path": str(condition.get("path") or "").strip(),
                    }
                )
    if conditions.get("must_any") and not matched_by_group["must_any"]:
        return []
    matched = [*matched_by_group["must_any"], *matched_by_group["prefer_any"]]
    unique: List[Dict[str, str]] = []
    seen = set()
    for item in matched:
        key = (item["label"], item["path"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _matched_fact_conditions(entry: Dict[str, Any], facts: Dict[str, Any]) -> List[str]:
    return [item["label"] for item in _matched_fact_condition_details(entry, facts)]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value not in (None, ""):
            return float(value)
    except (TypeError, ValueError):
        return default
    return default


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _build_market_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    judgement = _first_dict(data.get("market_structure_judgement"))
    summary_text = str(judgement.get("summary_text") or "")
    fact_basis_text = " ".join(str(item or "") for item in judgement.get("fact_basis") or [])
    index_relation = str(judgement.get("index_profit_relation") or "")
    combined_text = " ".join([summary_text, fact_basis_text, index_relation])
    market_facts: Dict[str, Any] = {}
    if "指数强" in index_relation or "指数强" in summary_text:
        market_facts["index_trend"] = "上涨"
    if "上涨家数偏弱" in fact_basis_text or "真实赚钱效应弱" in summary_text:
        market_facts["breadth"] = "上涨家数偏弱"
    if "结构集中" in summary_text:
        market_facts["turnover_distribution"] = "成交集中"
    if "结构性行情" in combined_text:
        market_facts["market_form"] = "结构性行情"
    if "九宫格" in combined_text or "网格化" in combined_text or "板块格子" in combined_text:
        market_facts["sector_grid"] = "水池九宫格"
    if "先选板块" in combined_text or "板块先行" in combined_text:
        market_facts["selection_order"] = "先选板块"
    if "边角" in combined_text:
        market_facts["corner_sample"] = "边角标的"
    _merge_rebound_facts(market_facts, _rebound_facts_from_text(combined_text))
    return market_facts


def _rebound_facts_from_text(text: str) -> Dict[str, List[str]]:
    rebound_roles: List[str] = []
    rebound_state: List[str] = []
    rebound_action: List[str] = []
    if any(term in text for term in ["主动带动", "主动反弹", "主动做多", "带动市场", "领涨"]):
        rebound_roles.append("主动带动反弹")
        rebound_action.append("B1参与权")
    if any(term in text for term in ["跟随反弹", "跟随指数", "被动跟涨", "被动反弹"]):
        rebound_roles.append("跟随指数反弹")
        rebound_action.extend(["减亏离场", "减风险"])
    if any(term in text for term in ["熟悉资产修复", "调研充分", "未来预期良好", "不愿意追陌生领涨", "持续承接"]):
        rebound_roles.append("熟悉资产修复")
        rebound_action.append("持续承接确认")
    if "深V" in text:
        rebound_state.append("指数深V")
    if "先于指数" in text:
        rebound_state.append("先于指数")
    if "板块高潮" in text:
        rebound_state.append("板块高潮")
    if any(term in text for term in ["节奏不匹配", "共振待确认", "共振是否有效也并未确认"]):
        rebound_state.append("节奏共振待确认")
    rebound_facts: Dict[str, List[str]] = {}
    if rebound_roles:
        rebound_facts["rebound_roles"] = list(dict.fromkeys(rebound_roles))
    if rebound_state:
        rebound_facts["rebound_state"] = list(dict.fromkeys(rebound_state))
    if rebound_action:
        rebound_facts["rebound_action"] = list(dict.fromkeys(rebound_action))
    return rebound_facts


def _merge_rebound_facts(target: Dict[str, Any], rebound_facts: Dict[str, List[str]]) -> None:
    for key in ("rebound_roles", "rebound_state", "rebound_action"):
        values = rebound_facts.get(key) or []
        if not values:
            continue
        existing = target.get(key) if isinstance(target.get(key), list) else []
        target[key] = list(dict.fromkeys([*existing, *values]))


def _candidate_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    return _first_dict(
        data.get("selected_position_candidate"),
        data.get("selected_candidate"),
        data.get("watch_anchor"),
        _first_dict(data.get("market_research_snapshot")).get("selected_position_candidate"),
    )


def _account_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    personal_position_context = _first_dict(data.get("personal_position_context"))
    market_research_snapshot = _first_dict(data.get("market_research_snapshot"))
    return _first_dict(
        data.get("account_profile"),
        data.get("account"),
        personal_position_context.get("account_profile"),
        market_research_snapshot.get("account_profile"),
    )


def _final_target_resolution_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    market_research_snapshot = _first_dict(data.get("market_research_snapshot"))
    execution_stage_context = _first_dict(data.get("execution_stage_context"))
    return _first_dict(
        data.get("final_target_resolution"),
        execution_stage_context.get("final_target_resolution"),
        market_research_snapshot.get("final_target_resolution"),
    )


def _existing_position_summary_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    personal_position_context = _first_dict(data.get("personal_position_context"))
    market_research_snapshot = _first_dict(data.get("market_research_snapshot"))
    return _first_dict(
        data.get("existing_position_summary"),
        personal_position_context.get("existing_position_summary"),
        market_research_snapshot.get("existing_position_summary"),
    )


def _has_existing_position(position: Dict[str, Any]) -> bool:
    if not isinstance(position, dict) or not position:
        return False
    if position.get("has_position") is False:
        return False
    if position.get("position_count") == 0:
        return False
    identity_keys = ("name", "stock_name", "code", "stock_code", "symbol")
    if any(str(position.get(key) or "").strip() for key in identity_keys):
        return True
    return bool(position.get("has_position"))


def _build_account_candidate_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    account = _account_from_data(data)
    candidate = _candidate_from_data(data)
    account_facts: Dict[str, Any] = {}
    candidate_facts: Dict[str, Any] = {}

    cash_available = _safe_float(account.get("cash_available"), default=0.0)
    one_lot_amount = _safe_float(candidate.get("one_lot_amount"), default=0.0)
    if cash_available:
        account_facts["cash_available"] = cash_available
    if one_lot_amount:
        candidate_facts["one_lot_amount"] = one_lot_amount
    if cash_available and one_lot_amount and one_lot_amount > cash_available:
        account_facts["status"] = "实际不可买"

    identity = str(candidate.get("identity") or candidate.get("cycle_identity") or candidate.get("market_identity") or "").strip()
    if identity:
        candidate_facts["identity"] = identity

    quality_terms = []
    if candidate.get("action_limit") or candidate.get("action_cap"):
        quality_terms.append("动作上限")
    if candidate.get("risk_items") or candidate.get("risk_flags"):
        quality_terms.append("风险项")
    if candidate.get("recover_condition") or candidate.get("recovery_condition"):
        quality_terms.append("恢复条件")
    if candidate.get("drop_condition") or candidate.get("remove_condition"):
        quality_terms.append("取关条件")
    if quality_terms:
        candidate_facts["quality"] = ["候选质量", *quality_terms]
    _merge_rebound_facts(candidate_facts, _rebound_facts_from_text(" ".join(_flatten_terms(candidate))))

    return {"account": account_facts, "candidate": candidate_facts}


def _build_position_capital_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    resolution = _final_target_resolution_from_data(data)
    decision = _first_dict(resolution.get("capital_priority_decision"))
    existing_position = _first_dict(
        resolution.get("existing_position_target"),
        _existing_position_summary_from_data(data),
    )
    exposure_plan = _first_dict(resolution.get("account_exposure_plan"))
    new_entry = _first_dict(
        resolution.get("new_entry_target"),
        resolution.get("tradable_proxy_target"),
        resolution.get("watch_target"),
    )

    position_facts: Dict[str, Any] = {}
    candidate_facts: Dict[str, Any] = {}
    capital_priority = str(decision.get("capital_priority") or "").strip()
    reason = str(decision.get("reason") or "").strip()
    old_position_priority = {
        "old_position_t",
        "old_position",
        "existing_position",
        "existing_position_t",
        "new_entry_after_old_exit",
    }
    switch_priority = {"new_entry_after_old_exit"}
    new_entry_priority = {"new_entry", "tradable_proxy"}
    has_existing_position = _has_existing_position(existing_position)
    same_stock_t = bool(exposure_plan.get("same_stock_t") or capital_priority == "same_stock_t")

    if has_existing_position or capital_priority in old_position_priority or same_stock_t:
        position_facts["state"] = "旧仓"
    if same_stock_t:
        position_facts["action"] = "同股T"
        candidate_facts.setdefault("quality", []).extend(["同股T", "临时2x"])
    if capital_priority in switch_priority:
        position_facts["action"] = "换仓"
        candidate_facts.setdefault("quality", []).append("新机会")
    elif new_entry and has_existing_position and capital_priority in new_entry_priority:
        candidate_facts.setdefault("quality", []).append("新机会")
    if new_entry and capital_priority in switch_priority:
        candidate_facts.setdefault("quality", []).append("换仓")
    if "满仓" in reason:
        candidate_facts.setdefault("quality", []).append("满仓")
    if reason and position_facts:
        position_facts["capital_priority_reason"] = reason
    if capital_priority and position_facts:
        position_facts["capital_priority"] = capital_priority
    _merge_rebound_facts(candidate_facts, _rebound_facts_from_text(" ".join(_flatten_terms(new_entry))))
    if has_existing_position:
        _merge_rebound_facts(position_facts, _rebound_facts_from_text(" ".join(_flatten_terms([existing_position, reason]))))

    result: Dict[str, Any] = {}
    if position_facts:
        result["position"] = position_facts
    if candidate_facts:
        result["candidate"] = candidate_facts
    if capital_priority:
        result["capital_priority"] = capital_priority
    return result


def _build_decision_response_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    resolution = _final_target_resolution_from_data(data)
    final = _first_dict(resolution.get("final"), resolution.get("final_action"))
    planned_participation = _first_dict(
        resolution.get("planned_participation"),
        resolution.get("participation_script"),
        final.get("planned_participation"),
        final.get("participation_script"),
    )
    target = _first_dict(
        final.get("execution_object"),
        final.get("target"),
        resolution.get("execution_object"),
        resolution.get("new_entry_target"),
        resolution.get("display_target"),
        resolution.get("watch_target"),
    )
    position_pct = final.get("position_pct", resolution.get("position_pct"))
    text_parts = _flatten_terms(
        [
            final.get("label"),
            final.get("action_text"),
            final.get("action"),
            final.get("reason"),
            final.get("failure_conditions"),
            resolution.get("action_text"),
            resolution.get("tomorrow_action"),
            resolution.get("reason"),
            resolution.get("failure_conditions"),
            resolution.get("participation_script"),
            planned_participation.get("confirm_conditions"),
            planned_participation.get("cancellation_conditions"),
            planned_participation.get("entry_plan"),
            planned_participation.get("risk_plan"),
            planned_participation.get("position_plan"),
        ]
    )
    combined = " ".join(text_parts)
    tags: List[str] = []
    structured: Dict[str, Any] = {}

    try:
        numeric_position = int(float(position_pct))
    except (TypeError, ValueError):
        numeric_position = None
    if numeric_position == 0:
        tags.append("0%不参与")
        structured["position_plan"] = "0%不参与"
    if not target and ("0%不参与" in combined or "不参与" in combined or "只观察" in combined):
        tags.append("无执行目标")
        structured["execution_object_state"] = "无执行目标"
    for term in [
        "0%不参与",
        "只观察",
        "无执行目标",
        "第一动作",
        "B1",
        "B2",
        "B1参与权",
        "B2确认权",
        "踏空焦虑",
        "买入资格",
        "不强行凑个股",
        "应对剧本",
    ]:
        if term in combined:
            tags.append(term)
    if "只观察" in combined:
        structured["action_layer"] = "只观察"
    if "第一动作" in combined:
        structured["participation_rhythm"] = "第一动作"
    if "B1" in combined:
        structured["b1_role"] = "参与权"
    if "B2" in combined:
        structured["b2_role"] = "确认权"
    if "买入资格" in combined:
        structured["qualification"] = "买入资格"
    if "应对剧本" in combined:
        structured["response_mode"] = "应对剧本"
    behavior_traps = [
        term
        for term in ["踏空焦虑", "阳线追后排", "回本卖出", "小赚止盈"]
        if term in combined
    ]
    if behavior_traps:
        structured["behavior_traps"] = behavior_traps

    unique_tags = list(dict.fromkeys(tags))
    if not unique_tags and not structured:
        return {}
    response_facts: Dict[str, Any] = dict(structured)
    if unique_tags:
        response_facts["response_script"] = unique_tags
    return {"decision": response_facts}


def _derived_llm_wiki_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    market_facts = _build_market_fact_tags(data)
    if market_facts:
        facts["market"] = market_facts
    account_candidate = _build_account_candidate_fact_tags(data)
    for key, value in account_candidate.items():
        if value:
            facts[key] = value
    position_capital = _build_position_capital_fact_tags(data)
    for key, value in position_capital.items():
        if not value:
            continue
        if isinstance(value, dict) and isinstance(facts.get(key), dict):
            merged = dict(facts[key])
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, list) and isinstance(merged.get(nested_key), list):
                    merged[nested_key] = list(dict.fromkeys([*merged[nested_key], *nested_value]))
                else:
                    merged[nested_key] = nested_value
            facts[key] = merged
        else:
            facts[key] = value
    decision_response = _build_decision_response_fact_tags(data)
    for key, value in decision_response.items():
        if not value:
            continue
        if isinstance(value, dict) and isinstance(facts.get(key), dict):
            merged = dict(facts[key])
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, list) and isinstance(merged.get(nested_key), list):
                    merged[nested_key] = list(dict.fromkeys([*merged[nested_key], *nested_value]))
                else:
                    merged[nested_key] = nested_value
            facts[key] = merged
        else:
            facts[key] = value
    return facts


_REJECTED_FACT_VALUE = object()


def _sanitize_fact_list_item(value: Any, *, path: str, warnings: List[str]) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        warnings.append(f"knowledge_fact_value_rejected:{path}")
        return _REJECTED_FACT_VALUE
    if isinstance(value, (list, tuple)):
        sanitized = []
        for index, item in enumerate(value):
            result = _sanitize_fact_list_item(
                item,
                path=f"{path}[{index}]",
                warnings=warnings,
            )
            if result is not _REJECTED_FACT_VALUE:
                sanitized.append(result)
        return sanitized
    warnings.append(f"knowledge_fact_value_rejected:{path}")
    return _REJECTED_FACT_VALUE


def _sanitize_explicit_fact_value(value: Any, *, path: str, warnings: List[str]) -> Any:
    is_leaf = path in EXPLICIT_FACT_PATHS
    is_container = any(allowed.startswith(f"{path}.") for allowed in EXPLICIT_FACT_PATHS)
    if isinstance(value, Mapping):
        if not is_container:
            warnings.append(f"knowledge_fact_path_rejected:{path}")
            return _REJECTED_FACT_VALUE
        sanitized = {}
        for key, item in value.items():
            key_text = str(key).strip()
            nested_path = f"{path}.{key_text}" if path else key_text
            if not key_text:
                warnings.append(f"knowledge_fact_key_rejected:{nested_path or '<empty>'}")
                continue
            result = _sanitize_explicit_fact_value(
                item,
                path=nested_path,
                warnings=warnings,
            )
            if result is not _REJECTED_FACT_VALUE:
                sanitized[key_text] = result
        return sanitized
    if not is_leaf:
        warnings.append(f"knowledge_fact_path_rejected:{path}")
        return _REJECTED_FACT_VALUE
    if isinstance(value, (list, tuple)):
        return _sanitize_fact_list_item(value, path=path, warnings=warnings)
    return _sanitize_fact_list_item(value, path=path, warnings=warnings)


def _sanitize_routed_facts(
    facts: Mapping[str, Any] | None,
    *,
    warnings: List[str],
) -> Dict[str, Any]:
    sanitized_facts: Dict[str, Any] = {}
    for key, value in (facts or {}).items():
        key_text = str(key).strip()
        if key_text not in EXPLICIT_FACT_ROOTS:
            warnings.append(f"knowledge_fact_root_rejected:{key_text or '<empty>'}")
            continue
        sanitized = _sanitize_explicit_fact_value(
            value,
            path=key_text,
            warnings=warnings,
        )
        if sanitized is _REJECTED_FACT_VALUE or sanitized == {}:
            continue
        sanitized_facts[key_text] = sanitized
    return sanitized_facts


def _declared_fact_path(path: str) -> str:
    normalized = str(path or "").strip()
    while normalized.endswith("]"):
        bracket = normalized.rfind("[")
        if bracket < 0 or not normalized[bracket + 1 : -1].isdigit():
            break
        normalized = normalized[:bracket]
    return normalized


def _fact_source_map(
    facts: Dict[str, Any],
    *,
    source: str,
    explicit_prefix: str = "",
) -> Dict[str, Dict[str, str]]:
    fact_sources: Dict[str, Dict[str, str]] = {}
    for leaf_path, _ in _iter_fact_leaves(facts):
        path = _declared_fact_path(leaf_path)
        if not path:
            continue
        fact_sources[path] = {
            "source": source,
            "input_path": f"{explicit_prefix}{path}" if explicit_prefix else path,
        }
    return fact_sources


def build_llm_wiki_fact_bundle(data: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return routed facts together with their origin and validation warnings."""
    if not isinstance(data, dict):
        return {
            "facts": {},
            "facts_source": "derived",
            "fact_sources": {},
            "warnings": [],
        }
    explicit = data.get("knowledge_hit_facts")
    if isinstance(explicit, dict):
        warnings: List[str] = []
        facts = _sanitize_routed_facts(explicit, warnings=warnings)
        return {
            "facts": facts,
            "facts_source": "explicit",
            "fact_sources": _fact_source_map(
                facts,
                source="explicit",
                explicit_prefix="knowledge_hit_facts.",
            ),
            "warnings": list(dict.fromkeys(warnings)),
        }
    facts = _derived_llm_wiki_fact_tags(data)
    return {
        "facts": facts,
        "facts_source": "derived",
        "fact_sources": _fact_source_map(facts, source="derived"),
        "warnings": [],
    }


def build_llm_wiki_fact_tags(data: Dict[str, Any] | None) -> Dict[str, Any]:
    """Extract compact fact tags used by the explainable Wiki router."""
    return dict(build_llm_wiki_fact_bundle(data)["facts"])


def _term_matches(term: str, text: str) -> bool:
    return bool(term and term in text)


def _strict_term_matches(term: str, text: str) -> bool:
    if not term:
        return False
    start = 0
    negative_markers = ("没有", "并非", "并未", "不是", "不能", "不", "非", "无", "未")
    clause_separators = f"，。；！？{_STRICT_FACT_SEPARATOR}"
    while True:
        index = text.find(term, start)
        if index < 0:
            return False
        clause_start = max(text.rfind(separator, 0, index) for separator in clause_separators) + 1
        prefix = text[clause_start:index]
        if not any(marker in prefix for marker in negative_markers):
            return True
        start = index + len(term)


def _matched_trigger_terms(entry: Dict[str, Any], facts_text: str, *, strict: bool = False) -> List[str]:
    matcher = _strict_term_matches if strict else _term_matches
    return [
        str(term)
        for term in entry.get("trigger_terms", [])
        if matcher(str(term), facts_text)
    ]


def _entry_requirements_satisfied(entry: Dict[str, Any], matched_terms: List[str], matched_conditions: List[str]) -> bool:
    weak_terms = {str(term) for term in entry.get("weak_trigger_terms", [])}
    if weak_terms and matched_terms and not matched_conditions and all(term in weak_terms for term in matched_terms):
        return False
    return True


def _scenario_allowed(entry: Dict[str, Any], scenario: str) -> bool:
    scenarios = [str(item) for item in entry.get("scenarios", [])]
    return not scenario or scenario in scenarios


def _required_fact_conditions_satisfied(
    entry: Dict[str, Any],
    facts: Dict[str, Any],
    *,
    strict: bool = False,
) -> bool:
    conditions = entry.get("fact_conditions") if isinstance(entry.get("fact_conditions"), dict) else {}
    required = [item for item in conditions.get("must_any") or [] if isinstance(item, dict)]
    return not required or any(
        _condition_matches(facts, condition, strict=strict)
        for condition in required
    )


def _build_hit(entry: Dict[str, Any], matched_terms: Iterable[str], matched_conditions: Iterable[str], index: int) -> Dict[str, Any]:
    matched_term_list = list(matched_terms)
    matched_condition_list = list(matched_conditions)
    triggered_by = list(dict.fromkeys(matched_term_list or matched_condition_list))
    return {
        "hit_id": f"kh-{index:03d}",
        "knowledge_id": entry["id"],
        "prior": entry["prior"],
        "source_path": entry["source_path"],
        "title": entry["title"],
        "triggered_by": triggered_by,
        "matched_conditions": matched_condition_list,
        "matched_topics": list(entry.get("topics", [])),
        "impact": entry["impact"],
        "report_slot": entry["report_slot"],
        "confidence": entry["confidence"],
    }


def _rank_knowledge_entries(
    facts: Dict[str, Any],
    *,
    entries: Iterable[Dict[str, Any]],
    scenario: str,
    include_fact_keys: bool = True,
    enforce_required_conditions: bool = False,
    strict_terms: bool = False,
) -> List[tuple[int, int, int, int, Dict[str, Any], List[str], List[Dict[str, str]]]]:
    facts_text = _joined_terms(
        facts,
        include_keys=include_fact_keys,
        separator=_STRICT_FACT_SEPARATOR if strict_terms else " ",
    )
    ranked_matches = []
    for order, entry in enumerate(entries):
        if not _scenario_allowed(entry, scenario):
            continue
        if enforce_required_conditions and not _required_fact_conditions_satisfied(
            entry,
            facts,
            strict=strict_terms,
        ):
            continue
        matched_terms = _matched_trigger_terms(entry, facts_text, strict=strict_terms)
        if enforce_required_conditions and not matched_terms:
            continue
        matched_details = _matched_fact_condition_details(
            entry,
            facts,
            strict=strict_terms,
        )
        matched_conditions = [item["label"] for item in matched_details]
        if (matched_terms or matched_conditions) and _entry_requirements_satisfied(
            entry,
            matched_terms,
            matched_conditions,
        ):
            score = len(matched_terms) + len(matched_conditions) * 2
            ranked_matches.append(
                (
                    score,
                    len(matched_conditions),
                    len(matched_terms),
                    -order,
                    entry,
                    matched_terms,
                    matched_details,
                )
            )
    ranked_matches.sort(reverse=True)
    return ranked_matches


def _iter_fact_leaves(value: Any, *, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            nested_path = f"{path}.{key}" if path else str(key)
            yield from _iter_fact_leaves(item, path=nested_path)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _iter_fact_leaves(item, path=f"{path}[{index}]")
    elif value is not None:
        text = str(value).strip()
        if text:
            yield path, text


def _matched_fact_paths(
    facts: Dict[str, Any],
    matched_terms: Iterable[str],
    matched_details: Iterable[Dict[str, str]],
    strict_terms: bool = False,
) -> List[str]:
    paths = [
        _declared_fact_path(str(item.get("path") or ""))
        for item in matched_details
    ]
    leaves = [
        (_declared_fact_path(path), text)
        for path, text in _iter_fact_leaves(facts)
    ]
    matcher = _strict_term_matches if strict_terms else _term_matches
    for term in matched_terms:
        if (
            str(term) == "指数上涨"
            and _value_at_path(facts, "market.index_trend") == "上涨"
        ):
            paths.append("market.index_trend")
        for path, text in leaves:
            if path and matcher(str(term), text):
                paths.append(path)
    return sorted(set(path for path in paths if path))


def _normalize_fact_sources(
    facts: Dict[str, Any],
    *,
    facts_source: str,
    fact_sources: Mapping[str, Any] | None,
    warnings: List[str],
) -> Dict[str, Dict[str, str]]:
    supplied = fact_sources if isinstance(fact_sources, Mapping) else {}
    normalized_source = "explicit" if facts_source == "explicit" else "derived"
    leaf_paths = sorted(
        {
            _declared_fact_path(path)
            for path, _ in _iter_fact_leaves(facts)
            if path
        }
    )
    normalized: Dict[str, Dict[str, str]] = {}
    for path in leaf_paths:
        expected_input_path = (
            f"knowledge_hit_facts.{path}"
            if normalized_source == "explicit"
            else path
        )
        source_ref = supplied.get(path)
        if isinstance(source_ref, Mapping):
            supplied_source = str(source_ref.get("source") or "").strip()
            supplied_input_path = str(source_ref.get("input_path") or "").strip()
            if (
                supplied_source != normalized_source
                or supplied_input_path != expected_input_path
            ):
                warnings.append(f"knowledge_fact_source_rejected:{path}")
        elif source_ref is not None:
            warnings.append(f"knowledge_fact_source_rejected:{path}")
        normalized[path] = {
            "source": normalized_source,
            "input_path": expected_input_path,
        }
    for supplied_path in sorted(str(path) for path in supplied if str(path) not in leaf_paths):
        warnings.append(f"knowledge_fact_source_path_rejected:{supplied_path}")
    return normalized


def _manifest_entry_as_router_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    source_ref = entry.get("source_ref") if isinstance(entry.get("source_ref"), Mapping) else {}
    report_slots = [str(item) for item in entry.get("report_slots") or [] if str(item).strip()]
    return {
        "id": str(entry.get("knowledge_id") or "").strip(),
        "prior": str(entry.get("prior") or "").strip(),
        "source_path": str(source_ref.get("path") or "").strip(),
        "source_ref": dict(source_ref),
        "title": str(entry.get("title") or "").strip(),
        "topics": list(entry.get("topics") or []),
        "trigger_terms": list(entry.get("trigger_terms") or []),
        "weak_trigger_terms": list(entry.get("weak_trigger_terms") or []),
        "fact_conditions": dict(entry.get("fact_conditions") or {}),
        "scenarios": list(entry.get("applies_to") or []),
        "report_slot": report_slots[0] if report_slots else "",
        "confidence": str(entry.get("confidence") or "").strip(),
        "impact": str(entry.get("decision_effect") or "").strip(),
        "decision_effect": str(entry.get("decision_effect") or "").strip(),
        "decision_scope": str(entry.get("decision_scope") or "").strip(),
    }


def route_llm_wiki_knowledge_trace(
    facts: Dict[str, Any] | None,
    *,
    manifest: Mapping[str, Any],
    scenario: str = "daily_report",
    limit: int = 3,
    target_date: str = "",
    query_date: str = "",
    facts_source: str = "derived",
    fact_sources: Mapping[str, Any] | None = None,
    warnings: Iterable[str] | None = None,
    source_root: Path | str | None = None,
) -> Dict[str, Any]:
    """Build a deterministic, source-linked Wiki routing trace."""
    target_date_text = str(target_date or "")
    query_date_text = str(query_date or "")
    normalized_target_date = target_date_text.strip()
    normalized_query_date = query_date_text.strip()
    target_date_valid = (
        target_date_text == normalized_target_date
        and is_iso_calendar_date(normalized_target_date)
    )
    query_date_valid = (
        query_date_text == normalized_query_date
        and is_iso_calendar_date(normalized_query_date)
    )
    routing_warnings = [str(item) for item in warnings or []]
    if not normalized_target_date:
        routing_warnings.append("目标交易日缺失，知识引用日期无法核对")
    elif not target_date_valid:
        routing_warnings.append("目标交易日格式无效，知识引用日期无法核对")
    if not normalized_query_date:
        routing_warnings.append("查询日期缺失，知识引用时间无法核对")
    elif not query_date_valid:
        routing_warnings.append("查询日期格式无效，知识引用时间无法核对")
    facts_valid = facts is None or isinstance(facts, Mapping)
    if not facts_valid:
        routing_warnings.append("knowledge_facts_type_invalid")
    routed_facts = _sanitize_routed_facts(
        facts if isinstance(facts, Mapping) else {},
        warnings=routing_warnings,
    )
    normalized_facts_source = "explicit" if str(facts_source or "").strip() == "explicit" else "derived"
    manifest_data = manifest if isinstance(manifest, Mapping) else {}
    manifest_warning_items = manifest_data.get("warnings")
    manifest_error_items = manifest_data.get("errors")
    manifest_warnings = (
        [str(item) for item in manifest_warning_items]
        if isinstance(manifest_warning_items, list)
        else []
    )
    manifest_errors = (
        [str(item) for item in manifest_error_items]
        if isinstance(manifest_error_items, list)
        else []
    )
    validation_errors = list(
        dict.fromkeys(
            [
                *validate_knowledge_manifest(manifest),
                *validate_knowledge_manifest_sources(
                    manifest,
                    root=Path(source_root) if source_root is not None else PROJECT_ROOT,
                ),
            ]
        )
    )
    manifest_availability = str(manifest_data.get("availability") or "invalid").strip()
    trace_warnings = [
        *routing_warnings,
        *manifest_warnings,
        *manifest_errors,
        *validation_errors,
    ]
    if validation_errors or manifest_availability == "invalid":
        trace_warnings.append("知识清单缺失或格式无效，停止生成知识引用")
    trace_warnings = list(dict.fromkeys(trace_warnings))
    if (
        validation_errors
        or manifest_availability == "invalid"
        or not target_date_valid
        or not query_date_valid
        or not facts_valid
    ):
        manifest_availability = "invalid"
        manifest_entries = []
    else:
        manifest_entries = [
            _manifest_entry_as_router_entry(entry)
            for entry in manifest_data.get("entries") or []
            if isinstance(entry, Mapping) and entry.get("available") is True
        ]
    ranked_matches = _rank_knowledge_entries(
        routed_facts,
        entries=manifest_entries,
        scenario=scenario,
        include_fact_keys=False,
        enforce_required_conditions=True,
        strict_terms=True,
    )
    normalized_fact_sources = _normalize_fact_sources(
        routed_facts,
        facts_source=normalized_facts_source,
        fact_sources=fact_sources,
        warnings=trace_warnings,
    )
    trace_warnings = list(dict.fromkeys(trace_warnings))
    hits = []
    for rank, ranked in enumerate(ranked_matches[: max(0, int(limit or 0))], start=1):
        score, _, _, _, entry, matched_terms, matched_details = ranked
        matched_conditions = [item["label"] for item in matched_details]
        hit = _build_hit(entry, matched_terms, matched_conditions, rank)
        matched_paths = _matched_fact_paths(
            routed_facts,
            matched_terms,
            matched_details,
            strict_terms=True,
        )
        hit.update(
            {
                "rank": rank,
                "score": score,
                "matched_fact_paths": matched_paths,
                "matched_fact_sources": [
                    {"path": path, **normalized_fact_sources[path]}
                    for path in matched_paths
                    if path in normalized_fact_sources
                ],
                "source_ref": dict(entry.get("source_ref") or {}),
                "decision_effect": entry.get("decision_effect") or entry.get("impact") or "",
                "decision_scope": entry.get("decision_scope") or "explanation_only",
                "used_for": ["knowledge_citation", "explanation", "review"],
                "not_used_for": list(DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE),
            }
        )
        hits.append(hit)

    trace = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "target_date": normalized_target_date,
        "query_date": normalized_query_date,
        "scenario": str(scenario or "").strip(),
        "manifest_hash": str(manifest_data.get("manifest_hash") or "").strip(),
        "facts_hash": stable_json_hash(routed_facts),
        "facts_source": normalized_facts_source,
        "fact_sources": normalized_fact_sources,
        "decision_scope": "explanation_only",
        "not_used_for": list(DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE),
        "availability": manifest_availability,
        "warnings": trace_warnings,
        "hits": hits,
    }
    trace["trace_hash"] = stable_json_hash(trace)
    return trace


def route_llm_wiki_knowledge(
    facts: Dict[str, Any] | None,
    *,
    scenario: str = "daily_report",
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Return compatibility hits from registered fact roots or a free-text question."""
    if not isinstance(facts, Mapping):
        return []
    routed_facts = {
        key: value
        for key, value in facts.items()
        if key in EXPLICIT_FACT_ROOTS
        or (key == "question" and isinstance(value, str))
    }
    if not routed_facts:
        return []
    ranked_matches = _rank_knowledge_entries(
        routed_facts,
        entries=KNOWLEDGE_INDEX,
        scenario=scenario,
    )
    hits = []
    for _, _, _, _, entry, matched_terms, matched_details in ranked_matches[: max(0, int(limit or 0))]:
        matched_conditions = [item["label"] for item in matched_details]
        hits.append(_build_hit(entry, matched_terms, matched_conditions, len(hits) + 1))
    return hits


__all__ = [
    "DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE",
    "EXPLICIT_FACT_ROOTS",
    "EXPLICIT_FACT_PATHS",
    "KNOWLEDGE_INDEX",
    "TRACE_SCHEMA_VERSION",
    "build_llm_wiki_fact_bundle",
    "build_llm_wiki_fact_tags",
    "is_iso_calendar_date",
    "route_llm_wiki_knowledge",
    "route_llm_wiki_knowledge_trace",
]
