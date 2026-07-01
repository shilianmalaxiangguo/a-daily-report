"""Explainable LLM Wiki routing for daily-report knowledge hits."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


KNOWLEDGE_INDEX = [
    {
        "id": "market.low-frequency-focus",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "指数强但赚钱效应弱",
        "topics": ["市场结构", "低频聚焦", "窄池子进攻"],
        "trigger_terms": ["指数上涨", "上涨家数偏弱", "成交集中", "指数强", "跌多涨少"],
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
        "scenarios": ["daily_report", "intraday_question", "candidate_quality"],
        "report_slot": "账户约束",
        "confidence": "verified",
        "impact": "实际不可买只影响当前账户参与，不降低市场核心、池内身份或板块锚价值。",
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
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "资金优先级",
        "confidence": "verified",
        "impact": "先判旧仓是否失去持仓资格，卖旧仓看旧仓资格；再判新机会是否取得执行资格，买新仓看新仓资格；不卖强补弱，也不用FOMO把两笔判断合成一次满仓替换。",
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
        "scenarios": ["intraday_question", "review", "daily_report"],
        "report_slot": "交易纪律",
        "confidence": "verified",
        "impact": "FOMO 是外部价格刺激被自己接住后的情绪，不是执行资格；反包先批改情绪反应，不直接批改前一日信息集。必卖日里，反抽、0轴、VWAP和开盘价修复先看作旧仓退出流动性；卖出后第一天因反包、后悔或怕踏空想买回，默认不执行，只能收盘后重新进入 T0 评估。",
    },
    {
        "id": "discipline.tplus-slot-timeline",
        "prior": "trade-discipline-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "Ta/Tb/Tc 日序时间表",
        "topics": ["Ta/Tb/Tc", "日序", "T+2必卖", "空仓", "没有Tb", "没有Tc"],
        "trigger_terms": [
            "Ta",
            "Tb",
            "Tc",
            "Ta+2",
            "Tb+0",
            "Tb+1",
            "Tc+0",
            "T+2必卖",
            "日序",
            "甘特图",
            "没有Tb",
            "没有Tc",
            "全天空仓",
        ],
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "持仓日序",
        "confidence": "reviewed",
        "impact": "Ta/Tb/Tc 要表格化呈现账户时间占用：Ta 是旧仓，处在 Ta+2 时优先退出；Tb 只来自今晚日报写入的明日目标，没有目标就写没有 Tb+0；Tc 只能由下一份日报重新决定，没有 Tc+0 时不得盘中临时补位。",
    },
    {
        "id": "intraday.do-t-risk-control",
        "prior": "intraday-question-prior",
        "source_path": "wiki/交易思想/做T与风险控制.md",
        "title": "做T先降风险，确认后买回",
        "topics": ["做T", "风险控制", "买回确认", "点位依据"],
        "trigger_terms": ["做T", "亏损", "反弹", "买回", "更便宜"],
        "scenarios": ["intraday_question", "daily_report", "review"],
        "report_slot": "盘中问股前提",
        "confidence": "verified",
        "impact": "做T先看防守线、止盈线和买回确认，不把更便宜当作更正确。",
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
        "scenarios": ["daily_report", "review"],
        "report_slot": "市场结构判断",
        "confidence": "verified",
        "impact": "同一炒作逻辑链连续扩散并有后排承接时，才提高修复级别。",
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
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "研究线索",
        "confidence": "reviewed",
        "impact": "先拆产业链并验证瓶颈，再把线索降维成研究优先级；不直接生成买入资格，交易动作仍看价格承接、板块选择和失效条件。",
    },
]


def _flatten_terms(value: Any) -> List[str]:
    terms: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            terms.append(str(key))
            terms.extend(_flatten_terms(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            terms.extend(_flatten_terms(item))
    elif value is not None:
        text = str(value).strip()
        if text:
            terms.append(text)
    return terms


def _joined_terms(facts: Dict[str, Any]) -> str:
    terms = _flatten_terms(facts or {})
    market = (facts or {}).get("market") if isinstance(facts, dict) else {}
    if isinstance(market, dict) and str(market.get("index_trend", "") or "").strip() == "上涨":
        terms.append("指数上涨")
    return " ".join(terms)


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
    return market_facts


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

    return {"account": account_facts, "candidate": candidate_facts}


def _build_position_capital_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    resolution = _final_target_resolution_from_data(data)
    decision = _first_dict(resolution.get("capital_priority_decision"))
    existing_position = _first_dict(
        resolution.get("existing_position_target"),
        _existing_position_summary_from_data(data),
    )
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

    if has_existing_position or capital_priority in old_position_priority:
        position_facts["state"] = "旧仓"
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

    result: Dict[str, Any] = {}
    if position_facts:
        result["position"] = position_facts
    if candidate_facts:
        result["candidate"] = candidate_facts
    if capital_priority:
        result["capital_priority"] = capital_priority
    return result


def build_llm_wiki_fact_tags(data: Dict[str, Any] | None) -> Dict[str, Any]:
    """Extract compact fact tags used by the explainable Wiki router."""
    if not isinstance(data, dict):
        return {}
    explicit = data.get("knowledge_hit_facts")
    if isinstance(explicit, dict):
        return dict(explicit)

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
    return facts


def _term_matches(term: str, text: str) -> bool:
    return bool(term and term in text)


def _matched_trigger_terms(entry: Dict[str, Any], facts_text: str) -> List[str]:
    return [
        str(term)
        for term in entry.get("trigger_terms", [])
        if _term_matches(str(term), facts_text)
    ]


def _scenario_allowed(entry: Dict[str, Any], scenario: str) -> bool:
    scenarios = [str(item) for item in entry.get("scenarios", [])]
    return not scenario or scenario in scenarios


def _build_hit(entry: Dict[str, Any], matched_terms: Iterable[str], index: int) -> Dict[str, Any]:
    return {
        "hit_id": f"kh-{index:03d}",
        "knowledge_id": entry["id"],
        "prior": entry["prior"],
        "source_path": entry["source_path"],
        "title": entry["title"],
        "triggered_by": list(matched_terms),
        "matched_topics": list(entry.get("topics", [])),
        "impact": entry["impact"],
        "report_slot": entry["report_slot"],
        "confidence": entry["confidence"],
    }


def route_llm_wiki_knowledge(
    facts: Dict[str, Any] | None,
    *,
    scenario: str = "daily_report",
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Return explainable Wiki knowledge hits for the supplied report facts."""
    facts_text = _joined_terms(facts or {})
    ranked_matches = []
    for order, entry in enumerate(KNOWLEDGE_INDEX):
        if not _scenario_allowed(entry, scenario):
            continue
        matched_terms = _matched_trigger_terms(entry, facts_text)
        if matched_terms:
            ranked_matches.append((len(matched_terms), -order, entry, matched_terms))

    ranked_matches.sort(reverse=True)
    hits = []
    for _, _, entry, matched_terms in ranked_matches[: max(0, int(limit or 0))]:
        hits.append(_build_hit(entry, matched_terms, len(hits) + 1))
    return hits


__all__ = ["KNOWLEDGE_INDEX", "build_llm_wiki_fact_tags", "route_llm_wiki_knowledge"]
