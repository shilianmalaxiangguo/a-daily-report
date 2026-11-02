"""Project new-high breadth snapshots into an auditable structure signal."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any


_PLACEHOLDER_SECTORS = {
    "",
    "-",
    "未知",
    "未归类",
    "待补充板块",
    "待补事实",
    "暂无",
}
_SINGLE_DIGIT_LIMIT = 10
_EXTREME_DIFFUSION_PCT = 5.0
_EFFECTIVE_DIFFUSION_PCT = 2.0
_COLD_DIFFUSION_PCT = 1.0
_FRACTURE_OBSERVATION_PCT = 0.2
_BREADTH_LEVEL_RANK = {
    "diffusion_fracture": 0,
    "very_low_diffusion": 1,
    "cold_diffusion": 2,
    "effective_diffusion": 3,
    "extreme_diffusion": 4,
    "insufficient": -1,
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        number = float(value)
        return number if number == number else default
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _optional_int(value: Any) -> int | None:
    number = _optional_float(value)
    return int(number) if number is not None else None


def build_new_high_breadth_thresholds() -> dict[str, Any]:
    """Return the single report/chart contract for absolute new-high breadth."""

    return {
        "schema_version": "new_high_breadth_thresholds.v1",
        "single_digit_count": _SINGLE_DIGIT_LIMIT,
        "extreme_diffusion_pct": _EXTREME_DIFFUSION_PCT,
        "effective_diffusion_pct": _EFFECTIVE_DIFFUSION_PCT,
        "cold_diffusion_pct": _COLD_DIFFUSION_PCT,
        "fracture_observation_pct": _FRACTURE_OBSERVATION_PCT,
        "levels": [
            {"code": "extreme_diffusion", "label": "极致扩散", "range": ">=5%"},
            {"code": "effective_diffusion", "label": "有效扩散", "range": "2%-5%"},
            {"code": "cold_diffusion", "label": "扩散偏冷", "range": "1%-2%"},
            {"code": "very_low_diffusion", "label": "极低扩散", "range": "0.2%-1%"},
            {
                "code": "diffusion_fracture",
                "label": "扩散断层",
                "range": "<0.2%或新高数<10只",
            },
        ],
        "mark_lines": [
            {"value": 5.0, "label": "5% 极致扩散线", "tone": "extreme"},
            {"value": 2.0, "label": "2% 有效扩散分界", "tone": "effective"},
            {"value": 1.0, "label": "1% 极低扩散分界", "tone": "cold"},
            {"value": 0.2, "label": "0.2% 断层观察线", "tone": "fracture"},
        ],
    }


def classify_new_high_breadth_level(
    all_a_share_pct: Any,
    new_high_count: Any = None,
) -> dict[str, Any]:
    """Classify absolute breadth without turning it into a trading action."""

    pct = _optional_float(all_a_share_pct)
    count = _optional_int(new_high_count)
    if count is not None and 0 <= count < _SINGLE_DIGIT_LIMIT:
        code = "diffusion_fracture"
        label = "扩散断层"
        reason = f"新高数低于{_SINGLE_DIGIT_LIMIT}只"
        level_range = "<0.2%或新高数<10只"
    elif pct is None or pct < 0:
        code = "insufficient"
        label = "事实不足"
        reason = "全A占比缺失或无效"
        level_range = "待补事实"
    elif pct >= _EXTREME_DIFFUSION_PCT:
        code = "extreme_diffusion"
        label = "极致扩散"
        reason = "全A占比达到5%及以上"
        level_range = ">=5%"
    elif pct >= _EFFECTIVE_DIFFUSION_PCT:
        code = "effective_diffusion"
        label = "有效扩散"
        reason = "全A占比处于2%到5%"
        level_range = "2%-5%"
    elif pct >= _COLD_DIFFUSION_PCT:
        code = "cold_diffusion"
        label = "扩散偏冷"
        reason = "全A占比处于1%到2%"
        level_range = "1%-2%"
    elif pct >= _FRACTURE_OBSERVATION_PCT:
        code = "very_low_diffusion"
        label = "极低扩散"
        reason = "全A占比处于0.2%到1%"
        level_range = "0.2%-1%"
    else:
        code = "diffusion_fracture"
        label = "扩散断层"
        reason = "全A占比低于0.2%"
        level_range = "<0.2%或新高数<10只"
    return {
        "breadth_level": code,
        "breadth_level_label": label,
        "breadth_level_reason": reason,
        "breadth_level_range": level_range,
        "breadth_level_rank": _BREADTH_LEVEL_RANK[code],
    }


def _normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return text


def _valid_sector(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text in _PLACEHOLDER_SECTORS else text


def _as_rows(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in snapshot.get("trend_rows") or []:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        item["trade_date"] = _normalize_date(item.get("trade_date") or item.get("date"))
        if not item["trade_date"]:
            continue
        item["new_high_count"] = max(0, _safe_int(item.get("new_high_count")))
        item["all_a_share_pct"] = round(_safe_float(item.get("all_a_share_pct")), 2)
        rows.append(item)
    return sorted(rows, key=lambda item: item["trade_date"])


def _source_is_comparable(row: Mapping[str, Any]) -> bool:
    trade_date = _normalize_date(row.get("trade_date"))
    source = str(row.get("source") or "").strip()
    source_date = _normalize_date(row.get("source_date"))
    return bool(source and source_date and source_date == trade_date)


def _sector_rows(snapshot: Mapping[str, Any], current_row: Mapping[str, Any]) -> list[dict[str, Any]]:
    row_sectors = current_row.get("sector_distribution")
    if isinstance(row_sectors, list):
        return [dict(item) for item in row_sectors if isinstance(item, Mapping)]
    top_level_sectors = snapshot.get("sector_distribution")
    current_date = _normalize_date(current_row.get("trade_date") or current_row.get("date"))
    top_level_dates = [
        _normalize_date(snapshot.get(field))
        for field in ("trade_date", "source_date")
        if str(snapshot.get(field) or "").strip()
    ]
    if (
        isinstance(top_level_sectors, list)
        and current_date
        and top_level_dates
        and all(source_date == current_date for source_date in top_level_dates)
    ):
        return [dict(item) for item in top_level_sectors if isinstance(item, Mapping)]
    return []


def _sector_summary(
    snapshot: Mapping[str, Any],
    current_row: Mapping[str, Any],
    current_count: int,
) -> dict[str, Any]:
    raw_rows = _sector_rows(snapshot, current_row)
    sector_counts: dict[str, int] = {}
    for raw in raw_rows:
        sector = _valid_sector(raw.get("sector"))
        count = max(0, _safe_int(raw.get("new_high_count")))
        if not sector or count <= 0:
            continue
        sector_counts[sector] = sector_counts.get(sector, 0) + count
    rows = [
        {"sector": sector, "new_high_count": count}
        for sector, count in sector_counts.items()
    ]
    rows.sort(key=lambda item: (-item["new_high_count"], item["sector"]))
    sector_count = len(rows)
    top = rows[0] if rows else {}
    top_count = _safe_int(top.get("new_high_count"))
    covered_count = sum(item["new_high_count"] for item in rows)
    top_share = round(top_count / current_count * 100.0, 2) if current_count > 0 else 0.0
    coverage_pct = round(covered_count / current_count * 100.0, 2) if current_count > 0 else 0.0
    coverage_valid = bool(current_count > 0 and covered_count <= current_count)
    sufficient = bool(rows and coverage_valid and coverage_pct >= 80.0)
    fragmented = bool(
        sufficient
        and current_count <= _SINGLE_DIGIT_LIMIT
        and sector_count >= 3
        and top_share <= 50.0
    )
    clustered = bool(sufficient and top_count >= 2 and top_share > 50.0)
    return {
        "sector_count": sector_count,
        "sector_covered_count": covered_count,
        "top_sector": top.get("sector", "") if sufficient else "",
        "top_sector_share_pct": top_share if sufficient else 0.0,
        "sector_coverage_pct": coverage_pct,
        "sector_coverage_valid": coverage_valid,
        "sector_data_available": sufficient,
        "sector_fragmented": fragmented,
        "sector_clustered": clustered,
    }


def _format_count_change(change_count: int, change_ratio_pct: float | None) -> str:
    if change_ratio_pct is None:
        return f"较前一可见行{change_count:+d}只"
    return f"较前一可见行{change_count:+d}只（{change_ratio_pct:+.2f}%）"


def build_new_high_structure_signal(
    snapshot: Mapping[str, Any] | None,
    target_date: str = "",
) -> dict[str, Any]:
    """Return structure-only evidence; never produces a trading action."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    requested_date = _normalize_date(target_date)
    rows = _as_rows(snapshot)
    available = bool(snapshot.get("available"))
    result: dict[str, Any] = {
        "available": available,
        "target_date": requested_date,
        "target_date_match": True,
        "matched_trade_date": "",
        "current_count": None,
        "current_pct": None,
        "previous_count": None,
        "change_count": None,
        "change_ratio_pct": None,
        "window_peak_count": None,
        "peak_retention_pct": None,
        "single_digit": False,
        "first_single_digit_in_window": False,
        "rapid_contraction": False,
        "breadth_level": "insufficient",
        "breadth_level_label": "事实不足",
        "breadth_level_reason": "创新高事实未形成",
        "breadth_level_range": "待补事实",
        "breadth_level_rank": -1,
        "previous_breadth_level": "insufficient",
        "previous_breadth_level_label": "事实不足",
        "breadth_level_change_steps": None,
        "breadth_direction": "待累计",
        "breadth_thresholds": build_new_high_breadth_thresholds(),
        "sector_count": 0,
        "top_sector": "",
        "top_sector_share_pct": 0.0,
        "sector_coverage_pct": 0.0,
        "sector_data_available": False,
        "sector_fragmented": False,
        "sector_clustered": False,
        "history_comparable": False,
        "state": "待累计",
        "severity": "事实不足",
        "summary": "事实不足：创新高趋势行未形成可复核结构样本。",
        "risk_note": "当前只作结构观察，不改变候选、明日对象、仓位、B1/B2或退出动作。",
        "counterevidence": "若同源数据连续回升、板块重新成群且后排承接改善，收缩判断应降级。",
        "next_window": "下一窗口复核创新高是否连续回升、是否形成板块集群，以及核心与所属板块能否重新同步。",
        "warnings": [],
    }

    if not available:
        result["warnings"] = ["创新高快照不可用"]
        result["summary"] = "事实不足：创新高快照不可用，暂不判断扩散收缩。"
        return result

    current_index = len(rows) - 1
    if rows:
        if requested_date:
            matches = [index for index, row in enumerate(rows) if row["trade_date"] == requested_date]
            if matches:
                current_index = matches[-1]
            else:
                result["target_date_match"] = False
                result["warnings"].append("目标日未在创新高趋势行中匹配")
        current_row = rows[current_index]
    else:
        current_row = {
            "trade_date": requested_date,
            "new_high_count": max(0, _safe_int(snapshot.get("new_high_count"))),
            "all_a_share_pct": round(_safe_float(snapshot.get("all_a_share_pct")), 2),
            "source": snapshot.get("source", ""),
            "source_date": snapshot.get("source_date", ""),
        }
        current_index = 0

    if (
        not current_row.get("source")
        and rows
        and current_index == len(rows) - 1
        and (not requested_date or current_row.get("trade_date") == requested_date)
    ):
        current_row["source"] = snapshot.get("source", "")
        current_row["source_date"] = snapshot.get("source_date", "")
    current_date = _normalize_date(current_row.get("trade_date"))
    current_count = max(0, _safe_int(current_row.get("new_high_count")))
    current_pct = round(_safe_float(current_row.get("all_a_share_pct")), 2)
    prior_rows = rows[:current_index]
    previous_row = prior_rows[-1] if prior_rows else None
    previous_count = _safe_int(previous_row.get("new_high_count")) if previous_row else None
    previous_pct = round(_safe_float(previous_row.get("all_a_share_pct")), 2) if previous_row else None
    change_count = current_count - previous_count if previous_row else None
    comparable_rows = [current_row, previous_row] if previous_row else []
    sources = {str(row.get("source") or "").strip() for row in comparable_rows if row}
    history_comparable = bool(
        previous_row
        and all(_source_is_comparable(row) for row in comparable_rows if row)
        and len(sources) == 1
    )
    change_ratio = (
        round(change_count / previous_count * 100.0, 2)
        if history_comparable and previous_count > 0
        else None
    )
    if previous_row and not history_comparable:
        result["warnings"].append("逐日来源或来源日期不足，跨日速度只作结构观察")

    window_counts = [max(0, _safe_int(row.get("new_high_count"))) for row in rows[: current_index + 1]]
    window_peak = max(window_counts) if window_counts else current_count
    peak_retention = (
        round(current_count / window_peak * 100.0, 2)
        if history_comparable and window_peak > 0
        else None
    )
    single_digit = current_count < _SINGLE_DIGIT_LIMIT
    first_single_digit = bool(single_digit and not any(count < _SINGLE_DIGIT_LIMIT for count in window_counts[:-1]))
    rapid_contraction = bool(
        history_comparable
        and previous_count
        and previous_count > 0
        and current_count <= previous_count * 0.5
    )
    current_level = classify_new_high_breadth_level(current_pct, current_count)
    previous_level = (
        classify_new_high_breadth_level(previous_pct, previous_count)
        if previous_row
        else classify_new_high_breadth_level(None, None)
    )
    level_change_steps = (
        current_level["breadth_level_rank"] - previous_level["breadth_level_rank"]
        if history_comparable
        else None
    )
    low_level_codes = {"cold_diffusion", "very_low_diffusion", "diffusion_fracture"}
    low_repair = bool(
        history_comparable
        and previous_count is not None
        and previous_pct is not None
        and current_count > previous_count
        and current_pct > previous_pct
        and current_level["breadth_level"] in low_level_codes
        and previous_level["breadth_level"] in low_level_codes
        and current_count < window_peak
    )
    if low_repair:
        breadth_direction = "低位修复"
    elif history_comparable and previous_count is not None and previous_pct is not None:
        if current_count < previous_count and current_pct < previous_pct:
            breadth_direction = "扩散收缩"
        elif current_count > previous_count and current_pct > previous_pct:
            breadth_direction = "扩散增强"
        elif current_count == previous_count and current_pct == previous_pct:
            breadth_direction = "持平"
        else:
            breadth_direction = "方向分歧"
    else:
        breadth_direction = "待累计"

    sector_info = _sector_summary(snapshot, current_row, current_count)
    result.update(
        {
            "matched_trade_date": current_date,
            "current_count": current_count,
            "current_pct": current_pct,
            "previous_count": previous_count,
            "change_count": change_count,
            "change_ratio_pct": change_ratio,
            "window_peak_count": window_peak,
            "peak_retention_pct": peak_retention,
            "single_digit": single_digit,
            "first_single_digit_in_window": first_single_digit,
            "rapid_contraction": rapid_contraction,
            **current_level,
            "previous_breadth_level": previous_level["breadth_level"],
            "previous_breadth_level_label": previous_level["breadth_level_label"],
            "breadth_level_change_steps": level_change_steps,
            "breadth_direction": breadth_direction,
            "history_comparable": history_comparable,
            **sector_info,
        }
    )

    if not result["target_date_match"]:
        result["state"] = "待累计"
        result["severity"] = "事实不足"
        result["summary"] = "事实不足：目标日未在创新高趋势行中匹配，只保留最新可见样本，不计算精确跨日变化。"
        return result
    if not rows or previous_row is None:
        result["state"] = "待累计"
        result["severity"] = "事实不足"
        result["summary"] = (
            f"事实不足：当前{current_count}只、全A占比{current_pct:.2f}%，但缺少前序创新高趋势行，"
            "暂不判断扩散速度和窗口位置。"
        )
        return result
    if current_count <= 0:
        result["state"] = "待累计"
        result["severity"] = "事实不足"
        result["summary"] = "事实不足：目标日创新高数量为空或无效，暂不判断扩散结构。"
        return result

    if low_repair:
        state = "低位修复"
        severity = "低"
    elif current_level["breadth_level"] == "diffusion_fracture":
        state = "扩散断层预警"
        severity = "高"
    elif (
        rapid_contraction
        or (
            breadth_direction == "扩散收缩"
            and level_change_steps is not None
            and level_change_steps <= -2
        )
        or (
            peak_retention is not None
            and peak_retention <= 50.0
            and current_count < (previous_count or current_count)
        )
    ):
        state = "扩散收缩"
        severity = "中"
    else:
        state = "扩散震荡"
        severity = "低"
    result["state"] = state
    result["severity"] = severity

    if history_comparable and change_count is not None:
        change_text = _format_count_change(change_count, change_ratio)
    elif change_count is not None:
        change_text = "可见序列较前一行收缩" if change_count < 0 else "可见序列较前一行回升" if change_count > 0 else "可见序列较前一行持平"
    else:
        change_text = "较前一可见行待累计"
    peak_text = f"窗口峰值保留率{peak_retention:.2f}%" if history_comparable and peak_retention is not None else "窗口逐日来源未形成同口径，峰值保留率不计算"
    single_text = "首次进入个位数" if first_single_digit else ("处于个位数" if single_digit else "尚未进入个位数")
    sector_text = ""
    if sector_info["sector_data_available"]:
        if sector_info["sector_fragmented"]:
            sector_text = f"有效板块{sector_info['sector_count']}个、头部占比{sector_info['top_sector_share_pct']:.2f}%，呈板块碎片化"
        elif sector_info["sector_clustered"]:
            sector_text = f"头部板块为{sector_info['top_sector']}、占比{sector_info['top_sector_share_pct']:.2f}%，存在成群迹象"
        else:
            sector_text = f"有效板块{sector_info['sector_count']}个，暂未形成清晰集群"
    elif not sector_info["sector_coverage_valid"]:
        sector_text = (
            f"板块归属覆盖数{sector_info['sector_covered_count']}只超过当前新高{current_count}只，"
            "事实不足，不能判断板块成群或主导"
        )
    else:
        sector_text = "板块归属不足，不能判断板块成群或主导"
    source_text = ""
    if not history_comparable and previous_row:
        source_text = "逐日采集来源或来源日期未统一，跨日速度和峰值保留率不计算"
    result["summary"] = (
        f"{state}：当前{current_count}只、全A占比{current_pct:.2f}%，"
        f"绝对水位为{current_level['breadth_level_label']}；{single_text}；"
        f"{change_text}，{peak_text}；{sector_text}。"
    )
    if source_text:
        result["summary"] += f" {source_text}。"
    if state == "低位修复":
        result["risk_note"] = (
            f"低位回升说明前一轮收缩正在修复，但绝对水位仍为{current_level['breadth_level_label']}；"
            "不能继续累加周期收缩故事，仍需确认回升能否持续并形成板块集群。"
            "这只是结构观察，不改变候选、明日对象、仓位、B1/B2或退出动作。"
        )
    elif state == "扩散震荡":
        result["risk_note"] = (
            "当前尚未确认快速收缩，趋势生成率仍需观察是否重新扩散；若后排掉队再叠加核心独强，才提高风险复核优先级。"
            "这只是结构观察，不改变候选、明日对象、仓位、B1/B2或退出动作。"
        )
    else:
        result["risk_note"] = (
            f"{state}说明新趋势生成率正在收缩，若后排继续掉队而核心仍独强，需观察生态转弱后是否向核心和指数传导；"
            "这只是风险候选，不是机械卖出条件，也不改变候选、明日对象、仓位、B1/B2或退出动作。"
        )
    result["counterevidence"] = (
        "长期下跌后的低位可能对应卖压衰竭；若同源数据连续回升、新板块成群、后排承接改善，"
        "或核心与所属板块重新同步，扩散收缩判断降级。"
    )
    result["next_window"] = (
        "下一窗口复核创新高是否连续回升、是否形成板块集群、后排是否恢复承接，以及核心与所属板块能否重新同步；"
        "板块归属不足时不判断某个板块主导。"
    )
    return result


__all__ = [
    "build_new_high_breadth_thresholds",
    "build_new_high_structure_signal",
    "classify_new_high_breadth_level",
]
