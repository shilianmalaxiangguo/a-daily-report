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
        "topics": ["汰弱留强", "资金优先级", "旧仓新机会分离", "换仓"],
        "trigger_terms": ["汰弱留强", "汰强留弱", "卖强补弱", "弱替代", "浮盈浮亏", "换仓", "旧仓", "新机会"],
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "资金优先级",
        "confidence": "verified",
        "impact": "先判旧仓是否仍被市场选择，再判新机会是否更强且窗口和亏损边界清楚；不卖强补弱，不用做T便利性替代强弱比较。",
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
        "title": "先挣分、再扣分、再看动作上限",
        "topics": ["候选质量", "动作层级", "恢复条件", "取关条件"],
        "trigger_terms": ["候选质量", "动作上限", "恢复条件", "取关条件", "风险项"],
        "scenarios": ["daily_report", "candidate_quality", "review"],
        "report_slot": "候选质量",
        "confidence": "verified",
        "impact": "候选先看质量、风险和动作上限，分数服务排序，最多能做什么由条件决定。",
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
        "topics": ["价格行为", "价格趋势优先", "A股量价本地化", "趋势区间谱系", "始终入场", "二次入场", "交易者等式"],
        "trigger_terms": [
            "布鲁克斯",
            "价格行为",
            "价格趋势",
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
        ],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "价格行为判断",
        "confidence": "reviewed",
        "impact": "先判趋势/交易区间，再看信号是否有后续行情；成交量只作资金表态证据，必须由价格强收盘、回踩不破或后续行情确认；错过强趋势只允许小仓按同一失效线参与。",
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
    market_facts: Dict[str, Any] = {}
    if "指数强" in index_relation or "指数强" in summary_text:
        market_facts["index_trend"] = "上涨"
    if "上涨家数偏弱" in fact_basis_text or "真实赚钱效应弱" in summary_text:
        market_facts["breadth"] = "上涨家数偏弱"
    if "结构集中" in summary_text:
        market_facts["turnover_distribution"] = "成交集中"
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
