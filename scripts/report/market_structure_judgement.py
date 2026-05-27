from __future__ import annotations


def _safe_float(*values, default=0.0):
    for value in values:
        try:
            if value not in (None, ""):
                return float(value)
        except (TypeError, ValueError):
            continue
    return float(default)


def _safe_int(*values, default=0):
    return int(_safe_float(*values, default=default))


def _text(value, default=""):
    text = str(value or "").strip()
    return text or default


def _first_index_change(data, market_research_snapshot):
    explicit = (market_research_snapshot or {}).get("market_structure_inputs") or {}
    if explicit.get("index_change_pct") not in (None, ""):
        return _safe_float(explicit.get("index_change_pct"))
    indices = (data or {}).get("indices") or {}
    for name in ("创业板指", "创业板", "中证全指", "上证指数"):
        item = indices.get(name) or {}
        if isinstance(item, dict) and item.get("涨跌幅") not in (None, ""):
            return _safe_float(item.get("涨跌幅"))
    wind_all = (data or {}).get("wind_a_alternative") or {}
    if isinstance(wind_all, dict):
        return _safe_float(wind_all.get("涨跌幅"))
    return 0.0


def _market_counts(data, market_research_snapshot):
    explicit = (market_research_snapshot or {}).get("market_structure_inputs") or {}
    market_stats = (data or {}).get("market_stats") or {}
    return {
        "up_count": _safe_int(explicit.get("up_count"), market_stats.get("up_count"), (data or {}).get("up_count")),
        "down_count": _safe_int(explicit.get("down_count"), market_stats.get("down_count"), (data or {}).get("down_count")),
    }


def _turnover(data, market_research_snapshot):
    explicit = (market_research_snapshot or {}).get("market_structure_inputs") or {}
    return _safe_float(explicit.get("total_turnover"), (data or {}).get("total_turnover"))


def _build_index_profit_relation(index_change_pct, up_count):
    if index_change_pct > 0 and 0 < up_count < 1500:
        return "指数强但真实赚钱效应弱，指数不能代表多数股票体感"
    if index_change_pct < -1 and 0 < up_count < 1200:
        return "指数和真实赚钱效应同时偏弱，先防亏钱效应扩散"
    if up_count >= 2800:
        return "指数与真实赚钱效应同向改善"
    return "指数与真实赚钱效应待确认"


def _build_turnover_distribution(turnover, up_count):
    if turnover >= 30000 and 0 < up_count < 1500:
        return "成交额高位但结构集中，不能按普涨支撑处理"
    if turnover >= 25000 and up_count >= 2500:
        return "成交额高位且扩散尚可，可继续看主线承接"
    if turnover > 0:
        return "成交额不低，仍需结合上涨家数和主线承接判断"
    return "成交额待确认"


def _build_rotation_nature(explicit):
    opposition = [str(item).strip() for item in explicit.get("opposition_rotation") or [] if str(item).strip()]
    neutral_topic = _text(explicit.get("neutral_topic"))
    if neutral_topic:
        return f"中性新题材{neutral_topic}出现，观察是否有新催化和主线承接"
    if opposition:
        return f"{'、'.join(opposition)}更像对立反弹，尚未证明主线切换"
    return "轮动性质待确认"


def _build_old_mainline_fatigue(explicit, market_research_snapshot):
    old_mainline = _text(explicit.get("old_mainline"))
    fatigue = bool(explicit.get("old_mainline_fatigue"))
    summary = _text(((market_research_snapshot or {}).get("mainline_turnover_summary") or {}).get("turnover_share_trend_summary"))
    if fatigue or "疲态" in summary or "回落" in summary:
        label = old_mainline or "老主线"
        return f"{label}仍活跃但短线疲态上升，只保留核心观察"
    if old_mainline:
        return f"{old_mainline}仍需看核心承接和扩散质量"
    return "老主线质量待确认"


def _build_tomorrow_rhythm(index_profit_relation, turnover_distribution, rotation_nature, old_mainline_fatigue):
    risk_text = "；".join([index_profit_relation, turnover_distribution, rotation_nature, old_mainline_fatigue])
    if (
        "真实赚钱效应弱" in risk_text
        and "结构集中" in risk_text
        and ("对立反弹" in risk_text or "疲态" in risk_text)
    ):
        return "低频聚焦"
    if "同时偏弱" in risk_text:
        return "不参与"
    if "同向改善" in risk_text and "扩散尚可" in risk_text:
        return "积极聚焦"
    return "观察聚焦"


def _candidate_policy(tomorrow_rhythm):
    if tomorrow_rhythm == "低频聚焦":
        return "只保留主线核心；题材荒时不从旧方向强行扩散候选"
    if tomorrow_rhythm == "不参与":
        return "候选统一降为观察，等待亏钱效应收敛"
    if tomorrow_rhythm == "积极聚焦":
        return "围绕主线核心和中性新题材核心做比较"
    return "先看主线承接，再决定是否缩小候选范围"


def build_market_structure_judgement(data=None, market_research_snapshot=None):
    data = data or {}
    market_research_snapshot = market_research_snapshot or {}
    explicit = market_research_snapshot.get("market_structure_inputs") or data.get("market_structure_inputs") or {}
    counts = _market_counts(data, market_research_snapshot)
    turnover = _turnover(data, market_research_snapshot)
    index_change_pct = _first_index_change(data, market_research_snapshot)

    if not explicit and turnover <= 0 and counts["up_count"] <= 0 and index_change_pct == 0:
        return {
            "index_profit_relation": "",
            "turnover_distribution": "",
            "rotation_nature": "",
            "old_mainline_fatigue": "",
            "new_topic_quality": "",
            "tomorrow_rhythm": "",
            "candidate_policy": "",
            "summary_text": "",
            "action_reason_text": "",
            "fact_basis": [],
        }

    index_profit_relation = _build_index_profit_relation(index_change_pct, counts["up_count"])
    turnover_distribution = _build_turnover_distribution(turnover, counts["up_count"])
    rotation_nature = _build_rotation_nature(explicit)
    old_mainline_fatigue = _build_old_mainline_fatigue(explicit, market_research_snapshot)
    new_topic_quality = "中性新题材待验证" if "中性新题材" in rotation_nature else "暂未出现新的中性主线"
    tomorrow_rhythm = _build_tomorrow_rhythm(index_profit_relation, turnover_distribution, rotation_nature, old_mainline_fatigue)
    candidate_policy = _candidate_policy(tomorrow_rhythm)
    summary_text = f"{index_profit_relation}；{turnover_distribution}；明日节奏：{tomorrow_rhythm}"
    action_reason_text = f"{tomorrow_rhythm}。原因是{index_profit_relation}，{turnover_distribution}，{rotation_nature}，{old_mainline_fatigue}。"
    up_count_basis = f"上涨家数{counts['up_count']}只"
    if 0 < counts["up_count"] < 1500:
        up_count_basis = f"上涨家数偏弱，{up_count_basis}"
    fact_basis = [
        f"指数涨跌幅{index_change_pct:.2f}%",
        up_count_basis,
        f"成交额{turnover:.2f}亿",
        rotation_nature,
        old_mainline_fatigue,
    ]
    return {
        "index_profit_relation": index_profit_relation,
        "turnover_distribution": turnover_distribution,
        "rotation_nature": rotation_nature,
        "old_mainline_fatigue": old_mainline_fatigue,
        "new_topic_quality": new_topic_quality,
        "tomorrow_rhythm": tomorrow_rhythm,
        "candidate_policy": candidate_policy,
        "summary_text": summary_text,
        "action_reason_text": action_reason_text,
        "fact_basis": fact_basis,
    }


def render_market_structure_section(judgement):
    judgement = judgement or {}
    if not _text(judgement.get("summary_text")):
        return []
    return [
        "### 3. 市场结构判断",
        "| 维度 | 结论 |",
        "|------|------|",
        f"| 指数与体感 | {judgement.get('index_profit_relation') or '待确认'} |",
        f"| 成交结构 | {judgement.get('turnover_distribution') or '待确认'} |",
        f"| 轮动性质 | {judgement.get('rotation_nature') or '待确认'} |",
        f"| 主线质量 | {judgement.get('old_mainline_fatigue') or '待确认'} |",
        f"| 明日节奏 | {judgement.get('tomorrow_rhythm') or '待确认'}；{judgement.get('candidate_policy') or '先看主线承接'} |",
        "",
    ]


def build_market_structure_knowledge_update(judgement):
    judgement = judgement or {}
    if judgement.get("tomorrow_rhythm") != "低频聚焦":
        return {}
    if "真实赚钱效应弱" not in _text(judgement.get("index_profit_relation")):
        return {}
    return {
        "topic": "市场结构判断",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "new_insight": "指数新高不等于真实赚钱效应改善；当上涨家数弱、成交集中、对立方向反弹时，日报应优先进入低频聚焦。",
        "fact_basis": "；".join(str(item).strip() for item in judgement.get("fact_basis") or [] if str(item).strip()),
        "suggested_nodes": [
            "wiki/板块补充/板块中枢与主线延续.md",
            "wiki/交易思想/价格行为与能量框架.md",
            "wiki/交易思想/AI摩擦与知识复利.md",
        ],
        "next_effect": "市场结构判断、候选数量、主线核心筛选、明日节奏",
    }


__all__ = [
    "build_market_structure_judgement",
    "build_market_structure_knowledge_update",
    "render_market_structure_section",
]
