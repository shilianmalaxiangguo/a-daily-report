from __future__ import annotations


CANDIDATE_SOURCE_DISPLAY_LABELS = {
    "sector_derived_candidates": "板块推导候选",
    "sector_capital_carrier_strategy": "板块资金载体",
    "market_emotion_candidates": "市场情绪线候选",
    "sector_leader_candidates": "板块核心候选",
    "extreme_conviction_list": "高确信观察池",
    "crossline_observation_stocks": "跨线观察池",
    "candidates": "通用过程池",
    "watchlist": "观察池",
    "core_stocks": "主线核心池",
    "secondary_stocks": "次级候选池",
    "hot_rank": "热榜",
    "hot_rank_top30": "热榜",
    "hot_rank_top50": "热榜",
    "integrated_hot": "综合热度",
    "integrated_hot_list": "综合热度",
    "limit_up": "涨停/连板证据",
    "turnover": "成交额排行",
    "turnover_rank": "成交额排行",
    "turnover_over_100b": "成交额排行",
    "selected_position_candidate": "运行时观察对象",
}


def candidate_source_display_label(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    source_key = text.rsplit(".", 1)[-1]
    if source_key in CANDIDATE_SOURCE_DISPLAY_LABELS:
        return CANDIDATE_SOURCE_DISPLAY_LABELS[source_key]
    if text.isascii() and all(char.isalnum() or char in "._-" for char in text):
        return "其他过程来源"
    return text
