from __future__ import annotations

__all__ = ["build_anchor_reversal_decision"]


def _clean_text(value):
    return str(value or "").strip()


def _stock_code(candidate):
    text = _clean_text((candidate or {}).get("code") or (candidate or {}).get("代码")).upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _stock_name(candidate):
    return _clean_text((candidate or {}).get("name") or (candidate or {}).get("名称"))


def _stock_label(name, code):
    if name and code:
        return f"{name}({code})"
    return name or code or ""


def _sector(candidate):
    return _clean_text(
        (candidate or {}).get("trade_narrative_sector")
        or (candidate or {}).get("active_trade_sector")
        or (candidate or {}).get("主 tag")
        or (candidate or {}).get("sector")
        or (candidate or {}).get("板块")
    )


def _raw_sector(candidate):
    return _clean_text(
        (candidate or {}).get("raw_sector")
        or (candidate or {}).get("industry")
        or (candidate or {}).get("所属行业")
        or (candidate or {}).get("sector_name")
    )


def _combined_text(candidate):
    candidate = candidate or {}
    parts = []
    for key in (
        "candidate_role",
        "reason",
        "conviction_reason",
        "core_level",
        "leader_speed_tier",
        "capacity_profile",
        "turnover_capacity",
        "volume_capacity",
        "ma_binding_strategy",
        "holding_strategy",
        "position_strategy",
        "acceptance_profile",
        "acceptance_repair_required",
        "pattern",
        "xuangubao_stock_reason",
        "xueqiu_hot_stock_argument",
        "xueqiu_hot_stock_reason",
        "trade_narrative_reason",
    ):
        value = candidate.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    return " / ".join(parts)


def _text_has_any(text, markers):
    return any(marker in str(text or "") for marker in markers)


def _sector_matches(a, b):
    a = _clean_text(a)
    b = _clean_text(b)
    return bool(a and b and (a in b or b in a))


def _anchor_from_snapshot_row(row):
    row = row or {}
    anchor_code = _stock_code({"code": row.get("anchor_code")})
    anchor_name = _clean_text(row.get("anchor_name"))
    if not (anchor_code or anchor_name):
        return {}
    return {
        "sector": _clean_text(row.get("sector")),
        "anchor_name": anchor_name,
        "anchor_code": anchor_code,
        "anchor_reason": _clean_text(row.get("anchor_reason")),
        "anchor_status": _clean_text(row.get("anchor_status") or row.get("status")),
    }


def _ma_binding_strategy(candidate, anchor=None):
    explicit = _clean_text(
        (candidate or {}).get("ma_binding_strategy")
        or (candidate or {}).get("holding_strategy")
        or (candidate or {}).get("position_strategy")
        or (candidate or {}).get("均线策略")
    )
    if explicit:
        return explicit
    text = " / ".join(
        value
        for value in (
            _combined_text(candidate),
            (anchor or {}).get("anchor_reason"),
        )
        if value
    )
    if _text_has_any(text, ("MA5入/MA7清/MA5T", "MA5B", "MA7清", "MA5T")):
        return "MA5入/MA7清/MA5T"
    return ""


def _anchor_certainty_path(candidate, anchor=None):
    strategy = _ma_binding_strategy(candidate, anchor)
    text = " / ".join(
        value
        for value in (
            _combined_text(candidate),
            (anchor or {}).get("anchor_reason"),
        )
        if value
    )
    if strategy and _text_has_any(text, ("承接", "趋势比价链", "大容量", "趋势资金", "沿MA5", "缩量回踩")):
        return f"板块锚优先，{strategy}和承接路径明确"
    if _text_has_any(text, ("大容量", "趋势资金", "趋势比价链", "反复做", "热门股")):
        return "板块锚优先，容量和趋势承接优先于一日涨停"
    return "板块锚优先，涨停只作辅助证据"


def _find_sector_anchor(candidate, sector_snapshot, mainline_name=""):
    candidate_sector = _sector(candidate)
    mainline_name = _clean_text(mainline_name)
    raw_sector = _raw_sector(candidate)
    has_trade_narrative_migration = bool(
        candidate_sector
        and mainline_name
        and raw_sector
        and _sector_matches(raw_sector, mainline_name)
        and not _sector_matches(candidate_sector, mainline_name)
    )
    if mainline_name and not has_trade_narrative_migration:
        for row in sector_snapshot or []:
            row_sector = _clean_text((row or {}).get("sector"))
            if row_sector and _sector_matches(row_sector, mainline_name):
                anchor = _anchor_from_snapshot_row(row)
                if anchor:
                    return anchor
    for row in sector_snapshot or []:
        row_sector = _clean_text((row or {}).get("sector"))
        if candidate_sector and row_sector and not _sector_matches(candidate_sector, row_sector):
            continue
        anchor = _anchor_from_snapshot_row(row)
        if anchor:
            return anchor
    if not sector_snapshot:
        return {}
    return {}


def _candidate_role(candidate, *, is_anchor=False):
    if is_anchor:
        return "板块锚"
    explicit = _clean_text((candidate or {}).get("candidate_role") or (candidate or {}).get("候选身份"))
    if explicit:
        return explicit
    text = _combined_text(candidate)
    if _text_has_any(text, ("套利工具", "套利载体", "阶段套利")):
        return "套利工具"
    if _text_has_any(text, ("低位补涨", "补涨")):
        return "低位补涨"
    if _text_has_any(text, ("跟风", "被带动")):
        return "跟风样本"
    if _text_has_any(text, ("分支龙头", "分支核心", "趋势比价链核心", "趋势核心")):
        return "分支龙头"
    if _text_has_any(text, ("大容量", "容量龙", "中军", "趋势资金", "large", "large_capacity")):
        return "大容量中军"
    if _text_has_any(text, ("龙头", "龙一", "板块锚", "锚定龙", "趋势比价链锚点")):
        return "分支龙头"
    if _text_has_any(text, ("修复观察", "龙回头")):
        return "修复观察"
    return "观察样本"


def _anchor_is_failed(anchor):
    text = " / ".join(
        value
        for value in (
            (anchor or {}).get("anchor_status"),
            (anchor or {}).get("anchor_reason"),
        )
        if value
    )
    return _text_has_any(text, ("失效", "走弱", "破位", "A杀", "退潮", "杀跌", "龙头死"))


def build_anchor_reversal_decision(candidate, *, sector_snapshot=None, mainline_name=""):
    candidate = dict(candidate or {})
    code = _stock_code(candidate)
    name = _stock_name(candidate)
    anchor = _find_sector_anchor(candidate, sector_snapshot or [], mainline_name=mainline_name)
    anchor_code = anchor.get("anchor_code", "")
    anchor_name = anchor.get("anchor_name", "")
    anchor_label = _stock_label(anchor_name, anchor_code)
    is_anchor = bool(anchor_code and code and anchor_code == code)
    role = _candidate_role(candidate, is_anchor=is_anchor)
    why_not_anchor = _clean_text(
        candidate.get("why_not_anchor")
        or candidate.get("为什么不做板块锚")
        or candidate.get("为什么不做锚")
        or candidate.get("为什么不做龙头")
    )
    anchor_failed = _anchor_is_failed(anchor)
    ma_strategy = _ma_binding_strategy(candidate, anchor)
    certainty_path = _anchor_certainty_path(candidate, anchor)
    limit_up_role = "涨停只是证据，不能替代板块锚和承接路径"

    if not anchor_label:
        return {
            "sector_anchor": "",
            "candidate_role": role,
            "relationship_to_anchor": "板块锚未识别，先保留原有排序证据",
            "why_not_anchor": why_not_anchor,
            "repair_priority": "待识别",
            "anchor_reversal_decision": "降级观察",
            "anchor_reversal_reason": "板块锚未识别，不能说明为什么不做板块锚",
            "ma_binding_strategy": ma_strategy,
            "leader_certainty_path": certainty_path,
            "limit_up_evidence_role": limit_up_role,
        }

    if is_anchor:
        reason = "候选就是板块锚，分歧后资金优先回看"
        if ma_strategy:
            reason = f"候选就是板块锚，{ma_strategy}和承接路径明确，涨停只是证据，慢即是快"
        return {
            "sector_anchor": anchor_label,
            "candidate_role": "板块锚",
            "relationship_to_anchor": "资金回流优先看板块锚，候选本身就是板块锚",
            "why_not_anchor": why_not_anchor,
            "repair_priority": "优先修复",
            "anchor_reversal_decision": "可作为主对象",
            "anchor_reversal_reason": reason,
            "ma_binding_strategy": ma_strategy,
            "leader_certainty_path": certainty_path,
            "limit_up_evidence_role": limit_up_role,
        }

    if anchor_failed and role in {"低位补涨", "套利工具", "跟风样本"}:
        return {
            "sector_anchor": anchor_label,
            "candidate_role": role,
            "relationship_to_anchor": f"板块锚已失效，{role}会放大回撤风险",
            "why_not_anchor": why_not_anchor,
            "repair_priority": "风险放大",
            "anchor_reversal_decision": "不参与",
            "anchor_reversal_reason": f"板块锚已失效，后排风险更大；不能把{role}当成{anchor_label}的替代品",
            "ma_binding_strategy": ma_strategy,
            "leader_certainty_path": certainty_path,
            "limit_up_evidence_role": limit_up_role,
        }

    if why_not_anchor and role in {"分支龙头", "大容量中军"}:
        return {
            "sector_anchor": anchor_label,
            "candidate_role": role,
            "relationship_to_anchor": f"相对{anchor_label}提供补位承接，需要继续验证板块同步",
            "why_not_anchor": why_not_anchor,
            "repair_priority": "次优先修复",
            "anchor_reversal_decision": "可作为补位",
            "anchor_reversal_reason": why_not_anchor,
            "ma_binding_strategy": ma_strategy,
            "leader_certainty_path": certainty_path,
            "limit_up_evidence_role": limit_up_role,
        }

    if role in {"低位补涨", "套利工具", "跟风样本"}:
        return {
            "sector_anchor": anchor_label,
            "candidate_role": role,
            "relationship_to_anchor": f"被{anchor_label}带动，只能反馈板块强度",
            "why_not_anchor": why_not_anchor,
            "repair_priority": "后排修复",
            "anchor_reversal_decision": "降级观察",
            "anchor_reversal_reason": f"{role}不能替代板块锚；涨停只是证据，无法说明为什么不做{anchor_label}",
            "ma_binding_strategy": ma_strategy,
            "leader_certainty_path": certainty_path,
            "limit_up_evidence_role": limit_up_role,
        }

    return {
        "sector_anchor": anchor_label,
        "candidate_role": role,
        "relationship_to_anchor": f"未证明比{anchor_label}更值得参与",
        "why_not_anchor": why_not_anchor,
        "repair_priority": "后排修复",
        "anchor_reversal_decision": "降级观察",
        "anchor_reversal_reason": f"不能替代板块锚；无法说明为什么不做{anchor_label}",
        "ma_binding_strategy": ma_strategy,
        "leader_certainty_path": certainty_path,
        "limit_up_evidence_role": limit_up_role,
    }
