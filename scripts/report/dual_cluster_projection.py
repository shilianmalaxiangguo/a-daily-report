from __future__ import annotations

from copy import deepcopy
from datetime import date
import re
from typing import Any, Mapping

from knowledge.llm_wiki_manifest import stable_json_hash


ACCOUNT_SCHEMA_VERSION = "account_day_order_dual_cluster.v1"
SECTOR_SCHEMA_VERSION = "sector_tournament_dual_cluster.v1"
DECISION_SCOPE = "explanation_only"
FORMAL_EFFECT = "none"
SOURCE_SECTOR_SCHEMA_VERSION = "sector_tournament_three_axis.v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
_DAY_ORDER_CODES = ("Ta", "Tb", "Tc", "Td", "Te")
_PENDING_MARKERS = (
    "持仓未输入",
    "待核实",
    "B1事实待确认",
    "未确认成交",
    "先确认",
    "只核实",
    "事实不清",
)
_EMPTY_MARKERS = (
    "空仓",
    "无旧仓",
    "没有B1/B2",
    "无B1占用",
    "0%不参与",
    "保持0%",
    "不参与",
)
_CORE_MARKERS = (
    "旧仓",
    "历史路径",
    "上一交易日路径",
    "最远复盘日",
    "历史复盘日",
    "只处理旧仓",
)
_DYNAMIC_MARKERS = (
    "新目标",
    "B1参与权",
    "B1先到",
    "同股",
    "冲击",
)
_WEAKEN_MARKERS = ("弱化", "走弱", "未修复", "降风险", "退出", "失去")
_DECAY_MARKERS = ("衰减", "无承接", "被吞没", "冲高回落")

_SECTOR_GAP_LABELS = {
    "direction": "资金方向",
    "sector_source_date": "目标日板块事实",
    "cross_day_continuity": "跨日延续",
    "core_acceptance": "核心承接",
    "target_day_price_acceptance": "目标日价格接受",
    "internal_expansion": "内部扩散",
    "competition_comparison": "竞争方向对照",
    "sector_diffusion_stage_evidence": "板块传导阶段证据",
    "local_trend_sector_proof": "局部趋势板块证据",
    "market_participation_limit": "市场参与范围依据",
    "cross_day_competition": "跨日竞争假设",
    "current_total_turnover": "目标日全市场成交额",
    "previous_total_turnover": "前一记录日全市场成交额",
    "market_breadth": "市场涨跌家数",
    "sector_internal_expansion": "板块内部扩散",
    "stage_mainline.direction": "阶段方向",
    "stage_mainline.direction_record": "阶段方向明细",
    "stage_mainline.stage_start_date": "阶段起点",
    "stage_mainline.stage_span_trading_days": "阶段跨度",
    "stage_mainline.active_trade_dates": "阶段活跃交易日",
    "stage_mainline.reflow_dates": "冷却后回流",
    "stage_mainline.sector_index_path": "板块指数逐日路径",
    "stage_mainline.relative_strength_metric": "板块指数相对强度",
    "stage_mainline.relative_strength_comparison": "板块指数相对强度",
    "stage_mainline.comparison_universe_scope.source_date": "相对强度比较范围来源日期",
    "stage_mainline.comparison_universe_scope.directions": "相对强度比较范围",
    "stage_mainline.internal_trend_density": "内部趋势股密度",
    "stage_mainline.divergence_repair": "分歧修复",
    "stage_mainline.field_source_dates": "阶段字段来源日期",
    "stage_mainline.active_trade_dates_outside_calendar": "活跃日与交易日历一致性",
    "stage_mainline.stage_date_invariant": "阶段日期顺序",
}
_SECTOR_GAP_PREFIX_LABELS = (
    ("stage_mainline.sector_index_path.", "板块指数逐日路径"),
    ("stage_mainline.comparison_universe_scope.", "相对强度比较范围"),
    ("stage_mainline.comparison_universe.", "板块指数相对强度"),
    ("stage_mainline.repair_evidence.", "分歧修复"),
    ("stage_mainline.", "阶段主线关键事实"),
)
_SECTOR_TRANSITION_STATUS_LABELS = {
    "confirmed": "已确认",
    "failed": "未成立",
    "unresolved": "待确认",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _strings(value: Any) -> list[str]:
    return [text for item in _list(value) if (text := _text(item))]


def _sector_gap_display_text(value: Any) -> str:
    labels = []
    seen = set()
    for raw in _strings(value):
        label = _SECTOR_GAP_LABELS.get(raw, "")
        if not label:
            for prefix, prefix_label in _SECTOR_GAP_PREFIX_LABELS:
                if raw.startswith(prefix):
                    label = prefix_label
                    break
        if not label:
            label = "其他关键事实" if re.match(r"^[A-Za-z][A-Za-z0-9_]*(?:[.:-].*)?$", raw) else raw
        if label and label not in seen:
            labels.append(label)
            seen.add(label)
    return "、".join(labels) or "无"


def _sector_transition_evidence_display_text(value: Any) -> str:
    items = []
    for raw in _strings(value):
        if raw.startswith("轮动复核="):
            status = raw.partition("=")[2]
            raw = "轮动复核=" + _SECTOR_TRANSITION_STATUS_LABELS.get(status, "待确认")
        items.append(raw)
    return "；".join(items) or "事实不足"


def _date(value: Any) -> str:
    text = _text(value)
    match = _DATE_RE.search(text)
    if not match:
        return ""
    candidate = match.group(1)
    try:
        parsed = date.fromisoformat(candidate)
    except ValueError:
        return ""
    return parsed.isoformat() if parsed.isoformat() == candidate else ""


def _stock_identity(value: Any) -> str:
    text = _text(value)
    if text in {"", "-", "无", "空仓"}:
        return ""
    match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9·]+)\((\d{6})\)", text)
    if match:
        return f"{match.group(1)}({match.group(2)})"
    return text


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _positive_b1(text: str) -> bool:
    if _contains_any(
        text,
        (
            "未确认成交",
            "不视为B1",
            "B1事实待确认",
            "没有B1",
            "无B1",
            "B1不成立",
            "不生成B1",
            "0%不参与",
            "不参与",
        ),
    ):
        return False
    return _contains_any(text, ("B1参与权", "B1先到", "已有1x/50%", "视为B1"))


def canonical_dual_cluster_projection_hash(payload: Any) -> str:
    return stable_json_hash(
        payload if isinstance(payload, Mapping) else {},
        excluded_keys={"artifact_hash"},
    )


def _capacity_summary(
    *,
    asset: str,
    combined_text: str,
    pending: bool,
    existing_core_asset: str = "",
) -> str:
    if pending:
        return "账户事实未完整；B1/B2均待确认"
    if "已有1x/50%" in combined_text and "B2" in combined_text:
        return "核心端占用=1x/50%；B2待确认=另1x/50%"
    if (
        existing_core_asset
        and asset
        and existing_core_asset != asset
        and "B1先到1x/50%" in combined_text
    ):
        return "核心端占用已记录；冲击端B1计划=1x/50%；B2待确认，账户总量上限=2x/100%"
    if "B1先到1x/50%" in combined_text and "2x/100%" in combined_text:
        return "冲击端B1=1x/50%；B2待确认=另1x/50%"
    if "B1参与权=1x/50%" in combined_text and (
        "本计划无B2" in combined_text or "不追加B2" in combined_text
    ):
        return "冲击端B1=1x/50%；本计划无B2"
    if "只定Te的B1+B2预案" in combined_text:
        prefix = "当前核心占用不变" if asset else "当前0x/0%"
        return f"{prefix}；Te为B1+B2条件预案"
    if "只定Te的B1预案" in combined_text:
        prefix = "当前核心占用不变" if asset else "当前0x/0%"
        return f"{prefix}；Te只预留B1参与权"
    if _contains_any(combined_text, _EMPTY_MARKERS) and not asset:
        return "0x/0%；无账户占用"
    if asset:
        return "核心端占用已记录；具体档位未单列"
    return "账户容量待确认"


def _account_input_rows(rows: Any) -> list[dict]:
    normalized = []
    for raw in _list(rows):
        row = _mapping(raw)
        code = _text(row.get("day_code") or row.get("code"))
        if code not in _DAY_ORDER_CODES:
            continue
        normalized.append(
            {
                "day_code": code,
                "date": _date(row.get("date")),
                "account": _text(row.get("account")),
                "target": _text(row.get("target")),
                "b12": _text(row.get("b12")),
                "action": _text(row.get("action")),
            }
        )
    normalized.sort(key=lambda item: _DAY_ORDER_CODES.index(item["day_code"]))
    return normalized


def build_account_day_order_dual_cluster(
    rows: Any,
    *,
    target_date: Any = "",
) -> dict:
    normalized_rows = _account_input_rows(rows)
    if not normalized_rows:
        return {}
    by_code = {row["day_code"]: row for row in normalized_rows}
    normalized_target_date = _date(target_date) or _date(
        _mapping(by_code.get("Td")).get("date")
    )
    td_date = _date(_mapping(by_code.get("Td")).get("date"))
    if normalized_target_date and td_date and td_date != normalized_target_date:
        return {}
    future_fact_codes = [
        row["day_code"]
        for row in normalized_rows
        if row["day_code"] != "Te"
        and row["date"]
        and normalized_target_date
        and row["date"] > normalized_target_date
    ]
    if future_fact_codes:
        return {}

    source_dates = sorted(
        {
            row["date"]
            for row in normalized_rows
            if row["day_code"] != "Te"
            and row["date"]
            and (not normalized_target_date or row["date"] <= normalized_target_date)
        }
    )
    plan_date = _mapping(by_code.get("Te")).get("date", "")
    missing_fields = []
    if not normalized_target_date:
        missing_fields.append("target_date")
    missing_fields.extend(
        f"{code}.date"
        for code in _DAY_ORDER_CODES
        if code in by_code and not by_code[code].get("date")
    )
    missing_fields.extend(
        f"{code}.row"
        for code in _DAY_ORDER_CODES
        if code not in by_code
    )

    projection_rows = []
    previous_confirmed_asset = ""
    previous_role = ""
    for row in normalized_rows:
        code = row["day_code"]
        combined = "；".join(
            part
            for part in (
                row["account"],
                row["target"],
                row["b12"],
                row["action"],
            )
            if part
        )
        target_asset = _stock_identity(row["target"])
        account_asset = _stock_identity(row["account"])
        if (
            code != "Te"
            and not target_asset
            and account_asset
            and re.search(r"\(\d{6}\)", account_asset)
        ):
            target_asset = account_asset
        asset = target_asset
        pending = _contains_any(combined, _PENDING_MARKERS)
        explicitly_empty = not asset and _contains_any(combined, _EMPTY_MARKERS)
        positive_b1 = _positive_b1(combined)
        explicit_core = bool(
            asset
            and _contains_any(combined, _CORE_MARKERS)
            and not _contains_any(combined, ("不用旧仓", "无旧仓", "没有旧仓"))
        )
        explicit_dynamic = bool(asset and _contains_any(combined, _DYNAMIC_MARKERS))
        same_as_previous = bool(asset and previous_confirmed_asset == asset)
        different_from_previous = bool(
            asset and previous_confirmed_asset and previous_confirmed_asset != asset
        )

        core_status = "unresolved"
        core_text = "角色待确认"
        impact_status = "unresolved"
        impact_text = "角色待确认"
        transition_status = "unresolved"
        transition_text = "迁移待确认"

        if pending:
            pass
        elif explicitly_empty:
            core_status = "empty"
            core_text = "无持续核心占用"
            impact_status = "empty"
            impact_text = "无新增冲击参与"
            if previous_confirmed_asset and previous_role == "dynamic_impact":
                transition_status = "dynamic_decay"
                transition_text = "动态冲击端 → 衰减"
            elif previous_confirmed_asset and _contains_any(combined, _WEAKEN_MARKERS):
                transition_status = "core_weakened"
                transition_text = "持续核心端 → 弱化"
            elif previous_confirmed_asset:
                transition_status = "exposure_ended"
                transition_text = "核心占用结束"
            else:
                transition_status = "empty"
                transition_text = "两端均未占用"
        elif asset:
            if code == "Te" and different_from_previous:
                core_status = "confirmed"
                core_text = f"{previous_confirmed_asset}：报告日核心占用延续"
            elif same_as_previous or explicit_core:
                core_status = "confirmed"
                core_text = (
                    f"{asset}：跨日延续"
                    if same_as_previous
                    else f"{asset}：旧仓/历史路径占用"
                )
            elif code == "Te":
                core_status = "unresolved"
                core_text = "持续核心端待确认"
            else:
                core_status = "candidate"
                core_text = f"{asset}：持续性待确认"

            if different_from_previous or explicit_dynamic or (code == "Te" and positive_b1):
                impact_status = "confirmed" if positive_b1 or different_from_previous else "candidate"
                impact_text = (
                    f"{asset}：新目标B1参与权"
                    if code == "Te" and positive_b1
                    else f"{asset}：动态冲击候选"
                )
            else:
                impact_status = "empty"
                impact_text = "无新增冲击参与"

            if _contains_any(combined, _DECAY_MARKERS):
                transition_status = "dynamic_decay"
                transition_text = "动态冲击端 → 衰减"
            elif _contains_any(combined, _WEAKEN_MARKERS) and core_status == "confirmed":
                transition_status = "core_weakened"
                transition_text = "持续核心端 → 弱化"
            elif same_as_previous and previous_role == "dynamic_impact":
                transition_status = "impact_to_core"
                transition_text = "动态冲击端 → 持续核心端"
            elif different_from_previous and code == "Te" and core_status == "confirmed":
                transition_status = "coexisting"
                transition_text = "两端并存：旧仓路径 + 新目标B1"
            elif different_from_previous:
                transition_status = "core_to_impact"
                transition_text = "持续核心端 → 动态冲击端"
            elif same_as_previous:
                transition_status = "core_continues"
                transition_text = "持续核心端延续"
            elif impact_status in {"confirmed", "candidate"}:
                transition_status = "impact_formed"
                transition_text = "动态冲击端形成，持续性待确认"

        if pending:
            evidence_status = "事实不足"
        elif core_status == "confirmed" or impact_status == "confirmed":
            evidence_status = "已有账户证据"
        elif explicitly_empty:
            evidence_status = "空仓事实已记录"
        else:
            evidence_status = "角色待确认"

        projection_rows.append(
            {
                "day_code": code,
                "date": row["date"],
                "temporal_role": {
                    "Ta": "最远复盘日",
                    "Tb": "历史复盘日",
                    "Tc": "上一交易日",
                    "Td": "报告日账户事实",
                    "Te": "已决定的明日计划",
                }[code],
                "persistent_core": {
                    "status": core_status,
                    "text": core_text,
                },
                "dynamic_impact": {
                    "status": impact_status,
                    "text": impact_text,
                },
                "transition": {
                    "status": transition_status,
                    "text": transition_text,
                },
                "capacity": _capacity_summary(
                    asset=asset,
                    combined_text=combined,
                    pending=pending,
                    existing_core_asset=(
                        previous_confirmed_asset
                        if code == "Te" and core_status == "confirmed"
                        else ""
                    ),
                ),
                "action": row["action"] or "事实不足",
                "evidence_status": evidence_status,
            }
        )

        if not pending and asset:
            previous_confirmed_asset = asset
            previous_role = (
                "dynamic_impact"
                if impact_status in {"confirmed", "candidate"}
                and not same_as_previous
                else "persistent_core"
                if core_status == "confirmed"
                else previous_role
            )
        elif explicitly_empty:
            previous_confirmed_asset = ""
            previous_role = ""

    input_payload = {
        "target_date": normalized_target_date,
        "plan_date": plan_date,
        "rows": normalized_rows,
    }
    artifact = {
        "schema_version": ACCOUNT_SCHEMA_VERSION,
        "decision_scope": DECISION_SCOPE,
        "formal_effect": FORMAL_EFFECT,
        "target_date": normalized_target_date,
        "plan_date": plan_date,
        "source_dates": source_dates,
        "rows": projection_rows,
        "missing_fields": sorted(set(missing_fields)),
        "counter_evidence": [
            "旧仓不自动等于市场核心",
            "新目标不确认参与者身份",
            "计划容量不等于已经持有",
        ],
        "input_hash": stable_json_hash(input_payload),
    }
    artifact["artifact_hash"] = canonical_dual_cluster_projection_hash(artifact)
    return artifact


def _iter_date_values(value: Any, *, key: str = ""):
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            yield from _iter_date_values(child_value, key=_text(child_key).lower())
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_date_values(item, key=key)
        return
    if key.endswith("_date") or key.endswith("_dates") or key in {
        "date",
        "trade_date",
        "target_date",
        "as_of_date",
    }:
        if parsed := _date(value):
            yield parsed


def _sector_source_is_valid(evidence: dict, target_date: str) -> bool:
    source_hash = _text(evidence.get("artifact_hash"))
    if (
        evidence.get("schema_version") != SOURCE_SECTOR_SCHEMA_VERSION
        or evidence.get("decision_scope") != DECISION_SCOPE
        or evidence.get("formal_effect") != FORMAL_EFFECT
    ):
        return False
    if not _SHA256_RE.fullmatch(source_hash):
        return False
    if canonical_dual_cluster_projection_hash(evidence) != source_hash:
        return False
    if _date(evidence.get("target_date")) != target_date:
        return False
    return not any(item > target_date for item in _iter_date_values(evidence))


def _sector_core_projection(evidence: dict) -> dict:
    stage_mainline = _mapping(evidence.get("stage_mainline"))
    foundation = _mapping(evidence.get("sector_foundation"))
    direction = _text(
        stage_mainline.get("cycle_mainline")
        or evidence.get("direction")
        or foundation.get("direction")
    )
    status = _text(stage_mainline.get("status"))
    continuity_dates = sorted(
        {
            parsed
            for item in _list(foundation.get("continuity_dates"))
            if (parsed := _date(item))
        }
    )
    span = stage_mainline.get("stage_span_trading_days")
    relative_metric = _mapping(stage_mainline.get("relative_strength_metric"))
    relative_value = relative_metric.get("value")
    slope_up = (
        foundation.get("sector_index_slope") == "向上"
        or (isinstance(relative_value, (int, float)) and not isinstance(relative_value, bool) and relative_value > 0)
    )
    density_known = (
        isinstance(stage_mainline.get("trend_stock_count"), int)
        and isinstance(stage_mainline.get("comparable_stock_count"), int)
        and stage_mainline.get("comparable_stock_count") > 0
    )
    cross_day = len(continuity_dates) >= 2 or (
        isinstance(span, int) and not isinstance(span, bool) and span >= 2
    )
    reflow_dates = [
        parsed
        for item in _list(stage_mainline.get("reflow_dates"))
        if (parsed := _date(item))
    ]
    evidence_items = []
    if cross_day:
        evidence_items.append("跨日持续已记录")
    if reflow_dates:
        evidence_items.append("冷却后回流=" + " -> ".join(reflow_dates))
    if slope_up:
        evidence_items.append("板块指数相对路径向上")
    if density_known:
        evidence_items.append(
            f"内部趋势股={stage_mainline.get('trend_stock_count')}/{stage_mainline.get('comparable_stock_count')}"
        )
    divergence = _text(stage_mainline.get("divergence_test_status"))
    if divergence and divergence not in {"事实不足", "尚未进入阶段分歧检验"}:
        evidence_items.append("分歧检验=" + divergence)

    if status == "阶段主线已确认" and direction and cross_day and slope_up and density_known:
        role_status = "confirmed"
        summary = f"{direction}：持续核心端已确认"
    elif status in {"阶段主线弱化", "阶段主线失效"}:
        role_status = "weakened" if status == "阶段主线弱化" else "invalidated"
        summary = f"{direction or '原阶段方向'}：{status}"
    elif direction:
        role_status = "candidate"
        summary = f"{direction}：持续核心端候选，证据尚未齐全"
    else:
        role_status = "unresolved"
        summary = "持续核心端待确认"

    gaps = []
    if not direction:
        gaps.append("阶段方向")
    if not cross_day:
        gaps.append("跨日持续")
    if not slope_up:
        gaps.append("板块指数相对强度")
    if not density_known:
        gaps.append("内部趋势股密度")
    return {
        "status": role_status,
        "direction": direction,
        "summary": summary,
        "last_confirmed_date": _date(stage_mainline.get("last_confirmed_date")),
        "evidence": evidence_items,
        "evidence_gaps": gaps,
    }


def _sector_impact_projection(evidence: dict) -> dict:
    stage_mainline = _mapping(evidence.get("stage_mainline"))
    liquidity = _mapping(evidence.get("liquidity_allocation_context"))
    target_date = _date(evidence.get("target_date"))
    direction = _text(stage_mainline.get("daily_attack_line"))
    direction_date = _date(stage_mainline.get("daily_attack_line_source_date"))
    time_stage = _text(_mapping(evidence.get("time_axis")).get("stage"))
    space_stage = _text(_mapping(evidence.get("space_axis")).get("stage"))
    evidence_items = []
    if direction and direction_date == target_date:
        evidence_items.append("当日主攻线已按目标日记录")
    allocation_pattern = _text(liquidity.get("allocation_pattern"))
    if allocation_pattern and allocation_pattern != "事实不足":
        evidence_items.append("量能分配=" + allocation_pattern)
    if time_stage and time_stage != "事实不足":
        evidence_items.append("时间阶段=" + time_stage)
    if space_stage and space_stage != "事实不足":
        evidence_items.append("空间位置=" + space_stage)

    if direction and direction_date == target_date:
        status = "confirmed"
        summary = f"{direction}：目标日动态冲击端"
    elif direction:
        status = "candidate"
        summary = f"{direction}：冲击日期未完成目标日校验"
    else:
        status = "unresolved"
        summary = "动态冲击端待确认"
    return {
        "status": status,
        "direction": direction,
        "source_date": direction_date,
        "summary": summary,
        "evidence": evidence_items,
        "evidence_gaps": [] if status == "confirmed" else ["目标日主攻线"],
    }


def _sector_transition_projection(evidence: dict, core: dict, impact: dict) -> dict:
    stage_mainline = _mapping(evidence.get("stage_mainline"))
    time_stage = _text(_mapping(evidence.get("time_axis")).get("stage"))
    core_status = core.get("status")
    impact_status = impact.get("status")
    core_direction = _text(core.get("direction"))
    impact_direction = _text(impact.get("direction"))
    phase_rotation = _text(stage_mainline.get("phase_rotation_status"))
    recognition_date = _date(stage_mainline.get("recognition_date"))
    target_date = _date(evidence.get("target_date"))

    if core_status in {"weakened", "invalidated"} and impact_status == "confirmed":
        status = "core_to_impact"
        summary = "持续核心端 → 动态冲击端"
    elif core_status == "confirmed" and impact_status == "confirmed" and core_direction != impact_direction:
        status = "coexisting"
        summary = "两端并存：阶段核心与当日主攻分离"
    elif (
        core_status == "confirmed"
        and impact_status == "confirmed"
        and core_direction == impact_direction
        and (recognition_date == target_date or phase_rotation == "confirmed")
    ):
        status = "impact_to_core"
        summary = "动态冲击端 → 持续核心端"
    elif impact_status == "confirmed" and time_stage in {"传导受阻", "趋势破坏候选"}:
        status = "dynamic_decay"
        summary = "动态冲击端 → 衰减"
    elif core_status in {"weakened", "invalidated"}:
        status = "core_weakened"
        summary = "持续核心端 → 弱化"
    elif core_status == "confirmed" and impact_status != "confirmed":
        status = "core_continues"
        summary = "持续核心端延续；新冲击待确认"
    elif impact_status == "confirmed":
        status = "impact_unconfirmed"
        summary = "动态冲击端已出现；能否迁移为核心待确认"
    else:
        status = "unresolved"
        summary = "迁移待确认"
    return {
        "status": status,
        "summary": summary,
        "evidence": [
            item
            for item in (
                _text(stage_mainline.get("daily_attack_relation")),
                f"阶段识别日={recognition_date}" if recognition_date else "",
                f"轮动复核={phase_rotation}" if phase_rotation else "",
            )
            if item
        ],
    }


def build_sector_tournament_dual_cluster(
    three_axis_evidence: Any,
    *,
    target_date: Any = "",
) -> dict:
    evidence = deepcopy(_mapping(three_axis_evidence))
    normalized_target_date = _date(target_date) or _date(evidence.get("target_date"))
    if not evidence or not normalized_target_date or not _sector_source_is_valid(
        evidence,
        normalized_target_date,
    ):
        return {}

    source_dates = sorted(
        {
            parsed
            for item in _list(evidence.get("source_dates"))
            if (parsed := _date(item)) and parsed <= normalized_target_date
        }
    )
    core = _sector_core_projection(evidence)
    impact = _sector_impact_projection(evidence)
    transition = _sector_transition_projection(evidence, core, impact)
    evidence_gaps = sorted(
        set(
            _strings(evidence.get("missing_fields"))
            + _strings(core.get("evidence_gaps"))
            + _strings(impact.get("evidence_gaps"))
        )
    )
    artifact = {
        "schema_version": SECTOR_SCHEMA_VERSION,
        "decision_scope": DECISION_SCOPE,
        "formal_effect": FORMAL_EFFECT,
        "target_date": normalized_target_date,
        "source_dates": source_dates,
        "source_artifact_schema": _text(evidence.get("schema_version")),
        "source_artifact_hash": _text(evidence.get("artifact_hash")),
        "persistent_core": core,
        "dynamic_impact": impact,
        "transition_band": transition,
        "evidence_gaps": evidence_gaps,
        "counter_evidence": _strings(evidence.get("counter_evidence"))
        or ["暂无明确反方证据"],
        "scope_text": "只解释持续核心、动态冲击与迁移，不改变明日对象、仓位或B1/B2。",
    }
    artifact["artifact_hash"] = canonical_dual_cluster_projection_hash(artifact)
    return artifact


def validate_dual_cluster_projection(
    value: Any,
    *,
    target_date: Any = "",
    expected_schema: str = "",
) -> bool:
    artifact = _mapping(value)
    if not artifact:
        return False
    schema_version = _text(artifact.get("schema_version"))
    if schema_version not in {ACCOUNT_SCHEMA_VERSION, SECTOR_SCHEMA_VERSION}:
        return False
    if expected_schema and schema_version != expected_schema:
        return False
    if artifact.get("decision_scope") != DECISION_SCOPE or artifact.get("formal_effect") != FORMAL_EFFECT:
        return False
    expected_target = _date(target_date)
    artifact_target = _date(artifact.get("target_date"))
    if expected_target and artifact_target != expected_target:
        return False
    if schema_version == SECTOR_SCHEMA_VERSION and not artifact_target:
        return False
    if (
        schema_version == SECTOR_SCHEMA_VERSION
        and artifact_target
        and any(item > artifact_target for item in _iter_date_values(artifact))
    ):
        return False
    if schema_version == ACCOUNT_SCHEMA_VERSION and artifact_target:
        for row in _list(artifact.get("rows")):
            normalized_row = _mapping(row)
            row_date = _date(normalized_row.get("date"))
            if normalized_row.get("day_code") == "Td" and row_date and row_date != artifact_target:
                return False
            if normalized_row.get("day_code") != "Te" and row_date and row_date > artifact_target:
                return False
    if artifact_target and any(
        parsed > artifact_target
        for item in _list(artifact.get("source_dates"))
        if (parsed := _date(item))
    ):
        return False
    artifact_hash = _text(artifact.get("artifact_hash"))
    return bool(
        _SHA256_RE.fullmatch(artifact_hash)
        and canonical_dual_cluster_projection_hash(artifact) == artifact_hash
    )


def normalize_dual_cluster_projection(
    value: Any,
    *,
    target_date: Any = "",
    expected_schema: str = "",
) -> dict:
    return (
        deepcopy(_mapping(value))
        if validate_dual_cluster_projection(
            value,
            target_date=target_date,
            expected_schema=expected_schema,
        )
        else {}
    )


def sector_dual_cluster_display(value: Any, *, target_date: Any = "") -> dict:
    artifact = normalize_dual_cluster_projection(
        value,
        target_date=target_date,
        expected_schema=SECTOR_SCHEMA_VERSION,
    )
    if not artifact:
        return {
            "available": False,
            "persistent_core": "持续核心端待确认",
            "persistent_core_evidence": "跨日、回流、指数强度或内部趋势密度不完整",
            "dynamic_impact": "动态冲击端待确认",
            "dynamic_impact_evidence": "目标日主攻线或响应事实不完整",
            "transition": "迁移待确认",
            "transition_evidence": "尚无同源迁移证据",
            "gaps": "双群聚投影未通过目标日校验",
            "counter_evidence": "暂无明确反方证据",
            "artifact_hash": "",
            "scope_text": "只解释持续核心、动态冲击与迁移，不改变明日对象、仓位或B1/B2。",
        }
    core = _mapping(artifact.get("persistent_core"))
    impact = _mapping(artifact.get("dynamic_impact"))
    transition = _mapping(artifact.get("transition_band"))
    return {
        "available": True,
        "persistent_core": _text(core.get("summary")) or "持续核心端待确认",
        "persistent_core_evidence": "；".join(_strings(core.get("evidence"))) or "事实不足",
        "dynamic_impact": _text(impact.get("summary")) or "动态冲击端待确认",
        "dynamic_impact_evidence": "；".join(_strings(impact.get("evidence"))) or "事实不足",
        "transition": _text(transition.get("summary")) or "迁移待确认",
        "transition_evidence": _sector_transition_evidence_display_text(
            transition.get("evidence")
        ),
        "gaps": _sector_gap_display_text(artifact.get("evidence_gaps")),
        "counter_evidence": "；".join(_strings(artifact.get("counter_evidence"))) or "无",
        "artifact_hash": _text(artifact.get("artifact_hash")),
        "scope_text": _text(artifact.get("scope_text")),
    }


__all__ = [
    "ACCOUNT_SCHEMA_VERSION",
    "SECTOR_SCHEMA_VERSION",
    "build_account_day_order_dual_cluster",
    "build_sector_tournament_dual_cluster",
    "canonical_dual_cluster_projection_hash",
    "normalize_dual_cluster_projection",
    "sector_dual_cluster_display",
    "validate_dual_cluster_projection",
]
